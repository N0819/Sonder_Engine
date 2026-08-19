"""An enclosed body's ACT must not reach whatever encloses it.

Found auditing a live playthrough. One character was shut inside a container
another was carrying. The Director's `observable` for the enclosed body's beat
was correct by its own spec -- what a hypothetical SIGHTED bystander would see
-- and every containment gate downstream fired as designed:
`containment_conceals` said True, `visual_channel_to_actor` came back False,
the actor's appearance was stripped from the payload.

The view written for the carrier still named the act. Identity was gated, no
visual detail was added, and the act's VERB walked straight across into the
touch channel as a tactile paraphrase. The character agent then quoted that
view verbatim as its sole observation and acted on it.

Two holes let it through, and this file guards both:

  1. The perception prompt had no rule for what a NON-VISUAL channel may
     carry. It has detailed rules for sight, sound, smell, vibration and
     temperature, and none at all for touch -- so degrading the modality
     while preserving the semantics read as compliant. A perceiver's declared
     `senses` (a keen-touch trait that reads muscle tension and pulse through
     skin contact) was then used as the bridge justifying the resolution.

  2. `_perceptible_entities` handed the objective entity table to every
     perceiver ungated. The enclosed body's record spelled out in
     `state.posture` exactly what it was doing -- an independent path to the
     same leak, live in the payload whether or not the Director's observable
     said anything.

The rule both encode: a closed channel costs RESOLUTION, not just modality.
Sensation may cross; the name of the act may not. Guessing what a sensation
means is the character agent's job, not perception's.
"""

import json
import time

import pytest

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

from agents.common import (
    _delivery_ok, _ensure_environment, _inject_action, _perceptible_entities,
)
from agents.perception import _in_plain_view, _source_channels
from llm.prompts import DEFAULT_PROMPTS
from world.spatial import containment_conceals


HOLDER = "Satchel"
CARRIER = "Bo"
ENCLOSED = "Ada"
COMPANION = "Cass"


def _scene():
    """One room. ENCLOSED is shut inside HOLDER, which CARRIER stands with."""
    return {
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {CARRIER: "hall", HOLDER: "hall"},
        "contained": {ENCLOSED: {"in": HOLDER, "mode": "container"}},
        "entities": {
            ENCLOSED: {
                "name": ENCLOSED, "kind": "object", "description": "",
                "state": {
                    "proximity": f"curled in the bottom of the {HOLDER}",
                    "posture": "unfolding a sheet of paper and reading it",
                    "description": "small enough to stand in a palm",
                },
            },
            "lantern_01": {
                "name": "Lantern", "kind": "object",
                "description": "A shuttered lantern.",
                "aliases": ["lamp", "light"],
                "state": {"posture": "guttering on the side table"},
            },
        },
    }


# --- the premise the gate rests on ----------------------------------------

def test_nothing_outside_the_enclosure_has_sight_of_what_is_inside_it():
    """Sanity: the primitive the gate calls already answers correctly.

    This was never the broken part -- it is asserted here so a regression in
    `containment_conceals` shows up as a failure of THIS story, not as a
    silently-passing gate that stopped gating anything.
    """
    sc = _scene()
    assert containment_conceals(sc, CARRIER, ENCLOSED)
    # ...and the enclosed body is not concealed from itself.
    assert not containment_conceals(sc, ENCLOSED, ENCLOSED)


# --- 1. objective entity state is withheld from minds that cannot reach it -

def test_enclosed_state_withheld_when_only_an_outsider_perceives():
    """The act-naming payload the live leak had a second path through."""
    projected = _perceptible_entities(_scene(), [CARRIER])

    assert "state" not in projected[ENCLOSED]
    assert "reading" not in json.dumps(projected).casefold()


def test_enclosed_state_withheld_from_the_body_doing_the_enclosing():
    """The live shape: the enclosure is itself a mind, and a perceiver.

    Distinct from the case above, where the container is inert and the
    perceiver stands outside it. A holder is NOT exempt from its own
    enclosure -- it is not inside itself, so the two do not match, and what
    it has instead of sight is touch. This is the arrangement the leak was
    found in, and the one where "it can obviously feel that" is most
    tempting: what it can feel is pressure and movement, not the act.
    """
    sc = _scene()
    sc["contained"][ENCLOSED] = {"in": CARRIER, "mode": "pocket"}
    projected = _perceptible_entities(sc, [CARRIER])

    assert "state" not in projected[ENCLOSED]
    assert "reading" not in json.dumps(projected).casefold()


