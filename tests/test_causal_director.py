"""The row machinery the prose Director's events still run through.

The causal Director's contract, its hands' positional envelope, their wire
grammars and the spatial hand's interior-minting check went with them on
2026-09-27. What stands here is what reads the rows code builds from the
encoder's events: normalization, owners, the recompiler, the beat record.
"""
from types import SimpleNamespace

from agents import director
from world.causality import compile_transforms


_span_items = director._span_items
normalize_causal_ledger = director.normalize_causal_ledger
span_owners = director.span_owners


def test_a_body_is_not_a_room_until_the_world_has_made_it_one():
    """A person's name in an event is staging, never a request to treat
    their body as a room. The interior roster admits a cast or player body
    only when the scene already holds an interior for it -- a room carrying
    it as `parent_entity` or an `interior_rooms` entry -- and reads no prose
    for it."""
    identities = {"persona:10": "Hinami", "character:58": "The Doctor"}
    sc = {"rooms": {}, "entities": {"Hinami": {"interior_rooms": []},
                                    "The Doctor": {"interior_rooms": []}}}
    excluded = director._bodies_without_interiors(sc, identities)
    assert {"persona:10", "Hinami", "character:58", "The Doctor"} <= excluded

    sc["rooms"]["hinami_throat"] = {"name": "Throat", "parent_entity": "Hinami"}
    excluded = director._bodies_without_interiors(sc, identities)
    assert "persona:10" not in excluded and "Hinami" not in excluded
    assert "character:58" in excluded and "The Doctor" in excluded


def test_authority_is_attached_to_identity_and_asserted_input_is_not_rerun():
    ctx = SimpleNamespace(
        chat=SimpleNamespace(persona_id=7),
        extra_players=[],
    )
    interp = {
        "authority_mode": "world_author",
        "sequence": [
            {"event_id": "asserted", "type": "action",
             "attempt": "opens the door", "commitment": "asserted"},
            {"event_id": "contested", "type": "action",
             "attempt": "strikes the guard", "commitment": "contestable"},
        ],
    }
    declarations = [{
        "char_id": 11, "name": "Mara",
        "sequence": [{"event_id": "mara:1", "type": "action",
                      "attempt": "steps back", "commitment": "asserted"}],
    }]
    groups = director._causal_event_inputs(
        ctx, interp, declarations, [], [])

    assert groups[0]["entity_id"] == "persona:7"
    assert groups[0]["authority_mode"] == "world_author"
    assert [event["event_id"] for event in groups[0]["events"]] == [
        "contested"]
    assert groups[1]["entity_id"] == "character:11"
    assert groups[1]["authority_mode"] == "autonomous"
    assert groups[1]["events"][0]["event_id"] == "mara:1"


def test_one_ledger_routes_to_every_owner_and_keeps_the_numeric_join():
    out = {"ledgers": [{
        "chrono_id": 99,
        "item_id": 7,
        "object_name": "coat",
        "source_entity_id": "character:11",
        "authority_mode": "autonomous",
        "source_event_id": "mara:1",
        "kind": "action",
        "event": "drops the coat on the bench",
        "resolution_notes": "The coat is unworn and rests on the bench.",
        "categories": ["attire", "entities", "positions"],
    }]}
    normalize_causal_ledger(out)
    spans = _span_items(out)

    assert spans[0]["event_id"] == 99
    assert spans[0]["item_id"] == 7
    assert spans[0]["object_name"] == "coat"
    assert spans[0]["authority_mode"] == "autonomous"
    assert spans[0]["_items"] == [{"id": 7, "name": "coat"}]
    assert span_owners(spans[0]) == ["body", "objects", "spatial"]


def test_projected_sequence_keeps_the_movement_the_spatial_hand_needs():
    out = {"ledgers": [{
        "chrono_id": 1, "item_id": 1, "object_name": "TARDIS",
        "source_entity_id": "persona:primary",
        "source_event_id": "turn:1:primary:raw",
        "authority_mode": "world_author", "kind": "action",
        "event": "steps into the TARDIS", "observable": "steps inside",
        "commitment": "asserted", "targets": ["TARDIS"],
        "visibility": "public", "conceal_from": [], "volume": "normal",
        "movement": {"mover": "self", "to_room": "tardis",
                     "arrives": True},
        "resolution_notes": "The player enters.",
        "categories": ["rooms", "positions"],
    }]}
    normalize_causal_ledger(out)
    assert out["sequence"][0]["movement"] == {
        "mover": "self", "to_room": "tardis", "arrives": True}


