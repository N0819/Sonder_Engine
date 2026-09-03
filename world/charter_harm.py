"""What being hurt, killed or taken does to a body, and to the institution
that counted on it.

``docs/design/DESIGN_CREATURES_AS_CHARTER.md`` §2. Until this existed the
package had every CONSEQUENCE of harm and no producer: `harm_done` was in
`charter_news.WITNESSABLE`, in `charter_practice.GRIEVANCE_KINDS` (the
actor is the answerable party), in `charter_social.DEFAULT_SIGNALS` (fear,
suspicion, lost trust) and in `charter_trigger.TRIGGER_EMITTABLE` -- and the
only thing in the repository that ever emitted one was an authored trigger
rule. A body could be starved to a standstill and could never be hurt.

ONE FIELD, CLOSED. A body's ``condition`` is one of `CONDITIONS`. ``well`` is
the default and is what every body written before this field existed reads
as. ``hurt`` is temporary and recovers on a named clock; ``dead`` and
``missing`` are final in this module's vocabulary and are what makes
``available`` false without `charter_needs` ever picking the body up again
(`advance_needs` recovers only a body NEEDS put down, and says so).

WHAT A DEATH DOES TO THE INSTITUTION, in the vocabulary it already has:

  * the body is unavailable, so the planner stops posting it and its post
    is reported unfilled or restaffed like any other absence;
  * its berth is freed, so `charter_generate`'s berth ceiling counts one
    fewer sleeper there and a later body may be berthed in its place;
  * if it held a HEAD post -- one nobody reports past and somebody reports
    to, `charter_generate._head_posts`'s own rule restated -- a successor is
    chosen by standing (`charter_politics`) and given the post as their
    ``home_post``, so the planner's own preference for a body's ordinary
    duty carries the office to the next in line. That is succession through
    politics, and it is one event (``succession``) in the register;
  * a ``harm_done`` event is emitted at the place, which is NEWS to whoever
    stood there (`charter_news.witness`), a GRIEVANCE against the actor
    (`charter_practice.grievance_against`), fear in every judgment formed
    from it (`charter_social`), and the change a `charter_trigger` rule may
    fire on. Nothing here writes into a head: the event is objective and
    every question of who knows is asked where it always was.

Pure and deterministic. No clock beyond what it is handed, no model.
"""

from __future__ import annotations

#: A body's condition. Closed: a reader that meets a word outside this set
#: reads ``well``, so a charter written before the field existed is whole.
CONDITIONS = ("well", "hurt", "dead", "missing")

#: The two conditions that take a body off the roster for good, as far as
#: this package can tell. A story may write the body back (authoring is not
#: this module's to refuse); the simulation never does.
GONE = frozenset({"dead", "missing"})

#: What a hurt body is worth in a contest, as a fraction of a well one.
HURT_CAPABILITY = 0.5

#: Hours a hurt body takes to read ``well`` again. A named rate rather than
#: a need, so it recovers whether or not the institution has a medical post:
#: the ``health`` need already exists for the institution that tends its
#: wounded, and a hurt body's health is knocked down to `HURT_HEALTH_LEVEL`
#: so that post has something to serve.
HURT_RECOVERY_HOURS = 72.0

#: Where a fresh hurt puts the ``health`` need (`charter_needs`), at most.
#: Above the default floor (0.20) on purpose: a hurt body can still stand a
#: post, it is just spent more reluctantly and fights worse.
HURT_HEALTH_LEVEL = 0.5

#: Extra reluctance the planner attributes to a hurt body, on the same axis
#: standing and exhaustion already ride (`charter_run.step`).
HURT_RELUCTANCE = 0.75

#: What a posted body and an unposted one are worth in a contest before any
#: authored weight. THE ENGINE'S OWN CATEGORY: a body on a post is somebody
#: standing where the institution put them, awake and answerable; a body off
#: the bill is on an errand or asleep. Nothing here knows what a guard is.
POSTED_CAPABILITY = 1.0
UNPOSTED_CAPABILITY = 0.4


def normalize_condition(value):
    text = str(value or "").strip().casefold()
    return text if text in CONDITIONS else "well"


def is_gone(body):
    return normalize_condition((body or {}).get("condition")) in GONE


def capability_of(body, *, posted, weights=None):
    """What one body brings to a contest, from the two facts that are
    objective: whether it is on a post, and whether it is hurt."""
    weights = weights or {}
    base = (float(weights.get("posted_weight", POSTED_CAPABILITY)) if posted
            else float(weights.get("unposted_weight", UNPOSTED_CAPABILITY)))
    if normalize_condition((body or {}).get("condition")) == "hurt":
        base *= HURT_CAPABILITY
    return max(0.0, base)


def head_posts(posts):
    """The posts nobody reports past and somebody reports to.

    `charter_generate._head_posts`'s rule, restated here rather than imported
    because that module carries the planner's model calls and this one must
    stay pure. A self-report counts as no superior; a post with no
    subordinate is a lone watch, not a head.
    """
    superiors = {}
    for key, post in (posts or {}).items():
        if not isinstance(post, dict):
            continue
        superior = str(post.get("reports_to") or "")
        if superior and superior != str(key):
            superiors[str(key)] = superior
    reported_to = set(superiors.values())
    return sorted(key for key in reported_to
                  if key in (posts or {}) and key not in superiors)


