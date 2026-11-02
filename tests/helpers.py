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


def model_dict(model, **kwargs):
    """`model` as a plain dict on either Pydantic major the engine declares
    (`pydantic>=1.10.13,<3`): `model_dump` on 2.x, `dict` on 1.x, the same
    output. A test that called `model_dump()` itself passed on the shipped
    2.x and failed CI's Pydantic 1 job, which nobody runs locally -- ten
    tests, red from 2026-09-27 under a structure failure that hid them.
    `tools/project_check.py` (`check_tests_reach_pydantic_through_helpers`)
    keeps the 2.x-only names here; `llm.schemas` owns the engine's branch."""
    dump = getattr(model, "model_dump", None)
    return dump(**kwargs) if dump is not None else model.dict(**kwargs)


def model_fields_of(model_cls):
    """A model class's declared fields by name, on either major."""
    from llm.schemas import _fields
    return _fields(model_cls)


def model_from(model_cls, data):
    """`data` validated into `model_cls`, on either major."""
    from llm.schemas import _validate
    return _validate(model_cls, data)


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


#: Every door a model, or any provider on the network, is reached through --
#: at the module that DEFINES it. ONE list. There were two, which already
#: disagreed: `MODEL_SEAMS` here named three doors and `tests/model_seams.py`'s
#: `MODEL_DOORS` five, so `forbid_model_calls` left both embedding doors open,
#: and neither named the decision model's post (`llm/decisions.py`, which
#: arrived after both lists), the async completion, the two image calls, the
#: model listing or the research fetches (2026-11-01). `tests/model_seams.py`
#: imports this tuple, and `tests/test_model_seams.py` opens every door in it.
#: A door the list forgets is still refused by the network floor in
#: `tests/conftest.py`; the list is what names WHICH door opened.
MODEL_DOORS = (
    ("agents.common_llm", "_agent_json"),
    ("llm.llm_quality", "complete_validated_json"),
    ("llm.providers", "chat_complete"),
    ("llm.providers", "chat_complete_async"),
    ("llm.providers", "embed_texts"),
    ("llm.providers", "embed_texts_meta"),
    ("llm.providers", "generate_image"),
    ("llm.providers", "edit_image"),
    ("llm.providers", "list_models"),
    ("llm.decisions", "_post"),
    ("llm.research_providers", "search"),
    ("llm.research_providers", "fetch"),
)

#: The engine's own packages: `ENGINE_PACKAGE_ROOTS` in tools/project_check.py,
#: which `tests/test_model_seams.py` holds this equal to. Only these are swept
#: for a binding to rebind -- a test module or a third-party one holding the
#: same object is not a path the engine can take. `dressing` was missing from
#: one of the two lists this replaces and three roots from both.
ENGINE_PACKAGES = ("core", "llm", "world", "mind", "story", "dressing",
                   "persist", "web", "agents", "extension_runtime",
                   "language_runtime", "language_adapters")


def _engine_modules():
    """`(name, module)` for every engine module imported so far."""
    import sys

    for name, module in list(sys.modules.items()):
        if module is not None and name.split(".")[0] in ENGINE_PACKAGES:
            yield name, module


def seal_doors(set_attr, refusal_for, doors=MODEL_DOORS):
    """Rebind every door, and every engine binding of the same object under
    ANY name, to the refusal `refusal_for(door)` returns.

    Identity, never the name: `from llm.providers import chat_complete as
    complete` is a reader too, and an unrelated module's same-named attribute
    is not one. The DEFINING module is rebound first, which covers the other
    order as well: a module imported after this copies the refusal into its
    globals. Returns `(bindings, doors)`: every `(module, name)` rebound, and
    the doors that were found to seal.
    """
    import importlib

    found = {}
    bindings = []
    sealed = []
    for module_path, attr in doors:
        try:
            origin = importlib.import_module(module_path)
        except ImportError:  # pragma: no cover - a tree without the door
            continue
        original = getattr(origin, attr, None)
        if original is None:
            continue
        door = "%s.%s" % (module_path, attr)
        refusal = refusal_for(door)
        found[id(original)] = (original, refusal)
        set_attr(origin, attr, refusal)
        bindings.append((module_path, attr))
        sealed.append(door)
    for name, module in _engine_modules():
        for held_as, value in list(vars(module).items()):
            entry = found.get(id(value))
            if entry is not None and value is entry[0]:
                set_attr(module, held_as, entry[1])
                bindings.append((name, held_as))
    return bindings, sealed


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

    Every door in `MODEL_DOORS` is sealed, wherever the ORIGINAL object is
    currently bound (`seal_doors`), which is the set of readers by definition.
    Returns the list of bindings, so a test can assert the net covers
    something rather than trusting that it does. Pass a `monkeypatch` to have
    it undone after the test; a driver script calls it with none.
    """
    set_attr = setattr if monkeypatch is None else monkeypatch.setattr

    def refusal_for(door):
        def _boom(*args, **kwargs):
            raise AssertionError("%s (through %s)" % (reason, door))
        return _boom

    bindings, _sealed = seal_doors(set_attr, refusal_for)
    return bindings


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

    Returns the `(module, attr)` bindings it replaced. A typo raises before
    anything is patched, as the `AttributeError` reading the original gives.
    And it RAISES when no engine module but `module_name` itself holds the
    object: the sweep then added nothing to a plain `monkeypatch.setattr` --
    and when `module_name` is a facade, the one binding it rebound is one no
    code reads, which is the inert patch this helper exists to prevent. That
    raise used to be `if not patched`, after a line that always appended the
    origin, so it could not fire (2026-11-01). Every one of the 177 static
    call sites then in `tests/` found a second holder.

    For a test making a claim about ONE reader -- that a particular module
    calls a particular thing -- patch that module by name and say so. This is
    for the commoner case of a test that only means "no real call happens
    here".
    """
    import importlib

    origin = importlib.import_module(module_name)
    original = getattr(origin, attr)
    monkeypatch.setattr(origin, attr, replacement)
    patched = [(module_name, attr)]
    for name, module in _engine_modules():
        if module is origin:
            continue
        if getattr(module, attr, None) is original:
            monkeypatch.setattr(module, attr, replacement)
            patched.append((name, attr))
    if len(patched) == 1:
        raise AssertionError(
            "patch_seam(%r, %r) found no engine module but %s holding that "
            "object, so it rebound one binding -- and if %s is a facade, one "
            "no code reads. Patch the module whose reader the test means with "
            "monkeypatch.setattr, and say which." % (
                module_name, attr, module_name, module_name))
    return patched


