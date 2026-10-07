"""The question chooses its search (`mind/memory_routes.py`, the owner
2026-10-06: "we can have alt search engines specialized for different
lookups"; "With jev we don't even need the llm to think about the question
type or field").

A ponder ranks by relevance, and "first" is a memory's place among the ones
that match, not anything in its content. So the decision model reads the
question alone and says what it asks for; code resolves the subject and runs
the search built for it, and decides the order. Pinned here: each search finds
the moment by the rule it is built on (a tag, a name said, a place, a verified
walk in time order), never the more relevant later row; the moment comes back
marked, with the turns around it; and routing only ADDS -- off, unasked,
failed, or not about the past, the ponder is the graded ponder alone.
"""

from __future__ import annotations

import json
import threading
import time

import numpy as np
import pytest

from llm import decisions
from llm.providers import EmbeddingBatch
from story.character_schema import default_character_data
from tests.helpers import patch_provider_seam

DIM = 48
OREN, ILSE, WREN = "Oren Dask", "Ilse Harrow", "Wren"
PERSON = {"name": "Mara", "drive": "keep the crossing open", "values": ["the river over the council"]}


def _vector(text):
    v = np.zeros(DIM, dtype=np.float32)
    for word in str(text or "").lower().split():
        v[sum(map(ord, word.strip(".,:;!?'\""))) % DIM] += 1.0
    return v / (float(np.linalg.norm(v)) or 1.0)


@pytest.fixture
def embeddings(monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", lambda texts, **_kw: EmbeddingBatch(
        vectors=[_vector(t) for t in texts], model_key="test-words", dimensions=DIM))


@pytest.fixture
def mind(temp_db, embeddings):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                         ("Mara", json.dumps(default_character_data("Mara")), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    return chat_id, char_id


def _mint(mind, turn, content, *, about=(), location="", char_id=None, kind="episodic", key=None):
    """One memory row. `key` tells apart rows that share a turn and kind -- a
    seeded past is many rows at one pseudo-turn, and the event key is what
    the write upserts on."""
    from mind.memory import add_memories_batch
    chat_id, own = mind
    who = char_id or own
    return add_memories_batch([{
        "chat_id": chat_id, "char_id": who, "turn_id": None, "turn_idx": turn, "kind": kind,
        "category": "episode" if kind == "episodic" else "inference",
        "provenance": "witnessed" if kind == "episodic" else "inferred", "salience": 0.6,
        "content": content, "event_key": f"event:{who}:{turn}:{kind}{':' + key if key else ''}",
        "about": list(about), "location": location, "encoded_at_seconds": float(turn) * 600.0}])[0]


class Jev:
    """The decision model, as a test: the router answers `route`; a ponder
    grade is strong where `graded` stands in the row; a verification is yes
    where a word of `yes` stands in it -- 0.9 sure, or as sure as `yes` maps
    the word to. Every request is recorded (from two threads: the router runs
    beside the grade)."""

    def __init__(self, route=None, *, graded="", yes=(), past=0.9, fail_route=False):
        self.route = route or {}
        self.yes = dict(yes) if isinstance(yes, dict) else {w: 0.9 for w in yes}
        self.graded, self.past, self.fail_route = graded, past, fail_route
        self.calls, self._lock = [], threading.Lock()

    def __call__(self, state, questions):
        with self._lock:
            self.calls.append((state, dict(questions)))
        if self.fail_route and "route:order" in questions:
            raise decisions.DecisionError("jev 503: unavailable")
        out = {}
        for key, q in questions.items():
            text = q["instructions"]
            if key == "route:order":
                probs = {self.route.get("order", "content"): 0.8}
            elif key == "route:kind":
                probs = {self.route.get("kind", "act"): 0.8}
            elif key == "route:past":
                probs = {"yes": self.past, "no": 1.0 - self.past}
            elif key == "route:who":
                want = self.route.get("who")
                hit = next((k for k, label in q["criteria"].items() if want and label.startswith(want)), "none")
                probs = {hit: 0.8}
            elif key.startswith("moment:"):
                p = max([share for word, share in self.yes.items() if word in text] or [0.1])
                probs = {"yes": p, "no": 1.0 - p}
            else:
                strong = bool(self.graded) and self.graded in text
                probs = {"strong": 0.9, "clear": 0.1} if strong else {"none": 0.9, "slight": 0.1}
            out[key] = {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs}
        return out

    def asked(self, prefix):
        return [(s, k, q) for s, qs in self.calls for k, q in qs.items() if k.startswith(prefix)]


def _ponder(mind, query, *, turn=60, about=(), known=(), asked_by=None, record=None):
    from llm.providers import embed_texts_meta
    from mind.memory import jev_ponder_packet
    chat_id, char_id = mind
    return jev_ponder_packet(chat_id, char_id, query, current_turn_idx=turn,
                             embedded=embed_texts_meta([query]), person=PERSON, about=about,
                             known=[k.casefold() for k in known], asked_by=asked_by,
                             record=record if record is not None else {})


def _found(rows):
    return [r for r in rows if r.get("in_time")]


def _turns(rows):
    return [r.get("turn_idx") for r in rows]


# ---- reading the router --------------------------------------------------------------------

def test_the_router_reads_its_most_likely_answers_and_the_past_gate():
    from mind.memory import read_route
    answers = {"route:order": {"probabilities": {"earliest": 0.4, "content": 0.35, "latest": 0.25}},
               "route:kind": {"probabilities": {"met": 0.5, "act": 0.5}},
               "route:who": {"probabilities": {"p1": 0.6, "none": 0.4}},
               "route:past": {"probabilities": {"yes": 0.7, "no": 0.3}}}
    assert read_route(answers, [OREN, WREN]) == {"order": "earliest", "kind": "met", "who": WREN}
    answers["route:past"] = {"probabilities": {"yes": 0.3, "no": 0.7}}
    assert read_route(answers, [OREN, WREN])["order"] == "content", \
        "a plan or a place read as 'before' is not routed"
    assert read_route({}, [])["order"] == "content"


def test_the_one_asking_is_labelled_and_no_one_is_a_choice():
    from mind.memory import route_questions
    qs = route_questions([OREN, WREN], "en", asker=WREN)
    assert set(qs) == {"route:order", "route:kind", "route:past", "route:who"}
    who = qs["route:who"]["criteria"]
    assert who["p0"] == OREN and who["p1"].startswith(WREN) and who["p1"] != WREN and "none" in who
    assert "route:who" not in route_questions([], "en")


def test_a_place_is_named_by_all_its_words_and_a_name_in_japanese_by_where_it_stands():
    from mind.memory import named_in
    from mind.memory import names_place
    assert names_place("What happened your first night at the Lantern Inn?", "Lantern Inn")
    assert not names_place("When did you first light the green lantern?", "Lantern Inn")
    assert names_place("ランタン亭で初めて過ごした夜", "ランタン亭")
    assert named_in("オレンに初めて会ったのはいつ？", ["オレン・ダスク", "イルゼ・ハロウ"]) == ["オレン・ダスク"]
    assert named_in("When did you first meet Oren?", [OREN, ILSE]) == [OREN]
    assert named_in("オレンジを一つ買った。", ["オレン・ダスク"]) == [], "an orange is not Oren"
    assert named_in("オレンダスクの店で。", ["オレン・ダスク"]) == ["オレン・ダスク"], "the name without its dot"
    assert named_in("田中先生に会った。", ["田中"]) == ["田中"], "an honorific attaches to a kanji name"


# ---- the searches -------------------------------------------------------------------------

def test_met_is_the_first_row_with_them_in_it_not_the_first_that_says_the_name(mind, monkeypatch):
    _mint(mind, 2, "Aldous said whoever buys Oren Dask's green lanterns worries the council.",
          about=["Aldous Toller"], location="Dock Office")
    _mint(mind, 5, "A man held up a green lantern: you'll be wanting the green one, then.",
          about=[OREN], location="East Landing")
    _mint(mind, 8, "I met Oren Dask at the inn again and we talked about lanterns, and I met his eye.",
          about=[OREN], location="Lantern Inn")
    jev = Jev({"order": "earliest", "kind": "met", "who": OREN}, yes=("wanting the green one",))
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    rows = _ponder(mind, "When did you first meet Oren?", about=[OREN], known=[OREN, WREN])
    found = _found(rows)
    assert _turns(found) == [5], "the tag says who was there; the later row only sounds more like it"
    assert found[0]["in_time"] == "the earliest moment I remember with Oren Dask"
    assert rows[0]["turn_idx"] == 5 and 8 in _turns(rows), "the moment first, then the turns after it"
    asked = [q["instructions"] for _s, _k, q in jev.asked("moment:")]
    met = [text for text in asked if text.startswith("Do you see or meet")]
    assert len(met) == 1 and "Aldous" in met[0], \
        "the row that only says his name before he is first seen is asked -- a first meeting may be heard"
    assert any("wanting the green one" in text for text in asked if text not in met), \
        "and the moment found is confirmed against the question"


def test_a_bank_with_no_tags_still_finds_the_meeting_by_asking(mind, monkeypatch):
    _mint(mind, 2, "Aldous said whoever buys Oren Dask's green lanterns worries the council.")
    _mint(mind, 5, "A man stepped out with a lantern and gave his name, Oren Dask.")
    _mint(mind, 8, "Oren Dask met me at the inn again.")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": OREN},
                                                   yes=("stepped out", "met me")))
    assert _turns(_found(_ponder(mind, "When did you first meet Oren?", about=[OREN], known=[OREN]))) == [5]


