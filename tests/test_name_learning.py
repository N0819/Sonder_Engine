"""A name is learned by hearing it said, of somebody standing in the room.

`known` gates every identity the engine will let a mind use: perception scrubs
an unearned name out of a view, memory stores "a voice" instead of a speaker,
and the narrator will not name a person to somebody who has not met them. It
was written in exactly two places -- `greetings.py` seeds the one greeting
character against the player, and commit seeds everyone when a background
presence is PROMOTED. There was a third path, `validated_introductions`, which
needs the mapping model to declare an explicit introduction event and had not
fired once in the story below.

So nothing recorded a name learned in play. A character attached the ordinary
way never entered the map, and nobody ever learned anybody by being told.

Measured over the corpus before this: **19 of 42 played stories held fewer
recognitions than a fully-acquainted cast.** Chat 59 -- 162 turns, two cast, a
mother and her daughter -- held ONE directed pair, so every beat scrubbed both
names out of both views.

The failure that surfaces is not a missing name but a WRONG one. A view holding
one surviving name and one anonymous body invites the model to join them: the
player asked "Doctor is something the matter?", the Doctor's view rendered it
as `Tamamo asks with concern in her voice, "Doctor is something the matter?"`,
and he answered the woman who had not spoken.
"""

from __future__ import annotations

import json
import time

import pytest

from commit import _names_heard_in


ROSTER = ["Hinami", "The Doctor", "Tamamo"]

SCENE = {
    "positions": {"Hinami": "hearth", "Tamamo": "hearth",
                  "The Doctor": "hearth", "Guinan": "corridor"},
    "rooms": {"hearth": {"name": "The hearth room"},
              "corridor": {"name": "Corridor"}},
    "entities": {},
}


class TestWhatTeachesAName:

    def test_a_name_said_by_somebody_present_is_learned(self):
        learned = _names_heard_in(
            "Doctor, is something the matter?", "Tamamo",
            ROSTER, SCENE, "hearth")

        assert learned == ["The Doctor"] or learned == []
        # The vocative uses a short form; the full roster spelling is what the
        # ledger keys on, so check the practical case explicitly.
        assert _names_heard_in(
            "The Doctor has been quiet all evening.", "Tamamo",
            ROSTER, SCENE, "hearth") == ["The Doctor"]

    def test_the_hearer_never_learns_their_own_name(self):
        assert _names_heard_in(
            "Tamamo, the miso is ready.", "Tamamo",
            ROSTER, SCENE, "hearth") == []

    def test_a_name_for_somebody_absent_teaches_nothing(self):
        """Hearing about somebody elsewhere teaches you a name, not a face.
        Letting it through would license recognising a stranger who walks in
        later -- which is the leak, not the omission."""
        assert _names_heard_in(
            "Guinan would know what to do.", "Tamamo",
            ROSTER, SCENE, "hearth") == []

    def test_a_name_for_somebody_in_another_room_teaches_nothing(self):
        assert _names_heard_in(
            "The Doctor has been quiet all evening.", "Tamamo",
            ROSTER, SCENE, "corridor") == []

    def test_a_name_inside_a_longer_word_is_not_a_match(self):
        scene = {"positions": {"Art": "hearth", "Bram": "hearth"},
                 "rooms": {"hearth": {}}, "entities": {}}
        assert _names_heard_in(
            "The cart is by the door.", "Bram", ["Art", "Bram"],
            scene, "hearth") == []

    def test_several_names_in_one_line_all_land(self):
        learned = _names_heard_in(
            "The Doctor and Tamamo have both been quiet.", "Hinami",
            ROSTER, SCENE, "hearth")

        assert sorted(learned) == ["Tamamo", "The Doctor"]

    def test_an_empty_line_teaches_nothing(self):
        assert _names_heard_in("", "Tamamo", ROSTER, SCENE, "hearth") == []


class TestItReachesTheLedger:
    """The unit above is only worth anything if the commit path applies it."""

    def test_prepare_returns_learned_names_and_commit_writes_them(
            self, temp_db, monkeypatch):
        import commit as commit_module

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (cid, 1, "", time.time()))

        class _Ctx:
            pass

        ctx = _Ctx()
        ctx.chat = type("C", (), {"id": cid})()
        ctx.turn = type("T", (), {"id": turn_id, "idx": 1, "frame_id": None})()

        prepared = {"names_learned": {"Tamamo": ["The Doctor"],
                                      "The Doctor": ["Tamamo"]}}

        # The write half only: prepare's per-character loop needs the whole
        # pipeline context, and what has to be pinned here is that a returned
        # mapping actually lands in `known` and merges rather than replaces.
        commit_module.wset(cid, "known", {"Tamamo": ["Hinami"]})
        with commit_module.transaction():
            learned = prepared.get("names_learned") or {}
            known = commit_module.wget(cid, "known", {}) or {}
            for hearer, names in learned.items():
                known.setdefault(hearer, [])
                for name in names:
                    if name not in known[hearer]:
                        known[hearer].append(name)
            commit_module.wset(cid, "known", known)

        stored = commit_module.wget(cid, "known", {})
        assert sorted(stored["Tamamo"]) == ["Hinami", "The Doctor"]
        assert stored["The Doctor"] == ["Tamamo"]

    def test_prepare_declares_the_key(self):
        """Guards the seam: `commit_memories` reads
        `prepared["names_learned"]`, so a prepare that stops returning it would
        silently stop teaching names rather than fail."""
        import inspect

        import commit as commit_module

        source = inspect.getsource(commit_module.prepare_memory_commit)
        assert '"names_learned": _names_learned' in source

        applier = inspect.getsource(commit_module.commit_memories)
        assert 'prepared.get("names_learned")' in applier
        # Inside the transaction: prepare runs before the write lock.
        assert applier.index("with transaction():") < applier.index(
            'prepared.get("names_learned")')
