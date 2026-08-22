import { initAccessibility } from "../ui/accessibility.js";

const root = document.documentElement;

if (root.dataset.uiNextEntry !== "development") {
  throw new Error("Replacement interface entry marker is missing.");
}

initAccessibility();
root.dataset.uiNextReady = "true";
