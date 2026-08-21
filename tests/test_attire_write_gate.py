"""A wardrobe changes only where the beat's words say it does.

Chat 78, nine turns of an interrogation in which nobody touches clothing:
**not one beat's words name a garment**, and the wardrobe was rewritten twice.

* t7 -- `coverage` restating the whole wardrobe as `{region: []}` on a beat
  whose prose is "Hinami winces slightly, then her head lowers". Every garment
  stayed `state: "worn"` and covered nothing, so every region read bare. The
  refusal guard that exists for this shape fired for the other body in the
  scene and not for hers: it asks whether the claim leaves the body covered
  NOWHERE, and her jacket's `waist` survived the block by one region.
* t8 -- `remove` of two garments nobody touched. That set `uncovered` on five
  regions, which is the licence `describe` reads before printing a body's
  `beneath` prose, and the narrator wrote the result onto the page.

Neither is a naming failure: every garment in both blocks is spelled exactly
as the ledger holds it. The gate is therefore not about resolving handles --
`resolve_garment` did that correctly both times -- but about whether the beat
contains the change at all.

The failure direction that matters is the other one. A wardrobe that goes
quiet, or an attire string that loses its garments, is worse than a change
that arrives a beat late, so every test here has its positive control beside
it: the same write, on a beat that names the garment, still lands.
"""

from __future__ import annotations

import time

import pytest

from persist import commit
from story import attire
from core.pipeline_context import ChatData, PipelineContext, TurnData

#: The wardrobe as chat 78 held it before t7, minus the descriptions.
_WORN = ["lightweight travel jacket", "fitted tank top",
         "utility sash with pouches", "travel shorts", "sturdy sandals"]

#: t7's prose, verbatim in shape: a whole beat with no clothing in it.
_QUIET_BEAT = ("Hinami winces slightly, then her head lowers as she stops "
               "supporting herself; her body slumps forward in the restraints, "
               "now held upright solely by the chair's harness.")


def _regions():
    return {
        "torso": {"garments": [
            {"name": "lightweight travel jacket",
             "covers": ["torso", "arms", "waist"]},
            {"name": "fitted tank top"}],
            "beneath": "a scar under the collarbone"},
        "waist": {"garments": [{"name": "utility sash with pouches"}],
                  "beneath": "a paler band of skin"},
        "groin": {"garments": [{"name": "travel shorts",
                                "covers": ["groin", "legs"]}],
                  "beneath": "PRIVATE BODY PROSE"},
        "feet": {"garments": [{"name": "sturdy sandals"}],
                 "beneath": "calloused heels"},
    }


def _ctx(temp_db, player_input="", resolved=""):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Gate", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Gate", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)
    ctx.director_interpret = {}
    ctx.director_resolve = {"resolved_event": resolved}
    return ctx


def _scene():
    return {"positions": {"Hinami": "cell"},
            "attire": {"Hinami": attire.authored_entry(
                list(_WORN), [], _regions())}}


def _apply(temp_db, diff, *, player_input="", resolved=""):
    sc = _scene()
    ctx = _ctx(temp_db, player_input, resolved)
    commit.apply_attire_diff(sc, {"attire": {"Hinami": diff}}, ctx,
                             ctx.director_resolve)
    return sc["attire"]["Hinami"], ctx


