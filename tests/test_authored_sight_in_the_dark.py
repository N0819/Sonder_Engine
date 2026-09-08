"""Darkness is a property of the place; who it blinds is a property of the
perceiver (review 2026-09-07 A87, owner ruling 2026-09-08).

Reproduced at head before the change, in-process: `sight_level({'same_room':
True, 'light': 'dark'})` and `sight_level({'barrier': 'wall'})` both answered
the same word `none`, so nothing downstream could tell a dark room from a
wall; `sense_adjusted('none', 'sight', [{'channel': 'vision', 'acuity':
'extraordinary', 'notes': 'sees in total darkness'}])` answered `none`,
because the one direction that adds refused to leave `none` on sight at all;
and `_sense_channel('echolocation')` answered None, so an authored non-human
sense had no acuity offset on any engine channel. A card that authored night
vision or echolocation was deterministically blind.

What holds now: a sense entry may say it does not need light (`needs_light`)
and may name the engine channel it delivers on (`equivalent`); one derivation
(`_sight_verdict`, read as `sight_level`, `sight_block` and `sight_verdict`)
carries the grade and what the PLACE did to it; a `none` the light caused
lifts for a perceiver whose sight does not need light, the glare cap is not
spent against one, and what a BODY or a BOUNDARY did never lifts. Hearing,
touch and smell were never gated by light and are not touched.
"""

from __future__ import annotations

import pytest

from tests.test_light_field import glare_scene
from world import spatial
from world.scene_memo import scene_read_pass
from world.spatial import glare_between


ORDINARY = [
    {"channel": "vision", "acuity": "ordinary", "range": "ordinary",
     "needs_light": True, "equivalent": "", "notes": ""},
    {"channel": "hearing", "acuity": "ordinary", "range": "ordinary",
     "needs_light": True, "equivalent": "", "notes": ""},
]
#: Sight that does not need light, authored the two ways the design allows:
#: on the vision channel itself, and on a channel the engine does not model
#: which says which engine channel it DELIVERS on.
NIGHT_EYES = [
    {"channel": "vision", "acuity": "ordinary", "range": "ordinary",
     "needs_light": False, "equivalent": "",
     "notes": "sees the shape of a room with no light in it at all"},
]
ECHOLOCATION = [
    {"channel": "echolocation", "acuity": "ordinary", "range": "ordinary",
     "needs_light": False, "equivalent": "sight",
     "notes": "reads the room back off its own returning sound"},
]
LIGHTLESS = (NIGHT_EYES, ECHOLOCATION)


def _dark_room():
    """Two bodies in one unlit room."""
    return {
        "rooms": {"cellar": {"name": "The Cellar", "desc": "Stone.",
                             "light": "dark", "adjacent": []}},
        "positions": {"Obs": "cellar", "Subj": "cellar"},
    }


def _dark_rooms_through_a_wall():
    return {
        "rooms": {
            "cellar": {"name": "The Cellar", "light": "dark",
                       "adjacent": [{"room": "vault", "barrier": "wall"}]},
            "vault": {"name": "The Vault", "light": "dark",
                      "adjacent": [{"room": "cellar", "barrier": "wall"}]},
        },
        "positions": {"Obs": "cellar", "Subj": "vault"},
    }


def _dark_room_sealed_container():
    sc = _dark_room()
    sc["positions"]["Crate"] = "cellar"
    sc["contained"] = {"Subj": {"in": "Crate", "mode": "container"}}
    return sc


# ---------------------------------------------------------------------------
# The fact that was being thrown away
# ---------------------------------------------------------------------------

class TestTheNoneNowSaysWhichNoneItWas:
    @pytest.mark.parametrize("rel,expected", [
        ({"same_room": True, "light": "dark"}, "dark"),
        ({"barrier": "wall"}, "barrier"),
        ({"same_room": True, "concealed": True}, "concealed"),
        ({"same_room": True, "light": "lit"}, ""),
        ({"same_room": True, "light": "dim"}, ""),
        ({"same_room": True, "light": "lit", "glare": True}, "glare"),
    ])
    def test_the_cause_is_carried_out_of_the_same_derivation(self, rel,
                                                             expected):
        assert spatial.sight_block(rel) == expected

    def test_the_level_and_the_cause_cannot_disagree(self):
        """One derivation, three readers: every `none` names which refusal it
        was, and the only cause a level above `none` carries is `glare` --
        the cap that is reported unapplied so the perceiver can decide
        whether the light that would dazzle it feeds it at all."""
        for light in ("dark", "dim", "lit", "bright"):
            for barrier in ("", "wall", "door", "curtain", "window"):
                for concealed in (False, True):
                    for crossing in (False, True):
                        for glare in (False, True):
                            rel = {"light": light, "barrier": barrier,
                                   "concealed": concealed,
                                   "crossing": crossing, "glare": glare}
                            if not barrier:
                                rel["same_room"] = True
                            level, block = spatial.sight_verdict(rel)
                            assert block == spatial.sight_block(rel)
                            assert spatial.sight_level(rel) == (
                                "shapes" if block == "glare" else level)
                            assert (level == "none") == (
                                block in ("dark", "barrier", "concealed")), (
                                    rel, level, block)


