"""The relationship graph: what one mind holds toward another, and why.

Axis deltas from conduct and from inference, and the history that records
which beat moved them."""

import time
from core.db import q, qi, wget, wset, wget_for_frame, wset_for_frame
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
    respect: float = 0.0
    suspicion: float = 0.0
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

def get_relationships(chat_id: int, char_id: int, frame_id=_UNSET) -> RelationshipGraph:
    state = (wget(chat_id, f"relationships:{char_id}", None)
             if frame_id is _UNSET else wget_for_frame(
                 chat_id, f"relationships:{char_id}", frame_id, None))
    if state:
        return RelationshipGraph.from_dict(state)
    return RelationshipGraph()

def save_relationships(chat_id: int, char_id: int, graph: RelationshipGraph,
                       frame_id=_UNSET):
    if frame_id is _UNSET:
        wset(chat_id, f"relationships:{char_id}", graph.to_dict())
    else:
        wset_for_frame(chat_id, f"relationships:{char_id}", graph.to_dict(),
                       frame_id)

#: The five axes a stance moves along. Named here so the ledger and the
#: scalar graph cannot disagree about what they are called.
RELATIONSHIP_AXES = (("trust_delta", "trust"),
                     ("warmth_delta", "warmth"),
                     ("fear_delta", "fear"),
                     ("respect_delta", "respect"),
                     ("suspicion_delta", "suspicion"))


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
        respect_delta = _clamp_signed(
            update.get("respect_delta", 0.0), -0.2, 0.2)
        suspicion_delta = _clamp_signed(
            update.get("suspicion_delta", 0.0), -0.2, 0.2)
        trigger_ids = [t for t in (update.get("trigger_event_ids") or []) if t]
        triggers = ", ".join(trigger_ids)
        # The ledger takes one row per axis that actually moved. Axes are kept
        # apart because "trust fell and fear rose" and "trust fell" are
        # different events with different causes, and a single blended row
        # could never be read back into either.
        for field, axis in RELATIONSHIP_AXES:
            moved = {"trust_delta": trust_delta, "warmth_delta": warmth_delta,
                     "fear_delta": fear_delta,
                     "respect_delta": respect_delta,
                     "suspicion_delta": suspicion_delta}[field]
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
            respect=_clamp_signed(current.respect + respect_delta, -1.0, 1.0),
            suspicion=_clamp_signed(
                current.suspicion + suspicion_delta, -1.0, 1.0),
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


#: Which scalar field on the graph each judgment axis is stored in. The
#: ledger and `world.charter_social.JUDGMENT_AXES` both call the second one
#: `warmth`; the dataclass has called it `emotional_valence` since before
#: either existed, and one map here is cheaper than renaming a stored field.
_WITNESSED_AXIS_FIELD = {"trust": "trust", "warmth": "emotional_valence",
                         "fear": "fear", "respect": "respect",
                         "suspicion": "suspicion"}

#: The provenance a floor movement is stamped with. Not `character` (the mind
#: declared nothing), not `inference` (it concluded nothing), not
#: `unevidenced` (it cites the observation it read): it WITNESSED an act.
WITNESSED_PROVENANCE = "witnessed"


