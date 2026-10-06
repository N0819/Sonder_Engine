"""A body the view never showed is never described (formerly UNBUILT_PIPELINE §1.176).

The narrator's labels and a character's frame read what the observer's own
view called a body -- but that record holds the bodies the view SHOWED, and
a body that reached a mind by another channel fell back to the identity
floor, which minted an appearance descriptor for a stranger whether or not
anybody had ever seen them, and recognised a disguised acquaintance by name
through a disguise that hides who she is. Reproduced end to end by the
review of the re-applied leak fixes (2026-10-05), each a present-tense field
beside a view that said otherwise:

  * a stranger's hand on a shoulder in a dark cellar: the view "the
    unfamiliar person's hand", the narrator's touch line and the character's
    own contact list "the tall fox-eared woman's hand";
  * the same hand, the woman an acquaintance in a disguise that hides who
    she is: her real name;
  * a focus on a stranger nobody can see: the frame "the tall fox-eared
    woman";
  * a player whose card says sight is absent: a body in a lit hall placed in
    the narrator's company.

The rule: what a present-tense field calls a body is what the view would --
its name only if this observer knows it and no disguise hides it, an
appearance only if the body is seen now or this observer's view once
described it (`described`, the per-observer first-mention ledger), and
otherwise the unfamiliar person.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData

PLAYER = "Pip"
FOX = "A tall fox-eared woman in a green coat."


def _beat(temp_db, monkeypatch, scene, *, known=None, persona_senses=None,
          disguise=None, described_before=(), described_as=None, chars=None,
          parts=None, persona_parts=None):
    """Perception and the narrator for one quiet beat; returns
    `(perception_outcome, narrator_payload, ctx, ids)`."""
    import agents.narration as narration
    import agents.perception as perception
    from story.character_schema import default_character_data, default_persona_data
    from agents.composer import body_key

    persona = default_persona_data(PLAYER)
    if persona_senses is not None:
        persona["embodiment"]["senses"] = list(persona_senses)
    if persona_parts is not None:
        persona["embodiment"]["extra_parts"] = list(persona_parts)
    persona_id = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                            (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Unseen", "", time.time(), persona_id))
    ids = {}
    for name, appearance in (chars or {"Alice": FOX}).items():
        sheet = default_character_data(name)
        sheet["embodiment"]["visible"]["summary"] = appearance
        if parts and name in parts:
            sheet["embodiment"]["extra_parts"] = parts[name]
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), f"unseen_{name}_{time.time()}"))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
                   (chat_id, cid, "active", "{}"))
        ids[name] = cid
    scene = dict(scene, location="x", time="day", attire={}, overlays={}, entities={})
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "known", known or {})
    if disguise:
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,started_at,payload,active) "
            "VALUES(?,?,?,?,?,?,1)",
            ("d_" + disguise["subject"], chat_id, disguise["subject"], "physical_disguise",
             time.time(), json.dumps({"subject_id": disguise["subject"], "state": disguise["state"]})))
    if described_before:
        # The previous beat's view described these bodies to the player.
        prev = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                          (chat_id, 0, "", time.time()))
        step = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                          (prev, "perception_outcome", "", 0))
        temp_db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                   (step, json.dumps({"composer_ledger": {"player": {
                       "standing": [], "described": [body_key(n) for n in described_before],
                       **({"described_as": {body_key(n): label for n, label in described_as.items()}}
                          if described_as else {})}}}),
                    time.time()))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                         (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Unseen", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = scene["positions"].get(PLAYER)
    ctx.director_interpret = {
        "action": {"attempt": "waits", "visibility": "overt", "conceal_from": [],
                   "targets": [], "commitment": "asserted"},
        "sequence": [{"type": "action", "attempt": "waits", "observable": "waits",
                      "visibility": "overt", "conceal_from": [], "targets": [],
                      "commitment": "asserted", "verb": "wait", "stage": "immediate",
                      "event_id": "turn:1:player:0:action"}],
        "speech": None, "speech_volume": "normal", "flow": {"reactors": []}}
    ctx.director_resolve = {"resolved_event": "Nothing much happens.", "state_diff": {},
                            "dialogue_log": [], "dialogue_order": []}
    out = perception.perception_outcome(ctx, nonce="n")
    ctx.perception_outcome = out
    ctx._extra["outcome_scene"] = ctx.get("outcome_scene") or scene
    captured = {}

    def _fake_agent_json(step_key, model_key, prompt, payload, **kw):
        captured["payload"] = payload
        return {"prose": "Time passes.", "new_specifics": []}

    monkeypatch.setattr(narration, "_agent_json", _fake_agent_json)
    monkeypatch.setattr(narration, "validate_llm_output", lambda key, o: (o, []))
    narration.narrator(ctx, 0)
    return out, captured["payload"], ctx, ids


def _touch(payload):
    touch = ((payload.get("sensory_channels") or {}).get("touch") or {})
    return " ".join(str(e.get("clause") or "") for e in touch.get("standing") or [])


def _dark_hand(on=PLAYER):
    return {"rooms": {"cellar": {"name": "the cellar", "desc": "A cellar.", "light": "dark"}},
            "positions": {PLAYER: "cellar", "Alice": "cellar"}, "stations": {},
            "contacts": [{"actor": "Alice", "target": on, "actor_part": "hand",
                          "target_part": "shoulder", "relation": "on", "motion": "still"}]}


def test_a_strangers_hand_in_the_dark_is_the_unfamiliar_persons_in_every_field(temp_db, monkeypatch):
    out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, _dark_hand())
    assert "the unfamiliar person's hand" in out["views"]["player"]
    touch = _touch(payload)
    assert touch and "fox" not in touch.lower()
    assert "unfamiliar person" in touch


def test_a_disguised_acquaintance_in_the_dark_is_not_named(temp_db, monkeypatch):
    disguise = {"subject": "Alice", "state": {
        "presented_appearance": "A hooded pilgrim in a grey cloak.", "known_to": ["Alice"],
        "conceals_identity": True, "concealed_terms": ["fox-eared", "fox ears"]}}
    out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, _dark_hand(),
                                     known={PLAYER: ["Alice"]}, disguise=disguise)
    assert "Alice" not in out["views"]["player"]
    touch = _touch(payload)
    assert touch and "Alice" not in touch and "fox" not in touch.lower()


def test_a_stranger_seen_in_full_before_keeps_their_description_in_the_dark(temp_db, monkeypatch):
    """A descriptor learned at a sighting is knowledge the mind keeps: the
    rule is about a body NEVER seen, not one out of sight now."""
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, _dark_hand(),
                                      described_before=("Alice",))
    assert "fox-eared" in _touch(payload)


def test_a_focus_on_a_stranger_nobody_can_see_is_not_described(temp_db, monkeypatch):
    scene = {"rooms": {"cellar": {"name": "the cellar", "desc": "A cellar.", "light": "dark"}},
             "positions": {PLAYER: "cellar", "Alice": "cellar"}, "stations": {},
             "orientation": {PLAYER: {"focus": {"kind": "entity", "ref": "Alice"}}}}
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, scene)
    frame = json.dumps(payload.get("spatial_frame") or {})
    assert "fox" not in frame.lower()


def test_a_blind_player_is_given_no_body_by_sight(temp_db, monkeypatch):
    scene = {"rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": "lit"}},
             "positions": {PLAYER: "hall", "Alice": "hall"}, "stations": {}}
    blind = [{"channel": "vision", "acuity": "absent", "range": "ordinary",
              "needs_light": True, "equivalent": "", "notes": ""}]
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, scene, persona_senses=blind)
    company = json.dumps(payload.get("co_present_positions") or {})
    assert "fox" not in company.lower()


def test_a_characters_own_contact_list_names_an_unseen_stranger_as_its_view_does(temp_db, monkeypatch):
    import agents.character as character_module
    scene = _dark_hand(on="Bob")
    scene["positions"]["Bob"] = "cellar"
    _out, _payload, ctx, ids = _beat(temp_db, monkeypatch, scene,
                                     chars={"Alice": FOX, "Bob": "A stocky man."})
    ctx.perception_act = ctx.perception_outcome
    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, ids["Bob"], nonce=0)
    contacts = json.dumps(((captured["payload"].get("self") or {}).get("standing_contacts")) or [])
    assert "hand" in contacts and "fox" not in contacts.lower()


PILGRIM = {"subject": "Alice", "state": {
    "presented_appearance": "A hooded pilgrim in a grey cloak.", "known_to": ["Alice"],
    "conceals_identity": True, "concealed_terms": ["fox-eared", "fox ears"]}}


def test_in_the_dark_a_stranger_is_the_form_this_mind_learned(temp_db, monkeypatch):
    """Review round 2 (2026-10-05): the ledger said WHICH body was described,
    not as what -- in the dark, a disguise donned since the sighting was
    named though never seen. The touch line keeps the form learned."""
    _out, payload, _ctx, _ids = _beat(
        temp_db, monkeypatch, _dark_hand(), disguise=PILGRIM,
        described_before=("Alice",), described_as={"Alice": "the tall fox-eared woman"})
    touch = _touch(payload)
    assert "fox-eared" in touch and "pilgrim" not in touch


def test_in_the_dark_a_disguise_dropped_since_leaves_only_the_disguise_known(temp_db, monkeypatch):
    """The other half: seen only as the pilgrim, her own face never reaches
    the page when the disguise ends in the dark."""
    _out, payload, _ctx, _ids = _beat(
        temp_db, monkeypatch, _dark_hand(),
        described_before=("Alice",), described_as={"Alice": "the hooded pilgrim"})
    touch = _touch(payload)
    assert "pilgrim" in touch and "fox" not in touch.lower()


def test_a_hidden_acquaintance_in_the_dim_is_a_figure_not_a_name(temp_db, monkeypatch):
    """Review round 2 (2026-10-05): short of full sight the rule returned the
    floor's answer, which for an acquaintance is her NAME -- through a
    disguise that hides who she is. And the pronoun roster keyed her by it."""
    import agents.perception as perception
    scene = {"rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": "dim"}},
             "positions": {PLAYER: "hall", "Alice": "hall"}, "stations": {}}
    _out, payload, ctx, _ids = _beat(temp_db, monkeypatch, scene,
                                     known={PLAYER: ["Alice"]}, disguise=PILGRIM)
    label = perception.present_label_fn(ctx, "player", PLAYER, ctx.get("outcome_scene") or scene)
    assert label("Alice") != "Alice"
    assert "Alice" not in json.dumps(payload.get("cast_pronouns") or {})


def _hall(light, contact=False):
    sc = {"rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": light,
                             "size": "medium",
                             "anchors": {"door": {"desc": "the door", "dir": "n"},
                                         "hearth": {"desc": "the hearth", "dir": "s"}},
                             "adjacent": []}},
          "positions": {PLAYER: "hall", "Alice": "hall"},
          "stations": {PLAYER: {"at": "door"}, "Alice": {"at": "hearth"}},
          "orientation": {PLAYER: {"facing": "n"}}, "poses": {}}
    if contact:
        sc["stations"]["Alice"] = {"at": "door"}
        sc["contacts"] = [{"actor": "Alice", "target": PLAYER, "actor_part": "hand",
                           "target_part": "shoulder", "relation": "on", "motion": "still"}]
    return sc


def test_a_body_behind_the_observer_is_not_learned_and_is_nobody_in_the_dark(temp_db, monkeypatch):
    """Review round 3 (2026-10-05): the learned form was read off the whole
    display map, which grades sight without the facing cone -- a stranger
    behind the player in a lit hall, whom the view never showed, was learned,
    and in the dark her hand was "the tall fox-eared woman's hand"."""
    import agents.perception as perception
    from agents.composer import body_key
    out1, _payload1, ctx1, _ids = _beat(temp_db, monkeypatch, _hall("lit"))
    ledger = out1["composer_ledger"]["player"]
    assert body_key("Alice") not in (ledger.get("described_as") or {})
    step = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                      (ctx1.turn.id, "perception_outcome", "", 0))
    temp_db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
               (step, json.dumps(out1), time.time()))
    dark = dict(_hall("dark", contact=True), location="x", time="day", attire={},
                overlays={}, entities={})
    temp_db.wset(ctx1.chat.id, "scene", dark)
    turn2 = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                       (ctx1.chat.id, 2, "", time.time()))
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    ctx2 = PipelineContext(chat=ctx1.chat, cast=ctx1.cast, input="",
                           turn=TurnData(id=turn2, chat_id=ctx1.chat.id, idx=2,
                                         player_input="", created=time.time()))
    ctx2["_player_room"] = "hall"
    ctx2.director_interpret = ctx1.director_interpret
    ctx2.director_resolve = ctx1.director_resolve
    ctx2.perception_outcome = perception.perception_outcome(ctx2, nonce="n")
    label = perception.present_label_fn(ctx2, "player", PLAYER, dark)
    assert "fox" not in label("Alice").lower()


def test_a_seat_the_observer_does_not_know_is_not_named(temp_db, monkeypatch):
    """Review round 3 (2026-10-05): "known" was read off the floor handing a
    name back unchanged -- which it does for a co-player's seat it has no
    card for -- so a stranger's real name reached the page."""
    import agents.perception as perception
    scene = {"rooms": {"cellar": {"name": "the cellar", "desc": "A cellar.", "light": "dark"}},
             "positions": {PLAYER: "cellar", "Alice": "cellar", "Quill": "cellar"},
             "stations": {}}
    _out, _payload, ctx, _ids = _beat(temp_db, monkeypatch, scene)
    ctx.extra_players = [{"persona_id": 99, "name": "Quill", "appearance": "A wiry man.",
                          "persona": {"identity": {"name": "Quill", "aliases": []}}}]
    label = perception.present_label_fn(ctx, "player", PLAYER, ctx.get("outcome_scene") or scene)
    assert label("Quill") != "Quill"


