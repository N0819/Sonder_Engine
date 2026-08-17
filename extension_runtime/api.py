"""The facade one installed extension is handed, and nothing else.

An extension never receives a `PipelineContext`, a database handle, or another
character's private view.  It receives one `SonderExtensionAPI` bound to its own
id, and every durable thing it can touch is namespaced under `ext:<id>` -- world
KV for per-story state, the settings table for install-scoped config, and a
single reserved key inside `chat_chars.state` for per-character state.  That
namespacing is the whole persistence story: all three of those already ride
checkpoints, archives and branches wholesale, so an extension inherits
rewind/export/clone without a schema change or a line in DATABASE.md's checklist.

The write gate on per-turn state exists for the reason `docs/design/
EXTENSIONS_DESIGN.md` section 4 names: a write made mid-pipeline lands OUTSIDE the
turn's transaction, so a later domain failure rolls back everything except the
extension's write and a rerun then replays against state that never went away.
`state.set()` therefore only works inside an `on_turn_committed` hook, which runs
after the turn's facts are durable.  `set_now()` is the deliberate, named escape
hatch -- an extension that wants it has to say so.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re

_COMMIT_SCOPE = contextvars.ContextVar("sonder_ext_commit_scope", default=False)

# Every psychology-bearing key deterministic commit code writes into
# `chat_chars.state` (verified against commit.py's `st[...]` assignments).  Read
# only -- an extension gets to SEE a mind's settled state, never to author it.
PSYCHOLOGY_STATE_KEYS = (
    "active_state", "interior", "stance", "recent_tells", "tell_grounds",
    "active_hypotheses", "unbidden", "memory_ponder",
)


class ExtensionError(RuntimeError):
    """An extension asked for something the host will not do."""


def in_commit_scope() -> bool:
    return bool(_COMMIT_SCOPE.get())


def enter_commit_scope():
    return _COMMIT_SCOPE.set(True)


def leave_commit_scope(token) -> None:
    _COMMIT_SCOPE.reset(token)


# ---------------------------------------------------------------- state


class ExtState:
    """One JSON value an extension owns, at one namespaced storage key."""

    def __init__(self, label, reader, writer, *, gated):
        self.label = label
        self._read = reader
        self._write = writer
        self._gated = gated

    def get(self, default=None):
        value = self._read()
        return default if value is None else value

    def set(self, value):
        if self._gated and not in_commit_scope():
            raise ExtensionError(
                f"{self.label} may only be written from an on_turn_committed "
                "hook, where the turn's own writes have already landed. Use "
                "set_now(...) to write outside one anyway.")
        self._write(value)
        return value

    def set_now(self, value):
        """Write outside a committed-turn hook, accepting the consequences."""
        self._write(value)
        return value

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<ExtState {self.label}>"


def _world_state(ext_id, chat_id, *, gated=True):
    from db import wget, wset

    key = f"ext:{ext_id}"
    cid = int(chat_id)
    return ExtState(
        f"extension {ext_id!r} state for chat {cid}",
        lambda: wget(cid, key),
        lambda value: wset(cid, key, value),
        gated=gated,
    )


def _settings_state(ext_id):
    from db import get_setting, set_setting

    key = f"ext:{ext_id}"

    def read():
        raw = get_setting(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    return ExtState(
        f"extension {ext_id!r} settings",
        read,
        lambda value: set_setting(key, json.dumps(value)),
        gated=False,
    )


def _read_char_state(chat_id, char_id):
    """The character's whole engine-owned state dict, frame override first."""
    from db import active_frame_id, q

    frame_id = active_frame_id.get()
    row = q(
        "SELECT COALESCE(ccf.state, cc.state) AS state FROM chat_chars cc "
        "LEFT JOIN chat_char_frames ccf "
        "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id "
        " AND ccf.frame_id=? "
        "WHERE cc.chat_id=? AND cc.char_id=?",
        (frame_id, int(chat_id), int(char_id)), one=True,
    )
    if not row:
        raise ExtensionError(
            f"character {char_id} is not attached to chat {chat_id}")
    try:
        state = json.loads(row["state"] or "{}")
    except (TypeError, ValueError):
        state = {}
    return state if isinstance(state, dict) else {}


