"""A mind's memories of a time skip (`mind/skip_memories.py`).

The skip stage leaves each asked mind its own LOG of the stretch a skip beat
passed over; after the commit, out of band, one writer call per mind turns that
log into the mind's memories, a two-part check holds them to it, and the rows
land on the mind's own ledger. Design: `docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md`
§§ 2.2 and 4.6, and the four rules of `DESIGN_OFFSCREEN_SUPERSEDED.md` § 3c.

The firewall here is a STRUCTURE, as `world/offscreen.agent_context` builds
its own: the writer is handed one mind's card, its memory from before the
stretch and its own record, and the tests below are mostly about what never
reaches it.
"""

from __future__ import annotations

import ast
import inspect
import json
import threading
import time

import pytest

from core.db import wset
from llm import decisions
from mind import skip_memories as sm

#: Planted where the writer must never look. Each is a sentence nobody else
#: says, so finding it in a call is finding the leak.
SECRET_OTHER_LOG = "the cellar key is under the third flagstone"
SECRET_OTHER_WHY = "because the harbourmaster owes him for the crate"
SECRET_OWN_WHY = "so that nobody guesses he means to leave the rock"
SECRET_PROSE = "the Director's account says the storm drowned the quay"
SECRET_OTHER_BANK = "Pell remembers the smuggled crate under the nets"

ANCHOR_HOUR = 7.0          # the story's clock reads 07:00 at elapsed zero
HOUR = 3600.0
SPAN = {"from_s": 0.0, "until_s": 48 * HOUR}


def _sheet(name, **extra):
    return {"identity": {"name": name},
            "psychology": {"drive": {"essence": "keep the light burning"},
                           "values": ["duty over comfort"]},
            **extra}


def _elias_log():
    return [
        {"from_s": 0.0, "until_s": 4 * HOUR, "room": "lamp_room", "away": None,
         "where_text": "the lamp room", "doing": "laying the new clockwork out on the bench",
         "asleep": False,
         "seen": [{"who": "Rhona Carrick", "doing": "working at the gear train",
                   "why": SECRET_OTHER_WHY}],
         "weather": "grey, a long swell from the south-west", "outcome": "done",
         "reason": None,
         # A field no LOG row carries: if a later stage ever put the mind's
         # intent here, it must still stop at the record.
         "why": SECRET_OWN_WHY},
        {"from_s": 15 * HOUR, "until_s": 23 * HOUR, "room": "elias_room", "away": None,
         "where_text": "my bedroom", "doing": "sleeping", "asleep": True, "seen": [],
         "weather": None, "outcome": "done", "reason": None},
        {"from_s": 26 * HOUR, "until_s": 30 * HOUR, "room": None,
         "away": "the harbour office", "where_text": "the Board's office",
         "doing": "asking after the new mechanism", "asleep": False,
         "seen": [{"who": "a clerk in sleeve-guards", "doing": "writing in a ledger"}],
         "weather": None, "outcome": "not_known", "reason": None},
    ]


def _pell_log():
    return [
        {"from_s": 2 * HOUR, "until_s": 6 * HOUR, "room": None, "away": "the quay",
         "where_text": "the quay", "doing": "loading the boat, " + SECRET_OTHER_LOG,
         "asleep": False, "seen": [], "weather": "fair", "outcome": "failed",
         "reason": "the letter was not on him"},
    ]


def _output(elias_log=None, pell_log=None):
    return {
        "span": dict(SPAN),
        "minds": {
            "Elias Thorne": {
                "source": "asked",
                "answer": {"plan": [{"doing": "fit the plate", "why": SECRET_OWN_WHY}]},
                "itinerary": [{"from_s": 0.0, "until_s": 4 * HOUR, "why": SECRET_OWN_WHY}],
                "log": _elias_log() if elias_log is None else elias_log,
                "far_end": {"room": "kitchen", "away": None, "asleep": False,
                            "asleep_since_s": None}},
            "Pell Hardacre": {
                "source": "asked",
                "answer": {"plan": [{"doing": "post the letter", "why": SECRET_OTHER_WHY}]},
                "itinerary": [{"why": SECRET_OTHER_WHY}],
                "log": _pell_log() if pell_log is None else pell_log,
                "far_end": {"room": None, "away": "the quay", "asleep": False,
                            "asleep_since_s": None}},
        },
    }


def _step(db, turn_id, key, content, ord_=0):
    sid = db.qi("INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                (turn_id, key, key, ord_))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps(content), time.time()))
    return sid


@pytest.fixture
def story(temp_db):
    """A lighthouse: Elias (active) and Pell (away), four beats, the fourth a
    two-day skip whose `skip_lives` step lived both of them."""
    db = temp_db
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("The Lamp Room", "", time.time()))
    elias = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                  ("Elias Thorne", json.dumps(_sheet(
                      "Elias Thorne",
                      knowledge={"public_history": "Keeper of the rock for eleven years."})),
                   "{}", time.time()))
    pell = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                 ("Pell Hardacre", json.dumps(_sheet("Pell Hardacre")), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, elias, "active", json.dumps({"active_state": {"goal": "judge the mechanism",
                                                             "mood": "wary"}})))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, pell, "dormant", "{}"))
    turns = []
    for idx in range(4):
        turns.append(db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,commit_seq) VALUES(?,?,?,?,?)",
            (cid, idx, "Two days later the wind gets up." if idx == 3 else "beat %d" % idx,
             time.time(), idx + 1)))
    skip_turn = turns[3]
    wset(cid, "simulation_clock", {"elapsed_seconds": 49 * HOUR, "anchor_hour": ANCHOR_HOUR,
                                   "day_length_hours": 24.0, "display": "morning"})
    wset(cid, "scene", {"rooms": {"lamp_room": {"name": "The Lamp Room"},
                                  "elias_room": {"name": "Elias's Room"},
                                  "kitchen": {"name": "The Kitchen"}},
                        "positions": {}, "entities": {}})
    wset(cid, "known", {"Elias Thorne": ["Rhona Carrick", "Pell Hardacre"]})
    from mind import memory
    memory.add_memory(cid, elias, turns[1], "episodic", "witnessed", 0.6,
                      "What I did: I read the Board's letter twice at the kitchen table.",
                      turn_idx=1, event_key="event:elias-1")
    memory.add_memory(cid, pell, turns[1], "episodic", "witnessed", 0.6,
                      SECRET_OTHER_BANK, turn_idx=1, event_key="event:pell-1")
    _step(db, skip_turn, "director_interpret", {"prose": SECRET_PROSE}, 0)
    _step(db, skip_turn, "director_resolve", {"prose": SECRET_PROSE}, 5)
    _step(db, skip_turn, sm.SKIP_LIVES_STEP, _output(), 2)
    return {"db": db, "cid": cid, "elias": elias, "pell": pell, "turns": turns,
            "turn": skip_turn}


def _answer(*episodes):
    return json.dumps({"episodes": list(episodes)})


def _episode(memory, rows=(0,), consequence="", valence=0.2, arousal=0.4, **extra):
    return {"rows": list(rows), "when": "", "where": "", "memory": memory,
            "consequence": consequence, "valence": valence, "arousal": arousal, **extra}


