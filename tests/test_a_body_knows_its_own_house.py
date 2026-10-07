"""A background voice knows its own house, and is not beside itself.

Found in play on 2026-10-06 (scratch story 165, turn 4582). Three voices in
one taproom, all of them the inn's own people:

* a house hand told the player "Keeper's not here. Hasn't been, since before
  noon." with the keeper at his elbow, holding the guild's letter. His payload
  listed the keeper as "the old wiry member of inn with ink on the fingers":
  nothing told him that man was his keeper. The keeper's `role_hint` was
  "member of inn" because `roles` are the posts a body stands WATCH on now,
  and a keeper between watches, behind his own bar, had none;
* every voice was listed in its own `present_others` -- the self-filter
  compared its NAME against these appearance LABELS -- so the heavy-armed hand
  was shown "the ... house hand with a burn across the wrist" beside himself.

A charter body's colleagues in the room are named with their post (what
working beside them gives anyone); a body off watch at its own post's place is
taken for its post; and nobody is listed beside themself.
"""

import types

import agents.background as background
from tests.test_a_charter_body_speaks_before_the_director_resolves import _chat
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import background_presence_records, save_registry


def _ctx():
    return types.SimpleNamespace(
        chat={"id": 1, "persona_id": None},
        turn=types.SimpleNamespace(idx=4, frame_id=None), cast=[],
        get=lambda k, d=None: d)


SCENE = {"rooms": {"taproom": {}}, "positions": {}}
INN = [{"charter": "inn", "body": "house_hand:0002"}]


def test_a_colleague_is_named_with_his_post_and_nobody_is_beside_himself(
        monkeypatch):
    monkeypatch.setattr(background, "_room_presences_in", lambda ctx, sc, room: [
        ("Niboold Moorelcroft", "the heavy-armed house hand",
         {"charter_refs": INN, "sketch": {"role_hint": "House Hand"}}),
        ("Fetoard Hollelwick", "the old wiry keeper",
         {"charter_refs": [{"charter": "inn", "body": "keeper:0001"}],
          "sketch": {"role_hint": "keeper"}}),
        ("Wattaand Maroford", "a stoop-shouldered warden",
         {"charter_refs": [{"charter": "walks", "body": "warden:0001"}]}),
    ])
    me = ("Niboold Moorelcroft", {"charter_refs": INN})
    others = background._present_others(_ctx(), SCENE, "taproom", asker=me)
    assert others == ["Fetoard Hollelwick (keeper)", "a stoop-shouldered warden"]


def test_without_an_asker_the_list_is_as_it_was(monkeypatch):
    monkeypatch.setattr(background, "_room_presences_in", lambda ctx, sc, room: [
        ("Fetoard Hollelwick", "the old wiry keeper",
         {"charter_refs": [{"charter": "inn", "body": "keeper:0001"}]})])
    assert background._present_others(_ctx(), SCENE, "taproom") == [
        "the old wiry keeper"]


def _inn():
    charter = normalize_charter({
        "key": "inn",
        "upkeeps": {"house": {"place": "taproom", "level": 0.8, "floor": 0.3,
                              "drift_per_hour": 0.01, "service_per_hour": 0.1}},
        "posts": {"keeper": {"place": "taproom", "serves": ["house"]},
                  "ostler": {"place": "yard", "serves": ["house"]}},
        "bodies": {"keeper:0001": {"place": "taproom", "name": "Fetoard Hollelwick",
                                   "home_post": "keeper"},
                   "ostler:0001": {"place": "taproom", "name": "Watisett Bray",
                                   "home_post": "ostler"}},
        "priority": ["house"],
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    charter["watch"] = {}
    return charter


def test_off_watch_at_his_own_post_he_is_taken_for_his_post(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn()})
    records = background_presence_records(cid)
    hints = {name: r["sketch"]["role_hint"] for name, r in records.items()}
    assert hints["Fetoard Hollelwick"] == "keeper", "behind his own bar"
    assert hints["Watisett Bray"].startswith("member of"), (
        "an ostler drinking in the taproom is only of the house")


def test_both_packs_say_an_unanswerable_question_is_not_answered():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "language_packs"
    en = (root / "en/cards/system_prompts/prompts/background_react.txt").read_text(
        encoding="utf-8")
    ja = (root / "ja/cards/system_prompts/prompts/background_react.txt").read_text(
        encoding="utf-8")
    assert "never supply the fact" in en
    assert "事実を補ってはいけません" in ja
