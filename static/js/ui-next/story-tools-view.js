export const MODULE_RELEASE = "alpha98-ui5-7fa758fa6df7";

// UI_CATALOG_START: Story Tool platform states shown before family modules land.
const COPY = Object.freeze({
  list: "Story tools",
  allTools: "All tools",
  chooseStory: "Choose a story to use Story Tools.",
  platformReady: "This current-story tool is ready for its dedicated controls.",
});
// UI_CATALOG_END

function element(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(documentRef, label) {
  const node = element(documentRef, "button", "ui-story-tools__item ui-button ui-button--quiet");
  node.type = "button";
  node.setAttribute("aria-label", label);
  return node;
}

const TOOL_ICONS = Object.freeze({
  cast: "cast", world: "world", style: "style", dialogue: "dialogue",
  attire: "clothing", backdrops: "image", ambience: "ambience",
  conditions: "conditions", frames: "frames", multiplayer: "multiplayer",
});

function icon(documentRef, name) {
  const svg = documentRef.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("ui-icon", "ui-story-tools__icon");
  svg.setAttribute("aria-hidden", "true");
  const use = documentRef.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/assets/icons/sonder-icons.svg?release=${MODULE_RELEASE}#icon-${name}`);
  svg.append(use);
  return svg;
}

export function mountStoryTools(options = {}) {
  const { services, registry, target, tools } = options;
  const documentRef = options.document || document;
  if (!services?.store || !services?.storyTools || !registry || !target) {
    throw new TypeError("Story Tool presentation requires a target and runtime.");
  }
  const t = services.localizer.t;
  const root = element(documentRef, "section", "ui-story-tools");
  root.dataset.storyTools = "true";
  const list = element(documentRef, "nav", "ui-story-tools__list");
  list.dataset.storyToolList = "true";
  list.setAttribute("aria-label", t(COPY.list));
  const panel = element(documentRef, "section", "ui-story-tools__panel");
  panel.dataset.storyToolPanel = "true";
  const controls = new Map();
  let mountedTool = null;

  for (const tool of registry.STORY_TOOLS) {
    const control = button(documentRef, t(tool.label));
    control.dataset.storyTool = tool.id;
    control.title = t(tool.label);
    const index = element(documentRef, "span", "ui-story-tools__index", String(tool.index).padStart(2, "0"));
    index.setAttribute("aria-hidden", "true");
    const copy = element(documentRef, "span", "ui-story-tools__copy");
    copy.append(
      element(documentRef, "strong", "ui-story-tools__label", t(tool.label)),
      element(documentRef, "small", "ui-story-tools__detail", t(tool.detail)),
    );
    control.append(
      index,
      icon(documentRef, TOOL_ICONS[tool.id] || "tools"),
      copy,
      icon(documentRef, "chevron-right"),
    );
    control.addEventListener("click", () => services.storyTools.open(tool.id, {
      preserveLayers: true,
    }));
    controls.set(tool.id, control);
    list.append(control);
  }

  const render = state => {
    mountedTool?.teardown?.();
    mountedTool = null;
    if (state.story?.status !== "ready") {
      list.hidden = true;
      root.dataset.detail = "false";
      panel.hidden = false;
      panel.replaceChildren(element(documentRef, "p", "ui-story-tools__state", t(COPY.chooseStory)));
      return;
    }
    const selectedId = state.inspector?.toolId || null;
    const active = selectedId ? registry.resolveStoryTool(selectedId) : null;
    for (const [id, control] of controls) {
      if (active && id === active.id) control.setAttribute("aria-current", "page");
      else control.removeAttribute("aria-current");
    }
    list.hidden = false;
    root.dataset.detail = String(Boolean(selectedId));
    panel.hidden = !selectedId;
    if (!selectedId) {
      panel.replaceChildren();
      return;
    }
    const back = element(documentRef, "button", "ui-button ui-button--quiet ui-story-tools__back");
    back.type = "button";
    back.append(icon(documentRef, "chevron-left"), element(documentRef, "span", "", t(COPY.allTools)));
    back.setAttribute("aria-label", t(COPY.allTools));
    back.addEventListener("click", () => {
      services.storyTools.close();
      queueMicrotask(() => controls.get(active.id)?.focus());
    });
    const heading = element(documentRef, "h3", "ui-heading ui-heading--3", t(active.label));
    heading.tabIndex = -1;
    const detail = element(documentRef, "p", "ui-muted", t(active.detail));
    const status = element(
      documentRef,
      "p",
      "ui-story-tools__state",
      state.story?.status === "ready" ? t(COPY.platformReady) : t(COPY.chooseStory),
    );
    status.dataset.state = state.inspector?.status || "empty";
    panel.replaceChildren(back, heading, detail, status);
    if (options.interactive !== false && state.story?.status === "ready" && tools) {
      const toolTarget = element(documentRef, "div", "ui-story-tools__content");
      toolTarget.dataset.storyToolContent = active.id;
      panel.replaceChildren(back, heading, detail, toolTarget);
      mountedTool = tools.mountStoryTool(active.id, {
        document: documentRef,
        services,
        target: toolTarget,
        compact: options.compact === true,
      });
      if (!mountedTool) toolTarget.append(status);
    }
  };

  root.append(list, panel);
  target.replaceChildren(root);
  const select = state => ({ story: state.story, inspector: state.inspector });
  const unsubscribe = services.store.subscribe(select, render, {
    equality: (left, right) => left.story === right.story && left.inspector === right.inspector,
  });
  render(select(services.store.getSnapshot()));
  services.localizer.localize(root);

  return Object.freeze({
    element: root,
    teardown() {
      unsubscribe();
      mountedTool?.teardown?.();
      root.remove();
    },
  });
}