def test_a_question_owed_names_its_asker_as_the_view_did_then():
    """Review rounds 2-3 (2026-10-05): the note reports a line delivered
    beats ago, and its asker is who the view said spoke it on that beat --
    not a disguise donned since, not the floor's real name or real look."""
    from agents.character import _heard_as, _labelled_debt
    rows = [{"idx": 3, "step_key": "perception_outcome", "content": json.dumps({
        "observations": {"7": [{"kind": "speech", "actor": "the hooded pilgrim",
                                "observed": {"text": 'The hooded pilgrim says: "Where is the key?"'}}]}})}]
    assert _heard_as(rows, 7, 3, "Where is the key?") == "the hooded pilgrim"
    debt = {"awaiting_your_answer": {"from": "Alice", "asked": "Where is the key?",
                                     "turns_ago": 1, "heard_as": "the hooded pilgrim"}}
    out = _labelled_debt(debt, lambda name: name)["awaiting_your_answer"]
    assert out["from"] == "the hooded pilgrim" and "heard_as" not in out


NINE_TAILS = {"Alice": [{"kind": "tail", "count": 9, "at": "waist"}]}
LIT_HALL = {"rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": "lit"}},
            "positions": {PLAYER: "hall", "Alice": "hall"}, "stations": {}}


def test_a_strangers_authored_parts_reach_the_page_only_when_seen(temp_db, monkeypatch):
    """Review round 4 (2026-10-05): `authored_body_parts` named every cast
    member with parts by real name -- a stranger in a dark cellar went to
    the page with her nine tails. Now a stranger's parts come only with a
    body shown in full, under the view's own label for her."""
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, _dark_hand(), parts=NINE_TAILS)
    dark = json.dumps(payload.get("authored_body_parts") or {})
    assert "Alice" not in dark and "tail" not in dark
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, LIT_HALL, parts=NINE_TAILS)
    lit = payload.get("authored_body_parts") or {}
    assert "Alice" not in lit
    assert any("tail" in " ".join(lines) for lines in lit.values())


