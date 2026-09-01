"""A memory is stamped in TIME, and the stamp is stored on its own row.

Minds were measuring their own past in BEATS -- turn indices, engine
vocabulary, frames of the story's construction. One instrumented run put 94
"about N beats ago" stamps in front of 54 character calls and the characters
reasoned in the unit they were handed ("the same declaration about the door
lock ten beats ago"). These hold the replacement:

  * the reading lands on the row at commit, from the clock the commit already
    holds;
  * ONE ladder names every interval, seconds through years, largest unit only;
  * both delivered lanes -- a single memory and a summarised window -- read it,
    so neither can drift into its own vocabulary;
  * the two questions that come BEFORE the arithmetic can refuse it (a row
    from the deciding turn, a row from another frame), and a refusal is a
    qualitative phrase rather than a confident wrong number;
  * the reading survives a reroll, an archive round trip, and the migration.

Class-level throughout: no story noun appears in an identifier or an
assertion, and every fixture below is a bare chat, a bare character and a
number on a clock.
"""

import json
import time

import pytest

from core import db
from core.pipeline_context import ChatData, PipelineContext, TurnData
from mind.memory import (
    JUST_NOW,
    MemoryClock,
    UNIT_LADDER,
    WHEN_BEFORE_RECORD,
    WHEN_UNPLACEABLE,
    _with_reading,
    dump_chat_memories,
    restore_chat_memories,
    time_ago_phrase,
    time_ago_span,
)
from story.character_schema import default_character_data


# ---- the ladder -------------------------------------------------------------

@pytest.mark.parametrize("seconds,phrase", [
    (0.0, JUST_NOW),
    (0.4, JUST_NOW),
    (1.0, "about 1 second ago"),
    (45.0, "about 45 seconds ago"),
    (170.0, "about 3 minutes ago"),
    (3 * 3600 + 90, "about 3 hours ago"),
    (2 * 86400, "about 2 days ago"),
    (3 * 604800, "about 3 weeks ago"),
    (5 * 2629800, "about 5 months ago"),
    (7 * 31557600, "about 7 years ago"),
])
def test_the_ladder_names_only_the_largest_unit_that_fits(seconds, phrase):
    assert time_ago_phrase(seconds) == phrase


def test_every_rung_is_reachable_including_the_top_one():
    """The whole range is built now, years included.

    A ladder that stops at the unit today's clock happens to reach is found the
    hard way -- by a mind told it slept 10080 minutes the first time a time
    skip lands. Three of each unit, so nothing rounds up onto its neighbour.
    """
    for name, size in UNIT_LADDER:
        assert time_ago_phrase(size * 3) == f"about 3 {name}s ago"


def test_a_phrase_never_compounds_two_units():
    """Presentation is coarse ON PURPOSE -- that is what makes the arithmetic
    sufficient rather than sloppy. Human memory holds "a few minutes", not two
    hours and thirteen minutes."""
    for name, size in UNIT_LADDER:
        phrase = time_ago_phrase(size * 2 + size / 3.0)
        assert sum(unit in phrase for unit, _ in UNIT_LADDER) == 1


def test_the_future_gets_no_phrase_at_all():
    """Never relabel something that has not happened. Empty is the refusal
    every caller already reads as "say nothing"."""
    assert time_ago_phrase(-1.0) == ""
    assert time_ago_span(-5.0, -10.0) == ""


def test_a_window_takes_its_own_rung_at_each_end():
    """Flattening a window onto one unit rounds its near end to nothing."""
    assert time_ago_span(3700.0, 60.0) == "between about 1 minute and 1 hour ago"
    assert time_ago_span(540.0, 240.0) == "between about 4 and 9 minutes ago"
    # Closed to a point: one phrase, not a range of one.
    assert time_ago_span(170.0, 170.0) == "about 3 minutes ago"


# ---- a bare story -----------------------------------------------------------

def _story(temp_db, *, name="T"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (name, "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("A", json.dumps(default_character_data("A")), "{}", time.time()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    return chat_id, char_id


def _frame(temp_db, chat_id, *, ordinal=1):
    return temp_db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
        "VALUES(?,?,?,?,?)", (chat_id, "F", ordinal, "other", time.time()))


def _row(temp_db, chat_id, char_id, *, turn_idx, seconds, frame_id=None,
         content="a thing happened", event_key=""):
    """One stored memory, written as SQL so the test states the row it means."""
    return temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,frame_id,kind,category,"
        "provenance,salience,content,gist,key_phrases,entities,location,"
        "emotional_context,valence,arousal,confidence,archived,event_key,"
        "embedding_model,encoded_at_seconds) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, char_id, turn_idx, frame_id, "episodic", "episode",
         "witnessed", 0.6, content, content, "[]", "[]", "", "", 0.0, 0.0,
         1.0, 0, event_key or f"k:{turn_idx}:{seconds}", "", seconds))


