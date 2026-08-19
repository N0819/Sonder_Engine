"""The narration seam: standing context blocks and narrator payload hooks.

The character routing seam (`on_character_payload`) answers "what may a mind be
told". This file covers the other direction: what may an extension put in front
of the NARRATOR, which is what the player actually reads.

The distinction is why this is a separate seam rather than a second argument to
the first one. A character payload carrying too much produces a mind acting on
knowledge it should not have -- legible, in-fiction, and recoverable in the next
beat. Narration carrying too much is simply told to the player and cannot be
taken back. So the properties pinned here are about a block being safe to leave
installed for a thousand turns, and about every edit naming its author.
"""

from __future__ import annotations

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _write_extension, ext_root, real_ext_root,
)


@pytest.fixture
def bare(ext_root):
    """One enabled extension whose python entry does nothing.

    Hooks are registered against its live api object so each test states the
    one registration it is about, rather than carrying an entry file that has
    to anticipate every test in the file.
    """
    _write_extension(ext_root, "seams", {
        "id": "seams", "version": "1.0.0", "ext_api": 1, "name": "Seams",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("seams")
    return extension_runtime._apis["seams"]


# ------------------------------------------------------------------- blocks


class TestNarrationBlocks:
    """The declarative half: standing context for one story.

    This is the shape a campaign layer actually wants. It says the same thing
    every beat, so saying it through a hook that must run every beat is the
    wrong shape -- and a hook that has to run is a hook that can fail.
    """

    def test_an_installed_block_reaches_the_narrator_payload(self, temp_db,
                                                             bare):
        chat_id = _chat(temp_db)
        bare.narration_context(chat_id).set("The corridors are dark and cold.")

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {"player_view": {}})

        assert out["extension_context"] == [
            {"source": "seams", "text": "The corridors are dark and cold.",
             "revision": 1}]
        assert out["player_view"] == {}

    def test_no_block_leaves_the_payload_untouched(self, temp_db, bare):
        """The overwhelmingly common beat must cost the payload nothing.

        Not merely "no text": no KEY. An empty `extension_context` in every
        narrator payload is a field the model has to be told to ignore, on
        every beat of every story that never installed one.
        """
        payload = {"player_view": {}}
        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=_chat(temp_db)), payload)

        assert "extension_context" not in out
        assert out == payload

    def test_setting_a_block_replaces_rather_than_appends(self, temp_db, bare):
        """A context injector that appends leaks everything it ever said."""
        chat_id = _chat(temp_db)
        block = bare.narration_context(chat_id)
        block.set("Three days into a fuel emergency.")
        block.set("The emergency is over; the ship is under tow.")

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {})

        assert out["extension_context"] == [
            {"source": "seams",
             "text": "The emergency is over; the ship is under tow.",
             "revision": 2}]

    def test_reinstalling_identical_text_does_not_bump_the_revision(
            self, temp_db, bare):
        """A rebuild that changed nothing is not a new revision.

        A caller that re-installs every beat -- which is exactly what a
        `syncForChat` loop does -- would otherwise drive the number to the turn
        count and make "has this changed since I last read it" unanswerable.
        """
        chat_id = _chat(temp_db)
        block = bare.narration_context(chat_id)
        first = block.set("The ship is under tow.")
        again = block.set("The ship is under tow.")

        assert first["revision"] == 1
        assert again["revision"] == 1
        assert again["hash"] == first["hash"]

    def test_clearing_removes_it_from_the_payload(self, temp_db, bare):
        chat_id = _chat(temp_db)
        block = bare.narration_context(chat_id)
        block.set("Standing context.")
        block.clear()

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {})

        assert "extension_context" not in out
        assert block.get() is None

    def test_setting_empty_text_clears_rather_than_storing_an_empty_block(
            self, temp_db, bare):
        chat_id = _chat(temp_db)
        block = bare.narration_context(chat_id)
        block.set("Something.")

        assert block.set("   ") is None
        assert block.get() is None

    def test_a_block_is_scoped_to_one_story(self, temp_db, bare):
        """`ext:<id>:narration` is a world key, so two chats cannot share one."""
        first, second = _chat(temp_db), _chat(temp_db)
        bare.narration_context(first).set("Only the first story.")

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=second), {})

        assert "extension_context" not in out

    def test_an_oversized_block_is_refused_rather_than_truncated(self, temp_db,
                                                                 bare):
        """It rides EVERY beat, so the cost is permanent, not one-off.

        Truncating would ship a silently half-installed frame, and the half
        that survived would be chosen by a byte count rather than by the author.
        """
        chat_id = _chat(temp_db)
        with pytest.raises(ExtensionError) as excinfo:
            bare.narration_context(chat_id).set("x" * 8001)

        assert "8000" in str(excinfo.value)
        assert bare.narration_context(chat_id).get() is None

    def test_a_block_is_attributed_on_the_turn(self, temp_db, bare):
        """Narration reaches the PLAYER, so its author has to be nameable."""
        chat_id = _chat(temp_db)
        bare.narration_context(chat_id).set("Standing context.")
        ctx = _StubCtx(chat_id=chat_id)

        extension_runtime.dispatch_narration_payload(ctx, {})

        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": None, "scope": "narrator",
             "changed": ["extension_context"]}]