def _write_char_state(chat_id, char_id, mutate):
    """Read-modify-write through the engine's own helper.

    Never build a fresh dict: `chat_chars.state` carries active_state, interior,
    stance, the tell ledgers and the spatial memory, and a blind overwrite would
    delete a mind's whole history to store one extension's counter.
    """
    from db import active_frame_id
    from scene import set_char_state

    state = _read_char_state(chat_id, char_id)
    mutate(state)
    set_char_state(int(chat_id), int(char_id),
                   json.dumps(state, ensure_ascii=False),
                   frame_id=active_frame_id.get())


def _char_ext_state(ext_id, chat_id, char_id, *, gated=True):
    key = f"ext:{ext_id}"

    def read():
        return _read_char_state(chat_id, char_id).get(key)

    def write(value):
        def mutate(state):
            state[key] = value
        _write_char_state(chat_id, char_id, mutate)

    return ExtState(
        f"extension {ext_id!r} state for character {char_id} in chat {chat_id}",
        read, write, gated=gated,
    )


# ---------------------------------------------------------------- characters


class CharacterHandle:
    """One attached character, seen through an extension's namespace."""

    def __init__(self, api, chat_id, char_id, names):
        self._api = api
        self.chat_id = int(chat_id)
        self.char_id = int(char_id)
        self.names = tuple(names)

    @property
    def name(self):
        return self.names[0] if self.names else ""

    @property
    def state(self):
        return _char_ext_state(self._api.id, self.chat_id, self.char_id)

    def step_output(self, turn_idx=None):
        """This character's own decision step, latest or for one turn."""
        from db import q

        key = f"character:{self.char_id}"
        params = [self.chat_id, key]
        clause = ""
        if turn_idx is not None:
            clause = " AND t.idx=?"
            params.append(int(turn_idx))
        row = q(
            "SELECT s.turn_id AS turn_id FROM steps s "
            "JOIN turns t ON t.id=s.turn_id "
            "JOIN variants v ON v.step_id=s.id AND v.active=1 "
            f"WHERE t.chat_id=? AND s.key=?{clause} "
            "ORDER BY t.idx DESC LIMIT 1",
            tuple(params), one=True,
        )
        if not row:
            return None
        from agents.storage import active_content
        return active_content(row["turn_id"], key)

    def psychology(self):
        """Whatever settled psychology actually lives on this character.

        Deterministic commit code owns every one of these keys; this is a read
        of what it already wrote, never a second channel into a mind.  Absent fields
        are absent, not defaulted -- an extension must be able to tell "this
        character has never deliberated" from "this character is calm".
        """
        state = _read_char_state(self.chat_id, self.char_id)
        return {key: state[key] for key in PSYCHOLOGY_STATE_KEYS
                if key in state}

    def binding(self):
        return (self.state.get({}) or {}).get("binding")

    def request_bind(self, config=None):
        """Record that this extension wants to be attached to this character.

        Written immediately rather than through the committed-turn gate: a bind
        is a host/authoring action taken outside a running turn, and there is no
        turn transaction for it to be rolled back with.
        """
        current = self.state.get({}) or {}
        if not isinstance(current, dict):
            current = {}
        current["binding"] = dict(config or {}) if config is not None else {}
        self.state.set_now(current)
        return current["binding"]

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<Character {self.char_id} {self.name!r}>"


