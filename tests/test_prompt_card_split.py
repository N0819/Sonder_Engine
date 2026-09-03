"""The prompt-card split moved text. It did not change text.

`language_packs/<id>/cards/system_prompts.json` used to be one JSON document
holding 414 KB (en) / 525 KB (ja) of prompt prose as escaped strings. It is
now an index of `{"$text": "<path>"}` references plus a sibling directory of
per-prompt `.txt` files. `language_runtime/card_source.py` states the format.

These tests are the standing proof that the move was only a move, plus the
guards that keep the layout from decaying back. The load-bearing one is
`test_assembled_card_matches_the_pre_split_reference`: it compares the
assembled card against `tests/data/prompt_cards_presplit/{en,ja}.json`, the
byte-for-byte pre-split card files, committed in the split commit and NEVER
regenerated. A later prompt edit is legitimate and must cost one line in
`EXPECTED_DIVERGENCE.json` naming the leaf it changed -- the same ledger
discipline `tools/project_check.py` applies to `translation_exceptions.json`.
That is what keeps this test meaningful after the monolith is gone: the
reference is immutable, and drift from it is ENUMERATED rather than
re-baselined. An accidental whitespace strip has no ledger line, so it is red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from language_runtime import card_source, raw_card
from language_runtime.card_source import (
    canonical_part_path,
    card_parts_dir,
    decode_part,
    encode_part,
    is_part_leaf,
    part_plan,
    read_card_source,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "tests" / "data" / "prompt_cards_presplit"
CARD = "system_prompts"
LANGUAGES = ("en", "ja")

#: How many part files the layout holds. Asserted alongside the stronger
#: `on_disk == claimed`, which it does not replace: that one proves the index
#: and the directory agree, and this one is what fails when they agree because
#: BOTH lost the same file. It moves when a prompt or fragment is added, and
#: the move belongs in the same commit as the addition.
#: 111 at the split (2026-08-29); 112 since `card_person_note` (2026-08-30).
PART_COUNT = 111   # +1 (2026-09-01): director_note.txt, the specialists' one
                   # statement about the Director's ruling channel;
                   # -2 (2026-09-04): mapping_stage and mapping_commit,
                   # retired with the mapping model; -2 (2026-09-04): the
                   # offscreen hand's core and its reactive-plan chunk;
                   # +2 (2026-09-04): story_planner and charter_planner,
                   # the Writers' Room's author and its delegate


def _pack_dir(language: str) -> Path:
    return ROOT / "language_packs" / language


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


def _expected_divergence() -> dict:
    text = (REFERENCE_DIR / "EXPECTED_DIVERGENCE.json").read_text(
        encoding="utf-8")
    ledger = json.loads(text)
    assert isinstance(ledger, dict), "the divergence ledger must be an object"
    for path, reason in ledger.items():
        assert isinstance(reason, str) and reason.strip(), (
            f"{path} is listed as a deliberate divergence with no reason; a "
            "ledger entry that says nothing is a re-baseline in disguise")
    return ledger


@pytest.mark.parametrize("language", LANGUAGES)
def test_assembled_card_matches_the_pre_split_reference(language):
    """The refactor moved text; it did not change text.

    Every later prompt edit must name the leaf it changes, in the same
    commit, so a diff that was meant to be a move can never be read as an
    edit -- and so that a silently stripped trailing space (there is a
    load-bearing one at `prose_author_sheet[20]`) cannot pass as one.
    """
    reference = json.loads(
        (REFERENCE_DIR / f"{language}.json").read_text(encoding="utf-8"))
    assembled = read_card_source(_pack_dir(language), CARD)
    ledger = _expected_divergence()

    before = dict(_leaves(reference))
    after = dict(_leaves(assembled))

    unexplained_missing = sorted(
        _dotted(path) for path in before if path not in after)
    unexplained_missing = [p for p in unexplained_missing if p not in ledger]
    assert not unexplained_missing, (
        f"{language}: leaves the pre-split card had and the assembled card "
        f"does not: {unexplained_missing[:8]}")

    unexplained_added = sorted(
        _dotted(path) for path in after if path not in before)
    unexplained_added = [p for p in unexplained_added if p not in ledger]
    assert not unexplained_added, (
        f"{language}: leaves the assembled card has and the pre-split card "
        f"did not: {unexplained_added[:8]}")

    changed = []
    for path, value in before.items():
        if path not in after:
            continue
        dotted = _dotted(path)
        if after[path] != value and dotted not in ledger:
            changed.append(dotted)
    assert not changed, (
        f"{language}: {len(changed)} leaves differ from the pre-split card, "
        f"starting at {changed[:6]}. If an edit was intended, add each path "
        f"to {REFERENCE_DIR.name}/EXPECTED_DIVERGENCE.json with a reason, in "
        "the same commit as the edit.")


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_card_still_loads_and_publishes_every_prompt(language):
    """Assembly is upstream of the loader, so prove the loader still sees it."""
    from language_runtime import installed_language_packs

    pack = installed_language_packs()[language]
    card = pack.card(CARD)
    assert len(card["prompts"]) == 36
    assert len(card["specialists"]) == 5
    assert len(card["prose_author_sheet"]) == 28
    # Fragments resolve AFTER assembly, so the loaded card must carry none.
    # (The loaded card is deeply frozen, so walk it rather than serialize it.)
    unresolved = [_dotted(path) for path, value in _leaves(card)
                  if isinstance(value, str) and "{{fragment" in value]
    assert not unresolved, unresolved


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_part_file_is_claimed_by_the_index(language):
    """A `.txt` nobody references is a prompt no model will ever be sent.

    It is the one fault that would otherwise be silent: the pack loads, the
    file is on disk, the author believes it shipped. `expand_card_parts`
    fails the load on it; this says so at the file layer too.
    """
    parts_dir = card_parts_dir(_pack_dir(language), CARD)
    on_disk = {path.relative_to(parts_dir).as_posix()
               for path in parts_dir.rglob("*.txt")}
    index = json.loads(
        (_pack_dir(language) / "cards" / f"{CARD}.json").read_text("utf-8"))
    claimed = {node["$text"] for node in _reference_nodes(index)}
    assert on_disk == claimed, (
        f"{language}: unclaimed {sorted(on_disk - claimed)[:5]}, "
        f"missing {sorted(claimed - on_disk)[:5]}")
    assert len(claimed) == PART_COUNT


def _reference_nodes(value):
    if isinstance(value, dict):
        if "$text" in value:
            yield value
            return
        for child in value.values():
            yield from _reference_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _reference_nodes(child)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_reference_resolves_and_is_canonically_named(language):
    """The index does not merely permit the layout, it asserts it.

    A hand-edited path that still resolves would make the layout advisory,
    and the next person to move a file would have two truths to keep level.
    """
    assembled = read_card_source(_pack_dir(language), CARD)
    plan = part_plan(assembled)
    assert len(plan) == PART_COUNT
    index = json.loads(
        (_pack_dir(language) / "cards" / f"{CARD}.json").read_text("utf-8"))
    for leaf_path, rel, _text in plan:
        node = index
        for segment in leaf_path:
            node = node[segment]
        assert node == {"$text": rel}, (
            f"{language}: {_dotted(leaf_path)} references {node}, not {rel}")
        assert (card_parts_dir(_pack_dir(language), CARD)
                / rel).is_file(), f"{language}: {rel} is missing"


@pytest.mark.parametrize("language", LANGUAGES)
def test_part_files_are_utf8_lf_nonempty_no_bom(language):
    """Windows checkouts and truncation, caught at the file rather than in a
    model's behaviour fifty beats later."""
    parts_dir = card_parts_dir(_pack_dir(language), CARD)
    for path in sorted(parts_dir.rglob("*.txt")):
        data = path.read_bytes()
        rel = path.relative_to(parts_dir).as_posix()
        assert data, f"{language}/{rel} is a zero-byte file"
        assert b"\r" not in data, f"{language}/{rel} carries a carriage return"
        assert not data.startswith(b"\xef\xbb\xbf"), f"{language}/{rel} has a BOM"
        # NOT `text.strip()`: `prose_author_sheet[16][1]` is genuinely a
        # single newline and nothing else, in both packs -- a spacer between
        # two segments of a sheet built by bare `"".join`. It is load-bearing
        # exactly because it is whitespace, which is also why an editor set
        # to trim trailing whitespace would empty this file; that fails the
        # load loudly rather than silently closing a paragraph break.
        assert decode_part(data, rel)


