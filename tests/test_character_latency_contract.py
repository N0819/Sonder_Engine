"""Feature-preserving character latency surfaces and the isolated wire A/B."""

import json


def test_provider_schema_drops_annotations_not_constraints():
    from llm import llm_quality, schemas

    builder = getattr(schemas.CharacterOutput, "model_json_schema", None)
    raw = builder() if builder is not None else schemas.CharacterOutput.schema()
    offered = llm_quality._step_json_schema("character")

    raw_size = len(json.dumps(raw, separators=(",", ":")))
    offered_size = len(json.dumps(offered, separators=(",", ":")))
    # Pydantic 1 emits far more annotation text than Pydantic 2, so a ratio
    # against the raw schema measured the dependency's verbosity rather than
    # the provider payload. Both supported majors must keep the actual wire
    # under the same useful ceiling while still proving annotations came off.
    assert offered_size < 8500
    assert offered_size < raw_size * 0.75

    def annotations(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in llm_quality._SCHEMA_ANNOTATIONS:
                    yield key
                yield from annotations(item)
        elif isinstance(value, list):
            for item in value:
                yield from annotations(item)

    assert not list(annotations(offered))
    assert offered.get("properties")
    assert offered.get("$defs") or offered.get("definitions")


def test_compact_character_wire_is_experimental_and_complete():
    from llm import llm_quality

    control = llm_quality._step_json_schema("character")
    compact = llm_quality._step_json_schema("character", wire_variant="compact")
    control_fields = set(control["properties"])
    compact_fields = set(compact["properties"])

    assert llm_quality._CHARACTER_COMPACT_WIRE_FIELDS <= control_fields
    assert not (llm_quality._CHARACTER_COMPACT_WIRE_FIELDS & compact_fields)
    for canonical in ("sequence", "present_evidence_used",
                      "memory_evidence_used", "response_candidates",
                      "appraisal", "active_state"):
        assert canonical in compact_fields


def test_runtime_prompt_moves_identity_behind_the_stable_prefix():
    from llm.prompts import character_prompt

    payload = {"self": {"name": "Vessel"}, "memory": {},
               "perception": {}, "decision": {}}
    for language in ("en", "ja"):
        prompt = character_prompt(payload, language=language)
        lines = prompt.splitlines()
        identity = next(i for i, line in enumerate(lines) if "{name}" in line)
        output = next(i for i, line in enumerate(lines)
                      if '"present_evidence_used"' in line
                      and '"response_candidates"' in line)

        assert identity > len(lines) // 2
        assert identity + 1 == output
        assert "{name}" not in "\n".join(lines[:identity])


def test_compact_prompt_removes_only_considered_response_scratch():
    from llm.prompts import character_prompt

    payload = {"self": {"name": "Vessel"}, "memory": {},
               "perception": {}, "decision": {}}
    control = character_prompt(payload)
    compact = character_prompt(payload, wire_variant="compact")

    assert '"considered_responses":[],' in control
    assert '"considered_responses":[],' not in compact
    assert compact == control.replace('"considered_responses":[],', "", 1)


def test_unanswered_question_snapshot_avoids_a_second_history_read(monkeypatch):
    from agents import character

    calls = []

    def no_rows(sql, args=(), **kwargs):
        calls.append((sql, args))
        return []

    monkeypatch.setattr(character, "q", no_rows)
    cache = {}
    first = character._unanswered_question_note(
        3, "Vessel", 7, 9, None, cache=cache)
    second = character._unanswered_question_note(
        3, "Vessel", 7, 9, None, cache=cache)

    assert first == second == {}
    assert len(calls) == 1


def test_social_wire_cases_supply_earned_memories_and_score_conduct():
    from tools.character_wire_ab import _social_memory_cases

    cases = {name: (payload, scorer)
             for name, payload, scorer in _social_memory_cases()}
    examples = {
        "social-memory:kept-confidence": (
            "That is Bram's to tell. Ask him; I will not expose a confidence.",
            "His hands shake because he is frightened."),
        "social-memory:earned-distrust": (
            "No. I keep the key until you account for the copy and break-in.",
            "She gives Cyra the archive key."),
        "social-memory:shared-code": (
            "Tamsin snuffs the lamp and moves for the back door.",
            "What does blue lantern mean? Is that our code phrase?"),
        "social-memory:repaired-hurt": (
            "You did not abandon me. You left to fetch the physician.",
            "You abandoned me there, and I will never forgive you."),
    }

    assert set(cases) == set(examples)
    for name, (payload, scorer) in cases.items():
        memories = payload["memory"]["recent_episodes"]
        assert memories
        assert all(memory["memory_ref"].startswith("event:social-")
                   for memory in memories)
        positive, negative = examples[name]
        assert scorer(positive)
        assert not scorer(negative)

    assert cases["social-memory:kept-confidence"][1](
        "If he wanted you to know, he'd tell you himself.")
    assert cases["social-memory:earned-distrust"][1](
        "You said that last time. The key came back copied.")
