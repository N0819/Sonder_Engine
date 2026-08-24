export const MODULE_RELEASE = "alpha98-ui6-57d168ae23cf";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

class TaskError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "TaskError";
    this.kind = kind;
  }
}

function progressValue(value) {
  if (value === undefined || value === null) return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0 || numeric > 1) {
    throw new TaskError("invalid-progress", "Task progress must be between zero and one.");
  }
  return numeric;
}

function publicTask(task, now) {
  const finishedAt = task.finishedAt ?? null;
  return Object.freeze({
    id: task.id,
    owner: task.owner,
    requestId: task.requestId,
    correlationId: task.correlationId,
    name: task.name,
    phase: task.phase,
    status: task.status,
    progress: task.progress,
    startedAt: task.startedAt,
    finishedAt,
    elapsedMs: Math.max(0, (finishedAt ?? now) - task.startedAt),
    summary: task.summary,
    error: task.error ? Object.freeze({ ...task.error }) : null,
    cancellable: task.status === "running" && typeof task.cancelCallback === "function",
  });
}

export function createTaskService(options = {}) {
  const limit = Math.max(1, Math.min(200, Number(options.limit || 50)));
  const clock = options.clock || (() => performance.now());
  const records = new Map();
  let sequence = 0;

  const snapshot = () => Object.freeze(
    [...records.values()].map(task => publicTask(task, clock())),
  );
  const emit = () => options.onChange?.(snapshot());
  const requireTask = (id) => {
    const task = records.get(id);
    if (!task) throw new TaskError("unknown-task", `Unknown task: ${id}`);
    return task;
  };
  const prune = () => {
    while (records.size > limit) {
      const terminal = [...records.values()].find(task => TERMINAL.has(task.status));
      if (!terminal) {
        throw new TaskError("task-capacity", "Too many active tasks are running.");
      }
      records.delete(terminal.id);
    }
  };

  const start = (input = {}) => {
    const name = String(input.name || "").trim();
    if (!name) throw new TaskError("invalid-task", "A task name is required.");
    const id = `task-${++sequence}`;
    records.set(id, {
      id,
      owner: String(input.owner || "runtime"),
      requestId: Number(input.requestId || 0),
      correlationId: String(input.correlationId || ""),
      name,
      phase: String(input.phase || "starting"),
      status: "running",
      progress: progressValue(input.progress),
      startedAt: clock(),
      finishedAt: null,
      summary: "",
      error: null,
      cancelCallback: typeof input.cancel === "function" ? input.cancel : null,
      cancelCalled: false,
    });
    prune();
    emit();
    return id;
  };

  const update = (id, patch = {}) => {
    const task = requireTask(id);
    if (task.status !== "running") return false;
    if (patch.phase !== undefined) task.phase = String(patch.phase);
    if (patch.progress !== undefined) task.progress = progressValue(patch.progress);
    emit();
    return true;
  };

  const finish = (id, status, details = {}) => {
    const task = requireTask(id);
    if (TERMINAL.has(task.status)) return false;
    task.status = status;
    task.finishedAt = clock();
    task.progress = status === "completed" ? 1 : task.progress;
    task.summary = String(details.summary || "");
    if (status === "failed") {
      task.error = {
        kind: String(details.kind || "server"),
        message: String(details.userMessage || details.message || "Task failed."),
      };
    }
    prune();
    emit();
    return true;
  };

  const cancel = async (id) => {
    const task = requireTask(id);
    if (task.status !== "running" || task.cancelCalled) return false;
    task.cancelCalled = true;
    try {
      await task.cancelCallback?.();
    } finally {
      finish(id, "cancelled");
    }
    return true;
  };

  const clear = (id) => {
    const task = requireTask(id);
    if (!TERMINAL.has(task.status)) return false;
    records.delete(id);
    emit();
    return true;
  };

  return Object.freeze({
    start,
    update,
    complete: (id, details = {}) => finish(id, "completed", details),
    fail: (id, error = {}) => finish(id, "failed", error),
    cancel,
    clear,
    snapshot,
  });
}