def test_a_seeded_past_is_asked_about_since_no_tag_can_reach_it(mind, monkeypatch):
    """Somebody the mind knew before the story is first met in its seeded
    past, which never carries a tag (`PRESTORY_TURN_IDX`)."""
    from mind.memory import PRESTORY_TURN_IDX
    _mint(mind, PRESTORY_TURN_IDX, "The winter I was seven I pulled Ilse Harrow out of the river ice.")
    _mint(mind, 3, "Ilse Harrow came to the boathouse with bread.", about=[ILSE])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": ILSE},
                                                   yes=("river ice",)))
    found = _found(_ponder(mind, "How long have you known Ilse?", about=[ILSE], known=[ILSE]))
    assert _turns(found) == [PRESTORY_TURN_IDX]


def test_the_last_time_seen_is_the_last_row_with_them_in_it_not_the_last_mention(mind, monkeypatch):
    _mint(mind, 5, "Oren Dask handed me the lantern.", about=[OREN])
    _mint(mind, 8, "Oren Dask lifted a hand from the stern of the Moth.", about=[OREN])
    _mint(mind, 12, "No word from Oren Dask since the Moth went downriver.", about=[WREN])
    jev = Jev({"order": "latest", "kind": "met", "who": OREN}, yes=("stern of the Moth", "No word from"))
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    found = _found(_ponder(mind, "When did you last see Oren?", about=[OREN], known=[OREN, WREN]))
    assert _turns(found) == [8], "the later row says his name and has him nowhere in it"
    assert found[0]["in_time"] == "the most recent moment I remember with Oren Dask"
    assert not any("No word from" in q["instructions"] for _s, _k, q in jev.asked("moment:"))


def test_a_last_time_is_the_moment_not_what_was_concluded_from_it(mind, monkeypatch):
    """"When did you last see Oren?" was marked on Mara's conclusion that he
    meant never to come back -- written the same turn as the sighting, after
    it -- in all three runs of 2026-10-06: newest first had reversed the turn's
    own order too, and the conclusion carries the turn's tags."""
    _mint(mind, 5, "Oren Dask handed me the lantern.", about=[OREN])
    _mint(mind, 8, "Oren Dask lifted a hand from the stern of the Moth and went downriver.", about=[OREN])
    _mint(mind, 8, "I concluded that Oren Dask means never to come back up the river.", about=[OREN],
          kind="inference")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "latest", "kind": "met", "who": OREN},
                                                   yes=("Oren Dask",)))
    found = _found(_ponder(mind, "When did you last see Oren?", about=[OREN], known=[OREN, WREN]))
    assert len(found) == 1 and "stern of the Moth" in found[0]["content"]


