"use strict";

function themePreview(theme) {
  const swatches = theme.swatches || [];
  return el("div", { class: "theme-preview", "aria-hidden": "true" },
    el("div", { class: "theme-preview-side", style: `background:${swatches[0] || "#111"}` },
      el("span", { style: `background:${swatches[2] || "#888"}` }),
      el("span", {}),
      el("span", {})),
    el("div", { class: "theme-preview-main", style: `background:${swatches[1] || "#222"}` },
      el("div", { class: "theme-preview-top" },
        el("span", { style: `background:${swatches[2] || "#888"}` }),
        el("span", { style: `background:${swatches[3] || "#aaa"}` })),
      el("div", { class: "theme-preview-lines" },
        el("i", {}), el("i", {}), el("i", {})),
      el("div", { class: "theme-preview-composer", style: `border-color:${swatches[2] || "#888"}` })));
}

function openAppearanceSettings() {
  const appearance = window.SONDER_APPEARANCE;
  if (!appearance) {
    toast("Appearance controls could not be loaded.", "err");
    return;
  }

  modal("Appearance", body => {
    const themeGrid = el("div", { class: "theme-grid" });
    const sizeRow = el("div", { class: "segmented-control", role: "group", "aria-label": "Story text size" });

    const syncThemeSelection = () => {
      const active = appearance.currentTheme();
      for (const card of themeGrid.querySelectorAll(".theme-choice")) {
        const selected = card.dataset.themeId === active;
        card.classList.toggle("selected", selected);
        card.setAttribute("aria-pressed", selected ? "true" : "false");
        const badge = card.querySelector(".theme-selected-badge");
        if (badge) badge.textContent = selected ? "Selected" : "Use theme";
      }
    };

    const syncSizeSelection = () => {
      const active = appearance.currentProseSize();
      for (const button of sizeRow.querySelectorAll("button")) {
        const selected = button.dataset.size === active;
        button.classList.toggle("on", selected);
        button.setAttribute("aria-pressed", selected ? "true" : "false");
      }
    };

    for (const theme of appearance.themes) {
      const card = el("button", {
        class: "theme-choice",
        type: "button",
        "data-theme-id": theme.id,
        "aria-label": `Use ${theme.name} theme`,
        onclick: () => {
          appearance.applyTheme(theme.id);
          syncThemeSelection();
          toast(`${theme.name} theme applied.`, "ok", 1800);
        },
      },
        themePreview(theme),
        el("span", { class: "theme-choice-copy" },
          el("strong", {}, theme.name),
          el("span", { class: "small dim" }, theme.description)),
        el("span", { class: "theme-selected-badge badge" }, "Use theme"));
      themeGrid.append(card);
    }

    const proseSizes = [
      ["15", "Compact"],
      ["17", "Comfortable"],
      ["19", "Large"],
      ["21", "Extra large"],
    ];
    for (const [size, label] of proseSizes) {
      sizeRow.append(el("button", {
        type: "button",
        "data-size": size,
        onclick: () => {
          appearance.applyProseSize(size);
          syncSizeSelection();
        },
      }, label));
    }

    const resetButton = el("button", {
      type: "button",
      onclick: () => {
        appearance.applyTheme(appearance.DEFAULT_THEME);
        appearance.applyProseSize(appearance.DEFAULT_PROSE_SIZE);
        syncThemeSelection();
        syncSizeSelection();
        toast("Appearance reset to Sonder defaults.", "ok");
      },
    }, "Reset appearance");

    body.append(
      el("p", { class: "appearance-intro" },
        "Themes change only this browser. Stories, exports, prompts, and generated prose are untouched."),
      el("div", { class: "section-title" }, "Theme"),
      themeGrid,
      el("div", { class: "appearance-reading-row" },
        el("div", {},
          el("div", { class: "section-title" }, "Story text size"),
          el("div", { class: "small dim" }, "Adjusts the fiction transcript without enlarging the controls.")),
        sizeRow),
      el("div", { class: "appearance-actions" }, resetButton,
        el("button", { class: "primary", type: "button", onclick: closeModal }, "Done")));

    syncThemeSelection();
    syncSizeSelection();
  }, { wide: true, autoFocus: false });
}

const appearanceButton = document.getElementById("b-theme");
if (appearanceButton) appearanceButton.onclick = openAppearanceSettings;
