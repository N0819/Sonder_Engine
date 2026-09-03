"""Closed sets the ENGINE owns, published to the hand that has to write them.

Five fields are read from model output against a fixed set of words and were
never shown that set. The failure is not a model failing to guess: it is the
engine asking a question and withholding the answers, and in each case the
miss is SILENT and expensive --

  * `entities[].kind` decides whether the `destruction` channel is ever
    granted (`director_scopes._gate_facts`), so a hull written `airship`
    leaves the objects specialist without the chunk whose own text says
    NARRATING A DESTRUCTION WITHOUT DECLARING IT IS AN ERROR;
  * `rooms[].adjacent[].barrier` was enumerated for the opening call and the
    repair call and not for the specialist that creates rooms DURING play,
    where an unread word becomes a WALL (`normalize_barrier`'s docstring
    measures the cost: 250 of 1,716 live declarations, 14.6%);
  * `rooms[].size` was not in that specialist's shape at all, so it could not
    be set even by accident, and an unsized room grades as medium;
  * a partial substance transfer needs `source_substance_id`, `portion` and an
    `amount_band` already on the origin -- none of the three appeared in the
    substance_ops sheet, and the failure preserves the origin, so the same
    matter stands in two places at once;
  * four of the nine speech-act kinds the commitment ledger acts on were
    absent from the social specialist's list AND from the whitelist that
    grounds it, so half an undertaking's lifecycle was unreachable code.

This is the OPPOSITE of the no-word-lists rule, and CLAUDE.md says so: "A
closed set the engine OWNS and can enumerate is a schema; a list that tries to
anticipate how English will phrase something is the thing that fails." The
reader of each of these fields accepts these members and nothing else, so the
enumeration can be finished -- which is exactly what an alias table for how
English names a hull can never be.

The tests below take the vocabulary FROM THE ENGINE (a constant, or the
function's own source where the set is an inline literal) rather than
restating it, so widening a set without publishing it fails here. That
pairing is the structural guard: it is what none of these five had.

Three more, found 2026-09-01 by auditing for the same shape:

  * `rooms[].size` again. (c) published the six to the specialist that makes
    rooms during play; the two hands that size MOST rooms -- the opening call
    and the mapping stage -- published three, as a closed alternation, so the
    other three read as non-values. The mapping stage additionally named a
    default (`small`) the engine does not have, grading every ordinary room
    one rank below what silence would have produced;
  * the prose author's DELEGATED CHANNELS paragraph, which is a hand-restated
    copy of `director_scopes.SPECIALISTS` and had drifted to 28 of 31 --
    `comms_ops`, `contact_action_ops`, `public_evidence` absent from a list
    that presents itself as complete;
  * `entities[].ubiquitous`, the flag saying a thing has no location at all.
    Published to the opening call and not to the objects specialist that owns
    `entities` on every normal turn, leaving the engine to guess a bodiless
    voice from a nine-word `kind` list.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest

from language_runtime import installed_language_packs
from llm import schemas
from world.spatial import (
    DEFAULT_ROOM_SIZE,
    ROOM_SIZES,
    SUBSTANCE_AMOUNT_BANDS,
    SUBSTANCE_PORTIONS,
    _VALID_BARRIERS,
    effective_room_size,
    normalize_barrier,
)

LANGUAGES = ("en", "ja")


def _chunk(language: str, specialist: str, chunk: str) -> str:
    """The sheet text one specialist actually receives for one channel."""
    card = installed_language_packs()[language].card("system_prompts")
    return card["specialists"][specialist]["chunks"][chunk]


def _inline_membership_sets(func) -> list[tuple[str, ...]]:
    """Every `x in ('a', 'b', ...)` literal in one function's source.

    Three of these vocabularies are inline literals rather than named
    constants, and a test that restated them would pass forever while the
    engine moved underneath it. Reading the source is the only way to bind to
    the set the engine actually applies; it is the same technique the wiring
    tests use, and it fails loudly if the literal becomes a name (at which
    point bind to the name instead).
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, ast.In):
                continue
            if not isinstance(comparator, (ast.Tuple, ast.Set, ast.List)):
                continue
            values = [e.value for e in comparator.elts
                      if isinstance(e, ast.Constant)
                      and isinstance(e.value, str)]
            if len(values) == len(comparator.elts) and values:
                found.append(tuple(values))
    return found


