export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

import { createOverlayController } from "../ui/components/overlay.js?release=alpha98-ui15-5b0f039aae29";

const LAYER_ID = "go-to";

// UI_CATALOG_START: expert navigation chrome and core destination labels.
const GO_TO_COPY = Object.freeze({
  title: "Go To",
  close: "Close",
  placeholder: "Type a destination",
  searchLabel: "Find a destination",
  resultsLabel: "Destinations",
  noResults: "No destinations match.",
  shortcutLabel: "Open Go To",
});
const CORE_RESULTS = Object.freeze([
  ["Destinations", "Play", "Your active story", "play", ""],
  ["Destinations", "Library", "Stories and play material", "library", ""],
  ["Destinations", "Settings", "Engine preferences", "settings", ""],
  ["Library", "Stories", "Browse saved stories", "library", "stories"],
  ["Library", "Characters", "Browse reusable characters", "library", "characters"],
  ["Library", "Personas", "Browse player personas", "library", "personas"],
  ["Library", "Lore", "Browse world material", "library", "lore"],
  ["Settings", "Experience", "Theme, reading, sound, and accessibility", "settings", "experience"],
  ["Settings", "AI Connections", "Providers, models, and roles", "settings", "ai-connections"],
  ["Settings", "Content", "Story content permissions", "settings", "content"],
  ["Settings", "Add-ons", "Extensions and permissions", "settings", "add-ons"],
  ["Settings", "Maintenance", "Updates, memory search, and diagnostics", "settings", "maintenance"],
  ["Settings", "Advanced", "Prompt and raw story tools", "settings", "advanced"],
]);
// UI_CATALOG_END

