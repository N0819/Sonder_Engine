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


class TestAutoPromoteIsOneAnswer:
    """FRONTEND-2. The gate is `persist/commit_background._auto_promote_enabled`."""

    def test_an_unset_setting_reads_off_everywhere(self, temp_db):
        from persist.commit_background import _auto_promote_enabled
        from web import app

        assert _auto_promote_enabled() is False
        assert app.get_auto_promote()["enabled"] is False
        assert app.bootstrap()["auto_promote"] is False

    def test_switching_it_on_reads_on_everywhere(self, temp_db):
        from persist.commit_background import _auto_promote_enabled
        from web import app

        app.set_auto_promote({"enabled": True})

        assert _auto_promote_enabled() is True
        assert app.get_auto_promote()["enabled"] is True
        assert app.bootstrap()["auto_promote"] is True

    def test_switching_it_off_reads_off_everywhere(self, temp_db):
        from persist.commit_background import _auto_promote_enabled
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
