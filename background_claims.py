"""Unratified lore claimed by background presences.

The live tavern run (demo/tavern_scene_life/findings.md) showed the scene
manager inventing small world facts through its people at roughly one proper
noun per turn -- "Tam Briddock's boy", "the tinker's lot last month" -- neither
of which appears anywhere in the Director's own output for that beat. It also
showed WHY that is worth keeping: the t2 invention was absorbed into canon and
became the dramatic spine of the best scene in the run.

So this module does not suppress invention. It makes every OUTCOME of an
invented claim diegetically coherent, which is the actual problem. Today the
failure mode is "the engine forgot it said this" -- the player asks who Tam
Briddock is and nothing in the world knows. That is incoherence. With a claim
recorded, the three possible outcomes are all ordinary fiction:

  ratified    -- the Director adopts it; it becomes canon.
  contradicted-- the Director says otherwise; the presence was WRONG, and
                 because the claimant is recorded the world can show that.
                 A bystander who misremembers is characterization, not a bug.
  expired     -- nobody followed up. It was tavern talk. Also fine.

None of those is incoherent, which is what "robust failure" means here.

This deliberately mirrors the Player Authority Contract in prompts.py's
director_interpret entry: a player's claim about another character's past words
is recorded as CLAIMED, not established, and the named party may confirm,
correct or ignore it. A background presence's assertion about the world gets
exactly the same treatment, for exactly the same reason -- neither of them owns
objective causality. The Director remains the sole ratifier.

Storage is world-KV (`background_claims`), frame-scoped like everything else
wget/wset touches, so a flashback cannot inherit claims from a future era.
"""

from __future__ import annotations

import hashlib
import re

from db import wget, wset

# A claim nobody ratifies or contradicts within this many turns has quietly
# become "something someone said once" -- which is the realistic outcome for
# most tavern talk. Expired claims are dropped rather than kept forever, so the
# Director's payload cannot grow without bound across a long chat.
CLAIM_TTL_TURNS = 8
# Never surface more than this many at once; the Director has a job to do.
MAX_SURFACED = 6

# Words that begin a sentence or are otherwise capitalized without naming
# anything. Deliberately small: a false positive costs one harmless recorded
# claim, a false negative costs an untracked invention.
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "but", "or", "if", "so", "then", "that", "this",
    "these", "those", "there", "here", "it", "its", "he", "she", "they", "you",
    "i", "we", "his", "her", "their", "your", "my", "our", "who", "what",
    "when", "where", "why", "how", "aye", "nay", "no", "yes", "well", "mind",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "not", "nothing", "nobody", "someone", "something", "all", "some",
    "any", "every", "both", "still", "just", "only", "even", "never", "always",
    "come", "came", "go", "went", "take", "took", "bet", "heard", "said",
})

# Ranks and honorifics. A line ending "...profiles, Captain." is addressing
# someone, not naming a new person -- the Enterprise run recorded "Captain" as
# invented lore and then ratified it. Titles are also stripped when matching
# against known names, so "Worf" is recognized as the established
# "Lieutenant Worf" rather than a second person.
_TITLES = frozenset({
    "dr", "mr", "mrs", "ms", "mister", "madam", "madame", "sir", "maam",
    "lord", "lady", "master", "professor", "doctor", "captain", "commander",
    "cmdr", "lieutenant", "lt", "ensign", "chief", "admiral", "general",
    "colonel", "major", "sergeant", "corporal", "private", "father", "mother",
    "sister", "brother", "reverend", "king", "queen", "prince", "princess",
    "number one", "counselor", "counsellor", "helm", "conn", "ops", "tactical",
    "engineering", "bridge", "sickbay",
})

# A ratification key must be short enough to actually appear in later prose.
# The Enterprise run had La Forge self-declare a whole sentence as a ref, so
# when Picard acted on it ("isolate that junction") nothing matched and a claim
# the fiction had plainly adopted stayed hearsay until expiry.
MAX_REF_WORDS = 6