# ---------------------------------------------------------------------------
# (a) entities[].kind -- the word that decides whether a channel exists
# ---------------------------------------------------------------------------

def destructible_kinds() -> tuple[str, ...]:
    from agents.director import _gate_facts
    sets = [s for s in _inline_membership_sets(_gate_facts) if "vehicle" in s]
    assert len(sets) == 1, (
        "the destructible-kind test in `_gate_facts` is no longer a single "
        f"inline membership literal: {sets}")
    return sets[0]


class TestTheDestructibleKindsArePublished:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_every_kind_the_gate_accepts_is_named_in_the_entities_chunk(
            self, language):
        chunk = _chunk(language, "objects", "entities")
        missing = sorted(k for k in destructible_kinds() if k not in chunk)
        assert not missing, (
            f"{language}: the hand that writes `kind` is not told these words "
            f"open the destruction channel: {missing}")

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_other_half_of_the_test_is_named_too(self, language):
        """`interior_rooms` grants the same channel and is the answer for
        anything the five words do not cover -- a cave system, a hive. Without
        it the published list reads as the whole test, which it is not."""
        assert "interior_rooms" in _chunk(language, "objects", "entities")

    def test_a_published_kind_opens_the_channel(self, temp_db):
        """The publication is only true if the engine honours it."""
        from agents.director import _CHANNEL_GATES, _gate_facts
        ctx = SimpleNamespace(chat={"id": 1}, turn={"idx": 3})
        for kind in destructible_kinds():
            facts = _gate_facts(ctx, {"entities": {"e": {"kind": kind}}},
                                physical=True, speech=False)
            assert _CHANNEL_GATES["destruction"](facts), kind

    @pytest.mark.parametrize("kind", ["airship", "warehouse", "tower",
                                      "barge", "keep"])
    def test_the_miss_direction_this_publication_exists_to_stop(
            self, kind, temp_db):
        """UNCHANGED behaviour, pinned deliberately. Every one of these is an
        ordinary English word for something with a whole to lose, and the
        channel is not refused for them -- it is never offered, on this beat
        or any later one. Widening the tuple to chase these words is the
        alias table that is always one spelling short; the fix is that the
        writing hand now knows which word to use."""
        from agents.director import _CHANNEL_GATES, _gate_facts
        ctx = SimpleNamespace(chat={"id": 1}, turn={"idx": 3})
        facts = _gate_facts(ctx, {"entities": {"e": {"kind": kind}}},
                            physical=True, speech=False)
        assert not _CHANNEL_GATES["destruction"](facts)


# ---------------------------------------------------------------------------
# (b) rooms[].adjacent[].barrier -- unread words become walls
# ---------------------------------------------------------------------------

#: The two members deliberately withheld from the prompt. `spatial_routing`
#: writes `separated` for two rooms with no edge between them and `unknown` is
#: the engine's own no-answer; neither is anybody's to author, and offering
#: them would invite a specialist to declare a room unreachable by writing a
#: word rather than by leaving out an edge.
ENGINE_ONLY_BARRIERS = frozenset({"separated", "unknown"})
AUTHORABLE_BARRIERS = frozenset(_VALID_BARRIERS) - ENGINE_ONLY_BARRIERS


