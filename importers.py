import json, time, re, uuid, base64, struct, zlib, hashlib, numpy as np
from contextlib import contextmanager
from db import q, qi, transaction
from memory import (
    add_lore, LORE_CATEGORIES, LOREBOOK_TYPES, LOREBOOK_LINK_TYPES,
    KNOWLEDGE_TAGS, KNOWLEDGE_RANGES, add_lorebook_link,
)
from providers import chat_complete, token_sink, embed_texts
from prompts import get_prompt
from character_schema import (
    CHARACTER_SCHEMA,
    PERSONA_SCHEMA,
    character_name,
    default_character_data,
    default_persona_data,
    normalize_character_data,
    normalize_persona_data,
    persona_name,
)

@contextmanager
def _silent_provider_stream():
    token = token_sink.set(lambda _delta: None)
    try:
        yield
    finally:
        token_sink.reset(token)

def _blob(v):
    return np.asarray(v, dtype=np.float32).tobytes()

def _repair_json(text):
    return re.sub(r',\s*([}\]])', r'\1', text or "")

def _jparse(text):
    t = re.sub(
        r"^```[a-zA-Z]*\n?|```$",
        "",
        (text or "").strip(),
        flags=re.M,
    ).strip()

    def _try_parse(s):
        try:
            result = json.loads(s)
            if isinstance(result, list):
                result = result[0] if result else {}
            if isinstance(result, dict):
                return result
        except Exception:
            pass
        return None

    result = _try_parse(t)
    if result is not None:
        return result
    result = _try_parse(_repair_json(t))
    if result is not None:
        return result

    m = re.search(r"\{.*\}", t, re.S)
    if m:
        block = m.group(0)
        result = _try_parse(block)
        if result is not None:
            return result
        result = _try_parse(_repair_json(block))
        if result is not None:
            return result

    if '{' in t:
        base = t
        if base.count('"') % 2 == 1:
            base = base + '"'
        for close in (
            '}',
            ']}',
            '}}',
            ']}]}',
            '"}]}',
            '"]}}',
            '"}}',
            '"]}',
            '"}}]}',
        ):
            result = _try_parse(base + close)
            if result is not None:
                return result
            result = _try_parse(_repair_json(base + close))
            if result is not None:
                return result

    return {}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

def _png_text_chunks(png_bytes):
    if not png_bytes.startswith(_PNG_SIGNATURE):
        raise ValueError("Not a valid PNG file")
    chunks = {}
    pos, n = 8, len(png_bytes)
    while pos + 8 <= n:
        length = struct.unpack(">I", png_bytes[pos:pos + 4])[0]
        ctype = png_bytes[pos + 4:pos + 8]
        data = png_bytes[pos + 8:pos + 8 + length]
        pos += 8 + length + 4
        if ctype == b"tEXt" and b"\x00" in data:
            key, _, val = data.partition(b"\x00")
            chunks[key.decode("latin-1")] = val.decode("latin-1")
        elif ctype == b"zTXt" and b"\x00" in data:
            key, _, rest = data.partition(b"\x00")
            if rest:
                try:
                    # Bound the inflate: a ~50KB crafted zTXt chunk can expand
                    # to gigabytes (decompression bomb) and OOM the process.
                    # Card imports are, by design, untrusted community files.
                    _MAX = 10 * 1024 * 1024  # 10 MB is far beyond any real card
                    raw = zlib.decompressobj().decompress(rest[1:], _MAX)
                    chunks[key.decode("latin-1")] = raw.decode("utf-8", "replace")
                except Exception:
                    pass
        elif ctype == b"IEND":
            break
    return chunks

def extract_png_card(png_base64):
    # Character cards shared as PNGs (chub.ai, JanitorAI, SillyTavern
    # community boards) embed the card JSON as base64 text in a PNG
    # metadata chunk rather than as a standalone JSON file: "chara" for
    # spec v2, "ccv3" for v3 (v3 exporters usually keep a v2-compatible
    # "chara" chunk too, for readers that don't know about v3 -- so v3
    # is preferred when both are present).
    raw = png_base64.split(",", 1)[-1]
    try:
        png_bytes = base64.b64decode(raw)
    except Exception as exc:
        raise ValueError(f"Invalid PNG data: {exc}") from exc

    chunks = _png_text_chunks(png_bytes)
    for key in ("ccv3", "chara"):
        text = chunks.get(key)
        if not text:
            continue
        try:
            parsed = json.loads(base64.b64decode(text).decode("utf-8"))
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None

def resolve_import_card(raw):
    if isinstance(raw, dict) and raw.get("png_base64"):
        card = extract_png_card(raw["png_base64"])
        if card is None:
            raise ValueError(
                "No character card data found in that PNG "
                "(expected a 'chara' or 'ccv3' metadata chunk)."
            )
        return card
    return raw if isinstance(raw, dict) else {}

def _card_data(payload):
    if isinstance(payload, dict) and \
       str(payload.get("spec", "")).startswith("chara_card"):
        return payload.get("data") or {}
    return payload if isinstance(payload, dict) else {}

