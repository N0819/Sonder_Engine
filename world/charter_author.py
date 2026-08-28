"""The author-switch: conduct written from outside, landing inside.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §12a. A background body
that walks on screen is not handed over to anything: its needs keep
draining, its feeling keeps resolving, its position keeps being its
position. What changes for a stretch is who WRITES ITS CONDUCT — and this
module is that switch, for the stretch between planning windows where a
scene actually happens.

Two directions, deliberately asymmetric, and the asymmetry is the firewall
shaping the API rather than a wart on it:

  * **A voiced BODY acts** (the scene manager writes a background NPC's
    line): the act resolves through ``charter_practice``'s own builders and
    effects — the identical path a utility-chosen act takes, with the
    identical licences. There is no parallel apply-function to drift from
    the chooser's, which is §12a's first requirement, and an act the state
    does not license is refused with a reason, never applied and never
    silently dropped.
  * **A FIGURE acts** (the player or a major character does something to a
    body): the figure has no mind here — its knowledge lives in the
    engine's own character machinery, and simulating its uptake would be a
    second copy of a mind that already exists. So a figure's acts touch
    only what a body could actually receive from them: a greeting opens the
    situation, a telling arrives through ``charter_mind.hear_claim`` — the
    ONE uptake door, same retention, same regard scaling, same
    stronger-holding-wins rule — an accusation lands in ``heard_blame``,
    a tending services a need. Nothing writes ``minds[figure]``, ever.

Situations open by circumstance here exactly as they do in
``opportunities``: an author bringing two people into speaking distance IS
the circumstance a greeting exists for, so a fresh encounter does not
require a planning window to have noticed the pair first. The situation
opened is the same situation, with the same key, that the window would have
opened — an authored meeting and a simulated one leave the same record.

Pure, like the rest of the package: takes a charter, returns a new charter
and a record. Commit is the reduction point that decides whether the record
becomes a ``world_events`` row; nothing here writes storage.
"""

from __future__ import annotations

from .charter_figure import figure_claim
from .charter_mark import advance_marks
from .charter_mind import hear_claim
from .charter_model import normalize_charter
from .charter_politics import normalize_politics, regard_map, regard_value
from .charter_practice import (
    ASKED_RETENTION,
    REFUSED_ABSENT,
    REFUSED_NO_SITUATION,
    REFUSED_OUTSIDE_LICENCE,
    REFUSED_UNABLE,
    _by_body,
    _offer_for,
    landed_effect,
    _open,
    _state_of,
    _whereabouts,
    normalize_practices,
    offers,
)

#: Acts a figure can author toward a body. The body-actor set is whatever
#: `charter_practice._AFFORDANCES` offers — one vocabulary, read from the
#: same table the chooser reads.
FIGURE_ACTS = ("greet", "ask", "tell", "accuse", "tend")


def _refusal(actor, act, other, reason):
    return {"actor": str(actor), "act": str(act), "other": str(other),
            "refused": reason}


def _pair_situations(actor, other, place, minds, needs, bodies, practices,
                     at_hours):
    """The situations this pair's circumstance licenses, opened if absent.

    The same kinds `opportunities` opens, for the one pair the author has
    brought together: a greeting between strangers, a conversation between
    acquaintances, a tending over somebody down. Deterministic keys, so an
    authored meeting and a window-opened one are the same situation.
    """
    opened = {}
    known = (minds.get(actor) or {}).get(other)
    kind = "converse" if known else "greeting"
    key, entry = _open(kind, place, {"a": actor, "b": other}, at_hours)
    if key not in practices:
        opened[key] = entry
    target = bodies.get(other)
    if target is not None and not target.get("available") \
            and (needs or {}).get(other):
        key, entry = _open("tending", place, {"a": actor, "b": other},
                           at_hours, about=other)
        if key not in practices:
            opened[key] = entry
    return opened


