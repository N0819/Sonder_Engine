"""Region visibility as a DERIVED, per-observer answer -- step 2 of
docs/DESIGN_REGION_VISIBILITY.md.

The scar this shape exists to avoid repeating: `wearing`/`state`/`regions`
are three representations of one wardrobe and they drifted until every writer
outside commit was made to call `rederive_entry`. A stored per-region
`visible` flag would be a fourth representation with the same failure mode,
so visibility is computed at read time from coverage plus the scene, and
these tests exercise the read -- nothing here asserts anything was written.

Deliberately database-free: pure dicts in, a dict out.
"""

from __future__ import annotations

from agents.common import observer_body_regions, region_visibility


# One room with beared anchors, so facing can put a body in an observer's
# rear arc -- the same fixture shape tests/test_stations.py uses.
TAPROOM = {
    "taproom": {
        "name": "the Taproom", "size": "large",
        "anchors": {
            "bar": {"desc": "the long oak bar", "dir": "n"},
            "door": {"desc": "the front door", "dir": "e"},
        },
    },
}


def _scene(positions, attire=None, **extra):
    sc = {"rooms": dict(TAPROOM), "positions": dict(positions),
          "attire": dict(attire or {})}
    sc.update(extra)
    return sc


MIRA = {"wearing": ["a linen shirt"],
        "regions": {"torso": {"garments": [{"name": "a linen shirt",
                                            "state": "worn"}]}}}


def _concealed(view):
    return [r for r, e in view.items() if e["visibility"] == "concealed"]


# --- the coverage half, per observer ----------------------------------------

def test_a_covered_region_is_concealed_by_the_garment_that_covers_it():
    """The promotion itself: what `covered_regions` said binarily now answers
    "and by what", so a caller no longer re-derives attribution from the raw
    ledger -- which is how second spellings of one predicate start."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": MIRA})
    view = region_visibility(sc, "Watcher", "Mira")
    assert view["torso"] == {"visibility": "concealed",
                             "by": {"garments": ["a linen shirt"]}}
    assert view["hands"] == {"visibility": "overt"}
    assert set(view) == {"head", "torso", "arms", "hands", "waist", "groin",
                         "legs", "feet"}


def test_an_attaching_ornament_conceals_nothing():
    """A hair clip is present WITHOUT covering -- the reason `attaches`
    exists. Folding presence into coverage here would report a concealed head
    on the strength of a hair pin."""
    entry = {"regions": {"head": {"garments": [
        {"name": "a hair clip", "attaches": True}]}}}
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": entry})
    assert region_visibility(sc, "Watcher", "Mira")["head"] == {
        "visibility": "overt"}


def test_a_legacy_flat_wardrobe_answers_without_a_backfill():
    """39 of 56 live chats store attire with no region breakdown at all; they
    are migrated on read by `rederive_entry`, so the derived answer must work
    from a bare `wearing` list or most existing stories would report every
    body overt everywhere."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"},
                {"Mira": {"wearing": ["a kimono"]}})
    view = region_visibility(sc, "Watcher", "Mira")
    for region in ("torso", "arms", "waist", "groin", "legs"):
        assert view[region]["by"] == {"garments": ["a kimono"]}
    assert view["feet"] == {"visibility": "overt"}


def test_a_body_with_no_attire_entry_is_simply_overt():
    """An unmodelled wardrobe conceals nothing. Refusing to answer for a body
    the ledger never dressed would make every unregistered presence
    invisible, which is a different (and wrong) claim."""
    sc = _scene({"Watcher": "taproom", "Stranger": "taproom"})
    view = region_visibility(sc, "Watcher", "Stranger")
    assert _concealed(view) == []


# --- the observer half ------------------------------------------------------

def test_two_observers_of_one_body_get_different_answers():
    """The point of borrowing `conceal_from`'s per-observer scoping rather
    than minting a body-level flag: one flag for the scene would let the
    observer a body faces and the observer at whose back it stands read the
    same answer. Mira is at the door (east); Ahead faces her, Turned faces
    west and has her in the rear arc -- the blind spot `behind_sources`
    already enforces for acts."""
    sc = _scene(
        {"Ahead": "taproom", "Turned": "taproom", "Mira": "taproom"},
        {"Mira": MIRA},
        stations={"Mira": {"at": "door"}},
        orientation={"Ahead": {"facing": "e"}, "Turned": {"facing": "w"}})
    facing = region_visibility(sc, "Ahead", "Mira")
    assert facing["torso"]["by"] == {"garments": ["a linen shirt"]}
    assert facing["hands"] == {"visibility": "overt"}
    behind = region_visibility(sc, "Turned", "Mira")
    assert _concealed(behind) == list(behind)   # every region
    assert behind["hands"]["by"] == {"vantage": ["behind the observer"]}


