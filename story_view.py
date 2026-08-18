"""Read-only projections of a story, for code outside the pipeline.

Two reads, and the difference between them is the whole design.

`story_view` is CANONICAL: what is objectively true of the story right now.
That is not a firewall breach, and saying so is worth the sentence, because the
instinct in this repo is that everything is. The firewall constrains what
reaches a fictional MIND. A campaign layer, an authoring tool and a debugging
panel are not minds; they are the same class of reader as `docs/CODE_MAP.md`
and the pipeline inspector, and the ruling is already written down in
`docs/design/EXTENSIONS_DESIGN.md` §1.

`player_view` is what one PERSON in the story may be shown, and it is a
security boundary rather than a convenience. It is built, deliberately, out of
what the engine ALREADY DELIVERED to that viewer -- the perception step's own
rendered view and the structured observations re-derived from it, the viewer's
own memories, their own relationships, the identity ledger's own answer about
who they can name. Nothing here re-decides admission. Re-deriving "what does
this persona know" from the objective scene would create a second authority
that agrees with `agents/perception.py` on the day it is written and drifts
from it forever after, and the drift would be invisible: a projection is not
narrated, so nobody would ever read the leak.

What is absent is absent. A field this cannot answer is OMITTED rather than
defaulted, because a default is a guess, and a guess about what someone knows
is exactly the failure this boundary exists to prevent.

Provenance uses the vocabulary the engine already speaks --
`what_i_experienced` / `what_i_was_told` / `what_i_concluded`, from
`memory.provenance_context_label` -- rather than a second one invented here.
"""

from __future__ import annotations

import json

from db import q, wget

#: Bump when a consumer could break. Callers are outside this repository and
#: cannot be migrated in the same commit, which is the whole reason a read this
#: shape carries a version at all.
STORY_VIEW_SCHEMA = 1

#: How many committed world events a view carries by default. Bounded because
#: this is a per-render read from a UI, and an unbounded history turns a panel
#: refresh into a table scan of the whole story.
DEFAULT_EVENT_LIMIT = 20
MAX_EVENT_LIMIT = 200


def _json(value, fallback):
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _chat_row(chat_id):
    return q("SELECT * FROM chats WHERE id=?", (int(chat_id),), one=True)


def latest_turn(chat_id, frame_id=None):
    """The newest committed turn, in one frame or across the story.

    `frame_id=None` means "whatever frame the story is actually on", which is
    what a caller outside the pipeline wants: `db.active_frame_id` is a
    ContextVar set for the duration of a turn, so a route reading it gets the
    default and not the answer.
    """
    if frame_id is None:
        return q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
                 (int(chat_id),), one=True)
    return q("SELECT * FROM turns WHERE chat_id=? AND frame_id IS ? "
             "ORDER BY idx DESC LIMIT 1", (int(chat_id), frame_id), one=True)


def _frame_of(turn):
    if not turn or turn["frame_id"] is None:
        return None
    row = q("SELECT * FROM frames WHERE id=?", (turn["frame_id"],), one=True)
    if not row:
        return None
    return {"id": row["id"], "label": row["label"], "ordinal": row["ordinal"],
            "kind": row["kind"]}


def _step_content(turn_id, key):
    """The active variant of one step, or `None`.

    `agents.storage.active_content` is the same read and is not used: it lives
    behind the pipeline's import graph, and this module is imported by routes
    that must not pull the agent runtime in to answer a panel refresh.
    """
    row = q("SELECT v.content FROM steps s JOIN variants v "
            "ON v.step_id=s.id AND v.active=1 "
            "WHERE s.turn_id=? AND s.key=? ORDER BY s.ord DESC LIMIT 1",
            (turn_id, key), one=True)
    if not row:
        return None
    try:
        content = json.loads(row["content"])
    except (TypeError, ValueError):
        return None
    return content if isinstance(content, dict) else None


def _cast(chat_id):
    """Attached characters with their STABLE ids.

    The id is the contract: a UI selection keyed on a display name breaks the
    first time somebody is renamed, and people in this engine are renamed by
    the story itself (a stranger becomes a name), not only by an author.
    """
    from character_schema import character_name_from_text

    rows = q("SELECT cc.char_id, cc.status, cc.sheet AS chat_sheet, "
             "c.sheet AS base_sheet FROM chat_chars cc "
             "JOIN characters c ON c.id=cc.char_id "
             "WHERE cc.chat_id=? ORDER BY cc.char_id", (int(chat_id),))
    cast = []
    for row in rows:
        sheet = row["chat_sheet"] or row["base_sheet"] or "{}"
        cast.append({"char_id": row["char_id"], "status": row["status"],
                     "name": character_name_from_text(sheet)})
    return cast


