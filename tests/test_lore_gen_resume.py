"""Regression tests for resumable lorebook-tree generation.

Generating a tree is many model calls (one structure call deciding books,
links and an outline of the entries, then one call per batch of outlined
entries). Every one of them can be lost to a dropped connection, an exhausted
provider retry budget, a closed browser tab, or a server restart -- and losing
any one of them used to lose ALL of them, because the whole run lived in a
single blocking request and nothing was written down until the user applied
the finished plan.

Each completed unit of work is now persisted to lore_gen_jobs the moment it
lands, so what these tests pin down is the recovery contract:

* an interruption keeps every batch that already finished,
* a resume re-runs only the units that never finished,
* a batch that returns unusable output does not cost the other batches,
* nothing in a generation run writes lore -- the plan is still provisional
  until it is applied.
"""

from __future__ import annotations

import json
import math

import httpx
import pytest

import importers
import providers


# ---- harness --------------------------------------------------------------

def _make_book(db, name="Canon", parent_id=None):
    return db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) VALUES(?,?,?,?)",
        (name, None, "general", parent_id),
    )


def _outline(count, book_id=None, start=0):
    return [
        {
            "book_id": book_id,
            "title": f"Subject {i}",
            "keys": f"subject{i}",
            "category": "other",
            "focus": f"cover subject {i}",
        }
        for i in range(start, start + count)
    ]


def _entries_for(batch):
    return {
        "entry_ops": [
            {
                "op": "create",
                "outline_index": stub["outline_index"],
                "book_id": stub["book_id"],
                "keys": stub["keys"],
                "title": stub["title"],
                "category": "other",
                "content": f"Body of {stub['title']}.",
            }
            for stub in batch
        ]
    }


class FakeModel:
    """Stands in for chat_complete, scripted per call kind.

    `structure` and `batch` are callables taking the request payload; either
    may raise, which is how the tests inject interruptions and bad output at a
    precise point in the run.
    """

    def __init__(self, structure, batch=None):
        self._structure = structure
        self._batch = batch or (lambda payload: _entries_for(payload["batch"]))
        self.structure_calls = []
        self.batch_calls = []

    def __call__(self, role, system, user, **kwargs):
        payload = json.loads(user)

        if payload.get("stage") == "structure":
            self.structure_calls.append(payload)
            result = self._structure(payload)
        else:
            self.batch_calls.append(payload)
            result = self._batch(payload)

        return result if isinstance(result, str) else json.dumps(result)

    @property
    def batched_titles(self):
        """Every stub title the model was actually asked to write, in order --
        this is what proves a resume did not regenerate finished work."""
        return [
            stub["title"]
            for payload in self.batch_calls
            for stub in payload["batch"]
        ]


@pytest.fixture
def model(monkeypatch):
    """Installs a FakeModel on demand and returns the installer."""

    def install(structure, batch=None):
        fake = FakeModel(structure, batch)
        monkeypatch.setattr(importers, "chat_complete", fake)
        return fake

    return install


def _plan_of(structure_extra=None, outline_count=8, book_ops=None):
    def build(payload):
        response = {
            "analysis": {"themes": ["trade"], "missing_areas": []},
            "book_ops": book_ops or [],
            "link_ops": [],
            "entry_ops": [],
            "entry_outline": _outline(outline_count),
        }
        response.update(structure_extra or {})
        return response

    return build


def _dropped_connection(_payload):
    raise httpx.ConnectError("connection reset by peer")


# ---- the happy path, for contrast ----------------------------------------

class TestCompleteRun:
    def test_a_finished_run_is_ready_and_batches_the_outline(self, temp_db, model):
        book = _make_book(temp_db)
        fake = model(_plan_of(outline_count=8))

        plan = importers.generate_lorebook_plan(book, "expand the trade lore")

        assert len(plan["entry_ops"]) == 8
        assert plan["_job"]["status"] == "ready"
        assert plan["_job"]["entries_done"] == 8
        assert plan["_job"]["entries_remaining"] == 0
        # One structure call plus one call per batch of LORE_GEN_ENTRY_BATCH.
        assert len(fake.structure_calls) == 1
        assert len(fake.batch_calls) == math.ceil(
            8 / importers.LORE_GEN_ENTRY_BATCH
        )

    def test_generation_writes_no_lore(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=8))

        importers.generate_lorebook_plan(book, "expand")

        # The plan stays provisional: only apply_lorebook_plan may write.
        assert temp_db.q("SELECT COUNT(*) c FROM lore_entries", one=True)["c"] == 0
        assert temp_db.q("SELECT COUNT(*) c FROM lorebooks", one=True)["c"] == 1

    def test_a_ready_run_is_not_offered_as_resumable(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=2))

        importers.generate_lorebook_plan(book, "expand")
        job = importers.recoverable_lore_gen_job(book)

        # It IS recoverable (the plan exists and was never applied) but there
        # is no work left to resume.
        assert job["restorable"] is True
        assert job["resumable"] is False


