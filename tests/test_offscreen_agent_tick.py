"""The paid `character_agent` rung: one reduced off-screen turn.

The rung is the highest-fidelity purchase in the off-screen design and the
easiest to build wrong in exactly two ways, both named in the roadmap: a mind
that knows something no channel delivered ("how did he know that"), and a
background job that lands the same work twice because a reroll or restore
moved the world underneath it. Every test here is one of those two failures,
or one of the cheaper ones beside them — a call spent on a character who gave
no reason, a consequence minted by anything other than the Director, prose
smuggled through a state field.
"""

from __future__ import annotations

import json
import threading
import time
import types

import offscreen

_EPOCH = "epoch_agent_test"

_SCENE = {
    "location": "Harbor",
    "rooms": {
        "gate": {"adjacent": [{"to": "yard", "barrier": "open"}]},
        "yard": {"adjacent": []},
    },
    "positions": {},
}


class _Chat(dict):
    @property
    def id(self):
        return self["id"]


def _ctx(cid, idx=5):
    return types.SimpleNamespace(
        chat=_Chat({"id": cid, "persona_id": None}),
        turn=types.SimpleNamespace(idx=idx, id=1, frame_id=None))


def _chat(db, *, offscreen_life="character_agent", ladder="ceiling",
          cap=3, turn_idx=5):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Agent tick", "", time.time()))
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
          "VALUES(?,?,?,?)", (cid, turn_idx, "", time.time()))
    db.wset(cid, "dialogue_config", {"offscreen_life": offscreen_life,
                                     "max_offscreen_actors": cap})
    db.wset(cid, "living_world", {"antagonist_ladder": ladder})
    db.wset(cid, "offscreen_epoch", {"epoch_id": _EPOCH, "turn": turn_idx,
                                     "sequence": 1})
    db.wset(cid, "scene", _SCENE)
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 7200.0})
    return cid


def _char(db, cid, name="Mora", uid="mora_uid", *, opted=True, state=None,
          plan=False):
    sheet = json.dumps({
        "identity": {"name": name, "uid": uid},
        "simulation": {"tier": "major", "offscreen_agent": opted},
    })
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, sheet, "{}", time.time()))
    if state is None:
        state = {"carried_reports": [{
            "world_event_id": "evt_bell", "claim": "the bell rang at the gate",
            "acquired_turn": 4,
        }]}
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,?,?)", (cid, char_id, "dormant", json.dumps(state)))
    if plan:
        db.wset(cid, "offscreen_plans", [{
            "plan_id": "p_gate", "actor_id": uid, "actor_display": name,
            "char_id": char_id, "objective": "bar the gate",
            "status": "active", "stage_index": 0,
            "stages": [{"stage_id": "s1", "trigger": {"due_at": 1.0},
                        "effect": None},
                       {"stage_id": "s2", "trigger": {"due_at": 2.0},
                        "effect": None}],
            "history": [{"event": "opened", "turn": 1}],
        }])
    return char_id


_ATTEMPT = {"attempt": "bar the north gate", "toward": "the gate",
            "plan_op": "keep", "plan_id": ""}
_VERDICT = {"outcome": "success", "moved_to": "gate", "consequence": None,
            "advance_plan": True}


def _stub_models(monkeypatch, attempt=None, verdict=None, capture=None):
    """One dispatcher for both calls, keyed on each call's own system text."""
    import providers

    calls = capture if capture is not None else []

    def _complete(role, sys, user, **kw):
        calls.append({"role": role, "sys": sys, "user": user})
        if sys == offscreen._AGENT_ATTEMPT_SYS:
            out = attempt if attempt is not None else _ATTEMPT
        elif sys == offscreen._AGENT_ADJUDICATE_SYS:
            out = verdict if verdict is not None else _VERDICT
        else:
            raise AssertionError(f"unexpected model call: {sys[:60]}")
        return json.dumps(out)

    monkeypatch.setattr(providers, "chat_complete", _complete)
    return calls


