# dialogue_colors.py
"""A colour per speaking character, derived from the card and overridable.

Three rules hold this together, and each one is a decision rather than an
implementation detail:

**The colour is never stored on a turn.** What gets persisted is the SPEAKER,
and speakers are already persisted -- `events.content.dialogue_log` carries
`{speaker, exact_quote}` for every line of every beat, and DIALOGUE FIDELITY
requires each of those lines to appear in the narrator's prose verbatim. So a
turn's colouring is a render-time lookup of an identity that was recorded when
the beat happened. Change a colour and three hundred turns of backlog change
with it; edit a turn's prose and nothing desyncs, because there were no
offsets to invalidate. A line whose quote no longer matches simply goes
uncoloured, which is the only safe failure: never colour by guess.

**Hue is chosen freely, lightness and chroma are not.** The prose panel is
~60% transparent over a generated image (see `--bd-panel`), so a colour that
picks its own lightness is a colour that vanishes over a bright render. Every
derived colour lands in one legible band and only its hue moves. That is what
makes automatic assignment safe rather than a lottery.

**Distinctness is a property of the CAST, not of a character.** Two people
in a room with neighbouring hues is the failure the reader actually notices,
and no per-character derivation can see the room. So the hue comes out of the
card, and `resolve_cast_colors` spreads collisions afterwards.

The digest is built from psychology -- trait names and their strengths, value
names and their priorities -- so a character's colour follows the personality
that was authored for them. NOTE THE CONSEQUENCE: rewriting those fields moves
the hue, and it moves it for the whole backlog. That is deliberate (a
different personality reads as a different voice) and it is exactly what an
explicit override is for when a host wants a colour pinned across an edit.
"""

from __future__ import annotations

import colorsys
import hashlib
import json
import re

#: Lightness and saturation the derived colours are held at, for the dark
#: surfaces every shipped theme uses seen through the translucent prose panel.
#:
#: THE TWO ARE CLAMPED FOR DIFFERENT REASONS, and only one of them is about
#: the backdrop. The glyph outline (`--prose-outline`, four cardinal offsets
#: in `body.has-backdrop .prose`) and the panel blur already carry contrast
#: against a bright patch of the render showing through 42% alpha -- that is
#: what they are for. So SATURATION does not need holding back for a busy
#: background, and is set high on purpose: more chroma means two speakers are
#: easier to tell apart at the same hue separation, and telling speakers apart
#: is the constraint that actually bites.
#:
#: LIGHTNESS stays clamped, and stays on the light side, because the outline
#: cannot help there. A dark outline rescues a light colour from a light
#: background; a colour that is itself dark is dark-on-black and the outline
#: makes it worse, not better.
AUTO_LIGHTNESS = 0.72
AUTO_SATURATION = 0.80

#: Two speakers closer than this on the hue circle read as the same colour in
#: running prose, where the two names are never side by side for comparison.
MIN_HUE_SEPARATION = 28.0

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_color(value):
    """A `#rrggbb` string, or "" for anything this cannot read.

    Fails to "" rather than to a default colour: an unreadable override should
    fall through to the derived hue, not silently paint a character in a
    colour nobody chose.
    """
    text = str(value or "").strip()
    if not _HEX_RE.match(text):
        return ""
    if len(text) == 4:  # #abc -> #aabbcc
        text = "#" + "".join(ch * 2 for ch in text[1:])
    return text.lower()


def personality_digest(sheet):
    """The authored personality, reduced to a stable string.

    Traits and values only. Deliberately NOT the name or the uid: two
    characters who happen to share a name should not share a colour, and a
    rename should not repaint someone's dialogue. Strengths and priorities are
    rounded to one decimal so an insignificant numeric tweak does not move the
    hue, and the parts are sorted so key order in the JSON cannot.
    """
    if isinstance(sheet, str):
        try:
            sheet = json.loads(sheet or "{}")
        except (TypeError, ValueError):
            sheet = {}
    if not isinstance(sheet, dict):
        return ""

    psychology = sheet.get("psychology")
    if not isinstance(psychology, dict):
        psychology = {}

    parts = []
    for field, weight_key in (("traits", "strength"), ("values", "priority")):
        entries = psychology.get(field)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                name = str(entry.get("name") or "").strip().casefold()
                weight = entry.get(weight_key)
            else:
                name = str(entry or "").strip().casefold()
                weight = None
            if not name:
                continue
            try:
                rounded = round(float(weight), 1)
            except (TypeError, ValueError):
                rounded = 0.0
            parts.append(f"{field}:{name}:{rounded}")

    drive = psychology.get("drive")
    if isinstance(drive, dict):
        essence = str(drive.get("essence") or "").strip().casefold()
        if essence:
            parts.append(f"drive:{essence}")

    return "|".join(sorted(parts))


