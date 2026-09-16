"""The opening plan: what the Story Planner may do before the first beat, and
where it leaves the answer (`docs/design/DESIGN_OPENING_PLAN.md`).

The runner lives beside the planner (`agents/story_planner.run_opening_plan`);
this module holds the STATE -- the capability set, the mandate the engine
mints for the step, the two world rows, and the reader the establish stage
uses -- so that the launches, the planner and the Director all read one
definition of what the opening plan is.
"""

from __future__ import annotations

import time

from core.db import wget_for_frame, wset_for_frame

#: The world row the launch writes once, whatever happened: {published,
#: calls, steps, stopped, notes, placements, error, at}. A story with no row
#: was opened before the step existed, or by a launch that skipped it.
OPENING_PLAN_KEY = "opening_plan"

#: `{name: {room, at?}}` -- where the plan put each present body, written by
#: `plot_packages.place_at_opening` when the package publishes and read by
#: `director_establish`. The establish stage places the body there; the row
#: is inert after turn 0.
OPENING_PLACEMENTS_KEY = "opening_placements"

#: WHAT THE OPENING MAY DO, AND NOTHING ELSE (owner, 2026-09-16). Rooms, a
#: placement per present body, and a note saying what the plan means. No
#: `request_location`: a charter is an option the player takes, never one the
#: planner assumes. No `plan_entity`: the cast exists and background people
#: are the establish stage's. No `create_people`, no `presimulate`.
OPENING_CAPABILITIES = ("plan_rooms", "place_at_opening", "director_note")

#: The sentence the mandate keeps. Engine-minted, so it is worded as the
#: standing rule it is rather than as something the player typed.
OPENING_MANDATE_TEXT = ("The opening is planned before the first beat: the "
                        "rooms the passage needs, and where each present "
                        "body stands.")
OPENING_MANDATE_SCOPE = "the opening"

#: The spend the step may make. Cited to the planner as its own budget; the
#: loop's ceilings in `agents/story_planner` are safety above this.
OPENING_CALLS_PER_REPLY = 40


def mint_opening_mandate(cid, frame_id=None):
    """Grant the opening its standing mandate, expiring with turn 0.

    Idempotent through `grant_mandate`'s own rule that one sentence in one
    scope is one grant, so a retried launch does not stack rows."""
    from story.mandates import grant_mandate

    return grant_mandate(
        cid, frame_id, text=OPENING_MANDATE_TEXT,
        scope=OPENING_MANDATE_SCOPE,
        capabilities=list(OPENING_CAPABILITIES),
        limits={"calls_per_reply": OPENING_CALLS_PER_REPLY},
        expires_turn=0, turn_idx=-1)


def opening_placements(cid, frame_id=None):
    """`{name: {room, at}}` as the plan left it, or {}."""
    stored = wget_for_frame(cid, OPENING_PLACEMENTS_KEY, frame_id, {}) or {}
    out = {}
    for name, entry in (stored.items() if isinstance(stored, dict) else ()):
        if not isinstance(entry, dict) or not str(entry.get("room") or ""):
            continue
        out[str(name)] = {"room": str(entry["room"]),
                          "at": str(entry.get("at") or "")}
    return out


def record_placement(cid, frame_id, who, room, at=""):
    """One body's opening room, merged onto the row. The last word wins, so a
    package that places a body twice stands by its later operation."""
    stored = wget_for_frame(cid, OPENING_PLACEMENTS_KEY, frame_id, {}) or {}
    stored = dict(stored) if isinstance(stored, dict) else {}
    stored[str(who)] = {"room": str(room), "at": str(at or "")}
    wset_for_frame(cid, OPENING_PLACEMENTS_KEY, stored, frame_id)
    return stored[str(who)]


def opening_plan_record(cid, frame_id=None):
    return wget_for_frame(cid, OPENING_PLAN_KEY, frame_id, {}) or {}


def record_opening_plan(cid, frame_id, **fields):
    """Write the one row the launch leaves behind. Every launch writes it,
    including one whose plan failed, so a story can always say whether it
    was planned and why not."""
    row = {"at": time.time(), **fields}
    row["placements"] = opening_placements(cid, frame_id)
    wset_for_frame(cid, OPENING_PLAN_KEY, row, frame_id)
    return row


def present_bodies(cid):
    """The names the opening may place: the persona and the attached cast."""
    from story.plot_packages import reserved_identities
    from story.scene import persona_name, persona_of
    from core.db import q

    names = []
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if chat:
        try:
            player = persona_name(persona_of(dict(chat)))
        except Exception:
            player = ""
        if player:
            names.append(str(player))
    for row in reserved_identities(cid)["cast"]:
        if row.get("name") and str(row["name"]) not in names:
            names.append(str(row["name"]))
    return names
