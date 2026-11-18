#!/usr/bin/env python3
"""Screen published institution homepages for explicit closure/parking signals."""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_peer_supporting_catalog import (  # noqa: E402
    CACHE,
    ensure_nces_sources,
    existing_records,
    institution_records,
)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.text = []
        self.in_title = False
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        if tag in {"script", "style"}:
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)

    def handle_data(self, value):
        if self.in_title:
            self.title.append(value)
        if not self.suppressed:
            self.text.append(value)


def check(url):
    try:
        response = requests.get(url, timeout=(8, 18), headers={
            "User-Agent": "COSOLVE-public-institution-source-check/1.0",
        })
        parser = PageText()
        parser.feed(response.text[:500000])
        text = " ".join(parser.text).casefold()
        title = " ".join(parser.title).strip()[:240]
        final_host = urlsplit(response.url).hostname or ""
        closed = re.search(
            r"(has permanently closed|permanently closed its|ceased (all )?operations|"
            r"institution is closed|college has closed|university has closed|"
            r"college closed permanently|university closed permanently)", text
        )
        parked = any(name in final_host for name in (
            "sedoparking", "hugedomains", "dan.com", "afternic", "buydomains",
        )) or "this domain is for sale" in text
        hold = response.status_code in {404, 410} or bool(closed) or parked
        reason = ("Explicit closure notice requires editorial review" if closed else
                  "Published homepage redirects to a parked/for-sale domain" if parked else
                  f"Published homepage returned HTTP {response.status_code}" if hold else "")
        return {"url": url, "final_url": response.url, "http_status": response.status_code,
                "title": title, "hold": hold, "reason": reason,
                "result": "reachable" if response.status_code == 200 else "inconclusive",
                "checked": "2026-11-18"}
    except requests.RequestException as error:
        return {"url": url, "hold": False, "result": "inconclusive",
                "reason": type(error).__name__, "checked": "2026-11-18"}


def main(catalogs=False):
    if not catalogs:
        ensure_nces_sources()
    records = existing_records() if catalogs else institution_records(existing_records(), [])
    urls = sorted({r["website_url"] for r in records if r.get("website_url")})
    path = CACHE / ("peer_website_checks.json" if catalogs else "institution_website_checks.json")
    checks = json.loads(path.read_text()) if path.exists() else {}
    institution_checks = CACHE / "institution_website_checks.json"
    if catalogs and institution_checks.exists():
        checks = {**json.loads(institution_checks.read_text()), **checks}
    pending = [url for url in urls if url not in checks]
    print(f"Checking {len(pending)} additional published website URLs.", flush=True)
    with ThreadPoolExecutor(max_workers=8) as executor:
        tasks = {executor.submit(check, url): url for url in pending}
        for index, future in enumerate(as_completed(tasks), 1):
            url = tasks[future]
            checks[url] = future.result()
            if index % 50 == 0:
                path.write_text(json.dumps(checks, indent=2) + "\n")
                print(f"Checked {index} / {len(pending)} URLs.", flush=True)
    path.write_text(json.dumps(checks, indent=2) + "\n")
    print(f"Saved {len(checks)} observations; {sum(bool(r['hold']) for r in checks.values())} "
          "flagged for manual review.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer-catalogs", action="store_true")
    main(catalogs=parser.parse_args().peer_catalogs)
