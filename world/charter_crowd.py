"""The crowds bridge: charter people at rest, presented as one crowd.

``docs/design/DESIGN_BACKGROUND_PRESENTATION.md`` Part B. `world/crowds.py`'s
stored object is Director-authored people who exist ONLY as a band; charter
bodies are the opposite -- fully simulated people who need a cheaper
presentation. So the bridge is not "put charter people into the crowds
ledger": a stored band, composition and membership would drift the moment
`charter_move.errands` walks a body elsewhere, the exact second-source-of-
truth scar `crowds.py`'s module note is written after.

**A charter crowd is derived at read time and never persisted.** Membership
is a subtraction: the charter bodies whose ``place`` is the observer's room,
minus every body presented individually this beat -- bound bodies
(``state["bindings"]``) and bodies with a live presence record
(``background_presences`` rows carrying ``charter_refs``). Crowd membership
is a LENS: it never touches ``bodies``, ``minds``, ``needs`` or any other
person store, which is also why absorption is free -- Charter never stopped
simulating anybody, so there is no state transition to get wrong in either
direction.

Every derived field comes from data the charter already owns:

* **band** -- `crowds.count_band` over the membership count, the one place an
  integer meets the band vocabulary (integer -> word is a projection; the
  reverse arithmetic still never happens).
* **composition** -- the dominant post/role nouns among the members, via the
  watch bill and each body's ``home_post``. Engine vocabulary by
  construction: posts are authored per charter, so the string is
  genre-correct without this module knowing any genre.
* **mood** -- the members' aggregate strain (`charter_feel.strain_of`),
  banded. Derived, so a place whose people are worn reads worn without
  anyone authoring it.
* **heading** -- none. Charter bodies move individually on their own
  errands; a derived crowd has no collective current unless the institution
  gives it one (an institution-level seam, deliberately not designed here).

This module is PURE: dicts in, dicts out, no database, matching
`world/crowds.py` and `world/charter_chatter.py`. Its inputs arrive as the
per-charter slices `agents.common.chatter_inputs` already fetches once per
stage; `agents.common.charter_crowds_for_room` is the only place these
functions meet an observer, and `persist/commit.py` re-derives the same rows
to resolve an `emerge` -- there is nothing stored for the two reads to
disagree about.
"""

from __future__ import annotations

from .crowds import CHARTER_CROWD_FLOOR, charter_crowd_uid, count_band

#: How many derived crowds one room's view may carry, matching the cap
#: `charter_runtime._place_views` already applies to co-located charters
#: (``ledgers[:3]``): at most one derived crowd per charter per room, and at
#: most this many charters read for one room. Structural, not a ledger cap --
#: a derived crowd occupies no `MAX_CROWDS` row.
CO_LOCATED_CAP = 3

#: What the members' aggregate strain reads as, by mean strain over ALL
#: members (a body carrying none counts as 0.0 -- the crowd is everyone
#: standing there, not only the worn). Thresholds are vocabulary in
#: `crowds.BANDS`' sense and a PREDICTION awaiting a play measurement: strain
#: is 0..1 (`charter_feel.strain_of`), `STRAIN_REST_TOLL`'s own scale.
_MOOD_BANDS = ((0.25, ""), (0.55, "weary"))
_MOOD_WORST = "worn thin"

#: K, the beat-tier analogue of `charter_practice.IDLE_CLOSE_HOURS`
#: (DESIGN_BACKGROUND_PRESENTATION §C3): a body neither addressed nor
#: addressing for this many consecutive beats returns to ground -- its
#: presence record stops presenting it individually, so the derived crowd
#: counts it again and it may re-emerge. MEASURED, not guessed, per the
#: note's own instruction: over every live chat's `background_presences`
#: ledger (2026-08-27 engine.db, 71 chats, 77 records, 244 re-engagement
#: gaps between consecutive addressed/dialogue turns), 216/244 resumptions
#: were consecutive beats (idle 0); of the 28 that followed real
#: inattention, 25/28 = 89.3% resumed within 4 idle beats and the next
#: resumption after that was at idle 8. K = 4 is the ~90% knee the note
#: asked for. Small n (28 events) -- re-take with the same query when the
#: corpus grows.
PRESENTED_IDLE_BEATS = 4


