"""Leaf helpers shared by more than one commit domain: scalar utilities,
entity-id canonicalisation, and the name/address roster.

Extracted verbatim from commit.py, which re-exports every name here so
`from commit import X` and `commit.X` keep working for callers and tests.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json, re
from core.db import q, wget, wset
from story.character_schema import (_UNSPACED_SCRIPT, character_name_from_text,
                              fold_identity_key, persona_name)
from world.mechanics import beat_end_elapsed, clock_elapsed, stable_event_key
from world.spatial import normalize_room_id

def _keys_str(value):
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value or "")

# Deterministic event/memory ids live in mechanics.py now (the sweep needs
# them without importing commit); kept under the old private name for the
# many call sites and tests that use it.
_stable_event_key = stable_event_key

# `_clamp` used to be written out here as well as in `mind/memory.py`, with
# separate callers each and nothing reporting them if they drifted (audit
# STORY-F11's shape). It belongs to `mind.memory`, whose confidences and
# saliences are what it bounds; `persist/commit.py` re-exports it, so
# `from commit import _clamp` is unaffected.
from mind.memory import _clamp  # noqa: F401


def _normalize_character_output(out):
    """Legacy `inference_updates` read as `mind_model_updates`.

    THIS IS THE OWNER, and `agents/common.py` imports it -- not the other way
    round, though the character stage is the more natural home for it. The
    import direction is forced: `agents/__init__.py` imports `background.py`,
    which imports `persist.commit` at module scope, so `commit_common`
    importing `agents.common` closes a cycle at interpreter start. Recorded
    because the obvious repair is the one that does not work.

    A second CALLER is legitimate and is why the shape survives: the character
    stage runs this on what the model returned, and commit runs it again on a
    rehydrated result, which never passed through the stage.
    """
    if not out.get("mind_model_updates") and out.get("inference_updates"):
        converted = []
        for update in out["inference_updates"]:
            converted.append({
                "about_entity": str(update.get("about") or "unknown"),
                "kind": "goal",
                "claim": str(update.get("conclusion") or ""),
                "confidence": float(update.get("confidence", 0.5)),
                "evidence": [{"event_id": "", "fact": str(update.get("basis") or "")}],
                "alternatives": [],
            })
        out["mind_model_updates"] = converted
    return out

def _player_name_or_none(ctx):
    """The player's own name, or None if it cannot be resolved."""
    try:
        from story.scene import persona_of
        return persona_name(persona_of(ctx.chat)) or None
    except Exception:
        return None



def _monotonic_elapsed(prev_clock, time_diff, *, floor=False):
    """The story clock this beat's time diff yields. TIME DOES NOT RUN
    BACKWARDS, AND A BEAT THAT SAYS NOTHING STILL TAKES TIME.

    `end_seconds` is an absolute position on the story clock, and a model
    that emits `start_seconds: 0` every beat -- an easy and entirely natural
    reading of a field named "start" -- resets the world to the length of its
    own beat, over and over. Measured on a fifty-beat quest with several
    explicit hour-long skips: the clock finished at 30.0 seconds while its
    own display read "an hour and a half", and everything windowed on seconds
    went quiet with it -- routine residue never fired once, because the gap
    between a room's last sighting and now was always zero.

    The duration is still honoured when the absolute position is nonsense: a
    beat that took an hour advances the clock by an hour rather than being
    discarded, because the elapsed time is the part the fiction actually
    asserted.

    ONE helper on purpose: `prepare_memory_commit` reads the same diff to
    stamp affect/strain/belief windows, and reading the raw field there let
    a backwards beat window this beat's psychology on a clock the scene
    commit had already refused. Returns ``(elapsed_seconds, displaced)``
    where ``displaced`` is None or ``(claimed, was)`` for the caller's
    warning -- a position the engine did not adopt, whether it ran
    backwards or arrived anchored away from the clock (the engine owns the
    clock's position; a beat contributes a span -- see
    `world.mechanics.read_time_diff`).

    The SHAPE of the diff is not this helper's to know -- it belongs to
    `world.mechanics.read_time_diff`, the one reader of the
    `state_diff.time` vocabulary. Knowing only `end_seconds` here was the
    second half of the same defect: a beat that named its position under
    the clock's own key, `elapsed_seconds` -- which the resolve payload
    prints to the model every beat -- read as no claim at all, and the
    clock held with nothing warned. Chat 88: turns 61 and 64 claimed 1107
    and 1266 against a clock standing at 1106.0, and turn 66 claimed 7200
    against 1136.0. Not one of the three moved the clock or warned; the only
    advance in that stretch came from turn 65's canonically spelled diff.

    `floor=True` is the caller saying THIS BEAT HAPPENED, and it is the
    third instalment of the same class. The scene commit charges a resolved
    beat that asserts no readable time `UNCLAIMED_BEAT_SECONDS`; this seam
    stamps affect decay, strain windows and belief provenance, so a memory
    commit that did not charge the same beat would leave a story's
    psychology ten seconds behind its world on every one of the 130 corpus
    beats measured in that shape. Both routes reach the arithmetic through
    `world.mechanics.beat_end_elapsed` and neither computes an end clock of
    its own -- a caller that does re-opens exactly the disagreement this
    helper exists to have closed.
    """
    elapsed, displaced, _refused, _floored = beat_end_elapsed(
        clock_elapsed(prev_clock), time_diff, floor=floor)
    return elapsed, displaced

