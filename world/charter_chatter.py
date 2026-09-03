"""Ambient chatter: what a room full of charter people sounds like.

``docs/design/DESIGN_BACKGROUND_PRESENTATION.md`` Part A. Two derived objects
per observer-room-beat, both subtractions from what the substrate already
computed and threw away:

* a HUM — one banded word for the room's talk as ground, graded from the
  last landed window's acts in that room against the crowd already standing
  there. A band for the same reason the crowd's count is one: nobody writes
  "eleven conversations", and two sources disagreeing about a number is a
  dispute nobody can resolve.
* at most ONE overheard fragment — the room's talk as figure, admitted only
  when a deterministic selector judges attention would snag on it. Prose has
  one channel, so anything rendered verbatim IS foreground (the walla rule);
  the correct fragment count is zero or one, never a transcript.

WHAT CROSSES IS THE TRIPLE, NOT THE SENTENCE. The substrate's ``line`` is a
skeleton (``{actor} asked {other} about {subject}``,
``charter_practice._afford_ask``) and holds no sentence content, so the
fragment carries ``{speaker_label, act, other_label, subject_label}`` and the
skeleton is deliberately NOT deposited — a literal string in a payload gets
restated (the chat-78 lesson on ``charter_log.scene_ledger``). The
information budget is the triple by construction: who-asked-whom-about-whom
is all the engine itself knows about what was said aloud.

DEGRADATION INVERTS WITH CROWDING. More crowd is more ground and less
figure: loose admits an ordinary fragment, packed only a high-salience one,
and a crush — already a membrane you cannot see across (`crowds.terrain`) —
is a din you cannot pick one voice out of. Fragments there are zero.

This module is PURE: dicts in, dicts out, no database, matching
`world/crowds.py`'s discipline. The persistence half is one field —
``window_acts`` on the charter state, deposited by `charter_run.step` and
carried by `charter_model.normalize_charter` — and the perception half is
`agents.common.chatter_for_room`, which is the only place these functions
meet an observer.
"""

from __future__ import annotations

import hashlib

from .crowds import CRUSH, LOOSE, PACKED

#: How loud the room's talk is, ordered; the index is the rank. Rank 0 is
#: silence and renders as nothing. Vocabulary, not tuning — chosen once so
#: the words keep their plain meanings, the way `crowds.BANDS` were.
HUM_BANDS = ("", "scattered talk", "a steady hum",
             "a din nothing carries over")

#: Acts in the observer's room at which scattered talk becomes a steady hum.
#: Set from the measurement in DESIGN_BACKGROUND_PRESENTATION §0
#: (twin_towns(40), 180 windows, seeds 0..179): the busiest single place
#: carries a median of 4 acts per window and a p90 of 6. One act is one
#: speaker (`enact` is one choice per actor per window), so a room past its
#: own p90 has more conversations running than anyone could follow — a hum.
STEADY_HUM_ACTS = 6

#: One-in-N odds that an ordinary act (no entanglement, no event kind)
#: surfaces as the fragment, so a long quiet scene still occasionally yields
#: an overheard nothing — texture, not information. A PREDICTION awaiting a
#: measurement: the design's open question 2 says the right rate is a play
#: question, read from fragments feeling like spam or never being noticed.
FRAGMENT_ODDS = 4

#: Most window-act rows one charter carries. The structural bound is one act
#: per body per window (`charter_practice.enact` is one choice per actor), so
#: the cap only defends a hand-edited blob; 256 covers the largest shipped
#: population (`twin_towns(240)`) at its measured whole-charter rate
#: (19 acts median per 40-body window, §0) with headroom.
WINDOW_ACTS_CAP = 256


def window_acts(acts, bodies, at_hours, event_kinds=frozenset()):
    """This window's acts as the room-stamped record perception reads.

    Deposited because nothing else survives to read time: `after_charter`
    carries ``acts`` only until the next `normalize_charter`, which rebuilds
    the state from a fixed key set — so the design note's plan to filter
    "a list the registry already holds" reads a list every persistence
    boundary was deleting. This is that list, made durable.

    ``place`` is the actor's place at deposit, the same presence test
    `charter_news.witness` applies (a body stood where it happened).
    ``event`` marks kinds the caller's `_ACT_EVENTS` already deems
    relationship-changing — stamped HERE because the substrate owns that
    vocabulary and this module must not import it back out of `charter_run`.
    The template ``line`` is deliberately dropped; see the module note.
    """
    rows = []
    for act in acts or ():
        actor = str((act or {}).get("actor") or "")
        body = (bodies or {}).get(actor)
        place = str((body or {}).get("place") or "")
        kind = str(act.get("act") or "")
        if not actor or not place or not kind:
            continue
        rows.append({
            "actor": actor,
            "act": kind,
            "other": str(act.get("other") or ""),
            "subject": str(act.get("subject") or ""),
            "place": place,
            "at_hours": round(float(at_hours), 6),
            "event": kind in (event_kinds or ()),
        })
    return rows[:WINDOW_ACTS_CAP]


