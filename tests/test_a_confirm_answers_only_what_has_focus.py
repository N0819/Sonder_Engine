"""The confirm/prompt overlay answers the control that has focus.

`_confirmOverlay` confirmed on any Enter, from a document listener that runs
before a focused button's own activation -- so Enter on Cancel confirmed the
delete -- and kept no focus in the box, so Enter on a sidebar row behind it
confirmed the dialog AND opened that story (frontend audit 2026-11-01,
frontend_core F3). Driven in a browser in
`browser_tests/test_a_confirm_answers_only_what_has_focus.py`; this pins the
three parts of the rule where the browser tier does not run.
"""

from pathlib import Path

COMPONENTS = (Path(__file__).resolve().parents[1] / "static" / "js" / "components.js"
              ).read_text(encoding="utf-8")
OVERLAY = COMPONENTS[COMPONENTS.index("function _confirmOverlay("):
                     COMPONENTS.index("function confirmModal(")]


def test_enter_is_answered_only_inside_the_box_and_never_for_a_button():
    enter = OVERLAY[OVERLAY.index('if (e.key !== "Enter") return;'):]
    assert enter.index("if (!inside)") < enter.index("onKeydown?.confirm()")
    assert "target instanceof HTMLButtonElement" in enter
    assert enter.index("target instanceof HTMLButtonElement") < enter.index("onKeydown?.confirm()")


def test_focus_is_kept_in_the_box():
    assert 'if (e.key === "Tab")' in OVERLAY
    assert "first.focus()" in OVERLAY and "last.focus()" in OVERLAY


def test_the_listener_runs_before_anything_behind_the_overlay():
    assert 'document.addEventListener("keydown", keyHandler, true);' in OVERLAY
    assert 'document.removeEventListener("keydown", keyHandler, true);' in OVERLAY
