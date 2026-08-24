export const MODULE_RELEASE = "alpha98-ui12-7eaf6b3481a3";

import {
  createStoryEditor,
  createStoryImporter,
} from "./library-editors/story.js?release=alpha98-ui12-7eaf6b3481a3";
import {
  createPersonEditor,
  createPersonImporter,
} from "./library-editors/character-persona.js?release=alpha98-ui12-7eaf6b3481a3";

// UI_CATALOG_START: Library authoring status copy.
const COPY = Object.freeze({
  loading: "Opening editor…",
  loadingDetail: "Reading the current saved document.",
  unavailable: "Editor unavailable",
  waiting: "Choose an item before editing.",
  saving: "Saving…",
  saved: "Saved to Library",
  dirty: "Draft saved on this device",
  conflict: "This story changed elsewhere. Your draft is still here.",
  failure: "Could not save. Your draft is still here.",
  previewing: "Generating preview…",
  previewFailure: "Preview failed. Your draft is still here.",
  back: "Back to story overview",
  backToLibrary: "Back to Library",
});
// UI_CATALOG_END

function node(documentRef, tag, className = "", text = "") {
  const element = documentRef.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function stateBlock(documentRef, title, detail, tone = "") {
  const block = node(documentRef, "div", "ui-empty");
  block.dataset.state = tone || "loading";
  block.append(
    node(documentRef, "strong", "ui-empty__title", title),
    node(documentRef, "p", "ui-muted", detail),
  );
  return block;
}

function statusCopy(state, t) {
  if (state.status === "saving") return t(COPY.saving);
  if (state.status === "saved") return t(COPY.saved);
  if (state.status === "conflict") return t(COPY.conflict);
  if (state.status === "recoverable-error") return t(COPY.failure);
  if (state.status === "previewing") return t(COPY.previewing);
  if (state.status === "generation-error") return state.error || t(COPY.previewFailure);
  return t(COPY.dirty);
}

function returnToLibrary(services, focusIdentity) {
  services.library.focusOnReturn(focusIdentity);
  return services.authoring.returnToLibrary();
}

export function isPersonAuthoringRoute(route) {
  if (route?.destination !== "library") return false;
  if (!["edit", "create", "import", "story-card"].includes(route.query?.mode)) {
    return false;
  }
  const segment = route.segments?.[0];
  const item = String(route.query?.item || "");
  return ["characters", "personas"].includes(segment)
    || /^(character|persona):[1-9][0-9]*$/.test(item);
}

export function mountLibraryAuthoring(options = {}) {
  const documentRef = options.document || document;
  const { services, target, onTitle } = options;
  let rendering = false;
  const render = (library, force = false) => {
    if (rendering) return;
    rendering = true;
    const state = library?.authoring;
    const renderRevision = String(Number(state?.renderRevision || 0));
    if (!force && state?.owner && state.status === "dirty"
        && target.dataset.authoringOwner === state.owner
        && target.dataset.authoringRenderRevision === renderRevision
        && target.querySelector("[data-story-editor], [data-person-editor]")) {
      const status = target.querySelector("[data-save-status]");
      if (status) {
        status.textContent = statusCopy(state, services.localizer.t);
        status.dataset.saveStatus = state.status;
      }
      rendering = false;
      return;
    }
    if (!state || state.status === "loading") {
      delete target.dataset.authoringOwner;
      delete target.dataset.authoringRenderRevision;
      target.replaceChildren(stateBlock(
        documentRef,
        services.localizer.t(COPY.loading),
        services.localizer.t(COPY.loadingDetail),
      ));
      rendering = false;
      return;
    }
    if (state.kind === "story" && state.mode === "import") {
      const wrapper = node(documentRef, "section", "ui-authoring");
      const back = node(
        documentRef, "button", "ui-button ui-button--quiet",
        services.localizer.t(COPY.backToLibrary),
      );
      back.type = "button";
      back.dataset.focusIdentity = "destination:library";
      back.addEventListener("click", () => returnToLibrary(services, back.dataset.focusIdentity));
      wrapper.append(back, createStoryImporter({
        document: documentRef, services, state,
      }));
      delete target.dataset.authoringOwner;
      delete target.dataset.authoringRenderRevision;
      target.replaceChildren(wrapper);
      services.localizer.localize(target);
      onTitle?.("Import story archive");
      rendering = false;
      return;
    }
    if (["character", "persona"].includes(state.kind) && state.mode === "import") {
      const wrapper = node(documentRef, "section", "ui-authoring");
      const back = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.backToLibrary));
      back.type = "button";
      back.dataset.focusIdentity = "destination:library";
      back.addEventListener("click", () => returnToLibrary(services, back.dataset.focusIdentity));
      wrapper.append(back, createPersonImporter({ document: documentRef, services, state }));
      target.dataset.authoringOwner = state.owner;
      target.dataset.authoringRenderRevision = renderRevision;
      target.replaceChildren(wrapper);
      services.localizer.localize(target);
      onTitle?.(`Import ${state.kind}`);
      rendering = false;
      return;
    }
    if (!state.draft || state.kind !== "story") {
      if (state.draft && (state.kind === "character" || state.kind === "persona")) {
        const wrapper = node(documentRef, "section", "ui-authoring");
        const back = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.backToLibrary));
        back.type = "button";
        back.dataset.focusIdentity = `library-item:${state.kind}:${state.id}`;
        back.addEventListener("click", () => returnToLibrary(services, back.dataset.focusIdentity));
        const status = node(documentRef, "p", "ui-authoring__status", statusCopy(state, services.localizer.t));
        status.setAttribute("role", "status");
        status.dataset.saveStatus = state.status;
        const topbar = node(documentRef, "div", "ui-authoring__topbar");
        topbar.append(back, status);
        wrapper.append(topbar, createPersonEditor({
          document: documentRef, services, state,
        }));
        target.dataset.authoringOwner = state.owner;
        target.dataset.authoringRenderRevision = renderRevision;
        target.replaceChildren(wrapper);
        services.localizer.localize(target);
        onTitle?.(state.draft.identity?.name || "Person editor");
        rendering = false;
        return;
      }
      target.replaceChildren(stateBlock(
        documentRef,
        services.localizer.t(COPY.unavailable),
        state.error || services.localizer.t(COPY.waiting),
        "error",
      ));
      delete target.dataset.authoringOwner;
      delete target.dataset.authoringRenderRevision;
      rendering = false;
      return;
    }
    const wrapper = node(documentRef, "section", "ui-authoring");
    const back = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.back));
    back.type = "button";
    back.dataset.focusIdentity = state.id
      ? `library-item:${state.kind}:${state.id}` : "destination:library";
    back.addEventListener("click", () => returnToLibrary(services, back.dataset.focusIdentity));
    const status = node(documentRef, "p", "ui-authoring__status", statusCopy(state, services.localizer.t));
    status.setAttribute("role", "status");
    status.dataset.saveStatus = state.status;
    const topbar = node(documentRef, "div", "ui-authoring__topbar");
    topbar.append(back, status);
    wrapper.append(topbar, createStoryEditor({
      document: documentRef,
      services,
      state,
      onRender: () => render(services.store.getSnapshot().library, true),
    }));
    target.dataset.authoringOwner = state.owner;
    target.dataset.authoringRenderRevision = renderRevision;
    target.replaceChildren(wrapper);
    services.localizer.localize(target);
    onTitle?.(state.draft.name || "Story editor");
    rendering = false;
  };
  const unsubscribe = services.store.subscribe(
    state => state.library,
    library => render(library),
  );
  render(services.store.getSnapshot().library);
  return Object.freeze({ teardown: unsubscribe });
}

export function createLibraryAuthoringWorkspace(options = {}) {
  const documentRef = options.document || document;
  const section = node(documentRef, "section", "ui-person-workspace");
  section.dataset.personWorkspace = "true";
  section.setAttribute("aria-label", "Character and Persona authoring");
  const target = node(documentRef, "div", "ui-person-workspace__mount");
  section.append(target);
  const mounted = mountLibraryAuthoring({
    ...options,
    document: documentRef,
    target,
  });
  return Object.freeze({ element: section, teardown: mounted.teardown });
}
