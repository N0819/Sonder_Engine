"""A line that names what only this mind knows, as a fact this mind is handed.

The firewall restricts the FLOW of knowledge, and it is a gap: two people do
not share a head. That gap is generative only while a mind can NOTICE it
being crossed -- deception, dramatic irony and a stranger who knows too much
all depend on the mind registering that a fact arrived with no channel behind
it. Measured (scratch play 2026-09-14, chat 2 turn 12): the player, whom Bram
Toll had never met, said "Your sister. Wen. What's wrong with her?" Bram's
only knowledge that his sister is called Wen sat in his card's
`knowledge.private_history` with `known_by: []`; nobody aboard had been told.
He answered the question. Nothing in his payload said a stranger could not
have had the name, because the engine that knew it was the only party that
never said so.

This module computes that one fact deterministically and hands it to the
mind as a cue beside the line -- `perception.impossible_knowledge`. It is
built out of things the mind already has (its own private history, the
words that reached it) and SUBTRACTS everything with a channel: a name the
cast carries, a room, a public history, a lore entry it may read, a matter it
shared with the speaker, or a word already said aloud in this story. Nothing
here widens what the mind receives; a cue can only point at prose the
observer's own view already contains, by that observation's id.

No word list. What counts as a name is a property of how the text is
written -- capitalised where a sentence does not begin, and never written in
lower case in the same text -- so the rule reaches a name in any story; an
uncased script has no such signal and gets no cue, which is the deferred
half, not a leak.
"""

from __future__ import annotations

import json
import re

from core.db import q
from story.character_schema import name_boundary_regex

from .common import _significant_name_tokens

_WORD_RE = re.compile(r"\w+")

#: What may stand between a sentence's end and its first word: closing and
#: opening quotation marks and brackets, in the shapes English and Japanese
#: prose write them. Punctuation, not vocabulary.
_SENTENCE_LEAD = " \t\"'“”‘’«»「」『』()[]"
_SENTENCE_ENDS = ".!?…:;\n\r。！？"


def _tokens(text):
    return _WORD_RE.findall(str(text or ""))


def folded_tokens(text):
    """Every word of `text`, casefolded, in whatever script it is written."""
    return {tok.casefold() for tok in _tokens(text)}


def naming_tokens(text):
    """The casefolded tokens `text` writes as NAMES.

    A name is a token capitalised where a sentence does not begin, and never
    written in lower case anywhere in the same text: "his sister Wen's
    medicine" names Wen; "The medicine ran out. The shop was shut" names
    nothing, because the only capital is sentence-initial. Titles and short
    tokens are dropped by the same floor every name comparison uses
    (`_significant_name_tokens`). A script without letter case yields no
    tokens here -- no signal, so no cue, rather than every word.
    """
    text = str(text or "")
    lowered = set()
    capitalised = []
    for match in _WORD_RE.finditer(text):
        tok = match.group(0)
        if not tok[0].isupper():
            if tok[0].islower():
                lowered.add(tok.casefold())
            continue
        before = text[:match.start()].rstrip(_SENTENCE_LEAD)
        if not before or before[-1] in _SENTENCE_ENDS:
            continue
        capitalised.append(tok)
    out = set()
    for tok in capitalised:
        for low in _significant_name_tokens(tok):
            if low not in lowered:
                out.add(low)
    return out


