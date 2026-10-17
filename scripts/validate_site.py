#!/usr/bin/env python3
"""Fast, dependency-free checks for the static AI Bharatiyaa pages."""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["index.html", "login.html", "account.html", "admin/users.html"]
SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.3/dist/umd/supabase.js"


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.internal_links: list[str] = []
        self.asset_links: list[str] = []
        self.has_title = False
        self.has_viewport = False
        self.has_main = False
        self.script_srcs: list[str] = []
        self.inline_scripts = 0

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
        if tag == "script":
            src = values.get("src")
            if src:
                self.script_srcs.append(src)
                if src.startswith("/"):
                    self.asset_links.append(src)
            else:
                self.inline_scripts += 1


def check_page(page: str) -> list[str]:
    html = (ROOT / page).read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(html)

    problems: list[str] = []
    if not parser.has_title:
        problems.append(f"{page} is missing a title")
    if not parser.has_viewport:
        problems.append(f"{page} is missing the viewport meta tag")
    if not parser.has_main:
        problems.append(f"{page} is missing a main landmark")
    if len(parser.ids) != len(set(parser.ids)):
        problems.append(f"{page} contains duplicate IDs")

    missing_targets = sorted(set(parser.internal_links) - set(parser.ids))
    if missing_targets:
        problems.append(f"{page}: missing fragment targets: {', '.join(missing_targets)}")

    for asset in parser.asset_links:
        if not (ROOT / asset.lstrip("/")).exists():
            problems.append(f"{page}: missing local asset: {asset}")

    # The CSP has no 'unsafe-inline': every script is a file, local or the pinned CDN build.
    if parser.inline_scripts:
        problems.append(f"{page} has an inline <script>; the CSP forbids it")
    for src in parser.script_srcs:
        if not (src.startswith("/") and not src.startswith("//")) and src != SUPABASE_JS:
            problems.append(f"{page}: script {src} is neither local nor the pinned supabase-js")
    return problems


def main() -> int:
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    problems: list[str] = []
    for page in PAGES:
        problems += check_page(page)

    if ":focus-visible" not in css:
        problems.append("styles.css is missing focus-visible styles")
    if "prefers-reduced-motion" not in css:
        problems.append("styles.css is missing reduced-motion support")
    if re.search(r"#[0-9a-fA-F]{3,8}\b", css):
        problems.append("styles.css contains raw hex colors; use shared tokens")

    if problems:
        print("Site validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("Site validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
