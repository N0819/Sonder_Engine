"""The identity floor applied to payloads and views: observer label functions,
the lore/paragraph name scrub, scene figures for charter sighting,
act-surface admission and the last-pass identity scrub.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from story.character_schema import (
    _UNSPACED_SCRIPT,
    character_appearance,
    persona_appearance,
    character_name,
    name_boundary_pattern,
    name_boundary_regex,
    normalized_character_of_row,
    persona_name,
)
from core.db import wget
from core.pipeline_context import note_step_decision
from language_runtime import compositor_text, compositor_value, linguistic
from story.scene import persona_of
from world.spatial import room_of, sense_adjusted, visual_level_between

from agents.common_base import _ling
from agents.common_names import (
    _name_tokens,
    _recognizes,
    _unknown_actor_label,
    _unspaced_name_parts,
)
from agents.common_cast import character_room, character_scene_keys
from agents.common_rooms import chatter_inputs
from agents.common_figures import presence_figures_for_room

def _uncarded_person(scene, name):
    """`(appearance, aliases)` when `name` is a PERSON the scene records --
    an animate entity, a charter body among them -- that no card describes;
    None for anything else. The entity's own spelling and aliases both count.
    The appearance is the entity's own, or None where it records none (the
    caller then asks the presence ledger, which is where perception reads a
    townsperson's look)."""
    from world.spatial import _is_body_entity, _unique_entity_keyed
    if not isinstance(scene, dict):
        return None
    eid, ent = _unique_entity_keyed(scene, name)
    if not eid or not isinstance(ent, dict) or not _is_body_entity(scene, eid, ent):
        return None
    appearance = ent.get("appearance") or ent.get("description") or None
    return appearance, [a for a in (ent.get("aliases") or []) if a]


def observer_view_label_fn(chat, observer_name, cast, scene, senses=None):
    """`observer_label_fn` for a field about what is in view RIGHT NOW --
    the orientation frame's `ahead_entity`, the note that the player said
    nothing -- where a stranger seen short of full detail is the view's own
    word for them, "an indistinct figure" (`composer.observer_display_map`'s
    rule, graded the same way: `sense_adjusted` over the body-level sight).
    `ahead_entity` named "the tall fox-eared woman" in a dim room while the
    view beside it said "an indistinct figure" (review 2026-10-04).

    A STRUCTURED SURFACE EARNS ITS SILHOUETTE, as it does in the display map
    (`composer._silhouette_labels`): a townsperson the charter dealt a
    surface is "the squat reedy figure in a scorched leather apron" in a dim
    hall, read off the same rows perception lays presence bodies from
    (`presence_figures_for_room`). The fixed figure is for a body with nothing
    structured to show -- and is the label the view gives every such body, so
    handing it to a surfaced one named somebody else (review 2026-10-05). Two
    silhouettes that read alike collapse to the fixed figure in the view; one
    name at a time cannot see that, and keeps the silhouette.

    Never the identity labeller itself: that one names a body for every
    reference -- an address the Director resolves, the teller of an old
    report, a name in lore -- and a reference is not a sighting. Put there,
    this rule made "the indistinct figure" resolve to a fountain and the
    descriptor a character knew a stranger by resolve to nobody. A known
    name, a thing, and a body out of view or in full view keep the identity
    label here too.
    """
    base = observer_label_fn(chat, observer_name, cast, scene=scene)
    # ONE derivation of the figures per labeller, shared by every name it is
    # asked about: `presence_figures_for_room` memoizes a room's rows on the
    # `inputs` it is handed, and handed none it built a fresh `chatter_inputs`
    # (registry slices, presence ledger, placements, derived records) for
    # EACH dim-light name (agents_common audit, Efficiency 3).
    inputs_box = []

    def _inputs():
        if not inputs_box:
            inputs_box.append(chatter_inputs(chat["id"], scene))
        return inputs_box[0]

    def label(name):
        out = base(name)
        text = str(name or "").strip()
        if not text or out == text or not isinstance(scene, dict):
            return out              # a known name, or a thing left as it is
        if not room_of(scene, observer_name) or not room_of(scene, text):
            return out
        level = sense_adjusted(
            visual_level_between(scene, observer_name, text, senses),
            "sight", senses)
        if level in ("full", "none"):
            return out
        from world.charter_surface import surface_label
        surface = _presence_surface(chat, scene, text, _inputs())
        described = surface_label(surface, level) if surface else ""
        if described:
            return str(compositor_text("unknown_actor", description=described))
        return str(compositor_value("dim_figure"))

    return label