def test_a_walk_never_takes_a_conclusion_for_the_moment(mind, monkeypatch):
    """"What were the last words you said to Oren?" walked newest first past
    his departure (read under the floor) to Mara's conclusion that he was not
    coming back (over it), and never reached the words themselves (2026-10-06,
    every run): a conclusion row is asked and kept with its turn, never taken."""
    _mint(mind, 12, "Oren Dask on the landing; I said keep your purse, Oren, my crossing is not for sale.",
          about=[OREN])
    _mint(mind, 20, "Oren Dask lifted a hand from the stern of the Moth and went downriver.", about=[OREN])
    _mint(mind, 20, "I concluded that Oren Dask means never to come back up the river.", about=[OREN],
          kind="inference")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "latest", "kind": "act", "who": OREN},
                                                   yes={"stern of the Moth": 0.75, "I concluded": 0.85,
                                                        "my crossing is not for sale": 0.98}))
    found = _found(_ponder(mind, "What were the last words you said to Oren?", about=[OREN], known=[OREN]))
    assert _turns(found) == [12]


def test_the_last_time_at_a_place_asks_about_the_visit_before_its_conclusion(mind, monkeypatch):
    """"The last time you were inside the chapel" confirmed the conclusion
    written after the right visit (0.01) and walked on to an older one
    (2026-10-06): the visit itself is the row asked first."""
    _mint(mind, 3, "I went up to the chapel to light a candle for Petra.", location="Chapel")
    _mint(mind, 9, "In the vestry the sexton showed me the painted saint.", location="Chapel")
    _mint(mind, 9, "I concluded the sexton knows more than he says.", location="Chapel", kind="inference")
    # The visit reads between the confirmation's floor and the walk's, as the
    # real one did (0.53-0.67): confirmed, it is found; refused, the walk
    # passes it by for the older visit.
    jev = Jev({"order": "latest", "kind": "place"}, yes={"painted saint": 0.7, "light a candle": 0.9})
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    found = _found(_ponder(mind, "When were you last at the Chapel?"))
    asked = jev.asked("moment:")
    assert "painted saint" in asked[0][2]["instructions"], "the visit, not the conclusion, is confirmed"
    assert len(found) == 1 and "painted saint" in found[0]["content"]


def test_a_last_time_in_a_seeded_past_is_its_newest_memory(mind, monkeypatch):
    """A seeded past shares one pseudo-turn, its rows separate moments in the
    order they were minted: newest first walks them newest-minted first
    (review, 2026-10-06 -- a beat's own order had walked it oldest first)."""
    _mint(mind, -1, "As children Ilse Harrow and I set eel traps in the side channels.", key="past:1")
    _mint(mind, -1, "The winter Petra died, Ilse Harrow sat up with me at the wake.", key="past:2")
    jev = Jev({"order": "latest", "kind": "met", "who": ILSE}, yes=("Ilse Harrow",))
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    found = _found(_ponder(mind, "When did you last see Ilse?", about=[ILSE], known=[ILSE]))
    assert len(found) == 1 and "wake" in found[0]["content"]


def test_a_seeded_memory_never_ties_a_story_moment(mind, monkeypatch):
    """A seeded row sits at turn -1, three turns from turn 2 by arithmetic and
    no moment of the story's at all: it ties nothing but itself."""
    _mint(mind, -1, "Long ago the old mill burned once before, when I was a girl.")
    _mint(mind, 2, "In the night the old mill burned and I dragged sacks out of the smoke.")
    _mint(mind, 3, "At dawn Bram's burned hands were bound.")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "after", "kind": "act"},
                                                   yes={"burned once before": 0.94, "dragged sacks": 0.97}))
    assert _turns(_found(_ponder(mind, "What happened right after the mill fire?"))) == [2]


def test_a_walk_is_cut_by_time_so_a_plain_first_time_is_kept(temp_db, monkeypatch):
    """"The first time you lied to Ilse" lost the lie itself -- a plain row,
    ranked below thirty later rows that say it outright -- when the walk was
    cut to the nearest 24 instead of the first 24 in time (measured
    2026-10-06, every run). The cut by time stays; what it costs (a first
    time late in the story) is in `docs/UNBUILT_CHARACTERS.md`."""
    from mind.memory import VERIFY_LIMIT, answer
    mems = {}

    def row(mid, turn, text):
        mems[mid] = {"id": mid, "turn_idx": turn, "content": text, "kind": "episodic",
                     "encoded_at_seconds": float(turn) * 600.0, "about": [], "location": ""}
    for i, t in enumerate(range(1, 10)):
        row(100 + i, t, f"Rain on the landing, day {t}.")
    row(200, 20, "The heel of the loaf was gone from the shelf.")
    for i, t in enumerate(range(30, 60)):
        row(300 + i, t, f"Bread went missing off the shelf again, day {t}.")
    nearest = [300 + i for i in range(30)] + [200] + [100 + i for i in range(9)]
    monkeypatch.setattr(decisions, "OVERRIDE", Jev(yes={"heel of the loaf": 0.9, "Bread went missing": 0.9}))
    record = {}
    found = answer({"order": "earliest", "kind": "act", "who": None},
                      "When did bread first start going missing off your shelf?",
                      memories=mems, vectors={}, lanes={"semantic": nearest, "cue": nearest, "keyword": nearest},
                      embedded=None, known=(), places=[], current_turn_idx=70, record=record)
    assert found and found[0]["turn_idx"] == 20 and found[0].get("in_time")
    asked = record["asked_turns"][0]
    assert len(asked) == VERIFY_LIMIT and asked == sorted(asked) and 20 in asked


def test_a_last_act_at_a_named_place_keeps_the_turns_own_order(temp_db, monkeypatch):
    """The place walk's "ahead" compared rows oldest first, so for a last time
    a row written later in the same turn (here what the mind noted about
    itself, written after the moment) counted as ahead of the moment and won
    (review, 2026-10-06): ahead is read in the walk's own order."""
    from mind.memory import answer
    mems = {}

    def row(mid, turn, text, kind="episodic"):
        mems[mid] = {"id": mid, "turn_idx": turn, "content": text, "kind": kind,
                     "encoded_at_seconds": float(turn) * 600.0, "about": [], "location": "Chapel"}
    row(1, 3, "I lit a candle for Petra at the Chapel.")
    row(2, 9, "In the Chapel I knelt and prayed for Ilse.")
    row(3, 9, "I noted that prayer in the Chapel steadies me.")
    nearest = [3, 1]    # the walk over everything never meets the moment itself
    monkeypatch.setattr(decisions, "OVERRIDE", Jev(yes={"knelt and prayed": 0.9, "prayer in the Chapel": 0.9}))
    found = answer({"order": "latest", "kind": "act", "who": None}, "When did you last pray at the Chapel?",
                   memories=mems, vectors={}, lanes={"semantic": nearest, "cue": nearest, "keyword": nearest},
                   embedded=None, known=(), places=["Chapel"], current_turn_idx=20)
    assert found and found[0]["id"] == 2 and found[0].get("in_time")