def _read(temp_db, mid):
    from mind.memory import _row_memory
    return _row_memory(temp_db.q("SELECT * FROM memories WHERE id=?",
                                 (mid,), one=True))


# ---- both readers, one ladder ----------------------------------------------

def test_both_delivered_lanes_read_the_same_ladder(temp_db):
    """A single memory and a summarised window are two lanes of one past.

    They had two naming rules and two arithmetics; a mind reading both found
    its own history measured two ways. Here the window has closed to a point,
    so the two lanes must produce the BYTE-IDENTICAL phrase.
    """
    chat_id, char_id = _story(temp_db)
    _row(temp_db, chat_id, char_id, turn_idx=3, seconds=120.0)
    _row(temp_db, chat_id, char_id, turn_idx=5, seconds=120.0)
    clock = MemoryClock(chat_id, char_id, 9, now_seconds=300.0,
                        viewer_frame_id=None)

    single = _with_reading(_read(temp_db, 1), clock)["when"]
    window = clock.of_window(3, 5)
    assert single == window == "about 3 minutes ago"


def test_a_window_that_spans_reads_both_of_its_own_ends(temp_db):
    chat_id, char_id = _story(temp_db)
    _row(temp_db, chat_id, char_id, turn_idx=2, seconds=60.0)
    _row(temp_db, chat_id, char_id, turn_idx=6, seconds=240.0)
    clock = MemoryClock(chat_id, char_id, 9, now_seconds=300.0,
                        viewer_frame_id=None)
    assert clock.of_window(2, 6) == "between about 1 and 4 minutes ago"


def test_no_delivered_stamp_speaks_in_beats(temp_db):
    """The vocabulary itself, checked at the payload boundary.

    A turn index is the engine's own unit; a mind reasoning in it is reasoning
    in frames of the story's construction. Nothing this hands a mind may name
    one, whether the row carries a reading, carries none, or belongs to no beat
    at all.
    """
    chat_id, char_id = _story(temp_db)
    stamped = _row(temp_db, chat_id, char_id, turn_idx=1, seconds=30.0)
    unstamped = temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist,key_phrases,entities,location,"
        "emotional_context,valence,arousal,confidence,archived,event_key,"
        "embedding_model) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, char_id, 2, "episodic", "episode", "witnessed", 0.6,
         "x", "x", "[]", "[]", "", "", 0.0, 0.0, 1.0, 0, "k:u", ""))
    prestory = temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,kind,category,"
        "provenance,salience,content,gist,key_phrases,entities,location,"
        "emotional_context,valence,arousal,confidence,archived,event_key,"
        "embedding_model) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, char_id, "episodic", "episode", "remembered", 0.6,
         "y", "y", "[]", "[]", "", "", 0.0, 0.0, 1.0, 0, "k:p", ""))
    clock = MemoryClock(chat_id, char_id, 9, now_seconds=300.0,
                        viewer_frame_id=None)
    whens = [_with_reading(_read(temp_db, mid), clock)["when"]
             for mid in (stamped, unstamped, prestory)]
    assert whens == ["about 4 minutes ago", WHEN_UNPLACEABLE,
                     WHEN_BEFORE_RECORD]
    for when in whens:
        assert "beat" not in when


# ---- the two questions that come before the arithmetic ----------------------

def test_a_row_from_another_frame_is_never_given_a_number(temp_db):
    """A stored reading is a PER-FRAME fiction time.

    `turn_idx` is global play order shared by every frame, so a window or a row
    can legitimately reach a mind standing in a different frame -- a traveler
    keeps its own ledger. Subtracting one frame's clock from another's is
    arithmetic across two unrelated clocks, and the answer would be confident
    and meaningless.
    """
    chat_id, char_id = _story(temp_db)
    elsewhere = _frame(temp_db, chat_id)
    other = _row(temp_db, chat_id, char_id, turn_idx=3, seconds=120.0,
                 frame_id=elsewhere)
    here = _row(temp_db, chat_id, char_id, turn_idx=4, seconds=180.0)
    clock = MemoryClock(chat_id, char_id, 9, now_seconds=300.0,
                        viewer_frame_id=None)

    assert _with_reading(_read(temp_db, other), clock)["when"] == WHEN_UNPLACEABLE
    assert _with_reading(_read(temp_db, here), clock)["when"] == "about 2 minutes ago"
    # And no digit anywhere in the refusal: a number is exactly what it may not
    # produce here.
    assert not any(c.isdigit() for c in WHEN_UNPLACEABLE)


