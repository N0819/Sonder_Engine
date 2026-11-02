"""CI reports every gate, every run, without making one wait for another.

`make check-fast` ran as ONE step, and `make` stops at the first prerequisite
that fails: every push from 2026-09-28 (8f408adf) to 2026-10-05 stopped at
`make structure` and ran no test at all -- sixty red runs -- and a Pydantic-1
regression stayed hidden behind the same structure failure
(tooling_gate F7). And `needs: fast`, with the `always()` guard added so a
failed matrix leg could not skip the other jobs, bought only delay: run
41366860777 took 14:52 where the jobs side by side take ~10:30 (F13).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _jobs(text):
    """`{job: [its lines]}`, read by indentation -- the workflow's own shape,
    without a YAML dependency the suite does not otherwise have."""
    jobs, current, inside = {}, None, False
    for line in text.splitlines():
        if line.startswith("jobs:"):
            inside = True
            continue
        if not inside:
            continue
        if line.startswith("  ") and not line.startswith("   ") \
                and line.strip().endswith(":") and not line.strip().startswith("#"):
            current = line.strip()[:-1]
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return jobs


def _steps(lines):
    """Each `- name:` step of a job as `{key: value}` for its scalar keys."""
    steps = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            steps.append({})
            stripped = stripped[2:]
        if steps and ":" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition(":")
            steps[-1].setdefault(key.strip(), value.strip())
    return steps


def test_no_job_waits_for_another():
    for job, lines in _jobs(WORKFLOW.read_text(encoding="utf-8")).items():
        assert not [line for line in lines
                    if line.strip().startswith("needs:")], job


def test_each_gate_is_its_own_step_and_runs_after_a_failure():
    jobs = _jobs(WORKFLOW.read_text(encoding="utf-8"))
    steps = _steps(jobs["fast"])
    runs = [step.get("run", "") for step in steps]
    for gate in ("make stack", "make compile", "make structure",
                 "make test-full"):
        assert gate in runs, (gate, runs)
        step = steps[runs.index(gate)]
        assert "!cancelled()" in step.get("if", ""), (
            "%s must report even when an earlier gate failed" % gate)
    assert "make check-fast" not in runs
