"""A mind's second round in one beat restated its first, because every
self-record the engine keeps ended at the last commit.

Measured, chat 98 turns 24/29/31/32 (2026-08-29), all the same shape: a
character granted a later micro-round in the same beat re-delivered content
its own earlier round had already put into the room -- twice verbatim (turn
32: an acknowledgment and a full order, both word for word), once as a
subset restatement (turn 24: the order's operative clause re-issued alone),
once as a high-overlap paraphrase (turn 29, 0.78 content-token overlap).

The lead hypothesis -- that the speaker had never been told what it already
said -- was tested and is FALSE: the handed views were reconstructed per
round from the stored `delivered_views`/`self_view` and every one contained
the earlier lines verbatim; the failing results even cite the micro
observation carrying them. What was missing was the LEDGER: `recent_self_
lines`, `recent_self_moves` and every repetition guard read committed turns
(`t.idx < current`), so the beat's own earlier rounds were in the mind's
view of the room and in none of its records of itself.

Two mechanisms close the class:

1. `_this_beat_self_record` extends the self-ledger to the beat's own
   earlier rounds, through a loop-owned channel (`ctx._extra["beat_
   declared"]`) that the interaction loop resets at start -- never through
   `ctx.character_results`, which the single-step reroll path hydrates with
   the DISCARDED roll's output.
2. `strip_beat_reissues` is the deterministic floor under it: one mouth does
   not deliver the same line into the same beat twice, whatever the model
   does with the ledger. Cross-turn repetition stays record-only (the
   owner's no-re-ask ruling); within one beat the first copy reached the
   same ears in the same instant, so the second is subtracted.

The quoted lines below mirror the recorded pairs with the story's identities
renamed; the originals are in the run's stored step rows at the turns named.
"""

from __future__ import annotations

import json
import time

import agents.loops as loops
from agents import character
from agents.character import (_this_beat_self_record, strip_beat_reissues,
                              _address_names_body, _body_address_keys)
from story.character_schema import default_character_data


def _speech(text, **extra):
    return {"type": "speech", "text": text, **extra}


def _result(*texts):
    return {"sequence": [_speech(t) for t in texts]}