def test_a_known_bodys_parts_stay_under_her_name(temp_db, monkeypatch):
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, LIT_HALL, parts=NINE_TAILS,
                                      known={PLAYER: ["Alice"]})
    assert "tail" in " ".join((payload.get("authored_body_parts") or {}).get("Alice") or [])


def test_a_known_body_in_no_room_keeps_its_name_behind_its_disguise(temp_db, monkeypatch):
    """Review round 4 (2026-10-05): a disguise hides a known body wherever
    it can be perceived and nowhere else. In no room of the scene she can be
    neither seen, heard nor felt, so she keeps her name; in the next room a
    voice through the door is still a stranger's (the verifiers' case)."""
    import agents.perception as perception
    nowhere = {"rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": "lit"}},
               "positions": {PLAYER: "hall"}, "stations": {}}
    _out, _payload, ctx, _ids = _beat(temp_db, monkeypatch, nowhere,
                                      known={PLAYER: ["Alice"]}, disguise=PILGRIM)
    scene = dict(nowhere, location="x", time="day", attire={}, overlays={}, entities={})
    assert perception.present_label_fn(ctx, "player", PLAYER, scene)("Alice") == "Alice"
    next_door = {"rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": "lit",
                                    "adjacent": [{"to": "study", "barrier": "closed_door"}]},
                           "study": {"name": "the study", "desc": "A study.", "light": "lit",
                                     "adjacent": [{"to": "hall", "barrier": "closed_door"}]}},
                 "positions": {PLAYER: "hall", "Alice": "study"}, "stations": {}}
    _out, _payload, ctx, _ids = _beat(temp_db, monkeypatch, next_door,
                                      known={PLAYER: ["Alice"]}, disguise=PILGRIM)
    scene = dict(next_door, location="x", time="day", attire={}, overlays={}, entities={})
    assert perception.present_label_fn(ctx, "player", PLAYER, scene)("Alice") != "Alice"


