"""The deterministic floor said one thing and the code underneath did another.

Perception-audit defect register 05 (branch wave2-build1), four leak-class
defects, each the same anatomy: the graded fact is computed somewhere in
`spatial.py` and the production delivery site consumes a coarser projection of
it -- a flag nothing sets, a parameter nothing passes, a light read from the
wrong room, a fallback that fails open.

L2  `spatial_rel_between` is the only setter of the enclosure direction flags
    (`inside_source` / `enclosed_from_source` / `source_enclosed`) and had zero
    production callers, so `hear_level`'s and `scent_level`'s enclosure guards
    could not fire: a voice sealed inside a body reached the whole room at full
    clarity, and an enclosed perceiver heard/smelled the room it was sealed
    away from. Fixed by making `spatial_rel_between` the production relation
    builder (`_source_channels`, the onset perceiver build, the outcome
    fallback rel, the micro-loop, background hearing).

L3  `_dialogue_hear_level` took no proximity, so the OUTCOME injection floor
    delivered a mutter across a great hall at full volume while the onset
    floor, two hundred lines away, applied the downgrade.

L6  `spatial_rel` stamps the light of its SECOND argument (the room being
    looked at); the onset build and the micro-loop passed (actor, observer),
    grading sight OF the actor by the light in the OBSERVER's room -- a full
    visual channel to an actor standing in darkness.

L7  `visible_adjacent_rooms` gated on sight barriers only: a pitch-dark
    neighbour's authored description was shipped as literal sight.

L8  `_audience_map` set level "full" for an unresolvable room -- while its
    sibling `_beat_for_presence` fails closed on exactly that uncertainty, and
    the comment claimed the two matched.

Every fix SUBTRACTS (AGENTS.md, Information boundaries): each assertion below
that expects delivery is the guard against over-subtraction, and each that
expects silence is the leak.
"""

from __future__ import annotations

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

from agents.background import _audience_map
from agents.loops import deterministic_micro_perception
from agents.perception import _dialogue_hear_level, _source_channels
from world.spatial import hear_level, visible_adjacent_rooms


OCCUPANT = "Wren"
HOST = "Vessel"
HOST_ID = "vessel_entity"
BYSTANDER = "Dana"


def _enclosure_scene():
    """One hall. Wren is sealed inside Vessel (a body), Dana stands by."""
    return {
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {OCCUPANT: "hall", HOST: "hall", BYSTANDER: "hall"},
        "entities": {HOST_ID: {"name": HOST, "kind": "person", "aliases": []}},
        # `_is_body_entity`: bodies wear things and have a size.
        "attire": {HOST: {}, OCCUPANT: {}},
        "scales": {OCCUPANT: 0.05},
        "contained": {OCCUPANT: {"in": HOST_ID, "mode": "inside"}},
    }


# --- L2: the enclosure flags must reach the production relation maps --------

class TestSourceChannelsCarriesEnclosureDirections:
    def test_a_sealed_voice_does_not_reach_the_room_full(self):
        """Register assertion (a): a `normal` line spoken by the enclosed body
        arrives at a bystander at <= fragment through the production
        channel-building path -- not by calling spatial_rel_between directly."""
        sc = _enclosure_scene()
        ch = _source_channels(sc, BYSTANDER, "hall",
                              [{"name": OCCUPANT, "room": "hall"}])
        rel = ch["spatial_to_sources"][OCCUPANT]
        assert hear_level(rel, "normal") == "fragment"
        assert hear_level(rel, "mutter") == "none"

    def test_an_enclosed_perceiver_does_not_hear_the_room(self):
        """Register assertion (b): a `normal` line spoken by the bystander
        arrives at the enclosed body as none -- the mass around them is the
        wall the same-room shortcut used to walk through."""
        sc = _enclosure_scene()
        ch = _source_channels(sc, OCCUPANT, "hall",
                              [{"name": BYSTANDER, "room": "hall"}])
        rel = ch["spatial_to_sources"][BYSTANDER]
        assert hear_level(rel, "normal") == "none"
        assert hear_level(rel, "shout") == "fragment"

    def test_scent_points_the_right_way_in_both_directions(self):
        """Register assertion (c): scent from the bystander to the enclosed
        body is none; scent from the enclosure itself is full -- the one body
        that should drown out everything."""
        sc = _enclosure_scene()
        ch = _source_channels(sc, OCCUPANT, "hall",
                              [{"name": BYSTANDER, "room": "hall"},
                               {"name": HOST, "room": "hall"}])
        assert ch["scent_channel_to_sources"][BYSTANDER] == "none"
        assert ch["scent_channel_to_sources"][HOST] == "full"

    def test_an_ordinary_same_room_source_is_untouched(self):
        """Over-subtraction guard: no enclosure, no change."""
        sc = _enclosure_scene()
        ch = _source_channels(sc, BYSTANDER, "hall",
                              [{"name": HOST, "room": "hall"}])
        rel = ch["spatial_to_sources"][HOST]
        assert hear_level(rel, "normal") == "full"
        assert ch["scent_channel_to_sources"][HOST] == "full"


