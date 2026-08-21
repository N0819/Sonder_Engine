"""What the charter BELIEVES about its people. Not what is true about them.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §5. The charter never reads a
body's ground truth. It reads a roster record with its own competence claim, an
availability claim, a strength, and a stamp -- and any of those may be stale or
wrong.

This is not firewall pedantry, it is where the material is. A charter with
ground truth about its crew assigns perfectly and produces a machine. A charter
with beliefs assigns the man who transferred out two months ago, leaves the
post silently unfilled, and produces an institution.

The same asymmetry as the rest of the engine: knowing is channelled. A roster
entry improves when somebody OBSERVES the body -- stands a watch beside it,
sees it in medical -- and decays otherwise.
"""

from __future__ import annotations

from .charter_model import meets, normalize_competence

#: Below this a roster claim is too weak to assign against. It is not
#: forgotten -- the charter still holds the belief, it simply will not stake a
#: post on it, which is what a chief does with a name they are no longer sure
#: of.
TRUST_FLOOR = 0.2

#: How much of its strength a claim loses per hour with nobody confirming it.
#: Small: rosters go stale over shifts, not minutes.
DECAY_PER_HOUR = 0.004

#: What a register entry never decays below. A ROSTER IS WRITTEN DOWN — it
#: does not forget a name the way a head forgets a face, it only stops being
#: sure the name is current. Below `TRUST_FLOOR` so an unconfirmed body is not
#: staked on a post, and above zero so it is never erased: the chief still has
#: the name and will not roster it without somebody vouching.
#:
#: Measured on the 500-hand fixture: without this the register held 1.0 for
#: the two dozen bodies standing posts and 0.0 for everyone else, which is an
#: institution that had struck 95% of its own crew off the books while they
#: were aboard and at work.
ARCHIVE_FLOOR = 0.05


def seed_roster(bodies, strength=1.0):
    """A roster that currently happens to be correct.

    The starting point for a test or a fresh institution. Correctness here is
    a coincidence of the seed, not a property of the type -- everything
    downstream must keep working when these claims drift away from the bodies.
    """
    return {
        key: {
            "body": key,
            "competence": dict(body["competence"]),
            "believed_available": bool(body["available"]),
            "strength": float(strength),
            "as_of_hours": 0.0,
        }
        for key, body in (bodies or {}).items()
    }


def decay_roster(roster, hours):
    """Time passing, with nobody confirming anything."""
    hours = max(0.0, float(hours))
    out = {}
    for key, record in (roster or {}).items():
        record = dict(record)
        record["strength"] = max(
            ARCHIVE_FLOOR,
            float(record.get("strength") or 0.0) - DECAY_PER_HOUR * hours)
        out[key] = record
    return out


def observe(roster, body, at_hours, strength=1.0):
    """Somebody saw this body, so the charter's claim about it is refreshed.

    The one legitimate way a roster becomes accurate again. Nothing else in
    this package writes a roster entry from ground truth.
    """
    roster = dict(roster or {})
    roster[body["key"]] = {
        "body": body["key"],
        "competence": normalize_competence(body["competence"]),
        "believed_available": bool(body["available"]),
        "strength": float(strength),
        "as_of_hours": float(at_hours),
    }
    return roster


def assignable(roster, requirement):
    """Body keys the charter would stake a post on, best-believed first.

    Ground truth is not consulted. A body that is in fact unavailable but
    believed available is returned here, and the post it is given will simply
    not be tended -- which is the silent-unfilled case that makes rosters
    matter.
    """
    out = []
    for key, record in (roster or {}).items():
        if float(record.get("strength") or 0.0) < TRUST_FLOOR:
            continue
        if not record.get("believed_available"):
            continue
        if not meets(record.get("competence"), requirement):
            continue
        out.append(key)
    # Strongest belief first, then by key so the order is total and stable --
    # an assignment that depended on dict ordering could not be replayed.
    out.sort(key=lambda k: (-float(roster[k].get("strength") or 0.0), k))
    return out


def stale_claims(roster, bodies):
    """Roster entries that no longer match the world, for diagnostics only.

    NOT consulted by the planner -- if the charter could see this it would
    have ground truth by the back door. It exists so a test can assert that a
    misassignment happened for the reason the design says it should.
    """
    wrong = []
    for key, record in (roster or {}).items():
        body = (bodies or {}).get(key)
        if body is None:
            wrong.append((key, "no such body"))
            continue
        if bool(record.get("believed_available")) != bool(body["available"]):
            wrong.append((key, "availability"))
        elif dict(record.get("competence") or {}) != dict(body["competence"]):
            wrong.append((key, "competence"))
    return wrong
