"use strict";

const LORE_INHERITANCE_MODES = [
  "inherit",
  "isolated",
  "reference_only"
];

const DEFAULT_LORE_LINK_TYPES = [
  "related",
  "references",
  "depends_on",
  "supplements",
  "overlaps",
  "supersedes",
  "contradicts",
  "alternate_version",
  "same_setting",
  "portal"
];

const loreUI = {
  selectedId: null,
  selectedTab: "entries",
  expanded: new Set(),
  sidebarExpanded: new Set(),
  dragId: null,
  filter: "",
  entryFilter: "",
  entryCategory: "",
  plan: null,
  rendering: false
};

function loreBookTypeIcon(type) {
  return {
    general: "📚",
    world: "🌍",
    knowledge: "🧠",
    location: "📍",
    system: "⚙",
    characters: "👥",
    events: "⏳"
  }[type] || "📖";
}

function loreLinkTypes() {
  return (
    S.boot?.lorebook_link_types
    || DEFAULT_LORE_LINK_TYPES
  );
}

function normalizeLoreBook(book) {
  return {
    ...book,
    id: Number(book.id),
    parent_id: book.parent_id == null
      ? null
      : Number(book.parent_id),
    chat_id: book.chat_id == null
      ? null
      : Number(book.chat_id),
    sort_order: Number(book.sort_order || 0),
    entry_count: Number(book.entry_count || 0),
    book_type: book.book_type || book.type || "general",
    inheritance_mode: book.inheritance_mode || "inherit",
    summary: book.summary || ""
  };
}

function loreOwnershipKey(book) {
  return book.chat_id == null
    ? "library"
    :`chat:${book.chat_id}`;
}

function loreBooksByParent(books) {
  const result = new Map();

  for (const book of books) {
    const key = book.parent_id == null
      ? "root"
      : String(book.parent_id);

    if (!result.has(key)) {
      result.set(key, []);
    }

    result.get(key).push(book);
  }

  for (const children of result.values()) {
    children.sort((a, b) => {
      return (
        a.sort_order - b.sort_order
        || a.name.localeCompare(b.name)
      );
    });
  }

  return result;
}

function loreBookMatches(book, filter) {
  if (!filter) {
    return true;
  }

  const haystack = [
    book.name,
    book.book_type,
    book.summary,
    book.scope_world_id,
    book.scope_location_id
  ].join(" ").toLowerCase();

  return haystack.includes(filter.toLowerCase());
}

function loreVisibleIds(books, filter) {
  // Filter values are stored raw (untrimmed) while typing; trim only here,
  // where the filter is actually applied.
  filter = (filter || "").trim();
  if (!filter) {
    return new Set(books.map(book => book.id));
  }

  const byId = new Map(
    books.map(book => [book.id, book])
  );
  const visible = new Set();

  for (const book of books) {
    if (!loreBookMatches(book, filter)) {
      continue;
    }

    visible.add(book.id);

    let current = book;
    const visited = new Set();

    while (
      current
      && current.parent_id != null
      && !visited.has(current.parent_id)
    ) {
      visited.add(current.parent_id);
      visible.add(current.parent_id);
      current = byId.get(current.parent_id);
    }
  }

  return visible;
}

function loreBookLabel(book) {
  return book.name ||`Lorebook ${book.id}`;
}

function parseStoredJSON(value, fallback) {
  if (value == null || value === "") {
    return fallback;
  }

  if (typeof value === "object") {
    return value;
  }

  try {
    return JSON.parse(value);
  } catch (error) {
    return fallback;
  }
}

function loreField(label, node, className = "") {
  return el(
    "div",
    { class: className },
    el("label", {}, label),
    node
  );
}

function loreSelect(options, value) {
  return el(
    "select",
    {},
    options.map(option => {
      const pair = Array.isArray(option)
        ? option
        : [option, option];

      return el(
        "option",
        {
          value: pair[0],
          ...(String(pair[0]) === String(value)
            ? { selected: "" }
            : {})
        },
        pair[1]
      );
    })
  );
}

function loreBookOptions(books, value, includeRoot = false) {
  const options = [];

  if (includeRoot) {
    options.push(el(
      "option",
      {
        value: "",
        ...(value == null ? { selected: "" } : {})
      },
      "(root)"
    ));
  }

  for (const book of books) {
    options.push(el(
      "option",
      {
        value: book.id,
        ...(Number(value) === book.id
          ? { selected: "" }
          : {})
      },
`${loreBookTypeIcon(book.book_type)} ${book.name}`
    ));
  }

  return options;
}

// ---- Library sidebar -------------------------------------------------------

function renderLoreLibrarySidebar(list, actions) {
  const books = (S.boot.lorebooks || [])
    .map(normalizeLoreBook);

  const byParent = loreBooksByParent(books);
  const visible = loreVisibleIds(books, loreUI.filter);
  const byId = new Map(
    books.map(book => [book.id, book])
  );
  const tree = el("div", { class: "lore-side-tree" });

  const roots = books.filter(book => {
    return (
      book.parent_id == null
      || !byId.has(book.parent_id)
    );
  });

  function renderNode(book) {
    if (!visible.has(book.id)) {
      return null;
    }

    const children = (byParent.get(String(book.id)) || [])
      .filter(child => visible.has(child.id));

    const expanded = (
      loreUI.sidebarExpanded.has(book.id)
      || Boolean(loreUI.filter)
    );

    const toggle = el(
      "button",
      {
        class: "lore-side-toggle",
        title: children.length
          ? "Expand or collapse"
          : "No children",
        disabled: !children.length,
        onclick: event => {
          event.stopPropagation();
          if (!children.length) return;

          const nodeEl = event.currentTarget.closest(
            ".lore-side-node"
          );
          const isExpanded = nodeEl
            ? nodeEl.classList.contains("expanded")
            : false;

          if (isExpanded) {
            loreUI.sidebarExpanded.delete(book.id);
            if (nodeEl)
              nodeEl.classList.remove("expanded");
            event.currentTarget.textContent = "▸";
          } else {
            loreUI.sidebarExpanded.add(book.id);
            if (nodeEl)
              nodeEl.classList.add("expanded");
            event.currentTarget.textContent = "▾";
          }
        }
      },
      children.length
        ? (expanded ? "▾" : "▸")
        : "·"
    );

    const row = el(
      "div",
      {
        class:
          "lore-side-row"
          + (loreUI.selectedId === book.id
            ? " on"
            : ""),
        draggable: "true",
        onclick: () => openLoreWorkspace(book.id),
        ondragstart: event => {
          loreUI.dragId = book.id;
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData(
            "text/plain",
            String(book.id)
          );
        },
        ondragover: event => {
          const dragged = Number(
            event.dataTransfer.getData("text/plain")
            || loreUI.dragId
          );
          if (dragged && dragged !== book.id) {
            event.preventDefault();
            row.classList.add("drag-over");
          }
        },
        ondragleave: () => {
          row.classList.remove("drag-over");
        },
        ondrop: async event => {
          event.preventDefault();
          row.classList.remove("drag-over");
          const dragged = Number(
            event.dataTransfer.getData("text/plain")
            || loreUI.dragId
          );
          if (!dragged || dragged === book.id) {
            return;
          }
          await moveLoreBook(dragged, book.id, null);
        }
      },
      toggle,
      el(
        "span",
        {
          class: "lore-side-name",
          title: book.name
        },
        `${loreBookTypeIcon(book.book_type)} ${book.name}`
      ),
      el(
        "span",
        { class: "lore-side-meta" },
        el(
          "span",
          { class: "badge" },
          book.entry_count || ""
        )
      )
    );

    const node = el(
      "div",
      {
        class:
          "lore-side-node"
          + (expanded ? " expanded" : "")
      },
      row
    );

    // ALWAYS render children into the DOM — CSS controls visibility
    if (children.length) {
      const childBox = el(
        "div",
        { class: "lore-side-children" }
      );
      for (const child of children) {
        const childNode = renderNode(child);
        if (childNode) {
          childBox.append(childNode);
        }
      }
      node.append(childBox);
    }

    return node;
  }

  for (const root of roots) {
    const node = renderNode(root);
    if (node) {
      tree.append(node);
    }
  }

  if (!tree.children.length) {
    tree.append(emptyState("No lorebooks yet."));
  }

  list.append(tree);

  actions.append(
    el(
      "button",
      { onclick: () => createLoreBookDialog(null) },
      "+ Lorebook"
    ),
    el(
      "button",
      { onclick: () => importModal("lorebook") },
      "⤓ Import"
    ),
    el(
      "button",
      {
        title: "Search lorebook tree",
        onclick: async () => {
          const value = await promptModal(
            "Filter lorebooks:",
            loreUI.filter
          );
          if (value == null) {
            return;
          }
          loreUI.filter = value.trim();
          renderSide();
        }
      },
      loreUI.filter ? "⌕ Clear/filter" : "⌕ Filter"
    )
  );
}