def test_a_characters_contact_reads_the_label_its_own_view_gave(temp_db, monkeypatch):
    """Review round 4 (2026-10-05): a character's fields named a body by the
    present-tense rule even where its own view had composed a line about
    it -- two look-alike strangers both "the tall fox-eared woman" though
    the view told them apart. The view's own label comes first."""
    import agents.character as character_module
    scene = {"rooms": {"hall": {"name": "the hall", "desc": "A hall.", "light": "lit"}},
             "positions": {PLAYER: "hall", "Alice": "hall", "Cara": "hall", "Bob": "hall"},
             "stations": {},
             "contacts": [{"actor": "Alice", "target": "Bob", "actor_part": "hand",
                           "target_part": "shoulder", "relation": "on", "motion": "still"}]}
    _out, _payload, ctx, ids = _beat(
        temp_db, monkeypatch, scene,
        chars={"Alice": "A tall fox-eared woman in a red coat.",
               "Cara": "A tall fox-eared woman in a green coat.", "Bob": "A stocky man."})
    ctx.perception_act = ctx.perception_outcome
    shown = {r["name"]: r["label"] for r in
             (ctx.perception_act.get("company") or {}).get(str(ids["Bob"])) or []}
    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, ids["Bob"], nonce=0)
    contacts = json.dumps(((captured["payload"].get("self") or {}).get("standing_contacts")) or [])
    assert shown.get("Alice") and shown["Alice"] in contacts