def _first_sentences(text, n=2):
    parts = re.split(
        r"(?<=[.!?])\s+",
        (text or "").strip(),
    )
    return " ".join(parts[:n]).strip()

# Canonical player token left in imported text. We deliberately do NOT
# substitute in a persona/player name at import time -- imported cards are
# authored against whoever will eventually play them, and inventing a persona
# name here would fabricate identity the card never stated. A stable, readable
# token is enough to stop a literal "{{user}}" from rendering to the player;
# see docs/GREETING_IMPORT_DESIGN.md's PLAYER token.
PLAYER_TOKEN = "{{PLAYER}}"

# SillyTavern / chub / JanitorAI card macros. {{char}}/<BOT> resolve to the
# character's own name; {{user}}/<USER> resolve to the neutral player token.
# Case-insensitive, tolerating the whitespace SillyTavern allows ({{ char }}).
_CHAR_MACRO_RE = re.compile(r"\{\{\s*char\s*\}\}|<BOT>", re.IGNORECASE)
_USER_MACRO_RE = re.compile(r"\{\{\s*user\s*\}\}|<USER>", re.IGNORECASE)


def _substitute_macros(text, char_name):
    """Resolve {{char}}/<BOT> and {{user}}/<USER> in a single string. Without
    this, a literal '{{user}}' or '{{char}}' from an imported card renders
    verbatim to the player (audit finding #24)."""
    if not isinstance(text, str) or not text:
        return text
    if char_name:
        text = _CHAR_MACRO_RE.sub(str(char_name), text)
    return _USER_MACRO_RE.sub(PLAYER_TOKEN, text)


def _substitute_card_macros(obj, char_name):
    """Deep-copy `obj`, substituting card macros in every string leaf. Card
    text (description, first_mes, scenario, mes_example, lorebook content, ...)
    can carry macros anywhere, so this walks the whole structure rather than
    enumerating fields. The original payload stored as `source` is untouched --
    only the derived sheet/lore content the player actually sees is rewritten."""
    if isinstance(obj, str):
        return _substitute_macros(obj, char_name)
    if isinstance(obj, dict):
        return {k: _substitute_card_macros(v, char_name) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_card_macros(v, char_name) for v in obj]
    return obj

def _native_payload(payload, expected_kind):
    if not isinstance(payload, dict):
        return None

    expected_schema = (
        CHARACTER_SCHEMA
        if expected_kind == "character"
        else PERSONA_SCHEMA
    )

    declared_schema = payload.get("schema")
    if declared_schema:
        if declared_schema != expected_schema:
            return None

        data = payload.get("data")
        return data if isinstance(data, dict) else None

    sheet = payload.get("sheet")
    if isinstance(sheet, dict):
        payload = sheet

    data = payload.get("data")
    if isinstance(data, dict):
        payload = data

    if expected_kind == "character":
        if (
            isinstance(payload.get("identity"), dict)
            and isinstance(payload.get("psychology"), dict)
        ):
            return payload
    else:
        if (
            isinstance(payload.get("identity"), dict)
            and isinstance(payload.get("narration"), dict)
        ):
            return payload

    return None

def _source_payload(payload):
    if isinstance(payload, dict):
        source = payload.get("source")
        if isinstance(source, dict):
            return source
    return {
        "format": "imported",
        "original": payload,
    }

def _reinterpret_payload(payload):
    if not isinstance(payload, dict):
        return payload

    source = payload.get("source")
    if isinstance(source, dict):
        original = source.get("original")
        if isinstance(original, dict):
            return original

    return payload

def heuristic_character_sheet(d):
    name = d.get("name") or "Unnamed"
    # Resolve {{char}}/{{user}} before any card text is copied into the sheet,
    # so a literal "{{user}}" never survives into first_message/history.
    d = _substitute_card_macros(d, name)
    desc = d.get("description") or ""
    personality = d.get("personality") or ""

    sheet = default_character_data(name)
    sheet["embodiment"]["visible"]["summary"] = (
        _first_sentences(desc, 3)
        or "A person of unremarkable appearance."
    )

    traits = [
        value.strip()
        for value in re.split(r"[,;\n]", personality)
        if value.strip()
    ][:10]

    sheet["psychology"]["traits"] = [
        {
            "name": trait,
            "strength": 0.5,
            "expression": "",
        }
        for trait in traits
    ]
    sheet["psychology"]["self_model"]["summary"] = personality[:500]
    sheet["social"]["voice"]["notes"] = _first_sentences(
        d.get("mes_example") or "",
        2,
    )
    sheet["knowledge"]["public_history"] = d.get("scenario") or ""
    sheet["opening"]["first_message"] = d.get("first_mes") or ""
    # Capture first_mes + alternate_greetings as a swipeable greetings list
    # (macros already normalized to {{PLAYER}} above). greeting_id is a stable
    # hash so re-extraction and swipe references survive edits elsewhere.
    raw_greetings = [d.get("first_mes")] + list(d.get("alternate_greetings") or [])
    greetings = []
    for g in raw_greetings:
        text = str(g or "").strip()
        if not text:
            continue
        greetings.append({
            "greeting_id": "greet_" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:16],
            "prose": text,
            "extraction": None,
            "extractor_version": None,
        })
    if greetings:
        sheet["opening"]["greetings"] = greetings
    return sheet

