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


def _world_state(ext_id, chat_id, *, gated=True, frame_scoped=False):
    """One of an extension's two per-story homes.

    `ext:<id>` is chat-global and `extf:<id>` is per-era -- the second prefix
    is in `db.FRAME_SCOPED_WORLD_PREFIXES`, which is what does the scoping, so
    everything downstream (checkpoints, archives, branch and clone frame
    remapping) already handles it: those paths parse the frame off a key
    generically rather than checking it against a list.
    """
    from db import wget, wset

    key = f"{'extf' if frame_scoped else 'ext'}:{ext_id}"
    cid = int(chat_id)
    return ExtState(
        f"extension {ext_id!r} {'frame ' if frame_scoped else ''}state "
        f"for chat {cid}",
        lambda: wget(cid, key),
        lambda value: wset(cid, key, value),
        gated=gated,
    )


NARRATION_CONTEXT_KEY = "narration"
#: One block's text ceiling. A narration block rides in the narrator's payload
#: on EVERY beat of the story it is installed in, so an unbounded one is a
#: permanent tax on the context window rather than a one-off cost -- and the
#: stage it lands in is the one already carrying the whole player view.
NARRATION_CONTEXT_MAX = 8000


DIRECTOR_CONTEXT_KEY = "director"
#: The Director phases an extension may put standing context in front of.
#: `establish` is the opening turn's single Director call; `interpret` reads
#: what the player declared; `resolve` decides what it did. A campaign rule
#: that must be true before the engine forms a belief about the beat belongs
#: in one of these, and after them is too late -- which is the whole reason
#: this exists alongside `narration_context`.
DIRECTOR_PHASES = ("establish", "interpret", "resolve")
#: Per PHASE, not per block: a campaign whose interpret and resolve rules are
#: both at the ceiling costs two payloads, never one of 16,000. Same ceiling
#: as narration and for the same reason -- it rides every beat.
DIRECTOR_CONTEXT_MAX = 8000


def _narration_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class NarrationBlock:
    """An extension's standing narration context for one story.

    The declarative half of the narration seam, and the shape a host-side
    context injector actually wants: ONE keyed block per extension per story,
    revision-tracked, replaced rather than appended to. Appending is what turns
    a context injector into a leak of everything it ever said, so there is no
    append.

    Writes are UNGATED. A block is installed by a host action -- a campaign
    starting, a panel's Save, a route call -- which has no turn transaction to
    belong to, the same reasoning as `request_bind`. It is read inside the turn
    and written outside one.

    It lives in the `world` KV under `ext:<id>:narration`, so it rides
    checkpoints, archives, branches and clones with everything else in that
    namespace and needs no line in `DATABASE.md`'s checklist.
    """

    def __init__(self, ext_id, chat_id):
        self.ext_id = str(ext_id)
        self.chat_id = int(chat_id)
        self._key = f"ext:{self.ext_id}:{NARRATION_CONTEXT_KEY}"

    def _read(self):
        from db import wget

        stored = wget(self.chat_id, self._key)
        return stored if isinstance(stored, dict) else None

    def _write(self, value):
        from db import wset

        wset(self.chat_id, self._key, value)

    def get(self):
        """The stored block, or `None` if this extension has installed none."""
        return self._read()

    @property
    def text(self) -> str:
        block = self._read()
        return str((block or {}).get("text") or "")

    def set(self, text):
        """Install or replace this story's block. Returns the stored record.

        Setting the same text twice does NOT bump the revision: a rebuild that
        changed nothing is not a new revision, and a caller that re-installs on
        every beat would otherwise make the number meaningless.
        """
        text = str(text or "").strip()
        if not text:
            return self.clear()
        if len(text) > NARRATION_CONTEXT_MAX:
            raise ExtensionError(
                f"narration context is {len(text)} characters; the ceiling is "
                f"{NARRATION_CONTEXT_MAX}. It rides every beat of the story.")
        previous = self._read() or {}
        digest = _narration_hash(text)
        if previous.get("hash") == digest:
            return dict(previous)
        block = {
            "text": text,
            "hash": digest,
            "revision": int(previous.get("revision") or 0) + 1,
        }
        self._write(block)
        return dict(block)

    def clear(self):
        """Remove this story's block. Idempotent."""
        self._write(None)
        return None

    def __repr__(self):  # pragma: no cover - diagnostic only
        block = self._read() or {}
        return (f"<NarrationBlock {self.ext_id} chat={self.chat_id} "
                f"rev={block.get('revision', 0)}>")


