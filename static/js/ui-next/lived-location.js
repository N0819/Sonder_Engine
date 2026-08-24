export const MODULE_RELEASE = "alpha98-ui8-eb87a8415bda";

// UI_CATALOG_START: Shared lived-location authoring copy.
const LIVED_LOCATION_COPY = Object.freeze([
  "Choose from the story",
  "Resident",
  "Travels with an institution",
  "Visitor",
  "Arrives with a generated journey",
  "Use authored history only",
  "No generated past",
  "Prepare a lived location",
  "Optional · institutions, recent life, and routed character history",
  "Build the place as somewhere already lived in",
  "Location brief",
  "A hospital built into a cliff",
  "Describe the place, its work, pressures, and public life.",
  "Recent history",
  "Start at the present",
  "Past week",
  "Past month",
  "The active tail is capped at 96 hours.",
  "Character",
  "Optional history guidance",
  "Sonder may publish public resident cards for the place. Private pasts are handed only to the character they belong to.",
  "A current Story is required.",
]);
// UI_CATALOG_END

const HISTORY_MODES = Object.freeze([
  ["auto", "Choose from the story"],
  ["resident", "Resident"],
  ["moving_institution", "Travels with an institution"],
  ["visitor", "Visitor"],
  ["generated_journey", "Arrives with a generated journey"],
  ["authored_only", "Use authored history only"],
  ["none", "No generated past"],
]);

function element(documentRef, tag, className = "", text = "") {
  const value = documentRef.createElement(tag);
  if (className) value.className = className;
  if (text) value.textContent = text;
  return value;
}

function cleanHistory(row = {}) {
  return {
    key: String(row.key || ""),
    mode: HISTORY_MODES.some(([mode]) => mode === row.mode) ? row.mode : "auto",
    brief: String(row.brief || ""),
  };
}

export function normalizeHistoryCharacters(characters = []) {
  return characters.map(cleanHistory).filter(row => row.key);
}

export function normalizeLivedLocation(value = {}) {
  const horizon = Math.max(0, Math.min(720, Number(value.horizonHours) || 0));
  return {
    enabled: Boolean(value.enabled),
    brief: String(value.brief || ""),
    horizonHours: [0, 168, 720].includes(horizon) ? horizon : 0,
    characterHistories: normalizeHistoryCharacters(value.characterHistories),
  };
}

export function buildLivedLocationRequest(value = {}, options = {}) {
  const normalized = normalizeLivedLocation(value);
  if (!normalized.enabled) return null;
  const resolveId = options.resolveCharacterId || (() => null);
  const histories = normalized.characterHistories.flatMap(row => {
    const charId = Number(resolveId(row.key));
    if (!Number.isSafeInteger(charId) || charId < 1) return [];
    return [{
      char_id: charId,
      mode: row.mode,
      brief: row.brief.trim(),
    }];
  });
  const horizon = normalized.horizonHours;
  return {
    enabled: true,
    brief: normalized.brief.trim(),
    horizon_hours: horizon,
    active_tail_hours: Math.min(96, horizon),
    generate_history: horizon > 0,
    ...(histories.length ? { character_histories: histories } : {}),
  };
}

export function buildQuickStartLivedLocation(value = {}) {
  const request = buildLivedLocationRequest(value, { resolveCharacterId: () => 1 });
  if (!request) return null;
  const history = request.character_histories?.[0];
  delete request.character_histories;
  if (history) request.character_history = { mode: history.mode, brief: history.brief };
  return request;
}

