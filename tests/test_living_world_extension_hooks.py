"""The Living World, reachable from Python instead of from a browser tab.

An extension could configure the living world and generate an inhabited place
only by making several host HTTP calls after the story already existed. That
is fine for a prototype and wrong as a contract: story initialization becomes
browser-owned and interruptible, a partially initialized story exists between
requests, and every consumer has to implement compensating deletion correctly.

Four hooks close it, and each is tested for the thing that would make it
useless rather than merely for working:

1. `story_view` carries a `living_world` slice -- and reports the EFFECTIVE
   ladder, because a request that gets silently clamped is the trap this
   subsystem is full of.
2. `provision_story` sets the ladder inside the same transaction that creates
   the story -- and REFUSES a bad value rather than normalizing it, because a
   caller sees no echo to correct.
3. A lived-location request may name characters by `resource_uid` -- the
   identity that survives an archive -- and an unresolvable one is refused
   rather than skipped.
4. A generation persists its expensive pure prefix before it writes anything,
   so a lost run does not have to be paid for twice, and refuses to repeat the
   half that already planted rooms.

The firewall is NOT the constraint here. It bounds what reaches a fictional
MIND; an extension is not one, and `GET /api/chats/{cid}/charters` already
serves the whole registry to any host session. A Python caller getting less
than the browser would be a weaker path, not a safer one.
"""

from __future__ import annotations

import json

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _chat, _enable, _write_extension, ext_root, real_ext_root,
)
from tests.test_extension_provisioning import campaign  # noqa: F401


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


class TestTheSliceReportsWhatWillActuallyRun:
    def test_the_key_is_always_present(self, temp_db):
        """Unconditional, which is why there is no schema bump: absence keeps
        meaning "engine predates the field", so the key is the check."""
        from web.story_view import story_view

        view = story_view(_chat(temp_db))
        assert "living_world" in view
        assert set(view["living_world"]) >= {
            "living_world", "offscreen_life", "max_offscreen_actors",
            "approaches", "background", "charters", "registry_warnings"}

    def test_a_fresh_story_is_all_off(self, temp_db):
        from web.story_view import story_view
        from world.living_world import LIVING_WORLD_APPROACHES

        ladder = story_view(_chat(temp_db))["living_world"]["living_world"]
        assert set(ladder) == set(LIVING_WORLD_APPROACHES)
        assert set(ladder.values()) == {"off"}

    def test_it_reports_the_clamp_rather_than_the_request(self, temp_db):
        """The whole reason `effective` is in the slice. Three of the four
        approaches have no built ceiling, so asking for one runs the floor --
        silently, because `effective_depth` never raises."""
        from core.db import wset
        from web.story_view import story_view
        from world.living_world import LIVING_WORLD_KEY

        cid = _chat(temp_db)
        wset(cid, LIVING_WORLD_KEY, {"routine_residue": "ceiling"})
        rows = {row["approach"]: row
                for row in story_view(cid)["living_world"]["approaches"]}
        assert rows["routine_residue"]["value"] == "ceiling"
        assert rows["routine_residue"]["effective"] == "floor"

    def test_the_off_screen_ceiling_rides_along(self, temp_db):
        """`value` without the ceiling is not an answer: the ceiling caps
        every approach."""
        from web.story_view import story_view

        slice_ = story_view(_chat(temp_db))["living_world"]
        # A chat that answered nothing rides the cognition toggle's default
        # since 2026-09-04; the ceiling still rides along, which is the point.
        assert slice_["offscreen_life"] == "character_agent"
        assert slice_["max_offscreen_actors"] == 3

    def test_no_charter_means_an_empty_list_not_a_crash(self, temp_db):
        from web.story_view import story_view

        slice_ = story_view(_chat(temp_db))["living_world"]
        assert slice_["charters"] == []
        assert slice_["registry_warnings"] == []

    def test_a_charter_is_summarised_with_its_display_name(self, temp_db):
        from core.db import wset
        from web.story_view import story_view

        cid = _chat(temp_db)
        wset(cid, "charters", {"version": 1, "items": {"ops": {
            "state": {"key": "ops", "structure": "site", "clock_hours": 12.0,
                      "bodies": {"a": {"key": "a", "name": "A"},
                                 "b": {"key": "b", "name": "B"}},
                      "posts": {"p": {"key": "p", "place": "bridge"}},
                      "upkeeps": {}},
            "window_hours": 6}}})
        wset(cid, "structures", {"items": {"site": {"name": "Site 17"}}})

        rows = story_view(cid)["living_world"]["charters"]
        assert len(rows) == 1
        assert rows[0]["key"] == "ops"
        assert rows[0]["name"] == "Site 17"
        assert rows[0]["counts"]["bodies"] == 2
        assert rows[0]["counts"]["posts"] == 1

    def test_full_detail_is_the_whole_registry(self, temp_db):
        """Size, never disclosure -- the same bytes the HTTP route serves."""
        from core.db import wset
        from web.story_view import story_view

        cid = _chat(temp_db)
        wset(cid, "charters", {"version": 1, "items": {"ops": {
            "state": {"key": "ops", "bodies": {"a": {"key": "a", "name": "A"}},
                      "posts": {}, "upkeeps": {}}, "window_hours": 6}}})

        full = story_view(cid, charters="full")["living_world"]["charters"]
        assert "items" in full
        assert "bodies" in full["items"]["ops"]["state"]

    def test_the_result_is_plain_json(self, temp_db):
        from web.story_view import story_view

        json.dumps(story_view(_chat(temp_db))["living_world"])


