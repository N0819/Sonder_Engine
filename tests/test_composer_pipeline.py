"""The composer path end to end: PERCEPTION_NO_LLM runs the three perception
stages with zero model calls, composes views from the IR, mints episodes for
memory, and keeps the firewall without any scrub firing.

Full tier (temp_db): these exercise the real stage entry points against a
committed scene, the same way the model-path stage tests do.
"""

from __future__ import annotations

import json
import time

import pytest

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Perception has no model seam of its own to stub any more — the flag
    and the fan-out are both gone. The guard now sits one level down, on
    the shared helper every agent role calls, so it still fires if any
    perception code path ever reaches for a model again."""
    import agents.common as common

    def _boom(*args, **kwargs):  # pragma: no cover - the assertion
        raise AssertionError("perception attempted a model call")

    monkeypatch.setattr(common, "_agent_json", _boom)


def _make_ctx(temp_db, *, known=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Composer", "", time.time()),
    )
    sheet = default_character_data("Reya")
    sheet["embodiment"]["visible"]["summary"] = (
        "Reya, a wiry courier with storm-grey eyes and a patched flight jacket"
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(sheet), "{}", time.time(), "char_reya"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "Waystation", "time": "night",
        "rooms": {"hall": {"name": "the Long Hall",
                           "notes": "Rope coils hang from the rafters.",
                           "adjacent": []}},
        "positions": {"The Stranger": "hall", "Reya": "hall"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    if known:
        temp_db.wset(chat_id, "known", known)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "hello", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Composer", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="hello", created=time.time()),
        cast=cast, input="hello",
    )
    return ctx, char_id


def _interp(char_id, sequence):
    return {
        "sequence": sequence,
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": [char_id], "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }


def test_act_pass_composes_with_zero_model_calls(temp_db):
    from agents.perception import perception_act

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_interpret = _interp(char_id, [
        {"type": "speech", "text": "Is anyone here?", "volume": "normal",
         "tone": "wary", "visibility": "overt", "conceal_from": []},
        {"type": "action", "attempt": "raises the lantern",
         "observable": "raises the lantern", "visibility": "overt"},
    ])
    out = perception_act(ctx, "n0")

    view = out["views"][str(char_id)]
    assert view
    # The declared line was delivered verbatim...
    assert "Is anyone here?" in view
    # ...and the unrecognized player is never named.
    assert "The Stranger" not in view
    assert "the lantern" in view
    # Standing state anchors the view for a character agent.
    assert "the Long Hall" in view
    assert "Rope coils hang from the rafters." in view
    # Observations project from the IR and quote the rendered spans.
    atoms = out["observations"][str(char_id)]
    assert atoms and all(a["observed"]["text"] in view for a in atoms)
    assert any(a["channel"] == "hearing" for a in atoms)
    # No tripwire fired: a firing tripwire is a composer defect.
    assert not [w for w in ctx.warnings if "COMPOSER TRIPWIRE" in w]
    assert isinstance(out.get("composer_ledger"), dict)


def test_act_pass_records_the_company_the_people_projection_reads(temp_db):
    """The delivered-company record rides the perception step beside the
    views it was composed with: same admitted percepts, so it cannot list a
    body the rendered view did not carry. Without this write-side proof,
    `story_view._delivered_company` is a reader of a field nothing produces
    -- the guard that cannot fire."""
    from agents.perception import perception_act

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_interpret = _interp(char_id, [
        {"type": "action", "attempt": "raises the lantern",
         "observable": "raises the lantern", "visibility": "overt"},
    ])
    out = perception_act(ctx, "n0")

    body, = out["company"][str(char_id)]
    # Reya does not recognize the player: the record carries the composer's
    # verdict and label, and the canonical name only engine-side.
    assert body["name"] == "The Stranger"
    assert body["recognized"] is False
    assert body["label"] and "Stranger" not in body["label"]
    assert body["key"] and "Stranger" not in body["key"]

    # Persist the step the way the runtime does, and read it back through
    # the facade: the write shape and the read shape must be one contract.
    from web import story_view

    step_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
        (ctx.turn.id, "perception_act", "act", 2))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (step_id, json.dumps(out), time.time()))

    view = story_view.player_view(ctx.chat.id, str(char_id))
    person, = view["people"]
    # Since schema 3 the facade re-keys the body onto a viewer-scoped
    # derivative of the immutable identity: the composer's `key` is a
    # canonical-name hash shared by every viewer, i.e. a correlation key,
    # so it must not surface as the id itself.
    assert person["id"].startswith("body:")
    assert person["id"] != "body:" + body["key"]
    assert person["display_name"] == body["label"]
    assert person["identity_status"] == "observed"
    assert "The Stranger" not in json.dumps(view)


def test_a_recognising_observer_is_recorded_under_the_earned_name(temp_db):
    """`recognized` in the company record is `observer_display_map`'s own
    verdict -- a recognised body maps to its own name -- not a downstream
    ledger re-check, which a disguise would make wrong."""
    from agents.perception import perception_act

    ctx, char_id = _make_ctx(temp_db, known={"Reya": ["The Stranger"]})
    ctx.director_interpret = _interp(char_id, [
        {"type": "action", "attempt": "raises the lantern",
         "observable": "raises the lantern", "visibility": "overt"},
    ])
    out = perception_act(ctx, "n0")

    body, = out["company"][str(char_id)]
    assert body["name"] == "The Stranger"
    assert body["label"] == "The Stranger"
    assert body["recognized"] is True


def test_concealed_line_absent_and_episode_minted_from_ir(temp_db):
    from agents.perception import perception_outcome

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_interpret = _interp(char_id, [
        {"type": "action", "attempt": "waves a hand",
         "observable": "waves a hand", "visibility": "overt"},
    ])
    ctx.director_resolve = {
        "resolved_event": "The stranger waves; Reya mutters a private oath.",
        "dialogue_log": [
            {"speaker": "Reya", "exact_quote": "State your business.",
             "volume": "normal"},
            {"speaker": "Reya", "exact_quote": "The cache is behind the well.",
             "volume": "normal", "visibility": "concealed",
             "conceal_from": ["The Stranger"]},
        ],
        "state_diff": {},
    }
    out = perception_outcome(ctx, "n0")

    player_view = out["views"]["player"]
    assert player_view
    assert "State your business." in player_view
    # The concealed line never reached the player -- absent from the view...
    assert "behind the well" not in player_view
    # ...and absent from every percept-derived representation.
    assert "behind the well" not in json.dumps(out["observations"])

    # The character's episode is minted from the IR: first person,
    # event-bearing content first, no second-person view prose.
    episode = out["episodes"][str(char_id)]
    assert episode
    assert "waves a hand" in episode or "wave a hand" in episode
    assert not episode.startswith("You ")
    assert not episode.startswith("I was in")
    meta = out["episode_meta"][str(char_id)]
    assert isinstance(meta.get("entities"), list)
    assert not [w for w in ctx.warnings if "COMPOSER TRIPWIRE" in w]


def test_player_delta_second_beat_omits_unchanged_room(temp_db):
    from agents.perception import perception_outcome

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_interpret = _interp(char_id, [])
    ctx.director_resolve = {
        "resolved_event": "",
        "dialogue_log": [
            {"speaker": "Reya", "exact_quote": "Well met.",
             "volume": "normal"},
        ],
        "state_diff": {},
    }
    first = perception_outcome(ctx, "n0")
    assert "the Long Hall" in (first["views"]["player"] or "")

    # Persist the first turn's outcome step, then run the next turn: the
    # player's view carries the delta, not the unchanged room restated.
    step_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
        (ctx.turn.id, "perception_outcome", "outcome", 0),
    )
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active,reasoning) "
        "VALUES(?,?,?,1,'')",
        (step_id, json.dumps(first), time.time()),
    )
    turn2 = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (ctx.chat.id, 2, "wait", time.time()),
    )
    ctx2 = PipelineContext(
        chat=ctx.chat,
        turn=TurnData(id=turn2, chat_id=ctx.chat.id, idx=2,
                      player_input="wait", created=time.time()),
        cast=ctx.cast, input="wait",
    )
    ctx2.director_interpret = _interp(char_id, [])
    ctx2.director_resolve = {
        "resolved_event": "",
        "dialogue_log": [
            {"speaker": "Reya", "exact_quote": "Still waiting.",
             "volume": "normal"},
        ],
        "state_diff": {},
    }
    second = perception_outcome(ctx2, "n1")
    player_view = second["views"]["player"] or ""
    assert "Still waiting." in player_view
    assert "You are in the Long Hall." not in player_view

    # The character view still carries the full standing state -- a
    # stateless mind gets everything, every beat.
    char_view = second["views"][str(char_id)] or ""
    assert "the Long Hall" in char_view

    # And an eventless-for-the-character beat of their OWN speech only
    # mints no episode restating the room (their own line is not their
    # percept; nothing else happened).
    assert second["episodes"][str(char_id)] == ""


def test_look_intent_rerenders_player_standing_state(temp_db):
    from agents.perception import perception_outcome

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_interpret = _interp(char_id, [
        {"type": "action", "attempt": "looks around the hall",
         "observable": "looks around the hall", "visibility": "overt"},
    ])
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}}
    # Seed a previous-turn ledger claiming the room was already rendered.
    prev_turn = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (ctx.chat.id, 0, "arrive", time.time()),
    )
    import agents.composer as composer
    env = composer.environment_percept(
        "hall", "the Long Hall", "Rope coils hang from the rafters.")
    step_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
        (prev_turn, "perception_outcome", "outcome", 0),
    )
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active,reasoning) "
        "VALUES(?,?,?,1,'')",
        (step_id, json.dumps({"views": {}, "observations": {},
                              "composer_ledger": {
                                  "player": {"standing": [env.dedupe_key],
                                             "described": []}}}),
         time.time()),
    )
    out = perception_outcome(ctx, "n0")
    assert "You are in the Long Hall." in (out["views"]["player"] or "")


def test_commit_mints_composed_episode_with_typed_entities(temp_db):
    from persist.commit import prepare_memory_commit

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}, "summary": ""}
    ctx.perception_outcome = {
        "views": {str(char_id): "You are in the Long Hall. The grey-eyed "
                                "figure waves a hand."},
        "observations": {},
        "episodes": {str(char_id): "I saw the grey-eyed figure wave a hand."},
        "episode_meta": {str(char_id): {
            "gist": "I saw the grey-eyed figure wave a hand.",
            "entities": ["the grey-eyed figure"]}},
    }
    prepared = prepare_memory_commit(ctx)
    episodic = [m for m in prepared["memory_batch"]["prepared"]
                if m["kind"] == "episodic"]
    assert len(episodic) == 1
    assert episodic[0]["content"] == "I saw the grey-eyed figure wave a hand."
    assert episodic[0]["entities"] == ["the grey-eyed figure"]


def test_commit_mints_nothing_for_a_composed_non_event(temp_db):
    from persist.commit import prepare_memory_commit

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}, "summary": ""}
    ctx.perception_outcome = {
        "views": {str(char_id): "You are in the Long Hall. Rope coils hang "
                                "from the rafters."},
        "observations": {},
        "episodes": {str(char_id): ""},
        "episode_meta": {str(char_id): {"gist": "", "entities": []}},
    }
    prepared = prepare_memory_commit(ctx)
    episodic = [m for m in prepared["memory_batch"]["prepared"]
                if m["kind"] == "episodic"]
    assert episodic == []
