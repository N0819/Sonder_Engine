"""The extension system: discovery, plan splicing, execution, and persistence.

The prototype's whole claim is that a third party can add a pipeline stage, keep
per-story state, and put a panel on the page WITHOUT editing any of the files
`agents/README.md`'s add-a-stage checklist names. These tests pin the two halves
that make that true: the plan splice (the piece `register_step` deliberately
punted on) and the namespacing that lets extension state ride checkpoints,
archives and branches with no schema change.

They also pin the containment posture, because it is the part that regresses
quietly: one malformed extension must cost the host that extension and nothing
else -- unlike `language_runtime`, where a single bad pack directory raises out
of every language read (`language_runtime/__init__.py:263-268`).
"""

from __future__ import annotations

import json
import time

import pytest

import extension_runtime
from extension_runtime import ExtensionError


REAL_ROOT = str(extension_runtime.DEFAULT_ROOT)
DEMO = "cohesion-demo"


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def ext_root(monkeypatch, tmp_path):
    """Point discovery at a scratch tree and hand back its path."""
    root = tmp_path / "extensions"
    root.mkdir()
    monkeypatch.setenv(extension_runtime.ROOT_ENV, str(root))
    monkeypatch.delenv(extension_runtime.SAFE_MODE_ENV, raising=False)
    extension_runtime.reload()
    yield root
    extension_runtime.reload()


@pytest.fixture
def real_ext_root(monkeypatch):
    """Discovery over the shipped `extensions/` directory."""
    monkeypatch.setenv(extension_runtime.ROOT_ENV, REAL_ROOT)
    monkeypatch.delenv(extension_runtime.SAFE_MODE_ENV, raising=False)
    extension_runtime.reload()
    yield REAL_ROOT
    extension_runtime.reload()


def _write_extension(root, ext_id, manifest, files=None):
    directory = root / ext_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(
        manifest if isinstance(manifest, str) else json.dumps(manifest),
        encoding="utf-8")
    for name, body in (files or {}).items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return directory


def _enable(*ext_ids):
    from db import set_setting
    extension_runtime.installed_extensions(refresh=True)
    set_setting(extension_runtime.ENABLED_SETTING, json.dumps(list(ext_ids)))
    extension_runtime.activate(refresh=True)


def _chat(db, name="Extensions"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _turn(db, chat_id, idx=1):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "do something", time.time()))


def _character(db, chat_id, name, uid, state="{}"):
    from character_schema import default_character_data

    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time(), uid))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (chat_id, char_id, "active", state))
    return char_id


class _StubTurn:
    def __init__(self, turn_id, idx, frame_id=None):
        self.id = turn_id
        self.idx = idx
        self.frame_id = frame_id


class _StubChat:
    def __init__(self, chat_id):
        self.id = chat_id


class _StubCtx:
    """A stand-in context of exactly the shape `compute_step` tolerates."""

    def __init__(self, chat_id=1, turn_id=1, idx=3, values=None):
        self.chat = _StubChat(chat_id)
        self.turn = _StubTurn(turn_id, idx)
        self._values = dict(values or {})
        self.warnings = []

    def get(self, key, default=None):
        return self._values.get(key, default)

    def __setitem__(self, key, value):
        # `PipelineContext` puts an unknown key in `_extra`; the routing note
        # writes through exactly that door, so the stub has to have one.
        self._values[key] = value

    def add_warning(self, message):
        self.warnings.append(message)


# ---------------------------------------------------------------- discovery


