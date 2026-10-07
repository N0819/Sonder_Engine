"""A charter voice is handed words, never the engine's keys.

`presence_view` relabelled the scene's figures for the observer and passed
the institution's own members, posts and happenings through as the engine
spells them. Measured (scratch story 165, 2026-10-06, turns 4581-4582): every
voice of an inn was handed three `{"what": "body_recovered", "about":
"keeper:0001"}` -- the keeper back on his feet after a night's rest -- and in a
story of a sunk barge and a search bell, each of them read it as corpses:

    "I've pulled three bodies out of this water in two days."   (the keeper)
    "Three out of the water, twelve hours gone. Keeper's the one pulled them."
    "Keeper's not here. Hasn't been, since before noon."

The Writers' Room's canon held no deaths. The slice now says what happened in
the sentence it is retold in, calls a member by name only where this body
knows them and by its post otherwise, and carries no record id.
"""

import json

from tests.test_a_charter_body_speaks_before_the_director_resolves import _chat
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import (carrier_entries, known_members,
                                   presence_view, save_registry)

KEEPER, HAND = "keeper:0001", "house_hand:0002"
NEWS = "news:body_recovered:%s@100.0000" % KEEPER


def _inn(*, keeper_knows_hand=False):
    charter = normalize_charter({
        "key": "inn",
        "upkeeps": {"house": {"place": "taproom", "level": 0.8, "floor": 0.3,
                              "drift_per_hour": 0.01, "service_per_hour": 0.1}},
        "posts": {"keeper": {"place": "taproom", "serves": ["house"]},
                  "house_hand": {"place": "taproom", "serves": ["house"]}},
        "bodies": {KEEPER: {"place": "taproom", "name": "Fetoard Hollelwick",
                            "home_post": "keeper"},
                   HAND: {"place": "taproom", "name": "Niboold Moorelcroft",
                          "home_post": "house_hand"}},
        "priority": ["house"],
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    charter["watch"] = {}
    charter["clock_hours"] = 112.1
    recovered = {"kind": "news", "body": NEWS, "event_kind": "body_recovered",
                 "about": KEEPER, "place": "taproom", "happened_at": 100.0,
                 "strength": 1.0, "heard_from": None}
    charter["minds"] = {HAND: {NEWS: dict(recovered)},
                        KEEPER: {NEWS: dict(recovered)}}
    if keeper_knows_hand:
        charter["minds"][KEEPER][HAND] = {
            "kind": "body", "believed_available": True, "strength": 0.9}
    charter["decisions"] = {"agenda": [{
        "about": KEEPER, "at_post": "house_hand", "event_kind": "body_recovered",
        "evidence_id": NEWS, "held_by": HAND, "source": "", "strength": 1.0}]}
    charter["judgments"] = {KEEPER: {HAND: {
        "trust": 0.6, "warmth": 0.5, "respect": 0.3, "fear": 0.0,
        "suspicion": 0.0,
        "reasons": [{"evidence_id": "news:aid_given:%s@%d.0000" % (HAND, h),
                     "signal": "aid_given", "source": "", "weight": 0.98}
                    for h in (80, 90, 95)]}}}
    return charter


def _slice(cid, name):
    view = presence_view(cid, "taproom", name)
    assert view, name
    return view[0]["presence"]


def test_no_key_of_the_engine_reaches_the_voice(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn()})
    for name in ("Niboold Moorelcroft", "Fetoard Hollelwick"):
        text = json.dumps(_slice(cid, name))
        for key in (KEEPER, HAND, "body_recovered", "aid_given",
                    "evidence_id", "news:"):
            assert key not in text, (name, key)


def test_a_happening_is_the_sentence_it_is_retold_in(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn()})
    hand = _slice(cid, "Niboold Moorelcroft")
    news = hand["can_bring_up"][0]
    assert news["claim"] == "the keeper recovered enough to continue at taproom"
    assert news["about"] == "the keeper", (
        "a house hand holding no claim about the keeper knows him by his post")
    assert hand["institutional"]["agenda"][0]["claim"] == (
        "the keeper recovered enough to continue")
    keeper = _slice(cid, "Fetoard Hollelwick")
    assert keeper["can_bring_up"][0]["claim"].startswith(
        "Fetoard Hollelwick recovered"), "of himself, by his own name"


def test_a_colleague_is_named_only_where_this_body_knows_him(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn()})
    keeper = _slice(cid, "Fetoard Hollelwick")
    assert keeper["strangers_here"] == ["the house hand"]
    assert keeper["social_judgments"][0]["subject"] == "the house hand"
    assert keeper["social_judgments"][0]["reasons"] == ["aid given (3 times)"]

    save_registry(cid, {"inn": _inn(keeper_knows_hand=True)})
    keeper = _slice(cid, "Fetoard Hollelwick")
    assert "Niboold Moorelcroft" in keeper["knows_here"]
    assert keeper["social_judgments"][0]["subject"] == "Niboold Moorelcroft"
    assert known_members(cid, [{"charter": "inn", "body": KEEPER}]) == {
        ("inn", KEEPER), ("inn", HAND)}
    assert known_members(cid, [{"charter": "inn", "body": HAND}]) == {
        ("inn", HAND)}, "his house hand holds no claim about him"


def test_the_carrier_rail_gist_is_the_holders_own_wording(temp_db):
    """`carrier_entries` minted every native gist from the raw subject: the
    Director and the encoder were handed 204 of "warden:0001 became unable to
    continue at chapel" a call, and a registered character told one kept the
    key as what it heard."""
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn()})
    entries = {e["uid"]: e for e in carrier_entries(cid)}
    assert [r["claim"] for r in entries[HAND]["state"]["carried_reports"]] == [
        "the keeper recovered enough to continue at taproom"]
    assert entries[KEEPER]["state"]["carried_reports"][0]["claim"] == (
        "Fetoard Hollelwick recovered enough to continue at taproom")
