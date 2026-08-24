export const MODULE_RELEASE = "alpha98-ui12-7eaf6b3481a3";

import { openNewStory } from "./new-story.js?release=alpha98-ui12-7eaf6b3481a3";

import { renderPipelineInspector } from "./pipeline-inspector.js?release=alpha98-ui12-7eaf6b3481a3";

// UI_CATALOG_START: player-facing Play workflow copy.
const COPY = Object.freeze({
  chooseStory: "Choose a story to begin",
  chooseDetail: "Open one of your recent stories, or browse the Library.",
  openLibrary: "Open Library",
  newStory: "New story",
  loading: "Opening your story…",
  loadingDetail: "Your saved story is being read from the engine.",
  unavailable: "This story could not be opened",
  offline: "Sonder is offline",
  retryOpen: "Try again",
  emptyTranscript: "This story is ready for its first turn.",
  emptyMeaning: "Leave the box empty and send to let the story continue without a new action.",
  muteAmbience: "Mute ambience",
  unmuteAmbience: "Unmute ambience",
  ambienceVolume: "Ambience volume",
  send: "Send",
  stop: "Stop",
  stopping: "Stopping…",
  retry: "Retry",
  newTurn: "New turn",
  rename: "Rename story",
  exportArchive: "Export archive",
  storyActions: "Story actions",
  switchStory: "Switch story",
  edit: "Edit",
  reroll: "Reroll",
  versions: "Versions",
  more: "More",
  editNarration: "Edit narration",
  branch: "Branch here",
  turnDetails: "Turn details",
  deleteTurn: "Delete turn",
  advanced: "Advanced technical detail",
  cancel: "Cancel",
  close: "Close",
  save: "Save",
  continue: "Continue",
  editPlayerInput: "Edit player input",
  rerollTitle: "Reroll this turn?",
  rerollWarning: "This restores world state, memories, and lorebooks to the start of this turn, including changes made since then.",
  editNarrationDetail: "This changes only the words shown for the beat. World state and memory stay as recorded.",
  deleteTitle: "Delete the latest turn?",
  deleteWarning: "The story returns to the point before this turn. This cannot be undone here.",
  currentStory: "Current story",
  storyThreads: "Story threads",
  present: "Present",
  transcript: "Story transcript",
  composerLabel: "What do you do or say?",
  saving: "Saving this turn…",
  generationStopped: "Generation stopped",
  loadingDetails: "Loading turn details…",
  detailsUnavailable: "Turn details are unavailable.",
  loadingVersions: "Loading versions…",
  oneVersion: "This turn has one version.",
  versionsUnavailable: "Versions are unavailable.",
  previousVersion: "Previous version",
  nextVersion: "Next version",
  variantCount: "${index} of ${total}",
  saveFailure: "That change could not be saved.",
  untitledStory: "Untitled story",
  earlierStep: "an earlier step",
  superseded: "Superseded — this text was written before “${label}” was re-run.",
  partlyOutdated: "Partly out of date — steps from “${label}” onward were not recomputed.",
});
// UI_CATALOG_END

let dialogSequence = 0;