class TestTheBarrierVocabularyReachesTheInPlayRoomWriter:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_every_authorable_barrier_is_named(self, language):
        chunk = _chunk(language, "spatial", "rooms")
        missing = sorted(b for b in AUTHORABLE_BARRIERS if b not in chunk)
        assert not missing, (
            f"{language}: the spatial specialist creates rooms during play "
            f"and is not told these barriers exist: {missing}")

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_engine_only_answers_are_not_offered(self, language):
        chunk = _chunk(language, "spatial", "rooms")
        for barrier in sorted(ENGINE_ONLY_BARRIERS):
            assert barrier not in chunk, (
                f"{language}: {barrier!r} is an engine answer, not an "
                "authorable one")

    @pytest.mark.parametrize("barrier", sorted(AUTHORABLE_BARRIERS))
    def test_every_published_barrier_survives_normalization(self, barrier):
        """The pairing that fails if a member is dropped from the engine
        without the sheet moving with it."""
        assert normalize_barrier(barrier) == barrier

    def test_the_miss_direction_the_publication_exists_to_stop(self):
        """`normalize_barrier` folds what it can and seals the rest, which is
        the right floor and the wrong thing to rely on: a word with no
        understood head noun closes a doorway the beat opened. `force field`
        and `turnstile` are both ways THROUGH and both arrive as walls."""
        assert normalize_barrier("force field") == "wall"
        assert normalize_barrier("turnstile") == "wall"


# ---------------------------------------------------------------------------
# (c) rooms[].size -- six ordered values, absent from the shape entirely
# ---------------------------------------------------------------------------

class TestTheRoomSizeVocabularyReachesTheInPlayRoomWriter:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_every_size_is_named(self, language):
        chunk = _chunk(language, "spatial", "rooms")
        missing = [s for s in ROOM_SIZES if s not in chunk]
        assert not missing, f"{language}: unpublished room sizes {missing}"

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_field_is_in_the_shape_line(self, language):
        """A vocabulary named in prose and absent from the JSON shape is a
        field the hand has no slot to put anywhere. Both halves or neither."""
        assert "size?" in _chunk(language, "spatial", "rooms")

    @pytest.mark.parametrize("size", ROOM_SIZES)
    def test_every_published_size_is_read_back_as_itself(self, size):
        scene = {"rooms": {"r": {"name": "Room", "size": size}}}
        assert effective_room_size(scene, "r") == size

    def test_a_word_outside_the_set_is_indistinguishable_from_silence(self):
        """The miss direction: `enormous` is discarded, and a room authored
        `enormous` grades exactly as a room nobody ever sized. Nothing warns."""
        sized = {"rooms": {"r": {"name": "Room", "size": "enormous"}}}
        unsized = {"rooms": {"r": {"name": "Room"}}}
        assert effective_room_size(sized, "r") == DEFAULT_ROOM_SIZE
        assert effective_room_size(unsized, "r") == DEFAULT_ROOM_SIZE


# ---------------------------------------------------------------------------
# (d) substance magnitude -- three fields, two closed sets, none published
# ---------------------------------------------------------------------------

PARTIAL_TRANSFER_FIELDS = ("source_substance_id", "portion", "amount_band")


class TestTheSubstanceMagnitudeVocabularyIsPublished:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_all_three_fields_a_partial_transfer_needs_are_named(
            self, language):
        chunk = _chunk(language, "contact", "substance_ops")
        missing = [f for f in PARTIAL_TRANSFER_FIELDS if f not in chunk]
        assert not missing, (
            f"{language}: a partial transfer is read from these and the "
            f"sheet does not name them: {missing}")

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_both_closed_value_sets_are_named(self, language):
        chunk = _chunk(language, "contact", "substance_ops")
        missing = [v for v in (*SUBSTANCE_AMOUNT_BANDS, *SUBSTANCE_PORTIONS)
                   if v not in chunk]
        assert not missing, f"{language}: unpublished magnitude words {missing}"

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_shape_line_carries_the_two_new_fields(self, language):
        chunk = _chunk(language, "contact", "substance_ops")
        shape = [line for line in chunk.splitlines()
                 if "substance_ops:[" in line]
        assert shape, f"{language}: no shape line in the substance chunk"
        for field in ("amount_band", "portion", "source_substance_id"):
            assert field in shape[0], f"{language}: {field!r} not in the shape"


# ---------------------------------------------------------------------------
# (e) public_evidence[].speech_acts[].kind -- nine kinds, five reachable
# ---------------------------------------------------------------------------