// ---- Data loading ----------------------------------------------------------

async function loadLoreWorkspaceData(selectedId) {
  const selectedResponse = await api(
    "GET",
`/api/lorebooks/${selectedId}`
  );

  const selectedBook = normalizeLoreBook(
    selectedResponse.book
  );

  let candidates = [];

  if (selectedBook.chat_id == null) {
    candidates = (S.boot.lorebooks || [])
      .map(normalizeLoreBook);
  } else {
    let chatData = S.chat;

    if (
      !chatData
      || Number(chatData.chat?.id) !== selectedBook.chat_id
    ) {
      chatData = await api(
        "GET",
`/api/chats/${selectedBook.chat_id}`
      );
    }

    const ids = new Set(
      (chatData.lorebooks || []).map(book => Number(book.id))
    );
    ids.add(selectedBook.id);

    const detailResponses = await Promise.all(
      [...ids].map(async id => {
        try {
          return await api("GET",`/api/lorebooks/${id}`);
        } catch (error) {
          return null;
        }
      })
    );

    candidates = detailResponses
      .filter(Boolean)
      .map(item => normalizeLoreBook(item.book));
  }

  if (!candidates.some(book => book.id === selectedBook.id)) {
    candidates.push(selectedBook);
  }

  const ownership = loreOwnershipKey(selectedBook);
  const scopedBooks = candidates.filter(book => {
    return loreOwnershipKey(book) === ownership;
  });

  let links = [];

  try {
    const result = await api(
      "GET",
`/api/lorebooks/${selectedId}/links`
    );
    links = result.links || [];
  } catch (error) {
    links = [];
  }

  return {
    selectedId: Number(selectedId),
    selected: selectedBook,
    selectedResponse,
    books: scopedBooks,
    allLinkTargets: collectLoreLinkTargets(
      scopedBooks,
      selectedBook
    ),
    links,
    tab: loreUI.selectedTab || "entries",
    plan: null,
    entryFilter: loreUI.entryFilter || "",
    entryCategory: loreUI.entryCategory || ""
  };
}

function collectLoreLinkTargets(scopedBooks, selectedBook) {
  const map = new Map();

  for (const book of scopedBooks) {
    map.set(book.id, book);
  }

  for (const book of S.boot.lorebooks || []) {
    const normalized = normalizeLoreBook(book);
    map.set(normalized.id, normalized);
  }

  if (
    S.chat
    && Number(S.chat.chat?.id) === selectedBook.chat_id
  ) {
    for (const book of S.chat.lorebooks || []) {
      const normalized = normalizeLoreBook(book);
      map.set(normalized.id, normalized);
    }
  }

  return [...map.values()]
    .filter(book => book.id !== selectedBook.id)
    .sort((a, b) => a.name.localeCompare(b.name));
}

// ---- Workspace -------------------------------------------------------------

// The lorebook workspace is a SINGLE persistent modal. Selecting a book in the
// tree, or refreshing after an edit, re-renders this one window in place. The
// old code called modal() every time, and modal() STACKS onto any already-open
// dialog (see components.js S.modalStack) -- so every navigation click and every
// post-edit refreshLoreUI() piled up another identical window that the user then
// had to close one at a time. openLoreWorkspace() now only opens a fresh window
// when the workspace is not already the visible modal; otherwise it swaps the
// body of the window that is already open.

function loreWorkspaceVisible() {
  if ($("#modal").classList.contains("hidden")) {
    return false;
  }
  // Either the workspace DOM is currently mounted, or a render is in flight
  // (the loading block is briefly showing between the two states).
  return (
    loreUI.rendering
    || Boolean($("#modalbody").querySelector(".lore-workspace"))
  );
}

async function renderLoreWorkspaceBody(selectedId) {
  const wanted = Number(selectedId);
  loreUI.rendering = true;

  const body = $("#modalbody");

  // On the FIRST open the modal is empty, so show a spinner. On an in-place
  // swap the workspace is already mounted -- keep it on screen and mark it
  // busy instead of tearing it down to a spinner, which visually reads as a
  // brand-new window popping open on every book click. We fetch the new book,
  // then replace the body in one atomic swap.
  const mounted = body.querySelector(".lore-workspace");
  if (mounted) {
    mounted.classList.add("lore-swapping");
  } else {
    body.innerHTML = "";
    body.append(loadingBlock("Loading lorebook…"));
  }

  try {
    const state = await loadLoreWorkspaceData(selectedId);

    // A newer selection superseded this one mid-load -- let the latest win
    // instead of clobbering it with stale content.
    if (loreUI.selectedId !== wanted) {
      return;
    }

    $("#modaltitle").textContent =
      "Lorebook workspace — " + state.selected.name;
    body.innerHTML = "";
    body.append(buildLoreWorkspace(state));
  } catch (error) {
    if (loreUI.selectedId === wanted) {
      body.innerHTML = "";
      body.append(
        emptyState("Could not load lorebook: " + error.message)
      );
    }
  } finally {
    loreUI.rendering = false;
  }
}

async function openLoreWorkspace(selectedId) {
  loreUI.selectedId = Number(selectedId);

  if (!loreWorkspaceVisible()) {
    modal(
      "Lorebook workspace",
      body => {
        body.append(loadingBlock("Loading lorebook tree…"));
      },
      { wide: true }
    );
  }

  await renderLoreWorkspaceBody(selectedId);
}

window.loreModal = openLoreWorkspace;

function renderLoreInspector(state, container) {
  container.innerHTML = "";

  const tabs = [
    {
      id: "entries",
      label: `Entries (${state.selectedResponse.entries?.length || 0})`,
      render: renderLoreEntries
    },
    {
      id: "book",
      label: "Book",
      render: renderLoreBookEditor
    },
    {
      id: "relationships",
      label: `Relationships (${state.links.length})`,
      render: renderLoreRelationshipEditor
    },
    {
      id: "generator",
      label: "Generator",
      render: renderLoreGenerator
    }
  ];

  if (!tabs.some(tab => tab.id === state.tab)) {
    state.tab = "entries";
  }

  const tabBar = el("div", { class: "lore-inspector-tabs" });
  const content = el("div", { class: "lore-inspector-content" });

  function selectTab(tabId) {
    state.tab = tabId;
    loreUI.selectedTab = tabId;

    for (const button of tabBar.querySelectorAll("button")) {
      button.classList.toggle("on", button.dataset.tab === tabId);
    }

    content.innerHTML = "";
    const selected = tabs.find(tab => tab.id === tabId);
    if (!selected) {
      content.append(emptyState("Unknown lorebook tab."));
      return;
    }
    selected.render(state, content);
  }

  for (const tab of tabs) {
    tabBar.append(el(
      "button",
      {
        "data-tab": tab.id,
        class: tab.id === state.tab ? "on" : "",
        onclick: () => selectTab(tab.id)
      },
      tab.label
    ));
  }

  container.append(tabBar, content);
  selectTab(state.tab);
}

function buildLoreWorkspace(state) {
  const workspace = el(
    "div",
    { class: "lore-workspace" }
  );

  const treePanel = el(
    "section",
    { class: "lore-panel" },
    el(
      "div",
      { class: "lore-panel-head" },
      el(
        "span",
        { class: "lore-panel-title" },
        "Lorebook tree"
      ),
      el("span", { class: "spacer" }),
      el(
        "span",
        { class: "badge" },
        String(state.books.length)
      )
    )
  );

  const treeBody = el(
    "div",
    { class: "lore-panel-body" }
  );

  treePanel.append(treeBody);

  const inspectorPanel = el(
    "section",
    { class: "lore-panel" },
    el(
      "div",
      { class: "lore-panel-head" },
      el(
        "span",
        { class: "lore-panel-title" },
`${loreBookTypeIcon(state.selected.book_type)} `
          + state.selected.name
      ),
      el("span", { class: "spacer" }),
      state.selected.chat_id == null
        ? el("span", { class: "badge" }, "library")
        : el(
          "span",
          { class: "badge ok" },
`story ${state.selected.chat_id}`
        )
    )
  );

  const inspectorBody = el(
    "div",
    { class: "lore-panel-body" }
  );

  inspectorPanel.append(inspectorBody);

  const relationshipPanel = el(
    "section",
    { class: "lore-panel" },
    el(
      "div",
      { class: "lore-panel-head" },
      el(
        "span",
        { class: "lore-panel-title" },
        "Connections"
      ),
      el("span", { class: "spacer" }),
      el(
        "span",
        { class: "badge" },
        String(state.links.length)
      )
    )
  );

  const relationshipBody = el(
    "div",
    { class: "lore-panel-body" }
  );

  relationshipPanel.append(relationshipBody);

  workspace.append(
    treePanel,
    inspectorPanel,
    relationshipPanel
  );

  renderWorkspaceTree(state, treeBody);
  renderLoreInspector(state, inspectorBody);
  renderRelationshipOverview(state, relationshipBody);

  return workspace;
}

