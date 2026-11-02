"""The institution's blame register is its books, never a head.

`scene_ledger` put `politics.blame[key]` -- the count `attribute_blame`
writes from the watch the charter BELIEVED it had arranged -- into every
presence slice as `blamed`, and `presence_view` hands that slice to the
background voice. A gate guard blamed twice in the books and never told was
voiced with `"blamed": 2, "knows_it_is_blamed": []` (audit
world_charter_behaviours F1). `heard_blame` is the channel; the count is
not."""
from world.charter import normalize_charter
from world.charter_log import scene_ledger


def _charter():
    c = normalize_charter({
        "key": "gate", "upkeeps": {}, "posts": {},
        "bodies": {"tam": {"place": "yard", "name": "Tam"},
                   "ivo": {"place": "yard", "name": "Ivo"}}})
    c["politics"] = dict(c.get("politics") or {}, blame={"tam": 2})
    return c


def test_a_body_blamed_in_the_books_and_never_told_carries_no_count():
    presence = scene_ledger(_charter(), "yard")["presences"]["tam"]
    assert "blamed" not in presence
    assert presence["knows_it_is_blamed"] == []
    assert 2 not in [v for v in presence.values() if isinstance(v, int)
                     and not isinstance(v, bool)]


def test_blame_said_aloud_still_reaches_the_body_it_landed_on():
    charter = _charter()
    charter["heard_blame"] = {"tam": ["ivo"]}
    presence = scene_ledger(charter, "yard")["presences"]["tam"]
    assert presence["knows_it_is_blamed"] == ["ivo"]
    assert "blamed" not in presence
