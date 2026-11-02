# Audit — `llm/providers.py`, `llm/llm_quality.py`, `llm/prompt_cache.py`, `llm/research_providers.py`

Auditor: one fleet member, 2026-11-01, working tree at `84f3de23` (branch
`worktree-jev-character-tracking`, clean). Read-only; every executed check was an
in-process snippet on `.venv/bin/python` against a scratch database under the
scratchpad (`ENGINE_DB=<scratchpad>/llmaudit/*.db`), with HTTP replaced by fakes —
no network call to any provider, no test-suite run.

## Scope read

Read in full, every line:

- `llm/providers.py` 1-5849 (all of it, in 24 consecutive slices), with the anatomy
  file `scratchpad/anatomy/providers.md` as the index.
- `llm/llm_quality.py` 1-2132.
- `llm/prompt_cache.py` 1-78.
- `llm/research_providers.py` 1-247.

Read in part, to trace callers and readers (not audited as files):

- `agents/runtime.py` 600-740, 2100-2180 (step workers, `cancel_event` set/clear).
- `agents/character.py` 3825-3850, 4860-4905, 5120-5160 (`last_reasoning` reader,
  kept thoughts); `agents/loops.py` 1380-1475 (sequential minds in the interaction
  loop); `mind/character_jev.py` 430-445; `mind/thoughts.py` 1-40.
- `core/jobs.py` 118-300 (context copy and `_clear_turn_scoped_context`).
- `persist/commit_memory_write.py` 23-130, 311, 415-435; `persist/commit.py` 625-640.
- `story/importers.py` 45-60, 2560-2590 (lorebook generator's `request_timeout`);
  `agents/story_planner.py` 2078-2100 (`patient_stream`).
- `story/room_research.py` 284-332 (`fetch_page`).
- `mind/memory_vectors.py` `embedding_bank_status`; `mind/skip_memories.py` 600-660;
  `mind/memory_summaries.py` 455-525; `agents/common.py` 4110-4150.
- `web/app.py` 3319-3345 (`add_provider`), 5340-5380 (`guest_input`), the
  `/api/memory/embeddings` route; `web/auth_routes.py` 50-175.
- `static/js/settings.js` 1975-2000, 2810-2830, 2980-2995; `static/js/chat.js`
  2040-2065; `core/pipeline_context.py` 560-590; `core/logging_utils.py` 95-122.
- `llm/decisions.py` 60-160, 290-320; `language_runtime/__init__.py` 635-645.
- Tests read for intent only: `tests/test_provider_fallbacks.py` 1-80,
  `tests/test_a_design_is_allowed_to_think.py`, `tests/test_a_first_token_may_take_thirty_seconds.py`
  1-120, `tests/test_a_restarted_answer_is_read_from_its_restart.py`, `tests/conftest.py` 285-330,
  `tests/test_memory_consolidation_parallel.py` 60-110.
- Registers grepped for every symbol named below: `docs/UNBUILT*.md` (all ten);
  docs checked: `AGENTS.md` 336-356, 552-559; `Design.md` 306, 400, 514, 517, 1188;
  `docs/guides/ENGINEERING.md` 690-740.

## Findings

### F1 — A mind can read the previous mind's private reasoning as its own (`last_reasoning` is never cleared, and two transports never write it)

- **Where.** `llm/providers.py:4350-4357` clears three of the four "last call" records at
  the start of every completion and not the fourth:
  ```python
  _capture_finish_reason(None)
  last_request_shape.set(None)
  last_output_spend.set(None)
  ```
  `_sse_anthropic` (`providers.py:3602-3670`) and the blocking Anthropic branch
  (`4436-4457`) never write `last_reasoning`; `_claude_cli_complete` writes it only
  `if reasoning:` (`3939-3943`). Only `_sse_openai` resets it (`3588`,
  `last_reasoning.set(reasoning or None)`).
- **The reader that turns this into a leak.** `agents/character.py:4883-4900`:
  ```python
  from llm.providers import last_reasoning
  # The model's own thinking ... is read by this mind's decision-model request
  _trace = str(last_reasoning.get() or "")
  _thought_in_order = _trace
  ...
  _holding.reasoning = _trace
  ```
  `_holding.reasoning` goes into the decision-model read-back
  (`mind/character_jev.py:441-443`, `if h.reasoning: ... _text(h.reasoning, ...)`), and with
  `character_thoughts_kept` set it is filed as this mind's own `_thought`
  (`character.py:5131-5136`) and handed back to it in later packets as
  `what_you_were_thinking` (`mind/thoughts.py`).
- **Scenario.** The interaction loop runs minds one after another on ONE thread and one
  context (`agents/loops.py:1393-1395`, "parallel in the FICTION, not in execution";
  `1466 result = character_step(ctx, speaker_id, ...)`). Mind A's tier
  (`character_major`) is on an OpenAI-style thinking route; mind B's tier
  (`character_mid`) is on a native `anthropic` connection (or `claude_cli` that streams no
  thinking). A's call leaves its trace in `last_reasoning`; B's call does not touch it; B's
  `_trace` is A's private thinking, which B's decision model reads and B keeps as its own
  thought. Same class: a `repair`-role field patch on a thinking route made during A's
  step leaves the patch model's trace about A's answer fragments for B.
- **Verified.** Snippet (scratch DB, fake Anthropic SSE session): set `last_reasoning` to
  `'A private: I will betray B at dawn'`, ran `_chat_complete_once` for `character_mid` on
  a `kind="anthropic"` provider —
  `(a) B answer: {"say": "B speaks"} | last_reasoning after B call: 'A private: I will betray B at dawn'`.
  The suite already knows the staleness: `tests/conftest.py:291-317` resets every provider
  ContextVar between tests because "`test_claude_cli_provider` leaves
  `last_reasoning == "private"`" — fixed in the harness, not in the engine. Readers traced:
  `character.py:4888`, `character_jev.py:441`, `character.py:5131`. Full multi-mind
  pipeline not executed.
- **Confidence.** CONFIRMED (mechanism reproduced; reachability needs a mixed-route
  configuration — any character tier on `anthropic` or `claude_cli`).
- **Severity.** LEAK (firewall: another mind's private thinking reaches a mind's decision
  input and its stored thoughts). Also STALE-DOC: `providers.py:70-76` says the trace "is
  diagnostic only: nothing downstream may treat it as content", and `mind/thoughts.py:17-20`
  says no other mind ever reads it.
- **Fix.** Clear `last_reasoning` with the other three at the start of `_chat_complete_once`
  (and `_claude_cli_complete`), and have `_sse_anthropic`/the CLI path always write it
  (`None` when nothing arrived). The class fix is for `character.py` to take the trace from
  the call it made (a per-call out-dict, as the tool round's `turn` already is) rather than
  from a context-wide "last" record. Test: set a sentinel in `last_reasoning`, run
  `_chat_complete_once` against a fake Anthropic stream, assert it reads `None`; and a
  two-mind interaction-loop test with the second tier on a fake Anthropic route asserting
  the second mind's `_holding.reasoning` is empty.

### F2 — Aborting one turn hands every embedding caller queued behind it crc32 fallback vectors (and books their spend to the wrong step)

- **Where.** `llm/providers.py:5705-5713` (`_serve_embed_group`) runs every queued
  caller's texts on the LEADER's thread and context:
  `got = _embed_with_retry(order, config)`. `_embed_request` (`5409-5413`) posts through
  `_post_abortable`, which registers the request under the leader's `cancel_event`, and
  records the batch with `record_llm_call` (`5439`) into the leader's `call_ledger_sink`.
  `_embed_with_retry` (`5797-5819`) "never raises": an `Aborted` falls through to
  `_note_embedding_fallback` and returns `cheap_embed` vectors stamped `cheap:crc32:256`.
- **Scenario.** Chat A's turn is embedding (commit's memory batch, or a retrieval query)
  and leads the coalescer; chat B's turn, or a background job (consolidation, skip
  memories — jobs clear their own `cancel_event` but still queue behind a leader), queues
  behind it. The player aborts chat A. `abort_live_requests(evA)` closes the shared request;
  the retry sees `evA` set and raises `Aborted`; the leader then serves B's queued group on
  the same aborted context. B — which nobody aborted — gets `fallback=True` vectors, and
  `embed_texts_meta`'s own docstring says what happens next: "silently replaced by a hash
  and PERSISTED under its own stamp" (keyword-only recall for those rows until a rebuild).
  On the success path the follower's batch lands on A's step ledger and B's records nothing.
  A follower's own abort is not seen until the leader returns (`waiter.done.wait(600)` does
  not poll `_check_cancel`).
