from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOST_PAGES = tuple(sorted((ROOT / "static").glob("*.html")))


class _HeadMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_head = False
        self.locks = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "head":
            self.in_head = True
        if self.in_head and tag == "meta" and dict(attrs).get("name") == "darkreader-lock":
            self.locks += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False


def test_every_static_host_page_locks_its_authored_palette_from_dark_reader():
    assert [path.name for path in HOST_PAGES] == [
        "guest.html",
        "login.html",
        "ui-next-lab.html",
        "ui-next-runtime.html",
        "ui-next.html",
    ]
    for page in HOST_PAGES:
        parser = _HeadMetaParser()
        parser.feed(page.read_text(encoding="utf-8"))
        assert parser.locks == 1, f"{page.name} must contain one static head-level Dark Reader lock"
