"""With no input there is nothing to interpret, and anything in the sequence is
the engine speaking for the player.

Live, chat 59 t154. The player's input was empty. `director_interpret` emitted

    speech:  "Kaa Sama Kaa Sama! You're cooking is simply to good to not indulge in."
    action:  "steps inside the shrine and looks around at the familiar sight of home"

— both the player's turn-150 declaration, verbatim, four beats stale. Tamamo
then thanked her for praise she had not given, and the whole beat proceeded
from a line nobody wrote.

This is the failure the PLAYER AUTHORITY CONTRACT exists to prevent, arriving
from the one direction nothing guarded: every other check compares the
Director's output against what the player declared, and here there was no
declaration to compare against.

Corpus: 10 turns carry an empty player input; 2 of them invented player speech.
The other was chat 10 t18, newly invented rather than replayed
("something reassuring").

The guard is deterministic rather than a prompt clause because an empty input
is unambiguous and the test costs nothing on any other beat. Silence remains a
thing the player DID — the beat still runs, and `_player_silence_note` still
tells characters about it. What no longer travels is words.
"""

from __future__ import annotations

import inspect

from agents import director


SRC = inspect.getsource(director.director_interpret)


class TestTheGuardExists:
    def test_it_keys_on_an_empty_raw_input(self):
        assert 'if not str(ctx.input or "").strip():' in SRC

    def test_it_clears_every_channel_a_declaration_travels_on(self):
        """`sequence` is what perception injects; `speech`/`action` are the
        scalar mirrors several stages read instead. Clearing one and leaving
        the others would move the fabrication rather than remove it.

        The row establishing the beat's places goes too: on an empty input
        the prose it was made from restates stale conduct, and a place that
        prose invents is as much a fabrication as the words. What survives is
        exactly the rooms the install built in when the beat opened, carried
        in the stage's assertions (`_silent_rooms`) -- kept whole, the row
        committed the invented place; cleared with nothing carried, the
        stub of a room the beat opened on built (reviews of the 2026-10-08
        rooms-in-view landing; `test_a_silent_beat_keeps_nothing_its_prose_made`,
        `test_a_silent_beat_keeps_the_rooms_it_opened_on`)."""
        block = SRC[SRC.index('if not str(ctx.input or "").strip():'):]
        block = block[:block.index("# A speech element that swallowed")]
        for field in ('out["sequence"] = []', 'out["speech"] = None',
                      'out["action"] = None', 'out["actions"] = []',
                      "_silent_rooms = _installed"):
            assert field in block, field
        assert "carry_installed_rooms(out, _silent_rooms)" in SRC

    def test_it_runs_before_anything_reads_the_sequence(self):
        """Downstream binds targets, routes authorial beats and injects speech
        verbatim; the fabrication has to be gone before any of that."""
        guard = SRC.index('if not str(ctx.input or "").strip():')
        for later in ("repair_narrated_speech_elements(out)",
                      "_route_authorial_npc_beat("):
            assert guard < SRC.index(later), later

    def test_it_reports_rather_than_silently_repairing(self):
        assert "discarded" in SRC
        assert "invented declaration" in SRC

    def test_it_tells_the_director_why(self):
        """The Director gets the correction on the next beat, or it repeats the
        mistake forever."""
        assert "not a cue to restate what they last said" in SRC


class TestItOnlyFiresOnSilence:
    def test_a_non_empty_input_is_untouched(self):
        """The clearing sits inside the empty-input branch, so a beat with any
        declaration at all passes through it entirely."""
        block = SRC[SRC.index('if not str(ctx.input or "").strip():'):]
        block = block[:block.index("# A speech element that swallowed")]
        # Everything that clears a field is indented inside the guard.
        for line in block.splitlines():
            if line.strip().startswith('out["'):
                assert line.startswith("        "), line

    def test_whitespace_only_counts_as_silence(self):
        assert '.strip()' in 'if not str(ctx.input or "").strip():'
