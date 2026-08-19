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

"Becomes canon" is a WRITE, not a flag. For two releases this module set
`rec["status"] = "ratified"` in its own world-KV blob and wrote nothing into
`lore_entries`, which is where every fact established during play actually
lives and the only store anything reads back (search_lore -> mapping's
relevant_lore -> the Director's and perception's payloads). A ratified claim
therefore became true and unreachable in the same instant -- the exact failure
the paragraph above says this module exists to prevent, moved one step later.
`settle_claims` now writes it (see `canon_entry`).

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

from core.db import q, wget, wset

# A claim nobody ratifies or contradicts within this many turns has quietly
# become "something someone said once" -- which is the realistic outcome for
# most tavern talk. Expired claims are dropped rather than kept forever, so the
# Director's payload cannot grow without bound across a long chat.
#
# Counted in PLAYER TURNS, and every one of them is a real chance: the live
# claims ride `director_resolve`'s payload unconditionally
# (agents/director.py's `unratified_claims` field), not only when the player
# revisits the place the claim is about. So expiry means the sole ratifier
# declined eight consecutive invitations, which is a decision, not a missed
# window -- and expiry unsays nothing, it only stops re-asking. Nothing here is
# tuned per subject kind (a place outliving a person, say): this module cannot
# tell a place from a person without guessing at a bare capitalized phrase.
#
# The corpus is no longer empty, and what it measures is the GATE rather than
# the TTL: chat 67 holds 7 claims, all 7 ratified, 0 contradicted, 0 expired
# -- every one of them by the same-beat brush-past `_verdicts` no longer
# accepts. So the TTL has still never been tested against a claim that had to
# survive to be taken up; do not tune it from that 7. See the note in
# docs/design/BACKGROUND_LIFE_DESIGN.md.
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

# The shortest reference an ADOPTION may be inferred from. Explicit
# ratification has no such floor -- the Director naming a claim is a decision
# whatever the name's length -- but inference reads a name out of running
# prose, and a two- or three-character run says nothing about whether the
# fiction took anything up.
MIN_INFERRED_REF_CHARS = 4

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


def _mint(chat_id, turn_idx, claims, stored):
    """{key: record} for the claims of this beat that are not already stored.

    Shared by `record_claims` and `prepare_canon` so both see exactly the same
    set: a claim can be asserted and EXPLICITLY settled in the same beat, so
    the pre-transaction pass has to know about claims that are not in the blob
    yet. (Inferred adoption cannot land on the claim's own beat -- see
    `_verdicts` -- because `background_react` runs after `director_resolve`,
    so that beat's record predates the claim.)
    """
    minted = {}
    for c in claims or []:
        claimant = str((c or {}).get("claimant") or "").strip()
        text = str((c or {}).get("text") or "").strip()
        if not claimant or not text:
            continue
        cid_key = _claim_id(chat_id, turn_idx, claimant, text)
        if cid_key in stored or cid_key in minted:
            continue
        minted[cid_key] = {
            "claimant": claimant,
            "text": text,
            "refs": [str(r) for r in ((c or {}).get("refs") or [])],
            "credence": str((c or {}).get("credence") or "unknown"),
            "turn": turn_idx,
            "status": "unratified",
            "expires_turn": turn_idx + CLAIM_TTL_TURNS,
        }
    return minted


def record_claims(chat_id, turn_idx, claims):
    """Persist newly-asserted background lore. `claims` is an iterable of
    {claimant, text, refs, credence}. Idempotent by content hash so a rerun of
    the same beat does not duplicate."""
    stored = wget(chat_id, "background_claims", {}) or {}
    minted = _mint(chat_id, turn_idx, claims, stored)
    if minted:
        stored.update(minted)
        wset(chat_id, "background_claims", stored)
    return len(minted)


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


# Canon in this engine is `lore_entries` in the chat's own canon lorebook
# (memory.ensure_chat_canon_book) -- the only durable store of facts written
# DURING play, and the only one anything reads back into a prompt. `other` is
# the honest category: this module cannot tell an invented person from an
# invented place from an invented incident without guessing, and `knowledge` is
# excluded from search_lore outright, so a wrong guess there would write the
# fact straight back out of reach.
CANON_CATEGORY = "other"
# A stable, greppable provenance stamp. It is also the denominator this lane
# has never had: `SELECT count(*) FROM lore_entries WHERE source_notes LIKE
# 'ratified background claim%'` is how anyone finds out whether ratification
# has ever happened, which is the measurement any future TTL change needs.
CANON_SOURCE_PREFIX = "ratified background claim"


