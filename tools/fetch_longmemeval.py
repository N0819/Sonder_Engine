#!/usr/bin/env python3
"""Download LongMemEval to a scratch directory.

Kept as a fetch script rather than vendored data for two reasons: the full
haystack variant is 277 MB, and a benchmark that lives in this repository is
one somebody will eventually edit. The point of this instrument is that its
questions were written by people who have never seen this engine, and that
property survives exactly as long as the file is not ours to change.

Licence: MIT (`xiaowu0162/longmemeval-cleaned`). The V2 release is Apache-2.0.
LoCoMo, the other obvious candidate, is CC BY-NC 4.0 -- usable for measurement
here, but a redistribution question if it ever entered this repository, which
is why this tool does not fetch it.

Variants:
    oracle       10,960 turns total, evidence sessions only. 500 questions,
                 no distractors. Fast, and too easy on its own -- use it to
                 prove a pipeline works, not to believe a number.
    s_cleaned    ~494 turns PER RECORD with realistic distractors. This is
                 the honest setting.
    m_cleaned    the 1.5M-token haystack. Not needed until something scores
                 well on s_cleaned.

Usage:
    python3 tools/fetch_longmemeval.py --out /tmp/lme [--variant oracle]
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

BASE = ("https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned"
        "/resolve/main")

VARIANTS = {
    "oracle": "longmemeval_oracle.json",
    "s_cleaned": "longmemeval_s_cleaned.json",
    "m_cleaned": "longmemeval_m_cleaned.json",
}


def fetch(variant, out_dir):
    name = VARIANTS[variant]
    dest = Path(out_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / name
    if target.exists():
        print(f"already present: {target} ({target.stat().st_size/1e6:.1f} MB)")
        return target
    url = f"{BASE}/{name}"
    print(f"fetching {url}")
    urllib.request.urlretrieve(url, target)
    print(f"wrote {target} ({target.stat().st_size/1e6:.1f} MB)")
    return target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="oracle")
    args = ap.parse_args()
    fetch(args.variant, args.out)


if __name__ == "__main__":
    main()