def normalize_window_acts(stored, bodies):
    """The deposited rows, from any shape, filtered to live bodies.

    An actor no longer in the charter must not leave talk behind — the same
    rule `marks` and `experiences` normalization applies, and this is the
    filter that counts because `normalize_charter` runs at the head of every
    `step`.
    """
    rows = []
    for row in (stored or []):
        if not isinstance(row, dict):
            continue
        actor = str(row.get("actor") or "")
        if actor not in (bodies or {}):
            continue
        place = str(row.get("place") or "")
        kind = str(row.get("act") or "")
        if not place or not kind:
            continue
        try:
            at = round(float(row.get("at_hours") or 0.0), 6)
        except (TypeError, ValueError):
            at = 0.0
        rows.append({
            "actor": actor, "act": kind,
            "other": str(row.get("other") or ""),
            "subject": str(row.get("subject") or ""),
            "place": place, "at_hours": at,
            "event": bool(row.get("event")),
        })
    return rows[:WINDOW_ACTS_CAP]


def acts_in_room(rows, place):
    """The last window's acts whose actor stood in this room, stably ordered."""
    room = str(place or "")
    if not room:
        return []
    return sorted(
        (r for r in (rows or []) if isinstance(r, dict)
         and str(r.get("place") or "") == room),
        key=lambda r: (str(r.get("actor") or ""), str(r.get("act") or ""),
                       str(r.get("other") or "")))


def hum_rank(act_count, band_rank=0, density=None):
    """0..3 into `HUM_BANDS`, from the acts and the crowd band together.

    Both inputs, deliberately: the acts sample the population, they do not
    exhaust it. A throng produces a hum even in a window that landed no acts
    (band floor); a handful produces scattered talk however busy the window
    was — which needs no explicit cap, because one act is one speaker, so a
    handful of people cannot land `STEADY_HUM_ACTS` acts. A crush is a din
    whatever was said: the same physics that makes it a `membrane` you
    cannot see across makes it a press you cannot pick a voice out of.
    """
    if density == CRUSH:
        return 3
    try:
        count = max(0, int(act_count))
    except (TypeError, ValueError):
        count = 0
    rank = 0 if count == 0 else (1 if count < STEADY_HUM_ACTS else 2)
    try:
        band = max(0, int(band_rank))
    except (TypeError, ValueError):
        band = 0
    if band >= 3:               # "a few dozen" or "a throng" standing there
        rank = max(rank, 2)
    elif band == 2:             # "a dozen or so"
        rank = max(rank, 1)
    if density == PACKED:
        rank = max(rank, 2)
    return rank


def hum_phrase(rank):
    """One clause of ground for the room view; empty at rank 0."""
    try:
        rank = int(rank)
    except (TypeError, ValueError):
        return ""
    if rank <= 0 or rank >= len(HUM_BANDS):
        rank = min(max(rank, 0), len(HUM_BANDS) - 1)
    word = HUM_BANDS[rank]
    if not word:
        return ""
    if rank == 1:
        return "There is %s among those around" % word
    if rank == 2:
        return "%s of conversation hangs over the room" % word.capitalize()
    return "The talk around is %s" % word


def _draw(seed_material, salt, modulus):
    """One deterministic draw, `ENCOUNTER_ODDS`-style: the run's own seed
    material through hashlib, never ambient randomness."""
    if modulus <= 0:
        return 0
    digest = hashlib.sha256(
        ("%s|%s" % (seed_material, salt)).encode("utf-8")).hexdigest()[:8]
    return int(digest, 16) % modulus


