#!/usr/bin/env python3
"""Read-only public-URL audit; availability and text signals are not fact verification.

Fetches bounded GET bodies, follows public redirects, records every asset/source URL,
and produces a reproducible ledger. Run with --refresh to ignore the local cache.
"""

import argparse
import hashlib
import ipaddress
import json
import re
import socket
import threading
import time
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
HOST_LOCKS = defaultdict(lambda: threading.Semaphore(2))
MAX_BYTES = 1024 * 1024


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.title_parts = []
        self.hidden = 0
        self.title_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "title":
            self.title_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.title_depth:
                self.title_parts.append(data)


def public_url(url):
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("Only credential-free public HTTP(S) URLs are supported")
    port = p.port or (443 if p.scheme == "https" else 80)
    if port not in {80, 443}:
        raise ValueError("Nonstandard port blocked")
    addresses = {a[4][0] for a in socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("Private/local/reserved address blocked")


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, cache, refresh):
    key = hashlib.sha256(url.encode()).hexdigest()
    cache_file = cache / (key + ".json")
    if cache_file.exists() and not refresh:
        cached = json.loads(cache_file.read_text())
        cached_text = cached.get("text", "")
        # Earlier snapshots could misread an unsolicited gzip body as HTML.
        if not cached_text or cached_text.count("\ufffd") / len(cached_text) <= 0.01:
            return cached
    result = {"url": url, "checked_at": datetime.now(timezone.utc).isoformat(), "method": "GET"}
    with HOST_LOCKS[urlsplit(url).hostname]:
        started = time.monotonic()
        try:
            public_url(url)
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; COSOLVE-Source-Audit/1.0)",
                    "Accept": "text/html,application/json,application/pdf;q=0.9,*/*;q=0.8",
                },
            )
            try:
                response = build_opener(PublicRedirects()).open(request, timeout=15)
            except HTTPError as error:
                response = error
            with response:
                body = response.read(MAX_BYTES + 1)
                result.update(
                    http_status=response.code,
                    final_url=response.geturl(),
                    content_type=response.headers.get("Content-Type", ""),
                    content_encoding=response.headers.get("Content-Encoding", ""),
                    body_truncated=len(body) > MAX_BYTES,
                )
                body = body[:MAX_BYTES]
                result["body_bytes"] = len(body)
                result["body_sha256"] = hashlib.sha256(body).hexdigest()
                if body.startswith(b"\x1f\x8b"):
                    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    body = decoder.decompress(body, MAX_BYTES + 1)
                    result["decompressed_body_truncated"] = len(body) > MAX_BYTES
                    body = body[:MAX_BYTES]
                if "pdf" in result["content_type"].lower() or body.startswith(b"%PDF"):
                    result.update(title="", text="", content_screen="pdf_not_extracted")
                else:
                    encoding = response.headers.get_content_charset() or "utf-8"
                    decoded = body.decode(encoding, errors="replace")
                    parser = TextParser()
                    parser.feed(decoded)
                    result.update(
                        title=" ".join(parser.title_parts).strip(),
                        text=re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip(),
                    )
                    result["content_screen"] = (
                        "readable_text" if len(result["text"]) >= 100 else "limited_or_empty_text"
                    )
            status = result["http_status"]
            title = result.get("title", "").lower()
            opening = result.get("text", "")[:1000].lower()
            if status in {404, 410}:
                result["classification"] = "http_not_found"
            elif status in {401, 403, 406, 418, 429} or any(
                t in title
                for t in ("just a moment", "access denied", "attention required", "robot challenge")
            ):
                result["classification"] = "access_blocked_or_rate_limited"
            elif status >= 500:
                result["classification"] = "server_error"
            elif status >= 400:
                result["classification"] = "http_error"
            elif any(
                t in title
                for t in (
                    "page not found",
                    "page cannot be found",
                    "404 not found",
                    "domain for sale",
                )
            ):
                result["classification"] = "suspected_soft_404"
            elif '"error"' in opening and '"code"' in opening and "arcgis" in url.lower():
                result["classification"] = "api_error_in_success_response"
            else:
                result["classification"] = "reachable"
            original, final = urlsplit(url), urlsplit(result["final_url"])
            result["redirected_to_homepage"] = bool(
                original.path.strip("/") and not final.path.strip("/")
            )
            if result["redirected_to_homepage"] and result["classification"] == "reachable":
                result["classification"] = "redirected_to_homepage_review"
        except (ValueError, OSError, TimeoutError, URLError) as error:
            result.update(classification="network_or_tls_error", error=str(error)[:400])
        except Exception as error:
            result.update(
                classification="unexpected_error", error=f"{type(error).__name__}: {error}"[:400]
            )
        result["duration_seconds"] = round(time.monotonic() - started, 2)
        cache_file.write_text(json.dumps(result, ensure_ascii=False))
        return result


