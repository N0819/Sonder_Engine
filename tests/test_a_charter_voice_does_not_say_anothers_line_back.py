"""A charter voice may not say another speaker's sentence back as its own.

Scratch play 2026-09-14, chat 9 turn 1: the master of ceremonies answered the
captain's "You have the best post in the room for judging it, ma'am" by
saying it again, verbatim, as his own line, and the page had a footman
parrot the captain. The prompt says never speak for anyone else present;
`_own_words_only` is the floor under it, exact on purpose: a paraphrase is
the voice's own words and the prompt's to judge, a copy is not speech.
"""

from agents.director import _fold_line, _own_words_only, _player_lines_this_beat


LINE = "You have the best post in the room for judging it, ma'am — though I fancy the room is judging you back tonight."


def test_a_copied_line_is_dropped_and_the_action_stands():
    decl = {"name": "Mr Pellew", "sequence": [
        {"type": "speech", "text": LINE},
        {"type": "action", "attempt": "permits himself a bow"}],
        "dialogue_log_entry": {"speaker": "Mr Pellew", "exact_quote": f'"{LINE}"'}}
    out, echoed = _own_words_only(decl, {_fold_line(f'"{LINE}"')})
    assert echoed == LINE
    assert [e["type"] for e in out["sequence"]] == ["action"]
    assert out["dialogue_log_entry"] is None


def test_the_voices_own_words_pass():
    decl = {"name": "Mr Pellew", "sequence": [{"type": "speech", "text": "Quite so, ma'am."}]}
    out, echoed = _own_words_only(decl, {_fold_line(LINE)})
    assert echoed == "" and out is decl


def test_the_players_line_counts_as_said():
    interp = {"speech": "Captain Hale. You are very prompt.", "sequence": [
        {"type": "speech", "text": "Captain Hale. You are very prompt."}]}
    assert _player_lines_this_beat(interp) == ["Captain Hale. You are very prompt."] * 2
    assert _fold_line('"Captain Hale. You are very prompt."') == "captain hale you are very prompt"
