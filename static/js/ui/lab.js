import { appearance } from "./appearance.js";
import { initAccessibility, updateAccessibility } from "./accessibility.js";
import { createIcon, setIconButton } from "./icons.js";
import { associateFieldError, connectTabs, createAnnouncer, createOverlayController, createRovingFocus } from "./components/index.js";

const root = document.documentElement;
const preferences = initAccessibility();

for (const mount of document.querySelectorAll("[data-icon]")) mount.replaceChildren(createIcon(mount.dataset.icon));
setIconButton(document.getElementById("icon-only"), "more", { accessibleName: "More actions" });
setIconButton(document.getElementById("close-dialog"), "close", { accessibleName: "Close dialog" });
setIconButton(document.getElementById("close-sheet"), "close", { accessibleName: "Close details" });

const themePicker = document.getElementById("theme-picker");
function selectTheme(button) {
  appearance.setTheme(button.dataset.themeChoice);
  for (const candidate of themePicker.children) candidate.setAttribute("aria-pressed", String(candidate === button));
}
themePicker.addEventListener("click", (event) => {
  const button = event.target.closest("[data-theme-choice]");
  if (button) selectTheme(button);
});
createRovingFocus(themePicker, { itemSelector: "[data-theme-choice]", onActivate: selectTheme });
const activeTheme = themePicker.querySelector(`[data-theme-choice="${root.dataset.theme}"]`);
if (activeTheme) selectTheme(activeTheme);

const a11yMode = document.getElementById("a11y-mode");
a11yMode.checked = preferences.mode;
for (const input of document.querySelectorAll("[data-a11y]")) input.checked = preferences[input.dataset.a11y];
function syncA11yControls(next) {
  a11yMode.checked = next.mode;
  for (const input of document.querySelectorAll("[data-a11y]")) input.checked = next[input.dataset.a11y];
}
a11yMode.addEventListener("change", () => syncA11yControls(updateAccessibility({ mode: a11yMode.checked })));
for (const input of document.querySelectorAll("[data-a11y]")) {
  input.addEventListener("change", () => syncA11yControls(updateAccessibility({ [input.dataset.a11y]: input.checked })));
}

const densityPicker = document.getElementById("density-picker");
createRovingFocus(densityPicker, {
  itemSelector: "button",
  onActivate(button) { for (const candidate of densityPicker.children) candidate.setAttribute("aria-pressed", String(candidate === button)); },
});

connectTabs(document.querySelector("[role='tablist']"));
createRovingFocus(document.getElementById("story-menu"), { itemSelector: "[role^='menuitem']", orientation: "vertical", activate: false });

const form = document.getElementById("example-form");
const storyName = document.getElementById("story-name");
const storyNameError = document.getElementById("story-name-error");
form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = storyName.value.trim() ? "" : "Enter a story name before continuing.";
  associateFieldError(storyName, storyNameError, message);
  if (message) storyName.focus();
});
form.addEventListener("reset", () => associateFieldError(storyName, storyNameError, ""));

const dialog = createOverlayController(document.getElementById("dialog-overlay"));
document.getElementById("open-dialog").addEventListener("click", () => dialog.show());
document.getElementById("close-dialog").addEventListener("click", () => dialog.close("close-button"));
document.getElementById("cancel-dialog").addEventListener("click", () => dialog.close("cancel"));

const sheet = createOverlayController(document.getElementById("sheet-overlay"));
document.getElementById("open-sheet").addEventListener("click", () => sheet.show());
document.getElementById("close-sheet").addEventListener("click", () => sheet.close("close-button"));

const announcer = createAnnouncer();
document.getElementById("announce-status").addEventListener("click", () => announcer.announce("Archive export complete."));

root.dataset.uiNextReady = "true";
