"""Tests for native and legacy character schemas."""

from story.character_schema import (
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
    assert normalized["initial_outfit"] == {"wearing": [], "state": [],
                                            "regions": {}}

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
    assert normalized["initial_outfit"] == {"wearing": [], "state": [],
                                            "regions": {}}


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
        from story.character_schema import normalize_character_data, character_psychology
        sheet = normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "expression": 3}]}})
        assert character_psychology(sheet)["traits"][0]["expression"] == "3"

    def test_it_reaches_every_profile_the_sheet_nests(self):
        from story.character_schema import normalize_character_data, character_psychology
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
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "strength": "0.8"}]}}))
        assert psych["traits"][0]["strength"] == 0.8

    def test_the_list_fields_still_split_a_comma_string(self):
        """The field-specific pre-validators still run first."""
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "activation_cues": "dark, cold"}]}}))
        assert psych["traits"][0]["activation_cues"] == ["dark", "cold"]

    def test_extension_keys_still_survive(self):
        from story.character_schema import normalize_character_data, character_psychology
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
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data(
            {"psychology": {"coping": {"strategies": 5}}}))
        assert psych["coping"]["strategies"] == []

    def test_a_scalar_where_associations_were_declared(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data(
            {"psychology": {"learning": {"associations": 5}}}))
        assert psych["learning"]["associations"] == []

    def test_one_strategy_written_as_itself(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data(
            {"psychology": {"coping": {"strategies": "freeze"}}}))
        assert psych["coping"]["strategies"][0]["name"] == "freeze"

    def test_one_association_written_as_itself(self):
        from story.character_schema import normalize_character_data, character_psychology
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
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "coping": {"strategies": {"freeze": {"trigger": "threat"},
                                      "flee": {"trigger": "noise"}}}}}))
        assert [(s["name"], s["trigger"]) for s in psych["coping"]["strategies"]] == [
            ("freeze", "threat"), ("flee", "noise")]

    def test_a_map_of_associations_keeps_its_cues(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "learning": {"associations": {"smoke": {"strength": 0.8}}}}}))
        assert [(a["cue"], a["strength"]) for a in psych["learning"]["associations"]] == [
            ("smoke", 0.8)]

    def test_a_map_of_traits_keeps_its_names(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": {"wary": {"strength": 0.8}}}}))
        assert [(t["name"], t["strength"]) for t in psych["traits"]] == [("wary", 0.8)]

    def test_a_map_of_beliefs_keeps_the_belief_and_its_confidence(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "self_model": {"beliefs": {"the door was open": {"confidence": 0.7}}}}}))
        belief = psych["self_model"]["beliefs"][0]
        assert (belief["belief"], belief["confidence"]) == ("the door was open", 0.7)

    def test_a_map_of_traits_to_bare_strengths_keeps_its_names(self):
        """`{"wary": 0.7}` is the shortest way to write a named trait and the
        one spelling that lost the name: the map expansion only fired when
        EVERY value was a dict, so a name-to-strength map fell through to the
        single-profile branch and became one anonymous trait carrying `wary`
        as a stray key. Caught by reading a captured character payload, where
        the sheet read as populated -- traits was non-empty -- and named
        nobody.
        """
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": {"wary": 0.7, "patient": 0.3}}}))
        assert [(t["name"], t["strength"]) for t in psych["traits"]] == [
            ("wary", 0.7), ("patient", 0.3)]

    def test_a_map_mixing_bare_strengths_and_objects_keeps_every_name(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": {"wary": 0.7, "patient": {"strength": 0.3,
                                                "expression": "waits"}}}}))
        assert [(t["name"], t["strength"], t["expression"]) for t in psych["traits"]] == [
            ("wary", 0.7, ""), ("patient", 0.3, "waits")]

    def test_a_map_of_values_to_bare_priorities_keeps_its_names(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "values": {"honesty": 0.9}}}))
        assert [(v["name"], v["priority"]) for v in psych["values"]] == [
            ("honesty", 0.9)]

    def test_a_profile_object_whose_numbers_are_bare_is_still_one_profile(self):
        """The discriminator is whether the KEYS are the profile's own fields,
        not whether the values are scalars -- otherwise every ordinary sheet
        entry would be read as a map of two traits named `name` and `strength`.
        """
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": {"name": "wary", "strength": 0.7}}}))
        assert [(t["name"], t["strength"]) for t in psych["traits"]] == [("wary", 0.7)]

    def test_one_profile_written_as_an_object_is_not_mistaken_for_a_map(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "coping": {"strategies": {"name": "freeze", "trigger": "threat"}}}}))
        assert [(s["name"], s["trigger"]) for s in psych["coping"]["strategies"]] == [
            ("freeze", "threat")]

    def test_a_single_strategy_named_by_a_string_is_one_strategy(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "coping": {"strategies": "freeze"}}}))
        assert [s["name"] for s in psych["coping"]["strategies"]] == ["freeze"]