def test_a_window_whose_rows_are_all_another_frames_refuses_too(temp_db):
    chat_id, char_id = _story(temp_db)
    _row(temp_db, chat_id, char_id, turn_idx=3, seconds=120.0,
         frame_id=_frame(temp_db, chat_id))
    clock = MemoryClock(chat_id, char_id, 9, now_seconds=300.0,
                        viewer_frame_id=None)
    assert clock.of_window(2, 5) == WHEN_UNPLACEABLE


def test_the_deciding_turns_own_rows_are_never_stamped(temp_db):
    """The turn cutoff stays in TURN INDICES, and it has to.

    The clock does not advance inside a beat, so a reading cannot tell turn N's
    own committed outcome from the beat before it. Play order can, and that is
    the unit the firewall's cutoff is kept in.
    """
    chat_id, char_id = _story(temp_db)
    own = _row(temp_db, chat_id, char_id, turn_idx=9, seconds=300.0)
    clock = MemoryClock(chat_id, char_id, 9, now_seconds=300.0,
                        viewer_frame_id=None)
    assert _with_reading(_read(temp_db, own), clock)["when"] == WHEN_UNPLACEABLE
    assert clock.of_window(8, 9) == ""


def test_a_reader_standing_after_the_turn_may_read_it(temp_db):
    """The out-of-band passes are not deciding anything.

    They run after commit, and that turn's rows are their whole subject; the
    cutoff that protects a deciding mind would blind them to it.
    """
    chat_id, char_id = _story(temp_db)
    own = _row(temp_db, chat_id, char_id, turn_idx=9, seconds=300.0)
    after = MemoryClock(chat_id, char_id, 9, now_seconds=300.0,
                        viewer_frame_id=None, deciding_turn=False)
    assert _with_reading(_read(temp_db, own), after)["when"] == JUST_NOW


# ---- the write path ---------------------------------------------------------