REINT_CHAR_SYS = (
 "Convert this character card into a native simulation-first sheet. "
 "Preserve setting only if it is explicitly supplied; otherwise create a "
 "character with no assumed relationship to the player, beyond what "
 "is directly stated.\n\n"
 "Separate embodiment.visible (currently observable features) from "
 "embodiment.latent (hidden capabilities, transformations, secret "
 "identities, equipment functions). Only visible features belong in the "
 "visible summary.\n\n"
 "Psychology should be behaviorally concrete. Traits include strength "
 "and ordinary expression. Values include priority. The self_model "
 "reflects how the character understands themselves. Coping describes "
 "typical behavior under stress.\n\n"
 "Abilities use honest levels: novice, competent, expert, master, with "
 "scope, limits, and notes. Do not inflate.\n\n"
 "private_history entries include fact_id, content, about_entity, and "
 "known_by. Empty known_by means only the character knows it.\n\n"
 "Output STRICT JSON matching the native character schema:\n"
 "{"
 "\"identity\":{\"uid\":\"\",\"name\":\"\",\"aliases\":[],"
 "\"pronouns\":{\"subject\":\"they\",\"object\":\"them\","
 "\"possessive\":\"their\"}},"
 "\"simulation\":{\"tier\":\"bg|mid|major\","
 "\"temperature\":0.8,\"sampler\":{}},"
 "\"embodiment\":{\"senses\":[{\"channel\":\"vision\","
 "\"acuity\":\"ordinary\",\"range\":\"ordinary\",\"notes\":\"\"}],"
 "\"visible\":{\"summary\":\"\",\"build\":\"\",\"face\":\"\","
 "\"hair\":\"\",\"eyes\":\"\",\"distinctive_features\":[]},"
 "\"latent\":[{\"capability\":\"\",\"visible_when\":\"\","
 "\"limits\":\"\"}]},"
 "\"psychology\":{\"traits\":[{\"name\":\"\",\"strength\":0.5,"
 "\"expression\":\"\"}],"
 "\"values\":[{\"name\":\"\",\"priority\":0.5}],"
 "\"self_model\":{\"summary\":\"\",\"protected_beliefs\":[],"
 "\"pride_triggers\":[],\"shame_triggers\":[]},"
 "\"coping\":{\"under_stress\":[],"
 "\"default_conflict_style\":\"\"}},"
 "\"social\":{\"voice\":{\"register\":\"\",\"cadence\":\"\","
 "\"verbosity\":\"natural\",\"markers\":[],\"notes\":\"\"},"
 "\"baseline_stances\":{\"unknown_person\":{\"trust\":0.0,"
 "\"warmth\":0.0,\"threat_sensitivity\":0.0}}},"
 "\"competence\":{\"abilities\":[{\"name\":\"\","
 "\"level\":\"competent\",\"scope\":\"\",\"limits\":\"\","
 "\"notes\":\"\"}]},"
 "\"knowledge\":{\"access_tags\":[\"common\"],"
 "\"excluded_titles\":[],\"public_history\":\"\","
 "\"private_history\":[{\"fact_id\":\"\",\"content\":\"\","
 "\"about_entity\":\"self\",\"known_by\":[]}]},"
 "\"initial_state\":{\"mood\":{\"label\":\"neutral\","
 "\"valence\":0.0,\"arousal\":0.0},"
 "\"goals\":[{\"goal\":\"\",\"priority\":0.5}],"
 "\"active_concerns\":[]},"
 "\"opening\":{\"first_message\":\"\"}"
 "}."
)

REINT_PERSONA_SYS = (
 "Convert this player persona into a native simulation-first persona. "
 "Do not assume a setting, genre, pre-existing NPC relationships, or "
 "special narrative role unless explicitly supplied.\n\n"
 "Separate visible embodiment from latent capabilities. "
 "narration.voice_setting is private narrator guidance and is never "
 "available to NPCs.\n\n"
 "Output STRICT JSON matching the native persona schema:\n"
 "{"
 "\"identity\":{\"uid\":\"\",\"name\":\"\",\"aliases\":[],"
 "\"pronouns\":{\"subject\":\"they\",\"object\":\"them\","
 "\"possessive\":\"their\"}},"
 "\"embodiment\":{\"senses\":[{\"channel\":\"vision\","
 "\"acuity\":\"ordinary\",\"range\":\"ordinary\",\"notes\":\"\"}],"
 "\"visible\":{\"summary\":\"\",\"build\":\"\",\"face\":\"\","
 "\"hair\":\"\",\"eyes\":\"\",\"distinctive_features\":[]},"
 "\"latent\":[]},"
 "\"competence\":{\"abilities\":[{\"name\":\"\","
 "\"level\":\"competent\",\"scope\":\"\",\"limits\":\"\","
 "\"notes\":\"\"}]},"
 "\"knowledge\":{\"public_history\":\"\","
 "\"private_history\":[{\"fact_id\":\"\",\"content\":\"\","
 "\"about_entity\":\"self\",\"known_by\":[]}]},"
 "\"narration\":{\"voice_setting\":\"\"}"
 "}."
)

