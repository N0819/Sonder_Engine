"""Listening on purpose earns the topic; a bystander still catches nothing.

`subject_label`'s rule is right and was unconditional: "a subject that is not
a person (a news key) yields empty: what a BYSTANDER catches of that is that
something happened". It was applied to everyone, because the engine had no way
to tell a bystander from somebody listening on purpose.

Measured (Aldermill, third run, 2026-09-19): the charter's own `window_acts`
carried real informational talk --

    {"actor": "bellows_striker:0002", "act": "ask",
     "other": "bellows_striker:0003",
     "subject": "news:stock_surplus:charcoal@20.0000", ...}

-- and the one path to an observer blanked every `news:` subject, so the line
rendered "asking someone something". Sal Weatherby, whose drive is "know how a
place really works -- asks the people nobody asks", sat in a taproom for
twenty-one beats deliberately listening and received a contentless hum every
one of them.

THE INVARIANT, and the reason this is a grade rather than a new channel:
attending may only UN-BLANK WHAT THE OBSERVER ALREADY HAD A CHANNEL TO. The
fragment has already passed the hearing and density gates before this runs --
the engine has already ruled that this body catches this act. All that changes
is whether the topic inside it is legible. Attention never adds a channel, and
a crush still admits nothing at all.

THE TOPIC, NOT THE PROPOSITION. An overhearing listener catches what the talk
is ABOUT, not what was concluded: "asking the tapster about charcoal", never
"charcoal is in surplus at the smithy". The key's own subject token is exactly
that much and no more, which is why this reads it rather than resolving the
claim behind it.
"""

from world.charter_chatter import subject_label


def test_a_bystander_still_catches_nothing():
    assert subject_label("news:stock_surplus:charcoal@20.0000") == ""


def test_attending_earns_the_topic():
    assert subject_label("news:stock_surplus:charcoal@20.0000",
                         attending=True) == "charcoal"


def test_a_multiword_topic_reads_as_words():
    assert subject_label("news:stock_restored:horseshoes_and_nails@8.0000",
                         attending=True) == "horseshoes and nails"


def test_a_topicless_news_key_stays_blank_even_attending():
    """Some events name no subject at all (`news:sighting:@4.0`). There is no
    topic to catch, and inventing one would be the engine speaking."""
    assert subject_label("news:sighting:@4.0000", attending=True) == ""


def test_a_topic_that_is_a_body_is_that_person_never_its_key():
    """Playerless Aldermill round 9 (2026-09-23): "asking the journeyman about
    head miller:0001" in Emory's views at idx 3, 7 and 11."""
    bodies = {"head_miller:0001": {"name": "Duneloc Lowenmill"}}
    assert subject_label("news:asked_after:head_miller:0001@12.0000",
                         bodies=bodies, attending=True) == "Duneloc Lowenmill"
    assert subject_label("news:asked_after:head_miller:0001@12.0000",
                         attending=True) == "head miller"


def test_a_person_subject_is_unchanged_by_attention():
    """A named body was always legible -- "overhearing a stranger's name is
    how a name first reaches you" -- and attention must not alter that."""
    bodies = {"tapster:0001": {"name": "Ferrin"}}
    for attending in (False, True):
        assert subject_label("tapster:0001", bodies=bodies,
                             attending=attending) == "Ferrin"


def test_attention_does_not_reach_past_the_gates_that_already_ran():
    """A crush admits no fragment at all, and no amount of listening changes
    that -- the din is the whole percept. Attention grades what arrived; it
    never decides whether anything arrives."""
    from world.charter_chatter import overheard_fragment
    from world.crowds import CRUSH

    rows = [{"actor": "a", "act": "ask", "other": "b",
             "subject": "news:stock_surplus:charcoal@20.0000"}]
    assert overheard_fragment(rows, density=CRUSH, seed_material="x") is None


