"""A thing a beat acted on and the world does not hold must become one.

THE HOLE, and the engine reports it itself. The contact hand's own sheet
says: resolve the target against `entity_names`, "or request the channel that
owns its record; otherwise mark the unresolved item no_referent and explain
the missing referent." It does exactly that. Nothing anywhere answers the
"otherwise".

Measured (Aldermill, two causality bubbles, 2026-09-19, second run): 29 of 93
specialist results came back `no_referent`, every transform on them dropped.
Emory Vane spent twenty-three consecutive beats working a sluice gate --

    t5   settled {"timber frame of the sluice gate": "no_referent"}
    t11  settled {"sluice gate": "no_referent"}
    t13  settled {"packed grit and small stones": "no_referent"}
    t15  settled {"wooden sluice gate": "no_referent"}

-- and `scene.entities` in his frame held exactly one record: himself. He was
working a gate the engine does not model, so `contact_ops` had nothing to hang
a contact on, nothing committed, nothing was perceived, and his next appraisal
had no evidence that anything had happened. Sixty beats over two runs produced
three changes to the world.

THE PRECEDENT IS THE PERSON PATH. `commit_background.track_background_presences`
takes a person the Director wrote into a beat who has no record and mints
durable bookkeeping from STRUCTURED FIELDS ONLY -- never NER over prose -- and
`planning_needs.NEED_KINDS` already carries "thing" beside "person" and "room".
A person the world did not plan gets a record; a thing the world did not plan
was dropped. This is the missing half, and it reads the same kind of field:
`settled`, which is typed, not prose.
"""

import agents.director as director


def _orchestration(settled):
    return {"specialists": {"contact": {"run": True, "results": [
        {"status": "no_referent", "transforms": [], "settled": settled}]}}}


def test_an_unheld_thing_is_minted_into_the_beat():
    scene = {"rooms": {"mill_race": {"name": "Mill Race and Sluice"}},
             "entities": {"char_emory": {"name": "Emory Vane", "kind": "person"}},
             "positions": {"Emory Vane": "mill_race"}}
    out = {"orchestration": _orchestration({"sluice gate": "no_referent"})}
    diff = {}
    minted = director.mint_unreferenced_things(out, scene, diff, "mill_race")

    assert minted, "a thing the beat reached for and the world lacks must be minted"
    key = minted[0]
    assert diff["entities"][key]["name"] == "sluice gate"
    assert diff["entities"][key]["kind"] == "fixture", (
        "an inert kind, so the person-tracking path never treats it as somebody")
    assert diff["positions"][key] == "mill_race", (
        "the thing stands where the beat that reached for it happened")


def test_a_thing_the_world_already_holds_is_not_minted_twice():
    scene = {"rooms": {"mill_race": {}},
             "entities": {"sluice_gate": {"name": "sluice gate",
                                          "kind": "fixture",
                                          "aliases": ["the gate"]}},
             "positions": {"sluice_gate": "mill_race"}}
    for spelling in ("sluice gate", "the sluice gate", "the gate", "sluice_gate"):
        diff = {}
        out = {"orchestration": _orchestration({spelling: "no_referent"})}
        assert not director.mint_unreferenced_things(
            out, scene, diff, "mill_race"), spelling
        assert not diff.get("entities")


def test_a_body_is_never_minted_as_a_fixture():
    """`settled` named "Emory Vane" no_referent on two live beats. A hand
    failing to resolve a PERSON is a different fault and must not answer it by
    standing a second copy of them in the room as furniture."""
    scene = {"rooms": {"mill_race": {}},
             "entities": {"char_emory": {"name": "Emory Vane", "kind": "person"}},
             "positions": {"Emory Vane": "mill_race"}}
    diff = {}
    out = {"orchestration": _orchestration({"Emory Vane": "no_referent"})}
    assert not director.mint_unreferenced_things(out, scene, diff, "mill_race")
    assert not diff.get("entities")


def test_only_no_referent_mints():
    """`not_mine` means another hand owns it, not that it is absent."""
    scene = {"rooms": {"mill_race": {}}, "entities": {}, "positions": {}}
    diff = {}
    out = {"orchestration": _orchestration({"sluice gate": "not_mine"})}
    assert not director.mint_unreferenced_things(out, scene, diff, "mill_race")
    assert not diff.get("entities")


def test_a_sentence_is_not_the_name_of_a_thing():
    """The same floor `planning_needs` puts under a subject: a hand explaining
    itself at length has not named something anybody can stand in a room."""
    scene = {"rooms": {"mill_race": {}}, "entities": {}, "positions": {}}
    diff = {}
    sentence = ("the packed grit and small stones wedged hard into the "
                "submerged runner groove beneath the waterline")
    out = {"orchestration": _orchestration({sentence: "no_referent"})}
    assert not director.mint_unreferenced_things(out, scene, diff, "mill_race")


def test_the_room_is_the_one_the_beat_happened_in():
    """`_beat_room` reads the beat's own ledger actors, not the player: a
    bubble's beat has no player and the body acting is the only body there."""
    scene = {"positions": {"Emory Vane": "mill_race"}}
    out = {"ledgers": [{"object_name": "Emory Vane", "item_names": ["Emory Vane"]}]}
    assert director._beat_room(out, scene) == "mill_race"


def test_two_rooms_mint_nothing():
    """A thing stood in the wrong room is perceivable by the wrong people,
    and presence and channel have to be two readings of one world."""
    scene = {"positions": {"Emory Vane": "mill_race", "Sal Weatherby": "inn"}}
    out = {"ledgers": [{"object_name": "Emory Vane"},
                       {"object_name": "Sal Weatherby"}]}
    assert director._beat_room(out, scene) == ""

    diff = {}
    out["orchestration"] = _orchestration({"sluice gate": "no_referent"})
    assert not director.mint_unreferenced_things(
        out, scene, diff, director._beat_room(out, scene))
