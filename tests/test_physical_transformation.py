"""A body that has actually changed, as opposed to one that is lying about it.

A DISGUISE IS A LIE WITH A TRUTH BEHIND IT -- hence `concealed_truth`,
`known_to`, and a fallback that fails toward concealment. A TRANSFORMATION HAS
NO TRUTH BEHIND IT: the body IS the new thing, nobody sees through it, and
somebody who knew you yesterday does not perceive your old shape today.
Modelling one as the other would invent a hidden fact where none exists and
hand other minds a `known_to` slot to be granted access to it.

So a transformation REPLACES where a disguise conceals, which is also what
lets it ADD -- a disguise can only ever subtract, and growing wings is the
ordinary case for a transformation.

Two rules the fiction depends on:

  * TRUTH FIRST, THEN CONCEALMENT. A transformed body can also be glamoured;
    the glamour then hides the fox's tail rather than the woman's.
  * REVERSIBLE UNLESS SAID OTHERWISE. A one-way door has to be chosen, because
    trapping somebody by forgetting a field is the one mistake here that
    cannot be undone from inside the fiction.
"""

import json

import pytest

from scene import (
    SINGULAR_BODY_CONDITIONS,
    active_transformations,
    conceal_disguised_parts,
    transformed_parts,
    transformed_sheet,
    transformed_true_appearance,
)


FOX = {"form": "a red fox",
       "appearance": "a small red fox, russet and quick",
       "parts": [{"kind": "tail", "count": 1, "at": "haunches"}]}

CARD_PARTS = [{"kind": "tails", "count": 6, "at": "waist"},
              {"kind": "fox ears", "count": 2, "at": "head"}]


# ---- Replacement, not concealment ----

def test_the_true_appearance_is_replaced_outright():
    """A body that is now a fox is not a woman with the fox words removed."""
    assert transformed_true_appearance(
        "A young woman with golden fox ears", FOX) == FOX["appearance"]


def test_form_carries_it_when_no_prose_was_written():
    assert transformed_true_appearance("a woman", {"form": "a red fox"}) == \
        "a red fox"


def test_an_empty_transformation_does_not_blank_a_body_out_of_the_world():
    assert transformed_true_appearance("a woman", {}) == "a woman"
    assert transformed_true_appearance("a woman", None) == "a woman"


def test_parts_are_replaced_so_a_transformation_can_add_or_remove():
    """The list is authoritative and total. A fox has one tail and no hands
    whatever the card said, and a body can be given a part no card declares --
    which a disguise, being subtractive only, can never do."""
    assert transformed_parts(CARD_PARTS, FOX) == FOX["parts"]
    assert transformed_parts([], {"parts": [{"kind": "wing", "count": 2}]}) == \
        [{"kind": "wing", "count": 2}]


def test_absent_parts_and_empty_parts_are_different_answers():
    """`parts` absent means "unchanged"; `parts: []` means "none". Collapsing
    them would make it impossible to transform INTO something plain."""
    assert transformed_parts(CARD_PARTS, {"form": "a statue"}) == CARD_PARTS
    assert transformed_parts(CARD_PARTS, {"form": "a statue", "parts": []}) == []


# ---- The mind in the body ----

def test_the_transformed_mind_gets_the_transformed_body():
    """THE ONE THAT MAKES IT PLAYABLE. Every character payload is built from
    the card -- senses, abilities, capabilities, parts -- so a transformation
    that stopped at the observer's view would leave the fox convinced it still
    had hands, declaring accordingly, and the Director refusing it every beat.
    """
    card = {"embodiment": {"visible": {"summary": "A young woman"},
                           "extra_parts": CARD_PARTS,
                           "senses": ["hearing"]}}
    out = transformed_sheet(card, FOX)
    assert out["embodiment"]["visible"]["summary"] == FOX["appearance"]
    assert out["embodiment"]["extra_parts"] == FOX["parts"]


def test_it_does_not_mutate_the_card_it_was_handed():
    """`sheet_state` reads are cached and shared across stages -- mutating in
    place would transform everybody's view of that card, permanently."""
    card = {"embodiment": {"visible": {"summary": "A young woman"},
                           "extra_parts": CARD_PARTS}}
    transformed_sheet(card, FOX)
    assert card["embodiment"]["visible"]["summary"] == "A young woman"
    assert card["embodiment"]["extra_parts"] == CARD_PARTS


def test_untouched_sections_of_the_card_survive():
    card = {"identity": {"name": "Hinami"},
            "competence": {"abilities": [{"name": "Foxfire"}]},
            "embodiment": {"senses": ["spiritual"]}}
    out = transformed_sheet(card, FOX)
    assert out["identity"] == card["identity"]
    assert out["competence"] == card["competence"]
    assert out["embodiment"]["senses"] == ["spiritual"]


