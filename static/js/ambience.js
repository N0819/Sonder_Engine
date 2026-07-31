"use strict";
// ---- Room ambience ----
// The sound half of the reading view: a looping audio bed for the room the
// player is standing in, chosen by ambience.py from the room's spatial
// description alone. This file is only ever responsible for playing the right
// bed at the right moment, at a volume that stays under the prose.
//
// Its controls sit beside the composer rather than in the top toolbar, because
// they are things a reader reaches for MID-SCENE -- muting a bed that has
// started to grate, or rerolling one that landed wrong -- not settings they
// configure once and leave.
//
// Five properties this deliberately preserves:
//
// 1. Nothing here blocks reading. A miss is a library search and a download,
//    so the transcript renders first and the sound arrives whenever it
//    arrives -- or never, which is a valid outcome, not an error state.
// 2. Audio never starts itself. Browsers block autoplay before a gesture, and
//    they are right to. The toggle IS the gesture; if playback is refused
//    anyway, the next click anywhere resumes it.
// 3. MUTE IS GLOBAL AND STICKY. It lives in localStorage, not in a setting on
//    the server and not in per-chat state: someone who muted this because
//    they are on a call wants it muted in the next room, the next story and
//    after a reload. It is also instant and needs no network -- which is the
//    whole point of having it separate from the on/off switch.
// 4. One MIX per token, once. A room is rarely one sound -- a courtyard in the
//    rain is stone-and-city under rain-on-flagstones -- so the engine sends a
//    set of layers, each with its own level, and they start together and fade
//    together. Consecutive turns in one room share a token and must not
//    re-fetch, re-fade, or restart a loop (audible, where a repainted backdrop
//    is not). A room change, a shift from day to night, weather, damage or a
//    reroll all move the token and so arrive here as an ordinary crossfade.
// 5. Browsing is not choosing. The picker auditions a library's own preview
//    URL directly; nothing is downloaded into the cache until it is pinned.

const AMB = {
  enabled: false,        // mirrors the ambience_enabled setting
  configured: false,     // a source (library folder or Freesound key) is set
  source: "local",
  // The mix. `playing` is index -> {audio, gain} for the bed currently
  // sounding; `retiring` is the previous mix, fading out beneath it. A room is
  // rarely one sound, so this is a set of loops rather than one, and each
  // carries its own level (weather two rooms in is quiet over an undiminished
  // room tone).
  playing: new Map(),
  retiring: [],
  layers: [],            // the payload's description of that mix, for the UI
  token: null,           // signature#rev currently playing
  wanted: null,          // the token the visible turn wants
  signature: null,       // the server-side cache key behind that token
  room: null,            // the room id on screen, for the reassign picker
  playingRoom: null,     // the room the SOUNDING bed belongs to, which is not
                         // the same question while a bed is still arriving
  roomName: null,
  pinned: false,
  // The room was judged to have no continuous sound of its own. A RESOLVED
  // state, not a missing one: nothing is playing and nothing should be
  // fetched, which is a different thing from a bed that has not arrived yet.
  silent: false,
  reason: "",            // why, in the model's words, for the panel
  track: null,           // manifest of what is playing, for the credit line
  turnSeq: 0,
  turnId: null,
  byTurn: new Map(),
  inflight: new Map(),
  failed: new Set(),
  chatId: null,
  timer: null,
  dwellTimer: null,      // the slower one: see ambienceOnVisibleTurn
  blocked: false,        // playback refused pending a user gesture
  muted: false,
  volume: 0.35,
  primed: null,          // one element touched by the unlock gesture
};

// Long enough that one room becomes another rather than cutting, short enough
// that walking through a door does not leave you in two places for a bar.
const AMB_FADE_MS = 1400;
// The overlap at the loop point. Long enough to hide the seam and the encoder's
// padding, short enough that the bed is not audibly doubled while it happens.
const AMB_LOOP_FADE_MS = 900;
// Below this, a clip is too short to overlap with itself without sounding like
// a canon, so it goes back to the browser's own looping.
const AMB_LOOP_MIN_S = 4;
const AMB_POLL_MS = 2500, AMB_POLL_LIMIT = 30;
// Playing a bed that already exists is instant and free; SEARCHING for one is
// neither -- a model call, a library search and a download. So the two run on
// different clocks: cached sound follows the scroll as soon as it settles, and
// nothing is commissioned until the reader has actually stopped to read.
const AMB_SETTLE_MS = 260, AMB_DWELL_MS = 2000;

function ambienceStored(key, fallback) {
  const raw = localStorage.getItem("ambience." + key);
  if (raw === null) return fallback;
  const num = parseFloat(raw);
  return Number.isFinite(num) ? num : fallback;
}

