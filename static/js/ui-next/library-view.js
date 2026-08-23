export const MODULE_RELEASE = "alpha98-ui1";

import { mountLivedLocationFields } from "./lived-location.js?release=alpha98-ui1";
import { openNewStory } from "./new-story.js?release=alpha98-ui1";

const loreLocationDrafts = new Map();

// UI_CATALOG_START: Library discovery and detail copy.
const COPY = Object.freeze({
  search: "Search Library",
  searchAction: "Search",
  sort: "Sort Library",
  filters: "Library categories and scopes",
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
  all: "All",
  allItems: "All Library items",
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
  scope: "Scope",
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
  reusableMaterial: "Reusable story material",
  yourMaterial: "Your story material",
  browseStories: "Browse stories",
  createStory: "Create a story",
  continueStory: "Continue a story",
  recentStories: "Recent stories",
  scopeSummary: "Library scope",
  everyReusableItem: "Every reusable item on this installation.",
  itemsShown: "Items shown",
  currentScope: "Current scope",
  viewOptions: "View options",
  library: "Library",
  libraryScope: "Library / Scope",
  allLibrary: "All Library",
  newStory: "New story",
  lorebooks: "Lorebooks",
  reusableMaterialTitle: "Reusable material",
  reusableMaterialDetail: "Use a story lens when you need a project-like view. Characters, personas, and lore remain reusable.",
  reusableAssets: "Reusable assets",
  openStoryLabel: "Open story",
  searchThisView: "Search this view",
  activeStory: "Active story",
  moreFor: "More actions for ${name}",
});
// UI_CATALOG_END

