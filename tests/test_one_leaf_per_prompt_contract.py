"""One leaf per contract: a rule stated in prompt text is stated ONCE.

Review 2026-09-07 finding B27. `prose_author_sheet[28][1]` and
`prose_author_output_shape` held the same 1,562 bytes in English and the same
1,289 in Japanese -- the prose author's output shape, written out twice, with
a test standing where a single source belonged
(`test_the_duplicated_prose_author_tail_stays_duplicated`: "either may
legitimately change without the other").

They never did change without the other, and the one time somebody edited a
single copy it cost a beat. `ledger_notes` was declared in the schema, the
payload and the sheet's prose, and grok-4.3 emitted zero of them on a live
replay: the OUTPUT SHAPE -- the field list the model is actually handed -- did
not mention it. The resolve prompt reads the SHEET, so the standalone file can
be corrected on its own and the model stays unaware. That is not two contracts
free to differ; it is one contract with two spellings and no mechanism to keep
them equal.

The pack already owns the mechanism. `{{fragment:<name>}}` is resolved at card
load, before anything downstream can read the card
(`language_runtime._resolve_prompt_fragments`), so an embedding is the same
bytes as its fragment by construction and a fragment edit is one edit. The
Japanese pack is why it exists: as hand-maintained pastes, ZERO of seventeen
copies matched their own fragment, because each was translated independently.

THE RULE, in the vocabulary the card already has: no two PROSE LEAVES of a
system-prompt card hold the same text. A prose leaf is `is_part_leaf` -- the
card's own definition of the text that gets a file, which is exactly the text
a model reads. Structure (gate names, `character_block_keys` paths, assembly
`order`) is not a leaf and repeats freely. Measured over both packs, the
byte-duplicates `is_part_leaf` excludes are exactly three: `planning_need`,
the gate key at both `prose_author_sheet[11][0]` and `[15][0]`;
`memory.earlier_in_my_life`; and `perception.sprint_reach`. What it does NOT
exclude is the whitespace-only spacer at `prose_author_sheet[16][1]` -- a lone
newline, a part leaf by the card's own definition, and the one part leaf that
may legitimately have a twin, because a second spacer is what inserting a
chunk group costs when the sheet is assembled by a bare join. So the scan
skips leaves with no words: a leaf that states no contract cannot state one
twice. That is an exclusion stated as a class, not a minimum length.

Scoped to EXACT equality on purpose. Two leaves that teach the same contract
in different words are the wider half of B27 -- the establish sheet's free
copies of the comms, poses, entities and sensory chunks, which teach a
four-rung sound ladder against the engine's six and `{...distance,intensity}`
against `{...db,detail}` -- and merging those changes what a model reads,
which is an owner's call and not a refactor's. This guard holds the half that
is free: bytes that are already identical must be one leaf and a reference.

The instance itself -- the sheet's `{{fragment:...}}` reference, what it
resolves to, and the assembled English sheet still carrying the shape byte for
byte -- is asserted in `tests/test_prompt_card_split.py`, where the
copy-preserving test it replaced lived. This file holds the class alone; a
second copy of that assertion here would be the very thing B27 is about.
"""

from __future__ import annotations

import collections

import pytest

from language_runtime import raw_card
from language_runtime.card_source import is_part_leaf

LANGUAGES = ("en", "ja")


def _leaves(value, path: tuple = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaves(child, path + (index,))
    else:
        yield path, value


def _dotted(path: tuple) -> str:
    out = ""
    for segment in path:
        out += f"[{segment}]" if isinstance(segment, int) else (
            f".{segment}" if out else str(segment))
    return out


def _duplicated_prose_leaves(card) -> dict[str, list[str]]:
    """Prose leaves that hold the same text, keyed by that text.

    `value.strip()` is the whitespace exclusion, stated as a class: a leaf
    with no words states no contract, so it cannot state one twice. It is not
    a minimum length -- there is no number here to tune. The one part leaf it
    covers today is `prose_author_sheet[16][1]`, a lone newline spacer.
    """
    by_text: dict[str, list[str]] = collections.defaultdict(list)
    for path, value in _leaves(card):
        if isinstance(value, str) and value.strip() and is_part_leaf(path):
            by_text[value].append(_dotted(path))
    return {text: paths for text, paths in by_text.items() if len(paths) > 1}


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_two_prose_leaves_hold_the_same_text(language):
    """The class. A second copy of a contract is a second copy free to drift.

    Fails before the fix on `prose_author_sheet[28][1]` /
    `prose_author_output_shape` in both packs, and on any future paste of one
    prompt's words into another.
    """
    duplicated = _duplicated_prose_leaves(raw_card(language))
    assert not duplicated, (
        f"{language}: {len(duplicated)} contract(s) stated in more than one "
        "prose leaf: "
        + "; ".join(" == ".join(paths) for paths in duplicated.values())
        + ". A contract lives in ONE leaf; every other sheet carries "
          "{{fragment:<name>}}, which resolves at card load and is the same "
          "bytes by construction.")


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_second_spacer_is_not_a_second_contract(language):
    """The guard does not fire on a leaf that states nothing (B27 rework).

    `prose_author_sheet[16][1]` is a single newline and IS a part leaf, and
    the sheet is assembled by a bare join, so a spacer is what separating a
    newly inserted chunk group costs. Two of them are identical bytes and no
    contract at all; reporting "stated in more than one prose leaf" about
    them would be a guard firing on valid content. A leaf with words still
    fails, so the exclusion did not hollow the guard out.
    """
    card = raw_card(language)
    card["prose_author_sheet"].append([None, "\n"])
    assert not _duplicated_prose_leaves(card)

    card["prose_author_sheet"].append(
        [None, card["prose_author_output_shape"]])
    assert _duplicated_prose_leaves(card)
