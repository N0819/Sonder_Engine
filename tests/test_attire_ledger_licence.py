"""Prose names the OCCASION of a wardrobe change; the ledger names its inventory.

Chat 98, turn 8 -- the beat where a body ended up in two wardrobes at once.
Every string in this file is the recorded one, taken out of the run's own
`director_resolve` and `commit` rows, because the defect IS the wording gap
and a fixture of invented names cannot carry it.

The beat: the player wrote "She changed out of uniform", the Director resolved
"She changes out of her duty uniform into civilian clothing", and the body
specialist emitted a `remove` naming all five garments the ledger held, spelled
exactly as the ledger held them, plus `replace: ["civilian clothing"]`. Three
guards fired and all three subtracted:

  1. the write gate dropped the `remove` of four of the five, because no word
     of the beat NAMES those garments;
  2. the omission gate put the same four back into `replace` for the same
     reason;
  3. the third, correctly, reported the one survivor as a no-op -- guard 2 had
     already taken it off by omission.

Result: `wearing` held the whole duty uniform AND the civilian clothes for the
rest of the run, while the scene entity said the uniform was taken off and the
prose said it was gone. Three representations of one fact, all different.

Why the per-garment test could not answer it: her ledger carried the same
garment under two authored spellings, so "uniform" -- the one word the beat
actually used -- was carried by two worn garments, and the uniqueness tier that
decides WHICH garment a word means refused both. Every other card in that run
had the same shape.

The rule these tests pin: the beat's words say WHOSE clothing changed; the
ledger says WHICH garments. A `remove` that resolves against the wardrobe is
licensed on a beat whose words are about that body's clothing, however the beat
spells the garment -- and a beat with no clothing in it licenses nothing, which
is the refusal `tests/test_attire_write_gate.py` exists for and which every
control here re-checks.
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist import commit
from story import attire

#: The ledger as chat 98 held it from turn 0 through turn 7. Two spellings of
#: one garment, both authored on the card: the first came from the card's
#: `regions` block, the second from the flat `wearing` list beside it, and
#: `normalize_regions` cannot tell they are the same coat.
_WORN = ["standard Starfleet duty uniform (teal science division shoulders)",
         "combadge", "Starfleet uniform jumpsuit, sciences blue shoulders",
         "black undertunic", "two gold rank pips"]

#: Turn 8's player input, verbatim.
_PLAYER = (
    "The turbolift took her down and she spent the ride with her arms folded, "
    "replaying the whole exchange and finding it survivable. Four hours later "
    "the decomposition was queued, the parameters were Data's problem now as "
    "much as hers, and her shift had ended somewhere in the middle of it. She "
    "changed out of uniform, and went to Ten Forward because the alternative "
    "was her quarters and the same numbers on a smaller screen.")

#: Turn 8's `director_resolve.resolved_event`, verbatim.
_RESOLVED = (
    "Sabine Oyelaran turns from the captain's chair and walks aft across the "
    "bridge to the turbolift doors. The doors part at her approach and she "
    "steps inside the car. She folds her arms and rides the turbolift down "
    "through the decks. Four hours pass. She changes out of her duty uniform "
    "into civilian clothing in her quarters, then walks to Ten Forward. She "
    "enters the lounge and stands near the bar, the shift ended somewhere in "
    "the middle of the queued decomposition parameters now belonging as much "
    "to Data as to her.")

#: Turn 8's `state_diff.attire`, verbatim.
_DIFF = {
    "add": [],
    "remove": ["standard Starfleet duty uniform (teal science division "
               "shoulders)",
               "combadge",
               "Starfleet uniform jumpsuit, sciences blue shoulders",
               "black undertunic",
               "two gold rank pips"],
    "replace": ["civilian clothing"],
    "conditions": {},
    "coverage": {},
    "regions": {},
    "notes": {},
}

#: A beat of the same story with no clothing in it -- the shape the write gate
#: exists to refuse. Turn 22's resolved prose, shortened to one sentence.
_NO_CLOTHING = ("She set the padd down on the table between them and asked "
                "what the second pulse had looked like from ops.")

_NAME = "Sabine Oyelaran"


def _scene():
    return {"positions": {_NAME: "ten_forward"},
            "attire": {_NAME: attire.authored_entry(list(_WORN), [], None)}}


def _ctx(temp_db, player_input, resolved):
    """A chat whose PLAYER is the body under test.

    The persona row is not decoration: `_player_name_or_none` is how the
    attribution ladder knows that "she" in the player's own input is the
    player, and the run this file replays had exactly that shape.
    """
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (_NAME, '{"identity": {"name": "%s"}}' % _NAME, "test"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Ledger", "", time.time(), persona_id))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 8, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Ledger", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=8,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)
    ctx.director_interpret = {}
    ctx.director_resolve = {"resolved_event": resolved}
    return ctx


def _apply(temp_db, diff, *, player_input="", resolved=""):
    sc = _scene()
    ctx = _ctx(temp_db, player_input, resolved)
    commit.apply_attire_diff(sc, {"attire": {_NAME: diff}}, ctx,
                             ctx.director_resolve)
    return sc["attire"][_NAME], ctx


class TestTheLedgerNamesTheInventory:
    """Turn 8, replayed."""

    def test_the_recorded_diff_takes_the_whole_duty_uniform_off(
            self, temp_db):
        """The defect, stated as its outcome: nothing of the duty uniform
        survives the beat, and the civilian clothes are what she has on."""
        entry, ctx = _apply(temp_db, dict(_DIFF),
                            player_input=_PLAYER, resolved=_RESOLVED)

        assert entry["wearing"] == ["civilian clothing"], ctx.warnings

    def test_a_body_is_never_left_in_two_wardrobes(self, temp_db):
        """The measured symptom, pinned separately from the fix.

        What committed in the run was the full duty uniform AND the civilian
        clothing at once. No beat may leave a body wearing the outfit it just
        changed out of alongside the one it changed into.
        """
        entry, _ = _apply(temp_db, dict(_DIFF),
                          player_input=_PLAYER, resolved=_RESOLVED)

        assert "civilian clothing" in entry["wearing"]
        for garment in _WORN:
            assert garment not in entry["wearing"]

    def test_no_guard_reports_a_dropped_removal(self, temp_db):
        """All three notices in the run's commit row were guards subtracting
        state the beat had asked for. None of them should have anything to
        say here."""
        _entry, ctx = _apply(temp_db, dict(_DIFF),
                             player_input=_PLAYER, resolved=_RESOLVED)

        assert not [w for w in ctx.warnings if "attire" in w], ctx.warnings

    def test_the_resolved_prose_alone_carries_the_licence(self, temp_db):
        """The player's input is not always where the beat says it -- an
        NPC's wardrobe changes on beats the player never mentions, and the
        Director's resolved prose is the licence there."""
        entry, _ = _apply(
            temp_db, dict(_DIFF),
            resolved="Sabine Oyelaran changed out of her duty uniform and "
                     "into civilian clothing.")

        assert entry["wearing"] == ["civilian clothing"]

    def test_a_paraphrase_the_ledger_does_not_use_is_still_a_licence(
            self, temp_db):
        """The class, without the run's strings.

        No word of "got out of her work clothes" spells any garment the
        ledger holds; it is unambiguously an undressing of that body.
        """
        entry, _ = _apply(
            temp_db, {"remove": list(_WORN), "replace": []},
            player_input="She got out of her work clothes and left them "
                         "folded on the chair.")

        assert entry["wearing"] == []


