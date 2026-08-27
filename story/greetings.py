"""Greeting-seeded openings: ingest-time greeting interpretation and a
"Start story now" launch. See docs/design/GREETING_IMPORT_DESIGN.md.

`greeting_interpret` is to a character-card greeting what `director_interpret`
is to player input -- one bounded parse of freeform opening prose into
structured establishment scaffolding -- but run per-card and cached. The
greeting prose itself is always preserved verbatim; the extraction is scaffolding
UNDER it, most importantly the character's PRIVATE knowledge, which routes to
character memory and is never shown to the player.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time

from core import db
from story.character_schema import (
    character_name, character_appearance, character_initial_active_state,
    character_public_history, persona_name, persona_private_history,
)
from language_runtime import (
    DEFAULT_LANGUAGE, language_scope, set_story_language, story_language_scope,
)
from llm.llm_quality import complete_validated_json
from llm.prompts import get_prompt
from mind.memory import (
    add_memories_batch, duplicate_lorebook_for_chat, get_relationships,
    record_relationship_event, save_relationships,
)
from mind.theory_of_mind import apply_mind_model_updates
from agents.runtime import _run_pipeline
from agents.storage import active_content

#: What produced an extraction, so a stored one can be refused. Raise this
#: whenever `extract_greeting`'s prompt, schema or post-processing changes in
#: a way that makes an older extraction wrong -- the salience cap below is the
#: worked example of exactly such a change, and it shipped while nothing
#: stamped or checked this, so every stored extraction ever written is of
#: unknown provenance and re-extracts.
#:
#: v2: the extraction became per-person (`minds`), carrying beliefs, stances
#: and opening affect as well as knowledge -- a v1 extraction is not wrong so
#: much as one-fortieth of the picture, and replaying it would silently
#: launch a story whose opening seeded almost nobody. See
#: docs/design/DESIGN_GREETING_MINDS.md.
EXTRACTOR_VERSION = 2

#: The player's slot in imported prose. ONE definition, in the module that
#: mints it: `importers._substitute_macros` writes this token into every
#: imported card, and a second literal here could drift from the one actually
#: written without a single test noticing.
from story.importers import PLAYER_TOKEN

# Every way the player's slot arrives in seed prose. The token is what the
# prompt asks for; the bare words are what models write instead, and they are
# the reason this is a regex rather than a string replace.
#
# "the player" is not a name the character has not learned yet -- it is a word
# from OUTSIDE the fiction, in a fictional mind's own memory. Observed live in
# "Run!": three of four seeds reached The Doctor's memory as "The Doctor knows
# THE PLAYER was being chased by a Dalek", "intrigued by THE PLAYER'S
# appearance", "THE PLAYER'S unique traits make them a potential candidate".
# The {{PLAYER}} token was not in any of them, so the substitution that exists
# for exactly this had nothing to replace and the engine's own vocabulary went
# straight into the bank at salience 1.0.
#
# Deliberately anchored on a leading article or the token, so an in-fiction
# "a lute player" is left alone.
_PLAYER_SLOT = re.compile(
    r"\{\{\s*(?:player|user)\s*\}\}(?P<tposs>'s|s')?"
    r"|(?<![\w-])(?P<art>the\s+)player(?P<poss>'s|s')?(?![\w-])",
    re.IGNORECASE,
)


def _substitute_player_slot(text: str, handle: str) -> str:
    """Rewrite every player reference in `text` to one in-fiction handle,
    preserving possessives ("the player's appearance" -> "<handle>'s
    appearance"). `handle` already carries its own article when it needs one
    ("the beautiful young woman"), so the matched article is consumed.

    A description handle is lower-case by construction, so it is capitalised
    where it lands at the start of a sentence -- these strings are read as
    prose in a memory panel, and "the beautiful young woman's ears were flat"
    mid-paragraph is a different kind of wrong from the one being fixed.
    """
    body = str(text or "")

    def _swap(match):
        poss = match.group("tposs") or match.group("poss") or ""
        out = handle + ("'s" if poss else "")
        before = body[:match.start()].rstrip()
        if not before or before[-1] in ".!?":
            out = out[:1].upper() + out[1:]
        return out

    return _PLAYER_SLOT.sub(_swap, body)


def player_handle_for(persona_sheet: dict, *, already_known: bool) -> str:
    """What a character legitimately calls the player in their own memory.

    Known -> the persona's name. Not known -> a DESCRIPTION, built by the same
    `_unknown_actor_label` every perception path uses, so the greeting launch
    cannot drift from the identity floor the rest of the engine enforces. Not
    the name, and never "the player".
    """
    from agents.common import _unknown_actor_label, character_scene_keys
    name = persona_name(persona_sheet)
    if already_known:
        return name
    return _unknown_actor_label(
        name,
        character_appearance(persona_sheet),
        character_scene_keys(persona_sheet)[1:],
    )


def extract_greeting(sheet: dict, greeting_prose: str) -> dict:
    """One bounded ingest-time call: greeting prose -> establishment seeds.
    Persona-neutral: the {{PLAYER}} token is left symbolic."""
    payload = {
        "character_name": character_name(sheet),
        "character_appearance": character_appearance(sheet),
        "character_public_history": character_public_history(sheet),
        "greeting_prose": greeting_prose,
        "player_token": PLAYER_TOKEN,
    }
    out = complete_validated_json(
        role="greeting_interpret",
        step_key="greeting_interpret",
        system=get_prompt("greeting_interpret"),
        payload=payload,
        temperature=0.2,
    )
    # Deterministic information-boundary guard (never trust the model to tag it
    # right): a "secret" seed that names the player is not actually asymmetric,
    # so it can't be routed as private-from-the-player. Applied to the legacy
    # top-level list and to every mind's own list -- the guard is about the
    # seed's content, not about where the extraction filed it.
    for seed in out.get("knowledge_seeds") or []:
        if PLAYER_TOKEN in str(seed.get("content", "")):
            seed["revealed_in_prose"] = True
    for mind in out.get("minds") or []:
        for seed in (mind or {}).get("knowledge_seeds") or []:
            if PLAYER_TOKEN in str(seed.get("content", "")):
                seed["revealed_in_prose"] = True
    # STAMPED WHERE IT IS MINTED, not where it is filed. The greeting record
    # has a sibling `extractor_version` field, and a writer that copies the
    # extraction without it -- an archive, an editor, a hand-written card --
    # would leave scaffolding that can never say what made it.
    out["extractor_version"] = EXTRACTOR_VERSION
    return out


def _usable_stored_extraction(record):
    """A stored extraction is replayable only if THIS extractor made it.

    `start_story` replays `record["extraction"]` instead of paying for a
    model call, and that stored blob is the one path into the turn-0 seeding
    code that never passes through today's schema -- the salience cap above
    exists because of what came through it. An extraction of unknown
    provenance is therefore not trusted: unstamped means older than the
    stamp, which is every extraction written before this check.
    """
    stored = (record or {}).get("extraction")
    if not stored:
        return None
    version = (record or {}).get("extractor_version")
    if version is None and isinstance(stored, dict):
        version = stored.get("extractor_version")
    return stored if version == EXTRACTOR_VERSION else None


def _greeting_record(sheet: dict, index: int):
    opening = sheet.get("opening") or {}
    greetings = opening.get("greetings") or []
    if greetings:
        return greetings[max(0, min(index, len(greetings) - 1))]
    fm = opening.get("first_message") or ""
    return {"prose": fm, "extraction": None} if fm else None


def _override_narrator(tid: int, prose: str) -> None:
    """Replace turn 0's narrator prose with the verbatim greeting (a new active
    variant -- mirrors edit_prose). The establishment ran to produce a valid,
    committed turn; this only changes how the opening reads to the player, so no
    step is marked stale."""
    step = db.q("SELECT * FROM steps WHERE turn_id=? AND key='narrator'", (tid,), one=True)
    if not step:
        return
    content = active_content(tid, "narrator") or {}
    content["prose"] = prose
    db.qi("UPDATE variants SET active=0 WHERE step_id=?", (step["id"],))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (step["id"], json.dumps(content, ensure_ascii=False), time.time()))


# Ceiling on an authored seed's salience, just under the 0.72 floor below
# which `memory.consolidate_character_memory` archives a memory.
#
# A seed is scaffolding for a story that has not happened yet, and salience
# used to be the model's unbounded self-report: chat 53 launched with four
# seeds at 1.00 against the 0.78 of the single memory the pipeline minted that
# turn. Above 0.72 nothing is ever archived, and `contrast_memory` scores
# `salience + 0.4 * (age / current_turn)` -- so those seeds not only outranked
# lived experience permanently, their chance of intruding UNBIDDEN grew with
# the length of the story. Under the floor, a seed decays like anything else
# the character went on to actually live.
#
# `GreetingKnowledgeSeed` caps this too, and that is not enough on its own:
# `start_story` reads `rec["extraction"]`, a STORED extraction persisted on the
# character card at import time. Cards written before the cap -- or edited by
# hand -- reach this line without ever passing through the schema. The write is
# the boundary that matters.
_SEED_SALIENCE_MAX = 0.7


def _seed_salience(value) -> float:
    try:
        salience = float(value)
    except (TypeError, ValueError):
        return 0.6
    return max(0.0, min(_SEED_SALIENCE_MAX, salience))


# ---- Mind routing (docs/design/DESIGN_GREETING_MINDS.md) ----
#
# Every ceiling here is enforced AT THE WRITE, not only in the schema, for
# the same reason _SEED_SALIENCE_MAX is: `start_story` replays STORED
# extractions that never pass through today's schema.

#: A seeded belief may be held firmly, never unshakeably: it must start where
#: lived reinforcement could have put it, and `apply_belief_updates`'s
#: absolute weakening step keeps anything under this revisable.
_BELIEF_CONFIDENCE_MAX = 0.85
#: Protection halves revision; a greeting that armors a whole worldview has
#: authored an unrevisable character, which is a card decision
#: (`psychology.self_model.protected_beliefs`), not an opening-passage one.
#: The overflow is demoted to ordinary belief, not dropped.
_PROTECTED_BELIEFS_MAX = 2
_BELIEFS_PER_MIND_MAX = 8
_STANCES_PER_MIND_MAX = 6

#: `about_entity` spellings that mean the belief is the mind's own -- routed
#: to `interior.beliefs` rather than through theory of mind.
_SELF_WORLD = ("", "self", "world")


def _mind_key(who):
    """One identity fold for greeting minds -- the presence ledger's own
    (`commit._presence_identity`), so the mind retained for `The Porter` is
    found when `a porter` is promoted."""
    from persist.commit import _presence_identity
    return _presence_identity(who)


def _bounded(value, lo, hi, default=0.0):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return max(lo, min(hi, f))


def _split_minds(minds, char_name):
    """(card character's mind, player's mind, everyone else's) by `who`.

    The player is recognized by the token (or the bare words `_PLAYER_SLOT`
    exists for); the card character by name under the presence-identity fold,
    or the literal `self`. Everything else is somebody the passage put in the
    room whose store does not exist yet.
    """
    card = player = None
    others = []
    char_key = _mind_key(char_name)
    for mind in minds:
        who = str(mind.get("who") or "").strip()
        key = _mind_key(who)
        if player is None and (PLAYER_TOKEN in who or _PLAYER_SLOT.search(who)):
            player = mind
        elif card is None and key in (char_key, "self"):
            card = mind
        else:
            others.append(mind)
    return card, player, others


def _route_mind_memories(chat_id, char_id, seeds, handle):
    """Route one mind's knowledge seeds to that character's private memory.
    Returns how many were written.

    Memories are per-character and never enter the player's perception, so an
    unrevealed-in-prose seed is knowledge the character has and the player
    does not -- the whole point of the extraction.
    """
    seed_specs = []
    for seed in seeds or []:
        # NOT the persona's name unless the character legitimately knows it:
        # `handle` is `player_handle_for`'s answer, and this is the one path
        # that also rewrites the literal words "the player", which a plain
        # token replace cannot see (see _PLAYER_SLOT).
        try:
            content = _substitute_player_slot(
                str((seed or {}).get("content") or ""), handle).strip()
            if not content:
                continue
            # Give each seed a stable identity. The batch upserts on
            # (chat, character, event_key), so routing the same seed twice
            # updates one row instead of writing a second -- which is what
            # every other memory writer in the engine already gets, and what
            # makes a retried or partially-failed launch safe to repeat.
            #
            # It does NOT dedupe across launches, and should not: `start_story`
            # creates a fresh chat every time, so a second launch is a
            # different story that has its own copy.
            #
            # Keyed by content, not position, so editing or reordering the
            # greeting does not silently orphan the old row.
            digest = hashlib.sha1(content.encode("utf-8", "ignore")).hexdigest()
            seed_specs.append({
                "chat_id": chat_id, "char_id": char_id, "turn_id": None,
                "kind": "episodic", "provenance": "remembered",
                "salience": _seed_salience(seed.get("salience")),
                "content": content, "turn_idx": 0,
                "event_key": "greeting_seed:%s" % digest[:16],
            })
        except Exception:
            continue  # a bad seed must not abort the launch
    if seed_specs:
        # ONE embedding call for the whole set, not one per seed. Each seed
        # embeds two documents, so six seeds were six separate round trips to
        # the provider on the busiest moment a story ever has -- and any one
        # of them failing strands that memory on the crc32 fallback under its
        # own stamp, which is what makes a brand-new story offer to rebuild
        # memories it wrote seconds ago (reported live, 2026-08-11). Batching
        # is not merely faster: it turns six chances to be stranded into one,
        # and that one is retried inside `embed_texts_meta`.
        try:
            add_memories_batch(seed_specs)
        except Exception:
            return 0  # a failed seed batch must not abort the launch
    return len(seed_specs)


def _seed_mind_state(chat_id, char_id, sheet, mind, handle, other_keys):
    """Route one mind's beliefs, stances, and opening affect into the stores
    the runtime already revises. Returns ({channel: count}, [refusals]).

    Everything written here is a STARTING POINT, not a rule: interior rows
    are learned (never `authored`) entries the ledger evicts first; claims
    about other minds go through `apply_mind_model_updates`, so the engine's
    own per-kind ceilings bound what a greeting may assert about someone
    else; a stance is a graph position the story is free to move; affect
    overlays the surface only and decays back toward the card's baseline.
    Nothing is written for a channel the greeting did not establish --
    absence is not neutrality, and the card's authored state must stand
    wherever the passage was silent.
    """
    counts = {"beliefs": 0, "impressions": 0, "stances": 0, "affect": 0}
    refused = []
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (chat_id, char_id), one=True)
    if not row:
        return counts, ["not attached to this chat; nothing seeded"]
    st = json.loads(row["state"] or "{}")
    own_key = _mind_key((mind or {}).get("who"))

    beliefs = [b for b in (mind.get("beliefs") or []) if isinstance(b, dict)]
    if len(beliefs) > _BELIEFS_PER_MIND_MAX:
        refused.append("%d belief(s) over the per-mind cap dropped"
                       % (len(beliefs) - _BELIEFS_PER_MIND_MAX))
    interior_rows, tom_updates = [], []
    protected_used = 0
    for seed in beliefs[:_BELIEFS_PER_MIND_MAX]:
        text = _substitute_player_slot(
            str(seed.get("belief") or ""), handle).strip()
        if not text:
            continue
        about_raw = str(seed.get("about_entity") or "").strip()
        about_key = _mind_key(about_raw)
        # A belief about another PERSON PRESENT is a hypothesis about a mind
        # and goes through the theory-of-mind gate; a belief about the world,
        # the self, or any mere thing ("the east lock") stays interior. The
        # roster is the extraction's own -- deterministic, no name guessing.
        to_tom = (about_key not in _SELF_WORLD and about_key != own_key
                  and (PLAYER_TOKEN in about_raw or about_key in other_keys))
        confidence = _bounded(seed.get("confidence"),
                              0.0, _BELIEF_CONFIDENCE_MAX, 0.5)
        if to_tom:
            tom_updates.append({
                "about_entity": (_substitute_player_slot(about_raw, handle)
                                 .strip() or handle),
                "claim": text,
                "kind": str(seed.get("kind") or ""),
                "confidence": confidence,
            })
        else:
            protected = (bool(seed.get("protected"))
                         and protected_used < _PROTECTED_BELIEFS_MAX)
            if protected:
                protected_used += 1
            interior_rows.append({
                "belief": text,
                "confidence": confidence,
                "protected": protected,
                "emotional_charge": _bounded(
                    seed.get("emotional_charge"), -1.0, 1.0),
                "source": "greeting",
                # Turn 0, so `_within_cap` treats these as the least live
                # entries once the ledger fills -- a seed decays and evicts
                # like anything the character goes on to actually live.
                "last_updated_turn": 0, "last_updated_seconds": 0.0,
            })
    if interior_rows:
        interior = st.setdefault("interior", {})
        interior["beliefs"] = list(interior.get("beliefs") or []) + interior_rows
        counts["beliefs"] = len(interior_rows)
    if tom_updates:
        apply_mind_model_updates(st, tom_updates, 0)
        counts["impressions"] = len(tom_updates)

    stances = [s for s in (mind.get("stances") or []) if isinstance(s, dict)]
    if len(stances) > _STANCES_PER_MIND_MAX:
        refused.append("%d stance(s) over the per-mind cap dropped"
                       % (len(stances) - _STANCES_PER_MIND_MAX))
    graph = None
    for stance in stances[:_STANCES_PER_MIND_MAX]:
        target = _substitute_player_slot(
            str(stance.get("toward") or ""), handle).strip()
        trust = _bounded(stance.get("trust"), -1.0, 1.0)
        warmth = _bounded(stance.get("warmth"), -1.0, 1.0)
        fear = _bounded(stance.get("fear"), -1.0, 1.0)
        if not target or not (trust or warmth or fear):
            continue
        because = _substitute_player_slot(
            str(stance.get("because") or ""), handle).strip()[:300]
        if graph is None:
            graph = get_relationships(chat_id, char_id)
        # Absolute starting points, not deltas: this is where the passage
        # says the relationship already stands as the story opens.
        graph.update(target, trust=trust, emotional_valence=warmth,
                     fear=fear, salient_event=because)
        # One ledger row per axis the greeting set, provenance `greeting`,
        # so `relationship_history` can explain a seeded stance the same way
        # it explains every stance the story moves later.
        for axis, value in (("trust", trust), ("warmth", warmth),
                            ("fear", fear)):
            if value:
                record_relationship_event(
                    chat_id, char_id, target, axis, value,
                    note=because, provenance="greeting", turn_idx=0)
        counts["stances"] += 1
    if graph is not None:
        save_relationships(chat_id, char_id, graph)

    affect_seed = mind.get("affect")
    if isinstance(affect_seed, dict):
        label = str(affect_seed.get("label") or "").strip()
        valence = _bounded(affect_seed.get("valence"), -1.0, 1.0)
        arousal = _bounded(affect_seed.get("arousal"), -1.0, 1.0)
        # An all-empty dict is absence wearing braces -- seeding it would
        # overwrite the card's authored opening mood with "calm neutral",
        # which is this codebase's named silent failure.
        if label or abs(valence) >= 0.05 or abs(arousal) >= 0.05:
            from mind import affect as affect_mod
            # The numbers win, the label yields: a lexicon-contradicted or
            # unknown-and-empty label falls back to the quadrant, exactly the
            # arbitration the runtime applies to its own proposals.
            if not label or not affect_mod.label_matches(
                    label, valence, arousal):
                label = affect_mod.quadrant_label(valence, arousal)
            active = character_initial_active_state(sheet)
            active["mood"] = label
            active["valence"] = valence
            active["arousal"] = arousal
            # Surface only. The baseline stays the card's: the greeting is
            # the moment, the card is the temperament the moment decays back
            # toward.
            active["affect"]["surface"] = {
                "label": label, "valence": valence, "arousal": arousal}
            st["active_state"] = active
            counts["affect"] = 1

    if any(counts.values()):
        from story.scene import set_char_state
        set_char_state(chat_id, char_id,
                       json.dumps(st, ensure_ascii=False))
    return counts, refused


def _seed_player_mind(chat_id, mind, player_name, persona_sheet):
    """Route the player-slot mind. The one player-readable store admits
    REVEALED items only: an implied player-mind item is a model's guess about
    what the player-character knows, and a guess can embed another mind's
    secret in its phrasing -- routing it to a surface the player can open
    would let the extraction widen the page. The player's affect, beliefs,
    and stances are refused outright: the player's mind is the human's, and
    the engine seeds no feeling into the one mind the simulation must never
    drive. Every refusal is returned for the visible record."""
    counts = {"memories": 0}
    refused = []
    entries = None
    for seed in mind.get("knowledge_seeds") or []:
        if not isinstance(seed, dict):
            continue
        # The persona's own name, not a description: the player knows who
        # they are, and this store belongs to them.
        content = _substitute_player_slot(
            str(seed.get("content") or ""), player_name).strip()
        if not content:
            continue
        if not seed.get("revealed_in_prose"):
            refused.append(
                "unrevealed player-mind item withheld: the page did not "
                "deliver it, so this store must not")
            continue
        if entries is None:
            existing = db.wget(chat_id, "persona_private_history", None)
            # Merge over the persona's AUTHORED private history: writing this
            # key shadows the sheet's copy (`private_knowledge_for` reads the
            # key first), so seeding without the merge would silently discard
            # every authored entry.
            entries = (list(existing) if existing is not None
                       else persona_private_history(persona_sheet))
        entries.append({"about": player_name, "content": content,
                        "known_by": []})
        counts["memories"] += 1
    if counts["memories"]:
        db.wset(chat_id, "persona_private_history", entries)
    dropped = sum(len(mind.get(channel) or [])
                  for channel in ("beliefs", "stances"))
    if dropped:
        refused.append(
            "%d player belief/stance item(s) refused: the player's mind is "
            "the human's" % dropped)
    if mind.get("affect"):
        refused.append(
            "player affect refused: the engine seeds no feeling into the "
            "player")
    return counts, refused


def _seed_minds(chat_id, char_id, sheet, extraction, char_name, seed_handle,
                player_name, persona_sheet):
    """Route every mind the extraction established, and write the chat's
    `greeting_minds` record saying exactly what each one received and what
    was refused -- because a half-filled mind that fails silently is this
    subsystem's named failure mode, and the record is how it stays visible.

    Minds that resolve to nobody (a porter, a pair of guards) are retained
    verbatim and unclaimed: a background presence has no memory or
    psychology until promotion, and `claim_greeting_mind` seeds them at that
    exact moment rather than jumping the gate.
    """
    minds = [dict(m) for m in (extraction.get("minds") or [])
             if isinstance(m, dict)]
    card, player, others = _split_minds(minds, char_name)
    # v1's top-level seeds are the card character's own, un-keyed.
    legacy = [s for s in (extraction.get("knowledge_seeds") or [])
              if isinstance(s, dict)]
    if legacy:
        if card is None:
            card = {"who": char_name}
        card["knowledge_seeds"] = (list(card.get("knowledge_seeds") or [])
                                   + legacy)
    record = {"extractor_version": EXTRACTOR_VERSION, "minds": {}}
    all_keys = {_mind_key(m.get("who")) for m in minds} - {""}
    if card is not None:
        card_key = _mind_key(card.get("who") or "") or _mind_key(char_name)
        memories = _route_mind_memories(
            chat_id, char_id, card.get("knowledge_seeds") or [], seed_handle)
        counts, refused = _seed_mind_state(
            chat_id, char_id, sheet, card, seed_handle,
            all_keys - {card_key})
        counts["memories"] = memories
        record["minds"][card_key] = {
            "who": card.get("who") or char_name,
            "resolved": "character:%d" % int(char_id),
            "claimed": True, "seeded": counts, "refused": refused,
        }
    if player is not None:
        counts, refused = _seed_player_mind(
            chat_id, player, player_name, persona_sheet)
        record["minds"]["player"] = {
            "who": PLAYER_TOKEN, "resolved": "player", "claimed": True,
            "seeded": counts, "refused": refused,
        }
    for mind in others:
        key = _mind_key(mind.get("who"))
        if not key or key in record["minds"]:
            continue
        record["minds"][key] = {
            "who": mind.get("who"), "resolved": None, "claimed": False,
            # Verbatim and persona-neutral: {{PLAYER}} stays a token so the
            # claim can substitute whatever handle is legitimate then.
            "mind": mind,
        }
    db.wset(chat_id, "greeting_minds", record)
    return record


def claim_greeting_mind(chat_id, char_id, name, sheet):
    """Seed a just-promoted character from the greeting mind retained for
    them at launch, if one was. Called by
    `commit_background.promote_background_character` -- promotion is the one
    sanctioned moment a background presence acquires memory and psychology,
    so it is the moment the retained material has been waiting for. Returns
    the updated record entry, or None when no unclaimed mind matches.

    The player handle is the persona's NAME: promotion seeds mutual
    recognition with the player ("she's been part of the scene the whole
    time"), so by the time this runs the name is legitimate.
    """
    record = db.wget(chat_id, "greeting_minds", None)
    if not isinstance(record, dict):
        return None
    minds = record.get("minds") or {}
    entry = key = None
    for candidate in (_mind_key(name), _mind_key(character_name(sheet))):
        found = minds.get(candidate) if candidate else None
        if (isinstance(found, dict) and not found.get("claimed")
                and isinstance(found.get("mind"), dict)):
            entry, key = found, candidate
            break
    if entry is None:
        return None
    from story.scene import persona_of
    chat_row = db.q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    handle = persona_name(persona_of(dict(chat_row))) if chat_row else "Player"
    mind = entry["mind"]
    memories = _route_mind_memories(
        chat_id, char_id, mind.get("knowledge_seeds") or [], handle)
    counts, refused = _seed_mind_state(
        chat_id, char_id, sheet, mind, handle,
        set(minds) - {key, "player"})
    counts["memories"] = memories
    entry.update({"claimed": True,
                  "resolved": "character:%d" % int(char_id),
                  "seeded": counts, "refused": refused})
    # Claimed material now lives in its stores; keeping a second copy here
    # would invite drift between the record and the mind.
    entry.pop("mind", None)
    minds[key] = entry
    db.wset(chat_id, "greeting_minds", record)
    return entry


def start_story(char_id: int, persona_id: int, greeting_index: int = 0,
                lorebook_id: int | None = None,
                already_known: bool = True,
                language: str | None = None,
                lived_location: dict | None = None) -> tuple[int, int]:
    """'Start story now': create a chat seeded from a character's greeting.
    The greeting is shown verbatim; its private knowledge routes to the
    character. An optional lorebook is attached before turn 0 runs, so the
    opening establishment can already draw on that world's lore. Returns
    (chat_id, turn_id).

    `already_known` seeds mutual name-recognition between the character and the
    player. It defaults True because greeting cards are typically written TO the
    player as an already-acquainted companion. Set False for a strangers-meeting
    greeting, where the character has no legitimate way to know the player's name
    yet -- otherwise perception hands the character that name from turn 1 (the
    canonical name-leak this guards against)."""
    ch = db.q("SELECT * FROM characters WHERE id=?", (char_id,), one=True)
    per = db.q("SELECT * FROM personas WHERE id=?", (persona_id,), one=True)
    if not ch:
        raise ValueError(f"character {char_id} not found")
    if not per:
        raise ValueError(f"persona {persona_id} not found")
    # Resolve the optional lorebook up front so a bad id aborts before any
    # chat/cast rows are created, rather than half-building a story.
    lb = None
    if lorebook_id:
        lb = db.q("SELECT * FROM lorebooks WHERE id=?", (int(lorebook_id),), one=True)
        if not lb:
            raise ValueError(f"lorebook {lorebook_id} not found")
    sheet = json.loads(ch["sheet"])
    psheet = json.loads(per["sheet"])
    p_name = persona_name(psheet)
    c_name = character_name(sheet)

    rec = _greeting_record(sheet, greeting_index)
    if not rec or not str(rec.get("prose") or "").strip():
        raise ValueError("character has no greeting to start from")
    prose_tok = rec.get("prose") or ""
    # Scoped here rather than after the chat row exists: this is a model call,
    # and it runs before there is a chat whose story language could be read.
    with language_scope(language or DEFAULT_LANGUAGE):
        extraction = (_usable_stored_extraction(rec)
                      or extract_greeting(sheet, prose_tok))

    def sub(s):  # deterministic {{PLAYER}} -> persona name
        return str(s or "").replace(PLAYER_TOKEN, p_name)

    # What the CHARACTER may call the player in their own private memory. The
    # verbatim prose above is shown to the player and keeps the persona's name;
    # a seed is knowledge inside a mind and obeys that mind's identity floor.
    seed_handle = player_handle_for(psheet, already_known=already_known)

    prose_final = sub(prose_tok)

    # chat + cast. Scenario = the full (substituted) greeting so establishment
    # builds the scene from the author's opening. Recognition is seeded mutual
    # by default (the greeting is written TO the player), but a strangers-meeting
    # greeting starts with `already_known=False` so neither party begins knowing
    # the other's name.
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                (f"{c_name} — {p_name}", prose_final, time.time()))
    # Recorded before anything is seeded, because turn 0 runs below and every
    # stage of it -- establishment, perception, the narrator -- reads this.
    set_story_language(cid, language or DEFAULT_LANGUAGE)
    db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona_id, cid))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?, 'active')", (cid, char_id))
    if already_known:
        db.wset(cid, "known", {c_name: [p_name], p_name: [c_name]})
    db.wset(cid, "fiction_model", {"genre": {"primary": "as written in the card"},
                                   "ontology": {}, "causal_regimes": [],
                                   "scale_rules": {}, "abstraction_rules": {}})
    # `display` is the scene's TIME OF DAY restated on the clock, and turn 0's
    # establish inherits this where it names none of its own. "now" as the
    # fallback made a story that said nothing about time claim a time anyway.
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0,
                                      "display": sub(extraction.get("time") or ""),
                                      "time_scale": "scene"})

    # Attach the chosen lorebook before turn 0 runs. A global (template) book is
    # duplicated into a per-chat copy the same way attach_lore does; a book that
    # is already chat-scoped attaches directly.
    generation_book_id = None
    if lb:
        if lb["chat_id"] == cid:
            new_lb, origin = lb["id"], lb["origin_id"]
        else:
            new_lb = duplicate_lorebook_for_chat(lb["id"], cid)
            origin = lb["id"]
        db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) "
              "VALUES(?,?,?,1)", (cid, new_lb, origin))
        generation_book_id = new_lb

    # A selected prehistory must exist before establishment authors turn 0.
    # Running this from the browser after /start returns made the supposedly
    # old residents and institutions arrive one scene late, after the opening
    # had already decided what the location contained.
    generated_location = None
    history_route = None
    if isinstance(lived_location, dict) and lived_location.get("enabled", True):
        from world.charter_runtime import generate_lived_location
        from story.history_routing import (
            resolve_character_history_route, route_uses_charter)
        from world.charter_history import (
            featured_resident_private_habits, featured_resident_seed)
        request = dict(lived_location)
        route_request = request.get("character_history") or {}
        route = resolve_character_history_route(
            sheet, requested=route_request,
            opening=prose_final, location_brief=request.get("brief") or "")
        route["guidance"] = str(
            (route_request if isinstance(route_request, dict) else {}).get(
                "brief") or "")[:2000]
        from story.journey_history import journey_event_count
        route["event_count"] = journey_event_count(
            (route_request if isinstance(route_request, dict) else {}).get(
                "events"))
        db.wset(cid, "character_history_routes", {str(char_id): route})
        history_route = route
        if route_uses_charter(route):
            resident_seed = featured_resident_seed(char_id, sheet)
            request["featured_residents"] = [resident_seed]
            request["featured_resident_private"] = {
                resident_seed["seed_id"]: {
                    "habits": featured_resident_private_habits(sheet)}}
        else:
            request.pop("featured_residents", None)
            request.pop("featured_resident_private", None)
        if generation_book_id is not None:
            # Read the selected library subtree (the legacy attachment seam
            # copies one book, not its children) while grounding the resulting
            # rooms in the story-local copy.
            request["lorebook_id"] = lb["id"]
            request["owning_lorebook_id"] = generation_book_id
        try:
            generated_location = generate_lived_location(cid, request)
        except Exception:
            # No turn exists yet and this chat was minted by this call.  A
            # failed location proposal must not leave an invisible half-story
            # that appears after refresh or gets duplicated on the next try.
            from persist.chat_delete import delete_chat_data
            delete_chat_data(cid)
            raise

    # Route every mind the extraction established -- the card character's in
    # full (memories, beliefs, stances, opening affect), the player's within
    # what the page delivered, and everyone else retained for promotion --
    # and record what each received in the chat's `greeting_minds` key.
    # BEFORE turn 0 runs, deliberately: the pipeline's checkpoint 0 then
    # snapshots the seeded state, so a rerun of the opening keeps it.
    with language_scope(language or DEFAULT_LANGUAGE):
        _seed_minds(cid, char_id, sheet, extraction, c_name, seed_handle,
                    p_name, psheet)

    # Itinerant history is a separate topology. Canon/authored travelers get
    # a cited compiler; an invented journey runs only after the author chose
    # that route explicitly. Neither path places the character in Charter.
    if isinstance(history_route, dict) and (
            history_route.get("mode") == "visitor"
            or history_route.get("mode") == "generated_journey"
            or (history_route.get("mode") == "auto"
                and history_route.get("opening_relationship") == "visiting")):
        from story.journey_history import compile_journey_history
        journey_lore = []
        if lb:
            from world.charter_runtime import generation_lore
            journey_lore, _source = generation_lore(
                cid, lb["id"], query=f"{c_name} journeys visits history")
        try:
            with language_scope(language or DEFAULT_LANGUAGE):
                journey_result = compile_journey_history(
                    cid, char_id, sheet, history_route, lore=journey_lore,
                    opening=prose_final,
                    # A journey ends where the story begins: the lived-location
                    # brief was computed for routing and then thrown away, so
                    # nothing could author the approach to the opening place.
                    arrival_brief=str(
                        lived_location.get("brief") or ""
                        if isinstance(lived_location, dict) else ""))
            routes = db.wget(cid, "character_history_routes", {}) or {}
            routes[str(char_id)]["handoff"] = {
                "complete": True,
                "memory_count": len(
                    journey_result.get("memory_event_keys") or ()),
                "journey_events": len(journey_result.get("events") or ()),
            }
            db.wset(cid, "character_history_routes", routes)
        except Exception as exc:
            if history_route.get("mode") == "generated_journey":
                from persist.chat_delete import delete_chat_data
                delete_chat_data(cid)
                raise
            routes = db.wget(cid, "character_history_routes", {}) or {}
            routes[str(char_id)]["handoff"] = {
                "complete": False,
                "safe_fallback": "authored card and greeting only",
                "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            }
            db.wset(cid, "character_history_routes", routes)

    # The card character lived through the requested prehistory as a Charter
    # body, then crosses the cognition boundary exactly once: their grounded
    # service becomes a few pre-story memories and their full character agent
    # owns them from turn zero onward. A generator that could not place them
    # leaves the ordinary card launch untouched and records no counterfeit
    # past.
    if isinstance(generated_location, dict):
        seed_id = f"character:{int(char_id)}"
        binding = (generated_location.get("featured_residents") or {}).get(
            seed_id)
        if binding:
            from world.charter_history import integrate_featured_resident
            try:
                with language_scope(language or DEFAULT_LANGUAGE):
                    history_result = integrate_featured_resident(
                        cid, char_id, binding, sheet,
                        author_guidance=(history_route or {}).get(
                            "guidance") or "")
                routes = db.wget(cid, "character_history_routes", {}) or {}
                if str(char_id) in routes:
                    routes[str(char_id)]["handoff"] = {
                        "complete": True,
                        "memory_count": len(
                            history_result.get("memory_event_keys") or ()),
                        "binding": copy.deepcopy(binding),
                    }
                    db.wset(cid, "character_history_routes", routes)
            except Exception:
                from persist.chat_delete import delete_chat_data
                delete_chat_data(cid)
                raise

    # Turn 0: run establishment (valid, committed), then show the greeting verbatim.
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                (cid, 0, "", time.time(), None))
    # `_run_pipeline` is called directly here rather than through
    # `run_pipeline`, which is the ONLY place the story language was ever set.
    # The opening beat is the first prose a reader sees, and it was always
    # English.
    with story_language_scope(cid):
        list(_run_pipeline(cid, tid))
    _override_narrator(tid, prose_final)
    return cid, tid


def generate_greeting(char_id: int, brief: str = "",
                      language: str | None = None) -> dict:
    """Generate one greeting for a character, in that character's voice, and
    return it as a `sheet.opening.greetings` entry (NOT persisted -- the caller
    adds it to the list and saves through the normal character-update path,
    exactly like a hand-added greeting).

    The player is referred to with the {{PLAYER}} token so the greeting stays
    reusable across personas, matching imported card greetings.
    """
    from story.importers import _substitute_macros
    from llm.providers import chat_complete
    from story.character_schema import (
        character_voice, character_psychology,
    )

    ch = db.q("SELECT sheet FROM characters WHERE id=?", (char_id,), one=True)
    if not ch:
        raise ValueError(f"character {char_id} not found")
    sheet = json.loads(ch["sheet"])
    name = character_name(sheet)

    payload = {
        "character": {
            "name": name,
            "appearance": character_appearance(sheet),
            "voice": character_voice(sheet),
            "psychology": character_psychology(sheet),
            "public_history": character_public_history(sheet),
        },
        "situation_brief": (brief or "").strip()
        or "No brief given -- invent an ordinary, evocative opening that suits this character.",
        "player_token": PLAYER_TOKEN,
    }

    # Scoped, not just passed: `providers` re-applies the schema policy at the
    # boundary from the contextvar, so a language given only to `get_prompt`
    # gets the Japanese contract with the English one appended underneath.
    with language_scope(language or DEFAULT_LANGUAGE):
        raw = chat_complete(
            "utility",
            get_prompt("generator_greeting"),
            json.dumps(payload, ensure_ascii=False),
            temperature=0.9,
            max_tokens=2000,
            json_mode=False,
        )
    prose = _strip_greeting_wrapping(raw)
    if not prose:
        raise RuntimeError("Greeting generator returned no usable text.")

    # Keep any literal character-name macros consistent with the card
    # convention; {{PLAYER}} is deliberately left intact for per-play
    # substitution downstream (start_story resolves it).
    prose = _substitute_macros(prose, name).strip()

    return {
        "greeting_id": "greet_" + hashlib.sha1(prose.encode("utf-8")).hexdigest()[:16],
        "prose": prose,
        "extraction": None,
        "extractor_version": None,
    }


#: Every quote character that can wrap a whole greeting, opening or closing.
_QUOTE_MARKS = "\"“”"


def _strip_greeting_wrapping(raw: str) -> str:
    """A utility model sometimes wraps prose in a code fence or in whole-string
    quotes despite the prompt. Peel those without touching the prose itself.

    A LEADING LABEL IS DELIBERATELY NOT PEELED, and this docstring used to
    claim it was. A short prefix before a colon cannot be told from a speaker
    attribution, and an attribution is CONTENT -- dropping it loses who is
    talking, which is worse than leaving a stray "Greeting:" where an author
    can see and delete it.
    """
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    text = text.strip()
    # ONE PAIR AROUND THE WHOLE THING, AND NOTHING INSIDE IT. A greeting may
    # legitimately open and close on dialogue, so the two ends prove nothing;
    # what distinguishes wrapping from speech is that wrapping is the only
    # quote in the string. Anything else is somebody talking, and peeling it
    # would take one mark off a line and leave its partner standing.
    #
    # The condition this replaces counted straight quotes against curly ones
    # (`count('"') + count(open) == 1 + count(close)`) and its body was
    # `pass`, so neither half of the peel this function documents ran.
    if (len(text) >= 2 and text[0] in _QUOTE_MARKS and text[-1] in _QUOTE_MARKS
            and not any(ch in _QUOTE_MARKS for ch in text[1:-1])):
        text = text[1:-1]
    return text.strip()
