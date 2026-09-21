"""A person who comes into the place you keep is your business.

Every other trigger in `pick_voice_demand` is downstream of somebody having
already spoken: addressed, place-addressed, owed, routed, emerged, and even
`acting` (a charter act already aimed at an authored mind). So a room could
hold working people indefinitely and never speak first, and the busier it was
the worse that read.

Measured, two_lives v5 (2026-09-19): Sal Weatherby walked into Aldermill Forge
past six charter smiths and stood there nine beats watching them work. No
trigger fired on any of those beats, and across thirty beats exactly one line
was spoken by anyone in that town.

The asymmetry is what keeps this from becoming ambient chatter: it fires for a
body standing at its OWN STATION (`_at_own_station`), so a smith at his forge
asks what you want and a stranger you pass on a road does not, with no
vocabulary of occupations anywhere. And an arrival is one beat's event, so it
raises the demand once and stops on its own.
"""

from __future__ import annotations

from persist.commit import _at_own_station, _authored_arrival_rooms


class TestAStationIsNotAPlaceYouPassThrough:
    def test_a_body_at_its_post_is_at_its_station(self):
        rec = {"sketch": {"station_room": "forge"}}
        assert _at_own_station(rec, "forge")

    def test_a_body_on_an_errand_is_not(self):
        rec = {"sketch": {"station_room": "forge"}}
        assert not _at_own_station(rec, "market_square")

    def test_a_body_posted_nowhere_has_no_station_to_keep(self):
        assert not _at_own_station({"sketch": {}}, "forge")
        assert not _at_own_station({}, "forge")
        assert not _at_own_station({"sketch": {"station_room": "forge"}}, "")


class TestAnArrivalIsAMoveNotAPresence:
    ROSTER = {"sal weatherby"}

    def test_the_room_walked_into_is_the_arrival(self):
        before = {"positions": {"Sal Weatherby": "smithy_yard"}}
        after = {"positions": {"Sal Weatherby": "smithy_forge"}}
        assert _authored_arrival_rooms(before, after, self.ROSTER) \
            == {"smithy_forge"}

    def test_standing_still_raises_nothing(self):
        """The bound that keeps a greeting from repeating every beat: after
        the beat she walked in, Sal is simply there."""
        same = {"positions": {"Sal Weatherby": "smithy_forge"}}
        assert _authored_arrival_rooms(same, same, self.ROSTER) == set()

    def test_only_authored_minds_arrive(self):
        """A charter body walking its errand through a room is not somebody
        the room has to greet."""
        before = {"positions": {"Striker Gorman": "smithy_yard"}}
        after = {"positions": {"Striker Gorman": "smithy_forge"}}
        assert _authored_arrival_rooms(before, after, self.ROSTER) == set()

    def test_a_mind_the_scene_had_no_position_for_arrives(self):
        before = {"positions": {}}
        after = {"positions": {"Sal Weatherby": "smithy_forge"}}
        assert _authored_arrival_rooms(before, after, self.ROSTER) \
            == {"smithy_forge"}


# --- the gate itself ------------------------------------------------------

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import pick_voice_demand

FORGE, YARD = "smithy_forge", "smithy_yard"


def _scene(where):
    return {
        "rooms": {FORGE: {"name": "Aldermill Forge", "adjacent": [YARD],
                          "light": "lit"},
                  YARD: {"name": "Smithy Yard", "adjacent": [FORGE],
                         "light": "lit"}},
        "positions": {"Sal Weatherby": where, "Gorman": FORGE},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _ctx(temp_db, station):
    """Sal in the yard, a smith posted at ``station``, nobody speaking."""
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    temp_db.wset(chat_id, "scene", _scene(YARD))
    temp_db.wset(chat_id, "background_presences", {
        "p1": {"uid": "p1", "name": "Gorman", "nature": "person",
               "first_turn": 1, "last_turn": 1, "dialogue_turns": [],
               "mention_turns": [], "addressed_turns": [], "engaged_turns": [],
               "charter_refs": [],
               "sketch": {"role_hint": "striker", "station_room": station}}})
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=4, player_input="",
                      created=time.time()),
        cast=[{"sheet": json.dumps({"identity": {"name": "Sal Weatherby"}})}],
        input="I step into the forge and watch the anvil.")
    ctx.director_interpret = {"sequence": []}
    return ctx


def _walk_in():
    """A beat whose only content is Sal crossing into the forge -- no line
    spoken by anyone, which is the whole point."""
    return {"dialogue_log": [], "state_diff": {"positions": {
        "Sal Weatherby": FORGE}}}


def test_a_smith_at_his_forge_speaks_when_somebody_walks_in(temp_db):
    out = pick_voice_demand(_ctx(temp_db, FORGE), _walk_in())
    assert out["picks"] == ["Gorman"]
    assert any(w.startswith("arrived:") for w in out["meta"]["Gorman"]["why"])
    # Not an addressee: nobody said anything to him, and the stage must not
    # hand him words as though somebody had.
    assert out["meta"]["Gorman"]["addressed"] is False


def test_somebody_merely_passing_through_owes_no_greeting(temp_db):
    """The same body, same room, same arrival -- posted elsewhere. This is
    the whole reason the trigger reads a station rather than a headcount:
    without it every passer-by in a busy room greets every arrival."""
    assert pick_voice_demand(_ctx(temp_db, YARD), _walk_in())["picks"] == []


def test_standing_in_the_room_is_not_arriving_in_it(temp_db):
    """The beat after: she is simply there, and the forge goes back to
    work. An arrival fires once because an arrival happens once."""
    ctx = _ctx(temp_db, FORGE)
    ctx.chat  # scene already has her in the yard; put her in the forge
    temp_db.wset(ctx.chat.id, "scene", _scene(FORGE))
    assert pick_voice_demand(ctx, {"dialogue_log": [], "state_diff": {}})[
        "picks"] == []
