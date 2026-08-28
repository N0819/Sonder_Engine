"""Grounded pre-story history for authored people living inside a Charter.

Charter supplies the factual skeleton: work actually stood, events personally
witnessed, reports still held, commitments, and earned acquaintance.  A model
may add only subjective meaning to those cited surfaces.  The result is a
small pre-story memory packet for a full character, after which Charter gives
up that body's cognition while keeping its institutional projection.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re


#: How many subjective memories the model pass may author over the simulated
#: past. Raised with `charter_promote.REMEMBERED_CAP`, which feeds it: these
#: were sized against a substrate that held 16 rows per body and truncated
#: everything past them, and the substrate now holds a life. One call, once,
#: at generation -- the cost is output tokens on a single model pass, against
#: a character the player will spend a whole story with.
PERSONAL_MEMORY_CAP = 60
#: The floor is an ACHIEVABILITY gate, not a depth lever: falling under it
#: raises rather than trims (:639), so a floor above what the evidence can
#: supply fails generation outright. It stays where it was proven; the target
#: and the cap are what buy depth.
PERSONAL_MEMORY_FLOOR = 10
PERSONAL_MEMORY_TARGET = 32
PERSONAL_SALIENCE_CAP = 0.7
PERSONAL_TONES = frozenset({
    "neutral", "steadying", "burdensome", "meaningful", "alienating",
    "reassuring", "unsettling", "frustrating", "absorbing", "bittersweet",
})
PERSONAL_LESSONS = frozenset({
    "none", "patience", "vigilance", "restraint", "empathy", "precision",
    "responsibility", "adaptability", "boundaries", "teamwork",
    "uncertainty",
})


_PERSONAL_HISTORY_SYSTEM = """You interpret a character's actual simulated
past. Return JSON only: {career_reflection,career_source_ids,memories:[{
source_id,tone,lesson,valence,arousal,salience}]}. tone is one of neutral,
steadying, burdensome, meaningful, alienating, reassuring, unsettling,
frustrating, absorbing, bittersweet. lesson is one of none, patience,
vigilance, restraint, empathy, precision, responsibility, adaptability,
boundaries, teamwork, uncertainty. Choose four to six memories when that many
distinct evidence rows exist; otherwise choose every worthwhile row. Every
source_id must be copied exactly from the evidence. You select and classify a
subjective response; you never rewrite the memory surface. Private card context
shapes selection and classification only and is not evidence that an event
happened. Author guidance has the same limit: emphasize matching evidence but
never turn a requested theme into a fact. Mundane service may remain mundane.
Omit rather than invent."""


_RECENT_LIFE_SYSTEM = """Create a richly detailed recent personal history for
one fictional resident immediately before a story opens. Return JSON only:
{overview,episodes:[{sequence,when,title,kind,location_id,participant_ids,
memory,consequence,source_ids,tone,lesson,valence,arousal,salience}]}.

Produce twelve distinct episodes, never fewer than ten and never more than
sixteen. Each episode becomes its OWN retrievable memory row. The memory must
be 45-180 words of concrete first-person autobiographical recollection: name
who was there, the physical place, what was wanted or at stake, what happened,
the resident's specific choice or reaction, and a detail that distinguishes
this occasion from routine. consequence says what remained changed, unresolved,
learned, owed, feared, trusted, suspected, or practically different afterward.
Use a chronological mix across the supplied recent window. Include work,
relationships, an ordinary private moment, disagreement or uncertainty, a
competence-revealing choice, and consequences of actual simulated conditions
when the anchors support them. Do not write twelve versions of standing watch.

