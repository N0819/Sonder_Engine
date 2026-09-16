from types import SimpleNamespace

from agents import director
from llm.llm_quality import _step_json_schema
from llm.prompts import prose_author_prompt, specialist_prompt
from llm.schemas import semantic_output_errors, validate_llm_output_strict
from world.causality import compile_transforms


_span_items = director._span_items
normalize_causal_ledger = director.normalize_causal_ledger
span_owners = director.span_owners


def test_both_director_invocations_share_one_minimal_contract():
    shared = prose_author_prompt(set())
    assert "Convert event_inputs into ordered event ledgers" in shared
    assert "state_diff" not in shared
    assert "resolved_event" not in shared
    assert "player_declaration" not in shared
    # The contract explains the job and includes a complete four-row
    # worked example. Bound its size without forcing causal instructions
    # back into the ambiguous shorthand exposed by live prose stress.
    assert len(shared) < 12_000


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
    visible = director._specialist_ledger(ledger)
    assert visible["targets"] == ["Nera", "brass box"]
    assert not {"item_id", "item_ids", "chrono_id"} & visible.keys()


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


def test_both_language_contracts_use_item_lists_and_distinct_public_targets():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for language in ("en", "ja"):
        text = (root / "language_packs" / language / "cards" / "system_prompts"
                / "causal_director.txt").read_text()
        example = json.loads(text[text.rfind('{"ledgers":'):].strip())
        rows = example["ledgers"]
        payload = {"event_inputs": [{"entity_id": "character:11",
                    "authority_mode": "world_author", "events": [
                        {"event_id": "scene:1", "type": "raw_input"}]}],
                   "identity_index": {"character:11": "Mara", "character:12": "Ivo"}}
        for stage in ("director_interpret", "director_resolve"):
            report = validate_llm_output_strict(stage, example, source_payload=payload)
            assert report.valid, report.errors
            schema = _step_json_schema(stage)
            required = schema.get("$defs", schema.get("definitions"))["CausalLedgerEntry"]["required"]
            assert all(set(required) <= row.keys() for row in rows)
        assert [row["chrono_id"] for row in rows] == [1, 2, 3, 4]
        assert rows[0]["item_ids"] == [1, 2]
        assert rows[0]["item_names"] == ["red tin", "blue tin"]
        assert rows[2]["item_ids"] == [1] and rows[3]["item_ids"] == [2]
        assert rows[1]["event"] == "Keep them shut,"
        assert rows[1]["categories"] == ["speech"]
        assert set(rows[2]["categories"]) == {"inventory_ops", "contact_ops", "stations"}
        assert "bench" in rows[2]["targets"] and "bench" not in rows[2]["item_names"]
        for row in rows:
            assert not {"item_id", "object_name", "authority_mode", "kind"} & row.keys()
            public = director._specialist_ledger(row)
            assert not {"item_ids", "item_id", "chrono_id"} & public.keys()
        assert "engine: speech, attention" in text
        target_line = next(line for line in text.splitlines() if line.startswith("- targets"))
        assert "world/identity" in target_line and "item_ids" in target_line


def _spatial_interior_payload(interior_rooms=None, *, movement=True):
    ledger = {
        "source_entity_id": "persona:primary",
        "object_name": "TARDIS", "targets": ["tardis"],
        "categories": ["rooms", *( ["positions"] if movement else [])],
    }
    if movement:
        ledger["movement"] = {
            "mover": "self", "to_room": "tardis", "arrives": True}
    return {
        "player": "The Stranger",
        "identity_index": {"persona:primary": "The Stranger"},
        "positions": {"The Stranger": "alley", "tardis": "alley"},
        "entity_interiors": {
            "tardis": {"name": "TARDIS",
                       "interior_rooms": list(interior_rooms or [])},
        },
        "ledgers": [ledger],
    }


def test_spatial_cannot_call_an_unmade_interior_already_true():
    report = validate_llm_output_strict(
        "director_spatial",
        {"results": [{"transforms": [], "status": "already_true"}],
         "notes": []},
        source_payload=_spatial_interior_payload(),
    )
    assert not report.valid
    assert any("must mint an interior" in error for error in report.errors)


def test_spatial_mints_a_furnished_interior_and_places_the_mover():
    report = validate_llm_output_strict(
        "director_spatial",
        {"results": [{"transforms": [
            {"patch": {"rooms": {"tardis_console": {
                "name": "TARDIS Console Room",
                "desc": "A many-sided control room around a central console.",
                "light": "bright", "size": "vast",
                "parent_entity": "tardis", "adjacent": [],
            }}}},
            {"patch": {"positions": {
                "The Stranger": "tardis_console"}}},
        ], "status": "encoded"}], "notes": []},
        source_payload=_spatial_interior_payload(),
    )
    assert report.valid, report.errors


