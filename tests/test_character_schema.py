"""Tests for native and legacy character schemas."""

from character_schema import (
    CHARACTER_SCHEMA,
    CHARACTER_VERSION,
    default_character_data,
    normalize_character_data,
    normalize_persona_data,
    senses_as_text,
)


def test_v4_psychology_and_outfit_defaults_migrate_v2():
    normalized = normalize_character_data({
        "schema": CHARACTER_SCHEMA,
        "version": 2,
        "data": {
            "identity": {"name": "Legacy Native"},
            "psychology": {
                "traits": [{"name": "watchful", "strength": 7}],
                "values": [{"name": "loyalty", "priority": -2}],
            },
        },
    })

    assert CHARACTER_VERSION == 4
    assert normalized["psychology"]["traits"][0]["strength"] == 1.0
    assert normalized["psychology"]["traits"][0]["activation_cues"] == []
    assert normalized["psychology"]["values"][0]["priority"] == 0.0
    assert normalized["psychology"]["self_model"]["beliefs"] == []
    assert normalized["psychology"]["learning"]["associations"] == []
    assert normalized["embodiment"]["interoception"]["pleasure_sensitivity"] == 0.5
    assert normalized["initial_state"]["hedonic"]["pain"] == 0.0
    assert normalized["initial_outfit"] == {"wearing": [], "state": []}

def test_default_character_is_agnostic():
    sheet = default_character_data("Test")

    assert sheet["identity"]["name"] == "Test"
    assert sheet["embodiment"]["senses"][0]["acuity"] == "ordinary"
    assert sheet["psychology"]["traits"] == []
    assert (
        sheet["social"]["baseline_stances"]["unknown_person"]["trust"]
        == 0.0
    )

def test_legacy_sheet_normalizes():
    legacy = {
        "name": "Legacy",
        "appearance": "A plainly dressed person.",
        "core": {
            "traits": ["careful"],
            "values": ["accuracy"],
            "self_image": "A reliable observer.",
        },
        "active_state": {
            "mood": "neutral",
            "goal": "",
        },
        "abilities": [
            {
                "name": "Observation",
                "level": "expert",
            },
        ],
        "private_history": [
            {
                "content": "secret",
                "known_by": [],
            },
        ],
    }

    normalized = normalize_character_data(legacy)

    assert normalized["identity"]["name"] == "Legacy"
    assert normalized["psychology"]["traits"][0]["name"] == "careful"
    assert (
        normalized["embodiment"]["visible"]["summary"]
        == "A plainly dressed person."
    )
    assert normalized["competence"]["abilities"][0]["level"] == "expert"
    assert (
        normalized["knowledge"]["private_history"][0]["content"]
        == "secret"
    )

def test_native_export_envelope_unwraps():
    sheet = default_character_data("Envelope")
    payload = {
        "schema": CHARACTER_SCHEMA,
        "version": 2,
        "data": sheet,
        "source": {"format": "native"},
    }

    normalized = normalize_character_data(payload)

    assert normalized["identity"]["name"] == "Envelope"

def test_native_character_defaults_missing_fields():
    normalized = normalize_character_data({
        "identity": {"name": "Partial"},
        "psychology": {"traits": []},
    })

    assert normalized["identity"]["name"] == "Partial"
    assert normalized["simulation"]["tier"] == "mid"
    assert normalized["knowledge"]["access_tags"] == ["common"]
    assert normalized["opening"]["first_message"] == ""

def test_native_persona_defaults_missing_fields():
    normalized = normalize_persona_data({
        "identity": {"name": "Partial Player"},
        "narration": {},
    })

    assert normalized["identity"]["name"] == "Partial Player"
    assert normalized["competence"]["abilities"] == []
    assert normalized["narration"]["voice_setting"] == ""
    assert normalized["initial_outfit"] == {"wearing": [], "state": []}


def test_native_adjacent_clothing_moves_out_of_body_appearance():
    character = normalize_character_data({
        "identity": {"name": "Dressed"},
        "embodiment": {
            "visible": {"summary": "Tall, freckled, with copper hair."},
            "clothing": "a green coat; mud-streaked boots",
        },
    })
    persona = normalize_persona_data({
        "identity": {"name": "Player"},
        "narration": {},
        "embodiment": {
            "visible": {"summary": "Short, with a shaved head."},
            "outfit": ["a blue shirt", "black trousers"],
        },
    })

    assert character["initial_outfit"]["wearing"] == [
        "a green coat", "mud-streaked boots",
    ]
    assert "coat" not in character["embodiment"]["visible"]["summary"]
    assert persona["initial_outfit"]["wearing"] == [
        "a blue shirt", "black trousers",
    ]
    assert "shirt" not in persona["embodiment"]["visible"]["summary"]

