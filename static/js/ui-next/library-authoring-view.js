export const MODULE_RELEASE = "wp07.1";

import {
  createStoryEditor,
  createStoryImporter,
} from "./library-editors/story.js?release=wp07.1";
import {
  createPersonEditor,
  createPersonImporter,
} from "./library-editors/character-persona.js?release=wp07.1";

// UI_CATALOG_START: Library authoring status copy.
const COPY = Object.freeze({
  loading: "Opening editor…",
  loadingDetail: "Reading the current saved document.",
  unavailable: "Editor unavailable",
  waiting: "Choose an item before editing.",
  saving: "Saving…",
  saved: "Saved",
  dirty: "Unsaved draft",
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

export function mountLibraryAuthoring(options = {}) {
  const documentRef = options.document || document;
  const { services, target, onTitle } = options;
  let rendering = false;
  const render = library => {
    if (rendering) return;
    rendering = true;
    const state = library?.authoring;
    if (state?.owner && state.status === "dirty"
        && target.dataset.authoringOwner === state.owner
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
      back.addEventListener("click", () => services.library.navigate({
        type: "story", query: {},
      }));
      wrapper.append(back, createStoryImporter({
        document: documentRef, services, state,
      }));
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
      back.addEventListener("click", () => services.library.navigate({ type: state.kind, query: {} }));
      wrapper.append(back, createPersonImporter({ document: documentRef, services, state }));
      target.dataset.authoringOwner = state.owner;
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
        back.addEventListener("click", () => services.library.navigate({
          type: state.kind, query: { item: `${state.kind}:${state.id}` },
        }));
        const status = node(documentRef, "p", "ui-authoring__status", statusCopy(state, services.localizer.t));
        status.setAttribute("role", "status");
        status.dataset.saveStatus = state.status;
        wrapper.append(back, status, createPersonEditor({
          document: documentRef, services, state,
        }));
        target.dataset.authoringOwner = state.owner;
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
      rendering = false;
      return;
    }
    const wrapper = node(documentRef, "section", "ui-authoring");
    const back = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.back));
    back.type = "button";
    back.addEventListener("click", () => {
      const route = services.library.currentRoute();
      services.library.navigate({
        type: state.kind,
        query: { ...(route?.query || {}), mode: "" },
      });
    });
    const status = node(documentRef, "p", "ui-authoring__status", statusCopy(state, services.localizer.t));
    status.setAttribute("role", "status");
    status.dataset.saveStatus = state.status;
    wrapper.append(back, status, createStoryEditor({
      document: documentRef,
      services,
      state,
      onRender: () => render(services.store.getSnapshot().library),
    }));
    target.dataset.authoringOwner = state.owner;
    target.replaceChildren(wrapper);
    services.localizer.localize(target);
    onTitle?.(state.draft.name || "Story editor");
    rendering = false;
  };
  const unsubscribe = services.store.subscribe(state => state.library, render);
  render(services.store.getSnapshot().library);
  return Object.freeze({ teardown: unsubscribe });
}