function element(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function icon(documentRef, name) {
  const svg = documentRef.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ui-icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = documentRef.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/assets/icons/sonder-icons.svg?release=${MODULE_RELEASE}#icon-${name}`);
  svg.append(use);
  return svg;
}

function button(documentRef, label, className = "ui-button ui-button--quiet") {
  const node = element(documentRef, "button", className, label);
  node.type = "button";
  return node;
}

function markData(node) {
  node.setAttribute("translate", "no");
  return node;
}

function localize(services, node) {
  services?.localizer?.localize(node);
  return node;
}

function emptyState(documentRef, title, detail) {
  const state = element(documentRef, "section", "ui-empty ui-play__state");
  state.dataset.state = "empty";
  state.append(
    element(documentRef, "h2", "ui-heading ui-heading--2", title),
    element(documentRef, "p", "ui-muted", detail),
  );
  return state;
}

function createDialogHost(documentRef, title, options = {}) {
  const overlay = documentRef.querySelector("[data-shell-overlay-host]") || documentRef.body;
  const dialog = element(documentRef, "dialog", "ui-dialog ui-play-dialog");
  dialog.setAttribute("aria-labelledby", `play-dialog-${++dialogSequence}`);
  const heading = element(documentRef, "h2", "ui-heading ui-heading--2", title);
  heading.id = dialog.getAttribute("aria-labelledby");
  const body = element(documentRef, "div", "ui-play-dialog__body");
  const actions = element(documentRef, "div", "ui-play-dialog__actions");
  const cancel = button(documentRef, options.cancelLabel || COPY.cancel);
  cancel.addEventListener("click", () => dialog.close("cancel"));
  actions.append(cancel);
  dialog.append(heading, body, actions);
  overlay.append(dialog);
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  dialog.addEventListener("cancel", event => {
    event.preventDefault();
    dialog.close("cancel");
  });
  dialog.showModal();
  localize(options.services, dialog);
  return { dialog, body, actions, cancel };
}

function textDialog(documentRef, title, initialValue, options = {}) {
  const host = createDialogHost(documentRef, title, { services: options.services });
  if (options.description) {
    host.body.append(element(documentRef, "p", "ui-muted", options.description));
  }
  const field = element(documentRef, options.multiline ? "textarea" : "input", "ui-play-dialog__field");
  if (!options.multiline) field.type = "text";
  field.value = String(initialValue ?? "");
  field.setAttribute("aria-label", title);
  host.body.append(field);
  const error = element(documentRef, "p", "ui-play-dialog__error");
  error.setAttribute("role", "alert");
  host.body.append(error);
  const save = button(documentRef, options.saveLabel || COPY.save, "ui-button ui-button--primary");
  host.actions.append(save);
  localize(options.services, host.dialog);
  save.addEventListener("click", async () => {
    save.disabled = true;
    error.textContent = "";
    try {
      await options.onSave?.(field.value);
      host.dialog.close("saved");
    } catch (failure) {
      save.disabled = false;
      error.textContent = failure?.userMessage || failure?.message || COPY.saveFailure;
      localize(options.services, error);
    }
  });
  queueMicrotask(() => field.focus());
  return host.dialog;
}

function confirmDialog(documentRef, title, description, options = {}) {
  return new Promise(resolve => {
    const host = createDialogHost(documentRef, title, {
      cancelLabel: COPY.cancel,
      services: options.services,
    });
    host.body.append(element(documentRef, "p", "ui-play-dialog__copy", description));
    const confirm = button(
      documentRef,
      options.confirmLabel || COPY.continue,
      `ui-button ${options.danger ? "ui-button--danger" : "ui-button--primary"}`,
    );
    host.actions.append(confirm);
    localize(options.services, host.dialog);
    confirm.addEventListener("click", () => host.dialog.close("confirmed"));
    host.dialog.addEventListener("close", () => resolve(host.dialog.returnValue === "confirmed"), { once: true });
    queueMicrotask(() => confirm.focus());
  });
}

function downloadArchive(documentRef, archive) {
  const url = URL.createObjectURL(new Blob(
    [JSON.stringify(archive.data, null, 2)],
    { type: "application/json" },
  ));
  const link = element(documentRef, "a");
  link.href = url;
  link.download = archive.filename;
  link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function storyChoice(documentRef, services, currentId) {
  const label = element(documentRef, "label", "ui-play__story-choice");
  label.append(element(documentRef, "span", "ui-sr-only", COPY.switchStory));
  const select = element(documentRef, "select", "ui-play__story-select");
  select.setAttribute("aria-label", COPY.switchStory);
  for (const chat of services.store.getSnapshot().library.chats || []) {
    const option = element(documentRef, "option", "", chat.name || `Story ${chat.id}`);
    markData(option);
    option.value = String(chat.id);
    option.selected = Number(chat.id) === Number(currentId);
    select.append(option);
  }
  select.addEventListener("change", () => services.play.openStory(select.value));
  label.append(select);
  return label;
}

function renderNoStory(documentRef, services) {
  const state = emptyState(documentRef, COPY.chooseStory, COPY.chooseDetail);
  const actions = element(documentRef, "div", "ui-play__empty-actions");
  for (const chat of (services.store.getSnapshot().library.chats || []).slice(0, 4)) {
    const open = markData(button(documentRef, chat.name || `Story ${chat.id}`));
    open.addEventListener("click", () => services.play.openStory(chat.id));
    actions.append(open);
  }
  const create = button(documentRef, COPY.newStory, "ui-button ui-button--primary");
  create.addEventListener("click", () => openNewStory({ document: documentRef, services }));
  const library = button(documentRef, COPY.openLibrary, "ui-button ui-button--quiet");
  library.addEventListener("click", () => services.router.navigate({ destination: "library" }));
  actions.append(create, library);
  state.append(actions);
  return { element: state, teardown() {} };
}

function renderUnavailable(documentRef, services, story) {
  const title = story.status === "loading"
    ? COPY.loading
    : (story.status === "offline" ? COPY.offline : COPY.unavailable);
  const detail = story.status === "loading"
    ? COPY.loadingDetail
    : (story.error?.message || story.error?.userMessage || COPY.chooseDetail);
  const state = emptyState(documentRef, title, detail);
  state.dataset.state = story.status;
  if (story.status === "error" || story.status === "offline") {
    const retry = button(documentRef, COPY.retryOpen, "ui-button ui-button--primary");
    retry.addEventListener("click", () => services.play.refresh());
    state.append(retry);
  }
  return { element: state, teardown() {} };
}

function staleNote(documentRef, turn) {
  if (!turn.stale_from) return null;
  const label = String(turn.stale_from.label || COPY.earlierStep);
  return element(
    documentRef,
    "p",
    "ui-play__stale",
    turn.prose_stale
      ? COPY.superseded.replace("${label}", label)
      : COPY.partlyOutdated.replace("${label}", label),
  );
}

function actionMenu(documentRef, label = COPY.more) {
  const menu = element(documentRef, "details", "ui-play__menu");
  const summary = element(documentRef, "summary", "ui-button ui-button--quiet", label);
  summary.setAttribute("role", "button");
  summary.setAttribute("aria-label", label);
  const body = element(documentRef, "div", "ui-play__menu-body");
  body.setAttribute("role", "menu");
  menu.append(summary, body);
  return { menu, body };
}

function closeMenu(menu) {
  menu.removeAttribute("open");
}

function turnDetailsDialog(documentRef, services, turn) {
  const host = createDialogHost(documentRef, COPY.turnDetails, {
    cancelLabel: COPY.close,
    services,
  });
  const loading = element(documentRef, "p", "ui-muted", COPY.loadingDetails);
  host.body.append(loading);
  localize(services, host.body);
  void services.play.pipeline(turn.id).then(payload => {
    host.body.replaceChildren(renderPipelineInspector(documentRef, payload));
    localize(services, host.body);
  }).catch(error => {
    loading.textContent = error?.userMessage || error?.message || COPY.detailsUnavailable;
    localize(services, loading);
  });
}

async function versionsDialog(documentRef, services, turn, proseModule) {
  const host = createDialogHost(documentRef, COPY.versions, {
    cancelLabel: COPY.close,
    services,
  });
  host.body.append(element(documentRef, "p", "ui-muted", COPY.loadingVersions));
  localize(services, host.body);
  try {
    const payload = await services.play.variants(turn.id);
    const variants = Array.isArray(payload?.variants) ? payload.variants : [];
    if (!variants.length) {
      host.body.replaceChildren(element(documentRef, "p", "ui-muted", COPY.oneVersion));
      localize(services, host.body);
      return;
    }
    let index = Math.max(0, variants.findIndex(variant => variant.active));
    const preview = element(documentRef, "div", "ui-play__variant-preview");
    const count = element(documentRef, "span", "ui-play__variant-count");
    const previous = button(documentRef, COPY.previousVersion);
    const next = button(documentRef, COPY.nextVersion);
    const controls = element(documentRef, "div", "ui-play__variant-controls");
    controls.append(previous, count, next);
    const paint = () => {
      const variant = variants[index];
      count.textContent = services.localizer.t(COPY.variantCount, {
        index: index + 1,
        total: variants.length,
      });
      proseModule.renderProse(preview, variant.prose || "…", {
        speech: turn.speech,
        colors: services.store.getSnapshot().story.data?.dialogue_colors,
      });
    };
    const select = async offset => {
      const nextIndex = (index + offset + variants.length) % variants.length;
      await services.play.selectVariant(turn.id, variants[nextIndex].id);
      index = nextIndex;
      paint();
    };
    previous.addEventListener("click", () => void select(-1));
    next.addEventListener("click", () => void select(1));
    host.dialog.addEventListener("keydown", event => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(documentRef.activeElement?.tagName || "")) return;
      event.preventDefault();
      void select(event.key === "ArrowLeft" ? -1 : 1);
    });
    paint();
    host.body.replaceChildren(preview, controls);
    localize(services, host.body);
  } catch (error) {
    host.body.replaceChildren(element(
      documentRef, "p", "ui-play-dialog__error",
      error?.userMessage || error?.message || COPY.versionsUnavailable,
    ));
    localize(services, host.body);
  }
}