// One looping element per layer. Not appended to the DOM: an <audio> element
// needs no document presence to play, and adding one invites a stylesheet or a
// screen reader to find controls the reader never asked for.
function ambienceElement(url) {
  const audio = new Audio(url);
  // NOT `loop = true`: the browser restarts at the file boundary, and an MP3
  // carries encoder padding at both ends, so a bed audibly stops for a moment
  // once a minute -- exactly the kind of hole a reader notices. `armSeamlessLoop`
  // overlaps the clip with itself instead, and only falls back to this flag for
  // a clip too short to overlap.
  audio.loop = false;
  audio.preload = "auto";
  audio.volume = 0;
  audio.muted = AMB.muted;
  return audio;
}

// Both elements of one layer: the one sounding, and the one waiting to take
// over at the loop point.
function entryAudios(entry) {
  return [entry.audio, entry.spare].filter(Boolean);
}

// Kept for the gesture that unlocks autoplay: a click has to touch an audio
// element synchronously, before any await, or some engines refuse the later
// play() as un-gestured.
function ambiencePlayers() {
  if (!AMB.primed) AMB.primed = ambienceElement("");
  return [AMB.primed];
}

function applyAmbienceMute() {
  // `muted` rather than volume 0: it is instant, it survives a crossfade
  // mid-flight, and it keeps each loop's playhead where it was, so unmuting
  // returns to the room rather than restarting it.
  for (const entry of AMB.playing.values()) {
    for (const audio of entryAudios(entry)) audio.muted = AMB.muted;
  }
  for (const audio of AMB.retiring) audio.muted = AMB.muted;
  if (AMB.primed) AMB.primed.muted = AMB.muted;
}

function setAmbienceVolume(value) {
  AMB.volume = Math.min(1, Math.max(0, Number(value) || 0));
  localStorage.setItem("ambience.volume", String(AMB.volume));
  // Every sounding layer follows the slider live, each keeping its own share
  // of it. The retiring mix is left alone: it is mid-fade, and re-targeting it
  // would make the fade jump.
  for (const [index, entry] of AMB.playing) {
    // A layer mid-handover is being driven frame by frame from ambienceLevel()
    // already; writing one of its two elements here would step on that.
    if (entry.crossing) continue;
    if (!entry.audio.paused) entry.audio.volume = ambienceLevel(index);
  }
  const slider = $("#amb-vol");
  if (slider && parseFloat(slider.value) !== AMB.volume) slider.value = AMB.volume;
}

// What one layer is actually set to: the reader's own volume, times that
// layer's share of the mix.
function ambienceLevel(index) {
  const entry = AMB.playing.get(index);
  const gain = entry ? entry.gain : 1;
  return Math.min(1, Math.max(0, AMB.volume * (gain == null ? 1 : gain)));
}

// The host's live override for one layer, if they are dragging its slider in
// the panel. Applied on top of the engine's own gain rather than replacing it,
// so "quieter" still means quieter than whatever the room decided.
function setLayerGain(index, gain) {
  const entry = AMB.playing.get(index);
  if (!entry) return;
  entry.gain = Math.min(1, Math.max(0, Number(gain) || 0));
  // Mid-handover the pair is being driven from ambienceLevel() every frame,
  // which already reads the gain just set.
  if (!entry.crossing && !entry.audio.paused) {
    entry.audio.volume = ambienceLevel(index);
  }
  const layer = AMB.layers.find(l => l.index === index);
  if (layer) layer.gain = entry.gain;
}

function toggleAmbienceMute() {
  AMB.muted = !AMB.muted;
  localStorage.setItem("ambience.muted", AMB.muted ? "1" : "0");
  applyAmbienceMute();
  updateAmbienceBtn();
}

// Crossfades a whole MIX at once: every incoming layer up to its own target,
// every outgoing one down to nothing, on one clock. Web Audio would give a
// smoother curve, but it also needs an AudioContext that must itself be
// unlocked by a gesture, and this is a background bed under prose -- the extra
// machinery buys nothing a reader could hear.
function ambienceFadeMix(incoming, outgoing) {
  const start = performance.now();
  const from = incoming.map(entry => entry.audio.volume);
  const fromOut = outgoing.map(audio => audio.volume);
  const step = now => {
    const t = Math.min(1, (now - start) / AMB_FADE_MS);
    incoming.forEach((entry, i) => {
      entry.audio.volume = Math.min(1, Math.max(0,
        from[i] + (entry.target - from[i]) * t));
    });
    outgoing.forEach((audio, i) => {
      audio.volume = Math.min(1, Math.max(0, fromOut[i] * (1 - t)));
    });
    if (t < 1) return requestAnimationFrame(step);
    for (const audio of outgoing) { audio.pause(); audio.removeAttribute("src"); }
    AMB.retiring = AMB.retiring.filter(a => !outgoing.includes(a));
  };
  requestAnimationFrame(step);
}

// ---- seamless looping ----
// A room tone that stops dead for a moment every time the file ends is worse
// than no room tone: the silence is an EVENT, and the reader looks up. So each
// layer keeps a second element on the same file and hands over to it before the
// first one runs out, overlapping the two across the seam.

