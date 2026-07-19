"""Regression tests for two more bugs from Fable's whole-codebase audit:

B6 -- scene.py's director_context (fed into the Director's own
director_interpret/director_resolve payload, and into mapping's) selected
the last N turns by idx across EVERY frame, unlike its sibling
recent_events which was already frame-filtered. Since idx is global play
order, one frame's Director could see another concurrently-played
frame's player declarations and resolved outcomes -- a leak at the
objective-truth layer, which then propagates to perception/character/
narration. The narrator/narrator_extra rhythm-context queries had the
same gap. All fixed by adding the same frame filter recent_events
already used.

B7 -- chat_import remapped memories' char_id through resources.characters
(old_id -> newly created/matched character) but passed memory_summaries
straight through with the SOURCE database's char_id, unmapped. Importing
an archive whose characters don't already exist locally either crashes
(PRAGMA foreign_keys=ON) or, worse, silently attaches one character's
autobiographical summary to a different character that happens to share
the raw id locally. Fixed by remapping (and dropping unmappable rows)
exactly like the sibling memories list already did.
"""

from __future__ import annotations

import json
import time

import app
from character_schema import default_character_data
from frames import create_frame


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


class TestDirectorContextIsFrameFiltered:
    def test_a_future_frames_turn_does_not_leak_into_the_present_directors_context(
        self, temp_db,
    ):
        from scene import director_context

        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 0, "present-turn declaration", time.time(), None),
        )
        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "future-turn declaration", time.time(), future),
        )

        present_ctx = director_context(chat_id, n=5, frame_id=None)
        future_ctx = director_context(chat_id, n=5, frame_id=future)

        assert [c["player_input"] for c in present_ctx] == ["present-turn declaration"]
        assert [c["player_input"] for c in future_ctx] == ["future-turn declaration"]


class TestNarratorRhythmContextIsFrameFiltered:
    def test_narrator_previous_prose_query_excludes_other_frames(self, temp_db):
        from db import q as db_q

        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        present_turn = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 0, "x", time.time(), None),
        )
        future_turn = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "y", time.time(), future),
        )
        for turn_id, prose in ((present_turn, "present prose"), (future_turn, "future prose")):
            step_id = temp_db.qi(
                "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                (turn_id, "narrator", "Narrator", 0),
            )
            temp_db.qi(
                "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                (step_id, json.dumps({"prose": prose}), time.time()),
            )

        # Same query narrator() runs, frame-filtered to the FUTURE frame
        # looking at turns before idx=2 -- must see only ITS OWN prior
        # prose, never the present's.
        rows = db_q(
            "SELECT v.content FROM turns t "
            "JOIN steps s ON s.turn_id=t.id AND s.key='narrator' "
            "JOIN variants v ON v.step_id=s.id AND v.active=1 "
            "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? ORDER BY t.idx DESC LIMIT 4",
            (chat_id, 2, future),
        )
        prev = [json.loads(r["content"])["prose"] for r in rows]
        assert prev == ["future prose"]


class TestChatImportRemapsMemorySummaryCharIds:
    def test_a_freshly_imported_characters_summary_lands_on_the_new_char_id(self, temp_db):
        chat_id = _make_chat(temp_db)
        source_char_id = _make_char(temp_db, "Alice")

        export = {
            "version": 3,
            "chat": {"name": "Source", "persona_id": None, "scenario": ""},
            "frames": [], "turns": [], "world": {}, "participants": [],
            "char_frames": [], "memories": [],
            "memory_summaries": [{
                "char_id": source_char_id, "scope": "autobiographical",
                "start_turn_idx": 0, "end_turn_idx": 5,
                "summary": "Alice's life so far.", "key_phrases": [], "unresolved_threads": [],
            }],
            "events": [], "checkpoints": [], "lorebook": None, "lorebooks": [],
            "resources": {
                "characters": [{
                    "old_id": source_char_id,
                    "sheet": default_character_data("Alice"),
                    "source": {},
                    # Deliberately no resource_uid -- forces
                    # _import_or_match_character to create a BRAND NEW
                    # character row with a different id than source_char_id,
                    # exactly like importing an archive from a different
                    # database where no character already matches.
                }],
            },
        }

        result = app.chat_import({"data": export})
        new_chat_id = result["id"]

        new_char = temp_db.q(
            "SELECT id FROM characters WHERE name=? AND id!=?",
            ("Alice", source_char_id), one=True,
        )
        assert new_char is not None
        new_char_id = new_char["id"]

        summary_row = temp_db.q(
            "SELECT char_id, summary FROM memory_summaries WHERE chat_id=?",
            (new_chat_id,), one=True,
        )
        assert summary_row is not None
        assert summary_row["char_id"] == new_char_id
        assert summary_row["summary"] == "Alice's life so far."

        # And it must NOT have landed on the source database's raw id --
        # that id belongs to a DIFFERENT character (or nothing at all)
        # in the imported chat's own cast.
        assert summary_row["char_id"] != source_char_id
