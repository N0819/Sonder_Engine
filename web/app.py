import contextvars, json, queue, random, re, time, threading, os, zlib
from core import updates
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body, HTTPException, Query, Request
from starlette.datastructures import Headers
from fastapi.responses import (StreamingResponse, JSONResponse, FileResponse,
                               Response)
from fastapi.staticfiles import StaticFiles

from story import attire
import extension_runtime
from web import guest_access as guest

from core import db
from core.db import (q, qi, qtx, transaction, wget, wset, get_setting, set_setting,
                parse_scoped_world_key, data_version)
from core.db import _FRAME_KEY_SEP
from llm import providers
from llm.providers import (
    chat_complete, chat_complete_async, token_sink, cancel_event,
    resolve_role, list_models, list_image_models, image_model, provider, agent_models,
    openrouter_routing, normalize_openrouter_routing, list_openrouter_endpoints,
    max_output_tokens, _coerce_max_output_tokens,
    reasoning_efforts, _coerce_reasoning_effort, REASONING_EFFORTS,
    MAX_OUTPUT_TOKENS_DEFAULT, MAX_OUTPUT_TOKENS_MIN, MAX_OUTPUT_TOKENS_MAX,
    DEFAULT_BASES, ROLES, ROLE_FALLBACKS, SAMPLER_KEYS, DEFAULT_SAMPLERS, Aborted,
)
from core.pipeline_context import PipelineContext, ChatData, TurnData
from story.dialogue_colors import normalize_color, resolve_cast_colors
from persist.checkpoints import (ensure_checkpoint, restore_checkpoint, snapshot_state,
                         refresh_checkpoint, insert_world_tables,
                         checkpoint_storage_status, compaction_progress,
                         start_compaction,
                         propagate_memory_summaries_to_checkpoints,
                         PRESERVED_SETTING_KEYS)
from core.frames import create_frame, get_frame, list_frames
from world import paradox
from story import greetings
from agents import (
    run_pipeline, request_abort, begin_pipeline,
    active_content, ABORTS, PipelineBusyError,
    fanout_is_parallel as director_fanout_is_parallel,
)
from story.character_schema import (
    character_export_document,
    character_initial_outfit,
    character_name,
    character_name_from_text,
    fold_identity_key,
    default_character_data,
    default_persona_data,
    new_uid,
    normalize_character_data,
    normalize_persona_data,
    persona_export_document,
    persona_initial_outfit,
    persona_name,
)
from story.scene import (background_config, dialogue_config, interaction_limits,
                   normalize_offscreen_life, player_authority,
                   set_player_authority, PLAYER_AUTHORITY_GRANTS,
                   PLAYER_AUTHORITY_MODES,
                   style_guide, normalize_style_guide,
                   OFFSCREEN_LIFE_BUILT, OFFSCREEN_LIFE_DEFAULT,
                   OFFSCREEN_LIFE_DESCRIPTIONS, OFFSCREEN_LIFE_LADDER,
                   STYLE_GUIDE_FIELDS)
from story.importers import (
    import_character, import_persona, import_lorebook,
    generate_character, generate_persona, generate_lore_entries,
    reinterpret_lorebook, resolve_import_card, draft_promoted_character,
    recover_greetings_from_source, character_import_warnings,
    fill_character_psychology, fill_appearance,
)
from persist.commit import (commit_all, promotable_background_presences,
                    promote_background_character,
                    _known_name_roster, sync_room_registry_with_scene)
from llm.prompts import (
    presets, active_preset, get_prompt, DEFAULT_PROMPTS, nsfw_enabled,
    default_prompts_for, preset_export_document, preset_import_document,
    unique_preset_name,
)
from language_runtime import (
    DEFAULT_LANGUAGE, STORY_LANGUAGE_KEY, LanguagePackError,
    installed_language_packs,
    language_scope, require_language_pack, set_story_language, set_ui_language,
    story_language, story_language_scope, ui_language,
)
from mind.memory import (
    add_lore, update_lore, delete_lore, LORE_CATEGORIES,
    LOREBOOK_TYPES, MEMORY_CATEGORIES, MEMORY_PROVENANCE, 
    LOREBOOK_LINK_TYPES, duplicate_lorebook_for_chat,
    list_memories, update_memory, delete_memory, add_memory,
    add_memories_batch,
    search_memories, build_character_memory_context,
    get_memory_summary, consolidate_character_memory,
    backfill_memory_summary_windows, memory_summary_coverage,
    restore_chat_memories, restore_lorebook, dump_lorebook,
    dump_chat_memories, dump_memory_summaries, restore_memory_summaries,
    chat_lorebook_ids, delete_turn_memories,
    restore_lorebook_links, dump_lorebook_links,
    relationships_for_payload,
    dramatic_irony_feed, promise_ledger,
    dump_character_memories, import_character_memories,
    embedding_bank_status, rebuild_progress, start_rebuild_if_needed,
    queue_fallback_rows_for_repair,
)
from story.scene import (
    persona_of, get_scene, chat_character_sheet, seed_initial_attire,
    weather_severity,
)
from dressing.backdrops import (build_backdrop_request, request_backdrop, cached_backdrop,
                       backdrop_status, backdrop_error)
from dressing.ambience import (FREESOUND_LICENCES, ambience_error, ambience_error_kind,
                      ambience_pin_for,
                      ambience_pins, ambience_settings, ambience_status,
                      build_ambience_request, cached_ambience,
                      clear_ambience_pin, library_files, media_type_for,
                      ONESHOT_VARIANTS, request_ambience, request_oneshot,
                      search_candidates,
                      set_ambience_pin)
from web.auth_routes import (
    GUEST_ALLOWED_API_PATHS,
    GUEST_COOKIE,
    HOST_COOKIE,
    PUBLIC_API_PATHS,
    router as auth_router,
)

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
def _reconcile_embedding_bank():
    """Hand the memory bank back to the reconciler, off the startup path.

    `memory.start_rebuild_if_needed` documents itself as "safe to call on every
    startup and every settings write", and startup never called it. The
    invitation was written into the function and never taken up, so the only
    things that reconciled a bank were a checkpoint restore and the host
    clicking the button.

    That matters because a degraded WRITE is permanent. Measured across the
    live corpus: 39 embedding fallbacks, every one of them an HTTP 429 from the
    provider, and each leaves its rows stamped `cheap:crc32:256` -- reachable
    by keyword and invisible to semantic recall until somebody pays for a
    rebuild. A rate limit is a transient condition writing a permanent defect,
    and the repair for it already existed one call away.

    On its OWN thread because the decision costs a provider round trip
    (`embedding_bank_status` asks what the live model is), and startup must not
    wait on the network to serve its first request. Failures are logged and
    swallowed on the same rule the checkpoint path follows: a maintenance task
    must never be able to break the thing it was maintaining.
    """
    def _go():
        try:
            from mind.memory import start_rebuild_if_needed
            decision = start_rebuild_if_needed()
            if decision.get("started"):
                print("Sonder Engine: reconciling %d memory rows onto the "
                      "live embedding model in the background."
                      % decision.get("stranded", 0), flush=True)
        except Exception as exc:                     # never fail startup
            print("Sonder Engine: embedding reconcile skipped (%s)." % exc,
                  flush=True)
    threading.Thread(target=_go, name="startup-embedding-reconcile",
                     daemon=True).start()


def _startup_engine():
    db.init()
    _reconcile_embedding_bank()
    port = os.environ.get("FICTION_ENGINE_PORT", "8008")
    # FICTION_ENGINE_RESET_HOST is the forgot-password escape hatch: wipe
    # the account (and every session) so /login shows first-run setup again.
    # It runs on EVERY startup while the variable stays set -- an environment
    # variable cannot un-set itself -- so left in a launch script it silently
    # wipes each replacement account on the next restart. That happened: an
    # account re-created after a reset was gone again a restart later, and
    # nothing had said the hatch was still armed. Announce it every time.
    if os.environ.get("FICTION_ENGINE_RESET_HOST"):
        had_account = guest.host_account_exists()
        guest.reset_host_account()
        print(
            "\n"
            "Sonder Engine: FICTION_ENGINE_RESET_HOST is set. "
            + ("The host account and every session were just wiped."
               if had_account else
               "No host account existed; nothing to wipe.")
            + " This repeats on EVERY restart while the variable stays "
            "set -- unset FICTION_ENGINE_RESET_HOST before creating the "
            "new account, or the next restart deletes that one too.\n",
            flush=True,
        )
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


class SelectiveGZipMiddleware:
    """gzip ordinary JSON, never a streamed response.

    Worth having because the UI catalog is large: `/api/bootstrap` carries a
    full message catalog (~190KB for Japanese, a third of the response) and
    `/api/ui` carries another -- about 816KB per page load, compressing to
    roughly a third.

    Streaming is EXCLUDED, and not as a precaution. Starlette's own
    GZipResponder writes each streamed chunk into a `GzipFile`, and the
    compressor buffers internally: a turn's NDJSON lines are far too small to
    fill that buffer, so nothing reaches the browser until enough has
    accumulated. Applying it to the turn stream stalled the live view -- the
    stage indicator stopped advancing, token deltas stopped appearing, and the
    client eventually gave up on a connection that looked dead, which the
    server then recorded as `Aborted: generation aborted by user` mid-turn.

    Keyed on the response's CONTENT TYPE rather than its path, so a streaming
    route added later is covered without anyone remembering to list it.

    Compresses with `zlib` directly and touches NOTHING private. The first
    version wrapped Starlette's `GZipResponder` and reached for
    `.send_with_gzip`, an internal that `requirements.txt`'s own declared range
    (`fastapi>=0.101,<1`) is wide enough to resolve away: on Starlette 0.50 the
    attribute is gone and EVERY api request raises AttributeError. CI never saw
    it because `constraints.txt` pins the pair, and `Start Sonder.bat` installs
    `requirements.txt` without those constraints -- so the people who would hit
    it were exactly the ones running the launcher on a fresh machine.
    """

    STREAMED = ("application/x-ndjson", "text/event-stream")

    def __init__(self, app, minimum_size: int = 2048):
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if "gzip" not in Headers(scope=scope).get("accept-encoding", ""):
            return await self.app(scope, receive, send)
        await _SelectiveGZipResponder(
            self.app, self.minimum_size, self.STREAMED).run(scope, receive, send)


