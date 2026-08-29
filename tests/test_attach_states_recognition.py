"""A cast membership created without an answer about recognition says so.

RECOGNITION IS A CHANNEL. `known` is the ledger perception subtracts against,
so a membership row written with no entry in it asserts, silently, that no
channel exists -- and the engine cannot tell that assertion from "the caller
omitted a flag". Strangers meeting is a real and valuable opening, which is
why the answer stays the caller's; what may not happen is the question going
unasked.

MEASURED CASE (chat 95): the cast was created without any recognition answer,
`known` stayed empty for nine turns, and the player's own commanding officer
was composed for the narrator as "a figure, backlit, indistinct, the face
unreadable". Perception was right every one of those turns. The damage
outlives the repair: after an in-story introduction finally filled `known`,
turn 11 still fed the character stage "I saw an indistinct figure return to
the science station console" as remembered_past, because recognition seeded
late does not rewrite the memories written before it.

Three paths create a membership from nothing -- the greeting launch, this
route, and background promotion -- and before this they held three different
recognition semantics with opposite defaults, none of them named anywhere.
"""

from __future__ import annotations

import inspect
import json
import time

from web import app
from story.character_schema import default_character_data, default_persona_data


def _chat_with_persona(db, persona_name):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (persona_name, json.dumps(default_persona_data(persona_name)), "{}"))
    return db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Test", "", time.time(), persona_id))


def _character(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()))


def test_an_attach_that_answers_nothing_is_reported(temp_db):
    """The chat 95 shape. Nothing is seeded -- an omission is not consent to
    widen a channel -- but the membership no longer arrives unremarked."""
    cid = _chat_with_persona(temp_db, "Sarah Chen")
    char_id = _character(temp_db, "Vrenak")

    result = app.chat_add_char(cid, {"char_id": char_id})

    assert temp_db.wget(cid, "known", {}) == {}
    assert any("Vrenak" in notice and "recognition" in notice
               for notice in result.get("warnings") or []), result


def test_an_attach_that_answers_no_is_left_alone(temp_db):
    """A strangers-meeting attach is an authored answer, not an omission, and
    the engine must not nag an author for writing one."""
    cid = _chat_with_persona(temp_db, "Sarah Chen")
    char_id = _character(temp_db, "Vrenak")

    result = app.chat_add_char(
        cid, {"char_id": char_id, "already_known": False})

    assert temp_db.wget(cid, "known", {}) == {}
    assert not (result.get("warnings") or []), result


def test_an_attach_that_answers_yes_is_left_alone_and_seeds_both_ways(temp_db):
    cid = _chat_with_persona(temp_db, "Sarah Chen")
    char_id = _character(temp_db, "Dr. Crusher")

    result = app.chat_add_char(
        cid, {"char_id": char_id, "already_known": True})

    known = temp_db.wget(cid, "known", {})
    assert known["Dr. Crusher"] == ["Sarah Chen"]
    assert known["Sarah Chen"] == ["Dr. Crusher"]
    assert not (result.get("warnings") or []), result


def test_an_attach_can_answer_whether_the_arrivals_know_each_other(temp_db):
    """TWO QUESTIONS, and until now only one of them could be asked.

    `already_known` answers "does this person know the player". Whether two
    arrivals know EACH OTHER is a different question with a different answer,
    and no attach surface could state it -- so a cast who share a workplace,
    a household or a command reached every story as mutual strangers.

    Measured on chat 98: after forty turns `known` held Picard -> [player,
    Data], Data -> [player, Worf], Worf -> [player, Data]. Three senior
    officers who had served together for years, each missing a colleague,
    because the only in-play channel is hearing a name said aloud and the man
    who does most of the naming learns nothing from his own mouth. His own
    composed view called the officer at tactical "the tall heavily built
    klingon male" on all forty turns while his dialogue said "Mr. Worf" five
    times -- a name from outside the ledger, in the objective record, because
    the engine had no way to be told what the story took for granted.
    """
    cid = _chat_with_persona(temp_db, "Sarah Chen")
    first = _character(temp_db, "Vrenak")
    second = _character(temp_db, "Dr. Crusher")

    app.chat_add_char(cid, {"char_id": first, "already_known": True})
    result = app.chat_add_char(
        cid, {"char_id": second, "already_known": True,
              "already_known_cast": True})

    known = temp_db.wget(cid, "known", {})
    assert known["Dr. Crusher"] == ["Sarah Chen", "Vrenak"]
    assert known["Vrenak"] == ["Sarah Chen", "Dr. Crusher"]
    assert not (result.get("warnings") or []), result