function element(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function normalized(value) {
  return String(value || "").trim().toLocaleLowerCase();
}

export function createGoTo(options = {}) {
  const { services, modules, shortcutRegistry } = options;
  const documentRef = options.document || document;
  const overlayHost = documentRef.querySelector("[data-shell-overlay-host]");
  const opener = documentRef.querySelector("[data-shell-go-to]");
  if (!overlayHost || !opener || !services?.router || !shortcutRegistry) {
    throw new Error("Go To requires the shell overlay, router, and shortcut registry.");
  }
  const t = services.localizer.t;
  const overlay = element(documentRef, "div", "ui-overlay");
  overlay.hidden = true;
  overlay.dataset.shellGoTo = "true";
  const dialog = element(documentRef, "section", "ui-dialog ui-go-to");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "ui-go-to-title");
  const header = element(documentRef, "header", "ui-go-to__header");
  const title = element(documentRef, "h2", "ui-heading ui-heading--2", t(GO_TO_COPY.title));
  title.id = "ui-go-to-title";
  const close = element(documentRef, "button", "ui-button ui-button--quiet", t(GO_TO_COPY.close));
  close.type = "button";
  header.append(title, close);
  const search = element(documentRef, "input", "ui-field__control ui-go-to__search");
  search.type = "search";
  search.autocomplete = "off";
  search.placeholder = t(GO_TO_COPY.placeholder);
  search.setAttribute("role", "searchbox");
  search.setAttribute("aria-label", t(GO_TO_COPY.searchLabel));
  search.setAttribute("aria-controls", "ui-go-to-results");
  search.setAttribute("aria-activedescendant", "");
  const results = element(documentRef, "div", "ui-go-to__results");
  results.id = "ui-go-to-results";
  results.setAttribute("role", "listbox");
  results.setAttribute("aria-label", t(GO_TO_COPY.resultsLabel));
  const empty = element(documentRef, "p", "ui-empty ui-go-to__empty", t(GO_TO_COPY.noResults));
  empty.hidden = true;
  dialog.append(header, search, results, empty);
  overlay.append(dialog);
  overlayHost.append(overlay);

  let route = services.router.current();
  let visible = [];
  let activeIndex = 0;
  let syncing = false;
  let stopped = false;

  const availableResults = () => {
    const state = services.store.getSnapshot();
    const core = CORE_RESULTS.map(([group, label, context, destination, segment]) => ({
      group: t(group),
      label: t(label),
      context: t(context),
      route: { destination, segments: segment ? [segment] : [] },
    }));
    const actions = [{
      group: t("Actions"),
      label: t("New story"),
      context: t("Start with a character, persona, and world"),
      action: () => modules?.newStory?.openNewStory?.({ document: documentRef, services }),
    }];
    if (state.story?.owner) {
      actions.push({
        group: t("Actions"),
        label: t("Story tools"),
        context: t("Current story"),
        action: () => options.openContext?.(),
      });
    }
    const recent = (state.library?.chats || []).slice(0, 5).map(story => ({
      group: t("Recent stories"),
      label: story.name || t("Untitled story"),
      context: t("Open in Play"),
      route: { destination: "play", query: { chat: String(story.id) } },
    }));
    const provided = (options.resultProviders || []).flatMap(provider => {
      try {
        return (provider() || []).map(item => ({ group: t("Add-ons"), ...item }));
      } catch {
        return [];
      }
    });
    return [...actions, ...core.slice(0, 3), ...recent, ...core.slice(3), ...provided].map((item, index) => ({
      ...item,
      id: `ui-go-to-result-${index}`,
    }));
  };

  const select = result => {
    if (result.action) {
      services.router.closeTopLayer();
      documentRef.defaultView.requestAnimationFrame(() => result.action());
      return;
    }
    services.router.navigate(result.route);
  };

  const paintActive = () => {
    const nodes = [...results.querySelectorAll("[role='option']")];
    nodes.forEach((node, index) => node.setAttribute("aria-selected", String(index === activeIndex)));
    const active = nodes[activeIndex];
    search.setAttribute("aria-activedescendant", active?.id || "");
    active?.scrollIntoView({ block: "nearest" });
  };

  const render = () => {
    const query = normalized(search.value);
    visible = availableResults().filter(item => (
      !query || normalized(`${item.label} ${item.context}`).includes(query)
    ));
    activeIndex = Math.min(activeIndex, Math.max(0, visible.length - 1));
    let lastGroup = "";
    const nodes = visible.flatMap((item, index) => {
      const groupNodes = [];
      if (item.group !== lastGroup) {
        lastGroup = item.group;
        groupNodes.push(element(documentRef, "h3", "ui-go-to__group", item.group));
      }
      const option = element(documentRef, "button", "ui-go-to__result");
      option.type = "button";
      option.id = item.id;
      option.setAttribute("role", "option");
      option.append(
        element(documentRef, "span", "ui-go-to__result-label", item.label),
        element(documentRef, "span", "ui-go-to__result-context", item.context),
      );
      option.addEventListener("pointermove", () => {
        activeIndex = index;
        paintActive();
      });
      option.addEventListener("click", () => select(item));
      groupNodes.push(option);
      return groupNodes;
    });
    results.replaceChildren(...nodes);
    empty.hidden = visible.length > 0;
    paintActive();
  };

  const controller = createOverlayController(overlay, {
    backgroundRoot: overlayHost.parentElement,
    onClose: () => {
      if (!syncing && services.router.current().layers.some(layer => layer.id === LAYER_ID)) {
        services.router.closeTopLayer();
      }
    },
  });

  const open = () => {
    if (stopped || route.layers.some(layer => layer.id === LAYER_ID)) return;
    const focusReturn = documentRef.activeElement?.dataset?.focusIdentity
      || `destination:${route.destination}`;
    services.router.openLayer({ id: LAYER_ID, focusReturn });
    route = services.router.current();
    search.value = "";
    activeIndex = 0;
    render();
    controller.show();
    search.focus();
  };

  const closeLayer = () => services.router.closeTopLayer();
  const sync = nextRoute => {
    route = nextRoute;
    const shouldOpen = route.layers.some(layer => layer.id === LAYER_ID);
    syncing = true;
    if (shouldOpen) {
      render();
      if (!controller.isOpen) {
        controller.show();
      }
    } else {
      controller.close("route-sync");
      visible = [];
      results.replaceChildren();
      search.setAttribute("aria-activedescendant", "");
    }
    syncing = false;
  };

  const onInput = () => { activeIndex = 0; render(); };
  const onSearchKey = event => {
    if (event.isComposing) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!visible.length) return;
      const direction = event.key === "ArrowDown" ? 1 : -1;
      activeIndex = (activeIndex + direction + visible.length) % visible.length;
      paintActive();
    } else if (event.key === "Enter" && visible[activeIndex]) {
      event.preventDefault();
      select(visible[activeIndex]);
    }
  };

  opener.addEventListener("click", open);
  close.addEventListener("click", closeLayer);
  search.addEventListener("input", onInput);
  search.addEventListener("keydown", onSearchKey);
  const unregisterOpen = shortcutRegistry.register({
    owner: "core-shell",
    id: "go-to",
    combo: "mod+k",
    label: t(GO_TO_COPY.shortcutLabel),
    handler: open,
    core: true,
  });

  const teardown = () => {
    if (stopped) return;
    stopped = true;
    unregisterOpen();
    opener.removeEventListener("click", open);
    close.removeEventListener("click", closeLayer);
    search.removeEventListener("input", onInput);
    search.removeEventListener("keydown", onSearchKey);
    controller.destroy();
    overlay.remove();
  };

  return Object.freeze({ open, sync, teardown, results: availableResults });
}
