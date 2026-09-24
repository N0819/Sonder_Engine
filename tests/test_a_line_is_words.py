"""A spoken element whose `text` holds elements is those elements.

The owner's chat 137 idx 46 (2026-09-23, GLM 5.2): the character wrote each
of Mirelle's lines as an element nested inside its own `text`; `str()` of
it was fused with the next line into two Python reprs, and the page read
`"{'text': "There you are. ..."`. The words are lifted out at the one
normalizer every producer's sequence passes through.
"""
from agents.common import fuse_speech_run, norm_sequence, normalize_speech_volume


def _texts(out):
    return [e["text"] for e in out["sequence"] if e.get("type") == "speech"]


def test_a_line_nested_in_its_own_text_is_lifted_out():
    out = {"sequence": [
        {"type": "speech", "text": {
            "text": "There you are. Rest, little fox.", "tone": "low, warm",
            "volume": "soft", "visibility": "3", "conceal_from": []}},
        {"type": "speech", "text": {
            "text": "Mmm... you feel wonderful in there.", "tone": "drowsy",
            "volume": "soft", "visibility": "3", "conceal_from": []}},
    ]}
    warned = []
    norm_sequence(out, warn=warned.append)
    assert _texts(out) == ["There you are. Rest, little fox.",
                           "Mmm... you feel wonderful in there."]
    assert [e["tone"] for e in out["sequence"]] == ["low, warm", "drowsy"]
    assert {e["volume"] for e in out["sequence"]} == {normalize_speech_volume("soft")}
    assert out["speech"] == "There you are. Rest, little fox."
    assert any("lifted out" in w for w in warned)
    fuse_speech_run(out)
    assert _texts(out) == ["There you are. Rest, little fox. "
                           "Mmm... you feel wonderful in there."]


def test_a_list_of_lines_is_that_many_lines_and_the_outer_delivery_holds():
    out = {"sequence": [{"type": "speech", "volume": "loud", "text": [
        "Down here!", {"text": "Can you hear me?", "tone": "urgent"}]}]}
    norm_sequence(out)
    assert _texts(out) == ["Down here!", "Can you hear me?"]
    assert {e["volume"] for e in out["sequence"]} == {normalize_speech_volume("loud")}
    assert out["sequence"][1]["tone"] == "urgent"


def test_a_nested_element_with_no_words_is_dropped_and_said():
    out = {"sequence": [{"type": "speech", "text": {"tone": "warm"}},
                        {"type": "speech", "text": "Still here."}]}
    warned = []
    norm_sequence(out, warn=warned.append)
    assert _texts(out) == ["Still here."]
    assert any("no words were dropped" in w for w in warned)


def test_a_plain_line_is_untouched_and_nothing_is_said():
    out = {"sequence": [{"type": "speech", "text": "Two kicks and I open."}]}
    warned = []
    norm_sequence(out, warn=warned.append)
    assert _texts(out) == ["Two kicks and I open."]
    assert not any("lifted out" in w for w in warned)
