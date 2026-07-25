// Scene backdrops (EXPERIMENTAL): the room the player is standing in, rendered
// behind the chat column.
//
// Three things this has to get right to be usable rather than merely pretty:
//
//   1. Legibility is measured, not assumed. Every generated image has
//      different brightness, so the scrim behind the text is derived from the
//      image's actual luminance in the band where the words sit -- sampled on
//      a tiny offscreen canvas -- rather than from a fixed opacity that will be
//      too dark for one picture and too weak for the next.
//   2. Scrolling back through the log moves through earlier LOCATIONS, so the
//      backdrop follows the turn you are actually looking at and crossfades
//      between rooms. It reuses the existing most-visible-turn observer rather
//      than adding a second one.
//   3. Nothing here is required. With no image model configured, no images
//      generated, or the whole feature switched off, the chat renders exactly
//      as it always has.

const BACKDROP = {
  enabled: false,
  bySignature: new Map(),   // signature -> {status, room_name}
  byTurn: new Map(),        // turn idx  -> signature
  current: null,
  requested: new Set(),
  luminance: new Map(),     // signature -> 0..1 measured behind the text
};

function backdropUrl(sig) {
  return `/api/chats/${S.chatId}/backdrops/${sig}.png`;
}

// The text column occupies the middle of the viewport, so only that band
// matters for legibility -- a bright sky at the top of the picture is
// irrelevant if the words sit over a dark floor.
function measureLuminance(url) {
  return new Promise(resolve => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      try {
        const c = document.createElement("canvas");
        c.width = 32; c.height = 32;
        const ctx = c.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, 32, 32);
        // Rows 8..24 of 32 == the middle half, where the column sits.
        const { data } = ctx.getImageData(0, 8, 32, 16);
        let sum = 0, n = 0;
        for (let i = 0; i < data.length; i += 4) {
          // Rec. 709 luma: green dominates perceived brightness, so a plain
          // channel average would call a saturated green wall "dark".
          sum += (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255;
          n++;
        }
        resolve(n ? sum / n : 0.5);
      } catch { resolve(0.5); }   // tainted canvas etc. -- assume mid
    };
    img.onerror = () => resolve(0.5);
    img.src = url;
  });
}

function applyContrast(lum) {
  const root = document.documentElement;
  // A bright backdrop needs a heavier scrim to keep light text readable; a
  // dark one needs almost none. Clamped so the picture never disappears
  // entirely and never stops being a background.
  const scrim = Math.min(0.82, Math.max(0.35, 0.30 + lum * 0.62));
  root.style.setProperty("--backdrop-scrim", scrim.toFixed(3));
  // Past roughly mid-grey, dark text on a light scrim reads better.
  root.style.setProperty("--backdrop-ink", lum > 0.62 ? "#10141c" : "");
  document.body.classList.toggle("backdrop-light", lum > 0.62);
}

async function showBackdrop(sig) {
  if (!BACKDROP.enabled || !sig || sig === BACKDROP.current) return;
  const entry = BACKDROP.bySignature.get(sig);
  if (!entry || entry.status !== "ready") return;

  const layer = document.getElementById("backdrop-layer");
  if (!layer) return;
  BACKDROP.current = sig;
  const url = backdropUrl(sig);

  let lum = BACKDROP.luminance.get(sig);
  if (lum === undefined) {
    lum = await measureLuminance(url);
    BACKDROP.luminance.set(sig, lum);
  }
  if (BACKDROP.current !== sig) return;   // scrolled away mid-measure
  applyContrast(lum);

  // Crossfade: the outgoing image stays until the incoming one is painted, so
  // a slow decode shows the previous room rather than a flash of empty page.
  const incoming = document.createElement("div");
  incoming.className = "backdrop-img";
  incoming.style.backgroundImage = `url("${url}")`;
  layer.append(incoming);
  requestAnimationFrame(() => {
    incoming.classList.add("on");
    const stale = [...layer.querySelectorAll(".backdrop-img")].slice(0, -1);
    setTimeout(() => stale.forEach(n => n.remove()), 900);
  });
}