class _SelectiveGZipResponder:
    """One response's worth of the decision, held until it can be made.

    The content type arrives with `http.response.start` and the size only with
    the first body chunk, so both messages are held back until the answer is
    known -- which is at the latest the first chunk, never further. A streamed
    response is therefore delayed by exactly one message and no bytes are
    buffered beyond it.
    """

    def __init__(self, app, minimum_size, streamed):
        self.app = app
        self.minimum_size = minimum_size
        self.streamed = streamed
        self.send = None
        self.start = None
        self.compressor = None

    async def run(self, scope, receive, send):
        self.send = send
        await self.app(scope, receive, self.route)

    async def route(self, message):
        if message["type"] == "http.response.start":
            self.start = message
            return                                  # held: size still unknown
        if message["type"] != "http.response.body":
            return await self.send(message)

        body = message.get("body", b"")
        more = message.get("more_body", False)

        if self.start is not None:
            headers = Headers(raw=self.start["headers"])
            content_type = headers.get("content-type", "")
            already = headers.get("content-encoding", "")
            small = not more and len(body) < self.minimum_size
            if (already or small
                    or any(kind in content_type for kind in self.streamed)):
                start, self.start = self.start, None
                await self.send(start)
                return await self.send(message)
            self.compressor = zlib.compressobj(
                9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
            await self.send(self._gzip_start(self.start))
            self.start = None

        if self.compressor is None:                 # decided plain earlier
            return await self.send(message)

        # Z_SYNC_FLUSH per chunk: the compressor is allowed to hold bytes back
        # otherwise, which is the exact mechanism that stalled the turn stream.
        # Costs a little ratio on a multi-chunk response and guarantees that
        # what the app wrote is on the wire.
        chunk = self.compressor.compress(body)
        chunk += (self.compressor.flush(zlib.Z_SYNC_FLUSH) if more
                  else self.compressor.flush())
        await self.send({"type": "http.response.body", "body": chunk,
                         "more_body": more})

    @staticmethod
    def _gzip_start(message):
        """Re-headered start: encoded, varying, and of unknown length.

        `content-length` MUST go -- it describes the uncompressed body, and
        leaving it makes the client wait for bytes that will never come.
        """
        headers = [
            (key, value) for key, value in message["headers"]
            if key.lower() not in (b"content-length", b"content-encoding")
        ]
        headers.append((b"content-encoding", b"gzip"))
        if not any(key.lower() == b"vary" for key, _v in headers):
            headers.append((b"vary", b"Accept-Encoding"))
        return {**message, "headers": headers}


app.add_middleware(SelectiveGZipMiddleware, minimum_size=2048)
app.include_router(auth_router)

# The voice anchor rides EVERY narrator call, so it is bounded on both axes:
# a handful of short passages is a calibration, and a dozen long ones is a
# permanent tax on every turn of every story. The architecture asks for 3-5.
EXEMPLAR_MAX_COUNT = 5
EXEMPLAR_MAX_CHARS = 2000


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
            # The other half of the stale-snapshot instrumentation. This runs on
            # the PIPELINE thread, after the generator (commit included) is
            # exhausted and before the response can close -- so this is the
            # data_version the client's very next read must be at or above.
            try:
                from core.db import data_version as _dv_fn
                _pipeline_logger.info(
                    "turn_committed data_version=%s thread=%s",
                    _dv_fn(), threading.get_ident())
            except Exception:
                pass
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
        # Batched drain: one blocking get(), then everything already queued.
        # Starlette drives this sync generator through iterate_in_threadpool,
        # which pays a threadpool dispatch AND a fresh contextvars copy for
        # every yielded item -- per TOKEN, when yielded one at a time. During
        # generation the producer runs well ahead of the ASGI consumer, so
        # draining the backlog into one yield hands the same NDJSON lines
        # (framing unchanged -- one JSON object per line) to one dispatch.
        # When the producer is slower than the consumer the inner loop finds
        # the queue empty and each event still goes out immediately, so
        # latency to first byte of any event is untouched.
        try:
            while True:
                evt = evt_queue.get()
                if evt is DONE:
                    return
                batch = [evt]
                while True:
                    try:
                        nxt = evt_queue.get_nowait()
                    except queue.Empty:
                        break
                    if nxt is DONE:
                        yield "".join(json.dumps(e) + "\n" for e in batch)
                        return
                    batch.append(nxt)
                yield "".join(json.dumps(e) + "\n" for e in batch)
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
    for c in q("SELECT COALESCE(cc.sheet,ch.sheet) AS sheet FROM chat_chars cc "
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
    for ev in blob.get("world_events") or []:
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
                "scheduled_events", "world_events", "room_registry",
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
                   char_idmap=None, persona_idmap=None,
                   world_id_remap=None, frame_idmap=None):
    frame_idmap = frame_idmap or {}
    remapped_memories = []
    for memory in blob.get("memories") or []:
        if char_idmap is not None:
            new_char_id = char_idmap.get(memory.get("char_id"))
            if new_char_id is None:
                continue
            memory["char_id"] = new_char_id
        memory["turn_id"] = turn_idmap.get(memory.get("turn_id"))
        memory["frame_id"] = frame_idmap.get(memory.get("frame_id"))
        remapped_memories.append(memory)
    if "memories" in blob:
        blob["memories"] = remapped_memories

    if char_idmap is not None and "memory_summaries" in blob:
        blob["memory_summaries"] = [
            {**summary, "char_id": char_idmap[summary["char_id"]]}
            for summary in (blob.get("memory_summaries") or [])
            if char_idmap.get(summary.get("char_id")) is not None
        ]

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

    if char_idmap is not None and blob.get("chars"):
        remapped_chars = {}
        for old_key, state in blob["chars"].items():
            try:
                old_id = int(old_key)
                new_id = char_idmap.get(old_id)
                if new_id is None:
                    continue
                new_key = str(new_id)
            except (ValueError, TypeError):
                continue
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
            if char_idmap is not None:
                new_char_id = char_idmap.get(ncf.get("char_id"))
                if new_char_id is None:
                    continue
                ncf["char_id"] = new_char_id
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
            if char_idmap is not None:
                nfr["travelers"] = _remap_frame_character_ids(
                    nfr.get("travelers"), char_idmap)
                nfr["nonexistent_cast"] = _remap_frame_character_ids(
                    nfr.get("nonexistent_cast"), char_idmap)
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
            if persona_idmap is not None:
                new_persona_id = persona_idmap.get(np.get("persona_id"))
                if new_persona_id is None:
                    continue
                np["persona_id"] = new_persona_id
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

    # Objective events are frame facts and their turn is a local FK. Both
    # integer ids must follow branch/import remapping independently of the
    # string world-id pass below.
    for ev in blob.get("world_events") or []:
        ev["turn_id"] = turn_idmap.get(ev.get("turn_id"))
        ev["frame_id"] = frame_idmap.get(ev.get("frame_id"))

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
                    "scheduled_events", "world_events", "room_registry",
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

def _json_id_list(value):
    """Return integer ids from a frame's JSON-list storage value."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result

def _remap_frame_character_ids(value, char_idmap):
    """Remap frame membership and serialize it for the TEXT columns.

    Missing characters are deliberately omitted. Carrying their raw source
    database ids can attach a traveler/nonexistent mask to an unrelated local
    character whose row happens to reuse that integer id.
    """
    return json.dumps([
        char_idmap[old_id]
        for old_id in _json_id_list(value)
        if old_id in char_idmap
    ])
    
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
def _bootstrap_language():
    """The UI pack to serve, and every pack worth offering.

    Deliberately non-fatal. A malformed pack dropped into `language_packs/`
    makes `installed_language_packs` raise, and this route is the whole
    application's entry point -- so one bad directory took down the entire UI
    rather than just the language picker. English is compiled into the
    distribution, so there is always something to render with.
    """
    try:
        return (require_language_pack(ui_language(), capability="ui"),
                [pack.public()
                 for pack in installed_language_packs().values()],
                None)
    except LanguagePackError as exc:
        english = _english_language_pack()
        return english, ([english.public()] if english else []), str(exc)


def _english_language_pack():
    try:
        return require_language_pack(DEFAULT_LANGUAGE, capability="ui")
    except LanguagePackError:
        return None


def _bootstrap_extensions():
    """Installed extensions, never fatally. Same posture as _bootstrap_language:
    a broken extension costs the host that extension, not the whole UI."""
    try:
        return (extension_runtime.listing(), extension_runtime.load_errors(),
                extension_runtime.registered_model_lanes())
    except Exception as exc:
        logging.getLogger("fiction_engine.pipeline").exception(
            "extension listing failed")
        return [], [{"dir": "", "error": str(exc)}], []


@app.get("/api/bootstrap")
def bootstrap():
    selected_ui, language_packs, language_error = _bootstrap_language()
    extensions, extension_errors, extension_lanes = _bootstrap_extensions()
    return {
        "providers": [_provider_public(r["id"]) for r in q("SELECT id FROM providers")],
        "provider_presets": DEFAULT_BASES,
        "roles": ROLES,
        # Which role an UNSET role actually inherits. Empty today -- every
        # blank row follows `default`, so the panel's label is true on every
        # row without an exception to teach. It is still published rather
        # than assumed away: the panel renders "follow <parent>" from this
        # map, so a future role that needs a non-default parent is one entry
        # in `providers.ROLE_FALLBACKS` and the label follows, instead of the
        # client carrying a second copy of the rule that can drift from it.
        "role_fallbacks": dict(ROLE_FALLBACKS),
        "sampler_keys": list(SAMPLER_KEYS),
        "default_samplers": DEFAULT_SAMPLERS,
        "lore_categories": LORE_CATEGORIES,
        "lorebook_types": LOREBOOK_TYPES,
        "memory_categories": MEMORY_CATEGORIES,
        "memory_provenance": MEMORY_PROVENANCE,
        "agent_models": json.loads(get_setting("agent_models") or "{}"),
        # The narrator's voice anchor. Read by agents/narration.py and named in
        # the narrator prompt's STYLE EXEMPLARS clause since that prompt was
        # written -- and until now there was no way to put anything in it, so
        # every install has run with the clause referring to an empty list.
        "exemplars": json.loads(get_setting("exemplars") or "[]"),
        "max_output_tokens": max_output_tokens(),
        "reasoning_effort": reasoning_efforts(),
        "reasoning_effort_levels": list(REASONING_EFFORTS),
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
        # What a card authors under each clothing region (attire.describe's
        # `beneath`). Off unless asked for: exposure itself is objective and
        # always reported, but spelling out the body under the garment is a
        # choice the host makes rather than one a first run makes for them.
        "attire_beneath": get_setting("attire_beneath") == "1",
        # Whether the Director's specialists run at once. Parallel is the
        # default and the point; sequential is for a provider that cannot
        # take concurrent requests (see director.fanout_is_parallel).
        "director_fanout_parallel": director_fanout_is_parallel(),
        # Affect habituation (design note 22). Default OFF, and otherwise
        # reachable only by editing the database -- a switch a host cannot
        # find is a switch that becomes folklore, and this one was live in a
        # real story with no visible off.
        "affect_habituation": str(
            get_setting("affect_habituation") or "").strip().lower()
        in ("1", "on", "true"),
        # Scene backdrops (backdrops.py). Off unless switched on: every new
        # room costs a real image generation, so this is opt-in per install
        # rather than something a first run starts spending money on.
        "image_model": image_model(),
        "backdrops_enabled": get_setting("backdrops_enabled") == "1",
        # Image-to-image continuity (backdrops._continuity_enabled). Explicitly
        # off until asked for: it changes how every picture after a room's
        # first one is made.
        "backdrop_continuity": get_setting("backdrop_continuity") == "1",
        # Room ambience (ambience.py). Off unless switched on, like backdrops --
        # but the reason is different: audio that starts itself on a first run
        # is a worse surprise than a picture, and a browser would block it
        # anyway until the reader has clicked something. The API key is never
        # sent back, only whether one is set.
        "ambience": {k: v for k, v in ambience_settings().items() if k != "key"},
        "ambience_licenses": list(FREESOUND_LICENCES),
        "auto_promote": get_setting("auto_promote") != "0",
        "default_prompts": DEFAULT_PROMPTS,
        "prompt_presets": presets(),
        "active_preset": active_preset(),
        "lorebook_link_types": LOREBOOK_LINK_TYPES,
        "language_packs": language_packs,
        "ui_language": selected_ui.id if selected_ui else DEFAULT_LANGUAGE,
        "ui_direction": selected_ui.direction if selected_ui else "ltr",
        "ui_messages": dict(selected_ui.ui_catalog) if selected_ui else {},
        # Surfaced rather than swallowed: the host needs to know a pack they
        # installed is not being used, and why.
        "language_error": language_error,
        # Installed extensions, and every directory that failed to load --
        # surfaced for exactly the reason `language_error` is. Both are
        # deliberately non-fatal: a malformed extension must cost the host its
        # own row in the panel, never the application's entry point.
        "extensions": extensions,
        "extension_errors": extension_errors,
        # Enabled extensions' declared model lanes ({ext_id, name, role,
        # label, description}), rendered by the models panel as rows of their
        # own beneath the host roles. NOT part of `roles`: that list is the
        # host's fixed vocabulary, and the panel needs to know which rows are
        # an extension's to label them as such. Empty with nothing installed.
        "extension_lanes": extension_lanes,
    }

@app.put("/api/agent_models")
def put_agent_models(body: dict = Body(...)):
    # Only the EMBEDDINGS role bears on stored vectors. Changing the narrator
    # or director model has nothing to do with them, so comparing before and
    # after keeps this from becoming a nag on every settings write.
    _stored = json.loads(get_setting("agent_models") or "{}") or {}
    _before = _stored.get("embeddings") or {}
    # The panel PUTs the whole map, built from the rows it rendered -- which
    # is how clearing a row works, and which would also delete the stored
    # configuration of any extension lane whose extension is disabled or
    # removed (those rows are not rendered). That configuration is the host's
    # work, so it rides through the save; a LIVE lane omitted from the body
    # was genuinely cleared and stays dropped.
    body = extension_runtime.keep_orphan_lane_rows(_stored, body)
    set_setting("agent_models", json.dumps(body))
    _after = (body or {}).get("embeddings") or {}
    changed = ((_before.get("provider"), _before.get("model"))
               != (_after.get("provider"), _after.get("model")))
    out = {"ok": True, "embeddings_role_changed": changed}
    if changed:
        # Not started here -- the host is told, and decides. A rebuild talks
        # to a paid provider and can run for a while on a large bank; doing
        # that silently because someone opened a settings panel is the wrong
        # default. `embeddings_role_changed` is what the UI prompts on.
        try:
            out["bank"] = embedding_bank_status()
        except Exception as exc:
            out["bank"] = {"error": str(exc)}
    return out


@app.get("/api/memory/embeddings")
def memory_embeddings_status():
    """What the embedding bank looks like, and whether a rebuild is running.

    Polled by the corner progress card; cheap enough to poll (two COUNTs plus
    an in-memory snapshot) and safe to call at any time.
    """
    out = {"progress": rebuild_progress()}
    try:
        out.update(embedding_bank_status())
    except Exception as exc:
        out["error"] = str(exc)
    return out


@app.post("/api/memory/embeddings/rebuild")
def memory_embeddings_rebuild(body: dict = Body(default={})):
    """Start the reconciler by hand.

    `force` rebuilds even when the live model is the crc32 fallback, which is
    a DOWNGRADE of any real vectors already stored -- so it is never the
    automatic behaviour and has to be asked for.
    """
    body = body or {}
    return start_rebuild_if_needed(
        chat_id=body.get("chat_id"), force=bool(body.get("force")))

@app.put("/api/image_model")
def put_image_model(body: dict = Body(...)):
    """The image generator used for scene backdrops.

    Its own setting rather than an `agent_models` role because image
    generation is a different API surface -- see providers.image_model().
    Sending no provider/model clears it, which switches backdrops off at the
    source without touching the enabled flag.
    """
    pid, model = body.get("provider"), str(body.get("model") or "").strip()
    if not pid or not model:
        set_setting("image_model", "")
        return {"ok": True, "image_model": None}
    if not provider(int(pid)):
        raise HTTPException(404, "Provider not found")
    cfg = {"provider": int(pid), "model": model}
    size = str(body.get("size") or "").strip()
    if size:
        cfg["size"] = size
    set_setting("image_model", json.dumps(cfg))
    return {"ok": True, "image_model": cfg}

@app.put("/api/exemplars")
def put_exemplars(body: dict = Body(...)):
    """The narrator's voice anchor: a few short passages at the target quality.

    THE SLOT EXISTED AND HAD NO DOOR. `agents/narration.py` has always read
    `settings.exemplars`, and the narrator prompt has always carried a STYLE
    EXEMPLARS clause telling the model to study them for voice, rhythm and
    restraint -- but nothing anywhere could write the setting, so the clause
    referred to an empty list on every install that has ever run.

    Passages are STYLE, never content: the prompt already says so, and the
    reason it must is that an exemplar is the one thing in the payload the
    narrator is told to imitate. A passage naming this story's people would
    be read as this story's facts.
    """
    passages = body.get("exemplars")
    if not isinstance(passages, list):
        raise HTTPException(400, "exemplars must be a list of passages")
    clean = []
    for passage in passages[:EXEMPLAR_MAX_COUNT]:
        text = str(passage or "").strip()
        if not text:
            continue
        # Bounded per passage, because this rides EVERY narrator call. Three
        # long passages are a permanent tax on every turn of every story.
        clean.append(text[:EXEMPLAR_MAX_CHARS])
    set_setting("exemplars", json.dumps(clean, ensure_ascii=False))
    return {"exemplars": clean, "count": len(clean),
            "max_count": EXEMPLAR_MAX_COUNT, "max_chars": EXEMPLAR_MAX_CHARS}


@app.put("/api/backdrops")
def put_backdrops(body: dict = Body(...)):
    enabled = bool(body.get("enabled"))
    set_setting("backdrops_enabled", "1" if enabled else "0")
    # Absent means unchanged, so the toolbar toggle can send {enabled} alone.
    if "continuity" in body:
        set_setting("backdrop_continuity", "1" if body.get("continuity") else "0")
    return {"enabled": enabled,
            "continuity": get_setting("backdrop_continuity") == "1"}

@app.put("/api/ambience")
def put_ambience(body: dict = Body(...)):
    """Room-ambience configuration: on/off, which source, and its credentials.

    Every field is optional so the toolbar toggle can send `{enabled}` alone
    without clearing the library path or the API key -- the same "absent means
    unchanged" contract the provider routes use for keys.
    """
    if "enabled" in body:
        set_setting("ambience_enabled", "1" if body.get("enabled") else "0")
    if "source" in body:
        source = str(body.get("source") or "").strip()
        if source not in ("local", "freesound"):
            raise HTTPException(400, "source must be 'local' or 'freesound'")
        set_setting("ambience_source", source)
    if "library" in body:
        set_setting("ambience_library", str(body.get("library") or "").strip())
    # An empty key means "leave it alone", never "delete it": the UI cannot
    # show the stored value back, so a blank field is the normal state of an
    # already-configured install. Clearing is explicit.
    if body.get("freesound_key"):
        set_setting("freesound_key", str(body["freesound_key"]).strip())
    if body.get("clear_key"):
        set_setting("freesound_key", "")
    if "licenses" in body:
        picked = [lic for lic in (body.get("licenses") or [])
                  if lic in FREESOUND_LICENCES]
        set_setting("ambience_licenses", json.dumps(picked))
    return {k: v for k, v in ambience_settings().items() if k != "key"}

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

@app.put("/api/reasoning_effort")
def put_reasoning_effort(body: dict = Body(...)):
    """PER-ROLE reasoning effort, {role: level}. A role set to 'off' disables
    reasoning; 'minimal'/'low'/'medium'/'high' set the level; anything else (or
    absent) is unset -> model default, with a role falling back to the 'default'
    role. Coerced rather than rejected -- it rides on every request, so a bad
    value must degrade to unset, not break generation. Accepts either the full
    map, or a single {role, value} to update one role."""
    if "role" in body and "value" in body:  # single-role update
        current = reasoning_efforts()
        lvl = _coerce_reasoning_effort(body.get("value"))
        if lvl:
            current[str(body["role"])] = lvl
        else:
            current.pop(str(body["role"]), None)
        cleaned = current
    else:  # full map
        cleaned = {}
        for role, level in (body.get("efforts") or body).items():
            lvl = _coerce_reasoning_effort(level)
            if lvl:
                cleaned[str(role)] = lvl
        # Same carry-through as `put_agent_models`: the panel's full map only
        # names the roles it rendered, and a disabled extension's lane is not
        # among them -- its stored effort is the host's choice and survives.
        cleaned = extension_runtime.keep_orphan_lane_rows(
            reasoning_efforts(), cleaned)
    set_setting("reasoning_effort", json.dumps(cleaned))
    return {"ok": True, "reasoning_effort": cleaned}

@app.put("/api/max_output_tokens")
def put_max_output_tokens(body: dict = Body(...)):
    """The per-call output-token ceiling every LLM request is clamped to.
    Coerced into range rather than rejected -- this value gates every call, so
    a bad one must degrade to a usable number, not break generation."""
    value = _coerce_max_output_tokens(body.get("value"))
    set_setting("max_output_tokens", str(value))
    return {"ok": True, "value": value}

def _default_authoring_language():
    """The language to author in when the request does not say.

    Characters, personas and lorebooks are global resources, so there is no
    story whose language could be read. Defaulting to English meant a host who
    had switched everything to Japanese still got English cards, because the
    only thing that carried their choice was whichever frontend remembered to
    send it. The interface language is the setting they actually changed.
    """
    try:
        return require_language_pack(ui_language(), capability="story").id
    except (LanguagePackError, ImportError):
        return DEFAULT_LANGUAGE


def _require_story_language(value):
    """Resolve a request's story language, or refuse the request."""
    try:
        return require_language_pack(
            value or _default_authoring_language(), capability="story").id
    except (LanguagePackError, ImportError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/default_prompts")
def default_prompts(language: str = DEFAULT_LANGUAGE):
    """One story language's editable prompt bodies, for the prompt editor.

    Bootstrap ships the English set; a host editing a Japanese preset needs
    the Japanese sheets to edit, not English ones to overwrite them with.
    """
    selected = _require_story_language(language)
    return {"language": selected, "prompts": default_prompts_for(selected)}


@app.put("/api/prompt_presets")
def save_preset(body: dict = Body(...)):
    name = str(body.get("name") or "").strip()
    if not name or name == "Default":
        raise HTTPException(400, "a preset needs a name of its own")
    language = _require_story_language(body.get("language"))
    supplied = body.get("prompts") or {}
    if not isinstance(supplied, dict):
        raise HTTPException(400, "prompts must be an object")
    ps = presets()
    ps[name] = {
        "language": language,
        "prompts": {str(pid): str(text) for pid, text in supplied.items()
                    if isinstance(text, str)},
    }
    set_setting("prompt_presets", json.dumps(ps))
    return {"ok": True, "name": name, "language": language}


@app.get("/api/prompt_presets/{name}/export")
def export_preset(name: str):
    try:
        document = preset_export_document(name)
    except KeyError as exc:
        raise HTTPException(404, f"No prompt preset named {name!r}.") from exc
    return document


@app.post("/api/prompt_presets/import")
def import_preset(body: dict = Body(...)):
    document = body.get("preset")
    try:
        name, preset = preset_import_document(document, body.get("name"))
    except (ValueError, LanguagePackError, ImportError) as exc:
        raise HTTPException(400, f"Preset import failed: {exc}") from exc
    ps = presets()
    final = unique_preset_name(name, ps)
    ps[final] = preset
    set_setting("prompt_presets", json.dumps(ps))
    return {"ok": True, "name": final, "language": preset["language"],
            "renamed": final != name}

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


# ---- Extensions ----
# Thin by design: everything here is a call into extension_runtime, so the
# loader's per-item isolation, containment checks and enable set live in one
# place instead of being re-implemented per route.

def _extension_id(eid: str) -> str:
    if not extension_runtime.EXTENSION_ID.fullmatch(str(eid or "")):
        raise HTTPException(404, "No such extension")
    return str(eid)


@app.get("/api/extensions")
def extensions_list():
    return {"extensions": extension_runtime.listing(),
            "load_errors": extension_runtime.load_errors(),
            "safe_mode": extension_runtime.safe_mode()}


@app.post("/api/extensions/{eid}/enable")
def extension_enable(eid: str):
    try:
        return extension_runtime.enable_extension(_extension_id(eid))
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/extensions/install")
def extension_install(body: dict = Body(...)):
    """Install from a local directory or an http(s) URL.

    Phase 1: nothing reviews what arrives, and the consent for that is taken in
    the browser before this is called. What this route owes the host is that a
    malformed or hostile ARCHIVE cannot damage the install — see
    `extension_runtime.install_extension`, which stages, validates and then
    moves atomically.
    """
    source = str(body.get("source") or "").strip()
    if not source:
        raise HTTPException(400, "source is required")
    try:
        return {"extension": extension_runtime.install_extension(source)}
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Install failed: {exc}") from exc


@app.get("/api/extensions/updates")
def extension_updates():
    """Ask every git-sourced extension's remote whether it has moved.

    One `ls-remote` each, no download. Never raises: an unreachable remote is
    reported on its own row so one dead repository cannot fail the sweep for
    everything else installed.
    """
    return {"updates": extension_runtime.check_updates()}


@app.post("/api/extensions/{eid}/update")
def extension_update(eid: str):
    try:
        return extension_runtime.update_extension(_extension_id(eid))
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Update failed: {exc}") from exc


@app.delete("/api/extensions/{eid}")
def extension_remove(eid: str):
    try:
        return extension_runtime.remove_extension(_extension_id(eid))
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/extensions/{eid}/disable")
def extension_disable(eid: str):
    return extension_runtime.disable_extension(_extension_id(eid))


@app.get("/api/extensions/{eid}/state")
def extension_state(eid: str, chat_id: int):
    return {"id": _extension_id(eid),
            "chat_id": chat_id,
            "state": wget(chat_id, f"ext:{_extension_id(eid)}")}


def _extension_documents(eid: str, chat_id):
    """One extension's document store, scope chosen by the query.

    `chat_id` present is story scope (rides checkpoints/archives/branches
    with the rest of the `ext:<id>` namespace); absent is install scope
    (the settings table, outside story history, like `api.settings`).
    Paths and prefixes travel as QUERY parameters rather than URL path
    segments, so a document may be named `verify` or `state` without
    shadowing anything and a prefix may be empty without a route ambiguity.
    """
    return extension_runtime.DocumentStore(_extension_id(eid), chat_id)


@app.get("/api/extensions/{eid}/documents")
def extension_documents_list(eid: str, chat_id: int | None = None,
                             prefix: str = ""):
    try:
        store = _extension_documents(eid, chat_id)
        return {"id": _extension_id(eid), "chat_id": chat_id,
                "documents": store.list(prefix)}
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/extensions/{eid}/documents/verify")
def extension_documents_verify(eid: str, chat_id: int | None = None,
                               prefix: str = ""):
    """The storage-integrity read: damage is rows in the report, never a 500."""
    try:
        return _extension_documents(eid, chat_id).verify(prefix)
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/extensions/{eid}/document")
def extension_document_get(eid: str, path: str, chat_id: int | None = None):
    try:
        store = _extension_documents(eid, chat_id)
        meta = store.stat(path)
        if meta is None:
            raise HTTPException(404, f"No document at {path!r}")
        return {"path": meta["path"], "doc": store.get(path), "meta": meta}
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/api/extensions/{eid}/document")
def extension_document_put(eid: str, path: str, body: dict = Body(...),
                           chat_id: int | None = None):
    """Store one document. The body is `{"doc": <any JSON value>}` -- an
    envelope rather than the raw value, because a bare list or scalar body
    would be indistinguishable from a malformed request.

    Written with `put_now`: a route call is a host action outside any turn,
    with no transaction to be rolled back with -- the same reasoning that
    leaves `NarrationBlock` writes ungated.
    """
    if "doc" not in body:
        raise HTTPException(400, 'body must be {"doc": <value>}')
    try:
        store = _extension_documents(eid, chat_id)
        return store.put_now(path, body["doc"])
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/extensions/{eid}/document")
def extension_document_delete(eid: str, path: str,
                              chat_id: int | None = None):
    try:
        store = _extension_documents(eid, chat_id)
        return {"deleted": store.delete_now(path)}
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/extensions/{eid}/documents")
def extension_documents_delete(eid: str, prefix: str,
                               chat_id: int | None = None):
    """Delete a whole prefix. `prefix` is REQUIRED so that a caller who
    forgot the parameter gets a 422, not an empty prefix silently matching
    the entire store; passing `prefix=` explicitly does mean everything."""
    try:
        store = _extension_documents(eid, chat_id)
        return {"deleted": store.delete_prefix_now(prefix)}
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/extensions/ui.js")
def extensions_ui():
    # Served under /api/ rather than /static/ so `access_control` gates it:
    # extension code stays behind the host session and never reaches the guest
    # page, which loads its own shell.
    return Response(extension_runtime.ui_bundle(),
                    media_type="application/javascript")


@app.get("/api/extensions/ui.css")
def extensions_ui_css():
    """Every enabled extension's stylesheet, as a document.

    A document rather than a `<style>` the bundle writes, so a theme is in
    effect before first paint instead of flashing the host's colours first.
    """
    return Response(extension_runtime.ui_styles(), media_type="text/css")


@app.get("/api/extensions/{eid}/ui.js")
def extension_ui_one(eid: str):
    """One extension's script, so the browser can load it AFTER page load.

    This is what makes enable hot rather than reload-only: the page-load bundle
    is a `<script>` tag and a script tag loads once, so enabling an extension
    the page was served without needs its code fetched separately.
    """
    return Response(extension_runtime.extension_script(_extension_id(eid)),
                    media_type="application/javascript")


@app.get("/api/extensions/{eid}/ui.css")
def extension_ui_css_one(eid: str):
    return Response(extension_runtime.extension_styles(_extension_id(eid)),
                    media_type="text/css")


@app.api_route("/api/extensions/{eid}/x/{path:path}",
               methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def extension_route(eid: str, path: str, request: Request):
    """Dispatch to a route an extension registered with `api.add_route`.

    Namespaced under `/x/` so an extension can never shadow a host route in its
    own namespace, whatever it names its path. The extension receives the
    engine's own `Request` shim, never Starlette's — an extension that bound to
    the framework's types would inherit every future upgrade of them.
    """
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = None
    try:
        result = extension_runtime.dispatch_route(
            _extension_id(eid), request.method, path,
            query=dict(request.query_params), body=body)
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Extension route failed: {exc}") from exc
    return result if isinstance(result, (dict, list)) else {"result": result}


@app.get("/api/extensions/{eid}/asset/{path:path}")
def extension_asset(eid: str, path: str):
    try:
        target = extension_runtime.asset_path(_extension_id(eid), path)
    except extension_runtime.ExtensionError as exc:
        raise HTTPException(404, str(exc)) from exc
    # A module entry and everything it imports are fetched through here, and a
    # browser REFUSES a module served as anything but a JavaScript MIME type --
    # `.mjs` in particular is guessed as `application/octet-stream` on hosts
    # whose mimetypes database predates it, which fails the import with a
    # message about the type rather than about the file.
    if target.suffix in (".js", ".mjs"):
        return FileResponse(str(target), media_type="application/javascript")
    return FileResponse(str(target))

@app.get("/api/nsfw")
def get_nsfw():
    return {"enabled": get_setting("nsfw_enabled") == "1"}

@app.put("/api/nsfw")
def set_nsfw(body: dict = Body(...)):
    set_setting("nsfw_enabled", "1" if body.get("enabled") else "0")
    return {"enabled": body.get("enabled", False)}

@app.put("/api/director_fanout_mode")
def set_director_fanout_mode(body: dict = Body(...)):
    """Whether the Director's specialists run at once or in turn.

    The fan-out itself is not optional and has no switch: each Director
    stage keeps ONE step and works inside it as a prose author that owns
    the beat's account plus specialists that own the state_diff channels
    the beat actually touches. That is the only path.

    What IS a choice is concurrency, because concurrency is not free
    everywhere -- a provider key that takes one request at a time, a limit
    measured in connections, a local runtime serving one model on one GPU.
    Sequential is not a fallback to the old monolithic sheet: the same
    specialists run with the same scopes and assemble in the same canonical
    order, and a beat dispatches a mean 1.75 of 6 hands carrying 1-4k
    sheets rather than one ~21k sheet. It is expected to beat the monolith
    on its own; parallel beats it by more.
    """
    parallel = bool(body.get("parallel", True))
    set_setting("director_fanout_mode",
                "parallel" if parallel else "sequential")
    return {"parallel": parallel}


@app.put("/api/affect_habituation")
def set_affect_habituation(body: dict = Body(...)):
    """Whether a held emotional peak wears off (design note 22).

    Off is the default and off is the shipped behaviour. On, sustained
    maximum feeling costs sensitivity, so a plateau sags and a genuine peak
    has somewhere to land -- measured on a live story, a character sat at
    0.99 valence for seventeen turns and her climax scored LOWER than the
    plateau it was meant to crown.

    Sensitivity accumulates from zero, so switching it on mid-story takes
    several beats to show and does not reach back over the plateau that
    prompted it.
    """
    enabled = bool(body.get("enabled"))
    set_setting("affect_habituation", "1" if enabled else "0")
    return {"enabled": enabled}


@app.put("/api/attire_beneath")
def set_attire_beneath(body: dict = Body(...)):
    """Whether a card's per-region `beneath` text is used at all.

    Turning it off does not erase what a card authored; it stops that text
    being put into any prompt. Regions still report themselves as bare, which
    is objective and belongs to the story either way.
    """
    enabled = bool(body.get("enabled"))
    set_setting("attire_beneath", "1" if enabled else "0")
    return {"enabled": enabled}

# ---- Self-update (host-only via the access-control middleware) ----
# Sync defs so FastAPI runs the blocking git/network work in its threadpool
# rather than on the event loop, matching every other route here.
@app.get("/api/updates/check")
def updates_check():
    return updates.check_updates()

@app.post("/api/updates/install")
def updates_install():
    return updates.install_updates()

@app.get("/api/maintenance/checkpoints")
def maintenance_checkpoints():
    """How much of the checkpoint store is still in the legacy inline-vector
    format, plus any conversion in flight.

    Lives beside the update routes because that is where a host looks after
    pulling a version whose storage format changed. Safe to poll: the status
    scan is sizes plus a one-entry probe per blob, not a full parse.
    """
    out = {"progress": compaction_progress()}
    try:
        out.update(checkpoint_storage_status())
    except Exception as exc:
        out["error"] = str(exc)
    return out

@app.post("/api/maintenance/checkpoints/compact")
def maintenance_compact(body: dict = Body(default={})):
    """Convert legacy checkpoints to the content-addressed format.

    Rewrites rollback history, so it is never automatic -- a host asks for it.
    Nothing is re-embedded and nothing is deleted: each vector moves into
    `memory_vectors` under its content address and the checkpoint keeps a
    reference. Resumable; already-converted checkpoints are skipped.
    """
    body = body or {}
    cid = body.get("chat_id")
    return start_compaction(int(cid) if cid else None)

# ============================ LOREBOOK TREE & LINKS ============================
from mind.memory import (
    move_lorebook, reorder_lorebook,
    add_lorebook_link, update_lorebook_link, delete_lorebook_link,
    get_lorebook_links, restore_lorebook_links,
    LOREBOOK_LINK_TYPES,
)
from world.survival import (survival_enabled, set_survival_enabled, seed_vitals,
                      survival_shows_npcs, set_survival_shows_npcs)
from story.importers import (
    generate_lorebook_plan, apply_lorebook_plan, resume_lorebook_plan,
    recoverable_lore_gen_job, lore_gen_job, cancel_lore_gen_job,
    mark_lore_gen_job_applied, LoreGenError,
)

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

@app.get("/api/chats/{cid}/lorebooks")
def chat_lorebooks_owned(cid: int):
    """Every lorebook this chat OWNS, plus the library books attached to it.

    Deliberately not `chat_lorebook_ids()`. That answers the retrieval
    question -- "which books may this chat draw lore from" -- by resolving
    outward from canon plus attachments through parents, children and links.
    A book the chat owns that hangs off nothing (parent_id NULL and no
    chat_lorebooks row) is unreachable by that walk, so the browser built on
    it could not show the book at all: a story whose canon had no children
    rendered as a single book, with its vehicle/location books missing
    entirely. Ownership is the right question for an editor, and unlike
    reachability it cannot orphan anything.

    `retrievable` reports the other question honestly per book, because a book
    that is visible here but unreachable is a book the pipeline will never
    draw lore from -- worth seeing rather than guessing at.
    """
    chat = q("SELECT id, lorebook_id FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")

    canon = chat["lorebook_id"]
    attachments = {
        r["lorebook_id"]: bool(r["enabled"])
        for r in q(
            "SELECT lorebook_id, enabled FROM chat_lorebooks WHERE chat_id=?",
            (cid,),
        )
    }
    retrievable = set(chat_lorebook_ids(cid, enabled_only=False))

    rows = q(
        "SELECT lb.*, ("
        " SELECT COUNT(*) FROM lore_entries le WHERE le.lorebook_id = lb.id"
        ") AS entry_count "
        "FROM lorebooks lb "
        "WHERE lb.chat_id = ? "
        "   OR lb.id IN (SELECT lorebook_id FROM chat_lorebooks WHERE chat_id = ?) "
        "   OR lb.id = ? "
        "ORDER BY lb.parent_id IS NULL DESC, lb.sort_order, lb.id",
        (cid, cid, canon),
    )

    books = []
    for lb in rows:
        book = dict(lb)
        book["canon"] = lb["id"] == canon
        book["attached"] = lb["id"] in attachments
        book["enabled"] = attachments.get(lb["id"], True)
        book["retrievable"] = lb["id"] in retrievable
        books.append(book)

    return {"lorebooks": books}

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
    update_lorebook_link(
        link_id,
        relation_type=body.get("relation_type"),
        label=body.get("label"),
        notes=body.get("notes"),
        bidirectional=body.get("bidirectional"),
        follow_for_retrieval=body.get("follow_for_retrieval"),
        weight=body.get("weight"),
        sort_order=body.get("sort_order"),
    )
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
        with language_scope(_require_story_language(body.get("language"))):
            plan = generate_lorebook_plan(
                lid, brief,
                mode=body.get("mode", "expand_tree"),
                depth=body.get("depth", 2),
                entry_target=body.get("entry_target", 40),
                allow_new_books=body.get("allow_new_books", True),
                allow_links=body.get("allow_links", True),
                allow_updates=body.get("allow_updates", True),
                preserve_locked=body.get("preserve_locked", True),
                timeout=body.get("timeout"),
            )
    except LoreGenError as exc:
        # The run produced nothing usable, but its job row survives with the
        # request and any completed stage, so point the client at the resume
        # instead of just reporting a dead end.
        raise HTTPException(502, f"Lore generation failed: {exc} (resumable)") from exc
    except Exception as exc:
        raise HTTPException(502, f"Lore generation failed: {exc}") from exc
    return plan

@app.get("/api/lorebooks/{lid}/generate_job")
def lorebook_generate_job(lid: int):
    """The newest generation run for this book that is still recoverable.

    This is the channel that survives a closed tab or a restarted server: the
    plan lives in the job row, not in the browser, so reopening the generator
    can offer to resume or restore it.
    """
    _require_lorebook(lid)
    return {"job": recoverable_lore_gen_job(lid)}

@app.post("/api/lore_gen_jobs/{job_id}/resume")
def lorebook_generate_resume(job_id: int, body: dict = Body(default={})):
    job = lore_gen_job(job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    _require_lorebook(job["lorebook_id"])
    try:
        # A read timeout is one of the interruptions being recovered from, so
        # the retry may be given longer than the attempt that ran out of it.
        plan = resume_lorebook_plan(job_id, timeout=body.get("timeout"))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except LoreGenError as exc:
        raise HTTPException(502, f"Lore generation failed: {exc} (resumable)") from exc
    except Exception as exc:
        raise HTTPException(502, f"Lore generation failed: {exc}") from exc
    return plan

@app.delete("/api/lore_gen_jobs/{job_id}")
def lorebook_generate_discard(job_id: int):
    job = lore_gen_job(job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    _require_lorebook(job["lorebook_id"])
    cancel_lore_gen_job(job_id)
    return {"ok": True}

@app.post("/api/lorebooks/{lid}/apply_plan")
def lorebook_apply_plan(lid: int, body: dict = Body(...)):
    _require_lorebook(lid)
    plan = body.get("plan")
    if not plan:
        raise HTTPException(400, "plan is required")

    # Ensure book ops are scoped to this lorebook's chat
    book = q("SELECT chat_id FROM lorebooks WHERE id=?", (lid,), one=True)
    chat_id = book["chat_id"] if book else None

    # root_id: books/entries whose own reference does not resolve land under
    # the book this plan was generated for, rather than becoming unreachable
    # orphans (or being dropped).
    result = apply_lorebook_plan(plan, chat_id=chat_id, root_id=lid)

    # An applied plan is no longer recoverable work -- retire its job so the
    # generator does not offer to resume a run whose entries are now real lore.
    job_id = body.get("job_id")
    if job_id:
        try:
            mark_lore_gen_job_applied(int(job_id))
        except (TypeError, ValueError):
            pass

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
    # Prompt caching, answered by the request path's own predicates rather than
    # re-derived in JS -- the rule is a three-way interaction (built-in kinds,
    # an allowlist, a deny list that wins) and two copies of it would drift.
    d["prompt_cache"] = providers.prompt_cache_enabled_for(row)
    d["prompt_cache_default"] = providers.prompt_cache_supported_for(row)
    d["prompt_cache_locked"] = not providers.PROMPT_CACHE_ENABLED
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

def _cache_list(key):
    """`prompt_cache_allow`/`_deny` as an ordered list of casefolded tokens."""
    raw = get_setting(key) or ""
    seen, out = set(), []
    for part in str(raw).split(","):
        tok = part.strip().casefold()
        if tok and tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out

@app.put("/api/providers/{pid}/prompt_cache")
def put_provider_prompt_cache(pid: int, body: dict = Body(...)):
    """Turn prompt caching on or off for one provider.

    The stored form is two comma-separated settings shared by every provider,
    so a per-provider switch has to edit them without disturbing anyone else.
    The case that needs care is a KIND-level deny ("nanogpt") covering several
    connections: enabling one of them by simply dropping that token would
    silently enable them all. It is expanded into per-provider denies instead,
    which preserves what every existing connection is set to. The cost is that
    a kind-level deny no longer covers connections created LATER -- a real
    tradeoff, taken because a switch that changes a provider you did not touch
    is the worse surprise.
    """
    row = q("SELECT * FROM providers WHERE id=?", (pid,), one=True)
    if not row:
        raise HTTPException(404, "Provider not found")
    enabled = bool(body.get("enabled"))
    name, kind = providers.cache_tokens(row)
    token = name or kind
    if not token:
        raise HTTPException(400, "Provider has neither a name nor a kind")

    deny, allow = _cache_list("prompt_cache_deny"), _cache_list("prompt_cache_allow")
    if enabled:
        if kind and kind in deny:
            # Only connections that have a name of their own can be denied
            # individually; a nameless one would fall back to its kind and
            # re-deny everybody, so it is left to follow this change.
            others = [providers.cache_tokens(r)[0]
                      for r in q("SELECT * FROM providers WHERE id<>?", (pid,))
                      if providers.cache_tokens(r)[1] == kind]
            deny = [t for t in deny if t != kind]
            deny += [t for t in others if t and t != token and t not in deny]
        deny = [t for t in deny if t != token]
        if not providers.prompt_cache_supported_for(row) and token not in allow:
            allow.append(token)
    elif token not in deny:
        # `allow` is left alone on purpose: deny wins over it, so pruning it
        # would only make re-enabling lose an opt-in the host typed by hand.
        deny.append(token)
    set_setting("prompt_cache_deny", ",".join(deny))
    set_setting("prompt_cache_allow", ",".join(allow))
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

@app.get("/api/providers/{pid}/image_models")
def image_models(pid: int):
    """Separate from /models because image generation is a separate catalogue
    on the one provider that publishes one -- see providers.list_image_models."""
    prov = provider(pid)
    if not prov: raise HTTPException(404)
    try: return {"models": list_image_models(prov)}
    except Exception as e: raise HTTPException(502, str(e))

# ============================ CHARACTERS ============================
@app.post("/api/characters/generate")
def char_generate(body: dict = Body(default={})):
    brief = str(body.get("prompt") or body.get("brief") or body.get("description") or "").strip()
    try:
        language = require_language_pack(
            body.get("language") or _default_authoring_language(),
            capability="story").id
    except LanguagePackError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        # Scoped, not merely passed: the provider boundary reads the
        # contextvar to apply the schema policy AND to size the output
        # budget. Passing `language` alone left both at English, which
        # stacked the English contract under the Japanese one and
        # truncated the sheet mid-JSON.
        with language_scope(language):
            cid, sheet = generate_character(brief, language=language)
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
    return {"id": cid, "sheet": sheet,
            "warnings": character_import_warnings(sheet)}

@app.post("/api/characters/{cid}/start")
def character_start_story(cid: int, body: dict = Body(default={})):
    """Start story now: seed a chat from this character's greeting with the
    chosen persona (greeting shown verbatim, private knowledge routed to the
    character). See greetings.start_story / docs/design/GREETING_IMPORT_DESIGN.md."""
    persona_id = body.get("persona_id")
    if persona_id is None:
        raise HTTPException(400, "persona_id required")
    lorebook_id = body.get("lorebook_id")
    try:
        chat_id, turn_id = greetings.start_story(
            cid, int(persona_id), int(body.get("greeting_index", 0)),
            lorebook_id=int(lorebook_id) if lorebook_id else None,
            already_known=bool(body.get("already_known", True)),
            language=_require_story_language(body.get("language")))
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

@app.post("/api/characters/{cid}/generate_greeting")
def char_generate_greeting(cid: int, body: dict = Body(default={})):
    """Generate one greeting in the character's voice from an optional situation
    brief. Returns the greeting entry WITHOUT persisting it -- the greeting
    editor adds it to the list and saves through the normal character-update
    path, exactly like a hand-added greeting."""
    if not q("SELECT 1 FROM characters WHERE id=?", (cid,), one=True):
        raise HTTPException(404, "Character not found")
    brief = str(body.get("prompt") or body.get("brief") or body.get("situation") or "")
    try:
        greeting = greetings.generate_greeting(
            cid, brief, language=_require_story_language(body.get("language")))
    except Exception as exc:
        raise HTTPException(502, f"Greeting generation failed: {exc}") from exc
    return {"greeting": greeting}

@app.post("/api/characters/{cid}/fill_psychology")
def char_fill_psychology(cid: int, body: dict = Body(default={})):
    """Preview missing v3 psychology fields for editor review."""
    brief = str(body.get("prompt") or body.get("brief") or "").strip()
    try:
        with language_scope(_require_story_language(body.get("language"))):
            sheet = fill_character_psychology(cid, brief)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Psychology fill failed: {exc}") from exc
    return {"id": cid, "sheet": sheet}

def _appearance_fill(kind, entity_id, body):
    """Shared handler for the two card editors' body-and-clothing generator."""
    try:
        with language_scope(_require_story_language(body.get("language"))):
            return fill_appearance(
                kind, entity_id,
                str(body.get("prompt") or body.get("brief") or "").strip(),
                include_beneath=bool(body.get("beneath")),
                draft=body.get("draft"),
            )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Appearance fill failed: {exc}") from exc

@app.post("/api/characters/{cid}/fill_appearance")
def char_fill_appearance(cid: int, body: dict = Body(default={})):
    """Preview a generated body and outfit for editor review. Writes nothing."""
    return {"id": cid, "sheet": _appearance_fill("character", cid, body)}

@app.post("/api/personas/{pid}/fill_appearance")
def persona_fill_appearance(pid: int, body: dict = Body(default={})):
    """Preview a generated body and outfit for editor review. Writes nothing."""
    return {"id": pid, "sheet": _appearance_fill("persona", pid, body)}

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
        language = require_language_pack(
            body.get("language") or _default_authoring_language(),
            capability="story").id
    except LanguagePackError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        # Scoped, not merely passed: the provider boundary reads the
        # contextvar to apply the schema policy AND to size the output
        # budget. Passing `language` alone left both at English, which
        # stacked the English contract under the Japanese one and
        # truncated the sheet mid-JSON.
        with language_scope(language):
            pid, sheet = generate_persona(brief, language=language)
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
        "scope_world_id": lb["scope_world_id"],
        "scope_location_id": lb["scope_location_id"],
        "inheritance_mode": lb["inheritance_mode"] or "inherit",
        "sort_order": lb["sort_order"] or 0,
        "anchor_entity_id": lb["anchor_entity_id"],
        "entries": dump_lorebook(lid),
    }

@app.post("/api/lorebooks/{lid}/reinterpret")
def lore_reinterpret_route(lid: int):
    _require_lorebook(lid)
    try:
        with language_scope(_require_story_language(None)):
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
    try:
        language = require_language_pack(
            body.get("language") or _default_authoring_language(),
            capability="story").id
    except LanguagePackError as exc:
        raise HTTPException(400, str(exc)) from exc
    with transaction():
        cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (body.get("name") or f"Chat {int(time.time())}",
                  body.get("scenario", ""), time.time()))
        set_story_language(cid, language)
    result = dict(q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    result["story_language"] = language
    return result


@app.get("/api/language-packs")
def language_packs_get():
    return {"language_packs": [
        pack.public() for pack in installed_language_packs().values()
    ]}


@app.get("/api/ui")
def ui_catalog_get():
    pack = require_language_pack(ui_language(), capability="ui")
    return {
        "language": pack.id,
        "direction": pack.direction,
        "messages": dict(pack.ui_catalog),
    }


@app.get("/api/language-packs/{language_id}/ui")
def language_pack_ui(language_id: str):
    try:
        pack = require_language_pack(language_id, capability="ui")
    except LanguagePackError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "language": pack.public(),
        "messages": dict(pack.ui_catalog),
    }


@app.put("/api/ui-language")
def ui_language_put(body: dict = Body(...)):
    if not str(body.get("language") or "").strip():
        raise HTTPException(400, "language is required")
    try:
        language = set_ui_language(body.get("language"))
    except LanguagePackError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "language": language}


@app.get("/api/chats/{cid}/language")
def chat_language_get(cid: int):
    if not q("SELECT 1 FROM chats WHERE id=?", (cid,), one=True):
        raise HTTPException(404, "Chat not found")
    stored = str(wget(cid, STORY_LANGUAGE_KEY, DEFAULT_LANGUAGE) or DEFAULT_LANGUAGE)
    effective = story_language(cid)
    return {
        "language": effective,
        # What is on disk, which survives an uninstalled pack and comes back
        # when it is reinstalled. The client must not offer `language` as the
        # current selection when these differ -- that is how a chat carried
        # from another machine lost its language to an unrelated save.
        "stored": stored,
        "installed": stored == effective,
    }


@app.put("/api/chats/{cid}/language")
def chat_language_put(cid: int, body: dict = Body(...)):
    if not q("SELECT 1 FROM chats WHERE id=?", (cid,), one=True):
        raise HTTPException(404, "Chat not found")
    _require_chat_idle(cid)
    # Required, never defaulted: there is no spelling of "leave it alone", so
    # an omitted field would be indistinguishable from a request to change to
    # English -- and this route is issued on every style-guide save.
    if not str(body.get("language") or "").strip():
        raise HTTPException(400, "language is required")
    try:
        language = set_story_language(cid, body.get("language"))
    except LanguagePackError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "language": language}

@app.put("/api/chats/{cid}")
def chat_edit(cid: int, body: dict = Body(...)):
    row = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not row:
        raise HTTPException(404, "Chat not found")
    cur = dict(row)
    persona_changed = (
        "persona_id" in body and body.get("persona_id") != cur.get("persona_id")
    )
    if persona_changed:
        _require_chat_idle(cid)
    for k in ("name", "persona_id", "scenario"):
        if k in body: cur[k] = body[k]
    with transaction():
        qi("UPDATE chats SET name=?,persona_id=?,scenario=? WHERE id=?",
           (cur["name"], cur["persona_id"], cur["scenario"], cid))
        if persona_changed and cur["persona_id"] is not None:
            prow = q(
                "SELECT sheet FROM personas WHERE id=?",
                (cur["persona_id"],), one=True,
            )
            existing_scene = wget(cid, "scene", None)
            if prow and isinstance(existing_scene, dict):
                sheet = normalize_persona_data(json.loads(prow["sheet"] or "{}"))
                if seed_initial_attire(
                    existing_scene, persona_name(sheet),
                    persona_initial_outfit(sheet),
                ):
                    wset(cid, "scene", existing_scene)
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
    with transaction():
        # Cascade through turns → steps → variants (no chat_id on steps/variants)
        for t in q("SELECT id FROM turns WHERE chat_id=?", (cid,)):
            for s in q("SELECT id FROM steps WHERE turn_id=?", (t["id"],)):
                qi("DELETE FROM variants WHERE step_id=?", (s["id"],))
            qi("DELETE FROM steps WHERE turn_id=?", (t["id"],))
        # Tables with a direct chat_id foreign key
        for tbl in (
            "turns", "events", "world", "checkpoints",
            "chat_chars", "chat_lorebooks", "chat_personas",
            "chat_char_frames", "turn_player_inputs", "frames",
            "guest_grants", "scheduled_events", "room_registry",
            "world_events", "world_entities", "world_placements",
            "world_conditions", "fiction_worlds", "fiction_locations",
            "transit_edges",
        ):
            qi(f"DELETE FROM {tbl} WHERE chat_id=?", (cid,))
        # FTS table stores chat_id as text
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

    parts = []
    color_cast = []
    for row in q(
        "SELECT ch.id,COALESCE(cc.sheet,ch.sheet) AS sheet,cc.sheet AS override_sheet,"
        "cc.state,cc.status,cc.dialogue_color FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=? "
        "ORDER BY cc.char_id",
        (cid,),
    ):
        sheet = normalize_character_data(json.loads(row["sheet"] or "{}"))
        state = json.loads(row["state"] or "{}")
        if state.get("private_history") is not None:
            sheet["knowledge"]["private_history"] = state["private_history"]
        name = character_name(sheet)
        parts.append({
            "id": row["id"],
            "name": name,
            "sheet": json.dumps(sheet, ensure_ascii=False),
            "status": row["status"],
            "card_source": "chat" if row["override_sheet"] is not None else "library",
            # "" means the host has not chosen one; the resolved colour they
            # will actually see is in `dialogue_colors` below. Both are sent:
            # the picker needs to show whether a colour is chosen or derived.
            "dialogue_color": row["dialogue_color"] or "",
        })
        color_cast.append({
            "uid": name,
            "sheet": sheet,
            "color": row["dialogue_color"] or "",
        })

    # Keyed by DISPLAY NAME, because that is what a dialogue_log entry records
    # as its speaker. ORDER BY char_id above is what makes collision spreading
    # deterministic -- the same cast must resolve to the same colours on every
    # read, or a reload would repaint the story.
    dialogue_colors = resolve_cast_colors(color_cast)

    # Who said which line, per turn -- the index the transcript colours from.
    # NOT a new persisted thing: `dialogue_log` has always been committed here,
    # and DIALOGUE FIDELITY requires every one of these lines to appear in the
    # narrator's prose verbatim, so the renderer can find each quote and tint
    # it without storing an offset that a prose edit would invalidate. A quote
    # that no longer matches simply goes uncoloured; nothing is coloured by
    # guess.
    speech_by_turn = {}
    for row in q("SELECT turn_id, content FROM events WHERE chat_id=? "
                 "AND turn_id IS NOT NULL", (cid,)):
        try:
            entries = (json.loads(row["content"]) or {}).get("dialogue_log")
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        lines = []
        for entry in (entries or []):
            if not isinstance(entry, dict):
                continue
            speaker = str(entry.get("speaker") or "").strip()
            quote = str(entry.get("exact_quote") or "").strip()
            if speaker and quote:
                lines.append({"speaker": speaker, "quote": quote})
        if lines:
            speech_by_turn[row["turn_id"]] = lines

    # One query for the whole chat, replacing the per-turn COUNT this used to
    # run: the widened payload is CHEAPER than the boolean it replaces.
    stale_rows = q(
        "SELECT s.turn_id, s.key, s.label, s.ord "
        "FROM steps s JOIN turns t ON t.id = s.turn_id "
        "WHERE t.chat_id = ? AND s.stale = 1 "
        "ORDER BY s.turn_id, s.ord",
        (cid,),
    )
    stale_by_turn = {}
    for r in stale_rows:
        stale_by_turn.setdefault(r["turn_id"], []).append(r)

    turns = []
    for t in q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx", (cid,)):
        nar = active_content(t["id"], "narrator") or {}
        rows = stale_by_turn.get(t["id"]) or []
        # Lowest ord, not rows[0]. First-row indexing is correct only while
        # the ORDER BY above holds; min() survives an arbitrary row order.
        # The ORDER BY is kept regardless, for any reader that does index.
        earliest = min(rows, key=lambda r: r["ord"]) if rows else None

        turns.append(
            {
                "id": t["id"],
                "idx": t["idx"],
                "player_input": t["player_input"],
                "prose": nar.get("prose", ""),
                "stale": bool(rows),
                "stale_from": (
                    {
                        "ord": earliest["ord"],
                        "key": earliest["key"],
                        "label": earliest["label"],
                    }
                    if earliest
                    else None
                ),
                "prose_stale": any(r["key"] == "narrator" for r in rows),
                "frame_id": t["frame_id"],
                "speech": speech_by_turn.get(t["id"]) or [],
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

    # Whether THIS chat's memories were embedded by the model in use now.
    # Checked when a chat is opened rather than at boot, because that is the
    # moment the answer is about something the host recognises -- a named
    # story with a countable number of memories -- and because a bank only
    # matters when it is about to be read. Two COUNTs; the answer is `None` if
    # anything about it fails, and a failed maintenance check must never stop
    # a chat from opening.
    # NOT ASKED ABOUT ANYTHING THE ENGINE CAN FINISH ITSELF. A row stamped
    # `cheap:crc32:256` while a real provider is configured is a write this
    # engine failed -- a rate limit it should wait out and retry, silently,
    # because nobody is watching that path and being asked about it is worse
    # than useless: the question offers a whole-bank rebuild as the cure for
    # four rows the engine is already finishing. Those rows are handed to the
    # repair queue here instead, which is also how a story picks its rows back
    # up after a restart (the queue dies with the process).
    #
    # The stamp is the entire discriminator. Some OTHER model's key is a host
    # who changed embedding model, which is the case this prompt was written
    # for and still the case it fires on.
    try:
        queue_fallback_rows_for_repair(cid)
    except Exception:
        pass
    try:
        bank = embedding_bank_status(chat_id=cid)
        stranded = (bank["memories"]["stranded"]
                    + bank["memory_summaries"]["stranded"]
                    - bank["memories"].get("fallback_written", 0)
                    - bank["memory_summaries"].get("fallback_written", 0))
        bank = {**bank, "stranded": stranded} if stranded > 0 else None
    except Exception:
        bank = None

    # INSTRUMENTATION for the "turn does not appear until I switch stories and
    # switch back" report, 2026-08-08. The transcript rendered is old because
    # THIS PAYLOAD was old: the frontend re-render provably runs, and the
    # pipeline provably commits before its stream closes.
    #
    # The hypothesis is a stale read snapshot. Connections are thread-local and
    # long-lived (db.py `_local.conn`), the pipeline commits on its own thread,
    # and this route is served from uvicorn's threadpool -- so a connection
    # whose WAL snapshot predates the commit cannot see the turn. That would be
    # occasional (which thread serves it), would leave the old transcript
    # intact, and would clear on the next request: all three reported.
    #
    # `data_version` is the exact test and db.py already says so -- it changes
    # when ANOTHER connection commits and never for this one's own writes. Pair
    # this line with the `turn_committed` line the pipeline logs: if the read's
    # version is BELOW the commit's, the snapshot was stale and the mechanism
    # is proven. If they match and the turn is still missing, the hypothesis is
    # wrong and the hunt moves on.
    try:
        _dv = data_version()
        _max_turn = max((t.get("id") or 0) for t in turns) if turns else 0
        _pipeline_logger.info(
            "chat_read chat=%s turns=%d max_turn_id=%s data_version=%s "
            "thread=%s", cid, len(turns), _max_turn, _dv,
            threading.get_ident())
    except Exception:
        pass

    chat_payload = dict(chat)
    chat_payload["story_language"] = story_language(cid)
    return {
        "chat": chat_payload,
        "participants": parts,
        "turns": turns,
        "dialogue_colors": dialogue_colors,
        "lorebook": lbc,
        "lorebooks": books,
        "frames": list_frames(cid),
        "embedding_bank": bank,
    }

@app.post("/api/chats/{cid}/characters")
def chat_add_char(cid: int, body: dict = Body(...)):
    ch = body.get("char_id")
    if ch is None:
        raise HTTPException(400, "char_id required")
    char_row = q("SELECT sheet FROM characters WHERE id=?", (ch,), one=True)
    if not char_row:
        raise HTTPException(404, "Character not found")
    ex = q("SELECT * FROM chat_chars WHERE chat_id=? AND char_id=?", (cid, ch), one=True)
    if ex:
        qi("UPDATE chat_chars SET status='active' WHERE chat_id=? AND char_id=?", (cid, ch))
    else:
        qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?, 'active')", (cid, ch))
    scene_exists = wget(cid, "scene", None) is not None
    if scene_exists:
        sheet = normalize_character_data(json.loads(char_row["sheet"] or "{}"))
        name = character_name(sheet)
        if not ex:
            scene = get_scene(cid, dict(q(
                "SELECT * FROM chats WHERE id=?", (cid,), one=True)))
            if seed_initial_attire(
                scene, name, character_initial_outfit(sheet),
            ):
                wset(cid, "scene", scene)
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
        with story_language_scope(cid):
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
    persona_row = q("SELECT sheet FROM personas WHERE id=?", (pid,), one=True)
    if not persona_row:
        raise HTTPException(404, "Persona not found")
    ex = q("SELECT * FROM chat_personas WHERE chat_id=? AND persona_id=?", (cid, pid), one=True)
    if ex:
        qi("UPDATE chat_personas SET status='active' WHERE chat_id=? AND persona_id=?", (cid, pid))
    else:
        qi("INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')", (cid, pid))
    existing_scene = wget(cid, "scene", None)
    if not ex and isinstance(existing_scene, dict):
        sheet = normalize_persona_data(json.loads(persona_row["sheet"] or "{}"))
        if seed_initial_attire(
            existing_scene, persona_name(sheet), persona_initial_outfit(sheet),
        ):
            wset(cid, "scene", existing_scene)
    return {"ok": True}

@app.delete("/api/chats/{cid}/personas/{pid}")
def chat_del_persona(cid: int, pid: int):
    # Attachment and remote authority have the same lifecycle. Committing
    # these together prevents a detached player from retaining a live guest
    # session if the process stops between the two writes.
    with transaction():
        qi(
            "UPDATE chat_personas SET status='dormant' "
            "WHERE chat_id=? AND persona_id=?",
            (cid, pid),
        )
        guest.revoke_persona_grants(cid, pid)
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

    # Same per-chat stale query as chat_get. A guest used to be sent nothing
    # at all about staleness, so superseded prose reached them looking exactly
    # like current prose -- not even the host's dim.
    stale_rows = q(
        "SELECT s.turn_id, s.key, s.label, s.ord "
        "FROM steps s JOIN turns t ON t.id = s.turn_id "
        "WHERE t.chat_id = ? AND s.stale = 1 "
        "ORDER BY s.turn_id, s.ord",
        (cid,),
    )
    stale_by_turn = {}
    for r in stale_rows:
        stale_by_turn.setdefault(r["turn_id"], []).append(r)

    turns = []
    for t in q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx", (cid,)):
        extra = active_content(t["id"], "narrator_extra") or {}
        entry = extra.get(str(pid)) or {}
        my_input = q(
            "SELECT input FROM turn_player_inputs WHERE chat_id=? AND turn_idx=? "
            "AND persona_id=?",
            (cid, t["idx"], pid), one=True,
        )
        rows = stale_by_turn.get(t["id"]) or []
        earliest = min(rows, key=lambda r: r["ord"]) if rows else None
        turns.append({
            "idx": t["idx"],
            "player_input": my_input["input"] if my_input else None,
            "prose": entry.get("prose", ""),
            "stale": bool(rows),
            "stale_from": (
                {
                    "ord": earliest["ord"],
                    "key": earliest["key"],
                    "label": earliest["label"],
                }
                if earliest
                else None
            ),
            # The text a guest reads is narrator_extra, which is its own step
            # key (read three lines up), not the narrator step's own content.
            # Keying on "narrator" alone would key the guest's warning on a
            # step that does not produce what they are looking at, so this
            # takes the union of the two.
            "prose_stale": any(
                r["key"] in ("narrator", "narrator_extra") for r in rows
            ),
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


@app.put("/api/chats/{cid}/characters/{ch}/card")
def chat_char_card_put(cid: int, ch: int, body: dict = Body(...)):
    """Set this story's authored card without touching reusable or live state."""
    if not q("SELECT 1 FROM chats WHERE id=?", (cid,), one=True):
        raise HTTPException(404, "Chat not found")
    current_raw = chat_character_sheet(cid, ch)
    if current_raw is None:
        raise HTTPException(404, "That character is not in this story")

    _require_chat_idle(cid)
    current = normalize_character_data(current_raw)
    sheet = normalize_character_data(body.get("sheet") or {})
    raw_identity = (
        current_raw.get("identity")
        if isinstance(current_raw, dict)
        and isinstance(current_raw.get("identity"), dict)
        else {}
    )
    current_identity = current.get("identity") or {}
    identity = sheet.get("identity") or {}
    # Scene positions, recognition maps, memories, and relationship ledgers use
    # these as stable identity keys. A card edit may change psychology, voice,
    # history, senses, etc.; renaming an already-running fictional person needs
    # a dedicated identity migration rather than a string replacement here.
    if character_name(sheet) != character_name(current):
        raise HTTPException(400, "A story character's name cannot be changed here")
    # Very old cards may genuinely have no stored uid; the normalized editor
    # supplies one on their first save. Once a uid exists it is immutable.
    if (
        raw_identity.get("uid")
        and str(identity.get("uid") or "") != str(current_identity.get("uid") or "")
    ):
        raise HTTPException(400, "A story character's identity uid cannot be changed")

    cc = q(
        "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
        (cid, ch), one=True,
    )
    state = json.loads(cc["state"] or "{}")
    # Private history already has a per-story runtime override. Keep that
    # authoritative channel in sync with the edited story card while leaving
    # every other live-state field (mood, stress, beliefs, relationships)
    # untouched.
    state["private_history"] = (
        (sheet.get("knowledge") or {}).get("private_history") or []
    )
    with transaction():
        qi(
            "UPDATE chat_chars SET sheet=?,state=? WHERE chat_id=? AND char_id=?",
            (
                json.dumps(sheet, ensure_ascii=False),
                json.dumps(state, ensure_ascii=False),
                cid, ch,
            ),
        )
    return {"ok": True, "sheet": sheet, "card_source": "chat"}

@app.get("/api/chats/{cid}/survival")
def survival_get(cid: int):
    return {"enabled": survival_enabled(cid),
            "show_npcs": survival_shows_npcs(cid)}

@app.put("/api/chats/{cid}/survival")
def survival_put(cid: int, body: dict = Body(...)):
    """Bodily condition tracking for THIS story: breath, stamina, nourishment,
    injury.

    Off by default and off means ABSENT -- turning it off stops the ticking and
    leaves whatever a scene already recorded alone rather than zeroing bodies.
    """
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")

    # This setting and its seeded scene state are one authoring edit. Do not
    # let either race an active pipeline, and do not commit the toggles if
    # seeding the scene fails.
    _require_chat_idle(cid)
    enabled = bool(body.get("enabled"))
    with transaction():
        set_survival_enabled(cid, enabled)
        if "show_npcs" in body:
            set_survival_shows_npcs(cid, bool(body.get("show_npcs")))

        if enabled:
            # Seed the bodies this story knows about. Without this, switching
            # the feature on did nothing visible: the table only came into
            # existence when the Director wrote a vitals patch, and on a quiet
            # turn it had no reason to -- so the tracker stayed empty and the
            # tick had nothing to advance. Existing records are untouched, so
            # re-enabling resumes.
            chat = dict(chat)
            scene = get_scene(cid, chat)
            names = [persona_name(persona_of(chat))]
            for row in q(
                "SELECT COALESCE(cc.sheet,ch.sheet) AS sheet "
                "FROM chat_chars cc JOIN characters ch "
                "ON ch.id = cc.char_id WHERE cc.chat_id=? AND cc.status='active'",
                (cid,),
            ):
                try:
                    names.append(character_name(json.loads(row["sheet"])))
                except (TypeError, ValueError):
                    continue
            seed_vitals(scene, names)
            wset(cid, "scene", scene)

    return {"enabled": enabled, "show_npcs": survival_shows_npcs(cid)}

@app.get("/api/chats/{cid}/vitals")
def chat_vitals_get(cid: int):
    """Every tracked body's condition in this chat, for the UI tracker.

    Returns an empty table when the feature is off or nothing has been
    recorded, so the tracker can simply not render.
    """
    from world.survival import vital_label

    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")

    scene = get_scene(cid, dict(chat))
    table = scene.get("vitals") if isinstance(scene.get("vitals"), dict) else {}
    player = persona_name(persona_of(dict(chat)))

    bodies = []
    for name, record in (table or {}).items():
        if not isinstance(record, dict):
            continue
        bodies.append({
            "name": name,
            "is_player": str(name).strip().casefold() == str(player).strip().casefold(),
            "vitals": {k: record.get(k) for k in
                       ("air", "stamina", "nourishment", "injury")},
            "labels": {k: vital_label(k, record.get(k)) for k in
                       ("air", "stamina", "nourishment", "injury")},
        })
    bodies.sort(key=lambda b: (not b["is_player"], b["name"]))
    return {"enabled": survival_enabled(cid), "bodies": bodies,
            "player": player, "show_npcs": survival_shows_npcs(cid)}

@app.get("/api/chats/{cid}/positions")
def chat_positions_get(cid: int):
    """Where everyone in this story currently stands, and the rooms available.

    Read from the scene blob, which is the single runtime source of truth for
    live positions -- not from `world_placements` (decommissioned) or
    `world_entities` (a derived projection). See docs/guides/DATABASE.md.
    """
    from world.spatial import room_of

    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")

    chat = dict(chat)
    scene = get_scene(cid, chat)
    rooms = scene.get("rooms") or {}

    room_list = []
    for rid, data in rooms.items():
        data = data if isinstance(data, dict) else {}
        parent = data.get("parent_entity")
        entity = (scene.get("entities") or {}).get(parent) or {}
        room_list.append({
            "id": rid,
            "name": data.get("name") or rid,
            # An interior room (a vehicle's cabin, a building's floor) is
            # labelled with what it is inside, since "Console Room" alone does
            # not say which ship.
            "parent_entity": parent,
            "parent_name": (entity.get("name") or parent) if parent else None,
        })
    room_list.sort(key=lambda r: (r["parent_name"] or "", r["name"]))

    characters = []
    for row in q(
        "SELECT cc.char_id AS id,cc.status AS status,"
        "COALESCE(cc.sheet,ch.sheet) AS sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id = cc.char_id "
        "WHERE cc.chat_id=? ORDER BY ch.name",
        (cid,),
    ):
        name = character_name(json.loads(row["sheet"] or "{}"))
        characters.append({
            "id": row["id"],
            "name": name,
            "status": row["status"],
            "room": room_of(scene, name),
        })

    # persona_of returns a normalized SHEET (name at identity.name), and falls
    # back to "The Stranger" when no persona is attached -- which is the name
    # the pipeline itself uses, so it is the name the scene is keyed by. Shown
    # read-only: the player's own position is the story's business, not an
    # authoring dropdown's.
    player = persona_name(persona_of(chat))

    return {
        "rooms": room_list,
        "characters": characters,
        "persona": {"name": player, "room": room_of(scene, player)},
        "location": scene.get("location") or "",
    }

@app.put("/api/chats/{cid}/characters/{ch}/position")
def chat_char_position_put(cid: int, ch: int, body: dict = Body(...)):
    """Move a character to another room in the current scene.

    An authoring action, deliberately silent: like the world editor and the
    attire editor, it edits state and does not narrate. Nothing is queued for
    the narrator, so if the move should be seen in the fiction, write it.

    Room ids are validated against the scene rather than trusted -- a position
    naming a room that does not exist would leave the character nowhere that
    perception, adjacency, or the narrator can reason about. An empty room
    means offscreen (no position at all), which is a legitimate state.
    """
    from world.spatial import room_of

    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")

    sheet = chat_character_sheet(cid, ch)
    if sheet is None:
        raise HTTPException(404, "That character is not in this story")

    # The pipeline reads and rewrites positions throughout a turn; editing them
    # underneath a running one would either corrupt the scene or be silently
    # overwritten by the commit. Same guard the world editor uses.
    _require_chat_idle(cid)

    room = str(body.get("room") or "").strip()
    scene = get_scene(cid, dict(chat))
    rooms = scene.get("rooms") or {}
    if room and room not in rooms:
        raise HTTPException(
            400,
            f"No room '{room}' in this scene. "
            f"Known rooms: {', '.join(sorted(rooms)) or '(none)'}",
        )

    positions = scene.setdefault("positions", {})
    name = character_name(sheet)

    # room_of resolves a name case- and punctuation-insensitively, so the key
    # already in the scene may not be spelled the way the character row is.
    # Rewrite THAT key rather than adding a second spelling: two keys for one
    # person puts them in two rooms at once for every reader that walks
    # positions to find a room's occupants.
    # fold_identity_key, and only when it is non-empty. The old ASCII-only
    # fold mapped every Japanese name to "", so all of them compared equal and
    # the pop below removed EVERY other character's position -- the two
    # sibling folds in spatial.py and commit.py both guard for this.
    folded_name = fold_identity_key(name)
    existing_keys = [
        key for key in positions
        if folded_name and fold_identity_key(key) == folded_name
    ]
    for key in existing_keys:
        positions.pop(key)

    if room:
        positions[name] = room

    wset(cid, "scene", scene)
    return {"ok": True, "name": name, "room": room or None}

@app.get("/api/chats/{cid}/characters/{ch}/private_history")
def ph_get(cid: int, ch: int):
    cc = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?", (cid, ch), one=True)
    st = json.loads(cc["state"] or "{}") if cc else {}
    if st.get("private_history") is not None:
        return {"entries": st["private_history"], "source": "chat"}
    raw_sheet = chat_character_sheet(cid, ch)
    sheet = normalize_character_data(raw_sheet or {})
    return {"entries": sheet.get("knowledge", {}).get("private_history", []), "source": "sheet"}

@app.put("/api/chats/{cid}/characters/{ch}/private_history")
def ph_put(cid: int, ch: int, body: dict = Body(...)):
    cc = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?", (cid, ch), one=True)
    if not cc: raise HTTPException(404)
    st = json.loads(cc["state"] or "{}")
    st["private_history"] = body.get("entries", [])
    qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?", (json.dumps(st), cid, ch))
    return {"ok": True}

@app.put("/api/chats/{cid}/characters/{ch}/dialogue_color")
def dialogue_color_put(cid: int, ch: int, body: dict = Body(...)):
    """Pin this character's dialogue colour for this story, or clear the pin.

    An empty/absent `color` stores "" and hands the character back to the
    derivation -- which is the difference between "no colour" (impossible;
    everyone gets one) and "no CHOICE" (the default). A value this cannot read
    is refused rather than stored, because a stored unreadable colour would
    look identical to an unset one while being much harder to explain.

    The response returns the whole resolved cast, not just this character:
    colours are spread against each other, so pinning one can legitimately
    move another, and the client would otherwise paint a stale palette until
    the next full chat load.
    """
    cc = q("SELECT 1 FROM chat_chars WHERE chat_id=? AND char_id=?",
           (cid, ch), one=True)
    if not cc:
        raise HTTPException(404)

    raw = str(body.get("color") or "").strip()
    color = normalize_color(raw)
    if raw and not color:
        raise HTTPException(400, "color must be #rgb or #rrggbb")

    qi("UPDATE chat_chars SET dialogue_color=? WHERE chat_id=? AND char_id=?",
       (color, cid, ch))
    return {"ok": True, "color": color,
            "dialogue_colors": _resolved_dialogue_colors(cid)}


def _resolved_dialogue_colors(cid: int):
    """{display name: "#rrggbb"} for one story's cast.

    Keyed by display name because that is what `dialogue_log` records as its
    speaker. ORDER BY char_id is load-bearing: collision spreading walks the
    cast in order, so a different row order would resolve to a different
    palette and the story would repaint itself on reload.
    """
    cast = []
    for row in q(
        "SELECT COALESCE(cc.sheet,ch.sheet) AS sheet,cc.dialogue_color "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? ORDER BY cc.char_id",
        (cid,),
    ):
        sheet = normalize_character_data(json.loads(row["sheet"] or "{}"))
        cast.append({"uid": character_name(sheet), "sheet": sheet,
                     "color": row["dialogue_color"] or ""})
    return resolve_cast_colors(cast)


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
    # Re-derived, not stored verbatim. `wearing`, `state` and `regions` are one
    # wardrobe said three ways, and only the commit path was keeping them in
    # step -- so renaming a garment in the region editor left `wearing` still
    # naming the old spelling, and the next beat's reconciliation read the two
    # spellings as two garments and began putting one on while taking the other
    # off. That is where the measured fork actually started.
    scene["attire"] = {
        name: (attire.rederive_entry(entry) if isinstance(entry, dict) else entry)
        for name, entry in (body or {}).items()
    }
    wset(cid, "scene", scene)
    return {"ok": True}

@app.get("/api/chats/{cid}/style_guide")
def style_guide_get(cid: int):
    """The authored house style for generated content. `{}` means the engine
    self-determines, which is the default."""
    return {"style_guide": style_guide(cid), "fields": list(STYLE_GUIDE_FIELDS)}

@app.put("/api/chats/{cid}/style_guide")
def style_guide_put(cid: int, body: dict = Body(...)):
    """Set or clear the style guide. Normalized rather than trusted: it reaches
    a prompt on every generative beat, so unknown keys are dropped and bad
    input degrades to "self-determine" instead of malforming the payload.
    Clearing any field (or sending a genre of 'auto'/'self-determine') restores
    engine self-determination for it."""
    guide = normalize_style_guide(body.get("style_guide", body))
    wset(cid, "style_guide", guide)
    return {"ok": True, "style_guide": guide}

@app.get("/api/chats/{cid}/dialogue_config")
def dlg_get(cid: int):
    config = dialogue_config(cid)
    # The ladder rides with the config so the UI renders the rungs the engine
    # actually has, in the engine's order, rather than a copy of them that
    # drifts the first time one is added.
    config["offscreen_life_levels"] = [
        {"value": level,
         "description": OFFSCREEN_LIFE_DESCRIPTIONS[level],
         # Marked by the engine, not by the menu: an unbuilt rung must not
         # quietly start reading as built when it ships and nobody remembers
         # to edit the UI.
         "built": level in OFFSCREEN_LIFE_BUILT}
        for level in OFFSCREEN_LIFE_LADDER
    ]
    return config

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
            # 0 = never promote. Capped well below the point where a counter
            # would be theatre rather than a setting.
            "promote_after_addressed": max(
                0, min(99, int(body.get("promote_after_addressed", 0)))),
            # The ceiling on what the cast may do off screen. Normalized
            # rather than rejected: an unreadable value falls to the default,
            # never to the floor, so a typo cannot quietly switch a story's
            # off-screen life off (scene.normalize_offscreen_life).
            "offscreen_life": normalize_offscreen_life(
                body.get("offscreen_life", OFFSCREEN_LIFE_DEFAULT)),
            # 0 means no ticks however high the level is set -- the bound and
            # the permission are separate answers, and a cap of zero is a
            # legitimate way to say "not right now" without losing the level.
            "max_offscreen_actors": max(
                0, min(12, int(body.get("max_offscreen_actors", 3)))),
        }

        for key, default in derived.items():
            config[key] = max(0, int(body.get(key, default)))
    except (TypeError, ValueError):
        raise HTTPException(400, "dialogue config numeric fields must be numbers")

    config["max_lines"] = max(config["min_lines"], config["max_lines"])

    wset(cid, "dialogue_config", config)
    return config

@app.get("/api/chats/{cid}/living_world")
def living_world_get(cid: int):
    """The living-world ladder: five approaches, each off / floor / ceiling.

    The approaches ride with the config (the ``offscreen_life_levels``
    convention) so the UI renders what is on, what it costs, and what is
    merely declared from the engine's own tables -- an unbuilt tier is
    marked by the engine, not by a menu that drifts. ``approaches`` is
    computed against the chat's off-screen authority ceiling (folded in at
    read time by ``living_world_config``; never stored), so ``effective``
    and each depth's ``requires``/``permitted`` state the clamp the engine
    will actually apply; the reported ``living_world`` stays the stored
    mechanisms alone — the ceiling's one durable spelling is
    ``dialogue_config``'s.
    """
    from world.living_world import (living_world_config, living_world_levels,
                              normalize_living_world)

    config = living_world_config(cid)
    return {"living_world": normalize_living_world(config),
            "approaches": living_world_levels(config)}


@app.put("/api/chats/{cid}/living_world")
def living_world_put(cid: int, body: dict = Body(...)):
    """Set the ladder. Normalized rather than rejected, and the normalized
    config is returned so what actually stuck is visible immediately --
    here the default IS off, so this is the surface where a typo shows."""
    from world.living_world import LIVING_WORLD_KEY, normalize_living_world

    config = normalize_living_world(body.get("living_world", body))
    wset(cid, LIVING_WORLD_KEY, config)
    return {"ok": True, "living_world": config}


@app.get("/api/chats/{cid}/background_config")
def bg_cfg_get(cid: int):
    return background_config(cid)

@app.put("/api/chats/{cid}/background_config")
def bg_cfg_put(cid: int, body: dict = Body(...)):
    """Scene-manager settings (docs/design/BACKGROUND_LIFE_DESIGN.md §3.10).

    Lives beside dialogue_config rather than the style guide because these are
    simulation dials -- who gets to speak and act -- the same family as
    allow_npc_to_npc_dialogue. The style guide governs how invented people
    SOUND (blurb theming, the §3.8.1 canon licence), which is a separate axis
    and already wired.
    """
    level = str(body.get("scene_life", "off")).strip().casefold()
    if level not in ("off", "ambient", "full"):
        raise HTTPException(400, "scene_life must be off, ambient or full")
    try:
        config = {
            "scene_life": level,
            # Hard-capped to match agents/background.py: past a handful of
            # individually-voiced extras a crowd reads as noise.
            "max_managed": max(1, min(8, int(body.get("max_managed", 6)))),
            "max_reactors": max(1, min(3, int(body.get("max_reactors", 1)))),
        }
    except (TypeError, ValueError):
        raise HTTPException(400, "background config numeric fields must be numbers")
    wset(cid, "background_config", config)
    return config

@app.get("/api/chats/{cid}/story_view")
def story_view_get(cid: int, events: int = 20):
    """Canonical story state, versioned. The read `story_view.py` documents.

    Served to the host UI as well as to extensions because it is the same
    question either asks -- and because a surface only extensions can reach is
    one nothing in this repository exercises.
    """
    from web import story_view

    try:
        return story_view.story_view(cid, events=events)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

@app.get("/api/chats/{cid}/player_view")
def player_view_get(cid: int, viewer: str = "player", memories: int = 12):
    """What one viewer may be shown. See `story_view.player_view`."""
    from web import story_view

    try:
        return story_view.player_view(cid, viewer, memories=memories)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

@app.get("/api/chats/{cid}/viewers")
def viewers_get(cid: int):
    from web import story_view

    return {"viewers": story_view.viewers(cid)}

@app.get("/api/chats/{cid}/player_authority")
def player_authority_get(cid: int):
    """This story's player-authority mode, its ladder, and its change record.

    The ladder is served by the engine rather than copied into the menu, for
    the reason the offscreen-life route gives: a mode list maintained in two
    places is one that disagrees with itself the first time a rung moves.
    """
    current = player_authority(cid)
    current["modes"] = [
        {"value": mode, "grants": sorted(PLAYER_AUTHORITY_GRANTS[mode])}
        for mode in PLAYER_AUTHORITY_MODES
    ]
    return current

@app.put("/api/chats/{cid}/player_authority")
def player_authority_put(cid: int, body: dict = Body(...)):
    """Choose the mode. Refused rather than normalized, unlike its neighbours.

    `offscreen_life` falls back to its default on an unreadable value because
    the cost of guessing wrong there is a story with slightly more or less
    happening off screen. Here the cost is the player silently keeping or
    losing authorship of the world, and a typo that lands on `world_author`
    when `actor_only` was meant is exactly the failure the whole feature
    exists to prevent.
    """
    mode = str(body.get("mode", "")).strip().lower()
    if mode not in PLAYER_AUTHORITY_MODES:
        raise HTTPException(
            400, "mode must be one of " + ", ".join(PLAYER_AUTHORITY_MODES))
    turn_idx = body.get("turn_idx")
    try:
        turn_idx = int(turn_idx) if turn_idx is not None else None
    except (TypeError, ValueError):
        turn_idx = None
    return set_player_authority(cid, mode, turn_idx=turn_idx)

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

from persist.chat_archive import ArchiveRemappers, ChatArchiveService

_chat_archive_service = ChatArchiveService(
    ArchiveRemappers(
        active_books=_remap_active_books,
        fixed_point_frames=_remap_fixed_points_frames,
        scheduled_event_frames=_remap_scheduled_event_frames,
        checkpoint_blob=_remap_cp_blob,
        json_id_list=_json_id_list,
        frame_character_ids=_remap_frame_character_ids,
    )
)
chat_export = _chat_archive_service.export_chat
chat_import = _chat_archive_service.import_chat
app.include_router(_chat_archive_service.router)

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
    # No current_turn_idx on purpose. This is the author's Memories tab, the
    # search half of the same panel whose browse half is list_memories -- and
    # the author is not a fictional mind, so the F1 turn cutoff must not apply
    # to them. current_turn_idx used to be a pure recency-scoring hint here
    # and passing the latest turn was harmless; now that it is a hard filter
    # in search_memories, passing it would silently hide every memory from the
    # turn just played -- exactly the ones an author searches for after a beat
    # -- while browse kept showing them. search_memories falls back to the
    # newest turn in the bank for recency scoring, which is the right
    # reference point for a whole-bank author search anyway.
    return {
        "query": query,
        "results": search_memories(
            cid, ch, query, k=limit,
            include_archived=True,
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
    # A host-pressed button is still a model call into this story, and the
    # summary it writes is read by every future beat. Without the scope it was
    # written in English and persisted into a Japanese memory bank.
    try:
        with story_language_scope(cid):
            return consolidate_character_memory(
                cid, ch,
                through_turn_idx=body.get("through_turn_idx"),
                archive_old=body.get("archive_old", True),
            )
    except Exception as exc:
        raise HTTPException(502, str(exc))

@app.post("/api/chats/{cid}/characters/{ch}/memories/backfill")
def mem_backfill(cid: int, ch: int, body: dict = Body(default={})):
    """Rebuild the summary windows the pre-v23 singleton overwrote.

    One LLM call per missing window, so it is a button the host presses rather
    than anything that runs on its own. Idempotent: once a bank's windows reach
    back to its first memory there is nothing below the floor and a second
    press does nothing.
    """
    try:
        with story_language_scope(cid):
            result = backfill_memory_summary_windows(
                cid, ch, window=int(body.get("window") or 10))
        result["checkpoints_updated"] = (
            propagate_memory_summaries_to_checkpoints(cid, ch))
        return result
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, str(exc))

@app.get("/api/chats/{cid}/characters/{ch}/memories/coverage")
def mem_coverage(cid: int, ch: int):
    """How much of this character's life has a summary above it.

    What the backfill button needs to know before it offers itself: a bank
    whose windows already reach its first memory has nothing to rebuild.
    """
    return memory_summary_coverage(cid, ch)

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
        valence=body.get("valence", 0.0),
        arousal=body.get("arousal", 0.0),
        encoding_valence=body.get("encoding_valence", 0.0),
        encoding_arousal=body.get("encoding_arousal", 0.0),
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
        encoding_valence=body.get("encoding_valence"),
        encoding_arousal=body.get("encoding_arousal"),
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
        # read-compute-checkpoint-insert is atomic against any other concurrent
        # writer, not just against itself.  The checkpoint must be in this same
        # transaction: if capturing it fails, no stepless turn may survive to
        # block the frame's next submission.
        #
        # The snapshot itself is serialized BEFORE the transaction. It is the
        # single most expensive read in the app (every world KV, every
        # chat_chars row, every lorebook entry, every memory and summary),
        # ensure_checkpoint's own contract says it belongs outside the lock,
        # and building it here held the global write lock -- blocking every
        # other writer, including background backdrop/ambience jobs -- for
        # the whole serialization.
        #
        # Staleness is decided by `db.data_version`, NOT by comparing turn ids.
        # A turn-id check only catches another frame's pipeline committing a
        # turn, and plenty of writers change checkpointed state without
        # inserting a turn row: a lorebook edited in another tab, a character
        # sheet saved, a memory edited, a background job writing a world key.
        # SQLite moves `data_version` on any OTHER connection's commit and
        # never on this connection's own, and connections here are
        # thread-local, so every concurrent writer is visible to it. A false
        # positive -- some unrelated write landing in the window -- costs one
        # rebuild under the lock, which is exactly the pre-change behaviour.
        pre_version = data_version()
        pre_blob = json.dumps(snapshot_state(cid))
        with transaction():
            last = _latest_turn(cid)
            idx = (last["idx"] + 1) if last else 0
            if data_version() != pre_version:
                pre_blob = json.dumps(snapshot_state(cid))
            ensure_checkpoint(cid, idx, blob=pre_blob)
            tid = qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                     (cid, idx, _player_input(body), time.time(), frame_id))
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
    # The branch inherits the source's scene, so the rooms it starts in are
    # the rooms the source already has backdrops for. Recording the source
    # (and everything the source itself branched from, so a branch of a
    # branch still reaches the original) lets backdrops.py read those images
    # where they lie instead of redrawing the inheritance room by room.
    # Nearest ancestor first: the closest chat is the likeliest to hold the
    # picture, and a shorter walk is a cheaper miss.
    try:
        lineage = json.loads(src.get("branched_from") or "[]")
        if not isinstance(lineage, list):
            lineage = []
    except (ValueError, TypeError):
        lineage = []
    lineage = json.dumps([cid] + [a for a in lineage if a != cid][:63])

    with transaction():
        ncid = qtx(
            "INSERT INTO chats(name,persona_id,scenario,branched_from,created) "
            "VALUES(?,?,?,?,?)",
            (f"{src['name']} ⎇{idx}", src["persona_id"], src["scenario"],
             lineage, time.time())
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

        # Copy chat characters. dialogue_color rides along with sheet for the
        # same reason: a branch inherits how the story was CONFIGURED, and a
        # cast that changed colour the moment you branched would read as a
        # rendering fault rather than a new timeline.
        for cc in q("SELECT * FROM chat_chars WHERE chat_id=?", (cid,)):
            qtx(
                "INSERT INTO chat_chars"
                "(chat_id,char_id,status,state,sheet,dialogue_color) "
                "VALUES(?,?,?,?,?,?)",
                (ncid, cc["char_id"], cc["status"], cc["state"], cc["sheet"],
                 cc["dialogue_color"] or "")
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
                        "INSERT INTO variants(step_id,content,created,active,"
                        "reasoning) VALUES(?,?,?,?,?)",
                        (ns, v["content"], v["created"], v["active"],
                         v["reasoning"] if "reasoning" in v.keys() else "")
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
        # `blob` is the checkpoint at the branch point, so every value in it is
        # as of that turn -- correct for the fiction, wrong for the reader's
        # settings. Turn NPC autonomy up at turn 60, branch from turn 20, and
        # the branch opened with the old dial because the change postdates the
        # checkpoint. Overlay the source chat's CURRENT settings; they are not
        # turn-scoped facts. (Same reasoning as checkpoints._preserved_settings,
        # which keeps them across a reroll.)
        for _skey in PRESERVED_SETTING_KEYS:
            _live = wget(cid, _skey, None)
            if _live is not None:
                world[_skey] = _live
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
                      "scheduled_events", "world_events", "room_registry",
                      "fiction_worlds", "fiction_locations")
        }))
        if world_id_remap:
            for k in world_tables:
                world_tables[k] = _deep_remap_ids(world_tables[k], world_id_remap)
                _remap_row_json_fields(world_tables[k], world_id_remap)
        for ent in world_tables["world_entities"]:
            ent["created_turn_id"] = idmap.get(ent.get("created_turn_id"))
            ent["retired_turn_id"] = idmap.get(ent.get("retired_turn_id"))
        for ev in world_tables["world_events"]:
            ev["turn_id"] = idmap.get(ev.get("turn_id"))
            ev["frame_id"] = frame_idmap.get(ev.get("frame_id"))
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

    # `story_language` lives in the `world` table, not on the chat row, so it
    # has to be added the way chat_new and chat_get already add it. The branch
    # carries the value correctly; only this response was missing it.
    branched = dict(q("SELECT * FROM chats WHERE id=?", (ncid,), one=True))
    branched["story_language"] = story_language(ncid)
    return branched
    
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

# ---- Narration variants: flipping between rerolls of the CURRENT beat ----
#
# A full reroll re-runs the pipeline against the same turn and appends a new
# variant to every step, the newest becoming active -- so a turn rerolled three
# times holds four renderings of itself and the reader can only see the last.
# These two routes are the whole affordance for browsing them without opening
# the technical panel.
#
# Deliberately NOT marking anything stale, for the reason `edit_prose` gives
# directly above: the director/perception/commit steps that already ran are the
# mechanical record of what happened, commit has already applied side effects
# that are not idempotent, and choosing which rendering of an already-true beat
# the reader sees is a presentational operation. Selecting a variant the engine
# itself generated is strictly less arbitrary than the free-text prose edit that
# route already permits without staleness.
#
# Restricted to the LATEST turn by `_require_latest`. An earlier turn's
# alternate rendering is a different question -- every turn after it was
# generated against the prose that IS active -- and swapping one silently would
# leave the story describing a beat nobody downstream read.

@app.get("/api/turns/{tid}/narration")
def turn_narration_variants(tid: int):
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")
    step = q("SELECT * FROM steps WHERE turn_id=? AND key='narrator'",
             (tid,), one=True)
    if not step:
        return {"variants": []}
    out = []
    for v in q("SELECT id,content,active,created FROM variants "
               "WHERE step_id=? ORDER BY id", (step["id"],)):
        try:
            prose = (json.loads(v["content"]) or {}).get("prose") or ""
        except (TypeError, ValueError):
            prose = ""
        out.append({"id": v["id"], "active": bool(v["active"]),
                    "created": v["created"], "prose": prose})
    return {"variants": out}


@app.post("/api/turns/{tid}/narration")
def turn_narration_select(tid: int, body: dict = Body(...)):
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")
    _require_latest(turn)
    step = q("SELECT * FROM steps WHERE turn_id=? AND key='narrator'",
             (tid,), one=True)
    if not step:
        raise HTTPException(404, "This turn has no narrator output")
    variant = q("SELECT id,content FROM variants WHERE id=? AND step_id=?",
                (body.get("variant_id"), step["id"]), one=True)
    if not variant:
        raise HTTPException(404, "Variant not found on this turn's narration")
    with transaction():
        qi("UPDATE variants SET active=0 WHERE step_id=?", (step["id"],))
        qi("UPDATE variants SET active=1 WHERE id=?", (variant["id"],))
    try:
        prose = (json.loads(variant["content"]) or {}).get("prose") or ""
    except (TypeError, ValueError):
        prose = ""
    return {"ok": True, "prose": prose}


@app.get("/api/turns/{tid}/pipeline")
def pipeline_get(tid: int):
    steps = []
    for s in q("SELECT * FROM steps WHERE turn_id=? ORDER BY ord", (tid,)):
        # `reasoning` is a thinking model's own trace, kept for debugging. It
        # is sent so the pipeline view can offer it behind a disclosure, and
        # it must stay clearly separated from `content`: it has been through
        # none of the validation the output has, and it is the model talking
        # to itself rather than anything the fiction has ratified.
        vs = [dict(r) for r in q(
            "SELECT id,content,active,created,reasoning FROM variants "
            "WHERE step_id=? ORDER BY id", (s["id"],))]
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
        "perceivers": _perceiver_names(turn["chat_id"]),
    }