class TestAStructuredValueInAProseSlot:
    """`LenientModel` flattens a structured value into prose; the psychology
    profiles did not, and `_normalize_psychology` has no `try` — so a nested
    object in `belief` or `expression` was a 500 on character save, on both
    majors."""

    def test_a_nested_object_where_prose_was_declared_is_flattened(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "traits": [{"name": "wary", "expression": {"when": "cornered"}}]}}))
        assert psych["traits"][0]["expression"] == "cornered"

    def test_a_prose_less_structure_degrades_to_empty_rather_than_raising(self):
        from story.character_schema import normalize_character_data, character_psychology
        psych = character_psychology(normalize_character_data({"psychology": {
            "self_model": {"beliefs": [{"belief": {"a": {"b": [1, {"c": 2}]}}}]}}}))
        assert psych["self_model"]["beliefs"][0]["belief"] == ""


class TestOneNormalizationPerCard:
    """Review 2026-09-07 C14. Normalization rebuilds the whole default tree and
    merges the card over it -- 5.3 ms on chat 117's stored 26 KB card -- and
    thirty-nine accessors were each paying it to read one field.
    `normalized_character_from_text` memoises the derivation on the stored
    sheet TEXT, and `normalize_character_data` marks its own product so the
    second and later reads short-circuit. These test the two ways a memo goes
    wrong: a stale answer, and a shared answer somebody mutated."""

    CARD = {"identity": {"name": "Vesper", "aliases": ["Ves"]},
            "psychology": {"drive": {"essence": "keep the light on"}},
            "embodiment": {"visible": {"summary": "a tall woman"}}}

    def _text(self, card=None):
        import json
        return json.dumps(card or self.CARD)

    def test_the_memo_gives_what_a_fresh_normalization_gives(self):
        import json
        from story.character_schema import normalized_character_from_text
        for card in (self.CARD,
                     {"name": "Legacy", "appearance": "a short man",
                      "senses": "keen hearing"},
                     # A shape the repair has to lift back out of `psychology`.
                     {"psychology": {"identity": {"name": "Parked",
                                                  "aliases": ["P"]}}}):
            text = json.dumps(card)
            memo = dict(normalized_character_from_text(text))
            fresh = dict(normalize_character_data(json.loads(text)))
            memo_id, fresh_id = memo.pop("identity"), fresh.pop("identity")
            assert memo == fresh
            memo_id.pop("uid")
            fresh_id.pop("uid")
            assert memo_id == fresh_id

    def test_an_edited_sheet_is_a_different_key(self):
        """The whole of the invalidation: the key IS the stored text, so a card
        somebody edited cannot come back as the card they edited."""
        import copy
        import json
        from story.character_schema import (character_name,
                                            normalized_character_from_text)
        edited = copy.deepcopy(self.CARD)
        edited["identity"]["name"] = "Vesper Holt"
        assert character_name(normalized_character_from_text(self._text())) == "Vesper"
        assert character_name(
            normalized_character_from_text(json.dumps(edited))) == "Vesper Holt"

    def test_a_caller_owns_what_it_receives(self):
        """A cached value handed out by reference is one mutation away from
        every later reader seeing somebody else's edit."""
        from story.character_schema import normalized_character_from_text
        first = normalized_character_from_text(self._text())
        first["identity"]["name"] = "MUTATED"
        first["psychology"]["drive"]["essence"] = "MUTATED"
        second = normalized_character_from_text(self._text())
        assert second["identity"]["name"] == "Vesper"
        assert second["psychology"]["drive"]["essence"] == "keep the light on"

    def test_a_minted_uid_stays_freshly_minted(self):
        """`cast_entity_id` is built on normalization minting a NEW uid every
        call for a card that authors none; a memo that froze it would give two
        cards made from one blank template the same identity."""
        import json
        from story.character_schema import normalized_character_from_text
        text = self._text()
        first = normalized_character_from_text(text)["identity"]["uid"]
        second = normalized_character_from_text(text)["identity"]["uid"]
        assert first.startswith("char_") and second.startswith("char_")
        assert first != second
        authored = json.dumps({"identity": {"name": "V", "uid": "char_authored"},
                               "psychology": {}})
        assert (normalized_character_from_text(authored)["identity"]["uid"]
                == "char_authored")
        assert (normalized_character_from_text(authored)["identity"]["uid"]
                == "char_authored")

    def test_normalization_recognises_its_own_product(self):
        import copy
        from story.character_schema import NormalizedCharacterSheet
        once = normalize_character_data(self.CARD)
        assert isinstance(once, NormalizedCharacterSheet)
        assert normalize_character_data(once) is once
        assert isinstance(copy.deepcopy(once), NormalizedCharacterSheet)
        # The escape hatch a caller that MUTATED a normalized sheet must use.
        assert not isinstance(dict(once), NormalizedCharacterSheet)
        again = dict(normalize_character_data(dict(once)))
        once_ = dict(once)
        once_.pop("identity")
        again.pop("identity")
        assert once_ == again

    def test_the_mark_never_reaches_storage(self):
        """It is a dict subclass precisely so that nothing about it survives
        `json.dumps` into a `characters.sheet` row."""
        import json
        stored = json.dumps(normalize_character_data(self.CARD))
        assert type(json.loads(stored)) is dict

    def test_a_row_with_no_readable_card_is_not_an_unnamed_body(self):
        from story.character_schema import normalized_character_of_row
        assert normalized_character_of_row({"sheet": "{not json"}) is None
        assert normalized_character_of_row({"id": 3}) is None
        assert normalized_character_of_row({"sheet": {"already": "parsed"}}) is None
        assert normalized_character_of_row(
            {"sheet": self._text()})["identity"]["name"] == "Vesper"

    def test_the_kind_dispatchers_still_read_the_card_as_stored(self):
        """`scene.senses_of` and its three siblings ask which KIND of card they
        hold by looking for a section only that kind has, and normalization
        gives every card a `psychology`. So a caller that normalizes once to
        share the answer must still hand these the sheet it read off the row --
        measured while wiring C14, and guarded here because the saving looks
        free."""
        from story.scene import scent_of, senses_of
        raw = {"name": "X", "senses": "keen hearing", "scent": "smoke"}
        assert senses_of(raw) == "keen hearing"
        assert scent_of(raw) == "smoke"
        normalized = normalize_character_data(raw)
        assert senses_of(normalized) != "keen hearing"
        assert scent_of(normalized) == ""

    def test_a_mind_is_not_rekeyed_by_the_uid_normalization_mints(self):
        """The two reads `character_step` takes BEFORE it normalizes, and why.
        `cast_entity_id` must answer the same string every turn and
        `identity_key` keys this mind's knowledge circles -- both fall back to
        a stable form for a card that authors no uid, and both would instead
        pick up a freshly minted one off a normalized sheet."""
        import inspect
        import json
        import agents.character as character
        from mind.knowledge_circles import identity_key
        from story.character_schema import (cast_entity_id,
                                            normalized_character_from_text)
        text = self._text()
        raw = json.loads(text)
        assert cast_entity_id(raw, 7) == "character:7"
        assert identity_key(raw) == "vesper"
        normalized = normalized_character_from_text(text)
        assert cast_entity_id(normalized, 7).startswith("char_")
        assert identity_key(normalized).startswith("char_")
        src = inspect.getsource(character.character_step)
        assert 'cast_entity_id(sh, row["id"])' in src
        assert "identity_key(raw_sheet)" in src