function armSeamlessLoop(entry) {
  const lead = entry.audio;
  const decide = () => {
    if (entry.retired || entry.spare) return;
    if (!Number.isFinite(lead.duration) || lead.duration < AMB_LOOP_MIN_S) {
      lead.loop = true;                  // too short to overlap; let the browser do it
      return;
    }
    entry.spare = ambienceElement(lead.src);
    entry.spare.load();
    for (const audio of entryAudios(entry)) {
      audio.addEventListener("timeupdate", () => {
        if (entry.retired || entry.crossing || audio !== entry.audio) return;
        if (!Number.isFinite(audio.duration)) return;
        if (audio.duration - audio.currentTime > AMB_LOOP_FADE_MS / 1000) return;
        crossLoop(entry);
      });
      // Whatever the overlap missed -- a stall, a tab asleep through the
      // handover -- must not leave the layer silent for the rest of the room.
      audio.addEventListener("ended", () => {
        if (entry.retired || audio !== entry.audio) return;
        audio.currentTime = 0;
        audio.volume = ambienceLevel(entry.index);
        const again = audio.play();
        if (again && again.catch) again.catch(() => { });
      });
    }
  };
  if (Number.isFinite(lead.duration)) decide();
  else lead.addEventListener("loadedmetadata", decide, { once: true });
}

function crossLoop(entry) {
  const lead = entry.audio, next = entry.spare;
  if (!next) return;
  entry.crossing = true;
  try { next.currentTime = 0; } catch (e) { /* not seekable yet */ }
  next.volume = 0;
  next.muted = AMB.muted;
  const started = next.play();
  if (started && started.catch) started.catch(() => { });
  const begin = performance.now();
  const step = now => {
    if (entry.retired) return;
    const t = Math.min(1, (now - begin) / AMB_LOOP_FADE_MS);
    // Read live, so dragging the level slider mid-handover still works.
    const target = ambienceLevel(entry.index);
    // Equal power, not linear: two copies of the same bed at half volume each
    // are quieter than one at full, and a dip in the middle of the seam is the
    // very hole this exists to remove.
    lead.volume = Math.max(0, Math.min(1, target * Math.cos(t * Math.PI / 2)));
    next.volume = Math.max(0, Math.min(1, target * Math.sin(t * Math.PI / 2)));
    if (t < 1) return requestAnimationFrame(step);
    lead.pause();
    try { lead.currentTime = 0; } catch (e) { /* not seekable */ }
    // The pair swaps roles rather than being rebuilt: no new fetch, no decode,
    // and the next seam is already armed.
    entry.audio = next;
    entry.spare = lead;
    entry.crossing = false;
  };
  requestAnimationFrame(step);
}

// Takes a set of layers out of service and returns every element they own, so
// the mix crossfade can fade them out. Marking them retired first is what stops
// a loop handover from writing volumes underneath that fade.
function retireEntries(entries) {
  const audios = [];
  for (const entry of entries) {
    entry.retired = true;
    audios.push(...entryAudios(entry));
  }
  return audios;
}

function stopAmbience() {
  AMB.token = null;
  AMB.track = null;
  for (const entry of AMB.playing.values()) {
    entry.retired = true;                // stops any handover mid-flight
    for (const audio of entryAudios(entry)) {
      audio.pause();
      audio.removeAttribute("src");
    }
  }
  for (const audio of AMB.retiring) { audio.pause(); audio.removeAttribute("src"); }
  AMB.playing = new Map();
  AMB.retiring = [];
  AMB.layers = [];
}

// Crossfades to a new mix. Every layer is loaded far enough to play BEFORE the
// fade starts, so a slow file cannot produce a gap where the old room has
// already faded out and the new one has not begun -- and so the layers of one
// room start together rather than trickling in.
function playAmbience(layers, token) {
  if (!token || AMB.token === token) return;
  layers = layers || [];
  if (!layers.length) {
    // A silent room is a mix of nothing, and arrives as an ordinary crossfade:
    // the previous room's bed fades out under the prose rather than cutting.
    AMB.token = token;
    AMB.track = null;
    AMB.layers = [];
    const leaving = retireEntries([...AMB.playing.values()]);
    AMB.playing = new Map();
    AMB.retiring = AMB.retiring.concat(leaving);
    ambienceFadeMix([], leaving);
    return;
  }
  AMB.token = token;
  AMB.layers = layers.map(layer => ({ ...layer }));

  const incoming = layers.map(layer => ({
    index: layer.index,
    gain: layer.gain == null ? 1 : layer.gain,
    audio: ambienceElement(layer.url),
  }));
  let remaining = incoming.length;
  const begin = () => {
    if (AMB.token !== token) {            // the reader moved on while loading
      for (const entry of incoming) entry.audio.pause();
      return;
    }
    const outgoing = retireEntries([...AMB.playing.values()]);
    AMB.retiring = AMB.retiring.concat(outgoing);
    AMB.playing = new Map(incoming.map(entry => [entry.index, entry]));
    const started = incoming.map(entry => {
      entry.target = ambienceLevel(entry.index);
      return entry.audio.play();
    });
    // Armed only once the mix is actually running: preparing the second element
    // is a second fetch, and it must not delay the first sound of a room.
    for (const entry of incoming) armSeamlessLoop(entry);
    Promise.all(started.map(p => (p && p.catch) ? p : Promise.resolve()))
      .then(() => { AMB.blocked = false; updateAmbienceBtn(); })
      .catch(() => {});
    // If the FIRST layer is refused, the browser is holding all of them back:
    // remember it and retry on the next gesture rather than reporting an error
    // the reader cannot act on.
    const first = started[0];
    if (first && first.catch) {
      first.catch(() => {
        AMB.blocked = true;
        AMB.token = null;
        updateAmbienceBtn();
        armAmbienceUnlock();
      });
    }
    ambienceFadeMix(incoming, outgoing);
  };
  for (const entry of incoming) {
    const ready = () => { if (--remaining <= 0) begin(); };
    entry.audio.addEventListener("canplay", ready, { once: true });
    // A layer that will not load must not hold the whole mix silent.
    entry.audio.addEventListener("error", ready, { once: true });
    entry.audio.load();
  }
}

