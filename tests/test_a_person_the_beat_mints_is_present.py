"""A person the beat mints is present on the beat that mints them.

Found in play on 2026-10-06 (scratch story 165, turn 4581). The player walked
to "the man by the fire who has the look of a ledger about him", said "Mr
Petch? Coyle, River Underwriters." and asked him for the guild's books. The
encoder minted him -- `entities.petch`, a person at the hearth -- and he
could not answer. The presence ledger is written at commit, so every reader
before it built "who is here" from a store one beat behind the scene:

* the figures voiced before resolve (`lay_charter_figures`) came from the
  ledger and the charters, so he was never asked, and the innkeeper answered
  for him, offering to fetch the guild's manifest himself;
* the descriptor binder read `petch` and the room id `inn_common` as
  descriptions and dealt them, by seed, to the house hand and the innkeeper,
  who were each left owing a reply nobody asked of them;
* the demand gate counted every name minted in `state_diff.entities` as
  already voiced -- a rule from when the Director wrote every line it minted
  a speaker for -- so even a later beat that re-declared him muted him.

One rule, `commit_background.scene_person_entities`, read by the same
predicate commit files a presence by.
"""

from __future__ import annotations

from agents import background
from agents.common import lay_charter_figures
from persist.commit import (descriptor_bindings, person_entity_named,
                            pick_voice_demand, scene_person_entities)
from tests.test_a_charter_body_speaks_before_the_director_resolves import \
    _chat, _ctx
from tests.test_background_description_address import ROOM, _make_ctx

PETCH = {"name": "Mr Petch", "kind": "person",
         "description": "a man seated by the fire with the look of a ledger "
                        "about him",
         "aliases": ["Petch", "Mr Petch", "the man by the fire"],
         "portable": False}
LANTERN = {"name": "a brass storm lantern", "kind": "lantern",
           "description": "brass, burning", "portable": True}


def _stage():
    return {"rooms": {"taproom": {"name": "Taproom", "adjacent": []},
                      "walk": {"name": "Walk", "adjacent": []}},
            "positions": {"Tamsin Coyle": "taproom", "petch": "taproom",
                          "lantern": "taproom"},
            "entities": {"petch": dict(PETCH), "lantern": dict(LANTERN)}}


def test_the_beats_people_are_read_by_the_rule_commit_files_them_by():
    people = scene_person_entities(_stage(), roster={"tamsin coyle"})
    assert set(people) == {"Mr Petch"}, "a lantern is a thing, not a person"
    assert people["Mr Petch"]["entity_id"] == "petch"
    assert people["Mr Petch"]["room"] == "taproom"
    for ref in ("petch", "Mr Petch", "the man by the fire"):
        assert person_entity_named(people, ref) == "Mr Petch", ref
    assert person_entity_named(people, "the innkeeper") == ""


def test_a_person_minted_in_view_is_laid_as_a_figure(temp_db):
    cid = _chat(temp_db)
    sc = _stage()
    rows = lay_charter_figures(_ctx(cid), sc, ["taproom", "walk"])
    assert [r["name"] for r in rows] == ["Mr Petch"]
    assert rows[0]["entity_id"] == "petch" and rows[0]["room"] == "taproom"
    assert "ledger" in rows[0]["appearance"]


def test_the_minted_person_is_asked_and_knows_he_was_addressed(
        monkeypatch, temp_db):
    cid = _chat(temp_db)
    asked = []

    def fake_react(ctx, dr, name, present_others, roster, sc_, rec, nonce,
                   player_addressed=False):
        asked.append((name, player_addressed, rec))
        return None

    monkeypatch.setattr(background, "_react_one", fake_react)
    monkeypatch.setattr(background, "_player_room", lambda ctx, sc_: "taproom")
    interp = {"ledgers": [
        {"object_name": "Tamsin Coyle",
         "event": "Mr Petch? Coyle, River Underwriters.",
         "categories": ["speech"], "volume": "normal",
         "targets": ["petch"], "visibility": "overt"}],
        "flow": {"addressed_to_refs": []}}
    rows = [{"name": "Mr Petch", "room": "taproom", "entity_id": "petch",
             "aliases": list(PETCH["aliases"]),
             "appearance": PETCH["description"]}]
    background.declare_charter_figures(_ctx(cid), interp, _stage(), rows, [], 0)
    assert [(n, a) for n, a, _rec in asked] == [("Mr Petch", True)]
    rec = asked[0][2]
    assert rec["entity_id"] == "petch", "where he stands is found by his id"
    assert "ledger" in rec["sketch"]["role_hint"]


def test_a_name_or_a_room_the_scene_holds_is_never_dealt_to_somebody_else(
        temp_db):
    traders = {"Trader Tate": {"first_turn": 1, "last_turn": 4},
               "Trader Mira": {"first_turn": 1, "last_turn": 4}}
    resolve = {"resolved_event": "She walks to the man by the fire.",
               "dialogue_log": [],
               "state_diff": {"entities": {"petch": dict(PETCH)},
                              "positions": {"petch": ROOM}}}
    ctx = _make_ctx(temp_db, traders, addressed_refs=["petch", ROOM],
                    director_resolve=resolve)
    assert descriptor_bindings(ctx) == {}


def test_an_entity_write_is_not_a_line(temp_db):
    """A beat that re-declares a known person's entity muted him: the mint
    was counted as his having spoken."""
    presences = {"Mr Petch": {"first_turn": 3, "last_turn": 3,
                              "entity_id": "petch",
                              "sketch": {"station_room": ROOM}}}
    resolve = {"resolved_event": "She asks again.", "dialogue_log": [],
               "state_diff": {"entities": {"petch": dict(PETCH)}}}
    ctx = _make_ctx(temp_db, presences, addressed_refs=["Mr Petch"],
                    player_input="Mr Petch. The manifest, please.",
                    director_resolve=resolve)
    out = pick_voice_demand(ctx, ctx.director_resolve, cap=1)
    assert out["picks"] == ["Mr Petch"]
