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
#:
#: 2: `player_view` carries `people`. Additive, but bumped anyway, because
#: under "absent means absent" an omitted `people` key must be readable as
#: "nobody this viewer can be shown" -- and on schema 1 the same absence means
#: "not supported". A version is the only thing that lets a consumer tell a
#: silent engine from an empty roster.
STORY_VIEW_SCHEMA = 2

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


#: Provenance marker for a fact that is public because an AUTHOR made it so
#: (a card's visible appearance, its public history) rather than because this
#: viewer acquired it. The acquisition labels stay `memory.
#: provenance_context_label`'s own -- `what_i_experienced` / `what_i_was_told`
#: / `what_i_concluded` -- and are not re-invented here; this is the one case
#: that vocabulary cannot name, because authored-public facts were never
#: acquired by anyone.
AUTHORED_PUBLIC = "authored_public"


def _delivered_company(turn_id, viewer_id):
    """The perception stage's own record of who this viewer's view was
    composed about, under the labels the viewer earned.

    Written by the composer stages beside `views`/`observations`
    (`agents/perception.py`'s `_composer_company`), from the same admitted
    percepts the view renders from -- so reading it back cannot list a body
    the delivered view did not carry. `None` when no stage recorded one for
    this viewer (older stories predate the record; absent stays absent).
    """
    for key in ("perception_outcome", "perception_act", "perception_establish"):
        content = _step_content(turn_id, key)
        if not content:
            continue
        company = content.get("company")
        if isinstance(company, dict) and viewer_id in company:
            entries = company.get(viewer_id)
            return entries if isinstance(entries, list) else None
    return None


def _public_facts(chat_id, entry):
    """The allowlisted authored-public facts of one cast member or persona.

    Two fields, both defensible as PUBLIC by the card's own structure:
    `embodiment.visible.summary` is the body's stable outward appearance --
    the card's own claim about what anyone who looks receives -- and
    `knowledge.public_history` is public by name. Nothing else on a card
    qualifies: psychology, private history, goals and relationships are the
    other side of the firewall, and this engine has no rank, role or
    assignment vocabulary to expose, so none is invented here.
    """
    from character_schema import normalize_character_data, normalize_persona_data

    if entry["kind"] == "character":
        row = q("SELECT cc.sheet AS chat_sheet, c.sheet AS base_sheet "
                "FROM chat_chars cc JOIN characters c ON c.id=cc.char_id "
                "WHERE cc.chat_id=? AND cc.char_id=?",
                (int(chat_id), int(entry["id"])), one=True)
        if not row:
            return {}, {}
        data = normalize_character_data(
            _json(row["chat_sheet"] or row["base_sheet"], {}))
    else:
        if entry["id"] == "player":
            row = q("SELECT p.sheet FROM personas p JOIN chats c "
                    "ON c.persona_id=p.id WHERE c.id=?", (int(chat_id),),
                    one=True)
        else:
            row = q("SELECT sheet FROM personas WHERE id=?",
                    (int(str(entry["id"]).split(":", 1)[1]),), one=True)
        if not row:
            return {}, {}
        data = normalize_persona_data(_json(row["sheet"], {}))

    facts, sources = {}, {}
    appearance = str(((data.get("embodiment") or {}).get("visible") or {})
                     .get("summary") or "").strip()
    if appearance:
        facts["appearance"] = appearance
        sources["appearance"] = AUTHORED_PUBLIC
    history = str((data.get("knowledge") or {})
                  .get("public_history") or "").strip()
    if history:
        facts["public_history"] = history
        sources["public_history"] = AUTHORED_PUBLIC
    return facts, sources


def _recognized_person(chat_id, entry):
    person = {"id": entry["id"], "kind": entry["kind"],
              "display_name": entry["name"],
              "identity_status": "recognized"}
    facts, sources = _public_facts(chat_id, entry)
    if facts:
        person["facts"] = facts
        person["fact_sources"] = sources
    return person


def _people(chat_id, identity, turn):
    """The structured people projection for one viewer. Ledgers only.

    Two admissions, and NEITHER is decided here:

      * `recognized` -- the identity ledger's own answer about who this
        viewer can name, the same read `knows` is, joined to the stable ids
        `viewers()` already speaks. A known name that resolves to no cast
        member or persona has no stable id to key a UI on and is omitted.
      * `observed` -- the perception stage's own per-beat record of the
        bodies this viewer's delivered view was composed about
        (`_delivered_company`). An unrecognised body appears under the label
        the composer gave it and an opaque `body:` key, never its canonical
        name or canonical id: the recognition verdict is the COMPOSER's, not
        re-derived from the ledger, because a disguise that conceals identity
        makes a well-known name a stranger, and a ledger re-check here would
        undo the disguise. For the same reason the two entries of a disguised
        acquaintance -- the name known, the body observed -- deliberately do
        not join.

    A person in both (recognised and delivered this beat) is one entry with
    `last_observed_turn`; a person in neither is absent, which is the
    acceptance test that matters most: this function has no opinion of its
    own about who exists.
    """
    people = {}
    known = (wget(chat_id, "known", {}) or {}).get(identity["name"]) or []
    roster = {entry["name"]: entry for entry in viewers(chat_id)}
    for name in sorted(str(item) for item in known):
        entry = roster.get(name)
        if not entry or entry["id"] == identity["id"]:
            continue
        people[entry["id"]] = _recognized_person(chat_id, entry)
    delivered = _delivered_company(turn["id"], identity["id"]) if turn else None
    for body in delivered or []:
        if not isinstance(body, dict):
            continue
        label = str(body.get("label") or "")
        if body.get("recognized"):
            entry = roster.get(str(body.get("name") or ""))
            if not entry or entry["id"] == identity["id"]:
                continue
            person = people.get(entry["id"]) \
                or _recognized_person(chat_id, entry)
            person["last_observed_turn"] = turn["idx"]
            people[entry["id"]] = person
            continue
        key = str(body.get("key") or "")
        if not key or not label:
            continue
        pid = f"body:{key}"
        people[pid] = {"id": pid, "kind": "presence", "display_name": label,
                       "identity_status": "observed",
                       "last_observed_turn": turn["idx"]}
    return sorted(people.values(),
                  key=lambda person: (person["identity_status"] != "recognized",
                                      person["display_name"].casefold(),
                                      person["id"]))


def player_view(chat_id, viewer="player", *, memories=12):
    """What this viewer may be shown. A security boundary, not a convenience.

    Every section is something the engine already decided this viewer has:

      * `view` / `observations` -- the perception stage's own output for them,
        which is the firewall's answer rather than a second opinion about it;
      * `knows` -- the identity ledger's list of who they can name. A body they
        can see but not name is in `observations` under whatever label the
        composer gave it, and is NOT resolved here;
      * `people` -- the same two ledgers joined into a structured roster with
        STABLE ids (`_people`): the identity ledger's names carrying the ids
        `viewers()` already speaks, plus the perception stage's own per-beat
        record of observed bodies under composer labels and opaque `body:`
        keys. A rename changes `display_name` and never `id`; a stranger's
        canonical name and canonical id appear nowhere;
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

    people = _people(chat_id, identity, turn)
    if people:
        view["people"] = people

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
