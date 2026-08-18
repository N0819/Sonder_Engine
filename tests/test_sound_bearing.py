"""S3a `sound_bearing`, the S4a bounded loudness walk, and the G2 alarm snap.

sound_bearing is firewall-clean by construction: every answer names the
observer's OWN room's edges or a relative sector, never an unseen room --
asserted directly below. The walk is a DELIBERATE SPEC CHANGE (non-adjacent
used to be nothing but a shout-fragment through `separated`): raised volumes
now travel at most two hops over open edges, attenuating per hop, capped at
`fragment`. The alarm snap consumes it in infer_focus.
"""
from __future__ import annotations

import json

from world.spatial import (
    is_alarming,
    sound_bearing,
    sound_path,
    sound_walk_level,
)
from world.spatial_frames import infer_focus


def _chain(*barriers):
    """hall -[b0]- corridor -[b1]- vault (plus a cellar below the hall)."""
    b0 = barriers[0] if barriers else "open"
    b1 = barriers[1] if len(barriers) > 1 else "open"
    return {
        "rooms": {
            "hall": {"name": "the Hall", "adjacent": [
                {"to": "corridor", "barrier": b0, "dir": "e"},
                {"to": "cellar", "barrier": "open", "vertical": "down"},
            ]},
            "corridor": {"name": "the Corridor", "adjacent": [
                {"to": "vault", "barrier": b1, "dir": "e"},
            ]},
            "vault": {"name": "the Vault", "adjacent": []},
            "cellar": {"name": "the Cellar", "adjacent": []},
        },
        "positions": {},
        "entities": {},
    }


# ---- sound_bearing -----------------------------------------------------------

def test_same_room_bearing_is_an_egocentric_sector():
    sc = _chain()
    sc["rooms"]["hall"]["anchors"] = {"hearth": {"desc": "the hearth",
                                                 "dir": "s"}}
    sc["positions"] = {"P": "hall", "Q": "hall"}
    sc["stations"] = {"Q": {"at": "hearth"}}
    sc["orientation"] = {"P": {"facing": "n"}}
    out = sound_bearing(sc, "P", "Q")
    assert out == {"scope": "same_room", "direction": "behind",
                   "phrase": "behind you"}


def test_same_room_without_facing_gives_no_bearing():
    sc = _chain()
    sc["positions"] = {"P": "hall", "Q": "hall"}
    assert sound_bearing(sc, "P", "Q") is None


def test_adjacent_bearing_renders_edge_against_facing():
    sc = _chain("open_door")
    sc["positions"] = {"P": "hall", "Q": "corridor"}
    sc["orientation"] = {"P": {"facing": "n"}}
    out = sound_bearing(sc, "P", "Q")
    assert out["scope"] == "adjacent"
    assert out["bearing"] == "e"
    assert out["direction"] == "right"
    assert out["phrase"] == "through the doorway to your right"


def test_adjacent_bearing_without_facing_is_compass_only():
    sc = _chain("open_door")
    sc["positions"] = {"P": "hall", "Q": "corridor"}
    out = sound_bearing(sc, "P", "Q")
    assert "direction" not in out
    assert out["phrase"] == "through the doorway, from the east"


def test_a_sound_from_below_says_so():
    sc = _chain()
    sc["positions"] = {"P": "hall", "Q": "cellar"}
    out = sound_bearing(sc, "P", "Q")
    assert out["vertical"] == "down"
    assert out["phrase"] == "from below"


def test_beyond_names_only_the_first_edge_never_the_unseen_room():
    sc = _chain()
    sc["positions"] = {"P": "hall", "Q": "vault"}
    out = sound_bearing(sc, "P", "Q")
    assert out["scope"] == "beyond"
    assert out["bearing"] == "e"          # the hall's own east opening
    dumped = json.dumps(out).casefold()
    assert "vault" not in dumped and "corridor" not in dumped


def test_no_sound_path_no_bearing():
    sc = _chain("open", "wall")
    sc["positions"] = {"P": "hall", "Q": "vault"}
    assert sound_bearing(sc, "P", "Q") is None


# ---- the bounded loudness walk -------------------------------------------------

def test_a_shout_two_open_hops_away_arrives_as_a_fragment():
    sc = _chain()
    assert sound_walk_level(sc, "hall", "vault", "shout") == "fragment"
    assert sound_walk_level(sc, "hall", "vault", "loud") == "fragment"
    assert sound_walk_level(sc, "hall", "vault", "violent") == "fragment"


def test_ordinary_speech_never_propagates():
    sc = _chain()
    for volume in ("normal", "mutter", "whisper", "quiet", None):
        assert sound_walk_level(sc, "hall", "vault", volume) == "none"


def test_a_closed_door_on_the_path_stops_the_walk():
    sc = _chain("open", "closed_door")
    assert sound_walk_level(sc, "hall", "vault", "shout") == "none"


