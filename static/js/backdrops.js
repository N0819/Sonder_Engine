"use strict";
// ---- Scene backdrops ----
// The picture half of the reading view: a generated image of the room the
// player is standing in, painted behind the transcript. The engine side
// (backdrops.py) guarantees the image depicts the room EMPTY and is cached on
// room + visible state; this file is only ever responsible for showing the
// right one at the right moment and keeping the prose readable on top of it.
//
// Three properties this deliberately preserves:
//
// 1. Nothing here blocks reading. A miss is a slow, paid image generation, so
//    the transcript renders first and the picture arrives whenever it
//    arrives -- or never, which is a valid outcome, not an error state.
// 2. Backdrops are opt-in and cost money, so a cache MISS is only ever paid
//    for when the feature is switched on. With it off, this file still shows
//    already-generated images (they are free) but never commissions one.
// 3. One picture per signature, once. Two turns in the same room share a
//    signature and must not re-fade, re-fetch, or re-pay.

const BD = {
  enabled: false,        // mirrors the backdrops_enabled setting
  configured: false,     // an image model is actually set
  layers: null,          // the two cross-fading image layers
  front: 0,              // which layer is currently showing
  signature: null,       // the signature currently painted
  shownRoom: null,       // which ROOM the painted picture is of
  wanted: null,          // the signature the visible turn wants painted
  turnSeq: 0,            // guards against out-of-order async responses
  byTurn: new Map(),     // turn id -> the GET payload (cleared per render)
  inflight: new Map(),   // signature -> promise, so one generation per picture
  failed: new Set(),     // signatures already tried and given up on
  chatId: null,          // which story the painted backdrop belongs to
  timer: null,
  dwellTimer: null,      // the second, slower one: see backdropOnVisibleTurn
  pendingTurn: null,     // which turn those two clocks are running for
};

// Reading what already exists is instant and free; COMMISSIONING one is neither.
// So the two are on different clocks: a picture already on disk appears as fast
// as the scroll settles, and nothing is paid for until the reader has actually
// stopped to read.
const BD_SETTLE_MS = 220, BD_DWELL_MS = 2000;

// The scrim over the whole picture: a fixed strength, tuned on screen. It was
// originally derived from the image's luminance across a 0.30-0.78 range,
// which protected readability but meant the same room could look markedly
// different depending on how bright its render came out.
const BD_VEIL = 0.62;
// The per-turn prose panel. It ran 0.86-0.92 -- near-opaque, the room only a
// faint impression behind a solid surface. It is now roughly 60% transparent,
// so the picture genuinely reads through the column and the panel is a tint
// over the room rather than a box in front of it.
//
// What carries the readability that the missing opacity used to: a mild
// backdrop-filter blur on the panel, and a thin four-way outline on the glyphs
// themselves (both in styles.css, `body.has-backdrop .prose`). Those two are
// load-bearing at this alpha, not decoration -- drop either one and bright
// detail in the render starts eating letterforms.
//
// The band is wider than the old one because the measurement now matters. At
// 0.86-0.92 luminance was a refinement; here it is the difference between a
// dark room the words sit on comfortably and a bright one that needs real
// help, so a bright render pulls a materially heavier tint.
const BD_PANEL_MIN = 0.34, BD_PANEL_MAX = 0.50;

function backdropLayers() {
  if (BD.layers) return BD.layers;
  // A direct child of <body>, NOT of #app: #app is position:relative;z-index:0
  // and so opens a stacking context that a negative z-index inside it cannot
  // escape. This sits alongside body::before (the mood tint), one level
  // further back, so the mood tint reads as a colour grade over the image.
  const root = el("div", { id: "scene-backdrop", "aria-hidden": "true" });
  const a = el("div", { class: "bd-layer" });
  const b = el("div", { class: "bd-layer" });
  root.append(a, b, el("div", { class: "bd-vignette" }), el("div", { class: "bd-veil" }));
  document.body.prepend(root);
  BD.layers = [a, b];
  return BD.layers;
}

// Average luminance of the middle band of the image -- where the text column
// actually sits. Sampling the whole frame instead would let bright sky at the
// edges darken a scrim the prose never needed.
function backdropLuminance(img) {
  try {
    const w = 48, h = 32;
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, w, h);
    const x0 = Math.floor(w * 0.2), x1 = Math.ceil(w * 0.8);
    const data = ctx.getImageData(x0, 0, x1 - x0, h).data;
    let total = 0, n = 0;
    for (let i = 0; i < data.length; i += 4) {
      // Rec. 709 luma, close enough to perceived brightness for a scrim.
      total += (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255;
      n++;
    }
    return n ? total / n : 0.5;
  } catch (e) {
    // A tainted canvas or a browser without getImageData is not worth
    // failing a backdrop over -- fall back to the middle of the range.
    return 0.5;
  }
}