def _perceiver_names(chat_id: int):
    """Perceiver id -> display name, for reading a perception step per mind.

    The perception stages key their views by cast id and the literal string
    "player", which is unreadable in a raw JSON dump: finding out that one
    character's view of a beat had no sight in it meant holding an id-to-name
    map in your head while diffing three blobs by eye.

    Every character ever attached to the chat, not just the currently active
    cast -- a turn is read long after it ran, and a character dormant or
    detached today still has views on the beats they were present for.
    """
    names = {}
    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if chat:
        try:
            names["player"] = persona_name(persona_of(dict(chat)))
        except Exception:
            names["player"] = "Player"
    for row in q(
        "SELECT c.id, COALESCE(cc.sheet, c.sheet) sheet FROM chat_chars cc "
        "JOIN characters c ON c.id=cc.char_id WHERE cc.chat_id=?", (chat_id,)
    ):
        try:
            names[str(row["id"])] = character_name_from_text(row["sheet"])
        except Exception:
            continue
    return names

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
# ============================ SCENE BACKDROPS ============================
# A generated image of the room the player is standing in, rendered behind the
# transcript. Entirely out of band: nothing here is reachable from the turn
# pipeline, and no turn ever waits on an image. See backdrops.py for the three
# rules that make the feature safe (whitelisted spatial projection, never any
# people, cache keyed on room + visible state).
#
# Every route below lives under /api/, so the access-control middleware makes
# it host-only for free. Serving the PNGs from a StaticFiles mount instead
# would have put an enumerable dump of every room in every story outside that
# middleware entirely -- the paths are predictable and the middleware waves
# through anything not under /api/.

