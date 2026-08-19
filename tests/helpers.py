"""Plain helpers shared by test modules, imported by name.

Not in `conftest.py`, and that is the point. pytest imports a conftest itself,
under a name of its own choosing; a test module that imports the same file a
second way (`from tests.conftest import ...`) gets a SECOND module object, so
every import-time side effect runs again and only one copy's fixtures are
registered. `tests/conftest.py` opens a scratch database at import, and the
second copy's had no owner and no teardown -- one leaked 516KB file in
/dev/shm per suite run, 164 of them by the time anyone counted.

Fixtures and hooks belong in `conftest.py`, where pytest delivers them without
an import. Anything a test must NAME belongs here.
"""

from __future__ import annotations

import json


def fanout_resolve_agent(output, *, per_step=None, calls=None):
    """A fake `agents.director._agent_json` that serves a whole-beat resolve
    output THROUGH the specialist fan-out.

    The Director's delegated channels are answered by their owners: a
    specialist's reply owns the channels it was granted, so a fixture that
    hands the prose author a complete `state_diff` has those channels
    replaced by whatever each specialist said -- which, for a fake that
    returns one shape to every call, is nothing. Position diffs vanished,
    room edits vanished, and a test about the movement backstop failed on a
    KeyError that had nothing to do with movement.

    So this slices the output the way the engine does. The prose author gets
    it verbatim; each specialist gets its own channels lifted out of
    `state_diff` to the TOP level, which is the shape a specialist emits.
    That keeps a fixture free to say "the Director decided X" without also
    having to say which hand carries it.

    `per_step` overrides any step key outright; `calls` collects
    (step_key, payload) when a test wants to count.
    """
    from agents.director import SPECIALISTS

    diff = (output or {}).get("state_diff") or {}
    sliced = {}
    for spec in SPECIALISTS.values():
        patch = {ch: diff[ch] for ch in spec["channels"] if ch in diff}
        if patch:
            sliced[spec["step_key"]] = patch
    canned = {**sliced, **(per_step or {})}

    def fake(role, step_key, system, payload, **kw):
        if calls is not None:
            calls.append((step_key, payload))
        if step_key in canned:
            return json.loads(json.dumps(canned[step_key]))
        if step_key == "director_resolve":
            return json.loads(json.dumps(output or {}))
        return {}
    return fake
