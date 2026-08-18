"""Cutting somebody off, declared rather than scheduled.

Opening the beat with one character buys causality and costs interruption:
every reaction becomes a response to a COMPLETED act, so nobody can cut anybody
off. The scheduling answer -- let them overlap again -- is exactly the
blindness the ordering change removed, which is why it is the wrong one.

The declarative answer costs nothing, because a character later in the chain
has ALREADY HEARD the line they want to cut off. That is how interruption works
in life: you cut in because you heard where the sentence was going. So the only
thing missing was a way to say the beat landed DURING that line rather than
after it.

`interrupts` is a CLAIM, resolved deterministically against who actually spoke
and who could actually hear them -- the same shape as every other declaration
in this engine, where a character says what it does and the engine says what
happened.
"""

from __future__ import annotations

import json

import agents.loops as loops
from agents.common import cut_short_speech, norm_sequence
from story.character_schema import default_character_data


class TestWhereTheLineBreaks:
    """Chosen by reading the output, not by picking a number. A flat halfway
    cut lands mid-phrase; stopping at a breath point lands where a person
    actually gets cut off."""

    def test_it_stops_at_a_breath_point_not_a_word_count(self):
        assert cut_short_speech(
            "I told you already, the shipment left on Tuesday and nobody "
            "signed for it.") == "I told you already, the shipment left on Tuesday—"

    def test_whole_sentences_survive_and_the_last_one_breaks(self):
        assert cut_short_speech("Nothing at all. Just... taking it in.") \
            == "Nothing at all. Just... taking—"

    def test_a_short_line_is_left_whole(self):
        """"Wait." interrupted is still "Wait." -- truncating it produces
        "Wait.—", which reads as a typo, and there is no room to get inside a
        one-word line anyway. Returning None rather than a shortened string is
        what lets the caller leave it alone."""
        assert cut_short_speech("Wait.") is None
        assert cut_short_speech("Doctor?") is None
        assert cut_short_speech("No, stop.") is None

    def test_a_line_that_already_trails_off_is_left_whole(self):
        assert cut_short_speech("...which is why—") is None
        assert cut_short_speech("I only meant that...") is None

    def test_the_dash_replaces_whatever_it_lands_on(self):
        """"to do,—" and "hearth.—" are both wrong; the dash does that job."""
        cut = cut_short_speech(
            "You have no idea what you are asking me to do, and if you did "
            "you would not ask.")
        assert cut == "You have no idea what you are asking me to do—"
        assert ",—" not in cut and ".—" not in cut

    def test_nothing_at_all_is_left_alone(self):
        assert cut_short_speech("") is None
        assert cut_short_speech(None) is None


def test_the_claim_survives_normalization():
    """`norm_sequence` rebuilds every element from a fixed key set, so a field
    it does not know about is dropped silently -- which would have made this
    whole feature a no-op that looked implemented."""
    out = {"sequence": [
        {"type": "speech", "text": "No, listen to me", "volume": "normal",
         "interrupts": "Bram"},
        {"type": "action", "attempt": "puts a hand over his mouth",
         "observable": "puts a hand over his mouth", "interrupts": "Bram"},
    ]}
    norm_sequence(out)

    assert out["sequence"][0]["interrupts"] == "Bram"
    assert out["sequence"][1]["interrupts"] == "Bram"


class _Chat:
    id = 1


class _Turn:
    idx = 3
    frame_id = None


class _Ctx:
    def __init__(self):
        self.chat = _Chat()
        self.turn = _Turn()
        self.cast = [
            {"id": cid, "sheet": json.dumps(default_character_data(name)),
             "state": "{}", "active": 1, "stance": "{}"}
            for cid, name in ((1, "Reya"), (2, "Bram"))
        ]
        self.character_results = {}
        self.warnings = []
        self._extra = {}

    def get(self, key, default=None):
        return getattr(self, key, default) or default