def test_the_enclosed_body_still_appears_only_its_state_is_gone():
    """Presence may reach a perceiver by contact or sound; the act may not.

    Dropping the whole record would be a different bug -- a body shifting
    inside a bag someone is holding is not absent from their world.
    """
    projected = _perceptible_entities(_scene(), [CARRIER])
    assert ENCLOSED in projected
    assert projected[ENCLOSED]["name"] == ENCLOSED


def test_a_body_keeps_its_own_state_when_it_is_the_perceiver():
    """Proprioception is not a leak."""
    projected = _perceptible_entities(_scene(), [ENCLOSED])
    assert projected[ENCLOSED]["state"]["posture"] == \
        "unfolding a sheet of paper and reading it"


def test_one_reaching_perceiver_is_enough():
    """The gate is 'nobody in this call can reach it', not 'someone cannot'."""
    projected = _perceptible_entities(_scene(), [CARRIER, ENCLOSED])
    assert "state" in projected[ENCLOSED]


def test_two_bodies_inside_the_same_enclosure_reach_each_other():
    sc = _scene()
    sc["contained"][COMPANION] = {"in": HOLDER, "mode": "container"}
    projected = _perceptible_entities(sc, [COMPANION])
    assert "state" in projected[ENCLOSED]


# --- the ordinary scene must be untouched ----------------------------------

def test_an_entity_in_the_open_is_unaffected():
    projected = _perceptible_entities(_scene(), [CARRIER])
    assert projected["Lantern"]["state"]["posture"] == \
        "guttering on the side table"


def test_nothing_contained_means_nothing_gated():
    sc = _scene()
    sc.pop("contained")
    projected = _perceptible_entities(sc, [CARRIER])
    assert "state" in projected[ENCLOSED]
    assert "state" in projected["Lantern"]


def test_omitting_the_perceiver_set_keeps_the_whole_table():
    """Back-compat: callers with no perceiver set to gate against."""
    projected = _perceptible_entities(_scene())
    assert "state" in projected[ENCLOSED]


def test_the_alias_scrub_still_applies_alongside_the_state_gate():
    """The two hygiene rules on this table compose."""
    projected = _perceptible_entities(_scene(), [CARRIER])
    assert "aliases" not in projected["Lantern"]
    assert "lamp" not in json.dumps(projected).casefold()


# --- 3. the deterministic backstop must not undo the model's compliance -----
#
# Caught in live play the moment the prompt rules above started working. The
# model stopped naming the act, which meant the injector's duplicate check
# (`_action_already_rendered`) no longer found it in the view -- so the
# backstop pasted the raw `observable` in instead, complete with the
# unknown-actor label:
#
#   "...the beautiful young woman appearing swallows thick fluids, throat
#    contracting and working visibly."
#
# The gate was `rel.get("same_room") or vis`. `vis` was correctly False. But a
# carried body's position derives to its carrier's, so `same_room` was True and
# the OR reinstated the exact bypass containment concealment exists to close.
# Every leak this file guards would have walked back out through here.

def _enclosed_rel():
    """What perception computes for an actor sealed inside the perceiver."""
    return {"same_room": True, "barrier": "open", "distance": "same",
            "light": "lit", "concealed": True}


def test_an_enclosed_actor_is_not_in_plain_view_despite_same_room():
    assert not _in_plain_view(_enclosed_rel(), False)
    # The other arm too: a stale/incorrect visual flag must not resurrect it.
    assert not _in_plain_view(_enclosed_rel(), True)


def test_an_ordinary_same_room_actor_is_still_in_plain_view():
    """The bypass is closed for concealment only -- nothing else changes."""
    assert _in_plain_view({"same_room": True}, False)
    assert _in_plain_view({"same_room": False}, True)
    assert not _in_plain_view({"same_room": False}, False)


def test_the_injector_does_not_paste_an_enclosed_actor_s_observable():
    """The regression itself, at the function that produced it."""
    view = "You feel a shifting weight low in the satchel at your hip."
    out = _inject_action(
        view, "the woman in the grey coat",
        "unfolds a sheet of paper and reads it",
        _in_plain_view(_enclosed_rel(), False),
    )
    assert out == view
    assert "unfolds" not in out


