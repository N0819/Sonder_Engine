"""Part C — demand-driven voice handoff (DESIGN_BACKGROUND_PRESENTATION §C).

The voice tier voices only whom an authored mind's own conduct calls on this
beat: addressed, owed a reply, acted toward an authored mind last beat, or
emerged from a crowd this beat. Co-presence, salience and recency stopped
being triggers (their subtraction is pinned in test_background_react.py and
test_crowds.py); this file pins the triggers themselves, the overflow order,
the addressee guarantee with its chorus degradation, and §C3's K — a body
neither addressed nor addressing for `PRESENTED_IDLE_BEATS` returns to
ground losslessly.

K was MEASURED, per the note's own instruction (set it from persisted
traces, not guesses): over every live chat's `background_presences` ledger
(2026-08-27 engine.db, 71 chats, 244 re-engagement gaps), 25/28 resumptions
after real inattention came within 4 idle beats — the ~90% knee.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from world import charter_crowd, crowds


def _mk_ctx(temp_db, presences=None, cast_names=None, player_input="",
            scene=None, turn_idx=5):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Demand", "", time.time()))
    for name in (cast_names or []):
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
    temp_db.wset(cid, "scene", scene if scene is not None else {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    if presences is not None:
        temp_db.wset(cid, "background_presences", presences)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, player_input, time.time()))
    return PipelineContext(
        chat=ChatData(id=cid, name="Demand", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=cast, input=player_input)


def _charter_scene(temp_db, ctx, *, window_acts=None, figures=True):
    """The Bridge fixture, five guild bodies with the player's cast figure."""
    scene = {
        "location": "Low Town",
        "rooms": {"square": {"name": "Square", "size": "large"}},
        "positions": {"Aldous": "square"},
        "entities": {}, "attire": {}, "overlays": {},
    }
    state = {
        "key": "guild", "upkeeps": {}, "priority": [],
        "posts": {"warden": {"place": "square", "serves": [],
                             "requires": {}}},
        "bodies": {
            "b1": {"name": "Marn", "place": "square", "available": True,
                   "competence": {}},
            "b2": {"name": "Etta", "place": "square", "available": True,
                   "competence": {}},
            "b3": {"name": "Sable", "place": "square", "available": True,
                   "competence": {}},
            "b4": {"name": "Vane", "place": "square", "available": True,
                   "competence": {}},
        },
        "watch": {"warden": "b1"},
    }
    if figures:
        state["figures"] = {"Aldous": {"place": "square"}}
    if window_acts is not None:
        state["window_acts"] = window_acts
    temp_db.wset(ctx.chat.id, "scene", scene)
    temp_db.wset(ctx.chat.id, "charters",
                 {"items": {"guild": {"state": state}}})
    return scene


_QUIET = {"resolved_event": "The square goes on about its business.",
          "dialogue_log": []}


class TestTheFourTriggers:
    def test_an_owed_reply_qualifies_with_nothing_else(self, temp_db):
        """§C1.2, and §C3's no-tenure claim from the other side: the open
        exchange re-offers the presence through the debt, not through any
        history counter."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, presences={
            "Clerk": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [],
                      "mention_turns": [],
                      "pending_reply": {"from": "someone", "quote": "Well?",
                                        "turn": 4, "expires_turn": 6}},
        })
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == ["Clerk"]

    def test_a_charter_emerge_op_qualifies_its_body_this_beat(self, temp_db):
        """§C1.4. The op is only APPLIED at commit, after the background
        stage; the gate reads the provisional op so the emergence gets its
        voice on the beat the Director asked for it, not one beat late."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, presences={})
        _charter_scene(temp_db, ctx)
        dr = dict(_QUIET)
        dr["state_diff"] = {"crowd_ops": [{
            "op": "emerge", "who": "Etta",
            "crowd_id": crowds.charter_crowd_uid(
                ctx.chat.id, "guild", "square")}]}
        assert pick_background_reactors(ctx, dr, cap=1) == ["Etta"]

    def test_a_charter_act_toward_a_figure_qualifies_its_actor(self, temp_db):
        """§C1.3's substrate half: a window act whose ``other`` is a scene
        figure keyed by an authored name is the body turning toward that
        mind, and the one-window lag is the same one every reader of
        ``window_acts`` already tolerates."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, presences={}, cast_names=["Aldous"])
        _charter_scene(temp_db, ctx, window_acts=[
            {"actor": "b2", "act": "ask", "other": "Aldous", "subject": "",
             "place": "square", "at_hours": 1.0, "event": False}])
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == ["Etta"]

    def test_the_same_act_toward_a_stranger_is_not_a_trigger(self, temp_db):
        """The trigger is the authored mind in the exchange, not the act:
        crowd members asking each other things is Part A's chatter, not a
        voice demand."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, presences={}, cast_names=["Aldous"])
        _charter_scene(temp_db, ctx, window_acts=[
            {"actor": "b2", "act": "ask", "other": "b3", "subject": "",
             "place": "square", "at_hours": 1.0, "event": False}])
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == []

    def test_the_demand_pick_is_deterministic(self, temp_db):
        from persist.commit import pick_voice_demand
        ctx = _mk_ctx(temp_db, presences={}, cast_names=["Aldous"])
        _charter_scene(temp_db, ctx, window_acts=[
            {"actor": "b2", "act": "ask", "other": "Aldous", "subject": "",
             "place": "square", "at_hours": 1.0, "event": False}])
        first = pick_voice_demand(ctx, dict(_QUIET), cap=2)
        assert first == pick_voice_demand(ctx, dict(_QUIET), cap=2)


