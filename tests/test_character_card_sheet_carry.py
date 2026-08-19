"""The card editor must not delete the fields it has no widget for.

`PUT /api/characters/{cid}` replaces the stored sheet wholesale, and
`charEditor` rebuilds that sheet field by field from its widgets. Every field
without a widget was therefore destroyed the first time anyone opened the
card -- and `normalize_character_data`'s `_deep_defaults` backfilled the hole
on the way back out, so the loss read as a value somebody chose rather than as
a deletion. Measured live on `simulation.sampler` (passed to the character's
model call), `simulation.curiosity`, and `psychology.projects`, which a
character adopts mid-play and is meant to give up only as a legible act.

These tests run the editor's ACTUAL payload literal -- sliced out of
`static/js/editors.js` and evaluated under node with stub widgets -- and feed
the result through the real normalizer and the real runtime readers. That is
the whole round trip the defect lived in: browser build, wholesale PUT,
normalize, read. A source-substring assertion could not have caught it, since
the bug was a field's ABSENCE.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from story.character_schema import (
    character_curiosity,
    character_projects,
    character_sampler,
    normalize_character_data,
)

ROOT = Path(__file__).resolve().parents[1]
EDITORS = ROOT / "static" / "js" / "editors.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)

# A stored sheet carrying exactly the three measured fields plus one the
# engine has not invented yet -- the fourth is the point, since a fix that
# names the three would lose it.
STORED = {
    "identity": {"uid": "character:x", "name": "Aleth"},
    "simulation": {
        "tier": "high",
        "temperature": 0.7,
        "curiosity": 0.9,
        "sampler": {"top_p": 0.85, "min_p": 0.02},
    },
    "psychology": {
        "projects": [{"project": "Rebuild the orrery", "about": "world"}],
        "traits": ["patient"],
    },
    "initial_outfit": {
        "regions": {"torso": {"garments": [{"name": "coat"}], "beneath": ""}},
        "wearing": ["coat"],
        "state": [],
    },
    "a_field_from_a_later_schema": {"kept": True},
}

_HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const stored = JSON.parse(process.argv[3]);

// The helper, sliced by its own name so a rename fails loudly here.
const hStart = src.indexOf("function carryUnpresentedFields(");
const hEnd = src.indexOf("\n\n", src.indexOf("const OWNED_SHEET_PATHS"));
if (hStart < 0 || hEnd < 0) throw new Error("carry helper not found");
// `const` inside a direct eval stays inside it; `var` reaches this scope,
// which is the only reason for the rewrite.
eval(src.slice(hStart, hEnd)
        .replace("const OWNED_SHEET_PATHS", "var OWNED_SHEET_PATHS"));
if (!Array.isArray(OWNED_SHEET_PATHS)) throw new Error("owned paths not found");

// The editor's real payload, bounded by the call that wraps it. First match is
// charEditor's; personaEditor's is the second.
const CALL = "const s = carryUnpresentedFields(sheet, {";
const TAIL = "}, OWNED_SHEET_PATHS);";
const pStart = src.indexOf(CALL);
if (pStart < 0) throw new Error("charEditor payload not found");
const pEnd = src.indexOf(TAIL, pStart) + TAIL.length;
const built = src.slice(pStart + "const s = ".length, pEnd - 1);
const bare = built.slice("carryUnpresentedFields(sheet, ".length,
                         built.length - ", OWNED_SHEET_PATHS)".length);

// Stub widgets: every f.<name> answers the three shapes the payload uses.
const widget = {
  read: () => "",
  checked: false,
  querySelector: () => ({ checked: false }),
};
var sheet = stored;
var f = new Proxy({}, { get: () => widget });
var gc = null;
var ph = widget;
var splitCL = v => (Array.isArray(v) ? v : []);
var access_tags = ["common"];

const withCarry = eval(built);
const withoutCarry = eval("(" + bare + ")");
console.log(JSON.stringify({ withCarry, withoutCarry }));
"""


def _editor_payload() -> dict:
    """Evaluate charEditor's save payload against STORED, under node."""
    script = ROOT / "tests" / "_carry_harness.js"
    script.write_text(_HARNESS, encoding="utf-8")
    try:
        out = subprocess.run(
            ["node", str(script), str(EDITORS), json.dumps(STORED)],
            capture_output=True, text=True, check=True,
        )
    finally:
        script.unlink(missing_ok=True)
    return json.loads(out.stdout)


def test_the_editor_would_lose_the_fields_without_the_carry():
    """The positive control: prove the defect is real before proving the fix.

    Without the carry, the payload the browser sends has no sampler, no
    curiosity and no projects -- and the normalizer then invents defaults for
    all three, which is why nobody saw the deletion.
    """
    bare = _editor_payload()["withoutCarry"]
    assert "curiosity" not in bare["simulation"]
    assert "projects" not in bare["psychology"]
    assert "a_field_from_a_later_schema" not in bare

    normalized = normalize_character_data(bare)
    assert character_sampler(normalized) == {}
    assert character_curiosity(normalized) == 0.5
    assert character_projects(normalized) == []


def test_the_saved_sheet_keeps_every_field_the_editor_does_not_present():
    """The fix, measured where it matters: after the round trip the runtime
    readers still see what the author wrote."""
    merged = _editor_payload()["withCarry"]
    normalized = normalize_character_data(merged)

    assert character_sampler(normalized) == {"top_p": 0.85, "min_p": 0.02}
    assert character_curiosity(normalized) == 0.9
    projects = character_projects(normalized)
    assert len(projects) == 1
    assert projects[0]["project"] == "Rebuild the orrery"
    # The class, not the three instances: a field this schema has never heard
    # of survives a save exactly as an authored one does.
    assert merged["a_field_from_a_later_schema"] == {"kept": True}


def test_the_carry_never_resurrects_a_garment_the_author_deleted():
    """`initial_outfit` is the one subtree the editor rebuilds WHOLE.

    The garment widget regenerates `regions` from its own list, so a missing
    region is a deletion; and `wearing`/`state` are derived mirrors that
    `_normalize_initial_outfit` folds back INTO `regions`, which would let the
    same garment return through the other door.
    """
    merged = _editor_payload()["withCarry"]
    assert merged["initial_outfit"] == {"regions": ""}, merged["initial_outfit"]

    normalized = normalize_character_data(merged)
    assert normalized["initial_outfit"]["regions"] == {}
    assert normalized["initial_outfit"]["wearing"] == []


def test_both_card_editors_route_their_payload_through_the_carry():
    """charEditor and personaEditor have the same shape and the same exposure;
    a new editor that builds a sheet field by field needs the same call."""
    source = EDITORS.read_text(encoding="utf-8")
    assert source.count("const s = carryUnpresentedFields(sheet, {") == 2
    assert source.count("}, OWNED_SHEET_PATHS);") == 2
