"""Authored post hierarchy routes information without granting omniscience."""

from world.charter import normalize_charter, report_to_superiors


def _charter(*, together=True):
    state = normalize_charter({
        "key": "watch",
        "posts": {
            "gate_watch": {"place": "gate", "serves": [],
                           "reports_to": "watch_captain"},
            "watch_captain": {"place": "gate", "serves": []},
        },
        "bodies": {
            "guard": {"name": "Iven Marr", "place": "gate"},
            "captain": {"name": "Ysra Vale",
                        "place": "gate" if together else "office"},
        },
        "watch": {"gate_watch": "guard", "watch_captain": "captain"},
    })
    state["minds"] = {
        "guard": {
            "report:road": {
                "kind": "news", "body": "report:road",
                "event_kind": "claim", "about": "the east road",
                "claim_text": "the east road is washed out", "place": "gate",
                "happened_at": 1.0, "strength": 1.0, "as_of_hours": 1.0,
                "heard_from": None, "provenance": "witnessed_surface",
            },
            "captain": {"body": "captain", "believed_available": False,
                        "strength": 1.0, "as_of_hours": 1.0},
        },
    }
    return state


def test_staffed_colocated_reporting_line_briefs_the_superior():
    state = _charter()
    minds, told = report_to_superiors(
        state["minds"], state["watch"], state["posts"], state["bodies"],
        naming=state["naming"], at_hours=2.0)

    claim = minds["captain"]["report:road"]
    assert told == 1
    # The subordinate's KEY, the vocabulary every reader of `heard_from`
    # keys by; this pinned the display name, which filed a refuted report's
    # stance on a subject that is no body (audit world_charter_behaviours F9,
    # 2026-11-01). The name is rendered where a voice reads the claim.
    assert claim["heard_from"] == "guard"
    assert claim["provenance"] == "reported"
    assert claim["source_provenance"] == "witnessed_surface"
    assert claim["retellings"] == 1
    assert "captain" not in minds["captain"]  # no private personnel belief


def test_reporting_line_does_not_cross_rooms():
    state = _charter(together=False)
    minds, told = report_to_superiors(
        state["minds"], state["watch"], state["posts"], state["bodies"])
    assert told == 0
    assert "report:road" not in minds.get("captain", {})


def test_reports_to_survives_normalization():
    assert _charter()["posts"]["gate_watch"]["reports_to"] == "watch_captain"


def test_an_exhausted_rumour_is_not_reported_forever():
    from world.degradation import EXHAUSTED_HOPS

    state = _charter()
    state["minds"]["guard"]["report:road"]["retellings"] = EXHAUSTED_HOPS - 1
    minds, told = report_to_superiors(
        state["minds"], state["watch"], state["posts"], state["bodies"])
    assert told == 0
    assert "report:road" not in minds.get("captain", {})