- **Verified.** Snippet with a fake blocking session, two threads with copied contexts:
  ```
  abort of chat A closed 1 live request(s)
  A fallback=True model_key=cheap:crc32:256 error='generation aborted by user'
  B fallback=True model_key=cheap:crc32:256 error='generation aborted by user'
  ```
- **Confidence.** CONFIRMED (in-process simulation; the persistence step is the module's
  documented behaviour, not executed here).
- **Severity.** CORRUPTION (persisted degraded vectors for a chat that never aborted).
- **Fix.** Serve followers outside the leader's turn-scoped context (run `_serve_embed_group`
  for groups the leader is not in under a context with `cancel_event`/`call_ledger_sink`
  cleared, and record each waiter's share in its own context), and on `Aborted` hand
  leadership on (wake the queue to serve itself) instead of degrading everyone. Test: two
  threads, leader with a set cancel event, follower queued behind it, fake `_embed_request`
  that succeeds when no event is set — assert the follower's batch is not a fallback.

### F3 — A fallback candidate's outage cancels the owner-ruled fresh ask, so configuring a backup model makes a malformed beat abort

- **Where.** `llm/llm_quality.py:1969-1970`:
  ```python
  if (((malformed_seen and not provider_errored) or runaway is not None)
          and not _original_cut and last_provider_error is None):
  ```
  `last_provider_error` is set by ANY rung's provider error, including a fallback
  candidate's (`1885`). The stage then raises
  `"{step_key}: all providers failed (last provider error: ...)"` (`2118-2122`).
- **Scenario.** The primary answers malformed JSON (unmendable), the temperature-0 rebuild
  copies the slip, the configured fallback candidate's host returns 503 after its retries.
  The D5 ruling ("one fresh encoder attempt before a beat with a malformed repair aborts";
  AGENTS.md:354, Design.md:306 "Built") does not fire; the beat aborts and the message
  blames providers although the primary answered both times. Without a fallback configured
  the same beat is rescued by the fresh ask.
- **Verified.** Scripted ladder (fake `chat_complete`, step `narrator`):
  with `role_candidate_count=2` and call 3 raising `LLMError('HTTP 503 ...', 503, True)` →
  `RAISED: narrator: all providers failed (last provider error: HTTP 503: fallback host down)`,
  calls `[(0, None), (0, 0.0), (1, 0.0)]` — no fresh ask. Control with
  `role_candidate_count=1` → `accepted via fresh`.
- **Confidence.** CONFIRMED.
- **Severity.** CRASH (stage failure: a beat lost that the ladder's own rule would keep).
- **Fix.** Gate the fresh ask on the primary's provider error only (keep the fallback
  candidates' errors in a separate variable for the final message). Test: the scripted
  ladder above, asserting `answered_by == "fresh"`.

### F4 — The Writers' Room research fetch reads any http(s) address, local network included (security, not the fiction firewall)

- **Where.** `llm/research_providers.py:104-109` checks only the scheme
  (`re.match(r"^https?://", url, re.I)`), then `_fetch_html` (`165-170`) issues
  `_session().get(url, ..., stream=True)` with requests' default redirect following.
  `story/room_research.py:285` documents `fetch_page` as "Read one page the search
  returned", but nothing checks that the address came from a search result.
- **Scenario.** Under a granted `research` mandate the Room's model — or text injected into a
  page or snippet it read — asks `fetch_page("http://127.0.0.1:8181/...")` (the owner's own
  embedding host), `http://192.168.x.x/...`, or, on a hosted instance on a cloud VM,
  `http://169.254.169.254/...`; or a public URL that 302s there. The body is read, returned
  into the Room's model context (a third-party provider) and can be filed as `web_reference`
  lore. The engine's own API is mostly cookie-gated (`request_is_local` gates only first-run
  setup), so the exposure is other local services and cloud metadata.
- **Verified.** Traced `fetch_page → rp.fetch → _adapter().fetch → _fetch_html → _session().get`;
  no host/IP check, redirects not disabled. Not executed against a live address.
- **Confidence.** CONFIRMED (code path); exposure depends on deployment.
- **Severity.** LEAK — security (host/network data leaves the machine), listed separately
  from firewall leaks.
- **Fix.** Refuse loopback/private/link-local/reserved destinations after DNS resolution and
  on every redirect hop (or `allow_redirects=False` with validated manual follow), and/or
  accept only addresses present in this story's cached search results, which is what the
  docstring promises. Test: `fetch("http://127.0.0.1:1/")` raises `ResearchError`; a fake
  302 to `169.254.169.254` is refused.

### F5 — Nothing in code keeps hosted or guest play off the `claude_cli` backend

