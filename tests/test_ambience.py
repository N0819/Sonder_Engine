"""Room ambience (EXPERIMENTAL) — cache keying, query derivation, and the
guards on host-supplied paths.

These pin the properties that make the feature safe and affordable, which are
NOT the same set as the backdrop equivalents even though the module is its
twin:

  * the acoustic cache key moves with what changes how a place SOUNDS and not
    with what changes how it LOOKS -- light being the one that matters, since a
    room going dark is a wholly new picture and the identical soundscape.
  * occupants never reach the search query, by construction, so a soundscape
    cannot report a presence perception did not deliver.
  * a library path arriving from host input (a pin, a manifest) cannot escape
    the library root, because it is interpolated into a filesystem read.

Deliberately database-free so it stays in the fast tier: everything here is a
pure function over dicts, temp directories, and stubbed settings.
"""

from __future__ import annotations

import json
import os

import pytest

from dressing import ambience
from dressing.ambience import (_safe_relative, acoustic_signature, candidate_key,
                      compose_query, library_files, resolve_local,
                      room_soundscape, search_local)


def _scene():
    return {
        "location": "USS Enterprise D", "time_of_day": "night",
        "rooms": {
            "ten_forward": {"name": "Ten Forward",
                            "desc": "Amber light, panoramic windows, a long bar.",
                            "light": "lit",
                            "adjacent": [{"barrier": "open", "dir": "aft"}]},
            "deck10": {"name": "Corridor", "desc": "Grey panelling.",
                       "light": "lit"},
        },
        "positions": {"Hinami": "ten_forward"},
    }


# --- cache keying ----------------------------------------------------------

def test_rooms_have_distinct_signatures():
    sc = _scene()
    assert acoustic_signature(sc, "ten_forward") != acoustic_signature(sc, "deck10")


def test_people_moving_does_not_invalidate_ambience():
    """The economics of the feature, and its information boundary at once: a
    room is not a different sound because someone walked into it."""
    sc = _scene()
    before = acoustic_signature(sc, "ten_forward")
    sc["positions"]["Guinan"] = "ten_forward"
    sc["positions"]["Hinami"] = "deck10"
    assert acoustic_signature(sc, "ten_forward") == before


def test_light_changes_the_picture_but_not_the_sound():
    """The one deliberate divergence from `backdrops.visual_signature`, and
    most of why ambience gets cache hits on beats where a backdrop pays."""
    from dressing.backdrops import visual_signature
    sc = _scene()
    sound_before = acoustic_signature(sc, "ten_forward")
    picture_before = visual_signature(sc, "ten_forward")
    sc["rooms"]["ten_forward"]["light"] = "dark"
    assert acoustic_signature(sc, "ten_forward") == sound_before
    assert visual_signature(sc, "ten_forward") != picture_before


def test_time_of_day_changes_the_sound():
    sc = _scene()                      # fixture is "night"
    before = acoustic_signature(sc, "ten_forward")
    sc["time_of_day"] = "dawn"
    assert acoustic_signature(sc, "ten_forward") != before


def test_weather_changes_the_sound():
    """Deliberately NOT on the starship fixture: a scene in space has no sky to
    change, which is the point of `weather.py` scoping this per room. See
    tests/test_weather.py for the full matrix."""
    sc = {"rooms": {"yard": {"name": "Courtyard", "desc": "Flagstones."}}}
    before = acoustic_signature(sc, "yard")
    sc["weather"] = "heavy rain"
    assert acoustic_signature(sc, "yard") != before


def test_damage_elsewhere_does_not_invalidate_this_room():
    sc = _scene()
    before = acoustic_signature(sc, "ten_forward")
    sc["overlays"] = {"deck10": ["hull breach, venting"]}
    assert acoustic_signature(sc, "ten_forward") == before
    sc["overlays"]["ten_forward"] = ["fire in the galley"]
    assert acoustic_signature(sc, "ten_forward") != before


def test_a_pin_collapses_the_signature_to_the_choice():
    """A pinned room keeps its sound while the hour and the weather move under
    it -- that is what pinning one means."""
    sc = _scene()
    pin = {"source": "local", "path": "rain/tin_roof.ogg"}
    pinned = acoustic_signature(sc, "ten_forward", None, pin)
    assert pinned.startswith("pin")
    sc["time_of_day"] = "dawn"
    sc["weather"] = "storm"
    assert acoustic_signature(sc, "ten_forward", None, pin) == pinned
    # ...and two rooms pinned to the same file share one cache entry.
    assert acoustic_signature(sc, "deck10", None, pin) == pinned


# --- the query -------------------------------------------------------------

def test_occupants_never_reach_the_query():
    """`place_desc` strips populations out of a room description before it is
    hashed or searched, so a lounge full of people does not become a search for
    a crowd."""
    sc = _scene()
    sc["rooms"]["ten_forward"]["desc"] = (
        "Amber light and panoramic windows. Crew members and civilians gather "
        "here during off-duty hours.")
    place = room_soundscape(sc, "ten_forward")
    query = compose_query(place)
    for leaked in ("crew", "civilians", "members", "gather"):
        assert leaked not in query
    assert "amber" in query or "windows" in query


def test_query_always_asks_for_ambience():
    """Without the word, a search for 'kitchen' returns knives and cupboard
    doors rather than the sound of a kitchen."""
    assert compose_query(room_soundscape(_scene(), "deck10")).endswith("ambience")


def test_soundscape_projection_has_no_concept_of_occupants():
    place = room_soundscape(_scene(), "ten_forward")
    assert set(place) <= {"name", "desc", "room", "time", "weather",
                          "overlays", "ground", "anchors", "openings"}
    assert "positions" not in place and "entities" not in place


# --- fixtures are what a room is heard through -----------------------------
#
# Live failure, "The Blizzard". `RoomDef.anchors` names a room's fixed features
# -- furniture, not occupants -- and the Waystation Main Hall carried
# `fireplace: "crackling stone hearth"`. Nothing read it. The query was built
# from the room's prose instead ("waystation main hall warm modest lit"), which
# describes the light and the mood, and the search answered its one material
# noun -- stone -- with a recording of a cave.

def _hearth_scene():
    return {
        "time_of_day": "evening",
        "rooms": {
            "waystation_interior": {
                "name": "Waystation Main Hall",
                "desc": "A warm, modest hall lit by a few oil lanterns.",
                "anchors": {"fireplace": {"desc": "crackling stone hearth"},
                            "bench": {"desc": "rough wooden bench"}},
                "light": "lit", "exposure": "enclosed",
            },
        },
        "positions": {"Hinami": "waystation_interior"},
    }


def test_the_thing_making_the_noise_reaches_the_query():
    place = room_soundscape(_hearth_scene(), "waystation_interior")
    assert place["anchors"] == ["crackling stone hearth", "rough wooden bench"]
    query = compose_query(place)
    assert "hearth" in query
    # And ahead of the description's adjectives, which no microphone can hear.
    assert query.index("hearth") < query.index("warm")


def test_an_anchor_without_a_description_still_names_itself():
    scene = _hearth_scene()
    scene["rooms"]["waystation_interior"]["anchors"] = {"stone_fountain": {}}
    assert room_soundscape(scene, "waystation_interior")["anchors"] == \
        ["stone fountain"]


def test_a_hearth_going_out_is_a_different_sound():
    """The fixtures are part of the cache key, or a room whose fire has died
    goes on playing the fire."""
    lit = _hearth_scene()
    out = _hearth_scene()
    out["rooms"]["waystation_interior"]["anchors"]["fireplace"] = \
        {"desc": "cold stone hearth, swept"}
    assert acoustic_signature(lit, "waystation_interior") != \
        acoustic_signature(out, "waystation_interior")
    # And far enough apart that the old bed is not adopted as a near-twin.
    assert ambience.fingerprint_similarity(
        ambience.acoustic_fingerprint(lit, "waystation_interior"),
        ambience.acoustic_fingerprint(out, "waystation_interior")) \
        < ambience._REUSE_SIMILARITY


