"""An author declares the anatomy once; the engine derives every transition.

THE MEASUREMENT, read-only against the author's corpus 2026-08-25 at a2bc44f:
79 stored sheets (61 characters, 18 personas), 0 of them carrying a non-empty
`embodiment.interior`. W8 built the structure and W9 built the clock that
walks it, and nothing anywhere fills the structure -- so a Director handed
"declare the next station if the passage continues" has no route to answer
from and correctly declines. The route on one of those cards is already
written, as prose, across `competence.abilities` and
`knowledge.private_history`, with magnitudes; `grep -rn private_history
agents/` returns nothing.

WHY A FILL SURFACE AND NOT A PARSER. Two alternatives were rejected on W9's
evidence and stay rejected: a runtime prose-duration parser is shaped by
whichever card's phrasing it was written against, and a per-beat model
choosing the next station is the guessing that crossed three stations in four
turns in one chat and stalled for nine beats in its sibling on identical
input. This converts prose to structure ONCE, at authoring time, under author
review -- the shape `fill_character_psychology` and `fill_appearance` already
have.

CLASS VOCABULARY ONLY IN THIS FILE. A vessel with an inside, and stations
called what the fixture calls them.
"""

import json
import time

import pytest


def _card(temp_db, *, interior=None, abilities=None):
    sheet = {
        # An explicit uid, so a re-normalization is comparable byte for byte
        # rather than minting a fresh one each call.
        "identity": {"name": "The Vessel", "uid": "char_vessel_fixture"},
        "embodiment": {"visible": {"summary": "Tall, unhurried."}},
        "competence": {"abilities": list(abilities or [])},
    }
    if interior is not None:
        sheet["embodiment"]["interior"] = interior
    return temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("The Vessel", json.dumps(sheet), "{}", time.time(), "char_vessel"))


def _proposal(stations):
    return json.dumps({"embodiment": {"interior": stations}})


CHAIN = [
    {"name": "First Station", "desc": "A tight passage.", "light": "dark"},
    {"name": "Second Station", "desc": "It opens.", "light": "dark",
     "barrier": "membrane", "transit_seconds": 8},
    {"name": "Third Station", "desc": "Deep.", "transit_seconds": 10800},
]


class TestItReadsTheProseAndEmitsStructure:

    def test_a_documented_route_becomes_an_ordered_chain(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(CHAIN))
        sheet = importers.fill_body_interior(char_id, "read the abilities")

        chain = sheet["embodiment"]["interior"]
        assert [s["name"] for s in chain] == [
            "First Station", "Second Station", "Third Station"]
        # The magnitudes are the point of the surface, and they land as
        # numbers or not at all.
        assert "transit_seconds" not in chain[0]
        assert chain[1]["transit_seconds"] == 8.0
        assert chain[2]["transit_seconds"] == 10800.0

    def test_a_nameless_station_is_dropped_and_the_cap_holds(
            self, temp_db, monkeypatch):
        """The normalizer is the engine-side floor: it never depends on the
        model cooperating."""
        from story import importers
        from story.character_schema import INTERIOR_STATIONS_MAX

        char_id = _card(temp_db)
        junk = ([{"name": "", "desc": "nowhere"}]
                + [{"name": "S%d" % n} for n in range(12)])
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(junk))
        sheet = importers.fill_body_interior(char_id, "")

        chain = sheet["embodiment"]["interior"]
        assert len(chain) == INTERIOR_STATIONS_MAX
        assert all(s["name"] for s in chain)

    def test_a_prose_magnitude_is_refused_rather_than_guessed(
            self, temp_db, monkeypatch):
        """"several seconds" is a claim the engine cannot act on, and storing
        it as a number would be inventing one."""
        from story import importers

        char_id = _card(temp_db)
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda *a, **k: _proposal(
                [{"name": "Only Station", "transit_seconds": "several"}]))
        sheet = importers.fill_body_interior(char_id, "")
        assert "transit_seconds" not in sheet["embodiment"]["interior"][0]

    def test_it_writes_nothing(self, temp_db, monkeypatch):
        """A generation request is "show me one", not "replace my card"."""
        from story import importers

        char_id = _card(temp_db)
        before = temp_db.q("SELECT sheet FROM characters WHERE id=?",
                           (char_id,), one=True)["sheet"]
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(CHAIN))
        importers.fill_body_interior(char_id, "")
        after = temp_db.q("SELECT sheet FROM characters WHERE id=?",
                          (char_id,), one=True)["sheet"]
        assert after == before

    def test_the_unsaved_rows_are_what_it_works_from(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db, interior=[{"name": "Saved Station"}])
        seen = {}
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda role, system, user, **k: (
                seen.update(json.loads(user)), _proposal(CHAIN))[1])
        importers.fill_body_interior(
            char_id, "brief",
            draft={"interior": [{"name": "First Station"},
                                {"name": "Second Station"},
                                {"name": "Third Station"}]})

        assert [s["name"] for s in seen["author_draft"]["interior"]] == [
            "First Station", "Second Station", "Third Station"]
        assert seen["brief"] == "brief"

    def test_an_unknown_card_is_a_value_error(self, temp_db, monkeypatch):
        from story import importers

        with pytest.raises(ValueError, match="not found"):
            importers.fill_body_interior(999999, "")


