"""A body the beat's acts are aimed at is asked what it does.

Under the prose contract `flow.reactors` is derived (`director_interpret`):
the beat's addressees, or everyone who perceives it when nobody was
addressed. Addressing one person therefore silenced every other mind in the
room -- including one the declaration's own act landed on.

Measured, Brackwater (scratch play db, chat 166 turn idx 30, the run's last
beat): the player opened the door to the pilot ("Come in, Mrs Gale") and
"steps aside so that brother and sister face each other across the lantern".
That act's targets were `character:81` and `character:83`; the reactors were
`[81]`. The pilot's line turned to the player, the loop stopped `awaiting
player response`, and her brother -- a full character at the table whose
drive and taboo are about her -- was never asked. The page spent the beat on
an unopened pocket instead of the exchange the scene had set.

The rule is `common.widen_reactors_to_acted_upon` (pure core
`common.acted_upon_cast`), read by the planner, the interaction loop and the
reaction phase alike. It is the response the act asks for, never a contest
over whether it succeeded and never conduct written for anybody.
"""

from __future__ import annotations

import inspect
import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data


PLAYER = "Tamsin"


def _rooms():
    """The house, the landing outside its shut door, and a cellar that
    shares no edge with either -- nothing of a beat upstairs reaches it."""
    return {
        "house": {"name": "House", "adjacent": [
            {"to": "landing", "barrier": "closed_door"}]},
        "landing": {"name": "Landing", "adjacent": [
            {"to": "house", "barrier": "closed_door"}]},
        "cellar": {"name": "Cellar", "adjacent": []},
    }


def _story(temp_db, positions):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Brackwater", "", time.time(), persona_id))
    ids = {}
    for name in ("Hester", "Abel"):
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    temp_db.wset(chat_id, "scene", {
        "location": "the fen", "time_of_day": "night", "rooms": _rooms(),
        "positions": dict(positions), "entities": {}, "attire": {},
        "overlays": {}})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 30, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Brackwater", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=30, player_input="",
                      created=time.time()),
        cast=cast, input="")
    return ctx, chat_id, ids


def _at_the_table():
    """Brother and player at the table; the sister on the landing."""
    return {PLAYER: "house", "Abel": "house", "Hester": "landing"}


def _the_last_beat(ids, *, reactors=None):
    """turn idx 30 as the interpret recorded it: the door opened at onset, a
    line to the sister, and an act aimed at both of them, in the engine's own
    handles."""
    hester, abel = f"character:{ids['Hester']}", f"character:{ids['Abel']}"
    open_door = {
        "house": {"adjacent": [{"to": "landing", "barrier": "open_door"}]},
        "landing": {"adjacent": [{"to": "house", "barrier": "open_door"}]},
    }
    return {
        "flow": {"reactors": list(reactors if reactors is not None
                                  else [ids["Hester"]]),
                 "addressed_to": [ids["Hester"]],
                 "resolution_flags": {}},
        "onset_state_assertions": {"rooms": open_door},
        "sequence": [
            {"type": "action", "attempt": "crosses to the door and opens it",
             "targets": ["landing"], "visibility": "overt",
             "commitment": "asserted"},
            {"type": "speech", "text": "Come in, Mrs Gale.",
             "targets": [hester], "visibility": "overt"},
            {"type": "action",
             "attempt": "steps aside so that brother and sister face each "
                        "other across the lantern",
             "targets": [hester, abel], "visibility": "overt",
             "commitment": "asserted"},
        ],
    }


# --- the engine's own handle -------------------------------------------------


def test_the_engines_own_handle_names_a_cast_member():
    """`character:<id>` is how the prose contract writes every cast target;
    the shared resolver read ids and names only, so the loop's acted-upon
    ranking found nobody in the measured beat."""
    from agents.common import normalize_character_refs
    cast = [{"id": 81, "sheet": json.dumps(default_character_data("Hester"))},
            {"id": 83, "sheet": json.dumps(default_character_data("Abel"))}]

    assert normalize_character_refs(
        ["character:81", "character:83"], cast) == [81, 83]
    assert normalize_character_refs(
        ["Character:83", "83", "Abel", 83], cast) == [83]
    assert normalize_character_refs(
        ["character:99", "character:", "character:abel", "persona:21"],
        cast) == []


