"""Voice channels: intercoms, PAs, radios, phones.

A channel is equipment that carries a VOICE between places, as distinct from a
doorway between them. Before this existed the engine had one per-LINE rescue --
a dialogue entry tagged `medium: "comm"` reached the observer it explicitly
named -- which covers a phone call to one person and nothing else. It could not
express a PA a whole room hears, a channel switched off mid-scene, a ship's
intercom across four compartments, a radio travelling in its owner's pocket, or
a broadcast that goes one way, because it was a property of one sentence rather
than a standing fact about the world.

The property every test here is really defending: a channel carries VOICE and
nothing else, and a mind that hears someone over one is never told they are
present. That is not decoration. A voice at your shoulder and a voice on a
speaker are different facts, and collapsing them hands a mind a fact it has no
channel for -- through the front door of the layer built to stop exactly that.
"""

from __future__ import annotations

import pytest

from world import spatial as sp
from agents import composer


def _scene(**over):
    scene = {
        "rooms": {
            "observation": {"name": "Observation Room",
                            "adjacent": [{"to": "cell", "barrier": "window"}]},
            "cell": {"name": "Interview Cell",
                     "adjacent": [{"to": "observation", "barrier": "window"}]},
            "street": {"name": "Street"},
            "van": {"name": "Van"},
        },
        "positions": {"Sarah Moon": "observation", "guard_1": "observation",
                      "Hinami": "cell", "Vela": "van", "Passerby": "street"},
        "comms": {},
    }
    scene.update(over)
    return scene


def _link(scene, speaker, listener):
    return sp.comms_link(
        scene, sp.room_of(scene, speaker), sp.room_of(scene, listener),
        speaker_name=speaker, observer_name=listener)


def _percept(scene, speaker, listener, text="State your designation.",
             volume="normal"):
    rel = sp.spatial_rel(scene, sp.room_of(scene, listener),
                         sp.room_of(scene, speaker))
    channel = _link(scene, speaker, listener)
    if channel:
        rel = {**rel, "comm_channel": channel}
    entry = {"speaker": speaker, "text": text, "exact_quote": text,
             "volume": volume}
    return composer.speech_percept(
        entry, rel, listener, display=speaker,
        can_see=sp.sight_level(rel) != "none")


# ---------------------------------------------------------------- the ledger


class TestTheLedger:
    def test_a_fixed_installation_joins_two_rooms(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "name": "the cell intercom",
            "rooms": ["observation", "cell"]}])
        assert _link(scene, "Sarah Moon", "Hinami")
        assert _link(scene, "Hinami", "Sarah Moon"), "duplex answers back"

    def test_a_broadcast_is_genuinely_one_way(self):
        """The asymmetry `_VALID_BARRIERS` refuses for doorways, and should.

        A barrier belongs to the doorway rather than to the side you stand on.
        A transmitter and a receiver are different equipment, so the same rule
        would be wrong here.
        """
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "pa", "name": "the PA", "rooms": ["observation", "cell"],
            "mode": "broadcast", "source": "observation"}])
        assert _link(scene, "Sarah Moon", "Hinami")
        assert _link(scene, "Hinami", "Sarah Moon") is None

    def test_a_broadcast_with_no_transmitter_falls_back_to_duplex(self):
        """Guessing which way a one-way channel points is how a voice ends up
        somewhere it never went."""
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "pa", "rooms": ["observation", "cell"],
            "mode": "broadcast", "source": "somewhere_else"}])
        assert scene["comms"]["pa"]["mode"] == "duplex"
        assert scene["comms"]["pa"]["source"] == ""

    def test_live_is_a_switch_and_a_fact_about_the_world(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "rooms": ["observation", "cell"]}])
        assert _link(scene, "Sarah Moon", "Hinami")

        sp.apply_comms_ops(scene, [{"id": "cell_intercom", "op": "close"}])
        assert _link(scene, "Sarah Moon", "Hinami") is None

        sp.apply_comms_ops(scene, [{"id": "cell_intercom", "op": "open"}])
        assert _link(scene, "Sarah Moon", "Hinami")

    def test_closing_does_not_forget_who_was_on_it(self):
        """`open`/`close` flip a switch; only `set` restates the endpoints."""
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "net", "name": "ship comm", "rooms": ["observation", "cell"]}])
        sp.apply_comms_ops(scene, [{"id": "net", "op": "close"}])
        assert scene["comms"]["net"]["rooms"] == ["observation", "cell"]
        assert scene["comms"]["net"]["name"] == "ship comm"

    def test_removing_takes_the_equipment_out_of_the_world(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{"id": "net", "rooms": ["observation", "cell"]}])
        sp.apply_comms_ops(scene, [{"id": "net", "op": "remove"}])
        assert scene["comms"] == {}

    def test_a_channel_needs_two_endpoints(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [
            {"id": "nowhere", "rooms": ["observation"]},
            {"id": "nobody", "carriers": ["Vela"]},
            {"id": "empty"},
        ])
        assert scene["comms"] == {}

    def test_a_base_station_and_one_field_radio_is_two(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "base", "name": "base station",
            "rooms": ["observation"], "carriers": ["Vela"]}])
        assert "base" in scene["comms"]
        assert _link(scene, "Sarah Moon", "Vela")

    def test_a_channel_to_a_retired_room_is_pruned(self):
        """Not kept, so a compartment nobody can stand in cannot keep carrying
        voices."""
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "net", "rooms": ["observation", "cell"]}])
        del scene["rooms"]["cell"]
        sp.normalize_scene_comms(scene)
        assert scene["comms"] == {}


