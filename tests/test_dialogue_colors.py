"""Deriving a speaker's colour from their card.

The three properties that make automatic assignment safe rather than a
lottery, each pinned here: the colour is STABLE (same card, same colour, on
every render and across restarts), it is LEGIBLE (hue is free, lightness and
chroma are not, because the prose panel is ~60% transparent over a generated
image), and it is DISTINCT WITHIN A CAST (two people in a room must not land
on neighbouring hues -- which no per-character derivation can know, so the
cast resolves as a set).

An explicit override outranks all of it, including collision spreading.
"""

import colorsys
import json

import pytest

from story.dialogue_colors import (
    AUTO_LIGHTNESS,
    MIN_HUE_SEPARATION,
    auto_dialogue_color,
    normalize_color,
    personality_digest,
    resolve_cast_colors,
)


def _sheet(traits=(), values=()):
    return {"psychology": {
        "traits": [{"name": n, "strength": s} for n, s in traits],
        "values": [{"name": n, "priority": p} for n, p in values],
    }}


def _hls(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


# ---- Stability ----

def test_the_same_card_always_gets_the_same_colour():
    """blake2b rather than the builtin hash(), which is salted per process --
    with hash() every character would change colour on every server restart."""
    sheet = _sheet(traits=[("patience", 0.9)], values=[("territory", 0.75)])
    first = auto_dialogue_color("uid-1", sheet)
    assert first
    assert auto_dialogue_color("uid-1", sheet) == first


def test_key_order_and_insignificant_precision_do_not_move_the_hue():
    """Sheets round-trip through JSON, archives and branch clones. If either
    of these moved the colour, a character would change hue on export/import
    with nothing about them having changed."""
    a = _sheet(traits=[("calm", 0.80), ("wary", 0.60)])
    b = _sheet(traits=[("wary", 0.6001), ("calm", 0.8004)])
    assert personality_digest(a) == personality_digest(b)
    assert auto_dialogue_color("uid", a) == auto_dialogue_color("uid", b)


def test_a_rename_does_not_repaint_someone():
    """The digest is psychology only. A name or uid in it would mean renaming
    a character silently recolours their whole backlog."""
    sheet = _sheet(traits=[("patience", 0.9)])
    assert auto_dialogue_color("old-uid", sheet) == \
        auto_dialogue_color("new-uid", sheet)


def test_a_sheet_string_is_read_the_same_as_a_dict():
    """chat_chars.sheet and characters.sheet are both stored as JSON text."""
    sheet = _sheet(traits=[("patience", 0.9)])
    assert auto_dialogue_color("uid", json.dumps(sheet)) == \
        auto_dialogue_color("uid", sheet)


# ---- Legibility ----

@pytest.mark.parametrize("seed", [f"uid-{i}" for i in range(24)])
def test_every_derived_colour_lands_in_the_legible_band(seed):
    """Hue is free; lightness is not, and it is clamped to the LIGHT side.

    The glyph outline rescues a light colour from a bright patch of the render
    showing through the panel. Nothing rescues a dark one -- a dark colour
    against a dark outline is worse than no outline at all -- so this is the
    clamp the outline cannot substitute for."""
    _hue, lightness, _sat = _hls(auto_dialogue_color(seed))
    assert abs(lightness - AUTO_LIGHTNESS) < 0.02
    assert lightness > 0.6, "a dark speaker colour cannot be outlined legible"


@pytest.mark.parametrize("seed", [f"uid-{i}" for i in range(12)])
def test_derived_colours_are_saturated_on_purpose(seed):
    """The other half of the same decision. Saturation is NOT held back for a
    busy background -- the outline and the panel blur already handle that --
    because chroma is what makes two speakers distinguishable at a given hue
    separation, and that is the constraint that actually bites."""
    _hue, _light, saturation = _hls(auto_dialogue_color(seed))
    assert saturation >= 0.7


def test_derived_hues_spread_across_the_circle():
    """A hash that clustered would defeat the whole point -- the cast spread
    below can only push colours apart, never invent range that is not there."""
    hues = {round(_hls(auto_dialogue_color(f"uid-{i}"))[0] * 360 / 30)
            for i in range(40)}
    assert len(hues) >= 8


# ---- Distinctness within a cast ----

def test_two_speakers_are_pushed_apart():
    cast = [{"uid": "a", "sheet": _sheet(traits=[("calm", 0.8)])},
            {"uid": "b", "sheet": _sheet(traits=[("calm", 0.8)])}]
    colors = resolve_cast_colors(cast)
    assert colors["a"] != colors["b"]
    gap = abs(_hls(colors["a"])[0] - _hls(colors["b"])[0]) * 360
    assert min(gap, 360 - gap) >= MIN_HUE_SEPARATION - 0.5


def test_a_whole_cast_stays_mutually_separated():
    cast = [{"uid": f"u{i}", "sheet": _sheet(traits=[("t", 0.5)])}
            for i in range(6)]
    hues = [_hls(c)[0] * 360 for c in resolve_cast_colors(cast).values()]
    for i, one in enumerate(hues):
        for other in hues[i + 1:]:
            gap = abs(one - other) % 360
            assert min(gap, 360 - gap) >= MIN_HUE_SEPARATION - 0.5


def test_the_result_is_the_same_every_time_for_the_same_cast():
    """Spreading walks in cast order, which is what keeps it deterministic --
    the same story must resolve to the same colours on every render."""
    cast = [{"uid": f"u{i}", "sheet": _sheet(traits=[("t", 0.5)])}
            for i in range(5)]
    assert resolve_cast_colors(cast) == resolve_cast_colors(list(cast))


def test_a_display_rename_does_not_repaint_a_seeded_institutional_body():
    before = resolve_cast_colors([
        {"uid": "Captain Ysra Vale", "seed": "charter:watch:ysra"}])
    after = resolve_cast_colors([
        {"uid": "Commander Ysra Vale", "seed": "charter:watch:ysra"}])
    assert before["Captain Ysra Vale"] == after["Commander Ysra Vale"]


# ---- Overrides ----

def test_an_explicit_colour_is_honoured_exactly():
    colors = resolve_cast_colors([{"uid": "a", "color": "#ff8800"}])
    assert colors["a"] == "#ff8800"


def test_an_override_is_never_moved_by_collision_spreading():
    """A host who picked a colour outranks every rule in the module. The
    alternative is the app quietly overruling a deliberate choice."""
    cast = [{"uid": "a", "color": "#ff8800"},
            {"uid": "b", "color": "#ff8801"}]
    colors = resolve_cast_colors(cast)
    assert colors == {"a": "#ff8800", "b": "#ff8801"}


def test_a_derived_hue_is_pushed_away_from_a_chosen_one():
    """Overrides are placed first for exactly this reason."""
    chosen_hue = _hls("#ff8800")[0] * 360
    cast = [{"uid": "a", "color": "#ff8800"},
            {"uid": "b", "sheet": _sheet(traits=[("t", 0.5)])}]
    derived = _hls(resolve_cast_colors(cast)["b"])[0] * 360
    gap = abs(derived - chosen_hue) % 360
    assert min(gap, 360 - gap) >= MIN_HUE_SEPARATION - 0.5


def test_an_unreadable_override_falls_through_to_the_derived_hue():
    """Fails to the derivation, not to a default colour: a typo should not
    paint someone in a colour nobody chose."""
    assert normalize_color("not a colour") == ""
    assert normalize_color("#12") == ""
    cast = [{"uid": "a", "color": "rgb(1,2,3)",
             "sheet": _sheet(traits=[("t", 0.5)])}]
    assert resolve_cast_colors(cast)["a"] == auto_dialogue_color(
        "a", _sheet(traits=[("t", 0.5)]))


def test_short_hex_is_expanded():
    assert normalize_color("#F80") == "#ff8800"


# ---- Cards with nothing authored ----

def test_a_card_with_no_psychology_still_gets_a_colour():
    """The uid is the fallback seed and ONLY the fallback -- an empty drive
    and empty traits are the documented silent-failure shape in this repo, so
    a blank card must not collapse every such character onto one hue."""
    assert personality_digest({}) == ""
    a = auto_dialogue_color("uid-a", {})
    b = auto_dialogue_color("uid-b", {})
    assert a and b and a != b


def test_a_member_with_no_uid_is_skipped_rather_than_keyed_on_empty():
    colors = resolve_cast_colors([{"uid": "", "color": "#ff8800"},
                                  {"uid": "real"}])
    assert "" not in colors
    assert "real" in colors