# ---- Address forms and the name roster ----
#
# NOT the mapping commit, which is `commit_mapping.py`. This block carried a
# `# ---- Mapping commit ----` marker for as long as it lived in commit.py,
# where the real mapping commit sat 1,700 lines below it under a heading that
# said "Background-presence tracking". The roster below is read by memory,
# background, mapping, carriers and crowds alike.

_ADDRESS_ARTICLES = ("the ", "a ", "an ")


def _form_in(form, body):
    """Is this address form spoken in this line?

    Case-insensitive for a distinctive name, case-SENSITIVE for a form that is
    also an ordinary English word -- the same posture, and the same word list,
    that `_scrub_unknown_identities` already uses. Live in this database: a
    Starfleet cast contains `Data`, and matching that case-insensitively would
    have every line mentioning sensor data introduce a man.
    """
    from story.character_schema import name_boundary_regex
    from language_runtime import linguistic
    common_word_names = linguistic("agents.common", "_COMMON_WORD_NAMES")
    flags = 0 if form.casefold() in common_word_names else re.I
    # A name boundary, not \b: `\bヒナミ\b` never matches `ヒナミさん`, so
    # every Japanese address form read as unspoken.
    return bool(name_boundary_regex(form, flags).search(body))


def _address_forms(roster):
    """The ways a roster name is actually SAID, keyed by the roster name.

    A name is stored as a display string -- `The Doctor`, `Cmdr. Vale`,
    `Jean-Luc Picard` -- and nobody speaks in display strings. They say
    "Doctor", "Vale", "Picard". Requiring the exact stored string meant the
    ordinary way of addressing somebody taught nobody anything.

    Measured on chat 63: 552 dialogue lines, 33 of them say "Doctor" and the
    roster holds "The Doctor". The engine's own data shows the same split from
    the other side -- chat 22's recognition map holds `Data` and `Lt.
    Commander Data`, `Deanna Troi` and `Counselor Troi`, as separate people
    who do not know each other.

    A form that two roster members share is DROPPED rather than guessed: two
    Picards in a room means "Picard" identifies nobody, and inventing an edge
    is worse than missing one, because a wrong edge cannot be told from a
    right one afterwards.
    """
    candidates = {}
    for name in roster:
        full = str(name or "").strip()
        if not full:
            continue
        forms = {full}
        folded = full.casefold()
        for article in _ADDRESS_ARTICLES:
            if folded.startswith(article):
                forms.add(full[len(article):].strip())
        tokens = [t for t in re.split(r"\s+", full) if t]
        if len(tokens) > 1:
            # The last token: a surname, or the noun under a title.
            forms.add(tokens[-1].strip(".,"))
        if len(tokens) > 2:
            # A titled full name is ordinarily introduced without repeating
            # the title ("Captain Ysra Vale" -> "Ysra Vale").  This is still
            # ambiguity-checked below, so two Ysra Vales teach neither.
            forms.add(" ".join(tokens[-2:]).strip(".,"))
        # The 3-character floor exists to stop short LATIN fragments from
        # matching ordinary words. A short CJK name is an ordinary name, and
        # dropping it meant a whole cast could not be addressed by name.
        candidates[full] = {
            f for f in forms
            if len(f) >= 3 or _UNSPACED_SCRIPT.match(f[:1] or "")}

    # Ambiguity: a form claimed by two names identifies neither.
    seen = {}
    for name, forms in candidates.items():
        for form in forms:
            seen.setdefault(form.casefold(), set()).add(name)
    return {name: {f for f in forms if len(seen[f.casefold()]) == 1}
            for name, forms in candidates.items()}


