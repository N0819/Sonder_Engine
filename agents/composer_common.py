"""Leaf: the typed IR (`Percept`, `RenderedView`, kinds, channels), the opaque
ledger keys, the compositor-pack accessors and the phrase splicers every
builder and renderer shares, and `_safe_renderer`.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from language_runtime import (
    LanguagePackError,
    current_language_id,
    language_pack,
    linguistic,
    renderer_for,
)
from world.spatial import sense_adjusted
logger = logging.getLogger("agents.composer")


# --------------------------------------------------------------------------
# The IR
# --------------------------------------------------------------------------

# The complete vocabulary of admitted percepts, ENFORCED (see Percept below).
# It was read by nothing for long enough to go two kinds stale -- `pose` and
# `body_part` were minted by live builders and declared here by nobody, while
# `_STANDING_ORDER`, which IS read on every render, carried both. Two
# hand-maintained lists of one thing, and only the unread one was wrong.
PERCEPT_KINDS = (
    "environment", "presence", "pose", "appearance", "act", "speech",
    "communication", "cue", "demeanor",
    "sensation", "substance", "body_part", "body_region", "body_state",
    "crossing", "residue", "ambient", "scent",
)

CHANNELS = ("sight", "hearing", "touch", "interoception", "smell", "mixed")

# English is the reference adapter while Layer B is extracted card by card.
# Loading these transforms through the installed pack is intentional: the
# default language exercises the same pack discovery/validation path every
# future language uses, instead of leaving English as an untested special case.
_ENGLISH_COMPOSITOR = language_pack("en").card("compositor")


def _compositor(name):
    """One compositor value from the ACTIVE story pack, read at use time."""
    from language_runtime import compositor_value
    return compositor_value(name)
_EN_TEMPLATES = _ENGLISH_COMPOSITOR["templates"]


def _ling(name):
    return linguistic("agents.composer", name)

def _en(key, **values):
    return str(_EN_TEMPLATES[key]).format(**values)


def _t(key, **values):
    """One template from the ACTIVE story pack, English where the pack has
    no entry. For the text the composer builds BEFORE the language adapter
    sees it -- a pose referent, a spliced noun -- because that text is data
    the adapter renders verbatim, so an English article minted here reaches
    a Japanese page as "the 砂浜" (chat 122 on a copy, 2026-09-07)."""
    try:
        templates = _compositor("templates")
    except Exception:
        templates = _EN_TEMPLATES
    # `compositor_value` hands back a read-only mapping proxy, not a dict.
    template = templates.get(key) if isinstance(templates, Mapping) else None
    if template is None:
        template = _EN_TEMPLATES[key]
    return str(template).format(**values)


def _pack_words(name):
    """A determiner table from the ACTIVE pack, empty where it has none, so a
    language that takes no article leaves every branch a no-op in fact and
    not only in the docstring."""
    try:
        return frozenset(str(w).casefold() for w in (_compositor(name) or ()))
    except Exception:
        return frozenset()


def _lower_lead(text):
    """Sentence case off an authored phrase about to be spliced mid-sentence:
    the first letter is lowered when it is the ONLY capital in its word, so
    an acronym or a capitalised name inside the phrase keeps its case. A
    one-letter first word is that case too -- the article of "A woman's,
    past fifty" (a card's `embodiment.voice`, 2026-10-20) is lowered, where
    the test on the second character alone kept it, and the page read "The
    voice is A woman's"; an initial with its stop ("A. Smith") is not."""
    text = str(text or "").strip()
    if len(text) > 1 and text[0].isupper() and (
            text[1].islower()
            or (text[1] == " " and len(text) > 2 and text[2].islower())):
        return text[0].lower() + text[1:]
    return text


def _strip_sentence_ends(text):
    """Take the terminal stops off a phrase about to be spliced into a
    sentence -- the pack's stops, not the ASCII full stop alone. A Japanese
    presented appearance ends in 。 and was rendered inside its own label:
    "見知らぬごく普通の人間の若い女性。は手の届く距離にいる" (chat 122 on a
    copy, 2026-09-07)."""
    text = str(text or "").strip()
    try:
        ends = str(_ling("_SENTENCE_ENDS") or ".!?")
    except Exception:
        ends = ".!?"
    return text.rstrip(ends + ";:,、；：").rstrip()