function createTurn(documentRef, services, proseModule, turn, isLatest) {
  const article = element(documentRef, "article", "ui-play__turn");
  article.dataset.turnId = String(turn.id);
  if (turn.stale) article.dataset.stale = "true";
  if (turn.player_input) {
    article.append(markData(element(documentRef, "p", "ui-play__input-echo", turn.player_input)));
  }
  const prose = markData(element(documentRef, "div", "ui-play__prose"));
  proseModule.renderProse(prose, turn.prose || "…", {
    speech: turn.speech,
    colors: services.store.getSnapshot().story.data?.dialogue_colors,
  });
  article.append(prose);
  const note = staleNote(documentRef, turn);
  if (note) article.append(note);
  const actions = element(documentRef, "div", "ui-play__turn-actions");
  const edit = button(documentRef, COPY.edit);
  edit.addEventListener("click", () => textDialog(
    documentRef,
    COPY.editPlayerInput,
    turn.player_input,
    { services, multiline: true, onSave: value => services.play.editInput(turn.id, value) },
  ));
  actions.append(edit);
  if (isLatest) {
    const reroll = button(documentRef, COPY.reroll);
    reroll.addEventListener("click", async () => {
      const confirmed = await confirmDialog(
        documentRef,
        COPY.rerollTitle,
        COPY.rerollWarning,
        { services, confirmLabel: COPY.reroll, danger: true },
      );
      if (confirmed) void services.play.reroll(turn.id);
    });
    const versions = button(documentRef, COPY.versions);
    versions.addEventListener("click", () => void versionsDialog(documentRef, services, turn, proseModule));
    actions.append(reroll, versions);
  }
  const more = actionMenu(documentRef);
  const editNarration = button(documentRef, COPY.editNarration);
  editNarration.setAttribute("role", "menuitem");
  editNarration.addEventListener("click", () => {
    closeMenu(more.menu);
    textDialog(documentRef, COPY.editNarration, turn.prose, {
      multiline: true,
      services,
      description: COPY.editNarrationDetail,
      onSave: value => services.play.editProse(turn.id, value),
    });
  });
  const branch = button(documentRef, COPY.branch);
  branch.setAttribute("role", "menuitem");
  branch.addEventListener("click", async () => {
    closeMenu(more.menu);
    const created = await services.play.branch(turn.id);
    if (created?.id) services.play.openStory(created.id);
  });
  const details = button(documentRef, COPY.turnDetails);
  details.setAttribute("role", "menuitem");
  details.addEventListener("click", () => {
    closeMenu(more.menu);
    turnDetailsDialog(documentRef, services, turn);
  });
  more.body.append(editNarration, branch, details);
  if (isLatest) {
    const remove = button(documentRef, COPY.deleteTurn, "ui-button ui-button--danger");
    remove.setAttribute("role", "menuitem");
    remove.addEventListener("click", async () => {
      closeMenu(more.menu);
      const confirmed = await confirmDialog(
        documentRef,
        COPY.deleteTitle,
        COPY.deleteWarning,
        { services, confirmLabel: COPY.deleteTurn, danger: true },
      );
      if (confirmed) await services.play.deleteTurn(turn.id);
    });
    more.body.append(remove);
  }
  actions.append(more.menu);
  article.append(actions);
  return localize(services, article);
}

