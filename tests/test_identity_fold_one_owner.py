"""One fold answers "is this name that name" (review 2026-09-07, item B34).

`story.character_schema.fold_identity_key` was written to retire the ASCII
squash `re.sub(r"[^a-z0-9]", "", name.casefold())`, which deletes every
non-Latin letter: a Japanese name folds to the EMPTY STRING, so a caller that
guards with `if norm:` silently stops matching and one that does not treats
distinct people as one. Fifteen live sites still carried the squash at the
review -- among them `story.scene.is_player_speaker`, which decides whether a
line of dialogue is the player's, and the Director's player awareness floor,
which is the guard that stops a gate being clamped on the player's own mind.

Both failed CLOSED, which is why a green suite and a running Japanese story
both looked fine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from agents.director import _norm_subject, _unsupported_player_awareness
from story import scene
from story.character_schema import default_persona_data, fold_identity_key

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402

# The persona as the card spells it, and the way a model writes it back:
# without the interpunct.
JA_PERSONA = "佐藤・ヒナミ"
JA_MODEL_SPELLING = "佐藤ヒナミ"
JA_OTHER_PERSON = "田中・ミナ"


def _make_persona(db, name):
    sheet = default_persona_data(name)
    return db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (name, json.dumps(sheet), "{}"),
    )


class TestTheFoldItself:
    def test_a_kana_name_survives_its_own_fold(self):
        assert fold_identity_key(JA_PERSONA) == JA_MODEL_SPELLING

    def test_two_different_kana_names_do_not_fold_together(self):
        # The squash returned "" for both, so anything comparing them without
        # an `if norm:` guard called them the same person.
        assert fold_identity_key(JA_PERSONA) != fold_identity_key(JA_OTHER_PERSON)

    def test_the_directors_subject_fold_is_the_same_fold(self):
        # director_floors carried a third spelling (`[\W_]+`) beside four
        # copies of the squash: three answers to one question.
        assert _norm_subject(JA_PERSONA) == fold_identity_key(JA_PERSONA)


class TestPlayerSpeaker:
    def test_a_kana_persona_matches_its_punctuation_variant(self, temp_db):
        chat = {"persona_id": _make_persona(temp_db, JA_PERSONA)}
        assert scene.is_player_speaker(JA_MODEL_SPELLING, chat) is True

    def test_the_latin_control_is_unchanged(self, temp_db):
        chat = {"persona_id": _make_persona(temp_db, "Alex Chen")}
        assert scene.is_player_speaker("Alex Chen", chat) is True
        assert scene.is_player_speaker("alex  chen", chat) is True
        assert scene.is_player_speaker("Alexandra", chat) is False

    def test_a_different_kana_speaker_is_not_the_player(self, temp_db):
        chat = {"persona_id": _make_persona(temp_db, JA_PERSONA)}
        assert scene.is_player_speaker(JA_OTHER_PERSON, chat) is False


class TestPlayerAwarenessFloor:
    def _conditions(self, subject):
        return {"c1": [{
            "condition_id": "c1", "subject_id": subject,
            "kind": "awareness", "state": {"level": "asleep"},
        }]}

    def test_the_floor_fires_for_a_kana_player(self):
        # The squash folded the player's name to "", the guard returned early
        # on `if not target`, and an unsupported gate on the PLAYER's own mind
        # went through unopposed.
        assert _unsupported_player_awareness(
            self._conditions(JA_MODEL_SPELLING), JA_PERSONA, "", "", [],
        ) == [("c1", "asleep")]

    def test_the_floor_leaves_another_persons_gate_alone(self):
        assert _unsupported_player_awareness(
            self._conditions(JA_OTHER_PERSON), JA_PERSONA, "", "", [],
        ) == []


class TestTheGuard:
    def test_no_engine_module_folds_a_name_by_hand(self):
        errors: list[str] = []
        pc.check_identity_fold_is_owned(errors)
        assert errors == []

    def test_a_new_squash_is_refused(self, tmp_path, monkeypatch):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text(
            'import re\n\n\ndef key(name):\n'
            '    return re.sub(r"[^a-z0-9]", "", str(name).casefold())\n',
            encoding="utf-8")
        monkeypatch.setattr(pc, "ROOT", tmp_path)
        monkeypatch.setattr(pc, "ENGINE_SOURCE_ROOTS", ("pkg",))
        errors: list[str] = []
        pc.check_identity_fold_is_owned(errors)
        assert len(errors) == 1 and "fold_identity_key" in errors[0]

    def test_a_tokenizer_and_an_id_slug_are_left_alone(self, tmp_path,
                                                       monkeypatch):
        # Different questions: splitting English words out of model prose, and
        # minting an ASCII id. Only the name-comparison fold is owned.
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text(
            'import re\n\n\ndef words(text):\n'
            '    return re.split(r"[^a-z0-9]+", text.casefold())\n\n\n'
            'def slug(text):\n'
            '    return re.sub(r"[^a-z0-9]+", "_", text.casefold())\n',
            encoding="utf-8")
        monkeypatch.setattr(pc, "ROOT", tmp_path)
        monkeypatch.setattr(pc, "ENGINE_SOURCE_ROOTS", ("pkg",))
        errors: list[str] = []
        pc.check_identity_fold_is_owned(errors)
        assert errors == []
