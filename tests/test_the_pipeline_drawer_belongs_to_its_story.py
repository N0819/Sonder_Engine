"""The pipeline drawer acts on the story it was opened for, or not at all.

`openPipeline` captured no scope and nothing closed `#drawer` on a story or
frame switch (frontend audit 2026-11-01, frontend_core F5). Open story A's
drawer, switch to story B, press "Run from here": `runStream` stamped the run
with B, so Stop posted B's abort (A's run could not be stopped), the early
narration preview appended A's prose into B's transcript, and the finish
marked B's newest turn just-generated -- the A73 effect the run's own comment
says it prevents. "Export chat" and the map panel read `S.chatId` at click
time and so acted on B too; Consolidate/Rebuild reopened the memory browser in
whatever story was open. Two quick 📖 clicks also stacked two turns' steps in
the drawer (F16): it was cleared before its fetch and appended after it.

Pinned on the source, as the sibling scope guards in
`test_frontend_state_guards.py` are; driven in a browser in
`browser_tests/test_the_pipeline_drawer_belongs_to_its_story.py`.
"""

import re
from pathlib import Path

CHAT = (Path(__file__).resolve().parents[1] / "static" / "js" / "chat.js").read_text(
    encoding="utf-8")


def _between(start: str, end: str) -> str:
    at = CHAT.index(start)
    return CHAT[at:CHAT.index(end, at)]


DRAWER = _between("async function openPipeline(", "// ---- Relationship viewer ----")


def test_every_run_the_drawer_starts_carries_the_drawers_story():
    calls = re.findall(r"runStream\((.*?)\);", DRAWER, re.S)
    assert len(calls) == 3, calls
    for call in calls:
        # The turn being re-run, in the drawer's own story and frame.
        assert "Object.assign({ turnId: tid }, scope)" in call, call


def test_nothing_in_the_drawer_reads_the_story_open_now():
    signature, body = DRAWER.split("\n", 1)
    # Captured once, where the drawer is opened from a turn on screen...
    assert "scope = { chatId: S.chatId, frameId: S.currentFrameId }" in signature
    # ...and never read again.
    assert "S.chatId" not in body
    assert "S.currentFrameId" not in body
    panel = _between("function pipelineMapPanel(", "// ---- Pipeline drawer ----")
    assert "S.chatId" not in panel
    assert "scope.chatId" in panel


def test_only_the_newest_open_draws_and_only_into_its_story():
    fetched = DRAWER.index("await api(")
    guard = DRAWER.index("if (seq !== _pipelineSeq || !inCurrentScope(scope)) return;")
    assert fetched < guard
    # Cleared after the guard, not before the fetch: two quick opens no
    # longer stack two turns' steps.
    assert guard < DRAWER.index('D.innerHTML = "";', guard)


def test_a_story_or_frame_switch_closes_the_drawer():
    switching = _between("if (switching) {", "const shownChatId")
    assert "closePipeline();" in switching
    frame = _between("function switchFrame(frameId)", "\n}\n")
    assert "closePipeline();" in frame


def test_the_memory_jobs_reopen_only_in_the_story_they_ran_in():
    for name in ("function backfillMemoryEras()", "function consolidateMemories()"):
        body = _between(name, "\n}\n")
        assert "const chatId = S.chatId;" in body, name
        assert "S.chatId === chatId" in body, name
