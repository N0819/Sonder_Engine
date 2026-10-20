"""What a body holds or carries is the same fact to every reader -- the author
who writes about it included.

THE CASE (chats 176-178, the owner's "plates and cups"). Hinami came in out
of the rain with a towel and a mug in her hands, and later held an empty
plate. The world kept every one of them in her keeping -- `scene.contained`
-- the whole time. The prose Director never saw it: its payload carried
`standing_relations` = positions and contacts, and a thing in a hand is in
neither -- its position is DERIVED from its bearer's room, so the world index
listed it loose in whatever room she stood in, and the one hand-hold ever
written aged out of the contact ledger. So the author gave the dishes resting
places, beat after beat: "the mug stands where it was left" (176 t1), "The mug
sits where it was set down" (177 t14), "the empty small plate on the floor
near her feet" (177 t22) -- and the encoder, which IS shown `contained`,
reconciled the two accounts by filing "sets the empty small plate on the
floor" and "sets the mug on the spare room bed" as the player's own acts.

One fact, four places it went missing, each fixed where it first goes wrong:

1. THE AUTHOR'S PAYLOAD. `causal_world_index` names the keeper on a kept
   thing's row and `causal_standing_relations` carries the ledger
   (`contained`), both read through `containment_record` -- the one store.
2. THE CONTACT LEDGER'S AGEING. A hold the containment ledger still keeps does
   not age out on silence (`spatial_contacts._hold_the_containment_keeps`):
   chat 177 lost Hinami's hand on the plate between checkpoints 19 and 20
   while `contained` went on saying she held it.
3. THE VIEW. A thing in the observer's keeping is re-told in each room it is
   carried into (`composer.room_content_percepts`, `kept_in`): chat 177 said
   "You are holding an empty small plate." on turn 12 and never again through
   the walk upstairs.
4. THE OPENING. `held_by` -- how the opening puts a thing in a hand -- is
   folded into `contained` at the merge (`derive_held_by_containment`), not
   only at the commit: chat 176's opening views said "There is the towel
   here." about the towel in Hinami's hands.

The scenes are chat 177's shape, under the fixture's names: the player
("The Stranger", Hinami) also has an entity record, and the ledger spells
one record by a display name and the other's holder by the player's entity
id, exactly as checkpoints 3-12 did.
"""
from __future__ import annotations

import copy
import json

import pytest

from agents import composer, perception
import agents.director as director
from agents.director import (causal_scene_room_ids, causal_standing_relations,
                             causal_world_index)
from persist.commit import derive_borne_containment
from tests.director_fakes import _fake_agent, _make_ctx
from world.spatial import (apply_contact_ops, container_of,
                           containment_record, merge_scene_with_diff,
                           same_subject)

PLAYER = "The Stranger"
PLATE = "plate_01"
MUG = "the mug"


def _cottage(where="spare_room"):
    """The player in `where`, holding the plate and carrying the mug; Mara
    with her; a blanket loose on the bed. Chat 177 checkpoint 22's ledger:
    the mug keyed by its name with a `bearing` record from its `held_by`,
    the plate keyed by its id and held by the player's ENTITY ID."""
    return {
        "location": "The Cottage",
        "rooms": {
            "kitchen": {"name": "The Kitchen", "light": "lit",
                        "adjacent": [{"to": "landing", "barrier": "open"}],
                        "anchors": {"kitchen_table": {"desc": "a scarred deal table"}}},
            "landing": {"name": "The Landing", "light": "lit",
                        "adjacent": [{"to": "kitchen", "barrier": "open"},
                                     {"to": "spare_room", "barrier": "open"}]},
            "spare_room": {"name": "The Second Room", "light": "lit",
                           "adjacent": [{"to": "landing", "barrier": "open"}],
                           "anchors": {"spare_room_bed": {"desc": "a narrow iron bedstead"}}},
        },
        "positions": {PLAYER: where, "Mara": where, PLATE: where, MUG: where,
                      "wool_blanket": where},
        "entities": {
            "stranger_01": {"name": PLAYER, "kind": "person",
                            "description": "A young woman soaked from the rain."},
            PLATE: {"name": "an empty small plate", "kind": "object",
                    "portable": True, "container": True,
                    "description": "A small earthenware plate, empty of its scone.",
                    "aliases": ["plate", "small plate"]},
            "mug_01": {"name": MUG, "kind": "object", "portable": True,
                       "container": True, "held_by": PLAYER,
                       "description": "A heavy stoneware mug, warm through its walls."},
            "wool_blanket": {"name": "a heavy wool blanket", "kind": "object",
                             "portable": True,
                             "description": "A folded grey wool blanket."},
        },
        "contained": {
            MUG: {"in": PLAYER, "mode": "carried", "by": "bearing"},
            PLATE: {"in": "stranger_01", "mode": "held"},
        },
        "stations": {"wool_blanket": {"at": "spare_room_bed", "near": []}}
        if where == "spare_room" else {},
        "contacts": [],
        "attire": {PLAYER: {"wearing": ["travel jacket"]},
                   "Mara": {"wearing": ["apron"]}},
        "overlays": {},
    }