@dataclass(frozen=True)
class Percept:
    """One admitted percept. `source_label` is ALREADY recognition/disguise
    gated -- a canonical name only ever appears here when the observer has
    earned it. `data` carries only surfaces the observer has a channel to,
    at the admitted fidelity (a fragment percept holds the fragment, never
    the full quote body)."""
    kind: str
    channel: str
    source_label: str = ""
    fidelity: str = "full"          # full|degraded|fragment|trace
    data: dict = field(default_factory=dict)
    salience: float = 0.4
    suddenness: float = 0.1
    order_key: int | None = None    # declared/beat order; None = standing state
    dedupe_key: str = ""

    def __post_init__(self):
        """Refuse a kind or channel nobody declared.

        The declarations are only a vocabulary if something asks. Both are
        closed sets minted exclusively by the builders in this module, so an
        undeclared value is a programming error, not a story the engine has
        to survive -- and a kind no renderer branch matches renders as the
        empty string, which is the failure this raise replaces: silent,
        invisible in tests, and indistinguishable from a percept that was
        correctly withheld.
        """
        if self.kind not in PERCEPT_KINDS:
            raise ValueError(f"undeclared percept kind: {self.kind!r}")
        if self.channel not in CHANNELS:
            raise ValueError(f"undeclared percept channel: {self.channel!r}")


def _sense_graded(level, channel, senses):
    """Shift one admission grade by the observer's card senses.

    `spatial.sense_adjusted` is THE senses gate (G4), and for a long time the
    only deterministic delivery path that asked it was the interaction
    micro-loop. Every builder in this module graded on the world alone, so an
    authored-blind card saw the room in its onset view, its outcome view and
    its memory of the beat, and was correctly blind for the length of one
    micro-round in between.

    `None` and an ordinary card return the level unchanged, byte-identical to
    before; the one direction that adds is capped inside `sense_adjusted`
    itself. Kept as a named wrapper rather than a bare call so the gate has
    one spelling here and every builder that grades can be seen to use it.

    No `blocked_by` here: every builder in this module grades a level that
    came back from `visual_level_between`, which was handed the senses and
    has already spent what the place did (A87) -- the dark has lifted by the
    time the level arrives. The one reader that
    grades a ROOM-level `sight_level` and needs the cause is
    `agents.common._delivery_ok`, and it calls `sense_adjusted` directly.
    """
    return sense_adjusted(level, channel, senses) if senses else level