def test_an_exclusion_written_in_the_engines_handle_excludes():
    """The micro-round's concealment floor read ids, names, uids and
    aliases, and not the handle its composer twin has always read: an
    exclusion written only as `character:<id>` named nobody. 39 resolve
    entries on the scratch db were handles and no list held handles alone --
    the floor held only because the model also wrote names."""
    from agents.common import _conceal_from_targets_observer
    from story.character_schema import normalize_character_data
    abel = normalize_character_data(default_character_data("Abel"))

    assert _conceal_from_targets_observer(["character:83"], 83, abel)
    assert _conceal_from_targets_observer(["Character:83"], 83, abel)
    assert _conceal_from_targets_observer(["Abel"], 83, abel)
    assert _conceal_from_targets_observer([83], 83, abel)
    assert not _conceal_from_targets_observer(["character:81"], 83, abel)
    assert not _conceal_from_targets_observer(["Hester"], 83, abel)


def test_a_contested_act_aimed_by_handle_is_a_contest():
    """The reaction phase's own gate read the target as an id or a name: a
    contestable act on `character:<id>` bound nobody, so the beat was never
    contested and the phase this widening also feeds never ran."""
    from agents.common import _requires_reaction_phase
    shove = {"type": "action", "commitment": "contestable",
             "attempt": "shoves him back from the table",
             "intended_effects": [{"kind": "pushed back"}]}

    assert _requires_reaction_phase(
        dict(shove, targets=["character:83"]), {81, 83}, {"abel", "hester"})
    assert _requires_reaction_phase(
        dict(shove, targets=["Abel"]), {81, 83}, {"abel", "hester"})
    assert not _requires_reaction_phase(
        dict(shove, targets=["character:99"]), {81, 83}, {"abel", "hester"})
    assert not _requires_reaction_phase(
        dict(shove, targets=["character:abel"]), {81, 83}, {"hester"})


# --- the class, at its pure core ----------------------------------------------


def test_a_body_an_act_lands_on_is_a_reactor_though_another_was_addressed(
        temp_db):
    """The measured beat: the line is to the sister, the act is aimed at
    both, and the brother at the table is the one the old list left out."""
    from agents.common import (acted_upon_cast, widen_reactors_to_acted_upon)
    from story.scene import get_scene
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    interp = _the_last_beat(ids)

    assert acted_upon_cast(get_scene(chat_id), ctx.cast, interp, PLAYER) == [
        ids["Hester"], ids["Abel"]]
    assert widen_reactors_to_acted_upon(
        chat_id, ctx.cast, interp, [ids["Hester"]]) == [
            ids["Hester"], ids["Abel"]]


def test_a_bystander_no_act_is_aimed_at_stays_the_directors_call(temp_db):
    """The widening is the act's, not the room's: a line to one person with
    nothing aimed at the other leaves the other where pacing put him."""
    from agents.common import widen_reactors_to_acted_upon
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    interp = _the_last_beat(ids)
    interp["sequence"] = interp["sequence"][:2]

    assert widen_reactors_to_acted_upon(
        chat_id, ctx.cast, interp, [ids["Hester"]]) == [ids["Hester"]]