def test_a_bed_cached_before_fixtures_were_keyed_is_kept_only_where_there_are_none():
    """Every manifest already on disk was fingerprinted without an `anchors`
    entry. Reading that absence as "this room has no fixtures" would discard
    every cached bed in every install at once -- but keeping it for a room that
    HAS one adopts a bed chosen before the hearth was legible, which is the
    pick this whole change exists to stop making."""
    plain = ambience.acoustic_fingerprint(_scene(), "deck10")
    assert ambience.fingerprint_similarity(
        plain, {k: v for k, v in plain.items() if k != "anchors"}) == 1.0

    hearth = ambience.acoustic_fingerprint(_hearth_scene(), "waystation_interior")
    assert ambience.fingerprint_similarity(
        hearth, {k: v for k, v in hearth.items() if k != "anchors"}) == 0.0


def test_anchors_carry_no_occupants():
    """They are furniture. A person standing at one is a `station`, which lives
    somewhere the projection has never looked."""
    scene = _hearth_scene()
    scene["rooms"]["waystation_interior"]["stations"] = {
        "Hinami": {"at": "fireplace"}}
    query = compose_query(room_soundscape(scene, "waystation_interior"))
    assert "hinami" not in query.casefold()


def test_style_is_part_of_the_key():
    sc = _scene()
    assert acoustic_signature(sc, "ten_forward", {"tone": "noir"}) \
        != acoustic_signature(sc, "ten_forward", {"tone": "pastoral"})


# --- library paths ---------------------------------------------------------

@pytest.fixture()
def library(tmp_path):
    root = tmp_path / "lib"
    (root / "weather").mkdir(parents=True)
    (root / "rooms").mkdir()
    for rel in ("weather/heavy_rain_on_stone.ogg",
                "weather/wind.mp3",
                "rooms/ship_corridor_hum.mp3",
                "rooms/notes.txt"):
        (root / rel).write_bytes(b"x")
    return root


def test_traversal_cannot_escape_the_library(library):
    assert _safe_relative("../../engine.db") == ""
    assert _safe_relative("/etc/passwd") == ""
    assert _safe_relative("weather/../../../engine.db") == ""
    # Non-audio is refused too: the path is handed to a media response.
    assert _safe_relative("rooms/notes.txt") == ""
    assert _safe_relative("weather/wind.mp3") == "weather/wind.mp3"


def test_resolve_local_rejects_paths_outside_the_root(library, tmp_path):
    outside = tmp_path / "secret.mp3"
    outside.write_bytes(b"x")
    assert resolve_local("weather/wind.mp3", str(library)) is not None
    assert resolve_local("../secret.mp3", str(library)) is None
    assert resolve_local("nothing/here.mp3", str(library)) is None


def test_library_listing_ignores_non_audio(library):
    files = library_files(str(library))
    assert "rooms/notes.txt" not in files
    assert "weather/heavy_rain_on_stone.ogg" in files


def test_local_search_ranks_by_filename_overlap(library):
    hits = search_local("heavy rain stone ambience", str(library))
    assert hits and hits[0]["path"] == "weather/heavy_rain_on_stone.ogg"


def test_local_search_reads_the_index_sidecar(library):
    """A host who does not want to rename files can tag them instead."""
    (library / "index.json").write_text(json.dumps({
        "rooms/ship_corridor_hum.mp3": "starship engine drone machinery",
    }), encoding="utf-8")
    hits = search_local("starship drone", str(library))
    assert hits and hits[0]["path"] == "rooms/ship_corridor_hum.mp3"


def test_local_search_of_an_empty_library_is_not_an_error(tmp_path):
    assert search_local("anything", str(tmp_path / "nope")) == []


# --- reroll ----------------------------------------------------------------

def test_candidate_keys_are_stable_across_sources():
    """The reroll ledger stores these, so they have to survive a re-search
    where ranking has moved."""
    assert candidate_key({"source": "freesound", "id": 4321}) == "fs:4321"
    assert candidate_key({"source": "local", "path": "a/b.mp3"}) == "lc:a/b.mp3"


def test_settings_default_to_a_local_source_and_safe_licences(monkeypatch):
    monkeypatch.setattr(ambience, "get_setting", lambda key, default=None: None)
    settings = ambience.ambience_settings()
    assert settings["source"] == "local"
    assert settings["enabled"] is False
    # NonCommercial is available but must never arrive without being asked for.
    assert settings["licenses"] == ["Creative Commons 0", "Attribution"]


def test_freesound_source_is_unconfigured_without_a_key(monkeypatch):
    monkeypatch.setattr(ambience, "get_setting",
                        lambda key, default=None:
                        "freesound" if key == "ambience_source" else None)
    assert ambience.ambience_settings()["configured"] is False


# --- freesound query broadening --------------------------------------------
#
# Freesound ANDs the terms of a query. Composed room queries are seven or eight
# words long, so without broadening every single one of them matches nothing
# and the source can never play a sound at all.

def test_the_ladder_broadens_but_keeps_the_anchor():
    ladder = ambience._query_ladder(
        "stone tile small room open reverb quiet ambience")
    assert ladder[0] == "stone tile small room open reverb quiet ambience"
    # The prefix half is unchanged and still bounded at four: terms go from the
    # end, because compose_query puts the room's own words first.
    prefix = ladder[:4]
    assert len(prefix) == 4
    assert all(rung.startswith("stone") for rung in prefix)
    # "ambience" -- what the recordings are tagged with -- survives every rung.
    assert all(rung.endswith("ambience") for rung in ladder)
    assert len(ladder[-1].split()) < len(ladder[0].split())


def test_the_ladder_reaches_the_head_noun_a_prefix_can_never_keep():
    """Live failure, "The Blizzard". A hall with a lit hearth was searched for
    as "stone hearth fire crackle wooden room ambience". English puts the
    modifier in front of the head noun, so every prefix rung kept `stone` and
    threw away the thing making the noise; the ladder bottomed out on `stone
    ambience`, which returns caves, and the hall was given one.

    `hearth ambience` returns four recordings tagged `ambience, fire, hearth`
    and no prefix of that query can ever reach it."""
    ladder = ambience._query_ladder(
        "stone hearth fire crackle wooden room ambience")
    assert "stone ambience" in ladder            # the rung that found the cave
    assert "hearth ambience" in ladder           # the rung that finds the hearth
    assert "fire ambience" in ladder
    # Bounded: the probes are a last resort, not a sweep of the whole query.
    assert len(ladder) <= 4 + ambience._MAX_PROBES


def test_the_ladder_reaches_past_an_invented_room_name():
    """The other half of the same failure. compose_query leads with the room's
    NAME, and a name in fiction is a proper noun no sound library has ever
    heard of -- so prefix broadening protects the one term guaranteed to match
    nothing. Every rung of the Waystation's draft ladder returned zero."""
    ladder = ambience._query_ladder("waystation main hall warm modest ambience")
    assert all(rung.startswith("waystation") for rung in ladder[:4])
    assert "hall ambience" in ladder
    assert "warm ambience" in ladder


def test_the_ladder_keeps_a_weather_query_intact_at_the_top():
    ladder = ambience._query_ladder("heavy rain downpour ambience loop")
    assert ladder[0] == "heavy rain downpour ambience loop"
    assert all("loop" in rung for rung in ladder)


