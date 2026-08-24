import { initAccessibility } from "../ui/accessibility.js?release=alpha98-ui9-ff279a1d1d7f";
import { bootRuntime } from "./bootstrap.js?release=alpha98-ui9-ff279a1d1d7f";

// UI_CATALOG_START: application-start fallback copy used before localization is available.
const APPLICATION_FAILURE_COPY = Object.freeze({
  forbidden: "This account cannot open the replacement interface.",
  failed: "The interface could not start.",
  unchanged: "Your saved stories were not changed. Return to sign in or try again.",
});
// UI_CATALOG_END

const root = document.documentElement;

if (!new Set(["application", "runtime-harness"]).has(root.dataset.uiNextEntry)) {
  throw new Error("Replacement interface entry marker is missing.");
}

initAccessibility();
const application = root.dataset.uiNextEntry === "application";
bootRuntime({ host: application, shell: application }).catch(error => {
  root.dataset.uiNextState = "failed";
  if (!application) return;
  const view = document.querySelector("[data-shell-destination-view]");
  if (!view) return;
  const state = document.createElement("div");
  state.className = "ui-empty";
  state.dataset.state = "error";
  const title = document.createElement("strong");
  title.className = "ui-empty__title";
  title.textContent = error?.kind === "forbidden"
    ? APPLICATION_FAILURE_COPY.forbidden
    : APPLICATION_FAILURE_COPY.failed;
  const detail = document.createElement("p");
  detail.textContent = APPLICATION_FAILURE_COPY.unchanged;
  state.append(title, detail);
  view.replaceChildren(state);
});
