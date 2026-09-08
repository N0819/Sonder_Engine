"""A CLOSED SET THE ENGINE OWNS must reach the browser FROM the engine.

The class is the set, not the screen that renders it: wherever Python holds
the only authoritative list of a stored field's permitted values, the menu
offering those values reads it off `/api/bootstrap` and keeps at most a named
fallback. Scoping this to "the card editor" is what let the lorebook editor
fall outside it once already.

Review 2026-09-07, finding B24: `static/js/components.js` retyped
`ATTIRE_REGIONS` and `ATTIRE_REGION_ZONES` as literals while
`static/js/world_browser.js` was already rendering the shipped
`vocab.attire_regions` -- two sites answering one question, and the zone map
shipped by nobody at all. The same file carried two more of the same shape:
`EXTRA_PART_ASPECTS` (`story/character_schema.py`) and `INTERIOR_LIGHTS`
(`world/spatial_light.py`'s `LIGHT_LEVELS`, which is what actually resolves
that field at mint). `static/js/lorebooks.js` carried a fifth,
`LORE_INHERITANCE_MODES`, against which `PUT /api/lorebooks/{id}` was
validating an inline tuple of its own -- the same three words typed in three
places, and the only one of the three with a name (`mind/memory.py`'s
constant) read by nobody.

Drift in any of them has NO symptom, bar the last. Every one of these is
coerced silently on save -- `attire.py` rewrites an unknown region to the
default region and drops an unknown zone, `character_schema` drops an unknown
aspect, `normalize_light` rewrites an unknown light -- so a term added
server-side is merely missing from the menu, and one removed is offered in the
menu and quietly discarded. The inheritance mode fails louder and no better:
the menu offers a mode and the route answers 400. That is why this needs a
test rather than a convention.

The browser keeps a fallback for a tab whose cached JavaScript is running
ahead of its first bootstrap response, the same posture `MEM_CATS_FALLBACK`
keeps in `static/js/utils.js`. A fallback is allowed to exist; it is not
allowed to disagree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mind.memory import KNOWLEDGE_RANGES, KNOWLEDGE_TAGS, LORE_INHERITANCE_MODES
from story import attire
from story.character_schema import EXTRA_PART_ASPECTS
from world.paradox import MODES as PARADOX_MODES
from world.spatial import LIGHT_LEVELS

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = (ROOT / "static/js/components.js").read_text(encoding="utf-8")
LOREBOOKS = (ROOT / "static/js/lorebooks.js").read_text(encoding="utf-8")
SETTINGS = (ROOT / "static/js/settings.js").read_text(encoding="utf-8")

# The second rework of B24 found the class stops at NAMED constants only if
# the test does: three more engine-owned sets sat as literals at the point of
# use -- `KNOWLEDGE_TAGS` and `KNOWLEDGE_RANGES` (two lines below the mode
# accessor this test had just pinned) and `world/paradox.py`'s `MODES`, the
# loudest of the family because the route RAISES on an unknown mode. So the
# point-of-use check below also refuses the literal spelling of each set.


def _js_array(source: str, name: str) -> list[str]:
    """The literal a top-level `const NAME = [...]` holds, comments stripped."""
    match = re.search(r"^const %s = (\[[^\]]*\]);" % re.escape(name),
                      source, re.MULTILINE | re.DOTALL)
    assert match, f"{name} not found as a top-level array"
    body = re.sub(r"//[^\n]*", "", match.group(1))
    return json.loads(re.sub(r",(\s*])", r"\1", body))


def _js_object(source: str, name: str) -> dict:
    """The literal a top-level `const NAME = {...}` holds."""
    match = re.search(r"^const %s = (\{[^}]*\});" % re.escape(name),
                      source, re.MULTILINE | re.DOTALL)
    assert match, f"{name} not found as a top-level object"
    body = re.sub(r"//[^\n]*", "", match.group(1))
    body = re.sub(r"(\w+):", r'"\1":', body)
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", body))


def test_the_editors_read_the_shipped_vocabularies():
    """Every menu an editor renders from a closed set reads the bootstrap."""
    for source, keys, frozen_names in (
        (COMPONENTS,
         ("attire_regions", "attire_region_zones",
          "extra_part_aspects", "interior_lights"),
         ("ATTIRE_REGIONS", "ATTIRE_REGION_ZONES",
          "EXTRA_PART_ASPECTS", "INTERIOR_LIGHTS")),
        (LOREBOOKS,
         ("lorebook_inheritance_modes", "knowledge_tags", "knowledge_ranges"),
         ("LORE_INHERITANCE_MODES", "KNOWLEDGE_TAGS", "KNOWLEDGE_RANGES")),
        (SETTINGS,
         ("paradox_modes",),
         ("PARADOX_MODES",)),
    ):
        for key in keys:
            assert "S.boot.%s" % key in source, key
        # And nothing may go back to reading a frozen copy at the point of
        # use: the only surviving literals are the named fallbacks. Comments
        # are stripped first -- they cite the engine's constants by name on
        # purpose.
        code = re.sub(r"//[^\n]*", "", source)
        for frozen in frozen_names:
            assert re.search(r"\b%s\b(?!_FALLBACK)" % frozen, code) is None, frozen
        # A literal at the point of use is the same drift under no name at
        # all: every array literal in the file that spells one of the
        # engine's sets must be the named fallback's own line.
        for line in code.splitlines():
            literal = re.search(r"\[\s*\"[^\]]*\"\s*\]", line)
            if not literal or "_FALLBACK = " in line:
                continue
            try:
                words = json.loads(re.sub(r",(\s*])", r"\1", literal.group(0)))
            except ValueError:
                continue
            for owned in (list(attire.REGIONS), list(EXTRA_PART_ASPECTS),
                          list(LIGHT_LEVELS), list(LORE_INHERITANCE_MODES),
                          list(KNOWLEDGE_TAGS), list(KNOWLEDGE_RANGES),
                          list(PARADOX_MODES)):
                assert sorted(words) != sorted(owned), line.strip()


def test_the_editor_fallbacks_still_agree_with_the_engine():
    """A drifted fallback is worse than none: it renders a plausible menu out
    of terms the engine will overwrite without saying so."""
    assert _js_array(COMPONENTS, "ATTIRE_REGIONS_FALLBACK") == list(attire.REGIONS)
    assert _js_object(COMPONENTS, "ATTIRE_REGION_ZONES_FALLBACK") == {
        region: list(zones) for region, zones in attire.REGION_ZONES.items()}
    assert _js_array(COMPONENTS, "EXTRA_PART_ASPECTS_FALLBACK") == list(EXTRA_PART_ASPECTS)
    assert _js_array(COMPONENTS, "INTERIOR_LIGHTS_FALLBACK") == list(LIGHT_LEVELS)
    assert (_js_array(LOREBOOKS, "LORE_INHERITANCE_MODES_FALLBACK")
            == list(LORE_INHERITANCE_MODES))
    assert _js_array(LOREBOOKS, "KNOWLEDGE_TAGS_FALLBACK") == list(KNOWLEDGE_TAGS)
    assert _js_array(LOREBOOKS, "KNOWLEDGE_RANGES_FALLBACK") == list(KNOWLEDGE_RANGES)
    assert _js_array(SETTINGS, "PARADOX_MODES_FALLBACK") == list(PARADOX_MODES)


def _client():
    from fastapi.testclient import TestClient

    from web import app as app_module
    from web import guest_access as guest

    guest.reset_host_account()
    client = TestClient(app_module.app)
    client.__enter__()
    r = client.post("/api/auth/setup",
                    json={"username": "host", "password": "pw12345"})
    assert r.status_code == 200, r.text
    return client


def test_the_bootstrap_ships_every_vocabulary_the_editors_render(temp_db):
    """Read off the real response, not off the source: the fallback agreeing
    with the engine proves nothing if the shipped list never arrives."""
    client = _client()
    try:
        boot = client.get("/api/bootstrap").json()
    finally:
        client.__exit__(None, None, None)
    assert boot["attire_regions"] == list(attire.REGIONS)
    assert boot["attire_region_zones"] == {
        region: list(zones) for region, zones in attire.REGION_ZONES.items()}
    assert boot["extra_part_aspects"] == list(EXTRA_PART_ASPECTS)
    assert boot["interior_lights"] == list(LIGHT_LEVELS)
    assert boot["lorebook_inheritance_modes"] == list(LORE_INHERITANCE_MODES)
    assert boot["knowledge_tags"] == list(KNOWLEDGE_TAGS)
    assert boot["knowledge_ranges"] == list(KNOWLEDGE_RANGES)
    assert boot["paradox_modes"] == list(PARADOX_MODES)


def test_the_lorebook_route_validates_against_the_shipped_list(temp_db):
    """The menu and the validator quote one source (B24, rework): the mode
    picker offered whatever `static/js/lorebooks.js` had typed, and
    `PUT /api/lorebooks/{id}` refused whatever an inline tuple did not name.
    Every mode the bootstrap offers must be one the route accepts."""
    client = _client()
    try:
        offered = client.get("/api/bootstrap").json()["lorebook_inheritance_modes"]
        lid = client.post("/api/lorebooks",
                          json={"name": "Book"}).json()["id"]
        for mode in offered:
            r = client.put("/api/lorebooks/%d" % lid,
                           json={"inheritance_mode": mode})
            assert r.status_code == 200, (mode, r.text)
            assert r.json()["book"]["inheritance_mode"] == mode
        refused = client.put("/api/lorebooks/%d" % lid,
                             json={"inheritance_mode": "borrowed"})
        assert refused.status_code == 400, refused.text
    finally:
        client.__exit__(None, None, None)
