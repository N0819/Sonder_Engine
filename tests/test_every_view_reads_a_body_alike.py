"""One body, one reading, in every view that delivers it.

Found while building distance-based level of detail (dab39f66, reverted in
594e4f67: the owner's level of detail is for distant landscapes, never
ordinary range) and true without it. Each is a place where two deliveries
of one beat disagreed about a body, and the one that said more was free to
be believed:

  * Across a doorway the act channel took its ADMISSION from the
    room-to-room edge and its DETAIL from the body-level grade, and turned a
    body-level `none` into `full` -- an act whose body the doorway's cone
    refuses was delivered whole (probed 2026-10-04).
  * The interaction micro-round labelled an actor from the card's TRUE
    appearance and bare name recognition: a disguised actor was named to
    anyone who knew the name, and an unseen stranger was described by a face
    nobody saw. It delivered every admitted act in full where the composed
    view of the same beat gives a body moving, or nothing.
  * The narrator's pronoun roster keyed every stranger by appearance, seen
    or not; its labels ignored what the player's view called a body; and two
    bodies the view could not tell apart overwrote each other in the
    position payload.
  * The Japanese renderer placed a body seen in another room 「ここ」.
  * A character's orientation frame named a stranger in the dim by the
    descriptor the view withheld.
"""

from __future__ import annotations

import inspect
import json
import time

from world.spatial import spatial_rel_between, visual_level_between


# --------------------------------------------------------------------------
# Scenes
# --------------------------------------------------------------------------