class TestNormalizationIsAFixedPoint:
    """Review 2026-09-07 C14 rework. `NormalizedCharacterSheet` lets a second
    normalization return the card unchanged, which is only sound if a second
    normalization WOULD have returned it unchanged. It would not have, for
    half the cards: the legacy conversion returned a hand-written native
    literal that a native pass then extended, so `normalize(x)` and
    `normalize(normalize(x))` were two different sheets and which one a reader
    saw depended on how many times the card had been through."""

    LEGACY = {"name": "Rook", "appearance": "a short man",
              "senses": "keen hearing", "abilities": ["baking"],
              "core": {"self_image": "a cook"},
              "active_state": {"mood": "wary", "goal": "find the key"}}

    def _uidless(self, sheet):
        import copy
        out = copy.deepcopy(dict(sheet))
        out.get("identity", {}).pop("uid", None)
        return out

    def test_a_legacy_card_is_where_a_second_pass_would_have_put_it(self):
        """The five slots the conversion literal never learned about. Each was
        added to `default_character_data` after it was written, and a second
        pass backfilled every one of them."""
        import copy
        once = normalize_character_data(copy.deepcopy(self.LEGACY))
        assert once["simulation"]["curiosity"] == 0.5
        assert once["knowledge"]["circles"] == []
        assert once["embodiment"]["scent"] == ""
        assert once["embodiment"]["interoception"]["responsive_regions"] == []
        assert once["psychology"]["capacity"] == ""

    def test_normalizing_twice_changes_nothing_for_either_branch(self):
        import copy
        for card in (self.LEGACY,
                     {"identity": {"name": "Native"},
                      "psychology": {"traits": ["kind"]}},
                     {"name": "Bare"},
                     {}):
            once = normalize_character_data(copy.deepcopy(card))
            twice = normalize_character_data(dict(once))
            assert self._uidless(once) == self._uidless(twice), card

    def test_a_name_read_off_a_normalized_card_is_the_name(self):
        """What every converted call site now depends on: `character_name` runs
        normalization itself, so it can only agree with a caller that
        normalized first if normalization is a fixed point."""
        from story.character_schema import character_name
        import copy
        raw = copy.deepcopy(self.LEGACY)
        assert character_name(raw) == character_name(
            normalize_character_data(copy.deepcopy(raw)))


class TestAnUnreadableCardIsNotAnUnnamedBody:
    """C14 rework. `character_name_from_text` answers "Unnamed" for a card that
    will not parse -- right for a label, wrong for frame surgery, where the
    four reads that decide which frame a body lands in used to abort on it.
    Two corrupt rows would otherwise be one "Unnamed" body: zoned together,
    and in `paradox._apply_toll` collapsed into a single map entry where one
    pays the other's toll."""

    def test_the_memo_raises_where_the_parse_did(self):
        import json
        import pytest
        from story.character_schema import (character_name_from_text,
                                            normalized_character_from_text)
        assert character_name_from_text("{not json") == "Unnamed"
        with pytest.raises(json.JSONDecodeError):
            normalized_character_from_text("{not json")

    def test_zoning_stops_on_a_card_it_cannot_read(self, monkeypatch):
        import json
        import pytest
        import world.spatial_frames as spatial_frames
        monkeypatch.setattr(spatial_frames, "active_cast",
                            lambda chat_id, frame_id: [
                                {"id": 1, "sheet": "{not json"},
                                {"id": 2, "sheet": "{not json"}])
        with pytest.raises(json.JSONDecodeError):
            spatial_frames._cast_char_ids_in_zone(1, None, {}, "here")