# ---------------------------------------------------------------- carried


class TestCarriedEquipment:
    """A walkie-talkie is a channel that travels in a pocket."""

    def test_a_radio_follows_its_carrier(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "squad", "name": "squad radio",
            "carriers": ["Sarah Moon", "Vela"]}])
        assert _link(scene, "Sarah Moon", "Vela")

        # Vela drives somewhere else; the radio is still in her hand.
        scene["positions"]["Vela"] = "street"
        assert _link(scene, "Sarah Moon", "Vela")

    def test_a_speaker_fills_the_room_its_carrier_is_standing_in(self):
        """A handheld on speaker is heard by whoever is beside it -- which is
        the difference between a private call and one everybody overhears."""
        scene = _scene()
        scene["positions"]["Vela"] = "street"
        sp.apply_comms_ops(scene, [{
            "id": "squad", "carriers": ["Sarah Moon", "Vela"]}])
        assert _link(scene, "Sarah Moon", "Passerby"), \
            "the passerby is standing next to Vela's radio"

    def test_private_reaches_the_carrier_and_nobody_else(self):
        scene = _scene()
        scene["positions"]["Vela"] = "street"
        sp.apply_comms_ops(scene, [{
            "id": "call", "name": "phone call", "private": True,
            "carriers": ["Sarah Moon", "Vela"]}])
        assert _link(scene, "Sarah Moon", "Vela")
        assert _link(scene, "Sarah Moon", "Passerby") is None

    def test_a_carrier_with_no_recorded_position_breaks_nothing(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "squad", "carriers": ["Sarah Moon", "Ghost"]}])
        assert _link(scene, "Sarah Moon", "Passerby") is None

    def test_co_presence_is_not_a_channel(self):
        """Two people in one room hear each other directly. Saying they heard
        it "over the radio" puts a device between them the beat does not need
        -- and tells a mind its neighbour was elsewhere."""
        scene = _scene()
        scene["positions"]["Vela"] = "observation"
        sp.apply_comms_ops(scene, [{
            "id": "squad", "carriers": ["Sarah Moon", "Vela"]}])
        assert _link(scene, "Sarah Moon", "Vela") is None


# ---------------------------------------------------------------- perception