def import_character(payload, reinterpret=False):
    native = _native_payload(payload, "character")
    source_payload = _reinterpret_payload(payload)
    card = _card_data(source_payload)

    # A payload already in this project's native schema round-trips
    # exactly via normalize_character_data -- that must win regardless
    # of the reinterpret flag, or re-importing this app's own export
    # would needlessly burn an AI call and risk the sheet drifting from
    # what was actually exported.
    if native is not None:
        sheet = normalize_character_data(native)
    elif reinterpret:
        with _silent_provider_stream():
            try:
                raw = chat_complete(
                    "utility",
                    REINT_CHAR_SYS,
                    json.dumps(source_payload, ensure_ascii=False),
                    max_tokens=5000,
                )
                parsed = _jparse(raw)
                if not parsed:
                    raise RuntimeError(
                        "Character reinterpretation returned no object"
                    )
                sheet = normalize_character_data(parsed)
            except Exception as exc:
                raise RuntimeError(
                    f"AI character reinterpretation failed: {exc}"
                ) from exc
    else:
        sheet = heuristic_character_sheet(card)

    name = character_name(sheet)
    cid = qi(
        "INSERT INTO characters(name,sheet,source,created) "
        "VALUES(?,?,?,?)",
        (
            name,
            json.dumps(sheet, ensure_ascii=False),
            json.dumps(
                _source_payload(payload),
                ensure_ascii=False,
            ),
            time.time(),
        ),
    )

    book = card.get("character_book")
    if isinstance(book, dict) and book.get("entries"):
        import_lorebook(
            _substitute_card_macros(book, name),
            name=f"{name} — book",
            book_type="characters",
            summary=f"Companion lore for {name}.",
        )

    return cid, sheet

def import_persona(payload, reinterpret=False):
    native = _native_payload(payload, "persona")
    source_payload = _reinterpret_payload(payload)
    card = _card_data(source_payload)

    # See import_character: native-schema payloads round-trip exactly
    # and must bypass the reinterpret flag entirely.
    if native is not None:
        sheet = normalize_persona_data(native)
    elif reinterpret:
        with _silent_provider_stream():
            try:
                raw = chat_complete(
                    "utility",
                    REINT_PERSONA_SYS,
                    json.dumps(source_payload, ensure_ascii=False),
                    max_tokens=5000,
                )
                parsed = _jparse(raw)
                if not parsed:
                    raise RuntimeError(
                        "Persona reinterpretation returned no object"
                    )
                sheet = normalize_persona_data(parsed)
            except Exception as exc:
                raise RuntimeError(
                    f"AI persona reinterpretation failed: {exc}"
                ) from exc
    else:
        name = card.get("name") or "Player"
        card = _substitute_card_macros(card, name)
        desc = (
            card.get("description")
            or card.get("personality")
            or ""
        )
        sheet = default_persona_data(name)
        sheet["embodiment"]["visible"]["summary"] = (
            _first_sentences(desc, 3)
            or "A person of unremarkable appearance."
        )
        sheet["narration"]["voice_setting"] = desc

    name = persona_name(sheet)
    pid = qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (
            name,
            json.dumps(sheet, ensure_ascii=False),
            json.dumps(
                _source_payload(payload),
                ensure_ascii=False,
            ),
        ),
    )
    return pid, sheet

def _promotion_evidence(chat_id, name):
    from commit import _background_name_mentioned

    rows = q(
        "SELECT turn_id, content FROM events WHERE chat_id=? ORDER BY turn_id",
        (chat_id,),
    )
    evidence = []
    for r in rows:
        try:
            payload = json.loads(r["content"])
        except Exception:
            continue
        dlog = [
            d for d in (payload.get("dialogue_log") or [])
            if isinstance(d, dict)
        ]
        lines = [
            d for d in dlog
            if str(d.get("speaker") or "").casefold() == name.casefold()
        ]
        event_text = str(payload.get("event") or "")
        mentioned = bool(lines) or _background_name_mentioned(name, event_text)
        if not mentioned:
            continue
        evidence.append({
            "turn": payload.get("turn"),
            "quoted_lines": [
                {"exact_quote": d.get("exact_quote", ""), "tone": d.get("tone", "")}
                for d in lines
            ],
            "resolved_event": event_text,
        })
    return evidence

def draft_promoted_character(chat_id, name):
    """Generate a character sheet + starter memories for a recurring
    background presence (see commit.py's track_background_presences),
    grounded in every turn's actual record of them rather than a blank
    brief. Returns the draft for review -- nothing is written to the
    characters/chat_chars tables here; see app.py's confirm endpoint for
    the actual attach step, so the user can edit before committing.
    """
    evidence = _promotion_evidence(chat_id, name)
    if not evidence:
        raise ValueError(
            f"No recorded turns mention {name!r} in this chat's events"
        )

    with _silent_provider_stream():
        raw = chat_complete(
            "utility",
            get_prompt("promote_character"),
            json.dumps({"name": name, "evidence": evidence}, ensure_ascii=False),
            temperature=0.4,
            max_tokens=5000,
        )

    parsed = _jparse(raw)
    if not parsed or not isinstance(parsed.get("sheet"), dict):
        raise RuntimeError(
            "Promotion generator returned no usable character sheet.\n"
            f"Raw output:\n{raw[:800]}"
        )

    sheet = normalize_character_data(parsed["sheet"])
    # opening.first_message is meaningless for someone already mid-scene
    # -- force it empty regardless of what the model produced, same as
    # the prompt instructs but without depending on it being followed.
    sheet["opening"]["first_message"] = ""
    memory_seeds = [
        str(m) for m in (parsed.get("memory_seeds") or []) if str(m).strip()
    ]
    return {
        "sheet": sheet,
        "memory_seeds": memory_seeds,
        "evidence_turns": [e["turn"] for e in evidence],
    }

