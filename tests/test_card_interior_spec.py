"""The card half of "a body's inside is a place": `embodiment.interior`.

THE ENGINE FLOOR MINTS ONE ROOM AND ONE IS ALL IT MAY MINT. The enclosure
record entails that an inside exists, whose it is, and that it is out of the
surrounding room's sight -- it entails nothing about internal structure, so
any multi-room default would be invented anatomy. Richer topology is authored,
and this is the surface it is authored on: an ordered list of stations,
outermost first, normalized here and carried to the scene by
`agents.common.stamp_authored_interiors`, which is the one seam that can --
`merge_scene_with_diff` is handed a scene and a diff and has no cast, no
sheets and no way to reach one.

ZERO OF THE AUTHOR'S 90 STORED SHEETS CARRY THE KEY, measured read-only
2026-08-25, so nothing about this path fires on any existing scene. It is
authoring capacity, and the `interior_note` fragment on the generation and
AI-reinterpretation surfaces is what makes it reachable rather than
permanently empty.

NOT ON THE PERSONA. The stamper walks the cast; a player persona is not in it,
so the field would have no reader there -- and a declared field nothing reads
is the failure this repo deleted 29 schema models over. Asserted below, so a
later reader cannot appear without the field appearing with it.
"""

from __future__ import annotations

import copy
import inspect
import json
import time

import persist.commit_scene_state as commit_scene_state
from agents.common import stamp_authored_interiors
from story.character_schema import (
    INTERIOR_STATIONS_MAX,
    character_body_interior,
    character_card_warnings,
    default_persona_data,
    normalize_character_data,
    normalize_persona_data,
)
from web import app
from world.spatial import _dedup_duplicate_entity_keys, merge_scene_with_diff

HOLDER = "Reya"
HOLDER_ID = "reya_entity"
OCCUPANT = "Wren"

STATIONS = [
    {"name": "Entry Passage", "desc": "A close, yielding passage just within "
                                      "the way in.", "light": "dark"},
    {"name": "Middle Chamber", "desc": "It widens here.", "light": "dark",
     "barrier": "membrane"},
    {"name": "Deep Hold", "desc": "The furthest the inside goes."},
]


def _sheet(interior=None, name=HOLDER, aliases=()):
    sheet = {"identity": {"name": name, "aliases": list(aliases)},
             "embodiment": {"visible": {"summary": "A tall woman."}}}
    if interior is not None:
        sheet["embodiment"]["interior"] = interior
    return sheet


def _cast(*sheets):
    return [{"sheet": json.dumps(s)} for s in sheets]


def _scene(entities=None):
    return {
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {HOLDER: "hall", OCCUPANT: "hall"},
        "entities": entities if entities is not None else {
            HOLDER_ID: {"name": HOLDER, "kind": "person", "aliases": []}},
        "attire": {HOLDER: {}, OCCUPANT: {}},
        "scales": {OCCUPANT: 0.05},
        "contained": {},
        "contacts": [],
    }


class TestNormalization:
    def test_a_dict_station_keeps_its_four_authored_fields(self):
        stations = character_body_interior(_sheet(STATIONS))
        assert [s["name"] for s in stations] == [
            "Entry Passage", "Middle Chamber", "Deep Hold"]
        assert stations[1]["desc"] == "It widens here."
        assert stations[1]["light"] == "dark"
        assert stations[1]["barrier"] == "membrane"

    def test_a_bare_string_list_is_a_linear_tract(self):
        stations = character_body_interior(
            _sheet(["Entry Passage", "Deep Hold"]))
        assert [s["name"] for s in stations] == ["Entry Passage", "Deep Hold"]
        assert all(s["desc"] == "" and s["barrier"] == "" for s in stations)

    def test_a_nameless_station_is_dropped(self):
        stations = character_body_interior(
            _sheet([{"name": "Entry Passage"}, {"desc": "nowhere"}, "   ",
                    {"name": "Deep Hold"}]))
        assert [s["name"] for s in stations] == ["Entry Passage", "Deep Hold"]

    def test_the_list_is_capped(self):
        stations = character_body_interior(
            _sheet([{"name": "Station %d" % n} for n in range(12)]))
        assert len(stations) == INTERIOR_STATIONS_MAX

    def test_a_long_description_is_capped_like_a_part_description(self):
        stations = character_body_interior(
            _sheet([{"name": "Entry Passage", "desc": "x" * 900}]))
        assert len(stations[0]["desc"]) == 400

    def test_a_sheet_without_the_section_normalizes_to_nothing(self):
        assert character_body_interior(_sheet()) == []
        assert normalize_character_data(_sheet())["embodiment"]["interior"] == []

    def test_junk_is_tolerated_rather_than_raising(self):
        for junk in ("a string", 7, {"Entry Passage": {"desc": "in"}}, None):
            assert isinstance(character_body_interior(_sheet(junk)), list)

    def test_the_keyed_spelling_a_model_writes_reads_as_a_chain(self):
        stations = character_body_interior(
            _sheet({"Entry Passage": {"desc": "close"},
                    "Deep Hold": {"light": "dark"}}))
        assert [s["name"] for s in stations] == ["Entry Passage", "Deep Hold"]


