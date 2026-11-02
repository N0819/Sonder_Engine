"""Portable chat archive HTTP routes and persistence service.

The archive boundary is deliberately separate from ``app.py``.  It owns the
versioned top-level document shape, resource matching, and the atomic
export/import workflow.  Branching still shares the lower-level remap
primitives that predate this module, so those are injected explicitly rather
than imported from ``app`` (which would create a circular dependency).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, ValidationError, validator

from llm.schemas import LenientModel

from persist.checkpoints import (global_key_remap, insert_world_tables,
                                 remap_global_keys)
from story.room_conversation import (dump_room_messages,
                                     restore_room_messages)
from story.character_schema import (
    character_name,
    new_uid,
    normalize_character_data,
    normalize_persona_data,
    persona_name,
)
from core.db import (
    _FRAME_KEY_SEP,
    forget_frame_eras,
    parse_scoped_world_key,
    q,
    qi,
    qtx,
    recover_scene_time_of_day,
    transaction,
    wset,
)
from mind.memory import (
    chat_lorebook_ids,
    dump_chat_memories,
    dump_lorebook,
    dump_lorebook_links,
    dump_lore_overlays,
    dump_memory_summaries,
    dump_memory_vectors,
    restore_chat_memories,
    restore_memory_vectors,
    restore_lorebook,
    restore_lorebook_links,
    restore_lore_overlays,
    restore_memory_summaries,
)


# The normalized world tables an archive carries whole, row for row. Named
# once because three places have to agree about them -- the export tuple, the
# import tuple, and `ChatArchiveData`'s field list -- and a table that is in
# two of the three is carried without being specified, or specified without
# being carried. Both were true here: seven of these nine were exported and
# imported and declared nowhere, surviving on `extra="allow"`.
WORLD_TABLES = (
    "world_events",
    "relationship_events",
    "world_entities",
    "world_placements",
    "world_conditions",
    "scheduled_events",
    "room_registry",
    "fiction_worlds",
    "fiction_locations",
)

# `world` keys that belong to this INSTALL rather than to the story, and must
# not leave it. An archive is a file a host hands to somebody else; a
# checkpoint or a branch is not, so these stay in both of those.
#
# `presence_id_namespace` (minted by `web/story_view.py`, spelled again here
# because `persist` does not import `web` -- `tests/test_archive_fidelity.py`
# holds the two spellings together) is the salt under every anonymous
# presence id. Every OTHER input to that hash is canonical data the caller
# can already read, so the salt is the entire reason a guessed identity
# cannot be confirmed by enumeration. It rode an archive twice: as its own
# `world` row, and again inside every checkpoint blob, which carries
# `snapshot_state`'s copy of the same table.
UNEXPORTED_WORLD_KEYS = frozenset({"presence_id_namespace"})


# WHERE A CHARACTER'S ROW ID LIVES IN A STORY'S WORLD STATE -- one table, read
# by every path that moves a story into another install: the import's live
# world and its world-table payloads, every checkpoint it carries
# (`web.app._remap_cp_blob`), and the export deciding which characters travel
# with the story. `characters.id` is the INSTALL's integer; an import
# re-creates the character under whatever id the importing install hands out,
# so every stored copy of the old number has to be rewritten through the
# import's map or it names whoever holds that number here. Measured (audit
# 2026-11-01, persistence F3): Mora became character 6, her stance graph
# stayed under `relationships:1`, and `get_relationships(.., 6)` read nothing
# about Hal while the remapped ledger still said why she distrusts him -- and
# a Charter body stayed bound to "1", a couple map's cast kept the old number.
#
# The engine spells the id in exactly these ways:
#   * a field named `char_id` -- its one field name for the id, in any record
#     (a Charter binding, a skip's whereabouts, an off-screen plan);
#   * a handle `<prefix><id>` -- the seat tokens of
#     `world.charter_model.MIND_SEED_PREFIXES` (`character:7`, `cast:7`),
#     which the greeting's `resolved` and a route's `seed_id` also use;
#   * a world KEY `relationships:<id>` -- one stance graph per mind;
#   * the keys of the per-character records named below;
#   * a couple map's `cast` lists (`world.spatial_frames.COUPLE_MAP_PREFIX`).
# A new per-character world record keyed by the id joins
# `CHARACTER_KEYED_WORLD_KEYS`; anything spelled the first two ways is covered
# wherever it sits. An id the map does not carry is DROPPED, never kept: the
# same number is a different person here.
CHARACTER_ID_FIELD = "char_id"
CHARACTER_ID_KEY_PREFIXES = ("relationships:",)
CHARACTER_KEYED_WORLD_KEYS = frozenset({
    "character_history_routes",       # story/greetings, world/charter_runtime
    "character_journey_histories",    # story/journey_history
    "charter_resident_histories",     # world/charter_history
})


def _character_row_id(value):
    """`value` as a character row id -- a positive integer or its decimal
    string -- else None: a sentinel `-1`, None, a name are not ids."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isascii() and text.isdigit():
            number = int(text)
            return number if number > 0 else None
    return None


def _handle_prefixes():
    """`(prefixes, initials)`: the seat-token prefixes, and the first
    letters any of them can start with, in either case -- a string starting
    with none of those is rejected before it is case-folded, because the walk
    below visits every string of a world whose Charter row alone has run to
    41 MB."""
    from world.charter_model import MIND_SEED_PREFIXES
    prefixes = tuple(p.casefold() for p in MIND_SEED_PREFIXES)
    initials = frozenset(c for p in prefixes for c in (p[:1], p[:1].upper()))
    return prefixes, initials


def _rekey_handle(text, new_id, spelling):
    """`(True, rewritten-or-None)` when `text` is a character handle,
    `(False, text)` otherwise. `character:player` is not a row id."""
    prefixes, initials = spelling
    if type(text) is not str or text[:1] not in initials:
        return False, text
    folded = text.casefold()
    for prefix in prefixes:
        if folded.startswith(prefix):
            old = _character_row_id(text[len(prefix):])
            if old is None:
                return False, text
            new = new_id(old)
            return True, (None if new is None else text[:len(prefix)] + str(new))
    return False, text


