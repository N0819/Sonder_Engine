"""One background voice is handed one Charter body's slice, never two.

`presence_view` resolved its body by display name across EVERY charter and
returned up to two, so two institutions each holding an "Ada Fenn" standing
in one square gave one voice both heads: "INN-ADA'S PRIVATE: the reeve
skimmed the granary" and "MILL-ADA'S PRIVATE: I set the kiln fire myself"
(audit world_charter_core F1, reproduced). Two people do not share a head.
The presence record's exact `charter_refs` resolve it, as they already do for
`apply_presence_conduct` and `promotion_bundle`; a name that matches more
than one body names none."""
import time

from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import presence_view, save_registry


def _house(key, body_key, secret):
    state = normalize_charter({
        "key": key, "upkeeps": {}, "posts": {},
        "bodies": {body_key: {"place": "square", "name": "Ada Fenn"}}})
    state["roster"] = seed_roster(state["bodies"])
    state["needs"] = seed_needs(state["bodies"])
    news = "news:upkeep_out_of_band:%s@1.0000" % key
    state["minds"] = {body_key: {news: {
        "kind": "news", "body": news, "event_kind": "upkeep_out_of_band",
        "about": key, "claim_text": secret, "place": "square",
        "happened_at": 1.0, "strength": 1.0, "as_of_hours": 1.0,
        "heard_from": None}}}
    return state


def _story(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Square", "", time.time()))
    save_registry(cid, {"items": {
        "inn": {"state": _house("inn", "tapster:0001",
                                "INN-ADA'S PRIVATE")},
        "mill": {"state": _house("mill", "miller:0001",
                                 "MILL-ADA'S PRIVATE")}}})
    return cid


def test_a_shared_name_without_refs_reaches_no_head(temp_db):
    cid = _story(temp_db)
    view = presence_view(cid, "square", "Ada Fenn")
    assert len(view) <= 1
    text = str(view)
    assert not ("INN-ADA" in text and "MILL-ADA" in text)
    assert view == []


def test_the_records_refs_reach_exactly_its_own_head(temp_db):
    cid = _story(temp_db)
    view = presence_view(cid, "square", "Ada Fenn",
                         refs=[{"charter": "mill", "body": "miller:0001"}])
    assert [(row["charter"], row["body"]) for row in view] == [
        ("mill", "miller:0001")]
    assert "MILL-ADA" in str(view) and "INN-ADA" not in str(view)