def _address_index(roster):
    """Reverse address forms so lookup scales with a LINE, not a population."""
    forms = _address_forms(roster)
    folded, unspaced = {}, []
    max_words = 1
    for name, variants in forms.items():
        for form in variants:
            if _UNSPACED_SCRIPT.match(form[:1] or ""):
                unspaced.append((form, name))
                continue
            folded[form.casefold()] = (name, form)
            max_words = max(max_words, len(form.split()))
    return {"forms": forms, "folded": folded,
            "unspaced": unspaced, "max_words": max_words}


_SPOKEN_NAME_TOKEN_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)


def _indexed_names_in(body, index):
    tokens = _SPOKEN_NAME_TOKEN_RE.findall(str(body or ""))
    hits = set()
    maximum = min(int(index.get("max_words") or 1), len(tokens))
    lookup = index.get("folded") or {}
    for size in range(1, maximum + 1):
        for start in range(0, len(tokens) - size + 1):
            phrase = " ".join(tokens[start:start + size]).casefold()
            match = lookup.get(phrase)
            if match and _form_in(match[1], body):
                hits.add(match[0])
    # CJK address boundaries intentionally allow attached honorifics, which a
    # whitespace n-gram cannot represent.  Keep that language-aware verifier
    # for unspaced forms only; the population-scale Latin path is indexed.
    for form, name in index.get("unspaced") or ():
        if _form_in(form, body):
            hits.add(name)
    return hits


def _names_heard_in(quote, hearer_name, roster, scene, hearer_room,
                    rooms_by_name=None, address_index=None):
    """Roster names spoken inside one line, of somebody standing right there.

    THE GAP THIS CLOSES. `known` gates every identity the engine will let a
    mind use -- perception scrubs an unearned name out of a view, memory stores
    "a voice" instead of a speaker, and the narrator will not name a person to
    somebody who has not met them. It was written in exactly two places:
    `greetings.py` seeds the one greeting character against the player, and
    `commit` seeds everyone when a background presence is PROMOTED. Nothing
    recorded a name learned in play, so a character attached the ordinary way
    never entered the map and nobody ever learned anybody by being told.

    Measured over the corpus before this: 19 of 42 played stories held fewer
    recognitions than a fully-acquainted cast. Chat 59 -- 162 turns, two cast,
    a mother and her daughter -- held ONE directed pair, so every beat scrubbed
    both names out of both views. The failure that surfaces is not a missing
    name but a wrong one: a view with one surviving name and one anonymous body
    invites the model to join them, and the Doctor answered a question the
    player asked as though Tamamo had asked it.

    THE RULE. A name is learned when it is SPOKEN in your hearing and the
    person it names is in the room with you. That is the ordinary way people
    learn names, it needs no model call, and it rides a channel the firewall
    already governs -- the caller passes only lines this hearer's own view
    received.

    Two refusals, both of which keep this from becoming a leak:

      * The named person must be PRESENT and in the hearer's room. Hearing
        about somebody absent teaches you a name, not a face, and letting it
        through would license recognising a stranger who walks in later.
      * Your own name teaches you nothing, and a speaker who says a name
        already knew it.
    """
    body = str(quote or "")
    if not body:
        return []
    forms = ((address_index or {}).get("forms")
             if address_index else _address_forms(roster))
    indexed_hits = (_indexed_names_in(body, address_index)
                    if address_index else None)
    learned = []
    for name in roster:
        candidate = str(name or "").strip()
        if not candidate or candidate == hearer_name:
            continue
        if indexed_hits is not None:
            mentioned = candidate in indexed_hits
        else:
            mentioned = any(
                _form_in(form, body) for form in forms.get(candidate, ()))
        if not mentioned:
            continue
        # Present, and here. `_room_of` resolves through the scene's own
        # subject identity, so a body recorded under an entity id still
        # matches the display name the line used.
        named_room = ((rooms_by_name or {}).get(candidate)
                      or (_room_of(scene, candidate) if scene else None))
        if not named_room or (hearer_room and named_room != hearer_room):
            continue
        learned.append(candidate)
    return learned


