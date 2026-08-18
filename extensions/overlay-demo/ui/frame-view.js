// The full-window surface. `registerView` hands it a container the host owns,
// so a throw in here is charged to this extension and disabling it takes the
// whole view down -- neither of which is true of an overlay appended to
// `document.body`.

import { readFrame, writeFrame } from "./client.js";

const MAX_FRAME = 600;

export function createFrameView(sonder) {
  return {
    id: "overlay-frame",
    label: "Story frame",
    async render(container) {
      container.append(el("div", { class: "ext-overlay-demo-shell" },
        el("header", { class: "ext-overlay-demo-head" },
          el("h2", {}, "Story frame"),
          el("button", {
            class: "ext-overlay-demo-close",
            onclick: () => sonder.closeView()
          }, "Close")),
        await body(sonder)));
    }
  };
}

async function body(sonder) {
  const { chatId } = sonder.state();
  if (!chatId) {
    return el("p", { class: "ext-overlay-demo-empty" },
      "Open a story to give it a standing frame.");
  }

  const current = await readFrame(sonder);
  const input = el("textarea", {
    class: "ext-overlay-demo-input",
    rows: 6,
    maxlength: String(MAX_FRAME),
    placeholder: "The ship is three days into a fuel emergency; corridors are dim and cold."
  });
  // Story-derived text is DATA, not UI: `el()` runs plain string children
  // through the UI translator, so anything that came back from a route goes in
  // through `txt()` under `translate="no"`. The same two-part guard the
  // transcript uses.
  input.value = String(current.frame || "");

  const status = el("p", { class: "ext-overlay-demo-status", translate: "no" },
    txt(revisionLabel(current)));

  const save = el("button", {
    class: "primary",
    onclick: async () => {
      const saved = await writeFrame(sonder, input.value);
      status.replaceChildren(txt(revisionLabel(saved)));
      toast(saved.frame ? "Frame installed." : "Frame cleared.", "ok");
    }
  }, "Save frame");

  return el("div", { class: "ext-overlay-demo-body" },
    el("p", { class: "ext-overlay-demo-hint" },
      "This text is given to the narrator on every beat of this story until "
      + "you clear it. Put SETTING and standing situation here — the frame the "
      + "story is told inside. Facts the engine already tracks (who is where, "
      + "which doors are open) belong in the world, not here: the narrator "
      + "checks those against the committed scene, and a frame that "
      + "contradicts them makes the two fight."),
    input, save, status);
}

function revisionLabel(record) {
  if (!record || !record.frame) return "No frame installed.";
  return `Installed — revision ${record.revision}.`;
}