def test_no_facing_gates_nothing():
    """FOV fails open, exactly as `entity_arc` documents: with no basis for
    an arc, a bare wardrobe answer must come back rather than a scene-wide
    concealment nobody authored."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": MIRA},
                stations={"Mira": {"at": "door"}})
    assert _concealed(region_visibility(sc, "Watcher", "Mira")) == ["torso"]


def test_containment_conceals_every_region_and_names_the_holder():
    """`spatial.hiding_holders_of` is the required read for "is this body
    shut inside something" -- reading `scene['contained']` directly misses
    the parented-interior form, which is how a live chat once had an occupant
    visible to the very entity enclosing them. Once enclosed, the garment
    answer must not show through: the observer cannot see the shirt either."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": MIRA},
                contained={"Mira": {"in": "the wardrobe", "mode": "hidden"}})
    view = region_visibility(sc, "Watcher", "Mira")
    assert _concealed(view) == list(view)
    assert view["torso"]["by"] == {"containment": ["the wardrobe"]}


def test_co_occupants_of_one_enclosure_see_each_other_normally():
    """Two bodies in one enclosure are simply in the same place -- the wall
    around them is around them both. Concealing them from each other would
    repeat the symmetric-flag mistake the three-direction containment
    relations exist to prevent."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": MIRA},
                contained={"Mira": {"in": "the wardrobe", "mode": "hidden"},
                           "Watcher": {"in": "the wardrobe", "mode": "hidden"}})
    assert _concealed(region_visibility(sc, "Watcher", "Mira")) == ["torso"]


def test_an_enclosed_observer_is_concealed_from_too():
    """Being shut inside something blocks the view out exactly as it blocks
    the view in -- the direction that is easier to forget. The concealer
    named is the enclosure doing the concealing: the observer's own."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": MIRA},
                contained={"Watcher": {"in": "the crate", "mode": "shut"}})
    view = region_visibility(sc, "Watcher", "Mira")
    assert _concealed(view) == list(view)
    assert view["torso"]["by"] == {"containment": ["the crate"]}


def test_darkness_conceals_and_dim_light_is_a_silhouette():
    """Sight failing is spatial's composed answer (light, barriers,
    containment), not re-derived here -- so a dark room conceals a body's
    regions exactly as it conceals the body, and dim light shows outline but
    not what is worn or bare, the same reading `_co_present_company` gives an
    indistinct figure."""
    dark = {"cellar": {"name": "the Cellar", "light": "dark"}}
    sc = {"rooms": dark, "positions": {"Watcher": "cellar", "Mira": "cellar"},
          "attire": {"Mira": dict(MIRA)}}
    view = region_visibility(sc, "Watcher", "Mira")
    assert _concealed(view) == list(view)
    assert view["torso"]["by"] == {"vantage": ["out of sight"]}
    sc["rooms"]["cellar"]["light"] = "dim"
    assert region_visibility(sc, "Watcher", "Mira")["torso"]["by"] == {
        "vantage": ["seen only in silhouette"]}


def test_a_body_is_never_concealed_from_itself_by_vantage_or_containment():
    """A perceiver is never sealed from themselves and never stands in their
    own blind spot -- the self-knowledge floor the enclosure work already
    established. Their own garments still conceal their regions, because
    covered is covered whoever looks."""
    dark = {"cellar": {"name": "the Cellar", "light": "dark"}}
    sc = {"rooms": dark, "positions": {"Mira": "cellar"},
          "attire": {"Mira": dict(MIRA)},
          "contained": {"Mira": {"in": "the crate", "mode": "shut"}}}
    view = region_visibility(sc, "Mira", "Mira")
    assert _concealed(view) == ["torso"]
    assert view["torso"]["by"] == {"garments": ["a linen shirt"]}