class TestItNeverInventsAnInside:
    """Most bodies have none, and a station nobody wrote is a place the
    engine will start moving people through."""

    def test_an_empty_answer_against_an_empty_card_changes_nothing(
            self, temp_db, monkeypatch):
        from story import importers
        from story.character_schema import normalize_character_data

        char_id = _card(temp_db)
        stored = json.loads(temp_db.q(
            "SELECT sheet FROM characters WHERE id=?",
            (char_id,), one=True)["sheet"])
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal([]))
        sheet = importers.fill_body_interior(char_id, "")

        assert sheet["embodiment"]["interior"] == []
        assert sheet == normalize_character_data(stored)

    def test_a_response_with_no_interior_key_invents_nothing(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda *a, **k: json.dumps({"embodiment": {"visible": {}}}))
        assert importers.fill_body_interior(
            char_id, "")["embodiment"]["interior"] == []


class TestItEditsOneFieldAndNoOther:

    def test_a_chatty_proposal_rewrites_nothing_else(
            self, temp_db, monkeypatch):
        """A button labelled with one field must not be a way to edit every
        field -- `fill_character_psychology`'s restriction, same reason."""
        from story import importers

        char_id = _card(temp_db)
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda *a, **k: json.dumps({
                "identity": {"name": "Somebody Else"},
                "embodiment": {"visible": {"summary": "REWRITTEN"},
                               "interior": CHAIN},
                "initial_outfit": {"wearing": ["a stolen coat"]},
                "psychology": {"drive": {"essence": "REWRITTEN"}},
            }))
        sheet = importers.fill_body_interior(char_id, "")

        assert sheet["identity"]["name"] == "The Vessel"
        assert sheet["embodiment"]["visible"]["summary"] == "Tall, unhurried."
        assert not sheet["initial_outfit"]["wearing"]
        assert sheet["psychology"]["drive"]["essence"] == ""
        assert len(sheet["embodiment"]["interior"]) == 3


