"""ONE ID NAMES ONE DECLARATION IN THE BEAT.

A mouth the interaction loop calls twice in one beat declares twice under
the same prefix (`turn:<turn>:character:<id>`), and `assign_event_ids`
numbered every declaration from 0. Measured, scratch story 166 turn 4610
(the Brackwater run, 2026-10-07): Abel Gale's round-0 lines and his round-2
lines were all `turn:4610:character:83:{0,1,2}:speech`. Every join
downstream is keyed on that id and keeps the first element under it
(`director_evidence.declared_elements`), so the resolve bound his round-2
lines to his round-0 declarations: his declared LOUD "Hester -- stay on the
walk. I'll come to you after." (how: "louder, meant to carry down the
stair") was logged, and delivered to the player, as a mutter in round 0's
tone ("the tone of a man who knows what he is asking and what it costs"),
and the page rendered "the same break" twice.

The rule is numbered past the mouth's earlier rounds, never per round: the
merged record a mouth carries through the beat then reads 0..n-1 in the
order it was said, exactly as if it had been one declaration.
"""

from __future__ import annotations

import json
import time

import agents.loops as loops
from agents import character
from agents.common import assign_event_ids
from agents.director import declared_elements
from story.character_schema import default_character_data


def _line(text, tone, volume="normal", target="Tamsin Coyle"):
    return {"type": "speech", "text": text, "tone": tone, "volume": volume,
            "targets": [target]}


class TestNumberingContinuesPastEarlierRounds:
    PREFIX = "turn:4610:character:83"

    def test_a_later_round_numbers_past_the_first(self):
        first = assign_event_ids([
            _line("Not here.", "low, flat", "mutter"),
            _line("Not with her standing there.", "barely above the fog",
                  "whisper"),
            _line("Hester. Go wait on--", "voice rough and wrong", "mutter",
                  "Hester Gale"),
        ], self.PREFIX)
        later = assign_event_ids([
            _line("She gave you the stairhead. That's not enough.",
                  "low, urgent", "mutter"),
            _line("Inside. Just you. Close the door behind you.",
                  "barely above a breath", "whisper"),
            _line("Hester -- stay on the walk. I'll come to you after.",
                  "louder, meant to carry down the stair", "loud",
                  "Hester Gale"),
        ], self.PREFIX, earlier=first)
        assert [e["event_id"] for e in first] == [
            f"{self.PREFIX}:{n}:speech" for n in (0, 1, 2)]
        assert [e["event_id"] for e in later] == [
            f"{self.PREFIX}:{n}:speech" for n in (3, 4, 5)]

    def test_each_round_binds_its_own_tags(self):
        """The join the resolve makes (`declared_elements`) over the loop's
        `combined_declarations`: each of round 2's ids names round 2's
        element, so the loud line stays loud."""
        first = assign_event_ids([
            _line("Hester. Go wait on--", "voice rough and wrong", "mutter",
                  "Hester Gale")], self.PREFIX)
        later = assign_event_ids([
            _line("Hester -- stay on the walk. I'll come to you after.",
                  "louder, meant to carry down the stair", "loud",
                  "Hester Gale")], self.PREFIX, earlier=first)
        index = declared_elements({}, [
            {"char_id": 83, "sequence": first},
            {"char_id": 83, "sequence": later}])
        bound = index[later[0]["event_id"]]
        assert bound["volume"] == "loud"
        assert bound["tone"] == "louder, meant to carry down the stair"

    def test_a_prefix_that_merely_starts_the_same_is_another_mouth(self):
        """`character:83` is not `character:830`: only the mouth's own
        numbers count."""
        other = assign_event_ids([_line("a", "t")], "turn:1:character:830")
        mine = assign_event_ids([_line("b", "t")], "turn:1:character:83",
                                earlier=other)
        assert mine[0]["event_id"] == "turn:1:character:83:0:speech"

    def test_an_already_stamped_element_keeps_its_id(self):
        stamped = assign_event_ids([_line("a", "t")], "turn:1:player")
        again = assign_event_ids(stamped, "turn:1:player", earlier=stamped)
        assert again[0]["event_id"] == stamped[0]["event_id"]


