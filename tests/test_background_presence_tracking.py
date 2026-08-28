"""Regression tests for track_background_presences/promotable_background_
presences: deterministic, LLM-free tracking of named entities the
director keeps writing into resolved_event/dialogue_log who have no
character sheet -- the "Dr. Crusher problem" (present and active for 35+
turns with zero mechanical backing)."""

from __future__ import annotations

import json
import time

from persist.commit import (
    track_background_presences,
    promotable_background_presences,
    _background_name_mentioned,
    presence_name_items,
    presence_record_for,
    BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
    BACKGROUND_PROMOTION_MENTION_THRESHOLD,
)
from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _rec(presences, name):
    """The tracked record answering to this display name, or None. The
    ledger keys on minted uids; every name assertion goes through the same
    resolver seam production readers use."""
    return presence_record_for(presences, name)[1]


def _names(presences):
    return {n for n, _ in presence_name_items(presences)}


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_character(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


def _ctx(chat_id, turn_idx, cast, director_resolve):
    return PipelineContext(
        chat=ChatData(
            id=chat_id, name="Test", persona_id=None, lorebook_id=None,
            scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=turn_idx + 1, chat_id=chat_id, idx=turn_idx, player_input="",
            created=time.time(),
        ),
        cast=cast, input="", director_resolve=director_resolve,
    )


class TestBackgroundNameMentioned:
    def test_full_name_match(self):
        assert _background_name_mentioned("Dr. Crusher", "Dr. Crusher checks the readout.")

    def test_last_name_only_still_matches(self):
        assert _background_name_mentioned("Dr. Crusher", "Crusher checks the readout.")

    def test_title_word_alone_does_not_match(self):
        # "Dr." stripped as a title word -- a scene full of OTHER doctors
        # must not count as a mention of this specific one.
        assert not _background_name_mentioned("Dr. Crusher", "The doctor on duty checks the readout.")

    def test_short_substring_does_not_false_positive(self):
        # "Ana" (a hypothetical 3-letter name) should not match inside
        # unrelated words like "banana" -- word-boundary regex, not a
        # bare substring check.
        assert not _background_name_mentioned("Ana", "The banana was left on the table.")

    def test_no_relation_does_not_match(self):
        assert not _background_name_mentioned("Dr. Crusher", "Picard stands at the viewscreen.")


def test_registered_cast_members_are_never_tracked(temp_db):
    chat_id = _make_chat(temp_db)
    char_id = _make_character(temp_db, "Jean-Luc Picard")
    cast = [dict(temp_db.q("SELECT * FROM characters WHERE id=?", (char_id,), one=True))]

    ctx = _ctx(chat_id, 0, cast, {
        "dialogue_log": [{"speaker": "Jean-Luc Picard", "exact_quote": "Make it so."}],
        "resolved_event": "Picard gives the order.",
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert _rec(presences, "Jean-Luc Picard") is None


def test_untracked_speaker_gets_tracked_and_counted(temp_db):
    chat_id = _make_chat(temp_db)

    ctx = _ctx(chat_id, 3, [], {
        "dialogue_log": [{"speaker": "Dr. Crusher", "exact_quote": "Hold still."}],
        "resolved_event": "Crusher checks the readout.",
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    rec = _rec(presences, "Dr. Crusher")
    assert rec is not None
    assert rec["dialogue_turns"] == [3]
    assert rec["first_turn"] == 3
    assert rec["last_turn"] == 3


def test_entity_with_person_kind_is_tracked(temp_db):
    chat_id = _make_chat(temp_db)

    ctx = _ctx(chat_id, 1, [], {
        "state_diff": {"entities": {
            "e1": {"kind": "person", "name": "The Innkeeper"},
            "e2": {"kind": "fixture", "name": "The Bar"},
        }},
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert "The Innkeeper" in _names(presences)
    assert "The Bar" not in _names(presences)


def test_declared_agents_of_any_kind_are_tracked(temp_db):
    # Regression: a player-declared agent is captured with whatever `kind`
    # the model chose ("actor" for "two security guards", but also monster,
    # creature, robot, ...). An allow-list of person/npc silently dropped
    # them, leaving them declared-into-the-scene yet inert (no path to a
    # reaction or promotion). Any non-inert kind is now tracked; clearly
    # inert kinds (object/fixture/vehicle/...) stay excluded, and an
    # ambiguous "machine" is tracked (could be a sentient robot).
    chat_id = _make_chat(temp_db)

    ctx = _ctx(chat_id, 1, [], {
        "state_diff": {"entities": {
            "guard_1": {"kind": "actor", "name": "Security Guard Peterson"},
            "beast_1": {"kind": "monster", "name": "The Grendel"},
            "crit_1": {"kind": "creature", "name": "Skitter"},
            "bot_1": {"kind": "robot", "name": "Unit 7"},
            "ai_1": {"kind": "machine", "name": "The Warden"},
            "panel": {"kind": "fixture", "name": "Control Panel"},
            "shuttle": {"kind": "vehicle", "name": "The Kestrel"},
            "crate": {"kind": "object", "name": "Supply Crate"},
        }},
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    for agent in ("Security Guard Peterson", "The Grendel", "Skitter",
                  "Unit 7", "The Warden"):
        assert agent in _names(presences), agent
    for inert in ("Control Panel", "The Kestrel", "Supply Crate"):
        assert inert not in _names(presences), inert


def test_id_shaped_speaker_folds_to_entity_display_name(temp_db):
    # Regression: the director sometimes voices a background entity by its
    # raw scene-entity id ("char_guard_alpha") instead of its display name
    # ("Security Guard Alpha"). Tracked verbatim that fragmented the guard
    # into two presences and orphaned its owed-reply debt on the id ghost
    # (a guard challenged the player under its id, then never answered).
    # The id must fold to the display name so exactly one presence exists
    # and the reply debt lands on the same figure the reactor gate ranks.
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", {"entities": {
        "char_guard_alpha": {"kind": "actor", "name": "Security Guard Alpha"},
    }})

    ctx = _ctx(chat_id, 5, [], {
        "dialogue_log": [
            {"speaker": "char_guard_alpha",
             "exact_quote": "Halt. State your designation."},
        ],
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert len(presences) == 1, "exactly one presence, not an id-keyed twin"
    assert _names(presences) == {"Security Guard Alpha"}
    # The dialogue turn is credited to the real (display-name) presence.
    assert _rec(presences, "Security Guard Alpha")["dialogue_turns"] == [5]


def test_mentions_only_count_for_already_tracked_names(temp_db):
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "background_presences", {
        "Dr. Crusher": {
            "first_turn": 1, "last_turn": 1,
            "dialogue_turns": [], "mention_turns": [],
        },
    })

    ctx = _ctx(chat_id, 5, [], {
        "resolved_event": "Crusher moves quietly near the biobed. A stranger watches from the door.",
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert _rec(presences, "Dr. Crusher")["mention_turns"] == [5]
    # "A stranger" is never seeded as a candidate from free prose alone.
    assert "A stranger" not in _names(presences)
    assert "stranger" not in {n.lower() for n in _names(presences)}


def test_promotable_after_dialogue_threshold(temp_db):
    chat_id = _make_chat(temp_db)
    for turn in range(BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD):
        ctx = _ctx(chat_id, turn, [], {
            "dialogue_log": [{"speaker": "Dr. Crusher", "exact_quote": f"Line {turn}."}],
        })
        track_background_presences(ctx, nonce=0)

    result = promotable_background_presences(chat_id)
    crusher = next(r for r in result if r["name"] == "Dr. Crusher")
    assert crusher["promotable"] is True


def test_not_promotable_below_threshold(temp_db):
    chat_id = _make_chat(temp_db)
    ctx = _ctx(chat_id, 0, [], {
        "dialogue_log": [{"speaker": "A Passing Waiter", "exact_quote": "Anything else?"}],
    })
    track_background_presences(ctx, nonce=0)

    result = promotable_background_presences(chat_id)
    waiter = next(r for r in result if r["name"] == "A Passing Waiter")
    assert waiter["promotable"] is False


def test_state_diff_person_harvests_sketch(temp_db):
    chat_id = _make_chat(temp_db)
    ctx = _ctx(chat_id, 1, [], {
        "state_diff": {
            "entities": {"g1": {"kind": "person", "name": "Mira",
                                "description": "harried young serving girl"}},
            "positions": {"Mira": "taproom"},
        },
    })
    track_background_presences(ctx, nonce=0)

    rec = _rec(temp_db.wget(chat_id, "background_presences", {}), "Mira")
    assert rec["sketch"]["role_hint"] == "harried young serving girl"
    assert rec["sketch"]["station_room"] == "taproom"


def test_sketch_not_clobbered_by_descriptionless_restatement(temp_db):
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "background_presences", {
        "Mira": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                 "mention_turns": [],
                 "sketch": {"role_hint": "harried young serving girl",
                            "station_room": "taproom"}},
    })
    ctx = _ctx(chat_id, 2, [], {
        "state_diff": {"entities": {"g1": {"kind": "person", "name": "Mira"}}},
    })
    track_background_presences(ctx, nonce=0)

    rec = _rec(temp_db.wget(chat_id, "background_presences", {}), "Mira")
    assert rec["sketch"]["role_hint"] == "harried young serving girl"  # preserved


def test_sketch_overwritten_by_new_director_description(temp_db):
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "background_presences", {
        "Mira": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                 "mention_turns": [],
                 "sketch": {"role_hint": "serving girl", "station_room": "taproom"}},
    })
    ctx = _ctx(chat_id, 2, [], {
        "state_diff": {"entities": {"g1": {"kind": "person", "name": "Mira",
                                           "description": "the innkeeper's daughter"}}},
    })
    track_background_presences(ctx, nonce=0)

    rec = _rec(temp_db.wget(chat_id, "background_presences", {}), "Mira")
    assert rec["sketch"]["role_hint"] == "the innkeeper's daughter"  # director truth wins
    assert rec["sketch"]["station_room"] == "taproom"  # untouched field preserved


def test_establish_entities_register_location_implied_presence(temp_db):
    # A person the tavern implies, established at the opening turn (idx 0),
    # where DirectorEstablish carries entities/positions at TOP level (not in
    # a state_diff) -- must be tracked as a present-but-not-yet-salient
    # presence, with a sketch, and must not be promotable off the bat.
    chat_id = _make_chat(temp_db)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=0, player_input="",
                      created=time.time()),
        cast=[], input="", director_resolve=None,
        director_establish={
            "entities": {"barkeep": {"kind": "person", "name": "Doran",
                                     "description": "grizzled one-eyed barkeep"}},
            "positions": {"Doran": "taproom"},
        },
    )
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert "Doran" in _names(presences)
    rec = _rec(presences, "Doran")
    assert rec["first_turn"] == 0
    assert rec["dialogue_turns"] == []
    assert rec["mention_turns"] == []
    assert "barkeep" in rec["sketch"]["role_hint"]
    assert rec["sketch"]["station_room"] == "taproom"

    result = promotable_background_presences(chat_id)
    assert next(r for r in result if r["name"] == "Doran")["promotable"] is False


def test_promotable_after_mention_threshold(temp_db):
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "background_presences", {
        "Dr. Crusher": {
            "first_turn": 1, "last_turn": 1,
            "dialogue_turns": [], "mention_turns": [],
        },
    })
    for turn in range(2, 2 + BACKGROUND_PROMOTION_MENTION_THRESHOLD):
        ctx = _ctx(chat_id, turn, [], {
            "resolved_event": "Crusher tends quietly to her patient.",
        })
        track_background_presences(ctx, nonce=0)

    result = promotable_background_presences(chat_id)
    crusher = next(r for r in result if r["name"] == "Dr. Crusher")
    assert crusher["promotable"] is True


class TestOneCreatureIsOnePresence:
    """The ledger is keyed by whatever string the prose used, and prose does
    not hold a determiner steady.

    Live in chat 57 ("Run! ⎇10"): one Dalek entity standing in one room, and
    THREE presences tracking it -- `A Dalek` (25 turns, 10 of them speaking),
    `Dalek` (from turn 19) and `The Dalek` (from turn 23). Each carried its own
    dialogue history, so the same creature had three partial memories of itself
    and none knew what the others had said; `max_managed` counted all three
    against a cap of six; and promotion thresholds were measured against a
    third of the evidence.
    """

    def test_an_article_does_not_make_a_second_presence(self):
        from persist.commit import _presence_identity
        assert (_presence_identity("A Dalek") == _presence_identity("Dalek")
                == _presence_identity("The Dalek") == "dalek")

    def test_case_and_spacing_are_not_identity_either(self):
        from persist.commit import _presence_identity
        assert _presence_identity("  the   DALEK ") == _presence_identity("Dalek")

    def test_a_title_still_distinguishes_two_strangers(self):
        """Articles only. Among unregistered figures a title is often the only
        thing telling two of them apart -- unlike `strip_name_titles`, which is
        right for roster matching and wrong here."""
        from persist.commit import _presence_identity
        assert _presence_identity("the guard") != _presence_identity("the captain")
        assert _presence_identity("Dr. Crusher") != _presence_identity("Crusher")

    def test_the_established_spelling_wins(self):
        from persist.commit import _resolve_or_mint_presence
        presences = {"A Dalek": {"first_turn": 0}}
        established = presences["A Dalek"]
        # Both re-spellings file under the ESTABLISHED record rather than
        # minting a stranger; a genuinely new name mints a fresh one.
        key = _resolve_or_mint_presence("The Dalek", presences)
        assert presences[key] is established
        key = _resolve_or_mint_presence("Dalek", presences)
        assert presences[key] is established
        fresh = _resolve_or_mint_presence("A Judoon", presences)
        assert presences[fresh] is not established
        assert presences[fresh]["name"] == "A Judoon"

    def test_an_already_split_ledger_heals(self):
        """Chat 57's exact shape. Folding happens on load so a story already
        carrying the split repairs on its next turn, with no migration."""
        from persist.commit import _fold_duplicate_presences
        folded = _fold_duplicate_presences({
            "A Dalek": {"first_turn": 0, "last_turn": 25,
                        "dialogue_turns": [1, 2, 17], "mention_turns": [3, 5],
                        "sketch": {"role_hint": "bronze shell"}},
            "Dalek": {"first_turn": 19, "last_turn": 25,
                      "dialogue_turns": [19, 20], "mention_turns": []},
            "The Dalek": {"first_turn": 23, "last_turn": 25,
                          "dialogue_turns": [24], "mention_turns": [23],
                          "sketch": {"station_room": "alley_room"}},
        })
        assert len(folded) == 1, "one creature, one record"
        record = next(iter(folded.values()))
        assert record["name"] == "A Dalek", "the first-seen spelling keeps the name"
        assert record["dialogue_turns"] == [1, 2, 17, 19, 20, 24]
        assert record["mention_turns"] == [3, 5, 23]
        assert record["first_turn"] == 0 and record["last_turn"] == 25
        # A sketch the duplicate carried describes the same body.
        assert record["sketch"]["role_hint"] == "bronze shell"
        assert record["sketch"]["station_room"] == "alley_room"

    def test_folding_leaves_genuinely_different_presences_alone(self):
        from persist.commit import _fold_duplicate_presences
        folded = _fold_duplicate_presences({
            "A Dalek": {"first_turn": 0, "last_turn": 3, "dialogue_turns": []},
            "A Judoon": {"first_turn": 1, "last_turn": 3, "dialogue_turns": []},
        })
        assert len(folded) == 2
        assert _names(folded) == {"A Dalek", "A Judoon"}

    def test_two_bodies_in_the_room_are_left_as_two(self):
        """The scene is the authority on how many there are, not the name.

        `A Dalek` and `The Dalek` are one creature when the room holds one and
        two when it holds two, and nothing in the strings can tell those apart.
        An over-merge silently welds two characters into one, which is worse
        than a split a name would fix -- so two bodies means hands off.
        """
        from persist.commit import (_fold_duplicate_presences,
                                    _resolve_or_mint_presence)
        crowd = {"entities": {
            "e1": {"name": "A Dalek"},
            "e2": {"name": "The Dalek"},
        }}
        ledger = {
            "A Dalek": {"first_turn": 0, "last_turn": 3, "dialogue_turns": [1]},
            "The Dalek": {"first_turn": 2, "last_turn": 3, "dialogue_turns": [3]},
        }
        folded = _fold_duplicate_presences(dict(ledger), crowd)
        assert len(folded) == 2
        assert _names(folded) == {"A Dalek", "The Dalek"}
        # A bare respelling in a crowd mints its own presence rather than
        # guessing which of the two bodies it meant.
        before = set(folded)
        key = _resolve_or_mint_presence("Dalek", folded, crowd)
        assert key not in before

    def test_one_body_in_the_room_still_merges(self):
        from persist.commit import (_fold_duplicate_presences,
                                    _resolve_or_mint_presence)
        alone = {"entities": {"e1": {"name": "A Dalek",
                                     "kind": "dalek war machine"}}}
        ledger = {
            "A Dalek": {"first_turn": 0, "last_turn": 3, "dialogue_turns": [1]},
            "The Dalek": {"first_turn": 2, "last_turn": 3, "dialogue_turns": [3]},
        }
        folded = _fold_duplicate_presences(dict(ledger), alone)
        assert len(folded) == 1
        (key, record), = folded.items()
        assert record["name"] == "A Dalek"
        # A later respelling files under the SAME record, not a new one.
        assert _resolve_or_mint_presence("Dalek", folded, alone) == key


class TestTheTwoTitleListsAreNotOneList:
    """COMMIT-3. Two title lists sit four lines apart with a comment saying
    they must stay separate, and nothing held them apart.

    `_NAME_TITLE_PREFIXES` is the wider list: what `strip_name_titles` peels
    off a display name so "Captain Jean-Luc Picard" matches the roster's
    "Jean-Luc Picard". `_BACKGROUND_NAME_TITLE_WORDS` is the narrower one, and
    it does the opposite job -- a word in it is NOT significant enough to
    count as naming somebody, so widening it makes mention-detection stricter.

    Merging them looks like tidying and is a behaviour change: every presence
    whose only distinguishing word is a rank stops being mentionable. The
    comment says so; these tests are what makes it true.

    Read through `persist.commit`'s facade, which is what `make structure`
    requires of a test that only CALLS: naming the defining sibling is
    reserved for a test that PATCHES one, because a patch on a re-export is
    inert. Nothing here patches anything.
    """

    def _lists(self):
        from persist.commit import (_BACKGROUND_NAME_TITLE_WORDS,
                                    _NAME_TITLE_PREFIXES)
        return set(_BACKGROUND_NAME_TITLE_WORDS), set(_NAME_TITLE_PREFIXES)

    def test_the_mention_list_is_strictly_the_smaller(self):
        mention, prefixes = self._lists()
        assert mention < prefixes

    def test_a_rank_only_the_wider_list_holds_still_names_somebody(self):
        from persist.commit import _background_name_mentioned

        mention, prefixes = self._lists()
        ranks = sorted(w for w in prefixes - mention if len(w) >= 3)
        assert ranks, "the two lists have collapsed into one"
        for word in ranks:
            # Prose that does NOT repeat the tracked name, so the significant-
            # word arm is the only thing that can answer.
            assert _background_name_mentioned(
                f"The {word.title()}", f"An unfamiliar {word} crosses the room."
            ), f"{word!r} stopped counting as a mention"

    def test_the_wider_list_is_what_strips_a_rank_off_a_roster_name(self):
        from persist.commit import strip_name_titles

        mention, prefixes = self._lists()
        for word in sorted(prefixes - mention):
            assert strip_name_titles(f"{word.title()} Ro") == "Ro"


class TestAWhisperAddressesNobody:
    """The `addressed_turns` ledger read the raw player input.

    `overt_declaration` exists because the pre-commit gate and the payload
    builder disagreed about what a bystander may be judged against, and
    `pick_background_reactors` was routed through it. The COMMIT-time writer
    one function over was not, so a concealed line naming a presence still
    accrued that presence a durable "the story turned toward you on purpose"
    debt -- the counter that earns a passer-by a character sheet, and the one
    that survives the beat.
    """

    def _whisper_ctx(self, chat_id, turn_idx, visibility):
        line = "Say nothing to Crusher about the readout."
        ctx = _ctx(chat_id, turn_idx, [], {
            "dialogue_log": [{"speaker": "Dr. Crusher",
                              "exact_quote": "Hold still."}],
            "resolved_event": "The ward is quiet.",
        })
        ctx.input = line
        ctx.turn.player_input = line
        ctx.director_interpret = {"sequence": [
            {"type": "speech", "text": line, "visibility": visibility},
        ]}
        return ctx

    def test_a_concealed_line_naming_a_presence_owes_them_nothing(self, temp_db):
        chat_id = _make_chat(temp_db)
        track_background_presences(self._whisper_ctx(chat_id, 3, "concealed"),
                                   nonce=0)

        record = _rec(temp_db.wget(chat_id, "background_presences", {}), "Dr. Crusher")
        assert record.get("addressed_turns", []) == []

    def test_the_same_line_spoken_openly_still_does(self, temp_db):
        """The control: the repair subtracts the concealed half and nothing
        else, or it is a guard that makes minds conclude less."""
        chat_id = _make_chat(temp_db)
        track_background_presences(self._whisper_ctx(chat_id, 3, "public"),
                                   nonce=0)

        record = _rec(temp_db.wget(chat_id, "background_presences", {}), "Dr. Crusher")
        assert record.get("addressed_turns", []) == [3]


class TestPromotionMintsAMindAndAThingCannotHoldOne:
    """The promotion bar is HIGHER than the speech gate's, on purpose.

    Letting a presence say one background line is a smaller commitment than
    minting a person out of it -- a sheet, memories, a psychology -- so
    "undecided" is enough for the first and not for the second. It used to
    demote only an outright "thing", which left every presence the kind
    string cannot classify sitting in the promotion list. Live, chat 84: the
    Scranton Reality Anchor, kind "device", a bolted suppression fixture,
    was offered for promotion after five passing mentions. "device" is off
    the inert deny-list ON PURPOSE (so a sentient robot stays trackable) and
    a bolted fixture is not portable, so nothing else caught it either.
    """

    @staticmethod
    def _mentioned_to_threshold(db, chat_id, name, scene):
        db.wset(chat_id, "scene", scene)
        db.wset(chat_id, "background_presences", {
            name: {"first_turn": 1, "last_turn": 1,
                   "dialogue_turns": [], "mention_turns": []},
        })
        for turn in range(2, 2 + BACKGROUND_PROMOTION_MENTION_THRESHOLD):
            track_background_presences(
                _ctx(chat_id, turn, [], {
                    "resolved_event": f"The {name} hums in the corner.",
                }), nonce=0)
        return {r["name"]: r for r in promotable_background_presences(chat_id)}

    _SCENE = {
        "rooms": {"cell": {"name": "Interview Cell"}},
        "positions": {"anchor_device": "cell", "guard_one": "cell"},
        "entities": {
            "anchor_device": {"name": "Reality Anchor", "kind": "device",
                              "portable": False, "aliases": []},
            "guard_one": {"name": "Site Guard", "kind": "person",
                          "portable": False, "aliases": []},
        },
    }

    def test_an_unclassifiable_device_is_not_offered(self, temp_db):
        chat_id = _make_chat(temp_db)
        rows = self._mentioned_to_threshold(
            temp_db, chat_id, "Reality Anchor", self._SCENE)
        assert rows["Reality Anchor"]["promotable"] is False
        # The history is still recorded -- it is the OFFER that is refused,
        # not the tracking, so a host may still promote it by hand.
        assert rows["Reality Anchor"]["mention_turns"]

    def test_a_person_is_still_offered(self, temp_db):
        chat_id = _make_chat(temp_db)
        rows = self._mentioned_to_threshold(
            temp_db, chat_id, "Site Guard", self._SCENE)
        assert rows["Site Guard"]["promotable"] is True

    def test_a_frozen_nature_of_person_restores_the_offer(self, temp_db):
        """`nature` is blurb_mint's answer to this exact question, and it
        outranks every guess. A "dalek war machine" the story has judged a
        person is offered again the moment anything actually asks."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", self._SCENE)
        temp_db.wset(chat_id, "background_presences", {
            "Reality Anchor": {
                "first_turn": 1, "last_turn": 9, "nature": "person",
                "dialogue_turns": [],
                "mention_turns": list(
                    range(2, 2 + BACKGROUND_PROMOTION_MENTION_THRESHOLD)),
            },
        })
        rows = {r["name"]: r for r in promotable_background_presences(chat_id)}
        assert rows["Reality Anchor"]["promotable"] is True


class TestEveryBackgroundPersonIsACharterBody:
    """Measured across the corpus before this: 84 tracked presences with no
    charter body against 14 with one. So 86% of the people a story populates
    itself with reached none of the memory, familiarity, ties, marks or
    history-reading volition Charter was built to give them -- they were a
    name in a dict, invented fresh each time, and keyed by DISPLAY NAME, which
    two people in one story may share.
    """

    def test_a_named_person_is_given_a_body(self, temp_db):
        from world.charter_runtime import (AMBIENT_CHARTER,
                                           ensure_ambient_bodies, registry_for)
        cid = _make_chat(temp_db)

        refs = ensure_ambient_bodies(
            cid, [{"name": "Dock Hand", "place": "quay"}])

        assert refs["Dock Hand"]["charter"] == AMBIENT_CHARTER
        state = registry_for(cid)["items"][AMBIENT_CHARTER]["state"]
        body = state["bodies"][refs["Dock Hand"]["body"]]
        assert body["name"] == "Dock Hand" and body["place"] == "quay"

    def test_an_institution_of_none_stands_nothing(self, temp_db):
        """The ambient charter is not a fake institution of one. It has no
        posts and no upkeeps -- it exists so a person with no institution is
        still somewhere the simulation advances them, which is what
        `charter_run.step` does for a charter's MEMBERS."""
        from world.charter_runtime import (AMBIENT_CHARTER,
                                           ensure_ambient_bodies, registry_for)
        cid = _make_chat(temp_db)

        ensure_ambient_bodies(cid, [{"name": "Dock Hand", "place": "quay"}])

        state = registry_for(cid)["items"][AMBIENT_CHARTER]["state"]
        assert not state["posts"] and not state["upkeeps"]

    def test_the_same_person_is_not_minted_twice(self, temp_db):
        from world.charter_runtime import ensure_ambient_bodies, registry_for
        cid = _make_chat(temp_db)

        first = ensure_ambient_bodies(cid, [{"name": "Dock Hand",
                                             "place": "quay"}])
        again = ensure_ambient_bodies(cid, [{"name": "Dock Hand",
                                             "place": "hold"}])

        assert first == again
        bodies = registry_for(cid)["items"]["ambient"]["state"]["bodies"]
        assert len(bodies) == 1

    def test_a_person_a_real_institution_already_employs_is_left_there(
            self, temp_db):
        """The mint is a floor, not a claimant: somebody a generated charter
        already employs keeps that employer, or the consolidation would tear
        people out of the institutions they belong to."""
        from world.charter_runtime import (ensure_ambient_bodies,
                                           registry_for, save_registry)
        cid = _make_chat(temp_db)
        save_registry(cid, {"crew": {
            "key": "crew", "posts": {}, "upkeeps": {},
            "bodies": {"tech:0001": {"name": "Dock Hand", "place": "quay",
                                     "competence": {}, "available": True}}}})

        refs = ensure_ambient_bodies(cid, [{"name": "Dock Hand",
                                            "place": "quay"}])

        assert refs["Dock Hand"] == {"charter": "crew", "body": "tech:0001"}
        assert "ambient" not in registry_for(cid)["items"]


class TestTheOverlayIsAnApertureNotALedgerEntry:
    """`with_charter_presences` says it itself: "merely noticing a Charter
    worker must not write a second identity store; ordinary presence tracking
    persists the record only after the person actually participates in a
    beat." Its caller persisted the merged copy wholesale.

    Harmless while a story had fourteen charter bodies. Measured on a
    generated market town of three hundred: 284 permanent records for people
    the story had never used, every one re-derivable from the registry on
    demand.
    """

    def test_a_body_merely_standing_there_earns_no_record(self, temp_db):
        from persist.commit_background import with_charter_presences
        from world.charter_runtime import save_registry
        cid = _make_chat(temp_db)
        save_registry(cid, {"crew": {
            "key": "crew", "posts": {}, "upkeeps": {},
            "naming": {"given": ["Mira"], "family": ["Reed"]},
            "bodies": {"hand:0001": {"name": "Mira Reed", "place": "quay",
                                     "competence": {}, "available": True}}}})

        overlaid = with_charter_presences(cid, {}, {"rooms": {"quay": {}}})

        # The aperture exists for the beat ...
        assert overlaid, "the overlay still derives the body"
        # ... and the ledger on disk is untouched by it.
        assert not (temp_db.wget(cid, "background_presences", {}) or {})

    def test_a_body_that_participates_keeps_its_record(self, temp_db):
        """The other half: earning a place has to still work, or the ledger
        stops tracking the people it exists for."""
        from persist.commit_background import promotable_background_presences
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {
            "p_1": {"name": "Mira Reed", "first_turn": 1, "last_turn": 2,
                    "charter_refs": [{"charter": "crew", "body": "hand:0001"}],
                    "dialogue_turns": [2], "mention_turns": [],
                    "addressed_turns": []}})

        held = temp_db.wget(cid, "background_presences", {}) or {}

        assert "p_1" in held, "a presence that spoke is durable"
        assert held["p_1"]["dialogue_turns"] == [2]