class CharacterAccess:
    """`api.characters` -- resolution that refuses to guess."""

    def __init__(self, api):
        self._api = api

    def _rows(self, chat_id):
        from character_schema import character_name_from_text
        from db import q

        rows = q(
            "SELECT ch.id AS id, ch.name AS name, "
            "COALESCE(cc.sheet, ch.sheet) AS sheet "
            "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
            "WHERE cc.chat_id=? ORDER BY ch.id",
            (int(chat_id),),
        )
        out = []
        for row in rows:
            names = []
            for candidate in (character_name_from_text(row["sheet"]),
                              row["name"]):
                candidate = str(candidate or "").strip()
                if candidate and candidate not in names:
                    names.append(candidate)
            out.append((int(row["id"]), names))
        return out

    def in_chat(self, chat_id):
        return [CharacterHandle(self._api, chat_id, char_id, names)
                for char_id, names in self._rows(chat_id)]

    def get(self, chat_id, ref):
        """Resolve an int char id or a display name to one handle.

        A name that matches two attached characters raises with both candidates
        rather than picking one.  Guessing here would silently point an
        extension's per-character state at the wrong mind and stay wrong
        forever, which is exactly the class of failure that only shows up fifty
        beats later.
        """
        rows = self._rows(chat_id)
        if isinstance(ref, bool):
            raise ExtensionError("character reference must be an id or a name")
        if isinstance(ref, int):
            for char_id, names in rows:
                if char_id == int(ref):
                    return CharacterHandle(self._api, chat_id, char_id, names)
            raise ExtensionError(
                f"character {int(ref)} is not attached to chat {chat_id}")
        wanted = str(ref or "").strip().casefold()
        if not wanted:
            raise ExtensionError("character reference must be an id or a name")
        matches = [(char_id, names) for char_id, names in rows
                   if any(name.casefold() == wanted for name in names)]
        if not matches:
            raise ExtensionError(
                f"no character named {ref!r} is attached to chat {chat_id}")
        if len(matches) > 1:
            listed = ", ".join(f"{char_id} ({names[0] if names else ''})"
                               for char_id, names in matches)
            raise ExtensionError(
                f"character name {ref!r} is ambiguous in chat {chat_id}: "
                f"{listed}. Reference the character by id.")
        char_id, names = matches[0]
        return CharacterHandle(self._api, chat_id, char_id, names)


# ---------------------------------------------------------------- stage view


class StepView:
    """The read-only slice of a running turn an extension stage receives.

    Deliberately NOT the `PipelineContext`.  A stage handed the real context is
    one line away from copying the Director's resolved truth into a character
    payload; this object exposes finished step OUTPUT and nothing that is still
    being assembled.  Built with getattr tolerance throughout, because
    `compute_step` is driven by stand-in contexts in tests and by extensions.
    """

    def __init__(self, ctx):
        self._ctx = ctx
        chat = getattr(ctx, "chat", None)
        turn = getattr(ctx, "turn", None)
        self.chat_id = getattr(chat, "id", None)
        self.turn_idx = getattr(turn, "idx", None)
        self.turn_id = getattr(turn, "id", None)
        self.frame_id = getattr(turn, "frame_id", None)

    def step(self, key):
        getter = getattr(self._ctx, "get", None)
        if not callable(getter):
            return None
        try:
            return getter(key)
        except Exception:
            return None

    @property
    def resolve(self):
        value = self.step("director_resolve")
        return value if isinstance(value, dict) else {}

    @property
    def state_diff(self):
        value = self.resolve.get("state_diff")
        return value if isinstance(value, dict) else {}

    @property
    def resolved_event(self):
        return str(self.resolve.get("resolved_event") or "")

    @property
    def dialogue_log(self):
        value = self.resolve.get("dialogue_log")
        return value if isinstance(value, list) else []


class CommitView:
    """What an `add_commit_domain` callback receives: a turn mid-transaction.

    The difference from `CommittedTurn` is the whole point of the seam. This
    runs INSIDE `_commit_all_locked`'s transaction, so a write made here is
    atomic with the turn's own -- if a later domain fails, this write is rolled
    back with everything else, which is exactly the ghost-state hazard the
    `ExtState` gate exists to prevent. State reached from here is therefore
    UNGATED: the transaction is the guarantee.
    """

    def __init__(self, api, ctx):
        self._api = api
        self._ctx = ctx
        chat = getattr(ctx, "chat", None)
        turn = getattr(ctx, "turn", None)
        self.chat_id = getattr(chat, "id", None)
        self.turn_idx = getattr(turn, "idx", None)
        self.turn_id = getattr(turn, "id", None)
        self.state = (_world_state(api.id, self.chat_id, gated=False)
                      if self.chat_id is not None else None)

    def char_state(self, char_id):
        return _char_ext_state(self._api.id, self.chat_id, char_id, gated=False)

    def step_content(self, key):
        getter = getattr(self._ctx, "get", None)
        if not callable(getter):
            return None
        try:
            return getter(key)
        except Exception:
            return None


