"""Deterministic WP-04 Play evidence capture.

The complete capture journeys are added as the Play browser contract closes.
Until then this entrypoint refuses to publish partial evidence.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    print("WP-04 Play evidence is not qualified yet.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
