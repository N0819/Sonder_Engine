"""Speech is a compiled channel, and no specialist may write it.

THE DEFECT THIS WAS WRITTEN FOR. The causal Director's ledger row had nowhere
to put words. `kind` was speech|action|event, `event` was specified as "short
objective occurrence", and `normalize_causal_ledger` projected `text = event`
-- while `composer._render_event` wraps a speech percept's body in literal
quotation marks. So a Director obeying its own prompt on "I ask Sera what
happened to the boat" produced `event: "asks Sera what happened to the boat"`,
and Sera's mind received:

    You says: "asks Sera what happened to the boat"

A description of an act, rendered as the act's own words. The engine already
had the right path for this -- `type: "communication"`, rendered through
`communication_surface` as indirect speech that invents no quotation -- and
the causal contract had made it unreachable.

The second half is the channel. Words come from exactly two places the engine
trusts: the player's raw input, which only the Director reads, and a
character's own declaration. A `speech` channel owned by a specialist would be
a third, so `speech` is compiled by the engine from the Director's ledger and
appears in no hand's channel list. `test_no_hand_can_author_a_line` is that
invariant, and it is the one test here that must never be relaxed.
"""

import pytest

from agents import composer
from agents.director import (
    ENGINE_CATEGORIES,
    SPECIALISTS,
    declared_speech_transforms,
    normalize_causal_ledger,
    speech_transforms,
    unnamed_work,
    _unrouted_rulings,
)
from llm import schemas
from world.causality import LIST_CHANNELS, compile_transforms


def _row(chrono_id, item_id, kind, event, **over):
    row = {
        "chrono_id": chrono_id, "item_id": item_id, "object_name": "Sera",
        "source_entity_id": "persona:1", "authority_mode": "world_author",
        "source_event_id": "turn:9:primary:raw", "kind": kind, "event": event,
        "observable": "", "commitment": "asserted", "targets": ["Sera"],
        "visibility": "overt", "conceal_from": [], "volume": "normal",
        "movement": None, "ability": "", "difficulty": "",
        "resolution_notes": "", "categories": ["speech"],
    }
    row.update(over)
    return row


def _projected(*rows):
    out = {"ledgers": list(rows)}
    normalize_causal_ledger(out)
    return out


def _heard(element, listener="Sera"):
    """What the element actually renders into another mind."""
    if element["type"] == "speech":
        percept = composer.speech_percept(
            {"speaker": "You", "exact_quote": element["text"],
             "volume": element.get("volume", "normal"), "tone": ""},
            {"same_room": True}, listener, display="You", can_see=True,
            order_key=1)
    else:
        percept = composer.communication_percept(
            element, {"same_room": True}, listener, display="You",
            can_see=True, order_key=1)
    return composer._render_event(percept)


class TestWordsAndDescriptionsAreDifferentActs:
    def test_supplied_words_are_rendered_as_the_words(self):
        out = _projected(_row(1, 1, "speech", "What happened to the boat?"))
        element = out["sequence"][0]
        assert element["type"] == "speech"
        assert element["text"] == "What happened to the boat?"
        assert '"What happened to the boat?"' in _heard(element)

    def test_a_described_act_never_becomes_a_quotation(self):
        """The regression. `kind: communication` carries a proposition, and
        no rendering of it may put quotation marks around the Director's
        description of the act."""
        out = _projected(_row(2, 2, "communication",
                              "what happened to the boat", act="ask"))
        element = out["sequence"][0]
        assert element["type"] == "communication"
        assert element["content"] == "what happened to the boat"
        heard = _heard(element)
        assert '"' not in heard, heard
        assert "asks what happened to the boat" in heard

    def test_the_act_verb_survives_onto_the_ledger_row(self):
        out = _projected(_row(1, 1, "communication", "the east route",
                              act="explain"))
        assert out["causal_ledger"][0]["act"] == "explain"
        assert out["sequence"][0]["act"] == "explain"

    def test_a_communication_with_no_verb_still_renders(self):
        """`act` is the one field a described row adds, so a Director that
        omits it must not produce an empty predicate."""
        out = _projected(_row(1, 1, "communication", "that the boat left"))
        assert out["sequence"][0]["act"] == "say"
        assert _heard(out["sequence"][0]).strip()


