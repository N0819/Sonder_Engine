"""The composer says where the light falls and where the sound is.

Two fields, one set of rules (the owner's, 2026-09-04), pinned for both
senses in both packs:

  a. speak only when the room is UNEVEN -- all cells one word and the
     existing sentence stands, byte-identically;
  b. grade by ANCHOR, not by cell -- the visible anchors grouped by the four
     light words or the three noise words, rendered from templates over the
     closed sets; no number, cell or sector name reaches prose;
  c. name the source when it is in view (light) or heard (sound), else the
     opening its light or noise comes through; never one the observer has no
     channel to;
  d. say where the observer stands in it -- with a cell; no cell, no claim;
  e. subtract, never add -- `observations_from_render` re-derives the same
     sentence, and an observer receives only their own view's.

The same sentences reach the Director's sight digest
(`director_movement._sightlines_view`, `payload.sightlines`) through
`composer.field_shape_sentence`.
"""

from __future__ import annotations

import re
import types

import pytest

from agents import composer, perception
from agents.director import _sightlines_view
from world import spatial
from world.spatial import (
    LIGHT_LEVELS, NOISE_WORDS, body_cell, light_shape, noise_word,
    sound_field, sound_shape,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def room(name, *, size="medium", light="dark", anchors=None, adjacent=()):
    return {"name": name, "desc": "", "light": light, "exposure": "enclosed",
            "size": size, "anchors": dict(anchors or {}),
            "adjacent": list(adjacent)}


def scene(rooms, positions, *, entities=None, stations=None,
          orientation=None, contained=None):
    return {"rooms": rooms, "positions": dict(positions),
            "entities": dict(entities or {}), "stations": dict(stations or {}),
            "orientation": dict(orientation or {}),
            "contained": dict(contained or {}), "poses": {}}


ANCHORS = {"table": {"desc": "the table", "dir": "n", "height": "waist"},
           "hearth": {"desc": "the hearth", "dir": "s"},
           "shelf": {"desc": "the shelf", "dir": "e", "height": "waist"}}


def lamp_hall(*, generator=False):
    """A dark medium hall: a lit lamp stands on the table (north wall); P
    stands at the table, Q at the hearth (south), both facing north. With
    `generator`, a loud one stands at the shelf (east)."""
    entities = {"lamp": {"name": "the lamp", "light_source": "lit",
                         "portable": True}}
    positions = {"P": "r", "Q": "r", "lamp": "r"}
    stations = {"lamp": {"at": "table"}, "P": {"at": "table"},
                "Q": {"at": "hearth"}}
    if generator:
        entities["gen"] = {"name": "the generator", "kind": "machine",
                           "sound_source": "loud"}
        positions["gen"] = "r"
        stations["gen"] = {"at": "shelf"}
    return scene({"r": room("the Hall", anchors=ANCHORS)}, positions,
                 entities=entities, stations=stations,
                 orientation={"P": {"facing": "n"}, "Q": {"facing": "n"}})


def cellar():
    """A dark cellar with barrels along its south wall, a lit kitchen
    through an open doorway north; P stands at the barrels facing the door."""
    rooms = {
        "k": room("the Kitchen", light="lit",
                  adjacent=[{"to": "c", "barrier": "open_door", "dir": "s"}]),
        "c": room("the Cellar", light="dark",
                  anchors={"barrel": {"desc": "the barrels", "dir": "s"}},
                  adjacent=[{"to": "k", "barrier": "open_door", "dir": "n"}]),
    }
    return scene(rooms, {"P": "c"}, stations={"P": {"at": "barrel"}},
                 orientation={"P": {"facing": "n"}})


def standing(sc, name):
    p = {"room": spatial.room_of(sc, name),
         "room_name": sc["rooms"][spatial.room_of(sc, name)]["name"],
         "room_notes": ""}
    return perception._composer_standing_percepts(sc, p, name, [], {}, {})


def view(sc, name, language="en"):
    return composer.render_view(standing(sc, name), mode="character",
                                full_render=True, language=language)


Q_LIGHT = ("The light from the lamp falls on the table, thins to half-light "
           "at the shelf, and leaves the hearth in the dark. You stand in "
           "half-light.")
P_LIGHT = "The light from the lamp falls on the table. You stand in the light."
Q_SOUND = ("The noise from the generator drowns everything at the shelf and "
           "the hearth and dies away at the table. Where you stand, the noise "
           "drowns everything.")
Q_LIGHT_JA = ("光はthe lampから来ている。the tableは明るく照らされている。"
              "the shelfは薄明かりの中にある。the hearthは闇の中にある。"
              "あなたは薄明かりの中に立っている。")
Q_SOUND_JA = ("騒音はthe generatorから来ている。the shelfとthe hearthでは騒音が"
              "何もかもをかき消している。the tableでは静かだ。"
              "あなたのいる場所では騒音が何もかもをかき消している。")


# ---------------------------------------------------------------------------
# a. The uneven gate
# ---------------------------------------------------------------------------

def test_an_even_room_says_nothing_new_and_the_flat_sentence_stands():
    """Every cell one word: no shape, and the environment percept is the one
    it always was -- data, dedupe key and rendered sentence byte-identical
    to a percept built with no shape argument at all."""
    even = scene({"r": room("the Hall", light="dim", anchors=ANCHORS)},
                 {"P": "r"}, stations={"P": {"at": "table"}})
    assert light_shape(even, "P") is None
    assert sound_shape(even, "P") is None
    with_arg = composer.environment_percept("r", "the Hall", "", "dim",
                                            light_shape=light_shape(even, "P"))
    without = composer.environment_percept("r", "the Hall", "", "dim")
    assert with_arg.data == without.data
    assert with_arg.dedupe_key == without.dedupe_key
    assert composer.soundscape_percept(None, "r") is None
    text = view(even, "P").text
    assert text.endswith("The light is dim.")
    assert "half-light" not in text and "noise" not in text
    # A dark room is dark everywhere: the flat sentence, unchanged.
    dark = scene({"r": room("the Hall", anchors=ANCHORS)}, {"P": "r"},
                 stations={"P": {"at": "table"}})
    assert light_shape(dark, "P") is None
    assert view(dark, "P").text.endswith("It is dark here.")


def test_a_quiet_room_has_no_soundscape_even_with_geometry():
    sc = lamp_hall()
    assert sound_field(sc, "Q") is not None
    assert sound_shape(sc, "Q") is None
    assert all(p.channel != "hearing" for p in standing(sc, "Q"))


# ---------------------------------------------------------------------------
# b. Grade by anchor, from templates over the closed sets
# ---------------------------------------------------------------------------

def test_light_groups_the_visible_anchors_by_word_bright_to_dark():
    sc = lamp_hall()
    shape = light_shape(sc, "Q")
    assert shape == {
        "groups": [{"level": "lit", "items": ["the table"]},
                   {"level": "dim", "items": ["the shelf"]},
                   {"level": "dark", "items": ["the hearth"]}],
        "sources": ["the lamp"], "openings": [], "self": "dim"}
    for group in shape["groups"]:
        assert group["level"] in LIGHT_LEVELS
    assert composer.render_light_shape(shape) == Q_LIGHT
    assert composer.field_shape_sentence("light", shape, language="ja") == Q_LIGHT_JA


def test_sound_groups_the_visible_anchors_by_noise_word_loud_to_quiet():
    sc = lamp_hall(generator=True)
    shape = sound_shape(sc, "Q")
    assert shape == {
        "groups": [{"level": "drowned", "items": ["the shelf", "the hearth"]},
                   {"level": "quiet", "items": ["the table"]}],
        "sources": ["the generator"], "openings": [], "self": "drowned"}
    for group in shape["groups"]:
        assert group["level"] in NOISE_WORDS
    assert composer.render_sound_shape(shape) == Q_SOUND
    assert composer.field_shape_sentence("sound", shape, language="ja") == Q_SOUND_JA


def test_the_noise_ladder_is_derived_from_the_snr_thresholds():
    """quiet | din | drowned by what the noise does to a normal voice one
    pace off: full, a fragment, nothing."""
    from world.spatial import FRAGMENT_SNR, FULL_SNR, VOICE_ONE_PACE
    assert NOISE_WORDS == ("quiet", "din", "drowned")
    assert noise_word(0.0) == "quiet"
    assert noise_word(VOICE_ONE_PACE / FULL_SNR) == "quiet"
    assert noise_word(VOICE_ONE_PACE / FULL_SNR + 0.01) == "din"
    assert noise_word(VOICE_ONE_PACE / FRAGMENT_SNR) == "din"
    assert noise_word(VOICE_ONE_PACE / FRAGMENT_SNR + 0.01) == "drowned"


def test_no_number_cell_or_sector_reaches_prose():
    sc = lamp_hall(generator=True)
    for name in ("P", "Q"):
        for language in ("en", "ja"):
            text = view(sc, name, language).text
            assert not re.search(r"\d", text), text
            for token in ("(", ")", "ahead", "sector", "cell", "0.", "gain"):
                assert token not in text, (token, text)


def test_a_word_outside_the_closed_set_is_dropped_before_any_template():
    shape = {"groups": [{"level": "blinding", "items": ["the table"]},
                        {"level": "lit", "items": ["the hearth"]}],
             "sources": [], "openings": [], "self": "glow"}
    cleaned = composer._clean_shape(shape, composer.LIGHT_SHAPE_LEVELS)
    assert cleaned == {"groups": [{"level": "lit", "items": ["the hearth"]}],
                       "sources": [], "openings": [], "self": None}
    assert composer.render_light_shape(shape) == "The light falls on the hearth."
    assert composer.render_light_shape({"groups": [], "self": "nowhere"}) == ""
    assert composer.render_sound_shape(None) == ""


# ---------------------------------------------------------------------------
# c. Name the source when there is a channel to it, else the opening
# ---------------------------------------------------------------------------

def test_a_source_behind_the_observer_is_not_named_and_its_light_still_is():
    """Q at the hearth turned south: the lamp is in the rear arc and more
    than a pace off, so it is not named -- 'the light' falls on the table
    all the same, because the table is what Q's eyes reach."""
    sc = lamp_hall()
    sc["orientation"]["Q"] = {"facing": "s"}
    shape = light_shape(sc, "Q")
    assert shape["sources"] == [] and shape["openings"] == []
    sentence = composer.render_light_shape(shape)
    assert sentence.startswith("The light ")
    assert "lamp" not in sentence
    # Turned back north, the lamp is in view and named.
    sc["orientation"]["Q"] = {"facing": "n"}
    assert light_shape(sc, "Q")["sources"] == ["the lamp"]


def test_light_through_a_doorway_is_named_by_the_opening():
    """The cellar: no source in it, the kitchen's floor spilling through the
    doorway P faces -- the light is 'from the open doorway', the barrels are
    in the dark, and so is P."""
    sc = cellar()
    shape = light_shape(sc, "P")
    assert shape["sources"] == [] and shape["openings"] == ["the open doorway"]
    assert shape["groups"] == [{"level": "dark", "items": ["the barrels"]}]
    assert shape["self"] == "dark"
    assert composer.render_light_shape(shape) == (
        "The light from the open doorway leaves the barrels in the dark. "
        "You stand in the dark.")
    # A stove in the kitchen casting through the same doorway is ALSO the
    # opening's, never named -- P has no channel to a thing in another room.
    sc["entities"]["stove"] = {"name": "the stove", "light_source": "bright"}
    sc["positions"]["stove"] = "k"
    shape = light_shape(sc, "P")
    assert shape["sources"] == [] and shape["openings"] == ["the open doorway"]
    assert "stove" not in composer.render_light_shape(shape)


def test_a_doorway_the_observer_cannot_see_names_nothing():
    """P turned away from the doorway (the door anchor falls in the rear
    arc): the spill still lands, and the sentence names no opening."""
    sc = cellar()
    sc["orientation"]["P"] = {"facing": "s"}
    shape = light_shape(sc, "P")
    assert shape is None or shape["openings"] == []


def test_a_sound_beyond_the_door_is_named_by_the_opening_and_an_unheard_one_never():
    two = {
        "a": room("A", light="lit", anchors={
            "c": {"desc": "a counter", "dir": "n", "height": "waist"}},
            adjacent=[{"to": "b", "barrier": "open_door", "dir": "e"}]),
        "b": room("B", light="lit", anchors={
            "w": {"desc": "the far window", "dir": "e"},
            "shelf": {"desc": "a shelf", "dir": "s", "height": "waist"}},
            adjacent=[{"to": "a", "barrier": "open_door", "dir": "w"}]),
    }
    sc = scene(two, {"L": "b", "gen": "a"},
               entities={"gen": {"name": "the generator", "kind": "machine",
                                 "sound_source": "deafening"}},
               stations={"gen": {"at": "c"}, "L": {"at": "w"}})
    shape = sound_shape(sc, "L")
    assert shape["sources"] == [] and shape["openings"] == ["the open doorway"]
    assert composer.render_sound_shape(shape).startswith(
        "The noise from beyond the open doorway ")
    # Switched off: nothing to hear, the room is even, nothing is said.
    sc["entities"]["gen"]["state"] = {"running": False}
    assert sound_shape(sc, "L") is None


# ---------------------------------------------------------------------------
# d. Where the observer stands -- with a cell
# ---------------------------------------------------------------------------

def test_the_observer_is_told_where_they_stand_only_with_a_cell():
    sc = lamp_hall(generator=True)
    assert light_shape(sc, "P")["self"] == "lit"
    assert light_shape(sc, "Q")["self"] == "dim"
    assert composer.render_light_shape(light_shape(sc, "P")) == P_LIGHT
    sc["positions"]["U"] = "r"                # nowhere in particular
    assert body_cell(sc, "U") is None
    shape = light_shape(sc, "U")
    assert shape["self"] is None and shape["groups"]
    assert "You stand" not in composer.render_light_shape(shape)
    shape = sound_shape(sc, "U")
    assert shape["self"] is None
    assert "Where you stand" not in composer.render_sound_shape(shape)


# ---------------------------------------------------------------------------
# e. Subtract, never add: the round trip, and only your own sentence
# ---------------------------------------------------------------------------

def test_the_percepts_ride_the_standing_state_and_round_trip_to_observations():
    sc = lamp_hall(generator=True)
    percepts = standing(sc, "Q")
    env = next(p for p in percepts if p.kind == "environment")
    assert env.channel == "sight" and env.data["light_shape"]["self"] == "dim"
    sound = next(p for p in percepts if p.kind == "ambient"
                 and p.data.get("soundscape"))
    assert sound.channel == "hearing"
    rendered = composer.render_view(percepts, mode="character",
                                    full_render=True, language="en")
    assert Q_LIGHT in rendered.text and Q_SOUND in rendered.text
    spans = dict((p.kind if p.kind != "ambient" else "soundscape", s)
                 for p, s in rendered.spans)
    assert spans["environment"].endswith(Q_LIGHT)
    assert spans["soundscape"] == Q_SOUND
    # The observations are the rendered spans, no more: the same text, the
    # channel known from the IR, and nothing the view did not say.
    obs = composer.observations_from_render("Q", rendered)
    texts = {o["channel"]: o["observed"]["text"] for o in obs}
    assert texts["sight"].endswith(Q_LIGHT)
    assert texts["hearing"] == Q_SOUND
    assert "".join(o["observed"]["text"] for o in obs).count("You stand") == 1
    # The shape is part of the CONTENT: the lamp going out is a room that
    # changed for this observer, not the same fact said again.
    doused = lamp_hall(generator=True)
    doused["entities"]["lamp"]["state"] = {"lit": False}
    env2 = next(p for p in standing(doused, "Q") if p.kind == "environment")
    assert env2.dedupe_key != env.dedupe_key


def test_an_observer_receives_only_their_own_views_sentence():
    sc = lamp_hall(generator=True)
    p_text = view(sc, "P").text
    q_text = view(sc, "Q").text
    assert P_LIGHT in p_text and Q_LIGHT not in p_text
    assert Q_LIGHT in q_text and P_LIGHT not in q_text
    assert "You stand in half-light." not in p_text
    assert "You stand in the light." not in q_text
    # And the Japanese views likewise.
    assert Q_LIGHT_JA in view(sc, "Q", "ja").text
    assert Q_LIGHT_JA not in view(sc, "P", "ja").text
    assert Q_SOUND_JA in view(sc, "Q", "ja").text


def test_the_sentence_says_only_what_the_eyes_and_ears_already_have():
    """Every item in a shape is an anchor description this observer's
    `feature_visibility` already delivers, or the label of a source in view
    or heard; a feature behind the observer's back is in neither list."""
    sc = lamp_hall(generator=True)
    sc["orientation"]["Q"] = {"facing": "s"}      # the table is now behind Q
    seen = {r["desc"] for r in spatial.feature_visibility(sc, "Q")
            if r["visible"] and not r["implicit"]}
    for shape in (light_shape(sc, "Q"), sound_shape(sc, "Q")):
        items = {i for g in shape["groups"] for i in g["items"]}
        assert items <= seen, (items, seen)
        assert "the table" not in items


# ---------------------------------------------------------------------------
# The Director's digest carries the same sentences
# ---------------------------------------------------------------------------

def test_the_sight_digest_carries_each_bodys_own_sentences():
    sc = lamp_hall(generator=True)
    ctx = types.SimpleNamespace(cast=[], language="en")
    digest = _sightlines_view(sc, ctx, "Q")
    assert digest["light"] == {"Q": Q_LIGHT}
    assert digest["sound"] == {"Q": Q_SOUND}
    # The digest's sentence IS the view's sentence, span for span.
    spans = {p.kind: s for p, s in view(sc, "Q").spans}
    assert spans["environment"].endswith(digest["light"]["Q"])
    assert spans["ambient"] == digest["sound"]["Q"]
    ctx = types.SimpleNamespace(cast=[], language="ja")
    digest = _sightlines_view(sc, ctx, "Q")
    assert digest["light"] == {"Q": Q_LIGHT_JA}
    assert digest["sound"] == {"Q": Q_SOUND_JA}
    # An even room: the digest has no light or sound key at all.
    even = scene({"r": room("the Hall", light="dim", anchors=ANCHORS)},
                 {"P": "r"}, stations={"P": {"at": "table"}})
    digest = _sightlines_view(even, types.SimpleNamespace(cast=[], language="en"), "P")
    assert "light" not in digest and "sound" not in digest
    assert set(digest) == {"sees", "hidden", "cover", "within_reach"}


def test_field_shape_sentence_falls_back_to_english():
    shape = light_shape(lamp_hall(), "Q")
    assert composer.field_shape_sentence("light", shape, language="en") == Q_LIGHT
    assert composer.field_shape_sentence("light", None) == ""
