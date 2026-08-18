// The extension's own routes, wrapped so the view never builds a URL.
//
// A separate file on purpose: this extension exists to demonstrate a module
// GRAPH, which is the thing a classic `ui.js` entry cannot express. Relative
// imports resolve against `/api/extensions/overlay-demo/asset/ui/`, so this
// file is fetched by the browser exactly where it sits in the directory.

export const EXTENSION_ID = "overlay-demo";

export function readFrame(sonder) {
  return sonder.call(EXTENSION_ID, "GET", "/x/frame");
}

export function writeFrame(sonder, frame) {
  return sonder.call(EXTENSION_ID, "POST", "/x/frame", { frame });
}
