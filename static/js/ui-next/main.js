import { initAccessibility } from "../ui/accessibility.js?release=wp03.1";
import { bootRuntime } from "./bootstrap.js?release=wp03.1";

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
    ? "This account cannot open the replacement interface."
    : "The interface could not start.";
  const detail = document.createElement("p");
  detail.textContent = "Your saved stories were not changed. Return to sign in or try again.";
  state.append(title, detail);
  view.replaceChildren(state);
});