// One listener, added only when playback was actually refused, removed the
// moment it fires -- a permanent document-wide handler for a feature that is
// usually already playing would be the wrong trade.
let _ambienceUnlockArmed = false;
function armAmbienceUnlock() {
  if (_ambienceUnlockArmed) return;
  _ambienceUnlockArmed = true;
  const resume = () => {
    _ambienceUnlockArmed = false;
    // An explicit gesture from someone who wants sound: no dwell to wait for.
    if (AMB.enabled && AMB.turnId != null) {
      ambienceForTurn(AMB.turnId, { commission: true });
    }
  };
  document.addEventListener("pointerdown", resume, { once: true });
}

function ambienceWorking(on) {
  const button = $("#b-ambience");
  if (button) button.classList.toggle("working", !!on);
}

// Polls until the SOUND changes, not merely until the server says "ready": a
// reroll keeps the same signature and its old manifest is still on disk, so
// "ready" is already true the instant the request is accepted.
async function awaitAmbience(turnId, signature, first, previousToken) {
  let state = first;
  for (let i = 0; i < AMB_POLL_LIMIT; i++) {
    const settled = state.status !== "pending"
      && (!previousToken || state.token !== previousToken);
    if (settled) break;
    await new Promise(resolve => setTimeout(resolve, AMB_POLL_MS));
    state = await api("GET", `/api/turns/${turnId}/ambience`);
    if (state.signature !== signature) break;
    if (state.status === "error") break;
  }
  if (state.status === "error") throw new Error(state.error || "search failed");
  if (!state.ready) throw new Error("still searching");
  return state;
}

function resolveAmbience(turnId, signature, opts = {}) {
  const key = signature + (opts.reroll ? ":reroll:" + (opts.layer ?? "all") : "");
  if (AMB.inflight.has(key)) return AMB.inflight.get(key);
  ambienceWorking(true);
  const previousToken = opts.reroll ? AMB.token : null;
  const job = api("POST", `/api/turns/${turnId}/ambience`,
    opts.reroll ? { reroll: true, layer: opts.layer ?? null } : {})
    .then(res => awaitAmbience(turnId, signature, res, previousToken))
    .then(res => {
      AMB.byTurn.set(turnId, res);
      // Every other turn in the same room is ready now too -- a room spans
      // several turns and each of them would otherwise re-POST for a bed that
      // is already on disk.
      for (const [id, state] of AMB.byTurn) {
        if (state && state.signature === res.signature && state.token !== res.token) {
          AMB.byTurn.set(id, { ...state, ready: true, url: res.url,
                               token: res.token, layers: res.layers });
        }
      }
      return res;
    })
    .catch(error => {
      // Give up on this bed for the session rather than retrying on every
      // scroll -- but never on a reroll, which is the reader explicitly asking
      // for another go.
      if (!opts.reroll) AMB.failed.add(signature);
      toast("Ambience: " + (error?.message || "could not find a sound"), "err");
      return null;
    })
    .finally(() => {
      AMB.inflight.delete(key);
      if (!AMB.inflight.size) ambienceWorking(false);
    });
  AMB.inflight.set(key, job);
  return job;
}

