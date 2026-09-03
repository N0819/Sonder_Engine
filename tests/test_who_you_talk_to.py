"""Who the player is talking to -- five defects from the Harrowmere
playtest (2026-09-02), each stated as the class it belongs to:

* THE SAME BODY ANSWERS NEXT TIME. A word every holder of a post shares is
  the post's name, not anyone's (`_shared_name_words`); a communication
  aimed at someone is an address (`_communication_targets`); among equal
  demands the body that has already spoken outranks one that never has, and
  the tie-break is blind to case (`pick_voice_demand`).
* A NAME WRITTEN WITH NO CAPITAL TAKES ONE. The generator's fix does not
  reach a body already stored, so the render heals it and the ledger follows
  (`charter_identity.heal_name_case`, `with_charter_presences`).
* A ROOM SOMEONE SLEEPS IN IS THEIRS. A berth where no upkeep is served is a
  dwelling; the Director sees whose, the voice sees that it is home
  (`charter_runtime.charter_dwellings`, `presence_view`).
* A MIND IS EARNED, AND THE ENGINE SAYS WHEN. The beat a presence crosses
  the promotion threshold is stamped and told to the Director; a
  `cast_changes` entry naming a non-attached person is refused WITH the
  reason (`_propose_promotions`, `commit_cast_changes`).
* A TOKEN IS THE ADDRESS OF A DELIVERED LINE. A token with no line behind
  it is stripped on every beat and named in a warning
  (`narration._stray_line_tokens`).
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from language_runtime import raw_card


PLAYER = "The Stranger"


def _mk_ctx(temp_db, presences=None, player_input="", scene=None, turn_idx=5,
            charters=None):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Who", "", time.time()))
    temp_db.wset(cid, "scene", scene if scene is not None else _hall())
    if presences is not None:
        temp_db.wset(cid, "background_presences", presences)
    if charters is not None:
        temp_db.wset(cid, "charters", charters)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, player_input, time.time()))
    return PipelineContext(
        chat=ChatData(id=cid, name="Who", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)


def _hall(player_room="reeve_hall"):
    return {
        "location": "Harrowmere",
        "rooms": {
            "reeve_hall": {"name": "Reeve's Hall", "size": "medium",
                           "adjacent": []},
        },
        "positions": {PLAYER: player_room},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _presence(room, **extra):
    rec = {"first_turn": 1, "last_turn": 4, "dialogue_turns": [],
           "mention_turns": [], "sketch": {"station_room": room}}
    rec.update(extra)
    return rec


_QUIET = {"resolved_event": "The hall goes on about its business.",
          "dialogue_log": []}


# ---------------------------------------------------------------------------
# The same body answers next time
# ---------------------------------------------------------------------------

class TestAWordEveryHolderOfAPostSharesIsThePostsName:
    def test_the_shared_words_are_derived_from_the_names_themselves(self):
        from persist.commit import _shared_name_words
        assert _shared_name_words([
            "Reeve Halinham Nookfeller", "Reeve fenemere quarrfellwick",
            "the reeve's clerk", "Osric Fell"]) == {"reeve"}

    def test_a_shared_word_reaches_nobody_and_a_unique_word_its_owner(self):
        from persist.commit import _background_name_mentioned
        text = "I go back to the reeve's hall and ask Nookfeller about the rolls."
        assert _background_name_mentioned(
            "Reeve Halinham Nookfeller", text, shared={"reeve"})
        assert not _background_name_mentioned(
            "Reeve fenemere quarrfellwick", text, shared={"reeve"})
        # The same declaration, with nothing marked shared, is the old
        # behaviour: the title word qualified everyone who held it.
        assert _background_name_mentioned(
            "Reeve fenemere quarrfellwick", text)

    def test_the_full_name_still_matches_whatever_is_shared(self):
        from persist.commit import _background_name_mentioned
        assert _background_name_mentioned(
            "Reeve Fenemere", "Reeve Fenemere, a word.",
            shared={"reeve", "fenemere"})

    def test_the_gate_voices_the_reeve_who_was_asked(self, temp_db):
        """Harrowmere turn 33: "ask Nookfeller" qualified both reeves on
        the word "reeve", and a string sort picked the other one."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(
            temp_db, player_input=(
                "I go back to the reeve's hall and ask Nookfeller whether "
                "the clerk found anything in the old rolls."),
            presences={
                "Reeve Halinham Nookfeller": _presence(
                    "reeve_hall", dialogue_turns=[2, 4]),
                "Reeve fenemere quarrfellwick": _presence("reeve_hall"),
            })
        assert pick_background_reactors(ctx, dict(_QUIET), cap=2) == [
            "Reeve Halinham Nookfeller"]

    def test_a_lone_holder_is_still_reached_by_the_title(self, temp_db):
        """Chat 72's night clerk, preserved: with one clerk in the story,
        "clerk" is that clerk's word."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, player_input="Clerk? Anyone at the desk?",
                      presences={"the night clerk": _presence("reeve_hall")})
        assert pick_background_reactors(ctx, dict(_QUIET), cap=2) == [
            "the night clerk"]

    def test_a_shared_word_accrues_no_address_to_every_holder(self, temp_db):
        """The addressed counter is what earns a passer-by a sheet; on
        Harrowmere every reeve accrued it on eight beats the player spoke
        to one of them."""
        from persist.commit import track_background_presences
        ctx = _mk_ctx(
            temp_db, player_input="Morning, reeve. Is the hall open?",
            presences={
                "Reeve Halinham Nookfeller": _presence("reeve_hall"),
                "Reeve fenemere quarrfellwick": _presence("reeve_hall"),
            })
        ctx["director_resolve"] = dict(_QUIET)
        ctx["background_react"] = {"fired": False, "reactions": []}
        track_background_presences(ctx, 1)
        for rec in temp_db.wget(ctx.chat.id, "background_presences").values():
            assert 5 not in (rec.get("addressed_turns") or [])


class TestACommunicationAimedAtSomeoneIsAnAddress:
    def _interp(self, targets, visibility="overt"):
        return {"flow": {"addressed_to": [], "addressed_to_refs": []},
                "sequence": [{"type": "communication", "act": "ask",
                              "targets": targets, "visibility": visibility,
                              "content": "whether the rolls held anything"}]}

    def test_the_target_of_indirect_speech_is_the_addressee(self, temp_db):
        from persist.commit import _addressed_ref_strings
        ctx = _mk_ctx(temp_db)
        ctx["director_interpret"] = self._interp(["Reeve Halinham Nookfeller"])
        assert _addressed_ref_strings(ctx, {"dialogue_log": []}) == [
            "Reeve Halinham Nookfeller"]

    def test_a_concealed_communication_addresses_nobody(self, temp_db):
        from persist.commit import _addressed_ref_strings
        ctx = _mk_ctx(temp_db)
        ctx["director_interpret"] = self._interp(["Reeve Halinham Nookfeller"],
                                                 visibility="concealed")
        assert _addressed_ref_strings(ctx, {"dialogue_log": []}) == []

    def test_every_earlier_source_outranks_it(self, temp_db):
        from persist.commit import _addressed_ref_strings
        ctx = _mk_ctx(temp_db)
        interp = self._interp(["Reeve Halinham Nookfeller"])
        interp["flow"]["addressed_to_refs"] = ["the clerk"]
        ctx["director_interpret"] = interp
        assert _addressed_ref_strings(ctx, {"dialogue_log": []}) == [
            "the clerk"]

    def test_the_gate_forces_the_communications_target(self, temp_db):
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, player_input="I ask him about the rolls.",
                      presences={"Osric Fell": _presence("reeve_hall"),
                                 "Wat Penny": _presence("reeve_hall")})
        ctx["director_interpret"] = self._interp(["Osric Fell"])
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == [
            "Osric Fell"]


class TestTheBodyThatHasSpokenOutranksOneThatNeverHas:
    def _owed(self, turn=4):
        return {"from": PLAYER, "quote": "Well?", "tone": "", "turn": turn,
                "expires_turn": turn + 2}

    def test_familiarity_breaks_the_tie(self, temp_db):
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, player_input="I wait.", presences={
            "Ash Tarn": _presence("reeve_hall", dialogue_turns=[3],
                                  pending_reply=self._owed()),
            "Elm Rook": _presence("reeve_hall", pending_reply=self._owed()),
        })
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == [
            "Ash Tarn"]

    def test_the_more_recent_voice_wins_between_two_familiar_bodies(
            self, temp_db):
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, player_input="I wait.", presences={
            "Ash Tarn": _presence("reeve_hall", dialogue_turns=[2],
                                  pending_reply=self._owed()),
            "Elm Rook": _presence("reeve_hall", dialogue_turns=[3],
                                  pending_reply=self._owed()),
        })
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == [
            "Elm Rook"]

    def test_a_demand_trigger_still_outranks_familiarity(self, temp_db):
        """A debt is a stronger claim on the beat than having been met."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, player_input="I wait.", presences={
            "Ash Tarn": _presence("reeve_hall", dialogue_turns=[3],
                                  engaged_turns=[4]),
            "Elm Rook": _presence("reeve_hall", pending_reply=self._owed()),
        })
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == [
            "Elm Rook"]

    def test_the_tie_break_is_blind_to_case(self, temp_db):
        """Before: "ash Tarn" sorted after "Elm Rook" on the lower-case a
        and so won the reversed sort -- a spelling deciding who spoke."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, player_input="I wait.", presences={
            "ash Tarn": _presence("reeve_hall", pending_reply=self._owed()),
            "Elm Rook": _presence("reeve_hall", pending_reply=self._owed()),
        })
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == [
            "Elm Rook"]


# ---------------------------------------------------------------------------
# A name written with no capital takes one
# ---------------------------------------------------------------------------

class TestANameWrittenWithNoCapitalTakesOne:
    @pytest.mark.parametrize("stored, healed", [
        ("halinham nookfeller", "Halinham Nookfeller"),
        ("fenemere", "Fenemere"),
        ("Ludwig van Beethoven", "Ludwig van Beethoven"),
        ("de la Cruz", "de la Cruz"),
        ("はるか", "はるか"),
        ("", ""),
    ])
    def test_the_heal_touches_only_a_name_with_no_capital_anywhere(
            self, stored, healed):
        from world.charter_identity import heal_name_case
        assert heal_name_case(stored) == healed

    def test_display_name_renders_a_legacy_body_healed(self):
        from world.charter_identity import display_name
        assert display_name(_body("halinham nookfeller")) == \
            "Halinham Nookfeller"
        assert display_name(_body("Halinham Nookfeller")) == \
            "Halinham Nookfeller"

    def test_a_name_no_law_assembled_keeps_its_spelling(self):
        """An ambient presence is named by the prose -- "the reeve's
        clerk" is a description, not a proper noun -- and a hand-authored
        roster is an authored spelling; neither carries the components a
        law stores beside a name it built, and neither is touched."""
        from world.charter_identity import display_name
        assert display_name({"name": "the reeve's clerk"}) == \
            "the reeve's clerk"
        assert display_name({"name": "wat penny"}) == "wat penny"

    def test_the_ledger_follows_the_healed_spelling(self, temp_db):
        from persist.commit import with_charter_presences
        ctx = _mk_ctx(temp_db, charters=_registry())
        ledger = {"p_1": {"name": "halinham nookfeller", "uid": "p_1",
                          "dialogue_turns": [2], "mention_turns": [],
                          "charter_refs": [{"charter": "reeves_hall",
                                            "body": "r1"}],
                          "sketch": {"station_room": "reeve_hall"}}}
        merged = with_charter_presences(
            ctx.chat.id, ledger, _hall(), places={"reeve_hall"})
        assert merged["p_1"]["name"] == "Halinham Nookfeller"
        assert merged["p_1"]["dialogue_turns"] == [2]

    def test_a_different_name_is_never_overwritten(self, temp_db):
        """Only a spelling that differs by case alone is the same name."""
        from persist.commit import with_charter_presences
        ctx = _mk_ctx(temp_db, charters=_registry())
        ledger = {"p_1": {"name": "Old Nook", "uid": "p_1",
                          "dialogue_turns": [], "mention_turns": [],
                          "charter_refs": [{"charter": "reeves_hall",
                                            "body": "r1"}],
                          "sketch": {"station_room": "reeve_hall"}}}
        merged = with_charter_presences(
            ctx.chat.id, ledger, _hall(), places={"reeve_hall"})
        assert merged["p_1"]["name"] == "Old Nook"


# ---------------------------------------------------------------------------
# A room someone sleeps in is theirs
# ---------------------------------------------------------------------------

#: A body whose name a naming law assembled carries the components the
#: generator stores beside it (`charter_identity._assign_names`).
def _body(name, place="reeve_hall", berth=""):
    parts = name.split()
    return {"name": name, "given_name": parts[0],
            "family_name": parts[-1] if len(parts) > 1 else "",
            "place": place, "berth": berth or place, "available": True,
            "competence": {}}


def _registry():
    return {"items": {
        "reeves_hall": {"state": {
            "key": "reeves_hall", "priority": [],
            "upkeeps": {"court": {"place": "reeve_hall"}},
            "posts": {"reeve": {"place": "reeve_hall", "serves": ["court"],
                                "requires": {}}},
            "bodies": {
                "r1": _body("halinham nookfeller", "reeve_hall",
                            "stone_lane_cottage"),
                "m1": _body("Wat Penny", "stone_lane_cottage"),
            },
            "watch": {"reeve": "r1"},
        }},
        "ford_inn": {"state": {
            "key": "ford_inn", "priority": [],
            "upkeeps": {"taproom": {"place": "ford_inn_common"}},
            "posts": {"innkeeper": {"place": "ford_inn_common",
                                    "serves": ["taproom"], "requires": {}}},
            "bodies": {
                "i1": _body("Tam Ashwell", "ford_inn_common"),
            },
            "watch": {"innkeeper": "i1"},
        }},
    }}


class TestARoomSomeoneSleepsInIsTheirs:
    def test_a_berth_where_no_upkeep_is_served_is_a_dwelling(self, temp_db):
        from world.charter_runtime import charter_dwellings
        ctx = _mk_ctx(temp_db, charters=_registry())
        rows = charter_dwellings(
            ctx.chat.id, {"stone_lane_cottage", "ford_inn_common",
                          "reeve_hall"})
        assert rows == [{"room": "stone_lane_cottage",
                         "home_of": ["Halinham Nookfeller", "Wat Penny"],
                         "at_home": ["Wat Penny"]}]

    def test_a_berth_that_is_also_a_workplace_refuses_nobody(self, temp_db):
        """The inn's staff sleep over the taproom; the taproom is public."""
        from world.charter_runtime import charter_dwellings
        ctx = _mk_ctx(temp_db, charters=_registry())
        assert charter_dwellings(ctx.chat.id, {"ford_inn_common"}) == []

    def test_an_enrolled_persons_home_is_a_real_berth(self, temp_db):
        """A person the Director rendered with no plan behind them is
        enrolled somewhere real (`charter_enrol`): a guest of a lodging
        sleeps at the lodging, which is a workplace and so no dwelling; a
        householder sleeps in a house, which is one. There is no ambient
        placeholder for the hall a minted clerk stands in to read as his."""
        from world.charter_enrol import enrol_person
        from world.charter_runtime import charter_dwellings, presence_view
        from agents.common import present_charter_figures
        ctx = _mk_ctx(temp_db, charters=_registry())
        guest = enrol_person(ctx.chat.id, {"kind": "person", "surface": {
            "name": "Marrow", "room": "ford_inn_common"}})
        assert guest["how"] == "guest"
        assert charter_dwellings(ctx.chat.id, {"ford_inn_common"}) == []
        view = presence_view(ctx.chat.id, "ford_inn_common", "Marrow")
        assert view and view[0]["home"] == {"room": "ford_inn_common",
                                            "at_home": True}
        # A clerk minted in the hall with no clerk's post to take, and no
        # institution keeping its own berths here, joins a households
        # charter minted for the story -- and the hall is where they were
        # seen, not a house the town has: a dwelling is owed.
        clerk = enrol_person(ctx.chat.id, {"kind": "person", "surface": {
            "name": "the reeve's clerk", "room": "reeve_hall"}})
        assert clerk["how"] == "minted_households" and clerk["room_need"]
        rows = present_charter_figures(ctx.chat.id, _hall(), {"reeve_hall"})
        homes = {r["name"]: r["home"] for r in rows}
        assert homes["the reeve's clerk"] == "reeve_hall"

    def test_a_room_out_of_reach_is_not_listed(self, temp_db):
        from world.charter_runtime import charter_dwellings
        ctx = _mk_ctx(temp_db, charters=_registry())
        assert charter_dwellings(ctx.chat.id, {"reeve_hall"}) == []
        assert charter_dwellings(ctx.chat.id, set()) == []

    def test_a_story_with_no_charter_lists_nothing(self, temp_db):
        from agents.common import dwellings_in_reach
        ctx = _mk_ctx(temp_db)
        assert dwellings_in_reach(ctx.chat.id, {"stone_lane_cottage"}) == []

    def test_the_directors_figures_carry_where_each_sleeps(self, temp_db):
        from agents.common import present_charter_figures
        ctx = _mk_ctx(temp_db, charters=_registry())
        rows = present_charter_figures(ctx.chat.id, _hall(), {"reeve_hall"})
        assert [(r["name"], r["home"]) for r in rows] == [
            ("Halinham Nookfeller", "stone_lane_cottage")]

    def test_the_voice_knows_it_is_at_home(self, temp_db):
        from world.charter_runtime import presence_view
        ctx = _mk_ctx(temp_db, charters=_registry())
        view = presence_view(ctx.chat.id, "stone_lane_cottage", "Wat Penny")
        assert view and view[0]["home"] == {"room": "stone_lane_cottage",
                                            "at_home": True}
        view = presence_view(ctx.chat.id, "reeve_hall",
                             "Halinham Nookfeller")
        assert view and view[0]["home"] == {"room": "stone_lane_cottage",
                                            "at_home": False}

    @pytest.mark.parametrize("lang", ["en", "ja"])
    def test_the_prose_author_is_told_the_rule(self, lang):
        text = raw_card(lang)["prose_author_sheet"][17][1]
        assert "`dwellings`" in text


