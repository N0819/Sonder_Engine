"""A crowd answering as one has no name to withhold.

`background._chorus_entry` answers an address to a crowd with one entry named
by the crowd's composition ("cousins and mistress"). Filed into the outcome
stage's identity roster, that composition was scrubbed from every observer
who had "not recognised" it, and the scrub's per-word forms took the word
"and" with it: "a chapel of dark slate the unfamiliar person granite"
(scratch play 2026-09-14, chat 7 turn 3). The chorus's act is delivered like
any other; its composition is prose, never an identity.
"""

from agents.perception import _background_beats, identity_bearing_sources
from world import crowds


def test_a_chorus_source_carries_no_identity():
    sources = [{"name": "Edith Marrow", "room": "taproom"},
               {"name": "cousins and mistress", "room": "taproom", "chorus": True},
               {"name": "Cousin Naniseth Carwarnor", "room": "taproom", "chorus": False}]
    assert [s["name"] for s in identity_bearing_sources(sources)] == [
        "Edith Marrow", "Cousin Naniseth Carwarnor"]


def test_the_background_beat_carries_the_chorus_flag():
    class _Ctx(dict):
        chat = {"id": 0}
    ctx = _Ctx()
    ctx["background_react"] = {"reactions": [
        {"name": "cousins and mistress", "chorus": True, "room": "taproom",
         "action": "answer together"},
        {"name": "Mistress Pascoe", "room": "taproom", "action": "nods"}]}
    beats = _background_beats(ctx, {"rooms": {"taproom": {}}, "positions": {}})
    assert [(b["name"], b["chorus"]) for b in beats] == [
        ("cousins and mistress", True), ("Mistress Pascoe", False)]


def test_a_band_joins_its_noun_the_way_english_does():
    assert crowds.describe({"band": "a handful", "composition": "cousins"}, "medium") \
        .startswith("a handful of cousins")
    assert crowds.describe({"band": "a dozen or so", "composition": "cousins"}, "medium") \
        .startswith("a dozen or so cousins")
    assert crowds.describe({"band": "a throng", "composition": "dockworkers"}, "large") \
        .startswith("a throng of dockworkers")
