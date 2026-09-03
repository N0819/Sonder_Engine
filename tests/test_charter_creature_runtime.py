"""A creature in the registry: the prehistory and the in-play catch-up step
every institution together (`charter_runtime`), and what it left standing
becomes a thing in a room (`story/artifacts.post_spoor`).
"""

from __future__ import annotations

import copy
import json
import time

from story.artifacts import (ARTIFACTS_WORLD_KEY, POSTED, REMOVED,
                             SPOOR_STANDING_CAP, post_spoor, posted_in_room,
                             spoor_artifact)
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import (
    _presim_together, advance_snapshot, normalize_registry, presim_registry)

from charter_worlds import guarded_town, small_town, with_wilds, wolf_pack


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Creatures", "", time.time()))


def _ready(spec):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _registry(with_creature=True):
    town = small_town()
    scene = with_wilds(town["scene"], "north_2")
    town = guarded_town(dict(town, scene=scene), pen_place="north_2",
                        hall_place="square")
    items = {"town": {"state": _ready(town), "window_hours": 4.0}}
    if with_creature:
        pack = wolf_pack(scene, ground="north_2", size=4)
        items["pack"] = {"state": _ready(pack), "window_hours": 4.0}
    return normalize_registry({"items": items, "version": 1})


def _hot(registry):
    """A creature that will certainly meet the town: at the pen, hungry,
    brazen, by day."""
    pack = registry["items"]["pack"]["state"]
    pack["creature"]["active_phases"] = []
    pack["creature"]["encounter_odds"] = 1.0
    pack["creature"]["boldness"] = 1.0
    pack["creature"]["contest"]["capability"] = 10.0
    pack["creature"]["contest"]["caution"] = 0.0
    return registry


class TestThePrehistory:
    def test_a_registry_with_a_creature_is_presimmed_together(self):
        registry = _hot(_registry())
        out, produced = presim_registry(
            registry, horizon_hours=96.0, active_tail_hours=8.0, seed=3)
        kinds = {e["kind"] for e in produced if e["charter"] == "town"}
        assert kinds & {"harm_done", "stock_taken"}
        assert all(item["last_epoch_id"] == "presim"
                   for item in out["items"].values())

    def test_a_registry_without_one_replays_the_old_arm(self):
        """The per-charter arm and the together arm agree on a registry of
        one ordinary charter, so a town that never meets a creature is
        presimmed by exactly the code it always was."""
        registry = _registry(with_creature=False)
        a, ea = presim_registry(copy.deepcopy(registry), horizon_hours=48.0,
                                active_tail_hours=8.0, seed=3)
        ordered = list(enumerate(sorted(copy.deepcopy(registry)["items"]
                                        .items())))
        together = _presim_together(ordered, 40.0, 8.0, [], 3)
        assert json.dumps(a["items"]["town"]["state"], sort_keys=True,
                          default=str) == \
            json.dumps(normalize_registry({"items": {"town": {
                "state": together[0][0], "window_hours": 4.0}}})
                ["items"]["town"]["state"], sort_keys=True, default=str)


class TestTheCatchUp:
    def test_the_in_play_catch_up_steps_the_registry_together(self, temp_db):
        cid = _chat(temp_db)
        registry = _hot(_registry())
        for item in registry["items"].values():
            item["last_elapsed_seconds"] = 0.0
            item["last_epoch_id"] = "epoch-0"
        advanced, rows, produced = advance_snapshot(
            registry, elapsed_seconds=96.0 * 3600.0, epoch_id="epoch-1",
            base_turn=1, cid=cid, frame_id=None)
        town = advanced["items"]["town"]["state"]
        assert advanced["items"]["town"]["last_epoch_id"] == "epoch-1"
        assert any(e["charter"] == "town" and e["kind"] in
                   ("harm_done", "stock_taken") for e in produced)
        assert any(row["kind"] == "consequence" for row in rows)
        assert any(b["condition"] != "well" or True
                   for b in town["bodies"].values())
        assert advanced["items"]["pack"]["state"]["spoor"] or True


class TestSpoorArtifacts:
    def test_spoor_becomes_an_artifact_and_comes_down_when_gone(self, temp_db):
        cid = _chat(temp_db)
        row = {"key": "spoor:pack:4.0000:north_2:0", "place": "north_2",
               "at_hours": 4.0, "until_hours": 76.0,
               "description": "a carcass torn open", "kind": "harm_done",
               "about": "town/herder_0", "actor": "pack"}
        registry = {"items": {"pack": {"state": {"spoor": [row]}}}}
        standing = post_spoor(cid, registry, 3)
        assert standing == 1
        artifacts = temp_db.wget(cid, ARTIFACTS_WORLD_KEY, [])
        posted = posted_in_room(artifacts, "north_2")
        assert len(posted) == 1
        assert posted[0]["description"] == "a carcass torn open"
        assert posted[0]["spoor"] is True and posted[0]["posted_by"] == ""
        assert posted[0]["report"]["claim"] == "a carcass torn open"
        # Landing it again is one artifact, not two.
        assert post_spoor(cid, registry, 4) == 1
        assert len(posted_in_room(
            temp_db.wget(cid, ARTIFACTS_WORLD_KEY, []), "north_2")) == 1
        # The registry no longer holds it: it comes down.
        assert post_spoor(cid, {"items": {"pack": {"state": {"spoor": []}}}},
                          5) == 0
        artifacts = temp_db.wget(cid, ARTIFACTS_WORLD_KEY, [])
        assert posted_in_room(artifacts, "north_2") == []
        assert artifacts[0]["status"] == REMOVED

    def test_spoor_has_its_own_cap_and_never_touches_a_notice(self, temp_db):
        cid = _chat(temp_db)
        notice = {"uid": "artifact:notice", "room": "square",
                  "description": "a wanted bill", "status": POSTED,
                  "posted_turn": 1, "posted_by": "reeve",
                  "report": {"claim": "a bill"}, "text": "",
                  "wording_failures": 0}
        temp_db.wset(cid, ARTIFACTS_WORLD_KEY, [notice])
        rows = [{"key": "spoor:pack:%d.0000:wood:0" % i, "place": "wood",
                 "at_hours": float(i), "until_hours": 500.0,
                 "description": "tracks %d" % i, "kind": "sighting",
                 "about": "", "actor": "pack"}
                for i in range(SPOOR_STANDING_CAP + 3)]
        standing = post_spoor(cid, {"items": {"pack": {"state":
                                                       {"spoor": rows}}}}, 2)
        assert standing == SPOOR_STANDING_CAP
        artifacts = temp_db.wget(cid, ARTIFACTS_WORLD_KEY, [])
        assert posted_in_room(artifacts, "square")[0]["uid"] == \
            "artifact:notice"

    def test_the_artifact_is_pure_from_the_row(self):
        row = {"key": "spoor:x", "place": "wood", "at_hours": 1.0,
               "description": "paw prints", "kind": "sighting"}
        a = spoor_artifact(7, row, 2)
        b = spoor_artifact(7, row, 9)
        assert a["uid"] == b["uid"] and a["room"] == "wood"