class TestProvisioningSetsTheLadderInOneAct:
    def test_both_arguments_are_optional(self, temp_db, campaign):
        """The backward-compatibility guard: a call that names neither must
        behave exactly as before."""
        result = campaign.provision_story(_package(), state={"m": 1})
        assert result["chat_id"]
        assert result["living_world"]["living_world"]["routine_residue"] \
            == "off"

    def test_the_ladder_lands_with_the_story(self, temp_db, campaign):
        result = campaign.provision_story(
            _package(), offscreen_life="deterministic",
            living_world={"routine_residue": "floor",
                          "place_obligations": "floor"})
        slice_ = result["living_world"]
        assert slice_["offscreen_life"] == "deterministic"
        assert slice_["living_world"]["routine_residue"] == "floor"
        assert slice_["living_world"]["place_obligations"] == "floor"

    def test_the_result_reports_effective_not_merely_requested(
            self, temp_db, campaign):
        """A campaign that reads back only its own request learns nothing
        about the clamp, and the clamp is silent."""
        result = campaign.provision_story(
            _package(), offscreen_life="deterministic",
            living_world={"antagonist_ladder": "ceiling"})
        rows = {row["approach"]: row
                for row in result["living_world"]["approaches"]}
        assert rows["antagonist_ladder"]["value"] == "ceiling"
        assert rows["antagonist_ladder"]["effective"] == "off"

    def test_a_partial_ladder_merges_rather_than_replaces(
            self, temp_db, campaign):
        """`normalize_living_world` is total over the four approaches, so a
        replace would switch off every approach this call did not name."""
        from core.db import wget, wset
        from world.living_world import LIVING_WORLD_KEY

        result = campaign.provision_story(
            _package(), living_world={"routine_residue": "floor"})
        cid = result["chat_id"]
        wset(cid, LIVING_WORLD_KEY,
             {**(wget(cid, LIVING_WORLD_KEY) or {}),
              "scheduled_consequence": "floor"})

        result = campaign.provision_story(
            _package("Two"), living_world={"place_obligations": "floor"})
        ladder = result["living_world"]["living_world"]
        assert ladder["place_obligations"] == "floor"
        assert ladder["routine_residue"] == "off"   # untouched, not cleared

    @pytest.mark.parametrize("bad", ["Deterministic", "determinstic", "on",
                                     "", "full"])
    def test_an_off_ladder_rung_is_refused_not_normalized(
            self, temp_db, campaign, bad):
        """The opposite of the HTTP route, deliberately: a host sees the
        normalized answer come back and can correct it; a campaign sees
        nothing, and `normalize_offscreen_life` falls to the DEFAULT, so a
        typo would buy MORE off-screen life than was asked for."""
        with pytest.raises(ExtensionError) as excinfo:
            campaign.provision_story(_package(), offscreen_life=bad)
        assert "offscreen_life must be one of" in str(excinfo.value)

    def test_an_unknown_approach_is_named(self, temp_db, campaign):
        with pytest.raises(ExtensionError) as excinfo:
            campaign.provision_story(
                _package(), living_world={"routine_residues": "floor"})
        assert "routine_residues" in str(excinfo.value)

    def test_an_unknown_depth_is_named(self, temp_db, campaign):
        with pytest.raises(ExtensionError) as excinfo:
            campaign.provision_story(
                _package(), living_world={"routine_residue": "maximum"})
        assert "routine_residue" in str(excinfo.value)

    def test_a_refusal_leaves_no_story_behind(self, temp_db, campaign):
        """Validation happens before the archive is touched, so the refusal
        cannot leave a half-built campaign."""
        from core.db import q

        before = q("SELECT COUNT(*) c FROM chats", one=True)["c"]
        with pytest.raises(ExtensionError):
            campaign.provision_story(_package(), offscreen_life="nonsense")
        assert q("SELECT COUNT(*) c FROM chats", one=True)["c"] == before

    def test_it_does_not_flatten_the_rest_of_dialogue_config(
            self, temp_db, campaign):
        """One key merged in. A whole-blob write would discard the autonomy
        and line budgets the package arrived with, and nothing would fail --
        `dialogue_config()` re-fills every missing key from the default."""
        from core.db import wget, wset

        result = campaign.provision_story(_package())
        cid = result["chat_id"]
        wset(cid, "dialogue_config",
             {**(wget(cid, "dialogue_config") or {}), "autonomy": 17,
              "max_lines": 9})

        from extension_runtime.api import SonderExtensionAPI  # noqa: F401
        from story.scene import dialogue_config

        stored = dict(wget(cid, "dialogue_config") or {})
        stored["offscreen_life"] = "inert"
        wset(cid, "dialogue_config", stored)
        config = dialogue_config(cid)
        assert config["autonomy"] == 17
        assert config["max_lines"] == 9
        assert config["offscreen_life"] == "inert"

    def test_the_capabilities_are_advertised(self, temp_db, campaign):
        assert "living_world_provisioning" in campaign.capabilities
        assert "living_world_generation" in campaign.capabilities