class TestManifestTellsRespectTheEnclosure:
    def _run(self, source_name):
        from types import SimpleNamespace
        from agents.perception import _delivered_manifest
        sc = _enclosure_scene()
        ctx = SimpleNamespace(character_results={
            1: {"manifest": {
                "surface_demeanor": "outwardly calm",
                "tells": [{"channel": "voice",
                           "cue": "a tremor under the vowels",
                           "subtlety": 0.0}]}}})
        return _delivered_manifest(
            ctx, sc, BYSTANDER,
            [{"name": source_name, "room": "hall"}],
            {BYSTANDER: [source_name]}, {source_name: 1})

    def test_a_voice_tell_does_not_cross_a_body_seal(self):
        """`audible` was bare same_room, and an enclosed body's position
        derives to its carrier's room -- so a breath/voice tell crossed a
        seal that muffles the voice itself to a fragment (L2)."""
        assert self._run(OCCUPANT) == {}

    def test_a_co_present_voice_tell_still_delivers(self):
        out = self._run(HOST)
        assert "a tremor under the vowels" in (out.get(HOST) or {}).get(
            "cues", [])


# --- L3: the outcome dialogue floor honours proximity -----------------------

class TestDialogueHearLevelProximity:
    def test_a_mutter_does_not_cross_a_great_hall(self):
        rel = {"same_room": True, "barrier": "open", "distance": "same"}
        entry = {"volume": "mutter"}
        assert _dialogue_hear_level(entry, rel, BYSTANDER,
                                    proximity="across") == "none"
        assert _dialogue_hear_level(entry, rel, BYSTANDER,
                                    proximity="near") == "fragment"

    def test_unknown_proximity_preserves_the_old_answer(self):
        """`near` is mostly a DEFAULT, not a measurement (6.7% of bodies carry
        a station) -- so absent proximity must keep pre-fix behaviour, and a
        normal line is never downgraded by any tier."""
        rel = {"same_room": True, "barrier": "open", "distance": "same"}
        assert _dialogue_hear_level({"volume": "mutter"}, rel, BYSTANDER) == "full"
        assert _dialogue_hear_level({"volume": "normal"}, rel, BYSTANDER,
                                    proximity="across") == "full"

    def test_the_comm_rescue_still_works(self):
        remote = {"same_room": False, "barrier": "separated", "distance": "remote"}
        entry = {"volume": "normal", "intended_target": BYSTANDER,
                 "medium": "comm"}
        assert _dialogue_hear_level(entry, remote, BYSTANDER,
                                    proximity=None) == "full"

    def test_the_shape_rescue_does_not_pierce_an_enclosure(self):
        """The by-name shape floor exists because a barrier plus a by-name
        exchange implies a comm channel. An enclosure implies no such thing:
        being named by a voice beyond the mass around you creates no channel
        through it. Explicit medium:'comm' still crosses (a radio in a
        pocket works)."""
        sealed = {"same_room": True, "enclosed_from_source": True}
        named = {"volume": "normal", "intended_target": OCCUPANT}
        assert _dialogue_hear_level(named, sealed, OCCUPANT) == "none"
        assert _dialogue_hear_level({**named, "medium": "comm"},
                                    sealed, OCCUPANT) == "full"


# --- L7: a dark neighbour is not literal sight -------------------------------

