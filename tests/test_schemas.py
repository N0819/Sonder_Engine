"""Tests for LLM output preprocessing/validation in schemas.py."""

from llm.schemas import validate_llm_output_strict

def _base_character_output(considered_responses):
    return {
        "sequence": [],
        "considered_responses": considered_responses,
    }

def test_character_considered_responses_accepts_plain_strings():
    report = validate_llm_output_strict(
        "character",
        _base_character_output(["Stay quiet.", "Speak up."]),
    )

    assert report.valid
    assert report.output["considered_responses"] == [
        "Stay quiet.", "Speak up.",
    ]

def test_character_considered_responses_coerces_structured_entries():
    # considered_responses is internal deliberation scratch with no
    # downstream reader (see schemas.py::_coerce_considered_responses).
    # Some models emit structured {"response": ..., "score": ...} entries
    # instead of the declared list[str]; this used to hard-fail the whole
    # character step (and therefore the whole turn) on a field nothing
    # actually consumes.
    report = validate_llm_output_strict(
        "character",
        _base_character_output([
            {"response": "Stay quiet.", "score": 0.4},
            {"text": "Speak up."},
            {"content": ""},
            42,
        ]),
    )

    assert report.valid, report.errors
    assert report.output["considered_responses"] == [
        "Stay quiet. (score: 0.4)",
        "Speak up.",
        "42",
    ]

def test_director_resolve_conditions_as_empty_list_is_coerced():
    # Live crash: state_diff.conditions is typed dict[str, list[dict]],
    # but a model reporting "nothing persistent happened" returned []
    # instead of {} -- both mean "empty" to a model, but pydantic rejects
    # the type mismatch outright, hard-failing the whole turn.
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Nothing persistent occurs.",
            "state_diff": {"conditions": []},
        },
    )

    assert report.valid, report.errors
    assert report.output["state_diff"]["conditions"] == {}

def test_director_resolve_conditions_as_list_of_dicts_is_grouped():
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Mara is wounded.",
            "state_diff": {
                "conditions": [
                    {"condition_id": "bleeding_mara", "subject_id": "Mara", "kind": "wound"},
                ],
            },
        },
    )

    assert report.valid, report.errors
    assert report.output["state_diff"]["conditions"] == {
        "bleeding_mara": [
            {"condition_id": "bleeding_mara", "subject_id": "Mara", "kind": "wound"},
        ],
    }

def test_director_resolve_condition_scalar_state_is_safely_normalized():
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Mara falls asleep.",
            "state_diff": {"conditions": {"sleeping_mara": [{
                "subject_id": "Mara", "kind": "awareness",
                "state": "asleep",
            }]}},
        },
    )

    assert report.valid, report.errors
    condition = report.output["state_diff"]["conditions"]["sleeping_mara"][0]
    assert condition["state"] == {}

def test_director_resolve_state_diff_dict_fields_as_empty_lists_are_coerced():
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Nothing changes.",
            "state_diff": {
                "positions": [], "rooms": [], "entities": [],
                "overlays": [], "attire": [],
            },
        },
    )

    assert report.valid, report.errors
    sd = report.output["state_diff"]
    assert sd["positions"] == {} and sd["rooms"] == {}
    assert sd["entities"] == {} and sd["overlays"] == {}
    assert sd["attire"] == {}

def test_director_establish_dict_fields_as_empty_lists_are_coerced():
    report = validate_llm_output_strict(
        "director_establish",
        {
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Mara": "hall"},
            "entities": [],
            "attire": [],
            "entity_states": [],
        },
    )

    assert report.valid, report.errors
    assert report.output["entities"] == {}
    assert report.output["attire"] == {}
    assert report.output["entity_states"] == {}


