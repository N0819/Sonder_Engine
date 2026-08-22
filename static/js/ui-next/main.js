import { initAccessibility } from "../ui/accessibility.js?release=wp02.1";
import { bootRuntime } from "./bootstrap.js?release=wp02.1";

const root = document.documentElement;

if (root.dataset.uiNextEntry !== "development") {
  throw new Error("Replacement interface entry marker is missing.");
}

initAccessibility();
bootRuntime().catch(() => {
  root.dataset.uiNextState = "failed";
});
