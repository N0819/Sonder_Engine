"""Release: the exit side of restraint.

`test_restraint_records.py` covers the relation being read and the movement
floor honouring it. This covers the gate coming OFF, which is the reason the
floor was held out of service at all (commit 30bc3d6): a gate that can be
entered and not left is worse than no gate.

The corpus, measured read-only against the owner's live engine.db
(2026-08-18): 24 active restraint-family rows, and NOT ONE has ever been
ended -- no row anywhere carries a restraint ending, and the Director has
never once re-emitted any condition with active:0 across 1483 resolves.
The two causes are the same two the awareness exits fixed one section up:
the resolve payload never showed the Director a restraint or the
condition_id an ending must re-emit (`_restraint_view` now does), and
nothing deterministic enforced the exits that are not judgement calls
(`_restraint_exits`).

What is deterministic is narrower than waking, because a restraint does not
end on a clock -- a rope stays tied all night:

1. A hold whose named holder is POSITIVELY gone (another room, or below
   waking) has physically ended. Standing restraints are untouched.
2. A completed release the Director's own resolved prose asserts is
   encoded. Attempts -- struggling, working at the knots -- are contests,
   and contests stay the Director's.
"""

from __future__ import annotations

from agents.director import (
    _release_attempts,
    _restraint_exits,
    _restraint_holder_pool,
    _restraint_view,
)
from story.scene import apply_restraint_records_diff

SUBJECT = "Hinami"
HOLDER = "Tamamo"


def _record(state, cond_id="c1", subject=SUBJECT, started=100.0):
    return apply_restraint_records_diff([], {"conditions": {cond_id: [{
        "condition_id": cond_id, "subject_id": subject, "kind": "restraint",
        "started_at_seconds": started, "state": state}]}})[0]


def _scene(**positions):
    return {"rooms": {"cell": {"name": "Cell"}, "hall": {"name": "Hall"}},
            "positions": dict(positions), "entities": {}, "contained": {}}


def _gated(name):
    return {name.casefold(): {"subject": name, "level": "unconscious",
                              "cause": "", "rousable_by": "",
                              "condition_id": "a1"}}


# --- rule 1: a hold needs a holder ------------------------------------------

class TestAHoldNeedsAHolder:
    def test_a_holder_in_another_room_ends_the_hold(self):
        record = _record({"level": "held", "by": HOLDER})
        sc = _scene(Hinami="cell", Tamamo="hall")
        endings, warnings = _restraint_exits(
            [record], "", sc, {}, [SUBJECT, HOLDER])
        assert "c1" in endings
        ended = endings["c1"][0]
        assert ended["condition_id"] == "c1"
        assert ended["kind"] == "restraint"
        assert ended["active"] == 0
        assert warnings

    def test_a_holder_below_waking_ends_the_hold(self):
        record = _record({"level": "pinned", "by": HOLDER})
        sc = _scene(Hinami="cell", Tamamo="cell")
        endings, _ = _restraint_exits(
            [record], "", sc, _gated(HOLDER), [SUBJECT, HOLDER])
        assert "c1" in endings

    def test_a_standing_binding_survives_its_tier_leaving(self):
        """A knot stays tied when the person who tied it walks away."""
        record = _record({"level": "bound", "by": HOLDER})
        sc = _scene(Hinami="cell", Tamamo="hall")
        endings, warnings = _restraint_exits(
            [record], "", sc, {}, [SUBJECT, HOLDER])
        assert endings == {}
        assert warnings == []

    def test_a_hold_vouching_for_nobody_is_not_ended(self):
        """Ending what cannot be verified is adjudication. The record stays
        the Director's to settle -- and it already blocks nobody."""
        record = _record({"type": "held_in_embrace"})
        sc = _scene(Hinami="cell")
        endings, _ = _restraint_exits([record], "", sc, {}, [SUBJECT, HOLDER])
        assert endings == {}

    def test_an_unknown_position_is_not_evidence_of_departure(self):
        record = _record({"level": "held", "by": HOLDER})
        sc = _scene(Hinami="cell")  # holder has no recorded position
        endings, _ = _restraint_exits([record], "", sc, {},
                                      [SUBJECT, HOLDER])
        assert endings == {}


# --- rule 2: a release the prose asserts ------------------------------------