def test_a_lookup_by_id_is_never_broadened():
    """_materialize re-fetches an exact sound with `id:NNN`. Broadening that
    into some other recording would silently swap what a pin points at."""
    assert ambience._query_ladder("id:4321") == ["id:4321"]


def test_search_broadens_until_something_matches(monkeypatch):
    tried = []

    def fake_page(query, key, licence_filter, limit, no_music=False):
        tried.append(query)
        return [{"source": "freesound", "id": 1}] if len(query.split()) <= 3 else []

    monkeypatch.setattr(ambience, "_freesound_page", fake_page)
    monkeypatch.setattr(ambience, "ambience_settings",
                        lambda: {"key": "k", "licenses": ["Attribution"]})
    found = ambience.search_freesound("kitchen warm bread oven crowded ambience")
    assert found and found[0]["id"] == 1
    assert len(tried) > 1                      # the full query missed
    assert tried[0] == "kitchen warm bread oven crowded ambience"


def test_search_stops_at_the_first_hit_that_answers_the_room(monkeypatch):
    """A rung that answers the room ends the search: the ladder only exists
    because the full query so often matches nothing."""
    tried = []

    def fake_page(query, key, licence_filter, limit, no_music=False):
        tried.append(query)
        return [{"source": "freesound", "id": 7, "title": "forest pine wind",
                 "tags": ["forest", "pine", "wind"]}]

    monkeypatch.setattr(ambience, "_freesound_page", fake_page)
    monkeypatch.setattr(ambience, "ambience_settings",
                        lambda: {"key": "k", "licenses": ["Attribution"]})
    assert ambience.search_freesound("forest pine wind ambience")[0]["id"] == 7
    assert tried == ["forest pine wind ambience"]


def test_a_rung_that_returns_anything_is_not_a_rung_that_answers(monkeypatch):
    """Live failure, "The Blizzard". Broadening threw away every word but
    `stone`, that rung came back full of caves, and taking the first non-empty
    rung meant the rungs that would have found the hearth were never tried."""
    tried = []
    caves = [{"source": "freesound", "id": 1, "title": "ambience in a large cave",
              "tags": ["ambience", "cave", "stone", "loopable"]}]
    hearth = [{"source": "freesound", "id": 2, "title": "hearth fire / soft",
               "tags": ["ambience", "fire", "hearth"]}]

    def fake_page(query, key, licence_filter, limit, no_music=False):
        tried.append(query)
        if query == "stone ambience":
            return caves
        if query == "hearth ambience":
            return hearth
        return []

    monkeypatch.setattr(ambience, "_freesound_page", fake_page)
    monkeypatch.setattr(ambience, "ambience_settings",
                        lambda: {"key": "k", "licenses": ["Attribution"]})
    found = ambience.search_freesound(
        "stone hearth fire crackle wooden room ambience",
        rank_query="waystation main hall crackling stone hearth warm ambience")
    assert "stone ambience" in tried and "hearth ambience" in tried
    # Both share exactly one word with the room ("stone", "hearth"), so `fit`
    # alone cannot separate them -- and the cave is the one tagged `loopable`.
    # What decides it is how much of what was ASKED FOR each answers: the
    # hearth recording carries both `hearth` and `fire`, the cave only `stone`.
    assert found[0]["id"] == 2
    assert found[0]["fit"] == 1 and found[0]["intent"] == 2


def test_search_without_a_key_is_an_error_not_an_empty_result(monkeypatch):
    monkeypatch.setattr(ambience, "ambience_settings",
                        lambda: {"key": "", "licenses": ["Attribution"]})
    with pytest.raises(RuntimeError):
        ambience.search_freesound("anything")


# --- choosing a bed that is actually this room ------------------------------
#
# The measured failure these exist for: a bath scene was given a well-rated
# recording of falling roof tiles. The query "stone tile bathroom" matched it
# honestly, and nothing downstream asked whether the result was a PLACE or a
# THING HAPPENING. Ranking is where that question gets asked.

def test_a_query_is_anchored_to_a_bed():
    assert ambience._anchored("stone tile bathroom").endswith(" ambience")
    # Already asking for a bed: not doubled.
    assert ambience._anchored("heavy rain loop") == "heavy rain loop"
    assert ambience._anchored("quiet room tone") == "quiet room tone"


def test_a_model_query_is_anchored_even_when_the_model_forgets(model_says):
    """The prompt asks for the anchor; the code guarantees it. An unanchored
    query is exactly how the roof tiles got in."""
    model_says({"layers": [{"role": "tone", "query": "stone tile floor bathroom"}]})
    plan, _verdict = ambience.refine_layers(_draft(), {"name": "Bathroom"})
    assert plan[0]["query"] == "stone tile floor bathroom ambience"


def test_ranking_prefers_the_room_over_the_crowd():
    """A recording's rating is the crowd's opinion of the RECORDING. It says
    nothing about whether this is the room, so it ranks last."""
    ranked = ambience._rank_candidates([
        {"id": 1, "title": "Dropping Rooftiles",
         "tags": ["tiles", "dropping", "roof"], "rating": 4.9},
        {"id": 2, "title": "Bathroom room tone",
         "tags": ["bathroom", "tile", "water", "ambience"], "rating": 1.2},
    ], "stone tile floor bathroom ambience")
    assert [c["id"] for c in ranked] == [2, 1]


def test_ranking_demotes_a_thing_happening():
    """Ambience is continuous. A clip of an event is unlistenable on a loop
    however well it matches the words."""
    ranked = ambience._rank_candidates([
        {"id": 1, "title": "door slam impact", "tags": ["slam", "impact"], "rating": 5.0},
        {"id": 2, "title": "empty stone hall", "tags": ["stone", "hall"], "rating": 0.4},
    ], "stone hall ambience")
    assert ranked[0]["id"] == 2


def test_ranking_strikes_out_what_the_model_asked_to_avoid():
    """`avoid` has been in the prompt's output shape since the first version
    and was read by nobody. It is applied here."""
    ranked = ambience._rank_candidates([
        {"id": 1, "title": "cafe chatter", "tags": ["voices", "crowd"], "rating": 5.0},
        {"id": 2, "title": "stone hall", "tags": ["stone", "hall"], "rating": 0.3},
    ], "stone hall ambience", avoid="voices, music")
    assert ranked[0]["id"] == 2


def test_ranking_folds_plurals():
    """Uploaders tag 'voices' where a query says 'voice'. An overlap that
    misses that is measuring spelling, not sound."""
    ranked = ambience._rank_candidates([
        {"id": 1, "title": "machine hum", "tags": ["machine"], "rating": 0.0},
        {"id": 2, "title": "cave drips", "tags": ["caves", "drips", "water"], "rating": 0.0},
    ], "cave drip water ambience")
    assert ranked[0]["id"] == 2


def test_the_model_veto_reaches_the_local_library(library):
    """Both sources honour `avoid`, or the setting means different things
    depending on where the host keeps their sounds."""
    assert search_local("rain storm", library=library)
    assert not search_local("rain storm", library=library, avoid="rain")


def test_ranking_prefers_a_bed_prepared_to_loop():
    """Between two equally room-like recordings, the one its uploader trimmed
    to loop is the one that will not stop dead every ninety seconds."""
    ranked = ambience._rank_candidates([
        {"id": 1, "title": "stone hall", "tags": ["stone", "hall"], "rating": 0.0},
        {"id": 2, "title": "stone hall", "tags": ["stone", "hall", "seamless", "loop"],
         "rating": 0.0},
    ], "stone hall ambience")
    assert ranked[0]["id"] == 2
    assert ranked[0]["loopable"] is True and ranked[1]["loopable"] is False