class TestTheQuietBeatChangesNothing:
    """t7 and t8, refused."""

    def test_a_coverage_block_on_a_beat_with_no_clothing_in_it_is_dropped(
            self, temp_db):
        entry, ctx = _apply(temp_db, {"coverage": {
            "lightweight travel jacket": {"torso": [], "arms": []},
            "fitted tank top": {"torso": [], "arms": []},
            "utility sash with pouches": {"waist": []},
            "travel shorts": {"groin": [], "legs": []},
            "sturdy sandals": {"feet": []},
        }}, resolved=_QUIET_BEAT)

        # Every garment still covers what it covered. Not "still worn" --
        # they were still `worn` in the live defect too, and covered nothing.
        assert attire.exposed_regions(entry["regions"]) == []
        assert not [n for n in attire.flat_state(entry["regions"])
                    if "displaced" in n or n.startswith("bare at")]
        assert any("no word of this beat names the garment" in w
                   for w in ctx.warnings)

    def test_a_removal_on_a_beat_with_no_clothing_in_it_is_dropped(
            self, temp_db):
        entry, ctx = _apply(temp_db, {"remove": [
            "lightweight travel jacket", "lightweight travel jacket",
            "travel shorts", "travel shorts"]}, resolved=_QUIET_BEAT)

        assert entry["wearing"] == _WORN
        assert not any(r.get("uncovered")
                       for r in entry["regions"].values())

    def test_the_string_is_not_scrubbed_by_the_gate(self, temp_db):
        """THE FAILURE DIRECTION THIS GATE MUST NOT HAVE.

        Refusing a change must leave the wardrobe exactly as legible as it
        was. A body whose garments stop being rendered is a worse defect than
        the one being fixed -- every mind in the scene reads this string.
        """
        entry, _ = _apply(temp_db, {"coverage": {
            "fitted tank top": {"torso": [], "arms": []}}},
            resolved=_QUIET_BEAT)

        line = attire.compact_line(entry["regions"], beneath_visible=True)
        for garment in ("travel jacket", "tank top", "sash", "sandals"):
            assert garment in line
        assert "PRIVATE BODY PROSE" not in line
        assert "bare" not in attire.describe(
            entry["regions"], beneath_visible=True)[0]


class TestANamedChangeStillLands:
    """The control. Every refusal above, with the beat saying it happened."""

    def test_a_named_removal_lands(self, temp_db):
        entry, ctx = _apply(
            temp_db, {"remove": ["lightweight travel jacket"]},
            resolved="She shrugs the travel jacket off and lets it fall.")

        assert "lightweight travel jacket" not in entry["wearing"]
        assert not any("names the garment" in w for w in ctx.warnings)

    def test_a_removal_named_by_the_player_alone_lands(self, temp_db):
        """The player's own input is licence: they are the same authority the
        Director is, scoped to their own conduct."""
        entry, _ = _apply(
            temp_db, {"remove": ["sturdy sandals"]},
            player_input="I kick the sandals off and stretch my toes.")

        assert "sturdy sandals" not in entry["wearing"]

    def test_a_named_displacement_lands(self, temp_db):
        entry, _ = _apply(
            temp_db, {"coverage": {"travel shorts": {"groin": [], "legs": []}}},
            resolved="She works the travel shorts down around her ankles.")

        assert "travel shorts" in entry["wearing"]
        assert "groin" in attire.exposed_regions(entry["regions"])

    def test_a_short_handle_is_licensed_by_the_ledger_spelling(self, temp_db):
        """The diff writes a handle, the prose uses its own words, and the
        ledger holds a third spelling. All three are the same garment."""
        entry, _ = _apply(
            temp_db, {"remove": ["tank top"]},
            resolved="The top comes free over her head.")

        assert "fitted tank top" not in entry["wearing"]


class TestUncoveredMeansUncovered:
    def test_shedding_an_outer_layer_does_not_bare_the_region_beneath(
            self, temp_db):
        """The jacket comes off over a tank top that is still on.

        `uncovered` is the flag `describe` reads before printing a body's
        `beneath`, and any departure at all used to set it. Torso keeps the
        tank top, so nothing about that region was uncovered; arms and waist,
        which the jacket alone covered, were.
        """
        entry, _ = _apply(
            temp_db, {"remove": ["lightweight travel jacket"]},
            resolved="She shrugs the travel jacket off her shoulders.")

        regions = entry["regions"]
        # Kept a covering -> not uncovered, and their `beneath` stays sealed.
        assert not regions["torso"].get("uncovered")
        assert not regions["waist"].get("uncovered")
        # The arms had only the jacket, so they genuinely were uncovered.
        assert regions["arms"].get("uncovered") is True
        assert attire.exposed_regions(regions) == ["arms"]
        line = attire.compact_line(regions, beneath_visible=True)
        assert "scar under the collarbone" not in line
        assert "paler band of skin" not in line
        assert "tank top" in line

    def test_shedding_the_last_covering_does_bare_the_region(self, temp_db):
        entry, _ = _apply(
            temp_db, {"remove": ["travel shorts"]},
            resolved="She steps out of the travel shorts.")

        assert entry["regions"]["groin"].get("uncovered") is True
        assert "PRIVATE BODY PROSE" in attire.compact_line(
            entry["regions"], beneath_visible=True)
