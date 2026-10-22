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
        assert set(rows[0]) <= {"n", "when", "where", "did", "asleep", "with",
                                "weather", "outcome", "reason"}
        assert rows[0]["with"] == [{"who": "Rhona Carrick", "doing": "working at the gear train"}]
        assert set(sm.SEEN_FIELDS) == {"who", "doing"}

    def test_the_mind_pass_never_reaches_for_a_plan_or_the_account(self):
        """Asked of the parsed functions, as `test_offscreen_agent_context`
        asks it: the names, attributes and string keys the bodies can reach."""
        tree = ast.parse(inspect.getsource(sm))
        for fname in ("remember_one", "writer_payload", "record_rows", "memory_packet",
                      "card_of", "_jev_state"):
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
        seen_states = []

        def answer(state, questions):
            if "others" in questions or any(k.startswith("s") and k[1:].isdigit()
                                            for k in questions):
                seen_states.append(state)
                return {k: {"type": "noul", "noul": 0.0} for k in questions}
            return {}

        monkeypatch.setattr(decisions, "OVERRIDE", answer)
        writer = _Writer({"Elias Thorne": ELIAS_PLAIN, "Pell Hardacre": PELL_PLAIN})
        monkeypatch.setattr(sm, "chat_complete", writer)
        sm.run_skip_memories(story["cid"], story["turn"])
        assert seen_states
        for state in seen_states:
            assert set(state) == {"name", "record", "memory"}
            blob = json.dumps(state)
            for secret in (SECRET_OWN_WHY, SECRET_PROSE, SECRET_OTHER_WHY):
                assert secret not in blob


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
        many = _answer(*[_episode("I tended the lamp on the %s watch." % w, rows=[0])
                         for w in ("first", "second", "third", "fourth", "fifth", "sixth")])
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
        for key in ("n", "when", "where", "did", "asleep", "with", "weather", "outcome",
                    "reason", "done", "failed", "not_known"):
            assert "`%s`" % key in system, key
        for key in ("rows", "memory", "consequence", "valence", "arousal"):
            assert '"%s"' % key in system, key

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_rewrite_pass_names_its_flags(self, language):
        system = sm.writer_system("Elias Thorne", 4, language, rewrite=True)
        assert system.count("Elias Thorne") >= 2
        for key in ("rewrite", "index", "flags", "number", "others", "said", "in"):
            assert "`%s`" % key in system, key
        assert '"index"' in system

    @pytest.mark.parametrize("pid", ["prompts.skip_memory", "prompts.skip_memory_rewrite",
                                     "jev_questions.skip_memory_others",
                                     "jev_questions.skip_memory_sentence"])
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
    def test_the_two_questions_are_the_packs(self, language):
        from llm.prompts import jev_question
        assert "Elias" in jev_question("skip_memory_others", language, name="Elias")
        sentence = jev_question("skip_memory_sentence", language, name="Elias",
                                sentence="The barman noticed.")
        assert "Elias" in sentence and sentence.rstrip().endswith("The barman noticed.")

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