def test_a_loop_tag_does_not_outrank_being_the_right_room():
    """A seamless loop of the wrong place is still the wrong place."""
    ranked = ambience._rank_candidates([
        {"id": 1, "title": "engine room", "tags": ["engine", "loop", "seamless"],
         "rating": 5.0},
        {"id": 2, "title": "stone hall tone", "tags": ["stone", "hall"], "rating": 0.1},
    ], "stone hall ambience")
    assert ranked[0]["id"] == 2


def test_music_may_be_a_room_but_never_the_sky():
    """A tavern band is a real thing to hear in a room. Rain does not play in
    a key, so the weather layer -- and only the weather layer -- vetoes music
    outright rather than merely ranking it down."""
    assert not ambience.role_veto("tone")
    assert not ambience.role_veto("extra")
    assert "music" in ambience.role_veto("weather")

    band = {"id": 1, "title": "tavern band", "tags": ["music", "folk", "fiddle"],
            "rating": 5.0, "category": "Music"}
    room = {"id": 2, "title": "tavern room tone", "tags": ["tavern", "crowd"],
            "rating": 0.2}
    # In a ROOM music is available but last-resort: it sinks beneath anything
    # that is not music, and it is never struck out.
    ranked = ambience._rank_candidates([band, room], "tavern crowd ambience")
    assert [c["id"] for c in ranked] == [2, 1]
    assert all(c["vetoed"] is False for c in ranked)

    # ...unless the room itself asked for it, when the penalty lifts and the
    # band competes on how well it answers the room like anything else.
    street = {"id": 3, "title": "empty street", "tags": ["street"], "rating": 5.0}
    assert [c["id"] for c in ambience._rank_candidates(
        [band, street], "tavern band ambience")] == [3, 1]
    assert [c["id"] for c in ambience._rank_candidates(
        [band, street], "tavern band music ambience")] == [1, 3]

    rain = {"id": 3, "title": "rain on roof", "tags": ["rain", "roof"], "rating": 0.1}
    musical_rain = {"id": 4, "title": "Rain (ambient piano)",
                    "tags": ["rain", "piano", "music"], "rating": 5.0}
    ranked = ambience._rank_candidates([musical_rain, rain], "rain roof ambience loop",
                                       avoid=ambience.role_veto("weather"))
    kept = [c for c in ranked if not c["vetoed"]]
    assert [c["id"] for c in kept] == [3]


def test_a_musical_weather_layer_is_left_out_rather_than_used(tmp_path, monkeypatch):
    """No fallback relaxes this one. A room with no rain layer is right; a room
    whose rain is a piano is not."""
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    monkeypatch.setattr(ambience, "branch_lineage", lambda cid: [])
    monkeypatch.setattr(ambience, "ambience_settings", lambda: {
        "source": "freesound", "library": "", "licenses": [], "key": "k",
        "enabled": True, "configured": True})
    monkeypatch.setattr(ambience, "build_ambience_request", lambda *a, **kw: {
        "room": "yard", "room_name": "Yard", "signature": "sigwx", "pin": None,
        "cached": None, "fingerprint": {},
        "place": {"name": "Yard", "desc": "Flagstones.", "weather": ["heavy rain"]},
        "weather": {"gain": 0.6}})
    monkeypatch.setattr(ambience, "refine_layers", lambda layers, place: (layers, {}))
    # Every search answers with the same music-tagged clip, marked exactly as
    # the ranker would mark it for the caller's veto.
    def fake_search(query, source=None, limit=8, avoid="", rank_query="", no_music=False):
        vetoed = "music" in avoid
        return [{"source": "freesound", "id": 9, "title": "Rain (ambient piano)",
                 "preview": "http://x/p.mp3", "fit": 1, "vetoed": vetoed}]
    monkeypatch.setattr(ambience, "search_candidates", fake_search)
    monkeypatch.setattr(
        ambience, "_materialize",
        lambda cid, sig, index, choice, role="tone", gain=1.0, query="":
        {"role": role, "gain": gain, "query": query, "source": "freesound",
         "id": choice["id"], "title": choice["title"], "file": "f.mp3"})

    out = ambience.resolve_ambience(1, 0)
    assert [layer["role"] for layer in out["layers"]] == ["tone"]


def test_a_bed_that_answers_nothing_is_refused(monkeypatch, tmp_path):
    """Live failure, "The Blizzard". The winner shared no word with the room
    and no word with what was searched for -- a fit and an intent of zero, the
    search saying it found nothing of this place -- and was laid under the room
    anyway on the strength of a `loopable` tag. Silence is the honest answer;
    the feature is ambience TRUE TO THE ROOM, not ambience at all costs."""
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    monkeypatch.setattr(ambience, "branch_lineage", lambda cid: [])
    monkeypatch.setattr(ambience, "ambience_settings", lambda: {
        "source": "freesound", "library": "", "licenses": [], "key": "k",
        "enabled": True, "configured": True})
    monkeypatch.setattr(ambience, "build_ambience_request", lambda *a, **kw: {
        "room": "waystation_interior", "room_name": "Waystation Main Hall",
        "signature": "sighall", "pin": None, "cached": None, "fingerprint": {},
        "place": {"name": "Waystation Main Hall", "desc": "A warm, modest hall.",
                  "anchors": ["crackling stone hearth"]},
        "weather": {}})
    monkeypatch.setattr(ambience, "refine_layers", lambda layers, place: (layers, {}))
    monkeypatch.setattr(
        ambience, "search_candidates",
        lambda query, source=None, limit=8, avoid="", rank_query="", **kw:
        [{"source": "freesound", "id": 611927, "preview": "http://x/p.mp3",
          "title": "ambience in a large cave", "fit": 0, "intent": 0,
          "loopable": True}])
    with pytest.raises(RuntimeError):
        ambience.resolve_ambience(1, 0)


def test_thunder_is_never_in_the_weather_bed():
    """The engine draws the flash and schedules the clap FROM it, by a delay
    standing in for distance. A bed with thunder baked in claps on its own
    schedule, so the sky flashes in one place and rumbles in another."""
    veto = ambience.role_veto("weather")
    assert "thunder" in veto and "lightning" in veto
    # The bed this story was actually using, tags and all.
    bed = {"id": 1, "title": "Rain&ThunderLoop1Light.wav",
           "tags": ["ambience", "field-recording", "lightning", "loop", "rain"],
           "rating": 4.7}
    plain = {"id": 2, "title": "Light Rain", "tags": ["rain", "ambience"],
             "rating": 0.5}
    ranked = ambience._rank_candidates([bed, plain], "rain light ambience loop",
                                       avoid=veto)
    assert ranked[0]["id"] == 2
    assert [c["id"] for c in ranked if not c["vetoed"]] == [2]


def test_rain_asks_for_the_surface_it_lands_on():
    """The same downpour is a roar on a tin roof, a hiss on leaves and a
    clatter on cobbles. The room already says which."""
    surface = ambience.rain_surface
    assert surface({"name": "Bunk Room", "desc": "A tin roof over four bunks."}) \
        == "tin roof"
    assert surface({"name": "Forest Track", "desc": "Pines close overhead."}) \
        == "leaves"
    # Plural, because rooms are described in the plural constantly -- and a cue
    # that only matched the singular sent a lane under awnings to cobblestones.
    assert surface({"name": "Sheltered Path",
                    "desc": "A lane with overhanging awnings."}) == "canvas awning"
    # A room that says nothing about its materials gets plain rain, which is
    # the honest answer rather than a guess.
    assert surface({"name": "Nowhere", "desc": ""}) == ""


