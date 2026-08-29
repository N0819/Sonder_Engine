"""What the deterministic composer puts in front of the narrator.

Four properties of the composed PLAYER view, each pinned against a shape
taken from a recorded run (chat 98, the Enterprise-D alpha shift) rather
than against a fixture invented to match the fix:

1. a player view the delta emptied is re-asked for the background rather
   than stored as None (`perception._composer_outcome`);
2. a body presented individually is described by the noun its own
   institution gives it, not by the generic stranger label;
3. a contact party that is not a body is never called "someone";
4. a forced observation merge spends a cheaper boundary before it welds two
   of one mouth's quoted lines into a single delivery.

Everything but (1) is fast tier: no database, no model. (1) runs the real
outcome stage twice over one unchanged scene, because the state it is about
-- a full standing ledger and nothing new against it -- is exactly what a
hand-built percept list cannot prove.
"""

from __future__ import annotations

import json
import time

import agents.common as common
import agents.composer as composer
from agents.perception import perception_outcome
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import (default_character_data,
                                    default_persona_data)

LOUNGE = "lounge"


# ---------------------------------------------------------------------------
# 1. "Nothing new" and "nothing reached this mind" are different states.
# ---------------------------------------------------------------------------

def _quiet_ctx(temp_db, *, turn_idx=1, chat_id=None, char=None):
    """A player standing in a lit room with one other body, and a beat in
    which nothing whatever happens -- chat 98 turn 20's shape (she never
    moved, no line reached her, `views.player` stored as null)."""
    persona_id = char
    if chat_id is None:
        persona_id = temp_db.qi(
            "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
            ("Sabine", json.dumps(default_persona_data("Sabine")), "{}"))
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created,persona_id) "
            "VALUES(?,?,?,?)", ("Quiet beat", "", time.time(), persona_id))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            ("Reya", json.dumps(default_character_data("Reya")), "{}",
             time.time(), "char_quiet"))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        temp_db.wset(chat_id, "scene", {
            "location": "Station", "time": "day",
            "rooms": {LOUNGE: {"name": "The Lounge", "adjacent": [],
                               "light": "lit"}},
            "positions": {"Sabine": LOUNGE, "Reya": LOUNGE},
            "entities": {}, "attire": {}, "overlays": {},
        })
        temp_db.wset(chat_id, "known", {"Sabine": ["Reya"],
                                        "Reya": ["Sabine"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Quiet beat", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="", created=time.time()),
        cast=cast, input="")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "speech_volume": "normal",
        "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}}
    ctx["background_react"] = {
        "fired": False, "name": None, "reactions": [], "selected": [],
        "mode": "background_react",
    }
    return ctx, chat_id, persona_id


def test_a_second_quiet_beat_still_hands_the_narrator_the_room(temp_db):
    """Chat 98 turns 13, 15, 16, 20, 21 and 36: `views.player` null and
    `observations.player` empty on six of thirty-eight played beats, so
    `agents/narration.py` fell through to "nothing in particular reaches you
    this beat" and the narrator wrote the room out of nothing. Nothing had
    stopped reaching her; nothing was NEW."""
    ctx, chat_id, persona_id = _quiet_ctx(temp_db)
    first = perception_outcome(ctx, "n0")
    assert (first["views"] or {}).get("player")

    later, _, _ = _quiet_ctx(temp_db, turn_idx=2, chat_id=chat_id,
                             char=persona_id)
    later["_composer_turn_ledger"] = first["composer_ledger"]
    second = perception_outcome(later, "n1")
    view = (second["views"] or {}).get("player")
    assert view and view.strip(), (
        "every standing percept suppressed as already told and no event "
        "left: the view collapsed while the observer was still in the room")
    assert "Lounge" in view


def test_the_recovered_view_is_background_and_not_an_obligation(temp_db):
    """The recovery re-delivers standing state; it must not claim any of it
    just happened. `_render_observed_events` files on `standing`, so a beat
    marked here becomes a numbered delivery the narrator owes the page."""
    ctx, chat_id, persona_id = _quiet_ctx(temp_db)
    first = perception_outcome(ctx, "n0")
    later, _, _ = _quiet_ctx(temp_db, turn_idx=2, chat_id=chat_id,
                             char=persona_id)
    later["_composer_turn_ledger"] = first["composer_ledger"]
    second = perception_outcome(later, "n1")
    observations = (second["observations"] or {}).get("player") or []
    assert observations
    assert all(o.get("standing") for o in observations)


def test_a_quiet_beat_still_composes_to_nothing_in_the_renderer():
    """The renderer's own contract is untouched: it renders a DELTA, and an
    empty delta is the honest answer to "what is new". Only the stage that
    holds the observer decides what the narrator is handed."""
    percepts = [composer.environment_percept("hall", "Hall", "Quiet.")]
    prev = {p.dedupe_key for p in percepts}
    assert composer.render_view(percepts, mode="player",
                                prev_standing=prev).text == ""


# ---------------------------------------------------------------------------
# 2. A body presented individually keeps the noun the crowd would have used.
# ---------------------------------------------------------------------------

#: Verbatim from chat 98's `world.background_presences`: the charter mints a
#: display name as `<role> <given> <family>`, and `presence_figures_for_room`
#: hands the same role back as the body's appearance summary.
RUN98_PRESENCES = [
    ("ensign Rooez Troerson", "ensign"),
    ("ensign Davona Lageson", "ensign"),
    ("lieutenant_commander Keianly Laison", "chief engineer"),
    ("captain Samanam Forerson", "captain"),
]


def test_a_role_worn_in_the_name_survives_the_identity_strip():
    """A label is stripped of the body's identity tokens so it cannot name
    them. A rank or duty carried in the minted name is not identity -- it is
    the same noun the crowd says aloud -- and stripping it deleted the whole
    description, so five crew standing in a lit room reached the view as
    "the unfamiliar person"."""
    for name, role in RUN98_PRESENCES:
        label = common._unknown_actor_label(name, role, [], role=role)
        assert role.split()[-1] in label.casefold(), (name, label)
        # ...and never the person.
        for token in name.split()[1:]:
            assert token.casefold() not in label.casefold()


def test_two_of_one_rank_are_still_told_apart():
    labels = composer.assign_stranger_labels([
        (name, role, [], role) for name, role in RUN98_PRESENCES[:2]])
    assert len(set(labels.values())) == 2
    assert all("ensign" in label for label in labels.values())


def test_the_role_exemption_cannot_release_a_personal_name():
    """The exemption is of the role's own tokens and nothing else: a summary
    that is the body's personal name still strips to the generic label."""
    label = common._unknown_actor_label("Hinami", "Hinami", [], role="ensign")
    assert "hinami" not in label.casefold()


def test_a_description_that_only_repeats_the_label_says_nothing():
    """"The ensign is close by. You see ensign." is one fact twice, and the
    second half is ungrammatical besides."""
    percept = composer.appearance_percept(
        "ensign Rooez Troerson", "the ensign", "ensign")
    assert composer._render_standing(percept) == ""
    kept = composer.appearance_percept(
        "ensign Rooez Troerson", "the ensign",
        "a wiry ensign with a stylus behind one ear")
    assert composer._render_standing(kept)


# ---------------------------------------------------------------------------
# 3. A contact party the display map cannot place is not thereby a person.
# ---------------------------------------------------------------------------

def test_an_object_in_contact_is_not_called_someone():
    """Chat 98 turn 22, verbatim: `contact_ops` recorded the player's combadge
    resting on her uniform, and the sensation label answered "someone" for the
    badge. The narrator wrote a body pressed against her and attached three
    absent people's scents to it. `_pose_referent` already ranks this exact
    order of certainty for poses (chat 84, "standing beside someone" for a
    desk); the contact clause is the site that never asked it."""
    scene = {
        "location": "Ten Forward",
        "rooms": {"ten_forward": {"name": "Ten Forward", "adjacent": []}},
        "positions": {"Sabine Oyelaran": "ten_forward",
                      "combadge": "ten_forward"},
        "entities": {"combadge": {
            "name": "combadge", "kind": "object", "portable": True,
            "description": "Starfleet delta shield communicator badge."}},
        "attire": {}, "overlays": {}, "poses": {},
    }
    label = composer._pose_referent(scene, "Sabine Oyelaran", {}, [],
                                    "combadge", is_self=True)
    assert label and "someone" not in label
    assert "combadge" in label

    # A body the observer has not been shown is still "someone": a body you
    # are touching is delivered by interoception whether or not you see who.
    scene["positions"]["Jean-Luc Picard"] = "ten_forward"
    scene["poses"]["Jean-Luc Picard"] = {"posture": "standing"}
    assert composer._pose_referent(scene, "Sabine Oyelaran", {}, [],
                                   "Jean-Luc Picard",
                                   is_self=True) == "someone"


# ---------------------------------------------------------------------------
# 4. The forced merge spends the cheapest boundary, and a delivery is not it.
# ---------------------------------------------------------------------------

#: Chat 98 turn 29's player view, entry for entry. Eight spoken lines and one
#: seen pose -- nine atoms against a cap of eight -- and the cap welded
#: Picard's first two lines into observation 0. The narrator then wrote them
#: as one delivery, quotes adjacent, which is the weld D-P reported.
RUN98_TURN29 = [
    ("Jean-Luc Picard", 'Jean-Luc Picard says in a measured voice: '
     '"Acknowledged, Lieutenant."'),
    ("Jean-Luc Picard", 'Jean-Luc Picard says in a measured voice: "The '
     'sudden appearance after a clean survey eleven years prior is noted."'),
    ("Jean-Luc Picard", 'Jean-Luc Picard says in a measured voice: '
     '"Commander Data, evaluate what this timing implies."'),
    (None, "Lieutenant Worf stands motionless at tactical station."),
    ("Data", 'Data says in a formal voice: "The timing indicates an '
     'artificial construction event approximately eleven years ago."'),
    ("Data", 'Data says in a formal voice: "No signal was detected during '
     'the prior survey."'),
    ("Jean-Luc Picard", 'Jean-Luc Picard says: "Acknowledged, Commander '
     'Data. The agreement between methods is noted."'),
    ("Jean-Luc Picard", 'Jean-Luc Picard says in a precise voice: "The '
     'sudden activation suggests an event of artificial initiation."'),
    ("Jean-Luc Picard", 'Jean-Luc Picard says: "What does this timing imply '
     'regarding possible triggers?"'),
]


class _Rendered:
    def __init__(self, spans):
        self.spans = spans


def _turn29_rendered():
    spans = []
    for order, (speaker, sentence) in enumerate(RUN98_TURN29):
        if speaker is None:
            percept = composer.Percept(
                kind="pose", channel="sight", source_label="Lieutenant Worf",
                data={}, order_key=order,
                dedupe_key="pose:worf:%d" % order)
        else:
            percept = composer.Percept(
                kind="speech", channel="hearing", source_label=speaker,
                data={"quote": sentence}, order_key=order,
                dedupe_key="speech:%d" % order)
        spans.append((percept, sentence))
    return _Rendered(spans)


def _quote_count(text):
    return str(text).count('"') // 2


def test_the_cap_does_not_weld_two_quoted_lines_into_one_delivery():
    out = composer.observations_from_render("player", _turn29_rendered())
    assert len(out) <= composer._MAX_OBSERVATION_ATOMS
    welded = [o for o in out
              if _quote_count((o.get("observed") or {}).get("text") or "") > 1]
    assert not welded, (
        "the cap spent a delivery boundary while a cheaper one was "
        "available: %r" % welded)