@pytest.mark.parametrize("language", LANGUAGES)
def test_part_files_are_in_canonical_written_form(language):
    """`write(read(x))` reproduces the on-disk bytes exactly.

    The strict half of the tolerant-reader/strict-checker pair. The reader
    forgives a missing final newline, because an editor adding one back is
    the common accident and must not change a prompt; nothing may forgive it
    on disk, or the convention that makes that accident harmless erodes. This
    is also the guard on the two Japanese-pack tools, which write through
    `write_card_source`.
    """
    parts_dir = card_parts_dir(_pack_dir(language), CARD)
    for path in sorted(parts_dir.rglob("*.txt")):
        data = path.read_bytes()
        rel = path.relative_to(parts_dir).as_posix()
        assert encode_part(decode_part(data, rel)) == data, (
            f"{language}/{rel} is not in canonical written form (exactly one "
            "trailing newline beyond the leaf's own text)")


def test_en_and_ja_declare_the_same_part_paths():
    """Closes a blind spot the loader structurally cannot see.

    `_leaf_paths` treats `prose_author_sheet` as ONE path, so a pack shipping
    27 segments instead of 28 passes the loader's card-parity comparison
    today. The file layer sees every part, and a missing segment there is
    a missing paragraph in an assembled sheet.
    """
    paths = {language: {rel for _leaf, rel, _text
                        in part_plan(read_card_source(_pack_dir(language), CARD))}
             for language in LANGUAGES}
    assert paths["en"] == paths["ja"], (
        f"only in en: {sorted(paths['en'] - paths['ja'])[:8]}; "
        f"only in ja: {sorted(paths['ja'] - paths['en'])[:8]}")
    assert len(paths["en"]) == PART_COUNT


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_assembled_sheet_id_has_a_part_file(language):
    """The `director_spatial` drift class, at the file layer.

    Seven prompt ids are BUILT from specialists/`prose_author_sheet` and never
    stored. A split that gives every prompt id a file of its own is exactly
    the shape that re-creates one sheet with two spellings -- and the stored
    English one was 1,518 characters short of its own assembly while the
    prompt editor showed it as the sheet.
    """
    from llm.prompts import ASSEMBLED_SHEET_IDS

    parts_dir = card_parts_dir(_pack_dir(language), CARD)
    for pid in sorted(ASSEMBLED_SHEET_IDS):
        assert not (parts_dir / "prompts" / f"{pid}.txt").exists(), (
            f"{language}: prompts/{pid}.txt exists, but {pid} is assembled "
            "from its parts and must have no body of its own")
    assert not set(read_card_source(_pack_dir(language), CARD)["prompts"]
                   ) & set(ASSEMBLED_SHEET_IDS)