function renderWorkspaceTree(state, container) {
  container.innerHTML = "";

  const filterInput = el(
    "input",
    {
      type: "search",
      class: "lore-tree-search",
      placeholder: "Filter tree…",
      value: loreUI.filter
    }
  );

  const toolbar = el(
    "div",
    { class: "lore-tree-toolbar" },
    filterInput,
    el(
      "button",
      {
        title: "New root book",
        onclick: () => createLoreBookDialog(
          null,
          state.selected.chat_id
        )
      },
      "+ Root"
    ),
    el(
      "button",
      {
        title: "New child",
        onclick: () => createLoreBookDialog(
          state.selected.id,
          state.selected.chat_id
        )
      },
      "+ Child"
    ),
    el(
      "button",
      {
        title: "Export selected book",
        onclick: () => exportLorebook(state.selected.id)
      },
      "⤓"
    )
  );

  container.append(toolbar);

  const help = el(
    "div",
    { class: "lore-drop-help" },
    "Drag a book onto another book to make it a child. "
      + "Use arrows for exact sibling ordering."
  );

  container.append(help);

  const tree = el("div", { class: "lore-tree" });
  container.append(tree);

  // Rebuild only the tree list on filter input so the filter input itself
  // stays in the DOM and keeps focus while typing. Store the RAW value and
  // trim only when applying the filter, so mid-word trailing spaces survive.
  filterInput.oninput = () => {
    loreUI.filter = filterInput.value;
    renderTreeList();
  };

  const byParent = loreBooksByParent(state.books);
  const byId = new Map(
    state.books.map(book => [book.id, book])
  );

  const roots = state.books.filter(book => {
    return (
      book.parent_id == null
      || !byId.has(book.parent_id)
    );
  });

  let treeFilter = "";
  let visible = new Set();

  function renderNode(book) {
    if (!visible.has(book.id)) {
      return null;
    }

    const children = (byParent.get(String(book.id)) || [])
      .filter(child => visible.has(child.id));

    const expanded = (
      loreUI.expanded.has(book.id)
      || Boolean(treeFilter)
    );

    const row = el(
      "div",
      {
        class:
          "lore-tree-row"
          + (state.selectedId === book.id
            ? " selected"
            : ""),
        draggable: "true",
        onclick: event => {
          if (book.id === state.selectedId) {
            return;
          }
          // Instant highlight so the click registers immediately while the
          // inspector/connections panels reload in place.
          const treeEl = event.currentTarget.closest(".lore-tree");
          if (treeEl) {
            for (const selected of treeEl.querySelectorAll(
              ".lore-tree-row.selected"
            )) {
              selected.classList.remove("selected");
            }
          }
          event.currentTarget.classList.add("selected");
          openLoreWorkspace(book.id);
        },
        ondragstart: event => {
          loreUI.dragId = book.id;
          row.classList.add("dragging");
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData(
            "text/plain",
            String(book.id)
          );
        },
        ondragend: () => {
          row.classList.remove("dragging");
          loreUI.dragId = null;
        },
        ondragover: event => {
          const draggedId = Number(
            event.dataTransfer.getData("text/plain")
            || loreUI.dragId
          );
          if (draggedId && draggedId !== book.id) {
            event.preventDefault();
            row.classList.add("drag-over");
          }
        },
        ondragleave: () => {
          row.classList.remove("drag-over");
        },
        ondrop: async event => {
          event.preventDefault();
          row.classList.remove("drag-over");
          const draggedId = Number(
            event.dataTransfer.getData("text/plain")
            || loreUI.dragId
          );
          if (!draggedId || draggedId === book.id) {
            return;
          }
          await moveLoreBook(
            draggedId,
            book.id,
            children.length
          );
        }
      },
      el(
        "button",
        {
          class: "lore-tree-toggle",
          disabled: !children.length,
          onclick: event => {
            event.stopPropagation();
            if (!children.length) return;

            const nodeEl = event.currentTarget.closest(
              ".lore-tree-node"
            );
            const isExpanded = nodeEl
              ? nodeEl.classList.contains("expanded")
              : false;

            if (isExpanded) {
              loreUI.expanded.delete(book.id);
              if (nodeEl)
                nodeEl.classList.remove("expanded");
              event.currentTarget.textContent = "▸";
            } else {
              loreUI.expanded.add(book.id);
              if (nodeEl)
                nodeEl.classList.add("expanded");
              event.currentTarget.textContent = "▾";
            }
          }
        },
        children.length
          ? (expanded ? "▾" : "▸")
          : "·"
      ),
      el(
        "span",
        {
          class: "lore-tree-handle",
          title: "Drag to reparent"
        },
        "⠿"
      ),
      el(
        "span",
        { class: "lore-tree-label" },
        el(
          "span",
          { class: "lore-tree-name" },
          `${loreBookTypeIcon(book.book_type)} ${book.name}`
        ),
        el(
          "span",
          { class: "lore-tree-subtitle" },
          [
            book.book_type,
            book.inheritance_mode,
            book.scope_location_id
              || book.scope_world_id
              || ""
          ].filter(Boolean).join(" · ")
        )
      ),
      el(
        "span",
        { class: "lore-tree-badges" },
        book.canon
          ? el("span", { class: "badge warn" }, "canon")
          : null,
        el(
          "span",
          { class: "badge" },
          String(book.entry_count || 0)
        )
      )
    );

    const node = el(
      "div",
      {
        class:
          "lore-tree-node"
          + (expanded ? " expanded" : "")
      },
      row
    );

    // ALWAYS render children — CSS controls visibility
    if (children.length) {
      const childBox = el(
        "div",
        { class: "lore-tree-children" }
      );
      for (const child of children) {
        const childNode = renderNode(child);
        if (childNode) {
          childBox.append(childNode);
        }
      }
      node.append(childBox);
    }

    return node;
  }

  function renderTreeList() {
    tree.innerHTML = "";

    treeFilter = (loreUI.filter || "").trim();
    visible = loreVisibleIds(state.books, treeFilter);

    for (const root of roots) {
      const node = renderNode(root);
      if (node) {
        tree.append(node);
      }
    }

    if (!tree.children.length) {
      tree.append(emptyState("No matching lorebooks."));
    }
  }

  renderTreeList();

  const rootDrop = el(
    "div",
    {
      class: "filedrop",
      style: "margin-top:8px;padding:12px",
      ondragover: event => {
        event.preventDefault();
        rootDrop.classList.add("drag-over");
      },
      ondragleave: () => {
        rootDrop.classList.remove("drag-over");
      },
      ondrop: async event => {
        event.preventDefault();
        rootDrop.classList.remove("drag-over");
        const draggedId = Number(
          event.dataTransfer.getData("text/plain")
          || loreUI.dragId
        );
        if (draggedId) {
          await moveLoreBook(draggedId, null, null);
        }
      }
    },
    "Drop here to move to root"
  );

  container.append(rootDrop);
}

// ---- Book metadata and tree operations ------------------------------------