def _rekey_in_place(obj, new_id, spelling):
    """Pass every `char_id` field and every handle inside the container `obj`
    through `new_id(old) -> new | None`, IN PLACE; True when anything moved.
    A record keyed by a handle that maps to nobody is dropped, as is a list
    member; a field or a value becomes None.

    In place, and with strings rejected by their first letter, because it
    walks whole worlds: copying every node made it 4.4x a `json.loads` of the
    same world (0.71 s over 3.9 MB, measured 2026-11-01)."""
    initials = spelling[1]
    changed = False
    if type(obj) is dict:
        renames = None
        for key, value in obj.items():
            if key == CHARACTER_ID_FIELD:
                old = _character_row_id(value)
                if old is not None:
                    new = new_id(old)
                    moved = (None if new is None
                             else str(new) if type(value) is str else new)
                    if moved != value:
                        obj[key] = moved
                        changed = True
                    continue
            kind = type(value)
            if kind is dict or kind is list:
                if _rekey_in_place(value, new_id, spelling):
                    changed = True
            elif kind is str and value[:1] in initials:
                is_handle, mapped = _rekey_handle(value, new_id, spelling)
                if is_handle and mapped != value:
                    obj[key] = mapped
                    changed = True
            if type(key) is str and key[:1] in initials:
                is_handle, mapped = _rekey_handle(key, new_id, spelling)
                if is_handle and mapped != key:
                    renames = renames or []
                    renames.append((key, mapped))
        for old_key, new_key in renames or ():
            value = obj.pop(old_key)
            if new_key is not None:
                obj.setdefault(new_key, value)
            changed = True
        return changed
    if type(obj) is list:
        dropped = None
        for index, item in enumerate(obj):
            kind = type(item)
            if kind is dict or kind is list:
                if _rekey_in_place(item, new_id, spelling):
                    changed = True
            elif kind is str and item[:1] in initials:
                is_handle, mapped = _rekey_handle(item, new_id, spelling)
                if is_handle and mapped != item:
                    changed = True
                    if mapped is None:
                        dropped = dropped or []
                        dropped.append(index)
                    else:
                        obj[index] = mapped
        for index in reversed(dropped or ()):
            del obj[index]
        return changed
    return False


def _rekey_world(world, new_id):
    """Pass every character row id `world` holds -- by the table above --
    through `new_id`, IN PLACE, and return it. Values are objects (an
    archive's or a parsed checkpoint's world), never stored JSON text."""
    from world.spatial_frames import COUPLE_MAP_PREFIX
    spelling = _handle_prefixes()
    renames = []
    for key, value in list(world.items()):
        base, frame_id = parse_scoped_world_key(key)
        new_key = key
        prefix = next((p for p in CHARACTER_ID_KEY_PREFIXES if base.startswith(p)), None)
        if prefix is not None:
            old = _character_row_id(base[len(prefix):])
            if old is not None:
                new = new_id(old)
                new_key = None             # a stance hung on nobody here
                if new is not None:
                    new_key = prefix + str(new)
                    if frame_id is not None:
                        new_key = f"{new_key}{_FRAME_KEY_SEP}{frame_id}"
        if base in CHARACTER_KEYED_WORLD_KEYS and isinstance(value, dict):
            keyed = {}
            for record_key, record in value.items():
                old = _character_row_id(record_key)
                if old is None:
                    keyed[record_key] = record
                elif new_id(old) is not None:
                    keyed.setdefault(str(new_id(old)), record)
            value = world[key] = keyed
        if base.startswith(COUPLE_MAP_PREFIX) and isinstance(value, dict) \
                and isinstance(value.get("cast"), dict):
            value["cast"] = {
                side: [new_id(old) for old in map(_character_row_id, members or [])
                       if old is not None and new_id(old) is not None]
                for side, members in value["cast"].items()}
        if type(value) in (dict, list):
            _rekey_in_place(value, new_id, spelling)
        else:
            is_handle, mapped = _rekey_handle(value, new_id, spelling)
            if is_handle:
                world[key] = mapped
        if new_key != key:
            renames.append((key, new_key))
    for old_key, new_key in renames:
        value = world.pop(old_key)
        # Two old ids the import matched onto one character land on one key;
        # the first kept is as good as any, and neither is a stranger's.
        if new_key is not None:
            world.setdefault(new_key, value)
    return world


def _new_ids(char_idmap):
    """`new_id(old)` for an import's `{old: new}` character map."""
    table = {}
    for old, new in (char_idmap or {}).items():
        old, new = _character_row_id(old), _character_row_id(new)
        if old is not None and new is not None:
            table[old] = new
    return table.get


def remap_world_character_ids(world, char_idmap):
    """Rewrite, IN PLACE, every character row id `world` holds through
    `char_idmap` (`{old: new}`), dropping what does not map. A same-install
    branch passes None: its characters are shared rows and keep their ids."""
    if char_idmap is None or not isinstance(world, dict):
        return world
    return _rekey_world(world, _new_ids(char_idmap))


def remap_row_character_ids(rows, char_idmap):
    """The same table over the JSON columns (`payload`, `detail`) of
    normalized world-table rows, re-dumped only where something changed."""
    if char_idmap is None:
        return rows
    new_id, spelling = _new_ids(char_idmap), _handle_prefixes()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for field in ("payload", "detail"):
            text = row.get(field)
            if not isinstance(text, str) or not text:
                continue
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                continue
            if not isinstance(parsed, (dict, list)):
                continue
            if _rekey_in_place(parsed, new_id, spelling):
                row[field] = json.dumps(parsed, ensure_ascii=False)
    return rows


def world_character_ids(world):
    """Every character row id `world` holds, by the same table -- what an
    export must bundle so the import has an id to map each one to. Asked
    with the identity, so the walk moves nothing."""
    found = []

    def collect(old):
        if old not in found:
            found.append(old)
        return old
    if isinstance(world, dict):
        _rekey_world(world, collect)
    return found


def _exportable_world(rows):
    """`{key: value}` for the story's own world state, secrets removed."""
    return {row["key"]: json.loads(row["value"]) for row in rows
            if parse_scoped_world_key(row["key"])[0] not in UNEXPORTED_WORLD_KEYS}


def _exportable_checkpoint_blob(blob):
    """One checkpoint blob with the same keys removed from its `world` copy.

    Re-serialised only when something was actually dropped: a blob is the
    largest thing in the archive and every other byte of it must survive
    verbatim.
    """
    try:
        snapshot = json.loads(blob)
    except (TypeError, ValueError):
        return blob                       # unreadable here is unreadable later
    world = snapshot.get("world")
    if not isinstance(world, dict):
        return blob
    kept = {k: v for k, v in world.items()
            if parse_scoped_world_key(k)[0] not in UNEXPORTED_WORLD_KEYS}
    if len(kept) == len(world):
        return blob
    snapshot["world"] = kept
    return json.dumps(snapshot)


def _model_validate(model_type, value):
    """Validate on Pydantic 1.x and 2.x without version-specific callers."""
    validate = getattr(model_type, "model_validate", None)
    return validate(value) if validate is not None else model_type.parse_obj(value)


def _model_dump(model):
    """Dump on Pydantic 1.x and 2.x without changing the archive payload."""
    dump = getattr(model, "model_dump", None)
    return dump() if dump is not None else model.dict()


#: The version the EXPORTER writes and the highest one import accepts.
#: An archive stamped above this was produced by a newer engine and may
#: carry tables this binary does not enumerate -- and everything not
#: enumerated is silently dropped on import (extra="allow" keeps the keys
#: through validation, but nothing ever writes them; that exact failure
#: kept `stations` inert for 45 scenes, see ChatArchiveData's docstring).
#: Refusing with both versions named is strictly kinder than truncating.
ARCHIVE_VERSION = 4