def apply_witnessed_signals(chat_id, char_id, turn_idx, witnessed,
                            frame_id=_UNSET):
    """The deterministic evidence floor for a registered mind's stances.

    Review 2026-09-07 D21. A charter body's five axes move from the
    speech-act kinds it witnesses, deterministically, on every beat
    (`charter_social.update_judgments_from_minds`); a registered character's
    moved only when the model chose to emit `relationship_updates`. So
    promoting a body stopped it obeying the rules that formed it, and two
    people standing in the same room -- one registered, one not -- came out
    of the same insult with different arithmetic. This is the same table,
    the same diminishing returns and the same axes, applied to the graph the
    registered mind actually keeps.

    `witnessed` is what THIS mind was delivered: entries of
    ``{"subject", "signal", "source_id"}`` that
    `persist.commit_memory._witnessed_signals` built from this observer's OWN
    composed view. The source set is never the charter's spatial reception
    answer and never another observer's -- one head's gate deciding another
    head's stance is the firewall failure this floor is most able to cause,
    so the delivery proof is made where the view is and this function only
    ever sees one mind's already-answered list.

    Runs AFTER the model's own ops for the beat, so a stance the character
    declared is the stance the floor moves from, and never the other way
    round.
    """
    resolved_frame_id = (
        _active_frame_id.get() if frame_id is _UNSET else frame_id)
    items = []
    seen = set()
    for entry in witnessed or ():
        if not isinstance(entry, dict):
            continue
        subject = str(entry.get("subject") or "").strip()
        signal = str(entry.get("signal") or "").strip()
        source_id = str(entry.get("source_id") or "").strip()
        if not subject or not signal:
            continue
        key = (subject, signal, source_id)
        if key in seen:
            continue
        seen.add(key)
        items.append(key)
    if not items:
        return None
    # ONCE PER BEAT, EVEN IF THE BEAT IS COMMITTED TWICE. `commit_memories`
    # deletes and re-mints this turn's memories on a re-run, but the graph is
    # cumulative and the ledger is append-only, so a re-run would move every
    # stance a second time from the same evidence. The ledger is the record
    # of what has already been read: an act cites its `source_id` in
    # `triggers` and names its signal in `note`, which is exactly the
    # `evidence_id|signal` idempotence key `update_judgments_from_minds`
    # keeps in a stance's `seen` list.
    already = set()
    # SCOPED BY FRAME, like the graph it guards: `relationships:` is in
    # `core.db.FRAME_SCOPED_WORLD_PREFIXES`, so each era keeps its own stance
    # row, and turn indices repeat across eras by construction. Unscoped, one
    # era's ledger silenced another's -- the same witnessed insult at turn 5
    # in a branch moved nothing and left the mind there with no `because` row
    # for a beat it lived (D21 skeptic, reproduced 2026-09-08).
    for row in q("SELECT target,triggers,note FROM relationship_events "
                 "WHERE chat_id=? AND char_id=? AND turn_idx=? AND "
                 "provenance=? AND frame_id IS ?",
                 (int(chat_id), int(char_id), int(turn_idx or 0),
                  WITNESSED_PROVENANCE, resolved_frame_id)) or []:
        already.add((str(row["target"] or ""), str(row["note"] or ""),
                     str(row["triggers"] or "")))
    graph = get_relationships(chat_id, char_id)
    movements = []
    for subject, signal, source_id in items:
        if (subject, signal, source_id) in already:
            continue
        current = graph.get(subject)
        if current is None:
            graph.update(subject)
            current = graph.get(subject)
        stance = {axis: float(getattr(current, field, 0.0) or 0.0)
                  for axis, field in _WITNESSED_AXIS_FIELD.items()}
        # ONE ARITHMETIC, and it lives with the table it reads. A deferred
        # import: `world` imports `mind` at module level in four places, so
        # an eager one here would be a new package cycle.
        from world.charter import signal_landing
        landed = signal_landing(signal, stance)
        if not landed:
            continue
        fields = {}
        for axis, after in landed.items():
            delta = round(after - stance[axis], 6)
            if not delta:
                continue
            field = _WITNESSED_AXIS_FIELD[axis]
            fields[field] = after
            record_relationship_event(
                chat_id, char_id, subject, axis, delta,
                triggers=[source_id] if source_id else (),
                note=signal, provenance=WITNESSED_PROVENANCE,
                turn_idx=turn_idx, frame_id=resolved_frame_id)
            movements.append({"subject": subject, "signal": signal,
                              "axis": axis, "delta": delta,
                              "source_id": source_id})
        if not fields:
            continue
        # `familiarity` and `salient_event` are deliberately left alone. The
        # first is a tally of time spent, which witnessing one act is not;
        # the second is the model's own sentence about why a stance moved,
        # and a floor that overwrote it would erase the history
        # `apply_relationship_updates` takes care not to erase.
        graph.update(subject, last_interaction_turn=turn_idx, **fields)
    if movements:
        save_relationships(chat_id, char_id, graph)
    return movements