def _doorframe():
    """A lit hall and a lit yard through an open door, Ben at a post on the
    door's own wall: the doorway's cone refuses him to anyone in the hall."""
    return {"rooms": {
        "hall": {"name": "hall", "desc": ".", "extent": {"w": 8, "d": 8},
                 "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "e"}]},
        "yard": {"name": "yard", "desc": ".", "extent": {"w": 20, "d": 20},
                 "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "w"}],
                 "anchors": {"post": {"desc": "a post", "dir": "w"}}}},
        "positions": {"Ada": "hall", "Ben": "yard"},
        "stations": {"Ben": {"at": "post"}}, "entities": {}}


def _yard_and_dark_barn():
    """A lit yard, a dark barn through a wide opening, both bodies pinned on
    one clear line through it (a doorway's cells are laid along its wall by
    hash -- rows 1-4 on the yard's side here)."""
    def room(name, light, to, d):
        return {"name": name, "desc": ".", "light": light,
                "extent": {"w": 20, "d": 20},
                "adjacent": [{"to": to, "barrier": "open", "dir": d, "width": 4}]}
    return {"rooms": {"yard": room("the yard", "lit", "barn", "e"),
                      "barn": room("the barn", "dark", "yard", "w")},
            "positions": {"Ada": "yard", "Ben": "barn"},
            "stations": {"Ada": {"cell": [18, 2]}, "Ben": {"cell": [8, 15]}},
            "entities": {}}


def _far_field():
    """Two lit rooms joined by an open edge authored `far`: a figure across
    it is `shapes` (`spatial_senses._visual_level_between`)."""
    return {"rooms": {
        "yard": {"name": "the yard", "desc": ".", "light": "lit", "adjacent": [
            {"to": "field", "barrier": "open", "dir": "n", "distance": "far"}]},
        "field": {"name": "the field", "desc": ".", "light": "lit", "adjacent": [
            {"to": "yard", "barrier": "open", "dir": "s", "distance": "far"}]}},
        "positions": {}, "stations": {}, "entities": {}}


# --------------------------------------------------------------------------
# The act channel across a doorway
# --------------------------------------------------------------------------

def test_an_act_the_doorway_cone_refuses_is_not_delivered():
    from agents.perception import _sight_detail
    sc = _doorframe()
    assert visual_level_between(sc, "Ada", "Ben") == "none"
    rel = spatial_rel_between(sc, "Ada", "Ben")
    assert _sight_detail(sc, "Ada", "Ben", rel) == "none"


def test_the_same_room_carve_out_is_untouched():
    """Inside the observer's own room `_in_plain_view` admits the act and
    only an opaque body in the way subtracts (PE9); an unlit room goes on
    admitting a co-present act in full, as it did."""
    from agents.perception import _sight_detail
    sc = {"rooms": {"cellar": {"name": "the cellar", "desc": ".", "light": "dark"}},
          "positions": {"Ada": "cellar", "Ben": "cellar"}, "stations": {},
          "entities": {}}
    assert visual_level_between(sc, "Ada", "Ben") == "none"
    assert _sight_detail(sc, "Ada", "Ben", spatial_rel_between(sc, "Ada", "Ben")) == "full"


def test_sight_that_needs_no_light_sees_the_act_it_sees_the_body_in():
    """The doorway's cone leaves a body deep in the barn a shape; the dark
    leaves ordinary eyes nothing, and eyes that need no light the shape."""
    from agents.perception import _sight_detail
    sc = _yard_and_dark_barn()
    owl = [{"channel": "sight", "needs_light": False}]
    rel = spatial_rel_between(sc, "Ada", "Ben")
    assert visual_level_between(sc, "Ada", "Ben") == "none"
    assert visual_level_between(sc, "Ada", "Ben", owl) == "shapes"
    assert _sight_detail(sc, "Ada", "Ben", rel) == "none"
    assert _sight_detail(sc, "Ada", "Ben", rel, senses=owl) == "shapes"


def test_keen_eyes_never_read_an_act_through_a_door():
    """The "Long Gallery" case: a body just through a locked door is a shape
    for a beat. A keen card reads further; it does not read through a door
    -- acuity never lifts the act channel (`visual_level_between` spends a
    card on the night-vision bit alone)."""
    from agents.perception import _sight_detail
    sc = {"rooms": {
        "hall": {"name": "hall", "desc": ".", "adjacent": [
            {"to": "study", "barrier": "closed_door", "locked": True, "dir": "n"}]},
        "study": {"name": "study", "desc": ".", "adjacent": [
            {"to": "hall", "barrier": "closed_door", "locked": True, "dir": "s"}]}},
        "positions": {"Edmund": "hall", "Ada": "study"}, "stations": {},
        "crossings": {"Ada": {"from": "hall", "to": "study", "beats": 2}},
        "entities": {}}
    keen = [{"channel": "sight", "acuity": "keen"}]
    assert visual_level_between(sc, "Edmund", "Ada") == "shapes"
    rel = spatial_rel_between(sc, "Edmund", "Ada")
    assert _sight_detail(sc, "Edmund", "Ada", rel, senses=keen) == "shapes"


def test_a_dulled_eye_is_shown_no_act_from_a_body_it_cannot_see():
    """A figure across a far edge is a shape to ordinary eyes and nothing to
    dulled ones -- the presence line says so (`composer._sense_graded`), and
    the act from that body must not arrive without it."""
    from agents.composer import _sense_graded
    from agents.perception import _sight_detail
    sc = _far_field()
    sc["positions"].update({"Ada": "yard", "Ben": "field"})
    dulled = [{"channel": "sight", "acuity": "dulled"}]
    rel = spatial_rel_between(sc, "Ada", "Ben")
    assert visual_level_between(sc, "Ada", "Ben") == "shapes"
    assert _sense_graded("shapes", "sight", dulled) == "none"
    assert _sight_detail(sc, "Ada", "Ben", rel) == "shapes"
    assert _sight_detail(sc, "Ada", "Ben", rel, senses=dulled) == "none"


def test_both_composed_views_hand_the_act_grader_the_observers_card():
    from agents import perception
    for fn in (perception._composer_act_views, perception._composer_outcome_views):
        src = inspect.getsource(fn)
        start = src.index("sight=_sight_detail(")
        assert "senses=p.get(\"sense_card\")" in src[start:start + 160], fn.__name__


# --------------------------------------------------------------------------
# The interaction micro-round
# --------------------------------------------------------------------------

def _micro_ctx(temp_db, sc, appearances, known, reactors=(2, 3)):
    from core.db import wset
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_character_data
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Micro", "", time.time()))
    cast = []
    for cid, name in enumerate(appearances, start=1):
        sheet = default_character_data(name)
        sheet["embodiment"]["visible"] = {"summary": appearances[name]}
        cast.append({"id": cid, "sheet": json.dumps(sheet), "cstate": "{}",
                     "stance": "{}"})
    sc.update({"location": "x", "time": "day", "attire": {}, "overlays": {}})
    wset(chat_id, "scene", sc)
    wset(chat_id, "known", known)
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Micro", scenario="", persona_id=None,
                      lorebook_id=None, created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="", director_interpret={"flow": {"reactors": list(reactors)}})


APPEARANCES = {"Alice": "A tall fox-eared woman in a green coat.",
               "Bob": "A stocky man.", "Cara": "A slight girl."}