class TestOverflowAndTheAddresseeGuarantee:
    def test_overflow_order_is_addressed_then_owed_then_acting(self, temp_db):
        """§C3's ranking, pinned end to end through the public pick."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, player_input="Archivist, the ledger, now.",
                      presences={
            "Archivist": {"first_turn": 1, "last_turn": 4,
                          "dialogue_turns": [], "mention_turns": []},
            "Clerk": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [],
                      "mention_turns": [],
                      "pending_reply": {"from": "x", "quote": "?", "turn": 4,
                                        "expires_turn": 6}},
            "Porter": {"first_turn": 1, "last_turn": 4,
                       "dialogue_turns": [4], "mention_turns": [],
                       "engaged_turns": [4]},
        })
        picks = pick_background_reactors(ctx, dict(_QUIET), cap=3)
        assert picks == ["Archivist", "Clerk", "Porter"]
        # The ceiling truncates from the bottom of that order.
        assert pick_background_reactors(ctx, dict(_QUIET), cap=2) == [
            "Archivist", "Clerk"]

    def test_two_addressees_widen_a_cap_of_one(self, temp_db):
        """An addressee is NEVER silently dropped -- the one hard guarantee
        (§C3). The forced widening the flow-addressed pick always had now
        covers every spelling of an address."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(
            temp_db,
            player_input="Archivist, Porter -- both of you, with me.",
            presences={
                "Archivist": {"first_turn": 1, "last_turn": 4,
                              "dialogue_turns": [], "mention_turns": []},
                "Porter": {"first_turn": 1, "last_turn": 3,
                           "dialogue_turns": [], "mention_turns": []},
            })
        picks = pick_background_reactors(ctx, dict(_QUIET), cap=1)
        assert set(picks) == {"Archivist", "Porter"}


