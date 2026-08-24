"""The deterministic craft screen that flags banned AI-tell phrases in narrator
prose (triggering a one-shot rewrite in the narrator stage)."""
from agents.narration import _craft_tells


def test_flags_common_ai_tells():
    prose = ("I stand by the fire, letting the warmth wash over me as I take the common "
             "room in. Sable shifts her weight, her eyes flicking to the door, his gaze on "
             "the middle distance. The lamp casts a faint diffused glow, deliberate and slow.")
    tells = _craft_tells(prose)
    for expected in ("washes over (emotion)", "shifts weight", "eyes flick", "middle distance",
                     "generic muted/dim + light/sound",
                     "adverb tell (deliberate/unhurried/pointedly/casually)"):
        assert expected in tells, (expected, tells)
    assert any("take the room in" in t for t in tells)


def test_flags_perception_ledger_diction_but_not_ordinary_registration():
    """Typed sensation wording is evidence for prose, not publishable prose.

    The live failure copied a standing contact clause almost literally into
    the final sentence: "The contact at your own wrist registers ...". Keep
    the trigger tied to a possessed body/contact surface so an instrument or
    clerk legitimately registering something does not spend a rewrite.
    """
    awkward = (
        "The contact at your own hand registers her fingertips still moving "
        "against it."
    )
    assert "sensor-ledger diction ('registers')" in _craft_tells(awkward)
    for copied_clause in (
        "Steady pressure, weight, and shared warmth register against my palm.",
        "The shared warmth and steady pressure of Rowan's hand keep "
        "registering against my own.",
    ):
        assert "sensor-ledger diction ('registers')" in _craft_tells(
            copied_clause)
    assert _craft_tells("The seismograph registers a second impact.") == []
    assert _craft_tells("The clerk registers the caravan at the gate.") == []


def test_clean_publishable_prose_has_no_tells():
    # The style exemplars must not self-trigger.
    for prose in (
        "The tide has turned; I can smell it before I reach the door — mudflat and old "
        "rope. The fire has burned down to a red seam. The barkeep counts coin by feel.",
        "The big man stands. Just that. His stool doesn't scrape — he lifts himself off it "
        "the way you lift a blade from a sheath. Three steps to the bar.",
        "She turns her cup a quarter-turn on the boards and studies the ring of wet it "
        "leaves. Behind me a door bangs against its chain.",
    ):
        assert _craft_tells(prose) == [], (prose, _craft_tells(prose))


def test_empty_prose_is_safe():
    assert _craft_tells("") == []
    assert _craft_tells(None) == []


def test_tells_inside_dialogue_are_ignored():
    # A banned word spoken in a quote is not the narrator's prose and can't be
    # rewritten away -- masking quotes prevents a wasted retry every turn.
    assert _craft_tells('She says, "Don\'t just casually mention that!"') == []
    assert _craft_tells('"Deliberate work," he grunts, setting the cup down.') == []


def test_literal_hands_and_water_not_flagged():
    assert _craft_tells("I take the mug in both hands and drink.") == []
    assert _craft_tells("The wave washes over the deck and drains through the scuppers.") == []
