"""Social address admission must preserve a specialist's causal batch order."""

from agents.director import (
    _unfulfilled_completion_requests,
    _granted_event_ids, _specialist_span_slice, _specialist_ledger,
)


def test_addressed_speech_and_reply_precede_later_explicit_social_work():
    view = {"addressed_figures": ["Barkeep"], "spans": [
        {"chrono_id": 1, "event_id": 1, "type": "speech", "actor": "Mara",
         "targets": ["Barkeep"], "categories": ["speech"],
         "event": "Bring water, please."},
        {"chrono_id": 2, "event_id": 2, "type": "action", "actor": "Barkeep",
         "categories": ["inventory_ops"], "event": "puts water on the counter"},
        {"chrono_id": 3, "event_id": 3, "type": "action", "actor": "Mara",
         "categories": ["world_facts"], "event": "names the new room"},
        {"chrono_id": 4, "event_id": 4, "type": "speech", "actor": "Mara",
         "targets": ["Another patron"], "categories": ["speech"],
         "event": "Is that yours?"},
        {"chrono_id": 5, "event_id": 5, "type": "speech", "actor": "Mara",
         "targets": ["Barkeep"], "categories": ["speech", "public_evidence"],
         "event": "Thank you."},
    ]}
    rows = _specialist_span_slice("social", view)
    assert [row["chrono_id"] for row in rows] == [1, 2, 3, 5]
    assert _granted_event_ids("social", view) == [1, 2, 3, 5]
    assert rows[-1] is view["spans"][-1]  # One answer, even when both rules admit it.


def test_legacy_social_rows_without_chrono_keep_their_original_order():
    view = {"addressed_figures": ["Barkeep"], "spans": [
        {"type": "speech", "targets": ["Barkeep"], "categories": ["speech"]},
        {"type": "action", "categories": ["world_facts"]},
    ]}
    assert _specialist_span_slice("social", view) == view["spans"]


def test_public_ledger_keeps_source_citation_but_hides_all_correlation_numbers():
    visible = _specialist_ledger({
        "chrono_id": 3, "event_id": 3, "item_id": 7, "item_ids": [7],
        "item_names": ["Cup"], "_items": [{"id": 7, "name": "Cup"}],
        "source_event_id": "turn:1:raw", "event": "sets down the cup",
    })
    assert visible == {"item_names": ["Cup"], "source_event_id": "turn:1:raw",
                       "event": "sets down the cup"}


def test_already_true_station_does_not_acquit_a_pose_the_hand_was_never_asked_for():
    span = {"chrono_id": 2, "event_id": 2, "item_id": 7,
            "item_ids": [7], "item_names": ["Mara"], "categories": ["stations"]}
    request = {"span": span, "chrono_id": 2, "from": "objects", "to": "spatial",
               "channels": ["poses"], "full_scope": False}
    state = {"run": True, "ran": True, "scope": ["stations"], "event_ids": [2],
             "ledger_items": [span], "results": [{"status": "already_true"}],
             "events_resolved": [{"event_id": 2, "status": "already_true"}]}
    missing = _unfulfilled_completion_requests([request], {"spatial": state}, [])
    assert len(missing) == 1
    assert missing[0]["chrono_id"] == 2
    assert missing[0]["channels"] == ["poses"]
    assert missing[0]["to"] == "spatial"

    state["scope"] = ["stations", "poses"]
    state["ledger_items"] = [{**span, "categories": ["stations", "poses"]}]
    assert not _unfulfilled_completion_requests([request], {"spatial": state}, [])
