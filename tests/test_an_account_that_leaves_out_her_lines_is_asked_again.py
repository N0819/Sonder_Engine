"""The interpretation's account carries every line the player quoted, in the
order she said it -- or the Director is asked again, before anything is
encoded.

Chat 167 turn 4631 (validation story, 2026-10-10): the interpret prose
stopped after the player's first sentence -- "Nell stops at the corner ...
and looks at Ffion Rees properly for the first time since the cage." -- and
both of her quoted lines, her nod and her walk to the door never reached the
encoder. A row inserted afterwards can only guess at the beat's order (the
owner: "the deterministic floor isn't great as it doesn't care about event
order"); an account that carries the lines is encoded in the Director's own
order, with spans of their own. Quoted lines are the one part of an input a
word check grades reliably: over 992 stored spans, a carried line scored 0.8
or more and a dropped one 0.0.
"""

from agents import director_prose


RAW = ('Nell stops at the corner and looks at Ffion. "Thank you. I\'ll not '
       'forget who told me." She nods down the row. "Go home to your boy, '
       'Mrs Rees." She walks on alone to the door and knocks.')
SHORT = ("Nell stops at the corner where the road turns down past Bethel "
         "Chapel and looks at Ffion Rees properly for the first time.")
WHOLE = (SHORT + " She says, 'Thank you. I'll not forget who told me.' She "
         "nods down the row. 'Go home to your boy, Mrs Rees.' She walks on "
         "alone to the door and knocks.")


def test_an_account_that_leaves_out_a_quoted_line_is_asked_again():
    asked = []

    def ask():
        asked.append(1)
        return WHOLE, []

    prose, places, record = director_prose.carry_every_quoted_line(
        RAW, SHORT, [], ask)
    assert asked == [1]
    assert prose == WHOLE
    assert record["left_out"] == ["Thank you. I'll not forget who told me.",
                                  "Go home to your boy, Mrs Rees."]
    assert record["still_left_out"] == []


def test_an_account_that_carries_her_lines_is_not_asked_again():
    def ask():
        raise AssertionError("asked again for an account that carried every line")

    prose, _places, record = director_prose.carry_every_quoted_line(
        RAW, WHOLE, [], ask)
    assert prose == WHOLE and record == {}


def test_the_account_that_carries_more_of_her_lines_is_kept():
    """Asked again and still short: the fuller of the two accounts goes on,
    and what neither carries is left to the ledger's floor."""
    one_line = SHORT + " She says, 'Thank you. I'll not forget who told me.'"

    prose, _places, record = director_prose.carry_every_quoted_line(
        RAW, SHORT, [], lambda: (one_line, []))
    assert prose == one_line
    assert record["still_left_out"] == ["Go home to your boy, Mrs Rees."]


def test_the_interpretation_runs_the_check_before_it_encodes():
    import inspect
    source = inspect.getsource(director_prose.run)
    assert "carry_every_quoted_line(" in source
    assert source.index("carry_every_quoted_line(") < source.index("select_channels(")