def _index(scene, actor=PLAYER):
    rooms = causal_scene_room_ids(scene, [actor])
    return causal_world_index(scene, here=scene["positions"][actor],
                              room_ids=rooms, include_entity_interiors=True), rooms


def _rows(index):
    return {row["id"]: row for room in index["rooms"].values()
            for row in room["holds"]}


# ---------------------------------------------------------------------------
# 1. The author's payload.
# ---------------------------------------------------------------------------

class TestTheAuthorIsShownTheHand:
    def test_a_kept_things_row_names_who_keeps_it_and_how(self):
        rows = _rows(_index(_cottage())[0])
        assert rows[PLATE]["contained"] == {"in": PLAYER, "mode": "held"}
        assert rows[MUG]["contained"] == {"in": PLAYER, "mode": "carried"}

    def test_a_thing_lying_loose_names_nobody(self):
        rows = _rows(_index(_cottage())[0])
        assert "contained" not in rows["wool_blanket"]
        assert "contained" not in rows["Mara"]

    def test_the_standing_relations_carry_the_ledger(self):
        scene = _cottage()
        index, rooms = _index(scene)
        relations = causal_standing_relations(scene, index, rooms)
        assert relations["contained"] == {
            MUG: {"in": PLAYER, "mode": "carried"},
            PLATE: {"in": PLAYER, "mode": "held"},
        }
        # positions and contacts are what they always were
        assert relations["positions"][PLATE] == "spare_room"
        assert relations["contacts"] == []

    def test_nothing_kept_is_nothing_said(self):
        """An ordinary payload stays byte-identical: no key when nobody
        keeps anything."""
        scene = _cottage()
        scene["contained"] = {}
        scene["entities"]["mug_01"].pop("held_by")
        index, rooms = _index(scene)
        assert "contained" not in causal_standing_relations(scene, index, rooms)
        assert not any("contained" in row for row in _rows(index).values())

    def test_a_record_outside_the_aperture_is_not_shown(self):
        scene = _cottage()
        scene["rooms"]["cellar"] = {"name": "Cellar", "adjacent": []}
        scene["positions"]["sack"] = "cellar"
        scene["entities"]["sack"] = {"name": "a sack", "kind": "object", "portable": True}
        scene["contained"]["sack"] = {"in": "cellar_crate", "mode": "container"}
        index, rooms = _index(scene)
        assert "sack" not in causal_standing_relations(scene, index, rooms)["contained"]

    def test_the_reader_finds_a_record_under_any_spelling(self):
        """The ledger keys the mug by its NAME and the plate by its ID, and
        spells the plate's holder by the player's entity id; `container_of`
        answers by key alone, so asked the other spelling it said nobody
        carried either."""
        scene = _cottage()
        # the keyed reader: nobody carries the mug under its id, and the
        # plate's keeper is an id no `positions` key spells
        assert container_of(scene, "mug_01") is None
        assert container_of(scene, PLATE) == "stranger_01"
        for spelling in (MUG, "mug_01", "THE MUG"):
            assert containment_record(scene, spelling) == {"in": PLAYER, "mode": "carried"}
        for spelling in (PLATE, "an empty small plate"):
            assert containment_record(scene, spelling) == {"in": PLAYER, "mode": "held"}
        assert containment_record(scene, "wool_blanket") is None

    def test_two_things_sharing_a_name_are_two_things(self):
        """The second plate on the table is not in the hand that holds the
        first: a name two entities share is nobody's spelling."""
        scene = _cottage()
        scene["entities"][PLATE]["name"] = "a plate"
        scene["entities"]["plate_02"] = {"name": "a plate", "kind": "object",
                                         "portable": True,
                                         "description": "A second plate."}
        scene["positions"]["plate_02"] = "spare_room"
        rows = _rows(_index(scene)[0])
        assert rows[PLATE]["contained"] == {"in": PLAYER, "mode": "held"}
        assert "contained" not in rows["plate_02"]
        assert containment_record(scene, "plate_02") is None
        assert containment_record(scene, "a plate") is None