def _because_by_target(chat_id, char_id, targets, frame_id):
    """Per target, the strongest recorded movement along each axis.

    D22 (review 2026-09-07): `relationship_events` had no reader anywhere.
    The scalar graph says where a stance stands and structurally cannot say
    why -- it keeps one `salient_event` string and overwrites it whenever the
    character feels anything at all -- while the ledger beside it has kept
    one row per axis per movement since the day it was built. A mind was
    being handed the five numbers and none of the beats that made them.

    HOW MANY REASONS, and why this is not a size cap: the stance IS five
    numbers (`RELATIONSHIP_AXES`), and this is the one beat behind each of
    them, so `because` can never be longer than the thing it explains
    however many rows the ledger has accumulated. Measured on the descent
    bench (chat 117): 322 rows for a single pair across 123 beats, five of
    which reach the payload.

    Frame-scoped exactly as the graph is: `get_relationships` reads through
    `wget`, whose key is redirected by the ambient `active_frame_id`, so the
    history a mind reads is its history IN THIS FRAME and an alternate era's
    reasons can never explain the present's stance.

    `triggers` is deliberately not carried across. A stored trigger id is a
    ref into the turn that wrote it (`current:78:4` on all 322 descent rows);
    grounding is a turn-scoped act, so the id is unresolvable afterwards and
    would reach the mind as a citation to nothing.
    """
    if not targets:
        return {}
    rows = q("SELECT target,axis,delta,note,provenance,turn_idx "
             "FROM relationship_events "
             "WHERE chat_id=? AND char_id=? AND frame_id IS ? "
             "ORDER BY ABS(delta) DESC, id DESC",
             (int(chat_id), int(char_id), frame_id)) or []
    strongest = {}
    for row in rows:
        target = str(row["target"] or "")
        if target not in targets:
            continue
        # Ordered by |delta| descending, so the first row seen for an axis is
        # that axis's largest movement; ties go to the most recent, because a
        # live reason outranks an equally large ancient one.
        strongest.setdefault(target, {}).setdefault(
            str(row["axis"] or ""), row)
    out = {}
    for target, held in strongest.items():
        entries = []
        for _field, axis in RELATIONSHIP_AXES:
            row = held.get(axis)
            if row is None:
                continue
            entry = {"axis": axis, "delta": float(row["delta"] or 0.0),
                     "turn": int(row["turn_idx"] or 0),
                     "provenance": str(row["provenance"] or "")}
            # ABSENT RATHER THAN EMPTY, and the measurement that says why the
            # key is often absent: on 2026-09-08 `note` was empty on all 353
            # stored rows across both benches, because the only provenance
            # either story produced is `character` and
            # `llm.schemas.RelationshipUpdate` carries no `reason` field for
            # `apply_relationship_updates`' `update.get("reason")` to find.
            # The greeting, inference, charter-promotion, journey-companion
            # and charter-acquaintance paths each write a real sentence (the
            # last two since this item's rework), so the key appears wherever
            # one exists.
            if str(row["note"] or ""):
                entry["note"] = str(row["note"])
            entries.append(entry)
        if entries:
            out[target] = entries
    return out


def relationships_for_payload(chat_id: int, char_id: int) -> dict:
    """The stance graph as the character agent and the host both read it.

    Each target carries `because`: the beat behind each axis it stands at
    (`_because_by_target`). Firewall-safe by construction -- every row in
    `relationship_events` under this `char_id` was written from this mind's
    own conduct, its own inference, its authored opening stance, or the
    charter history it lived, so nothing here is another observer's view.
    """
    graph = get_relationships(chat_id, char_id)
    out = graph.to_dict()
    because = _because_by_target(chat_id, char_id, set(out),
                                 _active_frame_id.get())
    for name, entry in out.items():
        reasons = because.get(name)
        if reasons:
            entry["because"] = reasons
    return out