class TestTheBeatMustStillBeAboutClothing:
    """The controls. Widening the licence to the BODY must not widen it to
    every beat: the refusals `tests/test_attire_write_gate.py` measured stay
    refusals, on this story's own wardrobe."""

    def test_a_beat_with_no_clothing_in_it_licenses_nothing(self, temp_db):
        entry, ctx = _apply(temp_db, {"remove": list(_WORN)},
                            resolved=_NO_CLOTHING)

        assert entry["wearing"] == _WORN
        assert any("names the garment" in w for w in ctx.warnings)

    def test_a_restatement_may_not_undress_by_omission_either(self, temp_db):
        entry, ctx = _apply(temp_db, {"replace": []}, resolved=_NO_CLOTHING)

        assert entry["wearing"] == _WORN
        assert any("names the garment" in w for w in ctx.warnings)

    def test_another_body_s_clothing_is_not_this_body_s_licence(
            self, temp_db):
        """A beat about somebody else's uniform says nothing about hers."""
        sc = _scene()
        sc["attire"]["Jean-Luc Picard"] = attire.authored_entry(
            ["Starfleet uniform jumpsuit, command red shoulders"], [], None)
        ctx = _ctx(temp_db, "", "Jean-Luc Picard's uniform jumpsuit was "
                                "immaculate, as it always was.")
        commit.apply_attire_diff(sc, {"attire": {_NAME: {
            "remove": list(_WORN)}}}, ctx, ctx.director_resolve)

        assert sc["attire"][_NAME]["wearing"] == _WORN