class TestTheChorus:
    def _address_the_square(self, temp_db):
        ctx = _mk_ctx(
            temp_db, presences={},
            player_input="Marn, Etta, Sable, Vane -- all of you, listen!")
        _charter_scene(temp_db, ctx)
        temp_db.wset(ctx.chat.id, "background_config",
                     {"max_reactors": 3, "scene_life": "off"})
        ctx.director_resolve = dict(_QUIET)
        return ctx

    def test_addressees_past_the_ceiling_answer_as_one_crowd(
            self, temp_db, monkeypatch):
        """§C3: four addressees against the hard ceiling of three means the
        address was to a crowd, and the answer is ONE chorus entry from the
        derived crowd -- deterministic, model-free, nobody dropped and
        nobody voiced badly."""
        import agents.background as background

        ctx = self._address_the_square(temp_db)

        def fail_if_called(*a, **k):
            raise AssertionError(
                "the chorus is deterministic; no model call may fire")

        monkeypatch.setattr(background, "_agent_json", fail_if_called)
        out = background.background_react(ctx, nonce=0)
        assert out["fired"] is True
        (entry,) = out["reactions"]
        assert entry["chorus"] is True
        assert entry["crowd_uid"] == crowds.charter_crowd_uid(
            ctx.chat.id, "guild", "square")
        assert set(entry["addressed"]) == {"Marn", "Etta", "Sable", "Vane"}
        assert "as one" in entry["action"]
        assert entry["dialogue_log_entry"] is None
        # The chorused members stay ground: selection is what persists a
        # record, and none of them was selected.
        assert out["selected"] == []

    def test_the_chorus_persists_nothing(self, temp_db, monkeypatch):
        import agents.background as background

        ctx = self._address_the_square(temp_db)
        monkeypatch.setattr(background, "_agent_json",
                            lambda *a, **k: {"reacts": False})
        background.background_react(ctx, nonce=0)
        assert not (temp_db.wget(ctx.chat.id, "background_presences", {})
                    or {})
        assert temp_db.wget(ctx.chat.id, "crowds", []) == []

    def test_a_chorused_addressees_reply_debt_discharges(self, temp_db):
        """The moment was theirs, answered together: the commit writer reads
        the chorus entry's `addressed` list into the discharge set without
        persisting a record for anyone in it."""
        from persist.commit import track_background_presences
        ctx = _mk_ctx(temp_db, presences={
            "Etta": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [],
                     "mention_turns": [],
                     "pending_reply": {"from": "x", "quote": "?", "turn": 4,
                                       "expires_turn": 6}},
        })
        ctx.director_resolve = dict(_QUIET)
        ctx["background_react"] = {
            "fired": True, "selected": [], "reactions": [{
                "name": "the wardens", "chorus": True,
                "addressed": ["Etta"], "dialogue_log_entry": None,
                "action": "the wardens answer together, as one crowd",
                "room": "square"}]}
        track_background_presences(ctx, nonce=0)
        ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
        (record,) = [r for r in ledger.values()
                     if r.get("name", "Etta") == "Etta" or True]
        assert "pending_reply" not in record


class TestReturnToGround:
    """§C3's K: `PRESENTED_IDLE_BEATS` idle beats end a body's individual
    presentation -- and nothing else. The record keeps its history, chatter
    attribution keeps the name, and Charter never stopped simulating."""

    def test_presented_lapses_and_engagement_refreshes(self):
        rec = {"first_turn": 1, "dialogue_turns": [1, 6],
               "addressed_turns": [2], "mention_turns": [9]}
        k = charter_crowd.PRESENTED_IDLE_BEATS
        assert charter_crowd.engaged_turn(rec) == 6
        assert charter_crowd.presented(rec, 6 + k - 1)
        assert not charter_crowd.presented(rec, 6 + k)
        # A mention is salience, not engagement: turn 9's mention above must
        # not have counted, or salience would be a presentation claim again.
        assert charter_crowd.engaged_turn({"mention_turns": [9]}) is None

    def test_a_lapsed_record_returns_its_body_to_the_crowd(self, temp_db):
        """Membership subtracts PRESENTATION, not recognition: the crowd
        counts the body again while `known_bodies` -- what licenses naming
        them in chatter -- keeps it forever. A name once learned is never
        unlearned."""
        from agents.common import chatter_inputs
        ctx = _mk_ctx(temp_db, presences={
            "Etta": {"name": "Etta", "nature": "person", "first_turn": 1,
                     "dialogue_turns": [1], "mention_turns": [],
                     "addressed_turns": [],
                     "charter_refs": [{"charter": "guild", "body": "b2"}]},
        })
        scene = _charter_scene(temp_db, ctx)
        k = charter_crowd.PRESENTED_IDLE_BEATS
        fresh = chatter_inputs(ctx.chat.id, scene, turn_idx=2)["charters"][0]
        assert "b2" not in charter_crowd.members_of(fresh, "square")
        lapsed = chatter_inputs(
            ctx.chat.id, scene, turn_idx=1 + k)["charters"][0]
        assert "b2" in charter_crowd.members_of(lapsed, "square")
        assert "b2" in lapsed["known_bodies"]
        # Lossless: the reads wrote nothing and deleted nothing.
        record = next(iter(temp_db.wget(
            ctx.chat.id, "background_presences", {}).values()))
        assert record["dialogue_turns"] == [1]

    def test_a_lapsed_body_re_emerges_into_the_same_record(self, temp_db):
        """Re-voicing later is cheap and consistent: the pick offers the
        body again once its presentation lapsed, and the overlay resolves by
        charter ref into the record it already has -- one person, one
        history, however many times they step out."""
        from persist.commit import emerge_from_charter_crowd
        ctx = _mk_ctx(temp_db, presences={})
        scene = _charter_scene(temp_db, ctx)
        cid = ctx.chat.id
        name, reason = emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=7)
        assert name == "Etta" and not reason
        k = charter_crowd.PRESENTED_IDLE_BEATS
        # Presented: a second emerge of the same person is refused.
        again, reason = emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=8)
        assert not again and "Etta" not in (again or "")
        # Lapsed: she is ground again, and stepping out lands in the SAME
        # record, refreshed, not a duplicate.
        name, reason = emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=7 + k)
        assert name == "Etta" and not reason
        ledger = temp_db.wget(cid, "background_presences", {})
        assert len(ledger) == 1
        record = next(iter(ledger.values()))
        assert record["last_turn"] == 7 + k


