"""Player-declared standing contact reaches the other party in perception 1.

Chat 68 turn 15 supplied the failure: the player explicitly felt a standing
exact part-to-interior relation, interpret retained only the visible squirm,
and pass 1 reused the older coarse part-to-region record. The other participant therefore
decided before receiving the contact declaration their own body should feel.
"""

from __future__ import annotations

import json
import time

from agents.director import (
    _drop_momentary_contact_adds,
    _merge_character_contact_endings,
    _merge_player_contact_assertions,
    _validated_character_contact_endings,
    _validated_player_contact_assertions,
)
from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.prompts import DEFAULT_PROMPTS, interpret_delegation_note
from llm.schemas import validate_llm_output
from world.spatial import apply_contact_ops


def test_momentary_acts_do_not_become_standing_contact_state():
    reports = []
    ops = _drop_momentary_contact_adds([
        {"op": "add", "actor": "Alex", "actor_part": "fist",
         "target": "Kade", "target_part": "guard", "manner": "strike"},
        {"op": "add", "actor": "Alex", "actor_part": "forearm",
         "target": "Kade", "target_part": "torso", "manner": "press"},
        {"op": "remove", "actor": "Alex", "actor_part": "hand",
         "target": "Kade", "target_part": "wrist", "manner": "grip"},
    ], reports.append)

    assert [op["manner"] for op in ops] == ["press", "grip"]
    assert reports == ["discarded momentary act from standing contact topology"]


def _scene():
    return {
        "rooms": {"room": {"name": "Room", "desc": "", "adjacent": []}},
        "positions": {"Hinami": "room", "Elyra Voss": "room"},
        "entities": {},
        "contacts": [{
            "actor": "Elyra Voss", "actor_part": "cock",
            "target": "Hinami", "target_interior": "vaginal canal",
            "target_part": "groin",
            "manner": "insert", "detail": "standing interior contact",
        }],
    }


def _assertion(target_part="cervix"):
    return {
        "actor": "Elyra Voss", "actor_part": "cock",
        "target": "Hinami", "target_interior": "vaginal canal",
        "target_part": target_part,
        "manner": "insert", "detail": "head pressing firmly",
    }


def test_interpret_schema_and_prompt_carry_exact_contact_assertions():
    """The channel is still the interpret contract; the VOCABULARY now lives
    on the hand that writes it.

    The interpret sheet taught the full contact grammar for its own
    `contact_assertions`, and `interpret_delegation_note` -- appended
    unconditionally at agents/director.py:595, there being no monolithic
    Director path left -- then told the same model to leave that channel
    empty because a specialist re-encodes it. 1,890 characters of instruction
    followed by an instruction voiding them, on every beat. The grammar moved
    to the contact specialist's own sheet, which is the sheet whose output
    actually reaches `_validated_player_contact_assertions`.
    """
    parsed, warnings = validate_llm_output(
        "director_interpret", {"contact_assertions": [_assertion()]})

    assert not warnings
    assert parsed["contact_assertions"][0]["target_part"] == "cervix"
    # The interpret contract still NAMES the channel -- the specialist's
    # answer is merged into it -- and the delegation note still says who fills
    # it in.
    assert "contact_assertions" in DEFAULT_PROMPTS["director_interpret"]
    assert "contact_assertions empty" in interpret_delegation_note()

    contact = DEFAULT_PROMPTS["director_contact"]
    assert "coarse visibility region" in contact
    assert "relation is surface|interior" in contact
    assert "motion is settled|moving" in contact
    assert "target_interior names what currently encloses" in contact
    assert "op:'cross'" in contact
    # The firewall half moved with the rest and is now pinned, which it never
    # was: `detail` is free prose, so no key whitelist can hold this and the
    # sheet is the only thing standing there.
    assert ("never the other participant's thoughts, pleasure, pain, or "
            "intention") in contact

    character, warnings = validate_llm_output(
        "character", {"contact_ops": [
            {"op": "remove", "contact_ref": "contact:0"}]})
    assert not warnings
    assert character["contact_ops"][0]["contact_ref"] == "contact:0"
    assert "self.standing_contacts" in DEFAULT_PROMPTS["character"]
    assert "character_contact_endings" in DEFAULT_PROMPTS["director_contact"]