This story-start option is an author licence to invent bounded PERSONAL recent
life consistent with the supplied card, roster, rooms, duties, actual anchors,
and guidance. Use only supplied location_id and participant_ids. You may invent
minor conversations, mistakes, favors, habits, tensions, and local work
incidents. Do not invent a new person, room, office, anomaly, power, death,
world-changing incident, institutional policy, promotion, crime, romance, or
canon fact. An anchor source_id may support a scene but never licenses facts
beyond its text. Private card context shapes the resident only; it is not a
fact about anybody else. The overview summarizes only returned episodes.
tone and lesson use the supplied closed vocabularies."""


def _bounded_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _public_words(value):
    words = set(re.findall(r"[a-z0-9]+", str(value or "").casefold()))
    expanded = set(words)
    for word in words:
        for suffix in ("ing", "ers", "er", "ists", "ist", "ies", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                expanded.add(word[:-len(suffix)])
    return expanded - {
        "a", "an", "and", "at", "for", "in", "of", "on", "the", "to",
        "with", "expert", "competent", "novice", "professional",
    }


def featured_resident_seed(char_id, sheet):
    """The public, placement-only slice of a full character card."""
    from story.character_schema import (
        character_abilities, character_name, character_public_history,
        normalize_character_data)

    normalized = normalize_character_data(sheet)
    public_history = _bounded_text(character_public_history(normalized), 4000)
    public_words = _public_words(public_history)
    abilities = []
    for raw in character_abilities(normalized)[:16]:
        if not isinstance(raw, dict):
            continue
        # Ability rows have no public/private flag and routinely carry facts
        # like "only does this in private" in their limits. Placement may use
        # only abilities whose name/scope is already corroborated by the
        # explicitly public history, and never receives the limits/notes.
        surface = " ".join(str(raw.get(key) or "")
                           for key in ("name", "scope"))
        if not public_words.intersection(_public_words(surface)):
            continue
        row = {
            key: _bounded_text(raw.get(key), 240)
            for key in ("name", "level", "scope")
            if _bounded_text(raw.get(key), 240)
        }
        if row:
            abilities.append(row)
    return {
        "seed_id": f"character:{int(char_id)}",
        "name": character_name(normalized),
        "public_history": public_history,
        "abilities": abilities,
    }


def featured_resident_private_habits(sheet):
    """Return a small self-only habit projection, never planner context."""
    from story.character_schema import character_psychology, normalize_character_data

    psychology = character_psychology(normalize_character_data(sheet))
    markers = re.compile(
        r"\b(private|privately|alone|off[- ]?(?:clock|duty)|locked|comfort|"
        r"bake|sweet|doodle|plush|hobby|ritual)\b", re.I)
    candidates = []
    coping = psychology.get("coping") or {}
    for index, row in enumerate(coping.get("strategies") or ()):
        if not isinstance(row, dict):
            continue
        material = " ".join(str(row.get(key) or "")
                            for key in ("name", "trigger", "response"))
        if markers.search(material):
            candidates.append({
                "id": f"coping_{index + 1}",
                "label": _bounded_text(row.get("name") or "private routine", 160),
                "activity": _bounded_text(row.get("response"), 500),
                "cadence_hours": 48,
                "source": f"psychology.coping.strategies.{index}",
            })
    for index, row in enumerate(psychology.get("traits") or ()):
        if not isinstance(row, dict):
            continue
        material = " ".join((
            str(row.get("name") or ""), str(row.get("expression") or ""),
            " ".join(str(value) for value in row.get("activation_cues") or ())))
        if markers.search(material):
            candidates.append({
                "id": f"trait_{index + 1}",
                "label": _bounded_text(row.get("name") or "private routine", 160),
                "activity": _bounded_text(row.get("expression"), 500),
                "cadence_hours": 72,
                "source": f"psychology.traits.{index}",
            })
    out, seen = [], []
    for row in candidates:
        words = _public_words(row["label"] + " " + row["activity"])
        if any(len(words & previous) >= 3 for previous in seen):
            continue
        seen.append(words)
        out.append(row)
        if len(out) >= 4:
            break
    return out


def featured_resident_bindings(registry, seed_ids=()):
    """Resolve generation seed ids to the exact bodies closure materialized."""
    wanted = {str(value) for value in seed_ids if str(value or "")}
    out = {}
    for charter_key, item in sorted((registry.get("items") or {}).items()):
        state = item.get("state") or {}
        for body_key, body in sorted((state.get("bodies") or {}).items()):
            seed_id = str(body.get("resident_seed_id") or "")
            if seed_id and (not wanted or seed_id in wanted):
                out[seed_id] = {
                    "seed_id": seed_id, "charter": str(charter_key),
                    "body": str(body_key), "name": str(body.get("name") or ""),
                    "place": str(body.get("place") or ""),
                }
    return out


def _first_person(surface):
    surface = _bounded_text(surface, 1000)
    replacements = (
        (r"^has stood\s+", "I stood "),
        (r"^was unable\s+", "I was unable "),
        (r"^was back\s+", "I was back "),
        (r"^knows\s+", "I know "),
        (r"^saw\s+", "I saw "),
        (r"^heard\s+", "I heard "),
        (r"^learned\s+", "I learned "),
    )
    for pattern, replacement in replacements:
        changed = re.sub(pattern, replacement, surface, flags=re.IGNORECASE)
        if changed != surface:
            return changed
    return surface


def _named_surface(memory, names):
    """Render structured experience with stable, scene-facing identities."""
    kind = str(memory.get("experience_kind") or "")
    place = str(memory.get("location") or "")
    where = f" in {place}" if place else ""
    if kind == "private_habit":
        label = str(memory.get("habit_label") or "private routine")
        return f"I made private time{where} for {label.casefold()}."
    if kind == "social":
        actor = str(memory.get("actor") or "")
        other = str(memory.get("other") or "")
        actor_name = str(names.get(actor) or actor)
        other_name = str(names.get(other) or other)
        act = str(memory.get("act") or "interacted with").replace("_", " ")
        past = {
            "greet": "greeted", "ask": "asked", "tell": "told",
            "tend": "tended", "accuse": "accused",
            "reconcile": "made peace with",
        }.get(act, act)
        if str(memory.get("role") or "") == "actor":
            return f"I {past} {other_name}{where}."
        return f"{actor_name} {past} me{where}."
    surface = _first_person(memory.get("content"))
    for key in sorted(names, key=len, reverse=True):
        surface = surface.replace(str(key), str(names[key]))
    return surface


def _recent_life_context(cid, state, bundle, binding, *, frame_id=None):
    """Bounded names, places and duties the recent-life author may use."""
    bodies = state.get("bodies") or {}
    posts = state.get("posts") or {}
    body_key = str(bundle.get("body") or binding.get("body") or "")
    resident = bodies.get(body_key) or {}
    home_post = str(resident.get("home_post") or "")
    home_place = str(resident.get("place") or binding.get("place") or "")
    names = bundle.get("social_names") or {}

    people = []
    for other_key, other in bodies.items():
        other_key = str(other_key)
        if other_key == body_key:
            continue
        other_post = str(other.get("home_post") or "")
        other_place = str(other.get("place") or "")
        score = (6 if home_post and other_post == home_post else 0)
        score += 4 if home_place and other_place == home_place else 0
        if home_post and other_post:
            ours = posts.get(home_post) or {}
            theirs = posts.get(other_post) or {}
            if str(ours.get("reports_to") or "") == other_post \
                    or str(theirs.get("reports_to") or "") == home_post:
                score += 5
        if score <= 0:
            continue
        people.append({
            "body_id": other_key,
            "name": str(names.get(other_key) or other.get("name") or other_key),
            "post": other_post,
            "title": str(other.get("title") or ""),
            "place": other_place,
            "relationship_basis": (
                "same post" if home_post and other_post == home_post else
                "same workplace" if home_place and other_place == home_place else
                "reporting line"),
            "_score": score,
        })
    people.sort(key=lambda row: (-row["_score"], row["body_id"]))
    for row in people:
        row.pop("_score", None)
    people = people[:24]

    place_ids = {home_place, str(resident.get("berth") or "")}
    place_ids.update(str(row.get("place") or "") for row in people)
    place_ids.update(str((posts.get(post) or {}).get("place") or "")
                     for post in set((state.get("stood") or {}).get(
                         body_key, {})) | ({home_post} if home_post else set()))
    room_specs = {}
    if state.get("structure"):
        try:
            from world.structure import skeleton_rooms
            room_specs = skeleton_rooms(
                cid, state["structure"], frame_id).get("rooms") or {}
        except Exception:
            room_specs = {}
    places = []
    for place_id in sorted(value for value in place_ids if value):
        spec = room_specs.get(place_id) or {}
        places.append({
            "location_id": place_id,
            "name": str(spec.get("name") or place_id).replace("_", " "),
            "purpose": str(spec.get("purpose") or ""),
        })

    duties = []
    duty_ids = list(dict.fromkeys(
        ([home_post] if home_post else [])
        + list(((state.get("stood") or {}).get(body_key) or {}).keys())))
    for post_id in duty_ids:
        post = posts.get(str(post_id)) or {}
        duties.append({
            "post_id": str(post_id),
            "title": str(resident.get("title") or post.get("purpose")
                         or str(post_id).replace("_", " ")),
            "place": str(post.get("place") or home_place),
            "reports_to": str(post.get("reports_to") or ""),
            "serves": [str(value) for value in post.get("serves") or ()],
        })
    return {
        "resident_body_id": body_key,
        "resident_name": str(binding.get("name") or resident.get("name") or ""),
        "recent_window_hours": min(
            720.0, max(24.0, float(state.get("clock_hours") or 0.0))),
        "people": people, "places": places, "duties": duties,
    }


def resident_history_packet(cid, binding, *, frame_id=None):
    """Build one body's evidence packet without reading another mind."""
    from world.charter_runtime import promotion_bundle, registry_for

    ref = {"charter": binding.get("charter"), "body": binding.get("body")}
    bundle = promotion_bundle(
        cid, binding.get("name") or binding.get("body"),
        record={"charter_refs": [ref]}, frame_id=frame_id)
    if not bundle:
        return None
    evidence = []
    names = bundle.get("social_names") or {}
    for index, memory in enumerate((bundle.get("handoff") or {}).get(
            "memories") or ()):
        if not isinstance(memory, dict) or not memory.get("content"):
            continue
        raw_id = str(memory.get("event_key") or index)
        # Aggregate service is career evidence, never an episode. It becomes
        # the separate human-readable career summary below.
        if raw_id.startswith("service:"):
            continue
        source_id = "charter:" + hashlib.sha256(
            (str(bundle["charter"]) + "|" + str(bundle["body"]) + "|" + raw_id)
            .encode("utf-8")).hexdigest()[:16]
        evidence.append({
            "source_id": source_id,
            "surface": _named_surface(memory, names),
            "kind": str(memory.get("kind") or "episodic"),
            "provenance": str(memory.get("provenance") or "remembered"),
            "salience": float(memory.get("salience") or 0.0),
            "confidence": float(memory.get("confidence") or 1.0),
            "location": str(memory.get("location") or ""),
            "entities": [str(names.get(str(value)) or value)
                         for value in memory.get("entities") or ()],
            "at_hours": float(memory.get("at_hours") or 0.0),
        })
    registry = registry_for(cid, frame_id)
    item = (registry.get("items") or {}).get(str(bundle["charter"])) or {}
    state = item.get("state") or {}
    actual = ((state.get("history") or {}).get("actual") or {})
    resident = (actual.get("residents") or {}).get(str(bundle["body"])) or {}
    service = copy.deepcopy((bundle.get("handoff") or {}).get("stood") or {})
    recent_context = _recent_life_context(
        cid, state, bundle, binding, frame_id=frame_id)
    duty_titles = [row["title"] for row in recent_context["duties"]
                   if row.get("title")]
    roles = duty_titles or [str(post).replace("_", " ")
                            for post in sorted(service)]
    place_name = next((row["name"] for row in recent_context["places"]
                       if row["location_id"] == binding.get("place")),
                      str(binding.get("place") or "").replace("_", " "))
    career = ""
    if roles:
        career = "I worked as " + ", then ".join(dict.fromkeys(roles))
        if place_name:
            career += f" in {place_name}"
        career += "."
    return {
        "binding": copy.deepcopy(binding),
        "service": service,
        "career_summary": career,
        "historian": {
            "summary": _bounded_text(resident.get("summary"), 1200),
            "event_ids": [str(value) for value in resident.get("event_ids") or ()],
            "turning_points": [copy.deepcopy(row) for row in
                               resident.get("turning_points") or ()
                               if isinstance(row, dict)][:12],
        },
        "recent_context": recent_context,
        "evidence": evidence,
        "handoff": bundle.get("handoff") or {},
        "promotion_bundle": bundle,
    }


