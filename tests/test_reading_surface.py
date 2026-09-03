"""The reading surface: how wide the story column gets, and what the prose
sits on once there is a picture behind it.

Two things here are easy to undo by accident and expensive to notice.

The column now GROWS into the space the sidebar, the pipeline drawer, the
vitals tracker and the ambience cluster are not using. The first two are in
flow and shrink #main by themselves; the last two FLOAT over it, so the width
has to reserve room for them explicitly or prose slides underneath a panel.

And the prose panel went from near-opaque (.86-.92) to roughly 60%
transparent. At that alpha the blur and the glyph outline are what keep the
words legible -- they are load-bearing, not decoration, and the old comment in
styles.css arguing the blur bought nothing was written when the panel was
opaque enough to make it true.
"""

from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def _styles():
    return (STATIC / "styles.css").read_text(encoding="utf-8")


def _settings():
    return (STATIC / "js" / "settings.js").read_text(encoding="utf-8")


def test_the_column_reserves_room_for_both_floats():
    """The tracker sits left, the ambience cluster right, and the column is
    centred -- so the larger of the two has to claim BOTH margins."""
    js = _settings()
    assert "--story-width" in js
    assert "STORY_MIN_WIDTH" in js and "STORY_MAX_WIDTH" in js
    # The tracker's own minimum gutter is what the reserve is built from, so
    # the two cannot drift into disagreeing about how much room it needs.
    assert "VITALS_MIN_GUTTER + 12" in js
    # The ambience cluster is MEASURED, not assumed: it is a variable number of
    # icon buttons and it grows while a track is playing.
    assert "#ambience-bar" in js


def test_the_reserve_keys_on_hidden_not_fits():
    """The feedback loop this avoids: `fits` is an OUTPUT of the width chosen
    here (the tracker hides when the gutter it was left is too small). Keying
    the reserve on it would let the column widen, evict the tracker, see the
    reserve drop, and widen again."""
    js = _settings()
    block = js[js.index("function syncVitalsGutterNow"):]
    block = block[:block.index("\n}\n")]
    reserve = block[block.index("const reserve"):block.index("--story-width")]
    assert "hidden" in reserve or "trackerPresent" in reserve
    assert "fits" not in reserve


def test_the_text_fills_the_panel_inset_by_a_fixed_ten_pixels():
    """OWNER'S CALL, and the opposite of where this started. Two versions held
    the words at a 68ch reading measure and gave the panel margins the way a
    book page does -- percentage padding first, then a grid track. Both were
    reported as the text still filling the box, and the decision was then made
    explicitly: a fixed inset, no measure.

    The consequence, so it is not rediscovered as a bug: the panel width IS
    the line length now, so STORY_MAX_WIDTH in settings.js is what controls
    how long a line gets."""
    styles = _styles()
    assert ".turn{max-width:var(--story-width,720px);" in styles
    # Line-anchored: a bare `.prose{` search also matches inside
    # `body.has-backdrop .prose{`, which is the rule this one must differ from.
    base = styles[styles.index("\n.prose{") + 1:]
    base = base[:base.index("}")]
    assert "padding:15px 10px 17px" in base
    # No measure of any kind: neither of the two forms that were tried.
    assert "grid-template-columns" not in base
    assert "68ch" not in base
    # ...and the old 65ch cap is gone, or the text would not fill the panel.
    assert "max-width:none" in base


def test_a_backdrop_appearing_does_not_reflow_the_story():
    """Reported live as "UI gore": the base rule carried `max-width:65ch` and
    `padding:8px 2px` while the has-backdrop rule overrode both, so turning a
    backdrop on or off rewrapped every line and left narrow text stranded in a
    wide column.

    The fix is that GEOMETRY LIVES IN ONE PLACE. The panel rule may add a
    surface, a border, a blur and a shadow; the moment it carries a width or a
    padding the two states can disagree again."""
    styles = _styles()
    panel = styles[styles.index("body.has-backdrop .prose,\n"
                                "body.has-backdrop #room.floating{"):]
    panel = panel[:panel.index("}")]
    for sizing in ("padding", "max-width", "width", "margin",
                   "grid-template-columns"):
        assert sizing not in panel, (
            f"{sizing!r} in the backdrop-only rule can reflow the story when a "
            "picture appears; put it on the base .prose rule instead")


def test_the_player_echo_shares_the_prose_inset():
    """The player's line has to start and end on the same pixels as the
    narration above it. One decision, two rules."""
    styles = _styles()
    pin = styles[styles.index(".pin{"):]
    pin = pin[:pin.index("}")]
    assert "padding:8px 10px" in pin


def test_the_blur_and_the_outline_are_present_and_gated():
    """Both carry the readability the opacity used to. The blur is also the
    expensive one -- a backdrop-filter re-blurs its backdrop every frame
    anything behind it changes -- so it drops under weather, the same
    unconditional gate the vitals plates get."""
    styles = _styles()
    panel = styles[styles.index("body.has-backdrop .prose,\n"
                                "body.has-backdrop #room.floating{"):]
    panel = panel[:panel.index("}")]
    assert "backdrop-filter:blur(3px)" in panel
    assert "-webkit-backdrop-filter:blur(3px)" in panel
    # Four cardinal offsets, not one drop shadow: a single offset leaves the
    # glyph unprotected from three directions, and a light edge in the picture
    # above a letterform eats it.
    assert panel.count("--prose-outline") == 4
    assert ("body.has-weather-fx .prose,\nbody.has-weather-fx #room.floating{"
            "backdrop-filter:none!important") in styles


def test_the_panel_is_actually_transparent_in_every_theme():
    """themes.css loads last and overrides the panel background per theme, so
    a band changed only in styles.css/backdrops.js would be reverted by every
    theme's own fallback."""
    themes = (STATIC / "themes.css").read_text(encoding="utf-8")
    # The DECLARATIONS, not the one rule that consumes the variable.
    fallbacks = [
        line for line in themes.splitlines()
        if line.strip().startswith("--reading-panel-bg:")
    ]
    assert fallbacks, "the themed reading panel went missing"
    for line in fallbacks:
        alpha = float(line.split("var(--bd-panel,")[1].split(")")[0].strip())
        assert alpha < 0.6, line

    bd = (STATIC / "js" / "backdrops.js").read_text(encoding="utf-8")
    band = bd[bd.index("const BD_PANEL_MIN"):]
    band = band[:band.index("\n")]
    lo, hi = (float(p.split("=")[1].strip().rstrip(";")) for p in band.split(","))
    assert 0 < lo < hi < 0.6, band


def test_the_composer_stays_opaque():
    """OPAQUE CHROME (styles.css header): every surface sitting directly over
    the page background is opaque, so an ambient colour meant for the STORY
    cannot wash the interface. The transparency pass is for the reading
    surface only -- the input bar is chrome and keeps its solid background."""
    styles = _styles()
    composer = styles[styles.index("#composer{"):]
    composer = composer[:composer.index("}")]
    assert "background:var(--bg2)" in composer
    assert "backdrop-filter" not in composer
