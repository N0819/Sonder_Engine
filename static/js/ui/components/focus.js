const FOCUSABLE = [
  "a[href]", "button:not([disabled])", "input:not([disabled])",
  "select:not([disabled])", "textarea:not([disabled])", "[tabindex]:not([tabindex='-1'])",
].join(",");

export function focusableElements(container) {
  return [...container.querySelectorAll(FOCUSABLE)].filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
}

export function containFocus(container, event) {
  if (event.key !== "Tab") return;
  const items = focusableElements(container);
  if (!items.length) {
    event.preventDefault();
    container.focus();
    return;
  }
  const first = items[0];
  const last = items.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function restoreFocus(opener) {
  if (opener instanceof HTMLElement && opener.isConnected && !opener.hasAttribute("disabled")) opener.focus();
}
