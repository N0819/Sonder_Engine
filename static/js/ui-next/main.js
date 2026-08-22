import { initAccessibility } from "../ui/accessibility.js?release=wp03.1";
import { bootRuntime } from "./bootstrap.js?release=wp03.1";

const root = document.documentElement;

if (!new Set(["development", "runtime-harness"]).has(root.dataset.uiNextEntry)) {
  throw new Error("Replacement interface entry marker is missing.");
}

initAccessibility();
bootRuntime().catch(() => {
  root.dataset.uiNextState = "failed";
});
