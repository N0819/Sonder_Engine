"""A structured field must not name a body the prose beside it is withholding.

`agents.common.observer_label_fn` is the identity floor, written after
`perception.spatial_frame.ahead_entity` told a character who she was looking at
-- she had asked twice in dialogue, been refused both times, and used the
surname aloud six beats later. Its docstring says the rule covers "everything
else that hands a character a NAME". Two fields in the decision block never
went through it.

MEASURED, chat 104. A character whose every observation called the other body
"the young woman", and whose `known_pronouns` was EMPTY, was handed
`decision.their_name: "Hinami"`. Its own reasoning caught it -- "Wait, I don't
actually know her name is Hinami. That's in the decision field but not in my
perception" -- and declined to use it. A leak a model declines is still a leak:
the deterministic floor must not depend on a model cooperating.
"""
from __future__ import annotations

import json

from agents.character import _player_silence_note, _unanswered_question_note
from agents.common import observer_label_fn
from core.db import qi, wset


def _persona(name):
    return qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
              (name, json.dumps({"identity": {"name": name}})))


def _chat(persona_id):
    return qi("INSERT INTO chats(name,persona_id,created) VALUES('gate',?,0)",
              (persona_id,))


def _sheet(name):
    return {"identity": {"name": name}}


class TestTheSilenceNote:
    """`decision.player_name` is only reachable when the player is in the room
    and silent -- which is exactly when a character has least reason to have
    learned a name."""

    def _note(self, temp_db, *, knows):
        persona = _persona("Hinami")
        chat_id = _chat(persona)
        observer = "Veyla"
        # `known` is the world map perception itself gates on.
        wset(chat_id, "known", {observer: ["Hinami"] if knows else []})
        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                              one=True))
        scene = {"positions": {observer: "den", "Hinami": "den"},
                 "rooms": {"den": {}}}
        # No label passed ON PURPOSE: the gate must be the default, or a
        # caller that forgets it silently restores the leak.
        return _player_silence_note(scene, chat, _sheet(observer), False)

    def test_a_stranger_is_not_named(self, temp_db):
        note = self._note(temp_db, knows=False)
        assert note.get("player_said_nothing") is True
        assert note.get("player_name") != "Hinami", note

    def test_someone_known_is_still_named(self, temp_db):
        """The gate SUBTRACTS. A character who knows the name keeps it --
        withholding what a mind legitimately has is the opposite failure."""
        note = self._note(temp_db, knows=True)
        assert note.get("player_name") == "Hinami"

    def test_the_note_is_absent_when_they_spoke(self, temp_db):
        persona = _persona("Hinami")
        chat_id = _chat(persona)
        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                              one=True))
        scene = {"positions": {"Veyla": "den", "Hinami": "den"},
                 "rooms": {"den": {}}}
        assert _player_silence_note(scene, chat, _sheet("Veyla"), True) == {}


class TestTheUnansweredQuestionNote:
    def test_the_asker_passes_the_same_gate(self, temp_db):
        """Being asked a question by a stranger does not tell you their name."""
        seen = []

        def label(name):
            seen.append(name)
            return "the unfamiliar person"

        # No question is owed in an empty chat, so this asserts the plumbing:
        # the note accepts the gate its sibling now uses, and callers pass it.
        persona = _persona("Hinami")
        chat_id = _chat(persona)
        out = _unanswered_question_note(chat_id, "Veyla", 1, 5, None,
                                        label=label)
        assert out == {} or out["awaiting_your_answer"]["from"] \
            == "the unfamiliar person"


class TestBothCallSitesPassTheGate:
    """The functions accepting a label is worth nothing if character_step does
    not hand one over. This reads the call sites rather than trusting them."""

    def test_character_step_gates_both_fields(self):
        import inspect

        from agents import character

        src = inspect.getsource(character.character_step)
        assert "_player_silence_note(" in src
        assert "_unanswered_question_note(" in src
        # Both calls sit inside the decision block and must carry the label.
        for marker in ("_player_silence_note(", "_unanswered_question_note("):
            start = src.index(marker)
            window = src[start:start + 420]
            assert "label=_contact_label" in window, marker
