"""The HTTP surface of resumable lorebook-tree generation.

`tests/test_lore_gen_resume.py` pins the recovery behaviour itself. These pin
the half that faces the browser, because the recovery only works if the wiring
does:

* the generator can ask "is there anything to recover for this book?" and get an
  answer that survived the request that created it,
* resume and discard reach the right job and refuse the wrong one,
* applying a plan retires its job, so finished work stops being offered as
  unfinished, and
* a raised timeout actually travels from the request body to the model call.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest
from story import importers


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post(
            "/api/auth/setup",
            json={"username": "host", "password": "pw12345"},
        )
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


@pytest.fixture
def book(temp_db):
    return temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
        ("Canon", None, "general"),
    )


def _stub_model(monkeypatch, outline_count=4, fail_batches=False, seen=None):
    def fake(role, system, user, **kwargs):
        payload = json.loads(user)
        if seen is not None:
            seen.append(payload)

        if payload.get("stage") == "structure":
            return json.dumps({
                "analysis": {"themes": ["salt"]},
                "book_ops": [],
                "link_ops": [],
                "entry_ops": [],
                "entry_outline": [
                    {"book_id": payload["selected_book_id"],
                     "title": f"Subject {i}", "keys": f"subject{i}",
                     "category": "other", "focus": "cover it"}
                    for i in range(outline_count)
                ],
            })

        if fail_batches:
            raise httpx.ConnectError("connection reset by peer")

        return json.dumps({
            "entry_ops": [
                {"op": "create", "outline_index": stub["outline_index"],
                 "book_id": stub["book_id"], "keys": stub["keys"],
                 "title": stub["title"], "category": "other",
                 "content": f"Body of {stub['title']}."}
                for stub in payload["batch"]
            ]
        })

    monkeypatch.setattr(importers, "chat_complete", fake)


class TestGeneratePlanRoute:
    def test_it_returns_the_plan_with_its_job(self, client, book, monkeypatch):
        _stub_model(monkeypatch, outline_count=4)

        response = client.post(
            f"/api/lorebooks/{book}/generate_plan",
            json={"prompt": "expand the salt roads", "entry_target": 4},
        )

        assert response.status_code == 200, response.text
        plan = response.json()
        assert len(plan["entry_ops"]) == 4
        assert plan["_job"]["status"] == "ready"
        assert plan["_job"]["id"]

    def test_a_missing_book_is_a_404(self, client, monkeypatch):
        _stub_model(monkeypatch)
        response = client.post("/api/lorebooks/999999/generate_plan", json={})
        assert response.status_code == 404


class TestRecoveryLookupRoute:
    def test_it_reports_nothing_when_there_is_nothing_to_recover(
        self, client, book,
    ):
        response = client.get(f"/api/lorebooks/{book}/generate_job")
        assert response.status_code == 200
        assert response.json()["job"] is None

    def test_a_finished_plan_outlives_the_request_that_made_it(
        self, client, book, monkeypatch,
    ):
        _stub_model(monkeypatch, outline_count=2)
        client.post(f"/api/lorebooks/{book}/generate_plan", json={})

        # The closed-tab case: a SEPARATE request finds the plan intact.
        job = client.get(f"/api/lorebooks/{book}/generate_job").json()["job"]
        assert job["restorable"] is True
        assert len(job["plan"]["entry_ops"]) == 2

    def test_an_interrupted_run_is_offered_for_resume(
        self, client, book, monkeypatch,
    ):
        _stub_model(monkeypatch, outline_count=4, fail_batches=True)
        failed = client.post(f"/api/lorebooks/{book}/generate_plan", json={})
        assert failed.status_code == 502
        assert "resumable" in failed.json()["detail"]

        job = client.get(f"/api/lorebooks/{book}/generate_job").json()["job"]
        assert job["resumable"] is True
        assert job["entries_total"] == 4
        assert job["entries_done"] == 0


class TestResumeRoute:
    def test_it_finishes_an_interrupted_run(self, client, book, monkeypatch):
        _stub_model(monkeypatch, outline_count=4, fail_batches=True)
        client.post(f"/api/lorebooks/{book}/generate_plan", json={})
        job_id = client.get(
            f"/api/lorebooks/{book}/generate_job"
        ).json()["job"]["id"]

        _stub_model(monkeypatch, outline_count=4)
        response = client.post(f"/api/lore_gen_jobs/{job_id}/resume", json={})

        assert response.status_code == 200, response.text
        plan = response.json()
        assert len(plan["entry_ops"]) == 4
        assert plan["_job"]["status"] == "ready"

    def test_resuming_a_missing_job_is_a_404(self, client):
        response = client.post("/api/lore_gen_jobs/4242/resume", json={})
        assert response.status_code == 404

    def test_resuming_a_discarded_job_is_a_409(self, client, book, monkeypatch):
        _stub_model(monkeypatch, outline_count=2)
        job_id = client.post(
            f"/api/lorebooks/{book}/generate_plan", json={},
        ).json()["_job"]["id"]

        client.delete(f"/api/lore_gen_jobs/{job_id}")
        response = client.post(f"/api/lore_gen_jobs/{job_id}/resume", json={})

        assert response.status_code == 409

    def test_it_works_without_a_body(self, client, book, monkeypatch):
        _stub_model(monkeypatch, outline_count=2)
        job_id = client.post(
            f"/api/lorebooks/{book}/generate_plan", json={},
        ).json()["_job"]["id"]

        # The UI omits the timeout unless the field was edited, so an empty
        # body must not be a 422.
        response = client.post(f"/api/lore_gen_jobs/{job_id}/resume")
        assert response.status_code == 200, response.text


class TestDiscardRoute:
    def test_it_stops_the_run_being_offered(self, client, book, monkeypatch):
        _stub_model(monkeypatch, outline_count=2)
        job_id = client.post(
            f"/api/lorebooks/{book}/generate_plan", json={},
        ).json()["_job"]["id"]

        assert client.delete(f"/api/lore_gen_jobs/{job_id}").status_code == 200
        assert client.get(
            f"/api/lorebooks/{book}/generate_job"
        ).json()["job"] is None

    def test_discarding_a_missing_job_is_a_404(self, client):
        assert client.delete("/api/lore_gen_jobs/4242").status_code == 404


class TestApplyRetiresTheJob:
    def test_applying_a_plan_stops_it_being_offered_as_recoverable(
        self, client, book, monkeypatch,
    ):
        _stub_model(monkeypatch, outline_count=2)
        plan = client.post(
            f"/api/lorebooks/{book}/generate_plan", json={},
        ).json()
        job_id = plan["_job"]["id"]

        response = client.post(
            f"/api/lorebooks/{book}/apply_plan",
            json={
                "plan": {
                    "book_ops": [],
                    "link_ops": [],
                    "entry_ops": plan["entry_ops"],
                },
                "job_id": job_id,
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["result"]["entries_created"] == 2
        # Its entries are real lore now; offering to resume it would be wrong.
        assert client.get(
            f"/api/lorebooks/{book}/generate_job"
        ).json()["job"] is None

    def test_applying_without_a_job_id_still_works(
        self, client, book, monkeypatch,
    ):
        _stub_model(monkeypatch, outline_count=1)
        plan = client.post(
            f"/api/lorebooks/{book}/generate_plan", json={},
        ).json()

        response = client.post(
            f"/api/lorebooks/{book}/apply_plan",
            json={"plan": {"book_ops": [], "link_ops": [],
                           "entry_ops": plan["entry_ops"]}},
        )

        assert response.status_code == 200, response.text


class TestTimeoutTravelsFromTheRequest:
    def test_a_raised_timeout_is_recorded_on_the_run(
        self, client, book, monkeypatch,
    ):
        _stub_model(monkeypatch, outline_count=2)

        plan = client.post(
            f"/api/lorebooks/{book}/generate_plan",
            json={"timeout": 1200},
        ).json()

        assert plan["_job"]["params"]["timeout"] == 1200.0

    def test_an_absurd_timeout_is_clamped_not_trusted(
        self, client, book, monkeypatch,
    ):
        _stub_model(monkeypatch, outline_count=1)

        plan = client.post(
            f"/api/lorebooks/{book}/generate_plan",
            json={"timeout": 10 ** 9},
        ).json()

        from llm import providers
        assert plan["_job"]["params"]["timeout"] == providers.READ_TIMEOUT_MAX

    def test_a_resume_can_raise_it(self, client, book, monkeypatch):
        _stub_model(monkeypatch, outline_count=4, fail_batches=True)
        client.post(f"/api/lorebooks/{book}/generate_plan",
                    json={"timeout": 300})
        job_id = client.get(
            f"/api/lorebooks/{book}/generate_job"
        ).json()["job"]["id"]

        _stub_model(monkeypatch, outline_count=4)
        plan = client.post(
            f"/api/lore_gen_jobs/{job_id}/resume",
            json={"timeout": 1800},
        ).json()

        assert plan["_job"]["params"]["timeout"] == 1800.0
