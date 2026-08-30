#!/usr/bin/env python3
"""Move prompt-card prose out of the card JSON into per-prompt part files.

A ONE-TIME migration, kept because it is also the proof. The split is a
refactor whose only acceptance criterion is that nothing changed: every
assembled leaf, every prompt body, every scoped specialist sheet and every
prose-author assembly must be byte-identical to what the monolithic card
produced. So the tool has three modes and they run in this order:

  --snapshot FILE   before touching anything. Records, per installed pack:
                    every string leaf of every card by dotted path; every
                    prompt body and complete prompt; `default_prompts_for`;
                    each specialist sheet at full, empty and single-channel
                    scope; and the prose-author sheet at every scope -- each
                    of those twice, with the NSFW overlay off and on.
  --split           writes the parts, re-reads them in-process, and deep-
                    compares against the card it started from. On ANY
                    mismatch it exits non-zero with the tree untouched.
  --verify FILE     reloads the packs from disk in a fresh process and
                    asserts equality with the snapshot. This is the
                    acceptance criterion, executed.

Compare DECODED leaves, never file bytes. The English card's committed JSON
differs from canonical `json.dumps` by exactly four `\\u2014` escapes with
identical parsed values, which is itself the proof that no consumer depends
on the escaping.

Run under `.venv/bin/python`: the system interpreter carries a different
Pydantic and `llm.prompts` imports through it (CLAUDE.md § Commands).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _scratch_database() -> None:
    """Point settings reads at an empty database, not the developer's.

    `get_prompt_body` consults the active preset and the NSFW flag, so a
    snapshot taken against a host's saved preset would not describe the
    shipped prompts at all.
    """
    from core import db

    path = os.path.join(tempfile.mkdtemp(prefix="sonder-split-"), "scratch.db")
    db.configure(path)
    db.init()


def _string_leaves(value, path: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _string_leaves(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _string_leaves(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def snapshot() -> dict:
    """Every value the split is forbidden to change."""
    import language_runtime as lr
    from llm import prompts

    out: dict = {}
    packs = lr.installed_language_packs()
    out["_packs"] = sorted(packs)
    for language, pack in sorted(packs.items()):
        entry: dict = {}
        for card_name in sorted(pack.cards):
            entry[f"card:{card_name}"] = dict(
                _string_leaves(pack.card(card_name)))
        for nsfw in (False, True):
            prompts.nsfw_enabled = (lambda value: (lambda: value))(nsfw)
            tag = "nsfw" if nsfw else "sfw"
            with lr.language_scope(language):
                entry[f"bodies:{tag}"] = {
                    pid: prompts.get_prompt_body(pid, language)
                    for pid in sorted(prompts.DEFAULT_PROMPTS)}
                entry[f"full:{tag}"] = {
                    pid: prompts.get_prompt(pid, language)
                    for pid in sorted(prompts.DEFAULT_PROMPTS)}
                entry[f"defaults:{tag}"] = dict(
                    prompts.default_prompts_for(language))
                card = pack.card("system_prompts")
                sheets = {}
                for name, spec in card["specialists"].items():
                    order = list(spec["order"])
                    sheets[f"{name}|FULL"] = prompts.specialist_prompt(
                        name, order, language)
                    sheets[f"{name}|NONE"] = prompts.specialist_prompt(
                        name, [], language)
                    for channel in order:
                        sheets[f"{name}|{channel}"] = prompts.specialist_prompt(
                            name, [channel], language)
                entry[f"specialists:{tag}"] = sheets
                entry[f"prose:{tag}|None"] = prompts.prose_author_prompt(
                    None, language)
                entry[f"prose:{tag}|all"] = prompts.prose_author_prompt(
                    frozenset(prompts.PROSE_DUTY_CHUNKS), language)
                for duty in prompts.PROSE_DUTY_CHUNKS:
                    entry[f"prose:{tag}|{duty}"] = prompts.prose_author_prompt(
                        frozenset({duty}), language)
        out[language] = entry
    return out


def _write_snapshot(target: Path) -> int:
    _scratch_database()
    data = snapshot()
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8")
    counted = sum(
        len(value) for entry in data.values() if isinstance(entry, dict)
        for value in entry.values() if isinstance(value, dict))
    print(f"snapshot: {len(data['_packs'])} packs, {counted} keyed values "
          f"-> {target}")
    return 0


def _differences(left, right, path: str = "") -> list[str]:
    """Deep, order-sensitive, type-sensitive comparison."""
    if type(left) is not type(right):
        return [f"{path}: {type(left).__name__} became {type(right).__name__}"]
    if isinstance(left, dict):
        out = []
        if list(left) != list(right):
            out.append(f"{path}: key order or key set changed")
        for key in left:
            if key not in right:
                out.append(f"{path}.{key}: gone")
            else:
                out.extend(_differences(left[key], right[key], f"{path}.{key}"))
        out.extend(f"{path}.{key}: added" for key in right if key not in left)
        return out
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{path}: length {len(left)} became {len(right)}"]
        out = []
        for index, (a, b) in enumerate(zip(left, right)):
            out.extend(_differences(a, b, f"{path}[{index}]"))
        return out
    if left != right:
        return [f"{path}: value changed ({len(str(left))} chars -> "
                f"{len(str(right))} chars)"]
    return []


def _split_one(pack_dir: Path, card_name: str) -> int:
    from language_runtime import card_source
    from llm.prompts import ASSEMBLED_SHEET_IDS

    index_path = pack_dir / "cards" / f"{card_name}.json"
    original = json.loads(index_path.read_text(encoding="utf-8"))

    # A part file for an assembled sheet id re-creates the `director_spatial`
    # class: one sheet with two spellings, free to drift, and the stored one
    # was 1,518 characters short of its own assembly.
    stored = set(original.get("prompts") or ()) & set(ASSEMBLED_SHEET_IDS)
    if stored:
        print(f"REFUSED {pack_dir.name}/{card_name}: prompts.{{{','.join(sorted(stored))}}} "
              f"is an ASSEMBLED sheet id and must not be stored as a body")
        return 1

    with tempfile.TemporaryDirectory(prefix="sonder-split-check-") as scratch:
        trial = Path(scratch) / pack_dir.name
        (trial / "cards").mkdir(parents=True)
        (trial / "cards" / f"{card_name}.json").write_text(
            index_path.read_text(encoding="utf-8"), encoding="utf-8")
        card_source.write_card_source(trial, card_name, original)
        rebuilt = card_source.read_card_source(trial, card_name)
        problems = _differences(original, rebuilt, card_name)
        if problems:
            print(f"REFUSED {pack_dir.name}/{card_name}: the split does not "
                  f"round-trip; the tree is untouched.")
            for line in problems[:20]:
                print(f"  - {line}")
            return 1
        parts = sorted(
            path.relative_to(trial / "cards" / card_name).as_posix()
            for path in (trial / "cards" / card_name).rglob("*.txt"))

    card_source.write_card_source(pack_dir, card_name, original)
    landed = card_source.read_card_source(pack_dir, card_name)
    problems = _differences(original, landed, card_name)
    if problems:
        print(f"FAILED {pack_dir.name}/{card_name} after writing: "
              f"{problems[:5]}")
        return 1
    print(f"split {pack_dir.name}/{card_name}: {len(parts)} part files, "
          f"index now {index_path.stat().st_size:,} bytes")
    return 0


def _split(card_name: str) -> int:
    status = 0
    for pack_dir in sorted(p for p in (ROOT / "language_packs").iterdir()
                           if p.is_dir()):
        if not (pack_dir / "cards" / f"{card_name}.json").exists():
            continue
        status |= _split_one(pack_dir, card_name)
    return status


def _verify(reference: Path) -> int:
    _scratch_database()
    import language_runtime as lr

    lr.installed_language_packs(refresh=True)
    expected = json.loads(reference.read_text(encoding="utf-8"))
    # Both sides through the same serialization. The snapshot FILE is written
    # sort_keys=True, so comparing a freshly built dict against it would read
    # its own key ordering as a divergence. Key SETS, list order and every
    # string still compare exactly; card key order is guarded separately, by
    # --split's round-trip and by test_prompt_card_split.
    actual = json.loads(json.dumps(snapshot(), ensure_ascii=False,
                                   sort_keys=True))
    problems = _differences(expected, actual, "snapshot")
    if problems:
        print(f"BYTE IDENTITY FAILED: {len(problems)} divergences")
        for line in problems[:40]:
            print(f"  - {line}")
        return 1
    counted = sum(
        len(value) for entry in expected.values() if isinstance(entry, dict)
        for value in entry.values() if isinstance(value, dict))
    print(f"byte identity holds: {len(expected['_packs'])} packs, "
          f"{counted} keyed values, 0 divergences")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", metavar="FILE")
    parser.add_argument("--split", action="store_true")
    parser.add_argument("--verify", metavar="FILE")
    parser.add_argument("--card", default="system_prompts")
    args = parser.parse_args()
    if not (args.snapshot or args.split or args.verify):
        parser.error("choose --snapshot, --split or --verify")
    status = 0
    if args.snapshot:
        status |= _write_snapshot(Path(args.snapshot))
    if args.split:
        status |= _split(args.card)
    if args.verify:
        status |= _verify(Path(args.verify))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