def test_no_transformation_is_a_pass_through():
    card = {"embodiment": {"visible": {"summary": "A young woman"}}}
    assert transformed_sheet(card, None) is card


# ---- Truth first, then concealment ----

def test_a_transformed_body_can_still_be_disguised():
    """The order is the model. The glamour hides what the body currently HAS,
    so it hides the fox's tail -- not the six the card remembers."""
    parts = transformed_parts(CARD_PARTS, FOX)
    assert parts == FOX["parts"]
    hidden = conceal_disguised_parts(
        {"Hinami": parts},
        {"hinami": {"presented_appearance": "an ordinary woman"}})
    assert "Hinami" not in hidden


# ---- Reversibility ----

def test_reversible_by_default(temp_db):
    """Absent means reversible. A Director that forgets the field cannot
    strand anybody, which is the only safe direction for this to fail."""
    cid = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0.0)")
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,1)",
        ("t1", cid, "Hinami", "physical_transformation", 1.0,
         json.dumps({"subject_id": "Hinami", "state": {"form": "a red fox"}})))
    assert active_transformations(cid)["hinami"]["reversible"] is True


def test_a_one_way_door_has_to_be_chosen(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0.0)")
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,1)",
        ("t1", cid, "Hinami", "physical_transformation", 1.0,
         json.dumps({"subject_id": "Hinami",
                     "state": {"form": "a statue", "reversible": False,
                               "reversal": "only the one who cast it"}})))
    got = active_transformations(cid)["hinami"]
    assert got["reversible"] is False
    assert got["reversal"] == "only the one who cast it"


def test_the_newest_transformation_wins(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0.0)")
    for n, (started, form) in enumerate([(1.0, "a fox"), (2.0, "a crow")]):
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,"
            "kind,started_at,payload,active) VALUES(?,?,?,?,?,?,1)",
            (f"t{n}", cid, "Hinami", "physical_transformation", started,
             json.dumps({"subject_id": "Hinami", "state": {"form": form}})))
    assert active_transformations(cid)["hinami"]["form"] == "a crow"


def test_a_transformation_is_singular_like_a_disguise():
    assert "physical_transformation" in SINGULAR_BODY_CONDITIONS
    assert "physical_disguise" in SINGULAR_BODY_CONDITIONS


def test_ending_one_ends_every_transformation_on_that_body():
    """"You let the shape go" is a statement about the body. The Director
    cannot name ids it was never shown, so an ending clears them all."""
    from commit import _supersede_disguises

    calls = []

    class _Cur:
        def execute(self, sql, args=()):
            calls.append((" ".join(sql.split()), args))

    _supersede_disguises(_Cur(), 7, {"subject_id": "Hinami",
                                     "kind": "physical_transformation",
                                     "active": 0}, "whatever")
    sql, args = calls[0]
    assert "condition_id<>?" not in sql
    # Both kinds, because the group is singular as a whole: a body that
    # transforms back stops presenting any borrowed form, including a
    # glamour that was standing beside the transformation.
    assert args == (7, "physical_disguise", "physical_transformation",
                    "Hinami")


# ---- The contract the Director is given ----

@pytest.mark.parametrize("clause", [
    "PHYSICAL TRANSFORMATION",
    "This is NOT a disguise",
    "never give it known_to",
    "REVERSIBILITY IS THE DEFAULT",
    "re-emit it with active:false",
    "may ALSO be disguised",
])
def test_the_director_is_told_the_distinction(clause):
    import prompts

    assert clause in json.dumps(prompts.DEFAULT_PROMPTS)


def test_a_transformation_wins_over_a_disguise_that_outlived_it(temp_db,
                                                                monkeypatch):
    """ONE OUTWARD FORM, AND THE TRANSFORMATION IS IT.

    The two kinds are a singular group enforced at the write -- but a branch
    copies conditions wholesale without one. Live (chat 74): "you allow your
    glamour to come undone" minted a `physical_transformation` BESIDE three
    active disguises instead of ending them, so a body that had just revealed
    its true form went on presenting the false one. The observer watched the
    ears rise and saw human ears again on the very next beat.
    """
    from agents.perception import _subject_disguise_context

    monkeypatch.setattr(
        "agents.perception.active_disguises",
        lambda _c: {"hinami": {"subject": "Hinami",
                               "presented_appearance": "an ordinary human",
                               "concealed_terms": ["fox ears"],
                               "known_to": []}})
    monkeypatch.setattr(
        "agents.perception.active_transformations",
        lambda _c: {"hinami": {"subject": "Hinami",
                               "appearance": "a kitsune, ears and tails bare"}})

    visible, payload, known_to, _ci = _subject_disguise_context(
        1, "Hinami", "a kitsune, ears and tails bare", {})
    assert payload is None, "a transformed body is concealing nothing"
    assert known_to is None
    assert "ordinary human" not in visible
