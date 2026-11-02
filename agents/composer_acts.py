"""An act, a substance transfer and a crossing as one observer receives them:
concealment, the rear arc's heard movement, the sight grade, suddenness and
the first-person copy for memory.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from core.pipeline_context import note_step_decision
from world.spatial import (
    entity_arc,
    movement_heard_at_ear,
    room_of,
    same_subject,
    sound_bearing,
)
from .common import _self_second_person

from agents.composer_common import Percept, _ling, _short_hash
from agents.composer_person import (
    _action_target_second_person,
    _mine_if_it_matters,
    _self_first_person,
)
from agents.composer_figures import _visible_room_label
from agents.composer_speech import concealed_from_observer




def _surface_suddenness(surface):
    """How abruptly an act arrives, from its leading verb.

    Keyed on `split()[0]`, which is the whole clause in a language that does
    not space its words -- so `Percept.suddenness` was pinned at 0.1 for every
    Japanese act, flattening a salience signal the observer receives and
    killing the "a sudden chain leads" discourse rule outright.
    """
    text = str(surface or "").casefold().strip()
    if not text:
        return 0.1
    cues = _ling("_SUDDEN_VERBS")
    words = text.split()
    first = re.sub(r"[^\w]", "", words[0]).rstrip("s")
    if first in cues:
        return 0.6
    # No leading token to test: fall back to whether the clause OPENS with a
    # cue, which is the same question asked without assuming a space.
    if len(words) == 1 and any(text.startswith(str(cue)) for cue in cues):
        return 0.6
    return 0.1


def _sound_bearing_phrase(scene, observer, source) -> str:
    """Where a heard movement came from, in the observer's own frame, or "".

    `spatial.sound_bearing` answers with the egocentric sector and never
    guesses; its own contract is that the record carries no room id and no
    room name, so a bearing discloses nothing a body's ears did not.
    """
    try:
        rec = sound_bearing(scene, observer, source)
    except Exception:
        return ""
    if not isinstance(rec, dict):
        return ""
    return str(rec.get("phrase") or rec.get("sector") or "").strip()


def _peel_own_name(surface, actor_name):
    """An act's surface with its actor's own leading name words removed.

    Whoever renders the act names the actor -- by the observer's label for
    it -- so a surface that opens with the actor's own name carries a second
    subject, and for a stranger that subject is a name no channel delivered.
    The renderer peels only the words of the LABEL, which for a stranger is
    a descriptor, so "Godidric plants his boots" read as an independent
    sentence and reached a mind that had never learned the name (playerless
    Aldermill round 3, 2026-09-23, t13 and t23: a charter voice writes its
    act about itself in the third person). A possessive is not peeled -- the
    predicate after it has its own subject ("Godidric's hands grip") -- and a
    surface that is nothing but the name is left alone."""
    if not surface or not actor_name:
        return surface
    own = {w.casefold() for w in str(actor_name).split() if w}
    words = surface.split()
    peeled = 0
    while peeled < len(words):
        word = words[peeled].strip(".,;:").casefold()
        if word not in own:
            break
        peeled += 1
    if not peeled or peeled == len(words):
        return surface
    return " ".join(words[peeled:])


def act_percept(scene, event, observer_name, actor_name, rel, *,
                display, can_see, self_forms=None, self_pronouns=None,
                other_forms=None,
                order_key=0,
                observer_id=None, surface=None, sight="full",
                sound=None, gait=None, own_sound=False):
    """Admit one action element's observable surface for one observer, or
    None. Gates: concealment, rear arc, sight (an action is visible or it is
    nothing -- a touch-only source contributes sensation percepts instead,
    never an event surface).

    `sight` is the GRADE, not a second boolean: "full" admits the observable
    surface, "shapes" admits a motion percept that names no object and no
    detail, "none" refuses. Every grader upstream already answers in those
    three words and this channel used to spend the answer as true/false --
    live (PC1), a shape-in-a-doorway budget bought "opens a black notebook on
    her knee" through a locked door, in the same beat the dialogue gate
    honoured the same wall.

    What reaches the rear arc is a SOUND, and three arguments say what it
    is: `sound` is the observer's sound field for `scene` (None where the
    room carries no geometry), `gait` the actor's gait where the beat walked
    them (`TREAD_GAITS`; a walk otherwise), and `own_sound` whether the act
    filed a sound event of its own this beat.
    """
    # Each refusal below is recorded with the reason it refused. They all
    # return None, and from outside the four are indistinguishable from "the
    # actor did nothing" -- which is how a body stood exposed inside another
    # for four turns while this function behaved perfectly. No-op when debug
    # capture is off; one ContextVar read on the hot path.
    _who = "%s -> %s" % (actor_name, observer_name)
    if concealed_from_observer(event, observer_name, observer_id):
        note_step_decision("act_percept", _who, "refused",
                           "concealed from this observer")
        return None
    if surface is None:
        from .common import observable_action_text
        surface = observable_action_text(event)
    surface = _peel_own_name(str(surface or "").strip(), actor_name)
    if not surface:
        note_step_decision("act_percept", _who, "refused",
                           "no observable surface -- a mental beat")
        return None                       # a mental beat is imperceptible
    if entity_arc(scene, observer_name, actor_name) == "rear":
        # WHAT IS BEHIND YOU IS NOT SEEN, AND IT IS STILL HEARD. `entity_arc`
        # has always promised exactly this -- "no new visual detail from
        # them ... though sound still carries" -- and nothing carried it,
        # because an act reached an observer on the SIGHT channel alone. So
        # five bodies at one anchor split into the two facing the actor, who
        # got the beat, and three facing away, who acted as if it had not
        # happened (multitude, 2026-09-05, PM5).
        #
        # What crosses is that SOMETHING MOVED, and where -- never who, and
        # never what they were doing. A footstep does not carry an identity
        # and a hand's shape does not carry at all, so the surface is
        # dropped whole and the label with it; `sound_bearing` supplies the
        # observer's own egocentric sector where the geometry supports one
        # and nothing when it does not, and it is firewall-clean by
        # construction (it names no room and no body).
        #
        # ...AND ONLY WHERE ITS SOUND REACHES THE EAR (2026-10-21). An act
        # that filed a sound event of its own is heard AS THAT SOUND -- the
        # beat's sound channel tells it -- and is not told a second time as
        # movement. Any other act sounds no louder than the body's own tread
        # (`movement_heard_at_ear`), graded against the noise at this
        # observer's ear: heard a few paces off in a quiet room, not in a
        # crowd's din. Measured on the tavern probe (2026-10-20, chat 2 idx
        # 3-5): a barman's rag along his own bar, his steps round to a
        # barrel and a woman lifting her cup reached three listeners in a
        # 68 dB taproom as "Something moves ..." seven times in three beats,
        # where a walk's tread arrives at 28-32 dB. Without a field (a room
        # with no geometry) the percept stands as it was -- but for a gait
        # that makes no tread where it walks, which is heard nowhere.
        if own_sound:
            note_step_decision("act_percept", _who, "refused",
                               "actor is in the observer's rear arc, and "
                               "the act filed its own sound -- it is told "
                               "as that sound, not twice")
            return None
        if movement_heard_at_ear(scene, observer_name, sound, actor_name,
                                 gait=gait or "walk") == "none":
            note_step_decision("act_percept", _who, "refused",
                               "actor is in the observer's rear arc, and a "
                               "body's movement makes no sound that carries "
                               "over the noise at the observer's ear")
            return None
        note_step_decision("act_percept", _who, "delivered",
                           "actor is in the observer's rear arc -- heard, "
                           "not seen, and not identified")
        return Percept(
            kind="act", channel="hearing", source_label="",
            fidelity="shapes",
            data={"motion": True, "unseen": True,
                  **({"bearing": _bearing}
                     if (_bearing := _sound_bearing_phrase(
                         scene, observer_name, actor_name)) else {})},
            salience=0.4, suddenness=0.3, order_key=order_key,
            # ONE "SOMETHING MOVES" PER BODY PER BEAT: three unseen acts by
            # one body behind you are one fact, not three lines (Hollin
            # Mill turn 11, 2026-09-15, "Something moves behind you." x3).
            dedupe_key="act-heard:" + _short_hash(actor_name))
    if not can_see or sight == "none":
        note_step_decision("act_percept", _who, "refused",
                           "observer cannot see (sight gate)")
        return None
    if sight == "shapes":
        # A body moving, and nothing about what it is doing. The label is
        # whatever identity the caller already earned -- who this is was
        # decided upstream and is not this grade's question.
        #
        # WHERE it moves is the observer's to have when the body stands in a
        # DIFFERENT room. The unseen sibling above already carries its
        # bearing; this branch carried nothing, so a figure seen through an
        # open doorway arrived as a placeless "moves, too little of it to
        # make out" and the narrator put it in the observer's own room.
        # Measured (chat 151 turns 9-10, 2026-09-21): Gushiga Toriki standing
        # on the Moonlit Beach, rendered as "whatever else is in here with
        # you" inside the TARDIS console room. Naming the room opens no
        # channel -- it is the room the observer is already looking into, and
        # `_visible_room_label` is this module's existing answer for a body
        # seen from another one.
        note_step_decision("act_percept", _who, "delivered",
                           "shapes only -- motion without conduct")
        _act_room = ("" if room_of(scene, actor_name)
                     == room_of(scene, observer_name)
                     else _visible_room_label(scene, actor_name))
        return Percept(
            kind="act", channel="sight", source_label=display,
            fidelity="shapes",
            data={"motion": True,
                  **({"room": _act_room} if _act_room else {})},
            salience=0.5, suddenness=0.2, order_key=order_key,
            dedupe_key="act-shapes:" + _short_hash(
                event.get("event_id") or "", actor_name))
    note_step_decision("act_percept", _who, "delivered", surface[:120])
    targets_self = any(
        same_subject(scene, target, observer_name)
        or str(target or "").strip().casefold() in {
            str(form or "").strip().casefold() for form in self_forms or ()}
        for target in event.get("targets") or ())
    # THE SAME REWRITE INTO THE OBSERVER'S OWN FIRST PERSON, for its memory
    # of the beat (`_said_as_mine`): the third person still says whether the
    # observer's name is the subject of its clause, and the second person
    # does not.
    mine = surface
    if targets_self and self_forms and self_pronouns:
        surface = _action_target_second_person(
            surface, self_forms, self_pronouns, other_forms)
        mine = _action_target_second_person(
            mine, self_forms, self_pronouns, other_forms, owner="my")
    if self_forms:
        surface = _self_second_person(surface, self_forms)
        mine = _self_first_person(mine, self_forms)
    mine = _mine_if_it_matters(mine, surface) if self_forms else ""
    return Percept(
        kind="act", channel="sight", source_label=display,
        data={"surface": surface,
              **({"surface_mine": mine} if mine else {}),
              # THE STRUCTURAL ANSWER FIRST: the event's own typed targets
              # name the observer. The English regex over the rewritten
              # surface was the only test, so a Japanese act on the observer
              # said False where the same English act said True (audit
              # agents_composer F10, 2026-11-01); it stays as the fallback
              # for an act whose targets are not typed.
              "directed_at_self": bool(targets_self or
                  re.search(r"\byou\b|\byour\b", surface, re.I))},
        salience=0.65,
        suddenness=_surface_suddenness(surface),
        order_key=order_key,
        dedupe_key="act:" + _short_hash(
            event.get("event_id") or "", actor_name, surface),
    )


def substance_percept(event, clause, order_key=0):
    """This beat's substance ADD delta, for a party to it. `clause` came from
    `spatial.substance_event_clause(you=observer)` -- empty for anyone who is
    not a party, so admission is inherited from the clause builder."""
    clause = str(clause or "").strip()
    if not clause:
        return None
    return Percept(
        kind="substance", channel="touch", source_label="you",
        data={"clause": clause, "directed_at_self": True},
        salience=0.55,
        order_key=order_key,
        dedupe_key="substance:" + _short_hash(
            event.get("substance"), event.get("target"),
            event.get("placement"), clause),
    )


# A crossing is not just another event in the queue -- it BOUNDS the beat
# for that body. You cannot hear someone speak before they walk in, and
# their footsteps out do not precede their last word. The outcome stage
# builds its order keys from one running counter over dialogue, then acts,
# then movement, so a body who arrived and spoke rendered as "X says ... X
# comes in." (measured in the corpus replay's prose sample). Arrivals and
# departures therefore sit in bands outside the counter's range rather than
# competing inside it.
_ARRIVAL_BAND = -1_000_000
_DEPARTURE_BAND = 1_000_000


def crossing_percept(mover_name, label, direction, order_key=0):
    """A body entering or leaving the observer's room this beat, already
    channel-gated by the caller (seen at either end of the beat). The
    mover's canonical name is hashed into the dedupe key only.

    `order_key` orders crossings AMONG THEMSELVES; which side of the beat
    they land on is decided here, from the direction (see the band comment
    above), so no caller has to remember to do it."""
    band = _ARRIVAL_BAND if direction == "arrived" else _DEPARTURE_BAND
    return Percept(
        kind="crossing", channel="sight", source_label=label,
        data={"direction": direction},
        salience=0.6, suddenness=0.4,
        order_key=band + order_key,
        dedupe_key="crossing:" + _short_hash(mover_name, direction),
    )