def test_first_heard_of_is_the_first_row_that_says_the_name(mind, monkeypatch):
    _mint(mind, 2, "Aldous said whoever buys Oren Dask's green lanterns worries the council.")
    _mint(mind, 5, "Oren Dask handed me the lantern.", about=[OREN])
    jev = Jev({"order": "earliest", "kind": "heard_of", "who": OREN}, yes=("whoever buys",))
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    found = _found(_ponder(mind, "When did you first hear the name Oren Dask?", about=[OREN], known=[OREN]))
    assert _turns(found) == [2]
    assert len(jev.asked("moment:")) == 1, "found by code, confirmed once"


def test_a_first_heard_row_is_confirmed_as_hearing_of_it(mind, monkeypatch):
    """A row where a name is only talked about is exactly a first-heard one;
    the moment question sets "only talked about" aside, so it is confirmed by
    the heard question (review, 2026-10-06)."""
    _mint(mind, 2, "Aldous said whoever buys Oren Dask's green lanterns worries the council.")
    _mint(mind, 5, "Oren Dask handed me the lantern.", about=[OREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "heard_of", "who": OREN},
                                                   yes={"Do you hear of": 0.9}))
    record = {}
    found = _found(_ponder(mind, "When did you first hear the name Oren Dask?", about=[OREN], known=[OREN],
                           record=record))
    assert _turns(found) == [2] and record["route"]["confirmed"] >= 0.6


def test_a_place_is_the_first_or_last_row_made_there(mind, monkeypatch):
    _mint(mind, 3, "I lit the green lantern at the bow.", location="Heron")
    _mint(mind, 7, "Caught by the curfew I took a room at the Lantern Inn.", location="Lantern Inn")
    _mint(mind, 8, "A night of rain on the inn's roof.", location="Lantern Inn")
    _mint(mind, 20, "Breakfast in the common room of the Lantern Inn again.", location="Lantern Inn")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "place"},
                                                   yes=("took a room",)))
    rows = _ponder(mind, "What happened your first night at the Lantern Inn?")
    assert _turns(_found(rows)) == [7] and 8 in _turns(rows)
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "latest", "kind": "place"}, yes=("Breakfast",)))
    assert _turns(_found(_ponder(mind, "When were you last at the Lantern Inn?"))) == [20]


def test_an_act_at_a_named_place_is_walked_among_the_rows_made_there(mind, monkeypatch):
    """The router read "your first night at the Lantern Inn" as an act, not
    a place (2026-10-06): the walk still keeps to the place it names, and a
    visit somewhere else that the model takes for it never wins."""
    _mint(mind, 3, "Wren went into the Lantern Inn and came out: full, no bed.", location="East Landing")
    _mint(mind, 7, "Caught by the curfew I took a room at the Lantern Inn.", location="Lantern Inn")
    _mint(mind, 8, "A night of rain on the inn's roof.", location="Lantern Inn")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act"},
                                                   yes=("into the Lantern Inn", "took a room")))
    assert _turns(_found(_ponder(mind, "What happened your first night at the Lantern Inn?"))) == [7]


def test_an_earlier_sure_moment_at_the_named_place_wins_however_sure_a_later_one(mind, monkeypatch):
    """Order decides between sure moments: the place's own first, against a
    later one elsewhere the walk among the nearest rows found -- the place's
    plainer row never reached that walk, eighty nearer ones did."""
    _mint(mind, 6, "Supper there, our first, the eel stew.", location="Lantern Inn")
    for t in range(10, 90):
        _mint(mind, t, f"When did we first eat, first eat a meal, eat first again, number {t}?", location="Boathouse")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act"},
                                                   yes={"Supper there": 0.85, "first eat a meal": 0.99}))
    assert _turns(_found(_ponder(mind, "When did you first eat at the Lantern Inn?", turn=95))) == [6]


def test_a_first_sight_from_elsewhere_keeps_its_place_against_a_later_one_there(mind, monkeypatch):
    """The place's own moment wins only on the right side in time, or over a
    row that merely names it: a first sight from the river, before any visit,
    stays the first."""
    _mint(mind, 2, "From the river at dusk I saw the inn's lit windows for the first time.", location="Heron")
    _mint(mind, 8, "Inside the Lantern Inn for supper, the windows lit.", location="Lantern Inn")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act"},
                                                   yes={"lit windows": 0.9, "windows lit": 0.9}))
    assert _turns(_found(_ponder(mind, "When did you first see the Lantern Inn?"))) == [2]


def test_a_place_mark_names_the_place_whoever_the_router_chose(mind, monkeypatch):
    """The place path marks with the place: "being at Oren Dask" was what a
    person the router also picked made of it."""
    _mint(mind, 7, "Caught by the curfew I took a room at the Lantern Inn.", location="Lantern Inn", about=[OREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "place", "who": OREN},
                                                   yes=("took a room",)))
    found = _found(_ponder(mind, "What happened my first night at the Lantern Inn, with Oren there?",
                           about=[OREN], known=[OREN]))
    assert found[0]["in_time"] == "the earliest I remember being at Lantern Inn"


def test_a_place_the_question_only_names_never_hides_the_moment_made_elsewhere(mind, monkeypatch):
    """"When did you last fix the Heron's rudder?" names the ferry, a place
    Mara stands aboard; the repair was made ashore (2026-10-06)."""
    _mint(mind, 10, "Rain on the river; I poled six crossings.", location="Heron")
    _mint(mind, 20, "In the boathouse I fitted a new pin to the Heron's rudder oar.", location="Boathouse")
    _mint(mind, 30, "A shepherd's ewes crowded the Heron's rudder end all the way over.", location="Heron")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "latest", "kind": "act"},
                                                   yes={"new pin": 0.96, "rudder end": 0.7}))
    assert _turns(_found(_ponder(mind, "When did you last fix the Heron's rudder?"))) == [20]


