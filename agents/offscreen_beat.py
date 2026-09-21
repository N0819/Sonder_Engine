"""A beat that runs in a causality bubble, with no player in it.

WHAT A BUBBLE IS FOR. `world/spatial_bubbles.py` gives a major character who
walks out of the player's causality bubble a frame of their own. Until this
module existed that frame was a PAUSE: her scene was preserved exactly as she
left it, and she stood in it, beat after beat, until somebody played her. So
a character who walked away had a place rather than a life, and the design's
own claim -- that a bubble prices an absent character by whether their thread
is being told -- had nothing behind it. Measured live before this landed
(`google/gemini-3.8-flash`, the Millbrook run, 2026-09-17): a courier crossed
to the far shore and stood on the landing for three player beats, her frame's
scene byte-identical each time, and formed not one memory.

WHAT RUNS, AND WHAT DOES NOT. The ordinary pipeline, minus the two stages that
exist because a player is watching:

  * NO `director_interpret` MODEL CALL. Interpretation is the reading of a
    player's declared line, and there is no line. `offscreen_interpretation`
    below writes the same shape deterministically: nobody spoke, nobody acted,
    and every body this frame places is a mind that may now act. Free, and it
    cannot invent conduct because it declares none.
  * NO NARRATOR. Narration is the player-facing slice and nobody is reading
    it. What she did reaches the player the way anything she did off-screen
    reaches them -- because she remembers it, and tells them, or because they
    find what she left. Rendering prose no eye receives would also be the one
    way this feature could leak: a page describing her beat is a page that
    could be shown.

Everything else is hers exactly as it is anybody's: her perception is
composed from her own scene, her character step declares from her private
perception and memory, the Director resolves objective outcome, and commit
writes her memories stamped with her own frame.

THE COST IS THE WHOLE ARGUMENT AGAINST THIS, and it is stated rather than
hidden: § 6 of `DESIGN_OFFSCREEN_SUPERSEDED.md` says "a bubble is a frame, and
frames cost more than a tick", and it is right. A live bubble costs a character
call and a Director resolve every beat, forever, whether or not anything is
happening to her, and EVERY live bubble runs -- there is no cap, because a cap
is a freeze wearing a number and an absent character who is not dormant must
not freeze. The lever is dormancy: see the module constant below.
"""

from __future__ import annotations

import time

#: NO CAP, and the absence is a ruling rather than an oversight (owner,
#: 2026-09-17: "I don't think a character should ever freeze unless they've
#: been made dormant"). A cap on how many bubbles advance per beat is a FREEZE
#: wearing a number: the third absent character stands still indefinitely while
#: the first two live, and nothing in the fiction explains why. This shipped
#: with `OFFSCREEN_BEAT_CAP = 2` for exactly one afternoon.
#:
#: WHICH MEANS THE COST SCALES WITH THE ABSENT CAST, one character call and one
#: Director resolve per live bubble per beat, and the lever is DORMANCY rather
#: than a ceiling here. A character nobody is telling a story about is made
#: dormant, Charter moves them for free, and what they did while dormant
#: becomes memory on the way back (`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md`
#: § 3b). Until that tier exists the lever is only the first half: dormant
#: characters do not get bubbles, so they cost nothing and remember nothing.
OFFSCREEN_BEATS_ARE_UNCAPPED = True

#: The jobs key, one per chat, so a beat still running when the next one
#: commits is not stacked on top of itself.
OFFSCREEN_BEAT_JOB_KEY = "offscreen_beat"

#: How many of a bubble's own beats may leave its body in the same room before
#: the engine says so. Three rather than one because standing still is
#: ordinary -- waiting, working, talking, sleeping are all a beat spent where
#: you are -- and a thread that has not moved three times running while
#: spending a beat each turn is a different thing from a person at rest.
#:
#: It files a NOTE, never a change: an open planning need the Writers' Room
#: may answer and may not. That is deliberately the weakest possible action --
#: the two deterministic triggers designed on 2026-08-30 both died the moment
#: they were replayed against the chat that motivated them, and this one has
#: been replayed against exactly one story.
STALLED_AFTER_BEATS = 3


