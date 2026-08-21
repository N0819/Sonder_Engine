"""Figures: people the institution can know without owning.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §12a. The player and the
major characters walk through a charter's world, and for a background body to
interact with them believably ACROSS encounters it must accumulate a view of
them — first-hand where it saw them, second-hand where it was told, decaying,
and capable of being wrong. Until now that view was structurally impossible:
``minds`` could only hold claims about bodies and news, so the person the
story is actually about was the one thing nobody off-screen could know.

A figure is deliberately NOT a body. It is not rostered, not planned, not
needed by any post, never blamed by ``attribute_blame`` (blame follows the
watch, and a figure stands no watch), and it has NO MIND HERE. Its knowledge,
memory and psychology live in the engine's own character machinery — copying
any of that into ``minds`` would be a second representation of a mind the
engine already owns, drifting from the first from the moment it was made.
What the charter holds is only what its bodies could coarsely perceive:
presence at a place, and an authored public ``surface``.

THE CLAIM IS THE SAME CLAIM. A sighting mints a record in the same ``minds``
dict, discriminated by ``kind`` exactly as news is, so figure claims travel on
``tell``/``ask``, decay under ``decay_minds``, count against ``RECALL_CAP``,
and surface in ``scene_ledger`` without one line of parallel machinery. A
body that saw the traveller at the gate tells the miller; the miller holds it
thinner, second-hand, stamped with who said so; both claims go stale where
the traveller does not stand still. That staleness is the feature: "capable
of being wrong" is what makes recognition mean something.
"""

from __future__ import annotations


def normalize_figures(stored):
    """``{key: figure}`` from any shape. A figure with no place is away —
    known, perhaps still believed present somewhere, but nowhere a body can
    see."""
    out = {}
    for key, entry in (stored or {}).items():
        key = str(key or "").strip()
        if not key:
            continue
        entry = entry if isinstance(entry, dict) else {}
        out[key] = {
            "key": key,
            "place": str(entry.get("place") or ""),
            # What a coarse witness gets: whatever the author says is
            # publicly visible about this person. Opaque to this package —
            # the engine does not read it, it only carries it into claims.
            "surface": dict(entry.get("surface") or {}),
        }
    return out


def figure_claim(figure, at_hours, strength=1.0, heard_from=None):
    """What laying eyes on a figure leaves in a head.

    ``place`` is where the figure was WHEN SEEN, not where it is — the claim
    does not update when the figure moves, which is precisely how a body
    comes to believe the traveller is still at the gate an hour after the
    traveller left.
    """
    return {
        "kind": "figure",
        "body": str(figure["key"]),
        "place": str(figure.get("place") or ""),
        "surface": dict(figure.get("surface") or {}),
        "strength": float(strength),
        "as_of_hours": float(at_hours),
        "heard_from": str(heard_from) if heard_from else None,
    }


def sight_figures(minds, bodies, figures, at_hours):
    """Bodies standing where a figure stands come to know it. Returns minds.

    Presence is the whole test, the same rule witnessing news follows: no
    timer, no broadcast, and nobody learns of a figure it never shared a
    room with. Every body present sees — figures are few and salient, and
    a stranger walking into the room is exactly the thing everyone in it
    notices. Refreshing an existing first-hand claim is deliberate: a body
    the figure keeps visiting keeps a current picture, which is what makes
    the shopkeeper's recognition differ from the miller's rumour.
    """
    for fig_key in sorted(figures or {}):
        figure = figures[fig_key]
        place = str(figure.get("place") or "")
        if not place:
            continue
        for body_key in sorted(bodies or {}):
            if str((bodies[body_key] or {}).get("place") or "") != place:
                continue
            held = minds.setdefault(str(body_key), {})
            current = held.get(fig_key)
            if current is not None and current.get("heard_from") is None \
                    and float(current.get("strength") or 0.0) >= 1.0 \
                    and str(current.get("place") or "") == place:
                continue
            held[fig_key] = figure_claim(figure, at_hours)
    return minds


def known_figures(minds, holder):
    """The figures one head currently holds a view of, strongest first."""
    claims = [c for c in (minds.get(str(holder)) or {}).values()
              if c.get("kind") == "figure"]
    claims.sort(key=lambda c: (-float(c.get("strength") or 0.0),
                               str(c.get("body") or "")))
    return claims


def figure_spread(minds, fig_key):
    """``(holders, secondhand)`` for one figure — how far a person has
    travelled through the town's heads, and how much of that is rumour."""
    holders = [c for claims in (minds or {}).values()
               for s, c in claims.items()
               if s == str(fig_key) and c.get("kind") == "figure"]
    return len(holders), sum(1 for c in holders if c.get("heard_from"))


def stale_figure_claims(minds, figures):
    """``[(holder, figure)]`` where a head believes a figure somewhere it is
    not. Diagnostics — the measurement that "capable of being wrong" is
    real, never an input to anything."""
    wrong = []
    for holder, claims in (minds or {}).items():
        for subject, claim in claims.items():
            if claim.get("kind") != "figure":
                continue
            figure = (figures or {}).get(subject)
            if figure is None:
                continue
            if str(claim.get("place") or "") != str(figure.get("place") or ""):
                wrong.append((holder, subject))
    return sorted(wrong)


__all__ = [
    "figure_claim", "figure_spread", "known_figures", "normalize_figures",
    "sight_figures", "stale_figure_claims",
]
