"""What a body is seen doing is admissible; what it is seen doing it TO is
admissible only where the target is.

Live: `docs/experiments/PLAY_2026_09_05C_masque.md` § PX5, "A Masque at the
Governor's House", turn 6, 2026-09-05. Ivo stood on a terrace the scene
records as "Completely dark and exposed to the winter cold", with the door
cracked. Verrin, in the gallery, declared

    {"type": "action", "visibility": "overt", "conceal_from": [],
     "observable": "looks leisurely over Ivo's uncovered face, then lifts
                    his wine glass and takes a slow, delicate sip without
                    flinching"}

and that sentence was delivered VERBATIM to Lisenne in the reception room two
edges away, and to Mattin in the gallery whose own view in the same beat
correctly read "Through the glazed terrace door, only darkness". Both
therefore received the name Ivo and the fact that his face was uncovered --
the plot's secret, delivered to the two people it was being kept from, in the
beat it was created. No tripwire fired: the identity scrub asks whether an
observer has earned a NAME, and the leak here was the STATE beside it.

The class, in the engine's vocabulary: an `observable` is free text about the
ACTOR, and every OTHER body it names is a percept about that body which must
pass the same admission a percept passes. `agents.perception`'s
`_act_surface_admission` cuts the span that names a body the observer's own
eyes did not reach this beat, and refuses the percept outright when no span
survives.

Both delivery floors are covered here, because F61's whole class is one beat
graded two ways: `perception_act` (the onset) and `perception_outcome`.
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

GALLERY = "gallery"
TERRACE = "terrace"
RECEPTION = "reception"


def _scene():
    """The masque's geometry: a lit gallery, a dark terrace through a
    cracked door, and a reception room one further edge away."""
    return {
        "location": "The Governor's House", "time": "night",
        "rooms": {
            GALLERY: {
                "name": "the Long Gallery", "light": "lit",
                "adjacent": [
                    {"to": TERRACE, "barrier": "open_door", "distance": "near",
                     "dir": "s"},
                    {"to": RECEPTION, "barrier": "open", "distance": "near",
                     "dir": "n"},
                ],
            },
            TERRACE: {
                "name": "the Terrace", "light": "dark",
                "adjacent": [{"to": GALLERY, "barrier": "open_door",
                              "distance": "near", "dir": "n"}],
            },
            RECEPTION: {
                "name": "the Reception Room", "light": "lit",
                "adjacent": [{"to": GALLERY, "barrier": "open",
                              "distance": "near", "dir": "s"}],
            },
        },
        # The player is Verrin; the persona has no card in this fixture, so
        # the engine's default persona name is the one the scene places.
        "positions": {"The Stranger": GALLERY, "Ivo Halvane": TERRACE,
                      "Mattin Sarr": GALLERY, "Lisenne Auber": RECEPTION},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Masque", "", time.time()))
    ids = {}
    for name in ("Ivo Halvane", "Mattin Sarr", "Lisenne Auber"):
        sheet = default_character_data(name)
        sheet["embodiment"]["visible"]["summary"] = (
            "%s, in a domino and a plain half-mask" % name)
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(),
             "char_" + name.split()[0].lower()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    temp_db.wset(chat_id, "scene", _scene())
    # Everyone has been introduced: the leak is not about an unearned NAME,
    # which is what makes it invisible to the identity scrub.
    guests = ["The Stranger", "Ivo Halvane", "Mattin Sarr", "Lisenne Auber"]
    temp_db.wset(chat_id, "known", {who: list(guests) for who in guests})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Masque", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["background_react"] = {
        "fired": False, "name": None, "reactions": [], "selected": [],
        "mode": "background_react",
    }
    return ctx, ids


OBSERVABLE = ("looks leisurely over Ivo Halvane's uncovered face, then lifts "
              "his wine glass and takes a slow, delicate sip without "
              "flinching")


def _act(ctx, ids):
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": OBSERVABLE,
                      "observable": OBSERVABLE, "visibility": "overt",
                      "conceal_from": []}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": list(ids.values()), "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    from agents.perception import perception_act
    return perception_act(ctx, "n0")


def _outcome(ctx, ids):
    """The same beat, one stage later. The outcome pass rebuilds the act
    from the interpret's own sequence, so the declaration is the same one."""
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": OBSERVABLE,
                      "observable": OBSERVABLE, "visibility": "overt",
                      "conceal_from": []}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    ctx.director_resolve = {
        "resolved_event": "He looks the man over and drinks.",
        "dialogue_log": [], "state_diff": {},
    }
    from agents.perception import perception_outcome
    return perception_outcome(ctx, "n0")