# A signature is sha256(...).hexdigest()[:24] (backdrops.visual_signature), so
# hex-only is both the true shape and, because the value is interpolated into
# a filesystem path, the thing that makes `../../engine.db` unrepresentable.
_BACKDROP_SIGNATURE = re.compile(r"^[0-9a-f]{8,64}$")


def _backdrop_turn(tid: int):
    turn = q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
    if not turn:
        raise HTTPException(404, "Turn not found")
    return turn


def _backdrop_player(chat_id: int):
    """The player's display name, which is how backdrops.py finds their room.

    The same persona_of/persona_name pair used by commit.py and the cast
    routes -- deliberately not the denormalised personas.name column, which
    diverges from the sheet.
    """
    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")
    return persona_name(persona_of(dict(chat)))


def _backdrop_url(chat_id, signature):
    return "/api/chats/%d/backdrop/%s.png" % (int(chat_id), signature)


@app.get("/api/turns/{tid}/backdrop")
def turn_backdrop(tid: int):
    """What backdrop this turn wants, and whether it is already on disk.

    Cheap and free: resolves the room and the cache signature, and NEVER
    generates. The frontend calls this for whichever turn the reader is
    looking at, then POSTs only if it wants to pay for a miss.
    """
    turn = _backdrop_turn(tid)
    cid = turn["chat_id"]
    req = build_backdrop_request(cid, turn["idx"], _backdrop_player(cid),
                                 style_guide(cid))
    configured = bool(image_model())
    enabled = get_setting("backdrops_enabled") == "1"
    if not req:
        # No room resolved -- an opening turn before mapping has placed
        # anyone, say. Not an error: there is simply nothing to depict.
        return {"enabled": enabled, "configured": configured, "room": None,
                "room_id": None,
                "signature": None, "ready": False, "url": None}
    status = backdrop_status(cid, req["signature"])
    return {
        "enabled": enabled,
        "configured": configured,
        "room": req["room_name"],
        # The room's IDENTITY, not its display name. A turn with no picture of
        # its own leaves whatever is on screen up rather than blanking, and that
        # is only honest while the reader is still in the same room -- see
        # `backdropForTurn`. Two rooms can share a name; they cannot share this.
        "room_id": req["room"],
        "signature": req["signature"],
        "ready": bool(req["cached"]),
        # 'ready' | 'pending' | 'error' | 'absent'. Pending is why this route
        # is worth polling: it is how a caller waits for an image without
        # anything holding a connection open for the length of a generation.
        "status": status,
        "error": backdrop_error(req["signature"]) if status == "error" else None,
        "url": _backdrop_url(cid, req["signature"]) if req["cached"] else None,
        # What the weather overlay should draw over this room, already scoped
        # to what the room can see. {} for anywhere with no sky. `severity` is
        # the host's own setting riding along on it, so the drawing can be as
        # restrained or as violent as the story asked for.
        "weather": dict(req.get("weather") or {},
                        severity=weather_severity(cid))
        if req.get("weather") else {},
    }


