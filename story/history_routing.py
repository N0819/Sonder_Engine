"""Choose a pre-story history topology before any backend mints facts.

Charter is a strong resident simulator and a bad universal backstory writer.
This module keeps that distinction structural: only routes whose backend is
``charter_resident`` may place a card character in a generated Charter.

Automatic routing is deliberately conservative.  It may recognise explicit
travel or an explicit, opening-relevant residence; uncertainty preserves the
authored card and greeting instead of inventing local tenure.
"""

from __future__ import annotations

import copy
import re


ROUTE_CHOICES = frozenset({
    "auto", "resident", "moving_institution", "visitor",
    "generated_journey", "authored_only", "none",
})
CHARTER_BACKEND = "charter_resident"

_TRAVEL_PATTERNS = (
    r"\b(?:wanders?|wandering|itinerant|nomadic|roaming)\b",
    r"\b(?:time|space|world|dimensional)\s+travell?er\b",
    r"\btravels?\s+(?:across|between|through|from)\b",
    r"\b(?:arrives?|arriving|visits?|visiting|passing through)\b",
    r"\b(?:tardis|portal-hopper)\b",
)
_RESIDENCE_PATTERNS = (
    r"\b(?:lives?|resides?|resident|based|stationed|posted)\s+(?:at|in|on|aboard)\b",
    r"\b(?:works?|serves?|employed)\s+(?:as\s+[a-z0-9 _-]{1,60}\s+)?"
    r"(?:at|in|on|aboard|for)\b",
    r"\b(?:researcher|doctor|officer|captain|crew|staff|director|lead|keeper)\s+(?:at|of|on|aboard)\b",
    r"\bhas spent\s+(?:\w+\s+){0,4}(?:year|years|month|months)\s+(?:at|in|on|with)\b",
)
_MOVING_PATTERNS = (
    r"\b(?:captain|crew|officer|engineer|medic)\s+(?:of|aboard|on)\b",
    r"\b(?:serves?|stationed|lives?)\s+aboard\b",
    r"\b(?:ship|starship|caravan|train|fleet|unit)\b",
)
_COMMON = {
    "about", "after", "again", "against", "along", "also", "among", "and",
    "been", "before", "being", "card", "character", "could", "facility",
    "from", "have", "here", "into", "location", "opening", "place",
    "recent", "scene", "story", "that", "the", "their", "there", "these",
    "they", "this", "through", "under", "where", "which", "while",
    "with", "world", "years",
}


def normalize_history_choice(value):
    if isinstance(value, dict):
        value = value.get("mode") or value.get("choice")
    choice = str(value or "auto").strip().casefold().replace("-", "_")
    aliases = {
        "lives_here": "resident", "lives": "resident",
        "travels_with": "moving_institution", "institution": "moving_institution",
        "visit": "visitor", "arriving": "visitor", "arrival": "visitor",
        "journey": "generated_journey", "invented_journey": "generated_journey",
        "authored": "authored_only", "card_only": "authored_only",
        "off": "none", "disabled": "none",
    }
    choice = aliases.get(choice, choice)
    return choice if choice in ROUTE_CHOICES else "auto"


def _matches(patterns, text):
    return [pattern for pattern in patterns if re.search(pattern, text, re.I)]


def _distinct_words(text):
    return {
        word for word in re.findall(r"[a-z0-9][a-z0-9_-]{2,}",
                                    str(text or "").casefold())
        if word not in _COMMON and not word.isdigit()
    }


def _manual_route(choice):
    if choice == "resident":
        return {
            "anchor": "fixed_place", "authority": "mixed",
            "opening_relationship": "resident",
            "backends": [CHARTER_BACKEND],
            "summary": "Lives here · recent local history",
        }
    if choice == "moving_institution":
        return {
            "anchor": "bounded_moving_institution", "authority": "mixed",
            "opening_relationship": "resident",
            "backends": [CHARTER_BACKEND],
            "summary": "Travels with this place or group · institutional history",
        }
    if choice == "visitor":
        return {
            "anchor": "itinerary", "authority": "authored",
            "opening_relationship": "visiting",
            "backends": ["authored_history"],
            "summary": "Visits or arrives · no invented local career",
        }
    if choice == "generated_journey":
        return {
            "anchor": "itinerary", "authority": "generated",
            "opening_relationship": "arriving",
            "backends": ["journey_history"],
            "summary": "Arrives after a generated journey · no local career",
        }
    if choice == "none":
        return {
            "anchor": "unanchored", "authority": "none",
            "opening_relationship": "arriving", "backends": [],
            "summary": "No generated past · opening remains authoritative",
        }
    return {
        "anchor": "unanchored", "authority": "authored",
        "opening_relationship": "arriving",
        "backends": ["authored_history"],
        "summary": "Authored past preserved · no invented local career",
    }


def resolve_character_history_route(sheet, *, requested="auto", opening="",
                                    location_brief=""):
    """Return one closed, author-auditable route; perform no generation."""
    from story.character_schema import (
        character_name, character_public_history, normalize_character_data)

    normalized = normalize_character_data(sheet)
    choice = normalize_history_choice(requested)
    if choice != "auto":
        route = _manual_route(choice)
        route.update({
            "mode": choice, "author_locked": True, "confidence": 1.0,
            "reasons": [{"source": "author", "claim": choice}],
        })
        return route

    public = character_public_history(normalized)
    opening_context = " ".join((str(opening or ""), str(location_brief or "")))
    travel = _matches(_TRAVEL_PATTERNS, public + " " + opening_context)
    residence = _matches(_RESIDENCE_PATTERNS, public)
    shared = sorted(_distinct_words(public) & _distinct_words(opening_context))
    moving = _matches(_MOVING_PATTERNS, public)

    reasons = []
    if travel:
        route = _manual_route("visitor")
        reasons.append({
            "source": "card/opening", "claim": "explicit travel or arrival language"})
        confidence = .94
    elif residence and shared:
        route = _manual_route(
            "moving_institution" if moving else "resident")
        reasons.extend((
            {"source": "card.public_history", "claim": "explicit residence or service"},
            {"source": "opening/location", "claim":
             "same named setting: " + ", ".join(shared[:4])},
        ))
        confidence = .86
    else:
        # Competence, a matching profession, or a location generator being
        # enabled is never evidence of tenure.  This is the Doctor firewall.
        route = _manual_route("authored_only")
        reasons.append({
            "source": "router", "claim":
            "local residence is not explicit enough to simulate safely"})
        confidence = .72 if residence else .9

    route.update({
        "mode": "auto", "author_locked": False,
        "confidence": confidence, "reasons": reasons,
        "character": character_name(normalized),
    })
    return copy.deepcopy(route)


def route_uses_charter(route):
    return CHARTER_BACKEND in set((route or {}).get("backends") or ())


__all__ = [
    "CHARTER_BACKEND", "ROUTE_CHOICES", "normalize_history_choice",
    "resolve_character_history_route", "route_uses_charter",
]
