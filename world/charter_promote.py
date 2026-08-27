"""Promotion: the past a background body brings to its first real beat.

``docs/UNBUILT.md`` §2.20 names the gap this answers — a promoted character's
"semantic self is rich and their episodic self is empty" — and, in the same
entry, the failure waiting on the other side: a thick past "does not read as
depth; it reads as haunting." A gate guard promoted after four hundred hours
has four hundred windows of standing the same watch, and every one of them is
true, boring, and capable of crowding the story's own memories out of
retrieval.

THE SELECTION RULE IS THE ENGINE'S OWN SIGNIFICANCE TEST: something is
remembered because it CHANGED A TRACKED LEDGER, and the routine that changed
nothing is remembered only as its aggregate. Concretely, a memory is minted
from exactly four sources —

  * an event in the shared ledger that names this body as its subject (a
    collapse, a recovery: the branches of its own life);
  * the news claims this head STILL HOLDS — witnessed or heard, with the
    provenance kept. The ledger never forgets; minds do, and promotion reads
    the mind, so a fact this body let decay is not resurrected by the
    paperwork of becoming a character;
  * the accusations said to its face (``heard_blame``);
  * its salient acquaintances, ranked by the same salience the scene ledger
    uses (a view held, a surprise, then confidence) and capped, plus ONE
    semantic row per post actually stood — four hundred watches become "has
    stood the gate for four hundred watches", which is the whole shape of a
    working life at the weight it deserves.

WHAT MUST NEVER CROSS, and each is a test: the institution's REGISTER (the
charter's belief, not this person's); the blame ledger, unless somebody said
it aloud (``heard_blame`` is the channel; a body blamed in the books and
never told arrives innocent of it); register-fact events (``post_unfilled``,
``post_believed_filled`` — conclusions in the books, unwitnessable in a
room); and any other head's interior. This module is the seam
``DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §12a flags as the firewall's exposure:
a body crosses from the coarse witness to `agents/perception.py`'s strict
one here, and anything it carries that coarse witnessing could not have
given it becomes a real mind's illegitimate knowledge.

The rows are in ``mind/memory_write.prepare_memory``'s own vocabulary —
``kind`` from ``MEMORY_KINDS``, ``provenance`` from ``MEMORY_PROVENANCE``,
plus salience, content, location, entities, confidence and an event key — so
the caller that owns a chat and a character id can mint them without
translating anything. The vocabulary agreement is pinned by a test that
imports the real constants, because a docstring promising a payload shape
has already been wrong once in this package.
"""

from __future__ import annotations

from .charter_feel import felt_handoff
from .charter_politics import regard_value
from .charter_commitment import commitment_view
from .charter_social import familiarity, judgment_view, tie_of

#: Memories a promotion mints, total. A budget, not a target: a quiet life
#: promotes with two or three rows, and that is a correct answer.
#:
#: THIS IS A ONE-TIME CAP AND WAS PRICED AS A PER-BEAT ONE. Promotion happens
#: once and the character keeps what it inherits for the rest of the story, so
#: this number is not protecting any turn's payload or any turn's wall clock --
#: it is deciding how much of a life a person arrives with. At 12 it was also
#: the neck of the whole depth pipeline: `charter_history.resident_history_packet`
#: builds its evidence from these rows, so the model pass that turns a simulated
#: past into subjective memory could never see more than twelve things however
#: deep the substrate underneath got. Selection is salience-ranked (`out.sort`
#: below) and then truncated, so raising this keeps the same best rows and adds
#: the ones that were being discarded.
REMEMBERED_CAP = 120

#: Acquaintances that cross as relationship memories. The same cap family as
#: `charter_log.scene_ledger`'s `knows_here`, for the same reason: a roll
#: call of everyone ever shared a room with is a payload, not a past. Raised on
#: the same argument as the cap above -- a scene payload is rebuilt every beat
#: and must stay small; an inheritance is paid for once.
RELATIONSHIP_CAP = 24

