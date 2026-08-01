"use strict";
// ---- Weather effects ----
// Rain, snow and lightning drawn over the story for rooms that can actually
// see the sky. The engine decides that (weather.weather_for_room); this file
// only draws what it is handed, and draws nothing at all for a room whose
// `weather_visible` is false -- which is most rooms, most of the time.
//
// HOW IT DRAWS, and why it is not a particle system. This used to be
// tsParticles: a full-viewport canvas, cleared and re-rasterised every frame
// from JavaScript. That is main-thread work plus a full-screen fill, thirty to
// sixty times a second, for scenery -- and on a HiDPI laptop panel with an
// integrated GPU it was the most expensive thing the app did while simply
// sitting there raining.
//
// What replaced it costs almost nothing: ONE small seamless tile, drawn once
// into a canvas and handed to CSS as a repeating background, then moved with a
// `transform` animation. Transforms on a composited layer run on the
// compositor -- no JavaScript per frame, no repaint, no main-thread work at
// all. It is the same class of operation as scrolling a page, which is what
// graphics hardware is built for.
//
// The tile is GENERATED rather than downloaded, for three reasons: a drawn
// tile can be made seamless by construction (wrap every streak that crosses an
// edge, and the pattern cannot show a grid), it needs no licence or credit
// line for something that is twenty lines of canvas, and it keeps the app free
// of another vendored dependency.
//
// Depth comes from three layers at different tile scales, speeds and
// opacities, which is also what hides the loop: each layer repeats on its own
// period, so the combination does not visibly cycle.
//
// The LIGHTNING is not part of that. A flash is not falling weather, and it
// has to hand a timestamp to the audio layer so the thunder can arrive after
// it by a distance-shaped delay -- so it stays a DOM overlay and a timer.
//
// Three properties this preserves:
//
// 1. It never competes with the prose. The layer sits at low opacity over the
//    story, the marks are small and low-contrast, and the whole thing is
//    skipped outright under prefers-reduced-motion.
// 2. It costs nothing when there is no weather. No layers exist, and no timer
//    runs, until a room with a visible sky turns up; leaving one tears them
//    down rather than pausing them.
// 3. Thunder follows lightning, never leads it. The flash is drawn first and
//    the sound is scheduled from it -- the gap is the distance, which is the
//    whole reason the effect reads as a storm rather than as a glitch.

const WFX = {
  host: null,           // the fixed layer everything is drawn into
  tilt: null,           // the rotated wrapper that gives wind its slant
  layers: [],           // the animated background-tiled divs
  kind: "",             // the shape key: "rain|heavy|breeze|1" etc, "" for none
  weather: null,        // the scoped weather dict from the backdrop payload
  tiles: new Map(),     // cache of generated tiles, keyed by kind+size+density
  flashEl: null,
  flashTimer: null,
  boltEl: null,          // the SVG host for a full-render strike
  boltTimer: null,
};

