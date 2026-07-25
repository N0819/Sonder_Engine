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
  wanted: null,          // the signature the visible turn wants painted
  turnSeq: 0,            // guards against out-of-order async responses
  byTurn: new Map(),     // turn id -> the GET payload (cleared per render)
  inflight: new Map(),   // signature -> promise, so one generation per picture
  failed: new Set(),     // signatures already tried and given up on
  chatId: null,          // which story the painted backdrop belongs to
  timer: null,
};

// The scrim over the whole picture: a fixed strength, tuned on screen. It was
// originally derived from the image's luminance across a 0.30-0.78 range,
// which protected readability but meant the same room could look markedly
// different depending on how bright its render came out.
const BD_VEIL = 0.62;
// The per-turn prose panel: near-opaque, so the words sit on a solid surface
// and only a faint impression of the room comes through. Below ~0.85 the
// picture starts competing with the text; above ~0.94 it reads as a plain box
// and the backdrop may as well not be there.
// Still luminance-driven, but over a deliberately narrow band -- at this
// strength the measurement is a refinement (a bright render gets the top of
// the range) rather than the difference between readable and not.
const BD_PANEL_MIN = 0.86, BD_PANEL_MAX = 0.92;

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

function clearBackdrop() {
  BD.signature = null;
  document.body.classList.remove("has-backdrop");
  if (BD.layers) for (const layer of BD.layers) layer.classList.remove("on");
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
    layers[BD.front].classList.remove("on");
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
  if (state.status === "error") throw new Error(state.error || "generation failed");
  if (state.status === "pending") throw new Error("still generating after several minutes");
  return state;
}

function generateBackdrop(turnId, signature) {
  if (BD.inflight.has(signature)) return BD.inflight.get(signature);
  backdropWorking(true);
  const job = api("POST", `/api/turns/${turnId}/backdrop`, {})
    .then(res => awaitBackdrop(turnId, signature, res))
    .then(res => {
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
      // Give up on this picture for the session rather than retrying on
      // every scroll: whatever failed (no credit, provider down, a room
      // with nothing to depict) will fail again the same way.
      BD.failed.add(signature);
      toast("Backdrop: " + (error?.message || "generation failed"), "err");
      return null;
    })
    .finally(() => {
      BD.inflight.delete(signature);
      if (!BD.inflight.size) backdropWorking(false);
    });
  BD.inflight.set(signature, job);
  return job;
}

async function backdropForTurn(turnId) {
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

  if (!state.signature) { BD.wanted = null; clearBackdrop(); return; }
  BD.wanted = state.signature;
  if (state.ready && state.url) { showBackdrop(state.url, state.signature); return; }
  // A miss. Free viewers see the previous room stay up rather than a blank
  // screen; only an enabled, configured install pays to fill it in.
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
    showBackdrop(generated.url, generated.signature);
  }
}

// Called from the scroll observer in chat.js, which fires on every
// intersection change -- coalesce, or a flick of the wheel becomes a dozen
// requests for turns the reader never stopped at.
function backdropOnVisibleTurn(turnId) {
  clearTimeout(BD.timer);
  BD.timer = setTimeout(() => backdropForTurn(turnId), 220);
}

// Turn content (and so its room) can change under us on reroll, edit or
// branch, and renderChat() is where that surfaces.
function backdropResetForRender() {
  BD.byTurn.clear();
  clearTimeout(BD.timer);
  // Opening a different story (or none) must not leave the previous story's
  // room on screen. The observer would eventually correct it, but only once a
  // turn scrolls into view -- an empty chat has none, so it never would.
  if (BD.chatId !== S.chatId) {
    BD.chatId = S.chatId;
    BD.wanted = null;
    clearBackdrop();
  }
  if (!S.chatId) clearBackdrop();
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