def commitment_kinds() -> tuple[str, ...]:
    """The kinds `update_commitments` acts on, read from its own source.

    Two inline literals: the three that OPEN an undertaking and the six that
    move a standing one. Anything else the ledger simply never sees.
    """
    from world.charter_commitment import observe_public_commitments
    sets = _inline_membership_sets(observe_public_commitments)
    opening = [s for s in sets if "promise" in s]
    moving = [s for s in sets if "agreement" in s]
    assert len(opening) == 1 and len(moving) == 1, (
        f"the commitment ledger's kind literals moved: {sets}")
    return tuple(opening[0]) + tuple(moving[0])


class TestEveryCommitmentKindCanActuallyArrive:
    def test_the_ledger_reads_nine_kinds(self):
        """Bounds the two tests below: if the ledger grows a tenth verb, the
        count moves and both halves of the publication have to be revisited."""
        assert len(commitment_kinds()) == 9

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_every_kind_is_offered_to_the_social_specialist(self, language):
        chunk = _chunk(language, "social", "public_evidence")
        missing = [k for k in commitment_kinds() if k not in chunk]
        assert not missing, (
            f"{language}: the ledger acts on these and the sheet does not "
            f"offer them: {missing}")

    def test_every_kind_survives_the_grounding_whitelist(self):
        """The half a prompt alone could not fix. `_ground_public_evidence`
        coerces any kind outside `_PUBLIC_SPEECH_ACTS` to `other`, which the
        ledger cannot read -- so a kind published in the prompt and missing
        here is worse than not publishing it: the hand writes the right word
        and the engine throws it away."""
        from agents.director import _PUBLIC_SPEECH_ACTS
        missing = [k for k in commitment_kinds()
                   if k not in _PUBLIC_SPEECH_ACTS]
        assert not missing, (
            f"coerced to 'other' before the ledger sees them: {missing}")


class TestTheFourKindsThatCouldNotArriveNowMoveTheLedger:
    """Behavioural proof that the four are ledger verbs and not decoration.

    Each acts on the undertaking standing between the two speakers, and each
    lands its own terminal state -- which is what made their absence a missing
    half of a lifecycle rather than a missing synonym.
    """

    @staticmethod
    def _standing():
        from world.charter_commitment import observe_public_commitments
        standing, _counts = observe_public_commitments(
            {},
            [{"kind": "speech", "source_id": "s1", "actor": "Ada",
              "target": "Bo",
              "speech_acts": [{"kind": "promise", "content": "the key"}]}],
            {"s1": ["Ada", "Bo"]}, at_hours=1.0)
        return standing

    @pytest.mark.parametrize("kind,state", [
        ("dispute", "disputed"),
        ("release", "released"),
        ("repudiation", "repudiated"),
        ("transfer", "transferred"),
    ])
    def test_the_kind_lands_its_state(self, kind, state):
        from world.charter_commitment import observe_public_commitments
        after, _counts = observe_public_commitments(
            self._standing(),
            [{"kind": "speech", "source_id": "s2", "actor": "Bo",
              "target": "Ada",
              "speech_acts": [{"kind": kind, "content": "the key"}]}],
            {"s2": ["Ada", "Bo"]}, at_hours=2.0)
        assert [r["state"] for r in after.values()] == [state]

    def test_an_unpublished_word_leaves_the_undertaking_open(self):
        """The cost the publication removes: a promise nobody can be released
        from stays open for the rest of the story."""
        from world.charter_commitment import observe_public_commitments
        after, _counts = observe_public_commitments(
            self._standing(),
            [{"kind": "speech", "source_id": "s2", "actor": "Bo",
              "target": "Ada",
              "speech_acts": [{"kind": "absolution", "content": "the key"}]}],
            {"s2": ["Ada", "Bo"]}, at_hours=2.0)
        assert [r["state"] for r in after.values()] == ["open"]


