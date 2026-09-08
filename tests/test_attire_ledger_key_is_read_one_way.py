"""Every reader of one body's wardrobe asks the ledger the same way.

Review 2026-09-07 B5: `story.scene.appearance_of` did a bare
`(scene["attire"]).get(name)` eleven lines below `visible_body_text`, which
went through `attire.entry_for`. The attire ledger's key is NOT reliably
canonical -- `persist.commit_attire._heal_attire_identity_keys` exists to
repair it, and nothing heals on the read path -- so on a body keyed under a
case variant the two neighbours answered differently about one person: one
found the garments, the other reported an undressed body to every observer.

The rule: one body's attire entry is read through `attire.entry_for`, and
whether the wardrobe knows a body at all is asked through `attire.key_for`.
These tests key the ledger under a lowercase spelling and ask each reader
about the display spelling; before the fix, each assertion failed on the
reader it names. Each test calls the SITE the fix changed -- an assertion
that `module.attire_entry_for is attire.entry_for` passes with the bare
`.get` still standing at the call, so there are none of those here.
"""
import copy
import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story import attire as attire_model
from story.character_schema import default_character_data

DRESSED = {
    "wearing": ["wool coat"],
    "state": [],
    "regions": {
        "torso": {"garments": [{"name": "wool coat", "state": "worn"}]},
    },
}


def _scene():
    """A scene whose wardrobe is keyed 'hinami' for a body named 'Hinami'."""
    return {
        "attire": {"hinami": copy.deepcopy(DRESSED)},
        "positions": {"Hinami": "room_a"},
        "rooms": {"room_a": {"name": "Room A"}},
        "entities": {},
    }


def test_entry_for_and_key_for_share_one_key_rule():
    ledger = {"hinami": copy.deepcopy(DRESSED)}
    assert attire_model.key_for(ledger, "Hinami") == "hinami"
    assert attire_model.key_for(ledger, " HINAMI ") == "hinami"
    assert attire_model.key_for(ledger, "someone else") is None
    assert attire_model.entry_for(ledger, "Hinami")["wearing"] == ["wool coat"]
    assert attire_model.entry_for(ledger, "someone else") == {}
    # An exact key wins over the fold, and a non-dict entry is still {}.
    assert attire_model.key_for({"a": 1, "A": 2}, "A") == "A"
    assert attire_model.entry_for({"a": "nonsense"}, "A") == {}
    # `key_for` distinguishes a present-but-empty entry from an absent one,
    # which is the distinction `agents.common`'s two `is None` tests turn on.
    assert attire_model.key_for({"hinami": {}}, "Hinami") == "hinami"


def test_appearance_of_agrees_with_visible_body_text():
    """B5's own site: the two neighbours in story/scene.py."""
    from story.scene import appearance_of, visible_body_text

    sc = _scene()
    said = appearance_of("Hinami", "tall", sc)
    assert "wool coat" in said, said
    # The gate beside it already read the ledger correctly; the point is that
    # both now do, so one wardrobe cannot describe one body two ways.
    body = {"build": "tall", "regions": {"torso": {"bare": "a long scar"}}}
    assert "long scar" not in visible_body_text(body, "Hinami", sc)


def test_exposure_screen_still_sees_the_covered_region():
    from agents.common import attire_exposure_facts

    facts = attire_exposure_facts(_scene(), [("Hinami", ["her"])])
    assert facts and "torso" in facts[0]["covered"], facts


def test_region_visibility_finds_the_garment():
    from agents.common import region_visibility

    sc = _scene()
    sc["positions"]["Watcher"] = "room_a"
    verdict = region_visibility(sc, "Watcher", "Hinami")["torso"]
    assert verdict["visibility"] == "concealed", verdict
    assert "wool coat" in (verdict.get("by") or {}).get("garments", []), verdict


def test_observer_body_row_reports_the_garment_surface():
    from agents.common import observer_body_regions

    sc = _scene()
    sc["positions"]["Watcher"] = "room_a"
    rows = observer_body_regions(sc, "Watcher", {"Hinami": "Hinami"})
    row = next((r for r in rows if r["body"] == "Hinami"), None)
    assert row and "torso" in row["regions"], rows
    assert "wool coat" in repr(row["regions"]["torso"]), row


