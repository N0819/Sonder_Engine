"""SOUND ARRIVES AFTER WHAT MADE IT (DESIGN_SOUND_FIELD.md § 14.3, wave B2,
2026-10-20).

Light crosses any distance a story holds at once; sound crosses air at some
343 m/s. A thing seen far off is seen first and heard after: a gun's flash,
then its bang; lightning, then its thunder, three seconds a kilometre.
Within a building the gap is a few hundredths of a second, nothing a body
can tell. The class: where a view holds the sight of a thing and the sound
it made, and the thing stands past the distance at which the gap reads as
a beat (`SOUND_AFTER_SIGHT_M`, about 103 m), the sight is told first and the
sound after it -- an order within the beat, never a new beat.

What existed, verified: the sky's `electrical` axis reached the screen (a
flash, then a clap 0.7-6.5 s later, `static/js/weather-fx.js`) and the
ambience, and no mind's view at all; and a beat's sound events were minted
without a place among its events, so a far shot's crack was never put after
the sight of it.
"""

from __future__ import annotations

import json
import time

from agents import composer
from world.spatial import (LIGHTNING_M, SOUND_AFTER_SIGHT_M,
                           seen_source_metres, sound_after_sight,
                           sound_delay_s)
from world.weather import weather_for_room


def test_the_gap_is_real_and_only_past_a_beat():
    """343 m/s: a hundred metres is three tenths of a second, the gap a
    reader takes as "and then"; under it sight and sound are one moment,
    past half a kilometre the sound comes seconds after; lightning comes
    from a cloud base a kilometre or two up, always seconds."""
    assert abs(SOUND_AFTER_SIGHT_M - 102.9) < 0.1
    assert abs(sound_delay_s(343.0) - 1.0) < 1e-9
    assert [sound_after_sight(m) for m in (None, 12, 72, 100)] == [None] * 4
    assert sound_after_sight(150) == "moment"
    assert sound_after_sight(600) == "seconds"
    assert sound_after_sight(LIGHTNING_M) == "seconds"


def _storm(exposure, *, fall="rain"):
    weather = {"sky": "storm", "cloud": "covered", "electrical": True,
               "wind": "wind"}
    if fall:
        weather.update({"precipitation": fall, "precipitation_kind": "liquid",
                        "intensity": "heavy"})
    sc = {"rooms": {"here": {"name": "here", "exposure": exposure,
                             "adjacent": [{"to": "out", "barrier": "closed_door"}]},
                    "out": {"name": "out", "exposure": "open", "adjacent": []}},
          "positions": {"P": "here"}, "weather": weather}
    return weather_for_room(sc, "here", "P")


def test_a_storm_flashes_and_its_thunder_comes_after():
    """Under the open sky a storm's lightning is seen and its thunder heard
    after it, in that order; indoors behind a door the thunder alone comes
    through, muffled; a story in Japanese is told it in Japanese."""
    from language_runtime import language_scope
    out = composer.weather_percepts(_storm("open"))
    storm = [p for p in out if "flash" in p.dedupe_key or "thunder" in p.dedupe_key]
    assert [p.channel for p in storm] == ["sight", "hearing"]
    text = composer.render_view(out).text
    flash = text.index("Lightning flickers across the storm sky.")
    thunder = text.index("Its thunder follows each flash, seconds later.")
    assert flash < thunder, text
    inside = composer.render_view(composer.weather_percepts(_storm("enclosed"))).text
    assert "Lightning" not in inside
    assert "Thunder rolls somewhere beyond the walls, muffled." in inside, inside
    with language_scope("ja"):
        ja = composer.weather_percepts(_storm("open"))
    said = " ".join(p.data.get("desc", "") for p in ja)
    assert "稲妻" in said and "数秒遅れて雷鳴" in said, said