def _hue_from(seed):
    """A hue in [0, 360) from a string, spread evenly across the circle.

    blake2b rather than `hash()`: the builtin is salted per process, so the
    same character would change colour every time the server restarted.
    """
    if not seed:
        return None
    digest = hashlib.blake2b(seed.encode("utf-8"), digest_size=8).digest()
    return (int.from_bytes(digest, "big") % 3600) / 10.0


def _hex_from_hsl(hue, saturation=AUTO_SATURATION, lightness=AUTO_LIGHTNESS):
    r, g, b = colorsys.hls_to_rgb((hue % 360.0) / 360.0, lightness, saturation)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def auto_dialogue_color(uid, sheet=None):
    """The colour a character gets when nobody has chosen one.

    The digest drives the hue; the uid is the fallback for a card with no
    authored psychology at all, and only the fallback -- otherwise two
    identically-authored characters would be told apart by an id the reader
    cannot see, and the colour would stop meaning anything about the person.
    """
    seed = personality_digest(sheet) or str(uid or "")
    hue = _hue_from(seed)
    if hue is None:
        return ""
    return _hex_from_hsl(hue)


def _hue_of(hex_color):
    text = normalize_color(hex_color)
    if not text:
        return None
    r, g, b = (int(text[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, _light, sat = colorsys.rgb_to_hls(r, g, b)
    if sat <= 0.02:  # a grey has no meaningful hue to keep away from
        return None
    return hue * 360.0


def resolve_cast_colors(cast):
    """{uid: "#rrggbb"} for one story's speaking cast.

    `cast` is an ordered sequence of `{uid, sheet, color}`. An explicit
    `color` is honoured exactly and never moved -- a host who picked a colour
    outranks every rule here, including collision spreading, because the
    alternative is the app quietly overruling a choice someone made on purpose.

    Derived hues are then pushed apart in cast order until each clears
    MIN_HUE_SEPARATION from everything already placed. Order is what makes
    this deterministic: the same cast resolves to the same colours on every
    render, on every reload, and after a restart.
    """
    resolved = {}
    taken = []

    entries = []
    for member in cast or []:
        if not isinstance(member, dict):
            continue
        uid = str(member.get("uid") or "").strip()
        if not uid:
            continue
        entries.append((uid, member))

    # Overrides first, so a derived hue is pushed away from a chosen one
    # rather than the other way round.
    for uid, member in entries:
        chosen = normalize_color(member.get("color"))
        if chosen:
            resolved[uid] = chosen
            hue = _hue_of(chosen)
            if hue is not None:
                taken.append(hue)

    for uid, member in entries:
        if uid in resolved:
            continue
        hue = _hue_from(personality_digest(member.get("sheet")) or uid)
        if hue is None:
            continue
        hue = _spread(hue, taken)
        taken.append(hue)
        resolved[uid] = _hex_from_hsl(hue)

    return resolved


def _spread(hue, taken):
    """Nudge `hue` until it clears every hue already placed.

    Walks in fixed increments rather than solving for a gap: with a large cast
    the circle genuinely fills up, and a solver would either fail or return
    something arbitrary. The walk always terminates, and once the circle is
    full it lands wherever it is -- crowded is better than absent, and past
    roughly a dozen simultaneous speakers no palette is legible anyway.
    """
    if not taken:
        return hue % 360.0
    step = MIN_HUE_SEPARATION / 2.0
    candidate = hue % 360.0
    for _ in range(int(360 / step)):
        if all(_hue_gap(candidate, other) >= MIN_HUE_SEPARATION
               for other in taken):
            return candidate
        candidate = (candidate + step) % 360.0
    return hue % 360.0


def _hue_gap(a, b):
    delta = abs(a - b) % 360.0
    return min(delta, 360.0 - delta)
