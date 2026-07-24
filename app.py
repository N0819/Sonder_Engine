import contextvars, json, queue, time, threading, os
import updates
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import guest_access as guest

import db
from db import q, qi, qtx, transaction, wget, wset, get_setting, set_setting, parse_scoped_world_key
from db import _FRAME_KEY_SEP
from providers import (
    chat_complete, chat_complete_async, token_sink, cancel_event,
    resolve_role, list_models, provider, agent_models,
    openrouter_routing, normalize_openrouter_routing, list_openrouter_endpoints,
    max_output_tokens, _coerce_max_output_tokens,
    MAX_OUTPUT_TOKENS_DEFAULT, MAX_OUTPUT_TOKENS_MIN, MAX_OUTPUT_TOKENS_MAX,
    DEFAULT_BASES, ROLES, SAMPLER_KEYS, DEFAULT_SAMPLERS, Aborted,
)
from pipeline_context import PipelineContext, ChatData, TurnData
from checkpoints import ensure_checkpoint, restore_checkpoint, snapshot_state, refresh_checkpoint, insert_world_tables
from frames import create_frame, get_frame, list_frames
import paradox
import greetings
from agents import (
    run_pipeline, request_abort, begin_pipeline,
    active_content, ABORTS, PipelineBusyError,
)
from character_schema import (
    character_export_document,
    character_name,
    default_character_data,
    default_persona_data,
    new_uid,
    normalize_character_data,
    normalize_persona_data,
    persona_export_document,
    persona_name,
)
from scene import dialogue_config, interaction_limits
from importers import (
    import_character, import_persona, import_lorebook,
    generate_character, generate_persona, generate_lore_entries,
    reinterpret_lorebook, resolve_import_card, draft_promoted_character,
    recover_greetings_from_source,
)
from commit import (commit_all, promotable_background_presences,
                    promote_background_character,
                    _known_name_roster, sync_room_registry_with_scene)
from prompts import presets, active_preset, get_prompt, DEFAULT_PROMPTS, nsfw_enabled
from memory import (
    add_lore, update_lore, delete_lore, LORE_CATEGORIES,
    LOREBOOK_TYPES, MEMORY_CATEGORIES, MEMORY_PROVENANCE, 
    LOREBOOK_LINK_TYPES, duplicate_lorebook_for_chat,
    list_memories, update_memory, delete_memory, add_memory,
    add_memories_batch,
    search_memories, build_character_memory_context,
    get_memory_summary, consolidate_character_memory,
    restore_chat_memories, restore_lorebook, dump_lorebook,
    dump_chat_memories, dump_memory_summaries, restore_memory_summaries,
    chat_lorebook_ids, delete_turn_memories,
    restore_lorebook_links, dump_lorebook_links,
    relationships_for_payload,
    dramatic_irony_feed, promise_ledger,
    dump_character_memories, import_character_memories,
)
from scene import persona_of, get_scene

# ---- App setup ----
# No CORS middleware: the frontend is always served same-origin from this
# same process (GET / -> static/index.html, no separate dev server or
# port). A wildcard allow_origins here bought nothing and meant any page
# open in the same browser could make credentialed cross-origin requests
# to localhost -- reading provider keys via /api/bootstrap, deleting
# chats, driving the pipeline -- the classic "localhost app + open CORS"
# drive-by. Add a specific allow_origins list back only if a real
# cross-origin caller (a separate dev server on another port, say) is
# ever actually needed.
def _startup_engine():
    db.init()
    port = os.environ.get("FICTION_ENGINE_PORT", "8008")
    # FICTION_ENGINE_RESET_HOST is the forgot-password escape hatch: wipe
    # the account (and every session) so /login shows first-run setup again.
    if os.environ.get("FICTION_ENGINE_RESET_HOST"):
        guest.reset_host_account()
    if not guest.host_account_exists():
        print(
            "\n"
            "Sonder Engine: no host account yet. Open "
            f"http://127.0.0.1:{port}/login to create your username and "
            "password (first run only).\n",
            flush=True,
        )
    else:
        print(
            "\n"
            "Sonder Engine: host account configured. Sign in at "
            f"http://127.0.0.1:{port}/login . If the password was lost, "
            "restart once with FICTION_ENGINE_RESET_HOST=1 to wipe the "
            "account and set it up again.\n",
            flush=True,
        )


@asynccontextmanager
async def lifespan(_app):
    _startup_engine()
    yield