class TestAnObjectIdIsNotAGarmentHandle:
    """Turn 19, and the seam a beat later.

    A garment that comes off becomes a thing in the room, and the thing has a
    scene key. The body specialist read that key back out of `entities` and
    offered it as a wearable name. The ledger was right to refuse it; the
    diagnosis it gave back was not -- "nothing they are currently wearing
    answers to it" sends the emitter hunting for a spelling when what it
    actually did was address the wrong ledger.
    """

    #: The recorded handle, and the entity key it is: `scene.entities` minted
    #: it when the uniform came off.
    _KEY = ("standard_starfleet_duty_uniform_teal_science_division_shoulders"
            "_sabine_oyelaran")

    def _shed_scene(self):
        sc = _scene()
        sc["attire"][_NAME] = attire.authored_entry(
            ["combadge", "civilian clothing"], [], None)
        sc["entities"] = {self._KEY: {
            "name": "standard Starfleet duty uniform (teal science division "
                    "shoulders)",
            "kind": "object",
            "description": "standard Starfleet duty uniform (teal science "
                           "division shoulders), taken off",
            "state": {"clothing": True, "worn_by": _NAME, "shed": True}}}
        return sc

    def _apply_shed(self, temp_db, resolved):
        sc = self._shed_scene()
        ctx = _ctx(temp_db, "", resolved)
        commit.apply_attire_diff(
            sc, {"attire": {_NAME: {"remove": [self._KEY]}}}, ctx,
            ctx.director_resolve)
        return sc["attire"][_NAME], ctx

    def test_the_removal_still_moves_nothing(self, temp_db):
        entry, _ = self._apply_shed(
            temp_db, "She shrugged the duty uniform off in her quarters.")

        assert entry["wearing"] == ["combadge", "civilian clothing"]

    def test_the_emitter_is_told_it_addressed_the_wrong_ledger(self, temp_db):
        _entry, ctx = self._apply_shed(
            temp_db, "She shrugged the duty uniform off in her quarters.")

        told = " ".join(ctx.engine_feedback)
        assert "THING IN THE SCENE" in told, told
        assert any("not a garment" in w for w in ctx.warnings), ctx.warnings

    def test_a_handle_that_is_no_entity_keeps_the_ordinary_diagnosis(
            self, temp_db):
        """The control: an ordinary misspelling is still an ordinary
        misspelling, and must not be reported as an object."""
        sc = self._shed_scene()
        ctx = _ctx(temp_db, "", "She shrugged the duty uniform off.")
        commit.apply_attire_diff(
            sc, {"attire": {_NAME: {"remove": ["nightwear garment"]}}}, ctx,
            ctx.director_resolve)

        told = " ".join(ctx.engine_feedback)
        assert "THING IN THE SCENE" not in told
        assert "has no removal to apply" in told, told


class TestWhoseClothingThisBeatIsAbout:
    """`wardrobe_change_subjects` on its own, at the unit."""

    _WARDROBE = {
        _NAME: list(_WORN),
        "Jean-Luc Picard": ["Starfleet uniform jumpsuit, command red "
                            "shoulders"],
    }

    def test_the_recorded_beat_names_her(self):
        assert attire.wardrobe_change_subjects(
            _PLAYER, [_RESOLVED], self._WARDROBE, player_name=_NAME) == {_NAME}

    def test_a_beat_with_no_clothing_word_names_nobody(self):
        assert attire.wardrobe_change_subjects(
            _NO_CLOTHING, [], self._WARDROBE, player_name=_NAME) == set()

    def test_a_garment_english_has_no_word_for_still_counts(self):
        """`_CLOTHING_CONTEXT` is a closed English list; the wardrobe's own
        spellings are the open half, exactly as the process reading reads
        them."""
        wardrobe = {_NAME: ["kesh-wrap", "combadge"]}
        assert attire.wardrobe_change_subjects(
            "She unwound the kesh-wrap and folded it.", [], wardrobe,
            player_name=_NAME) == {_NAME}

    def test_a_pronoun_beat_names_nobody(self):
        """THE LIMIT, unchanged from the per-garment gate: a beat whose every
        mention is a pronoun says neither what came off nor whose it was."""
        assert attire.wardrobe_change_subjects(
            "", ["He reaches over and pulls it off her, tossing it aside."],
            self._WARDROBE, player_name=_NAME) == set()