class TestStripBeatReissues:
    def test_a_verbatim_reissue_is_dropped(self):
        """Chat 98 t32 round 3: both of the round's lines were round 1's,
        word for word, with only a silent bystander round between."""
        prior = _result(
            "Your recommendation is noted, Lieutenant.",
            "Commander Veyra, assess the implications of approaching the "
            "source while the count continues.")
        out = _result(
            "Your recommendation is noted, Lieutenant.",
            "Commander Veyra, assess the implications of approaching the "
            "source while the count continues.")
        warnings = []
        strip_beat_reissues(out, prior, warn=warnings.append)
        assert out["sequence"] == []
        assert len(warnings) == 2
        assert all("re-delivers" in w for w in warnings)

    def test_a_subset_restatement_is_dropped_and_the_new_line_kept(self):
        """Chat 98 t24 round 3: the operative clause of round 1's order,
        re-issued alone -- every content token already delivered."""
        prior = _result(
            "Acknowledged, Mr. Sallow. Lieutenant Ashwin, source coordinates "
            "and decomposition parameters. Mr. Kade, maintain passive scans.")
        out = _result(
            "The nested intervals are noted.",
            "Source coordinates and decomposition parameters, Lieutenant.")
        warnings = []
        strip_beat_reissues(out, prior, warn=warnings.append)
        kept = [e["text"] for e in out["sequence"]]
        assert kept == ["The nested intervals are noted."]
        assert len(warnings) == 1

    def test_a_high_overlap_paraphrase_is_dropped(self):
        """Chat 98 t29 round 3: the same fact re-worded (measured 0.78
        content-token overlap against the 0.7 floor), beside a genuinely
        new question that must survive."""
        prior = _result(
            "The sudden appearance after a clean survey eleven years prior "
            "is noted.")
        out = _result(
            "The sudden activation after a clean survey eleven years prior "
            "suggests an event of artificial initiation.",
            "What does this timing imply regarding possible triggers or "
            "purpose?")
        strip_beat_reissues(out, prior, warn=None)
        kept = [e["text"] for e in out["sequence"]]
        assert kept == ["What does this timing imply regarding possible "
                        "triggers or purpose?"]

    def test_a_genuinely_new_second_round_is_untouched(self):
        """Chat 98 t33 round 3, the healthy case this must not break: the
        speaker's question was answered, and the second round acknowledges
        and issues a DIFFERENT order to a different officer."""
        prior = _result(
            "Understood, Lieutenant.",
            "Commander Veyra, assess the implications of approaching the "
            "source while the count continues.")
        out = _result(
            "Acknowledged, Commander.",
            "Mr. Kade, set course for the source at best speed.")
        warnings = []
        strip_beat_reissues(out, prior, warn=warnings.append)
        assert [e["text"] for e in out["sequence"]] == [
            "Acknowledged, Commander.",
            "Mr. Kade, set course for the source at best speed."]
        assert warnings == []

    def test_a_repeated_interjection_is_how_people_talk(self):
        prior = _result("Get out.")
        out = _result("Get out.")
        strip_beat_reissues(out, prior, warn=None)
        assert [e["text"] for e in out["sequence"]] == ["Get out."]

    def test_a_short_line_extended_is_escalation_not_reissue(self):
        """claim_similarity's subset short-circuit scores the short line as
        contained in the long one (1.0); the token floor keeps the judgment
        off lines too short to carry it."""
        prior = _result("I will not go.")
        out = _result("I will not go with you, whatever he says about it.")
        strip_beat_reissues(out, prior, warn=None)
        assert len(out["sequence"]) == 1

    def test_finishing_an_interrupted_line_is_completion(self):
        prior = {"sequence": [_speech(
            "The relay must be grounded before anyone touches the--",
            cut_short=True)]}
        out = _result(
            "The relay must be grounded before anyone touches the panel.")
        strip_beat_reissues(out, prior, warn=None)
        assert len(out["sequence"]) == 1

    def test_actions_pass_through_and_the_speech_scalar_is_cleared(self):
        prior = _result("Stand down and lower the blade, both of you.")
        out = {
            "speech": "Stand down and lower the blade, both of you.",
            "sequence": [
                {"type": "action", "attempt": "steps between them"},
                _speech("Stand down and lower the blade, both of you."),
            ],
        }
        strip_beat_reissues(out, prior, warn=None)
        assert [e["type"] for e in out["sequence"]] == ["action"]
        assert out["speech"] is None

    def test_no_prior_rounds_means_no_judgment(self):
        out = _result("Anything at all.")
        strip_beat_reissues(out, None, warn=None)
        assert len(out["sequence"]) == 1


class TestThisBeatSelfRecord:
    def test_lines_and_move_carry_the_this_beat_stamp(self):
        prior = {
            "sequence": [
                _speech("Bring the ledger to the annex before nightfall."),
                _speech("What did the courier carry?"),
            ],
            "response_candidates": [
                {"response": "direct the ledger's transfer and probe the "
                             "courier", "selected": True}],
            "interaction": {"expects_response": True},
        }
        lines, move = _this_beat_self_record(prior, 41)
        assert [l["said"] for l in lines] == [
            "Bring the ledger to the annex before nightfall.",
            "What did the courier carry?"]
        assert all(l["this_beat"] and l["turn"] == 41 for l in lines)
        assert move["this_beat"] and move["turn"] == 41
        assert move["asked"] == ["What did the courier carry?"]
        assert move["expected_answer"] is True

    def test_nothing_declared_is_nothing_recorded(self):
        assert _this_beat_self_record(None, 7) == ([], None)
        assert _this_beat_self_record({}, 7) == ([], None)


