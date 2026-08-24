export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

import { createOverlayController } from "../../ui/components/overlay.js?release=alpha98-ui15-5b0f039aae29";

export function createResponsiveDrawer(options = {}) {
  const documentRef = options.document || document;
  const root = options.root || documentRef.documentElement;
  const surface = options.surface;
  const overlayHost = options.overlayHost;
  if (!(surface instanceof HTMLElement) || !(overlayHost instanceof HTMLElement)) {
    throw new TypeError("A drawer surface and overlay host are required.");
  }
  const home = surface.parentElement;
  const overlayElement = documentRef.createElement("div");
  overlayElement.className = "ui-overlay ui-shell__context-overlay";
  overlayElement.hidden = true;
  overlayHost.append(overlayElement);
  let syncing = false;
  const overlay = createOverlayController(overlayElement, {
    backgroundRoot: overlayHost.parentElement,
    onClose: reason => {
      if (!syncing && reason !== "layout-sync") options.onRequestClose?.(reason);
    },
  });

  const atHome = () => {
    if (surface.parentElement !== home) home.insertBefore(surface, overlayHost);
  };
  const setMode = mode => {
    syncing = true;
    root.dataset.contextMode = mode;
    if (mode === "overlay") {
      if (surface.parentElement !== overlayElement) overlayElement.append(surface);
      surface.hidden = false;
      surface.setAttribute("role", "dialog");
      surface.setAttribute("aria-modal", "true");
      overlay.show();
    } else {
      overlay.close("layout-sync");
      atHome();
      surface.removeAttribute("aria-modal");
      surface.setAttribute("role", "complementary");
      surface.hidden = mode === "closed";
    }
    syncing = false;
  };

  return Object.freeze({
    setMode,
    teardown() {
      syncing = true;
      overlay.destroy();
      atHome();
      surface.hidden = true;
      overlayElement.remove();
      syncing = false;
    },
  });
}