def test_a_surface_cue_is_a_whole_word_and_not_a_denial():
    """Both of these were live errors: "hosting dozens of market stalls"
    matched `tin` and roofed an open square in corrugated iron, and "bare
    stone, no windows" matched `window` and rained on a cellar's glass."""
    surface = ambience.rain_surface
    assert surface({"name": "Central Market",
                    "desc": "A wide open square hosting dozens of stalls."}) == ""
    assert surface({"name": "Cellar", "desc": "Bare stone, no windows."}) == "stone"


def test_the_surface_is_the_first_thing_broadening_drops():
    """A refinement, never a requirement: a library with no rain-on-awning
    must fall back to plain rain of the right intensity, not to nothing."""
    layers = ambience.compose_layers(
        {"name": "Sheltered Path", "desc": "A lane with overhanging awnings.",
         "weather": ["rain light"]}, None, {"gain": 0.8})
    weather = [l for l in layers if l["role"] == "weather"][0]
    assert weather["query"] == "rain light canvas awning ambience loop"
    ladder = ambience._query_ladder(weather["query"])
    assert ladder[0] == weather["query"]
    # Plain rain of the right intensity is reachable, and is reached BEFORE the
    # surface is tried on its own -- an awning is a refinement of the rain, so
    # a rung that keeps only the awning is the last thing worth asking.
    assert "rain ambience loop" in ladder
    assert ladder.index("rain ambience loop") < ladder.index("awning ambience loop")


def test_five_stars_from_one_rater_is_not_a_rating():
    """Freesound's own sort=rating_desc is a trap: the library is full of
    perfect scores from a handful of voters."""
    lonely = {"rating": 5.0, "votes": 1, "downloads": 12}
    crowd = {"rating": 4.48, "votes": 6224, "downloads": 155854}
    assert ambience._crowd_score(crowd) > ambience._crowd_score(lonely)
    # ...and popularity is a nudge between near-equals, never a second
    # relevance score: being the right room still wins.
    right_room = {"id": 1, "title": "stone hall", "tags": ["stone", "hall"],
                  "rating": 0.0, "votes": 0, "downloads": 0}
    wrong_room = {"id": 2, "title": "busy street", "tags": ["street"],
                  "rating": 5.0, "votes": 9000, "downloads": 900000}
    ranked = ambience._rank_candidates([wrong_room, right_room], "stone hall ambience")
    assert ranked[0]["id"] == 1


def test_wildlife_is_its_own_layer_not_the_sky():
    """Rain recordings are very often rain AND something alive. Taken whole
    into the weather layer, a dawn chorus ends up welded to the sky's gain --
    which is derived from how deep the room sits under it, and has nothing to
    do with birds. Birds belong to the PLACE, and go on after the rain stops."""
    assert "birds" in ambience.role_veto("weather")
    # ...and nowhere else: an `extra` layer is exactly where they belong, and a
    # forest tone may be full of them.
    assert not ambience.role_veto("extra")
    assert not ambience.role_veto("tone")

    dawn = {"id": 1, "title": "Birds_at_Dawn_light_Rain", "tags": ["birds", "rain"],
            "rating": 5.0}
    plain = {"id": 2, "title": "Light Rain", "tags": ["rain"], "rating": 0.1}
    sky = ambience._rank_candidates([dawn, plain], "rain light ambience loop",
                                    avoid=ambience.role_veto("weather"))
    assert [c["id"] for c in sky if not c["vetoed"]] == [2]
    # The same recording, offered to an `extra` layer that asked for birds.
    living = ambience._rank_candidates([dawn, plain], "birdsong dawn ambience",
                                       avoid=ambience.role_veto("extra"))
    assert living[0]["id"] == 1 and living[0]["vetoed"] is False


def test_a_veto_word_is_caught_inside_a_compound_token():
    """"Rain&ThunderLoop1Light.wav" tokenises to "thunderloop", which no
    exact-match set will ever contain."""
    ranked = ambience._rank_candidates(
        [{"id": 1, "title": "Rain&ThunderLoop1Light.wav", "tags": ["rain"]}],
        "rain ambience loop", avoid=ambience.role_veto("weather"))
    assert ranked[0]["vetoed"] is True


def test_the_veto_list_is_not_truncated():
    """The music veto is longer than a query, and a cap sized for queries would
    quietly let the last words of it back in."""
    tail = ambience.role_veto("weather").split()[-1]
    ranked = ambience._rank_candidates(
        [{"id": 1, "title": "rain " + tail, "tags": [tail], "rating": 5.0}],
        "rain ambience loop", avoid=ambience.role_veto("weather"))
    assert ranked[0]["vetoed"] is True


# --- how much has to change before the sound does ---------------------------
#
# The room's state moves every beat; almost none of it is audible. Each of these
# used to mint a new cache key, and a new key is a model call plus a download.

def _room_scene(desc, name="Ten Forward", time="night", **extra):
    room = {"name": name, "desc": desc}
    room.update(extra)
    return {"time_of_day": time, "rooms": {"ten_forward": room},
            "positions": {"Hinami": "ten_forward"}}


def test_rewording_a_description_does_not_move_the_key():
    """Same materials, different sentence. Nothing a microphone would notice."""
    a = acoustic_signature(_room_scene("A long bar of polished wood, tall viewports."),
                           "ten_forward")
    b = acoustic_signature(_room_scene("Tall viewports; the bar is polished wood, long."),
                           "ten_forward")
    assert a == b


def test_a_new_material_does_move_the_key():
    a = acoustic_signature(_room_scene("A long bar of polished wood."), "ten_forward")
    b = acoustic_signature(_room_scene("A long bar of polished wood, and a fountain."),
                           "ten_forward")
    assert a != b


def test_the_style_guide_only_reaches_the_key_through_one_term():
    """Prose has no sound, so only the term the QUERY uses is hashed.

    That term was `genre` until 2026-09-04, when the field left the guide and
    this loop was left reading a key nothing could set -- the query silently
    lost its only style word. It is `tone` now. `avoid` is deliberately not
    here: it is a veto, and putting its words in a search asks for the thing
    they forbid.
    """
    scene = _room_scene("A long bar.")
    a = acoustic_signature(scene, "ten_forward", {"tone": "noir", "avoid": "x"})
    b = acoustic_signature(scene, "ten_forward", {"tone": "noir", "avoid": "y"})
    c = acoustic_signature(scene, "ten_forward", {"tone": "horror", "avoid": "x"})
    assert a == b
    assert a != c


def test_similarity_never_crosses_the_weather_or_the_hour():
    """A threshold that could be talked into playing a dry room under a
    downpour would be worse than no threshold."""
    dry = ambience.acoustic_fingerprint(_room_scene("Bare stone cell."), "ten_forward")
    wet = dict(dry, weather=["heavy rain"])
    dawn = dict(dry, time="morning")
    assert ambience.fingerprint_similarity(dry, dry) == 1.0
    assert ambience.fingerprint_similarity(dry, wet) == 0.0
    assert ambience.fingerprint_similarity(dry, dawn) == 0.0


def test_similarity_tolerates_a_small_change_and_not_a_large_one():
    base = ambience.acoustic_fingerprint(
        _room_scene("Bare stone cell, iron door, straw on the floor."), "ten_forward")
    nudged = ambience.acoustic_fingerprint(
        _room_scene("Bare stone cell, iron door, straw on the cold floor."),
        "ten_forward")
    other = ambience.acoustic_fingerprint(
        _room_scene("A busy market square, fountains, gulls overhead."), "ten_forward")
    assert ambience.fingerprint_similarity(base, nudged) >= ambience._REUSE_SIMILARITY
    assert ambience.fingerprint_similarity(base, other) < ambience._REUSE_SIMILARITY


