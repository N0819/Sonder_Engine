"""The player's authority covers her own body and her own acts -- nothing more.

Two seams on the contact channel, the one channel that stores an ACTOR.

THE MERGE (`director_contact._merge_player_contact_assertions`) holds an
interpret contact assertion's endpoint against the resolve, so a resolve
cannot re-describe a declared `cervix` as `groin` without ending the contact
first. It held EVERY interpret assertion that way, whoever's act it was.
Measured on chat 178 t29-t35: the interpretation restated Mellisande's
standing holds every beat, and the merge then held her lips at Hinami's
throat, her hand at the waist and her fingertip at the groin against
Mellisande's own moves ("preserved player-declared contact endpoint
'throat'; resolve attempted to coarsen it to 'collarbones'..."). Her own
acts, and her own refinement of where another body touches hers, still hold.

THE RESOLVE (`director_contact._player_contacts_held`) can write an act of
the player's body she never declared -- chat 95 t40's tongue on a body her
declared act never reached. The contact reading only warned, and under the
prose contract it ran before the encoder's ops were folded, so it read an
empty diff and warned of nothing. It runs on the merged ops now, and a
flagged op is not committed. Measured over the 155 stored resolves whose
encoder events are on record (557 contact ops, 144 of them the player's):
it flags none, once her body closing on a touch already in it is read as
the world's (chat 155 t31, the one beat it flagged before that).
"""

from __future__ import annotations

import inspect
import json

import agents.director as director
from agents.director import (_merge_player_contact_assertions,
                             _player_contacts_held)

SCENE = {
    "rooms": {"spare_room": {"name": "Second Room"}},
    "positions": {"Hinami": "spare_room", "Mellisande": "spare_room"},
    "contacts": [
        {"actor": "Mellisande", "actor_part": "lips", "target": "Hinami",
         "target_part": "throat", "manner": "press", "relation": "surface",
         "motion": "settled"},
        {"actor": "Hinami", "actor_part": "hands", "target": "Mellisande",
         "target_part": "back", "manner": "grip", "relation": "surface",
         "motion": "settled"},
        {"actor": "Mellisande", "actor_part": "fingers", "target": "Hinami",
         "target_part": "groin", "target_interior": "vaginal canal",
         "manner": "insert", "relation": "interior", "motion": "settled"},
    ],
}


def _add(**kw):
    return {"op": "add", "manner": "press", "relation": "surface",
            "motion": "settled", **kw}


def _endpoints(ops):
    return [(op["actor"], op["actor_part"], op["target_part"])
            for op in ops if op.get("op") == "add"]


def test_another_bodys_restated_hold_does_not_stop_its_own_move():
    """178 t29: lips restated at the throat, the resolve moves them down."""
    restated = _add(actor="Mellisande", actor_part="lips", target="Hinami",
                    target_part="throat")
    moved = _add(actor="Mellisande", actor_part="lips", target="Hinami",
                 target_part="collarbones")
    reports = []
    merged = _merge_player_contact_assertions(
        [restated], [moved], reports.append, scene=SCENE, player_name="Hinami")
    assert ("Mellisande", "lips", "collarbones") in _endpoints(merged)
    assert not reports


def test_her_own_act_still_holds_its_endpoint():
    """178 t33: Hinami's own hand at Mellisande's back, re-described as the
    sweater -- the drift the merge exists to stop, and still stopped."""
    own = _add(actor="Hinami", actor_part="hands", target="Mellisande",
               target_part="back", manner="grip")
    drift = _add(actor="Hinami", actor_part="hands", target="Mellisande",
                 target_part="cream knit sweater", manner="grip")
    reports = []
    merged = _merge_player_contact_assertions(
        [own], [drift], reports.append, scene=SCENE, player_name="Hinami")
    assert ("Hinami", "hands", "cream knit sweater") not in _endpoints(merged)
    assert reports and "preserved player-declared contact endpoint" in reports[0]


def test_her_refinement_of_her_own_body_still_holds():
    """First-person sensation is hers: `cervix` where the ledger said
    `groin`, which the resolve may not coarsen back without ending it."""
    refined = _add(actor="Mellisande", actor_part="fingers", target="Hinami",
                   target_part="cervix", target_interior="vaginal canal",
                   manner="insert", relation="interior")
    coarse = dict(refined, target_part="groin")
    merged = _merge_player_contact_assertions(
        [refined], [coarse], scene=SCENE, player_name="Hinami")
    assert _endpoints(merged) == [("Mellisande", "fingers", "cervix")]