class TestAReleaseTheProseAsserts:
    def test_an_uncuffing_in_the_resolved_prose_ends_the_restraint(self):
        record = _record({"restraint_type": "metal_cuffs"})
        sc = _scene(Hinami="cell")
        endings, warnings = _restraint_exits(
            [record], "Sarah Moon uncuffs Hinami and helps her to her feet.",
            sc, {}, [SUBJECT, "Sarah Moon"])
        assert "c1" in endings
        assert endings["c1"][0]["active"] == 0
        assert warnings

    def test_cutting_a_subject_loose_reads_as_release(self):
        record = _record({"level": "bound"})
        sc = _scene(Hinami="cell")
        endings, _ = _restraint_exits(
            [record], "Kaede cuts Hinami loose with two strokes.",
            sc, {}, [SUBJECT, "Kaede"])
        assert "c1" in endings

    def test_a_released_breath_is_not_a_released_body(self):
        """`releases` bare is prose's commonest exhale; only `released from`
        and the completed-release verbs count."""
        record = _record({"level": "bound"})
        sc = _scene(Hinami="cell")
        endings, _ = _restraint_exits(
            [record], "Hinami releases a shaky breath against the straps.",
            sc, {}, [SUBJECT])
        assert endings == {}

    def test_a_struggle_is_a_contest_not_a_release(self):
        record = _record({"level": "bound"})
        sc = _scene(Hinami="cell")
        endings, _ = _restraint_exits(
            [record], "Hinami strains against the cuffs, wrists reddening.",
            sc, {}, [SUBJECT])
        assert endings == {}

    def test_a_spoken_promise_to_untie_is_a_plan_not_an_act(self):
        """`_release_attempts` reads only resolved_event; dialogue is a
        person still holding the rope while they talk."""
        assert _release_attempts("", [SUBJECT]) == set()
        # the caller never passes quotes, and the cue does not fire on the
        # prose merely REPORTING speech about a future release
        assert _release_attempts(
            '"I\'ll get you out of these," Sarah promises, checking the '
            "locks.", [SUBJECT]) == set()

    def test_a_release_ends_every_record_on_that_subject(self):
        """Live chat 80 holds six redescriptions of the same cuffs. Prose
        asserting the body released must not leave five of them standing."""
        records = apply_restraint_records_diff([], {"conditions": {
            "c1": [{"condition_id": "c1", "subject_id": SUBJECT,
                    "kind": "restraint",
                    "state": {"restraint_type": "metal_cuffs"}}],
            "c2": [{"condition_id": "c2", "subject_id": SUBJECT,
                    "kind": "restraint",
                    "state": {"restraint_type": "chair_restraints"}}],
        }})
        sc = _scene(Hinami="cell")
        endings, _ = _restraint_exits(
            records, "Sarah Moon unshackles Hinami from the chair.",
            sc, {}, [SUBJECT, "Sarah Moon"])
        assert set(endings) == {"c1", "c2"}


# --- the view: what the Director is finally shown ---------------------------

class TestRestraintView:
    def test_the_view_names_the_id_an_ending_must_reemit(self):
        record = _record({"restraint_type": "metal_cuffs", "by": "Sarah"},
                         started=100.0)
        sc = _scene(Hinami="cell", Sarah="cell")
        view = _restraint_view([record], sc, {},
                               {"elapsed_seconds": 400.0}, None,
                               [SUBJECT, "Sarah"])
        assert len(view) == 1
        entry = view[0]
        assert entry["condition_id"] == "c1"
        assert entry["subject"] == SUBJECT
        assert entry["level"] == "bound"
        assert entry["holds_unattended"] is True
        assert entry["blocks_self_relocation"] is True
        assert entry["restrained_for_seconds"] == 300

    def test_a_live_hold_reports_its_holder_still_holding(self):
        record = _record({"level": "held", "by": HOLDER})
        sc = _scene(Hinami="cell", Tamamo="cell")
        entry = _restraint_view([record], sc, {}, {}, None,
                                [SUBJECT, HOLDER])[0]
        assert entry["holder_still_holding"] is True
        assert entry["blocks_self_relocation"] is True

    def test_a_hold_vouching_for_nobody_says_so(self):
        """The live embrace and lever-grip rows: the Director sees the
        record, sees it vouches for nobody, and knows the engine will not
        block or end it -- settling it is the Director's."""
        record = _record({"type": "held_in_embrace"})
        entry = _restraint_view([record], _scene(Hinami="cell"), {}, {},
                                None, [SUBJECT])[0]
        assert entry["holder_still_holding"] is None
        assert entry["blocks_self_relocation"] is False

    def test_the_holder_pool_offers_entities_too(self):
        """A vine, a mechanism or a crowd-mass can hold a body exactly as a
        person can."""
        sc = _scene(Hinami="cell")
        sc["entities"] = {"vine_mass": {"name": "the strangler vine"}}
        pool = _restraint_holder_pool(sc, ["Hinami"])
        assert "the strangler vine" in pool
        assert "vine_mass" in pool


