"""The room can read the story's configuration, so it can be asked about it.

The Story Planner is a conversation before it is a writer: the cheapest way to
get a critique of a change is to ask for one before publishing anything. That
only works over what the room can see, and until now it could see the world and
not the dials the same world runs under -- it authored rooms the Director then
renders under a genre and tone it had never read, and could not answer "will
this land?" about a setting it had no tool for.

READ ONLY, and deliberately. No capability gates it, no operation writes it,
and nothing here lets the room change a dial: a host still turns them, which is
the settled rule (a value the room owns must roll back with a rewind, and every
one of these is preserved across exactly that).
"""
import time

import pytest

from story.room_tools import TOOLS, run_tool, tool_manifest


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Config", "A cold harbour.", time.time()))


def _tool(name):
    return next((t for t in TOOLS if t["name"] == name), None)


class TestItIsAReadTool:
    def test_it_is_registered_and_takes_no_arguments(self):
        tool = _tool("inspect_config")
        assert tool is not None
        assert tool["args"]["properties"] == {}
        assert tool["args"]["required"] == []

    def test_it_writes_nothing(self):
        """A read tool that could write would need a mandate; this one is
        listed among the reads and holds no package seam."""
        import inspect

        from story import room_tools
        src = inspect.getsource(room_tools._t_inspect_config)
        for writer in ("wset", "qi(", "INSERT", "UPDATE", "DELETE",
                       "new_package", "publish"):
            assert writer not in src, "%s is a write" % writer

    def test_it_needs_no_mandate(self):
        from story.mandates import MANDATE_CAPABILITIES
        assert "inspect_config" not in MANDATE_CAPABILITIES

    def test_the_manifest_offers_it(self):
        names = [t["name"] for t in tool_manifest()]
        assert "inspect_config" in names


class TestWhatItReturns:
    def test_it_answers_for_a_story_that_configured_nothing(self, temp_db):
        cid = _chat(temp_db)
        out = run_tool(cid, "inspect_config", {})
        for section in ("style", "scene", "populace", "offscreen"):
            assert section in out, section

    def test_it_carries_the_house_style_the_director_is_handed(self, temp_db):
        """One free-text field since 2026-09-04: `genre`, `director_notes`,
        `mapping_notes` and `avoid` were retired to the room itself, which is
        where standing intent now lives."""
        cid = _chat(temp_db)
        temp_db.wset(cid, "style_guide", {
            "tone": "wry, unhurried",
            "genre": "retired", "avoid": "retired"})

        out = run_tool(cid, "inspect_config", {})

        assert out["style"]["tone"] == "wry, unhurried"
        assert "genre" not in out["style"]
        assert "avoid" not in out["style"]

    def test_it_reports_the_one_offscreen_question_not_five_rungs(self, temp_db):
        cid = _chat(temp_db)
        temp_db.wset(cid, "dialogue_config", {"offscreen_cognition": False})

        out = run_tool(cid, "inspect_config", {})

        assert out["offscreen"]["cognition"] is False
        assert out["offscreen"]["rung"] == "reactive"

    def test_it_reports_the_counts_a_plan_has_to_live_within(self, temp_db):
        cid = _chat(temp_db)
        temp_db.wset(cid, "background_config", {"max_reactors": 2})

        out = run_tool(cid, "inspect_config", {})

        assert out["populace"]["max_reactors"] == 2
        assert "scene_life" in out["populace"]

    def test_it_says_which_of_these_the_room_may_not_change(self, temp_db):
        """The room reads a dial to reason about it, and a reader that does not
        say so invites a proposal the engine will refuse."""
        cid = _chat(temp_db)
        out = run_tool(cid, "inspect_config", {})
        assert out["host_owned"] is True


class TestItDoesNotLeak:
    def test_it_carries_no_credential_and_no_model_name(self, temp_db):
        """These are install-wide settings, not story state: they are absent
        from the chat archive by design, and a story-facing tool must not
        reintroduce them."""
        import json

        cid = _chat(temp_db)
        blob = json.dumps(run_tool(cid, "inspect_config", {})).casefold()
        for secret in ("api_key", "host_pw_hash", "host_secret", "provider",
                       "gemini", "glm", "gpt", "claude"):
            assert secret not in blob, secret
