"""A line whose words did not carry is never filed as said TO the listener.

`observations_from_render` projects each rendered span into the evidence row
the character payload and the narrator packet carry, and it copied
`directed_at_self` off the percept. `speech_percept` and
`communication_percept` set that flag from the line's addressee at EVERY
fidelity, so a guard telling the prisoner "Tomorrow you hang." through a door
rendered `A voice — the words do not carry.` -- the sentence the cook gets for
the same line -- and the prisoner's row alone said `"directed_at_self": true`
(audit agents_composer F1, 2026-11-01). The second representation carried a
fact the page could not.

The rule: below `full`, the only self-directed fact a page carries is the
listener's own name caught in the line ("You catch your name in it."), and the
flag says exactly that and nothing about whom the line was addressed to.
"""

from agents import composer
from tests.helpers import patch_seam


GUARD = "Corlan Vey"
PRISONER = "Ilsa Marrow"
COOK = "Tam Bracken"
REL = {"tier": "near", "barrier": "door", "same_room": False}


def _rows(percept):
    view = composer.render_view([percept], mode="character", language="en")
    rows = composer.observations_from_render("7", view)
    for row in rows:
        row.pop("observation_id", None)
    return view.text, rows


def _hear(monkeypatch, level, *, voice=True):
    patch_seam(monkeypatch, "agents.composer_speech", "line_hear_level",
               lambda *a, **k: level)
    patch_seam(monkeypatch, "agents.composer_speech", "voice_carries",
               lambda *a, **k: voice)


def _line(target, text="Tomorrow you hang."):
    return {"speaker": GUARD, "text": text, "volume": "normal",
            "intended_target": target}


def _pair(monkeypatch, level, *, voice=True, can_see=False,
          proximity="near", rel=REL, **kw):
    _hear(monkeypatch, level, voice=voice)
    out = []
    for target in (PRISONER, COOK):
        p = composer.speech_percept(_line(target, **kw), rel, PRISONER,
                                    display="the gaoler", can_see=can_see,
                                    proximity=proximity)
        assert p is not None
        out.append(_rows(p))
    return out


def test_a_voice_without_its_words_is_the_same_row_whoever_it_was_said_to(
        monkeypatch):
    (text_a, rows_a), (text_b, rows_b) = _pair(monkeypatch, "none")
    assert text_a == text_b
    assert rows_a == rows_b, (
        "the observation told the listener a line it could not hear was "
        f"said to it: {rows_a} vs {rows_b}")
    assert not any(r.get("directed_at_self") for r in rows_a)


def test_a_line_heard_in_pieces_is_the_same_row_whoever_it_was_said_to(
        monkeypatch):
    (text_a, rows_a), (text_b, rows_b) = _pair(monkeypatch, "fragment")
    assert text_a == text_b
    assert rows_a == rows_b
    assert not any(r.get("directed_at_self") for r in rows_a)


def test_a_line_seen_spoken_and_unheard_is_the_same_row_whoever_it_was_said_to(
        monkeypatch):
    rel = {"tier": "within_reach", "barrier": "open", "same_room": True}
    (text_a, rows_a), (text_b, rows_b) = _pair(
        monkeypatch, "none", voice=False, can_see=True,
        proximity="within_reach", rel=rel)
    assert "cannot make out" in text_a
    assert rows_a == rows_b
    assert not any(r.get("directed_at_self") for r in rows_a)


def test_a_communication_heard_in_pieces_is_the_same_row_whoever_it_was_to(
        monkeypatch):
    _hear(monkeypatch, "fragment")
    out = []
    for target in (PRISONER, COOK):
        entry = {"speaker": GUARD, "type": "communication",
                 "act": "warns", "content": "the tide is turning",
                 "targets": [target], "volume": "normal"}
        p = composer.communication_percept(entry, REL, PRISONER,
                                           display="the gaoler",
                                           can_see=False, proximity="near")
        assert p is not None and p.fidelity == "fragment"
        out.append(_rows(p))
    assert out[0] == out[1]
    assert not any(r.get("directed_at_self") for r in out[0][1])


def test_a_whole_line_still_tells_its_addressee_it_was_said_to_them(
        monkeypatch):
    """The subtraction is the unheard case only: at `full` the listener has
    every word, and the addressee keeps the flag."""
    (_, rows_a), (_, rows_b) = _pair(monkeypatch, "full")
    assert [r.get("directed_at_self") for r in rows_a] == [True]
    assert [r.get("directed_at_self") for r in rows_b] == [None]


def test_a_name_caught_in_a_voice_is_the_one_self_directed_fact(monkeypatch):
    """`own_name` is the bit the page DOES say ("You catch your name in
    it."), so the row may say the line concerned the listener -- the same
    row whoever the line was addressed to."""
    _hear(monkeypatch, "none")
    out = []
    for target in (PRISONER, COOK):
        p = composer.speech_percept(
            _line(target, text="Ilsa Marrow hangs tomorrow."), REL, PRISONER,
            display="the gaoler", can_see=False, proximity="near",
            name_forms=["Ilsa Marrow", "Ilsa"])
        assert p is not None and p.data.get("own_name")
        out.append(_rows(p))
    assert out[0] == out[1]
    assert [r.get("directed_at_self") for r in out[0][1]] == [True]