def test_every_worked_example_validates_against_the_schema_it_illustrates():
    """An example is instruction, and a wrong one instructs wrongly.

    `OUTPUT_EXAMPLES[step]` is handed to the model verbatim as
    `required_json_example` on every repair and every fallback candidate -- so
    a call that just failed validation is answered with an object the same
    validator also rejects. Two were live when this test was written:
    `scene_life` omitted the required `speech.speaker` on its first entry, and
    `director_establish` failed its own semantic check with empty `rooms` and
    `positions`. Both were teaching a shape that cannot commit.

    This is the second time a wrong example has been found (the first cost a
    complete 4,000-token resolve, whose repair was handed the same broken
    example that caused the failure and could not converge), so the guard is
    the class rather than the two.
    """
    from llm.schemas import OUTPUT_EXAMPLES, validate_llm_output_strict

    broken = {}
    for step_key, example in sorted(OUTPUT_EXAMPLES.items()):
        report = validate_llm_output_strict(step_key, example)
        if not report.valid:
            broken[step_key] = report.errors[:4]
    assert not broken, (
        "worked examples that their own validator rejects: "
        + "; ".join(f"{step}: {errors}" for step, errors in broken.items()))


def test_specialist_channel_shapes_match_what_the_models_declare():
    """The empty-value coercion is chosen from a hand-kept list, and a hand-
    kept list drifts. `comms_ops` was declared `list[CommsOp]` and classified
    as a dict channel, so an empty `comms_ops: []` -- the ordinary way a model
    says "no voice channel changed this beat" -- was rewritten to `{}` on the
    way in. Inert only because `LenientModel` reversed it on the way out,
    which is a second mechanism covering for the first rather than a reason
    the first is right.
    """
    from llm import schemas

    wrong = []
    for step_key, channels in schemas.SPECIALIST_CHANNELS.items():
        fields = schemas._fields(schemas.SCHEMA_MAP[step_key])
        for channel in channels:
            declared = schemas._declared(fields[channel])
            if declared.is_list:
                expected = "list"
            elif declared.expects_object:
                expected = "dict"
            else:
                continue
            classified = (
                "dict" if channel in schemas._SPECIALIST_DICT_CHANNELS
                else "list" if channel in schemas._SPECIALIST_LIST_CHANNELS
                else "unclassified")
            if classified != expected:
                wrong.append(f"{step_key}.{channel}: declared {expected}, "
                             f"coerced as {classified}")
    assert not wrong, "; ".join(wrong)


def test_observation_defaults_are_the_values_the_compactor_omits():
    """`Observation`'s own comment says absent means the default, and names
    `composer.OBSERVATION_DEFAULTS` as the projection that omits them. They
    disagreed on all three advisory axes -- intensity 0.5 vs 0.35, suddenness
    0.0 vs 0.1, ambiguity 0.5 vs 0.15 -- so a compacted observation read back
    through the schema came out saying something the compactor never said.
    """
    from agents.composer import OBSERVATION_DEFAULTS
    from llm.schemas import Observation, _declared, _fields

    fields = _fields(Observation)
    for name, expected in OBSERVATION_DEFAULTS.items():
        assert _declared(fields[name]).default == expected, name
    # `null` and an omitted key are two spellings of "not said" and must land
    # on the same number: the pre-validator fallback is the other half.
    for name in ("intensity", "suddenness", "ambiguity"):
        parsed = Observation(**{"observation_id": "current:x:0", name: None})
        assert getattr(parsed, name) == OBSERVATION_DEFAULTS[name], name