def test_an_act_is_never_narrowed_to_the_one_asking_because_the_router_chose_them(mind, monkeypatch):
    """"When did you first light the green lantern?" came back as about Wren;
    Mara lit it alone (2026-10-06)."""
    _mint(mind, 5, "Alone on the slip I lit the green lantern for the first crossing after curfew.")
    _mint(mind, 9, "Wren watched me light the green lantern again.", about=[WREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act", "who": WREN},
                                                   yes=("lit the green lantern", "light the green lantern")))
    assert _turns(_found(_ponder(mind, "When did you first light the green lantern?",
                                 known=[WREN], asked_by=WREN))) == [5]


def test_a_walk_takes_no_moment_the_model_is_only_half_sure_of(mind, monkeypatch):
    """The green lights on the river read 0.50, then 0.64, for "when did you
    first see the river serpent?" -- there is none (2026-10-06)."""
    _mint(mind, 12, "Green lights blinked on the black river and went dark.")
    _mint(mind, 13, "Goats across before noon.")
    record = {}
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act"},
                                                   yes={"Green lights": 0.64}))
    rows = _ponder(mind, "When did you first see the river serpent?", record=record)
    assert not _found(rows) and record["route"]["found"] is False


def test_a_refused_first_meeting_still_walks_the_named_persons_own_rows(mind, monkeypatch):
    """Chat 74 (2026-10-06): "the night I first met Hinami -- her very first
    words to me" read as a meeting; her first tagged row (the landing, no
    words yet) was rightly refused, and the walk must still keep to her rows
    and hold her earliest, where her first words are, a turn later."""
    _mint(mind, 0, "The young woman lay on the sand within arm's reach.", about=[ILSE])
    _mint(mind, 1, "I heard the young woman say: \"W-who are you?\"", about=[ILSE])
    for t in range(2, 60):
        _mint(mind, t, f"Ilse Harrow and I met on the shore again and her words were warm, meeting {t}.",
              about=[ILSE])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": ILSE},
                                                   yes=("W-who are you", "her words were")))
    query = "The night I first met Ilse Harrow -- her very first words to me"
    assert _turns(_found(_ponder(mind, query, about=[ILSE], known=[ILSE], turn=70))) == [1]


def test_a_first_meeting_only_heard_is_found_before_the_first_sight(mind, monkeypatch):
    """A tag is sight alone (since b824a8a2); a first meeting in the dark,
    by voice, says the name and carries no tag."""
    _mint(mind, 3, "In the dark of the loft a voice said: \"I'm Tobin Reyes. Don't shout.\"")
    _mint(mind, 6, "By lamplight I saw Tobin Reyes at last, thin, in a torn blue coat.", about=["Tobin Reyes"])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": "Tobin Reyes"},
                                                   yes=("I'm Tobin Reyes",)))
    assert _turns(_found(_ponder(mind, "When did you first meet Tobin?", about=["Tobin Reyes"],
                                 known=["Tobin Reyes"]))) == [3]


def test_a_refused_seeded_meeting_still_tries_the_first_tagged_one(mind, monkeypatch):
    """Two moments code found, confirmed in turn: the seeded row that only
    names her is refused, and the first row with her in it is not."""
    from mind.memory import PRESTORY_TURN_IDX
    _mint(mind, PRESTORY_TURN_IDX, "Petra once said Ilse Harrow's family came from the marsh.")
    _mint(mind, 4, "Ilse Harrow stepped aboard and shook my hand.", about=[ILSE])
    jev = Jev({"order": "earliest", "kind": "met", "who": ILSE},
              yes={"Petra once said": 0.85, "shook my hand": 0.9})
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    record = {}

    def refuse_petra(state, questions):
        out = jev(state, questions)
        for key, q in questions.items():       # confirmed against the question, Petra's row is not the meeting
            if (len(questions) == 1 and "Petra once said" in q["instructions"]
                    and q["instructions"].startswith("Does what the question asks about")):
                out[key] = {"type": "choice", "probabilities": {"yes": 0.1, "no": 0.9}}
        return out
    monkeypatch.setattr(decisions, "OVERRIDE", refuse_petra)
    assert _turns(_found(_ponder(mind, "When did you first meet Ilse?", about=[ILSE], known=[ILSE],
                                 record=record))) == [4]


def test_a_found_moment_that_is_not_the_one_asked_about_is_dropped(mind, monkeypatch):
    """"When did you first see the river serpent?" came back as meeting the
    one asking (2026-10-06); her arrival is the first row with her in it, and
    is no serpent. Asked once, it is not it, and nothing in the bank is."""
    _mint(mind, 1, "Wren came aboard the last evening ferry, soaked.", about=[WREN])
    _mint(mind, 2, "Goats and a cart across before noon.", about=[WREN])
    jev = Jev({"order": "earliest", "kind": "met", "who": WREN}, yes=("serpent",))
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    record = {}
    rows = _ponder(mind, "When did you first see the river serpent?", known=[WREN], asked_by=WREN,
                   record=record)
    assert not _found(rows) and record["route"]["confirmed"] < 0.5 and record["route"]["found"] is False


def test_a_weak_early_yes_never_beats_the_moment(mind, monkeypatch):
    """Uncalibrated yes-shares: an ordinary visit read 0.55 for the first lie
    to Ilse (2026-10-06); the lie itself 0.95. Below `WALK_FLOOR`, never it."""
    _mint(mind, 3, "Ilse Harrow came to the boathouse with bread.", about=[ILSE])
    _mint(mind, 11, "I told Ilse Harrow I had seen no one near the boathouse.", about=[ILSE])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act", "who": ILSE},
                                                   yes={"with bread": 0.55, "seen no one": 0.95}))
    assert _turns(_found(_ponder(mind, "When was the first time you lied to Ilse?",
                                 about=[ILSE], known=[ILSE]))) == [11]