def charter_recognition_projection(cid, frame_id=None):
    """Every Charter body's display name, the formal variants that name that
    same body, and the room it stands in.

    THE POPULATION THE RECOGNITION LEDGER COULD NOT SEE. A Charter body is a
    real, placed identity that is absent from `chat_chars` by construction, so
    any roster built from the cast answers "is this somebody" with NO for a
    person standing in the room. `commit_memory` grew a copy of this block so
    that a name learned by HEARING could name one; `commit_mapping`, which
    writes the same ledger from an authored introduction, kept the cast-only
    answer. Two writers of one map, disagreeing about who exists.

    Measured on chat 98 (40 turns): turn 16 emitted five `ok` introductions,
    every one of them naming a Charter body -- including the reverse edge that
    would have let one of them use the player's name -- and every one was
    dropped unresolved. After forty turns no Charter body held a row in
    `known` at all, so `_presence_recognizes` returned the empty set on every
    beat and the player was "the unfamiliar person" to a man who had spoken to
    her twice.

    Carries no private institutional state: display name, formal aliases and
    place are the whole projection. That is what makes it safe to resolve a
    model-authored name against -- the roster answers existence, and every
    caller still asks its own question about presence.
    """
    from world.charter_runtime import charter_speaker_records
    names, rooms, aliases = [], {}, {}
    for speaker in charter_speaker_records(cid, frame_id=frame_id):
        name = str(speaker.get("name") or "").strip()
        if not name:
            continue
        if name not in names:
            names.append(name)
        rooms[name] = str(speaker.get("place") or "")
        variants = [str(value).strip()
                    for value in (speaker.get("aliases") or [name])
                    if str(value or "").strip()]
        aliases[name] = list(dict.fromkeys(variants))
    return {"names": names, "rooms": rooms, "aliases": aliases}


def _known_name_roster(chat, cast):
    """Exact display names perception.py's recognition check requires:
    known[perceiver_name] must contain the OTHER actor's exact name string
    for `actor_name in recognized_sources` to ever match. The persona/player
    name and every cast member's character_name() output are the only
    strings that check will ever compare against.

    PRESENCE, NOT EXISTENCE, and deliberately so. `_registered_name_roster`
    below answers the other question. They are two functions rather than one
    function with a flag because a flag has a default and a default is a thing
    to forget -- and the short, obvious name belongs to the narrow one, so the
    lazy call is the safe call.

    This one is safe to ENUMERATE. The wide one is not: `promote_background_
    character` iterates a roster straight into the `known` recognition map,
    and nothing downstream ever re-checks that write.
    """
    from story.scene import persona_of
    pers = persona_of(chat)
    roster = []
    if isinstance(pers, dict):
        name = pers.get("identity", {}).get("name")
        if name:
            roster.append(name)
    for row in cast:
        roster.append(character_name_from_text(row["sheet"]))
    return roster


