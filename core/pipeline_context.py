# pipeline_context.py
"""Typed context object carrying all pipeline state."""

import contextvars
from dataclasses import dataclass, field
from typing import Any, Optional
from core.db import wget

# Which pipeline step is running on THIS thread, so a warning raised anywhere
# under it can be attributed without every producer having to say so.
# `agents.runtime.compute_step` is the single funnel that sets it, and the
# parallel groups copy the context per thread, so a fan-out cannot mis-file a
# sibling's warning onto this step.
current_step_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_step_key", default=None)

#: Most deterministic decisions one turn may record before the log stops
#: growing. Named here rather than buried because it is a real ceiling on what
#: a debug export can tell you: past it, the turn's decision log is TRUNCATED
#: and the export says so rather than pretending it is complete.
#:
#: 2000 is chosen against the producer that sets the scale --
#: `composer.act_percept` runs once per observer per act, so a beat with six
#: present characters and a dozen acts is ~72 entries and an unusually crowded
#: one is a few hundred. A turn that reaches 2000 has something wrong with it,
#: and the truncation is itself the finding.
DECISION_LOG_LIMIT = 2000

# Where a warning raised BELOW the agent layer should land. `llm_quality`'s
# repair ladder (truncation re-ask, temperature-0 repair, fallback candidates)
# and the character stage's decision-review retry each issue a full extra
# provider call, and none of them left a stored trace: a retry that succeeded
# was indistinguishable from a first draft. The 2026-08-11 character-agent
# audit could bound the retry rate only from its failures -- 14 "repetition
# retained" notes in 401 recent-era calls, a floor of >=3.5% with the true
# rate unknowable -- while the live benchmark's 1.25-1.50 provider calls/turn
# against 1.01 stored results/turn suggested ~8-15s/turn on affected sessions.
# `agents.runtime.compute_step` points this at ctx.add_warning for the running
# step (the same funnel that sets current_step_key, so thread-copied contexts
# inherit it); outside a pipeline step it stays None and noting is a no-op --
# importers, generators and jobs keep making repairs silently as before.
current_warning_sink: contextvars.ContextVar[Optional[Any]] = \
    contextvars.ContextVar("current_warning_sink", default=None)


def note_step_warning(msg: str) -> None:
    """Record one diagnostic line on the running pipeline step's engine
    notes, from code that has no PipelineContext in scope. No-op outside a
    step."""
    sink = current_warning_sink.get()
    if sink is not None:
        try:
            sink(str(msg))
        except Exception:
            # A diagnostic must never fail the call it is describing.
            pass


# Where a deterministic DECISION made below the agent layer should land. The
# producers are the guards themselves -- composer, perception, the fan-out's
# manifest check, the background gate -- none of which hold a PipelineContext,
# and none of which should have to be handed one to say what they did.
current_decision_sink: contextvars.ContextVar[Optional[Any]] = \
    contextvars.ContextVar("current_decision_sink", default=None)

# Where one provider EXCHANGE (what was sent, what came back, the reasoning)
# should land. Separate from call_ledger_sink, which carries the same call's
# metadata and is always on: this one is content, off by default, and exists
# so the Director's six specialist sub-calls -- which have no step rows and so
# no variants -- are readable at all.
current_exchange_sink: contextvars.ContextVar[Optional[Any]] = \
    contextvars.ContextVar("current_exchange_sink", default=None)


def note_step_exchange(entry: dict) -> None:
    """Record one provider exchange on the running step. No-op outside a step
    and no-op when debug capture is off."""
    sink = current_exchange_sink.get()
    if sink is not None:
        try:
            sink(entry)
        except Exception:
            pass


def note_step_decision(kind: str, subject: str, verdict: str,
                       reason: str = "") -> None:
    """Record one deterministic decision on the running step. No-op outside a
    step, and no-op when debug capture is off -- which is the default, so the
    hot paths that call this pay one ContextVar read and nothing else."""
    sink = current_decision_sink.get()
    if sink is not None:
        try:
            sink(kind, subject, verdict, reason)
        except Exception:
            # A diagnostic must never fail the call it is describing.
            pass


