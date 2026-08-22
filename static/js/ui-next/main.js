const root = document.documentElement;

if (root.dataset.uiNextEntry !== "development") {
  throw new Error("Replacement interface entry marker is missing.");
}

root.dataset.uiNextReady = "true";