def _registered_name_roster(chat, cast):
    """Everyone the STORY knows about, present or not -- the existence answer.

    MEMBERSHIP ONLY. Test strings against it; never iterate it into anything a
    model reads or a table stores. Six of the eight roster call sites only ask
    "is this string somebody?", and for those, widening is either harmless or
    an outright repair -- every exclusion guard gets stronger, including the
    one that stops a registered character being handed to the background
    manager as furniture.

    Why it exists: `chat_chars.status` was answering three questions at once --
    does this person exist, are they in the scene, should we spend a model call
    on them. Reading the presence answer as the existence answer meant a
    dormant character could be named by nobody. Measured on chat 34: one turn
    emitted four `ok` introductions and exactly one survived, the only pair
    where both names were active.
    """
    from story.scene import extant_cast
    roster = list(_known_name_roster(chat, cast))
    try:
        chat_id = chat["id"]
    except (TypeError, KeyError, IndexError):
        return roster
    for row in extant_cast(chat_id) or []:
        name = character_name_from_text(row["sheet"])
        if name and name not in roster:
            roster.append(name)
    return roster

def recognition_roster(cid, chat, *, exclude_char_id=None):
    """The names a newly attached member could be given recognition OF: the
    player plus every active cast member, in the exact spelling perception's
    recognition check compares against. `exclude_char_id` drops the arriving
    member's own row, since nobody is seeded against themselves.
    """
    clause = "" if exclude_char_id is None else " AND ch.id!=?"
    params = (cid,) if exclude_char_id is None else (cid, exclude_char_id)
    cast_rows = q(
        "SELECT COALESCE(cc.sheet,ch.sheet) AS sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        f"WHERE cc.chat_id=? AND cc.status='active'{clause}", params)
    return _known_name_roster(chat, cast_rows)


def seed_mutual_recognition(cid, name, others):
    """THE ONLY WRITER that establishes recognition when a cast membership is
    created. Closes `name` against each of `others` in both directions, and is
    idempotent, so re-attaching cannot double an edge.

    RECOGNITION IS A CHANNEL and every edge written here asserts one, which is
    why this takes the roster instead of deciding it: the caller states whom
    this person legitimately already knows, and a caller with no answer must
    not call. Perception subtracts against `known`, so a membership with no
    entry renders as "the unfamiliar person" -- a real and valuable opening
    when it was authored, and chat 95's nine turns of the player failing to
    recognise their own commanding officer when it was not.

    RECOGNITION IS A RELATION OVER A ROSTER, not a relation to the player.
    Both seeding sites that predate this were shaped `{player: [char], char:
    [player]}` because the attach unit was one character meeting one persona,
    so no caller could express that two arrivals already know each other;
    `promote_background_character` reached past that shape by arguing from the
    fiction (she was in the scene the whole time) rather than from any rule.
    """
    if not name:
        return
    known = wget(cid, "known", {})
    known.setdefault(name, [])
    for other in others:
        if not other or other == name:
            continue
        if other not in known[name]:
            known[name].append(other)
        known.setdefault(other, [])
        if name not in known[other]:
            known[other].append(name)
    wset(cid, "known", known)


def _resolve_roster_name(value, roster, address_index=None):
    """mapping_commit's prompt allows 'who'/'learns' to be 'a name or brief
    descriptor' -- free text like 'Dana Osei -- supply pilot, claims three
    days of unanswered radio contact' has been observed live, instead of the
    bare exact name perception.py's recognition check requires. Resolve to
    the roster's canonical spelling; if it doesn't resolve to anyone in the
    roster, drop it rather than write a value that can never match and would
    permanently leave that perceiver unable to recognize anyone.

    THREE READINGS, NARROWEST FIRST, and the middle one is the repair. Exact
    equality, then the ADDRESS INDEX -- the same `_address_forms` machinery
    that decides whether a name spoken aloud was heard -- then the raw
    substring test that was once the only fallback.

    The index is here because the engine held two answers to one question.
    `_names_heard_in` knows a surname, an honorific and a titled variant all
    name the same person; this function knew only `casefold` equality and
    containment, so a value that WRAPS a roster name in a title resolved to
    nobody. Measured on chat 98 turn 1: `{"who": "Data", "learns":
    "Lieutenant Oyelaran"}` and two identical rows for the other two officers
    present, all three `ok`, all three dropped, because "Sabine Oyelaran" is
    not a substring of "Lieutenant Oyelaran". A person addressed by rank is
    the ordinary case in any fiction with ranks, titles, honorifics or
    professions, and it was the one reading this could not make.

    The index refuses an AMBIGUOUS value -- a form two roster names share
    identifies neither (`_address_forms` already drops those), and text that
    names two different people is not one person's name. The substring pass
    below returns the first roster hit and so cannot make that distinction,
    which is the reason it runs last rather than first.
    """
    text = str(value or "").strip()
    if not text:
        return None
    for name in roster:
        if text.casefold() == name.casefold():
            return name
    if address_index:
        hits = _indexed_names_in(text, address_index)
        if len(hits) == 1:
            return next(iter(hits))
        if hits:
            return None
    for name in roster:
        if name.casefold() in text.casefold():
            return name
    return None

# Filler tokens ignored when reducing an entity id / display name to its
# canonical token key ("ferry_tamsin" vs "tamsin_ferry_entity" must meet).
_GENERIC_ID_TOKENS = {"the", "a", "an", "entity", "obj", "object"}


def _canonical_token_key(text):
    tokens = [t for t in normalize_room_id(str(text or "")).split("_")
              if t and t not in _GENERIC_ID_TOKENS]
    return "_".join(sorted(tokens))


def _entity_alias_map(cid):
    """{normalized alias/name/id (slug AND sorted-token key): canonical
    entity_id} for this chat's live entities, from world_entities plus the
    current scene -- so a book proposal anchored to an ALIAS of a vehicle
    ('tamsin_ferry_entity' for 'ferry_tamsin') resolves to the same
    canonical entity as the book that already tracks it."""
    amap = {}

    def register(names, own_id):
        keys = []
        for value in names:
            value = str(value or "").strip()
            if not value:
                continue
            for key in (normalize_room_id(value),
                        _canonical_token_key(value)):
                if key and key not in keys:
                    keys.append(key)
        # Union semantics: if ANY of this entity's keys already resolves
        # to an earlier entity, this row is (for dedup purposes) another
        # spelling of THAT entity -- its own id inherits that canonical
        # rather than becoming its own. Row order is the deterministic
        # tiebreak (world_entities first, insertion order).
        canonical = next((amap[k] for k in keys if k in amap), own_id)
        for key in keys:
            amap.setdefault(key, canonical)

    # No `retired_turn_id IS NULL` filter: the projection has no retirement.
    # A removed entity's row is DELETED with the blob it projects, so the
    # filter excluded nothing and implied a row state that cannot occur --
    # see `test_the_entity_projection_never_retires_a_row`.
    for row in q(
        "SELECT entity_id, name, payload FROM world_entities WHERE chat_id=?",
        (cid,),
    ):
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            payload = {}
        register([row["entity_id"], row["name"],
                  *(payload.get("aliases") or [])], row["entity_id"])
    scene = wget(cid, "scene", {}) or {}
    for eid, ent in (scene.get("entities") or {}).items():
        if isinstance(ent, dict):
            register([eid, ent.get("name"), *(ent.get("aliases") or [])],
                     str(eid))
    return amap


def _canonical_anchor(anchor, alias_map):
    if not anchor:
        return None
    return alias_map.get(normalize_room_id(anchor)) \
        or alias_map.get(_canonical_token_key(anchor)) \
        or anchor

def _room_of(scene, name):
    positions = scene.get("positions") or {}
    if name in positions:
        return positions[name]
    lname = (name or "").lower().strip()
    for k, v in positions.items():
        if k.lower().strip() == lname:
            return v
    # Script-aware: the old ASCII fold erased every non-Latin name to "",
    # so this fallback could never match one.
    norm = fold_identity_key(lname)
    if norm:
        for k, v in positions.items():
            if fold_identity_key(k) == norm:
                return v
    return None

def _normalized_fact(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
