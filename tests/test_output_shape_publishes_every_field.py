"""A field the model is not SHOWN does not exist as far as it is concerned.

The class this guards is measured, not theorised. `ledger_notes` was added to
the schema, to the payload and to the prose author's own sheet, and grok-4.3
emitted zero of them on a live replay -- because the OUTPUT SHAPE, the JSON
field list at the end of the sheet, never mentioned it. The prose said "write
one short line per specialist" a thousand tokens earlier and the template won.
Three more of the same shape were found on 2026-09-01 and fixed in this
commit: `travel_interrupted` (asked by name and shape in
`prose_author_sheet/10_travel.txt`, absent from the template that follows it),
`thoughts_omitted` (asked in `prose_author_sheet/04.txt`, same), and
`CourierOp.freight` -- consumed by `world/charter_runtime.load_caravan_freight`
and `exchange_caravan_freight`, and asked for in NO prompt in either pack.

Three bars, because the stages publish their shape in different ways and one
rule over all of them would be dishonest:

  * THE PROSE-DIRECTOR BAR. Both invocation points publish the same two
    fields, `prose` and `places` (the causal Director's single `ledgers`
    until 2026-09-27). Any other schema field is a checkpoint compatibility
    reader and must stay out of the model contract.
  * THE TEMPLATE BAR, for the character. Its bare card ends in one
    self-contained `Answer with JSON only: {...}` field list.
  * THE SHEET BAR, for the encoder (the five specialists until 2026-09-27).
    Its sheet has no single template: each granted chunk states its own
    channel and shape, so the assembled sheet as a whole IS the publication,
    and a field named anywhere in it has been published to the model that
    must write it.

Anything not published is enumerated below WITH ITS REASON. That list is the
point of the test: an engine-authored or retired field is a decision, and a
decision that is written down is one a later reader can overturn.

SCOPED TO THE ENGLISH PACK, deliberately. The ja pack translates the marker
("厳密なJSONを出力してください"), so there is no stable anchor for the template
bar there; and measured on 2026-09-01 its specialist sheets are missing
`phase_sources` and `resolved_events.reroute_to` in all six, plus
`attire.regions` (body) and `resolved_events` (contact, offscreen) -- a
translation-completeness question with its own owner, which enumerating here
would bury under this one. (Those sheets went with the causal Director on
2026-09-27; the question is the encoder card's now.) en/ja parity for an edit is already the card-split
divergence ledger's job (tests/test_prompt_card_split.py).
"""

from __future__ import annotations

import json
import re
import typing

import pytest

from llm import schemas
from llm.prompts import (DEFAULT_PROMPTS, prose_director_prompt,
                         unified_specialist_prompt)


#: step key -> the prompt id whose body the stage is actually sent.
TEMPLATE_STAGES = {"character_bare": "character_bare"}

#: The prose Director is one step (`director_prose`) with a sheet per stage.
PROSE_DIRECTOR_STAGES = ("interpret", "resolve")

#: The line that opens a stage's JSON field list, one spelling per card.
_SHAPE_MARKERS = ("Output STRICT JSON", "Answer with JSON only")


#: "<step>.<dotted field path>" -> why the hand that writes the stage is never
#: shown this field. Every entry must be a DECISION, and the test fails an
#: entry that has gone stale (the field is published now, or no longer exists),
#: so this cannot decay into a mute allowlist.
UNPUBLISHED = {
    # --- the character ----------------------------------------------------
    "character_bare.people": (
        "the lines the notebook replaced (2026-09-27): no longer on the card, "
        "still read as new notes from a reply that writes them"),
    # --- specialists ------------------------------------------------------
    # `director_objects.entities.ubiquitous` stood here as an OPEN residual
    # until 2026-09-01 and is now published in both packs
    # (specialists/objects/chunks/entities.txt), so the entry is gone -- which
    # is what test_the_unpublished_ledger_has_no_stale_entries requires.
}


def _submodels(annotation):
    """Every LenientModel reachable from one field annotation."""
    found, stack = [], [annotation]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        if isinstance(node, type) and issubclass(node, schemas.LenientModel):
            found.append(node)
        stack.extend(typing.get_args(node))
    return found


def _field_paths(model, seen=None, prefix=""):
    """(dotted path, leaf name) for every field of a model and its children.

    Recursion is guarded by model identity, not by path: a model reachable
    twice is walked once, which is what keeps `StateDiff`-shaped schemas from
    exploding into thousands of paths.
    """
    seen = {model} if seen is None else seen
    hints = typing.get_type_hints(model)
    rows = []
    for name in (schemas._fields(model) or {}):
        rows.append((prefix + name, name))
        for sub in _submodels(hints.get(name)):
            if sub in seen:
                continue
            seen.add(sub)
            rows += _field_paths(sub, seen, prefix + name + ".")
    return rows


