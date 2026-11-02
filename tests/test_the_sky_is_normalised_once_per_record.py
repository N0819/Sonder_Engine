"""The scene's sky is normalised once per distinct record, not once per ask.

world_offscreen_time E1 (audit 2026-11-01): `weather_for_room` re-ran
`normalize_weather` on every call -- 94 call sites, per observer x room x
channel per beat -- measured 10 us for a record in the engine's own words
and 228 us for a story-named sky or synonym axis words (the A88 design's
intended case), because the fold and synonym loops ran every time. The
answer is a pure function of the record, so it is memoised on the record's
CONTENT: an edited record is a different key, and nothing an observer did
can reach it.
"""

from world import weather

STORY_SKY = {"sky": "ashfall over the pass", "precipitation": "grey ash",
             "intensity": "torrential", "wind": "gale-force",
             "temperature": "sub-zero"}


def _cold():
    memo = getattr(weather, "_SKY_RECORDS", None)
    if memo is not None:
        memo.clear()


def _scene(record):
    return {"rooms": {"yard": {"name": "Yard", "exposure": "open"}},
            "weather": record}


def _counting(monkeypatch):
    calls = []
    real = weather._fold_legacy

    def counting(value, field):
        calls.append(field)
        return real(value, field)

    monkeypatch.setattr(weather, "_fold_legacy", counting)
    return calls


def test_a_record_is_normalised_once_however_often_it_is_asked(monkeypatch):
    calls = _counting(monkeypatch)
    _cold()
    weather.normalize_weather(dict(STORY_SKY))
    one = len(calls)
    assert one > 0
    _cold()
    del calls[:]
    scene = _scene(dict(STORY_SKY))
    first = weather.weather_for_room(scene, "yard")
    for _ in range(25):
        assert weather.weather_for_room(scene, "yard") == first
    assert len(calls) == one


def test_the_memoised_answer_is_the_derivation_itself():
    for record in (dict(STORY_SKY), {"sky": "storm"}, "heavy rain, gale, cold",
                   {"sky": "clear", "electrical": True},
                   {"sky": "clear", "electrical": 1},
                   {"sky": "fair", "wind": {"speed": "high"}}):
        _cold()
        cold = weather.normalize_weather(record)
        warm = weather.normalize_weather(record)
        assert cold == warm


def test_an_edited_record_is_a_new_answer():
    _cold()
    record = dict(STORY_SKY)
    before = weather.normalize_weather(record)
    record["intensity"] = "light"
    after = weather.normalize_weather(record)
    assert before["intensity"] == "heavy" and after["intensity"] == "light"


def test_a_true_and_a_one_are_not_one_record():
    """`electrical: True` is a declaration; `electrical: 1` is not a bool
    and falls to the name's own axes. A key that folded the two together
    would hand one record the other's answer."""
    _cold()
    lit = weather.normalize_weather({"sky": "clear", "electrical": True})
    one = weather.normalize_weather({"sky": "clear", "electrical": 1})
    assert lit["electrical"] is True and one["electrical"] is False


def test_a_caller_editing_its_answer_cannot_edit_the_next_callers():
    _cold()
    first = weather.normalize_weather(dict(STORY_SKY))
    first["sky"] = "vandalised"
    assert weather.normalize_weather(dict(STORY_SKY))["sky"] == \
        "ashfall over the pass"


def test_a_written_over_sky_is_never_served_from_the_memo():
    _cold()
    base = {"sky": "storm", "intensity": "heavy", "precipitation": "rain"}
    weather.normalize_weather({"wind": "gale"})
    over = weather.normalize_weather({"wind": "gale"}, base=base)
    assert over["precipitation"] == "rain" and over["intensity"] == "heavy"
