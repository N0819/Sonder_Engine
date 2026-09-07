"""One label per (observer, body) per beat on the OUTCOME pass, and the
authored-prose gate writing the key its reader reads.

Review 2026-09-07 A3/A4/A35: the outcome pass tested the `known` ledger
before the disguise-aware display map, so an acquaintance not in
`disguise_known_to` received the canonical name for everything a masked
body said and did; `_gated_ambient_percepts` rewrote three keys and not
`detail`, which `ambient_percepts` reads first.
"""
import agents.perception as perception
from agents import composer


def _bodies():
    # `disguise_known_to` is stored casefolded (`scene.disguise_known_to`).
    return {"Mirelle": {"name": "Mirelle", "disguise_known_to": ["sarah"],
                        "disguise_conceals_identity": True}}


def test_a_masked_acquaintance_speaks_as_a_stranger_to_one_not_told():
    display_map = {"Mirelle": "the veiled woman"}
    label = perception._attributed_label(
        "Mirelle", "Aurel", recognized={"Mirelle"}, display_map=display_map,
        bodies_by_name=_bodies(), can_see=True, unseen="a voice",
        appearances={}, cast_aliases={})
    assert label == "the veiled woman"
    # ...and as herself to the one the disguise was declared to.
    assert perception._attributed_label(
        "Mirelle", "Sarah", recognized={"Mirelle"}, display_map=display_map,
        bodies_by_name=_bodies(), can_see=True, unseen="a voice",
        appearances={}, cast_aliases={}) == "Mirelle"
    # A known voice out of sight is still a known voice.
    assert perception._attributed_label(
        "Mirelle", "Sarah", recognized={"Mirelle"}, display_map={},
        bodies_by_name={}, can_see=False, unseen="a voice",
        appearances={}, cast_aliases={}) == "Mirelle"
    assert perception._attributed_label(
        "Mirelle", "Aurel", recognized=set(), display_map={},
        bodies_by_name={}, can_see=False, unseen="a voice",
        appearances={}, cast_aliases={}) == "a voice"


def test_the_scrub_pair_treats_a_masked_acquaintance_as_unknown():
    roster = [{"name": "Mirelle"}, {"name": "Aurel"}]
    recognized, unknown = perception._composer_unknown_sources(
        "Aurel", {"Aurel": ["Mirelle"]}, roster, _bodies())
    assert [s["name"] for s in unknown] == ["Mirelle"]
    assert "Mirelle" not in recognized
    recognized, unknown = perception._composer_unknown_sources(
        "Sarah", {"Sarah": ["Mirelle"]}, roster, _bodies())
    assert not any(s["name"] == "Mirelle" for s in unknown)


def test_the_gate_rewrites_detail_too():
    events = [{"kind": "sound", "room": "riser", "level": "loud",
               "detail": "Sarah Moon's siphon-vent hiss"}]
    percepts = perception._gated_ambient_percepts(
        lambda text: "a slow hiss", events, "riser")
    assert percepts and all(p.data["desc"] == "a slow hiss" for p in percepts)
    ungated = composer.ambient_percepts(events, "riser")
    assert ungated[0].data["desc"].startswith("Sarah"), "the reader takes detail first"
