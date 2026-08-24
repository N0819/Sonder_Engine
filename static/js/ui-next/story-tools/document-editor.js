export const MODULE_RELEASE = "alpha98-ui10-0415f377b12f";

import { button, element, replaceLocalized, stateMessage } from "./shared.js?release=alpha98-ui10-0415f377b12f";

// UI_CATALOG_START: shared explicit-save document controls.
const COPY = Object.freeze({
  advanced: "Advanced JSON",
  save: "Save changes",
  discard: "Discard draft",
  download: "Download draft",
  invalid: "Invalid JSON. Fix the highlighted document before saving.",
  saved: "Changes saved.",
  draft: "Unsaved draft restored from this browser.",
  saving: "Saving changes…",
  localUnavailable: "This draft is still open, but it is too large or sensitive for browser-local recovery. Download it before leaving.",
});
// UI_CATALOG_END

export function mountDocumentEditor(options) {
  const {
    services, target, document: documentRef, toolId, owner, serverValue,
    summary, validate, onSave,
  } = options;
  const recordType = `storytool-${toolId}`;
  const serverText = JSON.stringify(serverValue, null, 2);
  const restored = services.localState.getDraft(recordType, owner);
  let currentText = restored ?? serverText;
  let stopped = false;
  const root = element(documentRef, "div", "ui-tool-stack ui-document-editor");
  const summaryHost = element(documentRef, "section", "ui-tool-stack");
  const details = element(documentRef, "details", "ui-tool-card ui-document-editor__advanced");
  const heading = element(documentRef, "summary", "", COPY.advanced);
  const editor = element(documentRef, "textarea", "ui-document-editor__textarea");
  editor.value = currentText;
  editor.spellcheck = false;
  editor.setAttribute("aria-label", `${toolId} JSON`);
  const validation = element(documentRef, "p", "ui-field-error");
  validation.id = `ui-${toolId}-json-error`;
  validation.hidden = true;
  editor.setAttribute("aria-describedby", validation.id);
  details.append(heading, editor, validation);
  const actions = element(documentRef, "div", "ui-tool-inline");
  const save = button(documentRef, COPY.save, "ui-button ui-button--primary");
  const discard = button(documentRef, COPY.discard);
  const download = element(documentRef, "a", "ui-button ui-button--quiet", COPY.download);
  download.href = "#";
  download.download = `sonder-${toolId}-${owner}.json`;
  const status = element(documentRef, "div", "ui-document-editor__status");
  status.setAttribute("role", "status");
  if (restored !== null) status.textContent = services.localizer.t(COPY.draft);
  actions.append(save, discard, download);
  root.append(summaryHost, details, actions, status);

  const persistDraft = () => {
    try {
      services.localState.setDraft(recordType, owner, currentText);
      status.textContent = services.localizer.t(COPY.draft);
      return true;
    } catch {
      status.textContent = services.localizer.t(COPY.localUnavailable);
      return false;
    }
  };

  const parse = () => {
    try {
      const value = JSON.parse(editor.value);
      const message = validate?.(value) || "";
      editor.setCustomValidity(message);
      validation.textContent = message;
      validation.hidden = !message;
      return message ? null : value;
    } catch {
      editor.setCustomValidity(COPY.invalid);
      validation.textContent = COPY.invalid;
      validation.hidden = false;
      return null;
    }
  };
  const setDocument = (valueOrUpdater, rerender = false) => {
    let base;
    try { base = JSON.parse(editor.value); }
    catch { base = JSON.parse(serverText); }
    const value = typeof valueOrUpdater === "function"
      ? valueOrUpdater(base)
      : valueOrUpdater;
    currentText = JSON.stringify(value, null, 2);
    editor.value = currentText;
    persistDraft();
    if (rerender) renderSummary(value);
  };
  const renderSummary = value => {
    const nodes = summary?.(value, setDocument) || [];
    summaryHost.replaceChildren(...(Array.isArray(nodes) ? nodes : [nodes]));
    services.localizer.localize(summaryHost);
  };
  try { renderSummary(JSON.parse(currentText)); }
  catch { renderSummary(JSON.parse(serverText)); parse(); }

  editor.addEventListener("input", () => {
    currentText = editor.value;
    persistDraft();
    const parsed = parse();
    if (parsed) renderSummary(parsed);
  });
  save.addEventListener("click", async () => {
    const parsed = parse();
    if (!parsed) {
      details.open = true;
      status.textContent = validation.textContent;
      return editor.focus();
    }
    save.disabled = true;
    status.replaceChildren(stateMessage(documentRef, "loading", COPY.saving));
    try {
      await onSave(parsed);
      if (stopped) return;
      services.localState.clearDraft(recordType, owner);
      currentText = JSON.stringify(parsed, null, 2);
      editor.value = currentText;
      status.textContent = services.localizer.t(COPY.saved);
      renderSummary(parsed);
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      status.replaceChildren(stateMessage(
        documentRef,
        error?.kind === "network" ? "offline" : "error",
        error?.userMessage || error?.message || "Changes could not be saved.",
      ));
    } finally {
      if (!stopped) save.disabled = false;
      services.localizer.localize(status);
    }
  });
  discard.addEventListener("click", () => {
    services.localState.clearDraft(recordType, owner);
    currentText = serverText;
    editor.value = currentText;
    editor.setCustomValidity("");
    validation.hidden = true;
    status.textContent = "";
    renderSummary(JSON.parse(serverText));
  });
  download.addEventListener("click", () => {
    const previous = download.href.startsWith("blob:") ? download.href : null;
    download.href = URL.createObjectURL(new Blob(
      [editor.value], { type: "application/json;charset=utf-8" },
    ));
    if (previous) URL.revokeObjectURL(previous);
  });
  replaceLocalized(services, target, root);
  return Object.freeze({
    element: root,
    editor,
    parse,
    teardown() {
      stopped = true;
      if (download.href.startsWith("blob:")) URL.revokeObjectURL(download.href);
      root.remove();
    },
  });
}
