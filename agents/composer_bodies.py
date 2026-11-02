"""Every percept about a body: poses and their referents, extra parts,
appearance, tells and demeanor, the observer's own state, ears, contacts,
bare regions, and the non-awake residue.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from world.spatial import (
    _clean_pose,
    _entities_named,
    _entity_named,
    _anchor_room_of,
    _is_body_entity,
    contact_thing_label,
    effective_anchors,
    entity_arc,
    proximity_rel,
    room_of,
    same_subject,
    visual_level_between,
)
from .common import _self_second_person

from agents.composer_common import (
    Percept,
    _ENGLISH_COMPOSITOR,
    _lower_lead,
    _noun_phrase,
    _pack_words,
    _sense_graded,
    _strip_sentence_ends,
    _t,
    body_key,
    standing_key,
)
from agents.composer_person import (
    _mine_if_it_matters,
    _pose_owner_second_person,
    _self_first_person,
)


_COUNT_NAMES = {
    int(number): str(word)
    for number, word in _ENGLISH_COMPOSITOR["count_names"].items()
}


def body_part_percepts(rows):
    """Authored extra body parts -- tails, wings, horns -- already gated.

    Input is `observer_body_regions`' `part_data`: the parts this observer
    may see, with the same vantage/containment/garment decision the phrase
    list was built from. Structured rather than pre-phrased, because the
    composer renders to a reader now and "tail x6 — emerge from the back of
    the waist" is payload grammar.
    """
    out = []
    for label, part in rows or []:
        kind = " ".join(str(part.get("kind") or "").split())
        if not kind:
            continue
        try:
            count = max(1, int(part.get("count", 1)))
        except (TypeError, ValueError):
            count = 1
        out.append(Percept(
            kind="body_part", channel="sight",
            source_label=str(label or _t("someone")),
            data={"part": kind, "count": count,
                  "at": str(part.get("at") or "torso"),
                  "aspect": str(part.get("aspect") or "back"),
                  "description": " ".join(
                      str(part.get("description") or "").split()),
                  "tucked": bool(part.get("tucked")),
                  "directed_at_self": str(label) == "you"},
            salience=0.3,
            dedupe_key=standing_key(
                "part", (body_key(label), kind, part.get("at")),
                (count, part.get("aspect"), part.get("description"),
                 part.get("tucked"))),
        ))
    return out


def _names_a_body(scene, text, co_present):
    """Does this referent name a BODY, asked structurally rather than by word.

    `entities[*].kind` is free text a model writes: across the stories on disk
    it holds 'person', 'character', 'agent', 'npc', 'actor', 'kitsune',
    'succubus' and 'dalek war machine' beside 'object' and 'fixture', so any
    allowlist of person-kinds is really a list of the stories played so far
    and is wrong for the next one. The signals used instead hold whatever the
    story calls its people: a body is something the observer is co-present
    with, something the scene gives a POSE, or something the enclosure code
    already recognises as a body.

    A POSE IS NOT EVIDENCE OF A BODY, though, and that signal alone was
    minting people. `scene.poses` is keyed by whatever the Director gave a
    posture to, and a Director legitimately gives one to a thing: a survey
    staff planted upright, a canteen slung, a notebook pocketed. Each of
    those became "someone" in the composed view of a story whose cast was one
    woman alone in a dead town -- fourteen of twenty beats, three of them in
    the same paragraph -- while the mallet, the one possession that never
    received a posture, rendered correctly by its own name in the same view.
    So the scene is asked to vouch for a THING first, exactly as
    `contact_sensation`'s docstring tells a caller holding an identity floor
    to, and as `narration._partner_label` already does. That answer is
    affirmative in both directions and outranks the person-shaped default;
    silence leaves the default standing, which is what keeps a body the
    observer cannot place from being named.
    """
    for body in co_present or []:
        if same_subject(scene, text, str(body.get("name") or "")):
            return True
    if contact_thing_label(scene, text):
        return False
    for posed in (scene.get("poses") or {}):
        if same_subject(scene, text, str(posed or "")):
            return True
    primary, aliased = _entities_named(scene, text)
    return any(_is_body_entity(scene, eid, entity)
               for eid, entity in (*primary, *aliased))


def _part_qualified(scene, text):
    """Split a part-qualified referent `<owner>.<part>` into its two halves.

    A support or relation referent may name a PART OF a body or entity rather
    than the whole of it -- `Mirelle Sulmirath.tongue`, `kestrel.hand`. The
    dotted token is the engine's compound register for that, and it must never
    reach the page: composed today, a pose read "lying on Mirelle
    Sulmirath.tongue on you" with the dot token verbatim, while its id-spelled
    twin `mirelle_sulmirath.hands` hit the id-shaped drop and was lost whole,
    taking owner and part with it.

    The OWNER half decides whether the referent may be named at all, so this
    only reports a split when the owner is a spelling the scene knows. A
    spelling the scene knows AS A WHOLE is never split, which is what keeps a
    body or entity whose own name carries a period intact. A dot in free text
    -- "St. Ives", a sentence end -- resolves to nothing and is left exactly
    as written.

    Returns `(owner, part)`, or `(None, "")` for anything that is not one.
    """
    text = str(text or "").strip()
    if "." not in text:
        return None, ""

    def _known(name):
        name = str(name or "").strip()
        if not name:
            return False
        if _entity_named(scene, name):
            return True
        return any(
            same_subject(scene, name, str(key or ""))
            for table in ("positions", "poses", "attire")
            for key in ((scene or {}).get(table) or {}))

    if _known(text):
        return None, ""
    owner, _dot, part = text.partition(".")
    owner, part = owner.strip(), part.strip().replace("_", " ")
    if not owner or not part or not _known(owner):
        return None, ""
    return owner, part


#: An engine identifier as it appears inside authored prose: a run of word
#: characters carrying an underscore. English prose has none, so the shape is
#: decidable rather than guessed -- this is a closed vocabulary the ENGINE
#: owns (room uids, entity ids, anchor ids all mint this way), not an attempt
#: to anticipate how a sentence will be phrased.
_ID_SHAPED = re.compile(r"(?<![\w])[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+(?![\w])")


def _display_for_id(scene, token):
    """The story's own name for an engine id, or "" when it names nothing.

    Rooms, then entities, then anchors -- the three ledgers whose keys are
    minted with underscores and therefore the three that can leak one.
    """
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(token)
    if isinstance(room, dict) and str(room.get("name") or "").strip():
        return str(room["name"]).strip()
    named = str((_entity_named(scene, token) or {}).get("name") or "").strip()
    if named:
        return named
    for room in rooms.values():
        anchors = room.get("anchors") if isinstance(room, dict) else None
        if isinstance(anchors, dict) and isinstance(anchors.get(token), dict):
            desc = str(anchors[token].get("desc") or "").strip()
            if desc:
                return desc
    return ""


def _no_engine_ids(scene, text):
    """Authored prose with every engine identifier taken out of it.

    THE CLASS: an id is a handle the engine holds, never a word of the story.
    `_pose_referent` already refuses one where a REFERENT is resolved (step
    5), and the same string walked straight onto the page through the free
    prose beside it -- run 2026-09-05C `solitude` turn 1 (PS2): "poised at
    the brow with one foot on the top step down toward upper_terrace_rim,
    survey staff planted in a rut."

    An id that names a record renders as that record's own name, which
    discloses nothing the id did not already carry -- the reader could read
    `upper_terrace_rim` perfectly well.

    An id that names NOTHING takes its whole clause with it, not just the
    token: a clause reaching for a record the scene does not hold says
    nothing, and excising the word alone leaves the reach behind it ("one
    foot on the step down toward."). The unit is the clause the author's own
    punctuation marks, so no list of prepositions has to be right -- and
    where that is the only clause the field simply does not become a
    percept, which is the subtraction the rest of this module makes
    everywhere else.
    """
    text = str(text or "").strip()
    if not text or "_" not in text:
        return text

    def swap(match):
        # \x00 marks a token that named nothing; the clause holding it goes.
        return _display_for_id(scene, match.group(0)) or "\x00"
    parts = re.split(r"\s*([,;])\s*", text)
    kept = []                       # [(clause, the separator that followed)]
    for index in range(0, len(parts), 2):
        clause = _ID_SHAPED.sub(swap, parts[index]).strip()
        if not clause or "\x00" in clause:
            continue
        kept.append((clause,
                     parts[index + 1] if index + 1 < len(parts) else ""))
    out = "".join(
        clause + ((separator or ",") + " " if position < len(kept) - 1 else "")
        for position, (clause, separator) in enumerate(kept))
    return " ".join(out.split())


def _pose_referent(scene, observer_name, display_map, co_present, other,
                   *, is_self=False):
    """What a pose is arranged against, rendered as the KIND OF THING it is.

    Returns the text to render, or None to drop this referent -- and, where
    the caller is handling `relative_to`, its relation along with it.

    A POSE REFERENT IS NOT NECESSARILY A BODY. A body may be arranged against
    the observer, against another body, against a scene entity (furniture, a
    device, a fixture), or against a bare noun the Director wrote that names
    no record at all, and only the first two can be a PERSON. Every referent
    used to be resolved through `display_map` -- which holds co-present BODIES
    and nothing else -- with each miss taking the person-shaped default
    "someone". A desk, a bolted chair and a reality anchor were therefore each
    delivered as an unidentified person: "seated upright on desk at someone",
    "restrained in someone", "standing beside someone". Measured in chat 84,
    where all four poses in the scene did it in the same beat, and the last of
    them put a third body into a room the observer could see held exactly two
    guards.

    Order of certainty, and every miss SUBTRACTS:

      1. the observer -> "you"
      2. a body this observer has ALREADY BEEN GIVEN -> that body's own
         display label. This is the only place a person label may come from.
      3. any other body -> DROPPED, unless this is the observer's OWN pose.
         `observer_display_map` covers every co-present body, so a body
         absent from it is one this observer was not shown, and naming it in
         somebody else's pose would hand them a presence perception withheld.
         Their own pose is the exception and not a leak: a body you are
         arranged against is a body you are in CONTACT with, and contact is
         delivered by interoception whether or not you can see who it is.
         "pinned beneath someone" is the honest rendering of exactly that,
         and the identity stays unearned.
      4. a scene entity -> its own name, through the pack's own template so a
         language that takes no article does not get one.
      5. a room's own FIXTURE -> the noun its anchor id was minted from,
         through the same splice as a bare noun ("the access door"). A
         station, a pose and a contact all name fixtures by anchor id, and
         the id is the Director's own noun with underscores in it; the desc
         beside it is a whole authored sentence and reads wrong as a
         possessive ("You feel A heavy steel door seated in a reinforced
         frame's lever handle"). Resolved through `_anchor_room_of`, the
         one resolver the contact ledger already trusts for the question
         "which room is this fixture in". Measured on the descent copy
         (chat 117, beats 115-117): "You feel something's steel plate
         against your right palm", "something's lever handle" -- three beats
         of a player touching a door the room declared, delivered as an
         unnameable thing because step 6 below dropped the id first.
      6. an id-shaped token matching no record -> DROPPED. `anchor_device`
         (the entity's id is `scranton_anchor`) names nothing, and putting it
         on the page shows the reader engine plumbing.
      7. anything else -> the bare noun as written. It matches no record in
         the scene, so it can disclose nothing the Director's own phrasing
         did not already carry.
    """
    text = str(other or "").strip()
    if not text:
        return None
    # A part is a referent like any other; only its OWNER decides whether it
    # may be named, so the part resolves through the owner by this same order
    # of certainty and can never outrank it.
    owner, part = _part_qualified(scene, text)
    if owner is not None:
        whose = _pose_referent(scene, observer_name, display_map, co_present,
                               owner, is_self=is_self)
        if not whose:
            # The firewall answer at step 3 is INHERITED, not re-decided: a
            # part of a body this observer was not shown drops exactly as the
            # body does.
            return None
        if whose == "you":
            return _t("pose_part_self", part=part)
        return _t("pose_part_other", label=whose, part=part)
    if same_subject(scene, text, observer_name):
        return "you"
    for name, label in (display_map or {}).items():
        if same_subject(scene, text, str(name or "")):
            return label
    if _names_a_body(scene, text, co_present):
        # In the story's own word: the Japanese adapter translates only the
        # self label, so a literal "someone" reached a Japanese page (audit
        # agents_composer F9, 2026-11-01).
        return _t("someone") if is_self else None
    entity = _entity_named(scene, text)
    named = str((entity or {}).get("name") or "").strip()
    if named:
        # An entity may be NAMED with its determiner -- "The TARDIS", "the
        # Nostromo" -- and the pack's template supplies one of its own, so
        # the page read "facing the The TARDIS" (chat 114 on a copy,
        # 2026-09-05, turn 2). The same determiner list the bare-noun path
        # below consults decides it: a name that already opens with one is
        # rendered as it is written.
        first = named.split()[0].casefold().strip(",.")
        if first in _pack_words("pose_bare_determiners"):
            return named
        return _t("pose_entity", name=named)
    _fixture_room = _anchor_room_of(scene, text, prefer=room_of(scene, observer_name))
    if _fixture_room:
        # AN EDGE'S DOORWAY IS NOT A MINTED NOUN. Its id is `door:<room id>`
        # (`spatial_geometry.door_anchor_id`), and splicing it rendered
        # "against the door:mill race" into seven views and five memories of
        # one run (playerless Aldermill round 4, 2026-09-23). The implicit
        # anchor carries its own description -- the edge's name, or what the
        # boundary looks like -- and that is what the page says.
        if text.casefold().startswith("door:"):
            record = (effective_anchors(scene, _fixture_room) or {}).get(text)
            desc = str((record or {}).get("desc") or "").strip() \
                if isinstance(record, dict) else ""
            return desc or None
        return _noun_phrase(text.replace("_", " "))
    if "_" in text and not text.strip().count(" "):
        return None
    # A bare noun the Director wrote. It still reads better with the article
    # the pack supplies -- "at desk" is the awkwardness this whole repair was
    # reported for -- but only where it does not already carry a determiner
    # of its own ("the far wall", "her shoulder") and is not a proper name,
    # which a capital marks and which "the Marcus" would ruin. The determiner
    # list is language DATA and lives in the compositor card, empty for a
    # language that takes no article at all. One rule, shared with every
    # other place an authored description is spliced into a sentence.
    return _noun_phrase(text)


def _same_referent(scene, a, b):
    """Do two pose fields name one thing -- by spelling, or by resolving to
    the same scene entity."""
    a, b = str(a or "").strip(), str(b or "").strip()
    if not a or not b:
        return False
    # Two pose fields naming one body at two granularities -- the body in
    # `relative_to`, a place ON it in `support` -- are still ONE referent.
    # Comparing whole strings let both render, which is where the second
    # preposition came from ("on <body>.<part> on you"). Granularity is not
    # identity.
    a = _part_qualified(scene, a)[0] or a
    b = _part_qualified(scene, b)[0] or b
    if a.casefold() == b.casefold():
        return True
    ea, eb = _entity_named(scene, a), _entity_named(scene, b)
    na = str((ea or {}).get("name") or "").strip().casefold()
    nb = str((eb or {}).get("name") or "").strip().casefold()
    return bool(na) and na == nb


def pose_percepts(scene, observer_name, co_present, display_map,
                  senses=None, *, self_forms=(), self_pronouns=None,
                  scrub=None):
    """How bodies are arranged: posture, what holds them up, who they are
    against, what pins them.

    `scrub` is the observer's identity floor for the pose's free text
    (posture, constraint, detail), handed in by perception so this stays a
    leaf: a pose is written once, by the Director, in true names, and served
    to every mind that sees the body -- its owner included. Without it the
    detail "Kneeling over Hinami ..., left palm resting on the warmth of
    Hinami's lower ribs" read to Vexara, who had never learned the name,
    beside the structured half of the same line that called her "the young
    woman" (the owner's chat 120, every beat, under both contracts; the
    tripwire repaired it after the fact).

    Poses were already Director-declared (`state_diff.poses`), already
    normalized (`normalize_scene_poses`) and already living in the scene
    blob beside stations and facing. The only missing hop was this one --
    nothing composed them into a view, so 75 turns of authored arrangement
    reached no mind at all.

    THE GRADE FOLLOWS THE SIGHT, because posture is the one body fact a
    silhouette genuinely does carry: you can see that someone is kneeling
    across a dim room without seeing anything else about them. So a body at
    `shapes` yields posture and nothing else -- no support, no relation, no
    constraint, no authored detail -- and a body at `full` yields the lot.
    Subtractive either way: the fields simply do not become percepts.

    The observer's OWN pose is interoception and always arrives. A body in
    the rear arc does not, matching `presence_percepts` -- you do not see
    how someone behind you is sitting.
    """
    out = []
    for name, raw in ((scene or {}).get("poses") or {}).items():
        pose = _clean_pose(raw)
        if pose is None:
            continue
        is_self = same_subject(scene, name, observer_name)
        if is_self:
            level, label = "full", "you"
        else:
            if not any(same_subject(scene, name, body.get("name"))
                       for body in co_present or []):
                continue
            # A POSE NEEDS A WITHIN-ROOM TIER. Caught by a pose-bearing
            # drive scenario, not by the corpus: Kai stood in the yard, Reya
            # knelt in the forge behind a closed door, and his view read
            # "Reya is kneeling on the anvil block". Presence had already
            # declined to mention her -- `proximity_rel` answers None across
            # rooms -- while this gate checked only sight and arc, so a body
            # he was not even told was there arrived with her posture, her
            # support and her breathing.
            #
            # It was written as "a pose is never more reachable than a
            # presence", borrowing `presence_percepts`' gate. That is no
            # longer what either function does. Presence has since grown a
            # cross-room branch: where `proximity_rel` is None it does not
            # decline, it falls back to `tier="beyond"` plus the room label,
            # so an interviewer watching through observation glass is told
            # about the woman in the cell. Pose still declines there, and so
            # presence now outruns pose rather than the other way round.
            #
            # The subtraction is defensible on its own terms, which is why it
            # stays: a pose is rendered AGAINST the furniture and the bodies
            # around it ("kneeling on the anvil block", "leaning against
            # her"), and those referents belong to a room the observer is
            # not in. Seeing that someone across a barrier is kneeling is
            # not seeing what they are kneeling on. State it that way rather
            # than as a rule about presence, so the next body percept added
            # here inherits the reason and not a comparison that has flipped.
            if proximity_rel(scene, observer_name, name) is None:
                continue
            level = _sense_graded(
                visual_level_between(scene, observer_name, name, senses),
                "sight", senses)
            if level == "none":
                continue
            if entity_arc(scene, observer_name, name) == "rear":
                continue
            label = display_map.get(name) or _t("someone")
        # Every exact handle for the receiving observer becomes second person
        # before it enters the IR.  This applies to OTHER bodies' details too:
        # ``Mara ... squeezing Rhea's hand`` in Rhea's own view must
        # read ``... squeezing your hand``.
        # AN ENGINE ID IS NOT A WORD OF THE STORY, in the free prose beside a
        # referent as much as in the referent itself (`_no_engine_ids`; PS2).
        pose = {f: (_no_engine_ids(scene, pose[f])
                    if f in _POSE_FREE_TEXT else pose[f])
                for f in pose}
        # WHAT THE ARRANGEMENT IS, before this observer's words for it: the
        # ledger key is cut from this (below), never from the scrubbed and
        # relabelled fields the sentence is built from.
        authored = dict(pose)
        if scrub is not None:
            pose = {f: (scrub(pose[f]) if f in _POSE_FREE_TEXT and pose[f]
                        else pose[f])
                    for f in pose}
        data = {"posture": _self_second_person(
            pose["posture"], self_forms) if self_forms else pose["posture"]}
        # The observer's own first person of the same words, for its memory
        # (`_said_as_mine`): written while the third person still says which
        # role each of its names and pronouns had.
        mine = {"posture": _self_first_person(pose["posture"], self_forms)
                if self_forms else pose["posture"]}
        if level == "full":
            for f in ("support", "relation", "constraint", "detail"):
                data[f] = (_self_second_person(pose[f], self_forms)
                           if self_forms else pose[f])
                mine[f] = (_self_first_person(pose[f], self_forms)
                           if self_forms else pose[f])
            if is_self and self_pronouns:
                other_forms = []
                for body in co_present or []:
                    other = str(body.get("name") or "")
                    if not other or same_subject(scene, other, observer_name):
                        continue
                    other_forms.extend([
                        other, *(body.get("aliases") or []),
                        (display_map or {}).get(other),
                    ])
                for f in ("posture", "constraint", "detail"):
                    data[f] = _pose_owner_second_person(
                        data.get(f), self_pronouns, other_forms)
                    mine[f] = _pose_owner_second_person(
                        mine.get(f), self_pronouns, other_forms,
                        person="first")
            # Support is a referent too, and took the same raw string onto
            # the page: "on chair_interview" is an entity id being read to
            # the player. Both fields go through the same resolver.
            data["support"] = _pose_referent(
                scene, observer_name, display_map, co_present,
                pose["support"], is_self=is_self) or ""
            other = str(pose["relative_to"] or "").strip()
            if other:
                ref = _pose_referent(
                    scene, observer_name, display_map, co_present, other,
                    is_self=is_self)
                if ref and _same_referent(scene, other, pose["support"]):
                    # ONE THING, NAMED TWICE. The body specialist fills
                    # `support` and `relative_to` with the same referent --
                    # three of chat 84's four poses did -- which read as "on
                    # desk at desk" the moment the referent stopped being a
                    # person. Keep the RELATION, which is the more specific
                    # of the two ("restrained in" against a bare "on"), and
                    # let it carry the referent by itself.
                    if str(data.get("relation") or "").strip():
                        # Relation wins the preposition, the PART wins the
                        # noun. The rule above keeps the relation because it
                        # is the more specific of two identical referents; a
                        # part-qualified support is the more specific NOUN,
                        # because it says where on the body the arrangement
                        # bears, which a bare owner cannot.
                        precise = ref
                        if (_part_qualified(scene, pose["support"])[0]
                                and not _part_qualified(scene, other)[0]):
                            precise = data["support"]
                        data["support"] = ""
                        data["relative_to"] = precise
                    else:
                        data["support"] = ref
                elif ref:
                    data["relative_to"] = ref
        if not any(data.values()):
            continue
        firsts = {f + "_mine": m for f in ("posture", "relation",
                                           "constraint", "detail")
                  if (m := _mine_if_it_matters(mine.get(f), data.get(f)))}
        out.append(Percept(
            kind="pose",
            channel="interoception" if is_self else "sight",
            source_label=label,
            fidelity="full" if level == "full" else "degraded",
            data={**data, **firsts, "directed_at_self": is_self},
            salience=0.3,
            # KEYED ON WHAT THE ARRANGEMENT IS, NOT ON WHAT THIS OBSERVER
            # CALLS ITS PARTS. `support` and `relative_to` render through the
            # observer's display map and the free text through its identity
            # scrub, so learning a name re-keyed an unchanged pose: Xan
            # leaning against "the woman in grey" and against "Yul" were two
            # arrangements, and the player view led with "The tall man is
            # leaning against Yul." as a numbered change (audit
            # agents_composer F7, 2026-11-01 -- the 1.70 class `scent_percepts`
            # left long ago). The authored fields, hashed, and only those the
            # sight grade delivered (a silhouette's posture alone). A new tag,
            # so a ledger keyed the old way reads as first sight -- the
            # background, never a claim that anything moved.
            dedupe_key=standing_key(
                "arrangement", (body_key(name),),
                tuple(str(authored.get(f) or "")
                      if f == "posture" or level == "full" else ""
                      for f in (_OWN_POSE_KEY_FIELDS if is_self
                                else _POSE_RENDER_FIELDS))),
        ))
    return out


_POSE_RENDER_FIELDS = ("posture", "support", "relative_to", "relation",
                       "constraint", "detail")

#: The fields that CONSTITUTE the observer's own arrangement, for the dedupe
#: key alone. `detail` is left out for the same reason
#: `world.spatial_geometry._POSE_ARRANGEMENT_FIELDS` leaves it out: "it
#: qualifies an arrangement, it does not constitute one." Measured (chat
#: 117, 2026-09-07): the body hand re-words a player's `detail` nearly every
#: beat -- 67 of 89 consecutive pairs differed -- and with `detail` in the
#: key each re-wording hashed as a CHANGED pose, led the beat as a numbered
#: obligation the narrator sheet says must reach the page, and closed 51% of
#: those beats with the player being told his own posture back. Other
#: bodies keep the six-field key: THEIR detail is a seen fact ("fingers
#: hooked into his belt") and a real change.
_OWN_POSE_KEY_FIELDS = ("posture", "support", "relative_to", "relation",
                        "constraint")

#: The pose fields that are authored PROSE rather than a referent. `support`
#: and `relative_to` are referents and go through `_pose_referent`, which
#: already refuses an id (step 5); these three reach the page as written.
_POSE_FREE_TEXT = ("posture", "constraint", "detail")


def appearance_percept(source_name, label, description, *, force=False,
                       delta="", reearn=False, held=False):
    """The FULL authored appearance -- discovery/structural-change data, first
    mention only (the render ledger gates re-emission; ``force=True`` marks a
    structural change this beat, which re-earns the description).

    ``delta`` is what a change LOOKS LIKE from outside, and when it is
    present the renderer uses it INSTEAD of the full description. A garment
    coming off is an event; re-issuing the whole wardrobe is a ledger. The
    old behaviour put "wearing Ceremonial kimono, Nagajuban, Ornate gold
    obi, Zori, Tabi, bare at the head, hands" on the page because a change
    of any one item re-earned every item, and the narrator was then asked to
    render an inventory as something that happened. The full description
    stays available in the standing half of the view, where first-mention
    and dedupe already govern it.
    ``reearn=True`` re-delivers the description past the first-mention
    ledger WITHOUT claiming anything happened. The two are different jobs
    and `force` was doing both: a body you are meeting again is not a body
    that CHANGED, so its description is standing state that has become
    sayable again rather than an event the narrator owes the page. Without
    it, first-mention tracking is permanent -- a stranger described once on
    beat 3 is never described again in a two-hundred-beat story, however
    many times they leave and come back.

    ``held=True`` says THIS observer held the body at full sight last beat
    (perception's `saw_before`), which is what makes a `force` a change FOR
    THEM: the observation projection files a moved body under the changes
    noticed only then (`observations_from_render`).

    `description` must already be identity-safe for this observer
    (name-stripped when the observer does not recognize the body). The
    canonical name is folded into an opaque `body_key` for the ledger; it
    never rides the percept."""
    return Percept(
        kind="appearance", channel="sight", source_label=label,
        data={"source_key": body_key(source_name),
              "description": description, "force": bool(force),
              **({"reearn": True} if reearn else {}),
              **({"held": True} if held else {}),
              **({"delta": str(delta)} if str(delta or "").strip() else {})},
        salience=0.5,
        dedupe_key=standing_key("described", (body_key(source_name),),
                                (description,)),
    )


def cue_percept(source_name, label, cue, *, order_key, can_see=True):
    """One physical tell that reached this observer -- a glance, a grip, a
    catch in the voice the character did not declare as an action (D1;
    Wood/Stanislavski: the actor's body). `cue` is the OBSERVABLE text
    alone: `_delivered_manifest` has already decided, per observer and per
    channel, which tells land, and neither the tell's `because` nor its
    `betrays` ever reaches a percept -- meaning stays with the mind that
    has it. Observations derive from the render, so a reader downstream
    cannot recover more than the page says. Review A36 measured the payload
    computed for 101 beats and read by nothing."""
    text = _strip_sentence_ends(cue)
    if not text or not label:
        return None
    return Percept(
        kind="cue", channel="sight" if can_see else "hearing",
        source_label=label, order_key=order_key,
        data={"cue": text, "body": body_key(source_name)},
        salience=0.55,
        dedupe_key=standing_key("cue", (body_key(source_name),), (text,)),
    )


def demeanor_percept(source_name, label, demeanor):
    """A body's surface demeanor as STANDING state: how it carries itself
    this beat, rendered while it holds and again only when it changes --
    the standing ledger's ordinary verdicts, so a calm that lasts ten beats
    costs one sentence (D1)."""
    text = _lower_lead(_strip_sentence_ends(demeanor))
    if not text or not label:
        return None
    return Percept(
        kind="demeanor", channel="sight", source_label=label,
        data={"demeanor": text, "body": body_key(source_name)},
        salience=0.45,
        dedupe_key=standing_key("demeanor", (body_key(source_name),), (text,)),
    )


def body_state_percept(entity_state):
    state = {k: entity_state.get(k) for k in ("posture", "activity", "held_items")
             if entity_state.get(k)}
    if not state:
        return None
    return Percept(
        kind="body_state", channel="interoception", source_label="you",
        data=state, salience=0.3,
        dedupe_key=standing_key(
            "state", ("self",),
            (state.get("posture"), state.get("activity"),
             ",".join(state.get("held_items") or []))),
    )


#: What a body knows of its own ears (DESIGN_SOUND_FIELD § 13): `ringing`
#: after a blast, while the shift is at least `spatial_listener.RINGING_DB`;
#: `recovered`, said once to an ear that was ringing the beat before.
EAR_STATES = ("ringing", "recovered")


def ear_percepts(shift_db, prev_standing=frozenset(), *, fresh=False):
    """A BODY KNOWS ITS OWN RINGING EARS (DESIGN_SOUND_FIELD § 13). After a
    blast past `spatial_listener.BLAST_DB` the ear is dulled and rings; the
    listener has that as interoception -- their own body's state, never
    another's (nobody else knows it unless they see it, and nothing here
    reaches any view but this body's own). `fresh` is a blast that reached
    them THIS beat, before the commit has written the shift; `shift_db` is
    the shift the scene holds.

    Standing, keyed by its state, so it is news when it starts and furniture
    while it lasts; and its FADING is said once, to an ear whose own ledger
    held the ringing (`prev_standing`), which is the class every steady
    sound's stopping is told by (`sound_ceased_percept`)."""
    from world.spatial import RINGING_DB
    ringing = standing_key("ears", ("self",), ("ringing",))
    try:
        shift = float(shift_db or 0.0)
    except (TypeError, ValueError):
        shift = 0.0
    if fresh or shift >= RINGING_DB:
        return [Percept(
            kind="sensation", channel="interoception", source_label="you",
            data={"ears": "ringing", "directed_at_self": True},
            salience=0.55, dedupe_key=ringing)]
    if ringing in (prev_standing or ()):
        return [Percept(
            kind="sensation", channel="interoception", source_label="you",
            data={"ears": "recovered", "directed_at_self": True},
            salience=0.4,
            dedupe_key=standing_key("ears", ("self",), ("recovered",)))]
    return []


def contact_percepts(contacts_with_sensation):
    """Standing contact sensations. Input: [(contact_record, sensation_clause)]
    where the clause came from `spatial.contact_sensation(you=observer)` --
    empty for a contact the observer is only watching, so a non-party
    contributes nothing here by construction."""
    out = []
    for contact, clause in contacts_with_sensation or []:
        clause = str(clause or "").strip()
        if not clause:
            continue
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True},
            salience=0.45,
            dedupe_key=standing_key(
                "contact",
                (contact.get("actor"), contact.get("actor_part"),
                 contact.get("target"), contact.get("target_part")),
                (contact.get("manner"),)),
        ))
    return out


def contact_action_percepts(actions_with_sensation):
    """Standing contact-effect sensations as ``[(record, safe_clause)]``.

    Admission and observer-side phrasing happen upstream, exactly like
    ``contact_percepts``. The composer receives no scene and cannot widen the
    identity or tactile channel.
    """
    out = []
    for entry in actions_with_sensation or []:
        if not isinstance(entry, tuple) or len(entry) != 2:
            continue
        record, clause = entry
        if not isinstance(record, dict):
            continue
        clause = str(clause or "").strip()
        if not clause:
            continue
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True},
            salience=0.4,
            dedupe_key=standing_key(
                "contact_action",
                (record.get("contact_id"), record.get("action"),
                 record.get("actor")),
                (record.get("action_id"), record.get("intensity"),
                 record.get("rhythm"))),
        ))
    return out