app = FastAPI(title="Sonder Engine", version="1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---- Host/guest access control ----
# See guest_access.py's module docstring for the full security rationale.
# Every /api/* request must carry either a valid host session cookie
# (issued by /api/auth/setup or /api/auth/login) or a valid guest cookie
# (issued by redeeming a join code); anything else is rejected. This
# closes the "any webpage you visit can blindly POST to 127.0.0.1:8008"
# hole, not just the guest-classification one -- SameSite=Strict on the
# host cookie is what actually stops a forged cross-site request, not any
# inspection of where the request appears to come from.
HOST_COOKIE = "fe_host"
GUEST_COOKIE = "fe_guest"
HOST_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # matches guest.HOST_SESSION_TTL
PUBLIC_API_PATHS = {
    "/api/join", "/api/auth/status", "/api/auth/setup",
    "/api/auth/login", "/api/auth/logout",
}
GUEST_ALLOWED_API_PATHS = {"/api/guest/state", "/api/guest/input"}

@app.get("/guest")
def guest_page():
    # Deliberately its own small standalone page rather than the full SPA
    # shell -- reusing index.html would mean fighting the guest allowlist
    # in every one of chat.js/app.js/settings.js's calls instead of the
    # guest only ever being able to reach the two endpoints it needs.
    return FileResponse("static/guest.html")

@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.get("/login")
def login_page():
    # Standalone page like /guest: handles both first-run account setup
    # and sign-in, then redirects into the SPA once a session cookie is set.
    return FileResponse("static/login.html")

def _set_host_cookie(response: JSONResponse, token: str) -> JSONResponse:
    response.set_cookie(
        HOST_COOKIE, token, httponly=True, samesite="strict",
        max_age=HOST_COOKIE_MAX_AGE,
    )
    return response

@app.get("/api/auth/status")
def auth_status(request: Request):
    return {
        "setup_required": not guest.host_account_exists(),
        "authenticated": guest.verify_host_session(
            request.cookies.get(HOST_COOKIE)
        ),
    }

@app.post("/api/auth/setup")
def auth_setup(username: str = Body(""), password: str = Body("")):
    if guest.host_account_exists():
        return JSONResponse({"detail": "Account already exists"}, status_code=409)
    if not username.strip():
        return JSONResponse({"detail": "Username is required"}, status_code=400)
    if not password:
        return JSONResponse({"detail": "Password is required"}, status_code=400)
    token = guest.create_host_account(username, password)
    if token is None:
        return JSONResponse({"detail": "Account already exists"}, status_code=409)
    return _set_host_cookie(JSONResponse({"ok": True}), token)

@app.post("/api/auth/login")
def auth_login(username: str = Body(""), password: str = Body("")):
    if guest.login_rate_limited():
        return JSONResponse(
            {"detail": "Too many attempts, wait a minute"}, status_code=429
        )
    # Generic failure detail: don't reveal whether the username or the
    # password was the wrong half.
    if not guest.verify_host_login(username, password):
        return JSONResponse(
            {"detail": "Invalid username or password"}, status_code=401
        )
    token = guest.create_host_session()
    return _set_host_cookie(JSONResponse({"ok": True}), token)

@app.post("/api/auth/logout")
def auth_logout(request: Request):
    guest.destroy_host_session(request.cookies.get(HOST_COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(HOST_COOKIE)
    return response

@app.middleware("http")
async def access_control(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)
    if path in PUBLIC_API_PATHS:
        return await call_next(request)

    if guest.verify_host_session(request.cookies.get(HOST_COOKIE)):
        request.state.actor = "host"
        return await call_next(request)

    grant = guest.verify_guest_token(request.cookies.get(GUEST_COOKIE))
    if grant:
        if path not in GUEST_ALLOWED_API_PATHS:
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
        request.state.actor = "guest"
        request.state.guest_grant = grant
        return await call_next(request)

    return JSONResponse({"detail": "Unauthorized"}, status_code=401)


# ---- Helpers ----
import logging

_pipeline_logger = logging.getLogger("fiction_engine.pipeline")

def _require_chat_idle(chat_id: int):
    """Whole-chat exclusivity: no frame's pipeline may be running. Used
    for every operation that isn't safely frame-local under Stage A's
    concurrency model -- recompute (reroll/rerun/resume/step edit/step
    activate/turn delete), branch, export/import, and lorebook
    attach/detach (which touches checkpoints spanning every frame)."""
    # list() snapshots the keys atomically -- pipeline threads insert/pop
    # ABORTS entries concurrently, and iterating the live dict can raise
    # RuntimeError("dictionary changed size during iteration").
    if any(key[0] == chat_id for key in list(ABORTS)):
        raise HTTPException(
            409,
            "This chat still has an active pipeline. Abort it and wait for "
            "the aborted response before modifying turns.",
        )

def _require_frame_idle(chat_id: int, frame_id):
    """Frame-local exclusivity: only THIS frame's pipeline must be idle.
    Used for fresh turn creation only -- two frames each running their
    own turn concurrently is exactly the point of this feature; only a
    second overlapping attempt within the SAME frame is rejected."""
    if (chat_id, frame_id) in ABORTS:
        raise HTTPException(
            409,
            "This frame still has an active pipeline. Abort it and wait "
            "for the aborted response before submitting another turn.",
        )

def _begin_pipeline_or_409(chat_id: int, frame_id):
    """Thin wrapper translating begin_pipeline's PipelineBusyError into
    the same 409 the earlier _require_*_idle checks give -- those checks
    happen first for a fast, friendly rejection, but they're advisory:
    the ACTUAL race-closing gate is begin_pipeline's atomic check-then-
    register. Two near-simultaneous requests for the same (chat_id,
    frame_id) can both pass the earlier check; only one can win here."""
    try:
        return begin_pipeline(chat_id, frame_id)
    except PipelineBusyError:
        raise HTTPException(
            409,
            "A pipeline is already running for this. Abort it and wait "
            "for the aborted response before retrying.",
        )

def _stream(gen):
    """Drains `gen` (run_pipeline's generator) to completion on ONE
    dedicated thread running in ONE stable context, relaying each event
    through a queue -- rather than handing `gen` directly to
    StreamingResponse.

    Why this matters: Starlette drives a plain sync generator's `next()`
    calls through `iterate_in_threadpool`, which calls
    `anyio.to_thread.run_sync` separately for EVERY item -- and that
    copies a FRESH context for each call. A generator has no context of
    its own (confirmed empirically -- see db.py's active_frame_id
    comment), so anything the pipeline `.set()`s on a contextvar
    (active_frame_id, cancel_event) before its first yield is silently
    invisible by the second yield onward: the copy backing that second
    `next()` call was taken before the `.set()` ever happened. Every
    downstream `wget`/`wset` frame-scoping and every abort check would
    silently see the wrong frame (or none at all) for the rest of the
    turn -- exactly the cross-era leak this feature exists to prevent.

    Running `gen` on our own thread via one `context.run(...)` sidesteps
    this entirely: the thread's context is set up once and never
    swapped out mid-iteration, so `.set()` calls made inside `gen`
    (and inside the worker threads it itself spawns via
    contextvars.copy_context() in _stream_one/_stream_parallel, which
    copy FROM this same stable context) persist for the run's whole
    lifetime, matching exactly how the test suite already drives the
    pipeline via plain `for event in _run_pipeline(...)` iteration.
    """
    evt_queue = queue.Queue()
    DONE = object()

    def run():
        try:
            for evt in gen:
                evt_queue.put(evt)
        except Exception as exc:
            _pipeline_logger.exception("Pipeline stream failed")
            evt_queue.put({
                "type": "error",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "fatal": True,
            })
        finally:
            evt_queue.put(DONE)

    context = contextvars.copy_context()
    thread = threading.Thread(target=lambda: context.run(run))
    thread.start()

    def w():
        try:
            while True:
                evt = evt_queue.get()
                if evt is DONE:
                    return
                yield json.dumps(evt) + "\n"
        finally:
            thread.join()
    return StreamingResponse(w(), media_type="application/x-ndjson")

def _player_input(body: dict) -> str:
    value = body.get("input", "")

    if value is None or isinstance(value, bool):
        return ""

    return str(value)
    
def _clone_snapshot_entries(new_book_id: int, entries: list[dict]):
    cloned = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        item = dict(entry)
        item["entry_uid"] = new_uid("entry")
        cloned.append(item)
    restore_lorebook(new_book_id, cloned)

def _latest_turn(chat_id):
    """The latest turn ACROSS EVERY FRAME (global play order)."""
    return q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1", (chat_id,), one=True)

def _latest_turn_in_frame(chat_id, frame_id):
    return q(
        "SELECT * FROM turns WHERE chat_id=? AND frame_id IS ? ORDER BY idx DESC LIMIT 1",
        (chat_id, frame_id), one=True,
    )

def _other_frame_has_advanced_past(chat_id, frame_id, idx):
    return bool(q(
        "SELECT 1 FROM turns WHERE chat_id=? AND frame_id IS NOT ? AND idx>? LIMIT 1",
        (chat_id, frame_id, idx), one=True,
    ))

def _require_latest(turn):
    """Recompute (reroll/rerun/resume/step edit/delete) is gated on two
    things, not one: this must be the latest turn OF ITS OWN FRAME (not
    globally latest -- Stage A already makes per-frame turn creation
    genuinely concurrent, so a different frame having advanced further
    is normal, not a problem to block on), AND no OTHER frame may have
    advanced past this turn's play-order position.

    That second check is what keeps this safe without frame-sliced
    checkpoints (Stage B's original, much larger proposed shape):
    checkpoints/memories/chat_chars/world_entities remain chat-global,
    captured as a whole-chat snapshot at this turn's play-order moment.
    Restoring that snapshot is exactly correct PROVIDED nothing else in
    the chat has changed since -- which is precisely what "no other
    frame has advanced past this point" guarantees. When it doesn't
    hold, recompute here would silently roll back another frame's
    genuinely newer, unrelated progress, so it's refused with a clear
    reason instead. Whole-chat idle (_require_chat_idle, checked
    separately by every caller) closes the remaining race: nothing else
    can commit and invalidate this check between it passing and the
    actual checkpoint restore running.
    """
    frame_id = turn["frame_id"]
    lt = _latest_turn_in_frame(turn["chat_id"], frame_id)
    if not lt or lt["id"] != turn["id"]:
        raise HTTPException(409, "Only the latest turn in this frame can be recomputed.")
    if _other_frame_has_advanced_past(turn["chat_id"], frame_id, turn["idx"]):
        raise HTTPException(
            409,
            "Another frame has advanced since this turn. Recompute here "
            "would silently roll back that frame's progress too -- shared "
            "state (memories, cast, world entities) isn't sliced per frame "
            "in this version.",
        )

def _require_turn_resolved(chat_id, frame_id):
    """Refuse to start a new turn in this frame on top of THIS FRAME's
    latest turn if it still has an edited/incomplete step. Frame-scoped
    (unlike _latest_turn/_require_latest above) because this gates
    ordinary turn creation, which Stage A makes genuinely concurrent
    per-frame -- an incomplete edit in the past-era thread must not
    block the future-era thread from advancing. Without this check at
    all, editing an earlier step (which marks everything downstream
    stale) wouldn't stop the next turn from starting on top of it -- the
    edit would end up cosmetic, since the new turn's checkpoint
    snapshots world state derived from whichever content was actually
    committed, not the edit."""
    last = _latest_turn_in_frame(chat_id, frame_id)
    if not last:
        return
    from agents import resume_key_for_turn
    if resume_key_for_turn(last["id"], chat_id) is not None:
        raise HTTPException(
            409,
            "The latest turn in this frame has an edited or incomplete "
            "step. Resume or reroll it before starting a new turn.",
        )

def _delete_book(lid):
    qi("DELETE FROM lorebooks WHERE id=?", (lid,))

def _remap_active_books(world, bookmap):
    # active_books is frame-scoped (see db.py's FRAME_SCOPED_WORLD_KEYS),
    # so a checkpoint/export blob can hold both the bare "active_books"
    # key (present) AND per-frame "active_books<sep><frame_id>" keys --
    # remap every one of them, not just the bare present-frame key.
    for key in list(world.keys()):
        base, _ = parse_scoped_world_key(key)
        if base != "active_books":
            continue
        ab = world.get(key)
        if isinstance(ab, list):
            world[key] = [bookmap[x] for x in ab if x in bookmap]
    return world
    
def _remap_fixed_points_frames(world, frame_idmap):
    """fixed_points live as a world-KV list of dicts, each carrying a
    frame_id (which frame the anchor is scoped to). The generic world-id
    remap only touches entity/world/location STRING ids, so the integer
    frame_id would otherwise keep the source chat's value -- paradox
    scoping would then check the wrong frame. Remap it through
    frame_idmap (None/present stays present; an uncloned frame collapses
    to present rather than dangling)."""
    fps = world.get("fixed_points")
    if not isinstance(fps, list):
        return
    remapped = []
    for fp in fps:
        if not isinstance(fp, dict):
            remapped.append(fp)
            continue
        nfp = dict(fp)
        if fp.get("frame_id") is not None:
            nfp["frame_id"] = frame_idmap.get(fp.get("frame_id"))
        remapped.append(nfp)
    world["fixed_points"] = remapped

def _remap_scheduled_event_frames(rows, frame_idmap):
    """scheduled_events payloads carry an integer frame_id (which frame's
    simulation clock the event is due against -- see commit.py's
    commit_transit_sweep). Like fixed_points above, the generic world-id
    remap only touches STRING ids, so a cloned/imported chat's pending
    events would otherwise stay scoped to the SOURCE chat's frame ids and
    never fire. Remap in place (None/present stays present; an uncloned
    frame collapses to present rather than dangling)."""
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            payload = json.loads(row.get("payload") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and payload.get("frame_id") is not None:
            payload["frame_id"] = frame_idmap.get(payload.get("frame_id"))
            row["payload"] = json.dumps(payload, ensure_ascii=False)

def _branch_protected_identity_ids(chat_id, persona_id):
    """Identity strings that a branch's world-id remap must leave untouched: the
    cast characters' names + uids, and the player persona's name. These are the
    stable keys scene.positions uses for people (character_scene_keys /
    persona_name); a character is also projected into world_entities under its
    name, so without this protection the remap clobbers its position key."""
    protected = set()
    try:
        prow = q("SELECT sheet FROM personas WHERE id=?", (persona_id,), one=True) \
            if persona_id is not None else None
        if prow:
            ps = json.loads(prow["sheet"])
            protected.add((ps.get("identity") or {}).get("name") or persona_name(ps))
    except Exception:
        pass
    for c in q("SELECT ch.sheet AS sheet FROM chat_chars cc "
               "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,)):
        try:
            sh = json.loads(c["sheet"])
        except (TypeError, ValueError):
            continue
        ident = sh.get("identity") or {}
        for key in (ident.get("name"), ident.get("uid"), character_name(sh)):
            if key:
                protected.add(str(key))
    return protected


def _build_world_id_remap(blob, protected_ids=None):
    """Generate fresh IDs for all world entities/conditions/events/worlds/locations
    in a checkpoint blob. Returns a mapping of old_id -> new_id.

    `protected_ids` are identity strings that must NOT be remapped -- chiefly
    CHARACTER and player-persona identities (names/uids). A character positioned
    in the scene is looked up by its stable name/uid (character_scene_keys), but
    is ALSO projected into world_entities keyed by that same name; without this
    guard, remapping that world_entities row's id rewrote the scene.positions
    key from "Dr. Moon" to a fresh opaque uid, so the character no longer
    resolved to any room after a branch ("unspecified location" on the next
    turn). Object/entity ids remap freely; identity keys stay put."""
    import uuid

    protected = {str(p) for p in (protected_ids or set()) if p}
    remap = {}

    def reg(old_id):
        if old_id and old_id not in protected and old_id not in remap:
            remap[old_id] = uuid.uuid4().hex[:16]
        return remap.get(old_id) if old_id else old_id

    for ent in blob.get("world_entities") or []:
        reg(ent.get("entity_id"))
    for cond in blob.get("world_conditions") or []:
        reg(cond.get("condition_id"))
    for ev in blob.get("scheduled_events") or []:
        reg(ev.get("event_id"))
    for fw in blob.get("fiction_worlds") or []:
        reg(fw.get("world_id"))
    for fl in blob.get("fiction_locations") or []:
        reg(fl.get("location_id"))

    return remap

def _apply_world_id_remap(blob, remap):
    """Apply ID remapping to all world-state data in a checkpoint blob."""
    if not remap:
        return blob

    def deep_remap(obj):
        if isinstance(obj, str):
            return remap.get(obj, obj)
        if isinstance(obj, dict):
            new = {}
            for k, v in obj.items():
                nk = remap.get(k, k) if isinstance(k, str) else k
                new[nk] = deep_remap(v)
            return new
        if isinstance(obj, list):
            return [deep_remap(item) for item in obj]
        return obj

    for key in ("world_entities", "world_placements", "world_conditions",
                "scheduled_events", "room_registry",
                "fiction_worlds", "fiction_locations"):
        if blob.get(key):
            blob[key] = deep_remap(blob[key])
            _remap_row_json_fields(blob[key], remap)

    if isinstance(blob.get("world"), dict):
        new_world = {}
        for k, v in blob["world"].items():
            new_world[k] = deep_remap(v)
        blob["world"] = new_world

    return blob
    
def _deep_remap_ids(obj, remap):
    """Recursively remap exact string matches and dict keys."""
    if not remap:
        return obj
    if isinstance(obj, str):
        return remap.get(obj, obj)
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            nk = remap.get(k, k) if isinstance(k, str) else k
            new[nk] = _deep_remap_ids(v, remap)
        return new
    if isinstance(obj, list):
        return [_deep_remap_ids(item, remap) for item in obj]
    return obj

def _remap_row_json_fields(rows, remap):
    """Remap ids INSIDE the JSON-string columns of normalized world-table
    rows (payload/detail). _deep_remap_ids only rewrites exact string
    matches, so an entity id embedded in such a string -- e.g. a pending
    transit_arrival's payload.entity_id -- was never remapped: the branched
    chat's event then referenced the SOURCE chat's entity id and could only
    fire as a moot cancel. Parse, remap, and re-dump only when something
    actually changed, so untouched payloads stay byte-identical."""
    if not remap:
        return rows
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for field in ("payload", "detail"):
            value = row.get(field)
            if not isinstance(value, str) or not value:
                continue
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(parsed, (dict, list)):
                continue
            remapped = _deep_remap_ids(parsed, remap)
            if remapped != parsed:
                row[field] = json.dumps(remapped, ensure_ascii=False)
    return rows

def _remap_cp_blob(blob, turn_idmap, bookmap, fallback_canon,
                   char_idmap=None, world_id_remap=None, frame_idmap=None):
    frame_idmap = frame_idmap or {}
    for memory in blob.get("memories") or []:
        memory["turn_id"] = turn_idmap.get(memory.get("turn_id"))
        memory["frame_id"] = frame_idmap.get(memory.get("frame_id"))

    if isinstance(blob.get("world"), dict):
        # Retired-concept cleanup (see turn_branch's matching comment).
        blob["world"].pop("current_frame_id", None)
        for key in [k for k in blob["world"] if k.startswith("frame_bundle:")]:
            blob["world"].pop(key, None)
        remapped = {}
        for key, val in blob["world"].items():
            base, key_frame_id = parse_scoped_world_key(key)
            if key_frame_id is None:
                remapped[key] = val
                continue
            new_frame_id = frame_idmap.get(key_frame_id)
            if new_frame_id is not None:
                remapped[f"{base}{_FRAME_KEY_SEP}{new_frame_id}"] = val
        blob["world"] = remapped

    lore = blob.get("lore")
    if isinstance(lore, dict):
        old_id = lore.get("lorebook_id")
        lore["lorebook_id"] = bookmap.get(old_id) or fallback_canon

    for book in blob.get("lorebooks") or []:
        old_id = book.get("lorebook_id")
        old_parent_id = book.get("parent_id")
        book["lorebook_id"] = bookmap.get(old_id)
        book["parent_id"] = bookmap.get(old_parent_id)
        # Book retirement is stamped with a turn-row FK -- remap it like
        # world_entities.retired_turn_id below (null when the turn wasn't
        # cloned) or a cross-install restore FK-fails and aborts.
        if "retired_turn_id" in book:
            book["retired_turn_id"] = turn_idmap.get(book.get("retired_turn_id"))

    remapped_links = []
    for link in blob.get("lorebook_links") or []:
        source = bookmap.get(link.get("source_book_id"))
        target = bookmap.get(link.get("target_book_id"))
        if source is None or target is None or source == target:
            continue
        remapped = dict(link)
        remapped.pop("id", None)
        remapped["source_book_id"] = source
        remapped["target_book_id"] = target
        remapped_links.append(remapped)

    if "lorebook_links" in blob:
        blob["lorebook_links"] = remapped_links

    if isinstance(blob.get("world"), dict):
        _remap_active_books(blob["world"], bookmap)

    if char_idmap and blob.get("chars"):
        remapped_chars = {}
        for old_key, state in blob["chars"].items():
            try:
                old_id = int(old_key)
                new_key = str(char_idmap.get(old_id, old_id))
            except (ValueError, TypeError):
                new_key = str(old_key)
            remapped_chars[new_key] = state
        blob["chars"] = remapped_chars

    if blob.get("char_frames"):
        remapped_char_frames = []
        for cf in blob["char_frames"]:
            nfid = frame_idmap.get(cf.get("frame_id"))
            if nfid is None:
                continue
            ncf = dict(cf)
            ncf["frame_id"] = nfid
            if char_idmap:
                ncf["char_id"] = char_idmap.get(ncf.get("char_id"), ncf.get("char_id"))
            remapped_char_frames.append(ncf)
        blob["char_frames"] = remapped_char_frames

    # Frame rows and persona stations carry SOURCE-chat frame ids. Left
    # unmapped, _restore_frames PK-collides (500 forever) or DELETEs the
    # branch's own frames (cross-era collapse), and chat_personas re-attach
    # to foreign frame rows. Remap through frame_idmap; drop rows whose
    # frame wasn't cloned.
    if blob.get("frames"):
        remapped_frames = []
        for fr in blob["frames"]:
            nfid = frame_idmap.get(fr.get("id"))
            if nfid is None:
                continue
            nfr = dict(fr)
            nfr["id"] = nfid
            nfr["parent_frame_id"] = frame_idmap.get(fr.get("parent_frame_id"))
            remapped_frames.append(nfr)
        blob["frames"] = remapped_frames

    if blob.get("chat_personas"):
        remapped_personas = []
        for p in blob["chat_personas"]:
            old_fid = p.get("frame_id")
            if old_fid is not None and frame_idmap.get(old_fid) is None:
                # Stationed in a frame that wasn't cloned -- dropping the
                # row is safer than reattaching to a foreign frame id.
                continue
            np = dict(p)
            np["frame_id"] = frame_idmap.get(old_fid) if old_fid is not None else None
            remapped_personas.append(np)
        blob["chat_personas"] = remapped_personas

    # world_entities.created_turn_id/retired_turn_id are turn-row FKs, not
    # strings -- remap them through the turn idmap (null when the turn
    # wasn't cloned) or a cross-install restore FK-fails and aborts.
    for ent in blob.get("world_entities") or []:
        if "created_turn_id" in ent:
            ent["created_turn_id"] = turn_idmap.get(ent.get("created_turn_id"))
        if "retired_turn_id" in ent:
            ent["retired_turn_id"] = turn_idmap.get(ent.get("retired_turn_id"))

    # room_registry rows embed turn FKs (same rule as world_entities) plus
    # the owning book's INTEGER id, which the generic string remap below
    # never touches -- remap it through bookmap (None when the book wasn't
    # cloned; insert_world_tables also guards the FK).
    for rr in blob.get("room_registry") or []:
        if "created_turn_id" in rr:
            rr["created_turn_id"] = turn_idmap.get(rr.get("created_turn_id"))
        if "retired_turn_id" in rr:
            rr["retired_turn_id"] = turn_idmap.get(rr.get("retired_turn_id"))
        if "owning_book_id" in rr:
            rr["owning_book_id"] = bookmap.get(rr.get("owning_book_id"))

    if world_id_remap:
        for key in ("world_entities", "world_placements", "world_conditions",
                    "scheduled_events", "room_registry",
                    "fiction_worlds", "fiction_locations"):
            if blob.get(key):
                blob[key] = _deep_remap_ids(blob[key], world_id_remap)
                _remap_row_json_fields(blob[key], world_id_remap)
        if isinstance(blob.get("world"), dict):
            for k, v in list(blob["world"].items()):
                if isinstance(v, str):
                    try:
                        parsed = json.loads(v)
                        if isinstance(parsed, (dict, list)):
                            blob["world"][k] = json.dumps(
                                _deep_remap_ids(parsed, world_id_remap)
                            )
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(v, (dict, list)):
                    blob["world"][k] = _deep_remap_ids(v, world_id_remap)

    return blob
    
def _ensure_resource_uid(table: str, row_id: int, prefix: str):
    row = q(f"SELECT resource_uid FROM {table} WHERE id=?", (row_id,), one=True)
    if row and not row["resource_uid"]:
        qi(f"UPDATE {table} SET resource_uid=? WHERE id=?", (new_uid(prefix), row_id))

def _require_lorebook(lid: int):
    row = q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True)
    if not row:
        raise HTTPException(404, "Lorebook not found")
    return row

def _require_lore_entry(eid: int):
    row = q("SELECT * FROM lore_entries WHERE id=?", (eid,), one=True)
    if not row:
        raise HTTPException(404, "Lore entry not found")
    return row

def _lore_keys(value) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "")

def _stored_locations(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)

def _lore_entry_json(row) -> dict:
    return {
        "id": row["id"],
        "entry_uid": row["entry_uid"],
        "lorebook_id": row["lorebook_id"],
        "keys": row["keys"],
        "content": row["content"],
        "category": row["category"] or "other",
        "canon_locked": bool(row["canon_locked"]),
        "locked": bool(row["canon_locked"]),
        "turn_added": row["turn_added"],
        "title": row["title"],
        "knowledge_tag": row["knowledge_tag"],
        "knowledge_range": row["knowledge_range"],
        "knowledge_locations": row["knowledge_locations"],
        "importance": row["importance"],
        "aliases": row["aliases"],
        "scope": row["scope"],
        "relations": row["relations"],
        "source_notes": row["source_notes"],
    }

# ============================ BOOTSTRAP & SETTINGS ============================
@app.get("/api/bootstrap")
def bootstrap():
    return {
        "providers": [_provider_public(r["id"]) for r in q("SELECT id FROM providers")],
        "provider_presets": DEFAULT_BASES,
        "roles": ROLES,
        "sampler_keys": list(SAMPLER_KEYS),
        "default_samplers": DEFAULT_SAMPLERS,
        "lore_categories": LORE_CATEGORIES,
        "lorebook_types": LOREBOOK_TYPES,
        "memory_categories": MEMORY_CATEGORIES,
        "memory_provenance": MEMORY_PROVENANCE,
        "agent_models": json.loads(get_setting("agent_models") or "{}"),
        "max_output_tokens": max_output_tokens(),
        "openrouter_routing": openrouter_routing(),
        "max_output_tokens_bounds": {
            "default": MAX_OUTPUT_TOKENS_DEFAULT,
            "min": MAX_OUTPUT_TOKENS_MIN,
            "max": MAX_OUTPUT_TOKENS_MAX,
        },
        "characters": [dict(r) for r in q("SELECT id,name,sheet FROM characters")],
        "personas": [dict(r) for r in q("SELECT id,name,sheet FROM personas")],
        "lorebooks": [dict(r) for r in q("SELECT * FROM lorebooks WHERE chat_id IS NULL")],
        "chats": [dict(r) for r in q("SELECT * FROM chats ORDER BY id DESC")],
        "nsfw_enabled": get_setting("nsfw_enabled") == "1",
        "auto_promote": get_setting("auto_promote") != "0",
        "default_prompts": DEFAULT_PROMPTS,
        "prompt_presets": presets(),
        "active_preset": active_preset(),
        "lorebook_link_types": LOREBOOK_LINK_TYPES,
    }

@app.put("/api/agent_models")
def put_agent_models(body: dict = Body(...)):
    set_setting("agent_models", json.dumps(body))
    return {"ok": True}

@app.put("/api/openrouter_routing")
def put_openrouter_routing(body: dict = Body(...)):
    """Which upstream providers may serve an OpenRouter model.

    One OpenRouter model id is served by several upstreams (Anthropic direct,
    Bedrock, Azure, Vertex, third-party hosts) whose output quality AND
    prompt-retention policy differ, so this is a privacy control as much as a
    quality one. Normalized rather than trusted: it rides on every request and
    must never be able to make one invalid.
    """
    routing = normalize_openrouter_routing(body)
    set_setting("openrouter_routing", json.dumps(routing))
    return {"ok": True, "routing": routing}

@app.get("/api/openrouter/endpoints")
def get_openrouter_endpoints(provider_id: int, model: str):
    """The upstream providers actually serving one model, so the picker offers
    real choices instead of a slug the user has to know by heart."""
    prov = provider(provider_id)
    if not prov:
        raise HTTPException(404, "no such provider")
    try:
        return {"endpoints": list_openrouter_endpoints(prov, model)}
    except Exception as exc:
        raise HTTPException(502, f"could not list endpoints: {exc}")

@app.put("/api/max_output_tokens")
def put_max_output_tokens(body: dict = Body(...)):
    """The per-call output-token ceiling every LLM request is clamped to.
    Coerced into range rather than rejected -- this value gates every call, so
    a bad one must degrade to a usable number, not break generation."""
    value = _coerce_max_output_tokens(body.get("value"))
    set_setting("max_output_tokens", str(value))
    return {"ok": True, "value": value}

@app.put("/api/prompt_presets")
def save_preset(body: dict = Body(...)):
    ps = presets()
    ps[body["name"]] = body.get("prompts", {})
    set_setting("prompt_presets", json.dumps(ps))
    return {"ok": True}

@app.delete("/api/prompt_presets/{name}")
def del_preset(name: str):
    ps = presets()
    ps.pop(name, None)
    set_setting("prompt_presets", json.dumps(ps))
    if active_preset() == name:
        set_setting("active_preset", "Default")
    return {"ok": True}

@app.put("/api/active_preset")
def set_active(body: dict = Body(...)):
    set_setting("active_preset", body.get("name", "Default"))
    return {"ok": True}

@app.get("/api/nsfw")
def get_nsfw():
    return {"enabled": get_setting("nsfw_enabled") == "1"}

@app.put("/api/nsfw")
def set_nsfw(body: dict = Body(...)):
    set_setting("nsfw_enabled", "1" if body.get("enabled") else "0")
    return {"enabled": body.get("enabled", False)}

# ---- Self-update (host-only via the access-control middleware) ----
# Sync defs so FastAPI runs the blocking git/network work in its threadpool
# rather than on the event loop, matching every other route here.
@app.get("/api/updates/check")
def updates_check():
    return updates.check_updates()

@app.post("/api/updates/install")
def updates_install():
    return updates.install_updates()

# ============================ LOREBOOK TREE & LINKS ============================
from memory import (
    move_lorebook, reorder_lorebook,
    add_lorebook_link, update_lorebook_link, delete_lorebook_link,
    get_lorebook_links, restore_lorebook_links,
    LOREBOOK_LINK_TYPES,
)
from importers import generate_lorebook_plan, apply_lorebook_plan

@app.post("/api/lorebooks/{lid}/move")
def lorebook_move(lid: int, body: dict = Body(...)):
    _require_lorebook(lid)
    try:
        move_lorebook(lid, body.get("parent_id"), body.get("position"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}

@app.post("/api/lorebooks/{lid}/reorder")
def lorebook_reorder(lid: int, body: dict = Body(...)):
    _require_lorebook(lid)
    try:
        reorder_lorebook(lid, body.get("direction", "up"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}

@app.get("/api/lorebooks/{lid}/links")
def lorebook_links_get(lid: int):
    _require_lorebook(lid)
    return {"links": get_lorebook_links(lid)}

@app.post("/api/lorebooks/{lid}/links")
def lorebook_link_create(lid: int, body: dict = Body(...)):
    _require_lorebook(lid)
    target_id = body.get("target_book_id")
    if not target_id:
        raise HTTPException(400, "target_book_id is required")
    _require_lorebook(target_id)
    
    relation_type = body.get("relation_type", "related")
    if relation_type not in LOREBOOK_LINK_TYPES:
        raise HTTPException(400, f"Invalid relation_type. Must be one of: {', '.join(LOREBOOK_LINK_TYPES)}")
    
    link_id = add_lorebook_link(
        lid, target_id, relation_type,
        label=body.get("label", ""),
        notes=body.get("notes", ""),
        bidirectional=body.get("bidirectional", True),
        follow_for_retrieval=body.get("follow_for_retrieval", True),
        weight=body.get("weight", 0.75),
    )
    return {"id": link_id}

@app.put("/api/lorebook_links/{link_id}")
def lorebook_link_update(link_id: int, body: dict = Body(...)):
    update_lorebook_link(link_id, **body)
    return {"ok": True}

@app.delete("/api/lorebook_links/{link_id}")
def lorebook_link_delete(link_id: int):
    delete_lorebook_link(link_id)
    return {"ok": True}

@app.post("/api/lorebooks/{lid}/generate_plan")
def lorebook_generate_plan(lid: int, body: dict = Body(default={})):
    _require_lorebook(lid)
    brief = str(body.get("prompt") or body.get("brief") or "").strip()
    try:
        plan = generate_lorebook_plan(
            lid, brief,
            mode=body.get("mode", "expand_tree"),
            depth=body.get("depth", 2),
            entry_target=body.get("entry_target", 40),
            allow_new_books=body.get("allow_new_books", True),
            allow_links=body.get("allow_links", True),
            allow_updates=body.get("allow_updates", True),
            preserve_locked=body.get("preserve_locked", True),
        )
    except Exception as exc:
        raise HTTPException(502, f"Lore generation failed: {exc}") from exc
    return plan

@app.post("/api/lorebooks/{lid}/apply_plan")
def lorebook_apply_plan(lid: int, body: dict = Body(...)):
    _require_lorebook(lid)
    plan = body.get("plan")
    if not plan:
        raise HTTPException(400, "plan is required")
    
    # Ensure book ops are scoped to this lorebook's chat
    book = q("SELECT chat_id FROM lorebooks WHERE id=?", (lid,), one=True)
    chat_id = book["chat_id"] if book else None
    
    result = apply_lorebook_plan(plan, chat_id=chat_id)
    return {"ok": True, "result": result}

@app.post("/api/lorebooks/import")
def lore_import(body: dict = Body(...)):
    reinterpret = bool(body.get("reinterpret"))
    payload = (
        body.get("card")
        or body.get("payload")
        or body.get("book")
        or body.get("data")
        or body
    )

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            pass

    if not isinstance(payload, dict):
        payload = {}

    try:
        lid, count = import_lorebook(
            payload,
            name=body.get("name"),
            reinterpret=reinterpret,
            book_type=body.get("book_type"),
            summary=body.get("summary"),
        )
    except Exception as exc:
        raise HTTPException(
            502 if reinterpret else 400,
            f"Lorebook import failed: {exc}",
        ) from exc
    return {"id": lid, "imported": count}

# ============================ PROVIDERS ============================

def _provider_public(pid):
    # api_key never goes back to the frontend past creation -- CORS used to
    # be wide open (see app startup below), which turned "GET /api/bootstrap
    # returns every provider's plaintext key" into a real drive-by
    # exfiltration path for any page open in the same browser. has_key lets
    # the UI show "a key is set" without ever re-transmitting the secret.
    row = q("SELECT * FROM providers WHERE id=?", (pid,), one=True)
    if not row:
        return None
    d = dict(row)
    d["has_key"] = bool(d.pop("api_key", None))
    return d

@app.post("/api/providers")
def add_provider(body: dict = Body(...)):
    base = body.get("base_url") or DEFAULT_BASES.get(body.get("kind", "generic"), "")
    pid = qi("INSERT INTO providers(name,kind,base_url,api_key) VALUES(?,?,?,?)",
             (body.get("name") or body.get("kind"), body.get("kind", "generic"), base, body.get("api_key", "")))
    return _provider_public(pid)

@app.put("/api/providers/{pid}")
def put_provider(pid: int, body: dict = Body(...)):
    # An empty/omitted api_key means "leave it as-is", not "clear it" --
    # the frontend never has the real value to re-submit unchanged now that
    # it's no longer sent back, so a blank field must not wipe a working key.
    if not q("SELECT 1 FROM providers WHERE id=?", (pid,), one=True):
        raise HTTPException(404, "Provider not found")
    new_key = body.get("api_key") or None
    if new_key:
        qi("UPDATE providers SET name=?,kind=?,base_url=?,api_key=? WHERE id=?",
           (body.get("name", ""), body.get("kind", "generic"), body.get("base_url", ""), new_key, pid))
    else:
        qi("UPDATE providers SET name=?,kind=?,base_url=? WHERE id=?",
           (body.get("name", ""), body.get("kind", "generic"), body.get("base_url", ""), pid))
    return _provider_public(pid)

@app.delete("/api/providers/{pid}")
def del_provider(pid: int):
    qi("DELETE FROM providers WHERE id=?", (pid,))
    return {"ok": True}

@app.get("/api/providers/{pid}/models")
def models(pid: int):
    prov = provider(pid)
    if not prov: raise HTTPException(404)
    try: return {"models": list_models(prov)}
    except Exception as e: raise HTTPException(502, str(e))

# ============================ CHARACTERS ============================
@app.post("/api/characters/generate")
def char_generate(body: dict = Body(default={})):
    brief = str(body.get("prompt") or body.get("brief") or body.get("description") or "").strip()
    try:
        cid, sheet = generate_character(brief)
    except Exception as exc:
        raise HTTPException(502, f"Character generation failed: {exc}") from exc
    _ensure_resource_uid("characters", cid, "char")
    return {"id": cid, "sheet": sheet}

@app.post("/api/characters")
def char_create(body: dict = Body(...)):
    raw = body.get("sheet")
    if raw:
        sheet = normalize_character_data(raw)
    else:
        sheet = default_character_data(body.get("name") or "Unnamed")

    cid = qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            character_name(sheet),
            json.dumps(sheet, ensure_ascii=False),
            json.dumps({"format": "native", "original": None}, ensure_ascii=False),
            time.time(),
            new_uid("char"),
        ),
    )
    return {"id": cid, "sheet": sheet}

@app.post("/api/characters/import")
def char_import(body: dict = Body(...)):
    reinterpret = bool(body.get("reinterpret"))
    try:
        card = resolve_import_card(body.get("card"))
        cid, sheet = import_character(
            card,
            reinterpret,
        )
    except Exception as exc:
        raise HTTPException(502 if reinterpret else 400, f"Character import failed: {exc}") from exc
    _ensure_resource_uid("characters", cid, "char")
    return {"id": cid, "sheet": sheet}

@app.post("/api/characters/{cid}/start")
def character_start_story(cid: int, body: dict = Body(default={})):
    """Start story now: seed a chat from this character's greeting with the
    chosen persona (greeting shown verbatim, private knowledge routed to the
    character). See greetings.start_story / docs/GREETING_IMPORT_DESIGN.md."""
    persona_id = body.get("persona_id")
    if persona_id is None:
        raise HTTPException(400, "persona_id required")
    lorebook_id = body.get("lorebook_id")
    try:
        chat_id, turn_id = greetings.start_story(
            cid, int(persona_id), int(body.get("greeting_index", 0)),
            lorebook_id=int(lorebook_id) if lorebook_id else None,
            already_known=bool(body.get("already_known", True)))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"chat_id": chat_id, "turn_id": turn_id}

@app.post("/api/characters/{cid}/recover_greetings")
def char_recover_greetings(cid: int):
    """Backfill greetings from the character's stored source card, for imports
    that predate greeting capture or came through the AI-reinterpret path."""
    sheet = recover_greetings_from_source(cid)
    if sheet is None:
        raise HTTPException(404, "No greetings found in this character's imported card")
    return {"sheet": sheet,
            "greetings": (sheet.get("opening") or {}).get("greetings") or []}

@app.get("/api/characters/{cid}/export")
def char_export(cid: int):
    c = q("SELECT * FROM characters WHERE id=?", (cid,), one=True)
    if not c: raise HTTPException(404)
    source = json.loads(c["source"] or "{}")
    sheet = json.loads(c["sheet"] or "{}")
    return character_export_document(sheet, source)

@app.put("/api/characters/{cid}")
def char_edit(cid: int, body: dict = Body(...)):
    sheet = normalize_character_data(body.get("sheet") or {})
    qi(
        "UPDATE characters SET name=?,sheet=? WHERE id=?",
        (character_name(sheet), json.dumps(sheet, ensure_ascii=False), cid),
    )
    return {"ok": True, "sheet": sheet}

@app.delete("/api/characters/{cid}")
def char_del(cid: int):
    qi("DELETE FROM characters WHERE id=?", (cid,))
    qi("DELETE FROM chat_chars WHERE char_id=?", (cid,))
    return {"ok": True}

# ============================ PERSONAS ============================
@app.post("/api/personas/generate")
def persona_generate(body: dict = Body(default={})):
    brief = str(body.get("prompt") or body.get("brief") or body.get("description") or "").strip()
    try:
        pid, sheet = generate_persona(brief)
    except Exception as exc:
        raise HTTPException(502, f"Persona generation failed: {exc}") from exc
    _ensure_resource_uid("personas", pid, "persona")
    return {"id": pid, "sheet": sheet}

@app.post("/api/personas")
def persona_create(body: dict = Body(...)):
    raw = body.get("sheet")
    if raw:
        sheet = normalize_persona_data(raw)
    else:
        sheet = default_persona_data(body.get("name") or "Player")

    pid = qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) "
        "VALUES(?,?,?,?)",
        (
            persona_name(sheet),
            json.dumps(sheet, ensure_ascii=False),
            "{}",
            new_uid("persona"),
        ),
    )
    return {"id": pid, "sheet": sheet}

