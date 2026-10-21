"""A sentence a draft event quotes whole is that event's sentence, so the
check-and-repair pass does not ask Jev whether it is missing.

Measured on the owner's chats 175-178 (2026-10-20, the battery replayed on
the 67 recorded stages that sent missing-event jobs): Jev answered
"missing" for 58 sentences while shown the event that held each word for
word ("Mellisande crosses to the hearth and lifts the kettle off the iron
grate by its bail." against e4, the same words); the 12 repair jobs built
on them were all declined, and none of the 51 jobs the repair acted on was
such a sentence.
The rule is code's because the fact is code's: `citations` already ties
the event to the sentence, and an event whose text IS the sentence
records whatever the sentence tells.
"""

from agents import director_repair as repair

PROSE = ("Mellisande crosses to the hearth and lifts the kettle off the iron grate by its bail. "
         "\"Mind the step,\" she says, and goes in through the door. "
         "The threshold stone is dished a finger's depth in the middle.")


def _draft():
    return [
        {"source_entity_id": "character:83",
         "event": "Mellisande crosses to the hearth and lifts the kettle off the iron grate by its bail.",
         "speech": False, "item_names": ["Mellisande", "kettle"],
         "transforms": [{"item": "kettle", "patch": {"stations": {"kettle": {"at": "hearth"}}}}]},
        {"source_entity_id": "character:83", "event": "Mind the step,",
         "speech": True, "item_names": ["Mellisande"], "transforms": []},
    ]


def test_a_sentence_an_event_quotes_whole_is_not_asked():
    units = repair.sentences(PROSE)
    assert repair.citations(_draft(), units) == {"s1": [0], "s2": [1], "s3": []}
    questions, about = repair.battery(units, _draft(), ["stations"])
    asked = {a["sentence"] for a in about.values() if a["kind"] == "event"}
    # s1 is e1's own words: not asked. s2 is quoted only in part -- the line is
    # e2's, the walk through the door is nobody's yet -- so it is asked, and
    # s3, which no event comes from, is asked.
    assert asked == {"s2", "s3"}
    # The event that quotes s1 is still judged on what it WRITES.
    assert "bad:e1:0:stations" in about
    # A quoted sentence's event is still shown beside its neighbours' questions.
    assert "lifts the kettle off the iron grate" in questions["ev:s2"]["instructions"]


def test_whole_means_the_words_and_not_the_marks():
    # Case, quotation marks, punctuation and a sentence address are not words.
    assert repair.quotes_whole('"Mind the step," she says.', "[s2] mind the step she SAYS")
    assert repair.quotes_whole("The door swings inward.", "The door swings inward.")
    # A sentence with words outside the event is still asked -- its attribution
    # included, because what follows a quotation may be an act of its own, and
    # telling a frame from an act would take a word list.
    assert not repair.quotes_whole("Mind the step, it's worn hollow by better feet than mine.",
                                   'Mellisande says, "Mind the step, it\'s worn hollow by better feet than mine."')
    assert not repair.quotes_whole("Mind the step,",
                                   '"Mind the step," she says, and goes in through the door.')
    assert not repair.quotes_whole("", "Mind the step.")
    assert not repair.quotes_whole("Mind the step.", "")