def _character_context(sheet):
    """Private context for interpretation only; never stored in Charter."""
    from story.character_schema import (
        character_abilities, character_private_history,
        character_psychology, character_public_history, character_voice,
        normalize_character_data)

    normalized = normalize_character_data(sheet)
    private = []
    for row in character_private_history(normalized)[:16]:
        if isinstance(row, dict) and row.get("content"):
            private.append(_bounded_text(row["content"], 600))
    return {
        "public_history": _bounded_text(
            character_public_history(normalized), 5000),
        "abilities": [
            {key: _bounded_text(row.get(key), 300)
             for key in ("name", "level", "scope", "limits")
             if _bounded_text(row.get(key), 300)}
            for row in character_abilities(normalized)[:16]
            if isinstance(row, dict)
        ],
        "psychology": character_psychology(normalized),
        "voice": character_voice(normalized),
        "private_history": private,
    }


def ground_personal_history(value, packet):
    """Compile cited model interpretations over immutable evidence surfaces."""
    value = value if isinstance(value, dict) else {}
    sources = {
        str(row.get("source_id")): row for row in packet.get("evidence") or ()
        if isinstance(row, dict) and row.get("source_id") and row.get("surface")
    }
    dropped = []
    career_ids = [str(value) for value in value.get("career_source_ids") or ()]
    career = _bounded_text(value.get("career_reflection"), 1000)
    if career and (not career_ids or any(key not in sources for key in career_ids)):
        dropped.append({"section": "career_reflection", "reason": "uncited"})
        career, career_ids = "", []
    memories = []
    seen = set()
    for raw in value.get("memories") or ():
        if not isinstance(raw, dict):
            continue
        source_id = str(raw.get("source_id") or "")
        if source_id not in sources or source_id in seen:
            dropped.append({"source_id": source_id, "reason": "unknown_or_duplicate"})
            continue
        seen.add(source_id)
        source = sources[source_id]
        content = str(source["surface"]).rstrip()
        if content and content[-1] not in ".!?。！？":
            content += "."
        tone = str(raw.get("tone") or "neutral").strip().casefold()
        lesson = str(raw.get("lesson") or "none").strip().casefold()
        if tone not in PERSONAL_TONES:
            tone = "neutral"
        if lesson not in PERSONAL_LESSONS:
            lesson = "none"
        try:
            requested_salience = float(raw.get("salience", source["salience"]))
        except (TypeError, ValueError):
            requested_salience = float(source["salience"])
        memories.append({
            "source_id": source_id,
            "kind": str(source.get("kind") or "episodic"),
            "provenance": str(source.get("provenance") or "remembered"),
            "salience": round(max(0.0, min(
                PERSONAL_SALIENCE_CAP, float(source.get("salience") or 0.0),
                requested_salience)), 4),
            "content": content,
            "location": str(source.get("location") or ""),
            "entities": list(source.get("entities") or ()),
            "confidence": float(source.get("confidence") or 1.0),
            "at_hours": float(source.get("at_hours") or 0.0),
            # Protocol tags, not model prose: this metadata may enter a mind,
            # so it cannot become another aperture for an uncited incident.
            "emotional_context": f"tone:{tone};lesson:{lesson}",
            "valence": max(-1.0, min(1.0, _number(raw.get("valence")))),
            "arousal": max(0.0, min(1.0, _number(raw.get("arousal")))),
        })
        if len(memories) >= PERSONAL_MEMORY_CAP:
            break
    target = min(PERSONAL_MEMORY_FLOOR, len(sources), PERSONAL_MEMORY_CAP)
    if len(memories) < target:
        remaining = sorted(
            (row for key, row in sources.items() if key not in seen),
            key=lambda row: (float(row.get("at_hours") or 0.0),
                             -float(row.get("salience") or 0.0),
                             str(row.get("source_id") or "")))
        for source in remaining[:target - len(memories)]:
            supplement = ground_personal_history({
                "memories": [{"source_id": source["source_id"]}],
            }, {"evidence": [source]})["memories"]
            memories.extend(supplement)
            seen.add(source["source_id"])
    memories.sort(key=lambda row: (
        float(row.get("at_hours") or 0.0), str(row.get("source_id") or "")))
    return {
        "career_reflection": career,
        "career_source_ids": career_ids,
        "memories": memories,
        "grounding": {"dropped": dropped[:12]},
    }