# ---------------------------------------------------------------------------
# What lifts, and what does not
# ---------------------------------------------------------------------------

class TestAPlaceCausedNoneLifts:
    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_the_dark_room_is_seen(self, senses):
        sc = _dark_room()
        assert spatial.visual_level_between(sc, "Obs", "Subj") == "none"
        assert spatial.visual_level_between(sc, "Obs", "Subj", senses) == "full"

    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_the_room_level_grade_lifts_only_with_the_cause(self, senses):
        rel = {"same_room": True, "light": "dark"}
        level = spatial.sight_level(rel)
        assert spatial.sense_adjusted(level, "sight", senses) == "none"
        assert spatial.sense_adjusted(
            level, "sight", senses,
            blocked_by=spatial.sight_block(rel)) == "full"

    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_acuity_still_applies_on_top_of_the_lift(self, senses):
        dulled = [dict(entry, acuity="dulled") for entry in senses]
        rel = {"same_room": True, "light": "dark"}
        assert spatial.sense_adjusted(
            "none", "sight", dulled, blocked_by="dark") == "conduct"
        assert spatial.sight_block(rel) == "dark"


class TestABodyOrBoundaryCausedNoneNeverLifts:
    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_a_wall_is_still_a_wall(self, senses):
        sc = _dark_rooms_through_a_wall()
        assert spatial.visual_level_between(sc, "Obs", "Subj") == "none"
        assert spatial.visual_level_between(sc, "Obs", "Subj", senses) == "none"
        assert spatial.sense_adjusted(
            "none", "sight", senses, blocked_by="barrier") == "none"

    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_a_shut_container_is_still_shut(self, senses):
        sc = _dark_room_sealed_container()
        assert spatial.visual_level_between(sc, "Obs", "Subj") == "none"
        assert spatial.visual_level_between(sc, "Obs", "Subj", senses) == "none"
        assert spatial.sense_adjusted(
            "none", "sight", senses, blocked_by="concealed") == "none"

    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_a_crossing_still_caps_at_shapes(self, senses):
        """A body going through an opaque boundary is a shape in the doorway
        for both kinds of eye: the crossing grace is a floor, never a lift."""
        rel = {"barrier": "curtain", "crossing": True, "light": "dark"}
        level = spatial.sight_level(rel)
        assert level == "shapes"
        assert spatial.sense_adjusted(
            level, "sight", senses,
            blocked_by=spatial.sight_block(rel)) == "shapes"

    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_an_authored_blind_body_is_blind_in_the_dark_too(self, senses):
        """`absent` is a full cut, and it is applied after the lift."""
        blind = [dict(entry, acuity="absent") for entry in senses]
        assert spatial.sense_adjusted(
            "none", "sight", blind, blocked_by="dark") == "none"
        assert spatial.sense_adjusted("full", "sight", blind) == "none"