async function ambienceForTurn(turnId, opts = {}) {
  if (turnId == null) return;
  const seq = ++AMB.turnSeq;
  AMB.turnId = turnId;
  let state = AMB.byTurn.get(turnId);
  if (!state) {
    try {
      state = await api("GET", `/api/turns/${turnId}/ambience`);
    } catch (e) {
      return;                        // a transcript that scrolls is worth more
    }
    AMB.byTurn.set(turnId, state);
  }
  if (seq !== AMB.turnSeq) return;
  AMB.enabled = !!state.enabled;
  AMB.configured = !!state.configured;
  AMB.source = state.source || AMB.source;
  AMB.room = state.room_id || null;
  AMB.roomName = state.room || null;
  AMB.pinned = !!state.pinned;
  AMB.silent = !!state.silent;
  AMB.reason = state.reason || "";

  AMB.signature = state.signature || null;
  // AMB.track describes what is AUDIBLE, so it is only ever set beside a
  // playAmbience call. Mirroring the server's answer for the turn instead
  // would credit the incoming bed while the previous one is still playing --
  // and the credit line is how an Attribution licence gets honoured.
  updateAmbienceBtn();

  // Switched off means SILENT, which is the opposite of backdrops: a picture
  // already paid for costs nothing to keep showing, whereas sound switched off
  // has to actually stop.
  if (!AMB.enabled) { stopAmbience(); updateAmbienceBtn(); return; }
  if (!state.signature) { AMB.wanted = null; stopAmbience(); return; }
  AMB.wanted = state.token || state.signature;
  // `ready` covers a silent room too -- the answer for it has been resolved and
  // cached, and asking again would only buy the same verdict.
  if (state.ready) {
    AMB.track = state.silent ? null : (state.layers[0] || null);
    AMB.playingRoom = state.room_id || null;
    playAmbience(state.layers || [], state.token);
    updateAmbienceBtn();
    return;
  }
  // Nothing cached for this room. The bed already sounding carries on rather
  // than cutting out -- but only while it belongs to THIS ROOM. Consecutive
  // beats in one room differ by the hour, the weather, some damage, and holding
  // the sound through those is the room continuing to sound like itself.
  // Holding it through a doorway is not: it plays the waystation's fire under a
  // beat spent out in the blizzard. A room whose sound has not arrived is
  // better represented by quiet.
  if ((state.room_id || null) !== AMB.playingRoom) {
    AMB.playingRoom = null;
    stopAmbience();
    updateAmbienceBtn();
  }
  // Searching for one costs a model call and a download, so it waits until the
  // reader has settled here (or this turn was just generated): scrolling
  // through a long story passes dozens of rooms nobody stopped in, and each
  // would otherwise commission its own bed.
  if (!opts.commission) return;
  if (!AMB.configured || AMB.failed.has(state.signature)) return;

  const found = await resolveAmbience(turnId, state.signature);
  if (!found) return;
  AMB.silent = !!found.silent;
  AMB.reason = found.reason || "";
  // Gated on the BED still being wanted, not on the turn the request started
  // from: consecutive turns in one room share a token, so drifting a few beats
  // while a download finishes still wants this exact sound.
  if (found.token === AMB.wanted || found.signature === AMB.signature) {
    AMB.track = found.silent ? null : (found.layers[0] || null);
    AMB.playingRoom = state.room_id || null;
    AMB.wanted = found.token;
    playAmbience(found.layers || [], found.token);
    updateAmbienceBtn();
  }
}

// The escape hatch for a bad pick. The server remembers the refusal, so this
// walks down the result list rather than re-offering what was just rejected.
async function rerollAmbience(layer = null) {
  // Only a real layer index selects a layer; anything else means the mix.
  layer = Number.isInteger(layer) ? layer : null;
  if (!AMB.enabled || !AMB.configured) {
    toast("Turn ambience on first (🎧 beside the input box).", "warn");
    return;
  }
  if (AMB.turnId == null || !AMB.signature) return;
  if (AMB.pinned) {
    toast("This room's sound is pinned — clear the pin to reroll it.", "warn");
    return;
  }
  const found = await resolveAmbience(AMB.turnId, AMB.signature,
                                      { reroll: true, layer });
  if (!found) return;
  AMB.silent = !!found.silent;
  AMB.reason = found.reason || "";
  AMB.track = found.silent ? null : (found.layers[0] || null);
  AMB.wanted = found.token;
  playAmbience(found.layers || [], found.token);
  updateAmbienceBtn();
  if (found.silent) {
    toast("Nothing to hear in this room" + (found.reason ? ` — ${found.reason}` : "."),
          "warn");
    return;
  }
  const named = (found.layers || []).map(l => l.title).filter(Boolean).join(" + ");
  if (named) toast("Now playing: " + named, "ok");
}

function ambienceOnVisibleTurn(turnId, opts = {}) {
  clearTimeout(AMB.timer);
  clearTimeout(AMB.dwellTimer);
  // The quick pass plays whatever is already on disk.
  AMB.timer = setTimeout(
    () => ambienceForTurn(turnId, { commission: !!opts.fresh }), AMB_SETTLE_MS);
  // The slow one is allowed to go looking. Cancelled by the next scroll tick,
  // so it only ever fires where the reader actually stopped -- except on a
  // freshly generated turn, where they are plainly here and waiting.
  if (!opts.fresh) {
    AMB.dwellTimer = setTimeout(
      () => ambienceForTurn(turnId, { commission: true }), AMB_DWELL_MS);
  }
}

function ambienceResetForRender() {
  AMB.byTurn.clear();
  clearTimeout(AMB.timer);
  clearTimeout(AMB.dwellTimer);
  if (AMB.chatId !== S.chatId) {
    AMB.chatId = S.chatId;
    AMB.wanted = null;
    AMB.room = null;
    AMB.playingRoom = null;
    stopAmbience();
  }
  if (!S.chatId) stopAmbience();
  updateAmbienceBtn();
}

