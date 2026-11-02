"""The exposure fallback can no longer darken a room on a keyword: it reads a
keyword only as a whole word of the room's own text, and it reads the open
sky from the room's NAME alone.

world_offscreen_time F3 (audit 2026-11-01, measured read-only on the
owner's engine.db): a room misread `open` is DARK AT NIGHT whatever light it
declares (`spatial_light.room_light`) and has the rain fall on whoever stands
in it (`weather_for_room.falls_on_you`). Matched as substrings, "wood" in
"wooden", "roof" in "soundproof", "road"/"yard" in "broad"/"Halyard's"
misread 41 of the 666 rooms that author no exposure. Matched as whole words
over the description, an indoor room still read `open` on what its windows
look out on: of 14 distinct rooms the description alone read open, 9 were
indoors (a washroom facing the mountain, a tavern room over the street, a
ship's lounge). With the name deciding the sky, no live room reads darker
than it did, and 52 records read `enclosed` that read `open`.
"""

from world import weather


def _scene(name, desc):
    return {"rooms": {"r": {"name": name, "desc": desc}}}


def _exposure(name, desc):
    weather._ROOM_FACTS.clear()
    return weather.room_exposure(_scene(name, desc), "r")


def test_a_word_inside_another_word_is_not_a_keyword():
    assert _exposure("Tavern Common Room",
                     "Wooden tables are scattered under the beams.") == "enclosed"
    assert _exposure("Observation Dome",
                     "A dome of soundproof reinforced glass.") == "enclosed"
    assert _exposure("Halyard's Rest Observation Deck",
                     "A broad viewport gallery.") == "enclosed"
    assert _exposure("Study", "A wooden-panelled study lit by a fire.") == "enclosed"
    assert _exposure("Planetarium", "A ring of seats under a painted dome.") \
        == "enclosed"


def test_a_description_never_puts_a_room_under_the_sky():
    assert _exposure("Washroom", "A deep tub; the window faces the mountain.") \
        == "enclosed"
    assert _exposure("Tavern Room",
                     "A straw bed by a window over the street outside.") \
        == "enclosed"
    assert _exposure("Ten Forward", "The ship's lounge behind a bank of "
                     "viewports.") == "enclosed"


def test_the_name_still_puts_a_place_under_the_sky():
    assert _exposure("Market Square", "Stalls and cobbles.") == "open"
    assert _exposure("The Wood", "Birch and bracken.") == "open"
    assert _exposure("Rose Gardens", "Beds of roses.") == "open"
    assert _exposure("Old Cellar", "Barrels in the dark.") == "enclosed"
    assert _exposure("Cave Mouth", "The overhang drips.") == "sheltered"
    assert _exposure("Woodcutter's Lean-to", "A roof of boughs.") == "sheltered"


def test_a_description_may_still_take_a_room_indoors():
    assert _exposure("Market Square", "Stalls under a covered arcade.") \
        == "sheltered"
    assert _exposure("North Road", "The road dives into a tunnel.") == "enclosed"


def test_an_anchor_is_read_by_whole_words_too():
    assert weather.anchor_exposure({"name": "Stall canopy"}) == "sheltered"
    assert weather.anchor_exposure({"name": "Awnings"}) == "sheltered"
    assert weather.anchor_exposure(
        {"name": "Brazier", "desc": "Uncovered, its coals glowing."}) == ""


def test_the_deep_words_are_whole_words():
    """`_matches` reads `_DEEP_WORDS` for an unmapped room: "mine" inside
    "mineral" put a spring house at the depth of a mine shaft."""
    weather._ROOM_FACTS.clear()
    assert weather._matches(_scene(
        "Spring House", "A mineral spring rises in a stone basin."),
        "r", weather._DEEP_WORDS) is False
    assert weather._matches(_scene("Old Mine", "Timbers shore up the walls."),
                            "r", weather._DEEP_WORDS) is True
    assert weather._matches(_scene("The Catacombs", "Bones in niches."),
                            "r", weather._DEEP_WORDS) is True