# Where the engine holds no sayable name for the claimant. Canon has to
# attribute the line to somebody -- an unattributed quotation is a fact wearing
# quotation marks -- and "somebody in the room" is the honest attribution.
ANONYMOUS_CLAIMANT = "a bystander"

# Symmetric pairs a quoted line may already be wrapped in. `canon_entry` quotes
# the line itself, and a quotation of a quotation is a different sentence.
_QUOTE_PAIRS = ('""', "''", "“”", "‘’", "«»", "「」")


def _unwrap_quotes(text):
    """One symmetric pair of quotation marks stripped, repeatedly.

    Whether the line arrives quoted is the background lane's business and it
    varies: a model asked for an `exact_quote` sometimes includes the marks
    and sometimes does not. Canon supplies its own, so what it receives must
    be the line rather than a rendering of it.
    """
    out = str(text or "").strip()
    while len(out) >= 2:
        pair = out[0] + out[-1]
        if pair not in _QUOTE_PAIRS:
            break
        out = out[1:-1].strip()
    return out


def claimant_label(chat_id, claimant, scene=None):
    """The name canon may attribute a claim to, or "" for none.

    The claimant reaches this module as whatever spelling the background lane
    keyed the presence by, and that lane keys some presences by scene entity
    id. `world.subjects.speakable_name` is the seam that knows the difference:
    it round-trips an id to the display name its ledger holds, passes a plain
    name through, and answers "" for a handle no ledger owns.
    """
    text = str(claimant or "").strip()
    if not text:
        return ""
    from world.subjects import is_opaque_handle, speakable_name

    try:
        if scene is None:
            scene = wget(chat_id, "scene", {}) or {}
        return speakable_name(chat_id, scene, text)
    except Exception:
        # Canonicalisation is a courtesy; the floor is that an engine id never
        # reaches prose, and that holds without a database.
        return "" if is_opaque_handle(text) else text


def canon_entry(rec, speaker=None):
    """The lore row a ratified claim becomes: keys, title, content, provenance.

    Attributed, never paraphrased. The claim is a line somebody said, and the
    only way to turn it into a tidy third-person fact would be to ask a model
    -- which would put a second author between the Director's adoption and what
    canon ends up saying. The refs are the entry's `keys` because they already
    are short referring phrases (MAX_REF_WORDS exists for exactly that), which
    is what lore keys are for.

    And the entry says the line was SAID, never that it is TRUE. That is what
    ratification establishes: the Director let a bystander's line stand as part
    of the story. What the line itself asserts is a separate question the
    Director did not answer, and a wrapper that answers it inverts an entire
    class of ordinary utterance -- a denial, a boast, a mistake, a rumour
    repeated. Live, chat 67: "Never heard of Lugunica" was stamped "the
    Director has established this as true."

    `speaker` is the resolved display name (`claimant_label`). Absent one, the
    stored claimant is used, and an engine handle is refused here too: this is
    the last place before the text becomes canon, so the floor belongs here
    rather than only at the callers.
    """
    from world.subjects import is_opaque_handle

    named = str(speaker or rec.get("claimant") or "").strip()
    if not named or is_opaque_handle(named):
        named = ANONYMOUS_CLAIMANT
    said = " ".join(_unwrap_quotes(rec.get("text")).split())
    refs = [str(r).strip() for r in (rec.get("refs") or []) if str(r).strip()]
    return {
        "keys": ", ".join(refs),
        "title": refs[0] if refs else "",
        "content": '%s said: "%s" — the Director let this stand as part of the '
                   'story. What is established is that it was said; the line '
                   'itself may be true, mistaken, a boast or a denial.'
                   % (named, said),
        "source_notes": "%s: claimed turn %s by %s, ratified turn %s" % (
            CANON_SOURCE_PREFIX, rec.get("turn"), named,
            rec.get("ratified_turn")),
    }


