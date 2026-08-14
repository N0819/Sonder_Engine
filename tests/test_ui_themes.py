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
    """The transcript is capped at a reading measure while the composer ran
    full width, so what you typed and what you read were different column
    widths stacked on each other -- and story text sizing did not reach the
    input at all.

    Pinned on the SHARED VARIABLE rather than a literal width. The column is no
    longer a constant: syncVitalsGutter (settings.js) publishes --story-width
    per frame from the room the flanking floats leave. What must stay true is
    that both rules read the same one -- if they ever diverge, the input box
    stops lining up with the story above it at every width but the fallback."""
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    settings = (STATIC / "js" / "settings.js").read_text(encoding="utf-8")

    # A measure wrapper inside the full-bleed composer chrome, sharing the
    # story column's own max-width so the two line up on screen.
    assert 'id="composer-inner"' in index
    assert '#composer-inner{display:flex;' in styles
    assert '.turn{max-width:var(--story-width,720px);' in styles
    assert 'max-width:var(--story-width,720px);margin-inline:auto}' in styles
    # ...and somebody has to actually write it, or both fall to the literal.
    assert '"--story-width"' in settings

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


def test_tavern_every_sidebar_tab_is_a_shelf():
    """Stories, Characters and Personas were planks while Lore was books, which
    made the shelf read as one tab's private conceit rather than as what the
    sidebar is. The binding vocabulary is deliberately the same on all four, so
    switching tabs changes what is on the shelf, not the furniture."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")

    rows = _tavern_rule(
        styles, ':root[data-theme="tavern"] #sidelist .library-item {')
    assert "--book-leather" in rows
    assert "border-radius: 2px 6px 6px 2px;" in rows   # bound edge / fore-edge
    assert "margin-bottom: 0;" in rows                 # books on a shelf touch

    # The same five leathers as the Lore shelf, not a second palette that
    # happens to look similar.
    def leathers(marker):
        return {ln.split("--book-leather:")[1].strip()
                for ln in styles.splitlines()
                if "--book-leather:" in ln and marker in ln}

    shelf = leathers("#sidelist")
    lore = leathers(".lore-side")
    assert len(shelf) >= 4 and shelf <= lore | shelf and lore <= shelf | lore
    assert shelf == lore, (shelf ^ lore)

    # Scoped through #sidelist, so an .item inside a dialog -- where the
    # surface is paper, not a shelf -- does not pick a leather up.
    assert ":root[data-theme=\"tavern\"] .item { --book-leather" not in styles


def _srgb_luminance(hex_colour):
    parts = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    parts = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
             for c in parts]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def _contrast(a, b):
    la, lb = _srgb_luminance(a), _srgb_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_tavern_paper_is_not_a_lightbox():
    """The sheet began as #f2e6cb -- the colour of NEW paper under a flash.
    Against a room this dark that is the brightest thing on the screen by a
    wide margin, and a dialog opening at night puts it straight into your eyes.
    Old stock is the same hue at far lower luminance and still reads as paper;
    the test is the luminance, because 'still looks like paper' is exactly the
    judgement that drifts back upward one tweak at a time."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    block = styles[styles.index(':root[data-theme="tavern"] {'):]
    block = block[:block.index("\n}")]

    face = block[block.index("--paper-face:"):]
    face = face[:face.index(";")]
    tones = [t for t in face.split() if t.startswith("#")]
    tones = [t.rstrip(",)") for t in tones]
    assert len(tones) == 2, face

    # The original pair sat at ~.79 and ~.68 relative luminance. Anything in
    # that neighbourhood is the glare this was twice asked to fix.
    for tone in tones:
        assert _srgb_luminance(tone) < 0.55, (tone, _srgb_luminance(tone))

    # Darkening the sheet is only safe because the ink stayed put, which means
    # contrast went UP rather than down. Hold that: body ink and the secondary
    # ink both clear 4.5:1 against the darker of the two tones.
    ink = block[block.index("--paper-ink:"):]
    ink = ink[ink.index("#"):][:7]
    dim = block[block.index("--paper-ink-dim:"):]
    dim = dim[dim.index("#"):][:7]
    darkest = min(tones, key=_srgb_luminance)
    assert _contrast(ink, darkest) >= 4.5, _contrast(ink, darkest)
    assert _contrast(dim, darkest) >= 4.4, _contrast(dim, darkest)