function updateAmbienceBtn() {
  const button = $("#b-ambience");
  if (!button) return;
  const on = AMB.enabled && AMB.configured;
  button.classList.toggle("on", on && !AMB.blocked);
  button.classList.toggle("blocked", !!AMB.blocked);
  const playing = AMB.silent
    ? " — this room is silent"
    : AMB.track && AMB.track.title ? ` — “${AMB.track.title}”` : "";
  button.title = !AMB.configured
    ? "Room ambience — no source set yet (⚙ API › Room ambience)"
    : AMB.blocked
      ? "Room ambience — click anywhere to start (the browser blocked autoplay)"
      : `Room ambience: ${AMB.enabled ? "on" : "off"}${playing}\nClick for sound options`;

  const mute = $("#b-amb-mute");
  if (mute) {
    mute.textContent = AMB.muted ? "🔇" : "🔊";
    mute.classList.toggle("muted", AMB.muted);
    mute.title = AMB.muted
      ? "Ambience muted — stays muted in every room and story until you unmute"
      : "Mute ambience everywhere";
  }
  const reroll = $("#b-amb-reroll");
  if (reroll) {
    reroll.disabled = !on || !AMB.signature;
    reroll.title = AMB.pinned
      ? "This room's sound is pinned — clear the pin to reroll"
      : AMB.silent
        ? "This room was judged to have no sound of its own — find one anyway"
        : "Different sound for this room";
  }
  const slider = $("#amb-vol");
  if (slider) slider.value = AMB.volume;
}

// ---- one-shots ----
// A bed loops; thunder happens once. Routed through this file rather than
// played by weather-fx.js directly because mute and volume live here, and a
// thunderclap that ignored the mute button would be the single most annoying
// thing this feature could do.

// name -> [urls]. A LIST, because one thunderclap replayed for a whole storm
// stops being weather and becomes a sample: the ear learns it in three or four
// strikes. The server hands back a different take each time it is asked, and
// this collects them until there are enough to play from memory.
const AMB_ONESHOTS = new Map();
const AMB_ONESHOT_TAKES = 4;

async function playAmbienceOneshot(name, level = 0.7) {
  // Every gate the bed obeys, in the order that costs least: off, muted, no
  // story open. A one-shot is fire-and-forget, so a check skipped here is a
  // sound nobody asked for with nothing to stop it.
  if (!AMB.enabled || AMB.muted || !AMB.configured || !S.chatId) return;
  const takes = AMB_ONESHOTS.get(name) || [];
  const pick = () => takes[Math.floor(Math.random() * takes.length)];
  let url = null;
  // Once there are enough takes, play from memory and skip the network
  // entirely. Below that, keep asking -- each request returns a different one.
  if (takes.length >= AMB_ONESHOT_TAKES) {
    url = pick();
  } else {
    try {
      const res = await api("GET", `/api/chats/${S.chatId}/ambience/oneshot/${name}`);
      if (res.ready && res.url) {
        if (!takes.includes(res.url)) takes.push(res.url);
        AMB_ONESHOTS.set(name, takes);
        url = res.url;
      } else {
        // Still fetching. Rather than a silent strike, use a take we already
        // have -- the library warms up over the course of the storm.
        url = takes.length ? pick() : null;
      }
    } catch (e) {
      url = takes.length ? pick() : null;    // silent flash beats an error toast
    }
  }
  if (!url) return;
  // Its own element, not one of the crossfade pair: a one-shot must not
  // interrupt the bed underneath it, and two claps can overlap.
  const clip = new Audio(url);
  clip.volume = Math.min(1, Math.max(0, AMB.volume * level));
  clip.play().catch(() => {});
}

// ---- the ambience panel ----
// Everything that is not "shut up now": on/off, what is playing and who made
// it, and reassigning this room's sound.

function ambienceCandidateRow(candidate, onPick) {
  const label = candidate.source === "freesound"
    ? `${candidate.title} — ${candidate.username || "?"} · ${candidate.license || ""} · ${candidate.duration || "?"}s`
    : candidate.path;
  const preview = candidate.source === "freesound" ? candidate.preview : null;
  return el("div", { class: "card row", style: "gap:8px;align-items:center" },
    el("div", { class: "small", style: "flex:1;overflow-wrap:anywhere" }, label),
    // Auditioning streams the library's own preview URL directly and downloads
    // nothing into the cache -- browsing is not choosing.
    preview ? el("audio", { src: preview, controls: "", preload: "none",
                            style: "height:30px;max-width:220px" }) : null,
    el("button", { onclick: () => onPick(candidate) }, "Use here"));
}

// ---- the mix ----
// One row per simultaneous bed: what it is, who made it, how loud it sits, and
// two ways to change it. The gain slider is live -- you hear the balance while
// you drag it -- and "Save this mix" is what makes the arrangement stick to
// the room.

const AMB_ROLE_LABEL = { tone: "room", weather: "weather", extra: "detail" };