def test_perception_notices_the_change_of_clothes():
    from agents import perception

    before = _scene()
    after = _scene()
    after["attire"]["hinami"] = {"wearing": [], "state": [], "regions": {}}
    assert perception._attire_items(before, "Hinami") == {"wool coat"}
    assert perception._attire_items(after, "Hinami") == set()


def test_the_wardrobe_knowing_a_body_makes_it_a_body():
    from world.spatial import _moved_subject_is_body

    sc = _scene()
    # An entity row with no `kind` is what leaves this decidable by the
    # wardrobe alone; under a case-variant key it read as a thing.
    sc["entities"]["Hinami"] = {"name": "Hinami"}
    assert _moved_subject_is_body(sc, "Hinami") is True


def test_worn_garment_names_read_one_body_through_the_ledger():
    """Consolidation, not a repair: this site read the wardrobe through the
    shared spatial `_ci_get` and was ALREADY case-tolerant, so the assertion
    holds on either side of the change. What changed is that the wardrobe's
    key rule is asked of the wardrobe's own reader, so a later change to it
    cannot leave this caller behind."""
    from world.spatial import _worn_garment_names

    # Both representations are read on purpose (`wearing` and the regions),
    # so the coat is named twice -- what matters is that it is named at all.
    assert "wool coat" in _worn_garment_names(_scene(), "Hinami")


def test_the_lint_tool_does_not_accuse_a_case_variant_wardrobe():
    """`tools/scene_lint.py`'s `_worn_names`: its caller passes the
    Director's `worn_by` spelling, the same twin as the commit seam's fold,
    so a bare `.get` made the one diagnostic aimed at this class report a
    false "entity says worn, wardrobe disagrees"."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    from scene_lint import check_scene

    sc = _scene()
    sc["entities"] = {"hinami_coat": {
        "name": "wool coat", "kind": "object",
        "state": {"clothing": True, "worn_by": "Hinami"}}}
    assert not [p for p in check_scene(sc)
                if "wardrobe disagrees" in p[0]], check_scene(sc)


# ---------------------------------------------------------------------------
# The readers that need a story behind them.
# ---------------------------------------------------------------------------

def _chat_with_scene(temp_db, scene, name="Wardrobe"):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     (name, "", time.time()))
    temp_db.wset(cid, "scene", scene)
    return cid


def test_the_room_panel_lists_the_occupants_garments(temp_db):
    """`story.room_slice.room_slices`: the occupant's name comes off
    `positions`, whose spelling need not be the wardrobe's. A bare `.get`
    blanked the attire column for a dressed body."""
    from story.room_slice import room_slices

    scene = _scene()
    cid = _chat_with_scene(temp_db, scene)
    row, = room_slices(cid, None, ["room_a"], scene)
    occupant, = row["occupants"]
    assert occupant["name"] == "Hinami"
    assert (occupant["attire"] or {}).get("wearing") == ["wool coat"], occupant


def test_the_bodies_tab_lists_the_bodys_garments(temp_db):
    """`web.world_routes.body_rows`: `names` is built from positions as well
    as from the wardrobe, so the spelling in hand need not be the ledger's."""
    from web.world_routes import body_rows

    scene = _scene()
    cid = _chat_with_scene(temp_db, scene)
    rows = body_rows(cid, {"persona_id": None}, scene)
    row = next(r for r in rows if r["name"] == "Hinami")
    assert (row["attire"] or {}).get("wearing") == ["wool coat"], row


def test_the_character_payload_tells_a_body_its_own_clothes(
        temp_db, monkeypatch):
    """`agents.character.character_step`: a case-variant ledger key told a
    dressed body it was wearing nothing, which is a self-knowledge failure
    rather than a missing observation."""
    import agents.character as character_module

    sheet = default_character_data("Hinami")
    scene = _scene()
    scene["location"] = "Room A"
    cid = _chat_with_scene(temp_db, scene)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Hinami", json.dumps(sheet), "{}", time.time(), "char_hinami"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "what are you wearing?", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Wardrobe", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1,
                      player_input="what are you wearing?",
                      created=time.time()),
        cast=cast, input="what are you wearing?")
    ctx.director_interpret = {"flow": {"reactors": [char_id],
                                       "tom_triggers": []}}
    captured = {}

    def _fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", _fake_agent_json)
    character_module.character_step(ctx, char_id, nonce=0)
    assert "wool coat" in captured["payload"]["self"]["attire"], \
        captured["payload"]["self"]["attire"]