class TestThePersonaHasNoSuchField:
    """Absent BY DESIGN, and pinned so it cannot appear un-argued."""

    def test_the_persona_schema_declares_no_interior(self):
        assert "interior" not in default_persona_data("Player")["embodiment"]

    def test_a_persona_sheet_carrying_one_is_never_normalized(self):
        """It survives, as every unknown card key survives -- untouched, in
        the author's own shape, read by nothing. That is the tell: the
        character path returns four normalized fields per station and this
        path returns whatever was typed, because no reader exists to shape it
        for."""
        authored = [{"name": "Entry Passage", "unknown": 1}]
        persona = normalize_persona_data(
            {"identity": {"name": "Player"},
             "embodiment": {"interior": copy.deepcopy(authored)}})
        assert persona["embodiment"]["interior"] == authored

    def test_there_is_no_persona_accessor(self):
        import story.character_schema as schema
        assert not hasattr(schema, "persona_interior")
        assert not hasattr(schema, "persona_body_interior")


class TestTheWarning:
    def test_a_nameless_station_is_named_to_the_author(self):
        found = [w for w in character_card_warnings(
            _sheet([{"name": "Entry Passage"}, {"desc": "nowhere"}]))
            if "embodiment.interior" in w]
        assert found and "position 2" in found[0]

    def test_an_overlong_list_is_reported(self):
        found = [w for w in character_card_warnings(
            _sheet([{"name": "S%d" % n} for n in range(12)]))
            if "embodiment.interior" in w]
        assert found and "12" in found[0]

    def test_a_well_formed_interior_is_quiet(self):
        assert not [w for w in character_card_warnings(_sheet(STATIONS))
                    if "embodiment.interior" in w]

    def test_an_ordinary_card_with_no_interior_is_quiet(self):
        assert not [w for w in character_card_warnings(_sheet())
                    if "embodiment.interior" in w]


class TestTheStamper:
    def test_the_spec_lands_on_the_one_entity_that_is_that_sheet(self):
        scene = _scene()
        assert stamp_authored_interiors(scene, _cast(_sheet(STATIONS))) == \
            [HOLDER_ID]
        stamped = scene["entities"][HOLDER_ID]["interior_spec"]
        assert [s["name"] for s in stamped] == [
            "Entry Passage", "Middle Chamber", "Deep Hold"]

    def test_it_resolves_through_an_alias_the_scene_uses(self):
        scene = _scene({HOLDER_ID: {"name": "Dr. Reya", "kind": "person",
                                    "aliases": []}})
        assert stamp_authored_interiors(
            scene, _cast(_sheet(STATIONS, aliases=["Dr. Reya"]))) == [HOLDER_ID]
        assert scene["entities"][HOLDER_ID]["interior_spec"]

    def test_a_sheet_with_no_interior_adds_no_key(self):
        scene = _scene()
        assert stamp_authored_interiors(scene, _cast(_sheet())) == []
        assert "interior_spec" not in scene["entities"][HOLDER_ID]

    def test_two_entities_claiming_one_sheet_stamp_neither(self):
        """The same rule `reconcile_cast_entity_names` follows: folding two
        beings into one is strictly worse than leaving two spellings of one."""
        scene = _scene({
            HOLDER_ID: {"name": HOLDER, "kind": "person", "aliases": []},
            "reya_twin": {"name": HOLDER, "kind": "person", "aliases": []},
        })
        assert stamp_authored_interiors(scene, _cast(_sheet(STATIONS))) == []
        assert all("interior_spec" not in e
                   for e in scene["entities"].values())

    def test_it_touches_nothing_else_on_the_scene(self):
        scene = _scene()
        before = copy.deepcopy(scene)
        stamp_authored_interiors(scene, _cast(_sheet(STATIONS)))
        scene["entities"][HOLDER_ID].pop("interior_spec")
        assert scene == before

    def test_a_second_call_is_a_no_op(self):
        scene = _scene()
        cast = _cast(_sheet(STATIONS))
        stamp_authored_interiors(scene, cast)
        snapshot = copy.deepcopy(scene)
        assert stamp_authored_interiors(scene, cast) == []
        assert scene == snapshot

    def test_an_emptied_card_section_is_not_a_retraction(self):
        """Clearing a sheet field says nothing about a body already standing
        inside one, so the stamp is never deleted."""
        scene = _scene()
        stamp_authored_interiors(scene, _cast(_sheet(STATIONS)))
        assert stamp_authored_interiors(scene, _cast(_sheet([]))) == []
        assert scene["entities"][HOLDER_ID]["interior_spec"]