def _presence_surface(chat, scene, name, inputs=None):
    """The structured surface the charter dealt `name`, read off the rows
    perception lays presence bodies from (`presence_figures_for_room`, the
    body's own room), or None -- a carded body has none. ``inputs`` is a
    caller's shared `chatter_inputs`, on which the room's rows are memoized."""
    room = room_of(scene, name)
    if not room:
        return None
    folded = str(name).casefold()
    for row in presence_figures_for_room(chat["id"], scene, room, inputs) or ():
        if str(row.get("name") or "").casefold() == folded:
            surface = row.get("surface")
            return surface if isinstance(surface, dict) else None
    return None


def observer_label_fn(chat, observer_name, cast, scene=None, *, known=None):
    """`name -> what THIS observer may call them`, for any payload that names
    a body outside perception's own scrubbing.

    Perception decides identity per observer and renders prose accordingly.
    Everything else that hands a character a NAME has to make the same
    decision, and until now nothing did -- so a structured field could hand
    over an identity the prose beside it was carefully withholding. Observed
    live: `perception.spatial_frame.ahead_entity` came from `scene.positions`,
    which is keyed by canonical name, and told a character who she was looking
    at. She had asked twice, in dialogue, and been refused both times; six
    beats later she used the surname aloud.

    Same rule as `agents/perception.py`'s own gate, from the same `known` map,
    through the same `_recognizes` predicate and the same
    `_unknown_actor_label`, so this is one identity floor rather than a second
    one that can drift from it. The predicate is the half that HAD drifted:
    membership in `known` is string equality, and perception asks `_recognizes`
    at nine sites, so a rank or title variant of somebody the observer knows
    ("Commander Riker" to a mind introduced to "William T. Riker") was a
    person in the view and a stranger in every payload beside it.
    """
    if known is None:
        known = set((wget(chat["id"], "known", {}) or {}).get(observer_name)
                    or [])
    sheets = {}
    for row in (cast or []):
        # Normalized once per card text (C14): `label` below reads appearance
        # and every scene key off this same sheet.
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        name = character_name(sheet)
        if name:
            sheets[name] = sheet
    persona = persona_of(chat)
    p_name = persona_name(persona)
    if p_name:
        sheets.setdefault(p_name, persona)
    _scene_box, _looks_box = [], []

    def _scene():
        if not _scene_box:
            _scene_box.append(scene if isinstance(scene, dict)
                              else (wget(chat["id"], "scene", {}) or {}))
        return _scene_box[0]

    def _looks():
        """{folded name: (appearance, surface, role)} off the presence ledger
        -- what perception labels a townsperson from, so this label and the
        view's agree (`presence_figures_for_room`)."""
        if not _looks_box:
            from world import charter_crowd
            looks = {}
            ledger = wget(chat["id"], "background_presences", {}) or {}
            for key, rec in (ledger.items() if isinstance(ledger, dict) else ()):
                if not isinstance(rec, dict):
                    continue
                sketch = rec.get("sketch") or {}
                spelled = str(rec.get("name") or key).strip().casefold()
                if not spelled:
                    continue
                hint = str(sketch.get("role_hint") or "")
                posts = ([] if hint.startswith("member of ")
                         else [p.strip() for p in hint.split(",") if p.strip()])
                role = next((charter_crowd._role_noun(p) for p in posts
                             if charter_crowd._role_noun(p)), "")
                surface = sketch.get("surface")
                looks.setdefault(spelled, (
                    str(sketch.get("appearance") or "").strip() or None,
                    surface if isinstance(surface, dict) else None, role))
            _looks_box.append(looks)
        return _looks_box[0]

    def label(name):
        text = str(name or "").strip()
        if not text or text == observer_name or _recognizes(text, known):
            return text
        sheet = sheets.get(text)
        if sheet is None:
            # A BODY WITHOUT A CARD IS STILL SOMEBODY. A townsperson the
            # charter simulates, a person the Director minted: the scene
            # records them as people and no card describes them, and waving
            # them through handed a character the full name of the man in
            # front of him -- `ahead_entity` gave Emory "Master Leofelric
            # Fenstonwell", and his next want was "Answer Master Fenstonwell"
            # (playerless Aldermill round 6, 2026-09-23, idx 2). A prop or a
            # room is still left as it is: inventing a description for a lamp
            # would be worse than leaving it.
            uncarded = _uncarded_person(_scene(), text)
            if uncarded is None:
                return text
            appearance, aliases = uncarded
            look, surface, role = _looks().get(text.casefold()) or (None, None, "")
            return _unknown_actor_label(text, appearance or look, aliases,
                                        role=role, surface=surface)
        return _unknown_actor_label(
            text, character_appearance(sheet), character_scene_keys(sheet)[1:])

    return label


