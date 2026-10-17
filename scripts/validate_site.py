#!/usr/bin/env python3
"""Fast, dependency-free checks for the static AI Bharatiyaa homepage."""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.internal_links: list[str] = []
        self.asset_links: list[str] = []
        self.has_title = False
        self.has_viewport = False
        self.has_main = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self.has_title = True
        if tag == "meta" and values.get("name") == "viewport":
            self.has_viewport = True
        if tag == "main":
            self.has_main = True
        if values.get("id"):
            self.ids.append(values["id"] or "")
        href = values.get("href")
        if href and href.startswith("#"):
            self.internal_links.append(href[1:])
        if tag == "link" and href and href.startswith("/"):
            self.asset_links.append(href)


def main() -> int:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(html)

    problems: list[str] = []
    if not parser.has_title:
        problems.append("index.html is missing a title")
    if not parser.has_viewport:
        problems.append("index.html is missing the viewport meta tag")
    if not parser.has_main:
        problems.append("index.html is missing a main landmark")
    if len(parser.ids) != len(set(parser.ids)):
        problems.append("index.html contains duplicate IDs")

    missing_targets = sorted(set(parser.internal_links) - set(parser.ids))
    if missing_targets:
        problems.append(f"missing fragment targets: {', '.join(missing_targets)}")

    for asset in parser.asset_links:
        if not (ROOT / asset.lstrip("/")).exists():
            problems.append(f"missing local asset: {asset}")

    if ":focus-visible" not in css:
        problems.append("styles.css is missing focus-visible styles")
    if "prefers-reduced-motion" not in css:
        problems.append("styles.css is missing reduced-motion support")
    if re.search(r"#[0-9a-fA-F]{3,8}\b", css):
        problems.append("styles.css contains raw hex colors; use shared tokens")

    if problems:
        print("Homepage validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("Homepage validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