def test_the_prose_authors_example_shows_only_channels_it_still_owns():
    """`director_resolve` is the step key the PROSE AUTHOR's call runs under.
    Its example carried 20 `state_diff` channels the six specialists took over
    and omitted three of the six the author kept, so the object it was told to
    imitate on every repair was the dead monolith's. Whatever it writes in a
    delegated channel is replaced by that channel's owner in the same fan-out,
    so the instruction costs output budget to produce nothing.
    """
    from llm.schemas import OUTPUT_EXAMPLES, SPECIALIST_CHANNELS, StateDiff
    from llm.schemas import _fields

    delegated = {channel for channels in SPECIALIST_CHANNELS.values()
                 for channel in channels}
    owned = set(_fields(StateDiff)) - delegated
    shown = set(OUTPUT_EXAMPLES["director_resolve"]["state_diff"])
    assert not shown - owned, (
        "the prose author's example teaches delegated channels: "
        + ", ".join(sorted(shown - owned)))
    # `following_ops` is the one owned channel the author must NOT author --
    # it is projected deterministically from interpretation and character
    # decisions -- so showing it would be its own instruction to invent one.
    assert "following_ops" not in shown
    assert {"time", "weather", "location", "consequences"} <= shown


def test_the_character_repair_example_names_the_psychology_tier():
    """A key absent from the object a repair is told to imitate reads as
    "not part of the answer". The example named none of `intent_ops`,
    `project_ops`, `follow_op`, `drive_shift` or `manifest`, all five of
    which the character sheet asks for on every call -- `project_ops` in
    particular has never once been emitted in the live corpus.

    Legacy `speech`/`action`/`actions` stay OUT: they are the pre-`sequence`
    spelling, and showing them would teach the shape the sheet exists to
    replace.
    """
    from llm.schemas import OUTPUT_EXAMPLES

    example = OUTPUT_EXAMPLES["character"]
    for key in ("intent_ops", "project_ops", "follow_op", "drive_shift",
                "manifest"):
        assert key in example, key
    for key in ("speech", "action", "actions"):
        assert key not in example, key


def test_every_specialist_example_shows_exactly_the_channels_it_owns():
    """The same rule as the prose author's, one level in. A specialist's
    example is its `required_json_example` on repair, and a channel missing
    from it reads as one it does not answer for -- `comms_ops` was absent
    from the spatial specialist's, the same channel the published spatial
    sheet had lost. A channel it does NOT own would be an invitation to
    write into another hand's diff.
    """
    from llm.schemas import OUTPUT_EXAMPLES, SPECIALIST_CHANNELS

    for step_key, channels in SPECIALIST_CHANNELS.items():
        example = OUTPUT_EXAMPLES[step_key]
        shown = set(example) - {"notes"}
        assert shown == set(channels), (
            f"{step_key}: shows {sorted(shown)}, owns {sorted(channels)}")


