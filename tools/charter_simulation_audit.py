#!/usr/bin/env python3
"""Run the expensive Charter population/realism audit on demand.

This is deliberately outside pytest's default ``tests/`` collection.  The
ordinary suite proves the mechanism on a small deterministic institution;
this tool answers the separate questions that require hundreds of bodies,
months of simulated time, social convergence, famine, and replay at scale.
"""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
TEST_SUPPORT = ROOT / "tests"
AUDITS = [
    ROOT / "tools" / "charter_audit_scale.py",
    ROOT / "tools" / "charter_audit_mind.py",
    ROOT / "tools" / "charter_audit_needs.py",
    ROOT / "tools" / "charter_audit_feel.py",
]


def main(argv=None):
    try:
        import pytest
    except ImportError:
        print("Charter audit requires the development test dependencies.",
              file=sys.stderr)
        return 2
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(TEST_SUPPORT))
    args = ["-q", "--durations=30", *(str(path) for path in AUDITS)]
    args.extend(list(argv if argv is not None else sys.argv[1:]))
    return int(pytest.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
