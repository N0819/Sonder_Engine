"""Names, titles and colours for institution-scale Charter populations."""

from world.charter import normalize_charter
from world.charter_identity import display_name, identity_aliases, identity_seed


PROFILE = {
    "seed": "aldermere",
    "given": [f"Given{i:02d}" for i in range(48)],
    "family": [f"House{i:02d}" for i in range(48)],
    "name_format": "{given} {family}",
    "formal_format": "{title} {name}",
    "titles": {
        "ranks": {"captain": "Captain"},
        "posts": {"healer_watch": "Sister"},
    },
}


def _population(count=1000):
    return {
        "key": "aldermere",
        "naming": PROFILE,
        "bodies": {
            f"body-{i:04d}": {"place": "square", "competence": {}}
            for i in range(count)
        },
    }


def test_a_thousand_bodies_receive_unique_names_without_a_model_call():
    state = normalize_charter(_population())
    names = [body["name"] for body in state["bodies"].values()]
    assert len(names) == 1000
    assert len(set(names)) == 1000


def test_normalization_and_reload_never_regenerate_a_name():
    first = normalize_charter(_population(80))
    second = normalize_charter(first)
    assert {k: v["name"] for k, v in first["bodies"].items()} == {
        k: v["name"] for k, v in second["bodies"].items()}


def test_editing_the_profile_changes_only_bodies_not_yet_named():
    first = normalize_charter(_population(20))
    old = {k: v["name"] for k, v in first["bodies"].items()}
    first["naming"] = {
        **PROFILE,
        "seed": "a-new-authorial-style",
        "given": ["Newa", "Newen", "Newor"],
        "family": ["North", "South", "West"],
    }
    first["bodies"]["new-arrival"] = {
        "place": "square", "competence": {}}

    after = normalize_charter(first)

    assert {k: after["bodies"][k]["name"] for k in old} == old
    assert after["bodies"]["new-arrival"]["name"].startswith("New")


def test_inserting_a_body_does_not_rename_the_existing_population():
    first = normalize_charter(_population(50))
    old = {k: v["name"] for k, v in first["bodies"].items()}
    first["bodies"]["body-0000a"] = {"place": "square"}
    after = normalize_charter(first)
    assert {k: after["bodies"][k]["name"] for k in old} == old


def test_rank_and_post_titles_are_presentation_not_identity():
    state = normalize_charter({
        "key": "watch",
        "naming": PROFILE,
        "posts": {"healer_watch": {"place": "ward", "serves": []}},
        "bodies": {
            "ysra": {"name": "Ysra Vale", "rank": "captain"},
            "iven": {"name": "Iven", "place": "ward"},
        },
        "watch": {"healer_watch": "iven"},
    })
    assert display_name(
        state["bodies"]["ysra"], (), state["naming"]) == "Captain Ysra Vale"
    assert display_name(
        state["bodies"]["iven"], ("healer_watch",),
        state["naming"]) == "Sister Iven"
    assert state["bodies"]["ysra"]["name"] == "Ysra Vale"


def test_dialogue_identity_seed_ignores_names_and_titles():
    before = identity_seed("watch", "ysra")
    after = identity_seed("watch", "ysra")
    assert before == after == "charter:watch:ysra"


def test_all_authored_title_forms_remain_aliases_of_the_personal_name():
    body = {"name": "Ysra Vale", "rank": "captain"}
    assert identity_aliases(body, (), PROFILE) == [
        "Ysra Vale", "Captain Ysra Vale", "Sister Ysra Vale"]


def test_no_profile_preserves_the_genre_agnostic_key_fallback():
    state = normalize_charter({"key": "aliens", "bodies": {"x9": {}}})
    assert state["bodies"]["x9"]["name"] == "x9"
