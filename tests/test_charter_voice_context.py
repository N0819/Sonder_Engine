"""What reaches a Charter voice, and what is withheld from it.

Measured on the Harrowmere playtest (chat 2 of the traversal worktree's
scratch DB, 40 turns, 2026-09-02):

* `commit_charter_observations` returned ``acquired: 0`` on every turn
  against 109-345 opportunities, with the player speaking to the reeve in
  the reeve's own hall. The commit domain handed `ingest_public_evidence`
  the prepared-commit ENVELOPE (``{"scene": ..., "mapping": ...}``) where a
  scene belonged, `room_of(envelope, actor)` answered None for every actor,
  and every body failed reception, silently.
* `state.figures` was ``{}`` in all eight charters: the co-presence channel
  (`charter_figure.sight_figures`) ran only inside offscreen windows, so a
  body the player stood beside for a whole conversation held nothing about
  them unless it greeted them, and then under the stranger label as the
  claim's KEY -- twelve claims about "the slight woman", none about the
  person.
* Every piece of news any body held was stamped ``hours_ago`` 1,728,720:
  ``world_events.occurred_at`` counts simulation seconds, ``clock_hours``
  counts charter hours, and the carrier rail landed one in the other.

Each test here is the class, not the chat.
"""

from __future__ import annotations

import json
import time

from agents.common import _unknown_actor_label, scene_figures
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_charter_observations
from story.character_schema import default_character_data
from world import charter_runtime
from world.charter import normalize_charter, scene_ledger, seed_needs
from world.charter_log import (ACQUAINTANCE_BRING_UP_CAP, NEWS_BRING_UP_CAP,
                               own_state_of)
from world.charter_news import (charter_hours_of, claim_from_report,
                                report_from_claim, sim_seconds_of)

PLAYER = "Wren Ashby"
LOOK = "A slight woman in a dust-coloured travelling coat."


def _label():
    return _unknown_actor_label(PLAYER, LOOK)


def _scene(player_room="hall"):
    return {
        "location": "Harrowmere",
        "rooms": {
            "hall": {"name": "Reeve's Hall", "adjacent": [
                {"to": "square", "barrier": "open_door", "distance": "short"},
                {"to": "cellar", "barrier": "wall"}]},
            "square": {"name": "Market Square", "adjacent": [
                {"to": "hall", "barrier": "open_door", "distance": "short"}]},
            "cellar": {"name": "Cellar", "adjacent": [
                {"to": "hall", "barrier": "wall"}]},
        },
        "positions": {PLAYER: player_room},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _town():
    charter = normalize_charter({
        "key": "town",
        "bodies": {
            "reeve": {"name": "Ysra", "title": "Reeve", "place": "hall"},
            "clerk": {"name": "Tam", "place": "hall"},
            "trader": {"name": "Pell", "place": "square"},
            "cooper": {"name": "Bram", "place": "cellar"},
        },
    })
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _ctx(temp_db, *, scene=None, cast_names=(), turn_idx=5):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        (PLAYER, json.dumps({"name": PLAYER, "appearance": LOOK,
                             "senses": "ordinary senses"})))
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Voice context", persona_id, "", time.time()))
    for name in cast_names:
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower().replace(' ', '_')}"))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    scene = scene if scene is not None else _scene()
    temp_db.wset(cid, "scene", scene)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Voice context", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=turn_idx,
                      player_input="", created=time.time()),
        cast=cast, input="")
    return ctx, scene


def _speech(actor=PLAYER, **updates):
    row = {
        "source_id": f"speech:{actor}:0", "kind": "speech", "actor": actor,
        "exact_quote": '"I have a letter for the reeve. Which of you is he?"',
        "target": "Reeve Ysra", "volume": "normal", "visibility": "overt",
        "conceal_from": [], "salience": 0.7, "speech_acts": [],
    }
    row.update(updates)
    return row


def _minds(cid):
    return charter_runtime.registry_for(cid)["items"]["town"]["state"]["minds"]


# ---------------------------------------------------------------------------
# The commit domain hands the runtime a scene, not the envelope around one.
# ---------------------------------------------------------------------------

