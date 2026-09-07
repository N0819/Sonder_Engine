"""Regression tests for two scene-truth findings from the Doctor Who paradox run.

DW-4: an auto-created entity ended up in `positions` under BOTH its id key and
its display-name key, co-present in two rooms. DW-1: after a relocation to a new
place, the top-level `scene.location` label stayed stale and leaked the departed
location's name into perception/narration.
"""

from __future__ import annotations

from persist import commit
from world.spatial import merge_scene_with_diff, _dedup_duplicate_position_keys


# ---- DW-4: duplicate position keys ----

def test_id_and_name_position_keys_collapse_to_the_fresh_write():
    prev = {"entities": {"karen_marsh": {"name": "Karen Marsh"}},
            "positions": {"karen_marsh": "road", "Ellie Marsh": "road"}}
    diff = {"positions": {"Karen Marsh": "tardis", "Ellie Marsh": "tardis"}}
    merged = merge_scene_with_diff(prev, diff)
    assert "karen_marsh" not in merged["positions"]
    assert merged["positions"]["Karen Marsh"] == "tardis"  # fresh write wins


def test_a_lone_object_id_key_is_never_touched():
    """An object with only an id-keyed position (no name twin) must survive."""
    prev = {"entities": {"tardis": {"name": "TARDIS"}},
            "positions": {"tardis": "road", "Ellie Marsh": "road"}}
    merged = merge_scene_with_diff(prev, {"positions": {"Ellie Marsh": "hall"}})
    assert merged["positions"]["tardis"] == "road"


def test_dedup_prefers_name_key_when_neither_is_the_fresh_write():
    positions = {"karen_marsh": "road", "Karen Marsh": "tardis"}
    entities = {"karen_marsh": {"name": "Karen Marsh"}}
    _dedup_duplicate_position_keys(positions, entities, incoming_positions={})
    assert "karen_marsh" not in positions
    assert positions["Karen Marsh"] == "tardis"


def test_entity_without_a_name_is_ignored():
    positions = {"blob": "road"}
    entities = {"blob": {}}
    out = _dedup_duplicate_position_keys(positions, entities, {})
    assert out == {"blob": "road"}


# ---- DW-1: stale location label on relocation ----

def _ctx(monkeypatch, player="Ellie Marsh"):
    from story import scene

    from persist import commit_room_registry
    monkeypatch.setattr(scene, "persona_of",
                        lambda c: {"identity": {"name": player}}, raising=False)
    # _refresh_relocated_location resolves persona_name in ITS module's
    # globals -- commit_room_registry since the split; patching the commit
    # facade would be inert.
    monkeypatch.setattr(commit_room_registry, "persona_name", lambda p: player)

    class _Ctx:
        chat = {"id": 1}
    return _Ctx()


def test_location_refreshes_on_move_to_a_new_room(monkeypatch):
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bute_street": {"name": "Bute Street"}},
            "location": "Alley off Bute Street, Cardiff"}
    sc = {"rooms": {"bute_street": {"name": "Bute Street"},
                    "Bethnal_Green_Road": {"name": "Bethnal Green Road"}},
          "positions": {"Ellie Marsh": "Bethnal_Green_Road"},
          "location": "Alley off Bute Street, Cardiff"}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "Bethnal Green Road"


def test_director_named_location_is_preferred(monkeypatch):
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bute_street": {"name": "Bute Street"}}, "location": "Cardiff"}
    sc = {"rooms": {"bute_street": {"name": "Bute Street"},
                    "bgr": {"name": "Bethnal Green Road"}},
          "positions": {"Ellie Marsh": "bgr"}, "location": "Cardiff"}
    commit._refresh_relocated_location(sc, prev, {"location": "East London, 2003"}, ctx)
    assert sc["location"] == "East London, 2003"


def test_same_place_move_leaves_the_label_untouched(monkeypatch):
    """Moving between rooms that already existed is not a relocation."""
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bar": {"name": "Bar"}, "kitchen": {"name": "Kitchen"}},
            "location": "The Old Anchor"}
    sc = {"rooms": {"bar": {"name": "Bar"}, "kitchen": {"name": "Kitchen"}},
          "positions": {"Ellie Marsh": "kitchen"}, "location": "The Old Anchor"}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "The Old Anchor"


def test_no_player_room_leaves_the_label_untouched(monkeypatch):
    ctx = _ctx(monkeypatch)
    sc = {"rooms": {}, "positions": {}, "location": "Somewhere"}
    commit._refresh_relocated_location(sc, {"rooms": {}}, {}, ctx)
    assert sc["location"] == "Somewhere"