def authored(charter, actor, act, other, claim=None, retention=None):
    """One authored act, through the same machinery a chosen one uses.

    Returns ``(charter, record)`` — the record carries ``line`` when the act
    landed and ``refused`` with a reason when the state does not license it.
    A refused act changes nothing: the returned charter is the input,
    normalized, and a test pins that as byte-identical.

    ``claim`` is required only for a FIGURE telling a body something: the
    content of an authored telling comes from the author, and it arrives as
    a claim — provisional, decaying, refusable — through the same uptake
    door a body-to-body telling uses. ``retention`` defaults to
    ``ASKED_RETENTION``: a body in conversation with you is listening.
    """
    charter = normalize_charter(charter)
    actor, act, other = str(actor), str(act or ""), str(other or "")
    at = float(charter["clock_hours"])

    bodies = charter["bodies"]
    figures = charter["figures"]
    minds = charter["minds"]
    needs = charter["needs"]
    politics = normalize_politics(charter.get("politics"))
    regard = dict(politics.get("regard") or {})
    blame = dict(politics.get("blame") or {})
    practices = normalize_practices(charter.get("practices"))
    heard_blame = {k: set(v) for k, v in
                   (charter.get("heard_blame") or {}).items()}
    # Snapshotted BEFORE `_figure_act`, which writes into `heard_blame`
    # directly rather than through `state`. The `accused` onset below is the
    # delta on the merged set for exactly that reason: a figure's accusation
    # and a body's arrive by two different doors and both are the same fact.
    heard_before = {k: set(v) for k, v in heard_blame.items()}

    state = _state_of(bodies, minds, needs, regard, blame, at,
                      figures=figures,
                      experiences=charter.get("experiences"),
                      served_beside=charter.get("served_beside"),
                      judgments=charter.get("judgments"),
                      commitments=charter.get("commitments"))

    if actor in bodies:
        record = _body_act(actor, act, other, bodies, state, practices,
                           minds, needs, at)
    elif actor in figures:
        record = _figure_act(actor, act, other, figures, bodies, state,
                             practices, minds, needs, heard_blame, at,
                             claim=claim, retention=retention)
    else:
        record = _refusal(actor, act, other, REFUSED_ABSENT)

    if record.get("refused"):
        return charter, record

    for key, entry in state["spawned"]:
        practices.setdefault(key, entry)
    for key in state["closed"]:
        practices.pop(key, None)
    for subject, tellers in state["heard_blame"].items():
        heard_blame.setdefault(subject, set()).update(tellers)

    # THE SAME MARKS THE ENACT PATH MINTS (`RESEARCH.md` §1.7.6 item 4), from
    # the same two origins, because an authored act and a chosen one leave the
    # same record -- that is this module's whole contract. Without it the
    # accusation a FIGURE makes would set `heard_blame` and no mark, and the
    # next `step` would see no delta because the store had already absorbed
    # the telling: measured, a figure accusing a body is today the ONLY
    # reachable accusation outside a charter whose register already blames
    # somebody, so the author path is where most of them come from.
    #
    # `at` rather than `at + hours`: no time passes in an authored act, so the
    # onset hour is the clock the store will be pruned against next window.
    #
    # AND FILTERED BY `bindings`, exactly as `charter_run.step` filters its
    # four onset lists (`charter_run.py` §"AND FILTERED BY `external`") and as
    # `charter_runtime.bind_promoted_character` pops the store at binding: a
    # promoted body's interior has exactly one owner, and a Charter mark is a
    # scoring bias, which is cognition. Without this the author path was the
    # one writer of the store that did not check -- verified by execution on
    # the yard fixture: with `bindings = {"raul": ...}`,
    # `authored(charter, "ilse", "accuse", "raul")` returned
    # `marks = {"raul": {"accused": ...}}`, which then rode `normalize_charter`
    # (it filters to live `bodies`, not to unbound ones) onto
    # `charter_log.scene_ledger`'s presence slice, surviving the promotion
    # purge that had already run.
    external = set((charter.get("bindings") or {}).keys())
    aided = [(other, actor)] if record.get("act") == "tend" \
        and other in bodies and other not in external else []
    accused = sorted(
        (subject, sorted(tellers - heard_before.get(subject, set()))[0])
        for subject, tellers in heard_blame.items()
        if tellers - heard_before.get(subject, set())
        and subject not in external)
    charter["marks"] = advance_marks(
        charter.get("marks"), at, aided=aided, accused=accused)[0]

    charter["practices"] = practices
    charter["minds"] = minds
    charter["needs"] = needs
    charter["heard_blame"] = {k: sorted(v) for k, v in heard_blame.items()}
    charter["politics"] = {"regard": regard,
                           "standing": dict(politics.get("standing") or {}),
                           "blame": blame}
    return charter, record