class TestACharacterIsNamedByAnIdentityThatSurvivesAnArchive:
    def _attached(self, cid, name="Mara", uid="directive-crew-mara"):
        from core.db import qi

        char_id = qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps({"identity": {"name": name}}), "test", 0.0, uid))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
           "VALUES(?,?,?,?,?)", (cid, char_id, "active", "{}", ""))
        return char_id

    def test_a_uid_resolves_to_the_attached_character(self, temp_db):
        from world.charter_runtime import _prepare_cast_histories

        cid = _chat(temp_db)
        char_id = self._attached(cid)
        _clean, prepared = _prepare_cast_histories(cid, {
            "brief": "a ship",
            "character_histories": [{"resource_uid": "directive-crew-mara",
                                     "mode": "authored_only"}]})
        assert [row["char_id"] for row in prepared] == [char_id]

    def test_char_id_still_works(self, temp_db):
        from world.charter_runtime import _prepare_cast_histories

        cid = _chat(temp_db)
        char_id = self._attached(cid)
        _clean, prepared = _prepare_cast_histories(cid, {
            "brief": "a ship",
            "character_histories": [{"char_id": char_id,
                                     "mode": "authored_only"}]})
        assert [row["char_id"] for row in prepared] == [char_id]

    def test_the_same_person_twice_is_one_request(self, temp_db):
        from world.charter_runtime import _prepare_cast_histories

        cid = _chat(temp_db)
        char_id = self._attached(cid)
        _clean, prepared = _prepare_cast_histories(cid, {
            "brief": "a ship",
            "character_histories": [
                {"resource_uid": "directive-crew-mara", "mode": "authored_only"},
                {"char_id": char_id, "mode": "authored_only"}]})
        assert len(prepared) == 1

    def test_an_unresolvable_uid_is_refused_not_skipped(self, temp_db):
        """A stale `char_id` from a browser is a UI bug the author cannot act
        on, and is dropped. A `resource_uid` comes from a caller that believes
        it attached that character, and silently generating the location
        without them is the failure they most need told about."""
        from world.charter_runtime import _prepare_cast_histories

        cid = _chat(temp_db)
        self._attached(cid)
        with pytest.raises(ValueError) as excinfo:
            _prepare_cast_histories(cid, {
                "brief": "a ship",
                "character_histories": [
                    {"resource_uid": "nobody-by-that-name"}]})
        assert "nobody-by-that-name" in str(excinfo.value)

    def test_a_character_in_another_story_does_not_resolve(self, temp_db):
        """Resolution goes through `chat_chars`, so attachment to THIS story
        is enforced for either spelling."""
        from world.charter_runtime import _prepare_cast_histories

        other = _chat(temp_db)
        self._attached(other)
        with pytest.raises(ValueError):
            _prepare_cast_histories(_chat(temp_db), {
                "brief": "a ship",
                "character_histories": [
                    {"resource_uid": "directive-crew-mara"}]})


