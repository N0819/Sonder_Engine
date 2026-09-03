"use strict";

// ---- The Writers' Room panel ----
//
// One conversation with the Story Planner (and through it the Dramaturge),
// beside the story it is about, so the room's input -- the player-visible
// stream -- and the room itself are on one screen. Opened from a tab on the
// right edge of the play view. Two shapes, two looks, both borrowed from
// rules the page already has (docs/design/DESIGN_WRITERS_ROOM_PLAN.md § 6.5):
//
//   DOCKED  -- a right-hand column of #app, width-resizable from a handle on
//              its left edge, collapsing back to its tab. It sits directly
//              over the page background, so it is OPAQUE CHROME
//              (styles.css, the invariant's list names #room).
//   FLOATING -- undocked into a draggable, corner-resizable window over the
//              story column. It sits where the prose sits, so it earns the
//              prose's treatment: with a backdrop up it is the PROSE PLATE
//              (`body.has-backdrop .prose` extended to `#room.floating`,
//              weather gate included), and the opacity slider drives
//              --bd-panel for this element alone.
//
// It looks like a simple LLM chat: the thread, a compose box, and beside them
// only the standing mandates (typed grants the player can read and revoke)
// and the spoiler-safe status line (what is in motion, never what it is).
// No forms for budgets or events; those are sentences to the Planner.
//
// Reads the story-view globals it needs (S.chatId, S.currentFrameId, S.chat)
// and the shared helpers ($, el, api, t, toast). It never touches the turn
// pipeline's scripts and nothing there calls into it. Every stored
// preference is per viewer in localStorage, read and written inside
// try/catch, with defaults when the store is blocked.

// ---- Named limits ----
// The docked column's width: no narrower than a readable chat, no wider than
// a bit over half the window (the story keeps the rest).
const ROOM_MIN_WIDTH = 300;
const ROOM_MAX_WIDTH_FRACTION = 0.6;
const ROOM_DEFAULT_WIDTH = 380;
// The floating window: minimum size and the first-open geometry.
const ROOM_FLOAT_MIN_W = 320;
const ROOM_FLOAT_MIN_H = 260;
const ROOM_FLOAT_DEFAULT = { w: 440, h: 540 };
// The opacity slider drives --bd-panel on the panel alone. The floor is the
// readable floor the prose rule already assumes (~.40, backdrops.js), never
// below it: a plate the words cannot be read on is not a preference.
const ROOM_OPACITY_FLOOR = 0.4;
const ROOM_OPACITY_DEFAULT = 0.55;
// While the panel is OPEN, how often it compares the story view's identity
// (story, era, beat count) with what it last loaded. No network unless one
// changed; nothing at all while closed.
const ROOM_WATCH_MS = 1000;
// A summarised Dramaturge line shows this many characters before "more".
const ROOM_SUMMARY_CHARS = 140;
// Storage keys, per viewer.
const ROOM_STORE = {
  open: "room.open", mode: "room.mode", width: "room.width",
  geometry: "room.geometry", opacity: "room.opacity",
  dramaturge: "room.dramaturge",
};
// The placeholder's line, spelled here so the UI catalog harvests it and the
// stored English line translates on render. tests/test_room_routes.py holds
// this spelling and story/room_conversation.UNSEATED_LINE together.
const ROOM_UNSEATED_LINE = "The Story Planner is not seated yet. Your note is kept for it; nothing has been planned.";

// Class lists are composed from single words so the UI-catalog harvester,
// which reads every JS string literal, does not publish CSS classes as
// interface copy.
function roomCls(...names) { return names.join(" "); }

const ROOM = {
  open: false, mode: "docked", width: ROOM_DEFAULT_WIDTH,
  geometry: null, opacity: ROOM_OPACITY_DEFAULT, dramaturge: "shown",
  loadedKey: null, seated: false, messages: [], mandates: [], status: null,
  messageChars: 4000, page: 60, oldestId: null, busy: false, watch: null,
  expanded: new Set(),
};

