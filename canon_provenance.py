"""Canon provenance -- the provisional tier.

0a of ``docs/PROPOSAL_2026-08-06.md`` section 6, with section 3.4 as the source
of the disposition vocabulary and section 1.0.3 as the source of the rules
enforced here.

WHAT THIS IS FOR. Offscreen ticks, gap summaries and background claims all
produce assertions that no Director adjudicated. Stored beside resolved fact
they are indistinguishable from it the moment they land -- which is the
laundering section 2C describes, arriving from a new direction. This module
gives that output its own tier and refuses, on the write path, to let it look
like anything else.

WHAT THIS IS NOT. It does not promote. Promotion is the Director's, per
section 7 of ``docs/PROPOSAL_2026-08-06_AMENDMENTS.md``; the seam is named in
``promote`` below and is deliberately unimplemented here so the tier can land
and be tested without touching the Director seam.

SUBJECT KIND IS AN OPEN VOCABULARY, on purpose. ``KNOWN_SUBJECT_KINDS`` is a
courtesy list, not an enum: an unrecognised kind VALIDATES and is reported in
``ValidationResult.unknown_subject_kind`` so a caller can log it. A crowd, a
faction, a room and an ungenerated place must all be spellable without a
migration. Closing the vocabulary now IS the migration.

THE LOW TIER DOES NOT ASSUME ITS SUBJECT IS A PERSON. There is no field named
for a character, nothing defaults ``kind`` to ``"character"``, and every rule
below is stated over ``subject.kind``/``subject.id`` rather than over a cast
member.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: The tier this module exists for.
PROVISIONAL = "provisional"

#: The seven dispositions of section 3.4. Their order RELATIVE TO EACH OTHER is
#: not decided here -- nothing has measured it, and inventing a ranking would be
#: a decision taken by accident. All this module claims is that `provisional`
#: sits below every one of them; see ``outranks``.
#:
#: Naming note: `player_claim` here is a PROVENANCE disposition. It is NOT the
#: director's omission `source` field, which keeps its own meaning; the two
#: share a word and nothing else, and neither aliases the other.
ADJUDICATED_DISPOSITIONS = (
    "imported_canon",
    "resolved_fact",
    "player_claim",
    "spatial_generation",
    "character_belief",
    "narrator_audit",
    "inferred_mapping",
)

KNOWN_DISPOSITIONS = (PROVISIONAL,) + ADJUDICATED_DISPOSITIONS

#: A COURTESY LIST, not an enum. Unknown kinds validate; see the module
#: docstring and ``validate_provisional``.
#:
#: ``room`` AND ``place`` ARE BOTH HERE, DELIBERATELY -- settled during 0c.
#: They look like two spellings of one thing, which is the defect this whole
#: effort exists to prevent, but they are two LEDGERS for two lifecycle
#: states: a ``room`` has a ``room_uid`` in ``room_registry``; a ``place`` is
#: a lorebook location the mapping agent has never generated, which has no
#: room_uid to be keyed by and is keyed on its lore ``entry_uid`` instead
#: (amendment 8). Collapsing them would either mint fake room_uids for
#: ungenerated places or make them unspellable. The seam between the states
#: is owned by ``subjects.resolve_subject``: a place that HAS since been
#: generated resolves as the ``room`` subject, so both spellings are never
#: live for one location at once.
KNOWN_SUBJECT_KINDS = ("character", "room", "faction", "crowd", "place")

#: section 1.2 step 1: a gap that could not be produced returns
#: ``basis: "unavailable"`` with a reason, never nothing.
BASES = ("deterministic", "model", "unavailable")

#: Node ids are slugs or uids. The single ``offscreen_log`` row ever written
#: places its actor in "a quiet office" -- a room the scene graph does not
#: contain. This is the check that would have refused it on the write path,
#: which is where it belongs: a stored invented room outlives the turn that
#: made it.
_NODE_ID = re.compile(r"^[a-z0-9][a-z0-9_.:/-]*$")

#: Section 1.0.1's line: the rungs below full-agent may DESCRIBE, they may not
#: COMMIT. A rung that cannot express a consequence cannot smuggle one.
_CONSEQUENCE_KEYS = ("deltas", "standing_intentions", "ratified_claims")

#: Every field anywhere in a record that names a place.
_ROOM_FIELDS = ("room", "room_uid", "from_room", "to_room", "location")


@dataclass(frozen=True)
class Subject:
    """Who or what a provisional record is about.

    ``kind`` is free-form by design. ``id`` is an id -- the whole point of 0c
    arriving after this, and the reason five ledgers keyed by display name are
    a single defect rather than five.
    """

    kind: str
    id: str
    display: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "id": self.id}
        if self.display is not None:
            out["display"] = self.display
        return out


@dataclass
class ValidationResult:
    """Why a record was refused, or what was odd about one that was accepted.

    ``unknown_subject_kind`` is the open-vocabulary escape hatch: it is set,
    and the record still validates.
    """

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknown_subject_kind: str | None = None

    def __bool__(self) -> bool:
        return self.ok


def is_node_id(value: Any) -> bool:
    """Whether a string is id-shaped rather than prose.

    Public so the gap generator tests room references against the SAME
    pattern this module's validator enforces -- a second spelling of the
    regex would drift, and then one module's id is the other's prose.
    """

    return isinstance(value, str) and bool(_NODE_ID.match(value))


def is_canon(disposition: str) -> bool:
    """True only for a disposition something adjudicated."""

    return disposition in ADJUDICATED_DISPOSITIONS


def may_assert_consequence(disposition: str) -> bool:
    """Whether a record at this disposition may change the world.

    False for the provisional tier, and that is the whole safety property.
    """

    return disposition in ADJUDICATED_DISPOSITIONS


def outranks(a: str, b: str) -> bool | None:
    """Whether ``a`` beats ``b``, or ``None`` where this module declines to say.

    Only comparisons involving ``provisional`` are decided. Ranking the seven
    adjudicated dispositions against each other is a design decision nobody has
    taken, and returning a plausible answer to it would hide that.
    """

    if a not in KNOWN_DISPOSITIONS or b not in KNOWN_DISPOSITIONS:
        return None
    if a == b:
        return False
    if b == PROVISIONAL:
        return True
    if a == PROVISIONAL:
        return False
    return None


def unavailable(subject: Subject | Mapping[str, Any], base_turn: int, reason: str) -> dict[str, Any]:
    """A provisional record saying the thing could not be produced, and why.

    Silence is how the abort path made a crash and a closed tab
    indistinguishable. An empty reason raises rather than storing one.
    """

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "an unavailable record must say why; silence is the defect this replaces"
        )
    subj = subject.as_dict() if isinstance(subject, Subject) else dict(subject)
    return {
        "disposition": PROVISIONAL,
        "subject": subj,
        "base_turn": int(base_turn),
        "basis": "unavailable",
        "reason": reason,
    }


def _node_id_errors(record: Mapping[str, Any]) -> list[str]:
    out: list[str] = []

    def check(where: str, value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, str) or not _NODE_ID.match(value):
            out.append(
                f"{where} {value!r} is not a node id; 'a quiet office' is the row this refuses"
            )

    for name in _ROOM_FIELDS:
        if name in record:
            check(name, record.get(name))

    about = record.get("about")
    if isinstance(about, Mapping):
        for name in _ROOM_FIELDS:
            if name in about:
                check(f"about.{name}", about.get(name))

    moves = record.get("moves")
    if isinstance(moves, (list, tuple)):
        for i, mv in enumerate(moves):
            if isinstance(mv, Mapping):
                for name in _ROOM_FIELDS:
                    if name in mv:
                        check(f"moves[{i}].{name}", mv.get(name))
    elif moves is not None:
        out.append("moves must be a list when present")

    return out


def validate_provisional(
    record: Mapping[str, Any],
    *,
    adjudicated_event_ids: "set[str] | frozenset[str] | None" = None,
) -> ValidationResult:
    """Check a record before it is stored durably.

    This is a WRITE-path check on purpose. A stored invented room, or a ledger
    row keyed by a display name, is a defect that outlives the turn that made
    it, and no read-path filter can undo it afterwards.

    CITING IS NOT MINTING. A provisional record may reference an
    ``event_id`` something adjudicated elsewhere -- a citation is not a
    claim to have adjudicated anything -- but it may not mint a new one.
    The record's shape alone cannot tell the two apart (a minted id and a
    cited id are both strings), so the caller supplies the citable set as
    ``adjudicated_event_ids``: ids already minted by an adjudicated ledger
    (today that is ``scheduled_events``, the only id-bearing event ledger
    with a runtime writer). With no set supplied the check FAILS CLOSED and
    refuses every event_id, exactly as before -- an unverifiable citation
    is indistinguishable from a mint, and the tier must not guess.
    """

    if not isinstance(record, Mapping):
        return ValidationResult(False, ["record is not a mapping"])

    errors: list[str] = []
    warnings: list[str] = []
    unknown_kind: str | None = None

    disposition = record.get("disposition")
    if disposition != PROVISIONAL:
        errors.append(f"disposition is {disposition!r}, not {PROVISIONAL!r}")

    subject = record.get("subject")
    if not isinstance(subject, Mapping):
        errors.append("subject is missing or is not a mapping")
    else:
        kind = subject.get("kind")
        sid = subject.get("id")
        if not isinstance(kind, str) or not kind.strip():
            errors.append("subject.kind is required and must be a non-empty string")
        elif kind not in KNOWN_SUBJECT_KINDS:
            # Open vocabulary: reported, not refused.
            unknown_kind = kind
            warnings.append(
                f"subject.kind {kind!r} is outside the courtesy list and was accepted"
            )
        if not isinstance(sid, str) or not sid.strip():
            errors.append("subject.id is required and must be a non-empty string")
        else:
            if not _NODE_ID.match(sid):
                errors.append(
                    f"subject.id {sid!r} is not an id; ledgers keyed by display name are the "
                    "defect that splits one being into three"
                )
            display = subject.get("display")
            if (
                isinstance(display, str)
                and display.strip()
                and display.strip().casefold() == sid.strip().casefold()
            ):
                errors.append(
                    "subject.id equals subject.display; the id must not be the display name"
                )

    base_turn = record.get("base_turn")
    if isinstance(base_turn, bool) or not isinstance(base_turn, int) or base_turn < 0:
        errors.append("base_turn is required and must be a non-negative int")

    basis = record.get("basis")
    if basis not in BASES:
        errors.append(f"basis must be one of {BASES}, got {basis!r}")
    elif basis == "unavailable":
        reason = record.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("basis 'unavailable' requires a non-empty reason")

    for key in _CONSEQUENCE_KEYS:
        if record.get(key):
            errors.append(
                f"{key} is a consequence; the provisional tier may describe, not commit"
            )

    events = record.get("events")
    if events is None:
        pass
    elif isinstance(events, (list, tuple)):
        citable = adjudicated_event_ids or frozenset()
        for i, ev in enumerate(events):
            if not (isinstance(ev, Mapping) and ev.get("event_id")):
                continue
            if str(ev.get("event_id")) in citable:
                continue  # a citation of an adjudicated id, not a mint
            errors.append(
                f"events[{i}] event_id {ev.get('event_id')!r} is not in the "
                "adjudicated set; a provisional record may cite an "
                "already-adjudicated id, never mint one"
            )
    else:
        errors.append("events must be a list when present")

    errors.extend(_node_id_errors(record))

    return ValidationResult(not errors, errors, warnings, unknown_kind)


def promote(record: Mapping[str, Any], disposition: str, *, adjudicator: str) -> dict[str, Any]:
    """NOT IMPLEMENTED, and deliberately so. This is the named seam.

    Promotion out of the provisional tier belongs to the Director, per section 7
    of ``docs/PROPOSAL_2026-08-06_AMENDMENTS.md``. Most of the path is described
    there as already existing: the Director names a claim in
    ``state_diff.ratified_claims``, ``commit`` hands that list to
    ``background_claims.settle_claims``, and ``settle_claims`` sets a status
    flag in the world-KV blob and writes nothing into canon. That missing write
    is 0a's successor.

    It is left unimplemented here so this tier can land, be tested and be
    committed without touching the Director seam -- which the proposal itself
    warns should be approached test-first and small.
    """

    raise NotImplementedError(
        "promotion out of the provisional tier is the Director's; the seam is "
        "state_diff.ratified_claims -> settle_claims, and the write into canon does not "
        "exist yet. See docs/PROPOSAL_2026-08-06_AMENDMENTS.md section 7."
    )