def test_a_new_room_in_the_same_region_keeps_a_venue_label(monkeypatch):
    """The DW-1 rule above refreshes on a brand-new destination because the
    label is presumed stale. It is stale when the new room is a new PLACE;
    it is not when the new room is the next room of the same building. Chat
    117 turn 82: a plenum minted inside Site-17 turned "Site-17, Lower Sector
    Emergency Access Corridor" -- stable for 81 turns -- into the plenum's
    own name, then into the name of every room after it. `region` is the
    engine's fact for "same place": same region as the room just left, and
    a venue-level label stays."""
    ctx = _ctx(monkeypatch, player="Aurel Voss")
    prev = {"rooms": {"riser_13": {"name": "Upper Service-Core Riser 13",
                                   "region": "sub_level_5a"}},
            "positions": {"Aurel Voss": "riser_13"},
            "location": "Site-17, Lower Sector Emergency Access Corridor"}
    sc = {"rooms": {"riser_13": {"name": "Upper Service-Core Riser 13",
                                 "region": "sub_level_5a"},
                    "plenum_13": {"name": "Upper Service-Core Plenum Chase 13",
                                  "region": "sub_level_5a"}},
          "positions": {"Aurel Voss": "plenum_13"},
          "location": "Site-17, Lower Sector Emergency Access Corridor"}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "Site-17, Lower Sector Emergency Access Corridor"

    # A different region is a different place, and the label moves (DW-1).
    sc2 = {"rooms": {"riser_13": {"name": "Upper Service-Core Riser 13",
                                  "region": "sub_level_5a"},
                     "yard": {"name": "The Surface Yard",
                              "region": "surface"}},
           "positions": {"Aurel Voss": "yard"},
           "location": "Site-17, Lower Sector Emergency Access Corridor"}
    commit._refresh_relocated_location(sc2, prev, {}, ctx)
    assert sc2["location"] == "The Surface Yard"

    # And a Director that names the location this turn is always honoured.
    sc3 = {"rooms": sc["rooms"], "positions": {"Aurel Voss": "plenum_13"},
           "location": "Site-17, Lower Sector Emergency Access Corridor"}
    commit._refresh_relocated_location(
        sc3, prev, {"location": "Site-17, Upper Service Core"}, ctx)
    assert sc3["location"] == "Site-17, Upper Service Core"


# ---- TR-3: relocation into a PRE-EXISTING room (beam back aboard) ----

def test_location_refreshes_when_moving_back_to_an_existing_room(monkeypatch):
    """Beaming up from a planet surface returns the player to the ship's
    transporter room -- a room that existed before this turn. The DW-1 guard
    only refreshed for NEWLY-MINTED rooms, so the label stayed on the surface
    while every position was aboard. The stale label names the room the player
    just left, so it must move with them."""
    ctx = _ctx(monkeypatch, player="Commander Reyes")
    prev = {"rooms": {"ship_transporter": {"name": "Transporter Room"},
                      "surface": {"name": "Sigma Draconis VII — Surface"}},
            "positions": {"Commander Reyes": "surface"},
            "location": "Sigma Draconis VII — Surface"}
    sc = {"rooms": {"ship_transporter": {"name": "Transporter Room"},
                    "surface": {"name": "Sigma Draconis VII — Surface"}},
          "positions": {"Commander Reyes": "ship_transporter"},
          "location": "Sigma Draconis VII — Surface"}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "Transporter Room"


def test_in_venue_room_move_with_a_named_departed_room_still_refreshes(monkeypatch):
    """Distinct from the venue-label case: if the label literally equals the
    NAME of the room being left, it is a room label (not a venue label) and is
    stale -- it follows the player even between pre-existing rooms."""
    ctx = _ctx(monkeypatch, player="Commander Reyes")
    prev = {"rooms": {"bridge": {"name": "Bridge"}, "ready_room": {"name": "Ready Room"}},
            "positions": {"Commander Reyes": "bridge"}, "location": "Bridge"}
    sc = {"rooms": {"bridge": {"name": "Bridge"}, "ready_room": {"name": "Ready Room"}},
          "positions": {"Commander Reyes": "ready_room"}, "location": "Bridge"}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "Ready Room"


# ---- scene.description: the label's prose sibling, frozen since turn 0 ----

def test_description_refreshes_with_the_location(monkeypatch):
    """scene.description was only ever written from director_establish --
    i.e. once, on the opening turn. Live (Elevator Adventure branch 41) it
    still described the surface elevator bay 92 turns later, with the party
    in a sub-basement chamber. It follows the same trigger as the label."""
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bay": {"name": "Elevator Bay", "desc": "A quiet bay."}},
            "location": "Elevator Bay",
            "description": "A quiet elevator bay, two steady blue lights."}
    sc = {"rooms": {"bay": {"name": "Elevator Bay", "desc": "A quiet bay."},
                    "chamber": {"name": "West Chamber",
                                "desc": "A low, sealed concrete chamber."}},
          "positions": {"Ellie Marsh": "chamber"},
          "location": "Elevator Bay",
          "description": "A quiet elevator bay, two steady blue lights."}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["location"] == "West Chamber"
    assert sc["description"] == "A low, sealed concrete chamber."


def test_director_named_description_is_preferred(monkeypatch):
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bay": {"name": "Elevator Bay"}}, "location": "Elevator Bay",
            "description": "A quiet elevator bay."}
    sc = {"rooms": {"bay": {"name": "Elevator Bay"},
                    "chamber": {"name": "West Chamber", "desc": "Sealed concrete."}},
          "positions": {"Ellie Marsh": "chamber"}, "location": "Elevator Bay",
          "description": "A quiet elevator bay."}
    commit._refresh_relocated_location(
        sc, prev, {"description": "Deep beneath Site-17."}, ctx)
    assert sc["description"] == "Deep beneath Site-17."


def test_description_is_untouched_without_a_relocation(monkeypatch):
    ctx = _ctx(monkeypatch)
    prev = {"rooms": {"bar": {"name": "Bar", "desc": "A bar."},
                      "kitchen": {"name": "Kitchen", "desc": "A kitchen."}},
            "location": "The Old Anchor", "description": "A dockside pub."}
    sc = {"rooms": {"bar": {"name": "Bar", "desc": "A bar."},
                    "kitchen": {"name": "Kitchen", "desc": "A kitchen."}},
          "positions": {"Ellie Marsh": "kitchen"},
          "location": "The Old Anchor", "description": "A dockside pub."}
    commit._refresh_relocated_location(sc, prev, {}, ctx)
    assert sc["description"] == "A dockside pub."
