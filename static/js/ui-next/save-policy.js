export const MODULE_RELEASE = "wp02.1";

const AUTOSAVE_ACTIONS = new Set(["field-edit", "draft-update"]);
const INVERSE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const INVERSE_ENDPOINT = /^\/api\/[A-Za-z0-9_/-]{1,300}$/;
const MAX_UNDO_LIFETIME_MS = 900000;

export class SavePolicyError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "SavePolicyError";
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

export function classifySaveAction(action) {
  return AUTOSAVE_ACTIONS.has(String(action || "")) ? "autosave" : "explicit";
}

function publicSlot(slot) {
  if (!slot) return null;
  return deepFreeze({
    owner: slot.owner,
    revision: slot.revision,
    requestId: slot.requestId,
    status: slot.status,
    draft: clone(slot.draft),
    server: slot.server === null ? null : clone(slot.server),
    error: slot.error === null ? null : { ...slot.error },
  });
}

export function createSaveCoordinator(options = {}) {
  if (typeof options.write !== "function") {
    throw new SavePolicyError("save-writer", "A save writer is required.");
  }
  const slots = new Map();
  let activeOwner = null;
  let requestSequence = 0;

  const ensureSlot = (owner) => {
    const normalizedOwner = String(owner || "");
    if (!normalizedOwner) throw new SavePolicyError("save-owner", "A save owner is required.");
    if (!slots.has(normalizedOwner)) {
      slots.set(normalizedOwner, {
        owner: normalizedOwner,
        revision: null,
        requestId: 0,
        status: "saved",
        draft: null,
        server: null,
        error: null,
        queue: Promise.resolve(),
      });
    }
    return slots.get(normalizedOwner);
  };
  const emit = (slot) => options.onChange?.(publicSlot(slot));

  const selectOwner = (owner) => {
    activeOwner = String(owner || "") || null;
    if (activeOwner) ensureSlot(activeOwner);
    return activeOwner;
  };

  const stage = (input = {}) => {
    if (classifySaveAction(input.action) !== "autosave") {
      throw new SavePolicyError(
        "explicit-action",
        "That action requires an explicit confirmation and save.",
      );
    }
    const slot = ensureSlot(input.owner);
    if (input.revision === undefined || input.revision === null) {
      throw new SavePolicyError("save-revision", "A save revision is required.");
    }
    slot.revision = input.revision;
    slot.draft = clone(input.draft);
    slot.status = "dirty";
    slot.server = null;
    slot.error = null;
    emit(slot);
    return publicSlot(slot);
  };

  const identityMatches = (slot, captured, response) => (
    activeOwner === captured.owner
    && slot.revision === captured.revision
    && slot.requestId === captured.requestId
    && response?.owner === captured.owner
    && response?.revision === captured.revision
    && response?.requestId === captured.requestId
  );

  const markStale = (slot, requestId) => {
    if (slot.requestId === requestId && slot.status === "saving") {
      slot.status = "dirty";
      emit(slot);
    }
    return Object.freeze({ accepted: false, reason: "stale" });
  };

  const save = (owner) => {
    const slot = ensureSlot(owner);
    if (!new Set(["dirty", "conflict", "recoverable-error"]).has(slot.status)) {
      throw new SavePolicyError("save-state", "There is no dirty draft to save.");
    }
    const captured = Object.freeze({
      owner: slot.owner,
      revision: slot.revision,
      requestId: ++requestSequence,
      draft: clone(slot.draft),
    });
    slot.requestId = captured.requestId;
    slot.status = "saving";
    slot.error = null;
    emit(slot);

    const run = async () => {
      try {
        const response = await options.write(captured);
        const current = ensureSlot(captured.owner);
        if (!identityMatches(current, captured, response)) {
          return markStale(current, captured.requestId);
        }
        if (response.conflict === true) {
          current.status = "conflict";
          current.server = response.server === undefined ? null : clone(response.server);
          current.error = null;
          emit(current);
          return Object.freeze({ accepted: false, reason: "conflict" });
        }
        current.status = "saved";
        current.server = null;
        current.error = null;
        emit(current);
        return Object.freeze({ accepted: true, reason: "saved" });
      } catch (error) {
        const current = ensureSlot(captured.owner);
        if (activeOwner !== captured.owner
            || current.revision !== captured.revision
            || current.requestId !== captured.requestId) {
          return markStale(current, captured.requestId);
        }
        current.status = "recoverable-error";
        current.error = {
          kind: String(error?.kind || "server"),
          message: String(error?.userMessage || error?.message || "Save failed."),
        };
        emit(current);
        return Object.freeze({ accepted: false, reason: "error" });
      }
    };

    const pending = slot.queue.then(run, run);
    slot.queue = pending.then(() => undefined, () => undefined);
    return pending;
  };

  return Object.freeze({
    selectOwner,
    stage,
    save,
    snapshot: owner => publicSlot(slots.get(String(owner || ""))),
    activeOwner: () => activeOwner,
  });
}

export function acceptUndoReceipt(receipt, context = {}) {
  if (!receipt || typeof receipt !== "object") {
    throw new SavePolicyError("undo-missing", "No server undo receipt was provided.");
  }
  const owner = String(receipt.owner || "");
  const action = String(receipt.action || "");
  const receiptId = String(receipt.receiptId || "");
  if (owner !== String(context.owner || "")) {
    throw new SavePolicyError("undo-owner", "The undo receipt belongs to another record.");
  }
  if (action !== String(context.action || "")) {
    throw new SavePolicyError("undo-action", "The undo receipt belongs to another action.");
  }
  if (!/^[A-Za-z0-9:_-]{1,128}$/.test(receiptId)) {
    throw new SavePolicyError("undo-receipt", "The undo receipt id is invalid.");
  }
  const now = Number(context.now ?? Date.now());
  const expiresAt = Number(receipt.expiresAt);
  if (!Number.isFinite(expiresAt) || expiresAt <= now) {
    throw new SavePolicyError("undo-expired", "The undo receipt has expired.");
  }
  if (expiresAt - now > MAX_UNDO_LIFETIME_MS) {
    throw new SavePolicyError("undo-expiry", "The undo receipt lasts too long.");
  }
  const method = String(receipt.inverse?.method || "").toUpperCase();
  const endpoint = String(receipt.inverse?.endpoint || "");
  if (!INVERSE_METHODS.has(method) || !INVERSE_ENDPOINT.test(endpoint)) {
    throw new SavePolicyError("undo-endpoint", "The undo endpoint is invalid.");
  }
  return deepFreeze({
    receiptId,
    action,
    owner,
    inverse: { method, endpoint },
    expiresAt,
  });
}