class NetworkRefused(AssertionError):
    """A test reached for a host that is not this machine."""


#: Names that are this machine without asking anyone.
_LOCAL_NAMES = frozenset({"", "localhost", "localhost.localdomain",
                          "ip6-localhost", "ip6-loopback"})


def _ip(host):
    """`host` as an address object, or None when it is a name."""
    import ipaddress

    try:
        return ipaddress.ip_address(str(host).strip("[]").split("%", 1)[0])
    except ValueError:
        return None


def is_local_host(host) -> bool:
    """Whether connecting to `host` (a name, an address, or None) stays on
    this machine: loopback, the unspecified address, or a name that is
    defined to mean the machine itself."""
    if host is None:
        return True
    if isinstance(host, (bytes, bytearray)):
        host = bytes(host).decode("ascii", "ignore")
    name = str(host).strip().rstrip(".").casefold()
    if name.strip("[]") in _LOCAL_NAMES or name.endswith(".localhost"):
        return True
    address = _ip(name)
    return bool(address and (address.is_loopback or address.is_unspecified))


def install_network_guard(monkeypatch):
    """Refuse every connection that would leave this machine, for one test.

    The floor under the door list (`MODEL_DOORS`): it does not depend on the
    list being complete, because it sits where every client library ends --
    `socket.socket.connect`/`connect_ex`, and `socket.getaddrinfo` for a name
    that would need a lookup. Loopback and `AF_UNIX` pass, so a test serving
    the app on 127.0.0.1 still runs. Returns the list each refusal is recorded
    in as `(thread name, host:port)`, so a refusal the engine swallowed is
    still seen (`tests/conftest.py` fails the test on it).

    Until 2026-11-01 the suite was offline only because a fresh scratch
    database holds no provider row; nothing refused a connection.
    """
    import socket
    import threading

    attempts = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def refuse(where):
        attempts.append((threading.current_thread().name, where))
        raise NetworkRefused(
            "a test reached the network (%s). Stub the call -- "
            "tests.helpers.MODEL_DOORS names the doors -- or mark the test "
            "@pytest.mark.network if reaching the network is its point."
            % where)

    def check(sock, address):
        family = getattr(sock, "family", None)
        if family is not None and family == getattr(socket, "AF_UNIX", None):
            return
        if isinstance(address, (tuple, list)) and address:
            if not is_local_host(address[0]):
                port = address[1] if len(address) > 1 else ""
                refuse("%s:%s" % (address[0], port))

    def connect(self, address):
        check(self, address)
        return real_connect(self, address)

    def connect_ex(self, address):
        check(self, address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, port, *args, **kwargs):
        # An address needs no lookup; `connect` judges where it goes.
        if not is_local_host(host) and _ip(host) is None:
            refuse("%s:%s, a name lookup" % (host, port))
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return attempts


def engine_contextvars():
    """Every module-level ContextVar of every engine module imported so far."""
    import contextvars

    found = []
    for name, module in _engine_modules():
        key = (name, id(module))
        held = _CONTEXTVARS_BY_MODULE.get(key)
        if held is None:
            held = [value for value in list(vars(module).values())
                    if isinstance(value, contextvars.ContextVar)]
            _CONTEXTVARS_BY_MODULE[key] = held
        found.extend(held)
    unique = []
    seen = set()
    for var in found:
        if id(var) not in seen:
            seen.add(id(var))
            unique.append(var)
    return unique


#: `(module name, module id) -> its ContextVars`, so the per-test reset reads
#: each module's namespace once rather than every test.
_CONTEXTVARS_BY_MODULE: dict = {}


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


class SSEFake:
    """A blocking-style fake response (`.status_code`, `.json()`, `.text`)
    served as the OpenAI SSE stream the provider layer now always reads.

    Every OpenAI-style call streams since 2026-09-14 (the silence clock in
    `providers._sse_openai` needs to see activity), so a test that fakes
    `_session().post` answers `stream=True` with this and keeps its canned
    completion unchanged."""

    def __init__(self, response):
        self._response = response
        self.status_code = getattr(response, "status_code", 200)
        self.text = getattr(response, "text", "")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def iter_lines(self):
        import json as _json
        payload = self._response.json()
        choice = (payload.get("choices") or [{}])[0] or {}
        message = choice.get("message") or {}
        delta = {key: value for key, value in message.items() if key != "role"}
        chunk = {"choices": [{"delta": delta,
                              "finish_reason": choice.get("finish_reason")}]}
        if payload.get("model"):
            chunk["model"] = payload["model"]
        yield ("data: " + _json.dumps(chunk)).encode("utf-8")
        if payload.get("usage") is not None:
            yield ("data: " + _json.dumps(
                {"choices": [], "usage": payload["usage"]})).encode("utf-8")
        yield b"data: [DONE]"


def streamed(response, stream=None):
    """The response a fake `post` should return: the stream shape when the
    caller asked to stream, the blocking shape otherwise."""
    return SSEFake(response) if stream else response

