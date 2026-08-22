export const MODULE_RELEASE = "wp03.1";

export const CORE_DESTINATIONS = Object.freeze(["play", "library", "settings"]);

const DESTINATION_COPY = Object.freeze({
  play: Object.freeze({
    label: "Play",
    context: "Your active story and its tools stay together here.",
  }),
  library: Object.freeze({
    label: "Library",
    context: "Find the stories and material you use to play.",
  }),
  settings: Object.freeze({
    label: "Settings",
    context: "Adjust how Sonder Engine works for you.",
  }),
});

const SUBVIEW_COPY = Object.freeze({
  play: Object.freeze({
    "story-tools": "Story tools",
  }),
  library: Object.freeze({
    stories: "Stories",
    characters: "Characters",
    personas: "Personas",
    lore: "Lore",
  }),
  settings: Object.freeze({
    experience: "Experience",
    "ai-connections": "AI Connections",
    content: "Content",
    "add-ons": "Add-ons",
    maintenance: "Maintenance",
    appearance: "Appearance",
    language: "Language",
    providers: "Providers",
    models: "Models",
    extensions: "Extensions",
    advanced: "Advanced",
  }),
});

function element(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function emptyState(documentRef, title, detail) {
  const state = element(documentRef, "div", "ui-empty");
  state.dataset.state = "empty";
  state.append(
    element(documentRef, "strong", "ui-empty__title", title),
    element(documentRef, "p", "ui-muted", detail),
  );
  return state;
}

function playView(documentRef, state, t) {
  if (state.story?.status === "ready" && state.story.data) {
    return emptyState(
      documentRef,
      t("Story workspace is coming next"),
      t("This shell preserves the selected story without pretending the Play workflow is already replaced."),
    );
  }
  return emptyState(
    documentRef,
    t("Choose a story to begin."),
    t("Open Library to choose an existing story. Story creation arrives with the dedicated story workflow."),
  );
}

function libraryView(documentRef, state, t) {
  const library = state.library || {};
  if (library.status === "unrequested" || library.status === "loading") {
    return emptyState(documentRef, t("Loading Library…"), t("Reading the current engine state."));
  }
  const counts = [
    ["Stories", library.chats],
    ["Characters", library.characters],
    ["Personas", library.personas],
    ["Lore", library.lorebooks],
  ];
  const section = element(documentRef, "section", "ui-shell-placeholder");
  section.append(
    element(documentRef, "h2", "ui-heading ui-heading--2", t("Library inventory")),
    element(
      documentRef,
      "p",
      "ui-muted",
      t("These counts come from the current engine. Browsing and editing arrive with the Library replacement."),
    ),
  );
  const list = element(documentRef, "dl", "ui-shell-counts");
  for (const [label, items] of counts) {
    const item = element(documentRef, "div", "ui-shell-count");
    item.append(
      element(documentRef, "dt", "ui-shell-count__label", t(label)),
      element(documentRef, "dd", "ui-shell-count__value", String(Array.isArray(items) ? items.length : 0)),
    );
    list.append(item);
  }
  section.append(list);
  return section;
}

function settingsView(documentRef, _state, t) {
  const section = element(documentRef, "section", "ui-shell-placeholder");
  section.append(
    element(documentRef, "h2", "ui-heading ui-heading--2", t("Settings are available")),
    element(
      documentRef,
      "p",
      "ui-muted",
      t("The current settings were loaded safely. Editing moves here with the Settings replacement."),
    ),
  );
  const categories = element(documentRef, "ul", "ui-shell-category-list");
  for (const name of [
    "Experience",
    "AI Connections",
    "Content",
    "Add-ons",
    "Maintenance",
    "Advanced",
  ]) {
    categories.append(element(documentRef, "li", "ui-shell-category", t(name)));
  }
  section.append(categories);
  return section;
}

export function destinationCopy(destination, segment = "", t = value => value) {
  const safe = CORE_DESTINATIONS.includes(destination) ? destination : "play";
  const copy = DESTINATION_COPY[safe];
  const subview = SUBVIEW_COPY[safe]?.[segment];
  return Object.freeze({
    label: t(subview || copy.label),
    parent: t(subview ? copy.label : "Sonder Engine"),
    context: t(copy.context),
  });
}

export function renderDestination({ document: documentRef, destination, state, t }) {
  const safe = CORE_DESTINATIONS.includes(destination) ? destination : "play";
  if (safe === "library") return libraryView(documentRef, state, t);
  if (safe === "settings") return settingsView(documentRef, state, t);
  return playView(documentRef, state, t);
}