def test_the_injector_still_delivers_an_actor_in_the_open():
    view = "You are in the hall."
    out = _inject_action(
        view, "the woman in the grey coat",
        "unfolds a sheet of paper and reads it",
        _in_plain_view({"same_room": True}, False),
    )
    assert "unfolds" in out


def test_the_empty_view_fallback_does_not_announce_an_enclosed_actor():
    """`_ensure_environment` had the same `same_room` bypass."""
    out = _ensure_environment(
        None, {"room_name": "Hall", "room_notes": ""},
        "the woman in the grey coat", _enclosed_rel(), False,
        "unfolds a sheet of paper and reads it",
    )
    assert "here with you" not in out
    assert "unfolds" not in out
    assert "Hall" in out          # the perceiver still gets their surroundings


def test_source_channels_conceals_an_enclosed_source_from_the_room():
    """The outcome pass and the opening pass never asked this question.

    `visual_channel_to_sources` was built from a bare `spatial_rel`, so an
    enclosed body read as visually available to everyone standing around
    whatever held it -- which is what gated the appearance-describer that
    pasted a full appearance string onto the end of the view.
    """
    sc = _scene()
    sc["contained"][ENCLOSED] = {"in": CARRIER, "mode": "pocket"}
    sc["positions"][ENCLOSED] = "hall"
    sources = [{"name": ENCLOSED, "room": "hall"}]

    ch = _source_channels(sc, CARRIER, "hall", sources)
    assert ch["visual_channel_to_sources"][ENCLOSED] is False
    assert ch["spatial_to_sources"][ENCLOSED]["concealed"] is True


def test_source_channels_leaves_an_ordinary_source_visible():
    sc = _scene()
    sources = [{"name": CARRIER, "room": "hall"}]
    ch = _source_channels(sc, "Dana", "hall", sources)
    assert ch["visual_channel_to_sources"][CARRIER] is True
    assert not ch["spatial_to_sources"][CARRIER].get("concealed")


# --- 4. end to end, through the real call site ------------------------------
#
# The unit tests above cover `_in_plain_view`, but a call site that reverted to
# `rel.get("same_room") or vis` would sail past every one of them. This drives
# the actual perception_act pass with a stubbed model that returns a COMPLIANT
# view -- one that never names the act, which is what the prompt rules now ask
# for. Anything about the act in the result is therefore the deterministic
# backstop's doing, which is precisely the regression.

def _enclosed_ctx(temp_db):
    """Player shut inside the one cast member, who is the reactor."""
    persona = default_persona_data(ENCLOSED)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (ENCLOSED, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Enclosed", "", time.time(), persona_id))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (CARRIER, json.dumps(default_character_data(CARRIER)), "{}",
         time.time(), "char_carrier"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"room1": {"name": "Hall", "adjacent": []}},
        "positions": {ENCLOSED: "room1", CARRIER: "room1"},
        "contained": {ENCLOSED: {"in": CARRIER, "mode": "pocket"}},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known",
                 {CARRIER: [ENCLOSED], ENCLOSED: [CARRIER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Enclosed", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "room1"
    ctx.director_interpret = {
        "action": {"attempt": "reads the note", "visibility": "overt",
                   "conceal_from": [], "targets": [], "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "reads the note",
            "observable": "unfolds a sheet of paper and reads it",
            "visibility": "overt", "conceal_from": [], "targets": [],
            "commitment": "asserted", "verb": "read", "stage": "immediate",
            "event_id": "turn:1:player:0:action",
        }],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [cast[0]["id"]]},
    }
    return ctx, cast[0]["id"]


def test_perception_act_does_not_paste_an_enclosed_actor_s_act(
        temp_db, monkeypatch):
    """The live regression, end to end.

    The stub returns the kind of view the prompt rules now produce: the
    sensation, never the act. Before the fix the backstop appended
    "<actor> unfolds a sheet of paper and reads it" to exactly this.
    """
    import agents.perception as perception

    ctx, reactor_id = _enclosed_ctx(temp_db)
    out = perception.perception_act(ctx, nonce="n")
    view = out["views"][str(reactor_id)] or ""

    assert "unfolds" not in view, view
    assert "sheet of paper" not in view, view
    assert "reads" not in view, view
    # The old positive half ("...and the perceiver still gets the weight
    # against their hip") asserted a sentence the STUBBED MODEL supplied,
    # not one the engine produced, so it cannot move here. What survives is
    # the pairing this test exists for: the leak is absent while the view is
    # still a view, not silence.
    assert view.strip(), "the enclosing body received nothing at all"