def test_a_persons_earliest_rows_are_held_however_far_from_the_question(mind, monkeypatch):
    """The meeting is early and plain; sixty later rows say "Oren's first
    words" in so many words. The walk holds the person's own earliest rows
    beside the nearest, or the meeting never reaches it."""
    _mint(mind, 5, "A man held up a green lantern: you'll be wanting the green one, then.", about=[OREN])
    for t in range(20, 80):
        _mint(mind, t, f"Oren's very first words to you, said Oren Dask again, were what were they {t}?",
              about=[OREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act", "who": OREN},
                                                   yes=("wanting the green one", "said Oren Dask")))
    assert _turns(_found(_ponder(mind, "What were Oren's very first words to you?",
                                 about=[OREN], known=[OREN], turn=90))) == [5]


def test_a_walk_with_no_subject_is_walked_in_time_order(mind, monkeypatch):
    """The nearest row is the later one; the walk still takes the first."""
    _mint(mind, 5, "At the bow I lit it, the green lamp, before the crossing.")
    _mint(mind, 30, "I lit the green lantern, the green lantern again, lit the green lantern at the bow.")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act"},
                                                   yes=("lit it, the green lamp", "lit the green lantern")))
    assert _turns(_found(_ponder(mind, "When did you first light the green lantern?"))) == [5]


def test_a_near_tie_for_the_moment_goes_to_the_earlier(mind, monkeypatch):
    """"Right after the mill fire" read the dawn after it 0.93 and the fire
    0.92 (2026-10-06): within the model's own noise, and the moment is the
    one that came first."""
    _mint(mind, 30, "In the night the old mill burned and I dragged sacks out of the smoke.")
    _mint(mind, 31, "At dawn the town gathered talking of the mill fire.")
    _mint(mind, 32, "Bram burned his hands.")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "after", "kind": "act"},
                                                   yes={"mill burned": 0.92, "mill fire": 0.93}))
    rows = _ponder(mind, "What happened right after the mill fire?")
    assert _turns(_found(rows)) == [30] and {31, 32} <= set(_turns(rows))


def test_a_near_tie_reaches_the_three_turns_between_the_fire_and_the_dawn(mind, monkeypatch):
    """The mill fire (turn 140) and the dawn after it (143) stand three turns
    apart on the Saltmere bank, and the dawn reads a little surer in 8 of 13
    captured decisions: `TIE_REACH` is 3, its own number, so a smaller packet
    span cannot move which moment is found (review, 2026-10-06)."""
    _mint(mind, 30, "In the night the old mill burned and I dragged sacks out of the smoke.")
    _mint(mind, 33, "At dawn the town gathered at the landing talking of the mill fire.")
    for t, text in ((34, "Bram's burned hands were bound."), (35, "The sexton said it was set.")):
        _mint(mind, t, text)
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "after", "kind": "act"},
                                                   yes={"mill burned": 0.92, "talking of the mill fire": 0.93}))
    rows = _ponder(mind, "What happened right after the mill fire?")
    assert _turns(_found(rows)) == [30] and {33, 34} <= set(_turns(rows))


def test_a_near_tie_is_one_moment_told_twice_never_a_moment_long_before(mind, monkeypatch):
    """"Right after you and Bram carried Ilse's chest up to the chapel house"
    read the carrying 0.97 and the mill-fire night, 128 turns earlier, 0.94
    (2026-10-06, every run): within `NEAR_TIE`, and nothing like one moment.
    A tie reaches `SPAN_TURNS` turns, so the surest stands."""
    _mint(mind, 5, "In the night the old mill burned and we carried Ilse across to the chapel.")
    _mint(mind, 40, "Bram and I carried Ilse's chest up the hill to the chapel house.")
    for t, text in ((41, "Ilse unpacked her mother's quilt."), (42, "The sexton brought soup.")):
        _mint(mind, t, text)
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "after", "kind": "act"},
                                                   yes={"old mill burned": 0.94, "carried Ilse's chest": 0.97}))
    rows = _ponder(mind, "What happened right after you carried Ilse's chest up to the chapel house?")
    assert _turns(_found(rows)) == [40] and {41, 42} <= set(_turns(rows))


def test_the_moment_before_or_after_is_the_surest_not_the_first_likely(mind, monkeypatch):
    """Measured on the Saltmere bank (2026-10-06): Tobin breaking off at the
    granary read 0.92 and his confession 0.97 for "right after Tobin told you
    about the grain" -- the first row the model was sure of would have been
    the wrong one."""
    _mint(mind, 25, "Smoke over the mill all evening, from the stubble fires.")
    _mint(mind, 30, "In the night the old mill burned and I dragged sacks out of the smoke.")
    for t, text in ((31, "I poled Ilse across to the chapel."), (32, "Bram burned his hands.")):
        _mint(mind, t, text)
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "after", "kind": "act"},
                                                   yes={"Smoke over the mill": 0.8, "mill burned": 0.97}))
    assert _turns(_found(_ponder(mind, "What happened right after the mill fire?"))) == [30]


def test_a_first_act_is_the_earliest_row_that_shows_it_walked_in_time_order(mind, monkeypatch):
    _mint(mind, 1, "Bram lied to the dockmaster about the rope.")
    _mint(mind, 3, "Ilse Harrow came to the boathouse with bread.", about=[ILSE])
    _mint(mind, 11, "I told Ilse Harrow I had seen no one near the boathouse. My stomach turned.", about=[ILSE])
    _mint(mind, 20, "I lied to Ilse Harrow again, a lie about a cousin, and lying came easier.", about=[ILSE])
    _mint(mind, 25, "I keep thinking about the lies I have told Ilse Harrow.", about=[WREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "act", "who": ILSE},
                                                   yes=("seen no one", "lied to Ilse")))
    found = _found(_ponder(mind, "When was the first time you lied to Ilse?", about=[ILSE], known=[ILSE]))
    assert _turns(found) == [11], "the plainer first lie, not the later row that says the word"
    assert found[0]["in_time"] == "the earliest I remember it"