# --- the cue's precision, measured rather than designed ----------------------
#
# There are no historical release sentences to measure `_RELEASE_CUE` against
# -- across the whole live corpus, no restraint has ever ended -- so its
# precision was designed, not measured. This battery is the substitute: every
# false-positive class an adversarial pass found, each asserted with the
# genuine release phrasing nearest to it, so a tightening that buys precision
# by silently dropping recall fails here too. The classes, and who answers
# them: dialogue is masked (a quoted "I will untie you" is a plan spoken by
# someone still holding the rope); an act introduced as TRYING is not
# completed; a transitive release names its object NEXT to the verb, so a
# restrained name further than a short reach after the cue -- or past the
# cue's own "free"/"loose" -- is a bystander, not the thing released; and a
# possession coming loose ("Hinami's hair pulls loose") is not the person
# coming free, so a possessive name never carries subject-side attribution.

class TestReleasePrecision:
    def test_a_quoted_promise_inside_resolved_prose_is_a_plan(self):
        assert _release_attempts(
            '"I will untie you," Sarah tells Hinami, settling in to wait.',
            [SUBJECT]) == set()

    def test_a_try_is_not_a_completion(self):
        assert _release_attempts(
            "Hinami tries to work her wrists free, but the straps hold.",
            [SUBJECT]) == set()

    def test_a_release_still_in_progress_is_not_a_completion(self):
        assert _release_attempts(
            "Sarah begins to unbuckle the straps around Hinami's wrists.",
            [SUBJECT]) == set()

    def test_an_earlier_unrelated_try_does_not_suppress_the_release(self):
        assert _release_attempts(
            "No longer trying to be gentle, Sarah cuts Hinami loose.",
            [SUBJECT]) == {SUBJECT}

    def test_managing_it_is_completing_it(self):
        assert _release_attempts(
            "Sarah manages to cut Hinami loose.", [SUBJECT]) == {SUBJECT}

    def test_untying_something_else_near_the_restrained_name(self):
        assert _release_attempts(
            "Sarah unties her apron and hands Hinami the tray.",
            [SUBJECT]) == set()
        assert _release_attempts(
            "Sarah unties the boat from the dock while Hinami watches.",
            [SUBJECT]) == set()

    def test_letting_go_of_an_object_frees_nobody(self):
        assert _release_attempts(
            "Sarah lets go of the ladder and waves to Hinami.",
            [SUBJECT]) == set()

    def test_a_name_past_the_cues_own_loose_is_not_the_thing_released(self):
        assert _release_attempts(
            "Sarah works the cork loose and pours Hinami a glass.",
            [SUBJECT]) == set()

    def test_a_possession_coming_loose_is_not_the_person_coming_free(self):
        assert _release_attempts(
            "Hinami's hair pulls loose from its braid as she struggles.",
            [SUBJECT]) == set()

    def test_the_person_coming_free_still_reads(self):
        assert _release_attempts(
            "Hinami works her wrists free of the straps.",
            [SUBJECT]) == {SUBJECT}
        assert _release_attempts(
            "Hinami is finally untied.", [SUBJECT]) == {SUBJECT}
        assert _release_attempts(
            "Sarah unties the ropes binding Hinami.", [SUBJECT]) == {SUBJECT}
        assert _release_attempts(
            "Sarah sets Hinami free.", [SUBJECT]) == {SUBJECT}

    def test_the_japanese_attempt_is_not_a_completion(self):
        from language_runtime import language_scope

        with language_scope("ja"):
            assert _release_attempts(
                "サラは縄を解こうとしたが、結び目は固かった。",
                ["ヒナミ"]) == set()
            assert _release_attempts(
                "サラはヒナミの縄をほどいた。", ["ヒナミ"]) == {"ヒナミ"}


# --- the vocabulary the body specialist is finally handed --------------------

class TestPublishedVocabulary:
    def test_the_prompt_publishes_the_kind_and_the_ladder(self):
        """The reason every live row is spelled `physical_restraint` or
        `restrained` is that no prompt ever published a kind -- the body
        specialist was handed a parenthetical of examples, and the model
        wrote the consistent name while the reader asked for the
        inconsistent one."""
        from llm.prompts import DEFAULT_PROMPTS

        body = DEFAULT_PROMPTS["director_body"]
        assert "kind:'restraint'" in body
        assert "level ∈ {held|bound|pinned|encased}" in body
        assert "active_restraints" in body

    def test_the_release_cue_exists_in_every_story_pack(self):
        from language_runtime import linguistic

        for lang in ("en", "ja"):
            cue = linguistic("agents.director", "_RELEASE_CUE", lang)
            assert cue.search("sarah uncuffs hinami"), lang
            assert not cue.search("hinami releases a shaky breath"), lang
        ja = linguistic("agents.director", "_RELEASE_CUE", "ja")
        assert ja.search("サラは彼女の縄をほどいた")
        assert ja.search("手錠を外した")