def test_character_contact_endings_remove_only_selected_contacts():
    scene = _scene()
    scene["contacts"] = [
        {"actor": "Hinami", "actor_part": "tongue", "target": "Elyra Voss",
         "target_part": "lips", "manner": "kiss", "relation": "interior",
         "target_interior": "mouth", "motion": "moving"},
        {"actor": "Elyra Voss", "actor_part": "mouth", "target": "Hinami",
         "target_part": "mouth", "manner": "kiss", "relation": "surface",
         "motion": "settled"},
        {"actor": "Elyra Voss", "actor_part": "hand", "target": "Hinami",
         "target_part": "waist", "manner": "hold", "relation": "surface",
         "motion": "settled"},
    ]
    sheet = default_character_data("Elyra Voss")

    class Ctx:
        cast = [{"id": 7, "sheet": json.dumps(sheet)}]
        character_results = {7: {"contact_ops": [
            {"op": "remove", "contact_ref": "contact:0"},
            {"op": "remove", "contact_ref": "contact:1"},
        ]}}

    endings = _validated_character_contact_endings(Ctx(), scene)
    # The stale resolve repeats both onset kisses; the actor-owned ending wins.
    resolved = [
        {"op": "add", **{k: v for k, v in contact.items()
                          if k != "unasserted"}}
        for contact in scene["contacts"][:2]
    ]
    # A symmetric rephrasing is the same stale physical relation.
    resolved[1] = {
        **resolved[1],
        "actor": scene["contacts"][1]["target"],
        "actor_part": scene["contacts"][1]["target_part"],
        "target": scene["contacts"][1]["actor"],
        "target_part": scene["contacts"][1]["actor_part"],
    }
    merged = _merge_character_contact_endings(endings, resolved)
    after = apply_contact_ops(json.loads(json.dumps(scene)), merged, _age=False)

    assert [(c["actor_part"], c["target_part"]) for c in after["contacts"]] == [
        ("hand", "waist")]


def test_character_contact_refs_cannot_remove_someone_elses_contact():
    scene = _scene()
    scene["contacts"] = [{
        "actor": "Hinami", "actor_part": "hand", "target": "A Door",
        "target_part": "handle", "manner": "hold",
    }]
    sheet = default_character_data("Elyra Voss")

    class Ctx:
        cast = [{"id": 7, "sheet": json.dumps(sheet)}]
        character_results = {7: {"contact_ops": [
            {"op": "remove", "contact_ref": "contact:0"}]}}

    assert _validated_character_contact_endings(Ctx(), scene) == []


def test_felt_contact_can_refine_standing_relation_but_not_mint_npc_act():
    scene = _scene()

    kept = _validated_player_contact_assertions(
        scene, [_assertion()], "Hinami")
    rejected = _validated_player_contact_assertions(scene, [{
        "actor": "Elyra Voss", "actor_part": "hand",
        "target": "Hinami", "target_part": "throat", "manner": "grip",
    }], "Hinami")

    assert kept[0]["target_part"] == "cervix"
    assert kept[0]["relation"] == "interior"
    assert kept[0]["motion"] == "settled"
    assert rejected == []

    subpart = _validated_player_contact_assertions(scene, [{
        **_assertion(), "actor_part": "head",
    }], "Hinami")
    assert subpart[0]["actor_part"] == "cock"


def test_contestable_player_act_cannot_mint_contact_before_reaction():
    scene = _scene()
    scene["positions"] = {"Mara": "room", "Rhea": "room"}
    attempted = {
        "actor": "Mara", "actor_part": "hand",
        "target": "Rhea", "target_part": "shoulder",
        "manner": "grip", "relation": "surface", "motion": "settled",
    }

    assert _validated_player_contact_assertions(
        scene, [attempted], "Mara",
        allow_new_player_contacts=False) == []
    assert _validated_player_contact_assertions(
        scene, [attempted], "Mara",
        allow_new_player_contacts=True)[0]["target_part"] == "shoulder"