def test_just_after_finds_the_moment_and_reads_the_turns_after_it(mind, monkeypatch):
    _mint(mind, 29, "I mended a net on the slip.")
    _mint(mind, 30, "In the night the old mill burned and I dragged sacks out of the smoke.")
    for t, text in ((31, "I poled Ilse across to the chapel, coughing."), (32, "Bram burned his hands."),
                    (33, "At dawn the sexton said the fire was set."), (34, "Rain, all day.")):
        _mint(mind, t, text)
    _mint(mind, 40, "Wren and I thought about the night the old mill burned.", about=[WREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "after", "kind": "act", "who": WREN},
                                                   yes=("mill burned",)))
    rows = _ponder(mind, "What happened right after the mill fire?", about=[], known=[WREN],
                   asked_by=WREN)
    assert _turns(_found(rows)) == [30], "who the router took it for never hides the moment"
    assert {31, 32, 33} <= set(_turns(rows)) and 29 not in _turns(rows) and 34 not in _turns(rows)


def test_just_before_reads_the_turns_before_it(mind, monkeypatch):
    for t, text in ((26, "I planed a new blade for the rudder oar."), (27, "Tobin fitted the blade."),
                    (28, "We lashed the rudder oar."), (29, "I mended a net on the slip.")):
        _mint(mind, t, text)
    _mint(mind, 30, "In the night the old mill burned and I dragged sacks out of the smoke.")
    _mint(mind, 31, "I poled Ilse across to the chapel.")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "before", "kind": "act"}, yes=("mill burned",)))
    rows = _ponder(mind, "What were you doing just before the mill fire?")
    assert _turns(_found(rows)) == [30]
    assert {27, 28, 29} <= set(_turns(rows)) and 31 not in _turns(rows)


# ---- routing adds, and never removes --------------------------------------------------------

def test_the_graded_picks_still_come_back_beside_what_the_search_found(mind, monkeypatch):
    _mint(mind, 5, "Oren Dask handed me the green lantern at the East Landing.", about=[OREN])
    _mint(mind, 6, "Rain on the slip all morning.")
    _mint(mind, 7, "Goats and a cart across before noon.")
    _mint(mind, 20, "Oren Dask told me the green lantern means the river is watched.", about=[OREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": OREN},
                                                   graded="means the river", yes=("handed me the green lantern",)))
    rows = _ponder(mind, "When did you first meet Oren?", about=[OREN], known=[OREN])
    assert _turns(_found(rows)) == [5] and {6, 7} <= set(_turns(rows)), "the moment and its turns"
    assert next(r for r in rows if r["turn_idx"] == 20).get("picked_by") == "decision model", \
        "the grade's own pick, outside the span, still comes back"


def test_the_found_moment_is_projected_with_its_mark():
    """The projection itself carries the mark: every lane a found row lands in
    (`asked_recall`, `deliberate_recall`, a lookup) reads it through here."""
    from mind.memory import _with_reading

    class _Clock:
        def of_memory(self, _mem):
            return "about 3 days ago"
    out = _with_reading({"event_key": "event:1", "content": "x", "provenance": "witnessed",
                         "in_time": "the earliest moment I remember with Wren"}, _Clock())
    assert out["in_time"] == "the earliest moment I remember with Wren"
    assert "in_time" not in _with_reading({"event_key": "event:2", "content": "y"}, _Clock())


@pytest.mark.parametrize("how", ["off", "unasked", "not_past", "content"])
def test_without_a_route_the_ponder_is_the_graded_ponder_alone(mind, monkeypatch, temp_db, how):
    _mint(mind, 5, "Oren Dask handed me the green lantern at the East Landing.", about=[OREN])
    _mint(mind, 9, "Oren Dask told me the green lantern means the river is watched.", about=[OREN])
    if how == "off":
        temp_db.set_setting("ponder_routes", "off")
    jev = Jev({"order": "content" if how == "content" else "earliest", "kind": "met", "who": OREN},
              graded="means the river", past=0.2 if how == "not_past" else 0.9,
              fail_route=how == "unasked")
    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    record = {}
    rows = _ponder(mind, "When did you first meet Oren?", about=[OREN], known=[OREN], record=record)
    assert _turns(rows) == [9] and not _found(rows)
    assert bool(jev.asked("route:")) is (how != "off")
    if how == "unasked":
        assert "DecisionError" in record["route"]["unasked"]


def test_a_search_reads_only_this_minds_rows_from_before_now(mind, monkeypatch, temp_db):
    other = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                       ("Ilse", "{}", "{}", time.time()))
    _mint(mind, 1, "Oren Dask sold me a lantern.", about=[OREN], char_id=other)
    _mint(mind, 5, "Oren Dask handed me the green lantern.", about=[OREN])
    _mint(mind, 70, "Oren Dask, a turn not yet lived.", about=[OREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": OREN}, yes=("handed me",)))
    rows = _ponder(mind, "When did you first meet Oren?", about=[OREN], known=[OREN], turn=60)
    assert _turns(_found(rows)) == [5] and 1 not in _turns(rows) and 70 not in _turns(rows)
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "latest", "kind": "met", "who": OREN}, yes=("handed me",)))
    assert _turns(_found(_ponder(mind, "When did you last see Oren?", about=[OREN], known=[OREN], turn=60))) == [5]


# ---- where the mark reaches the mind ---------------------------------------------------------

