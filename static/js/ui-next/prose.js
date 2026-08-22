export const MODULE_RELEASE = "wp07.1";

const EMPHASIS_TAGS = Object.freeze({
  i: "em",
  em: "em",
  b: "strong",
  strong: "strong",
});
const EMPHASIS_PAIR = /<(i|em|b|strong)>([\s\S]*?)<\/\1>/gi;
const TYPOGRAPHY = Object.freeze({
  "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
  "‘": "'", "’": "'", "“": '"', "”": '"',
});

function decodeAllowedEntities(value) {
  return String(value ?? "")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");
}

function foldTypography(value) {
  return String(value ?? "").replace(/[‐-—‘’“”]/g, character => (
    TYPOGRAPHY[character] || character
  ));
}

export function emphasisRuns(value) {
  const source = decodeAllowedEntities(value);
  const runs = [];
  let plain = "";
  let cursor = 0;
  let match;
  EMPHASIS_PAIR.lastIndex = 0;
  while ((match = EMPHASIS_PAIR.exec(source))) {
    plain += source.slice(cursor, match.index);
    const start = plain.length;
    plain += match[2];
    runs.push(Object.freeze({
      start,
      end: plain.length,
      tag: EMPHASIS_TAGS[match[1].toLowerCase()],
    }));
    cursor = match.index + match[0].length;
  }
  plain += source.slice(cursor);
  return Object.freeze({ text: plain, runs: Object.freeze(runs) });
}

function speechLine(entry) {
  if (typeof entry === "string") return { speaker: "", text: entry };
  if (!entry || typeof entry !== "object") return { speaker: "", text: "" };
  return {
    speaker: String(entry.speaker ?? entry.who ?? entry.name ?? ""),
    text: String(entry.exact_quote ?? entry.text ?? entry.line ?? entry.dialogue ?? ""),
  };
}

export function speechSpans(prose, speech = []) {
  const haystack = foldTypography(prose);
  const regions = quotedRegions(haystack);
  const claimed = new Map();
  const loose = [];
  for (const raw of Array.isArray(speech) ? speech : []) {
    const line = speechLine(raw);
    const needle = foldTypography(quoteBody(line.text));
    if (needle.length < 2) continue;
    let from = 0;
    while (from <= haystack.length - needle.length) {
      const start = haystack.indexOf(needle, from);
      if (start < 0) break;
      const end = start + needle.length;
      const region = regions.findIndex(item => item.start <= start && end <= item.end);
      if (region >= 0) {
        const held = claimed.get(region);
        if (held === undefined) claimed.set(region, line.speaker);
        else if (held !== line.speaker) claimed.set(region, null);
        break;
      }
      if (!loose.some(span => start < span.end && end > span.start)) {
        loose.push({ start, end, speaker: line.speaker });
        break;
      }
      from = start + 1;
    }
  }
  const spans = loose.slice();
  for (const [index, speaker] of claimed) {
    if (!speaker) continue;
    spans.push({ ...regions[index], speaker });
  }
  return spans.sort((left, right) => left.start - right.start)
    .filter((span, index, all) => index === 0 || span.start >= all[index - 1].end);
}

function quoteBody(quote) {
  return String(quote || "").trim()
    .replace(/^["'“”‘’]+/, "")
    .replace(/["'“”‘’]+$/, "")
    .trim()
    .replace(/[.,!?…;:]+$/, "")
    .trim();
}

function quotedRegions(haystack) {
  const regions = [];
  let open = -1;
  for (let index = 0; index < haystack.length; index += 1) {
    if (haystack[index] !== '"') continue;
    if (open < 0) open = index;
    else { regions.push({ start: open, end: index + 1 }); open = -1; }
  }
  return regions; // An unclosed final quote is dropped rather than guessed at.
}

function speakerColor(colors, speaker) {
  if (!speaker || !colors || typeof colors !== "object") return "";
  return String(colors[speaker] || colors[String(speaker).toLowerCase()] || "");
}

function appendSegment(documentRef, host, text, emphasis, speaker, colors) {
  let node = documentRef.createTextNode(text);
  if (emphasis) {
    const mark = documentRef.createElement(emphasis);
    mark.append(node);
    node = mark;
  }
  if (speaker) {
    const said = documentRef.createElement("span");
    said.className = "ui-play__said";
    said.title = speaker;
    const color = speakerColor(colors, speaker);
    if (color) said.style.color = color;
    said.append(node);
    node = said;
  }
  host.append(node);
}

function mergeAdjacentSpeakerSpans(host) {
  for (const said of [...host.querySelectorAll(".ui-play__said")]) {
    let next = said.nextSibling;
    while (
      next?.nodeType === 1
      && next.classList.contains("ui-play__said")
      && next.title === said.title
      && next.getAttribute("style") === said.getAttribute("style")
    ) {
      const following = next.nextSibling;
      while (next.firstChild) said.append(next.firstChild);
      next.remove();
      next = following;
    }
  }
}

export function renderProse(host, value, options = {}) {
  if (!host?.ownerDocument) throw new TypeError("A prose host is required.");
  const documentRef = host.ownerDocument;
  const emphasis = emphasisRuns(value);
  const speakers = speechSpans(emphasis.text, options.speech);
  const boundaries = new Set([0, emphasis.text.length]);
  for (const run of emphasis.runs) {
    boundaries.add(run.start);
    boundaries.add(run.end);
  }
  for (const span of speakers) {
    boundaries.add(span.start);
    boundaries.add(span.end);
  }
  const points = [...boundaries].sort((left, right) => left - right);
  const fragment = documentRef.createDocumentFragment();
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    if (end <= start) continue;
    const run = emphasis.runs.find(item => start >= item.start && end <= item.end);
    const said = speakers.find(item => start >= item.start && end <= item.end);
    appendSegment(
      documentRef,
      fragment,
      emphasis.text.slice(start, end),
      run?.tag || "",
      said?.speaker || "",
      options.colors,
    );
  }
  mergeAdjacentSpeakerSpans(fragment);
  host.replaceChildren(fragment);
  host.setAttribute("translate", "no");
  return host;
}
