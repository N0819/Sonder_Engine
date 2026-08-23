"""The host surface: what the engine does, what the API reports, what the host sees.

A host-facing capability has three faces -- the code that decides, the route
that reports or changes it, and the control that reaches the route -- and
nothing in the tree makes them agree. Each of these tests pins one place they
were measured to disagree.

Two failure shapes recur, and both are silent:

  * **Two readings of one row.** A route re-derives a setting's truthiness with
    its own expression instead of calling the gate. `"" != "0"` is True and
    `"" in ("1", "on", ...)` is False, so the two answers part company on
    exactly the case that matters -- a fresh install where nothing was ever
    written.
  * **A control the copy names and the browser does not have.** Help text that
    says "switch it on in X" is a promise; if X has no such switch, the setting
    is unreachable and the host has no way to learn that.
  * **A route with no caller.** The handler is written, validated and tested,
    and no page in the app can reach it. Half a lifecycle -- attach with no
    detach, sign in with no sign out -- reads as a deliberate product decision
    when it is an omission.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_JS = (ROOT / "static/js/settings.js").read_text(encoding="utf-8")
LOREBOOKS_JS = (ROOT / "static/js/lorebooks.js").read_text(encoding="utf-8")
EDITORS_JS = (ROOT / "static/js/editors.js").read_text(encoding="utf-8")
AMBIENCE_JS = (ROOT / "static/js/ambience.js").read_text(encoding="utf-8")
UTILS_JS = (ROOT / "static/js/utils.js").read_text(encoding="utf-8")


class TestAutoPromoteIsOneAnswer:
    """FRONTEND-2. The gate is `_auto_promote_enabled`, defined in
    `persist/commit_background.py` and reached through the commit facade."""

    def test_an_unset_setting_reads_off_everywhere(self, temp_db):
        # Through the facade: `persist/commit.py` re-exports every moved
        # name, private ones included, and it is the universal import path.
        from persist.commit import _auto_promote_enabled
        from web import app

        assert _auto_promote_enabled() is False
        assert app.get_auto_promote()["enabled"] is False
        assert app.bootstrap()["auto_promote"] is False

    def test_switching_it_on_reads_on_everywhere(self, temp_db):
        # Through the facade: `persist/commit.py` re-exports every moved
        # name, private ones included, and it is the universal import path.
        from persist.commit import _auto_promote_enabled
        from web import app

        app.set_auto_promote({"enabled": True})

        assert _auto_promote_enabled() is True
        assert app.get_auto_promote()["enabled"] is True
        assert app.bootstrap()["auto_promote"] is True

    def test_switching_it_off_reads_off_everywhere(self, temp_db):
        # Through the facade: `persist/commit.py` re-exports every moved
        # name, private ones included, and it is the universal import path.
        from persist.commit import _auto_promote_enabled
        from web import app

        app.set_auto_promote({"enabled": True})
        app.set_auto_promote({"enabled": False})

        assert _auto_promote_enabled() is False
        assert app.get_auto_promote()["enabled"] is False
        assert app.bootstrap()["auto_promote"] is False

    def test_the_switch_the_dialogue_panel_promises_exists(self):
        """The per-story dial's help says promotion "has to be switched on
        globally in ⚙ API". That sentence had no control behind it."""
        assert "switched on globally in ⚙ API" in SETTINGS_JS
        assert '"PUT", "/api/auto_promote"' in SETTINGS_JS
        assert "S.boot.auto_promote" in SETTINGS_JS


class TestTheNarratorsVoiceAnchorIsReachable:
    """WEB-4 / FRONTEND-7. The read side and the prompt clause shipped; the
    write side had a route and no caller, so the clause read `[]` forever."""

    def test_the_editor_calls_the_route_that_writes_it(self):
        assert '"PUT", "/api/exemplars"' in SETTINGS_JS
        assert "S.boot.exemplars" in SETTINGS_JS

    def test_the_editor_takes_its_bounds_from_the_engine(self):
        """Every passage rides every narrator call, so the cap the host is
        shown must be the cap the route enforces -- not a second copy."""
        from web import app

        assert "S.boot.exemplar_bounds" in SETTINGS_JS
        assert "maxlength: String(maxChars)" in SETTINGS_JS
        assert app.EXEMPLAR_MAX_COUNT > 0 and app.EXEMPLAR_MAX_CHARS > 0

    def test_the_bounds_ride_the_bootstrap_payload(self, temp_db):
        from web import app

        bounds = app.bootstrap()["exemplar_bounds"]
        assert bounds == {"max_count": app.EXEMPLAR_MAX_COUNT,
                          "max_chars": app.EXEMPLAR_MAX_CHARS}

    def test_what_the_editor_saves_is_what_the_narrator_reads(self, temp_db):
        """The whole point of the row: the STYLE EXEMPLARS clause stops
        reading an empty list."""
        from core.db import get_setting
        from web import app

        app.put_exemplars({"exemplars": ["  A short passage.  ", "", "Another."]})

        import json
        assert json.loads(get_setting("exemplars")) == ["A short passage.",
                                                        "Another."]
        assert app.bootstrap()["exemplars"] == ["A short passage.", "Another."]