class PayloadContext:
    """Identity handed to an `on_character_payload` hook alongside the payload.

    Deliberately thin: the hook already receives the assembled payload, which
    is the powerful object. This says WHOSE it is, so a hook can decide whether
    this is a mind it was installed to touch.
    """

    def __init__(self, api, ctx, char_id, names=()):
        self.api = api
        self.char_id = int(char_id)
        self.names = tuple(names)
        chat = getattr(ctx, "chat", None)
        turn = getattr(ctx, "turn", None)
        self.chat_id = getattr(chat, "id", None)
        self.turn_idx = getattr(turn, "idx", None)
        self.turn_id = getattr(turn, "id", None)
        self._ctx = ctx

    @property
    def name(self):
        return self.names[0] if self.names else ""

    def step(self, key):
        getter = getattr(self._ctx, "get", None)
        if not callable(getter):
            return None
        try:
            return getter(key)
        except Exception:
            return None


class Request:
    """One call to an extension's own HTTP route.

    A plain object rather than the framework's request: an extension that binds
    to Starlette's types inherits every future upgrade of them, and the whole
    point of the facade is that it does not.
    """

    def __init__(self, method, path, query=None, body=None):
        self.method = str(method or "GET").upper()
        self.path = str(path or "")
        self.query = dict(query or {})
        self.body = body

    @property
    def chat_id(self):
        """`?chat_id=` as an int, or None -- the parameter almost every route wants."""
        try:
            return int(self.query.get("chat_id"))
        except (TypeError, ValueError):
            return None

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<Request {self.method} {self.path}>"


class CommittedTurn:
    """What an `on_turn_committed` hook receives: a durable turn, and a pen."""

    def __init__(self, api, ctx):
        self._ctx = ctx
        chat = getattr(ctx, "chat", None)
        turn = getattr(ctx, "turn", None)
        self.chat_id = getattr(chat, "id", None)
        self.turn_idx = getattr(turn, "idx", None)
        self.turn_id = getattr(turn, "id", None)
        self.state = (_world_state(api.id, self.chat_id)
                      if self.chat_id is not None else None)

    def step_content(self, key):
        getter = getattr(self._ctx, "get", None)
        if callable(getter):
            try:
                value = getter(key)
            except Exception:
                value = None
            if value is not None:
                return value
        if self.turn_id is None:
            return None
        try:
            from agents.storage import active_content
            return active_content(self.turn_id, key)
        except Exception:
            return None


# ---------------------------------------------------------------- the facade


_STAGE_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_ANCHOR_MODES = ("after", "before")


