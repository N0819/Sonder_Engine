"""The narrator cannot paraphrase a line it never types.

`DIALOGUE FIDELITY` is already the strongest sentence in the narrator card --
"ABSOLUTE", "MUST appear verbatim, complete, and unaltered", "NEVER SUMMARISE
A SPOKEN LINE" -- and it names this exact failure in its own examples. On the
beat that prompted this it failed anyway, three times, with the dropped lines
handed back as correction notes each time. The prompt was never the variable.

Measured (`docs/experiments/NARRATOR_DIALOGUE_PLACEHOLDERS_2026-08-24.md`),
three arms over one beat: the shipped prompt kept 75% of delivered lines,
naming the speakers instead of labelling them by appearance kept 67% (naming
did not help, which killed the obvious hypothesis), and handing the model
numbered tokens to place kept 100%.

The residual failure changes character, which matters more than the
percentage. A paraphrase is undetectable except by substring search,
unrecoverable, and already past the reader. An omitted token is countable
before the prose is shown, and the engine knows exactly which line is missing.
"""

from __future__ import annotations

import json

import pytest

from agents.narration import (_dialogue_tokens, _substitute_dialogue_tokens)


VIEW = (
    'Picard says in a measured voice: "Proceed with the model, Lieutenant." '
    'Riker says in a level voice: "That could be a countdown, Captain." '
    'You say in a nervous voice: "Nothing in the catalogue matches."'
)


class TestWhichLinesBecomeTokens:
    def test_every_delivered_line(self):
        lines = _dialogue_tokens(VIEW, [])
        assert "Proceed with the model, Lieutenant." in lines
        assert "That could be a countdown, Captain." in lines

    def test_the_players_own_lines_are_excluded(self):
        """PLAYER ECHO RULE requires their ABSENCE. Handing them back as
        tokens to place would push the model to break one rule to keep the
        other -- the same contradiction the fidelity check already avoids."""
        lines = _dialogue_tokens(
            VIEW, ['"Nothing in the catalogue matches."'])
        assert "Nothing in the catalogue matches." not in lines
        assert len(lines) == 2

    def test_a_repeated_line_is_one_token(self):
        view = ('Picard says in a flat voice: "Understood." '
                'Riker says in a quiet voice: "Understood."')
        assert _dialogue_tokens(view, []) == ["Understood."]

    def test_an_attribution_never_becomes_a_line(self):
        """`_QUOTE_BODY_RE` requires four characters between the marks, so a
        line shorter than that is invisible -- and its two skipped marks then
        pair with their neighbours, matching the ATTRIBUTION between two short
        lines as though it were a quote. The fidelity check merely gets
        confused by that; handing it to the narrator as a line to place would
        print `Riker says in a quiet voice:` inside quotation marks."""
        view = ('Picard says in a flat voice: "No." '
                'Riker says in a quiet voice: "No."')
        assert _dialogue_tokens(view, []) == []

    def test_extraction_is_exact_on_the_real_view_format(self):
        """Verified against the live Enterprise run: turns with 8, 9 and 10
        logged NPC lines extracted exactly 8, 9 and 10 tokens. The composer's
        format is `<label> says in a <tone> voice: "<line>"`, and the
        attribution between two lines must not itself become a token."""
        view = ('Picard says in a measured voice: "Proceed, Lieutenant." '
                'Riker says in a level voice: "Aye, sir." '
                'Picard says in a quiet voice: "And the terminus?"')
        assert _dialogue_tokens(view, []) == [
            "Proceed, Lieutenant.", "Aye, sir.", "And the terminus?"]

    def test_a_view_with_no_dialogue_produces_none(self):
        assert _dialogue_tokens("The room is quiet. Nobody speaks.", []) == []


class TestSubstitution:
    def test_the_exact_words_land_where_the_token_was(self):
        prose, missing = _substitute_dialogue_tokens(
            "He nods once. {{L1}} She turns away. {{L2}}",
            ["Proceed, Lieutenant.", "Aye, sir."])
        assert prose == ('He nods once. "Proceed, Lieutenant." '
                         'She turns away. "Aye, sir."')
        assert missing == []

    def test_an_omitted_token_is_reported_with_its_line(self):
        """The residual failure mode, and the whole reason it is better than a
        paraphrase: the engine knows exactly which line is missing."""
        _prose, missing = _substitute_dialogue_tokens(
            "He nods once. {{L1}}", ["Proceed.", "And the terminus?"])
        assert missing == [(2, "And the terminus?")]

    def test_an_invented_index_is_stripped_rather_than_shown(self):
        """A token for a line that does not exist is the model inventing an
        index. `{{L9}}` must never reach the page."""
        prose, _missing = _substitute_dialogue_tokens(
            "He nods. {{L1}} Then {{L9}} nothing.", ["Proceed."])
        assert "{{L9}}" not in prose
        assert '"Proceed."' in prose

    def test_prose_without_tokens_is_untouched(self):
        prose, missing = _substitute_dialogue_tokens("Nobody spoke.", [])
        assert prose == "Nobody spoke."
        assert missing == []

    def test_a_line_carrying_quote_marks_is_not_double_quoted(self):
        prose, _ = _substitute_dialogue_tokens("{{L1}}", ["Aye, sir."])
        assert prose.count('"') == 2


class TestTheRuleReachedThePrompts:
    @pytest.mark.parametrize("lang", ["en", "ja"])
    def test_both_packs_carry_it(self, lang):
        """A pack without the rule hands the model tokens it was never told
        about, which is worse than not sending them at all."""
        card = json.load(open(
            f"language_packs/{lang}/cards/system_prompts.json",
            encoding="utf-8"))
        narrator = card["prompts"]["narrator"]
        assert "DIALOGUE PLACEHOLDERS" in narrator
        assert "{{L1}}" in narrator

    def test_it_says_it_overrides_the_retype_instruction(self):
        """DIALOGUE FIDELITY says to type the lines out; this says not to.
        A prompt carrying both without saying which wins is a contradiction
        the model resolves however it likes."""
        card = json.load(open(
            "language_packs/en/cards/system_prompts.json", encoding="utf-8"))
        narrator = card["prompts"]["narrator"]
        assert "OVERRIDES DIALOGUE FIDELITY" in narrator


class TestOrderingIsNoLongerEnforceable:
    """Measured over 17 live turns: 7 out-of-order findings, every one of them
    a single transposed line in an otherwise correct sequence -- and the
    retries they bought did not fix them. The finding stays on the record; it
    stops costing a call."""

    def test_it_is_not_in_the_enforceable_set(self):
        from language_runtime import english_linguistic

        prefixes = english_linguistic(
            "agents.narration", "_ENFORCEABLE_PREFIXES")
        assert not any(p.startswith("Dialogue rendered out of order")
                       for p in prefixes)

    def test_the_losses_that_matter_stay_enforceable(self):
        from language_runtime import english_linguistic

        prefixes = english_linguistic(
            "agents.narration", "_ENFORCEABLE_PREFIXES")
        assert "Dialogue from view missing or altered" in prefixes
        assert ("Narrator invented quoted dialogue absent from the player "
                "view") in prefixes
