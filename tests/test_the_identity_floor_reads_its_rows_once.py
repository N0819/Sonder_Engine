"""The identity floor reads what it needs once per labeller, not once per name.

agents_common audit, Efficiency 3: `observer_name_scrub` read the observer's
`known` ledger after `observer_label_fn` -- which it calls -- had already
read it, and the in-view labeller's `_presence_surface` recomputed a room's
whole `presence_figures_for_room` (a fresh `chatter_inputs`: the registry
slices, the presence ledger, the placements, the derived records) for EACH
dim-light name it labelled. Per observer, per payload. The answers are the
same; the reads are now one.
"""

from __future__ import annotations

import json
import time

from agents import common_figures, common_identity


def _chat(db):
    from core.db import wset
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Dim hall", "", time.time()))
    wset(cid, "known", {})
    names = ["Bram", "Cole", "Dain"]
    wset(cid, "background_presences", {
        "p_%s" % n.lower(): {"uid": "p_%s" % n.lower(), "name": n,
                             "nature": "person",
                             "sketch": {"station_room": "hall",
                                        "appearance": "a stooped man"},
                             "first_turn": 0, "last_turn": 0}
        for n in names})
    scene = {"rooms": {"hall": {"name": "the hall", "desc": ".",
                                "light": "dim", "adjacent": []}},
             "positions": {"Ada": "hall", **{n: "hall" for n in names}},
             "stations": {},
             "entities": {n: {"name": n, "kind": "person",
                              "appearance": "a stooped man"} for n in names}}
    return cid, names, scene


def test_the_in_view_labeller_derives_a_rooms_figures_once(temp_db, monkeypatch):
    cid, names, scene = _chat(temp_db)
    calls = []
    real = common_figures.chatter_inputs

    def counting(*args, **kwargs):
        calls.append(args[:1])
        return real(*args, **kwargs)

    monkeypatch.setattr(common_figures, "chatter_inputs", counting)
    monkeypatch.setattr(common_identity, "chatter_inputs", counting,
                        raising=False)
    label = common_identity.observer_view_label_fn({"id": cid}, "Ada", [], scene)
    labels = [label(n) for n in names]
    assert all(l and l not in names for l in labels), labels
    assert len(calls) == 1, calls


def test_the_name_scrub_reads_the_known_ledger_once(temp_db, monkeypatch):
    cid, _names, scene = _chat(temp_db)
    reads = []
    real = common_identity.wget

    def counting(chat_id, key, default=None):
        reads.append(key)
        return real(chat_id, key, default)

    monkeypatch.setattr(common_identity, "wget", counting)
    scrub = common_identity.observer_name_scrub({"id": cid}, "Ada", [])
    assert scrub("Bram waits.") == "Bram waits."      # no carded subject
    assert reads.count("known") == 1, reads