class TestARerunNeverSilentlyDiscardsAuthoredWork:
    """The first fill surface whose output is a MECHANISM rather than prose:
    the chain's order IS the topology and its magnitudes ARE the clock, so a
    proposal that loses one does not degrade a description, it re-plumbs a
    body. Refusal, not repair -- a reviewed proposal hides an omission where
    it flaunts an invention."""

    def _rerun(self, temp_db, monkeypatch, proposal):
        from story import importers

        char_id = _card(temp_db, interior=CHAIN)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(proposal))
        return importers.fill_body_interior(char_id, "")

    def test_a_dropped_station_is_refused_by_name(self, temp_db, monkeypatch):
        with pytest.raises(RuntimeError, match="Second Station"):
            self._rerun(temp_db, monkeypatch,
                        [CHAIN[0], CHAIN[2]])

    def test_a_renamed_station_is_refused_by_its_old_name(
            self, temp_db, monkeypatch):
        renamed = [CHAIN[0], dict(CHAIN[1], name="A Better Name"), CHAIN[2]]
        with pytest.raises(RuntimeError, match="Second Station"):
            self._rerun(temp_db, monkeypatch, renamed)

    def test_a_reordered_chain_is_refused(self, temp_db, monkeypatch):
        with pytest.raises(RuntimeError, match="reordered"):
            self._rerun(temp_db, monkeypatch,
                        [CHAIN[0], CHAIN[2], CHAIN[1]])

    def test_a_dropped_crossing_time_is_refused(self, temp_db, monkeypatch):
        stripped = [CHAIN[0], {"name": "Second Station", "desc": "It opens."},
                    CHAIN[2]]
        with pytest.raises(RuntimeError, match="crossing time"):
            self._rerun(temp_db, monkeypatch, stripped)

    def test_refinement_and_addition_pass(self, temp_db, monkeypatch):
        """The guard refuses LOSS and nothing else."""
        refined = [
            dict(CHAIN[0], desc="A tighter passage than it looks."),
            dict(CHAIN[1], transit_seconds=12),
            CHAIN[2],
            {"name": "Fourth Station", "transit_seconds": 60},
        ]
        sheet = self._rerun(temp_db, monkeypatch, refined)
        chain = sheet["embodiment"]["interior"]
        assert [s["name"] for s in chain][-1] == "Fourth Station"
        assert chain[1]["transit_seconds"] == 12.0

    def test_an_empty_proposal_keeps_the_authored_chain(
            self, temp_db, monkeypatch):
        """Silence is not a deletion. Removal is a hand act in the editor."""
        sheet = self._rerun(temp_db, monkeypatch, [])
        assert [s["name"] for s in sheet["embodiment"]["interior"]] == [
            "First Station", "Second Station", "Third Station"]

    def test_the_guard_measures_the_draft_not_the_saved_copy(
            self, temp_db, monkeypatch):
        """An author who has just typed a station in the widget must not have
        it dropped by a fill that never saw it."""
        from story import importers

        char_id = _card(temp_db, interior=CHAIN)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(CHAIN))
        with pytest.raises(RuntimeError, match="Unsaved Station"):
            importers.fill_body_interior(
                char_id, "", draft={"interior": CHAIN + [
                    {"name": "Unsaved Station"}]})