class TestVisibleAdjacentRoomsLightGate:
    def _scene(self):
        return {
            "rooms": {
                "hall": {
                    "name": "Hall", "notes": "A long hall.",
                    "adjacent": [
                        {"to": "cellar", "barrier": "open_door"},
                        {"to": "parlor", "barrier": "open_door"},
                    ],
                },
                # No reverse edge: nothing spills in, the dark is total.
                "cellar": {"name": "Cellar", "light": "dark",
                           "notes": "Racks of dusty bottles line the walls.",
                           "adjacent": []},
                "parlor": {"name": "Parlor",
                           "notes": "Overstuffed chairs face a cold hearth.",
                           "adjacent": []},
            },
            "positions": {},
        }

    def test_a_pitch_dark_neighbour_is_withheld(self):
        got = {r["room_id"] for r in visible_adjacent_rooms(self._scene(), "hall")}
        assert "cellar" not in got

    def test_a_lit_neighbour_is_still_shipped(self):
        got = {r["room_id"]: r for r in
               visible_adjacent_rooms(self._scene(), "hall")}
        assert "parlor" in got
        assert "hearth" in got["parlor"]["description"]

    def test_reverse_declared_dark_neighbour_is_withheld_too(self):
        """The reverse-adjacency loop had the same hole."""
        sc = self._scene()
        sc["rooms"]["hall"]["adjacent"] = []
        sc["rooms"]["cellar"]["adjacent"] = [
            {"to": "hall", "barrier": "open_door"}]
        # With the hall lit, its light spills through the cellar's own
        # declared doorway: effective_light says dim, and dim (shapes) is
        # not withheld -- only total dark is. Documented tier choice.
        got = {r["room_id"] for r in visible_adjacent_rooms(sc, "hall")}
        assert "cellar" in got
        # An unlit hall spills nothing: the cellar is truly dark, and the
        # reverse-adjacency loop must withhold it exactly like the forward
        # one.
        sc["rooms"]["hall"]["light"] = "dark"
        got = {r["room_id"] for r in visible_adjacent_rooms(sc, "hall")}
        assert "cellar" not in got


# --- L8: the scene-manager audience fails closed ------------------------------

class TestAudienceMapFailsClosed:
    SC = {"rooms": {"r": {"name": "R", "adjacent": []}},
          "positions": {"Rex": "r", "Barkeep": "r"}}

    def test_an_unplaceable_presence_receives_nothing(self):
        entry = {"speaker": "Rex", "volume": "normal"}
        aud = _audience_map(self.SC, entry, [(1, "Ghost", {}, None)], "solo")
        # Fail closed: either the event is refused outright or the presence
        # gets none -- never "full" on unresolvable geometry.
        assert aud is None or aud.get("Ghost") == "none"

    def test_an_unplaceable_speaker_delivers_nothing(self):
        entry = {"speaker": "Nobody Known", "volume": "normal"}
        aud = _audience_map(self.SC, entry,
                            [(1, "Barkeep", {}, "r")], "solo")
        assert aud is None or aud.get("Barkeep") == "none"

    def test_placed_co_present_hearing_is_untouched(self):
        entry = {"speaker": "Rex", "volume": "normal"}
        aud = _audience_map(self.SC, entry,
                            [(1, "Barkeep", {}, "r")], "solo")
        assert aud == {"Barkeep": "full"}


# =============================================================================
# Integration: the production paths themselves (temp_db)
# =============================================================================