def _director_payloads(temp_db, monkeypatch, scene):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "The Stranger stands in the second room."},
        "director_specialist": {"events": [], "missing_tools": [],
                                "missing_referents": [], "notes": []},
    }))
    ctx = _make_ctx(temp_db, scene=scene, player_input='"Did you want to cuddle?"')
    director.director_interpret(ctx, nonce=0)
    interpret = [c["payload"] for c in calls if c["step_key"] == "director_prose"]
    calls.clear()
    ctx = _make_ctx(temp_db, scene=scene)
    director.director_resolve(ctx, nonce=0)
    resolve = [c["payload"] for c in calls if c["step_key"] == "director_prose"]
    encoder = [c["payload"] for c in calls if c["step_key"] == "director_specialist"]
    return interpret, resolve, encoder


@pytest.mark.parametrize("where", ["kitchen", "landing", "spare_room"])
def test_the_prose_director_is_shown_who_holds_what_at_both_stages(
        temp_db, prose_director, monkeypatch, where):
    """Chat 177's checkpoints 13-14 (the kitchen: "The mug sits off to her
    right, untouched since it was poured", "The mug sits where it was set
    down"), 21 (the landing) and 22 (the second room: "the empty small plate
    on the floor near her feet, the mug ... settled on the spare room bed"):
    each payload listed a plate and a mug the player held loose in her room.
    Both stages are shown the hand now, wherever she has carried them."""
    interpret, resolve, _encoder = _director_payloads(
        temp_db, monkeypatch, _cottage(where))
    assert interpret and resolve
    for payload in (interpret[0], resolve[0]):
        kept = payload["standing_relations"]["contained"]
        assert kept[PLATE] == {"in": PLAYER, "mode": "held"}
        assert kept[MUG] == {"in": PLAYER, "mode": "carried"}
        rows = _rows(payload["world_index"])
        assert rows[PLATE]["contained"]["in"] == PLAYER
        assert rows[MUG]["contained"]["in"] == PLAYER


def test_the_encoder_finds_no_disagreement_to_reconcile(
        temp_db, prose_director, monkeypatch):
    """The encoder is shown `contained` (the objects owner's slice) AND the
    Director's own inputs. When only the first said the player held the
    plate, it "fixed" the disagreement by inventing a set-down for her
    (chat 177 turn 22). Every keeper its ledger names is now named the same
    way, in the same payload, by the author's inputs."""
    _interpret, resolve, encoder = _director_payloads(
        temp_db, monkeypatch, _cottage())
    assert encoder, "the resolve encoded nothing"
    payload = encoder[0]
    scene = _cottage()
    ledger = payload.get("contained") or {}
    assert ledger, sorted(payload)
    authored = payload["standing_relations"].get("contained") or {}
    rows = _rows(payload["world_index"])
    for thing, record in ledger.items():
        said = authored.get(thing)
        assert said is not None, thing
        assert same_subject(scene, said["in"], record["in"]), (thing, said, record)
        assert said["mode"] == record["mode"]
        assert same_subject(scene, rows[thing]["contained"]["in"], record["in"])
    assert resolve[0]["standing_relations"] == payload["standing_relations"]


# ---------------------------------------------------------------------------
# 2. Contact ageing.
# ---------------------------------------------------------------------------

def _seated_with_the_plate():
    """Chat 177 checkpoint 19, in the fixture's names: the player seated at
    the table, her hand on the plate unmentioned one beat (`unasserted: 1`),
    Mara's hand on her spoon."""
    scene = _cottage("kitchen")
    scene["positions"]["mara_spoon"] = "kitchen"
    scene["entities"]["mara_spoon"] = {"name": "a spoon", "kind": "object",
                                       "portable": True}
    scene["contained"]["mara_spoon"] = {"in": "Mara", "mode": "held"}
    scene["contacts"] = [
        {"actor": PLAYER, "actor_part": "hand", "target": PLATE,
         "target_part": "", "manner": "hold", "relation": "surface",
         "motion": "settled", "unasserted": 1},
        {"actor": "Mara", "actor_part": "hand", "target": "mara_spoon",
         "target_part": "handle", "manner": "hold", "relation": "surface",
         "motion": "settled", "unasserted": 0},
    ]
    return scene