def test_an_act_hidden_from_its_target_does_not_put_it_on_the_spot(temp_db):
    """Asking a mind what it does about an act concealed from it is asking
    about a thing it cannot know. Hidden from somebody ELSE, the target sees
    it and is asked; hidden from nobody in particular, nobody is added."""
    from agents.common import acted_upon_cast
    from story.scene import get_scene
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    scene = get_scene(chat_id)
    slip = {"type": "action", "attempt": "slips the receipt under his elbow",
            "targets": [f"character:{ids['Abel']}"],
            "visibility": "concealed", "commitment": "asserted"}

    hidden_from_him = dict(slip, conceal_from=[f"character:{ids['Abel']}"])
    hidden_by_name = dict(slip, conceal_from=["Abel"])
    hidden_from_her = dict(slip, conceal_from=["Hester"])
    hidden_unsaid = dict(slip, conceal_from=[])

    def aimed(element):
        return acted_upon_cast(scene, ctx.cast, {"sequence": [element]}, PLAYER)

    assert aimed(hidden_from_him) == []
    assert aimed(hidden_by_name) == []
    assert aimed(hidden_from_her) == [ids["Abel"]]
    assert aimed(hidden_unsaid) == []


def test_a_target_the_beat_cannot_reach_is_not_asked(temp_db):
    """An act aimed at somebody nothing of the beat reaches -- a letter
    written to a man in a cellar with no way up -- does not call him."""
    from agents.common import acted_upon_cast
    from story.scene import get_scene
    ctx, chat_id, ids = _story(
        temp_db, {PLAYER: "house", "Hester": "house", "Abel": "cellar"})

    assert acted_upon_cast(get_scene(chat_id), ctx.cast,
                           _the_last_beat(ids), PLAYER) == [ids["Hester"]]


def test_the_room_the_player_walks_into_is_where_the_beat_reaches(temp_db):
    """A declared walk takes the beat with it: the act lands in the room the
    player arrives in, so the body standing there is reached."""
    from agents.common import acted_upon_cast
    from story.scene import get_scene
    ctx, chat_id, ids = _story(
        temp_db, {PLAYER: "house", "Hester": "house", "Abel": "cellar"})
    interp = _the_last_beat(ids)
    interp["movement"] = {"to_room": "cellar", "mover": "self",
                          "arrives": True}
    assert ids["Abel"] in acted_upon_cast(
        get_scene(chat_id), ctx.cast, interp, PLAYER)

    interp["movement"]["arrives"] = False
    assert ids["Abel"] not in acted_upon_cast(
        get_scene(chat_id), ctx.cast, interp, PLAYER), (
            "setting off toward a room is not arriving in it")


def test_a_target_the_scene_places_nowhere_is_not_asked(temp_db):
    from agents.common import acted_upon_cast
    from story.scene import get_scene
    ctx, chat_id, ids = _story(temp_db, {PLAYER: "house", "Hester": "house"})

    assert acted_upon_cast(get_scene(chat_id), ctx.cast,
                           _the_last_beat(ids), PLAYER) == [ids["Hester"]]


# --- every reader of the list asks the same people ----------------------------


def test_the_planner_plans_the_body_the_act_landed_on(temp_db):
    from agents.runtime import build_plan
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    # autonomy 0 names each reactor as its own step, so the plan shows who.
    temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})

    keys = [key for key, _ in build_plan(
        _the_last_beat(ids), ctx.cast, chat_id=chat_id, turn_idx=30)]

    assert f"character:{ids['Abel']}" in keys
    assert f"character:{ids['Hester']}" in keys


def test_an_act_aimed_at_a_sleeper_does_not_wake_him(temp_db, monkeypatch):
    """Widened before the consciousness gate, so the gate still applies:
    waking is a Director transition, and a roused body acts next beat."""
    from agents import runtime
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
    monkeypatch.setattr(runtime, "awareness_map", lambda chat_id: {
        "abel": {"subject": "Abel", "level": "asleep"}})

    keys = [key for key, _ in runtime.build_plan(
        _the_last_beat(ids), ctx.cast, chat_id=chat_id, turn_idx=30)]

    assert f"character:{ids['Abel']}" not in keys
    assert f"character:{ids['Hester']}" in keys


HER_LINE = "You called me in, so here is the last of what I am carrying."


