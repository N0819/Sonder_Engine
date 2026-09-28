"""Prompt cards whose prose lives in per-prompt files beside the index.

A card on disk is TWO things. `cards/<name>.json` is the INDEX: the shape a
reviewer reads -- assembly order, gate names, flags, allow-lists -- plus one
`{"$text": "<relative path>"}` reference wherever a prose leaf used to sit.
`cards/<name>/` is the parts directory: one UTF-8 `.txt` file per prose leaf,
which is what a human opens to edit a prompt.

Why: `system_prompts.json` reached 414 KB (English) and 525 KB (Japanese) as
single JSON documents whose values are 62 KB prompt strings with escaped
newlines. Editing one meant a surgical raw-text replace against an escaped
blob, which is slow, unreviewable in a diff, and the exact shape that turns a
one-word prompt fix into an accidental reflow of the other 62,000 characters.
Splitting moves WHERE the text lives and nothing else: the assembled card is
byte-identical to what the monolith produced, and `tests/
test_prompt_card_split.py` holds it to that against a committed pre-split
reference forever.

The file format, and the one convention in it: a part file is the leaf's exact
text plus a single trailing newline. Reading strips exactly one trailing
newline if present, and nothing else. That pairing exists because the dominant
real-world corruption is an editor adding a final newline on save -- of the
226 English leaves, 163 end with no newline at all, so a no-convention scheme
would let VS Code's `files.insertFinalNewline` silently change the majority of
the prompts in the engine. Under this convention every file already ends with
a newline, so the editor's "fix" is a no-op. The READER is deliberately
tolerant of a missing final newline (a stripped one decodes identically);
`check_prompt_card_parts` and `test_part_files_are_in_canonical_written_form`
are the strict half that keep the on-disk form canonical.

What fails, and how loudly: every fault below raises `CardSourceError`, which
`language_runtime._read_card` turns into `LanguagePackError` at `_load_pack`.
That propagates out of `installed_language_packs()`, is negative-cached, and
turns every subsequent `get_prompt` into the same error -- the server does not
start and the suite does not collect. There is deliberately NO path on which a
missing, empty or unreadable part file yields a SHORT prompt: a truncated
sheet is a silent behaviour change read by every story, which is worse than
not starting.

  * a reference whose file is missing;
  * a reference whose path is not `canonical_part_path` for its own leaf --
    the index does not merely permit the layout, it asserts it, so the paths
    stay greppable while drift stays impossible;
  * a reference path that escapes the parts directory (untrusted-pack
    hygiene: a downloaded pack must not read `../../../etc/passwd`);
  * a `.txt` file no reference claims. This is the new-prompt-written-but-
    never-shipped case, and it is the one fault that would otherwise be
    invisible: the pack loads, the prompt exists on disk, and no model ever
    sees it;
  * a part that decodes empty (zero leaves are empty today, so an empty file
    is always a truncation), carries a BOM, or contains a carriage return.

Cards with no `$text` anywhere and no parts directory pass through unchanged,
so `authoring`/`compositor`/`linguistics` need no special-casing and a future
split of one needs no loader change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


#: One extension, and not `.md`. The content is ALL-CAPS section headers,
#: `{...}` JSON shape blocks and enum alternations -- not Markdown. `.md`
#: invites exactly the tooling that destroys this data (Prettier reflow,
#: markdownlint list renumbering, trailing-whitespace trim), and a previewer
#: renders `{"reactors": [int]}` as garbage. `.txt` triggers no formatter.
PART_SUFFIX = ".txt"

#: The reference key. Deliberately NOT `$type`: `_leaf_paths` treats a Mapping
#: carrying `$type` as an opaque leaf, so spelling it that way would hide the
#: split from the loader's en/ja parity comparison.
PART_REF = "$text"

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class CardSourceError(ValueError):
    """A card index and its parts directory disagree, or a part is unreadable."""


def card_parts_dir(pack_dir: Path, card_name: str) -> Path:
    """The directory holding one card's part files."""
    return Path(pack_dir) / "cards" / card_name


def _component(value: Any, leaf_path: tuple) -> str:
    name = str(value)
    if not _IDENTIFIER.fullmatch(name):
        raise CardSourceError(
            f"{_render_path(leaf_path)}: {name!r} is not usable as a file "
            f"name; part paths are built from identifiers only")
    return name


def _render_path(leaf_path: tuple) -> str:
    out = ""
    for segment in leaf_path:
        if isinstance(segment, int):
            out += f"[{segment}]"
        else:
            out += f".{segment}" if out else str(segment)
    return out or "<root>"