#: Turn 19's contact talk, none of it about the player: Mara lets go of her
#: spoon and lays it on the table.
MARA_SETS_DOWN_HER_SPOON = [
    {"op": "remove", "actor": "Mara", "actor_part": "hand",
     "target": "mara_spoon", "target_part": "handle"},
    {"op": "add", "actor": "mara_spoon", "actor_part": "handle",
     "target": "kitchen_table", "target_part": "surface", "manner": "rest",
     "relation": "surface", "motion": "settled"},
]


def _holds(scene, thing):
    return [c for c in scene.get("contacts") or []
            if c.get("target") == thing and c.get("manner") == "hold"]


class TestAHoldTheContainmentKeepsDoesNotAge:
    def test_another_bodys_contact_talk_does_not_take_the_plate_out_of_her_hand(self):
        scene = apply_contact_ops(_seated_with_the_plate(),
                                  copy.deepcopy(MARA_SETS_DOWN_HER_SPOON))
        assert [c["actor"] for c in _holds(scene, PLATE)] == [PLAYER]
        assert containment_record(scene, PLATE) == {"in": PLAYER, "mode": "held"}

    def test_through_the_merge_the_two_ledgers_still_agree(self):
        """What the commit runs: the merge, ageing included."""
        scene = merge_scene_with_diff(_seated_with_the_plate(), {
            "contact_ops": copy.deepcopy(MARA_SETS_DOWN_HER_SPOON)})
        assert containment_record(scene, PLATE)["in"] == PLAYER
        assert [c["actor"] for c in _holds(scene, PLATE)] == [PLAYER]
        # and it goes on agreeing beat after beat of other talk
        for _ in range(3):
            scene = merge_scene_with_diff(scene, {"contact_ops": [
                {"op": "add", "actor": "Mara", "actor_part": "hand",
                 "target": "kitchen_table", "target_part": "edge",
                 "manner": "rest", "relation": "surface", "motion": "settled"}]})
        assert [c["actor"] for c in _holds(scene, PLATE)] == [PLAYER]

    def test_a_hold_nothing_else_records_still_ages(self):
        """The rule is the containment ledger's word, not a hold's: a hand on
        a thing nobody keeps ages exactly as before."""
        scene = _seated_with_the_plate()
        del scene["contained"][PLATE]
        scene = apply_contact_ops(scene, copy.deepcopy(MARA_SETS_DOWN_HER_SPOON))
        assert _holds(scene, PLATE) == []

    def test_a_hold_on_what_someone_else_keeps_still_ages(self):
        scene = _seated_with_the_plate()
        scene["contained"][PLATE] = {"in": "Mara", "mode": "held"}
        scene = apply_contact_ops(scene, copy.deepcopy(MARA_SETS_DOWN_HER_SPOON))
        assert _holds(scene, PLATE) == []

    def test_a_touch_is_not_a_hold(self):
        """Only the bearing manners are carriage; a fingertip resting on a
        plate she keeps is ordinary contact and ages as ordinary contact."""
        scene = _seated_with_the_plate()
        scene["contacts"][0]["manner"] = "touch"
        scene = apply_contact_ops(scene, copy.deepcopy(MARA_SETS_DOWN_HER_SPOON))
        assert not [c for c in scene["contacts"] if c.get("target") == PLATE]

    def test_setting_it_down_still_ends_both(self):
        scene = merge_scene_with_diff(_seated_with_the_plate(), {"inventory_ops": [
            {"op": "transfer", "object_id": PLATE, "from_id": PLAYER,
             "to_id": "kitchen_table"}]})
        assert containment_record(scene, PLATE) is None
        assert _holds(scene, PLATE) == []


# ---------------------------------------------------------------------------
# 3. The view.
# ---------------------------------------------------------------------------

def _view(scene, room, prev=frozenset()):
    percepts = composer.room_content_percepts(
        perception._visible_things(scene, PLAYER, room, bodies=[PLAYER, "Mara"]))
    return composer.render_view(percepts, mode="player", prev_standing=prev)


