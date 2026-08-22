"""Pipeline inspection stays readable after the replacement-shell cutover."""

from __future__ import annotations

import inspect
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_JS = (ROOT / "static/js/ui-next/pipeline-inspector.js").read_text(encoding="utf-8")
PLAY_JS = (ROOT / "static/js/ui-next/play-view.js").read_text(encoding="utf-8")
STYLES = (ROOT / "static/css/ui/play.css").read_text(encoding="utf-8")


class TestTheApiNamesThePerceivers:
    def test_ids_resolve_to_the_names_a_reader_knows(self, temp_db):
        from web import app
        chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Test", "", time.time()))
        char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)", ("The Doctor", '{"identity": {"name": "The Doctor"}}', time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        names = app._perceiver_names(chat_id)
        assert names[str(char_id)] == "The Doctor"
        assert "player" in names

    def test_a_dormant_character_is_still_named(self, temp_db):
        from web import app
        chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Test", "", time.time()))
        char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)", ("Guinan", '{"identity": {"name": "Guinan"}}', time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)", (chat_id, char_id, "dormant", "{}"))
        assert app._perceiver_names(chat_id)[str(char_id)] == "Guinan"

    def test_the_per_story_card_wins_over_the_reusable_one(self, temp_db):
        from web import app
        chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Test", "", time.time()))
        char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)", ("Reusable", '{"identity": {"name": "Reusable"}}', time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) VALUES(?,?,?,?,?)", (chat_id, char_id, "active", "{}", '{"identity": {"name": "Per-story"}}'))
        assert app._perceiver_names(chat_id)[str(char_id)] == "Per-story"

    def test_the_route_hands_the_map_to_the_inspector(self):
        from web import app
        assert '"perceivers": _perceiver_names(' in inspect.getsource(app.pipeline_get)


class TestReplacementPipelineInspector:
    def test_turn_details_uses_the_replacement_inspector(self):
        assert 'import { renderPipelineInspector }' in PLAY_JS
        assert "renderPipelineInspector(documentRef, payload)" in PLAY_JS

    def test_every_step_has_a_raw_json_view_and_derived_facets(self):
        assert "Object.keys(content).filter" in INSPECTOR_JS
        assert '"{ } JSON"' in INSPECTOR_JS
        assert "The whole step as stored" in INSPECTOR_JS

    def test_perceiver_and_loop_steps_are_sliced_per_mind(self):
        for token in ('kind: "perceiver"', 'kind: "mind"', "speaker_id", "reactor_id", "content.observations", "nothing registered"):
            assert token in INSPECTOR_JS

    def test_prose_is_not_rendered_as_an_escaped_json_scalar(self):
        assert 'typeof value === "string"' in INSPECTOR_JS
        assert 'return value || "(empty)"' in INSPECTOR_JS

    def test_variant_switches_keep_the_selected_lens(self):
        for token in ("let lens = null", "lens = id", "Previous version", "Next version"):
            assert token in INSPECTOR_JS

    def test_engine_repairs_and_concurrency_are_visible(self):
        for token in ("_engine_notes", "parallel_with", "ran concurrently with", "notes.warnings"):
            assert token in INSPECTOR_JS
        assert ".ui-play__engine-warning" in STYLES

    def test_director_specialists_are_facets_of_the_director_step(self):
        for token in ('kind: "specialist"', '["prose"].concat(specialists)', "record.specialists", "delegated.has(channel)", "granted and left empty", "gated out this beat", "specialist_repairs", "merged diff", "DID NOT RUN"):
            assert token in INSPECTOR_JS


class TestConcurrencyMetadata:
    def test_the_runtime_stamps_the_group_on_every_start_event(self):
        from agents import runtime
        src = inspect.getsource(runtime._run_parallel_group)
        assert '"group": members' in src
        assert "parallel_with=" in src

    def test_all_three_pairings_go_through_the_one_helper(self):
        from agents import runtime
        src = inspect.getsource(runtime._run_pipeline)
        assert src.count("_run_parallel_group(") == 3
        assert "_stream_parallel(bus, jobs, holders)" not in src
