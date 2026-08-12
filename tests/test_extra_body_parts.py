"""Extra body parts as structured data (design_notes/11-extra-body-parts.md).

A tail that exists only inside `embodiment.visible.summary` is prose: it
cannot be gated per observer, cannot interact with clothing coverage, and is
re-invented (or forgotten) by every model call. These tests pin the structured
alternative end to end:

* the card field normalizes through closed menus (`at` from attire.REGIONS,
  `aspect` from EXTRA_PART_ASPECTS) with junk tolerated, never crashed on;
* a sheet without the field behaves byte-identically to today -- the
  non-negotiable requirement;
* visibility rides the SAME region_visibility verdicts clothing uses: a
  through-clothing tail stays visible over a covered region, a tucked part
  hides with it, vantage/containment hide everything, and a body is never
  concealed from itself;
* a declared part is already a valid contact endpoint, because spatial's
  part identity is structural rather than a vocabulary.

Deliberately database-free: pure dicts in, dicts out.
"""

from __future__ import annotations

import copy

from agents.common import (
    extra_part_phrase,
    extra_parts_lines,
    observer_body_regions,
)
from character_schema import (
    EXTRA_PART_ASPECTS,
    character_extra_parts,
    default_character_data,
    normalize_character_data,
    normalize_persona_data,
    persona_extra_parts,
)
from spatial import apply_contact_ops, contacts_of


# --- the card field ----------------------------------------------------------

def _sheet(parts):
    data = default_character_data("Mira")
    data["embodiment"]["extra_parts"] = parts
    return data


def test_a_sheet_without_the_field_normalizes_to_an_empty_list():
    """Every existing card predates this field; [] is what keeps the whole
    feature inert for them."""
    assert character_extra_parts({"identity": {"name": "Old"}}) == []
    assert persona_extra_parts({"identity": {"name": "P"},
                                "narration": {}}) == []
    legacy = {"name": "Legacy", "appearance": "a tall person"}
    assert character_extra_parts(legacy) == []


def test_menus_are_enforced_and_junk_falls_to_the_placement_guess():
    parts = character_extra_parts(_sheet([
        {"kind": "tail", "at": "nowhere", "aspect": "diagonal", "count": 99},
        {"kind": "wings", "count": 2},
        "horns",
        {"at": "torso"},          # no kind: nothing to attach -- dropped
        7,                        # not a part at all
    ]))
    assert [p["kind"] for p in parts] == ["tail", "wings", "horns"]
    tail, wings, horns = parts
    # Unreadable menu values fall to the per-kind guess, never crash and
    # never survive as open text a later reader must parse.
    assert (tail["at"], tail["aspect"]) == ("waist", "back")
    assert tail["count"] == 12          # clamped to the ceiling
    assert (wings["at"], wings["aspect"]) == ("torso", "back")
    assert (horns["at"], horns["aspect"]) == ("head", "top")
    for part in parts:
        assert part["at"] in ("head", "torso", "arms", "hands", "waist",
                              "groin", "legs", "feet")
        assert part["aspect"] in EXTRA_PART_ASPECTS
        assert part["through_clothing"] is True    # the tail-through-skirt default


def test_authored_menu_choices_survive_normalization():
    parts = character_extra_parts(_sheet([
        {"kind": "arm", "count": 2, "at": "torso", "aspect": "sides",
         "through_clothing": False, "description": "chitinous, folded"},
    ]))
    assert parts == [{"kind": "arm", "count": 2, "at": "torso",
                      "aspect": "sides", "through_clothing": False,
                      "description": "chitinous, folded"}]


def test_normalization_is_idempotent():
    once = normalize_character_data(_sheet([{"kind": "tail"}]))
    twice = normalize_character_data(copy.deepcopy(once))
    assert once["embodiment"]["extra_parts"] == twice["embodiment"]["extra_parts"]


def test_persona_carries_parts_too():
    sheet = normalize_persona_data({"identity": {"name": "Player"},
                                    "narration": {}})
    sheet["embodiment"]["extra_parts"] = [{"kind": "tail"}]
    assert persona_extra_parts(sheet)[0]["kind"] == "tail"


# --- deterministic rendering -------------------------------------------------

def test_the_phrase_is_deterministic_and_states_the_attachment():
    part = {"kind": "tail", "count": 1, "at": "waist", "aspect": "back",
            "through_clothing": True, "description": "russet-furred"}
    text = extra_part_phrase(part)
    assert text == ("tail — emerges from the back of the waist; "
                    "passes through clothing worn there; russet-furred")
    assert extra_part_phrase(dict(part)) == text
    assert extra_parts_lines([]) == []
    assert extra_parts_lines([{"kind": ""}]) == []