class TestBothHalvesOfALifecycleHaveAControl:
    """WEB-9 / FRONTEND-8. Routes whose other half was already reachable.

    Half a lifecycle reads as a product decision when it is an omission: the
    host sees an Attach button and no Detach, a sign-in page and no sign-out,
    and has no way to tell "not offered" from "not built".
    """

    def test_an_attached_extra_player_can_be_detached(self):
        """`POST .../personas` had a button; `DELETE .../personas/{pid}` did
        not, so a player who joined a story once could not be removed except
        by editing the database."""
        assert '"POST", `/api/chats/${chatId}/personas`' in SETTINGS_JS
        assert '"DELETE", `/api/chats/${chatId}/personas/${p.id}`' in SETTINGS_JS

    def test_detaching_is_what_the_button_says_it_is(self, temp_db):
        """The copy promises their invite or live session stops working --
        the route does both in one transaction, so the promise is checkable."""
        import time

        from web import app
        from web import guest_access as guest

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
        pid = app.persona_create({"name": "Second Player"})["id"]
        app.chat_add_persona(cid, {"persona_id": pid})
        invite = guest.create_guest_invite(cid, pid)
        session = guest.redeem_code(invite["code"])
        assert guest.verify_guest_token(session["token"]) is not None

        app.chat_del_persona(cid, pid)

        assert app.chat_list_extra_personas(cid)["personas"] == []
        assert guest.verify_guest_token(session["token"]) is None

    def test_a_host_can_sign_out(self):
        """The host cookie lasts thirty days and is SameSite=Strict.
        `POST /api/auth/logout` destroys the session row and clears the
        cookie, and no page in the app offered it."""
        assert '"POST", "/api/auth/logout"' in SETTINGS_JS


class TestCanonCanBeChangedAfterTheStoryStarts:
    """WEB-9. `chats.lorebook_id` is what `agents/mapping.py` reads as this
    story's settled truth. The lorebook tree has always BADGED it and never
    offered a way to change it: canon was chosen once, on the greeting
    screen, and after that only a database edit could move it."""

    def test_the_tree_calls_both_halves_of_the_route(self):
        assert "canon" in LOREBOOKS_JS
        assert '"POST",\n`/api/chats/${book.chat_id}/lorebook`' in LOREBOOKS_JS
        assert '"DELETE",\n`/api/chats/${book.chat_id}/lorebook`' in LOREBOOKS_JS

    def test_binding_and_detaching_move_the_canon_the_tree_reports(self, temp_db):
        import time

        from web import app

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
        lid = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("Book", cid))

        def canon_ids():
            return [b["id"] for b in app.chat_lorebooks_owned(cid)["lorebooks"]
                    if b["canon"]]

        assert canon_ids() == []
        app.bind_lore(cid, {"lorebook_id": lid})
        assert canon_ids() == [lid]
        app.detach_lore(cid)
        assert canon_ids() == []


class TestAnAttachedLorebookCanBeSilenced:
    """FRONTEND-9. `chat_lorebooks.enabled` was declared, INSERTed as 1 by
    five writers, honoured by four readers, and UPDATEd by nothing -- so the
    column had one reachable value and the read path around it was dead."""

    def test_the_panel_calls_the_route(self):
        assert '"PUT",\n                      `/api/chats/${chatId}/lorebooks/${lb.id}`' \
            in SETTINGS_JS

    def test_disabling_drops_the_book_out_of_retrieval(self, temp_db):
        import time

        from mind.memory import chat_lorebook_ids
        from web import app

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
        lid = temp_db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)",
                         ("Attached", None))
        attached = app.attach_lore(cid, {"lorebook_id": lid})["lorebook_id"]

        assert attached in chat_lorebook_ids(cid)

        assert app.set_book_enabled(cid, attached, {"enabled": False}) == {
            "lorebook_id": attached, "enabled": False}
        assert attached not in chat_lorebook_ids(cid)
        # Still attached, and every entry still there -- that is what makes it
        # a different act from detaching.
        assert attached in chat_lorebook_ids(cid, enabled_only=False)

        app.set_book_enabled(cid, attached, {"enabled": True})
        assert attached in chat_lorebook_ids(cid)

    def test_a_book_that_is_not_attached_is_a_404(self, temp_db):
        import time

        import pytest
        from fastapi import HTTPException
        from web import app

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
        lid = temp_db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)",
                         ("Loose", None))

        with pytest.raises(HTTPException) as caught:
            app.set_book_enabled(cid, lid, {"enabled": False})
        assert caught.value.status_code == 404