#: Event kinds that may become a memory because this body was their SUBJECT.
#: An allowlist, like `charter_news.WITNESSABLE` and for the same reason:
#: `post_unfilled` and `post_believed_filled` name bodies too, and both are
#: entries in the institution's books that no one in a room could perceive.
_SELF_KINDS = {
    "body_unable": ("was unable to go on", 0.85),
    "body_recovered": ("was back on their feet", 0.6),
}

#: How a witnessed happening reads. Neutral verbs over engine kinds — the
#: lorebook owns what the condition or the post is called; these own only
#: that something failed, recovered, went down, or was stood again.
_NEWS_PHRASES = {
    "upkeep_out_of_band": "{about} failing at {place}",
    "upkeep_restored": "{about} coming back at {place}",
    "body_unable": "{about} going down at {place}",
    "body_recovered": "{about} back on their feet at {place}",
    "post_filled_again": "{about} being stood again at {place}",
}


def _news_phrase(claim):
    if str(claim.get("claim_text") or "").strip():
        return " ".join(str(claim["claim_text"]).split())
    template = _NEWS_PHRASES.get(str(claim.get("event_kind") or ""))
    if template is None:
        template = "{about} at {place}"
    return template.format(about=claim.get("about") or "something",
                           place=claim.get("place") or "somewhere")