def test_a_pair_reads_as_a_pair():
    text = extra_part_phrase({"kind": "wing", "count": 2, "at": "torso",
                              "aspect": "back", "through_clothing": True})
    assert text.startswith("wing x2 — emerge from the back of the torso")


# --- visibility through the attire seam --------------------------------------

TAPROOM = {"taproom": {"name": "the Taproom"}}

TAIL = [{"kind": "tail", "count": 1, "at": "waist", "aspect": "back",
         "through_clothing": True, "description": "long and expressive"}]
TUCKED = [{"kind": "vestigial wings", "count": 2, "at": "torso",
           "aspect": "back", "through_clothing": False, "description": ""}]

# A wrapped dress: covers torso/waist/groin/legs, so both attachment regions
# above are garment-concealed while it is worn.
DRESSED = {"wearing": ["a woollen dress"]}


def _scene(positions, attire=None):
    return {"rooms": dict(TAPROOM), "positions": dict(positions),
            "attire": dict(attire or {})}


def _row(rows, label):
    return next((r for r in rows if r["body"] == label), None)


def test_no_declaration_means_byte_identical_payloads():
    """THE inert-default check: with no parts declared, the projection is
    exactly what it was before the parameter existed -- same rows, same keys,
    whether the argument is omitted, None, or {}."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": DRESSED})
    labels = {"Mira": "the traveller"}
    before = observer_body_regions(sc, "Watcher", labels)
    assert before == observer_body_regions(sc, "Watcher", labels,
                                           extra_parts=None)
    assert before == observer_body_regions(sc, "Watcher", labels,
                                           extra_parts={})
    assert all("parts" not in row for row in before)


def test_a_through_clothing_tail_shows_over_a_covered_region():
    """The real case: a tail through a skirt. The waist is garment-concealed,
    and the tail is delivered anyway, because the garment is worn around it."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": DRESSED})
    rows = observer_body_regions(sc, "Watcher", {"Mira": "the traveller"},
                                 extra_parts={"Mira": TAIL})
    row = _row(rows, "the traveller")
    assert row is not None
    assert any(p.startswith("tail — emerges from the back of the waist")
               for p in row["parts"])
    assert "Mira" not in str(rows), "canonical identity leaked"


def test_a_tucked_part_hides_with_the_region_and_shows_when_it_is_bare():
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": DRESSED})
    dressed = observer_body_regions(sc, "Watcher", {"Mira": "the traveller"},
                                    extra_parts={"Mira": TUCKED})
    assert all("wings" not in str(row.get("parts", [])) for row in dressed)

    bare = _scene({"Watcher": "taproom", "Mira": "taproom"},
                  {"Mira": {"wearing": []}})
    shown = observer_body_regions(bare, "Watcher", {"Mira": "the traveller"},
                                  extra_parts={"Mira": TUCKED})
    row = _row(shown, "the traveller")
    assert row is not None and any("vestigial wings" in p
                                   for p in row["parts"])


def test_darkness_conceals_the_tail_with_the_rest_of_the_body():
    """Vantage concealment is body-level: through-clothing does not mean
    through-darkness."""
    dark = {"rooms": {"cellar": {"name": "Cellar", "light": "dark"}},
            "positions": {"Watcher": "cellar", "Mira": "cellar"},
            "attire": {"Mira": dict(DRESSED)}}
    rows = observer_body_regions(dark, "Watcher", {"Mira": "the traveller"},
                                 extra_parts={"Mira": TAIL})
    assert rows == []


def test_containment_conceals_the_tail_too():
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": DRESSED})
    sc["contained"] = {"Mira": {"in": "the wardrobe", "mode": "hidden"}}
    rows = observer_body_regions(sc, "Watcher", {"Mira": "the traveller"},
                                 extra_parts={"Mira": TAIL})
    assert rows == []


def test_a_body_is_never_concealed_from_itself():
    """The self-knowledge floor: own parts always arrive, and a tucked one
    says where it is rather than vanishing."""
    dark = {"rooms": {"cellar": {"name": "Cellar", "light": "dark"}},
            "positions": {"Mira": "cellar"},
            "attire": {"Mira": dict(DRESSED)},
            "contained": {"Mira": {"in": "the crate", "mode": "shut"}}}
    rows = observer_body_regions(dark, "Mira", {"Mira": "you"},
                                 extra_parts={"Mira": TUCKED + TAIL})
    row = _row(rows, "you")
    assert row is not None
    tucked = next(p for p in row["parts"] if "vestigial wings" in p)
    assert "[currently beneath clothing]" in tucked
    assert any(p.startswith("tail") for p in row["parts"])