def test_the_found_moment_is_marked_in_the_asked_lane_and_where_recall_already_holds_it(
        mind, monkeypatch, temp_db):
    from mind import memory
    chat_id, char_id = mind
    temp_db.wset(chat_id, "known", {"Mara": [WREN, OREN]})
    _mint(mind, 2, "Wren came aboard the last evening ferry, soaked, with a surveyor's chain.", about=[WREN])
    for t in range(3, 20):
        _mint(mind, t, f"An ordinary crossing with goats, the {t}th of the month.", about=[WREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": WREN}, yes=("came aboard",)))
    ctx = memory.build_character_memory_context(
        chat_id, char_id, 20, "Wren sits by the stove.", {"goal": "", "mood": "easy"},
        asked_query="Mara, do you remember when we first met?", asked_why="Wren asked",
        asked_by=WREN, person=PERSON)
    marked = [r for lane in (ctx.get("asked_recall", {}).get("additional_episodes") or [],
                             ctx.get("recalled_old_memories") or [], ctx.get("recent_memories") or [])
              for r in lane if r.get("in_time")]
    assert marked and marked[0]["in_time"] == "the earliest moment I remember with Wren"
    assert "soaked" in marked[0]["details"]
    assert ctx["_internal"]["asked_ponder"]["route"]["who"] == WREN


def test_a_found_moment_among_the_recent_turns_is_marked_where_it_already_stands(
        mind, monkeypatch, temp_db):
    """The asked lane skips a row the recent buffer already delivered; the
    mark goes on the copy the mind reads instead of being dropped with it."""
    from mind import memory
    chat_id, char_id = mind
    temp_db.wset(chat_id, "known", {"Mara": [WREN]})
    _mint(mind, 5, "Wren came aboard the last evening ferry, soaked, with a surveyor's chain.", about=[WREN])
    _mint(mind, 7, "Wren took the spare room.", about=[WREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": WREN}, yes=("came aboard",)))
    ctx = memory.build_character_memory_context(
        chat_id, char_id, 9, "Wren sits by the stove.", {"goal": "", "mood": "easy"},
        asked_query="Mara, do you remember when we first met?", asked_why="Wren asked",
        asked_by=WREN, person=PERSON)
    recent = {r["details"][:12]: r for r in ctx["recent_memories"]}
    assert recent["Wren came ab"].get("in_time") == "the earliest moment I remember with Wren"
    assert not recent["Wren took th"].get("in_time")


def test_a_lookups_mark_is_its_own_and_reaches_what_was_delivered(mind, monkeypatch):
    """A mark belongs to the lookup that found it -- a later lookup bringing
    the same row back unmarked shows none -- and a mark found for a row the
    call already delivered joins that delivery (read back, folded into every
    later rung)."""
    from agents.character_tools import Lookups
    chat_id, char_id = mind
    _mint(mind, 5, "Oren Dask handed me the green lantern at the East Landing.", about=[OREN])
    _mint(mind, 9, "Oren Dask at the inn, talking about lantern glass.", about=[OREN])
    look = Lookups(chat_id=chat_id, char_id=char_id, turn_idx=60, bank=None, handles={},
                   memory_context={}, memory_internal={}, holding=None, notebook_inputs={},
                   ponder_inputs={"known": [OREN.casefold()], "known_names": [OREN], "limit": 5,
                                  "person": PERSON})
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "content"}, graded="green lantern"))
    first = look.run("ponder", {"query": "What did Oren give me?"})
    assert not any(m.get("in_time") for m in first["memories"])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": OREN},
                                                   yes=("handed me",)))
    second = look.run("ponder", {"query": "When did I first meet Oren?"})
    assert next(m for m in second["memories"] if m.get("in_time"))["already_in_front_of_you"]
    assert next(d for d in look.delivered if "handed me" in d.get("details", "")).get("in_time")
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "content"}, graded="green lantern"))
    third = look.run("ponder", {"query": "What did Oren give me?"})
    assert not any(m.get("in_time") for m in third["memories"]), "the second question's mark stays its own"


def test_a_row_first_seen_marked_comes_back_unmarked_to_another_question(mind, monkeypatch):
    """The mark found on a row's first reading in a call is not the cache's:
    "the earliest I remember it" meant that question's "it"."""
    from agents.character_tools import Lookups
    chat_id, char_id = mind
    _mint(mind, 5, "Oren Dask handed me the green lantern at the East Landing.", about=[OREN])
    _mint(mind, 9, "Oren Dask at the inn, talking about lantern glass.", about=[OREN])
    look = Lookups(chat_id=chat_id, char_id=char_id, turn_idx=60, bank=None, handles={},
                   memory_context={}, memory_internal={}, holding=None, notebook_inputs={},
                   ponder_inputs={"known": [OREN.casefold()], "known_names": [OREN], "limit": 5,
                                  "person": PERSON})
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": OREN},
                                                   yes=("handed me",)))
    first = look.run("ponder", {"query": "When did I first meet Oren?"})
    assert any(m.get("in_time") for m in first["memories"])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "content"}, graded="green lantern"))
    later = look.run("ponder", {"query": "What did Oren give me?"})
    assert not any(m.get("in_time") for m in later["memories"])


def test_a_last_moment_survives_a_cut_lookup(mind, monkeypatch):
    """Chosen best first, handed back in time order: a last time is the
    latest row of its span, and a cut by time dropped it first."""
    from agents import character_tools
    from agents.character_tools import Lookups
    chat_id, char_id = mind
    for t in range(1, 8):
        _mint(mind, t, f"Oren Dask at the inn, an ordinary evening, number {t}. " + "Lamps and talk. " * 30,
              about=[OREN])
    monkeypatch.setattr(character_tools, "RESULT_CHARS", 1600)
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "latest", "kind": "met", "who": OREN},
                                                   yes=("number 7",)))
    look = Lookups(chat_id=chat_id, char_id=char_id, turn_idx=60, bank=None, handles={},
                   memory_context={}, memory_internal={}, holding=None, notebook_inputs={},
                   ponder_inputs={"known": [OREN.casefold()], "known_names": [OREN], "limit": 5,
                                  "person": PERSON})
    got = look.run("ponder", {"query": "When did I last see Oren?"})
    assert got.get("more_than_fits") and any(m.get("in_time") for m in got["memories"])


def test_a_lookup_points_at_a_found_moment_already_in_front_of_the_mind_and_keeps_its_mark(
        mind, monkeypatch):
    from agents.character_tools import Lookups
    chat_id, char_id = mind
    _mint(mind, 5, "Oren Dask handed me the green lantern at the East Landing.", about=[OREN])
    _mint(mind, 9, "Oren Dask at the inn.", about=[OREN])
    monkeypatch.setattr(decisions, "OVERRIDE", Jev({"order": "earliest", "kind": "met", "who": OREN}, yes=("handed me",)))
    look = Lookups(chat_id=chat_id, char_id=char_id, turn_idx=60, bank=None, handles={},
                   memory_context={"recalled_old_memories": [{"memory_ref": f"event:{char_id}:5:episodic"}]},
                   memory_internal={}, holding=None, notebook_inputs={},
                   ponder_inputs={"known": [OREN.casefold()], "known_names": [OREN], "limit": 5,
                                  "person": PERSON})
    got = look.run("ponder", {"query": "When did I first meet Oren?"})
    first = next(m for m in got["memories"] if m.get("in_time"))
    assert first.get("already_in_front_of_you") and first["in_time"].endswith("with Oren Dask")