class _Writer:
    """The writer, as a test: records every call and answers by mind."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, role, system, user, **kwargs):
        with self.lock:
            self.calls.append({"role": role, "system": system, "user": user,
                               "payload": json.loads(user), **kwargs})
        for name, answer in self.answers.items():
            if f"Write {name}'s own memories" in system:
                return answer(system, json.loads(user)) if callable(answer) else answer
        return _answer()

    def for_mind(self, name):
        return [c for c in self.calls if f"Write {name}'s own memories" in c["system"]]


def _no_decisions(monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", None)


ELIAS_PLAIN = _answer(
    _episode("I laid the new clockwork out on the bench in the lamp room and went over "
             "each piece. Rhona Carrick worked at the gear train beside me.",
             rows=[0], consequence="I have seen the mechanism now.", valence=0.1,
             arousal=0.4),
    _episode("I slept in my own bed and woke once to the swell.", rows=[1], valence=0.0,
             arousal=0.1),
    _episode("I went to the Board's office and asked after the new mechanism.", rows=[2],
             valence=-0.2, arousal=0.3))
PELL_PLAIN = _answer(_episode("I loaded the boat on the quay and the letter was not on me.",
                              rows=[0], valence=-0.8, arousal=0.8))


# ---------------------------------------------------------------------------
# Scheduled only after a skip beat with minds.
# ---------------------------------------------------------------------------

class _Ctx:
    def __init__(self, cid, turn_id, idx, output):
        self.chat = type("Chat", (), {"id": cid})()
        self.turn = type("Turn", (), {"id": turn_id, "idx": idx, "frame_id": None})()
        self._output = output

    def get(self, key, default=None):
        return self._output if key == sm.SKIP_LIVES_STEP and self._output is not None \
            else default


class TestScheduledOnlyAfterASkipBeatWithMinds:
    @pytest.fixture(autouse=True)
    def _quiet_jobs(self):
        from core import jobs
        jobs.reset()
        yield
        jobs.drain(timeout=2.0)
        jobs.reset()

    def test_an_ordinary_beat_schedules_nothing(self, story):
        from persist.commit import schedule_skip_memories
        assert schedule_skip_memories(_Ctx(story["cid"], story["turn"], 3, None)) is None

    def test_a_skip_with_no_mind_or_only_empty_logs_schedules_nothing(self, story):
        from persist.commit import schedule_skip_memories
        for output in ({"span": SPAN, "minds": {}},
                       {"span": SPAN, "minds": {"Elias Thorne": {"log": []}}},
                       {"span": SPAN}):
            assert schedule_skip_memories(_Ctx(story["cid"], story["turn"], 3, output)) is None

    def test_a_skip_with_minds_queues_one_job_for_its_own_beat(self, story, monkeypatch):
        from core import jobs
        from persist.commit import SKIP_MEMORIES_JOB_PREFIX, schedule_skip_memories
        ran = []
        monkeypatch.setattr(sm, "run_skip_memories",
                            lambda cid, turn_id, **kw: ran.append((cid, turn_id, kw)) or {})
        job = schedule_skip_memories(_Ctx(story["cid"], story["turn"], 3, _output()))
        assert job is not None
        assert job.key == SKIP_MEMORIES_JOB_PREFIX + str(story["turn"])
        assert job.base_turn == 3
        deadline = time.monotonic() + 5.0
        while job.state in ("pending", "running") and time.monotonic() < deadline:
            time.sleep(0.01)
        assert job.state == "done", (job.state, job.error)
        assert ran and ran[0][:2] == (story["cid"], story["turn"])
        assert jobs.status(story["cid"], job.key) == "done"

    def test_the_commit_tail_schedules_it_after_the_transaction(self):
        """Wired where consolidation is: after the turn's facts are durable,
        never inside the transaction a domain failure rolls back."""
        from persist import commit
        tree = ast.parse(inspect.getsource(commit._commit_all_locked))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and getattr(node.func, "id", "") == "schedule_skip_memories"]
        assert len(calls) == 1
        inside = [node for node in ast.walk(tree) if isinstance(node, ast.With)
                  for call in ast.walk(node) if call is calls[0]]
        assert not inside

    def test_a_restore_stops_only_a_job_whose_beat_it_takes_back(self, story):
        from core import jobs
        from persist.commit import cancel_discarded_skip_memories
        release = threading.Event()
        key = "skip_memories:%d" % story["turn"]
        job = jobs.submit(story["cid"], key, lambda j: release.wait(5.0), base_turn=3)
        try:
            assert cancel_discarded_skip_memories(story["cid"], 4) == 0
            assert not job.cancelled.is_set()          # beat 3 is kept
            assert cancel_discarded_skip_memories(story["cid"], 3) == 1
            assert job.cancelled.is_set()              # beat 3 is taken back
        finally:
            release.set()

    def test_the_restore_asks(self):
        from persist import checkpoints
        source = inspect.getsource(checkpoints._cancel_jobs_the_restore_discards)
        assert "cancel_discarded_skip_memories" in source


# ---------------------------------------------------------------------------
# One call per mind, each seeing only its own log -- and the firewall.
# ---------------------------------------------------------------------------

class TestOneCallPerMindItsOwnLogOnly:
    def test_each_mind_is_asked_once_on_the_writers_row(self, story, monkeypatch):
        _no_decisions(monkeypatch)
        writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        assert len(writer.calls) == 2
        assert {c["role"] for c in writer.calls} == {sm.SKIP_MEMORY_ROLE}
        assert len(writer.for_mind("Elias Thorne")) == 1
        assert len(writer.for_mind("Pell Hardacre")) == 1

    def test_nothing_of_another_mind_its_plan_or_the_account_reaches_a_call(
            self, story, monkeypatch):
        _no_decisions(monkeypatch)
        writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        elias = writer.for_mind("Elias Thorne")[0]
        sent = elias["system"] + elias["user"]
        # Its own log is there ...
        assert "laying the new clockwork out on the bench" in sent
        assert "Rhona Carrick" in sent and "working at the gear train" in sent
        # ... and nothing else is: not the other mind's log, plan or memory,
        # not what another mind meant by what it did, not its own plan's
        # intent, not the Director's prose.
        for secret in (SECRET_OTHER_LOG, SECRET_OTHER_WHY, SECRET_OWN_WHY,
                       SECRET_PROSE, SECRET_OTHER_BANK):
            assert secret not in sent, secret
        pell = writer.for_mind("Pell Hardacre")[0]
        assert SECRET_OTHER_LOG in pell["user"]          # its own
        assert "laying the new clockwork" not in pell["user"]
        assert "the Board's letter" not in pell["user"]  # Elias's memory

    def test_the_payload_is_the_allowlist_and_nothing_more(self, story, monkeypatch):
        _no_decisions(monkeypatch)
        writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        for call in writer.calls:
            assert tuple(call["payload"]) == sm.WRITER_PAYLOAD_KEYS
        params = inspect.signature(sm.writer_payload).parameters
        assert tuple(params) == sm.WRITER_PAYLOAD_KEYS

    def test_its_memory_is_its_own_and_from_before_the_skip(self, story, monkeypatch):
        _no_decisions(monkeypatch)
        from mind import memory
        # A row of the skip beat itself -- the far end -- is not the past.
        memory.add_memory(story["cid"], story["elias"], story["turn"], "episodic",
                          "witnessed", 0.6, "What I did: sat across the table with tea.",
                          turn_idx=3, event_key="event:elias-far-end")
        writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        sent = writer.for_mind("Elias Thorne")[0]["user"]
        assert "read the Board's letter twice" in sent
        assert "sat across the table with tea" not in sent
        # Host handles never go over: no event keys, no row ids.
        assert "event:elias-1" not in sent and "memory_ref" not in sent

    def test_a_log_row_is_read_through_its_allowlist(self):
        rows = sm.record_rows(_elias_log(), span_from=0.0, anchor=ANCHOR_HOUR, length=24.0)
        blob = json.dumps(rows)
        assert SECRET_OWN_WHY not in blob and SECRET_OTHER_WHY not in blob
        assert set(rows[0]) <= {"n", "when", "where", "set_about", "asleep", "with",
                                "weather", "outcome", "how_it_went"}
        assert rows[0]["with"] == [{"who": "Rhona Carrick", "doing": "working at the gear train"}]
        assert set(sm.SEEN_FIELDS) == {"who", "doing"}

    def test_the_mind_pass_never_reaches_for_a_plan_or_the_account(self):
        """Asked of the parsed functions, as `test_offscreen_agent_context`
        asks it: the names, attributes and string keys the bodies can reach."""
        tree = ast.parse(inspect.getsource(sm))
        for fname in ("remember_one", "writer_payload", "record_rows", "memory_packet",
                      "card_of", "_jev_state", "past_state", "how_it_went"):
            fn = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == fname)
            reached = set()
            for node in ast.walk(fn):
                if isinstance(node, ast.Name):
                    reached.add(node.id)
                elif isinstance(node, ast.Attribute):
                    reached.add(node.attr)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    reached.add(node.value)
            forbidden = {"answer", "itinerary", "why", "far_end", "director_interpret",
                         "director_resolve", "narrator", "scene", "minds"}
            assert not forbidden & reached, (fname, sorted(forbidden & reached))

    def test_the_decision_models_state_is_the_record_and_the_memory(self, story,
                                                                   monkeypatch):
        seen_states, past_states = [], []

        def answer(state, questions):
            if "past" in questions:
                past_states.append(state)
            elif "others" in questions or "outcome" in questions:
                seen_states.append(state)
            else:
                return {}
            return {k: {"type": "noul", "noul": 0.0} for k in questions}

        monkeypatch.setattr(decisions, "OVERRIDE", answer)
        writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        assert seen_states and past_states
        for state in seen_states:
            assert set(state) == {"name", "record", "memory"}
        # The past question alone reads what the writer had of the time
        # before: the mind's own card and memory, nothing more.
        for state in past_states:
            assert set(state) == {"name", "who", "remembered", "record", "memory"}
        elias = [s for s in past_states if s["name"] == "Elias Thorne"]
        assert elias and "read the Board's letter twice" in json.dumps(elias[0]["remembered"])
        for state in seen_states + past_states:
            blob = json.dumps(state)
            for secret in (SECRET_OWN_WHY, SECRET_PROSE, SECRET_OTHER_WHY):
                assert secret not in blob
        assert SECRET_OTHER_BANK not in json.dumps(elias)


# ---------------------------------------------------------------------------
# The count.
# ---------------------------------------------------------------------------

class TestTheCount:
    @pytest.mark.parametrize("hours, count", [
        (1, 1), (11.99, 1), (12, 1), (23.5, 1), (24, 2), (48, 4), (72, 6),
        (96, 8), (168, 8), (24 * 30, 8)])
    def test_one_per_twelve_lived_hours_at_least_one_at_most_eight(self, hours, count):
        assert sm.memory_count({"from_s": 100.0, "until_s": 100.0 + hours * HOUR}) == count

    def test_a_sum_a_hair_short_of_the_hour_reaches_it(self):
        assert sm.memory_count({"from_s": 0.0, "until_s": 24 * HOUR - 0.04}) == 2

    def test_the_writer_is_asked_up_to_the_count_and_kept_to_it(self, story, monkeypatch):
        _no_decisions(monkeypatch)
        # Each its own occasion -- its own row -- since two memories built
        # from the same rows are one (fix lane B3).
        many = _answer(*[_episode("I tended the lamp on the %s watch." % w, rows=[n])
                         for n, w in enumerate(("first", "second", "third", "fourth",
                                                "fifth", "sixth"))])
        writer = _Writer({"Elias Thorne": many, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        result = sm.run_skip_memories(story["cid"], story["turn"])
        system = writer.for_mind("Elias Thorne")[0]["system"]
        assert "up to 4 memories" in system and "{count}" not in system
        assert result["Elias Thorne"]["written"] == 4


# ---------------------------------------------------------------------------
# The floor: numbers, a closed form.
# ---------------------------------------------------------------------------

#: The glm-5.2 memory of the keeper's log, measured on the tight card
#: (skip_probe/t_glm_control.json, elias_two_days, memory 1): every time in it
#: was invented -- the keeper's card and memory hold none of them.
GLM_ELIAS_LOG = ("After dinner I pulled the log from the shelf and went back to the March "
                 "entry. The pin. I wrote: 'Clockwork pin sheared at 0315. Lamp rotation "
                 "halted. Pin replaced from stores at 0410. Rotation restored. Lamp continued "
                 "through night.' Then the August entry: 'Drive belt frayed and slipped at "
                 "2100. Belt replaced from stores at 2145. Rotation restored without "
                 "interruption to the light.'")


class TestTheNumbersFloor:
    def _support(self, **sources):
        return sm.number_support(sources)

    def test_the_invented_log_times_are_caught(self):
        found = sm.unsupported_numbers(GLM_ELIAS_LOG, self._support(
            record=[{"n": 0, "when": {"day": 0, "from": "midday", "until": "dusk"},
                     "did": "went back through the log to the March pin and August belt entries"}]))
        assert [f["said"] for f in found] == ["0315", "0410", "2100", "2145"]
        assert found[0]["in"] == "I wrote: 'Clockwork pin sheared at 0315."

    def test_a_number_the_record_memory_or_card_holds_stands(self):
        support = self._support(who={"public_history": "Keeper for eleven years."},
                                memory={"recent_memories": [{"details": "The letter came at 3:15."}]},
                                record=[{"did": "loaded 12 crates"}])
        text = "Eleven years on the rock. At 0315 I woke. I counted twelve crates."
        assert sm.unsupported_numbers(text, support) == []

    def test_a_time_is_held_by_its_hour_and_minute_not_by_its_hour(self):
        support = self._support(record=[{"did": "woke at three"}])
        assert [f["said"] for f in sm.unsupported_numbers("I woke at 3:15.", support)] == ["3:15"]
        assert sm.unsupported_numbers("I woke at three.", support) == []

    def test_number_words_are_composed_not_listed(self):
        support = self._support(record=[{"did": "watched for 26 minutes"}])
        assert sm.unsupported_numbers("Twenty-six minutes dark.", support) == []
        found = sm.unsupported_numbers("Twenty-seven minutes dark.", support)
        assert [f["said"] for f in found] == ["Twenty-seven"]
        assert [f["said"] for f in sm.unsupported_numbers(
            "Three hundred and twelve stairs.", support)] == ["Three hundred and twelve"]

    def test_one_and_a_bare_magnitude_are_not_figures(self):
        support = self._support()
        text = ("The one thing I never muck. No one came. It has happened a thousand "
                "times before, and a hundred more.")
        assert sm.unsupported_numbers(text, support) == []

    def test_the_row_index_is_not_a_number_the_mind_was_given(self):
        support = self._support(record=[{"n": 7, "did": "slept"}])
        assert [f["said"] for f in sm.unsupported_numbers("Seven bells.", support)] == ["Seven"]

    def test_japanese_numbers_by_the_packs_own_grammar(self):
        from language_runtime import current_language_id
        token = current_language_id.set("ja")
        try:
            support = sm.number_support({"record": [{"when": {"day": 2}, "did": "三時に起きた"}]})
            text = ("二十六分の闇。三時に起きた。十分に眠った。万一のために灯を残した。"
                    "二日目の朝。１２時に灯をともした。")
            assert [f["said"] for f in sm.unsupported_numbers(text, support)] == ["二十六", "12"]
        finally:
            current_language_id.reset(token)

    def test_the_floor_reads_the_pack_not_a_list_in_code(self):
        """The number words are the pack's (`linguistics.mind.skip_memories`),
        so a language is added by its pack: no number word is spelled in the
        module."""
        source = inspect.getsource(sm)
        for word in ("twenty", "hundred", "eleven", "dozen", "十", "百"):
            assert f'"{word}"' not in source and f"'{word}'" not in source


# ---------------------------------------------------------------------------
# The decision model's question, the rewrite and the drop.
# ---------------------------------------------------------------------------

INVENTED = "The barman noticed and said nothing."


def _others_override(flag_memory=(), flag_sentence=()):
    """Jev, as a test: the memory-level question says yes for a memory
    holding one of `flag_memory`; a sentence question says yes for a sentence
    holding one of `flag_sentence`. The picker's own questions go unanswered."""
    asked = []

    def answer(state, questions):
        out = {}
        for key, question in questions.items():
            if key == "others":
                text = state["memory"]
                out[key] = {"type": "noul",
                            "noul": 0.9 if any(m in text for m in flag_memory) else 0.05}
            elif key.startswith("s") and key[1:].isdigit():
                sentence = question["instructions"].rsplit(":", 1)[-1]
                out[key] = {"type": "noul",
                            "noul": 0.9 if any(m in sentence for m in flag_sentence) else 0.05}
        if out:
            asked.append((state, questions))
        return out

    return answer, asked


