"""The living world's paid off-screen tiers were retired, not left switched off.

The owner, 2026-11-01: "living world is supposed to be superseded by charter
and writers room." The stochastic, profile, agent and reactive tiers of
`world/offscreen.py`, the approach ladder of `world/living_world.py` and the
`offscreen_life` ladder of `story/scene.py` had been unreachable since
7140b9cc (2026-09-20) -- `LIVING_WORLD_APPROACHES = ()` refused every
approach and `dialogue_config` forced `max_offscreen_actors` to 0 -- and the
owner's db never stored a batch from any of them (review 2026-11-01,
world_offscreen_time F11, registered as UNBUILT_LIVING_WORLD §1.256 until this
retirement landed it). Unreachable code kept
costing: every beat read two config rows for gates that could not pass, and
four authority documents went on describing the rungs as live.

What superseded them stays and is not tested here: the Charter
(`world/charter_*.py`), the Writers' Room, causality bubbles and their
off-screen beats (`agents/offscreen_beat.py`), and the off-screen EPOCH whose
beat identity the Charter advances on (`world.offscreen.advance_epoch`).

Two things are pinned. No engine module binds a retired name again -- a
second copy of the ladder is how the first one stayed half-alive for six
weeks. And the published extension contract keeps its shape while `ext_api`
stays 1: `provision_story(offscreen_life=..., living_world=...)` still accepts
what it accepted, provisions nothing for it, and says so.
"""

from __future__ import annotations

import ast
import importlib
import json
import pathlib
import warnings

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _enable, _write_extension, ext_root, real_ext_root,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The engine's own source, as `tools/project_check.py` enumerates it.
ENGINE_DIRS = ("agents", "core", "llm", "mind", "persist", "story", "web",
               "world", "dressing", "extension_runtime", "language_runtime",
               "language_adapters")

#: Every name the retirement deleted, by the module that used to bind it.
RETIRED = {
    "world.offscreen": (
        # the importance x distance spend axes
        "IMPORTANCE_LEVELS", "DISTANCES", "SAME_REGION_HOPS", "RESOLUTIONS",
        "OVERRIDE_FIELD", "derived_importance", "importance_for",
        "_non_wall_hops", "_intention_mentions", "_intention_owned_by",
        "subject_distance", "resolution_for",
        # the stochastic rung and its log door
        "TICK_CHANCE", "_IDLE_TICKS", "stochastic_ticks",
        "append_offscreen_log", "_adjudicated_event_ids",
        # the reactive rung (the antagonist ladder's plans)
        "PLAN_KEY", "PLAN_CAP", "PLAN_OPS_PER_BEAT", "PLAN_HISTORY_CAP",
        "PLAN_STAGE_CAP", "REACTIVE_FIRE_CAP", "PLAN_TRIGGER_MIN_SECONDS",
        "PLAN_TRIGGER_MAX_SECONDS", "PLAN_EVENT_KINDS", "_plan_slug",
        "_plan_words", "_declared_plan_actors", "_basis_is_grounded",
        "_normalize_plan_stages", "_TERMINAL_PLAN_STATUSES", "_truncate_plans",
        "apply_plan_ops", "_reactive_triggered", "_reactive_due_crossed",
        "advance_reactive_plans",
        # the profile rung
        "DOING_MAX_WORDS", "MANNER_MAX_WORDS", "compose_tick",
        "_profile_surface", "_ProfileFallback", "profile_summary_record",
        "dormant_subjects", "_subject_importance", "_has_memories",
        "profile_candidates", "schedule_profile_ticks", "land_profile_ticks",
        # the character_agent rung
        "full_agent_candidates", "AGENT_CONTEXT_KEYS", "agent_context",
        "_plans_for", "AGENT_RUNG", "AGENT_ATTEMPT_MAX_WORDS",
        "AGENT_OUTCOMES", "AGENT_MEMORY_SALIENCE", "_AGENT_OUTCOME_PHRASES",
        "agent_proposal", "agent_adjudication",
        "compose_agent_tick", "compose_agent_memory", "land_agent_tick",
        "schedule_agent_ticks",
    ),
    "world.living_world": (
        "LIVING_WORLD_DEPTHS", "LIVING_WORLD_APPROACHES", "LIVING_WORLD_BUILT",
        "LIVING_WORLD_DESCRIPTIONS", "LIVING_WORLD_REQUIRES",
        "LIVING_WORLD_DEFAULT", "LIVING_WORLD_KEY", "OFFSCREEN_CEILING_KEY",
        "normalize_living_world", "living_world_config", "effective_depth",
        "living_world_allows", "living_world_levels",
    ),
    "story.scene": (
        "OFFSCREEN_LIFE_LADDER", "OFFSCREEN_LIFE_DEFAULT",
        "OFFSCREEN_LIFE_DESCRIPTIONS", "OFFSCREEN_LIFE_BUILT",
        "COGNITION_OFF_RUNG", "COGNITION_ON_RUNG",
        "OFFSCREEN_COGNITION_DEFAULT", "normalize_offscreen_cognition",
        "cognition_rung", "cognition_from_rung", "normalize_offscreen_life",
        "offscreen_life_allows",
    ),
    "story.character_schema": ("character_offscreen_agent",),
    "persist.commit": ("commit_offscreen_plans",),
}

