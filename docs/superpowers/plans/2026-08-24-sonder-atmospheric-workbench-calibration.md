# Sonder Atmospheric Workbench Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone in-conversation calibration mockup that compares
Focus and Workbench compositions, material intensity, canvas mode, and idle
versus active digital material without touching Sonder production UI.

**Architecture:** One self-contained HTML fragment owns the mock product window,
seeded content, product-specific CSS, and presentation-only state. An original
atmospheric image is compressed and embedded as a data URL so the fragment has
no runtime API or local-file dependency. Browser inspection validates both
visual composition and the four local controls.

**Tech Stack:** HTML fragment, product-scoped CSS, vanilla JavaScript, an
original generated raster canvas, bundled Python/Pillow for image compression,
the Visualize renderer, and the in-app browser for desktop verification.

**Spec:**
`docs/superpowers/specs/2026-08-24-sonder-atmospheric-digital-workbench-mockup-design.md`

## Global Constraints

- Output is mockup-only and lives outside the checked-out repository at
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html`.
- No Sonder route, API, storage, extension, persistence, or backend code changes.
- No Prime Intellect or ChungusHub source, markup, brand assets, video, or font
  binaries are copied, embedded, redistributed, or hotlinked.
- Preserve the measured Prime proportions while using an open licensed mono
  substitute for ABC Favorit Mono.
- The visualization fragment remains below 1 MB and contains no `fetch`, XHR,
  WebSocket, `window.open`, or external application calls.
- The fragment root ID is `sonder-calibration` and all custom selectors are
  scoped below it.
- The first render is useful without interaction and defaults to Workbench,
  Instrument material, Atmospheric canvas, and Idle activity.
- Both Focus and Workbench must use the same story, canvas, center geometry,
  typography, and composer.
- Idle material is static; activity motion honors `prefers-reduced-motion`.
- Existing `.tmp/` and `debug.log` in the repository remain untouched.

---

### Task 1: Original Atmospheric Canvas

**Files:**
- Create temporarily:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-atmosphere-source.png`
- Create temporarily:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-atmosphere.jpg`

**Interfaces:**
- Consumes: the visual thesis and atmospheric-canvas requirements from the spec.
- Produces: an original 16:9 image with a calm center-right focal structure and
  dark left/bottom negative space suitable for prose.

- [ ] **Step 1: Generate the original scene**

  Use the image-generation tool with this exact art direction:

  ```text
  Original cinematic atmospheric environment for a dark literary fiction
  workspace, 16:9. A vast misty ravine at blue hour, wet black rock, deep
  evergreen foliage, still reflective water, and one narrow impossible vertical
  aperture emitting restrained pale green-white light near the center-right.
  Large calm shadowed negative space through the left-center and lower center for
  readable story text. Photoreal, restrained exposure, subtle volumetric haze,
  premium science-fiction editorial art direction, no people, no spacecraft,
  no typography, no logo, no interface, no bright fantasy magic, no copied
  composition from any existing website.
  ```

- [ ] **Step 2: Inspect composition at original detail**

  Open the generated image with `view_image(detail="original")`. Reject and
  regenerate if the aperture dominates the frame, the left-center is too busy
  for prose, or the image contains text, a logo, or recognizable branded media.

- [ ] **Step 3: Compress for inline use**

  Use the bundled Python executable and Pillow to resize to 1600 x 900, convert
  to sRGB JPEG, and save at quality 74 with optimization. Confirm the result is
  below 300 KB; lower quality in increments of four only if required.

  ```python
  from pathlib import Path
  from PIL import Image, ImageOps

  source = Path(
      r"C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-atmosphere-source.png"
  )
  output = Path(
      r"C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-atmosphere.jpg"
  )
  image = Image.open(source).convert("RGB")
  image = ImageOps.fit(image, (1600, 900), method=Image.Resampling.LANCZOS)
  image.save(output, "JPEG", quality=74, optimize=True, progressive=True)
  assert output.stat().st_size < 300_000
  ```

- [ ] **Step 4: Reinspect the compressed image**

  Open `sonder-atmosphere.jpg` at original detail and verify that dark gradients,
  mist, foliage, and the aperture remain clean without block artifacts.

### Task 2: Calibration Fragment

**Files:**
- Create:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html`

**Interfaces:**
- Consumes: `sonder-atmosphere.jpg` from Task 1 and the exact measured reference
  profile in the spec.
- Produces: root `#sonder-calibration` with local state attributes
  `data-layout`, `data-material`, `data-canvas`, and `data-activity`.

