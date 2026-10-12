"""A thing this beat put into a body's hands is read by that body.

Saltmarsh Crossing (2026-10-11, scratch chat 170, idx 24): a clerk handed the
player a loading slip, she held it to the window and read it line by line,
and set it down on the desk. The resolve wrote two transfers -- into her
hands, then onto the desk -- and the slip's own record held every line she
read ("220 qtrs barley, 40 qtrs wheat ... Consignor: Venn"). Her view held
none of them: `_things_read_by` admitted a standing contact, a shared
station and her own `look`, and a thing held within the beat is none of the
three.

The HANDLED admission reads it as a look is read -- seen in full, by the same
test -- so light, sight and where the thing now is still decide, and a
transfer the commit refused (a thing out of reach) reads nothing.
"""
from __future__ import annotations

from agents import composer
from agents.perception import _own_handled, _things_read_by

BODIES = ["Agnes Holloway", "Mr Larkerwick"]
SLIP = {"name": "loading slip", "kind": "document", "portable": True,
        "state": {"lines": "220 qtrs barley, 40 qtrs wheat; Consignor: Venn"}}


def _scene(*, light="lit"):
    return {
        "rooms": {
            "grain_office": {"name": "Grain office", "light": light,
                             "adjacent": [{"to": "quay", "barrier": "closed_door"}],
                             "anchors": {"desk": {"desc": "a counting-house desk"}}},
            "quay": {"name": "Quay", "light": "lit",
                     "adjacent": [{"to": "grain_office", "barrier": "closed_door"}]},
        },
        "positions": {"Agnes Holloway": "grain_office", "Mr Larkerwick": "grain_office",
                      "loading_slip": "grain_office", "day_book": "quay"},
        "stations": {"Agnes Holloway": {"at": None, "cell": [1, 1]},
                     "Mr Larkerwick": {"at": None, "cell": [3, 1]},
                     "loading_slip": {"at": "desk"}},
        "entities": {
            "loading_slip": dict(SLIP),
            "day_book": {"name": "day book", "kind": "book", "portable": True,
                         "state": {"entries": "the Swallow's lading, struck through"}},
            "agnes": {"name": "Agnes Holloway", "kind": "person"},
            "larkerwick": {"name": "Mr Larkerwick", "kind": "person"},
        },
        "contacts": [],
    }


def _resolve(*ops):
    return {"state_diff": {"inventory_ops": list(ops)}}


HANDED_AND_SET_DOWN = _resolve(
    {"op": "transfer", "object_id": "loading_slip", "from_id": "Mr Larkerwick",
     "to_id": "Agnes Holloway", "relation": "held"},
    {"op": "transfer", "object_id": "loading_slip", "from_id": "Agnes Holloway",
     "to_id": "grain_office", "relation": "held"})


def _read(sc, who, res):
    rows = _things_read_by(sc, who, "grain_office", bodies=BODIES,
                           handled=_own_handled(sc, res, who))
    return {eid: channel for eid, _entity, channel in rows}


def test_what_this_beat_put_in_her_hands_is_what_she_handled():
    sc = _scene()
    assert _own_handled(sc, HANDED_AND_SET_DOWN, "Agnes Holloway") == ["loading_slip"]
    assert _own_handled(sc, HANDED_AND_SET_DOWN, "Mr Larkerwick") == [], \
        "handing a thing away is not taking it into the hand"


def test_the_slip_she_was_handed_is_read_by_sight():
    sc = _scene()
    assert _read(sc, "Agnes Holloway", HANDED_AND_SET_DOWN) == {"loading_slip": "sight"}
    rows = _things_read_by(sc, "Agnes Holloway", "grain_office", bodies=BODIES,
                           handled=["loading_slip"])
    view = composer.render_view(composer.thing_reading_percepts([
        (entity.get("name"), composer.thing_reading_text(entity.get("state")), eid, channel)
        for eid, entity, channel in rows]), mode="character").text
    assert "220 qtrs barley" in view and "Venn" in view, view


def test_before_this_nothing_admitted_it():
    """The measured beat: no contact, no shared station, no look."""
    assert _read(_scene(), "Agnes Holloway", _resolve()) == {}


def test_the_clerk_who_handed_it_over_reads_nothing_new():
    assert "loading_slip" not in _read(_scene(), "Mr Larkerwick", _resolve(
        {"op": "transfer", "object_id": "loading_slip", "from_id": "Mr Larkerwick",
         "to_id": "Agnes Holloway", "relation": "held"}))


def test_in_the_dark_a_thing_in_the_hand_is_not_read():
    assert _read(_scene(light="dark"), "Agnes Holloway", HANDED_AND_SET_DOWN) == {}


def test_a_thing_pocketed_unseen_is_not_read():
    assert _read(_scene(), "Agnes Holloway", _resolve(
        {"op": "transfer", "object_id": "loading_slip", "from_id": "Mr Larkerwick",
         "to_id": "Agnes Holloway", "relation": "pocket"})) == {}


def test_a_transfer_naming_a_thing_out_of_reach_reads_nothing():
    """A hand-off the commit refused still stands in the resolve's diff; the
    day book is behind a closed door, and stays unread."""
    assert _read(_scene(), "Agnes Holloway", _resolve(
        {"op": "transfer", "object_id": "day_book", "from_id": "Mr Larkerwick",
         "to_id": "Agnes Holloway", "relation": "held"})) == {}


def test_a_body_handed_over_is_never_read_as_a_thing():
    assert _read(_scene(), "Agnes Holloway", _resolve(
        {"op": "transfer", "object_id": "Mr Larkerwick", "from_id": "quay",
         "to_id": "Agnes Holloway", "relation": "held"})) == {}


