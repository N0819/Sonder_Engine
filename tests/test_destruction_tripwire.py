"""Regression tests for the destruction reconciliation tripwire.

Observed live (chat 26, the Emberhold razing): director_resolve's
resolved_event narrated a whole-town firestorm consuming a named region
and its wards, but state_diff.destruction was null and remove_rooms empty
-- so the Phase-3b cascade (which only realizes a DECLARED destruction)
never fired and the town stayed objectively intact against the prose,
with no warning anywhere.

_narrated_destruction_subjects is the deterministic, warn-only safety net:
it flags a named, KNOWN place (scene room, scene location, interior-
bearing entity, live lorebook name) appearing in a destruction-shaped
grammatical position in the prose while the diff encodes neither
destruction nor a covering removal. It must NOT fire on ordinary fire/
damage flavor or on an object being destroyed IN a room, and it never
mutates the diff -- warnings only (a wrongly-invented razing would be far
worse than a stale-missing one).
"""

import json
import time

import agents.director as director
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _scene():
    return {
        "location": "Emberhold",
        "time": "night",
        "rooms": {
            "market_ward": {"name": "Market Ward", "adjacent": []},
            "temple_ward": {"name": "Temple Ward", "adjacent": []},
            "harbor_row": {"name": "Harbor Row", "adjacent": []},
        },
        "positions": {"The Stranger": "market_ward"},
        "entities": {
            "elevator": {
                "name": "the elevator", "kind": "vehicle", "aliases": [],
                "interior_rooms": ["elevator_interior"], "state": {},
            },
        },
        "attire": {},
        "overlays": {},
    }


def _empty_sd(**over):
    sd = {"positions": {}, "rooms": {}, "entities": {}, "conditions": {},
          "attire": {}, "overlays": {}, "remove_rooms": [],
          "remove_entities": [], "remove_adjacent": [], "inventory_ops": [],
          "cast_changes": [], "world_facts": [], "introductions": [],
          "claim_dispositions": [], "time": None, "destruction": None}
    sd.update(over)
    return sd


# ---- unit level: the detector itself -------------------------------------

def test_flags_named_region_and_ward_destruction():
    prose = ("The firestorm consumed Emberhold ward by ward. By dawn the "
             "Market Ward was razed to its foundations.")
    flagged = director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene())
    assert "Emberhold" in flagged
    assert "Market Ward" in flagged


def test_no_false_positive_on_ordinary_fire_flavor():
    prose = ("The fire spread along the rooftops of the Market Ward as "
             "sparks drifted over Harbor Row. Smoke filled Emberhold's "
             "narrow streets.")
    assert director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene()) == []


def test_no_false_positive_on_object_destroyed_inside_a_room():
    prose = "The ledger was destroyed in the Market Ward before anyone read it."
    assert director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene()) == []


def test_declared_destruction_suppresses_the_scan():
    prose = "The firestorm consumed Emberhold ward by ward."
    sd = _empty_sd(destruction={"target_id": "emberhold", "scale": "region",
                                "kind": "fire", "news": []})
    assert director._narrated_destruction_subjects(prose, [], sd, _scene()) == []


def test_remove_rooms_covers_a_single_razed_room():
    prose = "The Market Ward was razed; the rest of the town stood untouched."
    sd = _empty_sd(remove_rooms=["market_ward"])
    assert director._narrated_destruction_subjects(prose, [], sd, _scene()) == []


def test_entity_destruction_flagged_and_covered_by_remove_entities():
    prose = "The rockslide flattened the elevator against the shaft wall."
    assert "the elevator" in director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene())
    sd = _empty_sd(remove_entities=["elevator"])
    assert director._narrated_destruction_subjects(prose, [], sd, _scene()) == []


def test_lorebook_names_are_matched_via_extra_names():
    prose = "Nothing was left of the Ashen Quarter when the flames died."
    flagged = director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene(), extra_names=["Ashen Quarter"])
    assert flagged == ["Ashen Quarter"]


# ---- end-to-end: the warning through director_resolve --------------------

def _make_ctx(temp_db, scene):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", scene)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "look", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="look", created=time.time()),
        cast=cast,
        input="look",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx


def test_resolve_warns_when_narrated_razing_is_not_encoded(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, _scene())
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {
            "resolved_event": ("The firestorm consumed Emberhold ward by "
                               "ward; by dawn the Market Ward was razed."),
            "dialogue_log": [],
            "state_diff": {},
        },
    )

    out = director.director_resolve(ctx, nonce=0)

    assert any("Possible unencoded destruction" in w for w in ctx.warnings)
    assert "Emberhold" in out["reconciliation"]["destruction_scan"]
    # Warn-only: the detector must never fabricate objective state.
    assert out["state_diff"].get("destruction") is None
    assert out["state_diff"]["remove_rooms"] == []


def test_resolve_stays_silent_when_destruction_is_declared(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, _scene())
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {
            "resolved_event": ("The firestorm consumed Emberhold ward by "
                               "ward; by dawn the Market Ward was razed."),
            "dialogue_log": [],
            "state_diff": {
                "destruction": {"target_id": "emberhold", "scale": "region",
                                "kind": "fire", "news": []},
                "positions": {"The Stranger": "refugee_road"},
                "rooms": {"refugee_road": {"name": "Refugee Road",
                                           "adjacent": []}},
            },
        },
    )

    out = director.director_resolve(ctx, nonce=0)

    assert not [w for w in ctx.warnings
                if "Possible unencoded destruction" in w]
    assert out["reconciliation"]["destruction_scan"] == []


def test_resolve_stays_silent_on_ordinary_prose(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, _scene())
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {
            "resolved_event": ("Mara crossed the Market Ward while the fire "
                               "spread along distant rooftops."),
            "dialogue_log": [],
            "state_diff": {},
        },
    )

    director.director_resolve(ctx, nonce=0)

    assert not [w for w in ctx.warnings
                if "Possible unencoded destruction" in w]
