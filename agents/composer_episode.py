"""The English reference EPISODE renderer (memory mode): first-person
sentences, what files as memory, `render_episode`, and `episode_signature`.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import logging
from .common import (
    _appearance_as_prose,
    _base_from_third_person_s,
    _compose_residue_view,
    _observable_predicate,
)
logger = logging.getLogger("agents.composer")

from agents.composer_common import (
    _ENGLISH_COMPOSITOR,
    _cap,
    _en,
    _safe_renderer,
)
from agents.composer_person import _first_person, _said_as_mine, _verbs_in_base
from agents.composer_bodies import EAR_STATES
from agents.composer_speech import _feeling_heard, _names_kept, _one_voice_each
from agents.composer_landscape import (
    far_sight,
    is_landscape,
    landscape_lines,
    render_landscape_line,
)
from agents.composer_standing import (
    HABITUATING_SOUND_TAGS,
    standing_verdicts,
    unheard_ceasing,
)
from agents.composer_render import (
    _end_sentence,
    _render_ambient,
    _render_pose,
    _render_scent,
)


# --------------------------------------------------------------------------
# Layer B -- the episode renderer (memory mode)
# --------------------------------------------------------------------------

_GENERIC_LABELS = frozenset(_ENGLISH_COMPOSITOR["generic_labels"])


def _observed_conduct(p, surface, key, **extra):
    """"I saw/heard <label> <the act in its base form>." -- the act's
    surface with its verbs turned, through `key` (`episode_act`,
    `episode_communication[_via]`), or the observable predicate where the
    leading verb cannot be turned."""
    words = surface.split()
    if words:
        base = _base_from_third_person_s(words[0])
        if base:
            # EVERY VERB OF THE ACTOR'S OWN PHRASES after "I saw X" takes
            # the base form, by the one rule the mind's own attempt is
            # turned by (`_verbs_in_base`): only the first verb was, and the
            # lighthouse probe's keeper filed "I saw Rhona Carrick dig into
            # her jacket and brings out a sealed letter" (2026-10-20, chat 2
            # row 40). Where the rule cannot turn the phrase exactly, the
            # first verb alone is turned, as before.
            turned = _verbs_in_base(surface).split()
            if turned:
                head = turned[0]
                action = (head if head.isupper() and len(head) > 1
                          else head[:1].lower() + head[1:])
                rest = " ".join(turned[1:]).rstrip(".")
            else:
                action, rest = base, " ".join(words[1:]).rstrip(".")
            ending = f" {rest}." if rest else "."
            return _en(key, label=p.source_label, action=action,
                       ending=ending, **extra)
    sentence = _observable_predicate(p.source_label, surface)
    if sentence and extra.get("via"):
        sentence = _en("speech_via", sentence=sentence.rstrip("."),
                       via=extra["via"])
    return sentence or ""


def _episode_sentence(p):
    if p.kind == "speech":
        if p.fidelity == "silence":
            return _en("episode_speech_silence", label=p.source_label)
        if p.fidelity == "trace":
            return _en("episode_speech_trace")
        if p.fidelity == "voice":
            # The voice is the whole of what arrived, so it is what is kept:
            # whose (where known or seen), how loud, the tone it carried.
            d = p.data or {}
            loudness = {"loud": _en("speech_voice_raised"),
                        "shout": _en("speech_voice_shouting")}.get(
                str(d.get("volume") or "").casefold(), "")
            line = (_en("episode_speech_voice", label=p.source_label,
                        loudness=loudness)
                    if d.get("attributed") and str(p.source_label or "").strip()
                    else _en("episode_speech_voice_unknown", loudness=loudness))
            tone = _feeling_heard(d)
            return line + (" " + _en("episode_speech_voice_tone", tone=tone)
                           if tone else "") + (
                " " + _en("episode_speech_own_name")
                if d.get("own_name") else "")
        via = str(p.data.get("via") or "")
        if p.fidelity == "fragment":
            attributed = bool(p.data.get("attributed"))
            key = ("episode_muffled_attributed_via" if attributed and via
                   else "episode_muffled_via" if via
                   else "episode_muffled_attributed" if attributed
                   else "episode_muffled")
            return _en(key, via=via, label=p.source_label,
                       fragment=p.data.get("fragment", "")) + (
                " " + _en("episode_speech_own_name")
                if p.data.get("own_name") else "")
        body = p.data.get("body") or ""
        # The route rides into MEMORY too. A character who later recalls being
        # told something over a radio must not remember the speaker standing
        # there -- that is the same fact deleted one layer down, and memory is
        # where it would never be noticed.
        if via:
            return _en("episode_speech_via", via=via,
                       label=p.source_label, body=body)
        if p.data.get("conducted"):
            return _en(
                "episode_conducted", label=_cap(p.source_label), body=body)
        return _en("episode_speech", label=p.source_label, body=body)
    if p.kind == "act":
        if p.data.get("unseen"):
            # HEARD, NOT SEEN, AND NOBODY NAMED: what crossed from the rear
            # arc is that something moved, and where (`act_percept`). This
            # fell to the `shapes` branch below with an empty label --
            # " moved, too little of it to make out." -- the bearing gone and
            # a sound filed as a sight (audit agents_composer F5,
            # 2026-11-01). The bearing is the observer's own ("behind you"),
            # turned into memory's first person.
            bearing = str(p.data.get("bearing") or "").strip()
            return _first_person(
                _en("episode_act_heard_placed", where=bearing) if bearing
                else _en("episode_act_heard"))
        if p.fidelity == "shapes":
            room = str(p.data.get("room") or "")
            if room:
                return _en("episode_act_shapes_placed",
                           label=_cap(p.source_label),
                           where=_en("presence_in_room", room=room))
            return _en("episode_act_shapes", label=_cap(p.source_label))
        surface = _said_as_mine(p.data, "surface")
        return _observed_conduct(p, surface, "episode_act")
    if p.kind == "communication":
        # A REPORTED ACT OF SPEECH IS REMEMBERED AS HEARD. This renderer had
        # no branch for it, so "Rhona warns the tide is turning" reached the
        # view and no English memory, while the Japanese episode filed it
        # (audit agents_composer F6, 2026-11-01). The same verb turning an
        # act gets, and the channel it came over, as a line's memory keeps
        # it (`episode_speech_via`).
        surface = str(p.data.get("surface") or "").strip()
        via = str(p.data.get("via") or "").strip()
        return _observed_conduct(
            p, surface, "episode_communication_via" if via
            else "episode_communication", via=via)
    if p.kind == "cue":
        cue = str(p.data.get("cue") or "").strip()
        return _en("episode_cue", label=p.source_label, cue=cue) if cue else ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return _en("episode_arrived", label=_cap(p.source_label))
        return _en("episode_departed", label=_cap(p.source_label))
    if p.kind == "substance":
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _end_sentence(_cap(clause)) if clause else ""
    if p.kind == "environment":
        name = p.data.get("room_name")
        return _en("episode_room", room=name) if name else ""
    if p.kind == "pose":
        return _render_pose(p, past=True)
    if p.kind == "sensation":
        if p.data.get("ears") in EAR_STATES:
            return _en("episode_ears_" + p.data["ears"])
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _end_sentence(_cap(clause)) if clause else ""
    if p.kind == "appearance":
        desc = _appearance_as_prose(p.data.get("description"))
        return _en("episode_appearance", description=desc) if desc else ""
    if p.kind == "scent":
        return _render_scent(p, episode=True)
    if p.kind == "residue":
        # A MEMORY IS THE MIND'S OWN, ASLEEP AS AWAKE: the residue is turned
        # into the first person like every other line of an episode. It was
        # turned only when a waking had more of the beat after it, so the
        # farmhouse probe's sleeper filed "You are under, below waking." five
        # beats running (2026-10-20, chat 2).
        return _first_person(_compose_residue_view(
            p.data.get("level"), targeted=p.data.get("targeted", False),
            loud_event=p.data.get("loud_event", False),
            pain=p.data.get("pain", False), woke=p.data.get("woke", ""),
            episode=True))
    if p.kind == "ambient":
        # What was seen far off and what was heard this beat: a vista line,
        # what a look at one found, a beat's own sound. The view rendered
        # them and memory did not -- the class 43946e73 fixed in
        # `_render_event`, one renderer over (UNBUILT_CHARACTERS §1.178).
        if p.data.get("landscape"):
            lines = landscape_lines([p])
            return render_landscape_line(lines[0][1], episode=True) if lines else ""
        return _first_person(_render_ambient(p, episode=True))
    return ""


#: The standing kinds an episode keeps when they are NEW OR CHANGED, plus far
#: sight (`far_sight`): a room, a sensation, a pose, a scent -- and what
#: stands on the horizon or far off, which is where a place sits in a mind's
#: memory of it. Every other standing line is the room's furniture.
_EPISODE_STANDING_KINDS = ("environment", "sensation", "pose", "scent")
#: A beat's own sound, as the outcome stage mints it: STANDING, keyed by
#: what it says (`ambient_percepts`, `distant_sound_percepts`), so new only
#: on the beat it is heard -- English filed it nowhere (review 2026-10-05).
#: AND A STEADY SOUND'S START AND STOP (DESIGN_SOUND_FIELD § 17, round 2):
#: the room's soundscape, a crowd's hum and the weather's sound
#: (`HABITUATING_SOUND_TAGS`) are keyed by the sound's own state, so they
#: are new on the beat they begin, on a beat they change, and on the beat
#: they stop (`sound_ceased_percept`'s key) -- and on no other: a sound
#: heard every beat is filed once, while the view, which has habituated,
#: says nothing (the owner, 2026-09-26: memory is the priority; "the
#: generator stopped some time in the night" must be recallable).
_EPISODE_SOUND_TAGS = ("ambient", "distant_sound", *HABITUATING_SOUND_TAGS)


def _files_as_memory(p):
    """Does English memory keep this standing percept when it is new or
    changed (appearance has its own ledger and is decided apart)?"""
    if p.kind in _EPISODE_STANDING_KINDS or far_sight(p):
        return True
    return (p.kind == "ambient"
            and str(p.dedupe_key or "").split(":", 1)[0] in _EPISODE_SOUND_TAGS)


def _render_episode_english(percepts, *, prev_standing=frozenset(),
                            prev_described=frozenset()):
    """Mint one first-person episode from the IR -- the salient delta.

    Consumes the SAME fidelity-degraded surfaces the view renderer consumes
    (a fragment percept carries only its fragment), so the episode can never
    outrun the view -- rule 03 section 5.2, subset-checked in tests.

    Returns ``(content, gist, entities)``. A percept list holding no events
    and no CHANGED standing state is a non-event: content is "" and nothing
    should be minted (the caller writes no row; the turn index still records
    the beat).
    """
    percepts = list(percepts or [])
    residue = [p for p in percepts if p.kind == "residue"]
    if residue:
        sentence = _episode_sentence(residue[0])
        rest = [p for p in percepts if p.kind != "residue"]
        if (residue[0].data or {}).get("woke") and rest:
            # THE WOKEN MIND REMEMBERS THE REST OF THE BEAT (§ 17): the
            # waking as the residue tells it, in the first person, then
            # what it perceived from that moment on, filed as any awake
            # mind's episode is. (`_episode_sentence` has already put the
            # residue into the first person.)
            woke = sentence
            content, gist, entities = _render_episode_english(
                rest, prev_standing=prev_standing,
                prev_described=prev_described)
            if content:
                return (woke + " " + content).strip(), gist or woke, entities
            return woke, woke, []
        return sentence, sentence, []

    events = sorted(
        [p for p in percepts if p.order_key is not None],
        key=lambda p: p.order_key)
    # A SILENCE IS ONLY A MEMORY TO AN EAR THAT HAD THE NOISE (D3, § 17):
    # the same verdicts the view renders by, so a stopping this mind's own
    # ledger never earned is filed nowhere.
    verdicts = standing_verdicts(
        [p for p in percepts if p.order_key is None],
        prev_standing, prev_described)
    changed = []
    for p in percepts:
        if p.order_key is not None or is_landscape(p):
            continue
        if p.kind == "appearance":
            if p.data.get("force") \
                    or str(p.data.get("source_key") or "") not in prev_described:
                changed.append(p)
        elif unheard_ceasing(p, verdicts.get(p.dedupe_key, "first")):
            continue
        elif _files_as_memory(p) and p.dedupe_key not in prev_standing:
            # A pose that CHANGED is a real memory -- somebody knelt, or was
            # pinned. An unchanged one is furniture and the dedupe key keeps
            # it out, which is the same rule the room already lives under.
            # A scent lives under it for the same reason and earns its place
            # for a stronger one: a smell is among the most retrievable
            # things a mind stores, and the dedupe key already moves when the
            # grade does, so walking into range of one is the change.
            changed.append(p)

    # FAR PLACES are laid out from every far percept, exactly as the view
    # lays them out, and a line is filed when a place it SHOWS is new or
    # changed -- re-laid from the changed places alone, an episode filed a
    # place the view had trimmed away (review 2026-10-05).
    far_lines = []
    for rep, line in landscape_lines([p for p in percepts if is_landscape(p)]):
        if any(q.dedupe_key not in prev_standing for q in line["shown"]):
            sentence = _cap(render_landscape_line(line, episode=True))
            if sentence:
                far_lines.append((rep, sentence, line["names"]))

    if not events and not changed and not far_lines:
        return "", "", []

    # Event-bearing content LEADS; changed standing state trails, with any
    # room change last of all. This ordering is LOAD-BEARING for retrieval:
    # embedding models systematically over-weight a text's first sentence
    # (~15% beginning-to-end similarity falloff, consistent across
    # positional-encoding families -- Lee, Goel & Ramchandran, "Quantifying
    # Positional Biases in Text Embedding Models", arXiv:2412.15241), so an
    # episode that opens with scene-setting embeds as its room, not its
    # event. When the only change IS the room, the movement is the event
    # and may lead.
    # FAR SIGHT TRAILS EVERYTHING, near to far -- the far places, then the
    # horizon -- and is a memory's gist only when it is all the memory holds:
    # it is where the place sat in view, never what happened (review
    # 2026-10-05: a town's lights at dusk took the gist from the question
    # put to the mind that beat).
    near = [c for c in changed if not far_sight(c)]
    horizon = [c for c in changed if far_sight(c)]
    if events:
        ordering = (events
                    + [c for c in near if c.kind != "environment"]
                    + [c for c in near if c.kind == "environment"])
    else:
        ordering = near

    sentences = []
    entities = []
    best = None
    for p in ordering:
        sentence = _episode_sentence(p)
        if not sentence:
            continue
        sentences.append((p, sentence))
        label = str(p.source_label or "")
        if label.casefold() not in _GENERIC_LABELS and label not in entities:
            entities.append(label)
        if best is None or p.salience > best[0].salience:
            best = (p, sentence)
    far = []
    for rep, sentence, names in far_lines:
        far.append((rep, sentence))
        for name in names:
            if name.casefold() not in _GENERIC_LABELS and name not in entities:
                entities.append(name)
    for p in horizon:
        sentence = _episode_sentence(p)
        if sentence:
            far.append((p, sentence))
            label = str(p.source_label or "")
            if label.casefold() not in _GENERIC_LABELS and label not in entities:
                entities.append(label)
    sentences += far
    if best is None and far:
        best = far[0]

    seen = set()
    ordered = []
    for p, sentence in sentences:
        if sentence in seen:
            continue
        seen.add(sentence)
        ordered.append(sentence)
    content = " ".join(ordered).strip()
    gist = best[1] if best else (ordered[0] if ordered else "")
    return content, gist[:240], entities[:16]


def episode_signature(p):
    """What a percept says in an episode, as a signature two stages can compare
    (the English sentence, whatever the story's language: it is never shown).
    The act stage and the outcome mint one act under different event ids, so
    its `dedupe_key` differs between them while what it says does not
    (`perception.perception_outcome`, 2026-09-30)."""
    if p.kind == "ambient":
        # An act re-minted under a new event id is what this exists for; an
        # ambient line is keyed by what it says already, and a look at a
        # vista said the standing line's words and was dropped as a repeat
        # of it -- in no memory at all (review 2026-10-05).
        return ""
    if p.kind == "act" and (p.data or {}).get("unseen"):
        # A movement HEARD is keyed by its body already (`act-heard:`), and
        # its sentence names nobody, so every such percept signed the same
        # string: one body's movement at the onset swallowed another body's
        # at the outcome as a "repeat" (audit agents_composer F5).
        return ""
    try:
        return " ".join(str(_episode_sentence(p) or "").split()).casefold()
    except Exception:  # noqa: BLE001 -- a percept no sentence covers has no signature
        return ""


def render_episode(percepts, *, prev_standing=frozenset(),
                   prev_described=frozenset(), language=None, renderer=None):
    """Mint a memory episode through the selected deterministic adapter."""
    percepts = _names_kept(_one_voice_each(percepts))
    selected = renderer if renderer is not None else _safe_renderer(language)
    if selected is not None:
        try:
            return selected.render_episode(
                percepts, prev_standing=prev_standing,
                prev_described=prev_described)
        except Exception:
            logger.exception("language renderer failed; using English wording")
    return _render_episode_english(
        percepts, prev_standing=prev_standing,
        prev_described=prev_described)
