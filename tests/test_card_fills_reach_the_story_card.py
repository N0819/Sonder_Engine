"""All three card fills read the sheet the story actually runs on (A64).

`scene.active_cast` resolves `chat_chars.sheet` OVER `characters.sheet`, so a
fill offered only on the reusable row is inert for every story with its own
card: the author presses the button, reviews a proposal, saves, and the sheet
the engine reads is untouched. `fill_body_interior` grew `chat_id` for exactly
that reason; `fill_appearance` and `fill_character_psychology` had not, and
read `characters` alone.

The rule now: one reader (`importers.authored_card_for_fill`) for all three,
and a chat-scoped route beside each character-scoped one.
"""

import json
import time

import pytest


_REUSABLE = "Tall, unhurried."
_IN_STORY = "Weathered, in this story."


def _card(temp_db):
    sheet = {
        "identity": {"name": "The Vessel", "uid": "char_vessel_fixture"},
        "embodiment": {"visible": {"summary": _REUSABLE}},
        "psychology": {"drive": {"essence": "", "expression": "",
                                 "taboo": ""}},
    }
    return temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("The Vessel", json.dumps(sheet), "{}", time.time(), "char_vessel"))


def _story_with_card(temp_db, char_id, sheet=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("A story", "", time.time()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
        "VALUES(?,?,?,?,?)",
        (chat_id, char_id, "active", "{}",
         json.dumps(sheet) if sheet is not None else None))
    return chat_id


def _story_card():
    return {
        "identity": {"name": "The Vessel", "uid": "char_vessel_fixture"},
        "embodiment": {"visible": {"summary": _IN_STORY}},
        "psychology": {"drive": {"essence": "", "expression": "",
                                 "taboo": ""}},
    }


def _capture(monkeypatch, reply):
    """Intercept the model call and record the payload it was handed."""
    from story import importers

    seen = {}
    monkeypatch.setattr(
        importers, "chat_complete",
        lambda role, system, user, **k: (
            seen.update(json.loads(user)), reply)[1])
    return seen


class TestAppearanceFill:

    def test_it_reads_and_proposes_against_the_per_story_sheet(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id, _story_card())
        seen = _capture(monkeypatch, json.dumps(
            {"initial_outfit": {"regions": {
                "torso": {"garments": [{"name": "a grey coat"}]}}}}))
        sheet = importers.fill_appearance(
            "character", char_id, "dress them", chat_id=chat_id)

        assert seen["card"]["embodiment"]["visible"]["summary"] == _IN_STORY
        # Merged onto the STORY's card, not the reusable one.
        assert sheet["embodiment"]["visible"]["summary"] == _IN_STORY
        assert sheet["initial_outfit"]["wearing"] == ["a grey coat"]

    def test_without_a_story_it_still_reads_the_reusable_row(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        seen = _capture(monkeypatch, json.dumps({"initial_outfit": {}}))
        importers.fill_appearance("character", char_id, "")
        assert seen["card"]["embodiment"]["visible"]["summary"] == _REUSABLE

    def test_a_character_not_in_the_story_is_a_value_error(self, temp_db):
        from story import importers

        char_id = _card(temp_db)
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("An empty story", "", time.time()))
        with pytest.raises(ValueError, match="not in this story"):
            importers.fill_appearance(
                "character", char_id, "", chat_id=chat_id)

    def test_a_persona_has_no_per_story_card(self, temp_db):
        from story import importers

        with pytest.raises(ValueError, match="per-story card"):
            importers.fill_appearance("persona", 1, "", chat_id=1)


class TestPsychologyFill:

    def test_it_reads_and_proposes_against_the_per_story_sheet(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id, _story_card())
        seen = _capture(monkeypatch, json.dumps(
            {"psychology": {"drive": {"essence": "to be let back in",
                                      "expression": "waits", "taboo": "asks"}}}))
        sheet = importers.fill_character_psychology(
            char_id, "who are they", chat_id=chat_id)

        assert seen["character"]["embodiment"]["visible"]["summary"] == _IN_STORY
        assert sheet["embodiment"]["visible"]["summary"] == _IN_STORY
        assert sheet["psychology"]["drive"]["essence"] == "to be let back in"

    def test_without_a_story_it_still_reads_the_reusable_row(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        seen = _capture(monkeypatch, json.dumps({"psychology": {}}))
        importers.fill_character_psychology(char_id, "")
        assert (seen["character"]["embodiment"]["visible"]["summary"]
                == _REUSABLE)


class TestTheRoutesExist:

    @pytest.fixture
    def client(self, temp_db):
        from fastapi.testclient import TestClient

        from web import app as app_module
        from web import guest_access as guest

        guest.reset_host_account()
        with TestClient(app_module.app) as c:
            r = c.post("/api/auth/setup",
                       json={"username": "host", "password": "pw12345"})
            assert r.status_code == 200, r.text
            yield c

    def test_the_story_scoped_fills_answer(
            self, temp_db, client, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id, _story_card())
        # The proposal says nothing about the body, so the summary that comes
        # back is whichever card was READ -- which is the assertion.
        _capture(monkeypatch, json.dumps(
            {"initial_outfit": {"regions": {
                "torso": {"garments": [{"name": "a grey coat"}]}}},
             "psychology": {"drive": {"essence": "e", "expression": "x",
                                      "taboo": "t"}}}))
        for route in ("fill_appearance", "fill_psychology"):
            r = client.post(
                f"/api/chats/{chat_id}/characters/{char_id}/{route}",
                json={"prompt": ""})
            assert r.status_code == 200, (route, r.text)
            body = r.json()
            assert body["chat_id"] == chat_id
            assert body["id"] == char_id
            assert (body["sheet"]["embodiment"]["visible"]["summary"]
                    == _IN_STORY), route

    def test_an_unknown_story_is_a_404(self, temp_db, client):
        char_id = _card(temp_db)
        for route in ("fill_appearance", "fill_psychology"):
            r = client.post(
                f"/api/chats/999999/characters/{char_id}/{route}", json={})
            assert r.status_code == 404, (route, r.text)

    def test_neither_row_is_written(self, temp_db, client, monkeypatch):
        """Both fills are previews: the author's Save is what commits."""
        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id, _story_card())
        _capture(monkeypatch, json.dumps(
            {"embodiment": {"visible": {"summary": "rewritten"}},
             "psychology": {"drive": {"essence": "e", "expression": "x",
                                      "taboo": "t"}}}))
        before = (
            temp_db.q("SELECT sheet FROM characters WHERE id=?",
                      (char_id,), one=True)["sheet"],
            temp_db.q("SELECT sheet FROM chat_chars WHERE chat_id=? "
                      "AND char_id=?", (chat_id, char_id), one=True)["sheet"],
        )
        for route in ("fill_appearance", "fill_psychology"):
            client.post(
                f"/api/chats/{chat_id}/characters/{char_id}/{route}", json={})
        after = (
            temp_db.q("SELECT sheet FROM characters WHERE id=?",
                      (char_id,), one=True)["sheet"],
            temp_db.q("SELECT sheet FROM chat_chars WHERE chat_id=? "
                      "AND char_id=?", (chat_id, char_id), one=True)["sheet"],
        )
        assert before == after
