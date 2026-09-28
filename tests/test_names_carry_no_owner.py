"""A name says what a thing or a place is, never whose it is (owner,
2026-09-28: "Perhaps we should inform prompts to not add ownership tags").

Found on a live replay of chat 154's departure: a pair of trousers minted as
"Gushiga Toriki's trousers" (chat 152 idx 12, by the retired causal
Director's mint-on-reference backstop) carried a fisherman's name into the
composed view of a mind that never learned it. The composer's identity
tripwire caught it -- the floor holds -- but the name was never the
trousers' to carry: who wears, holds or owns a thing has records of its own.
Every surface that names something new says so, in every pack.
"""

from __future__ import annotations

import pytest

from llm import prompts

#: What each pack's sentence says, in its own words.
RULE = {"en": "never whose it is", "ja": "誰のもの"}


@pytest.mark.parametrize("language", sorted(RULE))
def test_every_naming_surface_says_a_name_carries_no_owner(language):
    card = prompts._prompt_card(language)
    surfaces = {
        "the encoder, minting a thing": card["encoder"]["entities__new"],
        "the Director, naming a new place (interpret)": card["prose_contract"]["director_interpret"],
        "the Director, naming a new place (resolve)": card["prose_contract"]["director_resolve"],
        "the room author, naming a fixture": card["prose_contract"]["room_author"],
    }
    missing = [where for where, text in surfaces.items()
               if RULE[language].casefold() not in str(text).casefold()]
    assert not missing, f"{language}: no naming rule at {missing}"
