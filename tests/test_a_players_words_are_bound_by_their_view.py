"""WHOM A PLAYER'S WORDS ARE FOR IS READ OFF THEIR OWN VIEW.

O8/O23/O25 of the Cwm Du run (chat 167). A player picks people out by what
their view showed them -- a description, a guess at who someone is, a
pronoun -- and the interpretation turned those words into a name against the
all-knowing world index, which said nothing of what the player perceived or
who had just spoken to them:

- 4617: "the man behind the bar" became a potman the view never described,
  while the landlord it had shown stood there;
- 4627: "you'll be the overman" became a man who had walked in unseen, while
  the man her view had shown as the overman stood on the rails;
- 4628: a reply to the man who had just answered her went to her companion.

The same class at chat 165 turn 4582: "the old keeper" bound to a man the
view never showed, beside the old keeper it had.

The owner's ruling (2026-10-10): give the interpretation the player's view
(`player_knows_as`, `last_lines`), one card clause, and ONE re-ask when the
account names somebody no player perceived and no input named. With it, two
repairs to the index the investigation found: a charter body the scene
stands keeps its look and is listed once (4627-4628), and a thing placed
under its own name is not a body (chat 155).
"""

from __future__ import annotations

import json
import time

from agents import director, director_prose
from agents.composer import body_key
from agents.director import causal_world_index, index_people
from tests.director_fakes import _make_ctx, encoder_event

PLAYER = "The Stranger"     # the persona a `_make_ctx` chat plays


class TestTheIndexListsEachBodyOnce:
    SCENE = {
        "rooms": {"pit_bottom": {"name": "Pit Bottom", "adjacent": [
                      {"to": "main_level", "barrier": "open", "distance": "near"}]},
                  "main_level": {"name": "Main Level", "adjacent": [
                      {"to": "pit_bottom", "barrier": "open", "distance": "near"}]}},
        "positions": {"Nell Hartley": "main_level", "Gwenafryn Abogwyn": "pit_bottom",
                      "Prysenlas Cadyfawr": "main_level"},
        "entities": {
            "Gwenafryn Abogwyn": {"name": "Gwenafryn Abogwyn", "kind": "person",
                                  "charter_ref": {"charter": "colliery", "body": "hewer:0005"}},
            "Prysenlas Cadyfawr": {"name": "Prysenlas Cadyfawr", "kind": "person",
                                   "charter_ref": {"charter": "colliery", "body": "overman:0001"}}},
    }
    FIGURES = [
        {"name": "Gwenafryn Abogwyn", "room": "main_level", "role": "hewer",
         "look": "a heavy man in his prime with slate dust in his beard",
         "charter": "colliery", "body": "hewer:0005"},
        {"name": "Prysenlas Cadyfawr", "room": "main_level", "role": "overman",
         "look": "a broad-shouldered, stooping man in a battered felt hat",
         "charter": "colliery", "body": "overman:0001"},
        {"name": "Dai Haulier", "room": "main_level", "role": "haulier",
         "look": "a boy with a lamp", "charter": "colliery", "body": "haulier:0002"},
    ]

    def test_a_charter_body_the_scene_stands_is_its_row_with_its_look(self):
        index = causal_world_index(self.SCENE, room_ids=["pit_bottom", "main_level"],
                                   figures=self.FIGURES)
        rows = {room: {row["id"]: row for row in index["rooms"][room]["holds"]}
                for room in ("pit_bottom", "main_level")}
        # 4627: the hewer the scene stands at the pit bottom is listed there
        # alone -- not again at his post's level -- and with his look
        assert "Gwenafryn Abogwyn" not in rows["main_level"]
        assert rows["pit_bottom"]["Gwenafryn Abogwyn"]["look"] == self.FIGURES[0]["look"]
        # 4628: the leased overman was a bare row between a bag and a knife
        overman = rows["main_level"]["Prysenlas Cadyfawr"]
        assert (overman["kind"], overman["role"]) == ("entity", "overman")
        assert overman["look"] == self.FIGURES[1]["look"]
        # a figure the scene does not stand is listed as one, where it is
        assert rows["main_level"]["Dai Haulier"]["kind"] == "figure"

    def test_a_thing_placed_under_its_own_name_is_no_body(self):
        """Chat 155: `positions` held "folded warm towel" by its display name,
        its record by a hash id, and the index called the towel a body."""
        scene = {"rooms": {"treatment_room": {"name": "Treatment Room", "adjacent": []}},
                 "positions": {"Hinami": "treatment_room",
                               "folded warm towel": "treatment_room"},
                 "entities": {"7cc44255bf8c47fd": {"name": "folded warm towel",
                                                   "kind": "object"}}}
        index = causal_world_index(scene, room_ids=["treatment_room"])
        rows = {row["id"]: row for row in index["rooms"]["treatment_room"]["holds"]}
        assert rows["folded warm towel"]["kind"] == "entity"
        assert rows["Hinami"]["kind"] == "body"
        people, in_view = index_people(index, scene, {"persona:1": "Hinami"})
        assert "folded warm towel" not in people and in_view == ["Hinami"]

    def test_the_people_are_the_index_bodies_and_the_identities(self):
        index = causal_world_index(self.SCENE, room_ids=["pit_bottom", "main_level"],
                                   figures=self.FIGURES)
        people, in_view = index_people(index, self.SCENE, {"character:84": "Ffion Rees"})
        assert set(in_view) == {"Nell Hartley", "Gwenafryn Abogwyn",
                                "Prysenlas Cadyfawr", "Dai Haulier"}
        assert set(people) == set(in_view) | {"Ffion Rees"}


