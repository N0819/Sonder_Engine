"""How long a beat took is summed by code from what the author priced.

THE DEFECT THIS CLOSES. `state_diff.time` was the spatial specialist's
channel, and a specialist is handed `_specialist_span_slice` -- the rows
selected for it, never the beat. Its own chunk asked it for the total ("a
beat that holds several things in sequence spans all of them: the time is the
sum of its parts") while the fan-out handed it a subset of those parts, so it
was being asked for a sum over terms it could not see. It declined, which is
the correct answer to that question, and the clock stopped: measured
2026-09-20, `time` was in the hand's scope on 38 of 60 playerless beats
(two_lives v11) and on 50 of 118 live beats since 2026-09-15, and was written
on 0 of either, while across 3,000 stored `director_resolve` variants the
author routed the `time` category 0 times -- so the hand never received a
time work item in the first place. Every beat therefore fell to
`UNCLAIMED_BEAT_SECONDS`, which handed the charter 0.0028 hours per beat and
froze the off-screen world.

The prose author is the one agent that sees the beat whole, because it cuts
the steps. So it prices each step it cut and code adds them up.
"""

import json

from agents.director import (SPECIALISTS, _DELEGATED_CHANNELS,
                             _specialist_ledger, normalize_causal_ledger)
from llm import prompts, schemas
from world.mechanics import (UNCLAIMED_BEAT_SECONDS, beat_end_elapsed,
                             beat_time_from_spans, time_diff_claims)


def _row(chrono, **kw):
    row = {"chrono_id": chrono, "item_ids": [chrono], "item_names": ["a thing"],
           "source_entity_id": "character:1", "source_event_id": "scene:1",
           "event": "something happens", "categories": []}
    row.update(kw)
    return row


class TestTheSum:
    """`beat_time_from_spans` is the only place a beat's span is totalled."""

    def test_a_beat_is_the_sum_of_the_steps_its_author_cut(self):
        spans = [_row(1, seconds=5), _row(2, seconds=25), _row(3, seconds=2.5)]
        assert beat_time_from_spans(spans) == {"duration_seconds": 32.5}

    def test_a_night_lands_whole(self):
        """A span survives a translation a position does not, so a time skip
        needs no absolutes and no second field: eight hours is eight hours."""
        block = beat_time_from_spans([_row(1, seconds=28800)])
        assert block == {"duration_seconds": 28800.0}
        assert beat_end_elapsed(1000.0, block, floor=True)[0] == 29800.0

    def test_a_beat_nobody_priced_is_still_charged_the_floor(self):
        """Silence keeps the behaviour it has today -- the floor -- rather than
        acquiring a guess. A None return is how this reader says nothing."""
        assert beat_time_from_spans([_row(1), _row(2)]) is None
        assert beat_time_from_spans([]) is None
        assert beat_time_from_spans(None) is None
        elapsed, _displaced, _refused, floored = beat_end_elapsed(
            100.0, None, floor=True)
        assert floored and elapsed == 100.0 + UNCLAIMED_BEAT_SECONDS

    def test_an_unpriced_step_beside_a_priced_one_contributes_nothing(self):
        """Under-ageing a body is recoverable; over-ageing it is not
        (`time_diff_duration`'s own doctrine). A row that named no number is
        not charged an average of the ones that did."""
        assert beat_time_from_spans(
            [_row(1, seconds=30), _row(2), _row(3, seconds=None)]
        ) == {"duration_seconds": 30.0}

    def test_a_number_this_reader_cannot_act_on_is_silence(self):
        """The same answer `time_diff_claims` gives for an unreadable claim.
        A negative span is not clamped into the beat and a string that is not
        a number is not counted as one."""
        for bad in ("soon", -30, float("inf"), float("nan"), True, [12]):
            assert beat_time_from_spans([_row(1, seconds=bad)]) is None, bad

    def test_a_step_may_say_it_took_no_time(self):
        """Zero is a CLAIM, not silence: it turns the floor off, which is how
        a beat keeps the authority to say no time passed by saying it."""
        block = beat_time_from_spans([_row(1, seconds=0)])
        assert block == {"duration_seconds": 0.0}
        assert time_diff_claims(block)
        assert beat_end_elapsed(500.0, block, floor=True) == (500.0, None, [], False)