def test_spatial_mints_a_revealed_interior_before_anyone_enters():
    report = validate_llm_output_strict(
        "director_spatial",
        {"results": [{"transforms": [{"patch": {"rooms": {
            "tardis_console": {
                "name": "TARDIS Console Room",
                "desc": "A many-sided control room around a central console.",
                "light": "bright", "size": "vast",
                "parent_entity": "tardis", "adjacent": [],
            },
        }}}], "status": "encoded"}], "notes": []},
        source_payload=_spatial_interior_payload(movement=False),
    )
    assert report.valid, report.errors


def test_spatial_cannot_call_an_unmade_revealed_interior_already_true():
    report = validate_llm_output_strict(
        "director_spatial",
        {"results": [{"transforms": [], "status": "already_true"}],
         "notes": []},
        source_payload=_spatial_interior_payload(movement=False),
    )
    assert not report.valid
    assert any("must mint an interior" in error for error in report.errors)


def test_spatial_position_accepts_a_causal_identity_join():
    payload = _spatial_interior_payload()
    payload["player"] = "Hinami"
    payload["identity_index"] = {"persona:10": "Hinami"}
    payload["ledgers"][0]["source_entity_id"] = "persona:10"
    payload["ledgers"][0]["movement"]["mover"] = "persona:10"
    payload["positions"] = {"Hinami": "alley", "tardis": "alley"}
    report = validate_llm_output_strict(
        "director_spatial",
        {"results": [{"transforms": [
            {"patch": {"rooms": {"tardis_console": {
                "name": "TARDIS Console Room",
                "desc": "A many-sided control room around a central console.",
                "light": "bright", "size": "vast",
                "parent_entity": "tardis", "adjacent": [],
            }}}},
            {"patch": {"positions": {"Hinami": "tardis_console"}}},
        ], "status": "encoded"}], "notes": []},
        source_payload=payload,
    )
    assert report.valid, report.errors


def test_spatial_reuses_an_existing_interior():
    payload = _spatial_interior_payload(["tardis_console"])
    payload["ledgers"][0]["movement"]["to_room"] = "tardis_console"
    report = validate_llm_output_strict(
        "director_spatial",
        {"results": [{"transforms": [{"patch": {"positions": {
            "The Stranger": "tardis_console"}}}], "status": "encoded"}],
         "notes": []},
        source_payload=payload,
    )
    assert report.valid, report.errors


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


def test_specialist_results_are_positional_and_match_every_input_ledger():
    payload = {"ledgers": [{"object_name": "coat"},
                           {"object_name": "scarf"}]}
    report = validate_llm_output_strict(
        "director_body",
        {"results": [{
            "transforms": [{"patch": {"attire": {
                "Mara": {"remove": ["coat"]}}}}],
            "status": "encoded",
        }]},
        source_payload=payload,
    )
    assert not report.valid
    assert any("one entry per input ledger" in error
               for error in report.errors)


def test_specialist_cores_teach_the_positional_envelope_without_private_ids():
    import json

    for name in ("body", "social", "contact", "objects", "spatial"):
        sheet = specialist_prompt(name, [], "en")
        assert "same array position" in sheet
        assert "item_id" not in sheet and "chrono_id" not in sheet
        assert "required_channels" in sheet and "assigned_hands" in sheet
        assert "Output STRICT JSON" in sheet
        example = json.loads(next(line for line in sheet.splitlines()
                                  if line.startswith('{"results":')))
        assert set(example) == {"results", "notes"}
        assert all({"transforms", "status", "settled"} <= row.keys()
                   for row in example["results"])


def test_wire_grammars_expose_only_the_current_contracts():
    for step in ("director_interpret", "director_resolve"):
        schema = _step_json_schema(step)
        assert set(schema["properties"]) == {"ledgers"}
        row = schema.get("$defs", schema.get("definitions"))["CausalLedgerEntry"]
        assert {"event", "resolution_notes", "categories", "item_ids", "item_names"} <= set(row["required"])
        assert not {"item_id", "object_name", "authority_mode"} & set(row["properties"])
        assert row["properties"]["event"]["minLength"] == 1
        assert row["properties"]["resolution_notes"]["minLength"] == 1
    for step in ("director_body", "director_social", "director_contact",
                 "director_objects", "director_spatial"):
        schema = _step_json_schema(step)
        assert set(schema["properties"]) == {"results", "notes"}
        definitions = schema.get("$defs", schema.get("definitions"))
        transform = definitions["LedgerPatchTransform"]
        assert {"item", "patch"} <= set(transform["required"])
        patch = transform["properties"]["patch"]
        assert patch["additionalProperties"] is False
        assert patch["minProperties"] == 1
        assert "state_diff" not in patch["properties"]
        assert "status" in definitions["LedgerTransformResult"]["required"]


