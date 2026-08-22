export const MODULE_RELEASE = "wp06.1";

const TYPES = Object.freeze([
  ["", "All", "All Library items"],
  ["story", "Stories", "Stories"],
  ["character", "Characters", "Characters"],
  ["persona", "Personas", "Personas"],
  ["lore", "Lore", "Lore"],
]);
const SCOPES = Object.freeze([
  ["all", "All"],
  ["story", "Chosen story"],
  ["unassigned", "Not used"],
  ["multiple", "Multiple stories"],
]);
const KIND_LABELS = Object.freeze({
  story: "Story",
  character: "Character",
  persona: "Persona",
  lore: "Lore",
});

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
  exportStory: "Export story",
  deleteStory: "Delete story…",
  confirmDeleteStory: "Delete this story",
  cancelDelete: "Keep story",
  deleteWarning: "This permanently removes the complete story, its history, and story-owned lore. Reusable Characters, Personas, and original Lore remain.",
});
// UI_CATALOG_END

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
  if (!associations.length) return "Not used";
  if (associations.length === 1) return associations[0].story_name || "Used in one story";
  return `Used in ${associations.length} stories`;
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

function filterRail(documentRef, services, state) {
  const route = state.route || {};
  const query = routeQuery(route);
  const activeType = typeForRoute(route);
  const activeScope = query.scope || "all";
  const rail = node(documentRef, "nav", "ui-library__filters");
  rail.setAttribute("aria-label", COPY.filters);

  const typeList = node(documentRef, "ul", "ui-library__filter-list");
  for (const [type, label, accessible] of TYPES) {
    const item = node(documentRef, "li");
    const control = button(documentRef, label, "ui-library__filter");
    control.setAttribute("aria-label", accessible);
    if (type === activeType) control.setAttribute("aria-current", "page");
    control.addEventListener("click", () => navigate(services, type, { ...query, item: "" }));
    item.append(control);
    typeList.append(item);
  }
  rail.append(typeList);

  const scopeTitle = node(documentRef, "p", "ui-library__filter-title", "Scope");
  const scopeList = node(documentRef, "ul", "ui-library__filter-list");
  for (const [scope, label] of SCOPES) {
    const item = node(documentRef, "li");
    const control = button(documentRef, label, "ui-library__filter ui-library__filter--scope");
    if (scope === activeScope) control.setAttribute("aria-current", "page");
    control.addEventListener("click", () => {
      const firstStory = state.library?.chats?.[0]?.id;
      navigate(services, activeType, {
        ...query,
        item: "",
        scope: scope === "all" ? "" : scope,
        story: scope === "story" ? (query.story || firstStory || "") : query.story,
      });
    });
    item.append(control);
    scopeList.append(item);
  }
  rail.append(scopeTitle, scopeList);
  const stories = state.library?.chats || [];
  if (stories.length) {
    const storyLabel = node(documentRef, "label", "ui-field ui-library__story-scope");
    storyLabel.append(node(documentRef, "span", "ui-field__label", "Story scope"));
    const story = node(documentRef, "select", "ui-input");
    story.setAttribute("aria-label", "Story scope");
    for (const row of stories) {
      const option = node(documentRef, "option", "", row.name || "Untitled story");
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
    ["name", "Name"], ["type", "Type"], ["created", "Created"], ["usage", "Story use"],
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
  visibilityLabel.append(node(documentRef, "span", "ui-field__label", "Library visibility"));
  const visibility = node(documentRef, "select", "ui-input");
  visibility.setAttribute("aria-label", "Library visibility");
  for (const [value, text] of [["active", "Active items"], ["archived", "Archived items"]]) {
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
    if (query.item === item.key) control.setAttribute("aria-current", "true");
    const index = node(documentRef, "span", "ui-library__index", String(item.id).padStart(2, "0"));
    index.setAttribute("aria-hidden", "true");
    const copy = node(documentRef, "span", "ui-library__item-copy");
    const name = node(documentRef, "strong", "ui-library__name", item.name || "Untitled");
    const meta = node(documentRef, "span", "ui-library__meta");
    meta.append(
      node(documentRef, "span", "ui-library__kind", KIND_LABELS[item.kind] || "Library item"),
      node(documentRef, "span", "ui-library__usage", usage(item)),
    );
    if (item.summary) copy.append(name, node(documentRef, "span", "ui-library__summary", item.summary), meta);
    else copy.append(name, meta);
    control.append(index, copy);
    control.addEventListener("click", () => {
      services.library.recordRecent(item.key);
      navigate(services, activeType, { ...query, item: item.key });
      documentRef.dispatchEvent(new CustomEvent("sonder:library-select", {
        detail: { item: item.key },
      }));
    });
    row.append(control);
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
      library.items?.length ? COPY.preserved : "Try again when the engine is available.");
  }
  if (library.status === "empty") {
    const filtered = Boolean(library.route?.q || library.route?.type
      || library.route?.scope !== "all");
    return stateBlock(documentRef, "empty", filtered ? COPY.noResults : COPY.empty,
      filtered ? COPY.noResultsDetail : COPY.emptyDetail);
  }
  return null;
}

export function createLibraryView(options = {}) {
  const documentRef = options.document || document;
  const { services, state } = options;
  const section = node(documentRef, "section", "ui-library");
  section.dataset.libraryView = "true";
  const rail = filterRail(documentRef, services, state);
  const content = node(documentRef, "div", "ui-library__content");
  content.append(toolbar(documentRef, services, state));
  const library = state.library || {};
  if (library.notice) {
    const notice = node(documentRef, "p", "ui-notice ui-library__notice", library.notice);
    notice.setAttribute("role", "status");
    content.append(notice);
  }
  const status = resultState(documentRef, library);
  if (status) content.append(status);
  if (library.items?.length) content.append(ledger(documentRef, services, state));
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
    node(documentRef, "p", "", library.undo.message || "Library change saved."),
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
      ? "Remove from active cast" : "Restore to active cast";
  } else if (item.kind === "persona") {
    if (association.state === "primary") {
      return node(documentRef, "span", "ui-muted", "Primary persona · change in Story setup");
    }
    label = association.state === "active"
      ? "Remove additional player" : "Restore additional player";
  } else if (item.kind === "lore" && item.reusable
      && ["attached", "disabled", "canon"].includes(association.state)) {
    label = "Detach from story";
  }
  if (!label) return null;
  const control = button(documentRef, label);
  control.addEventListener("click", () => services.library.setAssociation(item, association));
  return control;
}

