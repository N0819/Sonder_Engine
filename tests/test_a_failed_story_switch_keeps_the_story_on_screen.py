"""A story that fails to open leaves the page on the story it was showing.

`openChat` set `S.chatId` to the story being opened BEFORE fetching it, and
nothing put it back when the fetch failed (frontend audit 2026-11-01,
frontend_core F2). The transcript, the header and the frame pills were still
the previous story's -- `renderChat` never ran -- while `S.chatId` named the
one that failed. Send posts to `/api/chats/${S.chatId}/turns`, so the next
line the reader typed for the story on screen was played into the other one,
and every toolbar button acted on it too.

`openChat` is sliced out of chat.js and run under node with its collaborators
stubbed; it touches no DOM of its own. Driven in a browser in
`browser_tests/test_a_line_is_played_where_it_was_typed.py`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

CHAT = (Path(__file__).resolve().parents[1] / "static" / "js" / "chat.js").read_text(
    encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

_HARNESS = r"""
const fs = require("fs");
const [, , subject, scenario] = process.argv;
const calls = [];
const window = {
  clearVitalsHud: () => calls.push("clearVitalsHud"),
  refreshVitalsHud: () => calls.push("refreshVitalsHud"),
  erOfferRebuild: () => {},
};
const S = { chatId: 7, currentFrameId: 3,
            chat: { chat: { id: 7, name: "Harbour" }, turns: [], frames: [{ id: 3 }] } };
const closeAllModals = () => calls.push("closeAllModals");
const closePipeline = () => calls.push("closePipeline");
const renderSide = () => calls.push("renderSide");
const renderChat = () => calls.push("renderChat");
const followRunningTurn = () => {};
const api = async (method, url) => {
  calls.push(method + " " + url);
  if (scenario === "fails") throw new Error("HTTP 500");
  return { chat: { id: 9, name: "Tavern" }, turns: [], frames: [] };
};
let _chatLoadSeq = 0;
eval(fs.readFileSync(subject, "utf8"));
(async () => {
  let threw = null, answer;
  try { answer = await openChat(9); } catch (e) { threw = e.message; }
  process.stdout.write(JSON.stringify({ threw, answer, chatId: S.chatId,
    frameId: S.currentFrameId, shown: S.chat.chat.id, calls }));
})();
"""


def _open_story_nine(scenario: str) -> dict:
    start = CHAT.index("async function openChat(id")
    block = CHAT[start:CHAT.index("\n}\n", start) + 3]
    with tempfile.TemporaryDirectory(prefix="open-chat-") as tmp:
        harness = Path(tmp) / "harness.js"
        subject = Path(tmp) / "subject.js"
        harness.write_text(_HARNESS, encoding="utf-8")
        subject.write_text(block, encoding="utf-8")
        run = subprocess.run(["node", str(harness), str(subject), scenario],
                             capture_output=True, text=True, check=True, timeout=60)
    return json.loads(run.stdout)


def test_a_failed_switch_points_the_page_back_at_the_story_it_shows():
    got = _open_story_nine("fails")
    assert got["threw"] == "HTTP 500"        # still reported to the reader
    assert got["shown"] == 7
    assert got["chatId"] == 7
    assert got["frameId"] == 3
    # The outgoing story's condition panel was cleared before the fetch; it
    # belongs on screen again with the story it describes.
    assert got["calls"].index("clearVitalsHud") < got["calls"].index("refreshVitalsHud")
    assert "renderChat" not in got["calls"]


def test_a_switch_that_succeeds_still_moves_the_page():
    got = _open_story_nine("succeeds")
    assert got["threw"] is None and got["answer"] is True
    assert got["chatId"] == 9 and got["shown"] == 9
    assert got["frameId"] is None
    assert "renderChat" in got["calls"]