class TestGlareDoesNotDazzleASightTheLightDoesNotFeed:
    """A light in the eyes caps sight at `shapes`; a light that does not feed
    the sense cannot do that (A87/R1).

    Measured on `tests/test_light_field.glare_scene()` -- P at the table
    facing Q, who stands beside P holding a lit lamp -- where
    `glare_between(sc, 'P', 'Q')` is True and `rel['glare']` is True. Before
    the fix the two carriers of that rule disagreed about the same perceiver:
    the per-body one answered `full` (it skips the cap for a lightless sight)
    while the room-level one answered `shapes`, because `sight_level` folded
    the cap into the word and reported no cause. Now `sight_verdict` hands
    back the grade the light allowed plus the cap still owed, and
    `sense_adjusted` is the one reader that spends it.
    """

    def test_the_scene_really_glares(self):
        sc = glare_scene()
        assert glare_between(sc, "P", "Q") is True
        rel = spatial.spatial_rel_between(sc, "P", "Q")
        assert rel.get("glare") is True

    def test_an_ordinary_eye_is_still_dazzled_on_both_carriers(self):
        sc = glare_scene()
        rel = spatial.spatial_rel_between(sc, "P", "Q")
        assert spatial.sight_level(rel) == "shapes"
        for senses in (None, [], ORDINARY):
            level, block = spatial.sight_verdict(rel)
            assert spatial.sense_adjusted(
                level, "sight", senses, blocked_by=block) == "shapes"
            assert spatial.visual_level_between(sc, "P", "Q", senses) \
                == "shapes"

    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_both_carriers_drop_the_cap_for_the_same_perceiver(self, senses):
        """The two answers that used to disagree, in a lit room where the
        room grade and the target's cell agree: `full` on both."""
        sc = glare_scene()
        rel = spatial.spatial_rel_between(sc, "P", "Q")
        level, block = spatial.sight_verdict(rel)
        assert block == "glare"
        room_level = spatial.sense_adjusted(
            level, "sight", senses, blocked_by=block)
        assert room_level == "full"
        assert spatial.visual_level_between(sc, "P", "Q", senses) == "full"

    @pytest.mark.parametrize("senses", LIGHTLESS)
    def test_the_cap_comes_off_without_the_light_being_credited(self, senses):
        """Dropping the cap gives back what the LIGHT allowed, never more: in
        an unlit room whose only source is the lamp in the observer's eyes the
        room grades `dim`, so the room-level answer is `conduct` -- glare must
        not become a way of seeing better than the place allows. (The per-body
        carrier answers `full` here for a reason that predates glare: it reads
        the light at the target's own cell, and Q is holding the lamp.)
        """
        sc = glare_scene()
        sc["rooms"]["r"]["light"] = "dark"
        rel = spatial.spatial_rel_between(sc, "P", "Q")
        level, block = spatial.sight_verdict(rel)
        assert (level, block) == ("conduct", "glare")
        assert spatial.sight_level(rel) == "shapes"
        assert spatial.sense_adjusted(
            level, "sight", senses, blocked_by=block) == "conduct"

    def test_a_glare_block_never_lifts_a_wall_or_a_shut_container(self):
        """`glare` is reported only where there is a line and light: what a
        BODY or a BOUNDARY did keeps its own cause and never lifts."""
        for rel in ({"barrier": "wall", "light": "lit", "glare": True},
                    {"same_room": True, "concealed": True, "light": "lit",
                     "glare": True}):
            level, block = spatial.sight_verdict(rel)
            assert level == "none" and block in ("barrier", "concealed")
            for senses in LIGHTLESS:
                assert spatial.sense_adjusted(
                    level, "sight", senses, blocked_by=block) == "none"


# ---------------------------------------------------------------------------
# An invented sense costs nothing, and delivers only where it says it does
# ---------------------------------------------------------------------------

class TestEquivalentIsWhatMakesAnInventedSenseDeliver:
    def test_an_unknown_channel_alone_is_still_no_channel(self):
        """`_sense_channel` must go on answering None for a word the engine
        does not model -- inventing a sense must cost nothing."""
        assert spatial._sense_channel("echolocation") is None
        bare = [{"channel": "echolocation", "acuity": "extraordinary",
                 "range": "ordinary", "notes": ""}]
        assert spatial.sense_entry(bare, "sight") is None
        assert spatial.sense_acuity_offset(bare, "sight") == 0

    def test_an_equivalent_names_the_channel_it_arrives_on(self):
        assert spatial.sense_entry(ECHOLOCATION, "sight") is ECHOLOCATION[0]
        assert spatial.sense_entry(ECHOLOCATION, "hearing") is None

    def test_a_directly_named_channel_wins_over_an_equivalent_one(self):
        both = ECHOLOCATION + NIGHT_EYES
        assert spatial.sense_entry(both, "sight") is NIGHT_EYES[0]

    def test_the_two_spellings_answer_identically_everywhere(self):
        for scene in (_dark_room(), _dark_rooms_through_a_wall(),
                      _dark_room_sealed_container()):
            assert spatial.visual_level_between(
                scene, "Obs", "Subj", NIGHT_EYES) == \
                spatial.visual_level_between(scene, "Obs", "Subj",
                                             ECHOLOCATION)