def write_canon(chat_id, claim_key, rec, embedding=None):
    """Write one ratified claim into the chat's canon lorebook.

    Keyed by the claim's own content hash (`entry_uid`), so a rerun of the beat
    -- checkpoint restore replays commit -- cannot mint a second entry for one
    ratification. Returns the lore entry id, or None if nothing was written.
    """
    from mind.memory import add_lore, ensure_chat_canon_book

    entry_uid = "%s:canon" % claim_key
    existing = q("SELECT id FROM lore_entries WHERE entry_uid=?",
                 (entry_uid,), one=True)
    if existing:
        return existing["id"]
    book_id = ensure_chat_canon_book(chat_id)
    if not book_id:
        return None
    entry = canon_entry(rec, speaker=claimant_label(chat_id, rec.get("claimant")))
    return add_lore(
        book_id, entry["keys"], entry["content"],
        turn_added=rec.get("ratified_turn"), category=CANON_CATEGORY,
        title=entry["title"] or None, entry_uid=entry_uid,
        source_notes=entry["source_notes"], embedding=embedding,
    )


def prepare_canon(chat_id, turn_idx, new_claims, resolved_text,
                  ratified_refs=(), contradicted_refs=()):
    """Embeddings for the canon rows this beat is about to write, {key: vector}.

    Runs BEFORE the outer commit transaction. Embedding a lore entry is a
    provider round-trip with a request timeout on it, and the house rule is
    that slow provider work happens in preparation rather than under SQLite's
    write lock -- `prepare_mapping_commit` batches its own lore embeddings for
    the same reason. Best-effort by contract: a failure here costs the entries
    their prepared vector, never the turn.
    """
    stored = dict(wget(chat_id, "background_claims", {}) or {})
    stored.update(_mint(chat_id, turn_idx, new_claims, stored))
    if not stored:
        return {}
    ratified, _contradicted, _conflicted, _expired = _verdicts(
        stored, turn_idx, resolved_text, ratified_refs, contradicted_refs)
    if not ratified:
        return {}
    from llm.providers import embed_texts

    # One scene read for the whole batch: the two passes must agree, and
    # `write_canon` resolves the same claimant against the same ledger.
    scene = wget(chat_id, "scene", {}) or {}
    entries = [
        canon_entry(stored[k],
                    speaker=claimant_label(chat_id, stored[k].get("claimant"),
                                           scene=scene))
        for k in ratified]
    vectors = embed_texts([
        (e["keys"] + " " + e["content"]).strip() for e in entries])
    return {k: v for k, v in zip(ratified, vectors) if v is not None}


def _named_in_record(ref, text_cf):
    """True when `ref` appears in the objective record AS a reference.

    A substring is not a reference: "Rose" occurs inside "prose", and the
    branch this feeds writes canon, which is a one-way door. The boundary is
    required at the name's LEADING edge only, because a name legitimately
    inflects at its trailing one -- a plural, a possessive, a case ending are
    the fiction using the name rather than a different word.

    The boundary test asks for a CASED letter rather than any letter. A script
    that marks words with case also separates them, so a boundary is there to
    be found; a script that writes no spaces cannot satisfy that rule at all,
    and holding it to one would make every reference in it unratifiable.
    """
    needle = str(ref or "").casefold().strip()
    if len(needle) < MIN_INFERRED_REF_CHARS:
        return False
    start = text_cf.find(needle)
    while start != -1:
        prev = text_cf[start - 1] if start else ""
        if not (prev.isalpha() and prev.lower() != prev.upper()):
            return True
        start = text_cf.find(needle, start + 1)
    return False


