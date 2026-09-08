"""Presence and address are statements about people, not about spelling.

Review 2026-09-07 A34. Two floors read English literals and literal scene
keys:

- `_scene_has_subject` exempted nine English self-words and compared the
  scene's keys verbatim, so a participant written in the story's own
  language, or by the uid / `character:<id>` spelling the engine itself
  hands out, was a "missing participant". The phase is then `blocked`,
  `prune_blocked_phase_changes` deletes every record sourced from it, and
  the beat loses the change.
- `_asks_player` matched three English aliases and an ASCII "?", so in a
  Japanese story the interaction loop never stopped for a question and the
  beat ran on past the player.
"""
import json

from language_runtime import language_scope
from story.character_schema import default_character_data

from agents.common import (_asks_player, _scene_has_subject,
                           cast_spelling_policy,
                           settle_sequence_dispositions)

SCENE = {"positions": {"Reya": "hall", "Alex": "hall"}, "entities": {}}


def _cast(aliases=()):
    sheet = default_character_data("Reya")
    sheet["identity"]["uid"] = "reya_uid"
    if aliases:
        sheet["identity"]["aliases"] = list(aliases)
    return [{"id": 7, "sheet": json.dumps(sheet)}]


def _canonical():
    return cast_spelling_policy(_cast(), "Alex")[0]


def test_a_self_word_in_the_storys_language_is_not_a_missing_participant():
    with language_scope("ja"):
        assert _scene_has_subject(SCENE, "自分")
        assert _scene_has_subject(SCENE, "あなた")
    assert _scene_has_subject(SCENE, "self")
    assert _scene_has_subject(SCENE, "you")
    # The pack states who counts; a body that is simply absent still does not.
    assert not _scene_has_subject(SCENE, "Ilsabet")


def test_a_body_named_by_uid_or_cast_key_is_present():
    canonical = _canonical()
    for spelling in ("character:7", "reya_uid", "Reya"):
        assert _scene_has_subject(SCENE, spelling, canonical), spelling
    assert not _scene_has_subject(SCENE, "character:7"), \
        "without the resolver the literal key is all there is"
    assert not _scene_has_subject(SCENE, "Ilsabet", canonical)


def test_a_phase_is_not_blocked_for_a_participant_spelled_as_a_cast_key():
    sequence = [{"event_id": "e1", "type": "action", "attempt": "opens it",
                 "participants": ["character:7"]}]
    blind = settle_sequence_dispositions(sequence, {}, SCENE)
    assert blind[0]["status"] == "blocked"
    seeing = settle_sequence_dispositions(sequence, {}, SCENE,
                                          _cast(), "Alex")
    assert seeing[0]["status"] == "executed"
    assert seeing[0]["reason"] == ""


def test_a_question_in_the_storys_own_punctuation_awaits_the_player():
    asked = {"interaction": {"addresses": []},
             "sequence": [{"type": "speech", "text": "本当にいいのか？"}]}
    with language_scope("ja"):
        assert _asks_player(asked, {}) is True
    ascii_asked = {"interaction": {"addresses": []},
                   "sequence": [{"type": "speech", "text": "Are you sure?"}]}
    assert _asks_player(ascii_asked, {}) is True


def test_addressing_the_player_by_a_cast_key_awaits_them(temp_db):
    import time

    from core.pipeline_context import ChatData
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()))
    chat = ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                    scenario="", created=time.time())
    result = {"interaction": {"addresses": ["character:player"]},
              "sequence": [{"type": "speech", "text": "It is done."}]}
    # The engine's own key for the player resolves to the player.
    assert _asks_player(result, chat, _cast()) is True
    result["interaction"]["addresses"] = ["you"]
    assert _asks_player(result, chat, _cast()) is True
    # A uid names the cast member it identifies, so the trailing-question
    # fallback stands down exactly as it does for that member's sheet name.
    asked = {"interaction": {"addresses": ["reya_uid"]},
             "sequence": [{"type": "speech", "text": "Are you sure?"}]}
    assert _asks_player(asked, chat, _cast()) is False
    asked["interaction"]["addresses"] = ["Reya"]
    assert _asks_player(asked, chat, _cast()) is False


def test_an_alias_is_one_of_that_bodys_spellings_too(temp_db):
    """The widening the skeptic asked to have pinned: `cast_names` used to
    hold sheet NAMES, and now holds every spelling `cast_spelling_policy`
    registers -- aliases included. So an NPC addressed as "Doc" stands the
    trailing-'?' fallback down exactly as "Reya" does, where before the
    question was read as one awaiting the player. An alias nobody registered
    still names nobody, and the fallback stands."""
    import time

    from core.pipeline_context import ChatData
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()))
    chat = ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                    scenario="", created=time.time())
    asked = {"interaction": {"addresses": ["Doc"]},
             "sequence": [{"type": "speech", "text": "Are you sure?"}]}
    assert _asks_player(asked, chat, _cast(aliases=["Doc"])) is False
    assert _asks_player(asked, chat, _cast()) is True