class ChatArchiveData(LenientModel):
    """Typed, forward-compatible validation for the archive's top level.

    Rows remain dictionaries because their shapes track SQLite migrations and
    older exports can legitimately omit newer columns.  Extra top-level keys
    are retained so an older engine does not reject a newer archive merely for
    carrying data it does not yet understand.

    A ``LenientModel`` because this gate was stricter than the code behind
    it: ``import_chat`` reads ``data.get("resources") or {}`` and
    ``dict(data.get("world") or {})``, but the model refused ``world: []``
    outright and rejected the whole archive with a 400.  Pydantic 1 hid that
    by coercing an empty list to an empty mapping for free, so the
    intolerance only appeared on 2.x -- a hand-edited or third-party archive
    importing on one machine and not another.  A missing ``chat`` is still a
    hard failure: it has no default, and inventing one would import an
    archive that says nothing.
    """

    version: int = 1
    chat: dict[str, Any]
    frames: list[dict[str, Any]] = Field(default_factory=list)
    turns: list[dict[str, Any]] = Field(default_factory=list)
    world: dict[str, Any] = Field(default_factory=dict)
    participants: list[dict[str, Any]] = Field(default_factory=list)
    char_frames: list[dict[str, Any]] = Field(default_factory=list)
    memories: list[dict[str, Any]] = Field(default_factory=list)
    memory_summaries: list[dict[str, Any]] = Field(default_factory=list)
    # Content-addressed vectors the CHECKPOINTS reference. Declared, because an
    # undeclared field validates cleanly and is then silently dropped by
    # extra="ignore" -- the failure that kept `stations` inert for 45 scenes
    # and stripped every opening turn's authored attire. Without this an
    # imported story's checkpoints would restore with no vectors at all.
    memory_vectors: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    # Every name in WORLD_TABLES, because the archive carries every one of
    # them. Seven of the nine used to be absent here and rode in on
    # `extra="allow"` -- carried without being specified, which makes this
    # model a description of some of the archive rather than of the archive.
    world_events: list[dict[str, Any]] = Field(default_factory=list)
    relationship_events: list[dict[str, Any]] = Field(default_factory=list)
    world_entities: list[dict[str, Any]] = Field(default_factory=list)
    world_placements: list[dict[str, Any]] = Field(default_factory=list)
    world_conditions: list[dict[str, Any]] = Field(default_factory=list)
    scheduled_events: list[dict[str, Any]] = Field(default_factory=list)
    room_registry: list[dict[str, Any]] = Field(default_factory=list)
    fiction_worlds: list[dict[str, Any]] = Field(default_factory=list)
    fiction_locations: list[dict[str, Any]] = Field(default_factory=list)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    lorebook: dict[str, Any] | None = None
    lorebooks: list[dict[str, Any]] = Field(default_factory=list)
    resources: dict[str, Any] = Field(default_factory=dict)
    chat_personas: list[dict[str, Any]] = Field(default_factory=list)
    turn_player_inputs: list[dict[str, Any]] = Field(default_factory=list)
    lorebook_links: list[dict[str, Any]] = Field(default_factory=list)
    # ROOM CONVERSATION (story/room_conversation.py): the player's thread
    # with the Writers' Room, every era. Declared for the reason
    # `memory_vectors` is declared above: an undeclared field validates and
    # is silently dropped.
    room_messages: list[dict[str, Any]] = Field(default_factory=list)
    # LORE OVERLAYS (mind/memory_lore_entries.py): what this story changed
    # about the library entries it reads, portable by entry uid.
    lore_overlays: list[dict[str, Any]] = Field(default_factory=list)

    @validator(
        "frames",
        "turns",
        "participants",
        "char_frames",
        "memories",
        "memory_summaries",
        "memory_vectors",
        "events",
        *WORLD_TABLES,
        "checkpoints",
        "lorebooks",
        "chat_personas",
        "turn_player_inputs",
        "lorebook_links",
        "room_messages",
        "lore_overlays",
        pre=True,
        always=True,
    )
    def _legacy_null_list(cls, value):
        """Legacy archives occasionally serialized absent collections null."""
        return [] if value is None else value

    @validator("world", "resources", pre=True, always=True)
    def _legacy_null_mapping(cls, value):
        """Treat null migration-era mappings as empty mappings."""
        return {} if value is None else value

    class Config:
        extra = "allow"


class ChatImportRequest(LenientModel):
    """The POST envelope used by the browser and external clients."""

    data: dict[str, Any]

    class Config:
        extra = "allow"


@dataclass(frozen=True)
class ArchiveRemappers:
    """Shared branch/archive remap operations supplied by ``app.py``."""

    active_books: Callable[[dict[str, Any], dict[Any, Any]], dict[str, Any]]
    fixed_point_frames: Callable[[dict[str, Any], dict[Any, Any]], None]
    couple_frames: Callable[..., None]
    scheduled_event_frames: Callable[[list[dict[str, Any]], dict[Any, Any]], None]
    checkpoint_blob: Callable[..., dict[str, Any]]
    json_id_list: Callable[[Any], list[int]]
    frame_character_ids: Callable[[Any, dict[Any, Any]], str]


