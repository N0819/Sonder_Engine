"""The room's sound belongs to the story on screen, and Off means silent.

Four findings of the frontend audit of 2026-11-01 (frontend_lorebooks_editors),
all in static/js/ambience.js:

* F8 -- a story switch reset what was WANTED but kept `AMB.turnId` and
  `AMB.signature`, so in an empty story B the 🎲 reroll stayed lit and POSTed
  a reroll of story A's room ("the server remembers the refusal"), and turning
  ambience on, or the click that unlocks autoplay, played A's bed under B.
* F9 -- switching ambience off while a bed was being searched for (the query
  model call alone is ~27 s) did not stop it: the search landed and
  `playAmbience` started the bed under a button reading "off".
* F3 -- a layer's `credit_url` comes from a stored pin, and pins travel in
  story archives; it was rendered as an `href` of any scheme. Only http(s) is
  a source link (the server-side validation is a separate request).
* F21 -- `AMB.primed`, "one element touched by the unlock gesture", was
  created and never played: it unlocked nothing in any engine.

ambience.js is loaded under node with inert stand-ins for the DOM, `Audio`,
`el` and `api`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "static" / "js" / "ambience.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

_HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const [, , subject, scenario] = process.argv;
const out = { audios: 0, posts: [] };
function fakeElement() {
  const classes = new Set();
  return { dataset: {}, style: {}, value: "0.35", disabled: false, title: "", textContent: "",
    classList: { add: c => classes.add(c), remove: c => classes.delete(c),
      toggle: (c, on) => { (on === undefined ? !classes.has(c) : on) ? classes.add(c) : classes.delete(c); },
      contains: c => classes.has(c) },
    addEventListener() {}, setAttribute() {}, removeAttribute() {} };
}
const elements = {};
let resolveSearch = null;
const state = { enabled: true, configured: true, signature: "sig-a", token: "sig-a#1",
                ready: false, room_id: "kitchen", room: "Kitchen", layers: [] };
const ctx = vm.createContext({
  console, setTimeout: fn => 0, clearTimeout() {}, performance, Promise, JSON, Math,
  Number, String, Map, Set, Error, Object, Array,
  $: s => (elements[s] ||= fakeElement()),
  document: { addEventListener() {}, querySelector: () => null },
  window: {}, localStorage: { getItem: () => null, setItem() {} },
  S: { chatId: 1, boot: null },
  Audio: function () { out.audios += 1; this.load = () => {}; this.play = () => Promise.resolve();
    this.pause = () => {}; this.addEventListener = () => {}; this.removeAttribute = () => {}; },
  toast() {}, taggedError: (kind, message) => Object.assign(new Error(message), { kind }),
  closeModal() {}, modal() {},
  el(tag, attrs = {}, ...kids) { return { tag, attrs, kids: kids.flat() }; },
  api: async (method, url, body) => {
    if (method === "GET") return state;
    if (method === "PUT") return { ok: true };
    out.posts.push(url);                       // a search: held until resolved
    return new Promise(resolve => { resolveSearch = resolve; });
  },
});
vm.runInContext(fs.readFileSync(subject, "utf8"), ctx, { filename: "ambience.js" });
const run = code => vm.runInContext(code, ctx);
const tick = () => new Promise(r => setImmediate(r));
(async () => {
  if (scenario === "switch") {
    run("AMB.enabled = true; AMB.configured = true; AMB.chatId = 1;");
    Object.assign(state, { ready: true, layers: [{ index: 0, url: "/a.ogg", title: "Hum" }] });
    await run("ambienceForTurn(10)");                 // story A's turn on screen
    out.before = { turnId: run("AMB.turnId"), reroll: elements["#b-amb-reroll"].disabled };
    const audiosBefore = out.audios;
    run("S.chatId = 2; ambienceResetForRender();");  // story B, no turns at all
    out.after = { turnId: run("AMB.turnId"), signature: run("AMB.signature"),
                  reroll: elements["#b-amb-reroll"].disabled };
    run("rerollAmbience()"); await tick();           // 🎲
    run("toggleAmbience()"); await tick();           // off
    run("toggleAmbience()"); await tick(); await tick();   // and on again
    out.audiosAfterSwitch = out.audios - audiosBefore;
  } else if (scenario === "off") {
    run("AMB.enabled = true; AMB.configured = true; AMB.chatId = 1;");
    const pending = run("ambienceForTurn(10, { commission: true })");
    await new Promise(r => setImmediate(r));
    run("AMB.enabled = false; stopAmbience();");      // the reader switches it off
    resolveSearch({ ...state, ready: true, status: "ready",
                    layers: [{ index: 0, url: "/a.ogg", title: "Hum" }] });
    await pending;
    out.token = run("AMB.token");
    out.playing = run("AMB.playing.size");
  } else if (scenario === "credit") {
    const link = url => {
      const layer = { index: 0, role: "tone", source: "freesound", title: "Hum",
                      username: "u", license: "CC0", gain: 1, credit_url: url };
      const row = run("ambienceLayerRow(" + JSON.stringify(layer) + ")");
      const found = [];
      const walk = node => { if (node && typeof node === "object") {
        if (node.tag === "a") found.push(node.attrs.href); (node.kids || []).forEach(walk); } };
      walk(row);
      return found;
    };
    out.https = link("https://freesound.org/people/u/sounds/1/");
    out.script = link("javascript:alert(document.cookie)");
    out.data = link("data:text/html,<script>alert(1)</script>");
  } else if (scenario === "primed") {
    out.hasPrimed = run("'primed' in AMB");
    out.hasPlayers = run("typeof ambiencePlayers");
  }
  process.stdout.write(JSON.stringify(out));
})();
"""


def _run(scenario: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="ambience-") as tmp:
        harness = Path(tmp) / "harness.js"
        harness.write_text(_HARNESS, encoding="utf-8")
        run = subprocess.run(["node", str(harness), str(JS), scenario],
                             capture_output=True, text=True, check=True, timeout=60)
    return json.loads(run.stdout)


def test_a_story_switch_forgets_the_last_storys_room():
    got = _run("switch")
    assert got["before"] == {"turnId": 10, "reroll": False}
    assert got["after"] == {"turnId": None, "signature": None, "reroll": True}
    # Nothing of story A's is rerolled or played in story B.
    assert got["posts"] == []
    assert got["audiosAfterSwitch"] == 0


def test_off_stops_a_bed_that_was_still_being_found():
    got = _run("off")
    assert got["posts"] == ["/api/turns/10/ambience"]   # the search was running
    assert got["token"] is None
    assert got["playing"] == 0


def test_only_a_web_address_is_a_source_link():
    got = _run("credit")
    assert got["https"] == ["https://freesound.org/people/u/sounds/1/"]
    assert got["script"] == []
    assert got["data"] == []


def test_no_element_claims_to_unlock_audio_without_playing():
    got = _run("primed")
    assert got["hasPrimed"] is False
    assert got["hasPlayers"] == "undefined"