class TestAddressTailRule:
    """The cross-turn half of the measured failure. Chat 98 t32->t33: an
    order's `interaction.addresses` held rank-plus-name while the sheet's
    canonical name is the bare name; exact equality read that as nobody, no
    debt registered, the addressee was never promoted, and the asker
    re-issued the order verbatim the next turn."""

    def test_a_rank_prefixed_form_names_the_body(self):
        assert _address_names_body("Commander Veyra", ["Veyra"])
        assert _address_names_body("Mr. Kade", ["Kade"])
        assert _address_names_body("Lady Ashenford", ["Ashenford"])

    def test_the_canonical_spelling_still_matches(self):
        assert _address_names_body("Veyra", ["Veyra"])
        assert _address_names_body("veyra", ["Veyra"])

    def test_a_bare_title_is_ambiguous_and_names_nobody(self):
        assert not _address_names_body("Lieutenant", ["Lieutenant Ashwin",
                                                      "Ashwin"])

    def test_a_name_ending_in_anothers_does_not_collide(self):
        assert not _address_names_body("Rosanna", ["Anna"])
        assert not _address_names_body("Jean-Luc", ["Luc"])

    def test_keys_come_from_name_uid_and_aliases(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", 0.0))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("Veyra", json.dumps({"identity": {
                "name": "Veyra", "uid": "veyra_of_the_ninth",
                "aliases": ["Commander Veyra"]}}), 0.0))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        keys = _body_address_keys(chat_id, char_id, "Veyra")
        assert "Veyra" in keys
        assert "veyra_of_the_ninth" in keys
        assert "Commander Veyra" in keys


class _Chat:
    id = 1


class _Turn:
    idx = 5
    frame_id = None


class _Ctx:
    def __init__(self, reactors):
        self.chat = _Chat()
        self.turn = _Turn()
        self.cast = [
            {"id": cid,
             "sheet": json.dumps(default_character_data(f"Char{cid}")),
             "state": "{}", "active": 1, "stance": "{}"}
            for cid in reactors
        ]
        self.director_interpret = {
            "flow": {"reactors": list(reactors), "addressed_to": [],
                     "tom_triggers": [], "dialogue_mode": True},
            "sequence": [],
        }
        self.perception_act = {"views": {}}
        self.reaction_results = {}
        self.reaction_loop = {}
        self.character_results = {}
        self.warnings = []
        self._extra = {}

    def get(self, key, default=None):
        return getattr(self, key, default) or default


class TestTheLoopOwnsTheChannel:
    """`beat_declared` is written by the loop and read by `character_step`.
    The wiring is the point: the record must be reset at loop start (a
    reroll's hydrated leftovers are not this beat's conduct) and must hold a
    speaker's earlier rounds by the time their later round is called."""

    def _install(self, monkeypatch, calls):
        monkeypatch.setattr(loops, "dialogue_config", lambda cid: {
            "max_micro_rounds": 4, "max_character_calls": 4,
            "initial_parallel_reactors": 1,
            "stop_on_question_to_player": True,
            "allow_npc_to_npc_dialogue": True,
            "silence_ends_exchange": False,
        })
        monkeypatch.setattr(loops, "get_scene", lambda *a, **kw: {})
        monkeypatch.setattr(
            loops, "normalize_character_refs",
            lambda refs, cast: [int(r) for r in refs
                                if isinstance(r, int) or str(r).isdigit()])
        monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
        monkeypatch.setattr(loops, "_drop_absent", lambda ctx, ids: ids)
        monkeypatch.setattr(loops, "_requires_director_resolution",
                            lambda r: False)
        monkeypatch.setattr(loops, "_asks_player",
                            lambda r, chat, cast: False)
        monkeypatch.setattr(loops, "_sequence_has_content", lambda r: True)
        monkeypatch.setattr(
            loops, "deterministic_micro_perception",
            lambda ctx, actor_id, actor_result, scene: (
                {other["id"]: [f"{actor_id} spoke"]
                 for other in ctx.cast if other["id"] != actor_id},
                {other["id"] for other in ctx.cast if other["id"] != actor_id},
            ))
        monkeypatch.setattr(loops, "_untargeted_order",
                            lambda ctx, ids, nonce: list(ids))
        # Speaker 1 again after both have spoken, then stop.
        monkeypatch.setattr(
            loops, "_next_speaker_candidates",
            lambda ctx, sid, perceived, spoke: [1] if len(calls) == 2 else [])

        seen = {}

        def fake_character_step(ctx, cid, nonce):
            declared = ctx._extra.get("beat_declared", {})
            seen[len(calls)] = {
                k: [e["text"] for e in (v.get("sequence") or [])]
                for k, v in declared.items()}
            calls.append(cid)
            return {"sequence": [_speech(f"line {len(calls)} from {cid}")],
                    "interaction": {"expects_response": True, "urgency": 0.9,
                                    "conversation_complete_for_me": False}}

        monkeypatch.setattr(loops, "character_step", fake_character_step)
        return seen

    def test_reset_then_accumulated_then_handed_to_the_second_round(
            self, monkeypatch):
        calls = []
        seen = self._install(monkeypatch, calls)
        ctx = _Ctx(reactors=[1, 2])
        ctx._extra["beat_declared"] = {
            9: {"sequence": [_speech("a stale roll's leftovers")]}}

        loops.interaction_loop(ctx, nonce=0)

        assert calls == [1, 2, 1]
        # Round 0 decided against an EMPTY record: the pre-seeded junk (a
        # rerolled turn's hydrated leftovers) is gone.
        assert seen[0] == {}
        # Round 1's caller sees round 0's conduct.
        assert seen[1] == {1: ["line 1 from 1"]}
        # The second round of speaker 1 is handed speaker 1's OWN earlier
        # round -- the record whose absence was the measured defect.
        assert seen[2][1] == ["line 1 from 1"]
        assert seen[2][2] == ["line 2 from 2"]