def _verdicts(stored, turn_idx, resolved_text, ratified_refs, contradicted_refs):
    """(ratified, contradicted, conflicted, expired) claim keys for one sweep.

    Split out of `settle_claims` so the commit path can reach the SAME verdict
    twice: once before the outer write transaction opens, to embed the canon
    text without a provider round-trip under SQLite's write lock (AGENTS.md
    persistence boundaries), and once inside it, where the writes happen.
    Pure over its inputs so the two passes cannot disagree.
    """
    text_cf = str(resolved_text or "").casefold()
    ratified_cf = {str(r).strip().casefold()
                   for r in (ratified_refs or []) if str(r).strip()}
    contra_cf = {str(r).strip().casefold()
                 for r in (contradicted_refs or []) if str(r).strip()}
    ratified, contradicted, conflicted, expired = [], [], [], []
    for key, rec in stored.items():
        if rec.get("status") != "unratified":
            continue
        refs = [str(r) for r in (rec.get("refs") or [])]
        named_true = any(r.strip().casefold() in ratified_cf for r in refs)
        # Contradiction is EXPLICIT ONLY, where adoption may also be inferred
        # from the Director writing the ref into the objective record. The
        # asymmetry is deliberate: prose naming a claim's subject is evidence
        # the fiction took it up, but prose can no more announce a rejection
        # than it can announce silence -- "the Widow denies it" and "the Widow
        # says it again" share every distinctive token.
        named_wrong = any(r.strip().casefold() in contra_cf for r in refs)
        if named_wrong:
            contradicted.append(key)
            # Named in BOTH lists: the Director disagreed with itself. Recorded
            # as a disagreement rather than resolved into a middling truth --
            # a contradiction is a dispute, never an average -- and settled the
            # way that does not write, because canon is a one-way door.
            if named_true:
                conflicted.append(key)
            continue
        # Adoption inferred from the record can only be inferred from a LATER
        # record. `background_react` runs after `director_resolve`
        # (agents/runtime.py's plan), so the resolved event of the beat a
        # claim was made in was written before the presence spoke: a reference
        # standing in it is the presence echoing the Director's own prose,
        # which is the opposite of the Director taking up the presence's
        # invention. Ratifying is a deliberate act and canon is a one-way
        # door, so a brush-past may not open it. Measured, chat 67: 7 claims,
        # 7 ratified, 0 contradicted, 0 expired -- a three-outcome design
        # collapsed onto its one irreversible branch, on same-beat text.
        # An EXPLICIT verdict is exempt: naming a claim is a decision whenever
        # it arrives, and `_mint` exists so the same-beat spelling of that
        # decision still finds the record.
        adopted_later = (
            turn_idx > int(rec.get("turn") or 0) and bool(refs)
            and any(_named_in_record(r, text_cf) for r in refs))
        if named_true or adopted_later:
            ratified.append(key)
            continue
        if turn_idx > int(rec.get("expires_turn") or -1):
            expired.append(key)
    return ratified, contradicted, conflicted, expired


def settle_claims(chat_id, turn_idx, resolved_text, ratified_refs=(),
                  contradicted_refs=(), canon_embeddings=None):
    """Post-resolution sweep, and the moment a claim's outcome becomes real.

    RATIFIED -- the Director adopted it, either naming it in
    `state_diff.ratified_claims` or writing its distinctive reference into the
    objective record of a LATER beat (`_verdicts`). The claim is WRITTEN INTO
    CANON here (`canon_entry`); flipping a status field and stopping was the
    defect this replaces.

    CONTRADICTED -- the Director named it in `state_diff.contradicted_claims`.
    The record is kept, claimant and all, rather than deleted: that a bystander
    was wrong is the thing a later beat gets to show, and a rejected claim that
    left no trace was byte-identical to one nobody bothered with.

    EXPIRED -- the TTL ran out with nobody taking it up. Dropped, not archived:
    an expired claim is something a stranger said once. Keeping it would grow
    the blob forever for no narrative benefit.

    `canon_embeddings` is {claim_key: vector} from `prepare_canon`. Absent, the
    canon write still happens -- correctness first -- and pays for its own
    embedding where it stands.
    """
    stored = wget(chat_id, "background_claims", {}) or {}
    if not stored:
        return {"ratified": 0, "contradicted": 0, "expired": 0}
    ratified, contradicted, conflicted, expired = _verdicts(
        stored, turn_idx, resolved_text, ratified_refs, contradicted_refs)
    embeddings = canon_embeddings or {}
    for key in ratified:
        rec = stored[key]
        rec["status"] = "ratified"
        rec["ratified_turn"] = turn_idx
        rec["canon_entry_id"] = write_canon(chat_id, key, rec,
                                            embedding=embeddings.get(key))
    for key in contradicted:
        rec = stored[key]
        rec["status"] = "contradicted"
        rec["contradicted_turn"] = turn_idx
        if key in conflicted:
            rec["ratification_conflict"] = True
    for key in expired:
        del stored[key]
    wset(chat_id, "background_claims", stored)
    return {"ratified": len(ratified), "contradicted": len(contradicted),
            "expired": len(expired)}


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