def test_parts_arrive_for_a_body_with_no_attire_entry():
    """Bare hands are bare, not unmodelled: a body the attire ledger never
    dressed still has its declared anatomy."""
    sc = _scene({"Watcher": "taproom", "Stranger": "taproom"})
    rows = observer_body_regions(sc, "Watcher", {"Stranger": "a stranger"},
                                 extra_parts={"Stranger": TAIL})
    row = _row(rows, "a stranger")
    assert row is not None and row["regions"] == {}
    assert any(p.startswith("tail") for p in row["parts"])


def test_the_parts_map_key_is_matched_tolerantly():
    """One being, one name: the map is keyed by display name and a caller
    holding another casing must not get a tailless body."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": DRESSED})
    rows = observer_body_regions(sc, "Watcher", {"mira": "the traveller"},
                                 extra_parts={"Mira": TAIL})
    assert any("tail" in str(row.get("parts", [])) for row in rows)


# --- contacts ----------------------------------------------------------------

def test_a_declared_part_is_a_valid_contact_endpoint():
    """No schema change was needed and none may creep in: `actor_part` is
    free text, and the structural identity rules already treat a refinement
    ('tail spade') as the same appendage, so re-describing the hold MOVES it
    rather than minting a second tail."""
    scene = {"rooms": dict(TAPROOM),
             "positions": {"Mira": "taproom", "Corin": "taproom"},
             "entities": {}, "contacts": []}
    apply_contact_ops(scene, [{"op": "add", "actor": "Mira",
                               "actor_part": "tail", "target": "Corin",
                               "target_part": "wrist", "manner": "coil"}])
    held = contacts_of(scene, "Mira")
    assert len(held) == 1 and held[0]["actor_part"] == "tail"

    apply_contact_ops(scene, [{"op": "add", "actor": "Mira",
                               "actor_part": "tail spade", "target": "Corin",
                               "target_part": "forearm", "manner": "press"}])
    held = contacts_of(scene, "Mira")
    assert len(held) == 1, "one tail became two"
    assert held[0]["target_part"] == "forearm"

    # Declaring the part changes nothing in the spatial ledgers themselves --
    # poses, scales and containment never read the card.
    assert scene.get("scales", {}) == {}
    assert "contained" not in scene or scene["contained"] == {}


# --- the merge gap: gated correctly, rendered nowhere ----------------------
#
# This feature and the deterministic composer were built in parallel and
# merged afterwards. `observer_body_regions` returns parts in a sibling key
# to `regions`, and the composer's body-region projection read only
# `regions` -- so on the live path the whole feature was gated correctly and
# then dropped on the floor. Nothing failed; the tails simply never reached
# a view. These pin the wiring rather than the gate.

def test_parts_reach_a_composed_view():
    from agents.common import observer_body_regions
    from agents.composer import body_part_percepts, render_view

    scene = {"rooms": {"h": {"name": "Hall", "light": "bright"}},
             "positions": {"Vess": "h", "Hinami": "h"},
             "attire": {}, "overlays": {}}
    parts = {"Hinami": [{"kind": "tail", "count": 6, "at": "waist",
                         "aspect": "back", "through_clothing": True,
                         "description": "golden and slow-moving"}]}
    rows = observer_body_regions(
        scene, "Vess", {"Vess": "you", "Hinami": "the fox-eared woman"},
        extra_parts=parts)

    assert rows and rows[0].get("part_data"), (
        "the gated projection must carry the parts themselves, not only the "
        "payload phrase -- the composer renders straight to a reader")

    percepts = body_part_percepts([
        (r["body"], p) for r in rows for p in r.get("part_data") or []])
    text = render_view(percepts).text
    assert text == ("Six tails emerge from the back of the fox-eared "
                    "woman's waist, golden and slow-moving.")
    assert "x6" not in text, "payload grammar reached the reader"


def test_your_own_parts_are_yours():
    from agents.composer import body_part_percepts, render_view

    text = render_view(body_part_percepts([
        ("you", {"kind": "wing", "count": 2, "at": "shoulders",
                 "aspect": "back", "description": ""})])).text
    assert text == "Two wings emerge from the back of your shoulders."


def test_a_single_part_reads_as_one():
    from agents.composer import body_part_percepts, render_view

    text = render_view(body_part_percepts([
        ("the horned man", {"kind": "horn", "count": 1, "at": "brow",
                            "aspect": "left"})])).text
    assert text == "A horn emerges from the left side of the horned man's brow."