class TestTheAddresseeSurvives:
    """Resolve no longer authors `dialogue_log`, so every row is re-minted
    from a declaration -- and that re-mint hardcodes `intended_target: None`.
    The projection is now where the addressee comes from, and two readers
    depend on it: `spatial_frames` snaps orientation from it, and the
    unanswered-address percept ("T says nothing") is keyed on it."""

    @pytest.mark.parametrize("kind", ["speech", "communication"])
    def test_the_first_target_becomes_the_intended_target(self, kind):
        out = _projected(_row(1, 1, kind, "words", targets=["Sera", "Bryn"]))
        assert out["sequence"][0]["intended_target"] == "Sera"

    @pytest.mark.parametrize("kind", ["speech", "communication"])
    def test_an_untargeted_line_names_nobody(self, kind):
        out = _projected(_row(1, 1, kind, "words", targets=[]))
        assert out["sequence"][0]["intended_target"] is None


class TestTheChannelCompiles:
    def test_speech_is_an_ordered_list_channel(self):
        assert "speech" in LIST_CHANNELS
        assert schemas.StateDiff().speech == []

    def test_only_spoken_rows_become_transforms(self):
        rows = [_row(1, 1, "speech", "Hello."),
                _row(2, 2, "action", "opens the door", categories=["rooms"]),
                _row(3, 3, "event", "the lamp gutters", categories=[]),
                _row(4, 4, "communication", "about the boat", act="ask")]
        built = speech_transforms(rows)
        assert len(built) == 2
        assert [t["patch"]["speech"][0]["mode"] for t in built] \
            == ["quote", "described"]

    def test_a_spoken_row_with_nothing_said_mints_no_line(self):
        """A row the Director failed to fill is not a silence. Minting from
        it would put a body on the page opening its mouth to say nothing."""
        assert speech_transforms([_row(1, 1, "speech", "   ")]) == []

    def test_the_speaker_is_an_engine_identity_not_a_display_name(self):
        built = speech_transforms([_row(1, 1, "speech", "Hello.")])
        assert built[0]["patch"]["speech"][0]["speaker"] == "persona:1"

    def test_the_compiled_channel_carries_the_beats_chronology(self):
        built = speech_transforms([_row(2, 2, "speech", "second"),
                                   _row(1, 1, "speech", "first")])
        diff, _history, rejected = compile_transforms(
            built, allowed_channels=("speech",), specialist="engine")
        assert rejected == []
        assert [row["text"] for row in diff["speech"]] == ["first", "second"]
        assert [row["from_event"] for row in diff["speech"]] == [1, 2]

    def test_three_sources_do_not_collide_in_chronology(self):
        """Interpret slices the player's declaration and resolve never sees
        it again, so the beat's spoken rows come from two ledgers that each
        number from 1. A character's own lines follow both, because a
        reaction is caused by the beat it answers."""
        interpret = speech_transforms([_row(1, 1, "speech", "player")])
        span = max(t["chrono_id"] for t in interpret)
        resolve = speech_transforms([_row(1, 1, "speech", "world",
                                          source_entity_id="world:1")],
                                    chrono_offset=span)
        declared = declared_speech_transforms(
            {"Sera": [{"text": "cast"}]}, chrono_offset=span + 1)
        diff, _history, rejected = compile_transforms(
            interpret + resolve + declared,
            allowed_channels=("speech",), specialist="engine")
        assert rejected == []
        assert [row["text"] for row in diff["speech"]] \
            == ["player", "world", "cast"]
        assert [row["from_event"] for row in diff["speech"]] == [1, 2, 3]

    def test_a_declared_line_with_no_text_is_skipped(self):
        assert declared_speech_transforms({"Sera": [{"text": ""}]}) == []


