"""The beat's bookkeeping around its minds: the plan invariant, merging a
mind's micro-round results, who speaks next and who is called to react,
declared goals, and the player's asserted state carried into the beat.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import json
from story.character_schema import (
    character_knowledge_config,
    character_name_from_text,
    normalized_character_of_row,
    persona_name,
)
from core.db import q
from story.scene import get_scene, persona_of
from world.spatial import merge_scene_with_diff, room_of

from agents.common_base import _dict, _dict_list, _ling, _list
from agents.common_cast import (
    _conceal_from_targets_observer,
    _present_cast_bodies,
    cast_spelling_policy,
    normalize_character_refs,
)
from agents.common_acts import communication_awaits_reply

def _assert_plan_materialized(turn_id, plan, ctx):
    """Verify that every planned step produced one active result."""
    expected = [key for key, _ in plan]

    rows = q(
        """
        SELECT
            s.key,
            COUNT(v.id) AS active_count
        FROM steps s
        LEFT JOIN variants v
          ON v.step_id=s.id
         AND v.active=1
        WHERE s.turn_id=?
        GROUP BY s.key
        """,
        (turn_id,),
    )

    active_counts = {
        row["key"]: int(row["active_count"])
        for row in rows
    }

    missing_context = [
        key
        for key in expected
        if key not in ctx
    ]

    invalid_results = [
        key
        for key in expected
        if active_counts.get(key, 0) != 1
    ]

    if missing_context or invalid_results:
        details = []

        if missing_context:
            details.append(
                "missing from context: "
                + ", ".join(missing_context)
            )

        if invalid_results:
            details.append(
                "without exactly one active variant: "
                + ", ".join(invalid_results)
            )

        raise RuntimeError(
            "Pipeline completion invariant failed; "
            + "; ".join(details)
        )

def _character_by_id(ctx, char_id):
    return next(row for row in ctx.cast if int(row["id"]) == int(char_id))

def _concat_dedup(*value_lists):
    """Union-concatenate list-of-dicts update fields, preserving order and
    dropping exact duplicates (a re-emitted identical update across rounds)."""
    out, seen = [], set()
    for values in value_lists:
        for item in _list(values):
            try:
                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            except (TypeError, ValueError):
                key = repr(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out

#: Every key a character's result can carry, classified by how TWO of that
#: character's declarations in one beat combine -- a later micro-round over an
#: earlier one (`loops._speak`), or the action result over the reaction result
#: (`commit_memory`'s `own_result`).
#:
#: CLASSIFYING A KEY IS MANDATORY, because the merge starts from `new` alone:
#: a key the earlier result carries and the later one omits is simply gone,
#: and "omits" is the ORDINARY shape of "had nothing to add this round" --
#: models emit sparse dicts and `_dump` uses exclude_none. Nothing warns,
#: because a field's warnings live inside the branch the drop skips: the only
#: reader of `drive_shift` is `elif own_result.get("drive_shift")` in
#: commit_memory, so a dropped rupture proposal is silent by construction.
#: `project_ops` and `drive_shift` were each lost this way before being named
#: here. tests/test_character_result_merge.py checks these four tuples against
#: CharacterOutput's own field list, so the next field added to the schema has
#: to be classified rather than defaulting to latest-wins by omission.

#: Concatenated in beat order and NOT deduped: two rounds may legitimately
#: carry the same line or motion, and a character who repeats themselves said
#: it twice.
#:
#: `recalled_memory_ids` is here for exactly that reason (A78). It is the
#: memory rows this mind's recall REACHED, handed to commit to record, and
#: each micro-round runs its own retrieval -- a row that came back in round 0
#: and again in round 1 came back twice, which is what `access_count` counted
#: while `search_memories` still made the write itself. Deduping it here
#: would quietly change the number the replay tools read.
_MERGE_APPEND_FIELDS = ("sequence", "recalled_memory_ids", "tool_calls", "_thought")

#: Unioned, order-preserving, exact duplicates dropped (a re-emitted identical
#: update across rounds). Each entry is an independent piece of work, so no
#: round's declared behavior or inference is lost.
_MERGE_UNION_FIELDS = (
    "mind_model_updates",
    "relationship_updates",
    "stance_updates",
    "inference_updates",
    "intent_ops",
    # A project adopted in round 0 and not restated in round 1 was
    # dropped here, which is the reaction-loop drop in miniature and
    # inside a single loop. Projects are removed only by being satisfied
    # or disputed -- never by a later round forgetting to mention one.
    "project_ops",
    "belief_updates",
    "association_updates",
    "present_evidence_used",
    "memory_evidence_used",
    "observations_used",
    "remember_lines",
    "memory_disputes",
    "memory_effects",
    "contact_ops",
    "material_effects",
    # Giving up on a promise is a decision, and the same reason `project_ops`
    # is here: one round declaring it and the next not restating it must not
    # un-declare it. Each row names its own debt, so two rounds abandoning two
    # different things both land.
    "waiting_ops",
    # The notebook's reminders: each op is its own add, change or strike, so
    # a round that keeps something and a later round that strikes something
    # else both land.
    "notebook_ops",
)

#: Preserved when the later declaration is SILENT about them; a later explicit
#: value wins. These are single-slot decisions -- there is no list to
#: accumulate into -- and saying nothing about one is not retracting it.
_MERGE_PRESERVE_FIELDS = (
    "active_state",
    "decision_continuity",
    # The bare contract's note to self: the last round that wrote one is the
    # beat's; a round that wrote none has not retracted it.
    "note",
    "ponder",
    # No-op/null means preserve the prior micro-round's explicit decision;
    # start/stop are both truthy dicts and the later explicit one wins.
    "follow_op",
    # PRESERVED rather than unioned because the slot holds exactly one:
    # affect.validate_drive_shift takes a single proposal, and a break closes
    # the window (commit_memory sets rupture=None), so a second proposal in
    # the same beat could not apply even if it were kept. Preserving matters
    # more here than anywhere else on this list: the window is engine-opened,
    # three turns wide, and the shift is invited only inside it, so the one
    # round that answers IS the rupture -- dropping it loses the scar, the
    # former-drive entry and the memory of the break together, and loses them
    # without a warning, since every drive_shift warning is emitted inside the
    # branch the drop skips.
    "drive_shift",
    # Set only when true, by the character stage, when this round's move
    # repeated an earlier one; it tells affect.apply_intent_ops not to credit
    # a `progress` claim. STICKY, because the intent_ops it guards accumulate:
    # latest-wins let a barren round's progress claim ride into commit under a
    # later clean round's flag. Over-suppressing costs one progress tick;
    # laundering credits a goal for a move already made.
    "_barren_beat",
)

#: LATEST WINS, deliberately -- named rather than omitted so the guard can
#: tell a decision from an oversight.
_MERGE_LATEST_WINS_FIELDS = (
    # The latest round's deliberation about the latest round's decision.
    "appraisal",
    "considered_responses",
    "response_candidates",
    "interaction",
    "salience",
    "manifest",
    # Mirrors `_sync_sequence_mirrors` derives FROM `sequence`, which
    # accumulates. They are stale after a merge, and that is safe only because
    # every reader prefers the sequence and falls back to the mirror when
    # there is none (`character._speech_texts`).
    "speech",
    "speech_volume",
    "action",
    "actions",
    # The character stage folds the earlier round's probe into the later one
    # itself, precisely because this merge keeps the latest ("the last round's
    # probe must therefore tell the whole beat's story", character.py).
    "unbidden_probe",
    # Identity of the character both results belong to; equal by construction.
    "name",
    "char_id",
    # The engine's mood after this round (`affect_pass.persisted`): each round
    # starts from the one before it, so the latest round's is the beat's.
    "_affect_pass",
)

#: Result keys that are NOT CharacterOutput fields: written by the stage after
#: validation (`norm_sequence` -> ponder, `_sync_sequence_mirrors` ->
#: speech_volume, `character_step` -> name/char_id/unbidden_probe/
#: recalled_memory_ids/_barren_beat) or legacy inputs commit still reads (stance_updates,
#: inference_updates). Enumerated so the guard can insist an unrecognised name
#: is either a schema field or a deliberate extra.
_MERGE_NON_SCHEMA_KEYS = frozenset({
    "stance_updates", "inference_updates", "ponder", "speech_volume",
    "name", "char_id", "unbidden_probe", "recalled_memory_ids",
    "_barren_beat", "_affect_pass", "tool_calls", "_thought",
})


def _merge_character_results(existing, new):
    """Combine a character's earlier-round result with a later one instead of
    overwriting. A character who speaks in more than one micro-round would
    otherwise lose its round-0 sequence/mind_model_updates/etc. at commit,
    which reads ctx.character_results[id] as a single result.

    Which key does what is declared in the four tables above -- append, union,
    preserve-if-the-later-round-is-silent, latest-wins -- and every key a
    result can carry sits in exactly one of them. Read the note above
    `_MERGE_APPEND_FIELDS` before adding a field: an unclassified key is
    latest-wins by accident, and drops without a warning."""
    if not isinstance(existing, dict):
        return new
    if not isinstance(new, dict):
        return existing
    merged = dict(new)
    for field in _MERGE_APPEND_FIELDS:
        merged[field] = _list(existing.get(field)) + _list(new.get(field))
    for field in _MERGE_UNION_FIELDS:
        combined = _concat_dedup(existing.get(field), new.get(field))
        if combined or field in existing or field in new:
            merged[field] = combined
    for field in _MERGE_PRESERVE_FIELDS:
        # An empty decision is an explicit clearing operation. Only an absent
        # legacy note preserves an earlier round's choice.
        silent = (new.get(field) is None if field == "decision_continuity"
                  else not new.get(field))
        previous = existing.get(field)
        present = (previous is not None if field == "decision_continuity"
                   else bool(previous))
        if silent and present:
            merged[field] = existing.get(field)
    previous_active = existing.get("active_state")
    current_active = merged.get("active_state")
    if (isinstance(previous_active, dict) and isinstance(current_active, dict)
            and current_active.get("active_concerns") is None
            and previous_active.get("active_concerns") is not None):
        merged["active_state"] = {
            **current_active,
            "active_concerns": previous_active["active_concerns"],
        }
    if isinstance(previous_active, dict) and isinstance(current_active, dict):
        previous_affect = previous_active.get("affect")
        current_affect = current_active.get("affect")
        if (isinstance(previous_affect, dict) and isinstance(current_affect, dict)
                and "undercurrent" in previous_affect
                and "undercurrent" not in current_affect):
            merged["active_state"] = {
                **merged["active_state"],
                "affect": {**current_affect,
                           "undercurrent": previous_affect["undercurrent"]},
            }
    return merged


def _char_known_tags(sheet):
    """(depth tiers, excluded titles, compartments) for one mind.

    Three returns rather than two because knowledge has three axes and the
    third one -- WHO may know a thing -- had no representation at all. See
    `mind.memory_lore_entries.knowledge_for_character`.
    """
    config = character_knowledge_config(sheet)
    tags = [tag for tag in ("common", "scholarly", "esoteric") if config.get(tag)]
    return tags, config.get("excluded_titles") or [], config.get("circles") or []

def _character_display_name(row):
    return character_name_from_text(row["sheet"])

def _normalize_scene_patch(value):
    patch = dict(value or {})
    for key in ("rooms", "entities", "positions", "stations"):
        if not isinstance(patch.get(key), dict):
            patch[key] = {}
    for key in ("remove_entities", "remove_rooms", "remove_adjacent"):
        if not isinstance(patch.get(key), list):
            patch[key] = []
    return patch

def _sequence_has_content(result):
    return any(
        (event.get("text") if event.get("type") == "speech"
         else (event.get("content") if event.get("type") == "communication"
               else event.get("attempt")))
        for event in (result.get("sequence") or [])
        if isinstance(event, dict)
    )

def _asks_player(result, chat, cast=None):
    """Is this character's turn a question the player is expected to answer?

    Two English/ASCII assumptions used to make the answer always "no" in
    another language (review 2026-09-07 A34), so the interaction loop never
    stopped for a question and the beat ran on past the player: the forms
    that MEAN the player were three English literals, and the fallback asked
    whether a speech line ends in an ASCII "?". Both are the pack's
    (`_PLAYER_ADDRESS_FORMS`, `_QUESTION_MARKS`), and who a spelling belongs
    to is `cast_spelling_policy`'s, so a uid or `character:<id>` in
    `addresses` names the body it identifies.
    """
    player_name = persona_name(persona_of(chat))
    interaction = _dict(result.get("interaction"))
    addresses = {
        str(v).strip().casefold()
        for v in _list(interaction.get("addresses"))
        if str(v or "").strip()
    }
    canonical, _spellings = cast_spelling_policy(cast, player_name)
    aliases = set(_ling("_PLAYER_ADDRESS_FORMS"))
    if player_name:
        aliases.add(player_name.casefold())

    def _names_player(token):
        text = str(token or "").strip().casefold()
        if not text:
            return False
        return bool(text in aliases or (
            player_name
            and str(canonical(text) or "").strip().casefold()
            == player_name.casefold()))

    if any(_names_player(form) for form in addresses):
        return True
    # The trailing-"?" fallback (a speech line ending in "?" is treated as a
    # question awaiting the player) must fire ONLY when the speaker didn't
    # aim the line at a specific cast member. An NPC asking ANOTHER NPC a
    # question ("Reya, are you sure?") is not awaiting the player, and using
    # "?" alone to end the loop there strands an NPC<->NPC exchange as if the
    # player had been addressed. So: if `addresses` names a registered cast
    # member (and not the player, handled above), never apply the fallback.
    # Every spelling a registered body answers to, not just its sheet name:
    # the same tolerance the presence floor reads, so "who was addressed" and
    # "who is present" cannot disagree about a uid.
    cast_names = {form for form, canon in _spellings.items()
                  if not player_name or canon.casefold() != player_name.casefold()}
    if addresses & cast_names:
        return False
    for event in _dict_list(result.get("sequence")):
        if event.get("type") == "communication":
            if communication_awaits_reply(event):
                targets = {str(value).strip().casefold()
                           for value in event.get("targets") or []
                           if str(value or "").strip()}
                if not targets or any(_names_player(t) for t in targets):
                    return True
            continue
        if event.get("type") != "speech":
            continue
        text = str(event.get("text") or "").strip()
        if text.endswith(tuple(_ling("_QUESTION_MARKS"))):
            return True
    return False

def _next_speaker_candidates(ctx, last_actor_id, perceived_by, already_spoke):
    candidates = []
    for row in ctx.cast:
        char_id = int(row["id"])
        if char_id == last_actor_id or char_id not in perceived_by:
            continue
        result = _dict(ctx.character_results.get(char_id))
        interaction = _dict(result.get("interaction"))
        priority = float(interaction.get("urgency", 0.0))
        if char_id not in already_spoke:
            priority += 0.2
        candidates.append((priority, char_id))
    candidates.sort(reverse=True)
    return [char_id for _, char_id in candidates]


def _append_micro_view(base_view, additions):
    parts = [str(base_view or "").strip()]
    parts.extend(str(item).strip() for item in additions if str(item or "").strip())
    return "\n\n".join(part for part in parts if part)

# Defined in `persist/commit_common.py` and imported through the `commit`
# facade rather than copied: this module and commit both run it, on the model's
# output and on a rehydrated result respectively, and two copies of one shape
# normalisation is how the two come to disagree about what a legacy field
# means (audit STORY-F11's shape). The direction is forced by an import cycle
# -- see that function's docstring.
from persist.commit import _normalize_character_output  # noqa: E402,F401


def declared_goal(result):
    """The goal one character result declares, derived from the enacted want.

    The output template no longer asks for `active_state.goal`: commit was
    measured (401 recent-era calls, 2026-08-11 audit + re-measure) replacing
    the emitted string with `wants[enacted].want` on 99.0% of calls, and the
    two matched only 16.2% of the time -- the field was ~20 tokens/call of
    decode-time cost carrying a worse copy of an answer the result already
    contains. Every reader of the raw variant/result field derives it here
    instead, with the legacy field as the fallback so pre-change stored
    variants -- and any provider that still emits it -- read identically.
    """
    if not isinstance(result, dict):
        return ""
    active = result.get("active_state")
    if not isinstance(active, dict):
        return ""
    wants = active.get("wants")
    enacted = active.get("enacted_want")
    if (isinstance(wants, list) and isinstance(enacted, int)
            and 0 <= enacted < len(wants) and isinstance(wants[enacted], dict)):
        want = str(wants[enacted].get("want") or "").strip()
        if want:
            return want
    return str(active.get("goal") or "").strip()


def _widening_reads(chat_id, scene=None, player_name=None):
    """``(scene, player name)`` for a reactor widening: what the caller
    already holds, else one read of each.

    Each `widen_reactors_*` read the committed scene (an uncached SELECT and
    a ~0.8 ms parse of a median 50 KB scene), the chat row and the persona
    for itself, from thirteen call sites a beat -- the planner six, the
    interaction loop seven -- though every caller already holds both
    (agents_common audit, Efficiency 1: ~15-25 ms of reads a beat). A caller
    that hands them in pays nothing here; one that does not reads exactly
    as before."""
    from story.character_schema import persona_name
    if scene is None:
        scene = get_scene(chat_id)
    if player_name is None:
        chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
        player_name = persona_name(persona_of(dict(chat))) if chat else ""
    return scene, player_name


def widen_reactors_to_hearers(chat_id, cast_rows, interp, reactors, *,
                              scene=None, player_name=None):
    """`reactors` plus every present cast body OUTSIDE the player's room
    that hears the player's line this beat (`hear_level` over
    `spatial_rel_between`, at the line's volume).

    A VOICE THAT CARRIES INTO ANOTHER ROOM REACHES A BODY THE DIRECTOR DID
    NOT SEE. `flow.reactors` is the Director's pacing judgement of the room
    the player stands in; the sound field is the engine's knowledge of
    where a line goes past it. Read by the planner and by the interaction
    loop alike (both read `flow.reactors` on their own), so the two cannot
    disagree about who was called to. Skerry Light turn 4 (2026-09-15): a
    loud challenge called down a three-storey stairwell reached the man at
    its foot in full, the Director's list was empty, and he stood there
    for the beat. Bodies in the player's own room stay the Director's call.
    """
    from world.spatial import (hear_level, room_of, spatial_rel_between,
                               spoken_to)
    try:
        scene, p_name = _widening_reads(chat_id, scene, player_name)
    except Exception:
        return reactors
    if not p_name or not room_of(scene, p_name):
        return reactors
    volume = str(interp.get("speech_volume") or "normal")
    widened = list(reactors)
    here = room_of(scene, p_name)
    # WHOM THE LINE IS SPOKEN TO, as the interpret booked it: the one body
    # a line breathed into an ear reaches (`spatial_senses.EAR_VOLUME`).
    flow = interp.get("flow") if isinstance(interp.get("flow"), dict) else {}
    aimed = {str(i) for i in (flow.get("addressed_to") or ())}
    for body in _present_cast_bodies(scene, cast_rows):
        if body["id"] in widened or body.get("room") == here:
            continue
        try:
            rel = spatial_rel_between(scene, body["name"], p_name)
            heard = hear_level(rel, volume,
                               addressed=spoken_to(str(body["id"]) in aimed,
                                                   bool(aimed)))
        except Exception:
            continue
        if heard and heard != "none":
            widened.append(body["id"])
    return widened


def widen_reactors_to_enclosure(chat_id, cast_rows, reactors, *,
                                scene=None, player_name=None):
    """`reactors` plus every present cast body the player is INSIDE, or that
    is inside the player.

    A BODY'S INSIDE IS PART OF IT. The place form gives an interior a room of
    its own, so a player swallowed into a throat stands in one room and the
    body whose throat it is stands in another -- and every other reactor
    rule reads rooms: the Director paces the player's room, and
    `widen_reactors_to_hearers` asks what carries across a wall. Neither
    sees that the holder IS the walls. Measured on the chat 137 replay
    (2026-09-23): a player inside Mirelle's throat squirmed, felt along the
    walls and spoke to her by name for six beats, and the body she was
    inside was not once asked what it did. Joined exactly as
    `enclosure_joins_rooms` joins the pair for contact -- strictly the pair,
    never a third body standing in the holder's room.
    """
    from world.spatial import enclosure_joins_rooms, room_of
    try:
        scene, p_name = _widening_reads(chat_id, scene, player_name)
    except Exception:
        return reactors
    here = room_of(scene, p_name) if p_name else None
    if not here:
        return reactors
    widened = list(reactors)
    for body in _present_cast_bodies(scene, cast_rows):
        if body["id"] in widened or body.get("room") == here:
            continue
        try:
            joined = enclosure_joins_rooms(scene, here, body.get("room"),
                                           p_name, body["name"])
        except Exception:
            continue
        if joined:
            widened.append(body["id"])
    return widened


def widen_reactors_to_rejoined(chat_id, cast_rows, reactors, turn_idx,
                               frame_id=None):
    """`reactors` plus every cast member a causality bubble returned to this
    frame AT this beat. The merge runs before the plan precisely because the
    beat walks the player into the bubble's reach (`runtime._merge_bubbles_
    the_beat_reaches`: "so its cast hear, see and answer it") -- but the
    reactors come from the interpret, which ran BEFORE the merge and never
    saw her. Measured on scratch story 166 (idx 13): the pilot rejoined at
    the foot of the stair with no step in the plan, so under "a walk is its
    owner's" nobody could move her and nobody could ask her; the player
    walked past her, boarded the boat she was to take her out in, and sat
    there alone, and the pilot was bubbled off again at the commit.

    Read from the durable record (`frames.merged_turn_idx`), so a resume or
    a rerun of the turn plans the same steps the run did."""
    if turn_idx is None:
        return reactors
    try:
        children = [row["id"] for row in q(
            "SELECT id FROM frames WHERE chat_id=? AND kind='spatial' "
            "AND merged_turn_idx=? AND parent_frame_id IS ?",
            (chat_id, int(turn_idx), frame_id))]
        if not children:
            return reactors
        marks = ",".join("?" for _ in children)
        rejoined = {int(row["char_id"]) for row in q(
            f"SELECT char_id FROM chat_char_frames WHERE chat_id=? "
            f"AND frame_id IN ({marks})", (chat_id, *children))}
    except Exception:
        return reactors
    valid = {int(row["id"]) for row in cast_rows or ()}
    out = list(reactors)
    for char_id in sorted(rejoined & valid):
        if char_id not in out:
            out.append(char_id)
    return out


def widen_reactors_to_engaged(chat_id, cast_rows, reactors, turn_idx,
                              frame_id=None, *, scene=None, player_name=None):
    """`reactors` plus every present cast body OUTSIDE the player's room
    that addressed the player on the previous beat: a conversation across
    rooms is still a conversation, and the body that just said "Coming
    down" is asked what it does next.

    THE DIRECTOR PACES THE ROOM IT SEES. A body elsewhere that answered
    the player last beat -- its `dialogue_log` line aimed at the player --
    is engaged with them, and on the beat after, with nothing said to
    widen it in (`widen_reactors_to_hearers`), it stood where it was:
    Skerry Light turn 15 (2026-09-15), "Coming down." from three storeys
    up, then a whole beat of silence on the stair. One beat of grace, read
    from the previous turn's committed resolve; a body that then neither
    moves nor speaks to the player is not asked again.
    """
    if turn_idx is None:
        return reactors
    try:
        idx = int(turn_idx)
    except (TypeError, ValueError):
        return reactors
    if idx <= 0:
        return reactors
    try:
        row = q("SELECT v.content AS content FROM turns t "
                "JOIN steps s ON s.turn_id=t.id "
                "JOIN variants v ON v.step_id=s.id AND v.active=1 "
                "WHERE t.chat_id=? AND t.idx=? AND t.frame_id IS ? "
                "AND s.key='director_resolve' LIMIT 1",
                (chat_id, idx - 1, frame_id), one=True)
        resolve = json.loads(row["content"]) if row else None
        scene, p_name = _widening_reads(chat_id, scene, player_name)
    except Exception:
        return reactors
    if not isinstance(resolve, dict) or not p_name:
        return reactors
    from world.spatial import room_of
    here = room_of(scene, p_name)
    spoke_to_player = set()
    for line in resolve.get("dialogue_log") or []:
        if not isinstance(line, dict):
            continue
        if str(line.get("intended_target") or "").strip().casefold() == p_name.casefold():
            spoke_to_player.add(str(line.get("speaker") or "").strip().casefold())
    if not spoke_to_player:
        return reactors
    widened = list(reactors)
    for body in _present_cast_bodies(scene, cast_rows):
        if body["id"] in widened or body.get("room") == here:
            continue
        if str(body.get("name") or "").strip().casefold() in spoke_to_player:
            widened.append(body["id"])
    return widened


#: The declared elements that can be AIMED at a body: what the beat says to
#: someone, does to someone, or sends to someone. The engine's own element
#: types (`schemas` sequence `type`), a closed set -- not a vocabulary of acts.
#: A `thought` is aimed at nobody.
AIMED_ELEMENT_TYPES = ("action", "speech", "communication")


def acted_upon_cast(scene, cast_rows, interp, player_name):
    """The cast ids an element of this beat's declaration is AIMED AT -- a
    sequence element whose `targets` name them -- that the beat reaches
    where they stand: present (`_present_cast_bodies`), and able to
    perceive the beat (`can_perceive_onset`) from the player's room or the
    room the declared walk takes the player into. In element order, each
    once. Pure: reads nothing but its arguments, so the planner, both loops
    and a replay against a stored beat get one answer.

    An element CONCEALED from a target does not put that target on the
    spot -- the act is hidden from them, and asking them what they do about
    it would be asking about a thing they cannot know. A concealed element
    that does not say whom it is hidden from widens nobody: the widening
    adds a call, so where the record cannot say, it stays as it was.
    """
    if not isinstance(interp, dict) or not player_name:
        return []
    from world.spatial import can_perceive_onset
    beat_rooms = []
    here = room_of(scene, player_name)
    if here:
        beat_rooms.append(here)
    movement = interp.get("movement")
    if isinstance(movement, dict) and movement.get("arrives", True) is not False:
        mover = str(movement.get("mover") or "self").strip().casefold()
        destination = str(movement.get("to_room") or "").strip()
        if mover in ("self", player_name.casefold()) and destination \
                and destination not in beat_rooms:
            beat_rooms.append(destination)
    if not beat_rooms:
        return []
    bodies = {int(body["id"]): body
              for body in _present_cast_bodies(scene, cast_rows)}
    if not bodies:
        return []
    out = []
    for element in interp.get("sequence") or []:
        if not isinstance(element, dict) \
                or element.get("type") not in AIMED_ELEMENT_TYPES:
            continue
        aimed = normalize_character_refs(_list(element.get("targets")),
                                         cast_rows)
        if not aimed:
            continue
        if str(element.get("visibility") or "").strip().casefold() == "concealed":
            hidden_from = _list(element.get("conceal_from"))
            if not hidden_from:
                continue
            sheets = {int(row["id"]): normalized_character_of_row(row)
                      for row in cast_rows or ()}
            # The firewall's own reading of an exclusion list -- every handle
            # a body answers to -- and a body it cannot enumerate counts as
            # excluded, as that reading fails closed.
            aimed = [cid for cid in aimed
                     if sheets.get(cid) is not None
                     and not _conceal_from_targets_observer(
                         hidden_from, cid, sheets[cid])]
        for cid in aimed:
            body = bodies.get(cid)
            if body is None or cid in out:
                continue
            if any(can_perceive_onset(scene, room, body.get("room"))
                   for room in beat_rooms):
                out.append(cid)
    return out


def widen_reactors_to_acted_upon(chat_id, cast_rows, interp, reactors, *,
                                 scene=None, player_name=None):
    """`reactors` plus every cast body an element of this beat's
    declaration is aimed at, where the beat reaches them
    (`acted_upon_cast`).

    A BODY THE BEAT'S ACTS ARE AIMED AT IS ASKED WHAT IT DOES. Under the
    prose contract `flow.reactors` is derived (`director.director_interpret`):
    the beat's addressees, or everyone who perceives it when nobody was
    addressed. So addressing one person silenced every other mind in the
    room, including one the declaration's own act landed on. Brackwater,
    chat 166 turn idx 30, the run's final beat: the player opened the door
    to the pilot ("Come in, Mrs Gale") and "steps aside so that brother and
    sister face each other across the lantern" -- that act's targets were
    `character:81` and `character:83`, the reactors `[81]`. The pilot's
    line turned to the player, the loop stopped `awaiting player
    response`, and her brother -- a full character at the table, whose
    drive and taboo are about her -- was never asked. The page spent the
    beat on an unopened pocket instead of the exchange the scene had set.

    It is the response the act asks for: "a line's addressee is asked"
    (`director._addressed_characters`) one channel over, and the registered
    P5(a) (`docs/UNBUILT_PIPELINE.md` § 5.3) without its conflict-verb list.
    Not a contest over whether the act succeeded -- that stays the reaction
    phase's, gated on `commitment` -- and nobody's conduct is written for
    them: the body is asked, and answers or does not.

    Cost, replayed against every stored beat of the scratch play db
    (2026-10-08, chats 135-166, each beat's own interpret on its pre-beat
    checkpoint): one extra character call on 1 of 385 beats -- the beat
    above, and no other. Read by the planner, the interaction loop and the
    reaction phase alike, so the three cannot disagree about who was put on
    the spot.
    """
    try:
        scene, p_name = _widening_reads(chat_id, scene, player_name)
        aimed = acted_upon_cast(scene, cast_rows, interp, p_name)
    except Exception:
        return reactors
    widened = list(reactors)
    for cid in aimed:
        if cid not in widened:
            widened.append(cid)
    return widened


# ---- What the player asserts is true before anyone reacts to it ----
#
# THE RULE, from the person who owns the fiction: interpret is NOT a lesser
# authority than resolve. It is merely scoped to player input. If the player
# says something happens, it happens that turn -- before perception pass 1
# fires.
#
# It was not true, and the reason was structural rather than deliberate. A
# player's declaration reached `director_interpret` as prose and reached the
# SCENE only through `director_resolve`, which runs AFTER every character has
# declared. So everything a player narrated was invisible for the beat in
# which they narrated it: "I pull my top off" was perceived as still wearing
# it, "I kneel" as still standing, "I duck into the alcove" as standing in the
# open with no alcove. Each reactor decided against a world one beat stale,
# and the change surfaced the turn after.
#
# Contact, movement and following were each fixed one at a time, with their
# own field, their own guard and their own preview. That was the mistake --
# a hand-picked list of the channels lucky enough to have been noticed, each
# one re-deciding what the player is allowed to say. This is the general form,
# and it is deliberately not a shorter list of powers:
#
#   * THE SAME SCHEMA. `state_assertions` is a `StateDiff` -- the exact
#     structure `director_resolve` emits, every channel of it. Rooms, entities,
#     positions, conditions, world facts, destruction. Equal authority means
#     the same vocabulary, not a curated subset of it.
#   * THE SAME APPLIER. `merge_scene_with_diff` is what commit uses, and it is
#     pure and deep-copying, so pass 1 sees precisely the world commit will.
#   * SCOPED BY SOURCE, NOT BY SUBJECT. What bounds interpret is that it reads
#     the player's input and nothing else. There is no channel filter and no
#     per-subject guard here, because either would be this stage second-
#     guessing a declaration it was built to carry.
#
# What is NOT changed: commit remains the only writer. This previews on a copy
# for pass 1, and the assertion is merged into resolve's own diff so the beat
# is still persisted exactly once, through every guard commit already runs
# (occupied-room removal, destruction, room-registry projection). And the
# information firewall is untouched -- putting a fact into the scene is not
# putting it into a mind; the composer still admits it to an observer only if
# that observer can perceive it.


def validated_player_state_assertions(sc, raw, player_name, report=None):
    """The player's declared state changes, validated as a `StateDiff`.

    SHAPE ONLY, on purpose. An earlier pass of this filtered by channel and
    then by subject, which made interpret a lesser authority than resolve by
    construction -- exactly the thing this exists to stop being true. The
    Director already classifies each act `asserted` or `contestable`, and an
    act on somebody else IS contestable; deciding that is interpret's job,
    not a whitelist's.

    Pure: reads nothing, writes nothing, returns a plain dict.

    ONE BAD CHANNEL COSTS THAT CHANNEL (A29, review 2026-09-07). This ran as
    `StateDiff(**raw)` inside a bare `except Exception: return {}`, and its
    caller (`agents/director.py`'s interpret tail) hands it the object the
    specialists have just merged their channels INTO -- so a single malformed
    specialist-written channel discarded the player's whole declared state,
    the same class the two prunes in `llm/schemas.py` fix for a step's own
    output. `validated_state_diff_channels` drops only the channels that
    error and reports each; the whole-payload discard survives for a failure
    no channel owns.
    """
    if not isinstance(raw, dict) or not raw:
        return {}
    try:
        from llm.schemas import validated_state_diff_channels
        clean, dropped = validated_state_diff_channels(raw)
    except Exception as exc:  # noqa: BLE001 - a malformed assertion is not a turn failure
        if report:
            report(f"discarded a malformed state assertion: {exc}")
        return {}
    if report:
        for channel in dropped:
            report("dropped a malformed state assertion channel: "
                   f"{channel}")
    clean = {key: value for key, value in clean.items() if value}

    # Spatial owns place creation. A position may name an existing room or a
    # room authored in this same diff; anything else would leave a body in a
    # room with no geometry, light, scale, or reliable identity. Earlier code
    # papered over that omission by minting a blank stub here. Besides being
    # low fidelity, it also turned poses such as "on Mara's palm" into rooms.
    # Refuse only the bad position and let the provider repair ladder ask the
    # spatial hand for a complete room.
    positions = clean.get("positions")
    if isinstance(positions, dict) and positions:
        rooms = (sc or {}).get("rooms") or {}
        declared = clean.get("rooms") or {}
        refused = []
        for who, room in positions.items():
            if not room or room in rooms or room in declared:
                continue
            refused.append(who)
            if report:
                report(
                    f"asserted position put {who!r} in unknown room {room!r}; "
                    "left them where they were. The spatial hand must create "
                    "and describe a destination before placing anyone there.")
        for who in refused:
            positions.pop(who, None)
        if not positions:
            clean.pop("positions", None)
    return clean


def preview_player_state_assertions(sc, assertions, ctx=None,
                                    player_name=None, *, causal_worlds=None):
    """Apply asserted state to a scene COPY and return it.

    The copy is the whole safety property. Pass 1 and the resolving Director
    both need to see the world the player just described; neither may persist
    it. `merge_scene_with_diff` deep-copies before it touches anything, so the
    caller's scene is never the one that changes.

    Surface marks and attire use commit's body appliers after the spatial
    merge. Run both inside each chronological span, before its receipt and
    observer snapshot; applying only the flattened final changes would lose
    a mark added and removed within this declaration. Attire's removal clamp
    reads only the player's input here, the account available before resolve.
    """
    if not assertions:
        return sc
    def apply_body(merged, patch):
        from persist.commit import _merge_overlays
        _merge_overlays(merged, patch.get("overlays") or {})
        if patch.get("attire") and ctx is not None:
            from persist.commit import apply_attire_diff
            apply_attire_diff(merged, {"attire": patch["attire"]}, ctx, {},
                              report=False)
    merged = merge_scene_with_diff(sc, assertions, causal_apply=apply_body,
                                   causal_worlds=causal_worlds, age_contacts=False)
    if not assertions.get("causal_steps"):
        apply_body(merged, assertions)
    return merged


def merge_player_state_assertions(assertions, resolved, player_name=None,
                                  report=None):
    """Carry asserted state into the durable diff.

    Previewing fixes what reactors SAW and nothing else -- if resolve then
    never mentions the change, commit writes the turn without it and the
    ledger forks from the beat everybody just played.

    Resolve keeps the last word and has to use it. Where resolve speaks about
    the same subject or key it is re-resolving, and it wins; silence is not a
    contradiction. Lists append rather than replace, since an op is an event
    and two events both happened.
    """
    out = dict(resolved) if isinstance(resolved, dict) else {}
    for channel, value in (assertions or {}).items():
        current = out.get(channel)
        if channel == "causal_steps":
            # Invocation-local item and chrono ids must not collide. Each
            # step carries its stage, and onset executes before resolution.
            out[channel] = list(value or []) + list(current or [])
            continue
        if isinstance(value, dict):
            merged = dict(current) if isinstance(current, dict) else {}
            for subject, payload in value.items():
                if subject in merged:
                    if report:
                        report(f"resolve restated {channel} for {subject}; "
                               "the assertion yields")
                    continue
                merged[subject] = payload
            out[channel] = merged
        elif isinstance(value, list):
            existing = list(current) if isinstance(current, list) else []
            for item in value:
                if item not in existing:
                    existing.append(item)
            out[channel] = existing
        elif current in (None, "", 0):
            out[channel] = value
        elif report:
            report(f"resolve restated {channel}; the assertion yields")
    return out
