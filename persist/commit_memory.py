"""Pre-lock memory preparation: what each mind may remember of this beat,
and the psychology/relationship/mind-model deltas riding with it.

Extracted verbatim from commit.py, which re-exports every name here. The
deferred function-body imports (agents, agents.common, scene,
place_purpose) are the existing cycle-breakers and stay deferred --
hoisting them creates a real cycle.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json, re
from core.db import wget, get_setting
from mind.memory import prepare_memories_batch, _is_empty_view
from mind import affect
from mind import psychology_runtime
from story.character_schema import (character_name, character_name_from_text,
                              character_psychology, character_interoception,
                              character_initial_active_state, effective_drive,
                              character_standing_intentions,
                              character_projects, persona_name,
                              name_boundary_pattern,
                              character_appearance as _char_appearance)
from mind.theory_of_mind import (apply_mind_model_updates, rekey_place_claims,
                            select_active_hypotheses, sheet_capacity)
from world.spatial import same_subject
from world.survival import vitals_of
from world.comfort import comfort_level
from persist.commit_common import (_clamp, _known_name_roster, _monotonic_elapsed,
                           _address_index, _names_heard_in,
                           _normalize_character_output,
                           _room_of, _stable_event_key,
                           charter_recognition_projection)
from persist.commit_place_graph import (ROUTE_CREDIT_CAP, ROUTE_CREDIT_WINDOW,
                                record_spatial_experience)
from persist.commit_background import _background_fired_reactions
from language_runtime import linguistic


def _ling(name):
    """One deterministic recognizer, from the story's own language pack.

    Same use-time read as `commit_common._form_in`'s, and for the same reason:
    two stories in different languages commit concurrently, and each must be
    judged in its own words. A pack that lacks the key raises rather than
    returning empty.
    """
    return linguistic("persist.commit_memory", name)

# ---- Memory commit ----

# How many of a character's most recent physical tells (manifest cues) are
# kept on cstate as the anti-repetition ledger fed back into the character
# payload (see agents/character.py's TELL VARIETY block).
RECENT_TELLS_CAP = 6

def _durable_dialogue_category(text):
    """Category for a quote worth keeping verbatim, or None.

    Each marker must BEGIN at a word boundary. A marker is a spoken word, and
    a word does not start in the middle of another one: bare substring
    matching made "compromised" a promise, and the live corpus proves it --
    of its 5 promise-category rows, 3 were the word "compromised" (chat 6's
    "Section C and D compromised", twice, and chat 58's "TARGETING
    COMPROMISED") against 2 genuine promises. The boundary is only required
    at the start, so inflections still match ("I promised", "she promises").
    The boundary is now IN the pattern rather than wrapped around a phrase,
    because `\b` is a rule about where an English word starts and there is no
    such boundary between a Japanese verb and its object -- a pack writes the
    anchor its own script needs. Ordered: promise before dialogue, as it was.

    tools/remember_lines.py asks the same pack and
    tests/test_remember_lines_telemetry.py holds the two in sync."""
    lowered = (text or "").lower()
    for category, markers in _ling("_DURABLE_QUOTE_MARKERS").items():
        if any(re.search(pattern, lowered) for pattern in markers):
            return category
    return None

def _cited_memory_ids(own_result):
    """Memory ids this mind used as EVIDENCE for a belief it formed this beat.

    Consequence, not popularity. Retrieval on its own never moves importance:
    a memory that gets recalled would then rank higher and get recalled more,
    which is a feedback loop wearing the word. Even citation is downstream of
    retrieval, so the loop is closed structurally instead of hoped away --
    `raise_importance` is called with `only_unrevised=True`, so a given memory
    can be lifted by citation exactly once, ever. The signal is "this turned
    out to be load-bearing at least once", which is boolean by nature.

    Bare `observations_used` deliberately does not count. Citing a memory while
    describing the beat is not the same as building a belief on it, and the
    weaker signal is the one that fires on almost every turn.

    Returns `event_key`s, because that is what a character actually cites. The
    first version of this required a numeric memory ROW id and was therefore
    dead on arrival -- across a 10-turn live run it matched nothing, while the
    handles the characters really wrote were `current`, `current:39:4`,
    `turn:2:character:39:0:action` and `event:<hash>`. The last of those IS the
    memory's `event_key` (`_stable_event_key`), and all five distinct ones
    emitted in that run resolved to a real row. The format was there the whole
    time; the reader was looking for one nothing produces.

    THE SAME MISTAKE, ONE LAYER UP. Having fixed the id format, this still read
    a single field, and measured over the beats that could have supplied any of
    them (`tools/fire_rates.py`):

        mind_model_updates evidence citing a stored memory     6 of 83
        belief_updates evidence citing a stored memory         1 of 83
        memory_effects, disposition `integrated`              74 of 83

    Importance has been revised on 9 of 6,460 memories, and that is why: the
    one signal being read is the rarest thing a character emits, while the
    field that says exactly what this function is looking for -- the character
    stating that a recalled memory changed their recognition, appraisal, choice
    or speech -- fires on 89% of eligible beats and was never consulted.

    `memory_effects` is a STRONGER consequence signal than citation, not a
    weaker one. Its prompt says in as many words: do not emit one merely
    because a row was present. `resisted` and `dismissed` do not count -- a
    memory the character pushed away did influence the beat, but recording that
    as "turned out to matter" would make importance a measure of salience-at-
    recall rather than of consequence. `only_unrevised=True` still holds the
    ceiling at one lift per memory for its whole life, so widening the inputs
    widens the population that can be lifted once, never the amount.

    `belief_updates` is included because the docstring's first line has always
    claimed it: a belief formed on a memory is the paradigm case. It contributes
    almost nothing at present, which is a fact about how models cite, not a
    reason to keep reading the wrong field.
    """
    if not isinstance(own_result, dict):
        return []
    out = set()
    for field in ("mind_model_updates", "belief_updates"):
        for update in own_result.get(field) or []:
            if not isinstance(update, dict):
                continue
            for ref in update.get("evidence") or []:
                if not isinstance(ref, dict):
                    continue
                raw = str(ref.get("event_id") or "").strip()
                # "current" and the turn:/character: handles name this beat or
                # an act within it, not a stored memory.
                if raw.startswith("event:"):
                    out.add(raw)
    for effect in own_result.get("memory_effects") or []:
        if not isinstance(effect, dict):
            continue
        if str(effect.get("disposition") or "").strip() != "integrated":
            continue
        raw = str(effect.get("memory_ref") or "").strip()
        if raw.startswith("event:"):
            out.add(raw)
    return sorted(out)


def _marked_for_memory(own_result, qbody):
    """Did this character ask to keep this line (CharacterOutput.remember_lines)?

    Matched on the quote body, loosely in both directions: a model asked to
    echo a quote will trim or extend it by a word, and rejecting the mark over
    that would make the feature depend on transcription rather than intent.
    Loose matching is safe HERE and would not be elsewhere -- the caller has
    already proved this quote was said this beat and reached this observer, so
    the only thing being decided is whether a line the character definitely
    heard is also one they keep.
    """
    body = " ".join(str(qbody or "").split()).casefold()
    if not body or not isinstance(own_result, dict):
        return None
    for mark in own_result.get("remember_lines") or []:
        if not isinstance(mark, dict):
            continue
        want = " ".join(str(mark.get("quote") or "").split()).casefold()
        want = _quote_body(want)
        if not want:
            continue
        if want == body or want in body or body in want:
            return mark
    return None


def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")


def _is_player(speaker, chat):
    from agents import is_player_speaker
    return is_player_speaker(speaker, chat)

def _salience_of(text):
    s = 0.45 + min(len(text or ""), 400) / 1600.0
    # Which words make a beat worth remembering is a question about words, so
    # the cue list is the pack's. Against an English-only list every memory in
    # a Japanese story scored the flat length-only floor -- not an error, just
    # a bank with no peaks in it.
    for w in _ling("_SALIENCE_CUES"):
        if w in (text or "").lower():
            s += 0.08
    return round(min(s, 0.95), 3)


def _own_sequence_memory(seq):
    """Render a character's own conduct as grammatical, chronological first
    person: ``I said 'X.' Then I tried to Y.``

    This is the ONLY durable record of what a mind itself said and did. The
    witnessed episode cannot carry it: deterministic perception structurally
    excludes a mind's own speech and acts from its own view (`speaker == name`
    / `actor == name` skips in `agents/perception.py`, and
    `_strip_self_narration` above them), which is the firewall working, not a
    gap in it. So the wording here is decision-framed on purpose -- "I said",
    "I tried to" -- an attempt beside the perceived outcome, never a second
    resolved event competing with it. The old ``I chose to attempted '...'``
    construction is what actually replayed an act as though it were a second
    happening; preserve order, and never cut a gist midway through an act.
    """
    clauses = []
    for event in (seq or []):
        if not isinstance(event, dict):
            continue
        if event.get("type") == "speech" and str(event.get("text") or "").strip():
            spoken = str(event["text"]).strip()
            clauses.append(
                f"I said {spoken!r}" + ("" if spoken[-1] in ".!?" else "."))
        elif (event.get("type") == "communication"
              and str(event.get("content") or "").strip()):
            act = str(event.get("act") or "communicate").strip().casefold()
            past = {
                "ask": "asked", "explain": "explained", "report": "reported",
                "tell": "told", "warn": "warned", "request": "requested",
                "offer": "offered", "instruct": "instructed",
                "reassure": "reassured", "promise": "promised",
                "admit": "admitted", "answer": "answered",
                "clarify": "clarified", "inform": "informed",
                "say": "said",
            }.get(act, "communicated")
            clauses.append(
                f"I {past} {str(event['content']).strip().rstrip('.')}.")
        elif event.get("type") == "action" and str(event.get("attempt") or "").strip():
            clauses.append(f"I tried to {str(event['attempt']).strip().rstrip('.')}.")
    if not clauses:
        return "", ""
    content = " Then ".join(clauses)
    gist_parts = []
    for clause in clauses:
        candidate = " Then ".join(gist_parts + [clause])
        if len(candidate) > 240:
            break
        gist_parts.append(clause)
    gist = " Then ".join(gist_parts) if gist_parts else clauses[0][:239].rstrip() + "…"
    return content, gist


def _inference_memory_text(claim, about="", confidence=0.5, evidence=""):
    """Voice a theory as this mind's theory, not an objective dossier fact.

    The row remains ``provenance: inferred`` structurally, but its content is
    also handed directly to the character agent. A bare third-person claim
    beside first-person episodes reads as omniscient fact before the model
    ever sees the provenance label. Confidence chooses ordinary epistemic
    language; evidence remains something *I based it on*, never an objective
    ``Evidence:`` appendix.
    """
    claim = str(claim or "").strip().rstrip(".")
    about = str(about or "").strip()
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    names_subject = bool(about) and about.casefold() in claim.casefold()
    if confidence >= 0.7:
        text = (f"I concluded that {claim}." if names_subject or not about
                else f"I concluded this about {about}: {claim}.")
    elif confidence >= 0.4:
        text = (f"I suspected that {claim}." if names_subject or not about
                else f"I suspected this about {about}: {claim}.")
    else:
        text = (f"I wondered whether {claim}." if names_subject or not about
                else f"I wondered whether this was true of {about}: {claim}.")
    evidence = str(evidence or "").strip().rstrip(".")
    if evidence:
        text += f" I based that on: {evidence}."
    return text


def _intent_names_term(text, term):
    """Does this intention's own text NAME this thing?

    The lexical half of the world-closed floor (`affect.settle_intent_world_anchors`),
    supplied as a callable for the same reason `evidence_ok` is: `mind.affect`
    cannot import `story.character_schema`, which imports `mind`.

    `name_boundary_pattern` rather than `\\b`: a word boundary asserts a
    transition between word and non-word characters, which only describes
    scripts that space their words, so a kana-named party or station never
    matched and the guard failed open with no warning -- the same failure
    `director_floors`' clause attribution documents.

    A term recorded under a two-word display name is also tried by its first
    token, because a text routinely calls a party by given name alone.

    The possessive guard is the distinction that matters: a station word whose
    immediate left context is a possessive names the OTHER party's anatomy,
    not the station of the subject's own standing relation, and reading the
    first as the second would anchor an aim to a place it never named.
    """
    text = str(text or "")
    term = str(term or "").strip()
    if not text or not term:
        return False
    low = text.casefold()
    parts = term.split()
    cands = [term.casefold()]
    if len(parts) > 1:
        cands.append(parts[0].casefold())
    guard = _ling("_STATION_POSSESSED_BEFORE")
    for cand in cands:
        if len(cand) < 2:
            continue
        for m in re.finditer(name_boundary_pattern(cand), low):
            if guard.search(low[:m.start()]):
                continue
            return True
    return False


def _interior_relations_of(scene, cname):
    """This beat's standing interior relations in which `cname` is the CONTAINER.

    Rows of {"other", "station", "source"} for
    `affect.settle_intent_world_anchors`, read off the settled scene's contact
    ledger -- `relation: "interior"`, the container in `target`, the occupant
    in `actor`, and the region they stand in in `target_interior`, which since
    the station consolidation is re-derived every beat from the room the
    occupant actually holds rather than frozen at entry.

    The asymmetry is deliberate: only the CONTAINER's aims are closable by
    where the contained body now stands within them. The contained party may
    legitimately strive AGAINST the passage -- an aim pointing back up the
    route is blocked-but-strivable, not world-closed -- so the contained side
    is out of this floor's reach by construction.

    `source` distinguishes the two vocabularies a station can arrive in: the
    display name of an interior room this container carries ("room"), or a
    free-text ledger region ("ledger"). A station string that changed only
    because the representation changed is not the world moving, and the floor
    can only tell the difference if the difference is carried.
    """
    sc = scene if isinstance(scene, dict) else {}
    cname = str(cname or "").strip()
    if not cname:
        return []
    interiors = set()
    rooms = sc.get("rooms")
    if isinstance(rooms, dict):
        for key, room in rooms.items():
            if not isinstance(room, dict):
                continue
            parent = str(room.get("parent_entity") or "").strip()
            if not parent or not same_subject(sc, parent, cname):
                continue
            for form in (room.get("name"), key):
                form = str(form or "").strip()
                if form:
                    interiors.add(form.casefold())
    out = []
    for contact in (sc.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        if str(contact.get("relation") or "").strip().casefold() != "interior":
            continue
        if str(contact.get("target") or "").strip().casefold() != cname.casefold():
            continue
        other = str(contact.get("actor") or "").strip()
        station = str(contact.get("target_interior") or "").strip()
        if not other or not station:
            continue
        out.append({"other": other, "station": station,
                    "source": "room" if station.casefold() in interiors
                    else "ledger"})
    return out


def prepare_memory_commit(ctx, *, scene=None):
    """Build and embed all per-character memory mutations without writes."""
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    # Build a fresh list -- never mutate res["dialogue_log"], since the
    # director_resolve step/variant was already persisted before
    # background_react ran (see agents/perception.py's merge comment). The
    # deterministic backstop line is merged only for rendering there; fold
    # it into the persisted event record here too, so hearers mint dialogue
    # memories of it and it reaches _promotion_evidence.
    dlog = list(res.get("dialogue_log") or [])
    for _r in _background_fired_reactions(ctx.get("background_react")):
        dlog.append({**_r["dialogue_log_entry"], "source": "background_react"})
    views = (
        (ctx.perception_outcome or {}).get("views")
        or (ctx.perception_establish or {}).get("views")
        or {}
    )
    # IR-minted episodes (deterministic composer, PERCEPTION_NO_LLM): when
    # perception composed the views, it also minted each character's episode
    # directly from the percept IR -- first person, event-bearing content
    # first, typed entities -- instead of the second-person view prose. A
    # composed "" is a NON-EVENT (all standing state, nothing changed) and
    # mints nothing; absent keys fall back to the view exactly as before.
    _composed_episodes = (ctx.perception_outcome or {}).get("episodes")
    if not isinstance(_composed_episodes, dict):
        _composed_episodes = None
    _composed_episode_meta = (
        (ctx.perception_outcome or {}).get("episode_meta") or {}
        if _composed_episodes is not None else {}
    )
    est = ctx.director_establish
    sc = scene if scene is not None else (wget(cid, "scene", {}) or {})
    pending_memories = []
    state_updates = []
    # Names learned by hearing them said, accumulated per hearer and applied
    # by commit_memories inside the transaction -- this function runs BEFORE
    # the write lock and must not write. See _names_heard_in.
    _name_roster = _known_name_roster(chat, ctx.cast)
    # Charter bodies are real co-located identities even before promotion.
    # They are absent from chat_chars by design, so the legacy cast-only
    # roster made it impossible for either a character or the player to learn
    # a Charter name they plainly heard.  The runtime projection contains no
    # private institutional state: only display name and physical place.
    _charter_rooms = {}
    _charter_aliases = {}
    try:
        _charter = charter_recognition_projection(cid, ctx.turn.frame_id)
    except Exception as exc:
        ctx.add_warning(f"Charter recognition roster skipped: {exc}")
    else:
        for _speaker_name in _charter["names"]:
            if _speaker_name not in _name_roster:
                _name_roster.append(_speaker_name)
        _charter_rooms = _charter["rooms"]
        _charter_aliases = _charter["aliases"]
    _name_address_index = _address_index(_name_roster)
    _names_learned = {}

    # The persona has no memory row and therefore never entered the character
    # loop below.  Learn through the same delivered-view proof: an exact line
    # must be present in this player's own view, and the named body must be in
    # the same room.  Additional human players use their own view keys.
    from story.scene import persona_of as _persona_for_recognition
    _primary_name = persona_name(_persona_for_recognition(chat))
    _human_hearers = [("player", _primary_name)]
    for _extra in (ctx.extra_players or []):
        _human_hearers.append((
            f"extra:{_extra.get('persona_id')}",
            str(_extra.get("name") or "").strip()))
    _known_before = wget(cid, "known", {}) or {}
    for _view_key, _hearer_name in _human_hearers:
        _view = str(views.get(_view_key) or "")
        if not _view or not _hearer_name:
            continue
        _hearer_room = _room_of(sc, _hearer_name)
        _already = set(_known_before.get(_hearer_name) or [])
        for _line in dlog:
            _quote = str((_line or {}).get("exact_quote") or "").strip()
            _qbody = _quote_body(_quote)
            if not _qbody or (_quote not in _view and _qbody not in _view):
                continue
            for _learned in _names_heard_in(
                    _qbody, _hearer_name, _name_roster, sc, _hearer_room,
                    rooms_by_name=_charter_rooms,
                    address_index=_name_address_index):
                if _learned not in _already:
                    for _alias in _charter_aliases.get(
                            _learned, [_learned]):
                        if _alias not in _already:
                            _already.add(_alias)
                            _names_learned.setdefault(
                                _hearer_name, []).append(_alias)
    relationship_ops = []
    belief_reconciles = []
    memory_disputes = []
    importance_bumps = []
    _clock = wget(
        cid, "simulation_clock",
        {"elapsed_seconds": 0.0, "display": "now"},
    ) or {}
    _time_diff = ((res.get("state_diff") or {}).get("time")
                  if isinstance(res.get("state_diff"), dict) else None)
    # The same monotonic read as the scene commit's, from the same helper.
    # This site read the raw `end_seconds` for two releases after the clock
    # itself was guarded, so a backwards beat stamped affect decay, strain
    # windows and belief provenance with a clock the scene commit had just
    # refused to store.
    #
    # UNCONDITIONALLY, and the guard that used to stand here IS the case it
    # was hiding. `if isinstance(_time_diff, dict)` sent every beat whose
    # time block was absent -- 130 of 2,614 resolved turns, measured
    # 2026-08-25 -- to the raw previous clock, which is precisely the beat
    # the floor exists to charge. `read_time_diff` has always tolerated a
    # non-dict, so the guard bought nothing and cost the silent beat.
    _clock_seconds, _ = _monotonic_elapsed(
        _clock, _time_diff, floor=bool(ctx.director_resolve))

    # Loop-invariant inputs to the place-claim rekey below, hoisted: the scene
    # rooms, the cast roster, and the persona do not change while this loop
    # runs, but they were being rebuilt (a full room walk plus a name
    # resolution per cast member) inside EVERY iteration that carried
    # mind_model_updates -- O(cast^2) name derivations on a full table.
    from story.scene import persona_of as _persona_of
    _rekey_place_names = [
        str((room or {}).get("name") or rid)
        for rid, room in (sc.get("rooms") or {}).items()
    ]
    _rekey_protected = [character_name_from_text(_r["sheet"])
                        for _r in ctx.cast]
    _rekey_protected.append(persona_name(_persona_of(chat)))

    for char_row in ctx.cast:
        ccid = char_row["id"]
        sh = json.loads(char_row["sheet"])
        st = json.loads(char_row["cstate"] or "{}")
        v = views.get(str(ccid))
        episode_content = ""
        _episode_entities = []
        _episode_gist = ""
        # Side records (durable quotes) are emitted after the coherent episode
        # row so storage order mirrors their role: event first, annotations
        # second.  They remain separately retrievable by provenance.
        side_memories = []
        cname = character_name(sh)
        char_room = _room_of(sc, cname)
        room_data = (sc.get("rooms") or {}).get(char_room, {})
        room_name = room_data.get("name") or char_room or ""
        # BOTH LOOPS, MERGED. The interaction loop merges its rounds into
        # `ctx.character_results`; the reaction loop writes to
        # `ctx.reaction_results` and nothing here ever read it, so everything
        # a REACTING mind worked out was dropped -- silently, because the
        # appliers below were handed empty lists and had nothing to warn
        # about.
        #
        # Measured across the 82 stored reaction beats in the corpus: every
        # single one carried interior content that never committed -- 159
        # mind_model_updates, 93 relationship_updates, 20 belief_updates, 18
        # remember_lines, 12 association_updates, and the only three project
        # adoptions the engine has ever produced (chats 70/71/72, one beat
        # across three branches: the Doctor committing to reach a shrine).
        # A reaction is the beat with the most immediate pressure on a
        # character, and they were forming theories about people and marking
        # things worth remembering into nothing.
        #
        # MERGED rather than chosen between, because a character can both
        # react and act in one beat, and the same union `_merge_character_
        # results` already performs across micro-rounds is the right one
        # here: accumulating lists combine, latest scalar state wins.
        from agents.common import _merge_character_results
        own_result = _merge_character_results(
            ctx.reaction_results.get(ccid),
            ctx.character_results.get(ccid)) or {}
        own_result = _normalize_character_output(own_result)
        # Place claims are re-keyed onto their place ONCE, up here, before
        # ANYTHING reads mind_model_updates. The inference memory minted for a
        # claim (below) and the hypothesis it is merged under (further down,
        # via apply_mind_model_updates) must share one subject key: minting
        # from the raw updates while merging the rekeyed ones stamped the
        # memory's entities[0] with a subject that never exists in
        # mind_models, so reconcile_inference_confidence could never find the
        # live hypothesis and demoted the row as abandoned from the start.
        _mm_updates = own_result.get("mind_model_updates") or []
        if _mm_updates:
            _mm_updates = rekey_place_claims(
                _mm_updates, _rekey_place_names, protected=_rekey_protected)
        active_state = own_result.get("active_state") or {}
        mood = str(active_state.get("mood") or "")
        # The character's blended surface affect this beat carries the numeric
        # valence/arousal that go with the `mood` label; without this the
        # emotional_context text was stored but valence/arousal stayed at their
        # 0.0 default on every memory (the memory editor showed them as always
        # zero). Mirror the label onto the numeric axes for this beat's memories.
        # THE MOOD THIS MEMORY WAS FORMED IN -- the character's RESOLVED affect,
        # not the self-report they opened the beat with.
        #
        # `resolve_affect` is what turns a model's proposed mood into the one
        # the character actually holds: decayed toward baseline, moved by this
        # beat's appraisal, and cross-checked against the label. It runs at the
        # psychology commit, ~500 lines below this one, so a memory minted here
        # can never see it -- it took the raw proposal instead.
        #
        # Measured across the same characters: the raw self-report averages
        # +0.773 with 0% negative, while their resolved affect averages +0.467
        # with 22% negative. The two disagree by +0.31, and only one of them is
        # a mood. Stored memories inherited the saturated one: newer stories
        # sat at a median valence of +0.85 with 4 negatives in 3,162 rows,
        # which is not an emotional axis, it is a constant -- and it silently
        # disables everything downstream that reads affect.
        #
        # The stored value is last beat's resolution, i.e. the mood the
        # character carried INTO this event. That is what encoding-time affect
        # should be: how you felt while it was happening, before the beat's own
        # appraisal moved you. The self-report is kept as the fallback for a
        # character with no resolved affect yet (their first beat).
        _surface = (((st.get("active_state") or {}).get("affect") or {})
                    .get("surface") or {})
        if not _surface:
            _surface = (active_state.get("affect") or {}).get("surface") or {}
        try:
            _mem_valence = float(_surface.get("valence") or 0.0)
            _mem_arousal = float(_surface.get("arousal") or 0.0)
        except (TypeError, ValueError):
            _mem_valence, _mem_arousal = 0.0, 0.0
        # Fallback for legacy/no-psychology turns: after equals before.  The
        # resolved appraisal below replaces these when it exists.
        _encoding_valence, _encoding_arousal = _mem_valence, _mem_arousal
        # --- Unbidden-recall ledger: the character stage proposed this beat's
        # probe on its step output (deterministic trigger state, and whether a
        # contrasting memory was surfaced); commit is the only writer of the
        # durable ledger, exactly like recent_tells. Placed BEFORE any st
        # mutation below so the previous beat's goal is still readable for
        # the same-beat "did it help" check. Nothing here ever mints a memory
        # row: a surfaced memory is context handed to the character, and only
        # what the character then DOES (speech, mind-model claims) is
        # canonical.
        _probe = own_result.get("unbidden_probe")
        if isinstance(_probe, dict):
            _led = dict(st.get("unbidden") or {})
            _probe_ref = str(_probe.get("memory_ref") or "")
            _effectful = any(
                isinstance(e, dict)
                and str(e.get("memory_ref") or "") == _probe_ref
                and str(e.get("disposition") or "").casefold()
                    not in {"", "dismissed", "ignored", "none"}
                and bool(str(e.get("changed") or "").strip())
                for e in (own_result.get("memory_effects") or []))
            _goal_before = str(((st.get("active_state") or {}).get("goal"))
                               or "")
            # The RAW emitted goal was read here to ask "did the goal move off
            # its snapshot" -- the third reader of that field the 2026-08-11
            # audit missed. The template no longer asks for it, so derive the
            # same text the psychology commit below will keep (the enacted
            # want's), with the legacy field as fallback; both sides of the
            # comparison (this and the `pending` snapshot) go through the one
            # derivation, so "moved" keeps meaning what it meant.
            from agents.common import declared_goal as _declared_goal
            _goal_now = _declared_goal(own_result)
            _pending = (_led.get("pending")
                        if isinstance(_led.get("pending"), dict) else None)
            if _pending is not None and turn.idx > int(_pending.get("turn")
                                                       or -1):
                # The beat AFTER an injection: it helped if the stuckness
                # cleared or the goal moved off its snapshot.
                _helped = (not _probe.get("stuck")
                           or _goal_now != str(_pending.get("goal") or ""))
                _outs = [o for o in (_led.get("outcomes") or [])
                         if isinstance(o, dict)]
                _outs = (_outs + [{"turn": turn.idx,
                                   "helped": bool(_helped)}])[-4:]
                _led["outcomes"] = _outs
                if (len(_outs) >= 2 and not _outs[-1]["helped"]
                        and not _outs[-2]["helped"]):
                    # Two consecutive injections that moved nothing: the
                    # character is stuck for a reason contrast cannot reach.
                    # Suppressed until the trigger is observed fully clear.
                    _led["suppressed"] = True
                _led.pop("pending", None)
            if not _probe.get("stuck"):
                _led["clear_seen"] = True
                _led["suppressed"] = False
            if _probe.get("fired") and _probe.get("memory_id") is not None:
                try:
                    _mid = int(_probe["memory_id"])
                except (TypeError, ValueError):
                    _mid = None
                if _mid is not None:
                    _led["last_turn"] = turn.idx
                    _led["last_trigger"] = str(_probe.get("trigger") or "")
                    _rids = [i for i in (_led.get("recent_ids") or [])
                             if isinstance(i, int) and i != _mid]
                    _led["recent_ids"] = (_rids + [_mid])[-8:]
                    _led["clear_seen"] = False
                    if _effectful or (_goal_now and _goal_now != _goal_before):
                        # Helped on the injection beat itself.
                        _led["outcomes"] = ([
                            o for o in (_led.get("outcomes") or [])
                            if isinstance(o, dict)]
                            + [{"turn": turn.idx, "helped": True}])[-4:]
                    else:
                        _led["pending"] = {
                            "turn": turn.idx, "goal": _goal_now,
                            **({"memory_ref": _probe_ref}
                               if _probe_ref else {})}
            _led["repeat_flag"] = bool(_probe.get("repeat_survived"))
            st["unbidden"] = _led
        if est and not v:
            room_label = char_room or "the scene"
            room_data2 = (sc.get("rooms") or {}).get(room_label, {})
            room_name2 = room_data2.get("name") or room_label
            room_desc = room_data2.get("desc") or room_data2.get("notes") or ""
            v = f"The scene opens. You are in {room_name2}." + (
                f" {room_desc}" if room_desc else ""
            )
        if v:
            # F2/P1: dialogue memory recognition gate. The speaker's
            # canonical name was stored regardless of whether the hearer
            # recognizes them, leaking identity into memory. Check the
            # hearer's known map -- if the speaker isn't recognized, store
            # an appearance-based label or "a voice" instead, and drop
            # intended_target (which also names the speaker).
            _known_map = wget(cid, "known", {}) or {}
            _hearer_known = set(_known_map.get(cname) or [])
            for d in dlog:
                spk = d.get("speaker", "")
                # The player used to be rewritten to the literal "the player"
                # here and then EXEMPTED from the recognition gate below, so a
                # character's own memory read `the player said "My Name is
                # Hinami." to Dr. Moon` -- the engine's out-of-fiction word for
                # the protagonist, inside a fictional mind, in the very memory
                # where they learned her name. 68 rows across the live corpus.
                # The player is a body in the room like any other: pass the
                # persona's real name in and let the gate decide, exactly as it
                # does for every character.
                _spk_is_player = _is_player(spk, chat)
                if _spk_is_player:
                    from story.scene import persona_of
                    spk = persona_name(persona_of(ctx.chat)) or spk
                if spk == cname:
                    continue
                # Recognition gate: the canonical name only if the hearer knows
                # the speaker. The label comes from _unknown_actor_label, the
                # same helper every perception path uses, rather than a second
                # hand-rolled copy of it -- the copy truncated at a fixed 60
                # characters and cut mid-word, and two implementations of the
                # identity floor drift apart exactly where it matters.
                if spk not in _hearer_known:
                    from agents.common import (
                        _unknown_actor_label, character_scene_keys)
                    if _spk_is_player:
                        from story.scene import persona_of
                        _spk_sheet = persona_of(ctx.chat)
                    else:
                        _spk_sheet = next(
                            (sheet for sheet in
                             (json.loads(_cr["sheet"]) for _cr in ctx.cast)
                             if character_name(sheet) == spk),
                            None)
                    spk_label = _unknown_actor_label(
                        spk,
                        _char_appearance(_spk_sheet) if _spk_sheet else None,
                        character_scene_keys(_spk_sheet)[1:] if _spk_sheet else None,
                    )
                    # This memory is HEARD. When there is no appearance to
                    # describe, _unknown_actor_label falls back to "the
                    # unfamiliar person" -- which claims the hearer saw a body.
                    # What they have is a voice.
                    if spk_label == "the unfamiliar person":
                        spk_label = "a voice"
                    tgt = None  # drop intended_target -- it names the speaker
                else:
                    spk_label = spk
                    tgt = d.get("intended_target")
                quote = d.get("exact_quote", "")
                qbody = _quote_body(quote)
                if qbody and (quote in v or qbody in v):
                    # This line reached THIS hearer's view -- the audibility
                    # question is already answered above, so a name inside it
                    # is a name they heard. See _names_heard_in.
                    for _learned in _names_heard_in(
                            qbody, cname, _name_roster, sc, char_room,
                            rooms_by_name=_charter_rooms,
                            address_index=_name_address_index):
                        if _learned not in _hearer_known:
                            for _alias in _charter_aliases.get(
                                    _learned, [_learned]):
                                if _alias not in _hearer_known:
                                    _hearer_known.add(_alias)
                                    _names_learned.setdefault(
                                        cname, []).append(_alias)
                    category = _durable_dialogue_category(qbody)
                    memory_mark = _marked_for_memory(own_result, qbody)
                    # This mind asked to keep the line. The phrase list is a
                    # floor of what ANYONE would remember; what a particular
                    # character finds durable is a fact about that character,
                    # so their own declaration is allowed to add to it -- never
                    # to remove, since the floor exists for the model that
                    # declares nothing. Bounded by everything above: the quote
                    # must have been said this beat and must have reached THIS
                    # observer's view, so a mark can only preserve something
                    # already heard.
                    if not category and memory_mark:
                        category = "dialogue"
                    if category:
                        side_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                            "turn_idx": turn.idx, "kind": "dialogue", "category": category,
                            "provenance": "heard",
                            "salience": 0.9 if category == "promise" else 0.82,
                            "content": f"I heard {spk_label} say {quote}" + (f" to {tgt}" if tgt else ""),
                            "gist": f"{spk_label}: {qbody}", "key_phrases": [qbody, spk_label],
                            "entities": [spk_label], "location": room_name,
                            "emotional_context": " — ".join(
                                p for p in (
                                    mood,
                                    ("kept because " + str(
                                        memory_mark.get("why") or "").strip())
                                    if memory_mark and str(
                                        memory_mark.get("why") or "").strip()
                                    else "",
                                ) if p),
                            "valence": _mem_valence, "arousal": _mem_arousal,
                            "event_key": _stable_event_key(
                                turn.id, ccid, "dialogue", d.get("speaker"),
                                qbody, d.get("intended_target"),
                            ),
                        })
            episode_content = v
            # IR-minted episode (see the top of this function): the composer
            # already rendered this mind's episode from the same gated,
            # fidelity-degraded percepts its view rendered -- never richer --
            # with typed entities instead of names scraped back out of prose
            # (memory.py's `_extract_entities` fallback).
            if _composed_episodes is not None and str(ccid) in _composed_episodes:
                episode_content = str(_composed_episodes.get(str(ccid)) or "")
                _meta = _composed_episode_meta.get(str(ccid)) or {}
                _episode_entities = [
                    str(e) for e in (_meta.get("entities") or [])
                    if str(e or "").strip()]
                _episode_gist = str(_meta.get("gist") or "").strip()
            # A view that says only "you are somewhere unspecified" is the
            # ABSENCE of an event, and an absence is not an episode. Minted
            # anyway, it becomes a retrievable memory carrying no information:
            # measured live, 356 rows across five stories -- 7.3% of the whole
            # bank, and a THIRD of one story's -- were the single sentence
            # "You are in an unspecified area.", all at salience 0.47, all
            # identical, all eligible to be handed to a character instead of
            # something that happened.
            #
            # It arises legitimately (an NPC off in unloaded space) and
            # illegitimately (`character_room`'s docstring calls the same
            # phrase "leaking a false empty view" from a position it could not
            # resolve). The cause does not change the remedy: either way there
            # is nothing to remember, so nothing is written. The turn still
            # happened and the turn index still records it. The composer
            # generalizes this floor upstream: a percept list that is all
            # unchanged standing state renders an EMPTY episode, so the
            # marker check below is the backstop, not the mechanism.
            if _is_empty_view(episode_content):
                episode_content = ""
        if episode_content:
            # WHY `turn.id` AND NOT A COPY-STABLE IDENTITY. The property this
            # mint is relied on for is stability across a RE-RUN, not across a
            # copy: `commit_memories` deletes the turn's rows and mints them
            # again, so the identities must come back byte-identical or every
            # summary clause citing them is stranded (`memory_summaries.
            # derive_summary_support`, and `dump_memory_summaries`'s note that
            # refs are event_keys precisely so they survive branch and
            # rollback). `turn.id` is stable across a re-run and is what a
            # branch's copied rows keep, so both hold.
            #
            # It is NOT stable across a copy -- a branched chat's rows carry
            # the source turn's id inside their key -- and that reads like a
            # defect until you look for a path it reaches. There is none: every
            # site minting from `turn.id` is entered through `commit_memories`,
            # which calls `delete_turn_memories(turn.id)` first, so nothing
            # reconciles a copied row by key. The two writers that DO reconcile
            # by key with no delete before them deliberately mint elsewhere --
            # `story/greetings.py` from a content digest, `world/offscreen.py`
            # from a chat-scoped agent key. Re-deriving this from `turn.idx`
            # was investigated and rejected: it fixes nothing reachable and
            # strands the support refs of every existing summary the first time
            # its turn is re-run. `tests/test_branch_memory_integrity.py` pins
            # both halves.
            _episode_row = {
                "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                "turn_idx": turn.idx, "kind": "episodic", "category": "episode",
                "provenance": "witnessed", "salience": _salience_of(episode_content),
                "content": episode_content, "location": room_name,
                "emotional_context": mood,
                "valence": _mem_valence, "arousal": _mem_arousal,
                "event_key": _stable_event_key(turn.id, ccid, "episode"),
            }
            if _episode_entities:
                _episode_row["entities"] = _episode_entities
            if _episode_gist:
                _episode_row["gist"] = _episode_gist
            pending_memories.append(_episode_row)
        pending_memories.extend(side_memories)
        if own_result:
            # Ponder is a private, deliberate retrieval request for the NEXT
            # character turn. The character stage removed it from the public
            # sequence, so it never becomes a world action. Consume an older
            # pending query only when this mind actually produced a committed
            # result, then optionally stage one new bounded query.
            _pending_ponder = (st.get("memory_ponder")
                               if isinstance(st.get("memory_ponder"), dict)
                               else {})
            try:
                _ponder_due = int(_pending_ponder.get("set_turn")) < turn.idx
            except (TypeError, ValueError):
                _ponder_due = False
            if _ponder_due:
                st.pop("memory_ponder", None)
            _new_ponder = (own_result.get("ponder")
                           if isinstance(own_result.get("ponder"), dict)
                           else {})
            _ponder_query = " ".join(
                str(_new_ponder.get("query") or "").split())[:240]
            _ponder_why = " ".join(
                str(_new_ponder.get("why") or "").split())[:240]
            if _ponder_query and _ponder_why:
                st["memory_ponder"] = {
                    "query": _ponder_query,
                    "why": _ponder_why,
                    "set_turn": turn.idx,
                }
                # Telemetry only, never a gate: a useful answer is allowed to
                # raise a new deliberate question immediately.
                st["last_ponder_turn"] = turn.idx
            seq = own_result.get("sequence") or []
            own_salience = float(own_result.get("salience", 0.0))
            # The bound: everything a mind SAID is durable (conversation
            # continuity is what measurably dies without it), a silent act is
            # durable only when the mind's own appraisal reached 0.7 -- idle
            # motion below that keeps its 12-turn `_recent_self_moves` window
            # and the episode of its consequences, not a row per fidget. This
            # is at most one extra row per speaking/salient character per
            # beat, beside the episode row every character already gets.
            should_store_own_acts = bool(seq) and (
                own_salience >= 0.7
                or any(event.get("type") == "speech" for event in seq)
            )
            # ALWAYS beside the episode, never instead of it. d290ca4 gated
            # this on `not episode_content`, reasoning that the view was
            # "already the coherent, resolved first-person episode" -- true
            # under model-composed perception, which wrote "You say X" into a
            # mind's own view. One day later 3a82657 made every view
            # deterministic, and the composer structurally EXCLUDES a mind's
            # own conduct from its own view (that is the firewall, and it is
            # correct) -- so the branch went unreachable and every character
            # in every story stopped remembering anything they said or did.
            # Measured live: chat 67 (pre-regression) holds 20 self rows over
            # 51 turns; chats 69-80 hold 0 over 240 turns, and chat 80's Dr.
            # Moon restated the same three propositions on five consecutive
            # beats with no memory of a promise she made on turn 5. The
            # fragmentation d290ca4 was fixing was the old "I chose to
            # attempted '...'" wording replaying an act as a second event;
            # `_own_sequence_memory`'s decision framing is that fix, and it
            # stands whether or not a view exists.
            if should_store_own_acts:
                self_content, self_gist = _own_sequence_memory(seq)
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "episodic", "category": "self",
                    "provenance": "remembered", "salience": max(0.5, own_salience),
                    "content": self_content,
                    "gist": self_gist,
                    "location": room_name, "emotional_context": mood,
                    "valence": _mem_valence, "arousal": _mem_arousal,
                    "event_key": _stable_event_key(turn.id, ccid, "own_acts"),
                })
            # The REKEYED updates (see the top of this loop body), so the
            # memory row's subject matches the key the hypothesis will live
            # under in mind_models.
            for update in _mm_updates:
                confidence = _clamp(update.get("confidence", 0.5))
                evidence = "; ".join(
                    str(item.get("fact") or "").strip()
                    for item in update.get("evidence") or []
                    if isinstance(item, dict)
                    and str(item.get("fact") or "").strip()
                )
                about = str(update.get("about_entity") or "").strip()
                claim = str(update.get("claim") or "").strip().rstrip(".")
                inference_content = _inference_memory_text(
                    claim, about, confidence, evidence)
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "inference", "category": "inference",
                    "provenance": "inferred", "salience": 0.45 + 0.3 * confidence,
                    "confidence": confidence,
                    "content": inference_content,
                    "gist": claim if len(claim) <= 240 else claim[:239].rsplit(" ", 1)[0] + "…",
                    "entities": [about] if about else [],
                    "location": room_name, "emotional_context": mood,
                    "event_key": _stable_event_key(
                        turn.id, ccid, "mind_model", update.get("about_entity"),
                        update.get("kind"), update.get("claim"),
                    ),
                })
            # --- Interior depth: deterministic floors over the model's proposed
            # active_state (goals + blended affect). All fields are optional;
            # absent ones degrade to the legacy {mood,goal}. affect.py is pure;
            # this is the single write point where the floors apply.
            if own_result.get("active_state") is not None:
                asv = own_result.get("active_state")
                if not isinstance(asv, dict):
                    asv = {"mood": str(asv), "goal": ""}
                prev_as = st.get("active_state") if isinstance(st.get("active_state"), dict) else {}
                interior = st.get("interior") if isinstance(st.get("interior"), dict) else {}
                intentions = interior.get("intentions") or []
                # How much this mind holds at once: the authored rung, narrowed
                # by one at the top of the absorption range. Read off the body
                # the character came INTO this beat with, because that is the
                # state they decided it in -- the settled figure below governs
                # the next beat, and using it here would apply a consequence of
                # the beat to the deliberation that produced it.
                _want_cap, _intent_cap = affect.capacity_caps(
                    character_psychology(sh).get("capacity"),
                    psychology_runtime.cognitive_absorption(
                        prev_as.get("hedonic"), prev_as.get("stress")))
                # Seed the character's AUTHORED standing intentions (from the
                # card's initial_state.goals) into the live list, so the model
                # can progress/close them via intent_ops and they persist and
                # evolve. Dedup by text against the CURRENT list (including any
                # already-abandoned/blocked copy), so a goal the character has
                # set aside never re-seeds. Mirrors the read-side merge in
                # agents/character._merge_standing_intentions.
                _seen_intent = {str(i.get("intent") or "").strip().casefold()
                                for i in intentions if isinstance(i, dict)}
                for _a in character_standing_intentions(sh):
                    if str(_a.get("intent") or "").strip().casefold() not in _seen_intent:
                        intentions = intentions + [_a]
                # PROJECTS (Tier 1.5): durable-but-not-eternal commitments,
                # capped at two -- see affect.apply_project_ops and
                # docs/design/DESIGN_LONG_TERM_GOALS.md. Authored ones seed from
                # the card exactly as standing intentions do, deduped
                # against live AND former so a project the character gave
                # up (with a stated reason) never silently re-seeds over
                # that decision. NOTE: _interior_out below is rebuilt from
                # scratch each beat, so both ledgers must be carried
                # through it explicitly or a beat would erase them.
                projects = [dict(p) for p in (interior.get("projects") or [])
                            if isinstance(p, dict)]
                former_projects = [
                    dict(p) for p in (interior.get("former_projects") or [])
                    if isinstance(p, dict)]
                # Deduped on ID as well as text. Text alone is not enough:
                # a project's wording can legitimately CHANGE after adoption
                # -- the maze harness appends the goal room's name the beat
                # the character first stands in it, which is the moment that
                # identifier becomes legitimately his -- and a text-keyed
                # check then stops recognising the authored source and seeds
                # a second copy of the same project. Measured live: `pa1`
                # held twice, one project occupying both slots, which defeats
                # the cap that is the entire point of the tier.
                _seen_proj = {
                    str(p.get("project") or "").strip().casefold()
                    for p in projects + former_projects}
                _seen_pids = {str(p.get("id") or "")
                              for p in projects + former_projects}
                for _p in character_projects(sh):
                    if len(projects) >= affect.PROJECT_CAP:
                        break
                    if str(_p.get("id") or "") in _seen_pids:
                        continue
                    if str(_p.get("project") or "").strip().casefold() \
                            not in _seen_proj:
                        # Seeding counts as service: the drift clock starts
                        # at the seeding beat, never at authored turn 0.
                        projects = projects + [
                            dict(_p, last_served_turn=turn.idx)]
                projects, former_projects, _pwarn = affect.apply_project_ops(
                    projects, former_projects,
                    own_result.get("project_ops") or [], turn.idx)
                for w in _pwarn:
                    ctx.add_warning(f"{cname}: project -- {w}")
                _project_ids = {str(p.get("id") or "") for p in projects}
                # Probationary vs established, as the character SAW them at
                # the start of this beat (pre-settlement, like valid_ids
                # for intentions): a probationary project weighs at
                # intention level until service establishes it.
                _probation_ids = {str(p.get("id") or "") for p in projects
                                  if p.get("probation")}
                _established_ids = _project_ids - _probation_ids
                drive = (character_psychology(sh) or {}).get("drive") or {}

                # this beat's evidence pool: resolved event + spoken lines, for
                # gating intention satisfy/abandon (light floor: cited + present).
                _ev_text = (res.get("resolved_event") or "") + " " + " ".join(
                    str(d.get("exact_quote") or "") for d in dlog)

                def _evidence_ok(op, _t=_ev_text):
                    ev = op.get("evidence") or []
                    if not ev:
                        return False
                    return any(str(e) and str(e) in _t for e in ev) or bool(op.get("why"))

                _before_status = {
                    str(i.get("id")): i.get("status")
                    for i in intentions if isinstance(i, dict)
                }
                intentions, _iwarn = affect.apply_intent_ops(
                    intentions, own_result.get("intent_ops") or [], turn.idx,
                    _evidence_ok, intent_cap=_intent_cap,
                    # Set by the character stage when this beat repeated an
                    # earlier move and the screen did not judge the repetition
                    # warranted -- i.e. the beat the engine already paid a full
                    # re-ask over. A `progress` claim on one of those does not
                    # advance the goal (affect._advance_intent).
                    barren_beat=bool(own_result.get("_barren_beat")))
                # OUTCOME FEEDBACK. Everything else in this engine revises a
                # belief by CONTRADICTION -- another claim -- never by whether
                # acting on it worked. So a character who concludes something,
                # acts, and is wrong sees that belief decay from disuse at
                # exactly the rate a correct one would, and a route that
                # demonstrably reached a goal accumulates no weight against the
                # novelty of one that has not been tried.
                #
                # An intention reaching `satisfied` is the one success signal
                # the engine can observe without trusting a bare self-report:
                # apply_intent_ops gates satisfy behind _evidence_ok, so it
                # needs on-screen cause. When one closes, the rooms walked
                # while pursuing it are credited -- their own route, no oracle
                # knowledge of whether it was the BEST way, only that it was a
                # way that worked.
                _satisfied = [
                    i for i in intentions
                    if isinstance(i, dict) and i.get("status") == "satisfied"
                    and _before_status.get(str(i.get("id"))) != "satisfied"
                ]
                if _satisfied:
                    _worked = st.get("routes_that_worked")
                    if not isinstance(_worked, dict):
                        _worked = {}
                    _since = max(
                        0, len(st.get("visited_rooms") or [])
                        - ROUTE_CREDIT_WINDOW)
                    for _r in set((st.get("visited_rooms") or [])[_since:]):
                        _worked[_r] = min(
                            ROUTE_CREDIT_CAP, int(_worked.get(_r, 0)) + 1)
                    st["routes_that_worked"] = _worked
                for w in _iwarn:
                    ctx.add_warning(f"{cname}: intention -- {w}")
                # A goal the world has invalidated must be closable by the
                # world. `nonviable` is the right verb and only the character
                # may emit it -- which is exactly the mind that can no longer
                # see the goal is closed. Chat 88 char 72 i6 named a station
                # the occupant left at turn 54; four commit warnings fired
                # (54/55/58/64) and nothing acted on any of them, so it was
                # still `active` at turn 67 with every want serving it.
                #
                # `sc` is the SETTLED scene for this beat (commit.py passes
                # prepare_scene_commit's output), so the ledger this reads is
                # the one the turn actually committed. The floor runs AFTER
                # apply_intent_ops, so it has the last word over a
                # grind-revival, and BEFORE steering/project_boundary, so the
                # closed state steers its collapse beat once and the existing
                # "your task closed this beat" review invites the successor
                # with no new machinery.
                #
                # The whole interior block runs only on beats this mind
                # emitted active_state, so a gated container closes late
                # rather than never -- as every other interior floor does.
                intentions, _wclose = affect.settle_intent_world_anchors(
                    intentions, _interior_relations_of(sc, cname), turn.idx,
                    _intent_names_term)
                for w in _wclose:
                    ctx.add_warning(f"{cname}: intention -- {w}")
                _steering = affect.steering_intent_ids(intentions, turn.idx)
                # A known id is not automatically a current purpose. Dormant,
                # blocked, satisfied and abandoned intentions remain in the
                # ledger for continuity, but cannot legitimize a fresh want by
                # appearing in `serves`. `_steering` deliberately includes an
                # intention closed THIS beat (last_progress_turn == turn.idx),
                # so a payoff is not demoted because of state the character
                # could not have seen when deciding. A goal already spent at
                # the START of the beat is absent and normalizes to situational.

                def _priority(serves, _ids=_steering, _intents=intentions,
                              _projs=projects, _pids=_established_ids,
                              _probs=_probation_ids):
                    # Models emit serves as "intention:<id-or-text>" or
                    # "project:<id-or-text>"; resolve to the bare id so a
                    # goal-serving impact scores at its tier's priority, not
                    # the situational default. An ESTABLISHED project weighs
                    # at DRIVE priority (1.0) -- the 1.0-vs-0.8 loss is the
                    # measured failure the project tier exists to close; a
                    # probationary one at intention priority (0.8) -- drive
                    # weight is earned by service, never by adoption.
                    serves = affect.normalize_serves(serves, _intents, _projs)
                    return affect.serves_priority(str(serves), _ids, _pids,
                                                  _probs)

                wants, enacted, suppressed = affect.normalize_wants(
                    asv.get("wants") or [], _steering | _project_ids,
                    want_cap=_want_cap)

                appraisal_input = dict(own_result.get("appraisal") or {})
                # Past experience may change familiarity, expectation and
                # perceived coping resources. It may also produce a mild body
                # echo or prime threat detection, but may not manufacture
                # current pain/pleasure, a present threat, or a goal event.
                # Apply every contribution only through the separately
                # grounded memory_modulation lane.
                _mod = appraisal_input.get("memory_modulation")
                _memory_echo = {}
                if isinstance(_mod, dict) and _mod.get("evidence"):
                    try:
                        _familiarity = max(
                            0.0, min(1.0, float(_mod.get("familiarity") or 0.0)))
                        _coping_effect = max(
                            -1.0, min(1.0, float(
                                _mod.get("coping_effect") or 0.0)))
                        _somatic_echo = max(
                            -1.0, min(1.0, float(
                                _mod.get("somatic_echo") or 0.0)))
                        _threat_bias = max(
                            0.0, min(1.0, float(
                                _mod.get("threat_bias") or 0.0)))
                    except (TypeError, ValueError):
                        (_familiarity, _coping_effect,
                         _somatic_echo, _threat_bias) = 0.0, 0.0, 0.0, 0.0
                    appraisal_input["novelty"] = max(
                        0.0, min(1.0,
                                 float(appraisal_input.get("novelty") or 0.0)
                                 * (1.0 - 0.35 * _familiarity)))
                    appraisal_input["coping_potential"] = max(
                        0.0, min(1.0,
                                 float(appraisal_input.get(
                                     "coping_potential") or 0.5)
                                 + 0.25 * _coping_effect))
                    # The model reports a normalized tendency; the engine
                    # decides how much reaches live state. One recalled beat
                    # can move either axis by at most 0.2, and the result stays
                    # explicitly labelled remembered_past.
                    _memory_echo = {
                        "somatic": round(0.2 * _somatic_echo, 4),
                        "threat_bias": round(0.2 * _threat_bias, 4),
                        "why": str(_mod.get("why") or "")[:240],
                        "source_refs": [
                            str(e.get("event_id") or "")
                            for e in (_mod.get("evidence") or [])
                            if isinstance(e, dict) and e.get("event_id")
                        ],
                        "temporal_source": "remembered_past",
                    }
                    appraisal_input["memory_echo"] = _memory_echo
                proposed_hedonic = (
                    asv.get("hedonic") if isinstance(asv.get("hedonic"), dict)
                    else {}
                )
                # The appetite this body carried INTO the beat, so appraisal can
                # tell a goal that completed from a drive that is being fed --
                # a confirmed win on an unreleased drive is not a reason to
                # stand down. Read before resolve_hedonic recomputes it, and
                # zeroed the moment the character declares the release, which
                # is the beat satisfaction becomes true.
                _prev_hedonic = (prev_as.get("hedonic")
                                 if isinstance(prev_as.get("hedonic"), dict)
                                 else {})
                _unresolved_drive = (
                    0.0 if bool(proposed_hedonic.get("released"))
                    else _prev_hedonic.get("charge") or 0.0
                )
                appraisal_out = affect.appraise(
                    appraisal_input.get("goal_impacts") or [], _priority,
                    dimensions=appraisal_input,
                    unresolved_drive=_unresolved_drive,
                )
                prev_affect = prev_as.get("affect") if isinstance(prev_as, dict) else None
                baseline = ((prev_affect or {}).get("baseline")
                            or character_initial_active_state(sh)["affect"]["baseline"])
                turns_since = max(1, turn.idx - int(prev_as.get("affect_turn") or (turn.idx - 1)))
                elapsed_units = psychology_runtime.elapsed_psych_units(
                    prev_as.get("affect_seconds"), _clock_seconds, turns_since)
                # Surface habituation (affect.py's _HABITUATION_* block):
                # default off, the shipped behaviour byte-for-byte. Switched
                # per install by the `affect_habituation` setting, read here
                # because affect.py deliberately imports no db. The release
                # flag is the character's own declared hedonic discharge --
                # the same one resolve_hedonic below receives -- which is
                # what lets a climax land uncompressed while the plateau
                # before it settles.
                _habituate = str(
                    get_setting("affect_habituation") or ""
                ).strip().casefold() in ("1", "on", "true")
                new_affect = affect.resolve_affect(
                    prev_affect, appraisal_out, baseline, elapsed_units,
                    proposed=asv.get("affect") or asv.get("mood"),
                    habituate=_habituate,
                    released=bool(proposed_hedonic.get("released")))
                _encoded_surface = new_affect.get("surface") or {}
                _encoding_valence = float(
                    _encoded_surface.get("valence") or 0.0)
                _encoding_arousal = float(
                    _encoded_surface.get("arousal") or 0.0)
                body_state = vitals_of(sc, cname)
                # World-side comfort, from the settled scene: what this body
                # is verifiably against (station/contact/posture, closed
                # vocabulary). Feeds the pleasure LEVEL floor only -- by
                # construction it never reaches the charge term, because a
                # warm bench is a resolved state, not an unresolved drive.
                _comfort, _comfort_src = comfort_level(sc, cname)
                new_hedonic = psychology_runtime.resolve_hedonic(
                    prev_as.get("hedonic"), appraisal_out,
                    character_interoception(sh), body_state, elapsed_units,
                    # Discharging an accumulated drive is the character's own
                    # event to have, so the declaration is theirs; how it built
                    # up in the first place stays the runtime's.
                    released=bool(proposed_hedonic.get("released")),
                    ambient_comfort=_comfort, comfort_source=_comfort_src,
                )
                proposed_stress = (
                    asv.get("stress") if isinstance(asv.get("stress"), dict) else {}
                )
                new_stress = psychology_runtime.resolve_stress(
                    prev_as.get("stress"), appraisal_out,
                    (character_psychology(sh) or {}).get("stress_profile") or {},
                    new_hedonic, elapsed_units,
                    proposed_mode=proposed_stress.get("coping_mode"),
                    # Explicit, because this is the argument whose absence
                    # held 55% of the strain weight at zero for the life of
                    # the feature: `appraise` returns the normalised list as
                    # `impacts`, and `resolve_stress` was reading
                    # `goal_impacts`, a key nothing writes.
                    goal_impacts=appraisal_out.get("impacts") or [],
                )

                # Leak tripwire: this character's OWN speech must not state a
                # suppressed want / the undercurrent / an unenacted intention.
                own_speech = [str(d.get("exact_quote") or "") for d in dlog
                              if d.get("speaker") == cname]
                for w in affect.leak_scan(own_speech, wants,
                                          new_affect.get("undercurrent"), intentions):
                    ctx.add_warning(f"{cname}: interior leak -- {w}")

                surface = new_affect.get("surface") or {}
                # The goal slot IS the enacted want's text -- measured on 401
                # recent-era calls: this branch took the want on 99.0% of
                # them, and the emitted goal string it used to fall back on
                # matched that want only 16.2% of the time, so the template
                # stopped asking for it. The fallback chain ends at the
                # PREVIOUS goal, never at empty: a beat with malformed wants
                # is the 1% case, and blanking the slot there silently killed
                # a standing aim -- goal routing, tenure and the unbidden
                # ledger all read this slot, and "" is a decision the
                # character never made. A legacy provider still emitting
                # asv.goal keeps its say first.
                enacted_goal = (wants[enacted]["want"]
                                if (wants and enacted is not None
                                    and 0 <= enacted < len(wants))
                                else asv.get("goal")
                                or prev_as.get("goal") or "")
                st["active_state"] = {
                    "mood": surface.get("label") or str(asv.get("mood") or ""),
                    "goal": str(enacted_goal or ""),
                    # canonical valence/arousal, projected to the flat legacy keys.
                    "valence": float(surface.get("valence") or 0.0),
                    "arousal": float(surface.get("arousal") or 0.0),
                    "affect": new_affect,
                    "wants": wants,
                    "enacted_want": enacted,
                    "suppressed_want": suppressed,
                    "affect_turn": turn.idx,
                    "affect_seconds": _clock_seconds,
                    "stress": new_stress,
                    "hedonic": new_hedonic,
                    # One-beat, source-labelled state. Deliberately separate
                    # from hedonic pain/pleasure and from current observations.
                    "memory_echo": _memory_echo,
                    "active_concerns": (
                        asv.get("active_concerns")
                        or prev_as.get("active_concerns")
                        or character_initial_active_state(sh).get("active_concerns")
                        or []
                    ),
                }
                # --- Project service ledger + boundary review (Tier 1.5).
                # A held project stopped failing by being outranked and
                # started failing by being FORGOTTEN (A15 run 5: pa1 held at
                # weight 1.0, twenty beats in, nothing emitted serving it).
                # Two deterministic facts close that gap: last_served_turn
                # per project (read back as `adrift` in the payload), and a
                # one-beat review flag when a boundary the engine can
                # actually see has passed. Facts only -- nothing here writes
                # a want or applies an op.
                from agents.common import character_room as _char_room_of
                _named_rooms = {}
                for _nrid, _nrec in (((st.get("place_graph") or {})
                                      .get("nodes")) or {}).items():
                    if isinstance(_nrec, dict):
                        _nname = str(_nrec.get("name") or "").strip()
                        if _nname:
                            _named_rooms.setdefault(_nname.casefold(),
                                                    str(_nrid))
                # Beat-goal slot currency: the slot is rewritten every
                # commit from the enacted want, but the CLAIM inside it is
                # whatever the model re-emits, and nothing above counts its
                # tenure or notices its named room has been reached. Stamp
                # both facts here (goal_since / goal_room /
                # goal_room_reached); agents/character reads them back as
                # `goal_held` / `goal_reached` and stops ROUTING on a spent
                # claim -- see affect.goal_slot_currency.
                st["active_state"].update(affect.goal_slot_currency(
                    prev_as, str(enacted_goal or ""), _named_rooms,
                    _char_room_of(sc, sh), turn.idx))
                for _p in projects:
                    # One-shot backfill for projects that predate the ledger
                    # (a live pa1 exists): grace from here, never instantly
                    # adrift on the deploy beat. NOT setdefault -- the live
                    # pa1 was measured carrying an explicit
                    # last_served_turn: null, which setdefault preserves,
                    # leaving the ledger dead and the drift marker silent
                    # forever.
                    try:
                        int(_p.get("last_served_turn"))
                    except (TypeError, ValueError):
                        _p["last_served_turn"] = turn.idx
                _impact_serves = [
                    affect.normalize_serves(
                        str((gi or {}).get("serves") or ""),
                        intentions, projects)
                    for gi in (appraisal_input.get("goal_impacts") or [])
                    if isinstance(gi, dict)]
                for _pid in affect.projects_served_this_beat(
                        projects, wants, str(enacted_goal or ""),
                        _impact_serves, _named_rooms):
                    for _p in projects:
                        if str(_p.get("id") or "") == _pid:
                            _p["last_served_turn"] = turn.idx
                            # Distinct serving beats, for establishment:
                            # probation is left by service, never survival.
                            _p["served_beats"] = 1 + int(
                                _p.get("served_beats") or 0)
                # Probation settles AFTER this beat's service counted:
                # runtime adoptions establish once lived into (drive weight
                # from the NEXT beat) or lapse quietly once unserved past
                # the fuse. Authored/harness projects carry no probation
                # flag and pass through untouched.
                projects, former_projects, _probw = affect.settle_probation(
                    projects, former_projects, turn.idx)
                for w in _probw:
                    ctx.add_warning(f"{cname}: project -- {w}")
                # Boundary detection runs BEFORE record_spatial_experience
                # (below, line ~4100), so st["visited_rooms"] still ends at
                # the previous position while sc already holds the new one
                # -- which is exactly the arrival comparison needed.
                _prev_room = next(
                    (str(r) for r in reversed(st.get("visited_rooms") or [])
                     if isinstance(r, str) and r), None)
                _scene_marker = (interior.get("scene_marker")
                                 if isinstance(interior.get("scene_marker"),
                                               dict) else None)
                _loc_now = str(sc.get("location") or "")
                _review_why = affect.project_boundary(
                    projects, intentions, _before_status,
                    _char_room_of(sc, sh), _prev_room, _scene_marker,
                    _loc_now, turn.frame_id, _named_rooms)
                # --- Drive rupture (Tier 1): a deterministic strain ledger and
                # two-key gate that can, rarely and earned, crack the core drive.
                def _serves_of(i):
                    return (str(wants[i].get("serves") or "")
                            if (isinstance(wants, list) and isinstance(i, int)
                                and 0 <= i < len(wants)) else "")
                strain = float(interior.get("drive_strain") or 0.0)
                strain_log = list(interior.get("strain_log") or [])
                _strain_turns = max(1, turn.idx - int(interior.get("strain_turn") or (turn.idx - 1)))
                _strain_elapsed = psychology_runtime.elapsed_psych_units(
                    interior.get("strain_seconds"), _clock_seconds, _strain_turns)
                strain, _slog = affect.update_drive_strain(
                    strain, strain_log, appraisal_out,
                    _serves_of(enacted), _serves_of(suppressed), _strain_elapsed)
                if _slog:
                    _slog["turn"] = turn.idx
                    strain_log = (strain_log + [_slog])[-12:]
                cur_drive = effective_drive(character_psychology(sh), interior)
                former = list(interior.get("former_drives") or [])
                last_shift = interior.get("last_shift_turn")
                override = interior.get("drive_override") if isinstance(interior.get("drive_override"), dict) else None
                rupture = interior.get("drive_rupture") if isinstance(interior.get("drive_rupture"), dict) else None
                window_open = bool(rupture and turn.idx <= int(rupture.get("window_expires") or -1))
                if not window_open:
                    _det = affect.detect_drive_rupture(strain, appraisal_out, turn.idx, last_shift)
                    if _det:
                        rupture = {"turn": turn.idx, "opened_turn": turn.idx,
                                   "why": _det.get("why"),
                                   "direction": _det.get("direction"), "window_expires": turn.idx + 3}
                        ctx.add_warning(f"{cname}: DRIVE RUPTURE window opened -- {_det.get('why')}")
                elif own_result.get("drive_shift"):
                    _norm, _kind, _vw = affect.validate_drive_shift(
                        own_result.get("drive_shift"), cur_drive, former, rupture)
                    for w in _vw:
                        ctx.add_warning(f"{cname}: drive_shift -- {w}")
                    if _norm and _kind == "break":
                        _rw = str(rupture.get("why") or "")
                        former = (former + [affect.former_drive_entry(cur_drive, turn.idx, _rw)])[-5:]
                        override = {**_norm, "since_turn": turn.idx, "by_event": _rw}
                        strain, last_shift, rupture = 0.0, turn.idx, None
                        ctx.add_warning(f"{cname}: DRIVE SHIFTED -> {_norm.get('essence')}")
                        pending_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id, "turn_idx": turn.idx,
                            "kind": "episodic", "category": "self", "provenance": "remembered", "salience": 1.0,
                            "content": (f"Something in me broke when {_rw}. What I lived for -- "
                                        f"{cur_drive.get('essence')} -- no longer holds me. Now I live for: "
                                        f"{_norm.get('essence')}."),
                            "gist": f"drive shift -> {_norm.get('essence')}"[:240],
                            "entities": [cname], "location": room_name,
                            "emotional_context": surface.get("label") or "",
                            "event_key": _stable_event_key(turn.id, ccid, "drive_shift", cname,
                                                           _norm.get("essence"), ""),
                        })
                    elif _norm and _kind == "bend":
                        override = {**_norm, "since_turn": turn.idx, "by_event": str(rupture.get("why") or "")}
                        strain, last_shift, rupture = strain * 0.5, (turn.idx - 30), None
                if rupture and turn.idx > int(rupture.get("window_expires") or -1):
                    _opened_turn = int(rupture.get("opened_turn") or rupture.get("turn") or turn.idx)
                    _turns_open = turn.idx - _opened_turn
                    if strain >= affect.RUPTURE_STRAIN_MIN \
                            and _turns_open < affect.RUPTURE_MAX_OPEN:
                        # Strain still at rupture level and the hard cap not yet
                        # reached: the crisis is unresolved, so the window RE-OPENS
                        # (extends) instead of quietly closing -- denial is a phase,
                        # not an exit. (agents/character.py escalates the prompt to a
                        # FORCED resolution once the window has been open
                        # RUPTURE_FORCE_AFTER turns, so this extension is not the
                        # unpressured "you MAY" it used to be.)
                        rupture = {**rupture, "window_expires": turn.idx + 3}
                        ctx.add_warning(
                            f"{cname}: drive-rupture window extended -- "
                            f"strain {strain:.2f} still at rupture level")
                    else:
                        # Force-close: either strain finally decayed below the floor,
                        # OR the window has been open RUPTURE_MAX_OPEN turns with no
                        # shift. A model that will not shift within the forced window
                        # has, in effect, reaffirmed the drive under maximal pressure
                        # -- so resolve the crisis (pay strain down below the floor)
                        # rather than leaving the character in a permanent, never-
                        # resolving limbo (the 23-turn Vorne case).
                        if strain >= affect.RUPTURE_STRAIN_MIN:
                            strain = affect.RUPTURE_STRAIN_MIN * 0.75
                            ctx.add_warning(
                                f"{cname}: drive-rupture force-closed after "
                                f"{_turns_open} turns unresolved -- drive reaffirmed "
                                f"under pressure, strain paid down")
                        else:
                            strain = strain * 0.5   # weathered the crisis, no shift
                        rupture = None
                _interior_out = {
                    "intentions": intentions,
                    # Both project ledgers, every beat: this dict is rebuilt
                    # from scratch, and a key not carried here is a key
                    # silently erased.
                    "projects": projects,
                    "former_projects": former_projects,
                    # Where and in which frame this beat committed -- what
                    # project_boundary compares against next beat. Written
                    # unconditionally so a project adopted later still meets
                    # a fresh marker.
                    "scene_marker": {"location": _loc_now,
                                     "frame": str(turn.frame_id or "")},
                    "drive_strain": round(float(strain), 4),
                    "strain_log": strain_log,
                    "former_drives": former,
                    "last_shift_turn": last_shift,
                    "strain_turn": turn.idx,
                    "strain_seconds": _clock_seconds,
                    "beliefs": psychology_runtime.apply_belief_updates(
                        interior.get("beliefs"), character_psychology(sh),
                        own_result.get("belief_updates") or [], turn.idx,
                        _clock_seconds,
                    ),
                    "associations": psychology_runtime.apply_association_updates(
                        interior.get("associations"), character_psychology(sh),
                        own_result.get("association_updates") or [], turn.idx,
                        _clock_seconds,
                    ),
                }
                if rupture is not None:
                    _interior_out["drive_rupture"] = rupture
                if override is not None:
                    _interior_out["drive_override"] = override
                if _review_why:
                    # One-beat flag: _interior_out is rebuilt each commit,
                    # so this clears itself unless a new boundary fires.
                    _interior_out["project_review"] = {
                        "turn": turn.idx, "why": _review_why}
                st["interior"] = _interior_out
            # --- Recent-tell ledger: the last few physical cues this
            # character has shown, kept on cstate and fed back into the
            # next character payload (self.recent_tells) so the model
            # stops reaching for the same gesture every beat.
            _tells = [t for t in ((own_result.get("manifest") or {}).get("tells") or [])
                      if isinstance(t, dict)]
            _cues = [str(t.get("cue") or "").strip() for t in _tells]
            _cues = [c for c in _cues if c]
            if _cues:
                _prev_cues = [str(c) for c in (st.get("recent_tells") or [])
                              if str(c).strip()]
                st["recent_tells"] = (_prev_cues + _cues)[-RECENT_TELLS_CAP:]
            # --- Tell-ground ledger (F6): each shown cue with the private
            # ground it betrayed (`because`, grounded at the character stage
            # by affect.ground_tells), kept on cstate and fed back as
            # self.tell_grounds so a later beat can pay the tell off. Same
            # cap as the cue ledger; grounds never leave the character's own
            # private context.
            _grounds = [
                {"cue": str(t.get("cue") or "").strip(),
                 "because": str(t.get("because") or "").strip(),
                 "turn": turn.idx}
                for t in _tells
                if str(t.get("cue") or "").strip()
                and str(t.get("because") or "").strip()
            ]
            if _grounds:
                _prev_grounds = [
                    g for g in (st.get("tell_grounds") or [])
                    if isinstance(g, dict) and str(g.get("cue") or "").strip()
                ]
                st["tell_grounds"] = (_prev_grounds + _grounds)[-RECENT_TELLS_CAP:]
            stance = st.get("stance") or sh.get("stance") or {"axes": {}}
            for u in own_result.get("stance_updates") or []:
                ax = u.get("axis")
                if not ax:
                    continue
                try:
                    stance.setdefault("axes", {})
                    # P9: the schema clamps each DELTA, but the running total
                    # was unbounded -- a character nudged the same direction
                    # every beat walked past the [-1, 1] the axes are read as
                    # (character_schema seeds them from baseline_stances in
                    # that range), and every consumer downstream then compared
                    # against a scale the value had left. Clamped here because
                    # this is the only place the accumulation happens; a reroll
                    # re-applying a delta is P2's problem, not this one.
                    stance["axes"][ax] = round(
                        max(-1.0, min(1.0,
                            float(stance["axes"].get(ax, 0))
                            + float(u.get("delta", 0)))),
                        3,
                    )
                    stance.setdefault("log", []).append({
                        "turn": turn.idx, "axis": ax,
                        "delta": u.get("delta"), "trigger": u.get("trigger"),
                    })
                except Exception:
                    pass
            st["stance"] = stance
            # Rooms this body has actually walked through, the exits of rooms
            # stood in, visibly-closed chambers, and the durable place graph
            # -- everything a beat of standing somewhere earns, recorded in
            # one place (see record_spatial_experience). Their OWN traversal
            # history and sight, so it crosses no information boundary.
            # Lazy, like the other agents.common uses in this module: importing
            # it at module scope would close an import cycle.
            from agents.common import character_room as _character_room
            record_spatial_experience(
                st, sc, _character_room(sc, sh), turn.idx)
            # Place purpose, witnessed basis: their OWN vitals rising across
            # consecutive commits settled in this room (they ate here; they
            # rested here), or their body verifiably lying on a soft support
            # (comfort.rest_affording -- the seam comfort.py left for exactly
            # this writer). Runs after record_spatial_experience so the
            # standing room's node exists. Never the event row.
            from world import place_purpose
            place_purpose.witness_affords(st, sc, cname, turn.idx)
            # _mm_updates was rekeyed once at the top of this loop body (a
            # claim about a PLACE is re-keyed onto that place before it is
            # merged, because hypotheses group by (about_entity, kind) and
            # explain each other away within a group -- correct for a mind,
            # backwards for space; people stay protected). The SAME rekeyed
            # list minted this turn's inference memories above, so memory
            # subject and hypothesis key cannot drift apart.
            # Absorption is read off the state we just settled, so it reflects
            # the body at the END of the beat -- the state the character
            # actually comes out of it in, which is what governs what they can
            # still hold in mind going into the next one.
            _settled = st.get("active_state") or {}
            _absorption = psychology_runtime.cognitive_absorption(
                _settled.get("hedonic"), _settled.get("stress"))
            st = apply_mind_model_updates(
                st, _mm_updates, turn.idx, elapsed_seconds=_clock_seconds,
                absorption=_absorption,
            )
            # Place purpose, told basis: stated-fact place beliefs (already
            # re-keyed onto place names above) mirrored onto this character's
            # OWN place-graph nodes, and every existing told entry's sureness
            # re-asked from belief_credence -- the node entry is a read-model
            # of the belief, and a belief explained away must stop steering
            # (docs/design/DESIGN_PLACE_PURPOSE.md, mandatory drift rule). Runs
            # AFTER the merge so it reads reconciled beliefs, mirroring how
            # reconcile_inference_confidence treats memories.
            place_purpose.mirror_told_affords(st, turn.idx, _clock_seconds)
            # Re-selected on every beat this character acted in, not only when
            # `_mm_updates` is non-empty: capacity tracks the BODY, so someone
            # merely in more pain than last beat holds fewer open questions
            # even though they concluded nothing new.
            _sheet, _sheet_keys = select_active_hypotheses(
                st.get("mind_models") or {},
                st.get("active_hypothesis_keys"),
                sheet_capacity(_absorption),
                turn.idx,
                elapsed_seconds=_clock_seconds,
                absorption=_absorption,
            )
            st["active_hypotheses"] = _sheet
            st["active_hypothesis_keys"] = _sheet_keys
            if _mm_updates:
                # Only characters whose beliefs actually moved this turn are
                # reconciled: the reconcile scans that character's whole
                # inference bank, and a belief cannot be abandoned on a turn
                # nothing was claimed about it.
                belief_reconciles.append(
                    (cid, ccid, st, _clock_seconds))
            explicit_updates = own_result.get("relationship_updates") or []
            if explicit_updates:
                relationship_ops.append(("explicit", ccid, explicit_updates))
            elif own_result.get("inference_updates"):
                relationship_ops.append(
                    ("inference", ccid, own_result.get("inference_updates") or [])
                )
            # This mind re-read one of its own memories. Deferred to the write
            # phase with everything else: prepare_memory_commit is pure.
            for _d in own_result.get("memory_disputes") or []:
                if isinstance(_d, dict):
                    memory_disputes.append(
                        (cid, ccid, str(_d.get("gist") or ""),
                         str(_d.get("now_reads") or ""), turn.idx,
                         str(_d.get("memory_ref") or ""),
                         # What changed the reading. Carried so a re-reading
                         # that cites the same source twice is legible as a
                         # loop rather than as instability -- a count alone
                         # cannot tell those apart.
                         [str(_e.get("event_id") or "")
                          for _e in (_d.get("evidence") or [])
                          if isinstance(_e, dict)]))
            # Consequence, not popularity: a memory the character cited as
            # EVIDENCE for a belief they formed this beat turned out to be
            # load-bearing. Retrieval alone never moves importance -- that
            # would make often-recalled memories more recallable, which is a
            # feedback loop wearing the word.
            _cited = _cited_memory_ids(own_result)
            if _cited:
                importance_bumps.append((ccid, _cited))
        # Every memory minted for this mind on this beat records both the
        # affect carried into the event (valence/arousal) and the resolved
        # affect after appraisal (encoding_*).  Assign here, after every
        # possible append including inference memories.
        for _memory in pending_memories:
            if _memory.get("char_id") == ccid:
                _memory["encoding_valence"] = _encoding_valence
                _memory["encoding_arousal"] = _encoding_arousal
        state_updates.append((cid, ccid, json.dumps(st)))

    event_content = json.dumps({
        "turn": turn.idx,
        "summary": res.get("summary") or "",
        "event": res.get("resolved_event") or "",
        "dialogue_log": dlog,
    })
    # WHEN each of this beat's memories was formed, in seconds of fiction
    # time, stamped once here after every append. This is the reading the
    # commit already held -- the same `_clock_seconds` belief reconciliation,
    # affect decay and strain windows are dated by -- and until now it simply
    # never landed on the row, so every downstream reader had nothing but the
    # turn index and stamped minds in BEATS (94 such stamps across 54
    # character calls in one instrumented run).
    #
    # Stamped in ONE place rather than at each mint site: a second copy of the
    # rule is a second thing to forget when a mint site is added, and every
    # row on this list was formed at the same moment of the fiction by
    # definition.
    for _memory in pending_memories:
        _memory["encoded_at_seconds"] = _clock_seconds
    memory_batch = prepare_memories_batch(pending_memories)
    # A missing or failing embeddings provider silently downgrades every
    # vector to the local character-trigram hash, which then scores as a
    # fuzzy-lexical signal forever (an audit of a live corpus found 100% of
    # rows on the fallback with nothing anywhere saying so). The batch already
    # records the downgrade; surface it where every other turn anomaly goes.
    _embedded = memory_batch.get("embedded")
    if _embedded is not None and getattr(_embedded, "fallback", False):
        ctx.add_warning(
            "memory embeddings fell back to local hashing "
            f"({getattr(_embedded, 'error', '') or 'no embeddings provider'});"
            " semantic recall is degraded until an embeddings provider is "
            "configured")
    return {
        "memory_batch": memory_batch,
        "names_learned": _names_learned,
        "state_updates": state_updates,
        "relationship_ops": relationship_ops,
        "belief_reconciles": belief_reconciles,
        "memory_disputes": memory_disputes,
        "importance_bumps": importance_bumps,
        "event_content": event_content,
    }
