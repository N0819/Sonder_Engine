"use strict";

// Standalone localization for the login and guest pages, which intentionally
// do not load the host SPA.
//
// NOT loaded by index.html: that page gets the same behaviour from
// utils.js + app.js, and running both meant a second catalog fetch, a second
// permanent observer, and a race over which one localized a node first.
// Keep the two implementations' RULES identical -- they diverged once over
// whitespace and produced `Hinami何をすべきか決めている` with the space eaten.
(async function loadStandaloneUILanguage() {
  let state;
  try {
    const response = await fetch("/api/ui", { cache: "no-store" });
    if (!response.ok) return;
    state = await response.json();
  } catch (_error) {
    return;
  }
  const messages = state.messages || {};
  document.documentElement.lang = state.language || "en";
  document.documentElement.dir = state.direction || "ltr";

  // Same two rules as utils.js: a key of pure placeholders matches every
  // string of that shape, and order must follow how much literal text a rule
  // anchors rather than catalog position.
  const templates = Object.entries(messages)
    .filter(([key]) => key.includes("${"))
    .map(([key, value]) => {
      const literals = key.split(/\$\{[^}]+\}/g);
      const parts = literals
        .map(part => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      return {
        regex: new RegExp(`^${parts.join("(.+?)")}$`),
        value,
        weight: literals.join("").trim().length,
      };
    })
    .filter(rule => rule.weight >= 3)
    .sort((a, b) => b.weight - a.weight);

  function translate(source) {
    source = String(source || "");
    if (messages[source] !== undefined) return messages[source];
    for (const rule of templates) {
      const match = source.match(rule.regex);
      if (!match) continue;
      let index = 1;
      // Each capture is translated too; see the note in utils.js.
      return rule.value.replace(/\$\{[^}]+\}/g, () => {
        const captured = match[index++] || "";
        const inner = messages[captured.trim()];
        return inner === undefined ? captured : inner;
      });
    }
    return source;
  }

  const SKIP_TREE = 'script,style,[data-no-i18n],[translate="no"]';
  const SKIP_TEXT = SKIP_TREE + ',textarea,input';

  function apply(root) {
    if (root.nodeType === Node.ELEMENT_NODE && root.closest(SKIP_TREE)) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      if (node.parentElement?.closest(SKIP_TEXT)) continue;
      const source = String(node.nodeValue || "").trim();
      if (!source) continue;
      const translated = translate(source);
      if (translated !== source) {
        // Re-attach the original padding. Writing the trimmed translation
        // back over the whole node value silently deleted significant
        // leading/trailing spaces around 348 literals.
        const lead = String(node.nodeValue).match(/^\s*/)?.[0] || "";
        const tail = String(node.nodeValue).match(/\s*$/)?.[0] || "";
        node.nodeValue = lead + translated + tail;
      }
    }
    const hosts = [...root.querySelectorAll("[title],[aria-label],[placeholder],[alt]")];
    if (root.nodeType === Node.ELEMENT_NODE
        && root.matches("[title],[aria-label],[placeholder],[alt]")) {
      hosts.push(root);
    }
    for (const element of hosts) {
      for (const attr of ["title", "aria-label", "placeholder", "alt"]) {
        if (element.hasAttribute(attr)) {
          element.setAttribute(attr, translate(element.getAttribute(attr)));
        }
      }
    }
  }

  apply(document.body);
  new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (node.nodeType === Node.ELEMENT_NODE) apply(node);
        else if (node.nodeType === Node.TEXT_NODE && node.parentElement) {
          apply(node.parentElement);
        }
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
})();
