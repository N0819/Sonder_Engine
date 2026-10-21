"""A VOICE ON THE CARD IS HEARD UNSEEN (DESIGN_SOUND_FIELD.md § 18, round 2,
lane D, 2026-10-20; the owner's § 12.6 question 9).

Real world: a stranger's voice through a door tells you what a body is
recognised by when it speaks -- a woman's or a man's, young or old, its
timbre, its accent -- before you know whose it is.

What existed: an unseen stranger was described by `social.voice.register`
(how the voice is USED: "clinical, deadpan, and strictly monotone"), filled
on 61 of the owner's 70 characters; a persona had no voice field at all, so
the player's voice was nothing to anyone who heard it unseen; and nothing on
either card carried a voice's sex, rough age or accent as a fact about
sound.

The class:

  1. `embodiment.voice` is on both card shapes -- the hearing sibling of
     `visible.summary` and `scent`, empty by default like them -- and is
     carried through every surface a card comes from: the blank card, the
     normalizer (a flat persona's included), the appearance fill's merge,
     the per-story override, the portable archive;
  2. a listener who hears a body and cannot see it is given the card's
     voice once, ahead of the register, and never a name; the register's
     SHAPE floor does not apply to a field authored for this sentence;
  3. a seen speaker keeps the register in the manner slot, as before;
  4. the player's voice reaches the cast through the persona
     (`perception._voice_sound_for`).
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from agents import composer
from agents.composer import body_key, render_view, standing_key
from story.character_schema import (character_voice_sound, default_character_data,
                                    default_persona_data, normalize_character_data,
                                    normalize_persona_data, persona_voice_sound)

REGISTER = "Low contralto, warm and unhurried."
SOUND = "A woman's, past fifty, with the clipped vowels of the coast."
SAID = "The voice is a woman's, past fifty, with the clipped vowels of the coast."
OPEN = {"same_room": False, "barrier": "open_door"}
DOOR = {"same_room": False, "barrier": "closed_door", "distance": "near"}
WALL = {"same_room": False, "barrier": "wall", "distance": "near"}
SEEN = {"same_room": True, "barrier": "open", "tier": "near"}


def _line(volume="normal", text="The boat leaves at dawn."):
    return {"speaker": "Verolla", "exact_quote": text, "volume": volume,
            "intended_target": "Ivo", "tone": ""}


def _p(rel, *, volume="normal", display="a voice", can_see=False,
       voice=REGISTER, sound=SOUND, prev=frozenset(), order_key=0, text=None):
    return composer.speech_percept(
        _line(volume, text or "The boat leaves at dawn."), rel, "Eve",
        display=display, can_see=can_see, voice=voice, voice_sound=sound,
        prev_standing=prev, order_key=order_key,
        bearing="" if can_see else "through the door")


# --- 1. the field, on every surface --------------------------------------------

def test_both_card_shapes_carry_an_empty_voice_beside_the_scent():
    for sheet in (default_character_data("Ivo"), default_persona_data("Eve")):
        assert sheet["embodiment"]["voice"] == ""
        assert "scent" in sheet["embodiment"]
    card = default_character_data("Ivo")
    card["embodiment"]["voice"] = " " + SOUND + " "
    assert normalize_character_data(card)["embodiment"]["voice"] == " " + SOUND + " "
    assert character_voice_sound(card) == SOUND
    assert character_voice_sound(default_character_data("Ivo")) == ""
    persona = default_persona_data("Eve")
    persona["embodiment"]["voice"] = SOUND
    assert persona_voice_sound(persona) == SOUND
    # A flat persona keeps its body where the schema keeps one, voice
    # included (the Kirinoura shape, scratch chat 167).
    flat = {"name": "Eve", "appearance": "A tall woman.",
            "embodiment": {"voice": SOUND}}
    assert normalize_persona_data(flat)["embodiment"]["voice"] == SOUND
    assert normalize_persona_data(flat)["embodiment"]["visible"]["summary"] \
        == "A tall woman."


def test_the_appearance_fill_merges_a_voice_the_model_wrote_and_keeps_silence(
        temp_db, monkeypatch):
    from story import importers
    card = default_character_data("The Vessel")
    card["embodiment"]["voice"] = "A boy's, unbroken."
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("The Vessel", json.dumps(card), "{}", time.time(), "char_vessel"))
    seen = {}

    def _reply(role, system, user, **k):
        seen.update(json.loads(user))
        return json.dumps({"embodiment": {"voice": SOUND},
                           "initial_outfit": {}})
    monkeypatch.setattr(importers, "chat_complete", _reply)
    sheet = importers.fill_appearance(
        "character", char_id, "", draft={"voice": "typed, unsaved"})
    assert sheet["embodiment"]["voice"] == SOUND
    assert seen["author_draft"]["voice"] == "typed, unsaved"
    assert seen["card"]["embodiment"]["voice"] == "A boy's, unbroken."
    # Silence is not a deletion: a model that omits the field leaves the
    # author's voice alone.
    monkeypatch.setattr(importers, "chat_complete",
                        lambda *a, **k: json.dumps({"initial_outfit": {}}))
    sheet = importers.fill_appearance("character", char_id, "")
    assert sheet["embodiment"]["voice"] == "A boy's, unbroken."


@pytest.fixture
def client(temp_db):
    from web import app as app_module
    from web import guest_access as guest
    guest.reset_host_account()
    with TestClient(app_module.app) as test_client:
        response = test_client.post(
            "/api/auth/setup", json={"username": "host", "password": "pw12345"})
        assert response.status_code == 200, response.text
        yield test_client
    guest.reset_host_account()


def _story(temp_db):
    base = default_character_data("Mara")
    base["psychology"]["drive"]["essence"] = "Protect the archive"
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(base), "{}", time.time(), base["identity"]["uid"]))
    persona = default_persona_data("Ivo")
    persona["embodiment"]["voice"] = "A man's, young, with a lisp."
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Ivo", json.dumps(persona), "{}", persona["identity"]["uid"]))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Story A", "", time.time(), persona_id))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps({})))
    return {"char_id": char_id, "persona_id": persona_id, "chat_id": chat_id,
            "base": base}


def test_the_per_story_override_carries_the_voice_and_cannot_rekey_identity(
        client, temp_db):
    from story.scene import active_cast
    story = _story(temp_db)
    participant = next(
        p for p in client.get(f"/api/chats/{story['chat_id']}").json()["participants"]
        if p["id"] == story["char_id"])
    sheet = json.loads(participant["sheet"])
    sheet["embodiment"]["voice"] = SOUND
    response = client.put(
        f"/api/chats/{story['chat_id']}/characters/{story['char_id']}/card",
        json={"sheet": sheet})
    assert response.status_code == 200, response.text
    override = json.loads(temp_db.q(
        "SELECT sheet FROM chat_chars WHERE chat_id=? AND char_id=?",
        (story["chat_id"], story["char_id"]), one=True)["sheet"])
    assert override["embodiment"]["voice"] == SOUND
    assert override["identity"]["uid"] == story["base"]["identity"]["uid"]
    assert override["identity"]["name"] == "Mara"
    assert character_voice_sound(
        json.loads(active_cast(story["chat_id"])[0]["sheet"])) == SOUND
    # The library card is untouched, and an edit cannot rekey the identity.
    library = json.loads(temp_db.q(
        "SELECT sheet FROM characters WHERE id=?", (story["char_id"],),
        one=True)["sheet"])
    assert library["embodiment"]["voice"] == ""
    renamed = json.loads(json.dumps(sheet))
    renamed["identity"]["name"] = "Not Mara"
    assert client.put(
        f"/api/chats/{story['chat_id']}/characters/{story['char_id']}/card",
        json={"sheet": renamed}).status_code == 400


def test_the_portable_archive_carries_the_voice_on_every_card(client, temp_db):
    from story.scene import active_cast, persona_of
    story = _story(temp_db)
    base = json.loads(json.dumps(story["base"]))
    base["embodiment"]["voice"] = SOUND
    temp_db.qi("UPDATE characters SET sheet=? WHERE id=?",
               (json.dumps(base), story["char_id"]))
    override = json.loads(json.dumps(base))
    override["embodiment"]["voice"] = "A girl's, in this story."
    temp_db.qi("UPDATE chat_chars SET sheet=? WHERE chat_id=? AND char_id=?",
               (json.dumps(override), story["chat_id"], story["char_id"]))
    exported = client.get(f"/api/chats/{story['chat_id']}/export")
    assert exported.status_code == 200, exported.text
    payload = exported.json()
    text = json.dumps(payload)
    assert SOUND in text and "A girl's, in this story." in text \
        and "A man's, young, with a lisp." in text
    # The route's body contract: the archive under a `data` member.
    imported = client.post("/api/chats/import", json={"data": payload})
    assert imported.status_code == 200, imported.text
    new_chat = imported.json().get("chat_id") or imported.json().get("id")
    assert new_chat and new_chat != story["chat_id"]
    cast = active_cast(new_chat)
    assert character_voice_sound(json.loads(cast[0]["sheet"])) \
        == "A girl's, in this story."
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (new_chat,), one=True))
    assert persona_voice_sound(persona_of(chat)) == "A man's, young, with a lisp."


# --- 2. and 3. what a listener in the dark is told ----------------------------

def test_an_unseen_strangers_voice_is_the_cards_sound_ahead_of_the_register():
    for rel, fidelity in ((OPEN, "full"), (DOOR, "fragment"), (WALL, "voice")):
        p = _p(rel, volume="loud" if rel is WALL else "normal")
        assert p.fidelity == fidelity
        text = render_view([p], mode="player", language="en").text
        assert text.endswith(SAID), text
        assert "Verolla" not in text and "contralto" not in text
    # No register at all: the sound alone is enough to say, and to key.
    p = _p(OPEN, voice="")
    assert p.data["voice_apart"] == SAID[len("The voice is "):-1]
    assert render_view([p], mode="player", language="en").text.endswith(SAID)
    # No sound on the card: the register, as wave A built it.
    p = _p(OPEN, sound="")
    assert render_view([p], mode="player", language="en").text.endswith(
        "The voice is low contralto, warm and unhurried.")
    # Neither: "a voice", as before.
    bare = render_view([_p(OPEN, voice="", sound="")], mode="player",
                       language="en").text
    assert "The voice is" not in bare


def test_the_name_guard_holds_and_the_registers_shape_floor_does_not_apply():
    # A sound that names its owner is withheld whole, and the register
    # (which fits) is said instead; a sound that is a long clause -- four
    # words to a part, more than the manner slot admits -- is said, because
    # the field is authored for this sentence and not for the slot.
    named = _p(OPEN, sound="Verolla's own low purr.")
    assert named.data["voice_apart"] == "low contralto, warm and unhurried"
    assert composer._fits_the_manner_slot(SOUND) is False
    assert _p(OPEN).data["voice_apart"] == SAID[len("The voice is "):-1]
    # And the register's own floor is unchanged: a register that is a
    # clause is still withheld from a listener in the dark.
    clause = "the voice of someone who has smoked for years and spent them shouting"
    assert "voice_apart" not in _p(OPEN, voice=clause, sound="").data


def test_a_voice_heard_once_is_not_described_again_and_the_old_key_survives():
    first = render_view([_p(OPEN)], mode="player", language="en")
    key = standing_key("voice", (body_key("Verolla"),), (REGISTER, SOUND))
    assert key in first.standing_keys
    again = render_view([_p(OPEN, prev=frozenset({key}))], mode="player",
                        language="en").text
    assert "The voice is" not in again
    # A card with no sound keys exactly as it did before the field existed.
    old = standing_key("voice", (body_key("Verolla"),), (REGISTER,))
    assert old in render_view([_p(OPEN, sound="")], mode="player",
                              language="en").standing_keys


def test_a_seen_speaker_keeps_the_register_in_the_manner_slot():
    seen = _p(SEEN, display="the tall woman", can_see=True)
    assert "voice_apart" not in seen.data
    text = render_view([seen], mode="player", language="en").text
    assert "in a low contralto" in text and "past fifty" not in text


def test_the_japanese_view_says_the_sound_in_its_own_words():
    from language_runtime import compositor_text
    p = _p(OPEN, display=compositor_text("unseen_voice_label", "ja"),
           voice="低いアルト、温かく穏やか。", sound="年配の女性の声、海辺の訛り。")
    ja = render_view([p], mode="player", language="ja").text
    assert "年配の女性の声" in ja and "低いアルト" not in ja and "誰か" in ja


# --- 4. the player's voice reaches the cast ------------------------------------

def test_the_players_voice_is_read_through_the_persona(temp_db):
    from agents import perception
    from story.scene import active_cast
    story = _story(temp_db)
    override = json.loads(json.dumps(story["base"]))
    override["embodiment"]["voice"] = SOUND
    temp_db.qi("UPDATE chat_chars SET sheet=? WHERE chat_id=? AND char_id=?",
               (json.dumps(override), story["chat_id"], story["char_id"]))

    class _Ctx(dict):
        pass
    ctx = _Ctx()
    ctx.cast = active_cast(story["chat_id"])
    ctx.chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?",
                              (story["chat_id"],), one=True))
    assert perception._voice_sound_for(ctx, "Mara") == SOUND
    assert perception._voice_sound_for(ctx, "Ivo") == "A man's, young, with a lisp."
    assert ctx["_persona_voice_sound"] == "A man's, young, with a lisp."
    assert perception._voice_sound_for(ctx, "a passer-by") == ""
    assert perception._voice_register_for(ctx, "Ivo") == ""