class TestWhatReachesAMind:
    def test_a_voice_crosses_a_wall_that_stops_it(self):
        scene = _scene()
        assert _percept(scene, "Sarah Moon", "Hinami") is None, \
            "a window stops an ordinary voice"

        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "name": "the cell intercom",
            "rooms": ["observation", "cell"]}])
        percept = _percept(scene, "Sarah Moon", "Hinami")
        assert percept is not None
        assert percept.data["level"] == "full"

    def test_the_route_is_recorded_on_the_percept(self):
        """The whole firewall claim of this feature.

        A voice on a speaker is a different fact from a voice in the room. A
        mind handed the second when the first is true has been told the
        speaker is present -- by the layer built to stop precisely that.
        """
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "name": "the cell intercom",
            "rooms": ["observation", "cell"]}])
        percept = _percept(scene, "Sarah Moon", "Hinami")
        assert percept.data["via"] == "the cell intercom"
        assert percept.data["via_channel"] == "cell_intercom"

    def test_a_live_channel_beats_a_wall_that_only_muffles(self):
        """The channel decides BEFORE the wall, and that ordering is the fix.

        Found in play, on a live interview room. The Director had encoded its
        two-way mirror as `membrane`, which muffles an ordinary voice to a
        `fragment` -- and a fragment is not "none", so the spatial read
        returned first and the live PA standing between those exact two rooms
        was never consulted. The scene had the equipment, the equipment was
        switched on, and the reader got a muffled voice through the glass.

        A speaker reproduces the voice; what the wall would have done to it is
        a property of the path the channel replaces.
        """
        scene = _scene()
        scene["rooms"]["observation"]["adjacent"] = [
            {"to": "cell", "barrier": "membrane"}]
        scene["rooms"]["cell"]["adjacent"] = [
            {"to": "observation", "barrier": "membrane"}]

        muffled = _percept(scene, "Sarah Moon", "Hinami")
        assert muffled.fidelity == "fragment", "the wall alone muffles"

        sp.apply_comms_ops(scene, [{
            "id": "pa", "name": "the PA", "rooms": ["observation", "cell"]}])
        clear = _percept(scene, "Sarah Moon", "Hinami")
        assert clear.data["level"] == "full"
        assert clear.data["body"] == "State your designation."
        assert clear.data["via"] == "the PA"

    def test_a_channel_only_ever_raises_what_arrives(self):
        """Where no channel applies, nothing about the ordinary spatial read
        changes -- the rescue is a floor, never a ceiling."""
        scene = _scene()
        scene["rooms"]["observation"]["adjacent"] = [
            {"to": "cell", "barrier": "membrane"}]
        scene["rooms"]["cell"]["adjacent"] = [
            {"to": "observation", "barrier": "membrane"}]
        assert _percept(scene, "Sarah Moon", "Hinami").fidelity == "fragment"
        assert _percept(scene, "Sarah Moon", "guard_1").data["level"] == "full"

    def test_someone_in_the_room_is_never_told_they_heard_a_radio(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "rooms": ["observation", "cell"]}])
        percept = _percept(scene, "Sarah Moon", "guard_1")
        assert percept is not None
        assert "via" not in percept.data

    def test_it_reaches_whoever_is_listening_not_only_the_addressee(self):
        """The difference between a channel and the old per-line rescue.

        `line_hear_level`'s `medium: "comm"` path only ever rescued the
        observer the line explicitly NAMED. A voice on a speaker is heard by
        whoever is in front of the speaker; it does not check who it was
        talking to.
        """
        scene = _scene()
        scene["positions"]["Vela"] = "cell"
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "rooms": ["observation", "cell"]}])
        for listener in ("Hinami", "Vela"):
            percept = _percept(scene, "Sarah Moon", listener)
            assert percept is not None, listener
            assert percept.data["level"] == "full"

    def test_closing_the_channel_silences_it_and_nothing_else(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "rooms": ["observation", "cell"]}])
        sp.apply_comms_ops(scene, [{"id": "cell_intercom", "op": "close"}])

        assert _percept(scene, "Sarah Moon", "Hinami") is None
        assert _percept(scene, "Sarah Moon", "guard_1") is not None, \
            "the guard beside her still hears her"

    def test_a_channel_carries_voice_and_not_sight(self):
        """A speaker in the ceiling is not a window."""
        scene = _scene()
        scene["rooms"]["street"]["adjacent"] = []
        sp.apply_comms_ops(scene, [{
            "id": "net", "rooms": ["observation", "street"]}])
        rel = sp.spatial_rel(scene, "street", "observation")
        assert sp.sight_level(rel) == "none"
        percept = _percept(scene, "Sarah Moon", "Passerby")
        assert percept is not None
        assert percept.data["can_see"] is False

    def test_the_view_says_which_channel_carried_it(self):
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "name": "the cell intercom",
            "rooms": ["observation", "cell"]}])
        rendered = composer._render_event(_percept(scene, "Sarah Moon", "Hinami"))
        assert "the cell intercom" in rendered

    def test_the_memory_episode_says_it_too(self):
        """The route rides into memory, or the fact is deleted one layer down
        where nobody would ever notice -- a character recalling being told
        something over a radio must not remember the speaker standing there."""
        scene = _scene()
        sp.apply_comms_ops(scene, [{
            "id": "cell_intercom", "name": "the cell intercom",
            "rooms": ["observation", "cell"]}])
        episode = composer._episode_sentence(
            _percept(scene, "Sarah Moon", "Hinami"))
        assert "the cell intercom" in episode
        assert "State your designation." in episode


# ---------------------------------------------------------------- reactions


