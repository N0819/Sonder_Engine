"""An action belongs to the body that does it; what is felt from another
body is that body's, never the feeler's act.

Measured on the owner's chat 178 turns 27-29 (2026-10-19): with Mellisande's
lips on Hinami's throat, the encoder wrote a contact effect `steady pulse`
with `actor: Mellisande`, and at turn 29 wrote the player's own quickening
heartbeat into it. The effect's actor sustains it and the other participant
feels it (`spatial_substance.contact_action_clause`), so the page read "her
heartbeat comes to you" -- Hinami told she felt the pulse she herself had.
The card said only that `actor` is "one participant in the contact".
"""

from __future__ import annotations

from llm.prompts import unified_specialist_prompt


def test_the_card_names_whose_effect_a_felt_one_is():
    en = unified_specialist_prompt(["contact_action_ops"], "en", [])
    ja = unified_specialist_prompt(["contact_action_ops"], "ja", [])
    assert "is the participant whose body or doing produces the effect" in en
    assert "never an effect the feeler sustains" in en
    assert "感じ取る側が保つ効果には決してしません" in ja
    assert "`actor` is one participant in the contact." not in en
    # Written the card's way -- the pulse its owner's -- the feeler is the
    # one who feels it (`spatial_substance.contact_action_clause`).
    from world.spatial import contact_action_clause
    pulse = {"actor": "Hinami", "action": "steady pulse", "rhythm": "quickening"}
    assert contact_action_clause(pulse, observer="Mellisande").startswith("You feel")
    assert contact_action_clause(pulse, observer="Hinami").startswith("You sustain")