class TestEveryCardProducingRouteWarns:
    """STORY-F15. `character_card_warnings` reached ONE of nine surfaces that
    create or edit a card -- the import route -- while `char_create` produced,
    by construction, the exact empty-drive sheet the first three warnings
    exist to catch, and said nothing.

    Nothing about the answer depends on where the sheet came from, so the
    rule is "every route that hands back a card hands back its warnings",
    not a list of routes that happen to.
    """

    BLANK_WARNS = 3  # empty drive, no goals, unset capacity

    def _blank(self, temp_db):
        from web import app

        return app.char_create({"name": "Unnamed"})

    def test_the_blank_card_route_warns(self, temp_db):
        created = self._blank(temp_db)
        assert len(created["warnings"]) >= self.BLANK_WARNS

    def test_a_hand_edit_warns(self, temp_db):
        from web import app

        created = self._blank(temp_db)
        edited = app.char_edit(created["id"], {"sheet": created["sheet"]})
        assert edited["warnings"] == created["warnings"]

    def test_a_filled_card_warns_about_nothing(self, temp_db):
        from web import app

        created = self._blank(temp_db)
        sheet = dict(created["sheet"])
        sheet["psychology"] = dict(sheet.get("psychology") or {})
        sheet["psychology"]["drive"] = {
            "essence": "to be believed", "expression": "tells the truth "
            "loudly", "taboo": "being humoured"}
        sheet["psychology"]["capacity"] = "ordinary"
        sheet["initial_state"] = dict(sheet.get("initial_state") or {})
        sheet["initial_state"]["goals"] = [{"text": "get the ledger back"}]

        assert app.char_edit(created["id"], {"sheet": sheet})["warnings"] == []

    def test_the_per_story_card_override_warns(self, temp_db):
        import time

        from web import app

        created = self._blank(temp_db)
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
        app.chat_add_char(cid, {"char_id": created["id"]})

        saved = app.chat_char_card_put(
            cid, created["id"], {"sheet": created["sheet"]})
        assert len(saved["warnings"]) >= self.BLANK_WARNS

    def test_starting_a_story_warns_before_the_card_starts_behaving(
        self, temp_db, monkeypatch,
    ):
        from story import greetings
        from web import app

        created = self._blank(temp_db)
        monkeypatch.setattr(greetings, "start_story",
                            lambda *a, **k: (1, 2))
        launched = app.character_start_story(
            created["id"], {"persona_id": 1, "language": "en"})
        assert len(launched["warnings"]) >= self.BLANK_WARNS

    def test_starting_with_an_exhausted_location_model_returns_a_clean_error(
            self, temp_db, monkeypatch):
        import pytest
        from fastapi import HTTPException
        from llm.providers import ReasoningBudgetExhausted
        from story import greetings
        from web import app

        created = self._blank(temp_db)

        def fail(*args, **kwargs):
            raise ReasoningBudgetExhausted("trace consumed answer")

        monkeypatch.setattr(greetings, "start_story", fail)
        with pytest.raises(HTTPException) as caught:
            app.character_start_story(
                created["id"], {"persona_id": 1, "language": "en"})

        assert caught.value.status_code == 502
        assert "whole response for reasoning" in caught.value.detail

    def test_the_browser_shows_them_through_one_helper(self):
        """A copy per call site is how eight of nine went silent. One
        helper, called wherever a card response comes back."""
        assert "function showCardWarnings(result)" in UTILS_JS
        assert EDITORS_JS.count("showCardWarnings(") >= 5