def test_without_a_scene_every_assertion_holds_as_before():
    restated = _add(actor="Mellisande", actor_part="lips", target="Hinami",
                    target_part="throat")
    moved = dict(restated, target_part="collarbones")
    merged = _merge_player_contact_assertions([restated], [moved])
    assert ("Mellisande", "lips", "collarbones") not in _endpoints(merged)


def test_the_resolve_merges_with_the_standing_scene():
    source = inspect.getsource(director.director_resolve)
    assert "scene=sc, player_name=p_name" in source


# ---------------------------------------------------------------------------
# The resolve may not give her body an act she did not declare
# ---------------------------------------------------------------------------

CAST = [{"id": 83, "sheet": json.dumps({"identity": {"name": "Mellisande"}})}]


def test_an_act_of_hers_nothing_she_declared_reached_is_not_committed():
    tongue = _add(actor="Hinami", actor_part="tongue", target="Mellisande",
                  target_part="throat")
    kept, warnings = _player_contacts_held(
        [tongue], [{"attempt": "lies back on the bed", "targets": []}],
        "Hinami", SCENE, SCENE, CAST)
    assert kept == []
    assert warnings and "Not committed as the player's conduct" in warnings[0]


def test_a_hold_that_already_stands_is_her_hold_said_again():
    """An encoder's op carries no `contact_id`; the standing hold is matched
    by its endpoints (`contact_id`), so a restated grip is never invented."""
    again = _add(actor="Hinami", actor_part="hand", target="Mellisande",
                 target_part="back", manner="grip")
    kept, warnings = _player_contacts_held(
        [again], [], "Hinami", SCENE, SCENE, CAST)
    assert kept == [again] and warnings == []


def test_what_she_reached_for_and_what_the_world_does_to_her_stand():
    reached = _add(actor="Hinami", actor_part="fingers", target="Mellisande",
                   target_part="hair", manner="hold")
    done_to_her = _add(actor="Mellisande", actor_part="mouth", target="Hinami",
                       target_part="vulva")
    furniture = _add(actor="Hinami", actor_part="heels", target="spare_room_bed",
                     target_part="mattress")
    ops = [reached, done_to_her, furniture]
    kept, warnings = _player_contacts_held(
        ops, [{"attempt": "rests her palm on Mellisande's head",
               "targets": ["Mellisande"]}], "Hinami", SCENE, SCENE, CAST)
    assert kept == ops and warnings == []


def test_her_body_closing_on_a_touch_already_in_it_is_not_her_reach():
    """Chat 155 t31, the one stored beat the reading flags at all: Mirelle's
    thumb inside her, and the encoder wrote her muscle closing on it. A part
    of another body on or in hers is done TO her; her body answering it is
    the world's to write, as a flinch is."""
    cast = [{"id": 72, "sheet": json.dumps(
        {"identity": {"name": "Mirelle Sulmirath"}})}]
    scene = {"positions": {"Hinami": "room", "Mirelle Sulmirath": "room"},
             "contacts": []}
    thumb_in = _add(actor="Mirelle Sulmirath", actor_part="left thumb",
                    target="Hinami", target_part="first knuckle depth",
                    manner="insert", relation="interior")
    clench = _add(actor="Hinami", actor_part="vaginal muscle",
                  target="Mirelle Sulmirath", target_part="left thumb",
                  manner="clench")
    kept, warnings = _player_contacts_held(
        [thumb_in, clench], [], "Hinami", scene, scene, cast)
    assert kept == [thumb_in, clench] and warnings == []
    # The same muscle on a part of hers that was never on her is a reach.
    reach = dict(clench, target_part="wrist")
    kept, warnings = _player_contacts_held(
        [thumb_in, reach], [], "Hinami", scene, scene, cast)
    assert kept == [thumb_in] and warnings


def test_the_floor_reads_the_merged_ops():
    source = inspect.getsource(director.director_resolve)
    held = source.index("_player_contacts_held(")
    assert source.index("_run_specialists(") < held
    assert held < source.index("_merge_player_contact_assertions(")