class TestTheEnvelopeIsUnwrapped:
    def test_evidence_lands_through_the_prepared_envelope(self, temp_db):
        """The exact shape `_commit_all_locked` passes -- and the shape
        that yielded zero for forty turns."""
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        ctx.director_resolve = {"public_evidence": [_speech()]}

        result = commit_charter_observations(
            ctx, {"scene": scene, "mapping": {}, "memories": {}})

        assert result["acquired"] >= 2, result
        assert result["unplaced"] == []
        held = _minds(ctx.chat.id)
        assert any(c.get("kind") == "news" for c in held["reeve"].values())
        assert any(c.get("kind") == "news" for c in held["clerk"].values())

    def test_a_bare_scene_is_still_accepted(self, temp_db):
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        ctx.director_resolve = {"public_evidence": [_speech()]}

        result = commit_charter_observations(ctx, scene)

        assert result["acquired"] >= 2

    def test_an_actor_the_scene_places_nowhere_is_said_out_loud(self, temp_db):
        """A silent zero is the class. An actor with no room reaches nobody,
        and the domain says which actor and why instead of counting
        opportunities it never had."""
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        ctx.director_resolve = {
            "public_evidence": [_speech(actor="Nobody Placed")]}

        result = commit_charter_observations(ctx, {"scene": scene})

        assert result["acquired"] == 0
        assert result["unplaced"] == ["Nobody Placed"]
        assert any("Nobody Placed" in w and "nowhere" in w
                   for w in ctx.warnings)


# ---------------------------------------------------------------------------
# A body remembers the bodies it has met, the player being one.
# ---------------------------------------------------------------------------

class TestStandingInTheRoomIsSeen:
    def test_bodies_in_the_room_come_to_know_the_figure(self, temp_db):
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})

        result = commit_charter_observations(ctx, {"scene": scene})

        assert result["sighted"] == 2, result
        held = _minds(ctx.chat.id)
        for body in ("reeve", "clerk"):
            claim = held[body][PLAYER]
            assert claim["kind"] == "figure"
            assert claim["place"] == "hall"
            assert claim["heard_from"] is None
            # The claim is keyed by the person and carries what was SEEN.
            assert claim["surface"]["label"] == _label()
            assert claim["surface"]["label"] != PLAYER

    def test_a_body_in_another_room_sees_nothing(self, temp_db):
        """Adversarial: no channel, no claim. The trader across the open
        door and the cooper behind the wall are equally not in the room."""
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})

        commit_charter_observations(ctx, {"scene": scene})

        held = _minds(ctx.chat.id)
        assert PLAYER not in (held.get("trader") or {})
        assert PLAYER not in (held.get("cooper") or {})

    def test_a_second_visit_refreshes_without_a_second_write(self, temp_db):
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        commit_charter_observations(ctx, {"scene": scene})
        writes = []
        original = charter_runtime.save_registry

        def counted(*args, **kwargs):
            writes.append(1)
            return original(*args, **kwargs)

        import pytest
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(charter_runtime, "save_registry", counted)
            again = commit_charter_observations(ctx, {"scene": scene})

        # Fresh first-hand claim at this very place: nothing to refresh, so
        # the private parse and the save are not paid.
        assert again["sighted"] == 0
        assert writes == []

    def test_the_cast_are_figures_too(self, temp_db):
        """The class is every scene-owned mind, not the player."""
        ctx, scene = _ctx(temp_db, cast_names=["Dorel Vance"])
        scene["positions"]["Dorel Vance"] = "square"
        temp_db.wset(ctx.chat.id, "scene", scene)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})

        commit_charter_observations(ctx, {"scene": scene})

        held = _minds(ctx.chat.id)
        assert held["trader"]["Dorel Vance"]["kind"] == "figure"
        assert "Dorel Vance" not in held["reeve"]

    def test_figures_are_the_scene_owned_minds_in_their_rooms(self, temp_db):
        ctx, scene = _ctx(temp_db, cast_names=["Dorel Vance"])
        figures = scene_figures(ctx.chat, ctx.cast, scene)
        keyed = {f["key"]: f for f in figures}
        assert keyed[PLAYER]["place"] == "hall"
        assert keyed[PLAYER]["label"] == _label()
        # Not placed by the scene: known, nowhere a body can see.
        assert keyed["Dorel Vance"]["place"] == ""
        # Recognition earns the name and nothing else does.
        named = scene_figures(ctx.chat, ctx.cast, scene, recognized={PLAYER})
        assert {f["key"]: f["label"] for f in named}[PLAYER] == PLAYER