def engaged_turn(record):
    """The last beat this presence was addressed or addressing, or None.

    "Neither addressed nor addressing" (§C3) is the idle test, so exactly
    three things count: the record's own spoken turns (``dialogue_turns``),
    the turns somebody deliberately turned toward it (``addressed_turns``,
    plus an unexpired ``pending_reply``'s turn), and the turn the record was
    born (``first_turn`` -- an emergence is an engagement: someone wanted
    this person). ``mention_turns`` and ``last_turn`` deliberately do NOT
    count: a narration mention is salience, and salience stopped being a
    presentation claim when the voice tier went demand-driven.
    """
    turns = [record.get("first_turn")]
    for field in ("dialogue_turns", "addressed_turns"):
        turns.extend(record.get(field) or ())
    pr = record.get("pending_reply")
    if isinstance(pr, dict):
        turns.append(pr.get("turn"))
    held = [int(t) for t in turns if isinstance(t, (int, float))]
    return max(held) if held else None


def presented(record, turn_idx):
    """Does this record still present its body individually, this beat?

    True while the body's last engagement is under `PRESENTED_IDLE_BEATS`
    ago. Lapsing is LOSSLESS by construction: nothing is deleted -- the
    record keeps its history, its names stay recognisable to chatter
    attribution (`known_bodies` never lapses), and Charter never stopped
    simulating the body -- only the crowd-membership subtraction expires,
    which is what "returns to ground with no ceremony" means. A record with
    no turn bookkeeping at all cannot be aged and stays presented, which is
    today's behaviour for exactly those records.
    """
    engaged = engaged_turn(record)
    if engaged is None or turn_idx is None:
        return True
    return (int(turn_idx) - engaged) < PRESENTED_IDLE_BEATS


def members_of(charter, place):
    """Who the derived crowd holds: bodies at this place that nothing this
    beat presents individually, stably ordered.

    The subtraction IS the presentation boundary (DESIGN_BACKGROUND_
    PRESENTATION §B2): a charter body is ground exactly when it is neither
    an authored mind's (`body_of_an_authored_mind` -- bound to a registered
    character, or reserved for one by ``resident_seed_id``; chat 95 counted
    Picard's and Data's own bodies as ground because only the first half was
    asked, 10 members on ``main_bridge`` where 8 is right) nor presented as an
    individual right now (``presented_bodies`` -- ``background_presences``
    records still inside `PRESENTED_IDLE_BEATS`, by body key, which is how
    an emerged body leaves the crowd on the next read without any
    ``emerged`` list being stored, and how an idle one returns to it). A
    slice built before the presentation-lapse read exists falls back to
    ``known_bodies`` -- every record, however old -- which is the
    conservative pre-§C3 subtraction.
    """
    from .charter_model import body_of_an_authored_mind

    room = str(place or "")
    if not room:
        return []
    if "presented_bodies" in charter:
        known = charter.get("presented_bodies") or ()
    else:
        known = charter.get("known_bodies") or ()
    return sorted(
        key for key, body in (charter.get("bodies") or {}).items()
        if str((body or {}).get("place") or "") == room
        and not body_of_an_authored_mind(charter, key, body)
        # A PERSON THE AUTHOR NAMED IS NEVER GROUND. A featured resident
        # carries `resident_seed_id` whoever seeded it; the planner's
        # landlady is not a mind's body (`body_of_an_authored_mind` since
        # 2026-09-14) but she was featured to be SEEN, and folding her into
        # "the crowd answered together" when the player asked her by name
        # (scratch play 2026-09-14, chat 7 turn 3) is the same deletion
        # `presence_figures_for_room` was built against. The crowd is the
        # institution's unnamed mass; the named stand out of it.
        and not str((body or {}).get("resident_seed_id") or "").strip()
        and key not in known)