def _short_hash(*parts):
    joined = "\x1f".join(str(p or "") for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def body_key(name):
    """Opaque, stable per-body ledger key. Canonical names never ride a
    Percept -- not even as bookkeeping -- so the IR invariant ("no field
    carries a fact the observer has no channel to") is checkable by simple
    string containment over the whole record."""
    return _short_hash("body", str(name or "").strip().casefold())


def standing_key(tag, subject_parts, content_parts):
    """One standing percept's dedupe key, as ``<tag>:<subject>:<content>``.

    THE KEY HAS TO ANSWER TWO QUESTIONS, and one hash could only answer the
    first. A renderer holding this beat's percepts and the observer's own
    previous ledger must be able to tell "the same fact, said again" from
    "this fact about the same thing, different now" from "I have never been
    told about this thing at all" -- unchanged, changed, first sight. A
    single hash over subject AND content collapses the last two: a pose that
    moved and a body that just walked in produce the same verdict, "a key I
    have not seen", so nothing could lead with what CHANGED.

    Both halves are hashes, so the invariant `body_key` exists for holds
    unaltered: no canonical name rides a Percept, not even as bookkeeping,
    and the whole record stays checkable by string containment.
    """
    return (f"{tag}:{_short_hash(*subject_parts)}"
            f":{_short_hash(*content_parts)}")


def _subject_prefix(dedupe_key):
    """``<tag>:<subject>`` of a split standing key, or None for any other
    shape. Old ledgers hold single-hash keys and every one of them answers
    None here, which is what makes an upgraded chat read as first sight
    rather than as a changed anything -- fail toward re-describing, never
    toward claiming something moved."""
    parts = str(dedupe_key or "").split(":")
    if len(parts) != 3 or not all(parts):
        return None
    return f"{parts[0]}:{parts[1]}"


def _spliced_fragment(text):
    """Authored text made fit to follow a verb, without deciding its shape.

    `_noun_phrase` is for a NOUN phrase and supplies an article where none
    stands, which is right for "sand shelf" and wrong for an adjectival
    demeanor ("calm, attentive" became "the calm, attentive"). This does
    the two subtractions that hold for any spliced fragment and nothing
    more: the terminal stop goes, and a leading article written in sentence
    case is lowercased, so "A wet, nervous young man on a bench." follows
    "seems" as "a wet, nervous young man on a bench".
    """
    text = " ".join(str(text or "").split())
    while text and text[-1] in ".!?":
        text = text[:-1].rstrip()
    if not text:
        return ""
    first, _, rest = text.partition(" ")
    if first.casefold() in _pack_words("pose_bare_determiners") \
            and first[:1].isupper():
        text = first.casefold() + (" " + rest if rest else "")
    return text


def _bare_words(text):
    """`text` folded for comparing two names of one thing: its leading
    article off, its case and spacing ignored."""
    words = str(text or "").split()
    articles = {str(a).casefold() for a in _compositor("articles")}
    if words and words[0].casefold() in articles:
        words = words[1:]
    return " ".join(words).casefold()


def _noun_phrase(text):
    """One authored description, made fit to SPLICE into a sentence.

    THE CLASS. Anchor descriptions, edge names and light-source labels are
    authored free text and arrive in three shapes at once: a bare noun
    ("cistern intake passage"), a phrase carrying its own determiner ("the
    middle shelf"), and a full capitalised SENTENCE ("Salt-rimed limestone
    kerbstones dividing the crystallisation pans."). The composer splices all
    three into the middle of ITS OWN sentences -- a feature list, a way out,
    where the light falls -- and only the second survives that intact.

    Measured, run 2026-09-05C `solitude` (PS9). Turn 4: "You can see
    Salt-rimed limestone kerbstones dividing the rectangular crystallisation
    pans. within arm's reach, The open stone lip of the middle shelf ...
    across the room." Turn 5: "...thins to half-light at The low
    cut-limestone arch ... and The massive limestone revetment wall at the
    far northeast end of the dry basin.." -- two full stops. Turn 20: "There
    is broad salt-crusted stone steps."

    Three subtractions, each decidable from the pack's own tables and none of
    them guessing at English:

      * a TERMINAL STOP goes. A phrase inside a list is not a sentence, and
        the stop that belongs is the one the enclosing template supplies.
      * a LEADING ARTICLE is lowercased. The pack names its own articles, so
        a capital on one of them is sentence case and can never be a name.
        Nothing else is lowered: "Salt-rimed" may be a proper name and this
        layer has no way to know, so it keeps its capital and its meaning.
      * a phrase carrying NO determiner takes the pack's, exactly as
        `_pose_referent` gives one to a bare noun. This is F52's unfixed last
        line ("from hand torch"), and it was live in three sentence families
        at once.

    English wording, like the rest of the reference renderer: a pack with no
    articles and no determiners (`ja`) leaves every branch a no-op.
    """
    text = _strip_sentence_ends(" ".join(str(text or "").split()))
    if not text:
        return ""
    words = text.split()
    first = words[0].casefold().strip(",.;:")
    if first in _pack_words("articles"):
        words[0] = words[0][:1].lower() + words[0][1:]
        return " ".join(words)
    # A support is authored free-text and often arrives with its own
    # preposition already on it ("on the sill"); `_render_pose` detects that
    # and declines to add a second one. Prefixing a determiner here would
    # slip underneath that check and produce "on the on the sill".
    if (words[0][:1].isupper()
            or first in _pack_words("pose_bare_determiners")
            or first in _pack_words("pose_prepositions")):
        return " ".join(words)
    return _t("pose_entity", name=" ".join(words))


def _cap(sentence):
    sentence = str(sentence or "").strip()
    return sentence[:1].upper() + sentence[1:] if sentence else sentence


def _join_clauses(clauses):
    if len(clauses) == 1:
        return clauses[0]
    if len(clauses) == 2:
        return str(_ENGLISH_COMPOSITOR["join"]["two"]).format(
            first=clauses[0], last=clauses[1])
    return ", ".join(clauses[:-1]) + str(
        _ENGLISH_COMPOSITOR["join"]["many"]).format(last=clauses[-1])


def _safe_renderer(language):
    """The pack's adapter, or None to use the in-module English renderer.

    `renderer_for` raises when a pack names an adapter that is not available;
    that is a configuration fault, and it was reaching callers as a dead turn.

    `language=None` follows the story's contextvar. The default used to be the
    literal "en", so any caller that omitted the argument rendered English
    inside a Japanese turn and said nothing about it -- the same silent
    fallback this whole layer exists to avoid.
    """
    try:
        return renderer_for(
            current_language_id.get() if language is None else language)
    except LanguagePackError:
        logger.exception("no renderer for language %r; using English", language)
        return None
