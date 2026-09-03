"""What a Charter body LOOKS like, dealt from its population's own look law.

WHY THIS EXISTS. The generator wrote posts, names, needs, minds and a month
of history for every townsperson, and nothing physical. The stranger label
every seam renders an unrecognised body by (`agents.common.
_unknown_actor_label`) is cut from the body's appearance text minus its own
name, and a Charter body had no appearance text -- so every unrecognised
townsperson collapsed to the fallback, and dim light then had nothing to
grade. Measured, Harrowmere replay 2026-09-03: "an indistinct figure" eleven
times and "the unfamiliar person" six times across forty turns, for a town of
a hundred people the player walked among.

THE PATTERN IS THE NAMING LAW'S. The planner already writes syllable pools
per population and the generator deals names from them by seed
(`charter_identity`). A look law is the same thing for bodies: pools per
AXIS in the population's own words (`looks` on the charter), and one value
per axis dealt per body from the identity seed, so a replay is byte-identical
and a valley town looks like one people. No prose is written per resident and
no model call is made per body: a hundred descriptions from a model converge
on the same six, and a dealt one does not.

THE SURFACE IS TIERED BY WHAT LIGHT SHOWS. A silhouette gives stature, build,
gait and the outline of what is worn; a face gives complexion, hair, age and
marks. `surface_label` takes the sight level the composer already grades and
composes only from the tier that level admits, so dim light yields "the tall
broad-shouldered figure in an apron" rather than nothing, and full light the
face tier. This is deliberately different from an appearance SUMMARY, which is
unsorted prose and yields nothing at `shapes` (the composer's rule); a
structured surface knows which of its facts a silhouette carries.

THE DESCRIPTOR IS BUILT FROM THE SURFACE ALONE. The body's name never enters
it and neither does its post's KEY: the trade shows through what the post's
holders visibly wear and what their work marks them with (`worn`/`marks`,
authored per post, attached through `home_post`). The one word from outside
the surface is the NOUN a caller hands in -- the institution's public noun
for what the body is, the same `charter_crowd.member_noun` the crowd
already renders to any observer ("deckhands"), so the one deckhand standing
out of the band reads as a deckhand and not as a person of no trade. That
is the crowd's existing rule (a rank or duty is worn), not a new licence:
nothing here reads the watch bill, and a surface dict smuggling a `post` or
`role` key is read on its axes and nothing else.
"""
from __future__ import annotations

import hashlib
import re

from language_runtime import compositor_text, compositor_value, linguistic

#: The scalar axes a look law deals one value of per body, in lane order.
#: Closed: the schema is the engine's; the VALUES are the population's.
AXES = ("stature", "build", "gait", "complexion", "hair", "age")
#: What a silhouette shows (plus the outline of what is worn).
SILHOUETTE_AXES = ("stature", "build", "gait")
#: What a face shows (plus marks).
FACE_AXES = ("complexion", "hair", "age")
#: Values kept per axis from an authored law. A law longer than this is
#: material nobody will ever see dealt.
POOL_CAP = 24
#: Characters kept per value; a value is a phrase a glance takes in.
VALUE_CHARS = 48
#: Marks and worn items kept per post, and law marks dealt per body.
DRESS_CAP = 3
#: One body in this many carries a distinguishing mark from the law's pool
#: (a post's own marks are additional and land on every holder).
MARK_ODDS = 3
#: Characters kept of a Director's settled render.
RENDER_CHARS = 400

_LAW_AUTHORED = "authored"
_LAW_DEFAULT = "default"


def _strings(value, cap):
    if isinstance(value, str):
        value = [value]
    out = []
    for item in value or ():
        text = " ".join(str(item or "").split())[:VALUE_CHARS].strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= cap:
            break
    return out


def normalize_looks_profile(value):
    """The bounded look law Charter understands: ``{axis: [phrase, ...]}``
    over `AXES` plus ``marks``. Empty pools stay empty; `looks_profile`
    decides whether the default steps in."""
    value = value if isinstance(value, dict) else {}
    out = {axis: _strings(value.get(axis), POOL_CAP) for axis in AXES}
    out["marks"] = _strings(value.get("marks"), POOL_CAP)
    return out


def looks_material_exists(profile):
    return any((profile or {}).get(axis) for axis in AXES + ("marks",))


def default_looks():
    """The engine's own minimal pool -- one closed schema, read from the
    language pack so a story in another language deals in its words."""
    return normalize_looks_profile(
        linguistic("world.charter_surface", "DEFAULT_LOOKS"))