@app.post("/api/turns/{tid}/backdrop")
def turn_backdrop_generate(tid: int, body: dict = Body(default={})):
    """Ask for this turn's backdrop. Returns immediately.

    Deliberately does NOT wait for the image. Generation runs tens of seconds
    and can reach the provider's three-minute timeout; blocking here would hold
    a server worker that whole time for a picture nobody is waiting on -- the
    prose is already on screen. The caller gets 'ready' or 'pending' and polls
    the GET. Two callers wanting the same signature share one worker.
    """
    turn = _backdrop_turn(tid)
    cid = turn["chat_id"]
    if not image_model():
        raise HTTPException(
            503, "No image model configured — pick one under ⚙ API › Scene backdrops.")
    out = request_backdrop(cid, turn["idx"], _backdrop_player(cid),
                           style_guide(cid), force=bool(body.get("force")))
    if not out:
        raise HTTPException(409, "This turn has no room to depict yet.")
    ready = out["status"] == "ready"
    return {"enabled": get_setting("backdrops_enabled") == "1",
            "configured": True,
            "room": out["room"], "signature": out["signature"],
            "status": out["status"], "ready": ready,
            "url": _backdrop_url(cid, out["signature"]) if ready else None}


@app.get("/api/chats/{cid}/backdrop/{signature}.png")
def backdrop_image(cid: int, signature: str):
    if not _BACKDROP_SIGNATURE.match(signature or ""):
        raise HTTPException(404)
    path = cached_backdrop(cid, signature)
    if not path:
        raise HTTPException(404, "No backdrop for that signature")
    # Content-addressed by signature: the bytes at a given URL can never
    # change, so this is safely immutable and a revisited room repaints
    # without touching the network at all.
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})
# ============================ ROOM AMBIENCE ============================
# The audio twin of the section above: a looping sound bed for the room the
# player is standing in. Same guarantees, same out-of-band execution -- see
# ambience.py for why the acoustic cache key is a different set of fields from
# the visual one (light changes the picture and not the sound; weather and the
# hour change both).
#
# Every route lives under /api/, so the access-control middleware makes it
# host-only for free -- and the audio route in particular must stay there: it
# serves files from a host-chosen directory, which is not something to hang
# outside authentication.