def fragment_key(row):
    """The act's identity, for dedupe: the same act never surfaces twice.

    The same discipline as composer ``dedupe_key``s — a fragment re-selected
    while its window stands keeps the same key, so the delivery layer reads
    it as unchanged furniture rather than a fresh overhearing.
    """
    return "chatter:%s" % hashlib.sha256("|".join([
        str(row.get("actor") or ""), str(row.get("act") or ""),
        str(row.get("other") or ""), str(row.get("subject") or ""),
        "%0.4f" % float(row.get("at_hours") or 0.0),
    ]).encode("utf-8")).hexdigest()[:16]


def overheard_fragment(rows, *, notable=(), density=LOOSE, seed_material="",
                       odds=FRAGMENT_ODDS):
    """At most one act the observer's attention would snag on, or None.

    Eligibility, in order (DESIGN_BACKGROUND_PRESENTATION §A2b):

    1. the act's other or subject names someone the beat is entangled with —
       the one fragment worth hearing is the crowd talking about *you*;
    2. the act is a kind the substrate already treats as an event the room
       witnesses (``event`` rows — `charter_run._ACT_EVENTS`), so surfacing
       it renders a fact co-present minds were going to hold anyway;
    3. failing both, an ordinary act on a seeded low-rate draw — an
       overheard nothing, admitted only in a loose room.

    Density inverts intelligibility: packed admits tiers 1–2 only, a crush
    admits nothing (the din is the whole percept). The winner within a tier
    is a seeded index rather than the alphabetically first actor, so a
    standing window does not always surface the same corner of the room
    across stories while one story's replay stays byte-identical.
    """
    if density == CRUSH:
        return None
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    if not rows:
        return None
    marks = {str(n or "").casefold() for n in (notable or ()) if str(n or "")}

    def _entangled(row):
        return bool(marks) and (
            str(row.get("other") or "").casefold() in marks
            or str(row.get("subject") or "").casefold() in marks
            or str(row.get("other_name") or "").casefold() in marks
            or str(row.get("subject_name") or "").casefold() in marks)

    tier = [r for r in rows if _entangled(r)]
    if not tier:
        tier = [r for r in rows if r.get("event")]
    if not tier:
        if density == PACKED:
            return None
        if _draw(seed_material, "fragment-gate", max(1, int(odds))):
            return None
        tier = rows
    return tier[_draw(seed_material, "fragment-pick", len(tier))]


#: How each act kind reads when overheard, keyed by the substrate's own act
#: vocabulary. Named as distinctions, never instances: these hold for a
#: dockside, a monastery and a starship alike because the nouns arrive in the
#: labels, not the template. An act kind this map has never met still
#: surfaces, as talk — a fiction may grow an affordance and overhearing it
#: must cost nothing.
_ACT_PHRASES = {
    "greet": "greeting {other}",
    "ask": "asking {other} about {subject}",
    "tell": "telling {other} about {subject}",
    "tend": "seeing to {other}",
    "accuse": "accusing {other}",
    "reconcile": "making peace with {other}",
}

_ACT_PHRASES_NO_SUBJECT = {
    "ask": "asking {other} something",
    "tell": "telling {other} something",
}


def fragment_phrase(fragment):
    """One rendered clause from the triple, composed rather than quoted.

    The view is composed, not quoted: no sentence the crowd "said" exists
    anywhere, so none can be restated. Labels arrive already licensed by
    `fragment_labels`; this only spells them.
    """
    if not isinstance(fragment, dict):
        return ""
    speaker = str(fragment.get("speaker_label") or "someone")
    other = str(fragment.get("other_label") or "someone else")
    subject = str(fragment.get("subject_label") or "")
    kind = str(fragment.get("act") or "")
    if subject:
        template = _ACT_PHRASES.get(kind)
    else:
        template = (_ACT_PHRASES_NO_SUBJECT.get(kind)
                    or _ACT_PHRASES.get(kind))
    if not template or ("{subject}" in template and not subject):
        template = "talking with {other}"
    doing = template.format(other=other, subject=subject)
    return "Close by, %s can be overheard %s" % (speaker, doing)