class TestCharacterStepReadsTheLedger(object):
    """Full production path through `character_step` with only the model
    seam faked: the beat's earlier round reaches the payload ledger, and the
    deterministic floor strips a re-delivered line from the output."""

    def _ctx(self, temp_db):
        from core.pipeline_context import ChatData, PipelineContext, TurnData
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Reissue", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            ("Veyra", json.dumps(default_character_data("Veyra")), "{}",
             time.time(), "veyra-reissue"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        temp_db.wset(chat_id, "scene", {
            "location": "Archive", "time": "day",
            "rooms": {"hall": {"name": "Records Hall", "adjacent": []}},
            "positions": {"Veyra": "hall"},
            "entities": {}, "attire": {}, "overlays": {},
        })
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 8, "", time.time()))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Reissue", persona_id=None,
                          lorebook_id=None, scenario="",
                          created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=8,
                          player_input="", created=time.time()),
            cast=cast, input="")
        ctx.director_interpret = {
            "speech": "", "flow": {"reactors": [char_id],
                                   "tom_triggers": []}}
        ctx.perception_act = {"views": {str(char_id): "The hall is quiet."},
                              "observations": {str(char_id): []}}
        return ctx, char_id

    def test_the_ledger_arrives_and_the_floor_holds(self, temp_db,
                                                    monkeypatch):
        ctx, char_id = self._ctx(temp_db)
        ctx._extra["beat_declared"] = {char_id: {
            "sequence": [_speech(
                "Bring the ledger to the annex before nightfall.")],
            "response_candidates": [{
                "response": "direct the ledger transfer to the annex",
                "selected": True}],
            "interaction": {"expects_response": True},
        }}

        payloads = []

        def fake_agent_json(role, step_key, system, payload, **kwargs):
            payloads.append(payload)
            return {
                "response_candidates": [{
                    "response": "confirm the transfer and add the seal",
                    "selected": True}],
                "active_state": {"mood": "even",
                                 "wants": [{"want": "see the ledger moved",
                                            "urgency": 0.5}]},
                "sequence": [
                    _speech("Bring the ledger to the annex before "
                            "nightfall."),
                    _speech("And carry the registrar's seal with it."),
                ],
            }

        monkeypatch.setattr(character, "_agent_json", fake_agent_json)

        result = character.character_step(ctx, char_id, nonce=0)

        self_payload = payloads[0]["self"]
        beat_lines = [l for l in self_payload["recent_self_lines"]
                      if l.get("this_beat")]
        assert [l["said"] for l in beat_lines] == [
            "Bring the ledger to the annex before nightfall."]
        beat_moves = [m for m in self_payload["recent_self_moves"]
                      if m.get("this_beat")]
        assert [m["move"] for m in beat_moves] == [
            "direct the ledger transfer to the annex"]
        # The floor: the re-delivered line is gone, the new one stands.
        kept = [e.get("text") for e in result["sequence"]
                if e.get("type") == "speech"]
        assert kept == ["And carry the registrar's seal with it."]
        assert any("re-delivers" in w for w in ctx.warnings)
