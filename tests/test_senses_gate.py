"""G4: the perceiver-senses gate.

Cards have carried typed senses {channel, acuity, range, notes} forever and
no channel function read them: a card saying vision `absent` composed a fully
sighted view, and "enhanced" vs "super enhanced" were indistinguishable
because nothing consumed the value. `spatial.sense_adjusted` is the one gate:
an integer acuity offset on each channel's ladder, with the semantic ceiling
the perception prompt states -- an upward shift never mints content, so a
hearing rescue from `none` lands on the contentless `trace` tier (detected,
direction at best, NO words, NO identity) and only at extraordinary.

Ordinary MUST be byte-identical: G4 is the single deliberate exception to
subtract-only, and only when explicitly authored on a card.
"""
from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData
from spatial import (
    HEARING_LEVELS,
    SCENT_LEVELS,
    SIGHT_LEVELS,
    sense_acuity_offset,
    sense_adjusted,
    sense_range_class,
)

from agents.loops import deterministic_micro_perception


def _sense(channel, acuity="ordinary", range_="ordinary"):
    return {"channel": channel, "acuity": acuity, "range": range_, "notes": ""}


# ---- byte-identical ordinary ---------------------------------------------------

def test_ordinary_and_unlisted_are_byte_identical():
    default = [_sense("vision"), _sense("hearing")]
    for channel, ladder in (("hearing", HEARING_LEVELS),
                            ("sight", SIGHT_LEVELS),
                            ("scent", SCENT_LEVELS)):
        for level in ladder:
            assert sense_adjusted(level, channel, None) == level
            assert sense_adjusted(level, channel, default) == level
            assert sense_adjusted(level, channel, []) == level
    # An EMPTY acuity is an authoring gap, and an authoring gap must never
    # blind a body -- it reads as ordinary, not as absent.
    blank = [_sense("hearing", acuity="")]
    assert sense_adjusted("full", "hearing", blank) == "full"


def test_unrecognized_free_text_never_adds():
    weird = [_sense("hearing", acuity="resonant with the spheres")]
    assert sense_acuity_offset(weird, "hearing") == 0
    assert sense_adjusted("none", "hearing", weird) == "none"


# ---- the offsets ----------------------------------------------------------------

def test_acuity_vocabulary_maps_to_offsets():
    for word, offset in (("ordinary", 0), ("keen", 1), ("enhanced", 1),
                         ("heightened", 1), ("expert", 1),
                         ("extraordinary", 2), ("supernatural", 2),
                         ("super enhanced", 2), ("dulled", -1),
                         ("failing", -1), ("hard of hearing", -1)):
        senses = [_sense("hearing", acuity=word)]
        assert sense_acuity_offset(senses, "hearing") == offset, word
    assert sense_acuity_offset([_sense("hearing", acuity="deaf")],
                               "hearing") is None


def test_channel_aliases_resolve():
    senses = [_sense("smell", acuity="keen")]
    assert sense_acuity_offset(senses, "scent") == 1
    senses = [_sense("supernatural scent", acuity="extraordinary")]
    assert sense_acuity_offset(senses, "scent") == 2
    # Channels the floor does not model stay unread.
    senses = [_sense("intuition", acuity="extraordinary")]
    assert sense_acuity_offset(senses, "hearing") == 0


def test_absent_cuts_the_channel():
    deaf = [_sense("hearing", acuity="absent")]
    blind = [_sense("vision", acuity="blind")]
    for level in HEARING_LEVELS:
        assert sense_adjusted(level, "hearing", deaf) == "none"
    for level in SIGHT_LEVELS:
        assert sense_adjusted(level, "sight", blind) == "none"


def test_dulled_shifts_one_rung_down():
    dulled = [_sense("hearing", acuity="dulled")]
    assert sense_adjusted("full", "hearing", dulled) == "fragment"
    assert sense_adjusted("fragment", "hearing", dulled) == "trace"
    assert sense_adjusted("none", "hearing", dulled) == "none"
    dim = [_sense("vision", acuity="poor")]
    assert sense_adjusted("full", "sight", dim) == "shapes"


def test_keen_upgrades_content_already_flowing():
    keen = [_sense("hearing", acuity="keen")]
    assert sense_adjusted("fragment", "hearing", keen) == "full"
    sharp = [_sense("vision", acuity="keen")]
    assert sense_adjusted("shapes", "sight", sharp) == "full"
    nose = [_sense("smell", acuity="keen")]
    assert sense_adjusted("muffled", "scent", nose) == "full"


def test_the_ceiling_no_rescue_from_none_ever_carries_content():
    # Keen is not enough to register what ordinary senses miss entirely.
    keen = [_sense("hearing", acuity="keen")]
    assert sense_adjusted("none", "hearing", keen) == "none"
    # Extraordinary registers gross direction and noise character -- a trace
    # -- NEVER a word-bearing grade, however large the offset.
    extra = [_sense("hearing", acuity="extraordinary")]
    assert sense_adjusted("none", "hearing", extra) == "trace"
    # Sight and scent never leave `none`: `none` cannot say whether it was a
    # wall or the dark, and neither is something acuity penetrates.
    eagle = [_sense("vision", acuity="extraordinary")]
    assert sense_adjusted("none", "sight", eagle) == "none"
    hound = [_sense("smell", acuity="supernatural")]
    assert sense_adjusted("none", "scent", hound) == "none"