def _rooms(chat_id):
    """The cross-frame room ledger -- identity and retirement, not contents.

    `room_registry` rather than the scene's `rooms`, because the question a
    campaign asks ("does this place exist, and is it still real") is the
    registry's question. The scene answers what is in a room right now, and it
    is carried separately under `scene`.
    """
    rows = q("SELECT room_uid, name, aliases, retired_turn_id FROM room_registry "
             "WHERE chat_id=? ORDER BY room_uid", (int(chat_id),))
    return [{"room_uid": row["room_uid"], "name": row["name"],
             "aliases": _json(row["aliases"], []),
             "retired": row["retired_turn_id"] is not None}
            for row in rows]


def _events(chat_id, limit):
    rows = q("SELECT event_id, kind, location_id, occurred_at, turn_id, payload "
             "FROM world_events WHERE chat_id=? "
             "ORDER BY occurred_at DESC, rowid DESC LIMIT ?",
             (int(chat_id), int(limit)))
    return [{"event_id": row["event_id"], "kind": row["kind"],
             "location_id": row["location_id"],
             "occurred_at": row["occurred_at"], "turn_id": row["turn_id"],
             "payload": _json(row["payload"], {})}
            for row in reversed(rows)]


def story_view(chat_id, *, events=DEFAULT_EVENT_LIMIT):
    """Canonical story state, versioned, read-only, serialisable.

    Ordinary values throughout: no ORM rows, no live scene dict, no mutation
    handle. A caller that receives the engine's own objects inherits every
    future change to them, which is the thing a facade exists to prevent.
    """
    chat_id = int(chat_id)
    chat = _chat_row(chat_id)
    if not chat:
        raise ValueError(f"no chat {chat_id}")

    from scene import get_scene, player_authority, simulation_clock

    turn = latest_turn(chat_id)
    scene = get_scene(chat_id, chat) or {}
    try:
        limit = max(0, min(MAX_EVENT_LIMIT, int(events)))
    except (TypeError, ValueError):
        limit = DEFAULT_EVENT_LIMIT

    persona = q("SELECT p.id, p.name FROM personas p JOIN chats c "
                "ON c.persona_id=p.id WHERE c.id=?", (chat_id,), one=True)

    view = {
        "schema": STORY_VIEW_SCHEMA,
        "story": {
            "chat_id": chat_id,
            "name": chat["name"],
            "scenario": chat["scenario"],
            "branched_from": _json(chat["branched_from"], []),
        },
        "frame": _frame_of(turn),
        "turn": ({"id": turn["id"], "idx": turn["idx"],
                  "player_input": turn["player_input"]} if turn else None),
        "clock": simulation_clock(chat_id),
        "scene": {
            "location": scene.get("location"),
            "time": scene.get("time"),
            "rooms": scene.get("rooms") or {},
            "positions": scene.get("positions") or {},
            "entities": scene.get("entities") or {},
        },
        "rooms": _rooms(chat_id),
        "cast": _cast(chat_id),
        "events": _events(chat_id, limit),
        "player_authority": player_authority(chat_id),
    }
    if persona:
        view["player"] = {"persona_id": persona["id"], "name": persona["name"]}
    return view


# ------------------------------------------------------------ player-safe


def viewers(chat_id):
    """Who this story can be projected for, as `{id, name, kind}`.

    The ids are perception's own view keys -- `"player"`, `"extra:<persona>"`,
    and a character's numeric id -- so a caller never has to guess the spelling
    of the thing it is about to ask for.
    """
    chat_id = int(chat_id)
    out = []
    persona = q("SELECT p.id, p.name FROM personas p JOIN chats c "
                "ON c.persona_id=p.id WHERE c.id=?", (chat_id,), one=True)
    if persona:
        out.append({"id": "player", "name": persona["name"], "kind": "player"})
    for row in q("SELECT cp.persona_id, p.name FROM chat_personas cp "
                 "JOIN personas p ON p.id=cp.persona_id WHERE cp.chat_id=? "
                 "ORDER BY cp.persona_id", (chat_id,)):
        out.append({"id": f"extra:{row['persona_id']}", "name": row["name"],
                    "kind": "player"})
    for member in _cast(chat_id):
        out.append({"id": str(member["char_id"]), "name": member["name"],
                    "kind": "character"})
    return out


