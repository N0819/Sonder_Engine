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

Since 2026-09-27 the rows are code's, built from the prose Director's encoder
events, and the sheets these tests pin are the encoder's and the prose
Director's. The engine-owned category list, the unrouted report, the hands'
row slice and the causal ledger validator went with the causal Director.
"""

import pytest

from agents import composer
from agents.director import (
    SPECIALISTS,
    span_owners,
    _span_items,
    declared_speech_transforms,
    normalize_causal_ledger,
    speech_transforms,
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


class TestThePromptTeachesTheDistinction:
    def test_the_contract_teaches_the_verb_as_the_distinction(self):
        """No `kind`, no flag: a verb is supplied exactly when the words are
        not, and that is the whole of it. The encoder's core since
        2026-09-27; the Director's own sheet keeps the rule that keeps a
        description out of quotation marks."""
        from llm.prompts import prose_director_prompt, unified_specialist_prompt
        sheet = unified_specialist_prompt([], "en", [])
        assert ("act: the speaking verb, only when the prose reports speech "
                "without giving its words.") in sheet
        # The rule that keeps a description out of quotation marks.
        assert "you never write a line or a decision nobody declared" in (
            prose_director_prompt("resolve", "en"))

    def test_the_contract_asks_for_neither_kind_nor_authority_on_a_row(self):
        from llm.prompts import unified_specialist_prompt
        sheet = unified_specialist_prompt([], "en", [])
        shape = sheet[sheet.index('{"events"'):]
        assert '"kind"' not in shape
        assert '"authority_mode"' not in shape

    def test_the_contract_says_where_the_words_go(self):
        from llm.prompts import unified_specialist_prompt
        sheet = unified_specialist_prompt([], "en", [])
        assert ("for a spoken event the words alone, exactly as the prose "
                "quotes them") in sheet
        # AND WITHOUT WHAT SURROUNDS THEM. The live run's Director packed the
        # attribution into the row -- `"The wells are sealed," you tell her.`
        # -- and the renderer wraps a speech body in quotes, so the page would
        # have read: You says: ""The wells are sealed," you tell her." No
        # sheet says so since 2026-09-27; code enforces it
        # (`director_prose.spoken_words_are_the_quotation`).
        assert "give every spoken line its own event" in sheet


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

    def test_the_contract_tells_the_director_the_index_is_there(self):
        from llm.prompts import prose_director_prompt
        sheet = prose_director_prompt("resolve", "en")
        assert ("call each thing by one name, the world_index's name for "
                "anything that already exists") in sheet


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
        """The causal sheet's "WHOSE CONDUCT THE ROW IS, not whose input it
        came from" until 2026-09-27; the encoder's field line since."""
        from llm.prompts import unified_specialist_prompt
        sheet = unified_specialist_prompt([], "en", [])
        assert ("source_entity_id: the identity_index key whose conduct "
                "this is.") in sheet

    @pytest.mark.parametrize("language, grant, outcomes, agency", [
        ("en", "world_author: its conduct and the world outcomes it states "
               "stand, written as done.",
         "actor_only and autonomous: its own conduct and body stand; what it "
         "does to anything beyond its own body is written as attempted, the "
         "outcome left open for the resolve",
         "Another mind's choices are its own."),
        ("ja", "world_author: その行為と、それが述べる世界の結果は成立し、"
               "済んだこととして書きます。",
         "自分の身体を超えて何かに及ぼすことは試みとして書き、結果は resolve "
         "のために開いたままにします。",
         "他の心の選択はその心自身のものです。"),
    ])
    def test_the_input_grant_and_other_minds_agency_are_separate(
            self, language, grant, outcomes, agency):
        """Attribution cannot revoke world-author outcomes or another mind's
        agency. The interpret sheet states each authority's grant; the
        resolve sheet leaves another mind's choices its own."""
        from llm.prompts import prose_director_prompt
        interpret = prose_director_prompt("interpret", language)
        resolve = prose_director_prompt("resolve", language)
        assert grant in interpret
        assert outcomes in interpret
        assert agency in resolve
        assert "only claims anyone else's" not in (interpret + resolve).casefold()

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
        output = {"ledgers": [row]}
        normalize_causal_ledger(
            output, {"persona:10": "world_author"}, payload["identity_index"])
        assert output["ledgers"][0]["source_entity_id"] == "persona:10"
        assert output["sequence"][0]["actor"] == "persona:10"

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
        """The encoder's core since 2026-09-27. A failed attempt is covered
        only as a member of the class, no longer by name."""
        from llm.prompts import unified_specialist_prompt
        sheet = unified_specialist_prompt([], "en", [])
        assert "Write events in the order they happen." in sheet
        assert ("Every outward act the prose states is an event, whether or "
                "not a tool records it") in sheet

    def test_it_also_refuses_a_row_that_only_restates(self):
        """`Sera is the intended recipient of Corin's directive` is not an
        event; it is the addressee, which `targets` already carries. The
        encoder's core and the decision model's `entities` question since
        2026-09-27; and the sibling that names absence -- silence, stillness,
        nothing changed -- is back in the core since 2026-09-28, the causal
        sheet's own rule (UNBUILT_PIPELINE §1.1 item 4)."""
        from llm.prompts import jev_channel_questions, unified_specialist_prompt
        sheet = unified_specialist_prompt([], "en", [])
        assert "a step that changes no record has none" in sheet
        assert ("silence, stillness or a statement that nothing changed makes "
                "no event") in sheet
        assert "described as they already are." in jev_channel_questions(
            ["entities"], "en")["entities"]


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


class TestTheAddresseeReachesTheDialogueLog:
    """`spatial_frames` snaps who turned to face whom by reading
    `dialogue_log[].intended_target`. Resolve no longer authors a log, so
    every row is re-minted from a declaration -- and both re-mint sites
    hardcoded `intended_target: None`, which meant the field was None on
    every line of every beat and the snap could never fire.
    """

    def test_a_declared_addressee_survives_the_remint(self, temp_db,
                                                      monkeypatch,
                                                      prose_director):
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

        from tests.director_fakes import prose_resolve_agent
        monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
            {"resolved_event": "They speak.", "state_diff": {}}))
        monkeypatch.setattr(director, "validate_llm_output",
                            lambda key, out: (out, []))

        out = director.director_resolve(ctx, 0)
        aimed = {row["speaker"]: row.get("intended_target")
                 for row in out["dialogue_log"]}
        assert aimed.get("Alice") == "The Stranger", aimed
        assert aimed.get("The Stranger") == "Alice", aimed