def test_a_body_in_the_blind_spot_is_not_described(temp_db, monkeypatch):
    """Review round 4 (2026-10-05): a body behind the observer gives no new
    visual detail (`entity_arc`), so the present-tense rule describes it as
    nobody it has learned -- the stealth approach handed a character the
    look of the player at its back."""
    import agents.perception as perception
    _out, _payload, ctx, _ids = _beat(temp_db, monkeypatch, _hall("lit"))
    scene = dict(_hall("lit"), location="x", time="day", attire={}, overlays={}, entities={})
    label = perception.present_label_fn(ctx, "player", PLAYER, scene)("Alice")
    assert "fox" not in label.lower()


def test_the_silence_note_never_places_a_player_in_the_blind_spot(monkeypatch):
    import agents.character as character
    from agents.character import _player_silence_note
    from story.character_schema import default_character_data
    scene = {"rooms": {"hall": {"name": "the hall", "light": "lit",
                                "anchors": {"door": {"desc": "the door", "dir": "n"},
                                            "hearth": {"desc": "the hearth", "dir": "s"}}}},
             "positions": {"Bob": "hall", PLAYER: "hall"},
             "stations": {"Bob": {"at": "door"}, PLAYER: {"at": "hearth"}},
             "orientation": {"Bob": {"facing": "n"}}}

    monkeypatch.setattr(character, "persona_of",
                        lambda chat: {"name": PLAYER, "identity": {"name": PLAYER}})
    note = _player_silence_note(scene, {"id": 1}, default_character_data("Bob"),
                                spoke=False, label=lambda n: n)
    assert note == {}
    # Facing the player, the note stands.
    scene["orientation"]["Bob"] = {"facing": "s"}
    assert _player_silence_note(scene, {"id": 1}, default_character_data("Bob"),
                                spoke=False, label=lambda n: n)


