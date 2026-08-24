export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

export function createFilterSheet(documentRef, options = {}) {
  const details = documentRef.createElement("details");
  details.className = "ui-filter-sheet";
  const summary = documentRef.createElement("summary");
  summary.className = "ui-button ui-button--quiet";
  summary.setAttribute("role", "button");
  summary.textContent = options.label || "Filters";
  const body = documentRef.createElement("div");
  body.className = "ui-filter-sheet__body";
  for (const child of options.children || []) {
    if (child instanceof HTMLElement) body.append(child);
  }
  details.append(summary, body);
  return Object.freeze({ element: details, summary, body });
}