def test_the_micro_round_names_no_one_through_a_disguise_that_hides_who_they_are(temp_db):
    from agents.loops import deterministic_micro_perception
    from agents.perception import _DISGUISES_CACHE, _TRANSFORMATIONS_CACHE
    sc = {"rooms": {"hall": {"name": "the hall", "desc": ".", "light": "lit"}},
          "positions": {"Alice": "hall", "Bob": "hall", "Cara": "hall"},
          "stations": {}, "entities": {}}
    ctx = _micro_ctx(temp_db, sc, APPEARANCES,
                     {"Bob": ["Alice"], "Cara": ["Alice"]})
    ctx[_DISGUISES_CACHE] = {"alice": {
        "presented_appearance": "A hooded pilgrim in a grey cloak.",
        "known_to": ["Cara"], "conceals_identity": True}}
    ctx[_TRANSFORMATIONS_CACHE] = {}
    views, _ = deterministic_micro_perception(
        ctx, 1, {"sequence": [{"type": "speech", "text": "Make way.",
                               "volume": "normal"}]}, sc)
    assert "Alice" not in views[2][0] and "fox" not in views[2][0]
    assert "pilgrim" in views[2][0]
    assert "Alice" in views[3][0]             # she told Cara


def test_the_micro_round_describes_no_face_nobody_saw(temp_db):
    from agents.loops import deterministic_micro_perception
    sc = {"rooms": {"cellar": {"name": "the cellar", "desc": ".", "light": "dark"}},
          "positions": {"Alice": "cellar", "Bob": "cellar", "Cara": "cellar"},
          "stations": {}, "entities": {}}
    ctx = _micro_ctx(temp_db, sc, APPEARANCES, {})
    views, _ = deterministic_micro_perception(
        ctx, 1, {"sequence": [{"type": "speech", "text": "Who's there?",
                               "volume": "normal"}]}, sc)
    assert "Who's there?" in views[2][0]
    assert "fox" not in views[2][0] and "green coat" not in views[2][0]


def test_the_micro_round_names_a_far_stranger_as_the_composed_view_does(temp_db):
    """Across an authored far edge the composed view calls her "an
    indistinct figure"; the round described her by the face the distance
    withheld. What she does still arrives whole here -- see the comment at
    the act branch for why the shape's collapse to motion is not spread."""
    from agents.loops import deterministic_micro_perception
    sc = _far_field()
    sc["positions"].update({"Alice": "field", "Bob": "yard", "Cara": "field"})
    ctx = _micro_ctx(temp_db, sc, APPEARANCES, {})
    views, _ = deterministic_micro_perception(
        ctx, 1, {"sequence": [{"type": "action",
                               "observable": "raises a silver key"}]}, sc)
    assert visual_level_between(sc, "Bob", "Alice") == "shapes"
    assert views[2][0].startswith("an indistinct figure")
    assert "silver key" in views[2][0] and "fox" not in views[2][0]
    assert "fox-eared" in views[3][0]         # Cara is beside her


def test_the_micro_round_delivers_no_act_the_doorway_cone_refuses(temp_db):
    """And says so, as `composer.act_percept` says so for the same pair --
    never a "delivered" row from the surface admission for an act the
    observer then does not receive (review 2026-10-05)."""
    from agents.loops import deterministic_micro_perception
    from core.pipeline_context import current_decision_sink
    sc = _doorframe()
    sc["positions"] = {"Alice": "yard", "Bob": "hall", "Cara": "loft"}
    sc["rooms"]["loft"] = {"name": "loft", "desc": ".", "adjacent": []}
    sc["stations"] = {"Alice": {"at": "post"}}
    ctx = _micro_ctx(temp_db, sc, {k: APPEARANCES[k] for k in ("Alice", "Bob", "Cara")},
                     {}, reactors=(2,))
    assert visual_level_between(sc, "Bob", "Alice") == "none"
    rows = []
    token = current_decision_sink.set(lambda *a, **k: rows.append(a))
    try:
        views, _ = deterministic_micro_perception(
            ctx, 1, {"sequence": [{"type": "action",
                                   "observable": "tosses Cara a silver key, then waves"}]},
            sc)
    finally:
        current_decision_sink.reset(token)
    assert 2 not in views
    mine = [r for r in rows if r[1] == "Alice -> Bob"]
    assert [r[2] for r in mine] == ["refused"]


# --------------------------------------------------------------------------
# The narrator
# --------------------------------------------------------------------------