def test_a_near_identical_room_adopts_the_bed_already_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    monkeypatch.setattr(ambience, "branch_lineage", lambda cid: [])
    monkeypatch.setattr(ambience, "ambience_settings", lambda: {
        "source": "local", "library": "", "licenses": [], "key": "",
        "enabled": True, "configured": True})
    monkeypatch.setattr(ambience, "resolve_local", lambda rel, library=None: "/x/%s" % rel)
    fingerprint = ambience.acoustic_fingerprint(
        _room_scene("Bare stone cell, iron door, straw on the floor."), "ten_forward")
    ambience._write_manifest(1, "oldsig", {
        "room": "Cell", "rejected": [], "fingerprint": fingerprint,
        "layers": [{"role": "tone", "gain": 1.0, "query": "cell stone ambience",
                    "source": "local", "path": "cell.wav", "title": "cell.wav"}]})

    nudged = ambience.acoustic_fingerprint(
        _room_scene("Bare stone cell, iron door, straw on the cold floor."),
        "ten_forward")
    twin = ambience.reusable_manifest(1, nudged)
    assert twin and twin["layers"][0]["path"] == "cell.wav"
    # ...and the fingerprint travels with it, so the next small change can
    # adopt it in turn rather than drifting one edit at a time into a re-fetch.
    assert twin["fingerprint"] == fingerprint
    # A different place gets nothing.
    far = ambience.acoustic_fingerprint(
        _room_scene("A busy market square, fountains, gulls."), "ten_forward")
    assert ambience.reusable_manifest(1, far) is None


def test_reuse_ignores_pins_and_one_shots(tmp_path, monkeypatch):
    """A pin is one room's explicit instruction and a one-shot is not a bed;
    neither may be adopted by a room that merely looks similar."""
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    monkeypatch.setattr(ambience, "branch_lineage", lambda cid: [])
    fingerprint = ambience.acoustic_fingerprint(_room_scene("Bare stone cell."),
                                                "ten_forward")
    for signature in ("pinabc", "fxthunder"):
        ambience._write_manifest(1, signature, {
            "room": "Cell", "fingerprint": fingerprint,
            "layers": [{"source": "local", "path": "x.wav"}]})
    assert ambience.reusable_manifest(1, fingerprint) is None


# --- silence as an answer ---------------------------------------------------
#
# The job is a bed TRUE TO THE ROOM, not a bed at any cost: a sealed vault that
# is given a room tone has been described wrongly. These pin the boundary
# between "this place has no sound" and the two things it must never become --
# a model that could not think of keywords, and a model quietly overruling a
# physical fact the engine derived.

@pytest.fixture
def model_says(monkeypatch):
    """Stub the ambience_prompt role with one canned answer.

    `get_prompt` is stubbed too, and that is not a detail. `refine_layers`
    wraps the whole model call -- prompt fetch included -- in a bare `except`
    that returns the draft plan unchanged, which is right in production (a
    nicety, never a dependency) and silent in a test. Reading the prompt hits
    the database, so on a checkout with no populated `engine.db` every test
    here took the fallback: three failed, and the two asserting the plan is
    UNCHANGED passed while exercising nothing at all. Stubbing the fetch keeps
    these about `refine_layers`'s own logic and makes them true anywhere.
    """
    def install(answer):
        import agents.common
        from llm import prompts
        from llm import providers
        monkeypatch.setattr(providers, "resolve_role_candidates",
                            lambda role: [("x", "y")])
        monkeypatch.setattr(prompts, "get_prompt", lambda *a, **kw: "stub")
        monkeypatch.setattr(
            agents.common, "_agent_json",
            lambda *a, **kw: (_ for _ in ()).throw(answer)
            if isinstance(answer, Exception) else answer)
    return install


def _draft(weather=False):
    plan = [{"role": "tone", "query": "stone chamber ambience", "gain": 1.0}]
    if weather:
        plan.append({"role": "weather", "query": "rain ambience loop", "gain": 0.4})
    return plan


def test_the_model_may_declare_a_room_silent(model_says):
    model_says({"silent": True, "reason": "a sealed stone vault in still air"})
    plan, verdict = ambience.refine_layers(_draft(), {"name": "Vault"})
    assert plan == []
    assert verdict["silent"] is True
    assert verdict["reason"] == "a sealed stone vault in still air"


def test_silence_does_not_reach_the_weather(model_says):
    """How far the sky carries into a room is a fact the engine derived from
    the room graph. A language model has no standing to overrule it, so a
    silent verdict drops the room's own tone and leaves the rain."""
    model_says({"silent": True, "reason": "sealed"})
    plan, verdict = ambience.refine_layers(_draft(weather=True), {"name": "Cellar"})
    assert verdict["silent"] is True
    assert [layer["role"] for layer in plan] == ["weather"]
    assert plan[0]["gain"] == 0.4


def test_an_empty_layer_list_is_not_a_declaration_of_silence(model_says):
    """An empty list is what a confused answer looks like; silence is a flag.
    Conflating them would silence rooms on a malformed reply."""
    model_says({"layers": []})
    plan, verdict = ambience.refine_layers(_draft(), {"name": "Hall"})
    assert not verdict.get("silent")
    assert plan == _draft()


def test_a_failed_call_leaves_the_plan_alone(model_says):
    model_says(RuntimeError("provider down"))
    plan, verdict = ambience.refine_layers(_draft(), {"name": "Hall"})
    assert (plan, verdict) == (_draft(), {})


def test_no_model_configured_means_the_deterministic_plan(monkeypatch):
    """The feature has to work with no extra model call at all -- and with no
    model there is nobody to judge a room silent."""
    from llm import providers
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: (_ for _ in ()).throw(RuntimeError("none")))
    assert ambience.refine_layers(_draft(), {"name": "Hall"}) == (_draft(), {})


def test_a_silent_room_is_cached_like_any_other_answer(tmp_path, monkeypatch):
    """Silence is a RESOLVED state, not a missing one. Written to disk like a
    bed, it settles the room once; treated as a miss, the model would be paid
    for the same judgement on every beat."""
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    monkeypatch.setattr(ambience, "branch_lineage", lambda cid: [])
    ambience._write_manifest(1, "abc123", {
        "room": "Vault", "layers": [], "rejected": [],
        "silent": True, "reason": "a sealed stone vault",
    })
    cached = ambience.cached_ambience(1, "abc123")
    assert cached is not None            # NOT the "no playable layer" miss
    assert cached["silent"] is True
    assert cached["layers"] == []
    assert cached["rev"] == 0


def test_rerolling_a_silent_room_overrules_the_verdict(tmp_path, monkeypatch):
    """🎲 on a silent room is the host saying "give me something anyway". It
    must not re-ask the model, which would answer "silent" again and make the
    button do nothing."""
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    monkeypatch.setattr(ambience, "branch_lineage", lambda cid: [])
    monkeypatch.setattr(ambience, "ambience_settings", lambda: {
        "source": "local", "library": "", "licenses": [], "key": "",
        "enabled": True, "configured": True})
    ambience._write_manifest(1, "sig000", {
        "room": "Vault", "layers": [], "rejected": [],
        "silent": True, "reason": "a sealed vault in still air"})
    monkeypatch.setattr(ambience, "build_ambience_request", lambda *a, **kw: {
        "room": "vault", "room_name": "Vault", "signature": "sig000",
        "pin": None, "cached": ambience.cached_ambience(1, "sig000"),
        "place": {"name": "Vault", "desc": "Bare stone."}, "weather": None})
    asked = []
    monkeypatch.setattr(ambience, "refine_layers",
                        lambda layers, place: (asked.append(place), (layers, {}))[1])
    monkeypatch.setattr(
        ambience, "search_candidates",
        lambda query, source=None, limit=8, avoid="", rank_query="", no_music=False:
        [{"source": "local", "path": "vault.wav", "title": "vault.wav", "fit": 1}])
    monkeypatch.setattr(
        ambience, "_materialize",
        lambda cid, sig, index, choice, role="tone", gain=1.0, query="":
        {"role": role, "gain": gain, "query": query, "source": "local",
         "path": choice["path"], "title": choice["title"]})

    out = ambience.resolve_ambience(1, 0, reroll=True)
    assert asked == []                       # the model was not consulted again
    assert not out.get("silent")
    assert [layer["path"] for layer in out["layers"]] == ["vault.wav"]
    # The refusal is in the ledger, so `rev` -- and the token the player
    # crossfades on -- moves. Without it the new bed arrives under the token
    # that is already playing and the client waits for a change forever.
    assert "silent" in out["rejected"]


