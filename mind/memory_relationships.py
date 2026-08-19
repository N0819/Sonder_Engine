"""The relationship graph: what one mind holds toward another, and why.

Axis deltas from conduct and from inference, and the history that records
which beat moved them."""

import time
from core.db import q, qi, wget, wset
from dataclasses import dataclass, field, asdict
from typing import Optional
from core.db import active_frame_id as _active_frame_id

from mind.memory_common import _UNSET, _ling
from mind.memory_write import _clamp_signed

# ---- Relationship Graph ----

@dataclass
class Relationship:
    target_name: str
    trust: float = 0.0
    familiarity: float = 0.0
    emotional_valence: float = 0.0
    fear: float = 0.0
    last_interaction_turn: int = 0
    salient_event: str = ""
    notes: str = ""

@dataclass
class RelationshipGraph:
    relationships: dict[str, Relationship] = field(default_factory=dict)

    def get(self, target_name: str) -> Optional[Relationship]:
        return self.relationships.get(target_name)

    def update(self, target_name: str, **kwargs):
        r = self.relationships.setdefault(target_name, Relationship(target_name=target_name))
        for k, v in kwargs.items():
            if hasattr(r, k):
                setattr(r, k, v)

    def adjust_trust(self, target_name: str, delta: float, trigger: str = ""):
        r = self.relationships.setdefault(target_name, Relationship(target_name=target_name))
        r.trust = max(-1.0, min(1.0, r.trust + delta))
        if trigger:
            r.salient_event = trigger

    def to_dict(self) -> dict:
        return {name: asdict(rel) for name, rel in self.relationships.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "RelationshipGraph":
        graph = cls()
        for name, rd in (data or {}).items():
            graph.relationships[name] = Relationship(**rd)
        return graph

def get_relationships(chat_id: int, char_id: int) -> RelationshipGraph:
    state = wget(chat_id, f"relationships:{char_id}", None)
    if state:
        return RelationshipGraph.from_dict(state)
    return RelationshipGraph()

def save_relationships(chat_id: int, char_id: int, graph: RelationshipGraph):
    wset(chat_id, f"relationships:{char_id}", graph.to_dict())

#: The three axes a stance moves along. Named here so the ledger and the
#: scalar graph cannot disagree about what they are called.
RELATIONSHIP_AXES = (("trust_delta", "trust"),
                     ("warmth_delta", "warmth"),
                     ("fear_delta", "fear"))


def record_relationship_event(chat_id, char_id, target, axis, delta, *,
                              triggers=(), note="", provenance="character",
                              turn_idx=0, frame_id=None):
    """Append one reason a stance moved. Never updated, never deleted.

    The scalar graph answers WHERE a relationship stands and cannot answer why
    it got there: it keeps a single `salient_event` string and overwrites it
    whenever the character's feelings move at all, so the reason somebody
    stopped trusting you survives until the next time they feel anything.

    Measured before this was built, because the interesting question was
    whether the reasons existed at all: 98.8% of the 5,704 stance movements in
    the live corpus already carried `trigger_event_ids`. The model had been
    saying why the entire time. This keeps what it said.
    """
    if not target or not axis or not float(delta or 0.0):
        return None
    return qi(
        "INSERT INTO relationship_events(chat_id,frame_id,char_id,target,axis,"
        "delta,triggers,note,provenance,turn_idx,created) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (int(chat_id), frame_id, int(char_id), str(target), str(axis),
         float(delta), ",".join(str(t) for t in (triggers or []) if t),
         str(note or "")[:300], str(provenance or ""), int(turn_idx or 0),
         time.time()))


def relationship_history(chat_id, char_id, target, limit=20):
    """Why this stance is where it is, oldest first.

    The question the scalar graph could never answer, and the reason item 4 of
    the off-screen roadmap exists.
    """
    rows = q("SELECT axis,delta,triggers,note,provenance,turn_idx "
             "FROM relationship_events WHERE chat_id=? AND char_id=? "
             "AND target=? ORDER BY id DESC LIMIT ?",
             (int(chat_id), int(char_id), str(target), int(limit))) or []
    return [dict(r) for r in reversed(rows)]


