export function createRovingFocus(container, {
  itemSelector = "[role='tab']",
  orientation = "horizontal",
  activate = true,
  onActivate = () => {},
} = {}) {
  if (!(container instanceof HTMLElement)) throw new TypeError("A roving-focus container is required.");

  const items = () => [...container.querySelectorAll(itemSelector)].filter((item) => !item.hasAttribute("disabled"));
  const select = (item, shouldActivate = activate) => {
    for (const candidate of items()) candidate.tabIndex = candidate === item ? 0 : -1;
    item.focus();
    if (shouldActivate) onActivate(item);
  };
  const onKeydown = (event) => {
    const available = items();
    const current = available.indexOf(document.activeElement);
    if (current < 0) return;
    const previous = orientation === "vertical" ? "ArrowUp" : "ArrowLeft";
    const next = orientation === "vertical" ? "ArrowDown" : "ArrowRight";
    let target = null;
    if (event.key === previous) target = available[(current - 1 + available.length) % available.length];
    if (event.key === next) target = available[(current + 1) % available.length];
    if (event.key === "Home") target = available[0];
    if (event.key === "End") target = available.at(-1);
    if (!target) return;
    event.preventDefault();
    select(target);
  };

  const available = items();
  if (available.length && !available.some((item) => item.tabIndex === 0)) available[0].tabIndex = 0;
  container.addEventListener("keydown", onKeydown);
  return Object.freeze({ select, destroy: () => container.removeEventListener("keydown", onKeydown) });
}

export function connectTabs(tablist) {
  const activate = (tab) => {
    const tabs = [...tablist.querySelectorAll("[role='tab']")];
    for (const candidate of tabs) {
      const selected = candidate === tab;
      candidate.setAttribute("aria-selected", String(selected));
      const panel = document.getElementById(candidate.getAttribute("aria-controls"));
      if (panel) panel.hidden = !selected;
    }
  };
  return createRovingFocus(tablist, { itemSelector: "[role='tab']", onActivate: activate });
}