def test_the_room_a_body_attends_to_is_read_off_its_focus():
    """`attending_this_room` asks the engine's own attention record rather
    than inventing a second notion of attending."""
    from agents.common import attending_this_room

    sc = {"positions": {"Sal": "taproom", "Host": "taproom", "Boy": "square"},
          "rooms": {"taproom": {"anchors": {"kitchen_door": {"desc": "a doorway"}}},
                    "square": {}},
          "orientation": {}}

    def focus(rec):
        sc["orientation"]["Sal"] = {"focus": rec}
        return attending_this_room(sc, "Sal", "taproom")

    assert focus({"kind": "anchor", "ref": "kitchen_door"}) is True
    assert focus({"kind": "target", "ref": "Host"}) is True

    # ATTENTION POINTED OUT OF THE ROOM IS THE BYSTANDER CASE BY
    # CONSTRUCTION: a body watching the street is not listening to the bar.
    assert focus({"kind": "edge", "ref": "square"}) is False
    # A body it is watching who stands somewhere else is not this room either.
    assert focus({"kind": "target", "ref": "Boy"}) is False
    # No focus is no attention, which leaves every story that never wrote an
    # orientation record exactly where it was.
    assert focus(None) is False
    assert attending_this_room({}, "Sal", "taproom") is False


def test_the_grade_reaches_the_seam_and_the_memo_keeps_them_apart(monkeypatch):
    """The wiring, which the two ends passing did not prove: a first mutation
    that hard-coded `attending=True` inside `chatter_for_room` was caught by
    nothing until this existed.

    Patches `world.charter_chatter.subject_label` -- the module that DEFINES
    it, never the caller's re-export, which would be inert -- and asserts both
    that the observer's grade arrives and that two observers of one room with
    different attention are not served each other's cached answer.
    """
    import agents.common as common
    from world import charter_chatter

    seen = []

    def _spy(key, *, bodies=None, figures=None, naming=None, attending=False):
        seen.append(bool(attending))
        return "charcoal" if attending else ""

    monkeypatch.setattr(charter_chatter, "subject_label", _spy)

    picked = {"actor": "a", "act": "ask", "other": "b",
              "subject": "news:stock_surplus:charcoal@20.0000"}
    # The real one picks one of the ROWS the caller built, which carry the
    # charter slice beside the act; returning the act alone loses it.
    monkeypatch.setattr(charter_chatter, "overheard_fragment",
                        lambda rows, **k: dict(rows[0]))
    monkeypatch.setattr(charter_chatter, "hum_rank", lambda *a, **k: 0)

    inputs = {"charters": [{"key": "k", "bodies": {}, "watch": {}, "posts": {},
                            "naming": None, "figures": {},
                            "known_bodies": frozenset(),
                            "presented_bodies": frozenset(),
                            "bindings": frozenset(), "clock_hours": 1.0,
                            "window_acts": [dict(picked, place="forge")]}],
              "memo": {}}
    sc = {"rooms": {"forge": {}}, "positions": {}}

    quiet = common.chatter_for_room(1, sc, "forge", inputs, attending=False)
    loud = common.chatter_for_room(1, sc, "forge", inputs, attending=True)

    assert seen == [False, True], (
        "the observer's grade must reach subject_label, not a constant")
    assert "something" in quiet[0]["what"]
    assert "about charcoal" in loud[0]["what"], (
        "a memo keyed by room alone serves the bystander's answer to the "
        "listener standing beside them")


def test_an_edge_focus_attends_the_room_it_points_INTO():
    """Watching through a doorway is attending to what is on the other side.

    The first cut of `attending_this_room` read an edge focus as the bystander
    case -- "a body watching the street is not listening to the bar" -- which
    is true about the bar and wrong about the street.

    Measured (Aldermill, fourth run, 2026-09-19): Sal Weatherby sat in the
    Wheel and Bushel with
    `focus {"kind": "edge", "ref": "wheel_bushel_kitchen"}` -- watching the
    kitchen doorway, which is the whole of what she went in there to do -- and
    took the bystander grade for BOTH rooms. Topics overheard across 39 beats:
    zero.

    The invariant is untouched. Perception only asks this for rooms the
    observer's hearing already reaches, so granting the grade for the room she
    is watching un-blanks a fragment she was receiving anyway; it never adds a
    room she could not hear.
    """
    from agents.common import attending_this_room

    sc = {"positions": {"Sal": "taproom"},
          "rooms": {"taproom": {"anchors": {"bench": {"desc": "a bench"}}},
                    "kitchen": {}, "square": {}},
          "orientation": {"Sal": {"focus": {"kind": "edge", "ref": "kitchen"}}}}

    assert attending_this_room(sc, "Sal", "kitchen") is True
    # ...and NOT the room she is sitting in, which is the half the first cut
    # had right: her attention is through the door, not on the bar.
    assert attending_this_room(sc, "Sal", "taproom") is False
    assert attending_this_room(sc, "Sal", "square") is False