function roomStoreGet(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v;
  } catch (e) { return fallback; }
}
function roomStoreSet(key, value) {
  try { localStorage.setItem(key, String(value)); } catch (e) {}
}

function roomRestorePrefs() {
  ROOM.open = roomStoreGet(ROOM_STORE.open, "0") === "1";
  ROOM.mode = roomStoreGet(ROOM_STORE.mode, "docked") === "floating" ? "floating" : "docked";
  ROOM.width = roomClampWidth(numOr(roomStoreGet(ROOM_STORE.width, ROOM_DEFAULT_WIDTH), ROOM_DEFAULT_WIDTH));
  ROOM.opacity = roomClampOpacity(numOr(roomStoreGet(ROOM_STORE.opacity, ROOM_OPACITY_DEFAULT), ROOM_OPACITY_DEFAULT));
  const mode = roomStoreGet(ROOM_STORE.dramaturge, "shown");
  ROOM.dramaturge = ["shown", "summarised", "hidden"].includes(mode) ? mode : "shown";
  try {
    const g = JSON.parse(roomStoreGet(ROOM_STORE.geometry, "null"));
    ROOM.geometry = g && Number.isFinite(g.w) ? g : null;
  } catch (e) { ROOM.geometry = null; }
}

function roomClampWidth(w) {
  const max = Math.max(ROOM_MIN_WIDTH, Math.floor(window.innerWidth * ROOM_MAX_WIDTH_FRACTION));
  return Math.min(max, Math.max(ROOM_MIN_WIDTH, Math.round(w)));
}
function roomClampOpacity(v) {
  return Math.min(1, Math.max(ROOM_OPACITY_FLOOR, Number(v)));
}
function roomClampGeometry(g) {
  const out = Object.assign({}, ROOM_FLOAT_DEFAULT, g || {});
  out.w = Math.max(ROOM_FLOAT_MIN_W, Math.min(window.innerWidth, Math.round(out.w)));
  out.h = Math.max(ROOM_FLOAT_MIN_H, Math.min(window.innerHeight, Math.round(out.h)));
  if (!Number.isFinite(out.x)) out.x = Math.max(0, window.innerWidth - out.w - 24);
  if (!Number.isFinite(out.y)) out.y = Math.max(0, Math.round((window.innerHeight - out.h) / 2));
  out.x = Math.max(0, Math.min(window.innerWidth - ROOM_FLOAT_MIN_W, Math.round(out.x)));
  out.y = Math.max(0, Math.min(window.innerHeight - 48, Math.round(out.y)));
  return out;
}

// ---- Shape: docked / floating / closed ----

function roomApplyShape() {
  const R = $("#room");
  const tab = $("#room-tab");
  if (!R || !tab) return;
  R.classList.toggle("hidden", !ROOM.open);
  tab.classList.toggle("on", ROOM.open);
  tab.setAttribute("aria-expanded", ROOM.open ? "true" : "false");
  R.classList.toggle("floating", ROOM.mode === "floating");
  R.classList.toggle("docked", ROOM.mode !== "floating");
  if (ROOM.mode === "floating") {
    const g = roomClampGeometry(ROOM.geometry);
    ROOM.geometry = g;
    R.style.width = g.w + "px";
    R.style.height = g.h + "px";
    R.style.left = g.x + "px";
    R.style.top = g.y + "px";
    R.style.setProperty("--bd-panel", String(ROOM.opacity));
  } else {
    R.style.width = roomClampWidth(ROOM.width) + "px";
    R.style.height = "";
    R.style.left = "";
    R.style.top = "";
    R.style.removeProperty("--bd-panel");
  }
  const head = R.querySelector(".room-head");
  if (head) head.classList.toggle("draggable", ROOM.mode === "floating");
  const slider = R.querySelector(".room-opacity");
  if (slider) slider.classList.toggle("hidden", ROOM.mode !== "floating");
  const modeBtn = R.querySelector(".room-mode");
  if (modeBtn) {
    modeBtn.textContent = ROOM.mode === "floating" ? "⇥" : "⧉";
    const label = ROOM.mode === "floating" ? "Dock the room to the right edge" : "Float the room over the story";
    modeBtn.title = t(label);
    modeBtn.setAttribute("aria-label", t(label));
  }
}

