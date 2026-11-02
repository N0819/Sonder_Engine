"""Who still owes a mind something is named as that mind knows them.

`self.still_waiting_for` is read off the figure that owes the promise
(`commit_background.owed_to`), and each row's `from` is that figure's
canonical ledger name: nothing relabelled it on the way to the mind, so a
woman who asked a never-introduced hostler for an ale carried his full name
into every later call -- the exact story `tellers_as_known` was floored for
on `told_by` (playerless Aldermill round 8, 2026-09-23), with `from` left
open (review 2026-11-01, agents_character_background F2). The row also
carried `to`, the FIGURE's own label for the asker -- another mind's view of
her. `from` now passes the identity floor every named field passes; the
figure's private label stays off the wire; and the read-back's
`waiting_ops`, which name the promise as the mind was shown it, are mapped
back to the ledger name the commit closes it by.
"""

from __future__ import annotations

from copy import deepcopy

from agents import character
from tests.test_character_continuity import story  # noqa: F401 -- the fixture

HOSTLER = "Hostler Gidoton Barrelfielder"


def _ledger():
    return {"hostler": {
        "name": HOSTLER, "first_turn": 0, "last_turn": 0,
        "sketch": {"station_room": "hall",
                   "appearance": "a wiry man with a scarred chin"},
        "pending_act": {"what": "a small ale", "to": "the dark-haired woman",
                        "to_ref": "Mara", "turn": 0, "expires_turn": 9}}}


def _reply(changes=()):
    return {"want": "get the ale she was promised", "held_back": "shout for it",
            "hinge": "the hostler has not come back", "unsure": "whether he heard",
            "sequence": [{"do": "looks toward the bar"}],
            "demeanor": "patient", "tells": [], "notebook": [],
            "changes": list(changes), "note": "waiting on an ale"}


def _run(story, monkeypatch, temp_db, script=(), changes=(), known=None):
    from llm import decisions
    from tests.test_character_bare import _answer
    char_id, context, _commit = story
    ctx = context(None, 1)
    temp_db.wset(ctx.chat.id, "background_presences", _ledger())
    if known is not None:
        temp_db.wset(ctx.chat.id, "known", known)
    sent = []

    def model(role, step_key, system, payload, **kwargs):
        sent.append(deepcopy(payload))
        return deepcopy(_reply(changes))

    monkeypatch.setattr(decisions, "OVERRIDE",
                        lambda state, questions: _answer(list(script))(questions))
    monkeypatch.setattr(character, "_agent_json", model)
    return character.character_step(ctx, char_id, 1), sent


def test_the_figure_that_owes_her_is_named_as_she_knows_him(temp_db, story, monkeypatch):
    _result, sent = _run(story, monkeypatch, temp_db)
    rows = sent[0]["self"]["still_waiting_for"]
    assert rows and rows[0]["what"] == "a small ale"
    shown = rows[0]["from"]
    assert shown and "Gidoton" not in shown and "Barrelfielder" not in shown
    # The figure's own label for her is the figure's view, not hers.
    assert "to" not in rows[0] and "to_ref" not in rows[0]


def test_giving_up_on_it_still_closes_the_figures_row(temp_db, story, monkeypatch):
    result, _sent = _run(
        story, monkeypatch, temp_db,
        script=[("change:0:kind", "stop_waiting"), ("change:0:promise", "w0")],
        changes=["I have waited long enough for that ale."])
    ops = result.get("waiting_ops") or []
    assert ops and ops[0]["from"] == HOSTLER and ops[0]["what"] == "a small ale"


def test_a_known_figure_keeps_his_name(temp_db, story, monkeypatch):
    _result, sent = _run(story, monkeypatch, temp_db, known={"Mara": [HOSTLER]})
    assert sent[0]["self"]["still_waiting_for"][0]["from"] == HOSTLER
