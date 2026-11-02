"""A run ends the way its stream says it ended -- and a stream that breaks is not an ending.

Two findings of the frontend audit of 2026-11-01 (frontend_core), both in
`runStream` (chat.js):

* F4 -- a pipeline that fails or is stopped inside the stream arrives as an
  in-stream `error` (`web.app._drain_on_own_thread`) or `aborted`
  (`agents.runtime.run_pipeline`) on an HTTP 200, and `runStream` read every
  stream that closed as a success: the "ready" chime sounded, the newest
  (older) turn was marked just-generated so its backdrop was commissioned at
  once, and the typed line was never given back -- although the server had
  DELETED the turn holding it when no stage had saved (`_discard_stepless_turn`).
* F6 -- a stream that DROPS (sleep, a Wi-Fi blip, a proxy timeout, a reload)
  leaves the run going on the server, and the page gave up on it: Stop hidden,
  Send re-enabled, the line put back -- so Send got a 409, or played the line
  twice once the turn had finished. `GET /api/turns/{tid}/status` exists for
  exactly this; the page now follows the run there until it ends, and does the
  same for a turn it finds running when it opens a story.

`runStream` and its helpers are sliced out of chat.js and run under node with
their collaborators stubbed. Timers run at once, so the follow loop's waits
cost nothing here.
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

LINE = "I open the door."

_HARNESS = r"""
const fs = require("fs");
const [, , subject, scopeFile, scenarioJson] = process.argv;
const scenario = JSON.parse(scenarioJson);
const record = { toasts: [], chimes: 0, refreshes: [], statusReads: 0,
                 busyWhileFollowing: [], stopShownWhileFollowing: [], phases: [] };
function element() {
  const classes = new Set();
  return { value: "", disabled: false, textContent: "", checked: false,
    classList: { add: c => classes.add(c), remove: c => classes.delete(c),
      toggle: (c, on) => { (on === undefined ? !classes.has(c) : on) ? classes.add(c) : classes.delete(c); },
      contains: c => classes.has(c) } };
}
const elements = {};
const $ = selector => (elements[selector] ||= element());
$("#stop").classList.add("hidden");      // as the page starts
const window = { location: { href: "" } };
const S = { busy: false, chatId: 7, currentFrameId: null,
  chat: { chat: { id: 7 }, turns: [{ id: 70, idx: 0, player_input: "", prose: "Dawn.", frame_id: null }] } };
let _activeRun = null, _freshRunPending = false, _freshTurnId = null;
const t = (text, vars = {}) => Object.entries(vars).reduce(
  (out, [k, v]) => out.split("{" + k + "}").join(String(v)), String(text));