def test_no_schema_model_is_declared_without_anything_reaching_it():
    """A Pydantic model nothing references is worse than no model at all.

    Nothing validates against it, so it states a shape the engine does not
    enforce while reading, to anyone opening this file, as the contract. That
    That was not hypothetical: the body specialist's sheet asked the Director
    for `tick_interval_seconds` while the only place that field existed in
    code was `PersistentCondition`, a model no call has ever validated. The
    resolution was to give the field a real reader (`world.mechanics.
    _tick_interval`, the due-tick sweep) and DELETE the model, not to extend
    it -- an unvalidated shape does not become a contract by growing.

    Twenty-nine such models were deleted: the fiction/time/authority models,
    the early entity ontology, and the shapes naming the
    fiction_worlds/fiction_locations/transit_edges/world_placements tables
    the movement/space phases decommissioned. Reachability is computed the
    way it has to be for this file -- a model is live if any `.py` outside it
    names it, or if anything at module level here does (SCHEMA_MAP, the
    helpers, the aliases), or if a live model's own body annotates a field
    with it.
    """
    import ast
    import collections
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1]
    source = (root / "llm/schemas.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    pattern = re.compile(
        r"\b(" + "|".join(sorted(classes, key=len, reverse=True)) + r")\b")

    seed = set()
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.as_posix() == "llm/schemas.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:                       # pragma: no cover - unreadable
            continue
        seed.update(m.group(1) for m in pattern.finditer(text))

    lines = source.splitlines()

    def _names_in(node):
        body = "\n".join(
            lines[node.lineno - 1:(node.end_lineno or node.lineno)])
        return {m.group(1) for m in pattern.finditer(body)}

    edges = collections.defaultdict(set)
    for name, node in classes.items():
        edges[name] = _names_in(node) - {name}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            seed.update(_names_in(node))

    reached, stack = set(), list(seed)
    while stack:
        name = stack.pop()
        if name in reached:
            continue
        reached.add(name)
        stack.extend(edges.get(name, ()))

    # Kept deliberately, each for a stated reason. Removing a name from this
    # allowlist means deleting the model, not silencing the test.
    allowed = {
        # `PersistentCondition` used to sit here, held while one open
        # question stood: build the due-tick sweep, or drop the prompt
        # field, the NULL `next_tick` column and the index that serves no
        # query. The sweep was built (`world.mechanics` pass (c1)), which
        # spent the exemption -- the shape a tick declares is now read and
        # clamped by `world.mechanics._tick_spec` from the lenient dict the
        # channel actually carries, so the unvalidated model went with the
        # other twenty-nine. One fewer name here is the point of the test.
        # Fixtures: tests/test_schema_leniency.py exercises the shared
        # coercion through these two, and tests/test_speech_concealment.py
        # through SpeechElement.
        "CausalRegime", "FictionFrame", "SpeechElement",
    }
    unreached = sorted(set(classes) - reached - allowed)
    assert not unreached, (
        f"{unreached} are declared in llm/schemas.py and reachable from "
        "nothing -- no SCHEMA_MAP entry, no other model's field, no module "
        "outside the file. Wire it up or delete it; a shape nothing "
        "validates is not a contract.")


def test_greeting_interpret_asks_only_for_what_the_launch_reads():
    """The greeting extraction declared eleven fields and `story.greetings`
    read two.

    The other nine were a whole scene graph -- rooms, positions, entities,
    attire, player_room -- plus location, scene_description, character_state
    and notes. None was a gap waiting to be wired: `start_story` stores the
    greeting prose as the chat's scenario, so `director_establish` builds the
    scene from the SAME passage one turn later with the engine's full payload
    behind it. Every card ingest paid for a second, weaker pass at that job
    and threw the answer away.

    Two assertions, because the defect can come back from either side: a
    field re-added to the schema that nothing reads, or a prompt that goes on
    asking for one the schema dropped.
    """
    import re

    from llm.schemas import GreetingInterpret
    from language_runtime import installed_language_packs

    declared = set(GreetingInterpret.__fields__)
    # `minds` joined when the extraction became per-person (every entry is
    # routed by `start_story._seed_minds`); `knowledge_seeds` stays as v1's
    # shape, folded into the card character's mind at launch. Anything beyond
    # these three is a field nothing reads -- the defect coming back.
    assert declared == {"time", "minds", "knowledge_seeds"}, (
        "GreetingInterpret declares a field story/greetings.py does not read; "
        "wire the reader or drop the field")

    # A stored extraction written by the older extractor still reads: extra
    # keys are ignored here as everywhere else in this module.
    legacy = {
        "location": "a dim tavern", "time": "night",
        "scene_description": "Rain against the shutters.",
        "rooms": {"tavern": {"name": "The Tavern"}},
        "positions": {"Kara": "tavern"}, "entities": {},
        "attire": {"Kara": {"summary": "a travel-worn cloak"}},
        "character_state": {"mood": "wary"}, "player_room": "tavern",
        "notes": "", "knowledge_seeds": [],
    }
    report = validate_llm_output_strict("greeting_interpret", legacy)
    # The v1 shape still READS -- extra keys dropped, known ones kept -- so a
    # hand-stamped stored extraction routes at launch. It is no longer
    # semantically VALID as fresh model output: a greeting always contains at
    # least its own character's mind, and an extraction that seeded nobody is
    # the silent-empty failure the semantic gate exists to retry.
    assert set(report.output) == declared
    assert report.output["time"] == "night"
    assert not report.valid and any("minds" in e for e in report.errors)

    # And every pack's output line names those fields and no others.
    for pack in installed_language_packs(refresh=True).values():
        if not pack.story:
            continue
        prompt = pack.card("system_prompts")["prompts"]["greeting_interpret"]
        for field in declared:
            assert field in prompt, (
                f"{pack.id} never names {field!r}, which the schema requires")
        for dropped in ("rooms", "positions", "player_room",
                        "scene_description", "character_state"):
            # Word-bounded: "Dispositions" in the psychology clause is not a
            # request for `positions`.
            assert not re.search(r"\b%s\b" % dropped, prompt), (
                f"{pack.id} still asks for {dropped!r}, which nothing reads")


