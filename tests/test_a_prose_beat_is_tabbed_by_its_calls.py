"""A prose-contract Director step is tabbed by the calls that ran.

Under the prose contract (agents/director_prose.py) the encoder's answer is
filed through each channel owner's binding, so the stored
`orchestration.specialists` carries `run`/`ran: true` for every hand that got
a channel -- and the step window built its "Written by" bar from that table.
The owner switched the contract on, played a beat and read "Written by:
prose author, social, objects, spatial": "latest turn it still seems to be
running specialists despite me telling it to use the prose contract"
(2026-09-24). Turn 4398 had made three calls a stage -- director, jev,
director_specialist -- and no specialist call at all.

These execute the real lens code from static/js/chat.js in Node.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

CHAT_JS = Path(__file__).resolve().parents[1] / "static/js/chat.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(process.argv[1], 'utf8');
const lines = [];
const context = vm.createContext({
  t: text => text,
  el: (tag, attrs, text) => text,
  box: {set innerHTML(value) {}, append: text => lines.push(text)},
});
function load(from, to) {
  const start = source.indexOf(from);
  const end = source.indexOf(to, start);
  if (start < 0 || end < 0) throw new Error('missing ' + from);
  vm.runInContext(source.slice(start, end), context);
}
load('function perceiverViews(', '// What the deterministic layer did');
load('function renderEngineNotes(', "// The drawer's map panel");
context.content = request.content;
const lenses = vm.runInContext('stepLenses(content)', context);
context.lenses = lenses;
const labels = {}, slices = {};
for (const id of lenses.ids) {
  context.id = id;
  labels[id] = vm.runInContext('lensLabel(lenses, id, content, {})', context);
  slices[id] = vm.runInContext('lensSlice(lenses, content, id, {}, null)', context);
}
vm.runInContext('renderEngineNotes(box, content)', context);
process.stdout.write(JSON.stringify({lenses, labels, slices, notes: lines}));
"""


def _run(content):
    result = subprocess.run(
        ["node", "-e", HARNESS, str(CHAT_JS)],
        input=json.dumps({"content": content}),
        capture_output=True, text=True, check=True, timeout=10,
    )
    return json.loads(result.stdout)


def _hand(channels_filled):
    return {"run": True, "ran": True, "scope": list(channels_filled),
            "addressed_by": ["decision_model"], "answered_by": "encoder",
            "channels": list(channels_filled), "channels_filled": list(channels_filled)}


def _prose_step(room_author=None):
    """The shape of turn 4398's director_resolve, trimmed."""
    return {
        "state_diff": {"positions": {"The Doctor": "console_room"}},
        "orchestration": {
            "enabled": True, "stage": "resolve",
            "specialists": {
                "body": {"run": False, "scope": [], "addressed_by": [],
                         "channels": ["attire", "poses"]},
                "social": _hand(["obligations"]),
                "objects": _hand(["entities", "inventory_ops"]),
                "spatial": _hand(["positions"]),
            },
            "prose_contract": {
                "stage": "resolve",
                "prose": "The Doctor releases his grip on the lever.",
                "author_seconds": 4.655,
                "jev": {"candidates": ["attire", "positions", "obligations"],
                        "threshold": 0.5,
                        "probabilities": {"attire": 0.16, "positions": 0.91,
                                          "obligations": 0.62},
                        "selected": ["positions", "obligations", "entities"],
                        "entered": [], "seconds": 0.289},
                "channels": ["positions", "obligations", "entities"],
                "encoder": {"seconds": 5.214},
                "room_author": room_author or {},
                "events": [{"event": "The Doctor releases the lever."},
                           {"event": "He shouts over the column."}],
                "missing_referents": [], "notes": [],
            },
        },
        "_engine_notes": {"llm_calls": [
            {"role": "director", "requested": "glm", "duration": 4.6},
            {"role": "jev", "requested": "jev", "duration": 0.3},
            {"role": "director_specialist", "requested": "deepseek",
             "duration": 5.2},
        ]},
    }


def test_the_tabs_are_the_calls_that_ran_not_the_hands_that_filed():
    out = _run(_prose_step())
    assert out["lenses"]["kind"] == "prose_contract"
    assert out["lenses"]["label"] == "Written by"
    assert out["lenses"]["ids"] == ["writer", "channels", "encoder"]
    for hand in ("social", "objects", "spatial"):
        assert hand not in out["lenses"]["ids"]
    assert out["labels"] == {"writer": "writer",
                             "channels": "channel picker ·3",
                             "encoder": "encoder ·2"}


def test_the_hands_are_named_on_the_encoders_tab_as_code():
    out = _run(_prose_step())
    encoder = out["slices"]["encoder"]
    assert "engine code, no model call" in encoder
    assert "objects: entities, inventory_ops" in encoder
    assert "The Doctor releases the lever." in encoder
    assert "The Doctor releases his grip" in out["slices"]["writer"]


def test_the_channel_pickers_tab_shows_each_kind_against_the_threshold():
    picker = _run(_prose_step())["slices"]["channels"]
    assert "granted at 0.5 or above" in picker
    assert "✓ 0.91  positions" in picker
    assert "  0.16  attire" in picker
    # A kind the picker was never asked about is still named.
    assert "granted without asking: entities" in picker


def test_the_room_designer_gets_a_tab_only_when_it_ran():
    assert "rooms" not in _run(_prose_step(room_author={
        "reserved": {"vault": {"name": "Vault"}}}))["lenses"]["ids"]
    out = _run(_prose_step(room_author={
        "ran": "parallel", "seconds": 12.4, "rooms": ["vault"]}))
    assert out["lenses"]["ids"] == ["writer", "channels", "encoder", "rooms"]
    assert out["labels"]["rooms"] == "room designer ·1"
    assert "built: vault" in out["slices"]["rooms"]
    failed = _run(_prose_step(room_author={"ran": "serial", "failed": "timeout"}))
    assert failed["labels"]["rooms"] == "room designer ·failed"


def test_each_call_line_says_which_call_it_was():
    notes = _run(_prose_step())["notes"]
    assert notes[0].startswith("⏱ director (writer) ·")
    assert notes[1].startswith("⏱ jev (channel picker) ·")
    assert notes[2].startswith("⏱ director_specialist (encoder) ·")


def test_a_causal_step_keeps_its_specialist_tabs():
    step = _prose_step()
    del step["orchestration"]["prose_contract"]
    step["_engine_notes"]["llm_calls"][2]["role"] = "director_spatial"
    out = _run(step)
    assert out["lenses"]["kind"] == "specialist"
    assert out["lenses"]["ids"] == ["prose", "social", "objects", "spatial"]
    assert out["notes"][0].startswith("⏱ director ·")