def test_private_item_targets_become_readable_names_before_dispatch():
    out = {"ledgers": [{
        "chrono_id": 1, "item_ids": [1, 2, 3],
        "item_names": ["brass box", "copper key", "Nera"],
        "source_entity_id": "persona:1", "source_event_id": "turn:1:primary:raw",
        "event": "The seal is intact.", "categories": ["speech"],
        "targets": ["3", "1"],
    }]}
    normalize_causal_ledger(
        out, identity_index={"persona:1": "Iona", "character:1": "Nera"},
        known_targets={"brass_box", "copper_key"})
    ledger = out["ledgers"][0]
    assert ledger["targets"] == ["Nera", "brass box"]
    assert ledger["item_ids"] == [1, 2, 3]
    assert out["sequence"][0]["intended_target"] == "Nera"


def test_real_world_and_identity_keys_win_over_private_handle_collisions():
    out = {"ledgers": [{
        "chrono_id": 1, "item_ids": [1, 2], "item_names": ["box", "key"],
        "event": "points at the numbered lockers", "categories": [],
        "targets": ["1", "2", "character:4", "existing_room"],
    }]}
    normalize_causal_ledger(
        out, identity_index={"2": "Mara", "character:4": "Nera"},
        known_targets={"1", "existing_room"})
    assert out["ledgers"][0]["targets"] == ["1", "2", "character:4", "existing_room"]


def test_legacy_numeric_character_target_is_not_reinterpreted_as_an_item():
    out = {"ledgers": [{
        "chrono_id": 1, "item_id": 4, "object_name": "brass box",
        "event": "shows the box to Mara", "categories": ["entities"],
        "targets": ["4"],
    }]}
    normalize_causal_ledger(out)
    assert out["ledgers"][0]["targets"] == ["4"]


def test_conflicting_names_for_a_private_handle_do_not_choose_an_object():
    out = {"ledgers": [
        {"chrono_id": 1, "item_ids": [1], "item_names": ["brass box"],
         "event": "opens the box", "categories": ["entities"], "targets": ["1"]},
        {"chrono_id": 2, "item_ids": [1], "item_names": ["copper key"],
         "event": "lifts the key", "categories": ["inventory_ops"], "targets": ["1"]},
    ]}
    normalize_causal_ledger(out)
    assert [row["targets"] for row in out["ledgers"]] == [["1"], ["1"]]


def test_recompiler_uses_every_transform_in_chronological_order():
    transforms = [
        {"item_id": 1,
         "patch": {"rooms": {"hall": {"state": {"open": True}}}}},
        {"item_id": 2,
         "patch": {"rooms": {"hall": {
             "name": "Hall", "state": {"open": False}}}}},
        {"item_id": 3,
         "patch": {"rooms": {"hall": {"desc": "north door"}}}},
    ]
    ledgers = [
        {"item_id": 1, "chrono_id": 2, "object_name": "north door"},
        {"item_id": 2, "chrono_id": 1, "object_name": "north door"},
        {"item_id": 3, "chrono_id": 2, "object_name": "north door"},
    ]
    compiled, history, rejected = compile_transforms(
        transforms,
        allowed_channels=["rooms"],
        ledger_items=ledgers,
        allowed_item_ids=[1, 2, 3],
        specialist="spatial",
    )

    assert rejected == []
    assert [row["chrono_id"] for row in history] == [1, 2, 2]
    assert len(history) == len(transforms)
    assert compiled["rooms"]["hall"]["name"] == "Hall"
    assert compiled["rooms"]["hall"]["desc"] == "north door"
    assert compiled["rooms"]["hall"]["state"] == {"open": True}
    assert history[1]["supersedes"] == [{
        "channel": "rooms", "object": "hall",
        "prior_chrono_id": 1, "prior_item_id": 2,
    }]
    assert history[1]["patch"]["rooms"]["hall"]["state"] == {
        "open": True}