# ---------------------------------------------------------------------------
# (f) rooms[].size AGAIN -- the two hands that size most of the rooms
# ---------------------------------------------------------------------------
#
# (c) above published the six to the specialist that creates rooms during
# play. That is not the hand that sizes most rooms: `director_establish` sizes
# every room the scene opens with, and `mapping_stage` runs on every turn that
# touches the map. Both published THREE of the six, and not as an omission --
# as a SET: "size:'small'|'medium'|'large'" and "'small' by default, 'large'
# only when it is genuinely big". A hand told the vocabulary is three words
# does not reach for a fourth. The three withheld include both ENDS, so they
# are the ones carrying the most information: a cupboard graded as a bedroom,
# a cathedral graded as a hall.

SIZING_PROMPTS = ("director_establish",)

#: The exact text each hand carried, quoted so the fix cannot regress into a
#: paraphrase of the same three-value scale. Substring checks, so they also
#: catch the alternation reappearing inside a longer sentence.
SUPERSEDED_SIZE_TEXT = {
    "director_establish": ("size:'small'|'medium'|'large'",),
}


def _prompt(language: str, name: str) -> str:
    return installed_language_packs()[language].card(
        "system_prompts")["prompts"][name]


class TestBothRoomSizingHandsSeeTheWholeScale:
    @pytest.mark.parametrize("language", LANGUAGES)
    @pytest.mark.parametrize("prompt", SIZING_PROMPTS)
    def test_every_size_is_named(self, language, prompt):
        text = _prompt(language, prompt)
        missing = [s for s in ROOM_SIZES if s not in text]
        assert not missing, (
            f"{language}/{prompt}: this hand authors `size` and is not told "
            f"these values exist: {missing}")

    @pytest.mark.parametrize("language", LANGUAGES)
    @pytest.mark.parametrize("prompt", SIZING_PROMPTS)
    def test_the_three_value_scale_is_not_offered_as_the_set(
            self, language, prompt):
        """The exact text that made the other three unreachable. A closed
        alternation naming three of six does not merely omit the rest; it
        states that they are not values. `mapping_stage`'s half of this is
        worse than an omission -- see the test below."""
        text = _prompt(language, prompt)
        present = [s for s in SUPERSEDED_SIZE_TEXT[prompt] if s in text]
        assert not present, f"{language}/{prompt}: still carries {present}"

    def test_the_mapping_stage_had_stated_a_default_the_engine_does_not_have(
            self):
        """Its instruction was "'small' by default". The engine's default is
        `medium` -- what `effective_room_size` returns for an unsized room --
        so a hand obeying that sentence graded every ordinary room one rank
        BELOW what writing nothing would have produced, on the one axis
        `proximity_rel` reads for near-versus-across. This pins the fact that
        made the sentence wrong, which the string check above cannot."""
        assert DEFAULT_ROOM_SIZE == "medium"
        assert effective_room_size({"rooms": {"r": {"name": "Room"}}}, "r") \
            == "medium"


# ---------------------------------------------------------------------------
# (g) the prose author's DELEGATED CHANNELS list -- 28 of the 31
# ---------------------------------------------------------------------------
#
# Not a value vocabulary but the same failure one level up: a closed set the
# engine owns (`director_scopes.SPECIALISTS`) restated by hand in a prompt and
# drifted from. That paragraph is the prose author's ONLY statement of what is
# not its to write, and it presents itself as the complete delegation -- so a
# channel missing from it reads as one the author may still encode, and what
# it writes in a delegated channel is discarded unread. `comms_ops` was the
# costly absence: it is in SPEECH_WRITTEN_CHANNELS ("a line carried by a
# device IS the op"), so a beat of pure dialogue settles it, which is the beat
# the author is least likely to think a specialist is involved in.

def _delegation_block(language: str) -> str:
    """The prose author sheet's one DELEGATED CHANNELS paragraph.

    Found by content rather than by index: the sheet is a list of blocks, and
    a fragment inserted above this one would silently move it.
    """
    card = installed_language_packs()[language].card("system_prompts")
    # `SOCIAL FABRIC` is spelled the same in both packs and appears in this
    # block alone (the world's traffic folded into it on 2026-09-04, when
    # the offscreen hand was retired).
    blocks = [text for _key, text in card["prose_author_sheet"]
              if isinstance(text, str) and "SOCIAL FABRIC" in text]
    assert len(blocks) == 1, (
        f"{language}: expected one delegated-channels block, got "
        f"{len(blocks)}")
    return blocks[0]


