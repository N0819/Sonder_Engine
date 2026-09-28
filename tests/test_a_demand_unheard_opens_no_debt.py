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


def test_the_beats_own_row_carries_its_line_as_a_note():
    """Round 5 (2026-09-23) idx 11: the commit pairs an op with the beat's
    SEQUENCE row, whose line is its `note`; read as `event` it was empty and
    every demand was exempted. Sal heard "...Keep..." and owed the whole."""
    row = {"categories": ["obligations", "speech"], "note": "Aye. Keep it dry,"}
    view = "The grizzled striker says something you cannot make out: ...Keep..."
    assert _demand_unheard_by(_Ctx(view), "Sal Weatherby", row)


class _PlayersCtx(dict):
    """The player's view is keyed `player`, an extra player's
    `extra:<persona_id>`; the cast holds neither. The chat is dict-shaped and
    names its persona by id, as `ChatData` does in a live commit."""

    def __init__(self, db, player_view, extra_view=""):
        from story.character_schema import default_persona_data
        super().__init__(perception_outcome={"views": {
            "player": player_view, "extra:12": extra_view}})
        persona_id = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                           ("Hinami", json.dumps(default_persona_data("Hinami")), "{}"))
        self.cast = [{"id": 7, "sheet": json.dumps(default_character_data("Sal Weatherby"))}]
        self.chat = {"id": 1, "persona_id": persona_id}
        self.extra_players = [{"persona_id": 12, "name": "Ivo Marsh"}]


BACKGROUND_LINE = {"categories": ["speech"],
                   "event": "Someone hollering out there -- want me to go look?"}


def test_the_player_owes_nothing_on_a_line_that_never_reached_her(temp_db):
    """Chat 122 replay (2026-09-28): a background figure's question reached no
    view, and the ledger held Hinami owing its answer for beats after -- the
    debtor was looked up among the cast alone, so the player had no view."""
    ctx = _PlayersCtx(temp_db, "The surf rolls in. The box stands upright on the sand.")
    assert _demand_unheard_by(ctx, "Hinami", BACKGROUND_LINE)


def test_the_player_owes_a_line_she_heard(temp_db):
    ctx = _PlayersCtx(temp_db, 'A voice calls: "Someone hollering out there -- '
                               'want me to go look?"')
    assert not _demand_unheard_by(ctx, "Hinami", BACKGROUND_LINE)


def test_an_extra_player_is_found_by_their_own_view(temp_db):
    ctx = _PlayersCtx(temp_db, "anything", extra_view="Only the surf.")
    assert _demand_unheard_by(ctx, "Ivo Marsh", BACKGROUND_LINE)


def test_rows_pair_with_current_ops_only():
    ops = [({"op": "open"}, False), ({"op": "open"}, True)]
    assert _zip_rows(ops, [{"event": "x"}]) == [
        ({"op": "open"}, False, {}), ({"op": "open"}, True, {"event": "x"})]
