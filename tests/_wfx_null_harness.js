// Evaluate weather-fx.js under node with the smallest browser stubs its
// null path touches, then call weatherFxApply(null) -- what backdrops.js does
// on every app boot and on every story switch.
const fs = require("fs");

function classList() {
  const set = new Set();
  return { add: c => set.add(c), remove: c => set.delete(c),
           contains: c => set.has(c), toggle: c => set.add(c) };
}

function element() {
  const el = {
    classList: classList(), style: {}, dataset: {}, children: [],
    textContent: "", innerHTML: "",
    appendChild(c) { el.children.push(c); return c; },
    removeChild(c) { return c; },
    remove() {}, querySelector: () => null, querySelectorAll: () => [],
    addEventListener() {}, removeEventListener() {},
    getBoundingClientRect: () => ({ width: 800, height: 600, top: 0, left: 0 }),
    animate: () => ({ cancel() {}, finish() {}, onfinish: null }),
    getAnimations: () => [],
  };
  return el;
}

const doc = {
  body: element(),
  documentElement: element(),
  createElement: () => element(),
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener() {}, removeEventListener() {},
  hidden: false, visibilityState: "visible",
};

global.document = doc;
global.window = {
  matchMedia: () => ({ matches: false, addEventListener() {},
                       removeEventListener() {}, addListener() {},
                       removeListener() {} }),
  requestAnimationFrame: cb => 1,
  cancelAnimationFrame() {},
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
  addEventListener() {}, removeEventListener() {},
  setTimeout, clearTimeout, setInterval, clearInterval,
};
for (const k of Object.keys(global.window)) {
  if (global[k] === undefined) global[k] = global.window[k];
}
global.matchMedia = global.window.matchMedia;
global.navigator = { userAgent: "node", hardwareConcurrency: 4 };
global.CSS = { supports: () => true };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };

const src = fs.readFileSync(process.argv[2], "utf8");
const out = { loaded: false, threw: null };
// The file is "use strict", so its declarations stay inside the eval scope and
// never reach the global object. The calls have to be appended to the source
// so they run in the scope that declares them.
const probe = src + `
try {
  weatherFxApply(null);          // the boot / story-switch call
  weatherFxApply(undefined);     // the same thing, spelled the other way
  globalThis.__wfxOk = true;
} catch (e) { globalThis.__wfxErr = String((e && e.message) || e); }
`;
try {
  (0, eval)(probe);
  out.loaded = true;
} catch (e) {
  out.threw = "load: " + String((e && e.message) || e);
}
if (!out.threw && globalThis.__wfxErr) out.threw = globalThis.__wfxErr;
out.applied = globalThis.__wfxOk === true;
console.log(JSON.stringify(out));
