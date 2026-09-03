"""Four defects from the Harrowmere replay on merged main (2026-09-03), each
fixed at the stage it originated in and stated as the class it belongs to:

* ATTRIBUTION FOLLOWS THE OBSERVER'S RECOGNITION, NOT THE STORY'S. A room's
  chatter fragment named a trader to a player who had never been told the
  name, because "the story has met this body" (`known_bodies`) licensed the
  name for every mind in the room (`charter_chatter.participant_forms`,
  `relabel_fragment`, `agents/perception`);
* A CAPITAL LETTER IS NOT A SUBJECT. An act surface opening with a
  third-person verb is a predicate whatever its case, and rendering it as
  an independent clause published it with no subject at all
  (`common._observable_predicate`);
* A MINT STANDS WHERE THE BEAT RESOLVED THE PLAYER INTO, and the opening
  beat binds like any other (`director_floors._mint_fallback_room`,
  `director._establish_identity_floor`);
* A LINE AIMED AT A DOOR IS AIMED AT WHOEVER IS INSIDE, and every pick
  records why it picked (`commit_background.addressed_rooms`,
  `pick_voice_demand`'s `why`, `background._result`'s `selected_why`).
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData


# ---------------------------------------------------------------------------
# Fixtures (the identity-binding suite's, so the two read alike)
# ---------------------------------------------------------------------------

PLAYER = "The Stranger"


def _mk_ctx(temp_db, presences=None, player_input="", scene=None,
            turn_idx=5, interpret=None):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("ReplayH", "", time.time()))
    temp_db.wset(cid, "scene", scene if scene is not None else {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    if presences is not None:
        temp_db.wset(cid, "background_presences", presences)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="ReplayH", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)
    if interpret is not None:
        ctx["director_interpret"] = interpret
    return ctx


def _two_rooms(player_room="stone_lane", barrier="open_door"):
    """A lane and a house joined by a door -- the Harrowmere t17 geometry.
    An open door grades a normal voice as FULL hearing; a shut one as a
    fragment, which is a line nobody can answer."""
    return {
        "location": "Harrowmere",
        "rooms": {
            "stone_lane": {"name": "Stone Lane", "size": "large",
                           "adjacent": [{"to": "house_aldred",
                                         "barrier": barrier,
                                         "distance": "near"}]},
            "house_aldred": {"name": "Aldred House", "size": "small",
                             "adjacent": [{"to": "stone_lane",
                                           "barrier": barrier,
                                           "distance": "near"}]},
        },
        "positions": {PLAYER: player_room},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _presence(room, **extra):
    rec = {"first_turn": 1, "last_turn": 4, "dialogue_turns": [],
           "mention_turns": [], "sketch": {"station_room": room}}
    rec.update(extra)
    return rec


def _player_line(target, text="\"Might I come in out of the rain?\""):
    return {"resolved_event": "A knock at the door.",
            "dialogue_log": [{"speaker": PLAYER, "exact_quote": text,
                              "intended_target": target,
                              "volume": "normal", "visibility": "overt"}],
            "state_diff": {}}


# ---------------------------------------------------------------------------
# N8 -- attribution follows the observer's recognition
# ---------------------------------------------------------------------------

class TestChatterNamesOnlyWhomTheObserverKnows:
    BODIES = {"t3": {"key": "t3", "name": "Kelselwell Brbrookmere",
                     "place": "square"},
              "b1": {"key": "b1", "name": "Marn", "place": "square"}}
    POSTS = {"warden": {"place": "square"}}
    WATCH = {"warden": "b1"}

    def test_the_forms_keep_the_name_and_the_anonymous_label_apart(self):
        from world import charter_chatter as chatter
        forms = chatter.participant_forms(
            "t3", place="square", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS, known_bodies=frozenset({"t3"}))
        assert forms == {"name": "Kelselwell Brbrookmere", "anon": ""}
        posted = chatter.participant_forms(
            "b1", place="square", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS, known_bodies=frozenset({"b1"}))
        assert posted == {"name": "Marn", "anon": "the warden"}

    def test_participant_label_is_unchanged_for_its_readers(self):
        from world import charter_chatter as chatter
        assert chatter.participant_label(
            "t3", place="square", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS, known_bodies=frozenset({"t3"})) == (
                "Kelselwell Brbrookmere", True)
        assert chatter.participant_label(
            "t3", place="square", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS) == ("", False)

    def test_an_observer_who_does_not_know_the_name_reads_a_stranger(self):
        """The Harrowmere t32 shape: the story had met the trader, the
        player had not, and the fragment named the trader to the player."""
        from world import charter_chatter as chatter
        fragment = {"speaker_label": "", "act": "ask",
                    "other_label": "", "subject_label": "",
                    "speaker_name": "Marn", "speaker_anon": "the warden",
                    "other_name": "Kelselwell Brbrookmere",
                    "other_anon": ""}
        fragment["what"] = chatter.fragment_phrase(fragment)
        out = chatter.relabel_fragment(fragment, recognizes=lambda n: False)
        assert "Kelselwell" not in out["what"]
        assert out["other_label"] == ""
        assert out["speaker_label"] == "the warden"
        assert "the warden" in out["what"]

    def test_an_observer_who_knows_the_name_reads_it(self):
        from world import charter_chatter as chatter
        fragment = {"speaker_label": "", "act": "ask",
                    "other_label": "", "subject_label": "",
                    "speaker_name": "", "speaker_anon": "",
                    "other_name": "Kelselwell Brbrookmere",
                    "other_anon": ""}
        out = chatter.relabel_fragment(
            fragment, recognizes=lambda n: n == "Kelselwell Brbrookmere")
        assert out["other_label"] == "Kelselwell Brbrookmere"
        assert "Kelselwell Brbrookmere" in out["what"]

    def test_a_body_the_observer_can_see_takes_the_observers_own_label(self):
        """Not recognised, but standing in view: the fragment calls them
        what the rest of this observer's view already calls them."""
        from world import charter_chatter as chatter
        fragment = {"speaker_label": "", "act": "tell",
                    "other_label": "", "subject_label": "",
                    "speaker_name": "", "speaker_anon": "",
                    "other_name": "Kelselwell Brbrookmere",
                    "other_anon": ""}
        out = chatter.relabel_fragment(
            fragment, recognizes=lambda n: False,
            display_for={"Kelselwell Brbrookmere":
                         "the weathered trader"}.get)
        assert out["other_label"] == "the weathered trader"
        assert "Kelselwell" not in out["what"]

    def test_a_fragment_carrying_no_names_is_returned_equal(self):
        from world import charter_chatter as chatter
        fragment = {"speaker_label": "the warden", "act": "ask",
                    "other_label": "", "subject_label": "", "what": "x"}
        assert chatter.relabel_fragment(
            fragment, recognizes=lambda n: True) == fragment

    def test_the_rooms_entry_carries_the_anonymous_form_by_default(
            self, temp_db):
        """The memoized per-room entry fails closed: a reader that never
        relabels reads a stranger, and the name rides beside it for the
        observer who has earned it."""
        from agents.common import chatter_for_room
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Chatter", "", time.time()))
        scene = {"location": "Low Town",
                 "rooms": {"square": {"name": "Square", "size": "large"}},
                 "positions": {"Aldous": "square"}}
        state = {
            "key": "guild", "upkeeps": {}, "priority": [],
            "posts": {"warden": {"place": "square", "serves": [],
                                 "requires": {}}},
            "bodies": {
                "b1": {"name": "Marn", "place": "square", "available": True,
                       "competence": {}},
                "b2": {"name": "Etta", "place": "square", "available": True,
                       "competence": {}}},
            "watch": {"warden": "b1"},
            "figures": {"Aldous": {"place": "square"}},
            "window_acts": [
                {"actor": "b1", "act": "ask", "other": "b2",
                 "subject": "Aldous", "place": "square", "at_hours": 8.0,
                 "event": False}],
        }
        temp_db.wset(cid, "charters", {"items": {"guild": {"state": state}}})
        # Etta has been met by the story (a live presence record).
        temp_db.wset(cid, "background_presences", {
            "p1": {"name": "Etta", "first_turn": 1, "last_turn": 2,
                   "dialogue_turns": [1], "mention_turns": [],
                   "sketch": {"station_room": "square"},
                   "charter_refs": [{"charter": "guild", "body": "b2"}]}})
        fragment = [e for e in chatter_for_room(cid, scene, "square")
                    if e["kind"] == "fragment"][0]
        assert fragment["other_name"] == "Etta"
        assert fragment["other_label"] == ""
        assert "Etta" not in fragment["what"]
        assert fragment["speaker_label"] == "the warden"


