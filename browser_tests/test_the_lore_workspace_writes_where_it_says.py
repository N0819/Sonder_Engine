"""The lore workspace writes where it says it does, moves only what was
dragged, and costs one workspace read per edit.

Audit 2026-11-01 (`frontend_lorebooks_editors`), in a real browser over a
mocked API:

* F6 -- with a story open, a LIBRARY book's entries are edited as the story's
  overlay and "+ Entry" lands in the story's canon, as the file's own header
  promises -- but "Generate entries", the book's own fields, moves, links and
  deletion wrote the shared library book every other story reads. None of
  those has a story-local form on the server, so each now says so and asks.
* F7 -- the sidebar never cleared its drag id, and every drop target fell
  back to it (or to any `text/plain`), so a file dropped on "Drop here to
  move to root" after a cancelled sidebar drag re-rooted that book.
* F24 -- the Parent select offered the book's own descendants, and Save
  wrote the book's fields BEFORE the move the server then refused as a cycle.
* E1 -- every entry edit re-ran `boot()`: the whole bootstrap (every card,
  book and chat) re-downloaded to save one entry that no bootstrap key holds.
* E2 -- every entry card was built in full while folded (310 entries in the
  owner's largest book, ~70 elements each).
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP, _chat_payload

BOOKS = [
    {"id": 10, "name": "Harbour City", "chat_id": None, "parent_id": None,
     "book_type": "location", "summary": "", "sort_order": 0, "inheritance_mode": "inherit"},
    {"id": 11, "name": "Docks", "chat_id": None, "parent_id": 10,
     "book_type": "location", "summary": "", "sort_order": 0, "inheritance_mode": "inherit"},
    {"id": 12, "name": "Warehouse Row", "chat_id": None, "parent_id": 11,
     "book_type": "location", "summary": "", "sort_order": 0, "inheritance_mode": "inherit"},
    {"id": 13, "name": "Inland Roads", "chat_id": None, "parent_id": None,
     "book_type": "general", "summary": "", "sort_order": 1, "inheritance_mode": "inherit"},
]

ENTRIES = [{"id": 100 + i, "lorebook_id": 10, "title": f"Pier {i}", "keys": f"pier {i}",
            "content": f"Stone pier number {i}.", "category": "place", "importance": 0.5}
           for i in range(1, 4)]


def _mount(page: Page, writes: list, seen: list, *, story: bool, move_status: int = 200) -> None:
    bootstrap = {**BOOTSTRAP, "lorebooks": BOOKS, "lorebook_types": ["general", "location"],
                 "lore_categories": ["other", "place"],
                 "chats": [{"id": 1, "name": "First"}] if story else []}

    def handle(route) -> None:
        request = route.request
        path = urlparse(request.url).path
        seen.append(f"{request.method} {path}")
        payload = json.loads(request.post_data) if request.post_data else {}
        status = 200
        if request.method != "GET":
            writes.append((request.method, path, payload))
        if path == "/api/bootstrap":
            body = bootstrap
        elif path == "/api/chats/1":
            body = _chat_payload(1, "First", "settled prose")
        elif path == "/api/chats/1/vitals":
            body = {"enabled": False, "bodies": []}
        elif request.method == "GET" and path.startswith("/api/lorebooks/") and path.endswith("/links"):
            body = {"links": []}
        elif request.method == "GET" and path.startswith("/api/lorebooks/"):
            lid = int(path.rsplit("/", 1)[1])
            book = next(b for b in BOOKS if b["id"] == lid)
            body = {"book": {**book, "library": True, "read_as_story": 1 if story else None},
                    "entries": ENTRIES if lid == 10 else []}
        elif path.endswith("/move"):
            status, body = (move_status, {"detail": "Cannot move lorebook: would create a cycle"}
                            if move_status != 200 else {"ok": True})
        elif path.startswith("/api/lore_entries/"):
            body = {"ok": True, "entry": {**ENTRIES[0], **payload}}
        elif request.method == "GET":
            body = {}
        else:
            body = {"ok": True}
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", handle)


def _open(page: Page, ui_base_url: str, *, story: bool, book: int = 10, **kw):
    writes: list = []
    seen: list = []
    _mount(page, writes, seen, story=story, **kw)
    page.goto(f"{ui_base_url}/static/index.html")
    if story:
        page.get_by_label("Open First").click()
        expect(page.locator("#chatname")).to_have_text("First")
    else:
        expect(page.locator("#send")).to_be_visible()
    page.evaluate(f"() => openLoreWorkspace({book})")
    expect(page.locator("#modal .lore-inspector-tabs")).to_be_visible()
    return writes, seen


def test_generating_into_a_library_book_from_a_story_asks_first(
        page: Page, ui_base_url: str) -> None:
    writes, _ = _open(page, ui_base_url, story=True)
    page.locator("#modal").get_by_role("button", name="✨ Generate entries").click()
    page.locator("#modal textarea").first.fill("the harbour's guilds")
    page.locator("#modal").get_by_role("button", name="Generate entries", exact=True).click()
    overlay = page.locator(".confirm-overlay")
    expect(overlay).to_contain_text("shared library")
    overlay.get_by_role("button", name="Cancel").click()
    assert not [w for w in writes if w[1].endswith("/generate")], writes


def test_saving_a_library_books_fields_from_a_story_asks_first(
        page: Page, ui_base_url: str) -> None:
    writes, _ = _open(page, ui_base_url, story=True)
    page.locator("#modal .lore-inspector-tabs button[data-tab=book]").click()
    page.locator("#modal .lore-meta-grid input").first.fill("Harbour City (story)")
    page.locator("#modal").get_by_role("button", name="Save book").click()
    overlay = page.locator(".confirm-overlay")
    expect(overlay).to_contain_text("shared library")
    overlay.get_by_role("button", name="Cancel").click()
    assert not [w for w in writes if w[0] == "PUT"], writes


def test_without_a_story_the_library_is_edited_as_the_library(
        page: Page, ui_base_url: str) -> None:
    writes, _ = _open(page, ui_base_url, story=False)
    page.locator("#modal .lore-inspector-tabs button[data-tab=book]").click()
    page.locator("#modal .lore-meta-grid input").first.fill("Harbour City")
    page.locator("#modal").get_by_role("button", name="Save book").click()
    expect(page.locator("#toasts")).to_contain_text("Lorebook saved.")
    assert [w for w in writes if w[:2] == ("PUT", "/api/lorebooks/10")]


def test_a_foreign_drop_after_a_cancelled_sidebar_drag_moves_nothing(
        page: Page, ui_base_url: str) -> None:
    writes, _ = _open(page, ui_base_url, story=False)
    page.evaluate("() => closeAllModals()")
    page.locator("#tabs button[data-tab=lore]").click()
    expect(page.locator(".lore-side-row").first).to_be_visible()
    # A sidebar drag that ends nowhere: dragstart, then dragend.
    page.evaluate("""() => {
      const row = document.querySelector('.lore-side-row');
      const dt = new DataTransfer();
      row.dispatchEvent(new DragEvent('dragstart', { dataTransfer: dt, bubbles: true }));
      row.dispatchEvent(new DragEvent('dragend', { dataTransfer: dt, bubbles: true }));
    }""")
    page.evaluate("() => openLoreWorkspace(13)")
    root = page.locator("#modal .filedrop", has_text="Drop here to move to root")
    expect(root).to_be_visible()
    # Then a FILE dropped on the root zone, and a plain-text "12".
    page.evaluate("""() => {
      const zone = [...document.querySelectorAll('#modal .filedrop')]
        .find(z => z.textContent.includes('Drop here to move to root'));
      const file = new DataTransfer();
      file.items.add(new File(['x'], 'map.png', { type: 'image/png' }));
      zone.dispatchEvent(new DragEvent('dragover', { dataTransfer: file, bubbles: true, cancelable: true }));
      zone.dispatchEvent(new DragEvent('drop', { dataTransfer: file, bubbles: true, cancelable: true }));
      const text = new DataTransfer();
      text.setData('text/plain', '12');
      zone.dispatchEvent(new DragEvent('drop', { dataTransfer: text, bubbles: true, cancelable: true }));
    }""")
    page.wait_for_timeout(400)
    assert not [w for w in writes if w[1].endswith("/move")], writes


def test_a_book_cannot_be_given_its_own_descendant_as_parent(
        page: Page, ui_base_url: str) -> None:
    _open(page, ui_base_url, story=False)
    page.locator("#modal .lore-inspector-tabs button[data-tab=book]").click()
    parent = page.locator("#modal .lore-meta-grid select").nth(1)
    values = parent.locator("option").evaluate_all("os => os.map(o => o.value)")
    assert "11" not in values and "12" not in values, values
    assert "13" in values, values


def test_a_refused_move_leaves_the_books_fields_unwritten(
        page: Page, ui_base_url: str) -> None:
    writes, _ = _open(page, ui_base_url, story=False, move_status=400)
    page.locator("#modal .lore-inspector-tabs button[data-tab=book]").click()
    page.locator("#modal .lore-meta-grid input").first.fill("Harbour City, renamed")
    page.locator("#modal .lore-meta-grid select").nth(1).select_option("13")
    page.locator("#modal").get_by_role("button", name="Save book").click()
    expect(page.locator("#toasts")).to_contain_text("would create a cycle")
    assert [w for w in writes if w[1].endswith("/move")], writes
    assert not [w for w in writes if w[0] == "PUT"], writes


def test_saving_an_entry_does_not_reload_the_bootstrap(
        page: Page, ui_base_url: str) -> None:
    writes, seen = _open(page, ui_base_url, story=False)
    boots = seen.count("GET /api/bootstrap")
    card = page.locator("#modal .lore-entry-card").first
    card.locator(":scope > summary").click()
    card.get_by_role("button", name="Save entry").click()
    expect(page.locator("#toasts")).to_contain_text("Entry saved.")
    page.wait_for_timeout(300)
    assert seen.count("GET /api/bootstrap") == boots
    assert [w for w in writes if w[:2] == ("PUT", "/api/lore_entries/101")]


def test_a_folded_entry_card_is_built_when_it_is_opened(
        page: Page, ui_base_url: str) -> None:
    _open(page, ui_base_url, story=False)
    cards = page.locator("#modal .lore-entry-card")
    expect(cards).to_have_count(3)
    assert page.locator("#modal .lore-entry-card textarea").count() == 0
    cards.nth(1).locator(":scope > summary").click()
    expect(cards.nth(1).locator("textarea.lore-entry-content")).to_have_value("Stone pier number 2.")
    assert page.locator("#modal .lore-entry-card textarea.lore-entry-content").count() == 1
