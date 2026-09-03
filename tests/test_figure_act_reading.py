"""Reading the beat for acts toward a townsperson: what the Harrowmere
replay (2026-09-03) showed the reader missing, six beats in seven.

* A compound speech-act kind carries every kind it names ("claim and
  request" is a request); a kind naming none is read as `other` and SAID.
* The story language's determiners are not words of a name ("The Miller"
  is the miller).
* A role noun resolves through what the post is authored to be and do --
  its key, titles, the upkeeps it serves and its authority entries, as
  stems -- never through a synonym list ("the brewer" is the cook whose
  duty reads "brews small beer").
* When a posted body and an ambient shadow both answer to a spelling, the
  posted body is the one the town stands there.
"""

from __future__ import annotations

from agents.director import _ground_public_evidence, _speech_act_kinds
from world.charter import normalize_charter
from world.charter_observe import resolve_target_body
from world.charter_runtime import plan_figure_acts


def _inn():
    return normalize_charter({
        "key": "ford_inn",
        "naming": {"formal_format": "{title} {given} {family}",
                   "titles": {"posts": {"innkeeper": "Innkeeper",
                                        "cook": "Cook",
                                        "stablehand": "Stablehand"},
                              "ranks": {"head": "Innkeeper of the Ford Inn",
                                        "officer": "Cook"}}},
        "upkeeps": {"keep_beer": {"place": "inn_kitchen"},
                    "keep_kitchen": {"place": "inn_kitchen"},
                    "keep_stable": {"place": "inn_stable"}},
        "posts": {
            "innkeeper": {"place": "inn_common",
                          "serves": ["keep_beer"],
                          "authority": ["runs the Ford Inn, serves the "
                                        "common room"]},
            "cook": {"place": "inn_kitchen", "reports_to": "innkeeper",
                     "serves": ["keep_kitchen", "keep_beer"],
                     "authority": ["prepares meals and brews small beer"]},
            "stablehand": {"place": "inn_stable", "reports_to": "innkeeper",
                           "serves": ["keep_stable"],
                           "authority": ["tends road horses and stables"]},
        },
        "bodies": {
            "cook:0001": {"name": "Jedstaned Fenfordwick",
                          "place": "inn_kitchen", "rank": "officer"},
            "innkeeper:0001": {"name": "Tamriced Fenbrookfield",
                               "place": "inn_kitchen", "rank": "head"},
            "stablehand:0002": {"name": "Maldunel Dunwellford",
                                "place": "inn_stable"},
        },
        "watch": {"cook": "cook:0001", "innkeeper": "innkeeper:0001",
                  "stablehand": "stablehand:0002"},
    })


def _smithy():
    return normalize_charter({
        "key": "smithy",
        "naming": {"titles": {"posts": {"smith": "Smith",
                                        "smith_apprentice": "Apprentice"}}},
        "upkeeps": {"keep_forge": {"place": "smithy"}},
        "posts": {"smith": {"place": "smithy", "serves": ["keep_forge"],
                            "authority": ["shoes road horses"]},
                  "smith_apprentice": {"place": "smithy",
                                       "reports_to": "smith",
                                       "serves": ["keep_forge"],
                                       "authority": ["tends the forge"]}},
        "bodies": {"smith:0001": {"name": "Tamstanmere Gargatebridge",
                                  "place": "smithy"},
                   "smith_apprentice:0003": {"name": "Kelminton Penstoneton",
                                             "place": "smithy"}},
        "watch": {"smith": "smith:0001",
                  "smith_apprentice": "smith_apprentice:0003"},
    })


def _ambient(name, place):
    return normalize_charter({
        "key": "ambient", "posts": {}, "upkeeps": {},
        "bodies": {name.casefold().replace(" ", "_") + ":abc123":
                   {"name": name, "place": place}},
    })


class TestACompoundKindCarriesEveryKindItNames:
    def test_the_words_are_read_against_the_closed_set(self):
        assert _speech_act_kinds("claim and request") == ["request"]
        assert _speech_act_kinds("Offer / bargain") == ["offer", "bargain"]
        assert _speech_act_kinds("request") == ["request"]
        assert _speech_act_kinds("ask") == []
        assert _speech_act_kinds("") == []

    def test_a_communication_frame_is_read_by_the_same_reader(self):
        out = {"dialogue_log": [], "public_evidence": []}
        view = {"public_sources": [{
            "source_id": "comm:0", "kind": "communication",
            "actor": "Wren Ashby", "target": "The Gatekeeper",
            "visibility": "overt", "conceal_from": [],
            "speech_acts": [
                {"kind": "claim and request",
                 "content": "asks him to let the next drover through"},
                {"kind": "ask", "content": "whether the reeve is in"}],
        }]}
        unread = _ground_public_evidence(out, view)
        frames = out["public_evidence"][0]["speech_acts"]
        # The interpreter's own verb ("ask") is kept as written -- it is
        # the surface's vocabulary, not this one's -- and names no public
        # kind, so no ledger answers it and nothing is warned about it.
        assert [f["kind"] for f in frames] == ["request", "ask"]
        assert frames[0]["content"] == \
            "asks him to let the next drover through"
        assert unread == []

    def test_the_social_hands_unknown_kind_is_other_and_said(self):
        quote = '"Would you have the clerk pull the old rolls?"'
        out = {"dialogue_log": [{"speaker": "Wren", "exact_quote": quote,
                                 "intended_target": "the reeve",
                                 "volume": "normal"}],
               "public_evidence": [{"source_id": "speech:0",
                                    "speech_acts": [{
                                        "kind": "ask",
                                        "content": "pull the old rolls"}]}]}
        view = {"public_sources": [{
            "source_id": "speech:0", "kind": "speech", "actor": "Wren",
            "exact_quote": quote, "target": "the reeve",
            "volume": "normal", "visibility": "overt", "conceal_from": []}]}
        assert _ground_public_evidence(out, view) == ["ask"]
        assert [f["kind"] for f in out["public_evidence"][0]["speech_acts"]] \
            == ["other"]

    def test_a_speech_frame_naming_two_kinds_becomes_two_frames(self):
        quote = '"Let him through, and I\'ll speak for you."'
        out = {"dialogue_log": [{"speaker": "Wren", "exact_quote": quote,
                                 "intended_target": "the gatekeeper",
                                 "volume": "normal"}],
               "public_evidence": [{"source_id": "speech:0",
                                    "speech_acts": [{
                                        "kind": "command and promise",
                                        "content": "Let him through"}]}]}
        view = {"public_sources": [{
            "source_id": "speech:0", "kind": "speech", "actor": "Wren",
            "exact_quote": quote, "target": "the gatekeeper",
            "volume": "normal", "visibility": "overt", "conceal_from": []}]}
        assert _ground_public_evidence(out, view) == []
        assert [f["kind"] for f in out["public_evidence"][0]["speech_acts"]] \
            == ["command", "promise"]