def generate_character(brief):
    with _silent_provider_stream():
        raw = chat_complete(
            "utility",
            get_prompt("generator_character"),
            brief or "Create a character.",
            temperature=0.9,
            max_tokens=5000,
        )
    
    parsed = _jparse(raw)
    if not parsed:
        raise RuntimeError(
            "Generator returned no usable character data.\n"
            f"Raw output:\n{raw[:800]}"
        )

    sheet = normalize_character_data(parsed)
    name = character_name(sheet)

    cid = qi(
        "INSERT INTO characters(name,sheet,source,created) "
        "VALUES(?,?,?,?)",
        (
            name,
            json.dumps(sheet, ensure_ascii=False),
            json.dumps(
                {
                    "format": "generated",
                    "generated_from": brief,
                },
                ensure_ascii=False,
            ),
            time.time(),
        ),
    )
    return cid, sheet

def generate_persona(brief):
    with _silent_provider_stream():
        raw = chat_complete(
            "utility",
            get_prompt("generator_persona"),
            brief or "Create a player persona.",
            temperature=0.9,
            max_tokens=5000,
        )
    
    parsed = _jparse(raw)
    if not parsed:
        raise RuntimeError(
            "Generator returned no usable persona data.\n"
            f"Raw output:\n{raw[:800]}"
        )

    sheet = normalize_persona_data(parsed)
    name = persona_name(sheet)

    pid = qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (
            name,
            json.dumps(sheet, ensure_ascii=False),
            json.dumps(
                {
                    "format": "generated",
                    "generated_from": brief,
                },
                ensure_ascii=False,
            ),
        ),
    )
    return pid, sheet

def guess_category(keys, content):
    t = ((keys or "") + " " + (content or "")).lower()

    def anyof(*ws):
        return any(w in t for w in ws)

    if anyof("floor", "hall", "wing", "stair", "basement", "layout",
             "chamber", "corridor", "genkan", "ofuro"):
        return "layout"
    if anyof("magic", "spell", "system", "mechan", "alchem", "technolog",
             "works by", "ritual", "device"):
        return "mechanic"
    if anyof("legend", "myth", "prophec", "believ", "religion", "folklore",
             "god of", "goddess"):
        return "myth"
    if anyof("battle", "war of", "incident", "happened", "founded", "fell in",
             "massacre", "treaty"):
        return "event"
    if anyof("city", "village", "forest", "castle", "tavern", "region",
             "kingdom", "mountain", "temple", "town", "island", "shrine"):
        return "location"
    return "other"

def guess_book_type(entries):
    counts = {}
    for keys, content, _ in entries:
        c = guess_category(keys, content)
        counts[c] = counts.get(c, 0) + 1

    if not counts:
        return "general"

    top = max(counts, key=counts.get)
    if counts[top] < max(2, len(entries) * 0.5):
        return "general"

    return {
        "location": "location",
        "layout": "location",
        "mechanic": "system",
        "event": "events",
        "character": "characters",
        "knowledge": "knowledge",
    }.get(top, "general")

def _batch_entries_by_chars(entries, max_batch_chars):
    batches, current, current_chars = [], [], 0
    for entry in entries:
        entry_chars = len(entry[0]) + len(entry[1])
        if current and current_chars + entry_chars > max_batch_chars:
            batches.append(current)
            current, current_chars = [], 0
        current.append(entry)
        current_chars += entry_chars
    if current:
        batches.append(current)
    return batches