# ---------------------------------------------------------------------------
# An ordinary card answers exactly as it did
# ---------------------------------------------------------------------------

class TestAnOrdinaryCardIsUnchanged:
    @pytest.mark.parametrize("senses", [None, [], ORDINARY])
    def test_every_sight_site_answers_as_before(self, senses):
        for scene in (_dark_room(), _dark_rooms_through_a_wall(),
                      _dark_room_sealed_container()):
            bare = spatial.visual_level_between(scene, "Obs", "Subj")
            assert spatial.visual_level_between(
                scene, "Obs", "Subj", senses) == bare

    @pytest.mark.parametrize("senses", [None, [], ORDINARY])
    def test_the_gate_answers_as_before_whatever_the_cause(self, senses):
        for level in spatial.SIGHT_LEVELS:
            for block in ("", "dark", "barrier", "concealed"):
                assert spatial.sense_adjusted(
                    level, "sight", senses, blocked_by=block) == \
                    spatial.sense_adjusted(level, "sight", senses)

    @pytest.mark.parametrize("senses", [None, [], ORDINARY])
    def test_an_eye_the_light_feeds_pays_the_glare_cap_here(self, senses):
        """`glare` is the one cause reported unapplied, so this reader is
        where an ordinary eye pays it -- and it pays exactly what
        `sight_level` charges a caller that never asked about a perceiver."""
        for level in spatial.SIGHT_LEVELS:
            capped = spatial.sense_adjusted(
                level, "sight", senses, blocked_by="glare")
            assert capped == ("shapes" if level in ("conduct", "full")
                              else level)

    def test_an_absent_or_malformed_field_reads_as_ordinary_eyes(self):
        """The safe direction for a field a generator might write as a word:
        a shape nobody meant to write is ordinary eyes, never night vision
        nobody authored. `authored_bool` still reads the words a human writes
        for false."""
        assert spatial.sense_needs_light(None) is True
        assert spatial.sense_needs_light(ORDINARY) is True
        assert spatial.sense_needs_light(
            [{"channel": "vision", "needs_light": "yes"}]) is True
        assert spatial.sense_needs_light(
            [{"channel": "vision", "needs_light": {}}]) is True
        assert spatial.sense_needs_light(
            [{"channel": "vision", "needs_light": "false"}]) is False
        assert spatial.sense_needs_light(NIGHT_EYES) is False

    def test_the_other_channels_are_not_touched(self):
        """Hearing, touch and smell were never gated by light; `blocked_by`
        reaches sight and nothing else."""
        for channel in ("hearing", "scent"):
            for block in ("", "dark", "barrier", "concealed", "glare"):
                assert spatial.sense_adjusted(
                    "none", channel, NIGHT_EYES, blocked_by=block) == "none"
                assert spatial.sense_adjusted(
                    "full", channel, NIGHT_EYES, blocked_by=block) == "full"


# ---------------------------------------------------------------------------
# The two chokepoints, and the memo underneath them
# ---------------------------------------------------------------------------

class TestTheDeliveryChokepoints:
    def test_the_micro_round_gate_delivers_in_the_dark(self):
        from agents.common import _delivery_ok

        sc = _dark_room()
        rel = spatial.spatial_rel(sc, "cellar", "cellar")
        assert _delivery_ok(rel, sc, "Obs", "Subj", "sight",
                            senses=ORDINARY) is False
        for senses in LIGHTLESS:
            assert _delivery_ok(rel, sc, "Obs", "Subj", "sight",
                                senses=senses) is True

    def test_the_micro_round_gate_still_refuses_a_wall(self):
        from agents.common import _delivery_ok

        sc = _dark_rooms_through_a_wall()
        rel = spatial.spatial_rel(sc, "cellar", "vault")
        for senses in LIGHTLESS:
            assert _delivery_ok(rel, sc, "Obs", "Subj", "sight",
                                senses=senses) is False

    def test_the_composed_view_admits_the_body(self):
        """`composer.presence_percepts` is the other chokepoint: it grades
        with `_sense_graded` over `visual_level_between`, so the senses must
        reach the carrier or the body never arrives."""
        from agents import composer

        sc = _dark_room()
        bodies = [{"name": "Subj", "appearance": "a tall woman",
                   "aliases": [], "role": ""}]
        assert composer.presence_percepts(
            sc, "Obs", bodies, {"Subj": "Subj"}, ORDINARY) == []
        for senses in LIGHTLESS:
            seen = composer.presence_percepts(
                sc, "Obs", bodies, {"Subj": "Subj"}, senses)
            assert [p.source_label for p in seen] == ["Subj"]


