"""A situation acted in during one window can be acted in during the next.

`close_stale` measured idleness at the END of the window about to be lived
(`at + hours`), so a practice that last produced an effect at this window's
start was `hours` old before anybody could act in it: at any window of
`IDLE_CLOSE_HOURS` (2.0) or longer every situation closed before its first
act -- presim's 4 h and 8 h, the town's ordinary 4 h advance, the skip's
2.0 h grid -- spawned practices were dead on arrival, and `reconcile` (which
needs a quarrel 12 h old) was reachable only between 1.72 h and 2.0 h windows.
Measured (audit world_charter_generation_run F6, a planted quarrel with a
grievance): at 4 h windows, zero acts and closed at the first window. Idleness
is measured where the window opens -- the last instant anything could have
been done -- and the 2 h constant stays the owner's."""
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_practice import _open
from world.charter_run import step


def _hall():
    charter = normalize_charter({
        "key": "hall", "upkeeps": {}, "posts": {},
        "bodies": {"a": {"place": "hall", "name": "Ada"},
                   "b": {"place": "hall", "name": "Bel"}},
        "active_places": ["hall"]})
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    # Ada holds her own firsthand claim that Bel did harm here: a grievance.
    charter["minds"] = {
        "a": {"news:harm_done:b@0.0000": {
            "kind": "news", "body": "news:harm_done:b@0.0000",
            "event_kind": "harm_done", "about": "b", "actor": "b",
            "place": "hall", "happened_at": 0.0, "strength": 0.9,
            "as_of_hours": 0.0, "heard_from": None},
              "b": {"body": "b", "competence": {}, "believed_available": True,
                    "strength": 1.0, "as_of_hours": 0.0, "heard_from": None}},
        "b": {"a": {"body": "a", "competence": {}, "believed_available": True,
                    "strength": 1.0, "as_of_hours": 0.0, "heard_from": None}}}
    key, entry = _open("quarrel", "hall", {"a": "a", "b": "b"}, 0.0,
                       about="b")
    charter["practices"] = {key: entry}
    return charter


def _acts(window, windows):
    charter = _hall()
    seen = []
    for index in range(windows):
        charter, _events = step(charter, hours=window, seed=index)
        seen.extend((index, row["act"]) for row in
                    charter.get("window_acts") or ())
    return seen


def test_a_quarrel_at_four_hour_windows_is_acted_in():
    acts = [act for _i, act in _acts(4.0, 6)]
    assert "accuse" in acts


def test_a_quarrel_at_four_hour_windows_lives_until_it_can_end_in_peace():
    """`reconcile` needs a quarrel twelve hours old. At 4 h windows the
    quarrel used to close at the first window; it now lives while it is
    acted in, and is open -- and peace on offer to the accuser -- once it is
    old enough."""
    from world.charter_practice import _afford_reconcile, _state_of
    charter = _hall()
    for index in range(4):
        charter, _events = step(charter, hours=4.0, seed=index)
    quarrel = next((p for p in (charter.get("practices") or {}).values()
                    if p["kind"] == "quarrel"), None)
    assert quarrel is not None, "the quarrel outlived its first window"
    at = float(charter["clock_hours"])
    assert at - float(quarrel["opened_at"]) >= 12.0
    regard = dict((charter.get("politics") or {}).get("regard") or {})
    state = _state_of(charter["bodies"], charter.get("minds") or {},
                      charter.get("needs") or {}, regard, {}, at)
    assert _afford_reconcile("a", "b", quarrel, state) is not None
