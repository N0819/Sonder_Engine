export function createAnnouncer({ root = document.body, politeness = "polite" } = {}) {
  const region = document.createElement("div");
  region.className = "ui-sr-only";
  region.setAttribute("role", "status");
  region.setAttribute("aria-live", politeness);
  region.setAttribute("aria-atomic", "true");
  root.append(region);
  let lastMessage = "";
  let clearHandle = 0;

  function announce(message) {
    const next = String(message || "").trim();
    if (!next || next === lastMessage) return false;
    lastMessage = next;
    clearTimeout(clearHandle);
    region.textContent = "";
    requestAnimationFrame(() => { region.textContent = next; });
    clearHandle = window.setTimeout(() => { lastMessage = ""; }, 1200);
    return true;
  }

  return Object.freeze({ announce, destroy() { clearTimeout(clearHandle); region.remove(); } });
}