def _role_noun(post_key):
    """A presentable noun from a post id. Ids carry disambiguators -- a watch
    bill needs ``patrol_a`` and ``patrol_b`` to be two slots -- so trailing
    one-character or numeric segments are dropped; they distinguish slots,
    never kinds of person."""
    segments = [s for s in str(post_key or "").split("_") if s]
    while segments and (len(segments[-1]) == 1 or segments[-1].isdigit()):
        segments.pop()
    return " ".join(segments).strip().casefold()


def _plural(noun):
    """The cheapest plural that survives authored nouns: add nothing to a
    word already ending in s. Authored ``titles.posts`` entries are the
    quality path; this only has to keep an id-derived fallback readable."""
    noun = str(noun or "").strip()
    if not noun or noun.endswith("s"):
        return noun
    # -man is the one English inflection a bare "+s" gets audibly wrong, and
    # it lands on exactly the post ids a working institution mints:
    # "journeymans and masters" stood in a forge's own description of itself
    # (two_lives v5, 2026-09-19). A suffix rule, not a word list -- it holds
    # for every compound ending that way and needs no vocabulary.
    if noun.endswith("man"):
        return noun[:-3] + "men"
    return noun + "s"


def _held_posts(charter):
    """body key -> the watch posts it stands, from the bill."""
    held = {}
    for post, holder in (charter.get("watch") or {}).items():
        held.setdefault(str(holder), []).append(str(post))
    return held


def member_noun(charter, body_key, held=None):
    """What ONE body IS, in a word or two, or "".

    `title_for` over the watch posts it stands, then over its ``home_post``
    (the duty it ordinarily belongs to), then the cleaned post id itself.

    Public because the crowd is not the only presentation of a member.
    `composition_of` tallies this over a membership to say what a band is
    made of; `agents.common.presence_figures_for_room` asks it about a body
    the crowd does NOT carry, which is the same question about one person.
    One reader, because two would drift -- a room whose crowd reads
    "engineers" while the one engineer standing out of it reads as an
    unfamiliar person is a description of two different rooms.
    """
    from .charter_identity import title_for

    held = _held_posts(charter) if held is None else held
    body = (charter.get("bodies") or {}).get(str(body_key)) or {}
    roles = sorted(held.get(str(body_key)) or ())
    if not roles and body.get("home_post"):
        roles = [str(body["home_post"])]
    # AN HONORIFIC IS HOW A PERSON IS ADDRESSED, NOT WHAT THEY ARE. A body
    # the planner named "Mrs Dacre" with `title: "Mrs"` carries its own
    # address in its name, and reading that title as the noun composed
    # "the elderly wiry miss with grey locks" and a crowd of "mrs"
    # (scratch play 2026-09-14, chat 9). The same test `display_name`
    # makes: a title the name already opens with is an address form, and
    # the noun is the post's.
    explicit = str(body.get("title") or "").strip()
    name = str(body.get("name") or "").strip()
    if explicit and name.casefold().startswith(explicit.casefold() + " "):
        body = {k: v for k, v in body.items() if k != "title"}
    noun = str(title_for(body, roles, charter.get("naming"))
               or "").strip().casefold()
    if not noun and roles:
        noun = _role_noun(roles[0])
    return noun


def composition_of(members, charter):
    """<=120 chars of what the members ARE: the dominant role nouns.

    Per member, the noun is `member_noun` (which see). The top two nouns by
    count compose the phrase; a membership carrying no readable duty at all
    -- the ambient charter's common case, an institution of none -- is
    "people", `describe`'s own default made explicit.
    """
    held = _held_posts(charter)
    tally = {}
    for key in members:
        noun = member_noun(charter, key, held)
        if noun:
            tally[noun] = tally.get(noun, 0) + 1
    ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
    if not ranked:
        return "people"
    return " and ".join(_plural(noun) for noun, _n in ranked)[:120]