def test_current_director_rejects_invented_sources_and_unknown_channels():
    payload = {"event_inputs": [{
        "entity_id": "entity:1", "authority_mode": "autonomous",
        "events": [{"event_id": "source:1", "type": "action"}],
    }]}
    ledger = {
        "chrono_id": 1, "item_id": 1, "object_name": "door",
        "source_entity_id": "invented:2", "authority_mode": "autonomous",
        "source_event_id": "source:1", "kind": "action",
        "event": "The door opens.", "commitment": "asserted",
        "resolution_notes": "The door is open.",
        "categories": ["imaginary_channel"],
    }
    report = validate_llm_output_strict(
        "director_resolve", {"ledgers": [ledger]}, source_payload=payload)
    assert not report.valid
    # An invented source is still refused -- it is neither a supplied source
    # nor an identity the payload names. (A KNOWN identity that supplied no
    # input of its own IS accepted now; natural prose narrates other people,
    # and their rows belong to them. See test_speech_is_a_channel.)
    assert any("neither a supplied source nor a known identity" in error
               for error in report.errors)
    # An unroutable channel is REPORTED, not fatal: `_unrouted_rulings`
    # already names it per span on the next beat, and losing one span beats
    # losing the beat it was in. See
    # test_speech_is_a_channel.TestAGuardMayNotDestroyABeatItCannotJustify.
    assert any("nothing answers to" in str(note)
               for note in report.warnings), report.warnings


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


def test_specialist_matches_distinguish_wearers_from_positioned_garments(monkeypatch):
    from agents import director_fanout as fanout
    monkeypatch.setattr(fanout, "survival_enabled", lambda _chat: False)
    scene = {
        "rooms": {"bay": {"name": "Bay"}},
        "positions": {"Nia": "bay", "jacket": "bay", "automaton": "bay"},
        "entities": {
            "jacket": {"name": "Orange work jacket"},
            "automaton": {"name": "Automaton"},
        },
        "attire": {"Nia": {"wearing": ["Orange work jacket"]}},
        "scales": {"automaton": {"ratio": 1}},
    }
    view = {"source": "causal_ledger", "player": "Nia", "cast": [], "spans": [{
        "type": "action", "categories": ["attire"],
        "item_ids": [1, 2], "item_names": ["Nia", "Orange work jacket"],
        "object_name": "Orange work jacket", "chrono_id": 1,
        "targets": ["jacket", "Nia", "automaton"],
    }]}
    payload = fanout._specialist_payload(
        "body", SimpleNamespace(chat={"id": 1}), scene, view,
        {"identity_index": {"persona:1": "Nia"}})
    row = payload["ledgers"][0]
    assert row["target_matches"]["jacket"] == [{
        "kind": "entity", "world_key": "jacket", "world_name": "Orange work jacket"}]
    assert row["target_matches"]["Nia"][0]["kind"] == "body"
    assert {r["kind"] for r in row["target_matches"]["automaton"]} == {"body", "entity"}
    garment = next(r for r in row["world_matches"] if r["kind"] == "garment")
    assert garment["worn_by"] == "Nia"
    assert not {"chrono_id", "item_id", "item_ids"} & row.keys()


def test_causal_social_patch_preserves_resolve_evidence_outside_state_diff(temp_db, monkeypatch):
    from tests.test_director_orchestration import _make_ctx, _fake_agent, _speech_interp
    calls = []
    evidence = {"source_id": "speech:The Stranger:0", "speech_act": "greeting"}
    responses = {
        "director_resolve": {"ledgers": [{
            "chrono_id": 1, "item_ids": [1], "item_names": ["The Stranger"],
            "source_entity_id": "persona:primary", "event": "Quiet night.",
            "resolution_notes": "A greeting is spoken.",
            "categories": ["speech", "public_evidence"],
        }]},
        "director_social": {"results": [{"status": "encoded", "transforms": [
            {"item": "The Stranger", "patch": {"public_evidence": [evidence]}}
        ]}]},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)
    history = out["orchestration"]["transform_history"]
    rows = [row for row in history if row.get("patch", {}).get("public_evidence")]
    assert len(rows) == 1
    assert rows[0]["patch"]["public_evidence"][0]["source_id"] == evidence["source_id"]
    assert "public_evidence" not in out["state_diff"]
    assert "public_evidence" in out["orchestration"]["specialists"]["social"]["channels_filled"]