function roomOpen(open) {
  ROOM.open = !!open;
  roomStoreSet(ROOM_STORE.open, ROOM.open ? "1" : "0");
  roomApplyShape();
  if (ROOM.open) {
    roomStartWatch();
    roomLoad();
  } else {
    roomStopWatch();
  }
}

function roomSetMode(mode) {
  ROOM.mode = mode === "floating" ? "floating" : "docked";
  roomStoreSet(ROOM_STORE.mode, ROOM.mode);
  roomApplyShape();
}

// ---- Loading ----

function roomKey() {
  const turns = (S.chat && Array.isArray(S.chat.turns)) ? S.chat.turns.length : 0;
  return String(S.chatId ?? "") + "|" + String(S.currentFrameId ?? "") + "|" + turns;
}

function roomFrameQuery() {
  return S.currentFrameId != null ? "?frame_id=" + encodeURIComponent(S.currentFrameId) : "";
}

async function roomLoad() {
  const key = roomKey();
  ROOM.loadedKey = key;
  if (!S.chatId) {
    ROOM.messages = []; ROOM.mandates = []; ROOM.status = null; ROOM.seated = false;
    roomRender();
    return;
  }
  try {
    const out = await api("GET", "/api/chats/" + S.chatId + "/room" + roomFrameQuery());
    if (roomKey() !== key) return; // the view moved on while we waited
    ROOM.messages = out.messages || [];
    ROOM.mandates = out.mandates || [];
    ROOM.status = out.status || null;
    ROOM.seated = !!out.seated;
    ROOM.messageChars = out.message_chars || ROOM.messageChars;
    ROOM.page = out.page || ROOM.page;
    ROOM.oldestId = ROOM.messages.length ? ROOM.messages[0].id : null;
    roomRender();
  } catch (error) {
    toast(error.message || String(error), "err");
  }
}

async function roomLoadEarlier() {
  if (!S.chatId || ROOM.oldestId == null) return;
  const sep = roomFrameQuery() ? "&" : "?";
  try {
    const out = await api(
      "GET",
      "/api/chats/" + S.chatId + "/room" + roomFrameQuery() + sep + "before=" + ROOM.oldestId
    );
    const earlier = out.messages || [];
    if (!earlier.length) { ROOM.oldestId = null; roomRender(); return; }
    ROOM.messages = earlier.concat(ROOM.messages);
    ROOM.oldestId = earlier[0].id;
    roomRender(true);
  } catch (error) {
    toast(error.message || String(error), "err");
  }
}

function roomStartWatch() {
  roomStopWatch();
  ROOM.watch = setInterval(() => {
    if (!ROOM.open) return;
    if (roomKey() !== ROOM.loadedKey) roomLoad();
  }, ROOM_WATCH_MS);
}
function roomStopWatch() {
  if (ROOM.watch) clearInterval(ROOM.watch);
  ROOM.watch = null;
}

// ---- Sending ----

