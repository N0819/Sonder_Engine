#!/usr/bin/env python3
"""Which Director output fields does nothing read?

A field the sheet asks for and no module consumes costs three times: the
sentence teaching it, the tokens spent writing it, and the reader's belief that
it matters. `referents[].role` was found this way -- the interpret sheet
publishes a six-value enum for it and `agents/common.resolve_action_referents`
reads `text`, `entity` and `occurrence` and never `role`.

For each field of `DirectorInterpret` / `DirectorResolve`, this looks for a
module that reads it by name. The search is deliberately generous -- any
mention outside tests, tools and the language packs counts -- so a field
reported here is one nothing so much as names.

NOT A VERDICT. Some fields are read through a schema round-trip rather than by
name (`StateDiff` channels reach commit as attributes of a validated model),
and some are diagnostics whose whole job is to be stored. Read the column, then
read the field.

    python3 tools/unread_output_fields.py

Read-only.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def readers(name):
    try:
        out = subprocess.run(
            ["git", "grep", "-l", "-w", name, "--", "*.py",
             ":!tests/*", ":!tools/*", ":!llm/schemas.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
    except Exception:                                    # noqa: BLE001
        return []
    return [f for f in out.stdout.split() if f]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)

    from llm import schemas

    for step in ("director_interpret", "director_resolve"):
        model = schemas.SCHEMA_MAP[step]
        fields = schemas._fields(model) or {}
        unread, thin = [], []
        for name in fields:
            found = readers(name)
            if not found:
                unread.append(name)
            elif len(found) == 1:
                thin.append((name, found[0]))
        print("=== %s (%s): %d fields" % (step, model.__name__, len(fields)))
        if unread:
            print("    NAMED BY NO MODULE:")
            for name in sorted(unread):
                print("      %s" % name)
        if thin:
            print("    read in exactly one module (check it is a real read):")
            for name, where in sorted(thin):
                print("      %-26s %s" % (name, where))
        if not unread and not thin:
            print("    every field is read in two or more modules")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