# ---- interruption during the entry batches -------------------------------

class TestInterruptedBatches:
    def _run_until_dropped(self, book, model):
        state = {"calls": 0}

        def batch(payload):
            state["calls"] += 1
            if state["calls"] > 1:
                raise httpx.ConnectError("connection reset by peer")
            return _entries_for(payload["batch"])

        fake = model(_plan_of(outline_count=8), batch)
        plan = importers.generate_lorebook_plan(book, "expand")
        return fake, plan

    def test_the_completed_batch_survives_and_is_handed_back(self, temp_db, model):
        book = _make_book(temp_db)
        _fake, plan = self._run_until_dropped(book, model)

        # A partial plan is returned rather than raised away: the user paid
        # for these entries.
        assert len(plan["entry_ops"]) == importers.LORE_GEN_ENTRY_BATCH
        assert plan["_job"]["status"] == "interrupted"
        assert plan["_job"]["resumable"] is True
        assert plan["_job"]["entries_done"] == importers.LORE_GEN_ENTRY_BATCH
        assert plan["_job"]["entries_remaining"] == 2
        assert "Interrupted" in plan["_job"]["error"]

    def test_it_stops_rather_than_marching_into_a_dead_provider(self, temp_db, model):
        book = _make_book(temp_db)
        fake, _plan = self._run_until_dropped(book, model)

        # chat_complete has already exhausted its own retries by the time the
        # error surfaces, so the remaining batch must not be attempted.
        assert len(fake.batch_calls) == 2

    def test_resume_regenerates_only_the_missing_entries(self, temp_db, model):
        book = _make_book(temp_db)
        _fake, plan = self._run_until_dropped(book, model)
        job_id = plan["_job"]["id"]

        healthy = model(_plan_of(outline_count=8))
        resumed = importers.resume_lorebook_plan(job_id)

        # The structure stage is settled; only the unfinished stubs are sent.
        assert healthy.structure_calls == []
        assert healthy.batched_titles == ["Subject 6", "Subject 7"]
        assert len(resumed["entry_ops"]) == 8
        assert resumed["_job"]["status"] == "ready"
        assert resumed["_job"]["entries_remaining"] == 0
        assert resumed["_job"]["id"] == job_id

    def test_resume_preserves_the_entries_the_first_attempt_produced(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        _fake, plan = self._run_until_dropped(book, model)
        first = [op["title"] for op in plan["entry_ops"]]

        model(_plan_of(outline_count=8))
        resumed = importers.resume_lorebook_plan(plan["_job"]["id"])

        titles = [op["title"] for op in resumed["entry_ops"]]
        assert titles[:len(first)] == first
        assert titles == [f"Subject {i}" for i in range(8)]

    def test_resume_uses_the_original_request(self, temp_db, model):
        book = _make_book(temp_db)

        def batch(payload):
            raise httpx.ConnectError("dropped")

        model(_plan_of(outline_count=3), batch)
        with pytest.raises(importers.LoreGenError):
            importers.generate_lorebook_plan(
                book, "chart the salt roads", mode="location_hierarchy",
                entry_target=17,
            )

        job = importers.recoverable_lore_gen_job(book)
        # The request survives the interruption, so a resume needs nothing
        # from the browser that started it.
        assert job["params"]["brief"] == "chart the salt roads"
        assert job["params"]["mode"] == "location_hierarchy"
        assert job["params"]["entry_target"] == 17

    def test_a_retryable_provider_error_counts_as_an_interruption(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        state = {"calls": 0}

        def batch(payload):
            state["calls"] += 1
            if state["calls"] > 1:
                raise providers.LLMError("HTTP 503: overloaded", 503, True)
            return _entries_for(payload["batch"])

        model(_plan_of(outline_count=8), batch)
        plan = importers.generate_lorebook_plan(book, "expand")

        assert plan["_job"]["status"] == "interrupted"
        assert plan["_job"]["resumable"] is True

    def test_an_abort_counts_as_an_interruption(self, temp_db, model):
        book = _make_book(temp_db)
        state = {"calls": 0}

        def batch(payload):
            state["calls"] += 1
            if state["calls"] > 1:
                raise providers.Aborted("cancelled")
            return _entries_for(payload["batch"])

        model(_plan_of(outline_count=8), batch)
        plan = importers.generate_lorebook_plan(book, "expand")

        assert plan["_job"]["status"] == "interrupted"
        assert plan["_job"]["resumable"] is True


# ---- interruption during the structure stage ----------------------------

class TestInterruptedStructure:
    def test_it_raises_a_resumable_error(self, temp_db, model):
        book = _make_book(temp_db)
        model(_dropped_connection)

        with pytest.raises(importers.LoreGenError) as excinfo:
            importers.generate_lorebook_plan(book, "expand")

        # No usable plan exists, so this one does raise -- but it names a job
        # rather than vanishing.
        assert excinfo.value.interrupted is True
        assert excinfo.value.job_id is not None

    def test_the_job_is_recoverable_and_still_at_the_structure_stage(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        model(_dropped_connection)
        with pytest.raises(importers.LoreGenError):
            importers.generate_lorebook_plan(book, "expand")

        job = importers.recoverable_lore_gen_job(book)
        assert job["status"] == "interrupted"
        assert job["stage"] == "structure"
        assert job["resumable"] is True

    def test_resume_re_runs_the_structure_stage_and_completes(self, temp_db, model):
        book = _make_book(temp_db)
        model(_dropped_connection)
        with pytest.raises(importers.LoreGenError) as excinfo:
            importers.generate_lorebook_plan(book, "expand")

        healthy = model(_plan_of(outline_count=4))
        resumed = importers.resume_lorebook_plan(excinfo.value.job_id)

        assert len(healthy.structure_calls) == 1
        assert len(resumed["entry_ops"]) == 4
        assert resumed["_job"]["status"] == "ready"
        assert resumed["_job"]["attempts"] == 2

    def test_a_plan_proposing_nothing_at_all_is_a_failure(self, temp_db, model):
        book = _make_book(temp_db)
        model(lambda payload: {
            "analysis": {"themes": []}, "book_ops": [], "link_ops": [],
            "entry_ops": [], "entry_outline": [],
        })

        # Parseable but empty in every dimension. Reporting this as a finished
        # plan would present nothing as a result.
        with pytest.raises(importers.LoreGenError):
            importers.generate_lorebook_plan(book, "expand")

    def test_a_books_only_plan_is_not_treated_as_empty(self, temp_db, model):
        book = _make_book(temp_db)
        model(lambda payload: {
            "analysis": {}, "link_ops": [], "entry_ops": [], "entry_outline": [],
            "book_ops": [{
                "op": "create", "temp_id": "b1", "name": "Split Off",
                "book_type": "location",
            }],
        })

        plan = importers.generate_lorebook_plan(book, "reorganize")

        # Restructuring modes legitimately propose books without entries.
        assert len(plan["book_ops"]) == 1
        assert plan["_job"]["status"] == "ready"

    def test_unparseable_structure_output_is_a_failure_not_an_interruption(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        model(lambda payload: "I'm afraid I can't help with that.")

        with pytest.raises(importers.LoreGenError) as excinfo:
            importers.generate_lorebook_plan(book, "expand")

        assert excinfo.value.interrupted is False
        job = importers.lore_gen_job(excinfo.value.job_id)
        assert job["status"] == "failed"
        # Still resumable: resuming re-runs the structure call with the same
        # request, which is exactly the right retry.
        assert job["resumable"] is True


# ---- a bad batch is not an interruption ---------------------------------

class TestUnusableBatchOutput:
    def _run_with_one_bad_batch(self, book, model):
        def batch(payload):
            if payload["batch"][0]["outline_index"] == 0:
                return "not json at all"
            return _entries_for(payload["batch"])

        fake = model(_plan_of(outline_count=8), batch)
        plan = importers.generate_lorebook_plan(book, "expand")
        return fake, plan

    def test_one_bad_batch_does_not_cost_the_others(self, temp_db, model):
        book = _make_book(temp_db)
        fake, plan = self._run_with_one_bad_batch(book, model)

        # Both batches were attempted -- unusable output is a content problem,
        # not a reason to abandon the run.
        assert len(fake.batch_calls) == 2
        assert [op["title"] for op in plan["entry_ops"]] == [
            "Subject 6", "Subject 7",
        ]

    def test_the_run_ends_interrupted_and_names_the_bad_batch(self, temp_db, model):
        book = _make_book(temp_db)
        _fake, plan = self._run_with_one_bad_batch(book, model)

        job = plan["_job"]
        assert job["status"] == "interrupted"
        assert job["resumable"] is True
        assert job["entries_done"] == 2
        assert job["entries_remaining"] == 6
        assert len(job["stage_errors"]) == 1

    def test_resume_retries_only_the_failed_stubs(self, temp_db, model):
        book = _make_book(temp_db)
        _fake, plan = self._run_with_one_bad_batch(book, model)

        healthy = model(_plan_of(outline_count=8))
        resumed = importers.resume_lorebook_plan(plan["_job"]["id"])

        assert healthy.batched_titles == [f"Subject {i}" for i in range(6)]
        assert len(resumed["entry_ops"]) == 8
        assert resumed["_job"]["status"] == "ready"

    def test_a_successful_resume_clears_the_previous_attempts_complaints(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        _fake, plan = self._run_with_one_bad_batch(book, model)
        assert plan["_job"]["stage_errors"]

        model(_plan_of(outline_count=8))
        resumed = importers.resume_lorebook_plan(plan["_job"]["id"])

        # Still reporting the fixed batch would read as an unfinished run.
        assert resumed["_job"]["stage_errors"] == []

    def test_a_short_batch_leaves_the_missing_entries_retriable(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)

        def batch(payload):
            # Answers only half its batch -- a partial batch, not a complete
            # one, so the skipped stubs must not be marked done.
            half = payload["batch"][:len(payload["batch"]) // 2]
            return _entries_for(half)

        model(_plan_of(outline_count=6), batch)
        plan = importers.generate_lorebook_plan(book, "expand")

        assert len(plan["entry_ops"]) == 3
        assert plan["_job"]["status"] == "interrupted"
        assert plan["_job"]["entries_done"] == 3
        assert plan["_job"]["entries_remaining"] == 3

        healthy = model(_plan_of(outline_count=6))
        resumed = importers.resume_lorebook_plan(plan["_job"]["id"])

        assert healthy.batched_titles == ["Subject 3", "Subject 4", "Subject 5"]
        assert len(resumed["entry_ops"]) == 6

    def test_a_repeated_outline_index_does_not_duplicate_one_subject(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)

        def batch(payload):
            response = _entries_for(payload["batch"])
            # Every op claims the same stub. Trusting the echo blindly would
            # write one subject three times and silently drop the other two.
            for op in response["entry_ops"]:
                op["outline_index"] = 0
            return response

        model(_plan_of(outline_count=3), batch)
        plan = importers.generate_lorebook_plan(book, "expand")

        book_ids = [op["book_id"] for op in plan["entry_ops"]]
        titles = [op["title"] for op in plan["entry_ops"]]
        assert book_ids == [book, book, book]
        assert sorted(titles) == ["Subject 0", "Subject 1", "Subject 2"]
        assert plan["_job"]["status"] == "ready"

    def test_a_batch_returning_no_entries_is_also_retried(self, temp_db, model):
        book = _make_book(temp_db)

        def batch(payload):
            if payload["batch"][0]["outline_index"] == 0:
                return {"entry_ops": []}
            return _entries_for(payload["batch"])

        model(_plan_of(outline_count=8), batch)
        plan = importers.generate_lorebook_plan(book, "expand")

        assert plan["_job"]["status"] == "interrupted"
        assert plan["_job"]["entries_remaining"] == 6


# ---- crashes and orphaned runs -----------------------------------------

class TestOrphanedRuns:
    def test_a_run_abandoned_by_a_dead_process_becomes_resumable(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=8))
        plan = importers.generate_lorebook_plan(book, "expand")
        job_id = plan["_job"]["id"]

        # Simulate the server having been killed mid-run: the row is left
        # 'running', stamped by a process that no longer exists.
        temp_db.qi(
            "UPDATE lore_gen_jobs SET status='running', stage='entries', "
            "owner='some-dead-process' WHERE id=?",
            (job_id,),
        )

        job = importers.recoverable_lore_gen_job(book)
        assert job["id"] == job_id
        assert job["status"] == "interrupted"
        assert job["resumable"] is True
        assert job["running"] is False

    def test_a_live_run_is_reported_as_running_not_resumable(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=8))
        plan = importers.generate_lorebook_plan(book, "expand")

        temp_db.qi(
            "UPDATE lore_gen_jobs SET status='running' WHERE id=?",
            (plan["_job"]["id"],),
        )

        job = importers.recoverable_lore_gen_job(book)
        assert job["running"] is True
        assert job["resumable"] is False

    def test_resume_refuses_a_run_this_process_is_still_executing(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=8))
        plan = importers.generate_lorebook_plan(book, "expand")
        temp_db.qi(
            "UPDATE lore_gen_jobs SET status='running' WHERE id=?",
            (plan["_job"]["id"],),
        )

        with pytest.raises(ValueError, match="still running"):
            importers.resume_lorebook_plan(plan["_job"]["id"])


# ---- retiring a run ----------------------------------------------------

class TestRetiringRuns:
    def test_an_applied_run_is_no_longer_recoverable(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=2))
        plan = importers.generate_lorebook_plan(book, "expand")

        importers.mark_lore_gen_job_applied(plan["_job"]["id"])

        assert importers.recoverable_lore_gen_job(book) is None

    def test_a_discarded_run_is_no_longer_recoverable(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=2))
        plan = importers.generate_lorebook_plan(book, "expand")

        importers.cancel_lore_gen_job(plan["_job"]["id"])

        assert importers.recoverable_lore_gen_job(book) is None

    def test_resume_refuses_an_applied_or_discarded_run(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=2))
        plan = importers.generate_lorebook_plan(book, "expand")
        job_id = plan["_job"]["id"]

        importers.cancel_lore_gen_job(job_id)
        with pytest.raises(ValueError, match="cancelled"):
            importers.resume_lorebook_plan(job_id)

    def test_a_ready_run_is_restored_without_another_model_call(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=3))
        plan = importers.generate_lorebook_plan(book, "expand")

        # The closed-tab case: the plan finished generating but its response
        # never reached the browser. Restoring it must not regenerate.
        idle = model(_plan_of(outline_count=3))
        restored = importers.resume_lorebook_plan(plan["_job"]["id"])

        assert idle.structure_calls == []
        assert idle.batch_calls == []
        assert len(restored["entry_ops"]) == 3
        assert restored["_job"]["status"] == "ready"

    def test_only_the_newest_runs_per_book_are_kept(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=1))

        for _ in range(importers.LORE_GEN_KEEP_PER_BOOK + 3):
            importers.generate_lorebook_plan(book, "expand")

        kept = temp_db.q(
            "SELECT COUNT(*) c FROM lore_gen_jobs WHERE lorebook_id=?",
            (book,), one=True,
        )["c"]
        assert kept == importers.LORE_GEN_KEEP_PER_BOOK

    def test_deleting_the_book_deletes_its_runs(self, temp_db, model):
        book = _make_book(temp_db)
        model(_plan_of(outline_count=1))
        importers.generate_lorebook_plan(book, "expand")

        temp_db.qi("DELETE FROM lorebooks WHERE id=?", (book,))

        assert temp_db.q("SELECT COUNT(*) c FROM lore_gen_jobs", one=True)["c"] == 0


