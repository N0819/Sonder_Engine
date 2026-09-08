"""ONE APERTURE PER BEAT: which rooms a beat is about, derived once.

Review 2026-09-07 finding C18. Two stages wanted the same answer and neither
asked the other. `agents/mapping.rulebook_rows` took the first
`RULEBOOK_ROOMS_CAP` = 24 keys of ``scene["rooms"]`` in DICT ORDER to find
the creatures and institutions "in view"; `agents/director.director_resolve`
derived the real aperture -- the player's room, its ambient scope, and the
room a declared move targets -- and walked `present_charter_figures` over it
a second time.

Measured on the bench copy of chat 117 (the descent, 38 rooms), which is a
live instance of the defect and not a constructed one: the player stood in
`sub_level_three_utility_core`, the 25th key or later of the scene's room
dict, so the walk never reached her room, and the row it DID produce read
"carbonic_stalker ... 1 of its kind stand here" about a body standing in
`upper_service_core_riser_9` -- five rooms and a stairwell away, in no part
of the map the beat touched. The cap is gone: the aperture decides, and a
dict's insertion order decides nothing.

And with one aperture there is one WALK of the charter: `figures_in_view`
memoises `present_charter_figures` for it, invalidated by the charter row's
own read token. Measured on the same copy of chat 114 (4 charters, 66
bodies): the walk is 8.1 ms over 3 rooms and 14.9 ms over 22, against
0.04-0.76 ms to hand back a copy.
"""
from __future__ import annotations

import time

import pytest

import agents.mapping as mapping
from agents.common import rooms_in_view
from agents.mapping import rulebook_rows
from core.db import wset
from world.charter_model import normalize_charter
from world.charter_runtime import save_registry


@pytest.fixture
def no_retrieval(monkeypatch):
    """No lore retrieval: this file is about the aperture, not the query."""
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [])