class SonderExtensionAPI:
    """Everything one extension can reach, bound to its own id."""

    def __init__(self, ext_id, data_path):
        self.id = str(ext_id)
        self.data_path = data_path
        self.log = logging.getLogger(f"ext.{self.id}")
        self.characters = CharacterAccess(self)

    # -- pipeline

    def add_stage(self, key, *, anchor, label=None, handler=None,
                  on_error="warn"):
        """Register a stage AND where it goes -- the two halves together.

        `runtime.register_step` has always covered the handler half; the plan
        half is what forced a third party to edit `build_plan` by hand, which is
        the one thing this prototype exists to make unnecessary.
        """
        key = str(key or "").strip()
        if not _STAGE_KEY.fullmatch(key):
            raise ExtensionError(f"invalid extension stage key: {key!r}")
        if not callable(handler):
            raise ExtensionError(
                f"extension stage {key!r} needs a callable handler")
        mode, _, core = str(anchor or "").partition(":")
        if mode not in _ANCHOR_MODES or not core.strip():
            raise ExtensionError(
                f"stage {key!r} anchor must be 'after:<step>' or "
                f"'before:<step>', not {anchor!r}")
        if on_error not in ("warn", "fail"):
            raise ExtensionError(
                f"stage {key!r} on_error must be 'warn' or 'fail'")

        full_key = f"ext:{self.id}:{key}"
        wrapper = _stage_wrapper(self, key, handler, on_error)

        from . import _record_stage
        _record_stage(self.id, key, full_key, anchor=f"{mode}:{core.strip()}",
                      label=str(label or f"Extension · {self.id} · {key}"),
                      handler=wrapper)
        return full_key

    def on_step(self, pattern, fn=None):
        """Observe every saved step whose key matches an fnmatch pattern.

        Usable as a call or as a decorator -- `on_turn_committed` right beside
        it is a decorator, and an API where the two neighbouring hooks are
        spelled differently is one people get wrong once each.
        """
        from . import _record_step_observer

        if fn is None:
            def decorate(func):
                _record_step_observer(self.id, str(pattern or "*"), func)
                return func
            return decorate
        _record_step_observer(self.id, str(pattern or "*"), fn)
        return fn

    def on_turn_committed(self, fn):
        """Run after a turn's facts are durable, outside the transaction."""
        from . import _record_commit_observer
        _record_commit_observer(self.id, fn)
        return fn

    def add_commit_domain(self, name, fn, *, on_error="warn"):
        """Run `fn(CommitView)` INSIDE the turn's own transaction.

        The atomic counterpart to `on_turn_committed`: a write made here is
        rolled back with the turn if a later domain fails, so an extension can
        keep state that cannot survive a beat that did not happen.

        `on_error="warn"` (the default) keeps the engine's promise that a broken
        extension never costs a turn -- the failure becomes a warning and the
        transaction continues. `on_error="fail"` opts INTO rolling the turn
        back, which is the right choice only when the extension's state being
        wrong is worse than the beat being lost.
        """
        name = str(name or "").strip()
        if not _STAGE_KEY.fullmatch(name):
            raise ExtensionError(f"invalid commit domain name: {name!r}")
        if not callable(fn):
            raise ExtensionError(f"commit domain {name!r} needs a callable")
        if on_error not in ("warn", "fail"):
            raise ExtensionError(
                f"commit domain {name!r} on_error must be 'warn' or 'fail'")
        from . import _record_commit_domain
        _record_commit_domain(self.id, name, fn, on_error)
        return f"ext:{self.id}:{name}"

    def add_director_specialist(self, name, *, channels, prompt, gate=None,
                                role="default", label=None):
        """Add a Director specialist family of your own.

        The Director is no longer one mind: each stage fans out to a prose
        author plus six scoped specialists, each owning a subset of
        `state_diff`'s channels. This adds a seventh, on the same fan-out, with
        the same scope gating, the same fail-open (your specialist failing
        leaves the stage author's channels standing and never kills a beat) and
        the same canonical merge order.

        Three things it is NOT, each stated because the alternative would be
        found out fifty beats later:

        * **Your channels are namespaced `ext:<your-id>:<channel>`.** You cannot
          take ownership of `attire` or `positions`; a family that could would
          silently replace the body or spatial specialist's work.
        * **Your channels are evidence, not causality.** No engine commit domain
          reads an `ext:` channel, so what you write lands in the merged
          `state_diff` and changes nothing by itself. Act on it from your own
          `add_commit_domain` or stage.
        * **Nothing narrates it.** The prose author's sheet is assembled from
          in-tree chunks, so a change you record is in the ledger and not in the
          prose unless you put it there yourself.

        `gate(facts) -> bool` decides whether this beat has work for the family;
        omit it and it runs on physical beats, which is the fail-open rule the
        engine's own gates follow.
        """
        from agents.director import register_specialist
        from . import _record_specialist

        full = register_specialist(self.id, name, channels=channels,
                                   prompt=prompt, gate=gate, role=role,
                                   label=label)
        _record_specialist(self.id, full)
        return full

    def on_character_payload(self, fn):
        """Alter what one mind is about to be given. The routing seam.

        `fn(payload, info)` runs after `character_step` has assembled a
        character's payload and before the model sees it. Return a dict to
        replace it, or `None` to leave it alone.

        This is the surface the information-routing requirement names, and it is
        deliberately unrestricted: a hook may add, remove or rewrite anything.
        What the engine guarantees in exchange is ATTRIBUTION -- every top-level
        key a hook changes is recorded against this extension's id and rides the
        turn's commit results, so a mind that knows something it should not can
        be traced to whoever put it there in one read.

        With that power the firewall guarantee stops describing Sonder's
        pipeline for this build and starts being yours. `docs/guides/
        EXTENSIONS.md` section 8 states where the responsibility passes and why
        the objective route (make it true, let perception distribute it) is
        still the better craft.
        """
        from . import _record_payload_hook
        _record_payload_hook(self.id, fn)
        return fn

    def add_route(self, path, fn, *, methods=("GET",)):
        """Serve `fn(Request)` at `/api/extensions/<your-id>/x/<path>`.

        Under `/x/` so an extension can never shadow a host route on its own
        namespace (`enable`, `state`, `asset`, `ui.js`), whatever it names its
        path. The return value is JSON-encoded; raise `ExtensionError` for a
        400, anything else for a 500.
        """
        path = "/" + str(path or "").strip().strip("/")
        if ".." in path:
            raise ExtensionError(f"invalid route path: {path!r}")
        if not callable(fn):
            raise ExtensionError(f"route {path!r} needs a callable")
        wanted = tuple(str(m or "").upper() for m in (methods or ("GET",)))
        for method in wanted:
            if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                raise ExtensionError(f"route {path!r} cannot serve {method!r}")
        from . import _record_route
        _record_route(self.id, path, fn, wanted)
        return f"/api/extensions/{self.id}/x{path}"

    # -- models

    def llm_json(self, system, payload, *, role="utility", temperature=None,
                 max_tokens=8000):
        """One loose validated-by-nobody JSON call on a configured role.

        Deliberately NOT `_agent_json`: that path validates against
        `schemas.SCHEMA_MAP`, which only knows the engine's own steps. An
        extension owns its output's shape, so it gets the parse and not the
        schema. Returns whatever parsed, with the raw text under `text` if it
        did not.
        """
        from agents.common import jparse
        from providers import chat_complete

        raw = chat_complete(
            role, str(system or ""),
            payload if isinstance(payload, str) else json.dumps(
                payload, ensure_ascii=False),
            temperature=temperature, max_tokens=max_tokens)
        return jparse(raw)

    def llm_text(self, system, user, *, role="utility", temperature=None,
                 max_tokens=8000):
        """The same call, unparsed, for an extension that wants prose."""
        from providers import chat_complete

        return chat_complete(role, str(system or ""), str(user or ""),
                             temperature=temperature, json_mode=False,
                             max_tokens=max_tokens)

    # -- storage

    def state(self, chat_id):
        return _world_state(self.id, chat_id)

    @property
    def settings(self):
        return _settings_state(self.id)

    def char_state(self, chat_id, char_id):
        return _char_ext_state(self.id, chat_id, char_id)