# ---------------------------------------------------------------------------
# A mind is earned, and the engine says when
# ---------------------------------------------------------------------------

class TestAMindIsEarnedAndTheEngineSaysWhen:
    def _record(self, name, dialogue=(), mentions=(), addressed=()):
        return {"name": name, "uid": "p_" + name.lower().replace(" ", "_"),
                "dialogue_turns": list(dialogue),
                "mention_turns": list(mentions),
                "addressed_turns": list(addressed), "nature": "person",
                "sketch": {"station_room": "reeve_hall"}}

    def test_crossing_the_dialogue_threshold_is_proposed_once(self, temp_db):
        from persist.commit import (BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
                                    _propose_promotions)
        ctx = _mk_ctx(temp_db)
        turns = list(range(1, BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD + 1))
        presences = {"p_ash_tarn": self._record(
            "Ash Tarn", dialogue=turns, addressed=turns)}
        assert _propose_promotions(ctx, presences, _hall()) == ["Ash Tarn"]
        assert presences["p_ash_tarn"]["promotion_proposed_turn"] == 5
        told = " ".join(ctx.engine_feedback)
        assert "Ash Tarn" in told and "cast_changes" in told
        assert any("promotion proposed" in w for w in ctx.warnings)
        # Once: the stamp is the memory.
        assert _propose_promotions(ctx, presences, _hall()) == []

    def test_below_the_threshold_nothing_is_proposed(self, temp_db):
        from persist.commit import (BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
                                    _propose_promotions)
        ctx = _mk_ctx(temp_db)
        presences = {"p_ash_tarn": self._record(
            "Ash Tarn",
            dialogue=range(1, BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD))}
        assert _propose_promotions(ctx, presences, _hall()) == []
        assert "promotion_proposed_turn" not in presences["p_ash_tarn"]

    def test_mentions_alone_can_cross_it(self, temp_db):
        from persist.commit import (BACKGROUND_PROMOTION_MENTION_THRESHOLD,
                                    _propose_promotions)
        ctx = _mk_ctx(temp_db)
        presences = {"p_ash_tarn": self._record(
            "Ash Tarn",
            mentions=range(1, BACKGROUND_PROMOTION_MENTION_THRESHOLD + 1))}
        assert _propose_promotions(ctx, presences, _hall()) == ["Ash Tarn"]

    def test_an_unnamed_presence_is_never_proposed(self, temp_db):
        from persist.commit import _propose_promotions
        ctx = _mk_ctx(temp_db)
        presences = {"p_x": self._record("a23653c914bf40a8",
                                         dialogue=[1, 2, 3])}
        assert _propose_promotions(ctx, presences, _hall()) == []

    def test_the_stories_own_threshold_governs(self, temp_db):
        from persist.commit import _propose_promotions
        ctx = _mk_ctx(temp_db)
        temp_db.wset(ctx.chat.id, "promotion_thresholds",
                     {"dialogue": 99, "mention": 99, "auto_dialogue": 99})
        presences = {"p_ash_tarn": self._record("Ash Tarn",
                                                dialogue=[1, 2, 3, 4])}
        assert _propose_promotions(ctx, presences, _hall()) == []

    def test_the_tracker_returns_what_it_proposed(self, temp_db):
        from persist.commit import (BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
                                    track_background_presences)
        n = BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD
        ctx = _mk_ctx(temp_db, player_input="I wait.", presences={
            "Ash Tarn": _presence("reeve_hall",
                                  dialogue_turns=list(range(1, n)))})
        ctx["director_resolve"] = {
            "resolved_event": "Ash Tarn answers.",
            "dialogue_log": [{"speaker": "Ash Tarn", "exact_quote": "Aye.",
                              "intended_target": PLAYER}]}
        ctx["background_react"] = {"fired": False, "reactions": []}
        out = track_background_presences(ctx, 1)
        assert out["promotion_proposed"] == ["Ash Tarn"]

    def test_a_cast_change_naming_a_stranger_is_refused_with_the_reason(
            self, temp_db):
        from persist.commit import commit_cast_changes
        ctx = _mk_ctx(temp_db)
        ctx["director_resolve"] = {"state_diff": {"cast_changes": [
            {"who": "Munda Thornhurst", "status": "active",
             "reason": "admits the player"}]}}
        commit_cast_changes(ctx, 1)
        assert any("not an attached character" in w for w in ctx.warnings)
        told = " ".join(ctx.engine_feedback)
        assert "Munda Thornhurst" in told and "promotion" in told

    @pytest.mark.parametrize("lang", ["en", "ja"])
    def test_the_social_hand_is_told_whom_it_may_name(self, lang):
        text = raw_card(lang)["specialists"]["social"]["chunks"][
            "cast_changes"]
        lowered = text.lower()
        assert ("attached" in lowered and "promotion" in lowered) or (
            "attached" in lowered and "昇格" in text)