function applyBackdropContrast(img) {
  const lum = Math.min(1, Math.max(0, backdropLuminance(img)));
  const root = document.documentElement.style;
  root.setProperty("--bd-veil", BD_VEIL.toFixed(3));
  root.setProperty("--bd-panel",
    (BD_PANEL_MIN + (BD_PANEL_MAX - BD_PANEL_MIN) * lum).toFixed(3));
  document.body.dataset.backdropLum = lum > 0.55 ? "bright" : "dark";
}

// Drop a faded-out layer's bitmap once it is genuinely invisible.
//
// `opacity:0` hides an image; it does not free it. A decoded 1024x1024 backdrop
// is several megabytes of GPU texture -- more once `background-size:cover`
// upscales it to the viewport -- and this app holds TWO layers to crossfade
// between. Without this, every backdrop the story ever showed stays resident
// for the life of the tab, on a laptop whose GPU memory is the same memory
// everything else is using.
//
// Guarded on the layer still being off when the transition finishes: a fast
// scroll can hand this same node the NEXT backdrop before the fade completes,
// and clearing then would blank an image that is on its way in.
function releaseBackdropLayer(layer) {
  if (!layer) return;
  const done = () => {
    layer.removeEventListener("transitionend", done);
    if (!layer.classList.contains("on")) layer.style.backgroundImage = "";
  };
  layer.addEventListener("transitionend", done);
  // `transitionend` never fires if the layer was already at opacity 0 (nothing
  // animates), and reduced-motion removes the transition entirely -- so the
  // listener alone would leak exactly the cases that need no animation.
  setTimeout(done, 1400);
}

function clearBackdrop() {
  BD.signature = null;
  document.body.classList.remove("has-backdrop");
  if (BD.layers) for (const layer of BD.layers) {
    layer.classList.remove("on");
    releaseBackdropLayer(layer);
  }
}

// Cross-fades to `url`. The image is decoded BEFORE the fade starts, so the
// transition is always image-to-image rather than a fade to a blank layer
// followed by a snap once the bytes land.
function showBackdrop(url, signature) {
  if (BD.signature === signature) return;
  BD.signature = signature;
  const layers = backdropLayers();
  const img = new Image();
  img.onload = () => {
    if (BD.signature !== signature) return;   // scrolled on while decoding
    const next = layers[1 - BD.front];
    next.style.backgroundImage = `url("${url}")`;
    next.classList.add("on");
    const outgoing = layers[BD.front];
    outgoing.classList.remove("on");
    releaseBackdropLayer(outgoing);
    BD.front = 1 - BD.front;
    // Reveal FIRST, measure second. The contrast pass reads pixels back off a
    // canvas, and no failure in it -- an unsupported API, a locked-down
    // browser -- may end with an image that was paid for sitting invisible
    // behind an opacity:0 container. Until it runs, the veil uses its CSS
    // default, which is readable.
    document.body.classList.add("has-backdrop");
    applyBackdropContrast(img);
  };
  img.onerror = () => { if (BD.signature === signature) BD.signature = null; };
  img.src = url;
}

function backdropWorking(on) {
  const button = $("#b-backdrop");
  if (button) button.classList.toggle("working", !!on);
}

// One generation per signature no matter how many turns or scroll events ask
// for it. The server deduplicates too (a lock per signature), but doing it
// here as well keeps a scroll-back from queueing a dozen identical 30-second
// requests behind each other.
// How long to keep asking before giving up on one picture. Generation is
// normally 12-40s; the provider's own ceiling is three minutes, so this sits
// just past it rather than abandoning an image that was about to arrive.
const BD_POLL_MS = 3000, BD_POLL_LIMIT = 70;

// The POST returns as soon as the work is QUEUED, so the wait happens here in
// polls rather than in a request held open server-side for the length of a
// generation.
async function awaitBackdrop(turnId, signature, first) {
  let state = first;
  for (let i = 0; state.status === "pending" && i < BD_POLL_LIMIT; i++) {
    await new Promise(resolve => setTimeout(resolve, BD_POLL_MS));
    state = await api("GET", `/api/turns/${turnId}/backdrop`);
    // The room changed under us (an edit, a reroll): whatever is rendering is
    // no longer what this turn wants, so stop asking. The caller's own
    // wanted-signature check then declines to paint it.
    if (state.signature !== signature) break;
  }
  // Each ending described as itself -- the twin of awaitAmbience's rule, and
  // it had the twin's defect in different wording: a signature that drifted
  // mid-poll broke the loop while the DRIFTED state still said "pending", so
  // the next line threw "still generating after several minutes" three
  // seconds in; and `absent` (work retired with nothing produced) fell
  // through silently, a paid pass that said nothing at all.
  if (state.signature !== signature) {
    // Obsolete, not broken: the observer's next pass owns the room's new
    // state, and there is nothing true to say about the old one.
    return null;
  }
  if (state.status === "error") {
    throw taggedError("failed", state.error || "generation failed");
  }
  if (state.ready) return state;
  if (state.status === "pending") {
    // Honestly still rendering when the budget ran out. The budget already
    // sits past the provider's own three-minute ceiling, but the queue entry
    // is still active and a later request simply joins it -- so this is
    // "slow", never a verdict on the room.
    throw taggedError("slow",
      "still rendering after several minutes — it appears when you next stop here");
  }
  throw taggedError("gone", "the generation was called off before it finished");
}