def looks_profile(charter):
    """``(profile, source)`` for a charter: its authored law where one
    exists, else the engine default. ``source`` is recorded on every
    surface dealt so an audit can tell a town with a law from one without."""
    authored = normalize_looks_profile((charter or {}).get("looks"))
    if looks_material_exists(authored):
        return authored, _LAW_AUTHORED
    return default_looks(), _LAW_DEFAULT


def post_dress(post):
    """What a post's holders visibly wear and what the work marks them with:
    ``{"worn": [...], "marks": [...]}``, authored on the post by the planner
    in the population's words. Nothing is invented for a post that carries
    none -- an apron at a forge is a fact about one setting, not a table
    the engine owns."""
    post = post if isinstance(post, dict) else {}
    return {"worn": _strings(post.get("worn"), DRESS_CAP),
            "marks": _strings(post.get("marks"), DRESS_CAP)}


def _lane(charter_key, body_key, lane):
    raw = hashlib.blake2b(
        f"surface:{charter_key}:{body_key}|{lane}".encode("utf-8"),
        digest_size=8).digest()
    return int.from_bytes(raw, "big")


def deal_surface(charter_key, body_key, looks, post=None, *, source=None):
    """One value per axis for one body, from the seed and nothing else.

    Deterministic by construction: the same charter and body keys deal the
    same surface on every replay, which is what lets the surface be derived
    on read for a registry generated before the field existed and stored
    only where generation or a settled render wrote it.
    """
    looks = normalize_looks_profile(looks)
    out = {}
    for index, axis in enumerate(AXES):
        pool = looks.get(axis) or []
        out[axis] = pool[_lane(charter_key, body_key, index) % len(pool)] \
            if pool else ""
    marks = []
    pool = looks.get("marks") or []
    if pool and _lane(charter_key, body_key, len(AXES)) % MARK_ODDS == 0:
        marks.append(pool[_lane(charter_key, body_key, len(AXES) + 1)
                          % len(pool)])
    dress = post_dress(post)
    for mark in dress["marks"]:
        if mark not in marks:
            marks.append(mark)
    out["marks"] = marks[:DRESS_CAP]
    out["worn"] = list(dress["worn"])
    out["law"] = str(source or (_LAW_AUTHORED if looks_material_exists(looks)
                                else _LAW_DEFAULT))
    return out


def surface_has_content(surface):
    if not isinstance(surface, dict):
        return False
    return any(surface.get(axis) for axis in AXES) \
        or bool(surface.get("marks")) or bool(surface.get("worn"))


def _home_post(charter, body):
    posts = (charter or {}).get("posts") or {}
    held = str((body or {}).get("home_post") or "")
    if held in posts:
        return posts[held]
    for post_key, holder in ((charter or {}).get("watch") or {}).items():
        if str(holder) == str((body or {}).get("key") or "") \
                and str(post_key) in posts:
            return posts[str(post_key)]
    return None


def surface_of(charter, body_key, body=None):
    """This body's surface: the stored one where generation or a settled
    render wrote it, else dealt now from the charter's law -- pure, so a
    registry from before the field existed reads the same as one after."""
    charter = charter if isinstance(charter, dict) else {}
    if body is None:
        body = (charter.get("bodies") or {}).get(str(body_key)) or {}
    stored = body.get("surface")
    if surface_has_content(stored):
        return dict(stored)
    looks, source = looks_profile(charter)
    return deal_surface(str(charter.get("key") or ""), str(body_key), looks,
                        post=_home_post(charter, body), source=source)


def _join_adjectives(parts):
    parts = [str(p).strip() for p in parts if str(p or "").strip()]
    return str(compositor_value("surface_adjective_join")).join(parts)


def _clean(text):
    return " ".join(str(text or "").split()).strip(" ,.;:").casefold()