def _ambience_url(chat_id, signature, rev=0, layer=0):
    # `rev` is what makes the immutable cache header honest across a reroll:
    # same signature, different bytes, therefore a different URL. `layer` picks
    # one bed out of a mix.
    return "/api/chats/%d/ambience/%s.audio?rev=%d&layer=%d" % (
        int(chat_id), signature, int(rev or 0), int(layer or 0))


def _ambience_payload(cid, req, status=None):
    """The one shape both ambience routes answer with."""
    settings = ambience_settings()
    manifest = req.get("cached") if req else None
    # A room the `ambience_prompt` model judged to have no continuous sound of
    # its own. RESOLVED, not missing: `ready` stays true and the token still
    # moves, so the client crossfades to quiet exactly as it would to a bed,
    # and nothing re-asks for a sound that was correctly declined.
    silent = bool((manifest or {}).get("silent"))
    return {
        "enabled": settings["enabled"],
        "configured": settings["configured"],
        "source": settings["source"],
        "room": req["room_name"] if req else None,
        "room_id": req["room"] if req else None,
        "signature": req["signature"] if req else None,
        "pinned": bool(req.get("pin")) if req else False,
        # Per-room level: rain two rooms in is quieter as well as different.
        "gain": (req or {}).get("gain") or 1.0,
        "ready": bool(manifest),
        "silent": silent,
        # Why this room is quiet, in the model's own words, for the panel to
        # show. A verdict a reader cannot see reads as a broken feature.
        "reason": (manifest or {}).get("reason") or "" if silent else "",
        "status": status or (ambience_status(cid, req["signature"]) if req else "absent"),
        "error": ambience_error(req["signature"]) if req else None,
        # WHICH KIND of recorded failure: 'notfound' is an answer ("this room
        # has no matching sound") and the client words it as one; 'failed' is
        # a malfunction. Without the distinction the client's only options
        # were a Python type name in a toast or one message for both.
        "error_kind": ambience_error_kind(req["signature"]) if req else None,
        "url": _ambience_url(cid, req["signature"],
                             (manifest or {}).get("rev")) if manifest and not silent
        else None,
        # The mix: one entry per simultaneous bed, each with its own level and
        # its own credit. A single-bed room is a one-entry list, so the client
        # has one shape to handle rather than two.
        "layers": [
            {"index": index,
             "role": layer.get("role") or "tone",
             "gain": layer.get("gain", 1.0),
             "title": layer.get("title") or "",
             "source": layer.get("source") or "",
             # What a pin needs to name this exact sound again. Host-only
             # route, and a local path is the host's own library.
             "path": layer.get("path") or "",
             "id": layer.get("id"),
             "license": layer.get("license") or "",
             "username": layer.get("username") or "",
             "credit_url": layer.get("url") or "",
             "query": layer.get("query") or "",
             "url": _ambience_url(cid, req["signature"],
                                  (manifest or {}).get("rev"), index)}
            for index, layer in enumerate((manifest or {}).get("layers") or [])
        ] if manifest else [],
        # The identity the PLAYER uses. A reroll keeps the signature (the room
        # and its state have not changed) but must still crossfade to the new
        # bed, so the thing the frontend compares has to move when the bytes
        # do.
        "token": "%s#%d" % (req["signature"], (manifest or {}).get("rev") or 0)
        if req and manifest else None,
        # What is actually playing, so the reader can see (and credit) it. The
        # Freesound licences in play require attribution, and a feature that
        # cannot tell you what it fetched cannot honour that.
        "track": {k: manifest.get(k) for k in
                  ("title", "source", "license", "username", "url", "query")}
        if manifest and not silent else None,
    }