def observer_name_scrub(chat, observer_name, cast):
    """`text -> the same text with unrecognized bodies renamed`, for a payload
    that hands a character PROSE somebody else wrote.

    `observer_label_fn` above gates a field that holds ONE name. This gates a
    field that holds a paragraph, and it exists because `world_knowledge` did
    not have either: lore entries are objective world record, they are written
    with canonical names in their prose, and some of them are written DURING
    PLAY -- by the mapping stage when this was measured, and since its
    retirement (2026-09-04) by the authoring package that files a Writers'
    Room change. Any character whose lore filter admitted the entry then
    read the name, met or not.

    Observed live (chat 38, t140): Tamamo had met the Doctor for the first
    time one beat earlier. Her `known` ledger was empty, her view called him
    "the lean energetic man", `ahead_entity` called him "the lean energetic
    man", her memories and her micro-perception all agreed -- and a lore entry
    in her payload opened "As The Doctor and Hinami walk deeper into the Deck
    14 corridor". She addressed him as "Doctor" in the same beat, and wrote
    "the lean energetic man now identified as Doctor" into her own concerns.
    Across the stored corpus, 65 lore entries in 22 chats name a cast member;
    16 of those were written during play.

    Whole-word only, and aliases too, because the entry that leaked used the
    plain registered name and a substring rule would maul any word containing
    it. Quoted spans are NOT exempt the way perception exempts them: a lore
    entry is not a transcript, and prose that quotes somebody naming a person
    is still telling the reader who they are.
    """
    # ONE read of the observer's `known` ledger for both halves -- it was
    # read here again after `observer_label_fn` had read it (agents_common
    # audit, Efficiency 3), and two reads are two answers free to differ.
    known = set((wget(chat["id"], "known", {}) or {}).get(observer_name) or [])
    label = observer_label_fn(chat, observer_name, cast, known=known)
    sheets = []
    for row in (cast or []):
        # Normalized once per card text (C14): the loop below reads a name and
        # every scene key off each of these.
        sheet = normalized_character_of_row(row)
        if sheet is not None:
            sheets.append(sheet)
    # The player is a body in the room like any other, and lore written during
    # play names them more often than it names anyone else. Same source as
    # observer_label_fn's, so the two cannot disagree about who is gated.
    persona = persona_of(chat)
    if isinstance(persona, dict):
        sheets.append(persona)
    subjects = []
    for sheet in sheets:
        name = character_name(sheet)
        # `_recognizes`, not membership: the same predicate `observer_label_fn`
        # above resolves a label with, so a mind's structured payload and its
        # prose cannot disagree about who it has met.
        if not name or name == observer_name or _recognizes(name, known):
            continue
        forms = {name} | {
            str(alias) for alias in (character_scene_keys(sheet)[1:] or [])
            if str(alias or "").strip()
        }
        replacement = label(name)
        if replacement == name:
            continue
        for form in forms:
            subjects.append((form, replacement))
    # Longest first: "The Doctor" must win over a bare "Doctor" alias, or the
    # longer form is left half-rewritten.
    subjects.sort(key=lambda pair: -len(pair[0]))
    shielded = _other_peoples_names(chat, sheets, subjects)

    def scrub(text):
        if not isinstance(text, str) or not text or not subjects:
            return text
        # ANOTHER PERSON'S NAME IS KEPT WHOLE while the forms run, so a
        # cast member's surname never matches inside a relative's name.
        held = {}
        for i, full in enumerate(shielded):
            pattern = name_boundary_pattern(full)
            if re.search(pattern, text):
                token = "\ue000%d\ue001" % i
                held[token] = full
                text = re.sub(pattern, token, text)
        for form, replacement in subjects:
            # Per-edge boundaries, the repaired siblings' rule
            # (`name_boundary_pattern`): `\b` is a property of spaced
            # scripts, so a Japanese name followed by its particle was
            # never scrubbed and this floor failed open in silence.
            text = re.sub(name_boundary_pattern(form), replacement, text)
        for token, full in held.items():
            text = text.replace(token, full)
        return text

    return scrub


