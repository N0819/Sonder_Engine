"""Turning and looking are acts, and the cone is aimed by them.

The cone subtracted only where a facing was known, and a facing was only
ever inferred: from walking through a beared edge, or from attending a
fixture with a bearing. Measured on the owner's copy (2026-09-15): 243 of
839 positioned bodies carried a facing; 89 attended a person and faced
nowhere; a look around was an English verb table, for the player only.
"""
import agents.perception as perception
from llm.schemas import ActionElement
from world.spatial import TURNS, effective_facing, turn_bearing
from world.spatial_frames import infer_facing, look_bearing


def _scene():
    return {
        "rooms": {"hall": {"name": "hall", "extent": {"w": 8, "d": 8}, "anchors": {
            "hearth": {"desc": "the hearth", "dir": "n"},
            "window": {"desc": "the window", "dir": "e"},
        }, "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "s"}]},
                  "yard": {"name": "yard", "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "n"}]}},
        "positions": {"Ada": "hall", "Bram": "hall"},
        "stations": {"Ada": {"at": None, "near": [], "cell": [4, 4]},
                     "Bram": {"at": None, "near": [], "cell": [7, 4]}},
        "orientation": {"Ada": {"facing": "n"}},
        "entities": {"bram_e": {"name": "Bram", "kind": "person"}},
    }


def test_a_turn_is_a_quarter_or_about_from_where_you_faced():
    assert TURNS == ("left", "right", "back")
    assert turn_bearing("n", "left") == "w"
    assert turn_bearing("n", "right") == "e"
    assert turn_bearing("n", "back") == "s"
    assert turn_bearing("ne", "back") == "sw"
    assert turn_bearing(None, "left") is None       # from nowhere, nowhere


def test_a_look_resolves_to_a_body_a_fixture_an_exit_or_a_turn():
    sc = _scene()
    assert look_bearing(sc, "Ada", "Bram", "n") == ("e", {"kind": "target", "ref": "Bram"})
    assert look_bearing(sc, "Ada", "hearth", "s") == ("n", {"kind": "anchor", "ref": "hearth"})
    assert look_bearing(sc, "Ada", "yard", "n") == ("s", {"kind": "edge", "ref": "yard"})
    assert look_bearing(sc, "Ada", "back", "n") == ("s", None)
    assert look_bearing(sc, "Ada", "around", "n") == ("n", None)
    assert look_bearing(sc, "Ada", "west", "n") == ("w", None)
    assert look_bearing(sc, "Ada", "nothing here", "n") == (None, None)


def test_a_declared_look_sets_the_facing_at_commit_and_a_sweep_marks_the_beat():
    sc = _scene()
    before = {k: dict(v) for k, v in sc["orientation"].items()}
    prev = {"positions": dict(sc["positions"]), "orientation": before}
    infer_facing(1, None, prev, sc, ["Ada", "Bram"], looks={"Ada": "back"}, turn_idx=7)
    assert sc["orientation"]["Ada"]["facing"] == "s"
    infer_facing(1, None, prev, sc, ["Ada", "Bram"], looks={"Ada": "around"}, turn_idx=8)
    assert sc["orientation"]["Ada"]["facing"] == "s" and sc["orientation"]["Ada"]["swept_turn"] == 8
    infer_facing(1, None, prev, sc, ["Ada", "Bram"], looks={"Ada": "Bram"}, turn_idx=9)
    assert sc["orientation"]["Ada"]["facing"] == "e"
    assert sc["orientation"]["Ada"]["focus"] == {"kind": "target", "ref": "Bram"}


def test_attending_a_person_turns_you_toward_their_cell():
    sc = _scene()
    sc["orientation"] = {"Bram": {"focus": {"kind": "target", "ref": "Ada"}}}
    assert effective_facing(sc, "Bram") == "w"
    prev = {"positions": dict(sc["positions"]), "orientation": {"Bram": {}}}
    infer_facing(1, None, prev, sc, ["Ada", "Bram"])
    assert sc["orientation"]["Bram"]["facing"] == "w"


def test_a_pose_facing_something_is_a_facing_when_nothing_else_says():
    sc = _scene()
    sc["orientation"] = {}
    sc["poses"] = {"Ada": {"posture": "standing", "relative_to": "window", "relation": "facing"}}
    prev = {"positions": dict(sc["positions"]), "orientation": {}}
    infer_facing(1, None, prev, sc, ["Ada", "Bram"])
    assert sc["orientation"]["Ada"]["facing"] == "e"


def test_a_sweeping_observer_faces_nowhere_for_the_beat():
    sc = _scene()
    assert effective_facing(sc, "Ada") == "n"
    sc["_sweeping"] = ["ada"]
    assert effective_facing(sc, "Ada") is None


def test_the_look_field_is_declared_and_read_as_the_sweep():
    assert ActionElement(attempt="turns", look="left").look == "left"
    interp = {"sequence": [{"type": "action", "attempt": "looks about", "look": "around"}]}
    assert perception._explicit_look_intent(interp)
    assert not perception._explicit_look_intent({"sequence": [{"type": "action", "attempt": "draws his sword"}]})
    res = {"sequence": [{"type": "action", "actor": "character:5", "look": "around"},
                        {"type": "action", "actor": "persona:1", "look": "left"}]}
    import json
    from story.character_schema import default_character_data
    cast = [{"id": 5, "sheet": json.dumps(default_character_data("Bram"))}]
    assert perception.swept_this_beat(res, "Ada", cast) == {"Bram"}


def test_the_commit_reads_the_players_look_from_the_interpret_and_the_casts_from_the_resolve():
    import json
    from persist.commit import _declared_looks
    from story.character_schema import default_character_data

    class _Ctx:
        chat = {"id": 1, "persona_id": None}
        cast = [{"id": 5, "sheet": json.dumps(default_character_data("Bram"))}]
        def __init__(self, interp): self._i = interp
        def get(self, key, default=None):
            return self._i if key == "director_interpret" else default
    ctx = _Ctx({"sequence": [{"type": "action", "actor": "persona:1", "look": "around"},
                             {"type": "action", "actor": "persona:1", "look": "back"}]})
    res = {"sequence": [{"type": "action", "actor": "character:5", "look": "Ada"}]}
    looks = _declared_looks(ctx, res, p_name="Ada")
    assert looks == {"Ada": "back", "Bram": "Ada"}