class TestTheActingFactIsWritten:
    def test_a_fired_line_aimed_at_an_authored_mind_writes_engaged_turns(
            self, temp_db):
        """`dialogue_turns` proves a presence spoke, to anyone; the §C1.3
        trigger needs to know an authored mind was IN the exchange, and the
        target lives on the entry, which does not survive into the record --
        so the writer records the aimed fact as `engaged_turns`."""
        from persist.commit import track_background_presences
        ctx = _mk_ctx(temp_db, presences={}, cast_names=["Aldous"])
        ctx.director_resolve = dict(_QUIET)
        ctx["background_react"] = {
            "fired": True, "selected": ["Etta"], "reactions": [{
                "name": "Etta", "action": "",
                "dialogue_log_entry": {
                    "speaker": "Etta", "exact_quote": '"Mind the step."',
                    "volume": "normal", "intended_target": "Aldous",
                    "tone": "", "visibility": "overt", "conceal_from": []}}]}
        track_background_presences(ctx, nonce=0)
        ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
        record = next(r for r in ledger.values()
                      if "Etta" in (r.get("name"), r.get("uid")))
        assert record["engaged_turns"] == [5]

    def test_an_unaimed_line_writes_no_engaged_turn(self, temp_db):
        from persist.commit import track_background_presences
        ctx = _mk_ctx(temp_db, presences={}, cast_names=["Aldous"])
        ctx.director_resolve = dict(_QUIET)
        ctx["background_react"] = {
            "fired": True, "selected": ["Etta"], "reactions": [{
                "name": "Etta", "action": "",
                "dialogue_log_entry": {
                    "speaker": "Etta", "exact_quote": '"Fine morning."',
                    "volume": "normal", "intended_target": None,
                    "tone": "", "visibility": "overt", "conceal_from": []}}]}
        track_background_presences(ctx, nonce=0)
        ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
        record = next(r for r in ledger.values()
                      if "Etta" in (r.get("name"), r.get("uid")))
        assert not record.get("engaged_turns")


class TestTheManagerIsDemandDriven:
    def test_the_manager_roster_is_the_demand_set(self, temp_db):
        """§C2 resolved: `max_managed` stops selecting -- a co-present
        presence with no trigger is not handed to the voice call, however
        recently active, and the owed one is."""
        import agents.background as background
        scene = {
            "location": "Inn", "time": "night", "player_room": "taproom",
            "rooms": {"taproom": {"name": "Taproom"}},
            "positions": {"Barkeep": "taproom", "Local": "taproom"},
            "entities": {
                "Barkeep": {"name": "Barkeep", "kind": "person"},
                "Local": {"name": "Local", "kind": "person"}},
            "attire": {}, "overlays": {},
        }
        ctx = _mk_ctx(temp_db, scene=scene, presences={
            "Barkeep": {"first_turn": 1, "last_turn": 2,
                        "dialogue_turns": [], "mention_turns": [],
                        "pending_reply": {"from": "x", "quote": "?",
                                          "turn": 4, "expires_turn": 6}},
            "Local": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [4],
                      "mention_turns": [4]},
        })
        ctx.director_resolve = dict(_QUIET)
        managed, _room = background.managed_presences(ctx, None)
        assert {n for _t, n, _r, _rm in managed} == {"Barkeep", "Local"}
        demanded = background._demanded_presences(
            ctx, ctx.director_resolve, managed, ceiling=6)
        assert [n for _t, n, _r, _rm in demanded] == ["Barkeep"]