HE = {"subject": "he", "object": "him", "possessive": "his"}
SHE = {"subject": "she", "object": "her", "possessive": "hers"}


def _sheet_row(name, pronouns):
    return {"sheet": json.dumps({"identity": {"name": name, "pronouns": pronouns}})}


def test_the_narrator_labels_a_body_as_the_players_view_did():
    from agents.narration import _earned_labels, _speaker_display

    class Ctx(dict):
        pass
    ctx = Ctx(perception_outcome={"company": {"player": [
        {"key": "k", "name": "Ben", "label": "an indistinct figure",
         "recognized": False}]}})
    earned = _earned_labels(ctx)
    assert _speaker_display("Ben", set(), "a tall fox-eared woman", [],
                            earned=earned) == "an indistinct figure"
    assert _speaker_display("Cara", set(), "a short man", [],
                            earned=earned) != "an indistinct figure"
    assert _earned_labels(Ctx(perception_establish={"company": {"player": [
        {"name": "Ben", "label": "the tall woman"}]}})) == {"Ben": "the tall woman"}


def test_the_pronoun_roster_holds_only_bodies_the_view_named_or_showed():
    from agents.narration import _cast_pronouns, _roster_label
    views = {"Ben": "the tall man", "Cara": "the short woman", "Dov": "Dov"}
    label = _roster_label(views.get, {"Ben": "the tall man"}, {"Dov"})
    cast = [_sheet_row("Ben", HE), _sheet_row("Cara", SHE), _sheet_row("Dov", HE)]
    assert set(_cast_pronouns(cast, label=label)) == {"the tall man", "Dov"}


def test_the_narrator_builds_its_roster_from_that_rule():
    from agents import narration
    src = inspect.getsource(narration.narrator)
    assert "_cast_pronouns(ctx.cast, label=_roster_label(" in src


def test_two_bodies_the_view_cannot_tell_apart_keep_an_arrival(temp_db):
    """Keyed by a label they share, the second in cast order overwrote the
    first -- and with it an arrival's `moved`. One entry, as the view gives
    them one label, and the arrival wins whichever order the cast is in;
    every body stays in the facts, under the label prose can say (review
    2026-10-05: numbering it "(2)" broke the pronoun lookup and both
    screens)."""
    from agents.narration import _position_delta_payload
    from core.db import wset
    rooms = {"hall": {"name": "the hall", "desc": ".", "light": "lit",
                      "adjacent": [{"to": "kitchen", "barrier": "open_door"}]},
             "kitchen": {"name": "the kitchen", "desc": ".", "light": "lit",
                         "adjacent": [{"to": "hall", "barrier": "open_door"}]}}
    twin = {"appearance": "A tall woman in grey.", "aliases": []}
    for order in (("Ada", "Bea"), ("Bea", "Ada")):
        ctx = _micro_ctx(temp_db, {
            "rooms": rooms, "positions": {"Pip": "hall", "Ada": "kitchen",
                                          "Bea": "hall"},
            "stations": {}, "entities": {}},
            {n: "A tall woman in grey." for n in order}, {})
        ctx["outcome_scene"] = {"rooms": rooms, "stations": {}, "entities": {},
                                "positions": {"Pip": "hall", "Ada": "hall",
                                              "Bea": "hall"}}
        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (ctx.chat.id,))[0])
        payload, facts, _ = _position_delta_payload(
            ctx, chat, "Pip", "hall", set(), {n: twin for n in order})
        (label, entry), = payload.items()
        assert entry["moved"] is True and entry["prev_room"] == "the kitchen"
        assert [f["name"] for f in facts] == [label, label]
        assert {f["key"] for f in facts} == {"Ada", "Bea"}
        assert "(2)" not in label


# --------------------------------------------------------------------------
# Japanese: a body in another room is in that room
# --------------------------------------------------------------------------

def _beyond(body="b1"):
    from agents.composer import Percept
    return Percept(kind="presence", channel="sight", source_label="Ben",
                   fidelity="full",
                   data={"tier": "beyond", "room": "台所", "side": None,
                         "arc": "front", "sight": "full", "body": body},
                   salience=0.35, dedupe_key="presence:%s:x" % body)


def test_a_body_in_another_room_is_in_that_room_in_japanese():
    from agents.composer import render_view
    text = render_view([_beyond()], mode="player", full_render=True,
                       language="ja").text
    assert "台所" in text and "ここ" not in text