# -------------------------------------------------------------------- hooks


class TestNarrationHooks:
    """The imperative half, making the same bargain the character hook makes."""

    def test_a_hook_may_rewrite_the_payload(self, temp_db, bare):
        bare.on_narration_payload(
            lambda payload, info: {**payload, "tone": "clipped"})

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=_chat(temp_db)), {"player_view": {}})

        assert out["tone"] == "clipped"
        assert out["player_view"] == {}

    def test_a_hook_that_mutates_in_place_is_still_attributed(self, temp_db,
                                                              bare):
        """The same hole the character seam had, closed the same way.

        A hook is handed the real payload, so comparing the returned object
        against the passed one compares an object with itself and reports no
        change -- an unattributed edit to what the reader is told.
        """
        def hook(payload, info):
            payload["unearned_fact"] = "the captain is already dead"
            return payload

        bare.on_narration_payload(hook)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        out = extension_runtime.dispatch_narration_payload(ctx, {"prose": ""})

        assert out["unearned_fact"] == "the captain is already dead"
        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": None, "scope": "narrator",
             "changed": ["unearned_fact"]}]

    def test_mutating_and_returning_none_is_attributed_too(self, temp_db,
                                                           bare):
        """The same hole by a shorter route: mutate, then say 'unchanged'."""
        def hook(payload, info):
            payload["smuggled"] = "in"
            return None

        bare.on_narration_payload(hook)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        out = extension_runtime.dispatch_narration_payload(ctx, {"prose": ""})

        assert out["smuggled"] == "in"
        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": None, "scope": "narrator",
             "changed": ["smuggled"]}]

    def test_a_hook_sees_which_reader_this_is(self, temp_db, bare):
        """`narrator` and `narrator_extra` are different people at one table.

        A hook that cannot tell them apart colours one player's story and not
        the other's, and the two then disagree about the same beat -- a
        divergence that surfaces as a continuity complaint from one seat only.
        """
        seen = []
        bare.on_narration_payload(
            lambda payload, info: seen.append((info.scope, info.player)))
        ctx = _StubCtx(chat_id=_chat(temp_db))

        extension_runtime.dispatch_narration_payload(ctx, {})
        extension_runtime.dispatch_narration_payload(
            ctx, {}, scope="narrator_extra", player="Mara")

        assert seen == [("narrator", ""), ("narrator_extra", "Mara")]

    def test_a_hook_receives_the_story_and_turn_it_is_running_in(self, temp_db,
                                                                 bare):
        chat_id = _chat(temp_db)
        seen = {}

        def hook(payload, info):
            seen["chat_id"] = info.chat_id
            seen["turn_idx"] = info.turn_idx
            return None

        bare.on_narration_payload(hook)
        extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id, idx=11), {})

        assert seen == {"chat_id": chat_id, "turn_idx": 11}

    def test_a_throwing_hook_leaves_the_payload_exactly_as_assembled(
            self, temp_db, bare):
        """A broken extension must cost the beat nothing."""
        def hook(payload, info):
            raise RuntimeError("no")

        bare.on_narration_payload(hook)
        payload = {"player_view": {"a": 1}}

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=_chat(temp_db)), payload)

        assert out == payload

    def test_a_hook_runs_after_blocks_and_can_replace_them(self, temp_db,
                                                           bare):
        """Order is stated, not incidental: declarative first, hook last.

        The hook is the escape hatch, so it has to be able to see -- and undo
        -- what the declarative half just assembled.
        """
        chat_id = _chat(temp_db)
        bare.narration_context(chat_id).set("Installed block.")
        bare.on_narration_payload(
            lambda payload, info: {**payload,
                                   "seen": list(payload["extension_context"]),
                                   "extension_context": []})

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {})

        assert out["seen"][0]["text"] == "Installed block."
        assert out["extension_context"] == []

    def test_a_non_dict_return_is_ignored(self, temp_db, bare):
        bare.on_narration_payload(lambda payload, info: "prose")
        payload = {"player_view": {}}

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=_chat(temp_db)), payload)

        assert out == payload

    def test_a_non_callable_hook_is_refused_at_registration(self, bare):
        with pytest.raises(ExtensionError):
            bare.on_narration_payload("not a function")

    def test_a_disabled_extension_stops_colouring_the_narration(self, temp_db,
                                                                bare):
        """Disable has to reach the reader's prose, not just the panel."""
        chat_id = _chat(temp_db)
        bare.narration_context(chat_id).set("Standing context.")
        extension_runtime.disable_extension("seams")

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {})

        assert "extension_context" not in out


    def test_an_extension_that_failed_to_register_colours_nothing(
            self, temp_db, ext_root):
        """"A malformed extension lands in `load_errors()` and its siblings
        load normally" is the module's own promise. A failed register strips
        every hook and unregisters every stage -- but a standing block is
        stored per STORY, so it outlives the session in which the extension
        worked and kept being injected by an extension shown in the menu as
        broken."""
        _write_extension(ext_root, "seams", {
            "id": "seams", "version": "1.0.0", "ext_api": 1,
            "capabilities": {"python": "extension.py", "chat_state": True},
        }, {"extension.py": "def register(api):\n    pass\n"})
        _enable("seams")
        chat_id = _chat(temp_db)
        extension_runtime._apis["seams"].narration_context(chat_id).set(
            "The corridors are dark and cold.")

        (ext_root / "seams" / "extension.py").write_text(
            "def register(api):\n    raise RuntimeError('boom')\n",
            encoding="utf-8")
        extension_runtime.reload()
        extension_runtime.activate(refresh=True)
        assert "boom" in extension_runtime.disabled_reasons()["seams"]

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {})

        assert "extension_context" not in out


