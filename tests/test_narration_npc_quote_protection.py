"""Regression test for the player-echo strip corrupting an NPC's legitimately
quoted line (AUDIT_FINDINGS #20 / MEDIUM).

_strip_player_echo runs AFTER the narrator fidelity check and used to remove
EVERY occurrence of a player line -- including one that coincides with, or is a
substring of, an NPC line the fidelity check just required verbatim. That turns
the strip into the exact ABSOLUTE-tier dialogue-fidelity violation the retry
loop exists to prevent.

Fix: _strip_player_echo masks NPC-attributed quoted spans (passed via
protect_quotes) so the strip can never reach inside them, while still removing
the player's own echoed line elsewhere in the prose.
"""

from __future__ import annotations

from agents.common import _protected_view_quotes, _strip_player_echo


def test_npc_quote_matching_player_line_is_preserved():
    # Both the player and an NPC say "Stop!"; the NPC's quoted line must
    # survive verbatim even though it equals the player's echoed line.
    prose = 'You shout, "Stop!" Kael freezes, then answers, "Stop!"'
    protect = ["Stop!"]  # NPC's line, from the perceiver's view
    result = _strip_player_echo(prose, ["Stop!"], protect_quotes=protect)

    # The NPC's quoted line is still present (fidelity preserved).
    assert '"Stop!"' in result
    # And the NPC's own attribution survives.
    assert "Kael" in result and "answers" in result


def test_player_echo_still_stripped_when_no_npc_quote_protects_it():
    prose = 'You say, "I am done with this." Kael says nothing.'
    result = _strip_player_echo(
        prose, ["I am done with this."], protect_quotes=[])
    assert "I am done with this." not in result


def test_long_npc_quote_containing_player_substring_is_not_corrupted():
    # Player line is a substring of a longer NPC quote; the bare-substring
    # strip (len>=8) would otherwise mutilate the NPC's verbatim line.
    prose = ('You mutter, "the shipment arrives." '
             'Kael grins: "So the shipment arrives at midnight after all."')
    protect = ["So the shipment arrives at midnight after all."]
    result = _strip_player_echo(
        prose, ["the shipment arrives."], protect_quotes=protect)

    assert "So the shipment arrives at midnight after all." in result


def test_protected_view_quotes_excludes_player_lines():
    view = ('Kael says: "Hold the line." You hear yourself say: "Retreat now."')
    quotes = _protected_view_quotes(view, player_lines=["Retreat now."])
    assert "Hold the line." in quotes
    assert "Retreat now." not in quotes