# ---- the one re-ask ---------------------------------------------------------

PEOPLE = {"Nell Hartley": ["Nell Hartley"],
          "Mr Llanarfryn Eigalyn": ["Llanarfryn Eigalyn", "Mr Llanarfryn Eigalyn"],
          "Mr Bryinwyr Rhiadd": ["Bryinwyr Rhiadd", "Mr Bryinwyr Rhiadd"],
          "Ffion Rees": ["Ffion Rees"]}
PERCEIVED = ["ffion rees", "mr llanarfryn eigalyn", "nell hartley"]
HERE = ["Ffion Rees", "Mr Llanarfryn Eigalyn"]
INPUT = "Nell turns back to the man behind the bar. \"I'll want your room tonight.\""
FIRST = ("Nell Hartley turns back to Mr Bryinwyr Rhiadd behind the bar. She says, "
         "\"I'll want your room tonight.\"")
SECOND = ("Nell Hartley turns back to Mr Llanarfryn Eigalyn behind the bar. She says, "
          "\"I'll want your room tonight.\"")


class TestTheAccountIsAskedAgainOnce:
    def test_4617_naming_a_man_her_view_never_showed_is_asked_again(self):
        asked = []

        def ask(note):
            asked.append(note)
            return SECOND, []
        prose, _places, record = director_prose.aim_by_their_view(
            INPUT, FIRST, [], PEOPLE, PERCEIVED, ask, perceived_here=HERE)
        assert asked == [{"named_unperceived": ["Mr Bryinwyr Rhiadd"]}]
        assert prose == SECOND
        assert (record["kept"], record["still_named"]) == ("again", [])

    def test_with_nobody_perceived_here_nothing_is_reaimed(self):
        """Chat 160 turn 4540: "Science lady!" as a stranger skids into the
        lift. Nobody perceived is there to mean instead."""
        def ask(note):
            raise AssertionError("asked again with nothing to re-aim at")
        prose, _places, record = director_prose.aim_by_their_view(
            INPUT, FIRST, [], PEOPLE, PERCEIVED, ask, perceived_here=[])
        assert (prose, record) == (FIRST, {})

    def test_a_person_an_input_names_is_the_players_to_name(self):
        named = director_prose.people_named_unperceived
        assert named(FIRST, INPUT, PEOPLE, PERCEIVED) == ["Mr Bryinwyr Rhiadd"]
        assert named("Nell Hartley asks Mr Bryinwyr Rhiadd for a room.",
                     "\"A room, Mr Rhiadd.\"", PEOPLE, PERCEIVED) == []
        assert named(SECOND, INPUT, PEOPLE, PERCEIVED) == []

    def test_a_name_is_read_in_any_script(self):
        people = {"佐藤花子": ["佐藤花子"], "ネル": ["ネル"]}
        named = director_prose.people_named_unperceived
        assert named("ネルは佐藤花子に話しかける。", "「すみません」", people,
                     ["ネル"]) == ["佐藤花子"]
        assert named("ネルは佐藤花子に話しかける。", "佐藤花子さん、すみません", people,
                     ["ネル"]) == []

    def test_what_the_author_keeps_stands(self):
        aim = director_prose.aim_by_their_view
        # the author keeps the binding (a call to someone unseen): the first goes on
        prose, _p, record = aim(INPUT, FIRST, [], PEOPLE, PERCEIVED,
                                lambda note: (FIRST.replace("turns back", "turns"), []),
                                perceived_here=HERE)
        assert prose == FIRST
        assert (record["kept"], record["still_named"]) == ("first", ["Mr Bryinwyr Rhiadd"])
        # a second account that re-aims but drops the quoted line never wins
        dropped = "Nell Hartley turns back to Mr Llanarfryn Eigalyn behind the bar."
        prose, _p, record = aim(INPUT, FIRST, [], PEOPLE, PERCEIVED,
                                lambda note: (dropped, []), perceived_here=HERE)
        assert (prose, record["kept"]) == (FIRST, "first")

        def down(note):
            raise RuntimeError("provider down")
        prose, _p, record = aim(INPUT, FIRST, [], PEOPLE, PERCEIVED, down,
                                perceived_here=HERE)
        assert prose == FIRST and "provider down" in record["error"]


