"""A browser that refuses storage still gets a working page.

Private windows and hardened profiles block `localStorage` -- reading the
property throws SecurityError, or it is `null` (Firefox with
`dom.storage.enabled=false`). The project treats that as supported:
theme-init.js, app.js, settings.js and writers_room.js all wrap storage.

chime.js and ambience.js did not (frontend audit 2026-11-01,
frontend_lorebooks_editors F1). chime.js read the mute flag inside the
initialiser of `const CHIME`, so the throw left `CHIME` and every `const`
after it in the temporal dead zone for the life of the page -- while the
hoisted `chimeWatches` still existed. `api()` calls `chimeWatches` before its
fetch, so EVERY request, GET included, threw "Cannot access 'CHIME_MUTATIONS'
before initialization" and `boot()` died. ambience.js read the same way at
the bottom of the file, so its four controls were never bound.

Three halves, each run under node: chime.js loads and answers, ambience.js
loads and binds its controls, and `api()` survives an optional module that
throws (the class: an optional module must never fail every request).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

#: A context whose storage throws on access, or is null, and a `$` that hands
#: back inert elements (recording what was bound to them).
_PRELUDE = r"""
const fs = require("fs"), vm = require("vm");
const [, , mode, ...files] = process.argv;
const bound = {};
function fakeElement(selector) {
  const classes = new Set();
  return new Proxy({ dataset: {}, style: {}, value: "0.35",
    classList: { add: c => classes.add(c), remove: c => classes.delete(c),
                 toggle: (c, on) => { (on === undefined ? !classes.has(c) : on)
                   ? classes.add(c) : classes.delete(c); },
                 contains: c => classes.has(c) },
    addEventListener() {}, setAttribute() {}, removeAttribute() {} }, {
    set(target, key, value) { target[key] = value;
      if (key === "onclick" || key === "oninput") bound[selector + "." + key] = typeof value;
      return true; },
  });
}
const elements = {};
const ctx = vm.createContext({ console, setTimeout, clearTimeout, performance,
  Promise, JSON, Math, Number, String, Map, Set, Error,
  $: selector => (elements[selector] ||= fakeElement(selector)),
  document: { addEventListener() {}, querySelector: () => null },
  window: {}, S: { chatId: null, boot: null } });
if (mode === "throws") {
  vm.runInContext(`Object.defineProperty(globalThis, "localStorage", { get() {
    const e = new Error("Access is denied for this document."); e.name = "SecurityError"; throw e; } });`, ctx);
} else {
  vm.runInContext("globalThis.localStorage = null;", ctx);
}
const result = { loaded: [], errors: [] };
for (const file of files) {
  try { vm.runInContext(fs.readFileSync(file, "utf8"), ctx, { filename: file }); result.loaded.push(file.split("/").pop()); }
  catch (e) { result.errors.push(file.split("/").pop() + ": " + e.name + " - " + e.message); }
}
"""

_CHIME = _PRELUDE + r"""
try {
  result.get = vm.runInContext('chimeWatches("GET", "/api/bootstrap")', ctx);
  result.post = vm.runInContext('chimeWatches("POST", "/api/chats")', ctx);
  vm.runInContext("chimeSetMuted(true)", ctx);
  result.muted = vm.runInContext("CHIME.muted", ctx);
} catch (e) { result.errors.push("call: " + e.name + " - " + e.message); }
process.stdout.write(JSON.stringify(result));
"""

_AMBIENCE = _PRELUDE + r"""
try {
  vm.runInContext("toggleAmbienceMute(); setAmbienceVolume(0.5);", ctx);
  result.muted = vm.runInContext("AMB.muted", ctx);
  result.volume = vm.runInContext("AMB.volume", ctx);
} catch (e) { result.errors.push("call: " + e.name + " - " + e.message); }
result.bound = bound;
process.stdout.write(JSON.stringify(result));
"""

#: `api()` from utils.js, beside a chime hook that throws the way the broken
#: load made it throw, and a fetch that answers.
_API = r"""
const fs = require("fs"), vm = require("vm");
const [, , utils] = process.argv;
const ctx = vm.createContext({ console, performance, JSON, Error, String, Array,
  fetch: async () => ({ ok: true, status: 200,
    headers: { get: () => "application/json" }, json: async () => ({ fine: true }) }),
  document: {}, window: {} });
vm.runInContext(fs.readFileSync(utils, "utf8"), ctx, { filename: "utils.js" });
vm.runInContext(`function chimeWatches() {
  throw new ReferenceError("Cannot access 'CHIME_MUTATIONS' before initialization"); }`, ctx);
vm.runInContext('api("GET", "/api/bootstrap")', ctx).then(
  value => process.stdout.write(JSON.stringify({ value })),
  error => process.stdout.write(JSON.stringify({ error: error.message })));
"""


def _node(script: str, *args: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="storage-") as tmp:
        harness = Path(tmp) / "harness.js"
        harness.write_text(script, encoding="utf-8")
        run = subprocess.run(["node", str(harness), *args],
                             capture_output=True, text=True, check=True, timeout=60)
    return json.loads(run.stdout)


@pytest.mark.parametrize("mode", ["throws", "null"])
def test_the_chime_loads_and_answers_without_storage(mode):
    got = _node(_CHIME, mode, str(JS / "chime.js"))
    assert got["errors"] == []
    assert got["loaded"] == ["chime.js"]
    assert got["get"] is False and got["post"] is True
    # The switch still works for this page; it just is not remembered.
    assert got["muted"] is True


@pytest.mark.parametrize("mode", ["throws", "null"])
def test_ambience_loads_and_binds_its_controls_without_storage(mode):
    got = _node(_AMBIENCE, mode, str(JS / "ambience.js"))
    assert got["errors"] == []
    assert got["muted"] is True
    assert got["volume"] == 0.5
    assert got["bound"] == {"#b-ambience.onclick": "function",
                            "#b-amb-mute.onclick": "function",
                            "#b-amb-reroll.onclick": "function",
                            "#amb-vol.oninput": "function"}


def test_an_optional_module_that_throws_does_not_fail_a_request():
    got = _node(_API, str(JS / "utils.js"))
    assert got == {"value": {"fine": True}}