def _other_peoples_names(chat, sheets, subjects):
    """The full names of people a scrub must NOT cut into, longest first.

    `observer_name_scrub` rewrites every form of an unmet cast member --
    the bare surname among them -- as a whole word, and a family shares a
    surname. Measured (scratch story 165, turn 4582, 2026-10-07): public lore
    read "What the town has to go on is Abel Gale's account", the scrub for
    the unmet pilot Hester GALE rewrote her surname inside her brother's
    name, and the innkeeper was handed "Abel the broad weather-worn woman's
    account" -- and told the player "ask Abel, she's standing right there".

    Other people are the registered cast (and the player) this scrub leaves
    alone, the story's planned people and the scene's animate people -- every
    multi-word name among them that contains a word of some subject's forms.
    A name that IS one of the scrubbed subjects' own forms is never shielded:
    a plan the Writers' Room filed under the player's own name must not carry
    that name past the floor. Read-only and fail-open to "shield nothing",
    which is the scrub as it was.
    """
    scrubbed = {str(form).casefold() for form, _ in subjects}
    # A NAME WRITTEN WITHOUT SPACES HAS WORDS TOO -- its script runs
    # (`_unspaced_name_parts`: 佐藤 | アベル). By whitespace alone 佐藤アベル
    # was one word and never a multi-word name, so it was never shielded and
    # the scrub for an unmet 佐藤 cut into it (agents_common audit F14).
    words = {w for form, _ in subjects
             for w in _words_of_a_name(str(form).casefold())}
    if not words:
        return []
    candidates = set()
    for sheet in sheets:
        candidates.add(character_name(sheet))
    try:
        from world.planned_entities import planned_entities
        for plan in (planned_entities(chat["id"]) or {}).values():
            candidates.add(str(plan.get("name") or ""))
            candidates.update(str(a or "") for a in plan.get("aliases") or ())
    except Exception:
        pass
    try:
        from llm.schemas import _ANIMATE_ENTITY_KINDS
        scene = wget(chat["id"], "scene", {}) or {}
        for ent in (scene.get("entities") or {}).values():
            if isinstance(ent, dict) and str(ent.get("kind") or "").strip() \
                    .casefold() in _ANIMATE_ENTITY_KINDS:
                candidates.add(str(ent.get("name") or ""))
    except Exception:
        pass
    out = set()
    for name in candidates:
        name = " ".join(str(name or "").split())
        folded = name.casefold()
        name_words = _words_of_a_name(folded)
        if (not name or len(name_words) < 2 or folded in scrubbed
                or not words & set(name_words)):
            continue
        out.add(name)
    return sorted(out, key=len, reverse=True)


def _words_of_a_name(name):
    """A name's words: by whitespace, exactly as before, plus the script runs
    of a name written without spaces (`_unspaced_name_parts`)."""
    text = str(name or "")
    return text.split() + _unspaced_name_parts(text)


def scrub_names_deep(value, scrub):
    """Apply a text scrub to every string in a nested payload value.

    Lore arrives as a list of dicts whose `content`, `title` and `keys` are all
    prose a mind will read; walking the structure keeps the caller from having
    to know which of them the current schema happens to use.
    """
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_names_deep(item, scrub) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_names_deep(item, scrub) for item in value)
    if isinstance(value, dict):
        # KEYS ARE TEXT A MIND READS TOO. A section keyed by who it is about
        # -- `{"<full name>": {...}}` -- handed the name over whole while the
        # value beside it was scrubbed (round-6 review of the identity floor,
        # 2026-09-23). Two keys that scrub to one label are both kept, the
        # second numbered, rather than one silently overwriting the other.
        out = {}
        for key, item in value.items():
            new_key = scrub(key) if isinstance(key, str) else key
            if new_key in out:
                n = 2
                while f"{new_key} ({n})" in out:
                    n += 1
                new_key = f"{new_key} ({n})"
            out[new_key] = scrub_names_deep(item, scrub)
        return out
    return value


def scene_figures(chat, cast, scene, recognized=None):
    """The scene-owned people -- the player and the cast -- as figures a
    Charter body could coarsely perceive: ``[{key, label, place}]``.

    ``key`` is the engine's canonical name (what `known` and every charter
    claim key by), ``place`` the room the scene puts them in (absent when
    it puts them nowhere), ``label`` how the observer in ``recognized``
    renders them: the name where recognition earned it, otherwise the same
    stranger label `_unknown_actor_label` mints for every other seam.
    ``recognized`` None means no vantage at all, so nothing is recognised --
    the right answer for the commit-side sighting, which stores the
    stranger label and lets each viewing observer relabel.
    """
    from world.spatial import room_of

    recognized = set(recognized or ())
    scene = scene or {}
    out = []
    pers = persona_of(chat)
    p_name = persona_name(pers)
    if p_name:
        out.append({
            "key": p_name,
            "label": (p_name if p_name in recognized
                      else _unknown_actor_label(
                          p_name, persona_appearance(pers))),
            "place": str(room_of(scene, p_name) or ""),
        })
    for row in cast or ():
        # Three normalizations per row became one (C14): name, appearance and
        # the scene keys `character_room` resolves through.
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        cname = character_name(sheet)
        if not cname:
            continue
        out.append({
            "key": cname,
            "label": (cname if cname in recognized
                      else _unknown_actor_label(
                          cname, character_appearance(sheet))),
            "place": str(character_room(scene, sheet) or ""),
        })
    return out