def mood_of(members, feel):
    """<=24 chars from the members' aggregate strain, banded.

    Mean over ALL members, carriers or not: ten fresh hands beside one
    exhausted one are not a weary crowd. `strain_of` is the reader so the
    felt quantity has exactly one spelling.
    """
    members = list(members or ())
    if not members:
        return ""
    from .charter_feel import strain_of

    strains = strain_of(feel or {})
    mean = sum(float(strains.get(key, 0.0)) for key in members) / len(members)
    for below, word in _MOOD_BANDS:
        if mean < below:
            return word
    return _MOOD_WORST


def crowd_face(charter, members, feel=None):
    """The ONE member a crowd fronts -- whoever in it has attention to spare
    -- or "" for an empty membership.

    A crowd is a cheaper presentation of people, not a deletion of them.
    Six smiths at a forge are legitimately "a handful of journeymen" to look
    at; nobody reads six names off a room. But a body you can SEE working is
    a body you can SPEAK to, and a room whose every person is carried by a
    band offers an observer nobody at all. Measured (two_lives v5, 2026-09-19,
    30 beats): Sal Weatherby stood in a forge holding six charter smiths,
    her own pose watching two of them at the anvil, and her view named them
    "a handful of journeymans and apprentices" with `company` empty -- not
    one person in that town spoke for thirty beats. The inversion is the
    tell: the BUSIER a place was, the less of it could answer.

    Lowest strain, ties by the stable key order. Strain is the engine's own
    quantity for how loaded a body is (`charter_feel.strain_of`, the reader
    `mood_of` bands), and the member with attention to spare is the one who
    looks up when somebody walks in. The tie-break is by key and not by
    anything felt, so the face is the SAME person beat after beat -- which
    is what lets an observer address them twice and get the same somebody.
    """
    from .charter_feel import strain_of

    members = [str(key) for key in (members or ()) if str(key or "")]
    if not members:
        return ""
    strains = strain_of(feel or {})
    return min(sorted(members), key=lambda key: float(strains.get(key, 0.0)))


def crowd_for(chat_id, charter, place, members=None, *, fronted=None):
    """One derived crowd for this charter in this room, or None.

    None below `CHARTER_CROWD_FLOOR`: two unvoiced bodies are two figures
    the existing overlay path can carry, not "a crowd". The returned row is
    the stored crowds' shape -- band, composition, mood -- so `describe`,
    `density`, `terrain` and every view read both species identically; what
    marks it derived is the uid prefix and the ``derived`` flag, and no
    ``since_turn``, because a projection has no birthday. The membership
    count dies here: it met the band vocabulary and is not carried out.

    ``members`` is `members_of`'s answer when the caller has already asked
    it. A VIEW MUST ASK ONCE: the crowd is the bodies it carries and the
    figures are the bodies it does not, so the two presentations are one
    subtraction and a second call to `members_of` is a second answer that
    can differ from the first (`agents.common.charter_ground_for_room`).
    """
    members = members_of(charter, place) if members is None else list(members)
    if len(members) < CHARTER_CROWD_FLOOR:
        return None
    # ``fronted`` is `crowd_face`'s answer when the caller has fronted one
    # member as a figure. The FLOOR is tested on the whole membership above
    # -- the room holds enough people to be a crowd whether or not one of
    # them turned around -- while the band, composition and mood describe
    # only the bodies this row still carries, because a body is presented
    # once per view and the fronted one is presented as itself.
    carried = [key for key in members if str(key) != str(fronted or "")]
    if not carried:
        return None
    key = str(charter.get("key") or "")
    return {
        "uid": charter_crowd_uid(chat_id, key, place),
        "room_uid": str(place or ""),
        "band": count_band(len(carried)),
        "composition": composition_of(carried, charter),
        "mood": mood_of(carried, charter.get("feel") or {}),
        "heading": None,
        "charter_key": key,
        "derived": True,
    }
