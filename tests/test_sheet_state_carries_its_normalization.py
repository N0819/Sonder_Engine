"""A cast row's card is normalized once, not once per field read (C14 residual).

`sheet_state` handed back a raw parse, and its thirteen call sites -- eleven
in `agents/perception.py` -- then asked that raw card seven to ten questions
apiece, each rebuilding the whole default tree and merging the card over it.
Measured on the review's bench copies, min of twenty in matching processes:
one site's card reads cost 78.3 ms on chat 114's 19 KB card and 43.8 ms on
chat 117's 26 KB one; through the carried normalization, 1.4 ms and 0.9 ms.

The card it hands back is still the card AS STORED, and that is the whole
constraint: the four kind dispatchers in `story/scene.py` route on a section
only one kind of card has, and `cast_entity_id` must read the uid the author
wrote rather than the one normalization mints. So the raw shape is what the
object IS; the normalization rides alongside.
"""

import copy
import json

from story import scene
from story.character_schema import (
    CardWithNormalization, cast_entity_id, character_name,
    normalize_character_data, stored_card_from_text,
)


_NATIVE = {
    "identity": {"name": "Kit", "uid": "char_authored"},
    "psychology": {"drive": {"essence": "to be let back in"}},
    "embodiment": {"senses": [{"channel": "hearing", "acuity": "keen"}],
                   "scent": "woodsmoke"},
}

#: A card so old it has none of the sections the dispatchers look for. This
#: is the one the whole constraint exists for: normalization GIVES it a
#: `psychology` section, which would route it into a branch it has been
#: falling past since it was written.
_MINIMAL_LEGACY = {"name": "Kit", "senses": "keen hearing", "scent": "smoke"}


def _row(sheet, cstate="{}"):
    return {"sheet": json.dumps(sheet), "cstate": cstate}


def test_the_card_is_the_card_as_stored():
    card, _active, _stance = scene.sheet_state(_row(_NATIVE))
    assert isinstance(card, CardWithNormalization)
    assert dict(card) == _NATIVE


def test_normalization_of_it_is_the_one_it_carries():
    card, _a, _s = scene.sheet_state(_row(_NATIVE))
    assert normalize_character_data(card) is card.normalized
    assert (json.dumps(normalize_character_data(card), sort_keys=True)
            == json.dumps(normalize_character_data(_NATIVE), sort_keys=True))


def test_a_minimal_legacy_card_still_answers_the_dispatchers_raw():
    """The reason the carried card is the RAW one and not the product."""
    card, _a, _s = scene.sheet_state(_row(_MINIMAL_LEGACY))
    assert scene.senses_of(card) == scene.senses_of(_MINIMAL_LEGACY)
    assert scene.senses_of(card) == "keen hearing"
    assert scene.scent_of(card) == "smoke"
    # And normalized it would answer something else entirely -- which is
    # exactly what a caller handing the product to these would have got.
    assert scene.senses_of(normalize_character_data(_MINIMAL_LEGACY)) \
        != "keen hearing"


def test_the_entity_id_is_the_authored_one_not_the_minted_one():
    card, _a, _s = scene.sheet_state(_row(_NATIVE))
    assert cast_entity_id(card, 7) == "char_authored"
    unauthored, _a, _s = scene.sheet_state(_row({"identity": {"name": "Kit"},
                                                 "psychology": {}}))
    assert cast_entity_id(unauthored, 7) == "character:7"


def test_the_defaults_are_what_they_were():
    card, active, stance = scene.sheet_state(_row(_NATIVE))
    assert active == scene.character_initial_active_state(_NATIVE)
    assert stance == scene.character_initial_stance(_NATIVE)
    assert character_name(card) == "Kit"


def test_stored_state_still_wins_over_the_cards_defaults():
    row = _row(_NATIVE, json.dumps({"active_state": {"mood": "wary",
                                                     "goal": "get out"},
                                    "stance": {"axes": {"trust_player": 0.5}}}))
    _card, active, stance = scene.sheet_state(row)
    assert active == {"mood": "wary", "goal": "get out"}
    assert stance == {"axes": {"trust_player": 0.5}}


def test_two_calls_do_not_share_a_card_a_caller_could_mutate():
    a, _x, _y = scene.sheet_state(_row(_NATIVE))
    b, _x, _y = scene.sheet_state(_row(_NATIVE))
    assert a is not b and a.normalized is not b.normalized
    a["identity"]["name"] = "Someone else"
    assert character_name(b) == "Kit"


def test_it_survives_the_copies_the_pipeline_makes():
    card, _a, _s = scene.sheet_state(_row(_NATIVE))
    assert json.loads(json.dumps(card)) == _NATIVE
    assert type(dict(card)) is dict
    deep = copy.deepcopy(card)
    assert normalize_character_data(deep) == card.normalized
