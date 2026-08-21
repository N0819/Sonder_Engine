"""Situations, and the three defects found when the layer got its first tests.

The practices machinery landed with a measurement (5,432 interactions, zero
empty beats) and no tests, and all three defects below survived it — each of
the class this repo keeps re-learning: the output shape was checked, the
consumer was never called.

  * A retold NEWS claim was rebuilt in body-claim shape, losing its kind —
    "news travels for free" was true, but it travelled as a token no
    listener could articulate: `known_news` empty, `can_bring_up` empty.
  * `ask`'s utility enumerated the subjects THE OTHER HEAD HELD — 634 of
    2,413 asks on the twin towns named a subject the asker did not hold,
    knowledge of which reached it through no channel.
  * No affordance checked co-presence at ACT time, so a practice that
    outlived its room let two parted bodies keep trading claims — measured
    directly, a body in one room greeted a body in another and minted a
    full-strength first-hand sighting through the wall.
"""

from __future__ import annotations

from world.charter import (
    IDLE_CLOSE_HOURS, close_stale, enact, hear, known_news, offers,
    opportunities, report_up, witness)
from world.charter_news import news_key
from world.charter_practice import _open
from world.charter_talk import RETOLD_RETENTION


def _body(key, place, available=True):
    return {"key": key, "place": place, "available": available,
            "competence": {}}


def _claim(subject, strength, heard_from=None):
    return {"body": subject, "competence": {}, "believed_available": True,
            "strength": float(strength), "as_of_hours": 0.0,
            "heard_from": heard_from}


class TestRetoldNewsStaysNews:
    def test_a_second_hand_fact_can_still_be_brought_up(self):
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        event = {"kind": "upkeep_out_of_band", "place": "p1",
                 "at_hours": 10.0, "upkeep": "u1", "level": 0.1}
        minds, _ = witness({}, {"a": bodies["a"]}, [event], 10.0)

        assert hear(minds, "b", "a", news_key(event), RETOLD_RETENTION, 1.0)

        held = known_news(minds, "b")
        assert held, "the listener heard the news and cannot articulate it"
        assert held[0]["event_kind"] == "upkeep_out_of_band"
        assert held[0]["about"] == "u1"
        assert held[0]["heard_from"] == "a"

    def test_a_retold_body_claim_is_unchanged_by_the_fix(self):
        minds = {"a": {"c": _claim("c", 1.0)}, "b": {}}

        assert hear(minds, "b", "a", "c", RETOLD_RETENTION, 1.0)

        arrived = minds["b"]["c"]
        assert arrived["strength"] == RETOLD_RETENTION
        assert arrived["heard_from"] == "a"
        assert arrived["believed_available"] is True
        assert "kind" not in arrived


class TestOneDecayerPerStore:
    def test_news_fades_at_exactly_the_news_rate(self):
        """`decay_news`'s docstring always promised body claims to
        `charter_mind`; `decay_minds` was nonetheless decaying everything,
        so news actually faded at the SUM of two rates and
        `NEWS_DECAY_PER_HOUR` was not the news decay rate. An authored rate
        that does not mean what it says fails silently."""
        from world.charter import decay_minds, decay_news
        from world.charter_news import NEWS_DECAY_PER_HOUR

        key = "news:upkeep_out_of_band:u1@1.0000"
        minds = {"a": {key: {"kind": "news", "body": key,
                             "event_kind": "upkeep_out_of_band",
                             "about": "u1", "place": "p1",
                             "happened_at": 1.0, "strength": 1.0,
                             "as_of_hours": 1.0, "heard_from": None}}}

        minds = decay_minds(minds, 10.0)
        minds = decay_news(minds, 10.0, {key})

        assert abs(minds["a"][key]["strength"]
                   - (1.0 - NEWS_DECAY_PER_HOUR * 10.0)) < 1e-9


class TestTheRegisterHoldsPeople:
    def test_news_in_a_watch_standers_head_never_joins_the_roster(self):
        """`report_up` predates `kind` and reported every claim a
        watch-stander held — so every witnessed event joined the register as
        a pseudo-person named `news:…`, and a figure the guard met became an
        entry in the institution's book of its own people. The register is a
        roster of who can be posted; only body claims belong."""
        bodies = {"a": _body("a", "p1")}
        event = {"kind": "upkeep_out_of_band", "place": "p1",
                 "at_hours": 1.0, "upkeep": "u1", "level": 0.1}
        minds, _ = witness({}, bodies, [event], 1.0)
        minds["a"]["b"] = _claim("b", 1.0)
        minds["a"]["fig"] = {"kind": "figure", "body": "fig", "place": "p1",
                             "surface": {}, "strength": 1.0,
                             "as_of_hours": 1.0, "heard_from": None}

        roster = report_up({}, minds, {"post": "a"}, bodies, at_hours=2.0)

        assert set(roster) == {"b"}


