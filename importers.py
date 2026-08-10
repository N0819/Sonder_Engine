import copy, json, time, re, uuid, base64, struct, zlib, hashlib, numpy as np
from contextlib import contextmanager
from db import q, qi, transaction
from logging_utils import logger
from memory import (
    add_lore, LORE_CATEGORIES, LOREBOOK_TYPES, LOREBOOK_LINK_TYPES,
    KNOWLEDGE_TAGS, KNOWLEDGE_RANGES, add_lorebook_link,
)
from providers import (
    chat_complete, token_sink, embed_texts, request_timeout,
    clamp_read_timeout,
)
from prompts import get_prompt
from character_schema import (
    CHARACTER_SCHEMA,
    PERSONA_SCHEMA,
    character_name,
    default_character_data,
    default_persona_data,
    new_uid,
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

def _prepared_lore_embeddings(entries):
    """Resolve entry vectors before opening the import write transaction."""
    vectors = [None] * len(entries)
    missing = []
    for idx, entry in enumerate(entries):
        raw = entry.get("embedding")
        if isinstance(raw, str):
            try:
                decoded = base64.b64decode(raw.encode("ascii"), validate=True)
                if decoded and len(decoded) % 4 == 0:
                    vectors[idx] = np.frombuffer(decoded, dtype=np.float32).copy()
            except (ValueError, TypeError):
                pass
        if vectors[idx] is None:
            missing.append(idx)
    if missing:
        texts = [
            f"{entries[idx].get('keys') or ''} {entries[idx].get('content') or ''}"
            for idx in missing
        ]
        for idx, vector in zip(missing, embed_texts(texts)):
            vectors[idx] = vector
    return vectors

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

def _card_greetings(card, name):
    """first_mes + alternate_greetings -> the swipeable opening.greetings list,
    macros resolved. Shared by every import path (heuristic AND AI-reinterpret)
    and by recover_greetings, so alternate greetings are captured no matter how
    the rest of the sheet was built. greeting_id is a stable content hash so a
    re-capture of the same prose keeps the same id."""
    if not isinstance(card, dict):
        return []
    raw = [card.get("first_mes")] + list(card.get("alternate_greetings") or [])
    out = []
    for g in raw:
        text = _substitute_macros(str(g or ""), name).strip()
        if not text:
            continue
        out.append({
            "greeting_id": "greet_" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:16],
            "prose": text,
            "extraction": None,
            "extractor_version": None,
        })
    return out

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


_OUTFIT_LINE_RE = re.compile(
    r"(?im)^[ \t]*(?:initial outfit|outfit|clothing|attire|wearing)"
    r"[ \t]*:[ \t]*(.+?)[ \t]*$"
)


def _outfit_items(value):
    if isinstance(value, dict):
        value = value.get("wearing") or value.get("items") or []
    if isinstance(value, str):
        value = re.split(r"[;\n]+", value)
    if not isinstance(value, list):
        value = [value] if value else []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _heuristic_appearance_and_outfit(card):
    """Separate labeled/direct clothing from stable body appearance."""
    description = str(card.get("description") or "")
    direct = (
        card.get("initial_outfit")
        or card.get("outfit")
        or card.get("clothing")
        or card.get("attire")
    )
    wearing = _outfit_items(direct)
    for match in _OUTFIT_LINE_RE.finditer(description):
        for item in _outfit_items(match.group(1)):
            if item not in wearing:
                wearing.append(item)
    appearance = _OUTFIT_LINE_RE.sub("", description)
    appearance = re.sub(r"\n{3,}", "\n\n", appearance).strip()
    return appearance, {"wearing": wearing, "state": []}


def heuristic_character_sheet(d):
    name = d.get("name") or "Unnamed"
    # Resolve {{char}}/{{user}} before any card text is copied into the sheet,
    # so a literal "{{user}}" never survives into first_message/history.
    d = _substitute_card_macros(d, name)
    desc, initial_outfit = _heuristic_appearance_and_outfit(d)
    personality = d.get("personality") or ""

    sheet = default_character_data(name)
    sheet["initial_outfit"] = initial_outfit
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
    # (macros already normalized to {{PLAYER}} above; _card_greetings is
    # idempotent on already-substituted text).
    greetings = _card_greetings(d, name)
    if greetings:
        sheet["opening"]["greetings"] = greetings
    return sheet

REINT_CHAR_SYS = (
 "Convert this character card into a native simulation-first sheet. "
 "Preserve setting only if it is explicitly supplied; otherwise create a "
 "character with no assumed relationship to the player, beyond what "
 "is directly stated.\n\n"
 "Separate embodiment.visible from embodiment.latent AND from initial_outfit. "
 "embodiment.visible is stable BODY appearance only: build, face, hair, eyes, "
 "skin, scars, and other features that remain when clothes change. Hidden "
 "capabilities, transformations, secret identities, and equipment functions "
 "belong in latent. Put every garment/accessory currently worn in "
 "initial_outfit.wearing; never repeat outfit text in the appearance summary.\n\n"
 "Psychology should be behaviorally concrete and conditional. Traits include "
 "strength, ordinary expression, activation cues, and inhibitors. Values include "
 "priority, behavioral expression, and conflicts. The self_model includes a few "
 "durable self/world beliefs with confidence and emotional charge. Coping "
 "strategies name triggers, responses, effectiveness, and costs. Learned "
 "associations must be supported by the card's history or examples and remain "
 "biases, never irresistible commands. Do not assign diagnoses.\n\n"
 # Mirrors generator_character/promote_character in prompts.py. Those two
 # were given this guidance and this template slot; the import path was
 # not (it keeps its own schema prompt here), so every imported character
 # arrived with an empty drive and no standing goals -- i.e. permanently
 # reactive, with nothing to say about it.
 "DRIVE is the deepest thing this character lives for -- REQUIRED and "
 "load-bearing: the engine derives the character's proactive wants from "
 "it every beat, so a blank drive makes the character passive. essence = "
 "the core they protect/pursue (concrete, not a platitude); expression = "
 "how it shows in behavior, INCLUDING their initiative; taboo = the line "
 "they will not cross. Infer it from the card -- its description, "
 "personality, scenario and example dialogue all evidence what this "
 "character wants. Make expression drive ACTION, not just restraint.\n\n"
 "STANDING GOALS (initial_state.goals) are the character's durable "
 "objectives -- REQUIRED, 1-3 concrete goals with priority. These are "
 "what the character proactively pursues turn to turn; without them the "
 "character only ever reacts to others. Make them active and specific to "
 "who they are.\n\n"
 "Abilities use honest levels: novice, competent, expert, master, with "
 "scope, limits, and notes. Do not inflate.\n\n"
 "private_history entries include fact_id, content, about_entity, and "
 "known_by. Empty known_by means only the character knows it.\n\n"
 "Output STRICT JSON matching the native character schema:\n"
 "{"
 "\"identity\":{\"uid\":\"\",\"name\":\"\",\"aliases\":[],"
 "\"pronouns\":{\"subject\":\"they\",\"object\":\"them\","
 "\"possessive\":\"their\"}},"
 "\"initial_outfit\":{\"wearing\":[],\"state\":[]},"
 "\"simulation\":{\"tier\":\"bg|mid|major\","
 "\"temperature\":0.8,\"sampler\":{}},"
 "\"embodiment\":{\"senses\":[{\"channel\":\"vision\","
 "\"acuity\":\"ordinary\",\"range\":\"ordinary\",\"notes\":\"\"}],"
 "\"visible\":{\"summary\":\"\",\"build\":\"\",\"face\":\"\","
 "\"hair\":\"\",\"eyes\":\"\",\"distinctive_features\":[]},"
 "\"latent\":[{\"capability\":\"\",\"visible_when\":\"\","
 "\"limits\":\"\"}],\"interoception\":{\"acuity\":0.5,"
 "\"pain_sensitivity\":0.5,\"fatigue_sensitivity\":0.5,"
 "\"pleasure_sensitivity\":0.5}},"
 "\"psychology\":{\"drive\":{\"essence\":\"\",\"expression\":\"\","
 "\"taboo\":\"\"},"
 "\"traits\":[{\"name\":\"\",\"strength\":0.5,"
 "\"expression\":\"\",\"activation_cues\":[],\"inhibited_by\":[]}],"
 "\"values\":[{\"name\":\"\",\"priority\":0.5,\"expression\":\"\","
 "\"conflicts_with\":[]}],"
 "\"self_model\":{\"summary\":\"\",\"protected_beliefs\":[],"
 "\"pride_triggers\":[],\"shame_triggers\":[],"
 "\"beliefs\":[{\"belief\":\"\",\"confidence\":0.5,\"protected\":false,"
 "\"emotional_charge\":0.0,\"source\":\"\"}]},"
 "\"coping\":{\"under_stress\":[],"
 "\"default_conflict_style\":\"\",\"strategies\":[{\"name\":\"\","
 "\"trigger\":\"\",\"response\":\"\",\"effectiveness\":0.5,\"costs\":\"\"}],"
 "\"recovery_supports\":[]},"
 "\"stress_profile\":{\"baseline_reactivity\":0.5,\"recovery_rate\":0.5,"
 "\"overload_threshold\":0.8,\"attentional_style\":\"\",\"somatic_signs\":[]},"
 "\"learning\":{\"associations\":[{\"cue\":\"\",\"appraisal_bias\":\"\","
 "\"response_tendency\":\"\",\"strength\":0.5,\"generalization_tags\":[]}]}},"
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
 "\"active_concerns\":[],\"stress\":{\"activation\":0.0,\"load\":0.0,"
 "\"coping_mode\":\"\"},\"hedonic\":{\"pain\":0.0,\"pleasure\":0.0,"
 "\"source\":\"\"}},"
 "\"opening\":{\"first_message\":\"\"}"
 "}."
)

