"""What a character can look up while it decides (the owner, 2026-10-05).

"I was thinking of making ponder and notebook reading a tool call that
retrieves immediate results with a budget, writing being part of the output"
-- and "We can have tool calls in the reasoning block right? That could give
us a lot of room we haven't had before". A character may now look back
mid-thought: the model reasons, calls a tool, is handed what came back, and
reasons on -- native tool calls (`llm.providers`, probed on the owner's
character route NanoGPT glm-5.3:thinking: the call arrives streamed, the
reasoning carries over, and a closing round on the grammar comes back
valid). Writing stays in the answer: every lookup is read-only, and the
character step remains what it was -- a proposal commit decides.

FOUR LOOKUPS, EACH OVER THIS MIND'S OWN STORES, through the seams recall
already uses:

- `ponder(query)` -- the graded ponder lane (`memory_jev.jev_ponder_packet`),
  answered now instead of on the next beat, the memories that changed what
  came back brought with them (`memory_links.pull_successors`);
- `notebook()` -- everything it keeps (`mind.notebook.full_view`), uncapped;
- `expand(memory_ref)` -- the turns around a memory, `SPAN_TURNS` each side,
  in order: a whole conversation as this mind heard it;
- `continue(memory_ref, before|after)` -- `SPAN_TURNS` more turns on either
  side of a memory.

What comes back is delivered as recall's own rows are: projected by
`memory_context._with_reading`, named by the wire's `m<n>` handles, walked
for citation grounding (a `looked_up` lane), offered to the read-back (so a
dispute can target the exact memory it re-reads), and counted as reached.
A firewall read and nothing else: `visible_memory_rows` -- this mind's rows,
this frame's, from before this turn.

THE PREFIX NEVER CHANGES BETWEEN ROUNDS: the same system card, the same
packet, the same tools, history only appended -- so with the replica hint
(`providers._apply_cache_affinity`) every round after the first reads the
whole packet from the provider's cache (measured: 5,515 of 5,870 prompt
tokens, 8.1 s against 33 s uncached).
"""

from __future__ import annotations

import json
import time

from core.db import get_setting

#: Lookups one character may make in one beat -- the owner's five, counted
#: across the micro-rounds of an interaction loop.
TOOL_BUDGET = 5
#: Turns `expand` brings back on each side of a memory, and `continue` on --
#: the owner's five.
SPAN_TURNS = 5
#: Seconds the lookups may take before the character must answer; the
#: closing round always runs after them. Named to the owner.
TOOL_WALL_SECONDS = 60
#: Characters of one lookup's result handed back. A turn's memory runs ~950
#: at the median, ~1,800 at p90, so a full expansion is ~10k (measured on the
#: owner's banks, 2026-10-05). Named to the owner.
RESULT_CHARS = 16000

TOOL_NAMES = ("ponder", "notebook", "expand", "continue")


def tools_enabled(role) -> bool:
    """Whether `role` may look things up mid-thought: the `character_tools`
    setting, a comma list of roles (`character_major`); unset, none."""
    raw = str(get_setting("character_tools") or "")
    return str(role or "") in {p.strip() for p in raw.split(",") if p.strip()}


def route_takes_tools(role) -> bool:
    """Whether the role's first model is on a route that carries tool rounds
    (`providers.tools_supported`) -- the role's own card asks for nothing a
    route cannot answer."""
    from llm.providers import resolve_role_candidates, tools_supported
    try:
        prov, model, _cfg = resolve_role_candidates(role)[0]
    except Exception:  # noqa: BLE001 -- no route is no tools
        return False
    return tools_supported(prov, model)


def tool_specs(language=None):
    """The four lookups as OpenAI-style functions: names and parameters are
    protocol, the descriptions the story's pack (`character_tools`)."""
    from llm.prompts import character_tools_text

    def say(key):
        return character_tools_text(key, language)

    ref = {"type": "string", "description": say("memory_ref")}
    return [
        {"type": "function", "function": {
            "name": "ponder", "description": say("ponder"),
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": say("ponder_query")}},
                "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "notebook", "description": say("notebook"),
            "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {
            "name": "expand", "description": say("expand"),
            "parameters": {"type": "object", "properties": {"memory_ref": ref},
                           "required": ["memory_ref"]}}},
        {"type": "function", "function": {
            "name": "continue", "description": say("continue"),
            "parameters": {"type": "object", "properties": {
                "memory_ref": ref,
                "direction": {"type": "string", "enum": ["before", "after"],
                              "description": say("direction")}},
                "required": ["memory_ref", "direction"]}}},
    ]