function generateBackdrop(turnId, signature) {
  if (BD.inflight.has(signature)) return BD.inflight.get(signature);
  backdropWorking(true);
  const job = api("POST", `/api/turns/${turnId}/backdrop`, {})
    .then(res => awaitBackdrop(turnId, signature, res))
    .then(res => {
      if (!res) return null;            // obsolete: the room moved on mid-poll
      BD.byTurn.set(turnId, res);
      // Every OTHER turn already known to want this same picture is ready
      // now too -- a room usually spans several turns, and without this each
      // of them would re-POST for an image that is already on disk.
      for (const [id, state] of BD.byTurn) {
        if (state && state.signature === res.signature && !state.ready) {
          BD.byTurn.set(id, { ...state, ready: true, url: res.url });
        }
      }
      return res;
    })
    .catch(error => {
      // Only a recorded verdict gives up on this picture for the session (no
      // credit, a bad model id, a room with nothing to depict -- those fail
      // again the same way). A generation that was called off, outlived the
      // poll's patience, or died with the connection may be asked again:
      // blacklisting those converted one bad minute into "this room never
      // gets a picture" for the rest of the session.
      if (error?.kind === "failed") BD.failed.add(signature);
      toast(`Backdrop: ${(error?.message || "generation failed")}`,
            error?.kind && error.kind !== "failed" ? "warn" : "err");
      return null;
    })
    .finally(() => {
      BD.inflight.delete(signature);
      if (!BD.inflight.size) backdropWorking(false);
    });
  BD.inflight.set(signature, job);
  return job;
}

async function backdropForTurn(turnId, opts = {}) {
  if (turnId == null) return;
  const seq = ++BD.turnSeq;
  let state = BD.byTurn.get(turnId);
  if (!state) {
    try {
      state = await api("GET", `/api/turns/${turnId}/backdrop`);
    } catch (e) {
      return;                       // a transcript that scrolls is worth more
    }
    BD.byTurn.set(turnId, state);
  }
  if (seq !== BD.turnSeq) return;   // the reader moved on while we asked
  BD.enabled = !!state.enabled;
  BD.configured = !!state.configured;
  updateBackdropBtn();
  // The room-scoped weather rides on this payload, so the rain overlay follows
  // the same "which turn is being read" answer the picture does. Guarded like
  // every other optional module here: a missing script must not break the
  // transcript.
  if (typeof weatherFxForTurn === "function") weatherFxForTurn(state);

  if (!state.signature) { BD.wanted = null; clearBackdrop(); return; }
  BD.wanted = state.signature;
  if (state.ready && state.url) {
    BD.shownRoom = state.room_id || null;
    showBackdrop(state.url, state.signature);
    return;
  }
  // A miss. The previous picture stays up rather than blanking -- but only
  // while it is a picture of THIS ROOM. Consecutive beats in one room differ by
  // the hour, the weather, some damage; holding the image through those reads
  // as the room the reader is in. Holding it across a doorway does not: it
  // shows the waystation's fire behind a beat spent out in the blizzard, which
  // is the transcript and the screen disagreeing about where the story is.
  // A room with no picture yet is better represented by none.
  if ((state.room_id || null) !== BD.shownRoom) {
    BD.shownRoom = null;
    clearBackdrop();
  }
  // Only an enabled, configured install pays to fill it in -- and only once the
  // reader has settled here, or this turn was just generated. Scrolling through
  // a long story crosses dozens of rooms nobody stopped in.
  if (!opts.commission) return;
  if (!BD.enabled || !BD.configured || BD.failed.has(state.signature)) return;

  const generated = await generateBackdrop(turnId, state.signature);
  if (!generated || !generated.url) return;
  // Gated on the PICTURE still being wanted, NOT on the turn this request
  // started from. Generation takes tens of seconds and every scroll tick
  // bumps turnSeq, so a sequence check here threw away almost every image the
  // moment it was paid for -- generated, written to disk, never displayed.
  // The signature is the right identity anyway: consecutive turns in one room
  // share it, so drifting a few beats while it renders still wants this exact
  // image.
  if (generated.signature === BD.wanted) {
    BD.shownRoom = state.room_id || null;
    showBackdrop(generated.url, generated.signature);
  }
}