const toast = (message, type) => record.toasts.push([String(message), type]);
const liveReset = () => {};
const turnStatusStart = () => {};
const turnStatusStop = () => {};
const handleEvt = () => {};
const chimeArm = () => {};
const chimePlay = () => { record.chimes += 1; };
const resizeComposer = () => {};
const setTimeout = fn => { Promise.resolve().then(fn); return 0; };
const newTurn = { id: 71, idx: 1, player_input: scenario.line, prose: "", frame_id: null };
async function openChat(id, opts = {}) {
  record.refreshes.push(opts.sinceTurnId ?? null);
  if (scenario.turnSaved) {
    S.chat = { chat: { id: 7 }, turns: S.chat.turns.filter(x => x.id !== 71).concat([newTurn]) };
  }
  return true;
}
const statuses = scenario.statuses || [];
async function apiOrNull(url) {
  if (url.includes("/status")) {
    record.statusReads += 1;
    record.busyWhileFollowing.push(S.busy);
    record.stopShownWhileFollowing.push(!$("#stop").classList.contains("hidden"));
    record.phases.push($("#turnstatus-phase").textContent);
    const answer = statuses.length > 1 ? statuses.shift() : statuses[0];
    if (answer === "offline") throw new Error("Could not reach the server.");
    return answer;   // null = 404
  }
  // the story read that finds the run's turn
  return scenario.storyGone ? null
    : { turns: scenario.turnSaved || scenario.statuses ? [newTurn] : [] };
}
async function streamPost(url, body, onEvt, onOpen) {
  if (scenario.refused) throw new Error("A pipeline is already running for this.");
  if (onOpen) onOpen();
  onEvt({ type: "step_start", key: "director_interpret", label: "Director · interpret" });
  for (const ev of scenario.events || []) onEvt(ev);
  if (scenario.drops) throw new TypeError("network error");
}
const api = async () => ({});
eval(fs.readFileSync(scopeFile, "utf8") + "\n" + fs.readFileSync(subject, "utf8"));
(async () => {
  let ok;
  if (scenario.reload) {
    S.chat.turns.push({ ...newTurn, player_input: "" });
    await followRunningTurn();
  } else {
    $("#input").value = "";
    ok = await runStream("/api/chats/7/turns", { input: scenario.line },
                         { chatId: 7, frameId: null, playerInput: scenario.line });
  }
  record.ok = ok;
  record.input = $("#input").value;
  record.fresh = _freshRunPending;
  record.busy = S.busy;
  record.stopHidden = $("#stop").classList.contains("hidden");
  process.stdout.write(JSON.stringify(record));
})();
"""


def _run(**scenario) -> dict:
    scenario.setdefault("line", LINE)
    start = CHAT.index("async function abortActiveRun()")
    block = CHAT[start:CHAT.index("// Rerolling/resuming/", start)]
    scope_start = CHAT.index("function inCurrentScope(scope)")
    scope = CHAT[scope_start:CHAT.index("\n}\n", scope_start) + 3]
    with tempfile.TemporaryDirectory(prefix="run-stream-") as tmp:
        harness, subject, scope_file = (Path(tmp) / name for name in
                                        ("harness.js", "subject.js", "scope.js"))
        harness.write_text(_HARNESS, encoding="utf-8")
        subject.write_text(block, encoding="utf-8")
        scope_file.write_text(scope, encoding="utf-8")
        run = subprocess.run(["node", str(harness), str(subject), str(scope_file),
                              json.dumps(scenario)],
                             capture_output=True, text=True, check=True, timeout=60)
    return json.loads(run.stdout)


def test_done_is_the_one_success():
    got = _run(events=[{"type": "done", "turn_id": 71}], turnSaved=True)
    assert got["ok"] is True
    assert got["chimes"] == 1
    assert got["fresh"] is True
    assert got["refreshes"] == [70]          # an append: the slice
    assert got["input"] == ""


@pytest.mark.parametrize("ending", [
    {"type": "error", "error": "Out of credit", "fatal": True},
    {"type": "aborted", "turn_id": 71},
])
def test_a_run_that_saved_nothing_gives_the_line_back(ending):
    got = _run(events=[ending])
    assert got["ok"] is False
    assert got["chimes"] == 0                 # "ready" never means "gone wrong"
    assert got["fresh"] is False              # nothing new to commission for
    assert got["refreshes"] == [None]         # a failed run refreshes whole
    assert got["input"] == LINE               # the server deleted the turn


def test_a_partial_turn_keeps_the_line_it_holds():
    """A run that failed after a stage saved left a resumable turn carrying the
    line; putting it back in the box as well would play it twice."""
    got = _run(events=[{"type": "error", "error": "boom", "fatal": True}], turnSaved=True)
    assert got["ok"] is False and got["chimes"] == 0
    assert got["input"] == ""


def test_a_refused_run_gives_the_line_back():
    got = _run(refused=True)
    assert got["ok"] is False
    assert got["input"] == LINE
    assert any("already running" in message for message, _ in got["toasts"])


def test_a_dropped_stream_is_followed_to_its_end():
    got = _run(drops=True, turnSaved=True, statuses=[
        {"running": True, "committed": False},
        "offline",
        {"running": True, "committed": False},
        {"running": False, "committed": True},
    ])
    assert got["ok"] is True
    assert got["chimes"] == 1
    assert got["statusReads"] == 4
    # Stop and the busy page stay with the run while it is followed.
    assert all(got["busyWhileFollowing"]) and all(got["stopShownWhileFollowing"])
    assert all("following" in phase for phase in got["phases"])
    assert got["refreshes"] == [70]
    assert got["busy"] is False and got["stopHidden"] is True
    assert got["input"] == ""


def test_a_stream_that_closes_without_an_ending_is_followed_too():
    got = _run(turnSaved=True, statuses=[{"running": False, "committed": True}])
    assert got["ok"] is True and got["statusReads"] == 1


def test_a_followed_run_the_server_discarded_gives_the_line_back():
    got = _run(drops=True, statuses=[None])          # 404: no stage saved
    assert got["ok"] is False and got["chimes"] == 0
    assert got["input"] == LINE
    assert got["toasts"], "the reader is told the beat did not finish"


def test_a_followed_run_that_stopped_partway_keeps_its_line():
    got = _run(drops=True, turnSaved=True, statuses=[{"running": False, "committed": False}])
    assert got["ok"] is False and got["chimes"] == 0
    assert got["input"] == ""


def test_a_turn_found_running_on_open_is_followed():
    got = _run(reload=True, line="", statuses=[
        {"running": True, "committed": False},
        {"running": False, "committed": True},
    ])
    assert got["statusReads"] == 2
    # The first read is the probe that finds it running; from then on the
    # page holds the run as its own.
    assert got["busyWhileFollowing"] == [False, True]
    assert got["stopShownWhileFollowing"] == [False, True]
    assert got["chimes"] == 1
    assert got["refreshes"] == [None]
    assert got["busy"] is False


def test_a_finished_turn_is_not_probed_on_open():
    """The probe is for a beat with no prose yet; anything else costs nothing."""
    got = _run(reload=True, line="", statuses=[{"running": False, "committed": True}])
    assert got["statusReads"] == 1          # the newest beat had no prose: asked once
    assert got["chimes"] == 0               # and it was not running: nothing followed
