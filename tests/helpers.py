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
import os
import tempfile


def fast_tmp_dir():
    """A RAM-backed directory for test databases, where the platform has one.

    ``db.init()`` is fsync-bound, not compute-bound: ``executescript(SCHEMA)``
    auto-commits ~117 DDL statements (53 tables, 64 indexes, FTS5 virtuals,
    triggers) against a brand-new file, and pays a flush for each. That single
    call was the dominant cost of the whole suite -- 159 of 252 test files
    request ``temp_db``, and their test BODIES run in 0.02--0.10s against a
    setup measured at 0.2s idle and 1.2--1.6s on a loaded checkout.

    Measured here, 13 database-backed tests: 2.93s on disk, 0.61s on tmpfs.
    Nothing about the database changes -- same schema, same WAL, same
    isolation, same per-test file. Only the storage backing moves, so a test
    cannot tell the difference; the suite just stops waiting on the platter.

    Returns None where no tmpfs exists (macOS, Windows), which falls back to
    tempfile's own default. Correct everywhere, fast where it can be.
    ``ENGINE_TEST_TMPDIR`` overrides, for a host where /dev/shm is too small.

    It lives HERE rather than in `conftest.py` because a test file that builds
    its own database has to be able to name it. Two did not, and paid the
    platter for a full `db.init()` -- in the fast tier, which is documented as
    database-independent.
    """
    override = os.environ.get("ENGINE_TEST_TMPDIR")
    if override:
        return override
    if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
        return "/dev/shm"
    return None


TMP_DIR = fast_tmp_dir()


def scratch_db_path():
    """A path for a database a test will create itself, on tmpfs where there is
    one. The file is removed immediately: `db.init()` wants to make it."""
    fd, path = tempfile.mkstemp(suffix=".db", dir=TMP_DIR)
    os.close(fd)
    os.remove(path)
    return path


def remove_scratch_db(path):
    """Delete a scratch database and the WAL/SHM sidecars it leaves behind.

    Ask forgiveness, not permission. `if exists(): remove()` is a race, and it
    lost once in a pinned-stack run: `FileNotFoundError: /dev/shm/....db-wal`
    in teardown, one error out of 8,450 tests, gone on a re-run. The engine
    keeps daemon threads alive across a test -- `memory_write`'s embedding
    repair loop is one -- and SQLite checkpoints and unlinks a `-wal` on its
    own schedule, so the file can go between the check and the removal. A
    teardown that fails because something ALREADY did its job is noise that
    reads exactly like a real failure.
    """
    for leftover in (path, path + "-wal", path + "-shm"):
        try:
            os.remove(leftover)
        except FileNotFoundError:
            pass


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


#: Every seam a model call passes through, at the module that DEFINES it.
#: `_agent_json` is the strict validated-JSON path every state-mutating stage
#: uses; `complete_validated_json` is what it calls; `chat_complete` is the
#: provider call under both.
MODEL_SEAMS = (
    ("agents.common", "_agent_json"),
    ("llm.llm_quality", "complete_validated_json"),
    ("llm.providers", "chat_complete"),
)

#: Only engine packages are swept. A third-party module that happens to hold a
#: same-named attribute is not a model call.
_SEAM_PACKAGES = ("agents", "llm", "core", "world", "mind", "story",
                  "dressing", "persist", "web")


def forbid_model_calls(monkeypatch=None, *,
                       reason="a model call was attempted"):
    """Make any model call raise, in every module that can reach one.

    Patching the DEFINING module is not enough and was the defect this
    replaces: every role module binds the seam into its own globals at import
    (`from .common import _agent_json`), so `monkeypatch.setattr(common,
    "_agent_json", boom)` leaves `mapping`, `narration`, `background` and the
    Director calling the original. Two composer test files carried that
    fixture as `autouse`, guarding nothing, and the modules they exercise do
    not import the seam at all -- so no positive control was possible either.

    This rebinds each seam wherever the ORIGINAL object is currently bound,
    which is the set of readers by definition, and it patches the DEFINING
    module first -- which covers the other order too: a role module imported
    after this runs copies the raising version into its globals. Returns the
    list of bindings, so a test can assert the net covers something rather
    than trusting that it does. Pass a `monkeypatch` to have it undone after
    the test; a driver script calls it with none.
    """
    import importlib
    import sys

    set_attr = setattr if monkeypatch is None else monkeypatch.setattr

    def _boom(*args, **kwargs):
        raise AssertionError(reason)

    patched = []
    for module_name, attr in MODEL_SEAMS:
        try:
            origin = importlib.import_module(module_name)
        except ImportError:  # pragma: no cover - a tree without the seam
            continue
        original = getattr(origin, attr, None)
        if original is None:
            continue
        for module in list(sys.modules.values()):
            name = getattr(module, "__name__", "")
            if not name.startswith(_SEAM_PACKAGES):
                continue
            if getattr(module, attr, None) is original:
                set_attr(module, attr, _boom)
                patched.append((name, attr))
    return patched


def patch_seam(monkeypatch, module_name, attr, replacement):
    """Rebind one imported seam wherever the ORIGINAL is bound, not only where
    it is defined.

    The same defect `forbid_model_calls` was written for, in a different
    package and found the same way. `mind/memory.py` is now a facade over
    twelve `mind/memory_*` modules, and `embed_texts_meta` is imported by NAME
    into eight of them -- so `monkeypatch.setattr(memory, "embed_texts_meta",
    fake)` rebinds a name no code in the facade reads, and all eight readers
    go on calling the provider. Twelve tests failed loudly the moment those
    readers moved. The ones that would NOT have failed are why this exists
    instead of eight enumerated module names, which go stale on the next move
    and go stale silently.

    Returns the `(module, attr)` bindings it replaced, and raises when that
    list is empty: a seam matching nothing is a typo or a rename, and patching
    nothing quietly is the whole failure being fixed.

    For a test making a claim about ONE reader -- that a particular module
    calls a particular thing -- patch that module by name and say so. This is
    for the commoner case of a test that only means "no real call happens
    here".
    """
    import importlib
    import sys

    origin = importlib.import_module(module_name)
    original = getattr(origin, attr)
    patched = []
    monkeypatch.setattr(origin, attr, replacement)
    patched.append((module_name, attr))
    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if not name.startswith(_SEAM_PACKAGES) or name == module_name:
            continue
        if getattr(module, attr, None) is original:
            monkeypatch.setattr(module, attr, replacement)
            patched.append((name, attr))
    if not patched:  # pragma: no cover - defended, never reached
        raise AssertionError(
            "patch_seam(%r, %r) matched no binding" % (module_name, attr))
    return patched


def patch_provider_seam(monkeypatch, attr, replacement):
    """`patch_seam` for the `llm.providers` names other packages import by name.

    `embed_texts`, `embed_texts_meta`, `embedding_model_key` and
    `chat_complete` are each bound into several `mind/memory_*` modules, and
    which ones depends on the path under test -- the consolidator's
    `chat_complete` is in `memory_summaries`, the write path's
    `embed_texts_meta` is in `memory_write`, and a checkpoint restore crosses
    four modules in one call. A test that does not care which calls this; a
    test that does care names its module.
    """
    return patch_seam(monkeypatch, "llm.providers", attr, replacement)