@app.get("/api/turns/{tid}/ambience")
def turn_ambience(tid: int):
    """What this turn's room should sound like, and whether it is already here.

    Cheap and free: resolves the room and the cache signature, and NEVER
    searches or downloads. The frontend calls this for whichever turn is on
    screen, then POSTs only if it wants to pay for a miss.
    """
    turn = _backdrop_turn(tid)
    cid = turn["chat_id"]
    req = build_ambience_request(cid, turn["idx"], _backdrop_player(cid),
                                 style_guide(cid))
    if not req:
        return _ambience_payload(cid, None)
    return _ambience_payload(cid, req)


@app.post("/api/turns/{tid}/ambience")
def turn_ambience_resolve(tid: int, body: dict = Body(default={})):
    """Ask for this turn's ambience. Returns immediately.

    Like the backdrop POST, this does NOT wait: a library search plus a
    download is seconds of network for audio nobody is waiting on. The caller
    gets 'ready' or 'pending' and polls the GET.
    """
    turn = _backdrop_turn(tid)
    cid = turn["chat_id"]
    settings = ambience_settings()
    if not settings["configured"]:
        raise HTTPException(
            503, "Ambience has no source yet — set one under ⚙ API › Room ambience.")
    layer = body.get("layer")
    # `layer` narrows a reroll to one bed of the mix; absent, null or
    # unparseable all mean the whole mix. A caller that sends something else is
    # asking for a reroll, not for a 500.
    try:
        reroll_layer = int(layer) if layer is not None else None
    except (TypeError, ValueError):
        reroll_layer = None
    out = request_ambience(cid, turn["idx"], _backdrop_player(cid),
                           style_guide(cid), force=bool(body.get("force")),
                           reroll=bool(body.get("reroll")),
                           reroll_layer=reroll_layer)
    if not out:
        raise HTTPException(409, "This turn has no room to give a sound to yet.")
    req = build_ambience_request(cid, turn["idx"], _backdrop_player(cid),
                                 style_guide(cid))
    return _ambience_payload(cid, req, status=out["status"])


