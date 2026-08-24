export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

export const CORE_DESTINATIONS = Object.freeze(["play", "library", "settings"]);

// UI_CATALOG_START: destination and placeholder copy owned by the shell.
const SHELL_NAME = "Sonder Engine";
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
const PLACEHOLDER_COPY = Object.freeze({
  storyPending: "Story workspace is coming next",
  storyPendingDetail: "This shell preserves the selected story without pretending the Play workflow is already replaced.",
  chooseStory: "Choose a story to begin.",
  chooseStoryDetail: "Open Library to choose an existing story. Story creation arrives with the dedicated story workflow.",
  loadingLibrary: "Loading Library…",
  readingEngine: "Reading the current engine state.",
  stories: "Stories",
  characters: "Characters",
  personas: "Personas",
  lore: "Lore",
  inventory: "Library inventory",
  inventoryDetail: "These counts come from the current engine. Browsing and editing arrive with the Library replacement.",
  settingsReady: "Settings are available",
  settingsDetail: "The current settings were loaded safely. Editing moves here with the Settings replacement.",
});
// UI_CATALOG_END

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

function playView(documentRef, state, t, services, modules) {
  return modules.playView.createPlayView({
    document: documentRef,
    state,
    t,
    services,
    prose: modules.prose,
  });
}

export function destinationCopy(destination, segment = "", t = value => value) {
  const safe = CORE_DESTINATIONS.includes(destination) ? destination : "play";
  const copy = DESTINATION_COPY[safe];
  const subview = safe === "play" ? "" : SUBVIEW_COPY[safe]?.[segment];
  return Object.freeze({
    label: t(subview || copy.label),
    parent: t(subview ? copy.label : SHELL_NAME),
    context: t(copy.context),
  });
}

export function renderDestination({
  document: documentRef,
  destination,
  state,
  t,
  services,
  modules,
}) {
  const safe = CORE_DESTINATIONS.includes(destination) ? destination : "play";
  if (safe === "library") {
    if (modules.libraryAuthoringView.isPersonAuthoringRoute(state.route)) {
      return modules.libraryAuthoringView.createLibraryAuthoringWorkspace({
        document: documentRef,
        state,
        t,
        services,
      });
    }
    return modules.libraryView.createLibraryView({
      document: documentRef,
      state,
      t,
      services,
    });
  }
  if (safe === "settings") return modules.settingsView.createSettingsView({
    document: documentRef,
    state,
    t,
    services,
  });
  return playView(documentRef, state, t, services, modules);
}