def offscreen_interpretation(cast_rows, scene):
    """A `director_interpret` payload for a beat nobody declared.

    The same SHAPE the model would have produced, with every player-owned
    field empty, because they are empty: no speech, no action, no movement, no
    assertion. What it does say is `flow.reactors` -- every cast body the
    scene places in this frame -- which is the Director's pacing judgement in
    a beat where the only minds present are the ones whose beat it is.

    DETERMINISTIC ON PURPOSE, and not merely to save the call. An interpret
    stage asked to read an absent player's input is asked to invent one, and
    the engine's oldest rule is that nobody may author the player's conduct.
    There is no player here to author, and the safe way to say that is a
    payload that declares nothing rather than a prompt asked to declare
    nothing.
    """
    from agents.common import _present_cast_bodies

    present = _present_cast_bodies(scene or {}, cast_rows or [])
    return {
        "kind": "interpret",
        "ledgers": [], "causal_ledger": [], "obligations": [],
        "ledger_notes": "", "changes_asserted": [],
        "sequence": [], "speech": "", "speech_volume": "normal",
        "private_thought": "", "action": "", "actions": [],
        "movement": None, "contact_assertions": [], "state_assertions": [],
        "onset_state_assertions": [], "follow_op": None,
        "location_query": "", "notes": "", "other_players": [],
        "orchestration": {},
        "flow": {"reactors": [int(b["id"]) for b in present],
                 "resolution_flags": {}},
    }


def is_offscreen_beat(chat_id, turn_row):
    """Is this turn a bubble's own beat rather than a played one.

    DERIVED, never stored, for the reason `is_bubble_frame` is: a turn in a
    frame no human is playing, carrying no player input, is a beat the engine
    scheduled -- and a host who switches to that frame and types something is
    playing it, which is a different beat and takes the ordinary plan. Neither
    fact needs a column, and a column would be free to disagree with both.
    """
    if not turn_row:
        return False
    try:
        frame_id = turn_row["frame_id"]
        player_input = turn_row["player_input"]
    except (KeyError, IndexError, TypeError):
        return False
    if frame_id is None or (player_input or "").strip():
        return False
    from world.spatial_frames import is_bubble_frame

    return bool(is_bubble_frame(chat_id, frame_id))


def live_bubbles(chat_id, parent_frame_id):
    """Every live bubble frame split from this one, oldest first."""
    from core.db import q
    from world.spatial_frames import is_bubble_frame

    return [row["id"] for row in q(
        "SELECT id FROM frames WHERE chat_id=? AND parent_frame_id IS ? "
        "AND kind='spatial' AND merged_turn_idx IS NULL ORDER BY id",
        (chat_id, parent_frame_id))
        if is_bubble_frame(chat_id, row["id"])]


def schedule_offscreen_beats(ctx):
    """Queue this beat's bubbles out of band. Returns the Job, or None.

    OUT OF BAND for the reason the memory consolidation beside it is: a whole
    pipeline beat inside the player's wait would double the turn, and none of
    what it produces is a fact this turn needs. The player's beat is already
    durable when this runs; a bubble that fails is a warning and never a
    rollback, and the next beat offers it again.

    One job per chat (`OFFSCREEN_BEAT_JOB_KEY`), so a bubble still thinking
    when the next player beat commits is not stacked on top of itself.
    """
    from core import jobs

    chat_id = ctx.chat.id
    parent = ctx.turn.frame_id
    turn_idx = ctx.turn.idx
    bubbles = live_bubbles(chat_id, parent)
    if not bubbles:
        return None

    def _produce(job):
        from core.logging_utils import logger

        ran = []
        for frame_id in bubbles:
            if job.cancelled.is_set():
                break
            try:
                ran.append(run_offscreen_beat(chat_id, frame_id))
            except Exception as exc:            # noqa: BLE001 - reported
                logger.info("offscreen beat failed: chat=%s frame=%s error=%s",
                            chat_id, frame_id, str(exc)[:300])
                ran.append({"frame_id": frame_id, "error": str(exc)[:300]})
        return ran

    return jobs.submit(chat_id, OFFSCREEN_BEAT_JOB_KEY, _produce,
                       base_turn=turn_idx)


def run_offscreen_beat(chat_id, frame_id):
    """One beat in one bubble. Blocking; called from the job above.

    The turn row is created the way `turn_new` creates one -- chat-global idx
    inside a transaction, and a checkpoint before it -- because a rewind must
    be able to take this beat back exactly as it takes back a played one. An
    offscreen beat that no checkpoint covered would be the one kind of turn
    the story could not undo.
    """
    from agents.runtime import run_pipeline
    from core.db import q, qi, transaction
    from persist.checkpoints import ensure_checkpoint, snapshot_blob

    blob = snapshot_blob(chat_id)
    with transaction():
        last = q("SELECT idx FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
                 (chat_id,), one=True)
        idx = (last["idx"] + 1) if last else 0
        ensure_checkpoint(chat_id, idx, blob=blob)
        turn_id = qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (chat_id, idx, "", time.time(), frame_id))

    from core.db import wget_for_frame

    def _rooms():
        scene = wget_for_frame(chat_id, "scene", frame_id, {}) or {}
        return stalling_bodies(scene)

    before = _rooms()
    started = time.time()
    for _ in run_pipeline(chat_id, turn_id, frame_id=frame_id):
        pass
    after = _rooms()
    stalled = note_beat_movement(chat_id, frame_id, idx, before, after)
    return {"frame_id": frame_id, "turn_id": turn_id, "idx": idx,
            "seconds": round(time.time() - started, 1), "stalled": stalled}