def test_perception_act_still_delivers_an_actor_in_the_open(
        temp_db, monkeypatch):
    """The same path with nothing enclosing anyone: delivery is unchanged."""
    import agents.perception as perception

    ctx, reactor_id = _enclosed_ctx(temp_db)
    sc = temp_db.wget(ctx.chat["id"], "scene", {})
    sc.pop("contained")
    temp_db.wset(ctx.chat["id"], "scene", sc)

    out = perception.perception_act(ctx, nonce="n")
    view = out["views"][str(reactor_id)] or ""
    assert "unfolds" in view, view


# --- 5. the other direction: what the ENCLOSED body is told ----------------
#
# Everything above gates what the ENCLOSING side learns. Concealment is
# symmetric -- being shut inside blocks the view OUT as completely as the view
# in -- and the outcome pass had a second, separate leak on the way back.
#
# Found in live play after the rest of this file shipped. The enclosed player
# HEARS the character enclosing them speak, which is legitimate; audibility is
# not sight. But the unrecognised-speaker branch pasted that speaker's full
# appearance paragraph into the view, gated on
# `visual.get(speaker) or rel.get("same_room")`. Its own comment says the
# right thing -- "pasting a full visual appearance onto an unseen voice would
# hallucinate sight the perceiver doesn't have" -- and it was written for
# comm channels and walls, both of which put the speaker in ANOTHER room. A
# body sealed inside the speaker is in the same room by derivation, so the OR
# was true and the paste went ahead.

def _speaking_enclosure_ctx(temp_db):
    """Player shut inside the one cast member, who SPEAKS this beat.

    The player does not recognise them, which is what routes the view through
    the appearance-pasting branch.
    """
    persona = default_persona_data(ENCLOSED)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (ENCLOSED, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Enclosed", "", time.time(), persona_id))
    sheet = default_character_data(CARRIER)
    # Where character_appearance actually reads from. Setting a top-level
    # "appearance" key silently does nothing -- the fixture looked right and
    # tested nothing, which the mutation check caught and a green run did not.
    sheet["embodiment"]["visible"]["summary"] = (
        "a tall woman in a long grey coat, hood raised, "
        "boots caked with river mud")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (CARRIER, json.dumps(sheet), "{}", time.time(), "char_speaker"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"room1": {"name": "Hall", "adjacent": []}},
        "positions": {ENCLOSED: "room1", CARRIER: "room1"},
        "contained": {ENCLOSED: {"in": CARRIER, "mode": "inside"}},
        "entities": {}, "attire": {}, "overlays": {}})
    # The player has NOT been introduced to them -- the unrecognised branch.
    temp_db.wset(chat_id, "known", {})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Enclosed", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "room1"
    ctx["director_interpret"] = {"flow": {"reactors": [cast[0]["id"]]}}
    ctx["director_resolve"] = {
        "resolved_event": "A voice speaks, close and all around.",
        "dialogue_order": [CARRIER],
        "dialogue_log": [{"speaker": CARRIER,
                          "exact_quote": "Stay still.",
                          "volume": "normal", "intended_target": ENCLOSED,
                          "visibility": "overt", "conceal_from": []}],
        "state_diff": {},
    }
    # Give the carrier a minimal character result so they appear in `sources`
    # (perception_outcome only adds cast members who spoke/acted this beat).
    cast_id = cast[0]["id"] if cast else 1
    ctx.character_results = {
        cast_id: {"name": CARRIER, "sequence": [
            {"type": "speech", "text": "Stay still.",
             "visibility": "overt"}]}
    }
    return ctx


def test_enclosed_player_hears_the_voice_but_gets_no_appearance(
        temp_db, monkeypatch):
    """The live report: the player was still getting full NPC appearance."""
    import agents.perception as perception

    ctx = _speaking_enclosure_ctx(temp_db)
    out = perception.perception_outcome(ctx, nonce="n")
    view = out["views"]["player"] or ""

    # The appearance paragraph must not be there, in whole or in part.
    assert "grey coat" not in view, view
    assert "hood raised" not in view, view
    assert "river mud" not in view, view
    # ...but the voice legitimately reached them. Audibility is not sight.
    assert "Stay still" in view, view