def ground_recent_history(value, packet):
    """Turn a licensed recent-life draft into separate grounded memories."""
    value = value if isinstance(value, dict) else {}
    context = packet.get("recent_context") or {}
    valid_people = {
        str(row.get("body_id")): row for row in context.get("people") or ()
        if isinstance(row, dict) and row.get("body_id") and row.get("name")
    }
    valid_places = {
        str(row.get("location_id")): row for row in context.get("places") or ()
        if isinstance(row, dict) and row.get("location_id")
    }
    valid_sources = {
        str(row.get("source_id")) for row in packet.get("evidence") or ()
        if isinstance(row, dict) and row.get("source_id")
    }
    dropped, episodes, seen = [], [], set()
    for raw in value.get("episodes") or ():
        if not isinstance(raw, dict):
            continue
        location_id = str(raw.get("location_id") or "")
        participants = list(dict.fromkeys(
            str(item) for item in raw.get("participant_ids") or ()
            if str(item) in valid_people))[:6]
        unknown_people = [str(item) for item in raw.get("participant_ids") or ()
                          if str(item) not in valid_people
                          and str(item) != str(context.get("resident_body_id") or "")]
        source_ids = list(dict.fromkeys(
            str(item) for item in raw.get("source_ids") or ()
            if str(item) in valid_sources))
        title = _bounded_text(raw.get("title"), 160)
        when = _bounded_text(raw.get("when"), 120)
        memory = _bounded_text(raw.get("memory"), 1400)
        consequence = _bounded_text(raw.get("consequence"), 500)
        missing = []
        if location_id not in valid_places:
            missing.append("location")
        if unknown_people:
            missing.append("unknown_participant")
        if not title:
            missing.append("title")
        if not when:
            missing.append("when")
        if len(memory.split()) < 45:
            missing.append("thin_memory")
        if len(consequence.split()) < 4:
            missing.append("thin_consequence")
        if missing:
            dropped.append({"title": title, "reasons": missing})
            continue
        identity = json.dumps({
            "when": when, "title": title, "location": location_id,
            "participants": participants, "memory": memory,
            "consequence": consequence,
        }, ensure_ascii=False, sort_keys=True)
        source_id = "recent:" + hashlib.sha256(
            identity.encode("utf-8")).hexdigest()[:18]
        if source_id in seen:
            dropped.append({"title": title, "reasons": ["duplicate"]})
            continue
        seen.add(source_id)
        place_name = str(valid_places[location_id].get("name") or location_id)
        people_names = [str(valid_people[item]["name"]) for item in participants]
        # The structured identifiers are authority. Ensure the independently
        # retrievable prose still carries those hooks even if the model forgot
        # to repeat one in its autobiographical paragraph.
        prefix = when
        if place_name.casefold() not in memory.casefold():
            prefix += f", in {place_name}"
        absent = [name for name in people_names
                  if name.casefold() not in memory.casefold()]
        if absent:
            prefix += ", with " + ", ".join(absent)
        content = f"{title} — {prefix}: {memory}"
        if consequence.casefold() not in memory.casefold():
            content += f" What remained afterward: {consequence}"
        tone = str(raw.get("tone") or "neutral").strip().casefold()
        lesson = str(raw.get("lesson") or "none").strip().casefold()
        if tone not in PERSONAL_TONES:
            tone = "neutral"
        if lesson not in PERSONAL_LESSONS:
            lesson = "none"
        try:
            salience = float(raw.get("salience", 0.58))
        except (TypeError, ValueError):
            salience = 0.58
        try:
            sequence = int(raw.get("sequence"))
        except (TypeError, ValueError):
            sequence = len(episodes) + 1
        episodes.append({
            "source_id": source_id, "sequence": sequence,
            "when": when, "title": title,
            "consequence": consequence,
            "event_kind": _bounded_text(raw.get("kind") or "recent_event", 80),
            "kind": "episodic", "provenance": "remembered",
            "salience": round(max(0.35, min(PERSONAL_SALIENCE_CAP, salience)), 4),
            "content": content, "location": location_id,
            "entities": people_names, "participant_ids": participants,
            "source_ids": source_ids, "confidence": 1.0,
            "emotional_context": f"tone:{tone};lesson:{lesson}",
            "valence": max(-1.0, min(1.0, _number(raw.get("valence")))),
            "arousal": max(0.0, min(1.0, _number(raw.get("arousal")))),
        })
        if len(episodes) >= PERSONAL_MEMORY_CAP:
            break
    episodes.sort(key=lambda row: (row["sequence"], row["source_id"]))
    window = float(context.get("recent_window_hours") or 720.0)
    for index, episode in enumerate(episodes, 1):
        episode["sequence"] = index
        episode["at_hours"] = round(window * index / max(1, len(episodes)), 4)
    if len(episodes) < PERSONAL_MEMORY_FLOOR:
        raise ValueError(
            "resident recent history produced %d usable episodes; at least %d "
            "rich independent memories are required" % (
                len(episodes), PERSONAL_MEMORY_FLOOR))
    return {
        "overview": _bounded_text(value.get("overview"), 1000),
        "memories": episodes,
        "grounding": {"dropped": dropped[:24],
                      "accepted": len(episodes)},
    }