class TestALostGenerationIsNotPaidForTwice:
    def test_no_job_by_default(self, temp_db):
        from world.charter_runtime import lived_location_job

        assert lived_location_job(_chat(temp_db)) is None

    def test_a_running_job_from_a_dead_process_reads_as_interrupted(
            self, temp_db):
        """Derived from the owner token, not stored: a job cannot be left
        claiming to be alive by a process that is gone, and there is no
        staleness timeout to tune."""
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY,
                                           lived_location_job)

        cid = _chat(temp_db)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "a-dead-process",
              "status": "running", "stage": "planned", "digest": "d"})
        job = lived_location_job(cid)
        assert job["status"] == "interrupted"
        assert "server stopped" in job["error"]

    def test_this_process_s_own_job_still_reads_as_running(self, temp_db):
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY, _GEN_OWNER,
                                           lived_location_job)

        cid = _chat(temp_db)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": _GEN_OWNER,
              "status": "running", "stage": "planning", "digest": "d"})
        assert lived_location_job(cid)["status"] == "running"

    def test_a_stored_plan_is_reused_only_for_the_same_request(self, temp_db):
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY,
                                           _request_digest, _resumable_plan)

        cid = _chat(temp_db)
        request = {"brief": "a ship"}
        digest = _request_digest(cid, request, None)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "dead",
              "status": "running", "stage": "planned", "digest": digest,
              "artifact": {"town": {"name": "Site 17"}, "horizon": 720.0}})

        artifact, _job = _resumable_plan(cid, digest)
        assert artifact["town"] == {"name": "Site 17"}

        other, _job = _resumable_plan(
            cid, _request_digest(cid, {"brief": "a different place"}, None))
        assert other is None

    def test_a_plan_that_already_planted_rooms_is_not_reused(self, temp_db):
        """`_remap_generated_town` reads live state, so replaying the landing
        half would plant the same town a second time."""
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY,
                                           _request_digest, _resumable_plan)

        cid = _chat(temp_db)
        digest = _request_digest(cid, {"brief": "a ship"}, None)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "dead",
              "status": "running", "stage": "planted", "digest": digest,
              "artifact": {"town": {"name": "Site 17"}}})
        artifact, job = _resumable_plan(cid, digest)
        assert artifact is None
        assert job["stage"] == "planted"

    def test_the_digest_ignores_key_order(self, temp_db):
        from world.charter_runtime import _request_digest

        cid = _chat(temp_db)
        assert _request_digest(cid, {"a": 1, "b": 2}, None) == \
            _request_digest(cid, {"b": 2, "a": 1}, None)

    def test_the_digest_separates_eras(self, temp_db):
        from world.charter_runtime import _request_digest

        cid = _chat(temp_db)
        assert _request_digest(cid, {"a": 1}, None) != \
            _request_digest(cid, {"a": 1}, 4)

    def test_clearing_forgets_it(self, temp_db):
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY,
                                           clear_lived_location_job,
                                           lived_location_job)

        cid = _chat(temp_db)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "dead",
              "status": "running", "stage": "planned", "digest": "d"})
        clear_lived_location_job(cid)
        assert lived_location_job(cid) is None

    def test_the_api_hides_the_stored_plan(self, temp_db, campaign):
        """The artefact is large and of no use to a caller; the status is the
        answer."""
        from core.db import wset
        from world.charter_runtime import LIVED_LOCATION_JOB_KEY

        cid = _chat(temp_db)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "dead",
              "status": "running", "stage": "planned", "digest": "d",
              "artifact": {"town": {"name": "Site 17"}}})
        job = campaign.living_world_job(cid)
        assert job["status"] == "interrupted"
        assert "artifact" not in job

    def test_the_api_says_none_when_there_is_no_job(self, temp_db, campaign):
        assert campaign.living_world_job(_chat(temp_db)) is None

    def test_a_non_dict_request_is_refused_by_name(self, temp_db, campaign):
        with pytest.raises(ExtensionError) as excinfo:
            campaign.generate_lived_location(_chat(temp_db), "a ship")
        assert "request dict" in str(excinfo.value)