def _run_scheduled(monkeypatch, cid, ctx=None, epoch=None):
    """Schedule, then run the captured producer exactly as jobs._run would."""
    import jobs

    captured = {}

    def _capture(chat_id, key, fn, base_turn=None):
        captured["key"] = key
        captured["fn"] = fn
        captured["job"] = types.SimpleNamespace(cancelled=threading.Event(),
                                                as_dict=lambda: {})
        return captured["job"]

    monkeypatch.setattr(jobs, "submit", _capture)
    epoch = epoch if epoch is not None else {"opportunity": True,
                                             "epoch_id": _EPOCH}
    job = offscreen.schedule_agent_ticks(ctx or _ctx(cid), epoch)
    if job is not None:
        captured["result"] = captured["fn"](captured["job"])
    captured["epoch"] = epoch
    captured["job_returned"] = job
    return captured


def _land(db, cid, char_id, *, proposal=None, verdict=None, base_turn=5,
          epoch_id=_EPOCH, prepared=None):
    """Land directly, the way a second in-flight job's producer would —
    landing must not depend on the subject still being a candidate, because
    the first landing is precisely what spends the candidacy."""
    entry = {"id": "mora_uid", "display": "Mora", "char_id": char_id,
             "sheet": {}, "state": {}}
    return offscreen.land_agent_tick(
        cid, entry, proposal or dict(_ATTEMPT), verdict or dict(_VERDICT),
        base_turn=base_turn, turn_id=1, epoch_id=epoch_id, frame_id=None,
        scene=_SCENE, clock={"elapsed_seconds": 7200.0},
        prepared_memories=prepared)


class TestTheGatesFailTowardNotSpending:
    def test_a_character_existing_is_not_a_reason(self, temp_db, monkeypatch):
        """The roadmap's second safeguard verbatim: no call occurs merely
        because a character exists. An opted-in dormant mind with no active
        plan and no fresh evidence must cost nothing."""
        cid = _chat(temp_db)
        _char(temp_db, cid, state={})
        calls = _stub_models(monkeypatch)
        captured = _run_scheduled(monkeypatch, cid)
        assert captured["job_returned"] is None
        assert captured["epoch"]["agent_skip"] == "no_private_reason"
        assert calls == []

    def test_the_ladder_gate_composes_both_axes(self, temp_db, monkeypatch):
        """`living_world_allows(..., "ceiling")` already folds the chat's
        `offscreen_life` ceiling through LIVING_WORLD_REQUIRES; a second
        spelling of that rule here would drift. A chat whose off-screen
        ceiling is only `stochastic` must not run the paid rung, however the
        antagonist ladder is set."""
        cid = _chat(temp_db, offscreen_life="stochastic")
        _char(temp_db, cid)
        calls = _stub_models(monkeypatch)
        captured = _run_scheduled(monkeypatch, cid)
        assert captured["job_returned"] is None
        assert captured["epoch"]["agent_opportunity"] is False
        assert calls == []

    def test_no_epoch_means_no_job(self, temp_db, monkeypatch):
        """One base turn, frame and epoch guard every job — a tick minted
        outside a world epoch would have no identity for the landing guards
        to check, and a reroll could not recognise its double."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        _stub_models(monkeypatch)
        assert offscreen.schedule_agent_ticks(
            _ctx(cid), {"opportunity": False}) is None
        epoch = {"opportunity": True, "epoch_id": ""}
        assert offscreen.schedule_agent_ticks(_ctx(cid), epoch) is None
        assert epoch["agent_skip"] == "missing_epoch_id"

    def test_max_offscreen_actors_is_a_hard_cap(self, temp_db, monkeypatch):
        """The cap survives as a HARD bound on the paid rung: three eligible
        candidates against a cap of one is one reduced turn — two model
        calls — not three."""
        cid = _chat(temp_db, cap=1)
        for i in range(3):
            _char(temp_db, cid, name=f"C{i}", uid=f"c{i}_uid")
        calls = _stub_models(monkeypatch)
        captured = _run_scheduled(monkeypatch, cid)
        assert captured["epoch"]["agent_candidates"] == 1
        assert len(calls) == 2

    def test_the_job_key_is_the_epoch(self, temp_db, monkeypatch):
        """`jobs.submit` dedupes on (chat, key); a key that did not carry the
        epoch would let one epoch's reroll twin run beside the original as a
        second job instead of joining it."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        _stub_models(monkeypatch)
        captured = _run_scheduled(monkeypatch, cid)
        assert captured["key"] == f"offscreen_agent:{_EPOCH}"