@app.post("/api/personas/import")
def persona_import(body: dict = Body(...)):
    reinterpret = bool(body.get("reinterpret"))
    try:
        card = resolve_import_card(body.get("card"))
        pid, sheet = import_persona(
            card,
            reinterpret,
        )
    except Exception as exc:
        raise HTTPException(502 if reinterpret else 400, f"Persona import failed: {exc}") from exc
    _ensure_resource_uid("personas", pid, "persona")
    return {"id": pid, "sheet": sheet}

@app.get("/api/personas/{pid}/export")
def persona_export(pid: int):
    p = q("SELECT * FROM personas WHERE id=?", (pid,), one=True)
    if not p: raise HTTPException(404)
    return persona_export_document(
        json.loads(p["sheet"] or "{}"),
        json.loads(p["source"] or "{}"),
    )

@app.put("/api/personas/{pid}")
def persona_edit(pid: int, body: dict = Body(...)):
    sheet = normalize_persona_data(body.get("sheet") or {})
    qi(
        "UPDATE personas SET name=?,sheet=? WHERE id=?",
        (persona_name(sheet), json.dumps(sheet, ensure_ascii=False), pid),
    )
    return {"ok": True, "sheet": sheet}

@app.delete("/api/personas/{pid}")
def persona_del(pid: int):
    qi("DELETE FROM personas WHERE id=?", (pid,))
    return {"ok": True}

# ============================ LOREBOOKS ============================
@app.get("/api/lorebooks/{lid}")
def lore_get(lid: int):
    book = q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True)
    if not book:
        raise HTTPException(404, "Lorebook not found")
    book_dict = dict(book)
    book_dict["entry_count"] = q(
        "SELECT COUNT(*) c FROM lore_entries WHERE lorebook_id=?",
        (lid,), one=True
    )["c"]
    entries = [
        _lore_entry_json(r)
        for r in q(
            "SELECT * FROM lore_entries WHERE lorebook_id=? ORDER BY id",
            (lid,),
        )
    ]
    return {"book": book_dict, "entries": entries}
    
@app.post("/api/lorebooks")

def lore_create(body: dict = Body(...)):
    name = str(body.get("name") or "Untitled lorebook").strip()
    book_type = body.get("book_type") or "general"
    if book_type not in LOREBOOK_TYPES:
        book_type = "general"
    summary = str(body.get("summary") or "")
    parent_id = body.get("parent_id")
    chat_id = body.get("chat_id")
    inheritance_mode = body.get("inheritance_mode") or "inherit"
    sort_order = int(body.get("sort_order") or 0)

    lid = qi(
        "INSERT INTO lorebooks("
        "name,chat_id,book_type,summary,parent_id,"
        "inheritance_mode,sort_order"
        ") VALUES(?,?,?,?,?,?,?)",
        (name, chat_id, book_type, summary, parent_id,
         inheritance_mode, sort_order),
    )
    return dict(q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True))
    
