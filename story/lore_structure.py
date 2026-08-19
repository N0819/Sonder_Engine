"""The tree a SillyTavern lorebook encodes in its entry titles.

A World Info book is a flat list, and every large one is really a tree that its
author drew in the `comment` field with rule characters and glyphs. The Re:Zero
book (300 entries, 354k characters) is exactly regular:

    ═══════[World]═══════                    section
    [«»] World History [«»]                    leaf
    [›] Great Calamity                           child of the leaf above
    ⚲────↓Kingdom Locations↓────⚲            subsection
    [🏰] Dragon Kingdom of Lugunica [🏰]        leaf
    [›] Lugunica Currency                        child of the leaf above

6 sections, 9 subsections, 168 leaves, 116 `[›]` children. Not one of those
relationships survived import: `comment` is never read anywhere in
`importers.py`, so the titles went in the bin and the book landed flat.

WHY THE TREE IS WORTH RECOVERING, beyond navigability. It is the only
principled source for the knowledge fields. `[›] Lugunica Currency` sitting
under `[🏰] Dragon Kingdom of Lugunica` says, structurally, that this is
LOCAL knowledge about Lugunica -- which is what lets an innkeeper there be
expected to know it while a stranger two kingdoms away is not. Asking a model
that question per entry would cost 300 calls and answer worse: the author
already encoded it, in the layout.

Everything here is deterministic and reads only the titles and their order.
"""

from __future__ import annotations

import re

# A section rule: ═══════[World]═══════
_SECTION_RE = re.compile(r"^[═=]{3,}\s*\[?([^\]═=]+?)\]?\s*[═=]{3,}\s*$")
# A subsection rule, whose name sits between the down-arrows:
# ⚲────↓Kingdom Locations↓────⚲   or   [⚖️]────↓Authority↓────[⚖️]
_SUBSECTION_RE = re.compile(r"[─-]{3,}\s*↓(.+?)↓\s*[─-]{3,}")
# A child marker. The child belongs to the LEAF ABOVE IT, not to the section --
# "Lugunica Currency" is a fact about Lugunica, not a sibling of it.
_CHILD_PREFIX = "[›]"
# Decorative glyph brackets around a leaf's name: "[📍] Lugunica", and the
# trailing repeat some entries carry: "[🏰] ... [🏰]".
_GLYPH_RE = re.compile(r"^\s*\[([^\]]{1,8})\]\s*|\s*\[([^\]]{1,8})\]\s*$")


def clean_title(raw):
    """A title with its rules, glyphs and child marker stripped."""
    text = str(raw or "").strip()
    if text.startswith(_CHILD_PREFIX):
        text = text[len(_CHILD_PREFIX):]
    section = _SECTION_RE.match(text)
    if section:
        return section.group(1).strip()
    sub = _SUBSECTION_RE.search(text)
    if sub:
        return sub.group(1).strip()
    previous = None
    while previous != text:
        previous = text
        text = _GLYPH_RE.sub("", text).strip()
    return text.strip(" -–—│|").strip()


def classify_title(raw):
    """`section` | `subsection` | `child` | `leaf` for one raw title."""
    text = str(raw or "").strip()
    if not text:
        return "leaf"
    if _SECTION_RE.match(text):
        return "section"
    if _SUBSECTION_RE.search(text):
        return "subsection"
    if text.startswith(_CHILD_PREFIX):
        return "child"
    return "leaf"


def parse_structure(entries):
    """Walk a lorebook IN AUTHORED ORDER and resolve every entry's place.

    `entries` is the raw SillyTavern list. Order is `displayIndex` when present
    and `uid` otherwise, because the tree is positional -- a child means "the
    leaf above me", which is meaningless in any other order.

    Returns one record per entry: title, clean, level, section, subsection,
    parent (the leaf a child hangs from), and `structural` for a rule that
    carries no content of its own and is scaffolding rather than lore.
    """
    def order_key(entry):
        idx = entry.get("displayIndex")
        return idx if idx is not None else (entry.get("uid") or 0)

    out = []
    section = subsection = parent = None
    for entry in sorted(entries, key=order_key):
        raw = str(entry.get("comment") or "").strip()
        level = classify_title(raw)
        name = clean_title(raw)
        if level == "section":
            section, subsection, parent = name, None, None
        elif level == "subsection":
            subsection, parent = name, None
        elif level == "leaf":
            parent = name
        out.append({
            "uid": entry.get("uid"),
            "title": name,
            "raw_title": raw,
            "level": level,
            "section": section,
            "subsection": subsection,
            # A child hangs from the leaf above it; a leaf hangs from nothing.
            "parent": parent if level == "child" else None,
            # A rule with no content of its own is scaffolding: it should
            # become structure, never an entry a retrieval can return.
            "structural": (level in ("section", "subsection")
                           and not str(entry.get("content") or "").strip()),
            "content": entry.get("content") or "",
            "keys": entry.get("key") or [],
            "constant": bool(entry.get("constant")),
        })
    return out


# --- knowledge derivation ---------------------------------------------------
#
# Deliberately keyword-based on the SECTION NAME rather than on the entry, and
# deliberately generic rather than Re:Zero-specific: the engine must not carry a
# mapping that only works for one book. Anything unmatched falls to
# common/global, which is the honest default for a published setting book --
# its whole purpose is describing what is true and known in that world.

