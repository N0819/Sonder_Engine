"""A quoted line is lifted out of an act row only where the row QUOTES it,
and never said twice.

`director_evidence.restore_declared_quotes` lifts a line the player quoted
out of an act row that swallowed it. Its first stage judged "already said"
by EXACT body equality and "in the row" by a bare SUBSTRING, while the stage
below it judges by word share (`QUOTED_LINE_CARRIED`, whose comment promises
a re-punctuated line "is never said twice"). Executed on the real function
(review 2026-11-01, director floors F5):

  1. `"Hi" she calls, and hits the brass chime twice.` -- the line said
     twice, and the act cut to "ts the brass chime twice" (the "hi" of
     "hits");
  2. `"Wait here," she says, and walks to the door.` -- "Wait here." and
     "Wait here," both delivered: every hearer heard her line twice;
  3. Japanese -- the act left as `Hinamiは「 」と言って扉を開けた`, the
     residual strip knowing only "/“”.
"""

from __future__ import annotations

from agents.director import restore_declared_quotes


def _row(event, categories, chrono=1, item=1):
    return {"chrono_id": chrono, "item_id": item, "event": event,
            "categories": list(categories), "source_event_id": "turn:1:primary:raw",
            "source_entity_id": "persona:1", "targets": []}


def _spoken(out):
    return [r["event"] for r in out["ledgers"] if "speech" in r["categories"]]


def _acts(out):
    return [r["event"] for r in out["ledgers"] if "speech" not in r["categories"]]


def test_a_word_inside_another_word_is_not_her_line():
    out = {"ledgers": [_row("Hi!", ["speech"]),
                       _row("hits the brass chime twice", ["contact_action_ops"], 2, 2)]}
    restore_declared_quotes(out, '"Hi" she calls, and hits the brass chime twice.')
    assert _spoken(out) == ["Hi!"]
    assert _acts(out) == ["hits the brass chime twice"]


def test_a_line_carried_with_other_punctuation_is_not_said_again():
    out = {"ledgers": [_row("Wait here.", ["speech"]),
                       _row('says "Wait here," and walks to the door',
                            ["positions"], 2, 2)]}
    restore_declared_quotes(out, '"Wait here," she says, and walks to the door.')
    assert _spoken(out) == ["Wait here."]


def test_a_japanese_line_leaves_no_empty_brackets_behind():
    out = {"ledgers": [_row("Hinamiは「行こう」と言って扉を開けた", ["rooms"])]}
    restore_declared_quotes(out, "「行こう」と言って扉を開ける。")
    assert _spoken(out) == ["行こう"]
    assert _acts(out) and not [a for a in _acts(out) if "「" in a or "」" in a], _acts(out)


def test_a_line_filed_as_an_act_is_still_lifted():
    """What the lift is for (the owner's chat 125): the line, quoted inside
    an act row and said by no speech row, becomes her line."""
    out = {"ledgers": [_row('calls out "Hello, is anyone here?" and looks around',
                            ["poses"])]}
    restore_declared_quotes(out, '"Hello, is anyone here?" I call out, looking around.')
    assert _spoken(out) == ["Hello, is anyone here?"]
    assert _acts(out) == ["calls out and looks around"]
