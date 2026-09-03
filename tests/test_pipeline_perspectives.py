"""Reading a pipeline step the way the engine actually produced it.

Two things the pipeline drawer could not show, both of which cost real
diagnosis time on chat 38:

1. A perception step emits one view PER MIND, keyed by cast id and the literal
   "player". Dumped as raw JSON it is a wall of escaped prose with the reader
   doing the id-to-name join in their head, and a view missing an entire
   sensory channel looks exactly like a view that is merely shorter. That is
   how turn idx 140 — a character delivered a sound-only view of an embrace
   happening six feet in front of him — went unnoticed for six turns.

2. Steps that genuinely run at the same time were rendered as a flat list, so
   a concurrent pair read as two sequential steps that happened to be quick.
   Reported, reasonably, as "I cannot see them in the pipeline UI".
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT_JS = (ROOT / "static/js/chat.js").read_text(encoding="utf-8")
STYLES = (ROOT / "static/styles.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


class TestTheApiNamesThePerceivers:
    def test_ids_resolve_to_the_names_a_reader_knows(self, temp_db):
        from web import app

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("The Doctor",
             '{"identity": {"name": "The Doctor"}}', time.time()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))

        names = app._perceiver_names(chat_id)
        assert names[str(char_id)] == "The Doctor"
        assert "player" in names

    def test_a_dormant_character_is_still_named(self, temp_db):
        """A turn is read long after it ran. A character dormant or detached
        today still has views on the beats they were present for, and an
        unresolvable id is exactly the friction this removes."""
        from web import app

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("Guinan", '{"identity": {"name": "Guinan"}}', time.time()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "dormant", "{}"))

        assert app._perceiver_names(chat_id)[str(char_id)] == "Guinan"

    def test_the_per_story_card_wins_over_the_reusable_one(self, temp_db):
        """`chat_chars.sheet` is the per-story authored card and is what
        `scene.active_cast` resolves; the drawer must not label a mind with a
        name the story stopped using."""
        from web import app

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("Reusable", '{"identity": {"name": "Reusable"}}', time.time()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
            "VALUES(?,?,?,?,?)",
            (chat_id, char_id, "active", "{}",
             '{"identity": {"name": "Per-story"}}'))

        assert app._perceiver_names(chat_id)[str(char_id)] == "Per-story"

    def test_the_route_hands_the_map_to_the_drawer(self):
        from web import app

        src = inspect.getsource(app.pipeline_get)
        assert '"perceivers": _perceiver_names(' in src


class TestEveryStepIsReadableThroughALens:
    """The facets are derived from the content, not declared per step key, so
    a stage that grows a field gets a button for it without anyone remembering
    to add one."""

    def test_a_per_mind_step_is_read_per_mind(self):
        block = _between(CHAT_JS, "function stepLenses(",
                         "function perceiverLabel(")
        assert 'kind: "perceiver"' in block
        assert 'kind: "mind"' in block

    def test_everything_else_falls_back_to_its_own_top_level_keys(self):
        block = _between(CHAT_JS, "function stepLenses(",
                         "function perceiverLabel(")
        assert "Object.keys(content)" in block
        assert 'kind: "key"' in block

    def test_the_engine_notes_are_not_offered_as_a_facet(self):
        """They are rendered above the step in their own block; a button for
        them would be the same information twice."""
        block = _between(CHAT_JS, "function stepLenses(",
                         "function perceiverLabel(")
        assert '!== "_engine_notes"' in block

    def test_both_loops_are_sliced_by_the_mind_that_acted(self):
        block = _between(CHAT_JS, "function loopMindIds(",
                         "// What this step can be read")
        assert "speaker_id" in block and "reactor_id" in block

    def test_a_loop_shows_the_rounds_and_the_results_map(self):
        """The two are written separately and rehydrated separately on a
        rerun, so them disagreeing is a bug class — invisible if only one is
        shown."""
        block = _between(CHAT_JS, "function mindSlice(", "function keySlice(")
        assert "content.rounds" in block
        assert "character_results" in block and "reaction_results" in block

    def test_a_prose_field_is_shown_as_prose(self):
        """resolved_event, summary and the narrator's text are the whole
        reason to open most steps, and they are unreadable with their newlines
        spelled backslash-n."""
        block = _between(CHAT_JS, "function keySlice(", "// What the deterministic")
        assert 'typeof value === "string"' in block
        assert "JSON.stringify(value, null, 2)" in block

    def test_the_bar_shows_how_much_is_in_each_facet(self):
        """An empty list and a missing key are different answers, and the
        shape of a step should be readable without opening anything."""
        block = _between(CHAT_JS, "function facetBadge(", "function lensLabel(")
        assert "Array.isArray(value)" in block
        assert '"∅"' in block

    def test_a_null_view_is_shown_as_an_answer_not_an_absence(self):
        """null is the perception layer SAYING nothing registered. Rendering it
        as a missing key loses the distinction between a mind that received
        nothing and a mind that was never asked."""
        block = _between(CHAT_JS, "function perceiverSlice(",
                         "function renderEngineNotes(")
        assert "nothing registered" in block

    def test_the_observations_ride_with_the_view_they_came_from(self):
        """The structured observations are the projection of the prose. Read
        apart from it, a channel missing from one is invisible in the other."""
        block = _between(CHAT_JS, "function perceiverSlice(",
                         "function renderEngineNotes(")
        assert "content.observations" in block

    def test_the_raw_json_is_always_one_click_away(self):
        block = _between(CHAT_JS, "function renderLensBar(",
                         "function lensSlice(")
        assert "{ } JSON" in block
        assert "The whole step as stored" in block

    def test_the_chosen_facet_survives_a_variant_switch(self):
        """Comparing rerolls is most of what this drawer is for, and it only
        works if both sides are read through the same lens."""
        block = _between(CHAT_JS, "for (const s of p.steps) {",
                         "const controls = el(")
        assert "let lens = null;" in block
        assert "lens = lenses.kind" in block

    def test_only_a_per_mind_step_opens_on_something_other_than_json(self):
        """The habit of reading a step whole must be unchanged: the facets are
        an addition, not a redirection."""
        block = _between(CHAT_JS, "const lenses = stepLenses(content);",
                         "// A thinking model's own trace")
        assert 'lens = lenses.kind === "key" ? "" : lenses.ids[0];' in block
        assert "JSON.stringify(content, null, 2)" in block

    def test_a_step_that_is_not_an_object_still_renders(self):
        block = _between(CHAT_JS, "const lenses = stepLenses(content);",
                         "// A thinking model's own trace")
        assert "if (!lenses) {" in block


class TestConcurrencyIsVisible:
    def test_the_runtime_stamps_the_group_on_every_start_event(self):
        from agents import runtime

        src = inspect.getsource(runtime._run_parallel_group)
        assert '"group": members' in src
        assert "parallel_with=" in src

    def test_both_pairings_go_through_the_one_helper(self):
        """Character siblings and narrator beside narrator_extra were copies
        of the same body — which is why making concurrency visible had to
        mean editing it in every copy. (The third pairing, mapping beside
        action-onset perception, went with the mapping model: the world
        context is compiled deterministically before perception, so there is
        no provider latency left to overlap.)"""
        from agents import runtime

        src = inspect.getsource(runtime._run_pipeline)
        assert src.count("_run_parallel_group(") == 2
        assert "_stream_parallel(bus, jobs, holders)" not in src

    def test_the_live_log_marks_a_group(self):
        block = _between(CHAT_JS, "function liveStep(", "function handleEvt(")
        assert "lk-parallel" in block
        assert '"⇉ "' in block
        assert ".lk-parallel" in STYLES

    def test_the_status_line_does_not_name_one_of_a_pair_alone(self):
        block = _between(CHAT_JS, "function turnStatusSet(",
                         "function turnStatusStop()")
        assert "running > 1" in block
        assert "running alongside" in block

    def test_the_suffix_is_added_after_the_label_is_matched(self):
        """friendlyPhase pattern-matches the label (the scene-manager prefix,
        the character-name strip), so decorating the label first would corrupt
        the match."""
        block = _between(CHAT_JS, "function turnStatusSet(",
                         "function turnStatusStop()")
        assert block.index("friendlyPhase(") < block.index("running > 1")

    def test_the_persisted_view_can_still_tell(self):
        """The drawer reads the steps table long after the stream events are
        gone, and `ord` cannot express "these two ran at once"."""
        block = _between(CHAT_JS, "function renderEngineNotes(",
                         "// ---- Pipeline drawer ----")
        assert "parallel_with" in block
        assert "ran concurrently with" in block


class TestTheRepairsAreShown:
    def test_the_drawer_renders_the_engine_notes(self):
        block = _between(CHAT_JS, "function renderEngineNotes(",
                         "// ---- Pipeline drawer ----")
        assert "_engine_notes" in block
        assert "notes.warnings" in block

    def test_the_notes_block_is_in_the_step_box(self):
        block = _between(CHAT_JS, 'class:\n          "step"', "show(cur);")
        assert "notes," in block
        assert "perspectives," in block

    def test_a_warning_is_styled_as_one(self):
        assert ".engine-notes .engine-warning" in STYLES


class TestTheDirectorsSpecialistsAreTabsOfItsOwnWindow:
    """A Director stage is ONE step made of several calls.

    The prose author owns the beat's account; the specialists own the
    state_diff channels the beat touches. Rendered flat, all six were a
    nested blob under `orchestration`, so reading what one hand actually
    did meant scrolling a merged diff and matching channel names by eye --
    on the very stage where "which hand wrote this" is the first question
    anyone asks. They are facets of the Director's own step, which is what
    they are.
    """

    def test_the_specialists_are_a_lens_of_their_own(self):
        block = _between(CHAT_JS, "function stepLenses(",
                         "function perceiverLabel(")
        assert 'kind: "specialist"' in block

    def test_the_roster_is_read_off_the_step_not_hardcoded(self):
        """A specialist added or renamed in agents/director.py must need
        nothing here -- a hardcoded list is a second roster to drift."""
        block = _between(CHAT_JS, "function specialistIds(",
                         "function stepLenses(")
        assert "record.specialists" in block
        for name in ("body", "social", "contact", "objects", "spatial",
                     "offscreen"):
            assert f'"{name}"' not in block, name

    def test_a_specialist_that_never_ran_gets_no_tab(self):
        """Most beats dispatch about two of the six. A tab per specialist
        regardless would make every Director step look like it did six
        things, which is the opposite of what the lens is for."""
        block = _between(CHAT_JS, "function specialistIds(",
                         "function stepLenses(")
        assert "].run" in block or ".run)" in block

    def test_the_prose_author_gets_the_first_tab(self):
        """The beat's account is what a reader opens a Director step for;
        the channels are the follow-up question."""
        block = _between(CHAT_JS, "function stepLenses(",
                         "function perceiverLabel(")
        assert '["prose"].concat(specialists)' in block

    def test_the_prose_tab_subtracts_what_it_does_not_own(self):
        """Showing the merged diff under the prose author would credit it
        with every channel a specialist wrote -- the exact confusion the
        lens exists to end."""
        block = _between(CHAT_JS, "function specialistSlice(",
                         "// What the deterministic layer did")
        assert "delegated.has(channel)" in block

    def test_granted_and_empty_reads_differently_from_gated_out(self):
        """Two different answers. "I was asked and had nothing" is the
        specialist reporting; "nobody asked" is the scope gate deciding.
        Collapsing them hides which of the two a missing encoding was."""
        block = _between(CHAT_JS, "function specialistSlice(",
                         "// What the deterministic layer did")
        assert "granted and left empty" in block
        assert "gated out this beat" in block

    def test_a_failed_specialist_says_so_on_its_tab_and_its_label(self):
        """Fail-open means the beat survives a specialist dying, which is
        correct and is exactly why it must not be silent in the drawer."""
        slice_block = _between(CHAT_JS, "function specialistSlice(",
                               "// What the deterministic layer did")
        assert "DID NOT RUN" in slice_block
        label_block = _between(CHAT_JS, "function lensLabel(",
                               "function renderLensBar(")
        assert "·failed" in label_block

    def test_the_repair_pass_shows_on_the_hand_that_was_asked_again(self):
        """The seam routes an omission to the channel's owner, so "was this
        hand asked twice" is answerable from its own tab rather than from
        the reconciliation blob."""
        block = _between(CHAT_JS, "function specialistSlice(",
                         "// What the deterministic layer did")
        assert "specialist_repairs" in block

    def test_the_merged_value_is_labelled_as_merged(self):
        """A channel a later repair mended shows its mended content. That
        is the truth about the channel and not the specialist's raw reply,
        and the difference matters when reading a beat that went wrong."""
        block = _between(CHAT_JS, "function specialistSlice(",
                         "// What the deterministic layer did")
        assert "merged diff" in block