class TestWhoMayReact:
    """The reactor fallback used a hand-written list of barrier names, and it
    had drifted from the vocabulary it was quoting.

    Measured the day it was found, against the real tables: 4 of 9 barriers
    classified wrong, in BOTH directions. It admitted `wall`, through which
    nothing whatever is perceived, and excluded `bars` (sight and full speech),
    `window` (sight) and `membrane` (muffled speech). So a character behind
    glass could not answer what she was plainly watching, while one behind a
    solid wall could react to what she could not possibly know.
    """

    @pytest.mark.parametrize("barrier", ["open", "open_door", "bars",
                                         "closed_door", "membrane", "window"])
    def test_anything_perceptible_may_react(self, barrier):
        scene = {"rooms": {"a": {"adjacent": [{"to": "b", "barrier": barrier}]},
                           "b": {"adjacent": [{"to": "a", "barrier": barrier}]}}}
        assert sp.can_perceive_onset(scene, "a", "b") is True

    @pytest.mark.parametrize("barrier", ["wall", "separated", "unknown"])
    def test_nothing_perceptible_may_not(self, barrier):
        """Dropping `wall` is the deliberate half of the correction. A mind
        that perceives nothing has nothing to react to, and handing it a turn
        invites it to answer something it never received."""
        scene = {"rooms": {"a": {"adjacent": [{"to": "b", "barrier": barrier}]},
                           "b": {"adjacent": [{"to": "a", "barrier": barrier}]}}}
        assert sp.can_perceive_onset(scene, "a", "b") is False

    def test_a_live_channel_makes_a_sealed_room_reactable(self):
        scene = {"rooms": {"a": {"adjacent": [{"to": "b", "barrier": "wall"}]},
                           "b": {"adjacent": [{"to": "a", "barrier": "wall"}]}},
                 "positions": {}, "comms": {}}
        assert sp.can_perceive_onset(scene, "a", "b") is False
        sp.apply_comms_ops(scene, [{"id": "net", "rooms": ["a", "b"]}])
        assert sp.can_perceive_onset(scene, "a", "b") is True

    def test_the_probe_is_an_ordinary_voice_not_a_shout(self):
        """A shout carries a fragment through absolutely everything, including
        `separated` -- which is what two rooms with no edge between them
        report. Probing at shout volume answers True for every pair of rooms in
        the scene, which turns the gate into "everyone" and plans a character
        step per cast member per beat."""
        scene = {"rooms": {"a": {}, "b": {}}}
        rel = sp.spatial_rel(scene, "a", "b")
        assert sp.hear_level(rel, "shout") == "fragment"
        assert sp.can_perceive_onset(scene, "a", "b") is False


# ---------------------------------------------------------------- the merge


class TestItRidesTheEngine:
    def test_ops_land_through_the_ordinary_merge(self):
        scene = _scene()
        merged = sp.merge_scene_with_diff(scene, {
            "comms_ops": [{"id": "net", "name": "ship comm",
                           "rooms": ["observation", "cell"]}]})
        assert merged["comms"]["net"]["name"] == "ship comm"

    def test_the_schema_carries_the_channel(self):
        from llm import schemas

        out, _warnings = schemas.validate_llm_output("director_spatial", {
            "comms_ops": [{"id": "pa", "rooms": ["observation", "cell"],
                           "mode": "broadcast", "source": "observation"}]})
        assert out["comms_ops"][0]["mode"] == "broadcast"
        assert out["comms_ops"][0]["op"] == "set"

    def test_the_opening_beat_can_install_one(self):
        """A scene BUILT around an intercom -- an observation room, a bridge, a
        control booth -- must have one on beat zero, which is the beat it was
        needed for."""
        from llm import schemas

        out, _warnings = schemas.validate_llm_output("director_establish", {
            "location": "Site-17", "time": "now", "scene_description": "x",
            "comms_ops": [{"id": "cell_intercom",
                           "rooms": ["observation", "cell"]}]})
        assert out["comms_ops"][0]["id"] == "cell_intercom"

    def test_the_spatial_specialist_owns_it(self):
        from agents import director

        assert "comms_ops" in director.SPECIALISTS["spatial"]["channels"]
        assert "comms_ops" in director._CHANNEL_GATES

    def test_the_specialist_sheet_can_teach_it(self):
        """An owned channel with no chunk loads nothing when granted."""
        from llm import prompts

        chunks = prompts.SPECIALIST_PROMPT_SPECS["spatial"]["chunks"]
        assert "comms_ops" in chunks
        assert "carriers" in chunks["comms_ops"]
        assert "broadcast" in chunks["comms_ops"]