function renderLoreBookEditor(state, container) {
  const book = state.selected;

  const nameInput = el(
    "input",
    { value: book.name || "" }
  );

  const typeSelect = loreSelect(
    S.boot.lorebook_types || [
      "general",
      "world",
      "knowledge",
      "location",
      "system",
      "characters",
      "events"
    ],
    book.book_type
  );

  const summaryInput = el(
    "textarea",
    { rows: "5" },
    book.summary || ""
  );

  const compatibleParents = state.books.filter(candidate => {
    return candidate.id !== book.id;
  });

  const parentSelect = el(
    "select",
    {},
    loreBookOptions(
      compatibleParents,
      book.parent_id,
      true
    )
  );

  const inheritanceSelect = loreSelect(
    LORE_INHERITANCE_MODES,
    book.inheritance_mode
  );

  const worldScopeInput = el(
    "input",
    {
      value: book.scope_world_id || "",
      placeholder: "world ID or empty"
    }
  );

  const locationScopeInput = el(
    "input",
    {
      value: book.scope_location_id || "",
      placeholder: "location ID or empty"
    }
  );

  const orderInput = el(
    "input",
    {
      type: "number",
      step: "1",
      value: book.sort_order || 0
    }
  );

  const grid = el(
    "div",
    { class: "lore-meta-grid" },
    loreField("Name", nameInput),
    loreField("Book type", typeSelect),
    loreField(
      "Summary for mapping and retrieval",
      summaryInput,
      "full"
    ),
    loreField("Parent", parentSelect),
    loreField("Inheritance", inheritanceSelect),
    loreField("World scope", worldScopeInput),
    loreField("Location scope", locationScopeInput),
    loreField("Sibling order", orderInput)
  );

  const saveButton = el(
    "button",
    {
      class: "primary",
      onclick: async event => {
        await buttonTask(
          event.currentTarget,
          "Saving…",
          async () => {
            const parentId = parentSelect.value
              ? Number(parentSelect.value)
              : null;

            await api(
              "PUT",
`/api/lorebooks/${book.id}`,
              {
                name: nameInput.value.trim(),
                book_type: typeSelect.value,
                summary: summaryInput.value,
                scope_world_id:
                  worldScopeInput.value.trim() || null,
                scope_location_id:
                  locationScopeInput.value.trim() || null,
                inheritance_mode:
                  inheritanceSelect.value,
                sort_order: Number(orderInput.value || 0)
              }
            );

            if (parentId !== book.parent_id) {
              await api(
                "POST",
`/api/lorebooks/${book.id}/move`,
                {
                  parent_id: parentId,
                  position: Number(orderInput.value || 0)
                }
              );
            }

            await refreshLoreUI(book.id);
            toast("Lorebook saved.", "ok");
          }
        );
      }
    },
    "Save book"
  );

  const movement = el(
    "div",
    { class: "toolbar" },
    el(
      "button",
      {
        title: "Move before previous sibling",
        onclick: () => reorderLoreBook(book.id, "up")
      },
      "↑ Move up"
    ),
    el(
      "button",
      {
        title: "Move after next sibling",
        onclick: () => reorderLoreBook(book.id, "down")
      },
      "↓ Move down"
    ),
    el(
      "button",
      {
        title: "Move beside current parent",
        disabled: book.parent_id == null,
        onclick: () => promoteLoreBook(state, book)
      },
      "↖ Promote"
    ),
    el(
      "button",
      {
        title: "Move beneath previous sibling",
        onclick: () => demoteLoreBook(state, book)
      },
      "↘ Demote"
    ),
    el(
      "button",
      {
        onclick: () => createLoreBookDialog(
          book.id,
          book.chat_id
        )
      },
      "+ Child"
    ),
    el(
      "button",
      {
        onclick: () => createSiblingLoreBook(state, book)
      },
      "+ Sibling"
    )
  );

  const ownershipText = book.chat_id == null
    ? "Global library lorebook"
    :`Story-local lorebook for story ${book.chat_id}`;

  container.append(
    el(
      "div",
      { class: "small dim" },
      ownershipText
    ),
    grid,
    el(
      "div",
      { class: "row", style: "margin-top:10px" },
      saveButton,
      el(
        "button",
        { onclick: () => exportLorebook(book.id) },
        "⤓ Export"
      )
    ),
    movement,
    el(
      "div",
      { class: "card" },
      el(
        "div",
        { class: "section-title", style: "margin-top:0" },
        "Inheritance behavior"
      ),
      el(
        "div",
        { class: "small dim" },
        "inherit: shares hierarchical context. "
          + "isolated: retrieved independently. "
          + "reference_only: organizational context without automatic "
          + "entry retrieval."
      )
    ),
    el(
      "div",
      { class: "lore-danger-zone" },
      el(
        "div",
        { class: "section-title", style: "margin-top:0" },
        "Danger zone"
      ),
      el(
        "button",
        {
          class: "danger",
          onclick: async () => {
            const warning = state.books.some(
              candidate => candidate.parent_id === book.id
            )
              ? "This book has children. Deleting it may delete its "
                + "subtree. Continue?"
              : "Delete this lorebook?";

            if (!await confirmModal(warning, { danger: true, confirmLabel: "Delete" })) {
              return;
            }

            await api(
              "DELETE",
`/api/lorebooks/${book.id}`
            );

            closeModal();
            await boot();
            toast("Lorebook deleted.", "ok");
          }
        },
        "Delete lorebook"
      )
    )
  );
}

async function moveLoreBook(bookId, parentId, position) {
  try {
    await api(
      "POST",
`/api/lorebooks/${bookId}/move`,
      {
        parent_id: parentId,
        position
      }
    );

    await refreshLoreUI(bookId);
    toast("Lorebook moved.", "ok");
  } catch (error) {
    toast("Could not move lorebook: " + error.message, "err");
  }
}

async function reorderLoreBook(bookId, direction) {
  try {
    await api(
      "POST",
`/api/lorebooks/${bookId}/reorder`,
      { direction }
    );

    await refreshLoreUI(bookId);
  } catch (error) {
    toast("Could not reorder lorebook: " + error.message, "err");
  }
}

async function promoteLoreBook(state, book) {
  const parent = state.books.find(
    candidate => candidate.id === book.parent_id
  );

  if (!parent) {
    await moveLoreBook(book.id, null, null);
    return;
  }

  await moveLoreBook(
    book.id,
    parent.parent_id,
    parent.sort_order + 1
  );
}

async function demoteLoreBook(state, book) {
  const siblings = state.books
    .filter(candidate => candidate.parent_id === book.parent_id)
    .sort((a, b) => {
      return (
        a.sort_order - b.sort_order
        || a.name.localeCompare(b.name)
      );
    });

  const index = siblings.findIndex(
    candidate => candidate.id === book.id
  );

  if (index <= 0) {
    toast(
      "There is no previous sibling to demote beneath.",
      "warn"
    );
    return;
  }

  const previous = siblings[index - 1];
  await moveLoreBook(book.id, previous.id, null);
}

function createSiblingLoreBook(state, book) {
  createLoreBookDialog(
    book.parent_id,
    book.chat_id,
    book.sort_order + 1
  );
}

function createLoreBookDialog(
  parentId = null,
  chatId = null,
  position = null
) {
  const nameInput = el(
    "input",
    {
      value: "New lorebook",
      style: "width:100%"
    }
  );

  const typeSelect = loreSelect(
    S.boot.lorebook_types || ["general"],
    "general"
  );

  const summaryInput = el(
    "textarea",
    {
      rows: "4",
      style: "width:100%"
    }
  );

  const inheritanceSelect = loreSelect(
    LORE_INHERITANCE_MODES,
    "inherit"
  );

  modal(
    "Create lorebook",
    body => {
      body.append(
        loreField("Name", nameInput),
        loreField("Type", typeSelect),
        loreField("Summary", summaryInput),
        loreField("Inheritance", inheritanceSelect),
        el(
          "div",
          { class: "row", style: "margin-top:10px" },
          el(
            "button",
            {
              class: "primary",
              onclick: async event => {
                await buttonTask(
                  event.currentTarget,
                  "Creating…",
                  async () => {
                    const result = await api(
                      "POST",
                      "/api/lorebooks",
                      {
                        name:
                          nameInput.value.trim()
                          || "New lorebook",
                        book_type: typeSelect.value,
                        summary: summaryInput.value,
                        parent_id: parentId,
                        chat_id: chatId,
                        inheritance_mode:
                          inheritanceSelect.value,
                        sort_order: position || 0
                      }
                    );

                    if (parentId != null) {
                      await api(
                        "POST",
`/api/lorebooks/${result.id}/move`,
                        {
                          parent_id: parentId,
                          position
                        }
                      );
                    }

                    // Pop this create dialog off the modal stack first so the
                    // workspace it was opened over is reused in place rather
                    // than a second workspace being stacked on top of it.
                    closeModal();
                    await boot();
                    await openLoreWorkspace(result.id);
                  }
                );
              }
            },
            "Create"
          )
        )
      );
    }
  );
}

async function refreshLoreUI(selectedId) {
  await boot();
  await openLoreWorkspace(selectedId);
}

// ---- Entry editor ----------------------------------------------------------

