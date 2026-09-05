"""What the Writers' Room may state as fact, and what it read to know it.

THE MEASURED CLASS. A recap is the room's most useful reply and its most
dangerous one, because it reads as the engine talking. Measured on
2026-09-05: the caravanserai run's recap said a character was "feigning
sleep while listening intently" (his ledger says watchful and hooded, and
never asleep) and that another had "sent a servant to alert Gate Warden
Vesk" (nothing was sent; the one attempt was rebuffed). The road run's said
a salve was offered and "she declined" (the ledger holds a contact and an
inventory transfer, and no refusal) and that a scout "heard movement
inside" (an invention from an earlier beat, read back as fact). The manor
run's explained a tool result with a mechanism the engine does not have.

The class is not lying. It is that the room READS LEDGERS -- positions,
contacts, transfers, intentions -- AND RENDERS THEM AS MOTIVES, and nothing
between the reading and the rendering asked which row said so.

THE CONTRACT, and it is a contract rather than a guard. A recap states what
the ledgers say and CITES THE ROWS IT READ; where it has no row, it says so
rather than composing one. Two things follow, and both are the point:

* A PROPOSAL IS NOT AN ASSERTION. The room stays free to suggest, invent
  and speculate -- that is its whole job -- and none of that needs a row.
  What it may not do is let the two wear the same clothes. So a claim
  arrives marked: either it cites the rows it came from, or it is a
  proposal.
* AN UNCITED CLAIM IS DEMOTED, NOT DELETED. A claim carrying no row it
  could have come from does not vanish from the reply; it stops counting as
  something the world says. Deleting the room's sentence would make the
  room less useful and teach nobody anything; demoting it says exactly what
  is wrong with it.

WHAT THIS IS NOT. It is not a prose guard: nothing here reads the room's
English, classifies a sentence, or matches a phrase. The room enumerates
its own claims and names the rows behind each; the engine checks that those
rows were actually read this reply, which is a set membership test over
ids the engine itself served. Nor is it a restriction on what the room may
PROPOSE -- an unsupported claim is refused as an assertion and kept as a
suggestion, which is what it always was.

THE LEDGER OF WHAT WAS READ is filled by `story/room_tools.run_tool`, the
one call site every read passes through, and lives for one reply. A row the
room did not read this reply cannot be cited this reply -- deliberately:
the failure mode is a room recapping from what it remembers of an earlier
session, and memory is not a ledger.
"""

from __future__ import annotations

import contextlib
import contextvars

#: THE ID KEYS a tool result carries, a closed set the engine owns: the
#: field names its own readers use for the identity of a row. Harvesting is
#: deliberately GENEROUS -- an id missed here makes an honest claim look
#: unsupported, which is the expensive direction of the error, while an id
#: gathered that nobody would cite costs a set entry.
ID_KEYS = ("uid", "id", "room", "room_id", "to", "entry_id", "need_uid",
           "package_uid", "mandate_uid", "charter", "body", "post", "key",
           "subject_id", "book_id", "char_id", "turn_id", "structure")

#: Rows remembered per reply. A LIMIT THE OWNER SHOULD KNOW ABOUT: past it
#: further reads are not remembered and a claim citing one of them reads as
#: unsupported. Set well above the largest measured reply (chat 114's
#: seventeen-tool reply gathered a few hundred), so reaching it means a
#: reply that read a whole map, and the honest answer for that reply is
#: that the room can no longer say which row it meant.
ROWS_READ_CAP = 20_000

#: How deep into a tool result the harvest walks. A result is JSON the
#: engine composed, not arbitrary data; nothing it returns nests an id
#: deeper than this.
HARVEST_DEPTH = 8

#: The verdicts a claim can carry.
VERDICTS = ("supported", "unsupported", "proposal")

#: The contract, in the words the room is given it in. It lives here rather
#: than in the prompt card so that the sentence the room is held to and the
#: check that holds it cannot drift apart.
CONTRACT_TEXT = (
    "Anything you state as fact about the story comes from a row you read "
    "in this reply, and you name the row: put each such statement in "
    "`claims`, as {text, cites: [the ids of the rows it came from]}. "
    "Anything you are suggesting, guessing at, or inventing is a proposal "
    "and needs no row: mark it {text, proposal: true}. Where you have no "
    "row for something, say you have none -- that sentence is worth more "
    "than a composed one, and a claim naming no row you read is recorded "
    "as a proposal whatever it says.")