REINT_PERSONA_SYS = (
 "Convert this player persona into a native simulation-first persona. "
 "Do not assume a setting, genre, pre-existing NPC relationships, or "
 "special narrative role unless explicitly supplied.\n\n"
 "Separate visible embodiment from latent capabilities AND from clothing. "
 "embodiment.visible is stable BODY appearance only; every starting "
 "garment/accessory belongs in initial_outfit.wearing and must not be repeated "
 "in the appearance summary. "
 "narration.voice_setting is private narrator guidance and is never "
 "available to NPCs.\n\n"
 "Output STRICT JSON matching the native persona schema:\n"
 "{"
 "\"identity\":{\"uid\":\"\",\"name\":\"\",\"aliases\":[],"
 "\"pronouns\":{\"subject\":\"they\",\"object\":\"them\","
 "\"possessive\":\"their\"}},"
 "\"initial_outfit\":{\"wearing\":[],\"state\":[]},"
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
                payload_json = json.dumps(source_payload, ensure_ascii=False)
                # Scale the budget off the card's own volume, the same way
                # _reinterpret_entries does for lorebook batches. A flat 5000
                # was fine for a terse card and silently truncating for a long
                # one -- and a truncated sheet does not fail loudly, because
                # _jparse's brace repair turns it into a parseable object with
                # the tail nested in the wrong place (see
                # character_schema.repair_character_shape).
                max_tokens = max(5000, int(len(payload_json) / 2))
                raw = chat_complete(
                    "utility",
                    REINT_CHAR_SYS,
                    payload_json,
                    max_tokens=max_tokens,
                )
                parsed = _jparse(raw)
                if not parsed:
                    raise RuntimeError(
                        "Character reinterpretation returned no object"
                    )
                sheet = normalize_character_data(parsed)
                # The model does not get to name the engine's key for this
                # character. identity.uid IS the scene entity id (scene.py's
                # entity_id falls back to it) and one of the forms character
                # matching keys off, so a model-authored value -- GLM returns
                # the character's own name, "tamamo" -- makes every import of
                # that card THE SAME ENTITY: two characters sharing one
                # position, one set of clothes, one owner of the memories.
                # A native re-import keeps its uid (that path is above and
                # untouched); anything a model reconstructed gets a fresh one.
                sheet["identity"]["uid"] = new_uid("char")
            except Exception as exc:
                raise RuntimeError(
                    f"AI character reinterpretation failed: {exc}"
                ) from exc
    else:
        sheet = heuristic_character_sheet(card)

    name = character_name(sheet)
    # Capture the author's greetings for the swipe/quick-start UI on EVERY
    # import path. heuristic_character_sheet already fills this; the AI-
    # reinterpret path does not (the model returns a fresh sheet with no
    # greetings), so without this backfill alternate greetings were silently
    # lost for reinterpreted imports. Greetings are verbatim authored prose and
    # must survive regardless of how the rest of the sheet was built.
    opening = sheet.setdefault("opening", {})
    if not opening.get("greetings"):
        greetings = _card_greetings(card, name)
        if greetings:
            opening["greetings"] = greetings
            if not opening.get("first_message"):
                opening["first_message"] = greetings[0]["prose"]
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


def character_import_warnings(sheet):
    """What is missing from an imported sheet that will make the character
    read as passive, as a list of human-readable strings.

    psychology.drive is where every proactive want comes from (prompts.py's
    WANTS AND GOALS rule) and initial_state.goals are the durable objectives
    on top of it. A card that supplies neither imports cleanly and then only
    ever reacts -- which looks like a dull character rather than a missing
    field, so it has to be said out loud at import time. The heuristic
    (LLM-free) path cannot invent either one by construction.
    """
    warnings = []
    psychology = sheet.get("psychology") or {}
    drive = psychology.get("drive") or {}
    if not str(drive.get("essence") or "").strip():
        warnings.append(
            "No drive was authored for this character, so they will react "
            "rather than pursue anything. Add psychology.drive in the "
            "character editor, or re-import with AI reinterpretation."
        )
    if not (sheet.get("initial_state") or {}).get("goals"):
        warnings.append(
            "No standing goals were authored, so this character has nothing "
            "they are trying to achieve between beats."
        )
    # Not a defect -- the default is exactly the pair every story ran on before
    # this dial existed, so an unset one cannot misbehave. It is named because
    # nobody looks for a field they do not know is there, and a character who
    # should be single-minded or should juggle will otherwise be authored at
    # the middle rung forever by omission.
    if not str(psychology.get("capacity") or "").strip():
        warnings.append(
            "No attentional capacity was authored, so this character holds the "
            "ordinary three wants and four intentions. Set psychology.capacity "
            "(narrow / focused / ordinary / broad / wide) to make them "
            "single-minded or to let them keep more in the air at once."
        )
    return warnings

def recover_greetings_from_source(char_id):
    """Backfill opening.greetings for an already-imported character from its
    stored source card (first_mes + alternate_greetings). Imports made via the
    AI-reinterpret path (or before greeting capture existed) never stored the
    alternate greetings; this recovers them losslessly without a re-import.
    Returns the updated sheet, or None if there was nothing to recover."""
    row = q("SELECT id,sheet,source FROM characters WHERE id=?", (char_id,), one=True)
    if not row:
        return None
    sheet = json.loads(row["sheet"] or "{}")
    opening = sheet.setdefault("opening", {})
    if opening.get("greetings"):
        return sheet  # already present -- nothing to do
    src = json.loads(row["source"] or "{}")
    original = src.get("original") if isinstance(src, dict) else None
    card = _card_data(original) if isinstance(original, dict) else {}
    greetings = _card_greetings(card, character_name(sheet))
    if not greetings:
        return None
    opening["greetings"] = greetings
    if not opening.get("first_message"):
        opening["first_message"] = greetings[0]["prose"]
    qi("UPDATE characters SET sheet=? WHERE id=?",
       (json.dumps(sheet, ensure_ascii=False), char_id))
    return sheet

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
                # Same as the character path above: a reconstructed sheet does
                # not carry a model-chosen identity key.
                sheet["identity"]["uid"] = new_uid("persona")
            except Exception as exc:
                raise RuntimeError(
                    f"AI persona reinterpretation failed: {exc}"
                ) from exc
    else:
        name = card.get("name") or "Player"
        card = _substitute_card_macros(card, name)
        desc, initial_outfit = _heuristic_appearance_and_outfit(card)
        if not desc:
            desc = card.get("personality") or ""
        sheet = default_persona_data(name)
        sheet["initial_outfit"] = initial_outfit
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
    # Nor is the NAME the model's to choose, and for the same reason. It is
    # what the scene has been calling this person, the key
    # `background_presences` tracks them under, and the speaker label their
    # quoted lines were matched on. Meanwhile the evidence pack is full of
    # OTHER people's names -- the player's most of all, since `resolved_event`
    # is the whole beat, not just this person's part in it. Left to the model,
    # a spice seller and a young shopper in one market were BOTH minted
    # carrying the player persona's name.
    sheet.setdefault("identity", {})["name"] = name
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


def _merge_missing_fields(existing, proposed):
    """Recursively fill empty card fields without replacing authored content."""
    if isinstance(existing, dict) and isinstance(proposed, dict):
        result = copy.deepcopy(existing)
        for key, value in proposed.items():
            if key not in result:
                result[key] = copy.deepcopy(value)
            else:
                result[key] = _merge_missing_fields(result[key], value)
        return result
    if isinstance(existing, list) and isinstance(proposed, list):
        if not existing:
            return copy.deepcopy(proposed)
        if all(isinstance(item, dict) for item in [*existing, *proposed]):
            result = copy.deepcopy(existing)
            for candidate in proposed:
                identity = next((
                    str(candidate.get(key) or "").strip().casefold()
                    for key in ("name", "belief", "cue")
                    if str(candidate.get(key) or "").strip()
                ), "")
                match = next((
                    idx for idx, current in enumerate(result)
                    if identity and any(
                        str(current.get(key) or "").strip().casefold() == identity
                        for key in ("name", "belief", "cue")
                    )
                ), None)
                if match is None:
                    result.append(copy.deepcopy(candidate))
                else:
                    result[match] = _merge_missing_fields(
                        result[match], candidate)
            return result
        return copy.deepcopy(existing)
    if existing is None or existing == "" or existing == [] or existing == {}:
        return copy.deepcopy(proposed)
    return copy.deepcopy(existing)


def fill_character_psychology(char_id, brief):
    """Preview an AI fill of missing psychology/interoception fields.

    The existing card remains unchanged until the editor's normal Save action.
    This lets an author review the generated completion and keeps this helper
    from turning a generation request into an implicit write.
    """
    row = q("SELECT sheet FROM characters WHERE id=?", (char_id,), one=True)
    if not row:
        raise ValueError("Character not found")
    stored = json.loads(row["sheet"] or "{}")
    normalized = normalize_character_data(stored)
    payload = {
        "brief": str(brief or "").strip(),
        "character": normalized,
    }
    with _silent_provider_stream():
        raw = chat_complete(
            "utility",
            get_prompt("fill_character_psychology"),
            json.dumps(payload, ensure_ascii=False),
            temperature=0.65,
            max_tokens=5000,
        )
    proposed = _jparse(raw)
    if not proposed:
        raise RuntimeError(
            "Psychology fill returned no usable data.\n"
            f"Raw output:\n{raw[:800]}"
        )
    restricted = {}
    if isinstance(proposed.get("psychology"), dict):
        restricted["psychology"] = proposed["psychology"]
    embodiment = proposed.get("embodiment")
    if isinstance(embodiment, dict) and isinstance(
            embodiment.get("interoception"), dict):
        restricted["embodiment"] = {
            "interoception": embodiment["interoception"],
        }
    initial = proposed.get("initial_state")
    if isinstance(initial, dict):
        allowed_initial = {
            key: initial[key] for key in ("stress", "hedonic")
            if isinstance(initial.get(key), dict)
        }
        if allowed_initial:
            restricted["initial_state"] = allowed_initial
    # Merge into the stored (pre-normalization) card so fields absent on a v2
    # card are distinguishable from v3's neutral defaults.
    merged = _merge_missing_fields(stored, restricted)
    return normalize_character_data(merged)


def _json_arrived_whole(text):
    """Did this response contain a COMPLETE JSON object, or a salvaged one?

    `_jparse` recovers a cut-off response by closing its open braces, which is
    right for a pipeline beat that must not die and wrong for a generator whose
    result a person is about to read: a half-written outfit comes back looking
    exactly like a finished one. Checking that the text ends in `}` is not
    enough -- a truncation lands immediately after a closing brace often
    enough, and then the tail of the object is simply missing.

    So: strict parse of the outermost braced block, with no repair of any kind.
    Prose on either side of it is fine; that is a complete answer with chatter
    around it, not a truncated one.
    """
    stripped = re.sub(
        r"^```[a-zA-Z]*\n?|```$", "", str(text or "").strip(), flags=re.M).strip()
    match = re.search(r"\{.*\}", stripped, re.S)
    if not match:
        return False
    try:
        json.loads(match.group(0))
    except Exception:
        return False
    return True


def fill_appearance(kind, entity_id, brief, include_beneath=False, draft=None):
    """Preview an AI fill of one card's body and clothing.

    Like `fill_character_psychology`, this WRITES NOTHING -- the editor shows
    the proposal and the author's ordinary Save is what commits it. A
    generation request that quietly rewrote a card would make "let me see what
    it comes up with" an irreversible act.

    `draft` is what the author currently has typed in the editor, which may not
    be what is stored: generating from the saved copy would ignore the two
    lines they just wrote, which is exactly when they press the button.

    Unlike the psychology fill, this one REPLACES rather than fills gaps. Body
    and clothing are a single coherent description -- a generated outfit under
    a hand-written summary that contradicts it is worse than either alone -- so
    the author reviews a whole proposal and keeps or discards it.
    """
    table = "characters" if kind == "character" else "personas"
    normalize = (normalize_character_data if kind == "character"
                 else normalize_persona_data)
    row = q(f"SELECT sheet FROM {table} WHERE id=?", (entity_id,), one=True)
    if not row:
        raise ValueError("Card not found")
    stored = json.loads(row["sheet"] or "{}")
    normalized = normalize(stored)
    draft = draft if isinstance(draft, dict) else {}
    payload = {
        "brief": str(brief or "").strip(),
        "include_beneath": bool(include_beneath),
        "card": normalized,
        "author_draft": {
            "appearance": draft.get("appearance") or {},
            "initial_outfit": draft.get("initial_outfit") or {},
        },
    }
    with _silent_provider_stream():
        raw = chat_complete(
            "utility",
            get_prompt("fill_appearance"),
            json.dumps(payload, ensure_ascii=False),
            temperature=0.8,
            # None means the configured ceiling, not a hardcoded budget. A
            # reasoning model bills its thinking as output, so a fixed few
            # thousand tokens is spent deliberating before any JSON is emitted
            # and the call returns an EMPTY string -- see the same finding in
            # llm_quality.complete_validated_json (maze arm A11).
            max_tokens=None,
        )
    proposed = _jparse(raw)
    if not proposed:
        # Distinguish the two failures: nothing came back at all, versus
        # something came back that was not JSON. They have different causes and
        # the message used to show neither, because it printed an empty string.
        if not str(raw or "").strip():
            raise RuntimeError(
                "The model returned nothing. This usually means the output "
                "budget ran out before any JSON was written — a reasoning "
                "model spends its thinking on that budget. Raise "
                "'Max output tokens' in Settings, or point the `utility` role "
                "at a non-reasoning model."
            )
        raise RuntimeError(
            "Appearance fill returned no usable data.\n"
            f"Raw output:\n{raw[:800]}"
        )
    if not _json_arrived_whole(raw):
        raise RuntimeError(
            "The model ran out of output budget partway through and the "
            "result was cut off. Raise 'Max output tokens' in Settings, or "
            "point the `utility` role at a non-reasoning model — a reasoning "
            "model spends that same budget on its thinking."
        )
    merged = copy.deepcopy(stored)
    visible = ((proposed.get("embodiment") or {}).get("visible")
               if isinstance(proposed.get("embodiment"), dict) else None)
    if isinstance(visible, dict):
        merged.setdefault("embodiment", {})
        if not isinstance(merged["embodiment"], dict):
            merged["embodiment"] = {}
        merged["embodiment"]["visible"] = {
            **(merged["embodiment"].get("visible") or {}), **visible}
    outfit = proposed.get("initial_outfit")
    if isinstance(outfit, dict):
        if not include_beneath:
            # Belt and braces against a model that answered the question it
            # was not asked. The setting governs whether `beneath` is USED;
            # this governs whether it is written onto a card at all.
            for entry in (outfit.get("regions") or {}).values():
                if isinstance(entry, dict):
                    entry["beneath"] = ""
                    entry["beneath_zones"] = {}
        merged["initial_outfit"] = outfit
    return normalize(merged)


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

def _structure_key(content):
    """A stable handle for matching a prepared entry back to its source.

    Index alignment cannot be used: the rewrite SPLITS entries (the live
    Re:Zero import produced 310 rows from 300 sources), so position drifts.
    The opening of the text survives a rewrite far better than its length or
    its keys do, and both halves of a split entry legitimately inherit the same
    structural facts -- both halves of "Lugunica Currency" are still local
    knowledge about Lugunica.
    """
    text = " ".join(str(content or "").split()).casefold()
    return text[:120] if text else ""


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
    failures = []
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
                # ONE BAD BATCH USED TO LOSE THE WHOLE BOOK. This raised, and
                # `import_lorebook` turned it into "AI lore reinterpretation
                # failed" -- so on the 300-entry, 354,677-character Re:Zero
                # book, roughly 59 batches deep, a single malformed response
                # discarded every batch that had already succeeded and every
                # one that would have.
                #
                # Two escalating recoveries, in the order that costs least:
                first_error = exc
                recovered = None
                if raw:
                    # 1. REPAIR. The model is handed back its own output and
                    #    the error, never the source payload again -- the same
                    #    shape llm_quality.complete_validated_json uses, and
                    #    affordable for the same reason: closing a bracket does
                    #    not need the question restated. One attempt, never a
                    #    loop; a model that cannot emit valid JSON twice will
                    #    not manage it on the fifth, and a repair loop is how a
                    #    429 becomes a bill.
                    try:
                        fixed = chat_complete(
                            "utility",
                            get_prompt("lore_reinterpret"),
                            json.dumps({
                                "instruction": (
                                    "Your previous reply could not be used. "
                                    "Return the SAME entries as valid JSON of "
                                    "the form {\"entries\": [...]}, preserving "
                                    "every entry and all of its content."),
                                "error": str(exc)[:400],
                                "previous_reply": raw[:20000],
                            }, ensure_ascii=False),
                            temperature=0.1,
                            max_tokens=max_tokens,
                        )
                        recovered = (_jparse(fixed) or {}).get("entries") or []
                    except Exception:
                        recovered = None
                if recovered:
                    for e in recovered:
                        if e.get("content"):
                            cat = e.get("category")
                            out.append({
                                "keys": e.get("keys", ""),
                                "content": e["content"],
                                "category": (cat if cat in LORE_CATEGORIES
                                             else guess_category(e.get("keys"),
                                                                 e["content"])),
                                "locked": 0,
                            })
                    failures.append(
                        f"batch {i + 1}/{len(batches)}: recovered by repair "
                        f"after {first_error}")
                    continue
                # 2. KEEP THE SOURCE. A batch that cannot be rewritten is
                #    imported UNREWRITTEN rather than dropped: the author's own
                #    text, categorised heuristically. Losing the model's
                #    polish on a few entries is a far smaller harm than losing
                #    the entries, and the import stays a complete book.
                for k, c, locked in batch:
                    out.append({"keys": k, "content": c, "locked": locked,
                                "category": guess_category(k, c)})
                failures.append(
                    f"batch {i + 1}/{len(batches)}: kept {len(batch)} "
                    f"entries unrewritten after {first_error}")

    if failures:
        logger.warning("lore reinterpretation: %d of %d batches degraded; %s",
                       len(failures), len(batches), "; ".join(failures[:5]))
    return out

def import_lorebook(payload, name=None, reinterpret=False,
                    book_type=None, summary=None):
    payload_meta = payload if isinstance(payload, dict) else {}
    src = payload_meta.get("entries") if payload_meta else payload
    if isinstance(src, dict):
        src = list(src.values())
    # Skip author-disabled entries. World Info exports mark them with
    # `disable: true`; character-card-spec-v2 `character_book` entries use
    # `enabled: false` (default true). Both must be excluded, or an entry the
    # author switched OFF gets imported as active canon lore (audit #24).
    src = [
        e for e in (src or [])
        if isinstance(e, dict) and not e.get("disable")
        and e.get("enabled", True) not in (False, 0)
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
        vectors = _prepared_lore_embeddings(src)
        with transaction():
            lb = qi(
                "INSERT INTO lorebooks("
                "name,book_type,summary,scope_world_id,scope_location_id,"
                "inheritance_mode,sort_order,anchor_entity_id"
                ") VALUES(?,?,?,?,?,?,?,?)",
                (
                    lbname,
                    book_type,
                    summary or "",
                    payload_meta.get("scope_world_id"),
                    payload_meta.get("scope_location_id"),
                    payload_meta.get("inheritance_mode") or "inherit",
                    int(payload_meta.get("sort_order") or 0),
                    payload_meta.get("anchor_entity_id"),
                ),
            )
            for e, vector in zip(src, vectors):
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
                    embedding=vector,
                )
        return lb, len(src)

    # THE TREE THE AUTHOR DREW IN THE TITLES. A World Info book is a flat list
    # and every large one is really a tree, rendered with rule characters in
    # `comment` -- a field that appeared NOWHERE in this module, so 300 titles
    # and 116 explicit parent/child relations went in the bin on every import.
    #
    # It is recovered before the rewrite because it is the only principled
    # source for the knowledge fields: `[>] Lugunica Currency` sitting under
    # `[castle] Dragon Kingdom of Lugunica` says structurally that this is LOCAL
    # knowledge about Lugunica, which is what lets an innkeeper there be
    # expected to know it. Asking a model that per entry would cost 300 calls
    # and answer worse -- the author already encoded it, in the layout.
    structure = {}
    try:
        from lore_structure import derive_knowledge, parse_structure
        for record in parse_structure(src):
            body = _structure_key(record.get("content"))
            if body:
                tag, rng, locs = derive_knowledge(record)
                structure[body] = {
                    "title": record.get("title") or "",
                    # The `[>]` parent, by TITLE. Ids do not exist yet, so the
                    # link is resolved in a second pass after every row has one.
                    "parent_title": record.get("parent") or "",
                    "knowledge_tag": tag,
                    "knowledge_range": rng,
                    "knowledge_locations": locs,
                    # `constant` in the source means always-injected, which is
                    # the author saying this one matters more than the rest.
                    # Everything used to land on a flat 0.5.
                    "importance": 0.9 if record.get("constant") else 0.5,
                }
    except Exception:
        structure = {}

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

    if reinterpret and entries:
        try:
            reinterpreted_entries = _reinterpret_entries(entries)
        except Exception as exc:
            raise RuntimeError(
                f"AI lore reinterpretation failed: {exc}"
            ) from exc
        prepared_entries = reinterpreted_entries
    else:
        prepared_entries = [
            {
                "keys": keys,
                "content": content,
                "locked": locked,
                "category": guess_category(keys, content),
            }
            for keys, content, locked in entries
        ]

    vectors = _prepared_lore_embeddings(prepared_entries)
    with transaction():
        lb = qi(
            "INSERT INTO lorebooks("
            "name,book_type,summary,scope_world_id,scope_location_id,"
            "inheritance_mode,sort_order,anchor_entity_id"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (
                lbname,
                book_type,
                summary or "",
                payload_meta.get("scope_world_id"),
                payload_meta.get("scope_location_id"),
                payload_meta.get("inheritance_mode") or "inherit",
                int(payload_meta.get("sort_order") or 0),
                payload_meta.get("anchor_entity_id"),
            ),
        )
        inserted = []
        for entry, vector in zip(prepared_entries, vectors):
            meta = structure.get(_structure_key(entry["content"])) or {}
            inserted.append((meta, add_lore(
                lb,
                entry["keys"],
                entry["content"],
                turn_added=None,
                locked=entry["locked"],
                category=entry["category"],
                embedding=vector,
                title=meta.get("title") or None,
                knowledge_tag=meta.get("knowledge_tag"),
                knowledge_range=meta.get("knowledge_range"),
                knowledge_locations=meta.get("knowledge_locations"),
                importance=meta.get("importance", 0.5),
            )))

        # THE `[>]` TREE, as `relations.refines_entry_ids`. That vocabulary
        # already exists and already means this -- "Lugunica Currency" refines
        # "Dragon Kingdom of Lugunica" -- so the hierarchy needs no new column
        # and no entry moved between books, which would have orphaned every
        # chat_lorebooks link and every entry_uid a story has cited.
        #
        # A SECOND PASS because a parent's row id does not exist while its
        # children are being written. Titles are unique enough within one book
        # to resolve on; a title that resolves to nothing is left unlinked
        # rather than guessed at.
        by_title = {}
        for meta, row_id in inserted:
            title = (meta.get("title") or "").strip()
            if title and title not in by_title:
                by_title[title] = row_id
        for meta, row_id in inserted:
            parent = (meta.get("parent_title") or "").strip()
            parent_id = by_title.get(parent)
            if not parent_id or parent_id == row_id:
                continue
            qi("UPDATE lore_entries SET relations=? WHERE id=?",
               (json.dumps({"supersedes_entry_id": None,
                            "refines_entry_ids": [parent_id],
                            "contradicts_entry_ids": []}), row_id))

    return lb, len(prepared_entries)

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

# ===================== RESUMABLE LOREBOOK-TREE GENERATION =====================
# Generating a lorebook tree is many model calls, not one: a cheap "structure"
# call that decides the books, links and an outline of the entries, then one
# call per batch of outlined entries. Every one of those calls can be lost to a
# dropped stream, an exhausted provider retry budget, a closed browser tab, or
# a server restart -- and before this, losing any of them lost ALL of them.
#
# Each completed unit of work is now written to lore_gen_jobs the moment it
# lands, so recovery has something to recover: resuming re-runs only the units
# that never finished. Nothing here writes lore -- the plan stays provisional
# until the user applies it, which is still the only path that touches
# lorebooks/lore_entries.

# Stamped on every job this process starts. A 'running' row carrying a
# DIFFERENT token was orphaned when that process died, which is an
# interruption -- detected exactly, with no staleness timeout to tune.
_GEN_OWNER = uuid.uuid4().hex

# Statuses worth telling the user about when they reopen the generator.
# 'ready' is included deliberately: a run whose plan finished generating but
# whose HTTP response never reached the browser is the cheapest recovery of
# all -- the work is done, only the delivery was lost.
LORE_GEN_RECOVERABLE = ("running", "interrupted", "failed", "ready")

# Outlined entries expanded per model call. Small enough that one lost call
# costs little and each entry gets a real share of the output budget; large
# enough that a 40-entry tree is ~7 calls rather than 40.
LORE_GEN_ENTRY_BATCH = 6

# Newest runs kept per book; older rows are pruned when a run starts.
LORE_GEN_KEEP_PER_BOOK = 5


class LoreGenError(RuntimeError):
    """A generation run stopped without producing a usable plan.

    `interrupted` distinguishes "the network/provider dropped out" from "the
    model returned something unusable" -- the caller shows a different message
    for each, but both name a job_id that resume can pick up, because resuming
    re-runs from the first incomplete unit either way.
    """

    def __init__(self, message, job_id=None, interrupted=False):
        super().__init__(message)
        self.job_id = job_id
        self.interrupted = interrupted


def _is_interruption(exc):
    """True when a run stopped on transport, not on content.

    chat_complete has already exhausted its own retry budget by the time
    anything reaches us, so a transient error surfacing here means the
    provider or the connection is genuinely unavailable right now -- stop and
    offer a resume rather than marching the remaining batches into the same
    wall.
    """
    from providers import (
        Aborted, LLMError, DEFAULT_RETRY, TRANSIENT_NETWORK_ERRORS,
    )

    if isinstance(exc, (Aborted, TRANSIENT_NETWORK_ERRORS)):
        return True
    if isinstance(exc, LLMError):
        return bool(exc.retryable) or exc.status_code in DEFAULT_RETRY.retryable_status
    return False


def _jdict(text, default=None):
    try:
        value = json.loads(text or "")
    except Exception:
        return {} if default is None else default
    return value if isinstance(value, dict) else ({} if default is None else default)


def _chunked(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


def _empty_plan():
    return {"analysis": {}, "book_ops": [], "link_ops": [], "entry_ops": []}


def _plan_shape(plan):
    """Every op list present, whatever a stored row happens to hold.

    A resumed run reads its plan back out of the database, so the run loop
    must never be the thing that discovers a missing key.
    """
    plan = plan if isinstance(plan, dict) else {}
    if not isinstance(plan.get("analysis"), dict):
        plan["analysis"] = {}
    for key in ("book_ops", "link_ops", "entry_ops"):
        if not isinstance(plan.get(key), list):
            plan[key] = []
    return plan


# ---- job store ------------------------------------------------------------

def _gen_job_row(job_id):
    return q("SELECT * FROM lore_gen_jobs WHERE id=?", (job_id,), one=True)


def _gen_save(job_id, plan=None, progress=None, **fields):
    if plan is not None:
        fields["plan"] = json.dumps(plan, ensure_ascii=False)
    if progress is not None:
        fields["progress"] = json.dumps(progress, ensure_ascii=False)
    fields["updated"] = time.time()

    assignments = ", ".join(f"{name}=?" for name in fields)
    qi(
        f"UPDATE lore_gen_jobs SET {assignments} WHERE id=?",
        (*fields.values(), job_id),
    )


def _gen_job_create(lorebook_id, params):
    now = time.time()
    job_id = qi(
        "INSERT INTO lore_gen_jobs(lorebook_id,status,stage,params,plan,"
        "progress,error,owner,attempts,created,updated) "
        "VALUES(?,'running','structure',?,'{}','{}','',?,1,?,?)",
        (
            lorebook_id,
            json.dumps(params, ensure_ascii=False),
            _GEN_OWNER,
            now,
            now,
        ),
    )
    # Only the newest few runs per book are ever offered for recovery, so the
    # rest are dead weight. Pruning on create (rather than on a timer) keeps
    # this to one statement on a path that is already doing model calls.
    qi(
        "DELETE FROM lore_gen_jobs WHERE lorebook_id=? AND id NOT IN "
        "(SELECT id FROM lore_gen_jobs WHERE lorebook_id=? "
        "ORDER BY id DESC LIMIT ?)",
        (lorebook_id, lorebook_id, LORE_GEN_KEEP_PER_BOOK),
    )
    return job_id


def _gen_reap_orphans(lorebook_id=None):
    """Reclassify runs abandoned by a dead process as interruptions.

    A 'running' row can only be genuinely live if this process is the one
    running it; anything else is a crash or restart, and the user should be
    offered the resume rather than staring at a spinner that owns nothing.
    """
    sql = "SELECT id FROM lore_gen_jobs WHERE status='running' AND owner<>?"
    args = [_GEN_OWNER]
    if lorebook_id is not None:
        sql += " AND lorebook_id=?"
        args.append(lorebook_id)

    for row in q(sql, tuple(args)):
        _gen_save(
            row["id"],
            status="interrupted",
            error="Interrupted: the server stopped while this generation was running.",
        )


def _gen_job_public(row):
    """The job as the API and UI see it: decoded, with derived counts."""
    plan = _plan_shape(_jdict(row["plan"], _empty_plan()))
    progress = _jdict(row["progress"])
    outline = progress.get("outline") or []
    done = sum(1 for stub in outline if stub.get("state") == "done")
    status = row["status"]

    return {
        "id": row["id"],
        "lorebook_id": row["lorebook_id"],
        "status": status,
        "stage": row["stage"],
        "params": _jdict(row["params"]),
        "plan": plan,
        "error": row["error"] or "",
        "attempts": row["attempts"],
        "created": row["created"],
        "updated": row["updated"],
        "entries_total": len(outline),
        "entries_done": done,
        "entries_remaining": len(outline) - done,
        "stage_errors": progress.get("stage_errors") or [],
        # Work remains that a resume would continue rather than duplicate.
        "resumable": status in ("interrupted", "failed"),
        # The plan is finished and merely needs handing back to the client.
        "restorable": status == "ready",
        "running": status == "running" and row["owner"] == _GEN_OWNER,
    }


def lore_gen_job(job_id):
    row = _gen_job_row(job_id)
    return _gen_job_public(row) if row else None


def recoverable_lore_gen_job(lorebook_id):
    """The newest run for this book that the user could still recover, or None."""
    _gen_reap_orphans(lorebook_id)
    placeholders = ",".join("?" for _ in LORE_GEN_RECOVERABLE)
    row = q(
        f"SELECT * FROM lore_gen_jobs WHERE lorebook_id=? AND status IN "
        f"({placeholders}) ORDER BY id DESC LIMIT 1",
        (lorebook_id, *LORE_GEN_RECOVERABLE),
        one=True,
    )
    return _gen_job_public(row) if row else None


def cancel_lore_gen_job(job_id):
    row = _gen_job_row(job_id)
    if not row:
        raise ValueError("Generation job not found")
    _gen_save(job_id, status="cancelled")
    return True


def mark_lore_gen_job_applied(job_id):
    """Applying a plan retires its job -- it must not resurface as recoverable
    work once its entries are real lore."""
    row = _gen_job_row(job_id)
    if not row:
        return False
    _gen_save(job_id, status="applied")
    return True


def _gen_result(job_id):
    """What the API hands back: the plan, carrying its job under `_job`.

    Keeping the plan itself as the top-level shape is deliberate -- the
    preview/apply path already consumes exactly that, and only the recovery UI
    needs the job block.
    """
    job = _gen_job_public(_gen_job_row(job_id))
    plan = job.pop("plan")
    plan["_job"] = job
    return plan


def _gen_record_failure(job_id, exc, plan, progress):
    interrupted = _is_interruption(exc)
    message = str(exc) or exc.__class__.__name__
    _gen_save(
        job_id,
        status="interrupted" if interrupted else "failed",
        error=(("Interrupted: " if interrupted else "") + message)[:2000],
        plan=plan,
        progress=progress,
    )
    return interrupted


# ---- shared generation context -------------------------------------------

def _lore_gen_context(lorebook_id):
    """Book/entry context for a generation run.

    Rebuilt from the database on every call, including on resume: the job
    stores the REQUEST, never this, so a resumed run sees the tree as it is
    now rather than as it was when the run first started.
    """
    from memory import lorebook_descendants

    book_ids = lorebook_descendants(lorebook_id) or [lorebook_id]

    books_ctx = []
    category_counts = {}
    existing_titles = []
    existing_entries = []

    for bid in book_ids:
        lb = q("SELECT * FROM lorebooks WHERE id=?", (bid,), one=True)
        if not lb:
            continue
        entries = q(
            "SELECT keys, content, category, title, canon_locked "
            "FROM lore_entries WHERE lorebook_id=?",
            (bid,),
        )
        books_ctx.append({
            "id": bid,
            "name": lb["name"],
            "book_type": lb["book_type"],
            "summary": lb["summary"],
            "entry_count": len(entries),
            "parent_id": lb["parent_id"],
        })
        for e in entries:
            cat = e["category"] or "other"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if e["title"]:
                existing_titles.append(e["title"])
            existing_entries.append({
                "book_id": bid,
                "keys": e["keys"],
                "title": e["title"],
                "category": cat,
                "content": e["content"],
                "locked": bool(e["canon_locked"]),
            })

    # For large trees, only the first slice carries full content; the rest go
    # as titles/keys so the prompt stays a sane size.
    if len(existing_entries) > 50:
        digest = existing_entries[:20] + [
            {"book_id": e["book_id"], "keys": e["keys"], "title": e["title"],
             "category": e["category"], "locked": e["locked"]}
            for e in existing_entries[20:]
        ]
    else:
        digest = existing_entries

    return {
        "selected_book_id": lorebook_id,
        "books": books_ctx,
        "category_counts": category_counts,
        "existing_entries": digest,
        "existing_titles": existing_titles,
    }


def _normalize_entry_ops(parsed, default_book_id):
    """Finished entry ops out of whatever shape the model used.

    Handles both the documented entry_ops list and the flat `entries` list
    looser responses return, so a model that answers the structure call with
    complete entries (or a custom prompt preset predating staged generation)
    still produces a usable plan.
    """
    ops = [
        dict(op) for op in (parsed.get("entry_ops") or [])
        if isinstance(op, dict) and str(op.get("content") or "").strip()
    ]
    if ops:
        for op in ops:
            # `apply_lorebook_plan` dispatches on this key, so an op that omits
            # it -- or claims an update it cannot address, having no id -- is
            # dropped after a generation the author watched succeed. The
            # prompt documents "op", which is not the same as the model
            # always sending it.
            if op.get("op") != "update" or not op.get("id"):
                op["op"] = "create"
                op.pop("id", None)
            # `importance` reaches float() inside add_lore. One model
            # answering "high" would otherwise abort a whole approved plan
            # inside its transaction, losing every other entry with it.
            try:
                op["importance"] = float(op.get("importance", 0.5))
            except (TypeError, ValueError):
                op["importance"] = 0.5
        return ops

    return [
        {
            "op": "create",
            "book_id": default_book_id,
            "keys": e.get("keys", ""),
            "content": e.get("content", ""),
            "category": e.get("category", "other"),
            "title": e.get("title"),
            "knowledge_tag": e.get("knowledge_tag"),
            "knowledge_range": e.get("knowledge_range"),
            "knowledge_locations": e.get("knowledge_locations", []),
        }
        for e in (parsed.get("entries") or [])
        if isinstance(e, dict) and str(e.get("content") or "").strip()
    ]


def _normalize_book_id(value, valid_temp_ids, default_book_id):
    """A stub/op book reference resolved to an int id or a real temp_id.

    An unresolvable reference falls back to the selected book rather than
    dropping the entry: misfiling one entry is recoverable by hand, silently
    losing a generated entry is not.
    """
    if isinstance(value, bool):
        return default_book_id
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text in valid_temp_ids:
            return text
        try:
            return int(text)
        except ValueError:
            return default_book_id
    return default_book_id


def _normalize_outline(raw_outline, plan, params, default_book_id):
    """Model outline stubs -> the resumable unit-of-work list.

    Each stub carries a stable `index` (how a batch's entries are matched back
    to their stub) and a `state` that is the entire resume mechanism: only
    stubs that are not yet 'done' are ever regenerated.
    """
    valid_temp_ids = {
        str(op.get("temp_id")) for op in plan["book_ops"] if op.get("temp_id")
    }
    try:
        target = int(params.get("entry_target") or 40)
    except (TypeError, ValueError):
        target = 40
    # A runaway outline would otherwise commit the run to hundreds of calls.
    cap = max(1, min(target * 2, 200))

    outline = []
    seen = set()

    for stub in (raw_outline or []):
        if not isinstance(stub, dict):
            continue
        title = str(stub.get("title") or stub.get("keys") or "").strip()
        if not title:
            continue
        dedupe_key = title.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        category = stub.get("category")
        item = {
            "index": len(outline),
            "book_id": _normalize_book_id(
                stub.get("book_id"), valid_temp_ids, default_book_id
            ),
            "title": title,
            "keys": str(stub.get("keys") or "").strip(),
            "category": category if category in LORE_CATEGORIES else "other",
            "focus": str(stub.get("focus") or "").strip(),
            "op": "update" if stub.get("op") == "update" and stub.get("id") else "create",
            "state": "pending",
        }
        if item["op"] == "update":
            item["id"] = stub.get("id")

        outline.append(item)
        if len(outline) >= cap:
            break

    return outline


# ---- stage 1: structure ---------------------------------------------------

def _lore_gen_structure(params, ctx):
    payload = {
        "request": params.get("brief") or "Create useful lore entries.",
        # The stage key is what switches the generator prompt into outline
        # mode. A model (or an older custom preset) that ignores it and
        # returns finished entry_ops is handled below, not treated as failure.
        "stage": "structure",
        "mode": params.get("mode", "expand_tree"),
        "depth": params.get("depth", 2),
        "entry_target": params.get("entry_target", 40),
        "allow_new_books": params.get("allow_new_books", True),
        "allow_links": params.get("allow_links", True),
        "allow_updates": params.get("allow_updates", True),
        "preserve_locked": params.get("preserve_locked", True),
        "selected_book_id": ctx["selected_book_id"],
        "books": ctx["books"],
        "category_counts": ctx["category_counts"],
        "existing_entries": ctx["existing_entries"],
        "link_types": LOREBOOK_LINK_TYPES,
        "lore_categories": LORE_CATEGORIES,
        "lorebook_types": LOREBOOK_TYPES,
    }

    with _silent_provider_stream(), request_timeout(params.get("timeout")):
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
            f"Raw output:\n{(raw or '')[:800]}"
        )

    plan = {
        "analysis": parsed.get("analysis") if isinstance(parsed.get("analysis"), dict) else {},
        "book_ops": [op for op in (parsed.get("book_ops") or []) if isinstance(op, dict)],
        "link_ops": [op for op in (parsed.get("link_ops") or []) if isinstance(op, dict)],
        "entry_ops": [],
    }

    direct = _normalize_entry_ops(parsed, ctx["selected_book_id"])
    if direct:
        # One-call run: the entries are already written, so there is nothing
        # to batch and nothing left that an interruption could cost.
        plan["entry_ops"] = direct
        return plan, []

    outline = _normalize_outline(
        parsed.get("entry_outline"), plan, params, ctx["selected_book_id"]
    )
    if not outline and not plan["book_ops"] and not plan["link_ops"]:
        # Parseable but empty in every dimension -- proposing nothing at all is
        # a failed generation, not a plan, and marking it 'ready' would present
        # an empty result as a finished one.
        raise RuntimeError(
            "Lore generator proposed no books, links, or entries.\n"
            f"Raw output:\n{(raw or '')[:800]}"
        )

    return plan, outline


# ---- stage 2: entry batches ----------------------------------------------

def _lore_gen_entry_batch(params, ctx, plan, batch):
    written = [
        str(op.get("title") or op.get("keys") or "").strip()
        for op in plan["entry_ops"]
    ]
    payload = {
        "request": params.get("brief") or "Create useful lore entries.",
        "mode": params.get("mode", "expand_tree"),
        "selected_book_id": ctx["selected_book_id"],
        # Books planned by the structure call are listed alongside real ones:
        # a stub can be filed into a book that does not exist yet.
        "books": ctx["books"] + [
            {
                "temp_id": op.get("temp_id"),
                "name": op.get("name"),
                "book_type": op.get("book_type"),
                "summary": op.get("summary"),
                "parent_id": op.get("parent_id"),
                "planned": True,
            }
            for op in plan["book_ops"]
        ],
        "existing_entries": ctx["existing_entries"],
        "already_written_titles": (
            ctx["existing_titles"][:80] + [t for t in written if t][-80:]
        ),
        "batch": [
            {
                "outline_index": stub["index"],
                "book_id": stub["book_id"],
                "title": stub["title"],
                "keys": stub.get("keys", ""),
                "category": stub.get("category", "other"),
                "focus": stub.get("focus", ""),
                "op": stub.get("op", "create"),
                **({"id": stub["id"]} if stub.get("id") else {}),
            }
            for stub in batch
        ],
        "lore_categories": LORE_CATEGORIES,
        "knowledge_tags": KNOWLEDGE_TAGS,
        "knowledge_ranges": KNOWLEDGE_RANGES,
    }

    with _silent_provider_stream(), request_timeout(params.get("timeout")):
        raw = chat_complete(
            "utility",
            get_prompt("generator_lorebook_entries"),
            json.dumps(payload, ensure_ascii=False),
            temperature=0.7,
            # Budgeted per stub rather than flat, for the same reason
            # _reinterpret_entries does it: a flat ceiling truncates the JSON
            # and costs the whole batch.
            max_tokens=max(3000, 1200 * len(batch)),
        )

    parsed = _jparse(raw)
    if not parsed:
        raise RuntimeError(
            "model returned unparseable JSON (first 300 chars: "
            f"{(raw or '')[:300]!r})"
        )

    ops = _normalize_entry_ops(parsed, ctx["selected_book_id"])
    if not ops:
        raise RuntimeError(
            "model returned no usable entries (first 300 chars: "
            f"{(raw or '')[:300]!r})"
        )

    # Re-anchor every op onto its stub. The stub -- not the model's echo -- is
    # the authority on which book an entry belongs to and whether it updates
    # an existing entry, so a model that drops outline_index or rewrites
    # book_id cannot misfile lore or turn an update into a duplicate.
    by_index = {stub["index"]: stub for stub in batch}
    anchored = []
    covered = set()

    for op in ops[:len(batch)]:
        stub = by_index.get(op.get("outline_index"))
        if stub is None or stub["index"] in covered:
            # No usable echo, or an echo pointing at a stub already written.
            # Fall back to the next unwritten stub rather than letting one
            # index claim the whole batch and duplicate a single subject.
            stub = next(
                (item for item in batch if item["index"] not in covered),
                None,
            )
            if stub is None:
                break

        covered.add(stub["index"])
        op = dict(op)
        op.pop("outline_index", None)
        op["book_id"] = stub["book_id"]

        if stub.get("op") == "update" and stub.get("id"):
            op["op"] = "update"
            op["id"] = stub["id"]
        else:
            op["op"] = "create"
            op.pop("id", None)

        if not str(op.get("title") or "").strip():
            op["title"] = stub["title"]
        if not str(op.get("keys") or "").strip():
            op["keys"] = stub.get("keys") or stub["title"]
        if op.get("category") not in LORE_CATEGORIES:
            op["category"] = (
                stub["category"] if stub.get("category") in LORE_CATEGORIES
                else guess_category(op.get("keys", ""), op.get("content", ""))
            )

        anchored.append(op)

    # `covered` is what the caller marks done. A short response therefore
    # leaves the stubs it skipped pending instead of silently dropping them.
    return anchored, covered


# ---- the run loop --------------------------------------------------------

def _run_lore_gen_job(job_id):
    row = _gen_job_row(job_id)
    params = _jdict(row["params"])
    plan = _plan_shape(_jdict(row["plan"], _empty_plan()))
    progress = _jdict(row["progress"])
    # Scoped to THIS attempt: the durable record of what is left to do is the
    # outline's own stub states, so carrying a previous attempt's complaints
    # forward would keep reporting failures a resume has already fixed.
    progress["stage_errors"] = []

    ctx = _lore_gen_context(row["lorebook_id"])

    if row["stage"] == "structure":
        try:
            plan, outline = _lore_gen_structure(params, ctx)
        except Exception as exc:
            # Nothing usable exists yet, so there is no partial plan to hand
            # back. The job still holds the request, so a resume re-runs
            # exactly this call without the user retyping anything.
            interrupted = _gen_record_failure(job_id, exc, plan, progress)
            raise LoreGenError(
                (
                    "Lorebook generation was interrupted before any of the "
                    f"plan was written: {exc}"
                    if interrupted else
                    f"Lorebook generation failed while planning the tree: {exc}"
                ),
                job_id=job_id,
                interrupted=interrupted,
            ) from exc

        progress["outline"] = outline
        _gen_save(job_id, stage="entries", plan=plan, progress=progress)

    outline = progress.get("outline") or []
    # 'failed' stubs are picked up here too, which is what makes a resume
    # retry the batches that produced unusable output.
    pending = [stub for stub in outline if stub.get("state") != "done"]

    for batch in _chunked(pending, LORE_GEN_ENTRY_BATCH):
        try:
            ops, covered = _lore_gen_entry_batch(params, ctx, plan, batch)
        except Exception as exc:
            if _is_interruption(exc):
                # The provider or the connection is down. Stop -- every batch
                # already written stays written, and the remaining stubs are
                # left pending for a resume.
                _gen_record_failure(job_id, exc, plan, progress)
                if plan["entry_ops"] or plan["book_ops"]:
                    # There IS a usable partial plan: hand it back so it can
                    # be reviewed, applied, or resumed, instead of throwing
                    # away work the user already paid for.
                    return _gen_result(job_id)
                raise LoreGenError(
                    "Lorebook generation was interrupted before any entries "
                    f"were written: {exc}",
                    job_id=job_id,
                    interrupted=True,
                ) from exc

            # Unusable output for THIS batch only. One bad batch must not
            # cost the other twelve, so record it and carry on; the resume
            # retries just these stubs.
            for stub in batch:
                stub["state"] = "failed"
            progress["stage_errors"].append(
                f"{len(batch)} entries starting at #{batch[0]['index'] + 1}: {exc}"[:500]
            )
            _gen_save(job_id, plan=plan, progress=progress)
            continue

        plan["entry_ops"].extend(ops)
        for stub in batch:
            stub["state"] = "done" if stub["index"] in covered else "failed"

        # A response shorter than its batch is a partial batch, not a
        # complete one: the stubs it skipped stay retriable.
        skipped = len(batch) - len(covered)
        if skipped > 0:
            progress["stage_errors"].append(
                f"{skipped} of {len(batch)} entries starting at "
                f"#{batch[0]['index'] + 1} were not returned by the model"
            )

        # Persisted per batch: this line is what makes the next interruption
        # cost one batch instead of the whole run.
        _gen_save(job_id, plan=plan, progress=progress)

    failed = [stub for stub in outline if stub.get("state") != "done"]
    if failed:
        _gen_save(
            job_id,
            status="interrupted",
            stage="entries",
            error=(
                f"{len(failed)} of {len(outline)} entries could not be "
                "generated. Resume to retry just those."
            ),
            plan=plan,
            progress=progress,
        )
    else:
        _gen_save(
            job_id,
            status="ready",
            stage="done",
            error="",
            plan=plan,
            progress=progress,
        )

    return _gen_result(job_id)


def generate_lorebook_plan(lorebook_id, brief, mode="expand_tree", depth=2,
                           entry_target=40, allow_new_books=True,
                           allow_links=True, allow_updates=True,
                           preserve_locked=True, timeout=None):
    """Plan a lorebook-tree expansion. Writes nothing but its own job row.

    Returns the plan dict (analysis/book_ops/link_ops/entry_ops) with the
    generation job under `_job`. Raises LoreGenError -- naming a job that can
    be resumed -- only when the run produced no usable plan at all.

    `timeout` raises the per-call read timeout above the 300s default, for slow
    local models that are still producing tokens when it expires. It is stored
    with the request, so a resume runs under the same allowance.
    """
    if not q("SELECT id FROM lorebooks WHERE id=?", (lorebook_id,), one=True):
        raise ValueError("Lorebook not found")

    job_id = _gen_job_create(lorebook_id, {
        "brief": brief or "",
        "mode": mode,
        "depth": depth,
        "entry_target": entry_target,
        "allow_new_books": allow_new_books,
        "allow_links": allow_links,
        "allow_updates": allow_updates,
        "preserve_locked": preserve_locked,
        "timeout": clamp_read_timeout(timeout),
    })
    return _run_lore_gen_job(job_id)


def resume_lorebook_plan(job_id, timeout=None):
    """Continue a stopped run from its first incomplete unit of work.

    Completed structure and completed entry batches are never regenerated. A
    run that already reached 'ready' is simply handed back -- its plan was
    generated and only the delivery was lost.

    `timeout` raises the read timeout for the remaining work. A read timeout is
    itself one of the interruptions this recovers from, so the retry has to be
    able to give the model longer than the attempt that just ran out of it.
    """
    row = _gen_job_row(job_id)
    if not row:
        raise ValueError("Generation job not found")
    if row["status"] in ("applied", "cancelled"):
        raise ValueError(
            f"That generation was already {row['status']} and cannot be resumed."
        )
    if row["status"] == "running" and row["owner"] == _GEN_OWNER:
        raise ValueError("That generation is still running.")
    if not q("SELECT id FROM lorebooks WHERE id=?", (row["lorebook_id"],), one=True):
        raise ValueError("The lorebook this generation targeted no longer exists.")

    if row["status"] == "ready":
        return _gen_result(job_id)

    fields = {
        "status": "running",
        "owner": _GEN_OWNER,
        "error": "",
        "attempts": int(row["attempts"] or 0) + 1,
    }

    raised = clamp_read_timeout(timeout)
    if raised is not None:
        # Persisted, not just applied: every later batch and every later
        # resume of this run inherits the longer allowance.
        params = _jdict(row["params"])
        params["timeout"] = raised
        fields["params"] = json.dumps(params, ensure_ascii=False)

    _gen_save(job_id, **fields)
    return _run_lore_gen_job(job_id)

def _plan_parent_id(raw_parent, created_books, root_id, chat_id):
    """Where a planned book actually hangs.

    `commit.py`'s `_apply_mapping_book_ops` already refuses to leave a new book
    unreachable ("keeps the tree rooted under canon -- never an unreachable
    orphan"); this is the same rule for the generator's apply path, which did
    not have it. A chat-owned book with parent_id NULL and no chat_lorebooks
    row is reachable from nothing: lore retrieval walks out from canon plus
    attachments, so the book's entries can never reach play, and an
    ownership-blind browser could not even show it.

    Resolution order: a temp_id created by this same plan, then a real existing
    book, then the book the plan was generated for, then the chat's canon.
    """
    if isinstance(raw_parent, str):
        resolved = created_books.get(raw_parent)
        if resolved:
            return resolved
    elif isinstance(raw_parent, int) and not isinstance(raw_parent, bool):
        if q("SELECT id FROM lorebooks WHERE id=?", (raw_parent,), one=True):
            return raw_parent

    if root_id:
        return root_id

    if chat_id:
        chat = q(
            "SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True,
        )
        if chat and chat["lorebook_id"]:
            return chat["lorebook_id"]

    # A library book with no parent is a legitimate root; only a CHAT-owned
    # book needs somewhere to hang, and by here it has nowhere to hang from.
    return None


def apply_lorebook_plan(plan, chat_id=None, root_id=None):
    """Write an approved plan.

    `root_id` is the lorebook the plan was generated for: it is where books and
    entries land when their own reference cannot be resolved, so nothing is
    created unreachable and no entry is silently dropped.
    """
    from memory import add_lore, update_lore, add_lorebook_link
    from db import q, qi, transaction

    created_books = {}
    created_entries = []
    created_links = []

    # Wrap all write operations in a single transaction so the plan is
    # applied atomically — a crash mid-plan rolls back everything.
    with transaction():
        # Process book ops
        for book_op in plan.get("book_ops", []):
            if book_op.get("op") != "create":
                continue
            parent_id = _plan_parent_id(
                book_op.get("parent_id"), created_books, root_id, chat_id
            )

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

            # An unresolvable book reference used to drop the entry on the floor.
            # File it in the book the plan was generated for instead: misfiled is
            # fixable by hand, silently discarded is not.
            if not book_id:
                book_id = root_id

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
    # `generator_lorebook` documents entry_ops and nothing else, and instructs
    # a model given no "stage" key -- which is every call made from here -- to
    # return complete entry_ops in one response. Reading only the legacy
    # `entries` key therefore rejected every compliant answer. Fold both
    # shapes through the same normalizer the staged tree generator applies to
    # this prompt's output, so the two callers of one prompt agree about its
    # contract instead of one of them quietly defining a second one.
    entries = _normalize_entry_ops(parsed, lorebook_id)
    if not entries:
        raise RuntimeError(
            "Lore generator returned no entries.\n"
            f"Raw output:\n{(raw or '')[:800]}"
        )

    entry_ids = []
    for e in entries:
        # Every op reaching here belongs to this book: the payload shows the
        # model no entry ids and no second book, so an "update" op cannot be
        # addressing anything real. Write it as a new entry -- misfiling one
        # entry is fixable by hand, silently discarding a generated one is not.
        cat = e.get("category")
        if cat not in LORE_CATEGORIES:
            cat = guess_category(e.get("keys", ""), e.get("content", ""))
        eid = add_lore(
            lorebook_id,
            e.get("keys", ""),
            e.get("content", ""),
            category=cat,
            title=e.get("title"),
            knowledge_tag=e.get("knowledge_tag"),
            knowledge_range=e.get("knowledge_range"),
            knowledge_locations=e.get("knowledge_locations"),
            importance=e.get("importance", 0.5),
            aliases=e.get("aliases", []),
            scope=e.get("scope", {}),
            relations=e.get("relations", {}),
            source_notes=e.get("source_notes", ""),
        )
        entry_ids.append(eid)

    return entry_ids