function renderLoreEntries(state, container) {
  const entries = state.selectedResponse.entries || [];

  const searchInput = el(
    "input",
    {
      type: "search",
      value: loreUI.entryFilter,
      placeholder: "Filter entries…"
    }
  );

  const categorySelect = loreSelect(
    [
      ["", "All categories"],
      ...(S.boot.lore_categories || []).map(
        category => [category, category]
      )
    ],
    loreUI.entryCategory
  );

  const list = el("div");

  const toolbar = el(
    "div",
    { class: "lore-entry-toolbar" },
    searchInput,
    categorySelect,
    el(
      "button",
      {
        onclick: async () => {
          const result = await api(
            "POST",
`/api/lorebooks/${state.selected.id}/entries`,
            {
              keys: "",
              content: "New entry",
              category: "other"
            }
          );

          await refreshLoreUI(state.selected.id);

          if (result?.id) {
            requestAnimationFrame(() => {
              document
                .querySelector(`[data-entry-id="${result.id}"]`)
                ?.setAttribute("open", "");
            });
          }
        }
      },
      "+ Entry"
    ),
    el(
      "button",
      {
        onclick: () => generateLoreEntriesPrompt(state)
      },
      "✨ Generate entries"
    ),
    el(
      "button",
      {
        onclick: () => reinterpretLoreBook(state)
      },
      "✨ Reinterpret"
    )
  );

  function renderList() {
    loreUI.entryFilter = searchInput.value.trim();
    loreUI.entryCategory = categorySelect.value;
    list.innerHTML = "";

    const filtered = entries.filter(entry => {
      const category = entry.category || "other";
      const text = [
        entry.title,
        entry.keys,
        entry.content,
        category
      ].join(" ").toLowerCase();

      const searchMatches = (
        !loreUI.entryFilter
        || text.includes(loreUI.entryFilter.toLowerCase())
      );

      const categoryMatches = (
        !loreUI.entryCategory
        || category === loreUI.entryCategory
      );

      return searchMatches && categoryMatches;
    });

    if (!filtered.length) {
      list.append(emptyState("No matching entries."));
      return;
    }

    for (const entry of filtered) {
      list.append(buildLoreEntryCard(state, entry));
    }
  }

  searchInput.oninput = renderList;
  categorySelect.onchange = renderList;

  container.append(toolbar, list);
  renderList();
}

function buildLoreEntryCard(state, entry) {
  const category = entry.category || "other";
  const aliases = parseStoredJSON(entry.aliases, []);
  const scope = parseStoredJSON(entry.scope, {});
  const relations = parseStoredJSON(entry.relations, {});

  const keysInput = el(
    "input",
    { value: entry.keys || "" }
  );

  const titleInput = el(
    "input",
    { value: entry.title || "" }
  );

  const categorySelect = loreSelect(
    S.boot.lore_categories || ["other"],
    category
  );

  const contentInput = el(
    "textarea",
    {
      rows: "7",
      class: "lore-entry-content"
    },
    entry.content || ""
  );

  const lockedInput = el(
    "input",
    {
      type: "checkbox",
      ...(entry.canon_locked || entry.locked
        ? { checked: "" }
        : {})
    }
  );

  const importanceInput = el(
    "input",
    {
      type: "number",
      min: "0",
      max: "1",
      step: "0.05",
      value: entry.importance ?? 0.5
    }
  );

  const aliasesInput = el(
    "input",
    { value: (aliases || []).join(", ") }
  );

  const worldIdsInput = el(
    "input",
    {
      value: (scope.world_ids || []).join(", "),
      placeholder: "world IDs"
    }
  );

  const locationIdsInput = el(
    "input",
    {
      value: (scope.location_ids || []).join(", "),
      placeholder: "location IDs"
    }
  );

  const entityIdsInput = el(
    "input",
    {
      value: (scope.entity_ids || []).join(", "),
      placeholder: "entity IDs"
    }
  );

  const sourceNotesInput = el(
    "textarea",
    { rows: "2" },
    entry.source_notes || ""
  );

  const knowledgeTagSelect = loreSelect(
    ["common", "scholarly", "esoteric"],
    entry.knowledge_tag || "common"
  );

  const knowledgeRangeSelect = loreSelect(
    ["global", "local"],
    entry.knowledge_range || "global"
  );

  const storedLocations = parseStoredJSON(
    entry.knowledge_locations,
    []
  );

  const knowledgeLocationsInput = el(
    "input",
    {
      value: (storedLocations || []).join(", "),
      placeholder: "local room/location IDs"
    }
  );

  const supersedesInput = el(
    "input",
    {
      type: "number",
      value: relations.supersedes_entry_id || "",
      placeholder: "entry ID"
    }
  );

  const refinesInput = el(
    "input",
    {
      value: (relations.refines_entry_ids || []).join(", "),
      placeholder: "entry IDs"
    }
  );

  const contradictsInput = el(
    "input",
    {
      value:
        (relations.contradicts_entry_ids || []).join(", "),
      placeholder: "entry IDs"
    }
  );

  const knowledgeFields = el(
    "div",
    {
      class: "lore-entry-grid full",
      style: category === "knowledge" ? "" : "display:none"
    },
    loreField("Knowledge tag", knowledgeTagSelect),
    loreField("Knowledge range", knowledgeRangeSelect),
    loreField(
      "Knowledge locations",
      knowledgeLocationsInput,
      "full"
    )
  );

  categorySelect.onchange = () => {
    knowledgeFields.style.display =
      categorySelect.value === "knowledge"
        ? ""
        : "none";
  };

  const title = (
    entry.title
    || entry.keys
    || entry.content
    || `Entry ${entry.id}`
  );

  const card = el(
    "details",
    {
      class: "lore-entry-card card",
      "data-entry-id": entry.id
    },
    el(
      "summary",
      {},
      el("span", { class: "badge" }, category),
      el(
        "span",
        {
          class: "lore-entry-title",
          title
        },
        title
      ),
      entry.canon_locked || entry.locked
        ? el("span", { class: "badge warn" }, "locked")
        : null,
      el(
        "span",
        { class: "small dim" },
`#${entry.id}`
      )
    ),
    el(
      "div",
      {
        class: "lore-entry-grid",
        style: "margin-top:10px"
      },
      loreField("Keys", keysInput, "full"),
      loreField("Title", titleInput),
      loreField("Category", categorySelect),
      loreField("Content", contentInput, "full"),
      loreField("Importance", importanceInput),
      loreField(
        "Canon lock",
        el(
          "label",
          { class: "tgl" },
          lockedInput,
          " locked"
        )
      ),
      loreField("Aliases", aliasesInput, "full"),
      loreField("World scope", worldIdsInput),
      loreField("Location scope", locationIdsInput),
      loreField("Entity scope", entityIdsInput, "full"),
      knowledgeFields,
      el(
        "details",
        { class: "full" },
        el("summary", {}, "Entry relationships"),
        el(
          "div",
          { class: "lore-entry-grid" },
          loreField("Supersedes entry", supersedesInput),
          loreField("Refines entries", refinesInput),
          loreField(
            "Contradicts entries",
            contradictsInput,
            "full"
          )
        )
      ),
      loreField("Source notes", sourceNotesInput, "full"),
      el(
        "div",
        { class: "full row" },
        el(
          "button",
          {
            class: "primary",
            onclick: async event => {
              await buttonTask(
                event.currentTarget,
                "Saving…",
                async () => {
                  const isKnowledge =
                    categorySelect.value === "knowledge";

                  const knowledgeLocations = (
                    isKnowledge
                    && knowledgeRangeSelect.value === "local"
                  )
                    ? splitCL(knowledgeLocationsInput.value)
                    : [];

                  await api(
                    "PUT",
`/api/lore_entries/${entry.id}`,
                    {
                      keys: keysInput.value,
                      title: titleInput.value || null,
                      category: categorySelect.value,
                      content: contentInput.value,
                      canon_locked: lockedInput.checked,
                      importance: numOr(
                        importanceInput.value,
                        0.5
                      ),
                      aliases: splitCL(aliasesInput.value),
                      scope: {
                        world_ids: splitCL(
                          worldIdsInput.value
                        ),
                        location_ids: splitCL(
                          locationIdsInput.value
                        ),
                        entity_ids: splitCL(
                          entityIdsInput.value
                        )
                      },
                      relations: {
                        supersedes_entry_id:
                          supersedesInput.value
                            ? Number(supersedesInput.value)
                            : null,
                        refines_entry_ids:
                          splitNumberList(refinesInput.value),
                        contradicts_entry_ids:
                          splitNumberList(
                            contradictsInput.value
                          )
                      },
                      source_notes: sourceNotesInput.value,
                      knowledge_tag: isKnowledge
                        ? knowledgeTagSelect.value
                        : null,
                      knowledge_range: isKnowledge
                        ? knowledgeRangeSelect.value
                        : null,
                      knowledge_locations:
                        knowledgeLocations
                    }
                  );

                  toast("Entry saved.", "ok");
                  await refreshLoreUI(state.selected.id);
                }
              );
            }
          },
          "Save entry"
        ),
        el(
          "button",
          {
            class: "danger",
            onclick: async () => {
              if (!await confirmModal("Delete this lore entry?", { danger: true, confirmLabel: "Delete" })) {
                return;
              }

              await api(
                "DELETE",
`/api/lore_entries/${entry.id}`
              );

              await refreshLoreUI(state.selected.id);
            }
          },
          "Delete"
        )
      )
    )
  );

  return card;
}

