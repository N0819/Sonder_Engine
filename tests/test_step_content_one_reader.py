"""One reader of a step's active content (review 2026-09-07, B23).

A step's output is opaque JSON in `variants.content`, one active row per
step, and four modules asked the same question of it: the pipeline
rehydrating a rerun, a read-only projection answering a panel, the backdrop
painter quoting the player's own view, and the Dramaturge quoting recent
narration. Four copies of one query is four places for one rule about that
table to be stated -- and they had already drifted twice:

  * `web/story_view._step_content` kept the engine's own repair log
    (`_engine_notes`) that `active_content` strips, on the stated grounds
    that the shared reader lived behind the pipeline's import graph;
  * `dressing/backdrops` and `agents/dramaturge` each called `.get(...)` on
    whatever the JSON parsed to, which is an `AttributeError` -- not one of
    the errors they guarded -- the moment a step's content is not a mapping.

`persist/steps.py` is the reader now: it imports `core.db` and nothing else,
so the import-graph justification is gone, and every site above reads through
it.

The second rule that table needs is the one those two `AttributeError`s were
instances of, and it is stated once in `active_mapping`: a step's content is
any JSON -- `/api/steps/{sid}/edit` stores whatever the request body holds,
with no shape check -- so a consumer reading NAMED KEYS off a step must
narrow to a mapping first. Four shipped consumers still assumed one and now
read through `active_mapping`: the chat list route's per-turn prose
(`chat_get`), the extra-player view (`guest_state`), the prose edit
(`edit_prose`, which raised `TypeError` rather than `AttributeError`, on
`content['prose'] = ...`), and the greeting override
(`story.greetings._override_narrator`).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest

from agents import dramaturge, storage
from dressing import backdrops
from persist import steps as step_store
from story import greetings
from web import app, story_view


@pytest.fixture()
def chat_turn(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 0, "look around", time.time()))
    return chat_id, turn_id


class TestOneDefinition:
    def test_every_spelling_is_the_same_function(self):
        assert storage.active_content is step_store.active_content
        assert storage.ENGINE_NOTES_KEY is step_store.ENGINE_NOTES_KEY

    def test_the_reader_needs_no_pipeline(self):
        """The whole justification for the second copy: importing
        `agents.storage` runs `agents/__init__.py`, which pulls the pipeline
        in, and a projection answering a panel refresh must not.

        Asked of a fresh interpreter rather than of this module's own
        imports, because the property is about what LANDS in `sys.modules`,
        not about which lines `persist/steps.py` happens to spell: an import
        added to `persist/__init__.py`, or one buried in a module `core.db`
        reaches, would lose it without touching the reader at all.
        """
        import pathlib

        root = pathlib.Path(step_store.__file__).resolve().parents[1]
        probe = (
            "import sys, json; import persist.steps; "
            "print(json.dumps(sorted(m for m in sys.modules "
            "if m == 'agents' or m.startswith('agents.'))))"
        )
        done = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(root), capture_output=True, text=True, check=True,
        )
        assert json.loads(done.stdout.strip().splitlines()[-1]) == []


class TestTheProjectionReadsWhatTheEngineReads:
    def test_the_repair_log_is_stripped_on_both_sides(self, chat_turn):
        _chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "perception_outcome", "Perception", 0, {
            "views": {"player": "The lamp is lit."},
            step_store.ENGINE_NOTES_KEY: {"warnings": ["dropped a sentence"]},
        })
        projected = story_view._step_content(turn_id, "perception_outcome")
        assert projected == storage.active_content(turn_id, "perception_outcome")
        assert step_store.ENGINE_NOTES_KEY not in projected
        assert projected["views"] == {"player": "The lamp is lit."}

    def test_a_missing_step_is_absent_rather_than_empty(self, chat_turn):
        _chat_id, turn_id = chat_turn
        assert story_view._step_content(turn_id, "narrator") is None

    def test_a_non_mapping_step_answers_nothing(self, chat_turn):
        """The projection reads named keys off a mapping; a step whose
        content is a list or a string answers none of them."""
        _chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0, "bare prose")
        assert story_view._step_content(turn_id, "narrator") is None

    def test_the_delivered_view_still_reads(self, chat_turn):
        _chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "perception_outcome", "Perception", 0, {
            "views": {"player": "The lamp is lit."},
            "observations": {"player": [{"what": "a lamp"}]},
            step_store.ENGINE_NOTES_KEY: {"warnings": ["noted"]},
        })
        delivered = story_view._delivered(turn_id, "player")
        assert delivered["stage"] == "perception_outcome"
        assert delivered["view"] == "The lamp is lit."
        assert delivered["observations"] == [{"what": "a lamp"}]


class TestTheOtherQuotersOfAStep:
    def test_the_backdrop_reads_the_players_own_view(self, chat_turn):
        chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "perception_outcome", "Perception", 0,
                          {"views": {"player": "Rain on the glass."}})
        assert backdrops.player_view_for_turn(chat_id, 0) == "Rain on the glass."

    def test_the_backdrop_survives_a_non_mapping_step(self, chat_turn):
        chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "perception_outcome", "Perception", 0,
                          "not a mapping")
        assert backdrops.player_view_for_turn(chat_id, 0) == ""

    def test_the_dramaturge_quotes_the_narration(self, chat_turn):
        chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0,
                          {"prose": "The door gives."})
        stream = dramaturge.player_visible_stream(chat_id)
        assert [beat["narration"] for beat in stream] == ["The door gives."]

    def test_the_dramaturge_survives_a_non_mapping_step(self, chat_turn):
        chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0, "bare prose")
        stream = dramaturge.player_visible_stream(chat_id)
        assert [beat["narration"] for beat in stream] == [""]


class TestAHandEditedStepIsAnyJSON:
    """`/api/steps/{sid}/edit` stores whatever the body holds, so every
    consumer reading named keys off a step narrows first (`active_mapping`).
    Each of these raised before -- `AttributeError` on a read, `TypeError` on
    the assignment -- inside the route, so one mangled step took out a whole
    chat rather than one beat's prose."""

    def test_the_narrowing_answers_nothing_rather_than_raising(self, chat_turn):
        _chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0, ["bare prose"])
        assert step_store.active_mapping(turn_id, "narrator") == {}
        # A step that never ran answers the same nothing; `active_content`
        # is still the one that tells them apart.
        assert step_store.active_mapping(turn_id, "narrator_extra") == {}
        assert step_store.active_content(turn_id, "narrator_extra") is None

    def test_the_narrowing_hands_back_the_mapping_it_was_given(self, chat_turn):
        _chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0,
                          {"prose": "The door gives.",
                           step_store.ENGINE_NOTES_KEY: {"warnings": []}})
        assert step_store.active_mapping(turn_id, "narrator") == {
            "prose": "The door gives."}

    def test_the_chat_list_survives_a_non_mapping_narrator(self, chat_turn):
        chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0, ["bare prose"])
        listed = app.chat_get(chat_id)["turns"]
        assert [t["prose"] for t in listed] == [""]

    def test_the_prose_edit_survives_a_non_mapping_narrator(self, chat_turn):
        _chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0, ["bare prose"])
        assert app.edit_prose(turn_id, {"prose": "The corrected line."}) == {
            "ok": True, "prose": "The corrected line."}
        assert storage.active_content(turn_id, "narrator") == {
            "prose": "The corrected line."}

    def test_the_greeting_override_survives_a_non_mapping_narrator(self, chat_turn):
        _chat_id, turn_id = chat_turn
        storage.save_step(turn_id, "narrator", "Narrator", 0, "bare prose")
        greetings._override_narrator(turn_id, "The gate stands open.")
        assert storage.active_content(turn_id, "narrator") == {
            "prose": "The gate stands open."}


