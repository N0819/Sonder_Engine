"""Did the player speak this beat -- one question, one answer.

Review 2026-09-07 finding A44. The `speech` scalar on `director_interpret` is
derived from `type == "speech"` sequence elements alone
(`common._sync_sequence_mirrors`), so a player who signed, wrote, gestured a
meaning or spoke down a radio emits a `communication` element and no `speech`
at all. Two readers asked the scalar a yes/no question it could not answer:
`character._player_silence_note`'s gate and `character._player_quiet_beats`.
The first then told every mind in the room the player had stood there saying
nothing, while `_unanswered_question_note` and
`narration._narrator_player_declared` -- reading the same beat off the
sequence, twenty lines away -- already counted it as speaking.

`narration._narrator_player_declared` was a third reading in its own right:
it walked the sequence and said True on an utterance element carrying no
text, where the helper says False -- so one beat could reach the narrator
marked as spoken while every mind in the room was told it was silent.

`common.player_communicated` is the one answer, and these tests hold all
three readers to it.
"""

from __future__ import annotations

import json

import agents.character as character
from agents.common import player_communicated


def _signed(content="hands lifted: come here"):
    """A beat the player communicated on with no spoken quote: the shape the
    scalar mirror cannot represent."""
    return {"sequence": [{"type": "communication", "act": "sign",
                          "content": content, "targets": ["Mara"],
                          "volume": "normal"}],
            "speech": None}


def _spoke(text="come here"):
    return {"sequence": [{"type": "speech", "text": text, "volume": "normal"}],
            "speech": text}


def _silent():
    return {"sequence": [{"type": "action", "attempt": "look at the door"}],
            "speech": None}


class TestTheHelper:
    def test_a_communication_with_no_quote_is_communicating(self):
        assert player_communicated(_signed()) is True

    def test_speech_is_communicating(self):
        assert player_communicated(_spoke()) is True

    def test_an_action_only_beat_is_not(self):
        assert player_communicated(_silent()) is False

    def test_the_scalar_still_answers_for_a_beat_that_has_no_sequence(self):
        """A stored beat from before the sequence field is the only record
        there is, so the mirror is the fallback and nothing more."""
        assert player_communicated({"speech": "come here"}) is True
        assert player_communicated({"speech": None}) is False
        assert player_communicated(None) is False

    def test_an_empty_utterance_is_not_one(self):
        assert player_communicated(
            {"sequence": [{"type": "communication", "content": "  "}]}) is False


class TestTheSilenceNote:
    """`player_said_nothing` is presence-as-signal: its presence IS the claim
    that the player stood here and said nothing."""

    def _note(self, spoke):
        sheet = {"identity": {"name": "Mara"}}
        # "The Stranger" is the default persona name a chat with no persona
        # row resolves to (`story.scene.persona_of`).
        scene = {"positions": {"Mara": "hall", "The Stranger": "hall"},
                 "rooms": {"hall": {"name": "hall"}},
                 "entities": {}, "attire": {}, "overlays": {}}
        chat = {"id": 1, "persona_id": None}
        return character._player_silence_note(
            scene, chat, sheet, spoke, quiet_beats=0, label=lambda n: n)

    def test_a_silent_beat_still_reports_silence(self):
        assert self._note(player_communicated(_silent())) != {}

    def test_a_signed_beat_does_not(self):
        """The defect: the player said something, in a channel the scalar
        does not mirror, and every mind in the room was told they had not."""
        assert self._note(player_communicated(_signed())) == {}


class TestTheQuietRun:
    """`_player_quiet_beats` counts CONSECUTIVE beats of silence, and the
    character prompt reads four differently from one."""

    def _rows(self, monkeypatch, interpreteds):
        rows = [{"idx": 9 - i, "content": json.dumps(d)}
                for i, d in enumerate(interpreteds)]
        monkeypatch.setattr(character, "_variant_window",
                            lambda cache, key, load: rows)
        return rows

    def test_a_run_of_silence_counts(self, monkeypatch):
        self._rows(monkeypatch, [_silent(), _silent()])

        assert character._player_quiet_beats(1, 10, None) == 3

    def test_a_signed_beat_ends_the_run(self, monkeypatch):
        """It ended the run for `_unanswered_question_note` already; here it
        was counted as another beat of not speaking."""
        self._rows(monkeypatch, [_silent(), _signed(), _silent()])

        assert character._player_quiet_beats(1, 10, None) == 2


class TestTheWiring:
    """The three readers ASK the helper -- checked at the source, because the
    beat the finding was written for cannot be reached from a unit test.

    `character_step` reads the answer once, into `_p_spoke`, and hands it to
    `_player_silence_note`; the note itself takes a boolean, so a test that
    computes the boolean correctly passes even with the caller reverted to the
    scalar. What has to hold is the WIRING, so that is what is asserted --
    the same shape the read-only-stage test in
    `test_recall_access_is_written_by_commit.py` uses (A78).
    """

    def _tree(self):
        import ast
        from pathlib import Path

        return ast.parse(Path(character.__file__).read_text(encoding="utf-8"))

    def _calls(self, node):
        import ast

        return {c.func.id for c in ast.walk(node)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}

    def test_the_silence_gate_asks_the_helper(self):
        """`_p_spoke` is what gates the note every mind in the room reads."""
        import ast

        tree = self._tree()
        assigns = [n for n in ast.walk(tree)
                   if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_p_spoke"
                           for t in n.targets)]

        assert assigns, "character.py no longer computes _p_spoke"
        for node in assigns:
            assert "player_communicated" in self._calls(node), (
                "the silence gate reads the `speech` scalar again: a beat the "
                "player signed, wrote or radioed tells every mind in the room "
                "they stood there saying nothing (A44)")

    def test_the_quiet_run_asks_the_helper(self):
        import ast

        fn = next(n for n in ast.walk(self._tree())
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_player_quiet_beats")

        assert "player_communicated" in self._calls(fn)

    def test_the_narrator_asks_the_helper_too(self):
        """The third reading (A44 rework): `_narrator_player_declared` walked
        the sequence itself and answered True where the helper answers False.
        Its loop still builds the sequence; the yes/no is the helper's."""
        import ast
        from pathlib import Path

        import agents.narration as narration

        tree = ast.parse(
            Path(narration.__file__).read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_narrator_player_declared")

        assert "player_communicated" in self._calls(fn)

    def test_the_narrator_and_the_silence_note_cannot_disagree(self):
        """The two answers, on the beat they used to differ on: an utterance
        element carrying nothing."""
        import agents.narration as narration

        empty = {"sequence": [{"type": "communication", "act": "sign",
                               "content": "  ", "targets": ["Mara"]}],
                 "speech": None}

        assert narration._narrator_player_declared(empty)["spoke"] is (
            player_communicated(empty))
        assert narration._narrator_player_declared(_signed())["spoke"] is True
        assert narration._narrator_player_declared(_silent())["spoke"] is False