function splitNumberList(value) {
  return splitCL(value)
    .map(item => Number(item))
    .filter(Number.isFinite);
}

function reinterpretLoreBook(state) {
  backgroundTask(
    "Reinterpreting " + state.selected.name,
    () => api(
      "POST",
`/api/lorebooks/${state.selected.id}/reinterpret`
    ),
    {
      onSuccess: async () => {
        await refreshLoreUI(state.selected.id);
      },
      successMessage: result => {
        return`Reinterpreted ${result?.reinterpreted || 0} entries.`;
      },
      errorPrefix: "Reinterpretation failed"
    }
  );
}

function generateLoreEntriesPrompt(state) {
  const promptInput = el(
    "textarea",
    {
      rows: "9",
      style: "width:100%",
      placeholder:
        "Describe the lore entries to generate.\n\n"
        + "Example: Create entries for the capital's districts, "
        + "government, defenses, major factions, and local customs."
    }
  );

  const guidanceInput = el(
    "select",
    {},
    [
      ["general", "General expansion"],
      ["locations", "Locations and layouts"],
      ["systems", "Rules and mechanics"],
      ["characters", "Characters and factions"],
      ["history", "History and events"],
      ["culture", "Culture, myths, and knowledge"],
      ["gaps", "Find and fill missing subjects"]
    ].map(([value, label]) => {
      return el(
        "option",
        { value },
        label
      );
    })
  );

  const preserveExistingInput = el(
    "input",
    {
      type: "checkbox",
      checked: ""
    }
  );

  const lockedNote = el(
    "div",
    {
      class: "small dim",
      style: "margin-top:8px"
    },
    "Entries are written directly to the selected lorebook. "
      + "Use the Generator tab instead when you want to preview "
      + "new books, relationships, and entry updates before applying them."
  );

  modal(
`Generate entries — ${state.selected.name}`,
    body => {
      body.append(
        el(
          "div",
          { class: "lore-generator-grid" },
          loreField(
            "Generation focus",
            guidanceInput
          ),
          loreField(
            "Selected book",
            el(
              "input",
              {
                value: state.selected.name,
                disabled: "disabled"
              }
            )
          ),
          loreField(
            "What should be generated?",
            promptInput,
            "full"
          ),
          el(
            "div",
            { class: "full" },
            el(
              "label",
              { class: "tgl" },
              preserveExistingInput,
              " Avoid duplicate subjects and preserve existing entries"
            )
          )
        ),
        lockedNote,
        el(
          "div",
          {
            class: "row",
            style: "margin-top:12px"
          },
          el(
            "button",
            {
              class: "primary",
              onclick: event => {
                const request = buildDirectLoreRequest(
                  guidanceInput.value,
                  promptInput.value,
                  preserveExistingInput.checked
                );

                if (!promptInput.value.trim()) {
                  toast(
                    "Describe what entries should be generated.",
                    "warn"
                  );
                  promptInput.focus();
                  return;
                }

                const button = event.currentTarget;
                button.disabled = true;

                backgroundTask(
`Generating entries for ${state.selected.name}`,
                  () => api(
                    "POST",
`/api/lorebooks/${state.selected.id}/generate`,
                    {
                      prompt: request
                    }
                  ),
                  {
                    onSuccess: async result => {
                      await boot();
                      await openLoreWorkspace(
                        state.selected.id
                      );

                      if (result?.entry_ids?.length) {
                        requestAnimationFrame(() => {
                          for (
                            const entryId
                            of result.entry_ids
                          ) {
                            document
                              .querySelector(
`[data-entry-id="${entryId}"]`
                              )
                              ?.setAttribute("open", "");
                          }
                        });
                      }
                    },
                    successMessage: result => {
                      const count = result?.added || 0;

                      return (
`Generated ${count} `
                        + (
                          count === 1
                            ? "lore entry."
                            : "lore entries."
                        )
                      );
                    },
                    errorPrefix:
                      "Lore entry generation failed",
                    onFinally: () => {
                      if (button.isConnected) {
                        button.disabled = false;
                      }
                    }
                  }
                );
              }
            },
            "Generate entries"
          ),
          el(
            "button",
            {
              onclick: () => closeModal()
            },
            "Cancel"
          ),
          el("span", { class: "spacer" }),
          el(
            "button",
            {
              title:
                "Open the advanced generator after returning "
                + "to the lorebook workspace",
              onclick: async () => {
                loreUI.selectedTab = "generator";
                // Pop this dialog so the workspace beneath is reused in place
                // rather than a second workspace being stacked over it.
                closeModal();
                await openLoreWorkspace(
                  state.selected.id
                );
              }
            },
            "Advanced generator →"
          )
        )
      );
    },
    {
      wide: false,
      autoFocus: true
    }
  );
}

function buildDirectLoreRequest(
  focus,
  prompt,
  preserveExisting
) {
  const focusGuidance = {
    general:
      "Expand the lorebook with a balanced set of useful subjects.",
    locations:
      "Focus on locations and layouts. Separate places and interior "
      + "sections into clear, individually retrievable entries.",
    systems:
      "Focus on systems and mechanics. State exact rules, costs, "
      + "limits, exceptions, and failure modes.",
    characters:
      "Focus on characters and factions. Include public roles, goals, "
      + "resources, methods, alliances, and conflicts.",
    history:
      "Focus on events and history. Include chronology, causes, "
      + "participants, consequences, and current relevance.",
    culture:
      "Focus on cultures, myths, customs, beliefs, and knowledge. "
      + "Distinguish objective facts from in-world belief.",
    gaps:
      "Inspect the supplied existing entries and fill important missing "
      + "subjects without repeating covered material."
  };

  const parts = [
    focusGuidance[focus] || focusGuidance.general,
    preserveExisting
      ? (
        "Do not replace, contradict, or duplicate existing entries. "
        + "Generate only distinct new entries."
      )
      : (
        "Related subjects are allowed, but each generated entry must "
        + "still add materially new information."
      ),
    String(prompt || "").trim()
  ];

  return parts.filter(Boolean).join("\n\n");
}

// ---- Lorebook relationships ------------------------------------------------

function renderRelationshipOverview(state, container) {
  container.innerHTML = "";

  const center = el(
    "div",
    { class: "lore-graph-center" },
    el(
      "strong",
      {},
      `${loreBookTypeIcon(state.selected.book_type)} `
        + state.selected.name
    ),
    el(
      "div",
      { class: "small dim" },
      state.selected.book_type
    )
  );

  const graph = el(
    "div",
    { class: "lore-link-graph" },
    center
  );

  if (!state.links.length) {
    graph.append(emptyState(
      "No semantic relationships. Parentage remains visible in the tree."
    ));
  } else {
    const targetMap = new Map(
      state.allLinkTargets.map(book => [book.id, book])
    );

    targetMap.set(state.selected.id, state.selected);

    for (const link of state.links) {
      const outgoing =
        Number(link.source_book_id) === state.selected.id;

      const otherId = outgoing
        ? Number(link.target_book_id)
        : Number(link.source_book_id);

      const other = targetMap.get(otherId);
      const arrow = link.bidirectional
        ? "↔"
        : (outgoing ? "→" : "←");

      graph.append(el(
        "div",
        {
          class: "lore-graph-edge",
          title: link.notes || ""
        },
        el(
          "span",
          {},
          outgoing
            ? state.selected.name
            : (other?.name || `Book ${otherId}`)
        ),
        el(
          "span",
          { class: "arrow" },
          `${arrow} ${link.relation_type}`
        ),
        el(
          "span",
          {},
          outgoing
            ? (other?.name || `Book ${otherId}`)
            : state.selected.name
        )
      ));
    }
  }

  container.append(
    graph,
    el(
      "div",
      { class: "small dim", style: "margin-top:10px" },
      "Solid tree containment is edited in the tree. "
        + "These links connect books without making either one a parent."
    ),
    el(
      "button",
      {
        style: "margin-top:9px",
        onclick: () => {
          const tabBtn = document.querySelector(
            '[data-tab="relationships"]'
          );
          if (tabBtn) {
            tabBtn.click();
          } else {
            loreUI.selectedTab = "relationships";
            openLoreWorkspace(state.selected.id);
          }
        }
      },
      "Manage relationships"
    )
  );
}