def _successor(charter, post_key, gone_key):
    """Who takes a head post when its holder is gone: the available body of
    highest standing, ties to the most competent for the post, then by key.
    Standing is `charter_politics`' number and nothing else is read."""
    from .charter_model import meets

    standing = ((charter.get("politics") or {}).get("standing") or {})
    post = (charter.get("posts") or {}).get(post_key) or {}
    best = None
    for key, body in sorted((charter.get("bodies") or {}).items()):
        if key == gone_key or not body.get("available", True) \
                or is_gone(body):
            continue
        fit = 1 if meets(body.get("competence"), post.get("requires")) else 0
        candidate = (float(standing.get(key, 0.0)), fit, key)
        if best is None or (candidate[0], candidate[1]) > (best[0], best[1]) \
                or ((candidate[0], candidate[1]) == (best[0], best[1])
                    and key < best[2]):
            best = candidate
    return best[2] if best else ""


def apply_harm(charter, victim, *, by, at_hours, outcome="hurt", place=None,
               cause="", copy_state=True):
    """One body harmed. Returns ``(charter, events)``; never mutates its
    input unless ``copy_state`` is False.

    ``outcome`` is ``hurt``, ``dead`` or ``missing``. ``by`` names the actor
    as the victim's own institution can name it -- a body key of its own, or
    the qualified id of a body elsewhere (`charter_runtime.person_id`) --
    and it is the `actor` of the emitted event, which is what makes the
    grievance land on the right party.

    ``copy_state=False`` mutates the charter handed in. It exists for the
    registry round, which owns its states outright: a deep copy of a
    thousand-body town on every kill measured as most of the round's cost
    (big_town, 48 hours: +2.4s over the town alone, for two kills).
    """
    import copy

    outcome = normalize_condition(outcome)
    if outcome == "well":
        return charter, []
    if copy_state:
        charter = copy.deepcopy(charter)
    bodies = charter.setdefault("bodies", {})
    body = bodies.get(str(victim))
    if body is None or is_gone(body):
        return charter, []
    victim = str(victim)
    at = round(float(at_hours), 6)
    where = str(place or body.get("place") or "")
    events = []
    if outcome == "hurt":
        if normalize_condition(body.get("condition")) != "hurt":
            body["condition"] = "hurt"
            body["hurt_at_hours"] = at
        held = (charter.get("needs") or {}).get(victim) or {}
        health = held.get("health")
        if isinstance(health, dict):
            health["level"] = min(float(health.get("level", 1.0)),
                                  HURT_HEALTH_LEVEL)
    else:
        body["condition"] = outcome
        body["available"] = False
        body["stood_down"] = False
        body.pop("walk", None)
        body.pop("hurt_at_hours", None)
        if outcome == "dead":
            body["berth"] = ""
        else:
            body["place"] = ""
        watch = dict(charter.get("watch") or {})
        held_posts = sorted(post for post, who in watch.items()
                            if str(who) == victim)
        for post_key in held_posts:
            watch.pop(post_key, None)
        charter["watch"] = watch
        heads = set(head_posts(charter.get("posts")))
        for post_key in held_posts:
            if post_key not in heads:
                continue
            heir = _successor(charter, post_key, victim)
            if not heir:
                continue
            bodies[heir]["home_post"] = post_key
            politics = charter.setdefault("politics", {})
            standing = politics.setdefault("standing", {})
            others = [float(v) for k, v in standing.items() if k != heir]
            standing[heir] = max([float(standing.get(heir, 0.0))]
                                 + [v + 1.0 for v in others] + [1.0])
            events.append({
                "kind": "succession", "at_hours": at,
                "place": str(((charter.get("posts") or {}).get(post_key)
                              or {}).get("place") or where),
                "post": post_key, "body": heir, "after": victim,
            })
    events.insert(0, {
        "kind": "harm_done", "at_hours": at, "place": where,
        # `about`/`actor`/`body` all name the ACTING party -- the shape
        # `charter_run._social_events` writes and every reader takes --
        # and `subject` is whom it was done to.
        "about": str(by), "actor": str(by), "body": str(by),
        "subject": victim, "outcome": outcome,
        **({"cause": str(cause)[:120]} if cause else {}),
    })
    return charter, events


def advance_harm(charter, at_hours):
    """Hurt bodies past `HURT_RECOVERY_HOURS` read well again.

    Returns ``(charter, recovered)``; never mutates its input. A body that
    was hurt keeps its ``health`` need wherever the institution's tending
    left it -- the clock heals the condition, the post heals the need.
    """
    import copy

    at = float(at_hours)
    recovered = []
    out = None
    for key, body in sorted((charter.get("bodies") or {}).items()):
        if normalize_condition(body.get("condition")) != "hurt":
            continue
        since = body.get("hurt_at_hours")
        try:
            since = float(since)
        except (TypeError, ValueError):
            since = at
        if at - since < HURT_RECOVERY_HOURS:
            continue
        if out is None:
            out = copy.deepcopy(charter)
        healed = out["bodies"][key]
        healed["condition"] = "well"
        healed.pop("hurt_at_hours", None)
        recovered.append(key)
    return (out if out is not None else charter), recovered


__all__ = [
    "CONDITIONS", "GONE", "HURT_CAPABILITY", "HURT_HEALTH_LEVEL",
    "HURT_RECOVERY_HOURS", "HURT_RELUCTANCE", "POSTED_CAPABILITY",
    "UNPOSTED_CAPABILITY", "advance_harm", "apply_harm", "capability_of",
    "head_posts", "is_gone", "normalize_condition",
]
