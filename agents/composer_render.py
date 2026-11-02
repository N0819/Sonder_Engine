"""The English reference VIEW renderer: standing and event sentences, the
presence roll-call, openings and features, `_render_view_english` with its
slot ordering, and `render_view`.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from .common import (
    _appearance_as_prose,
    _compose_residue_view,
    _inject_dialogue,
    _observable_predicate,
)
logger = logging.getLogger("agents.composer")

from agents.composer_common import (
    Percept,
    _ENGLISH_COMPOSITOR,
    _bare_words,
    _cap,
    _en,
    _join_clauses,
    _noun_phrase,
    _safe_renderer,
    _spliced_fragment,
    _strip_sentence_ends,
    _subject_prefix,
)
from agents.composer_person import _said_as_mine
from agents.composer_figures import (
    _dim_figure,
    _label_core,
    _ordinal_label,
    _presence_sort_key,
)
from agents.composer_bodies import EAR_STATES, _COUNT_NAMES
from agents.composer_speech import (
    _can_say_the_voice,
    _feeling_heard,
    _names_kept,
    _one_voice_each,
)
from agents.composer_landscape import (
    far_sight,
    is_landscape,
    landscape_lines,
    render_landscape_line,
)
from agents.composer_standing import (
    appearance_delta,
    as_beat,
    asked_this_beat,
    carried_voices,
    habituated,
    leads_the_beat,
    player_view_order,
    standing_verdicts,
    unheard_ceasing,
    view_verdicts,
)
from agents.composer_fields import (
    render_distant_sound,
    render_light_shape,
    render_sound_shape,
)


# --------------------------------------------------------------------------
# Layer B -- rendering
# --------------------------------------------------------------------------

_STANDING_ORDER = {
    # Pose sits right after presence: who is here, then how they are
    # arranged. Before appearance, because how a body is held is a fact
    # about this beat and its authored description is a fact about the body.
    "environment": 0, "presence": 1, "pose": 2, "appearance": 3,
    # How a body CARRIES itself this beat -- its surface demeanor -- sits
    # with the body's arrangement and description, before the observer's
    # own state (D1).
    "demeanor": 4,
    "body_state": 5, "sensation": 6, "body_part": 7, "body_region": 8,
    # The air of the place, after the bodies in it and after what is on them.
    "ambient": 9, "scent": 10,
}

#: Standing kinds that DESCRIBE a body's own surface rather than report its
#: situation. Deliberately excludes `pose` and `environment`: where a body is
#: and how it is arranged CHANGE, and are the two things a mind cannot read
#: off its own card.
_OWN_BODY_DESCRIPTION_KINDS = frozenset(("body_part", "body_region"))

# Standing kinds exempt from the player tier's unchanged-state suppression.
# EMPTY ON PURPOSE since 2026-09-07. It held `sensation` from 2026-08-24 on
# the argument that an unchanged contact "is present bodily input on every
# beat it remains true" and so must never be deduped. Measured over the
# owner's corpus that argument produced the single worst tic on the page:
# 649 of 1,500 player-view "You feel ..." sentences (43.3%) byte-identical to
# the previous beat's, and in one 70-beat stretch of chat 117 a hand that
# never left a belt was announced on 40 beats -- with a template that ends
# "continuous while the contact holds", i.e. the engine stating the fact is
# unchanged in the same breath as re-delivering it. A body adapts: a constant
# pressure stops being news. The memory rule below already says so (an
# unchanged sensation mints no episode); the view now agrees with it.
#
# What survives, and why nothing is lost: a NEW contact still leads the beat
# (`_FIRST_SIGHT_LEADS` carries `sensation`), a contact whose parts or manner
# change gets a new key and renders as changed, character mode is untouched
# (its `delta` is always False -- a stateless mind is re-told everything),
# and the "empty delta -> full render" fallback in perception still
# re-delivers the sensation on a beat where nothing else happened. The name
# is kept so the seam stays visible at its one read site.
ACTIVE_STANDING_KINDS = frozenset()


def _is_own_body_description(p):
    """Is this standing percept the observer describing their OWN surface.

    Character mode re-renders the full standing state every beat, and the
    reason is sound: a character agent is a stateless LLM call, so what is
    not in context is not in the mind. That argument does not reach the
    observer's own anatomy, because the CARD is in that context on every one
    of those calls -- `embodiment.extra_parts` carries the same count, place
    and description the view renders, so the view is repeating what the
    prompt already said.

    In a measured 27-beat run, 43% of one character's perception payload
    described their own body: 13,298 characters of authored anatomy, 92%
    byte-identical to the previous beat. A stable horn description repeated
    every beat despite the same structured horn data already being on the
    character card.

    Suppression is by dedupe key, not by kind, so the mutable half re-earns
    itself for free: `tucked` is hashed into a body_part's key, so wings
    coming out from under a coat change the key and render. `full_render`
    (an explicit look) re-renders everything, which is how a mind examines
    itself on purpose.
    """
    return (p.source_label == "you"
            and p.kind in _OWN_BODY_DESCRIPTION_KINDS)


_TIER_PHRASES = dict(_ENGLISH_COMPOSITOR["tier_phrases"])
_SIZE_PHRASES = dict(_ENGLISH_COMPOSITOR["size_phrases"])


# A placeholder holding the position the presence group will occupy, so
# the group can be rendered once the whole set is known without losing
# where it belongs in the discourse order. Identity comparison only.
_PRESENCE_SLOT = ("presence-slot", None)
_LANDSCAPE_SLOT = ("landscape-slot", None)


def _appearance_restates_label(percept):
    """Does this appearance percept say only what the observer's own label
    for the body already says.

    The presence line has already reported who is here, under this
    observer's label; an appearance summary identical to that label is the
    same fact a second time, and for a one-word summary it is ungrammatical
    besides. Measured, chat 98 turn 38: the player's ENTIRE view for the
    beat was "The lieutenant commander is close by. You see lieutenant
    commander." Compared on `_label_core`, which drops the article and the
    ordinal distinguisher, so the two spellings of one noun cannot slip past
    each other and the second of a pair is treated like the first.

    A percept this answers True for was still DELIVERED -- the observer has
    the description, it just cost no sentence -- so the caller records it in
    the first-mention ledger rather than leaving the body undescribed and
    re-describing it next beat.
    """
    if percept.kind != "appearance":
        return False
    desc = _appearance_as_prose((percept.data or {}).get("description"))
    if not desc:
        return False
    return _label_core(percept.source_label) == _label_core(desc)


@dataclass
class RenderedView:
    text: str
    spans: list                 # [(Percept, sentence)]
    standing_keys: set          # dedupe keys of ALL standing percepts seen
    described: set              # source names whose full appearance rendered
    # WHAT EACH STANDING KEY WAS FOR THIS OBSERVER THIS BEAT, as
    # {dedupe_key: verdict} over `STANDING_VERDICTS`. Empty outside the
    # player tier, which is the only one that diffs against a ledger at all.
    #
    # It is carried OUT of the render because the view is not the only thing
    # downstream re-delivers a standing fact to (B28): the narrator's sensory
    # manifest re-derives the same standing contacts from the scene, and with
    # no verdict to read it shipped every one of them as though it had just
    # happened -- measured chat 117, a hand that never left a belt announced
    # on 40 of 70 beats, in the same beats the view had correctly gone quiet.
    # One observer, one ledger, one answer: whoever re-delivers reads it.
    verdicts: dict = field(default_factory=dict)


#: Region and zone names that take a plural verb. An engine constant because
#: the NAMES are engine constants (`attire.REGIONS` plus the torso zones);
#: whether a LANGUAGE agrees in number is the pack's business, and a pack that
#: does not gives both `exposed_detail` templates the same string.
PLURAL_PLACES = frozenset({"arms", "hands", "legs", "feet"})


_COUNT_WORDS = {
    int(number): str(word)
    for number, word in _ENGLISH_COMPOSITOR["count_words"].items()
}


def _presence_clause(p, *, brief=False, fresh=False):
    """One body's presence as a bare clause -- no capital, no full stop, so
    it can stand alone or be joined with others.

    `brief` is the same fact at reduced cost, for a body whose presence has
    not changed since this observer's last view: who they are and where, and
    none of the qualifying clauses that were already delivered. See
    `_render_presence_group` for why an unchanged body is still named.

    `fresh` is its complement and the reason it exists: a body this observer
    did NOT hold last view and holds now. A CHANGE IN WHAT IS PRESENT MUST
    NOT READ AS FURNITURE. The engine already knew this was the beat's news
    -- `leads_the_beat` puts a first-sight presence in the beat half, so it
    reaches the narrator as a numbered `current_events` entry under the one
    rule in that sheet that is absolute -- and the SENTENCE still said "the
    compact wiry figure is close by on your right", which is the same
    grammar as "Sarah Moon is within arm's reach". Sitting between two
    standing-description entries, an arrival phrased as a location was
    indistinguishable from scenery, and the narrator dropped it.

    Measured live (chat 117 turn 58): a carbonic stalker that had been
    hunting the cast for thirty beats walked into the room they were
    standing in, reached both views, was entry 4 of the player's
    `current_events`, and did not reach the page at all. The player was not
    told a thing was beside them.

    "is now" against `presence_unchanged`'s "is still": the pair is the
    whole distinction, and it claims only what the observer has. It does not
    say the body came IN -- an observer may be meeting it because it moved,
    because they turned, or because a light reached it -- only that it is
    there and was not. You may not know what has arrived; you know that
    something has.
    """
    room = str(p.data.get("room") or "")
    tier = (_en("presence_in_room", room=room) if room
            else _TIER_PHRASES.get(str(p.data.get("tier")),
                                   _TIER_PHRASES["default"]))
    if brief:
        where = _strip_sentence_ends(p.data.get("at"))
        return _en("presence_unchanged", label=p.source_label,
                   where=_en("presence_at_bare", at=where) if where else tier)
    side = p.data.get("side")
    side_clause = _en("side", side=side) if side in ("left", "right") else ""
    # Relative magnitude qualifies every other clause in the view -- what can
    # be reached, held, or resolved at all -- so it rides the STANDING
    # presence sentence rather than waiting for an act to make it visible. An
    # unknown or absent label costs wording and never the beat.
    size = _SIZE_PHRASES.get(str(p.data.get("size") or ""), "")
    size_clause = f", {size}" if size else ""
    # Where they are standing, when the scene knows and they are in this
    # room. It rides the tier rather than replacing it: "close by" is how
    # far, "at the hearth" is where, and a reader wants both.
    at = _strip_sentence_ends(p.data.get("at"))
    at_clause = _en("presence_at", at=at) if at else ""
    # Seen over something: name what, and how much of them shows. Plain
    # words -- "behind the counter, from the waist up" -- never a fraction.
    behind = str(p.data.get("behind") or "").strip()
    cover_clause = ""
    if behind:
        cover_clause = _en("presence_behind", behind=behind)
        shows = str(p.data.get("shows") or "").strip()
        if shows:
            cover_clause += _en("presence_shows", shows=shows)
    # The observer's own beam is on this body (D5). A fact about where the
    # observer is POINTING, which is theirs by construction, and it rides
    # the presence sentence the way the tier and the cover clause do.
    beam_clause = _en("presence_in_beam") if p.data.get("in_beam") else ""
    where = (f"{tier}{at_clause}{side_clause}{size_clause}"
             f"{cover_clause}{beam_clause}")
    if fresh:
        return _en("presence_fresh", label=p.source_label, where=where)
    return f"{p.source_label} is {where}"


def _render_presence_group(percepts):
    """Every co-present body the observer can see, as ONE sentence.

    `percepts` is a list of (percept, brief) pairs. A SENTENCE THAT
    ENUMERATES WHO IS PRESENT MUST ENUMERATE EVERYONE PRESENT. The player
    view leads with what changed and suppresses standing state this observer
    already holds, which is right for a room, a smell or a pose and wrong for
    this one clause, because presence is delivered in the grammar of a closed
    conjunctive list -- and a reader cannot tell a delta from a roll-call
    when both read "A is here, B is here, and C is here."

    Measured, run 2026-09-05C `multitude` turn 1 (PM6): six bodies in the
    hall, and the player's outcome view read "Maren Vaunt is within arm's
    reach on your left, Ilsabet Roon is across the room on your left, Corin
    Ashe is across the room on your left, and Devereux Hallam is within arm's
    reach." Four names, an `and` before the last, and no Tobin Slake -- who
    was standing at the doors and was the only person in the room who did
    nothing that beat. The narrator then named exactly those four. Recurred
    on turns 4, 7, 8 and 9.

    So an unchanged body is still named, at reduced cost (`brief`): its label
    and where it is, without the tier, side, size and cover clauses it was
    already given. The delta survives as EMPHASIS -- what moved is spelled in
    full and leads the sentence -- rather than as an omission that reads as
    an absence.

    The order is NEAR TO FAR (D4, review 2026-09-07). A list of bodies is
    blocking, and blocking is what the page was missing: the sentence
    enumerated in scene-dict order, so the narrator received no arrangement
    at all and supplied one -- a body standing at the other door was put "on
    my right" (UNBUILT 1.149). Ordering withholds nothing; every body the
    observer can see is still in the same sentence with the same words.
    `presence_percepts` ALREADY SORTED THEM -- the rule lives in the IR so
    every pack's renderer inherits it -- and the sort below is a no-op for
    anything that came from there, kept because this function also renders
    percepts a caller built by hand.

    Three more things happen here, and all three are why the corpus replay
    called the composed prose staccato:

    * A room with four people in it produced four sentences of identical
      shape. They are one observation -- who is here -- and they read as
      one sentence.
    * Two bodies seen only as shapes produced the same sentence twice.
      Counted, they become "Two indistinct figures are close by", which is
      both shorter and more accurate about what the observer can tell.
    * FIDELITY IS NEVER MIXED. A `degraded` body folded into a `full`
      body's sentence would read as clearly perceived, which is the
      information boundary laundered by a prose choice. So the group
      splits by fidelity first and each half gets its own sentence -- the
      same rule `observations_from_render` applies when it merges atoms.

    Returns [(representative percept, sentence)], at most one per fidelity.
    """
    pairs = [(p, False, False) if isinstance(p, Percept)
             else (p[0], bool(p[1]), bool(p[2]) if len(p) > 2 else False)
             for p in percepts or ()]
    out = []
    for fidelity in ("full", "degraded"):
        # What CHANGED is spelled in full and comes first; what merely
        # persists closes the sentence. Stable within each half.
        group = [row for row in pairs if row[0].fidelity == fidelity]
        # NEAR TO FAR (D4). A no-op on a list from `presence_percepts`,
        # which minted the order; it re-states it for hand-built percepts.
        # Stable, and inside each half of the delta split below, so the
        # emphasis rule keeps its say: what changed is still spelled in
        # full and still leads. A room the geometry cannot measure gives
        # every body the same key and the order is untouched.
        group = sorted(group, key=lambda row: _presence_sort_key(row[0]))
        group = [x for x in group if not x[1]] + [x for x in group if x[1]]
        if not group:
            continue
        clauses, counts = [], {}
        for p, brief, fresh in group:
            clause = _presence_clause(p, brief=brief, fresh=fresh)
            if clause in counts:
                counts[clause] += 1
            else:
                counts[clause] = 1
                clauses.append(clause)
        rendered = []
        for clause in clauses:
            n = counts[clause]
            # Against the ACTIVE pack's label, not the English compat export.
            # Layer A mints this label through `_dim_figure()`, so comparing
            # it to `DIM_FIGURE` asks whether the story is in English -- and
            # where it is not, this `startswith` can never be true and the
            # rule silently does not run. What that costs is the COUNT:
            # identical clauses collapse either way, so an observer who can
            # plainly see two figures was told about one.
            #
            # The wording around the label stays English on purpose. This is
            # `_render_view_english`, the reference renderer a pack's own
            # adapter falls back to when it raises, and its contract is that
            # a malformed pack costs wording and never the beat. Losing a
            # fact the observer's own eyes have is not wording.
            singular, plural = _dim_figure(), _dim_figure(True)
            if n > 1 and clause.startswith(singular + " "):
                word = _COUNT_WORDS.get(n, str(n))
                rendered.append(
                    f"{word.casefold()} {plural}"
                    + clause[len(singular):].replace(" is ", " are ", 1))
            else:
                rendered.append(clause)
        out.append((group[0][0], _cap(_join_clauses(rendered)) + "."))
    return out



#: Articles and connectives a hand-authored `kind` may already carry. The
#: renderer supplies its own count word, so "a", "an", "the" and a leading
#: "and" would double up ("A and a long flexible tail...").
_LEADING_CONNECTIVES = tuple(_ENGLISH_COMPOSITOR["leading_connectives"])


def _strip_leading_connective(kind):
    text = " ".join(str(kind or "").split())
    lowered = text.casefold()
    for prefix in _LEADING_CONNECTIVES:
        if lowered.startswith(prefix):
            return text[len(prefix):]
    return text


def _render_body_part(p):
    """"Six tails emerge from the back of her waist" -- not "tail x6"."""
    count, kind = p.data["count"], p.data["part"]
    you = p.source_label == "you"
    word = _COUNT_NAMES.get(count, str(count))
    # A CARD'S `kind` IS AUTHORED, so it arrives however a human wrote it.
    # Measured live: "membranous bat-like wings" x2 rendered as "Two
    # membranous bat-like wingss", and "and a long flexible tail ending in
    # a spade" x1 as "A and a long flexible tail ...". The docstring's
    # example assumes a bare singular noun ("tail" -> "Six tails"); real
    # cards carry plurals and stray connectives, and a body's own anatomy
    # reading as gibberish in its owner's perception view is the loudest
    # possible way to look broken.
    kind = _strip_leading_connective(kind)
    plural = kind if kind.rstrip().endswith("s") else f"{kind}s"
    subject = f"{word} {kind}" if count == 1 else f"{word} {plural}"
    verb = "emerges" if count == 1 else "emerge"
    aspect, at = p.data["aspect"], p.data["at"]
    whose = "your" if you else f"{p.source_label}'s"
    if aspect == "sides":
        where = _en("body_part_where_sides", whose=whose, at=at)
    elif aspect in ("left", "right"):
        where = _en(
            "body_part_where_side", aspect=aspect, whose=whose, at=at)
    else:
        where = _en(
            "body_part_where_aspect", aspect=aspect, whose=whose, at=at)
    sentence = f"{_cap(subject)} {verb} {where}"
    if p.data.get("description"):
        sentence += f", {p.data['description'].rstrip('.')}"
    if p.data.get("tucked"):
        sentence += _en("body_part_tucked")
    return sentence + "."


def _render_pose(p, *, past=False):
    """One body's arrangement as a sentence.

    Built as clauses so a pose with only a posture (a body seen as shapes)
    reads as naturally as one carrying support, relation and constraint --
    the degraded case is a shorter sentence, not a sentence with holes in
    it.

    `past` is for the episode renderer, and the tense is chosen HERE rather
    than patched afterwards: a memory saying "I am kneeling" is a claim
    about now, and regex-ing tense out of finished prose would also reach
    into the authored `detail` text, which is not ours to rewrite.
    """
    you = p.source_label == "you"
    if you:
        subject = _en("pose_self_past" if past else "pose_self_present")
    else:
        subject = _en(
            "pose_other_past" if past else "pose_other_present",
            label=_cap(p.source_label))
    def value(field):
        text = str(p.data.get(field) or "").strip()
        # Episode prose is first person whether the pose belongs to the mind
        # or to somebody it watched.  Thus another body's ``astride you`` is
        # remembered as ``astride me``, while the owner's ``your heels`` is
        # remembered as ``my heels`` -- and the owner's "as you turn" as "as
        # I turn", from the rewrite that still knew "she" was the subject.
        return _said_as_mine(p.data, field) if past else text

    parts = [value("posture")]
    support = value("support")
    if support:
        parts.append(support if support.split()[:1] and support.split()[0] in
                     _POSE_PREPOSITIONS else _en("pose_support", support=support))
    other = value("relative_to")
    if other:
        relation = value("relation")
        parts.append(f"{relation} {other}" if relation
                     else _en("pose_relation", other=other))
    clause = " ".join(x for x in parts if x).strip()
    if not clause:
        return ""
    sentence = f"{subject} {clause}"
    constraint = value("constraint")
    if constraint:
        sentence += f", {constraint}"
    detail = value("detail")
    if detail:
        sentence += f" — {detail.rstrip('.')}"
    return sentence.rstrip(".") + "."


_POSE_PREPOSITIONS = frozenset(_ENGLISH_COMPOSITOR["pose_prepositions"])
# The article and bare-determiner tables are read from the ACTIVE pack at use
# time (`_pack_words`), because the text they shape is data the language
# adapter renders verbatim; only the English renderer's own clause assembly
# above still reads the English card.


def _feature_items(rows, *, placed=True):
    """The furniture rows as rendered noun phrases, near to far.

    `placed` is False for furniture in ANOTHER room, seen through an opening.
    The whole distance vocabulary here -- close by, across the room, at the
    edge of sight -- is measured WITHIN one room, so spending it on the far
    side of a threshold states a distance nobody measured: "across the room"
    about a thing that is across a different room. The things are named and
    the distance is simply not claimed, which is what the observer actually
    has.
    """
    items = []
    for row in rows or ():
        # An authored desc is a NOUN PHRASE here, whatever it was written as
        # (`_noun_phrase`): this list is the inside of one sentence.
        desc = _noun_phrase((row or {}).get("desc"))
        if not desc:
            continue
        if not placed:
            items.append(desc)
            continue
        if row.get("peripheral"):
            items.append(_en("feature_glimpse", desc=desc))
            continue
        tier = _TIER_PHRASES.get(str(row.get("tier") or ""), "")
        side = row.get("side")
        where = _en("side", side=side).strip() if side in ("left", "right") \
            else ""
        place = " ".join(part for part in (tier, where) if part)
        items.append(_en("feature_item", desc=desc, place=place).strip())
    return items


def _render_features(rows):
    """The furniture this observer's eyes reach, as one sentence a person
    would say -- near to far, each thing by where it lies. NEVER the grid:
    no cell, no fraction, no degree, no sector name reaches the page; a
    thing is close by, across the room, on your left, or at the edge of
    sight, which is the whole vocabulary a body has for it."""
    items = _feature_items(rows)
    if not items:
        return ""
    return _en("features", items=_join_clauses(items))


def _render_openings(openings, here=""):
    """Every boundary of this room the observer can see, and what sight
    reaches past it.

    THE CLASS: a way out is a fact about the room, and what an opening
    admits is a fact about the opening. The engine had neither. Door
    pseudo-anchors are minted for every edge (`spatial_geometry`) and then
    dropped from the furniture list as `implicit` on the stated grounds that
    "the exits digest already carries them" -- but that digest
    (`director._egocentric_exits`) is built for the Director and reaches no
    observer, so the doorway was minted and discarded and no view in this
    engine had ever named one. `presence_percepts` meanwhile grew a
    cross-room tier for BODIES, because an interviewer was receiving the cell
    and not the woman in it; the same subtraction was never lifted for the
    PLACE, so a mind could see a person through a door and never the room
    they stood in.

    SUBTRACTS IN THREE PLACES, and the order matters. A boundary the
    observer's own cone or line does not reach never arrives at all. A
    boundary sight does not cross (a shut door, a wall) arrives as itself and
    NAMES NOTHING BEYOND IT -- naming the room behind a closed door would be
    the leak this whole layer has to avoid. And a room beyond that is dark
    arrives as darkness, because you see what is lit.
    """
    # TWO BOUNDARIES ARE NEVER ONE SENTENCE TWICE. A way out with no authored
    # name falls back to its barrier's generic phrasing, so a room with two of
    # them rendered "The doorway is shut. The doorway is shut." (run
    # 2026-09-05C `masque`, turn 15, PX20) -- referentially indistinguishable
    # and reading as a stutter. Describing the second one by where it goes is
    # exactly what a blind boundary may not do, so the distinguisher is the
    # one `assign_stranger_labels` already uses for bodies whose appearance
    # cannot tell them apart: an ordinal, which distinguishes by NOTHING the
    # observer has not already got -- they can see two doorways, and counting
    # them adds no attribute and no identity.
    rows = []
    for opening in openings or ():
        desc = _noun_phrase((opening or {}).get("desc"))
        if desc:
            rows.append((opening, desc))
    total, so_far = {}, {}
    for _opening, desc in rows:
        total[desc] = total.get(desc, 0) + 1
    parts = []
    for opening, desc in rows:
        # A WAY THAT GOES ON, NEVER A DOOR SEEN THROUGH (`perception.
        # _visible_openings`' `onward` row: an unbuilt frontier stub's far
        # join). The place is named and nothing past the join is described,
        # in the words the pack already has for a way that goes on from here
        # -- up, down, or on. It names no boundary, so it takes no ordinal
        # from one beside it: said before the ordinals are counted out.
        if str(opening.get("state") or "") == "onward":
            room = str(opening.get("room_name") or "").strip()
            if room:
                parts.append(_cap(_en(
                    {"up": "opening_onward_up", "down": "opening_onward_down"}.get(
                        opening.get("vertical"), "opening_onward"), room=room)))
            continue
        if total[desc] > 1:
            so_far[desc] = so_far.get(desc, 0) + 1
            if so_far[desc] > 1:
                desc = _ordinal_label(desc, so_far[desc])
        state = str(opening.get("state") or "")
        room = str(opening.get("room_name") or "").strip()
        if state == "blind":
            parts.append(_cap(_en("opening_closed", opening=desc)))
            continue
        if state == "dark":
            parts.append(_cap(_en("opening_dark", opening=desc)))
            continue
        if state != "seen" or not room:
            parts.append(_cap(_en("opening_bare", opening=desc)))
            continue
        if opening.get("way") == "overlook" and opening.get("vertical") in ("up", "down"):
            parts.append(_cap(_en("opening_seen_above" if opening["vertical"] == "up"
                                  else "opening_seen_below", opening=desc, room=room)))
        elif _bare_words(desc) in (_bare_words(room), _bare_words(here)) and desc:
            # A way named for a room it joins identifies no boundary: "Through
            # the long stone stair is the long stone stair" (Kirinoura, scratch
            # chat 167, 2026-10-05), and from the stair's far side "Through
            # the terrace is the long stone stair". The way goes on from HERE
            # to the room -- worded true of any destination, a place as much
            # as a passage (review, 2026-10-05: 97 of 398 named edges in the
            # owner's scenes carry their destination's name, most of them
            # places).
            parts.append(_cap(_en(
                {"up": "opening_onward_up", "down": "opening_onward_down"}.get(
                    opening.get("vertical"), "opening_onward"), room=room)))
        else:
            parts.append(_cap(_en("opening_seen", opening=desc, room=room)))
        notes = str(opening.get("room_notes") or "").strip()
        if notes:
            parts.append(notes if notes[-1:] in ".!?" else notes + ".")
        items = _feature_items(opening.get("features"), placed=False)
        if items:
            parts.append(_en("opening_features", items=_join_clauses(items)))
    return " ".join(parts)


def _end_sentence(text):
    """`text` ending a sentence: its own terminal stop kept, one added only
    where it has none. A clause the pack writes as a whole sentence ("The
    air is mild.") was given a second one by the sensation renderer, in
    every outdoor view and memory ("The air is mild..", seen 2026-10-05)."""
    text = str(text or "").rstrip()
    return text if (not text or text[-1] in ".!?\u3002") else text + "."


def _render_standing(p):
    if p.kind == "environment":
        parts = []
        if p.data.get("room_name"):
            parts.append(_en("room", room=p.data["room_name"]))
        if p.data.get("room_notes"):
            notes = str(p.data["room_notes"]).strip()
            if notes and notes[-1:] not in ".!?":
                notes += "."
            parts.append(notes)
        sentence = _render_features(p.data.get("features"))
        if sentence:
            parts.append(sentence)
        ways = _render_openings(p.data.get("openings"), here=p.data.get("room_name") or "")
        if ways:
            parts.append(ways)
        # WHERE THE LIGHT FALLS, when the field found the room uneven; else
        # the flat sentence, exactly as before (the shape is only ever
        # present when there is more to say than one word for the room).
        shaped = render_light_shape(p.data.get("light_shape"))
        if shaped:
            parts.append(shaped)
        else:
            light = str(p.data.get("light") or "").casefold()
            if light in ("dim", "low"):
                parts.append(_en("light_dim"))
            elif light in ("dark", "none", "pitch_black", "black"):
                parts.append(_en("light_dark"))
        return " ".join(parts)
    if p.kind == "presence":
        return _cap(_presence_clause(p)) + "."
    if p.kind == "appearance":
        # A CHANGE RENDERS AS THE CHANGE. Only when there is nothing
        # readable to say about it does the full description stand in --
        # failing toward delivering more, because a change the observer can
        # see and the page does not mention is the worse error.
        change = str(p.data.get("delta") or "").strip()
        if change:
            # The LABEL, because a change needs a body to belong to: the
            # first cut of this rendered "You see no longer wearing haori."
            # -- the delta reads as a predicate and the appearance template
            # it borrowed supplies a subject that is the wrong one. The
            # label is this observer's own, so it carries the identity floor
            # (a stranger stays "the unfamiliar person") for free.
            return _cap(_en("appearance_change",
                            label=p.source_label or "someone", change=change))
        desc = _appearance_as_prose(p.data.get("description"))
        if _appearance_restates_label(p):
            return ""
        return _en("appearance", description=desc) if desc else ""
    if p.kind == "pose":
        return _render_pose(p)
    if p.kind == "body_part":
        return _render_body_part(p)
    if p.kind == "demeanor":
        # Spliced like every other authored description (`_noun_phrase`):
        # a character writes its demeanor as a sentence, and the raw form
        # rendered "An indistinct figure seems A wet, nervous young man on a
        # bench, ...." (scratch play 2026-09-14, chat 2 turn 1).
        text = _spliced_fragment(str(p.data.get("demeanor") or ""))
        return _en("demeanor", label=_cap(p.source_label), demeanor=text) \
            if text else ""
    if p.kind == "body_state":
        parts = []
        if p.data.get("posture"):
            parts.append(_en("posture", value=p.data["posture"]))
        if p.data.get("activity"):
            parts.append(_en("activity", value=p.data["activity"]))
        if p.data.get("held_items"):
            parts.append(_en("held", items=", ".join(p.data["held_items"])))
        return " ".join(parts)
    if p.kind == "sensation":
        if p.data.get("ears") in EAR_STATES:
            return _en("ears_" + p.data["ears"])
        clause = str(p.data.get("clause") or "").strip()
        return _end_sentence(_cap(clause)) if clause else ""
    if p.kind == "body_region":
        place = str(p.data.get("place") or "").strip()
        detail = str(p.data.get("detail") or "").strip()
        if not place or not detail:
            return ""
        if detail[-1:] not in ".!?":
            detail += "."
        subject = (_en("exposed_self", place=place)
                   if p.source_label == "you" else _en(
                       "exposed_other", label=_cap(p.source_label), place=place))
        # HALF THE PLACE NAMES ARE PLURAL. `place` is an engine constant -- a
        # member of `attire.REGIONS` or a torso zone -- so the agreement is
        # decidable here, and "Hinami's exposed feet is visible" was on the
        # page. Not a spelling rule: `feet` is plural and does not end in `s`,
        # which is precisely the case a spelling rule gets wrong.
        template = ("exposed_detail_plural"
                    if place.casefold() in PLURAL_PLACES else "exposed_detail")
        return _en(template, subject=subject, detail=detail)
    if p.kind == "ambient":
        return _render_ambient(p)
    if p.kind == "scent":
        return _render_scent(p)
    return ""


def _render_scent(p, *, episode=False):
    """Three shapes, chosen by what the observer actually has a channel to:
    the smell and whose it is, the smell alone, or the smell as a faint thing
    from somewhere beyond. The percept decides which; this only spells it."""
    prefix = "episode_" if episode else ""
    scent = str(p.data.get("scent") or "").strip()
    if not scent:
        return ""
    if p.data.get("level") == "muffled":
        return _en(prefix + "scent_faint", scent=scent)
    if p.data.get("attributed") and p.source_label:
        return _en(prefix + "scent_source",
                   label=_cap(p.source_label), scent=scent)
    return _en(prefix + "scent_air", scent=scent)


def _render_ambient(p, *, episode=False):
    """An ambient percept's sentence, standing or ordered alike -- in the
    episode's own words where a typed renderer carries them (`episode`)."""
    if p.data.get("landscape"):
        lines = landscape_lines([p])
        return render_landscape_line(lines[0][1]) if lines else ""
    if p.data.get("ceased"):
        # A stopping that names what stopped carries its own sentence
        # (`weather_sound_percepts`: "The rain has stopped."); the room's
        # soundscape keeps the pack's generic one.
        own = str(p.data.get("desc") or "").strip()
        if own:
            return own if own[-1:] in ".!?" else own + "."
        return _en("sound_subsided" if p.data.get("subsided")
                   else "sound_ceased")
    if p.data.get("soundscape"):
        return render_sound_shape(p.data.get("soundscape"))
    if p.data.get("distant"):
        return render_distant_sound(p.data["distant"], episode=episode)
    desc = str(p.data.get("desc") or "").strip()
    if desc and desc[-1:] not in ".!?":
        desc += "."
    return desc


def _en_voice_line(p):
    """A voice whose words did not carry (`fidelity == "voice"`): whose it
    is where the listener knows or sees the speaker, how loud, and from
    where -- "Mara's voice, raised, beyond the wall -- the words do not
    carry." Never a word of the line."""
    d = p.data or {}
    loudness = {"loud": _en("speech_voice_raised"),
                "shout": _en("speech_voice_shouting")}.get(
        str(d.get("volume") or "").casefold(), "")
    bearing = str(d.get("bearing") or "")
    where = _en("speech_voice_where", where=bearing) if bearing else ""
    if d.get("attributed") and str(p.source_label or "").strip():
        return _en("speech_voice", label=_cap(p.source_label),
                   loudness=loudness, where=where)
    return _en("speech_voice_unknown", loudness=loudness, where=where)


def _heard_after(p, line, *, ended=False):
    """What follows a line where the listener did not have all of it: the
    tone its voice carried (`tone_heard`, for a fragment or a voice alone),
    and a stranger's voice said once (`voice_apart`) -- in that order,
    each its own sentence."""
    if not line:
        return line
    d = p.data or {}
    extra = []
    tone = _feeling_heard(d)
    if tone and p.fidelity in ("fragment", "voice"):
        extra.append(_en("speech_voice_tone", tone=tone))
    if d.get("own_name") and p.fidelity in ("fragment", "voice"):
        extra.append(_en("speech_own_name"))
    if d.get("voice_apart"):
        extra.append(_en("voice_register", register=d["voice_apart"]))
    if not extra:
        return line
    head = _end_sentence(line) if ended or p.fidelity != "full" \
        else line.rstrip()
    return head + " " + " ".join(extra)


def _render_event(p):
    if p.kind == "speech":
        # An answer that did not come (D6). Before the fragment branch,
        # because there is no fragment and no body to render: the percept
        # carries no words by construction.
        if p.fidelity == "silence":
            return _en("speech_silence", label=_cap(p.source_label))
        # Detected, and nothing more: no words, no speaker, no tone.
        if p.fidelity == "trace":
            bearing = str(p.data.get("bearing") or "")
            return (_en("speech_trace_placed", where=bearing) if bearing
                    else _en("speech_trace"))
        # The voice, without its words (§ 12 of the sound note).
        if p.fidelity == "voice":
            return _heard_after(p, _en_voice_line(p))
        body = p.data.get("body") or ""
        via = str(p.data.get("via") or "")
        # `_inject_dialogue` into an empty document is the production grammar
        # (bare-infinitive heard form, conducted, articulation) emitting into
        # nothing -- no duplicate detection against model prose needed.
        if p.fidelity == "fragment":
            line = _en(
                "muffled_attributed" if p.data.get("attributed") else "muffled",
                label=_cap(p.source_label),
                fragment=p.data.get("fragment", ""))
        else:
            line = _inject_dialogue(
                "", p.source_label, f'"{body}"', p.data.get("level", "full"),
                p.data.get("volume", "normal"), p.data.get("can_see", False),
                conducted=p.data.get("conducted", False),
                tone=p.data.get("manner", p.data.get("tone", "")),
                articulation=p.data.get("articulation", ""))
        # The route is part of what was perceived, not a flourish. A voice on a
        # speaker and a voice at your shoulder are different facts, and the
        # view is where a reader learns which one this was -- drop it here and
        # the whole channel reads as somebody standing in the room.
        bearing = str(p.data.get("bearing") or "")
        if via and line:
            line = _en("speech_via", sentence=line.rstrip("."), via=via)
        elif bearing and line:
            line = _en("speech_from", sentence=line.rstrip("."), where=bearing)
        # A voice too long for the manner slot, said once after the line
        # (`_voice_fields`).
        if line and p.fidelity != "fragment" and p.data.get("said_apart"):
            # A route clause ends without a stop; a line ends on its quote.
            line = (_end_sentence(line) if via or bearing else line.rstrip()) \
                + " " + _en("voice_register", register=p.data["said_apart"])
        return _heard_after(p, line, ended=bool(via or bearing))
    if p.kind == "communication":
        line = _observable_predicate(
            p.source_label, p.data.get("surface")) or ""
        via = str(p.data.get("via") or "")
        return (_en("speech_via", sentence=line.rstrip("."), via=via)
                if via and line else line)
    if p.kind == "act":
        if p.data.get("unseen"):
            bearing = str(p.data.get("bearing") or "").strip()
            return (_en("act_heard_placed", where=bearing) if bearing
                    else _en("act_heard"))
        if p.fidelity == "shapes":
            room = str(p.data.get("room") or "")
            if room:
                return _en("act_shapes_placed", label=_cap(p.source_label),
                           where=_en("presence_in_room", room=room))
            return _en("act_shapes", label=_cap(p.source_label))
        return _observable_predicate(
            p.source_label, p.data.get("surface")) or ""
    if p.kind == "cue":
        cue = str(p.data.get("cue") or "").strip()
        return _en("cue", label=_cap(p.source_label), cue=cue) if cue else ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return _en("arrived", label=_cap(p.source_label))
        return _en("departed", label=_cap(p.source_label))
    if p.kind == "substance":
        clause = str(p.data.get("clause") or "").strip()
        return _end_sentence(_cap(clause)) if clause else ""
    # AN AMBIENT PERCEPT WITH AN ORDER IS A THING THAT HAPPENED THIS BEAT --
    # a beat's own sound event (`ambient_percepts(order_key=...)`), what a
    # look at the horizon found (`vista_percepts`). This renderer had no
    # branch for it, so in English every one rendered to nothing and was
    # dropped, while the Japanese adapter rendered it: measured 2026-10-04,
    # chat 117's siphon-vent hiss (the case the ordered key was minted for)
    # composed to '' in both the player's and a character's view.
    if p.kind == "ambient":
        return _render_ambient(p)
    return ""


def _render_view_english(percepts, *, mode="character",
                         prev_standing=frozenset(),
                         prev_described=frozenset(), full_render=False):
    """Decision-free realisation of one observer's percepts.

    ``mode='character'`` renders the full standing state every beat, including
    complete visible anatomy and attire for every OTHER person. The observer's
    own body description (`_is_own_body_description` -- anatomy and bare
    regions, never pose or place) is delta-suppressed because the updated card
    and self.attire already carry it into the same call.

    ``mode='player'`` LEADS WITH WHAT CHANGED. The view is two halves: the
    BEAT -- this beat's events in declared order, then the standing percepts
    `standing_verdicts` calls changed for THIS observer, with a changed room
    last -- and then the BACKGROUND: first mentions, re-encounters, and the
    sensations that are still true. What is continuously true is context;
    what is different since this observer last perceived it is the beat.
    ``full_render`` (an explicit look) re-renders the whole standing state,
    which is how the background is asked for on purpose. An unchanged
    sensation is standing state like any other on the player tier: it led
    the beat when it began, it renders again when its parts or manner
    change, and between those it is context the reader already holds
    (`ACTIVE_STANDING_KINDS`, and the measurement beside it).

    Events always render, in declared order -- chronology is authoritative.

    THE APPEARANCE BRANCH ASKS THE LEDGER BEFORE IT ASKS `force`. `force` is
    an objective judgement ("some visible-form channel moved this beat") and
    it was deciding a per-observer question. Measured live (chat 89, turns
    3-27): it fired on every single beat while the composed description
    stayed byte-identical, and the same 342-character card went to the
    narrator twenty-five times running. An overlay wiggle whose composed
    description hashes to the key this observer already holds is no change
    FOR THIS OBSERVER, and now suppresses; a description that actually moved
    renders as the change (the attire delta when there is one, the current
    description when there is not) and leads.

    Returns a RenderedView; ``text`` may be "" ("nothing reached this mind"
    -- the caller stores None, as today).
    """
    percepts = list(percepts or [])
    residue = [p for p in percepts if p.kind == "residue"]
    if residue:
        p = residue[0]
        text = _compose_residue_view(
            p.data.get("level"), targeted=p.data.get("targeted", False),
            loud_event=p.data.get("loud_event", False),
            pain=p.data.get("pain", False), woke=p.data.get("woke", ""))
        rest = [q for q in percepts if q.kind != "residue"]
        if p.data.get("woke") and rest:
            # A SLEEPER A SOUND WOKE PERCEIVES THE REST OF THE BEAT
            # (DESIGN_SOUND_FIELD § 17): what woke them leads, as the
            # residue tells it, and the remainder follows as an awake mind's
            # view. What the remainder holds was decided by the caller
            # (`perception._composer_outcome_views`, from the waking moment
            # on); this only orders it. The woke sentence is the beat's
            # (`as_beat`), and the ledger files the room they woke in.
            after = _render_view_english(
                rest, mode=mode, prev_standing=prev_standing,
                prev_described=prev_described, full_render=full_render)
            return RenderedView(
                text=(text + " " + after.text).strip(),
                spans=[(as_beat(p), text)] + list(after.spans),
                standing_keys=set(after.standing_keys),
                described=after.described, verdicts=dict(after.verdicts))
        # A VOICE ONCE KNOWN STAYS KNOWN, asleep as awake (`carried_voices`):
        # the ledger is replaced each beat, and filing the residue's key alone
        # forgot every voice this mind knew, so its first line after a beat
        # asleep re-declared each speaker's register. The Japanese renderer
        # carried them; this one did not (audit agents_composer F8,
        # 2026-11-01).
        return RenderedView(text=text, spans=[(p, text)],
                            standing_keys=carried_voices(prev_standing)
                            | {p.dedupe_key},
                            described=set(prev_described))

    standing = sorted(
        [p for p in percepts if p.order_key is None],
        key=lambda p: _STANDING_ORDER.get(p.kind, 9))
    events = sorted(
        [p for p in percepts if p.order_key is not None],
        key=lambda p: p.order_key)

    player = mode == "player"
    delta = player and not full_render
    described = set(prev_described)
    # A VOICE ONCE KNOWN STAYS KNOWN. The ledger is rolled forward a turn at
    # a time and a standing key survives only while something re-files it;
    # a voice key was re-filed only on a beat the speaker spoke, so one
    # silent beat made their next line a first hearing again (descent copy,
    # beats 120-121). Carried forward unconditionally, like a description
    # already delivered: knowing how somebody sounds does not lapse.
    standing_keys = carried_voices(prev_standing)
    seen_dedupe = set()
    verdicts = view_verdicts(standing, prev_standing, prev_described,
                             player=player)
    # Presence is ONE observation -- who is here -- so the whole group takes
    # one side of the partition, decided before the loop reaches the first
    # of them: if any body in it is new or has moved tier, who is here is
    # this beat's news.
    # A BODY YOU CANNOT NAME IS NEVER BACKGROUND. `leads_the_beat` asks
    # what CHANGED, which is the right question for a room, a smell or a
    # pose, and the wrong one for a stranger standing still: nothing about
    # them changes, so who is here stops being the beat's news and the
    # sentence naming them becomes standing description -- which the
    # narrator sheet says in as many words "carries no obligation".
    #
    # Measured live, chat 117 turns 58 and 59. A carbonic stalker walked
    # into the room the cast were standing in and did not reach the page.
    # On the arrival beat the sentence read as furniture; on the NEXT beat
    # it was furniture, because the thing had the decency to hold still. Two
    # beats with a hunter at arm's reach and a player who was never told.
    #
    # A person does not stop noticing a stranger they cannot name in a dark
    # corridor, and the engine already knows which bodies those are. Bounded
    # by measurement rather than by hope: across the author's 3771 composed
    # beats an unrecognised body is co-present on 235 (6.2%), never more
    # than two at once -- crowds are the crowd system's and never arrive
    # here as company rows. So this is rare, and every instance of it is the
    # case worth spending a sentence on.
    _stranger_present = any(
        p.kind == "presence" and not (p.data or {}).get("known", True)
        for p in standing)
    presence_leads = player and (_stranger_present or any(
        leads_the_beat(p, verdicts.get(p.dedupe_key, "first"), prev_standing)
        for p in standing if p.kind == "presence"))
    # The far places are one view of one landscape, said as lines rather
    # than a sentence each (`landscape_lines`), so like the roll-call they
    # take one half of the partition: the beat's, when any place in them is
    # this beat's news.
    landscape_group = []
    landscape_leads = player and any(
        leads_the_beat(p, verdicts.get(p.dedupe_key, "first"), prev_standing)
        for p in standing
        if is_landscape(p) and not (delta and p.dedupe_key in prev_standing))

    standing_spans = []         # the background half in player mode
    beat_spans = []             # player mode only
    presence_group = []
    for p in standing:
        standing_keys.add(p.dedupe_key)
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        verdict = verdicts.get(p.dedupe_key, "first")
        # A silence is only news to an ear that had the noise (D3). The key
        # is already filed above, so the sound coming back next beat still
        # reads as a change against it.
        if unheard_ceasing(p, verdict):
            continue
        # ...and a steady sound it has been hearing, unchanged, has faded
        # from its attention (`habituated`) -- on either tier.
        if habituated(p, verdict, full_render=full_render):
            continue
        leads = player and leads_the_beat(p, verdict, prev_standing)
        if is_landscape(p):
            if delta and p.dedupe_key in prev_standing:
                continue
            landscape_group.append(p)
            if len(landscape_group) == 1:
                (beat_spans if landscape_leads else standing_spans).append(
                    _LANDSCAPE_SLOT)
            continue
        if p.kind == "presence":
            # NEVER SUPPRESSED, only shortened. A body that stands still is
            # still in the room, and the sentence that says who is here is
            # the one clause in this view whose grammar claims to be
            # exhaustive (`_render_presence_group`, PM6).
            #
            # `standing` is already sorted by _STANDING_ORDER, so
            # re-inserting the presence group at the first presence position
            # keeps the discourse order of whichever half it belongs to
            # intact.
            # (percept, brief, fresh). `brief` is a presence this observer
            # already held unchanged; `fresh` its complement -- a BODY they
            # did not hold at all and hold now, which only a ledger can tell
            # from an opening view where everyone is new and nobody arrived.
            #
            # Compared on `_subject_prefix`, never on the whole key: a
            # dedupe key carries the presence's STATE as well as its
            # subject, so a body that merely crossed the room has a key the
            # ledger has not seen and is not new. Caught by
            # `test_a_body_that_stood_still_is_still_in_the_room`, which
            # read "Maren Vaunt is now within arm's reach" for a woman who
            # had been in the room the whole time.
            _subject = _subject_prefix(p.dedupe_key)
            _held = {_subject_prefix(k) for k in (prev_standing or ())}
            _held.discard(None)
            presence_group.append(
                (p, delta and p.dedupe_key in prev_standing,
                 bool(delta and prev_standing and _subject
                      and _subject not in _held)))
            if len(presence_group) == 1:
                (beat_spans if presence_leads else standing_spans).append(
                    _PRESENCE_SLOT)
            continue
        if p.kind == "appearance":
            if (player and not full_render and verdict == "unchanged"
                    and not appearance_delta(p)):
                # Already delivered, byte for byte, to this observer. This
                # is the line `force` used to be able to walk past.
                continue
            if (player and not full_render and verdict == "reearn"
                    and not p.data.get("reearn")
                    and not p.data.get("force")):
                # The standing ledger says nothing about this body at all,
                # and the older first-mention ledger says it was described
                # once. Nothing here claims it moved, so it stays told.
                continue
        elif (delta and p.dedupe_key in prev_standing
              and p.kind not in ACTIVE_STANDING_KINDS
              and not asked_this_beat(p)):
            continue
        elif (not full_render and p.dedupe_key in prev_standing
                and _is_own_body_description(p)):
            continue
        sentence = _render_standing(p)
        # A description the label already carried was delivered without
        # costing a sentence (`_appearance_restates_label`); leaving it out
        # of the ledger would re-offer it as a first mention every beat.
        if p.kind == "appearance" and (
                sentence or _appearance_restates_label(p)):
            described.add(str(p.data.get("source_key") or ""))
        if not sentence:
            continue
        if leads:
            beat_spans.append((as_beat(p), sentence))
        else:
            standing_spans.append((p, sentence))
    for half in (beat_spans, standing_spans):
        if _PRESENCE_SLOT in half:
            at = half.index(_PRESENCE_SLOT)
            group = _render_presence_group(presence_group)
            if half is beat_spans:
                group = [(as_beat(gp), sentence) for gp, sentence in group]
            half[at:at + 1] = group
        if _LANDSCAPE_SLOT in half:
            at = half.index(_LANDSCAPE_SLOT)
            group = [(as_beat(rep) if half is beat_spans else rep, sentence)
                     for rep, line in landscape_lines(landscape_group)
                     for sentence in [render_landscape_line(line)] if sentence]
            half[at:at + 1] = group

    event_spans = []
    for p in events:
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        sentence = _render_event(p)
        if sentence:
            event_spans.append((p, _cap(sentence)))
            # A voice SAID is a voice established for this observer -- never
            # one only heard round a corner, whose register no line has said
            # yet (review round 5, 2026-10-05).
            if p.data.get("voice_key") and _can_say_the_voice(p):
                standing_keys.add(str(p.data["voice_key"]))
            # A look at a standing thing files the thing (`vista_percepts`).
            if p.data.get("files_standing"):
                standing_keys.add(str(p.data["files_standing"]))

    if player:
        # The ordering rule itself lives in `player_view_order`, which every
        # pack calls, so the reference renderer cannot drift from one.
        spans = player_view_order(event_spans + beat_spans + standing_spans)
        # A ROLL-CALL IS ADDED TO A VIEW; IT IS NEVER THE WHOLE OF ONE. The
        # brief clause above exists so the presence sentence stays honest
        # about who is in the room, not so it can be a beat's entire content
        # -- a beat whose only content is that nobody moved has told this
        # mind nothing, and the empty view is exactly what
        # `perception._composer_render_observer`'s floor reads before asking
        # for the background instead (chat 98 turns 13, 15, 16, 20, 21, 36).
        # ...unless one of the people in the room cannot be NAMED. "Nobody
        # moved" is nothing to report about company this observer knows, and
        # is the whole of the report when a stranger is standing there: the
        # beat where a hunter holds still at arm's reach is exactly the beat
        # the player most needs, and it is the one this rule was emptying
        # (chat 117 turn 59, the beat after it walked in).
        # Decided on the NEAR spans: a far line beside an unchanged roll-call
        # is added to the view, never the whole of it -- kept, so the floor
        # (which also asks the near spans) re-renders the room around it.
        near_spans = [(p, s) for p, s in spans if not far_sight(p)]
        if (delta and near_spans and not _stranger_present
                and all(row[1] for row in presence_group)
                and all(p.kind == "presence" for p, _s in near_spans)):
            spans = [(p, s) for p, s in spans if far_sight(p)]
    else:
        # Discourse rule: a sudden event chain leads; otherwise standing state
        # anchors the view and the beat follows.
        sudden = any(p.suddenness >= 0.6 for p, _ in event_spans)
        spans = (event_spans + standing_spans) if sudden \
            else (standing_spans + event_spans)
    text = " ".join(sentence for _, sentence in spans).strip()
    # The ledger's verdicts are the player tier's, as before: a character's
    # steady-sound verdicts decide its view and are not filed.
    return RenderedView(text=text, spans=spans,
                        standing_keys=standing_keys, described=described,
                        verdicts=dict(verdicts) if player else {})


def render_view(percepts, *, mode="character", prev_standing=frozenset(),
                prev_described=frozenset(), full_render=False,
                language=None, renderer=None):
    """Render through the story language's deterministic Layer-B adapter.

    Layer A's admitted ``Percept`` list is unchanged and remains the
    information boundary. A language adapter receives only that list and the
    ordinary render-mode state, so changing languages cannot grant it scene,
    database, or identity knowledge that the observer never earned.

    A QUIET BEAT STILL COMPOSES TO "" HERE, and that is the honest answer:
    this function renders a DELTA, and an empty delta means "nothing new",
    not "nothing reached this mind". The two are different states and only
    the stage that holds the observer decides which one the narrator is
    handed -- see `perception._composer_outcome`, which asks for the
    background on a player view the delta emptied rather than storing the
    None that `agents/narration.py` reads as a claim about the world.
    """
    # THE VERDICT IS THE ENGINE'S, NOT THE PACK'S. Computed here rather than
    # inside a renderer so both language paths carry the same answer: a pack
    # that never heard of the field cannot leave a downstream re-delivery
    # (see `RenderedView.verdicts`) with nothing to read.
    def _stamp(out):
        if mode == "player" and not out.verdicts:
            out.verdicts = standing_verdicts(
                [p for p in percepts or [] if p.order_key is None],
                prev_standing, prev_described)
        return out

    percepts = _names_kept(_one_voice_each(percepts))
    selected = renderer if renderer is not None else _safe_renderer(language)
    if selected is not None:
        try:
            out = selected.render_view(
                percepts, mode=mode, prev_standing=prev_standing,
                prev_described=prev_described, full_render=full_render)
            # The tolerance below covered only a RAISE. An adapter that
            # returned successfully with a dict, a tuple or the bare text --
            # the shapes a pack gets wrong first -- went straight through,
            # and the caller read `.text`, `.standing_keys` and `.described`
            # off it one stage later, outside every guard. Checked here so a
            # malformed return costs the same as a malformed raise.
            if not isinstance(out, RenderedView):
                raise TypeError(
                    f"language renderer returned {type(out).__name__}, "
                    "not RenderedView")
            return _stamp(out)
        except Exception:
            # A view is what an observer perceives at all. A malformed pack
            # must cost wording, never the whole beat, so fall through to the
            # in-module reference renderer rather than killing the turn.
            logger.exception("language renderer failed; using English wording")
    return _stamp(_render_view_english(
        percepts, mode=mode, prev_standing=prev_standing,
        prev_described=prev_described, full_render=full_render))
