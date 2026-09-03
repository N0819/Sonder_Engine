"""A Charter body has a surface: what a stranger sees of it, dealt from its
population's look law and graded by the light it is seen in.

Measured on the Harrowmere replay (2026-09-03): a hundred townspeople with
no appearance text, every unrecognised one rendered "the unfamiliar person"
or "an indistinct figure". Against the replay's own registry, every one of
the 27 bodies the player met now carries a descriptor at the light they
were met in (18 silhouettes at dim, 13 faces at lit; 0 fallbacks).
"""
from __future__ import annotations

import copy
import json
import os
import time

import pytest

from agents import composer
from agents.common import _unknown_actor_label, present_charter_figures
from world import charter_surface as cs
from world.charter_generate import close_plan
from world.charter_model import normalize_charter
from world.charter_runtime import (background_presence_records, presence_view,
                                   save_registry, settle_rendered_surfaces)

_HERE = os.path.dirname(os.path.abspath(__file__))

LAW = {
    "stature": ["towering", "squat"],
    "build": ["barrel-chested", "reedy"],
    "gait": ["rolling", "mincing"],
    "complexion": ["ash-pale", "copper-dark"],
    "hair": ["a tarred queue", "a cropped fringe"],
    "age": ["greybeard", "green"],
    "marks": ["a rope burn across the palm"],
}
POST = {"place": "forge", "serves": [], "requires": {},
        "worn": ["a scorched leather apron"], "marks": ["soot in the creases"]}


def _charter(*, looks=LAW, with_post=True, body_name="Reeve Bram Fenwick"):
    return normalize_charter({
        "key": "hall",
        "looks": looks,
        "posts": {"reeve": dict(POST, place="hall")} if with_post else {},
        "bodies": {"reeve:0001": {"name": body_name, "home_post": "reeve",
                                  "place": "hall", "berth": "cottage"}},
        "watch": {"reeve": "reeve:0001"} if with_post else {},
    })


# ---------------------------------------------------------------- dealing

class TestTheLawIsDealtLikeNames:

    def test_one_value_per_axis_from_the_seed_and_nothing_else(self):
        a = cs.deal_surface("hall", "reeve:0001", LAW, post=POST)
        b = cs.deal_surface("hall", "reeve:0001", LAW, post=POST)
        assert a == b
        for axis in cs.AXES:
            assert a[axis] in LAW[axis]
        assert a["law"] == "authored"

    def test_two_bodies_deal_from_the_same_pools_independently(self):
        surfaces = {key: cs.deal_surface("hall", key, LAW)
                    for key in (f"b:{i:04d}" for i in range(40))}
        # forty bodies over two-value pools: both values of every axis land
        for axis in cs.AXES:
            assert {s[axis] for s in surfaces.values()} == set(LAW[axis])

    def test_the_post_dresses_and_marks_its_holders(self):
        s = cs.deal_surface("hall", "reeve:0001", LAW, post=POST)
        assert s["worn"] == ["a scorched leather apron"]
        assert "soot in the creases" in s["marks"]

    def test_a_law_mark_lands_on_one_body_in_mark_odds(self):
        marked = sum(
            1 for i in range(300)
            if "a rope burn across the palm"
            in cs.deal_surface("hall", f"b:{i}", LAW)["marks"])
        assert 300 // cs.MARK_ODDS * 0.6 < marked < 300 // cs.MARK_ODDS * 1.4

    def test_no_law_deals_the_engine_default_and_says_so(self):
        charter = _charter(looks={})
        s = cs.surface_of(charter, "reeve:0001")
        assert s["law"] == "default"
        assert s["stature"] in cs.default_looks()["stature"]

    def test_a_stored_surface_outranks_a_dealt_one(self):
        charter = _charter()
        charter["bodies"]["reeve:0001"]["surface"] = {
            "stature": "hunched", "build": "", "gait": "", "complexion": "",
            "hair": "", "age": "", "marks": [], "worn": [], "law": "authored"}
        assert cs.surface_of(charter, "reeve:0001")["stature"] == "hunched"

    def test_normalize_keeps_looks_and_dress_and_leaves_legacy_bytes(self):
        charter = _charter()
        assert charter["looks"]["stature"] == LAW["stature"]
        assert charter["posts"]["reeve"]["worn"] == POST["worn"]
        # a body from before the field existed stores no surface
        assert "surface" not in charter["bodies"]["reeve:0001"]


# ------------------------------------------------------------- the label

