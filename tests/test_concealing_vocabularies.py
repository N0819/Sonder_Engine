"""Two fields whose published vocabulary made CONCEALMENT the likely answer.

Both are perception fields written by a model, and both failed in the same
direction: an ordinary, honest English word for what happened HID something
from observers who should have perceived it, while writing nothing at all
would have been safe. That is the reverse of the usual leak and it is just as
much an engine failure, because in each case the hand was never told what the
field's answers mean.

  * `inventory_ops[].relation` (the objects specialist) becomes the carried
    ledger's containment `mode` verbatim, and every mode outside the five
    `_OPEN_CONTAINMENT_MODES` conceals. The vocabulary was published only in
    the CONTACT specialist's `containment` chunk, which the objects hand never
    receives; its own chunk named the field once inside a JSON shape and
    defined it nowhere. So "held_by" or "in_hand" -- the natural way to say a
    thing is in someone's fist -- handed the object over AND made it invisible
    to the room, where an omitted `relation` would have left it in plain view.

  * `manifest.tells[].channel` (the character sheet) was offered as six BODY
    REGIONS against the only branch that reads it, which asks a two-way SENSE
    question. Four of the six values were sight-only, so a swallow, a breath
    caught, a hand drumming the table were lost on any mind that could hear
    but not see.

The fix in both cases is to publish the closed set the ENGINE owns to the hand
that must write the field -- the opposite of the word-list failure, which is
an open-ended attempt to anticipate English. These tests hold that publication
in place and pin the miss direction that motivated it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.perception import (
    TELL_CHANNELS,
    _delivered_manifest,
    tell_is_audible,
)
from language_runtime import installed_language_packs
from world.spatial import (
    _OPEN_CONTAINMENT_MODES,
    hiding_holders_of,
    merge_scene_with_diff,
)


LANGUAGES = ("en", "ja")
CARD = "system_prompts"


def _card(language: str) -> dict:
    return installed_language_packs()[language].card(CARD)


# ---------------------------------------------------------------------------
# (a) inventory_ops[].relation
# ---------------------------------------------------------------------------

THING = "brass_key"
BODY = "Ada"


def _scene() -> dict:
    """One room, one body, one thing. `attire` is what makes a body a body --
    `_is_body_entity` derives it rather than trusting a `kind` label, and
    without it the transfer resolves to an anchor and never reaches the
    carrier branch this file is about."""
    return {
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {BODY: "hall"},
        "attire": {BODY: {}},
        "entities": {THING: {"name": "brass key", "kind": "object",
                             "portable": True}},
    }


def _transfer(relation=None) -> dict:
    op = {"op": "give", "object_id": THING, "from_id": "Bo", "to_id": BODY}
    if relation is not None:
        op["relation"] = relation
    return {"inventory_ops": [op]}


def _inventory_chunk(language: str) -> str:
    return _card(language)["specialists"]["objects"]["chunks"]["inventory_ops"]


class TestTheRelationVocabularyIsPublishedToTheHandThatWritesIt:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_every_in_view_mode_the_engine_honours_is_named(self, language):
        """`_OPEN_CONTAINMENT_MODES` is the whole of the sighted half. A mode
        the engine grants sight to and the chunk does not name is a word the
        hand has no reason to reach for -- and reaching past it conceals."""
        chunk = _inventory_chunk(language)
        missing = sorted(m for m in _OPEN_CONTAINMENT_MODES if m not in chunk)
        assert not missing, (
            f"{language}: the objects specialist is asked for a containment "
            f"mode and is not told these grant sight: {missing}")

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_shut_away_half_is_named_too(self, language):
        """Publishing only the open half would teach the split as a default
        rather than a choice; the concealing words are the ones a pocketed
        thing needs."""
        chunk = _inventory_chunk(language)
        for mode in ("pocket", "container", "inside"):
            assert mode in chunk, f"{language}: {mode!r} unpublished"

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_chunk_says_an_unlisted_word_conceals(self, language):
        """The rule that makes the list load-bearing rather than decorative.
        Both packs must carry the engine's own token for the fallback."""
        chunk = _inventory_chunk(language)
        assert "held_by" in chunk and "in_hand" in chunk, (
            f"{language}: the chunk does not show what an invented relation "
            "costs, which is the only reason the list is worth reading")


class TestTheMissDirectionThisPublicationExistsToStop:
    def test_an_unvouched_relation_hides_what_was_handed_over(self):
        """The behaviour is UNCHANGED and deliberate -- a word the engine
        cannot vouch for must not be the one that grants sight -- so this
        pins the cost the prompt now warns about rather than a fix."""
        merged = merge_scene_with_diff(_scene(), _transfer("held_by"))
        assert hiding_holders_of(merged, THING) == [BODY]

    def test_omitting_the_relation_leaves_it_in_plain_view(self):
        """Saying nothing was always safe, which is what made the missing
        definition a trap: the more precisely the hand described the carry,
        the more likely the object was to vanish."""
        merged = merge_scene_with_diff(_scene(), _transfer())
        assert hiding_holders_of(merged, THING) == []

    @pytest.mark.parametrize("mode", sorted(_OPEN_CONTAINMENT_MODES))
    def test_every_published_in_view_word_actually_keeps_it_in_view(self, mode):
        """The publication is only true if the engine honours it. This is the
        pairing that would fail if `_OPEN_CONTAINMENT_MODES` were narrowed
        without the chunk moving with it."""
        merged = merge_scene_with_diff(_scene(), _transfer(mode))
        assert hiding_holders_of(merged, THING) == []


