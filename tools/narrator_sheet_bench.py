#!/usr/bin/env python3
"""Narrator sheet variants, measured against REAL turns from real stories.

The synthetic beat in `narrator_package_bench.py` answered one question well
and cannot answer this one: it exercises about six of the sheet's thirty-odd
blocks, so a cut anywhere else scores as "no change" for want of a beat that
tests it. This harness replays turns the engine actually ran -- their own
view, their own beat record, their own preceding narration -- and scores the
output with THE ENGINE'S OWN CHECKS rather than bespoke regexes.

That last part is the point. Ten of the thirteen fidelity checks are
enforceable (`_ENFORCEABLE_PREFIXES`), and an enforceable warning buys a whole
extra narrator call; the craft screen buys up to two more. So the decision
variable for cutting a block is not "did the prose read fine", it is "how many
extra model calls did this arm buy, and did any fact reach the page wrong".

Baseline for comparison, free and offline -- the stored warnings on the
variants the engine already wrote (`fidelity_warnings` is persisted on the
narrator step):

    24.4% of 2,369 active variants carry at least one, dominated by
    content-reuse (298), dropped/altered dialogue (222) and missing proper
    nouns (88). Those are POST-correction residuals: an enforceable warning
    has already bought its rewrite by the time the variant is stored.

    python3 tools/narrator_sheet_bench.py --list
    python3 tools/narrator_sheet_bench.py --turns 12 --arms full,no_instances
    python3 tools/narrator_sheet_bench.py --turns 8 --arms full,lean --show

REAL CALLS, REAL MONEY: one per (turn x arm). The narrator role's configured
model, as-is. Reads the live database READ-ONLY and writes nothing to it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SHEETS = os.path.join(ROOT, "tools", "narrator_sheets")


def _db(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _step(con, turn_id, key):
    row = con.execute(
        "SELECT v.content FROM steps s JOIN variants v "
        "ON v.step_id=s.id AND v.active=1 WHERE s.turn_id=? AND s.key=?",
        (turn_id, key)).fetchone()
    if not row:
        return {}
    try:
        out = json.loads(row["content"])
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


def player_name(con, chat_id):
    """THE PERSONA'S NAME, from the chat's persona sheet.

    Read from the right place because reading it from the wrong one poisoned
    a whole run: the first cut of this file took `commit.player_name`, which
    that step does not carry, so every beat fell back to the literal "You".
    `_check_player_person` then hunted for a player NAMED "You" inside
    second-person prose, where the word is in every sentence, and reported
    five to six "Player named in third person" violations per twelve drafts
    against a stored corpus rate of four in 2,369. A metric that fires on
    almost every draft is measuring the harness, not the sheet.
    """
    row = con.execute(
        "SELECT p.name AS name, p.sheet AS sheet FROM chats c "
        "JOIN personas p ON p.id=c.persona_id WHERE c.id=?",
        (chat_id,)).fetchone()
    if not row:
        return "Player"
    try:
        sheet = json.loads(row["sheet"] or "{}")
        named = ((sheet.get("identity") or {}).get("name") or "").strip()
        if named:
            return named
    except (TypeError, ValueError):
        pass
    return (row["name"] or "Player").strip()


def speaker_displays(con, chat_id, player_name):
    """`name -> what THIS player may call them`, the engine's own floor.

    `_ordered_beat_events` renders every speaker through `_speaker_display`
    against the `known` ledger, so an unrecognised body arrives as the
    composer's epithet rather than its canonical name. Reconstructing the
    record without that step hands the control arm names the player has not
    earned: chat 81's view says "You hear a voice say" while the raw loop
    output says "Sarah Moon", and chat 84's view says "The unfamiliar person"
    where the raw output says "Security Guard (Right)".
    """
    from agents.narration import _speaker_display
    from agents.common import character_scene_keys
    from story.character_schema import character_appearance, character_name
    row = con.execute(
        "SELECT value FROM world WHERE chat_id=? AND key='known'",
        (chat_id,)).fetchone()
    try:
        known = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        known = {}
    recognized = set((known or {}).get(player_name) or [])
    out = {}
    for r in con.execute(
            "SELECT c.sheet AS sheet FROM chat_chars cc "
            "JOIN characters c ON c.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,)):
        try:
            sheet = json.loads(r["sheet"])
        except (TypeError, ValueError):
            continue
        name = character_name(sheet)
        if not name:
            continue
        out[name] = _speaker_display(
            name, recognized, character_appearance(sheet),
            character_scene_keys(sheet)[1:])
    return out


def _perceives(scene, player_name, name):
    """The gate `_ordered_beat_events` puts on an NPC ACT, applied here too.

    Omitting it is not a small inaccuracy: chat 81 turn 6 put "picks up the
    pen from the console and writes on the intake form" into the control arm's
    beat record, and the narrator rendered it -- a thing the player cannot see
    through a one-way mirror from the next room. Every `full` comparison run
    before this gate existed was scoring an arm that had been handed material
    the firewall withholds, which flatters its length and its detail.
    """
    from agents.narration import _player_sees_character
    from world.spatial import room_of
    if not scene or not name:
        return False
    p_room = room_of(scene, player_name)
    if not p_room:
        return False
    return bool(_player_sees_character(
        scene, player_name, p_room, name, room_of(scene, name)))


def beat_events(con, turn_id, player_name, scene=None):
    """This beat's record, rebuilt the way `_ordered_beat_events` builds it.

    Deliberately a RECONSTRUCTION rather than a call into the live function:
    that one needs a whole PipelineContext and a writable database. The
    ordering is the same -- the player's declaration first, then interaction
    rounds in call order, then background reactions -- and the info-barrier
    filter (an NPC line enters only if its quote reached the player's view) is
    applied by the caller, which holds the view.
    """
    from agents.common import observable_action_text

    events = []
    for e in (_step(con, turn_id, "director_interpret").get("sequence") or []):
        if not isinstance(e, dict):
            continue
        if e.get("type") == "speech" and e.get("text"):
            events.append({"actor": player_name, "kind": "speech",
                           "declared": True, "quote": e["text"]})
        elif e.get("type") == "action":
            # THE ENGINE'S OWN COERCION, not a copy of it. `observable or
            # attempt` is not what `observable_action_text` does in two ways
            # that matter: an explicit empty `observable` means "no outward
            # manifestation, skip this act" and must NOT fall through to
            # `attempt`, and a non-string value has to be stringified rather
            # than carried. Ten of the 2,223 stored action events have a
            # non-string `attempt`, and each one reached this harness as an
            # act whose text was the word "True".
            surface = observable_action_text(e)
            if surface:
                events.append({"actor": player_name, "kind": "action",
                               "action": surface})
    for key in ("reaction_loop", "interaction_loop"):
        for rnd in (_step(con, turn_id, key).get("rounds") or []):
            who = rnd.get("speaker") or rnd.get("reactor")
            for e in ((rnd.get("result") or {}).get("sequence") or []):
                if not isinstance(e, dict) or not who:
                    continue
                if e.get("type") == "speech" and e.get("text"):
                    events.append({"actor": who, "kind": "speech",
                                   "quote": e["text"]})
                elif e.get("type") == "action" and (
                        str(e.get("visibility") or "overt").lower() == "overt"):
                    surface = observable_action_text(e)
                    if surface and _perceives(scene, player_name, who):
                        events.append({"actor": who, "kind": "action",
                                       "action": surface})
    br = _step(con, turn_id, "background_react")
    for r in (br.get("reactions") or ([br] if br.get("fired") else [])):
        entry = (r or {}).get("dialogue_log_entry") or {}
        if entry.get("exact_quote") and entry.get("speaker"):
            events.append({"actor": entry["speaker"], "kind": "speech",
                           "quote": entry["exact_quote"]})
    return events


def narration_person(con, chat_id):
    """The person this story established, not an assumption. Second is the
    common case and was hardcoded here at first; a first- or third-person
    story scored against it would have had every draft judged wrong."""
    row = con.execute(
        "SELECT value FROM world WHERE chat_id=? AND key='narration_person'",
        (chat_id,)).fetchone()
    if not row:
        return "second"
    try:
        return str(json.loads(row[0]) or "second")
    except (TypeError, ValueError):
        return "second"


def past_narration(con, chat_id, turn_idx, frame_id, current_input, depth=12):
    """`_past_narration_block`, rebuilt read-only. Same query, same shape."""
    rows = con.execute(
        "SELECT t.player_input AS said, v.content AS content FROM turns t "
        "LEFT JOIN steps s ON s.turn_id=t.id AND s.key='narrator' "
        "LEFT JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? "
        "ORDER BY t.idx DESC LIMIT ?",
        (chat_id, turn_idx, frame_id, depth)).fetchall()
    parts, prev = [], []
    for r in reversed(rows):
        said = (r["said"] or "").strip()
        if said:
            parts.append(said)
        prose = ""
        if r["content"]:
            try:
                prose = (json.loads(r["content"]) or {}).get("prose") or ""
            except (TypeError, ValueError):
                prose = ""
        if prose.strip():
            parts.append(prose.strip())
            prev.append(prose)
    tail = (current_input or "").strip()
    if tail:
        parts.append(tail)
    return "\n\n".join(parts), prev[-4:]


def collect(con, want, chats=None, ledger_only=True):
    """Real beats worth scoring: awake, non-opening, with a delivered view and
    at least one NPC line that actually reached the player -- and, unless
    `ledger_only=False`, only beats whose stored observations were written by
    the projection that runs today (see the era gate below)."""
    from agents.common import _quote_body
    from agents.narration import _narrator_player_declared

    where = "WHERE t.idx > 0"
    args = []
    if chats:
        where += " AND t.chat_id IN (%s)" % ",".join("?" * len(chats))
        args += list(chats)
    rows = con.execute(
        f"SELECT t.id, t.chat_id, t.idx, t.frame_id, t.player_input "
        f"FROM turns t {where} ORDER BY t.id DESC LIMIT 4000", args).fetchall()
    # SPREAD ACROSS STORIES, not just the newest one. Taking the most recent
    # N turns hands back N beats from a single chat -- same cast, same room,
    # same handful of sheet blocks exercised -- which is the failure the
    # synthetic beat already had.
    picked, per_chat = [], {}
    cap = max(1, want // 4)
    for t in rows:
        if len(picked) >= want:
            break
        if per_chat.get(t["chat_id"], 0) >= cap:
            continue
        outcome = _step(con, t["id"], "perception_outcome")
        view = ((outcome.get("views") or {}).get("player") or "")
        if len(view) < 120:
            continue
        # THE ERA GATE, and the marker is the LEDGER rather than a turn id.
        # `composer_ledger` is written by the live span projection, so its
        # presence is exactly "these observations came from the code that
        # runs today". Beats without it carry the output of a sentence
        # chunker deleted in `dbe9ffa` -- it split the model-written view on
        # full stops with no idea what a quote was, so a replayed pre-ledger
        # beat feeds the narrator fractured utterances the live engine
        # cannot produce. Measured with the partition applied: 398 of 1,418
        # delivered lines split on pre-ledger beats, 0 of 1,026 on ledger
        # ones. Absolute rates from a mixed selection are measuring a
        # retired function; an A/B still holds, because both arms see the
        # same beats.
        ledger_era = isinstance(outcome.get("composer_ledger"), dict)
        if ledger_only and not ledger_era:
            continue
        di = _step(con, t["id"], "director_interpret")
        player = player_name(con, t["chat_id"])
        srow = con.execute(
            "SELECT value FROM world WHERE chat_id=? AND key='scene'",
            (t["chat_id"],)).fetchone()
        try:
            scene = json.loads(srow[0]) if srow else {}
        except (TypeError, ValueError):
            scene = {}
        events = beat_events(con, t["id"], player, scene)
        # Same floor the engine puts on the record it hands the narrator.
        displays = speaker_displays(con, t["chat_id"], player)
        for ev in events:
            if ev["actor"] != player:
                ev["actor"] = displays.get(ev["actor"], ev["actor"])
        view_norm = re.sub(r"\s+", " ", view).casefold()
        kept = []
        for ev in events:
            if ev["kind"] == "speech" and not ev.get("declared"):
                body = re.sub(r"\s+", " ", _quote_body(ev["quote"])).casefold()
                if not body or body not in view_norm:
                    continue          # never reached the player
            kept.append(ev)
        if not any(e["kind"] == "speech" and not e.get("declared")
                   for e in kept):
            continue                  # nothing to score dialogue fidelity on
        for i, ev in enumerate(kept, 1):
            ev["n"] = i
        block, prev = past_narration(
            con, t["chat_id"], t["idx"], t["frame_id"], t["player_input"])
        block_no_tail, _ = past_narration(
            con, t["chat_id"], t["idx"], t["frame_id"], "")
        person = narration_person(con, t["chat_id"])
        per_chat[t["chat_id"]] = per_chat.get(t["chat_id"], 0) + 1
        picked.append({
            "turn_id": t["id"], "chat_id": t["chat_id"], "idx": t["idx"],
            "ledger_era": ledger_era,
            "view": view, "events": kept, "past": block, "prev": prev,
            "past_no_tail": block_no_tail,
            "player": player, "person": person,
            "observations": ((_step(con, t["id"], "perception_outcome")
                              .get("observations") or {}).get("player") or []),
            "input": t["player_input"] or "",
            "declared": _narrator_player_declared(di),
            "p_lines": [e.get("text") for e in (di.get("sequence") or [])
                        if isinstance(e, dict) and e.get("type") == "speech"
                        and e.get("text")],
        })
    return picked


def world_fields(con, beat):
    """The standing-state half of the payload, built from the stored scene.

    Without this the harness exercised roughly six of the sheet's thirty-odd
    blocks: `spatial_frame`, `portal_states`, `co_present_positions`,
    `sensory_channels`, `already_established_phrases` and `overused_phrases`
    were all absent or empty, so SPATIAL FRAME (2,824 chars and the largest
    block with no code behind it), POSITION CONTINUITY, PORTAL STATE, SENSORY
    CHANNELS, ESTABLISHED-DETAIL ECONOMY and OVERUSED PHRASES could not be
    scored at all -- a cut anywhere in them read as "no change" for want of a
    beat that tested it.
    """
    from agents.narration import (_already_established_phrases,
                                  _overused_phrases, _visible_portal_states,
                                  _sensory_channels_manifest)
    from world.spatial import room_of, spatial_digest, visible_adjacent_rooms

    row = con.execute(
        "SELECT value FROM world WHERE chat_id=? AND key='scene'",
        (beat["chat_id"],)).fetchone()
    try:
        scene = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        scene = {}
    out = {}
    if not scene:
        return out
    who = beat["player"]
    p_room = room_of(scene, who)
    digest = spatial_digest(scene, who)
    if digest:
        out["spatial_frame"] = digest
    if p_room:
        visible = {str(r["room_id"]) for r in visible_adjacent_rooms(scene, p_room)
                   if isinstance(r, dict) and r.get("room_id")} | {p_room}
        portals = _visible_portal_states(scene, p_room, visible)
        if portals:
            out["portal_states"] = portals
    positions = scene.get("positions") or {}
    rooms = scene.get("rooms") or {}
    # BODIES ONLY. `positions` keys every placed thing, so a naive pass put
    # `scranton_anchor` and a raw entity id into the payload as co-present
    # PEOPLE -- the same "a referent is not necessarily a body" defect the
    # composer's pose renderer had. Asked structurally, never by kind string.
    from world.spatial import _entities_named, _is_body_entity
    posed = {str(k).casefold() for k in (scene.get("poses") or {})}

    def is_body(name):
        if str(name).casefold() in posed:
            return True
        primary, aliased = _entities_named(scene, name)
        return any(_is_body_entity(scene, eid, ent)
                   for eid, ent in (*primary, *aliased))

    co = []
    for name, room in positions.items():
        if name == who or not isinstance(room, str):
            continue
        if p_room and room != p_room:
            continue
        if not is_body(name):
            continue
        # An ID IS NOT A NAME. The live path resolves through the observer's
        # display map; here the scene's own entity name is the equivalent,
        # and an opaque key that resolves to nothing readable is dropped
        # rather than handed to the model as a person called
        # "002663fa035048cd".
        primary, aliased = _entities_named(scene, name)
        display = next((str((ent or {}).get("name") or "").strip()
                        for _eid, ent in (*primary, *aliased)
                        if str((ent or {}).get("name") or "").strip()), "")
        if not display:
            if re.fullmatch(r"[0-9a-f]{8,}", str(name)) or "_" in str(name):
                continue
            display = str(name)
        co.append({"who": display,
                   "room": (rooms.get(room) or {}).get("name") or room,
                   "prev_room": (rooms.get(room) or {}).get("name") or room,
                   "moved": False})
    if co:
        out["co_present_positions"] = co
    senses = _sensory_channels_manifest(
        scene, who, beat["view"], beat.get("observations") or [],
        set(), {}, p_room)
    if senses:
        out["sensory_channels"] = senses
    return out


def payload_for(beat, extra=None):
    """THE SHIPPED PAYLOAD, rebuilt from stored rows.

    THIS IS THE CONTROL, and it is only worth anything while it matches what
    `agents/narration.narrator` actually sends. It did not: until 2026-08-23
    this function built the payload that was RETIRED when the three packages
    landed -- this turn's input on the tail of `past_narration` instead of in
    its own `current_narration` section, no `player_declared`, and
    `current_events` re-derived from `event_order` rather than taken from
    perception's own observations. Every arm measured against it was
    measuring its own delta plus that one, and an arm that merely undid part
    of the drift would have scored as an improvement.

    The rule this file now keeps: a transform arm is a DIFFERENCE FROM WHAT
    SHIPS. When the engine's payload changes, this function changes with it
    and the arm that introduced the change is deleted, because it has become
    the baseline and can no longer be compared against anything.
    """
    from agents.narration import (_render_observed_events,
                                  _already_established_phrases,
                                  _overused_phrases)
    established = _already_established_phrases(beat["view"], beat["prev"])
    overused = _overused_phrases(beat["prev"])
    payload = {
        "narration_person": beat["person"],
        "player_name": beat["player"],
        "player_pronouns": {},
        "cast_pronouns": beat.get("pronouns") or {},
        "player_awareness": "awake",
        "scene_opening": False,
        "player_declared": beat.get("declared") or {},
        # Absent when empty, as the engine now emits them.
        **({"overused_phrases": overused} if overused else {}),
        **({"already_established_phrases": established} if established
           else {}),
        "past_narration": beat["past_no_tail"],
        "current_narration": (beat.get("input") or "").strip(),
        "present_scene": beat["view"],
        # Perception's own record, with the player's Director-reconciled acts
        # in front of it -- `_render_observed_events`, the shipped function,
        # rather than a copy of it that can drift.
        "current_events": _render_observed_events(
            beat.get("observations") or [],
            [ev for ev in beat["events"]
             if ev.get("kind") == "action" and ev.get("actor") == beat["player"]]),
        "variant_seed": 0,
    }
    # Standing facts go in front of the packages, exactly as
    # `agents/narration.narrator` orders them.
    for key, value in (extra or {}).items():
        payload[key] = value
    return {k: payload[k] for k in PAYLOAD_ORDER if k in payload}


#: The shipped key order, and the one place it is written down for the
#: harness. `agents/narration.narrator`'s own comment explains why order is
#: load-bearing; an arm that reorders must state so by rebuilding this list.
PAYLOAD_ORDER = [
    "narration_person", "player_name", "player_pronouns", "cast_pronouns",
    "player_awareness", "private_voice_setting", "scene_opening",
    "authored_body_parts", "player_declared", "exemplars",
    "overused_phrases", "already_established_phrases",
    "spatial_frame", "co_present_positions", "portal_states",
    "sensory_channels", "past_narration", "current_narration",
    "present_scene", "current_events", "variant_seed",
]


#: PAYLOAD arms, distinct from sheet arms. Each is a transform on the built
#: payload, testing whether an instruction attached to the DATA can do the
#: work a block of the sheet is doing -- the one lever measured to work three
#: times (the per-line act marker, the ordering sentence, a prohibition
#: attached to the value it governs).
#:
#: FIVE ARMS WERE DELETED HERE on 2026-08-23, not because they lost but
#: because they WON: `split_input`, `events_perception`,
#: `events_perception_acts`, `split_input_perception` and
#: `split_perception_acts` are all now what `payload_for` builds, and an arm
#: that equals the baseline can only ever measure noise. Their measured
#: results live where the behaviour lives, in `agents/narration.py`.
def _drop(payload, *keys):
    return {k: v for k, v in payload.items() if k not in keys}


def _no_player_name(payload, beat=None):
    """In first/second person the player must never be NAMED, and
    `_check_player_person` fires enforceably if they are -- so the payload is
    sending a name whose only legal use is "never write this"."""
    if payload.get("narration_person") == "third":
        return dict(payload)
    return _drop(payload, "player_name", "player_pronouns")


def _value_prohibitions(payload, beat=None):
    """Attach each prohibition to the value it governs instead of stating it
    once in the sheet."""
    out = dict(payload)
    portals = out.get("portal_states")
    if isinstance(portals, list):
        out["portal_states"] = [
            {**p, "note": f"{p.get('state')} — never render it otherwise"}
            if isinstance(p, dict) else p for p in portals]
    co = out.get("co_present_positions")
    if isinstance(co, list):
        out["co_present_positions"] = [
            {**c, "note": ("still where they were; do not move them"
                           if not c.get("moved")
                           else "moved this beat; their arrival may be rendered")}
            if isinstance(c, dict) else c for c in co]
    return out


#: Beats on which `drop_view` kept `present_scene` rather than dropping it,
#: because a line the fidelity check will DEMAND was not carried by
#: `current_events`. Read by `main` so a run reports its own fallbacks
#: instead of silently scoring a different arm than the one named.
DROP_VIEW_FALLBACKS = []


def _drop_view(payload, beat=None):
    """`present_scene` removed -- `current_events` is already the same text.

    Measured 2026-08-23 over 370 stored `perception_outcome` steps: the
    structured observations cover 99.3% of the view's characters, and on 97%
    of turns every observation span is verbatim in the view at >=95% of its
    total length. That is not a coincidence, it is construction --
    `composer.observations_from_render` projects `rendered.spans`, the same
    spans in the same order, merged into at most `_MAX_OBSERVATION_ATOMS`
    groups. Two authorities on "what reached this mind" is the drift
    condition this repo names explicitly, and the pair had already drifted
    once (`agents/perception.py:_repaired_observations`).

    THE FALLBACK IS THE POINT, and it encodes a rule worth more than the arm:
    *the floor may only score the model against material the payload
    carried.* `_check_narrator_fidelity` scores DIALOGUE FIDELITY off the
    VIEW whether or not the view was sent, so a beat whose demanded lines
    are missing from `current_events` would be an enforceable finding the
    model could not have avoided -- a guaranteed wasted rewrite, and a
    measurement of the harness rather than the payload. On such a beat the
    view is kept and the fallback is recorded.
    """
    from agents.common import _protected_view_quotes

    events = str(payload.get("current_events") or "")
    demanded = _protected_view_quotes(beat.get("view") if beat else "",
                                      (beat or {}).get("p_lines") or [])
    carried = re.sub(r"\s+", " ", events)
    missing = [q for q in demanded
               if re.sub(r"\s+", " ", q).strip() not in carried]
    if missing:
        DROP_VIEW_FALLBACKS.append({
            "turn_id": (beat or {}).get("turn_id"),
            "missing": missing[:3],
        })
        return dict(payload)
    return _drop(payload, "present_scene")


def _channel_tags(payload, beat=None):
    """The per-sense manifest's `this_beat` replaced by a tag on each line.

    `sensory_channels.this_beat` is a third copy of the beat's percepts
    (view, observations, manifest). Moving the CHANNEL onto the line it
    describes keeps the per-sense information at the point of use, which is
    the instructions-attached-to-data lever; the statuses and the standing
    substrate stay, because a silent or degraded verdict is unique content
    nothing else carries.
    """
    out = dict(payload)
    senses = out.get("sensory_channels")
    if isinstance(senses, dict):
        out["sensory_channels"] = {
            k: (({ik: iv for ik, iv in v.items() if ik != "this_beat"}
                 if isinstance(v, dict) else v))
            for k, v in senses.items()}
    channels = []
    for obs in (beat or {}).get("observations") or []:
        # `channel` is a TOP-LEVEL key of the observation, beside
        # `observed`, not inside it -- `observations_from_render` writes it
        # from the IR. Reading it from the wrong level is silent: every line
        # simply comes back untagged and the arm measures nothing.
        ch = str((obs or {}).get("channel") or "").strip()
        channels.append(ch)
    lines, seen_obs = [], 0
    for line in str(out.get("current_events") or "").split("\n"):
        if not line.strip():
            continue
        # Only perception's own entries carry a channel; the player's acts
        # are prepended by the engine and are not percepts at all.
        if "did this (" in line or "はこれを行った" in line:
            lines.append(line)
            continue
        ch = channels[seen_obs] if seen_obs < len(channels) else ""
        seen_obs += 1
        lines.append(f"{line} [{ch}]" if ch else line)
    out["current_events"] = "\n".join(lines)
    return out


#: `beat_only` LIVED HERE and was deleted before it ever ran. It tried to
#: replay the standing/event re-filing by classifying each stored entry from
#: the beat record, because rows written before `observations_from_render`
#: carried a `standing` flag cannot be filed any other way. The dry run
#: killed it: it dropped "the unfamiliar person steps forward and removes the
#: wrist restraints" as scenery -- an NPC act the engine keeps via
#: `order_key` -- so the arm would have measured its own classifier and
#: scored the change worse than it is. Span order gives no rescue: standing
#: is a contiguous block but leads or trails depending on whether a sudden
#: event chain won the discourse rule (composer.py:1738-1742). The re-filing
#: is settled by `tests/test_composer_poses.py::TestOneEntryIsOneDelivery`
#: and by a live run once stored rows carry the flag; it is not settleable by
#: replaying rows that predate it.
PAYLOAD_ARMS = {
    "legacy_sheet": ("legacy_sheet", None),
    "no_player_name": ("full", _no_player_name),
    "lean_values": ("lean", _value_prohibitions),
    "drop_view": ("full", _drop_view),
    "channel_tags": ("full", _channel_tags),
}


def arms(names):
    from llm.prompts import get_prompt
    out = {}
    for name in names:
        if name == "full":
            out[name] = get_prompt("narrator")
            continue
        path = os.path.join(SHEETS, f"{name}.txt")
        if not os.path.exists(path):
            print(f"  no such sheet variant: {path}")
            continue
        with open(path, encoding="utf-8") as fh:
            out[name] = fh.read()
    return out


def cast_pronouns_for(con, chat_id):
    from agents.narration import _cast_pronouns
    rows = con.execute(
        "SELECT c.sheet AS sheet FROM chat_chars cc "
        "JOIN characters c ON c.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,)).fetchall()
    return _cast_pronouns([{"sheet": r["sheet"]} for r in rows])


def score(raw, beat):
    """The ENGINE's own verdict on this draft, not a bespoke one."""
    from agents.common import _check_narrator_fidelity
    from agents.narration import _craft_tells, _ling

    prose = ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            prose = parsed.get("prose") or ""
    except (TypeError, ValueError):
        prose = raw or ""
    warnings = _check_narrator_fidelity(
        {"prose": prose, "new_specifics": []}, beat["view"],
        recent_prose=beat["prev"], exclude_quotes=beat["p_lines"],
        cast_pronouns=beat.get("pronouns") or {},
        player_name=beat["player"], narration_person=beat["person"],
        event_order=beat["events"])
    enforceable = [w for w in warnings
                   if w.startswith(_ling("_ENFORCEABLE_PREFIXES"))]
    return {
        "warnings": warnings,
        "enforceable": enforceable,
        "craft_tells": _craft_tells(prose),
        "act_coverage": _act_coverage(prose, beat),
        "direction_agreement": _direction_agreement(prose, beat),
        "tag_leaks": _tag_leaks(prose),
        # CATALOGUE PROXY. One paragraph per numbered entry is what
        # transcription looks like; composing pulls the ratio away from 1.
        # Not a verdict -- a short beat legitimately runs close to it -- so
        # it is only ever read as a difference between arms.
        "entries": len([l for l in str(beat.get("_events_sent") or "").split("\n")
                        if l.strip()]),
        "chars": len(prose),
        "paragraphs": prose.count("<p>"),
        "prose": prose,
    }


#: Content words too common to prove an act reached the page. Deliberately
#: short: the metric is a COVERAGE estimate for the harness, not a warning,
#: and a long stoplist tuned against these twelve beats would be a metric
#: measuring the beats it was tuned on.
_ACT_STOPWORDS = frozenset("""
a an the and or but of to in on at by for with from into onto over under
is are was were be been being do does did doing has have had his her their
its your you they them he she it this that these those not no as up down
""".split())


def _act_coverage(prose, beat):
    """Did the player's own acts reach the page?

    THE ONE QUESTION NO FIDELITY CHECK CAN ASK. A mind is never handed its
    own conduct as a percept, so a player's act is in no view -- and every
    check here scores the prose against the VIEW. Measured: sourcing
    `current_events` from perception alone dropped player-act coverage to
    1 of 9 while every draft still scored 12/12 clean on every check. A
    payload regression in this exact place is structurally invisible, which
    is why the harness carries the metric even though production does not
    warn on it.

    Coverage is per ACT, and an act counts as covered when at least half of
    its content words appear in the prose. Not a warning and not a verdict:
    a narrator legitimately renders "he shrugs it off" for a longer written
    act, so this is a comparative number between arms, never a threshold.
    """
    acts = [ev for ev in beat.get("events") or []
            if ev.get("kind") == "action" and ev.get("actor") == beat["player"]]
    if not acts:
        return None
    text = re.sub(r"<[^>]+>", " ", prose or "").casefold()
    covered = 0
    for act in acts:
        words = [w for w in re.findall(r"[a-z']+",
                                       str(act.get("action") or "").casefold())
                 if len(w) > 2 and w not in _ACT_STOPWORDS]
        if not words:
            continue
        hits = sum(1 for w in words if w in text)
        if hits * 2 >= len(words):
            covered += 1
    return [covered, len(acts)]


def _direction_agreement(prose, beat):
    """Does an egocentric direction word in the prose match its bucket?

    `spatial_frame` is the ONLY carrier of the direction license and nothing
    deterministic backs it: the enforceable direction check reads event_order
    VERBS, not this field. So the 2.8k-character sheet block that governs it
    and the field itself have never been measured at all. This is the cheap
    harness-side start: when the prose says a room lies behind/ahead, does
    the frame agree.

    Returns [agreed, claimed] or None when the prose makes no directional
    claim about a named room -- which is most beats, and why this is a
    per-arm sum rather than a per-beat verdict.
    """
    frame = (beat.get("world") or {}).get("spatial_frame") or {}
    if not isinstance(frame, dict) or not frame:
        return None
    buckets = {}
    for bucket, rooms in frame.items():
        # ROOM BUCKETS ONLY, and each entry is a RECORD ({room, barrier,
        # bearing}) rather than a bare name. Both halves are load-bearing
        # and both failed silently on the first cut of this metric:
        # `ahead_entity` holds a STRING (the body being faced, "The
        # Doctor"), so iterating it walked the name CHARACTER BY CHARACTER
        # and every single letter matched somewhere in the prose --
        # producing 61 direction claims of which 1 agreed, a 1.6% that was
        # entirely the harness. The sheet's direction licence governs
        # rooms; a body is not one.
        if not isinstance(rooms, list):
            continue
        for room in rooms:
            name = (str(room.get("room") or "") if isinstance(room, dict)
                    else str(room or "")).strip()
            # A one- or two-character "room" is not a room. Cheap guard
            # against exactly the class above rather than against its
            # one instance.
            if len(name) >= 3:
                buckets.setdefault(name.casefold(), set()).add(str(bucket))
    if not buckets:
        return None
    text = re.sub(r"<[^>]+>", " ", prose or "").casefold()
    # An egocentric word licensed by exactly one bucket. `unclassified` is
    # deliberately absent: it licenses NO direction word, so a claim near an
    # unclassified room is a disagreement, which is the interesting half.
    words = {"behind you": "behind", "back the way": "behind",
             "ahead": "ahead", "onward": "ahead", "in front of you": "ahead",
             "above you": "above", "below you": "below",
             "to your left": "left", "to your right": "right"}
    agreed = claimed = 0
    for room, wanted in buckets.items():
        at = text.find(room)
        if at < 0:
            continue
        for phrase, bucket in words.items():
            where = text.find(phrase)
            if where < 0 or abs(where - at) >= 120:
                continue
            claimed += 1
            if bucket in wanted:
                agreed += 1
    return [agreed, claimed] if claimed else None


def _tag_leaks(prose):
    """Bracketed engine tokens on the page.

    Only meaningful for the `channel_tags` arm, and it is exactly the risk
    that arm carries: an instruction attached to the data can be COPIED
    rather than obeyed. Cheap enough to run on every arm, because a leak
    anywhere is a finding.
    """
    return re.findall(r"\[(?:sight|hearing|smell|touch|taste|interoception|"
                      r"mixed)\]", prose or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "engine.db"))
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--chats", default="", help="comma-separated chat ids")
    ap.add_argument("--arms", default="full")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--list", action="store_true",
                    help="pick the beats and print them, make no calls")
    args = ap.parse_args()

    con = _db(args.db)
    chats = [int(x) for x in args.chats.split(",") if x.strip()]
    beats = collect(con, args.turns, chats or None)
    for b in beats:
        b["world"] = world_fields(con, b)
        b["pronouns"] = cast_pronouns_for(con, b["chat_id"])
    print(f"beats selected: {len(beats)}")
    for b in beats:
        npc = sum(1 for e in b["events"]
                  if e["kind"] == "speech" and not e.get("declared"))
        acts = sum(1 for e in b["events"] if e["kind"] == "action")
        print(f"  chat {b['chat_id']:>3} turn {b['idx']:>3} "
              f"(id {b['turn_id']}): {npc} npc line(s), {acts} act(s), "
              f"view {len(b['view'])} ch, past {len(b['past'])} ch")
    if args.list or not beats:
        return

    from llm.providers import chat_complete, resolve_role
    prov, model, _cfg = resolve_role("narrator")
    print(f"\nnarrator role -> {prov['name']} / {model}")
    wanted = [a.strip() for a in args.arms.split(",") if a.strip()]
    sheet_names = [PAYLOAD_ARMS[a][0] if a in PAYLOAD_ARMS else a
                   for a in wanted]
    sheets = arms(sorted(set(sheet_names)))
    plan = []
    for name in wanted:
        sheet_key, transform = PAYLOAD_ARMS.get(name, (name, None))
        if sheet_key not in sheets:
            continue
        plan.append((name, sheets[sheet_key], transform))
        print(f"  arm {name:16} sheet {sheet_key:<13} {len(sheets[sheet_key]):>6} chars"
              f"{'  + payload transform' if transform else ''}")

    results = {}
    for name, system, transform in plan:
        rows = []
        for b in beats:
            built = payload_for(b, b.get("world"))
            if transform:
                built = transform(built, b)
            b["_events_sent"] = built.get("current_events") or ""
            user = json.dumps(built, ensure_ascii=False)
            t0 = time.monotonic()
            try:
                raw = chat_complete("narrator", system, user, json_mode=True)
            except Exception as exc:                      # noqa: BLE001
                print(f"  {name} turn {b['turn_id']}: CALL FAILED {exc}")
                continue
            row = score(raw, b)
            row["seconds"] = round(time.monotonic() - t0, 1)
            row["turn_id"] = b["turn_id"]
            row["chat_id"] = b["chat_id"]
            row["idx"] = b["idx"]
            row["player_input"] = b["input"]
            rows.append(row)
        results[name] = rows
        if rows:
            n = len(rows)
            enf = sum(len(r["enforceable"]) for r in rows)
            allw = sum(len(r["warnings"]) for r in rows)
            tells = sum(len(r["craft_tells"]) for r in rows)
            clean = sum(1 for r in rows if not r["enforceable"])
            print(f"\n{name:14} n={n}"
                  f" | clean drafts {clean}/{n}"
                  f" | ENFORCEABLE {enf} ({enf / n:.2f}/turn)"
                  f" | all warnings {allw}"
                  f" | craft tells {tells}"
                  f" | mean chars {sum(r['chars'] for r in rows) // n}")
            # THE METRICS NO CHECK CAN PRODUCE. Printed unconditionally,
            # including their denominators: an arm that silently had no
            # player acts to cover would otherwise read as a perfect score.
            acts = [r["act_coverage"] for r in rows if r["act_coverage"]]
            if acts:
                print(f"      player acts on the page: "
                      f"{sum(a[0] for a in acts)}/{sum(a[1] for a in acts)}"
                      f"  (over {len(acts)} of {n} beats that had any)")
            dirs = [r["direction_agreement"] for r in rows
                    if r["direction_agreement"]]
            if dirs:
                print(f"      egocentric direction agrees with the frame: "
                      f"{sum(d[0] for d in dirs)}/{sum(d[1] for d in dirs)}"
                      f"  (over {len(dirs)} of {n} beats that claimed one)")
            else:
                print(f"      egocentric direction: no beat claimed one "
                      f"-- spatial_frame unexercised in this selection")
            ents = sum(r.get("entries") or 0 for r in rows)
            paras = sum(r["paragraphs"] for r in rows)
            print(f"      entries sent {ents}, paragraphs written {paras} "
                  f"(ratio {paras / max(1, ents):.2f} — 1.00 is transcription)")
            leaks = sum(len(r["tag_leaks"]) for r in rows)
            if leaks:
                print(f"      ENGINE TAGS COPIED ONTO THE PAGE: {leaks}")
            if name in PAYLOAD_ARMS and name == "drop_view" \
                    and DROP_VIEW_FALLBACKS:
                print(f"      present_scene KEPT on "
                      f"{len(DROP_VIEW_FALLBACKS)} beat(s): a demanded line "
                      f"was not carried by current_events")
            kinds = {}
            for r in rows:
                for w in r["warnings"]:
                    k = w.split(":")[0].split("(")[0].strip()[:52]
                    kinds[k] = kinds.get(k, 0) + 1
            for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
                print(f"      {v:>3}  {k}")
            if args.show:
                print("   sample:", repr(rows[0]["prose"][:400]))

    out = os.path.join(ROOT, "tools", "narrator_sheet_bench_last.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({k: [{kk: vv for kk, vv in r.items()} for r in v]
                   for k, v in results.items()}, fh, indent=1,
                  ensure_ascii=False)
    print(f"\nfull output -> {out}")


if __name__ == "__main__":
    main()