def impossible_knowledge_cues(*, own_entries, lines, delivered, public_texts,
                              speaker_keys, already_aired, label):
    """The cues for one observer on one beat.

    `own_entries` are THIS mind's private-history rows (`content`,
    `known_by`); `lines` are `(speaker, text)` for every line another mind
    spoke this beat, in the order they were spoken; `delivered` is
    `(line_ref, text)` for each observation this observer was actually
    handed; `public_texts` is every text whose words have a channel (names,
    rooms, public histories, lore); `speaker_keys` maps a speaker to the
    casefolded names they answer to, for the `known_by` check;
    `already_aired(token)` says whether the story has heard the word said
    aloud before; `label(speaker)` is what THIS observer may call them.

    A cue is `{speaker, line_ref, private_matter}`: the line, by the id of
    the observation that carried it, and the private matter it touches. A
    token cued once in a beat is aired for every later line in it -- the
    second mind to say the word has a channel, the first one did not.
    """
    public = set()
    for text in public_texts or ():
        public |= folded_tokens(text)
    entries = []
    for entry in own_entries or ():
        if not isinstance(entry, dict):
            continue
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        private = naming_tokens(content) - public
        if not private:
            continue
        shared = {str(name or "").strip().casefold()
                  for name in (entry.get("known_by") or [])}
        entries.append((content, private, shared))
    if not entries:
        return []
    handed = [(str(ref or ""), folded_tokens(text))
              for ref, text in (delivered or ()) if ref]
    aired_this_beat = set()
    cues = []
    seen = set()
    for speaker, text in lines or ():
        speaker = str(speaker or "").strip()
        keys = {k.casefold() for k in (speaker_keys or {}).get(speaker, ())}
        keys.add(speaker.casefold())
        line_tokens = folded_tokens(text)
        newly_aired = set()
        for content, private, shared in entries:
            if shared & keys:
                # The speaker is one of the people this mind shared it with:
                # a channel, whatever they do with it.
                continue
            for token in sorted(private & line_tokens):
                if token in aired_this_beat or already_aired(token):
                    continue
                ref = next((ref for ref, words in handed if token in words),
                           None)
                if ref is None:
                    # Said, but not handed to this observer -- withheld,
                    # muffled to a fragment, or out of earshot.
                    continue
                newly_aired.add(token)
                key = (speaker, ref, content)
                if key in seen:
                    continue
                seen.add(key)
                cues.append({
                    "speaker": str(label(speaker) if label else speaker),
                    "line_ref": ref,
                    "private_matter": content,
                })
        aired_this_beat |= newly_aired
    return cues


def _spoken_texts(content):
    """Every spoken or written line a stored Director variant records."""
    out = []
    for entry in content.get("dialogue_log") or []:
        if isinstance(entry, dict):
            out.append(str(entry.get("exact_quote") or ""))
    for element in content.get("sequence") or []:
        if isinstance(element, dict) and element.get("type") in (
                "speech", "communication"):
            out.append(str(element.get("text") or element.get("content")
                           or ""))
    out.append(str(content.get("speech") or ""))
    return [text for text in out if text.strip()]


def aired_in_story(chat_id, frame_id, before_turn_idx, token, cache=None):
    """Has `token` been said aloud in this story before this beat?

    The engine keeps no ledger of which private facts have been spoken --
    `known_by` is authored and never written at runtime -- so the record of
    what has been aired is the committed dialogue itself: every Director
    `dialogue_log` quote (the player's lines included) and every interpreted
    player utterance. Objective record, read to SUBTRACT: a word anyone has
    said aloud has a channel, whoever heard it.

    One `LIKE` prefilter per token, then a whole-word check on the rows it
    admits, so a beat with no candidate costs no read at all and a beat with
    one costs a single indexed scan. Cached per beat in the turn snapshot.
    SQLite's `LIKE` folds case for ASCII alone, so a token written in any
    other script skips the prefilter rather than risk missing the row that
    aired it: a miss here would fire a cue the story had already earned.
    """
    word = str(token or "").strip()
    if not word or before_turn_idx is None:
        return False
    key = ("aired", int(chat_id), frame_id, int(before_turn_idx),
           word.casefold())
    if isinstance(cache, dict) and key in cache:
        return cache[key]
    sql = ("SELECT v.content AS content FROM turns t "
           "JOIN steps s ON s.turn_id=t.id "
           "JOIN variants v ON v.step_id=s.id AND v.active=1 "
           "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? "
           "AND s.key IN ('director_resolve','director_interpret')")
    params = [int(chat_id), int(before_turn_idx), frame_id]
    if word.isascii():
        escaped = (word.replace("\\", "\\\\").replace("%", "\\%")
                   .replace("_", "\\_"))
        sql += " AND v.content LIKE ? ESCAPE '\\'"
        params.append(f"%{escaped}%")
    rows = q(sql, tuple(params))
    pattern = name_boundary_regex(word, re.IGNORECASE)
    found = False
    for row in rows:
        try:
            content = json.loads(row["content"]) or {}
        except (TypeError, ValueError):
            continue
        if not isinstance(content, dict):
            continue
        if any(pattern.search(text) for text in _spoken_texts(content)):
            found = True
            break
    if isinstance(cache, dict):
        cache[key] = found
    return found