# ---- the view itself, and the interpretation that reads it -----------------

LANDLORD = "the middle-aged square landlord with a waistcoat"


def _taproom(temp_db):
    """The 4617 shape in a dark taproom: the companion she knows by name, the
    landlord her view described, a potman it never showed -- and the beat
    before, with a line from her companion and one of hers."""
    scene = {"location": "Quarryman's Arms", "time": "night", "attire": {},
             "overlays": {}, "entities": {},
             "rooms": {"taproom": {"name": "Taproom", "adjacent": [], "light": "dark"}},
             "positions": {PLAYER: "taproom", "Mara": "taproom",
                           "Mr Llanarfryn Eigalyn": "taproom",
                           "Mr Bryinwyr Rhiadd": "taproom"}}
    ctx = _make_ctx(temp_db, scene=scene, player_input=INPUT.replace("Nell", "I"))
    mara = ctx.cast[0]["id"]
    temp_db.wset(ctx.chat.id, "known", {PLAYER: ["Mara"]})
    prev = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                      (ctx.chat.id, 0, "", time.time()))
    for key, content in (
            ("perception_outcome", {"composer_ledger": {"player": {
                "standing": [], "seen": ["Mara", "Mr Llanarfryn Eigalyn"],
                "described": [body_key("Mr Llanarfryn Eigalyn")],
                "described_as": {body_key("Mr Llanarfryn Eigalyn"): LANDLORD}}}}),
            ("director_resolve", {"dialogue_log": [
                {"speaker": "Mara", "exact_quote": "\"You'll want a room?\"",
                 "intended_target": PLAYER},
                {"speaker": PLAYER, "exact_quote": "\"I will.\"",
                 "intended_target": f"character:{mara}"},
                {"speaker": "Mara", "exact_quote": "\"Two ales.\"",
                 "intended_target": "Mr Llanarfryn Eigalyn"}]})):
        step = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                          (prev, key, "", 0))
        temp_db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                   (step, json.dumps(content), time.time()))
    return ctx, scene, mara


def test_the_view_says_whom_she_knows_and_how(temp_db):
    ctx, scene, mara = _taproom(temp_db)
    index = causal_world_index(scene, room_ids=["taproom"])
    view = director._players_view(
        ctx, scene, index, {"persona:primary": PLAYER, f"character:{mara}": "Mara"},
        [("player", PLAYER)])
    assert view["knows_as"] == {PLAYER: {"Mara": "Mara",
                                         "Mr Llanarfryn Eigalyn": LANDLORD}}
    assert view["perceived_here"] == ["Mara", "Mr Llanarfryn Eigalyn"]
    assert "mr bryinwyr rhiadd" not in view["perceived"]
    # the lines between her and anyone, by name -- never one she was not party to
    assert view["last_lines"] == [
        {"speaker": "Mara", "to": [PLAYER], "line": "\"You'll want a room?\""},
        {"speaker": PLAYER, "to": ["Mara"], "line": "\"I will.\""}]


def test_the_interpretation_reads_her_view_and_is_asked_again(temp_db, prose_director,
                                                             monkeypatch):
    ctx, _scene, _mara = _taproom(temp_db)
    first = FIRST.replace("Nell Hartley", PLAYER)
    second = SECOND.replace("Nell Hartley", PLAYER)
    calls = []

    def fake(role, step_key, system, payload, **kw):
        calls.append((step_key, payload))
        if step_key == "director_prose":
            return {"prose": second if payload.get("asked_again") else first}
        if step_key == "director_specialist":
            return {"events": [encoder_event(
                "turns back to the landlord and asks for a room", speech=True,
                targets=["Mr Llanarfryn Eigalyn"])], "missing_tools": []}
        return {}
    monkeypatch.setattr(director, "_agent_json", fake)
    out = director.director_interpret(ctx, nonce=0)
    authored = [payload for key, payload in calls if key == "director_prose"]
    assert len(authored) == 2
    assert authored[0]["player_knows_as"] == {
        PLAYER: {"Mara": "Mara", "Mr Llanarfryn Eigalyn": LANDLORD}}
    assert [line["speaker"] for line in authored[0]["last_lines"]] == ["Mara", PLAYER]
    assert "asked_again" not in authored[0]
    assert authored[1]["asked_again"] == {"named_unperceived": ["Mr Bryinwyr Rhiadd"]}
    contract = out["orchestration"]["prose_contract"]
    assert contract["prose"] == second
    assert any("was asked again" in w for w in ctx.warnings)


def test_the_card_names_the_view_it_is_given():
    for language in ("en", "ja"):
        from llm.prompts import prose_director_prompt
        sheet = prose_director_prompt("interpret", language)
        for field in ("player_knows_as", "last_lines", "asked_again"):
            assert field in sheet, (language, field)