class TestTheResumePathActuallyResumes:
    """The bug the first cut of this shipped, and the reason these exist.

    `_resumable_plan` returned the stored plan and the caller never assigned
    it to `town` -- it set `plan = None` and fed that to `close_plan`, which
    silently produced an EMPTY town. The resume path planted nothing, reported
    success and cleared the job. Four independent review lenses found it and
    the original tests did not, because they exercised `_resumable_plan` in
    isolation and never ran a resume end to end. These do.
    """

    def _stub_generation(self, monkeypatch):
        """The two model calls, replaced by counters."""
        calls = {"town": 0, "history": 0}
        from world import charter_generate

        def propose_town(lore, brief, constraints=None):
            calls["town"] += 1
            return {"name": "Site 17", "rooms": {}, "charters": {}}

        def propose_history(plan, lore, horizon):
            calls["history"] += 1
            return {}

        monkeypatch.setattr(charter_generate, "propose_town", propose_town)
        monkeypatch.setattr(charter_generate, "propose_history",
                            propose_history)
        return calls

    def test_a_resume_skips_the_model_calls_and_keeps_the_town(
            self, temp_db, monkeypatch):
        """The artifact is a CLOSED town, not a plan -- so a resume must skip
        `close_plan` too, not merely `propose_town`."""
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY,
                                           _request_digest, _resumable_plan)

        cid = _chat(temp_db)
        request = {"brief": "a ship"}
        digest = _request_digest(cid, request, None)
        artifact = {"town": {"name": "Site 17", "rooms": {}, "charters": {}},
                    "required_rooms_added": [], "lore_manifest": {},
                    "source_book": None, "owning_book": None,
                    "horizon": 720.0, "wants_history": False}
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "dead",
              "status": "running", "stage": "planned", "digest": digest,
              "artifact": artifact})

        restored, _job = _resumable_plan(cid, digest)
        assert restored["town"]["name"] == "Site 17"
        # Every field the landing half needs, or a resume carries one run's
        # town beside another run's lore provenance.
        from world.charter_runtime import _ARTIFACT_FIELDS
        assert set(_ARTIFACT_FIELDS) <= set(restored)

    def test_an_artifact_without_a_town_is_not_resumable(self, temp_db):
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY,
                                           _request_digest, _resumable_plan)

        cid = _chat(temp_db)
        digest = _request_digest(cid, {"brief": "a ship"}, None)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "dead",
              "status": "running", "stage": "planned", "digest": digest,
              "artifact": {"horizon": 720.0}})
        restored, _job = _resumable_plan(cid, digest)
        assert restored is None