def is_part_leaf(leaf_path: tuple) -> bool:
    """Is this leaf path one of the shapes that becomes a file?

    Only prose moves. Structure -- `specialists.<n>.order` (the authoritative
    channel order the encoder's chunks follow, which is deliberately not
    `chunks` insertion order: `contact` differs) and `nsfw_prompt_ids` (the one
    roster of prompt ids the adult overlay is appended to) -- stays inline,
    because a list in a text file needs a parser and gains nothing.
    """
    if len(leaf_path) == 1:
        return isinstance(leaf_path[0], str)
    if len(leaf_path) == 2:
        # `prose_contract.<sheet>` and `jev_questions.<channel>` are the
        # prose-contract Director's families (agents/director_prose.py): its
        # sheets, and one decision-model question per engine channel. Its
        # encoder's own card is `encoder.<name>`: the core, one chunk per
        # channel, and `<channel>__<part>` for a part of a big channel that
        # ships only when the decision model says the beat needs it.
        # `affect_appraisal.<question>` is the decision model's appraisal of
        # an event or a recalled memory (mind/affect_appraisal.py); its answer
        # labels, `affect_appraisal.options.*`, are short and stay inline.
        # The bare character contract's families (agents/character_bare.py):
        # `character_bare.<module>`, a short section of the card shipped only
        # when a detector says the moment calls for it, and
        # `character_jev.<question>`, what the decision model asks around the
        # character call; its labels, `character_jev.options.*`, stay inline.
        if leaf_path[0] in ("prompts", "prose_contract",
                            "jev_questions", "encoder", "affect_appraisal",
                            "character_bare", "character_jev"):
            return isinstance(leaf_path[1], str)
        return False
    if len(leaf_path) == 4:
        # `specialists.<hand>.chunks.<channel>`: the spatial hand's room
        # chunks, shipped verbatim by the room designer
        # (`prompts.room_author_prompt`). The hands' cores and every other
        # chunk went with the causal Director on 2026-09-27.
        return (leaf_path[0] == "specialists" and leaf_path[2] == "chunks"
                and isinstance(leaf_path[1], str)
                and isinstance(leaf_path[3], str))
    return False


def canonical_part_path(leaf_path: tuple) -> str:
    """The one file path a given leaf may live at. Total, and no discretion."""
    leaf_path = tuple(leaf_path)
    if not is_part_leaf(leaf_path):
        raise CardSourceError(
            f"{_render_path(leaf_path)} is not a part leaf")
    if len(leaf_path) == 1:
        return f"{_component(leaf_path[0], leaf_path)}{PART_SUFFIX}"
    if len(leaf_path) == 2:
        return (f"{leaf_path[0]}/"
                f"{_component(leaf_path[1], leaf_path)}{PART_SUFFIX}")
    name = _component(leaf_path[1], leaf_path)
    # `chunks/` is kept as a path segment rather than flattened into the
    # specialist directory. It costs one level and buys exact leaf-path
    # correspondence plus immunity to a future chunk named `core`.
    return (f"specialists/{name}/chunks/"
            f"{_component(leaf_path[3], leaf_path)}{PART_SUFFIX}")