class TestTheConsentDialogDisclosesWhatWasAskedFor:
    """WEB-2. `capabilities` is DISCLOSURE, never enforcement, so the only
    thing it has to do is arrive complete at the moment of consent."""

    def test_the_engine_owns_the_vocabulary_and_it_is_read(self):
        from extension_runtime import CAPABILITY_DISCLOSURES, KNOWN_CAPABILITIES

        assert tuple(CAPABILITY_DISCLOSURES) == KNOWN_CAPABILITIES
        assert len(KNOWN_CAPABILITIES) == 10

    def test_every_declared_capability_is_disclosed(self):
        """The browser's old hand-written summary named six of the ten. The
        four it dropped are the four a host would most want named."""
        from extension_runtime import Extension, KNOWN_CAPABILITIES

        ext = Extension(
            id="e", name="E", description="", version="1", ext_api=1,
            trust="code", provenance="local", path=Path("."),
            capabilities={key: True for key in KNOWN_CAPABILITIES},
        )
        said = " ".join(ext.disclosures()).lower()
        for phrase in ("python code inside the engine",
                       "commit transaction",
                       "http endpoints",
                       "character's own per-story state"):
            assert phrase in said, phrase

    def test_a_capability_this_engine_does_not_know_is_still_disclosed(self):
        """Unknown keys are tolerated so a later-`ext_api` manifest stays
        loadable. Tolerated must not mean silent."""
        from extension_runtime import Extension

        ext = Extension(
            id="e", name="E", description="", version="1", ext_api=1,
            trust="code", provenance="local", path=Path("."),
            capabilities={"time_travel": True},
        )
        assert any("time_travel" in line for line in ext.disclosures())

    def test_the_dialog_shows_them_and_the_browser_keeps_no_second_list(self):
        assert "It asks to:" in SETTINGS_JS
        assert "return (ext && ext.disclosures) || [];" in SETTINGS_JS

    def test_the_listing_carries_them(self):
        import extension_runtime

        for row in extension_runtime.listing():
            assert isinstance(row["disclosures"], list)


class TestABrokenExtensionIsNamed:
    """WEB-10. Producers write `dir`; the panel read `id`, which no producer
    has ever written -- so every load failure reported itself as "an
    extension" while the loader had the directory in hand."""

    def test_the_panel_reads_the_field_the_loader_writes(self):
        assert "${err.dir || \"an extension\"} failed to load" in SETTINGS_JS

    def test_a_load_error_carries_the_directory(self, tmp_path, monkeypatch):
        import extension_runtime

        broken = tmp_path / "broken-ext"
        broken.mkdir()
        (broken / "manifest.json").write_text("{not json", encoding="utf-8")
        monkeypatch.setenv(extension_runtime.ROOT_ENV, str(tmp_path))
        # The scan is cached module-wide, so put the real tree back whatever
        # this assertion does.
        try:
            extension_runtime.reload()
            errors = extension_runtime.load_errors()
            assert [e["dir"] for e in errors] == ["broken-ext"]
        finally:
            monkeypatch.delenv(extension_runtime.ROOT_ENV, raising=False)
            extension_runtime.reload()


class TestTheBackdropRoutesAnswerWithOneShape:
    """FRONTEND-28. The browser CACHES the POST's payload under the turn id,
    so a POST that answers with less than the GET plants a short record that a
    later read treats as complete."""

    def test_both_routes_return_the_same_keys(self, temp_db, monkeypatch):
        import time

        from web import app

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (cid, 0, "look", time.time()))

        req = {"signature": "abc123", "room": "hall_1", "room_name": "The Hall",
               "cached": True, "weather": {"kind": "rain"}}
        monkeypatch.setattr(app, "build_backdrop_request", lambda *a, **k: req)
        monkeypatch.setattr(app, "image_model", lambda: {"provider": "x"})
        monkeypatch.setattr(app, "request_backdrop", lambda *a, **k: {
            "signature": "abc123", "status": "ready", "room": "The Hall"})

        got = app.turn_backdrop(tid)
        posted = app.turn_backdrop_generate(tid, {})

        assert set(posted) == set(got)
        for field in ("room_id", "weather"):
            assert posted[field] == got[field], field

    def test_the_no_room_answer_is_the_same_shape_too(self, temp_db, monkeypatch):
        """An opening turn before mapping has placed anyone. Not an error --
        and not a reason for a payload with different keys either."""
        import time

        from web import app

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (cid, 0, "look", time.time()))
        monkeypatch.setattr(app, "build_backdrop_request", lambda *a, **k: None)

        empty = app.turn_backdrop(tid)
        assert empty["weather"] == {}
        assert empty["room_id"] is None
        assert empty["status"] == "absent"


class TestTheAmbiencePickerCanListTheLibrary:
    """FRONTEND-27. `GET /api/ambience/library` says in its own docstring that
    it exists so the picker can list the library unfiltered, and the picker
    had a search box and no listing path -- so an unhelpfully-named library
    was unbrowsable, which is exactly the library search cannot rank."""

    def test_the_picker_calls_it(self):
        assert '"GET", "/api/ambience/library"' in AMBIENCE_JS
        assert "Browse library" in AMBIENCE_JS