export function mountLivedLocationFields(options = {}) {
  const documentRef = options.document || document;
  const target = options.target;
  const characters = Array.isArray(options.characters) ? options.characters : [];
  const value = normalizeLivedLocation(options.value);
  const changed = next => options.onChange?.(normalizeLivedLocation(next));
  const root = element(documentRef, "details", "ui-lived-location");
  root.open = Boolean(value.enabled);
  const summary = element(documentRef, "summary", "ui-lived-location__summary");
  summary.append(
    element(documentRef, "strong", "", options.title || "Prepare a lived location"),
    element(documentRef, "small", "", "Optional · institutions, recent life, and routed character history"),
  );
  const content = element(documentRef, "div", "ui-lived-location__content");
  const enabledLabel = element(documentRef, "label", "ui-lived-location__toggle");
  const enabled = documentRef.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = value.enabled;
  enabled.setAttribute("aria-label", "Prepare a lived location");
  enabledLabel.append(enabled, documentRef.createTextNode(" Build the place as somewhere already lived in"));
  const briefLabel = element(documentRef, "label", "ui-field");
  briefLabel.append(element(documentRef, "span", "ui-field__label", "Location brief"));
  const brief = element(documentRef, "textarea", "ui-textarea");
  brief.value = value.brief;
  brief.placeholder = "A hospital built into a cliff";
  briefLabel.append(brief, element(documentRef, "small", "ui-muted", "Describe the place, its work, pressures, and public life."));
  const horizonLabel = element(documentRef, "label", "ui-field");
  horizonLabel.append(element(documentRef, "span", "ui-field__label", "Recent history"));
  const horizon = element(documentRef, "select", "ui-select");
  [[0, "Start at the present"], [168, "Past week"], [720, "Past month"]].forEach(([hours, label]) => {
    const option = element(documentRef, "option", "", label);
    option.value = String(hours);
    option.selected = hours === value.horizonHours;
    horizon.append(option);
  });
  horizonLabel.append(horizon, element(documentRef, "small", "ui-muted", "The active tail is capped at 96 hours."));
  const routes = element(documentRef, "div", "ui-lived-location__routes");
  const current = new Map(value.characterHistories.map(row => [row.key, row]));
  characters.forEach(character => {
    const key = String(character.key);
    const row = current.get(key) || { key, mode: "auto", brief: "" };
    const group = element(documentRef, "fieldset", "ui-lived-location__route");
    const legend = element(documentRef, "legend", "", character.name || "Character");
    legend.setAttribute("translate", "no");
    const mode = element(documentRef, "select", "ui-select");
    mode.setAttribute("aria-label", `History route for ${character.name || "Character"}`);
    HISTORY_MODES.forEach(([raw, label]) => {
      const option = element(documentRef, "option", "", label);
      option.value = raw;
      option.selected = raw === row.mode;
      mode.append(option);
    });
    const guidance = element(documentRef, "input", "ui-input");
    guidance.type = "text";
    guidance.value = row.brief;
    guidance.placeholder = "Optional history guidance";
    guidance.setAttribute("aria-label", `History guidance for ${character.name || "Character"}`);
    const sync = () => {
      current.set(key, { key, mode: mode.value, brief: guidance.value });
      changed({ ...value, enabled: enabled.checked, brief: brief.value, horizonHours: Number(horizon.value), characterHistories: [...current.values()] });
    };
    mode.addEventListener("change", sync);
    guidance.addEventListener("input", sync);
    group.append(legend, mode, guidance);
    routes.append(group);
  });
  const boundary = element(documentRef, "p", "ui-lived-location__boundary", "Sonder may publish public resident cards for the place. Private pasts are handed only to the character they belong to.");
  const sync = () => changed({ ...value, enabled: enabled.checked, brief: brief.value, horizonHours: Number(horizon.value), characterHistories: [...current.values()] });
  enabled.addEventListener("change", sync);
  brief.addEventListener("input", sync);
  horizon.addEventListener("change", sync);
  content.append(enabledLabel, briefLabel, horizonLabel, routes, boundary);
  root.append(summary, content);
  target?.append(root);
  return { element: root, value: () => normalizeLivedLocation({ enabled: enabled.checked, brief: brief.value, horizonHours: Number(horizon.value), characterHistories: [...current.values()] }) };
}

export async function generateLivedLocation(options = {}) {
  const request = buildLivedLocationRequest(options.value, { resolveCharacterId: options.resolveCharacterId });
  if (!request) return null;
  const api = options.apiClient;
  const chatId = Number(options.chatId);
  if (!api || !Number.isSafeInteger(chatId) || chatId < 1) throw new Error("A current Story is required.");
  let owningLorebookId = options.owningLorebookId ? Number(options.owningLorebookId) : null;
  if (options.lorebookId) {
    const attached = await api.post(`/api/chats/${chatId}/lorebooks`, { lorebook_id: Number(options.lorebookId) }, options.requestOptions || {});
    owningLorebookId = Number(attached.data?.lorebook_id || attached.data?.id || owningLorebookId) || null;
  }
  const sourceLorebookId = Number(options.sourceLorebookId || options.lorebookId) || null;
  const body = { ...request, ...(sourceLorebookId ? { lorebook_id: sourceLorebookId } : {}), ...(owningLorebookId ? { owning_lorebook_id: owningLorebookId } : {}) };
  const result = await api.post(`/api/chats/${chatId}/charters/generate`, body, options.requestOptions || {});
  return result.data;
}
