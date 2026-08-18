

def test_the_narrator_is_told_which_bodies_have_which_parts():
    """Measured live: the narration gave Elyra the player's six fox tails.
    Her card declares no extra parts at all, so nothing in the narrator's
    payload could have said otherwise -- perception and the Director have
    carried this index all along, and only the stage that writes the prose
    was without it.

    Same fact and same failure as `cast_pronouns`, which exists because
    guessing flipped a character's pronouns across beats."""
    from llm.prompts import get_prompt

    sheet = get_prompt("narrator")
    assert "authored_body_parts" in sheet
    # Stated as a SUBTRACTION -- the list bounds what may be written, it is
    # not content to render.
    assert "is not listed there has NONE" in sheet
    assert "never give" in sheet and "a part it does not have" in sheet