- [ ] **Step 1: Write the semantic product frame**

  Use literal markup under one root. Include:

  - a product window with an accessible label;
  - the 40 px top shelf with `SCENE 01`, `LIBRARY 02`, `SETTINGS 03`, static
    story identity, and ready/activity status;
  - the atmospheric Scene center with story identity, realistic transcript, and
    compact composer;
  - a left dock containing Characters above Custom Theme;
  - a right dock containing Scene Effects above a Personas / AI Connections tab
    group;
  - collapsed edge controls visible in Focus;
  - a compact calibration rail containing exactly four controls: Layout,
    Material, Canvas, and Activity.

- [ ] **Step 2: Implement composition before effects**

  Build the base geometry in grayscale first:

  - 40 px top shelf;
  - 286 px left and right docks at the 1600 px calibration width;
  - a center transcript measure between 620 and 680 px;
  - 30 px module headers and one-pixel shelf dividers;
  - 11-12 px mono chrome, 14 px story identity, and 17 px literary prose;
  - square corners, no cards, no pills, and no independent panel shadows.

  Focus must collapse both docks without changing the center content tree.

- [ ] **Step 3: Implement the shared material family**

  Define product-specific values directly below `#sonder-calibration`; do not
  use visualization CSS variables or generic `.card` / `.btn` classes.

  The target Instrument material uses:

  - neutral black glass between 76 and 84 percent opacity;
  - `backdrop-filter: blur(12px)`;
  - a one-pixel white upper edge around 14 percent opacity;
  - a one-pixel black lower edge around 52 percent opacity;
  - one raster field shared by top cells, active tabs, and module headers;
  - cyan for current Scene, green for ready, and amber only for Settings/source
    identification;
  - environmental color behind material, never across text.

  Editorial and Phosphor adjust only raster/bloom intensity. They do not change
  geometry, type size, or content.

- [ ] **Step 4: Embed both canvases**

  Encode `sonder-atmosphere.jpg` as base64 and embed it in the fragment's
  atmospheric layer. Define the Gradient canvas as authored layered radial and
  linear gradients named `Deep Current`; do not add a third canvas option.

- [ ] **Step 5: Add local interactions**

  Use native buttons with `aria-pressed` or native selects. The state function
  must set only root data attributes and visible labels:

  ```js
  const root = document.getElementById("sonder-calibration");
  const setState = (name, value) => {
    root.dataset[name] = value;
    root.querySelectorAll(`[data-set-${name}]`).forEach(control => {
      control.setAttribute("aria-pressed", String(control.dataset[`set${name[0].toUpperCase()}${name.slice(1)}`] === value));
    });
  };
  ```

  Activity may start the slow light wake; switching back to Idle must return to
  a fully static frame.

- [ ] **Step 6: Validate the fragment contract**

  Confirm:

  - no doctype, html, head, or body wrapper;
  - no literal `\"` or `\n` escape artifacts;
  - no undefined queried elements;
  - file size below 1 MB;
  - all four controls update their corresponding root data attribute;
  - no references to Prime assets or font binaries.

### Task 3: Render and Visual Verification

**Files:**
- Read:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html`
- Generate for inspection:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration-preview.html`
- Generate for inspection:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.png`

**Interfaces:**
- Consumes: the complete fragment from Task 2.
- Produces: a visually reviewed fragment ready for the inline visualization
  reference.

- [ ] **Step 1: Render the fragment**

  Run:

  ```powershell
  C:\Users\Keptin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe `
    C:\Users\Keptin\.codex\plugins\cache\openai-bundled\visualize\1.0.22\skills\visualize\scripts\render.py `
    C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration.html `
    C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration-preview.html
  ```

  Expected: the preview path prints and the process exits zero.

- [ ] **Step 2: Inspect desktop geometry and interactions**

  Open the rendered preview in the in-app browser at 1600 x 900. Verify with
  computed geometry that the shelf is 40 px, both docks are 286 px in Workbench,
  the story title is static, and Focus collapses both docks. Exercise every
  Layout, Material, Canvas, and Activity option and verify root data attributes.

- [ ] **Step 3: Capture and inspect the Workbench state**

  Capture the browser viewport to `sonder-workbench-calibration.png`, inspect it
  with `view_image`, and apply the composition, squint, grayscale, texture-off,
  density, and subtraction review gates from the spec.

- [ ] **Step 4: Inspect the Focus state**

  Switch to Focus without reloading. Verify that the same story content and
  canvas remain, edge controls replace the docks, and the frame still feels
  intentional rather than empty.

- [ ] **Step 5: Check runtime cleanliness**

  Read browser console logs and confirm no JavaScript errors, failed font/image
  loads, blocked resources, or accessibility-name omissions on controls.

- [ ] **Step 6: Deliver the reviewed fragment**

  Return the required inline visualization reference for
  `sonder-workbench-calibration.html`, plus one concise note identifying the
  measured font sources and the licensed mono substitution.
