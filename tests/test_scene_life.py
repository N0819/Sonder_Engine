"""Regression tests for the scene-manager path (docs/BACKGROUND_LIFE_DESIGN.md).

The manager voices a whole location's background populace in ONE batched call.
That is a deliberate relaxation of the per-presence isolation the engine
normally applies, so the guarantees it keeps instead are what these tests pin:

  * admission control, not prompt discipline, is what protects concealed
    content (§3.11 layer 1);
  * `ambient` holds no divergent perception at all, so contamination is
    impossible rather than mitigated (§3.10);
  * the verbatim floor runs before an entry can be rendered OR appended,
    because a leak that reaches storage is re-read every subsequent turn
    (§3.3.1, §3.11);
  * a blurb is frozen once written (§3.8) -- it is the anchor against the
    self-feeding drift the profile-append loop creates;
  * the append routes each entry to its OWN presence by name (§3.11).
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

from agents.background import (
    _audience_map,
    _manager_events,
    _name_to_entity_id,
    _presence_room,
    _redacted_resolved_event,
    _reproduces_withheld,
    _withheld_bodies,
    managed_presences,
)
from commit import _append_manager_conduct, _persist_blurbs

COMMON = "tavern_common_room"
CELLAR = "tavern_cellar"


def _scene():
    return {
        "location": "The Moorside", "time": "night",
        "rooms": {
            COMMON: {"name": "common room", "desc": "low ceiling, pipe smoke",
                     "adjacent": [{"to": CELLAR, "barrier": "closed_door"}]},
            CELLAR: {"name": "cellar", "desc": "cold, damp",
                     "adjacent": [{"to": COMMON, "barrier": "closed_door"}]},
        },
        # Positions are keyed by opaque entity id, NOT display name -- the
        # exact mismatch that made co-presence lookups miss nearly every
        # presence in the first live run.
        "player_room": COMMON,
        "positions": {"Kessa Vane": COMMON, "barkeep": COMMON,
                      "local_1": COMMON, "cellarman": CELLAR},
        "entities": {
            "barkeep": {"name": "The Barkeep", "kind": "person"},
            "local_1": {"name": "Thin Local", "kind": "person"},
            "cellarman": {"name": "The Cellarman", "kind": "person"},
        },
        "attire": {}, "overlays": {},
    }


def _presences():
    return {
        "The Barkeep": {"first_turn": 0, "last_turn": 4, "dialogue_turns": [1],
                        "mention_turns": []},
        "Thin Local": {"first_turn": 0, "last_turn": 3, "dialogue_turns": [],
                       "mention_turns": []},
        "The Cellarman": {"first_turn": 2, "last_turn": 2,
                          "dialogue_turns": [], "mention_turns": []},
    }


def _make_ctx(temp_db, presences=None, scene=None):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Tavern", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Bran Holt", json.dumps(default_character_data("Bran Holt")), "{}",
         time.time(), "char_bran"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    temp_db.wset(chat_id, "scene", scene if scene is not None else _scene())
    temp_db.wset(chat_id, "background_presences",
                 _presences() if presences is None else presences)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 5, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Tavern", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=5, player_input="",
                      created=time.time()),
        cast=cast, input="")


# --- co-presence resolution (the bug the first live run surfaced) ----------

def test_presence_room_resolves_through_entity_id(temp_db):
    sc = _scene()
    ids = _name_to_entity_id(sc)
    # No position keyed by the display name at all -- only by entity id.
    assert "Thin Local" not in (sc.get("positions") or {})
    assert _presence_room(sc, "Thin Local", {}, ids) == COMMON


def test_presence_room_falls_back_to_station_room(temp_db):
    sc = _scene()
    rec = {"sketch": {"station_room": CELLAR}}
    assert _presence_room(sc, "Unplaced Stranger", rec) == CELLAR


def test_managed_presences_covers_the_room_not_just_the_salient(temp_db):
    """The manager is handed the room's populace. Contrast
    pick_background_reactors, where every condition mirrors the player -- which
    is what made extras feel reactive rather than alive (§2.1)."""
    ctx = _make_ctx(temp_db)
    managed, p_room = managed_presences(ctx, cap=6)
    assert p_room == COMMON
    names = {n for _, n, _r, _rm in managed}
    # Both common-room presences, including the one with no dialogue history.
    assert names == {"The Barkeep", "Thin Local"}
    # The cellarman is behind a closed door -- outside the player's ambient
    # scope, so he is not this manager's to voice.
    assert "The Cellarman" not in names


def test_managed_presences_respects_cap(temp_db):
    ctx = _make_ctx(temp_db)
    managed, _ = managed_presences(ctx, cap=1)
    assert len(managed) == 1


# --- admission control: the hard guarantee (§3.11 layer 1) -----------------

def test_concealed_line_never_admitted(temp_db):
    ctx = _make_ctx(temp_db)
    sc = _scene()
    managed, _ = managed_presences(ctx, cap=6)
    dr = {"dialogue_log": [
        {"speaker": "Kessa Vane", "exact_quote": "The barrow map is a forgery.",
         "visibility": "concealed", "volume": "mutter"},
    ]}
    for level in ("ambient", "full"):
        assert _manager_events(ctx, dr, sc, managed, level) == []


def test_line_concealed_from_every_managed_presence_is_dropped(temp_db):
    ctx = _make_ctx(temp_db)
    sc = _scene()
    managed, _ = managed_presences(ctx, cap=6)
    entry = {"speaker": "Kessa Vane", "exact_quote": "Not in front of them.",
             "conceal_from": ["The Barkeep", "Thin Local"]}
    assert _audience_map(sc, entry, managed, "full") is None


def test_ambient_withholds_divergent_perception_entirely(temp_db):
    """At `ambient` the manager's context must hold nothing that is not common
    to every managed presence -- so contamination is impossible, not merely
    unlikely. The same event IS admitted at `full`, tagged inline."""
    ctx = _make_ctx(temp_db)
    sc = _scene()
    managed, _ = managed_presences(ctx, cap=6)
    entry = {"speaker": "Kessa Vane", "exact_quote": "Just between us.",
             "conceal_from": ["Thin Local"]}
    assert _audience_map(sc, entry, managed, "ambient") is None
    aud = _audience_map(sc, entry, managed, "full")
    assert aud["Thin Local"] == "none"
    assert aud["The Barkeep"] == "full"


def test_overt_shared_line_is_admitted_at_both_levels(temp_db):
    ctx = _make_ctx(temp_db)
    sc = _scene()
    managed, _ = managed_presences(ctx, cap=6)
    dr = {"dialogue_log": [{"speaker": "Kessa Vane", "exact_quote": "Three ales.",
                            "volume": "normal"}]}
    for level in ("ambient", "full"):
        events = _manager_events(ctx, dr, sc, managed, level)
        assert len(events) == 1
        assert set(events[0]["audience"].values()) == {"full"}


def test_concealed_content_is_redacted_from_the_directors_prose():
    """Admission control must cover the Director's PROSE, not just its
    dialogue_log. resolved_event is authored from the omniscient objective
    frame and can restate a whispered line verbatim; the manager path passed it
    raw until live play surfaced the gap."""
    dr = {
        "resolved_event": "Kessa leans in and murmurs that the map is a "
                          "forgery. The barkeep pulls a tap.",
        "dialogue_log": [
            {"speaker": "Kessa Vane", "visibility": "concealed",
             "exact_quote": '"the map is a forgery"'},
        ],
    }
    out = _redacted_resolved_event(dr)
    assert "forgery" not in out
    assert "The barkeep pulls a tap." in out


def test_overt_prose_survives_redaction():
    dr = {"resolved_event": "The barkeep slides three ales across the plank.",
          "dialogue_log": [{"speaker": "The Barkeep", "visibility": "overt",
                            "exact_quote": '"three ales"'}]}
    assert _redacted_resolved_event(dr) == \
        "The barkeep slides three ales across the plank."


# --- the verbatim floor (§3.3.1) ------------------------------------------

def test_withheld_bodies_collects_only_concealed_quotes(temp_db):
    dr = {"dialogue_log": [
        {"exact_quote": '"the map is a forgery and he knows it"',
         "visibility": "concealed"},
        {"exact_quote": '"three ales"', "visibility": "overt"},
    ]}
    bodies = _withheld_bodies(dr)
    assert len(bodies) == 1
    assert "forgery" in bodies[0]


def test_verbatim_floor_catches_reproduction():
    withheld = ["the map is a forgery and he knows it"]
    assert _reproduces_withheld('"The map is a forgery and he knows it."', withheld)
    # A distinctive run of the withheld line, not the whole thing.
    assert _reproduces_withheld('"map is a forgery and he knows something"',
                                withheld)
    assert not _reproduces_withheld('"Another round over here."', withheld)


# --- storage: frozen blurbs, routed conduct (§3.8, §3.11) -----------------

def test_blurb_is_written_once_and_never_rewritten():
    presences = {"The Barkeep": {}}
    _persist_blurbs({"blurbs": {"The Barkeep": {"manner": "clipped",
                                                "trait": "distrusts adventurers"}}},
                    presences)
    assert presences["The Barkeep"]["blurb"]["manner"] == "clipped"
    # A later mint must not overwrite: immutability is the anchor against the
    # self-feeding drift the profile-append loop creates (§3.11).
    _persist_blurbs({"blurbs": {"The Barkeep": {"manner": "sunny and talkative",
                                                "trait": "loves adventurers"}}},
                    presences)
    assert presences["The Barkeep"]["blurb"]["manner"] == "clipped"


def test_empty_blurb_is_not_persisted():
    presences = {"The Barkeep": {}}
    _persist_blurbs({"blurbs": {"The Barkeep": {"manner": "", "trait": ""}}},
                    presences)
    assert "blurb" not in presences["The Barkeep"]


def test_conduct_routes_to_its_own_presence():
    """The append is a ROUTING operation: the model emitted attributed entries
    and deterministic code files each under the name it carries."""
    presences = {"The Barkeep": {}, "Thin Local": {}}
    br = {"reactions": [
        {"name": "The Barkeep",
         "dialogue_log_entry": {"exact_quote": "Coin first."}, "action": ""},
        {"name": "Thin Local", "dialogue_log_entry": None,
         "action": "turns on his stool to watch"},
    ]}
    _append_manager_conduct(br, presences, turn_idx=7)
    assert 'said "Coin first."' in presences["The Barkeep"]["recent"][0]["text"]
    # An action-only entry still belongs in its own profile.
    assert "turns on his stool" in presences["Thin Local"]["recent"][0]["text"]
    assert presences["Thin Local"]["recent"][0]["turn"] == 7


def test_conduct_for_untracked_name_is_dropped():
    presences = {"The Barkeep": {}}
    _append_manager_conduct(
        {"reactions": [{"name": "Someone Invented",
                        "dialogue_log_entry": {"exact_quote": "hello"}}]},
        presences, turn_idx=3)
    assert "Someone Invented" not in presences
    assert "recent" not in presences["The Barkeep"]


def test_recent_tail_is_bounded():
    presences = {"The Barkeep": {}}
    for turn in range(10):
        _append_manager_conduct(
            {"reactions": [{"name": "The Barkeep",
                            "dialogue_log_entry": {"exact_quote": "line %d" % turn}}]},
            presences, turn_idx=turn)
    tail = presences["The Barkeep"]["recent"]
    assert len(tail) == 4
    assert "line 9" in tail[-1]["text"]


# --- registered characters are never furniture (Enterprise run) -----------

def test_titled_registered_character_is_not_managed(temp_db):
    """The Director wrote "Captain Jean-Luc Picard" where the roster held
    "Jean-Luc Picard", so an exact-casefold check tracked a REGISTERED
    character as a background presence and handed him to the stateless manager.
    The model declined to puppet him; the guarantee must not depend on that."""
    scene = _scene()
    scene["positions"]["Bran Holt"] = COMMON
    presences = dict(_presences())
    presences["Captain Bran Holt"] = {
        "first_turn": 0, "last_turn": 9, "dialogue_turns": [],
        "mention_turns": [], "sketch": {"station_room": COMMON}}
    ctx = _make_ctx(temp_db, presences=presences, scene=scene)
    managed, _ = managed_presences(ctx, cap=6)
    names = {n for _, n, _r, _rm in managed}
    assert "Captain Bran Holt" not in names   # Bran Holt is registered cast
    assert "The Barkeep" in names


def test_ref_dedup_drops_a_scanned_fragment_of_a_declared_ref(temp_db):
    """The scan re-finds pieces of what the model already declared."""
    from agents.background import _claimed_refs
    entry = {"asserts": ["Two D'deridex-class warbirds"]}
    refs = _claimed_refs(entry, "Two D'deridex-class warbirds, bearing mark eight.",
                         {"The Barkeep"})
    assert refs == ["Two D'deridex-class warbirds"]


def test_long_declared_ref_is_truncated_to_a_matchable_key(temp_db):
    """A ref is a ratification key, not a summary."""
    from agents.background import _claimed_refs
    from background_claims import MAX_REF_WORDS
    entry = {"asserts": ["EPS relay feeding the tactical console's deck-nine "
                         "junction suffered real hardware damage from the short"]}
    refs = _claimed_refs(entry, "The damage is real.", {"The Barkeep"})
    assert len(refs) == 1
    assert len(refs[0].split()) <= MAX_REF_WORDS


# --- the stage names itself in the pipeline UI ----------------------------

def test_stage_label_names_the_path_it_takes(temp_db):
    """The manager and the per-presence backstop share a step key, so without
    a mode-aware label the pipeline UI showed "Background · presence reaction"
    while the manager was doing all the work."""
    from agents.runtime import _background_stage_label
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("L", "", 0))
    assert _background_stage_label(cid) == "Background · presence reaction"
    temp_db.wset(cid, "background_config", {"scene_life": "ambient"})
    assert "ambient" in _background_stage_label(cid)
    temp_db.wset(cid, "background_config", {"scene_life": "full"})
    assert _background_stage_label(cid).startswith("Scene life")


def test_stage_label_survives_a_broken_config(temp_db):
    from agents.runtime import _background_stage_label
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("L", "", 0))
    temp_db.wset(cid, "background_config", {"scene_life": "nonsense"})
    assert _background_stage_label(cid) == "Background · presence reaction"


def test_result_reports_mode_and_sub_agents():
    """The technical log needs to distinguish one call voicing a whole room
    from one presence reacting."""
    from agents.background import _result
    out = _result(["A"], [], mode="scene_life:full",
                  agent_calls=["blurb_mint", "scene_life"])
    assert out["mode"] == "scene_life:full"
    assert out["agent_calls"] == ["blurb_mint", "scene_life"]
    # Default keeps the historical shape for the per-presence path.
    assert _result([], [])["mode"] == "background_react"