# Mirrors _protected_view_quotes' quoted-span shape: a name inside a quote
# is sensory signal the observer legitimately heard (an introduction, a
# name called aloud) and must survive the identity scrub verbatim.
#
# Single-quoted dialogue must be protected too -- the perception model
# routinely renders speech as '...' rather than "...", and the double-quote-
# only form let a name spoken aloud this beat (a self-introduction like
# 'I-I'm Hinami') get scrubbed straight out of what the hearer legitimately
# heard. The single-quote alternative is apostrophe-aware: the opening quote
# must not follow a word char or another quote (so contraction/possessive
# apostrophes -- She's, Hinami's -- never open a span), and an internal '
# counts as content only when a word char follows it (I'm, don't), so the
# span still closes at the real terminating quote.

_SURFACE_CLAUSE_SPLIT = re.compile(
    r"(?<=[,;:])\s+|\s+[—–]\s+|\s+--\s+"
    # The full-width clause marks, with no whitespace required: Japanese
    # writes none after 、, so a Japanese act was ONE span and naming one
    # unseen body cut the actor's whole conduct (agents_common audit F7).
    r"|(?<=[、，；：])\s*")
#: The marks a kept clause sheds before it is rejoined, of both families.
_SURFACE_CLAUSE_MARKS = ",;:、，；："


def _act_surface_admission(surface, *, actor, observer, forms_by_body,
                           perceived, who):
    """WHAT A BODY IS SEEN DOING IS ADMISSIBLE; WHAT IT IS SEEN DOING IT TO
    IS ADMISSIBLE ONLY WHERE THE TARGET IS.

    An `observable` is free text describing the ACTOR, and the act channel
    admitted the whole string on the actor's channel alone. Any OTHER body
    the sentence names is a percept about THAT body -- its presence, its
    state, its name -- and it reached every observer who could see the actor
    without passing a single admission gate of its own.

    Live (`PLAY_2026_09_05C_masque.md` § PX5, turn 6). Ivo stood on a
    completely dark terrace; Verrin, in the gallery, declared
    ``observable: "looks leisurely over Ivo's uncovered face, then lifts his
    wine glass and takes a slow, delicate sip without flinching"``. That
    sentence was delivered verbatim to a body in the reception room two
    edges away and to a body in the gallery whose own view in the same beat
    correctly read "Through the glazed terrace door, only darkness". Both
    received the name Ivo and the fact that his face was uncovered -- the
    plot's secret, delivered to the two people it was being kept from, in
    the beat it was created. No tripwire fired, because nothing was looking:
    the identity scrub answers "may this observer hear this NAME", and the
    leak here is the STATE beside it.

    `perceived` is this observer's own eyes for the beat -- the set
    `_composer_standing_percepts` fills through `seen_out`, which is the
    same "could this observer see them" answer every presence percept is
    built from. A body in it is admissible; a body absent from it is not,
    and the span that named it is cut. This SUBTRACTS: what survives is the
    actor's own conduct, which is what the channel was carrying.

    Returns ``(surface, cut_bodies)``; an empty surface means every span
    named somebody the observer has no channel to, and the caller refuses.
    """
    text = str(surface or "").strip()
    if not text or not forms_by_body:
        return text, []
    exempt = {str(actor or "").strip().casefold(),
              str(observer or "").strip().casefold()}
    seen_folded = {str(n or "").strip().casefold() for n in (perceived or ())}
    # Read from the section that OWNS the table (`agents.common`), never a
    # second copy under this module's own key: one list of ordinary English
    # words that are also names, in one place, per pack.
    common_words = linguistic("agents.common", "_COMMON_WORD_NAMES")
    third = []
    for body, forms in forms_by_body.items():
        canonical = str(body or "").strip()
        folded = canonical.casefold()
        if not canonical or folded in exempt or folded in seen_folded:
            continue
        patterns = []
        for form in {canonical, *(forms or ())}:
            form = str(form or "").strip()
            if not form:
                continue
            # An ordinary English word that is also somebody's name matches
            # only in its capitalised spelling -- the same guard
            # `_scrub_unknown_identities` applies, for the same reason: "the
            # rose garden" is not a percept of Rose.
            if len(form.split()) == 1 and form.casefold() in common_words:
                patterns.append(
                    name_boundary_regex(form[:1].upper() + form[1:]))
            else:
                patterns.append(name_boundary_regex(form, re.IGNORECASE))
        if patterns:
            third.append((canonical, patterns))
    named = [(body, patterns) for body, patterns in third
             if any(pattern.search(text) for pattern in patterns)]
    if not named:
        return text, []
    kept, cut = [], []
    for span in _SURFACE_CLAUSE_SPLIT.split(text):
        hits = [body for body, patterns in named
                if any(pattern.search(span) for pattern in patterns)]
        if hits:
            cut.extend(hits)
            continue
        span = span.strip().rstrip(_SURFACE_CLAUSE_MARKS).strip()
        if span:
            kept.append(span)
    cut = sorted(set(cut))
    # Rejoined with the clause mark the act itself was written with: 、 in a
    # Japanese act, a comma otherwise (an English act naming 佐藤 included).
    joiner = "、" if "、" in text and "," not in text else ", "
    trimmed = joiner.join(kept)
    note_step_decision(
        "act_percept", who, "refused" if not trimmed else "delivered",
        "the observable named %s, whom this observer has no channel to; "
        "%s" % (", ".join(cut),
                "nothing else was said about the actor"
                if not trimmed else "that clause was cut"))
    return trimmed, cut