class _Loop:
    """The interaction loop's own helpers, made deterministic around the
    REAL `character_step` (only the model seam is faked): the beat runs
    Abel, then Hester, then Abel again -- turn 4610's shape."""

    @staticmethod
    def install(monkeypatch, order):
        monkeypatch.setattr(loops, "dialogue_config", lambda cid: {
            "max_micro_rounds": 3, "max_character_calls": 3,
            "initial_parallel_reactors": 1,
            "stop_on_question_to_player": False,
            "allow_npc_to_npc_dialogue": True,
            "silence_ends_exchange": False,
        })
        monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
        monkeypatch.setattr(loops, "_drop_absent", lambda ctx, ids: ids)
        monkeypatch.setattr(loops, "_requires_director_resolution",
                            lambda r: False)
        monkeypatch.setattr(loops, "_asks_player",
                            lambda r, chat, cast: False)
        monkeypatch.setattr(loops, "_sequence_has_content", lambda r: True)
        monkeypatch.setattr(loops, "_untargeted_order",
                            lambda ctx, ids, nonce: list(ids))
        monkeypatch.setattr(
            loops, "deterministic_micro_perception",
            lambda ctx, actor_id, actor_result, scene, **kwargs: ({}, set()))
        monkeypatch.setattr(
            loops, "_next_speaker_candidates",
            lambda ctx, sid, perceived, spoke: (
                [order[len(spoke) % len(order)]]))


def _db_ctx(temp_db):
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Brackwater", "", time.time()))
    ids = []
    for name in ("Abel Gale", "Hester Gale"):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), name.casefold().replace(" ", "-")))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        ids.append(char_id)
    temp_db.wset(chat_id, "scene", {
        "location": "Gale house landing", "time": "night",
        "rooms": {"landing": {"name": "Gale house landing", "adjacent": []}},
        "positions": {"Abel Gale": "landing", "Hester Gale": "landing"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) "
        "VALUES(?,?,?,?)", (chat_id, 25, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Brackwater", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=25,
                      player_input="", created=time.time()),
        cast=cast, input="")
    ctx.director_interpret = {
        "speech": "", "sequence": [],
        "flow": {"reactors": [ids[0], ids[1]], "addressed_to": [],
                 "tom_triggers": []}}
    ctx.perception_act = {
        "views": {str(i): "The landing is wet with fog." for i in ids},
        "observations": {str(i): [] for i in ids}}
    return ctx, ids


def test_a_mouth_speaking_in_two_rounds_keeps_each_rounds_delivery(
        temp_db, monkeypatch):
    """Turn 4610 end to end through the loop: Abel, Hester, Abel. Every id
    in the beat's declarations is distinct, and the join the resolve makes
    binds Abel's second-round line to its own delivery."""
    ctx, (abel, hester) = _db_ctx(temp_db)
    _Loop.install(monkeypatch, [abel, hester])
    replies = iter([
        {"want": "keep Hester from hearing it",
         "sequence": [{"say": "Hester. Go wait on--", "to": "Hester Gale",
                       "how": "voice rough and wrong", "why": "get her off"}]},
        {"want": "stay in hearing",
         "sequence": [{"say": "I'm on the walk already, Abel.",
                       "to": "Abel Gale", "how": "low and even",
                       "why": "give him the stairhead"}]},
        {"want": "say it without her",
         "sequence": [{"say": "Hester -- stay on the walk. I'll come to "
                              "you after.",
                       "to": "Hester Gale",
                       "how": "louder, meant to carry down the stair",
                       "why": "keep her at the stairhead"}]},
    ])

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        return next(replies)

    monkeypatch.setattr(character, "_agent_json", fake_agent_json)

    out = loops.interaction_loop(ctx, nonce=0)

    assert [r["speaker_id"] for r in out["rounds"]] == [abel, hester, abel]
    declarations = out["combined_declarations"]
    ids = [element["event_id"] for declaration in declarations
           for element in declaration["sequence"]]
    assert len(ids) == len(set(ids)), ids
    index = declared_elements({}, declarations)
    second = declarations[2]["sequence"][0]
    assert index[second["event_id"]]["tone"] == \
        "louder, meant to carry down the stair"
    # The merged record the commit and perception read carries both rounds,
    # numbered in the order they were said.
    merged = ctx.character_results[abel]["sequence"]
    assert [e["event_id"] for e in merged] == [
        f"turn:{ctx.turn.id}:character:{abel}:0:speech",
        f"turn:{ctx.turn.id}:character:{abel}:1:speech"]
