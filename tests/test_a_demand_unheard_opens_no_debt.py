"""A debt is opened by a demand that reached its debtor.

Playerless Aldermill round 4 (2026-09-23): a question put to Sal was refused
to her by perception, and the obligation ledger still held her owing its
answer for nine beats, re-deferred past its window on every one.
"""
import json

from persist.commit import _demand_unheard_by, _zip_rows
from story.character_schema import default_character_data


class _Ctx(dict):
    def __init__(self, view):
        super().__init__(perception_outcome={"views": {"7": view}})
        self.cast = [{"id": 7, "sheet": json.dumps(default_character_data("Sal Weatherby"))}]


ROW = {"categories": ["speech"],
       "event": "Have you business in this yard, or are you waiting on someone?"}


def test_a_line_the_debtor_never_heard_opens_nothing():
    assert _demand_unheard_by(_Ctx("You are in Mill Yard. A cart creaks."),
                              "Sal Weatherby", ROW)


def test_a_line_the_debtor_heard_opens_the_debt():
    view = ('A voice says: "Have you business in this yard, or are you '
            'waiting on someone?"')
    assert not _demand_unheard_by(_Ctx(view), "Sal Weatherby", ROW)


def test_a_debtor_with_no_view_or_a_row_that_is_no_line_is_left_alone():
    assert not _demand_unheard_by(_Ctx("nothing"), "Master Kenelmund", ROW)
    assert not _demand_unheard_by(_Ctx("nothing"), "Sal Weatherby",
                                  {"categories": ["poses"], "event": ROW["event"]})


def test_rows_pair_with_current_ops_only():
    ops = [({"op": "open"}, False), ({"op": "open"}, True)]
    assert _zip_rows(ops, [{"event": "x"}]) == [
        ({"op": "open"}, False, {}), ({"op": "open"}, True, {"event": "x"})]