def test_recompiler_preserves_list_transforms_and_replaces_scalar_state():
    compiled, history, rejected = compile_transforms(
        [{"item_id": 1, "patch": {
            "following_ops": [{"op": "start", "who": "Mara"}],
            "location": "North Road",
        }}],
        allowed_channels=["following_ops", "location"],
        ledger_items=[{"item_id": 1, "chrono_id": 1,
                       "object_name": "Mara"}],
        specialist="spatial",
    )
    assert rejected == []
    assert compiled["following_ops"] == [{
        "op": "start", "who": "Mara", "from_event": 1}]
    assert compiled["location"] == "North Road"
    assert len(history) == 1


def test_the_beat_record_is_the_rows_not_a_template():
    """`resolved_event` is what memory files as the beat's event. The template
    it replaced glued whole declarations onto "attempts to": chat 123 turn 9
    filed "Hinami attempts to Hinami's tails sway a bit in interest.." for
    every mind in the scene."""
    out = {"ledgers": [
        {"source_entity_id": "persona:10", "event": "Hinami's tails sway.",
         "categories": []},
        {"source_entity_id": "persona:10", "event": "Show me.",
         "categories": ["speech"]},
        {"source_entity_id": "character:58", "act": "asks",
         "event": "whether she is ready", "categories": ["speech"]},
        {"source_entity_id": "character:58",
         "event": "Pulls the TARDIS door open wide.",
         "categories": ["contacts", "entities"]},
    ]}
    names = {"persona:10": "Hinami", "character:58": "The Doctor"}
    assert director._beat_event_sentences(out, names) == [
        "Hinami's tails sway.",
        'Hinami says: "Show me."',
        "The Doctor asks: whether she is ready",
        "The Doctor: Pulls the TARDIS door open wide.",
    ]
    assert director._beat_event_sentences({"ledgers": []}, names) == []


def test_the_beats_movement_is_the_last_arrival():
    """Scratch play 2026-09-14, chat 3 turn 5: "crossed the hall alone and
    let himself into the study" -- rows hall then study; the first was taken
    and the commit left him in the hall while the page described the study."""
    rows = [
        {"movement": {"mover": "self", "to_room": "hall", "arrives": True}},
        {"event": "shuts the door"},
        {"movement": {"mover": "self", "to_room": "study", "arrives": True}},
    ]
    assert director._final_movement(rows)["to_room"] == "study"
    refused = rows + [{"movement": {"mover": "self", "to_room": "cellar",
                                    "arrives": False}}]
    assert director._final_movement(refused)["to_room"] == "study"
    assert director._final_movement([]) is None


def test_a_present_character_a_line_targets_is_a_reactor():
    """Scratch play 2026-09-14, chat 2 turns 15-16: "Mrs Marrow. Come down."
    targeted character:2; the Director named only character:3 and the woman
    the line was for was never asked, so the page read "no answer came"."""
    cast = [{"id": 2, "name": "Odile"}, {"id": 3, "name": "Bram"}]
    rows = [
        {"categories": ["speech"], "targets": ["character:2", "persona:9"]},
        {"categories": ["stations"], "targets": ["character:3"]},
        {"categories": ["speech"], "targets": ["character:2", "character:7"]},
    ]
    assert director._addressed_characters(rows, cast) == [2]
    assert director._addressed_characters([], cast) == []


def test_a_row_about_a_doorway_in_view_is_routed_to_rooms():
    """Scratch play 2026-09-14, chat 4 turns 7-8: "slid the bolt back",
    "cracked it the width of her hand", "pushed the door wide" were routed
    as contacts and contact actions; the edge stayed shut while the page
    described it open, and the creature on the other side never entered
    the aperture. The join is the engine's own edge name."""
    sc = {"rooms": {
        "scullery": {"name": "Scullery", "adjacent": [
            {"to": "yard", "barrier": "closed_door",
             "name": "the back door to the yard"},
            {"to": "kitchen", "barrier": "open_door"}]},
        "yard": {"name": "Farmyard", "adjacent": [
            {"to": "scullery", "barrier": "closed_door",
             "name": "the back door to the yard"}]}}}
    out = {"ledgers": [
        {"object_name": "yard door", "event": "pushed the door wide",
         "categories": ["contact_action_ops"]},
        {"object_name": "door", "event": "slid the bolt back",
         "categories": ["contacts"]},
        {"object_name": "tallow candle", "event": "lifted the candle",
         "categories": ["contact_action_ops"]},
        {"object_name": "the open doorway", "event": "stepped through",
         "categories": []},
    ]}
    routed = director._route_doorway_rows(sc, out, ["scullery"])
    assert routed == ["yard door", "door", "the open doorway"]
    assert "rooms" in out["ledgers"][0]["categories"]
    assert "rooms" not in out["ledgers"][2]["categories"]
    assert director._route_doorway_rows(sc, {"ledgers": []}, ["scullery"]) == []