class TestTheAskersOwnGap:
    def test_an_ask_names_a_subject_the_asker_holds(self):
        """The asker's thin claim is about s1; the other privately holds s2.
        Asking about s2 would require reading the other's head."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {"a": {"s1": _claim("s1", 0.2), "b": _claim("b", 1.0)},
                 "b": {"s1": _claim("s1", 1.0), "s2": _claim("s2", 1.0),
                       "a": _claim("a", 1.0)}}
        key, entry = _open("converse", "p1", {"a": "a", "b": "b"}, 0.0)

        acts, *_rest = enact(bodies, minds, {}, {key: entry}, {}, {}, 0.0)

        asks = [a for a in acts if a["act"] == "ask" and a["actor"] == "a"]
        assert asks, "the asker had a thin claim and did not ask"
        assert "s1" in asks[0]["line"]
        assert "s2" not in asks[0]["line"]

    def test_an_honest_ask_can_miss_and_a_miss_is_not_an_effect(self):
        """The other holds nothing on the subject: nothing arrives, and the
        beat records nothing. A dead question must not keep a situation
        warm — with misses counted as effects, every open conversation
        stayed open forever and the town measured 0.9 acts per body per
        hour against the 0.147 the layer was tuned at."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {"a": {"s1": _claim("s1", 0.2), "b": _claim("b", 1.0)},
                 "b": {"a": _claim("a", 1.0)}}
        key, entry = _open("converse", "p1", {"a": "a", "b": "b"}, 0.0)

        acts, *_rest = enact(bodies, minds, {}, {key: entry}, {}, {}, 1.0)

        assert not any(a["act"] == "ask" and a["actor"] == "a" for a in acts)
        assert minds["a"]["s1"]["strength"] == 0.2, "an answer from nowhere"
        assert entry["last_effect_at"] == 0.0, "a dead question kept the " \
            "situation warm"


class TestSpeakingDistance:
    def test_no_affordance_fires_across_rooms(self):
        """The situation remembers the pair; the world decides whether they
        are still within speaking distance."""
        bodies = {"a": _body("a", "east"), "b": _body("b", "west")}
        minds = {"a": {"c": _claim("c", 0.9)}, "b": {}}
        key, entry = _open("converse", "east", {"a": "a", "b": "b"}, 0.0)

        acts, *_rest = enact(bodies, minds, {}, {key: entry}, {}, {}, 1.0)

        assert acts == []
        assert minds["b"] == {}, "a first-hand sighting through a wall"

    def test_a_parted_pairs_practice_still_closes(self):
        key, entry = _open("converse", "east", {"a": "a", "b": "b"}, 0.0)

        survivors = close_stale({key: entry}, IDLE_CLOSE_HOURS + 0.1)

        assert survivors == {}


class TestSituationsOpenAndFeed:
    def test_two_strangers_in_a_room_get_a_greeting(self):
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}

        opened = opportunities(bodies, {}, {}, [], {}, 0.0)

        kinds = {entry["kind"] for entry in opened.values()}
        assert "greeting" in kinds

    def test_acting_spawns_the_next_situation(self):
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {}
        opened = opportunities(bodies, minds, {}, [], {}, 0.0)

        acts, spawned, _closed, _heard, _refused = enact(
            bodies, minds, {}, opened, {}, {}, 0.0)

        assert any(a["act"] == "greet" for a in acts)
        assert any(entry["kind"] == "converse" for _k, entry in spawned)

    def test_offers_enumerates_without_licensing(self):
        """The Versu seam: the action instances handed outward are the same
        set the chooser picks from, and reading them changes nothing."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {"a": {"b": _claim("b", 1.0), "s1": _claim("s1", 0.3)},
                 "b": {"a": _claim("a", 1.0)}}
        key, entry = _open("converse", "p1", {"a": "a", "b": "b"}, 0.0)
        before = {h: dict(c) for h, c in minds.items()}

        rows = offers(bodies, minds, {}, {key: entry}, {}, {}, 0.0)

        assert {r["act"] for r in rows["a"]} >= {"ask", "tell"}
        assert minds == before