# Hyphenated given names are one token, not two: without this "Captain
# Jean-Luc Picard" split into "Captain Jean" + "Luc Picard" and neither matched
# the roster's "Jean-Luc Picard".
_WORD = r"[A-Z][a-z']+(?:-[A-Z][a-z']+)*"
_PROPER = re.compile(rf"\b({_WORD}(?:\s+{_WORD})*)\b")
# A capitalized word is not evidence of a name when it merely opens a sentence.
_SENTENCE_START = re.compile(r"(?:^|[.!?…]['\"]?\s+)$")
_CONTRACTION = re.compile(r"'(?:d|s|ll|re|ve|t|m)$", re.IGNORECASE)
_LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)


def _normalize_ref(phrase):
    """Strip a possessive/contraction tail so "Tam Briddock's" and "Tam
    Briddock" are one name rather than two claims."""
    words = [_CONTRACTION.sub("", w) for w in str(phrase or "").split()]
    return " ".join(w for w in words if w).strip()


def _strip_titles(name):
    """Leading ranks/honorifics removed, so "Lieutenant Worf" and "Worf" are
    the same referent."""
    words = str(name or "").strip().split()
    while words and words[0].strip(".,").casefold() in _TITLES:
        words = words[1:]
    return " ".join(words).strip()


def is_title_only(phrase):
    """True when the phrase is nothing but a rank/honorific -- a form of
    address, never an invented name."""
    cf = _normalize_ref(phrase).casefold().strip(".,!?")
    if not cf:
        return True
    if cf in _TITLES:
        return True
    return all(w.strip(".,") in _TITLES for w in cf.split())


def _known_variants(known):
    """Known names plus their article-stripped forms, so an extra saying
    "Widow" is recognized as referring to the established "The Widow" rather
    than inventing someone new."""
    out = set()
    for k in known or []:
        name = _normalize_ref(k)
        if not name:
            continue
        out.add(name.casefold())
        stripped = _LEADING_ARTICLE.sub("", name).strip()
        if stripped:
            out.add(stripped.casefold())
        titleless = _strip_titles(name)
        if titleless:
            out.add(titleless.casefold())
    return out


def _claim_id(cid, turn_idx, claimant, text):
    digest = hashlib.sha256(
        f"{cid}:{turn_idx}:{claimant}:{text}".encode("utf-8")).hexdigest()[:16]
    return f"bgclaim:{digest}"


def novel_proper_nouns(quote, known):
    """Capitalized names in `quote` that are not already known to the world.

    A deterministic backstop to the manager's own self-declared `asserts`, on
    the same principle as every other floor in this codebase: the model is
    asked to report what it invented, and a cheap check catches the times it
    does not. `known` is the union of scene entity names, room names, cast and
    persona names, and previously-recorded claim refs -- anything already in
    play is not a new invention.
    """
    text = str(quote or "")
    known_cf = _known_variants(known)
    out = []
    for match in _PROPER.finditer(text):
        phrase = _normalize_ref(match.group(1))
        if not phrase:
            continue
        cf = phrase.casefold()
        if cf in known_cf or cf in _STOPWORDS:
            continue
        # A bare rank is a form of address, not a new name.
        if is_title_only(phrase):
            continue
        if _LEADING_ARTICLE.sub("", cf).strip() in known_cf:
            continue
        if _strip_titles(phrase).casefold() in known_cf:
            continue
        # A single capitalized word that only opens a sentence is not a name --
        # and "sentence start" is not just offset 0 ("...end of autumn. That'd
        # be..." produced a spurious "That'd" claim in the tavern run).
        if " " not in phrase and _SENTENCE_START.search(text[:match.start()]):
            continue
        if all(w in _STOPWORDS for w in cf.split()):
            continue
        # Already covered by a longer phrase captured this pass.
        if any(cf in prior.casefold() for prior in out):
            continue
        out.append(phrase)
    return out