# ---------------------------------------------------------------------------
# N12 -- a capital letter is not a subject
# ---------------------------------------------------------------------------

class TestACapitalLetterIsNotASubject:
    def test_a_capitalised_verb_surface_takes_the_actor_as_subject(self):
        from agents.common import _observable_predicate
        out = _observable_predicate(
            "the unfamiliar person",
            "Wipes his hands on his apron and lifts his head.")
        assert out.startswith("the unfamiliar person wipes his hands")

    def test_a_real_independent_clause_still_stands_alone(self):
        from agents.common import _observable_predicate
        out = _observable_predicate(
            "Dr. Moon", "The flashlight beam moves across the wall.")
        assert out == "The flashlight beam moves across the wall."

    def test_a_lower_case_predicate_is_unchanged(self):
        from agents.common import _observable_predicate
        out = _observable_predicate(
            "the unfamiliar person", "rests both hands on the counter.")
        assert out.startswith("the unfamiliar person rests both hands")


# ---------------------------------------------------------------------------
# N1 -- a mint stands where the beat resolved the player into
# ---------------------------------------------------------------------------

class TestAMintStandsWhereThePlayerArrived:
    def test_the_arrival_room_outranks_the_room_before_the_beat(self):
        from agents.director import _mint_fallback_room
        sd = {"positions": {"Wren Ashby": "smithy"}}
        assert _mint_fallback_room(sd, "Wren Ashby", "market_square") \
            == "smithy"

    def test_a_beat_that_did_not_move_the_player_keeps_their_room(self):
        from agents.director import _mint_fallback_room
        assert _mint_fallback_room({"positions": {}}, "Wren Ashby",
                                   "market_square") == "market_square"
        assert _mint_fallback_room({}, "Wren Ashby", None) is None

    def test_the_floor_binds_a_movement_beat_mint_to_the_body_there(self):
        """Harrowmere t23: "The Blacksmith" minted on the beat the player
        stepped into the smithy, no position, the smith on watch inside."""
        from agents.director import (
            _bind_minted_entities_to_present_figures, _mint_fallback_room)
        # The figures resolve offers: the square the player left (a trader
        # stands there) and the smithy they walked into.
        figures = [{"name": "Trader Kelselwell Brbrookmere", "role": "trader",
                    "posts": ["stall"], "room": "market_square",
                    "charter": "market", "body": "trader:0003"},
                   {"name": "Smith of Harrowmere Tamstanmere Gargatebridge",
                    "role": "smith", "posts": ["smith"], "room": "smithy",
                    "charter": "smithy_charter", "body": "smith:0001"}]
        sd = {"entities": {"the_blacksmith": {
                  "name": "The Blacksmith", "kind": "person",
                  "description": "A burly, soot-streaked craftsman."}},
              "positions": {"Wren Ashby": "smithy"}}
        # Pooled by the pre-move room, the floor sees only the trader and
        # binds nothing; pooled by the arrival room it finds the smith.
        assert _bind_minted_entities_to_present_figures(
            {}, json.loads(json.dumps(sd)), figures,
            fallback_room="market_square") == []
        bound = _bind_minted_entities_to_present_figures(
            {}, sd, figures,
            fallback_room=_mint_fallback_room(sd, "Wren Ashby",
                                              "market_square"))
        assert [b["bound_to"] for b in bound] == [
            "Smith of Harrowmere Tamstanmere Gargatebridge"]
        assert sd["entities"]["the_blacksmith"]["charter_ref"] == {
            "charter": "smithy_charter", "body": "smith:0001"}

    def test_the_opening_beat_binds_like_any_other(self, temp_db,
                                                   monkeypatch):
        """Harrowmere t0: "The Gatekeeper" minted at the gate the town's own
        watch stands; `director_establish` ran no floor at all."""
        import agents.common as common
        from agents.director import _establish_identity_floor
        monkeypatch.setattr(common, "present_charter_figures",
                            lambda cid, sc, rooms, frame_id=None: [
                                {"name": "Householder Irmerwell Fenfordton",
                                 "role": "gatekeeper", "posts": ["gate_watch"],
                                 "room": "upland_gate",
                                 "charter": "reeves_hall",
                                 "body": "watchman:0003"}]
                            if "upland_gate" in rooms else [])
        ctx = _mk_ctx(temp_db, turn_idx=0)
        out = {"state_diff": {
                   "entities": {"gatekeeper": {
                       "name": "The Gatekeeper", "kind": "person",
                       "description": "A watchman at the gate."}},
                   "positions": {"Wren Ashby": "upland_gate",
                                 "The Gatekeeper": "upland_gate"}},
               "dialogue_log": [], "dialogue_order": []}
        bound = _establish_identity_floor(ctx, out, "Wren Ashby")
        assert [b["bound_to"] for b in bound] == [
            "Householder Irmerwell Fenfordton"]
        assert out["identity_bindings"] == bound
        assert any("Minted 'The Gatekeeper'" in w for w in ctx.warnings)

    def test_the_opening_floor_is_silent_without_a_charter(self, temp_db,
                                                           monkeypatch):
        import agents.common as common
        from agents.director import _establish_identity_floor
        monkeypatch.setattr(common, "present_charter_figures",
                            lambda *a, **k: [])
        ctx = _mk_ctx(temp_db, turn_idx=0)
        out = {"state_diff": {"entities": {"g": {"name": "The Gatekeeper",
                                                  "kind": "person"}},
                              "positions": {"Wren Ashby": "gate"}}}
        assert _establish_identity_floor(ctx, out, "Wren Ashby") == []
        assert "identity_bindings" not in out
        assert ctx.warnings == []