def _record_shared_recent_history(cid, binding, episodes, *, frame_id=None):
    """Give every named participant a bounded reciprocal event record."""
    from world.charter_runtime import registry_for_update, save_registry

    # registry_for_update, not registry_for: this function mutates
    # `experiences` in place and the shared cached registry is read-only.
    registry = registry_for_update(cid, frame_id)
    item = (registry.get("items") or {}).get(str(binding.get("charter") or ""))
    if not item:
        return 0
    state = item["state"]
    bodies = state.get("bodies") or {}
    resident_body = str(binding.get("body") or "")
    resident_name = str(binding.get("name") or resident_body)
    experiences = state.setdefault("experiences", {})
    written = 0
    for episode in episodes:
        for participant in episode.get("participant_ids") or ():
            participant = str(participant)
            if participant == resident_body or participant not in bodies:
                continue
            event_id = f"shared:{episode.get('source_id')}:{participant}"
            rows = [row for row in experiences.get(participant, [])
                    if str((row or {}).get("id") or "") != event_id]
            rows.append({
                "id": event_id, "kind": "shared_prestory",
                "at_hours": float(episode.get("at_hours") or 0.0),
                "place": str(episode.get("location") or ""),
                "with": resident_body, "title": str(episode.get("title") or ""),
                "when": str(episode.get("when") or ""),
                "surface": (
                    f"I shared {str(episode.get('title') or 'a recent event').casefold()} "
                    f"with {resident_name}. What remained afterward: "
                    f"{str(episode.get('consequence') or 'the encounter still mattered')}."),
            })
            experiences[participant] = rows[-16:]
            written += 1
    if written:
        save_registry(cid, registry, frame_id)
    return written


