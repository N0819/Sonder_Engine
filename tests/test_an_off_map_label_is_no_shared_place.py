"""An off-map label is a mind's own words for where it is, so two minds
writing the same words have not been shown to share a place.

world_offscreen_time F1 (audit 2026-11-01, CONFIRMED): two cast members who
each spent a skip "home" were each handed the other's doings as company --
`skip_itinerary.share_company` keyed co-presence on the folded label, and a
place named relative to its speaker ("home", "my room", "bed", "work") is a
different place for every speaker. `skip_memories` turns `seen` into a memory
of watching the other, so the leak became a remembered scene.

The rule now: a room the world holds is one place for everyone in it; off
the map, two minds kept company only where both name the same label AND each
names the other in its own `with` -- the one thing in the rows that says the
two meant the same place.
"""

from world import skip_itinerary as itin


def _row(start, end, *, room=None, away=None, doing="", with_=(),
         asleep=False):
    return {"from_s": start, "until_s": end, "room": room, "away": away,
            "where_text": room or away or "", "doing": doing, "why": "",
            "asleep": asleep, "with": list(with_), "seen": [],
            "weather": None, "outcome": "done", "reason": None}


def _as_named(_observer, other):
    return other


def test_two_minds_each_at_home_are_not_told_each_others_doings():
    logs = {"Alice": [_row(0, 100, away="home", doing="bathes by the fire")],
            "Bob": [_row(0, 100, away="Home.", doing="counts the stolen coins")]}
    itin.share_company(logs, _as_named)
    assert logs["Alice"][0]["seen"] == []
    assert logs["Bob"][0]["seen"] == []


def test_the_same_holds_for_a_label_in_an_unspaced_script():
    logs = {"アリス": [_row(0, 100, away="家", doing="湯に浸かる")],
            "ボブ": [_row(0, 100, away="家", doing="盗んだ金を数える")]}
    itin.share_company(logs, _as_named)
    assert logs["アリス"][0]["seen"] == []
    assert logs["ボブ"][0]["seen"] == []


def test_two_minds_who_name_each_other_at_one_label_keep_company():
    logs = {"Pell Hardacre": [_row(0, 100, away="the harbour pub",
                                   doing="plays dominoes", with_=["Nell"])],
            "Nell": [_row(50, 150, away="The Harbour Pub",
                          doing="nurses a cider", with_=["Pell"])]}
    itin.share_company(logs, _as_named)
    assert logs["Pell Hardacre"][0]["seen"] == [
        {"who": "Nell", "doing": "nurses a cider"}]
    assert logs["Nell"][0]["seen"] == [
        {"who": "Pell Hardacre", "doing": "plays dominoes"}]


def test_company_one_mind_meant_is_that_minds_wish_alone():
    logs = {"Pell": [_row(0, 100, away="the pub", doing="plays dominoes",
                          with_=["Nell"])],
            "Nell": [_row(0, 100, away="the pub", doing="nurses a cider")]}
    itin.share_company(logs, _as_named)
    assert logs["Pell"][0]["seen"] == []
    assert logs["Nell"][0]["seen"] == []


def test_naming_each_other_at_two_different_labels_is_not_one_place():
    logs = {"Ada": [_row(0, 100, away="the market", doing="haggles",
                         with_=["Bram"])],
            "Bram": [_row(0, 100, away="home", doing="mends a net",
                          with_=["Ada"])]}
    itin.share_company(logs, _as_named)
    assert logs["Ada"][0]["seen"] == [] and logs["Bram"][0]["seen"] == []


def test_a_room_the_world_holds_is_still_shared_by_whoever_stands_in_it():
    logs = {"A": [_row(0, 100, room="kitchen", doing="pours the tea")],
            "B": [_row(50, 150, room="kitchen", doing="reads the log")]}
    itin.share_company(logs, _as_named)
    assert logs["A"][0]["seen"] == [{"who": "B", "doing": "reads the log"}]
    assert logs["B"][0]["seen"] == [{"who": "A", "doing": "pours the tea"}]


def test_a_with_naming_someone_elses_kin_is_not_the_mind_itself():
    logs = {"Pell": [_row(0, 100, away="the pub", doing="plays dominoes",
                          with_=["Nell's brother"])],
            "Nell": [_row(0, 100, away="the pub", doing="nurses a cider",
                          with_=["Pell"])]}
    itin.share_company(logs, _as_named)
    assert logs["Pell"][0]["seen"] == [] and logs["Nell"][0]["seen"] == []