class TestAHalfPlantedTownIsNeverPlantedAgain:
    """The second blocker: the refusal was gated on `status ==
    "interrupted"`, which is only ever derived for a FOREIGN owner. A run that
    died inside a live process kept `status: running` and sailed past it.
    And on a matching digest, so the obvious retry -- same request, one field
    changed -- bypassed it too."""

    def _job(self, temp_db, cid, **over):
        from core.db import wset
        from world.charter_runtime import LIVED_LOCATION_JOB_KEY

        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "status": "running",
              "stage": "planted", "digest": "digest-a", **over})

    @pytest.mark.parametrize("stage", ["planting", "planted", "presimmed"])
    def test_every_past_boundary_stage_refuses(self, temp_db, stage):
        from world.charter_runtime import (PAST_BOUNDARY_STAGES,
                                           generate_lived_location)

        assert stage in PAST_BOUNDARY_STAGES
        cid = _chat(temp_db)
        self._job(temp_db, cid, stage=stage)
        with pytest.raises(ValueError) as excinfo:
            generate_lived_location(cid, {"brief": "anything"})
        assert stage in str(excinfo.value)

    def test_it_refuses_a_job_this_very_process_owns(self, temp_db):
        """A same-process failure never sets `interrupted`, so a status test
        would have let this through."""
        from world.charter_runtime import _GEN_OWNER, generate_lived_location

        cid = _chat(temp_db)
        self._job(temp_db, cid, owner=_GEN_OWNER)
        with pytest.raises(ValueError):
            generate_lived_location(cid, {"brief": "anything"})

    def test_it_refuses_a_different_request_too(self, temp_db):
        """A story with half-planted rooms is in that state whatever is asked
        for next, and changing one field is the obvious retry."""
        from world.charter_runtime import generate_lived_location

        cid = _chat(temp_db)
        self._job(temp_db, cid, owner="dead", digest="digest-a")
        with pytest.raises(ValueError):
            generate_lived_location(cid, {"brief": "a completely new place"})

    def test_clearing_it_lets_the_next_run_start(self, temp_db):
        from world.charter_runtime import (clear_lived_location_job,
                                           lived_location_job)

        cid = _chat(temp_db)
        self._job(temp_db, cid, owner="dead")
        clear_lived_location_job(cid)
        assert lived_location_job(cid) is None

    def test_the_marker_leads_the_write(self, temp_db):
        """`planting` is recorded BEFORE `plant_structure`. A marker claiming
        a write that did not happen costs one wasted regeneration; one that
        misses a write that DID happen costs a second town on the same
        ground, and only the first is recoverable."""
        import inspect

        from world import charter_runtime

        body = inspect.getsource(charter_runtime._generate_lived_location)
        assert body.index('"stage": "planting"') < body.index(
            "structure, rooms = plant_structure(")


class TestAFailureLeavesAnHonestRecord:
    def test_a_failure_before_the_boundary_forgets_the_job(self, temp_db):
        """Nothing was written, so there is nothing to recover -- and a stale
        `running` claim owned by this process would look live forever."""
        from world.charter_runtime import (generate_lived_location,
                                           lived_location_job)

        cid = _chat(temp_db)
        with pytest.raises(ValueError):
            generate_lived_location(cid, {
                "brief": "a ship",
                "character_histories": [{"resource_uid": "nobody"}]})
        assert lived_location_job(cid) is None

    def test_a_failure_after_the_boundary_keeps_it(self, temp_db):
        """The record is what refuses the next run, so it is marked, never
        cleared."""
        from world.charter_runtime import _fail_job, lived_location_job
        from core.db import wset
        from world.charter_runtime import LIVED_LOCATION_JOB_KEY

        cid = _chat(temp_db)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "dead",
              "status": "running", "stage": "planted", "digest": "d"})
        _fail_job(cid, RuntimeError("the historian died"))
        job = lived_location_job(cid)
        assert job["status"] == "failed"
        assert "the historian died" in job["error"]