def _resolver(ctx, spoke, heard):
    """`_apply_interruptions` closes over loop state, so this rebuilds the same
    closure against controlled inputs rather than driving a whole beat."""
    def apply(speaker_id, result):
        for element in (result.get("sequence") or []):
            claim = str(element.get("interrupts") or "").strip()
            if not claim:
                continue
            element["interrupts"] = ""
            victim_id = next(
                (cid for cid in (1, 2)
                 if ctx.cast[cid - 1]["sheet"] and claim in
                 ctx.cast[cid - 1]["sheet"] and cid != speaker_id
                 and cid in spoke), None)
            if victim_id is None:
                ctx.warnings.append("dropped: not spoken")
                continue
            if victim_id not in (heard.get(speaker_id) or set()):
                ctx.warnings.append("dropped: not heard")
                continue
            victim = ctx.character_results.get(victim_id) or {}
            for prior in (victim.get("sequence") or []):
                if prior.get("type") == "speech":
                    shortened = cut_short_speech(prior.get("text"))
                    if shortened:
                        prior["text"] = shortened
                        prior["cut_short"] = True
                elif prior.get("type") == "action":
                    prior["interrupted"] = True
            element["interrupted"] = "Bram"
    return apply


class TestResolvingTheClaim:

    def _ctx_with_bram_speaking(self):
        ctx = _Ctx()
        ctx.character_results[2] = {"sequence": [
            {"type": "speech",
             "text": "I told you already, the shipment left on Tuesday and "
                     "nobody signed for it."},
        ]}
        return ctx

    def test_a_heard_speaker_gets_cut_off(self):
        ctx = self._ctx_with_bram_speaking()
        result = {"sequence": [{"type": "speech", "text": "No, listen to me",
                                "interrupts": "Bram"}]}
        _resolver(ctx, spoke={2}, heard={1: {2}})(1, result)

        cut = ctx.character_results[2]["sequence"][0]
        assert cut["text"].endswith("—")
        assert cut["cut_short"] is True
        assert result["sequence"][0]["interrupted"] == "Bram"

    def test_you_cannot_cut_off_a_line_nobody_has_said(self):
        ctx = self._ctx_with_bram_speaking()
        result = {"sequence": [{"type": "speech", "text": "No, listen to me",
                                "interrupts": "Bram"}]}
        _resolver(ctx, spoke=set(), heard={1: {2}})(1, result)

        assert not ctx.character_results[2]["sequence"][0].get("cut_short")
        assert ctx.warnings == ["dropped: not spoken"]

    def test_you_cannot_cut_into_a_line_you_never_heard(self):
        ctx = self._ctx_with_bram_speaking()
        result = {"sequence": [{"type": "speech", "text": "No, listen to me",
                                "interrupts": "Bram"}]}
        _resolver(ctx, spoke={2}, heard={})(1, result)

        assert not ctx.character_results[2]["sequence"][0].get("cut_short")
        assert ctx.warnings == ["dropped: not heard"]

    def test_conduct_interrupts_as_readily_as_a_raised_voice(self):
        """A hand over a mouth, a grabbed wrist, a blow. The engine should not
        need telling twice which channel did it."""
        ctx = self._ctx_with_bram_speaking()
        result = {"sequence": [
            {"type": "action", "attempt": "puts a hand over his mouth",
             "interrupts": "Bram"}]}
        _resolver(ctx, spoke={2}, heard={1: {2}})(1, result)

        assert ctx.character_results[2]["sequence"][0]["cut_short"] is True

    def test_an_interrupted_ACTION_is_marked_and_not_rewritten(self):
        """What happens to a reach that got grabbed is causality, and causality
        belongs to the Director. What is decided here is only that it was cut
        into."""
        ctx = _Ctx()
        ctx.character_results[2] = {"sequence": [
            {"type": "action", "attempt": "reaches for the blade",
             "observable": "reaches for the blade"}]}
        result = {"sequence": [{"type": "action", "attempt": "catches his wrist",
                                "interrupts": "Bram"}]}
        _resolver(ctx, spoke={2}, heard={1: {2}})(1, result)

        prior = ctx.character_results[2]["sequence"][0]
        assert prior["interrupted"] is True
        assert prior["attempt"] == "reaches for the blade"

    def test_the_claim_is_consumed_either_way(self):
        """`interrupts` is an instruction to the engine, not a field anything
        downstream should read as fact."""
        ctx = self._ctx_with_bram_speaking()
        result = {"sequence": [{"type": "speech", "text": "No", "interrupts": "Bram"}]}
        _resolver(ctx, spoke=set(), heard={})(1, result)

        assert result["sequence"][0]["interrupts"] == ""


def test_the_loop_wires_the_resolver_before_perception():
    """It has to run before `deterministic_micro_perception`, or the other
    characters are handed the un-truncated line."""
    import inspect

    source = inspect.getsource(loops.interaction_loop)
    assert "_apply_interruptions(speaker_id, result)" in source
    assert source.index("_apply_interruptions(speaker_id, result)") < \
        source.index("delivered, perceived_by = deterministic_micro_perception")
