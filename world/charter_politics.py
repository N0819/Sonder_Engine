"""Standing, regard, and blame — who gets believed and who gets posted.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §5, the half that is not
about competence. An institution is not a sorting algorithm over skills. Who
is believed, who is spared, and who is blamed when something fails are
decisions it makes about people, and they are the decisions that make an
institution feel like one.

Three quantities, all of them plain numbers, none of them naming a genre:

  * **regard** — ``(a, b)`` how much a weighs what b says. Scales a gossiped
    claim in ``charter_talk``. Nobody's regard for themselves is modelled;
    a body hears itself at full strength by standing its own post.
  * **standing** — how much weight a body's word carries generally, and how
    reluctant the charter is to spend them on menial posts. A chief is not
    rostered to the well.
  * **blame** — where a failure attaches. NOT where it belongs: blame lands
    on whoever was posted, or on whoever was believed to be, and the
    difference between those two is a story.

BLAME IS A BELIEF, NOT A VERDICT. This module records who the institution
holds responsible, which may be exactly wrong — the classic case being a body
blamed for a post it was never at, because the roster said it was. The engine
does not adjudicate; it records what the institution concluded and lets that
shape who is believed next.
"""

from __future__ import annotations

#: Regard's neutral value: a claim arrives at face value from a stranger.
NEUTRAL_REGARD = 1.0

#: The band regard is held inside. A floor above zero because total disbelief
#: makes a body socially invisible and the roster then cannot be corrected by
#: anyone they talk to; a ceiling because a single trusted voice must not be
#: able to overwrite the institution's whole picture.
REGARD_FLOOR = 0.3
REGARD_CEILING = 1.6

#: What being blamed costs, per incident, in everyone else's regard.
BLAME_COST = 0.15

#: What standing does to the reluctance to spend somebody. Multiplies the
#: `criticality` cost a planner already pays, so a high-standing body is
#: treated as scarcer than their competence alone implies.
STANDING_WEIGHT = 1.0


def normalize_politics(stored):
    """Regard, standing and blame, from any shape."""
    stored = stored if isinstance(stored, dict) else {}
    regard = {}
    for key, value in (stored.get("regard") or {}).items():
        if isinstance(key, (list, tuple)) and len(key) == 2:
            pair = (str(key[0]), str(key[1]))
        elif isinstance(key, str) and "->" in key:
            left, right = key.split("->", 1)
            pair = (left.strip(), right.strip())
        else:
            continue
        regard[pair] = _clamp_regard(value)
    return {
        "regard": regard,
        "standing": {str(k): float(v)
                     for k, v in (stored.get("standing") or {}).items()},
        "blame": {str(k): int(v)
                  for k, v in (stored.get("blame") or {}).items()},
    }


def _clamp_regard(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return NEUTRAL_REGARD
    return max(REGARD_FLOOR, min(REGARD_CEILING, value))


def regard_between(politics, listener, speaker):
    return _clamp_regard(
        (politics.get("regard") or {}).get(
            (str(listener), str(speaker)), NEUTRAL_REGARD))


def regard_map(politics):
    """The ``{(listener, speaker): weight}`` `charter_talk` asks for."""
    return dict(politics.get("regard") or {})


def spend_reluctance(politics, body):
    """Extra scarcity a planner should attribute to this body.

    Standing is not competence and must not be able to make somebody
    unpostable — it makes them EXPENSIVE, which the planner already knows how
    to weigh. A charter short of hands still posts the chief; it simply posts
    everyone else first.
    """
    standing = float((politics.get("standing") or {}).get(str(body), 0.0))
    return STANDING_WEIGHT * max(0.0, standing)


def attribute_blame(politics, events, watch):
    """Where the institution decides a failure came from. Returns new politics.

    Blame follows the WATCH, which is what the charter believed it had
    arranged — so a body blamed here may have been nowhere near the place.
    That is the intended failure: the roster said they were on it, the thing
    failed, and the institution knows who to be angry with. Correcting that
    belief is somebody else's job and may never happen.
    """
    politics = normalize_politics(politics)
    blame = dict(politics["blame"])
    regard = dict(politics["regard"])

    serving = {}
    for post_key, body_key in (watch or {}).items():
        serving.setdefault(post_key, body_key)

    for event in events or []:
        if event.get("kind") != "upkeep_out_of_band":
            continue
        # An upkeep starved by an input is not the post-holder's doing, and an
        # institution that blamed the baker for the miller's empty hopper
        # would be one this module got wrong. Blame stops at the first link
        # that had a body on it.
        if event.get("starved_by"):
            continue
        for post_key, body_key in serving.items():
            blame[body_key] = blame.get(body_key, 0) + 1
            for other in {b for b in serving.values()} | set(blame):
                if other == body_key:
                    continue
                pair = (str(other), str(body_key))
                regard[pair] = _clamp_regard(
                    regard.get(pair, NEUTRAL_REGARD) - BLAME_COST)
            break

    return {"regard": regard, "standing": dict(politics["standing"]),
            "blame": blame}