class TestTheDecisionModelCheck:
    def _run(self, story, monkeypatch, elias, *, flag_memory=(), flag_sentence=()):
        override, asked = _others_override(flag_memory, flag_sentence)
        monkeypatch.setattr(decisions, "OVERRIDE", override)
        writer = _Writer({"Elias Thorne": elias, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        result = sm.run_skip_memories(story["cid"], story["turn"])
        rows = story["db"].q("SELECT content, event_key FROM memories WHERE char_id=? AND "
                             "event_key LIKE 'skip:%' ORDER BY event_key", (story["elias"],))
        return result["Elias Thorne"], [r["content"] for r in rows], writer, asked

    def test_a_flagged_memory_is_rewritten_once_then_its_flagged_sentence_goes(
            self, story, monkeypatch):
        first = ("I went to the Board's office and asked after the new mechanism. "
                 + INVENTED + " I left with nothing.")

        def elias(system, payload):
            if "rewrite" in payload:
                # The rewrite still carries it.
                return _answer(_episode(first + " I walked back slowly.", rows=[2], index=1))
            return _answer(_episode("I laid the clockwork out in the lamp room.", rows=[0]),
                           _episode(first, rows=[2]))

        result, contents, writer, asked = self._run(
            story, monkeypatch, elias, flag_memory=("barman",), flag_sentence=("barman",))
        calls = writer.for_mind("Elias Thorne")
        assert len(calls) == 2                       # the writer, then ONE rewrite
        rewrite = calls[1]["payload"]["rewrite"]
        assert [w["index"] for w in rewrite] == [1]
        assert rewrite[0]["flags"] == [{"kind": "others", "in": INVENTED}]
        assert "ONE MORE PASS" in calls[1]["system"]
        assert result["rewritten"] == [1]
        assert result["dropped_sentences"] == {1: [INVENTED]}
        assert len(contents) == 2
        assert INVENTED not in contents[1]
        assert contents[1].startswith("I went to the Board's office")
        assert "I walked back slowly." in contents[1]     # the rewrite's own text stands

    def test_a_rewrite_that_holds_replaces_the_memory_whole(self, story, monkeypatch):
        def elias(system, payload):
            if "rewrite" in payload:
                return _answer(_episode("I asked after the mechanism and left.", rows=[2],
                                        index=0))
            return _answer(_episode("I asked after the mechanism. " + INVENTED, rows=[2]))

        result, contents, _writer, _asked = self._run(
            story, monkeypatch, elias, flag_memory=("barman",), flag_sentence=("barman",))
        assert contents == ["I asked after the mechanism and left."]
        assert result["dropped_sentences"] == {}

    def test_a_memory_with_nothing_left_goes(self, story, monkeypatch):
        def elias(system, payload):
            if "rewrite" in payload:
                return _answer(_episode(INVENTED, rows=[2], index=1))
            return _answer(_episode("I laid the clockwork out in the lamp room.", rows=[0]),
                           _episode(INVENTED, rows=[2]))

        result, contents, _writer, _asked = self._run(
            story, monkeypatch, elias, flag_memory=("barman",), flag_sentence=("barman",))
        assert result["dropped"] == [1]
        assert contents == ["I laid the clockwork out in the lamp room."]

    def test_a_number_flag_names_what_was_said_and_the_rewrite_mends_it(
            self, story, monkeypatch):
        def elias(system, payload):
            if "rewrite" in payload:
                return _answer(_episode("The pin sheared in the small hours.", rows=[0],
                                        index=0))
            return _answer(_episode("The pin sheared at 0315.", rows=[0]))

        result, contents, writer, _asked = self._run(story, monkeypatch, elias)
        flags = writer.for_mind("Elias Thorne")[1]["payload"]["rewrite"][0]["flags"]
        assert flags == [{"kind": "number", "said": "0315", "in": "The pin sheared at 0315."}]
        assert contents == ["The pin sheared in the small hours."]

    def test_an_unanswering_decision_model_leaves_the_floor_standing(self, story,
                                                                    monkeypatch):
        def refuse(state, questions):
            raise decisions.DecisionError("unreachable")

        monkeypatch.setattr(decisions, "OVERRIDE", refuse)
        # The rewrite comes back unchanged: the writer did not mend it.
        same = _answer(_episode("It came at 0315. " + INVENTED, rows=[0], index=0))
        writer = _Writer({"Elias Thorne": same, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        result = sm.run_skip_memories(story["cid"], story["turn"])["Elias Thorne"]
        assert result["jev"] == "unavailable"
        assert result["dropped_sentences"] == {0: ["It came at 0315."]}
        row = story["db"].q("SELECT content FROM memories WHERE char_id=? AND event_key "
                            "LIKE 'skip:%'", (story["elias"],), one=True)
        assert row["content"] == INVENTED   # the floor took its sentence; nobody could
                                            # ask about the rest, so the rest stands


# ---------------------------------------------------------------------------
# The rows.
# ---------------------------------------------------------------------------

class TestTheRows:
    def _write(self, story, monkeypatch, elias=ELIAS_PLAIN):
        _no_decisions(monkeypatch)
        writer = _Writer({"Elias Thorne": elias, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        return sm.run_skip_memories(story["cid"], story["turn"])

    def _rows(self, story, char_id):
        return story["db"].q("SELECT * FROM memories WHERE char_id=? AND event_key LIKE "
                             "'skip:%' ORDER BY event_key", (char_id,))

    def test_every_field(self, story, monkeypatch):
        result = self._write(story, monkeypatch)
        assert result["Elias Thorne"]["written"] == 3
        rows = self._rows(story, story["elias"])
        assert [r["event_key"] for r in rows] == [
            "skip:%d:Elias Thorne:%d" % (story["turn"], n) for n in range(3)]
        for row in rows:
            assert row["kind"] == "episodic" and row["provenance"] == "witnessed"
            assert row["category"] == "episode"
            assert row["turn_id"] == story["turn"] and row["turn_idx"] == 3
            assert row["frame_id"] is None
            assert row["embedding"] is not None and row["embedding_model"]
            assert row["confidence"] == 1.0
            assert sm.is_skip_memory(row)
        first, sleep, office = rows
        # Each at its own occasion: the end of the stretch it was made from.
        assert [r["encoded_at_seconds"] for r in rows] == [4 * HOUR, 23 * HOUR, 30 * HOUR]
        assert first["location"] == "The Lamp Room"
        assert sleep["location"] == "Elias's Room"
        assert office["location"] == "the harbour office"
        assert json.loads(first["about"]) == ["Rhona Carrick"]
        assert office["about"] == ""                  # a stranger's label is nobody's name
        assert first["content"].endswith("What stayed with me: I have seen the mechanism now.")
        assert first["valence"] == first["encoding_valence"] == pytest.approx(0.1)
        assert first["salience"] == pytest.approx(0.45 + 0.4 * 0.4)

    def test_a_rerun_replaces_and_never_duplicates(self, story, monkeypatch):
        self._write(story, monkeypatch)
        assert len(self._rows(story, story["elias"])) == 3
        self._write(story, monkeypatch, elias=_answer(
            _episode("I laid the clockwork out in the lamp room.", rows=[0])))
        rows = self._rows(story, story["elias"])
        assert [r["event_key"] for r in rows] == ["skip:%d:Elias Thorne:0" % story["turn"]]
        assert rows[0]["content"] == "I laid the clockwork out in the lamp room."
        # And the commit's own delete-by-turn takes them as it takes the beat's rows.
        from mind.memory import delete_turn_memories
        delete_turn_memories(story["turn"])
        assert self._rows(story, story["elias"]) == []

    def test_a_rerolled_step_or_a_taken_back_commit_writes_nothing(self, story,
                                                                  monkeypatch):
        db = story["db"]
        sid = db.q("SELECT id FROM steps WHERE turn_id=? AND key=?",
                   (story["turn"], sm.SKIP_LIVES_STEP), one=True)["id"]
        _no_decisions(monkeypatch)
        state = {"n": 0}

        def reroll_midway(role, system, user, **kw):
            # The skip step is rerolled while the writer is out.
            if state["n"] == 0:
                db.qi("UPDATE variants SET active=0 WHERE step_id=?", (sid,))
                db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                      (sid, json.dumps(_output()), time.time()))
            state["n"] += 1
            return ELIAS_PLAIN if "Elias" in system else PELL_PLAIN

        monkeypatch.setattr(sm, "chat_complete", reroll_midway)
        result = sm.run_skip_memories(story["cid"], story["turn"], workers=1)
        assert {r["status"] for r in result.values()} == {"superseded"}
        assert self._rows(story, story["elias"]) == []
        db.qi("UPDATE turns SET commit_seq=NULL WHERE id=?", (story["turn"],))
        assert not sm.still_committed(story["turn"], 3,
                                      sm.committed_output(story["turn"])[0])

    def test_a_cancelled_job_writes_nothing(self, story, monkeypatch):
        _no_decisions(monkeypatch)
        monkeypatch.setattr(sm, "chat_complete", _Writer(
            {"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN}))
        job = type("Job", (), {"cancelled": threading.Event()})()
        job.cancelled.set()
        result = sm.run_skip_memories(story["cid"], story["turn"], job=job)
        assert {r["status"] for r in result.values()} == {"cancelled"}
        assert self._rows(story, story["elias"]) == []

    def test_a_checkpoint_taken_after_the_beat_carries_them_and_none_before(
            self, story, monkeypatch):
        db = story["db"]
        for idx in (3, 4):
            db.qi("INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
                  (story["cid"], idx, json.dumps({"memories": [
                      {"char_id": story["elias"], "turn_id": story["turn"],
                       "event_key": "skip:%d:Elias Thorne:9" % story["turn"],
                       "content": "a stale row"}]}), time.time()))
        self._write(story, monkeypatch)
        before = json.loads(db.q("SELECT blob FROM checkpoints WHERE turn_idx=3",
                                 one=True)["blob"])["memories"]
        after = json.loads(db.q("SELECT blob FROM checkpoints WHERE turn_idx=4",
                                one=True)["blob"])["memories"]
        assert [m["content"] for m in before] == ["a stale row"]     # untouched
        keys = sorted(m["event_key"] for m in after if m["char_id"] == story["elias"])
        assert keys == ["skip:%d:Elias Thorne:%d" % (story["turn"], n) for n in range(3)]
        assert all(m.get("vkey") for m in after)


# ---------------------------------------------------------------------------
# The rows reach recall.
# ---------------------------------------------------------------------------

class TestTheyReachRecall:
    def test_the_recent_window_holds_them(self, story, monkeypatch):
        TestTheRows()._write(story, monkeypatch)
        from mind.memory import build_character_memory_context
        ctx = build_character_memory_context(story["cid"], story["elias"], 4,
                                             "the kitchen", {})
        refs = {m["memory_ref"] for m in ctx["recent_memories"]}
        assert {"skip:%d:Elias Thorne:%d" % (story["turn"], n) for n in range(3)} <= refs

    def test_the_decision_models_pick_reaches_them_past_the_window(self, story,
                                                                  monkeypatch):
        TestTheRows()._write(story, monkeypatch)
        db = story["db"]
        from mind import memory
        for idx in range(4, 20):
            tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,commit_seq) "
                        "VALUES(?,?,?,?,?)", (story["cid"], idx, "x", time.time(), idx + 1))
            memory.add_memory(story["cid"], story["elias"], tid, "episodic", "witnessed",
                              0.5, "What I did: trimmed the wick on beat %d." % idx,
                              turn_idx=idx, event_key="event:later-%d" % idx)
        graded = []

        def grade(state, questions):
            out = {}
            for key, question in questions.items():
                strong = "Board's office" in question["instructions"]
                graded.append(key) if strong else None
                out[key] = {"type": "choice", "choice": "strong" if strong else "none",
                            "probabilities": {"strong": 0.95} if strong else {"none": 0.95}}
            return out

        monkeypatch.setattr(decisions, "OVERRIDE", grade)
        ctx = memory.build_character_memory_context(
            story["cid"], story["elias"], 20, "the Board's office again", {},
            person={"name": "Elias Thorne", "drive": "", "values": []}, recall_limit=3)
        assert graded                                  # the picker asked of the skip row
        refs = [m["memory_ref"] for m in ctx["recalled_old_memories"]]
        assert "skip:%d:Elias Thorne:2" % story["turn"] in refs
        assert ctx["_internal"]["picker"]["answered"] > 0


# ---------------------------------------------------------------------------
# The cards, en and ja.
# ---------------------------------------------------------------------------

class TestTheCards:
    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_card_names_every_field_it_is_handed_and_every_one_it_asks_for(
            self, language):
        system = sm.writer_system("Elias Thorne", 4, language)
        assert "Elias Thorne" in system and "4" in system
        assert "{name}" not in system and "{count}" not in system
        for key in sm.WRITER_PAYLOAD_KEYS:
            assert "`%s`" % key in system, key
        for key in ("n", "when", "where", "set_about", "asleep", "with", "weather",
                    "outcome", "how_it_went", "done", "failed", "not_known"):
            assert "`%s`" % key in system, key
        for key in ("rows", "memory", "consequence", "valence", "arousal"):
            assert '"%s"' % key in system, key

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_rewrite_pass_names_its_flags(self, language):
        system = sm.writer_system("Elias Thorne", 4, language, rewrite=True)
        assert system.count("Elias Thorne") >= 2
        for key in ("rewrite", "index", "flags", "number", "others", "outcome", "past",
                    "said", "in", "with", "how_it_went", "failed", "not_known"):
            assert "`%s`" % key in system, key
        assert '"index"' in system

    @pytest.mark.parametrize("pid", ["prompts.skip_memory", "prompts.skip_memory_rewrite",
                                     "jev_questions.skip_memory_others",
                                     "jev_questions.skip_memory_sentence",
                                     "jev_questions.skip_memory_outcome",
                                     "jev_questions.skip_memory_outcome_sentence",
                                     "jev_questions.skip_memory_past",
                                     "jev_questions.skip_memory_past_sentence"])
    def test_japanese_keeps_every_protocol_span(self, pid):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "tools"))
        from project_check import canonical_language_tokens
        from language_runtime import installed_language_packs
        packs = installed_language_packs()
        group, key = pid.split(".")
        en = str(packs["en"].card("system_prompts")[group][key])
        ja = str(packs["ja"].card("system_prompts")[group][key])
        assert en != ja
        assert canonical_language_tokens(en) <= canonical_language_tokens(ja)

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_questions_are_the_packs(self, language):
        from llm.prompts import jev_question
        assert set(sm.SKIP_MEMORY_CHECKS) <= set(sm.SKIP_MEMORY_QUESTIONS)
        for whole_key, sentence_key, _prefix in sm.SKIP_MEMORY_QUESTIONS.values():
            assert "Elias" in jev_question(whole_key, language, name="Elias")
            sentence = jev_question(sentence_key, language, name="Elias",
                                    sentence="The barman noticed.")
            assert "Elias" in sentence and sentence.rstrip().endswith("The barman noticed.")

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_each_question_names_what_its_state_holds(self, language):
        """A question talks about the fields its request carries, and the
        outcome question about the record's words for how a row went."""
        from llm.prompts import jev_question
        for kind, keys in sm.SKIP_MEMORY_QUESTIONS.items():
            for key in keys[:2]:
                text = jev_question(key, language, name="Elias", sentence="x")
                assert "`memory`" in text and "`record`" in text, (kind, key)
        for key in sm.SKIP_MEMORY_QUESTIONS["outcome"][:2]:
            text = jev_question(key, language, name="Elias", sentence="x")
            assert "`how_it_went`" in text, key
        for key in sm.SKIP_MEMORY_QUESTIONS["past"][:2]:
            text = jev_question(key, language, name="Elias", sentence="x")
            assert "`remembered`" in text and "`who`" in text, key

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_adult_overlay_reaches_the_writer_as_it_reaches_the_character(
            self, language):
        from language_runtime import installed_language_packs
        roster = installed_language_packs()[language].card("system_prompts")["nsfw_prompt_ids"]
        assert "skip_memory" in roster and "character_bare" in roster

    def test_the_writers_row_is_a_host_role_with_no_hidden_parent(self):
        from llm import providers
        assert sm.SKIP_MEMORY_ROLE in providers.ROLES
        assert sm.SKIP_MEMORY_ROLE not in providers.ROLE_FALLBACKS


# ---------------------------------------------------------------------------
# The record says how each stretch went IN WORDS, and three narrow questions
# hold a memory to it. The live case, the lighthouse replayed on
# 2026-10-21's code (job tmp fixes/live_skip/live_control.db, chat 3, turn 25
# at idx 8): the boatman's post-office stretch reached the writer as the
# codes `failed`/`not_held` and came back "So I did ... into the box" -- in
# a world where the letter never left the rock; the keeper's rotation test
# got a drift and then a clean mesh that no row gives; and the yard man
# "looked at it" while the others-check let him by.
# ---------------------------------------------------------------------------

#: What the boatman's stretch used and did not have to hand, in his own
#: words: the executor's `missing` (lane B2) on a `not_held` row.
PELL_LETTER = "Rhona Carrick's sealed letter, dry in the inside pocket of the oilskin jacket"
PELL_POST_DOING = (
    "Runs the Mary Ann in on the last of the flood, makes her fast, and goes straight up off "
    "the boat to the post office on the quay with Rhona Carrick's letter in his hand — puts "
    "it in the box himself before he does anything else, and says a word to the clerk about "
    "the weather coming so the crossing gets talked about.")
PELL_KNOCK_DOING = (
    "Has the engine cover off the Mary Ann first thing and works the knock — cleans the "
    "injectors, checks the tappets, runs her against the warps and listens. If it's beyond "
    "him, walks the impeller and the fuel line down to the yard man and stands over him while "
    "he looks at it, asking questions the whole time.")
ELIAS_TEST_DOING = (
    "Continue fitting and testing the new clockwork against the old — running it through "
    "rotation cycles, checking gear engagement, timing the sweep, marking any faults to show "
    "the engineer on Tuesday")

#: The live memories, word for word (`skip:25:Pell Hardacre:0`, `:2`;
#: `skip:25:Elias Thorne:2`), split at the row's own consequence label.
PELL_POSTED = (
    "I brought the Mary Ann in on the last of the flood and made her fast, and I went straight "
    "up off the boat with Rhona Carrick's letter in me hand — Harrow Street, by the post office "
    "on the quay, that's what she said, and I'd told her I'd put it in the box meself before "
    "the pub got its hooks in me. So I did. Straight up the quay, letter in the fist, into the "
    "box. And I had a word with the clerk about the weather coming up the channel, for it was "
    "worth talking about, spray heavy enough to sting and the glass falling. I stood there a "
    "moment after, thinking that was the job done neat.")
PELL_POSTED_AFTER = "I did what she asked and I did it first, before anything else — that much I know I did."
PELL_YARD = (
    "Woke with the gulls, boiled a tin kettle on the little stove, drank tea standing on the "
    "quay watching the sky over the channel to see what the day meant to do. Then I had the "
    "engine cover off the Mary Ann and a proper look at the knock — cleaned the injectors, "
    "checked the tappets, topped the oil, ran her against the warps to hear the beat. That "
    "knock was still in her. So I walked the impeller and the fuel line down to the yard man "
    "and stood over him while he looked at it, asking questions the whole time, for I'd "
    "rather know than guess.")
YARD_MAN = ("So I walked the impeller and the fuel line down to the yard man and stood over him "
            "while he looked at it, asking questions the whole time, for I'd rather know than "
            "guess.")
ELIAS_DRIFT = (
    "Barometer reading, weather logged, the horizon watched for first light. Extinguished the "
    "lamp, trimmed the wick, cleaned the chimney and lens. Then I ran the new clockwork "
    "through rotation cycles against the old — checking gear engagement, timing the sweep "
    "against the clock, marking faults to show the engineer on Tuesday. The timing drifted. "
    "I ran it again. The drift held. I marked it in the log and set the old method in "
    "parallel, because the light will not wait on a mechanism that cannot keep its measure. "
    "Carrick was below, or somewhere in the tower; I did not look for her. The work was the "
    "work.")
#: What the boatman's memory says once it holds to the record.
PELL_MENDED = ("I brought the Mary Ann in on the last of the flood, made her fast and went "
               "straight up the quay for the box -- and the letter was not on me.")


def _live_row(from_h, until_h, doing, outcome, *, reason=None, room=None, away=None,
              where_text="", seen=(), **extra):
    return {"from_s": from_h * HOUR, "until_s": until_h * HOUR, "room": room, "away": away,
            "where_text": where_text, "doing": doing, "asleep": False, "seen": list(seen),
            "weather": None, "outcome": outcome, "reason": reason, **extra}


def _pell_post_row(**extra):
    return _live_row(2, 6, PELL_POST_DOING, "failed", reason="not_held", room="the_mainland",
                     where_text="the mainland quay and the post office on the quay", **extra)


def _relog(story, *, elias_log=None, pell_log=None):
    """Put the skip step's output back with these logs, as the live LOG had them."""
    db = story["db"]
    sid = db.q("SELECT id FROM steps WHERE turn_id=? AND key=?",
               (story["turn"], sm.SKIP_LIVES_STEP), one=True)["id"]
    db.qi("UPDATE variants SET content=? WHERE step_id=? AND active=1",
          (json.dumps(_output(elias_log=elias_log, pell_log=pell_log)), sid))


def _questions(questions, kind):
    """`(whole, {i: sentence})`: one kind's memory question and its
    sentence questions in a request, by the keys the module gives them."""
    whole = questions.get(kind)
    prefix = sm.SKIP_MEMORY_QUESTIONS[kind][2]
    placed = {int(key[len(prefix):]): q["instructions"].rsplit("The sentence: ", 1)[-1].strip()
              for key, q in questions.items()
              if key.startswith(prefix) and key[len(prefix):].isdigit()}
    return whole, placed


class _Judge:
    """The decision model, as a test: yes for a memory -- and for each of its
    sentences -- holding one of the markers given for that kind, no for
    everything else asked. Records every request."""

    def __init__(self, **markers):
        self.markers = markers
        self.requests = []

    def __call__(self, state, questions):
        self.requests.append((state, questions))
        out = {}
        for kind in sm.SKIP_MEMORY_QUESTIONS:
            whole, placed = _questions(questions, kind)
            marks = self.markers.get(kind) or ()
            if whole is not None:
                hit = any(m in state["memory"] for m in marks)
                out[kind] = {"type": "noul", "noul": 0.9 if hit else 0.05}
            prefix = sm.SKIP_MEMORY_QUESTIONS[kind][2]
            for i, sentence in placed.items():
                hit = any(m in sentence for m in marks)
                out[f"{prefix}{i}"] = {"type": "noul", "noul": 0.9 if hit else 0.05}
        return out

    def asked(self, kind):
        return [q for _s, q in self.requests if kind in q]


def _run_pell(story, monkeypatch, judge, pell_log, first, rewrite):
    monkeypatch.setattr(decisions, "OVERRIDE", judge)
    _relog(story, pell_log=pell_log)

    def pell(system, payload):
        return rewrite(payload) if "rewrite" in payload else first

    writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": pell})
    monkeypatch.setattr(sm, "chat_complete", writer)
    result = sm.run_skip_memories(story["cid"], story["turn"])["Pell Hardacre"]
    rows = story["db"].q("SELECT content FROM memories WHERE char_id=? AND event_key LIKE "
                         "'skip:%' ORDER BY event_key", (story["pell"],))
    return result, [r["content"] for r in rows], writer.for_mind("Pell Hardacre")


class TestTheRecordSaysHowItWent:
    def _one(self, row, language="en", **kw):
        return sm.record_rows([row], span_from=0.0, anchor=ANCHOR_HOUR, length=24.0,
                              name="Pell Hardacre", language=language, **kw)[0]

    def test_a_failed_row_says_in_words_what_was_not_to_hand(self):
        row = self._one(_pell_post_row(missing=[PELL_LETTER]))
        assert row["outcome"] == "failed"
        words = row["how_it_went"]
        assert "did not come off" in words and PELL_LETTER in words
        assert "Pell Hardacre" in words
        # The words carry the reason; the bare code never reaches the writer,
        # and what the mind set about is never called what it DID.
        assert "reason" not in row and "did" not in row
        assert row["set_about"].startswith("Runs the Mary Ann in")
        # It went: the place stands, in its own words.
        assert row["where"] == "the mainland quay and the post office on the quay"

    def test_more_than_one_thing_is_named_by_the_packs_own_list(self):
        row = self._one(_pell_post_row(missing=["the post bag", "the standing order",
                                                "the Mary Ann"]))
        assert "the post bag, the standing order, and the Mary Ann" in row["how_it_went"]
        ja = self._one(_pell_post_row(missing=["郵便袋", "定期の注文品", "メアリー・アン号"]),
                       language="ja")
        assert "郵便袋、定期の注文品、そしてメアリー・アン号" in ja["how_it_went"]

    def test_a_row_written_before_missing_still_says_it_did_not_come_off(self):
        row = self._one(_pell_post_row())
        assert "did not come off" in row["how_it_went"]
        assert "missing" not in row

    @pytest.mark.parametrize("reason", ["no_route", "shut_way", "too_far"])
    def test_a_way_that_failed_names_where_it_was_going_and_where_it_stood(self, reason):
        # The executors' shape: `room` is where the mind stood (or as far
        # along the way as it got), `where_text` its own words for where it
        # meant to be.
        row = _live_row(26, 30, "asking after the new mechanism", "failed", reason=reason,
                        room="lamp_room", where_text="the Board's office")
        got = self._one(row, room_names={"lamp_room": "The Lamp Room"})
        assert got["where"] == "The Lamp Room"
        assert "the Board's office" in got["how_it_went"]
        assert "did not come off" in got["how_it_went"]
        # The LOG's own `meant` (lane B2) is the place, where it gives one.
        got = self._one(dict(row, meant="the harbour office"),
                        room_names={"lamp_room": "The Lamp Room"})
        assert "the harbour office" in got["how_it_went"]
        assert "the Board's office" not in json.dumps(got)

    def test_a_way_only_a_vessel_crosses_names_where_it_was_going(self):
        for language in ("en", "ja"):
            words = sm.how_it_went("Pell Hardacre", "failed", "no_crossing",
                                   meant="the rock", language=language)
            assert "the rock" in words and "Pell Hardacre" in words
        assert "did not come off" in sm.how_it_went("Pell Hardacre", "failed",
                                                    "no_crossing", meant="the rock")

    def test_a_row_carrying_meant_says_where_it_stood_in_its_own_words(self):
        """The executor's shape once `meant` is on every row (lane B2):
        `where_text` is where the body WAS, `meant` where it was going -- so
        an empty `meant` never borrows `where_text` for the place."""
        row = _live_row(26, 30, "asking after the new mechanism", "failed",
                        reason="no_route", room="lamp_room", where_text="up in the lantern",
                        meant=None, missing=[])
        got = self._one(row, room_names={"lamp_room": "The Lamp Room"})
        assert got["where"] == "The Lamp Room"
        assert "lantern" not in got["how_it_went"]
        assert "did not come off" in got["how_it_went"]

    def test_not_known_says_the_mind_set_about_it_and_done_that_it_did_it(self):
        # Said as the mind would remember it, never as a note about the
        # record (fix lane B3: the old words were written into the memories
        # as they stood, "and did not know what came of it", row after row).
        unknown = self._one(_live_row(0, 4, "supper at the pub", "not_known",
                                      away="the harbour pub", where_text="the harbour pub"))
        assert unknown["how_it_went"] == ("Pell Hardacre set about it, and the rest was "
                                          "out of Pell Hardacre's hands.")
        done = self._one(_live_row(0, 4, "testing the clockwork", "done", room="lamp_room",
                                   where_text="The Lamp Room"))
        assert done["how_it_went"] == "Pell Hardacre did it."
        for row in (unknown, done):
            assert "record" not in row["how_it_went"]
            assert "what came of it" not in row["how_it_went"]

    def test_the_words_are_the_packs_in_japanese(self):
        row = self._one(_pell_post_row(missing=["リアナの封をした手紙"]), language="ja")
        assert "リアナの封をした手紙" in row["how_it_went"]
        assert "Pell Hardacre" in row["how_it_went"]
        assert "did not come off" not in row["how_it_went"]
        unknown = self._one(_live_row(0, 4, "x", "not_known", away="港"), language="ja")
        assert "Pell Hardacre" in unknown["how_it_went"]
        assert "did not come off" not in unknown["how_it_went"]
        assert "what came of it" not in unknown["how_it_went"]

    def test_every_outcome_and_reason_has_its_words_in_both_packs(self):
        from language_runtime import installed_language_packs
        from world.skip_itinerary import FAILURE_REASONS
        # Every reason either executor writes has its words.
        assert set(FAILURE_REASONS) <= set(sm.FAILURE_WORDS)
        keys = list(sm.RECORD_WORDS.values()) + [
            key for pair in sm.FAILURE_WORDS.values() for key in pair]
        for language in ("en", "ja"):
            templates = installed_language_packs()[language].card("compositor")["templates"]
            for key in keys:
                assert str(templates.get(key) or "").strip(), (language, key)

    def test_the_writer_is_handed_the_words(self, story, monkeypatch):
        _no_decisions(monkeypatch)
        _relog(story, pell_log=[_pell_post_row(missing=[PELL_LETTER])])
        writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        record = writer.for_mind("Pell Hardacre")[0]["payload"]["record"]
        assert "did not come off" in record[0]["how_it_went"]
        assert PELL_LETTER in record[0]["how_it_went"]


class TestTheOutcomeCheck:
    def test_pells_posted_letter_is_flagged_and_mended(self, story, monkeypatch):
        judge = _Judge(outcome=("So I did", "into the box", "job done neat",
                                "that much I know I did"))
        first = _answer(_episode(PELL_POSTED, rows=[0], consequence=PELL_POSTED_AFTER,
                                 valence=0.3, arousal=0.4))
        mended = _answer(_episode(PELL_MENDED, rows=[0], index=0, valence=-0.8, arousal=0.8))
        result, contents, calls = _run_pell(story, monkeypatch, judge,
                                            [_pell_post_row(missing=[PELL_LETTER])],
                                            first, lambda payload: mended)
        assert len(calls) == 2                      # the writer, then ONE rewrite
        flags = calls[1]["payload"]["rewrite"][0]["flags"]
        assert {f["kind"] for f in flags} == {"outcome"}
        flagged = {f["in"] for f in flags}
        assert "So I did." in flagged
        assert "Straight up the quay, letter in the fist, into the box." in flagged
        assert PELL_POSTED_AFTER in flagged         # the consequence line too
        assert result["rewritten"] == [0]
        assert contents == [PELL_MENDED]

    def test_a_rewrite_that_still_posts_it_loses_those_sentences(self, story, monkeypatch):
        judge = _Judge(outcome=("So I did", "into the box", "job done neat",
                                "that much I know I did"))
        first = _answer(_episode(PELL_POSTED, rows=[0], consequence=PELL_POSTED_AFTER))
        again = _answer(_episode(PELL_POSTED, rows=[0], consequence=PELL_POSTED_AFTER,
                                 index=0))
        result, contents, _calls = _run_pell(story, monkeypatch, judge,
                                             [_pell_post_row(missing=[PELL_LETTER])],
                                             first, lambda payload: again)
        assert "So I did." in result["dropped_sentences"][0]
        assert len(contents) == 1
        assert "into the box" not in contents[0] and "So I did" not in contents[0]
        assert "What stayed with me" not in contents[0]   # the consequence went whole
        assert contents[0].startswith("I brought the Mary Ann in")

    @pytest.mark.parametrize("outcome, reason", [("failed", "not_held"), ("not_known", None)])
    def test_elias_invented_drift_is_flagged(self, story, monkeypatch, outcome, reason):
        """As the live LOG had the row (`failed`/`not_held`), and as it reads
        once a thing in reach counts as to hand (`not_known`: the test's
        verdict is the world's to judge)."""
        judge = _Judge(outcome=("drifted", "drift held", "drifts on the sweep"))
        monkeypatch.setattr(decisions, "OVERRIDE", judge)
        _relog(story, elias_log=[_live_row(0, 6, ELIAS_TEST_DOING, outcome, reason=reason,
                                           room="lamp_room", where_text="The Lamp Room")])
        writer = _Writer({"Pell Hardacre": PELL_PLAIN, "Elias Thorne": lambda system, payload: (
            _answer(_episode(ELIAS_DRIFT, rows=[0], index=0,
                             consequence="The new clockwork drifts on the sweep, and I have "
                                         "it written down."))
        )})
        monkeypatch.setattr(sm, "chat_complete", writer)
        result = sm.run_skip_memories(story["cid"], story["turn"])["Elias Thorne"]
        flags = result["flagged"][0]
        assert {"kind": "outcome", "in": "The timing drifted."} in flags
        assert {"kind": "outcome", "in": "The drift held."} in flags
        assert "The timing drifted." in result["dropped_sentences"][0]
        row = story["db"].q("SELECT content FROM memories WHERE char_id=? AND event_key "
                            "LIKE 'skip:%'", (story["elias"],), one=True)
        assert "drift" not in row["content"]

    def test_a_clean_memory_is_asked_and_passes(self, story, monkeypatch):
        judge = _Judge(outcome=("into the box",), others=("looked at it",),
                       past=("tucked it",))
        clean = _answer(_episode(PELL_MENDED, rows=[0], valence=-0.8, arousal=0.8))
        result, contents, calls = _run_pell(story, monkeypatch, judge,
                                            [_pell_post_row(missing=[PELL_LETTER])],
                                            clean, lambda payload: clean)
        assert len(calls) == 1                      # nothing to rewrite
        assert contents == [PELL_MENDED]
        assert result["flagged"] == {} and result["jev"] == "asked"
        # ...and it WAS asked, all three questions, about the one memory.
        for kind in ("others", "outcome", "past"):
            assert any(PELL_MENDED in state["memory"] and kind in questions
                       for state, questions in judge.requests), kind


class TestTheOthersCheckReadsWith:
    def test_the_question_says_the_record_shows_others_only_in_with(self):
        from llm.prompts import jev_question
        for language in ("en", "ja"):
            for key in ("skip_memory_others", "skip_memory_sentence"):
                text = jev_question(key, language, name="Pell", sentence="x")
                assert "`with`" in text and "`set_about`" in text, (language, key)

    def test_the_yard_man_is_flagged(self, story, monkeypatch):
        """The live miss. The yard man "looks at it" in the boatman's OWN
        stretch -- his plan wrote it -- and in no `with`: nobody saw the yard
        man do anything. A judge that reads the record the way the question
        tells it to: where the question says only `with` shows another
        person, it looks there; where it does not, the whole record shows
        them, and the plan's own words pass the memory."""

        def judge(state, questions):
            out = {}
            whole, placed = _questions(questions, "others")
            if whole is None:
                return out
            only_with = "`with`" in whole["instructions"] and "`set_about`" in whole[
                "instructions"]
            shown = (" ".join(other.get("doing", "") for row in state["record"]
                              for other in row.get("with") or ())
                     if only_with else json.dumps(state["record"]))
            invented = "looks at it" not in shown

            def says(text):
                return invented and "looked at it" in text

            out["others"] = {"type": "noul", "noul": 0.9 if says(state["memory"]) else 0.05}
            prefix = sm.SKIP_MEMORY_QUESTIONS["others"][2]
            for i, sentence in placed.items():
                out[f"{prefix}{i}"] = {"type": "noul", "noul": 0.9 if says(sentence) else 0.05}
            return out

        first = _answer(_episode(PELL_YARD, rows=[0]))
        mended = _answer(_episode(PELL_YARD.replace(
            YARD_MAN, "So I walked the impeller and the fuel line down to the yard man."),
            rows=[0], index=0))
        row = _live_row(4, 10, PELL_KNOCK_DOING, "failed", reason="not_held",
                        room="the_mainland", where_text="the mainland quay and the harbour")
        result, contents, calls = _run_pell(story, monkeypatch, judge, [row], first,
                                            lambda payload: mended)
        assert {"kind": "others", "in": YARD_MAN} in result["flagged"][0]
        assert len(calls) == 2
        assert contents and "looked at it" not in contents[0]


class TestTheLogLine:
    def test_it_says_whether_the_model_was_asked_and_what_it_flagged(self, story,
                                                                     monkeypatch):
        """The live replay's line kept only what was written, so whether its
        check ran could not be read back. It says so now, by kind."""
        lines = []
        monkeypatch.setattr(sm.logger, "info",
                            lambda msg, *args: lines.append(msg % args if args else msg))
        judge = _Judge(others=("barman",))
        monkeypatch.setattr(decisions, "OVERRIDE", judge)
        flagged = _answer(_episode("I asked after the mechanism. " + INVENTED, rows=[2]))
        writer = _Writer({"Elias Thorne": flagged, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        line = next(text for text in lines if text.startswith("skip memories:"))
        summary = json.loads(line.split(" ", 4)[-1])
        assert summary["Elias Thorne"]["jev"] == "asked"
        assert summary["Elias Thorne"]["flags"] == {"others": 1}
        assert summary["Elias Thorne"]["dropped_sentences"] == 1
        assert summary["Pell Hardacre"]["jev"] == "asked"
        assert "flags" not in summary["Pell Hardacre"]


#: The keeper's live memories against rows the executor marked `done`
#: (`skip:25:Elias Thorne:1` and `:3`, word for word): results told past what
#: the record holds of a night watch and of a rotation test.
ELIAS_NIGHT = (
    "Barometer reading at first light, weather logged. Extinguished the lamp, trimmed the "
    "wick, cleaned the chimney and lens with the chamois and the spirit. Breakfast in the "
    "kitchen — bread and tea — then down to the hall to check the stores. The afternoon went "
    "to the mechanism: fitting, testing, adjusting. I filled the reservoir, checked the wick, "
    "set the rotation, and lit the lamp at dusk. Tea and a meal, then back up to check the "
    "lamp before the night watch. Every two hours through the dark, the rotation turning, the "
    "wick burning clean. The clockwork held through the night. I did not sleep much. I never "
    "do when a new thing is turning over my head.")
ELIAS_NIGHT_AFTER = ("The new mechanism has run a full night without fault, and I have logged "
                     "it — but a night is not a storm.")
NIGHT_WATCH_DOING = ("Night watch — the lamp burning, checking rotation and wick every two "
                     "hours, logging weather and any vessel lights seen")
ELIAS_MESHED = (
    "I ran the new clockwork through a full rotation cycle, checking gear engagement and "
    "timing the sweep against the clock. The gear teeth meshed clean. The sweep came round on "
    "the mark. I stood at the pedestal with the clock in my hand and watched it turn, and for "
    "that one cycle it did what it was sent to do. I did not say anything to it. I do not "
    "speak to the new mechanism. But I stood there longer than the test required, watching "
    "the brass go round, and the light was steady, and the sea below was the same sea it has "
    "always been.")
ELIAS_MESHED_AFTER = "One clean cycle is not trust, but it is a fact I can log — and I logged it."
AT_THE_END_DOING = ("Testing the new clockwork through a rotation cycle, checking gear "
                    "engagement and timing the sweep against the clock")


def _scoped_judge(results):
    """The decision model as a reader of the outcome question's own scope.
    Where the question asks only of rows the record marks `failed` or
    `not_known` (it names those codes), a row marked `done` is outside it and
    a result told past it passes; where it asks of every row's
    `how_it_went`, every row is inside. Yes for a sentence telling one of
    `results` -- how a doing turned out -- about a row in scope; a doing
    told as done is never one of them."""

    def judge(state, questions):
        whole, placed = _questions(questions, "outcome")
        if whole is None:
            return {}
        coded = any(code in whole["instructions"] for code in ("`failed`", "`not_known`"))
        in_scope = [row for row in state["record"]
                    if not coded or row["outcome"] in ("failed", "not_known")]

        def says(text):
            return 0.9 if in_scope and any(r in text for r in results) else 0.05

        out = {"outcome": {"type": "noul", "noul": says(state["memory"])}}
        prefix = sm.SKIP_MEMORY_QUESTIONS["outcome"][2]
        for i, sentence in placed.items():
            out[f"{prefix}{i}"] = {"type": "noul", "noul": says(sentence)}
        return out

    return judge


class TestTheOutcomeCheckReachesEveryRow:
    """The coordinator's ruling, 2026-10-21, on the live measurement: a result
    told past ANY row's `how_it_went` goes beyond the record -- the `done`
    words say only that the mind did it (fix lane B3: "did it") -- so the
    outcome check is keyed to `how_it_went`, never to the `failed`/`not_known`
    codes. A routine doing told as done stays clean."""

    @pytest.mark.parametrize("doing, memory, after, results, flagged, clean", [
        (AT_THE_END_DOING, ELIAS_MESHED, ELIAS_MESHED_AFTER,
         ("meshed clean", "came round on the mark", "did what it was sent to do",
          "One clean cycle"),
         ["The gear teeth meshed clean.", "The sweep came round on the mark.",
          ELIAS_MESHED_AFTER],
         "I ran the new clockwork through a full rotation cycle, checking gear engagement "
         "and timing the sweep against the clock."),
        (NIGHT_WATCH_DOING, ELIAS_NIGHT, ELIAS_NIGHT_AFTER,
         ("held through the night", "without fault", "the rotation turning"),
         ["The clockwork held through the night.", ELIAS_NIGHT_AFTER],
         "I filled the reservoir, checked the wick, set the rotation, and lit the lamp at "
         "dusk."),
    ])
    def test_a_result_told_past_a_done_row_is_flagged(self, story, monkeypatch, doing,
                                                      memory, after, results, flagged,
                                                      clean):
        monkeypatch.setattr(decisions, "OVERRIDE", _scoped_judge(results))
        _relog(story, elias_log=[_live_row(0, 6, doing, "done", room="lamp_room",
                                           where_text="The Lamp Room")])
        written = _answer(_episode(memory, rows=[0], consequence=after, index=0))
        writer = _Writer({"Pell Hardacre": PELL_PLAIN,
                          "Elias Thorne": lambda system, payload: written})
        monkeypatch.setattr(sm, "chat_complete", writer)
        result = sm.run_skip_memories(story["cid"], story["turn"])["Elias Thorne"]
        placed = {flag.get("in") for flag in result["flagged"][0] if flag["kind"] == "outcome"}
        for sentence in flagged:
            assert sentence in placed, sentence
        assert clean not in placed                  # the doing, told as done
        row = story["db"].q("SELECT content FROM memories WHERE char_id=? AND event_key "
                            "LIKE 'skip:%'", (story["elias"],), one=True)
        assert clean in row["content"]
        for sentence in flagged:
            assert sentence not in row["content"]

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_question_is_keyed_to_how_it_went_never_to_the_codes(self, language):
        from llm.prompts import jev_question
        for key in sm.SKIP_MEMORY_QUESTIONS["outcome"][:2]:
            text = jev_question(key, language, name="Elias", sentence="x")
            assert "`how_it_went`" in text, key
            assert "`failed`" not in text and "`not_known`" not in text, key

    @pytest.mark.parametrize("language, done", [
        ("en", "anything else Elias did as done"),
        ("ja", "ほかにEliasがしたことはしたこととして"),
    ])
    def test_a_routine_doing_told_as_done_is_named_clean(self, language, done):
        """The complement, stated where the question says no: what the mind
        did is told as done; only what did not come off, and how any doing
        turned out, go past the record."""
        from llm.prompts import jev_question
        for key in sm.SKIP_MEMORY_QUESTIONS["outcome"][:2]:
            assert done in jev_question(key, language, name="Elias", sentence="x"), key

    @pytest.mark.parametrize("language, told", [
        ("en", "is told as done"), ("ja", "したこととして語ります")])
    def test_the_cards_take_every_row_as_far_as_its_how_it_went(self, language, told):
        system = sm.writer_system("Elias Thorne", 4, language, rewrite=True)
        flag = next(line for line in system.splitlines()
                    if line.startswith("- ") and "`outcome`" in line)
        assert "`how_it_went`" in flag
        assert "`failed`" not in flag and "`not_known`" not in flag
        bullet = next(line for line in system.splitlines()
                      if line.startswith("- ") and "`how_it_went`" in line
                      and "`outcome`" not in line)
        assert told in bullet