class TestTheFirewall:
    def test_the_character_call_carries_only_the_private_context(
            self, temp_db, monkeypatch):
        """The producer is the step tempted to pass the scene along for
        convenience, and that is the whole tier's named failure: "how did he
        know that". The character call's payload must parse back to the
        `agent_context` allowlist and nothing beside it."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        calls = _stub_models(monkeypatch)
        _run_scheduled(monkeypatch, cid)
        character_call = next(
            c for c in calls if c["sys"] == offscreen._AGENT_ATTEMPT_SYS)
        payload = json.loads(character_call["user"])
        assert set(payload) <= set(offscreen.AGENT_CONTEXT_KEYS)
        blob = character_call["user"].casefold()
        for forbidden in ("player", "position", "rooms_available", "yard"):
            assert forbidden not in blob

    def test_the_director_alone_sees_the_map(self, temp_db, monkeypatch):
        """The split is the on-screen split: the Director owns causality and
        may see the world; the character may not. Rooms the subject never
        walked reach only the adjudication payload."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        calls = _stub_models(monkeypatch)
        _run_scheduled(monkeypatch, cid)
        director_call = next(
            c for c in calls if c["sys"] == offscreen._AGENT_ADJUDICATE_SYS)
        payload = json.loads(director_call["user"])
        assert payload["rooms_available"] == ["gate", "yard"]
        assert payload["attempt"] == _ATTEMPT["attempt"]

    def test_importance_never_becomes_prompt_content(self, temp_db,
                                                     monkeypatch):
        """Importance and distance select spend — the tier picks which model
        pays — and must never be readable from inside the fiction. A
        character who could tell how important they were would be reading
        the engine, not the world."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        calls = _stub_models(monkeypatch)
        _run_scheduled(monkeypatch, cid)
        assert calls, "the rung must actually have run for this to mean anything"
        for call in calls:
            blob = (call["sys"] + call["user"]).casefold()
            assert "importance" not in blob
            assert "tier" not in blob
        character_call = next(
            c for c in calls if c["sys"] == offscreen._AGENT_ATTEMPT_SYS)
        assert character_call["role"] == "character_major"


class TestOnlyTheDirectorChangesTheWorld:
    def test_a_character_volunteered_consequence_is_never_read(
            self, temp_db, monkeypatch):
        """A model may volunteer fields; the gate is the reader. A character
        call that helpfully attaches a `consequence` must find that nothing
        opens it — only the adjudication's verdict can mint, or the mind
        would author its own success after all."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        _stub_models(
            monkeypatch,
            attempt={**_ATTEMPT,
                     "consequence": {"what": "the gate falls", "where": "gate",
                                     "due_seconds": 60, "witnessed": "a crash"}},
            verdict={**_VERDICT, "consequence": None})
        _run_scheduled(monkeypatch, cid)
        rows = temp_db.q("SELECT * FROM scheduled_events WHERE chat_id=?",
                         (cid,))
        assert rows == []

    def test_the_verdicts_consequence_passes_the_shared_validator(
            self, temp_db, monkeypatch):
        """The one channel this rung changes the world through is
        `mint_consequences` — the same deterministic validator every other
        fuse passes. A consequence at a room the world does not contain is
        the 'quiet office' row and must be refused while the rest of the
        tick still lands."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid)
        _stub_models(
            monkeypatch,
            verdict={**_VERDICT,
                     "consequence": {"what": "the gate is barred",
                                     "where": "a quiet office",
                                     "due_seconds": 60,
                                     "witnessed": "the gate stands barred"}})
        _run_scheduled(monkeypatch, cid)
        assert temp_db.q("SELECT * FROM scheduled_events WHERE chat_id=?",
                         (cid,)) == []
        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)["state"])
        assert state["offscreen_agent"]["last_epoch_id"] == _EPOCH

    def test_an_adjudicated_consequence_lands_under_a_stable_id(
            self, temp_db, monkeypatch):
        """Stable ids are what make a replayed landing overwrite its own row
        instead of minting a sibling — the same property the reactive rung
        and the world-event spine already rely on."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid)
        verdict = {**_VERDICT,
                   "consequence": {"what": "the gate is barred",
                                   "where": "gate", "due_seconds": 60,
                                   "witnessed": "the gate stands barred"}}
        _stub_models(monkeypatch, verdict=verdict)
        _run_scheduled(monkeypatch, cid)
        rows = temp_db.q("SELECT * FROM scheduled_events WHERE chat_id=?",
                         (cid,))
        assert len(rows) == 1
        # Replay after the stamp was rolled back: same id, same single row.
        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)["state"])
        del state["offscreen_agent"]["last_epoch_id"]
        temp_db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
                   (json.dumps(state), cid, char_id))
        result = _land(temp_db, cid, char_id, verdict=verdict)
        assert result["landed"]
        again = temp_db.q("SELECT * FROM scheduled_events WHERE chat_id=?",
                          (cid,))
        assert len(again) == 1
        assert again[0]["event_id"] == rows[0]["event_id"]

    def test_movement_lands_in_the_own_trail_never_the_scene(
            self, temp_db, monkeypatch):
        """A dormant body holds no live position, and `scene.positions` has
        no off-screen write warrant (UNBUILT §1.20) — an adjudicated move
        becomes the character's own `last_known`, met as state at contact,
        and the scene blob stays untouched."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid)
        _stub_models(monkeypatch, verdict={**_VERDICT, "moved_to": "yard"})
        _run_scheduled(monkeypatch, cid)
        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)["state"])
        assert state["offscreen_agent"]["last_known"]["room"] == "yard"
        assert temp_db.wget(cid, "scene", {})["positions"] == {}

    def test_a_room_outside_the_world_fails_the_verdict_closed(
            self, temp_db, monkeypatch):
        """`moved_to` is validated where the data first goes wrong — the
        adjudication read — not compensated at landing. A verdict that walks
        a mind into 'a quiet office' is refused whole, and nothing lands."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid)
        _stub_models(monkeypatch,
                     verdict={**_VERDICT, "moved_to": "a quiet office"})
        captured = _run_scheduled(monkeypatch, cid)
        assert captured["result"] == {"landed": 0, "skipped": 1,
                                      "candidates": 1}
        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)["state"])
        assert "offscreen_agent" not in state