@app.put("/api/lorebooks/{lid}")
def lore_edit(lid: int, body: dict = Body(...)):
    current = _require_lorebook(lid)

    name = str(
        body["name"] if "name" in body else current["name"]
    ).strip()
    if not name:
        raise HTTPException(400, "Lorebook name cannot be empty")

    book_type = (
        body["book_type"]
        if "book_type" in body
        else current["book_type"]
    )
    if book_type not in LOREBOOK_TYPES:
        raise HTTPException(400, "Invalid lorebook type")

    inheritance_mode = (
        body["inheritance_mode"]
        if "inheritance_mode" in body
        else current["inheritance_mode"]
    )
    if inheritance_mode not in (
        "inherit",
        "isolated",
        "reference_only",
    ):
        raise HTTPException(400, "Invalid inheritance mode")

    summary = str(
        body["summary"]
        if "summary" in body
        else current["summary"] or ""
    )

    qi(
        """UPDATE lorebooks SET
            name=?,book_type=?,summary=?,scope_world_id=?,
            scope_location_id=?,inheritance_mode=?,sort_order=?
        WHERE id=?""",
        (
            name,
            book_type,
            summary,
            (
                body["scope_world_id"]
                if "scope_world_id" in body
                else current["scope_world_id"]
            ),
            (
                body["scope_location_id"]
                if "scope_location_id" in body
                else current["scope_location_id"]
            ),
            inheritance_mode,
            int(
                body["sort_order"]
                if "sort_order" in body
                else current["sort_order"] or 0
            ),
            lid,
        ),
    )

    return {
        "ok": True,
        "book": dict(_require_lorebook(lid)),
    }

@app.delete("/api/lorebooks/{lid}")
def lore_delete(lid: int):
    _require_lorebook(lid)
    _delete_book(lid)
    return {"ok": True}

@app.get("/api/lorebooks/{lid}/export")
def lore_export(lid: int):
    lb = q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True)
    if not lb: raise HTTPException(404)
    return {
        "name": lb["name"],
        "book_type": lb["book_type"] or "general",
        "summary": lb["summary"] or "",
        "resource_uid": lb["resource_uid"],
        "entries": dump_lorebook(lid),
    }

@app.post("/api/lorebooks/{lid}/reinterpret")
def lore_reinterpret_route(lid: int):
    _require_lorebook(lid)
    try:
        count = reinterpret_lorebook(lid)
    except Exception as exc:
        raise HTTPException(502, f"Lorebook reinterpretation failed: {exc}") from exc
    return {
        "ok": True,
        "reinterpreted": count,
    }

@app.post("/api/lorebooks/{lid}/generate")
def lore_generate(lid: int, body: dict = Body(default={})):
    _require_lorebook(lid)
    brief = str(body.get("prompt") or body.get("brief") or "").strip()
    try:
        entry_ids = generate_lore_entries(lid, brief)
    except Exception as exc:
        raise HTTPException(502, f"Lore generation failed: {exc}") from exc
    return {
        "ok": True,
        "added": len(entry_ids),
        "entry_ids": entry_ids,
    }

@app.post("/api/lorebooks/{lid}/entries")
def lore_entry_create(lid: int, body: dict = Body(...)):
    _require_lorebook(lid)

    content = str(body.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "Lore entry content is required")

    category = body.get("category") or "other"
    if category not in LORE_CATEGORIES:
        category = "other"

    eid = add_lore(
        lid,
        _lore_keys(body.get("keys")),
        content,
        locked=int(bool(body.get("canon_locked") or body.get("locked"))),
        category=category,
        title=body.get("title"),
        knowledge_tag=body.get("knowledge_tag"),
        knowledge_range=body.get("knowledge_range"),
        knowledge_locations=body.get("knowledge_locations"),
    )

    return {
        "id": eid,
        "entry": _lore_entry_json(_require_lore_entry(eid)),
    }

@app.put("/api/lore_entries/{eid}")
def lore_entry_edit(eid: int, body: dict = Body(...)):
    current = _require_lore_entry(eid)

    keys = _lore_keys(body["keys"] if "keys" in body else current["keys"])
    content = str(body["content"] if "content" in body else current["content"])
    if not content.strip():
        raise HTTPException(400, "Lore entry content is required")

    category = body["category"] if "category" in body else current["category"]
    if category not in LORE_CATEGORIES:
        category = "other"

    locations = body["knowledge_locations"] if "knowledge_locations" in body else current["knowledge_locations"]

    update_lore(
        eid,
        keys,
        content,
        category,
        title=(
            body["title"]
            if "title" in body
            else current["title"]
        ),
        knowledge_tag=(
            body["knowledge_tag"]
            if "knowledge_tag" in body
            else current["knowledge_tag"]
        ),
        knowledge_range=(
            body["knowledge_range"]
            if "knowledge_range" in body
            else current["knowledge_range"]
        ),
        knowledge_locations=_stored_locations(locations),
        importance=(
            body["importance"]
            if "importance" in body
            else current["importance"]
        ),
        aliases=(
            body["aliases"]
            if "aliases" in body
            else current["aliases"]
        ),
        scope=(
            body["scope"]
            if "scope" in body
            else current["scope"]
        ),
        relations=(
            body["relations"]
            if "relations" in body
            else current["relations"]
        ),
        source_notes=(
            body["source_notes"]
            if "source_notes" in body
            else current["source_notes"]
        ),
    )

    if "canon_locked" in body or "locked" in body:
        locked = body.get("canon_locked", body.get("locked", False))
        qi("UPDATE lore_entries SET canon_locked=? WHERE id=?", (int(bool(locked)), eid))

    return {
        "ok": True,
        "entry": _lore_entry_json(_require_lore_entry(eid)),
    }

@app.delete("/api/lore_entries/{eid}")
def lore_entry_delete(eid: int):
    _require_lore_entry(eid)
    delete_lore(eid)
    return {"ok": True}

# ============================ CHATS ============================
@app.post("/api/chats")
def chat_new(body: dict = Body(...)):
    cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
             (body.get("name") or f"Chat {int(time.time())}", body.get("scenario", ""), time.time()))
    return dict(q("SELECT * FROM chats WHERE id=?", (cid,), one=True))

@app.put("/api/chats/{cid}")
def chat_edit(cid: int, body: dict = Body(...)):
    row = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not row:
        raise HTTPException(404, "Chat not found")
    cur = dict(row)
    for k in ("name", "persona_id", "scenario"):
        if k in body: cur[k] = body[k]
    qi("UPDATE chats SET name=?,persona_id=?,scenario=? WHERE id=?",
       (cur["name"], cur["persona_id"], cur["scenario"], cid))
    return {"ok": True}

@app.post("/api/chats/{cid}/lorebooks")
def attach_lore(cid: int, body: dict = Body(...)):
    if not q("SELECT 1 FROM chats WHERE id=?", (cid,), one=True):
        raise HTTPException(404, "Chat not found")
    # refresh_checkpoint mutates the latest turn's checkpoint -- must not
    # race a running pipeline that's about to write that same turn.
    _require_chat_idle(cid)
    src = body.get("lorebook_id")
    if not src: raise HTTPException(400, "lorebook_id required")
    row = q("SELECT * FROM lorebooks WHERE id=?", (src,), one=True)
    if not row: raise HTTPException(404, "Lorebook not found")
    ex = q("SELECT cl.lorebook_id FROM chat_lorebooks cl JOIN lorebooks lb ON lb.id=cl.lorebook_id WHERE cl.chat_id=? AND (cl.lorebook_id=? OR lb.origin_id=?)", (cid, src, src), one=True)
    if ex: return {"lorebook_id": ex["lorebook_id"], "already": True}
    if row["chat_id"] == cid:
        new = src
        origin = row["origin_id"]
    else:
        new = duplicate_lorebook_for_chat(src, cid)
        origin = src
    qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) VALUES(?,?,?,1)", (cid, new, origin))
    last = _latest_turn(cid)
    if last:
        refresh_checkpoint(cid, last["idx"])
    return {"lorebook_id": new}

@app.delete("/api/chats/{cid}/lorebooks/{lid}")
def detach_book(cid: int, lid: int):
    _require_chat_idle(cid)
    qi("DELETE FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?", (cid, lid))
    lb = q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True)
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if lb and lb["chat_id"] == cid:
        if chat and chat["lorebook_id"] == lid:
            qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (cid,))
        _delete_book(lid)
    last = _latest_turn(cid)
    if last:
        refresh_checkpoint(cid, last["idx"])
    return {"ok": True}

@app.post("/api/chats/{cid}/lorebook")
def bind_lore(cid: int, body: dict = Body(...)):
    _require_chat_idle(cid)
    src = body["lorebook_id"]
    if not src:
        qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (cid,))
        return {"lorebook_id": None}
    row = q("SELECT * FROM lorebooks WHERE id=?", (src,), one=True)
    if not row: raise HTTPException(404, "Lorebook not found")
    new = src if row["chat_id"] == cid else duplicate_lorebook_for_chat(src, cid)
    qi("UPDATE chats SET lorebook_id=? WHERE id=?", (new, cid))
    last = _latest_turn(cid)
    if last:
        refresh_checkpoint(cid, last["idx"])
    return {"lorebook_id": new}

@app.delete("/api/chats/{cid}/lorebook")
def detach_lore(cid: int):
    _require_chat_idle(cid)
    qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (cid,))
    last = _latest_turn(cid)
    if last:
        refresh_checkpoint(cid, last["idx"])
    return {"ok": True}

@app.delete("/api/chats/{cid}")
def chat_del(cid: int):
    # A still-running pipeline would keep writing into rows we're deleting
    # (and re-create orphan world rows for the dead chat id).
    _require_chat_idle(cid)
    for t in q("SELECT id FROM turns WHERE chat_id=?", (cid,)):
        for s in q("SELECT id FROM steps WHERE turn_id=?", (t["id"],)):
            qi("DELETE FROM variants WHERE step_id=?", (s["id"],))
        qi("DELETE FROM steps WHERE turn_id=?", (t["id"],))
    for tbl in ("turns", "events", "world", "checkpoints", "chat_chars", "chat_lorebooks"):
        qi(f"DELETE FROM {tbl} WHERE chat_id=?", (cid,))
    qi("DELETE FROM memory_retrieval_fts WHERE chat_id=?", (str(cid),))
    qi("DELETE FROM memories WHERE chat_id=?", (cid,))
    qi("DELETE FROM memory_summaries WHERE chat_id=?", (cid,))
    qi("DELETE FROM lorebooks WHERE chat_id=?", (cid,))
    qi("DELETE FROM chats WHERE id=?", (cid,))
    return {"ok": True}

@app.get("/api/chats/{cid}")
def chat_get(cid: int):
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404)

    parts = [
        dict(r)
        for r in q(
            "SELECT ch.id,ch.name,ch.sheet,cc.status "
            "FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id "
            "WHERE cc.chat_id=?",
            (cid,),
        )
    ]

    turns = []
    for t in q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx", (cid,)):
        nar = active_content(t["id"], "narrator") or {}
        stale = q(
            "SELECT COUNT(*) c FROM steps WHERE turn_id=? AND stale=1",
            (t["id"],),
            one=True,
        )["c"]

        turns.append(
            {
                "id": t["id"],
                "idx": t["idx"],
                "player_input": t["player_input"],
                "prose": nar.get("prose", ""),
                "stale": stale > 0,
                "frame_id": t["frame_id"],
            }
        )

    canon = chat["lorebook_id"]
    books = []

    for lid in chat_lorebook_ids(cid, enabled_only=False):
        lb = q(
            "SELECT * FROM lorebooks WHERE id=?",
            (lid,),
            one=True,
        )
        if not lb:
            continue

        attachment = q(
            "SELECT enabled FROM chat_lorebooks "
            "WHERE chat_id=? AND lorebook_id=?",
            (cid, lid),
            one=True,
        )

        books.append(
            {
                "id": lid,
                "name": lb["name"],
                "chat_id": lb["chat_id"],
                "origin_id": lb["origin_id"],
                "book_type": lb["book_type"] or "general",
                "summary": lb["summary"] or "",
                "parent_id": lb["parent_id"],
                "scope_world_id": lb["scope_world_id"],
                "scope_location_id": lb["scope_location_id"],
                "inheritance_mode": lb["inheritance_mode"] or "inherit",
                "sort_order": lb["sort_order"] or 0,
                "canon": lid == canon,
                "enabled": (
                    bool(attachment["enabled"])
                    if attachment
                    else True
                ),
            }
        )

    lbc = None
    if canon:
        r = q(
            "SELECT id,name FROM lorebooks WHERE id=?",
            (canon,),
            one=True,
        )
        lbc = dict(r) if r else None

    return {
        "chat": dict(chat),
        "participants": parts,
        "turns": turns,
        "lorebook": lbc,
        "lorebooks": books,
        "frames": list_frames(cid),
    }