const TYPES = Object.freeze([
  ["", COPY.all, COPY.allItems],
  ["story", COPY.stories, COPY.stories],
  ["character", COPY.characters, COPY.characters],
  ["persona", COPY.personas, COPY.personas],
  ["lore", COPY.lore, COPY.lore],
]);
const SCOPES = Object.freeze([
  ["all", COPY.all],
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
  use.setAttribute("href", `/static/assets/icons/sonder-icons.svg#icon-${name}`);
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

function filterRail(documentRef, services, state) {
  const route = state.route || {};
  const query = routeQuery(route);
  const activeType = typeForRoute(route);
  const activeScope = query.scope || "all";
  const rail = node(documentRef, "nav", "ui-library__filters");
  rail.setAttribute("aria-label", COPY.filters);

  const head = node(documentRef, "header", "ui-library__side-head");
  const heading = node(documentRef, "div");
  const sideTitle = node(documentRef, "h2", "ui-library__side-title", COPY.allLibrary);
  sideTitle.tabIndex = -1;
  sideTitle.dataset.focusIdentity = "destination:library";
  heading.append(
    node(documentRef, "p", "ui-library__breadcrumb", COPY.libraryScope),
    sideTitle,
  );
  const search = node(documentRef, "form", "ui-library__side-search");
  search.setAttribute("role", "search");
  const searchInput = node(documentRef, "input", "ui-input");
  searchInput.type = "search";
  searchInput.value = query.q || "";
  searchInput.placeholder = COPY.searchThisView;
  searchInput.setAttribute("aria-label", COPY.search);
  searchInput.maxLength = 200;
  search.addEventListener("submit", event => {
    event.preventDefault();
    navigate(services, activeType || "story", { ...query, item: "", q: searchInput.value.trim() });
  });
  search.append(searchInput);

  const scope = node(documentRef, "select", "ui-input ui-library__scope");
  scope.setAttribute("aria-label", COPY.scope);
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
  head.append(heading, search, scope,
    node(documentRef, "p", "ui-library__scope-note", COPY.everyReusableItem));
  rail.append(head);

  const typeList = node(documentRef, "ul", "ui-library__filter-list ui-library__tabs");
  for (const [type, label, accessible] of TYPES.filter(([type]) => type)) {
    const item = node(documentRef, "li");
    const control = button(documentRef, label, "ui-library__filter");
    control.setAttribute("aria-label", accessible);
    if (type === (activeType || "story")) control.setAttribute("aria-current", "page");
    control.addEventListener("click", () => navigate(services, type, { ...query, item: "" }));
    item.append(control);
    typeList.append(item);
  }
  rail.append(typeList);
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
    rail.append(storyLabel);
  }
  const railState = { ...state, library: {
    ...(state.library || {}),
    items: (state.library?.items || []).filter(item => item.kind === (activeType || "story")),
  } };
  const status = resultState(documentRef, railState.library);
  if (status) rail.append(status);
  if (railState.library.items?.length) rail.append(ledger(documentRef, services, railState));

  const actions = node(documentRef, "div", "ui-library__side-actions");
  const create = labelWithIcon(documentRef,
    button(documentRef, COPY.newStory, "ui-button ui-button--primary"), "plus", COPY.newStory);
  create.addEventListener("click", () => openNewStory({ document: documentRef, services }));
  const importStory = labelWithIcon(documentRef,
    button(documentRef, COPY.importStory, "ui-button ui-button--quiet"), "import", COPY.importStory);
  importStory.addEventListener("click", () => navigate(services, "story", {
    mode: "import", session: workflowSession(),
  }));
  actions.append(create, importStory);
  rail.append(actions);
  return rail;
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
  if (!activeType || activeType === "story") {
    const importStory = button(documentRef, COPY.importStory);
    importStory.addEventListener("click", () => {
      navigate(services, "story", { mode: "import", session: workflowSession() });
      documentRef.dispatchEvent(new CustomEvent("sonder:library-select", {
        detail: { workflow: "story-import" },
      }));
    });
    form.append(importStory);
  }
  if (activeType === "character" || activeType === "persona") {
    const isCharacter = activeType === "character";
    const create = button(documentRef, isCharacter ? COPY.createCharacter : COPY.createPersona);
    create.addEventListener("click", () => navigate(services, activeType, {
      mode: "create", session: workflowSession(),
    }));
    const importPerson = button(documentRef, isCharacter ? COPY.importCharacter : COPY.importPersona);
    importPerson.addEventListener("click", () => navigate(services, activeType, {
      mode: "import", session: workflowSession(),
    }));
    const createCluster = node(documentRef, "div", "ui-action-cluster ui-library__create-cluster");
    createCluster.setAttribute("role", "group");
    createCluster.append(create, importPerson);
    form.append(createCluster);
  }
  return form;
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
    const more = button(documentRef, "…", "ui-library__more");
    more.setAttribute("aria-label", COPY.moreFor.replace("${name}", item.name || COPY.untitled));
    more.addEventListener("click", selectItem);
    row.append(control, more);
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

function libraryHome(documentRef, services, library) {
  const route = library?.route || {};
  const home = services.library.homeState();
  const byKey = new Map((library.items || []).map(item => [item.key, item]));
  const section = node(documentRef, "section", "ui-library-home");
  section.dataset.libraryHome = "true";

  const toolbar = node(documentRef, "header", "ui-library-home__toolbar");
  const title = node(documentRef, "div");
  title.append(
    node(documentRef, "p", "ui-library__kicker", COPY.library),
    node(documentRef, "h2", "ui-library-home__title", COPY.yourMaterial),
  );
  const actions = node(documentRef, "div", "ui-library-home__actions");
  const browse = labelWithIcon(documentRef,
    button(documentRef, COPY.browseStories, "ui-button ui-button--quiet"), "filter", COPY.browseStories);
  browse.addEventListener("click", () => navigate(services, "story", {}));
  const create = labelWithIcon(documentRef,
    button(documentRef, COPY.createStory, "ui-button ui-button--primary"), "plus", COPY.createStory);
  create.addEventListener("click", () => openNewStory({ document: documentRef, services }));
  actions.append(browse, create);
  toolbar.append(title, actions);

  const facets = library.facets || {};
  const summary = node(documentRef, "div", "ui-library-home__summary");
  summary.setAttribute("aria-label", "Library totals");
  for (const [kind, label, index] of [
    ["story", COPY.stories, "01"],
    ["character", COPY.characters, "02"],
    ["persona", COPY.personas, "03"],
    ["lore", COPY.lorebooks, "04"],
  ]) {
    const stat = node(documentRef, "button", "ui-library-stat");
    stat.type = "button";
    stat.append(
      node(documentRef, "span", "ui-library-stat__index", index),
      icon(documentRef, ({ story: "story", character: "character", persona: "persona", lore: "lore" })[kind]),
      node(documentRef, "strong", "ui-library-stat__value", String(facets.types?.[kind] || 0)),
      node(documentRef, "span", "ui-library-stat__label", label),
    );
    stat.addEventListener("click", () => navigate(services, kind, {}));
    summary.append(stat);
  }

  const recent = node(documentRef, "section", "ui-library-home__recent");
  const recentHead = node(documentRef, "header", "ui-library-section-heading");
  const recentTitle = node(documentRef, "div");
  recentTitle.append(
    node(documentRef, "p", "ui-library__kicker", COPY.recentStories),
    node(documentRef, "h3", "", COPY.continueStory),
  );
  recentHead.append(recentTitle, node(documentRef, "span", "ui-library-section-code", "LIB / 01"));

  const overview = node(documentRef, "div", "ui-library-home__overview");
  const recentList = node(documentRef, "ol", "ui-library-home__stories");
  let recentStories = home.recents.map(key => byKey.get(key)).filter(item => item?.kind === "story");
  if (!recentStories.length) recentStories = (library.items || []).filter(item => item.kind === "story").slice(0, 5);
  if (!recentStories.length) {
    recentList.append(node(documentRef, "li", "ui-library-home__none", COPY.noneYet));
  }
  for (const [position, item] of recentStories.entries()) {
    const row = node(documentRef, "li");
    const control = button(documentRef, "", "ui-library-home__story");
    control.append(
      node(documentRef, "span", "ui-library__index", String(position + 1).padStart(2, "0")),
      icon(documentRef, "story"),
      node(documentRef, "strong", "", item.name || COPY.untitled),
      node(documentRef, "span", "ui-library-home__story-meta", usage(item)),
      icon(documentRef, "chevron-right"),
    );
    control.addEventListener("click", () => navigate(services, "story", { item: item.key }));
    row.append(control);
    recentList.append(row);
  }

  const context = node(documentRef, "aside", "ui-library-home__context");
  context.append(
    node(documentRef, "p", "ui-library__kicker", "Scope / Context"),
    node(documentRef, "h3", "", COPY.reusableMaterialTitle),
    node(documentRef, "p", "ui-library-home__context-copy", COPY.reusableMaterialDetail),
  );
  const meta = node(documentRef, "dl", "ui-library-home__context-meta");
  for (const [label, value] of [
    [COPY.scope, route.scope || "all"],
    [COPY.stories, library.facets?.types?.story || 0],
    [COPY.reusableAssets, Math.max(0, (library.page?.total || 0) - (library.facets?.types?.story || 0))],
    [COPY.openStoryLabel, library.chats?.[0]?.name || "—"],
  ]) {
    const row = node(documentRef, "div");
    row.append(node(documentRef, "dt", "", label), node(documentRef, "dd", "", String(value)));
    meta.append(row);
  }
  context.append(meta);
  overview.append(recentList, context);
  recent.append(recentHead, overview);
  section.append(toolbar, summary, recent);
  return section;
}

export function createLibraryView(options = {}) {
  const documentRef = options.document || document;
  const { services, state } = options;
  const section = node(documentRef, "section", "ui-library");
  section.dataset.libraryView = "true";
  const rail = filterRail(documentRef, services, state);
  const content = node(documentRef, "div", "ui-library__content");
  const library = state.library || {};
  const home = libraryHome(documentRef, services, library);
  if (home) content.append(home);
  const undo = undoNotice(documentRef, services, library);
  if (undo) content.prepend(undo);
  if (library.notice) {
    const notice = node(documentRef, "p", "ui-notice ui-library__notice", library.notice);
    notice.setAttribute("role", "status");
    content.append(notice);
  }
  if (!home) content.append(toolbar(documentRef, services, state));
  section.append(rail, content);
  const routeIdentity = state.route?.canonicalHash || "#/library";
  const scrollRegion = content;
  scrollRegion.scrollTop = services.library.scrollFor(routeIdentity);
  const onScroll = () => services.library.saveScroll(routeIdentity, scrollRegion.scrollTop);
  scrollRegion.addEventListener("scroll", onScroll, { passive: true });
  return Object.freeze({
    element: section,
    teardown: () => scrollRegion.removeEventListener("scroll", onScroll),
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
