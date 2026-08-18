"""The story lifecycle as a declared contract, and the per-era state home.

Two items from the Directive gap review, and they share a shape: both were
things an extension could already do by reaching past the facade, which is to
say things that worked and would break silently the first time somebody
refactored underneath them. That is the position the UI mount points were in
before 9.0 declared them.

The lifecycle also has a REFUSAL in it that is not a gap, and this file pins it
too: an extension cannot post an assistant message. Prose here is produced by
the pipeline from state the Director committed, and text inserted as though the
narrator wrote it would be narration nothing earned.
"""

from __future__ import annotations

import json

import pytest

import extension_runtime
from extension_runtime.api import ChatAccess

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _chat, _enable, _turn, _write_extension, ext_root, real_ext_root,
)


@pytest.fixture
def bare(ext_root):
    _write_extension(ext_root, "lifecycle", {
        "id": "lifecycle", "version": "1.0.0", "ext_api": 1, "name": "Lifecycle",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("lifecycle")
    return extension_runtime._apis["lifecycle"]


# ----------------------------------------------------------- the lifecycle


class TestChatAccess:
    def test_it_creates_a_story(self, temp_db, bare):
        chat = bare.chats.create(name="A Quiet House", scenario="Nothing yet.")

        assert chat["name"] == "A Quiet House"
        assert bare.story_view(chat["id"])["story"]["scenario"] == "Nothing yet."

    def test_mine_finds_only_the_stories_this_extension_provisioned(
            self, temp_db, bare):
        """The other half of "create or bind".

        Matching on a chat's NAME would bind to whatever a player happened to
        rename something to -- and renaming a story is the most ordinary thing
        a person does to one. Provenance is written at provisioning time and
        cannot be typed into existence.
        """
        bare.chats.create(name="Not a campaign")
        provisioned = bare.provision_story(
            {"version": 1, "chat": {"name": "A Campaign"}},
            package_id="pkg", package_version="1.0.0")

        mine = bare.chats.mine()

        assert [row["chat_id"] for row in mine] == [provisioned["chat_id"]]
        assert mine[0]["provenance"]["package"] == "pkg"

    def test_mine_does_not_see_another_extensions_campaign(self, temp_db, bare,
                                                            ext_root):
        _write_extension(ext_root, "other", {
            "id": "other", "version": "1.0.0", "ext_api": 1, "name": "Other",
            "capabilities": {"python": "extension.py", "chat_state": True},
        }, {"extension.py": "def register(api):\n    pass\n"})
        _enable("lifecycle", "other")
        other = extension_runtime._apis["other"]
        other.provision_story({"version": 1, "chat": {"name": "Theirs"}})

        assert extension_runtime._apis["lifecycle"].chats.mine() == []

    def test_turns_reads_the_story_oldest_last(self, temp_db, bare):
        chat_id = _chat(temp_db)
        for idx in (1, 2, 3):
            _turn(temp_db, chat_id, idx=idx)

        assert [t["idx"] for t in bare.chats.turns(chat_id)] == [1, 2, 3]

    def test_turns_is_bounded(self, temp_db, bare):
        """A campaign panel refreshing must not scan a thousand-turn story."""
        chat_id = _chat(temp_db)
        for idx in range(10):
            _turn(temp_db, chat_id, idx=idx)

        assert len(bare.chats.turns(chat_id, limit=3)) == 3

    def test_there_is_no_way_to_post_prose(self, temp_db, bare):
        """Not an oversight to be filled in later.

        Prose comes out of the pipeline from state the Director committed. Text
        an extension inserted as though the narrator wrote it is narration
        nothing earned -- which is the thing `commit.py` exists to make
        impossible, and a seam for it would make the whole persistence boundary
        advisory.
        """
        assert not [name for name in dir(ChatAccess)
                    if "message" in name or "prose" in name
                    or "post" in name.lower()]

    def test_the_refusal_is_documented_where_an_author_will_look(self):
        """A refusal nobody can find reads as a missing feature, and the author
        goes looking for the internal that does it anyway."""
        import inspect
        import re

        # Whitespace-normalised: the sentence wraps, and a matcher that could
        # be satisfied by reflowing a paragraph is testing the line breaks.
        doc = re.sub(r"\s+", " ", inspect.getdoc(ChatAccess))

        assert "cannot write an assistant message" in doc
        assert "api.narration_context" in doc
        assert "api.director_context" in doc


# ------------------------------------------------------------- per-era state


class TestFrameState:
    def test_the_two_homes_are_separate(self, temp_db, bare):
        chat_id = _chat(temp_db)
        bare.state(chat_id).set_now({"installed": True})
        bare.frame_state(chat_id).set_now({"mission": "survey"})

        assert bare.state(chat_id).get() == {"installed": True}
        assert bare.frame_state(chat_id).get() == {"mission": "survey"}

    def test_chat_global_state_is_shared_across_eras(self, temp_db, bare):
        """What an installation IS does not change because the player walked
        into a different century."""
        from core.db import active_frame_id

        chat_id = _chat(temp_db)
        bare.state(chat_id).set_now({"installed": True})

        token = active_frame_id.set(7)
        try:
            assert bare.state(chat_id).get() == {"installed": True}
        finally:
            active_frame_id.reset(token)

    def test_frame_state_is_per_era(self, temp_db, bare):
        """A mission advanced in one era was advanced in EVERY era before this,
        and a rewind that took the room back left the objective ticked."""
        from core.db import active_frame_id

        chat_id = _chat(temp_db)
        state = bare.frame_state(chat_id)

        token = active_frame_id.set(1)
        try:
            state.set_now({"objective": "done"})
        finally:
            active_frame_id.reset(token)

        token = active_frame_id.set(2)
        try:
            assert state.get() is None
        finally:
            active_frame_id.reset(token)

        token = active_frame_id.set(1)
        try:
            assert state.get() == {"objective": "done"}
        finally:
            active_frame_id.reset(token)

    def test_the_prefix_is_what_scopes_it(self, temp_db):
        """So checkpoints, archives and branch/clone frame remapping already
        handle it: those paths parse the frame off a key generically rather
        than checking it against a list of names."""
        from core import db

        assert db._is_frame_scoped_world_key("extf:demo")
        assert not db._is_frame_scoped_world_key("ext:demo")

    def test_the_two_prefixes_cannot_be_confused(self, temp_db, bare):
        """`extf:` must not be caught by a scan for `ext:`, or an extension's
        per-era state would read as a second copy of its global state."""
        assert not "extf:x".startswith("ext:")

    def test_per_era_state_rides_an_export(self, temp_db, bare):
        from web import app
        from core.db import active_frame_id

        chat_id = _chat(temp_db)
        token = active_frame_id.set(3)
        try:
            bare.frame_state(chat_id).set_now({"objective": "done"})
        finally:
            active_frame_id.reset(token)

        world = json.loads(json.dumps(
            app._chat_archive_service.export_chat(chat_id)))["world"]

        assert any(key.startswith("extf:lifecycle") for key in world)

    def test_a_commit_domain_receives_both_homes(self, temp_db, bare):
        """The likeliest caller. A domain that could only reach the chat-global
        home would have to reimplement the scoping itself, wrongly."""
        from extension_runtime.api import CommitView

        from tests.test_extensions import _StubCtx

        view = CommitView(bare, _StubCtx(chat_id=_chat(temp_db)))

        assert view.state is not None
        assert view.frame_state is not None