class TestEveryGateAsksTheSameQuestion:
    """The class, not the site (A87 rework): the composed view and the six
    gates that decide whether a demeanor, a tell, a visual channel or a sweep
    reaches an observer must answer the same thing about the same pair.

    Each of those gates asked `has_visual(rel)` and graded a bare `"full"`
    with no perceiver, which is card-blind -- so an authored sight that does
    not need light was graded `none` by the gate and `full` by the view on
    the same beat, and the feature worked at half its sites. They now share
    one composition, `perception._sight_reaches`.
    """

    def test_a_lightless_sight_is_admitted_by_every_gate_in_the_dark(self):
        from agents import composer, perception

        sc = _dark_room()
        rel = spatial.spatial_rel(sc, "cellar", "cellar")
        for senses in LIGHTLESS:
            view = composer._sense_graded(
                spatial.visual_level_between(sc, "Obs", "Subj", senses),
                "sight", senses)
            assert view != "none", senses
            # The gate agrees with the view, both with and without a
            # relation in hand -- the two shapes the six sites use.
            assert perception._sight_reaches(sc, "Obs", "Subj", senses) is True
            assert perception._sight_reaches(
                sc, "Obs", "Subj", senses, rel=rel) is True

    def test_an_ordinary_card_is_still_refused_by_every_gate(self):
        from agents import perception

        sc = _dark_room()
        rel = spatial.spatial_rel(sc, "cellar", "cellar")
        assert perception._sight_reaches(sc, "Obs", "Subj", ORDINARY) is False
        assert perception._sight_reaches(
            sc, "Obs", "Subj", ORDINARY, rel=rel) is False

    def test_a_wall_still_refuses_a_lightless_sight_at_the_gate(self):
        """What a BOUNDARY did never lifts, at the gate as at the view."""
        from agents import perception

        sc = _dark_rooms_through_a_wall()
        rel = spatial.spatial_rel(sc, "cellar", "vault")
        for senses in LIGHTLESS:
            assert perception._sight_reaches(
                sc, "Obs", "Subj", senses, rel=rel) is False


class TestTheMemoKeepsThePerceiversApart:
    def test_two_observers_of_one_pair_do_not_share_an_answer(self):
        """FIREWALL/correctness: the memo key names both bodies AND whether
        this observer's sight needs light, so an ordinary reader cannot be
        handed a lightless one's answer inside a read pass."""
        sc = _dark_room()
        with scene_read_pass(sc):
            assert spatial.visual_level_between(sc, "Obs", "Subj") == "none"
            assert spatial.visual_level_between(
                sc, "Obs", "Subj", NIGHT_EYES) == "full"
            assert spatial.visual_level_between(sc, "Obs", "Subj") == "none"
            assert spatial.visual_level_between(
                sc, "Obs", "Subj", ORDINARY) == "none"


# ---------------------------------------------------------------------------
# The card carries the fields
# ---------------------------------------------------------------------------

class TestTheCardSchema:
    def test_the_default_templates_carry_both_fields(self):
        from story.character_schema import (default_character_data,
                                            default_persona_data)

        for sheet in (default_character_data("Someone"),
                      default_persona_data("Someone")):
            senses = sheet["embodiment"]["senses"]
            assert senses
            for entry in senses:
                assert entry["needs_light"] is True
                assert entry["equivalent"] == ""

    def test_an_authored_night_sense_survives_normalization(self):
        from story.character_schema import (character_senses,
                                            default_character_data)

        sheet = default_character_data("Someone")
        sheet["embodiment"]["senses"] = list(ECHOLOCATION)
        senses = character_senses(sheet)
        assert senses[0]["equivalent"] == "sight"
        assert senses[0]["needs_light"] is False
        assert spatial.sense_needs_light(senses) is False

    def test_a_sheet_written_before_the_fields_existed_is_ordinary(self):
        from story.character_schema import (character_senses,
                                            normalize_character_data)

        legacy = normalize_character_data(
            {"identity": {"name": "Old"},
             "embodiment": {"senses": "ordinary human senses"}})
        assert spatial.sense_needs_light(character_senses(legacy)) is True