def test_media_types_cover_every_accepted_extension():
    for ext in ambience.AUDIO_EXTENSIONS:
        assert ambience.media_type_for("x" + ext) != "application/octet-stream"


def test_local_library_default_is_inside_the_repo():
    assert os.path.basename(ambience.DEFAULT_LIBRARY_DIR) == "ambience_library"


# --- layers ----------------------------------------------------------------

def test_weather_is_its_own_layer_at_its_own_level():
    """The reason layering earns its keep: rain heard two rooms in is a QUIET
    rain layer over an UNDIMINISHED room tone. One clip cannot say that."""
    from dressing.ambience import compose_layers
    from world.weather import weather_for_room
    scene = {
        "weather": {"precipitation": "rain", "intensity": "heavy"},
        "rooms": {"parlour": {"name": "Parlour", "desc": "A fire and old chairs.",
                              "exposure": "enclosed"}},
    }
    place = room_soundscape(scene, "parlour")
    scoped = weather_for_room(scene, "parlour")
    layers = compose_layers(place, None, scoped)

    assert [layer["role"] for layer in layers] == ["tone", "weather"]
    assert layers[0]["gain"] == 1.0                  # the room is undiminished
    assert 0 < layers[1]["gain"] < 1.0               # the rain is not
    # ...and the tone layer must not also be asking for rain, or the mix says
    # the same thing twice.
    assert "rain" not in layers[0]["query"]
    assert "rain" in layers[1]["query"]


def test_a_room_with_no_weather_is_a_single_layer():
    from dressing.ambience import compose_layers
    scene = {"rooms": {"hall": {"name": "Hall", "desc": "Panelled walls."}}}
    layers = compose_layers(room_soundscape(scene, "hall"))
    assert len(layers) == 1 and layers[0]["role"] == "tone"


def test_old_single_track_manifests_still_play():
    """Written before layering existed, still on disk in every install that ran
    the first version -- and in branch ancestors, which are read in place and
    never rewritten."""
    from dressing.ambience import _as_layered
    old = {"source": "local", "path": "rain.ogg", "title": "rain.ogg",
           "query": "rain ambience"}
    layered = _as_layered(old)
    assert len(layered["layers"]) == 1
    assert layered["layers"][0]["path"] == "rain.ogg"
    assert layered["layers"][0]["gain"] == 1.0
    assert layered["layers"][0]["role"] == "tone"


def test_a_mix_can_be_pinned_with_its_levels(tmp_path, monkeypatch):
    """"This hall is a room tone at full and a fountain at a third" is
    something a host must be able to state and keep."""
    from dressing import ambience as amb
    saved = {}
    monkeypatch.setattr(amb, "wget", lambda cid, key, default=None: saved.get(key, default))
    monkeypatch.setattr(amb, "wset", lambda cid, key, value: saved.__setitem__(key, value))
    pin = amb.set_ambience_pin(1, "hall", {"layers": [
        {"source": "local", "path": "rooms/hall.ogg", "gain": 1.0},
        {"source": "local", "path": "water/fountain.ogg", "gain": 0.33},
    ]})
    assert [layer["gain"] for layer in pin["layers"]] == [1.0, 0.33]
    assert [layer["role"] for layer in pin["layers"]] == ["tone", "extra"]
    assert amb.ambience_pin_for(1, "hall")["layers"][1]["path"] == "water/fountain.ogg"


def test_a_single_sound_pin_is_still_accepted():
    """The shape the first version wrote, still in live saves."""
    from dressing import ambience as amb
    saved = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(amb, "wget", lambda cid, key, default=None: saved.get(key, default))
        mp.setattr(amb, "wset", lambda cid, key, value: saved.__setitem__(key, value))
        pin = amb.set_ambience_pin(1, "hall", {"source": "local", "path": "a/b.ogg"})
        assert pin["source"] == "local"
        assert amb.ambience_pin_for(1, "hall")["path"] == "a/b.ogg"


def test_a_mix_is_capped():
    """Past three the layers stop being a place and start being a noise floor,
    and every one is another fetch and another decoder."""
    from dressing import ambience as amb
    saved = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(amb, "wget", lambda cid, key, default=None: saved.get(key, default))
        mp.setattr(amb, "wset", lambda cid, key, value: saved.__setitem__(key, value))
        pin = amb.set_ambience_pin(1, "hall", {"layers": [
            {"source": "local", "path": "a/%d.ogg" % i} for i in range(6)]})
    assert len(pin["layers"]) == amb.MAX_LAYERS