def test_the_duplicated_prose_author_tail_stays_duplicated():
    """`prose_author_sheet[27][1]` is byte-identical to
    `prose_author_output_shape`, and they get two files.

    Deduping them behind a shared reference is a behaviour change wearing a
    refactor's clothes: the two are read by different assemblies and either
    may legitimately change without the other. This asserts the current fact
    so that a future divergence is a decision somebody made, not a surprise.
    """
    card = raw_card("en")
    assert card["prose_author_sheet"][27][1] == card["prose_author_output_shape"]


def test_a_missing_part_file_fails_the_load_rather_than_shortening_a_prompt(
        tmp_path):
    """The floor: there is no path on which a lost part yields a short sheet.

    A truncated prompt loads, runs, and shows up as a model behaving oddly
    many beats later. A pack that refuses to load is a line in a log.
    """
    pack = tmp_path / "en"
    (pack / "cards").mkdir(parents=True)
    (pack / "cards" / "demo.json").write_text(
        json.dumps({"prompts": {"a": {"$text": "prompts/a.txt"}}}),
        encoding="utf-8")
    parts = pack / "cards" / "demo"
    (parts / "prompts").mkdir(parents=True)
    (parts / "prompts" / "a.txt").write_bytes(encode_part("BODY"))
    assert read_card_source(pack, "demo") == {"prompts": {"a": "BODY"}}

    (parts / "prompts" / "a.txt").unlink()
    with pytest.raises(card_source.CardSourceError, match="missing part file"):
        read_card_source(pack, "demo")

    (parts / "prompts" / "a.txt").write_bytes(b"")
    with pytest.raises(card_source.CardSourceError, match="empty"):
        read_card_source(pack, "demo")

    (parts / "prompts" / "a.txt").write_bytes(b"BODY\r\n")
    with pytest.raises(card_source.CardSourceError, match="carriage return"):
        read_card_source(pack, "demo")

    (parts / "prompts" / "a.txt").write_bytes(b"\xef\xbb\xbfBODY\n")
    with pytest.raises(card_source.CardSourceError, match="byte-order mark"):
        read_card_source(pack, "demo")

    (parts / "prompts" / "a.txt").write_bytes(encode_part("BODY"))
    (parts / "prompts" / "orphan.txt").write_bytes(encode_part("NEVER SHIPPED"))
    with pytest.raises(card_source.CardSourceError, match="no reference claims"):
        read_card_source(pack, "demo")