def _reinterpret_entries(entries):
    # A flat 15-entries-per-batch cap paired with a flat max_tokens=3000
    # worked for short, terse world-info-style entries, but this format
    # allows long ones too (imported SillyTavern entries commonly run
    # 1-3k characters each) -- 15 of those in one batch needs far more
    # output budget to rewrite than any flat cap anticipates. A truncated
    # response fails to parse into a usable {"entries": [...]} shape,
    # which used to surface as a bare, unexplained "batch 1: " error.
    # Batch by total character volume instead of entry count, and size
    # max_tokens off each batch's actual volume with real headroom.
    out = []
    batches = _batch_entries_by_chars(entries, max_batch_chars=6000)

    with _silent_provider_stream():
        for i, batch in enumerate(batches):
            batch_chars = sum(len(k) + len(c) for k, c, _ in batch)
            # Rewritten content plus JSON structure/escaping overhead can
            # exceed the source's own size -- budget generously rather
            # than tightly against the estimate.
            max_tokens = max(3000, int(batch_chars / 2))
            raw = None
            try:
                raw = chat_complete(
                    "utility",
                    get_prompt("lore_reinterpret"),
                    json.dumps([
                        {"keys": k, "content": c}
                        for k, c, _ in batch
                    ], ensure_ascii=False),
                    temperature=0.2,
                    max_tokens=max_tokens,
                )
                res = _jparse(raw)
                es = res.get("entries") or []
                if not es:
                    raise RuntimeError(
                        "model returned no usable entries (raw response, "
                        f"first 300 chars: {raw[:300]!r})"
                    )
                for e in es:
                    if e.get("content"):
                        cat = e.get("category")
                        out.append({
                            "keys": e.get("keys", ""),
                            "content": e["content"],
                            "category": (
                                cat
                                if cat in LORE_CATEGORIES
                                else guess_category(
                                    e.get("keys"), e["content"]
                                )
                            ),
                            "locked": 0,
                        })
            except Exception as exc:
                raise RuntimeError(
                    f"Lore reinterpretation failed in batch "
                    f"{i + 1}/{len(batches)}: {exc}"
                ) from exc

    return out

def import_lorebook(payload, name=None, reinterpret=False,
                    book_type=None, summary=None):
    src = payload.get("entries") if isinstance(payload, dict) else payload
    if isinstance(src, dict):
        src = list(src.values())
    # Skip author-disabled entries. World Info exports mark them with
    # `disable: true`; character-card-spec-v2 `character_book` entries use
    # `enabled: false` (default true). Both must be excluded, or an entry the
    # author switched OFF gets imported as active canon lore (audit #24).
    src = [
        e for e in (src or [])
        if isinstance(e, dict) and not e.get("disable") and e.get("enabled", True) is not False
    ]

    # A payload this project exported stamps every entry with the
    # entry_uid add_lore always assigns on creation -- no foreign World
    # Info / character-book export does that. Detect it so a native
    # export round-trips every field (category, title, knowledge_tag,
    # importance, aliases, scope, relations, ...), not just keys/content,
    # and never gets routed through category re-guessing or AI
    # reinterpretation. The entry_uid itself is not reused (it is
    # uniquely indexed -- reusing it would collide on a second import of
    # the same export), so add_lore mints a fresh one, same as how
    # import_character/import_persona mint a fresh resource_uid.
    is_native = bool(src) and all(e.get("entry_uid") for e in src)

    lbname = (
        name
        or (payload.get("name") if isinstance(payload, dict) else None)
        or f"Imported lorebook ({len(src)} entries)"
    )

    if isinstance(payload, dict):
        book_type = book_type or payload.get("book_type")
        summary = summary or payload.get("summary")

    if is_native:
        if book_type not in LOREBOOK_TYPES:
            book_type = "general"
        lb = qi(
            "INSERT INTO lorebooks(name,book_type,summary) VALUES(?,?,?)",
            (lbname, book_type, summary or ""),
        )
        for e in src:
            add_lore(
                lb,
                e.get("keys", ""),
                e.get("content", ""),
                turn_added=e.get("turn_added"),
                locked=e.get("locked", 0),
                category=e.get("category", "other"),
                title=e.get("title"),
                knowledge_tag=e.get("knowledge_tag"),
                knowledge_range=e.get("knowledge_range"),
                knowledge_locations=e.get("knowledge_locations"),
                importance=e.get("importance", 0.5),
                aliases=e.get("aliases"),
                scope=e.get("scope"),
                relations=e.get("relations"),
                source_notes=e.get("source_notes", ""),
            )
        return lb, len(src)

    entries = []
    for e in src:
        keys = e.get("key") or e.get("keys") or []
        if isinstance(keys, list):
            keys = ", ".join(map(str, keys))

        content = e.get("content") or e.get("entry") or ""
        if content:
            entries.append((
                keys,
                content,
                1 if e.get("constant") else 0,
            ))

    if book_type not in LOREBOOK_TYPES:
        book_type = guess_book_type(entries)

    lb = qi(
        "INSERT INTO lorebooks(name,book_type,summary) VALUES(?,?,?)",
        (lbname, book_type, summary or ""),
    )

    if reinterpret and entries:
        try:
            reinterpreted_entries = _reinterpret_entries(entries)
            for e in reinterpreted_entries:
                add_lore(
                    lb,
                    e["keys"],
                    e["content"],
                    turn_added=None,
                    locked=e["locked"],
                    category=e["category"],
                )
            return lb, len(reinterpreted_entries)
        except Exception as exc:
            raise RuntimeError(
                f"AI lore reinterpretation failed: {exc}"
            ) from exc

    for keys, content, locked in entries:
        add_lore(
            lb,
            keys,
            content,
            turn_added=None,
            locked=locked,
            category=guess_category(keys, content),
        )

    return lb, len(entries)