function renderLoreRelationshipEditor(state, container) {
  const list = el("div");

  const addButton = el(
    "button",
    {
      onclick: () => showNewRelationshipForm(state, list)
    },
    "+ Relationship"
  );

  container.append(
    el(
      "div",
      { class: "toolbar" },
      addButton,
      el(
        "span",
        { class: "small dim" },
        "Links may cross tree boundaries."
      )
    ),
    list
  );

  renderRelationshipList(state, list);
}

function renderRelationshipList(state, list) {
  list.innerHTML = "";

  if (!state.links.length) {
    list.append(emptyState("No relationships yet."));
    return;
  }

  const books = new Map(
    state.allLinkTargets.map(book => [book.id, book])
  );

  books.set(state.selected.id, state.selected);

  for (const link of state.links) {
    const outgoing =
      Number(link.source_book_id) === state.selected.id;

    const otherId = outgoing
      ? Number(link.target_book_id)
      : Number(link.source_book_id);

    const other = books.get(otherId);

    const typeSelect = loreSelect(
      loreLinkTypes(),
      link.relation_type || "related"
    );

    const labelInput = el(
      "input",
      {
        value: link.label || "",
        placeholder: "optional label"
      }
    );

    const notesInput = el(
      "textarea",
      { rows: "2" },
      link.notes || ""
    );

    const weightInput = el(
      "input",
      {
        type: "number",
        min: "0",
        max: "1",
        step: "0.05",
        value: link.weight ?? 0.75
      }
    );

    const bidirectionalInput = el(
      "input",
      {
        type: "checkbox",
        ...(link.bidirectional
          ? { checked: "" }
          : {})
      }
    );

    const followInput = el(
      "input",
      {
        type: "checkbox",
        ...(link.follow_for_retrieval
          ? { checked: "" }
          : {})
      }
    );

    list.append(el(
      "div",
      { class: "card lore-relation-card" },
      el(
        "div",
        { class: "row" },
        el(
          "strong",
          {},
          other?.name ||`Lorebook ${otherId}`
        ),
        el(
          "span",
          { class: "badge" },
          link.relation_type
        ),
        el(
          "span",
          { class: "lore-relation-direction" },
          outgoing ? "outgoing" : "incoming"
        )
      ),
      el(
        "div",
        {
          class: "lore-meta-grid",
          style: "margin-top:8px"
        },
        loreField("Relationship", typeSelect),
        loreField("Weight", weightInput),
        loreField("Label", labelInput, "full"),
        loreField("Notes", notesInput, "full"),
        el(
          "div",
          { class: "full row" },
          el(
            "label",
            { class: "tgl" },
            bidirectionalInput,
            " bidirectional"
          ),
          el(
            "label",
            { class: "tgl" },
            followInput,
            " follow during retrieval"
          )
        ),
        el(
          "div",
          { class: "full row" },
          el(
            "button",
            {
              class: "primary",
              onclick: async () => {
                await api(
                  "PUT",
`/api/lorebook_links/${link.id}`,
                  {
                    relation_type: typeSelect.value,
                    label: labelInput.value,
                    notes: notesInput.value,
                    weight: numOr(weightInput.value, 0.75),
                    bidirectional:
                      bidirectionalInput.checked,
                    follow_for_retrieval:
                      followInput.checked
                  }
                );

                await refreshLoreUI(state.selected.id);
              }
            },
            "Save"
          ),
          el(
            "button",
            {
              class: "danger",
              onclick: async () => {
                if (!await confirmModal("Delete this relationship?", { danger: true, confirmLabel: "Delete" })) {
                  return;
                }

                await api(
                  "DELETE",
`/api/lorebook_links/${link.id}`
                );

                await refreshLoreUI(state.selected.id);
              }
            },
            "Delete"
          )
        )
      )
    ));
  }
}

function showNewRelationshipForm(state, list) {
  const existing = list.querySelector(
    ".lore-new-relationship"
  );

  if (existing) {
    existing.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
    return;
  }

  if (!state.allLinkTargets.length) {
    toast("There are no other lorebooks to link.", "warn");
    return;
  }

  const targetSelect = el(
    "select",
    {},
    loreBookOptions(
      state.allLinkTargets,
      state.allLinkTargets[0]?.id,
      false
    )
  );

  const typeSelect = loreSelect(
    loreLinkTypes(),
    "related"
  );

  const labelInput = el("input", {
    placeholder: "optional display label"
  });

  const notesInput = el(
    "textarea",
    {
      rows: "2",
      placeholder: "why these books are connected"
    }
  );

  const weightInput = el(
    "input",
    {
      type: "number",
      min: "0",
      max: "1",
      step: "0.05",
      value: "0.75"
    }
  );

  const bidirectionalInput = el(
    "input",
    { type: "checkbox", checked: "" }
  );

  const followInput = el(
    "input",
    { type: "checkbox", checked: "" }
  );

  const form = el(
    "div",
    { class: "card lore-new-relationship" },
    el(
      "div",
      { class: "section-title", style: "margin-top:0" },
      "New relationship"
    ),
    el(
      "div",
      { class: "lore-meta-grid" },
      loreField("Target book", targetSelect),
      loreField("Relationship", typeSelect),
      loreField("Label", labelInput, "full"),
      loreField("Notes", notesInput, "full"),
      loreField("Retrieval weight", weightInput),
      el(
        "div",
        {},
        el(
          "label",
          { class: "tgl" },
          bidirectionalInput,
          " bidirectional"
        ),
        el(
          "label",
          { class: "tgl" },
          followInput,
          " follow for retrieval"
        )
      ),
      el(
        "div",
        { class: "full row" },
        el(
          "button",
          {
            class: "primary",
            onclick: async () => {
              await api(
                "POST",
`/api/lorebooks/${state.selected.id}/links`,
                {
                  target_book_id: Number(targetSelect.value),
                  relation_type: typeSelect.value,
                  label: labelInput.value,
                  notes: notesInput.value,
                  bidirectional:
                    bidirectionalInput.checked,
                  follow_for_retrieval:
                    followInput.checked,
                  weight: numOr(weightInput.value, 0.75)
                }
              );

              await refreshLoreUI(state.selected.id);
            }
          },
          "Create link"
        ),
        el(
          "button",
          { onclick: () => form.remove() },
          "Cancel"
        )
      )
    )
  );

  list.prepend(form);
}

// ---- Advanced generator ----------------------------------------------------

function renderLoreGenerator(state, container) {
  const briefInput = el(
    "textarea",
    {
      rows: "7",
      placeholder:
        "Describe what should be expanded, audited, or generated…"
    }
  );

  const modeSelect = loreSelect(
    [
      ["expand_tree", "Expand selected tree"],
      ["fill_gaps", "Find and fill gaps"],
      ["location_hierarchy", "Build location hierarchy"],
      ["world_hierarchy", "Build world hierarchy"],
      ["system_specification", "Specify a system"],
      ["characters_factions", "Characters and factions"],
      ["history_timeline", "History and timeline"],
      ["audit_contradictions", "Audit contradictions"],
      ["refine_existing", "Refine existing entries"],
      ["split_book", "Split an oversized book"]
    ],
    "expand_tree"
  );

  const depthInput = el(
    "input",
    {
      type: "number",
      min: "0",
      max: "6",
      value: "2"
    }
  );

  const targetInput = el(
    "input",
    {
      type: "number",
      min: "1",
      max: "200",
      value: "40"
    }
  );

  const newBooksInput = el(
    "input",
    { type: "checkbox", checked: "" }
  );

  const linksInput = el(
    "input",
    { type: "checkbox", checked: "" }
  );

  const updatesInput = el(
    "input",
    { type: "checkbox", checked: "" }
  );

  const preserveLockedInput = el(
    "input",
    { type: "checkbox", checked: "" }
  );

  const planArea = el("div");

  const controls = el(
    "div",
    { class: "lore-generator-grid" },
    loreField("Generation request", briefInput, "full"),
    loreField("Mode", modeSelect),
    loreField("Tree depth", depthInput),
    loreField("Target entries", targetInput),
    el(
      "div",
      {},
      el(
        "label",
        { class: "tgl" },
        newBooksInput,
        " allow child books"
      ),
      el(
        "label",
        { class: "tgl" },
        linksInput,
        " allow semantic links"
      ),
      el(
        "label",
        { class: "tgl" },
        updatesInput,
        " allow entry updates"
      ),
      el(
        "label",
        { class: "tgl" },
        preserveLockedInput,
        " preserve locked canon"
      )
    ),
    el(
      "div",
      { class: "full row" },
      el(
        "button",
        {
          class: "primary",
          onclick: event => {
            const button = event.currentTarget;

            backgroundTask(
              "Planning lorebook expansion",
              () => api(
                "POST",
`/api/lorebooks/${state.selected.id}/generate_plan`,
                {
                  prompt: briefInput.value.trim(),
                  mode: modeSelect.value,
                  depth: Number(depthInput.value || 2),
                  entry_target:
                    Number(targetInput.value || 40),
                  allow_new_books:
                    newBooksInput.checked,
                  allow_links: linksInput.checked,
                  allow_updates: updatesInput.checked,
                  preserve_locked:
                    preserveLockedInput.checked
                }
              ),
              {
                closeModal: false,
                onSuccess: plan => {
                  state.plan = normalizeGeneratorPlan(plan);
                  renderLorePlanPreview(
                    state,
                    planArea
                  );
                },
                successMessage:
                  "Lorebook plan generated.",
                errorPrefix:
                  "Lorebook planning failed",
                onFinally: () => {
                  if (button.isConnected) {
                    button.disabled = false;
                  }
                }
              }
            );

            button.disabled = true;
          }
        },
        "✨ Generate plan"
      )
    )
  );

  container.append(
    controls,
    el(
      "div",
      { class: "small dim", style: "margin-top:8px" },
      "Nothing is written until you review and apply the plan."
    ),
    planArea
  );

  if (state.plan) {
    renderLorePlanPreview(state, planArea);
  }
}

