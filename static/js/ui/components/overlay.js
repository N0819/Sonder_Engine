import { containFocus, focusableElements, restoreFocus } from "./focus.js";

function setBackgroundInert(overlay, parent) {
  if (!parent) return [];
  const changed = [];
  for (const sibling of parent.children) {
    if (sibling === overlay || sibling.contains(overlay)
        || !(sibling instanceof HTMLElement)) continue;
    changed.push({ sibling, inert: sibling.inert, ariaHidden: sibling.getAttribute("aria-hidden") });
    sibling.inert = true;
    sibling.setAttribute("aria-hidden", "true");
  }
  return changed;
}

function restoreBackground(changed) {
  for (const { sibling, inert, ariaHidden } of changed) {
    sibling.inert = inert;
    if (ariaHidden === null) sibling.removeAttribute("aria-hidden");
    else sibling.setAttribute("aria-hidden", ariaHidden);
  }
}

export function createOverlayController(overlay, {
  closeOnEscape = true,
  onClose = () => {},
  backgroundRoot = overlay.parentElement,
} = {}) {
  if (!(overlay instanceof HTMLElement)) throw new TypeError("An overlay element is required.");
  const surface = overlay.querySelector("[role='dialog']") || overlay;
  let opener = null;
  let background = [];
  let open = false;

  const onKeydown = (event) => {
    containFocus(surface, event);
    if (event.key === "Escape" && closeOnEscape) {
      event.preventDefault();
      event.stopImmediatePropagation();
      close("escape");
    }
  };

  function show() {
    if (open) return;
    opener = document.activeElement;
    open = true;
    overlay.hidden = false;
    background = setBackgroundInert(overlay, backgroundRoot);
    document.documentElement.classList.add("ui-scroll-lock");
    document.addEventListener("keydown", onKeydown, true);
    const target = overlay.querySelector("[autofocus]") || focusableElements(surface)[0] || surface;
    if (!target.hasAttribute("tabindex") && target === surface) target.setAttribute("tabindex", "-1");
    target.focus();
  }

  function close(reason = "programmatic") {
    if (!open) return;
    open = false;
    overlay.hidden = true;
    document.removeEventListener("keydown", onKeydown, true);
    document.documentElement.classList.remove("ui-scroll-lock");
    restoreBackground(background);
    background = [];
    restoreFocus(opener);
    onClose(reason);
  }

  return Object.freeze({ show, close, destroy: () => close("destroy"), get isOpen() { return open; } });
}