def reinterpret_lorebook(lid):
    from db import q
    from memory import delete_lore

    rows = q(
        "SELECT * FROM lore_entries WHERE lorebook_id=?",
        (lid,),
    )
    unlocked = [
        (r["keys"], r["content"], 0)
        for r in rows
        if not r["canon_locked"]
    ]

    if not unlocked:
        return 0

    redone = _reinterpret_entries(unlocked)

    for r in rows:
        if not r["canon_locked"]:
            delete_lore(r["id"])

    for e in redone:
        add_lore(
            lid,
            e["keys"],
            e["content"],
            turn_added=None,
            locked=0,
            category=e["category"],
        )

    return len(redone)

def generate_lorebook_plan(lorebook_id, brief, mode="expand_tree", depth=2,
                           entry_target=40, allow_new_books=True,
                           allow_links=True, allow_updates=True,
                           preserve_locked=True):
    from db import q
    from memory import lorebook_manifest, lorebook_descendants

    book = q(
        "SELECT * FROM lorebooks WHERE id=?",
        (lorebook_id,),
        one=True,
    )
    if not book:
        raise ValueError("Lorebook not found")

    # Gather context: book summaries, category counts, titles/keys
    book_ids = lorebook_descendants(lorebook_id)
    if not book_ids:
        book_ids = [lorebook_id]
    
    books_ctx = []
    category_counts = {}
    existing_titles = set()
    existing_entries = []
    
    for bid in book_ids:
        lb = q("SELECT * FROM lorebooks WHERE id=?", (bid,), one=True)
        if not lb:
            continue
        entries = q(
            "SELECT keys, content, category, title, canon_locked FROM lore_entries WHERE lorebook_id=?",
            (bid,),
        )
        n = len(entries)
        books_ctx.append({
            "id": bid,
            "name": lb["name"],
            "book_type": lb["book_type"],
            "summary": lb["summary"],
            "entry_count": n,
            "parent_id": lb["parent_id"],
        })
        for e in entries:
            cat = e["category"] or "other"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if e["title"]:
                existing_titles.add(e["title"])
            existing_entries.append({
                "book_id": bid,
                "keys": e["keys"],
                "title": e["title"],
                "category": cat,
                "content": e["content"],
                "locked": bool(e["canon_locked"]),
            })
    
    # For large books, only send full content for a sample
    if len(existing_entries) > 50:
        # Send full content for first 20, titles+keys for rest
        full_entries = existing_entries[:20]
        summary_entries = [
            {"book_id": e["book_id"], "keys": e["keys"], "title": e["title"],
             "category": e["category"], "locked": e["locked"]}
            for e in existing_entries[20:]
        ]
        existing_context = full_entries + summary_entries
    else:
        existing_context = existing_entries

    payload = {
        "request": brief or "Create useful lore entries.",
        "mode": mode,
        "depth": depth,
        "entry_target": entry_target,
        "allow_new_books": allow_new_books,
        "allow_links": allow_links,
        "allow_updates": allow_updates,
        "preserve_locked": preserve_locked,
        "selected_book_id": lorebook_id,
        "books": books_ctx,
        "category_counts": category_counts,
        "existing_entries": existing_context,
        "link_types": LOREBOOK_LINK_TYPES,
        "lore_categories": LORE_CATEGORIES,
        "lorebook_types": LOREBOOK_TYPES,
    }

    with _silent_provider_stream():
        raw = chat_complete(
            "utility",
            get_prompt("generator_lorebook"),
            json.dumps(payload, ensure_ascii=False),
            temperature=0.7,
            max_tokens=8000,
        )

    parsed = _jparse(raw)
    if not parsed:
        raise RuntimeError(
            "Lore generator returned no usable plan.\n"
            f"Raw output:\n{raw[:800]}"
        )

    parsed = _jparse(raw)
    if not parsed:
        raise RuntimeError(
            "Lore generator returned no usable plan.\n"
            f"Raw output:\n{raw[:800]}"
        )

    # Normalize: if the LLM returned flat entries instead of
    # structured entry_ops, convert them so the plan preview
    # and apply_lorebook_plan can process them.
    flat_entries = parsed.get("entries")
    if isinstance(flat_entries, list) and flat_entries:
        existing_ops = parsed.get("entry_ops")
        if not isinstance(existing_ops, list) or not existing_ops:
            parsed["entry_ops"] = [
                {
                    "op": "create",
                    "book_id": lorebook_id,
                    "keys": e.get("keys", ""),
                    "content": e.get("content", ""),
                    "category": e.get("category", "other"),
                    "title": e.get("title"),
                    "knowledge_tag": e.get("knowledge_tag"),
                    "knowledge_range": e.get("knowledge_range"),
                    "knowledge_locations": e.get("knowledge_locations", []),
                }
                for e in flat_entries
                if isinstance(e, dict) and e.get("content")
            ]
            parsed.pop("entries", None)

    return parsed

