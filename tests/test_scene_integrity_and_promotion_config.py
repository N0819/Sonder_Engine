"""Findings from auditing a long live chat ("The Doctor — Hinami ⎇14 ⎇17 ⎇16 ⎇23").

That chat ran 39 turns and ended with a scene containing an exit to a room that
does not exist, plus entities keyed by opaque generated ids. Both are covered
here, along with making promotion thresholds authorial rather than fixed.
"""

from __future__ import annotations

import time

import pytest

from commit import prune_dangling_exits, promotion_thresholds
from schemas import _entity_name_from_key, validate_llm_output_strict
from scene import promotion_config


@pytest.fixture
def chat(temp_db):
    """world rows carry a FK to chats, so a real chat row has to exist."""
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Hinami", "", time.time()))


# --- dangling exits --------------------------------------------------------

def test_exit_to_undefined_room_is_dropped():
    """The real shape found live: the janitor closet carried an exit to
    `enterprise_corridor` while only `enterprise_corridor_deck10` and
    `_deck14` existed. The merge only ever pruned edges to rooms it had just
    REMOVED, so a room the model never defined survived as a permanent exit."""
    sc = {"rooms": {
        "enterprise_janitor_closet": {"adjacent": [
            {"to": "enterprise_corridor", "barrier": "closed_door"},
            {"to": "enterprise_corridor_deck14", "barrier": "open"},
        ]},
        "enterprise_corridor_deck14": {"adjacent": []},
    }}
    warnings = prune_dangling_exits(sc)
    kept = [e["to"] for e in sc["rooms"]["enterprise_janitor_closet"]["adjacent"]]
    assert kept == ["enterprise_corridor_deck14"]
    assert warnings and "enterprise_corridor" in warnings[0]


def test_valid_scene_is_untouched_and_silent():
    sc = {"rooms": {
        "a": {"adjacent": [{"to": "b"}]},
        "b": {"adjacent": [{"to": "a"}]},
    }}
    assert prune_dangling_exits(sc) == []
    assert len(sc["rooms"]["a"]["adjacent"]) == 1


def test_malformed_scene_does_not_raise():
    assert prune_dangling_exits({}) == []
    assert prune_dangling_exits({"rooms": "nonsense"}) == []
    assert prune_dangling_exits({"rooms": {"a": {"adjacent": "nope"}}}) == []
    assert prune_dangling_exits({"rooms": {"a": {"adjacent": [None, 7]}}}) == []


# --- opaque entity ids -----------------------------------------------------

@pytest.mark.parametrize("key", ["10ae6b6a11324780", "41b518dc08c3436f",
                                 "8942820c2de9410e"])
def test_opaque_ids_derive_no_name(key):
    """Real keys from that chat. Title-casing one yields "10Ae6B6A11324780",
    which would be shown to the player and used as a lookup key."""
    assert _entity_name_from_key(key) == ""


def test_opaque_id_entity_falls_back_to_kind_not_hex():
    """It must still validate -- failing the turn over a missing name is the
    bug alpha4.0.2 fixed -- but the fallback has to be honest."""
    raw = {"resolved_event": "The TARDIS hums.",
           "state_diff": {"entities": {
               "10ae6b6a11324780": {"kind": "vehicle"},
               "41b518dc08c3436f": {}}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.valid, report.errors
    entities = report.output["state_diff"]["entities"]
    assert entities["10ae6b6a11324780"]["name"] == "Vehicle"
    assert entities["41b518dc08c3436f"]["name"] == "Object"


def test_semantic_keys_still_derive_properly():
    assert _entity_name_from_key("sake_carafe") == "Sake Carafe"
    assert _entity_name_from_key("guinan_entity") == "Guinan"


# --- promotion thresholds as authorial settings ----------------------------

def test_defaults_match_the_historical_constants(temp_db, chat):
    import commit
    cid = chat
    limits = promotion_config(cid)
    assert limits["dialogue"] == commit.BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD
    assert limits["mention"] == commit.BACKGROUND_PROMOTION_MENTION_THRESHOLD
    assert limits["auto_dialogue"] == commit.AUTO_PROMOTE_DIALOGUE_THRESHOLD


def test_thresholds_are_overridable_per_chat(temp_db, chat):
    temp_db.wset(chat, "promotion_thresholds",
                 {"dialogue": 6, "mention": 10, "auto_dialogue": 8})
    limits = promotion_config(chat)
    assert (limits["dialogue"], limits["mention"], limits["auto_dialogue"]) \
        == (6, 10, 8)
    assert promotion_thresholds(chat)["dialogue"] == 6


def test_partial_override_keeps_other_defaults(temp_db, chat):
    import commit
    temp_db.wset(chat, "promotion_thresholds", {"dialogue": 9})
    limits = promotion_config(chat)
    assert limits["dialogue"] == 9
    assert limits["mention"] == commit.BACKGROUND_PROMOTION_MENTION_THRESHOLD


def test_nonsense_values_fall_back_rather_than_break_promotion(temp_db, chat):
    import commit
    temp_db.wset(chat, "promotion_thresholds",
                 {"dialogue": "loads", "mention": None})
    limits = promotion_config(chat)
    assert limits["dialogue"] == commit.BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD
    assert limits["mention"] == commit.BACKGROUND_PROMOTION_MENTION_THRESHOLD


def test_thresholds_are_clamped_to_something_reachable(temp_db, chat):
    """A zero would promote everyone instantly; a huge value would read as
    'promotion is broken'."""
    temp_db.wset(chat, "promotion_thresholds", {"dialogue": 0, "mention": 9999})
    limits = promotion_config(chat)
    assert limits["dialogue"] == 1
    assert limits["mention"] == 50


def test_raised_threshold_actually_suppresses_promotion(temp_db, chat):
    """End-to-end through the real reader, not just the config helper."""
    from commit import promotable_background_presences
    temp_db.wset(chat, "background_presences",
                 {"Guinan": {"dialogue_turns": [1, 2], "mention_turns": []}})
    assert promotable_background_presences(chat)[0]["promotable"] is True
    temp_db.wset(chat, "promotion_thresholds", {"dialogue": 5})
    assert promotable_background_presences(chat)[0]["promotable"] is False
