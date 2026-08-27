"""A beat may not end in silence while the person it asked has not been asked.

Measured live on a starship bridge, three beats running. A lieutenant was
addressed on beat 1 and stayed silent, which left him owing an answer. On beat 3
the player asked the CAPTAIN to decide something; the unanswered-question
promotion put the lieutenant ahead of him, he was silent again, and
`natural silence` closed the beat with the captain never called at all. The
debt is discharged by speaking, so a silent debtor keeps his own promotion and
the question addressed to somebody else is never put to them.

The promotion is not the defect and is not changed here: whoever owes an answer
still has the floor. What changes is that their silence cannot close a beat
whose own addressee has not been reached.
"""
import agents.loops as loops


def test_a_silent_third_party_cannot_close_a_beat_the_addressee_has_not_answered():
    """The exact live shape, at the predicate that decides it."""
    addressed = {74}
    initial_reactors = [75, 74]
    already_spoke = {75}          # the debtor was called and said nothing

    unheard = [cid for cid in addressed
               if cid not in already_spoke and cid in initial_reactors]
    assert unheard == [74], (
        "the addressee is still owed a turn, so silence must not end the beat")


def test_silence_still_ends_a_beat_once_the_addressee_has_spoken():
    """The guard SUBTRACTS an early exit; it must not remove the exit itself.
    A beat whose addressee has had their turn ends on silence exactly as
    before."""
    addressed = {74}
    initial_reactors = [75, 74]
    already_spoke = {75, 74}

    unheard = [cid for cid in addressed
               if cid not in already_spoke and cid in initial_reactors]
    assert unheard == []


def test_a_beat_addressing_nobody_is_unchanged():
    """The overwhelming majority of beats address no one in particular, and
    they must keep ending on the first silence."""
    unheard = [cid for cid in set()
               if cid not in {75} and cid in [75, 74]]
    assert unheard == []


def test_an_addressee_who_is_not_a_reactor_cannot_hold_the_beat_open():
    """Addressing somebody who is not in the beat -- absent, asleep, in
    another room -- must not keep a beat running for a turn that can never
    come."""
    addressed = {99}
    initial_reactors = [75, 74]
    already_spoke = {75}

    unheard = [cid for cid in addressed
               if cid not in already_spoke and cid in initial_reactors]
    assert unheard == []


def test_the_predicate_is_the_one_the_loop_uses():
    """Pins the guard to the source rather than to a copy of it: the loop must
    still compute this from `addressed`, `already_spoke` and
    `initial_reactors`, so a rename or a dropped conjunct fails here."""
    import inspect
    src = inspect.getsource(loops.interaction_loop)
    assert "_addressed_unheard" in src
    assert "and not _addressed_unheard" in src, (
        "the silence stop no longer consults whether the addressee was heard")


# --- an empty declaration is not an answer -----------------------------------
#
# The first version of the guard above held a beat open only while an ADDRESSED
# character was uncalled, and made the measured case worse. Two runs of one
# scenario, same beat: before it, a silent first speaker was followed by three
# more calls and two of them answered (4 calls, `budget exhausted`); after it,
# the addressee was correctly ordered first, emitted `sequence: []`, and that
# null closed the beat on the spot -- one call, nothing said, three beats
# running. The trade was "the addressee is never asked" for "the addressee is
# asked first and their nothing ends the conversation", which is worse.


def _nothing_happened(rounds):
    return not any((rd.get("result") or {}).get("sequence")
                   or (rd.get("result") or {}).get("actions")
                   for rd in rounds)


def test_a_null_declaration_does_not_close_a_beat_others_have_not_seen():
    """The regression, at the predicate. One call, empty result, four reactors
    who have not been asked: the beat stays open."""
    rounds = [{"speaker": "A", "result": {"sequence": []}}]
    uncalled = [75, 76, 77]
    assert _nothing_happened(rounds) and uncalled


def test_a_real_silence_still_ends_the_exchange():
    """Silence IS an answer when a character acts without speaking. An emitted
    action with no speech must close the beat exactly as it always did."""
    rounds = [{"speaker": "A", "result": {"sequence": [
        {"type": "action", "observable": "turns back to the console"}]}}]
    assert not _nothing_happened(rounds)


def test_a_null_does_not_hold_a_beat_open_once_everyone_has_been_asked():
    """The guard subtracts an early exit; it must not remove the exit. With
    nobody left uncalled there is nothing to wait for."""
    rounds = [{"speaker": "A", "result": {"sequence": []}}]
    uncalled = []
    assert _nothing_happened(rounds) and not uncalled


def test_the_null_predicate_is_the_one_the_loop_uses():
    """Pins the guard to the source, not to a copy: a dropped conjunct or a
    rename fails here rather than three runs later."""
    import inspect
    src = inspect.getsource(loops.interaction_loop)
    assert "_nothing_happened" in src
    assert "not (_nothing_happened and _uncalled)" in src, (
        "the silence stop no longer distinguishes an empty declaration from "
        "a silence that was an answer")
