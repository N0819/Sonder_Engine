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

import hashlib
import json
import secrets

from core.db import q, wget, wset

#: Bump when a consumer could break. Callers are outside this repository and
#: cannot be migrated in the same commit, which is the whole reason a read this
#: shape carries a version at all.
#:
#: 2: `player_view` carries `people`. Additive, but bumped anyway, because
#: under "absent means absent" an omitted `people` key must be readable as
#: "nobody this viewer can be shown" -- and on schema 1 the same absence means
#: "not supported". A version is the only thing that lets a consumer tell a
#: silent engine from an empty roster.
#:
#: 3: every anonymous `body:` id is re-keyed. Schema 2 derived it from a hash
#: of the body's canonical NAME (`composer.body_key`), which changed when the
#: person was renamed and was identical across viewers -- a correlation key.
#: Schema 3 derives it from the person's immutable identity, namespaced per
#: story and per viewer (`_viewer_presence_id`). A consumer that stored
#: schema-2 ids for continuity will see every anonymous id change exactly
#: once, which is a break worth a version: silence would look like every
#: stranger in the story being replaced.
STORY_VIEW_SCHEMA = 3

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
    from story.character_schema import character_name_from_text

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

    from story.scene import get_scene, player_authority, simulation_clock

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


def _persona_sheet_name(sheet):
    """An extra player's identity name, from their sheet. Same rule as the
    primary persona -- `story/scene.py` seeds them under `persona_name(sheet)`
    too, so that is the key the scene and the ledger will answer to."""
    from story.character_schema import persona_name

    try:
        parsed = json.loads(sheet or "{}")
    except (TypeError, ValueError):
        return ""
    if not isinstance(parsed, dict):
        return ""
    return persona_name(parsed) or ""