def test_native_private_history_coerces_bare_strings():
    # private_knowledge_for (scene.py) only accepts dict entries with a
    # "content" key. Every other list-of-facts field on this schema
    # (traits, values, abilities, senses) tolerates a legacy bare-string
    # form; private_history must too, or a character authored with plain
    # strings (e.g. hand-typed via the API, or the character generator
    # deviating from its prompted shape) silently ends up with zero
    # private knowledge and nothing signals why.
    normalized = normalize_character_data({
        "identity": {"name": "Secretive"},
        "knowledge": {
            "private_history": [
                "A plain-string secret only this character should carry.",
                {"content": "An already-structured secret.", "known_by": ["Ally"]},
                "",
            ],
        },
    })

    entries = normalized["knowledge"]["private_history"]

    assert entries == [
        {
            "content": "A plain-string secret only this character should carry.",
            "about": "",
            "known_by": [],
        },
        {"content": "An already-structured secret.", "known_by": ["Ally"]},
    ]

def test_legacy_character_private_history_coerces_bare_strings():
    normalized = normalize_character_data({
        "name": "Legacy Secretive",
        "private_history": ["A legacy-schema plain-string secret."],
    })

    assert normalized["knowledge"]["private_history"] == [
        {"content": "A legacy-schema plain-string secret.", "about": "", "known_by": []},
    ]

def test_native_persona_private_history_coerces_bare_strings():
    normalized = normalize_persona_data({
        "identity": {"name": "Secretive Player"},
        "knowledge": {"private_history": ["A plain-string persona secret."]},
    })

    assert normalized["knowledge"]["private_history"] == [
        {"content": "A plain-string persona secret.", "about": "", "known_by": []},
    ]

def test_senses_as_text_string_passthrough():
    assert (
        senses_as_text("ordinary human senses")
        == "ordinary human senses"
    )

def test_senses_as_text_structured():
    senses = [
        {
            "channel": "vision",
            "acuity": "ordinary",
            "range": "ordinary",
            "notes": "",
        },
        {
            "channel": "hearing",
            "acuity": "keen",
            "range": "ordinary",
            "notes": "can hear heartbeats",
        },
    ]

    text = senses_as_text(senses)

    assert "keen hearing" in text
    assert "can hear heartbeats" in text

def test_senses_as_text_rejects_invalid_container():
    assert senses_as_text(None) == "ordinary senses"
    assert senses_as_text({"channel": "vision"}) == "ordinary senses"

class TestASheetIsReadableOnEitherPydantic:
    """A number where a psychology field declared prose.

    `_normalize_psychology` calls `parse_obj` with no try/except, and it sits
    on the READ path of every character accessor via
    `normalize_character_data`. Pydantic 1 quietly read `"expression": 3` as
    `"3"`; Pydantic 2 raises, which is a 500 on character save and a
    character that cannot be loaded on any later turn -- for a card that had
    been perfectly loadable the day before the dependency resolved
    differently. `pydantic>=1.10.13,<3` is a real promise, so the tolerance
    has to be the engine's own and not the installed major's.
    """

    def test_a_number_where_a_trait_declared_prose(self):
        from character_schema import normalize_character_data, character_psychology
        sheet = normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "expression": 3}]}})
        assert character_psychology(sheet)["traits"][0]["expression"] == "3"

    def test_it_reaches_every_profile_the_sheet_nests(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "values": [{"name": 1}],
            "self_model": {"beliefs": [{"belief": 7, "source": 1.5}]},
            "coping": {"strategies": [{"name": "freeze", "costs": 2}]},
            "learning": {"associations": [{"cue": 5}]},
        }}))
        assert psych["values"][0]["name"] == "1"
        assert psych["self_model"]["beliefs"][0]["belief"] == "7"
        assert psych["self_model"]["beliefs"][0]["source"] == "1.5"
        assert psych["coping"]["strategies"][0]["costs"] == "2"
        assert psych["learning"]["associations"][0]["cue"] == "5"

    def test_the_numeric_fields_are_still_numbers(self):
        """The generic coercion must not reach a field that declared one."""
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "strength": "0.8"}]}}))
        assert psych["traits"][0]["strength"] == 0.8

    def test_the_list_fields_still_split_a_comma_string(self):
        """The field-specific pre-validators still run first."""
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "activation_cues": "dark, cold"}]}}))
        assert psych["traits"][0]["activation_cues"] == ["dark", "cold"]

    def test_extension_keys_still_survive(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "house_rule": "keep me"}]}}))
        assert psych["traits"][0]["house_rule"] == "keep me"