def test_range_is_the_separate_axis():
    assert sense_range_class([_sense("hearing", range_="extended")],
                             "hearing") == "extended"
    assert sense_range_class([_sense("hearing", range_="long")],
                             "hearing") == "extended"
    assert sense_range_class([_sense("hearing", range_="skin contact")],
                             "hearing") == "reduced"
    assert sense_range_class([_sense("hearing")], "hearing") == "ordinary"
    assert sense_range_class(None, "hearing") == "ordinary"
    # Range never changes acuity.
    long_ear = [_sense("hearing", range_="extended")]
    assert sense_adjusted("none", "hearing", long_ear) == "none"


# ---- wired through the deterministic micro-loop ---------------------------------

def _setup(temp_db, names, senses_by_name=None, rooms=None, positions=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()),
    )
    ids = {}
    for n in names:
        sheet = default_character_data(n)
        if senses_by_name and n in senses_by_name:
            sheet["embodiment"]["senses"] = senses_by_name[n]
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (n, json.dumps(sheet), "{}", time.time(), f"char_{n}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, cid, "active", "{}"),
        )
        ids[n] = cid
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    scene = {
        "location": "x", "time": "day",
        "rooms": rooms or {"room1": {"name": "Room 1", "adjacent": []}},
        "positions": positions or {n: "room1" for n in names},
        "entities": {}, "attire": {}, "overlays": {},
    }
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="",
    )
    return ctx, ids, scene


_TWO_ROOMS = {
    "study": {"name": "the Study", "adjacent": [
        {"to": "landing", "barrier": "wall", "dir": "e"}]},
    "landing": {"name": "the Landing", "adjacent": []},
}


def test_extraordinary_hearing_through_a_wall_is_a_contentless_trace(temp_db):
    ctx, ids, scene = _setup(
        temp_db, ["Reya", "Kael", "Mara"],
        senses_by_name={"Kael": [
            {"channel": "hearing", "acuity": "extraordinary",
             "range": "ordinary", "notes": ""}]},
        rooms=_TWO_ROOMS,
        positions={"Reya": "study", "Kael": "landing", "Mara": "landing"},
    )
    result = {"sequence": [{"type": "speech",
                            "text": "The gate opens at dawn.",
                            "volume": "normal"}]}
    views, perceived_by = deterministic_micro_perception(
        ctx, ids["Reya"], result, scene)

    # Ordinary ears on the far side of a wall: nothing, exactly as before.
    assert ids["Mara"] not in views

    # Extraordinary ears: detection only. No words, no identity, no name --
    # not even the unknown-actor label, which would still assert a person.
    line = " ".join(views.get(ids["Kael"], []))
    assert line, "extraordinary hearing should register a trace"
    assert "dawn" not in line
    assert "Reya" not in line
    assert "says" not in line
    assert "beyond the wall" in line
    assert ids["Kael"] in perceived_by


def test_deaf_observer_receives_no_speech_but_still_sees(temp_db):
    ctx, ids, scene = _setup(
        temp_db, ["Reya", "Kael"],
        senses_by_name={"Kael": [
            {"channel": "vision", "acuity": "ordinary",
             "range": "ordinary", "notes": ""},
            {"channel": "hearing", "acuity": "absent",
             "range": "ordinary", "notes": ""}]},
    )
    result = {"sequence": [
        {"type": "speech", "text": "Can you hear me?", "volume": "loud"},
        {"type": "action", "attempt": "waves", "observable": "waves a hand"},
    ]}
    views, _ = deterministic_micro_perception(ctx, ids["Reya"], result, scene)
    line = " ".join(views.get(ids["Kael"], []))
    assert "hear me" not in line
    assert "waves a hand" in line


def test_blind_observer_receives_speech_but_no_action(temp_db):
    ctx, ids, scene = _setup(
        temp_db, ["Reya", "Kael"],
        senses_by_name={"Kael": [
            {"channel": "vision", "acuity": "absent",
             "range": "ordinary", "notes": ""},
            {"channel": "hearing", "acuity": "ordinary",
             "range": "ordinary", "notes": ""}]},
    )
    result = {"sequence": [
        {"type": "speech", "text": "Stay close.", "volume": "normal"},
        {"type": "action", "attempt": "waves", "observable": "waves a hand"},
    ]}
    views, _ = deterministic_micro_perception(ctx, ids["Reya"], result, scene)
    line = " ".join(views.get(ids["Kael"], []))
    assert "Stay close" in line
    assert "waves a hand" not in line


def test_ordinary_cards_change_nothing(temp_db):
    # The default card IS the ordinary card; delivery must read exactly as it
    # always has -- the inert-default pin for the one gate that can add.
    ctx, ids, scene = _setup(temp_db, ["Reya", "Kael"])
    result = {"sequence": [{"type": "speech", "text": "All quiet.",
                            "volume": "normal"}]}
    views, _ = deterministic_micro_perception(ctx, ids["Reya"], result, scene)
    assert 'says: "All quiet."' in " ".join(views.get(ids["Kael"], []))
