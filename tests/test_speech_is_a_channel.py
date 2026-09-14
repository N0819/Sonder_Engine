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
    span_owners,
    _span_items,
    declared_speech_transforms,
    normalize_causal_ledger,
    speech_transforms,
    unnamed_work,
    _unrouted_rulings,
)
from llm import schemas
from world.causality import LIST_CHANNELS, compile_transforms


def _row(chrono_id, item_id, kind, event, **over):
    """A ledger row. `kind` is the TEST's shorthand, not a field -- there is
    no `kind` on a row. "speech" means the words were given, "communication"
    means only a verb was, and anything else is an ordinary act."""
    row = {
        "chrono_id": chrono_id, "item_id": item_id, "object_name": "Sera",
        "source_entity_id": "persona:1",
        "source_event_id": "turn:9:primary:raw", "event": event,
        "observable": "", "commitment": "asserted", "targets": ["Sera"],
        "visibility": "overt", "conceal_from": [], "volume": "normal",
        "movement": None, "ability": "", "difficulty": "",
        "resolution_notes": "", "categories": ["speech"],
    }
    if kind == "communication":
        row["act"] = "ask"
    elif kind != "speech":
        row["categories"] = []
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

    def test_a_described_row_with_no_verb_still_renders(self):
        """`act` is the one field a described row adds, so a Director that
        writes a proposition and forgets the verb must not produce an empty
        predicate. It cannot be told apart from a quote in that case, so it
        renders as one -- but it renders."""
        out = _projected(_row(1, 1, "communication", "that the boat left",
                              act=""))
        assert out["sequence"][0]["type"] == "speech"
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
        assert [bool(t["patch"]["speech"][0].get("act")) for t in built] \
            == [False, True]

    def test_a_spoken_row_with_nothing_said_mints_no_line(self):
        """A row the Director failed to fill is not a silence. Minting from
        it would put a body on the page opening its mouth to say nothing."""
        assert speech_transforms([_row(1, 1, "speech", "   ")]) == []

    def test_the_speaker_is_an_engine_identity_not_a_display_name(self):
        built = speech_transforms([_row(1, 1, "speech", "Hello.")])
        row = built[0]["patch"]["speech"][0]
        assert row["source_entity_id"] == "persona:1"

    def test_the_channel_carries_the_row_not_a_copy_of_it(self):
        """One line, one record. A reshaped copy beside the ledger row is a
        second representation of the same fact, and the two can drift."""
        row = speech_transforms(
            [_row(1, 1, "speech", "Hello.")])[0]["patch"]["speech"][0]
        assert row["event"] == "Hello."
        assert row["object_name"] == "Sera"
        assert row["resolution_notes"] == ""
        # ...minus the Director's own working input, which is not a hand's
        # and not the world's.
        assert "authority_mode" not in row

    def test_the_compiled_channel_carries_the_beats_chronology(self):
        built = speech_transforms([_row(2, 2, "speech", "second"),
                                   _row(1, 1, "speech", "first")])
        diff, _history, rejected = compile_transforms(
            built, allowed_channels=("speech",), specialist="engine")
        assert rejected == []
        assert [row["event"] for row in diff["speech"]] == ["first", "second"]
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
        assert [row["event"] for row in diff["speech"]] \
            == ["player", "world", "cast"]
        assert [row["from_event"] for row in diff["speech"]] == [1, 2, 3]

    def test_one_line_from_two_producers_lands_once(self):
        """MEASURED LIVE. Both the resolve ledger and the character's own
        declaration carry the beat's speech, so both carried Sera's "All
        three?" -- once as `character:1`, once as the display name `Sera` --
        and the channel held it twice. The words are the only thing the two
        agree on, so they are the key."""
        directors = speech_transforms(
            [_row(1, 1, "speech", "All three?",
                  source_entity_id="character:1", targets=["Corin"])])
        declared = declared_speech_transforms(
            {"Sera": [{"text": '"All three?"'}]}, chrono_offset=1,
            already=[t["patch"]["speech"][0]["event"] for t in directors])
        assert declared == []

        # ...and a line the Director's rows did NOT carry still gets in.
        other = declared_speech_transforms(
            {"Sera": [{"text": "Sealed how?"}]}, chrono_offset=1,
            already=[t["patch"]["speech"][0]["event"] for t in directors])
        assert len(other) == 1

    def test_the_directors_row_is_the_one_that_survives(self):
        """It carries the delivery facts -- targets, concealment, volume --
        that a `char_speech` entry has none of."""
        directors = speech_transforms(
            [_row(1, 1, "speech", "All three?",
                  source_entity_id="character:1", targets=["Corin"],
                  conceal_from=["Bryn"], volume="mutter")])
        row = directors[0]["patch"]["speech"][0]
        assert row["targets"] == ["Corin"]
        assert row["conceal_from"] == ["Bryn"]
        assert row["volume"] == "mutter"

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

    def test_the_category_is_what_routes_a_row_to_the_recompiler(self):
        """The category does the work, exactly as it does for every other
        channel -- and it may sit beside a hand's channel in the same list,
        so one line reaches the recompiler AND the social ledger. Measured on
        the first live run: the Director filed spoken rows under
        `telling_ops`, which is correct for a telling; naming `speech` too is
        what puts the words in the world."""
        both = _row(1, 1, "speech", "Hello.",
                    categories=["speech", "telling_ops"])
        assert len(speech_transforms([both])) == 1
        assert "social" in span_owners(_span_items(
            _projected(both))[0])

        unnamed = _row(1, 1, "speech", "Hello.", categories=["telling_ops"])
        assert speech_transforms([unnamed]) == []

    def test_the_contract_does_not_ask_for_the_speech_category(self):
        """AND IT MUST NOT. `telling_ops` is the right answer for a line that
        lands in the social ledger; instructing the Director to write `speech`
        instead would divert exactly those spans away from the social hand to
        no hand at all. The word is tolerated, never requested."""
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "categories" in sheet          # the field is still taught
        assert "settles speech" not in sheet
        assert "name it on every speech" not in sheet

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
    def test_the_contract_teaches_the_verb_as_the_distinction(self):
        """No `kind`, no flag: a verb is supplied exactly when the words are
        not, and that is the whole of it."""
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "Omit it when you have the line itself" in sheet
        # The rule that keeps a description out of quotation marks.
        assert "never invent a quote" in sheet

    def test_the_contract_asks_for_neither_kind_nor_authority_on_a_row(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        shape = sheet[sheet.index('{"ledgers"'):]
        assert '"kind"' not in shape
        assert '"authority_mode"' not in shape

    def test_the_contract_says_where_the_words_go(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "the words ALONE" in sheet
        # AND WITHOUT WHAT SURROUNDS THEM. The live run's Director packed the
        # attribution into the row -- `"The wells are sealed," you tell her.`
        # -- and the renderer wraps a speech body in quotes, so the page would
        # have read: You says: ""The wells are sealed," you tell her."
        assert "without the attribution around them" in sheet
        assert "one row per line" in sheet


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

    def test_the_causal_scene_is_the_actors_sight_aperture(self):
        from agents.director import causal_scene_room_ids, causal_world_index
        scene = {
            **self.scene,
            "rooms": {
                **self.scene["rooms"],
                "distant_cellar": {"name": "Distant Cellar", "adjacent": []},
            },
            "positions": {
                **self.scene["positions"], "sealed_chest": "distant_cellar",
            },
            "entities": {
                **self.scene["entities"],
                "sealed_chest": {"name": "sealed chest"},
            },
        }
        aperture = causal_scene_room_ids(scene, ["Sera"])
        index = causal_world_index(
            scene, here="forge", room_ids=aperture,
            include_entity_interiors=True)

        assert aperture == {"forge", "square"}
        assert "anvil" in index["entities"]
        assert index["entities"]["anvil"]["interior_rooms"] == []
        assert "sealed_chest" not in index["entities"]
        assert "distant_cellar" not in index["rooms"]

    def test_a_room_behind_a_wall_is_not_in_the_aperture(self):
        from agents.director import causal_scene_room_ids
        scene = {
            **self.scene,
            "rooms": {
                "forge": {"name": "The Forge", "adjacent": [
                    {"to": "square", "barrier": "wall"}]},
                "square": self.scene["rooms"]["square"],
            },
        }
        assert causal_scene_room_ids(scene, ["Sera"]) == {"forge"}

    def test_a_body_interior_is_opt_in_to_the_causal_entity_roster(self):
        from agents.director import causal_world_index
        scene = {
            **self.scene,
            "entities": {**self.scene["entities"],
                         "Sera": {"name": "Sera", "interior_rooms": []}},
        }
        hidden = causal_world_index(
            scene, room_ids={"forge"}, include_entity_interiors=True,
            exclude_entity_interiors={"Sera"})
        assert "Sera" not in hidden.get("entities", {})
        mentioned = causal_world_index(
            scene, room_ids={"forge"}, include_entity_interiors=True)
        assert "Sera" in mentioned["entities"]

    def test_standing_relations_are_scoped_to_the_same_aperture(self):
        from agents.director import causal_contact_rows
        scene = {
            **self.scene,
            "contacts": [
                {"actor": "Sera", "target": "anvil"},
                {"actor": "Bryn", "target": "remote cart"},
            ],
            "positions": {
                **self.scene["positions"], "remote cart": "square"},
        }
        assert causal_contact_rows(scene, {"forge"}) == [
            {"actor": "Sera", "target": "anvil"}]

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

    def test_authority_mode_never_reaches_a_hand(self):
        """It is the DIRECTOR's working input -- how an asserted act is judged
        contestable -- and the answer already arrived as `commitment`. Handing
        a hand the reasoning beside the ruling invites it to re-derive the
        ruling, and a hand that disagrees with the Director about whether
        something happened is what the fan-out cannot reconcile."""
        from agents.director import _span_items, _specialist_payload

        out = {"ledgers": [_row(1, 1, "action", "hauls the door open",
                                categories=["rooms"])]}
        normalize_causal_ledger(out)
        # It IS on the engine's own ledger, where the floors want it.
        assert out["causal_ledger"][0]["authority_mode"]

        view = {"source": "causal_ledger", "ledger_notes": {}, "dialogue": [],
                "manifest": [], "spans": _span_items(out),
                "declared_actions": {}, "dice": [], "player": "You",
                "cast": [], "declaration": {}, "prose": ""}

        class _Ctx:
            def __getattr__(self, name):
                raise AttributeError(name)

        # `spatial` builds from the scene alone, so it can be driven here end
        # to end. Every other hand goes through the same one-line strip, so
        # the choke point below is what actually covers all five.
        payload = _specialist_payload("spatial", _Ctx(), self.scene, view,
                                      {"nonce": 0})
        rows = payload.get("ledgers") or []
        assert rows
        for row in rows:
            assert "authority_mode" not in row
            assert "item_id" not in row

    def test_the_strip_is_one_choke_point_for_every_hand(self):
        """Whatever a hand's payload adds, this is the only door a ledger row
        goes through -- so testing it is testing all five."""
        from agents.director import _specialist_ledger

        stripped = _specialist_ledger(
            {"event": "x", "authority_mode": "world_author",
             "item_id": 3, "chrono_id": 2, "targets": ["Sera"]})
        assert stripped == {"event": "x", "targets": ["Sera"]}

    def test_the_contract_tells_the_director_the_index_is_there(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "world_index" in sheet

    def test_every_hand_is_told_targets_are_resolved_for_it(self):
        from llm.prompts import specialist_prompt
        from agents.director import SPECIALISTS as _hands
        for name in _hands:
            assert "target_matches" in specialist_prompt(name, (), "en"), name


class TestAWordedRowReachesTheChannelEvenUnnamed:
    """FROM THE SECOND LIVE RUN, and it is why the category alone is not
    enough. Handed a beat with three quoted lines, the Director filed all
    three under `public_evidence` -- a defensible ledger for a thing said in
    a market -- and named `speech` on none of them.

    Under a category-only rule the words sat in `event` and reached nothing:
    no channel row, no `dialogue_log`, so no concealment enforced on the line
    the player had deliberately lowered their voice for, and nothing anywhere
    remembering that a word had been said. These are those exact rows.
    """

    @staticmethod
    def _live(event, categories, **over):
        row = {"chrono_id": 1, "item_id": 1, "object_name": "Sera",
               "source_entity_id": "persona:1", "source_event_id": "e1",
               "event": event, "observable": "speaks to Sera",
               "commitment": "asserted", "targets": ["Sera"],
               "visibility": "overt", "conceal_from": [], "volume": "normal",
               "act": "", "resolution_notes": "n", "categories": categories}
        row.update(over)
        return row

    def test_a_quoted_line_filed_as_public_evidence_is_still_speech(self):
        quoted = self._live('"The wells are sealed."', ["public_evidence"])
        out = _projected(quoted)
        assert out["sequence"][0]["type"] == "speech"
        assert len(speech_transforms([quoted])) == 1

    def test_the_concealment_on_that_line_survives_with_it(self):
        """The one that mattered: the player dropped their voice so a
        bystander would not hear, and an unrecovered row enforces nothing."""
        hushed = self._live('"Somebody did that on purpose."',
                            ["public_evidence"], volume="quiet",
                            conceal_from=["character:2"])
        row = speech_transforms([hushed])[0]["patch"]["speech"][0]
        assert row["conceal_from"] == ["character:2"]
        assert row["volume"] == "quiet"

    def test_a_described_row_is_recovered_by_its_verb(self):
        """Beat 3 named `rooms` and still had `act: asks`."""
        asked = self._live("what she saw at the gate last night", ["rooms"],
                           act="asks")
        assert _projected(asked)["sequence"][0]["type"] == "communication"
        assert len(speech_transforms([asked])) == 1

    def test_recovery_does_not_swallow_ordinary_acts(self):
        """The row beside them in the same beat. An act with no words and no
        verb stays an act -- otherwise the recovery is just a leak."""
        acted = self._live("You straighten and find Sera across the stalls.",
                           ["positions", "poses"], observable="straightens")
        assert _projected(acted)["sequence"][0]["type"] == "action"
        assert speech_transforms([acted]) == []

    def test_a_written_notice_is_not_a_spoken_line(self):
        """The quote must OPEN the row. An act that merely contains one --
        nailing up a board, reading a label aloud is not what this is -- must
        not mint dialogue, because inventing a line nobody said is the one
        error worse than losing one."""
        notice = self._live('nails up a board reading "the wells are sealed"',
                            ["artifact_ops"], observable="nails up a board")
        assert _projected(notice)["sequence"][0]["type"] == "action"
        assert speech_transforms([notice]) == []

    def test_the_category_still_wins_over_the_shape(self):
        """A Director that says `speech` is believed whatever the event looks
        like -- recovery is the fallback, never the authority."""
        plain = self._live("the wells are sealed", ["speech"])
        assert _projected(plain)["sequence"][0]["type"] == "speech"

    def test_the_category_is_still_what_the_contract_asks_for(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "A row carrying words always names speech" in sheet


class TestARowBelongsToWhoseConductItIs:
    """FOUND BY THE PARAGRAPH RUN, and it is a firewall-shaped gap.

    Natural prose narrates other people. Given a paragraph where the player
    writes Sera arriving and speaking -- `"Three," she says` -- the Director
    attributed EVERY row to `persona:1`, so the compiled `speech` channel held
    four things in the player's mouth that the player never said: two of
    Sera's lines, a narrative sentence about what Sera told him, and a stage
    direction.

    The model was obeying its instructions. The contract said only
    `source_entity_id, source_event_id: copy from the causing input` -- which
    literally means "attribute every row to whoever typed it". The monolith
    had carried the rule ("A volitional ACTION or line the player narrates FOR
    another character is not the player's to complete -- down-scope it") and
    it went out with the monolith.
    """

    def test_the_contract_says_a_row_belongs_to_its_actor(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "WHOSE CONDUCT THE ROW IS, not whose input it came from" in sheet

    def test_the_contract_says_another_bodys_conduct_is_contestable(self):
        """An input's author states their own conduct and only CLAIMS anyone
        else's -- which is what keeps a narrated NPC line out of that NPC's
        mouth until they answer for themselves."""
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "only claims anyone else's" in sheet.casefold()

    def test_a_narrated_characters_row_is_not_refused(self):
        """AND THE FIX FOR THE FIX. Telling the Director to attribute a row to
        its actor is useless if the validator then refuses it: at interpret
        the only entity supplying input is the player, so every correctly
        down-scoped row was rejected and the beat died --

            director_interpret failed JSON validation:
            ledgers.0.source_entity_id was not supplied in event_inputs; ...

        -- five rows, one paragraph. `source_entity_id` was doing two jobs:
        WHO TYPED (provenance, which is `source_event_id`'s question) and
        WHOSE CONDUCT (attribution). A known identity is a valid actor
        whether or not it supplied a group of its own.
        """
        payload = {
            "event_inputs": [{
                "entity_id": "persona:1", "authority_mode": "world_author",
                "events": [{"event_id": "turn:2:primary:raw"}]}],
            "identity_index": {"persona:1": "Corin", "character:1": "Sera"},
        }
        sera_speaks = {
            "chrono_id": 1, "item_id": 1, "object_name": "Sera",
            "source_entity_id": "character:1",
            "source_event_id": "turn:2:primary:raw",
            "event": "Three.", "commitment": "contestable",
            "resolution_notes": "Sera has said there were three.",
            "categories": ["speech"],
        }
        assert schemas.semantic_output_errors(
            "director_interpret", {"ledgers": [sera_speaks]},
            source_payload=payload) == []

    def test_an_identity_nobody_has_heard_of_is_still_refused(self):
        """The widening must not become a hole: an actor the payload never
        names is the Director inventing a person."""
        payload = {
            "event_inputs": [{
                "entity_id": "persona:1", "authority_mode": "world_author",
                "events": [{"event_id": "e1"}]}],
            "identity_index": {"persona:1": "Corin"},
        }
        invented = {
            "chrono_id": 1, "item_id": 1, "object_name": "x",
            "source_entity_id": "character:99", "source_event_id": "e1",
            "event": "Three.", "commitment": "asserted",
            "resolution_notes": "n", "categories": ["speech"],
        }
        assert schemas.semantic_output_errors(
            "director_interpret", {"ledgers": [invented]},
            source_payload=payload)

    def test_a_unique_display_name_is_renormalized_without_a_repair_call(self):
        """Identity is a join code already owns, not a reason to rerun prose."""
        payload = {
            "event_inputs": [{
                "entity_id": "persona:10", "authority_mode": "world_author",
                "events": [{"event_id": "e1"}],
            }],
            "identity_index": {"persona:10": "Hinami"},
        }
        row = {
            "chrono_id": 1, "item_id": 1, "object_name": "TARDIS",
            "source_entity_id": "Hinami", "source_event_id": "e1",
            "event": "opens the doors", "commitment": "asserted",
            "resolution_notes": "The doors are open.",
            "categories": ["entities"],
        }
        assert schemas.semantic_output_errors(
            "director_interpret", {"ledgers": [row]},
            source_payload=payload) == []
        output = {"ledgers": [row]}
        normalize_causal_ledger(
            output, {"persona:10": "world_author"}, payload["identity_index"])
        assert output["ledgers"][0]["source_entity_id"] == "persona:10"
        assert output["sequence"][0]["actor"] == "persona:10"

    @pytest.mark.parametrize("category", sorted(SPECIALISTS))
    def test_a_hand_name_is_a_coarser_answer_not_a_wrong_one(self, category):
        """`manifest_category_targets` has accepted a hand name since
        2026-09-09 -- it grants that hand its story's channels -- and this
        validator did not, so a beat died on `categories: ["objects"]` whose
        routing would have been perfectly fine. The validator and the router
        must not hold two different vocabularies; that exact drift is what
        the router's own docstring was written about."""
        payload = {
            "event_inputs": [{
                "entity_id": "persona:1", "authority_mode": "world_author",
                "events": [{"event_id": "e1"}]}],
            "identity_index": {"persona:1": "Corin"},
        }
        row = {"chrono_id": 1, "item_id": 1, "object_name": "x",
               "source_entity_id": "persona:1", "source_event_id": "e1",
               "event": "e", "commitment": "asserted",
               "resolution_notes": "n", "categories": [category]}
        assert schemas.semantic_output_errors(
            "director_interpret", {"ledgers": [row]},
            source_payload=payload) == []
        from agents.director import manifest_category_targets
        assert manifest_category_targets(category)

    def test_a_row_attributed_elsewhere_still_compiles(self):
        """The engine must carry the down-scoped row, not just ask for it."""
        row = _row(1, 1, "speech", "Three.",
                   source_entity_id="character:1", commitment="contestable")
        built = speech_transforms([row])
        assert len(built) == 1
        assert built[0]["patch"]["speech"][0]["source_entity_id"] \
            == "character:1"
        assert built[0]["patch"]["speech"][0]["commitment"] == "contestable"


class TestANonEventIsNotARow:
    """MEASURED ON THE PARAGRAPH RUN. Five of one beat's ten rows described
    things that did not happen, and carried live categories doing it:

        Sera does not disagree...           -> social, ratified_claims
        Corin does not turn around...       -> poses
        Sera does not turn around...        -> poses
        A period of silence passes...       -> speech
        Sera is the intended recipient...   -> social, world_facts

    A silence filed as speech. Two bodies NOT turning dispatching the spatial
    hand to encode a posture that never changed. And one row that is not an
    event at all, only a restatement of who was addressed.

    The pressure came from the omission detector (see the sibling class):
    told it had dropped a sentence, the Director covered every clause,
    including the ones describing absence.
    """

    def test_the_contract_says_a_row_is_something_that_happened(self):
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "A row is something that HAPPENED" in sheet

    def test_it_names_the_shapes_absence_takes(self):
        """Stated as a class with instances marked as such, not as a list to
        match against -- silence and stillness are the two the run produced,
        and 'nothing changing' is the parent that covers the rest."""
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en").casefold()
        for shape in ("silence", "stillness", "not answering",
                      "nothing changing"):
            assert shape in sheet, shape

    def test_it_also_refuses_a_row_that_only_restates(self):
        """`Sera is the intended recipient of Corin's directive` is not an
        event; it is the addressee, which `targets` already carries."""
        from llm.prompts import get_prompt_body
        sheet = get_prompt_body("director_resolve_lean", "en")
        assert "only restates who or where" in sheet


class TestTheCoverageDetectorNoLongerBuysARepairCall:
    """A LEXICAL TEST CANNOT GRADE A CONTRACT THAT PARAPHRASES.

    `_uncovered_declarations` looks for the input's significant tokens in the
    interpretation. That held while the Director echoed the player's wording.
    The causal contract requires the opposite -- objective observable spans --
    so a faithful paraphrase reads as a dropped declaration.

    Measured: 3 flags across 2 repair calls, 0 of them real.

        "Sera finds you before you find her"     -> a row, reworded
        "The light has moved while you were..."  -> a row, reworded
        "Neither of you says anything..."        -> a NEGATIVE, no event

    The detection stays as a warning, because a partial slice is still worth
    knowing about and nothing else sees one. What stops is spending a model
    call on it and teaching the Director to widen.
    """

    def test_a_causal_output_reports_instead_of_repairing(self):
        import agents.director as director

        calls = []

        def _no_calls(role, step_key, *a, **k):
            calls.append(step_key)
            return {}

        ctx = _FakeCtx("Sera finds you before you find her.")
        out = {"causal_ledger": [{"chrono_id": 1, "item_id": 1,
                                  "event": "Sera comes around the trestle"}],
               "sequence": [{"type": "action",
                             "attempt": "Sera comes around the trestle"}],
               "flow": {}}
        original = director._agent_json
        director._agent_json = _no_calls
        try:
            director._reconcile_interpretation(ctx, out, {"rooms": {}})
        finally:
            director._agent_json = original

        assert "interpret_repair" not in calls, calls
        assert out["interpret_reconciliation"]["uncovered"]
        assert any("interpret coverage" in w for w in ctx.warnings), \
            ctx.warnings

    def test_the_legacy_shape_does_not_take_the_early_return(self):
        """Gated, not deleted. The detector's premise still holds for an
        output that echoed the player's wording, so a legacy shape falls
        through to the repair seam instead of stopping at the report."""
        import agents.director as director

        ctx = _FakeCtx("Sera finds you before you find her.")
        out = {"sequence": [{"type": "action", "attempt": "unrelated"}],
               "flow": {}}
        original = director._agent_json
        director._agent_json = lambda *a, **k: {}
        try:
            director._reconcile_interpretation(ctx, out, {"rooms": {}})
        except Exception:
            pass          # the seam wants a fuller ctx; the GATE is the test
        finally:
            director._agent_json = original

        assert out["interpret_reconciliation"]["uncovered"]
        assert not any("interpret coverage" in w for w in ctx.warnings), \
            ctx.warnings


class _FakeCtx(dict):
    """The three things `_reconcile_interpretation` touches."""

    def __init__(self, player_input):
        super().__init__(input=player_input)
        self.warnings = []
        self.language = "en"

    def add_warning(self, text):
        self.warnings.append(str(text))


class TestAGuardMayNotDestroyABeatItCannotJustify:
    """The rule four live beat-deaths in one afternoon paid for:

        a check may be fatal only if nothing downstream reads the field,
        repairs it, or already reports it.

    Every demotion below failed that test. `item_id` uniqueness and
    positivity are REPAIRED by `normalize_causal_ledger` on the very next
    pass -- the beat was dying for something fixed a line later. Density is
    read by nobody; the join is id equality, not position. Ordering is
    REDUNDANT with `compile_transforms`, which sorts by chrono itself. An
    unroutable category is already REPORTED per-span by `_unrouted_rulings`,
    and losing one span beats losing the beat it was in. `object_name` is a
    matching hint, so its absence degrades matching, not the ruling.
    """

    payload = {
        "event_inputs": [{"entity_id": "persona:1",
                          "authority_mode": "world_author",
                          "events": [{"event_id": "e1"}]}],
        "identity_index": {"persona:1": "Corin", "character:1": "Sera"},
    }

    @staticmethod
    def _row(**over):
        row = {"chrono_id": 1, "item_id": 1, "object_name": "x",
               "source_entity_id": "persona:1", "source_event_id": "e1",
               "event": "e", "commitment": "asserted",
               "resolution_notes": "n", "categories": ["poses"]}
        row.update(over)
        return row

    def _report(self, *ledgers):
        return schemas.validate_llm_output_strict(
            "director_interpret", {"ledgers": list(ledgers)},
            source_payload=self.payload)

    def test_a_beat_carrying_every_demoted_fault_still_survives(self):
        report = self._report(
            self._row(item_id=5, chrono_id=3, object_name="",
                      categories=["geography"]),
            self._row(item_id=5, chrono_id=1, categories=["inventory"]),
            self._row(item_id=0, chrono_id=0),
        )
        assert report.valid, report.errors
        assert report.errors == []

    def test_and_says_so_rather_than_swallowing_it(self):
        """Demoted, not deleted: the information still reaches the log."""
        report = self._report(self._row(item_id=5), self._row(item_id=5))
        assert any("renumbered" in str(w) for w in report.warnings), \
            report.warnings

    def test_the_packs_own_alias_no_longer_kills_a_beat(self):
        """`inventory` is the alias the router resolves to `inventory_ops`;
        the validator's channel list does not carry aliases, so it was
        refusing a word the engine understands."""
        report = self._report(self._row(categories=["inventory"]))
        assert report.valid
        from agents.director import manifest_category_targets
        assert manifest_category_targets("inventory")

    @pytest.mark.parametrize("fault,over", [
        ("an empty event", {"event": ""}),
        ("no ruling at all", {"resolution_notes": ""}),
        ("a commitment nothing means", {"commitment": "maybe"}),
        ("an invented person", {"source_entity_id": "character:99"}),
    ])
    def test_what_stays_fatal_stays_fatal(self, fault, over):
        """The answer being malformed or saying nothing. Demoting these would
        make the validator decorative."""
        assert not self._report(self._row(**over)).valid, fault

    def test_answering_nothing_at_all_is_still_fatal(self):
        assert not self._report().valid


class TestNormalizationDoesNotEatTheRowsIdentity:
    """THE ONE THAT COST THE WHOLE INTERPRET FAN-OUT.

    `norm_sequence` rebuilds every sequence element from a fixed key set, and
    `SPAN_FIELDS` was `("category", "note", "items")` -- so the causal row's
    `item_id` was dropped between the Director answering and the hands being
    dispatched. `compile_transforms` REJECTS a transform with no item_id, so
    every interpret-stage specialist write was discarded by the engine that
    had just asked for it.

    Measured live 2026-09-12, turn 1: `{"reason": "missing item_id",
    "chrono_id": 0}` against the spatial hand. And turn 3, a belt taken off
    and dropped on a bench: the objects hand ran with no `object_name` to
    match and no id to answer under, and the belt ended in no ledger at all
    -- not worn, not carried, not on the bench, not an entity.

    Resolve was never affected: its sequence does not pass through here.
    """

    row = {
        "chrono_id": 1, "item_id": 1, "object_name": "Corin",
        "source_entity_id": "persona:1", "source_event_id": "turn:4:raw",
        "event": "works the belt off and drops it on the bench",
        "observable": "removes a belt and drops it on a bench", "act": "",
        "commitment": "asserted", "targets": ["Sera"], "visibility": "overt",
        "conceal_from": [], "volume": "normal", "movement": None,
        "ability": "", "difficulty": "",
        "resolution_notes": "Corin's belt is on the bench.",
        "categories": ["inventory_ops", "sensory_events"],
    }

    def _normalized_span(self):
        from agents.common import norm_sequence
        out = {"ledgers": [dict(self.row)]}
        normalize_causal_ledger(out)
        norm_sequence(out)
        return _span_items(out)[0]

    def test_the_join_id_survives_normalization(self):
        assert self._normalized_span()["item_id"] == 1

    def test_the_transform_that_was_thrown_away_now_compiles(self):
        span = self._normalized_span()
        diff, _history, rejected = compile_transforms(
            [{"item_id": span["item_id"],
              "patch": {"inventory_ops": [{"op": "drop",
                                           "object_id": "belt"}]}}],
            allowed_channels=("inventory_ops",), ledger_items=[span],
            allowed_item_ids=[span["item_id"]], specialist="objects")
        assert rejected == []
        assert diff["inventory_ops"][0]["object_id"] == "belt"
        assert diff["inventory_ops"][0]["from_event"] == 1

    def test_the_matching_hint_survives(self):
        """Without it `world_matches` has nothing to resolve, and the hand is
        handed prose and asked to find the object in it."""
        assert self._normalized_span()["object_name"] == "Corin"

    def test_both_ledgers_survive_not_just_the_first(self):
        """A span may name two, and only the LIST says so. Keeping the folded
        singular alone silently halves the multi-hand routing."""
        span = self._normalized_span()
        assert len(span["categories"]) == 2
        assert set(span_owners(span)) == {"objects"}

    def test_the_actor_survives(self):
        assert self._normalized_span()["actor"] == "persona:1"

    def test_chronology_is_the_directors_not_the_positions(self):
        from agents.common import norm_sequence
        out = {"ledgers": [dict(self.row, chrono_id=4, item_id=4)]}
        normalize_causal_ledger(out)
        norm_sequence(out)
        assert _span_items(out)[0]["event_id"] == 4


class TestTheValidatorDoesNotKillABeatOverBookkeeping:
    """FOUND BY A LIVE RUN, not by a test. Beat 4 of the first real
    playthrough died outright:

        RuntimeError: director_resolve failed JSON validation:
        ledgers.1.source_event_id was not supplied by its source

    Every row was correct -- right entity, right authority, right causality.
    The contract asks for several rows per source event, so the model split
    one declaration into three and numbered them: handed
    `turn:4:character:1` it wrote `turn:4:character:1:0:action`. A whole beat
    was lost on the shape of a provenance string.

    The two `communication`/`speech` cases are the same class and were mine:
    the validator's closed sets would have rejected every described-speech
    beat the moment the new kind was used.
    """

    payload = {"event_inputs": [{
        "entity_id": "character:1", "authority_mode": "autonomous",
        "events": [{"event_id": "turn:4:character:1"}],
    }]}

    @staticmethod
    def _ledger(source_event_id="turn:4:character:1", **over):
        row = {"chrono_id": 1, "item_id": 1, "object_name": "Sera",
               "source_entity_id": "character:1",
               "authority_mode": "autonomous",
               "source_event_id": source_event_id, "kind": "action",
               "event": "glances at the belt", "observable": "glances",
               "commitment": "asserted", "targets": [],
               "visibility": "overt", "conceal_from": [], "volume": "normal",
               "movement": None, "ability": "", "difficulty": "",
               "resolution_notes": "She has looked at the belt.",
               "categories": []}
        row.update(over)
        return row

    def _errors(self, *ledgers, payload=None):
        return schemas.semantic_output_errors(
            "director_resolve", {"ledgers": list(ledgers)},
            source_payload=payload or self.payload)

    def test_the_beat_that_died_now_survives(self):
        assert self._errors(
            self._ledger(),
            self._ledger("turn:4:character:1:0:action", item_id=2, chrono_id=2),
            self._ledger("turn:4:character:1:1:speech", item_id=3, chrono_id=3),
        ) == []

    def test_a_described_speech_row_is_a_valid_kind(self):
        assert self._errors(self._ledger(kind="communication")) == []

    def test_the_engine_owned_category_is_accepted(self):
        assert self._errors(self._ledger(categories=["speech"])) == []

    def test_a_source_with_one_event_is_never_ambiguous(self):
        """Whatever was written, there is only one event it can mean."""
        assert self._errors(self._ledger("something else entirely")) == []

    def test_recovery_is_not_a_hole(self):
        """The reasons a beat SHOULD be refused still refuse it."""
        assert self._errors(self._ledger(source_entity_id="character:99"))
        assert self._errors(self._ledger(event=""))
        # `categories=["geography"]` is NO LONGER fatal -- it is reported as
        # a note, because `_unrouted_rulings` already reports it per span and
        # losing one span beats losing the beat. See
        # TestAGuardMayNotDestroyABeatItCannotJustify.

    def test_the_second_live_shape_a_rebuilt_turn_number(self):
        """The third run died the same way on a different mangling: handed
        `turn:2:character:2:0:action`, the model wrote `turn:4:...` -- it
        rebuilt the id from its own idea of the turn rather than copying, so
        nothing matched by prefix. The shared TAIL picks the right one of the
        entity's two events, which is the discrimination a reader makes."""
        payload = {"event_inputs": [{
            "entity_id": "character:2", "authority_mode": "autonomous",
            "events": [{"event_id": "turn:2:character:2:0:action"},
                       {"event_id": "turn:2:character:2:1:speech"}]}]}
        for written in ("turn:4:character:2:0:action",
                        "turn:4:character:2:1:speech"):
            assert self._errors(
                self._ledger(written, source_entity_id="character:2"),
                payload=payload) == [], written

    def test_a_genuinely_ambiguous_id_is_still_reported(self):
        """Two candidate events and a string matching neither: guessing would
        attribute causality the model never stated."""
        two = {"event_inputs": [{
            "entity_id": "character:1", "authority_mode": "autonomous",
            "events": [{"event_id": "turn:4:a"}, {"event_id": "turn:4:b"}]}]}
        assert self._errors(self._ledger("turn:4:zzz"), payload=two)


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