def test_the_walk_is_bounded_at_two_hops():
    sc = _chain()
    sc["rooms"]["vault"]["adjacent"].append(
        {"to": "crypt", "barrier": "open", "dir": "e"})
    sc["rooms"]["crypt"] = {"name": "the Crypt", "adjacent": []}
    assert sound_walk_level(sc, "hall", "crypt", "shout") == "none"
    # An extended-range card may widen the envelope explicitly.
    assert sound_walk_level(sc, "hall", "crypt", "shout",
                            max_hops=3) == "fragment"


def test_adjacent_and_same_room_belong_to_hear_level():
    sc = _chain()
    assert sound_walk_level(sc, "hall", "corridor", "shout") == "none"
    assert sound_walk_level(sc, "hall", "hall", "shout") == "none"


def test_a_hop_may_only_attenuate():
    """The walk never grades ABOVE fragment, whatever the volume, path or
    hop budget -- attenuation-only, the acoustic side of the subtract-only
    invariant."""
    sc = _chain()
    sc["rooms"]["vault"]["adjacent"].append(
        {"to": "crypt", "barrier": "bars", "dir": "e"})
    sc["rooms"]["crypt"] = {"name": "the Crypt", "adjacent": []}
    for target in ("corridor", "vault", "crypt"):
        for volume in ("loud", "shout", "violent"):
            for hops in (1, 2, 3, 4):
                assert sound_walk_level(sc, "hall", target, volume,
                                        max_hops=hops) in ("none", "fragment")


def test_sound_path_is_deterministic_and_bounded():
    sc = _chain()
    assert sound_path(sc, "hall", "vault") == ["hall", "corridor", "vault"]
    assert sound_path(sc, "hall", "vault", max_hops=1) is None


# ---- alarm ----------------------------------------------------------------------

def test_is_alarming_on_loudness_and_targets():
    assert is_alarming(loudness="loud")
    assert is_alarming(loudness="Shout")
    assert is_alarming(loudness="violent")
    assert not is_alarming(loudness="normal")
    assert not is_alarming(loudness=None)
    assert is_alarming(loudness="quiet", targets=["Mara"], perceiver="mara")
    assert not is_alarming(loudness="quiet", targets=["Kael"],
                           perceiver="Mara")


def _focus_scene():
    sc = _chain()
    sc["positions"] = {"Bystander": "hall", "Guard": "corridor",
                       "Shouter": "vault"}
    sc["orientation"] = {}
    return sc


def test_a_shout_snaps_an_unclaimed_bystander_toward_its_first_edge():
    sc = _focus_scene()
    dr = {"dialogue_log": [{"speaker": "Shouter", "text": "FIRE!",
                            "volume": "shout"}]}
    infer_focus(None, None, sc, sc, dr, list(sc["positions"]))
    # Two hops away: the bystander spins toward the doorway the sound came
    # through -- their own room's east opening -- never the unseen vault.
    assert sc["orientation"]["Bystander"]["focus"] == {
        "kind": "edge", "ref": "corridor"}
    # One hop away: the guard turns toward the shouter's room.
    assert sc["orientation"]["Guard"]["focus"] == {
        "kind": "edge", "ref": "vault"}
    # The shouter's own focus is not snapped by their own voice.
    assert sc["orientation"].get("Shouter", {}).get("focus") is None


def test_a_co_located_shout_snaps_to_the_shouter():
    sc = _focus_scene()
    sc["positions"]["Bystander"] = "vault"
    dr = {"dialogue_log": [{"speaker": "Shouter", "text": "DOWN!",
                            "volume": "loud"}]}
    infer_focus(None, None, sc, sc, dr, list(sc["positions"]))
    assert sc["orientation"]["Bystander"]["focus"] == {
        "kind": "target", "ref": "Shouter"}


def test_conversation_outranks_the_alarm_snap():
    sc = _focus_scene()
    sc["positions"]["Friend"] = "hall"
    dr = {"dialogue_log": [
        {"speaker": "Shouter", "text": "HEY!", "volume": "shout"},
        {"speaker": "Bystander", "intended_target": "Friend",
         "text": "as I was saying", "volume": "normal"},
    ]}
    infer_focus(None, None, sc, sc, dr, list(sc["positions"]))
    # Addressing someone holds your focus on them; the shout does not steal it.
    assert sc["orientation"]["Bystander"]["focus"] == {
        "kind": "target", "ref": "Friend"}


def test_a_quiet_line_snaps_nothing():
    sc = _focus_scene()
    dr = {"dialogue_log": [{"speaker": "Shouter", "text": "psst",
                            "volume": "mutter"}]}
    infer_focus(None, None, sc, sc, dr, list(sc["positions"]))
    assert sc["orientation"].get("Bystander", {}).get("focus") is None


def test_an_unreachable_shout_snaps_nothing():
    sc = _chain("open", "wall")
    sc["positions"] = {"Bystander": "hall", "Shouter": "vault"}
    # No open path and separated rel: no channel, no snap -- a direction the
    # perceiver has no way to know is never handed to them.
    dr = {"dialogue_log": [{"speaker": "Shouter", "text": "HELP!",
                            "volume": "shout"}]}
    infer_focus(None, None, sc, sc, dr, list(sc["positions"]))
    assert sc["orientation"].get("Bystander", {}).get("focus") is None
