export const MODULE_RELEASE = "alpha98-ui11-0acc47fb0573";

import { mountLivedLocationFields } from "./lived-location.js?release=alpha98-ui11-0acc47fb0573";
import { openNewStory } from "./new-story.js?release=alpha98-ui11-0acc47fb0573";

const loreLocationDrafts = new Map();

// UI_CATALOG_START: Library discovery and detail copy.
const COPY = Object.freeze({
  search: "Search Library",
  searchAction: "Search",
  sort: "Sort Library",
  filters: "Library material types",
  loading: "Loading Library…",
  loadingDetail: "Reading the current Library index.",
  empty: "Your Library is empty",
  emptyDetail: "Stories and reusable play material will appear here when they exist.",
  noResults: "No Library items match",
  noResultsDetail: "Try a different search, category, or scope.",
  offline: "Library is offline",
  error: "Library could not be refreshed",
  preserved: "The last confirmed results remain below.",
  unavailable: "Unavailable item",
  unavailableDetail: "That item no longer exists or is outside the current Library view.",
  choose: "Choose an item",
  chooseDetail: "Select a Library row to see its usage and details.",
  favorite: "Add to favorites",
  unfavorite: "Remove from favorites",
  associations: "Used by stories",
  noAssociations: "Not used by a story.",
  undo: "Undo",
  openStory: "Open in Play",
  editStory: "Edit story",
  exportStory: "Export story",
  deleteStory: "Delete story…",
  confirmDeleteStory: "Delete this story",
  cancelDelete: "Keep story",
  deleteWarning: "This permanently removes the complete story, its history, and story-owned lore. Reusable Characters, Personas, and original Lore remain.",
  stories: "Stories",
  characters: "Characters",
  personas: "Personas",
  lore: "Lore",
  chosenStory: "Chosen story",
  notUsed: "Not used",
  multipleStories: "Multiple stories",
  story: "Story",
  character: "Character",
  persona: "Persona",
  storyScope: "Story scope",
  untitledStory: "Untitled story",
  name: "Name",
  type: "Type",
  created: "Created",
  storyUse: "Story use",
  visibility: "Library visibility",
  activeItems: "Active items",
  archivedItems: "Archived items",
  untitled: "Untitled",
  libraryItem: "Library item",
  tryAgain: "Try again when the engine is available.",
  usedOne: "Used in one story",
  usedMany: "Used in ${count} stories",
  changeSaved: "Library change saved.",
  removeActiveCast: "Remove from active cast",
  restoreActiveCast: "Restore to active cast",
  primaryPersonaChange: "Primary persona · change in Story setup",
  removeAdditionalPlayer: "Remove additional player",
  restoreAdditionalPlayer: "Restore additional player",
  detachFromStory: "Detach from story",
  addToStoryHeading: "Add to a story",
  storyFor: "Story for ${name}",
  addToStory: "Add to story",
  archiveStory: "Archive story",
  archiveCharacter: "Archive character",
  archivePersona: "Archive persona",
  archiveLore: "Archive lore",
  restoreStory: "Restore story",
  restoreCharacter: "Restore character",
  restorePersona: "Restore persona",
  restoreLore: "Restore lore",
  libraryDetails: "Library details",
  noSummary: "No public summary has been added.",
  savingChange: "Saving Library change…",
  waitingEngine: "Waiting for the engine to accept it.",
  changeNotSaved: "Library change was not saved",
  active: "Active",
  dormant: "Dormant",
  primary: "Primary",
  attached: "Attached",
  disabled: "Disabled",
  canon: "Canon",
  owned: "Owned",
  safeLink: "Some Library link options were invalid and were safely ignored.",
  unavailableInformation: "Library information is temporarily unavailable.",
  undoBriefly: "The Library change can be undone briefly.",
  removedCast: "Character removed from the active cast. Their story history remains.",
  restoredCast: "Character restored to the active cast.",
  removedPlayer: "Additional player removed from the story.",
  restoredPlayer: "Additional player restored.",
  detachedLore: "Lore detached from the story; the reusable original remains in Library.",
  addedCharacter: "Character added to the story.",
  addedPlayer: "Additional player added to the story.",
  attachedLore: "Lore attached to the story.",
  archivedTemplate: "${name} archived.",
  restoredTemplate: "${name} restored.",
  mutationFailed: "The Library change was not saved.",
  undoFailed: "Undo was not accepted.",
  storyOverview: "Story overview",
  connectedCast: "Connected cast",
  connectedPlayers: "Player personas",
  connectedLore: "Connected lore",
  recentActivity: "Recent activity",
  turnsRecorded: "${count} turns recorded",
  setupIssues: "Needs attention",
  importStory: "Import story",
  branchLatest: "Branch from latest turn",
  branching: "Creating story branch…",
  branchHelp: "Creates a new Story at the latest recorded turn. The current Story is unchanged.",
  recentUse: "Recent use",
  recent: "Recent",
  favorites: "Favorites",
  drafts: "Drafts",
  noneYet: "None yet.",
  localDraft: "Local draft",
  editCharacter: "Edit character",
  editPersona: "Edit persona",
  exportCharacter: "Export character",
  exportPersona: "Export persona",
  duplicateCharacter: "Duplicate character",
  duplicatePersona: "Duplicate persona",
  createCharacter: "Create character",
  createPersona: "Create persona",
  importCharacter: "Import character",
  importPersona: "Import persona",
  more: "More",
  editAction: "Edit",
  exportAction: "Export",
  duplicateAction: "Duplicate",
  editStoryCard: "Edit Story card",
  library: "Library",
  libraryScope: "Library scope",
  allLibrary: "All Library",
  storyMaterial: "Story material",
  newStory: "New story",
  activeStory: "Active story",
  moreFor: "More actions for ${name}",
});
// UI_CATALOG_END