def record_claims(chat_id, turn_idx, claims):
    """Persist newly-asserted background lore. `claims` is an iterable of
    {claimant, text, refs, credence}. Idempotent by content hash so a rerun of
    the same beat does not duplicate."""
    stored = wget(chat_id, "background_claims", {}) or {}
    added = 0
    for c in claims or []:
        claimant = str((c or {}).get("claimant") or "").strip()
        text = str((c or {}).get("text") or "").strip()
        if not claimant or not text:
            continue
        cid_key = _claim_id(chat_id, turn_idx, claimant, text)
        if cid_key in stored:
            continue
        stored[cid_key] = {
            "claimant": claimant,
            "text": text,
            "refs": [str(r) for r in ((c or {}).get("refs") or [])],
            "credence": str((c or {}).get("credence") or "unknown"),
            "turn": turn_idx,
            "status": "unratified",
            "expires_turn": turn_idx + CLAIM_TTL_TURNS,
        }
        added += 1
    if added:
        wset(chat_id, "background_claims", stored)
    return added


def unratified_claims(chat_id, turn_idx):
    """What the Director should be offered this beat: still-live claims, newest
    first. Shaped for a prompt payload, not for storage."""
    stored = wget(chat_id, "background_claims", {}) or {}
    live = [
        {"claimant": r.get("claimant"), "said": r.get("text"),
         "names": r.get("refs") or [], "credence": r.get("credence"),
         "turns_ago": max(0, turn_idx - int(r.get("turn") or 0))}
        for r in stored.values()
        if r.get("status") == "unratified"
        and turn_idx <= int(r.get("expires_turn") or -1)
    ]
    live.sort(key=lambda r: r["turns_ago"])
    return live[:MAX_SURFACED]


def settle_claims(chat_id, turn_idx, resolved_text, ratified_refs=()):
    """Post-resolution sweep. A claim is RATIFIED when the Director adopted it
    -- either naming it explicitly in state_diff/ratified_claims, or writing its
    distinctive reference into the objective record -- and EXPIRED when its TTL
    ran out with no one taking it up.

    Contradiction is deliberately NOT inferred here. The Director saying
    something incompatible is a normal beat, and an unratified claim simply
    stays unratified until it expires; guessing at semantic contradiction with
    string matching would be worse than leaving it to time.
    """
    stored = wget(chat_id, "background_claims", {}) or {}
    if not stored:
        return {"ratified": 0, "expired": 0}
    text_cf = str(resolved_text or "").casefold()
    ratified_cf = {str(r).strip().casefold() for r in (ratified_refs or [])}
    ratified = expired = 0
    for key, rec in list(stored.items()):
        if rec.get("status") != "unratified":
            continue
        refs = [str(r) for r in (rec.get("refs") or [])]
        adopted = any(r.strip().casefold() in ratified_cf for r in refs) or (
            bool(refs) and any(r.casefold() in text_cf for r in refs if len(r) >= 4))
        if adopted:
            rec["status"] = "ratified"
            rec["ratified_turn"] = turn_idx
            ratified += 1
            continue
        if turn_idx > int(rec.get("expires_turn") or -1):
            # Dropped, not archived: an expired claim is something a stranger
            # said once and nobody followed up on. Keeping it would grow the
            # blob forever for no narrative benefit.
            del stored[key]
            expired += 1
    wset(chat_id, "background_claims", stored)
    return {"ratified": ratified, "expired": expired}


def claimant_credence(blurb):
    """How much weight the FICTION already tells the player to give this
    speaker. Derived from the frozen blurb (§3.8), so the cue is authored
    rather than invented: a drunk's story reads as suspect on sight, the
    barkeep's does not. This is what makes an unratified claim safe to leave
    floating -- the player has already been signalled how much to trust it.
    """
    text = " ".join(str(v or "") for v in (blurb or {}).values()).casefold()
    if any(w in text for w in ("drunk", "ale-soaked", "rambling", "boast",
                               "liar", "gossip", "senile", "trails off",
                               "half-remember", "mutter")):
        return "low"
    if any(w in text for w in ("precise", "careful", "keeps the books",
                               "sober", "watches everything", "clerk")):
        return "high"
    return "ordinary"