class TestEveryProfileListToleratesTheSameSpellings:
    """`traits`/`values` were taught to survive a non-sequence;
    `coping.strategies` and `learning.associations` were not, and raised a
    bare `TypeError` out of `_normalize_psychology` — which has no `try` and
    sits on the read path of every character accessor. Pydantic 2 does not
    rewrap `TypeError` as `ValidationError`, so it escapes every caller that
    catches the latter."""

    def test_a_scalar_where_strategies_were_declared(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data(
            {"psychology": {"coping": {"strategies": 5}}}))
        assert psych["coping"]["strategies"] == []

    def test_a_scalar_where_associations_were_declared(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data(
            {"psychology": {"learning": {"associations": 5}}}))
        assert psych["learning"]["associations"] == []

    def test_one_strategy_written_as_itself(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data(
            {"psychology": {"coping": {"strategies": "freeze"}}}))
        assert psych["coping"]["strategies"][0]["name"] == "freeze"

    def test_one_association_written_as_itself(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data(
            {"psychology": {"learning": {"associations": {"cue": "smoke"}}}}))
        assert psych["learning"]["associations"][0]["cue"] == "smoke"

class TestAProfileMapKeepsBothItsKeyAndItsContents:
    """A map keyed by the profile's own name is a spelling models reach for,
    and the old code half-handled it by accident: iterating a dict yielded
    its KEYS, so `{"freeze": {...}}` produced a strategy named "freeze" and
    silently threw away everything under it. It iterated a bare string the
    same way, so `"freeze"` became six strategies named f, r, e, e, z, e.
    """

    def test_a_map_of_strategies_keeps_every_strategy_and_its_fields(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "coping": {"strategies": {"freeze": {"trigger": "threat"},
                                      "flee": {"trigger": "noise"}}}}}))
        assert [(s["name"], s["trigger"]) for s in psych["coping"]["strategies"]] == [
            ("freeze", "threat"), ("flee", "noise")]

    def test_a_map_of_associations_keeps_its_cues(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "learning": {"associations": {"smoke": {"strength": 0.8}}}}}))
        assert [(a["cue"], a["strength"]) for a in psych["learning"]["associations"]] == [
            ("smoke", 0.8)]

    def test_a_map_of_traits_keeps_its_names(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": {"wary": {"strength": 0.8}}}}))
        assert [(t["name"], t["strength"]) for t in psych["traits"]] == [("wary", 0.8)]

    def test_a_map_of_beliefs_keeps_the_belief_and_its_confidence(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "self_model": {"beliefs": {"the door was open": {"confidence": 0.7}}}}}))
        belief = psych["self_model"]["beliefs"][0]
        assert (belief["belief"], belief["confidence"]) == ("the door was open", 0.7)

    def test_one_profile_written_as_an_object_is_not_mistaken_for_a_map(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "coping": {"strategies": {"name": "freeze", "trigger": "threat"}}}}))
        assert [(s["name"], s["trigger"]) for s in psych["coping"]["strategies"]] == [
            ("freeze", "threat")]

    def test_a_single_strategy_named_by_a_string_is_one_strategy(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "coping": {"strategies": "freeze"}}}))
        assert [s["name"] for s in psych["coping"]["strategies"]] == ["freeze"]

class TestAStructuredValueInAProseSlot:
    """`LenientModel` flattens a structured value into prose; the psychology
    profiles did not, and `_normalize_psychology` has no `try` — so a nested
    object in `belief` or `expression` was a 500 on character save, on both
    majors."""

    def test_a_nested_object_where_prose_was_declared_is_flattened(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "expression": {"when": "cornered"}}]}}))
        assert psych["traits"][0]["expression"] == "cornered"

    def test_a_prose_less_structure_degrades_to_empty_rather_than_raising(self):
        from character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "self_model": {"beliefs": [{"belief": {"a": {"b": [1, {"c": 2}]}}}]}}}))
        assert psych["self_model"]["beliefs"][0]["belief"] == ""