@app.post("/api/chats/{cid}/characters")
def chat_add_char(cid: int, body: dict = Body(...)):
    ch = body.get("char_id")
    if ch is None:
        raise HTTPException(400, "char_id required")
    if not q("SELECT 1 FROM characters WHERE id=?", (ch,), one=True):
        raise HTTPException(404, "Character not found")
    ex = q("SELECT * FROM chat_chars WHERE chat_id=? AND char_id=?", (cid, ch), one=True)
    if ex:
        qi("UPDATE chat_chars SET status='active' WHERE chat_id=? AND char_id=?", (cid, ch))
    else:
        qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?, 'active')", (cid, ch))
    scene_exists = wget(cid, "scene", None) is not None
    if scene_exists:
        name = q("SELECT name FROM characters WHERE id=?", (ch,), one=True)["name"]
        pend = wget(cid, "pending", [])
        pend.append({"type": "arrival", "who": name, "returning": bool(ex)})
        wset(cid, "pending", pend)
    if body.get("already_known"):
        # The recognition map ("known") otherwise only grows from
        # validated_introductions as an in-story introduction beat fires
        # (commit.py commit_mapping), so an opening-scene companion the
        # player is meant to already know renders as "the unfamiliar
        # person" until that happens to occur. Let attaching a character
        # seed mutual recognition directly, same effect as an
        # introduction having already happened off-screen.
        char_name = q("SELECT name FROM characters WHERE id=?", (ch,), one=True)["name"]
        chat_row = dict(q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
        player_name = persona_name(persona_of(chat_row))
        known = wget(cid, "known", {})
        known.setdefault(char_name, [])
        if player_name not in known[char_name]:
            known[char_name].append(player_name)
        known.setdefault(player_name, [])
        if char_name not in known[player_name]:
            known[player_name].append(char_name)
        wset(cid, "known", known)
    return {"ok": True}

# ---- Background-presence promotion ----

@app.get("/api/chats/{cid}/promotable")
def list_promotable_presences(cid: int):
    return {"presences": promotable_background_presences(cid)}

@app.get("/api/chats/{cid}/dramatic_irony")
def get_dramatic_irony_feed(cid: int):
    return {"feed": dramatic_irony_feed(cid)}

@app.get("/api/chats/{cid}/promises")
def get_promise_ledger(cid: int):
    return {"promises": promise_ledger(cid)}

@app.post("/api/chats/{cid}/promotions/draft")
def draft_promotion(cid: int, body: dict = Body(...)):
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Missing name")
    try:
        draft = draft_promoted_character(cid, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Promotion draft failed: {exc}") from exc
    return draft

@app.post("/api/chats/{cid}/promotions/confirm")
def confirm_promotion(cid: int, body: dict = Body(...)):
    """Attach a reviewed (possibly hand-edited) promotion draft as a real
    character. Forward-only: past turns' steps/variants are untouched --
    she becomes character_step-eligible starting next turn, the same as
    manually attaching any other character mid-chat.
    """
    name = str(body.get("name") or "").strip()
    sheet = body.get("sheet")
    if not name or not isinstance(sheet, dict):
        raise HTTPException(400, "Missing name or sheet")

    memory_seeds = [str(m) for m in (body.get("memory_seeds") or []) if str(m).strip()]
    char_id = promote_background_character(
        cid, name, sheet=sheet, memory_seeds=memory_seeds)
    return {"ok": True, "char_id": char_id}

@app.get("/api/auto_promote")
def get_auto_promote():
    return {"enabled": get_setting("auto_promote") != "0"}

@app.put("/api/auto_promote")
def set_auto_promote(body: dict = Body(...)):
    set_setting("auto_promote", "1" if body.get("enabled", True) else "0")
    return {"enabled": bool(body.get("enabled", True))}

@app.get("/api/chats/{cid}/personas")
def chat_list_extra_personas(cid: int):
    rows = q(
        "SELECT p.id, p.name, cp.frame_id FROM chat_personas cp "
        "JOIN personas p ON p.id=cp.persona_id "
        "WHERE cp.chat_id=? AND cp.status='active'",
        (cid,),
    )
    return {"personas": [dict(r) for r in rows]}

@app.put("/api/chats/{cid}/personas/{pid}/station")
def chat_persona_station(cid: int, pid: int, body: dict = Body(...)):
    """Which frame this persona is currently playing in -- this is what
    makes 'players eras apart' real: turn creation only folds an extra
    player into a turn (_load_extra_players) when their station matches
    that turn's frame. Re-stationing is whole-chat-exclusive (not just
    frame-local) since it changes who a NOT-YET-CREATED turn in either
    the old or new frame would fold in."""
    row = q("SELECT frame_id FROM chat_personas WHERE chat_id=? AND persona_id=?", (cid, pid), one=True)
    if not row:
        raise HTTPException(404, "Persona not attached to this chat")
    frame_id = body.get("frame_id")
    frame_id = int(frame_id) if frame_id is not None else None
    if frame_id is not None:
        fr = get_frame(frame_id)
        if fr is None or fr["chat_id"] != cid:
            raise HTTPException(404, f"Frame {frame_id} not found")
    _require_chat_idle(cid)

    # A paradox only strands whoever's actually stationed in its own
    # frame -- moving INTO or OUT OF that frame is blocked, an unrelated
    # re-station isn't this paradox's business (see paradox.paradox_visible_to).
    # Each frame has its own independent slot, so both the old and new
    # frame need their own check -- a paradox active in some THIRD frame
    # must never block this move.
    if paradox.get_paradox(cid, row["frame_id"]) or paradox.get_paradox(cid, frame_id):
        raise HTTPException(
            409,
            "A paradox is unfolding in that frame -- you can't station "
            "into or out of it until it's resolved.",
        )

    qi("UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id=?", (frame_id, cid, pid))
    return {"ok": True, "frame_id": frame_id}

@app.post("/api/chats/{cid}/personas")
def chat_add_persona(cid: int, body: dict = Body(...)):
    """Attach an ADDITIONAL human player to this chat, alongside the
    existing single-persona chats.persona_id (untouched -- this is purely
    additive multiplayer support). Mirrors chat_add_char's pattern.
    """
    pid = body["persona_id"]
    ex = q("SELECT * FROM chat_personas WHERE chat_id=? AND persona_id=?", (cid, pid), one=True)
    if ex:
        qi("UPDATE chat_personas SET status='active' WHERE chat_id=? AND persona_id=?", (cid, pid))
    else:
        qi("INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')", (cid, pid))
    return {"ok": True}

@app.delete("/api/chats/{cid}/personas/{pid}")
def chat_del_persona(cid: int, pid: int):
    qi("UPDATE chat_personas SET status='dormant' WHERE chat_id=? AND persona_id=?", (cid, pid))
    return {"ok": True}

@app.post("/api/chats/{cid}/turns/{idx}/player_input")
def submit_extra_player_input(cid: int, idx: int, body: dict = Body(...)):
    """Pre-submit an additional player's declared action for a specific
    upcoming (or current, if not yet resolved) turn index. Keyed by
    chat+idx rather than turn_id since the turn row for that index may not
    exist yet -- this is what makes same-beat resolution possible:
    whichever request actually creates/runs that turn picks up everything
    already declared for it. Rejects submissions against an already-run
    turn (has active steps) since the beat has already resolved.
    """
    pid = body["persona_id"]
    text = _player_input(body)
    attached = q(
        "SELECT 1 FROM chat_personas WHERE chat_id=? AND persona_id=? AND status='active'",
        (cid, pid), one=True,
    )
    if not attached:
        raise HTTPException(400, "Persona is not attached to this chat")
    existing_turn = q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (cid, idx), one=True)
    if existing_turn:
        already_run = q(
            "SELECT 1 FROM steps WHERE turn_id=? LIMIT 1", (existing_turn["id"],), one=True,
        )
        if already_run:
            raise HTTPException(409, "That turn has already been resolved")
    _submit_player_input(cid, idx, pid, text)
    return {"ok": True}

def _submit_player_input(cid: int, idx: int, pid: int, text: str):
    qi(
        "INSERT INTO turn_player_inputs(chat_id,turn_idx,persona_id,input,created) "
        "VALUES(?,?,?,?,?) "
        "ON CONFLICT(chat_id,turn_idx,persona_id) DO UPDATE SET input=excluded.input,created=excluded.created",
        (cid, idx, pid, text, time.time()),
    )

# ---- Guest invites ("invite a friend") ----

@app.post("/api/chats/{cid}/guest_invites")
def create_guest_invite(cid: int, body: dict = Body(...)):
    pid = body["persona_id"]
    attached = q(
        "SELECT 1 FROM chat_personas WHERE chat_id=? AND persona_id=? AND status='active'",
        (cid, pid), one=True,
    )
    if not attached:
        raise HTTPException(
            400, "Attach this persona to the chat as an extra player first",
        )
    invite = guest.create_guest_invite(cid, pid)
    return {
        "grant_id": invite["grant_id"],
        "code": invite["code"],
        "expires": invite["expires"],
    }

@app.get("/api/chats/{cid}/guest_invites")
def list_guest_invites(cid: int):
    return {"grants": guest.list_grants(cid)}

@app.delete("/api/chats/{cid}/guest_invites/{gid}")
def revoke_guest_invite(cid: int, gid: int):
    if not guest.revoke_grant(cid, gid):
        raise HTTPException(404, "Grant not found")
    return {"ok": True}

@app.post("/api/join")
def join_with_code(body: dict = Body(...)):
    result = guest.redeem_code(str(body.get("code") or ""))
    if not result:
        raise HTTPException(400, "That code is invalid, expired, or already used")
    chat = q("SELECT name FROM chats WHERE id=?", (result["chat_id"],), one=True)
    persona = q("SELECT name FROM personas WHERE id=?", (result["persona_id"],), one=True)
    response = JSONResponse({
        "ok": True,
        "chat_name": chat["name"] if chat else "",
        "persona_name": persona["name"] if persona else "Guest",
    })
    response.set_cookie(
        GUEST_COOKIE, result["token"], httponly=True, samesite="lax",
        max_age=guest.GUEST_TOKEN_TTL,
    )
    return response

@app.get("/api/guest/state")
def guest_state(request: Request):
    grant = getattr(request.state, "guest_grant", None)
    if not grant:  # e.g. a signed-in HOST hitting /guest -- no guest grant set
        raise HTTPException(403, "Guest session required")
    cid, pid = grant["chat_id"], grant["persona_id"]
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404)

    turns = []
    for t in q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx", (cid,)):
        extra = active_content(t["id"], "narrator_extra") or {}
        entry = extra.get(str(pid)) or {}
        my_input = q(
            "SELECT input FROM turn_player_inputs WHERE chat_id=? AND turn_idx=? "
            "AND persona_id=?",
            (cid, t["idx"], pid), one=True,
        )
        turns.append({
            "idx": t["idx"],
            "player_input": my_input["input"] if my_input else None,
            "prose": entry.get("prose", ""),
        })

    persona = q("SELECT name FROM personas WHERE id=?", (pid,), one=True)
    next_idx = (turns[-1]["idx"] + 1) if turns else 0
    return {
        "chat_name": chat["name"],
        "persona_name": persona["name"] if persona else "Guest",
        "turns": turns,
        "next_idx": next_idx,
    }

@app.post("/api/guest/input")
def guest_input(request: Request, body: dict = Body(...)):
    grant = getattr(request.state, "guest_grant", None)
    if not grant:
        raise HTTPException(403, "Guest session required")
    cid, pid = grant["chat_id"], grant["persona_id"]
    idx = body.get("idx")
    if idx is None:
        raise HTTPException(400, "Missing idx")
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        raise HTTPException(400, "idx must be an integer")
    if idx < 0:
        raise HTTPException(400, "idx must be non-negative")
    existing_turn = q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (cid, idx), one=True)
    if existing_turn:
        already_run = q(
            "SELECT 1 FROM steps WHERE turn_id=? LIMIT 1", (existing_turn["id"],), one=True,
        )
        if already_run:
            raise HTTPException(409, "That turn has already been resolved")
    _submit_player_input(cid, idx, pid, _player_input(body))
    return {"ok": True}

@app.delete("/api/chats/{cid}/characters/{ch}")
def chat_del_char(cid: int, ch: int):
    qi("UPDATE chat_chars SET status='dormant' WHERE chat_id=? AND char_id=?", (cid, ch))
    name = q("SELECT name FROM characters WHERE id=?", (ch,), one=True)["name"]
    pend = wget(cid, "pending", [])
    pend.append({"type": "departure", "who": name})
    wset(cid, "pending", pend)
    return {"ok": True}

@app.get("/api/chats/{cid}/characters/{ch}/private_history")
def ph_get(cid: int, ch: int):
    cc = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?", (cid, ch), one=True)
    st = json.loads(cc["state"] or "{}") if cc else {}
    if st.get("private_history") is not None:
        return {"entries": st["private_history"], "source": "chat"}
    row = q("SELECT sheet FROM characters WHERE id=?", (ch,), one=True)
    sheet = normalize_character_data(json.loads(row["sheet"] or "{}")) if row else {}
    return {"entries": sheet.get("knowledge", {}).get("private_history", []), "source": "sheet"}

@app.put("/api/chats/{cid}/characters/{ch}/private_history")
def ph_put(cid: int, ch: int, body: dict = Body(...)):
    cc = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?", (cid, ch), one=True)
    if not cc: raise HTTPException(404)
    st = json.loads(cc["state"] or "{}")
    st["private_history"] = body.get("entries", [])
    qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?", (json.dumps(st), cid, ch))
    return {"ok": True}

@app.get("/api/chats/{cid}/persona_private_history")
def pph_get(cid: int):
    ents = wget(cid, "persona_private_history", None)
    if ents is not None:
        return {"entries": ents, "source": "chat"}
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if chat and chat["persona_id"]:
        p = q("SELECT sheet FROM personas WHERE id=?", (chat["persona_id"],), one=True)
        if p:
            sheet = normalize_persona_data(json.loads(p["sheet"] or "{}"))
            return {"entries": sheet.get("knowledge", {}).get("private_history", []), "source": "sheet"}
    return {"entries": [], "source": "sheet"}

@app.put("/api/chats/{cid}/persona_private_history")
def pph_put(cid: int, body: dict = Body(...)):
    wset(cid, "persona_private_history", body.get("entries", []))
    return {"ok": True}

@app.get("/api/chats/{cid}/world")
def world_get(cid: int):
    return {w["key"]: json.loads(w["value"]) for w in q("SELECT * FROM world WHERE chat_id=?", (cid,))}

@app.put("/api/chats/{cid}/world")
def world_put(cid: int, body: dict = Body(...)):
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")
    # A running pipeline reads/writes world keys throughout the turn; wiping
    # and rewriting them mid-turn would corrupt it. And DELETE+loop must be
    # atomic so a crash can't leave the un-rewritten keys permanently lost.
    _require_chat_idle(cid)
    # Scene blobs (present + every frame-scoped copy) BEFORE the rewrite:
    # the manual world editor is a scene writer like commit_scene, so the
    # room_registry projection must be reconciled against what each blob
    # held before vs. after -- it was the one write path that bypassed the
    # registry (Phase 3a single-source-of-truth consolidation).
    old_scenes = {
        w["key"]: json.loads(w["value"])
        for w in q("SELECT * FROM world WHERE chat_id=?", (cid,))
        if parse_scoped_world_key(w["key"])[0] == "scene"
    }
    with transaction():
        qi("DELETE FROM world WHERE chat_id=?", (cid,))
        for k, v in body.items():
            wset(cid, k, v)
        scene_keys = {
            k for k in list(old_scenes) + list(body)
            if parse_scoped_world_key(k)[0] == "scene"
        }
        for key in sorted(scene_keys):
            new_scene = body.get(key)
            sync_room_registry_with_scene(
                cid, chat["lorebook_id"],
                old_scenes.get(key) if isinstance(old_scenes.get(key), dict)
                else {},
                new_scene if isinstance(new_scene, dict) else {})
    return {"ok": True}

@app.get("/api/chats/{cid}/attire")
def attire_get(cid: int):
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat: raise HTTPException(404, "Chat not found")
    scene = get_scene(cid, chat)
    return scene.get("attire") or {}

@app.put("/api/chats/{cid}/attire")
def attire_put(cid: int, body: dict = Body(...)):
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat: raise HTTPException(404, "Chat not found")
    scene = get_scene(cid, chat)
    scene["attire"] = body
    wset(cid, "scene", scene)
    return {"ok": True}

@app.get("/api/chats/{cid}/dialogue_config")
def dlg_get(cid: int):
    return dialogue_config(cid)

@app.put("/api/chats/{cid}/dialogue_config")
def dlg_put(cid: int, body: dict = Body(...)):
    try:
        autonomy = max(0, min(100, int(body.get("autonomy", 50))))
    except (TypeError, ValueError):
        raise HTTPException(400, "autonomy must be an integer")
    derived = interaction_limits(autonomy)

    try:
        config = {
            "style": body.get("style", "natural"),
            "min_lines": max(0, int(body.get("min_lines", 0))),
            "max_lines": max(0, int(body.get("max_lines", 4))),
            "variance": max(0.0, min(1.0, float(body.get("variance", 0.6)))),
            "autonomy": autonomy,
            "allow_npc_initiative": bool(body.get("allow_npc_initiative", True)),
            "allow_npc_to_npc_dialogue": bool(body.get("allow_npc_to_npc_dialogue", True)),
            "stop_on_player_address": bool(body.get("stop_on_player_address", True)),
            "stop_on_question_to_player": bool(body.get("stop_on_question_to_player", True)),
            "silence_ends_exchange": bool(body.get("silence_ends_exchange", True)),
        }

        for key, default in derived.items():
            config[key] = max(0, int(body.get(key, default)))
    except (TypeError, ValueError):
        raise HTTPException(400, "dialogue config numeric fields must be numbers")

    config["max_lines"] = max(config["min_lines"], config["max_lines"])

    wset(cid, "dialogue_config", config)
    return config

@app.get("/api/chats/{cid}/frames")
def frames_list(cid: int):
    return {"frames": list_frames(cid)}