class TestSpeechIsTheEnginesOwnCategory:
    def test_no_hand_can_author_a_line(self):
        """THE INVARIANT. A channel is a thing a model writes, so a `speech`
        channel owned by a specialist would mean a hand inventing dialogue.
        Words have two legitimate origins and a hand is neither of them."""
        for name, spec in SPECIALISTS.items():
            assert "speech" not in spec["channels"], name
        for role, channels in (schemas.SPECIALIST_CHANNELS or {}).items():
            assert "speech" not in channels, role

    def test_the_category_is_declared_engine_owned(self):
        assert "speech" in ENGINE_CATEGORIES

    def test_a_speech_span_is_not_reported_as_unrouted(self):
        """`speech` reaches no hand on purpose. Reporting it would tell the
        next beat's author that the word it used routes nowhere and invite it
        to pick another one."""
        view = {"spans": [{"categories": ["speech"], "event_id": 1}],
                "manifest": [], "ledger_notes": {}}
        assert _unrouted_rulings(view) == []
        assert unnamed_work(view) == []

    def test_a_genuinely_unknown_category_is_still_reported(self):
        """The engine-owned exemption must not become a hole: a word nothing
        answers to is still the thing this report exists for."""
        view = {"spans": [{"categories": ["geography"], "event_id": 1}],
                "manifest": [], "ledger_notes": {}}
        assert _unrouted_rulings(view) == ["geography"]


