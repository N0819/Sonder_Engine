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

Two bars, because the stages publish their shape two different ways and one
rule over both would be dishonest:

  * THE TEMPLATE BAR, for the prose author and the character. Both sheets end
    in one self-contained `Output STRICT JSON {...}` field list, and that
    list -- not the surrounding prose -- is what a model fills in. Naming a
    field only in the prose is exactly the defect above, so prose does not
    count here.
  * THE SHEET BAR, for the six specialists. Their sheets have no single
    template: each granted chunk states its own channel and `Shape:` line, so
    the assembled sheet as a whole IS the publication, and a field named
    anywhere in it has been published to the hand that must write it.

Anything not published is enumerated below WITH ITS REASON. That list is the
point of the test: an engine-authored or retired field is a decision, and a
decision that is written down is one a later reader can overturn.

SCOPED TO THE ENGLISH PACK, deliberately. The ja pack translates the marker
("厳密なJSONを出力してください"), so there is no stable anchor for the template
bar there; and measured on 2026-09-01 its specialist sheets are missing
`phase_sources` and `resolved_events.reroute_to` in all six, plus
`attire.regions` (body) and `resolved_events` (contact, offscreen) -- a
translation-completeness question with its own owner, which enumerating here
would bury under this one. en/ja parity for an edit is already the card-split
divergence ledger's job (tests/test_prompt_card_split.py).
"""

from __future__ import annotations

import re
import typing

import pytest

from llm import schemas
from llm.prompts import DEFAULT_PROMPTS


#: step key -> the prompt id whose body the stage is actually sent. The prose
#: author's sheet is ASSEMBLED (`director_resolve_lean`), not stored, which is
#: why the id and the step key differ for exactly one entry.
TEMPLATE_STAGES = {
    "director_resolve": "director_resolve_lean",
    "character": "character",
}

SHEET_STAGES = ("director_body", "director_contact", "director_objects",
                "director_social", "director_spatial")

_SHAPE_MARKER = "Output STRICT JSON"


#: "<step>.<dotted field path>" -> why the hand that writes the stage is never
#: shown this field. Every entry must be a DECISION, and the test fails an
#: entry that has gone stale (the field is published now, or no longer exists),
#: so this cannot decay into a mute allowlist.
UNPUBLISHED = {
    # --- prose author -----------------------------------------------------
    # A DELEGATED CHANNEL. `public_evidence` belongs to the social specialist
    # (director_scopes._DELEGATED_CHANNELS), and run 20 measured what happens
    # when the prose author's template lists a channel it does not own: 18
    # discarded emissions in 14 beats, pure output-token latency. Its absence
    # is asserted directly by test_director_orchestration's
    # test_prose_author_shape_carries_no_delegated_fields.
    "director_resolve.public_evidence":
        "delegated to the social specialist; a delegated channel must have no "
        "field in the prose author's shape at all",
    # DECLARED, NOT ASKED. The engine rolls the dice itself from the interpret
    # flow's DiceSpec under a deterministic seed and overwrites the field
    # wholesale (agents/director.py:3441), and nothing reads the resolve-side
    # `fiction_frame` -- the payload builder reads the INTERPRET flow's copy.
    # The fields stay on the model because LenientModel drops undeclared keys
    # and persisted variants, archives and traces carry historical values.
    "director_resolve.dice":
        "engine-rolled and overwritten wholesale (director.py:3441); declared "
        "only so the round trip keeps stored history",
    "director_resolve.fiction_frame":
        "no reader touches the resolve-side copy; declared only so the round "
        "trip keeps stored history",
    # ENGINE-AUTHORED. The model never writes these; they are declared because
    # LenientModel's round trip would otherwise discard them on the way into
    # the persisted variant.
    "director_resolve.travel":
        "engine-authored: what the travel continuation did this beat, read by "
        "commit.py to retire or keep each standing approach record",
    "director_resolve.routed_to_background":
        "engine-authored: the hand-off of a Director-written line to the "
        "background stage",
    "director_resolve.sequence_dispositions":
        "engine-authored: deterministic causal verdicts composed from claim "
        "dispositions and phase dependencies",
    "director_resolve.orchestration":
        "engine-authored: the dispatch record for the beat (design note 19)",

    # --- character --------------------------------------------------------
    # RETIRED 2026-08-30, both groups, and both kept on the model with empty
    # defaults so stored variants parse and old turns replay. The reasoning
    # and the measurements are in
    # tests/data/prompt_cards_presplit/EXPECTED_DIVERGENCE.json under
    # `prompts.character`.
    "character.observations_used":
        "evidence arrays retired 2026-08-30; perception isolates the character "
        "by construction, so the citation had no reader",
    "character.present_evidence_used":
        "evidence arrays retired 2026-08-30 (see EXPECTED_DIVERGENCE)",
    "character.memory_evidence_used":
        "evidence arrays retired 2026-08-30 (see EXPECTED_DIVERGENCE)",
    "character.considered_responses":
        "deliberation field retired 2026-08-30: filled 59% of the time across "
        "384 results and read by nothing",
    "character.response_candidates":
        "deliberation field retired 2026-08-30: every reader took only the "
        "selected entry, and both used parts are now derived",
    # MIRRORS, not channels. agents/common._sync_sequence_mirrors recomputes
    # all three FROM `sequence` after validation; a model that writes them
    # instead is tolerated (readers fall back) but never asked, because
    # `sequence` plus a mirror of it was adjudicated, perceived and narrated
    # twice on the real validated path (collapse_duplicate_events).
    "character.speech":
        "derived from `sequence` by _sync_sequence_mirrors; asking for both "
        "duplicates one declared act",
    "character.action":
        "derived from `sequence` by _sync_sequence_mirrors",
    "character.actions":
        "derived from `sequence` by _sync_sequence_mirrors",
    # PUBLISHED CONDITIONALLY, and that is the design. agents/character.py
    # appends the drive_shift instruction ONLY inside an engine-opened rupture
    # window, so a drive cannot flip-flop turn to turn; the base contract
    # documenting it would be the flip-flop.
    "character.drive_shift":
        "asked only inside an engine-opened rupture window "
        "(agents/character.py), never in the base contract",

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


def _template(step, pid):
    """The JSON field list a template stage ends with, and nothing before it.

    Anchored at the marker rather than taking the whole line, because the
    character sheet's lead-in prose shares that line and names `speech` --
    which is a derived mirror, not a field the model fills. Counting the
    prose would make this test pass on exactly the arrangement it exists to
    catch.
    """
    body = DEFAULT_PROMPTS[pid]
    index = body.rfind(_SHAPE_MARKER)
    assert index >= 0, (
        f"{step}: no {_SHAPE_MARKER!r} in its assembled prompt. Either the "
        "stage stopped publishing an output template -- which is the defect "
        "this file guards -- or the marker was reworded and this test needs "
        "to learn the new one.")
    end = body.find("\n", index)
    return body[index:] if end < 0 else body[index:end]


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


@pytest.mark.parametrize("step", SHEET_STAGES)
def test_every_specialist_field_is_asked_for_somewhere_in_its_sheet(step):
    model = schemas.SCHEMA_MAP[step]
    unpublished = [
        path for path, name in _field_paths(model)
        if not _names(DEFAULT_PROMPTS[step], name)
        and f"{step}.{path}" not in UNPUBLISHED
    ]
    assert not unpublished, (
        f"{step}: {unpublished} are fields no chunk of the assembled sheet "
        "names. `CourierOp.freight` sat here -- a whole economy path "
        "(world/charter_runtime.load_caravan_freight) fed by a field no "
        "prompt asked for. Publish it in BOTH packs or record why not.")


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
    for step in SHEET_STAGES:
        body = DEFAULT_PROMPTS[step]
        for path, name in _field_paths(schemas.SCHEMA_MAP[step]):
            live[f"{step}.{path}"] = _names(body, name)

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


def test_the_two_fields_this_file_was_written_for_are_published():
    """The regression, stated as itself.

    Both were asked for BY NAME AND SHAPE in a prose-duty chunk of the prose
    author's own sheet -- `travel_interrupted` in 10_travel.txt, which is the
    only way a walk already under way can be stopped, and `thoughts_omitted`
    in 04.txt, which is the only thing that tells an honestly interior beat
    apart from a beat that lost its changes -- and neither appeared in the
    template that follows them.
    """
    template = _template("director_resolve", "director_resolve_lean")
    assert "travel_interrupted" in template
    assert "thoughts_omitted" in template


def test_caravan_freight_is_published_to_the_hand_that_writes_it():
    """`freight` is the only field of CourierOp that moves real stock, and it
    was asked for nowhere. The three keys are a closed set the ENGINE owns
    (world/charter_runtime.load_caravan_freight reads exactly `from_holder`,
    `stock` and `wants`), which is the kind of vocabulary that SHOULD be
    published rather than guessed at."""
    sheet = DEFAULT_PROMPTS["director_social"]
    for token in ("freight", "from_holder", "stock", "wants"):
        assert token in sheet, token