def test_npc_refinement_cannot_drop_standing_endpoint():
    scene = _scene()
    scene["positions"] = {"Mara": "room", "Rhea": "room"}
    scene["contacts"] = [{
        "actor": "Rhea", "actor_part": "forearm",
        "target": "Mara", "target_part": "right shoulder",
        "manner": "press", "relation": "surface", "motion": "settled",
    }]

    [refined] = _validated_player_contact_assertions(scene, [{
        "actor": "Rhea", "actor_part": "forearm",
        "target": "Mara", "target_part": "",
        "manner": "press", "relation": "surface", "motion": "settled",
    }], "Mara")

    assert refined["target_part"] == "right shoulder"


def test_resolve_cannot_silently_coarsen_asserted_contact_endpoint():
    assertion = {"op": "add", **_assertion()}
    coarse = {"op": "add", **_assertion("groin")}

    merged = _merge_player_contact_assertions([assertion], [coarse])
    assert [op["target_part"] for op in merged if op.get("op") == "add"] == [
        "cervix"]

    # A real later transition is expressible, but it must end the asserted
    # relation explicitly rather than overwriting its endpoint by re-description.
    moved = _merge_player_contact_assertions([assertion], [
        {"op": "remove", "actor": "Elyra Voss", "actor_part": "cock",
         "target": "Hinami", "target_part": "cervix"},
        coarse,
    ])
    assert moved[-1]["target_part"] == "groin"


def test_explicit_crossing_can_advance_a_player_declared_endpoint():
    assertion = {"op": "add", **_assertion()}
    crossing = {
        "op": "cross", "actor": "Elyra Voss", "actor_part": "cock",
        "target": "Hinami", "crossed_target_part": "cervix",
        "target_interior": "downstream chamber", "target_part": "far wall",
        "manner": "push", "relation": "interior", "motion": "moving",
    }

    validated = _validated_player_contact_assertions(
        {**_scene(), "contacts": [assertion]}, [crossing], "Hinami")
    merged = _merge_player_contact_assertions([assertion], validated)

    assert validated[0]["op"] == "cross"
    assert validated[0]["crossed_target_part"] == "cervix"
    assert merged[-1]["op"] == "cross"


def test_crossing_cannot_bypass_a_different_declared_endpoint():
    invalid = {
        "op": "cross", **_assertion("far wall"),
        "crossed_target_part": "groin",
        "target_interior": "downstream chamber",
    }

    assert _validated_player_contact_assertions(
        {**_scene(), "contacts": [{"op": "add", **_assertion()}]},
        [invalid], "Hinami") == []


def _ctx(temp_db):
    persona = default_persona_data("Hinami")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Contact onset", "", time.time(), persona_id))
    sheet = default_character_data("Elyra Voss")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Elyra Voss", json.dumps(sheet), "{}", time.time(), "char_elyra"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", _scene())
    temp_db.wset(chat_id, "known", {
        "Elyra Voss": ["Hinami"], "Hinami": ["Elyra Voss"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "I feel the exact contact.", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Contact onset", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="I feel the exact contact.",
                      created=time.time()),
        cast=cast, input="I feel the exact contact.")
    ctx["_player_room"] = "room"
    ctx.director_interpret = {
        "sequence": [{
            "type": "action", "attempt": "reacts to the exact contact",
            "observable": "body tenses", "visibility": "overt",
            "targets": [], "commitment": "asserted",
        }],
        "action": {"attempt": "reacts to the exact contact"},
        "contact_assertions": [{"op": "add", **_assertion()}],
        "flow": {"reactors": [char_id], "resolution_flags": {}},
    }
    return ctx, char_id


def test_other_participant_feels_exact_contact_in_perception_pass_one(
        temp_db, monkeypatch):
    import agents.perception as perception

    ctx, char_id = _ctx(temp_db)
    view = perception.perception_act(ctx, nonce=0)["views"][str(char_id)]

    # The contact record used to be read out of the payload; the sensation
    # it produces is now in the view itself, which is the thing that had to
    # be right all along.
    assert "your cock registers hinami's vaginal canal enclosing it" in view.casefold()
    assert "contact at hinami's cervix" in view.casefold()
    assert "hinami's groin" not in view.casefold()