def inventory(records):
    urls = defaultdict(list)
    for record in records:
        for field, value in record.items():
            if field.endswith("_url") and isinstance(value, str) and value:
                urls[value].append({"asset": record["name"], "field": field})
        for source in record.get("sources", []):
            if source.get("url"):
                urls[source["url"]].append(
                    {"asset": record["name"], "field": "sources", "title": source.get("title", "")}
                )
    return urls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/virginia_real_assets.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/source_audit_2026_09_04.json")
    parser.add_argument(
        "--cache", type=Path, default=Path("/private/tmp/cosolve-source-audit-2026-09-04")
    )
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    catalog_bytes = args.catalog.read_bytes()
    catalog = json.loads(catalog_bytes)
    records = catalog["records"]
    urls = inventory(records)
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 20))) as executor:
        futures = {executor.submit(fetch, url, args.cache, args.refresh): url for url in urls}
        for future in as_completed(futures):
            result = future.result()
            results[result["url"]] = result
            if len(results) % 50 == 0:
                counts = dict(Counter(r["classification"] for r in results.values()))
                print(
                    f"Checked {len(results)}/{len(urls)} URLs: {counts}",
                    flush=True,
                )
    assets = []
    for record in records:
        source_urls = list(
            dict.fromkeys(s["url"] for s in record.get("sources", []) if s.get("url"))
        )
        usable_urls = [
            u
            for u in source_urls
            if results[u]["classification"] in {"reachable", "redirected_to_homepage_review"}
        ]
        texts = " ".join(results[u].get("text", "") for u in usable_urls).casefold()
        address = record.get("address_line", "")
        address_base = re.split(r",|\bSuite\b|\bSte\b", address, flags=re.I)[0].strip().casefold()
        readable_count = sum(
            results[u].get("content_screen") == "readable_text" for u in usable_urls
        )
        record_urls = [
            u for u, refs in urls.items() if any(ref["asset"] == record["name"] for ref in refs)
        ]
        issues = [
            {"url": u, "classification": results[u]["classification"]}
            for u in record_urls
            if results[u]["classification"] != "reachable"
        ]
        reasons = []
        if any(
            i["classification"]
            in {"http_not_found", "suspected_soft_404", "api_error_in_success_response"}
            for i in issues
        ):
            reasons.append(
                "One or more links returned a missing-page/error response; "
                "independently verify and repair the source."
            )
        if any(i["classification"] == "redirected_to_homepage_review" for i in issues):
            reasons.append(
                "A deep link redirects to a homepage; determine whether its original "
                "specific evidence is still present."
            )
        if any(
            i["classification"]
            in {
                "access_blocked_or_rate_limited",
                "network_or_tls_error",
                "server_error",
                "unexpected_error",
            }
            for i in issues
        ):
            reasons.append(
                "Some links could not be checked conclusively because of blocking, "
                "transport/TLS, or server failures."
            )
        if not readable_count:
            reasons.append(
                "No successful readable HTML/text source was available to this checker; "
                "inspect PDF, JavaScript, or blocked sources separately."
            )
        if record["name"] == "Blue Ridge Defense Works" and any(
            i["url"] == "https://blueridgedefense.com/"
            and i["classification"] == "http_not_found"
            for i in issues
        ):
            reasons.append(
                "September 4 editorial follow-up: company homepage returned 404; "
                "exact-name web search did not corroborate the claimed Virginia counter-UAS "
                "role. The SAM page requires independent entity and capability review; "
                "do not infer closure or nonexistence."
            )
        assets.append(
            {
                "name": record["name"],
                "source_urls": source_urls,
                "source_classifications": dict(
                    Counter(results[u]["classification"] for u in source_urls)
                ),
                "readable_source_count": readable_count,
                "exact_name_text_match": record["name"].casefold() in texts,
                "address_text_match": bool(address_base and address_base in texts),
                "unmanned_keyword_text_match": bool(
                    re.search(
                        r"\b(?:unmanned|uncrewed|drone|drones|uas|uav|uxs|autonomous|"
                        r"robot|robots|robotics|auv|usv|uuv)\b",
                        texts,
                    )
                ),
                "editorial_verification": "not_performed_by_this_automated_audit",
                "url_issues": issues,
                "follow_up_reasons": reasons,
            }
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog_record_count": len(records),
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "unique_url_count": len(urls),
        "url_reference_count": sum(map(len, urls.values())),
        "classification_counts": dict(Counter(r["classification"] for r in results.values())),
        "methodology": (
            "Every nonempty catalog *_url field and attached sources[].url receives a bounded "
            "HTTP GET with public-address validation on the initial URL and every redirect; "
            "at most two concurrent requests per starting host and a 1 MiB body cap. HTTP/TLS "
            "failures and blocking are distinguished from successful fetches. HTML visible-text "
            "name/address/unmanned keyword signals help prioritize editorial review; they neither "
            "prove nor disprove a claim. The audit does not extract PDFs or render JavaScript. "
            "Cached responses retain their actual checked_at timestamps."
        ),
        "limitations": [
            "A reachable page is not proof that every associated claim, contact, operating "
            "status, or coordinate is correct.",
            "Text matches are literal triage signals and can miss abbreviations, alternate "
            "addresses, maps, tables, PDF evidence, and JavaScript content.",
            "403/429 and network/TLS errors are inconclusive, not proof of a broken public source.",
            "HTTP 404/410 may be bot/WAF behavior; replacement decisions need independent "
            "browser/search corroboration.",
            "Public-host validation limits accidental private-network access; DNS rebinding "
            "is not fully eliminated by the standard HTTP client.",
        ],
        "assets": assets,
        "urls": [
            {
                **{k: v for k, v in results[url].items() if k != "text"},
                "references": urls[url],
            }
            for url in sorted(results)
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("catalog_record_count", "unique_url_count", "classification_counts")
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