class TestWhatYouCarryGoesWithYou:
    def test_it_is_told_again_in_the_room_it_is_carried_into(self):
        kitchen = _cottage("kitchen")
        first = _view(kitchen, "kitchen")
        assert "You are holding an empty small plate." in first.text
        assert "You are carrying the mug." in first.text
        # the next beat, still in the kitchen: furniture, as before
        again = _view(kitchen, "kitchen", frozenset(first.standing_keys))
        assert "plate" not in again.text and "mug" not in again.text
        # she follows Mara up the stairs: the dishes go with her, and she
        # is told so where she arrives
        landing = merge_scene_with_diff(copy.deepcopy(kitchen),
                                        {"positions": {PLAYER: "landing"}})
        assert landing["positions"][PLATE] == "landing"
        moved = _view(landing, "landing", frozenset(again.standing_keys))
        assert "You are holding an empty small plate." in moved.text
        assert "You are carrying the mug." in moved.text

    def test_a_move_retells_it_as_background_never_as_an_event(self):
        """A room it has not been kept in is a first sight, which an
        ambient never leads with -- the narrator is not handed "you picked
        up the plate"."""
        kitchen = _cottage("kitchen")
        keys = frozenset(_view(kitchen, "kitchen").standing_keys)
        landing = merge_scene_with_diff(copy.deepcopy(kitchen),
                                        {"positions": {PLAYER: "landing"}})
        percepts = composer.room_content_percepts(
            perception._visible_things(landing, PLAYER, "landing", bodies=[PLAYER]))
        verdicts = composer.standing_verdicts(percepts, keys)
        assert set(verdicts.values()) == {"first"}
        assert not any(composer.leads_the_beat(p, verdicts[p.dedupe_key], keys)
                       for p in percepts)

    def test_a_change_of_grip_in_one_room_is_still_a_change(self):
        kitchen = _cottage("kitchen")
        keys = frozenset(_view(kitchen, "kitchen").standing_keys)
        kitchen["contained"][PLATE] = {"in": PLAYER, "mode": "carried"}
        percepts = composer.room_content_percepts(
            perception._visible_things(kitchen, PLAYER, "kitchen", bodies=[PLAYER]))
        verdicts = composer.standing_verdicts(percepts, keys)
        assert "changed" in verdicts.values()


# ---------------------------------------------------------------------------
# 4. The opening.
# ---------------------------------------------------------------------------

def _opening_diff():
    """Chat 176's establish, in the fixture's names: the towel and the mug
    are put in the player's hands with `held_by` and positioned in the
    kitchen; nothing else says she has them."""
    scene = _cottage("kitchen")
    return {
        "rooms": scene["rooms"],
        "positions": {PLAYER: "kitchen", "Mara": "kitchen",
                      "the towel": "kitchen", MUG: "kitchen"},
        "entities": {
            "stranger_01": scene["entities"]["stranger_01"],
            "towel_01": {"name": "the towel", "kind": "object", "portable": True,
                         "held_by": PLAYER,
                         "description": "A thick cotton towel."},
            "mug_01": scene["entities"]["mug_01"],
        },
        "attire": scene["attire"],
    }


class TestTheOpeningPutsItInTheOneStore:
    def test_the_merged_preview_already_carries_it(self):
        """No commit has run: this is the scene perception_establish reads."""
        preview = merge_scene_with_diff({}, _opening_diff())
        assert containment_record(preview, "the towel") == {"in": PLAYER, "mode": "carried"}
        assert containment_record(preview, MUG) == {"in": PLAYER, "mode": "carried"}

    def test_the_openings_own_view_says_it_is_hers(self):
        """176's opening view: "There is the towel here. There is the mug
        here." beside "You hold: the towel, the mug."."""
        preview = merge_scene_with_diff({}, _opening_diff())
        said = " ".join(row["what"] for row in perception._visible_things(
            preview, PLAYER, "kitchen", bodies=[PLAYER, "Mara"]))
        assert "You are carrying the towel." in said
        assert "You are carrying the mug." in said
        assert "There is" not in said

    def test_the_commit_finds_the_record_it_would_have_written(self):
        preview = merge_scene_with_diff({}, _opening_diff())
        before = json.loads(json.dumps(preview["contained"]))
        assert derive_borne_containment(preview) == []
        assert preview["contained"] == before
        assert before["the towel"] == {"in": PLAYER, "mode": "carried", "by": "bearing"}
