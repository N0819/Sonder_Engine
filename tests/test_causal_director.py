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
    assert len(shared) < 4_500


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


def test_specialists_are_prompted_for_multiple_transforms_not_direct_diffs():
    for name in ("body", "social", "contact", "objects", "spatial"):
        sheet = specialist_prompt(name, [], "en")
        assert "emit a transform" in sheet
        assert "same array position" in sheet
        assert "Do not emit item_id or chrono_id" in sheet
        assert 'Output STRICT JSON {"results":[' in sheet


def test_wire_grammars_expose_only_the_current_contracts():
    for step in ("director_interpret", "director_resolve"):
        schema = _step_json_schema(step)
        assert set(schema["properties"]) == {"ledgers"}
    for step in ("director_body", "director_social", "director_contact",
                 "director_objects", "director_spatial"):
        schema = _step_json_schema(step)
        assert set(schema["properties"]) == {"results", "notes"}


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
