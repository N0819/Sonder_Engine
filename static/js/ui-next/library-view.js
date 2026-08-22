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
    control.addEventListener("click", () => navigate(services, activeType, {
      ...query,
      item: "",
      scope: scope === "all" ? "" : scope,
    }));
    item.append(control);
    scopeList.append(item);
  }
  rail.append(scopeTitle, scopeList);
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
  form.addEventListener("submit", event => {
    event.preventDefault();
    navigate(services, activeType, { ...query, item: "", q: input.value.trim() });
  });
  form.append(label, submit, sortLabel);
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

function renderDetail(documentRef, services, target, library) {
  const item = library?.selected;
  if (library?.unavailableItem) {
    target.replaceChildren(stateBlock(
      documentRef, "unavailable", COPY.unavailable, COPY.unavailableDetail,
    ));
    return COPY.unavailable;
  }
  if (!item) {
    target.replaceChildren(stateBlock(documentRef, "empty", COPY.choose, COPY.chooseDetail));
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
      list.append(row);
    }
    associations.append(list);
  }
  article.append(associations);
  target.replaceChildren(article);
  return item.name || "Library details";
}

export function mountLibraryDetail(options = {}) {
  const documentRef = options.document || document;
  const { services, target, onTitle } = options;
  target.dataset.libraryDetailHost = "true";
  const render = library => {
    const title = renderDetail(documentRef, services, target, library);
    onTitle?.(title);
  };
  const unsubscribe = services.store.subscribe(state => state.library, render);
  render(services.store.getSnapshot().library);
  return Object.freeze({ teardown: unsubscribe });
}