# ---------------------------------------------------------------------------
# A token is the address of a delivered line
# ---------------------------------------------------------------------------

class TestATokenIsTheAddressOfADeliveredLine:
    def test_a_token_with_no_line_behind_it_is_named(self):
        from agents.narration import _stray_line_tokens
        assert _stray_line_tokens("My voice cuts through. {{L1}}", []) == [
            "{{L1}}"]
        assert _stray_line_tokens("{{L1}} then {{L2}}", ["Aye."]) == [
            "{{L2}}"]
        assert _stray_line_tokens("{{L1}}", ["Aye."]) == []
        assert _stray_line_tokens("Nobody spoke.", []) == []

    def test_the_strip_runs_on_a_beat_with_no_lines(self, monkeypatch):
        """Harrowmere turns 15, 22 and 37: substitution ran only when
        tokens existed, so a stray token on any other beat reached the
        page verbatim."""
        from agents import narration
        monkeypatch.setattr(
            narration, "_agent_json",
            lambda *a, **k: {"prose": "I stand facing the door. {{L1}} "
                                      "The lane is quiet.",
                             "new_specifics": []})
        out, warnings, _fidelity = narration._generate_narration(
            {"player_name": PLAYER}, "The lane is quiet.", "", [])
        assert "{{L1}}" not in out["prose"]
        assert out["prose"] == "I stand facing the door. The lane is quiet."
        assert any("no line behind it" in w and "{{L1}}" in w
                   for w in warnings)

    @pytest.mark.parametrize("lang", ["en", "ja"])
    def test_the_narrator_is_told_when_there_is_no_token(self, lang):
        text = raw_card(lang)["prompts"]["narrator"]
        assert "answers to no line" in text
