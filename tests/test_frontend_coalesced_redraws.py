"""A redraw or re-read asked for by a burst runs once per burst.

C22 (review 2026-09-07). Three panels did the same expensive thing once per
EVENT where once per burst draws the same picture:

* the Writers' Room re-rendered its whole thread on every streamed token --
  60 messages back through the localizer, whose Japanese catalog compiles to
  393 template regexes. Measured on `language_packs/ja/ui.json`: 3.9 ms of
  regex matching per thread render, so a 900-delta answer spent 3.5 s of it,
  and one render per frame spends 118 ms for the same final thread;
* the World Browser re-read the room index, the positions and the selected
  room's grid after every field commit, and holding an arrow key to nudge a
  mark commits on each key repeat. Measured on the owner's 307-body town
  (chat 114): index 52 ms, positions 10 ms, grid 26 ms -- five nudges cost 15
  requests where a trailing pass costs 3;
* `boot()` re-downloaded the whole bootstrap on all 61 of its call sites.

These are source pins, in the shape `tests/test_frontend_one_stream_reader.py`
uses: this repo has no JavaScript test runner, and the alternative to pinning
the mechanism is not pinning it. What each pin protects is the FLUSH -- the
path that guarantees the last state is drawn -- because a coalescer that drops
the final redraw is the way this class of change goes wrong.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
ROOM = (ROOT / "static/js/writers_room.js").read_text(encoding="utf-8")
WORLD = (ROOT / "static/js/world_browser.js").read_text(encoding="utf-8")


def _slice(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


# ---- boot(): the install half is fetched once per version -------------------

def test_boot_tells_the_server_which_half_it_already_holds():
    body = _slice(APP, "async function boot()", "$$(\"#tabs button\")")
    assert "known_install" in body
    assert "install_unchanged" in body
    assert "bootInstall" in body


def test_boot_keeps_no_second_copy_of_which_keys_the_half_holds():
    """The server names them (`install_keys`). A list retyped here is the B24
    drift again: a key added server-side would silently stop being cached."""
    body = _slice(APP, "async function boot()", "$$(\"#tabs button\")")
    assert "fresh.install_keys" in body
    assert "default_prompts" not in body
    assert "ui_messages" in body      # read, but never enumerated as a key list


# ---- the Writers' Room: one render per frame -------------------------------

def test_the_room_stream_schedules_a_render_rather_than_running_one():
    body = _slice(ROOM, "function roomEvent(event)", "async function roomRevoke")
    assert "roomRenderSoon(true);" in body
    assert "roomRender(" not in body


def test_the_scheduler_coalesces_and_the_direct_call_flushes():
    scheduler = _slice(ROOM, "function roomRenderSoon", "function roomRender(")
    # One frame at a time: a second call while one is pending does not book
    # another.
    assert "if (roomRenderFrame) return;" in scheduler
    assert "requestAnimationFrame(" in scheduler

    render = _slice(ROOM, "function roomRender(keepScroll = false)",
                    "function roomRenderStatus")
    # THE FLUSH. Every direct caller -- a click, and the `finally` that ends a
    # stream -- draws now and cancels the frame that would redraw after it.
    assert "cancelAnimationFrame(roomRenderFrame)" in render


def test_the_stream_still_ends_in_a_direct_render():
    """A coalesced render is only safe because something un-coalesced runs
    last: `roomSend`'s finally, whatever the stream did."""
    send = _slice(ROOM, "async function roomSend", "// ---- The stream ----")
    assert "finally {" in send
    assert "roomRender();" in send


# ---- the World Browser: one re-read pass per burst of writes ---------------

def test_a_write_re_reads_through_the_coalescer():
    ctx = _slice(WORLD, "      replaceCard: async fresh =>", "      currentSlice:")
    assert "await replaceReads();" in ctx
    assert "refresh: () => refreshReads()," in ctx
    # The reads themselves live in the coalesced passes, nowhere else.
    assert "refreshIndex()" not in ctx


def test_the_coalescer_runs_one_more_pass_for_what_landed_during_the_last():
    """Dropping the trailing pass is how this goes wrong: the last write's
    view would never be read back."""
    body = _slice(WORLD, "function wbCoalesced(run)", "async function wbWrite")
    assert "again = true;" in body
    assert "} while (again);" in body
    # Callers still await the settled view -- `wbWrite`'s error path and Undo
    # both sequence on it.
    assert "return running;" in body