@pytest.mark.parametrize("stage", ["act", "outcome"])
def test_an_observable_may_not_carry_a_body_the_observer_cannot_see(
        temp_db, stage):
    """PX5. The unmasked man is in a dark room next door; the clause about
    him is cut from every view, and the actor's own conduct survives."""
    ctx, ids = _ctx(temp_db)
    out = _act(ctx, ids) if stage == "act" else _outcome(ctx, ids)
    views = out["views"]

    for watcher in ("Mattin Sarr", "Lisenne Auber"):
        view = views[str(ids[watcher])]
        assert "Ivo" not in view, (watcher, view)
        assert "uncovered" not in view, (watcher, view)
        # The actor's own conduct is not collateral: the clause that names
        # nobody but him is still delivered where he is seen.
        if watcher == "Mattin Sarr":
            assert "wine glass" in view, view


def test_the_same_clause_survives_where_the_target_is(temp_db):
    """The gate is the target's ADMISSION, not the sentence. Put the man in
    the lit gallery with everyone else and the whole observable is
    delivered -- otherwise this would forbid describing what a body does to
    the person standing next to it."""
    ctx, ids = _ctx(temp_db)
    scene = _scene()
    scene["positions"]["Ivo Halvane"] = GALLERY
    temp_db.wset(ctx.chat.id, "scene", scene)
    view = _act(ctx, ids)["views"][str(ids["Mattin Sarr"])]
    assert "Ivo Halvane" in view, view
    assert "uncovered face" in view, view


def test_a_surface_that_is_only_about_an_unseen_body_is_refused(temp_db):
    """No span survives, so nothing is delivered: an act channel that
    cannot say what the actor did without naming somebody the observer has
    no channel to says nothing at all. It is a SUBTRACTION -- the observer
    is not told a different act happened."""
    ctx, ids = _ctx(temp_db)
    only = "takes hold of Ivo Halvane's bare chin and turns it to the light"
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": only, "observable": only,
                      "visibility": "overt", "conceal_from": []}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": list(ids.values()), "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    from agents.perception import perception_act
    view = perception_act(ctx, "n0")["views"][str(ids["Lisenne Auber"])]
    assert "Ivo" not in view, view
    assert "chin" not in view, view


def test_an_ordinary_word_that_is_also_a_name_does_not_cut_prose(temp_db):
    """The complement, and the reason the match is not a bare casefold: a
    body called by an everyday English word is matched only in its
    capitalised spelling, so "the rose in her hair" is not a percept of
    Rose. Without this a guard written to subtract identity would delete
    ordinary conduct instead."""
    from agents.perception import _act_surface_admission

    surface = "sets the rose down on the sill and turns away"
    kept, cut = _act_surface_admission(
        surface, actor="Verrin", observer="Mattin",
        forms_by_body={"Rose": ["Rose"]}, perceived=set(), who="probe")
    assert (kept, cut) == (surface, [])

    kept, cut = _act_surface_admission(
        "sets Rose down on the sill, then turns away",
        actor="Verrin", observer="Mattin",
        forms_by_body={"Rose": ["Rose"]}, perceived=set(), who="probe")
    assert kept == "then turns away"
    assert cut == ["Rose"]


def test_the_actor_and_the_observer_are_never_cut_from_their_own_act(temp_db):
    """Two exemptions the rule needs by construction: the act is ABOUT the
    actor, and an observer needs no channel to themselves."""
    from agents.perception import _act_surface_admission

    surface = "steps between Verrin and Mattin"
    kept, cut = _act_surface_admission(
        surface, actor="Verrin", observer="Mattin",
        forms_by_body={"Verrin": ["Verrin"], "Mattin": ["Mattin"]},
        perceived=set(), who="probe")
    assert (kept, cut) == (surface, [])
