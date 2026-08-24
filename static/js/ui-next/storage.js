export const MODULE_RELEASE = "alpha98-ui5-98f796584158";

import { assertSafeToPersist } from "./credentials.js?release=alpha98-ui5-98f796584158";

export const LOCAL_STATE_VERSION = 2;
export const LOCAL_STATE_NAMESPACE = "sonder.ui-next";

const RECORDS = new Set(["appearance", "navigation", "panes"]);
const IDENTITY = /^[A-Za-z0-9:_-]{1,128}$/;

export class LocalStateError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "LocalStateError";
    this.kind = kind;
  }
}

function clone(value) {
  return globalThis.structuredClone
    ? globalThis.structuredClone(value)
    : JSON.parse(JSON.stringify(value));
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function plainRecord(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function validRecord(value) {
  if (!plainRecord(value)) return false;
  try {
    assertSafeToPersist(value);
    return JSON.stringify(value).length <= 20000;
  } catch {
    return false;
  }
}

function validateDrafts(value) {
  const clean = {};
  let invalid = false;
  if (!plainRecord(value)) return { clean, invalid: true };
  for (const [recordType, owners] of Object.entries(value)) {
    if (!IDENTITY.test(recordType) || !plainRecord(owners)) {
      invalid = true;
      continue;
    }
    const cleanOwners = {};
    for (const [ownerId, draft] of Object.entries(owners)) {
      try {
        if (!IDENTITY.test(ownerId) || typeof draft !== "string"
            || draft.length > 200000) {
          invalid = true;
          continue;
        }
        assertSafeToPersist(draft);
        cleanOwners[ownerId] = draft;
      } catch {
        invalid = true;
      }
    }
    if (Object.keys(cleanOwners).length) clean[recordType] = cleanOwners;
  }
  return { clean, invalid };
}

function emptyEnvelope() {
  return {
    version: LOCAL_STATE_VERSION,
    appearance: {},
    navigation: {},
    panes: {},
    drafts: {},
  };
}

function migrateV1(value) {
  const drafts = {};
  for (const [key, draft] of Object.entries(value.drafts || {})) {
    const separator = key.indexOf(":");
    if (separator < 1 || typeof draft !== "string") continue;
    const recordType = key.slice(0, separator);
    const ownerId = key.slice(separator + 1);
    if (!IDENTITY.test(recordType) || !IDENTITY.test(ownerId)) continue;
    drafts[recordType] ||= {};
    drafts[recordType][ownerId] = draft;
  }
  return {
    version: LOCAL_STATE_VERSION,
    appearance: value.theme ? { theme: String(value.theme) } : {},
    navigation: value.lastRoute ? { route: String(value.lastRoute) } : {},
    panes: value.sidePane ? { side: String(value.sidePane) } : {},
    drafts,
  };
}

export function createLocalState(options = {}) {
  const storage = options.storage || globalThis.localStorage;
  const namespace = String(options.namespace || LOCAL_STATE_NAMESPACE);
  let envelope = emptyEnvelope();

  const report = (kind, message) => {
    const error = new LocalStateError(kind, message);
    options.onError?.(error);
    return error;
  };
  const persist = () => {
    try {
      storage.setItem(namespace, JSON.stringify(envelope));
      return true;
    } catch {
      report("storage-write", "Browser-local state could not be saved.");
      return false;
    }
  };

  try {
    const raw = storage.getItem(namespace);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed?.version === 1) {
        envelope = migrateV1(parsed);
        persist();
      } else if (parsed?.version === LOCAL_STATE_VERSION) {
        const next = emptyEnvelope();
        for (const record of RECORDS) {
          if (validRecord(parsed[record])) next[record] = clone(parsed[record]);
          else if (parsed[record] !== undefined) {
            report("invalid-member", `Invalid browser-local member: ${record}`);
          }
        }
        const drafts = validateDrafts(parsed.drafts || {});
        next.drafts = drafts.clean;
        if (drafts.invalid) report("invalid-member", "Invalid browser-local member: drafts");
        envelope = next;
      } else {
        report("unknown-version", "Browser-local state used an unknown version.");
      }
    }
  } catch {
    report("storage-read", "Browser-local state could not be read.");
  }

  const snapshot = () => deepFreeze(clone(envelope));
  const setRecord = (record, value) => {
    if (!RECORDS.has(record)) {
      throw new LocalStateError("unknown-record", `Unknown browser-local record: ${record}`);
    }
    assertSafeToPersist(value);
    if (!validRecord(value)) {
      throw new LocalStateError("invalid-member", `Invalid browser-local member: ${record}`);
    }
    envelope = { ...envelope, [record]: clone(value) };
    return persist();
  };
  const validateDraftIdentity = (recordType, ownerId) => {
    if (!IDENTITY.test(recordType) || !IDENTITY.test(ownerId)) {
      throw new LocalStateError("invalid-draft-owner", "Draft ownership is invalid.");
    }
  };
  const setDraft = (recordType, ownerId, value) => {
    validateDraftIdentity(recordType, ownerId);
    const draft = String(value ?? "");
    if (draft.length > 200000) {
      throw new LocalStateError("draft-too-large", "The local draft is too large.");
    }
    assertSafeToPersist(draft);
    const drafts = clone(envelope.drafts);
    drafts[recordType] ||= {};
    drafts[recordType][ownerId] = draft;
    envelope = { ...envelope, drafts };
    return persist();
  };
  const getDraft = (recordType, ownerId) => {
    validateDraftIdentity(recordType, ownerId);
    return envelope.drafts[recordType]?.[ownerId] ?? null;
  };
  const clearDraft = (recordType, ownerId) => {
    validateDraftIdentity(recordType, ownerId);
    if (!Object.hasOwn(envelope.drafts[recordType] || {}, ownerId)) return false;
    const drafts = clone(envelope.drafts);
    delete drafts[recordType][ownerId];
    if (!Object.keys(drafts[recordType]).length) delete drafts[recordType];
    envelope = { ...envelope, drafts };
    return persist();
  };

  return Object.freeze({ snapshot, setRecord, setDraft, getDraft, clearDraft });
}
