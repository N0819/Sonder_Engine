"""Stable, author-controlled identities for Charter bodies.

Charter may hold thousands of bodies, so identity creation cannot be an LLM
call and a display name cannot become the key other systems use.  The body
dict key remains the permanent identity.  This module only materialises the
human-facing name and presentation attached to that key.

Authors opt in with a small cultural ``naming`` profile.  Curated given and
family pools form a deterministic Cartesian name space; optional syllable
parts extend it when a setting needs more variety.  A generated name is
written into the body once.  Existing names therefore survive changes to the
profile, insertion of new bodies, checkpoint restore and promotion.
"""

from __future__ import annotations

import hashlib
import re


_FORMAT_FIELDS = {"given", "family", "name", "title", "rank"}


def _strings(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _parts(value):
    value = value if isinstance(value, dict) else {}
    return {
        "starts": _strings(value.get("starts")),
        "middles": _strings(value.get("middles")),
        "ends": _strings(value.get("ends")),
    }


def _safe_format(value, fallback):
    text = str(value or fallback).strip() or fallback
    fields = set(re.findall(r"\{([^{}]+)\}", text))
    return text if fields <= _FORMAT_FIELDS else fallback


def normalize_naming_profile(value):
    """Return the bounded, JSON-safe naming profile Charter understands.

    No implicit English profile exists.  Core is genre agnostic: an author
    who supplies no naming law keeps the historical body-key fallback rather
    than receiving names from a culture the engine invented.
    """
    value = value if isinstance(value, dict) else {}
    titles = value.get("titles") if isinstance(value.get("titles"), dict) else {}
    return {
        "seed": str(value.get("seed") or ""),
        "given": _strings(value.get("given")),
        "family": _strings(value.get("family")),
        "given_parts": _parts(value.get("given_parts")),
        "family_parts": _parts(value.get("family_parts")),
        "name_format": _safe_format(value.get("name_format"),
                                    "{given} {family}"),
        "formal_format": _safe_format(value.get("formal_format"),
                                      "{title} {name}"),
        "titles": {
            "posts": {str(k): str(v).strip()
                      for k, v in (titles.get("posts") or {}).items()
                      if str(v or "").strip()},
            "ranks": {str(k): str(v).strip()
                      for k, v in (titles.get("ranks") or {}).items()
                      if str(v or "").strip()},
        },
    }


def _number(seed, lane=0):
    raw = hashlib.blake2b(
        f"{seed}|{lane}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(raw, "big")


def _syllable_name(parts, seed):
    starts, middles, ends = (
        parts.get("starts") or [], parts.get("middles") or [],
        parts.get("ends") or [])
    if not starts or not ends:
        return ""
    start = starts[_number(seed, 0) % len(starts)]
    middle = ""
    if middles:
        middle = middles[_number(seed, 1) % len(middles)]
    end = ends[_number(seed, 2) % len(ends)]
    return f"{start}{middle}{end}"


def _component(pool, parts, seed, lane):
    if pool:
        return pool[_number(seed, lane) % len(pool)]
    return _syllable_name(parts, f"{seed}|{lane}")


def generated_name(charter_key, body_key, profile, attempt=0):
    """One deterministic candidate, or ``""`` when the profile has no law."""
    profile = normalize_naming_profile(profile)
    if not (profile["given"] or profile["given_parts"]["starts"]):
        return ""
    seed = "%s|%s|%s|%s" % (
        profile.get("seed") or charter_key, charter_key, body_key, attempt)
    given = _component(profile["given"], profile["given_parts"], seed, 0)
    family = _component(profile["family"], profile["family_parts"], seed, 1)
    if not given:
        return ""
    values = {"given": given, "family": family, "name": "",
              "title": "", "rank": ""}
    return " ".join(profile["name_format"].format(**values).split()).strip()


def _stored_name_components(body, profile):
    """Recover format fields without mistaking a display title for identity.

    New generated bodies store their components directly. Older registries
    predate those fields, so the two common authored formats receive a narrow
    compatibility parse. Any unfamiliar cultural format falls back to the
    full stored name instead of rendering a title with a blank identity.
    """
    body = body if isinstance(body, dict) else {}
    profile = normalize_naming_profile(profile)
    name = str(body.get("name") or body.get("key") or "").strip()
    given = str(body.get("given_name") or "").strip()
    family = str(body.get("family_name") or "").strip()
    parts = name.split()
    if parts and not (given and family):
        if profile["name_format"] == "{given} {family}":
            given = given or " ".join(parts[:-1]) or parts[0]
            family = family or parts[-1]
        elif profile["name_format"] == "{family} {given}":
            family = family or parts[0]
            given = given or " ".join(parts[1:]) or parts[-1]
    # A custom format may not expose separable components. Repeating the full
    # identity is imperfect but never collapses "Dr. Sarah Moon" to "Dr.".
    return given or name, family or name


def materialize_body_names(charter_key, raw_bodies, profile):
    """Copy ``raw_bodies`` and give every unnamed body one stable name.

    Collision resolution is deterministic on the first materialisation.
    Once the normalised registry is persisted, generated names are ordinary
    stored names and never enter this allocator again.
    """
    raw_bodies = raw_bodies if isinstance(raw_bodies, dict) else {}
    out = {str(key): dict(value) if isinstance(value, dict) else {}
           for key, value in raw_bodies.items()}
    used = {
        str(body.get("name") or "").strip().casefold()
        for body in out.values() if str(body.get("name") or "").strip()
    }
    for body_key in sorted(out):
        body = out[body_key]
        if str(body.get("name") or "").strip():
            continue
        chosen = ""
        for attempt in range(max(32, len(out) * 2)):
            candidate = generated_name(charter_key, body_key, profile, attempt)
            if not candidate:
                break
            if candidate.casefold() not in used:
                chosen = candidate
                break
        # A very small authored pool may genuinely be exhausted.  A stable
        # disambiguator is better than silently merging two people, and it is
        # only reached after every authored combination/part attempt failed.
        if not chosen:
            base = generated_name(charter_key, body_key, profile, 0)
            chosen = f"{base} {body_key}".strip() if base else body_key
        body["name"] = chosen
        given, family = _stored_name_components(body, profile)
        if given:
            body.setdefault("given_name", given)
        if family:
            body.setdefault("family_name", family)
        used.add(chosen.casefold())
    return out


def title_for(body, roles=(), profile=None):
    """The authored/rank/post title currently presented for this body."""
    body = body if isinstance(body, dict) else {}
    explicit = str(body.get("title") or "").strip()
    if explicit:
        return explicit
    profile = normalize_naming_profile(profile)
    rank = str(body.get("rank") or "").strip()
    if rank and rank in profile["titles"]["ranks"]:
        return profile["titles"]["ranks"][rank]
    for role in roles or ():
        title = profile["titles"]["posts"].get(str(role))
        if title:
            return title
    return ""


def display_name(body, roles=(), profile=None):
    """Formal scene-facing name; the underlying body key remains identity."""
    body = body if isinstance(body, dict) else {}
    name = str(body.get("name") or body.get("key") or "").strip()
    title = title_for(body, roles, profile)
    if not title or name.casefold().startswith(title.casefold() + " "):
        return name
    fmt = normalize_naming_profile(profile)["formal_format"]
    given, family = _stored_name_components(body, profile)
    values = {"given": given,
              "family": family,
              "name": name, "title": title,
              "rank": str(body.get("rank") or "")}
    return " ".join(fmt.format(**values).split()).strip()


def identity_aliases(body, roles=(), profile=None):
    """Every authored formal form that may refer to this same body.

    Personal names are materialized and permanent; rank and post titles are
    presentation that may legitimately change.  Keeping the bounded authored
    title variants as aliases lets recognition and historical transcript
    colour survive that presentation change without treating the display
    string as identity.
    """
    body = body if isinstance(body, dict) else {}
    profile = normalize_naming_profile(profile)
    name = str(body.get("name") or body.get("key") or "").strip()
    if not name:
        return []
    titles = [str(body.get("title") or "").strip()]
    titles.extend(profile["titles"]["ranks"].values())
    titles.extend(profile["titles"]["posts"].values())
    current = title_for(body, roles, profile)
    titles.append(current)
    given, family = _stored_name_components(body, profile)
    values = {
        "given": given,
        "family": family,
        "name": name,
        "rank": str(body.get("rank") or ""),
    }
    aliases = [name]
    for title in titles:
        title = str(title or "").strip()
        if not title:
            continue
        formal = " ".join(profile["formal_format"].format(
            **{**values, "title": title}).split()).strip()
        if formal:
            aliases.append(formal)
    shown = display_name(body, roles, profile)
    aliases.append(shown)
    return list(dict.fromkeys(alias for alias in aliases if alias))


def identity_seed(charter_key, body_key):
    """Stable render seed shared by background dialogue and promotion."""
    return f"charter:{charter_key}:{body_key}"
