"""The facade one installed extension is handed, and nothing else.

An extension never receives a `PipelineContext`, a database handle, or another
character's private view.  It receives one `SonderExtensionAPI` bound to its own
id, and every durable thing it can touch is namespaced under `ext:<id>` -- world
KV for per-story state, the settings table for install-scoped config, a
single reserved key inside `chat_chars.state` for per-character state, and
JSON documents at logical paths (`DocumentStore`) stored as rows in those same
two KV tables.  That namespacing is the whole persistence story: all of those
already ride checkpoints, archives and branches wholesale, so an extension
inherits rewind/export/clone without a schema change or a line in DATABASE.md's
checklist.

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

#: Frame-selection sentinels, module-private. Two of them because `None` is
#: unavailable for either job: it is the engine's real identifier for the
#: implicit present era, and a caller must be able to select the present
#: explicitly. `_LATEST_FRAME` means "the latest committed turn's frame,
#: resolved once"; `_AMBIENT_FRAME` means "whatever `db.active_frame_id`
#: holds at call time" -- the behaviour every unbound state accessor keeps.
#: Deliberately DIFFERENT objects from `web/story_view.py`'s own sentinel:
#: neither module's sentinel may ever travel into the other as a value.
_LATEST_FRAME = object()
_AMBIENT_FRAME = object()

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


def _world_state(ext_id, chat_id, *, gated=True, frame_scoped=False,
                 frame_id=_AMBIENT_FRAME):
    """One of an extension's two per-story homes.

    `ext:<id>` is chat-global and `extf:<id>` is per-era -- the second prefix
    is in `db.FRAME_SCOPED_WORLD_PREFIXES`, which is what does the scoping, so
    everything downstream (checkpoints, archives, branch and clone frame
    remapping) already handles it: those paths parse the frame off a key
    generically rather than checking it against a list.

    `frame_id` (only meaningful with `frame_scoped=True`) BINDS the state to
    one era at construction: reads and writes go through `wget_for_frame`/
    `wset_for_frame`, which resolve the frame into each individual call --
    set-and-reset around one query, never left ambient across extension code
    -- so a later `.get()` still answers for the bound frame whatever
    `active_frame_id` has become in between. `_AMBIENT_FRAME` keeps the
    historical behaviour: whichever frame is active AT CALL TIME, which is
    what state read inside a pipeline run wants.
    """
    from core.db import wget, wget_for_frame, wset, wset_for_frame

    key = f"{'extf' if frame_scoped else 'ext'}:{ext_id}"
    cid = int(chat_id)
    if frame_scoped and frame_id is not _AMBIENT_FRAME:
        fid = frame_id
        return ExtState(
            f"extension {ext_id!r} frame state for chat {cid} in frame "
            f"{'present' if fid is None else fid}",
            lambda: wget_for_frame(cid, key, fid),
            lambda value: wset_for_frame(cid, key, value, fid),
            gated=gated,
        )
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
        from core.db import wget

        stored = wget(self.chat_id, self._key)
        return stored if isinstance(stored, dict) else None

    def _write(self, value):
        from core.db import wset

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
        from core.db import wget

        stored = wget(self.chat_id, self._key)
        return stored if isinstance(stored, dict) else {}

    def _write(self, value):
        from core.db import wset

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


# ---------------------------------------------------------------- documents

#: One logical-path segment. The store never touches a filesystem -- a path is
#: an exact KV row key, so there is nothing here to traverse -- but paths
#: round-trip through URLs, integrity panels and OTHER hosts' storage adapters
#: (the port this was built for keeps JSON documents at logical paths), so the
#: alphabet is the portable one. Requiring the first character to be
#: alphanumeric is what makes "." and ".." unspellable as segments: traversal
#: is refused by construction rather than by a denylist someone extends after
#: the miss.
DOCUMENT_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DOCUMENT_PATH_MAX = 256

#: Per-document ceiling, in bytes of the CANONICAL serialization. A story
#: document is a `world` row, and checkpoints snapshot the whole world table
#: on every turn, so a document's real cost is its size times the length of
#: the story -- the same reasoning as `NARRATION_CONTEXT_MAX`, with the
#: checkpoint ledger in place of the context window. Refused, never truncated:
#: a truncated JSON document is not a smaller document, it is a parse error,
#: and one that `verify` would dutifully report fifty beats after the write
#: that caused it. The writer must learn at write time.
DOCUMENT_MAX_BYTES = 131072
#: Per extension, per scope. The count ceiling exists for the same checkpoint
#: arithmetic as the size ceiling -- 256 documents at the size ceiling is
#: already a 32 MiB tax on every checkpoint of the story -- and to keep
#: `list`/`verify` answerable in one read.
DOCUMENT_COUNT_MAX = 256

_DOC_INFIX = ":doc:"
_LIKE_ESCAPE = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})


def document_path(path) -> str:
    """Validate one logical document path, or raise with the rule.

    A path is `/`-separated segments, each matching `DOCUMENT_SEGMENT`
    (letters, digits, then letters/digits/`._-`, 64 chars max), the whole
    thing at most `DOCUMENT_PATH_MAX` characters. No leading or trailing
    slash, no empty segment, no backslash, and no segment starting with a
    dot -- which refuses `.` and `..` and every other traversal spelling.
    """
    text = str(path or "")
    if not text:
        raise ExtensionError("document path must not be empty")
    if len(text) > DOCUMENT_PATH_MAX:
        raise ExtensionError(
            f"document path is {len(text)} characters; the ceiling is "
            f"{DOCUMENT_PATH_MAX}")
    if text.startswith("/") or "\\" in text:
        raise ExtensionError(
            f"document path {text!r} must be relative, `/`-separated, and "
            "backslash-free")
    for segment in text.split("/"):
        if not DOCUMENT_SEGMENT.fullmatch(segment):
            raise ExtensionError(
                f"document path {text!r} has an invalid segment "
                f"{segment!r}: each segment must start with a letter or "
                "digit and contain only letters, digits, '.', '_' and '-' "
                "(max 64 chars)")
    return text


def _canonical_document(value):
    """The bytes a document is sized and hashed as.

    Canonical (sorted keys, tight separators) so that two spellings of the
    same JSON value hash the same and the integrity check verifies CONTENT,
    not formatting -- a dict reserialized in a different key order is not
    damage.
    """
    import hashlib

    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ExtensionError(f"document is not JSON-serializable: {exc}")
    data = text.encode("utf-8")
    return data, hashlib.sha256(data).hexdigest()


class DocumentStore:
    """JSON documents at logical paths, one KV row per document.

    The fifth persistence home, and deliberately NOT a fifth table. The
    `world` table already is a namespaced JSON-document store keyed
    `(chat_id, key)`, and every carriage a durable table would owe --
    checkpoint snapshot/restore, portable archive export/import, branch
    cloning, cascade on chat delete -- copies that table WHOLESALE, with no
    per-key knowledge (`checkpoints.snapshot_state`, `chat_archive`'s
    `export["world"]`, `app.py`'s branch helper). A story document stored as
    a `world` row under `ext:<id>:doc:<path>` therefore inherits rewind,
    export and clone exactly as the four existing homes do, and a new table
    would re-implement all of that plus a migration to be equivalent --
    `DATABASE.md`'s checklist exists because tables keep failing to finish
    that list, and the namespaced homes' entire design argument is that they
    never start it.

    One ROW per document, not paths inside the `ext:<id>` blob: a put must
    not rewrite every sibling document, and `list` must not deserialize the
    whole store to answer with metadata.

    Two scopes, because the two questions Directive's adapter asks are not
    the same question:

    * **story scope** (`chat_id` given) -- rows in `world`. Campaign
      progress, mission ledgers, anything computed FROM the story. Rides
      checkpoints/archives/branches, so a rewound beat takes its documents
      with it and a branch carries the documents as of the branch point.
    * **install scope** (`chat_id=None`) -- rows in `settings`, exactly
      like `api.settings`. A campaign package library, adapter config: it
      exists before any story does and belongs to the machine, so it
      deliberately does NOT ride story history -- a reroll must not delete
      the host's library.

    Writes to story documents are gated to the committed-turn hook exactly
    as `ExtState.set` is, and for the same measured hazard: a document
    written mid-pipeline lands outside the turn's transaction, survives the
    rollback that undid everything it was computed from, and the rerun then
    replays against a document that never went away. `put_now`/`delete_now`
    are the named escape hatches for host actions (a panel's Save, a route
    call), which have no turn transaction to belong to -- the same reasoning
    that leaves `NarrationBlock` and install-scope writes ungated.
    """

    def __init__(self, ext_id, chat_id=None, *, gated=None):
        self.ext_id = str(ext_id)
        self.chat_id = None if chat_id is None else int(chat_id)
        # Install scope is ungated like `api.settings`; story scope is gated
        # like `api.state`. A caller inside the turn's own transaction (a
        # commit domain's `CommitView`) passes gated=False, because there the
        # transaction is the guarantee.
        self._gated = (self.chat_id is not None) if gated is None else bool(
            gated)
        self._prefix = f"ext:{self.ext_id}{_DOC_INFIX}"

    # -- raw row access, scope-switched

    def _key(self, path):
        return self._prefix + path

    def _rows(self, prefix=""):
        """Every (path, raw value) under this store, RAW on purpose.

        `list` and `verify` must survive a damaged row, so they read the
        stored text and do their own parsing instead of going through
        `wget`/`get_setting`+`json.loads`, which would throw on the exact
        rows they exist to report.
        """
        from core.db import q

        like = self._prefix.translate(_LIKE_ESCAPE) + (
            prefix.translate(_LIKE_ESCAPE) + "%" if prefix else "%")
        if self.chat_id is None:
            rows = q("SELECT key, value FROM settings "
                     "WHERE key LIKE ? ESCAPE '\\' ORDER BY key", (like,))
        else:
            rows = q("SELECT key, value FROM world "
                     "WHERE chat_id=? AND key LIKE ? ESCAPE '\\' "
                     "ORDER BY key", (self.chat_id, like))
        out = []
        for row in rows:
            path = row["key"][len(self._prefix):]
            if prefix and not (path == prefix
                               or path.startswith(prefix + "/")):
                continue
            out.append((path, row["value"]))
        return out

    def _read_raw(self, path):
        from core.db import q

        if self.chat_id is None:
            row = q("SELECT value FROM settings WHERE key=?",
                    (self._key(path),), one=True)
        else:
            row = q("SELECT value FROM world WHERE chat_id=? AND key=?",
                    (self.chat_id, self._key(path)), one=True)
        return row["value"] if row else None

    def _write(self, path, envelope):
        if self.chat_id is None:
            from core.db import set_setting

            set_setting(self._key(path), json.dumps(envelope,
                                                    ensure_ascii=False))
        else:
            from core.db import wset

            wset(self.chat_id, self._key(path), envelope)

    def _delete_key(self, path):
        from core.db import q, qi

        if self.chat_id is None:
            existed = q("SELECT 1 FROM settings WHERE key=?",
                        (self._key(path),), one=True)
            qi("DELETE FROM settings WHERE key=?", (self._key(path),))
        else:
            existed = q("SELECT 1 FROM world WHERE chat_id=? AND key=?",
                        (self.chat_id, self._key(path)), one=True)
            qi("DELETE FROM world WHERE chat_id=? AND key=?",
               (self.chat_id, self._key(path)))
        return bool(existed)

    @staticmethod
    def _envelope(raw):
        """Parse one stored row, or raise ExtensionError naming the damage."""
        try:
            stored = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ExtensionError(f"stored document is not JSON: {exc}")
        if not isinstance(stored, dict) or "doc" not in stored:
            raise ExtensionError(
                "stored document has no envelope; something outside this "
                "store wrote the row")
        return stored

    @staticmethod
    def _meta(path, envelope):
        return {"path": path,
                "size": int(envelope.get("size") or 0),
                "sha256": str(envelope.get("sha256") or ""),
                "revision": int(envelope.get("revision") or 0),
                "created_at": envelope.get("created_at"),
                "updated_at": envelope.get("updated_at")}

    def _scope_label(self):
        return ("the install" if self.chat_id is None
                else f"chat {self.chat_id}")

    # -- the surface

    def put(self, path, value):
        """Store one JSON document. Gated for story scope; see `put_now`."""
        if self._gated and not in_commit_scope():
            raise ExtensionError(
                f"extension {self.ext_id!r} documents for "
                f"{self._scope_label()} may only be written from an "
                "on_turn_committed hook, where the turn's own writes have "
                "already landed. Use put_now(...) to write outside one "
                "anyway.")
        return self.put_now(path, value)

    def put_now(self, path, value):
        """Write outside a committed-turn hook, accepting the consequences."""
        import time

        path = document_path(path)
        data, digest = _canonical_document(value)
        if len(data) > DOCUMENT_MAX_BYTES:
            raise ExtensionError(
                f"document {path!r} is {len(data)} bytes; the ceiling is "
                f"{DOCUMENT_MAX_BYTES}. Refused rather than truncated, "
                "because a truncated JSON document is a parse error, not a "
                "smaller document -- and a story document is re-stored in "
                "every checkpoint of the story.")
        raw = self._read_raw(path)
        previous = None
        if raw is not None:
            try:
                previous = self._envelope(raw)
            except ExtensionError:
                previous = None  # overwriting damage is repair, not loss
        if previous is None and raw is None:
            count = len(self._rows())
            if count >= DOCUMENT_COUNT_MAX:
                raise ExtensionError(
                    f"extension {self.ext_id!r} already stores {count} "
                    f"documents for {self._scope_label()}; the ceiling is "
                    f"{DOCUMENT_COUNT_MAX}. Delete before adding -- every "
                    "story document rides every checkpoint of the story.")
        if previous is not None and previous.get("sha256") == digest:
            # Same content is not a new revision -- a caller that re-puts on
            # every beat must not make the number meaningless (the same rule
            # as NarrationBlock's).
            return self._meta(path, previous)
        now = time.time()
        envelope = {
            "doc": value,
            "sha256": digest,
            "size": len(data),
            "revision": int((previous or {}).get("revision") or 0) + 1,
            "created_at": (previous or {}).get("created_at") or now,
            "updated_at": now,
        }
        self._write(path, envelope)
        return self._meta(path, envelope)

    def get(self, path, default=None):
        """The stored document, `default` when absent.

        A DAMAGED row raises rather than returning `default`: absence and
        damage are different answers, and a caller shown `default` for a row
        `verify` would report as broken has been lied to.
        """
        path = document_path(path)
        raw = self._read_raw(path)
        if raw is None:
            return default
        return self._envelope(raw)["doc"]

    def stat(self, path):
        """Metadata for one document, or `None` when absent."""
        path = document_path(path)
        raw = self._read_raw(path)
        if raw is None:
            return None
        return self._meta(path, self._envelope(raw))

    def list(self, prefix=""):
        """Every document under `prefix`, as metadata, sorted by path.

        Prefixes are SEGMENT-aware: `missions` matches `missions` and
        `missions/1`, never `missions2/1` -- a prefix that matched raw
        characters would make one store's namespace bleed into a sibling's.
        Total: a damaged row is listed with `"damaged": True` and the error,
        because an integrity screen's roster must include exactly the rows
        `verify` will complain about.
        """
        prefix = document_path(prefix) if prefix else ""
        out = []
        for path, raw in self._rows(prefix):
            try:
                out.append(self._meta(path, self._envelope(raw)))
            except ExtensionError as exc:
                out.append({"path": path, "damaged": True,
                            "error": str(exc)})
        return out

    def delete(self, path):
        """Remove one document. Gated exactly as `put` is; see `delete_now`."""
        if self._gated and not in_commit_scope():
            raise ExtensionError(
                f"extension {self.ext_id!r} documents for "
                f"{self._scope_label()} may only be deleted from an "
                "on_turn_committed hook. Use delete_now(...) to delete "
                "outside one anyway.")
        return self.delete_now(path)

    def delete_now(self, path):
        """Remove one document immediately. True if it existed. Idempotent."""
        return self._delete_key(document_path(path))

    def delete_prefix(self, prefix=""):
        """Remove every document under `prefix`. Gated; see the `_now` form."""
        if self._gated and not in_commit_scope():
            raise ExtensionError(
                f"extension {self.ext_id!r} documents for "
                f"{self._scope_label()} may only be deleted from an "
                "on_turn_committed hook. Use delete_prefix_now(...) to "
                "delete outside one anyway.")
        return self.delete_prefix_now(prefix)

    def delete_prefix_now(self, prefix=""):
        """Remove every document under `prefix` (`""` = all). Returns count.

        Bounded by the namespace: however wide the prefix, only this
        extension's rows in this scope can go.
        """
        prefix = document_path(prefix) if prefix else ""
        removed = 0
        for path, _raw in self._rows(prefix):
            removed += 1 if self._delete_key(path) else 0
        return removed

    def verify(self, prefix=""):
        """Check every stored document is readable, parseable and unaltered.

        The integrity screen's question, answered without throwing: damage
        is the REPORT, never an exception -- an integrity check that dies on
        the first broken row cannot tell you about the second. Three checks
        per row: the stored text parses as JSON, the envelope has a
        document, and the document's canonical hash matches the recorded
        `sha256` (a mismatch means the row was altered outside this store,
        or corrupted at rest).
        """
        prefix = document_path(prefix) if prefix else ""
        damaged = []
        checked = 0
        for path, raw in self._rows(prefix):
            checked += 1
            try:
                envelope = self._envelope(raw)
            except ExtensionError as exc:
                damaged.append({"path": path, "error": str(exc)})
                continue
            try:
                _data, digest = _canonical_document(envelope.get("doc"))
            except ExtensionError as exc:
                damaged.append({"path": path, "error": str(exc)})
                continue
            if digest != envelope.get("sha256"):
                damaged.append({
                    "path": path,
                    "error": "content hash mismatch: the row was altered "
                             "outside this store or corrupted at rest"})
        return {"ok": not damaged, "checked": checked, "damaged": damaged}

    def __repr__(self):  # pragma: no cover - diagnostic only
        return (f"<DocumentStore {self.ext_id} "
                f"scope={self._scope_label()}>")


def _settings_state(ext_id):
    from core.db import get_setting, set_setting

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


def _read_char_state(chat_id, char_id, *, frame_id=_AMBIENT_FRAME):
    """The character's whole engine-owned state dict, frame override first.

    An explicit `frame_id` is resolved into the QUERY PARAMETER, never set on
    the ambient contextvar: a bound read must not leave `active_frame_id`
    changed across arbitrary extension code, and must keep answering for its
    own frame after somebody else changes the ambient one.
    """
    from core.db import active_frame_id, q

    if frame_id is _AMBIENT_FRAME:
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


def _write_char_state(chat_id, char_id, mutate, *, frame_id=_AMBIENT_FRAME):
    """Read-modify-write through the engine's own helper.

    Never build a fresh dict: `chat_chars.state` carries active_state, interior,
    stance, the tell ledgers and the spatial memory, and a blind overwrite would
    delete a mind's whole history to store one extension's counter.

    The frame is resolved ONCE and used for both halves: reading era A and
    writing era B would be the mixed-frame defect on the write side, worse,
    because it copies one era's whole state dict over another's.
    """
    from core.db import active_frame_id
    from story.scene import set_char_state

    if frame_id is _AMBIENT_FRAME:
        frame_id = active_frame_id.get()
    state = _read_char_state(chat_id, char_id, frame_id=frame_id)
    mutate(state)
    set_char_state(int(chat_id), int(char_id),
                   json.dumps(state, ensure_ascii=False),
                   frame_id=frame_id)


def _char_ext_state(ext_id, chat_id, char_id, *, gated=True,
                    frame_id=_AMBIENT_FRAME):
    key = f"ext:{ext_id}"

    def read():
        return _read_char_state(chat_id, char_id, frame_id=frame_id).get(key)

    def write(value):
        def mutate(state):
            state[key] = value
        _write_char_state(chat_id, char_id, mutate, frame_id=frame_id)

    label = f"extension {ext_id!r} state for character {char_id} in chat {chat_id}"
    if frame_id is not _AMBIENT_FRAME:
        label += f" in frame {'present' if frame_id is None else frame_id}"
    return ExtState(label, read, write, gated=gated)


# ---------------------------------------------------------------- frames


def _validate_frame(chat_id, frame_id):
    """An explicitly selected frame, validated, or an `ExtensionError`.

    `None` (the implicit present era) is valid for every chat. A frame that
    does not exist and a frame belonging to ANOTHER chat get the same refusal
    on purpose: an extension holding chat A must not be able to use the
    refusal text to probe which frame ids exist in chat B.
    """
    if frame_id is None:
        return None
    from core.frames import get_frame

    frame = get_frame(frame_id)
    if frame is None or int(frame["chat_id"]) != int(chat_id):
        raise ExtensionError(
            f"no frame {frame_id!r} in chat {int(chat_id)}")
    return int(frame_id)


def _latest_frame_id(chat_id):
    """The frame the story is actually on: the latest committed turn's.
    `None` -- the present -- for a story with no turns at all."""
    from web.story_view import latest_turn

    turn = latest_turn(int(chat_id))
    return turn["frame_id"] if turn else None


class ExtensionFrameView:
    """Every frame-sensitive read and write, bound to exactly ONE era.

    The mixed-frame defect this exists against: `player_view` resolves the
    latest committed turn's frame, while an unbound `frame_state(...).get()`
    or `char_state(...).get()` reads whatever `db.active_frame_id` holds --
    which, on an extension HTTP route, is unset and answers for the present.
    A projection composed from both was structurally valid and semantically
    impossible: scene and identity from one era, mission, clock and crew
    state from another. Worse than a hard failure, because a consumer
    receives plausible data. The frame is therefore resolved ONCE, here, at
    construction, and every method reads or writes that frame and no other;
    a new read added to a growing DTO cannot drift, because there is no
    per-call frame left to forget.

    Immutable, and inspectable: `frame_id` is the resolved selection
    (`None` = the present era), so a test or a log can prove what one
    request was reading instead of trusting that it composed correctly.

    What is deliberately NOT here: `state` and `documents` (chat-global by
    design -- putting them on a frame-bound object would imply a scoping
    they do not have), `viewers` (the roster is chat-global), and events
    (`story_view`'s `events` stays story-global under any selection; see
    `web/story_view.py`'s `_events` for the ruling).

    Writes bind exactly like reads, because refusing them would manufacture
    the same defect on the write side: read era A through the view, then
    `api.frame_state(chat).set_now(...)` lands in era B. A bound write is
    `db.wset_for_frame` -- the primitive the engine's own cross-frame code
    (spatial split/merge) already uses -- confined to this extension's own
    `extf:`/`ext:` namespace; nothing here can touch the scene, the ledgers
    or another extension's rows. The commit gate is unchanged: the binding
    decides WHERE a write lands, the gate still decides WHEN it may
    (`set()` inside an `on_turn_committed` hook, `set_now()` as the named
    escape hatch).
    """

    __slots__ = ("_api", "_chat_id", "_frame_id")

    def __init__(self, api, chat_id, frame_id):
        object.__setattr__(self, "_api", api)
        object.__setattr__(self, "_chat_id", int(chat_id))
        object.__setattr__(self, "_frame_id", frame_id)

    def __setattr__(self, name, value):
        raise ExtensionError(
            "a frame view is immutable; call api.at_frame(...) again to "
            "select a different frame")

    @property
    def chat_id(self):
        return self._chat_id

    @property
    def frame_id(self):
        """The resolved selection. `None` is the implicit present era."""
        return self._frame_id

    def story_view(self, *, events=None):
        return self._api.story_view(self._chat_id, events=events,
                                    frame_id=self._frame_id)

    def player_view(self, viewer="player", *, memories=12):
        return self._api.player_view(self._chat_id, viewer,
                                     memories=memories,
                                     frame_id=self._frame_id)

    def frame_state(self):
        return _world_state(self._api.id, self._chat_id, frame_scoped=True,
                            frame_id=self._frame_id)

    def char_state(self, char_id):
        return _char_ext_state(self._api.id, self._chat_id, char_id,
                               frame_id=self._frame_id)

    def __repr__(self):  # pragma: no cover - diagnostic only
        frame = "present" if self._frame_id is None else self._frame_id
        return (f"<ExtensionFrameView {self._api.id} chat={self._chat_id} "
                f"frame={frame}>")


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
        from core.db import q

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
        from story.character_schema import character_name_from_text
        from core.db import q

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

    def documents(self):
        """This story's document store, ungated for the same reason `state`
        is: a write made here is inside the turn's transaction, so it rolls
        back with the turn and the ghost-state hazard the gate exists for is
        already impossible."""
        if self.chat_id is None:
            return None
        return DocumentStore(self._api.id, self.chat_id, gated=False)

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


#: A violation's `code` is machine-readable and its `message` is what the
#: Director is asked to fix, so the ceiling belongs on the message: it rides
#: into a correction payload that already carries the whole beat.
CORRECTION_MESSAGE_MAX = 600


class Correction:
    """One campaign invariant a Director result broke, and what to do about it.

    Deliberately a VALUE rather than a mutation handle. A validator that could
    edit the result directly would be a second author of objective causality,
    and the Director would have no idea its answer had been changed underneath
    it -- the correction it never saw could not teach it anything, and the next
    beat would break the same rule again. So a validator states what is wrong
    and the DIRECTOR fixes it, which is the same bargain every other retry in
    this stage makes (player-act authority, world pressure, the omission
    repair): name the violation, hand it back, re-check the answer.
    """

    def __init__(self, code, message, evidence=None):
        self.code = str(code or "").strip() or "violation"
        message = str(message or "").strip()
        if len(message) > CORRECTION_MESSAGE_MAX:
            raise ExtensionError(
                f"correction message is {len(message)} characters; the ceiling "
                f"is {CORRECTION_MESSAGE_MAX}. It rides a payload that already "
                "carries the whole beat.")
        self.message = message
        # Serialisable or it does not travel: this ends up in a model payload
        # and on the durable turn, and an object that survives neither is a
        # violation nobody can read afterwards.
        try:
            json.dumps(evidence)
        except (TypeError, ValueError):
            raise ExtensionError(
                f"correction {self.code!r} evidence must be JSON-serialisable")
        self.evidence = evidence

    def as_dict(self, ext_id="", name=""):
        out = {"extension": str(ext_id), "validator": str(name),
               "code": self.code, "message": self.message}
        if self.evidence is not None:
            out["evidence"] = self.evidence
        return out

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<Correction {self.code!r}>"


class DirectorResult:
    """What an `on_director_result` validator receives: the settled beat.

    The MERGED result, after every one of this engine's own deterministic
    floors has run -- player-act authority, the movement backstop, the
    passability floor, the reconciliation repair. A validator therefore judges
    what would actually be committed, not a prose-author draft and not one
    specialist's fragment.

    Read-only by construction: `resolve` and `interpret` are deep copies, so a
    validator that edits what it was handed changes nothing. That is not
    distrust, it is the same reason `StepView` is not a `PipelineContext` --
    the shape of the object should make the wrong thing hard rather than
    forbidden.

    No model handle. A validator is deterministic code; a campaign invariant
    that needs a model call to evaluate is not an invariant, and paying for one
    inside the beat's wall clock to decide whether the beat may finish is the
    cost this seam exists to avoid.
    """

    def __init__(self, api, ctx, result):
        import copy

        self.api = api
        chat = getattr(ctx, "chat", None)
        turn = getattr(ctx, "turn", None)
        self.chat_id = getattr(chat, "id", None)
        self.turn_idx = getattr(turn, "idx", None)
        self.turn_id = getattr(turn, "id", None)
        self.resolve = copy.deepcopy(result if isinstance(result, dict) else {})
        try:
            self.interpret = copy.deepcopy(ctx.get("director_interpret") or {})
        except Exception:
            self.interpret = {}

    @property
    def state_diff(self):
        value = self.resolve.get("state_diff")
        return value if isinstance(value, dict) else {}

    @property
    def resolved_event(self):
        return str(self.resolve.get("resolved_event") or "")

    @property
    def positions(self):
        value = self.state_diff.get("positions")
        return value if isinstance(value, dict) else {}

    def story_view(self):
        """The canonical read, for a rule that needs the world around the beat."""
        return self.api.story_view(self.chat_id)

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<DirectorResult chat={self.chat_id} turn={self.turn_idx}>"


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

#: Step-key namespaces an anchor may not name, because the planner has no
#: single position to splice beside. `character:<id>` is the runtime's
#: reserved dynamic namespace, planned as a PARALLEL GROUP -- splicing into
#: the middle of one would silently serialize it. `ext:<id>:<key>` is another
#: extension's stage, which is itself only spliced in during this same pass
#: and so is not in the plan when anchors are resolved.
#:
#: Refused here rather than dropped by the planner: a stage anchored on one
#: of these used to register cleanly, appear in `registered_stages()`, and
#: never run on any turn, with nothing anywhere saying so.
_UNSPLICEABLE_ANCHOR_PREFIXES = ("character:", "ext:")


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
        from core.db import q, qi, transaction
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
        from core.db import q, wget

        found = []
        for row in q("SELECT id, name FROM chats ORDER BY id DESC"):
            stored = wget(row["id"], f"ext:{self._api.id}:provisioned")
            if isinstance(stored, dict):
                found.append({"chat_id": row["id"], "name": row["name"],
                              "provenance": dict(stored)})
        return found

    def turns(self, chat_id, limit=20):
        """Recent committed turns of one story, oldest last."""
        from core.db import q

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
        if core.strip().startswith(_UNSPLICEABLE_ANCHOR_PREFIXES):
            raise ExtensionError(
                f"stage {key!r} anchor {anchor!r} names a step the plan "
                f"cannot splice beside; anchor on a core step key")
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
                                role="default", label=None,
                                list_channels=None):
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

        `list_channels` names the subset of `channels` whose value is a LIST.
        The merge coerces every other channel to a keyed table, so an undeclared
        list arrives as `{}` -- your family dispatched, paid for and discarded
        with nothing said. Declare the shape or return a dict.
        """
        from agents.director import register_specialist
        from . import _record_specialist

        full = register_specialist(self.id, name, channels=channels,
                                   prompt=prompt, gate=gate, role=role,
                                   label=label, list_channels=list_channels)
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

    def correction(self, code, message, evidence=None):
        """Build the violation an `on_director_result` validator returns."""
        return Correction(code, message, evidence)

    def on_director_result(self, fn=None, *, on_error="warn"):
        """Validate the SETTLED Director result, and ask for one repair.

        `fn(result, info)` runs after every deterministic floor this engine
        owns, on the merged result that would otherwise be committed. Return
        `None` to accept it, or an `api.correction(...)` (or a list of them) to
        refuse it. A refusal buys exactly ONE re-resolution with every
        extension's violations attached, after which the whole stage -- floors
        included -- runs again over the new answer.

        The difference from `add_commit_domain` is the question being asked. A
        commit domain answers "may this transaction finish", and its only move
        is to roll the beat back: a turn is lost where a corrected turn was
        possible, and the explanation arrives after the whole pipeline has been
        paid for. This asks "is this a valid proposal, and can the Director
        repair it" -- in the retry the Director already understands. Keep the
        commit domain as the last safety net; do not make it the normal way to
        enforce a campaign rule.

        `on_error` governs BOTH the validator raising and a violation surviving
        the correction, and it defaults to `"warn"` for the reason every other
        seam here does: a broken extension must not cost a beat. `"fail"` opts
        into losing the turn instead, which is right only when the campaign
        being wrong is worse than the beat being lost -- and it is the setting a
        real invariant wants.

        Validators are deterministic code and receive no model handle, cannot
        mutate the result (`DirectorResult` hands over deep copies), and run in
        a stable order: by extension id, then by registration order within an
        extension.
        """
        if on_error not in ("warn", "fail"):
            raise ExtensionError(
                "on_director_result on_error must be 'warn' or 'fail'")
        from . import _record_result_validator

        if fn is None:
            def decorate(func):
                _record_result_validator(self.id, func, on_error)
                return func
            return decorate
        _record_result_validator(self.id, fn, on_error)
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

    def add_model_lane(self, name, *, label=None, description=None):
        """Declare a model lane of your own: a role that appears in the host's
        model settings with its own provider row, sampler and backups, instead
        of borrowing a host role. Returns the role string to pass to
        `llm_json`/`llm_text`.

        Borrowing was the previous state and it failed twice over: a call on
        `role="utility"` runs on whatever the host chose FOR UTILITY WORK
        (an extension has no row of its own to be configured on), and it is
        logged as utility spend, so "which model is looping" stops being
        answerable per lane -- the whole reason `_log_usage` keys on the role
        string. A lane of your own fixes both, and its blank row inherits
        `default` exactly the way every blank host row does, because that is
        what a host who leaves a row blank means.

        Three properties, each deliberate:

        * **The role is namespaced `ext:<your-id>:<name>`**, never appended to
          `providers.ROLES` -- that list is the host's fixed vocabulary, read
          all over the engine, and a mutable one would let an install shadow
          or retire a host role. A name that IS a host role (`director`,
          `narrator`, ...) is refused outright rather than namespaced into
          something legal: a settings row wearing a host role's name reads as
          that role's configuration, and the misread costs real money.
        * **Declaration buys the settings row, nothing else.** Resolution
          reads `agent_models` by role string, so the calls themselves would
          resolve without this method -- what an undeclared lane can never be
          is CONFIGURED, because the host's panel has no row to offer.
        * **Disable takes the row, not the host's configuration.** The lane
          registry empties with your registration, so no phantom row survives
          you in the panel -- but a stored configuration is the host's work
          and outlives you (`keep_orphan_lane_rows`), the same rule that
          leaves `world["ext:<id>"]` alone on remove. Re-enabling finds the
          lane configured as it was left.
        """
        name = str(name or "").strip()
        if not _STAGE_KEY.fullmatch(name):
            raise ExtensionError(f"invalid model lane name: {name!r}")
        from llm.providers import ROLES
        if name in ROLES:
            raise ExtensionError(
                f"model lane {name!r} is a host role; a lane needs a name of "
                "its own")
        role = f"ext:{self.id}:{name}"
        from . import _record_model_lane
        _record_model_lane(self.id, name, role,
                           label=str(label or f"{self.id} · {name}"),
                           description=str(description or ""))
        return role

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
        from llm.providers import chat_complete

        raw = chat_complete(
            role, str(system or ""),
            payload if isinstance(payload, str) else json.dumps(
                payload, ensure_ascii=False),
            temperature=temperature, max_tokens=max_tokens)
        return jparse(raw)

    def llm_text(self, system, user, *, role="utility", temperature=None,
                 max_tokens=8000):
        """The same call, unparsed, for an extension that wants prose."""
        from llm.providers import chat_complete

        return chat_complete(role, str(system or ""), str(user or ""),
                             temperature=temperature, json_mode=False,
                             max_tokens=max_tokens)

    # -- creating a story

    def provision_story(self, package, *, state=None, frame_state=None,
                        package_id="", package_version="",
                        player_authority=None, director_context=None,
                        narration_context=None, documents=None):
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

        `frame_state`, `director_context`, `narration_context` and `documents`
        are the rest of turn zero, and they are arguments rather than four
        calls afterwards because pressing Start must produce either a complete
        campaign or no campaign. The reference campaign used to provision and
        THEN install its Director rules; if that second write failed, the story
        stayed in the player's list -- playable, carrying its campaign state and
        its authority mode, and missing the one rule that made its sealed wing
        mean anything. That is not a race, it is failure atomicity, and the only
        cure is being inside the same transaction.

        Data rather than a callback, deliberately (the report that asked for
        this recommended the same and the reasoning holds): every value is
        validated before the archive is touched, nothing arbitrary executes
        inside a database transaction, and the whole bootstrap stays
        serialisable and lintable. A callback form can be added if some real
        campaign turns out to need initialisation that cannot be written down;
        until then it would be a general transaction handle wearing a narrower
        name.

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

        from core.db import transaction, wset

        payload = package
        if not isinstance(payload, dict):
            raise ExtensionError("provision_story needs an archive dict")

        # VALIDATE BEFORE THE ARCHIVE IS TOUCHED. Every one of these has its
        # own refusal -- an unknown Director phase, an oversized block, a bad
        # document path, an unserialisable value -- and finding out inside the
        # transaction would mean the rollback is doing work the caller could
        # have been told about before anything was created. The errors are also
        # simply better here: "unknown Director phase 'narrator'" is actionable,
        # "campaign package refused" is not.
        blocks = dict(director_context or {})
        for phase in blocks:
            DirectorBlock._phase(phase)
        for phase, text in blocks.items():
            text = str(text or "").strip()
            if text and len(text) > DIRECTOR_CONTEXT_MAX:
                raise ExtensionError(
                    f"Director {phase} context is {len(text)} characters; the "
                    f"ceiling is {DIRECTOR_CONTEXT_MAX}")
        narration = str(narration_context or "").strip()
        if len(narration) > NARRATION_CONTEXT_MAX:
            raise ExtensionError(
                f"narration context is {len(narration)} characters; the "
                f"ceiling is {NARRATION_CONTEXT_MAX}")
        docs = dict(documents or {})
        for path, value in docs.items():
            document_path(path)
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                raise ExtensionError(
                    f"document {path!r} is not JSON-serialisable")
        for label, value in (("state", state), ("frame_state", frame_state)):
            if value is None:
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                raise ExtensionError(f"{label} is not JSON-serialisable")

        with transaction():
            try:
                from web import app

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
                from core.db import qi

                qi("UPDATE chats SET name=? WHERE id=?", (wanted, chat_id))
                chat = dict(chat, name=wanted)
            if player_authority is not None:
                from story.scene import (PLAYER_AUTHORITY_MODES,
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
            if frame_state is not None:
                # Lands on the imported story's ACTIVE frame, which is the one
                # turn zero will run in -- the same frame every other
                # frame-scoped key written here would reach.
                self.frame_state(chat_id).set_now(frame_state)
            if blocks:
                self.director_context(chat_id).set(blocks)
            if narration:
                self.narration_context(chat_id).set(narration)
            for path, value in docs.items():
                self.documents(chat_id).put_now(path, value)
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
        from core.db import wget

        stored = wget(int(chat_id), f"ext:{self.id}:provisioned")
        return dict(stored) if isinstance(stored, dict) else None

    # -- reading the story

    def story_view(self, chat_id, *, events=None, frame_id=_LATEST_FRAME):
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

        `frame_id` selects the era the whole view is read in: omitted is the
        latest committed turn's frame, `None` is explicitly the present, an
        integer is a declared frame of THIS chat (anything else is refused).
        Composing several frame-sensitive reads into one DTO should go
        through `api.at_frame(...)` instead, which resolves the frame once
        for all of them.
        """
        from web import story_view as facade

        kwargs = {}
        if events is not None:
            kwargs["events"] = events
        if frame_id is not _LATEST_FRAME:
            kwargs["frame_id"] = _validate_frame(chat_id, frame_id)
        return facade.story_view(chat_id, **kwargs)

    def player_view(self, chat_id, viewer="player", *, memories=12,
                    frame_id=_LATEST_FRAME):
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

        `people` (schema 2) is the structured roster for a persistent crew or
        people interface: stable ids that never depend on display names,
        `identity_status` from the identity ledger and the perception stage's
        own delivery record, composer labels for unrecognised bodies, and an
        allowlisted `facts`/`fact_sources` pair carrying only authored-public
        card surfaces. Key your UI on `id` and join your own campaign state to
        it; do not join known-name strings to canonical cast data, which is
        the disclosure logic this field exists so you never re-implement.

        `api.viewers(chat_id)` lists the ids this accepts.

        `frame_id` follows `story_view`'s vocabulary exactly (omitted =
        latest turn's frame, `None` = the present, integer = a declared
        frame of this chat), the selection is reported back under `frame`,
        and a selected frame never widens the viewer's budget: the view is
        still built only from what the engine delivered to that viewer in
        that era. For a DTO composed of several reads, use
        `api.at_frame(...)`.
        """
        from web import story_view as facade

        kwargs = {"memories": memories}
        if frame_id is not _LATEST_FRAME:
            kwargs["frame_id"] = _validate_frame(chat_id, frame_id)
        return facade.player_view(chat_id, viewer, **kwargs)

    def at_frame(self, chat_id, frame_id=_LATEST_FRAME):
        """A read/write facade bound to exactly ONE frame of one story.

        THE way to build a projection out of several public reads. Each of
        `player_view`, `frame_state(...)` and `char_state(...)` is correct
        alone, and composing them on an HTTP route is where they disagreed:
        the first resolves the latest turn's frame, the others follow the
        ambient `active_frame_id`, which a route does not have. This
        resolves the frame ONCE and hands back an immutable
        `ExtensionFrameView` whose every read and write is that frame's::

            host = api.at_frame(chat_id)          # latest turn's frame
            player  = host.player_view("player")
            mission = host.frame_state().get() or {}
            crew    = host.char_state(person_id).get() or {}
            assert (player["frame"] or {}).get("id") == host.frame_id or (
                player["frame"] is None and host.frame_id is None)

        Omit `frame_id` for the latest committed turn's frame -- whatever
        frame the story is actually on (the present, for a story with no
        turns). Pass `None` explicitly for the implicit present era; pass an
        integer for a declared frame, verified to belong to this chat. A
        frame that exists but holds no turns yet is honoured: its views
        report `turn: None` beside that frame's own state.

        `api.state(chat_id)`, `api.documents(chat_id)` and `api.settings`
        stay off this object because they are chat-global (or install-
        global) by design; `api.frame_state(chat_id)` and
        `api.char_state(...)` keep their ambient behaviour for code running
        inside a pipeline turn, where the ambient frame IS the answer.
        """
        cid = int(chat_id)
        from core.db import q

        if not q("SELECT 1 FROM chats WHERE id=?", (cid,), one=True):
            raise ExtensionError(f"no chat {cid}")
        resolved = (_latest_frame_id(cid) if frame_id is _LATEST_FRAME
                    else _validate_frame(cid, frame_id))
        return ExtensionFrameView(self, cid, resolved)

    def viewers(self, chat_id):
        """Who this story can be projected for, as `{id, name, kind}`."""
        from web import story_view as facade

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

    def documents(self, chat_id=None):
        """JSON documents at logical paths -- `list`, `delete`, `verify`.

        The fifth persistence home, for the extension whose unit of state is
        a FILE rather than a value: a storage adapter ported from a host that
        kept JSON documents at logical paths, a campaign package library, an
        integrity screen that needs to enumerate and check what it stored.

        ```python
        docs = api.documents(chat_id)          # story scope
        docs.put_now("missions/epsilon", {...})  # or put(), gated, in a hook
        docs.get("missions/epsilon")
        docs.list("missions")     # [{path, size, sha256, revision, ...}]
        docs.verify()             # {"ok", "checked", "damaged": [...]}
        docs.delete_now("missions/epsilon")
        api.documents().put_now("library/campaign-3", {...})  # install scope
        ```

        `chat_id` given is STORY scope -- rows in the `world` KV, so the
        documents ride checkpoints, archives and branches with the rest of
        your namespace: a rewound beat takes its documents with it.
        `chat_id=None` is INSTALL scope -- rows in the settings table, like
        `api.settings`, deliberately outside story history: a campaign
        library exists before any story does, and a reroll must not delete
        it. See `DocumentStore` for the gate, the path rules and the
        ceilings, each with its reason.
        """
        return DocumentStore(self.id, chat_id)

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
    "ChatAccess", "Correction", "DirectorBlock", "DirectorContext",
    "DirectorResult", "DocumentStore",
    "ExtState", "ExtensionError", "ExtensionFrameView",
    "PSYCHOLOGY_STATE_KEYS", "PayloadContext",
    "Request", "SonderExtensionAPI", "StepView", "document_path",
    "enter_commit_scope", "in_commit_scope", "leave_commit_scope",
]
