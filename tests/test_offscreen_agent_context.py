"""What an absent mind is allowed to know.

The `character_agent` rung is the highest-fidelity purchase in the off-screen
design and the most dangerous: it lets a character who is nowhere near the
player act on their own initiative. The failure it must not have is named in
the design as the fatal one — "how did he know that" — and its shape is a
villain who reacts before evidence reaches them, in prose that sounds entirely
plausible while doing it.

So the context is built as a STRUCTURE rather than as an instruction, and
these tests are about what is absent.
"""

from __future__ import annotations

import json
import time

import pytest

from world import offscreen


def _subject(state=None, sheet=None):
    return {
        "id": "kestrel_uid",
        "char_id": None,
        "sheet": sheet or {"identity": {"name": "Kestrel", "uid": "kestrel_uid"},
                           "psychology": {"drive": {"essence": "hold the gate"},
                                          "traits": {"wary": 0.8}}},
        "state": state or {},
    }


class TestTheFirewallIsAStructure:
    def test_it_is_an_allowlist_not_a_denylist(self, temp_db):
        """A denylist grows a hole every time the payload gains a key, and the
        hole is silent. The roadmap lists what must be excluded; the way to
        honour a list of exclusions is to never build the thing they would
        have to be removed from."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        ctx = offscreen.agent_context(cid, _subject())
        assert set(ctx) <= set(offscreen.AGENT_CONTEXT_KEYS)

    def test_there_is_no_scene_to_forget_to_leave_out(self):
        """`agent_context` takes no scene parameter at all. A signature that
        cannot receive the objective world cannot leak it."""
        import inspect

        params = inspect.signature(offscreen.agent_context).parameters
        assert "scene" not in params
        assert "player_room" not in params
        assert set(params) == {"cid", "entry", "frame_id", "clock"}

    def test_nothing_about_the_player_reaches_it(self, temp_db):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        ctx = offscreen.agent_context(cid, _subject())
        blob = json.dumps(ctx).casefold()
        for forbidden in ("player", "position", "scene", "narrat"):
            assert forbidden not in blob

    def test_importance_never_becomes_content(self, temp_db):
        """Distance and importance may select model spend. A character who
        could tell how important they were would be reading the engine rather
        than the world."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        sheet = {"identity": {"name": "Kestrel"},
                 "psychology": {"drive": {}, "traits": {}},
                 "simulation": {"tier": "major", "importance_override": 0.9}}
        ctx = offscreen.agent_context(cid, _subject(sheet=sheet))
        blob = json.dumps(ctx).casefold()
        assert "importance" not in blob and "tier" not in blob


class TestItReceivesWhatItLegitimatelyHas:
    def test_its_own_carried_reports_arrive_already_degraded(self, temp_db):
        """The reports were subtracted at the moment each was heard, so this
        hands over what the character BELIEVES rather than what is true."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        heard = {"world_event_id": "e1", "retellings": 2, "told_by": "Rem",
                 "claim": "a stranger barred the gate in some place"}
        ctx = offscreen.agent_context(cid, _subject(state={
            "carried_reports": [heard]}))
        assert ctx["carried_reports"] == [heard]

    def test_it_gets_its_own_drive_and_beliefs(self, temp_db):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        ctx = offscreen.agent_context(cid, _subject(state={
            "beliefs": {"the gate": "still holds"}}))
        assert ctx["drive"]["essence"] == "hold the gate"
        assert ctx["beliefs"] == {"the gate": "still holds"}

    def test_a_mind_with_nothing_gets_an_empty_context_not_an_error(self,
                                                                   temp_db):
        """An absent character with no memories, no plans and no reports is
        the ordinary case, not an exception. Failing here would make the rung
        unreachable for exactly the characters it is cheapest to run."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        ctx = offscreen.agent_context(cid, _subject())
        assert ctx["memories"] == [] and ctx["plans"] == []
        assert ctx["carried_reports"] == []

    def test_a_real_char_id_reaches_real_memory_rows(self, temp_db):
        """The memory read shipped selecting a `summary` column the memories
        table has never had, and every test exercised it with char_id=None —
        so the query that crashed on any real candidate looked covered and
        was not. The paid producer's first live run would have been the
        crash's first exercise."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)", ("Kestrel", "{}", "{}", time.time()))
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,content) "
            "VALUES(?,?,?,?)", (cid, char_id, 3, "the gate held"))
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,content,archived) "
            "VALUES(?,?,?,?,1)", (cid, char_id, 4, "an archived aside"))
        entry = _subject()
        entry["char_id"] = char_id
        ctx = offscreen.agent_context(cid, entry)
        assert ctx["memories"] == [{"summary": "the gate held",
                                    "turn_idx": 3}]


class TestSelectionStaysSeparateFromContent:
    def test_candidates_are_chosen_without_reading_the_world(self):
        """`full_agent_candidates` already documents this; it is asserted here
        because the producer is the step that would be tempted to pass the
        scene along for convenience."""
        import inspect

        params = inspect.signature(offscreen.full_agent_candidates).parameters
        assert "scene" not in params and "player_room" not in params
        # And the body reads only the character's own rows, never the turn.
        body = inspect.getsource(offscreen.full_agent_candidates)
        body = body[body.index('"""', body.index('"""') + 3) + 3:]
        assert "scene" not in body and "director" not in body