# ---------------------------------------------------------------------------
# AN ACT THAT ASKS IS ANSWERED, UNCHANGED OR NOT. The slip's lines had reached
# the player's view two beats earlier, when she stood at the desk it lay on;
# on the beat she took it up and read it, the delta view dropped its reading
# as furniture and the page answered nothing (`composer.asked_this_beat`).

from agents.perception import _things_asked_by  # noqa: E402

READING = "examined: 220 qtrs barley, 40 qtrs wheat; consignor: Venn"


def _reading(asked):
    return composer.thing_reading_percepts([("loading slip", READING, "loading_slip",
                                             "sight", asked)])


def _player_view(percepts, language):
    told = {p.dedupe_key for p in _reading(False)}
    return composer.render_view(percepts, mode="player", prev_standing=told,
                                language=language).text


def test_a_reading_already_told_is_furniture_until_an_act_asks_for_it():
    for language in ("en", "ja"):
        assert "220" not in _player_view(_reading(False), language), language
        assert "220" in _player_view(_reading(True), language), language


def test_an_asked_reading_leads_the_beat():
    (percept,) = _reading(True)
    told = {percept.dedupe_key}
    assert composer.leads_the_beat(percept, "unchanged", told)
    (quiet,) = _reading(False)
    assert not composer.leads_the_beat(quiet, "unchanged", told)


def test_an_asked_reading_keeps_its_ledger_key():
    """Re-said, never re-keyed: a key that moved would read as `changed` on
    the next beat, a slip that did nothing announced as news."""
    assert [p.dedupe_key for p in _reading(True)] == [p.dedupe_key for p in _reading(False)]


def test_what_her_act_asked_about_is_matched_by_id_name_or_alias():
    sc = _scene()
    sc["entities"]["loading_slip"]["aliases"] = ["the Swallow's slip"]
    assert _things_asked_by(sc, looks=["the Swallow's slip"]) == ["loading_slip"]
    assert _things_asked_by(sc, handled=["loading_slip"], looks=["loading slip"]) == ["loading_slip"]
    assert _things_asked_by(sc) == []


# ---------------------------------------------------------------------------
# A NAME WRITTEN ON A THING IS THE NAME, NEVER WHOSE BODY IT IS. The view's
# identity floor swapped an unknown name for the observer's label for that
# body -- right for "Kai steps toward you", and the leak itself for a slip
# that reads "Loading supervised: Larkerwick": rewritten to "the old thickset
# tally clerk", it told her which man in front of her the name belonged to
# (idx 22 in the view; idx 24 onto the page once the read was answered).

from types import SimpleNamespace  # noqa: E402

from agents.common import _scrub_unknown_identities  # noqa: E402
from agents.perception import _authored_prose_gate  # noqa: E402

SLIP_TEXT = "Loading supervised: Larkerwick. Tally: Kelleystone. Consignor: Venn."
STRANGERS = [{"name": "Mr Larkerwick", "appearance": "old thickset tally clerk"},
             {"name": "Mr Kelleystone", "appearance": "elderly tally clerk"}]


def _quoted(form):
    return f"“{form}”"


def test_written_text_keeps_the_name_as_written():
    out, leaked = _scrub_unknown_identities(
        SLIP_TEXT, allowed_forms=["Agnes Holloway"], unknown_sources=STRANGERS,
        labels={"Mr Larkerwick": "the old thickset tally clerk"}, as_written=_quoted)
    assert out == "Loading supervised: “Larkerwick”. Tally: “Kelleystone”. Consignor: Venn."
    assert leaked == ["Mr Larkerwick", "Mr Kelleystone"]
    assert "clerk" not in out


def test_prose_about_a_body_is_still_labelled():
    """The floor's ordinary work is untouched: a name in an act is the leak
    a descriptor repairs."""
    out, _ = _scrub_unknown_identities(
        "Larkerwick shakes his head.", allowed_forms=["Agnes Holloway"],
        unknown_sources=STRANGERS, labels={"Mr Larkerwick": "the old thickset tally clerk"})
    assert out == "the old thickset tally clerk shakes his head."


def test_the_view_floor_leaves_a_written_name_as_written():
    """The whole view is scrubbed again last of all; a quoted name is out of
    its reach, so the reading survives it word for word."""
    written, _ = _scrub_unknown_identities(
        SLIP_TEXT, allowed_forms=["Agnes Holloway"], unknown_sources=STRANGERS,
        as_written=_quoted)
    again, leaked = _scrub_unknown_identities(
        written, allowed_forms=["Agnes Holloway"], unknown_sources=STRANGERS,
        labels={"Mr Larkerwick": "the old thickset tally clerk"})
    assert again == written and leaked == []


def test_the_observers_gate_writes_it_in_her_language():
    gate = _authored_prose_gate(SimpleNamespace(warnings=[]), "perception_outcome",
                                "Agnes Holloway", {"Agnes Holloway": set()},
                                [{"name": "Agnes Holloway"}, *STRANGERS])
    assert gate.written(SLIP_TEXT) == (
        "Loading supervised: “Larkerwick”. Tally: “Kelleystone”. Consignor: Venn.")
    known = _authored_prose_gate(SimpleNamespace(warnings=[]), "perception_outcome",
                                 "Agnes Holloway", {"Agnes Holloway": {"Mr Larkerwick"}},
                                 [{"name": "Agnes Holloway"}, *STRANGERS])
    assert "Loading supervised: Larkerwick." in known.written(SLIP_TEXT), \
        "a name she knows is hers to read plainly"
