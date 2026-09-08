"""What one beat spends re-normalizing character cards.

Review 2026-09-07 C14. `normalize_character_data` rebuilds the whole default
tree and recursively merges the card over it, and thirty-nine accessors call it
to read ONE field -- so a reader that wants a name, an appearance and a sense
list pays three full normalizations of the same card. Three shapes repeat every
turn:

  cast_scene_context      eight card reads per cast row, twice a turn
  cast_spelling_policy    two per cast row, seven-plus times a turn
  character_step          fifty-nine card reads for one mind, once per
                          character per beat

Each is timed in BOTH shapes, in one process, so the numbers are comparable:
`per read` is what the code did before C14 (parse the row, then let every
accessor normalize again), `once` is what it does now.

`once` is NOT the same shape at all three rows, and the difference is the
saving. `cast_scene_context` and `cast_spelling_policy` are handed cast rows
and read the memo, so a warm memo makes them nearly free. `character_step` is
NOT: it takes the parsed sheet from `scene.sheet_state` (it needs the stored
state beside the card) and normalizes that ONCE, so it still pays one full
normalization per beat and the memo never enters. Timed against a warm memo
this row reported 250.8x on chat 117; timed as the code is, it is 45-50x
across runs -- 160.4 ms of fifty-nine re-normalizations down to 3.6 ms of one
(chat 114, 47.7x: 224.7 -> 4.7 ms). The row below times the shape the code
actually has.

WHAT C14 DID NOT TOUCH, AND IT IS THE LARGER HALF. `scene.sheet_state` still
hands back a RAW parse at thirteen call sites, eleven of them in
`agents/perception.py`, and each of those blocks then pays about eight
`character_name` plus `character_identity`, `character_room`, `senses_of` and
two `_sense_card` on it. The reason is not oversight: `senses_of` and its three
siblings ask which KIND of card they hold by looking for a section only a
legacy card has, and a normalized card answers differently -- pinned by
`tests/test_character_schema.py::TestOneNormalizationPerCard`. Measured on
chat 117: one such block 35.7 ms before this patch and 35.1 ms after, so ten of
them (about one perception stage over a one-row cast) stay at ~0.35 s. Closing
it means giving those four dispatchers a kind-independent read, which is a
behaviour change, not a memo.

Run it against a COPY of a story database. It reads only `characters` and
`chat_chars`, never a `providers` row, and makes no model call:

    .venv/bin/python tools/bench/sheet_normalization.py <db> <chat_id>
"""

import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from agents.common import cast_spelling_policy                    # noqa: E402
from story import character_schema as cs                          # noqa: E402
from story.scene import cast_scene_context, senses_as_text        # noqa: E402

#: The accessors `character_step` calls on its card, in the counts it calls
#: them (38 of the 59 reads are `character_name`).
STEP_READS = ([cs.character_name] * 38) + [
    cs.character_psychology, cs.character_senses, cs.character_extra_parts,
    cs.character_standing_intentions, cs.character_public_history,
    cs.character_curiosity, cs.character_voice, cs.character_interoception,
    cs.character_abilities, cs.character_embodiment_capabilities,
    cs.character_projects, cs.character_tier, cs.character_temperature,
    cs.character_sampler, cs.character_appearance,
]

#: The eight `cast_scene_context` takes beside the identity block.
CONTEXT_READS = [
    cs.character_extra_parts, cs.character_name, cs.character_appearance,
    cs.character_initial_outfit, cs.character_abilities,
    cs.character_public_history, cs.character_opening_context,
]


def _cast(db, chat_id):
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT cc.char_id AS id, COALESCE(cc.sheet, ch.sheet) AS sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=?", (chat_id,)).fetchall()
    return [{"id": int(r["id"]), "sheet": r["sheet"]} for r in rows]


def _per_read(cast, readers):
    """The pre-C14 shape: parse the row, then let every accessor normalize."""
    for row in cast:
        sheet = json.loads(row["sheet"])
        for reader in readers:
            reader(sheet)
        senses_as_text(cs.character_senses(sheet))


def _once(cast, readers):
    """The C14 shape for a reader handed cast ROWS: read the memo, then the
    same accessors, which recognise the product and do nothing."""
    for row in cast:
        sheet = cs.normalized_character_from_text(row["sheet"])
        for reader in readers:
            reader(sheet)
        senses_as_text(cs.character_senses(sheet))


def _once_unmemoised(cast, readers):
    """The C14 shape for `character_step`: `sheet_state` hands back a raw
    parse (the stored state comes with it), so the one normalization is paid
    in full every beat and the text memo is not involved. See the note in the
    module docstring -- timing this row against the memo overstates it."""
    for row in cast:
        sheet = cs.normalize_character_data(json.loads(row["sheet"]))
        for reader in readers:
            reader(sheet)
        senses_as_text(cs.character_senses(sheet))


def _time(fn, n):
    fn()                                       # warm the interpreter, not the memo
    start = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - start) / n * 1000.0


def main():
    db, chat_id = sys.argv[1], int(sys.argv[2])
    cast = _cast(db, chat_id)
    print("cast rows: %d, sheet bytes: %s"
          % (len(cast), [len(row["sheet"] or "") for row in cast]))
    rows = [
        ("cast_scene_context",
         lambda: _per_read(cast, CONTEXT_READS),
         lambda: cast_scene_context(cast)),
        ("cast_spelling_policy",
         lambda: _per_read(cast, [cs.character_name]),
         lambda: cast_spelling_policy(cast)),
        ("character_step reads",
         lambda: _per_read(cast, STEP_READS),
         lambda: _once_unmemoised(cast, STEP_READS)),
    ]
    for label, old, new in rows:
        cs._normalized_from_text.cache_clear()
        before = _time(old, 10)
        cs._normalized_from_text.cache_clear()
        after = _time(new, 10)
        print("%-22s per read %9.2f ms   once %9.2f ms   %5.1fx"
              % (label, before, after, before / after if after else 0.0))


if __name__ == "__main__":
    main()
