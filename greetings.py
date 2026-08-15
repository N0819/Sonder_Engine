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

import hashlib
import json
import re
import time

import db
from character_schema import (
    character_name, character_appearance, character_public_history, persona_name,
)
from llm_quality import complete_validated_json
from prompts import get_prompt
from memory import add_memories_batch, duplicate_lorebook_for_chat
from agents.runtime import _run_pipeline
from agents.storage import active_content

EXTRACTOR_VERSION = 1
PLAYER_TOKEN = "{{PLAYER}}"

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
    # so it can't be routed as private-from-the-player.
    for seed in out.get("knowledge_seeds") or []:
        if PLAYER_TOKEN in str(seed.get("content", "")):
            seed["revealed_in_prose"] = True
    return out


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


def start_story(char_id: int, persona_id: int, greeting_index: int = 0,
                lorebook_id: int | None = None,
                already_known: bool = True) -> tuple[int, int]:
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
    extraction = rec.get("extraction") or extract_greeting(sheet, prose_tok)

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
    db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona_id, cid))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?, 'active')", (cid, char_id))
    if already_known:
        db.wset(cid, "known", {c_name: [p_name], p_name: [c_name]})
    db.wset(cid, "fiction_model", {"genre": {"primary": "as written in the card"},
                                   "ontology": {}, "causal_regimes": [],
                                   "scale_rules": {}, "abstraction_rules": {}})
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0,
                                      "display": sub(extraction.get("time") or "now"),
                                      "time_scale": "scene"})

    # Attach the chosen lorebook before turn 0 runs. A global (template) book is
    # duplicated into a per-chat copy the same way attach_lore does; a book that
    # is already chat-scoped attaches directly.
    if lb:
        if lb["chat_id"] == cid:
            new_lb, origin = lb["id"], lb["origin_id"]
        else:
            new_lb = duplicate_lorebook_for_chat(lb["id"], cid)
            origin = lb["id"]
        db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) "
              "VALUES(?,?,?,1)", (cid, new_lb, origin))

    # Route the character's private knowledge to character memory. Memories are
    # per-character and never enter the player's perception, so an
    # unrevealed-in-prose seed is knowledge the character has and the player
    # does not -- the whole point of the extraction.
    seed_specs = []
    for seed in extraction.get("knowledge_seeds") or []:
        # NOT `sub`. That resolves the player's slot to the persona's name,
        # which is right for the prose the player reads and wrong for a
        # character's private memory: it hands the name over on beat zero,
        # defeating `already_known=False`. `seed_handle` is the name only when
        # the character is meant to know it, and a description otherwise --
        # and either way this is the one path that also rewrites the literal
        # words "the player", which `sub` cannot see (see _PLAYER_SLOT).
        try:
            content = _substitute_player_slot(seed.get("content") or "",
                                              seed_handle).strip()
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
            # different story that has its own copy. (docs/UNBUILT.md 1.16 said
            # a re-launch duplicates them; there is no in-chat re-routing path,
            # so that half of the entry was wrong.)
            #
            # Keyed by content, not position, so editing or reordering the
            # greeting does not silently orphan the old row.
            digest = hashlib.sha1(content.encode("utf-8", "ignore")).hexdigest()
            seed_specs.append({
                "chat_id": cid, "char_id": char_id, "turn_id": None,
                "kind": "episode", "provenance": "remembered",
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
            pass  # a failed seed batch must not abort the launch

    # Turn 0: run establishment (valid, committed), then show the greeting verbatim.
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                (cid, 0, "", time.time(), None))
    list(_run_pipeline(cid, tid))
    _override_narrator(tid, prose_final)
    return cid, tid


def generate_greeting(char_id: int, brief: str = "") -> dict:
    """Generate one greeting for a character, in that character's voice, and
    return it as a `sheet.opening.greetings` entry (NOT persisted -- the caller
    adds it to the list and saves through the normal character-update path,
    exactly like a hand-added greeting).

    The player is referred to with the {{PLAYER}} token so the greeting stays
    reusable across personas, matching imported card greetings.
    """
    from importers import _substitute_macros
    from providers import chat_complete
    from character_schema import (
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

    import hashlib
    return {
        "greeting_id": "greet_" + hashlib.sha1(prose.encode("utf-8")).hexdigest()[:16],
        "prose": prose,
        "extraction": None,
        "extractor_version": None,
    }


def _strip_greeting_wrapping(raw: str) -> str:
    """A utility model sometimes wraps prose in a code fence, a leading label,
    or whole-string quotes despite the prompt. Peel those without touching the
    prose itself."""
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    text = text.strip()
    # A single pair of wrapping quotes around the ENTIRE greeting (not internal
    # dialogue) -- only strip when both ends are quotes and there's no earlier
    # closing quote that would make this real dialogue.
    if len(text) >= 2 and text[0] in "\"“" and text[-1] in "\"”" \
            and text.count('"') + text.count("“") == 1 + text.count("”"):
        pass  # ambiguous -- leave dialogue-opening greetings intact
    return text.strip()