class TestTheDescriptorIsBuiltFromTheSurfaceAlone:

    def _surface(self):
        return cs.deal_surface("hall", "reeve:0001", LAW, post=POST)

    def test_full_sight_composes_the_face_tier(self):
        label = _unknown_actor_label("Reeve Bram Fenwick", surface=self._surface())
        s = self._surface()
        assert label.startswith("the ")
        assert s["age"] in label and s["build"] in label
        assert "soot in the creases" in label or "rope burn" in label

    def test_short_of_full_composes_the_silhouette_tier_only(self):
        s = self._surface()
        label = _unknown_actor_label("Reeve Bram Fenwick", surface=s,
                                     sight="shapes")
        assert s["stature"] in label and s["build"] in label
        assert "figure" in label and "apron" in label
        for face in (s["complexion"], s["hair"], s["age"], "soot"):
            assert face not in label, (face, label)

    def test_no_channel_is_no_phrase(self):
        assert cs.surface_label(self._surface(), "none") == ""
        assert _unknown_actor_label("X", surface=self._surface(),
                                    sight="none") == "the unfamiliar person"

    @pytest.mark.parametrize("sight", ["full", "shapes"])
    def test_adversarial_the_name_never_enters_the_label(self, sight):
        s = self._surface()
        label = _unknown_actor_label("Reeve Bram Fenwick", "Reeve Bram Fenwick",
                                     ["Bram", "Fenwick"], surface=s,
                                     sight=sight).casefold()
        for token in ("reeve", "bram", "fenwick"):
            assert token not in label, (token, label)

    @pytest.mark.parametrize("sight", ["full", "shapes"])
    def test_adversarial_the_post_key_never_enters_the_label(self, sight):
        # a surface smuggling name-shaped keys is read on its axes alone
        s = dict(self._surface(), name="Reeve Bram Fenwick", post="reeve",
                 role="the reeve", key="reeve:0001")
        label = _unknown_actor_label("Reeve Bram Fenwick", surface=s,
                                     sight=sight).casefold()
        assert "reeve" not in label

    def test_the_public_noun_the_crowd_renders_is_the_noun_at_full_sight(self):
        # the crowd's rule, not a new one: a rank or duty is worn, and the
        # one deckhand standing out of the band reads as a deckhand
        s = self._surface()
        label = _unknown_actor_label("X", surface=s, role="deckhand")
        assert label.endswith(f"deckhand with {s['marks'][0]}") \
            or "deckhand" in label
        assert "deckhand" not in _unknown_actor_label(
            "X", surface=s, role="deckhand", sight="shapes")

    def test_the_summary_carries_every_tier_for_first_mention(self):
        s = self._surface()
        text = cs.appearance_text(s)
        for part in (s["age"], s["stature"], s["build"], s["complexion"],
                     s["hair"], "apron"):
            assert part in text

    def test_words_widen_from_the_surface(self):
        s = self._surface()
        assert cs.surface_words(s, "shapes")[:2] == [s["stature"], s["build"]]
        assert s["hair"].split()[-1] in cs.surface_words(s, "full")


# ---------------------------------------------------------- the composer

def _scene(light="dim"):
    return {
        "rooms": {"r": {"name": "The Hall", "light": light, "adjacent": []}},
        "positions": {"OBS": "r", "A": "r", "B": "r"},
        "stations": {"OBS": {"at": "s1", "near": []},
                     "A": {"at": "s2", "near": []},
                     "B": {"at": "s2", "near": []}},
        "poses": {}, "contacts": {}, "contained": {},
    }


class TestDimLightYieldsASilhouetteNotNothing:

    def test_a_charter_body_at_dim_is_a_silhouette_of_its_own_surface(self):
        s = cs.deal_surface("hall", "a", LAW, post=POST)
        bodies = [{"name": "A", "appearance": "", "aliases": [], "surface": s}]
        display = composer.observer_display_map(_scene("dim"), "OBS", bodies,
                                                {"OBS": []})
        assert display["A"] != composer.DIM_FIGURE
        assert s["stature"] in display["A"] and "apron" in display["A"]
        assert s["age"] not in display["A"]
        percept = composer.presence_percepts(_scene("dim"), "OBS", bodies,
                                             display)[0]
        assert percept.source_label == display["A"]
        assert percept.fidelity == "degraded"

    def test_two_silhouettes_that_read_the_same_still_collide(self):
        s = cs.deal_surface("hall", "a", LAW, post=POST)
        bodies = [{"name": "A", "appearance": "", "aliases": [], "surface": s},
                  {"name": "B", "appearance": "", "aliases": [],
                   "surface": dict(s)}]
        display = composer.observer_display_map(_scene("dim"), "OBS", bodies,
                                                {"OBS": []})
        assert display["A"] == display["B"] == composer.DIM_FIGURE

    def test_a_summary_only_body_at_dim_stays_the_fixed_label(self):
        bodies = [{"name": "A", "appearance": "A lean man in a wet coat.",
                   "aliases": []}]
        display = composer.observer_display_map(_scene("dim"), "OBS", bodies,
                                                {"OBS": []})
        assert display["A"] == composer.DIM_FIGURE

    def test_full_light_yields_the_face_tier(self):
        s = cs.deal_surface("hall", "a", LAW, post=POST)
        bodies = [{"name": "A", "appearance": "", "aliases": [], "surface": s}]
        display = composer.observer_display_map(_scene("lit"), "OBS", bodies,
                                                {"OBS": []})
        assert s["age"] in display["A"] and "person" in display["A"]

    def test_dark_is_no_channel(self):
        s = cs.deal_surface("hall", "a", LAW, post=POST)
        bodies = [{"name": "A", "appearance": "", "aliases": [], "surface": s}]
        display = composer.observer_display_map(_scene("dark"), "OBS", bodies,
                                                {"OBS": []})
        assert display["A"] == "the unfamiliar person"

    def test_two_faces_that_collide_widen_through_the_surface(self):
        s = cs.deal_surface("hall", "a", LAW, post=POST)
        other = dict(s, hair=next(h for h in LAW["hair"] if h != s["hair"]),
                     marks=[], worn=[])
        bodies = [{"name": "A", "appearance": "", "aliases": [], "surface": s},
                  {"name": "B", "appearance": "", "aliases": [],
                   "surface": other}]
        display = composer.observer_display_map(_scene("lit"), "OBS", bodies,
                                                {"OBS": []})
        assert display["A"] != display["B"]