class TestTheWholeChatAtOnce:
    """`active_mappings`: the same answer for every turn of a chat, one query.

    The bulk reader is C22a's, and `tests/test_transcript_read_is_one_query.py`
    pins its COST and the two routes that read through it. These pin its
    ANSWER against the per-turn reader that lives beside it here, driving
    through `storage.save_step` -- the writer the engine actually uses --
    rather than building the rows by hand: a reroll supersedes a variant
    through that function, not through an `active` column written as 0. The
    neighbouring-key case is covered nowhere else, and it is the one a JOIN
    over `steps` gets wrong (review 2026-09-07, C22b).
    """

    def _chat_with_turns(self, temp_db, name="Bulk"):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            (name, "", time.time()))
        turns = [temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, idx, "", time.time()))
            for idx in range(4)]
        return chat_id, turns

    def test_it_answers_what_the_per_turn_reader_answers(self, temp_db):
        chat_id, turns = self._chat_with_turns(temp_db)
        storage.save_step(turns[0], "narrator_extra", "Extra", 0,
                          {"7": {"prose": "yours"}})
        storage.save_step(turns[1], "narrator_extra", "Extra", 0,
                          {"7": {"prose": "and yours"},
                           step_store.ENGINE_NOTES_KEY: {"warnings": ["x"]}})
        storage.save_step(turns[2], "narrator_extra", "Extra", 0, ["bare"])
        # turns[3] never ran that step at all.
        bulk = step_store.active_mappings(chat_id, "narrator_extra")
        assert {turn: bulk.get(turn) or {} for turn in turns} == {
            turn: step_store.active_mapping(turn, "narrator_extra")
            for turn in turns}
        assert bulk[turns[1]] == {"7": {"prose": "and yours"}}
        # A hand-edited non-mapping and a step that never ran are both absent,
        # which the callers read as the `{}` the per-turn form answers.
        assert turns[2] not in bulk and turns[3] not in bulk

    def test_it_stops_at_the_chat_it_was_asked_about(self, temp_db):
        mine, my_turns = self._chat_with_turns(temp_db, "Mine")
        theirs, their_turns = self._chat_with_turns(temp_db, "Theirs")
        storage.save_step(my_turns[0], "narrator_extra", "Extra", 0,
                          {"7": {"prose": "mine"}})
        storage.save_step(their_turns[0], "narrator_extra", "Extra", 0,
                          {"7": {"prose": "theirs"}})
        assert step_store.active_mappings(mine, "narrator_extra") == {
            my_turns[0]: {"7": {"prose": "mine"}}}
        assert step_store.active_mappings(theirs, "narrator_extra") == {
            their_turns[0]: {"7": {"prose": "theirs"}}}

    def test_it_reads_the_active_variant_and_not_a_superseded_one(self, temp_db):
        """A reroll through `save_step`, which is how a superseded variant is
        really made: the row is written, not flagged."""
        chat_id, turns = self._chat_with_turns(temp_db)
        storage.save_step(turns[0], "narrator_extra", "Extra", 0,
                          {"7": {"prose": "first draft"}})
        storage.save_step(turns[0], "narrator_extra", "Extra", 0,
                          {"7": {"prose": "second draft"}})
        assert step_store.active_mappings(chat_id, "narrator_extra") == {
            turns[0]: {"7": {"prose": "second draft"}}}

    def test_it_answers_one_key_and_not_its_neighbours(self, temp_db):
        chat_id, turns = self._chat_with_turns(temp_db)
        storage.save_step(turns[0], "narrator", "Narrator", 0,
                          {"prose": "the room"})
        storage.save_step(turns[0], "narrator_extra", "Extra", 1,
                          {"7": {"prose": "your corner of it"}})
        assert step_store.active_mappings(chat_id, "narrator_extra") == {
            turns[0]: {"7": {"prose": "your corner of it"}}}