const TYPES = Object.freeze([
  ["story", COPY.stories, COPY.stories],
  ["character", COPY.characters, COPY.characters],
  ["persona", COPY.personas, COPY.personas],
  ["lore", COPY.lore, COPY.lore],
]);
const SCOPES = Object.freeze([
  ["all", COPY.allLibrary],
  ["story", COPY.chosenStory],
  ["unassigned", COPY.notUsed],
  ["multiple", COPY.multipleStories],
]);
const KIND_LABELS = Object.freeze({
  story: COPY.story,
  character: COPY.character,
  persona: COPY.persona,
  lore: COPY.lore,
});
const ARCHIVE_LABELS = Object.freeze({
  story: COPY.archiveStory,
  character: COPY.archiveCharacter,
  persona: COPY.archivePersona,
  lore: COPY.archiveLore,
});
const RESTORE_LABELS = Object.freeze({
  story: COPY.restoreStory,
  character: COPY.restoreCharacter,
  persona: COPY.restorePersona,
  lore: COPY.restoreLore,
});

function node(documentRef, tag, className = "", text = "") {
  const element = documentRef.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function button(documentRef, label, className = "ui-button ui-button--quiet") {
  const control = node(documentRef, "button", className, label);
  control.type = "button";
  return control;
}

function stateBlock(documentRef, state, title, detail) {
  const block = node(documentRef, "div", "ui-empty");
  block.dataset.state = state;
  block.append(
    node(documentRef, "strong", "ui-empty__title", title),
    node(documentRef, "p", "ui-muted", detail),
  );
  return block;
}

function usage(item) {
  const associations = Array.isArray(item?.associations) ? item.associations : [];
  if (!associations.length) return COPY.notUsed;
  if (associations.length === 1) return associations[0].story_name || COPY.usedOne;
  return COPY.usedMany.replace("${count}", String(associations.length));
}

function typeForRoute(route) {
  const segment = route?.segments?.[0] || "";
  return ({
    stories: "story",
    characters: "character",
    personas: "persona",
    lore: "lore",
  })[segment] || "";
}

function routeQuery(route) {
  return { ...(route?.query || {}) };
}

function navigate(services, type, query) {
  services.library.navigate({ type, query });
}

function icon(documentRef, name) {
  const svg = documentRef.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ui-icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = documentRef.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/assets/icons/sonder-icons.svg?release=${MODULE_RELEASE}#icon-${name}`);
  svg.append(use);
  return svg;
}

function labelWithIcon(documentRef, control, iconName, label) {
  control.replaceChildren(icon(documentRef, iconName), node(documentRef, "span", "", label));
  return control;
}

function workflowSession() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function workspaceFilters(documentRef, services, state) {
  const route = state.route || {};
  const query = routeQuery(route);
  const activeType = typeForRoute(route);
  const activeScope = query.scope || "all";
  const filters = node(documentRef, "div", "ui-library-workspace__filters");

  const types = node(documentRef, "nav", "ui-library-workspace__types");
  types.setAttribute("aria-label", COPY.filters);
  const typeList = node(documentRef, "ul", "ui-library__filter-list ui-library__tabs");
  for (const [type, label, accessible] of TYPES) {
    const item = node(documentRef, "li");
    const control = button(documentRef, label, "ui-library__filter");
    control.setAttribute("aria-label", accessible);
    if (type === (activeType || "story")) control.setAttribute("aria-current", "page");
    control.addEventListener("click", () => navigate(services, type, { ...query, item: "" }));
    item.append(control);
    typeList.append(item);
  }
  types.append(typeList);

  const scopeField = node(documentRef, "label", "ui-field ui-library__scope-field");
  scopeField.append(node(documentRef, "span", "ui-field__label", COPY.libraryScope));
  const scope = node(documentRef, "select", "ui-input ui-library__scope");
  scope.setAttribute("aria-label", COPY.libraryScope);
  for (const [value, label] of SCOPES) {
    const option = node(documentRef, "option", "", label);
    option.value = value;
    option.selected = value === activeScope;
    scope.append(option);
  }
  scope.addEventListener("change", () => {
    const firstStory = state.library?.chats?.[0]?.id;
    navigate(services, activeType || "story", {
      ...query,
      item: "",
      scope: scope.value === "all" ? "" : scope.value,
      story: scope.value === "story" ? (query.story || firstStory || "") : query.story,
    });
  });
  scopeField.append(scope);
  filters.append(types, scopeField);

  const stories = state.library?.chats || [];
  if (stories.length && activeScope === "story") {
    const storyLabel = node(documentRef, "label", "ui-field ui-library__story-scope");
    storyLabel.append(node(documentRef, "span", "ui-field__label", COPY.storyScope));
    const story = node(documentRef, "select", "ui-input");
    story.setAttribute("aria-label", COPY.storyScope);
    for (const row of stories) {
      const option = node(documentRef, "option", "", row.name || COPY.untitledStory);
      option.value = row.id;
      option.selected = String(query.story || "") === String(row.id);
      story.append(option);
    }
    story.addEventListener("change", () => navigate(services, activeType, {
      ...query, item: "", scope: "story", story: story.value,
    }));
    storyLabel.append(story);
    filters.append(storyLabel);
  }
  return filters;
}

function workspaceActions(documentRef, services, activeType) {
  const actions = node(
    documentRef, "div", "ui-action-cluster ui-library-workspace__actions",
  );
  actions.setAttribute("role", "group");
  if (activeType === "story") {
    const create = labelWithIcon(documentRef,
      button(documentRef, COPY.newStory, "ui-button ui-button--primary"), "plus", COPY.newStory);
    create.addEventListener("click", () => openNewStory({ document: documentRef, services }));
    const importStory = labelWithIcon(documentRef,
      button(documentRef, COPY.importStory), "import", COPY.importStory);
    importStory.addEventListener("click", () => {
      documentRef.dispatchEvent(new CustomEvent("sonder:library-select", {
        detail: { workflow: "story-import" },
      }));
      navigate(services, "story", { mode: "import", session: workflowSession() });
    });
    actions.append(create, importStory);
  } else if (activeType === "character" || activeType === "persona") {
    const isCharacter = activeType === "character";
    const createLabel = isCharacter ? COPY.createCharacter : COPY.createPersona;
    const importLabel = isCharacter ? COPY.importCharacter : COPY.importPersona;
    const create = labelWithIcon(documentRef,
      button(documentRef, createLabel, "ui-button ui-button--primary"), "plus", createLabel);
    create.addEventListener("click", () => navigate(services, activeType, {
      mode: "create", session: workflowSession(),
    }));
    const importPerson = labelWithIcon(documentRef,
      button(documentRef, importLabel), "import", importLabel);
    importPerson.addEventListener("click", () => navigate(services, activeType, {
      mode: "import", session: workflowSession(),
    }));
    actions.append(create, importPerson);
  }
  return actions.childElementCount ? actions : null;
}

function toolbar(documentRef, services, state) {
  const route = state.route || {};
  const query = routeQuery(route);
  const activeType = typeForRoute(route);
  const form = node(documentRef, "form", "ui-library__toolbar");
  form.setAttribute("role", "search");
  const label = node(documentRef, "label", "ui-field ui-library__search");
  const labelText = node(documentRef, "span", "ui-field__label", COPY.search);
  const input = node(documentRef, "input", "ui-input");
  input.type = "search";
  input.name = "q";
  input.value = query.q || "";
  input.setAttribute("aria-label", COPY.search);
  input.maxLength = 200;
  label.append(labelText, input);
  const submit = button(documentRef, COPY.searchAction, "ui-button ui-button--primary");
  submit.type = "submit";

  const sortLabel = node(documentRef, "label", "ui-field ui-library__sort");
  sortLabel.append(node(documentRef, "span", "ui-field__label", COPY.sort));
  const sort = node(documentRef, "select", "ui-input");
  sort.setAttribute("aria-label", COPY.sort);
  for (const [value, text] of [
    ["name", COPY.name], ["recent", COPY.recentUse], ["type", COPY.type],
    ["created", COPY.created], ["usage", COPY.storyUse],
  ]) {
    const option = node(documentRef, "option", "", text);
    option.value = value;
    option.selected = (query.sort || "name") === value;
    sort.append(option);
  }
  sort.addEventListener("change", () => navigate(services, activeType, {
    ...query,
    item: "",
    sort: sort.value === "name" ? "" : sort.value,
  }));
  sortLabel.append(sort);
  const visibilityLabel = node(documentRef, "label", "ui-field ui-library__visibility");
  visibilityLabel.append(node(documentRef, "span", "ui-field__label", COPY.visibility));
  const visibility = node(documentRef, "select", "ui-input");
  visibility.setAttribute("aria-label", COPY.visibility);
  for (const [value, text] of [["active", COPY.activeItems], ["archived", COPY.archivedItems]]) {
    const option = node(documentRef, "option", "", text);
    option.value = value;
    option.selected = (query.visibility || "active") === value;
    visibility.append(option);
  }
  visibility.addEventListener("change", () => navigate(services, activeType, {
    ...query,
    item: "",
    visibility: visibility.value === "active" ? "" : visibility.value,
  }));
  visibilityLabel.append(visibility);
  form.addEventListener("submit", event => {
    event.preventDefault();
    navigate(services, activeType, { ...query, item: "", q: input.value.trim() });
  });
  form.append(label, submit, sortLabel, visibilityLabel);
  return form;
}

function rowAction(documentRef, label, action) {
  const control = button(documentRef, label, "ui-menu__item");
  control.setAttribute("role", "menuitem");
  control.addEventListener("click", action);
  return control;
}

function rowOverflow(documentRef, services, item) {
  const name = item.name || COPY.untitled;
  const details = node(documentRef, "details", "ui-library__more-menu");
  const summary = node(documentRef, "summary", "ui-library__more");
  summary.setAttribute("role", "button");
  summary.setAttribute("aria-label", COPY.moreFor.replace("${name}", name));
  summary.setAttribute("aria-haspopup", "menu");
  summary.setAttribute("aria-expanded", "false");
  summary.append(icon(documentRef, "more"));
  const menu = node(documentRef, "div", "ui-menu ui-library__row-menu");
  menu.id = `ui-library-actions-${item.kind}-${item.id}`;
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", COPY.moreFor.replace("${name}", name));
  summary.setAttribute("aria-controls", menu.id);

  const closeMenu = () => {
    details.open = false;
    summary.setAttribute("aria-expanded", "false");
  };
  const act = (label, action) => rowAction(documentRef, label, event => {
    event.stopPropagation();
    closeMenu();
    action();
  });

  if (item.kind === "story") {
    menu.append(
      act(COPY.openStory, () => services.router.navigate({
        destination: "play", query: { chat: String(item.id) },
      })),
      act(COPY.editStory, () => {
        const route = services.library.currentRoute();
        services.library.navigate({
          type: "story",
          query: { ...(route?.query || {}), item: item.key, mode: "edit" },
        });
      }),
    );
    const exported = node(documentRef, "a", "ui-menu__item", COPY.exportStory);
    exported.setAttribute("role", "menuitem");
    exported.href = `/api/chats/${item.id}/export`;
    exported.download = `${name}.json`;
    exported.addEventListener("click", closeMenu);
    menu.append(exported);
  } else if (item.kind === "character" || item.kind === "persona") {
    const editLabel = item.kind === "character" ? COPY.editCharacter : COPY.editPersona;
    menu.append(act(editLabel, () => {
      const route = services.library.currentRoute();
      services.library.navigate({
        type: item.kind,
        query: { ...(route?.query || {}), item: item.key, mode: "edit" },
      });
    }));
    const exported = node(
      documentRef, "a", "ui-menu__item",
      item.kind === "character" ? COPY.exportCharacter : COPY.exportPersona,
    );
    exported.setAttribute("role", "menuitem");
    exported.href = item.kind === "character"
      ? `/api/characters/${item.id}/export`
      : `/api/personas/${item.id}/export`;
    exported.download = `${name}.json`;
    exported.addEventListener("click", closeMenu);
    menu.append(exported);
  }
  menu.append(act(
    item.archived ? RESTORE_LABELS[item.kind] : ARCHIVE_LABELS[item.kind],
    () => services.library.setArchived(item, !item.archived),
  ));

  details.addEventListener("toggle", () => {
    summary.setAttribute("aria-expanded", String(details.open));
    if (!details.open) return;
    for (const other of documentRef.querySelectorAll(".ui-library__more-menu[open]")) {
      if (other !== details) other.open = false;
    }
  });
  details.addEventListener("keydown", event => {
    if (event.key !== "Escape" || !details.open) return;
    event.preventDefault();
    event.stopPropagation();
    closeMenu();
    summary.focus({ preventScroll: true });
  });
  details.append(summary, menu);
  return details;
}

function ledger(documentRef, services, state) {
  const library = state.library || {};
  const route = state.route || {};
  const query = routeQuery(route);
  const activeType = typeForRoute(route);
  const list = node(documentRef, "ol", "ui-library__ledger");
  list.dataset.libraryLedger = "true";
  const items = (library.items || []).slice(0, 100);
  for (const item of items) {
    const row = node(documentRef, "li", "ui-library__row");
    const control = button(documentRef, "", "ui-library__item");
    control.dataset.libraryItem = item.key;
    control.dataset.focusIdentity = `library-item:${item.key}`;
    const openStoryId = state.library?.chats?.[0]?.id;
    if (query.item === item.key || (!query.item && item.kind === "story"
        && String(item.id) === String(openStoryId || ""))) {
      control.setAttribute("aria-current", "true");
    }
    const index = node(documentRef, "span", "ui-library__index", String(item.id).padStart(2, "0"));
    index.setAttribute("aria-hidden", "true");
    const copy = node(documentRef, "span", "ui-library__item-copy");
    const name = node(documentRef, "strong", "ui-library__name", item.name || COPY.untitled);
    if (item.kind === "story") {
      copy.append(name, node(documentRef, "span", "ui-library__summary", COPY.activeStory));
    } else {
      const meta = node(documentRef, "span", "ui-library__meta");
      meta.append(
        node(documentRef, "span", "ui-library__kind", KIND_LABELS[item.kind] || COPY.libraryItem),
        node(documentRef, "span", "ui-library__usage", usage(item)),
      );
      if (item.summary) copy.append(name, node(documentRef, "span", "ui-library__summary", item.summary), meta);
      else copy.append(name, meta);
    }
    control.append(index, copy);
    const selectItem = () => {
      services.library.recordRecent(item.key);
      navigate(services, activeType, { ...query, item: item.key });
      documentRef.dispatchEvent(new CustomEvent("sonder:library-select", {
        detail: { item: item.key },
      }));
    };
    control.addEventListener("click", selectItem);
    row.append(control, rowOverflow(documentRef, services, item));
    list.append(row);
  }
  return list;
}

function resultState(documentRef, library) {
  if (library.status === "loading" || library.status === "unrequested") {
    return stateBlock(documentRef, "loading", COPY.loading, COPY.loadingDetail);
  }
  if (library.status === "offline" || library.status === "error") {
    const title = library.status === "offline" ? COPY.offline : COPY.error;
    return stateBlock(documentRef, library.status, title,
      library.items?.length ? COPY.preserved : COPY.tryAgain);
  }
  if (library.status === "empty") {
    const filtered = Boolean(library.route?.q || library.route?.type
      || library.route?.scope !== "all");
    return stateBlock(documentRef, "empty", filtered ? COPY.noResults : COPY.empty,
      filtered ? COPY.noResultsDetail : COPY.emptyDetail);
  }
  return null;
}

function libraryWorkspace(documentRef, services, state) {
  const activeType = typeForRoute(state.route) || "story";
  const filteredState = { ...state, library: {
    ...(state.library || {}),
    items: (state.library?.items || []).filter(item => item.kind === activeType),
  } };
  const section = node(documentRef, "section", "ui-library-workspace");
  section.dataset.libraryWorkspace = "true";
  const head = node(documentRef, "header", "ui-library-workspace__header");
  const title = node(documentRef, "div");
  title.append(
    node(documentRef, "p", "ui-library__kicker", COPY.storyMaterial),
    node(documentRef, "h2", "ui-library-workspace__title", COPY.library),
  );
  const heading = title.querySelector("h2");
  heading.tabIndex = -1;
  heading.dataset.focusIdentity = "destination:library";
  head.append(title);
  const actions = workspaceActions(documentRef, services, activeType);
  if (actions) head.append(actions);
  section.append(
    head,
    workspaceFilters(documentRef, services, filteredState),
    toolbar(documentRef, services, filteredState),
  );
  const status = resultState(documentRef, filteredState.library);
  if (status) section.append(status);
  if (filteredState.library.items?.length) {
    section.append(ledger(documentRef, services, filteredState));
  }
  return section;
}

export function createLibraryView(options = {}) {
  const documentRef = options.document || document;
  const { services, state } = options;
  const section = node(documentRef, "section", "ui-library");
  section.dataset.libraryView = "true";
  const content = node(documentRef, "div", "ui-library__content");
  const library = state.library || {};
  const workspace = libraryWorkspace(documentRef, services, state);
  content.append(workspace);
  const undo = undoNotice(documentRef, services, library);
  if (undo) content.prepend(undo);
  if (library.notice) {
    const notice = node(documentRef, "p", "ui-notice ui-library__notice", library.notice);
    notice.setAttribute("role", "status");
    content.append(notice);
  }
  section.append(content);
  const routeIdentity = services.library.scrollIdentity(state.route);
  const scrollRegion = content;
  const restorePosition = services.library.scrollFor(routeIdentity);
  const returnFocusIdentity = services.library.returnFocusIdentity();
  const mayRestoreReturnFocus = !["loading", "refreshing"].includes(library.status);
  scrollRegion.scrollTop = restorePosition;
  const viewTarget = documentRef.defaultView;
  let restoreFrame = viewTarget?.requestAnimationFrame(() => {
    restoreFrame = null;
    scrollRegion.scrollTop = restorePosition;
    if (returnFocusIdentity && mayRestoreReturnFocus) {
      const focusTarget = [...section.querySelectorAll("[data-focus-identity]")]
        .find(element => element.dataset.focusIdentity === returnFocusIdentity);
      if (focusTarget) {
        focusTarget.focus({ preventScroll: true });
        services.library.clearReturnFocus(returnFocusIdentity);
      }
    }
  });
  const onScroll = () => services.library.saveScroll(routeIdentity, scrollRegion.scrollTop);
  scrollRegion.addEventListener("scroll", onScroll, { passive: true });
  return Object.freeze({
    element: section,
    teardown: () => {
      if (restoreFrame) viewTarget?.cancelAnimationFrame(restoreFrame);
      services.library.saveScroll(routeIdentity, scrollRegion.scrollTop);
      scrollRegion.removeEventListener("scroll", onScroll);
    },
  });
}

function undoNotice(documentRef, services, library) {
  if (!library?.undo) return null;
  const notice = node(documentRef, "section", "ui-notice ui-library-detail__undo");
  notice.dataset.tone = "success";
  notice.setAttribute("role", "status");
  notice.append(
    node(documentRef, "p", "", library.undo.message || COPY.changeSaved),
  );
  const undo = button(documentRef, COPY.undo, "ui-button ui-button--quiet");
  undo.addEventListener("click", () => services.library.runUndo());
  notice.append(undo);
  return notice;
}

function associationAction(documentRef, services, item, association) {
  let label = "";
  if (item.kind === "character") {
    label = association.state === "active"
      ? COPY.removeActiveCast : COPY.restoreActiveCast;
  } else if (item.kind === "persona") {
    if (association.state === "primary") {
      return node(documentRef, "span", "ui-muted", COPY.primaryPersonaChange);
    }
    label = association.state === "active"
      ? COPY.removeAdditionalPlayer : COPY.restoreAdditionalPlayer;
  } else if (item.kind === "lore" && item.reusable
      && ["attached", "disabled", "canon"].includes(association.state)) {
    label = COPY.detachFromStory;
  }
  const controls = node(documentRef, "div", "ui-action-cluster");
  controls.setAttribute("role", "group");
  if (item.kind === "character") {
    const editCard = button(documentRef, COPY.editStoryCard);
    editCard.setAttribute(
      "aria-label",
      `${COPY.editStoryCard} · ${association.story_name || COPY.untitledStory}`,
    );
    editCard.addEventListener("click", () => {
      const route = services.library.currentRoute();
      services.library.navigate({
        type: "character",
        query: {
          ...(route?.query || {}), item: item.key,
          mode: "story-card", story: String(association.story_id),
        },
      });
    });
    controls.append(editCard);
  }
  if (!label) return controls.childElementCount ? controls : null;
  const control = button(documentRef, label);
  control.addEventListener("click", () => services.library.setAssociation(item, association));
  controls.append(control);
  return controls;
}

function addToStory(documentRef, services, library, item) {
  if (item.kind === "story" || !item.reusable) return null;
  const used = new Set((item.associations || []).map(row => Number(row.story_id)));
  const stories = (library.chats || []).filter(story => !used.has(Number(story.id)));
  if (!stories.length) return null;
  const section = node(documentRef, "section", "ui-library-detail__add");
  section.append(node(documentRef, "h4", "ui-heading ui-heading--3", COPY.addToStoryHeading));
  const controls = node(documentRef, "div", "ui-tool-inline");
  const select = node(documentRef, "select", "ui-input");
  select.setAttribute("aria-label", COPY.storyFor.replace("${name}", item.name || COPY.libraryItem));
  for (const story of stories) {
    const option = node(documentRef, "option", "", story.name || COPY.untitledStory);
    option.value = story.id;
    select.append(option);
  }
  const add = button(documentRef, COPY.addToStory, "ui-button ui-button--primary");
  add.addEventListener("click", () => services.library.addToStory(item, select.value));
  controls.append(select, add);
  section.append(controls);
  return section;
}

function lifecycleActions(documentRef, services, library, item, viewState, rerender) {
  const section = node(documentRef, "section", "ui-library-detail__actions ui-action-cluster");
  section.setAttribute("role", "toolbar");
  section.setAttribute("aria-label", `${item.name || COPY.libraryItem} actions`);
  const archive = button(
    documentRef,
    item.archived ? RESTORE_LABELS[item.kind] : ARCHIVE_LABELS[item.kind],
  );
  archive.addEventListener("click", () => services.library.setArchived(item, !item.archived));
  if (item.kind === "character" || item.kind === "persona") {
    const edit = button(documentRef, COPY.editAction);
    edit.setAttribute("aria-label", item.kind === "character" ? COPY.editCharacter : COPY.editPersona);
    edit.addEventListener("click", () => {
      const route = services.library.currentRoute();
      services.library.navigate({
        type: item.kind,
        query: { ...(route?.query || {}), item: item.key, mode: "edit" },
      });
    });
    const exported = node(
      documentRef, "a", "ui-button ui-button--quiet",
      COPY.exportAction,
    );
    exported.setAttribute("aria-label", item.kind === "character" ? COPY.exportCharacter : COPY.exportPersona);
    exported.href = item.kind === "character"
      ? `/api/characters/${item.id}/export`
      : `/api/personas/${item.id}/export`;
    exported.download = `${item.name || item.kind}.json`;
    const duplicate = button(
      documentRef,
      COPY.duplicateAction,
    );
    duplicate.setAttribute("aria-label", item.kind === "character" ? COPY.duplicateCharacter : COPY.duplicatePersona);
    duplicate.addEventListener("click", () => services.authoring.duplicate());
    const more = node(documentRef, "details", "ui-action-more");
    more.append(node(documentRef, "summary", "ui-button ui-button--quiet", COPY.more));
    const menu = node(documentRef, "div", "ui-action-more__menu");
    menu.append(archive);
    more.append(menu);
    section.append(edit, exported, duplicate, more);
    return section;
  }
  if (item.kind !== "story") {
    section.append(archive);
    return section;
  }

  const open = button(documentRef, COPY.openStory, "ui-button ui-button--primary");
  open.addEventListener("click", () => services.router.navigate({
    destination: "play", query: { chat: String(item.id) },
  }));
  const exported = node(documentRef, "a", "ui-button ui-button--quiet", COPY.exportStory);
  exported.href = `/api/chats/${item.id}/export`;
  exported.download = `${item.name || "story"}.json`;
  const edit = button(documentRef, COPY.editStory);
  edit.addEventListener("click", () => {
    const route = services.library.currentRoute();
    services.library.navigate({
      type: "story",
      query: { ...(route?.query || {}), item: item.key, mode: "edit" },
    });
  });
  section.append(open, edit, exported, archive);

  if (!viewState.confirmDelete) {
    const remove = button(documentRef, COPY.deleteStory, "ui-button ui-button--danger");
    remove.addEventListener("click", () => {
      viewState.confirmDelete = true;
      rerender();
    });
    section.append(remove);
    return section;
  }
  const warning = node(documentRef, "div", "ui-notice ui-library-detail__delete");
  warning.dataset.tone = "danger";
  warning.append(node(documentRef, "p", "", COPY.deleteWarning));
  const confirm = button(documentRef, COPY.confirmDeleteStory, "ui-button ui-button--danger");
  confirm.addEventListener("click", () => services.library.deleteStory(item));
  const cancel = button(documentRef, COPY.cancelDelete);
  cancel.addEventListener("click", () => {
    viewState.confirmDelete = false;
    rerender();
  });
  warning.append(confirm, cancel);
  section.append(warning);
  return section;
}

function loreLocationAction(documentRef, services, item) {
  if (item.kind !== "lore" || !item.reusable) return null;
  const story = services.store.getSnapshot().story;
  const section = node(documentRef, "section", "ui-library-detail__location");
  section.append(node(documentRef, "h4", "ui-heading ui-heading--3", "Create a lived location"));
  if (!story?.data?.chat?.id) {
    section.append(node(documentRef, "p", "ui-muted", "Open the Story that should own the location, then return to this Lore."));
    return section;
  }
  if (story.frameId !== null && story.frameId !== undefined) {
    section.append(node(documentRef, "p", "ui-muted", "Return to the Story's present frame before creating a lived location."));
    return section;
  }
  const draft = loreLocationDrafts.get(item.key) || { enabled: true, brief: item.summary || item.name || "", horizonHours: 168, characterHistories: [] };
  loreLocationDrafts.set(item.key, draft);
  const host = node(documentRef, "div", "");
  mountLivedLocationFields({ document: documentRef, target: host, value: draft, title: "Location preparation", onChange(value) { loreLocationDrafts.set(item.key, value); } });
  const run = button(documentRef, "Create lived location", "ui-button ui-button--primary");
  run.addEventListener("click", () => services.library.generateLocationFromLore(item, loreLocationDrafts.get(item.key)));
  section.append(host, run);
  return section;
}

function storyOverview(documentRef, services, library, item) {
  const authoring = library?.authoring;
  if (item.kind !== "story" || authoring?.owner !== item.key
      || !authoring.overview) return null;
  const overview = authoring.overview;
  const section = node(documentRef, "section", "ui-library-detail__overview");
  section.append(node(documentRef, "h4", "ui-heading ui-heading--3", COPY.storyOverview));
  const ledger = node(documentRef, "dl", "ui-library-detail__overview-ledger");
  for (const [label, value] of [
    [COPY.connectedCast, overview.cast?.length || 0],
    [COPY.connectedPlayers, overview.personas?.length || 0],
    [COPY.connectedLore, overview.lore?.length || 0],
    [COPY.recentActivity, COPY.turnsRecorded.replace(
      "${count}", String(overview.activity?.turn_count || 0),
    )],
  ]) {
    ledger.append(
      node(documentRef, "dt", "ui-muted", label),
      node(documentRef, "dd", "", String(value)),
    );
  }
  section.append(ledger);
  const latest = overview.activity?.recent?.[0];
  if (latest?.id) {
    const help = node(documentRef, "p", "ui-muted", COPY.branchHelp);
    const branch = button(
      documentRef,
      authoring.status === "branching" ? COPY.branching : COPY.branchLatest,
      "ui-button ui-button--quiet",
    );
    branch.disabled = authoring.status === "branching";
    branch.addEventListener("click", () => services.authoring.branchStory(latest.id));
    section.append(help, branch);
  }
  if (overview.issues?.length) {
    const warning = node(documentRef, "div", "ui-notice");
    warning.dataset.tone = "warning";
    warning.append(
      node(documentRef, "strong", "", COPY.setupIssues),
      node(documentRef, "p", "", overview.issues.map(issue => (
        issue.code === "missing-player-persona"
          ? COPY.primaryPersonaChange
          : "Connected lore is missing its reusable origin."
      )).join(" ")),
    );
    section.append(warning);
  }
  return section;
}

function renderDetail(documentRef, services, target, library, viewState, rerender) {
  const item = library?.selected;
  const wrapper = node(documentRef, "div", "ui-library-detail-host");
  const undo = undoNotice(documentRef, services, library);
  if (library?.unavailableItem) {
    wrapper.append(stateBlock(documentRef, "unavailable", COPY.unavailable, COPY.unavailableDetail));
    if (undo) wrapper.append(undo);
    target.replaceChildren(wrapper);
    return COPY.unavailable;
  }
  if (!item) {
    wrapper.append(stateBlock(documentRef, "empty", COPY.choose, COPY.chooseDetail));
    if (undo) wrapper.append(undo);
    target.replaceChildren(wrapper);
    return COPY.libraryDetails;
  }
  const article = node(documentRef, "article", "ui-library-detail");
  const kind = node(documentRef, "p", "ui-library-detail__kind", KIND_LABELS[item.kind] || COPY.libraryItem);
  const title = node(documentRef, "h3", "ui-heading ui-heading--2", item.name || COPY.untitled);
  const summary = node(documentRef, "p", "ui-library-detail__summary",
    item.summary || COPY.noSummary);
  const favorite = button(
    documentRef,
    services.library.isFavorite(item.key) ? COPY.unfavorite : COPY.favorite,
  );
  favorite.addEventListener("click", () => {
    const active = services.library.toggleFavorite(item.key);
    favorite.textContent = active ? COPY.unfavorite : COPY.favorite;
  });
  article.append(kind, title, summary, favorite);
  const currentMutation = library.mutation?.routeOwner === library.owner
    ? library.mutation : null;
  if (currentMutation?.status === "saving") {
    article.append(stateBlock(documentRef, "loading", COPY.savingChange, COPY.waitingEngine));
  } else if (currentMutation?.status === "error") {
    article.append(stateBlock(documentRef, "error", COPY.changeNotSaved, currentMutation.message));
  }
  const associations = node(documentRef, "section", "ui-library-detail__associations");
  associations.append(node(documentRef, "h4", "ui-heading ui-heading--3", COPY.associations));
  if (!item.associations?.length) {
    associations.append(node(documentRef, "p", "ui-muted", COPY.noAssociations));
  } else {
    const list = node(documentRef, "ul", "ui-library-detail__usage-list");
    for (const association of item.associations) {
      const row = node(documentRef, "li", "ui-library-detail__usage");
      row.append(
        node(documentRef, "strong", "", association.story_name || COPY.untitledStory),
        node(documentRef, "span", "ui-state-marker", String(association.state || "used")
          .replace(/(^|[-_])([a-z])/g, (_match, lead, letter) => `${lead ? " " : ""}${letter.toUpperCase()}`)),
      );
      const action = associationAction(documentRef, services, item, association);
      if (action) row.append(action);
      list.append(row);
    }
    associations.append(list);
  }
  article.append(associations);
  const overview = storyOverview(documentRef, services, library, item);
  if (overview) article.append(overview);
  const add = addToStory(documentRef, services, library, item);
  if (add) article.append(add);
  const location = loreLocationAction(documentRef, services, item);
  if (location) article.append(location);
  article.append(lifecycleActions(documentRef, services, library, item, viewState, rerender));
  if (undo) article.append(undo);
  wrapper.append(article);
  target.replaceChildren(wrapper);
  return item.name || COPY.libraryDetails;
}

export function mountLibraryDetail(options = {}) {
  const documentRef = options.document || document;
  const { services, target, onTitle } = options;
  target.dataset.libraryDetailHost = "true";
  const viewState = { confirmDelete: false };
  let currentLibrary = services.store.getSnapshot().library;
  const rerender = () => render(currentLibrary);
  const render = library => {
    currentLibrary = library;
    const title = renderDetail(
      documentRef, services, target, library, viewState, rerender,
    );
    services.localizer.localize(target);
    onTitle?.(title);
  };
  const unsubscribe = services.store.subscribe(state => state.library, render);
  render(services.store.getSnapshot().library);
  return Object.freeze({ teardown: unsubscribe });
}