class TestStructuredStateNeverProse:
    def test_narration_cannot_ride_the_attempt_field(self, temp_db,
                                                     monkeypatch):
        """A field long enough to hold a sentence will be handed one. An
        attempt past the word bound is narration wearing a field name; the
        proposal fails closed and the Director is never even asked."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        calls = _stub_models(monkeypatch, attempt={
            "attempt": "spends the whole evening arguing with the "
                       "quartermaster about the missing shipment and "
                       "then bars the gate",
            "toward": "", "plan_op": "keep", "plan_id": ""})
        captured = _run_scheduled(monkeypatch, cid)
        assert captured["result"]["landed"] == 0
        assert all(c["sys"] != offscreen._AGENT_ADJUDICATE_SYS
                   for c in calls)
        assert temp_db.wget(cid, "offscreen_log", []) == []

    def test_the_log_record_is_composed_by_code(self, temp_db, monkeypatch):
        """Offscreen output is structured state, never narrator prose: the
        stored `tick` string is deterministic composition from the bounded
        fields, so the log cannot smuggle a sentence past the state shape."""
        cid = _chat(temp_db)
        _char(temp_db, cid)
        _stub_models(monkeypatch)
        _run_scheduled(monkeypatch, cid)
        log = temp_db.wget(cid, "offscreen_log", [])
        assert len(log) == 1
        event = log[0]["events"][0]
        assert event["state"] == {"doing": "bar the north gate",
                                  "at": "gate", "manner": ""}
        assert event["tick"] == offscreen.compose_agent_tick(
            "Mora", "bar the north gate", "success", "gate")
        assert "summary" not in event

    def test_the_autobiographical_memory_is_deterministic(
            self, temp_db, monkeypatch):
        """The returning character remembers its own off-screen experience —
        as a composition of the adjudicated fields, byte-stable so a reroll
        re-mints the SAME memory under the same event_key instead of a
        sibling the dedup cannot see."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid)
        _stub_models(monkeypatch)
        _run_scheduled(monkeypatch, cid)
        rows = temp_db.q(
            "SELECT * FROM memories WHERE chat_id=? AND char_id=?",
            (cid, char_id))
        assert len(rows) == 1
        assert rows[0]["content"] == offscreen.compose_agent_memory(
            "bar the north gate", "success")
        assert rows[0]["provenance"] == "witnessed"
        assert rows[0]["event_key"]