# ---------------------------------------------------------------- one-way sight


class TestOneWayWindow:
    """Sight that passes in one direction and not the other.

    Every other barrier is a property of the DOORWAY rather than of the side
    you stand on, and `_one_sided_seal`'s docstring records why: a stair
    declared `open_shoji` from one end and `wall` from the other left a hall
    with no route to its own upstairs. That rule is right for passage and for
    sound. It is wrong for SIGHT, and a real class of object sat
    unrepresentable behind it -- a two-way mirror, an observation window, a
    peephole, a hunting blind, a confessional screen.

    Found in play. An interview room with an observation window offered the
    Director only `window` (both see) or `membrane` (neither sees), and it
    chose `membrane` -- so the interviewer could not see the person she was
    watching through the glass.
    """

    def _mirror(self, both_sides=False):
        cell_edges = ([{"to": "obs", "barrier": "one_way_window"}] if both_sides
                      else [{"to": "obs", "barrier": "wall"}])
        return {"rooms": {
            "obs": {"name": "Observation",
                    "adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
            "cell": {"name": "Cell", "adjacent": cell_edges}}}

    def test_the_watcher_sees_and_the_watched_does_not(self):
        scene = self._mirror()
        assert sp.sight_level(sp.spatial_rel(scene, "obs", "cell")) == "full"
        assert sp.sight_level(sp.spatial_rel(scene, "cell", "obs")) == "none"

    def test_the_room_itself_is_only_visible_one_way(self):
        """`visible_adjacent_rooms` admits a neighbour's whole room record, so
        the two answers have to agree -- otherwise the far side is refused a
        sightline and handed the room description anyway."""
        scene = self._mirror()
        assert [r["room_id"] for r in sp.visible_adjacent_rooms(scene, "obs")] \
            == ["cell"]
        assert sp.visible_adjacent_rooms(scene, "cell") == []

    def test_one_declaration_is_enough(self):
        """The asymmetry lives on a single edge. Requiring the blind side to
        also declare something would make a forgotten second line silently
        restore the sightline."""
        scene = {"rooms": {
            "obs": {"adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
            "cell": {"adjacent": []}}}
        assert sp.sight_level(sp.spatial_rel(scene, "obs", "cell")) == "full"
        assert sp.sight_level(sp.spatial_rel(scene, "cell", "obs")) == "none"
        assert sp.spatial_rel(scene, "cell", "obs")["barrier"] == "wall", \
            "the back of a one-way mirror is a wall"
        assert sp.visible_adjacent_rooms(scene, "cell") == []

    def test_declared_from_both_sides_it_is_an_ordinary_window(self):
        """Two one-way windows back to back ARE a window, and that is the only
        reading available without an arbitrary tie-break -- nothing in the pair
        says which of them the author meant. The prompts therefore ask for
        `wall` on the blind side rather than a second one of these."""
        scene = self._mirror(both_sides=True)
        assert sp.sight_level(sp.spatial_rel(scene, "obs", "cell")) == "full"
        assert sp.sight_level(sp.spatial_rel(scene, "cell", "obs")) == "full"

    def test_it_is_glass_so_it_stops_a_voice_and_a_body(self):
        scene = self._mirror()
        rel = sp.spatial_rel(scene, "obs", "cell")
        assert sp.hear_level(rel, "normal") == "none"
        assert "one_way_window" not in sp._PASSABLE_BARRIERS
        assert "one_way_window" not in sp._AMBIENT_BARRIERS
        assert "one_way_window" not in sp._SCENT_BARRIERS

    @pytest.mark.parametrize("written", [
        "two-way mirror", "two_way_mirror", "one-way mirror", "one_way_mirror",
        "mirrored glass", "mirrored_glass", "peephole", "spy_hole",
    ])
    def test_what_a_model_actually_writes_normalizes_to_it(self, written):
        """A vocabulary the model cannot spell is a vocabulary it does not
        have."""
        assert sp.normalize_barrier(written) == "one_way_window"

    def test_an_ambiguous_word_keeps_the_reading_it_had(self):
        """`observation_window` was already an alias for plain `window`, and
        the word really is ambiguous -- a hospital nursery's is glass both
        ways, an interrogation suite's is not. Hijacking it would have made
        every existing scene that used the word silently one-way."""
        assert sp.normalize_barrier("observation_window") == "window"

    def test_the_director_is_offered_the_whole_vocabulary(self):
        """The reason the live scene got `membrane`: the prompts listed
        open|open_door|membrane|closed_door|wall and nothing else, so `window`
        and `bars` existed in the engine and were never on the menu. A barrier
        the Director is not told about cannot be chosen, and the nearest
        wrong one gets picked instead.
        """
        from llm.prompts import get_prompt

        for key in ("director_establish", "resolve_repair",
                    "greeting_interpret"):
            text = get_prompt(key)
            for barrier in ("window", "bars", "one_way_window", "membrane"):
                assert barrier in text, f"{key} never offers {barrier}"

    def test_every_valid_barrier_is_offered_somewhere(self):
        """The list in the prompt and the list in the engine are two spellings
        of one vocabulary, and they had drifted."""
        from llm.prompts import get_prompt

        text = get_prompt("director_establish")
        for barrier in sp._VALID_BARRIERS - {"separated", "unknown"}:
            assert barrier in text, barrier


class TestSeeingSomeoneInAnotherRoom:
    """A body you can see is present to you, whatever room it is standing in.

    `presence_percepts` dropped anyone `proximity_rel` gave no tier for, on the
    comment "co-located only". But `proximity_rel` measures WITHIN a room --
    None means "not in this one", not "not visible". So the engine handed a
    mind the adjacent ROOM and never anyone standing in it: an interviewer
    watching through observation glass received the cell and not the woman in
    it, which is the whole content of looking through it.

    `visual_level_between` had always answered the sight question properly for
    cross-room pairs, caps and all. The only thing missing was somewhere to put
    the distance, and the room's own name is the one phrasing that stays true
    through a doorway, a grille and a pane of glass alike.
    """

    def _scene_with(self, barrier):
        return {
            "rooms": {
                "obs": {"name": "Observation Room",
                        "adjacent": [{"to": "cell", "barrier": barrier}]},
                "cell": {"name": "Interview Cell",
                         "adjacent": [{"to": "obs", "barrier": "wall"}]},
            },
            "positions": {"Moon": "obs", "Ward": "obs", "Hinami": "cell"},
        }

    def _seen(self, scene, observer):
        bodies = [{"name": n, "room": r} for n, r in scene["positions"].items()]
        return {p.source_label: p.data for p in composer.presence_percepts(
            scene, observer, bodies, {n["name"]: n["name"] for n in bodies})}

    def test_a_body_through_the_glass_is_present(self):
        seen = self._seen(self._scene_with("one_way_window"), "Moon")
        assert "Hinami" in seen
        assert seen["Hinami"]["tier"] == "beyond"
        assert seen["Hinami"]["room"] == "Interview Cell"

    def test_the_blind_side_still_sees_nobody(self):
        assert self._seen(self._scene_with("one_way_window"), "Hinami") == {}

    def test_the_room_is_named_rather_than_a_distance_guessed(self):
        """"close by" and "across the room" are both false through a wall, and
        the room's name is true for every barrier."""
        scene = self._scene_with("one_way_window")
        bodies = [{"name": n, "room": r} for n, r in scene["positions"].items()]
        clauses = [composer._presence_clause(p) for p in
                   composer.presence_percepts(
                       scene, "Moon", bodies,
                       {b["name"]: b["name"] for b in bodies})]
        assert "Hinami is in Interview Cell" in clauses
        assert "Ward is close by" in clauses

    @pytest.mark.parametrize("barrier", ["open", "open_door", "window", "bars"])
    def test_it_holds_for_every_see_through_barrier(self, barrier):
        """Not a one-way-mirror special case: an open doorway had the same
        hole, and someone standing in the next room through it was equally
        invisible."""
        assert "Hinami" in self._seen(self._scene_with(barrier), "Moon")

    @pytest.mark.parametrize("barrier", ["wall", "membrane", "closed_door"])
    def test_and_never_through_one_that_stops_sight(self, barrier):
        assert "Hinami" not in self._seen(self._scene_with(barrier), "Moon")

    def test_a_dark_room_is_still_dark(self):
        """Sight is decided by `visual_level_between`, which this defers to
        entirely -- so every existing subtraction still subtracts."""
        scene = self._scene_with("window")
        scene["rooms"]["cell"]["light"] = "dark"
        assert "Hinami" not in self._seen(scene, "Moon")

    def test_co_located_bodies_keep_their_measured_tier(self):
        """The within-room answer must not be replaced by the room's name for
        people who are actually in the room with you."""
        seen = self._seen(self._scene_with("window"), "Moon")
        assert seen["Ward"]["tier"] == "near"
        assert "room" not in seen["Ward"]