- **Where.** `llm/providers.py:4395-4399` dispatches any role whose provider row says
  `kind == "claude_cli"` to `_claude_cli_complete` unconditionally; `web/app.py:3319-3324`
  (`add_provider`) accepts any kind; the only barrier is help text
  (`static/js/settings.js:1980`, "A hosted instance that serves other people must not route
  their play through your login"). `web/auth_routes.public_mode()` exists and is not
  consulted; `web/app.py:5363-5379` (`guest_input`) files a guest's declaration for the
  host's beat, which `runtime._load_extra_players` resolves with the host's role table
  (the guest's own `narrator_extra` page included).
- **Scenario.** A host who set any role to a `claude_cli` provider for a debug run, then
  publishes the instance or invites a guest, serves other people's play on their Claude
  Code login — the owner's named violation (memory note `claude-cli-is-a-dev-backend`,
  ruling 2026-09-15). No error, no warning, no log.
- **Verified.** Traced `guest_input → _submit_player_input → host beat → chat_complete →
  _chat_complete_once:4395`; grep found no `public_mode`/guest check on the CLI path.
- **Confidence.** CONFIRMED by trace (not executed).
- **Severity.** POLICY (none of the brief's classes fits; the owner's ruling is the standard).
- **Fix.** Refuse the CLI dispatch with a typed error when `public_mode()` is on or the
  chat has live guest grants / extra players, and hide the kind from the provider form in
  public mode. Test: in public mode a role on a `claude_cli` provider raises before
  `_claude_cli_popen` is called.

### F6 — An unset `embeddings` role inherits the default CHAT model, contrary to the UI and the test that says it never does

- **Where.** `llm/providers.py:2500-2504`:
  ```python
  primary = (models.get(role)
             or models.get(ROLE_FALLBACKS.get(role, ""))
             or models.get("default"))
  ```
  applies to `"embeddings"` like any role. The panel promises the opposite
  (`static/js/settings.js:2817` "embeddings ... is never inherited", `2826` "leave it unset
  and the engine falls back to a local hash", `2986-2991` "`embeddings` may NEVER follow
  Default"), and `tests/test_provider_fallbacks.py:40-42` skips embeddings with the comment
  "A different KIND of model; never inherited" — so no test checks the server.
- **Scenario.** A host follows the panel and leaves embeddings unset with `default` on a
  chat model. `embedding_model_key()` returns `openrouter:<id>:z-ai/glm-5.3`; every
  `embed_texts_meta` call POSTs `/embeddings` with the chat model, gets a 4xx (not
  retryable, not connect-dead, so `_EMBED_DEAD` never short-circuits it), logs a fallback
  warning and returns crc32 vectors. On the turn path that is one failing round trip per
  retrieval query and per commit batch, forever. `embedding_bank_status`
  (`mind/memory_vectors.py`) sees a configured key, so the panel reports "the configured
  embeddings model did not answer" instead of "no embeddings provider is set".
- **Verified.** Snippet on a scratch DB with only `default` configured:
  `embedding_model_key with embeddings unset: openrouter:1:z-ai/glm-5.3` and
  `resolve_role(embeddings) -> openrouter z-ai/glm-5.3`.
- **Confidence.** CONFIRMED.
- **Severity.** SILENT-NOOP (the documented unset behaviour is not what runs) + PERF.
- **Fix.** Do not fall back to `default` for `embeddings` in `resolve_role_candidates`
  (raise, so `embedding_model_key()` returns `cheap:crc32:256`, the documented state).
  Test: only `default` configured → `embedding_model_key() == "cheap:crc32:256"` and
  `embed_texts_meta` makes no HTTP request.

### F7 — The two "how long may this call be silent" knobs each set one of two deadlines, so neither long-work caller gets the patience it asked for

- **Where.** The streamed reader builds its watchdog from `silence_limit_override` only
  (`providers.py:3515`, `clock = _ActivityClock(limit=silence_limit_override.get())`) and its
  socket from `read_timeout_override` capped by 30 s
  (`3518`, `between = min(_request_timeout()[1], _between_tokens_limit())`). So
  `request_timeout(...)` raises the socket but not the clock, and `patient_stream(...)` raises
  the clock but not the socket.
- **Scenario.** (a) The lorebook generator wraps its call in `request_timeout(params["timeout"])`
  (`story/importers.py:2582, 2674`), the knob AGENTS.md:554 names for exactly this; on a slow
  local model whose first token arrives at 45 s the clock raises `ProviderSilent` the moment
  that token arrives, four attempts running. (b) The location pass wraps `run_planner` in
  `patient_stream(180)` only (`agents/story_planner.py:2090`); on a host that sends no
  keepalive while thinking, the socket still dies at 30 s of byte silence. The docstring of
  `_between_tokens_limit` (`471-478`) says the deadline is "never shorter than either" knob.
- **Verified.** Snippet:
  `patient_stream(180): socket before first token (30, 30.0) | socket after first token 30.0 | clock first/limit 180.0 180.0`;
  `request_timeout(600): socket before (30, 600.0) | after 600.0 | clock first/limit 30.0 10.0`;
  and under `request_timeout(600)` a fake clock at t=45 s →
  `ProviderSilent provider silent for 45s (before any token)`.
  `tests/test_lore_gen_resume.py:868-884` checks only `_request_timeout()`, so it passes.
- **Confidence.** CONFIRMED.
- **Severity.** SILENT-NOOP (two documented knobs that do half of what they say).
- **Fix.** One function returns both deadlines from both overrides (first token
  `max(30, patience, read_override)`, between tokens `max(10, patience, read_override)`),
  used by the socket and the clock alike. Test: under `request_timeout(600)` a local SSE
  server (the `_serve` helper in `test_a_first_token_may_take_thirty_seconds.py`) whose
  first token comes at 35 s is answered; same for `patient_stream(180)` with no keepalives.

### F8 — A json_schema rejection is re-imposed as a fresh 24-hour suspension at every restart and never pruned (the memory note's "never heals", in the form the code has now)

- **Where.** `_note_json_schema_rejected` persists a 400 to `providers_no_json_schema`
  (`providers.py:2981-2992`, `2902-2907`). At load every stored entry becomes a NEW 24 h
  suspension (`2875-2884`, `_SCHEMA_SUSPENDED.setdefault(..., now + _SCHEMA_SUSPEND_SECONDS)`)
  — the comment scopes this to "ENTRIES WRITTEN BEFORE SUSPENSIONS EXISTED", but every new
  400 still lands in the same row. A later successful grammar call never removes the row.
  `_persist_schema_blacklist` rewrites the row from the in-process set alone, so an unrelated
  400 on another model silently drops older entries. `_json_schema_supported`'s docstring
  (`2958-2960`) says a rejection "is permanent". The verdict is keyed on
  `(provider, model)` while the evidence is one step's schema, so one step's oversized grammar
  costs every role on that model its grammar. `_SCHEMA_STALLS` (`2826`) never decays or resets
  on success, so two stalls days apart in one long `make serve` process also suspend it.
- **Scenario.** A model once 400s a grammar (a host's schema-feature limit, since fixed). On
  `make run` (restarts on every edit) or a nightly restart, every role on that model runs
  without its grammar for the next 24 h, every time, indefinitely — falling back to the
  `json_object` flag the module itself measures as worse on prose-leading prompts.
- **Verified.** Snippet on a scratch DB:
  ```
  row after 400 on A: ["1\u0000glm-a"]
  proc2 A supported? False | suspended until in h: 24.0
  after lapse A supported? True | row still: ["1\u0000glm-a"]
  proc3 A supported? False
  row after 400 on B in proc3: ["1\u0000glm-b"]
  ```
- **Confidence.** CONFIRMED.
- **Severity.** SILENT-NOOP (the healing design does not survive a restart; the record is
  free to disagree with what the provider now does).
- **Fix.** Persist each rejection with its own timestamp and rehydrate it with that expiry;
  prune the row on the first successful grammar call for the key; merge rather than
  overwrite when persisting; key the verdict on the schema (hash) as well as the model, or
  re-test per step. Test: reject, simulate two restarts and one successful schema call,
  assert the row no longer names the pair.

### F9 — Research pages without a charset header are decoded as Latin-1, so Japanese pages arrive as mojibake

- **Where.** `llm/research_providers.py:183`:
  `raw = body.decode(resp.encoding or "utf-8", errors="replace")`. For `text/*` without a
  charset, requests sets `resp.encoding = "ISO-8859-1"`, so the `"utf-8"` default is never
  reached.
- **Scenario.** A Japanese story's Room fetches a UTF-8 page that declares its charset only in
  `<meta charset>`. The text becomes `æ¥æ¬èªã®ãã¼ã`, is cached for 30 days, returned to
  the Room and can be filed as `web_reference` lore.
- **Verified.** `.venv` requests 2.32.4:
  `get_encoding_from_headers({'content-type':'text/html'}) -> 'ISO-8859-1'`, and
  `'日本語のページ'` decoded that way → `æ¥æ¬èªã®ãã¼ã`.
- **Confidence.** CONFIRMED (mechanism); occurrence depends on the site's headers.
- **Severity.** CORRUPTION (garbled text cached and fileable as lore; a language-pack hazard).
- **Fix.** Use the header charset only when the header names one; otherwise sniff the BOM /
  `<meta charset>` or `resp.apparent_encoding`, trying UTF-8 first. Test: a fake `text/html`
  response with UTF-8 Japanese and no charset round-trips.

### F10 — A malformed tool-history 400 is read as "this model refuses tools" and turns tool rounds off for the process

- **Where.** `llm/providers.py:544-549`: `return "tool" in lowered or "function" in lowered`
  over the provider's error text; used at `4516-4527` to add `(provider, model)` to
  `_NO_TOOLS` for the life of the process. The comment two lines above (`4519-4522`) says a
  400 about "a malformed message -- is this beat's failure, and the next beat may look things
  up again".
- **Scenario.** A later tool round's history is malformed (a tool result whose
  `tool_call_id` matches no call — the kind of slip the index-0 merging in
  `_merge_tool_call_deltas` exists to avoid). An OpenAI-style host answers `400 "messages with
  role 'tool' must be a response to a preceeding message with 'tool_calls'"`. The predicate
  sees "tool", and that model never gets a tool round again until restart.
- **Verified.** Snippet: `_names_tools` on that error string → `True`; on a `max_tokens`
  error → `False`.
- **Confidence.** CONFIRMED (predicate); PLAUSIBLE (that such a history 400 occurs live).
  False-positive rate unmeasured — per the owner's rule, measure before cutting.
- **Severity.** SILENT-NOOP (the agentic-character lookups switched off without a beat
  saying why).
- **Fix.** Remember the refusal only when the error names the request's tool FIELDS
  (`tools`, `tool_choice`, `functions` as parameters, or a structured `param` naming them),
  never a `messages[...]` validation error. Test: that 400 leaves `_NO_TOOLS` empty.

### F11 — After a failed field patch, the rebuild is handed the patched object with the unpatched object's error list

- **Where.** `llm/llm_quality.py:1718-1737`: when the targeted patch does not validate,
  `previous_parsed = _patched` (`1733`) but `report` keeps the ORIGINAL errors; then
  `_original, _original_errors = previous_parsed, list(report.errors or [])` (`1737`) and the
  rebuild payload sends `"previous_parsed_output": previous_parsed` with
  `"validation_errors": report.errors` (`1745-1752`). `_unshrunk` (`1106-1140`) then prunes the
  pre-patch error paths from the patched object.
- **Scenario.** The answer fails on fields X and Y; the patch fixes X and leaves (or breaks)
  Y. The rebuild model is told X is wrong in an object where X is right and is not told about
  anything the patch broke; if the rebuild comes back thinner, `first_pruned` deletes the
  repaired X from the kept answer.
- **Verified.** Traced the four assignments; not executed.
- **Confidence.** PLAUSIBLE.
- **Severity.** WRONG-SCENE (low: a repair steered by stale errors).
- **Fix.** Move `report = _patched_report` together with `previous_parsed = _patched` (or keep
  the unpatched object for the rebuild), so object and errors stay one pair. Test: scripted
  patch that fixes path A and breaks path B; assert the rebuild payload's errors name B.

### F12 — The degenerate-output guard never sees reasoning, so a looping trace runs to the token ceiling

- **Where.** `OutputGuard` is fed only through `_guarded_sink` (`providers.py:775-782`), which
  wraps the CONTENT sink; reasoning deltas go to `reasoning += _r` and `_think_sink(_r)`
  (`3568-3575`) and to the activity clock, which counts them as healthy activity.
- **Scenario.** A thinking model locks into "Wait, let me reconsider..." in its trace. The
  clock is satisfied, the guard is never consulted, and the call bills reasoning until
  `max_tokens` (20,000 by default, more after an escalation), then usually ends as
  `ReasoningBudgetExhausted` and is retried.
- **Verified.** Traced both sinks in `_sse_openai`; not executed.
- **Confidence.** CONFIRMED (by trace).
- **Severity.** PERF (cost and wall-clock on a failure mode the guard exists for).
- **Fix.** Feed reasoning deltas to a second `OutputGuard` per stream (same battery).
  Test: fake stream of 2,000 identical reasoning fragments → `DegenerateOutput`.

### F13 — A host's reasoning `off` silently becomes `low` for the rest of the process

- **Where.** `providers.py:1836-1852` (`_sse_with_reasoning_fallback`) and `1459-1470`
  (the beside write) add the pair to `_REASONING_MANDATORY` with no log line; thereafter
  `_apply_reasoning_effort` (`1855-1878`) swaps `off` for `low` silently. Every sibling memo
  in the module says itself once (`_note_json_object_rejected`, `_note_json_schema_rejected`,
  `_warn_unsent_on_anthropic`, whose docstring is "Saying that a set dial is inert is not
  [the owner's to decide]").
- **Scenario.** The encoder's measured `off` default (102-198 s at `high` vs 3-11 s off,
  `ROLE_DEFAULT_EFFORTS` note) runs at `low` after one refusal; turns slow and the cause is in
  no log, only in a capture's `request_shape`.
- **Verified.** Read; no `_logger` call on either path.
- **Confidence.** CONFIRMED.
- **Severity.** SILENT-NOOP (low).
- **Fix.** Log once per pair, as the JSON-mode memos do. Test: `caplog` sees one line after a
  scripted "cannot be disabled" 400.

### F14 — The call ledger's `in` means two different things by dialect, and reasoning tokens are not on it

- **Where.** `_normalize_usage` (`providers.py:4145-4178`, "One shape from either provider
  dialect") reads `prompt_tokens` (OpenAI-compatible: INCLUDES cached tokens) or
  `input_tokens` (Anthropic native and the CLI: EXCLUDES cache reads and writes) into the same
  `input`; `_log_usage` writes it as `in` (`4284-4292`) beside `cached`. The drawer renders
  `in N (M cached)` (`static/js/chat.js:2052-2054`). `_reasoning_tokens(usage)` is computed for
  `last_output_spend` but not put on the entry.
- **Scenario.** An Anthropic-native call with a 15k cached prefix shows `in 120 (15000 cached)`
  where the same call through OpenRouter shows `in 15120 (15000 cached)`; any bill computed as
  `(in - cached) * input + cached * read` goes negative on the first. The owner prices turns
  from these records (memory note "Turn cost bill").
- **Verified.** Read; Anthropic's usage semantics are the documented API's.
- **Confidence.** CONFIRMED by reading.
- **Severity.** CORRUPTION (diagnostic ledger only, low).
- **Fix.** Normalise `input` to the inclusive total (Anthropic: input + cache_read +
  cache_write) and add `reasoning` to the entry. Test: an Anthropic usage block and its
  OpenAI-shaped equivalent normalise equal.

### F15 — Capture rows record `requested: ""` for every role that follows `default`, and the primary model for a fallback's answer

- **Where.** `llm/llm_quality.py:873`:
  `"requested": str((providers.agent_models().get(role) or {}).get("model") or "")`.
- **Verified.** Snippet with `agent_models = {default, narrator(+fallback)}`:
  `[('repair', ''), ('narrator', 'narr-model')]` — `repair` follows default and records
  nothing; a fallback candidate's rebuild row would name `narr-model`, not the backup.
- **Confidence.** CONFIRMED.
- **Severity.** CORRUPTION (debug capture only, low).
- **Fix.** Record the model the call actually resolved (the `_log_usage` entry already has
  `requested`/`served`). Test: a role following default records the default's model.

### F16 — `_chat_complete_once`'s blocking OpenAI branch is unreachable

- **Where.** `providers.py:4380` `streaming = bool(raw_sink) or prov["kind"] != "anthropic"`,
  after the CLI and Anthropic branches have returned, so `streaming` is always True and
  `4649-4725` (the blocking 400 ladder, the blocking placeholder re-ask, `_capture_reasoning`,
  `_message_content`) never runs. `_message_content` (`4814-4843`) and `_capture_reasoning`
  (`253-266`) are reachable only from it and from the registered-dead async path. The comment
  at `3557-3565` still says the non-streaming branch "serves almost nothing".
- **Consequence beyond dead code.** Nothing in the recovery ladder can drop `stream` or
  `stream_options` (`_sse_openai` re-adds both on every rung, `3491`, `3498`), so a host that
  400s on `stream_options` now has no path at all; the blocking branch that never sent it is
  the dead one. Which hosts do that is unmeasured (PLAUSIBLE).
- **Verified.** Snippet: `_chat_complete_once` for `kind="openai"` with no token sink, with
  `_post_abortable` replaced by an assertion → `(b) openai no-sink -> {"ok": 1} ['stream']`.
- **Confidence.** CONFIRMED.
- **Severity.** DEAD.
- **Fix.** Delete the branch and the two helpers' only callers (or turn the blocking send into
  a ladder rung for a host that refuses streaming). No test needed for the deletion.

### F17 — The timeout comments still describe the 90-second read and the blocking POST

- **Where.** `providers.py:282-287` ("90s is chosen against time-to-first-byte"),
  `332-333` (`HTTPX_TIMEOUT` read 90 is "the async path's twin of REQUEST_TIMEOUT's read half"),
  `340-341` ("`REQUEST_TIMEOUT`'s 90s INTER-CHUNK read" — the comment that itself records
  fixing a stale number, E7), `438-452` ("REQUEST_TIMEOUT's 90s is reasoned entirely..."),
  `819-820` ("`REQUEST_TIMEOUT`'s 90s between chunks on a stream"). `REQUEST_TIMEOUT` is
  `(30, PROVIDER_FIRST_TOKEN_SECONDS)` = 30 s (`310`), narrowed to 10 s after the first token.
  AGENTS.md:554 still calls `HTTPX_TIMEOUT` a pipeline default; it serves only the dead async
  path.
- **Confidence.** CONFIRMED. **Severity.** STALE-DOC.
- **Fix.** Rewrite to the current split (30 s before the first token, 10 s between, socket
  narrowed at first token; the blocking POST now serves only native Anthropic without a sink,
  the beside write and embeddings).

## Efficiency

1. **The degenerate-output guard's short-loop regex is most of its cost, held under the GIL,
   on every streamed call.** `providers.py:605` `(.{2,23})\1{80,}` is searched over a 4 KB tail
   every 200 new characters (`OutputGuard.feed`, `672-747`). Measured (`.venv`, pure CPU):
   guard total 0.42 s per 20k streamed characters, 1.24 s / 60k, 3.02 s / 140k; per 700 strides
   the short-loop regex alone is 2.41 s against 0.12 / 0.06 / 0.10 / 0.01 s for the other four
   rules. An end-anchored slice test (`tail[-81p:] == tail[-p:]*81` for p in 2..23, the same
   philosophy as `_repeating_period`) took 0.0074 s for the same 700 strides (~300x) and still
   catches a live loop. Hot: every OpenAI-style call (all are streamed); roughly 0.1-0.4 s of
   GIL-held CPU per ordinary call, seconds on long pages, contending with parallel character
   streams. Cheap fix, large gain.
2. **A fresh TCP+TLS connection per step thread.** `_session()` (`providers.py:323-329`) keeps
   one `requests.Session` per THREAD, and the pipeline makes a new thread per step
   (`agents/runtime.py:654-657`, `720-721`) and new `ThreadPoolExecutor`s per call
   (`director_prose`, `director_repair`, `background`, `decisions`, `memory_links`), so most
   calls open a new connection. The owner measured the cost on OpenRouter: 0.295 s fresh vs
   0.248 s kept alive, ~0.05 s a request (`llm/decisions.py:129-140`). Fix: mount ONE shared
   `HTTPAdapter` (urllib3 pools are thread-safe) on every thread's Session. Gain ~0.05 s ×
   the beat's fresh-thread calls (tens), part of it on the critical path. Cheap.
3. **An unset embeddings role pays a failing round trip per embedding call** (F6): one 4xx per
   retrieval query and commit batch, on the turn path, forever. Cheap fix (do not inherit
   `default`), gain = every such round trip.
4. **Settings re-read per call.** One `chat_complete` reads about nine settings rows
   (`max_output_tokens`, `agent_models`, `response_format`, `reasoning_effort`,
   `openrouter_routing`, `service_tier`, `cache_affinity_allow`, `prompt_cache_deny/allow`
   where applicable) plus 1-2 `providers` rows and ~4 `json.loads`; `note_provider_exchange`
   re-reads and re-parses `agent_models` for every exchange even with capture off
   (`llm_quality.py:873`). `get_setting` is uncached (`core/db.py:2982`). Sub-millisecond each in
   WAL; low gain, cheap (one snapshot per call).
5. **Reasoning loops are not guarded** (F12): cost bounded only by `max_tokens`.
6. Minor: `research_providers._fetch_html` never closes its streamed response (`165-188`),
   leaving the connection to garbage collection on every early return and after the byte cap.

## Already registered

- **`providers.chat_complete_async` is dead** — `docs/UNBUILT_PARKED.md` (bullet "providers.
  chat_complete_async is dead"). Still true; the dead half also includes
  `_chat_complete_async_once`, `_sse_openai_async`, `_sse_anthropic_async`, `_httpx_timeout`,
  `HTTPX_TIMEOUT` (`providers.py:330-336, 510-515, 4846-5195`), ~360 lines, kept alive only by
  tests (`tests/test_claude_cli_provider.py:408`, `test_usage_telemetry.py:179-187`,
  `test_reasoning_sink.py`). It has also drifted from the sync path (no common prompt policy, no
  language scaling, no reasoning-only remedy, no activity clock, no stall ladder), so it is not
  a usable fallback. The register's "only three references in the tree" undercounts the tests.
- **`llm/prompt_cache.py` is dead** — `docs/UNBUILT_PARKED.md`. Still true (no importer). Stale
  references beyond the AGENTS.md one the register names: `docs/guides/ENGINEERING.md:708`
  ("`llm/prompt_cache.py` places cache breakpoints"), `Design.md:1188`, and
  `agents/narration.py:2733` (cites `add_cache_breakpoint` as the live mechanism; its
  conclusion still holds because the narrator sends no `cache_user`).
- **A failed attempt leaves no ledger trace** — `docs/UNBUILT_PLATFORM.md` §1.171. Still true:
  `_log_usage` runs only on success paths, so killed runaways, silences and aborts are
  absent from `call_ledger_sink`.
- **The restart reader has no cut-off guard outside the ladder** — `docs/UNBUILT_PIPELINE.md`
  §1.214. Re-confirmed: `strict_json_parse('{"entries":[{"a":1},{"b":2}')` → `{'b': 2}`,
  silently (the `restarted` note is only said when `goes_on`). Callers:
  `world/charter_generate.py:367`, `mind/memory_judge.py:136`, `mind/memory_summaries.py:470`,
  `mind/skip_memories.py:634`, `agents/common.py:4131`.
- **JSON validation stalls cost beats** — `docs/UNBUILT_PIPELINE.md` §1.7, with its residuals in
  §1.196. What is still true in `complete_validated_json`: an answer that PARSES and fails
  validation, whose field patch and rebuild also fail, is never asked afresh (by the documented
  design, owner's call) and the stage raises `RuntimeError`, losing the beat; only three rungs'
  malformed answers are mended locally; the capture does not name a row's rung. New beside it:
  F3 (a fallback's outage also cancels the malformed-answer fresh ask).
- **The json_object drop does not survive a restart; a silent formatless rung restarts from
  the grammar** — `docs/UNBUILT_PLATFORM.md` §1.186. Still true (`_NO_JSON_OBJECT` is
  process-local; the ladder re-raises a non-400 at `providers.py:4621-4622`). F8 is a different
  defect in the same family.
- **The 30 s first-token clock caps a thinking model whose host does not stream reasoning** —
  `docs/UNBUILT_PIPELINE.md` §1.187a (item 3). Still true.
- **Research is grantable and unmeasured** — `docs/UNBUILT_PLANNING.md` (the "Research is
  grantable" bullet). F4 and F9 are not in it.

## Structure notes

**Monoliths in miniature.** `llm_quality.complete_validated_json` (`1143-2132`, ~990 lines, one
function threading ~15 mutable locals — `provider_errored`, `last_provider_error`, `runaway`,
`malformed_seen`, `any_parsed`, `ran_out_of_room`, `ran_away`, `token_ceiling`,
`previous_raw/parsed`, `report`, `_original`, `_original_cut`, `_asked` — through ten rungs; F3
and F11 are both products of that threading). `providers._chat_complete_once` (395 lines),
`chat_complete` (180), `_claude_cli_complete` (130), `_sse_openai` (118).

**Natural seams in `providers.py`** (a split needs the `persist.commit`-style facade and the
patch-the-defining-module rule: 251 monkeypatch sites and 161 attribute uses go through the
module object): (1) per-context call records and sinks, `33-266`; (2) timeouts, the activity
clock and the output guard, `268-925` + `3387-3437`; (3) request shaping — cache, affinity,
routing, tiers, effort, output ceiling, `980-2020`; (4) the role table and resolution,
`2022-2580`; (5) JSON-mode capability memory and its persistence, `2582-3350`; (6) transports —
`_sse_openai`, `_sse_anthropic`, the CLI, `3440-3954`; (7) orchestration, `3957-4725`;
(8) usage and ledger, `4138-4329`; (9) images and model listing, `2139-2368`, `5197-5292`;
(10) embeddings — pacing, dead-endpoint memory, coalescing, `5294-5849`; (11) the dead async
half, `4846-5195` (delete). `llm_quality.py` splits into the JSON reader (`1-450`), the field
patch (`514-686`), schema-on-the-wire (`719-827`), capture (`829-897`) and the ladder.

**Module-level mutable state and its writers** (46 in the anatomy, plus three it does not list):

| State | Kind | Writers | Shared across chats? | Note |
|---|---|---|---|---|
| `token_sink`, `generation_event_sink`, `reasoning_sink`, `call_ledger_sink`, `cancel_event` | ContextVar | `agents/runtime.py` per step / run; importers; the Room | no (per context) | cleared for jobs by `core/jobs._clear_turn_scoped_context` |
| `last_reasoning` | ContextVar | `_sse_openai:3588`, async `5140`, CLI `3941` (only if non-empty), `_capture_reasoning` (dead path), `agents/character.py:4899` | no | NOT cleared per completion; NOT cleared for jobs (F1) |
| `last_finish_reason`, `last_request_shape`, `last_output_spend` | ContextVar | `_capture_finish_reason`, `_note_request_shape`, `_log_usage` | no | cleared at each completion's start (`4355-4357`); not cleared for jobs (harmless: the job's first call clears them) |
| `read_timeout_override`, `silence_limit_override` | ContextVar | `request_timeout`, `patient_stream` context managers | no | not in the jobs denylist: a job submitted inside one inherits the patience (F7 family) |
| `_NO_TOOLS`, `_BESIDE_REFUSED`, `_REASONING_MANDATORY` | set, no lock | `_chat_complete_once:4523`; beside thread `1474`; `1466`, `1848` | yes (provider facts) | process-permanent; atomic `add` under the GIL |
| `_NO_JSON_OBJECT`, `_JSON_OBJECT_HELD_BACK`, `_NO_JSON_SCHEMA`, `_SCHEMA_STALLS`, `_SCHEMA_SUSPENDED` | set/dict + lock | `_note_json_*`, `_load_schema_blacklist` | yes | counts never decay; schema verdicts persisted (F8) |
| `_LIVE_REQUESTS` | dict keyed by Event + lock | `_abortable`, `abort_live_requests` | keyed per run | correct isolation |
| `_PREFIX_WRITTEN` | dict + lock | `_claim_prefix_write` & co. | yes (per prefix) | TTL 300 s |
| `_UNSENT_ON_ANTHROPIC`, `_SERVED_SEEN` | set/dict + lock | say-once memos | yes | |
| `_EMBED_PACE`, `_EMBED_DEAD` | dict + lock | pacer, dead-endpoint memory | yes | one unlocked read of `_EMBED_DEAD["key"]` in `_embed_with_retry` (benign) |
| `_COALESCE_QUEUE` + `global _COALESCE_INFLIGHT` | list/bool + lock | `_coalesced_embed` | yes | leader serves everyone on its own context (F2) |
| `_EMBED_STATS`, `_EMBED_FALLBACK_SAID` | dict | coalescer (partly outside the lock), fallback log | yes | diagnostic; lost increments possible |
| `_thread_local` | threading.local | `_session` | per thread | Efficiency 2 |
| `_json_schema_supported._loaded` | function attribute | first call | process | a failed first load is never retried |
| `DEFAULT_BASES`, `DEFAULT_SAMPLERS`, `_NOOP`, `ROLES`, `RENAMED_ROLES`, `ROLE_FALLBACKS`, `ROLE_DEFAULT_EFFORTS`, `ROLE_DEFAULT_FORMATS`, `CLAUDE_CLI_EFFORTS`, `DEFAULT_RETRY` | mutable literals / dataclass | none in production (grepped) | — | `PROMPT_CACHE_ENABLED`, `_claude_cli_popen`, `_run_beside` are rebound by tests only |
| `llm_quality._SCHEMA_CACHE`, `llm_quality.answered_by` | dict / ContextVar | `_step_json_schema`; `_accepted` | — | `answered_by` is set on success only; its one reader resets it first (`director_prose.py:3924`) |
| `research_providers.OVERRIDE` | test seam | tests | — | |

**`global` statements.** One in the four files: `global _COALESCE_INFLIGHT`
(`providers.py:5730`), a bool that no module imports by name (tests read it through the module),
so no importer holds a stale object. No production code imports any cache, flag or override by
name; the ContextVar objects imported by name (`last_reasoning` ×8, `token_sink` ×7, ...) are
never rebound.

**Answers to the assignment's nine questions, in brief.**

1. *Concurrency.* The eleven per-call values are ContextVars, not plain globals, so two
   overlapping calls on different threads never see each other's values; `copy_context()` fans
   out inward only, and the runtime carries `last_reasoning` back out by hand. The real hazards
   are within ONE context: the four "last call" records are "the last call on this thread", and
   `last_reasoning` alone is not cleared per completion — F1. Readers that depend on "the last
   call's": `response_truncated`/`answer_ran_away` (the ladder, read right after each call —
   correct), `request_shape` and `last_reasoning` for the capture, the step's stored trace, the
   Room's capture, and the character's decision read-back and kept thoughts (F1). Cross-chat
   coupling exists only through the process-wide provider verdicts (intended) and the embedding
   coalescer (F2).
2. *Cancellation.* One Event per pipeline run, in that run's context; `_LIVE_REQUESTS` is keyed
   by the Event, so aborting chat A closes only A's sockets; jobs clear the Event; the beside
   write and the ponder pool inherit their caller's Event on purpose. The exception is the
   embedding coalescer, where an abort crosses chats (F2).
3. *Retries and timeouts.* `DEFAULT_RETRY`: 3 retries, equal-jitter backoff 1-30 s, statuses
   429/5xx, `ProviderSilent` and runaways retryable (runaways at once). Retries resend the
   identical body — no seed, same temperature — except the documented, announced changes
   (reasoning `off` after a reasoning-only reply, next candidate after two, the 400 ladder's
   field drops, the placeholder re-stream without a format) and the silent `off`→`low` swap
   (F13). The clock counts reasoning and tool-argument deltas as activity and keepalives as
   silence, as ruled; the overrides are split (F7); the degenerate guard ignores reasoning
   (F12). `_should_retry` reads `error.retryable`, which is computed from `DEFAULT_RETRY`'s
   statuses at every raise site, so a caller's narrower `retryable_status` cannot make a 5xx
   non-retryable (no caller does today).
4. *The json_schema blacklist.* Lives in `_NO_JSON_SCHEMA` (400s, persisted to
   `providers_no_json_schema`) and `_SCHEMA_SUSPENDED` (2 stalls → 24 h, persisted with expiry
   to `providers_schema_suspended`), keyed on (provider, model) — not on role. The memory note's
   "2 timeouts, never heals" is stale for stalls: since the healing change the suspension
   expires, documented design. The 400 path is the accident: permanent within a process, a fresh
   24 h at every restart, never pruned (F8). Gemini never gets a grammar by ruling (`2972`).
   `DegenerateOutput` is language-neutral (character-level whitespace, repetition, period and
   control rules); the only English-shaped number is `_approx_tokens`' 4 characters a token,
   used in a diagnostic sentence (`_reasoning_only_error`), which under-reads a Japanese trace
   about threefold.
5. *Cost accounting.* Ledger entries carry `in/out/cached`, `written` when non-zero, tier asked
   and served. Reasoning is inside `out` (billed correctly) but not split out; `in` changes
   meaning by dialect (F14); failed attempts are missing (§1.171); follower embeddings are booked
   to the leader's step (F2).
6. *Streams.* Tool-call fragments merge by id first, then index (NanoGPT's index-0 whole calls
   handled). `finish_reason=length` is captured into `last_finish_reason` and neither raised nor
   logged: the ladder reads it, direct `chat_complete` callers that parse with
   `strict_json_parse` do not (§1.214). A stream that ends without `[DONE]` or a finish reason
   is returned as complete, and any line that fails `json.loads` is dropped without a count (a
   host writing `data:{...}` with no space after the colon, legal SSE, would yield empty answers
   and a misleading "invalid JSON at position 0"). The Anthropic reader never checks
   `message_stop` and never captures thinking (part of F1).
7. *`complete_validated_json`.* §1.7 as above; F3, F11. Content-dropping rungs are said aloud
   (`_read_answer` notes, `_unshrunk`'s warning, `_accepted`'s validation warnings); the field
   patch is the one rung not size-checked by `_unshrunk` (it touches only failing paths, so the
   loss is bounded to them). The fallback rung passes `sampler=sampler` with
   `temperature=0.0`, and `_merge_samplers` lets a sampler-carried temperature win, so a card
   whose `simulation.sampler` names a temperature rebuilds at it rather than at 0 (the rebuild
   rung omits the sampler entirely).
8. *`claude_cli`.* No role-table default reaches it (`agent_models` is host-set) and the panel
   warns, but nothing in code stops hosted or guest play from using it — F5.
9. *Efficiency.* At the provider layer the stable system card goes first (common policy
   appended, cache-marked where honoured), the per-beat payload second, history after; nothing
   volatile precedes the card here — whether each role's card string is itself stable is the
   callers'. `ROLES` is not consulted per call; `resolve_role_candidates` is, with a settings
   read and provider queries each time (Efficiency 4). Serialisation per retry is once per POST
   (necessary); the beside write deep-copies the body once.

**Outside my files, found in passing (route to their owners).**

- `persist/commit_memory_write.py:64-70` runs `parent.run(...)` for every cast member from a
  thread pool on ONE `Context` object; concurrent `Context.run` on the same object raises
  `RuntimeError: cannot enter context ... is already entered` (reproduced with three threads).
  Reached only by `commit_memories(..., consolidate=True)`, the default argument, which the live
  commit never passes (`persist/commit.py:631-633` passes `False`) — latent, test-only today;
  `tests/test_memory_consolidation_parallel.py` passes only because its fakes return at once.
- `world/offscreen.py:1553-1560` says a job thread "starts with a FRESH contextvars context";
  `core/jobs.submit` copies the submitting context (`jobs.py:130`) and clears the turn-scoped
  half. STALE-DOC.

## Docs checked

| Claim | Where | Held? |
|---|---|---|
| Provider behaviour's watch-file is `llm/prompt_cache.py` | AGENTS.md:552 | STALE (registered, UNBUILT_PARKED) |
| Both cache paths ask the same predicate | AGENTS.md:553, ENGINEERING.md:709 | HELD (`_anthropic_system` checks `_cache_denied`; `_openai_system_message` checks `_cache_passthrough_allowed`, which checks deny first) |
| The lorebook generator's `timeout` is the per-call knob; `REQUEST_TIMEOUT`/`HTTPX_TIMEOUT` stay the pipeline default | AGENTS.md:554 | FAILS — the knob does not reach the activity clock (F7); `HTTPX_TIMEOUT` serves only the dead async path |
| Per-call cost via `call_ledger_sink`/`record_llm_call` | AGENTS.md:559 | HELD with caveats (failed attempts §1.171; dialect F14; coalescer F2) |
| Empty `{}` re-asked once; mend before a model; early-closed objects mended on every rung | AGENTS.md:336-353 | HELD (traced `1442-1489`, `1426-1440`, `_read_answer`) |
| A malformed failure is asked afresh `MALFORMED_REASKS` times unless the request's own answer was cut | AGENTS.md:354, Design.md:306 ("Built") | PARTIAL — also skipped whenever any rung had a provider error, including a fallback candidate's (F3) |
| `last_output_spend` cleared at every completion's start; runaway re-ask at the same budget | AGENTS.md:355, Design.md:308 | HELD (`4357`, `4954`; `answer_ran_away`) |
| A cut-off answer is never read by salvage | Design.md:514 | HELD inside the ladder; outside it §1.214 (registered) |
| The rebuild never repairs by deleting | Design.md:517 | HELD for rebuild and fallbacks; the field patch is not size-checked (bounded to failing paths) |
| Research: query and address written to the thread before leaving the machine | Design.md:400 | HELD (`_disclose` precedes `rp.fetch`); the address is not restricted (F4) |
| Provider layer includes `llm/prompt_cache.py` | Design.md:1188, ENGINEERING.md:708 | STALE (registered module; these two references are not named in the register) |
| "A stage that cannot produce valid output raises rather than silently substituting" | ENGINEERING.md:704-706 | HELD (`RuntimeError` at `2118-2133`) |
| `last_reasoning` "is diagnostic only: nothing downstream may treat it as content" | providers.py:70-76 | FAILS — `agents/character.py:4888` feeds it to the decision model and kept thoughts (F1) |
| "No other mind ... ever reads it, as no other reader ever read `last_reasoning`" | mind/thoughts.py:17-20 | FAILS under F1's configuration |
| `_between_tokens_limit` is "never shorter than either" knob | providers.py:471-478 | FAILS at its call site (`min(..., 30)`), F7 |
| A json_schema REJECTION "is permanent" | providers.py:2958-2960 | FAILS — permanent within a process, a renewable 24 h suspension across restarts (F8) |
| `_capture_finish_reason` is called with None at the start of every completion | providers.py:122-126 | HELD (`4355`, `4952`) |
| `embeddings` "is never inherited" / unset falls back to the local hash | settings.js:2817, 2826, 2986-2991; tests/test_provider_fallbacks.py:40-42 | FAILS on the server (F6) |
| The non-streaming branch "serves almost nothing" | providers.py:3557-3565 | STALE — it serves nothing (F16) |
| Timeout numbers (90 s) in five comments | providers.py:282-287, 332-333, 340-341, 438-452, 819-820 | STALE (F17) |
| `fetch_page` reads "one page the search returned" | story/room_research.py:285 | FAILS — any http(s) address is fetched (F4) |
| Jobs start with a fresh context | world/offscreen.py:1553-1560 | STALE (outside scope) |