def stalling_bodies(scene):
    """``{name: room}`` for the bodies in this scene a thread can stall for.

    POSITIONS IS NOT A BODY ROSTER. The class is CLAUDE.md's, from review
    2026-09-07 A56, which found three sites reading `scene.positions` as if
    every key in it were somebody; `director.mint_unreferenced_things` made a
    fourth the day it landed, because a thing a beat reached for has to stand
    somewhere for a contact to attach to it.

    Measured the same afternoon (Aldermill, third run, turn 16): a winch's
    `crank_handle` was minted into the mill yard, sat there for three beats
    exactly as a crank handle does, and the engine filed an open planning need
    asking the Writers' Room to unstick its narrative thread.

    `scene_names_body` is the same predicate the player-room resolver uses, so
    the two cannot drift about what counts as somebody. A scene that never
    wrote an entity record for its cast still answers yes for them, which is
    what keeps a story from losing its own people to this.
    """
    from agents.common import scene_names_body

    scene = scene if isinstance(scene, dict) else {}
    return {str(name): str(room)
            for name, room in (scene.get("positions") or {}).items()
            if room and scene_names_body(scene, name)}


def note_beat_movement(chat_id, frame_id, turn_idx, before, after):
    """Record what this beat moved, and say so when nothing has for a while.

    WHAT IT WRITES IS AN OBSERVATION, and the count is DERIVED from it rather
    than kept beside it: the log already has to carry the beat, and a second
    row holding "how many in a row" would be the same fact stored twice and
    free to disagree with the first. `offscreen_log` is frame-scoped, so a
    bubble's run of beats is its own.

    Returns the names the engine has just called stalled, or [].
    """
    from core.db import wget_for_frame, wset_for_frame

    moved = sorted(name for name, room in (after or {}).items()
                   if (before or {}).get(name) != room)
    log = wget_for_frame(chat_id, "offscreen_log", frame_id, []) or []
    log.append({"turn": turn_idx, "kind": "offscreen_beat",
                "where": dict(after or {}), "moved": moved})
    wset_for_frame(chat_id, "offscreen_log", log, frame_id)

    # The trailing run of this frame's own beats, newest first, stopping at
    # anything that is not one: a split or a couple in the middle of the run
    # is a different stretch of life and not evidence about this one.
    run = []
    for entry in reversed(log):
        if not isinstance(entry, dict) or entry.get("kind") != "offscreen_beat":
            break
        run.append(entry)
    if len(run) < STALLED_AFTER_BEATS:
        return []

    stuck = []
    for name, room in (after or {}).items():
        if not room:
            continue
        if all(not (e.get("moved") or []) or name not in (e.get("moved") or [])
               for e in run[:STALLED_AFTER_BEATS]) and all(
                   (e.get("where") or {}).get(name) == room
                   for e in run[:STALLED_AFTER_BEATS]):
            stuck.append(name)
    if stuck:
        _file_stalled_needs(chat_id, frame_id, turn_idx, stuck, after)
    return sorted(stuck)


def _file_stalled_needs(chat_id, frame_id, turn_idx, names, where):
    """One open need per stalled body, carrying its own words untouched."""
    from story.scene import active_cast, char_state
    from story.character_schema import (character_name,
                                        normalized_character_from_text)
    from world.planning_needs import file_planning_need, planning_need

    aims = {}
    for row in active_cast(chat_id, frame_id):
        name = character_name(normalized_character_from_text(row["sheet"]))
        if name not in names:
            continue
        state = char_state(chat_id, row["id"], frame_id=frame_id) or {}
        active = state.get("active_state") if isinstance(
            state.get("active_state"), dict) else {}
        aims[name] = str(active.get("goal") or "").strip()

    for name in sorted(names):
        aim = aims.get(name, "")
        try:
            need = planning_need(
                "room", "offscreen_thread_stalled",
                # HER OWN WORDS, verbatim and unparsed. Reading them for a
                # place name would be the engine deciding what a sentence is
                # about; the Room reads prose and this does not.
                subject=aim or name,
                surface={"who": name, "room": str((where or {}).get(name) or ""),
                         "beats": STALLED_AFTER_BEATS, "aim": aim},
                turn_idx=turn_idx, frame_id=frame_id)
            file_planning_need(chat_id, need, frame_id=frame_id,
                               turn_idx=turn_idx)
        except Exception:                       # noqa: BLE001 - a note, never a beat
            continue
