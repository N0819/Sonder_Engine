"""Frontend code that described behaviour nothing performed is gone.

Three leftovers the frontend audit of 2026-11-01 found (frontend_core F12-F14),
each with a comment promising something the page did not do:

* F12 -- `FRIENDLY_SUBAGENTS` (chat.js) said "the progress line names them
  instead of leaving the stage looking stuck". Nothing read it, and no event
  in the turn stream names a sub-agent (`agents/runtime.py` emits step_start,
  token, step, done and aborted).
* F13 -- `friendlyPhase` matched the server's English label for "Scene life"
  to "keep that name rather than be flattened back to a generic one", and
  returned exactly the phrase the table already returns for its key,
  `background_react` -- while coupling the page to the server's English.
* F14 -- `renderLegacyLoreSidebar` (app.js) ran only when lorebooks.js had
  failed to load, and then called lorebooks.js itself and threw; its Cancel
  created a lorebook named "New lorebook". index.html's rule is that a core
  script is not guarded.
"""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "static" / "js"
CHAT = (JS / "chat.js").read_text(encoding="utf-8")
APP = (JS / "app.js").read_text(encoding="utf-8")


def test_no_table_promises_a_progress_line_nothing_draws():
    assert "FRIENDLY_SUBAGENTS" not in CHAT


def test_the_phase_comes_from_the_step_key_not_the_servers_english():
    body = CHAT[CHAT.index("function friendlyPhase("):]
    body = body[:body.index("\n}\n")]
    assert "Scene life" not in body


def test_the_lore_tab_has_one_renderer():
    assert "renderLegacyLoreSidebar" not in APP
    side = APP[APP.index("function renderSide()"):]
    side = side[:side.index("\n}\n")]
    assert "renderLoreLibrarySidebar(list, actions);" in side
    assert 'typeof renderLoreLibrarySidebar' not in side