def delegated_channels() -> list[str]:
    from agents.director import SPECIALISTS
    return [channel for spec in SPECIALISTS.values()
            for channel in spec["channels"]]


class TestEveryDelegatedChannelIsNamedAsDelegated:
    def test_the_engine_owns_thirty(self):
        """Bounds the tests below: a specialist that gains a channel moves
        this count, and the sheet has to move in the same commit. 31 until
        2026-09-04; `offscreen_plan_ops` left the Director's diff with the
        offscreen hand (a plan is a character's own declaration)."""
        assert len(delegated_channels()) == 30

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_sheet_names_all_of_them(self, language):
        block = _delegation_block(language)
        missing = [c for c in delegated_channels() if c not in block]
        assert not missing, (
            f"{language}: channels a specialist owns that the prose author's "
            f"delegation paragraph does not name: {missing}. An unlisted "
            "channel reads as one the author may still write, and what it "
            "writes there is discarded unread and re-encoded anyway.")

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_channel_names_stay_identifiers_in_both_packs(self, language):
        """The ja pack had translated eleven of them, and one translation was
        wrong in a way prose cannot be: `stations` as 駅, a railway station.
        A state_diff channel name is an identifier -- a sheet cannot name a
        channel it has translated out of existence."""
        block = _delegation_block(language)
        for channel in delegated_channels():
            assert channel in block, f"{language}: {channel!r}"


# ---------------------------------------------------------------------------
# (h) entities[].ubiquitous -- the flag that says a thing has no place at all
# ---------------------------------------------------------------------------

class TestTheBodilessVoiceFlagReachesTheHandThatMintsEntities:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_objects_specialist_is_told_the_field_exists(self, language):
        """`director_establish` published it and the specialist that owns
        `entities` on every NORMAL turn did not, so a bodiless voice first
        written mid-story could not be flagged at all."""
        assert "ubiquitous" in _chunk(language, "objects", "entities")

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_field_is_in_the_shape_line(self, language):
        chunk = _chunk(language, "objects", "entities")
        shape = [line for line in chunk.splitlines()
                 if "entities:{entity_id:{" in line]
        assert shape, f"{language}: no shape line in the entities chunk"
        assert "ubiquitous" in shape[0], (
            f"{language}: taught in prose with no slot in the shape")

    def test_the_flag_survives_the_validation_round_trip(self):
        """A published field the round-trip drops is worse than an
        unpublished one: the hand writes the right thing and the engine
        throws it away before any reader sees it."""
        entity = schemas.SceneEntityDef(name="Overseer", kind="agent",
                                        ubiquitous=True)
        assert schemas._dump(entity).get("ubiquitous") is True

    def test_the_flag_is_what_exempts_a_voice_from_being_placed(self):
        from story.scene import is_ubiquitous_entity
        assert is_ubiquitous_entity({"kind": "agent", "ubiquitous": True})
        assert schemas._unplaced_establish_entities({
            "entities": {"o": {"name": "Overseer", "kind": "agent",
                               "ubiquitous": True}},
            "positions": {}}) == []

    def test_the_miss_direction_this_publication_exists_to_stop(self):
        """UNCHANGED behaviour, pinned deliberately. Without the flag a
        bodiless voice can only be inferred from `kind` matching
        `scene.UBIQUITOUS_KINDS`, a nine-word list whose own comment calls
        itself deliberately narrow -- the alias table that is always one
        spelling short. An overseer, an oracle, a house are each an ordinary
        word for the same thing and miss it, and each is then reported as an
        entity somebody forgot to position, on this beat and every later one.
        Widening the list is not the fix; the writing hand knowing the flag
        is."""
        from story.scene import is_ubiquitous_entity
        for kind in ("overseer", "oracle", "house", "choir", "agent"):
            assert not is_ubiquitous_entity({"kind": kind}), kind
        assert schemas._unplaced_establish_entities({
            "entities": {"o": {"name": "Overseer", "kind": "agent"}},
            "positions": {}}) != []