def test_an_unplaceable_observer_sees_nothing():
    """Safe-closed, like every other spatial query: `unknown` must look like
    distance, never like a sight line nobody established."""
    sc = _scene({"Mira": "taproom"}, {"Mira": MIRA})
    view = region_visibility(sc, "Nowhere Man", "Mira")
    assert _concealed(view) == list(view)
    assert view["torso"]["by"] == {"vantage": ["out of sight"]}


def test_the_attire_ledger_key_is_matched_tolerantly():
    """One being, one name: five separate defects in this module's history
    were a bare `==` between two spellings of one being. The ledger is keyed
    by display name; a caller passing another casing must not get a naked
    body."""
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": MIRA})
    assert _concealed(region_visibility(sc, "Watcher", "mira")) == ["torso"]


def test_observer_projection_delivers_exposed_authored_body_detail(temp_db):
    """The production consumer: an authored region description reaches a
    legitimate observer only after that region has actually been uncovered."""
    temp_db.set_setting("attire_beneath", "1")
    entry = {"regions": {
        "torso": {
            "garments": [{"name": "linen shirt", "state": "removed"}],
            "beneath": "a distinctive silver scar across the ribs",
        },
        "waist": {
            "garments": [{"name": "wool sash", "state": "worn",
                          "description": "coarse blue wool"}],
            "beneath": "a hidden tattoo no observer has earned",
        },
    }}
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": entry})

    projected = observer_body_regions(
        sc, "Watcher", {"Mira": "the traveller"})

    assert projected[0]["body"] == "the traveller"
    assert "distinctive silver scar" in projected[0]["regions"]["torso"]
    assert "coarse blue wool" in projected[0]["regions"]["waist"]
    assert "hidden tattoo" not in str(projected)
    assert "Mira" not in str(projected), "canonical identity leaked in the new channel"


def test_partial_torso_projection_reveals_midriff_but_not_chest(temp_db):
    """A rucked top is still worn. Its structured zone coverage exposes only
    the midriff; neither the coarse whole-torso fallback nor the covered chest
    description may cross the observer firewall."""
    temp_db.set_setting("attire_beneath", "1")
    entry = {"regions": {"torso": {
        "garments": [{
            "name": "fitted tank top", "state": "worn",
            "covered_zones": {"torso": ["chest"]},
        }],
        "beneath": "HOSTILE-WHOLE-TORSO-FALLBACK",
        "beneath_zones": {
            "chest": "HOSTILE-COVERED-CHEST-DETAIL",
            "midriff": "soft stomach and faded scrape scars across the ribs",
        },
    }}}
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": entry})

    projected = observer_body_regions(
        sc, "Watcher", {"Mira": "the traveller"})
    torso = projected[0]["regions"]["torso"]

    assert "chest: fitted tank top" in torso
    assert "midriff: bare" in torso
    assert "soft stomach" in torso
    assert "HOSTILE-WHOLE-TORSO-FALLBACK" not in torso
    assert "HOSTILE-COVERED-CHEST-DETAIL" not in torso


def test_partial_outer_garment_reveals_an_underlayer_not_skin(temp_db):
    temp_db.set_setting("attire_beneath", "1")
    entry = {"regions": {"torso": {
        "garments": [
            {"name": "rucked blouse", "state": "worn",
             "covered_zones": {"torso": ["chest"]}},
            {"name": "linen undershirt", "state": "worn"},
        ],
        "beneath_zones": {"midriff": "HOSTILE-SKIN-DETAIL"},
    }}}
    sc = _scene({"Watcher": "taproom", "Mira": "taproom"}, {"Mira": entry})

    torso = observer_body_regions(
        sc, "Watcher", {"Mira": "the traveller"})[0]["regions"]["torso"]

    assert "midriff: linen undershirt" in torso
    assert "HOSTILE-SKIN-DETAIL" not in torso


def test_observer_projection_withholds_body_detail_without_sight(temp_db):
    temp_db.set_setting("attire_beneath", "1")
    dark = {"cellar": {"name": "Cellar", "light": "dark"}}
    sc = {"rooms": dark,
          "positions": {"Watcher": "cellar", "Mira": "cellar"},
          "attire": {"Mira": {"regions": {"torso": {
              "garments": [{"name": "shirt", "state": "removed"}],
              "beneath": "a distinctive silver scar across the ribs",
          }}}}}

    assert observer_body_regions(
        sc, "Watcher", {"Mira": "the traveller"}) == []
