# pipeline_context.py
"""Typed context object carrying all pipeline state."""

import contextvars
from dataclasses import dataclass, field
from typing import Any, Optional
from db import wget

# Which pipeline step is running on THIS thread, so a warning raised anywhere
# under it can be attributed without every producer having to say so.
# `agents.runtime.compute_step` is the single funnel that sets it, and the
# parallel groups copy the context per thread, so a fan-out cannot mis-file a
# sibling's warning onto this step.
current_step_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_step_key", default=None)

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


class StepTaggedWarnings(list):
    """A list of warning strings that also remembers which step raised each.

    A plain `list` because that is what every producer and every test already
    has: the engine warns from ~40 sites across six modules, spelled both
    `ctx.warnings.append(...)` and `ctx.add_warning(...)`, and a dozen tests
    build a stand-in context whose `warnings` is a bare list. Tagging at the
    call sites would have meant editing all of them and would still have
    missed the next one. Tagging here catches every spelling, including the
    ones not written yet, and a fake context with a plain list keeps working
    untagged.

    `notes` is parallel to the list itself, one entry per append.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.notes: list[dict] = [
            {"step": None, "text": str(item)} for item in self]

    def append(self, item):
        super().append(item)
        self.notes.append({"step": current_step_key.get(), "text": str(item)})

    def extend(self, items):
        for item in items:
            self.append(item)

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

    director_establish: Optional[dict] = None
    director_interpret: Optional[dict] = None
    mapping_stage: Optional[dict] = None
    mapping_quick: Optional[dict] = None
    perception_establish: Optional[dict] = None
    perception_act: Optional[dict] = None
    director_resolve: Optional[dict] = None
    perception_outcome: Optional[dict] = None
    narrator: Optional[dict] = None
    interaction_loop: Optional[dict] = None
    reaction_loop: Optional[dict] = None

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
    _fiction_model: Optional[dict] = None
    _simulation_clock: Optional[dict] = None

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

    def get(self, key: str, default=None):
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
            if key.startswith("_") and key in self._extra:
                return self._extra[key]
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

    def tell_director(self, msg: str):
        """Report what the engine made of the model's output, for next beat."""
        msg = str(msg or "").strip()
        if msg and msg not in self.engine_feedback:
            self.engine_feedback.append(msg)