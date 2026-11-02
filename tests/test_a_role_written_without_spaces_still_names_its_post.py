"""A role written in a script without spaces still names the post it names,
and a declaration written in one is still read for what it left uncovered.

Two readers in the Director's floors tokenised with ASCII classes
(`[^a-z0-9]+`, `[a-z0-9']+`), so every Japanese word read as nothing (review
2026-11-01, director floors F13 and F15):

  * `_figure_head_noun("門番") == ""`, and `_role_noun_matches("", {""})` is
    False even for identical roles: a mint of the gatekeeper beside the
    charter's posted gatekeeper never bound by role, and the beat kept a
    second, unsimulated gatekeeper -- the "phantom fourth innkeeper" the
    binder exists to prevent. A phrase with no spaces to find a head noun by
    is compared whole.
  * `_decl_tokens` read no token from a Japanese declaration, so every unit
    had fewer than two and the interpret-coverage detector never ran for a
    Japanese story. An unspaced script's words are its runs of kanji and
    katakana (hiragana runs are particles and inflection); a spaced script
    keeps exactly the rule it had.
"""

from __future__ import annotations

import re

from agents.director import (_bind_minted_entities_to_present_figures,
                             _decl_tokens, _figure_head_noun, _ling,
                             _role_noun_matches, _uncovered_declarations)
from language_runtime import language_scope


def test_an_unspaced_role_has_a_head_and_matches_itself():
    assert _figure_head_noun("門番") == "門番"
    assert _figure_head_noun("宿屋の主人") == "宿屋の主人"
    assert _role_noun_matches(_figure_head_noun("門番"), {_figure_head_noun("門番")})
    assert not _role_noun_matches(_figure_head_noun("門番"), {_figure_head_noun("宿屋の主人")})


def test_the_english_head_noun_rule_is_unchanged():
    assert _figure_head_noun("the reeve's clerk") == "clerk"
    assert _figure_head_noun("ford_innkeeper") == "innkeeper"
    assert _figure_head_noun("the innkeeper") == "innkeeper"
    assert _figure_head_noun("Guard 2") == "guard"


def test_a_japanese_mint_binds_to_the_post_by_its_role():
    sd = {"entities": {"monban": {"name": "門番", "kind": "person"}},
          "positions": {"monban": "gate"}}
    figures = [{"name": "Tanaka Jiro", "role": "門番", "posts": ["gate_watch"],
                "room": "gate", "charter": "town", "body": "g1"}]
    bound = _bind_minted_entities_to_present_figures({"entities": {}}, sd, figures)
    assert [(b["bound_to"], b["by"]) for b in bound] == [("Tanaka Jiro", "role")]


def _old_decl_tokens(text):
    """The rule this replaced, for spaced-script parity."""
    tokens = set()
    for tok in re.findall(r"[a-z0-9']+", str(text or "").casefold()):
        tok = tok.strip("'")
        if len(tok) >= 3 and tok not in _ling("_DECL_STOPWORDS"):
            tokens.add(tok)
    return tokens


def test_english_declaration_tokens_are_what_they_were():
    for text in ("I'm going to grab the lantern and head down the cellar stairs.",
                 "She doesn't answer; I wait by the 3rd door, then knock twice.",
                 "'Tis the dogs' bowls -- I kick them over."):
        assert _decl_tokens(text) == _old_decl_tokens(text), text


def test_a_japanese_declaration_has_content_tokens():
    with language_scope("ja"):
        tokens = _decl_tokens("ランタンを持って地下室の階段を下りる")
    assert {"ランタン", "地下室", "階段"} <= tokens, tokens


def test_a_japanese_clause_no_row_covers_is_found():
    with language_scope("ja"):
        out = {"sequence": [{"type": "action", "attempt": "ランタンを持つ"}],
               "flow": {}}
        uncovered = _uncovered_declarations(
            "ランタンを持って、そして地下室の階段を下りて扉を叩く。", out)
    assert uncovered and "地下室" in uncovered[0], uncovered
