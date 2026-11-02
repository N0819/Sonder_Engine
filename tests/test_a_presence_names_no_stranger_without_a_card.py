"""A background voice is never handed the name of a stranger who has no card.

`background._presence_label_fn` is the identity floor for every field of a
presence's payload, and it knew only the cast and the player: a body no card
describes -- a townsperson the charter simulates, a person the Director
minted, another presence -- went through as its full name, while the
`present_others` list in the SAME payload called him by his look. Measured
(review 2026-11-01, agents_character_background F1, probe
`snip/label_probe.py`): for an entity "Master Leofelric Fenstonwell"
(appearance "a stout man in a scorched leather apron") the cast's floor
(`common.observer_label_fn`) answered "the stout man" and the presence
floor answered "Master Leofelric Fenstonwell" -- reaching the barman's beat
(`_beat_for_presence`), the scene manager's events (`_manager_events`) and a
thread's heard lines (`_thread_heard`), and his act surfaces through
`_presence_identity_floor`, whose roster held the cast alone. The fix the
cast's floor already had (`observer_label_fn`'s uncarded-person branch,
playerless Aldermill round 6) is now the presence floor's too, and a ledger
presence is called what `present_others` calls it.
"""

from __future__ import annotations

import agents.background as background
from agents.common import observer_label_fn

from tests.test_background_character_reply import _setup

STRANGER = "Master Leofelric Fenstonwell"
HOSTLER = "Hostler Gidoton Barrelfielder"


def _scene():
    return {
        "location": "Aldermill", "rooms": {"taproom": {"name": "Taproom", "adjacent": []}},
        "positions": {STRANGER: "taproom", "Barman": "taproom", "Ostler": "taproom"},
        "entities": {"e1": {"name": STRANGER, "kind": "person",
                            "appearance": "a stout man in a scorched leather apron"}},
        "attire": {}, "overlays": {},
    }


def _ledger():
    return {
        "barman": {"name": "Barman", "first_turn": 1, "last_turn": 1,
                   "sketch": {"station_room": "taproom"}},
        "ostler": {"name": "Ostler", "first_turn": 1, "last_turn": 1,
                   "sketch": {"station_room": "taproom"}},
        "hostler": {"name": HOSTLER, "first_turn": 1, "last_turn": 1,
                    "sketch": {"station_room": "taproom",
                               "appearance": "a wiry man with a scarred chin"}},
    }


def _ctx(temp_db):
    return _setup(temp_db, scene=_scene(), presences=_ledger())


def _named(text):
    return any(part in str(text) for part in ("Leofelric", "Fenstonwell",
                                              "Gidoton", "Barrelfielder"))


def test_the_presence_floor_labels_an_uncarded_person_as_the_cast_floor_does(temp_db):
    _chat_id, ctx = _ctx(temp_db)
    # Read off the stored scene when the caller holds none...
    shown = background._presence_label_fn(ctx, "Barman")(STRANGER)
    assert not _named(shown)
    assert shown == observer_label_fn(ctx.chat, "Barman", [], scene=_scene())(STRANGER)
    # ...and off the beat's scene when the caller holds it.
    assert background._presence_label_fn(ctx, "Barman", scene=_scene())(STRANGER) == shown


def test_a_ledger_presence_is_called_what_present_others_calls_it(temp_db):
    _chat_id, ctx = _ctx(temp_db)
    sc = _scene()
    shown = background._presence_label_fn(ctx, "Barman")(HOSTLER)
    assert not _named(shown)
    assert shown in background._present_others(ctx, sc, "taproom")


def test_a_recognized_name_and_a_thing_pass_unchanged(temp_db):
    chat_id, ctx = _ctx(temp_db)
    temp_db.wset(chat_id, "known", {"Barman": [STRANGER]})
    label = background._presence_label_fn(ctx, "Barman")
    assert label(STRANGER) == STRANGER
    assert label("the brass taps") == "the brass taps"


def test_his_line_reaches_the_barman_under_his_look(temp_db):
    _chat_id, ctx = _ctx(temp_db)
    sc = _scene()
    dr = {"dialogue_log": [{"speaker": STRANGER, "exact_quote": '"Another round?"',
                            "volume": "normal", "visibility": "overt",
                            "conceal_from": [], "intended_target": None}]}
    beat = background._beat_for_presence(
        dr, sc, "taproom", "Barman",
        label=background._presence_label_fn(ctx, "Barman"), ctx=ctx)
    assert "Another round?" in beat and not _named(beat)
    managed = [(1, "Barman", _ledger()["barman"], "taproom")]
    events = background._manager_events(ctx, dr, sc, managed, "full")
    assert events and not _named(events[0]["speaker"])
    heard = background._thread_heard(ctx, dr, ["Barman", "Ostler"],
                                     rooms={"Barman": "taproom", "Ostler": "taproom"},
                                     sc=sc)
    assert heard and not _named(heard[0]["speaker"])


def test_an_act_surface_naming_him_is_scrubbed_for_the_barman(temp_db):
    _chat_id, ctx = _ctx(temp_db)
    scrub = background._presence_identity_floor(ctx, "Barman")
    out = scrub(f"angles his shoulder past {STRANGER} toward the door")
    assert not _named(out) and "toward the door" in out
