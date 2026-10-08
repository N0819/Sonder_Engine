"""The narrator's grammar offers only the fields the model writes.

`NarratorOutput` declares `text` (the engine's alias of `prose`) and
`paragraph_count` (engine-written by `preprocess_llm_output`) so both survive
validation into the stored variant. The wire schema kept both, and an optional
string field in a grammar is an invitation: on the Brackwater run (chat 166,
2026-10-07) 15 of 40 narrator calls wrote the page a second time into `text`,
and one (capture 6416, turn 4592) went on from `text` into a 5,521-tag
`<fragment>` loop until the 50,000-token cap. `llm_quality._WIRE_OMITTED`
takes both out of what the model is asked to write; every reader keeps
working because nothing reads them from the model.
"""

from llm import llm_quality
from llm.schemas import NarratorOutput, _fields, validate_llm_output_strict


def test_the_narrators_grammar_offers_no_engine_written_field():
    schema = llm_quality._step_json_schema("narrator")
    assert set(schema["properties"]) == {"prose", "new_specifics"}
    assert "text" not in schema.get("required", [])
    assert "paragraph_count" not in schema.get("required", [])
    # The page is still required and non-empty on the wire.
    assert schema["required"] == ["prose"]
    assert schema["properties"]["prose"]["minLength"] == 1


def test_the_model_still_declares_both_for_the_stored_variant():
    """Omitted from the WIRE only: validation and storage keep them."""
    fields = set(_fields(NarratorOutput))
    assert {"text", "paragraph_count"} <= fields


def test_an_answer_that_sends_them_anyway_still_validates():
    """A provider that samples without the grammar may still send either
    field; it is accepted exactly as before, and the paragraph count stays
    the engine's own."""
    report = validate_llm_output_strict(
        "narrator", {"prose": "<p>one</p><p>two</p>", "text": "copy",
                     "paragraph_count": 9})
    assert report.valid
    assert report.output["paragraph_count"] == 2
    assert report.output["prose"] == "one\n\ntwo"


def test_a_field_the_schema_does_not_declare_is_left_alone():
    schema = {"type": "object", "properties": {"prose": {"type": "string"}}}
    assert llm_quality._wire_omitted("narrator", schema) is schema


def test_no_other_step_loses_a_field():
    """The omission is a table the engine owns, keyed by step."""
    assert set(llm_quality._WIRE_OMITTED) == {"narrator"}
    character = llm_quality._step_json_schema("character_bare")
    assert character and character.get("properties")
