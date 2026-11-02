"""A guest reads their own slice of the story, never what the host's stages are called.

`guest_state` sends each turn's earliest stale step as `stale_from` -- its key
and its label -- and a character's step is labelled "Character · <true name>"
(`agents/runtime.py` STEP_LABELS, filled at plan time). `static/guest.html`
printed that label in its stale note, so a guest whose persona knew a woman
only as "the hooded woman" read "steps from “Character · Mirelle Sulmirath”
onward were not recomputed" (frontend audit 2026-11-01, frontend_core F1; the
server half is web_app F4 / web_routes_extensions F8). The page names no stage
at all now: the note says what happened to the text the guest is reading,
which is the only part of it a guest can act on.

Driven in `browser_tests/test_a_guest_reads_only_their_own_beats.py`; this is
the default-tier half, so the rule holds where the browser tier does not run.
"""

from pathlib import Path

GUEST = (Path(__file__).resolve().parents[1] / "static" / "guest.html").read_text(
    encoding="utf-8")
SCRIPT = GUEST[GUEST.index("<script>"):]


def test_the_guest_page_never_prints_a_step_label():
    assert "stale_from.label" not in SCRIPT
    assert "stale_from.key" not in SCRIPT


def test_the_stale_note_still_says_what_happened():
    """The dim is not a message on its own (`test_stale_surface.py`): the note
    stays, it only stops naming the stage."""
    render = SCRIPT[SCRIPT.index("function render("):]
    render = render[:render.index("\n}\n")]
    assert "t.stale_from" in render
    assert "Superseded" in render and "Partly out of date" in render


def test_a_guests_turn_is_story_text_to_the_translator():
    """Everything under a turn was written by a model or by the guest, so the
    catalog must never touch it: i18n.js's observer walks the whole page, and
    a guest who typed "Continue" read 続ける as their own line (F8)."""
    helper = SCRIPT[SCRIPT.index("function storyText("):]
    helper = helper[:helper.index("\n}\n")]
    assert 'setAttribute("translate", "no")' in helper
    render = SCRIPT[SCRIPT.index("function render("):]
    render = render[:render.index("\n}\n")]
    assert 'storyText("pin", t.player_input)' in render
    assert 'storyText("prose", t.prose)' in render
