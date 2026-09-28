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

THE CLAUSE WENT WITH THE CAUSAL DIRECTOR ON 2026-09-27. It lived on the
ledger author's sheet ("WORK ON A THING CHANGES IT", the "different next beat
if nothing else happened" boundary, and "A body's posture, grip and place are
never the record of its work"). On the prose path the decision model's
`entities` question decides whether the channel is granted, and no prose card
carries the clause: `docs/UNBUILT_PIPELINE.md` § 1.1. What survives is the
exception, on the encoder's core.
"""

from llm.prompts import unified_specialist_prompt


def test_the_exception_survives_the_reduction():
    """A reduction is real only if it still says everything the child said.
    The child here is the no-record-change rule, and it must still be there
    and still be reachable -- otherwise a sheet licenses inventing a state
    effect for every push that does not give."""
    core = unified_specialist_prompt([], "en", [])
    assert ("A brief reaction of a body changes no record and no tool owns it: "
            "its observable carries it, with no transforms and no tool asked "
            "for") in core
    assert ("Every outward act the prose states is an event, whether or not a "
            "tool records it") in core