class TestAPinResolvesTheSoundItPinned:
    """Live failure, story "Escaping the rain": a pinned two-layer soundscape
    played the same unrelated recording on both layers.

    A pin stores a sound's IDENTITY, not its preview URL -- a URL would expire.
    Resolving that identity went through the text search as `id:341802`, and
    Freesound's search has no `id` field, so it matched the string as free text
    and returned a sound literally named "file_id.diz.mp3" -- the same wrong
    sound for every id ever asked for. Both layers therefore downloaded one
    file, byte for byte, and the room played it twice against itself.
    """

    def _pin(self):
        return {"layers": [
            {"source": "freesound", "id": 852349, "role": "tone",
             "title": "canal ambience"},
            {"source": "freesound", "id": 341802, "role": "weather",
             "title": "Rain.wav", "gain": 0.85},
        ]}

    def test_each_layer_fetches_its_own_sound(self, tmp_path, monkeypatch):
        from dressing import ambience as amb

        by_id = {
            852349: {"id": 852349, "title": "canal ambience",
                     "preview": "https://x/852349.mp3"},
            341802: {"id": 341802, "title": "Rain.wav",
                     "preview": "https://x/341802.mp3"},
        }
        fetched = []
        monkeypatch.setattr(amb, "AMBIENCE_DIR", str(tmp_path))
        monkeypatch.setattr(amb, "freesound_sound",
                            lambda sid, key=None: by_id.get(int(sid)))
        # The search endpoint must not be consulted for a known id at all.
        # Its positive control is the test below: an UNPINNED query with the
        # same stub installed must reach it, or "the pinned path did not
        # search" is a claim about a stub nobody calls.
        monkeypatch.setattr(amb, "search_freesound", lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a pinned id must not go through the text search")))
        monkeypatch.setattr(amb, "_fetch_preview",
                            lambda cid, sig, url, index=0, expect_id=None: (
                                fetched.append((url, expect_id)),
                                "%s-%d.mp3" % (sig, index))[1])
        monkeypatch.setattr(amb, "_write_manifest",
                            lambda cid, sig, manifest: manifest)

        manifest = amb._pin_manifest(7, "pinsig", self._pin(), "sheltered path")
        # The id each layer claims travels with the fetch, so a preview that
        # belongs to a different sound is refused rather than cached.
        assert fetched == [("https://x/852349.mp3", 852349),
                           ("https://x/341802.mp3", 341802)]
        assert [l["id"] for l in manifest["layers"]] == [852349, 341802]
        assert [l["role"] for l in manifest["layers"]] == ["tone", "weather"]
        # Distinct files. One name for two layers is the bug itself.
        assert len({l["file"] for l in manifest["layers"]}) == 2

    def test_an_unpinned_query_does_reach_the_text_search(self, monkeypatch):
        """The positive control for the throw-stub above.

        The pinned test asserts an absence -- `search_freesound` was not
        called -- and an absence is also what a stub on a name nothing reads
        produces. This installs the same stub and takes the ordinary path,
        which must reach it.
        """
        from dressing import ambience as amb

        calls = []
        monkeypatch.setattr(amb, "ambience_settings",
                            lambda: {"source": "freesound"})
        monkeypatch.setattr(amb, "search_freesound",
                            lambda query, **kw: calls.append(query) or [])

        amb.search_candidates("rain on a canal")
        assert calls == ["rain on a canal"], (
            "an unpinned query did not reach search_freesound: the stub the "
            "pinned test installs cannot fire")

    def test_a_missing_sound_is_an_error_not_a_wrong_sound(
            self, tmp_path, monkeypatch):
        """Better to fail than to quietly substitute something else -- which is
        precisely what the text-search fallback did."""
        from dressing import ambience as amb
        import pytest

        monkeypatch.setattr(amb, "AMBIENCE_DIR", str(tmp_path))
        monkeypatch.setattr(amb, "freesound_sound", lambda sid, key=None: None)
        with pytest.raises(RuntimeError, match="no preview"):
            amb._materialize(7, "sig", 0, {"source": "freesound", "id": 999999})


class TestTheFetchRefusesTheWrongSound:
    """The class of bug, not just the instance. Fetching by id fixed the cause
    of the pin failure; this catches a mismatched preview whatever produced it,
    because a wrong file written into the cache persists and is
    indistinguishable from a badly chosen one."""

    def test_a_preview_url_names_its_own_sound(self):
        from dressing import ambience as amb

        assert amb.preview_sound_id(
            "https://cdn.freesound.org/previews/341/341802_1511977-hq.mp3") == 341802
        assert amb.preview_sound_id(
            "https://cdn.freesound.org/previews/165/165866_2103589-lq.ogg") == 165866

    def test_a_url_that_does_not_say_is_not_evidence(self):
        """An unrecognised preview format must not take the feature down the
        day Freesound changes its CDN paths."""
        from dressing import ambience as amb

        assert amb.preview_sound_id("https://example.com/whatever.mp3") is None
        assert amb.preview_sound_id("") is None
        assert amb.preview_sound_id(None) is None

    def test_a_mismatched_preview_is_refused(self, tmp_path, monkeypatch):
        from dressing import ambience as amb
        import pytest

        monkeypatch.setattr(amb, "AMBIENCE_DIR", str(tmp_path))
        with pytest.raises(RuntimeError, match="preview mismatch"):
            amb._fetch_preview(
                1, "sig",
                "https://cdn.freesound.org/previews/165/165866_2103589-hq.mp3",
                index=1, expect_id=341802)
        # Nothing was written: the refusal happens before the request.
        assert not list(tmp_path.rglob("*.mp3"))

    def test_an_unknown_url_shape_is_still_fetched(self, tmp_path, monkeypatch):
        from dressing import ambience as amb

        monkeypatch.setattr(amb, "AMBIENCE_DIR", str(tmp_path))

        class _Response:
            content = b"audio"
            def raise_for_status(self): pass

        import requests
        monkeypatch.setattr(requests, "get", lambda *a, **k: _Response())
        name = amb._fetch_preview(1, "sig", "https://example.com/x.mp3",
                                  index=1, expect_id=341802)
        assert name == "sig-1.mp3"

    def test_the_by_id_endpoint_is_held_to_its_answer(self, monkeypatch):
        from dressing import ambience as amb
        import pytest

        class _Response:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"id": 165866, "name": "file_id.diz.mp3",
                        "previews": {"preview-hq-mp3": "https://x/165866_1-hq.mp3"}}

        import requests
        monkeypatch.setattr(requests, "get", lambda *a, **k: _Response())
        monkeypatch.setattr(amb, "ambience_settings", lambda: {"key": "k"})
        with pytest.raises(RuntimeError, match="when asked for"):
            amb.freesound_sound(341802)


class TestTheResolutionLockTable:
    """Ambience is the backdrop module's twin, and it inherited the twin's leak:
    a lock per signature, pruned by nothing, one dead entry per distinct
    AUDIBLE room-state for the life of the process. Measured on the unmodified
    module: 500 distinct signatures, 500 entries, no work in flight.
    """

    def test_it_does_not_grow_with_the_number_of_room_states_seen(self):
        from dressing import ambience as amb

        for i in range(500):
            with amb._resolution_lock((1, "sig%04d" % i)):
                pass

        assert len(amb._AMB_LOCKS) == 0

    def test_one_signature_is_still_resolved_once(self):
        """Pruning must not cost the exclusion the lock exists for: two callers
        for one room would otherwise both search and both download.
        """
        import threading

        from dressing import ambience as amb

        order = []
        holding = threading.Event()
        release = threading.Event()

        def first():
            with amb._resolution_lock((1, "shared")):
                order.append("first")
                holding.set()
                release.wait(3.0)
                order.append("first-out")

        def second():
            holding.wait(3.0)
            with amb._resolution_lock((1, "shared")):
                order.append("second")

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for t in threads:
            t.start()
        assert holding.wait(3.0)
        release.set()
        for t in threads:
            t.join(3.0)

        assert order == ["first", "first-out", "second"]
        assert len(amb._AMB_LOCKS) == 0


class TestErrorKind:
    """A search that concluded "there is nothing" and a provider that fell
    over were one string to the client -- "TypeName: message" out of the
    queue's error table -- so the toast either showed a reader a Python type
    name or one message for both. The kind is derived HERE, beside the class
    whose name it reads, and travels as its own payload field.
    """

    def _fail_with(self, exc):
        import time

        from dressing import ambience as amb

        amb._QUEUE.reset()
        sig = "kind-test-signature"

        def boom(work):
            raise exc

        amb._QUEUE.submit(sig, boom)
        deadline = time.monotonic() + 3.0
        while amb._QUEUE.status(sig) == "pending" and time.monotonic() < deadline:
            time.sleep(0.01)
        try:
            return amb.ambience_error_kind(sig)
        finally:
            amb._QUEUE.reset()

    def test_a_concluded_empty_search_is_notfound(self):
        kind = self._fail_with(
            ambience.AmbienceNotFound("No ambience found for: quiet vault"))
        assert kind == "notfound"

    def test_a_provider_failure_is_failed(self):
        kind = self._fail_with(RuntimeError("provider fell over"))
        assert kind == "failed"

    def test_no_failure_on_record_is_no_kind(self):
        from dressing import ambience as amb

        amb._QUEUE.reset()
        assert amb.ambience_error_kind("never-seen") is None

    def test_an_exhausted_search_raises_the_notfound_type(self, monkeypatch):
        """The raise itself must be the typed one: a plain RuntimeError here
        would silently reclassify "no sound exists" as a malfunction and the
        client would blacklist-and-alarm for an ordinary empty answer."""
        monkeypatch.setattr(ambience, "search_candidates", lambda *a, **kw: [])
        monkeypatch.setattr(ambience, "ambience_settings",
                            lambda: {"source": "freesound", "configured": True,
                                     "enabled": True})
        with pytest.raises(ambience.AmbienceNotFound):
            ambience.resolve_oneshot(1, "thunder")