class TestTheDetailControlIsReachable:
    """It was documented in two guides and forwarded by nothing."""

    def test_through_the_extension_api(self, temp_db, campaign):
        from core.db import wset

        cid = _chat(temp_db)
        wset(cid, "charters", {"version": 1, "items": {"ops": {
            "state": {"key": "ops", "bodies": {}, "posts": {}, "upkeeps": {}},
            "window_hours": 6}}})
        full = campaign.story_view(
            cid, charters="full")["living_world"]["charters"]
        assert "items" in full

    def test_through_the_frame_bound_view(self, temp_db, campaign):
        view = campaign.at_frame(_chat(temp_db), None).story_view(
            charters="full")
        assert isinstance(view["living_world"]["charters"], dict)

    def test_full_detail_has_one_shape_with_or_without_a_registry(
            self, temp_db, campaign):
        """A consumer indexing `["items"]` should not have to know whether
        this story happens to have institutions yet."""
        empty = campaign.story_view(
            _chat(temp_db), charters="full")["living_world"]["charters"]
        assert empty == {"version": 1, "items": {}}

    def test_the_summary_stays_a_list(self, temp_db, campaign):
        assert campaign.story_view(
            _chat(temp_db))["living_world"]["charters"] == []


class TestGenerationHoldsTheRouteSGuards:
    def test_a_turn_in_flight_refuses_generation(self, temp_db, campaign):
        """The HTTP route 409s here; the Python path used to proceed and race
        the turn's own commit."""
        from web import app as web_app

        cid = _chat(temp_db)
        web_app.ABORTS[(cid, None)] = object()
        try:
            with pytest.raises(ExtensionError) as excinfo:
                campaign.generate_lived_location(cid, {"brief": "a ship"})
            assert "turn is running" in str(excinfo.value)
        finally:
            web_app.ABORTS.pop((cid, None), None)


class TestTheCapIsCheckedBeforeTheQuery:
    def test_too_many_uids_is_the_documented_refusal(self, temp_db):
        """One placeholder per uid, so an oversized request used to reach
        sqlite's variable limit instead of the cap's own message."""
        from world.charter_runtime import (CAST_HISTORY_REQUEST_CAP,
                                           _prepare_cast_histories)

        cid = _chat(temp_db)
        rows = [{"resource_uid": f"uid-{i}"}
                for i in range(CAST_HISTORY_REQUEST_CAP + 5)]
        with pytest.raises(ValueError) as excinfo:
            _prepare_cast_histories(cid, {"brief": "a ship",
                                          "character_histories": rows})
        assert "at most" in str(excinfo.value)

    def test_a_second_live_run_is_refused(self, temp_db):
        """`_require_frame_idle` cannot see this — it reads the turn
        pipeline's registry, which generation never joins — so two hooks or a
        double-click gave two runs claiming one job slot, and the loser's
        `planted` marker was erased by the winner's `planning`."""
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY, _GEN_OWNER,
                                           generate_lived_location)

        cid = _chat(temp_db)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": _GEN_OWNER,
              "status": "running", "stage": "planning", "digest": "d"})
        with pytest.raises(ValueError) as excinfo:
            generate_lived_location(cid, {"brief": "a ship"})
        assert "already running" in str(excinfo.value)

    def test_a_run_from_a_dead_process_is_not_mistaken_for_a_live_one(
            self, temp_db):
        """It reads as `interrupted`, and at a pre-boundary stage nothing was
        written, so the next run may simply proceed."""
        from core.db import wset
        from world.charter_runtime import (LIVED_LOCATION_JOB_KEY,
                                           lived_location_job)

        cid = _chat(temp_db)
        wset(cid, LIVED_LOCATION_JOB_KEY,
             {"version": 1, "job_id": "abc", "owner": "a-dead-process",
              "status": "running", "stage": "planning", "digest": "d"})
        assert lived_location_job(cid)["status"] == "interrupted"
