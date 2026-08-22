export const MODULE_RELEASE = "wp06.1";

const ALLOWED_ELEMENTS = new Set([
  "a",
  "blockquote",
  "br",
  "code",
  "em",
  "h1",
  "h2",
  "h3",
  "h4",
  "hr",
  "li",
  "ol",
  "p",
  "pre",
  "strong",
  "ul",
]);
const DROP_WITH_CONTENT = new Set([
  "script",
  "style",
  "svg",
  "math",
  "iframe",
  "object",
  "embed",
  "template",
]);
const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

export function setText(target, value) {
  if (!target || !("textContent" in target)) {
    throw new TypeError("A text-capable target is required.");
  }
  target.textContent = String(value ?? "");
  return target;
}

function safeHref(value, baseUrl) {
  const href = String(value || "").trim();
  if (!href || /[\u0000-\u001f\u007f]/.test(href)) return "";
  if (href.startsWith("#") || href.startsWith("/")
      || href.startsWith("./") || href.startsWith("../")) return href;
  try {
    const parsed = new URL(href, baseUrl);
    return SAFE_PROTOCOLS.has(parsed.protocol) ? href : "";
  } catch {
    return "";
  }
}

function copySafeNode(source, destinationDocument, baseUrl) {
  if (source.nodeType === Node.TEXT_NODE) {
    return destinationDocument.createTextNode(source.nodeValue || "");
  }
  if (source.nodeType !== Node.ELEMENT_NODE) return null;
  const tag = source.localName.toLowerCase();
  if (DROP_WITH_CONTENT.has(tag) || !ALLOWED_ELEMENTS.has(tag)) return null;
  const clean = destinationDocument.createElement(tag);
  if (tag === "a") {
    const href = safeHref(source.getAttribute("href"), baseUrl);
    if (href) clean.setAttribute("href", href);
    const title = String(source.getAttribute("title") || "").slice(0, 300);
    if (title) clean.setAttribute("title", title);
    if (source.getAttribute("target") === "_blank") {
      clean.setAttribute("target", "_blank");
      if (href) clean.setAttribute("rel", "noopener noreferrer");
    }
  }
  for (const child of source.childNodes) {
    const copied = copySafeNode(child, destinationDocument, baseUrl);
    if (copied) clean.append(copied);
  }
  return clean;
}

export function safeRichText(markup, options = {}) {
  const destinationDocument = options.document || document;
  const parser = new DOMParser();
  const parsed = parser.parseFromString(String(markup ?? ""), "text/html");
  const fragment = destinationDocument.createDocumentFragment();
  const baseUrl = options.baseUrl || destinationDocument.baseURI || location.origin;
  for (const child of parsed.body.childNodes) {
    const copied = copySafeNode(child, destinationDocument, baseUrl);
    if (copied) fragment.append(copied);
  }
  return fragment;
}

export function appendSafeRichText(target, markup, options = {}) {
  const fragment = safeRichText(markup, {
    ...options,
    document: options.document || target?.ownerDocument,
  });
  target.replaceChildren(fragment);
  return target;
}