def decode_part(data: bytes, where: str) -> str:
    """Decode one part file's bytes into its leaf value."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CardSourceError(f"{where} is not valid UTF-8: {exc}") from exc
    if text.startswith("\ufeff"):
        raise CardSourceError(
            f"{where} begins with a byte-order mark; a BOM would be shipped "
            f"to the model as the first character of the prompt")
    if "\r" in text:
        raise CardSourceError(
            f"{where} contains a carriage return; prompt parts are LF-only "
            f"(see .gitattributes)")
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise CardSourceError(
            f"{where} is empty; no prompt leaf is empty, so an empty part "
            f"file is a truncation")
    return text


def encode_part(text: str) -> bytes:
    """The canonical on-disk bytes for one leaf value."""
    return (text + "\n").encode("utf-8")


def _safe_relative(reference: Any, parts_dir: Path, where: str) -> Path:
    rel = str(reference)
    if not rel or rel.startswith("/") or "\\" in rel:
        raise CardSourceError(f"{where}: unusable part reference {rel!r}")
    parts = rel.split("/")
    if any(segment in ("", ".", "..") for segment in parts):
        raise CardSourceError(
            f"{where}: part reference {rel!r} escapes the parts directory")
    return parts_dir.joinpath(*parts)


def expand_card_parts(index: dict, parts_dir: Path) -> dict:
    """Return the card with every `{"$text": ...}` reference read from disk.

    Key order is preserved, containers are rebuilt mutable, and the result is
    still UNRESOLVED: `{{fragment:...}}` spellings stay exactly as authored,
    because `_resolve_prompt_fragments` runs after this and must be the only
    thing that expands them. Splitting after resolution would re-create the
    seventeen hand-maintained pastes that had already drifted apart once.
    """
    parts_dir = Path(parts_dir)
    consumed: set[Path] = set()

    def read_reference(node: Mapping, leaf_path: tuple) -> str:
        if len(node) != 1:
            raise CardSourceError(
                f"{_render_path(leaf_path)}: a part reference carries only "
                f"{PART_REF!r}, not {sorted(node)}")
        rel = node[PART_REF]
        expected = canonical_part_path(leaf_path)
        # Equality with the canonical path is checked BEFORE the path is
        # built, and doing it in that order is what keeps traversal
        # impossible without a per-reference safety walk: `expected` is
        # assembled from components this module has already matched against
        # `^[a-z][a-z0-9_]*$`, so a reference equal to it cannot escape.
        # `_safe_relative` then runs only on the failing branch, where its
        # more specific message is worth the work.
        if rel != expected:
            where = _render_path(leaf_path)
            _safe_relative(rel, parts_dir, where)
            raise CardSourceError(
                f"{where}: part reference is {rel!r} but this leaf's "
                f"only canonical path is {expected!r}")
        path = parts_dir.joinpath(*expected.split("/"))
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise CardSourceError(
                f"{_render_path(leaf_path)}: missing part file "
                f"{expected}") from exc
        except OSError as exc:
            raise CardSourceError(
                f"{_render_path(leaf_path)}: cannot read part file "
                f"{expected}: {exc}") from exc
        consumed.add(path)
        return decode_part(data, expected)

    def walk(value: Any, leaf_path: tuple) -> Any:
        if isinstance(value, Mapping):
            if PART_REF in value:
                return read_reference(value, leaf_path)
            return {str(key): walk(child, leaf_path + (str(key),))
                    for key, child in value.items()}
        if isinstance(value, list):
            return [walk(child, leaf_path + (index,))
                    for index, child in enumerate(value)]
        return value

    expanded = {str(key): walk(child, (str(key),))
                for key, child in index.items()}

    if not consumed and not parts_dir.is_dir():
        return expanded

    if parts_dir.is_dir():
        # Membership before `is_file()`: the stat is the expensive half and
        # on a healthy pack every file is already consumed, so this pays for
        # 222 stat calls that answer a question nothing asked.
        orphans = sorted(
            path.relative_to(parts_dir).as_posix()
            for path in parts_dir.rglob(f"*{PART_SUFFIX}")
            if path not in consumed and path.is_file())
        if orphans:
            raise CardSourceError(
                "part files no reference claims, so nothing ships them to a "
                "model: " + ", ".join(orphans[:8]))

    _assert_no_surviving_reference(expanded)
    return expanded


def _assert_no_surviving_reference(value: Any, path: tuple = ()) -> None:
    if isinstance(value, Mapping):
        if PART_REF in value:
            raise CardSourceError(
                f"{_render_path(path)}: an unexpanded {PART_REF!r} reference "
                f"survived assembly")
        for key, child in value.items():
            _assert_no_surviving_reference(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_surviving_reference(child, path + (index,))


def read_card_source(pack_dir: Path, card_name: str) -> dict:
    """One card's AUTHORED source: index plus parts, unresolved and mutable.

    This is what a tool or a test that wants to see what a human wrote should
    read. `LanguagePack.card(...)` is the loaded card -- fragments resolved,
    deeply frozen -- and is the wrong artifact for anything auditing the
    authored text, because a fragment appears there seventeen times.
    """
    pack_dir = Path(pack_dir)
    path = pack_dir / "cards" / f"{card_name}.json"
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CardSourceError(f"missing card index: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CardSourceError(f"cannot read card index {path}: {exc}") from exc
    if not isinstance(index, dict):
        raise CardSourceError(f"a card index must be an object: {path}")
    return expand_card_parts(index, card_parts_dir(pack_dir, card_name))


def part_plan(card: dict) -> list[tuple[tuple, str, str]]:
    """`(leaf path, part path, text)` for every prose leaf of an assembled card."""
    plan: list[tuple[tuple, str, str]] = []

    def walk(value: Any, leaf_path: tuple) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                walk(child, leaf_path + (str(key),))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, leaf_path + (index,))
        elif isinstance(value, str) and is_part_leaf(leaf_path):
            plan.append((leaf_path, canonical_part_path(leaf_path), value))

    for key, child in card.items():
        walk(child, (str(key),))
    return plan


def write_card_source(pack_dir: Path, card_name: str, card: dict) -> None:
    """Write one assembled card back out as an index plus part files.

    The inverse of `read_card_source`, and the only supported writer: the two
    Japanese-pack tools go through it so a regenerated or re-translated pack
    lands in the split layout rather than silently re-inlining 500 KB of prose.
    """
    pack_dir = Path(pack_dir)
    parts_dir = card_parts_dir(pack_dir, card_name)
    plan = part_plan(card)

    seen: dict[str, tuple] = {}
    for leaf_path, rel, _text in plan:
        if rel in seen:
            raise CardSourceError(
                f"{_render_path(leaf_path)} and {_render_path(seen[rel])} "
                f"both want the part file {rel}")
        seen[rel] = leaf_path

    index: Any = json.loads(json.dumps(card))
    for leaf_path, rel, _text in plan:
        node = index
        for segment in leaf_path[:-1]:
            node = node[segment]
        node[leaf_path[-1]] = {PART_REF: rel}

    # Replace the parts directory wholesale: a rename that leaves the old file
    # behind would ship as an orphan, and an orphan is a hard load failure
    # rather than a mystery, but only if it is not ALSO still referenced.
    if parts_dir.exists():
        for stale in sorted(parts_dir.rglob(f"*{PART_SUFFIX}")):
            stale.unlink()
    for _leaf_path, rel, text in plan:
        path = parts_dir.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encode_part(text))
    for directory in sorted(
            (p for p in parts_dir.rglob("*") if p.is_dir()),
            key=lambda p: len(p.parts), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()

    target = pack_dir / "cards" / f"{card_name}.json"
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    temp.replace(target)