function createStoryView(documentRef, services, proseModule, initialState) {
  const root = element(documentRef, "section", "ui-play");
  root.dataset.playWorkspace = "true";
  const story = initialState.story.data;
  const atmosphere = element(documentRef, "div", "ui-play__atmosphere");
  atmosphere.setAttribute("data-play-atmosphere", "true");
  atmosphere.setAttribute("aria-hidden", "true");
  const backdrop = element(documentRef, "img", "ui-play__backdrop");
  backdrop.setAttribute("data-play-backdrop", "true");
  backdrop.alt = "";
  const weather = element(documentRef, "div", "ui-play__weather");
  weather.setAttribute("data-play-weather", "true");
  atmosphere.append(backdrop, weather);
  const storyHeader = element(documentRef, "header", "ui-play__story-header");
  const identity = element(documentRef, "div", "ui-play__identity");
  const storyTitle = element(
    documentRef, "h2", "ui-heading ui-heading--2", story.chat.name || COPY.untitledStory,
  );
  if (story.chat.name) markData(storyTitle);
  identity.append(
    element(documentRef, "p", "ui-kicker", COPY.currentStory),
    storyTitle,
  );
  const storyActions = element(documentRef, "div", "ui-play__story-actions");
  const rename = button(documentRef, COPY.rename);
  rename.addEventListener("click", () => textDialog(
    documentRef,
    COPY.rename,
    story.chat.name,
    { services, onSave: value => services.play.rename(value) },
  ));
  const archive = button(documentRef, COPY.exportArchive);
  archive.addEventListener("click", async () => downloadArchive(
    documentRef, await services.play.exportArchive(),
  ));
  const storyMore = actionMenu(documentRef, COPY.storyActions);
  storyMore.menu.querySelector("summary").append(icon(documentRef, "more"));
  storyMore.body.append(storyChoice(documentRef, services, story.chat.id), rename, archive);
  storyActions.append(
    element(documentRef, "span", "ui-play__story-state", "Ready"),
    storyMore.menu,
  );
  storyHeader.append(identity, storyActions);

  const frames = story.frames || [];
  if (frames.length > 1) {
    const frameBar = element(documentRef, "nav", "ui-play__frames");
    frameBar.setAttribute("aria-label", COPY.storyThreads);
    for (const frame of frames) {
      const frameButton = button(documentRef, frame.id === null ? COPY.present : frame.label);
      if (frame.id !== null) markData(frameButton);
      if ((frame.id ?? null) === (initialState.story.frameId ?? null)) {
        frameButton.setAttribute("aria-current", "page");
      }
      frameButton.addEventListener("click", () => services.play.openStory(story.chat.id, frame.id));
      frameBar.append(frameButton);
    }
    storyHeader.append(frameBar);
  }

  const transcript = element(documentRef, "div", "ui-play__transcript");
  transcript.setAttribute("data-play-transcript", "true");
  transcript.dataset.shellScrollRegion = "play-transcript";
  transcript.setAttribute("aria-label", COPY.transcript);
  transcript.setAttribute("role", "region");
  const newTurn = button(documentRef, COPY.newTurn, "ui-button ui-button--primary ui-play__new-turn");
  newTurn.hidden = true;
  newTurn.addEventListener("click", () => {
    transcript.scrollTo({ top: transcript.scrollHeight, behavior: "smooth" });
    newTurn.hidden = true;
  });

  const composer = element(documentRef, "section", "ui-play__composer");
  composer.setAttribute("data-play-composer", "true");
  const input = element(documentRef, "textarea", "ui-play__composer-input");
  input.setAttribute("aria-label", COPY.composerLabel);
  input.placeholder = COPY.composerLabel;
  const composerHelp = element(documentRef, "p", "ui-play__composer-help", COPY.emptyMeaning);
  const progress = element(documentRef, "div", "ui-play__progress");
  progress.setAttribute("data-play-progress", "true");
  progress.setAttribute("role", "status");
  const phase = element(documentRef, "span", "ui-play__progress-phase");
  const elapsed = element(documentRef, "span", "ui-play__progress-elapsed");
  const technical = element(documentRef, "details", "ui-play__advanced");
  technical.append(
    element(documentRef, "summary", "", COPY.advanced),
    element(documentRef, "pre", "ui-play__technical"),
  );
  progress.append(phase, elapsed, technical);
  const composerActions = element(documentRef, "div", "ui-play__composer-actions");
  const send = button(documentRef, COPY.send, "ui-button ui-button--primary");
  send.setAttribute("data-play-send", "true");
  const stop = button(documentRef, COPY.stop, "ui-button ui-button--danger");
  stop.setAttribute("data-play-stop", "true");
  const retry = button(documentRef, COPY.retry, "ui-button ui-button--primary");
  retry.dataset.playRetry = "true";
  const validation = element(documentRef, "p", "ui-play__validation");
  validation.setAttribute("role", "alert");
  composerActions.append(send, stop, retry);
  const audioCluster = element(documentRef, "div", "ui-play__audio-cluster");
  audioCluster.setAttribute("aria-label", "Ambience controls");
  const muteAmbience = button(documentRef, COPY.muteAmbience, "ui-button ui-button--quiet");
  const ambienceVolume = documentRef.createElement("input");
  ambienceVolume.type = "range";
  ambienceVolume.min = "0"; ambienceVolume.max = "1"; ambienceVolume.step = "0.05";
  ambienceVolume.setAttribute("aria-label", COPY.ambienceVolume);
  audioCluster.append(muteAmbience, ambienceVolume);
  composer.append(input, composerHelp, validation, progress, composerActions, audioCluster);
  root.append(atmosphere, storyHeader, transcript, newTurn, composer);

  let lastItems = null;
  let lastPreview = null;
  let elapsedTimer = null;
  let disposed = false;

  const pinned = () => transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 96;
  const renderTranscript = state => {
    const wasPinned = lastItems === null || lastItems.length === 0 || pinned();
    const previousTop = transcript.scrollTop;
    transcript.dataset.scrollSettled = "false";
    const items = state.transcript.items || [];
    const nodes = items.map((turn, index) => createTurn(
      documentRef, services, proseModule, turn, index === items.length - 1,
    ));
    if (!nodes.length) {
      nodes.push(element(documentRef, "p", "ui-play__empty-transcript", COPY.emptyTranscript));
    }
    if (state.transcript.preview?.prose) {
      const preview = element(documentRef, "article", "ui-play__turn ui-play__turn--preview");
      preview.dataset.preview = "true";
      if (state.transcript.preview.playerInput) {
        preview.append(markData(element(
          documentRef, "p", "ui-play__input-echo", state.transcript.preview.playerInput,
        )));
      }
      const prose = markData(element(documentRef, "div", "ui-play__prose"));
      proseModule.renderProse(prose, state.transcript.preview.prose);
      preview.append(prose, element(documentRef, "p", "ui-kicker", COPY.saving));
      localize(services, preview);
      nodes.push(preview);
    }
    transcript.replaceChildren(...nodes);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (disposed) return;
      if (wasPinned) {
        transcript.scrollTo({ top: transcript.scrollHeight, behavior: "instant" });
        newTurn.hidden = true;
      } else if (lastItems !== null) {
        transcript.scrollTop = previousTop;
        newTurn.hidden = false;
      }
      transcript.dataset.scrollSettled = "true";
    }));
    lastItems = items;
    lastPreview = state.transcript.preview;
  };

  const scheduleElapsed = run => {
    clearTimeout(elapsedTimer);
    if (!run || disposed) return;
    const tick = () => {
      if (disposed) return;
      const seconds = Math.max(0, Math.floor((Date.now() - run.startedAt) / 1000));
      elapsed.textContent = `${seconds}s`;
      elapsedTimer = setTimeout(tick, 1000);
    };
    tick();
  };

  const renderComposer = state => {
    const current = state.composer;
    if (documentRef.activeElement !== input && input.value !== current.draft) {
      input.value = current.draft || "";
    }
    const running = current.status === "running";
    const stopping = current.status === "stopping";
    const failed = current.status === "recoverable-error";
    send.hidden = running || stopping || failed;
    stop.hidden = !running;
    retry.hidden = !failed || current.failure?.retryable === false;
    input.disabled = running || stopping;
    phase.textContent = current.run?.phase || (failed ? current.failure?.message || COPY.generationStopped : "");
    localize(services, phase);
    progress.hidden = !current.run && !failed;
    stop.textContent = stopping ? COPY.stopping : COPY.stop;
    stop.disabled = stopping;
    validation.textContent = current.validation || "";
    const detail = current.run?.detail || [];
    technical.querySelector("pre").textContent = detail.map(
      entry => `${entry.type}${entry.label ? ` · ${entry.label}` : ""}`,
    ).join("\n");
    scheduleElapsed(current.run);
  };

  const renderAtmosphere = state => {
    const payload = state.atmosphere?.backdrop?.payload;
    const url = payload?.ready ? payload.url : null;
    if (url) {
      if (backdrop.getAttribute("src") !== url) backdrop.setAttribute("src", url);
      backdrop.hidden = false;
    } else {
      backdrop.hidden = true;
      backdrop.removeAttribute("src");
    }
    const conditions = payload?.weather || {};
    const kind = conditions.precipitation || conditions.sky || conditions.kind || "";
    weather.dataset.weather = String(kind);
    weather.dataset.severity = String(conditions.severity || "");
    weather.hidden = !kind;
    const preferences = state.atmosphere?.preferences || {};
    muteAmbience.textContent = preferences.muted ? COPY.unmuteAmbience : COPY.muteAmbience;
    ambienceVolume.value = String(preferences.volume ?? 0.7);
    localize(services, audioCluster);
  };

  muteAmbience.addEventListener("click", () => {
    const muted = services.store.getSnapshot().atmosphere.preferences.muted;
    services.atmosphere.setMuted(!muted);
  });
  ambienceVolume.addEventListener("input", () => services.atmosphere.setVolume(ambienceVolume.value));

  input.addEventListener("input", () => services.play.updateDraft(input.value));
  input.addEventListener("keydown", event => {
    if (event.isComposing || event.key !== "Enter" || event.shiftKey) return;
    if (!(event.ctrlKey || event.metaKey)) return;
    event.preventDefault();
    void services.play.send(input.value);
  });
  send.addEventListener("click", () => void services.play.send(input.value));
  stop.addEventListener("click", () => void services.play.stop());
  retry.addEventListener("click", () => void services.play.retry());

  const selectPlayState = state => ({
    story: state.story,
    transcript: state.transcript,
    composer: state.composer,
    atmosphere: state.atmosphere,
  });
  const unsubscribe = services.store.subscribe(selectPlayState, state => {
    storyTitle.textContent = state.story.data?.chat?.name || storyTitle.textContent;
    if (state.transcript.items !== lastItems || state.transcript.preview !== lastPreview) {
      renderTranscript(state);
    }
    renderComposer(state);
    renderAtmosphere(state);
  }, { equality: (left, right) => (
    left.story === right.story
    && left.transcript === right.transcript
    && left.composer === right.composer
    && left.atmosphere === right.atmosphere
  ) });
  const initial = selectPlayState(services.store.getSnapshot());
  renderTranscript(initial);
  input.value = initial.composer.draft || "";
  renderComposer(initial);
  renderAtmosphere(initial);

  return {
    element: root,
    teardown() {
      if (disposed) return;
      disposed = true;
      clearTimeout(elapsedTimer);
      unsubscribe();
    },
  };
}

export function createPlayView(options = {}) {
  const documentRef = options.document || document;
  const state = options.state || options.services.store.getSnapshot();
  if (state.story?.status === "empty" || state.story?.status === "unrequested") {
    return renderNoStory(documentRef, options.services);
  }
  if (state.story?.status !== "ready" || !state.story.data) {
    return renderUnavailable(documentRef, options.services, state.story || {});
  }
  return createStoryView(documentRef, options.services, options.prose, state);
}
