"""D12 (review 2026-09-07): the person governs reference, never focalization.

Rule 4 of the narrator sheet grants the page the player's OWN feeling --
"colouring what they sense or feel is ordinary craft, not a trespass" -- and
granted it in the second person only: "second person is written from inside
their skin". Measured in the descent run: 101 first-person beats rendered
exterior-only, while `player_declared.private_thought` and
`sensory_channels.interoception` sat in the payload with nothing telling the
writer they were usable there.

The fix is one sentence appended to rule 4, in both packs, stating the class:
`narration_person` decides what the player character is CALLED and nothing
else, so the focalization is theirs in all three persons. The two data halves
were already in the payload and are pinned here too, because a clause about a
field that stopped being delivered is a clause about nothing.
"""

from __future__ import annotations

import pytest

from language_runtime import raw_card


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_the_sheet_separates_reference_from_focalization(lang):
    text = raw_card(lang)["prompts"]["narrator"]
    if lang == "en":
        assert "never focalization" in text
        assert "narration_person governs REFERENCE" in text
        # The player's own idiom on the page is the point of the item, and
        # the sentence must not read as a second-person licence again.
        assert "in first and third exactly as in second" in text
    else:
        assert "焦点化" in text and "narration_person" in text
        assert "一人称でも三人称でも" in text


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_rule_four_still_says_what_it_always_said(lang):
    """A clause is an addition, not a rewrite: the interior of ANOTHER mind
    is still out of reach, and the licence is still proportionate."""
    text = raw_card(lang)["prompts"]["narrator"]
    if lang == "en":
        assert "DECIDE FOR NO ONE" in text
        assert "never a feeling that decides something for them." in text
    else:
        assert "誰の代わりにも決めないこと" in text
        assert "感情によって何かを決めてしまわないこと" in text


def test_the_two_fields_the_clause_points_at_are_real():
    """`private_thought` and the interoception channel are the payload halves
    the sentence licenses; neither is invented by this item."""
    import inspect

    from agents import narration
    from agents.composer import CHANNELS

    assert "interoception" in CHANNELS
    assert '"private_thought": interpreted.get("private_thought")' in \
        inspect.getsource(narration._narrator_player_declared)