async function roomSend() {
  const box = $("#room-input");
  if (!box || ROOM.busy) return;
  const text = box.value.trim();
  if (!text) return;
  if (!S.chatId) { toast("Select a story first", "warn"); return; }
  if (text.length > ROOM.messageChars) {
    toast(t("That note is longer than the room reads at once ({max} characters)", { max: ROOM.messageChars }), "warn");
    return;
  }
  ROOM.busy = true;
  const send = $("#room-send");
  if (send) send.disabled = true;
  try {
    const out = await api("POST", "/api/chats/" + S.chatId + "/room/messages", {
      text, frame_id: S.currentFrameId,
    });
    box.value = "";
    ROOM.messages = ROOM.messages.concat([out.message], out.replies || []);
    ROOM.mandates = out.mandates || ROOM.mandates;
    ROOM.status = out.status || ROOM.status;
    ROOM.seated = !!out.seated;
    ROOM.loadedKey = roomKey();
    roomRender();
    if (out.error) toast(t("The room could not answer: {why}", { why: out.error }), "err");
  } catch (error) {
    toast(error.message || String(error), "err");
  } finally {
    ROOM.busy = false;
    if (send) send.disabled = false;
    box.focus();
  }
}

async function roomRevoke(uid) {
  if (!S.chatId) return;
  try {
    const out = await api("POST", "/api/chats/" + S.chatId + "/room/mandates/" + encodeURIComponent(uid) + "/revoke", {
      frame_id: S.currentFrameId,
    });
    ROOM.mandates = out.mandates || [];
    roomRender();
    toast("Mandate revoked", "ok");
  } catch (error) {
    toast(error.message || String(error), "err");
  }
}

// ---- Rendering ----

const ROOM_ROLE_LABELS = {
  player: "You", planner: "Story Planner", dramaturge: "Dramaturge", room: "Room",
};

function roomRender(keepScroll = false) {
  const R = $("#room");
  if (!R) return;
  const thread = R.querySelector(".room-thread");
  const prevTop = thread ? thread.scrollTop : 0;
  const prevHeight = thread ? thread.scrollHeight : 0;
  roomRenderStatus(R.querySelector(".room-status"));
  roomRenderMandates(R.querySelector(".room-mandates"));
  roomRenderThread(thread);
  const seatedNote = R.querySelector(".room-seated");
  if (seatedNote) {
    seatedNote.classList.toggle("hidden", ROOM.seated || !S.chatId);
  }
  if (thread) {
    if (keepScroll) thread.scrollTop = thread.scrollHeight - prevHeight + prevTop;
    else thread.scrollTop = thread.scrollHeight;
  }
}

function roomRenderStatus(box) {
  if (!box) return;
  box.innerHTML = "";
  const st = ROOM.status;
  if (!S.chatId) {
    box.append(el("div", { class: "dim" }, "Select a story to open its room."));
    return;
  }
  box.append(el("div", { class: "room-status-line" },
    st && st.line ? st.line : "Nothing is in motion."));
  if (st && st.in_motion && st.in_motion.length) {
    box.append(el("div", { class: "room-motion" },
      st.in_motion.map(item => el("span", {
        class: "badge", title: item.kind || "",
      }, item.label + (item.state ? " · " + item.state : "")))));
  }
  if (st && st.questions && st.questions.length) {
    box.append(el("div", { class: "room-questions" },
      el("b", {}, "The room asks"),
      el("ul", {}, st.questions.map(qn => el("li", {}, qn.text)))));
  }
}

function roomRenderMandates(box) {
  if (!box) return;
  box.innerHTML = "";
  if (!S.chatId) return;
  const active = ROOM.mandates.filter(m => m.status === "active");
  const spent = ROOM.mandates.filter(m => m.status !== "active");
  box.append(el("div", { class: "room-section-title" }, "Standing mandates"));
  if (!active.length) {
    box.append(el("div", { class: "dim small" },
      "No standing mandates. Grant one by telling the Story Planner what it may do."));
  }
  for (const m of active) {
    box.append(el("div", { class: "room-mandate" },
      el("div", { class: "room-mandate-text" }, m.text),
      el("div", { class: roomCls("row", "small", "dim") },
        m.scope ? el("span", {}, m.scope) : null,
        m.expires_turn != null
          ? el("span", {}, t("until beat {n}", { n: m.expires_turn })) : null,
        el("span", { class: "spacer" }),
        el("button", {
          class: roomCls("ghost", "small"), title: "Withdraw this grant",
          onclick: () => roomRevoke(m.uid),
        }, "Revoke"))));
  }
  if (spent.length) {
    box.append(el("details", { class: "room-spent" },
      el("summary", { class: "dim small" },
        t("{n} revoked or expired", { n: spent.length })),
      spent.map(m => el("div", { class: roomCls("room-mandate", "spent", "small") },
        el("s", {}, m.text),
        el("span", { class: "dim" }, " · " + (m.status === "revoked" ? t("Revoked") : t("Expired")))))));
  }
}

