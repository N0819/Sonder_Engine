"""A view is what ONE mind receives — it must not narrate that mind from outside.

Live, alpha 6.3, chat 52 "Elyndra — Hinami ⎇16 ⎇1" turn 19. Elyndra's own
perception view read:

    "Elyndra's gaze stays fixed on the shifting lump, her teasing smile
     faltering as she watches the genuine terror in that tiny trembling form."

in a view that elsewhere said "You see Hinami." Two things wrong from her side:
she is not watching her own smile falter, and she cannot know another mind's
terror is genuine.

Traced upstream, perception did not invent it. `director_resolve` had written
"Elyndra's teasing smile falters completely at the shrill, panicked cry", and
perception COPIED the omniscient sentence into her view rather than rendering
the beat from her frame. Per-observer calls did not prevent it: each observer
gets its own call, and this one echoed its input.
"""

from __future__ import annotations

from agents.perception import _strip_self_narration

VIEW = (
    'A thin, high cry rises from the rumpled quilt — the words cut through '
    'clear enough: "W-what did you do to me!?" The voice is breathy and '
    'shrill. '
    "Elyndra's gaze stays fixed on the shifting lump, her teasing smile "
    'faltering as she watches. '
    'The hearth coals pulse low orange. You see Hinami.'
)


def test_the_live_failure_is_removed():
    kept, dropped = _strip_self_narration(VIEW, "Elyndra")
    assert len(dropped) == 1
    assert "teasing smile" in dropped[0]
    assert "teasing smile" not in kept


def test_everything_else_survives_intact():
    kept, _ = _strip_self_narration(VIEW, "Elyndra")
    for surviving in ("A thin, high cry", "The voice is breathy",
                      "hearth coals pulse", "You see Hinami"):
        assert surviving in kept


def test_a_closing_quote_is_not_eaten_by_the_split():
    """`(?<=[.!?])\\s+` alone cannot split after '!?"' — the quote sits between
    the punctuation and the space. That made whole passages one "sentence" and
    let this guard pass everything."""
    kept, _ = _strip_self_narration(VIEW, "Elyndra")
    assert 'to me!?"' in kept


def test_a_pronoun_subject_is_never_guessed_at():
    """"She watches the lump" could be anyone in the beat, and guessing would
    gut legitimate views."""
    assert _strip_self_narration("She watches the lump.", "Elyndra")[1] == []


def test_another_character_is_left_alone():
    assert _strip_self_narration("Hinami trembles.", "Elyndra")[1] == []


def test_a_view_is_never_emptied_entirely():
    """A perceiver who received something must be told something. If every
    sentence named them, the view is beyond repair by deletion."""
    view = "Elyndra smiles. Elyndra steps closer."
    kept, dropped = _strip_self_narration(view, "Elyndra")
    assert kept == view and dropped == []


def test_the_possessive_form_is_caught():
    kept, dropped = _strip_self_narration(
        "Elyndra's wings fold tight. The lamp gutters.", "Elyndra")
    assert dropped and "The lamp gutters." in kept


def test_missing_inputs_are_noops():
    assert _strip_self_narration("", "Elyndra") == ("", [])
    assert _strip_self_narration("Anything.", "") == ("Anything.", [])


def test_every_perception_stage_applies_the_guard():
    """Pass 1 applies the identity floor DIRECTLY rather than through
    `_scrub_view_for`, so it needs the guard wired explicitly — and it is the
    pass that most needs it. The act view is written closest to the Director's
    resolved_event, which is omniscient by construction, so it is the likeliest
    place for that omniscience to be copied through intact.

    Measured on a fresh 4-turn live run: 1 of 17 views narrated its own
    perceiver, and it was a pass-1 view.
    """
    import inspect

    from agents import perception
    for stage in (perception.perception_act,
                  perception.perception_establish,
                  perception.perception_outcome):
        src = inspect.getsource(stage)
        assert ("_strip_self_narration" in src
                or "_scrub_view_for" in src), stage.__name__


# --- the same boundary at the last stage ------------------------------------
#
# The chain that produced the live failure ran Director -> perception ->
# narrator. The Director asserted "the genuine terror"; perception copied it
# into another mind's view; the narrator renders what reaches the reader. A
# guard at the first two stages leaves the third able to add it back on its
# own — and there it becomes what the story SAID happened.

from agents.common import _check_player_interiority_prose

VIEW_SRC = "Your hands shake. The crimson figure leans closer."


def test_the_narrator_may_not_tell_the_player_what_they_feel():
    assert _check_player_interiority_prose(
        "You feel a genuine terror rising.", VIEW_SRC)


def test_an_emotion_that_acts_on_you_is_the_same_assertion():
    """"Terror grips you" asserts the state as surely as "you feel terror"."""
    assert _check_player_interiority_prose(
        "Terror grips you as she leans in.", VIEW_SRC)
    assert _check_player_interiority_prose("Your fear is unmistakable.", VIEW_SRC)


def test_the_body_is_always_the_narrators_to_render():
    for prose in ("Your hands shake as she leans closer.",
                  "Your hands shake and you take a step back.",
                  "Your breath catches and you go still."):
        assert _check_player_interiority_prose(prose, VIEW_SRC) == [], prose


