"""A body named by its own engine key, and a naming law that cannot mint,
are reported to the author rather than kept in silence.

`materialize_body_names` falls back to the body KEY when the law mints
nothing, and the key then counts as a name for ever: a law added later never
names `cook:0001`, and a law that addresses people by family name alone
(`{"family": [...], "name_format": "{family}"}`) mints nothing at all because
`generated_name_parts` returns "" without a given-name source --
`registry_warnings` said nothing in either case (audit world_charter_core
F14, reproduced). Renaming a key-named body is the owner's to rule on (a
generated name is materialised once); the notice is not."""
from world.charter import normalize_charter
from world.charter_runtime import normalize_registry, registry_warnings


def _house(naming=None, bodies=None):
    raw = {"key": "inn",
           "upkeeps": {"custom": {"place": "taproom", "level": 1.0,
                                  "floor": 0.2, "drift_per_hour": 0.0,
                                  "service_per_hour": 1.0}},
           "posts": {"cook": {"place": "taproom", "serves": ["custom"],
                              "requires": {}}},
           "bodies": bodies or {"cook:0001": {"place": "taproom"},
                                "cook:0002": {"place": "taproom"}}}
    if naming is not None:
        raw["naming"] = naming
    return normalize_charter(raw)


def test_bodies_named_by_their_keys_are_reported():
    state = _house()
    warnings = registry_warnings({"items": {"inn": {"state": state}}})
    assert any("cook:0001" in w and "key" in w for w in warnings), warnings


def test_a_family_only_law_that_mints_nothing_is_reported():
    state = _house(naming={"family": ["Varn", "Brack", "Tull"],
                           "name_format": "{family}"})
    warnings = registry_warnings({"items": {"inn": {"state": state}}})
    assert any("family" in w and "given" in w for w in warnings), warnings


def test_a_law_that_mints_is_not_reported():
    state = _house(naming={"given": ["Ada", "Bel", "Cal"],
                           "family": ["Varn", "Brack"],
                           "name_format": "{given} {family}"})
    warnings = registry_warnings({"items": {"inn": {"state": state}}})
    assert not any("named by" in w or "cannot mint" in w for w in warnings), \
        warnings