def viewers(chat_id):
    """Who this story can be projected for, as `{id, name, kind}`.

    The ids are perception's own view keys -- `"player"`, `"extra:<persona>"`,
    and a character's numeric id -- so a caller never has to guess the spelling
    of the thing it is about to ask for.
    """
    from story.character_schema import persona_name
    from story.scene import persona_of

    chat_id = int(chat_id)
    out = []
    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if chat:
        # The name here is a JOIN KEY, not a label: `known` and the scene's
        # `positions` are both keyed by the sheet's identity name. The
        # denormalised `personas.name` column is a copy taken at insert time
        # and free to diverge from the sheet forever after -- where it has,
        # every lookup keyed on it misses silently and reads as "recognises
        # nobody" rather than as a miss. `persona_of` also answers for a chat
        # with no persona attached, with the same "The Stranger" the scene is
        # seeded under; emitting nothing there made this the only reader in
        # the engine that cannot see the default player.
        out.append({"id": "player",
                    "name": persona_name(persona_of(dict(chat))),
                    "kind": "player"})
    for row in q("SELECT cp.persona_id, p.name, p.sheet FROM chat_personas cp "
                 "JOIN personas p ON p.id=cp.persona_id WHERE cp.chat_id=? "
                 "ORDER BY cp.persona_id", (chat_id,)):
        out.append({"id": f"extra:{row['persona_id']}",
                    "name": _persona_sheet_name(row["sheet"]) or row["name"],
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
    from mind.memory import provenance_context_label

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
    from story.character_schema import normalize_character_data, normalize_persona_data

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


#: World key holding this story's presence-id namespace: random hex minted
#: once and never serialised into any projection. It exists because every
#: OTHER input to an anonymous id is canonical data a `story_view` caller can
#: read for itself -- a derivative computed only from canonical values is
#: invertible by enumeration no matter how it is hashed, and "cannot confirm
#: a guessed identity" is the property the id is for. Deliberately NOT in
#: `db.FRAME_SCOPED_WORLD_KEYS`: an unidentified person is the same person
#: in every era, so their per-viewer continuity must span frames the way the
#: person does. As a plain world row it rides checkpoints, archives and
#: branches with no carriage code of its own -- the same argument as
#: `api.documents`.
PRESENCE_NAMESPACE_KEY = "presence_id_namespace"


def _presence_namespace(chat_id):
    """This story's secret presence-id namespace, minted on first need.

    The one write in this read-only module, and it writes no story state: a
    nonce is bookkeeping for the projection itself, like a session id. Minted
    lazily rather than at chat creation so every existing story gains one the
    first time an anonymous body is projected, with no migration. The
    read-after-write is for two concurrent first calls: both re-read, so both
    return whichever mint won rather than each keeping its own loser.
    """
    namespace = wget(chat_id, PRESENCE_NAMESPACE_KEY)
    if isinstance(namespace, str) and namespace:
        return namespace
    wset(chat_id, PRESENCE_NAMESPACE_KEY, secrets.token_hex(16))
    return wget(chat_id, PRESENCE_NAMESPACE_KEY)


def _person_refs(chat_id):
    """Each roster id's IMMUTABLE identity ref -- the hash input that keeps a
    viewer-scoped presence id still while every label around it moves.

    Internal only, never serialised: a ref is (or contains) the card's own
    uid, which an unrecognising viewer has not earned. Cast refs come from
    `character_schema.cast_entity_id` -- the one id-shaped spelling a cast
    member is already live under, reading the RAW sheet because normalization
    mints a fresh uid per call for a uid-less sheet (its docstring carries the
    argument). Personas get the mirror-image read for the mirror-image
    reason, with `persona:<row id>` as the stable fallback.
    """
    from story.character_schema import cast_entity_id

    def persona_ref(row):
        sheet = _json(row["sheet"], {})
        identity = sheet.get("identity") if isinstance(sheet, dict) else None
        uid = (identity or {}).get("uid")
        return str(uid or f"persona:{int(row['id'])}")

    refs = {}
    persona = q("SELECT p.id, p.sheet FROM personas p JOIN chats c "
                "ON c.persona_id=p.id WHERE c.id=?", (int(chat_id),), one=True)
    if persona:
        refs["player"] = persona_ref(persona)
    for row in q("SELECT p.id, p.sheet FROM chat_personas cp "
                 "JOIN personas p ON p.id=cp.persona_id WHERE cp.chat_id=? "
                 "ORDER BY cp.persona_id", (int(chat_id),)):
        refs[f"extra:{row['id']}"] = persona_ref(row)
    for row in q("SELECT cc.char_id, cc.sheet AS chat_sheet, "
                 "c.sheet AS base_sheet FROM chat_chars cc "
                 "JOIN characters c ON c.id=cc.char_id WHERE cc.chat_id=?",
                 (int(chat_id),)):
        refs[str(row["char_id"])] = cast_entity_id(
            _json(row["chat_sheet"] or row["base_sheet"], {}), row["char_id"])
    return refs


def _presence_ref(name, key, by_name, refs):
    """The most durable identity the engine holds for one delivered body.

    Best case the canonical name resolves to exactly one roster member and
    the ref is that person's immutable id -- a rename then moves the name,
    not the person. A name shared by several roster members cannot pick one
    (and the scene, which keys bodies by name, cannot have delivered two of
    them at once), so it degrades to the name itself -- which is also the
    honest ref for an unregistered background presence, whose tracked name
    IS its identity in this engine: `commit._fold_duplicate_presences` keys
    one record per body under its first-seen spelling and folds every later
    spelling into it. The composer's own opaque key is the last resort, for
    a record that carried no name at all.
    """
    entries = by_name.get(name) or []
    if len(entries) == 1:
        ref = refs.get(entries[0]["id"])
        if ref:
            return ref
    if name:
        return "name:" + name.strip().casefold()
    if key:
        return "record:" + key
    return None


def _viewer_presence_id(namespace, viewer_id, ref):
    """Viewer-scoped opaque id for a body this viewer cannot name.

    Stable for THIS viewer across encounters and label changes, because the
    inputs are all identity-stable: the story's secret namespace, the
    viewer's own stable id, and the immutable ref. Useless for anything
    else, by construction: the viewer id in the input means two viewers'
    projections of one person never share an id (no cross-viewer join), and
    the secret namespace means the hash cannot be inverted or confirmed by
    a caller enumerating canonical ids -- which any `story_view` caller
    could otherwise do, since every non-secret input here is canonical data
    that read already exposes.
    """
    digest = hashlib.sha1("\x1f".join(
        ("story_view.presence", str(namespace), str(viewer_id), str(ref))
    ).encode("utf-8")).hexdigest()[:12]
    return f"body:{digest}"


def _people(chat_id, identity, turn):
    """The structured people projection for one viewer. Ledgers only.

    Two admissions, and NEITHER is decided here:

      * `recognized` -- the identity ledger's own answer about who this
        viewer can name, the same read `knows` is, joined to the stable ids
        `viewers()` already speaks. The ledger speaks NAMES and a name is a
        label, not an identity, so the join is name-to-entries rather than
        name-to-entry: every roster member bearing a granted name is a
        distinct person with their own id and their own facts (two people
        may legitimately share a name -- a transporter duplicate shares
        everything at the moment of duplication). A known name that resolves
        to no cast member or persona has no stable id to key a UI on and is
        omitted.
      * `observed` -- the perception stage's own per-beat record of the
        bodies this viewer's delivered view was composed about
        (`_delivered_company`). An unrecognised body appears under the label
        the composer gave it and an opaque viewer-scoped `body:` key
        (`_viewer_presence_id`), never its canonical name or canonical id:
        the recognition verdict is the COMPOSER's, not re-derived from the
        ledger, because a disguise that conceals identity makes a well-known
        name a stranger, and a ledger re-check here would undo the disguise.
        For the same reason the two entries of a disguised acquaintance --
        the name known, the body observed -- deliberately do not join.

    A person in both (recognised and delivered this beat) is one entry with
    `last_observed_turn`; a delivered name that several roster members share
    dates NOBODY, because a date this cannot attribute to one person is a
    guess (absent means absent, applied to a field); a person in neither is
    wholly absent, which is the acceptance test that matters most: this
    function has no opinion of its own about who exists.
    """
    people = {}
    known = (wget(chat_id, "known", {}) or {}).get(identity["name"]) or []
    by_name = {}
    for entry in viewers(chat_id):
        by_name.setdefault(entry["name"], []).append(entry)
    for name in sorted(str(item) for item in known):
        for entry in by_name.get(name) or []:
            if entry["id"] == identity["id"]:
                continue
            people[entry["id"]] = _recognized_person(chat_id, entry)
    delivered = _delivered_company(turn["id"], identity["id"]) if turn else None
    refs = _person_refs(chat_id) if delivered else {}
    namespace = None
    for body in delivered or []:
        if not isinstance(body, dict):
            continue
        label = str(body.get("label") or "")
        name = str(body.get("name") or "")
        if body.get("recognized"):
            entries = [entry for entry in by_name.get(name) or []
                       if entry["id"] != identity["id"]]
            if len(entries) != 1:
                continue     # several bearers or none: attributable to nobody
            entry = entries[0]
            person = people.get(entry["id"]) \
                or _recognized_person(chat_id, entry)
            person["last_observed_turn"] = turn["idx"]
            people[entry["id"]] = person
            continue
        if not label:
            continue
        ref = _presence_ref(name, str(body.get("key") or ""), by_name, refs)
        if not ref:
            continue
        if namespace is None:
            namespace = _presence_namespace(chat_id)
        pid = _viewer_presence_id(namespace, identity["id"], ref)
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
      * `people` -- the same two ledgers joined into a structured roster
        keyed on IMMUTABLE identity (`_people`): the identity ledger's names
        joined to every roster member bearing them under the ids `viewers()`
        already speaks, plus the perception stage's own per-beat record of
        observed bodies under composer labels and viewer-scoped opaque
        `body:` keys (`_viewer_presence_id`). A rename or alias changes
        `display_name` and never `id`; two people sharing a name are two
        entries; a stranger's canonical name and canonical id appear
        nowhere, and their opaque id neither survives into another viewer's
        projection nor confirms a guessed identity;
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

    from story.scene import get_scene, simulation_clock
    from world.spatial import room_of

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
