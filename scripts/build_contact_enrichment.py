#!/usr/bin/env python3
"""Discover conservative public contact routes from checked-in official asset sources."""

import concurrent.futures
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "virginia_real_assets.json"
OUTPUT = ROOT / "data" / "asset_contact_enrichment.json"
USER_AGENT = "cosolve-uxs-map-contact-research/1.0"
SKIP_HOSTS = {"www.vedp.org", "vedp.org", "www.prnewswire.com", "prnewswire.com"}
SKIP_RECORDS = {"Virginia Space Grant Consortium Drone Academies"}


class ContactPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current_href = ""
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        self.current_href = (dict(attrs).get("href") or "").strip()
        self.current_text = []

    def handle_data(self, data):
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_href:
            self.links.append(
                (self.current_href, " ".join("".join(self.current_text).split()))
            )
            self.current_href = ""
            self.current_text = []


def fetch_page(url):
    if url.lower().split("?", 1)[0].endswith((".pdf", ".doc", ".docx")):
        return url, None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=12) as response:  # noqa: S310
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return url, None
            page = response.read(2_000_000).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return url, None
    parser = ContactPageParser()
    parser.feed(page)
    return url, parser.links


def normalized_http_url(base_url, href):
    url = urllib.parse.urljoin(base_url, href)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))


def same_host(first, second):
    return urllib.parse.urlsplit(first).hostname == urllib.parse.urlsplit(second).hostname


def contact_link_score(url, text):
    path = urllib.parse.urlsplit(url).path.lower().rstrip("/")
    label = re.sub(r"\s+", " ", text.lower()).strip()
    score = 0
    if label in {"contact", "contact us", "contact information", "get in touch"}:
        score += 100
    if re.search(r"/(contact|contact-us|contactus|get-in-touch)(/|$)", path):
        score += 90
    if "phone directory" in label or label == "directory":
        score += 65
    if label in {"staff directory", "our team", "team", "staff"}:
        score += 45
    if any(term in path for term in ("privacy", "media", "press", "accessibility")):
        score -= 80
    return score


def clean_email(href):
    value = urllib.parse.unquote(href.removeprefix("mailto:")).split("?", 1)[0].strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return ""
    lowered = value.lower()
    local, domain = lowered.split("@", 1)
    if domain == "mysite.com" or any(
        term in local
        for term in (
            "noreply",
            "no-reply",
            "webmaster",
            "privacy",
            "newsletter",
            "accommodations",
            "animalcontrol",
        )
    ):
        return ""
    if local in {"pr", "press", "media", "news"}:
        return ""
    if local in {"djones", "hqnews-join", "phec", "rdtf"}:
        return ""
    return value


def clean_phone(href):
    value = urllib.parse.unquote(href.removeprefix("tel:")).split("?", 1)[0].strip()
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) < 10:
        return ""
    if digits[3:10] in {"5550000", "9990000"}:
        return ""
    phone = f"{digits[:3]}-{digits[3:6]}-{digits[6:10]}"
    return f"{phone} ext. {digits[10:]}" if len(digits) > 10 else phone


def published_contacts(links):
    emails = []
    phones = []
    for href, _text in links or []:
        if href.lower().startswith("mailto:"):
            email = clean_email(href)
            if email and email not in emails:
                emails.append(email)
        elif href.lower().startswith("tel:"):
            phone = clean_phone(href)
            if phone and phone not in phones:
                phones.append(phone)
    return (
        phones[0] if len(phones) == 1 else "",
        emails[0] if len(emails) == 1 else "",
    )


def candidate_for(record, pages):
    if record["name"] in SKIP_RECORDS:
        return ""
    starting_urls = [record["contact_url"], record["website_url"]]
    starting_urls.extend(source["url"] for source in record["sources"])
    candidates = []
    for source_url in dict.fromkeys(starting_urls):
        host = urllib.parse.urlsplit(source_url).hostname or ""
        if host in SKIP_HOSTS:
            continue
        if host == "news.vcu.edu":
            continue
        if host == "www.dcjs.virginia.gov" and "First Responder UAS Capability" in record["name"]:
            continue
        if host == "www.louisacounty.gov" and record["name"].startswith("Orange County"):
            continue
        if contact_link_score(source_url, "") >= 90:
            candidates.append((contact_link_score(source_url, ""), source_url))
        for href, text in pages.get(source_url) or []:
            url = normalized_http_url(source_url, href)
            if not url or not same_host(source_url, url):
                continue
            score = contact_link_score(url, text)
            if score > 0:
                candidates.append((score, url))
    if not candidates:
        return ""
    return max(candidates, key=lambda item: (item[0], -len(item[1])))[1]


def main():
    payload = json.loads(CATALOG.read_text())
    records = [
        record
        for record in payload["records"]
        if record["provenance"] in {"curated-public-source", "virginia-military-factbook"}
    ]
    starting_urls = {
        url
        for record in records
        for url in (
            [record["contact_url"], record["website_url"]]
            + [source["url"] for source in record["sources"]]
        )
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        pages = dict(executor.map(fetch_page, sorted(starting_urls)))

    candidates = {record["name"]: candidate_for(record, pages) for record in records}
    candidate_urls = {url for url in candidates.values() if url and url not in pages}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        pages.update(dict(executor.map(fetch_page, sorted(candidate_urls))))

    assets = {}
    for record in records:
        contact_url = candidates[record["name"]]
        if not contact_url:
            continue
        phone, email = published_contacts(pages.get(contact_url))
        path = urllib.parse.urlsplit(contact_url).path.strip("/")
        if not path and not phone and not email:
            continue
        assets[record["name"]] = {
            "contact_url": contact_url,
            "contact_phone": phone,
            "contact_email": email,
            "source_url": contact_url,
        }

    OUTPUT.write_text(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "methodology": (
                    "Conservative discovery of same-host public contact, directory, or staff links "
                    "from the catalog's checked-in official source pages. Phone and email values "
                    "are retained only when published as tel: or mailto: links on the selected "
                    "page."
                ),
                "assets": assets,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"Wrote {len(assets)} source-linked contact enrichments to {OUTPUT}")


if __name__ == "__main__":
    main()
