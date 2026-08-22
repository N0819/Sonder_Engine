import { initAccessibility } from "../ui/accessibility.js?release=wp03.1";
import { bootRuntime } from "./bootstrap.js?release=wp03.1";

const root = document.documentElement;

if (!new Set(["application", "runtime-harness"]).has(root.dataset.uiNextEntry)) {
  throw new Error("Replacement interface entry marker is missing.");
}

initAccessibility();
const application = root.dataset.uiNextEntry === "application";
bootRuntime({ host: application, shell: application }).catch(() => {
  root.dataset.uiNextState = "failed";
});