def _body_act(actor, act, other, bodies, state, practices, minds, needs, at):
    body = bodies.get(actor)
    if not body.get("available"):
        return _refusal(actor, act, other, REFUSED_UNABLE)
    place = _whereabouts(actor, state)
    if place and place == _whereabouts(other, state):
        practices.update(_pair_situations(
            actor, other, place, minds, needs, bodies, practices, at))
    offer, practice, reason = _offer_for(
        actor, act, other, _by_body(practices).get(actor, ()), state)
    if offer is None:
        return _refusal(actor, act, other, reason)
    line, subject = landed_effect(offer[1]())
    if not line:
        # The builder licensed the act but the effect found nothing to do —
        # a telling the listener already held stronger. Still conduct; the
        # record says what was attempted rather than pretending silence.
        line = f"{actor} {act} {other}".strip()
    practice["last_effect_at"] = at
    record = {"actor": actor, "act": act, "other": other, "line": line}
    if subject:
        record["subject"] = subject
    return record


def _figure_act(actor, act, other, figures, bodies, state, practices, minds,
                needs, heard_blame, at, claim=None, retention=None):
    figure = figures[actor]
    target = bodies.get(other)
    if target is None:
        return _refusal(actor, act, other, REFUSED_ABSENT)
    if act not in FIGURE_ACTS:
        return _refusal(actor, act, other, REFUSED_NO_SITUATION)
    place = _whereabouts(actor, state)
    if not place or place != _whereabouts(other, state):
        return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)

    if act == "greet":
        # Being spoken to is being seen: the body's picture of the figure
        # refreshes, and the situation a conversation needs opens.
        minds.setdefault(other, {})[actor] = figure_claim(figure, at)
        key, entry = _open("converse", place, {"a": other, "b": actor}, at)
        practices.setdefault(key, entry)
        return {"actor": actor, "act": act, "other": other,
                "line": f"{actor} greeted {other}"}

    if act == "ask":
        # The question is the author's; the body's answer is its own
        # conduct, chosen or authored on the body's side. Asking only keeps
        # the situation warm.
        key, entry = _open("converse", place, {"a": other, "b": actor}, at)
        practices.setdefault(key, entry)
        practices[key]["last_effect_at"] = at
        return {"actor": actor, "act": act, "other": other,
                "line": f"{actor} asked {other}"}

    if act == "tell":
        if not isinstance(claim, dict) or not claim.get("body"):
            return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)
        keep = ASKED_RETENTION if retention is None else float(retention)
        taken = hear_claim(
            minds, other, claim, keep,
            regard_value(state["regard"], other, actor), heard_from=actor)
        subject = str(claim.get("body"))
        return {"actor": actor, "act": act, "other": other,
                "taken": bool(taken),
                "line": f"{actor} told {other} about {subject}"}

    if act == "accuse":
        heard_blame.setdefault(other, set()).add(actor)
        key, entry = _open("quarrel", place, {"a": other, "b": actor}, at,
                           about=other)
        practices.setdefault(key, entry)
        return {"actor": actor, "act": act, "other": other,
                "line": f"{actor} accused {other}"}

    # act == "tend"
    held = (needs or {}).get(other) or {}
    if not held:
        return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)
    worst = min(held.values(),
                key=lambda n: float(n["level"]) - float(n["floor"]))
    if float(worst["floor"]) - float(worst["level"]) <= 0.0:
        return _refusal(actor, act, other, REFUSED_OUTSIDE_LICENCE)
    worst["level"] = min(1.0, float(worst["level"]) + 0.05)
    return {"actor": actor, "act": act, "other": other,
            "line": f"{actor} tended {other} ({worst['key']})"}


def action_instances(charter, actor=None):
    """The affordances currently open to one presence, or to all of them.

    A convenience over ``charter_practice.offers`` that reads the charter's
    own stores, for a scene manager deciding what a voiced body could
    plausibly do next. Reading it licenses nothing.
    """
    charter = normalize_charter(charter)
    politics = normalize_politics(charter.get("politics"))
    # The same four history stores the chooser reads, and passed for the same
    # reason: `charter_runtime` puts these utility numbers in front of a
    # scene-manager model (`agents/background.py`), and numbers computed
    # without history beside a chooser that decides with it would be a seam
    # lying about what the body wants.
    return offers(
        charter["bodies"], charter["minds"], charter["needs"],
        normalize_practices(charter.get("practices")),
        regard_map(politics), dict(politics.get("blame") or {}),
        float(charter["clock_hours"]), figures=charter["figures"],
        actor=actor, experiences=charter.get("experiences"),
        served_beside=charter.get("served_beside"),
        judgments=charter.get("judgments"),
        commitments=charter.get("commitments"))