def participant_forms(key, *, place, bodies=None, watch=None, posts=None,
                      naming=None, figures=None, known_bodies=frozenset()):
    """Both things a bystander could call one participant, kept apart.

    ``name`` is the participant's own name -- a figure's (someone the scene
    itself presents: the player, cast, an emerged presence) or a body's the
    story has met individually (``known_bodies``, live presence records by
    body key) -- and ``anon`` is what a stranger sees: the role noun of a
    watch post held IN THIS ROOM (engine vocabulary by construction, because
    posts are authored per charter), else empty for the anonymous register.

    WHY TWO. A fragment is composed once per room and read by every mind
    standing in it, and "the story has met this person" is not "THIS
    observer has". Measured, Harrowmere replay 2026-09-03 turn 32: the
    market trader had a presence record since turn 2, so `known_bodies`
    licensed the name, the room's chatter named the trader to a player
    whose `known` ledger was empty, and the composer's tripwire had to
    scrub it -- a name reaching a mind through eavesdropping on people who
    were not saying it. The name is still licensed for the observer who
    recognises it; the per-observer choice is made where the observer is
    (`agents/perception` -> `relabel_fragment`), and everything below it
    carries the anonymous form by default so a reader that forgets to
    choose fails closed.
    """
    key = str(key or "")
    if not key:
        return {"name": "", "anon": ""}
    if key in (figures or {}):
        return {"name": key, "anon": ""}
    body = (bodies or {}).get(key)
    if body is None:
        return {"name": "", "anon": ""}
    from .charter_identity import display_name, title_for
    roles = sorted(post for post, holder in (watch or {}).items()
                   if str(holder) == key)
    name = display_name(body, roles, naming) if key in (known_bodies or ()) \
        else ""
    here = [post for post in roles
            if str(((posts or {}).get(post) or {}).get("place") or "")
            == str(place or "")]
    anon = ""
    if here:
        title = title_for(body, here, naming)
        noun = (title or here[0].replace("_", " ")).strip()
        if noun:
            anon = "the %s" % noun.casefold()
    return {"name": str(name or ""), "anon": anon}


def participant_label(key, *, place, bodies=None, watch=None, posts=None,
                      naming=None, figures=None, known_bodies=frozenset()):
    """What a bystander may call one participant. NEVER an unearned name.

    Attribution follows recognition (§A2c): a body the story has already met
    individually (``known_bodies`` — live presence records, by body key) or a
    figure (someone the scene itself presents — the player, cast, an emerged
    presence) is named; a body standing a watch post IN THIS ROOM is its
    role noun, engine vocabulary by construction because posts are authored
    per charter; everyone else is empty, and the caller renders the
    anonymous register. Returns ``(label, recognized)``.

    The story-level answer; `participant_forms` is the split a per-observer
    reader needs, and the reason it exists is in its docstring.
    """
    forms = participant_forms(
        key, place=place, bodies=bodies, watch=watch, posts=posts,
        naming=naming, figures=figures, known_bodies=known_bodies)
    if forms["name"]:
        return forms["name"], True
    if forms["anon"]:
        return forms["anon"], True
    return "", False


def relabel_fragment(fragment, *, recognizes, display_for=None):
    """One observer's rendering of a room's fragment.

    ATTRIBUTION FOLLOWS THE OBSERVER'S RECOGNITION, NOT THE STORY'S. For each
    participant the fragment carries a ``<role>_name`` (the name the story
    could use) and a ``<role>_anon`` (what a stranger sees); the label this
    observer reads is the name when ``recognizes(name)`` says they know it,
    else what they already call that body in this beat (``display_for``,
    the observer's display map -- a stranger descriptor for a body they can
    see), else the anonymous form. The clause is re-composed from the
    chosen labels. The input is not mutated; a fragment carrying no names
    comes back equal to itself.
    """
    if not isinstance(fragment, dict):
        return fragment
    out = dict(fragment)
    changed = False
    for role in ("speaker", "other"):
        name = str(out.get(f"{role}_name") or "")
        if not name:
            continue
        if recognizes(name):
            label = name
        else:
            label = str((display_for(name) if display_for else "") or "") \
                or str(out.get(f"{role}_anon") or "")
        if label != str(out.get(f"{role}_label") or ""):
            out[f"{role}_label"] = label
            changed = True
    if changed:
        out["what"] = fragment_phrase(out)
    return out


def subject_label(key, *, bodies=None, figures=None, naming=None):
    """What the talk was ABOUT, named even when the observer has never met
    them — the asymmetry that makes rumour work: the name was said aloud,
    and overhearing a stranger's name is how a name first reaches you. A
    subject that is not a person (a news key) yields empty: what a bystander
    catches of that is that something happened, which is the phrase's
    no-subject shape."""
    key = str(key or "")
    if not key or key.startswith("news:"):
        return ""
    if key in (figures or {}):
        return key
    body = (bodies or {}).get(key)
    if body is None:
        return ""
    from .charter_identity import display_name
    return display_name(body, (), naming)