def test_the_narrator_payload_carries_the_players_own_ledger(
        temp_db, monkeypatch):
    """`agents.narration.narrator`: a case-variant key silently dropped
    `player_attire`, which is the absence that block exists to fix."""
    import agents.narration as narration

    player = "The Stranger"
    scene = {"attire": {player.casefold(): copy.deepcopy(DRESSED)},
             "positions": {player: "room_a"},
             "rooms": {"room_a": {"name": "Room A", "notes": "a room"}},
             "entities": {}}
    cid = _chat_with_scene(temp_db, scene)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Wardrobe", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=3, player_input="hi",
                      created=time.time()),
        cast=[], input="I look down at myself.")
    ctx._extra["outcome_scene"] = scene
    ctx["_player_room"] = "room_a"
    ctx["director_interpret"] = {"sequence": [], "speech": None}
    ctx["perception_outcome"] = {"views": {"player": "The room is quiet."}}
    captured = {}

    def _fake_agent_json(step_key, model_key, prompt, payload, **kw):
        captured["payload"] = payload
        return {"prose": "You look down.", "new_specifics": []}

    monkeypatch.setattr(narration, "_agent_json", _fake_agent_json)
    monkeypatch.setattr(narration, "validate_llm_output",
                        lambda key, out: (out, []))
    narration.narrator(ctx, 0)
    assert "wool coat" in captured["payload"].get("player_attire", ""), \
        captured["payload"].get("player_attire")


def test_a_worn_garment_entity_folds_into_a_case_variant_wardrobe():
    """`persist.commit._fold_worn_garment_entities`: `worn_by` is the
    Director's spelling of the wearer, which the ledger's key need not
    match, so the duplicate record stood beside the wardrobe that had it."""
    from persist import commit

    class _Ctx:
        def __init__(self):
            self.told, self.warned = [], []

        def tell_director(self, msg):
            self.told.append(msg)

        def add_warning(self, msg):
            self.warned.append(msg)

    sc = _scene()
    sc["entities"] = {"hinami_coat": {
        "name": "wool coat", "kind": "object",
        "state": {"clothing": True, "worn_by": "Hinami",
                  "condition": "damp"}}}
    sc["positions"]["hinami_coat"] = "room_a"
    diff = {"entities": dict(sc["entities"])}
    ctx = _Ctx()
    commit._fold_worn_garment_entities(sc, diff, ctx)
    assert sc["entities"] == {} and diff["entities"] == {}
    assert "hinami_coat" not in sc["positions"]
    garment, = sc["attire"]["hinami"]["regions"]["torso"]["garments"]
    assert garment["condition"] == "damp"
    assert ctx.told and "attire ledger owns it" in ctx.told[0]


def test_a_reclaimed_garment_is_respelled_in_a_case_variant_wardrobe():
    """`persist.commit._reclaim_worn_shed_garments`: the shed object's own
    spelling goes back on the body, and the rename reaches the entry only if
    the wardrobe is asked the way everything else asks."""
    from persist import commit

    sc = _scene()
    sc["attire"]["hinami"] = {
        "wearing": ["black half-mask"], "state": [],
        "regions": {"head": {"garments": [
            {"name": "black half-mask", "state": "worn"}]}}}
    sc["entities"] = {"shed_mask": {
        "name": "a plain black half-mask of moulded leather", "kind": "object",
        "state": {"clothing": True, "shed": True, "worn_by": "Hinami",
                  "garment": "a plain black half-mask of moulded leather"}}}
    sc["positions"]["shed_mask"] = "room_a"
    diff = {"entities": dict(sc["entities"])}
    reclaimed = commit._reclaim_worn_shed_garments(
        sc, diff, None, {"Hinami": ["black half-mask"]})
    assert [r[0] for r in reclaimed] == ["shed_mask"]
    entry = sc["attire"]["hinami"]
    assert entry["wearing"] == \
        ["a plain black half-mask of moulded leather"], entry
    assert entry["regions"]["head"]["garments"][0]["name"] == \
        "a plain black half-mask of moulded leather", entry
