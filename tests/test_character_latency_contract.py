"""Character latency surfaces that outlived the full card.

The full card's seven-field kernel, its compact-wire A/B and its prompt
ceiling went with it (2026-09-27); the bare card's length is pinned in
`tests/test_character_bare.py`. What stays: the grammar carries constraints
and no annotation text, the card's name-bearing line sits behind a prefix
every mind shares, and per-turn reads are made once.
"""

import json


def test_provider_schema_drops_annotations_not_constraints():
    from llm import llm_quality, schemas

    model = schemas.SCHEMA_MAP["character_bare"]
    builder = getattr(model, "model_json_schema", None)
    raw = builder() if builder is not None else model.schema()
    offered = llm_quality._step_json_schema("character_bare")

    raw_size = len(json.dumps(raw, separators=(",", ":")))
    offered_size = len(json.dumps(offered, separators=(",", ":")))
    # 933 bytes on the wire against 2,392 raw, measured 2026-09-27.
    assert offered_size < 1500
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
    assert "sequence" in offered.get("properties")
    assert offered.get("$defs") or offered.get("definitions")


def test_the_bare_card_keeps_its_name_behind_a_shared_prefix():
    """Everything before the name-bearing line is the same for every mind,
    so a provider can cache it; the line sits just before the reply shape."""
    from llm.prompts import bare_character_prompt

    for language in ("en", "ja"):
        lines = bare_character_prompt(language).splitlines()
        identity = next(i for i, line in enumerate(lines) if "{name}" in line)
        output = next(i for i, line in enumerate(lines)
                      if '"want"' in line and '"sequence"' in line)

        assert identity > len(lines) // 2
        assert identity + 1 == output
        assert "{name}" not in "\n".join(lines[:identity])


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