# ---- routing entries the outline chose ---------------------------------

class TestEntryRouting:
    def test_an_entry_keeps_the_planned_book_its_stub_chose(self, temp_db, model):
        book = _make_book(temp_db)
        structure = _plan_of(
            outline_count=0,
            book_ops=[{
                "op": "create", "temp_id": "salt_roads",
                "name": "The Salt Roads", "book_type": "location",
            }],
        )

        def with_outline(payload):
            response = structure(payload)
            response["entry_outline"] = [{
                "book_id": "salt_roads", "title": "Toll Houses",
                "keys": "toll", "category": "location", "focus": "the tolls",
            }]
            return response

        model(with_outline)
        plan = importers.generate_lorebook_plan(book, "expand")

        # The temp_id must survive to apply time, which is what files the
        # entry into the child book instead of flattening it into canon.
        assert plan["entry_ops"][0]["book_id"] == "salt_roads"

    def test_an_unresolvable_book_reference_falls_back_to_the_selected_book(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)

        def with_outline(payload):
            return {
                "analysis": {}, "book_ops": [], "link_ops": [], "entry_ops": [],
                "entry_outline": [{
                    "book_id": "no_such_book", "title": "Orphan",
                    "keys": "orphan", "category": "other", "focus": "x",
                }],
            }

        model(with_outline)
        plan = importers.generate_lorebook_plan(book, "expand")

        # Misfiled is fixable by hand; silently dropped is not.
        assert plan["entry_ops"][0]["book_id"] == book

    def test_the_stub_not_the_model_decides_the_book(self, temp_db, model):
        book = _make_book(temp_db)
        other = _make_book(temp_db, "Elsewhere")

        def batch(payload):
            response = _entries_for(payload["batch"])
            # A model that rewrites book_id must not be able to misfile lore.
            for op in response["entry_ops"]:
                op["book_id"] = other
            return response

        model(_plan_of(outline_count=2), batch)
        plan = importers.generate_lorebook_plan(book, "expand")

        assert [op["book_id"] for op in plan["entry_ops"]] == [book, book]