def _commit_context(temp_db, chat_id, char_id, *, turn_idx, duration):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "x", time.time()))
    temp_db.wset(chat_id, "scene", {
        "rooms": {"r": {"name": "R"}}, "positions": {"A": "r"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="x", created=time.time()),
        cast=cast, input="x")
    ctx.director_resolve = {
        "summary": "s",
        "resolved_event": "Something happened in the room.",
        "state_diff": {"time": {"duration_seconds": duration}},
        "dialogue_log": [],
    }
    ctx.perception_outcome = {"views": {str(char_id): "Something happened."}}
    return ctx


def test_the_commit_stamps_the_clock_it_already_held(temp_db, monkeypatch):
    """The reading was in the commit's hand and never landed on the row.

    `prepare_memory_commit` already computes the beat's end clock -- affect
    decay, strain windows and belief provenance are all dated by it. Every row
    the beat mints is formed at that same moment by definition, so the stamp is
    applied once, after every append, rather than at each mint site.
    """
    from persist import commit_memory_write
    from persist.commit import commit_memories

    chat_id, char_id = _story(temp_db)
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": 180.0, "display": "now"})
    ctx = _commit_context(temp_db, chat_id, char_id, turn_idx=1, duration=45)

    captured = []

    def _capture(memories=None, *, prepared_batch=None):
        batch = memories if memories is not None else prepared_batch["prepared"]
        captured.extend(batch)
        return list(range(1, len(batch) + 1))

    monkeypatch.setattr(commit_memory_write, "add_memories_batch", _capture)
    monkeypatch.setattr(commit_memory_write,
                        "maybe_consolidate_character_memory",
                        lambda *a, **k: None)
    commit_memories(ctx, nonce=0)

    assert captured, "the beat minted no memory to stamp"
    assert {m["encoded_at_seconds"] for m in captured} == {225.0}


def test_a_reroll_rewrites_the_stamp_with_the_new_reading(temp_db, monkeypatch):
    """THE REASON THE READING IS STORED AND NOT DERIVED.

    A derived age -- `(now_turn - turn_idx) * (now_elapsed / now_turn)` -- reads
    off a MOVING denominator: re-run one turn with a different declared
    duration and every memory in the bank silently changes age, including rows
    from beats that never changed. A stored reading is LOCAL. The write path
    deletes the turn's rows and re-mints them, so the re-run turn's stamp moves
    and nothing else does.
    """
    from persist import commit_memory_write
    from persist.commit import commit_memories

    chat_id, char_id = _story(temp_db)
    monkeypatch.setattr(commit_memory_write,
                        "maybe_consolidate_character_memory",
                        lambda *a, **k: None)
    untouched = _row(temp_db, chat_id, char_id, turn_idx=0, seconds=5.0)

    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": 100.0, "display": "now"})
    ctx = _commit_context(temp_db, chat_id, char_id, turn_idx=1, duration=20)
    commit_memories(ctx, nonce=0)
    turn_id = ctx.turn.id
    first = {r["encoded_at_seconds"] for r in temp_db.q(
        "SELECT encoded_at_seconds FROM memories WHERE turn_id=?", (turn_id,))}
    assert first == {120.0}

    # The same turn, re-run against a clock that has been rolled back with it
    # and a beat that now declares a different duration.
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": 100.0, "display": "now"})
    ctx.director_resolve["state_diff"]["time"] = {"duration_seconds": 300}
    commit_memories(ctx, nonce=1)
    second = {r["encoded_at_seconds"] for r in temp_db.q(
        "SELECT encoded_at_seconds FROM memories WHERE turn_id=?", (turn_id,))}
    assert second == {400.0}

    # And the beat that never changed did not move.
    assert temp_db.q("SELECT encoded_at_seconds AS s FROM memories WHERE id=?",
                     (untouched,), one=True)["s"] == 5.0


# ---- it survives being carried ---------------------------------------------

def test_the_reading_survives_an_archive_round_trip(temp_db):
    """Not re-derivable from anything else on the row, so it must be carried.

    Drop it on an export and the bank falls back to whatever the importing
    story's clock divided by its turn count happens to say -- the moving
    denominator this column exists to escape.
    """
    chat_id, char_id = _story(temp_db)
    _row(temp_db, chat_id, char_id, turn_idx=2, seconds=61.5)
    _row(temp_db, chat_id, char_id, turn_idx=4, seconds=None)

    dumped = dump_chat_memories(chat_id)
    assert sorted(m["encoded_at_seconds"] for m in dumped
                  if m["encoded_at_seconds"] is not None) == [61.5]

    other_chat, _ = _story(temp_db, name="U")
    restore_chat_memories(
        other_chat, [{**m, "char_id": char_id} for m in dumped])
    restored = sorted(
        (r["turn_idx"], r["encoded_at_seconds"]) for r in temp_db.q(
            "SELECT turn_idx, encoded_at_seconds FROM memories WHERE chat_id=?",
            (other_chat,)))
    assert restored == [(2, 61.5), (4, None)]


# ---- the migration ----------------------------------------------------------

def test_the_migration_estimates_nothing_and_says_so(temp_db):
    """A row written before the column existed carries NO reading.

    The obvious backfill -- turn_idx * UNCLAIMED_BEAT_SECONDS -- was written
    first and measured second, and it is the same derivation-off-a-fixed-rate
    the stored column exists to replace. Measured against a real clock: a chat
    that ran at ~18s/beat returns "about 9 minutes ago" for a memory 30 seconds
    old, and where the estimate overshoots the live clock the interval goes
    negative and the row reads as unplaceable regardless. A confident wrong age
    is worse than an honest shrug, so the migration adds the column and stops.

    This asserts the ABSENCE of a backfill, which is a thing a test has to say
    out loud: nothing else fails if one is quietly reintroduced.
    """
    chat_id, char_id = _story(temp_db)
    before_column = _row(temp_db, chat_id, char_id, turn_idx=7, seconds=None)
    already = _row(temp_db, chat_id, char_id, turn_idx=8, seconds=3.0)

    for statement in db.MIGRATIONS[-1]:
        if statement.strip().upper().startswith("UPDATE"):
            temp_db.qi(statement)

    assert temp_db.q("SELECT encoded_at_seconds AS s FROM memories WHERE id=?",
                     (before_column,), one=True)["s"] is None, (
        "a legacy row was given an estimated reading; the migration must "
        "leave it NULL so its readers keep the qualitative phrasing")
    assert temp_db.q("SELECT encoded_at_seconds AS s FROM memories WHERE id=?",
                     (already,), one=True)["s"] == 3.0


def test_no_migration_statement_derives_a_reading_from_a_turn_index(temp_db):
    """The class, not the instance: no migration may compute a clock reading
    from `turn_idx` at any rate, however the arithmetic is spelled."""
    for version, statements in enumerate(db.MIGRATIONS):
        for statement in statements:
            flat = " ".join(str(statement).split()).upper()
            if "ENCODED_AT_SECONDS" not in flat:
                continue
            assert "TURN_IDX" not in flat, (
                f"migration {version} derives encoded_at_seconds from "
                f"turn_idx: {statement}")


#: The schema version whose migration adds `memories.encoded_at_seconds`.
#: The migration that takes a database TO version N lives at MIGRATIONS[N-2].
ENCODED_AT_SECONDS_VERSION = 34


def test_the_migration_belongs_to_the_version_that_adds_the_column(temp_db):
    """The backfill has to belong to the version that adds the column.

    This asserted `MIGRATIONS[-1]` until 2026-09-01, which was the same thing
    only while v34 happened to be newest: the next migration to land (v35, the
    debug-capture tables) moved the column's own migration off the end and the
    test failed for a reason that had nothing to do with the property it
    names. Pinned to the version instead, so it keeps testing the claim in its
    docstring rather than the shape of the list.
    """
    index = ENCODED_AT_SECONDS_VERSION - 2
    assert any("encoded_at_seconds" in s for s in db.MIGRATIONS[index])
    assert len(db.MIGRATIONS) + 1 == db.SCHEMA_VERSION
    cols = {r["name"] for r in temp_db.q("PRAGMA table_info(memories)")}
    assert "encoded_at_seconds" in cols


# ---- the payload boundary, walked whole -------------------------------------

def _every_string(value, path="payload"):
    """Every string in a nested payload, with the path that reached it."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _every_string(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _every_string(item, f"{path}[{index}]")


def test_nothing_anywhere_in_a_delivered_payload_names_a_beat(temp_db):
    """The class, at the only boundary that matters: what a mind is handed.

    Five stamping sites read the clock correctly and NOTHING ASSERTED WHAT THEY
    PRODUCED, so each could be reverted to a hardcoded "about N beats ago" with
    a fully green suite -- and one of them was, verbatim, during the adversarial
    pass: `mind/memory_judge.py`'s recall-review row, put back into beats,
    9820 passed 0 failed. A per-site test would have to be written again for
    every site added later. This walks the whole payload instead, so a lane
    that starts speaking in beats fails here whether or not anyone remembered
    to cover it.

    The lanes populated below are the five: a single memory, a scoped
    provenance summary, the autobiographical summary, a row belonging to no
    beat, and a row carrying no reading at all.
    """
    from mind.memory import build_character_memory_context
    from mind.memory import save_memory_summary

    chat_id, char_id = _story(temp_db)
    _row(temp_db, chat_id, char_id, turn_idx=1, seconds=30.0,
         content="a door closed")
    _row(temp_db, chat_id, char_id, turn_idx=2, seconds=90.0,
         content="someone spoke")
    # No reading, and no beat at all -- the two refusal paths.
    temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist,key_phrases,entities,location,"
        "emotional_context,valence,arousal,confidence,archived,event_key,"
        "embedding_model) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, char_id, 3, "episodic", "episode", "witnessed", 0.6,
         "no reading", "no reading", "[]", "[]", "", "", 0.0, 0.0, 1.0, 0,
         "k:nr", ""))
    temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,kind,category,"
        "provenance,salience,content,gist,key_phrases,entities,location,"
        "emotional_context,valence,arousal,confidence,archived,event_key,"
        "embedding_model) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, char_id, "semantic", "episode", "remembered", 0.5,
         "before the record", "before the record", "[]", "[]", "", "", 0.0,
         0.0, 1.0, 0, "k:pre", ""))
    save_memory_summary(chat_id, char_id, "A stretch of days.",
                        start_turn_idx=1, end_turn_idx=2)

    payload = build_character_memory_context(
        chat_id, char_id, 9, "You are in a room.", {})

    offenders = [(path, text) for path, text in _every_string(payload)
                 if "beat" in text.casefold()]
    assert not offenders, (
        "a delivered payload named the engine's own turn unit: "
        + "; ".join(f"{path} = {text!r}" for path, text in offenders[:6]))
