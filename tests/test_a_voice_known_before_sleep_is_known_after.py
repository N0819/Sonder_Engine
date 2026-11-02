"""A voice once known stays known across a beat asleep, in every pack.

The standing ledger is replaced each beat (`perception`'s `"standing":
sorted(rendered.standing_keys)`), and a `voice:` key is the one family that
persists without being re-earned (`composer.carried_voices`: "A VOICE ONCE
KNOWN STAYS KNOWN ... Carried forward unconditionally"). The English
renderer's non-awake branch filed the residue's key alone, so after one beat
asleep every known speaker's next line was a first hearing that re-declared
their register; the Japanese renderer carried the voices (audit
agents_composer F8, 2026-11-01: EN asleep keeps the voice False, EN woken
True, JA asleep True). The two renderers now agree.
"""

import pytest

from agents import composer

VOICE = composer.VOICE_KEY_PREFIX + "abc123:def456"


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("level", ["asleep", "unconscious"])
def test_an_asleep_view_files_the_voices_it_knew(language, level):
    residue = composer.residue_percepts(level)
    prev = frozenset({VOICE, "env:aaa:bbb"})
    view = composer.render_view(residue, mode="character", language=language,
                                prev_standing=prev)
    assert VOICE in view.standing_keys, (language, view.standing_keys)
    # Only the voices ride across: the room is not re-filed for a sleeper.
    assert "env:aaa:bbb" not in view.standing_keys