# ------------------------------------------------- the registry's readers

def _chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name, scenario, created) VALUES (?, ?, ?)",
        ("surface", "", time.time()))


class TestEveryReaderDescribesTheSamePerson:

    def test_the_sketch_carries_the_surface_and_its_summary(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"hall": _charter()})
        records = background_presence_records(cid, places={"hall"})
        record = next(iter(records.values()))
        sketch = record["sketch"]
        assert sketch["surface"]["law"] == "authored"
        assert sketch["surface"]["worn"] == POST["worn"]
        # the noun is the crowd's public noun for the post, never its key
        assert sketch["appearance"] == cs.appearance_text(
            sketch["surface"], noun="reeve")
        assert "reeve:0001" not in sketch["appearance"]

    def test_the_director_sees_the_look(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"hall": _charter()})
        rows = present_charter_figures(cid, {}, {"hall"})
        assert rows and rows[0]["look"]
        assert "apron" in rows[0]["look"]

    def test_the_voice_knows_its_own_look(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"hall": _charter()})
        rows = presence_view(cid, "hall", "Reeve Bram Fenwick")
        assert rows and "apron" in rows[0]["look"]


# ------------------------------------------------------ render-on-view

class TestTheDirectorsRenderSettlesOnce:

    def test_a_render_settles_and_the_next_visit_keeps_it(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"hall": _charter()})
        out = settle_rendered_surfaces(cid, [
            {"charter": "hall", "body": "reeve:0001",
             "render": "A reeve with ink on his cuffs and a chain of office."}])
        assert out and out[0].get("settled")
        again = settle_rendered_surfaces(cid, [
            {"charter": "hall", "body": "reeve:0001",
             "render": "Somebody else entirely."}])
        assert again == []
        records = background_presence_records(cid, places={"hall"})
        surface = next(iter(records.values()))["sketch"]["surface"]
        assert surface["rendered"].startswith("A reeve with ink")

    def test_a_render_that_contradicts_a_dealt_axis_is_refused(self, temp_db):
        cid = _chat(temp_db)
        charter = _charter()
        save_registry(cid, {"hall": charter})
        dealt = cs.surface_of(charter, "reeve:0001")
        other = next(v for v in LAW["stature"] if v != dealt["stature"])
        out = settle_rendered_surfaces(cid, [
            {"charter": "hall", "body": "reeve:0001",
             "render": f"A {other} man at the ledger."}])
        assert out == [{"charter": "hall", "body": "reeve:0001",
                        "refused": "stature"}]
        records = background_presence_records(cid, places={"hall"})
        assert "rendered" not in next(iter(records.values()))["sketch"]["surface"]

    def test_a_render_may_add_what_the_law_never_dealt(self):
        charter = _charter()
        surface, refused = cs.settle_render(
            charter, "reeve:0001", "A man with a limp and a signet ring.")
        assert refused == "" and surface["rendered"]


# -------------------------------------------------------------- closure

@pytest.fixture(scope="module")
def harrowmere():
    with open(os.path.join(_HERE, "data", "harrowmere_plan.json")) as fh:
        return json.load(fh)


class TestGenerationDealsEveryBody:

    def test_a_plan_without_a_law_warns_and_still_deals_everyone(self, harrowmere):
        town = close_plan(harrowmere)
        assert any("no look law" in w for w in town["closure"]["warnings"])
        for charter in town["charters"].values():
            for body in charter["bodies"].values():
                assert cs.surface_has_content(body["surface"])
                assert body["surface"]["law"] == "default"

    def test_an_authored_law_is_dealt_and_replays_byte_identical(self, harrowmere):
        plan = copy.deepcopy(harrowmere)
        for raw in plan["charters"]:
            raw["looks"] = LAW
            for post in raw["posts"].values():
                post["worn"] = ["a hood"]
        a, b = close_plan(plan), close_plan(plan)
        assert json.dumps(a["charters"], sort_keys=True) == \
            json.dumps(b["charters"], sort_keys=True)
        assert not any("no look law" in w for w in a["closure"]["warnings"])
        for charter in a["charters"].values():
            assert charter["looks"]["build"] == LAW["build"]
            for body in charter["bodies"].values():
                assert body["surface"]["law"] == "authored"
                assert body["surface"]["build"] in LAW["build"]
                assert body["surface"]["worn"] == ["a hood"]
