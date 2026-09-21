"""What a body says it is looking at outranks what it is sitting on.

`infer_focus`'s ladder had no rung for a DECLARED look. `_declared_looks`
reads `ActionElement.look` off the beat and hands it to `infer_facing`, which
turns the body -- and focus, the thing perception grades detail by, was left
to `anchor_focus_for`: the anchor a body's POSE is relative to.

Measured (Aldermill, third run, 2026-09-19, 30 beats): Sal Weatherby sat down
on a bench in the Wheel and Bushel to watch the kitchen doorway and the staff
working through it. Her own reasoning, every beat -- "absorbing the low hum of
conversation, picking up on the nuances of what the seniors and house hands
are discussing". The scene recorded

    orientation["Sal Weatherby"].focus = {"kind": "anchor", "ref": "bench"}

because her pose was relative to the bench. For twenty-one beats the engine
held that a woman whose entire drive is to learn how a place works was
attending to her own furniture.

A pose says where a body is braced; a look says where it is aimed. The rung
sits BELOW the salience-snap -- a shout still takes attention nobody gave it
-- and ABOVE the pose anchor, which is the same argument `anchor_focus_for`
already makes against bare persistence: the fresher declaration wins.
"""

import world.spatial_frames as frames


def _scene():
    return {
        "positions": {"Sal Weatherby": "inn_taproom", "Host": "inn_taproom"},
        "rooms": {"inn_taproom": {"name": "Taproom", "anchors": {
            "bench": {"desc": "a trestle bench"},
            "kitchen_door": {"desc": "the kitchen doorway"}}},
            "market_square": {"name": "Market Square"}},
        "poses": {"Sal Weatherby": {"posture": "seated", "relative_to": "bench"}},
        "orientation": {},
    }


def _focus(scene, looks, prev=None):
    frames.infer_focus(1, None, prev if prev is not None else scene,
                       scene, {}, ["Sal Weatherby"], looks=looks)
    return (scene["orientation"].get("Sal Weatherby") or {}).get("focus")


def test_a_declared_look_beats_the_pose_anchor():
    scene = _scene()
    assert _focus(scene, {"Sal Weatherby": "kitchen_door"}) == {
        "kind": "anchor", "ref": "kitchen_door"}


def test_without_a_look_the_pose_anchor_still_wins():
    """The rung is added, not substituted: a body that declared no look is
    attending to what it is braced against, exactly as before."""
    scene = _scene()
    assert _focus(scene, {}) == {"kind": "anchor", "ref": "bench"}


def test_a_look_at_a_co_located_body_focuses_them():
    scene = _scene()
    assert _focus(scene, {"Sal Weatherby": "Host"}) == {
        "kind": "target", "ref": "Host"}


def test_a_look_at_an_adjacent_room_is_an_edge():
    scene = _scene()
    scene["rooms"]["inn_taproom"]["adjacent"] = [
        {"to": "market_square", "barrier": "open_door"}]
    assert _focus(scene, {"Sal Weatherby": "market_square"}) == {
        "kind": "edge", "ref": "market_square"}


def test_a_bare_turn_word_is_not_a_focus():
    """`look` also carries left|right|back|around, which turn the body and
    name nothing to attend to. Those must fall through to the pose rung
    rather than minting a focus on a word."""
    for word in ("left", "right", "back", "around"):
        scene = _scene()
        assert _focus(scene, {"Sal Weatherby": word}) == {
            "kind": "anchor", "ref": "bench"}, word


def test_a_look_at_nothing_the_room_holds_falls_through():
    scene = _scene()
    assert _focus(scene, {"Sal Weatherby": "the far mountains"}) == {
        "kind": "anchor", "ref": "bench"}


def test_a_look_at_a_background_presence_resolves(monkeypatch):
    """Watching a person who has no character sheet is still watching a person.

    `look_focus_for` resolved a declared look against `positions`, the room's
    anchors and its adjacent rooms. A background presence is in NONE of those
    -- the same fact that kept them out of `present_others` -- so every look
    at one fell through to the pose anchor or to nothing.

    Measured (Aldermill, fifth run, 2026-09-19): Sal Weatherby, whose drive is
    to learn who really decides things, declared six looks in eleven rounds
    and four of them were at the reeve's deputies, by the appearance labels
    she had been shown -- "the grizzled burly deputy with...", "the
    weather-worn burly deput...". Her recorded focus was `null` for the whole
    stretch. She was watching the people she came to watch and the engine
    held that she was attending to nothing.

    The label is what she was SHOWN, so it is what she names, and matching it
    is how the look resolves. Only presences in her own room are candidates --
    the room admits, exactly as it does for the cast half.
    """
    scene = _scene()
    monkeypatch.setattr(
        frames, "_room_presences_named",
        lambda chat_id, frame_id, sc, room: {
            "the grizzled burly deputy with a broken nose": "Deputy Harrow"})
    got = _focus(scene, {"Sal Weatherby":
                         "the grizzled burly deputy with a broken nose"})
    assert got == {"kind": "target", "ref": "Deputy Harrow"}


def test_a_presence_in_another_room_is_not_resolved(monkeypatch):
    scene = _scene()
    monkeypatch.setattr(frames, "_room_presences_named",
                        lambda chat_id, frame_id, sc, room: {})
    assert _focus(scene, {"Sal Weatherby": "somebody elsewhere"}) == {
        "kind": "anchor", "ref": "bench"}
