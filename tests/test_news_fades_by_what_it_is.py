"""Some things never fade; basic things fade, slowly.

Owner's ruling (2026-09-14). One rate had a firsthand claim gone in 66
hours and a told one in 30, so word said in a taproom at dusk was out of
every head by the next evening.
"""
from world.charter_mind import PERSONAL_FLOOR
from world.charter_news import (NEWS_DECAY_BASIC_PER_HOUR, NEWS_DECAY_PER_HOUR,
                                NEWS_NEVER_FADES, decay_news, news_decay_rate)


def _minds(kind, strength=1.0):
    return {"tam": {"n": {"kind": "news", "event_kind": kind,
                          "strength": strength}}}


def test_a_sighting_and_a_body_found_never_fade():
    for kind in ("sighting", "body_recovered", "incident"):
        assert kind in NEWS_NEVER_FADES
        minds = decay_news(_minds(kind, 0.5), 24.0 * 365)
        assert minds["tam"]["n"]["strength"] == 0.5


def test_a_grievance_is_kept_for_months_and_then_cools():
    from world.charter_news import NEWS_DECAY_GRIEVANCE_PER_HOUR
    assert (1.0 - PERSONAL_FLOOR) / NEWS_DECAY_GRIEVANCE_PER_HOUR > 24 * 60
    minds = decay_news(_minds("harm_done"), 24.0 * 30)
    assert "n" in minds["tam"]
    minds = decay_news(_minds("harm_done"), 24.0 * 365)
    assert "n" not in minds["tam"]


def test_what_somebody_said_lasts_weeks_not_a_day():
    firsthand = (1.0 - PERSONAL_FLOOR) / NEWS_DECAY_PER_HOUR
    told = (0.5 - PERSONAL_FLOOR) / NEWS_DECAY_PER_HOUR
    assert firsthand > 24 * 14 and told > 24 * 7
    minds = decay_news(_minds("figure_speech", 0.5), 24.0 * 3)
    assert "n" in minds["tam"]
    minds = decay_news(_minds("figure_speech", 0.5), 24.0 * 30)
    assert "n" not in minds["tam"]


def test_the_road_being_out_fades_faster_but_still_in_days():
    assert news_decay_rate({"event_kind": "stock_low"}) == NEWS_DECAY_BASIC_PER_HOUR
    assert NEWS_DECAY_BASIC_PER_HOUR > NEWS_DECAY_PER_HOUR
    minds = decay_news(_minds("stock_low"), 24.0 * 2)
    assert "n" in minds["tam"]
    minds = decay_news(_minds("stock_low"), 24.0 * 10)
    assert "n" not in minds["tam"]


def test_a_kind_nobody_named_fades_at_the_slow_rate():
    assert news_decay_rate({"event_kind": "consequence"}) == NEWS_DECAY_PER_HOUR
    assert news_decay_rate({}) == NEWS_DECAY_PER_HOUR