class TestTheFailureModesSayWhatWentWrong:

    def test_an_empty_response_names_the_output_budget(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        monkeypatch.setattr(importers, "chat_complete", lambda *a, **k: "")
        with pytest.raises(RuntimeError, match="budget ran out"):
            importers.fill_body_interior(char_id, "")

    def test_a_non_json_response_shows_it(self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: "I would rather not.")
        with pytest.raises(RuntimeError, match="no usable data"):
            importers.fill_body_interior(char_id, "")

    def test_a_truncated_response_is_refused_rather_than_salvaged(
            self, temp_db, monkeypatch):
        """A half-written chain that `_jparse_salvage` closed up looks
        finished, which is worse than a failure."""
        from story import importers

        char_id = _card(temp_db)
        monkeypatch.setattr(
            importers, "chat_complete",
            # One closing brace short: `_jparse_salvage` closes it up and
            # hands back what looks like a finished one-station chain.
            lambda *a, **k: ('{"embodiment": {"interior": ['
                            '{"name": "First Station"}]}'))
        with pytest.raises(RuntimeError, match="cut off"):
            importers.fill_body_interior(char_id, "")


class TestTheRoute:

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
        guest.reset_host_account()

    def test_it_returns_the_sibling_shape(self, temp_db, client, monkeypatch):
        from story.character_schema import normalize_character_data
        from web import app as app_module

        char_id = _card(temp_db)
        sheet = normalize_character_data(
            {"identity": {"name": "The Vessel"},
             "embodiment": {"interior": CHAIN}})
        # The reader's own binding: `web.app` imported the name, so a patch on
        # `story.importers` would be inert here (the facade rule, applied to a
        # from-import).
        monkeypatch.setattr(app_module, "fill_body_interior",
                            lambda *a, **k: sheet)
        r = client.post(f"/api/characters/{char_id}/fill_interior",
                        json={"prompt": "read the card"})

        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {"id", "sheet", "warnings"}
        assert body["id"] == char_id
        assert len(body["sheet"]["embodiment"]["interior"]) == 3

    def test_an_unknown_card_is_a_404(self, temp_db, client, monkeypatch):
        from web import app as app_module

        def _missing(*_a, **_k):
            raise ValueError("Character not found")

        monkeypatch.setattr(app_module, "fill_body_interior", _missing)
        r = client.post("/api/characters/999999/fill_interior", json={})
        assert r.status_code == 404

    def test_a_refused_rerun_reaches_the_author(
            self, temp_db, client, monkeypatch):
        from web import app as app_module

        char_id = _card(temp_db)

        def _refuse(*_a, **_k):
            raise RuntimeError("the fill dropped or renamed authored "
                               "station(s) 'Second Station'")

        monkeypatch.setattr(app_module, "fill_body_interior", _refuse)
        r = client.post(f"/api/characters/{char_id}/fill_interior", json={})
        assert r.status_code == 502
        assert "Second Station" in r.text

    def test_the_warnings_come_back_with_the_proposal(
            self, temp_db, client, monkeypatch):
        """The feedback loop the author actually sees: a chain with no
        crossing time anywhere is a chain nothing advances anyone along."""
        from story.character_schema import normalize_character_data
        from web import app as app_module

        char_id = _card(temp_db)
        sheet = normalize_character_data(
            {"identity": {"name": "The Vessel"},
             "embodiment": {"interior": [{"name": "One"}, {"name": "Two"}]}})
        monkeypatch.setattr(app_module, "fill_body_interior",
                            lambda *a, **k: sheet)
        r = client.post(f"/api/characters/{char_id}/fill_interior", json={})

        assert r.status_code == 200, r.text
        assert any("how long it takes to cross" in w
                   for w in r.json()["warnings"])


def _story_with_card(temp_db, char_id, sheet=None):
    """A story that attaches this character, optionally with its own card.

    `chat_chars.sheet` is the per-story override, and `scene.active_cast`
    resolves it OVER the reusable row -- so it is the sheet the engine reads.
    """
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("A story", "", time.time()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
        "VALUES(?,?,?,?,?)",
        (chat_id, char_id, "active", "{}",
         json.dumps(sheet) if sheet is not None else None))
    return chat_id


class TestTheCardTheStoryActuallyReads:
    """A fill that lands in a sheet nothing reads is a silent authoring
    failure, which is the whole class this surface exists to remove.

    `stamp_authored_interiors` reads the CAST row, and the cast row is
    `COALESCE(chat_chars.sheet, characters.sheet)`. Measured read-only against
    the author's corpus 2026-08-25: 13 of 116 `chat_chars` rows carry a
    per-story sheet, and every story of the one line whose card documents a
    route is among them -- so a character-scoped fill alone reached none of
    the stories it was built for.
    """

    def _story_card(self, interior=None):
        sheet = {
            "identity": {"name": "The Vessel", "uid": "char_vessel_fixture"},
            "embodiment": {"visible": {"summary": "Weathered, in this story."}},
        }
        if interior is not None:
            sheet["embodiment"]["interior"] = interior
        return sheet

    def test_the_proposal_is_built_on_the_per_story_sheet(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id, self._story_card())
        seen = {}
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda role, system, user, **k: (
                seen.update(json.loads(user)), _proposal(CHAIN))[1])
        sheet = importers.fill_body_interior(
            char_id, "read the card", chat_id=chat_id)

        # The card handed to the model, and the card the proposal is merged
        # onto, are both the story's -- not the reusable row's.
        assert (seen["card"]["embodiment"]["visible"]["summary"]
                == "Weathered, in this story.")
        assert (sheet["embodiment"]["visible"]["summary"]
                == "Weathered, in this story.")
        assert len(sheet["embodiment"]["interior"]) == 3

    def test_the_rerun_guard_measures_the_story_card(
            self, temp_db, monkeypatch):
        """The stations it must not lose are the ones THIS story declared."""
        from story import importers

        char_id = _card(temp_db, interior=CHAIN)
        chat_id = _story_with_card(
            temp_db, char_id,
            self._story_card(interior=[{"name": "Story Station"}]))
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(CHAIN))
        with pytest.raises(RuntimeError, match="Story Station"):
            importers.fill_body_interior(char_id, "", chat_id=chat_id)

    def test_a_story_without_its_own_card_reads_the_reusable_one(
            self, temp_db, monkeypatch):
        """COALESCE, not an either/or: most attachments have no override and
        the story reads the reusable row, so the fill must too."""
        from story import importers

        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id)
        seen = {}
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda role, system, user, **k: (
                seen.update(json.loads(user)), _proposal(CHAIN))[1])
        importers.fill_body_interior(char_id, "", chat_id=chat_id)
        assert (seen["card"]["embodiment"]["visible"]["summary"]
                == "Tall, unhurried.")

    def test_a_character_not_in_the_story_is_a_value_error(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("An empty story", "", time.time()))
        with pytest.raises(ValueError, match="not in this story"):
            importers.fill_body_interior(char_id, "", chat_id=chat_id)

    def test_it_writes_neither_row(self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id, self._story_card())
        before = (
            temp_db.q("SELECT sheet FROM characters WHERE id=?",
                      (char_id,), one=True)["sheet"],
            temp_db.q("SELECT sheet FROM chat_chars WHERE chat_id=? "
                      "AND char_id=?", (chat_id, char_id), one=True)["sheet"],
        )
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(CHAIN))
        importers.fill_body_interior(char_id, "", chat_id=chat_id)
        after = (
            temp_db.q("SELECT sheet FROM characters WHERE id=?",
                      (char_id,), one=True)["sheet"],
            temp_db.q("SELECT sheet FROM chat_chars WHERE chat_id=? "
                      "AND char_id=?", (chat_id, char_id), one=True)["sheet"],
        )
        assert after == before