class TestThePromptTeachesTheDistinction:
    def test_the_contract_names_both_spoken_kinds(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "communication" in sheet
        # The rule that keeps a description out of quotation marks.
        assert "never invent a quote" in sheet

    def test_the_contract_says_where_the_words_go(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "words exactly as spoken" in sheet


class TestTheDirectorCanConstructAnUnnamedTarget:
    """`targets` is resolved against the world for the hands, so resolution
    can only find what the Director actually wrote. A Director shown an
    id->name list and nothing else writes "the belt" and "the man by the
    door" -- right words, and neither resolves, because the world was never
    shown to it. `causal_world_index` is placement, not state."""

    scene = {
        "rooms": {"forge": {"name": "The Forge",
                            "adjacent": [{"to": "square"}]},
                  "square": {"name": "The Square", "adjacent": []}},
        "positions": {"Sera": "forge", "anvil": "forge", "Bryn": "square"},
        "entities": {"anvil": {"name": "the anvil"}},
        "attire": {"Sera": {"wearing": ["belt", "apron"]}},
        "stations": {"forge": {"bench": {}}},
    }

    def test_a_room_lists_what_it_holds_and_what_it_opens_onto(self):
        from agents.director import causal_world_index
        index = causal_world_index(self.scene, here="forge")
        forge = index["rooms"]["forge"]
        assert index["here"] == "forge"
        assert forge["exits"] == ["square"]
        assert {row["id"] for row in forge["holds"]} == {"Sera", "anvil"}
        assert {row["id"]: row["kind"] for row in forge["holds"]} \
            == {"Sera": "body", "anvil": "entity"}

    def test_a_garment_is_nameable_without_being_in_the_input(self):
        from agents.director import causal_world_index
        assert causal_world_index(self.scene)["worn"]["Sera"] \
            == ["belt", "apron"]

    def test_the_anchors_a_body_can_stand_at_are_named(self):
        from agents.director import causal_world_index
        assert "bench" in causal_world_index(self.scene)["stations"]["forge"]

    def test_it_carries_placement_and_never_state(self):
        """A Director that can read what a condition says is a Director being
        invited to resolve it, and resolving belongs to the hands."""
        from agents.director import causal_world_index
        scene = dict(self.scene, conditions={"Sera": [{"kind": "wound"}]},
                     vitals={"Sera": {"hp": 3}}, poses={"Sera": {"posture": "x"}})
        index = causal_world_index(scene)
        assert set(index) <= {"rooms", "worn", "stations", "here"}

    def test_an_empty_scene_is_an_empty_index_not_a_crash(self):
        from agents.director import causal_world_index
        assert causal_world_index({}) == {"rooms": {}}
        assert causal_world_index(None) == {"rooms": {}}

    def test_a_target_the_hand_receives_is_resolved_against_the_world(self):
        """The other half: what the Director names, deterministic code turns
        into canonical world keys before any hand sees it."""
        from agents.director import (_span_items,
                                    _specialist_payload)

        out = {"ledgers": [_row(1, 1, "action", "hauls the door open",
                                object_name="the anvil",
                                targets=["Sera", "nothing anyone has heard of"],
                                categories=["rooms"])]}
        normalize_causal_ledger(out)
        view = {"source": "causal_ledger", "ledger_notes": {}, "dialogue": [],
                "manifest": [], "spans": _span_items(out),
                "declared_actions": {}, "dice": [], "player": "You",
                "cast": [], "declaration": {}, "prose": ""}

        class _Ctx:
            def __getattr__(self, name):
                raise AttributeError(name)

        row = _specialist_payload("spatial", _Ctx(), self.scene, view,
                                  {"nonce": 0})["ledgers"][0]
        assert row["target_matches"]["Sera"] == [
            {"kind": "body", "world_key": "Sera", "world_name": "Sera"}]
        # Unmatched is ABSENT, never a fabricated guess.
        assert "nothing anyone has heard of" not in row["target_matches"]

    def test_the_contract_tells_the_director_the_index_is_there(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "world_index" in sheet

    def test_every_hand_is_told_targets_are_resolved_for_it(self):
        from llm.prompts import specialist_prompt
        from agents.director import SPECIALISTS as _hands
        for name in _hands:
            assert "target_matches" in specialist_prompt(name, (), "en"), name


class TestTheAddresseeReachesTheDialogueLog:
    """`spatial_frames` snaps who turned to face whom by reading
    `dialogue_log[].intended_target`. Resolve no longer authors a log, so
    every row is re-minted from a declaration -- and both re-mint sites
    hardcoded `intended_target: None`, which meant the field was None on
    every line of every beat and the snap could never fire.
    """

    def test_a_declared_addressee_survives_the_remint(self, temp_db,
                                                      monkeypatch):
        from tests.test_pipeline_audit import (
            _basic_scene, _make_cast, _make_chat, _make_ctx, _make_turn)
        import agents.director as director

        chat_id = _make_chat(temp_db)
        ids, cast_rows = _make_cast(temp_db, chat_id, ["Alice"])
        temp_db.wset(chat_id, "scene",
                     _basic_scene({"Alice": "kitchen",
                                   "The Stranger": "kitchen"}))
        turn_id = _make_turn(temp_db, chat_id, idx=2)
        ctx = _make_ctx(temp_db, chat_id, turn_id, cast_rows, idx=2,
                        player_input="I ask her to wait.")
        ctx["director_interpret"] = {
            "flow": {"dice": [], "resolution_flags": {}},
            "sequence": [{"type": "speech", "text": "Wait here.",
                          "intended_target": "Alice",
                          "targets": ["Alice"], "volume": "normal"}],
            "movement": None,
        }
        ctx["mapping_quick"] = {"relevant_lore": []}
        ctx.character_results[ids["Alice"]] = {
            "name": "Alice",
            "sequence": [{"type": "speech", "text": "Not for long.",
                          "targets": ["The Stranger"]}],
        }

        monkeypatch.setattr(director, "_agent_json",
                            lambda *a, **k: {"resolved_event": "They speak.",
                                             "summary": "beat",
                                             "dialogue_log": [],
                                             "state_diff": {}})
        monkeypatch.setattr(director, "validate_llm_output",
                            lambda key, out: (out, []))

        out = director.director_resolve(ctx, 0)
        aimed = {row["speaker"]: row.get("intended_target")
                 for row in out["dialogue_log"]}
        assert aimed.get("Alice") == "The Stranger", aimed
        assert aimed.get("The Stranger") == "Alice", aimed