function addToStory(documentRef, services, library, item) {
  if (item.kind === "story" || !item.reusable) return null;
  const used = new Set((item.associations || []).map(row => Number(row.story_id)));
  const stories = (library.chats || []).filter(story => !used.has(Number(story.id)));
  if (!stories.length) return null;
  const section = node(documentRef, "section", "ui-library-detail__add");
  section.append(node(documentRef, "h4", "ui-heading ui-heading--3", "Add to a story"));
  const controls = node(documentRef, "div", "ui-tool-inline");
  const select = node(documentRef, "select", "ui-input");
  select.setAttribute("aria-label", `Story for ${item.name || "Library item"}`);
  for (const story of stories) {
    const option = node(documentRef, "option", "", story.name || "Untitled story");
    option.value = story.id;
    select.append(option);
  }
  const add = button(documentRef, "Add to story", "ui-button ui-button--primary");
  add.addEventListener("click", () => services.library.addToStory(item, select.value));
  controls.append(select, add);
  section.append(controls);
  return section;
}

function lifecycleActions(documentRef, services, library, item, viewState, rerender) {
  const section = node(documentRef, "section", "ui-library-detail__actions");
  const archive = button(
    documentRef,
    `${item.archived ? "Restore" : "Archive"} ${KIND_LABELS[item.kind]?.toLowerCase() || "item"}`,
  );
  archive.addEventListener("click", () => services.library.setArchived(item, !item.archived));
  section.append(archive);
  if (item.kind !== "story") return section;

  const open = button(documentRef, COPY.openStory, "ui-button ui-button--primary");
  open.addEventListener("click", () => services.router.navigate({
    destination: "play", query: { chat: String(item.id) },
  }));
  const exported = node(documentRef, "a", "ui-button ui-button--quiet", COPY.exportStory);
  exported.href = `/api/chats/${item.id}/export`;
  exported.download = `${item.name || "story"}.json`;
  section.prepend(open, exported);

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
    return "Library details";
  }
  const article = node(documentRef, "article", "ui-library-detail");
  const kind = node(documentRef, "p", "ui-library-detail__kind", KIND_LABELS[item.kind] || "Library item");
  const title = node(documentRef, "h3", "ui-heading ui-heading--2", item.name || "Untitled");
  const summary = node(documentRef, "p", "ui-library-detail__summary",
    item.summary || "No public summary has been added.");
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
    article.append(stateBlock(documentRef, "loading", "Saving Library change…", "Waiting for the engine to accept it."));
  } else if (currentMutation?.status === "error") {
    article.append(stateBlock(documentRef, "error", "Library change was not saved", currentMutation.message));
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
        node(documentRef, "strong", "", association.story_name || "Untitled story"),
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
  const add = addToStory(documentRef, services, library, item);
  if (add) article.append(add);
  article.append(lifecycleActions(documentRef, services, library, item, viewState, rerender));
  if (undo) article.append(undo);
  wrapper.append(article);
  target.replaceChildren(wrapper);
  return item.name || "Library details";
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
    onTitle?.(title);
  };
  const unsubscribe = services.store.subscribe(state => state.library, render);
  render(services.store.getSnapshot().library);
  return Object.freeze({ teardown: unsubscribe });
}