async function loadBackdrops() {
  BACKDROP.bySignature.clear();
  BACKDROP.byTurn.clear();
  BACKDROP.current = null;
  const layer = document.getElementById("backdrop-layer");
  if (layer) layer.innerHTML = "";
  document.body.classList.remove("has-backdrop", "backdrop-light");
  if (!S.chatId || !BACKDROP.enabled) return;

  let data;
  try { data = await api("GET", `/api/chats/${S.chatId}/backdrops`); }
  catch { return; }
  if (!data || !data.configured) return;

  for (const e of data.backdrops || []) {
    BACKDROP.byTurn.set(e.turn, e.signature);
    BACKDROP.bySignature.set(e.signature, { status: e.status, room_name: e.room_name });
  }
  document.body.classList.add("has-backdrop");

  // Only ask for the room the reader is actually in. Generating every room in
  // the history up front would be a burst of paid calls for pictures nobody
  // may scroll back to.
  const turns = [...BACKDROP.byTurn.keys()].sort((a, b) => b - a);
  if (turns.length) await ensureBackdrop(turns[0]);
}

async function ensureBackdrop(turn) {
  const sig = BACKDROP.byTurn.get(turn);
  if (!sig) return;
  const entry = BACKDROP.bySignature.get(sig);
  if (entry && entry.status === "ready") { showBackdrop(sig); return; }
  if (BACKDROP.requested.has(sig)) return;
  BACKDROP.requested.add(sig);
  try {
    const out = await api("POST", `/api/chats/${S.chatId}/backdrops/generate`, { turn });
    if (out.status === "ready") {
      BACKDROP.bySignature.set(sig, { ...entry, status: "ready" });
      showBackdrop(sig);
      return;
    }
    // Pending: poll gently. Generation runs ~10-20s.
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 2000));
      const fresh = await api("GET", `/api/chats/${S.chatId}/backdrops`);
      const hit = (fresh.backdrops || []).find(e => e.signature === sig);
      if (hit && hit.status === "ready") {
        BACKDROP.bySignature.set(sig, { ...entry, status: "ready" });
        showBackdrop(sig);
        return;
      }
      if (hit && hit.status === "error") break;
    }
  } catch { /* a backdrop is decoration; never surface a failure as an error */ }
  finally { BACKDROP.requested.delete(sig); }
}

// Called by chat.js's existing most-visible-turn observer, so scrolling back
// through the log walks back through the rooms it happened in.
function backdropForTurn(turn) {
  if (!BACKDROP.enabled || turn == null) return;
  const sig = BACKDROP.byTurn.get(turn);
  if (!sig) return;
  const entry = BACKDROP.bySignature.get(sig);
  if (entry && entry.status === "ready") showBackdrop(sig);
  else ensureBackdrop(turn);
}

function setBackdropEnabled(on) {
  BACKDROP.enabled = !!on;
  localStorage.setItem("backdrops_enabled", on ? "1" : "0");
  if (!on) {
    document.body.classList.remove("has-backdrop", "backdrop-light");
    const layer = document.getElementById("backdrop-layer");
    if (layer) layer.innerHTML = "";
    BACKDROP.current = null;
  } else {
    loadBackdrops();
  }
}

BACKDROP.enabled = localStorage.getItem("backdrops_enabled") === "1";


function syncBackdropButton() {
  const btn = document.getElementById("b-backdrop");
  if (!btn) return;
  btn.textContent = "Backdrop: " + (BACKDROP.enabled ? "ON" : "OFF");
  btn.classList.toggle("on", BACKDROP.enabled);
}

function initBackdropUI() {
  const btn = document.getElementById("b-backdrop");
  if (!btn) return;
  btn.onclick = () => { setBackdropEnabled(!BACKDROP.enabled); syncBackdropButton(); };
  syncBackdropButton();
}

document.addEventListener("DOMContentLoaded", initBackdropUI);
