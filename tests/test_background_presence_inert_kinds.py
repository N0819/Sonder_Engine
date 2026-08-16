"""An object the beat sets down is not a person.

`track_background_presences` has a `positions` path -- anything the beat placed
in a room is in the scene by construction -- guarded by the same inert-kind rule
the entity harvest uses. The guard looked its kind up in a map keyed by the
entity's DISPLAY NAME while querying it with a `positions` key, which is an
entity ID. `utility_sash_with_pouches_hinami` never matched "utility sash with
pouches hinami", the lookup returned None, and None is not an inert kind -- so
the rule never fired for any entity whose id differs from its name.

Live, chat 75 turns 57-60: a shed utility sash was admitted as a background
presence, handed a housekeeper persona, and given three turns of dialogue.
"""

from __future__ import annotations

import commit


def _kinds(diff_entities, scene_entities):
    """Rebuild the lookup exactly as track_background_presences does."""
    out = {}
    for eid, edef in (list(diff_entities.items()) + list(scene_entities.items())):
        if not isinstance(edef, dict):
            continue
        kind = str(edef.get("kind") or "").strip().casefold()
        if not kind:
            continue
        for key in (eid, edef.get("name")):
            key = str(key or "").strip().casefold()
            if key:
                out.setdefault(key, kind)
    return out


SASH = {
    "utility_sash_with_pouches_hinami": {
        "name": "Utility Sash With Pouches Hinami",
        "kind": "object",
        "state": {"clothing": True, "worn_by": None, "shed": True},
    }
}
CLERK = {
    "char_night_clerk": {"name": "night clerk", "kind": "character"},
}


def test_an_id_keyed_position_resolves_its_kind():
    """The regression: positions is keyed by ID, so the ID must resolve."""
    k = _kinds({}, SASH)
    assert k["utility_sash_with_pouches_hinami"] == "object"


def test_the_display_name_still_resolves():
    """The original lookup must keep working -- the Director voices background
    entities by display name, and that path is unchanged."""
    k = _kinds({}, SASH)
    assert k["utility sash with pouches hinami"] == "object"


def test_a_shed_garment_is_an_inert_kind():
    """Belt and braces: 'object' and 'clothing' are both already denied, so
    once the lookup HITS, the sash is excluded."""
    k = _kinds({}, SASH)
    assert k["utility_sash_with_pouches_hinami"] in commit._INERT_ENTITY_KINDS


def test_a_person_is_not_excluded():
    """The gate must not start eating real background people -- the whole
    reason this path exists is the hotel clerk who arrived in `positions` and
    nothing else (chat 72 turn 47)."""
    k = _kinds({}, CLERK)
    assert k["char_night_clerk"] == "character"
    assert k["char_night_clerk"] not in commit._INERT_ENTITY_KINDS


def test_an_unknown_kind_still_defaults_to_inclusion():
    """`kind` is a freeform model string. An agent kind nobody enumerated --
    'actor', 'spirit', 'drone' -- must still be tracked, which is the trade the
    deny-list exists to make."""
    k = _kinds({}, {"thing_1": {"name": "Wandering Spirit", "kind": "spirit"}})
    assert k["thing_1"] == "spirit"
    assert k["thing_1"] not in commit._INERT_ENTITY_KINDS


def test_a_bare_position_with_no_entity_def_is_unknown():
    """No def, no kind -- the caller then falls through to inclusion, which is
    the documented trade (a body placed in a room with no def is agent-shaped
    by default). Recorded so a future change to that trade is deliberate."""
    k = _kinds({}, {})
    assert k.get("someone_the_beat_placed") is None