def test_a_reference_may_not_escape_the_parts_directory(tmp_path):
    """Untrusted-pack hygiene: a downloaded pack is data, and data does not
    get to name a path outside its own directory."""
    pack = tmp_path / "en"
    (pack / "cards").mkdir(parents=True)
    (pack / "cards" / "demo.json").write_text(
        json.dumps({"prompts": {"a": {"$text": "../../../etc/passwd"}}}),
        encoding="utf-8")
    with pytest.raises(card_source.CardSourceError, match="escapes"):
        read_card_source(pack, "demo")


def test_a_reference_at_a_non_canonical_path_is_refused(tmp_path):
    pack = tmp_path / "en"
    (pack / "cards").mkdir(parents=True)
    (pack / "cards" / "demo.json").write_text(
        json.dumps({"prompts": {"a": {"$text": "prompts/elsewhere.txt"}}}),
        encoding="utf-8")
    parts = pack / "cards" / "demo" / "prompts"
    parts.mkdir(parents=True)
    (parts / "elsewhere.txt").write_bytes(encode_part("BODY"))
    with pytest.raises(card_source.CardSourceError, match="canonical path"):
        read_card_source(pack, "demo")


def test_a_card_with_no_parts_passes_straight_through(tmp_path):
    """The three unsplit cards need no special case, and a future split of
    one needs no loader change."""
    pack = tmp_path / "en"
    (pack / "cards").mkdir(parents=True)
    body = {"words": ["a", "b"], "table": {"x": {"$type": "regex"}}}
    (pack / "cards" / "plain.json").write_text(
        json.dumps(body), encoding="utf-8")
    assert read_card_source(pack, "plain") == body


def test_canonical_part_path_covers_exactly_the_five_prose_shapes():
    """The path function is total and has no discretion in it."""
    assert canonical_part_path(("prompts", "narrator")) == "prompts/narrator.txt"
    assert canonical_part_path(
        ("specialists", "body", "core")) == "specialists/body/core.txt"
    assert canonical_part_path(("specialists", "body", "chunks", "attire")) == (
        "specialists/body/chunks/attire.txt")
    assert canonical_part_path(("prose_author_sheet", 0, 1), "voices") == (
        "prose_author_sheet/00_voices.txt")
    assert canonical_part_path(("prose_author_sheet", 27, 1)) == (
        "prose_author_sheet/27.txt")
    assert canonical_part_path(("nsfw_overlay",)) == "nsfw_overlay.txt"

    # Structure does not move.
    assert not is_part_leaf(("specialists", "body", "order", 0))
    assert not is_part_leaf(("specialists", "body", "nsfw"))
    assert not is_part_leaf(("nsfw_prompt_ids", 0))
    assert not is_part_leaf(("prose_author_sheet", 0, 0))
    assert not is_part_leaf(("character_block_keys", 0, 0))


def test_the_sheet_is_named_index_first_because_the_index_is_the_identity():
    """`planning_need` is the gate name at BOTH 11 and 15, and 12 of the 28
    segments have no name at all. Naming key-first would collide and would
    not sort into assembly order."""
    card = raw_card("en")
    keys = [entry[0] for entry in card["prose_author_sheet"]]
    assert keys[11] == keys[15] == "planning_need"
    assert keys.count(None) == 12
    names = [rel for leaf, rel, _text in part_plan(card)
             if leaf[0] == "prose_author_sheet"]
    assert names == sorted(names), "the sheet's files must sort into join order"
    assert len(set(names)) == 28