def _stage_wrapper(api, key, handler, on_error):
    """The generic step handler every extension stage actually runs as.

    A stage MUST return a dict: `_assert_plan_materialized` requires exactly one
    active variant per planned key, so a stage that returns nothing fails the
    whole turn's materialization check long after the interesting failure.  With
    `on_error="warn"` the error becomes the step's content and a turn warning --
    which is the design's containment promise: a flaky extension degrades to a
    visible note, it does not kill a beat.
    """

    def wrapper(ctx, nonce):
        view = StepView(ctx)
        try:
            result = handler(view, api, nonce)
        except Exception as exc:
            if on_error == "fail":
                raise
            api.log.exception("extension stage %s failed", key)
            note = getattr(ctx, "add_warning", None)
            if callable(note):
                try:
                    note(f"extension {api.id!r} stage {key!r} failed: {exc}")
                except Exception:
                    pass
            return {"error": str(exc)}
        if result is None:
            return {}
        if not isinstance(result, dict):
            return {"value": result}
        return result

    wrapper.__name__ = f"ext_{api.id}_{key}".replace("-", "_")
    return wrapper


__all__ = [
    "CharacterAccess", "CharacterHandle", "CommitView", "CommittedTurn",
    "ExtState", "ExtensionError", "PSYCHOLOGY_STATE_KEYS", "PayloadContext",
    "Request", "SonderExtensionAPI", "StepView", "enter_commit_scope",
    "in_commit_scope", "leave_commit_scope",
]