// Marks per tile, tuned against the text they pass over rather than against
// realism: enough to read as weather at a glance, few enough that the words
// stay the thing you are looking at.
// Marks per REFERENCE TILE, not per tile. Each layer scales this by its own
// area (see weatherFxBuild), because three tiles of different sizes carrying
// the same count are three different densities -- which is half of why the
// repeat was findable.
const WFX_DENSITY = { light: 9, moderate: 18, heavy: 34 };
const WFX_DENSITY_TILE = 110;
// Seconds for one layer to travel exactly one tile. Rain falls; snow drifts.
const WFX_FALL_S = {
  // Rain at roughly 1.7x the original pace: the first pass read as drifting
  // rather than falling, because a raindrop crosses a window far faster than
  // anything else the eye is used to tracking.
  rain: { light: 0.88, moderate: 0.62, heavy: 0.44 },
  snow: { light: 9, moderate: 7, heavy: 5.5 },
};
// The slant, in degrees. Applied by rotating the whole layer stack, so the
// marks and their travel stay parallel -- drops sliding sideways across their
// own direction is the tell that weather is a texture rather than falling.
const WFX_TILT = { still: 0, breeze: 7, wind: 15, gale: 24 };
// A storm flashes every few seconds, not every few frames.
const WFX_FLASH_GAP = [4200, 14000];
// How often a flash is close enough to draw the channel itself rather than
// just light the sky. Deliberately a minority of strikes: a bolt every time
// would be a lightshow, and the wash is what most lightning actually looks
// like from inside a scene.
const WFX_BOLT_CHANCE = 0.22;
// How long after a flash the thunder arrives. A near strike is almost
// immediate; a distant one takes seconds, which is what makes the sky feel big.
const WFX_THUNDER_DELAY = [700, 6500];
// How violently the sky is allowed to be drawn, from the story's own Genre &
// tone setting. Density and fall speed both scale, so calm weather is a hint
// at the window and catastrophic weather is something you would not walk into.
// Multiplies what the room already decided -- reach and intensity still apply
// underneath, so a sheltered lane in a catastrophic storm is still sheltered.
const WFX_SEVERITY = {
  calm: { density: 0.45, speed: 0.8, opacity: 0.7 },
  seasonal: { density: 1, speed: 1, opacity: 1 },
  harsh: { density: 1.5, speed: 1.25, opacity: 1.15 },
  catastrophic: { density: 2.2, speed: 1.6, opacity: 1.3 },
};

// The three layers: tile size in CSS pixels, how much faster or slower than the
// base fall, and how strongly it reads. Near ones are bigger, faster, clearer.
const WFX_LAYERS = [
  { size: 150, speed: 1.35, opacity: 0.85 },
  { size: 110, speed: 1.0, opacity: 0.6 },
  { size: 80, speed: 0.72, opacity: 0.4 },
];
// Snow needs bigger tiles than rain. A rain streak is a thin vertical line and
// its neighbours blur into it; a snowflake is a distinct round blob, so the eye
// finds the same little constellation repeating every 150px and reads the whole
// field as a grid. The sizes below are deliberately not multiples of each
// other, so the three layers' repeats never come back into phase.
// `sway` is how far this layer drifts sideways and `swayS` how long it takes;
// `tilt` leans it a few degrees off the stack's own angle. All three differ per
// layer and none of the periods divide each other, so the depths never fall
// back into step -- which is the whole difference between snow drifting and a
// sheet of wallpaper being pulled downward.
const WFX_LAYERS_SNOW = [
  { size: 317, speed: 1.35, opacity: 0.85, sway: 34, swayS: 8.3, tilt: -5 },
  { size: 233, speed: 1.0, opacity: 0.6, sway: 22, swayS: 11.7, tilt: 3 },
  { size: 179, speed: 0.72, opacity: 0.4, sway: 14, swayS: 15.1, tilt: -2 },
];