def remembered(charter, body_key, events=(), cap=REMEMBERED_CAP):
    """The memories one body's background life has earned. Selected, capped.

    Flat in time by construction: a stretch in which nothing branched, no
    news arrived, nobody accused and nobody new was met adds NOTHING — the
    service aggregate's count rises inside one row's content. Doubling a
    quiet run doubles no part of this list, and a test pins that.
    """
    key = str(body_key)
    charter = charter if isinstance(charter, dict) else {}
    held = (charter.get("minds") or {}).get(key) or {}
    out = []

    def body_name(value):
        body = (charter.get("bodies") or {}).get(str(value)) or {}
        return str(body.get("name") or value)

    # Participant-owned social experience and self-only private routines.
    # These are not the institution's omniscient event log: each row was
    # copied only to a person who took part, and private habits only to self.
    for experience in (charter.get("experiences") or {}).get(key, ()):
        if not isinstance(experience, dict):
            continue
        experience_kind = str(experience.get("kind") or "")
        at_hours = float(experience.get("at_hours") or 0.0)
        place = str(experience.get("place") or "")
        if experience_kind == "private_habit":
            label = str(experience.get("label") or "private routine")
            content = f"made private time for {label.casefold()}"
            entities = [key]
            salience = 0.48
        elif experience_kind == "shared_prestory":
            content = str(experience.get("surface") or "shared a recent event")
            other = str(experience.get("with") or "")
            entities = [other] if other else []
            salience = 0.58
        elif experience_kind == "social":
            actor, other = (str(experience.get("actor") or ""),
                            str(experience.get("other") or ""))
            act = str(experience.get("act") or "interacted with")
            if str(experience.get("role") or "") == "actor":
                content = f"{act} {body_name(other)}"
                entities = [other]
            else:
                content = f"{body_name(actor)} {act} them"
                entities = [actor]
            salience = 0.5
        elif experience_kind == "service":
            # What the body DID with its time. `stood` counts the windows;
            # this is the one row that says taking the post was an event in
            # a life, which is what a memory is and what a counter is not.
            post = str(experience.get("post") or "a post")
            content = f"took {post.replace('_', ' ')}"
            entities = [key]
            salience = 0.45
        elif experience_kind == "acquaintance":
            other = str(experience.get("other") or "")
            content = (f"came to know {body_name(other)}"
                       if experience.get("firsthand")
                       else f"heard tell of {body_name(other)}")
            entities = [other] if other else []
            salience = 0.55
        elif experience_kind == "encounter":
            other = str(experience.get("other") or "")
            during = str(experience.get("during") or "")
            content = f"passed a watch with {body_name(other)}"
            if during:
                content += f" on {during.replace('_', ' ')}"
            entities = [other] if other else []
            salience = 0.58
        elif experience_kind == "stood_through":
            about = str(experience.get("about") or "something")
            content = f"was there when {about.replace('_', ' ')} gave way"
            entities = [key]
            salience = 0.62
        else:
            continue
        # HOW IT LANDED, carried rather than invented. `charter_feel` appraised
        # the window this row was laid down in, from the body's own needs and
        # its own place, and `_record_coarse_experiences` stamped the reading
        # onto the row. A moment that shook somebody is more memorable than one
        # that did not -- so intensity lifts salience instead of every row of a
        # kind sharing one constant. Rows written before the stamp existed, and
        # rows for a body with nothing to feel about, carry no affect and keep
        # the flat salience; absent is not neutral.
        valence = experience.get("valence")
        arousal = experience.get("arousal")
        felt = {}
        if valence is not None or arousal is not None:
            felt = {"valence": round(float(valence or 0.0), 4),
                    "arousal": round(float(arousal or 0.0), 4)}
            intensity = max(abs(float(valence or 0.0)), abs(float(arousal or 0.0)))
            salience = round(min(1.0, salience + 0.35 * intensity), 4)
        out.append({
            "kind": "episodic", "provenance": "remembered",
            "salience": salience, "content": content,
            "location": place, "entities": entities, "confidence": 1.0,
            **felt,
            "event_key": str(experience.get("id") or
                             f"experience:{key}:{at_hours}"),
            "at_hours": at_hours, "experience_kind": experience_kind,
            "role": str(experience.get("role") or ""),
            "actor": str(experience.get("actor") or ""),
            "other": str(experience.get("other") or ""),
            "act": str(experience.get("act") or ""),
            "habit_label": str(experience.get("label") or ""),
        })

    # The branches of its own life, from the shared ledger.
    for event in events or []:
        spec = _SELF_KINDS.get(str(event.get("kind") or ""))
        if spec is None or str(event.get("body") or "") != key:
            continue
        phrase, salience = spec
        place = str(event.get("place") or "")
        out.append({
            "kind": "episodic", "provenance": "witnessed",
            "salience": salience,
            "content": f"{phrase}" + (f" at {place}" if place else ""),
            "location": place, "entities": [key], "confidence": 1.0,
            "event_key": f"{event['kind']}:{key}"
                         f"@{float(event['at_hours']):.4f}",
        })

    # What it still knows happened. The mind is read, not the ledger:
    # decayed news stays forgotten.
    news = [c for c in held.values() if c.get("kind") == "news"]
    news.sort(key=lambda c: (-float(c.get("strength") or 0.0),
                             str(c.get("body") or "")))
    for claim in news:
        provenance = str(claim.get("provenance") or "")
        firsthand = claim.get("heard_from") is None and provenance not in {
            "read", "letter", "told"}
        strength = float(claim.get("strength") or 0.0)
        phrase = _news_phrase(claim)
        if firsthand:
            content = f"saw {phrase}"
        elif claim.get("heard_from"):
            content = f"heard from {claim['heard_from']} that {phrase}"
        else:
            content = f"learned that {phrase}"
        entities = [str(claim.get("about") or "")]
        if claim.get("heard_from"):
            entities.append(str(claim["heard_from"]))
        out.append({
            "kind": "episodic",
            "provenance": "witnessed" if firsthand else "heard",
            "salience": round(0.4 + 0.3 * strength, 4),
            "content": content,
            "location": str(claim.get("place") or ""),
            "entities": [e for e in entities if e],
            "confidence": round(strength, 4),
            "event_key": str(claim.get("body") or ""),
            "at_hours": float(claim.get("last_seen") or
                              claim.get("at_hours") or 0.0),
        })

    # The accusations said to its face. `heard_blame` is the CHANNEL —
    # blame the institution holds in its books but never said aloud does
    # not cross, which is the firewall test this module exists to pass.
    for teller in (charter.get("heard_blame") or {}).get(key, ()):
        out.append({
            "kind": "episodic", "provenance": "told", "salience": 0.8,
            "content": f"{teller} said the fault was {key}'s",
            "location": "", "entities": [str(teller)], "confidence": 1.0,
            "event_key": f"accused:{key}:{teller}",
        })

    # Specific undertakings this person made, received, or learned about.
    # Unlike the foreground pending-obligation ledger these can remain open
    # for years; their lifecycle and provenance are the memory.
    for commitment in commitment_view(
            charter.get("commitments"), key, cap=16):
        if key == commitment.get("promisor"):
            relation = "promised"
            other = commitment.get("beneficiary") or "someone"
        elif key == commitment.get("beneficiary"):
            relation = "was promised"
            other = commitment.get("promisor") or "someone"
        else:
            relation = "learned of a promise between"
            other = "%s and %s" % (
                commitment.get("promisor") or "someone",
                commitment.get("beneficiary") or "someone")
        out.append({
            "kind": "semantic", "category": "promise",
            "provenance": "witnessed" if key in {
                commitment.get("promisor"), commitment.get("beneficiary")
            } else "heard",
            "salience": 0.85 if commitment.get("state") in {
                "open", "accepted", "disputed"} else 0.65,
            "content": f"{relation} {other}: {commitment.get('terms')}; "
                       f"currently {commitment.get('state')}",
            "location": "", "entities": [str(other)], "confidence": 1.0,
            "event_key": commitment.get("id"),
            "at_hours": float(commitment.get("updated_at") or
                              commitment.get("created_at") or 0.0),
        })

    # The people it holds a view about — ranked by the scene ledger's own
    # salience (a view held, a surprise, then confidence) and capped.
    regard = ((charter.get("politics") or {}).get("regard") or {})
    people = [c for c in held.values()
              if c.get("kind") in (None, "figure")
              and str(c.get("body") or "") not in ("", key)]

    def _salience(claim):
        other = str(claim["body"])
        return (abs(1.0 - regard_value(regard, key, other)),
                0.0 if claim.get("kind") == "figure"
                or claim.get("believed_available") else 1.0,
                float(claim.get("strength") or 0.0))

    people.sort(key=lambda c: (_salience(c), str(c["body"])), reverse=True)
    for claim in people[:RELATIONSHIP_CAP]:
        other = str(claim["body"])
        firsthand = claim.get("heard_from") is None
        view = regard_value(regard, key, other)
        if view < 1.0:
            standing = " and thinks less of them"
        elif view > 1.0:
            standing = " and trusts them"
        else:
            standing = ""
        content = (f"knows {other}{standing}" if firsthand
                   else f"knows of {other} from {claim['heard_from']}"
                        f"{standing}")
        out.append({
            "kind": "relationship",
            "provenance": "witnessed" if firsthand else "heard",
            "salience": round(0.3 + 0.3 * _salience(claim)[0]
                              + 0.1 * float(claim.get("strength") or 0.0), 4),
            "content": content, "location": "",
            "entities": [other], "confidence":
                round(float(claim.get("strength") or 0.0), 4),
            "event_key": f"acquaintance:{key}:{other}",
            "at_hours": float(claim.get("last_seen") or 0.0),
        })

    # The shape of the working life: one row per post ever stood, however
    # long the standing. This is the anti-haunting rule — the four hundred
    # identical watches are one sentence that says four hundred.
    stood = (charter.get("stood") or {}).get(key) or {}
    for post_key in sorted(stood):
        windows = int(stood[post_key])
        out.append({
            "kind": "semantic", "provenance": "remembered",
            "salience": round(min(0.65, 0.35 + windows / 400.0), 4),
            "content": f"has stood {post_key} through {windows} watches",
            "location": str((charter.get("posts") or {})
                            .get(post_key, {}).get("place") or ""),
            "entities": [post_key], "confidence": 1.0,
            "event_key": f"service:{key}:{post_key}",
            "at_hours": float(charter.get("clock_hours") or 0.0),
        })

    out.sort(key=lambda m: (-float(m["salience"]), m["event_key"]))
    return out[:max(0, int(cap))]