def test_enclosed_player_gets_a_voice_not_a_visual_label(
        temp_db, monkeypatch):
    """Gating the paragraph left a COMPRESSED version going through.

    `_unknown_actor_label` derives a short descriptor from the same
    appearance so two strangers in a scene are distinguishable -- and it was
    built regardless of `can_see`, then injected as the dialogue's speaker.
    So the full paragraph stopped and "the tall woman in a long grey coat
    says ..." carried on. Milder, same leak: a perceiver who cannot see the
    speaker has no visual referent for them at all.
    """
    import agents.perception as perception

    ctx = _speaking_enclosure_ctx(temp_db)

    view = perception.perception_outcome(ctx, nonce="n")["views"]["player"] or ""

    for token in ("grey coat", "hood", "river mud", "tall woman", "boots"):
        assert token not in view, (token, view)
    assert "Stay still" in view, view


def test_outcome_payload_withholds_appearances_nobody_can_see(
        temp_db, monkeypatch):
    """The model's own channel, which no deterministic gate covers.

    The live view carried detail ("soaked silk strips clinging to her
    curves") that no injector had pasted -- the model wrote it, from
    `present_appearances`. The act pass strips this when nobody can see the
    actor; the outcome pass shipped it unconditionally.
    """
    import agents.perception as perception

    ctx = _speaking_enclosure_ctx(temp_db)
    # `present_appearances` was the payload field the model wrote the leak
    # from. There is no such field and no such model: the only place an
    # appearance can now reach a mind is a percept, and an unseen carrier
    # never becomes one.
    view = perception.perception_outcome(ctx, nonce="n")["views"]["player"]

    assert CARRIER not in (view or ""), view
    assert "grey coat" not in (view or ""), view


def test_outcome_payload_keeps_appearances_someone_can_see(
        temp_db, monkeypatch):
    """Negative control: an ordinary scene still hands over appearances.

    A source is excluded from its OWN visibility test -- it can always see
    itself, which would keep every appearance alive regardless of who else
    is there -- so this must pass for a reason other than self-sight.
    """
    import agents.perception as perception

    ctx = _speaking_enclosure_ctx(temp_db)
    sc = temp_db.wget(ctx.chat["id"], "scene", {})
    sc.pop("contained")           # nothing enclosing anyone now
    temp_db.wset(ctx.chat["id"], "scene", sc)

    view = perception.perception_outcome(ctx, nonce="n")["views"]["player"] or ""

    # The old assertion looked for the carrier's NAME in a payload field.
    # A view names only what the observer has earned; what it must carry
    # here is the appearance of a body they can plainly see.
    assert "grey coat" in view, view


# --- 2. the prompt rule that governed the surviving channel -- REMOVED ------
#
# This section asserted paragraphs of the `perception` prompt, on the stated
# premise that "perception writes prose. The rule can only live in the
# prompt." That premise is gone: perception makes no model call at all, every
# view is composed from the typed IR in `agents/composer.py`, and the
# `perception` prompt has been deleted from the language packs.
#
# Hole 1 therefore cannot recur -- there is no model left to disobey the rule.
# Hole 2, the ungated entity table, is real code and is tested above. A test
# that asserts wording no model reads is not coverage of anything, and it
# cost a translation of 28,467 characters in every language pack.


# --- 6. one being, two spellings -------------------------------------------
#
# Everything in section 1 keys the enclosed body by its DISPLAY NAME: `Ada` is
# the entities dict key, the `name` field and the `contained` key at once. That
# is the one arrangement in which a gate that asks a single spelling cannot be
# wrong. A scene routinely keys the same being the other way -- an entity id in
# `positions` and `contained`, a display name on the record -- and
# `spatial_identity.canonical_subject_map` deliberately refuses to fold a lone
# entity-id key, so the two spellings stay live side by side.
#
# Both parties to the question carry the pair, so both are tested here.

ENCLOSED_ID = "ada_01"
CARRIER_ID = "bo_01"


def _id_keyed_scene():
    """The same story, with the enclosed body keyed by id rather than name."""
    sc = _scene()
    sc["entities"][ENCLOSED_ID] = sc["entities"].pop(ENCLOSED)
    sc["contained"] = {ENCLOSED_ID: {"in": HOLDER, "mode": "container"}}
    return sc