class TestTheRowCarriesIt:
    """A field the normalizer's key list forgets is dropped without a word."""

    def test_the_normalizer_carries_seconds_onto_the_ledger(self):
        out = {"ledgers": [_row(1, seconds=12), _row(2, seconds="45"), _row(3)]}
        normalize_causal_ledger(out)
        assert [row["seconds"] for row in out["causal_ledger"]] == \
            [12.0, 45.0, None]

    def test_an_unreadable_number_is_recorded_as_unpriced(self):
        """The persisted ledger says what the author actually priced, so a
        reader downstream never has to re-parse the model's spelling."""
        out = {"ledgers": [_row(1, seconds="a while")]}
        normalize_causal_ledger(out)
        assert out["causal_ledger"][0]["seconds"] is None

    def test_the_schema_declares_it(self):
        """Declared everywhere, still unroutable: the field has to exist on
        the model the author's output validates against, or the round trip
        discards it before any of the above can run."""
        entry = schemas.CausalLedgerEntry(**_row(1, seconds=7))
        assert entry.seconds == 7.0
        assert schemas.CausalLedgerEntry(**_row(1)).seconds is None


class TestTheBeatIsBothLedgers:
    """A beat's steps are the interpret rows plus the resolve rows."""

    def test_the_two_stages_are_disjoint_and_both_count(self):
        """`_causal_event_inputs` withholds already-asserted human conduct
        from resolve, so the player's declared acts are priced once, on their
        own stage. Summing resolve alone drops them -- and a declared sleep,
        the field's whole reason for existing, lands on an interpret row."""
        declared = [_row(1, seconds=28800, commitment="asserted")]
        answered = [_row(1, seconds=5), _row(2, seconds=10)]
        assert beat_time_from_spans(declared + answered) == \
            {"duration_seconds": 28815.0}

    def test_a_contested_declaration_is_priced_by_its_outcome(self):
        """The one row that must NOT be counted from interpret: a contestable
        declaration is passed through to resolve and re-cut there, so
        counting both spellings would charge the beat twice. Keyed on the
        engine's own asserted/contestable split, never on matching prose."""
        rows = [_row(1, seconds=600, commitment="contestable")]
        kept = [row for row in rows
                if str(row.get("commitment") or "").casefold() != "contestable"]
        assert kept == []
        assert beat_time_from_spans(kept) is None


class TestNoHandIsAskedForIt:
    """One writer. The channel left the hand that could not compute it."""

    def test_no_specialist_owns_time(self):
        for name, spec in SPECIALISTS.items():
            assert "time" not in spec["channels"], name
        assert "time" not in _DELEGATED_CHANNELS
        assert "time" not in schemas.SPECIALIST_CHANNELS["director_spatial"]

    def test_no_spatial_sheet_still_teaches_the_channel(self):
        """The chunk went with the grant. A sheet that still asked for a
        duration would be instructing a hand to write a channel the
        orchestrator now drops from it -- the inverse of the defect."""
        spec = prompts.SPECIALIST_PROMPT_SPECS["spatial"]
        assert "time" not in spec["chunks"]
        assert "time" not in spec["order"]

    def test_a_hand_is_never_shown_the_price(self):
        """What a hand could do with a duration is re-derive a total it cannot
        see the terms of -- the same reasoning that keeps `authority_mode`
        off a hand's row."""
        visible = _specialist_ledger(_row(1, seconds=30))
        assert "seconds" not in visible


class TestTheAuthorIsAsked:
    """A schema field nothing asks for is filled on no beat at all, which is
    how `time` came to have a typed home and zero writers."""

    def test_every_shipped_author_sheet_asks_for_the_span(self):
        for language in ("en", "ja"):
            sheet = prompts.prose_author_prompt(None, language=language)
            assert "seconds" in sheet, language

    def test_the_worked_example_prices_its_own_steps(self):
        """The example is the shape the model copies. An envelope whose rows
        carry no span teaches that the field is optional in practice."""
        sheet = prompts.prose_author_prompt(None, language="en")
        envelope = sheet[sheet.index('{"ledgers"'):]
        rows = json.loads(envelope[:envelope.rindex("}") + 1])["ledgers"]
        assert rows and all("seconds" in row for row in rows)
