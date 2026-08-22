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

#: Memories a promotion mints, total. A budget, not a target: a quiet life
#: promotes with two or three rows, and that is a correct answer.
REMEMBERED_CAP = 12

#: Acquaintances that cross as relationship memories. The same cap family as
#: `charter_log.scene_ledger`'s `knows_here`, for the same reason: a roll
#: call of everyone ever shared a room with is a payload, not a past.
RELATIONSHIP_CAP = 4

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
    """
    payload = felt_handoff(body_key, charter)
    payload["memories"] = remembered(charter, body_key, events=events)
    return payload
