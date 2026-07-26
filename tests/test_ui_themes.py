from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def test_theme_assets_are_loaded_in_safe_order():
    index = (STATIC / "index.html").read_text(encoding="utf-8")

    init_at = index.index('/static/js/theme-init.js')
    base_css_at = index.index('/static/styles.css')
    theme_css_at = index.index('/static/themes.css')
    runtime_at = index.index('/static/js/themes.js')
    app_at = index.index('/static/js/app.js')

    # The tiny initializer runs before CSS to avoid a light/dark flash. The
    # theme overrides load after component CSS, and the modal runtime binds
    # before app boot begins.
    assert init_at < base_css_at < theme_css_at
    assert runtime_at < app_at


def test_requested_and_fallback_themes_are_registered():
    source = (STATIC / "js" / "theme-init.js").read_text(encoding="utf-8")

    for theme_id in (
        "sonder",
        "tavern",
        "lcars",
        "stone",
        "ink",
    ):
        assert f'id: "{theme_id}"' in source

    # Scroll and Daylight were withdrawn; nothing may reintroduce them by
    # halves (a registry entry with no tokens, or tokens with no entry).
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    for retired in ("scroll", "daylight"):
        assert f'id: "{retired}"' not in source
        assert f'data-theme="{retired}"' not in styles

    assert 'const THEME_KEY = "sonder.ui.theme"' in source
    assert 'const PROSE_SIZE_KEY = "sonder.ui.proseSize"' in source


def test_a_long_row_title_drops_the_action_group_instead_of_truncating():
    """A long story/character name used to be ellipsized to protect the action
    column -- the buttons stayed put but the name became unreadable, which is
    the thing you are picking from. The row wraps now: the label keeps a
    legible measure, and when nothing fits beside it the whole
    Rename/Export/Delete group moves down together, still right-aligned."""
    app_source = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert 'class: "item story-item"' in app_source
    assert 'class: "item-actions"' in app_source
    # Wrapping row, not a rigid two-column grid.
    assert '.story-item,.library-item{display:flex;flex-wrap:wrap;' in styles
    # The label wraps rather than ellipsizing...
    assert 'white-space:normal;overflow-wrap:anywhere' in styles
    # ...and flex-basis:auto is what makes the drop conditional: flexbox breaks
    # lines on an item's MAX-CONTENT width, so a short title still shares the
    # row and only a long one pushes the group down.
    assert 'flex:1 1 auto;min-width:0' in styles
    # The group stays together and right-aligned on whichever line it lands on.
    assert '.item-actions{display:flex;flex:0 0 auto;' in styles
    assert 'margin-left:auto}' in styles


def test_composer_shares_the_story_measure_and_text_size():
    """The transcript is capped at 65ch while the composer ran full width, so
    what you typed and what you read were different column widths stacked on
    each other -- and story text sizing did not reach the input at all."""
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    # A measure wrapper inside the full-bleed composer chrome, sharing the
    # story column's own max-width so the two line up on screen.
    assert 'id="composer-inner"' in index
    assert '#composer-inner{display:flex;' in styles
    assert '.turn{max-width:720px;margin:0 auto;' in styles
    assert 'max-width:720px;\nmargin-inline:auto}' in styles

    # Story text sizing drives the input, in the prose face.
    input_rule = styles[styles.index("#input{"):]
    input_rule = input_rule[:input_rule.index("}")]
    assert 'font-size:var(--prose-size,17px)' in input_rule
    assert 'var(--prose-font' in input_rule


def test_login_and_guest_inherit_the_saved_theme():
    for filename in ("login.html", "guest.html"):
        html = (STATIC / filename).read_text(encoding="utf-8")
        assert '/static/js/theme-init.js' in html
        assert '/static/themes.css' in html


def test_textured_theme_assets_and_input_contrast_tokens_exist():
    textures = STATIC / "assets" / "theme-textures"
    for filename in ("tavern-wood.png", "stone-slate.png"):
        assert (textures / filename).is_file()

    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    assert '--input-surface:' in styles
    assert '--input-border:' in styles
    assert 'background: var(--composer-surface);' in styles
    assert 'url("/static/assets/theme-textures/tavern-wood.png")' in styles


