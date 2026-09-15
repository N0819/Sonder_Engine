"""An addressee the spans name is an addressee, and a line aimed at an
unregistered figure addresses the social hand.

Scratch play 2026-09-14, chat 9 turns 2-3: the author wrote every line of the
errand with `targets: ["Mr Pellew"]` and left `flow.addressed_to` empty, so
the master of ceremonies ranked as nobody's addressee, the reactor list held
the captain alone, no hand was addressed for what the figure would do with
the message, and the errand "did not leave the room by his legs".
"""

from agents.director import _address_from_spans
from agents.director import _ruling_for, addressed_figures


CAST = [{"id": 11, "name": "Captain Edmund Hale"}]
FIGURES = ["Mr Pellew", "Mrs Dacre"]


def _out(targets, addressed=None):
    return {"flow": {"addressed_to": list(addressed or []),
                     "addressed_to_refs": list(addressed or [])},
            "sequence": [{"type": "speech", "text": "Would you send a man?",
                          "targets": targets},
                         {"type": "action", "attempt": "steps nearer",
                          "targets": ["Mr Pellew"]}]}


def test_a_figure_named_by_a_speech_span_is_addressed_by_name():
    out = _out(["Mr Pellew", "card_room", "Josiah Crane"])
    _address_from_spans(out, FIGURES, CAST)
    assert out["flow"]["addressed_to"] == []
    assert out["flow"]["addressed_to_refs"] == ["Mr Pellew"]


def test_a_cast_member_named_by_id_or_name_is_addressed_by_id():
    out = _out(["character:11", "Mr Pellew"])
    _address_from_spans(out, FIGURES, CAST)
    assert out["flow"]["addressed_to"] == [11]
    assert out["flow"]["addressed_to_refs"] == [11, "Mr Pellew"]
    out = _out(["Captain Edmund Hale"])
    _address_from_spans(out, FIGURES, CAST)
    assert out["flow"]["addressed_to"] == [11]


def test_a_filled_list_stands_and_an_action_target_is_not_an_address():
    out = _out(["Mr Pellew"], addressed=[11])
    _address_from_spans(out, FIGURES, CAST)
    assert out["flow"]["addressed_to_refs"] == [11]
    out = {"flow": {"addressed_to": [], "addressed_to_refs": []},
           "sequence": [{"type": "action", "attempt": "bows", "targets": ["Mr Pellew"]}]}
    _address_from_spans(out, FIGURES, CAST)
    assert out["flow"]["addressed_to_refs"] == []


def test_an_addressed_figure_addresses_the_social_hand_and_no_other():
    interp = {"flow": {"addressed_to": [], "addressed_to_refs": ["Mr Pellew"]}}
    assert addressed_figures(interp) == ["Mr Pellew"]
    assert addressed_figures({"flow": {"addressed_to_refs": [11]}}) == []
    view = {"ledger_notes": {}, "manifest": [], "spans": [],
            "addressed_figures": ["Mr Pellew"]}
    assert "addressee" in _ruling_for("social", view)[0]
    assert _ruling_for("spatial", view)[0] == []
    assert _ruling_for("social", {**view, "addressed_figures": []})[0] == []


def test_the_line_aimed_at_a_figure_is_the_social_hands_work_item():
    from agents.director import _specialist_span_slice
    view = {"spans": [
        {"type": "speech", "categories": ["speech"], "targets": ["Mr Pellew"],
         "event_id": 1, "text": "Your man, if you please."},
        {"type": "action", "categories": ["stations"], "targets": ["Mr Pellew"],
         "event_id": 2, "attempt": "steps nearer"},
        {"type": "speech", "categories": ["speech"], "targets": ["character:11"],
         "event_id": 3, "text": "You are very kind, Captain."}],
        "addressed_figures": ["Mr Pellew"]}
    assert [i["event_id"] for i in _specialist_span_slice("social", view)] == [1]
    assert _specialist_span_slice("social", {**view, "addressed_figures": []}) == []
    assert [i["event_id"] for i in _specialist_span_slice("spatial", view)] == [2]


def test_the_figures_own_answer_is_the_social_hands_row_at_resolve():
    from agents.director import _specialist_span_slice
    view = {"spans": [
        {"type": "action", "actor": "character:11", "categories": ["poses"], "targets": ["Josiah Crane"], "event_id": 1},
        {"type": "speech", "actor": "Mr Pellew", "categories": ["speech"], "targets": ["Clara Penrose"], "event_id": 2},
        {"type": "action", "actor": "Mr Pellew", "categories": ["poses"], "targets": [], "event_id": 3}],
        "addressed_figures": ["Mr Pellew"]}
    assert [i["event_id"] for i in _specialist_span_slice("social", view)] == [2, 3]