def test_a_sound_heard_after_its_sight_is_told_after_the_act():
    """The composer, given the act it saw at its place among the beat's
    events and the sound just after it, says the sight and then the sound,
    and says the sound came after."""
    act = composer.Percept(kind="act", channel="sight", source_label="Rook",
                           data={"surface": "fires the musket"}, order_key=3,
                           dedupe_key="act:x")
    sound = composer.ambient_percepts(
        [{"room": "meadow", "detail": "a flat crack of musket fire"}],
        "meadow", order_key=3.5, after="moment")
    later = composer.Percept(kind="act", channel="sight", source_label="Wren",
                             data={"surface": "ducks"}, order_key=4,
                             dedupe_key="act:y")
    text = composer.render_view([later] + sound + [act], mode="player").text
    assert text.index("fires the musket") < text.index("crack of musket fire") \
        < text.index("ducks"), text
    assert "a moment after the sight of it" in text, text


# ---------------------------------------------------------------------------
# End to end: a shot across two fields, the outcome pass
# ---------------------------------------------------------------------------

PLAYER = "Pip"
CAST = "Wren Hollis"


def _fields(cast_cell):
    def room(name, adjacent):
        return {"name": name, "exposure": "open", "extent": {"w": 96, "d": 6},
                "anchors": {}, "adjacent": adjacent, "light": "bright"}
    return {"location": "the fields", "time": "noon",
            "rooms": {"meadow": room("the meadow", [{"to": "pasture",
                                                    "barrier": "open",
                                                    "dir": "e"}]),
                      "pasture": room("the pasture", [{"to": "meadow",
                                                       "barrier": "open",
                                                       "dir": "w"}])},
            "positions": {PLAYER: "meadow", CAST: "pasture"},
            "stations": {PLAYER: {"cell": [40, 3]}, CAST: {"cell": list(cast_cell)}},
            "entities": {}, "attire": {}, "overlays": {}, "poses": {},
            "orientation": {}, "contained": {}}


def _outcome(db, cast_cell):
    from agents import perception
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import (default_character_data,
                                        default_persona_data)
    persona_id = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                       (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                "VALUES(?,?,?,?)", ("Fields", "", time.time(), persona_id))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (CAST, json.dumps(default_character_data(CAST)), "{}", time.time(),
         "char_wren_%d" % cast_cell[0]))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, char_id, "active", "{}"))
    db.wset(cid, "scene", _fields(cast_cell))
    db.wset(cid, "known", {CAST: [PLAYER], PLAYER: [CAST]})
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
                (cid,))
    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Fields", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "meadow"
    ctx.director_interpret = {
        "action": {"attempt": "fires the musket into the air",
                   "visibility": "overt", "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{"type": "action", "attempt": "fires the musket into the air",
                      "observable": "fires the musket into the air",
                      "visibility": "overt", "conceal_from": [], "targets": [],
                      "commitment": "asserted", "verb": "fire",
                      "stage": "immediate",
                      "event_id": "turn:1:player:0:action"}],
        "speech": None, "speech_volume": "normal", "flow": {"reactors": []}}
    ctx.director_resolve = {
        "resolved_event": "The musket fires.",
        "state_diff": {"sensory_events": [{
            "kind": "sound", "room": "meadow", "level": "loud",
            "source": PLAYER, "detail": "a flat crack of musket fire"}]},
        "dialogue_log": [], "dialogue_order": []}
    out = perception.perception_outcome(ctx, nonce="n")
    return (out.get("views") or {}).get(str(cast[0]["id"])) or ""


def test_a_shot_seen_across_two_fields_is_heard_after_it(temp_db):
    """Pip fires a musket in the meadow. Wren, a hundred and fifty paces off
    across the gap in the hedge -- a hundred and twelve metres -- sees the
    shot and then hears it; at the near edge of the pasture, sixty-odd
    metres off, the crack and the sight are one moment."""
    sc = _fields((94, 3))
    assert seen_source_metres(sc, CAST, PLAYER) > SOUND_AFTER_SIGHT_M
    far = _outcome(temp_db, (94, 3))
    assert "fires the musket" in far and "crack of musket fire" in far, far
    assert far.index("fires the musket") < far.index("crack of musket fire"), far
    assert "a moment after the sight of it" in far, far
    near = _outcome(temp_db, (40, 3))
    assert "crack of musket fire" in near, near
    assert "after the sight of it" not in near, near