def test_the_premise_two_spellings_of_one_being_answer_differently():
    """Sanity, and the reason the gate cannot ask just one of them.

    `containment_conceals` resolves the string it is given. Handed the
    spelling the scene does not key this body by, it answers about a being
    with no enclosure at all -- which is indistinguishable from an answer
    about a body standing in the open.
    """
    sc = _id_keyed_scene()
    assert containment_conceals(sc, CARRIER, ENCLOSED_ID)
    assert not containment_conceals(sc, CARRIER, ENCLOSED)


def test_enclosed_state_withheld_when_the_entity_is_keyed_by_id():
    """The leak: the gate asked the display name, the scene keyed the id."""
    projected = _perceptible_entities(_id_keyed_scene(), [CARRIER])

    assert "state" not in projected[ENCLOSED]
    assert "reading" not in json.dumps(projected).casefold()


def test_an_id_keyed_body_keeps_its_own_state_when_it_is_the_perceiver():
    """Proprioception survives the wider gate: nothing is concealed from
    itself, under either of its own spellings."""
    projected = _perceptible_entities(_id_keyed_scene(), [ENCLOSED])
    assert projected[ENCLOSED]["state"]["posture"] == \
        "unfolding a sheet of paper and reading it"


def test_an_id_keyed_entity_in_the_open_is_unaffected():
    """Negative control: the wider gate must subtract only from the enclosed.

    `Lantern`/`lantern_01` is the same two-spelling shape with nothing shut
    around it, so a gate that treated an unresolvable spelling as concealment
    would silently blank the ordinary scene.
    """
    projected = _perceptible_entities(_id_keyed_scene(), [CARRIER])
    assert projected["Lantern"]["state"]["posture"] == \
        "guttering on the side table"


def test_id_keyed_bodies_inside_the_same_enclosure_reach_each_other():
    sc = _id_keyed_scene()
    sc["contained"][COMPANION] = {"in": HOLDER, "mode": "container"}
    projected = _perceptible_entities(sc, [COMPANION])
    assert "state" in projected[ENCLOSED]


def _open_room_relation():
    """What a caller computes for two bodies standing in one lit room.

    A carried body's position derives to its carrier's, so this is exactly
    the relation the delivery gate is handed for a body inside a satchel
    somebody is holding: same room, no barrier, full light. Containment is
    the only thing standing between them.
    """
    return {"same_room": True, "barrier": "open", "distance": "same",
            "light": "lit"}


def test_the_delivery_gate_conceals_an_id_keyed_enclosed_body():
    """The same blindness at the gate every deterministic delivery asks.

    `_delivery_ok` resolves containment from the strings its caller happened
    to use, so an enclosed body keyed by id read as a body standing in the
    open and both channels were granted.
    """
    sc = _id_keyed_scene()
    assert not _delivery_ok(_open_room_relation(), sc, CARRIER, ENCLOSED,
                            "sight")
    assert not _delivery_ok(_open_room_relation(), sc, CARRIER, ENCLOSED,
                            "hearing")


def test_the_delivery_gate_still_delivers_an_ordinary_body():
    """Negative control: nothing shut around anybody, both channels open."""
    sc = _id_keyed_scene()
    sc.pop("contained")
    assert _delivery_ok(_open_room_relation(), sc, CARRIER, ENCLOSED, "sight")
    assert _delivery_ok(_open_room_relation(), sc, CARRIER, ENCLOSED,
                        "hearing")


def test_the_delivery_gate_still_delivers_between_co_occupants():
    sc = _id_keyed_scene()
    sc["contained"][COMPANION] = {"in": HOLDER, "mode": "container"}
    assert _delivery_ok(_open_room_relation(), sc, COMPANION, ENCLOSED,
                        "sight")


def test_state_withheld_when_the_perceiver_is_the_id_keyed_one():
    """The same defect on the other side of the question.

    The perceiver arrives as a display name and the scene shut them in under
    their entity id, so the gate resolved an observer standing in the open and
    handed them the room's objective state. Being enclosed blocks the view out
    exactly as it blocks the view in.
    """
    sc = _scene()
    sc["entities"][CARRIER_ID] = {
        "name": CARRIER, "kind": "person", "description": "",
        "state": {"posture": "standing"},
    }
    sc["contained"] = {CARRIER_ID: {"in": HOLDER, "mode": "container"}}

    projected = _perceptible_entities(sc, [CARRIER])

    assert "state" not in projected["Lantern"]
    assert "guttering" not in json.dumps(projected).casefold()
