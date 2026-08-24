export const MODULE_RELEASE = "alpha98-ui5-98f796584158";

import { buildLivedLocationRequest, mountLivedLocationFields } from "../lived-location.js?release=alpha98-ui5-98f796584158";
import { button, element, markData } from "./shared.js?release=alpha98-ui5-98f796584158";

// UI_CATALOG_START: Charter inspection copy.
const COPY = Object.freeze({
  title: "Institutions and upkeep",
  empty: "No institutions have been prepared for this Story.",
  explanation: "Institutions continue their authored work on the world clock. Witnessing, telling, reading, and carrying information are not settings; they happen through bodies and routes in the story.",
  diagnostics: "Load Charter diagnostics",
  diagnosticsEmpty: "Diagnostics have not been loaded.",
  diagnosticsLoading: "Loading Charter diagnostics…",
  diagnosticsUnavailable: "Diagnostics are unavailable.",
  unavailable: "Institution information is unavailable.",
  generationUnavailable: "Location preparation is unavailable.",
  generating: "Preparing lived location…",
  generate: "Prepare lived location",
  another: "Prepare another lived location",
  locationHistory: "Location and history",
  loreLabel: "Lore for lived location",
  chooseLore: "Choose Story Lore",
  chooseFirst: "Choose Story Lore and describe the location first.",
  failed: "The lived location could not be prepared.",
  institution: "institution",
  residentBody: "resident body",
  residentBodies: "resident bodies",
  historyRoute: "Character history route",
});
// UI_CATALOG_END

function itemsOf(data) {
  const items = data?.charters?.items;
  return items && typeof items === "object" ? Object.entries(items) : [];
}

function bodyCount(items) {
  return items.reduce((total, [, value]) => total + Object.keys(value?.bodies || value?.residents || {}).length, 0);
}

function plural(count, singular, pluralValue = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralValue}`;
}

export function mountCharterSection(options = {}) {
  const { services, scope, chatId, document: documentRef } = options;
  let data = options.data || {};
  const lorebooks = Array.isArray(options.lorebooks) ? options.lorebooks : [];
  const root = element(documentRef, "section", "ui-tool-card ui-charters");
  const render = () => {
    root.replaceChildren(
      element(documentRef, "h4", "ui-heading ui-heading--4", COPY.title),
      element(documentRef, "p", "ui-muted", COPY.explanation),
    );
    if (options.unavailable) {
      const unavailable = element(documentRef, "p", "ui-muted", COPY.unavailable);
      unavailable.dataset.state = "unavailable";
      unavailable.setAttribute("role", "status");
      root.append(unavailable);
      services.localizer.localize(root);
      return;
    }
    const items = itemsOf(data);
    const routes = Object.keys(data.character_history_routes || {}).length;
    const summary = element(documentRef, "p", "ui-charters__summary", `${plural(items.length, "institution")} · ${plural(bodyCount(items), "resident body", "resident bodies")} · ${plural(routes, "Character history route")}`);
    root.append(summary);
    if (!items.length) root.append(element(documentRef, "p", "ui-muted", COPY.empty));
    else {
      const ledger = element(documentRef, "div", "ui-charters__ledger");
      items.forEach(([key, charter]) => {
        const row = element(documentRef, "div", "ui-charters__row");
        row.append(
          markData(element(documentRef, "strong", "", charter?.name || charter?.title || key)),
          element(documentRef, "span", "ui-muted", plural(Object.keys(charter?.bodies || charter?.residents || {}).length, "resident body", "resident bodies")),
        );
        ledger.append(row);
      });
      root.append(ledger);
    }
    (data.warnings || []).forEach(message => {
      const warning = markData(element(documentRef, "p", "ui-charters__warning", String(message)));
      warning.setAttribute("role", "status");
      root.append(warning);
    });
    const diagnostics = element(documentRef, "details", "ui-charters__diagnostics");
    diagnostics.append(element(documentRef, "summary", "ui-button ui-button--quiet", COPY.diagnostics));
    const diagnosticBody = element(documentRef, "pre", "ui-charters__raw", "Diagnostics have not been loaded.");
    diagnostics.addEventListener("toggle", async () => {
      if (!diagnostics.open || diagnostics.dataset.loaded) return;
      diagnostics.dataset.loaded = "loading";
      diagnosticBody.textContent = "Loading Charter diagnostics…";
      try {
        const result = await scope.run("GET", "charter-diagnostics", `/api/chats/${chatId}/charters/diagnostics`);
        if (!scope.isLive() || !result) return;
        diagnosticBody.textContent = JSON.stringify(result, null, 2);
        diagnostics.dataset.loaded = "true";
      } catch (error) {
        diagnosticBody.textContent = error?.userMessage || error?.message || "Diagnostics are unavailable.";
        delete diagnostics.dataset.loaded;
      }
    });
    diagnostics.append(diagnosticBody);
    root.append(diagnostics);

    if (options.generationUnavailable) {
      const unavailable = element(documentRef, "p", "ui-muted", COPY.generationUnavailable);
      unavailable.dataset.state = "unavailable";
      unavailable.setAttribute("role", "status");
      root.append(unavailable);
      services.localizer.localize(root);
      return;
    }

    const generation = element(documentRef, "details", "ui-charters__generation");
    generation.append(element(documentRef, "summary", "ui-button ui-button--quiet", "Prepare another lived location"));
    const controls = element(documentRef, "div", "ui-charters__generation-body");
    let value = { enabled: true, brief: "", horizonHours: 168, characterHistories: [] };
    mountLivedLocationFields({ document: documentRef, target: controls, value, title: "Location and history", onChange(next) { value = next; } });
    const lore = documentRef.createElement("select");
    lore.className = "ui-select";
    lore.setAttribute("aria-label", "Lore for lived location");
    const blank = element(documentRef, "option", "", "Choose Story Lore");
    blank.value = "";
    lore.append(blank);
    lorebooks.forEach(book => {
      const option = markData(element(documentRef, "option", "", book.name || `Lore ${book.id}`));
      option.value = String(book.id);
      lore.append(option);
    });
    const status = element(documentRef, "p", "ui-muted");
    status.setAttribute("role", "status");
    const run = button(documentRef, COPY.generate, "ui-button ui-button--primary");
    run.addEventListener("click", async () => {
      const request = buildLivedLocationRequest(value);
      if (!request || !lore.value) {
        status.textContent = "Choose Story Lore and describe the location first.";
        return;
      }
      run.disabled = true;
      status.textContent = COPY.generating;
      try {
        await scope.run("POST", "charter-generate", `/api/chats/${chatId}/charters/generate`, {
          ...request, lorebook_id: Number(lore.value), owning_lorebook_id: Number(lore.value),
        });
        const refreshed = await scope.run("GET", "charter-refresh", `/api/chats/${chatId}/charters`);
        if (!scope.isLive() || !refreshed) return;
        data = refreshed;
        render();
      } catch (error) {
        status.textContent = error?.userMessage || error?.message || "The lived location could not be prepared.";
        run.disabled = false;
      }
    });
    controls.append(lore, run, status);
    generation.append(controls);
    root.append(generation);
    services.localizer.localize(root);
  };
  render();
  return root;
}