def apply_relationship_updates(chat_id, char_id, turn_idx, updates,
                               frame_id=None):
    graph = get_relationships(chat_id, char_id)
    for update in updates or []:
        target = str(update.get("target_entity") or "").strip()
        if not target:
            continue
        current = graph.get(target)
        if current is None:
            graph.update(target)
            current = graph.get(target)
        trust_delta = _clamp_signed(update.get("trust_delta", 0.0), -0.2, 0.2)
        warmth_delta = _clamp_signed(update.get("warmth_delta", 0.0), -0.2, 0.2)
        fear_delta = _clamp_signed(update.get("fear_delta", 0.0), -0.2, 0.2)
        trigger_ids = [t for t in (update.get("trigger_event_ids") or []) if t]
        triggers = ", ".join(trigger_ids)
        # The ledger takes one row per axis that actually moved. Axes are kept
        # apart because "trust fell and fear rose" and "trust fell" are
        # different events with different causes, and a single blended row
        # could never be read back into either.
        for field, axis in RELATIONSHIP_AXES:
            moved = {"trust_delta": trust_delta, "warmth_delta": warmth_delta,
                     "fear_delta": fear_delta}[field]
            if moved:
                record_relationship_event(
                    chat_id, char_id, target, axis, moved,
                    triggers=trigger_ids, note=update.get("reason") or "",
                    provenance="character" if trigger_ids else "unevidenced",
                    turn_idx=turn_idx, frame_id=frame_id)
        graph.update(target,
            trust=_clamp_signed(current.trust + trust_delta, -1.0, 1.0),
            emotional_valence=_clamp_signed(current.emotional_valence + warmth_delta, -1.0, 1.0),
            fear=_clamp_signed(current.fear + fear_delta, -1.0, 1.0),
            familiarity=min(1.0, current.familiarity + 0.03),
            last_interaction_turn=turn_idx,
            # Only overwrite the recorded salient event when this update
            # actually carries triggers -- a routine trigger-less delta
            # must not erase previously recorded history.
            **({"salient_event": triggers[-300:]} if triggers else {}))
    save_relationships(chat_id, char_id, graph)
    return graph

# How far one inference moves trust, by direction. Deliberately asymmetric:
# concluding somebody cannot be trusted is worth more than concluding they
# can, because the cost of the two mistakes is not the same. This is
# psychology, not language, so it does NOT live in the pack -- only the
# vocabularies that decide which direction a conclusion points do.
_TRUST_INFERENCE_STEP = {"trusting": 0.1, "wary": -0.15}


def update_relationships_from_inference(chat_id, char_id, turn_idx,
                                        inference_updates, existing=None,
                                        frame_id=_UNSET):
    """Move a stance from what the character CONCLUDED about someone.

    The second of the two paths that move the scalar graph, and the one that
    left no trace. `apply_relationship_updates` writes a `relationship_events`
    row per axis that moved -- a ledger that is never updated and never deleted,
    because the graph holds one `salient_event` string and overwrites it
    whenever the character feels anything at all. This path moved the same
    scalar, on the same graph, saved by the same call, and recorded nothing. A
    whole class of trust movement was missing from the record of why trust is
    where it is, and the gap does not surface as a wrong row: it surfaces as a
    stance whose history cannot explain it.

    The reason is stamped `inference` rather than `character`, because
    concluding somebody is dangerous and being told so are different
    provenances and the ledger already exists to keep that difference.

    Which conclusions move trust is a question about WORDS, so the two
    vocabularies live in the pack (`mind.memory._TRUST_INFERENCE_CUES`); how
    far each moves it does not, so the step stays here. Before this, a
    Japanese story drew every inference it liked and none of them ever moved
    a relationship, silently.
    """
    graph = existing or get_relationships(chat_id, char_id)
    resolved_frame_id = (
        _active_frame_id.get() if frame_id is _UNSET else frame_id)
    for u in inference_updates:
        about = u.get("about", "")
        if not about:
            continue
        confidence = float(u.get("confidence", 0.5))
        conclusion = u.get("conclusion", "")
        cl = conclusion.lower()
        trust_delta = 0.0
        for direction, cues in _ling("_TRUST_INFERENCE_CUES"):
            if any(w in cl for w in cues):
                trust_delta = _TRUST_INFERENCE_STEP[direction] * confidence
                break
        if trust_delta != 0:
            graph.adjust_trust(about, trust_delta, conclusion[:200])
            # The conclusion IS the reason, so it is the note. No trigger ids:
            # an inference cites the events it was drawn from upstream, and
            # inventing one here would put a fabricated citation in a ledger
            # that is never corrected.
            record_relationship_event(
                chat_id, char_id, about, "trust", trust_delta,
                note=conclusion, provenance="inference",
                turn_idx=turn_idx, frame_id=resolved_frame_id)
        graph.update(about,
            familiarity=min(1.0, (graph.get(about).familiarity + 0.05) if graph.get(about) else 0.05),
            last_interaction_turn=turn_idx)
    save_relationships(chat_id, char_id, graph)
    return graph

def relationships_for_payload(chat_id: int, char_id: int) -> dict:
    graph = get_relationships(chat_id, char_id)
    return graph.to_dict()