def _order(row):
    turn = row.get("turn_idx")
    return (turn if turn is not None else -10 ** 9,
            row.get("encoded_at_seconds") or 0.0, row.get("id") or 0)


class Lookups:
    """One character's lookups for one call, over its own stores only.

    `handles` is the wire's handle -> memory_ref map
    (`character_evidence.compact_character_evidence`); lookups extend it, so
    a memory reached here is named as one in the packet is. `holding` is the
    read-back's (`character_jev.Holding`): what a lookup delivered joins its
    memories and notebook, so a dispute or a note change can name it."""

    def __init__(self, *, chat_id, char_id, turn_idx, bank, handles, memory_context,
                 memory_internal, holding, notebook_inputs, ponder_inputs, language=None):
        self.chat_id, self.char_id, self.turn_idx = chat_id, char_id, turn_idx
        self.bank = bank
        self.handles = handles if isinstance(handles, dict) else {}
        self.memory_context = memory_context if isinstance(memory_context, dict) else {}
        self.memory_internal = memory_internal if isinstance(memory_internal, dict) else {}
        self.holding = holding
        self.notebook_inputs = dict(notebook_inputs or {})
        self.ponder_inputs = dict(ponder_inputs or {})
        self.language = language
        self._key_to_handle = {v: k for k, v in self.handles.items() if str(k)[:1] == "m"}
        self._next = 1 + max((int(k[1:]) for k in self.handles
                              if str(k)[:1] == "m" and str(k)[1:].isdigit()), default=0)
        self._in_packet = self._packet_keys()
        self._rows_cache = None
        self.delivered = []        # canonical projected rows, in the order reached
        self._delivered_keys = set()
        self._read_units = set()   # what expand/continue have read, for continue
        self._projected = {}        # event_key -> the row as recall projects it
        self._clock_now = None
        self.reached_ids = []      # row ids, for the access record
        self.calls = []            # the transcript the step keeps

    # -- reading -------------------------------------------------------------
    def _packet_keys(self):
        from agents.character import _delivered_memory_rows
        rows, _summaries = _delivered_memory_rows(self.memory_context)
        return {ref for _row, ref in rows}

    def _rows(self):
        """This mind's visible rows, oldest first -- the firewall's own read
        at the beat deciding (a memo hit on the step's bank)."""
        if self._rows_cache is None:
            from mind.memory import _UNSET, _row_memory, visible_memory_rows
            # The ambient frame, as recall reads it: the lookups run on the
            # character step's own thread, in the context it decides in.
            rows = [_row_memory(r) for r in visible_memory_rows(
                self.chat_id, self.char_id, before_turn_idx=self.turn_idx,
                viewer_frame_id=_UNSET, include_archived=True, bank=self.bank)]
            self._rows_cache = sorted(rows, key=_order)
        return self._rows_cache

    def _resolve(self, ref):
        """The event_key a handle or key names, among this mind's own rows."""
        text = str(ref or "").strip()
        key = self.handles.get(text, text)
        return key if any(str(r.get("event_key") or "") == key for r in self._rows()) else ""

    def _handle(self, key):
        if key not in self._key_to_handle:
            short = f"m{self._next}"
            self._next += 1
            self._key_to_handle[key] = short
            self.handles[short] = key
        return self._key_to_handle[key]

    def _say(self, key):
        """A sentence a lookup answers with, in the story's language
        (`character_tools.<key>`); the keys around it are protocol."""
        from llm.prompts import character_tools_text
        return character_tools_text(key, self.language)

    def _clock(self):
        from mind.memory import MemoryClock
        return MemoryClock(self.chat_id, self.char_id, self.turn_idx)

    def _item(self, row):
        """`(key, projected, item)` for one row as the mind would read it now:
        projected as recall projects (the engine's form, kept for its own
        readers), and the item the model is shown -- a pointer when the row is
        already in front of it, in the packet or returned by an earlier lookup
        this call. The item's `memory_ref` is a placeholder until it is
        returned (`_returned`), so a row that never comes back mints no handle."""
        from mind.memory import _with_reading
        if self._clock_now is None:
            # Read once, when a lookup first needs it: a mind that never
            # looks anything up never pays for it.
            self._clock_now = self._clock()
        key = str(row.get("event_key") or "")
        if key not in self._projected:
            self._projected[key] = _with_reading(
                row, self._clock_now, set(self.ponder_inputs.get("known") or ()))
        projected = self._projected[key]
        held = key in self._in_packet or key in self._delivered_keys
        ref = self._key_to_handle.get(key) or "m0"
        item = ({"memory_ref": ref, "when": projected.get("when", ""),
                 "already_in_front_of_you": True} if held else dict(projected, memory_ref=ref))
        return key, projected, item

    def _size(self, rows):
        return sum(len(json.dumps(self._item(r)[2], ensure_ascii=False)) for r in rows
                   if r.get("event_key"))

    def _returned(self, rows):
        """The rows that come back, in order: named by handle, and delivered --
        folded, grounded, counted as reached -- only now that they have."""
        out = []
        for row in rows:
            key, projected, item = self._item(row)
            if not key:
                continue
            held = bool(item.get("already_in_front_of_you"))
            item["memory_ref"] = self._handle(key)
            out.append(item)
            if not held:
                self._delivered_keys.add(key)
                self.delivered.append(projected)
                if row.get("id") is not None:
                    self.reached_ids.append(row["id"])
        return out

    def _deliver(self, rows):
        """A ponder's rows, best first, as many as fit in `RESULT_CHARS`."""
        keep, size = [], 0
        for row in rows:
            size += self._size([row])
            if size > RESULT_CHARS and keep:
                return {"memories": self._returned(keep), "more_than_fits": True}
            keep.append(row)
        return {"memories": self._returned(keep)}

    # -- the lookups -----------------------------------------------------------
    def ponder(self, query):
        query = " ".join(str(query or "").split())[:240]
        if not query:
            return {"refused": self._say("needs_a_query")}
        from llm.providers import embed_texts_meta
        from mind.memory import jev_ponder_packet, named_in, pull_successors
        p = self.ponder_inputs
        record = {}
        picks = jev_ponder_packet(
            self.chat_id, self.char_id, query, current_turn_idx=self.turn_idx,
            embedded=embed_texts_meta([query]), here=p.get("here"),
            limit=int(p.get("limit") or 5), person=p.get("person"), view=p.get("view") or "",
            active_state=p.get("active_state") or {}, unsettled=p.get("unsettled") or (),
            language=self.language, bank=self.bank, record=record,
            about=named_in(query, p.get("known_names") or ()), known=p.get("known") or ())
        picks = pull_successors(self.chat_id, self.char_id, picks,
                                current_turn_idx=self.turn_idx, bank=self.bank)
        if not picks:
            return {"memories": [], "nothing_comes_back": True}
        return self._deliver(sorted(picks, key=_order))

    def notebook(self):
        from mind import notebook as nb
        i = self.notebook_inputs
        view = nb.full_view(i.get("state") or {}, self.turn_idx,
                            elapsed_seconds=i.get("elapsed_seconds"),
                            concerns=i.get("concerns") or (), projects=i.get("projects") or ())
        # Entries the mind saw only here join the read-back's notebook, at the
        # end of each section -- an id seen through a lookup must route as one
        # seen on the page, and inserting before would shift every index.
        shown = getattr(self.holding, "notebook", None)
        if isinstance(shown, dict):
            have = {e.get("id") for rows in shown.values() for e in rows or [] if isinstance(e, dict)}
            for section, rows in view.items():
                for entry in rows:
                    if entry.get("id") not in have:
                        shown.setdefault(section, []).append(entry)
        return nb.for_payload(view) or {"nothing_kept": True}

    def _units(self, anchor_key):
        """`(units, at, members)`: the ordered units a span is counted in and
        the anchor's place among them -- turns for a dated past; single
        memories for a seeded or undated one, which ties at one turn, so its
        neighbours are the memories formed beside it, in the order formed."""
        rows = self._rows()
        anchor = next((r for r in rows if str(r.get("event_key") or "") == anchor_key), None)
        if anchor is None:
            return None
        turn = anchor.get("turn_idx")
        members = {}
        if turn is None or turn < 0:
            for r in rows:
                if r.get("turn_idx") == turn:
                    members[("row", str(r.get("event_key") or ""))] = [r]
            units = list(members)
            return units, units.index(("row", anchor_key)), members
        for r in rows:
            t = r.get("turn_idx")
            if t is not None and t >= 0:
                members.setdefault(("turn", t), []).append(r)
        units = sorted(members, key=lambda u: u[1])
        return units, units.index(("turn", turn)), members

    def _read(self, before, start, after, members):
        """Whole units, chronological. `start` (the anchor of an expansion;
        none for a continuation) always comes back; then the units nearest it
        on each side -- `before` and `after` are listed nearest first -- while
        the result fits `RESULT_CHARS`. Only what came back counts as read, so
        a `continue` picks up exactly where this stopped, and the result says
        which side holds more."""
        kept = list(start)
        size = sum(self._size(members[u]) for u in kept)
        sides = {"before": list(before), "after": list(after)}
        taken = {"before": [], "after": []}
        open_ = {"before": True, "after": True}
        while any(open_[s] and sides[s] for s in sides):
            for s in ("before", "after"):
                if not (open_[s] and sides[s]):
                    continue
                unit = sides[s][0]
                cost = self._size(members[unit])
                if (kept or taken["before"] or taken["after"]) and size + cost > RESULT_CHARS:
                    open_[s] = False
                    continue
                taken[s].append(sides[s].pop(0))
                size += cost
        units = list(reversed(taken["before"])) + kept + taken["after"]
        self._read_units.update(units)
        out = {"memories": self._returned([r for unit in units for r in members[unit]])}
        if sides["before"]:
            out["more_before"] = True
        if sides["after"]:
            out["more_after"] = True
        return out

    def expand(self, ref):
        key = self._resolve(ref)
        if not key:
            return {"refused": self._say("no_such_memory")}
        units, at, members = self._units(key)
        return self._read(list(reversed(units[max(0, at - SPAN_TURNS):at])), [units[at]],
                          units[at + 1:at + SPAN_TURNS + 1], members)

    def continue_(self, ref, direction):
        """`SPAN_TURNS` more, before or after: from the edge of what was
        already read around this memory (an expansion, an earlier continue),
        or from the memory itself when nothing around it was read yet."""
        key = self._resolve(ref)
        if not key:
            return {"refused": self._say("no_such_memory")}
        if direction not in ("before", "after"):
            return {"refused": self._say("before_or_after")}
        units, at, members = self._units(key)
        lo = hi = at
        while lo > 0 and units[lo - 1] in self._read_units:
            lo -= 1
        while hi + 1 < len(units) and units[hi + 1] in self._read_units:
            hi += 1
        if direction == "before":
            pick = list(reversed(units[max(0, lo - SPAN_TURNS):lo]))
            return (self._read(pick, [], [], members) if pick
                    else {"memories": [], "nothing_further": True})
        pick = units[hi + 1:hi + 1 + SPAN_TURNS]
        return (self._read([], [], pick, members) if pick
                else {"memories": [], "nothing_further": True})

    def run(self, tool, args):
        """One lookup's result, JSON-able; never raises."""
        args = args if isinstance(args, dict) else {}
        t0 = time.time()
        try:
            if tool == "ponder":
                result = self.ponder(args.get("query"))
            elif tool == "notebook":
                result = self.notebook()
            elif tool == "expand":
                result = self.expand(args.get("memory_ref"))
            elif tool == "continue":
                result = self.continue_(args.get("memory_ref"), str(args.get("direction") or ""))
            else:
                result = {"refused": self._say("no_such_lookup")}
        except Exception as exc:  # noqa: BLE001 -- a failed lookup is an answer, not a lost beat
            result = {"refused": self._say("could_not_be_made")}
            self.calls.append({"tool": tool, "args": args, "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                               "seconds": round(time.time() - t0, 3)})
            return result
        refs = [m.get("memory_ref") for m in (result.get("memories") or []) if isinstance(m, dict)]
        self.calls.append({"tool": tool, "args": args,
                           "refs": [self.handles.get(r, r) for r in refs if r],
                           **({"refused": result["refused"]} if "refused" in result else {}),
                           "seconds": round(time.time() - t0, 3)})
        # What the model is shown carries no engine number, as its packet
        # does not (the owner, 2026-10-01): judgements in words, the rest
        # dropped. `delivered` keeps the engine's own form for its readers.
        from agents.character_bare import without_engine_numbers
        return without_engine_numbers(result)

    # -- after the call --------------------------------------------------------
    def register(self, holding=None):
        """What the lookups delivered, made delivered: a `looked_up` lane the
        citation walk reads, the read-back's memories, the access record."""
        if not self.delivered:
            return
        lane = self.memory_context.setdefault("looked_up", [])
        have = {str(r.get("memory_ref") or "") for r in lane if isinstance(r, dict)}
        lane.extend(r for r in self.delivered if str(r.get("memory_ref") or "") not in have)
        target = holding if holding is not None else self.holding
        memories = getattr(target, "memories", None)
        if isinstance(memories, list):
            have = {m.get("ref") for m in memories if isinstance(m, dict)}
            for row in self.delivered:
                ref = str(row.get("memory_ref") or "")
                text = row.get("gist") or row.get("details")
                if ref and ref not in have and str(text or "").strip():
                    memories.append({"ref": ref, "text": " ".join(str(text).split())[:600],
                                     "origin": str(row.get("epistemic_origin") or "")})
        ids = self.memory_internal.setdefault("memory_access_ids", [])
        ids.extend(i for i in self.reached_ids if i not in ids)

    def folded(self, wire_payload):
        """The wire packet with what the lookups delivered folded in as a
        memory lane, named by the same handles -- what every repair rung
        resends, so none answers without it."""
        if not self.delivered:
            return None
        from agents.character_bare import without_engine_numbers
        out = dict(wire_payload or {})
        memory = dict(out.get("memory") or {})
        new = [dict(row, memory_ref=self._handle(str(row.get("memory_ref") or "")))
               for row in self.delivered]
        memory["looked_up"] = (list(memory.get("looked_up") or [])
                               + without_engine_numbers({"rows": new})["rows"])
        out["memory"] = memory
        return out


def _call_args(text):
    try:
        args = json.loads(text or "{}")
    except (TypeError, ValueError):
        return None
    return args if isinstance(args, dict) else None


#: The key a route takes a round's reasoning back under. NanoGPT answers with
#: `reasoning` and was probed taking it back (2026-10-05); other routes are
#: unprobed and get the same key until one is measured.
_PASSBACK_KEY = "reasoning"


def look_then_answer(role, system, wire_payload, lookups, *, budget=TOOL_BUDGET,
                     temperature=None, sampler=None, language=None, record=None):
    """The lookup rounds of one character call: `None` where the route takes
    no tool rounds (the caller makes its single call, and says so), else
    `{"answer": raw or None, "history": [...], "reasoning": str}` -- `answer`
    set when the model answered in a round that called nothing (validated as
    the first attempt), `history` the rounds to close on otherwise.

    Each round sends the same system and packet with the history appended,
    so the provider's cache holds the packet for every round after the
    first. Every call is answered -- one past the budget with "no lookups
    left" -- because a call left unanswered is a 400 on the next request.

    A round the route refuses or fails (`LLMError`, a tools body refused
    included) ends the lookups, never the beat: before any lookup the caller
    makes its single call as before; after some, a plain call with what they
    brought folded in. Each round that called a tool is one capture row --
    what it was sent and what it called; the round that answers is the
    ladder's first attempt, recorded there with whether it stood."""
    from llm.llm_quality import note_provider_exchange
    from llm.providers import Aborted, LLMError, RetryConfig, _normalize_usage, chat_complete
    record = record if record is not None else {}
    # One retry a round, not the call's four: the wall clock is checked
    # between rounds, and four attempts of a stalled round would spend it.
    retry = RetryConfig(max_retries=1)
    specs = tool_specs(language)
    user = json.dumps(wire_payload, ensure_ascii=False)
    history, reasonings = [], []
    spent, rounds, t0 = 0, 0, time.time()
    answer_started = None
    from llm.prompts import character_tools_text
    stopped = "answered"
    answer = None
    while True:
        if spent >= budget:
            stopped = "budget"
            break
        if time.time() - t0 > TOOL_WALL_SECONDS:
            stopped = "wall"
            break
        turn = {}
        sent = {**wire_payload, "tool_history": list(history)} if history else wire_payload
        t_round = time.time()
        try:
            # `max_tokens=None` is the configured ceiling, as the single
            # call's is: a thinking round is billed its trace as output.
            content = chat_complete(role, system, user, temperature=temperature,
                                    json_mode=False, max_tokens=None, sampler=sampler,
                                    history=history or None, tools=specs, tool_choice="auto",
                                    turn=turn, retry_config=retry)
        except Aborted:
            raise
        except LLMError as exc:
            # Refused before any lookup: the caller's single call, said so.
            # Refused after some: what they brought is folded into the
            # packet for a plain closing call (no history to close on).
            note_provider_exchange(role=role, system=system, payload=sent, response="",
                                   ok=False, started=t_round, error=str(exc))
            record.update(fallback=f"{type(exc).__name__}: {str(exc)[:200]}", rounds=rounds,
                          calls=spent, seconds=round(time.time() - t0, 3))
            if not history:
                return None
            return {"answer": None, "history": None, "reasoning": _joined(reasonings),
                    "tools": specs}
        rounds += 1
        reasonings.append(str(turn.get("reasoning") or ""))
        used = _normalize_usage(turn.get("usage") or {})
        record.setdefault("usage", []).append({
            "input": used.get("input", 0), "cached": used.get("cache_read", 0),
            "output": used.get("output", 0), "seconds": round(time.time() - t_round, 3)})
        calls = turn.get("tool_calls") or []
        if not calls:
            answer = content or turn.get("content") or ""
            answer_started = t_round
            stopped = "answered"
            break
        note_provider_exchange(role=role, system=system, payload=sent,
                               response={"content": turn.get("content") or "", "tool_calls": calls},
                               ok=True, started=t_round)
        assistant = {"role": "assistant", "content": turn.get("content") or "",
                     "tool_calls": []}
        if turn.get("reasoning"):
            assistant[_PASSBACK_KEY] = turn["reasoning"]
        results = []
        for i, call in enumerate(calls):
            call_id = call.get("id") or f"call_{rounds}_{i}"
            assistant["tool_calls"].append({"id": call_id, "type": "function", "function": {
                "name": call.get("name") or "", "arguments": call.get("arguments") or "{}"}})
            args = _call_args(call.get("arguments"))
            if spent >= budget:
                result = {"not_run": character_tools_text("no_lookups_left", language)}
            elif args is None:
                spent += 1
                result = {"refused": character_tools_text("unreadable_arguments", language)}
            else:
                spent += 1
                result = lookups.run(call.get("name") or "", args)
            results.append({"role": "tool", "tool_call_id": call_id,
                            "content": json.dumps(result, ensure_ascii=False)})
        history.append(assistant)
        history.extend(results)
    record.update(rounds=rounds, calls=spent, stopped=stopped,
                  seconds=round(time.time() - t0, 3))
    return {"answer": answer if stopped == "answered" and answer else None,
            "answer_started": answer_started,
            "history": history, "reasoning": _joined(reasonings),
            "reasonings": [r for r in reasonings if r.strip()], "tools": specs}


def _joined(reasonings):
    """The rounds' thinking as one trace, latest first: the read-back keeps the
    head of a trace (`character_jev.REASONING_CHARS`), and the thinking done
    after the results arrived is the part that decided."""
    kept = [r for r in reasonings if r.strip()]
    return "\n\n".join(reversed(kept))