// Called from the scroll observer in chat.js, which fires on every
// intersection change -- coalesce, or a flick of the wheel becomes a dozen
// requests for turns the reader never stopped at.
function backdropOnVisibleTurn(turnId, opts = {}) {
  // Only a CHANGE of turn restarts the clocks. A repeat notification for the
  // turn already pending is not the reader moving, and this module causes
  // several of them itself: renderChat re-asserts its scroll in a
  // requestAnimationFrame, and clearBackdrop() strips the padding, border and
  // max-width off every .prose in the transcript, reflowing the whole scroll
  // container. Restarting a two-second dwell on each of those is how a room
  // with no picture yet never reaches the pass that would commission one --
  // and only such a room, because a room already drawn is served by the quick
  // pass and never needed the dwell at all. That asymmetry is the reported bug.
  if (turnId === BD.pendingTurn) return;
  BD.pendingTurn = turnId;
  clearTimeout(BD.timer);
  clearTimeout(BD.dwellTimer);
  // Always the quick pass, which shows whatever is already cached.
  BD.timer = setTimeout(
    () => backdropForTurn(turnId, { commission: !!opts.fresh }), BD_SETTLE_MS);
  // And, unless this turn was just generated (where the reader is plainly here
  // and waiting), a second pass that is allowed to spend money -- cancelled by
  // scrolling ON to another turn, so passing through a room never commissions
  // it.
  if (!opts.fresh) {
    BD.dwellTimer = setTimeout(
      () => backdropForTurn(turnId, { commission: true }), BD_DWELL_MS);
  }
}

// Turn content (and so its room) can change under us on reroll, edit or
// branch, and renderChat() is where that surfaces.
function backdropResetForRender() {
  BD.byTurn.clear();
  clearTimeout(BD.timer);
  clearTimeout(BD.dwellTimer);
  // The clocks were just cancelled, so nothing is pending for that turn any
  // more. Without this, a re-render that lands the reader back on the SAME
  // turn id would be read as a repeat notification and re-arm nothing -- the
  // one way the guard above could turn into the very defect it fixes.
  BD.pendingTurn = null;
  // Opening a different story (or none) must not leave the previous story's
  // room on screen. The observer would eventually correct it, but only once a
  // turn scrolls into view -- an empty chat has none, so it never would.
  if (BD.chatId !== S.chatId) {
    BD.chatId = S.chatId;
    BD.wanted = null;
    BD.shownRoom = null;
    clearBackdrop();
    // The sky belongs to the story too. WFX state is module-global and is only
    // ever updated when a TURN's payload arrives, so without this a new story
    // kept raining the old one's rain -- indefinitely for a story with no
    // turns yet, since the observer that would correct it never fires.
    if (typeof weatherFxApply === "function") weatherFxApply(null);
  }
  if (!S.chatId) {
    clearBackdrop();
    if (typeof weatherFxApply === "function") weatherFxApply(null);
  }
}

function updateBackdropBtn() {
  const button = $("#b-backdrop");
  if (!button) return;
  const on = BD.enabled && BD.configured;
  button.classList.toggle("on", on);
  button.title = !BD.configured
    ? "Scene backdrops — no image model set yet (⚙ API › Scene backdrops)"
    : (BD.enabled
      ? "Scene backdrops: on — new rooms will be generated"
      : "Scene backdrops: off — already-generated rooms still show");
}

async function toggleBackdrops() {
  BD.enabled = !BD.enabled;
  // Switching it on is the natural "try that again" gesture after a failure
  // (topped up credit, fixed the model id), so it clears the give-up list.
  if (BD.enabled) BD.failed.clear();
  updateBackdropBtn();
  try {
    await api("PUT", "/api/backdrops", { enabled: BD.enabled });
    if (S.boot) S.boot.backdrops_enabled = BD.enabled;
    if (BD.enabled && !BD.configured) {
      toast("Backdrops are on, but no image model is set yet — pick one under ⚙ API.", "warn");
    }
  } catch (error) {
    BD.enabled = !BD.enabled;
    updateBackdropBtn();
    toast("Could not change the backdrop setting.", "err");
  }
}

// Called from boot() once /api/bootstrap has landed.
function syncBackdrops() {
  BD.enabled = !!(S.boot && S.boot.backdrops_enabled);
  BD.configured = !!(S.boot && S.boot.image_model);
  updateBackdropBtn();
}

$("#b-backdrop").onclick = toggleBackdrops;