def test_an_unchanged_body_in_another_room_stays_in_that_room_in_japanese():
    from agents.composer import Percept, render_view
    beyond = _beyond("b3")
    bell = Percept(kind="ambient", channel="hearing", source_label="",
                   fidelity="full", data={"desc": "鐘が鳴る。"}, salience=0.5,
                   order_key=1, dedupe_key="ambient:bell")
    text = render_view([beyond, bell], mode="player",
                       prev_standing={beyond.dedupe_key}, language="ja").text
    assert "台所" in text and "ここ" not in text


# --------------------------------------------------------------------------
# A character's orientation frame
# --------------------------------------------------------------------------

def test_the_orientation_frame_names_a_stranger_in_the_dim_as_the_view_does(temp_db):
    """The frame's `ahead_entity` said "the tall fox-eared woman" while the
    view beside it said "an indistinct figure". The identity labeller every
    REFERENCE uses -- an address, a past teller, lore -- keeps the
    descriptor, and a thing stays itself."""
    from agents.common import observer_label_fn, observer_view_label_fn
    from core.db import wset
    from story.character_schema import default_character_data
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Dim hall", "", time.time()))
    wset(chat_id, "known", {})
    ben = default_character_data("Ben")
    ben["embodiment"]["visible"] = {"summary": "a tall fox-eared woman"}
    cast = [{"id": 1, "sheet": json.dumps(default_character_data("Ada"))},
            {"id": 2, "sheet": json.dumps(ben)}]
    sc = {"rooms": {"hall": {"name": "the hall", "desc": ".", "light": "dim"}},
          "positions": {"Ada": "hall", "Ben": "hall", "fountain": "hall"},
          "stations": {}, "entities": {"fountain": {"name": "fountain",
                                                    "kind": "fixture"}}}
    chat = {"id": chat_id}
    view = observer_view_label_fn(chat, "Ada", cast, sc)
    ident = observer_label_fn(chat, "Ada", cast, scene=sc)
    assert view("Ben") == "an indistinct figure"
    assert ident("Ben") not in ("an indistinct figure", "Ben")
    assert view("fountain") == ident("fountain") == "fountain"
    sc["rooms"]["hall"]["light"] = "lit"
    assert observer_view_label_fn(chat, "Ada", cast, sc)("Ben") == ident("Ben")