function roomRenderThread(box) {
  if (!box) return;
  box.innerHTML = "";
  if (!S.chatId) return;
  if (ROOM.oldestId != null && ROOM.messages.length >= ROOM.page) {
    box.append(el("button", { class: roomCls("ghost", "small", "room-earlier"), onclick: roomLoadEarlier },
      "Earlier"));
  }
  if (!ROOM.messages.length) {
    box.append(el("div", { class: roomCls("room-msg", "room", "dim") },
      ROOM.seated
        ? "Tell the Story Planner what you want prepared, what it may do, and how much it may surprise you."
        : ROOM_UNSEATED_LINE));
  }
  for (const m of ROOM.messages) {
    if (m.role === "dramaturge" && ROOM.dramaturge === "hidden") continue;
    const node = el("div", { class: "room-msg " + m.role },
      el("div", { class: "room-who" }, ROOM_ROLE_LABELS[m.role] || m.role));
    let text = m.text;
    if (m.role === "dramaturge" && ROOM.dramaturge === "summarised"
        && text.length > ROOM_SUMMARY_CHARS && !ROOM.expanded.has(m.id)) {
      node.append(el("div", { class: "room-text" }, text.slice(0, ROOM_SUMMARY_CHARS) + "…"),
        el("button", { class: roomCls("ghost", "small"), onclick: () => { ROOM.expanded.add(m.id); roomRender(true); } },
          "More"));
    } else {
      node.append(el("div", { class: "room-text" }, text));
    }
    box.append(node);
  }
}

// ---- Building the panel ----

function roomBuild() {
  const R = $("#room");
  if (!R || R.dataset.built) return;
  R.dataset.built = "1";

  const head = el("div", { class: "room-head" },
    el("b", { class: "room-title" }, "Writers' Room"),
    el("span", { class: "spacer" }),
    el("label", { class: roomCls("room-opacity", "hidden"), title: "How much of the story shows through the floating room" },
      el("input", {
        type: "range", min: String(ROOM_OPACITY_FLOOR), max: "1", step: "0.01",
        value: String(ROOM.opacity), "aria-label": "Room opacity",
        oninput: event => {
          ROOM.opacity = roomClampOpacity(event.target.value);
          roomStoreSet(ROOM_STORE.opacity, ROOM.opacity);
          R.style.setProperty("--bd-panel", String(ROOM.opacity));
        },
      })),
    el("select", {
      class: roomCls("room-dramaturge", "small"), title: "How the Dramaturge's contributions are shown",
      "aria-label": "Dramaturge visibility",
      onchange: event => {
        ROOM.dramaturge = event.target.value;
        roomStoreSet(ROOM_STORE.dramaturge, ROOM.dramaturge);
        roomRender();
      },
    },
      el("option", { value: "shown" }, "Dramaturge shown"),
      el("option", { value: "summarised" }, "Dramaturge summarised"),
      el("option", { value: "hidden" }, "Dramaturge hidden")),
    el("button", {
      class: roomCls("icon-button", "ghost", "room-mode"), title: "Float the room over the story",
      "aria-label": "Float the room over the story",
      onclick: () => roomSetMode(ROOM.mode === "floating" ? "docked" : "floating"),
    }, "⧉"),
    el("button", {
      class: roomCls("icon-button", "ghost"), title: "Close the room", "aria-label": "Close the room",
      onclick: () => roomOpen(false),
    }, "✕"));

  head.querySelector(".room-dramaturge").value = ROOM.dramaturge;

  const seated = el("div", { class: roomCls("room-seated", "dim", "small", "hidden") },
    "Nobody is seated in the room yet. Notes are kept for the Story Planner.");
  const status = el("div", { class: "room-status" });
  const mandates = el("div", { class: "room-mandates" });
  const thread = el("div", { class: "room-thread", "aria-live": "polite" });
  const input = el("textarea", {
    id: "room-input", rows: "3",
    placeholder: "Tell the Story Planner what to prepare, or what it may do… (Ctrl+Enter to send)",
    "aria-label": "Message to the Writers' Room",
    onkeydown: event => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        roomSend();
      }
    },
  });
  const compose = el("div", { class: "room-compose" }, input,
    el("button", { id: "room-send", class: "primary", onclick: roomSend }, "Send ➤"));

  const edge = el("div", { class: "room-edge", title: "Drag to resize", "aria-hidden": "true" });
  const corner = el("div", { class: "room-corner", title: "Drag to resize", "aria-hidden": "true" });

  R.append(edge, head, seated, status, mandates, thread, compose, corner);
  roomWireDrag(R, head, edge, corner);
}