# ------------------------------------------------------------ the live stage


class TestNarratorWiring:
    """That the seam is actually reached from `agents/narration.py`.

    Registering a hook nobody calls is the failure this file would otherwise
    not notice, and it is the one that costs a day: every unit test passes and
    the block never appears in a single beat.
    """

    def test_the_narrator_applies_the_seam_before_generating(self, temp_db,
                                                             bare, monkeypatch):
        from agents import narration

        chat_id = _chat(temp_db)
        bare.narration_context(chat_id).set("The ship is under tow.")

        seen = {}

        def fake_generate(payload, *args, **kwargs):
            seen["payload"] = payload
            return {"prose": "", "new_specifics": []}, [], []

        monkeypatch.setattr(narration, "_generate_narration", fake_generate)

        payload = narration._extension_narration_payload(
            _StubCtx(chat_id=chat_id), {"player_view": {}}, scope="narrator")

        assert payload["extension_context"][0]["text"] == "The ship is under tow."

    def test_the_wrapper_is_total(self, temp_db, bare, monkeypatch):
        """It runs inside the turn's wall clock; it may never raise."""
        from agents import narration

        def boom(*args, **kwargs):
            raise RuntimeError("dispatch exploded")

        monkeypatch.setattr(extension_runtime, "dispatch_narration_payload",
                            boom)
        payload = {"player_view": {}}

        out = narration._extension_narration_payload(
            _StubCtx(chat_id=_chat(temp_db)), payload, scope="narrator")

        assert out == payload


# ------------------------------------------------------- the demo extension


class TestOverlayDemo:
    """The shipped reference extension, exercised end to end.

    A reference extension that is never run is documentation with a file
    extension. These assert the two claims its manifest makes -- that it serves
    its own frame routes, and that what it stores through them is what the
    narrator is then told.
    """

    def test_it_installs_a_frame_that_reaches_the_narrator(self, temp_db,
                                                           real_ext_root):
        chat_id = _chat(temp_db)
        _enable("overlay-demo")

        extension_runtime.dispatch_route(
            "overlay-demo", "POST", "/frame",
            query={"chat_id": str(chat_id)},
            body={"frame": "Three days into a fuel emergency."})

        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {"player_view": {}})

        assert out["extension_context"] == [
            {"source": "overlay-demo",
             "text": "Three days into a fuel emergency.",
             "revision": 1}]

    def test_saving_an_empty_frame_clears_it(self, temp_db, real_ext_root):
        """"Saving nothing removes it" is a behaviour a reader will rely on."""
        chat_id = _chat(temp_db)
        _enable("overlay-demo")
        query = {"chat_id": str(chat_id)}

        extension_runtime.dispatch_route(
            "overlay-demo", "POST", "/frame", query=query,
            body={"frame": "Installed."})
        cleared = extension_runtime.dispatch_route(
            "overlay-demo", "POST", "/frame", query=query, body={"frame": ""})

        assert cleared["frame"] == ""
        out = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {})
        assert "extension_context" not in out

    def test_reading_reports_the_stored_revision(self, temp_db, real_ext_root):
        chat_id = _chat(temp_db)
        _enable("overlay-demo")
        query = {"chat_id": str(chat_id)}

        extension_runtime.dispatch_route(
            "overlay-demo", "POST", "/frame", query=query,
            body={"frame": "First."})
        extension_runtime.dispatch_route(
            "overlay-demo", "POST", "/frame", query=query,
            body={"frame": "Second."})
        read = extension_runtime.dispatch_route(
            "overlay-demo", "GET", "/frame", query=query)

        assert read == {"chat_id": chat_id, "frame": "Second.", "revision": 2}

    def test_an_oversized_frame_is_a_400_not_a_500(self, temp_db,
                                                   real_ext_root):
        """The demo bounds well under the host ceiling, so a reader typing into
        the box gets a sentence rather than the host's refusal."""
        chat_id = _chat(temp_db)
        _enable("overlay-demo")

        with pytest.raises(ExtensionError):
            extension_runtime.dispatch_route(
                "overlay-demo", "POST", "/frame",
                query={"chat_id": str(chat_id)},
                body={"frame": "x" * 601})
