"""A state_diff field name can never become an entity.

Chat 80 turn 1: the objects specialist's `entities` map came back carrying
its own sibling field names as keys -- `remove_entities`, `inventory_ops`,
`artifact_ops`, `destruction`, `notes`, `resolved_events` -- each holding a
verbatim copy of the Interview Chair's def. The resolve path has hoisted
misplaced siblings out of `entities` for ages, but the specialist path never
did, so six chair clones passed validation as entities, merged into the
scene, and sat in `scene.entities` as furniture for the rest of the story.

Three layers each hold the line: validation hoists (or drops debris),
the scene merge refuses and HEALS (so a live story needs no migration),
and get_scene tolerates a stored scene that still carries the keys.

The specialist-path hoist and its two tests went with the causal hands on
2026-09-27. The encoder's patch path does not hoist (UNBUILT_PIPELINE §1.1),
so today the merge and get_scene layers are what stand.
"""

from __future__ import annotations

from llm.schemas import NON_ENTITY_FIELD_KEYS, preprocess_llm_output
from world.spatial import merge_scene_with_diff

_CHAIR = {
    "name": "Interview Chair", "kind": "furniture",
    "description": "A heavy metal chair bolted to the floor.",
    "aliases": [], "portable": False,
    "state": {"restraints": "engaged at wrists and ankles"},
}


def test_resolve_diff_hoists_objects_channels_too():
    """artifact_ops and destruction are StateDiff siblings like any other and
    were missing from the resolve-path hoist list."""
    out = preprocess_llm_output("director_resolve", {
        "resolved_event": "x",
        "state_diff": {
            "entities": {
                "interview_chair": dict(_CHAIR),
                "artifact_ops": [],
                "destruction": None,
            },
        },
    })
    assert set(out["state_diff"]["entities"]) == {"interview_chair"}


def test_merge_refuses_field_named_entities_and_heals_standing_ones():
    """The merge is the floor: an incoming diff whose entities map still
    carries sibling-named keys does not mint them, and a scene ALREADY
    holding them (chat 80's six chair clones) is healed by the next merge --
    the merged blob is what commits, so the live story needs no migration."""
    scene = {
        "rooms": {"cell": {"name": "Cell"}},
        "entities": {
            "interview_chair": dict(_CHAIR),
            "remove_entities": dict(_CHAIR),
            "inventory_ops": dict(_CHAIR),
            "notes": dict(_CHAIR),
        },
        "positions": {"interview_chair": "cell", "notes": "cell"},
    }
    diff = {"entities": {"artifact_ops": dict(_CHAIR),
                         "folder": {"name": "Folder", "kind": "document"}}}
    merged = merge_scene_with_diff(scene, diff)
    assert set(merged["entities"]) & NON_ENTITY_FIELD_KEYS == set()
    assert "interview_chair" in merged["entities"]
    assert "folder" in merged["entities"]
    assert "notes" not in merged["positions"]
    assert merged["positions"]["interview_chair"] == "cell"


def test_get_scene_reads_stored_junk_keys_out(temp_db):
    """Every reader between now and the next commit goes through the stored
    blob; get_scene must not hand them six phantom chairs."""
    from story.scene import get_scene

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", 0.0),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "y",
        "rooms": {}, "attire": {}, "overlays": {},
        "entities": {"interview_chair": dict(_CHAIR),
                     "destruction": dict(_CHAIR),
                     "resolved_events": dict(_CHAIR)},
        "positions": {"interview_chair": "cell", "destruction": "cell"},
    })
    sc = get_scene(chat_id)
    assert set(sc["entities"]) == {"interview_chair"}
    assert set(sc["positions"]) == {"interview_chair"}


def test_non_entity_field_keys_cover_every_declared_sibling():
    """The vocabulary is computed from the models' own declarations, so a
    channel added later is covered without anyone remembering this list. The
    six measured keys are the regression anchor."""
    for key in ("remove_entities", "inventory_ops", "artifact_ops",
                "destruction", "notes", "resolved_events"):
        assert key in NON_ENTITY_FIELD_KEYS

