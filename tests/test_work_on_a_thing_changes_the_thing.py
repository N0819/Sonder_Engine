"""The author must be told a beat has a world half.

Measured (Aldermill, two causality bubbles, 2026-09-19, both runs): across 60
beats the Director's prose author filed 118 category tags using six words --
`contacts` 41, `poses` 38, `attention` 32, `stations` 9, `body` 7,
`positions` 2. Every one is about a BODY. `objects`, `entities`,
`substance_ops` and `world_facts` never appeared once, the objects hand ran on
one beat of sixty and the social hand on none, and `state_diff.entities` was
written zero times in either run.

So Emory Vane hooked packed grit out of a sluice runner for twenty-three
consecutive beats and the runner was never once recorded as different. The
body changed, perception had something new to say about the body, and his next
appraisal was about his own posture while the thing he was working on stayed
exactly as unresolved as it was.

THE SHEET ALREADY SAID THE HALF THAT PRODUCES THIS: "A visible attempt with no
record change still has its event and observable action, with categories:[]".
That is correct for a push that does not give and was being read as covering
work that plainly accumulates. The clause states the boundary using the
engine's own test -- would the thing be different next beat if nothing else
happened -- and names the exception as that test's complement, rather than
listing verbs that count as work.
"""

import pytest

from llm.prompts import DEFAULT_PROMPTS


def _sheet():
    return DEFAULT_PROMPTS["director_resolve_lean"]


def test_the_author_is_told_the_consequence_belongs_to_the_thing():
    sheet = _sheet()
    assert "WORK ON A THING CHANGES IT" in sheet
    assert "route its own channel (entities) beside the contact" in sheet


def test_the_boundary_is_the_engine_s_own_test_and_not_a_verb_list():
    """`sensory_events` already decides what outlasts a beat with exactly this
    sentence. One test stated once reaches the case nobody has hit yet; a list
    of verbs reaches only what it names."""
    sheet = _sheet()
    assert "different next beat if nothing else happened" in sheet


def test_the_exception_survives_the_reduction():
    """A reduction is real only if it still says everything the child said.
    The child here is the no-record-change rule, and it must still be there
    and still be reachable -- otherwise the clause licenses inventing a state
    effect for every push that does not give."""
    sheet = _sheet()
    assert "invents no state effect to earn a channel" in sheet
    assert "A span that neither changes nor asks it" in sheet
    assert "keeps its event and observable" in sheet
    assert "categories:[]" in sheet


def test_a_body_s_posture_is_not_the_record_of_its_work():
    """The measured failure in one sentence: 118 of 118 tags were the body."""
    assert "A body's posture, grip and place are never the record of its work" in _sheet()
