"""A featured resident the Charter Planner invented is an extra with a name.

Two callers seed a featured body. A registered character's card seeds it
`cast:<id>` and that character's own agent plays the body, so the background
stage must not voice it too (chat 95, 2026-08-28). The Charter Planner's brief
seeds it `authored:<hash>` and nobody plays it: the landlady, the minister and
the skipper the story asked the town to have. Reading every seed as a mind's
made those people invisible off screen in every story of the 2026-09-14
campaign -- no presence record, no figure, no voice -- while the extras the
institution grew around them were seen and spoken to.
"""

from world.charter_model import body_of_an_authored_mind
from world.charter_runtime import background_presence_records


def _charter(seed):
    return {"bindings": {}, "bodies": {
        "innkeeper:featured:abc": {"name": "Mother Pascoe", "place": "taproom",
                                   "resident_seed_id": seed}}}


def test_a_planner_authored_resident_is_not_a_mind():
    assert not body_of_an_authored_mind(_charter("authored:b9879afcbd"),
                                        "innkeeper:featured:abc")


def test_a_registered_characters_seat_still_is():
    assert body_of_an_authored_mind(_charter("cast:75"), "innkeeper:featured:abc")


def test_a_bound_body_is_a_mind_whatever_its_seed():
    charter = _charter("authored:b9879afcbd")
    charter["bindings"] = {"innkeeper:featured:abc": "Mother Pascoe"}
    assert body_of_an_authored_mind(charter, "innkeeper:featured:abc")


def test_the_landlady_presents_where_she_stands(temp_db, monkeypatch):
    import time
    from world.charter_runtime import save_registry
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Gull Stair", "", time.time()))
    registry = {"version": 1, "items": {"the_ship": {"state": {
        "key": "the_ship",
        "bodies": {
            "innkeeper:featured:abc": {"name": "Mother Pascoe", "place": "taproom",
                                       "berth": "taproom", "available": True,
                                       "resident_seed_id": "authored:b9879afcbd"},
            "inn_servant:0001": {"name": "Naniseth Carwarnor", "place": "taproom",
                                 "berth": "taproom", "available": True},
        },
        "posts": {"innkeeper": {"place": "taproom", "serves": []},
                  "inn_servant": {"place": "taproom", "serves": []}},
        "upkeeps": {}, "watch": {}, "roster": {}, "bindings": {},
    }}}}
    save_registry(cid, registry)
    records = background_presence_records(cid, places={"taproom"})
    assert "Mother Pascoe" in records
    assert "Naniseth Carwarnor" in records


def test_an_honorific_in_the_name_is_not_the_bodys_noun():
    """"Mrs Dacre" with `title: "Mrs"` composed "the elderly wiry miss" and a
    crowd of "mrs" (scratch play 2026-09-14, chat 9); the noun is the post's."""
    from world.charter_crowd import member_noun
    charter = {"bodies": {"lady_patroness:featured:1": {
        "name": "Mrs Dacre", "title": "Mrs", "home_post": "lady_patroness"}},
        "watch": {}, "naming": {}}
    assert member_noun(charter, "lady_patroness:featured:1") == "lady patroness"
    charter["bodies"]["skipper:featured:1"] = {"name": "Jory Trewin", "title": "Skipper",
                                               "home_post": "skipper"}
    assert member_noun(charter, "skipper:featured:1") == "skipper"