function ambienceLayerRow(layer) {
  const level = el("input", {
    type: "range", min: "0", max: "1", step: "0.01",
    value: String(layer.gain == null ? 1 : layer.gain),
    style: "width:110px", title: "How loud this layer sits in the mix",
    "aria-label": `Level for the ${AMB_ROLE_LABEL[layer.role] || layer.role} layer`,
  });
  level.oninput = () => setLayerGain(layer.index, level.value);

  // Attribution is not decoration: the licences this feature fetches under
  // require crediting the uploader, and a mix has one per layer.
  const credit = layer.source === "freesound"
    ? el("span", { class: "small dim" },
        layer.username ? ` by ${layer.username}` : "",
        layer.license ? ` (${layer.license})` : "",
        layer.credit_url
          ? el("a", { href: layer.credit_url, target: "_blank", rel: "noreferrer",
                      style: "margin-left:6px" }, "source")
          : "")
    : el("span", { class: "small dim" }, " — local library");

  return el("div", { class: "card", style: "padding:8px 10px" },
    el("div", { class: "row", style: "gap:8px;align-items:center" },
      el("span", { class: "badge" }, AMB_ROLE_LABEL[layer.role] || layer.role),
      el("div", { style: "flex:1;overflow-wrap:anywhere" },
        el("b", { class: "small" }, layer.title || "(untitled)"), credit),
      level,
      el("button", {
        title: "A different sound for this layer only",
        onclick: () => { closeModal(); rerollAmbience(layer.index); },
        ...(AMB.pinned ? { disabled: "" } : {}),
      }, "🎲")));
}

function ambienceMixPanel() {
  // A silent room has to SAY it is silent. Shown as "nothing playing yet" it
  // would read as a feature stuck mid-search, and the reader would keep
  // clicking at it.
  if (AMB.silent) {
    return el("div", { class: "small dim" },
      el("b", {}, "Nothing to hear in this room. "),
      AMB.reason || "It makes no continuous sound of its own.",
      el("div", { style: "margin-top:6px" },
        "A bed is meant to be true to the room, so the engine can decline to lay one under a place that has none. 🎲 below overrules that and finds a sound anyway."));
  }
  if (!AMB.layers.length) {
    return el("div", { class: "small dim" }, "Nothing playing yet.");
  }
  return el("div", {},
    ...AMB.layers.map(ambienceLayerRow),
    el("div", { class: "small dim", style: "margin-top:6px" },
      "Levels apply straight away. Saving the mix keeps this arrangement for this room — including through weather and time changes, which the automatic pick follows."));
}