class TestTheSliceSaysMetBeforeAndNeverTheName:
    def test_first_meeting_is_a_stranger_and_a_return_is_met(self, temp_db):
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        figures = [{"key": PLAYER, "label": _label()}]

        first = charter_runtime.presence_view(
            ctx.chat.id, "hall", "Reeve Ysra", figures=figures)[0]["presence"]
        assert _label() in first["strangers_here"]
        assert _label() not in first["knows_here"]

        commit_charter_observations(ctx, {"scene": scene})

        back = charter_runtime.presence_view(
            ctx.chat.id, "hall", "Reeve Ysra", figures=figures)[0]["presence"]
        assert _label() not in back["strangers_here"]
        entry = back["knows_here"][_label()]
        assert entry["figure"] is True
        assert entry["met"] is True
        assert entry["believes_present"] is True
        assert entry["last_seen_hours_ago"] == 0.0

    def test_the_name_reaches_no_part_of_the_slice(self, temp_db):
        """Adversarial: the mind keys the encounter by the name; the voiced
        slice renders it under the observer's label everywhere -- claim
        keys, judgment subjects, affordance targets, news text."""
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        ctx.director_resolve = {"public_evidence": [_speech()]}
        commit_charter_observations(ctx, {"scene": scene})

        view = charter_runtime.presence_view(
            ctx.chat.id, "hall", "Reeve Ysra",
            figures=[{"key": PLAYER, "label": _label()}])[0]

        assert PLAYER not in json.dumps(view["presence"])
        # The only place the name survives is the affordance row's `key`,
        # which the voice path strips before the model sees the rows and
        # the commit gate resolves the echo by.
        assert PLAYER not in json.dumps([
            {k: v for k, v in row.items() if k != "key"}
            for row in view["action_instances"]])
        news = view["presence"]["can_bring_up"]
        assert news and news[0]["claim"].startswith(_label() + " said")
        assert news[0]["about"] == _label()
        greet = [row for row in view["action_instances"]
                 if row["other"] == _label()]
        assert greet and all(row["key"] == PLAYER for row in greet)

    def test_recognition_renders_the_name_and_only_then(self, temp_db):
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        commit_charter_observations(ctx, {"scene": scene})

        view = charter_runtime.presence_view(
            ctx.chat.id, "hall", "Reeve Ysra",
            figures=[{"key": PLAYER, "label": PLAYER}])[0]

        assert view["presence"]["knows_here"][PLAYER]["met"] is True

    def test_a_greet_echo_lands_on_the_person_not_the_label(self, temp_db):
        """The model echoes the rendered label; the offer row that licensed
        it carries the key, and the claim the greeting leaves is keyed by
        the person -- the same subject sighting and evidence keep."""
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        view = charter_runtime.presence_view(
            ctx.chat.id, "hall", "Reeve Ysra",
            figures=[{"key": PLAYER, "label": _label()}])[0]
        greet = next(row for row in view["action_instances"]
                     if row["act"] == "greet" and row["other"] == _label())

        landed = charter_runtime.apply_presence_conduct(
            ctx.chat.id, "Reeve Ysra", {"act": "greet", "other": _label()},
            record={"charter_refs": [{"charter": "town", "body": "reeve"}]},
            allowed=[greet], place="hall")

        assert not landed.get("refused"), landed
        held = _minds(ctx.chat.id)["reeve"]
        assert held[PLAYER]["kind"] == "figure"
        assert held[PLAYER]["surface"]["label"] == _label()
        assert _label() not in held


# ---------------------------------------------------------------------------
# News reaches a voice through a channel, stamped on the body's own clock.
# ---------------------------------------------------------------------------

class TestNewsReachesAVoice:
    def test_speech_through_a_wall_reaches_nobody(self, temp_db):
        """Adversarial: the cooper behind the wall may not voice what the
        player said in the hall; the trader through the open door may."""
        ctx, scene = _ctx(temp_db)
        charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
        ctx.director_resolve = {"public_evidence": [_speech()]}

        commit_charter_observations(ctx, {"scene": scene})

        cooper = charter_runtime.presence_view(
            ctx.chat.id, "cellar", "Bram")[0]["presence"]
        trader = charter_runtime.presence_view(
            ctx.chat.id, "square", "Pell")[0]["presence"]
        assert cooper["can_bring_up"] == []
        assert trader["can_bring_up"] and "letter" in trader["can_bring_up"][0]["claim"]

    def test_the_bring_up_caps_are_named(self):
        assert NEWS_BRING_UP_CAP == 3
        assert ACQUAINTANCE_BRING_UP_CAP == 4

    def test_a_carrier_envelope_lands_on_the_charter_clock(self):
        anchor = {"clock_hours": 720.0, "elapsed_seconds": 0.0}
        assert charter_hours_of(-1728000.0, anchor) == 240.0
        assert sim_seconds_of(240.0, anchor) == -1728000.0
        # Passes through untouched with no anchor, as before.
        assert charter_hours_of(-1728000.0, None) == -1728000.0

        report = {"world_event_id": "event:1", "claim": "the market ran out",
                  "kind": "consequence", "occurred_at": -1728000.0,
                  "provenance": "witnessed_surface", "retellings": 0}
        claim = claim_from_report(report, 720.0, anchor=anchor)
        assert claim["happened_at"] == 240.0
        back = report_from_claim(claim, anchor=anchor)
        assert back["occurred_at"] == -1728000.0

    def test_hours_ago_in_the_slice_is_the_body_own_hours(self, temp_db):
        ctx, scene = _ctx(temp_db)
        state = _town()
        state["clock_hours"] = 720.0
        charter_runtime.save_registry(ctx.chat.id, {"items": {"town": {
            "state": state, "last_elapsed_seconds": 0.0}}})

        charter_runtime.save_carrier_state(
            ctx.chat.id,
            {"charter_ref": {"charter": "town", "body": "reeve"}},
            {"carried_reports": [{
                "world_event_id": "event:1", "claim": "the market ran out",
                "kind": "consequence", "occurred_at": -1728000.0,
                "provenance": "told", "told_by": "a carter",
                "retellings": 1}]})

        slice_ = charter_runtime.presence_view(
            ctx.chat.id, "hall", "Reeve Ysra")[0]["presence"]
        assert slice_["can_bring_up"][0]["hours_ago"] == 480.0
        # And back out onto the rail in the rail's own seconds.
        entry = next(e for e in charter_runtime.carrier_entries(ctx.chat.id)
                     if e["uid"] == "reeve")
        assert entry["state"]["carried_reports"][0]["occurred_at"] == -1728000.0