def promotion_handoff(body_key, charter, events=()):
    """Everything a promotion call receives: the interior and the past.

    The interior half is `charter_feel.felt_handoff` verbatim — hedonic,
    stress, vitals-shaped body state, interoception, stress profile, the
    service record. This adds `memories`, the selected past above. One
    payload, both halves in their readers' own vocabularies, so the caller
    copies and never translates.

    The discrete tie rides on the `acquaintances` rows and nowhere else here
    — one word per edge, beside the `regard` and `familiarity` numbers it is a
    reading of. No new key on this payload, and no reciprocity anywhere in it.
    """
    payload = felt_handoff(body_key, charter)
    payload["memories"] = remembered(charter, body_key, events=events)
    subjects = list((charter.get("bodies") or {})) + list(
        (charter.get("figures") or {}))
    payload["social_judgments"] = judgment_view(
        charter.get("judgments"), body_key, subjects=subjects, cap=24)
    payload["commitments"] = commitment_view(
        charter.get("commitments"), body_key, cap=24)
    payload["acquaintances"] = acquainted(body_key, charter)
    return payload


#: How many people a promotion may carry as RELATIONSHIP EDGES. Larger than
#: the prose-memory cap above it because an edge is a row in a graph the
#: character pipeline consults every beat, not a sentence competing for room
#: in a memory list -- and because the alternative to a thin edge is a
#: stranger, which is worse.
ACQUAINTANCE_EDGE_CAP = 40


