"""Releasing a stale twin's placement rows must not rebind the spelling table.

`heal_unbound_twins` built its spelling table into `table`, then reused the
name for each placement ledger while releasing a stale twin -- so every entity
after the first released twin was looked up in the poses ledger (or raised on
a missing one). The commit wraps the call in `except Exception`, so the raise
silently skipped every later heal, every lease move and every release of the
beat; the lookup in the wrong ledger bound a lamp to a charter body as a
`person` (audit world_charter_behaviours F7, reproduced with the fixtures of
`tests/test_a_charter_body_is_leased_to_the_scene.py`)."""
from world.charter import normalize_charter
from world.charter_place import heal_unbound_twins


def _registry():
    inn = normalize_charter({
        "key": "inn",
        "upkeeps": {"custom": {"place": "taproom", "level": 1.0, "floor": 0.2,
                               "drift_per_hour": 0.0, "service_per_hour": 1.0}},
        "posts": {"keep": {"place": "taproom", "serves": ["custom"],
                           "requires": {"keep": 1}}},
        "bodies": {"tam": {"place": "taproom", "name": "Tam",
                           "competence": {"keep": 1}},
                   "pip": {"place": "taproom", "name": "Pip",
                           "competence": {"keep": 1}}},
        "priority": ["custom"],
    })
    return {"items": {"inn": {"state": inn}}}


def _scene(with_poses):
    # Entities iterate in insertion order: the stale twin FIRST, then an
    # unrelated thing, then a second twin of another body.
    sc = {"rooms": {"taproom": {"name": "Taproom", "adjacent": []},
                    "yard": {"name": "Yard", "adjacent": []}},
          "entities": {"a_tam": {"name": "Tam", "kind": "fixture"},
                       "lamp": {"name": "a lamp", "kind": "thing"},
                       "z_pip": {"name": "Pip", "kind": "fixture"}},
          "positions": {"a_tam": "yard", "lamp": "taproom", "z_pip": "yard"},
          "stations": {"a_tam": {"at": "bar"}},
          "orientation": {}}
    if with_poses:
        sc["poses"] = {"lamp": {"posture": "standing"}}
    standing = {"entities": {"a_tam": {"name": "Tam", "kind": "fixture"},
                             "z_pip": {"name": "Pip", "kind": "fixture"}}}
    return sc, standing


def test_a_scene_without_a_poses_ledger_heals_every_twin():
    sc, standing = _scene(with_poses=False)
    healed = heal_unbound_twins(_registry(), sc, standing=standing)
    assert sorted(h["entity_id"] for h in healed) == ["a_tam", "z_pip"]
    assert sc["entities"]["z_pip"]["charter_ref"] == {"charter": "inn",
                                                      "body": "pip"}


def test_a_thing_after_a_released_twin_is_never_bound():
    sc, standing = _scene(with_poses=True)
    healed = heal_unbound_twins(_registry(), sc, standing=standing)
    assert "lamp" not in [h["entity_id"] for h in healed]
    assert "charter_ref" not in sc["entities"]["lamp"]
    assert sc["entities"]["lamp"]["kind"] == "thing"
    assert sorted(h["entity_id"] for h in healed) == ["a_tam", "z_pip"]