class TestHowTheBodyIsFaring:
    def test_own_state_reads_needs_and_feel(self):
        needs = {"rest": {"level": 0.3, "floor": 0.15},
                 "sustenance": {"level": 0.9, "floor": 0.1}}
        feel = {"hedonic": {"pain": 0.4, "pleasure": 0.0, "charge": 0.0},
                "stress": {"activation": 0.0, "strain": 0.35, "load": 0.1,
                           "overloaded": False}}
        state = own_state_of(needs, feel)
        assert state["pressed"] == 0.7
        assert state["worst_need"] == "rest"
        assert state["unmet"] == 0.0
        assert state["hedonic"]["pain"] == 0.4
        assert state["stress"]["strain"] == 0.35

    def test_a_breach_and_a_quiet_interior(self):
        needs = {"rest": {"level": 0.05, "floor": 0.15}}
        state = own_state_of(needs, {"hedonic": {"pain": 0.001},
                                     "stress": {"strain": 0.0}})
        assert state["unmet"] == 0.1
        assert "hedonic" not in state and "stress" not in state

    def test_the_slice_carries_it(self, temp_db):
        ctx, scene = _ctx(temp_db)
        state = _town()
        state["needs"]["reeve"]["rest"]["level"] = 0.2
        charter_runtime.save_registry(ctx.chat.id, {"town": state})
        slice_ = charter_runtime.presence_view(
            ctx.chat.id, "hall", "Reeve Ysra")[0]["presence"]
        assert slice_["own_state"]["worst_need"] == "rest"
        assert slice_["own_state"]["pressed"] == 0.8
        ledger = scene_ledger(state, "hall")
        assert ledger["presences"]["reeve"]["own_state"]["pressed"] == 0.8


# ---------------------------------------------------------------------------
# The per-presence voice path hands the slice over in the presence's labels.
# ---------------------------------------------------------------------------

def test_the_voice_payload_says_met_before_without_the_name(temp_db,
                                                             monkeypatch):
    import agents.background as background

    ctx, scene = _ctx(temp_db)
    scene["entities"]["reeve_ysra"] = {
        "name": "Reeve Ysra", "kind": "person", "position": "hall"}
    scene["positions"]["Reeve Ysra"] = "hall"
    temp_db.wset(ctx.chat.id, "scene", scene)
    charter_runtime.save_registry(ctx.chat.id, {"town": _town()})
    temp_db.wset(ctx.chat.id, "background_presences", {
        "Reeve Ysra": {"first_turn": 1, "last_turn": 4,
                       "dialogue_turns": [2], "mention_turns": [],
                       "engaged_turns": [4],
                       "sketch": {"role_hint": "reeve", "station_room": "hall"},
                       "charter_refs": [{"charter": "town", "body": "reeve"}]},
    })
    # Yesterday's visit: the reeve has seen this person before.
    commit_charter_observations(ctx, {"scene": scene})
    ctx.director_resolve = {"resolved_event": "The stranger waits.",
                            "dialogue_log": []}
    captured = {}

    def capture(role, name, system, payload, **kw):
        captured["payload"] = payload
        return {"reacts": False, "dialogue_log_entry": None, "action": ""}

    monkeypatch.setattr(background, "_agent_json", capture)
    background.background_react(ctx, nonce=0)

    context = captured["payload"]["institutional_context"]
    assert context, captured["payload"]
    slice_ = context[0]["presence"]
    assert slice_["knows_here"][_label()]["met"] is True
    assert "own_state" in slice_
    assert PLAYER not in json.dumps(captured["payload"])