@app.get("/api/chats/{cid}/ambience/{signature}.audio")
def ambience_audio(cid: int, signature: str, layer: int = 0):
    if not _BACKDROP_SIGNATURE.match(
            (signature or "").removeprefix("pin").removeprefix("fx")):
        raise HTTPException(404)
    manifest = cached_ambience(cid, signature)
    if not manifest:
        raise HTTPException(404, "No ambience for that signature")
    layers = manifest.get("layers") or []
    if layer < 0 or layer >= len(layers):
        raise HTTPException(404, "No such layer in that mix")
    path = layers[layer]["file_path"]
    return FileResponse(path, media_type=media_type_for(path),
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.get("/api/ambience/search")
def ambience_search(q: str, source: str = "", limit: int = 8):
    """Candidate sounds for a query, for the reassignment picker.

    Deliberately NOT cached and NOT written anywhere: this is a host browsing,
    not the engine choosing. Nothing is downloaded until something is pinned.
    """
    query = str(q or "").strip()
    if not query:
        raise HTTPException(400, "A search needs a query")
    if source and source not in ("local", "freesound"):
        raise HTTPException(400, "source must be 'local' or 'freesound'")
    try:
        results = search_candidates(query, source or None,
                                    limit=max(1, min(int(limit), 20)))
    except Exception as exc:
        raise HTTPException(502, "Search failed: %s" % str(exc)[:200])
    return {"query": query, "source": source or ambience_settings()["source"],
            "results": results}


@app.get("/api/ambience/library")
def ambience_library():
    """Everything in the local library, so the picker can list it unfiltered."""
    settings = ambience_settings()
    return {"library": settings["library"],
            "exists": os.path.isdir(settings["library"]),
            "files": library_files(settings["library"])}


@app.get("/api/chats/{cid}/ambience/oneshot/{name}")
def ambience_oneshot(cid: int, name: str, variant: int = -1):
    """A non-looping effect (thunder), fetched once and cached forever.

    Asked for by the weather overlay when it draws lightning: a flash with no
    sound is a screen artifact. Returns immediately with 'pending' on a miss --
    the first storm of a session may flash silently, and that is a better
    outcome than holding a request open.
    """
    # A different take each time unless one is asked for by number. Chosen
    # HERE rather than by the caller so every route to a thunderclap gets the
    # variety, and so the client stays as dumb as "play thunder".
    if variant < 0:
        variant = random.randrange(ONESHOT_VARIANTS)
    try:
        out = request_oneshot(cid, name, variant)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    ready = out["status"] == "ready"
    return {"name": name, "variant": variant, "status": out["status"],
            "ready": ready, "error": ambience_error(out["signature"]),
            "url": _ambience_url(cid, out["signature"]) if ready else None}


@app.get("/api/chats/{cid}/ambience/pins")
def ambience_pins_get(cid: int):
    return {"pins": ambience_pins(cid)}


@app.put("/api/chats/{cid}/ambience/pin")
def ambience_pin_put(cid: int, body: dict = Body(...)):
    """Fix one room's sound to an explicit choice.

    Keyed by room rather than by cache signature on purpose: a host saying
    "this hall sounds like this" means the hall, not the hall-at-night-in-rain.
    The pin therefore also overrides the time-of-day and weather shifts the
    automatic path makes -- that is the point of pinning one.
    """
    room = str(body.get("room") or "").strip()
    if not room:
        raise HTTPException(400, "A pin needs a room id")
    try:
        pin = set_ambience_pin(cid, room, body.get("choice") or body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "room": room, "pin": pin}


@app.delete("/api/chats/{cid}/ambience/pin")
def ambience_pin_delete(cid: int, room: str):
    """Drop a pin, returning the room to automatic selection."""
    return {"ok": True, "cleared": clear_ambience_pin(cid, str(room or "").strip()),
            "pin": ambience_pin_for(cid, str(room or "").strip())}