def _scrub_unknown_identities(view, *, allowed_forms, unknown_sources,
                              labels=None, as_written=None):
    """Deterministic identity floor for perception view prose.

    The knows_identity/_unknown_actor_label gate used to be enforced only
    inside the deterministic injection helpers -- the perception LLM's own
    free-text prose was never checked, so a model that wrote a stranger's
    canonical name into a view walked straight past the gate (and no
    prompt paragraph even defined knows_identity, so this was not limited
    to weak models). This pass runs LAST on every view: each unknown
    source's name/alias forms are replaced, outside quoted spans only,
    with that source's unknown-actor descriptor.

    unknown_sources: [{name, appearance, aliases}] the observer does NOT
    recognize. allowed_forms: names the observer legitimately commands
    (their own name/aliases plus their recognized set) -- any colliding
    form is skipped rather than scrubbed.

    Returns (scrubbed_view, leaked_names) so callers can surface a
    warning; a silent leak was exactly how the original bug hid.

    ``as_written`` is for text WRITTEN ON A THING -- a slip, a ledger, a
    sign -- and takes each name as matched to what replaces it (the name in
    quotation marks, which this pass leaves alone outside-quotes-only on
    every later run). There the descriptor is the leak: a slip that reads
    "Loading supervised: Larkerwick" tells its reader a name, and rewritten
    to "the old thickset tally clerk" it told her which of the men in front
    of her the name was -- a fact the slip does not carry (Saltmarsh
    Crossing, 2026-10-11, scratch chat 170 idx 22 and 24, the second onto
    the page).
    """
    text = str(view or "")
    if not text or not unknown_sources:
        return view, []
    allowed = {str(f or "").strip().casefold()
               for f in (allowed_forms or []) if str(f or "").strip()}
    segments = _ling("_QUOTED_SPAN_RE").split(text)

    # ONE alternation, longest form first, so the longest name wins at every
    # position. Scripts without spaces make this load-bearing rather than
    # tidy: a name boundary cannot be asserted in Japanese (see
    # `name_boundary_pattern`), so a short unknown name like レイ would
    # otherwise eat into a longer recognised one like レイヤ. Allowed forms
    # are therefore matched too, and replaced with themselves, which shields
    # them from being partially consumed.
    candidates = []
    # Every label this pass may write is shielded like a name the observer
    # commands, so a second pass leaves a label the first one wrote alone:
    # the scrub is idempotent, and a view composed through two stages
    # cannot grow a label inside a label.
    label_shields = set()
    for src in unknown_sources:
        name = str(src.get("name") or "").strip()
        if not name or name.casefold() in allowed:
            continue
        # ONE LABEL PER (OBSERVER, BODY) PER BEAT: where the observer's own
        # display map has already chosen what to call this body -- "an
        # indistinct figure" for a stranger in dim light -- the scrub uses
        # that, never a full-sight epithet of its own. Measured (scratch play
        # 2026-09-14, chat 2 turn 1): the map said "an indistinct figure",
        # this rewrote "Bram" to "the slight young man early twenties", and
        # the page read "An indistinct figure the slight young man early
        # twenties shifts on the bench".
        label = (labels or {}).get(name) or _unknown_actor_label(
            name, src.get("appearance"), aliases=src.get("aliases"))
        if label:
            label_shields.add(str(label).strip())
        # A NAME'S OWN PARTS ARE SPELLINGS OF THE BODY IT NAMES. The forms
        # were the full name and the authored aliases, so a Director writing
        # a bare given name in free text walked past this pass while the same
        # channel carrying the full name was caught and repaired three times
        # in the same run. Measured (the Cold Season Ball, 2026-09-05, PX1):
        # `poses["Verrin Sault"].detail` said "eyes fixed on Ivo through his
        # white silk mask", and that sentence reached two minds' views, their
        # observations and their stored episodes -- whose `entities` array
        # ends `"Verrin Sault", "Ivo"`. The control is in the same run: turns
        # 8, 9 and 15 carried "Ivo Sarn" and every one fired the tripwire.
        #
        # Withholding is the direction that may be generous, because every
        # miss here SUBTRACTS: a part that collides with a form the observer
        # legitimately commands is shielded by the `allowed` check below and
        # by the longest-form-first alternation, and a part too short or too
        # ordinary to tell from a word is refused by the same two guards the
        # authored forms pass through.
        # A part that is a TITLE, an ARTICLE or one of the engine's own
        # label heads is a word the name shares with the language, not a
        # spelling of the body: "The Stranger" yields nothing here, which is
        # right twice over -- it is an engine label rather than an identity,
        # and scrubbing its "the" would eat every article in the view. Both
        # tables are language DATA the pack already owns for naming.
        _generic = set(_ling("_NAME_TITLE_TOKENS")) | set(
            _ling("_GENERIC_LABEL_HEADS"))
        # AND A ROLE WORN IN THE NAME IS NOT IDENTITY -- `_unknown_actor_label`'s
        # rule, for the same bodies: an institution puts its post in front of
        # the personal name ("Reeve Cuthon Hurster"), and the language's own
        # title table cannot know every post a town invents. Scrubbed as a
        # part, "Reeve" turned the room "Reeve's Hall" into "the unfamiliar
        # person's Hall" in Sal's views on five beats, with nine false
        # tripwires (playerless Aldermill round 8, 2026-09-23). The full name
        # and the personal parts are still scrubbed.
        _generic |= {tok.casefold() for key in ("role", "noun", "titles")
                     for tok in re.findall(r"[\w-]+", str(src.get(key) or ""))}
        # ...and the runs of a role written without spaces (衛兵隊長), which
        # the word split above keeps whole.
        _generic |= {tok.casefold() for key in ("role", "noun", "titles")
                     for tok in _name_tokens(str(src.get(key) or ""))
                     if _UNSPACED_SCRIPT.match(tok[:1])}
        # A HYPHENATED COMPOUND IS ONE WORD, the rule the label check below
        # already keeps: its fragments are not spellings of the body. Split
        # on every non-word character, the post "Flume-tender" gave a part
        # "Flume", and the room "Wheelhouse and Flume" read "Wheelhouse and
        # the hard-bitten barrel-chested hand ..." in Emory's views, with
        # eight false tripwires (playerless Aldermill round 7, 2026-09-23).
        if len(name.split()) > 1:
            parts = [tok.strip("-") for tok in re.split(r"[^\w-]+", name)
                     if tok.strip("-")
                     and tok.strip("-").casefold() not in _generic]
        else:
            # A NAME WRITTEN WITHOUT SPACES HAS PARTS TOO: 佐藤ヒナミ and
            # 佐藤・ヒナミ are 佐藤 | ヒナミ (`_unspaced_name_parts`, script
            # runs at the length that script identifies somebody in). The
            # whitespace test above derived none, so a bare ヒナミ in free
            # prose reached the view and `leaked` stayed empty -- no tripwire
            # (agents_common audit F2, 2026-11-01). A Latin name with no
            # space ("Jean-Luc") is still one word.
            parts = [tok for tok in _unspaced_name_parts(name)
                     if tok.casefold() not in _generic]
        authored = {name.casefold()} | {
            str(a or "").strip().casefold() for a in (src.get("aliases") or [])}
        derived = {tok for tok in parts if tok.casefold() not in authored}
        for form in [name] + [str(a or "").strip()
                              for a in (src.get("aliases") or [])] + parts:
            if not form or form.casefold() in allowed:
                continue
            # A SPELLING THE OBSERVER'S OWN LABEL FOR THIS BODY ALREADY USES
            # IS NOT A NAME THE OBSERVER LACKS. A post can be both a name
            # form and what the body is seen as: "Master Miller" is the
            # miller's title and the head of his label ("the middle-aged ...
            # master miller"). Scrubbing it rewrote the label's own words
            # into the label, and every later pass rewrote them again --
            # "measured the middle-aged tall broad-shouldered pale measured
            # the middle-aged ..." in every view Emory read (playerless
            # Aldermill, 2026-09-23). Whole words only, a hyphen joining a
            # word to another making it part of that word, so a name "Grey"
            # is still scrubbed beside a label "grey-haired".
            if label and re.search(
                    r"(?<![\w-])" + re.escape(form.casefold()) + r"(?![\w-])",
                    str(label).casefold()):
                continue
            # A short Latin form cannot be told from an ordinary word; a short
            # CJK form is a perfectly ordinary name, and skipping it is the
            # leak this whole pass exists to prevent.
            if (len(form) < 3 and len(form.split()) == 1
                    and not _UNSPACED_SCRIPT.match(form[:1])):
                continue
            # A WORD TAKEN FROM INSIDE A NAME IS A NAME ONLY AS A PROPER
            # NOUN. "Master" in "Master Godidric Stanpenridge" is a post the
            # composer's own descriptor uses in lower case ("...measured
            # master, with flour-dusted hair"); matched in any case it was
            # rewritten into a label that did not contain it, and every
            # later pass rewrote it again (playerless Aldermill round 3,
            # 2026-09-23, Emory's views t7-t23). The given name a Director
            # or a voice writes is capitalised, so capitalised is what a
            # derived part matches -- the same rule the common-word names
            # below already follow.
            if (len(form.split()) == 1
                    and (form in derived
                         # Single-token names that are also everyday English words ("Rose walks in"
                         # vs "the rose garden"). For these, only the exact capitalized form is
                         # scrubbed, so ordinary lowercase prose is never mangled.
                         or form.casefold() in _ling("_COMMON_WORD_NAMES"))):
                # common-word guard: exact capitalized form only
                exact = form[:1].upper() + form[1:]
                candidates.append(
                    (exact, f"(?-i:{name_boundary_pattern(exact)})", name, label))
            else:
                candidates.append(
                    (form, name_boundary_pattern(form), name, label))
    if not candidates:
        return view, []
    shields = sorted(
        {str(f or "").strip() for f in (allowed_forms or []) if str(f or "").strip()}
        | {f for f in label_shields if f},
        key=len, reverse=True)
    ordered = sorted(candidates, key=lambda item: len(item[0]), reverse=True)
    by_group = {}
    parts = []
    for index, form in enumerate(shields):
        by_group[f"s{index}"] = None
        parts.append(f"(?P<s{index}>{name_boundary_pattern(form)})")
    for index, (_form, pattern, name, label) in enumerate(ordered):
        by_group[f"u{index}"] = (name, label)
        parts.append(f"(?P<u{index}>{pattern})")
    combined = re.compile("|".join(parts), re.IGNORECASE)

    leaked = []

    def _replace(match):
        entry = by_group.get(match.lastgroup)
        if entry is None:  # an allowed form: kept exactly as written
            return match.group(0)
        name, label = entry
        if name not in leaked:
            leaked.append(name)
        if as_written is not None:
            return as_written(match.group(0))
        return label

    for i in range(0, len(segments), 2):  # even = outside quotes
        if segments[i]:
            segments[i] = combined.sub(_replace, segments[i])
    if not leaked or as_written is not None:
        return "".join(segments) if leaked else view, leaked
    # A LABEL BRINGS ITS OWN FIRST WORD, and where the view had already
    # written that word in front of the name the page doubled it: "facing the
    # the unfamiliar person's trousers" (a thing named for its owner, chat 154
    # replay, 2026-09-28). The view's copy goes; the label's stays, taking the
    # capital the view's had at the head of a sentence. Only the label's own
    # first word, so no language needs an article table here.
    for name, label in {v for v in by_group.values() if v}:
        words = str(label or "").split()
        if name not in leaked or not words:
            continue
        doubled = re.compile(r"(?<![\w-])(" + re.escape(words[0]) + r")\s+("
                             + re.escape(str(label)) + r")", re.IGNORECASE)

        def _once(match):
            kept = match.group(2)
            return (kept[:1].upper() + kept[1:]) if match.group(1)[:1].isupper() else kept

        for i in range(0, len(segments), 2):
            if segments[i]:
                segments[i] = doubled.sub(_once, segments[i])
    return "".join(segments), leaked
