export const MODULE_RELEASE = "alpha98-ui6-57d168ae23cf";

export function element(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text !== "" && text !== null && text !== undefined) node.textContent = String(text);
  return node;
}

export function button(documentRef, label, className = "ui-button ui-button--quiet") {
  const node = element(documentRef, "button", className, label);
  node.type = "button";
  return node;
}

export function markData(node) {
  node.setAttribute("translate", "no");
  return node;
}

export function stateMessage(documentRef, state, message, retry = null) {
  const box = element(documentRef, "div", "ui-tool-state");
  box.dataset.state = state;
  box.setAttribute("role", "status");
  if (state === "error" || state === "offline") box.setAttribute("aria-live", "polite");
  box.append(element(documentRef, "p", "ui-tool-state__message", message));
  if (retry) {
    const control = button(documentRef, "Try again");
    control.addEventListener("click", retry);
    box.append(control);
  }
  return box;
}

export function replaceLocalized(services, target, ...nodes) {
  target.replaceChildren(...nodes);
  services.localizer.localize(target);
}

export function frameQuery(frameId) {
  return frameId === null || frameId === undefined ? "" : `?frame_id=${encodeURIComponent(frameId)}`;
}

export function errorState(error) {
  return {
    state: error?.kind === "network" ? "offline" : "error",
    message: error?.userMessage || error?.message || "This tool is unavailable right now.",
  };
}

let nextScopeId = 0;

export function toolScope(services, toolId) {
  let live = true;
  const scopeId = ++nextScopeId;
  const keys = new Set();
  const current = () => services.storyTools.current();
  const run = async (method, key, path, body) => {
    if (!live || current().toolId !== toolId) return null;
    const scopedKey = `${scopeId}:${key}`;
    keys.add(scopedKey);
    return services.storyTools.request(toolId, scopedKey, method, path, body);
  };
  return Object.freeze({
    current,
    run,
    teardown() {
      live = false;
      for (const key of keys) services.storyTools.cancelRequest(toolId, key);
      keys.clear();
    },
    isLive() { return live && current().toolId === toolId; },
  });
}

export function fieldLabel(documentRef, label, control, hint = "") {
  const wrap = element(documentRef, "label", "ui-tool-field");
  wrap.append(element(documentRef, "span", "ui-tool-field__label", label), control);
  if (hint) wrap.append(element(documentRef, "span", "ui-tool-field__hint", hint));
  return wrap;
}