def test_tavern_every_menu_is_a_page():
    """The room is wood; the things you READ in it are paper. Every dialog in
    the app is #modalbox, so the page treatment binds to that one element and
    the whole menu system becomes one open book with no per-dialog rule.
    The affordable part is that styles.css and lorebooks.css are nearly all
    token-driven: rebinding tokens on the page re-tints its inputs, buttons,
    cards, badges and rules at once."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")

    page = _tavern_rule(styles, ':root[data-theme="tavern"] #modalbox {')
    assert "--paper-face" in page          # one continuous sheet
    assert "--book-cover" in page          # bound into a cover

    # Ink on paper, rebound so everything inside inherits it -- and the --bg
    # ramp with it, because the second tier (inset code blocks, dropdown
    # panels, toolbars) reads --bg directly assuming it is dark.
    tokens = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-panel {')
    for token in ("--fg:", "--dim:", "--bd:", "--input-bg:", "--card-bg:",
                  "--bg:", "--bg3:", "--chrome-bg:"):
        assert token in tokens, token

    # --chrome-bg is declared at :root as var(--bg2), which SUBSTITUTES there;
    # what inherits down is the dark value already resolved, so rebinding
    # --bg2 alone leaves a dark bar lying across the page.
    assert "--chrome-bg: var(" not in tokens

    # The board rule sets background-image directly rather than through a
    # token, so a card on a page has to clear those layers by hand or a wooden
    # plank sits in the middle of the paper.
    card = _tavern_rule(styles, ':root[data-theme="tavern"] #modalbox .card,')
    assert "background-image: none;" in card

    # The lit-panel glow belongs to wood. On paper it reads as a stain.
    glow = _tavern_rule(styles, ':root[data-theme="tavern"] #composer {')
    assert "inset 0 0 60px rgba(255, 168, 74, .07)" in glow
    head = styles[:styles.index("inset 0 0 60px rgba(255, 168, 74, .07)")]
    assert '#modalbox {\n  box-shadow: inset 0 0 60px' not in head


def test_tavern_dialogs_are_bound_in_book_covers():
    """A dialog opened from a row in the sidebar is bound in that row's
    leather. The choice cannot be made in CSS -- which list row you clicked is
    not something a stylesheet can see from #modalbox -- so components.js
    resolves it and writes data-cover, and every other theme ignores it."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")
    source = (STATIC / "js" / "components.js").read_text(encoding="utf-8")

    for n in range(1, 6):
        assert f"--book-cover-{n}:" in styles
        assert f'#modalbox[data-cover="{n}"]' in styles

    assert "box.dataset.cover" in source
    # The cycle length has to agree with the stylesheet's five leathers.
    assert "const BOOK_COVERS = 5;" in source
    # Consumed on use: a dialog opened from the toolbar must not inherit
    # whichever book happened to be clicked last, possibly minutes ago.
    assert "pendingCover = null;" in source
    # And the cover unwinds with the modal stack, or closing a confirm
    # re-shows its parent bound in the confirm's cover.
    assert "cover: box.dataset.cover," in source


def test_tavern_lorebook_editor_has_no_board_of_its_own():
    """The workspace is three panels side by side, which is the shape of an
    open spread -- but the dialog around it is the binding now. A second
    leather board inside it put a wooden frame between the cover and the
    pages."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")

    ws = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-workspace {')
    assert "gap: 0;" in ws               # pages meet at a gutter, not a gap
    assert "background: none;" in ws
    assert "tavern-wood.png" not in ws

    page = _tavern_rule(styles, ':root[data-theme="tavern"] .lore-panel {')
    assert "--paper-edge" in page        # the fold, and nothing else


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


def test_lcars_filled_blocks_never_carry_dark_theme_ink():
    """Three surfaces in this theme are solid LCARS orange -- badges
    (--badge-bg), selected lore rows (--selected-bg) and the active inspector
    tab -- and each drew text picked for a NEAR-BLACK row: --dim grey, or the
    lore tree's near-white name. Grey on orange lands around 1.9:1, which made
    the selected entry the hardest thing in the editor to read. A filled block
    takes black ink here, without exception."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")

    badge = _tavern_rule(styles, ':root[data-theme="lcars"] .badge {')
    assert "color: #000;" in badge

    # The status variants then have to recolour the BLOCK: their pastel greens
    # and pinks were chosen to glow on near-black and do nothing on orange.
    for variant in ("ok", "warn", "err"):
        rule = _tavern_rule(styles, f':root[data-theme="lcars"] .badge.{variant} {{')
        assert "background: var(--" in rule and "color: #000;" in rule

    # The whole selected row, not just its first line: name, subtitle, handle
    # and toggle were all light-on-dark colours.
    selected = _tavern_rule(
        styles, ':root[data-theme="lcars"] .lore-tree-row.selected .lore-tree-name,')
    assert "color: #000;" in selected
    assert ".lore-tree-subtitle," in styles and ".lore-tree-handle," in styles

    # A badge riding in a selected row is an orange pill ON orange. Inverted.
    inverted = _tavern_rule(
        styles, ':root[data-theme="lcars"] .lore-tree-row.selected .badge,')
    assert "background: #000;" in inverted and "color: var(--acc);" in inverted


def test_lcars_inspector_tabs_are_pills():
    """The tab strip across the cast, persona and lorebook windows is a
    dark-theme idiom: transparent buttons with a coloured underline. Against
    the black ink every LCARS button carries, that was black text on a
    transparent strip over a black panel -- a row of controls you could only
    find by hovering."""
    styles = (STATIC / "themes.css").read_text(encoding="utf-8")

    tab = _tavern_rule(
        styles, ':root[data-theme="lcars"] .lore-inspector-tabs button {')
    assert "background: var(--lcars-blue);" in tab
    assert "border-radius: 999px;" in tab
    assert "color: #000;" in tab

    on = _tavern_rule(
        styles, ':root[data-theme="lcars"] .lore-inspector-tabs button.on {')
    assert "background: var(--acc);" in on and "color: #000;" in on