function weatherFxReduced() {
  return window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// A 2d canvas is all this needs now -- no OffscreenCanvas, no worker, no
// library. The old implementation had to check for `transferControlToOffscreen`
// because tsParticles THREW without it rather than degrading.
function weatherFxSupported() {
  return typeof document !== "undefined"
    && typeof document.createElement("canvas").getContext === "function";
}

function weatherFxHost() {
  if (WFX.host) return WFX.host;
  // Its own fixed layer over the app, NOT a child of #scene-backdrop. Two
  // reasons, both from the stylesheet rather than from guessing: that
  // container is opacity:0 unless a backdrop image exists, so weather would be
  // invisible on an install with no image model; and it sits at z-index 0
  // BEHIND #app, whose per-turn prose panels are ~90% opaque, so rain drawn
  // there would be hidden everywhere the reader is looking. Over the top at
  // low opacity is also the truer effect: weather between you and the scene.
  WFX.host = el("div", { id: "weather-fx", "aria-hidden": "true" });
  // Oversized and rotated: the stack has to be bigger than the window or a
  // slant would show its corners, and rotating the WRAPPER keeps every layer
  // and its travel on the same axis.
  WFX.tilt = el("div", { class: "wfx-tilt" });
  WFX.host.append(WFX.tilt);
  WFX.flashEl = el("div", { id: "weather-flash", "aria-hidden": "true" });
  WFX.boltEl = el("div", { id: "weather-bolt", "aria-hidden": "true" });
  document.body.append(WFX.host, WFX.flashEl, WFX.boltEl);
  return WFX.host;
}

// --- the tile --------------------------------------------------------------

// Deterministic, so a tile is identical between reloads and between machines:
// the scatter should look random, not BE random, or the cache below would be
// keyed to something that changes underneath it.
function weatherFxRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

// One seamless tile. Every mark that crosses an edge is drawn again on the
// opposite side, so the pattern wraps exactly -- which is what lets the layer
// be translated by precisely one tile and loop invisibly.
function weatherFxTile(kind, size, marks) {
  // Drawn at device resolution and DISPLAYED at CSS resolution. This is the
  // one place sharpness is still free: the tile is rasterised once, so a
  // denser texture costs a little memory and nothing per frame -- unlike the
  // canvas this replaced, where every extra pixel was redrawn thirty times a
  // second. Streaks stay crisp on a HiDPI panel at no running cost.
  // Rain streaks are thin lines and stay crisp only at device resolution.
  // Snow is a soft round blob that gains nothing above 2x -- and snow tiles
  // are twice the size, so the same raster ratio would cost four times the
  // memory for a sharpness nobody can see.
  const cap = kind === "snow" ? 2 : 3;
  const ratio = Math.min(cap, Math.max(1, window.devicePixelRatio || 1));
  const key = kind + ":" + size + ":" + marks + ":" + ratio;
  if (WFX.tiles.has(key)) return WFX.tiles.get(key);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = Math.round(size * ratio);
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const rand = weatherFxRandom(size * 7919 + marks * 104729 + (kind === "snow" ? 7 : 3));

  for (let i = 0; i < marks; i++) {
    const x = rand() * size, y = rand() * size;
    const alpha = 0.25 + rand() * 0.5;
    // Drawn at four offsets so anything overhanging an edge continues on the
    // far side. Cheap: it happens once per tile, not once per frame.
    for (const [dx, dy] of [[0, 0], [-size, 0], [0, -size], [-size, -size]]) {
      if (kind === "snow") {
        ctx.beginPath();
        ctx.fillStyle = "rgba(238,243,251," + alpha.toFixed(3) + ")";
        // A wide spread of sizes, most of them small. Flakes of one size are
        // a texture; flakes of many sizes are weather -- and the variation
        // does as much to hide the repeat as the bigger tile does.
        ctx.arc(x + dx, y + dy, 0.6 + rand() * rand() * 3.2, 0, Math.PI * 2);
        ctx.fill();
      } else {
        const length = size * (0.06 + rand() * 0.09);
        ctx.beginPath();
        ctx.strokeStyle = "rgba(200,214,235," + alpha.toFixed(3) + ")";
        ctx.lineWidth = 1;
        ctx.moveTo(x + dx, y + dy);
        ctx.lineTo(x + dx, y + dy + length);
        ctx.stroke();
      }
    }
  }
  const url = canvas.toDataURL("image/png");
  WFX.tiles.set(key, url);
  return url;
}

// How much of the weather is in view here: all of it in the open, the edges of
// it from under cover. Older payloads carry no reach and mean "all of it".
function weatherFxReach(weather) {
  const reach = (weather || {}).visible_reach;
  return typeof reach === "number" ? Math.min(1, Math.max(0, reach)) : 1;
}

// --- the layers ------------------------------------------------------------

function weatherFxBuild(kind, weather) {
  const host = weatherFxHost();
  const reach = weatherFxReach(weather);
  const intensity = weather.intensity in WFX_DENSITY ? weather.intensity : "moderate";
  const severity = WFX_SEVERITY[weather.severity] || WFX_SEVERITY.seasonal;
  // Under cover you see the edges of it, so the marks thin out rather than the
  // weather stopping.
  const density = WFX_DENSITY[intensity] * reach * severity.density;
  const fall = (WFX_FALL_S[kind] || WFX_FALL_S.rain)[intensity] / severity.speed;
  const specs = kind === "snow" ? WFX_LAYERS_SNOW : WFX_LAYERS;

  weatherFxClearLayers();
  WFX.tilt.style.transform = "rotate(" + (WFX_TILT[weather.wind] || 0) + "deg)";

  for (const spec of specs) {
    const layer = el("div", { class: "wfx-layer" });
    // Snow gets a wrapper carrying the sideways drift, so the two transforms
    // compose. Rain does not: it falls hard and straight, and swaying it would
    // be a lie about how rain behaves.
    const drift = spec.sway ? el("div", { class: "wfx-drift" }) : null;
    if (drift) {
      drift.style.setProperty("--wfx-sway", spec.sway + "px");
      drift.style.animationDuration = spec.swayS + "s";
      // A negative delay starts each layer mid-sway instead of all three
      // beginning at the same edge of their arc.
      drift.style.animationDelay = (-spec.swayS * specs.indexOf(spec) * 0.37).toFixed(2) + "s";
      // The `rotate` PROPERTY, not a transform: the sway animates `transform`,
      // and an inline transform here would simply be overridden by it. `rotate`
      // is an independent property and composes with the animated transform.
      if (spec.tilt) drift.style.rotate = spec.tilt + "deg";
    }
    // Scaled by AREA, so a 317px tile is not the same handful of flakes spread
    // thin. Never below two, or a tile reads as empty.
    const marks = Math.max(2, Math.round(
      density * (spec.size * spec.size) /
      (WFX_DENSITY_TILE * WFX_DENSITY_TILE)));
    layer.style.backgroundImage = "url(" + weatherFxTile(kind, spec.size, marks) + ")";
    layer.style.backgroundSize = spec.size + "px " + spec.size + "px";
    // Each layer starts somewhere different inside its own tile, so the three
    // repeats do not line up into one visible lattice.
    layer.style.backgroundPosition =
      Math.round(spec.size * 0.37 * specs.indexOf(spec)) + "px "
      + Math.round(spec.size * 0.61 * specs.indexOf(spec)) + "px";
    layer.style.opacity = String(Math.min(1, spec.opacity * severity.opacity));
    // Travel is exactly one tile, so the end of the animation is pixel-for-
    // pixel the start of it and the loop cannot be seen.
    layer.style.setProperty("--wfx-travel", spec.size + "px");
    layer.style.animationDuration = (fall / spec.speed).toFixed(2) + "s";
    if (drift) {
      drift.append(layer);
      WFX.tilt.append(drift);
      WFX.layers.push(drift);
    } else {
      WFX.tilt.append(layer);
      WFX.layers.push(layer);
    }
  }
  host.classList.add("on");
  document.body.classList.add("has-weather-fx");
}

function weatherFxClearLayers() {
  for (const layer of WFX.layers) layer.remove();
  WFX.layers = [];
}

// --- lifecycle -------------------------------------------------------------

function weatherFxStop() {
  WFX.kind = "";
  weatherFxClearLayers();
  clearTimeout(WFX.flashTimer);
  WFX.flashTimer = null;
  if (WFX.host) WFX.host.classList.remove("on");
  document.body.classList.remove("has-weather-fx");
}

// The engine's own answer about this room, straight from the backdrop payload.
// Everything below is a rendering decision; nothing here decides whether the
// room can see the sky.
// Whether weather can be SEEN from this room. `weather_visible` is the field
// that answers it; `sky_visible` is the older, narrower one (is the open sky
// overhead) and stays as the fallback for a payload written before the two were
// separated -- a cached turn, or a browser holding an older page.
function weatherFxVisible(weather) {
  if (!weather) return false;
  return weather.weather_visible === undefined
    ? !!weather.sky_visible : !!weather.weather_visible;
}

function weatherFxApply(weather) {
  WFX.weather = weather || null;
  const visible = weatherFxVisible(weather);
  const falling = visible && weather.precipitation !== "none";
  const kind = !falling ? ""
    : (weather.precipitation === "snow" || weather.precipitation === "sleet")
      ? "snow" : "rain";
  const storm = visible && weatherFxStormy(weather);

  if ((!kind && !storm) || weatherFxReduced() || !weatherFxSupported()) {
    weatherFxStop();
    return;
  }

  weatherFxHost().classList.add("on");
  document.body.classList.add("has-weather-fx");
  // Rebuild only when the LOOK changes. Consecutive turns in one room hand over
  // the identical weather, and rebuilding then would restart every drop
  // mid-fall. The reach is part of the look: stepping under an awning is the
  // same rain at a fraction of the density.
  const shape = kind + "|" + (weather.intensity || "") + "|" + (weather.wind || "")
    + "|" + weatherFxReach(weather) + "|" + (weather.severity || "");
  if (kind && shape !== WFX.kind) {
    WFX.kind = shape;
    weatherFxBuild(kind, weather);
  } else if (!kind && WFX.layers.length) {
    // A dry storm sky: keep the flashes, drop the falling weather.
    WFX.kind = "";
    weatherFxClearLayers();
  }
  weatherFxScheduleFlash(storm);
}

// --- lightning -------------------------------------------------------------

// Whether this sky throws lightning at all. Mirrors weather.has_lightning, and
// must keep mirroring it: a sky that flashes here with no thunder written into
// what the room hears is the worse half of the bug this came from.
//
// A snowing storm is silent unless it is THUNDERSNOW, which the engine marks on
// the sky itself -- rolled rarely by the weather drift, or declared outright by
// a beat. Derived from the precipitation instead, every blizzard would flash;
// forbidden outright, none ever could.
function weatherFxStormy(weather) {
  weather = weather || {};
  if (weather.sky !== "storm") return false;
  const snowing = weather.precipitation === "snow"
    || weather.precipitation === "sleet";
  return !snowing || !!weather.thundersnow;
}

function weatherFxScheduleFlash(storm) {
  clearTimeout(WFX.flashTimer);
  WFX.flashTimer = null;
  if (!storm) return;
  const gap = WFX_FLASH_GAP[0] + Math.random() * (WFX_FLASH_GAP[1] - WFX_FLASH_GAP[0]);
  WFX.flashTimer = setTimeout(() => {
    weatherFxFlash();
    // Lightning lights up an awning as readily as an open square.
    weatherFxScheduleFlash(weatherFxStormy(WFX.weather)
      && weatherFxVisible(WFX.weather));
  }, gap);
}

function weatherFxFlash() {
  const flash = WFX.flashEl;
  if (!flash) return;
  // Ordinarily a radiating wash and nothing more: most lightning is seen as
  // the SKY lighting up, not as a drawn channel, and a wash asks nothing of
  // the picture underneath -- which is a photograph of a room this code knows
  // nothing about.
  flash.classList.remove("flash");
  void flash.offsetWidth;              // restart the animation
  flash.classList.add("flash");
  // ...but a strike near enough to see gets the full render. Gated on
  // `sky_visible`, NOT on `weather_visible`: you can watch a storm from under
  // an awning, and the flash of it reaches you there, but the channel itself
  // is in the open sky. A bolt drawn inside a room, or under the very cover
  // the reader stepped beneath to escape the rain, is simply wrong.
  if (weatherFxOpenSky(WFX.weather) && Math.random() < WFX_BOLT_CHANCE) {
    weatherFxBolt();
  }
  weatherFxThunder();
}

// Is the sky itself overhead here? The narrower of the two visibility
// questions -- see weather.py, which answers both separately.
function weatherFxOpenSky(weather) {
  return !!(weather && weather.sky_visible);
}

// One drawn channel, as an SVG path over the scene. Built fresh per strike and
// discarded after: lightning is never twice the same shape, and a static asset
// reused every time would be more obviously a loop than the rain is.
function weatherFxBolt() {
  if (weatherFxReduced() || !WFX.boltEl) return;
  const width = window.innerWidth || 1200;
  const height = window.innerHeight || 800;
  // Starts somewhere across the top, wanders down, and stops well short of the
  // ground: where it LANDS is in a photograph this code cannot see, so the
  // channel fades out rather than striking anything in particular.
  let x = width * (0.15 + Math.random() * 0.7);
  let y = 0;
  const steps = 5 + Math.floor(Math.random() * 4);
  const drop = (height * (0.35 + Math.random() * 0.3)) / steps;
  const points = [x.toFixed(0) + "," + y.toFixed(0)];
  const forks = [];
  for (let i = 0; i < steps; i++) {
    x += (Math.random() - 0.5) * width * 0.09;
    y += drop * (0.7 + Math.random() * 0.6);
    points.push(x.toFixed(0) + "," + y.toFixed(0));
    // The occasional branch. A single unbranched line reads as a crack in the
    // screen; two or three short spurs read as lightning.
    if (i > 0 && Math.random() < 0.4) {
      forks.push("M" + x.toFixed(0) + "," + y.toFixed(0) + "L"
        + (x + (Math.random() - 0.5) * width * 0.07).toFixed(0) + ","
        + (y + drop * 0.7).toFixed(0));
    }
  }
  WFX.boltEl.innerHTML =
    '<svg width="100%" height="100%" viewBox="0 0 ' + width + " " + height
    + '" preserveAspectRatio="none" aria-hidden="true">'
    + '<g fill="none" stroke="rgba(226,214,255,.95)" stroke-width="2.4"'
    + ' stroke-linecap="round" stroke-linejoin="round"'
    + ' style="filter:drop-shadow(0 0 7px rgba(168,146,255,.85))">'
    + '<polyline points="' + points.join(" ") + '"/>'
    + forks.map(d => '<path d="' + d + '" stroke-width="1.2"/>').join("")
    + "</g></svg>";
  WFX.boltEl.classList.remove("flash");
  void WFX.boltEl.offsetWidth;
  WFX.boltEl.classList.add("flash");
  // Torn down after the animation: an SVG left in the document is a layer the
  // compositor keeps considering forever.
  clearTimeout(WFX.boltTimer);
  WFX.boltTimer = setTimeout(() => {
    WFX.boltEl.classList.remove("flash");
    WFX.boltEl.innerHTML = "";
  }, 800);
}

// Thunder follows the flash by a delay standing in for distance. The audio
// itself belongs to ambience.js, which owns the mute and the volume -- a
// thunderclap that ignored the mute button would be the single most annoying
// thing this feature could do.
function weatherFxThunder() {
  if (typeof playAmbienceOneshot !== "function") return;
  const near = (WFX.weather || {}).intensity === "heavy" && Math.random() < 0.4;
  const delay = near
    ? WFX_THUNDER_DELAY[0]
    : WFX_THUNDER_DELAY[0] + Math.random() * (WFX_THUNDER_DELAY[1] - WFX_THUNDER_DELAY[0]);
  setTimeout(() => playAmbienceOneshot(near ? "thunder_close" : "thunder",
                                       near ? 0.9 : 0.55), delay);
}

// Called by backdrops.js on every turn it resolves, since that is where the
// room-scoped weather arrives.
function weatherFxForTurn(state) {
  weatherFxApply((state && state.weather) || null);
}

// Browsers already throttle animations in a hidden tab, but "already throttle"
// is not "definitely stopped", and the whole point of this rewrite is that the
// weather costs nothing it does not have to. Pausing outright is one line, and
// it also stops the lightning timer firing thunder at an empty room.
document.addEventListener("visibilitychange", () => {
  const paused = document.hidden;
  const state = paused ? "paused" : "running";
  for (const layer of WFX.layers) {
    layer.style.animationPlayState = state;
    // Snow animates on TWO nodes: `wfx-sway` on the drift wrapper, which is
    // what `WFX.layers` holds, and `wfx-fall` on the tile layer inside it.
    // Pausing only the entry stopped the sideways drift and left the falling
    // running, so a hidden tab still ran three infinite composited animations
    // -- the exact cost this file exists to avoid. Rain has no wrapper and no
    // descendants, so this loop is empty for it.
    for (const inner of layer.querySelectorAll(".wfx-layer")) {
      inner.style.animationPlayState = state;
    }
  }
  if (paused) {
    clearTimeout(WFX.flashTimer);
    WFX.flashTimer = null;
  } else {
    weatherFxScheduleFlash(weatherFxStormy(WFX.weather)
      && weatherFxVisible(WFX.weather));
  }
});