def body_region_percepts(bare_details):
    """Authored bare-surface anatomy, already observer-gated upstream
    (`observer_body_regions` + `_bare_body_details`). Input:
    [(body_label, place, detail)] where body_label is 'you' or an
    observer-safe label."""
    out = []
    for body_label, place, detail in bare_details or []:
        out.append(Percept(
            kind="body_region", channel="sight",
            source_label=str(body_label or _t("someone")),
            data={"place": place, "detail": detail},
            salience=0.3,
            dedupe_key=standing_key(
                "region", (body_key(body_label), place), (detail,)),
        ))
    return out


def residue_percepts(level, *, targeted=False, loud_event=False, pain=False,
                     woke=""):
    """A non-awake mind gets the residue and nothing else -- and a sleeper a
    sound woke this beat gets only what woke them (`woke`, one of
    `spatial_listener.WAKING_SOUNDS`; DESIGN_SOUND_FIELD § 13)."""
    data = {"level": level, "targeted": bool(targeted),
            "loud_event": bool(loud_event), "pain": bool(pain),
            "directed_at_self": True}
    if woke:
        data["woke"] = str(woke)
    return [Percept(
        kind="residue", channel="interoception", source_label="you",
        fidelity="trace",
        data=data,
        salience=0.2 if not woke else 0.6,
        dedupe_key=standing_key("residue", (level,),
                                (targeted, loud_event, pain)
                                + ((str(woke),) if woke else ())),
    )]
