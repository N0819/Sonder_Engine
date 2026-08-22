export const MODULE_RELEASE = "wp07.1";

const SKIP_TREE = 'script,style,[data-no-i18n],[translate="no"]';
const SKIP_TEXT = `${SKIP_TREE},textarea,input,[contenteditable]`;
const LOCALIZED_ATTRIBUTES = Object.freeze([
  "title",
  "aria-label",
  "placeholder",
  "alt",
]);
const ATTRIBUTE_SELECTOR = LOCALIZED_ATTRIBUTES.map(name => `[${name}]`).join(",");
const LANGUAGE_ID = /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/;
const PLACEHOLDER = /\$\{([A-Za-z_$][\w$]*)\}|\{([A-Za-z_$][\w$]*)\}/g;

export class LocalizationError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "LocalizationError";
    this.kind = kind;
  }
}

function placeholderNames(value) {
  const names = [];
  for (const match of String(value).matchAll(PLACEHOLDER)) {
    names.push(match[1] || match[2]);
  }
  return names.sort();
}

function samePlaceholders(source, target) {
  return JSON.stringify(placeholderNames(source)) === JSON.stringify(placeholderNames(target));
}

function validateProjection(projection) {
  const language = String(projection?.language || "").toLowerCase();
  const direction = String(projection?.direction || "").toLowerCase();
  const messages = projection?.messages;
  if (!LANGUAGE_ID.test(language)) {
    throw new LocalizationError("invalid-language", "The UI language id is invalid.");
  }
  if (!new Set(["ltr", "rtl"]).has(direction)) {
    throw new LocalizationError("invalid-direction", "The UI direction is invalid.");
  }
  if (!messages || typeof messages !== "object" || Array.isArray(messages)) {
    throw new LocalizationError("invalid-messages", "The UI catalog is invalid.");
  }
  const cleanMessages = {};
  const entries = Object.entries(messages);
  if (entries.length > 10000) {
    throw new LocalizationError("catalog-too-large", "The UI catalog is too large.");
  }
  for (const [source, target] of entries) {
    if (!source || typeof target !== "string" || source.length > 5000 || target.length > 10000) {
      throw new LocalizationError("invalid-message", "A UI catalog message is invalid.");
    }
    if (!samePlaceholders(source, target)) {
      throw new LocalizationError(
        "placeholder-mismatch",
        `A translated UI message changed its placeholders: ${source.slice(0, 80)}`,
      );
    }
    cleanMessages[source] = target;
  }
  return { language, direction, messages: Object.freeze(cleanMessages) };
}

function compileTemplates(messages) {
  return Object.freeze(Object.entries(messages)
    .filter(([source]) => source.includes("${"))
    .map(([source, target]) => {
      const literals = source.split(/\$\{[^}]+\}/g);
      const literalWeight = literals.join("").trim().length;
      const escaped = literals.map(part => (
        part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      ));
      return Object.freeze({
        matcher: new RegExp(`^${escaped.join("(.+?)")}$`),
        target,
        literalWeight,
      });
    })
    .filter(rule => rule.literalWeight >= 3)
    .sort((left, right) => right.literalWeight - left.literalWeight));
}

function replaceVariables(value, vars) {
  let output = String(value);
  for (const [name, replacement] of Object.entries(vars || {})) {
    output = output
      .split(`\${${name}}`).join(String(replacement))
      .split(`{${name}}`).join(String(replacement));
  }
  return output;
}

export function projectionFromBootstrap(bootstrap) {
  return {
    language: bootstrap?.ui_language,
    direction: bootstrap?.ui_direction,
    messages: bootstrap?.ui_messages,
  };
}

export function createLocalizer(projection) {
  const { language, direction, messages } = validateProjection(projection);
  const templates = compileTemplates(messages);

  const t = (source, vars = {}) => {
    const normalizedSource = String(source ?? "");
    let translated = messages[normalizedSource];
    if (translated === undefined) {
      for (const rule of templates) {
        const match = normalizedSource.match(rule.matcher);
        if (!match) continue;
        let index = 1;
        translated = rule.target.replace(/\$\{[^}]+\}/g, () => {
          const captured = match[index++] || "";
          return messages[captured.trim()] ?? captured;
        });
        break;
      }
    }
    return replaceVariables(translated ?? normalizedSource, vars);
  };

  const localize = (root) => {
    if (!root) return root;
    const documentRef = root.nodeType === Node.DOCUMENT_NODE ? root : root.ownerDocument;
    const scope = root.nodeType === Node.DOCUMENT_NODE ? root.body : root;
    if (!documentRef || !scope) return root;
    documentRef.documentElement.lang = language;
    documentRef.documentElement.dir = direction;
    if (scope.nodeType === Node.ELEMENT_NODE && scope.closest(SKIP_TREE)) return root;

    const walker = documentRef.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    for (const node of textNodes) {
      if (node.parentElement?.closest(SKIP_TEXT)) continue;
      const original = String(node.nodeValue || "");
      const source = original.trim();
      if (!source) continue;
      const translated = t(source);
      if (translated === source) continue;
      const leading = original.match(/^\s*/)?.[0] || "";
      const trailing = original.match(/\s*$/)?.[0] || "";
      node.nodeValue = `${leading}${translated}${trailing}`;
    }

    const hosts = [...scope.querySelectorAll(ATTRIBUTE_SELECTOR)]
      .filter(element => !element.closest(SKIP_TREE));
    if (scope.nodeType === Node.ELEMENT_NODE
        && scope.matches(ATTRIBUTE_SELECTOR)
        && !scope.closest(SKIP_TREE)) {
      hosts.push(scope);
    }
    for (const element of hosts) {
      for (const attribute of LOCALIZED_ATTRIBUTES) {
        if (element.hasAttribute(attribute)) {
          element.setAttribute(attribute, t(element.getAttribute(attribute)));
        }
      }
    }
    return root;
  };

  return Object.freeze({ language, direction, t, localize });
}