def flesh_resident_history(packet, sheet, *, author_guidance="", model_call=None):
    """Author a bounded rich recent life over Charter's named substrate."""
    payload = {
        "resident": {
            "name": (packet.get("binding") or {}).get("name"),
            "historian": packet.get("historian") or {},
        },
        "recent_context": packet.get("recent_context") or {},
        "actual_simulation_anchors": packet.get("evidence") or [],
        "character_context_for_interpretation_only": _character_context(sheet),
        "author_guidance": _bounded_text(author_guidance, 2000),
        "target_episodes": PERSONAL_MEMORY_TARGET,
        "minimum_episodes": PERSONAL_MEMORY_FLOOR,
        "maximum_episodes": PERSONAL_MEMORY_CAP,
        "tone_vocabulary": sorted(PERSONAL_TONES),
        "lesson_vocabulary": sorted(PERSONAL_LESSONS),
    }
    if model_call is None:
        from llm.providers import chat_complete
        raw = chat_complete(
            "utility", _RECENT_LIFE_SYSTEM,
            json.dumps(payload, ensure_ascii=False), temperature=0.62,
            max_tokens=7000, json_mode=True)
        value = json.loads(raw)
    else:
        value = model_call(payload)
    if not isinstance(value, dict):
        raise ValueError("resident recent-life generator returned a non-object")
    from llm.schemas import PrestoryResidentHistory
    parsed = PrestoryResidentHistory(**value)
    normalized = parsed.model_dump() if hasattr(parsed, "model_dump") \
        else parsed.dict()
    return ground_recent_history(normalized, packet)