def _delivered(turn_id, viewer_id):
    """The last view and observations the engine DELIVERED to this viewer.

    Outcome before act: `perception_outcome` is what the viewer was left
    holding at the end of the beat, and `perception_act` is a mid-beat state
    that a later stage may have corrected. A projection showing the earlier one
    is showing something the story no longer says.
    """
    for key in ("perception_outcome", "perception_act", "perception_establish"):
        content = _step_content(turn_id, key)
        if not content:
            continue
        views = content.get("views")
        observations = content.get("observations")
        text = (views or {}).get(viewer_id) if isinstance(views, dict) else None
        if not text:
            continue
        return {
            "stage": key,
            "view": text,
            "observations": (observations or {}).get(viewer_id)
            if isinstance(observations, dict) else None,
        }
    return None


def _viewer_identity(chat_id, viewer_id):
    """Resolve a viewer id to a name, or `None` if it names nobody here."""
    for entry in viewers(chat_id):
        if entry["id"] == str(viewer_id):
            return entry
    return None


def _viewer_memories(chat_id, char_id, limit):
    """This character's own memories, newest last, with their provenance.

    Their OWN: `char_id` is the whole filter, and it is the same filter the
    character's payload is built with. A memory bank is per mind by
    construction, so this cannot leak sideways -- there is no query here that
    could return another mind's row.
    """
    from memory import provenance_context_label

    rows = q("SELECT turn_idx, kind, category, provenance, gist, content, "
             "salience, confidence FROM memories "
             "WHERE chat_id=? AND char_id=? AND archived=0 "
             "ORDER BY turn_idx DESC, id DESC LIMIT ?",
             (int(chat_id), int(char_id), int(limit)))
    return [{"turn_idx": row["turn_idx"], "kind": row["kind"],
             "category": row["category"],
             "epistemic_origin": provenance_context_label(row["provenance"]),
             "gist": row["gist"] or row["content"],
             "salience": row["salience"], "confidence": row["confidence"]}
            for row in reversed(rows)]


def player_view(chat_id, viewer="player", *, memories=12):
    """What this viewer may be shown. A security boundary, not a convenience.

    Every section is something the engine already decided this viewer has:

      * `view` / `observations` -- the perception stage's own output for them,
        which is the firewall's answer rather than a second opinion about it;
      * `knows` -- the identity ledger's list of who they can name. A body they
        can see but not name is in `observations` under whatever label the
        composer gave it, and is NOT resolved here;
      * `memories` and `relationships` -- their own, by construction;
      * `location` -- where their own body is, which a body always knows.

    Anything this cannot answer is missing from the result. There is no
    "unknown" filler and no default, because a UI cannot tell a guess from a
    fact and would render both the same way.
    """
    chat_id = int(chat_id)
    identity = _viewer_identity(chat_id, viewer)
    if identity is None:
        raise ValueError(f"no viewer {viewer!r} in chat {chat_id}")

    from scene import get_scene, simulation_clock
    from spatial import room_of

    turn = latest_turn(chat_id)
    scene = get_scene(chat_id) or {}
    name = identity["name"]

    view = {
        "schema": STORY_VIEW_SCHEMA,
        "viewer": dict(identity),
        "story": {"chat_id": chat_id},
        "turn": ({"id": turn["id"], "idx": turn["idx"]} if turn else None),
        "clock": simulation_clock(chat_id),
    }

    room_id = room_of(scene, name)
    if room_id:
        room = (scene.get("rooms") or {}).get(room_id) or {}
        view["location"] = {"room_id": room_id,
                            "name": room.get("name") or room_id}

    delivered = _delivered(turn["id"], identity["id"]) if turn else None
    if delivered:
        view["perception"] = delivered

    known = (wget(chat_id, "known", {}) or {}).get(name)
    if known:
        view["knows"] = sorted(str(item) for item in known)

    if identity["kind"] == "character":
        char_id = int(identity["id"])
        state = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
                  (chat_id, char_id), one=True)
        stored = _json(state["state"], {}) if state else {}
        relationships = stored.get("relationships")
        if isinstance(relationships, dict) and relationships:
            view["relationships"] = relationships
        remembered = _viewer_memories(chat_id, char_id, memories)
        if remembered:
            view["memories"] = remembered
    return view
