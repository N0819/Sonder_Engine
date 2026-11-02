"""`scene_ledger` normalizes each social store once per call, and a single
presence can be asked for alone.

It ran `judgment_view`, `commitment_view` and `decision_view` inside the
per-presence loop, each normalizing the WHOLE store again, and
`presence_view` built every presence of the room to keep one: measured
(audit world_charter_behaviours E1, 300 bodies, 60 in one room) 3.94 s per
call, one `normalize_judgments` 0.0585 s x 60. The slices are unchanged."""
from world import charter_log
from world.charter import normalize_charter
from world.charter_log import scene_ledger


def _room(people=12):
    bodies = {"b%02d" % i: {"place": "yard", "name": "Body %d" % i}
              for i in range(people)}
    charter = normalize_charter({"key": "yard_folk", "upkeeps": {},
                                 "posts": {}, "bodies": bodies})
    keys = sorted(bodies)
    charter["minds"] = {k: {o: {"body": o, "competence": {},
                                "believed_available": True, "strength": 0.9,
                                "as_of_hours": 0.0, "heard_from": None}
                            for o in keys if o != k} for k in keys}
    charter["judgments"] = {k: {o: {"trust": -0.3, "fear": 0.1,
                                    "reasons": [{"evidence_id": "e1",
                                                 "signal": "accusation"}]}
                                for o in keys[:4] if o != k} for k in keys}
    return charter


def test_each_store_is_normalized_once_per_call(monkeypatch):
    counts = {"judgments": 0, "commitments": 0, "decisions": 0}
    for name, store in (("normalize_judgments", "judgments"),
                        ("normalize_commitments", "commitments"),
                        ("normalize_decisions", "decisions")):
        real = getattr(charter_log, name)

        def counted(value, _real=real, _store=store):
            counts[_store] += 1
            return _real(value)

        monkeypatch.setattr(charter_log, name, counted)
    scene_ledger(_room(), "yard")
    assert counts == {"judgments": 1, "commitments": 1, "decisions": 1}


def test_one_presence_asked_alone_is_the_same_slice():
    charter = _room()
    whole = scene_ledger(charter, "yard")["presences"]["b03"]
    alone = scene_ledger(charter, "yard", only="b03")["presences"]
    assert list(alone) == ["b03"]
    assert alone["b03"] == whole
