// Extension-v2 destination. It receives only its owner-bound facade and the
// contained mount node supplied by Sonder; it uses no private host helpers.

import { readFrame, writeFrame } from "./client.js";

const MAX_FRAME = 600;

function element(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "class") node.className = value;
    else if (name.startsWith("on") && typeof value === "function") {
      node.addEventListener(name.slice(2).toLowerCase(), value);
    } else node.setAttribute(name, value);
  }
  for (const child of children.flat()) {
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function createFrameView(sonder) {
  return {
    id: "overlay-frame",
    title: "Story frame",
    async render(container) {
      const shell = element("div", { class: "ext-overlay-demo-shell" });
      shell.append(element("h2", { class: "ext-overlay-demo-title" }, "Story frame"));
      container.append(shell);
      shell.append(await body(sonder));
    },
  };
}

async function body(sonder) {
  const { chatId } = sonder.state();
  if (!chatId) {
    return element("p", { class: "ext-overlay-demo-empty" },
      "Open a story to give it a standing frame.");
  }

  const current = await readFrame(sonder);
  const input = element("textarea", {
    class: "ext-overlay-demo-input",
    rows: "6",
    maxlength: String(MAX_FRAME),
    placeholder: "The ship is three days into a fuel emergency; corridors are dim and cold.",
  });
  input.value = String(current.frame || "");

  const status = element("p", {
    class: "ext-overlay-demo-status",
    translate: "no",
    role: "status",
  }, revisionLabel(current));

  const save = element("button", {
    class: "ext-overlay-demo-save",
    type: "button",
    onclick: async () => {
      save.disabled = true;
      try {
        const saved = await writeFrame(sonder, input.value);
        status.textContent = revisionLabel(saved);
        sonder.notify({
          title: "Story frame",
          body: saved.frame ? "Frame installed." : "Frame cleared.",
          level: "ok",
        });
      } finally {
        save.disabled = false;
      }
    },
  }, "Save frame");

  return element("div", { class: "ext-overlay-demo-body" },
    element("p", { class: "ext-overlay-demo-hint" },
      "This text is given to the narrator on every beat of this story until you clear it. Put the standing situation here; facts the engine already tracks belong in the world."),
    input,
    save,
    status);
}

function revisionLabel(record) {
  if (!record || !record.frame) return "No frame installed.";
  return `Installed — revision ${record.revision}.`;
}