# ---- single-call compatibility ----------------------------------------

class TestSingleCallResponses:
    def test_a_structure_call_that_returns_finished_entries_is_accepted(
        self, temp_db, model,
    ):
        book = _make_book(temp_db)
        fake = model(lambda payload: {
            "analysis": {"themes": []},
            "book_ops": [],
            "link_ops": [],
            "entry_ops": [
                {"op": "create", "book_id": book, "keys": "a",
                 "content": "A fact.", "category": "other", "title": "A"},
                {"op": "create", "book_id": book, "keys": "b",
                 "content": "B fact.", "category": "other", "title": "B"},
            ],
        })

        plan = importers.generate_lorebook_plan(book, "expand")

        # A custom prompt preset predating staged generation (or a model that
        # ignores the stage flag) still produces a usable plan in one call.
        assert fake.batch_calls == []
        assert len(plan["entry_ops"]) == 2
        assert plan["_job"]["status"] == "ready"
        assert plan["_job"]["entries_total"] == 0

    def test_a_flat_entries_list_is_still_normalized(self, temp_db, model):
        book = _make_book(temp_db)
        model(lambda payload: {
            "analysis": {},
            "entries": [
                {"keys": "a", "content": "A fact.", "category": "other"},
            ],
        })

        plan = importers.generate_lorebook_plan(book, "expand")

        assert len(plan["entry_ops"]) == 1
        assert plan["entry_ops"][0]["book_id"] == book
        assert plan["_job"]["status"] == "ready"