def apply_lorebook_plan(plan, chat_id=None):
    from memory import add_lore, update_lore, add_lorebook_link
    from db import q, qi
    
    created_books = {}
    created_entries = []
    created_links = []
    
    # Process book ops
    for book_op in plan.get("book_ops", []):
        if book_op.get("op") != "create":
            continue
        parent_id = book_op.get("parent_id")
        if isinstance(parent_id, str) and parent_id in created_books:
            parent_id = created_books[parent_id]
        elif isinstance(parent_id, str):
            parent_id = None
        
        bid = qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,summary,parent_id,inheritance_mode,sort_order) VALUES(?,?,?,?,?,?,?)",
            (
                book_op.get("name", "New book"),
                chat_id,
                book_op.get("book_type", "general"),
                book_op.get("summary", ""),
                parent_id,
                book_op.get("inheritance_mode", "inherit"),
                book_op.get("sort_order", 0),
            ),
        )
        created_books[book_op.get("temp_id", f"book_{bid}")] = bid
    
    # Process entry ops
    for entry_op in plan.get("entry_ops", []):
        book_id = entry_op.get("book_id") or entry_op.get("book_temp_id")
        if isinstance(book_id, str) and book_id in created_books:
            book_id = created_books[book_id]
        elif isinstance(book_id, str):
            book_id = None
        
        if not book_id:
            continue
        
        if entry_op.get("op") == "update" and entry_op.get("id"):
            entry_id = entry_op["id"]
            update_lore(
                entry_id,
                entry_op.get("keys", ""),
                entry_op.get("content", ""),
                category=entry_op.get("category"),
                title=entry_op.get("title"),
                knowledge_tag=entry_op.get("knowledge_tag"),
                knowledge_range=entry_op.get("knowledge_range"),
                knowledge_locations=entry_op.get("knowledge_locations"),
                importance=entry_op.get("importance", 0.5),
                aliases=entry_op.get("aliases", []),
                scope=entry_op.get("scope", {}),
                relations=entry_op.get("relations", {}),
                source_notes=entry_op.get("source_notes", ""),
            )
            created_entries.append(entry_id)
        elif entry_op.get("op") == "create":
            eid = add_lore(
                book_id,
                entry_op.get("keys", ""),
                entry_op.get("content", ""),
                category=entry_op.get("category", "other"),
                title=entry_op.get("title"),
                knowledge_tag=entry_op.get("knowledge_tag"),
                knowledge_range=entry_op.get("knowledge_range"),
                knowledge_locations=entry_op.get("knowledge_locations"),
                importance=entry_op.get("importance", 0.5),
                aliases=entry_op.get("aliases", []),
                scope=entry_op.get("scope", {}),
                relations=entry_op.get("relations", {}),
                source_notes=entry_op.get("source_notes", ""),
            )
            created_entries.append(eid)
    
    # Process link ops
    for link_op in plan.get("link_ops", []):
        source_id = link_op.get("source_id") or link_op.get("source_book_id")
        target_id = link_op.get("target_id") or link_op.get("target_book_id")
        
        if isinstance(source_id, str) and source_id in created_books:
            source_id = created_books[source_id]
        if isinstance(target_id, str) and target_id in created_books:
            target_id = created_books[target_id]
        
        if not isinstance(source_id, int) or not isinstance(target_id, int):
            continue
        
        try:
            lid = add_lorebook_link(
                source_id, target_id,
                relation_type=link_op.get("relation_type", "related"),
                label=link_op.get("label", ""),
                notes=link_op.get("notes", ""),
                bidirectional=link_op.get("bidirectional", True),
                follow_for_retrieval=link_op.get("follow_for_retrieval", True),
                weight=link_op.get("weight", 0.75),
            )
            created_links.append(lid)
        except Exception:
            pass
    
    return {
        "books_created": len(created_books),
        "entries_created": len(created_entries),
        "links_created": len(created_links),
    }
def generate_lore_entries(lorebook_id, brief):
    from db import q

    book = q("SELECT * FROM lorebooks WHERE id=?", (lorebook_id,), one=True)
    if not book:
        raise ValueError("Lorebook not found")

    existing = q(
        "SELECT keys, content, category, title FROM lore_entries "
        "WHERE lorebook_id=?",
        (lorebook_id,),
    )
    existing_ctx = [
        {"keys": r["keys"], "content": r["content"],
         "category": r["category"], "title": r["title"]}
        for r in existing
    ]

    payload = {
        "request": brief or "Create useful lore entries.",
        "book": {
            "name": book["name"],
            "book_type": book["book_type"],
            "summary": book["summary"],
        },
        "existing_entries": existing_ctx[:50],
    }

    with _silent_provider_stream():
        raw = chat_complete(
            "utility",
            get_prompt("generator_lorebook"),
            json.dumps(payload, ensure_ascii=False),
            temperature=0.7,
            max_tokens=8000,
        )

    parsed = _jparse(raw)
    entries = parsed.get("entries") or []
    if not entries:
        raise RuntimeError(
            "Lore generator returned no entries.\n"
            f"Raw output:\n{raw[:800]}"
        )

    entry_ids = []
    for e in entries:
        if not e.get("content"):
            continue
        cat = e.get("category")
        if cat not in LORE_CATEGORIES:
            cat = guess_category(e.get("keys", ""), e["content"])
        eid = add_lore(
            lorebook_id,
            e.get("keys", ""),
            e["content"],
            category=cat,
            title=e.get("title"),
            knowledge_tag=e.get("knowledge_tag"),
            knowledge_range=e.get("knowledge_range"),
            knowledge_locations=e.get("knowledge_locations"),
        )
        entry_ids.append(eid)

    return entry_ids