class TestRerollAndRestoreCannotDoubleLand:
    def test_landing_twice_for_one_epoch_lands_once(self, temp_db,
                                                    monkeypatch):
        """THE safeguard most likely to be got wrong. A reroll re-derives the
        same epoch id and resubmits the same job; whichever landing runs
        second must find the first one's stamp on the character's fresh
        state and discard itself — one memory, one log batch, one plan
        advance."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid, plan=True)
        _stub_models(monkeypatch)
        _run_scheduled(monkeypatch, cid)
        second = _land(temp_db, cid, char_id)
        assert second == {"landed": False, "reason": "already_landed"}
        assert len(temp_db.q(
            "SELECT * FROM memories WHERE chat_id=? AND char_id=?",
            (cid, char_id))) == 1
        assert len(temp_db.wget(cid, "offscreen_log", [])) == 1
        plan = temp_db.wget(cid, "offscreen_plans", [])[0]
        assert plan["stage_index"] == 1
        advances = [h for h in plan["history"]
                    if h.get("event") == "stage_advanced_offscreen"]
        assert len(advances) == 1

    def test_a_restored_checkpoint_discards_inflight_work(self, temp_db,
                                                          monkeypatch):
        """A checkpoint restore brings back the previous epoch record, so a
        tick computed against the discarded epoch describes a future that no
        longer happens. It must be dropped loudly, never committed — the
        engine's own precedent is the restore that silently undid a
        completed embedding rebuild."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid)
        temp_db.wset(cid, "offscreen_epoch", {"epoch_id": "epoch_before",
                                              "turn": 4})
        result = _land(temp_db, cid, char_id)
        assert result == {"landed": False, "reason": "epoch_changed"}
        assert temp_db.wget(cid, "offscreen_log", []) == []
        assert temp_db.q("SELECT * FROM memories WHERE chat_id=?",
                         (cid,)) == []

    def test_a_rollback_past_the_base_turn_discards(self, temp_db,
                                                    monkeypatch):
        """`base_turn` makes 'the world rolled back underneath the job'
        decidable; the landing acts on it rather than trusting the epoch
        alone, because a legacy world key can carry a stale epoch id while
        the turn ledger tells the truth."""
        cid = _chat(temp_db, turn_idx=3)
        char_id = _char(temp_db, cid)
        result = _land(temp_db, cid, char_id, base_turn=5)
        assert result == {"landed": False, "reason": "rolled_back"}
        assert temp_db.wget(cid, "offscreen_log", []) == []

    def test_a_replay_after_restore_is_replay_not_duplication(
            self, temp_db, monkeypatch):
        """The distinction the spec draws: a restored timeline may re-land
        the same tick — that is replay — but every durable row must come out
        single. Stable ids carry this even when a restore missed a ledger:
        the memory upserts on event_key, the log batch dedupes on its seed,
        and the plan's epoch-stamped history refuses a second advance."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid, plan=True)
        _stub_models(monkeypatch)
        _run_scheduled(monkeypatch, cid)
        # Simulate a restore that rolled back the state stamp but left the
        # other ledgers standing (the worst case for a naive re-landing).
        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)["state"])
        state["offscreen_agent"].pop("last_epoch_id")
        temp_db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
                   (json.dumps(state), cid, char_id))
        from memory import prepare_memories_batch
        from mechanics import stable_event_key

        prepared = prepare_memories_batch([{
            "chat_id": cid, "char_id": char_id, "turn_id": 1, "turn_idx": 5,
            "kind": "episodic", "provenance": "witnessed", "salience": 0.6,
            "content": offscreen.compose_agent_memory(
                "bar the north gate", "success"),
            "location": "gate",
            "event_key": stable_event_key(
                "offscreen_agent_memory", cid, None, _EPOCH, "mora_uid"),
            "frame_id": None,
        }])
        result = _land(temp_db, cid, char_id, prepared=prepared)
        assert result["landed"]
        assert len(temp_db.q(
            "SELECT * FROM memories WHERE chat_id=? AND char_id=?",
            (cid, char_id))) == 1
        assert len(temp_db.wget(cid, "offscreen_log", [])) == 1
        plan = temp_db.wget(cid, "offscreen_plans", [])[0]
        assert plan["stage_index"] == 1


class TestTheTierIsReachable:
    def test_the_commit_tail_schedules_the_rung(self):
        """Superseded by `tests/test_commit_tail_producers.py`.

        This asserted a substring of `inspect.getsource`, which cannot fail on a
        behavioural change: `job = None if True else schedule_agent_ticks(ctx)`
        keeps the text and never runs the call. The replacement drives a real
        commit and asserts the producer was reached.
        """
        import tests.test_commit_tail_producers  # noqa: F401  (the real cover)
    def test_end_to_end_from_epoch_to_landed_tick(self, temp_db, monkeypatch):
        """The whole reduced turn, in order: private context, one character
        call, one Director adjudication, one atomic landing — state stamp,
        own-trail movement, plan advance, log record, autobiographical
        memory — from nothing but an epoch and an opted-in mind with a
        reason."""
        cid = _chat(temp_db)
        char_id = _char(temp_db, cid, plan=True)
        calls = _stub_models(monkeypatch,
                             verdict={**_VERDICT, "moved_to": "yard"})
        captured = _run_scheduled(monkeypatch, cid)
        assert captured["epoch"]["agent_opportunity"] is True
        assert captured["epoch"]["agent_candidates"] == 1
        assert captured["epoch"]["agent_scheduled"] is True
        assert captured["result"] == {"landed": 1, "skipped": 0,
                                      "candidates": 1}
        assert [c["sys"] for c in calls] == [
            offscreen._AGENT_ATTEMPT_SYS, offscreen._AGENT_ADJUDICATE_SYS]
        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)["state"])
        agent_state = state["offscreen_agent"]
        assert agent_state["last_turn"] == 5
        assert agent_state["last_epoch_id"] == _EPOCH
        assert agent_state["last_known"]["room"] == "yard"
        assert temp_db.wget(cid, "offscreen_plans", [])[0]["stage_index"] == 1
        assert len(temp_db.wget(cid, "offscreen_log", [])) == 1
        memories = temp_db.q(
            "SELECT * FROM memories WHERE chat_id=? AND char_id=?",
            (cid, char_id))
        assert len(memories) == 1
        # And the evidence reason is now spent — the same carried report does
        # not buy a second tick — while the still-active plan legitimately
        # keeps the mind eligible: that is what advancing a plan means.
        remaining = offscreen.full_agent_candidates(cid, cap=3)
        assert [r["reasons"] for r in remaining] == [["active_plan"]]

    def test_the_ladder_declares_the_rung_built(self):
        """`character_agent` marked unbuilt would clamp every story that
        asked for it back to the floor (`effective_depth`), and the tier
        would be another mechanism that reads correct and cannot fire."""
        from living_world import LIVING_WORLD_BUILT
        from scene import OFFSCREEN_LIFE_BUILT

        assert "character_agent" in OFFSCREEN_LIFE_BUILT
        assert "ceiling" in LIVING_WORLD_BUILT["antagonist_ladder"]