def test_the_cast_answer_and_the_player_answer_are_independent(temp_db):
    """A stranger to the player who is not a stranger to the crew she arrives
    with. Neither answer may stand in for the other."""
    cid = _chat_with_persona(temp_db, "Sarah Chen")
    first = _character(temp_db, "Vrenak")
    second = _character(temp_db, "Dr. Crusher")

    app.chat_add_char(cid, {"char_id": first, "already_known": False})
    app.chat_add_char(
        cid, {"char_id": second, "already_known": False,
              "already_known_cast": True})

    known = temp_db.wget(cid, "known", {})
    assert known["Dr. Crusher"] == ["Vrenak"]
    assert known["Vrenak"] == ["Dr. Crusher"]
    assert "Sarah Chen" not in known


def test_the_unasked_cast_question_is_reported_when_there_is_one_to_ask(
        temp_db):
    """Same rule as the player question: an omission is not an authored no,
    so nothing is seeded and the omission is said aloud. It is only a question
    when somebody is already here to be a stranger to -- the first arrival has
    nobody to know, and is not nagged about it."""
    cid = _chat_with_persona(temp_db, "Sarah Chen")
    first = _character(temp_db, "Vrenak")
    second = _character(temp_db, "Dr. Crusher")

    alone = app.chat_add_char(cid, {"char_id": first, "already_known": True})
    assert not (alone.get("warnings") or []), alone

    result = app.chat_add_char(
        cid, {"char_id": second, "already_known": True})

    assert temp_db.wget(cid, "known", {}).get("Dr. Crusher") == ["Sarah Chen"]
    assert any("Vrenak" in notice and "each other" in notice
               for notice in result.get("warnings") or []), result


def test_recognition_is_a_relation_over_a_roster_not_over_the_player(temp_db):
    """The seeder takes the names it is to close over, so a caller with a
    reason to recognise more than the player can say so in one call. Both of
    the seeding sites that existed before this were shaped `{player: [char],
    char: [player]}` and could not express anything else."""
    from persist.commit import seed_mutual_recognition

    cid = _chat_with_persona(temp_db, "Sarah Chen")
    seed_mutual_recognition(cid, "Vrenak", ["Sarah Chen", "Dr. Crusher"])
    seed_mutual_recognition(cid, "Vrenak", ["Sarah Chen"])

    known = temp_db.wget(cid, "known", {})
    assert known["Vrenak"] == ["Sarah Chen", "Dr. Crusher"]
    assert known["Dr. Crusher"] == ["Vrenak"]
    assert known["Sarah Chen"] == ["Vrenak"]


def test_every_path_that_creates_a_membership_seeds_through_one_writer():
    """The ownership itself, which is the defect: an invariant established by
    only some of the paths that create a record is not an invariant, it is a
    coincidence of which door was used. Three creating paths, one writer."""
    from persist import commit_background
    from story import greetings

    # `promote_background_character` is named at the module that DEFINES it
    # rather than through the `persist.commit` facade, because what is read
    # here is that module's source; the facade's re-export is the same object
    # under a name that says nothing about where the writer lives.
    for owner in (app.chat_add_char, greetings.start_story,
                  getattr(commit_background, "promote_background_character")):
        source = inspect.getsource(owner)
        assert "seed_mutual_recognition(" in source, owner.__name__
        assert not [line for line in source.splitlines()
                    if "wset(" in line and "known" in line], (
            f"{owner.__name__} writes the recognition ledger by hand")