class DirectorBlock:
    """An extension's standing context for one story's DIRECTOR calls.

    The narration seam's counterpart, one stage earlier, and the difference is
    the point of having both. `NarrationBlock` colours what the reader is
    TOLD, after the engine has already decided what happened. This colours
    what the engine decides -- a campaign rule that makes an objective ineligible
    until its evidence exists, or a command invalid while the system carrying it
    is down, has to be in front of the Director or it is a note appended to a
    verdict already reached.

    Stored per PHASE (`DIRECTOR_PHASES`), because the two questions are not the
    same question. Interpret reads the player's declaration; resolve decides
    what it did; a rule aimed at one and applied to both is how an interpretive
    constraint starts silently vetoing outcomes.

    Everything else matches `NarrationBlock` deliberately: one keyed block per
    extension per phase, REPLACED rather than appended to (an injector that
    appends leaks everything it ever said), revision stable across an identical
    re-install, writes ungated because a block is installed by a host action
    outside any turn, and resident in the `world` KV under
    `ext:<id>:director` so it rides checkpoints, archives, branches and clones
    with the rest of the namespace.

    What it is NOT is engine authority. The block arrives attributed, in
    `payload["extension_context"]`, alongside every other extension's -- it
    cannot present itself as the host's own instruction, and the Director's
    deterministic floors (player authority, claim coverage, the movement and
    restraint backstops) run afterwards on the merged result exactly as they do
    on an unextended beat.
    """

    def __init__(self, ext_id, chat_id):
        self.ext_id = str(ext_id)
        self.chat_id = int(chat_id)
        self._key = f"ext:{self.ext_id}:{DIRECTOR_CONTEXT_KEY}"

    def _read(self):
        from db import wget

        stored = wget(self.chat_id, self._key)
        return stored if isinstance(stored, dict) else {}

    def _write(self, value):
        from db import wset

        wset(self.chat_id, self._key, value or None)

    def get(self, phase=None):
        """Every stored phase as `{phase: record}`, or one phase's record."""
        stored = self._read()
        if phase is None:
            return {name: dict(record) for name, record in stored.items()
                    if isinstance(record, dict)}
        record = stored.get(self._phase(phase))
        return dict(record) if isinstance(record, dict) else None

    def text(self, phase) -> str:
        record = self.get(phase) or {}
        return str(record.get("text") or "")

    @staticmethod
    def _phase(phase):
        name = str(phase or "").strip().lower()
        if name not in DIRECTOR_PHASES:
            raise ExtensionError(
                f"unknown Director phase {phase!r}; "
                f"expected one of {', '.join(DIRECTOR_PHASES)}")
        return name

    def set(self, blocks=None, **kwargs):
        """Install or replace this story's blocks. Returns the stored record.

        Takes a mapping, keyword arguments, or both::

            api.director_context(chat_id).set(
                interpret="Deck 4 is sealed; no order can route a body there.",
                resolve="A sealed deck refuses entry however the attempt is made.",
            )

        A phase given `None` is left ALONE and a phase given an empty string is
        CLEARED -- the distinction matters because the common caller rebuilds
        one phase per host action and must not silently drop the other. Setting
        the same text twice does not bump that phase's revision.
        """
        merged = dict(blocks or {})
        merged.update(kwargs)
        if not merged:
            return self.get()
        stored = self._read()
        for phase, text in merged.items():
            name = self._phase(phase)
            if text is None:
                continue
            text = str(text).strip()
            if not text:
                stored.pop(name, None)
                continue
            if len(text) > DIRECTOR_CONTEXT_MAX:
                raise ExtensionError(
                    f"Director {name} context is {len(text)} characters; the "
                    f"ceiling is {DIRECTOR_CONTEXT_MAX}. It rides every beat "
                    "of the story.")
            previous = stored.get(name) if isinstance(
                stored.get(name), dict) else {}
            digest = _narration_hash(text)
            if previous.get("hash") == digest:
                continue
            stored[name] = {
                "text": text,
                "hash": digest,
                "revision": int(previous.get("revision") or 0) + 1,
            }
        self._write(stored)
        return self.get()

    def clear(self, phase=None):
        """Remove one phase's block, or every phase. Idempotent."""
        if phase is None:
            self._write(None)
            return {}
        stored = self._read()
        stored.pop(self._phase(phase), None)
        self._write(stored)
        return self.get()

    def __repr__(self):  # pragma: no cover - diagnostic only
        stored = self._read()
        return (f"<DirectorBlock {self.ext_id} chat={self.chat_id} "
                f"phases={sorted(stored)}>")


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
        # The per-era half, ungated for the same reason: the transaction is the
        # guarantee. A commit domain advancing mission state is the likeliest
        # caller of it -- an objective ticked in one era and not another is
        # precisely the thing `frame_state` exists for, and a domain that could
        # only reach the chat-global home would have to reimplement the
        # scoping itself, wrongly.
        self.frame_state = (
            _world_state(api.id, self.chat_id, gated=False, frame_scoped=True)
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


class NarrationContext:
    """Identity handed to an `on_narration_payload` hook alongside the payload.

    The counterpart of `PayloadContext`, and thin for the same reason. The one
    field with real content is `scope`: the narrator runs once for the reader
    and again per extra player (`narrator_extra`), and a hook that colours only
    the first silently gives two people at the same table different stories.
    """

    def __init__(self, api, ctx, *, scope="narrator", player=""):
        self.api = api
        self.scope = str(scope or "narrator")
        self.player = str(player or "")
        chat = getattr(ctx, "chat", None)
        turn = getattr(ctx, "turn", None)
        self.chat_id = getattr(chat, "id", None)
        self.turn_idx = getattr(turn, "idx", None)
        self.turn_id = getattr(turn, "id", None)
        self._ctx = ctx

    def step(self, key):
        getter = getattr(self._ctx, "get", None)
        if not callable(getter):
            return None
        try:
            return getter(key)
        except Exception:
            return None

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<NarrationContext {self.scope} chat={self.chat_id}>"


class DirectorContext:
    """Identity handed to an `on_director_payload` hook alongside the payload.

    `phase` is the field with content, and reading it is not optional: the
    three Director calls ask different questions of the same beat, and a hook
    that answers all of them the same way is applying an interpretive rule to
    a resolution or an opening-turn rule to every turn after it.
    """

    def __init__(self, api, ctx, *, phase):
        self.api = api
        self.phase = str(phase or "")
        chat = getattr(ctx, "chat", None)
        turn = getattr(ctx, "turn", None)
        self.chat_id = getattr(chat, "id", None)
        self.turn_idx = getattr(turn, "idx", None)
        self.turn_id = getattr(turn, "id", None)
        self._ctx = ctx

    def step(self, key):
        getter = getattr(self._ctx, "get", None)
        if not callable(getter):
            return None
        try:
            return getter(key)
        except Exception:
            return None

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<DirectorContext {self.phase} chat={self.chat_id}>"


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


class ChatAccess:
    """`api.chats` -- the story lifecycle, declared rather than merely reachable.

    Every call here was already possible by writing the host's own URL into a
    request. That is the position the UI mount points were in before they were
    declared: working, and one refactor from breaking somebody else's build.
    Naming them makes them a contract the host owes.

    What is deliberately absent is a way to POST prose. An extension cannot
    write an assistant message, and this is not an oversight to be filled in
    later -- narration in this engine is produced by the pipeline from state
    the Director committed, and text inserted as though the narrator wrote it
    is narration nothing earned. `commit.py` exists to make that impossible.
    An extension that wants the reader told something has three legitimate
    routes and should pick one: make it TRUE (`state_diff` via a specialist,
    or a commit domain) and let perception distribute it; put standing context
    in front of the narrator (`api.narration_context`); or put a rule in front
    of the Director (`api.director_context`).
    """

    def __init__(self, api):
        self._api = api

    def create(self, name="", scenario="", language=None):
        """A new empty story. For a whole campaign use `provision_story`."""
        from db import q, qi, transaction
        import time as _time

        with transaction():
            chat_id = qi(
                "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                (str(name or f"Chat {int(_time.time())}"), str(scenario or ""),
                 _time.time()))
            if language:
                from language_runtime import set_story_language

                set_story_language(chat_id, language)
        return dict(q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True))

    def mine(self):
        """Every story THIS extension provisioned, newest first.

        The other half of "create or bind": an extension resuming a campaign
        needs to find the story it already made, and matching on a chat's NAME
        would bind to whatever a player happened to rename something to. This
        reads the provenance written at provisioning time, so it can only ever
        return stories that are actually yours.
        """
        from db import q, wget

        found = []
        for row in q("SELECT id, name FROM chats ORDER BY id DESC"):
            stored = wget(row["id"], f"ext:{self._api.id}:provisioned")
            if isinstance(stored, dict):
                found.append({"chat_id": row["id"], "name": row["name"],
                              "provenance": dict(stored)})
        return found

    def turns(self, chat_id, limit=20):
        """Recent committed turns of one story, oldest last."""
        from db import q

        rows = q("SELECT id, idx, player_input FROM turns WHERE chat_id=? "
                 "ORDER BY idx DESC LIMIT ?", (int(chat_id), int(limit)))
        return [{"turn_id": r["id"], "idx": r["idx"],
                 "player_input": r["player_input"]} for r in reversed(rows)]

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<ChatAccess {self._api.id}>"


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

    def on_narration_payload(self, fn):
        """Alter what the NARRATOR is about to be given. The other routing seam.

        `fn(payload, info)` runs after the narrator's payload is assembled and
        before the model sees it -- including the retry paths, which reuse the
        hooked payload rather than re-running the hook, so a fidelity or craft
        correction cannot silently narrate against different context than the
        first attempt did.

        `info` is a `NarrationContext`. Read `info.scope` before assuming which
        reader this is: `"narrator"` is the main player and `"narrator_extra"`
        is one additional player at the same table, each with their own
        perception-filtered view. A hook that colours only one of them hands two
        people at one table different stories.

        Unrestricted and attributed, exactly as `on_character_payload` is, and
        §8 of the guide applies here with one difference worth stating: the
        narrator writes what the READER sees. A character payload that carries
        too much produces a mind acting on knowledge it should not have --
        legible, in-fiction, and recoverable. Narration that carries too much is
        simply told to the player and cannot be taken back.

        Most callers want `api.narration_context(chat_id)` instead: standing
        context for a story is a stored block, not a hook that has to run on
        every beat to say the same thing.
        """
        from . import _record_narration_hook
        _record_narration_hook(self.id, fn)
        return fn

    def on_director_payload(self, fn):
        """Alter what the DIRECTOR is about to be given. The earliest seam.

        `fn(payload, info)` runs after a Director payload is assembled and
        before the model sees it, for all three phases -- read `info.phase`
        (`"establish"`, `"interpret"`, `"resolve"`) and return a dict to
        replace the payload, or `None` to leave it alone.

        Once per BEAT, not once per attempt. `director_resolve` re-enters
        generation for the world-pressure floor and again for the player-act
        authority retry, and those retries reuse the hooked payload rather than
        re-running the hook -- a correction that saw different campaign context
        than the first attempt did would be answering a question nobody asked.

        Unrestricted and attributed, exactly as `on_character_payload` and
        `on_narration_payload` are. The distinction worth holding: a character
        payload shapes what one mind believes, a narration payload shapes what
        the reader is told, and this shapes what the ENGINE believes happened
        -- which is the one of the three that then propagates into state,
        perception, memory and every later beat. It also cannot be taken back
        by a reroll of a later stage.

        Most callers want `api.director_context(chat_id)` instead: standing
        campaign rules are a stored block, not a hook that has to run every
        beat to say the same thing.
        """
        from . import _record_director_hook
        _record_director_hook(self.id, fn)
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

    # -- creating a story

    def provision_story(self, package, *, state=None, package_id="",
                        package_version="", player_authority=None):
        """Create a whole playable story in one act, or create nothing.

        `package` is a chat archive -- the engine's own portable format, the
        one `chat_archive.py` already exports, validates and id-remaps. That is
        a deliberate refusal to invent a second scenario format: a campaign
        needs a story, a persona, a cast with stable ids, rooms and portals and
        positions, a scene, a clock, authored lore on both sides of the
        firewall, and relationship state, all agreeing from the first turn --
        which is a list this engine already knows how to build atomically,
        because it is the same list a branch and a restore have to get right.
        A second importer would be a second set of the bugs that one has
        already had.

        `state` seeds this extension's own namespaced state for the new story
        INSIDE the same transaction. That is the part an archive alone cannot
        do and the reason this is a method rather than a documentation note: a
        story that exists with no campaign state attached is precisely the
        partial provisioning the whole contract is supposed to make impossible.

        `player_authority` declares the rung the campaign needs -- `actor_only`,
        `explicit_outcomes` or `world_author` (`Design.md` § Hard mode). A
        campaign whose whole premise is that the player may not write the world
        cannot ask for that after the first beat has already been played under
        the other rule, and reaching into `scene.set_player_authority` to get it
        would be exactly the unsupported-internals dependency this facade
        exists to remove. Omitted leaves the story on the host default.

        Provenance is recorded against your id, so a story can always answer
        which extension and which package version made it. Six months later
        that is the difference between a reproducible campaign and a save file
        nobody can place.

        Everything or nothing: a validation failure anywhere leaves no chat, no
        characters, no lore and no state behind. Raises `ExtensionError` with
        the validation message on a package the engine will not accept.
        """
        import time

        from db import transaction, wset

        payload = package
        if not isinstance(payload, dict):
            raise ExtensionError("provision_story needs an archive dict")

        with transaction():
            try:
                import app

                chat = app._chat_archive_service.import_chat({"data": payload})
            except ExtensionError:
                raise
            except Exception as exc:
                detail = getattr(exc, "detail", None) or str(exc)
                raise ExtensionError(f"campaign package refused: {detail}")

            chat_id = int(chat["id"])
            # The import path appends " (import)" so somebody else's save does
            # not sit in the list looking like your own. A campaign the player
            # just pressed Start on is not somebody else's save: the package
            # named the story, and the name it chose is the one that belongs on
            # it. Renamed inside the same transaction, so a later failure takes
            # the rename with everything else.
            wanted = str((payload.get("chat") or {}).get("name") or "").strip()
            if wanted and wanted != chat.get("name"):
                from db import qi

                qi("UPDATE chats SET name=? WHERE id=?", (wanted, chat_id))
                chat = dict(chat, name=wanted)
            if player_authority is not None:
                from scene import (PLAYER_AUTHORITY_MODES,
                                   set_player_authority)

                # Refused rather than normalized, for the reason the host route
                # gives: `set_player_authority` falls back to the default on an
                # unreadable value, and a campaign whose premise is that the
                # player may not write the world would then quietly ship with
                # the player writing the world.
                if player_authority not in PLAYER_AUTHORITY_MODES:
                    raise ExtensionError(
                        f"player_authority must be one of "
                        f"{', '.join(PLAYER_AUTHORITY_MODES)}")
                set_player_authority(chat_id, player_authority, turn_idx=0)
            if state is not None:
                self.state(chat_id).set_now(state)
            wset(chat_id, f"ext:{self.id}:provisioned", {
                "extension": self.id,
                "package": str(package_id or ""),
                "version": str(package_version or ""),
                "at": time.time(),
            })
        return {"chat_id": chat_id, "name": chat.get("name"),
                "schema": self.story_view(chat_id)["schema"]}

    def provenance(self, chat_id):
        """What this extension recorded when it provisioned this story.

        `None` for a story it did not provision -- including one a player
        started by hand and later installed you into, which is a different
        situation from a campaign of yours and should not be mistaken for one.
        """
        from db import wget

        stored = wget(int(chat_id), f"ext:{self.id}:provisioned")
        return dict(stored) if isinstance(stored, dict) else None

    # -- reading the story

    def story_view(self, chat_id, *, events=None):
        """Canonical story state as a versioned, read-only, plain-value dict.

        What is objectively true right now: ids, clock, frame, scene, rooms,
        cast with their STABLE ids, recent committed events, and the story's
        player-authority mode. Enough to derive campaign eligibility and render
        a panel without importing an engine module or opening the database --
        which is the point, because an integration built on either of those is
        one refactor from breaking, and the extension boundary was supposed to
        prevent exactly that.

        Objective truth, and deliberately so. The firewall constrains what
        reaches a fictional MIND; an extension is not one. Where a mind's
        limits ARE the question, ask `player_view` instead -- and note that
        wanting the objective read here is usually the right instinct, because
        a campaign rule that fires on what the PLAYER happens to have noticed
        fires differently on a reroll.

        `schema` is the compatibility contract: it is bumped when a consumer
        could break, and consumers of this live outside this repository and
        cannot be migrated in the same commit.
        """
        import story_view as facade

        if events is None:
            return facade.story_view(chat_id)
        return facade.story_view(chat_id, events=events)

    def player_view(self, chat_id, viewer="player", *, memories=12):
        """What one person in the story may be shown. A security boundary.

        Built out of what the engine ALREADY DELIVERED to that viewer -- the
        perception stage's own rendered view and structured observations, their
        own memories and relationships, the identity ledger's own answer about
        who they can name. Nothing in it re-decides admission, because a second
        implementation of "what does this persona know" agrees with
        `agents/perception.py` on the day it is written and drifts from it
        silently forever after. A projection is never narrated, so nobody would
        read the leak.

        Absent means absent. A field this cannot answer is missing from the
        result rather than defaulted, guessed, or filled from personality: a UI
        cannot tell a guess from a fact and will render both the same way.

        `api.viewers(chat_id)` lists the ids this accepts.
        """
        import story_view as facade

        return facade.player_view(chat_id, viewer, memories=memories)

    def viewers(self, chat_id):
        """Who this story can be projected for, as `{id, name, kind}`."""
        import story_view as facade

        return facade.viewers(chat_id)

    @property
    def chats(self):
        """The story lifecycle. See `ChatAccess`, including what it refuses."""
        return ChatAccess(self)

    # -- storage

    def state(self, chat_id):
        """Per-story state, shared across every era of that story.

        The right home for what an installation is -- your configuration for
        this story, the package you provisioned it from, anything whose answer
        does not change because the player walked into a different century.
        For what does, see `frame_state`.
        """
        return _world_state(self.id, chat_id)

    def frame_state(self, chat_id):
        """Per-story state scoped to the FRAME the story is currently in.

        Sonder stories can hold more than one era (`frames.py`), and most of
        the world is already per-era for a reason a campaign inherits whole: a
        branch that never went somewhere must not arrive holding what happened
        there. `scene`, `known`, the clock, the crowds and the couriers are all
        frame-scoped; an extension's state was not, so a mission advanced in
        one era was advanced in every era, and a rewind that took the room back
        left the objective ticked.

        Two homes rather than one flag, because the KEY is the scoping
        mechanism: a story already holding `ext:<id>` cannot gain scoping
        without its key changing, so a flag would be a migration wearing the
        word. It is also a real distinction rather than a workaround -- a
        campaign's provenance spans eras and its mission state does not, and an
        author choosing between them is answering a question about their
        campaign, not about this engine.

        Reads and writes go to whichever frame the turn is running in. Outside
        a pipeline run there is no active frame and this reads the present, the
        same rule every other frame-scoped key follows.
        """
        return _world_state(self.id, chat_id, frame_scoped=True)

    @property
    def settings(self):
        return _settings_state(self.id)

    def char_state(self, chat_id, char_id):
        return _char_ext_state(self.id, chat_id, char_id)

    def narration_context(self, chat_id):
        """This extension's standing narration block for one story.

        The declarative narration seam: install a block once and every beat of
        that story carries it into the narrator's payload under
        `extension_context`, attributed to you, until you clear it.

        ```python
        api.narration_context(chat_id).set(
            "The ship is three days into a fuel emergency; corridors are dim "
            "and the air is cold.")
        ```

        What belongs in it is SETTING and STANDING SITUATION -- the frame the
        beat is narrated inside. What does not is world fact the engine also
        tracks: the narrator checks event order, positions, room names and
        portal states against the committed scene, so a block asserting a door
        is open when `state_diff.rooms` recorded it closed makes the two fight,
        and the loser is legible only as a narrator defect fifty beats later.
        Where a fact belongs to the world, put it in the world and let
        perception distribute it.
        """
        return NarrationBlock(self.id, chat_id)

    def director_context(self, chat_id):
        """Standing campaign context for this story's Director calls.

        The declarative half of the Director seam::

            api.director_context(chat_id).set(
                interpret="Deck 4 is sealed; no order routes a body there.",
                resolve="A sealed deck refuses entry however it is attempted.",
            )

        Installed once and read on every beat of that phase, attributed to you,
        until you clear it. Returns a `DirectorBlock`; see it for what the
        block is and, as importantly, what it is not.
        """
        return DirectorBlock(self.id, chat_id)


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
    "ChatAccess", "DirectorBlock", "DirectorContext",
    "ExtState", "ExtensionError", "PSYCHOLOGY_STATE_KEYS", "PayloadContext",
    "Request", "SonderExtensionAPI", "StepView", "enter_commit_scope",
    "in_commit_scope", "leave_commit_scope",
]
