"""The mapping model no longer transcribes lore back to the engine.

`relevant_lore` used to be asked for as `{id, book_id, keys, content,
category, why_relevant}` — the whole entry, echoed back out of the same
`candidate_lore` rows the engine had just handed in. Measured over all 416
real mapping calls in the corpus (855 entries): 86.3% came back
byte-identical, 5.8% truncated, 7.7% rewritten at a median 59% of the true
length.

The mutated 13.6% is the part that matters. `lore_for` forwards the echo
into the Director's payloads and `commit.py` writes it into `lore_cache`,
which `mapping_quick` re-serves with no model call for 1,879 of 1,881
measured steps — so an abridged echo becomes the *served* copy of that
entry until some later real mapping call happens to replace it. The engine
held the true rows in `hits` the whole time.

These tests pin the join, and pin that the two things the model is actually
authoring — which entries, and why — survive it.
"""

from __future__ import annotations

from agents import mapping


class _Ctx:
    def __init__(self):
        self.warnings = []

    def add_warning(self, msg):
        self.warnings.append(msg)


def _hit(entry_id=7, content="The lighthouse keeper has not been seen since "
                             "the equinox, and the lamp still turns."):
    return {
        "id": entry_id, "entry_uid": "u7", "book_id": 3,
        "keys": "lighthouse, keeper", "content": content,
        "category": "location", "locked": True,
    }


def test_an_abridged_echo_is_replaced_by_the_stored_entry():
    ctx = _Ctx()
    hit = _hit()
    joined = mapping._join_relevant_lore(
        ctx,
        [{"id": 7, "book_id": 3, "keys": "lighthouse",
          "content": "The lighthouse keeper is missing.",
          "category": "location", "why_relevant": "they are at the door"}],
        [hit])
    assert joined[0]["content"] == hit["content"]
    assert joined[0]["keys"] == hit["keys"]
    assert not ctx.warnings


def test_the_models_own_judgement_survives_the_join():
    """Which entries, and why: the only two things still being authored."""
    ctx = _Ctx()
    joined = mapping._join_relevant_lore(
        ctx, [{"id": 7, "why_relevant": "they are at the door"}], [_hit()])
    assert joined[0]["why_relevant"] == "they are at the door"
    assert joined[0]["content"] == _hit()["content"]


def test_a_bare_id_is_enough_to_reconstitute_the_whole_entry():
    """What the trimmed contract actually asks for."""
    ctx = _Ctx()
    joined = mapping._join_relevant_lore(ctx, [{"id": 7}], [_hit()])
    assert joined[0] == {**{"id": 7}, **_hit()}


def test_an_id_the_engine_never_offered_is_kept_and_warned_about():
    """Either a hallucinated citation or a retrieval path this join does not
    know about. Dropping it silently would hide both."""
    ctx = _Ctx()
    joined = mapping._join_relevant_lore(
        ctx, [{"id": 99, "content": "invented"}], [_hit()])
    assert joined[0]["content"] == "invented"
    assert len(ctx.warnings) == 1
    assert "99" in ctx.warnings[0]


def test_string_and_int_ids_are_the_same_entry():
    """Models emit `"7"` as readily as `7`; a type mismatch would silently
    route every entry down the unverified branch."""
    ctx = _Ctx()
    joined = mapping._join_relevant_lore(ctx, [{"id": "7"}], [_hit()])
    assert joined[0]["content"] == _hit()["content"]
    assert not ctx.warnings


def test_the_prompt_no_longer_asks_for_the_entry_text():
    from llm.prompts import get_prompt
    text = get_prompt("mapping_stage")
    assert "relevant_lore:[{id,why_relevant}]" in text
    assert "relevant_lore:[{id,book_id,keys,content" not in text


def test_nothing_and_junk_are_survivable():
    ctx = _Ctx()
    assert mapping._join_relevant_lore(ctx, None, None) == []
    assert mapping._join_relevant_lore(ctx, ["not a dict", 3], [_hit()]) == []