function openAmbiencePanel() {
  modal("Room ambience", body => {
    const roomName = AMB.roomName || "this room";
    const onOff = el("input", { type: "checkbox", ...(AMB.enabled ? { checked: "" } : {}) });
    onOff.onchange = () => { if (!!onOff.checked !== AMB.enabled) toggleAmbience(); };

    const query = el("input", {
      style: "flex:1", placeholder: "rain on stone, low machine hum, forest at night…",
    });
    const sourceSel = el("select", {},
      el("option", { value: "" }, "configured source"),
      el("option", { value: "local", ...(AMB.source === "local" ? { selected: "" } : {}) }, "local library"),
      el("option", { value: "freesound", ...(AMB.source === "freesound" ? { selected: "" } : {}) }, "Freesound"));
    const results = el("div", { style: "margin-top:10px" });

    const pick = async candidate => {
      try {
        await api("PUT", `/api/chats/${S.chatId}/ambience/pin`,
          { room: AMB.room, choice: candidate });
        // A pin changes the signature, so everything cached per turn is now
        // answering about the wrong bed.
        AMB.byTurn.clear();
        AMB.failed.clear();
        AMB.wanted = null;
        closeModal();
        toast(`“${roomName}” will use that sound.`, "ok");
        if (AMB.turnId != null) ambienceForTurn(AMB.turnId);
      } catch (e) {
        toast("Could not pin that sound.", "err");
      }
    };

    const search = async () => {
      results.innerHTML = "";
      results.append(loadingBlock("Searching…"));
      try {
        const res = await api("GET", "/api/ambience/search?q="
          + encodeURIComponent(query.value.trim())
          + (sourceSel.value ? "&source=" + sourceSel.value : ""));
        results.innerHTML = "";
        if (!res.results.length) {
          results.append(emptyState("Nothing matched. Try plainer words — a sound library indexes “rain” and “machine hum”, never a place from your story."));
          return;
        }
        for (const candidate of res.results) results.append(ambienceCandidateRow(candidate, pick));
      } catch (e) {
        results.innerHTML = "";
        results.append(emptyState("Search failed: " + (e?.message || "unknown error")));
      }
    };
    query.onkeydown = e => { if (e.key === "Enter") search(); };

    body.append(
      el("div", { class: "row" },
        el("label", { class: "small" }, onOff, " Play ambience for the room on screen"),
        el("span", { class: "spacer", style: "flex:1" }),
        el("button", { onclick: () => { toggleAmbienceMute(); closeModal(); openAmbiencePanel(); } },
          AMB.muted ? "🔇 Unmute" : "🔊 Mute")),
      el("div", { class: "small dim", style: "margin-top:4px" },
        "Sound is chosen from the room's spatial description only — never from who is standing in it. It follows the room, the hour, the weather and any damage; each distinct state is fetched once and cached."),
      el("h4", { style: "margin-top:14px" }, "The mix"),
      ambienceMixPanel(),
      el("div", { class: "row", style: "margin-top:8px" },
        el("button", { onclick: () => { closeModal(); rerollAmbience(); },
                       ...(AMB.pinned || !AMB.signature ? { disabled: "" } : {}) },
          AMB.silent ? "🎲 Find a sound anyway" : "🎲 Different sounds"),
        el("button", {
          onclick: async () => {
            try {
              await api("PUT", `/api/chats/${S.chatId}/ambience/pin`, {
                room: AMB.room,
                choice: { layers: AMB.layers.map(layer => ({
                  source: layer.source, path: layer.path, id: layer.id,
                  title: layer.title, license: layer.license,
                  username: layer.username, url: layer.credit_url,
                  role: layer.role, gain: layer.gain,
                })) },
              });
              AMB.byTurn.clear(); AMB.wanted = null;
              closeModal();
              toast("Mix saved for this room.", "ok");
              if (AMB.turnId != null) ambienceForTurn(AMB.turnId);
            } catch (e) {
              toast("Could not save the mix.", "err");
            }
          },
          ...(AMB.layers.length ? {} : { disabled: "" }),
        }, "📌 Save this mix"),
        AMB.pinned ? el("span", { class: "small dim" }, "This room is pinned.") : null),

      el("h4", { style: "margin-top:18px" }, `Choose the sound for “${roomName}”`),
      el("div", { class: "small dim" },
        "Describe the SOUND, not the fiction — a library has recordings of “low electrical hum”, never of a named ship. A choice made here sticks to the room and holds while the hour and the weather move; the automatic pick follows them."),
      el("div", { class: "row", style: "margin:8px 0" }, query, sourceSel,
        el("button", { onclick: search }, "Search")),
      results,
      el("div", { style: "margin-top:14px" },
        el("button", {
          onclick: async () => {
            await api("DELETE", `/api/chats/${S.chatId}/ambience/pin?room=`
              + encodeURIComponent(AMB.room || ""));
            AMB.byTurn.clear(); AMB.wanted = null;
            closeModal();
            toast("Back to automatic for this room.", "ok");
            if (AMB.turnId != null) ambienceForTurn(AMB.turnId);
          },
          ...(AMB.pinned ? {} : { disabled: "" }),
        }, "Clear this room's pin")));
  }, { wide: true });
}

async function toggleAmbience() {
  AMB.enabled = !AMB.enabled;
  if (AMB.enabled) AMB.failed.clear();
  // Create the players inside the click itself: this gesture is what a browser
  // accepts as permission to make noise, and doing it after an await no longer
  // counts as user-initiated in some engines.
  ambiencePlayers();
  updateAmbienceBtn();
  try {
    await api("PUT", "/api/ambience", { enabled: AMB.enabled });
    if (S.boot && S.boot.ambience) S.boot.ambience.enabled = AMB.enabled;
    if (AMB.enabled && !AMB.configured) {
      toast("Ambience is on, but no source is set — pick one under ⚙ API.", "warn");
    }
    if (AMB.enabled) {
      AMB.byTurn.clear();
      if (AMB.turnId != null) await ambienceForTurn(AMB.turnId);
    } else {
      stopAmbience();
    }
  } catch (error) {
    AMB.enabled = !AMB.enabled;
    updateAmbienceBtn();
    toast("Could not change the ambience setting.", "err");
  }
}

// Called from boot() once /api/bootstrap has landed. Server-derived state
// only -- volume and mute are restored at load (below), because waiting for a
// round trip to learn that the reader muted this would mean a window in which
// a bed could start playing over the top of whatever they muted it for.
function syncAmbience() {
  const cfg = (S.boot && S.boot.ambience) || {};
  AMB.enabled = !!cfg.enabled;
  AMB.configured = !!cfg.configured;
  AMB.source = cfg.source || "local";
  updateAmbienceBtn();
}

// Restore the reader's own two knobs synchronously, before anything can ask
// for audio: these are client-side by design and need no network at all, and a
// slider that reads 0.35 for as long as bootstrap takes is showing a number
// that is not true.
AMB.volume = ambienceStored("volume", 0.35);
AMB.muted = localStorage.getItem("ambience.muted") === "1";
updateAmbienceBtn();

$("#b-ambience").onclick = openAmbiencePanel;
$("#b-amb-mute").onclick = toggleAmbienceMute;
// Wrapped, not passed by reference: an onclick handler is called WITH the
// click event, which would arrive as the layer index and reach the server as
// an object. The whole-mix reroll takes no argument.
$("#b-amb-reroll").onclick = () => rerollAmbience();
$("#amb-vol").oninput = e => setAmbienceVolume(e.target.value);