def test_the_orientation_frame_gives_a_townsperson_the_views_own_silhouette(temp_db):
    """A charter body with a dealt surface, in a dim hall: the view calls
    him by his silhouette, and the frame did not -- it said "an indistinct
    figure", the view's word for a DIFFERENT body there (review 2026-10-05,
    reproduced end to end). Read from the real perception stage's record of
    what it called him."""
    from agents import perception
    from agents.common import observer_label_fn, observer_view_label_fn
    from core.db import wset
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_character_data, default_persona_data
    from story.scene import get_scene
    from world import charter_surface as cs
    from world.charter_model import normalize_charter
    from world.charter_runtime import background_presence_records, save_registry
    law = {"stature": ["towering", "squat"], "build": ["barrel-chested", "reedy"],
           "gait": ["rolling", "mincing"], "complexion": ["ash-pale", "copper-dark"],
           "hair": ["a tarred queue", "a cropped fringe"], "age": ["greybeard", "green"],
           "marks": ["a rope burn across the palm"]}
    post = {"place": "hall", "serves": [], "requires": {},
            "worn": ["a scorched leather apron"], "marks": ["soot in the creases"]}
    name = "Reeve Bram Fenwick"
    charter = normalize_charter({
        "key": "hall", "looks": law, "posts": {"reeve": dict(post)},
        "bodies": {"reeve:0001": {"name": name, "home_post": "reeve", "place": "hall",
                                  "berth": "cottage",
                                  "surface": cs.deal_surface("hall", "reeve:0001", law,
                                                             post=post)}},
        "watch": {"reeve": "reeve:0001"}})
    persona_id = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                            ("Pip", json.dumps(default_persona_data("Pip")), "{}"))
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                         "VALUES(?,?,?,?)", ("Surface", "", time.time(), persona_id))
    ada = default_character_data("Ada")
    ada["embodiment"]["visible"] = {"summary": "A small woman in a grey cloak."}
    ada_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                        "VALUES(?,?,?,?,?)", ("Ada", json.dumps(ada), "{}", time.time(),
                                              "ada-%s" % time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, ada_id, "active", "{}"))
    save_registry(chat_id, {"hall": charter})
    surface = next(iter(background_presence_records(
        chat_id, places={"hall"}).values()))["sketch"]["surface"]
    wset(chat_id, "background_presences", {"p_reeve": {
        "uid": "p_reeve", "name": name, "nature": "person",
        "charter_refs": [{"charter": "hall", "body": "reeve:0001"}],
        "sketch": {"role_hint": "reeve", "station_room": "hall", "surface": surface,
                   "appearance": cs.appearance_text(surface, noun="reeve")},
        "first_turn": 0, "last_turn": 0, "entity_id": "e_reeve",
        "dialogue_turns": [], "mention_turns": [], "addressed_turns": []}})
    labels = {}
    for idx, light in enumerate(("dim", "lit"), start=1):
        wset(chat_id, "scene", {
            "rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": light}},
            "positions": {"Pip": "hall", "Ada": "hall", "e_reeve": "hall"},
            "stations": {}, "location": "x", "time": "day", "attire": {}, "overlays": {},
            "entities": {"e_reeve": {"name": name, "kind": "person",
                                     "charter_ref": {"charter": "hall",
                                                     "body": "reeve:0001"}}}})
        wset(chat_id, "known", {})
        cast = temp_db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                         "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
                         (chat_id,))
        turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                             "VALUES(?,?,?,?)", (chat_id, idx, "", time.time()))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Surface", persona_id=persona_id,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx, player_input="",
                          created=time.time()),
            cast=cast, input="")
        ctx["_player_room"] = "hall"
        ctx.director_interpret = {
            "action": {"attempt": "waits", "visibility": "overt", "conceal_from": [],
                       "targets": [], "commitment": "asserted"},
            "sequence": [{"type": "action", "attempt": "waits", "observable": "waits",
                          "visibility": "overt", "conceal_from": [], "targets": [],
                          "commitment": "asserted", "verb": "wait", "stage": "immediate",
                          "event_id": "turn:1:player:0:action"}],
            "speech": None, "speech_volume": "normal", "flow": {"reactors": [ada_id]}}
        out = perception.perception_act(ctx, nonce="n")
        viewed = {r["name"]: r["label"]
                  for r in (out.get("company") or {}).get(str(ada_id)) or []}
        sc = get_scene(chat_id, {"id": chat_id})
        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,))[0])
        frame = observer_view_label_fn(chat, "Ada", cast, sc)(name)
        labels[light] = (viewed.get(name), frame,
                         observer_label_fn(chat, "Ada", cast, scene=sc)(name))
    dim_view, dim_frame, _ = labels["dim"]
    assert dim_view and dim_frame == dim_view and "apron" in dim_frame
    lit_view, lit_frame, lit_ident = labels["lit"]
    assert lit_frame == lit_ident


def test_the_character_step_hands_its_present_tense_fields_the_view_labeller():
    from agents import character
    src = inspect.getsource(character.character_step)
    assert "spatial_digest(sc, character_name(sh),\n" \
           "                               label_for=observer_view_label_fn(" in src


def test_an_extra_seat_keys_its_roster_by_its_own_view():
    """A second human is a second observer: the labels and the pronoun
    roster come from what THAT seat's view earned (`company["extra:<id>"]`)."""
    from agents.narration import _earned_labels

    class Ctx(dict):
        pass
    ctx = Ctx(perception_outcome={"company": {
        "player": [{"name": "Ben", "label": "the tall woman"}],
        "extra:7": [{"name": "Ben", "label": "an indistinct figure"}]}})
    assert _earned_labels(ctx) == {"Ben": "the tall woman"}
    assert _earned_labels(ctx, seat="extra:7") == {"Ben": "an indistinct figure"}
    from agents import narration
    src = inspect.getsource(narration.narrator_extra)
    assert 'earned = _earned_labels(ctx, seat=f"extra:{pid_key}")' in src
    assert "earned=earned, roster=True)" in src


def test_a_motion_only_act_is_filed_as_ambiguous():
    """It had no entry in `_FIDELITY_AMBIGUITY`, so "an indistinct figure
    moves, too little of it to make out" went into memory with the resting
    values of a full sighting."""
    from agents.composer import Percept, observations_from_render, render_view
    act = Percept(kind="act", channel="sight", source_label="an indistinct figure",
                  fidelity="shapes", data={"surface": ""}, salience=0.5,
                  order_key=0, dedupe_key="act:x")
    rows = observations_from_render("2", render_view([act], mode="character",
                                                     full_render=True))
    assert rows and rows[0]["fidelity"] == "ambiguous"