@app.post("/api/chats/{cid}/frames")
def frames_create(cid: int, body: dict = Body(...)):
    label = str(body.get("label") or "").strip()
    if not label:
        raise HTTPException(400, "Missing label")
    try:
        ordinal = int(body.get("ordinal", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "ordinal must be an integer")
    kind = body.get("kind") or "other"
    if kind == "spatial":
        # Spatial frames are engine-created only (spatial_frames.py's
        # deterministic proximity detector) -- there is no such thing as
        # a user-DECLARED spatial split; it only ever means "these two
        # parties just walked apart," which the engine itself observes.
        raise HTTPException(400, "kind 'spatial' cannot be created directly")
    try:
        fid = create_frame(
            cid, label=label, ordinal=ordinal, kind=kind,
            travelers=body.get("travelers"),
            nonexistent_cast=body.get("nonexistent_cast"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return get_frame(fid)


@app.get("/api/chats/{cid}/paradox_policy")
def paradox_policy_get(cid: int):
    return paradox.get_policy(cid)

@app.put("/api/chats/{cid}/paradox_policy")
def paradox_policy_put(cid: int, body: dict = Body(...)):
    try:
        return paradox.set_policy(
            cid, mode=body.get("mode"),
            escalation_rate=body.get("escalation_rate"),
            toll_in_radius=body.get("toll_in_radius"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.get("/api/chats/{cid}/fixed_points")
def fixed_points_list(cid: int):
    # A list, not a single "paradox" -- each frame now has its own
    # independent slot (paradox.get_all_paradoxes), so more than one can
    # genuinely be active at once under concurrent multi-frame play.
    return {
        "fixed_points": paradox.fixed_points(cid),
        "paradoxes": list(paradox.get_all_paradoxes(cid).values()),
    }

@app.post("/api/chats/{cid}/fixed_points")
def fixed_points_create(cid: int, body: dict = Body(...)):
    entity_id = str(body.get("entity_id") or "").strip()
    label = str(body.get("label") or "").strip()
    if not entity_id or not label:
        raise HTTPException(400, "Missing entity_id or label")
    frame_id = body.get("frame_id")
    frame_id = int(frame_id) if frame_id is not None else None
    if frame_id is not None:
        fr = get_frame(frame_id)
        if fr is None or fr["chat_id"] != cid:
            raise HTTPException(404, f"Frame {frame_id} not found")
    try:
        anchor_id = paradox.add_fixed_point(
            cid, entity_id=entity_id, frame_id=frame_id,
            required_exists=bool(body.get("required_exists", True)),
            label=label, mode=body.get("mode"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"anchor_id": anchor_id}

@app.delete("/api/chats/{cid}/fixed_points/{anchor_id}")
def fixed_points_delete(cid: int, anchor_id: int):
    paradox.remove_fixed_point(cid, anchor_id)
    return {"ok": True}

@app.get("/api/chats/{cid}/export")
def chat_export(cid: int):
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat: raise HTTPException(404)
    export = {"version": 3, "chat": dict(chat), "frames": [], "turns": [], "world": {}, "participants": [], "char_frames": [], "memories": [], "memory_summaries": [], "events": [], "checkpoints": [], "lorebook": None, "lorebooks": []}
    export["frames"] = [dict(f) for f in q("SELECT * FROM frames WHERE chat_id=?", (cid,))]
    export["char_frames"] = [dict(r) for r in q("SELECT * FROM chat_char_frames WHERE chat_id=?", (cid,))]
    for t in q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx", (cid,)):
        td = dict(t)
        td["steps"] = []
        for s in q("SELECT * FROM steps WHERE turn_id=? ORDER BY ord", (t["id"],)):
            sd = dict(s)
            sd["variants"] = [dict(v) for v in q("SELECT id,step_id,content,created,active FROM variants WHERE step_id=? ORDER BY id", (s["id"],))]
            td["steps"].append(sd)
        export["turns"].append(td)
    export["world"] = {w["key"]: json.loads(w["value"]) for w in q("SELECT * FROM world WHERE chat_id=?", (cid,))}
    export["participants"] = [dict(r) for r in q("SELECT * FROM chat_chars WHERE chat_id=?", (cid,))]
    export["memories"] = dump_chat_memories(cid)
    export["memory_summaries"] = dump_memory_summaries(cid)
    export["events"] = [dict(r) for r in q("SELECT * FROM events WHERE chat_id=? ORDER BY id", (cid,))]
    export["checkpoints"] = [
        {"turn_idx": r["turn_idx"], "blob": r["blob"], "created": r["created"]}
        for r in q("SELECT * FROM checkpoints WHERE chat_id=? ORDER BY turn_idx", (cid,))]
    # Live normalized world tables -- without these, an import has an empty
    # world_entities table while world.scene + fixed_points reference
    # entities, so the first post-import commit false-fires a paradox.
    for tbl in ("world_entities", "world_placements", "world_conditions",
                "scheduled_events", "room_registry",
                "fiction_worlds", "fiction_locations"):
        export[tbl] = [dict(r) for r in q(f"SELECT * FROM {tbl} WHERE chat_id=?", (cid,))]
    # Multiplayer roster + frame stations, and any pre-submitted co-player
    # inputs, and the lore link graph -- all silently dropped before.
    export["chat_personas"] = [dict(r) for r in q("SELECT * FROM chat_personas WHERE chat_id=?", (cid,))]
    export["turn_player_inputs"] = [dict(r) for r in q("SELECT * FROM turn_player_inputs WHERE chat_id=?", (cid,))]
    export["lorebook_links"] = dump_lorebook_links(chat_lorebook_ids(cid, enabled_only=False))
    canon = chat["lorebook_id"]
    for lid in chat_lorebook_ids(cid, enabled_only=False):
        lb = q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True)
        if not lb: continue
        att = q("SELECT enabled FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?", (cid, lid), one=True)
        export["lorebooks"].append({"book": dict(lb), "canon": lid == canon, "enabled": att["enabled"] if att else 1, "entries": dump_lorebook(lid)})
    if canon:
        lb = q("SELECT * FROM lorebooks WHERE id=?", (canon,), one=True)
        if lb:
            export["lorebook"] = {"book": dict(lb), "entries": dump_lorebook(canon)}
    # Portable resource bundle. chat_import remaps every char_id/persona_id
    # through resources.{persona,characters} (old_id -> embedded sheet). Without
    # it, a cross-install import raises "references character N but does not
    # embed it" (and even a same-install import that DID resolve by raw id would
    # drop every memory/summary for the unembedded characters, or silently
    # attach the wrong character if ids happen to collide). Embedding the sheets
    # here is what makes an exported story actually portable.
    char_ids = []
    for row in export["participants"] + export["char_frames"]:
        cid_ = row.get("char_id")
        if cid_ is not None and cid_ not in char_ids:
            char_ids.append(cid_)
    characters = []
    for ch_id in char_ids:
        c = q("SELECT * FROM characters WHERE id=?", (ch_id,), one=True)
        if not c:
            continue
        characters.append({
            "old_id": ch_id,
            "resource_uid": c["resource_uid"],
            "sheet": json.loads(c["sheet"]),
            "source": json.loads(c["source"] or "{}"),
        })
    persona = None
    if chat["persona_id"]:
        p = q("SELECT * FROM personas WHERE id=?", (chat["persona_id"],), one=True)
        if p:
            persona = {
                "resource_uid": p["resource_uid"],
                "sheet": json.loads(p["sheet"]),
                "source": json.loads(p["source"] or "{}"),
            }
    # Extra multiplayer personas (chat_personas beyond chats.persona_id)
    # need their sheets embedded too, or a cross-install import can't
    # resolve the roster's persona ids.
    extra_personas = []
    seen_pids = {chat["persona_id"]} if chat["persona_id"] else set()
    for row in export["chat_personas"]:
        pid = row.get("persona_id")
        if pid is None or pid in seen_pids:
            continue
        seen_pids.add(pid)
        p = q("SELECT * FROM personas WHERE id=?", (pid,), one=True)
        if not p:
            continue
        extra_personas.append({
            "old_id": pid,
            "resource_uid": p["resource_uid"],
            "sheet": json.loads(p["sheet"]),
            "source": json.loads(p["source"] or "{}"),
        })
    export["resources"] = {"persona": persona, "characters": characters,
                           "extra_personas": extra_personas}
    return export
    
def _variant_content(value):
    if isinstance(value, str):
        return value
    return json.dumps(value or {}, ensure_ascii=False)

def _import_or_match_character(resource):
    uid = resource.get("resource_uid")
    if uid:
        existing = q("SELECT id FROM characters WHERE resource_uid=?", (uid,), one=True)
        if existing:
            return existing["id"]

    sheet = normalize_character_data(resource.get("sheet") or {})
    uid = uid or sheet.get("identity", {}).get("uid") or new_uid("char")

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

def _import_or_match_persona(resource):
    if not resource:
        return None

    uid = resource.get("resource_uid")
    if uid:
        existing = q("SELECT id FROM personas WHERE resource_uid=?", (uid,), one=True)
        if existing:
            return existing["id"]

    sheet = normalize_persona_data(resource.get("sheet") or {})
    uid = uid or sheet.get("identity", {}).get("uid") or new_uid("persona")

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

def _import_book_uid(uid):
    """resource_uid for a lorebook created by chat_import.

    Unlike characters/personas -- shared resources that _import_or_match_*
    dedupes onto the existing row when the uid is already known -- an
    imported chat's lorebooks are per-chat copies (chat_id-scoped). Reusing
    the archive's uid verbatim therefore hits uq_lorebooks_resource_uid
    when the archive is imported into the SAME install that exported it,
    aborting the whole import. Keep the uid when it is free (cross-install
    portability); mint a fresh one when this install already owns it --
    the import is a distinct book in a distinct chat.
    """
    if uid and not q("SELECT id FROM lorebooks WHERE resource_uid=?",
                     (uid,), one=True):
        return uid
    return new_uid("book")

@app.post("/api/chats/import")
def chat_import(body: dict = Body(...)):
    archive = body.get("data")
    if not isinstance(archive, dict):
        raise HTTPException(400, "No chat data provided")

    if archive.get("schema") == "fiction-engine.chat":
        data = archive.get("data") or archive
    else:
        data = archive

    # Tolerate a bare {"data": {...}} envelope even without the schema marker:
    # some exports (e.g. the bundled demo) wrap the archive one level deep, and
    # the frontend also re-wraps the request body as {"data": fileContent}.
    if "chat" not in data and isinstance(data.get("data"), dict) \
            and "chat" in data["data"]:
        data = data["data"]

    if "chat" not in data:
        raise HTTPException(400, "Chat archive has no chat object")

    resources = data.get("resources") or {}

    with transaction():
        persona_id = _import_or_match_persona(resources.get("persona"))

        old_char_map = {}
        for resource in resources.get("characters") or []:
            old_id = resource.get("old_id")
            new_id = _import_or_match_character(resource)
            if old_id is not None:
                old_char_map[old_id] = new_id

        source_chat = data["chat"]

        # Persona id remap for the multiplayer roster: the primary persona's
        # source id (from the source chat row) maps to the resolved primary,
        # and every embedded extra persona maps old_id -> found-or-created.
        persona_idmap = {}
        if source_chat.get("persona_id") and persona_id is not None:
            persona_idmap[source_chat["persona_id"]] = persona_id
        for resource in resources.get("extra_personas") or []:
            old_pid = resource.get("old_id")
            new_pid = _import_or_match_persona(resource)
            if old_pid is not None and new_pid is not None:
                persona_idmap[old_pid] = new_pid

        if persona_id is None:
            old_persona_id = source_chat.get("persona_id")
            if old_persona_id:
                existing = q("SELECT id FROM personas WHERE id=?", (old_persona_id,), one=True)
                persona_id = existing["id"] if existing else None

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
        for f in data.get("frames") or []:
            old_fid = f.get("id")
            nfid = qtx(
                "INSERT INTO frames(chat_id,label,ordinal,kind,travelers,nonexistent_cast,created,"
                "split_turn_idx,merged_turn_idx) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    new_chat_id, f.get("label") or "", int(f.get("ordinal") or 0),
                    f.get("kind") or "other", f.get("travelers") or "[]",
                    f.get("nonexistent_cast") or "[]", f.get("created", time.time()),
                    f.get("split_turn_idx"), f.get("merged_turn_idx"),
                ),
            )
            if old_fid is not None:
                frame_idmap[old_fid] = nfid
        # parent_frame_id is self-referential -- deferred to a second
        # pass so it can be remapped through the now-complete frame_idmap
        # regardless of what order the source rows happened to come in.
        for f in data.get("frames") or []:
            old_fid = f.get("id")
            old_parent = f.get("parent_frame_id")
            if old_fid is not None and old_parent is not None and old_parent in frame_idmap:
                qtx(
                    "UPDATE frames SET parent_frame_id=? WHERE id=?",
                    (frame_idmap[old_parent], frame_idmap[old_fid]),
                )

        turn_id_map = {}
        for turn in data.get("turns") or []:
            new_turn_id = qtx(
                "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                "VALUES(?,?,?,?,?)",
                (
                    new_chat_id,
                    turn["idx"],
                    turn.get("player_input", ""),
                    turn.get("created", time.time()),
                    frame_idmap.get(turn.get("frame_id")),
                ),
            )
            turn_id_map[turn.get("id")] = new_turn_id

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

                variants = step.get("variants") or []
                active_seen = False
                for variant in variants:
                    active = bool(variant.get("active", 0))
                    if active and active_seen:
                        active = False
                    active_seen = active_seen or active

                    qtx(
                        "INSERT INTO variants(step_id,content,created,active) "
                        "VALUES(?,?,?,?)",
                        (
                            new_step_id,
                            _variant_content(variant.get("content")),
                            variant.get("created", time.time()),
                            int(active),
                        ),
                    )

        for participant in data.get("participants") or []:
            old_char_id = participant.get("char_id")
            new_char_id = old_char_map.get(old_char_id)

            if new_char_id is None:
                existing = q("SELECT id FROM characters WHERE id=?", (old_char_id,), one=True)
                if existing:
                    new_char_id = existing["id"]

            if new_char_id is None:
                raise HTTPException(
                    400,
                    f"Chat archive references character {old_char_id} "
                    f"but does not embed it",
                )

            qtx(
                "INSERT INTO chat_chars(chat_id,char_id,status,state) "
                "VALUES(?,?,?,?)",
                (
                    new_chat_id,
                    new_char_id,
                    participant.get("status", "active"),
                    participant.get("state", "{}"),
                ),
            )

        for cf in data.get("char_frames") or []:
            new_char_id = old_char_map.get(cf.get("char_id"))
            new_fid = frame_idmap.get(cf.get("frame_id"))
            if new_char_id is None or new_fid is None:
                continue
            qtx(
                "INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) "
                "VALUES(?,?,?,?,?)",
                (
                    new_chat_id,
                    new_char_id,
                    new_fid,
                    cf.get("status", "active"),
                    cf.get("state", "{}"),
                ),
            )

        bookmap = {}
        new_canon = None
        books = data.get("lorebooks")
        if books:
            for b in books:
                bk = b.get("book", {})
                nb = qtx(
                    "INSERT INTO lorebooks("
                    "name,chat_id,origin_id,book_type,summary,resource_uid,"
                    "anchor_entity_id,retired_turn_id"
                    ") VALUES(?,?,?,?,?,?,?,?)",
                    (
                        bk.get("name") or "book",
                        new_chat_id,
                        bk.get("origin_id"),
                        bk.get("book_type") or "general",
                        bk.get("summary") or "",
                        _import_book_uid(bk.get("resource_uid")),
                        bk.get("anchor_entity_id"),
                        # Turn-row FK: remap or null, never carry verbatim.
                        turn_id_map.get(bk.get("retired_turn_id")),
                    ),
                )
                restore_lorebook(nb, b.get("entries") or [])
                if bk.get("id"):
                    bookmap[bk["id"]] = nb
                if b.get("canon"):
                    new_canon = nb
                    qtx("UPDATE chats SET lorebook_id=? WHERE id=?", (nb, new_chat_id))
                else:
                    qtx(
                        "INSERT INTO chat_lorebooks("
                        "chat_id,lorebook_id,origin_id,enabled"
                        ") VALUES(?,?,?,?)",
                        (
                            new_chat_id,
                            nb,
                            bk.get("origin_id"),
                            1 if b.get("enabled", 1) else 0,
                        ),
                    )

        elif data.get("lorebook") and data["lorebook"].get("entries"):
            lb_data = data["lorebook"]
            new_canon = qtx(
                "INSERT INTO lorebooks("
                "name,chat_id,origin_id,resource_uid"
                ") VALUES(?,?,?,?)",
                (
                    (lb_data.get("book", {}).get("name") or "Imported canon") + " (import)",
                    new_chat_id,
                    lb_data.get("book", {}).get("id"),
                    _import_book_uid(lb_data.get("book", {}).get("resource_uid")),
                ),
            )
            restore_lorebook(new_canon, lb_data["entries"])
            old = lb_data.get("book", {}).get("id")
            if old:
                bookmap[old] = new_canon
            qtx("UPDATE chats SET lorebook_id=? WHERE id=?", (new_canon, new_chat_id))

        mems = [
            {
                "char_id": old_char_map.get(m.get("char_id")),
                "turn_id": turn_id_map.get(m.get("turn_id")),
                "turn_idx": m.get("turn_idx"),
                "frame_id": frame_idmap.get(m.get("frame_id")),
                "kind": m.get("kind", "episodic"),
                "category": m.get("category"),
                "provenance": m.get("provenance", "witnessed"),
                "salience": m.get("salience", 0.5),
                "content": m.get("content", ""),
                "gist": m.get("gist"),
                "key_phrases": m.get("key_phrases"),
                "entities": m.get("entities"),
                "location": m.get("location", ""),
                "emotional_context": m.get("emotional_context", ""),
                "valence": m.get("valence", 0.0),
                "arousal": m.get("arousal", 0.0),
                "confidence": m.get("confidence", 1.0),
                "archived": m.get("archived", False),
                "event_key": m.get("event_key", ""),
            }
            for m in data.get("memories", [])
            if m.get("content") and old_char_map.get(m.get("char_id"))
        ]
        restore_chat_memories(new_chat_id, mems)
        # char_id here is still the SOURCE database's id -- remap through
        # old_char_map exactly like `mems` above, and drop (rather than
        # import verbatim) any summary whose character wasn't embedded
        # in this archive: importing it unmapped would either crash the
        # whole import against PRAGMA foreign_keys=ON, or -- worse, if
        # the raw id happens to already exist locally -- silently attach
        # another character's autobiography to the wrong character.
        summaries = [
            {**s, "char_id": old_char_map[s["char_id"]]}
            for s in (data.get("memory_summaries") or [])
            if old_char_map.get(s.get("char_id"))
        ]
        restore_memory_summaries(new_chat_id, summaries)

        for e in data.get("events") or []:
            qtx(
                "INSERT INTO events(chat_id,turn_id,content) "
                "VALUES(?,?,?)",
                (
                    new_chat_id,
                    turn_id_map.get(e.get("turn_id")),
                    e["content"],
                ),
            )

        world = dict(data.get("world") or {})
        remapped_world = {}
        for k, v in world.items():
            base, key_frame_id = parse_scoped_world_key(k)
            if key_frame_id is None:
                remapped_world[k] = v
                continue
            new_frame_id = frame_idmap.get(key_frame_id)
            if new_frame_id is not None:
                remapped_world[f"{base}{_FRAME_KEY_SEP}{new_frame_id}"] = v
        world = remapped_world
        _remap_active_books(world, bookmap)
        # fixed_points frame_ids point at source frames -- rescope them to
        # the import's own frames (integer ids the string remaps never see).
        _remap_fixed_points_frames(world, frame_idmap)
        for k, v in world.items():
            wset(new_chat_id, k, v)

        # Populate the normalized world tables so world.scene/fixed_points
        # resolve against real rows (no false paradox on the first commit).
        # Import keeps the source entity ids verbatim (internally consistent
        # with the un-remapped world KV + checkpoint blobs); only the
        # created/retired turn FKs go through the turn idmap.
        world_tables = {
            k: [dict(r) for r in (data.get(k) or [])]
            for k in ("world_entities", "world_placements", "world_conditions",
                      "scheduled_events", "room_registry",
                      "fiction_worlds", "fiction_locations")
        }
        for ent in world_tables["world_entities"]:
            ent["created_turn_id"] = turn_id_map.get(ent.get("created_turn_id"))
            ent["retired_turn_id"] = turn_id_map.get(ent.get("retired_turn_id"))
        # room_registry: turn FKs through the turn idmap, the owning book's
        # integer id through bookmap (None when the book wasn't imported --
        # insert_world_tables also guards the FK); room_uid/parent_entity
        # stay verbatim like every other entity id on import.
        for rr in world_tables["room_registry"]:
            rr["created_turn_id"] = turn_id_map.get(rr.get("created_turn_id"))
            rr["retired_turn_id"] = turn_id_map.get(rr.get("retired_turn_id"))
            rr["owning_book_id"] = bookmap.get(rr.get("owning_book_id"))
        _remap_scheduled_event_frames(world_tables["scheduled_events"], frame_idmap)
        insert_world_tables(new_chat_id, world_tables)

        # Multiplayer roster + pre-submitted co-player inputs + lore link
        # graph -- remap persona_id through persona_idmap, frame_id through
        # frame_idmap; drop rows whose persona wasn't resolvable.
        for p in data.get("chat_personas") or []:
            new_pid = persona_idmap.get(p.get("persona_id"))
            if new_pid is None:
                continue
            qtx(
                "INSERT OR IGNORE INTO chat_personas(chat_id,persona_id,status,frame_id) "
                "VALUES(?,?,?,?)",
                (new_chat_id, new_pid, p.get("status", "active"),
                 frame_idmap.get(p.get("frame_id"))),
            )
        for tpi in data.get("turn_player_inputs") or []:
            new_pid = persona_idmap.get(tpi.get("persona_id"))
            if new_pid is None:
                continue
            qtx(
                "INSERT OR IGNORE INTO turn_player_inputs(chat_id,turn_idx,persona_id,input,created) "
                "VALUES(?,?,?,?,?)",
                (new_chat_id, tpi.get("turn_idx"), new_pid,
                 tpi.get("input", ""), tpi.get("created", time.time())),
            )
        restore_lorebook_links(new_chat_id, bookmap, data.get("lorebook_links") or [])

        for cp in data.get("checkpoints") or []:
            blob = cp["blob"] if isinstance(cp["blob"], str) else json.dumps(cp["blob"])
            blob = json.loads(blob)
            remapped = _remap_cp_blob(blob, turn_id_map, bookmap, new_canon,
                                      char_idmap=old_char_map, frame_idmap=frame_idmap)
            qtx(
                "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) "
                "VALUES(?,?,?,?)",
                (
                    new_chat_id,
                    cp["turn_idx"],
                    json.dumps(remapped),
                    cp.get("created", time.time()),
                ),
            )

    return dict(q("SELECT * FROM chats WHERE id=?", (new_chat_id,), one=True))

# ============================ MEMORIES ============================
@app.get("/api/chats/{cid}/characters/{ch}/memories")
def mem_list(
    cid: int, ch: int,
    include_archived: bool = Query(False),
    category: str | None = Query(None),
    provenance: str | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return {
        "memories": list_memories(
            cid, ch,
            include_archived=include_archived,
            category=category,
            provenance=provenance,
            limit=limit,
            offset=offset,
        ),
        "summary": get_memory_summary(cid, ch),
    }

@app.get("/api/chats/{cid}/characters/{ch}/memories/search")
def mem_search(
    cid: int, ch: int,
    query: str = Query(""),
    limit: int = Query(12, ge=1, le=50),
):
    latest = _latest_turn(cid)
    current_turn_idx = latest["idx"] if latest else 0
    return {
        "query": query,
        "results": search_memories(
            cid, ch, query, k=limit,
            include_archived=True,
            current_turn_idx=current_turn_idx,
            chronological=True,
        ),
    }

@app.get("/api/chats/{cid}/characters/{ch}/memories/export")
def mem_export(cid: int, ch: int):
    char = q("SELECT * FROM characters WHERE id=?", (ch,), one=True)
    if not char:
        raise HTTPException(404, "Character not found")
    return {
        "format": "fiction_engine.character_memories.v1",
        "char_name": character_name(json.loads(char["sheet"])),
        "memories": dump_character_memories(cid, ch),
    }

@app.post("/api/chats/{cid}/characters/{ch}/memories/import")
def mem_import(cid: int, ch: int, body: dict = Body(...)):
    if not q("SELECT 1 FROM characters WHERE id=?", (ch,), one=True):
        raise HTTPException(404, "Character not found")
    memories = body.get("memories")
    if not isinstance(memories, list):
        raise HTTPException(400, "Missing memories list")
    imported = import_character_memories(cid, ch, memories)
    return {"ok": True, "imported": imported}

@app.get("/api/chats/{cid}/characters/{ch}/memory-context")
def memory_context_preview(
    cid: int, ch: int,
    query: str = Query(""),
):
    latest = _latest_turn(cid)
    current_turn_idx = latest["idx"] if latest else 0
    return build_character_memory_context(
        chat_id=cid, char_id=ch,
        current_turn_idx=current_turn_idx,
        current_view=query, active_state={},
    )

@app.get("/api/chats/{cid}/characters/{ch}/relationships")
def relationships_get(cid: int, ch: int):
    """How this character currently feels about everyone else they've
    interacted with in this chat -- trust/familiarity/emotional_valence/fear,
    plus what drove the last shift (salient_event) and when
    (last_interaction_turn). Read-only view onto the same relationship
    graph the character agent itself reads each turn; nothing here is
    computed fresh for this endpoint.
    """
    return relationships_for_payload(cid, ch)

@app.post("/api/chats/{cid}/characters/{ch}/memories/consolidate")
def mem_consolidate(cid: int, ch: int, body: dict = Body(default={})):
    try:
        return consolidate_character_memory(
            cid, ch,
            through_turn_idx=body.get("through_turn_idx"),
            archive_old=body.get("archive_old", True),
        )
    except Exception as exc:
        raise HTTPException(502, str(exc))

@app.post("/api/chats/{cid}/characters/{ch}/memories")
def mem_add(cid: int, ch: int, body: dict = Body(...)):
    try:
        salience = float(body.get("salience", 0.5))
    except (TypeError, ValueError):
        raise HTTPException(400, "salience must be a number")
    mid = add_memory(
        cid, ch, body.get("turn_id"),
        body.get("kind", "episodic"),
        body.get("provenance", "told"),
        salience,
        body.get("content", ""),
        category=body.get("category"),
        gist=body.get("gist"),
        key_phrases=body.get("key_phrases"),
        entities=body.get("entities"),
        location=body.get("location", ""),
        emotional_context=body.get("emotional_context", ""),
        event_key=body.get("event_key", ""),
    )
    return {"id": mid}

@app.put("/api/memories/{mid}")
def mem_edit(mid: int, body: dict = Body(...)):
    ok = update_memory(
        mid, body.get("content"), body.get("salience"),
        body.get("kind"), body.get("provenance"),
        category=body.get("category"),
        gist=body.get("gist"),
        key_phrases=body.get("key_phrases"),
        entities=body.get("entities"),
        location=body.get("location"),
        emotional_context=body.get("emotional_context"),
        valence=body.get("valence"),
        arousal=body.get("arousal"),
        confidence=body.get("confidence"),
        archived=body.get("archived"),
    )
    if not ok: raise HTTPException(404)
    return {"ok": True}

@app.delete("/api/memories/{mid}")
def mem_del(mid: int):
    delete_memory(mid)
    return {"ok": True}

# ============================ TURNS & PIPELINE ============================
@app.post("/api/chats/{cid}/turns")
def turn_new(cid: int, body: dict = Body(...)):
    frame_id = body.get("frame_id")
    frame_id = int(frame_id) if frame_id is not None else None
    if frame_id is not None:
        fr = get_frame(frame_id)
        # Frame must exist AND belong to THIS chat -- a bare existence check
        # would let a request operate on another chat's frame.
        if fr is None or fr["chat_id"] != cid:
            raise HTTPException(404, f"Frame {frame_id} not found")
    _require_frame_idle(cid, frame_id)
    _require_turn_resolved(cid, frame_id)
    # Claim the pipeline slot (the atomic race-closing gate) BEFORE creating
    # the turn row: a 409-losing request must not leave a stepless orphan
    # turn that then blocks the frame. run_pipeline reuses this abort.
    abort = _begin_pipeline_or_409(cid, frame_id)
    try:
        # idx allocation is chat-GLOBAL (play order across every frame), so
        # two frames creating turns at nearly the same moment race on
        # computing "current max + 1" -- wrapped in a transaction so the
        # read-compute-insert is atomic against any other concurrent writer,
        # not just against itself.
        with transaction():
            last = _latest_turn(cid)
            idx = (last["idx"] + 1) if last else 0
            tid = qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                     (cid, idx, _player_input(body), time.time(), frame_id))
        ensure_checkpoint(cid, idx)
    except BaseException:
        # Release the slot we grabbed if row/checkpoint creation failed, so
        # a later request isn't wrongly rejected as "already running".
        ABORTS.pop((cid, frame_id), None)
        raise
    return _stream(run_pipeline(cid, tid, abort=abort, frame_id=frame_id))

@app.post("/api/chats/{cid}/abort")
def chat_abort(cid: int, frame_id: int | None = Query(None)):
    return {"aborted": request_abort(cid, frame_id)}

@app.post("/api/turns/{tid}/branch")
def turn_branch(tid: int):
    turn = q(
        "SELECT * FROM turns WHERE id=?",
        (tid,),
        one=True,
    )
    if not turn:
        raise HTTPException(404, "Turn not found")

    _require_chat_idle(turn["chat_id"])
    active_paradox = paradox.get_paradox(turn["chat_id"], turn["frame_id"])
    if active_paradox:
        raise HTTPException(
            409,
            "A paradox is unfolding in this frame -- resolve it before branching from here.",
        )

    cid, idx = turn["chat_id"], turn["idx"]
    src = dict(q("SELECT * FROM chats WHERE id=?", (cid,), one=True))

    nxt = q(
        "SELECT * FROM checkpoints WHERE chat_id=? AND turn_idx=?",
        (cid, idx + 1),
        one=True
    )
    blob = json.loads(nxt["blob"]) if nxt else snapshot_state(cid)

    # Mirror chat_import: every insert from the new chats row through the
    # final checkpoint commits atomically, so a mid-branch failure cannot
    # leave a visible half-built chat behind.
    with transaction():
        ncid = qtx(
            "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
            (f"{src['name']} ⎇{idx}", src["persona_id"], src["scenario"], time.time())
        )

        # Clone every declared frame (chat-wide declarations, not turn-scoped
        # like turns/steps below -- a frame created after the branch point
        # still needs to exist in the branch if any copied turn/memory
        # references it) with a fresh id, so copied turns/memories can point
        # at THIS chat's own frame rows instead of dangling on the source
        # chat's.
        frame_idmap = {}
        for f in q("SELECT * FROM frames WHERE chat_id=?", (cid,)):
            nfid = qtx(
                "INSERT INTO frames(chat_id,label,ordinal,kind,travelers,nonexistent_cast,created,"
                "split_turn_idx,merged_turn_idx) VALUES(?,?,?,?,?,?,?,?,?)",
                (ncid, f["label"], f["ordinal"], f["kind"], f["travelers"], f["nonexistent_cast"], f["created"],
                 f["split_turn_idx"], f["merged_turn_idx"]),
            )
            frame_idmap[f["id"]] = nfid
        # parent_frame_id is self-referential -- deferred to a second pass,
        # same reasoning as chat_import's identical remap.
        for f in q("SELECT id, parent_frame_id FROM frames WHERE chat_id=?", (cid,)):
            if f["parent_frame_id"] is not None and f["parent_frame_id"] in frame_idmap:
                qtx(
                    "UPDATE frames SET parent_frame_id=? WHERE id=?",
                    (frame_idmap[f["parent_frame_id"]], frame_idmap[f["id"]]),
                )

        # Copy chat characters
        for cc in q("SELECT * FROM chat_chars WHERE chat_id=?", (cid,)):
            qtx(
                "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
                (ncid, cc["char_id"], cc["status"], cc["state"])
            )

        # Copy per-frame character overrides (state/status divergence between
        # frames), remapping each row's frame_id to this branch's own frame.
        for ccf in q("SELECT * FROM chat_char_frames WHERE chat_id=?", (cid,)):
            nfid = frame_idmap.get(ccf["frame_id"])
            if nfid is None:
                continue
            qtx(
                "INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) "
                "VALUES(?,?,?,?,?)",
                (ncid, ccf["char_id"], nfid, ccf["status"], ccf["state"])
            )

        # Copy turns, steps, and variants
        idmap = {}
        for t in q("SELECT * FROM turns WHERE chat_id=? AND idx<=? ORDER BY idx", (cid, idx)):
            nt = qtx(
                "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                (ncid, t["idx"], t["player_input"], t["created"], frame_idmap.get(t["frame_id"]))
            )
            idmap[t["id"]] = nt

            for s in q("SELECT * FROM steps WHERE turn_id=? ORDER BY ord", (t["id"],)):
                ns = qtx(
                    "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,?)",
                    (nt, s["key"], s["label"], s["ord"], s["stale"])
                )
                for v in q("SELECT * FROM variants WHERE step_id=? ORDER BY id", (s["id"],)):
                    qtx(
                        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,?)",
                        (ns, v["content"], v["created"], v["active"])
                    )

            for e in q("SELECT * FROM events WHERE turn_id=?", (t["id"],)):
                qtx(
                    "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
                    (ncid, nt, e["content"])
                )

        # Restore character states from the snapshot
        for cidk, st in (blob.get("chars") or {}).items():
            if isinstance(st, dict) and "status" in st and "state" in st:
                qtx(
                    "UPDATE chat_chars SET state=?,status=? WHERE chat_id=? AND char_id=?",
                    (json.dumps(st["state"]), st["status"], ncid, int(cidk))
                )
            else:
                qtx(
                    "UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
                    (json.dumps(st), ncid, int(cidk))
                )

        # Snapshot char_frames reflects the branch point exactly (unlike the
        # raw copy above, which mirrors the source chat's CURRENT overlay
        # rows) -- replace with the snapshot's version, remapped to this
        # branch's frame ids.
        qtx("DELETE FROM chat_char_frames WHERE chat_id=?", (ncid,))
        for cf in blob.get("char_frames") or []:
            nfid = frame_idmap.get(cf.get("frame_id"))
            if nfid is None:
                continue
            qtx(
                "INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) "
                "VALUES(?,?,?,?,?)",
                (ncid, cf["char_id"], nfid, cf.get("status", "active"),
                 json.dumps(cf.get("state") or {}))
            )

        # Restore memories and summaries
        mems = []
        for m in (blob.get("memories") or []):
            m = dict(m)
            m["turn_id"] = idmap.get(m.get("turn_id"))
            m["frame_id"] = frame_idmap.get(m.get("frame_id"))
            mems.append(m)

        restore_chat_memories(ncid, mems)
        restore_memory_summaries(ncid, blob.get("memory_summaries") or [])

        # Build world ID remap ONCE from the source snapshot, up front:
        # the lorebook clone below needs it to remap vehicle-book
        # anchor_entity_id, and every checkpoint for the branched chat must
        # reuse the same new ids.
        #
        # Protect character / player-persona identities from remapping: they
        # appear in world_entities keyed by name but are looked up by that
        # stable name/uid, so remapping their id orphans the scene position (the
        # "unspecified location" branch bug). Object entity ids remap freely.
        _protected_ids = _branch_protected_identity_ids(cid, src.get("persona_id"))
        world_id_remap = _build_world_id_remap(blob, _protected_ids)

        # --- Lorebook Tree Cloning ---
        bookmap = {}
        new_canon = None
        snap_books = blob.get("lorebooks")

        # Fallback for older checkpoints without the lorebooks array
        if snap_books is None and blob.get("lore") and blob["lore"].get("entries") is not None:
            lo = blob["lore"]
            snap_books = [{
                "lorebook_id": lo.get("lorebook_id"),
                "canon": True,
                "name": f"{src['name']} ⎇{idx} — canon",
                "entries": lo.get("entries")
            }]

        # Pass 1: Create all books without parent references, clone entries safely
        for b in snap_books or []:
            old_id = b.get("lorebook_id")
            _anchor = b.get("anchor_entity_id")
            nb = qtx(
                "INSERT INTO lorebooks("
                "name,chat_id,origin_id,book_type,summary,"
                "parent_id,scope_world_id,scope_location_id,"
                "inheritance_mode,sort_order,resource_uid,anchor_entity_id,"
                "retired_turn_id"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    b.get("name") or "canon",
                    ncid,
                    b.get("origin_id") or old_id,
                    b.get("book_type") or "general",
                    b.get("summary") or "",
                    None,  # Parent ID deferred to Pass 2
                    b.get("scope_world_id"),
                    b.get("scope_location_id"),
                    b.get("inheritance_mode") or "inherit",
                    int(b.get("sort_order") or 0),
                    new_uid("book"),
                    # Vehicle-book anchor follows an entity -- remap it to the
                    # branch's own entity id so the book keeps tracking it.
                    (world_id_remap.get(_anchor, _anchor) if _anchor else _anchor),
                    # Retirement stamp is a turn-row FK -- remap through the
                    # branch's turn idmap or null it (uncloned turn).
                    idmap.get(b.get("retired_turn_id")),
                )
            )

            if old_id:
                bookmap[int(old_id)] = nb

            # _clone_snapshot_entries generates fresh entry_uids to avoid
            # UNIQUE constraint crashes
            _clone_snapshot_entries(nb, b.get("entries") or [])

            if b.get("canon"):
                new_canon = nb
                qtx("UPDATE chats SET lorebook_id=? WHERE id=?", (nb, ncid))
            else:
                qtx(
                    "INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) "
                    "VALUES(?,?,?,?)",
                    (ncid, nb, b.get("origin_id") or old_id,
                     1 if b.get("enabled", 1) else 0)
                )

        # Pass 2: Remap parent IDs to preserve hierarchy
        for b in snap_books or []:
            old_parent = b.get("parent_id")
            new_book = bookmap.get(b.get("lorebook_id"))
            new_parent = bookmap.get(old_parent)

            if new_book is not None:
                qtx(
                    "UPDATE lorebooks SET parent_id=? WHERE id=?",
                    (new_parent, new_book)
                )

        # Restore lorebook links only if both endpoints exist in the branch
        branch_links = []
        for link in blob.get("lorebook_links") or []:
            s = link.get("source_book_id")
            t = link.get("target_book_id")
            if s in bookmap and t in bookmap:
                branch_links.append(link)

        restore_lorebook_links(ncid, bookmap, branch_links)

        # Restore world state (deep-copy so blob stays untouched for checkpoints)
        world = json.loads(json.dumps(blob.get("world") or {}))
        # Retired-concept cleanup: current_frame_id/frame_bundle:* were written
        # by the old whole-chat frame-swap mechanism (replaced by frame-scoped
        # storage keys -- see db.py's active_frame_id). Harmless no-ops unless
        # a chat has stale rows from before that refactor.
        world.pop("current_frame_id", None)
        for key in [k for k in world if k.startswith("frame_bundle:")]:
            world.pop(key, None)
        # Frame-scoped keys (e.g. "scene<sep>fr5") embed the SOURCE chat's
        # frame id -- remap it to the branch's own corresponding frame (built
        # above), or drop the row if that frame somehow wasn't cloned, rather
        # than leave a key pointing at a frame id that means nothing here.
        remapped_world = {}
        for key, val in world.items():
            base, key_frame_id = parse_scoped_world_key(key)
            if key_frame_id is None:
                remapped_world[key] = val
                continue
            new_frame_id = frame_idmap.get(key_frame_id)
            if new_frame_id is not None:
                remapped_world[f"{base}{_FRAME_KEY_SEP}{new_frame_id}"] = val
        world = remapped_world
        _remap_active_books(world, bookmap)
        if world_id_remap:
            for k, v in list(world.items()):
                if isinstance(v, str):
                    try:
                        parsed = json.loads(v)
                        if isinstance(parsed, (dict, list)):
                            world[k] = json.dumps(
                                _deep_remap_ids(parsed, world_id_remap)
                            )
                    except (json.JSONDecodeError, TypeError):
                        world[k] = world_id_remap.get(v, v)
                elif isinstance(v, (dict, list)):
                    world[k] = _deep_remap_ids(v, world_id_remap)
        # fixed_points carry integer frame_ids the generic string remap
        # above never touched -- rescope them to the branch's own frames.
        _remap_fixed_points_frames(world, frame_idmap)
        for k, v in world.items():
            wset(ncid, k, v)

        # Populate the normalized world tables from the branch-point blob,
        # remapped to this branch's ids. Without this the tables stay empty
        # while world.scene + fixed_points reference entities -- a false
        # paradox fires on the first commit. created/retired turn FKs go
        # through the turn idmap (None when the turn wasn't cloned).
        world_tables = json.loads(json.dumps({
            k: (blob.get(k) or [])
            for k in ("world_entities", "world_placements", "world_conditions",
                      "scheduled_events", "room_registry",
                      "fiction_worlds", "fiction_locations")
        }))
        if world_id_remap:
            for k in world_tables:
                world_tables[k] = _deep_remap_ids(world_tables[k], world_id_remap)
                _remap_row_json_fields(world_tables[k], world_id_remap)
        for ent in world_tables["world_entities"]:
            ent["created_turn_id"] = idmap.get(ent.get("created_turn_id"))
            ent["retired_turn_id"] = idmap.get(ent.get("retired_turn_id"))
        # room_registry: turn FKs through the branch turn idmap; the owning
        # book's integer id through bookmap (parent_entity already followed
        # the entity remap via _deep_remap_ids above).
        for rr in world_tables["room_registry"]:
            rr["created_turn_id"] = idmap.get(rr.get("created_turn_id"))
            rr["retired_turn_id"] = idmap.get(rr.get("retired_turn_id"))
            rr["owning_book_id"] = bookmap.get(rr.get("owning_book_id"))
        _remap_scheduled_event_frames(world_tables["scheduled_events"], frame_idmap)
        insert_world_tables(ncid, world_tables)

        # Clone the multiplayer roster + any pre-submitted co-player inputs
        # (frame_id remapped; persona ids are same-DB in a branch). Without
        # these the branch loses every extra player's station and queued
        # beats.
        for p in q("SELECT * FROM chat_personas WHERE chat_id=?", (cid,)):
            qtx(
                "INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
                "VALUES(?,?,?,?)",
                (ncid, p["persona_id"], p["status"], frame_idmap.get(p["frame_id"])),
            )
        for tpi in q("SELECT * FROM turn_player_inputs WHERE chat_id=? AND turn_idx<=?", (cid, idx)):
            qtx(
                "INSERT INTO turn_player_inputs(chat_id,turn_idx,persona_id,input,created) "
                "VALUES(?,?,?,?,?)",
                (ncid, tpi["turn_idx"], tpi["persona_id"], tpi["input"], tpi["created"]),
            )

        # Copy checkpoints safely (using deep copies to prevent mutation issues)
        for cp in q("SELECT * FROM checkpoints WHERE chat_id=? AND turn_idx<=?", (cid, idx)):
            cp_blob = json.loads(cp["blob"])
            b = _remap_cp_blob(
                cp_blob, idmap, bookmap, new_canon,
                world_id_remap=world_id_remap, frame_idmap=frame_idmap,
            )
            qtx(
                "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
                (ncid, cp["turn_idx"], json.dumps(b), time.time())
            )

        # Final checkpoint snapshot for the newly branched chat
        final_blob = json.loads(json.dumps(blob))
        b = _remap_cp_blob(
            final_blob, idmap, bookmap, new_canon,
            world_id_remap=world_id_remap, frame_idmap=frame_idmap,
        )
        qtx(
            "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
            (ncid, idx + 1, json.dumps(b), time.time())
        )

    return dict(q("SELECT * FROM chats WHERE id=?", (ncid,), one=True))
    
@app.put("/api/turns/{tid}/input")
def edit_input(tid: int, body: dict = Body(...)):
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")
    # Don't flip steps stale / rewrite input while a pipeline is building
    # those very steps for this turn.
    _require_chat_idle(turn["chat_id"])
    qi("UPDATE turns SET player_input=? WHERE id=?", (_player_input(body), tid))
    lt = _latest_turn(turn["chat_id"])
    latest = lt and lt["id"] == tid
    if latest:
        qi("UPDATE steps SET stale=1 WHERE turn_id=?", (tid,))
    return {"ok": True, "latest": latest}

@app.put("/api/turns/{tid}/prose")
def edit_prose(tid: int, body: dict = Body(...)):
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")

    step = q(
        "SELECT * FROM steps WHERE turn_id=? AND key='narrator'",
        (tid,),
        one=True,
    )
    if not step:
        raise HTTPException(404, "This turn has no narrator output to edit")

    content = active_content(tid, "narrator") or {}
    content["prose"] = str(body.get("prose", ""))

    # Unlike /api/steps/{sid}/edit, this deliberately does not mark
    # anything stale. The director/perception/commit steps that already
    # ran are the actual mechanical record of what happened -- commit in
    # particular already applied its memory/world-state side effects, and
    # those aren't idempotent, so nothing here should make them
    # reroll/rerun-eligible. A prose edit only changes how an already-true
    # beat reads to the player, same class of operation as fixing a typo.
    qi("UPDATE variants SET active=0 WHERE step_id=?", (step["id"],))
    qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (step["id"], json.dumps(content, ensure_ascii=False), time.time()),
    )
    return {"ok": True, "prose": content["prose"]}

@app.get("/api/turns/{tid}/pipeline")
def pipeline_get(tid: int):
    steps = []
    for s in q("SELECT * FROM steps WHERE turn_id=? ORDER BY ord", (tid,)):
        vs = [dict(r) for r in q("SELECT id,content,active,created FROM variants WHERE step_id=? ORDER BY id", (s["id"],))]
        steps.append({"id": s["id"], "key": s["key"], "label": s["label"], "ord": s["ord"], "stale": bool(s["stale"]), "variants": vs})
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")
    frame_latest = _latest_turn_in_frame(turn["chat_id"], turn["frame_id"])
    is_frame_latest = bool(frame_latest and frame_latest["id"] == tid)
    # editable mirrors _require_latest's actual gate: frame-latest AND no
    # other frame has advanced past this point (see that function for why
    # both are required). Surfaced separately so the UI can explain WHY
    # a frame-latest turn is still blocked, instead of just refusing.
    blocked_by_other_frame = is_frame_latest and _other_frame_has_advanced_past(
        turn["chat_id"], turn["frame_id"], turn["idx"])
    editable = is_frame_latest and not blocked_by_other_frame

    from agents import resume_key_for_turn

    resume_key = resume_key_for_turn(tid, turn["chat_id"]) if editable else None

    return {
        "steps": steps,
        "editable": editable,
        "blocked_by_other_frame": blocked_by_other_frame,
        "resume_key": resume_key,
        "resumable": bool(resume_key),
    }

@app.post("/api/turns/{tid}/reroll")
def turn_reroll(tid: int):
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")
    _require_latest(turn)
    _require_chat_idle(turn["chat_id"])
    abort = _begin_pipeline_or_409(turn["chat_id"], turn["frame_id"])
    return _stream(run_pipeline(turn["chat_id"], tid, abort=abort, frame_id=turn["frame_id"]))

@app.post("/api/turns/{tid}/rerun")
def turn_rerun(tid: int, body: dict = Body(...)):
    turn = q(
        "SELECT * FROM turns WHERE id=?",
        (tid,),
        one=True,
    )

    if not turn:
        raise HTTPException(404, "Turn not found")

    _require_latest(turn)
    _require_chat_idle(turn["chat_id"])

    from_key = body.get("from_key")

    abort = _begin_pipeline_or_409(turn["chat_id"], turn["frame_id"])
    return _stream(run_pipeline(
        turn["chat_id"],
        tid,
        from_key=from_key,
        abort=abort,
        frame_id=turn["frame_id"],
    ))

# ---- Pipeline resume endpoint ----

@app.post("/api/turns/{tid}/resume")
def turn_resume(tid: int):
    turn = q(
        "SELECT * FROM turns WHERE id=?",
        (tid,),
        one=True,
    )
    if not turn:
        raise HTTPException(404, "Turn not found")

    _require_latest(turn)
    _require_chat_idle(turn["chat_id"])

    from agents import resume_key_for_turn

    resume_key = resume_key_for_turn(tid, turn["chat_id"])

    if resume_key is None:
        raise HTTPException(
            409,
            "This turn is already complete"
        )

    abort = _begin_pipeline_or_409(turn["chat_id"], turn["frame_id"])
    return _stream(run_pipeline(
        turn["chat_id"],
        tid,
        from_key=resume_key,
        abort=abort,
        frame_id=turn["frame_id"],
    ))

@app.post("/api/steps/{sid}/reroll")
def step_reroll(sid: int):
    step = q(
        "SELECT * FROM steps WHERE id=?",
        (sid,),
        one=True,
    )

    if not step:
        raise HTTPException(404, "Step not found")

    turn = q(
        "SELECT * FROM turns WHERE id=?",
        (step["turn_id"],),
        one=True,
    )

    if not turn:
        raise HTTPException(404, "Turn not found")

    _require_latest(turn)
    _require_chat_idle(turn["chat_id"])

    abort = _begin_pipeline_or_409(turn["chat_id"], turn["frame_id"])
    return _stream(run_pipeline(
        turn["chat_id"],
        turn["id"],
        only_key=step["key"],
        abort=abort,
        frame_id=turn["frame_id"],
    ))

def _require_step_turn(sid: int):
    s = q("SELECT * FROM steps WHERE id=?", (sid,), one=True)
    if not s:
        raise HTTPException(404, "Step not found")
    turn = q("SELECT * FROM turns WHERE id=?", (s["turn_id"],), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")
    # Editing/activating a step on a non-latest turn is otherwise silent:
    # nothing stops it, but the edit can never be resumed/recommitted
    # since later turns' checkpoints already derive from the turn's
    # original content -- it just permanently desyncs.
    _require_latest(turn)
    _require_chat_idle(turn["chat_id"])
    return s

@app.post("/api/steps/{sid}/edit")
def step_edit(sid: int, body: dict = Body(...)):
    s = _require_step_turn(sid)
    with transaction():
        qi("UPDATE variants SET active=0 WHERE step_id=?", (sid,))
        vid = qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                 (sid, json.dumps(body.get("content")), time.time()))
    qi("UPDATE steps SET stale=1 WHERE turn_id=? AND ord>?", (s["turn_id"], s["ord"]))
    return {"variant_id": vid}

@app.post("/api/steps/{sid}/activate")
def step_activate(sid: int, body: dict = Body(...)):
    s = _require_step_turn(sid)
    variant_id = body.get("variant_id")
    variant = q("SELECT id FROM variants WHERE id=? AND step_id=?", (variant_id, sid), one=True)
    if not variant:
        raise HTTPException(404, "Variant not found on this step")
    with transaction():
        qi("UPDATE variants SET active=0 WHERE step_id=?", (sid,))
        qi("UPDATE variants SET active=1 WHERE id=?", (variant_id,))
    qi("UPDATE steps SET stale=1 WHERE turn_id=? AND ord>?", (s["turn_id"], s["ord"]))
    return {"ok": True}

@app.delete("/api/turns/{tid}")
def turn_del(tid: int):
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")

    _require_latest(turn)
    _require_chat_idle(turn["chat_id"])

    with transaction():
        # The checkpoint restore must live in the SAME transaction as the
        # deletes: restoring first and deleting after (as two separate
        # commits) meant a failed delete left the chat rewound to the
        # turn's start while the turn/steps still existed. The restore
        # runs before the deletes so it can still read the checkpoint row
        # for this idx, which the deletes below remove.
        restore_checkpoint(turn["chat_id"], turn["idx"])

        for step in q(
            "SELECT id FROM steps WHERE turn_id=?",
            (tid,),
        ):
            qi(
                "DELETE FROM variants WHERE step_id=?",
                (step["id"],),
            )

        qi("DELETE FROM steps WHERE turn_id=?", (tid,))
        delete_turn_memories(tid)
        qi("DELETE FROM events WHERE turn_id=?", (tid,))
        qi(
            "DELETE FROM checkpoints "
            "WHERE chat_id=? AND turn_idx>=?",
            (turn["chat_id"], turn["idx"]),
        )
        qi("DELETE FROM turns WHERE id=?", (tid,))

    return {"ok": True}