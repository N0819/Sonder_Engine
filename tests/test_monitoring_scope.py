"""Regression tests for the monitoring subtree walk and perception
scope-by-nesting-depth (movement/space Phase 1, item 5).

- memory.monitoring_subtree: read-only "what's aboard/nested here right
  now" over parent_id (belongs-to) + currently_within (is-at), joined with
  scene positions for occupants. Reporting only -- never a perception
  input.
- spatial.ambient_scope + the coarse perception filter: information scoped
  to an ancestor location must not reach an observer sealed inside a
  nested interior (the port must not leak into a sealed elevator/van);
  it flows back in when the connection is actually open.
"""

import time

from memory import monitoring_subtree
from spatial import ambient_scope, apply_transit_dock_edges


def _nested_scene(van_phase="docked", van_hatch="open"):
    scene = {
        "location": "Port Kael",
        "rooms": {
            "harbor": {"name": "Harbor", "adjacent": []},
            "vehicle_deck": {"name": "Vehicle Deck", "parent_entity": "ferry",
                            "adjacent": []},
            "van_interior": {"name": "Van Interior", "parent_entity": "van",
                             "adjacent": []},
        },
        "positions": {"ferry": "harbor", "van": "vehicle_deck",
                      "Alex": "van_interior", "Mara": "vehicle_deck"},
        "entities": {
            "ferry": {"name": "The Ferry", "kind": "vehicle",
                      "interior_rooms": ["vehicle_deck"],
                      "state": {"transit": {"phase": "docked",
                                            "hatch": "open"}}},
            "van": {"name": "The Van", "kind": "vehicle",
                    "interior_rooms": ["van_interior"],
                    "state": {"transit": {"phase": van_phase,
                                          "hatch": van_hatch}}},
        },
    }
    apply_transit_dock_edges(scene)
    return scene


# ---- ambient scope -------------------------------------------------------

def test_sealed_nested_interior_is_closed_to_the_world():
    scene = _nested_scene(van_phase="sealed")
    scope, open_to_world = ambient_scope(scene, "van_interior")
    assert scope == {"van_interior"}
    assert open_to_world is False


def test_open_hatches_reach_the_world_through_both_hops():
    scene = _nested_scene(van_phase="docked", van_hatch="open")
    scope, open_to_world = ambient_scope(scene, "van_interior")
    assert {"van_interior", "vehicle_deck", "harbor"} <= scope
    assert open_to_world is True


def test_plain_world_room_is_always_open():
    scene = _nested_scene()
    _, open_to_world = ambient_scope(scene, "harbor")
    assert open_to_world is True


# ---- coarse staged-lore filter ------------------------------------------

class _StubCtx:
    def __init__(self, staged):
        self._staged = staged

    def get(self, key, default=None):
        if key == "mapping_stage":
            return {"staged_lore": self._staged, "relevant_lore": []}
        return default


def test_ancestor_scoped_lore_is_filtered_for_sealed_observer():
    from agents.common import _room_notes_from_lore

    staged = [{
        "keys": "van_interior, port_kael",
        "content": "Gulls wheel over Port Kael; the harbor smells of tar.",
        "category": "location",
    }]
    ctx = _StubCtx(staged)

    sealed = _nested_scene(van_phase="sealed")
    assert _room_notes_from_lore("van_interior", ctx, sealed) == "", \
        "port ambience must not leak into the sealed van"

    open_scene = _nested_scene(van_phase="docked", van_hatch="open")
    assert "Port Kael" in _room_notes_from_lore(
        "van_interior", ctx, open_scene)


def test_own_room_lore_still_reaches_the_sealed_observer():
    from agents.common import _room_notes_from_lore

    staged = [{
        "keys": "van_interior",
        "content": "The van's cargo netting sways overhead.",
        "category": "layout",
    }]
    ctx = _StubCtx(staged)
    sealed = _nested_scene(van_phase="sealed")
    assert "cargo netting" in _room_notes_from_lore(
        "van_interior", ctx, sealed)


def test_perception_payload_scopes_ambient_location_by_nesting():
    from agents.perception import _ambient_location_for

    sealed = _nested_scene(van_phase="sealed")
    label = _ambient_location_for(sealed, "van_interior")
    assert "Port Kael" not in str(label), \
        "the outer location's name must not ride into a sealed interior"
    assert "The Van" in str(label)

    open_scene = _nested_scene(van_phase="docked", van_hatch="open")
    assert _ambient_location_for(open_scene, "van_interior") == "Port Kael"
    assert _ambient_location_for(open_scene, "harbor") == "Port Kael"


# ---- monitoring subtree walk --------------------------------------------

def _make_books(db):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    port = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,scope_location_id) "
        "VALUES(?,?,?,?)",
        ("Port Kael", chat_id, "location", "harbor"),
    )
    ferry = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id) "
        "VALUES(?,?,?,?)",
        ("The Ferry", chat_id, "vehicle", "ferry"),
    )
    van = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id) "
        "VALUES(?,?,?,?)",
        ("The Van", chat_id, "vehicle", "van"),
    )
    crew_log = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) "
        "VALUES(?,?,?,?)",
        ("Crew Log", chat_id, "general", ferry),
    )
    return chat_id, port, ferry, van, crew_log


def test_monitoring_walk_enumerates_nested_contents(temp_db):
    import commit

    chat_id, port, ferry, van, crew_log = _make_books(temp_db)
    scene = _nested_scene()
    # The live presence links are exactly what commit derives from
    # positions -- exercise the real writer rather than hand-inserting.
    commit.sync_anchored_books(chat_id, scene)

    tree = monitoring_subtree(chat_id, port, scene=scene)
    assert tree["id"] == port
    present = {n["name"]: n for n in tree["present"]}
    assert "The Ferry" in present, "the docked ferry is aboard the port"

    ferry_node = present["The Ferry"]
    assert ferry_node["rooms"] == ["vehicle_deck"]
    assert "Mara" in ferry_node["occupants"]
    assert "van" in ferry_node["occupants"], \
        "the parked van itself is aboard the ferry"
    # Canonical containment children (belongs-to) are reported separately.
    assert [c["name"] for c in ferry_node["children"]] == ["Crew Log"]

    van_node = {n["name"]: n for n in ferry_node["present"]}["The Van"]
    assert van_node["rooms"] == ["van_interior"]
    assert van_node["occupants"] == ["Alex"]


def test_monitoring_walk_is_cycle_safe(temp_db):
    from memory import add_lorebook_link

    chat_id, port, ferry, van, _ = _make_books(temp_db)
    add_lorebook_link(ferry, port, "currently_within")
    # A pathological inverse link must not hang the walk.
    add_lorebook_link(port, ferry, "currently_within")

    tree = monitoring_subtree(chat_id, port)
    assert tree is not None