def _names(text, name):
    """Does this prompt text name the field? Word-bounded, so `travel` does
    not match inside `travel_interrupted` and vice versa -- the two are
    different fields with different owners."""
    return bool(re.search(r"\b%s\b" % re.escape(name), text))


def _template(step, pid, body=None):
    """The JSON field list a template stage ends with, and nothing before it.

    Anchored at the marker rather than taking the whole line, because the
    character sheet's lead-in prose shares that line and names `speech` --
    which is a derived mirror, not a field the model fills. Counting the
    prose would make this test pass on exactly the arrangement it exists to
    catch.
    """
    body = DEFAULT_PROMPTS[pid] if body is None else body
    index = max(body.rfind(marker) for marker in _SHAPE_MARKERS)
    assert index >= 0, (
        f"{step}: none of {_SHAPE_MARKERS!r} in its assembled prompt. Either the "
        "stage stopped publishing an output template -- which is the defect "
        "this file guards -- or the marker was reworded and this test needs "
        "to learn the new one.")
    # Templates may put the JSON object on the marker line or immediately
    # below it. Stop at the following paragraph, not at the first newline.
    return body[index:].split("\n\n", 1)[0]


@pytest.mark.parametrize("stage", PROSE_DIRECTOR_STAGES)
def test_the_prose_director_publishes_only_prose_and_places(stage):
    """Compatibility fields parse old checkpoints; they are not live output.

    The causal Director's `ledgers` until 2026-09-27. The retired resolve
    fields (`travel_interrupted`, `thoughts_omitted`, `state_diff`) had a test
    of their own; an exact key set already refuses them.
    """
    template = _template("director_prose", None,
                         body=prose_director_prompt(stage))
    published = set(json.loads(template[template.index("{"):]))
    assert published == {"prose", "places"}


@pytest.mark.parametrize("step", sorted(TEMPLATE_STAGES))
def test_the_output_template_names_every_field_the_stage_owns(step):
    model = schemas.SCHEMA_MAP[step]
    template = _template(step, TEMPLATE_STAGES[step])
    unpublished = [
        name for name in (schemas._fields(model) or {})
        if not _names(template, name)
        and f"{step}.{name}" not in UNPUBLISHED
    ]
    assert not unpublished, (
        f"{step}: {unpublished} are fields of {model.__name__} that its "
        "output template never names. A field asked for in prose and absent "
        "from the shape is a field that does not exist as far as the model "
        "is concerned (grok-4.3, ledger_notes, 2026-09-01). Add it to the "
        "template in BOTH packs, or add it to UNPUBLISHED with the reason it "
        "is never asked for.")


def test_the_unpublished_ledger_has_no_stale_entries():
    """An allowlist nobody prunes stops being a decision and becomes a hole.

    Two ways an entry goes stale: the field is published now (the ledger is
    hiding nothing and should say so by not existing), or the field is gone
    from the model (the ledger names something that cannot be written at all).
    """
    live = {}
    for step, pid in TEMPLATE_STAGES.items():
        template = _template(step, pid)
        for name in (schemas._fields(schemas.SCHEMA_MAP[step]) or {}):
            live[f"{step}.{name}"] = _names(template, name)
    unknown = sorted(key for key in UNPUBLISHED if key not in live)
    assert not unknown, (
        f"{unknown} are listed as deliberately unpublished but are not fields "
        "of their stage's model. Delete the entry with the field.")

    now_published = sorted(key for key in UNPUBLISHED if live[key])
    assert not now_published, (
        f"{now_published} are listed as deliberately unpublished and their "
        "prompt names them. Delete the ledger entry in the commit that "
        "publishes the field.")


def test_every_ledger_entry_gives_a_reason():
    """The same discipline EXPECTED_DIVERGENCE.json applies: an entry that
    says nothing is a re-baseline in disguise."""
    for key, reason in UNPUBLISHED.items():
        assert isinstance(reason, str) and len(reason.split()) >= 4, (
            f"{key} is listed as unpublished with no usable reason")


def test_caravan_freight_is_published_to_the_hand_that_writes_it():
    """`freight` is the only field of CourierOp that moves real stock, and it
    was asked for nowhere. The three keys are a closed set the ENGINE owns
    (world/charter_runtime.load_caravan_freight reads exactly `from_holder`,
    `stock` and `wants`), which is the kind of vocabulary that SHOULD be
    published rather than guessed at.

    The hand that writes it is the encoder since 2026-09-27, and the keys are
    in the channel's own chunk, not a part the decision model may leave out.
    """
    sheet = unified_specialist_prompt(["courier_ops"], "en", [])
    for token in ("freight", "from_holder", "stock", "wants"):
        assert token in sheet, token