class TestTheSpecSurvivesTheMerge:
    def test_a_collapsed_entity_twin_keeps_its_topology(self):
        """`_ENTITY_STRUCTURAL_FIELDS`, asserted rather than assumed. A record
        keyed by id and one keyed by display name is the shape this corpus
        produces routinely, and a new entity key not listed there is dropped
        when the two collapse."""
        entities = {
            HOLDER_ID: {"name": HOLDER, "kind": "person",
                        "interior_spec": [{"name": "Entry Passage",
                                           "desc": "", "light": "",
                                           "barrier": ""}]},
            HOLDER: {"name": HOLDER, "kind": "person"},
        }
        collapsed = _dedup_duplicate_entity_keys(entities)
        survivor = [e for e in collapsed.values() if isinstance(e, dict)]
        assert len(survivor) == 1
        assert survivor[0]["interior_spec"][0]["name"] == "Entry Passage"

    def test_the_authored_rooms_are_minted_not_the_fallback(self):
        scene = _scene()
        stamp_authored_interiors(scene, _cast(_sheet(STATIONS)))
        merged = merge_scene_with_diff(
            scene, {"containment": {OCCUPANT: {"in": HOLDER_ID,
                                               "mode": "interior"}}})
        interiors = {rid for rid, room in merged["rooms"].items()
                     if room.get("parent_entity") == HOLDER_ID}
        assert interiors == {HOLDER_ID + "_entry_passage",
                             HOLDER_ID + "_middle_chamber",
                             HOLDER_ID + "_deep_hold"}
        assert HOLDER_ID + "_interior" not in merged["rooms"]
        assert merged["positions"][OCCUPANT] == HOLDER_ID + "_entry_passage"


def test_the_commit_stamps_both_scopes_beside_the_identity_reconcile():
    """WIRING, in the repo's existing shape. The stamp has to happen on the
    standing scene AND on this beat's diff, before `merge_scene_with_diff`
    reads either -- a holder the Director minted this beat has no stamp
    otherwise, and the merge has no cast to ask."""
    source = inspect.getsource(commit_scene_state)
    loop = source.split("for _scope in (prev_scene, diff):", 1)[1]
    body = loop.split("sc = merge_scene_with_diff(", 1)[0]
    assert "stamp_authored_interiors(" in body


def test_an_authored_interior_survives_an_archive_round_trip(temp_db):
    """Both keys ride blobs the archive already carries whole -- the sheet in
    `chat_chars.sheet`, the stamp in the `world` scene row -- so this asserts
    the inheritance rather than trusting it."""
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Interior source", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
        (HOLDER, json.dumps(_sheet()), time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,sheet) VALUES(?,?,?)",
               (cid, char_id, json.dumps(_sheet(STATIONS))))
    scene = _scene()
    scene["entities"][HOLDER_ID]["interior_spec"] = \
        character_body_interior(_sheet(STATIONS))
    temp_db.wset(cid, "scene", json.dumps(scene))

    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(cid)})
    icid = imported["id"] if isinstance(imported, dict) else imported

    row = temp_db.q("SELECT sheet FROM chat_chars WHERE chat_id=?",
                    (icid,), one=True)
    assert character_body_interior(json.loads(row["sheet"])) == \
        character_body_interior(_sheet(STATIONS))
    restored = json.loads(temp_db.wget(icid, "scene"))
    assert restored["entities"][HOLDER_ID]["interior_spec"] == \
        scene["entities"][HOLDER_ID]["interior_spec"]