def surface_label(surface, sight="full", noun=None):
    """The referring phrase (no article) an observer at ``sight`` may use
    for a stranger with this surface, or "" when the tier has nothing.

    ``full`` composes from the face tier: age and build, then the one most
    distinguishing feature a glance keeps -- a mark, else what is worn, else
    the hair. Anything short of full but still a visual channel composes
    from the silhouette tier only: stature and build, then the outline of
    what is worn. ``none`` is nothing: no channel, no phrase. ``noun`` is
    the public noun the caller may use for what the body is (the crowd's
    `member_noun`), at full sight only; a silhouette is a figure.
    """
    if not surface_has_content(surface) or sight == "none":
        return ""
    if sight == "full":
        adjectives = _join_adjectives(
            [surface.get("age"), surface.get("build")])
        noun = " ".join(str(noun or "").split()) \
            or str(compositor_value("surface_person"))
        label = compositor_text("surface_label", adjectives=adjectives,
                                noun=noun).strip()
        feature = next((m for m in (surface.get("marks") or ()) if m), "") \
            or next((w for w in (surface.get("worn") or ()) if w), "") \
            or str(surface.get("hair") or "")
        if feature:
            label = compositor_text("surface_with", label=label,
                                    feature=feature)
        return _clean(label)
    adjectives = _join_adjectives(
        [surface.get("stature"), surface.get("build")])
    worn = next((w for w in (surface.get("worn") or ()) if w), "")
    if not adjectives and not worn:
        return ""
    noun = str(compositor_value("surface_figure"))
    label = compositor_text("surface_label", adjectives=adjectives,
                            noun=noun).strip()
    if worn:
        label = compositor_text("surface_in", label=label, worn=worn)
    return _clean(label)


def surface_words(surface, sight="full"):
    """Every content word the tier admits, in the order a label widens
    through them when two strangers collide on the short form."""
    if not surface_has_content(surface) or sight == "none":
        return []
    if sight == "full":
        parts = [surface.get("age"), surface.get("build"),
                 surface.get("complexion"), surface.get("stature")]
        parts.extend(surface.get("marks") or ())
        parts.extend(surface.get("worn") or ())
        parts.extend([surface.get("hair"), surface.get("gait")])
    else:
        parts = [surface.get("stature"), surface.get("build")]
        parts.extend(surface.get("worn") or ())
        parts.append(surface.get("gait"))
    articles = {str(a).casefold() for a in compositor_value("articles")}
    words = []
    for part in parts:
        for word in str(part or "").split():
            if word.casefold() in articles:
                continue
            words.append(word)
    return words


def appearance_text(surface, noun=None):
    """The full-sight summary of a surface as one clause without its
    article -- what `appearance` carries for a body whose look was dealt,
    read by every seam that describes a stranger on first mention.
    ``noun`` as for `surface_label`."""
    if not surface_has_content(surface):
        return ""
    adjectives = _join_adjectives(
        [surface.get("age"), surface.get("stature"), surface.get("build"),
         surface.get("complexion"), surface.get("gait")])
    noun = " ".join(str(noun or "").split()) \
        or str(compositor_value("surface_person"))
    text = compositor_text("surface_label", adjectives=adjectives,
                           noun=noun).strip()
    join = str(compositor_value("surface_list_join"))
    features = [p for p in (surface.get("hair"),) if p]
    features.extend(m for m in (surface.get("marks") or ()) if m)
    if features:
        text = compositor_text("surface_summary_with", text=text,
                               items=join.join(features))
    worn = [w for w in (surface.get("worn") or ()) if w]
    if worn:
        text = compositor_text("surface_summary_wearing", text=text,
                               items=join.join(worn))
    return " ".join(text.split()).strip(" ,")


def _phrase_in(phrase, text):
    phrase = " ".join(str(phrase or "").split()).casefold()
    if not phrase:
        return False
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
                     str(text or "").casefold()) is not None


def settle_render(charter, body_key, render, body=None):
    """The Director's high-fidelity render of a body, settled onto its
    surface ONCE so the same townsperson looks the same next visit.

    Returns ``(surface, refused_axis)``. A render may ADD to a dealt
    surface and never contradict it: if it names another value of an
    axis's own pool than the one dealt -- "short" of a body dealt "tall" --
    the axis is returned and nothing is written, because the pool is the
    population's closed vocabulary for that axis and a second value of it
    is a second body. A surface already carrying a render keeps it.
    """
    charter = charter if isinstance(charter, dict) else {}
    if body is None:
        body = (charter.get("bodies") or {}).get(str(body_key)) or {}
    surface = surface_of(charter, body_key, body)
    render = " ".join(str(render or "").split())[:RENDER_CHARS]
    if not render:
        return surface, ""
    if surface.get("rendered"):
        return surface, ""
    looks, _source = looks_profile(charter)
    for axis in AXES:
        dealt = str(surface.get(axis) or "")
        for value in looks.get(axis) or ():
            if value == dealt or not value:
                continue
            if _phrase_in(value, render) and not (
                    dealt and _phrase_in(dealt, value)):
                return surface, axis
    settled = dict(surface)
    settled["rendered"] = render
    return settled, ""
