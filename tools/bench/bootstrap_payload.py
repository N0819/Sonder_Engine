"""What `/api/bootstrap` costs, and how much of it repeats.

`boot()` re-runs on every import, save, provider edit and NSFW toggle -- 61
call sites across `static/js` -- so the payload is paid for many times per
session, and the half of it that is the INSTALL's own content (the UI catalog,
every default prompt, the closed vocabularies) is the same bytes every time.
`web/app.py`'s `_INSTALL_BLOCK_KEYS` names that half and `_bootstrap_split`
versions it by a digest of its own content; this prints what the split is
worth on a real database.

Both halves of the claim are printed, because a payload split is only worth
having if the answer is unchanged: the BASELINE row is what the route sent
before the split -- `jsonable_encoder` then FastAPI's `JSONResponse` encoding
-- and the last line re-parses every path and compares them key for key.

Run it against a COPY of a story database -- it only reads, but nothing here
needs the original::

    ENGINE_DB=/path/to/copy.db python tools/bench/bootstrap_payload.py

Measured on the owner's 307-body town (chat 114) on 2026-09-07: the baseline
response is 2,001,987 bytes in 41.3 ms; the split's full response is 2,002,515
bytes (the +528 is `install_version` and `install_keys`) in 29.7 ms, of which
767,608 bytes (38.3%) is the install half; and every repeat boot receives
1,234,933 bytes in 28.0 ms -- 767,582 bytes, 38.3%, saved per repeat. The
repeat figure is what the route ships since 2026-09-08: the repeat branch
serializes itself on `_JSON_WIRE` like the full branch, where it used to hand a
dict to FastAPI's encoder over the 896KB `characters` key (45.9 ms measured by
the second C22c skeptic against the 28.5 this tool modelled).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.encoders import jsonable_encoder  # noqa: E402

from web import app as web_app  # noqa: E402


def _timed(call, repeats: int = 10) -> float:
    """Minimum of `repeats`, not the mean: this competes with a page's worth
    of allocation, and the fastest run is the one least polluted by it."""
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        call()
        samples.append((time.perf_counter() - started) * 1000)
    return min(samples)


def _wire(payload: dict) -> bytes:
    return json.dumps(payload, **web_app._JSON_WIRE).encode("utf-8")


def main() -> int:
    payload = web_app.bootstrap()
    install_json, version, rest = web_app._bootstrap_split(payload)
    full = web_app._json_object_merge(install_json, _wire(rest))
    known = _wire(dict(rest, install_unchanged=True))

    def baseline():
        """What the route sent before the split, encoded as FastAPI does."""
        return _wire(jsonable_encoder(web_app.bootstrap()))

    def first_boot():
        fresh = web_app.bootstrap()
        block, _version, tail = web_app._bootstrap_split(fresh)
        return web_app._json_object_merge(block, _wire(tail))

    def repeat_boot():
        fresh = web_app.bootstrap()
        _block, _version, tail = web_app._bootstrap_split(fresh)
        tail["install_unchanged"] = True
        return _wire(tail)

    before = baseline()
    print(f"install version      {version}")
    print(f"baseline (pre-split) {len(before):>9,} bytes  "
          f"{_timed(baseline):5.1f} ms")
    print(f"whole payload        {len(full):>9,} bytes  "
          f"{_timed(first_boot):5.1f} ms  "
          f"({len(full) - len(before):+,} vs baseline)")
    print(f"  install half       {len(install_json):>9,} bytes "
          f"({100 * len(install_json) / len(full):.1f}%)")
    print(f"  repeat boot() gets {len(known):>9,} bytes  "
          f"{_timed(repeat_boot):5.1f} ms "
          f"({100 * len(known) / len(full):.1f}%)")
    print(f"  saved per repeat   {len(full) - len(known):>9,} bytes "
          f"({100 * (len(full) - len(known)) / len(full):.1f}%)")

    biggest = sorted(((len(json.dumps(value)), key)
                      for key, value in payload.items()), reverse=True)[:8]
    print("largest keys")
    for size, key in biggest:
        half = "install" if key in web_app._INSTALL_BLOCK_KEYS else "data"
        print(f"  {size:>9,}  {key}  ({half})")

    # THE OTHER HALF OF THE CLAIM. Three routes to the same answer: the
    # payload as it was, the spliced full response, and a client's cached half
    # merged into an `install_unchanged` reply.
    def canonical(obj: dict) -> str:
        trimmed = {key: value for key, value in obj.items()
                   if key not in ("install_version", "install_keys",
                                  "install_unchanged", "providers")}
        return json.dumps(jsonable_encoder(trimmed), sort_keys=True,
                          ensure_ascii=False)

    merged = json.loads(known)
    merged.update(json.loads(install_json))
    answers = {canonical(payload), canonical(json.loads(full)),
               canonical(merged)}
    print(f"same answer three ways: {len(answers) == 1}")
    print("install_keys all present in the half: "
          f"{set(rest['install_keys']) == set(json.loads(install_json))}")
    return 0 if len(answers) == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