function normalizeGeneratorPlan(plan) {
  const result = structuredClone(plan || {});

  result.analysis = result.analysis || {};
  result.book_ops = Array.isArray(result.book_ops)
    ? result.book_ops
    : [];
  result.link_ops = Array.isArray(result.link_ops)
    ? result.link_ops
    : [];
  result.entry_ops = Array.isArray(result.entry_ops)
    ? result.entry_ops
    : [];

  for (const collection of [
    result.book_ops,
    result.link_ops,
    result.entry_ops
  ]) {
    for (const operation of collection) {
      operation._accepted = operation._accepted !== false;
    }
  }

  return result;
}

function renderLorePlanPreview(state, container) {
  container.innerHTML = "";

  const plan = state.plan;

  if (!plan) {
    return;
  }

  const analysis = plan.analysis || {};
  const allOps = [
    ...plan.book_ops,
    ...plan.link_ops,
    ...plan.entry_ops
  ];

  const summary = el(
    "div",
    { class: "lore-plan-summary" },
    planStat("Books", plan.book_ops.length),
    planStat("Links", plan.link_ops.length),
    planStat("Entries", plan.entry_ops.length),
    planStat(
      "Accepted",
      allOps.filter(operation => operation._accepted).length
    )
  );

  const analysisCard = el(
    "details",
    { class: "card", open: "" },
    el("summary", {}, "Generator analysis"),
    renderAnalysisSection("Themes", analysis.themes),
    renderAnalysisSection(
      "Missing areas",
      analysis.missing_areas
    ),
    renderAnalysisSection(
      "Contradictions",
      analysis.contradictions
    ),
    renderAnalysisSection(
      "Assumptions",
      analysis.assumptions
    )
  );

  const operationsBox = el("div");

  function renderOperations() {
    operationsBox.innerHTML = "";

    addPlanGroup(
      operationsBox,
      "Book operations",
      plan.book_ops,
      operation => {
        return (
          `${operation.op || "create"}: `
          + (operation.name || operation.temp_id || "book")
          +` [${operation.book_type || "general"}]`
        );
      },
      renderOperations
    );

    addPlanGroup(
      operationsBox,
      "Relationship operations",
      plan.link_ops,
      operation => {
        return (
          `${operation.source_id || operation.source_book_id}`
          +` ${operation.relation_type || "related"} `
          +`${operation.target_id || operation.target_book_id}`
        );
      },
      renderOperations
    );

    addPlanGroup(
      operationsBox,
      "Entry operations",
      plan.entry_ops,
      operation => {
        return (
          `${operation.op || "create"}: `
          + (
            operation.title
            || operation.keys
            || operation.content
            || "entry"
          )
        );
      },
      renderOperations
    );
  }

  const raw = el(
    "details",
    { class: "card" },
    el("summary", {}, "Raw plan JSON"),
    el(
      "pre",
      { class: "lore-plan-json" },
      JSON.stringify(stripPlanUIFields(plan), null, 2)
    )
  );

  const applyButton = el(
    "button",
    {
      class: "primary",
      onclick: async event => {
        const accepted = acceptedGeneratorPlan(plan);
        const acceptedCount = (
          accepted.book_ops.length
          + accepted.link_ops.length
          + accepted.entry_ops.length
        );

        if (!acceptedCount) {
          toast("No plan operations are selected.", "warn");
          return;
        }

        await buttonTask(
          event.currentTarget,
          "Applying…",
          async () => {
            const result = await api(
              "POST",
`/api/lorebooks/${state.selected.id}/apply_plan`,
              { plan: accepted }
            );

            toast(
              "Applied lorebook plan: "
                + `${result.result?.books_created || 0} books, `
                + `${result.result?.entries_created || 0} entries, `
                + `${result.result?.links_created || 0} links.`,
              "ok"
            );

            await refreshLoreUI(state.selected.id);
          }
        );
      }
    },
    "Apply accepted operations"
  );

  const acceptAllButton = el(
    "button",
    {
      onclick: () => {
        for (const operation of allOps) {
          operation._accepted = true;
        }

        renderLorePlanPreview(state, container);
      }
    },
    "Accept all"
  );

  const rejectAllButton = el(
    "button",
    {
      onclick: () => {
        for (const operation of allOps) {
          operation._accepted = false;
        }

        renderLorePlanPreview(state, container);
      }
    },
    "Reject all"
  );

  container.append(
    el(
      "div",
      { class: "section-title" },
      "Generated plan"
    ),
    summary,
    analysisCard,
    el(
      "div",
      { class: "row" },
      acceptAllButton,
      rejectAllButton
    ),
    operationsBox,
    raw,
    el(
      "div",
      { class: "row", style: "margin-top:10px" },
      applyButton
    )
  );

  renderOperations();
}

function planStat(label, value) {
  return el(
    "div",
    { class: "lore-plan-stat" },
    el("strong", {}, String(value)),
    el("span", { class: "small dim" }, label)
  );
}

function renderAnalysisSection(label, items) {
  if (!Array.isArray(items) || !items.length) {
    return null;
  }

  return el(
    "div",
    { style: "margin-top:8px" },
    el("strong", {}, label),
    ...items.map(item => {
      const text = typeof item === "string"
        ? item
        : JSON.stringify(item);

      return el(
        "div",
        { class: "small", style: "margin-top:3px" },
        "• " + text
      );
    })
  );
}

function addPlanGroup(
  container,
  label,
  operations,
  describe,
  rerender
) {
  const group = el(
    "details",
    {
      class: "card",
      ...(operations.length ? { open: "" } : {})
    },
    el(
      "summary",
      {},
`${label} (${operations.length})`
    )
  );

  if (!operations.length) {
    group.append(
      el("div", { class: "small dim" }, "None proposed.")
    );
  }

  for (const operation of operations) {
    const acceptedInput = el(
      "input",
      {
        type: "checkbox",
        ...(operation._accepted
          ? { checked: "" }
          : {})
      }
    );

    acceptedInput.onchange = () => {
      operation._accepted = acceptedInput.checked;
      row.classList.toggle(
        "rejected",
        !operation._accepted
      );
    };

    const row = el(
      "div",
      {
        class:
          "lore-plan-op"
          + (operation._accepted ? "" : " rejected")
      },
      acceptedInput,
      el(
        "div",
        {},
        el("div", {}, describe(operation)),
        el(
          "details",
          {},
          el("summary", { class: "small dim" }, "Details"),
          el(
            "pre",
            { class: "lore-plan-json" },
            JSON.stringify(stripPlanUIFields(operation), null, 2)
          )
        )
      )
    );

    group.append(row);
  }

  container.append(group);
}

function stripPlanUIFields(value) {
  if (Array.isArray(value)) {
    return value.map(stripPlanUIFields);
  }

  if (value && typeof value === "object") {
    const result = {};

    for (const [key, item] of Object.entries(value)) {
      if (key === "_accepted") {
        continue;
      }

      result[key] = stripPlanUIFields(item);
    }

    return result;
  }

  return value;
}

function acceptedGeneratorPlan(plan) {
  return {
    analysis: stripPlanUIFields(plan.analysis || {}),
    book_ops: plan.book_ops
      .filter(operation => operation._accepted)
      .map(stripPlanUIFields),
    link_ops: plan.link_ops
      .filter(operation => operation._accepted)
      .map(stripPlanUIFields),
    entry_ops: plan.entry_ops
      .filter(operation => operation._accepted)
      .map(stripPlanUIFields)
  };
}