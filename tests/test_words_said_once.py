"""Words said once are said once.

Background and charter voices are asked at once, blind to each other, so two
bystanders nobody addressed can volunteer the SAME sentence. Measured on
scratch story 166, turn 4588: two staithe hands both declared "I'll mind the
stage while you're up.", the narrator rendered a duet ("two voices carried
over the planking ..."), and the log filed both under one of them. Across
every stored beat with two or more figure declarations (42), that identical
line was the only one two figures shared. The later voice keeps its act and
loses its words, exactly as a second answer to one addressed line already
did; a near-copy is left alone.
"""

from agents.background import _first_answer_only


def _voice(name, line, *, answering=None, action="shifts at the post"):
    reaction = {"name": name, "action": action,
                "dialogue_log_entry": {"speaker": name, "exact_quote": line}}
    if answering:
        reaction["heard_address"] = {"exact_quote": answering, "beats_ago": 0}
    return reaction


def test_an_identical_line_from_a_second_voice_is_not_said_twice():
    first = _voice("Dobadum Dykeowley", "I'll mind the stage while you're up.")
    second = _voice("Dunion Dykeowden", "I'll mind the stage while you're up")
    kept, demoted = _first_answer_only([first, second])
    assert kept[0] is first
    assert kept[1]["dialogue_log_entry"] is None
    assert kept[1]["action"] == "shifts at the post", "the act stands"
    assert kept[1]["demoted_line"] == "I'll mind the stage while you're up"
    assert demoted == [("Dunion Dykeowden", "I'll mind the stage while you're up",
                        "Dobadum Dykeowley", "said")]


def test_a_near_copy_is_left_to_the_card():
    first = _voice("Barenock Brackidon", "She's right. You'll see nowt off a hull at night.")
    second = _voice("Garory Haugowlow", "She's right about the dark.")
    kept, demoted = _first_answer_only([first, second])
    assert kept == [first, second] and demoted == []


def test_one_line_still_has_one_answerer():
    asked = "Who keeps the bell?"
    first = _voice("Gatoen Netowick", "The chapel keeps it.", answering=asked)
    second = _voice("Barelum Marleyburn", "Old Petch, most nights.", answering=asked)
    kept, demoted = _first_answer_only([first, second])
    assert kept[1]["dialogue_log_entry"] is None
    assert demoted == [("Barelum Marleyburn", "Old Petch, most nights.",
                        "Gatoen Netowick", "answered")]


def test_silent_entries_pass_through_where_they_stand():
    first = _voice("Dobadum Dykeowley", "Aye.")
    kept, demoted = _first_answer_only([None, first, None])
    assert kept == [None, first, None] and demoted == []


def test_one_question_is_one_address_however_it_was_handed_over():
    """Scratch story 166 turn 4592: the keeper the player named was handed the
    line; the keeper the gate found addressed was handed the player's whole
    declaration. Both answered "I rang it." to one question."""
    line = "\"Who rang the bell just now -- and what's been brought in?\""
    whole = ("steps in over the threshold, lowers the brass storm lantern "
             "\"\"Tamsin Coyle, River Underwriters,\"\" \"\"Who rang the bell just now -- "
             "and what's been brought in?\"\"")
    first = _voice("Colynon Saltowford", "I rang it. I only just came through.",
                   answering=line)
    second = _voice("Lamynum Carromere", "I rang it. Nothing's come in yet.",
                    answering=whole)
    kept, demoted = _first_answer_only([first, second])
    assert kept[1]["dialogue_log_entry"] is None
    assert demoted[0][0] == "Lamynum Carromere" and demoted[0][3] == "answered"