#: What `world/offscreen.py` keeps: the epoch and the beat identity the
#: Charter advances on, and nothing that spends.
OFFSCREEN_PUBLIC = {"EPOCH_SECONDS", "EPOCH_KEY", "epoch_reasons",
                    "advance_epoch"}

ALL_RETIRED = frozenset(name for names in RETIRED.values() for name in names)


def _engine_files():
    for top in ENGINE_DIRS:
        for path in sorted((ROOT / top).rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


def _bindings(tree):
    """(line, name) for every name a module defines, assigns or imports,
    and every attribute it reads off something else."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            yield node.lineno, node.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield node.lineno, target.id
        elif isinstance(node, ast.AnnAssign) \
                and isinstance(node.target, ast.Name):
            yield node.lineno, node.target.id
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                yield node.lineno, alias.name
                if alias.asname:
                    yield node.lineno, alias.asname
        elif isinstance(node, ast.Attribute):
            yield node.lineno, node.attr


class TestTheRetiredNamesStayGone:
    @pytest.mark.parametrize("module", sorted(RETIRED))
    def test_the_module_that_held_them_no_longer_does(self, module):
        loaded = importlib.import_module(module)
        still = [name for name in RETIRED[module] if hasattr(loaded, name)]
        assert still == [], f"{module} still binds {still}"

    def test_no_engine_module_binds_one_again(self):
        """Defined, assigned, imported or read as an attribute, anywhere in
        the engine's own source -- a second copy of a retired gate is how
        the first one stayed half-alive."""
        found = []
        for path in _engine_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(ROOT).as_posix()
            found.extend(f"{rel}:{line} {name}"
                         for line, name in _bindings(tree)
                         if name in ALL_RETIRED)
        assert found == [], found

    def test_the_off_screen_module_is_the_epoch_and_nothing_else(self):
        from world import offscreen

        public = {name for name, value in vars(offscreen).items()
                  if not name.startswith("_")
                  and getattr(value, "__module__", offscreen.__name__)
                  == offscreen.__name__
                  and not isinstance(value, type(offscreen))}
        public -= {"annotations"}      # `from __future__ import annotations`
        assert public == OFFSCREEN_PUBLIC, sorted(public ^ OFFSCREEN_PUBLIC)

    def test_no_pack_ships_a_prompt_for_a_retired_tier(self):
        from language_runtime import installed_language_packs

        for language, pack in installed_language_packs().items():
            prompts = pack.card("system_prompts")["prompts"]
            assert not [pid for pid in prompts
                        if pid.startswith("offscreen_")], language

    def test_no_route_serves_the_retired_ladder(self):
        from web import app

        assert not hasattr(app, "living_world_get")
        assert not hasattr(app, "living_world_put")
        paths = {getattr(route, "path", "") for route in app.app.routes}
        assert "/api/chats/{cid}/living_world" not in paths


# -- the extension contract ---------------------------------------------------


@pytest.fixture
def campaign(ext_root):
    _write_extension(ext_root, "directive", {
        "id": "directive", "version": "1.0.0", "ext_api": 1,
        "name": "Directive",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("directive")
    return extension_runtime._apis["directive"]


def _package(name="Episode One"):
    return {
        "version": 1,
        "chat": {"name": name, "scenario": "A ship under tow."},
        "world": {"scene": {
            "location": "the bridge", "time": "0400",
            "rooms": {"bridge": {"name": "Bridge"}},
            "positions": {}, "entities": {},
        }},
        "resources": {"persona": {"sheet": {"name": "Commander"}}},
    }


class TestTheProvisioningContractKeepsItsShape:
    """`ext_api` stays 1, so a call written against the old guide must not
    start raising -- the owner bumps the version, a cleanup never does. Its
    own example (`EXTENSIONS.md`, "A world that runs while nobody is
    looking") was REFUSED from 2026-09-20 until this retirement, because the
    approach list it validated against was empty."""

    def test_the_guides_own_call_provisions_and_says_what_it_ignored(
            self, temp_db, campaign):
        from core.db import wget

        with pytest.warns(DeprecationWarning, match="retired"):
            result = campaign.provision_story(
                _package(), state={"mission": "survey"},
                offscreen_life="deterministic",
                living_world={"routine_residue": "floor",
                              "place_obligations": "floor"})

        cid = result["chat_id"]
        assert campaign.state(cid).get() == {"mission": "survey"}
        notes = " ".join(result["deprecations"])
        assert "offscreen_life" in notes and "living_world" in notes
        # Provisions NOTHING for either argument.
        assert wget(cid, "living_world", None) is None
        assert "offscreen_life" not in (
            wget(cid, "dialogue_config", None) or {})

    @pytest.mark.parametrize("approach", [
        "routine_residue", "scheduled_consequence", "place_obligations",
        "antagonist_ladder"])
    @pytest.mark.parametrize("depth", ["off", "floor", "ceiling"])
    def test_every_retired_approach_and_depth_is_still_accepted(
            self, temp_db, campaign, approach, depth):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = campaign.provision_story(
                _package(), living_world={approach: depth})
        assert result["deprecations"]

    @pytest.mark.parametrize("kwargs", [
        {"living_world": {"rumour_mill": "floor"}},
        {"living_world": {"routine_residue": "warp speed"}},
        {"living_world": ["routine_residue"]},
        {"offscreen_life": "warp speed"},
    ])
    def test_what_was_never_valid_is_still_refused_before_anything_is_made(
            self, temp_db, campaign, kwargs):
        from core.db import q

        before = q("SELECT COUNT(*) AS n FROM chats", one=True)["n"]
        with pytest.raises(ExtensionError):
            campaign.provision_story(_package(), **kwargs)
        assert q("SELECT COUNT(*) AS n FROM chats", one=True)["n"] == before

    def test_a_call_that_names_neither_carries_no_deprecation(
            self, temp_db, campaign):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            result = campaign.provision_story(_package())
        assert result.get("deprecations", []) == []

    def test_the_capability_that_promised_it_has_left(self):
        from extension_runtime.api import HOST_CAPABILITIES

        assert "living_world_provisioning" not in HOST_CAPABILITIES
        # The generation half was never the ladder's and stays.
        assert "living_world_generation" in HOST_CAPABILITIES

    def test_story_view_reports_the_dial_that_runs_not_the_ladder(
            self, temp_db, campaign):
        cid = campaign.provision_story(_package())["chat_id"]
        from core.db import wset

        wset(cid, "dialogue_config", {"max_bubbles": 5})
        slice_ = campaign.story_view(cid)["living_world"]
        for gone in ("living_world", "offscreen_life", "max_offscreen_actors",
                     "approaches"):
            assert gone not in slice_, gone
        assert slice_["max_bubbles"] == 5
        assert json.loads(json.dumps(slice_)) == slice_
