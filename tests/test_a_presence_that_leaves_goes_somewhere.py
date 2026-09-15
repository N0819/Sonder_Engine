"""A background figure that says where it goes is there when the beat ends.

A reaction is stateless, and nothing it said could move its figure: `room`
is where it reacted, `action` is prose nobody reads, `charter_act` needs a
charter body. A figure who rose from the card table to answer a summons
(scratch play 2026-09-14, chat 9 turn 11) was still seated four beats later
while the player waited for him downstairs. `goes_to` is the typed exit, and
the commit walks it on the one graph every body walks.
"""
from agents.background import _presence_exits, _presence_rooms
from llm.schemas import BackgroundReactOutput
from llm import prompts
from persist.commit import apply_presence_departures


def _scene():
    door = {"kind": "open_doorway"}
    return {
        "rooms": {
            "card_room": {"name": "card room", "adjacent": [
                {"to": "ballroom", "barrier": door}]},
            "ballroom": {"name": "ballroom", "adjacent": [
                {"to": "card_room", "barrier": door},
                {"to": "supper_room", "barrier": door}]},
            "supper_room": {"name": "supper room", "adjacent": [
                {"to": "ballroom", "barrier": door}]},
        },
        "entities": {"josiah_crane": {"name": "Josiah Crane", "kind": "person"}},
        "positions": {"Josiah Crane": "card_room", "Clara": "supper_room"},
    }


def test_the_figure_is_shown_the_exits_and_the_rooms_of_the_place():
    exits = _presence_exits(_scene(), "card_room")
    assert exits == [{"room_id": "ballroom", "name": "ballroom"}]
    assert _presence_exits(_scene(), "") == []
    assert [r["room_id"] for r in _presence_rooms(_scene())] == [
        "ballroom", "card_room", "supper_room"]


def test_a_declared_exit_moves_the_figure_one_step():
    scene = _scene()
    presences = {"Josiah Crane": {"name": "Josiah Crane", "recent": []}}
    warnings = []
    moved = apply_presence_departures(
        scene, [{"name": "Josiah Crane", "action": "rises", "goes_to": "ballroom"}],
        presences, warn=warnings.append)
    assert moved == [("Josiah Crane", "card_room", "ballroom")]
    assert scene["positions"]["Josiah Crane"] == "ballroom"
    assert presences["Josiah Crane"]["recent"][-1]["text"] == "went through to ballroom"
    assert warnings == []


def test_a_room_two_steps_away_is_reached_this_beat():
    """The owner's call, 2026-09-14: one room a beat is "rather extremely
    strict" for a figure crossing a building between two beats."""
    scene = _scene()
    warnings = []
    moved = apply_presence_departures(
        scene, [{"name": "Josiah Crane", "action": "rises", "goes_to": "supper_room"}],
        {}, warn=warnings.append)
    assert moved == [("Josiah Crane", "card_room", "supper_room")]
    assert scene["positions"]["Josiah Crane"] == "supper_room"
    assert warnings == []


def test_a_room_no_open_route_reaches_is_refused_and_the_figure_stays():
    scene = _scene()
    scene["rooms"]["ballroom"]["adjacent"][1]["barrier"] = {"kind": "locked_door"}
    scene["rooms"]["supper_room"]["adjacent"][0]["barrier"] = {"kind": "locked_door"}
    warnings = []
    moved = apply_presence_departures(
        scene, [{"name": "Josiah Crane", "action": "rises", "goes_to": "supper_room"}],
        {}, warn=warnings.append)
    assert moved == []
    assert scene["positions"]["Josiah Crane"] == "card_room"
    assert warnings and "no open route" in warnings[0]


def test_no_such_room_is_refused_and_an_empty_goes_to_stays():
    scene = _scene()
    warnings = []
    moved = apply_presence_departures(
        scene, [{"name": "Josiah Crane", "goes_to": "the moon"},
                {"name": "Josiah Crane", "goes_to": ""}],
        {}, warn=warnings.append)
    assert moved == []
    assert len(warnings) == 1 and "no room here" in warnings[0]


def test_the_field_and_the_sheet_name_the_same_thing():
    assert BackgroundReactOutput(reacts=True, goes_to="ballroom").goes_to == "ballroom"
    assert BackgroundReactOutput().goes_to == ""
    sheet = prompts.get_prompt_body("background_react", "en")
    assert "goes_to" in sheet and "place.rooms" in sheet
