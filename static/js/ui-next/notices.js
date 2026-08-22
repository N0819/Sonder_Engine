export const MODULE_RELEASE = "wp04.1";

class NoticeError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "NoticeError";
    this.kind = kind;
  }
}

function publicNotice(notice) {
  return Object.freeze({
    id: notice.id,
    owner: notice.owner,
    condition: notice.condition,
    kind: notice.kind,
    message: notice.message,
    persistent: notice.persistent,
    recoverable: notice.recoverable,
    acknowledged: notice.acknowledged,
    canRetry: typeof notice.retryCallback === "function",
  });
}

export function createNoticeService(options = {}) {
  const limit = Math.max(1, Math.min(100, Number(options.limit || 30)));
  const records = new Map();
  let sequence = 0;

  const snapshot = () => Object.freeze([...records.values()].map(publicNotice));
  const emit = () => options.onChange?.(snapshot());
  const requireNotice = (id) => {
    const notice = records.get(id);
    if (!notice) throw new NoticeError("unknown-notice", `Unknown notice: ${id}`);
    return notice;
  };
  const prune = () => {
    while (records.size > limit) {
      const acknowledgement = [...records.values()].find(
        notice => notice.kind === "acknowledgement",
      );
      records.delete((acknowledgement || records.values().next().value).id);
    }
  };

  const publish = (input = {}) => {
    const kind = input.kind === "problem" ? "problem" : "acknowledgement";
    const message = String(input.message || "").trim();
    if (!message) throw new NoticeError("invalid-notice", "A notice message is required.");
    const id = String(input.id || `notice-${++sequence}`);
    records.set(id, {
      id,
      owner: String(input.owner || "runtime"),
      condition: String(input.condition || ""),
      kind,
      message,
      persistent: kind === "problem" ? input.persistent !== false : Boolean(input.persistent),
      recoverable: kind === "problem" && Boolean(input.recoverable),
      acknowledged: false,
      retryCallback: typeof input.retry === "function" ? input.retry : null,
    });
    prune();
    emit();
    return id;
  };

  const problem = (input = {}) => publish({
    ...input,
    kind: "problem",
    recoverable: true,
    retry: input.error?.retryable === true ? input.retry : null,
  });

  const acknowledge = (id) => {
    const notice = requireNotice(id);
    if (notice.acknowledged) return false;
    notice.acknowledged = true;
    emit();
    return true;
  };

  const dismiss = (id) => {
    requireNotice(id);
    records.delete(id);
    emit();
    return true;
  };

  const clearCondition = (owner, condition) => {
    let removed = 0;
    for (const [id, notice] of records) {
      if (notice.owner === String(owner) && notice.condition === String(condition)) {
        records.delete(id);
        removed += 1;
      }
    }
    if (removed) emit();
    return removed;
  };

  const retry = async (id) => {
    const notice = requireNotice(id);
    if (!notice.retryCallback) return false;
    return notice.retryCallback();
  };

  return Object.freeze({
    publish,
    problem,
    acknowledge,
    dismiss,
    clearCondition,
    retry,
    snapshot,
  });
}