def _chat(db, name="Aperture"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _long_scene(n=30, player_room_index=29):
    """A plan with more rooms than the retired cap covered, the player in a
    room past it. Every room is its own island: `ambient_scope` reaches no
    further than the room itself, so the aperture is exactly one room."""
    rooms = {"room_%02d" % i: {"name": "Room %d" % i} for i in range(n)}
    return {"rooms": rooms,
            "positions": {"Pilgrim": "room_%02d" % player_room_index}}


def _charter_at(place, key="hall"):
    return normalize_charter({
        "key": key,
        "posts": {"warden": {"place": place, "serves": [], "requires": {},
                             "worn": [], "marks": []}},
        "bodies": {"warden:0001": {"name": "Warden Ilse Marrow",
                                   "home_post": "warden", "place": place}},
        "watch": {"warden": "warden:0001"},
    })


class _Ctx(dict):
    """A stand-in for the context's `_extra` bag: `rooms_in_view` reads and
    writes its memo through `ctx.get(key)` / `ctx[key] = value` and touches
    nothing else on the context."""


class TestTheApertureIsDerivedOnce:

    def test_it_is_the_players_room_its_scope_and_the_destination(self):
        scene = {"rooms": {"a": {"exits": {"north": "b"}},
                           "b": {"exits": {"south": "a"}},
                           "c": {}},
                 "positions": {"Pilgrim": "a"}}
        ctx = _Ctx()
        assert rooms_in_view(ctx, scene, "a", "c") >= {"a", "c"}
        assert rooms_in_view(ctx, scene, "a") >= {"a"}

    def test_it_derives_once_for_one_key_and_again_when_the_room_moves(self):
        """The memo is keyed by what it reads, so a beat whose player room
        does not move derives once for both stages -- and one where an
        onset assertion moved her before resolve is not served a stale set.
        """
        scene = {"rooms": {"a": {}, "b": {}}, "positions": {"Pilgrim": "a"}}
        ctx = _Ctx()
        first = rooms_in_view(ctx, scene, "a", None)
        cached = ctx.get("_rooms_in_view_cache")
        assert cached and cached[0] == ("a", "")
        assert rooms_in_view(ctx, scene, "a", None) == first
        assert ctx.get("_rooms_in_view_cache") is cached
        moved = rooms_in_view(ctx, scene, "b", None)
        assert moved == {"b"}
        assert ctx.get("_rooms_in_view_cache")[0] == ("b", "")

    def test_the_caller_gets_a_set_it_may_mutate(self):
        ctx = _Ctx()
        scene = {"rooms": {"a": {}}, "positions": {}}
        got = rooms_in_view(ctx, scene, "a")
        got.add("scratch")
        assert rooms_in_view(ctx, scene, "a") == {"a"}


class TestTheCharterIsWalkedOncePerAperture:
    """`common.figures_in_view` memoises the walk, and its invalidation is
    the charter row's own read token -- so a beat that writes the registry
    is not served what stood there before (C18)."""

    class _Ctx(dict):
        def __init__(self, cid):
            super().__init__()
            self.chat = {"id": cid}

    def test_the_second_ask_for_the_same_aperture_does_not_walk_again(
            self, temp_db, monkeypatch):
        import agents.common as common
        cid = _chat(temp_db)
        save_registry(cid, {"hall": _charter_at("room_02")})
        ctx = self._Ctx(cid)
        first = common.figures_in_view(ctx, {}, {"room_02"})
        assert [r["name"] for r in first] == ["Warden Ilse Marrow"]

        walks = []
        real = common.present_charter_figures
        monkeypatch.setattr(common, "present_charter_figures",
                            lambda *a, **k: walks.append(a) or real(*a, **k))
        assert common.figures_in_view(ctx, {}, {"room_02"}) == first
        assert walks == [], "the same aperture is one walk"
        common.figures_in_view(ctx, {}, {"room_29"})
        assert len(walks) == 1, "a different aperture is its own walk"

    def test_a_registry_write_invalidates_it(self, temp_db):
        """The memo's key carries `core.db.world_read_token` for the charter
        row, so what the beat wrote is what the next reader sees."""
        import agents.common as common
        cid = _chat(temp_db)
        save_registry(cid, {"hall": _charter_at("room_02")})
        ctx = self._Ctx(cid)
        assert len(common.figures_in_view(ctx, {}, {"room_02"})) == 1
        save_registry(cid, {})
        assert common.figures_in_view(ctx, {}, {"room_02"}) == []

    def test_the_rows_handed_back_are_the_callers_to_keep(self, temp_db):
        import agents.common as common
        cid = _chat(temp_db)
        save_registry(cid, {"hall": _charter_at("room_02")})
        ctx = self._Ctx(cid)
        got = common.figures_in_view(ctx, {}, {"room_02"})
        got[0]["name"] = "scribbled over"
        got[0]["posts"].append("invented")
        again = common.figures_in_view(ctx, {}, {"room_02"})
        assert again[0]["name"] == "Warden Ilse Marrow"
        assert "invented" not in again[0]["posts"]

    def test_an_empty_aperture_asks_nothing(self, temp_db, monkeypatch):
        import agents.common as common
        cid = _chat(temp_db)
        monkeypatch.setattr(common, "present_charter_figures",
                            lambda *a, **k: pytest.fail("walked an empty set"))
        assert common.figures_in_view(self._Ctx(cid), {}, set()) == []


class TestTheRulebookWalksTheApertureAndNotTheDictOrder:

    def test_a_room_past_the_retired_cap_is_still_walked(self, temp_db):
        """C18: with no aperture given, every room the scene holds is walked.
        The body stands in the 30th room; the retired 24-room dict-order walk
        could not see it."""
        cid = _chat(temp_db)
        scene = _long_scene()
        save_registry(cid, {"hall": _charter_at("room_29")})
        sources = {r["source"] for r in rulebook_rows(cid, scene, None)}
        assert "charter:hall" in sources

    def test_the_aperture_decides_what_stands_here(self, temp_db):
        """A charter body outside the beat's aperture is not described as
        standing here -- the chat-117 row that said a hunter stood in the
        player's room while it stood five rooms away."""
        cid = _chat(temp_db)
        scene = _long_scene()
        save_registry(cid, {"hall": _charter_at("room_02")})
        far = {r["source"] for r in rulebook_rows(cid, scene, None,
                                                  rooms={"room_29"})}
        near = {r["source"] for r in rulebook_rows(cid, scene, None,
                                                   rooms={"room_02"})}
        assert "charter:hall" not in far
        assert "charter:hall" in near

    def test_an_empty_aperture_is_not_the_whole_scene(self, temp_db):
        """`rooms=None` means "no aperture was computed, walk everything";
        an EMPTY aperture means the beat touches no room, and must not fall
        back to walking the map."""
        cid = _chat(temp_db)
        scene = _long_scene()
        save_registry(cid, {"hall": _charter_at("room_02")})
        assert not {r["source"] for r in
                    rulebook_rows(cid, scene, None, rooms=set())} & {
                        "charter:hall"}


class TestTheCompilerRecordsTheApertureOnItsStep:
    """`compile_world_context` records the set so `director_resolve` reads
    one answer instead of deriving a second."""

    def _ctx(self, temp_db, scene, interp, idx=4):
        from core.pipeline_context import ChatData, PipelineContext, TurnData
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Aperture", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (cid, idx, "go", time.time()))
        wset(cid, "scene", scene)
        ctx = PipelineContext(
            chat=ChatData(id=cid, name="Aperture", persona_id=None,
                          lorebook_id=None, scenario="",
                          created=time.time()),
            turn=TurnData(id=turn_id, chat_id=cid, idx=idx,
                          player_input="go", created=time.time(),
                          frame_id=None),
            cast=[], input="go")
        ctx.director_interpret = interp
        return cid, ctx

    def test_the_step_carries_the_players_room_and_the_destination(
            self, temp_db, no_retrieval):
        scene = _long_scene()
        scene["positions"] = {"The Stranger": "room_29"}
        cid, ctx = self._ctx(temp_db, scene,
                             {"flow": {}, "movement": {"to_room": "room_02"},
                              "sequence": []})
        out = mapping.compile_world_context(ctx, nonce=0)
        assert out["rooms_in_view"] == sorted({"room_29", "room_02"})
        # The same derivation, shared: resolve asking for this beat's
        # aperture is served the compiler's answer, not a second walk.
        assert rooms_in_view(ctx, scene, "room_29", "room_02") == {
            "room_29", "room_02"}
        assert ctx.get("_rooms_in_view_cache")[0] == ("room_29", "room_02")

    def test_the_room_comes_from_this_stages_own_scene_read(
            self, temp_db, no_retrieval):
        """The compiler runs BESIDE `perception_act`, which may refresh
        `ctx["_player_room"]`; a stage documented deterministic reads its own
        scene first and falls back to the cache only when the scene places
        nobody."""
        scene = _long_scene()
        scene["positions"] = {"The Stranger": "room_29"}
        cid, ctx = self._ctx(temp_db, scene, {"flow": {}, "sequence": []})
        ctx["_player_room"] = "room_00"
        assert mapping.compile_world_context(
            ctx, nonce=0)["rooms_in_view"] == ["room_29"]

        scene2 = _long_scene()
        scene2["positions"] = {}
        _cid2, ctx2 = self._ctx(temp_db, scene2, {"flow": {}, "sequence": []})
        ctx2["_player_room"] = "room_07"
        assert mapping.compile_world_context(
            ctx2, nonce=0)["rooms_in_view"] == ["room_07"]

    def test_a_charter_body_past_the_retired_cap_reaches_the_rulebook(
            self, temp_db, no_retrieval):
        """The whole of C18 in one beat: the player stands in the 30th room
        of the plan, a warden holds a post there, and the row says so. The
        24-room dict-order walk reached neither."""
        scene = _long_scene()
        scene["positions"] = {"The Stranger": "room_29"}
        cid, ctx = self._ctx(temp_db, scene, {"flow": {}, "sequence": []})
        save_registry(cid, {"hall": _charter_at("room_29")})
        out = mapping.compile_world_context(ctx, nonce=0)
        assert out["rooms_in_view"] == ["room_29"]
        assert "charter:hall" in {r["source"] for r in out["rulebook"]}
