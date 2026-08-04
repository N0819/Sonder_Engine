"use strict";
// ---- Turn-completion chime ----
// A turn in this engine is a long wait -- a median of several minutes across
// the benchmark corpus -- so the reader goes and does something else and comes
// back to check. This is the "it's ready" tap on the shoulder, and its entire
// job is to be audible from another tab without being the kind of sound
// somebody switches off on the second day.
//
// Four decisions, each of which the obvious alternative gets wrong:
//
// 1. SYNTHESISED, NOT A FILE. Two sine tones through a gain envelope: nothing
//    to ship, nothing to fetch, nothing to fail on a cold cache at the exact
//    moment it is supposed to fire. A notification sound that has to download
//    first is a notification sound that arrives late or not at all.
// 2. SCHEDULED ON THE AUDIO CLOCK, NEVER ON setTimeout. A backgrounded tab has
//    its timers throttled to once a second or worse, which would smear the two
//    notes into something arrhythmic and wrong. `ctx.currentTime` runs at
//    audio rate regardless of what the page is doing, so the envelope sounds
//    identical hidden and visible -- which is the whole requirement.
// 3. UNLOCKED ON THE GESTURE THAT STARTS THE WAIT. Browsers refuse audio until
//    the user has interacted, and the interaction is right there: you press
//    send, then you leave. `chimeArm()` runs on that press, so by the time the
//    turn lands the context has been running for minutes. Resuming at the
//    moment of the ping instead would be a race against a policy that is
//    designed to be won by the browser.
// 4. QUIET, SHORT, AND CONSONANT. Peak gain 0.06, decayed away inside a
//    second and a half, and a rising perfect fifth -- an interval with no
//    tension in it to resolve. An alert has to be noticeable from the next
//    room; this has to be noticeable from the next tab and ignorable from
//    this one, which is a different and much softer target.
//
// Mute is global and sticky in localStorage, for the same reason ambience's
// is: somebody who silenced this because they are on a call wants it silent in
// the next story and after a reload, without a round trip.

const CHIME = {
  ctx: null,
  muted: localStorage.getItem("chime.muted") === "1",
  // Peak of the gain envelope. Deliberately far below the ambience bed's
  // default: this plays over whatever else is sounding and must not duck it.
  level: 0.06,
};

// A rising perfect fifth, D5 to A5, the second note overlapping the first.
// Written as data because the shape is the design -- anyone retuning this is
// changing these six numbers and nothing else.
const CHIME_NOTES = [
  { freq: 587.33, at: 0.00, decay: 1.10 },
  { freq: 880.00, at: 0.11, decay: 1.40 },
];

function chimeContext() {
  if (CHIME.ctx) return CHIME.ctx;
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return null;
  try {
    CHIME.ctx = new Ctor();
  } catch (e) {
    CHIME.ctx = null;
  }
  return CHIME.ctx;
}

// Called from the send/reroll gesture, minutes before the sound is needed.
// Creating the context here rather than at load is deliberate: a context
// constructed with no gesture behind it starts suspended, and some browsers
// count that against the page.
function chimeArm() {
  if (CHIME.muted) return;
  const ctx = chimeContext();
  if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {});
}

function chimePlay() {
  if (CHIME.muted) return;
  const ctx = chimeContext();
  if (!ctx) return;
  // A context suspended at this point means the gesture never happened or the
  // browser took it back. Ask once; if it is refused there is nothing further
  // to do and silence is the correct outcome, not an error to report.
  if (ctx.state === "suspended") ctx.resume().catch(() => {});

  const now = ctx.currentTime;
  // One shared lowpass: sine partials are already soft, but the attack
  // transient is not, and this is the difference between a chime and a click.
  const tone = ctx.createBiquadFilter();
  tone.type = "lowpass";
  tone.frequency.setValueAtTime(2600, now);
  tone.connect(ctx.destination);

  for (const note of CHIME_NOTES) {
    const at = now + note.at;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(note.freq, at);
    // Attack over 12ms, not instantly: a gain step from zero is a click at any
    // volume. Then an exponential tail, because a linear one audibly stops
    // rather than fading.
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(CHIME.level, at + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + note.decay);
    osc.connect(gain);
    gain.connect(tone);
    osc.start(at);
    osc.stop(at + note.decay + 0.05);
  }
}

// ---- Which other waits are worth a chime ----
//
// A turn is not the only thing here that takes minutes. Generating a
// character, filling a psychology sheet, drafting a persona, building a
// lorebook -- all of them are start-it-and-go-elsewhere operations, and all of
// them are ordinary `api()` calls rather than the pipeline stream. Rather than
// name each one (a list that would be wrong the first time somebody adds a
// route), the rule is duration: a mutation that took long enough that the
// reader plausibly stopped watching gets the same tap on the shoulder.
//
// Two exclusions, both because the result announces itself:
//
//   * BACKDROPS. The picture appears. Chiming as well would be a second
//     notification for something already impossible to miss.
//   * AMBIENCE. It is a SOUND. Ringing a bell to announce that a sound is
//     about to start is the definition of obnoxious, and it would land right
//     on top of the crossfade.
//
// GET is excluded outright: reads are polling, listing and refreshing, and
// none of them are a thing the engine finished making.
const CHIME_EXCLUDED = /\/(backdrops?|ambience)(\/|$|\?)/i;
const CHIME_MUTATIONS = /^(POST|PUT|PATCH)$/i;
// Below this, the reader was still looking at the screen and the result is its
// own feedback. Chosen well above an ordinary save round trip and well below
// any real generation.
const CHIME_MIN_MS = 4000;

function chimeWatches(method, url) {
  return CHIME_MUTATIONS.test(String(method || ""))
    && !CHIME_EXCLUDED.test(String(url || ""));
}

// Called by `api()` on a successful response. Silent for anything short,
// excluded, or muted.
function chimeWorkFinished(method, url, elapsedMs) {
  if (!chimeWatches(method, url)) return false;
  if (!(elapsedMs >= CHIME_MIN_MS)) return false;
  chimePlay();
  return true;
}

function chimeSetMuted(muted) {
  CHIME.muted = !!muted;
  localStorage.setItem("chime.muted", CHIME.muted ? "1" : "0");
  updateChimeBtn();
}

function toggleChimeMute() {
  chimeSetMuted(!CHIME.muted);
  // Unmuting IS a gesture, and it is the one moment somebody wants to hear
  // what they just switched on rather than find out three minutes later.
  if (!CHIME.muted) {
    chimeArm();
    chimePlay();
  }
}

function updateChimeBtn() {
  const btn = $("#b-chime");
  if (!btn) return;
  btn.textContent = CHIME.muted ? "🔕" : "🔔";
  btn.classList.toggle("muted", CHIME.muted);
  btn.title = CHIME.muted
    ? "Completion chime off — stays off in every story until you turn it on"
    : "Chime when a turn or a generation finishes. Plays while this tab is in "
      + "the background";
}

if ($("#b-chime")) $("#b-chime").onclick = toggleChimeMute;
updateChimeBtn();