# ---------------------------------------------------------------------------
# (b) manifest.tells[].channel
# ---------------------------------------------------------------------------

SOURCE = "Bo"
OBSERVER = "Ada"


def _dark_room_scene() -> dict:
    """One unlit room. Sight fails; hearing does not."""
    return {
        "rooms": {"cellar": {"name": "Cellar", "desc": "No windows.",
                             "light": "dark", "adjacent": []}},
        "positions": {OBSERVER: "cellar", SOURCE: "cellar"},
    }


def _deliver(channel, scene=None):
    """What OBSERVER receives of SOURCE's one tell. Subtlety 0 so only the
    channel gate can suppress it -- `tell_gate` is a separate question."""
    ctx = SimpleNamespace(character_results={
        7: {"manifest": {"surface_demeanor": "even",
                         "tells": [{"channel": channel,
                                    "cue": "a swallow he does not hide",
                                    "subtlety": 0.0}]}}})
    out = _delivered_manifest(
        ctx, scene if scene is not None else _dark_room_scene(), OBSERVER,
        [{"name": SOURCE, "room": "cellar"}],
        {OBSERVER: [SOURCE]}, {SOURCE: 7})
    return (out.get(SOURCE) or {}).get("cues", [])


class TestATellReachesAMindThatCannotSee:
    def test_the_dark_room_actually_blinds_the_observer(self):
        """Guard on the fixture itself: if sight survived here, every
        assertion below would pass for the wrong reason."""
        from world.spatial import visual_level_between
        assert visual_level_between(_dark_room_scene(), OBSERVER, SOURCE) \
            == "none"

    def test_a_heard_tell_lands_on_a_listener_who_cannot_see(self):
        assert _deliver("heard") == ["a swallow he does not hide"]

    def test_a_seen_tell_does_not(self):
        """The complement, and the reason the default cannot be flipped: a
        glance at the door must not reach a blind observer."""
        assert _deliver("seen") == []

    @pytest.mark.parametrize("legacy", ["voice", "breath"])
    def test_the_two_spellings_stored_manifests_carry_still_work(self, legacy):
        """`voice` and `breath` are what the sheet published before `heard`
        existed, so every stored variant replayed from a rerun carries them.
        Dropping them would make the old data concealing."""
        assert _deliver(legacy) == ["a swallow he does not hide"]

    @pytest.mark.parametrize("chan", ["face", "eyes", "hands", "posture",
                                      "tone", "", None])
    def test_a_word_the_engine_cannot_vouch_for_is_sight_only(self, chan):
        """Unrecognised stays sight-only ON PURPOSE. That is the firewall,
        not the defect: nothing deciding who perceives what may depend on the
        character model picking a good word. The four body regions here are
        exactly the sight-only values the old enum offered, which is what the
        prompt change is for."""
        assert _deliver(chan) == []

    def test_sight_still_reaches_every_tell(self):
        """Over-subtraction guard. An observer who can see gets the cue
        whatever its channel says -- this branch was never the bug."""
        lit = _dark_room_scene()
        lit["rooms"]["cellar"]["light"] = "lit"
        for chan in ("seen", "heard", "face", "voice", None):
            assert _deliver(chan, lit) == ["a swallow he does not hide"]


class TestTheEngineOwnsTheModalitySet:
    def test_tell_is_audible_answers_for_the_whole_published_set(self):
        """`TELL_CHANNELS` is the vocabulary the sheet offers, so exactly one
        of its members must be the audible one -- otherwise the sheet is
        offering an answer the engine has no sense for."""
        audible = [c for c in TELL_CHANNELS if tell_is_audible(c)]
        assert audible == ["heard"]
        assert set(TELL_CHANNELS) == {"seen", "heard"}

    @pytest.mark.parametrize("spelling", ["Heard", " heard ", "VOICE"])
    def test_case_and_padding_do_not_conceal(self, spelling):
        """A capitalised word is not an unrecognised one; the branch it
        replaced lowercased but did not strip."""
        assert tell_is_audible(spelling) is True

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_sheet_publishes_the_sense_and_not_the_body_parts(self,
                                                                  language):
        """The whole of the change: six regions become two senses. Both packs
        must move together, and the enum is the canonical token that has to
        appear in both."""
        prompt = _card(language)["prompts"]["character"]
        assert '"channel":"seen|heard"' in prompt
        assert "face|eyes|voice|hands|posture|breath" not in prompt

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_sheet_states_the_test_the_field_answers(self, language):
        """Not a list of instances: the question is whether the cue reaches a
        mind that cannot see, and both published values must be named where
        the rule is stated as well as inside the JSON shape."""
        prompt = _card(language)["prompts"]["character"]
        for value in TELL_CHANNELS:
            assert prompt.count(f"`{value}`") >= 1, (
                f"{language}: {value!r} appears only in the output shape, so "
                "nothing tells the hand when to choose it")