_META_WORDS = ("writing style", "style guide", "naming", "instruction",
               "system prompt", "read this", "author", "ooc", "formatting")
_LOCATION_WORDS = ("location", "place", "geography", "region", "city",
                   "kingdom", "territory", "map", "settlement")
_ESOTERIC_WORDS = ("authority", "curse", "forbidden", "secret", "hidden",
                   "occult", "taboo", "heresy", "witch")
_SCHOLARLY_WORDS = ("magic", "ability", "abilities", "protection", "science",
                    "technology", "arcana", "history", "theory", "lore")


# A trailing parenthetical is a VARIANT of the same place, not a different one.
# Live: `[›] Lugunica Currency` follows `[⤹] Dragon Kingdom of Lugunica (Lite)`
# -- an abridged alternate of the entry above it -- so the child resolved to a
# place called "Dragon Kingdom of Lugunica (Lite)", which matches nothing a
# scene will ever be standing in.
_VARIANT_SUFFIX_RE = re.compile(r"\s*\([^)]{1,24}\)\s*$")


def _place_name(name):
    text = str(name or "").strip()
    previous = None
    while previous != text:
        previous = text
        text = _VARIANT_SUFFIX_RE.sub("", text).strip()
    return text


def _matches(text, words):
    """Whole-word matching, never substring.

    Caught by test: "author" in the meta list matched "AUTHORITY", so every
    Authority entry in the Re:Zero book was classified as an authoring
    instruction and excluded from world knowledge entirely -- a whole power
    system silently deleted from what anyone in that world can know. Substring
    matching on a keyword list fails exactly this way, quietly and in the
    direction of doing less.
    """
    low = str(text or "").casefold()
    return any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in words)


# WORLD MECHANICS VS LOCATIONAL KNOWLEDGE, and why STRUCTURE decides it alone.
#
# How the world works is not where you are standing, and the two must not be
# confused: an innkeeper knowing the local currency is a different claim from
# an innkeeper knowing how souls reincarnate. That distinction is already made
# by SECTION -- Abilities, Magic, Authority and Curse resolve `global`, and
# only what the author filed under a Locations heading is ever `local`.
#
# Using the entry's `category` as a second signal was tried and MEASURED WORSE,
# so it is deliberately absent. `guess_category` calls `Lugunica Currency` a
# `mechanic`, which would have destroyed the exact case this feature exists to
# serve, and it calls Costuul, Flanders, the Kararagi City-States and the Holy
# Kingdom of Gusteko `mechanic`/`myth` too -- four real places that would have
# lost their locality to fix one genuinely mis-filed leaf (`Od Lagna`, the
# entity governing the cycle of souls, sitting under "Other Locations" because
# it is a thing you can point at).
#
# One mis-filed entry is the cheaper error, and the author's own placement is
# better evidence than a keyword guess over the same text.


def derive_knowledge(record):
    """`(knowledge_tag, knowledge_range, knowledge_locations)` for one record.

    NO `category` PARAMETER, and there used to be one that the body never
    mentioned. The comment above is a long argument that the entry's category
    is the wrong second signal and measurably makes this worse; leaving it in
    the signature meant a reader could supply it and get the rejected
    behaviour -- which is to say nothing at all, silently.

    `(None, None, None)` for authoring scaffolding -- a "Writing Style" entry
    is an instruction to the engine and must never reach a character as
    something their world knows. That distinction is the single most valuable
    thing the tree buys, and it is invisible in a flat import.
    """
    if record.get("structural"):
        return (None, None, None)
    section = record.get("section") or ""
    subsection = record.get("subsection") or ""
    both = f"{section} {subsection}"

    if _matches(section, _META_WORDS) or _matches(record.get("title"), _META_WORDS):
        return (None, None, None)

    if _matches(both, _ESOTERIC_WORDS):
        tag = "esoteric"
    elif _matches(both, _SCHOLARLY_WORDS):
        tag = "scholarly"
    else:
        tag = "common"

    # LOCAL means "known where it applies", and the place it applies to is the
    # leaf itself for a location, or the leaf a child hangs from. That second
    # case is the whole point: "Lugunica Currency" is local knowledge about
    # Lugunica because of where its author put it, and nothing else in the file
    # says so.
    if _matches(both, _LOCATION_WORDS):
        # AN EXPLICIT NESTING OUTRANKS A GUESSED CATEGORY. A `[›]` child was
        # placed under its parent BY THE AUTHOR, so "Lugunica Currency" under
        # "Dragon Kingdom of Lugunica" is local to Lugunica and stays that way
        # -- `guess_category` calls it a `mechanic`, and letting that win threw
        # away the one case this whole feature exists to serve.
        #
        # The veto applies only to a LEAF, where nothing was nested and the
        # section is the only evidence. That is where "Od Lagna" sits -- the
        # entity governing the world's cycle of souls, filed under "Other
        # Locations" because it is a thing you can point at. A rule about how
        # the world works is true and known the same way everywhere.
        if record.get("level") == "child":
            where = _place_name(record.get("parent"))
            if where:
                return (tag, "local", [where])
        where = _place_name(record.get("parent") or record.get("title"))
        return (tag, "local", [where] if where else None)
    return (tag, "global", None)