# ---------------------------------------------------------------------------
# N7 -- a line aimed at a door is aimed at whoever is inside
# ---------------------------------------------------------------------------

class TestALineAimedAtADoorIsAimedAtWhoeverIsInside:
    def test_the_rooms_a_line_is_aimed_into_are_read_from_the_beat(
            self, temp_db):
        from persist.commit import addressed_rooms
        ctx = _mk_ctx(temp_db, scene=_two_rooms())
        sc = temp_db.wget(ctx.chat.id, "scene", {})
        # By the room's own name, by its id, and by a target the beat
        # places inside it.
        assert addressed_rooms(ctx, _player_line("Aldred House"), sc,
                               "stone_lane") == {"house_aldred"}
        assert addressed_rooms(ctx, _player_line("house_aldred"), sc,
                               "stone_lane") == {"house_aldred"}
        inside = _player_line("Mistress Tamar Aldred")
        inside["state_diff"] = {"positions": {
            "Mistress Tamar Aldred": "house_aldred"}}
        assert addressed_rooms(ctx, inside, sc, "stone_lane") == {
            "house_aldred"}

    def test_the_players_own_room_and_other_speakers_are_never_aimed(
            self, temp_db):
        from persist.commit import addressed_rooms
        ctx = _mk_ctx(temp_db, scene=_two_rooms())
        sc = temp_db.wget(ctx.chat.id, "scene", {})
        assert addressed_rooms(ctx, _player_line("Stone Lane"), sc,
                               "stone_lane") == set()
        other = {"dialogue_log": [{"speaker": "Somebody Else",
                                   "exact_quote": "\"Hello?\"",
                                   "intended_target": "Aldred House"}]}
        assert addressed_rooms(ctx, other, sc, "stone_lane") == set()

    def test_a_declared_move_not_yet_arrived_is_the_threshold(self, temp_db):
        """The player spoke and named nobody the scene can place, and their
        declared destination is a room they have not reached: the line is
        aimed into it."""
        from persist.commit import addressed_rooms
        ctx = _mk_ctx(temp_db, scene=_two_rooms(),
                      interpret={"movement": {"to_room": "house_aldred",
                                              "mover": "self",
                                              "arrives": False}})
        sc = temp_db.wget(ctx.chat.id, "scene", {})
        assert addressed_rooms(ctx, _player_line("whoever is home"), sc,
                               "stone_lane") == {"house_aldred"}
        # Already inside: nothing is a threshold.
        arrived = _player_line("whoever is home")
        arrived["state_diff"] = {"positions": {PLAYER: "house_aldred"}}
        assert addressed_rooms(ctx, arrived, sc, "stone_lane") == set()

    def test_a_body_inside_answers_through_an_open_door(self, temp_db):
        """Harrowmere t17: the knock reached every mind in the house and no
        voice could answer, because a candidate had to stand in the
        player's own room."""
        from persist.commit import pick_voice_demand
        ctx = _mk_ctx(temp_db, scene=_two_rooms(),
                      presences={"Goodwife Aldred": _presence("house_aldred")})
        demand = pick_voice_demand(ctx, _player_line("Aldred House"), cap=1)
        assert demand["picks"] == ["Goodwife Aldred"]
        why = demand["meta"]["Goodwife Aldred"]["why"]
        assert "place_addressed:house_aldred" in why
        assert "channel:hearing" in why
        assert demand["meta"]["Goodwife Aldred"]["addressed"] is False

    def test_a_shut_door_grades_the_line_down_and_nobody_answers(
            self, temp_db):
        from persist.commit import pick_voice_demand
        ctx = _mk_ctx(temp_db, scene=_two_rooms(barrier="closed_door"),
                      presences={"Goodwife Aldred": _presence("house_aldred")})
        assert pick_voice_demand(
            ctx, _player_line("Aldred House"), cap=1)["picks"] == []

    def test_a_house_is_answered_by_one_person(self, temp_db):
        """Place-addressed never forces the slot: eight sleepers behind one
        door are one answer, not eight."""
        from persist.commit import pick_voice_demand
        ctx = _mk_ctx(temp_db, scene=_two_rooms(), presences={
            "Goodwife Aldred": _presence("house_aldred"),
            "Old Aldred": _presence("house_aldred"),
            "Young Aldred": _presence("house_aldred")})
        demand = pick_voice_demand(ctx, _player_line("Aldred House"), cap=1)
        assert len(demand["picks"]) == 1

    def test_a_precise_addressee_outranks_the_house(self, temp_db):
        from persist.commit import pick_voice_demand
        ctx = _mk_ctx(temp_db, scene=_two_rooms(), presences={
            "Goodwife Aldred": _presence("house_aldred"),
            "Old Aldred": _presence("house_aldred")})
        dr = _player_line("Old Aldred")
        dr["state_diff"] = {"positions": {"Old Aldred": "house_aldred"}}
        demand = pick_voice_demand(ctx, dr, cap=1)
        assert demand["picks"] == ["Old Aldred"]
        assert "character_address" in demand["meta"]["Old Aldred"]["why"]

    def test_every_pick_records_why_it_picked(self, temp_db):
        """Harrowmere t23: a gate watchman answered a line spoken in the
        smithy on the acting trigger, and the step could not say so."""
        from persist.commit import pick_voice_demand
        acting = _presence("house_aldred", engaged_turns=[4])
        ctx = _mk_ctx(temp_db, scene=_two_rooms(),
                      presences={"Goodwife Aldred": acting})
        quiet = {"resolved_event": "The lane is quiet.", "dialogue_log": []}
        demand = pick_voice_demand(ctx, quiet, cap=1)
        assert demand["picks"] == ["Goodwife Aldred"]
        assert demand["meta"]["Goodwife Aldred"]["why"] == [
            "acting", "channel:hearing"]

    def test_the_stage_result_carries_the_working(self):
        from agents.background import _merge_stage_results, _result
        backstop = _result(["A"], [], why={"A": ["owed", "channel:same_room"]})
        assert backstop["selected_why"] == {"A": ["owed", "channel:same_room"]}
        manager = _result(["B"], [], mode="scene_life:full",
                          why={"B": ["flow_addressed", "channel:exempt"]})
        merged = _merge_stage_results(manager, backstop)
        assert merged["selected_why"] == {
            "B": ["flow_addressed", "channel:exempt"],
            "A": ["owed", "channel:same_room"]}
        assert _result([], [])["selected_why"] == {}
