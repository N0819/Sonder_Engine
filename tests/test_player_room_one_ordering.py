"""One ordering for "which room is the player in" (review finding B36).

Review 2026-09-07, Section B ("two representations free to disagree"): five
readers spelled the same ladder five ways. `background_react` read the scene
with a spelling-only lookup and then `scene["player_room"]`, a key nothing in
the engine writes; `dressing/backdrops._room_of_player` did the same for the
image and sound routes; `director_interpret` read the cached answer and then
the resolver, with no scene read at all; the narrator read the cache and then
the scene -- the exact inversion of the rule perception was written to hold;
and `perception_establish` named the resolver directly (the mildest: the
resolver's own first rung is the scene, so only the spelling changed).

The ladder is now `agents.common.player_room_in` and every stage reads it:
the scene this stage builds its views from, then the cached answer, then the
resolver that may cost a model call. A reader with no `ctx` to reach -- the
backdrop and ambience routes -- stops at rung 1, which is `resolve=False` one
rung further down. `director_resolve` is the one deliberate exception and
says so where it reads the cache.
"""

import inspect

import agents.common as common
from agents.common import player_room_in


class _Ctx:
    """Just the four things the ladder touches on a PipelineContext."""

    def __init__(self, cached=None, cast=(), player_input=""):
        self.chat = {"id": 1}
        self.cast = list(cast)
        self._d = {"_player_room": cached, "input": player_input}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def __setitem__(self, key, value):
        self._d[key] = value


def _no_resolver(monkeypatch):
    """The rung that can cost a model call, wired to record every trip."""
    calls = []

    def _record(*a, **k):
        calls.append(a)
        return "resolver_room"

    monkeypatch.setattr(common, "_resolve_player_room", _record)
    return calls


PERS = {"name": "Vee"}


def test_the_scene_outranks_a_stale_cache(monkeypatch):
    """Presence and channel are two readings of one world, so the scene the
    views are built from answers first."""
    calls = _no_resolver(monkeypatch)
    ctx = _Ctx(cached="room_a")
    sc = {"positions": {"Vee": "room_b"}}

    assert player_room_in(sc, ctx, pers=PERS) == "room_b"
    assert ctx.get("_player_room") == "room_b"
    assert calls == []


def test_the_cache_stands_in_when_the_scene_places_no_body(monkeypatch):
    calls = _no_resolver(monkeypatch)
    ctx = _Ctx(cached="room_a")

    assert player_room_in({"positions": {}}, ctx, pers=PERS) == "room_a"
    assert calls == []


def test_the_resolver_is_the_last_rung(monkeypatch):
    calls = _no_resolver(monkeypatch)
    ctx = _Ctx()

    assert player_room_in({"positions": {}}, ctx, pers=PERS) == "resolver_room"
    assert len(calls) == 1
    assert ctx.get("_player_room") == "resolver_room"


def test_a_stage_that_may_not_spend_a_call_truncates_the_same_ladder(
        monkeypatch):
    """`resolve=False` stops at the cache. It never reorders the rungs above
    it -- the scene still answers first."""
    calls = _no_resolver(monkeypatch)
    ctx = _Ctx(cached="room_a")

    assert player_room_in({"positions": {"Vee": "room_b"}}, ctx, pers=PERS,
                          resolve=False) == "room_b"
    assert player_room_in({"positions": {}}, ctx, pers=PERS,
                          resolve=False) == "room_b"
    assert calls == []


def test_the_player_is_found_under_an_entity_id_or_alias(monkeypatch):
    """`room_of` resolves identity, not spelling. background_react's own
    lookup did not, so a player the scene held under her entity id had no
    room there and every hearing test in that module failed closed."""
    _no_resolver(monkeypatch)
    sc = {
        "positions": {"vee_entity": "room_b"},
        "entities": {"vee_entity": {"name": "Vee"}},
    }
    ctx = _Ctx()

    assert player_room_in(sc, ctx, pers=PERS, resolve=False) == "room_b"


def test_background_react_reads_the_ladder(monkeypatch):
    """The stage's own reader is the shared one now: a scene that tracks no
    position for the player falls through to the cached room instead of to a
    `scene["player_room"]` key nothing writes."""
    import agents.background as background

    _no_resolver(monkeypatch)
    monkeypatch.setattr(common, "persona_of", lambda chat: PERS)
    ctx = _Ctx(cached="room_a")

    assert background._player_room(ctx, {"positions": {}}) == "room_a"
    assert background._player_room(
        ctx, {"positions": {"Vee": "room_b"}}) == "room_b"


def test_a_backdrop_finds_a_player_the_scene_holds_by_entity_id():
    """The image and sound routes ask the same identity-resolving question the
    pipeline does. `dressing/backdrops._room_of_player` matched spelling only,
    so a player the scene held under her entity id had no room to draw and no
    room to sound -- `build_backdrop_request` and `build_ambience_request`
    both returned None for a body standing in a lit room."""
    from dressing.backdrops import _room_of_player

    sc = {
        "positions": {"vee_entity": "room_b"},
        "entities": {"vee_entity": {"name": "Vee"}},
    }
    assert _room_of_player(sc, "Vee") == "room_b"
    assert _room_of_player({"positions": {"Vee": "room_b"}}, "Vee") == "room_b"
    # The dead key is gone rather than demoted: nothing in the engine writes
    # `scene["player_room"]`, so honouring it was a guaranteed None dressed up
    # as a fallback.
    assert _room_of_player({"player_room": "room_c"}, "Vee") is None
    assert _room_of_player({"positions": {}}, None) is None


def test_every_stage_asks_the_one_function():
    """No stage keeps a private ordering. Each of these read the fact its own
    way before B36; the check is that none of them reads the cache as its
    first answer again."""
    import agents.background as background
    import agents.director as director
    import agents.narration as narration
    import agents.perception as perception

    for fn in (perception.perception_establish, perception.perception_act,
               perception.perception_outcome, director.director_interpret,
               narration.narrator, background._player_room):
        src = inspect.getsource(fn)
        assert "player_room_in(" in src, fn.__name__
        assert 'ctx.get("_player_room") or' not in src, fn.__name__
