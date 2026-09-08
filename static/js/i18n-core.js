"use strict";

// ---- The localization rules, once ----
//
// Two pages localize themselves: the host SPA (utils.js, over `S.uiCatalog`)
// and the login/guest pages (i18n.js, over its own `/api/ui` fetch). They
// stay separate on purpose -- running both on one page meant a second catalog
// fetch, a second permanent observer, and a race over which one localized a
// node first -- but what they DO is one thing, and it lived in two hand-kept
// copies until B25 (review 2026-09-07). Those copies drifted twice: once over
// whitespace, which ate the space in `Hinami 何をすべきか決めている`, and once
// over the skip set, so a `translate="no"` subtree kept a translated tooltip.
// A pinning test caught the second and could not catch the next one before it
// shipped. So the rules live here, in the one file both loaders load, and the
// two remaining differences are the only two that are real: WHERE the catalog
// comes from, and (in the SPA) `{var}` interpolation on top of the lookup.

// Text this layer must never touch. The UI catalog is a map of ENGINE source
// strings; story text is authored by a model or by the reader, and it only
// looks like a catalog key by accident. 134 single-word keys have real
// translations, so narrator prose containing "Close" rendered 閉じる mid-
// sentence and a story named "Cast" became 配役. `translate="no"` is the
// standard HTML opt-out and is honoured here for the same reason browsers
// honour it.
//
// Two different exclusions, and conflating them cost every placeholder.
// A whole SUBTREE is off-limits for script/style and anything opted out;
// a textarea or input excludes only its CONTENT, because that content is
// data being edited while its placeholder and title are still chrome.
// (boot() re-localizes the whole document, and boot() runs while the prompt
// editor is open -- so a system prompt sitting in a textarea was walked by
// the translator on its way to being saved.)
const I18N_SKIP_TREE = 'script,style,[data-no-i18n],[translate="no"]';
const I18N_SKIP_TEXT = I18N_SKIP_TREE + ',textarea,input';

// Chrome that lives in an attribute rather than in a text node.
const I18N_ATTRS = ["title", "aria-label", "placeholder", "alt"];
// Built from the list rather than written out again, so the selector and the
// loop that reads the attributes cannot name different sets.
const I18N_ATTR_SELECTOR = I18N_ATTRS.map(name => "[" + name + "]").join(",");

// How much literal text a template rule must pin down before it may match
// anything, so a rule recognises something about the message and not merely
// its shape. Named because it is a threshold: see the shadowing case below.
const I18N_MIN_ANCHOR_CHARS = 3;

// Compile the catalog's `${...}` templates into rules that can be matched
// back from an already-interpolated string. Two rules decide whether that is
// possible at all, and both were once missing:
//
// 1. A key made only of placeholders ("${a} ${b}") compiles to
//    /^(.+?) (.+?)$/ -- every string with a space. One such rule sat near the
//    front of the catalog and shadowed 220 of the 226 templates behind it, so
//    almost every counter and "X of Y" label rendered English despite being
//    correctly translated.
// 2. Order must be by how much LITERAL text a rule pins down, not by catalog
//    position, or a vague rule still wins over a precise one.
function i18nCompileTemplates(messages) {
  return Object.entries(messages || {})
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
    .filter(rule => rule.weight >= I18N_MIN_ANCHOR_CHARS)
    .sort((a, b) => b.weight - a.weight);
}

// Exact key first, then the compiled templates in anchor order.
function i18nTranslate(messages, rules, source) {
  source = String(source ?? "");
  const catalog = messages || {};
  if (catalog[source] !== undefined) return catalog[source];
  for (const rule of rules || []) {
    const match = source.match(rule.regex);
    if (!match) continue;
    let index = 1;
    // Translate each CAPTURE too. The captured span is whatever the caller
    // interpolated, and it is very often another engine string with its own
    // catalog entry -- `${phase} (+2 running alongside)` captures an already
    // English step label, so the status bar came out half Japanese:
    // 「Writing the scene (他に2が並行して実行中)」.
    return rule.value.replace(/\$\{[^}]+\}/g, () => {
      const captured = match[index++] || "";
      const inner = catalog[captured.trim()];
      return inner === undefined ? captured : inner;
    });
  }
  return source;
}

// Walk `root` and localize its text nodes and its chrome attributes with
// `translate`.
function i18nLocalize(root, translate) {
  if (!root) return;
  if (typeof root.querySelectorAll !== "function") {
    // A text node has no querySelectorAll. Callers pass `parentElement`
    // today, but the nodeType guards below imply other roots are allowed.
    root = root.parentElement;
    if (!root) return;
  }
  if (root.nodeType === Node.ELEMENT_NODE && root.closest(I18N_SKIP_TREE)) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node.parentElement?.closest(I18N_SKIP_TEXT)) continue;
    const trimmed = String(node.nodeValue || "").trim();
    if (!trimmed) continue;
    const translated = translate(trimmed);
    if (translated !== trimmed) {
      // Re-attach the original padding. Writing the trimmed translation back
      // over the whole node value silently deleted significant leading and
      // trailing spaces around 348 literals.
      const lead = String(node.nodeValue).match(/^\s*/)?.[0] || "";
      const tail = String(node.nodeValue).match(/\s*$/)?.[0] || "";
      node.nodeValue = lead + translated + tail;
    }
  }
  // `root` ITSELF, not just its descendants. The observer hands us each newly
  // added element as the root, and querySelectorAll never matches the node it
  // is called on -- so a dynamically created input's placeholder was never
  // translated at all.
  //
  // The SAME skip tree the text pass uses. It was applied to text nodes only,
  // so a tooltip under `translate="no"` was still translated -- a character
  // named "Cast" got a キャスト tooltip on the very element whose text the
  // guard was protecting. Attributes are chrome by default, which is why
  // textarea/input are not excluded here, but a subtree opted out is opted
  // out for both passes.
  const hosts = [...root.querySelectorAll(I18N_ATTR_SELECTOR)]
    .filter(element => !element.closest(I18N_SKIP_TREE));
  if (root.nodeType === Node.ELEMENT_NODE && root.matches(I18N_ATTR_SELECTOR)
      && !root.closest(I18N_SKIP_TREE)) {
    hosts.push(root);
  }
  for (const element of hosts) {
    for (const attr of I18N_ATTRS) {
      if (element.hasAttribute(attr)) {
        element.setAttribute(attr, translate(element.getAttribute(attr)));
      }
    }
  }
}

// Keep localizing whatever the page adds after the first pass.
//
// `attributes` as well as `childList`: several toggles set `.title` after the
// element is already in the DOM (the ambience mute, the backdrop and chime
// toggles), and a childList-only observer never sees it -- so those tooltips
// stayed English although the pack has all of them.
function i18nObserve(localize, translate) {
  const observer = new MutationObserver(records => {
    for (const record of records) {
      if (record.type === "attributes") {
        const element = record.target;
        if (element && element.nodeType === Node.ELEMENT_NODE
            && !element.closest(I18N_SKIP_TREE)) {
          const current = element.getAttribute(record.attributeName);
          const translated = translate(String(current || ""));
          if (current && translated !== current) {
            element.setAttribute(record.attributeName, translated);
          }
        }
        continue;
      }
      for (const node of record.addedNodes) {
        if (node.nodeType === Node.TEXT_NODE) {
          if (node.parentElement) localize(node.parentElement);
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          localize(node);
        }
      }
    }
  });
  observer.observe(document.body, {
    childList: true, subtree: true,
    attributes: true,
    attributeFilter: I18N_ATTRS,
  });
  return observer;
}
