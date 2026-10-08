"""A page weighs what its beat weighed.

The narrator card's length clauses, both packs, from the Brackwater run (chat 166,
2026-10-07, 30 kept beats):

* PAGE LENGTH. Narration length against what happened on the beat (NPC acts
  plus lines) correlated at r = 0.02; quiet beats ran a median 833 narration
  characters against 1,012 on dramatic ones that carried several times the
  events. SCENE CRAFT said "Cutting REALLOCATES, it does not shrink" -- a
  length floor, added in 13ab1c76 so that cutting the view would hand its
  words to the beat's consequences instead of leaving a thin turn -- and
  PROSE CRAFT asked for "one sentence per beat that hits hard and ends
  early" (38 sentences of four words or fewer on 18 pages). The card now
  states the class: what happened sets the length, a quiet beat is a short
  page, and the 13ab1c76 case survives -- what a cut frees still goes to the
  consequences and to licensed sensation, as far as the beat has them.

A VOICE section was built beside these and withheld. It named
`private_voice_setting` and `register` as the voice the page is written in,
never a licence, because 15 of 30 kept traces cited the voice setting, one as
"Licensed by the private_voice_setting". On the same six captured requests the
new-card traces consulted the setting MORE (11 mentions against 4), and one
slip confirmed a claim on the strength of "Tamsin's dry voice" (turn 4611):
naming the field pulled the model toward it.

Not a restraint on glosses: a "never gloss a sign" clause was A/B-tested on
the same run and did not take (the readings arrive in the delivered record,
which is where that fix belongs).

Measured after, on six captured requests from that run (24 calls, one
upstream for every arm): page length did not move -- quiet-beat medians of
181.5 words on the old card against 201.5 on the new one (which then still
carried the VOICE section above), six samples each --
and every delivered line was placed exactly once in every answer. So these
pins hold the card to a true statement; they do not claim it shortens a page.
What sets a page's length is upstream of the card, like the glosses.
"""

import pytest

from llm.prompts import get_prompt_body, narrator_prompt

PACKS = ("en", "ja")

#: Each pack's spelling of the page-length class, and of the two clauses it
#: replaced. A pin, not a word list: the test reads the card, not prose.
PAGE_CLASS = {"en": "A PAGE WEIGHS WHAT ITS BEAT WEIGHED",
              "ja": "ページの重さは節の重さです"}
RETIRED = {"en": ("Cutting REALLOCATES", "does not shrink", "hits hard and ends early"),
           "ja": ("削減は再配分であり縮小ではありません", "一文を強く打ち", "早く終わらせて")}
THIRTEEN_AB1C76 = {"en": "what the cut frees goes to the beat's consequences and to licensed sensation",
                   "ja": "その結果と上記の感覚チャネルの許可された感覚に使い"}


@pytest.mark.parametrize("language", PACKS)
def test_a_page_weighs_what_its_beat_weighed_in_both_packs(language):
    sheet = narrator_prompt({"past_narration", "current_events"}, language)
    assert PAGE_CLASS[language] in sheet
    for retired in RETIRED[language]:
        assert retired not in get_prompt_body("narrator", language), retired


@pytest.mark.parametrize("language", PACKS)
def test_what_a_cut_frees_still_goes_to_the_consequences(language):
    """The case 13ab1c76 wrote the length floor for is kept: cutting the view
    is not the whole job, the freed words have somewhere to go."""
    sheet = narrator_prompt({"past_narration", "current_events"}, language)
    assert THIRTEEN_AB1C76[language] in sheet