class TestAnArticleIsNotPartOfAName:
    def test_the_miller_is_the_miller(self):
        mill = normalize_charter({
            "key": "mill",
            "naming": {"titles": {"posts": {"miller": "Miller"},
                                  "ranks": {"head": "Miller of Harrowmere"}}},
            "posts": {"miller": {"place": "mill"},
                      "mill_hand": {"place": "mill", "reports_to": "miller"}},
            "bodies": {"miller:0001": {"name": "Keldunwick Stanwickbridge",
                                       "place": "mill", "rank": "head"},
                       "mill_hand:0002": {"name": "Garthored Garmerewell",
                                          "place": "mill"}},
            "watch": {"miller": "miller:0001", "mill_hand": "mill_hand:0002"},
        })
        assert resolve_target_body(mill, "The Miller", place="mill") == \
            "miller:0001"
        assert resolve_target_body(mill, "the miller", place="mill") == \
            "miller:0001"
        assert resolve_target_body(mill, "the mill hand", place="mill") == \
            "mill_hand:0002"

    def test_a_name_is_still_a_name(self):
        inn = _inn()
        assert resolve_target_body(inn, "Tamriced Fenbrookfield",
                                   place="inn_kitchen") == "innkeeper:0001"
        assert resolve_target_body(inn, "Fenbrookfield",
                                   place="inn_kitchen") == "innkeeper:0001"


class TestARoleNounResolvesThroughThePost:
    def test_the_brewer_is_the_cook_whose_duty_is_brewing(self):
        assert resolve_target_body(_inn(), "the brewer",
                                   place="inn_kitchen") == "cook:0001"
        assert resolve_target_body(_inn(), "the cook",
                                   place="inn_kitchen") == "cook:0001"

    def test_the_exact_post_outranks_a_post_that_merely_contains_the_word(
            self):
        assert resolve_target_body(_smithy(), "the smith", place="smithy") \
            == "smith:0001"
        assert resolve_target_body(_smithy(), "the apprentice",
                                   place="smithy") == "smith_apprentice:0003"

    def test_two_posts_answering_alike_is_nobody(self):
        # Both serve the forge: "the forge hand" names neither.
        assert resolve_target_body(_smithy(), "the forge", place="smithy") \
            is None

    def test_the_room_still_bounds_it(self):
        assert resolve_target_body(_inn(), "the stablehand",
                                   place="inn_kitchen") is None


class TestAPostedBodyOutranksAnAmbientShadow:
    def _scene(self):
        return {"rooms": {"inn_kitchen": {"name": "Kitchen"}},
                "positions": {"Wren Ashby": "inn_kitchen"}}

    def _request(self, target, content="a jug of small beer to take"):
        return {"kind": "communication", "actor": "Wren Ashby",
                "target": target, "source_id": "comm:0",
                "speech_acts": [{"kind": "request", "content": content}]}

    def test_the_brewer_lands_on_the_cook_not_the_shadow(self):
        registry = {"items": {
            "ford_inn": {"state": _inn()},
            "ambient": {"state": _ambient("The Brewer", "inn_kitchen")}}}
        plans = plan_figure_acts(registry, [self._request("the brewer")], [],
                                 self._scene(), ["Wren Ashby"])
        assert [(p["charter"], p["body"]) for p in plans] == \
            [("ford_inn", "cook:0001")]

    def test_two_posted_bodies_is_still_nobody(self):
        other = _inn()
        other["key"] = "second_inn"
        registry = {"items": {"ford_inn": {"state": _inn()},
                              "second_inn": {"state": other}}}
        assert plan_figure_acts(registry, [self._request("the cook")], [],
                                self._scene(), ["Wren Ashby"]) == []

    def test_a_shadow_alone_still_answers(self):
        registry = {"items": {
            "ambient": {"state": _ambient("The Hostler", "inn_kitchen")}}}
        plans = plan_figure_acts(registry, [self._request("The Hostler")],
                                 [], self._scene(), ["Wren Ashby"])
        assert len(plans) == 1 and plans[0]["charter"] == "ambient"