def acquainted(body_key, charter):
    """Who this body actually knows, in the shape a relationship graph takes.

    THE GAP THIS CLOSES. `remembered` already renders acquaintance as prose
    memory rows, and prose is not an edge: `mind.get_relationships` is the
    only structure the character pipeline consults for trust, warmth, fear,
    respect and suspicion, and the sole writer into it at promotion was gated
    on `social_judgments` -- which measured ZERO holders across all four
    charters of a real story, so the branch never ran. A person who stood
    beside the same colleagues for 720 hours arrived a stranger to every one
    of them.

    Only channelled inputs. The claim is this body's OWN belief about the
    other; the regard is this body's OWN regard; the familiarity is its own
    co-presence count. No other head is read and the institution's register
    is not consulted -- an edge here says "I know them and this is how I hold
    them", never anything about how they hold me.

    `tie` is derived from exactly those three own-inputs and carries no
    reciprocity for the same reason: it is this head's one-word reading of its
    own numbers (`charter_social.tie_of`), not a fact about the relationship.
    A body may arrive holding somebody `close` who holds it nothing at all,
    and that asymmetry is the feature -- two people do not share a head, so a
    discrete tie cannot be symmetric here the way CiF's are.
    """
    key = str(body_key)
    charter = charter if isinstance(charter, dict) else {}
    held = (charter.get("minds") or {}).get(key) or {}
    regard = (charter.get("politics") or {}).get("regard") or {}
    beside = (charter.get("served_beside") or {}).get(key) or {}
    bodies = charter.get("bodies") or {}
    out = []
    for other, claim in held.items():
        other = str(other)
        if other == key or not isinstance(claim, dict):
            continue
        if claim.get("kind") == "news" or other not in bodies:
            continue
        shared = int(beside.get(other) or 0)
        # Familiarity is time served in the same room, and it saturates: the
        # difference between never and often is most of the signal, and the
        # difference between often and constantly is nearly none. THE
        # SATURATION LIVES IN `charter_social` now, as `TIE_SATURATION`; it was
        # inline here as `shared / 200.0` and the tie layer needs the same
        # number, and two copies of a tuned constant is how they drift.
        familiar = familiarity(charter.get("served_beside"), key, other)
        tie = tie_of(charter.get("ties"), key, other,
                     served_beside=charter.get("served_beside"))
        out.append({
            "body": other,
            "name": str((bodies.get(other) or {}).get("name") or other),
            "firsthand": claim.get("heard_from") is None,
            "heard_from": str(claim.get("heard_from") or ""),
            "strength": round(float(claim.get("strength") or 0.0), 4),
            "regard": round(float(regard_value(regard, key, other)), 4),
            "shared_windows": shared,
            "familiarity": familiar,
            "tie": tie,
            "tie_since_hours": round(float(
                ((charter.get("ties") or {}).get(key) or {}).get(other, {})
                .get("since_hours") or 0.0), 4),
        })
    out.sort(key=lambda row: (-row["familiarity"], -row["strength"],
                              row["body"]))
    return out[:ACQUAINTANCE_EDGE_CAP]
