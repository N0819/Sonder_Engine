const ROUTE_FOCUS_CLASS = "ui-route-focus-target";

const INTERACTIVE_SELECTOR = [
  "a[href]",
  "button",
  "input",
  "select",
  "textarea",
  "summary",
  "[contenteditable='true']",
  "[role='button']",
  "[role='link']",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function focusRouteTarget(target, options = {}) {
  if (!(target instanceof HTMLElement)) return false;
  if (target.matches(INTERACTIVE_SELECTOR)) {
    target.focus({ preventScroll: options.preventScroll !== false });
    return document.activeElement === target;
  }

  const clear = () => target.classList.remove(ROUTE_FOCUS_CLASS);
  target.classList.add(ROUTE_FOCUS_CLASS);
  target.addEventListener("blur", clear, { once: true });
  target.focus({ preventScroll: options.preventScroll !== false });
  if (document.activeElement === target) return true;
  target.removeEventListener("blur", clear);
  clear();
  return false;
}