def test_lcars_uses_the_real_design_language():
    """LCARS is a specific system, not a dark theme with round corners. The
    previous pass gave every control the same opposite-corner radius, which
    read as scattered diagonal lines rather than a console."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    block = styles[styles.index(':root[data-theme="lcars"] {'):]
    block = block[:block.index("}")]

    # True black ground and the canonical palette.
    assert "--bg: #000;" in block
    assert "--acc: #f90;" in block        # LCARS orange
    assert "--acc2: #99f;" in block       # periwinkle
    assert "--lcars-lilac: #c9c;" in block
    # Pills, not the old 18px/5px wedge.
    assert "--control-radius: 999px;" in block
    assert "18px 5px" not in block
    # Flat: colour lives in the frame bars, so surfaces carry no gradient
    # and no texture.
    assert "--chrome-surface: #000;" in block
    assert "gradient" not in block
    assert "theme-textures" not in block
    # Black ink on every colour block.
    assert "--accent-ink: #000;" in block

    # The elbow frame, and colour-cycled control banks.
    assert ':root[data-theme="lcars"] #side {' in styles
    assert "border-right: 18px solid var(--acc);" in styles
    assert '#topactions button:nth-child(4n + 1) { background: var(--acc); }' \
        in styles


def _tavern_rule(styles, selector):
    """Every declaration block for a tavern selector, concatenated.

    A selector legitimately appears in more than one rule -- #side carries its
    border in one and its light grade in another -- so taking the first match
    alone would pin whichever happened to be written first.
    """
    out, at = [], styles.find(selector)
    while at != -1:
        block = styles[at:]
        out.append(block[block.index("{") + 1:block.index("}")])
        at = styles.find(selector, at + 1)
    assert out, selector
    return "\n".join(out)


def test_tavern_list_rows_are_opaque_boards():
    """The rows were transparent over the sidebar's own wood, so one grain ran
    continuously through the whole list and slid underneath the rows as they
    scrolled -- which reads as a hole in the panel rather than as an object
    sitting on it. Each row now carries its own opaque face."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    block = styles[styles.index(':root[data-theme="tavern"] {'):]
    block = block[:block.index("\n}")]

    assert "--board-face:" in block
    # Near-opaque: at anything much below this the panelling behind shows
    # through again and the board turns back into a window.
    for alpha in (".94", ".96"):
        assert alpha in block
    assert 'url("/static/assets/theme-textures/tavern-wood.png")' in block


def test_tavern_board_background_lists_stay_in_step():
    """A background-position list shorter than the layer list is repeated
    cyclically rather than rejected, so a dropped entry silently mis-places a
    layer instead of failing visibly. Every list must name all seven."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    board = _tavern_rule(styles, ':root[data-theme="tavern"] .item,')

    def count(prop):
        line = board[board.index(prop):]
        return line[:line.index(";")].count(",") + 1

    # crack A, crack B, crack C, grain A, grain B, face gradient, plank photo.
    assert count("background-size:") == 7
    assert count("background-repeat:") == 7
    assert count("background-position:") == 7

    # And every per-row variant carries the same seven.
    rows = [ln for ln in styles.splitlines() if ".item:nth-child(7n+" in ln]
    assert len(rows) == 7
    for line in rows:
        positions = line[line.index("background-position:"):]
        assert positions[:positions.index(";")].count(",") + 1 == 7, line


def test_tavern_grain_is_not_a_comb():
    """A single evenly spaced repeat reads as a comb: every line parallel, the
    same weight, the same distance apart -- the one thing wood never is."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    block = styles[styles.index(':root[data-theme="tavern"] {'):]
    block = block[:block.index("\n}")]

    # Two passes on OPPOSED bearings, so the lines converge and separate
    # across the width instead of marching in parallel.
    assert "--board-grain-a:" in block and "--board-grain-b:" in block
    assert "repeating-linear-gradient(0.7deg," in block
    assert "repeating-linear-gradient(-1.1deg," in block
    # Cracks on three genuinely different bearings, entering from different
    # edges -- one set of parallel verticals read as panel seams dividing the
    # row rather than as damage in a single board.
    bearings = {"72deg", "107deg", "148deg"}
    assert all("linear-gradient(%s," % b in block for b in bearings)