def test_a_feeling_the_view_already_carried_is_rendering_not_adding():
    """Perception is the narrator's source of truth. A feeling that reached
    the view legitimately may be rendered; this catches what the narrator
    invents."""
    view = "You feel the cold through the floorboards."
    assert _check_player_interiority_prose(
        "You feel the cold through the floorboards.", view) == []


def test_it_is_enforced_rather_than_merely_warned():
    """It is the LAST stage — an interior state asserted here reaches the
    reader as fact, so it earns a rewrite rather than a note nobody reads."""
    from agents.narration import _ENFORCEABLE_PREFIXES
    assert any("interior state" in p for p in _ENFORCEABLE_PREFIXES)


def test_empty_prose_is_a_noop():
    assert _check_player_interiority_prose("", VIEW_SRC) == []


# Chat 56 ("Run!") t6, verbatim from perception_outcome.views["player"]: the
# Director's omniscient sentence copied whole into the PLAYER's own view, in
# the third person, naming an interior state the player never declared.
T6_PLAYER_VIEW = (
    "Warm amber light fills the console chamber, the roundel walls glowing "
    "faintly. Hinami stands by the doors. She feels her arms still wrapped "
    "tightly, her breathing slowing, the terror in her eyes beginning to "
    "recede."
)


def test_third_person_self_narration_under_a_pronoun_is_dropped():
    view, dropped = _strip_self_narration(
        T6_PLAYER_VIEW, "Hinami", ["Hinami", "The Doctor"])
    assert dropped, "the perceiver cannot watch her own terror recede"
    assert "terror in her eyes" not in view
    assert "Warm amber light" in view, "the rest of the view must survive"


def test_a_view_that_never_names_the_perceiver_is_left_alone():
    """An unanchored pronoun binds to nobody rather than to a guess."""
    view, dropped = _strip_self_narration(
        "She watches the shifting lump.", "Hinami", ["Hinami", "The Doctor"])
    assert dropped == []


def test_another_bodys_sentences_are_not_dropped():
    view, dropped = _strip_self_narration(
        "The Doctor steps back. He raises both hands.", "Hinami",
        ["Hinami", "The Doctor"])
    assert dropped == []
    assert "raises both hands" in view


def test_narrator_may_not_name_the_players_interior_state_at_a_distance():
    """Chat 56 t6, verbatim narrator prose. Every branch of _YOU_INTERIOR
    required the state to sit beside "you"/"your" or govern it through a short
    verb list; here "your" attaches to "eyes" and the verb is "pulls back"."""
    assert _check_player_interiority_prose(
        "The terror that had been living wide-open in your eyes pulls back to "
        "something smaller, something that can blink.", VIEW_SRC)


def test_observable_surface_at_a_distance_is_still_allowed():
    """The widened branch must not swallow ordinary description."""
    for prose in ("The tremor that had been running through your hands eases.",
                  "The light in your eyes steadies.",
                  "The grip on your arm loosens."):
        assert _check_player_interiority_prose(prose, VIEW_SRC) == [], prose


# ---- the article belongs to the prose, not to the name ----
#
# Live, chat 58 t28. The Dalek's own view read "The Dalek's visual sensors pick
# up...", "The Dalek hears the Doctor's sharp call", "The Dalek's own base
# grinds forward" — third person about its own perceiver, in the view addressed
# to it, and invisible to this guard. Its registered name is "A Dalek", so the
# subject forms were "A Dalek" and "Dalek", and neither opens a sentence that
# begins "The Dalek's". The article is the only difference — the same trap
# docs/UNBUILT.md §1.17 documents for presence identity.

def test_a_body_named_with_an_article_is_caught_under_another_article():
    view = ("The Dalek's visual sensors pick up the man in the trench coat. "
            "The Dalek hears a sharp call. "
            "Rain hisses on the wet pavement.")
    kept, dropped = _strip_self_narration(view, "A Dalek", ["The Doctor"])
    assert len(dropped) == 2
    assert "Rain hisses" in kept
    assert "visual sensors" not in kept
    assert "hears a sharp call" not in kept


def test_the_bare_name_and_the_registered_form_both_still_bind():
    for opener in ("A Dalek swivels its eye-stalk.",
                   "Dalek swivels its eye-stalk.",
                   "An Dalek swivels its eye-stalk."):
        kept, dropped = _strip_self_narration(
            opener + " Rain hisses on the pavement.", "A Dalek", [])
        assert dropped, opener
        assert "Rain hisses" in kept


def test_an_article_does_not_let_one_body_absorb_another():
    # "The Doctor" must not be read as the Dalek merely because both can carry
    # a leading article.
    view = ("The Doctor raises the sonic screwdriver. "
            "The Dalek grinds forward.")
    kept, dropped = _strip_self_narration(view, "A Dalek", ["The Doctor"])
    assert dropped == ["The Dalek grinds forward."]
    assert "The Doctor raises" in kept


def test_the_article_tolerance_does_not_swallow_a_title():
    # §1.17's line: a TITLE often is the only thing telling two bodies apart,
    # so it is never treated as a droppable leader here.
    view = "The captain signals the guard. The guard does not move."
    kept, dropped = _strip_self_narration(view, "The guard", ["The captain"])
    assert "The captain signals" in kept
    assert dropped == ["The guard does not move."]