class TestReadTimeout:
    """The 300s default is sized for pipeline turns, not for a slow local model
    grinding through a batch of lore entries -- and a read timeout surfaces as
    exactly the kind of interruption this all exists to recover from, so the
    retry has to be able to give the model longer than the attempt that ran
    out of it."""

    def _observed_timeouts(self, monkeypatch):
        seen = []

        def record(role, system, user, **kwargs):
            seen.append(providers.read_timeout_override.get())
            payload = json.loads(user)
            if payload.get("stage") == "structure":
                return json.dumps({
                    "analysis": {}, "book_ops": [], "link_ops": [],
                    "entry_ops": [], "entry_outline": _outline(2),
                })
            return json.dumps(_entries_for(payload["batch"]))

        monkeypatch.setattr(importers, "chat_complete", record)
        return seen

    def test_the_default_leaves_the_timeout_alone(self, temp_db, monkeypatch):
        book = _make_book(temp_db)
        seen = self._observed_timeouts(monkeypatch)

        importers.generate_lorebook_plan(book, "expand")

        # No override: every call runs on providers.REQUEST_TIMEOUT.
        assert seen == [None, None]

    def test_a_raised_timeout_applies_to_every_call_in_the_run(
        self, temp_db, monkeypatch,
    ):
        book = _make_book(temp_db)
        seen = self._observed_timeouts(monkeypatch)

        importers.generate_lorebook_plan(book, "expand", timeout=1200)

        assert seen == [1200.0, 1200.0]

    def _interrupted_run(self, book, model, timeout):
        """Start a run whose every entry batch drops, and return its job id."""
        model(_plan_of(outline_count=2), _dropped_connection)
        with pytest.raises(importers.LoreGenError) as excinfo:
            importers.generate_lorebook_plan(book, "expand", timeout=timeout)
        return excinfo.value.job_id

    def test_it_is_stored_with_the_request_so_a_resume_inherits_it(
        self, temp_db, monkeypatch, model,
    ):
        book = _make_book(temp_db)
        job_id = self._interrupted_run(book, model, 900)

        seen = self._observed_timeouts(monkeypatch)
        importers.resume_lorebook_plan(job_id)

        assert importers.lore_gen_job(job_id)["params"]["timeout"] == 900.0
        assert seen and all(value == 900.0 for value in seen)

    def test_a_resume_may_raise_it_further(self, temp_db, monkeypatch, model):
        book = _make_book(temp_db)
        job_id = self._interrupted_run(book, model, 600)

        seen = self._observed_timeouts(monkeypatch)
        importers.resume_lorebook_plan(job_id, timeout=2400)

        assert seen and all(value == 2400.0 for value in seen)
        # Persisted, so any further batch or resume keeps the new allowance.
        assert importers.lore_gen_job(job_id)["params"]["timeout"] == 2400.0

    def test_a_resume_without_one_keeps_the_stored_allowance(
        self, temp_db, monkeypatch, model,
    ):
        book = _make_book(temp_db)
        job_id = self._interrupted_run(book, model, 900)

        seen = self._observed_timeouts(monkeypatch)
        importers.resume_lorebook_plan(job_id, timeout=None)

        # Resuming must never quietly lower what the run was started with.
        assert seen and all(value == 900.0 for value in seen)

    def test_a_read_timeout_is_recoverable_as_an_interruption(
        self, temp_db, model,
    ):
        import requests.exceptions as req_exc

        book = _make_book(temp_db)
        state = {"calls": 0}

        def batch(payload):
            state["calls"] += 1
            if state["calls"] > 1:
                raise req_exc.Timeout("read timed out")
            return _entries_for(payload["batch"])

        model(_plan_of(outline_count=8), batch)
        plan = importers.generate_lorebook_plan(book, "expand", timeout=300)

        assert plan["_job"]["status"] == "interrupted"
        assert plan["_job"]["resumable"] is True
        assert len(plan["entry_ops"]) == importers.LORE_GEN_ENTRY_BATCH

    @pytest.mark.parametrize(
        "given,expected",
        [
            (None, None),
            (0, None),
            ("", None),
            ("not a number", None),
            (5, providers.READ_TIMEOUT_MIN),
            (999999, providers.READ_TIMEOUT_MAX),
            ("450", 450.0),
        ],
    )
    def test_the_value_is_clamped_not_trusted(self, given, expected):
        assert providers.clamp_read_timeout(given) == expected

    def test_the_override_does_not_leak_out_of_its_block(self):
        with providers.request_timeout(600):
            assert providers.read_timeout_override.get() == 600.0
        assert providers.read_timeout_override.get() is None

    def test_the_override_is_reset_even_when_the_block_raises(self):
        with pytest.raises(RuntimeError):
            with providers.request_timeout(600):
                raise RuntimeError("boom")
        assert providers.read_timeout_override.get() is None

    def test_the_request_timeout_tuple_reflects_the_override(self):
        assert providers._request_timeout() == providers.REQUEST_TIMEOUT
        with providers.request_timeout(1800):
            connect, read = providers._request_timeout()
            assert connect == providers.REQUEST_TIMEOUT[0]
            assert read == 1800.0
            assert providers._httpx_timeout().read == 1800.0


class TestBadInput:
    def test_generating_for_a_missing_book_raises_before_any_model_call(
        self, temp_db, model,
    ):
        fake = model(_plan_of(outline_count=1))

        with pytest.raises(ValueError, match="not found"):
            importers.generate_lorebook_plan(9999, "expand")

        assert fake.structure_calls == []

    def test_resuming_a_missing_job_raises(self, temp_db):
        with pytest.raises(ValueError, match="not found"):
            importers.resume_lorebook_plan(4242)

    def test_resuming_a_run_whose_book_was_deleted_raises(self, temp_db, model):
        book = _make_book(temp_db)
        model(_dropped_connection)
        with pytest.raises(importers.LoreGenError) as excinfo:
            importers.generate_lorebook_plan(book, "expand")
        job_id = excinfo.value.job_id

        # The FK cascade removes the job with the book, so the job itself is
        # gone -- the point is that resume reports it instead of crashing.
        temp_db.qi("DELETE FROM lorebooks WHERE id=?", (book,))

        with pytest.raises(ValueError):
            importers.resume_lorebook_plan(job_id)