_rows_read: contextvars.ContextVar = contextvars.ContextVar(
    "room_rows_read", default=None)


@contextlib.contextmanager
def reading():
    """One reply's ledger of rows read. Nested scopes do not stack: the
    innermost owns the reply, because a reply is the unit a claim is
    checked against."""
    token = _rows_read.set(set())
    try:
        yield
    finally:
        _rows_read.reset(token)


def enter_reading() -> None:
    """Open a reply's ledger for the REST OF THIS CONTEXT, with no close.

    The pair to `reading` for a worker thread: the room's streamed reply
    makes its calls in a thread, and a ContextVar set outside it is not
    visible there. Nothing has to close it, because the thread's context is
    a copy and dies with the reply.
    """
    _rows_read.set(set())


def rows_read() -> set:
    """The rows read so far this reply, or an empty set outside a reply."""
    rows = _rows_read.get()
    return set(rows) if rows else set()


def note_reads(tool, result) -> int:
    """Remember every row id one tool result served. Returns how many were
    new. No-op outside a `reading` scope, and never raises: a room that
    cannot record what it read must still be able to read."""
    rows = _rows_read.get()
    if rows is None:
        return 0
    before = len(rows)
    try:
        _harvest(result, rows, 0)
    except Exception:
        return len(rows) - before
    return len(rows) - before


def _harvest(value, rows, depth):
    if depth > HARVEST_DEPTH or len(rows) >= ROWS_READ_CAP:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            # A mapping FROM ids to records -- `read_scene`'s rooms, the
            # entity table -- carries its ids in its keys, which is the
            # other half of how this engine spells a row.
            if isinstance(item, dict):
                _add(rows, key)
            if key in ID_KEYS:
                _add(rows, item)
            _harvest(item, rows, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _harvest(item, rows, depth + 1)


def _add(rows, value):
    if isinstance(value, str) and value.strip() and len(rows) < ROWS_READ_CAP:
        rows.add(value.strip())


def normalize_claim(entry):
    """One claim as the room states it: what it says, what it cites, and
    whether it is offered as a proposal at all."""
    entry = entry if isinstance(entry, dict) else {"text": entry}
    cites = entry.get("cites")
    if isinstance(cites, str):
        cites = [cites]
    return {
        "text": " ".join(str(entry.get("text") or "").split()),
        "cites": [str(c).strip() for c in cites or () if str(c or "").strip()],
        "proposal": bool(entry.get("proposal")),
    }


def check_claims(claims, *, rows=None):
    """Check what the room stated against what it read.

    Returns ``{"claims": [...], "asserted": [...], "proposed": [...],
    "unsupported": [...]}``: every claim with a verdict and the cites that
    named nothing, then the three readings of the same list. A claim is

      * `proposal` when it says it is one -- no row is asked for, and none
        is checked;
      * `supported` when every row it cites was read this reply;
      * `unsupported` otherwise, WHICH INCLUDES CITING NOTHING AT ALL, and
        is then reported among the proposals rather than the assertions.

    A reply with no claims at all is not an error and not a pass: it is
    reported as `stated_nothing`, because a room that enumerated nothing
    has told us nothing about what it asserted, and pretending that is a
    clean bill would be the same silence the contract exists to end.
    """
    rows = rows_read() if rows is None else set(rows)
    out = []
    for raw in claims or ():
        claim = normalize_claim(raw)
        if not claim["text"]:
            continue
        if claim["proposal"]:
            claim["verdict"] = "proposal"
            claim["missing"] = []
        else:
            missing = [c for c in claim["cites"] if c not in rows]
            uncited = not claim["cites"]
            claim["missing"] = missing
            claim["verdict"] = ("unsupported" if (missing or uncited)
                                else "supported")
            claim["uncited"] = uncited
        out.append(claim)
    return {
        "claims": out,
        "rows_read": len(rows),
        "stated_nothing": not out,
        "asserted": [c["text"] for c in out if c["verdict"] == "supported"],
        # An unsupported claim is a proposal now. That is the demotion, and
        # it is the whole enforcement: the room keeps its sentence and
        # loses the authority it was borrowing.
        "proposed": [c["text"] for c in out if c["verdict"] != "supported"],
        "unsupported": [c["text"] for c in out if c["verdict"] == "unsupported"],
    }