def test_tavern_light_comes_from_one_corner_and_falls_off():
    """One source, high in the top-left. Every surface is graded by its own
    distance from it; a uniformly lit set of panels reads as a brown tint on
    the page rather than as a room with a fire in it."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    block = styles[styles.index(':root[data-theme="tavern"] {'):]
    block = block[:block.index("\n}")]
    assert "at 2% -6%" in block          # hearth in the LEFT corner

    # The sidebar brightens toward its top, the header toward its left.
    assert "rgba(255, 190, 104, .13)" in _tavern_rule(
        styles, ':root[data-theme="tavern"] #side {')
    assert "rgba(255, 194, 110, .15)" in _tavern_rule(
        styles, ':root[data-theme="tavern"] #top {')


def test_tavern_sidebar_footer_does_not_restart_the_falloff():
    """Giving the footer its own graded surface restarted the sidebar's
    gradient at the footer's top edge, so the light stepped down abruptly at
    the seam instead of continuing to the floor."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    footer = _tavern_rule(styles, ':root[data-theme="tavern"] #sideactions {')
    assert "background: transparent;" in footer
    assert "--composer-surface" not in footer
    assert "--chrome-surface" not in footer


def test_tavern_hearth_flicker_stops_for_reduced_motion():
    """It sits behind text people are reading, so the movement is opt-out."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    assert "@keyframes tavern-hearth" in styles
    assert "animation: tavern-hearth" in styles

    reduced = styles[styles.rindex("@media (prefers-reduced-motion: reduce)"):]
    assert 'body::before { animation: none }' in reduced


def test_tavern_lore_tab_is_a_bookshelf():
    """Every other tab lists things that live in the story; the Lore tab lists
    BOOKS, and in a tavern they are on a shelf. The tree structure already
    matches the furniture -- a book with children is a book with a shelf under
    it -- so this is a restyle of the existing rows, not new markup."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")

    tree = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-side-tree {')
    assert "gap: 0;" in tree                 # books on a shelf touch
    assert "border-bottom: 4px solid" in tree   # the shelf board itself

    row = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-side-row {')
    assert "--book-leather" in row
    assert "border-radius: 2px 6px 6px 2px;" in row   # bound edge / fore-edge

    # Bindings are dyed in batches: several leathers on a cycle, so a shelf is
    # not one colour repeated.
    leathers = {ln.split("--book-leather:")[1]
                for ln in styles.splitlines() if "--book-leather:" in ln}
    assert len(leathers) >= 5

    # Scoped to the Lore tab by construction -- .lore-side-* exists nowhere
    # else -- so no other list picks up book styling.
    assert ".lore-side-row" in styles and "#sidelist .item { --book-leather" not in styles


def test_tavern_lorebook_editor_is_an_open_book():
    """The workspace is already three panels side by side, which is the shape
    of an open book. The affordable part is that lorebooks.css is nearly all
    token-driven, so rebinding tokens on the page re-tints its inputs, badges
    and rules at once."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")

    ws = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-workspace {')
    assert "gap: 0;" in ws               # pages meet at a gutter, not a gap

    page = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-panel {')
    # Ink on paper, rebound so everything inside inherits it.
    for token in ("--fg:", "--dim:", "--bd:", "--input-bg:", "--card-bg:"):
        assert token in page, token

    # The board rule sets background-image directly rather than through a
    # token, so a card on a page has to clear those layers by hand or a wooden
    # plank sits in the middle of the paper.
    card = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-panel .card,')
    assert "background-image: none;" in card


def test_lcars_dismiss_controls_are_filled_blocks():
    """LCARS has no ghost control. `button.ghost` zeroes the background and
    this theme sets black ink on every button, so a window's close control was
    a black glyph on a transparent black panel -- legible only as the gap where
    something should be."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    rule = _tavern_rule(styles, ':root[data-theme="lcars"] #modalx,')

    assert "background: var(--err);" in rule   # filled, in the dismiss colour
    assert "color: #000;" in rule              # the black ink LCARS wants
    assert "border-radius: 999px;" in rule     # a pill, like every other block