// Pointer-driven drag and resize. One pattern for all three gestures: capture
// the pointer, remember where it started, apply the delta, persist on release.
function roomWireDrag(R, head, edge, corner) {
  function track(target, onMove, onEnd) {
    target.addEventListener("pointerdown", down => {
      if (down.button !== 0) return;
      if (down.target.closest(roomCls("button", "input", "select", "textarea", "label").split(" ").join(","))) return;
      down.preventDefault();
      const start = { x: down.clientX, y: down.clientY,
        g: Object.assign({}, roomClampGeometry(ROOM.geometry)), w: ROOM.width };
      target.setPointerCapture(down.pointerId);
      const move = ev => onMove(ev.clientX - start.x, ev.clientY - start.y, start);
      const up = () => {
        target.removeEventListener("pointermove", move);
        target.removeEventListener("pointerup", up);
        target.removeEventListener("pointercancel", up);
        onEnd();
      };
      target.addEventListener("pointermove", move);
      target.addEventListener("pointerup", up);
      target.addEventListener("pointercancel", up);
    });
  }
  // Floating: drag by the header.
  track(head, (dx, dy, start) => {
    if (ROOM.mode !== "floating") return;
    ROOM.geometry = roomClampGeometry({ ...start.g, x: start.g.x + dx, y: start.g.y + dy });
    roomApplyShape();
  }, () => roomStoreSet(ROOM_STORE.geometry, JSON.stringify(ROOM.geometry)));
  // Floating: resize by the corner.
  track(corner, (dx, dy, start) => {
    if (ROOM.mode !== "floating") return;
    ROOM.geometry = roomClampGeometry({ ...start.g, w: start.g.w + dx, h: start.g.h + dy });
    roomApplyShape();
  }, () => roomStoreSet(ROOM_STORE.geometry, JSON.stringify(ROOM.geometry)));
  // Docked: resize width from the left edge (the handle moves left to widen).
  track(edge, (dx, _dy, start) => {
    if (ROOM.mode === "floating") return;
    ROOM.width = roomClampWidth(start.w - dx);
    roomApplyShape();
  }, () => roomStoreSet(ROOM_STORE.width, ROOM.width));
}

// ---- Boot ----

(function roomBoot() {
  const tab = $("#room-tab");
  if (!tab || !$("#room")) return;
  roomRestorePrefs();
  roomBuild();
  tab.onclick = () => roomOpen(!ROOM.open);
  window.addEventListener("resize", () => { if (ROOM.open) roomApplyShape(); });
  roomApplyShape();
  if (ROOM.open) roomOpen(true);
})();
