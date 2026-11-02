"""Arrival language in the opening is about the opening, not the card character.

Automatic history routing searched its travel patterns over the card's public
history AND the opening passage, and checked travel first. Greetings
routinely open on the PLAYER arriving ("Dana arrives at the Gilded Goose"),
so a card whose public history states twenty years of residence was routed a
visitor: `start_story` compiled a journey for her and did not seat her in the
Charter town, which was then planned without her post (story_attire_import
audit F12, measured on the Mara case below).

Travel is now read from the card's own history only. The opening still
counts for what it can actually say about this character -- that the
setting her residence names is the setting the story opens in.
"""

from __future__ import annotations

from story.history_routing import (resolve_character_history_route,
                                   route_uses_charter)


MARA = {"identity": {"name": "Mara"}, "knowledge": {"public_history": (
    "Mara has run the Gilded Goose inn in Hollowmere for twenty years and "
    "lives in the rooms above it.")}}


def test_the_players_arrival_does_not_make_a_resident_a_visitor():
    route = resolve_character_history_route(
        MARA, opening="Dana arrives at the Gilded Goose in Hollowmere as the "
                      "rain begins.",
        location_brief="Hollowmere, a river town")
    assert route["opening_relationship"] == "resident"
    assert route_uses_charter(route)


def test_the_same_card_with_a_quiet_opening_is_unchanged():
    route = resolve_character_history_route(
        MARA, opening="The rain hammers the Gilded Goose in Hollowmere. Mara "
                      "wipes the bar.",
        location_brief="Hollowmere, a river town")
    assert route["opening_relationship"] == "resident"


def test_travel_in_the_card_itself_still_routes_a_visitor():
    sheet = {"identity": {"name": "The Wanderer"}, "knowledge": {
        "public_history": "A traveler who wanders between worlds."}}
    route = resolve_character_history_route(
        sheet, opening="The vessel lands in a desert city.",
        location_brief="a desert city")
    assert route["opening_relationship"] == "visiting"
    assert not route_uses_charter(route)
