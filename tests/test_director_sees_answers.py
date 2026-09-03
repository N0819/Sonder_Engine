"""A person's answer is their own ledgers', and the Director is shown it.

Harrowmere replay t26 (2026-09-03): the prose author had the reeve grant
the request and the narrator rendered it, while the same beat's figure act
landed `request -> declined, reason pressed`. The voice had the preview
(`presence_view` -> `answers`); the Director did not. `figure_answers` now
puts the identical judgment on the resolve payload's `present_figures`
rows, computed by `charter_author.dealing_answer` -- the single decision
`_figure_dealing` records -- so no second reading can exist to disagree.
"""

from __future__ import annotations

import copy
import json
import time

from world.charter import authored, normalize_charter, seed_needs
from world.charter_author import dealing_answer, preview_dealings


TRAVELLER = {"traveller": {"place": "yard", "surface": {"cloak": "grey"}}}


def _yard(**extra):
    charter = normalize_charter({
        "key": "pair",
        "bodies": {
            "ash": {"name": "Ash", "competence": {}, "available": True,
                    "place": "yard"},
            "birch": {"name": "Birch", "competence": {}, "available": True,
                      "place": "yard"},
        },
        "figures": TRAVELLER,
        "clock_hours": 10.0,
        **extra,
    })
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _ranked():
    return _yard(
        posts={"chief": {"place": "yard"},
               "hand": {"place": "yard", "reports_to": "chief"}},
        watch={"chief": "birch", "hand": "ash"},
        bindings={"birch": {"name": "traveller", "char_id": 1}})


def _press(charter, body):
    for need in charter["needs"][body].values():
        need["level"] = 0.0
    return charter


class TestThePreviewIsTheJudgmentTheLedgerRecords:
    def test_granted_and_declined_agree_with_the_applied_act(self):
        for pressed in (False, True):
            charter = _yard()
            if pressed:
                _press(charter, "ash")
            preview = preview_dealings(charter, "traveller", ["ash"],
                                       ("request", "bargain"))["ash"]
            _c, record = authored(copy.deepcopy(charter), "traveller",
                                  "request", "ash", terms="the rolls")
            assert preview[0]["act"] == "request"
            assert preview[0]["answer"] == record["answer"]
            assert preview[0]["reason"] == record.get("reason", "")
            _c, record = authored(copy.deepcopy(charter), "traveller",
                                  "bargain", "ash", terms="a fair price")
            assert preview[1]["answer"] == record["answer"]
        assert preview[0]["answer"] == "declined" and \
            preview[0]["reason"] == "pressed"

    def test_an_order_without_standing_is_answered_as_a_request(self):
        charter = _yard()
        preview = preview_dealings(charter, "traveller", ["ash"],
                                   ("order",))["ash"][0]
        assert preview == {"act": "order", "answered_as": "request",
                           "answer": "granted", "reason": ""}
        _c, record = authored(copy.deepcopy(charter), "traveller", "order",
                              "ash", terms="fetch the rolls")
        assert record["as"] == "request" and record["answer"] == "granted"

    def test_an_order_with_standing_is_obeyed_or_refused_alike(self):
        charter = _ranked()
        preview = preview_dealings(charter, "traveller", ["ash"],
                                   ("order",))["ash"][0]
        assert preview["answered_as"] == "" and preview["answer"] == "obeyed"
        _c, record = authored(copy.deepcopy(charter), "traveller", "order",
                              "ash", terms="fetch the rolls")
        assert record["answer"] == "obeyed"
        charter["bodies"]["ash"]["available"] = False
        assert dealing_answer(
            {"bodies": charter["bodies"], "regard": {}}, charter["needs"],
            {"watch": charter["watch"], "posts": charter["posts"],
             "bindings": charter["bindings"], "commitments": {}},
            "traveller", "order", "ash", charter["bodies"]["ash"]) == \
            ("order", "refused", "unable")

    def test_the_preview_touches_nothing(self):
        charter = _yard()
        before = json.dumps(charter, sort_keys=True, default=str)
        preview_dealings(charter, "traveller", ["ash", "birch", "nobody"],
                         ("order", "request", "bargain"))
        assert json.dumps(charter, sort_keys=True, default=str) == before

    def test_a_body_the_charter_does_not_hold_gets_no_entry(self):
        assert preview_dealings(_yard(), "traveller", ["nobody"],
                                ("request",)) == {}


class TestTheDirectorIsShownTheAnswers:
    def _registry(self, temp_db, cid):
        from world import charter_runtime
        charter = _yard()
        _press(charter, "ash")
        charter_runtime.save_registry(cid, {"pair": charter})

    def test_one_line_per_act_with_the_asker_unnamed(self, temp_db):
        from world.charter_runtime import figure_answers
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Answers", "", time.time()))
        self._registry(temp_db, cid)
        figures = [
            {"name": "Ash", "role": "", "room": "yard", "posts": [],
             "charter": "pair", "body": "ash"},
            {"name": "Birch", "role": "", "room": "yard", "posts": [],
             "charter": "pair", "body": "birch"},
            {"name": "Ghost", "role": "", "room": "yard", "posts": [],
             "charter": "gone", "body": "g1"},
        ]
        answers = figure_answers(cid, figures, "traveller")
        assert answers == {
            "Ash": ["order: answered as a request, declined (pressed)",
                    "request: declined (pressed)",
                    "bargain: declined (pressed)"],
            "Birch": ["order: answered as a request, granted",
                      "request: granted",
                      "bargain: accepted"],
        }
        assert "traveller" not in json.dumps(answers)

    def test_nobody_present_means_nothing_computed(self, temp_db):
        from world.charter_runtime import figure_answers
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Answers", "", time.time()))
        assert figure_answers(cid, [], "traveller") == {}
        assert figure_answers(cid, [{"name": "x"}], "traveller") == {}