def _speaks_to_the_player(ctx, cid, nonce, *, calls, to_player, heard):
    calls.append(cid)
    heard[cid] = str(ctx._extra.get("interaction_views", {}).get(cid) or "")
    if cid in to_player:
        return {"sequence": [
                    {"type": "action",
                     "attempt": "steps in over the threshold with the coat",
                     "observable": "steps in over the threshold with the coat",
                     "targets": [PLAYER], "visibility": "overt",
                     "commitment": "asserted"},
                    {"type": "speech", "text": HER_LINE,
                     "targets": [PLAYER], "volume": "normal"}],
                "interaction": {"addresses": [PLAYER],
                                "expects_response": True}}
    return {"sequence": [{"type": "action",
                          "attempt": "looks from the coat to his sister",
                          "observable": "looks from the coat to his sister",
                          "targets": ["Hester"], "visibility": "overt",
                          "commitment": "asserted"}],
            "interaction": {"addresses": ["Hester"],
                            "expects_response": False}}


def test_the_brother_is_asked_after_his_sister_turns_to_the_player(
        temp_db, monkeypatch):
    """The whole measured beat through the loop: the sister comes in at the
    door the player opened, her line turns to the player, and the brother
    the player's act was aimed at -- who never was asked -- has his first
    turn, having heard her whole line, before the beat stops for the
    player."""
    from agents import loops
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    ctx.director_interpret = _the_last_beat(ids)
    ctx.perception_act = {"views": {}}
    calls, heard = [], {}
    monkeypatch.setattr(
        loops, "character_step",
        lambda c, cid, nonce: _speaks_to_the_player(
            c, cid, nonce, calls=calls, to_player={ids["Hester"]},
            heard=heard))

    out = loops.interaction_loop(ctx, nonce=0)

    assert calls == [ids["Hester"], ids["Abel"]], (
        f"asked {calls}, stopped {out.get('stop_reason')!r}: the sister, "
        "then her brother, each once, and nobody called again")
    assert out["stop_reason"] == "awaiting player response"
    assert HER_LINE in heard[ids["Abel"]], (
        f"he heard her through a shut door: {heard[ids['Abel']]!r}")


def test_the_target_of_a_contested_act_reacts_in_the_reaction_phase(
        temp_db, monkeypatch):
    """The reaction phase exists for the body a contestable act lands on;
    the planner plans it on the widened list, so the phase reads the same."""
    from agents import loops
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    interp = _the_last_beat(ids)
    interp["flow"]["resolution_flags"] = {"contested": True}
    interp["sequence"][2] = dict(
        interp["sequence"][2], attempt="shoves the brother back from the table",
        targets=[f"character:{ids['Abel']}"], commitment="contestable")
    ctx.director_interpret = interp
    ctx.perception_act = {"views": {str(ids["Hester"]): "a view",
                                    str(ids["Abel"]): "a view"}}
    calls = []
    monkeypatch.setattr(loops, "character_step",
                        lambda c, cid, nonce: calls.append(cid) or {
                            "sequence": []})

    loops.reaction_loop(ctx, nonce=0)

    assert ids["Abel"] in calls


def test_every_reader_of_the_list_widens_to_the_acted_upon():
    """The planner, the interaction loop and the reaction phase each read
    `flow.reactors` on their own; a widening that reaches one of them and not
    another plans a step its reader then finds empty (scratch story 166
    idx 13, the rejoined widening)."""
    from agents import loops, runtime
    for reader in (runtime.build_plan, loops.interaction_loop,
                   loops.reaction_loop):
        assert "widen_reactors_to_acted_upon(" in inspect.getsource(reader), (
            reader.__name__)


@pytest.mark.parametrize("element_type", ["thought", "", None])
def test_only_what_can_be_aimed_is_read(temp_db, element_type):
    """A thought is aimed at nobody: the element types are the engine's own
    closed set (`AIMED_ELEMENT_TYPES`)."""
    from agents.common import acted_upon_cast
    from story.scene import get_scene
    ctx, chat_id, ids = _story(temp_db, _at_the_table())
    interp = {"sequence": [{"type": element_type,
                            "targets": [f"character:{ids['Abel']}"]}]}

    assert acted_upon_cast(get_scene(chat_id), ctx.cast, interp, PLAYER) == []
