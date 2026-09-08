"""Which books a lorebook tree draws, and where each tree starts.

A77 (review 2026-09-07). Three surfaces draw the same tree -- the library
sidebar, the workspace tree and the Cast > Lorebooks tab -- and the third had
neither half of the rule the first two had.

It read `GET /api/chats/{cid}` for its books, which answers the RETRIEVAL
question ("which books may this story draw lore from") by walking outward from
canon and the attachments through parents, children and links. A book the story
owns that hangs off nothing is unreachable by that walk, which is why the
lorebook workspace moved to the ownership route and said so in its comment.

And it drew only `byParent.get("root")`, so an attached book whose parent is not
attached hung off nothing that was rendered. The loop that was supposed to catch
that had an empty body: it found every such book and did nothing with it, so the
book was never appended anywhere and its open, silence and detach controls could
not be reached at all -- while the attach dropdown went on offering exactly
those books, since it lists every library book not already attached.

Source-pinned, like its siblings: there is no bundler and the browser tier is
optional. A browser tier would drive it by attaching a library book whose parent
is not attached, opening Cast > Lorebooks, and asserting the book has a row with
a working detach button.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOREBOOKS = (ROOT / "static/js/lorebooks.js").read_text(encoding="utf-8")
SETTINGS = (ROOT / "static/js/settings.js").read_text(encoding="utf-8")
INDEX = (ROOT / "static/index.html").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def test_the_missing_parent_rule_is_written_once():
    """A book is a root when it names no parent AND when the parent it names is
    not in the set being drawn. That second half was spelled out twice in
    lorebooks.js and missing from the third caller, which is the shape a rule
    takes just before it is dropped somewhere."""
    assert LOREBOOKS.count("function loreRootBooks(books)") == 1
    rule = _between(LOREBOOKS, "function loreRootBooks(books)",
                    "function loreBooksByParent(books)")
    assert "book.parent_id == null || !byId.has(book.parent_id)" in rule

    # Nobody re-derives it: the only place the filter is spelled is the helper.
    inline = re.findall(r"parent_id == null\s*\n?\s*\|\|\s*!byId\.has", LOREBOOKS)
    assert len(inline) == 1, "a caller still re-derives the root rule"
    assert inline[0] in rule

    for caller in (LOREBOOKS, SETTINGS):
        assert "loreRootBooks(" in caller


def test_the_cast_lorebooks_tab_asks_for_ownership_not_reachability():
    block = _between(SETTINGS, "function renderLorebooksTab(d, b, chatId)",
                     "function renderMultiplayerTab(")
    assert 'api("GET", `/api/chats/${chatId}/lorebooks`)' in block
    assert 'api("GET", "/api/chats/" + chatId)' not in block
    # Drawn from the shared rule, and the empty-bodied orphan loop is gone.
    assert "for (const root of loreRootBooks(books))" in block
    assert "Skip — already rendered as descendant" not in block
    # Normalized like every other reader of a book payload, so `parent_id` is a
    # number on both sides of the `byId` lookup.
    assert "map(normalizeLoreBook)" in block


def test_a_book_the_story_owns_is_shown_with_what_it_actually_is():
    """The ownership route carries `attached` and `retrievable`, and the tab
    now shows books where both can be false. A silence button on a book with no
    `chat_lorebooks` row is a 404 the reader cannot act on, and a book outside
    the retrieval walk looks identical to one inside it unless it is marked."""
    block = _between(SETTINGS, "function renderLorebooksTab(d, b, chatId)",
                     "function renderMultiplayerTab(")
    assert "!isCanon && lb.attached === true" in block
    assert 'lb.retrievable === false' in block
    assert '"not retrieved"' in block

    # AND WHAT THE REMOVAL CONTROL ACTUALLY DOES. One route, two acts:
    # `DELETE /api/chats/{cid}/lorebooks/{lid}` drops the attachment row and
    # then, when `lb.chat_id` is this story, calls `_delete_book` -- the book
    # and every entry in it. Labelling that "Detach from story" was survivable
    # while the panel only drew books the retrieval walk reached; it is not,
    # now that the story's own unattached books are drawn for the first time,
    # because for those the detach half does nothing at all and only the
    # delete happens.
    assert "Number(lb.chat_id) === Number(chatId)" in block
    delete_arm = _between(block, "Number(lb.chat_id) === Number(chatId)",
                          "Detach from story")
    assert "await confirmModal(" in delete_arm
    assert "danger: true" in delete_arm
    # Says what is destroyed, and how much of it.
    assert "is not a detach" in delete_arm
    assert "every entry in it" in delete_arm
    assert "${lb.entry_count || 0}" in delete_arm
    assert '"Delete this book and its entries"' in delete_arm
    assert delete_arm.index("await confirmModal(") < delete_arm.index('api("DELETE"')
    # The reversible act keeps its own plain label and needs no confirm.
    assert "Detach from story (the library keeps the book)" in block


def test_the_lorebook_route_still_deletes_a_book_the_story_owns():
    """The label above is only right while the route behaves this way, and the
    route is where the two acts actually part. Pinned here so a change to
    `detach_book` that made it a pure detach is caught as a UI lie rather than
    quietly leaving the panel threatening a deletion that no longer happens.
    """
    server = (ROOT / "web/app.py").read_text(encoding="utf-8")
    route = _between(server, '@app.delete("/api/chats/{cid}/lorebooks/{lid}")',
                     '@app.post("/api/chats/{cid}/lorebook")')
    assert "DELETE FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?" in route
    assert 'if lb and lb["chat_id"] == cid:' in route
    assert "_delete_book(lid)" in route


def test_settings_can_call_the_shared_rule_at_all():
    """These files are browser globals in a hand-maintained load order, so a
    helper used across two of them is only real if the definition loads first.
    """
    names = re.findall(r'src="/static/js/([\w.-]+\.js)(?:\?[^"]*)?"', INDEX)
    assert names.index("lorebooks.js") < names.index("settings.js")
