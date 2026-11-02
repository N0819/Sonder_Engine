"""A Japanese authored event can be told and written down, and so fired.

Coverage is token overlap between the assertion and what the beat narrated
and committed, and the tokens came from `_content_tokens`, which splits on
`[^\\w]+`. An unspaced sentence is ONE token, so a Japanese assertion matched
only a prose that repeated the identical clause between punctuation: it was
never `narrated`, never `covered`, never `stale` by retirement. It was
re-queued and handed back to the Director as due, resolve-now, on the next
two beats -- inviting a second and third enactment of a thing that already
happened -- and the "narrated and encoded in no channel" warning could never
fire (story_scene_schema audit F6).

The comparator now reads an unspaced run as the words it is written in: a
katakana run is a loanword, kept whole; a kanji run is read by its character
pairs, so a compound and its parts meet; hiragana -- particles, okurigana --
carries no content and is dropped. Latin text keeps the reading it had.
"""

from __future__ import annotations

import time

from core.db import q
from story.authored_events import mint_authored_events, resolve_authored_events


SUMMARY = "エレベーターが地下に墜落する"


def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("t", "", time.time()))


def _status(cid):
    return [r["status"] for r in q(
        "SELECT status FROM scheduled_events WHERE chat_id=? "
        "AND kind='authored_event'", (cid,))]


def test_a_japanese_event_told_and_written_down_fires(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 1, [{"summary": SUMMARY, "due_in_turns": 1}])
    fired, requeued, dropped = resolve_authored_events(
        cid, 2, "轟音とともにエレベーターは地下へ墜落した。",
        {"rooms": {"エレベーター": {"state": "地下に墜落した"}}})
    assert (fired, requeued, dropped) == (1, 0, 0)
    assert _status(cid) == ["fired"]


def test_a_beat_that_only_mentions_the_subject_does_not_fire_it(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 1, [{"summary": SUMMARY, "due_in_turns": 1}])
    fired, requeued, _dropped = resolve_authored_events(
        cid, 2, "二人はエレベーターの話をしていた。",
        {"rooms": {"エレベーター": {"note": "静か"}}})
    assert (fired, requeued) == (0, 1)


def test_a_japanese_event_whose_referent_the_beat_retired_goes_stale(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 1, [{"summary": SUMMARY, "due_in_turns": 1}])
    fired, requeued, dropped = resolve_authored_events(
        cid, 2, "天井が崩れ、通路は塞がった。",
        {"remove_entities": ["地下のエレベーター墜落"]})
    assert (fired, requeued, dropped) == (0, 0, 1)


def test_the_english_reading_is_what_it_was(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 1, [{"summary": "The elevator crashes into "
                                   "the basement", "due_in_turns": 1}])
    fired, _r, _d = resolve_authored_events(
        cid, 2, "With a roar the elevator crashed into the basement.",
        {"rooms": {"basement": {"note": "the elevator crashed here"}}})
    assert fired == 1