class TestAnEmptiedWidgetIsAnAnswer:
    """The editor always sends the widget's current rows. An author who
    deleted every station by hand and then pressed fill is not dropping
    anything -- they already dropped it, deliberately, where it was visible."""

    def test_an_emptied_draft_is_not_refused_for_dropping_the_saved_chain(
            self, temp_db, monkeypatch):
        from story import importers

        char_id = _card(temp_db, interior=CHAIN)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(
                                [{"name": "A Fresh Station"}]))
        sheet = importers.fill_body_interior(
            char_id, "", draft={"interior": []})
        assert [s["name"] for s in sheet["embodiment"]["interior"]] == [
            "A Fresh Station"]

    def test_a_caller_with_no_draft_still_gets_the_saved_chain_guarded(
            self, temp_db, monkeypatch):
        """No editor in the loop means no rows were shown to anybody, so the
        stored chain is the only authored work there is to lose."""
        from story import importers

        char_id = _card(temp_db, interior=CHAIN)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: _proposal(
                                [{"name": "A Fresh Station"}]))
        with pytest.raises(RuntimeError, match="First Station"):
            importers.fill_body_interior(char_id, "")


class TestTheStoryScopedRoute:

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
        guest.reset_host_account()

    def test_it_names_the_story_it_read(self, temp_db, client, monkeypatch):
        from story.character_schema import normalize_character_data
        from web import app as app_module

        char_id = _card(temp_db)
        chat_id = _story_with_card(temp_db, char_id, {
            "identity": {"name": "The Vessel"}})
        sheet = normalize_character_data(
            {"identity": {"name": "The Vessel"},
             "embodiment": {"interior": CHAIN}})
        seen = {}
        monkeypatch.setattr(
            app_module, "fill_body_interior",
            lambda *a, **k: (seen.update(k), sheet)[1])
        r = client.post(
            f"/api/chats/{chat_id}/characters/{char_id}/fill_interior",
            json={"prompt": "read the card"})

        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {"id", "chat_id", "sheet", "warnings"}
        assert body["id"] == char_id and body["chat_id"] == chat_id
        # The scope reaches the filler, or the route is the character one
        # under a different URL.
        assert seen["chat_id"] == chat_id
        assert len(body["sheet"]["embodiment"]["interior"]) == 3

    def test_an_unknown_story_is_a_404(self, temp_db, client, monkeypatch):
        from web import app as app_module

        char_id = _card(temp_db)
        monkeypatch.setattr(app_module, "fill_body_interior",
                            lambda *a, **k: {})
        r = client.post(
            f"/api/chats/999999/characters/{char_id}/fill_interior", json={})
        assert r.status_code == 404

    def test_a_character_not_in_the_story_is_a_404(self, temp_db, client):
        char_id = _card(temp_db)
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("An empty story", "", time.time()))
        r = client.post(
            f"/api/chats/{chat_id}/characters/{char_id}/fill_interior",
            json={})
        assert r.status_code == 404
