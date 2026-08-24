export const MODULE_RELEASE = "alpha98-ui13-a39372e1d8d1";

function savedNavigation(localState) {
  const panes = localState.snapshot().panes || {};
  return panes.navigation || {};
}

export function createAppHeader(options = {}) {
  const { services } = options;
  const documentRef = options.document || document;
  const root = options.root || documentRef.documentElement;
  const collapse = documentRef.querySelector("[data-shell-nav-collapse]");
  const label = documentRef.querySelector("[data-shell-nav-collapse-label]");
  const mark = documentRef.querySelector("[data-shell-nav-collapse-mark]");
  if (!collapse || !label || !mark) throw new Error("The application header controls are incomplete.");

  let collapsed = savedNavigation(services.localState).collapsed === true;
  const apply = () => {
    root.dataset.navCollapsed = String(collapsed);
    collapse.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
    label.textContent = collapsed ? "Expand" : "Collapse";
    mark.textContent = collapsed ? "›" : "‹";
  };
  const persist = () => {
    const panes = services.localState.snapshot().panes || {};
    services.localState.setRecord("panes", {
      ...panes,
      navigation: { ...(panes.navigation || {}), collapsed },
    });
  };
  const toggle = () => {
    collapsed = !collapsed;
    persist();
    apply();
  };
  collapse.addEventListener("click", toggle);
  apply();
  return Object.freeze({
    setLayout: () => apply(),
    teardown() { collapse.removeEventListener("click", toggle); },
  });
}