class StepTaggedWarnings(list):
    """A list of warning strings that also remembers which step raised each.

    A plain `list` because that is what every producer and every test already
    has: the engine warns from ~40 sites across six modules, spelled both
    `ctx.warnings.append(...)` and `ctx.add_warning(...)`, and a dozen tests
    build a stand-in context whose `warnings` is a bare list. Tagging at the
    call sites would have meant editing all of them and would still have
    missed the next one. Tagging here catches every spelling that ADDS a
    warning, including the ones not written yet, and a fake context with a
    plain list keeps working untagged.

    All four of them, because the docstring's argument is future spellings and
    two of the four are C-level: `list.__iadd__` and `list.insert` do not route
    through a Python `extend`/`append` override, so `ctx.warnings += [...]`
    added an entry that was in the list, absent from `notes`, and therefore
    invisible to `for_step` -- the step it belonged to showed no engine note at
    all. Slice assignment (`w[1:2] = [...]`) is deliberately not covered: it
    REPLACES rather than adds, and rewriting a warning somebody already raised
    is not a spelling this channel has.

    `notes` is parallel to the list itself, one entry per warning, at the same
    index.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.notes: list[dict] = [
            {"step": None, "text": str(item)} for item in self]

    def _note(self, item):
        return {"step": current_step_key.get(), "text": str(item)}

    def append(self, item):
        super().append(item)
        self.notes.append(self._note(item))

    def extend(self, items):
        for item in items:
            self.append(item)

    def __iadd__(self, items):
        self.extend(items)
        return self

    def insert(self, index, item):
        # Clamped the way list.insert clamps, so `notes` stays index-parallel
        # for an out-of-range or negative position too.
        at = min(max(index if index >= 0 else len(self) + index, 0), len(self))
        super().insert(index, item)
        self.notes.insert(at, self._note(item))

    def for_step(self, key) -> list[str]:
        """Every warning raised while `key` was the running step.

        By contextvar rather than by list position: the parallel groups run
        siblings on their own threads against a copied context, so slicing by
        index would file one step's repair under whichever sibling happened to
        finish first.
        """
        return [n["text"] for n in self.notes if n.get("step") == key]

@dataclass
class ChatData:
    id: int
    name: str
    persona_id: Optional[int]
    lorebook_id: Optional[int]
    scenario: str
    created: float

    @classmethod
    def from_row(cls, row) -> "ChatData":
        return cls(
            id=row["id"], name=row["name"],
            persona_id=row["persona_id"],
            lorebook_id=row["lorebook_id"],
            scenario=row["scenario"] or "",
            created=row["created"],
        )

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        val = getattr(self, key, None)
        return val if val is not None else default

@dataclass
class TurnData:
    id: int
    chat_id: int
    idx: int
    player_input: str
    created: float
    frame_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> "TurnData":
        return cls(
            id=row["id"], chat_id=row["chat_id"],
            idx=row["idx"], player_input=row["player_input"] or "",
            created=row["created"], frame_id=row["frame_id"],
        )

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        val = getattr(self, key, None)
        return val if val is not None else default

@dataclass
class PipelineContext:
    chat: ChatData
    turn: TurnData
    cast: list
    input: str
    # Human-language policy for this story. Protocol keys and enums remain
    # canonical; prompts, deterministic recognizers and compositor Layer B
    # use this installed pack id.
    language: str = "en"

    director_establish: Optional[dict] = None
    director_interpret: Optional[dict] = None
    # The world-context compiler's step (`agents/mapping.py`). The two model
    # stages it replaced, `mapping_stage` and `mapping_quick`, are no longer
    # declared: a stored turn from before the compiler still hydrates them
    # into `_extra`, and `world_context()` below reads whichever is present,
    # so a rerun of an old beat serves the lore it was served then.
    compile_world_context: Optional[dict] = None
    perception_establish: Optional[dict] = None
    perception_act: Optional[dict] = None
    director_resolve: Optional[dict] = None
    # Declared, not left to `_extra`, for the reason agents/README.md step 5
    # gives: five modules read this stage's output (narration, perception and
    # three commit domains). The storage choice is not cosmetic -- `__contains__`
    # answers `getattr(...) is not None` for a declared field but `key in
    # _extra` for anything else, so an undeclared stage whose handler returned
    # None passed `_assert_plan_materialized` and a declared one does not.
    background_react: Optional[dict] = None
    perception_outcome: Optional[dict] = None
    narrator: Optional[dict] = None
    interaction_loop: Optional[dict] = None
    reaction_loop: Optional[dict] = None
    # Nothing downstream reads it -- commit is the last stage -- but it is a
    # planned step, and the materialization check must be able to tell a
    # commit that returned nothing from one that never ran.
    commit: Optional[dict] = None

    character_results: dict[int, dict] = field(default_factory=dict)
    reaction_results: dict[int, dict] = field(default_factory=dict)

    # Additional human players declaring in the same beat as the primary
    # player (whose input/room/etc. remain the untouched top-level fields
    # above). Each entry: {"persona_id": int, "name": str, "pronouns": dict,
    # "input": str}. Empty for every single-player chat.
    extra_players: list = field(default_factory=list)
    narrator_extra: Optional[dict] = None

    _player_room: Optional[str] = None
    _books: Optional[list[int]] = None
    _persona: Optional[dict] = None

    # What the deterministic layer had to REPAIR in this beat's model output,
    # tagged with the step that raised each message (see StepTaggedWarnings)
    # and shown per step in the pipeline drawer.
    #
    # This was a developer channel nothing in production read, and the cost of
    # that was measured rather than theorised: perception dropped both sight
    # sentences from a character's view of a beat he was watching from six
    # feet away, warned about it twice, and the warnings went into a list no
    # reader existed for. His view, his structured observations and his
    # committed memory of that beat all came out sound-only, and finding out
    # why took a database excavation.
    warnings: StepTaggedWarnings = field(default_factory=StepTaggedWarnings)
    # Every provider call the turn paid for, one dict per call
    # ({step_key, role, requested, served, in, out, cached, duration, kind}),
    # tagged with the running step by the same contextvar warnings use.
    # Fed by providers.call_ledger_sink -> note_llm_call (compute_step wires
    # the two together), persisted per step by runtime._with_engine_notes.
    #
    # This is the durable half of `_log_usage`: the stderr line dies with the
    # process, and three slow-stage investigations in one day each began with
    # a wrong guess because the only surviving record of a live turn was
    # stage-total timestamps. Diagnostic only -- roles, model ids, token
    # counts and durations, never content.
    llm_calls: list = field(default_factory=list)

    # What the DETERMINISTIC layer decided, one dict per decision
    # ({step_key, kind, subject, verdict, reason}), tagged with the running
    # step by the same contextvar warnings and llm_calls use.
    #
    # Distinct from `warnings`, and the distinction is the whole point: a
    # warning means the engine had to REPAIR something, so it fires only on
    # the failure path. This channel records the engine DECLINING as well --
    # `composer.act_percept` refusing an act an observer could not see,
    # `changes_asserted` finding a manifest entry the diff never encoded,
    # `pick_background_reactors` returning [] so no call is made at all.
    #
    # A correct refusal and "nothing happened" are indistinguishable from
    # outside, which is why they cost days to tell apart: act_percept refused
    # every unseen act for four turns while a body stood exposed inside
    # another, behaved perfectly, and left no trace of having run. The
    # firewall works by SUBTRACTION, and subtraction is invisible by
    # construction unless something writes it down.
    #
    # Bounded, because act_percept runs per observer per act and a crowded
    # room would otherwise out-write the story: see DECISION_LOG_LIMIT.
    decisions: list = field(default_factory=list)

    # One dict per provider exchange, content included, tagged by running
    # step. Held in memory for the turn and flushed to `llm_capture` by
    # runtime at the step's own persist point, so capture never opens a write
    # inside the turn's commit lock. Empty unless debug capture is on.
    exchanges: list = field(default_factory=list)

    # What the deterministic layer DID with this beat's model output, in the
    # Director's own terms, carried to the NEXT beat through engine_notices.
    #
    # Distinct from `warnings`: that one is a developer/UI channel about what
    # the engine had to repair. This one is for the model — when commit
    # silently reinterprets or discards something it emitted, saying so is the
    # difference between a mistake it repeats forever and one it can correct.
    # A stage that cannot see what happened to its output is guessing every
    # beat.
    engine_feedback: list[str] = field(default_factory=list)
    _extra: dict[str, Any] = field(default_factory=dict)

    def world_context(self) -> dict:
        """The beat's compiled world context: the compiler's step, or -- for a
        turn stored before the compiler existed -- whichever of the two
        retired mapping stages this turn ran. Every reader of relevant
        lore, staged lore or the scene patch goes through here, so an old
        beat reruns against the context it was resolved with."""
        return (self.compile_world_context
                or self._extra.get("mapping_stage")
                or self._extra.get("mapping_quick")
                or {})

    def get(self, key: str, default=None):
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
            return default
        if key.startswith("character:"):
            cid = int(key.split(":")[1])
            return self.character_results.get(cid, default)
        if key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            return self.reaction_results.get(cid, default)
        return self._extra.get(key, default)

    def __setitem__(self, key: str, value: Any):
        if hasattr(self, key):
            setattr(self, key, value)
        elif key.startswith("character:"):
            cid = int(key.split(":")[1])
            self.character_results[cid] = value
        elif key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            self.reaction_results[cid] = value
        else:
            self._extra[key] = value

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        if key.startswith("character:"):
            cid = int(key.split(":")[1])
            if cid in self.character_results:
                return self.character_results[cid]
        if key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            if cid in self.reaction_results:
                return self.reaction_results[cid]
        if key in self._extra:
            return self._extra[key]
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        if hasattr(self, key) and getattr(self, key) is not None:
            return True
        if key.startswith("character:"):
            cid = int(key.split(":")[1])
            return cid in self.character_results
        if key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            return cid in self.reaction_results
        return key in self._extra

    @property
    def chat_id(self) -> int:
        return self.chat.id

    @property
    def turn_id(self) -> int:
        return self.turn.id

    @property
    def turn_idx(self) -> int:
        return self.turn.idx

    def wget(self, key: str, default=None):
        return wget(self.chat.id, key, default)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def warnings_for_step(self, key: str) -> list[str]:
        """Every warning raised while `key` was the running step."""
        for_step = getattr(self.warnings, "for_step", None)
        return for_step(key) if for_step else []

    def note_llm_call(self, entry: dict):
        """Record one finished provider call against the running step.

        Tagged by contextvar rather than by caller, for the same reason
        StepTaggedWarnings is: the parallel groups and the specialist
        fan-out run on copied contexts, so the producer never has to know
        which step it is under. list.append is atomic under the GIL, so
        sibling threads sharing this context cannot corrupt the list."""
        if not isinstance(entry, dict):
            return
        self.llm_calls.append(
            {"step_key": current_step_key.get(), **entry})

    def llm_calls_for_step(self, key: str) -> list[dict]:
        """Every provider call made while `key` was the running step."""
        return [dict(entry) for entry in self.llm_calls
                if entry.get("step_key") == key]

    def note_decision(self, kind: str, subject: str, verdict: str,
                      reason: str = ""):
        """Record one deterministic decision against the running step.

        Cheap enough to call on the hot path: it is a no-op once the turn's
        ceiling is reached, and the ceiling is hit by exactly the callers that
        would flood it. Tagged by contextvar for the same reason
        `note_llm_call` is -- perception fans out across a thread pool.
        """
        if len(self.decisions) >= DECISION_LOG_LIMIT:
            return
        self.decisions.append({
            "step_key": current_step_key.get(),
            "kind": str(kind or "")[:64],
            "subject": str(subject or "")[:200],
            "verdict": str(verdict or "")[:64],
            "reason": str(reason or "")[:400],
        })

    def decisions_for_step(self, key: str) -> list[dict]:
        """Every deterministic decision made while `key` was the running step."""
        return [dict(entry) for entry in self.decisions
                if entry.get("step_key") == key]

    def note_exchange(self, entry: dict):
        """Record one provider exchange (sent, received, reasoning)."""
        if isinstance(entry, dict):
            self.exchanges.append(
                {"step_key": current_step_key.get(), **entry})

    def exchanges_for_step(self, key: str) -> list[dict]:
        return [dict(entry) for entry in self.exchanges
                if entry.get("step_key") == key]

    def tell_director(self, msg: str):
        """Report what the engine made of the model's output, for next beat."""
        msg = str(msg or "").strip()
        if msg and msg not in self.engine_feedback:
            self.engine_feedback.append(msg)