class TestDiscovery:
    def test_one_malformed_extension_never_hides_a_good_one(self, ext_root):
        _write_extension(ext_root, "good-one", {
            "id": "good-one", "version": "1.0.0", "ext_api": 1,
            "name": "Good", "capabilities": {},
        })
        _write_extension(ext_root, "broken-one", "{ not json")
        _write_extension(ext_root, "mislabelled", {
            "id": "something-else", "version": "1.0", "ext_api": 1})

        installed = extension_runtime.installed_extensions(refresh=True)
        errors = {item["dir"]: item["error"]
                  for item in extension_runtime.load_errors()}

        assert set(installed) == {"good-one"}
        assert set(errors) == {"broken-one", "mislabelled"}
        assert "does not match id" in errors["mislabelled"]

    def test_unknown_manifest_keys_and_capabilities_are_tolerated(self, ext_root):
        _write_extension(ext_root, "forward-compat", {
            "id": "forward-compat", "version": "2.11.4", "ext_api": 1,
            "future_field": {"anything": True},
            "provenance": {"author": "somebody", "url": "https://example.invalid"},
            "capabilities": {"chat_state": True, "telepathy": ["nope"]},
        })
        ext = extension_runtime.installed_extensions(refresh=True)["forward-compat"]
        assert ext.version == "2.11.4"
        assert ext.provenance["author"] == "somebody"
        assert ext.trust == "data"

    def test_dot_directories_are_staging_not_extensions(self, ext_root):
        _write_extension(ext_root, ".staging-half-written", "{ not json")
        assert extension_runtime.installed_extensions(refresh=True) == {}
        assert extension_runtime.load_errors() == []

    def test_trust_class_follows_what_the_extension_can_do(self, ext_root):
        _write_extension(ext_root, "data-only", {
            "id": "data-only", "version": "1", "ext_api": 1,
            "capabilities": {"chat_state": True}})
        _write_extension(ext_root, "prompt-only", {
            "id": "prompt-only", "version": "1", "ext_api": 1,
            "prompts": {"narrator": "..."}})
        _write_extension(ext_root, "code-one", {
            "id": "code-one", "version": "1", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            files={"extension.py": "def register(api):\n    pass\n"})
        installed = extension_runtime.installed_extensions(refresh=True)
        assert installed["data-only"].trust == "data"
        assert installed["prompt-only"].trust == "prompt"
        assert installed["code-one"].trust == "code"

    def test_bad_ext_api_and_bad_version_are_refused(self, ext_root):
        _write_extension(ext_root, "old-api", {
            "id": "old-api", "version": "1.0", "ext_api": 0})
        _write_extension(ext_root, "no-version", {
            "id": "no-version", "version": "beta", "ext_api": 1})
        assert extension_runtime.installed_extensions(refresh=True) == {}
        errors = {item["dir"]: item["error"]
                  for item in extension_runtime.load_errors()}
        assert "ext_api" in errors["old-api"]
        assert "version" in errors["no-version"]

    def test_safe_mode_empties_the_enabled_set(self, temp_db, real_ext_root,
                                               monkeypatch):
        _enable(DEMO)
        assert extension_runtime.enabled_ids() == [DEMO]

        monkeypatch.setenv(extension_runtime.SAFE_MODE_ENV, "1")
        assert extension_runtime.safe_mode() is True
        assert extension_runtime.enabled_ids() == []
        assert extension_runtime.ui_bundle() == ""
        extension_runtime.activate(refresh=True)
        assert extension_runtime.registered_stages() == []

    def test_a_python_entry_that_raises_disables_only_itself(self, temp_db,
                                                             ext_root):
        _write_extension(ext_root, "explodes", {
            "id": "explodes", "version": "1", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            files={"extension.py": "raise RuntimeError('boom')\n"})
        _write_extension(ext_root, "fine", {
            "id": "fine", "version": "1", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            files={"extension.py":
                   "def register(api):\n"
                   "    api.add_stage('note', anchor='after:narrator',\n"
                   "                  handler=lambda v, a, n: {'ok': True})\n"})
        _enable("explodes", "fine")

        assert "boom" in extension_runtime.disabled_reasons()["explodes"]
        assert [stage["full_key"]
                for stage in extension_runtime.registered_stages()] == [
                    "ext:fine:note"]

    def test_a_manifest_may_not_name_a_python_module_path(self, ext_root):
        _write_extension(ext_root, "escapee", {
            "id": "escapee", "version": "1", "ext_api": 1,
            "capabilities": {"python": "../../db.py"}})
        errors = {item["dir"]: item["error"]
                  for item in extension_runtime.load_errors(refresh=True)}
        assert "inside its own directory" in errors["escapee"]


# ---------------------------------------------------------------- the splice


class TestPlanSplice:
    def test_enabled_extension_lands_immediately_after_its_anchor(
            self, temp_db, real_ext_root):
        from agents.runtime import build_plan

        _enable(DEMO)
        keys = [key for key, _ in build_plan({}, [], chat_id=_chat(temp_db))]

        assert f"ext:{DEMO}:pulse" in keys
        assert keys[keys.index("director_resolve") + 1] == f"ext:{DEMO}:pulse"
        assert keys[-1] == "commit"

    def test_the_plan_is_identical_when_recomputed(self, temp_db, real_ext_root):
        # Resume and every rerun-from-stage path rebuild the plan from stored
        # step content; a splice that varied between the run and the recompute
        # would make `resume_key_for_turn` point at the wrong stage.
        from agents.runtime import build_plan

        _enable(DEMO)
        chat_id = _chat(temp_db)
        assert build_plan({}, [], chat_id=chat_id) == build_plan(
            {}, [], chat_id=chat_id)

    def test_a_disabled_extension_is_absent_from_the_plan(self, temp_db,
                                                          real_ext_root):
        from agents.runtime import build_plan

        _enable(DEMO)
        extension_runtime.disable_extension(DEMO)
        keys = [key for key, _ in build_plan({}, [], chat_id=_chat(temp_db))]
        assert not any(key.startswith("ext:") for key in keys)

    def test_labels_ride_the_splice(self, temp_db, real_ext_root):
        from agents.runtime import build_plan

        _enable(DEMO)
        plan = dict(build_plan({}, [], chat_id=_chat(temp_db)))
        assert plan[f"ext:{DEMO}:pulse"] == "Cohesion · pulse"

    def test_an_anchor_no_turn_runs_is_skipped_silently(self, temp_db, ext_root):
        from agents.runtime import build_plan

        _write_extension(ext_root, "nowhere", {
            "id": "nowhere", "version": "1", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            files={"extension.py":
                   "def register(api):\n"
                   "    api.add_stage('a', anchor='after:no_such_step',\n"
                   "                  handler=lambda v, x, n: {})\n"
                   "    api.add_stage('b', anchor='sideways:narrator',\n"
                   "                  handler=lambda v, x, n: {})\n"})
        _enable("nowhere")
        keys = [key for key, _ in build_plan({}, [], chat_id=_chat(temp_db))]
        assert not any(key.startswith("ext:") for key in keys)

    def test_two_extensions_at_one_anchor_order_by_id(self, temp_db, ext_root):
        from agents.runtime import build_plan

        body = ("def register(api):\n"
                "    api.add_stage('s', anchor='after:narrator',\n"
                "                  handler=lambda v, x, n: {})\n")
        for ext_id in ("zeta-ext", "alpha-ext"):
            _write_extension(ext_root, ext_id, {
                "id": ext_id, "version": "1", "ext_api": 1,
                "capabilities": {"python": "extension.py"}},
                files={"extension.py": body})
        _enable("zeta-ext", "alpha-ext")

        keys = [key for key, _ in build_plan({}, [], chat_id=_chat(temp_db))]
        start = keys.index("narrator")
        assert keys[start + 1:start + 3] == ["ext:alpha-ext:s", "ext:zeta-ext:s"]

    def test_a_broken_splice_registry_leaves_the_plan_untouched(
            self, temp_db, real_ext_root, monkeypatch):
        from agents.runtime import build_plan

        _enable(DEMO)
        monkeypatch.setattr(extension_runtime, "registered_stages",
                            lambda: (_ for _ in ()).throw(RuntimeError("nope")))
        keys = [key for key, _ in build_plan({}, [], chat_id=_chat(temp_db))]
        assert not any(key.startswith("ext:") for key in keys)
        assert "director_resolve" in keys


# ---------------------------------------------------------------- execution


class TestStageExecution:
    def test_the_demo_stage_runs_through_compute_step(self, temp_db,
                                                      real_ext_root):
        from agents.runtime import compute_step

        _enable(DEMO)
        ctx = _StubCtx(values={"director_resolve": {
            "dialogue_log": [{"speaker": "A", "line": "hello"}],
            "state_diff": {"conditions": [{"who": "A", "state": "bruised"}]},
        }})
        out = compute_step(f"ext:{DEMO}:pulse", ctx, 0)

        assert isinstance(out, dict)
        # +1 for dialogue, -1 for the one condition entry.
        assert out["cohesion_delta"] == 0
        assert len(out["evidence"]) == 2

    def test_a_stage_never_sees_the_pipeline_context(self, temp_db,
                                                     real_ext_root):
        from agents.runtime import compute_step

        _enable(DEMO)
        seen = {}

        def spy(view, api, nonce):
            seen["view"] = view
            return {"ok": True}

        api = extension_runtime._apis[DEMO]
        api.add_stage("spy", anchor="after:narrator", handler=spy)
        ctx = _StubCtx()
        compute_step(f"ext:{DEMO}:spy", ctx, 0)

        view = seen["view"]
        assert view is not ctx
        assert view.chat_id == 1 and view.turn_idx == 3
        assert not hasattr(view, "cast")
        assert not hasattr(view, "character_results")

    def test_on_error_warn_materializes_the_failure_as_content(
            self, temp_db, ext_root):
        from agents.runtime import compute_step

        _write_extension(ext_root, "flaky", {
            "id": "flaky", "version": "1", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            files={"extension.py":
                   "def boom(view, api, nonce):\n"
                   "    raise ValueError('the model ate it')\n"
                   "def register(api):\n"
                   "    api.add_stage('boom', anchor='after:narrator',\n"
                   "                  handler=boom, on_error='warn')\n"})
        _enable("flaky")
        ctx = _StubCtx()
        out = compute_step("ext:flaky:boom", ctx, 0)

        # A dict, because `_assert_plan_materialized` needs exactly one active
        # variant per planned key -- a stage that returned nothing would fail
        # the whole turn's materialization check instead of one extension.
        assert out == {"error": "the model ate it"}
        assert any("flaky" in warning for warning in ctx.warnings)

    def test_on_error_fail_propagates(self, temp_db, ext_root):
        from agents.runtime import compute_step

        _write_extension(ext_root, "strict", {
            "id": "strict", "version": "1", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            files={"extension.py":
                   "def boom(view, api, nonce):\n"
                   "    raise ValueError('deliberate')\n"
                   "def register(api):\n"
                   "    api.add_stage('boom', anchor='after:narrator',\n"
                   "                  handler=boom, on_error='fail')\n"})
        _enable("strict")
        with pytest.raises(ValueError):
            compute_step("ext:strict:boom", _StubCtx(), 0)

    def test_step_observers_are_contained_individually(self, temp_db,
                                                       real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        seen = []
        api.on_step("character:*", lambda key, content: seen.append(key))
        api.on_step("*", lambda key, content: 1 / 0)

        ctx = _StubCtx()
        extension_runtime.notify_step_saved(ctx, "character:7", {"x": 1})
        extension_runtime.notify_step_saved(ctx, "narrator", {"prose": "hi"})

        assert seen == ["character:7"]
        assert extension_runtime.observer_failures()[DEMO] == 2


class TestStepPersistence:
    def test_an_extension_step_saves_like_any_other(self, temp_db,
                                                    real_ext_root):
        # The full stubbed-turn path is exercised by
        # tests/test_branching_integrity.py; here the point is narrower and
        # does not need it -- an ext: key is an ordinary steps/variants row, so
        # reroll, one-active-variant, staleness and the pipeline drawer come
        # for free without a line of extension-specific persistence code.
        from agents.storage import active_content, save_step, variant_count

        _enable(DEMO)
        chat_id = _chat(temp_db)
        turn_id = _turn(temp_db, chat_id)
        key = f"ext:{DEMO}:pulse"
        save_step(turn_id, key, "Cohesion · pulse", 5, {"cohesion_delta": 2})
        save_step(turn_id, key, "Cohesion · pulse", 5, {"cohesion_delta": -1})

        assert variant_count(turn_id, key) == 2
        assert active_content(turn_id, key) == {"cohesion_delta": -1}
        row = temp_db.q("SELECT COUNT(*) c FROM steps s JOIN variants v "
                        "ON v.step_id=s.id AND v.active=1 WHERE s.key=?",
                        (key,), one=True)
        assert row["c"] == 1


# ---------------------------------------------------------------- state


class TestStateRidesTheEngine:
    def test_the_write_gate_names_its_escape_hatch(self, temp_db,
                                                   real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        state = api.state(chat_id)

        with pytest.raises(ExtensionError) as caught:
            state.set({"cohesion": 60})
        assert "set_now" in str(caught.value)

        state.set_now({"cohesion": 60})
        assert state.get()["cohesion"] == 60

    def test_a_committed_turn_hook_may_write(self, temp_db, real_ext_root):
        _enable(DEMO)
        chat_id = _chat(temp_db)
        turn_id = _turn(temp_db, chat_id, idx=4)
        ctx = _StubCtx(chat_id=chat_id, turn_id=turn_id, idx=4, values={
            f"ext:{DEMO}:pulse": {"cohesion_delta": 3, "evidence": []}})

        report = extension_runtime.dispatch_turn_committed(ctx)

        assert report["errors"] == {}
        assert DEMO in report["ran"]
        from db import wget
        assert wget(chat_id, f"ext:{DEMO}") == {
            "cohesion": 53.0,
            "last_turn": 4,
            # Bounded on purpose: world KV is copied wholesale into every
            # checkpoint, branch and archive, so an unbounded log here would
            # grow all three forever.
            "history": [{"turn": 4, "delta": 3, "cohesion": 53.0}],
        }

    def test_the_gate_closes_again_after_dispatch(self, temp_db, real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        extension_runtime.dispatch_turn_committed(
            _StubCtx(chat_id=chat_id, turn_id=_turn(temp_db, chat_id)))
        assert extension_runtime.in_commit_scope() is False
        with pytest.raises(ExtensionError):
            api.state(chat_id).set({"cohesion": 1})

    def test_a_failing_hook_is_reported_not_raised(self, temp_db, ext_root):
        _write_extension(ext_root, "bad-hook", {
            "id": "bad-hook", "version": "1", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            files={"extension.py":
                   "def register(api):\n"
                   "    api.on_turn_committed(lambda turn: 1 / 0)\n"})
        _enable("bad-hook")
        chat_id = _chat(temp_db)
        report = extension_runtime.dispatch_turn_committed(
            _StubCtx(chat_id=chat_id, turn_id=_turn(temp_db, chat_id)))
        assert "bad-hook" in report["errors"]

    def test_settings_state_is_install_scoped_and_ungated(self, temp_db,
                                                          real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        api.settings.set({"threshold": 12})
        assert api.settings.get() == {"threshold": 12}

    def test_extension_state_rides_export_and_import(self, temp_db,
                                                     real_ext_root):
        import app
        from checkpoints import ensure_checkpoint
        from db import wget, wset

        _enable(DEMO)
        chat_id = _chat(temp_db, "Rides")
        wset(chat_id, f"ext:{DEMO}", {"cohesion": 71})
        ensure_checkpoint(chat_id, 0)

        imported = app.chat_import({"data": app.chat_export(chat_id)})
        assert wget(imported["id"], f"ext:{DEMO}") == {"cohesion": 71}

    def test_extension_state_rides_a_checkpoint_restore(self, temp_db,
                                                        real_ext_root):
        from checkpoints import ensure_checkpoint, restore_checkpoint
        from db import wget, wset

        _enable(DEMO)
        chat_id = _chat(temp_db, "Rewind")
        wset(chat_id, f"ext:{DEMO}", {"cohesion": 40})
        ensure_checkpoint(chat_id, 3)
        wset(chat_id, f"ext:{DEMO}", {"cohesion": 99})

        restore_checkpoint(chat_id, 3)
        assert wget(chat_id, f"ext:{DEMO}") == {"cohesion": 40}

    # A branch clone goes through the same `world` rows this covers
    # (app.py's branch helper copies the table wholesale, and `ext:<id>` is
    # not frame-scoped so there is no id to remap); left uncovered here
    # because the branch route needs a fully-populated chat to call.


class TestCharacterTargeting:
    def test_char_state_round_trips_without_clobbering_engine_keys(
            self, temp_db, real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        engine_state = {
            "active_state": {"mood": "wary", "goal": "get out"},
            "interior": {"beliefs": [{"claim": "the door is locked"}]},
            "visited_rooms": ["hall", "stair"],
        }
        char_id = _character(temp_db, chat_id, "Ash", "ext_ash",
                             state=json.dumps(engine_state))

        api.char_state(chat_id, char_id).set_now({"seen": 3})

        stored = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, char_id), one=True)["state"])
        assert stored["active_state"] == engine_state["active_state"]
        assert stored["interior"] == engine_state["interior"]
        assert stored["visited_rooms"] == engine_state["visited_rooms"]
        assert stored[f"ext:{DEMO}"] == {"seen": 3}
        assert api.char_state(chat_id, char_id).get() == {"seen": 3}

    def test_psychology_reads_what_commit_actually_wrote(self, temp_db,
                                                         real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        char_id = _character(temp_db, chat_id, "Bell", "ext_bell", state=json.dumps({
            "active_state": {"mood": "tense", "stress": {"level": 0.4}},
            "interior": {"projects": [{"name": "get home"}]},
            "recent_tells": ["a hand at the collar"],
            "visited_rooms": ["hall"],
        }))
        handle = api.characters.get(chat_id, char_id)

        psychology = handle.psychology()
        assert set(psychology) == {"active_state", "interior", "recent_tells"}
        assert psychology["active_state"]["stress"] == {"level": 0.4}
        assert "visited_rooms" not in psychology

    def test_psychology_of_a_fresh_character_is_empty_not_invented(
            self, temp_db, real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        char_id = _character(temp_db, chat_id, "Cyn", "ext_cyn")
        assert api.characters.get(chat_id, char_id).psychology() == {}

    def test_an_ambiguous_display_name_raises_with_the_candidates(
            self, temp_db, real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        first = _character(temp_db, chat_id, "Ash", "ext_ash_one")
        second = _character(temp_db, chat_id, "Ash", "ext_ash_two")

        with pytest.raises(ExtensionError) as caught:
            api.characters.get(chat_id, "Ash")
        message = str(caught.value)
        assert "ambiguous" in message
        assert str(first) in message and str(second) in message

        # The unambiguous id still resolves.
        assert api.characters.get(chat_id, second).char_id == second

    def test_an_unknown_name_raises_rather_than_returning_none(
            self, temp_db, real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        _character(temp_db, chat_id, "Ash", "ext_ash_solo")
        with pytest.raises(ExtensionError):
            api.characters.get(chat_id, "Nobody")

    def test_in_chat_lists_every_attached_character(self, temp_db,
                                                    real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        ids = {_character(temp_db, chat_id, "Ash", "ext_a"),
               _character(temp_db, chat_id, "Bell", "ext_b")}
        assert {handle.char_id for handle in api.characters.in_chat(chat_id)} == ids

    def test_step_output_reads_the_active_character_variant(self, temp_db,
                                                            real_ext_root):
        from agents.storage import save_step

        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        char_id = _character(temp_db, chat_id, "Ash", "ext_step")
        first = _turn(temp_db, chat_id, idx=1)
        second = _turn(temp_db, chat_id, idx=2)
        save_step(first, f"character:{char_id}", "Ash", 3, {"say": "one"})
        save_step(second, f"character:{char_id}", "Ash", 3, {"say": "two"})

        handle = api.characters.get(chat_id, char_id)
        assert handle.step_output() == {"say": "two"}
        assert handle.step_output(turn_idx=1) == {"say": "one"}
        assert handle.step_output(turn_idx=99) is None

    def test_request_bind_and_binding_round_trip(self, temp_db, real_ext_root):
        _enable(DEMO)
        api = extension_runtime._apis[DEMO]
        chat_id = _chat(temp_db)
        char_id = _character(temp_db, chat_id, "Ash", "ext_bind")
        handle = api.characters.get(chat_id, char_id)

        assert handle.binding() is None
        handle.request_bind({"role": "observer"})
        assert handle.binding() == {"role": "observer"}


# ---------------------------------------------------------------- host surface


class TestHostSurface:
    def test_asset_paths_cannot_escape_the_extension_directory(
            self, real_ext_root):
        assert extension_runtime.asset_path(DEMO, "manifest.json").is_file()
        for bad in ("../../db.py", "/etc/passwd", "", "ui/../../../db.py"):
            with pytest.raises(ExtensionError):
                extension_runtime.asset_path(DEMO, bad)

    def test_ui_bundle_wraps_each_enabled_extension(self, temp_db, ext_root):
        _write_extension(ext_root, "painter", {
            "id": "painter", "version": "1", "ext_api": 1,
            "capabilities": {"ui": {"js": "ui/panel.js"}}},
            files={"ui/panel.js": "Sonder.registerTab('x');\n"})
        _enable("painter")

        bundle = extension_runtime.ui_bundle()
        assert 'Sonder._begin("painter")' in bundle
        assert "Sonder.registerTab('x');" in bundle
        assert "Sonder._end();" in bundle
        assert "//# sourceURL=/api/extensions/painter/asset/ui/panel.js" in bundle

    def test_ui_bundle_is_empty_when_nothing_is_enabled(self, temp_db,
                                                        ext_root):
        assert extension_runtime.ui_bundle() == ""

    def test_a_missing_ui_file_costs_that_extension_only(self, temp_db,
                                                         ext_root):
        _write_extension(ext_root, "ghost", {
            "id": "ghost", "version": "1", "ext_api": 1,
            "capabilities": {"ui": {"js": "ui/panel.js"}}})
        _write_extension(ext_root, "real", {
            "id": "real", "version": "1", "ext_api": 1,
            "capabilities": {"ui": {"js": "ui/panel.js"}}},
            files={"ui/panel.js": "// here\n"})
        _enable("ghost", "real")

        bundle = extension_runtime.ui_bundle()
        assert 'Sonder._begin("real")' in bundle
        assert 'Sonder._begin("ghost")' not in bundle

    def test_listing_reports_enablement_and_trust(self, temp_db,
                                                  real_ext_root):
        rows = {row["id"]: row for row in extension_runtime.listing()}
        assert rows[DEMO]["enabled"] is False
        assert rows[DEMO]["trust"] == "code"

        extension_runtime.enable_extension(DEMO)
        rows = {row["id"]: row for row in extension_runtime.listing()}
        assert rows[DEMO]["enabled"] is True
        assert rows[DEMO]["error"] is None

    def test_enable_refuses_an_extension_that_is_not_installed(
            self, temp_db, real_ext_root):
        with pytest.raises(ExtensionError):
            extension_runtime.enable_extension("no-such-extension")

    def test_bootstrap_carries_extensions_and_their_errors(self, temp_db,
                                                           ext_root):
        import app

        _write_extension(ext_root, "listed", {
            "id": "listed", "version": "1", "ext_api": 1})
        _write_extension(ext_root, "broken", "{{{")
        payload = app.bootstrap()

        assert [row["id"] for row in payload["extensions"]] == ["listed"]
        assert payload["extension_errors"][0]["dir"] == "broken"

    def test_the_routes_exist_and_are_host_gated(self):
        import app

        paths = {route.path for route in app.app.routes}
        assert {"/api/extensions",
                "/api/extensions/{eid}/enable",
                "/api/extensions/{eid}/disable",
                "/api/extensions/{eid}/state",
                "/api/extensions/ui.js",
                "/api/extensions/{eid}/asset/{path:path}"} <= paths
        # Never in the guest allowlist: extension code is host-session only.
        assert not any(str(path).startswith("/api/extensions")
                       for path in app.GUEST_ALLOWED_API_PATHS)