def test_a_disguised_co_player_is_called_what_the_view_called_him_on_the_touch_line():
    """Review round 4 (2026-10-05): the touch line asked the present-tense
    rule of cast cards only, so a co-player the player knows was named
    there beside a view that said "the hooded pilgrim's hand"."""
    from agents.narration import _sensory_channels_manifest
    scene = {"rooms": {"cellar": {"name": "the cellar", "light": "lit"}},
             "positions": {PLAYER: "cellar", "Quill": "cellar"},
             "contacts": [{"actor": "Quill", "target": PLAYER, "actor_part": "hand",
                           "target_part": "shoulder", "relation": "on", "motion": "still"}]}
    for earned, present in (({"Quill": "the hooded pilgrim"}, None),
                            ({}, lambda name: "the unfamiliar person")):
        manifest = _sensory_channels_manifest(
            scene, PLAYER, "You feel a hand on your shoulder.", [], {"Quill"}, {}, "cellar",
            earned=earned, present=present)
        touch = json.dumps((manifest.get("touch") or {}).get("standing") or [])
        assert "Quill" not in touch, touch


def test_a_disguised_bodys_hidden_parts_never_reach_the_page(temp_db, monkeypatch):
    """Review round 5 (2026-10-05): keyed by the view's label but read raw
    from the card, a disguised body's nine tails went to the page under "the
    hooded pilgrim" while the view hid them. Parts come from the map the
    views are rendered from: a transformation's, then a disguise's
    concealment."""
    out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, LIT_HALL, parts=NINE_TAILS,
                                     disguise=PILGRIM)
    assert "tail" not in out["views"]["player"].lower()
    assert "tail" not in json.dumps(payload.get("authored_body_parts") or {})


def test_the_players_own_parts_are_always_their_own(temp_db, monkeypatch):
    """A body is never concealed from itself: the player's own parts come
    from their own card whatever the scene's map holds."""
    _out, payload, _ctx, _ids = _beat(
        temp_db, monkeypatch, LIT_HALL,
        persona_parts=[{"kind": "tail", "count": 6, "at": "waist"}])
    assert "tail" in " ".join((payload.get("authored_body_parts") or {}).get(PLAYER) or [])


def test_a_body_known_only_by_ear_keeps_its_anatomy_off_the_page(temp_db, monkeypatch):
    """Review round 5 (2026-10-05): "known by name" was taken for "its parts
    could be seen" -- a name heard in the dark put her nine tails on the
    page. A known body's parts need a body seen in full, now or before."""
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, _dark_hand(), parts=NINE_TAILS,
                                      known={PLAYER: ["Alice"]})
    assert "tail" not in json.dumps(payload.get("authored_body_parts") or {})
    _out, payload, _ctx, _ids = _beat(temp_db, monkeypatch, _dark_hand(), parts=NINE_TAILS,
                                      known={PLAYER: ["Alice"]}, described_before=("Alice",))
    assert "tail" in " ".join((payload.get("authored_body_parts") or {}).get("Alice") or [])