def integrate_featured_resident(cid, char_id, binding, sheet, *, frame_id=None,
                                author_guidance="", model_call=None):
    """Give an existing full character their simulated past, then bind them."""
    from core.db import q, qi, wget_for_frame, wset_for_frame
    from mind.memory import add_memories_batch
    from world.charter_runtime import bind_promoted_character

    packet = resident_history_packet(cid, binding, frame_id=frame_id)
    if not packet:
        raise ValueError("featured resident no longer resolves to one Charter body")
    # A sparse fallback is worse than a visible creation failure: it mints an
    # impoverished past as canon and the story cannot later distinguish it
    # from an author-approved result. The story-start caller removes its
    # half-created chat if this bounded generation fails.
    fleshed = flesh_resident_history(
        packet, sheet, author_guidance=author_guidance,
        model_call=model_call)

    rows = []
    selected = list(fleshed.get("memories") or ())
    for memory in selected:
        source_id = str(memory.get("source_id") or "")
        stored_memory = {
            key: copy.deepcopy(value) for key, value in memory.items()
            if key not in {"source_id", "at_hours", "sequence", "when",
                           "title", "event_kind", "participant_ids",
                           "source_ids", "consequence"}
        }
        rows.append({
            "chat_id": cid, "char_id": char_id, "turn_id": None,
            # BEFORE THE STORY, NOT OUTSIDE IT. `mind/memory_read` filters
            # `turn_idx IS NOT NULL` for the two readers that constitute a
            # self -- the autobiographical summary and the recent-memory
            # buffer that grounds a beat -- so a null here made an inherited
            # life reachable by embedding search alone. The character had a
            # past it could not narrate and could not be reminded of, which
            # reads in play as a person born this turn. Turn 0 is the opening,
            # so a pre-story row sits at the earliest point the story has and
            # survives every rollback into it.
            "turn_idx": 0, "frame_id": frame_id,
            **stored_memory,
            "event_key": "prestory:charter:%s:%s:%s" % (
                binding["charter"], binding["body"], source_id),
        })
    overview = str(fleshed.get("overview") or "").strip()
    if overview:
        overview_key = hashlib.sha256(
            overview.encode("utf-8")).hexdigest()[:18]
        rows.insert(0, {
            "chat_id": cid, "char_id": char_id, "turn_id": None,
            # BEFORE THE STORY, NOT OUTSIDE IT. `mind/memory_read` filters
            # `turn_idx IS NOT NULL` for the two readers that constitute a
            # self -- the autobiographical summary and the recent-memory
            # buffer that grounds a beat -- so a null here made an inherited
            # life reachable by embedding search alone. The character had a
            # past it could not narrate and could not be reminded of, which
            # reads in play as a person born this turn. Turn 0 is the opening,
            # so a pre-story row sits at the earliest point the story has and
            # survives every rollback into it.
            "turn_idx": 0, "frame_id": frame_id,
            "kind": "semantic", "provenance": "remembered",
            "salience": 0.5, "content": overview,
            "location": str(binding.get("place") or ""),
            "entities": [], "confidence": 1.0,
            "event_key": "prestory:charter:%s:%s:overview:%s" % (
                binding["charter"], binding["body"], overview_key),
        })
    career_summary = str(packet.get("career_summary") or "").strip()
    if career_summary:
        rows.insert(0, {
            "chat_id": cid, "char_id": char_id, "turn_id": None,
            # BEFORE THE STORY, NOT OUTSIDE IT. `mind/memory_read` filters
            # `turn_idx IS NOT NULL` for the two readers that constitute a
            # self -- the autobiographical summary and the recent-memory
            # buffer that grounds a beat -- so a null here made an inherited
            # life reachable by embedding search alone. The character had a
            # past it could not narrate and could not be reminded of, which
            # reads in play as a person born this turn. Turn 0 is the opening,
            # so a pre-story row sits at the earliest point the story has and
            # survives every rollback into it.
            "turn_idx": 0, "frame_id": frame_id,
            "kind": "semantic", "provenance": "remembered",
            "salience": 0.45, "content": career_summary,
            "location": str(binding.get("place") or ""),
            "entities": [str(binding.get("charter") or "")],
            "confidence": 1.0,
            "event_key": "prestory:charter:%s:%s:career" % (
                binding["charter"], binding["body"]),
        })
    if rows:
        add_memories_batch(rows)

    row = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)
    state = json.loads(row["state"] or "{}") if row else {}
    state["charter_origin"] = {
        "charter": binding["charter"], "body": binding["body"],
        "stood": copy.deepcopy(packet.get("service") or {}),
    }
    qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
       (json.dumps(state, ensure_ascii=False), cid, char_id))
    reciprocal_records = _record_shared_recent_history(
        cid, binding, selected, frame_id=frame_id)
    if not bind_promoted_character(
            cid, packet["promotion_bundle"], char_id=char_id,
            name=binding.get("name") or "", entity_id=(sheet.get("identity") or {}).get(
                "uid") or "", promoted_turn=0, place=binding.get("place") or "",
            frame_id=frame_id):
        raise RuntimeError("featured resident Charter binding could not be saved")

    record = wget_for_frame(
        cid, "charter_resident_histories", frame_id, {}) or {}
    record[str(char_id)] = {
        "binding": copy.deepcopy(binding),
        "historian": copy.deepcopy(packet.get("historian") or {}),
        "overview": fleshed.get("overview") or "",
        "memory_event_keys": [row["event_key"] for row in rows],
        "chronology": [
            {"source_id": row.get("source_id"), "title": row.get("title"),
             "when": row.get("when"), "at_hours": row.get("at_hours"),
             "location": row.get("location"),
             "entities": row.get("entities") or []}
            for row in selected],
        "grounding": fleshed.get("grounding") or {}, "error": "",
        "reciprocal_records": reciprocal_records,
        "author_guidance": _bounded_text(author_guidance, 2000),
    }
    wset_for_frame(cid, "charter_resident_histories", record, frame_id)
    return record[str(char_id)]


__all__ = [
    "PERSONAL_LESSONS", "PERSONAL_MEMORY_CAP", "PERSONAL_MEMORY_FLOOR",
    "PERSONAL_MEMORY_TARGET", "PERSONAL_TONES",
    "featured_resident_bindings",
    "featured_resident_private_habits", "featured_resident_seed",
    "flesh_resident_history",
    "ground_personal_history", "ground_recent_history",
    "integrate_featured_resident",
    "resident_history_packet",
]