def _make_ctx(temp_db, scene, npcs=("Dr. Moon",), player="Hinami"):
    sheet = default_persona_data(player)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (player, json.dumps(sheet), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("T", "", time.time(), persona_id))
    ids = {}
    for n in npcs:
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (n, json.dumps(default_character_data(n)), "{}", time.time(),
             f"char_{n.lower().replace(' ', '_').replace('.', '')}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, cid, "active", "{}"))
        ids[n] = cid
    temp_db.wset(chat_id, "scene", scene)
    known = {player: list(npcs)}
    for n in npcs:
        known[n] = [player] + [m for m in npcs if m != n]
    temp_db.wset(chat_id, "known", known)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    return ctx, ids


def _stub_empty_views(monkeypatch):
    """Kept as a no-op so these tests read as they always did.

    They were written to force the deterministic path by stubbing the model
    out, on the principle that whatever leaked was then the floor's doing.
    That is now the only path there is, so there is nothing to stub — but
    the intent, and every assertion below it, is unchanged.
    """
    return None


# --- L3 through perception_outcome ------------------------------------------

class TestOutcomeFloorProximity:
    def _scene(self):
        return {
            "location": "the hall", "time": "day",
            "rooms": {"room1": {"name": "Great Hall", "size": "large",
                                # Real anchors: normalize_scene_stations
                                # blanks an `at` naming an anchor the room
                                # does not declare, which is itself the
                                # "default is not a measurement" guard.
                                "anchors": {"hearth": {"dir": "west"},
                                            "gallery": {"dir": "east"}},
                                "adjacent": []}},
            "positions": {"Hinami": "room1", "Dr. Moon": "room1"},
            "stations": {"Hinami": {"at": "hearth"},
                         "Dr. Moon": {"at": "gallery"}},
            "entities": {}, "attire": {}, "overlays": {}}

    def _run(self, temp_db, monkeypatch, volume, stations=None):
        import agents.perception as perception
        sc = self._scene()
        if stations is not None:
            sc["stations"] = stations
        ctx, ids = _make_ctx(temp_db, sc)
        ctx["_player_room"] = "room1"
        ctx.director_interpret = {"sequence": [],
                                  "flow": {"reactors": [ids["Dr. Moon"]]}}
        ctx.director_resolve = {
            "resolved_event": "Dr. Moon speaks by the far gallery.",
            "dialogue_log": [{"speaker": "Dr. Moon",
                              "exact_quote":
                                  "The vault combination is seventeen nineteen.",
                              "volume": volume, "intended_target": ""}]}
        _stub_empty_views(monkeypatch)
        return perception.perception_outcome(ctx, nonce=0)["views"]["player"]

    def test_a_mutter_across_a_measured_great_hall_is_not_delivered(
            self, temp_db, monkeypatch):
        """1,364 live mutters rode this hole. Both parties hold real stations
        at distinct anchors of a size:'large' room -- 'across' is a
        measurement here, not the ~91%-defaulted 'near'."""
        view = self._run(temp_db, monkeypatch, "mutter")
        assert "vault" not in view.lower()
        assert "seventeen" not in view.lower()

    def test_a_normal_line_still_crosses_the_hall(self, temp_db, monkeypatch):
        view = self._run(temp_db, monkeypatch, "normal")
        assert "seventeen nineteen" in view

    def test_a_mutter_within_reach_is_still_verbatim(self, temp_db, monkeypatch):
        view = self._run(temp_db, monkeypatch, "mutter",
                         stations={"Hinami": {"at": "hearth"},
                                   "Dr. Moon": {"at": "hearth"}})
        assert "seventeen nineteen" in view

    def test_unstationed_mutter_keeps_prior_delivery(self, temp_db, monkeypatch):
        """No stations anywhere -> proximity is None, not a fake 'near': the
        fix must not let the DEFAULT tier silently degrade the ~91% of rooms
        with no station data. (proximity_rel returns 'near' for an
        unstationed pair; hear_level treats near-mutter as fragment -- so the
        call site must pass the measurement only when one exists.)"""
        view = self._run(temp_db, monkeypatch, "mutter", stations={})
        assert "seventeen nineteen" in view


# --- L2 through the outcome injection floor ----------------------------------

class TestOutcomeFloorEnclosedSpeaker:
    def test_a_sealed_voice_arrives_as_fragment_not_verbatim(
            self, temp_db, monkeypatch):
        import agents.perception as perception
        sc = {
            "location": "the hall", "time": "day",
            "rooms": {"room1": {"name": "Hall", "adjacent": []}},
            "positions": {"Hinami": "room1", "Dr. Moon": "room1",
                          HOST: "room1"},
            "entities": {HOST_ID: {"name": HOST, "kind": "person",
                                   "aliases": []}},
            "attire": {HOST: {}, "Dr. Moon": {}},
            "scales": {"Dr. Moon": 0.05},
            "contained": {"Dr. Moon": {"in": HOST_ID, "mode": "inside"}},
            "overlays": {}}
        ctx, ids = _make_ctx(temp_db, sc)
        ctx["_player_room"] = "room1"
        ctx.director_interpret = {"sequence": [],
                                  "flow": {"reactors": [ids["Dr. Moon"]]}}
        ctx.director_resolve = {
            "resolved_event": "A voice comes from inside.",
            "dialogue_log": [{"speaker": "Dr. Moon",
                              "exact_quote": "Nobody expects me to be heard.",
                              "volume": "normal", "intended_target": ""}]}
        _stub_empty_views(monkeypatch)
        view = perception.perception_outcome(ctx, nonce=0)["views"]["player"]
        assert "Nobody expects me to be heard" not in view


# --- L2 through the onset injection floor -------------------------------------

class TestOnsetFloorEnclosedActor:
    def test_a_sealed_players_line_is_not_reinjected_verbatim(
            self, temp_db, monkeypatch):
        import agents.perception as perception
        sc = {
            "location": "the hall", "time": "day",
            "rooms": {"room1": {"name": "Hall", "adjacent": []}},
            "positions": {"Hinami": "room1", "Dr. Moon": "room1",
                          HOST: "room1"},
            "entities": {HOST_ID: {"name": HOST, "kind": "person",
                                   "aliases": []}},
            "attire": {HOST: {}, "Hinami": {}},
            "scales": {"Hinami": 0.05},
            "contained": {"Hinami": {"in": HOST_ID, "mode": "inside"}},
            "overlays": {}}
        ctx, ids = _make_ctx(temp_db, sc)
        ctx["_player_room"] = "room1"
        ctx.director_interpret = {
            "speech": "Nobody expects me to be heard.",
            "speech_volume": "normal",
            "sequence": [{"type": "speech",
                          "text": "Nobody expects me to be heard.",
                          "volume": "normal", "visibility": "overt",
                          "event_id": "e1"}],
            "flow": {"reactors": [ids["Dr. Moon"]], "resolution_flags": {}}}
        _stub_empty_views(monkeypatch)
        view = perception.perception_act(ctx, nonce=0)["views"][
            str(ids["Dr. Moon"])]
        assert "Nobody expects me to be heard" not in view


# --- L6 through the micro-loop and the onset payload ---------------------------

def _two_room_scene(actor_room_light=None, names=("Reya", "Kael")):
    rooms = {
        "room1": {"name": "Lit Room",
                  "adjacent": [{"to": "room2", "barrier": "open_door"}]},
        # Edge declared on room1 only: no reverse edge, so no light spills
        # into room2 and its own light stands.
        "room2": {"name": "Far Room", "adjacent": []},
    }
    if actor_room_light:
        rooms["room2"]["light"] = actor_room_light
    return {
        "location": "x", "time": "day", "rooms": rooms,
        "positions": {names[0]: "room2", names[1]: "room1"},
        "entities": {}, "attire": {}, "overlays": {}}


class TestMicroLoopSightIsGradedByTheActorsLight:
    def _run(self, temp_db, light):
        scene = _two_room_scene(light)
        ctx, ids = _make_ctx(temp_db, scene, npcs=("Reya", "Kael"))
        result = {"sequence": [
            {"type": "action", "attempt": "runs a hand along the shelf",
             "observable": "runs a hand along the shelf",
             "visibility": "overt"},
            {"type": "speech", "text": "Still here.", "volume": "normal",
             "visibility": "overt"}]}
        views, _ = deterministic_micro_perception(
            ctx, ids["Reya"], result, scene)
        return " ".join(views.get(ids["Kael"], []))

    def test_an_actor_in_the_dark_is_not_seen_from_a_lit_room(
            self, temp_db):
        delivered = self._run(temp_db, "dark")
        assert "shelf" not in delivered          # the act is unseen
        assert "Still here" in delivered         # the voice still carries

    def test_an_actor_in_a_lit_room_is_still_seen(self, temp_db):
        delivered = self._run(temp_db, None)
        assert "shelf" in delivered


class TestOnsetPayloadSightIsGradedByTheActorsLight:
    def test_dark_actor_room_yields_no_visual_channel(
            self, temp_db, monkeypatch):
        import agents.perception as perception
        sc = _two_room_scene("dark", names=("Hinami", "Dr. Moon"))
        ctx, ids = _make_ctx(temp_db, sc)
        ctx["_player_room"] = "room2"
        ctx.director_interpret = {
            "sequence": [{"type": "action",
                          "attempt": "feel along the wall",
                          "observable": "feels along the wall",
                          "visibility": "overt", "event_id": "e1"}],
            "flow": {"reactors": [ids["Dr. Moon"]], "resolution_flags": {}}}
        view = perception.perception_act(
            ctx, nonce=0)["views"][str(ids["Dr. Moon"])] or ""
        # The payload field this used to read (`visual_channel_to_actor`)
        # was the model's instruction; the view is the consequence. An
        # actor in a dark room is not seen doing anything.
        assert "feels along the wall" not in view, (
            "a full visual channel was granted to an actor standing in a "
            "dark room -- sight was graded by the OBSERVER's light")