def test_the_item_id_is_the_directors_handle_and_the_chrono_id_is_the_row():
    """The owner, 2026-09-15: item_id is the Director's handle for a thing,
    the same on every row about it, so every hand's transforms reconcile
    onto that thing in chronological order whether or not the world knows
    it. The engine keeps the handle AS WRITTEN -- no merging by name, no
    renumbering a shared handle -- and only fills a missing one. Chrono is
    the row's own key, unique to it."""
    from agents.director import normalize_causal_ledger
    out = {"ledgers": [
        {"chrono_id": 1, "item_id": 1, "object_name": "Hinami", "source_entity_id": "persona:10",
         "event": "Uhm hello?", "categories": ["speech"]},
        {"chrono_id": 2, "item_id": 1, "object_name": "Hinami", "source_entity_id": "persona:10",
         "event": "looks at Mirelle", "look": "Mirelle", "categories": ["attention"]},
        {"chrono_id": 3, "item_id": 2, "object_name": "a new thing", "source_entity_id": "character:72",
         "event": "produces a thing the world has no record of", "categories": ["entities"]},
        {"chrono_id": 3, "item_id": None, "object_name": "hinami", "source_entity_id": "character:72",
         "event": "a row with no handle", "categories": ["poses"]},
    ]}
    normalize_causal_ledger(out)
    rows = out["causal_ledger"]
    assert [r["item_id"] for r in rows[:3]] == [1, 1, 2], "handles kept as written"
    assert rows[3]["item_id"] == 3, "a missing handle is filled past the highest, never merged by name"
    assert [r["chrono_id"] for r in rows] == [1, 2, 3, 4], "a repeated chrono gets the row its own"
    spans = out["sequence"]
    assert spans[0]["items"][0]["id"] == spans[1]["items"][0]["id"] == 1


def test_transforms_join_by_the_row_and_order_by_its_chronology():
    """Two rows about one object, two hands' transforms attached by
    position: each cites its row's chrono id, and the recompiler orders
    by it rather than by the object's first appearance."""
    rows = [
        {"item_id": 1, "chrono_id": 1, "object_name": "door"},
        {"item_id": 1, "chrono_id": 2, "object_name": "door"},
    ]
    transforms = [
        {"chrono_id": 2, "item_id": 1, "patch": {"rooms": {"hall": {"state": {"open": True}}}}},
        {"chrono_id": 1, "item_id": 1, "patch": {"rooms": {"hall": {"state": {"open": False}}}}},
    ]
    compiled, history, rejected = compile_transforms(
        transforms, allowed_channels=["rooms"], ledger_items=rows,
        allowed_item_ids=[1, 2], specialist="spatial")
    assert rejected == []
    assert [row["chrono_id"] for row in history] == [1, 2]
    assert compiled["rooms"]["hall"]["state"]["open"] is True, "the later row wins"


def test_causal_social_patch_preserves_resolve_evidence_outside_state_diff(
        temp_db, monkeypatch, prose_director):
    """The encoder's `public_evidence` write since 2026-09-27; the social
    hand's before."""
    from tests.director_fakes import _make_ctx, _speech_interp, prose_resolve_agent
    evidence = {"source_id": "speech:The Stranger:0", "speech_act": "greeting"}
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "Quiet night.",
         "state_diff": {"public_evidence": [evidence]}}))
    ctx = _make_ctx(temp_db, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)
    history = out["orchestration"]["transform_history"]
    rows = [row for row in history if row.get("patch", {}).get("public_evidence")]
    assert len(rows) == 1
    assert rows[0]["patch"]["public_evidence"][0]["source_id"] == evidence["source_id"]
    assert "public_evidence" not in out["state_diff"]
    assert "public_evidence" in out["orchestration"]["specialists"]["social"]["channels_filled"]