# ---------------------------------------------------------------------------
# The Pydantic-major seam. Reported by the Directive team against
# `reorganization`, and the failure it names is the reason these are here:
# `agents/director_scopes._schema_list_channels` read `field.outer_type_`,
# which exists ONLY on Pydantic 1. On a Pydantic-2 install `_LIST_DELEGATED`
# was the empty set, so `_normalized_channel_value` coerced every op-list
# channel a specialist wrote to `{}` -- dispatched, paid for, discarded in
# silence. The suite did not catch it because the suite runs on Pydantic 1
# while the venv the engine serves from runs Pydantic 2: a green gate saying
# nothing at all about the installed engine.
#
# Both tests below are written to fail on EITHER major. The first names the
# roll literally, because a test that re-derives the answer the same way the
# code does agrees with the code about being empty.
# ---------------------------------------------------------------------------

def test_list_shaped_fields_reads_the_same_shapes_on_either_pydantic():
    """A bare `list` is list-shaped; a parametrized one is; a dict is not.

    `list_shaped_fields` is deliberately WIDER than `_declared(f).is_list`,
    which counts only a parametrized list because it drives the
    wrap-a-single-item coercion and that needs a known item type. Channel
    shape asks a different question, and `StateDiff.world_facts` is annotated
    bare -- reading it through `is_list` dropped exactly that one channel, so
    the fix for an empty set nearly shipped as a set missing one.
    """
    from typing import Optional

    from pydantic import BaseModel, Field

    from llm.schemas import list_shaped_fields

    class Shapes(BaseModel):
        bare: list = Field(default_factory=list)
        parametrized: list[dict] = Field(default_factory=list)
        keyed: dict = Field(default_factory=dict)
        scalar: str = ""
        optional_scalar: Optional[int] = None

    assert list_shaped_fields(Shapes) == {"bare", "parametrized"}


def test_every_list_valued_director_channel_is_registered_as_one():
    """The roll is named, not re-derived. An empty `_LIST_DELEGATED` passes
    any assertion that computes the expected set the way the code does."""
    from agents.director import _DELEGATED_CHANNELS, _LIST_DELEGATED
    from llm.schemas import StateDiff, list_shaped_fields

    expected = {
        "cast_changes", "introductions", "world_facts", "contact_ops",
        "substance_ops", "remove_entities", "inventory_ops", "artifact_ops",
        "remove_rooms", "remove_adjacent", "crowd_ops", "courier_ops",
        "telling_ops", "ratified_claims",
        "contradicted_claims", "comms_ops",
    }
    assert expected <= _LIST_DELEGATED, sorted(expected - _LIST_DELEGATED)

    # And it stays derived: a channel `StateDiff` declares as a list, owned by
    # a specialist, must be registered as one without anybody editing the roll
    # above. The roll is the floor; the schema is the source.
    schema_lists = list_shaped_fields(StateDiff)
    assert schema_lists, "list_shaped_fields returned nothing at all"
    for channel in _DELEGATED_CHANNELS:
        if channel in schema_lists:
            assert channel in _LIST_DELEGATED, channel