class ChatArchiveService:
    """Owns chat archive routes while preserving the original wire format."""

    def __init__(self, remappers: ArchiveRemappers):
        self._remap = remappers
        self.router = APIRouter()
        self.router.add_api_route(
            "/api/chats/{cid}/export",
            self.export_chat,
            methods=["GET"],
            name="chat_export",
        )
        self.router.add_api_route(
            "/api/chats/import",
            self.import_chat,
            methods=["POST"],
            name="chat_import",
        )

    def export_chat(self, cid: int):
        chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
        if not chat:
            raise HTTPException(404)

        export = {
            "version": ARCHIVE_VERSION,
            "chat": dict(chat),
            "frames": [],
            "turns": [],
            "world": {},
            "participants": [],
            "char_frames": [],
            "memories": [],
            "memory_summaries": [],
            "events": [],
            "checkpoints": [],
            "lorebook": None,
            "lorebooks": [],
            "lore_overlays": [],
        }
        export["frames"] = [
            dict(f) for f in q("SELECT * FROM frames WHERE chat_id=?", (cid,))
        ]
        export["char_frames"] = [
            dict(r)
            for r in q("SELECT * FROM chat_char_frames WHERE chat_id=?", (cid,))
        ]
        for turn in q(
            "SELECT * FROM turns WHERE chat_id=? ORDER BY idx", (cid,)
        ):
            turn_data = dict(turn)
            turn_data["steps"] = []
            for step in q(
                "SELECT * FROM steps WHERE turn_id=? ORDER BY ord", (turn["id"],)
            ):
                step_data = dict(step)
                step_data["variants"] = [
                    dict(variant)
                    for variant in q(
                        "SELECT id,step_id,content,created,active "
                        "FROM variants WHERE step_id=? ORDER BY id",
                        (step["id"],),
                    )
                ]
                turn_data["steps"].append(step_data)
            export["turns"].append(turn_data)

        export["world"] = _exportable_world(
            q("SELECT * FROM world WHERE chat_id=?", (cid,)))
        export["participants"] = [
            dict(row)
            for row in q("SELECT * FROM chat_chars WHERE chat_id=?", (cid,))
        ]
        export["memories"] = dump_chat_memories(cid)
        export["memory_summaries"] = dump_memory_summaries(cid)
        export["events"] = [
            dict(row)
            for row in q(
                "SELECT * FROM events WHERE chat_id=? ORDER BY id", (cid,)
            )
        ]
        export["checkpoints"] = [
            {
                "turn_idx": row["turn_idx"],
                "blob": _exportable_checkpoint_blob(row["blob"]),
                "created": row["created"],
                # the newest commit it holds (`persist.beat_order`)
                "commit_seq": row["commit_seq"],
            }
            for row in q(
                "SELECT * FROM checkpoints WHERE chat_id=? ORDER BY turn_idx",
                (cid,),
            )
        ]

        # Live normalized world tables keep world.scene/fixed_points aligned
        # with actual rows on the first post-import commit.
        for table in WORLD_TABLES:
            export[table] = [
                dict(row)
                for row in q(f"SELECT * FROM {table} WHERE chat_id=?", (cid,))
            ]

        export["chat_personas"] = [
            dict(row)
            for row in q("SELECT * FROM chat_personas WHERE chat_id=?", (cid,))
        ]
        export["turn_player_inputs"] = [
            dict(row)
            for row in q(
                "SELECT * FROM turn_player_inputs WHERE chat_id=?", (cid,)
            )
        ]
        # ROOM CONVERSATION (story/room_conversation.py).
        export["room_messages"] = dump_room_messages(cid)

        canon = chat["lorebook_id"]
        # Preserve owned books, attached library books, and retrieval-reachable
        # books.  An isolated child is owned data even when not reachable.
        archive_book_ids = []
        for lorebook_id in [
            canon,
            *(
                row["id"]
                for row in q(
                    "SELECT id FROM lorebooks WHERE chat_id=? "
                    "ORDER BY sort_order,id",
                    (cid,),
                )
            ),
            *(
                row["lorebook_id"]
                for row in q(
                    "SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?",
                    (cid,),
                )
            ),
            *chat_lorebook_ids(cid, enabled_only=False),
        ]:
            if lorebook_id is not None and lorebook_id not in archive_book_ids:
                archive_book_ids.append(lorebook_id)

        export["lorebook_links"] = dump_lorebook_links(archive_book_ids)
        for lorebook_id in archive_book_ids:
            lorebook = q(
                "SELECT * FROM lorebooks WHERE id=?", (lorebook_id,), one=True
            )
            if not lorebook:
                continue
            attachment = q(
                "SELECT enabled FROM chat_lorebooks "
                "WHERE chat_id=? AND lorebook_id=?",
                (cid, lorebook_id),
                one=True,
            )
            export["lorebooks"].append(
                {
                    "book": dict(lorebook),
                    "canon": lorebook_id == canon,
                    "enabled": attachment["enabled"] if attachment else 1,
                    # A LIBRARY book is bundled whole so an install that lacks
                    # it can create it, and flagged so one that has it (by
                    # `resource_uid`) links to its own copy instead.
                    "library": lorebook["chat_id"] is None,
                    "entries": dump_lorebook(lorebook_id),
                }
            )
        export["lore_overlays"] = dump_lore_overlays(cid)
        if canon:
            lorebook = q(
                "SELECT * FROM lorebooks WHERE id=?", (canon,), one=True
            )
            if lorebook:
                export["lorebook"] = {
                    "book": dict(lorebook),
                    "entries": dump_lorebook(canon),
                }

        # Embed every referenced character/persona so integer ids can be
        # remapped rather than accidentally resolving to unrelated local rows.
        char_ids = []
        for row in export["participants"] + export["char_frames"]:
            char_id = row.get("char_id")
            if char_id is not None and char_id not in char_ids:
                char_ids.append(char_id)
        for frame in export["frames"]:
            for char_id in (
                self._remap.json_id_list(frame.get("travelers"))
                + self._remap.json_id_list(frame.get("nonexistent_cast"))
            ):
                if char_id not in char_ids:
                    char_ids.append(char_id)
        # Every id the live world holds (a stance graph, a Charter binding, a
        # seat token, a keyed history): bundled so the import has a character
        # to map each one to, rather than dropping the reference.
        for char_id in world_character_ids(export["world"]):
            if char_id not in char_ids:
                char_ids.append(char_id)

        checkpoint_persona_ids = []
        for checkpoint in export["checkpoints"]:
            try:
                blob = (
                    json.loads(checkpoint["blob"])
                    if isinstance(checkpoint["blob"], str)
                    else checkpoint["blob"]
                )
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(blob, dict):
                continue
            for memory in blob.get("memories") or []:
                char_id = memory.get("char_id")
                if char_id is not None and char_id not in char_ids:
                    char_ids.append(char_id)
            for summary in blob.get("memory_summaries") or []:
                char_id = summary.get("char_id")
                if char_id is not None and char_id not in char_ids:
                    char_ids.append(char_id)
            for char_id in blob.get("chars") or {}:
                try:
                    char_id = int(char_id)
                except (TypeError, ValueError):
                    continue
                if char_id not in char_ids:
                    char_ids.append(char_id)
            for char_frame in blob.get("char_frames") or []:
                char_id = char_frame.get("char_id")
                if char_id is not None and char_id not in char_ids:
                    char_ids.append(char_id)
            for frame in blob.get("frames") or []:
                for char_id in (
                    self._remap.json_id_list(frame.get("travelers"))
                    + self._remap.json_id_list(frame.get("nonexistent_cast"))
                ):
                    if char_id not in char_ids:
                        char_ids.append(char_id)
            for roster_row in blob.get("chat_personas") or []:
                persona_id = roster_row.get("persona_id")
                if (
                    persona_id is not None
                    and persona_id not in checkpoint_persona_ids
                ):
                    checkpoint_persona_ids.append(persona_id)

        characters = []
        for char_id in char_ids:
            character = q(
                "SELECT * FROM characters WHERE id=?", (char_id,), one=True
            )
            if not character:
                continue
            characters.append(
                {
                    "old_id": char_id,
                    "resource_uid": character["resource_uid"],
                    "sheet": json.loads(character["sheet"]),
                    "source": json.loads(character["source"] or "{}"),
                }
            )

        persona = None
        if chat["persona_id"]:
            persona_row = q(
                "SELECT * FROM personas WHERE id=?",
                (chat["persona_id"],),
                one=True,
            )
            if persona_row:
                persona = {
                    "old_id": chat["persona_id"],
                    "resource_uid": persona_row["resource_uid"],
                    "sheet": json.loads(persona_row["sheet"]),
                    "source": json.loads(persona_row["source"] or "{}"),
                }

        extra_personas = []
        seen_persona_ids = (
            {chat["persona_id"]} if chat["persona_id"] else set()
        )
        for persona_id in [
            *(row.get("persona_id") for row in export["chat_personas"]),
            *checkpoint_persona_ids,
        ]:
            if persona_id is None or persona_id in seen_persona_ids:
                continue
            seen_persona_ids.add(persona_id)
            persona_row = q(
                "SELECT * FROM personas WHERE id=?", (persona_id,), one=True
            )
            if not persona_row:
                continue
            extra_personas.append(
                {
                    "old_id": persona_id,
                    "resource_uid": persona_row["resource_uid"],
                    "sheet": json.loads(persona_row["sheet"]),
                    "source": json.loads(persona_row["source"] or "{}"),
                }
            )
        export["resources"] = {
            "persona": persona,
            "characters": characters,
            "extra_personas": extra_personas,
        }

        # Validate our own boundary without filtering migration-era or
        # forward-compatible fields from the returned dictionary.
        _model_validate(ChatArchiveData, export)
        # Vectors the CHECKPOINTS reference by content address. A checkpoint
        # carries `vkey` rather than the payload (memory.dump_chat_memories),
        # and the importing database has no such store -- so the referenced
        # vectors travel with the archive, deduped. That is what the addressing
        # buys here too: one story's checkpoints held 1.00 GB of duplicated
        # vectors and only 13 MB of distinct ones.
        wanted = set()
        for checkpoint in export["checkpoints"]:
            try:
                blob = (json.loads(checkpoint["blob"])
                        if isinstance(checkpoint["blob"], str)
                        else checkpoint["blob"])
            except (json.JSONDecodeError, TypeError):
                continue
            for mem in (blob or {}).get("memories") or []:
                if isinstance(mem, dict) and mem.get("vkey"):
                    wanted.add(mem["vkey"])
        export["memory_vectors"] = dump_memory_vectors(sorted(wanted))
        return export

    def import_chat(
        self,
        body: dict[str, Any] = Body(...),
    ):
        # Keep the original route's dict body contract (including its 400
        # response for a missing/non-object ``data`` member), then validate
        # that dictionary through the typed request model internally.
        if not isinstance(body.get("data"), dict):
            raise HTTPException(400, "No chat data provided")
        try:
            typed_request = _model_validate(ChatImportRequest, body)
        except ValidationError:
            raise HTTPException(400, "No chat data provided")
        archive = typed_request.data

        if archive.get("schema") == "fiction-engine.chat":
            data = archive.get("data") or archive
        else:
            data = archive

        # Tolerate a bare {"data": {...}} envelope even without the schema
        # marker.  Bundled/legacy exports and the frontend have both used it.
        if (
            "chat" not in data
            and isinstance(data.get("data"), dict)
            and "chat" in data["data"]
        ):
            data = data["data"]

        if "chat" not in data:
            raise HTTPException(400, "Chat archive has no chat object")
        try:
            typed_data = _model_validate(ChatArchiveData, data)
        except ValidationError as exc:
            raise HTTPException(400, "Invalid chat archive") from exc
        # Refuse a FUTURE archive before any write happens: import only
        # lands the tables this binary enumerates, so a newer archive would
        # come in 200 OK minus whatever the newer engine added -- silent
        # truncation presented as success. Checked here, before the
        # transaction opens, so a refusal writes nothing at all.
        if typed_data.version > ARCHIVE_VERSION:
            raise HTTPException(
                400,
                f"Chat archive is version {typed_data.version}, but this "
                f"engine reads archives up to version {ARCHIVE_VERSION}. "
                "Importing it would silently drop the newer data; update "
                "the engine first.",
            )

        # Pydantic retains unknown keys under extra="allow".  Using the model's
        # dictionary supplies safe defaults for fields absent in old archives.
        data = _model_dump(typed_data)
        resources = data.get("resources") or {}

        with transaction():
            persona_id = self._import_or_match_persona(resources.get("persona"))

            old_char_map = {}
            for resource in resources.get("characters") or []:
                old_id = resource.get("old_id")
                new_id = self._import_or_match_character(resource)
                if old_id is not None:
                    old_char_map[old_id] = new_id

            source_chat = data["chat"]

            persona_idmap = {}
            if source_chat.get("persona_id") and persona_id is not None:
                persona_idmap[source_chat["persona_id"]] = persona_id
            for resource in resources.get("extra_personas") or []:
                old_persona_id = resource.get("old_id")
                new_persona_id = self._import_or_match_persona(resource)
                if old_persona_id is not None and new_persona_id is not None:
                    persona_idmap[old_persona_id] = new_persona_id

            if persona_id is None:
                old_persona_id = source_chat.get("persona_id")
                if old_persona_id:
                    existing = q(
                        "SELECT id FROM personas WHERE id=?",
                        (old_persona_id,),
                        one=True,
                    )
                    persona_id = existing["id"] if existing else None

            # branched_from is intentionally not portable: it contains raw
            # source chat ids used for a local backdrop directory.
            new_chat_id = qtx(
                "INSERT INTO chats(name,persona_id,scenario,created) "
                "VALUES(?,?,?,?)",
                (
                    (source_chat.get("name") or "Imported") + " (import)",
                    persona_id,
                    source_chat.get("scenario", ""),
                    time.time(),
                ),
            )

            frame_idmap = {}
            for frame in data.get("frames") or []:
                old_frame_id = frame.get("id")
                new_frame_id = qtx(
                    "INSERT INTO frames("
                    "chat_id,label,ordinal,kind,travelers,nonexistent_cast,"
                    "created,split_turn_idx,merged_turn_idx"
                    ") VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        new_chat_id,
                        frame.get("label") or "",
                        int(frame.get("ordinal") or 0),
                        frame.get("kind") or "other",
                        self._remap.frame_character_ids(
                            frame.get("travelers"), old_char_map
                        ),
                        self._remap.frame_character_ids(
                            frame.get("nonexistent_cast"), old_char_map
                        ),
                        frame.get("created", time.time()),
                        frame.get("split_turn_idx"),
                        frame.get("merged_turn_idx"),
                    ),
                )
                if old_frame_id is not None:
                    frame_idmap[old_frame_id] = new_frame_id

            # Resolve the self-referential parent only after all frames exist.
            for frame in data.get("frames") or []:
                old_frame_id = frame.get("id")
                old_parent_id = frame.get("parent_frame_id")
                if (
                    old_frame_id is not None
                    and old_parent_id is not None
                    and old_parent_id in frame_idmap
                ):
                    qtx(
                        "UPDATE frames SET parent_frame_id=? WHERE id=?",
                        (
                            frame_idmap[old_parent_id],
                            frame_idmap[old_frame_id],
                        ),
                    )
            # A frame's era is its parentage, and the parents land only
            # here: nothing remembered about these ids may outlive it.
            forget_frame_eras()

            turn_idmap = {}
            for turn in data.get("turns") or []:
                new_turn_id = qtx(
                    "INSERT INTO turns(chat_id,idx,player_input,created,frame_id,commit_seq,"
                    "offscreen) VALUES(?,?,?,?,?,?,?)",
                    (
                        new_chat_id,
                        turn["idx"],
                        turn.get("player_input", ""),
                        turn.get("created", time.time()),
                        frame_idmap.get(turn.get("frame_id")),
                        turn.get("commit_seq"),
                        turn.get("offscreen"),
                    ),
                )
                turn_idmap[turn.get("id")] = new_turn_id

                for step in turn.get("steps") or []:
                    new_step_id = qtx(
                        "INSERT INTO steps(turn_id,key,label,ord,stale) "
                        "VALUES(?,?,?,?,?)",
                        (
                            new_turn_id,
                            step["key"],
                            step.get("label", ""),
                            step.get("ord", 0),
                            step.get("stale", 0),
                        ),
                    )

                    active_seen = False
                    for variant in step.get("variants") or []:
                        active = bool(variant.get("active", 0))
                        if active and active_seen:
                            active = False
                        active_seen = active_seen or active
                        # `reasoning` is deliberately NOT carried across the
                        # portable archive boundary. It is a thinking model's
                        # private trace: large, unvalidated, and nothing the
                        # fiction ever ratified. It is worth keeping locally
                        # to debug the run that produced it and worth nothing
                        # to whoever imports the story. Imports therefore land
                        # with the column at its default, which is correct
                        # rather than lossy -- there is no reasoning for a beat
                        # this machine did not generate.
                        qtx(
                            "INSERT INTO variants("
                            "step_id,content,created,active"
                            ") VALUES(?,?,?,?)",
                            (
                                new_step_id,
                                self._variant_content(variant.get("content")),
                                variant.get("created", time.time()),
                                int(active),
                            ),
                        )

            for participant in data.get("participants") or []:
                old_char_id = participant.get("char_id")
                new_char_id = old_char_map.get(old_char_id)
                if new_char_id is None:
                    existing = q(
                        "SELECT id FROM characters WHERE id=?",
                        (old_char_id,),
                        one=True,
                    )
                    if existing:
                        new_char_id = existing["id"]
                if new_char_id is None:
                    raise HTTPException(
                        400,
                        f"Chat archive references character {old_char_id} "
                        f"but does not embed it",
                    )
                override_sheet = participant.get("sheet")
                if override_sheet is not None:
                    try:
                        if isinstance(override_sheet, str):
                            override_sheet = json.loads(override_sheet)
                        if not isinstance(override_sheet, dict):
                            raise ValueError("card override is not an object")
                        override_sheet = json.dumps(
                            normalize_character_data(override_sheet),
                            ensure_ascii=False,
                        )
                    except (json.JSONDecodeError, TypeError, ValueError) as exc:
                        raise HTTPException(
                            400,
                            f"Invalid story card for character {old_char_id}",
                        ) from exc
                qtx(
                    "INSERT INTO chat_chars"
                    "(chat_id,char_id,status,state,sheet,dialogue_color) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        new_chat_id,
                        new_char_id,
                        participant.get("status", "active"),
                        participant.get("state", "{}"),
                        override_sheet,
                        # Absent in archives written before v29; '' is the
                        # live default and means "derive from the card", so an
                        # older story imports looking exactly as it did.
                        participant.get("dialogue_color") or "",
                    ),
                )

            for char_frame in data.get("char_frames") or []:
                new_char_id = old_char_map.get(char_frame.get("char_id"))
                new_frame_id = frame_idmap.get(char_frame.get("frame_id"))
                if new_char_id is None or new_frame_id is None:
                    continue
                qtx(
                    "INSERT INTO chat_char_frames("
                    "chat_id,char_id,frame_id,status,state"
                    ") VALUES(?,?,?,?,?)",
                    (
                        new_chat_id,
                        new_char_id,
                        new_frame_id,
                        char_frame.get("status", "active"),
                        char_frame.get("state", "{}"),
                    ),
                )

            bookmap = {}
            new_canon = None
            books = data.get("lorebooks")
            if books:
                # Create all rows before resolving parent_id so archive order
                # cannot break a child-before-parent hierarchy.
                for book_data in books:
                    book = book_data.get("book", {})
                    if book_data.get("library"):
                        # A library book: link to this install's own by
                        # portable uid, else create it AS a library book and
                        # attach by reference. Never a chat copy.
                        existing = q(
                            "SELECT id FROM lorebooks WHERE resource_uid=? "
                            "AND chat_id IS NULL",
                            (book.get("resource_uid"),), one=True
                        ) if book.get("resource_uid") else None
                        if existing:
                            lib_id = existing["id"]
                        else:
                            lib_id = qtx(
                                "INSERT INTO lorebooks("
                                "name,chat_id,origin_id,book_type,summary,"
                                "resource_uid,parent_id,scope_world_id,"
                                "scope_location_id,inheritance_mode,"
                                "default_circles,sort_order,anchor_entity_id"
                                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (
                                    book.get("name") or "book", None, None,
                                    book.get("book_type") or "general",
                                    book.get("summary") or "",
                                    self._import_book_uid(book.get("resource_uid")),
                                    None,
                                    book.get("scope_world_id"),
                                    book.get("scope_location_id"),
                                    book.get("inheritance_mode") or "inherit",
                                    book.get("default_circles") or "[]",
                                    int(book.get("sort_order") or 0),
                                    book.get("anchor_entity_id"),
                                ),
                            )
                            restore_lorebook(lib_id, book_data.get("entries") or [])
                        if book.get("id"):
                            bookmap[book["id"]] = lib_id
                        qtx(
                            "INSERT OR IGNORE INTO chat_lorebooks("
                            "chat_id,lorebook_id,origin_id,enabled"
                            ") VALUES(?,?,NULL,?)",
                            (new_chat_id, lib_id,
                             1 if book_data.get("enabled", 1) else 0),
                        )
                        continue
                    new_book_id = qtx(
                        "INSERT INTO lorebooks("
                        "name,chat_id,origin_id,book_type,summary,resource_uid,"
                        "parent_id,scope_world_id,scope_location_id,"
                        "inheritance_mode,default_circles,sort_order,"
                        "anchor_entity_id,retired_turn_id"
                        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            book.get("name") or "book",
                            new_chat_id,
                            # Resolved in the second pass, through the
                            # archive's own book map (see there).
                            None,
                            book.get("book_type") or "general",
                            book.get("summary") or "",
                            self._import_book_uid(book.get("resource_uid")),
                            None,
                            book.get("scope_world_id"),
                            book.get("scope_location_id"),
                            book.get("inheritance_mode") or "inherit",
                            # The compartment is the difference between a
                            # secret and a leak, so it must survive an export
                            # -- an archive that drops it republishes the
                            # organisation's existence to everybody.
                            book.get("default_circles") or "[]",
                            int(book.get("sort_order") or 0),
                            book.get("anchor_entity_id"),
                            turn_idmap.get(book.get("retired_turn_id")),
                        ),
                    )
                    restore_lorebook(
                        new_book_id, book_data.get("entries") or []
                    )
                    if book.get("id"):
                        bookmap[book["id"]] = new_book_id
                    if book_data.get("canon"):
                        new_canon = new_book_id
                        qtx(
                            "UPDATE chats SET lorebook_id=? WHERE id=?",
                            (new_book_id, new_chat_id),
                        )
                    else:
                        qtx(
                            "INSERT INTO chat_lorebooks("
                            "chat_id,lorebook_id,origin_id,enabled"
                            ") VALUES(?,?,?,?)",
                            (
                                new_chat_id,
                                new_book_id,
                                None,
                                1 if book_data.get("enabled", 1) else 0,
                            ),
                        )

                for book_data in books:
                    book = book_data.get("book", {})
                    if book_data.get("library"):
                        continue
                    new_book_id = bookmap.get(book.get("id"))
                    if new_book_id is None:
                        continue
                    # `origin_id` is a ROW ID, and the source install's: a
                    # fork of another story's book names that book, and the
                    # same integer here can be an unrelated library book --
                    # `attach_lore` then read it as "already attached" and
                    # the host could never attach it (audit 2026-11-01,
                    # persistence F8). It survives only through this
                    # archive's own map, when the origin came along.
                    origin = bookmap.get(book.get("origin_id"))
                    qtx(
                        "UPDATE lorebooks SET parent_id=?, origin_id=? WHERE id=?",
                        (
                            bookmap.get(book.get("parent_id")),
                            origin,
                            new_book_id,
                        ),
                    )
                    qtx(
                        "UPDATE chat_lorebooks SET origin_id=? "
                        "WHERE chat_id=? AND lorebook_id=?",
                        (origin, new_chat_id, new_book_id),
                    )
            elif data.get("lorebook") and data["lorebook"].get("entries"):
                lorebook_data = data["lorebook"]
                book = lorebook_data.get("book", {})
                new_canon = qtx(
                    "INSERT INTO lorebooks("
                    "name,chat_id,origin_id,book_type,summary,resource_uid,"
                    "scope_world_id,scope_location_id,inheritance_mode,"
                    "default_circles,sort_order,anchor_entity_id,"
                    "retired_turn_id"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        (book.get("name") or "Imported canon") + " (import)",
                        new_chat_id,
                        # the SOURCE install's row id: no origin here (F8)
                        None,
                        book.get("book_type") or "general",
                        book.get("summary") or "",
                        self._import_book_uid(book.get("resource_uid")),
                        book.get("scope_world_id"),
                        book.get("scope_location_id"),
                        book.get("inheritance_mode") or "inherit",
                        book.get("default_circles") or "[]",
                        int(book.get("sort_order") or 0),
                        book.get("anchor_entity_id"),
                        turn_idmap.get(book.get("retired_turn_id")),
                    ),
                )
                restore_lorebook(new_canon, lorebook_data["entries"])
                old_book_id = book.get("id")
                if old_book_id:
                    bookmap[old_book_id] = new_canon
                qtx(
                    "UPDATE chats SET lorebook_id=? WHERE id=?",
                    (new_canon, new_chat_id),
                )

            # Carried through whole, with only the three id columns remapped
            # onto this database's rows -- the same shape the summaries
            # projection below uses. A hand-listed projection here would have
            # to track `dump_chat_memories` column by column, and whatever it
            # failed to name would be dropped in silence rather than fail:
            # that is how the inlined vectors (which exist precisely so an
            # import need not re-embed the whole bank, downgrading every
            # vector to the crc32 fallback on one provider hiccup) and the
            # post-appraisal encoding affect (not re-derivable from the row's
            # text, any more than importance or a recorded re-reading is) were
            # both thrown away here. `prepare_chat_memory_restore` names the
            # keys it accepts and supplies their defaults, so an unknown key
            # in an archive reaches no statement.
            memories = [
                {
                    **memory,
                    "char_id": old_char_map.get(memory.get("char_id")),
                    "turn_id": turn_idmap.get(memory.get("turn_id")),
                    "frame_id": frame_idmap.get(memory.get("frame_id")),
                }
                for memory in data.get("memories", [])
                if memory.get("content")
                and old_char_map.get(memory.get("char_id"))
            ]
            restore_chat_memories(new_chat_id, memories)

            summaries = [
                {**summary, "char_id": old_char_map[summary["char_id"]]}
                for summary in data.get("memory_summaries") or []
                if old_char_map.get(summary.get("char_id"))
            ]
            restore_memory_summaries(new_chat_id, summaries)

            # ROOM CONVERSATION (story/room_conversation.py): frame ids
            # remapped, a line of an era that did not come across dropped.
            restore_room_messages(
                new_chat_id, data.get("room_messages") or [],
                frame_idmap=frame_idmap)
            # LORE OVERLAYS: resolved by entry uid onto whichever library
            # rows this install holds; an overlay on an entry it lacks drops.
            restore_lore_overlays(
                new_chat_id, data.get("lore_overlays") or [],
                frame_idmap=frame_idmap)

            for event in data.get("events") or []:
                qtx(
                    "INSERT INTO events(chat_id,turn_id,content) "
                    "VALUES(?,?,?)",
                    (
                        new_chat_id,
                        turn_idmap.get(event.get("turn_id")),
                        event["content"],
                    ),
                )

            world = dict(data.get("world") or {})
            remapped_world = {}
            for key, value in world.items():
                base, key_frame_id = parse_scoped_world_key(key)
                if key_frame_id is None:
                    remapped_world[key] = value
                    continue
                new_frame_id = frame_idmap.get(key_frame_id)
                if new_frame_id is not None:
                    remapped_world[
                        f"{base}{_FRAME_KEY_SEP}{new_frame_id}"
                    ] = value
            world = remapped_world
            # Every character row id the world holds, by the one table
            # (`remap_world_character_ids`) -- the couple maps' casts among
            # them, which is why the frame rescope below is handed no
            # character map of its own.
            remap_world_character_ids(world, old_char_map)
            # The two world tables with a GLOBAL key get fresh ids, one map
            # for the live rows, the live world and every checkpoint below
            # (`checkpoints.GlobalKeyRemap`): an import of a story this
            # install still holds collided on `fiction_worlds.world_id`
            # (audit 2026-11-01, persistence F9). Every other world id is
            # `(chat_id, id)` and kept verbatim, as it always was here.
            global_keys = global_key_remap([data])
            if global_keys:
                world = remap_global_keys(world, global_keys)
            self._remap.active_books(world, bookmap)
            self._remap.fixed_point_frames(world, frame_idmap)
            self._remap.couple_frames(world, frame_idmap, None, persona_idmap)
            for key, value in world.items():
                wset(new_chat_id, key, value)

            # An archive written before the time-of-day split carries a scene
            # whose `time` is whatever passage phrase its last beat happened
            # to leave there, and the opening that actually named the time of
            # day -- which this import has already restored as a step. Same
            # recovery the database migration runs, on the one chat that just
            # arrived; a no-op for an archive written after the split.
            recover_scene_time_of_day(new_chat_id)

            world_tables = {
                table: [dict(row) for row in data.get(table) or []]
                for table in WORLD_TABLES
            }
            for entity in world_tables["world_entities"]:
                entity["created_turn_id"] = turn_idmap.get(
                    entity.get("created_turn_id")
                )
                entity["retired_turn_id"] = turn_idmap.get(
                    entity.get("retired_turn_id")
                )
            for event in world_tables["world_events"]:
                event["turn_id"] = turn_idmap.get(event.get("turn_id"))
                event["frame_id"] = frame_idmap.get(event.get("frame_id"))
            # A stance's history follows the character it belongs to. An id
            # that does not remap is DROPPED rather than carried across: the
            # same integer means a different person in the new chat, and
            # reattaching a grudge to whoever inherited the number is worse
            # than losing it.
            world_tables["relationship_events"] = [
                dict(row, char_id=old_char_map.get(row.get("char_id")),
                     frame_id=frame_idmap.get(row.get("frame_id")))
                for row in world_tables["relationship_events"]
                if old_char_map.get(row.get("char_id")) is not None
            ]
            for room in world_tables["room_registry"]:
                room["created_turn_id"] = turn_idmap.get(
                    room.get("created_turn_id")
                )
                room["retired_turn_id"] = turn_idmap.get(
                    room.get("retired_turn_id")
                )
                room["owning_book_id"] = bookmap.get(
                    room.get("owning_book_id")
                )
            self._remap.scheduled_event_frames(
                world_tables["scheduled_events"], frame_idmap
            )
            for table in WORLD_TABLES:
                remap_row_character_ids(world_tables[table], old_char_map)
                if global_keys:
                    world_tables[table] = remap_global_keys(
                        world_tables[table], global_keys)
            insert_world_tables(new_chat_id, world_tables)

            for roster_row in data.get("chat_personas") or []:
                new_persona_id = persona_idmap.get(
                    roster_row.get("persona_id")
                )
                if new_persona_id is None:
                    continue
                qtx(
                    "INSERT OR IGNORE INTO chat_personas("
                    "chat_id,persona_id,status,frame_id"
                    ") VALUES(?,?,?,?)",
                    (
                        new_chat_id,
                        new_persona_id,
                        roster_row.get("status", "active"),
                        frame_idmap.get(roster_row.get("frame_id")),
                    ),
                )
            for player_input in data.get("turn_player_inputs") or []:
                new_persona_id = persona_idmap.get(
                    player_input.get("persona_id")
                )
                if new_persona_id is None:
                    continue
                qtx(
                    "INSERT OR IGNORE INTO turn_player_inputs("
                    "chat_id,turn_idx,persona_id,input,created"
                    ") VALUES(?,?,?,?,?)",
                    (
                        new_chat_id,
                        player_input.get("turn_idx"),
                        new_persona_id,
                        player_input.get("input", ""),
                        player_input.get("created", time.time()),
                    ),
                )
            restore_lorebook_links(
                new_chat_id, bookmap, data.get("lorebook_links") or []
            )

            # Before the checkpoints that reference them. A checkpoint blob
            # carries content addresses, not payloads, so without these an
            # imported story could not roll back without re-embedding.
            restore_memory_vectors(data.get("memory_vectors") or [])

            for checkpoint in data.get("checkpoints") or []:
                blob = (
                    checkpoint["blob"]
                    if isinstance(checkpoint["blob"], str)
                    else json.dumps(checkpoint["blob"])
                )
                blob = json.loads(blob)
                remapped = self._remap.checkpoint_blob(
                    blob,
                    turn_idmap,
                    bookmap,
                    new_canon,
                    char_idmap=old_char_map,
                    persona_idmap=persona_idmap,
                    world_id_remap=global_keys,
                    frame_idmap=frame_idmap,
                )
                qtx(
                    "INSERT INTO checkpoints(chat_id,turn_idx,blob,created,commit_seq) "
                    "VALUES(?,?,?,?,?)",
                    (
                        new_chat_id,
                        checkpoint["turn_idx"],
                        json.dumps(remapped),
                        checkpoint.get("created", time.time()),
                        checkpoint.get("commit_seq"),
                    ),
                )

        return dict(
            q("SELECT * FROM chats WHERE id=?", (new_chat_id,), one=True)
        )

    @staticmethod
    def _variant_content(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value or {}, ensure_ascii=False)

    @staticmethod
    def _import_or_match_character(resource: dict[str, Any]) -> int:
        uid = resource.get("resource_uid")
        if uid:
            existing = q(
                "SELECT id FROM characters WHERE resource_uid=?",
                (uid,),
                one=True,
            )
            if existing:
                return existing["id"]

        sheet = normalize_character_data(resource.get("sheet") or {})
        uid = (
            uid
            or sheet.get("identity", {}).get("uid")
            or new_uid("char")
        )
        return qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (
                character_name(sheet),
                json.dumps(sheet, ensure_ascii=False),
                json.dumps(resource.get("source") or {}, ensure_ascii=False),
                time.time(),
                uid,
            ),
        )

    @staticmethod
    def _import_or_match_persona(
        resource: dict[str, Any] | None,
    ) -> int | None:
        if not resource:
            return None

        uid = resource.get("resource_uid")
        if uid:
            existing = q(
                "SELECT id FROM personas WHERE resource_uid=?",
                (uid,),
                one=True,
            )
            if existing:
                return existing["id"]

        sheet = normalize_persona_data(resource.get("sheet") or {})
        uid = (
            uid
            or sheet.get("identity", {}).get("uid")
            or new_uid("persona")
        )
        return qi(
            "INSERT INTO personas(name,sheet,source,resource_uid) "
            "VALUES(?,?,?,?)",
            (
                persona_name(sheet),
                json.dumps(sheet, ensure_ascii=False),
                json.dumps(resource.get("source") or {}, ensure_ascii=False),
                uid,
            ),
        )

    @staticmethod
    def _import_book_uid(uid: str | None) -> str:
        """Keep a portable uid only when this install does not own it."""
        if uid and not q(
            "SELECT id FROM lorebooks WHERE resource_uid=?",
            (uid,),
            one=True,
        ):
            return uid
        return new_uid("book")
