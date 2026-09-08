"""How many times one turn rebuilds the carrier index, and what it costs.

`story.carriers._carriers` is THE enumeration of every body that can hold a
report -- extant cast, the player, and every unbound Charter body. A normal
turn asks for it six times: the Director's carried-report view at
`director_interpret` and again at `director_resolve`, then `advance_carriers`,
`apply_tellings`, `run_couriers` and `run_artifacts`, the last four
consecutive inside `commit_information_carriers` and all four handed the same
scene object. This replays those six sites and reports the number of real
walks and the wall clock, with the per-turn memo (review 2026-09-07, C9) on
and off.

It makes NO model calls and writes nothing: every site here is a read. Point
it at a COPY of a database, never a live one:

    python tools/bench/carrier_index.py <chat_id> <path/to/copy.db>
    python tools/bench/carrier_index.py <chat_id> <path/to/copy.db> --nomemo

Measured 2026-09-07 on a 307-body charter town at 14 turns (63 charter
carriers standing in reach) -- 6 walks, 0.362 s -> 2 walks, 0.176 s -- and on
a 123-beat two-body descent -- 6 walks, 0.151 s -> 2 walks, 0.089 s. A single
walk was 45 ms on the town, 30 ms of it `charter_runtime.carrier_entries`.
"""

from __future__ import annotations

import os
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


class _Chat(dict):
    """A chat with both `.id` and `.get`, as the real `ChatData` has -- the
    persona is a carrier, and resolving one needs `.get`."""

    @property
    def id(self):
        return self["id"]


class _Ctx:
    """The `_extra` side channel of a `PipelineContext`, and nothing else:
    the memo needs somewhere to live and no stage output to live beside."""

    def __init__(self, chat, turn):
        self.chat, self.turn = chat, turn
        self._extra = {}

    def get(self, key, default=None):
        if hasattr(self, key):
            return getattr(self, key)
        return self._extra.get(key, default)

    def __setitem__(self, key, value):
        self._extra[key] = value


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    chat_id, path = int(argv[1]), argv[2]
    nomemo = "--nomemo" in argv

    from core import db
    db.configure(path)
    row = db.q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if row is None:
        print("no chat %d in %s" % (chat_id, path))
        return 1

    from agents.director import _carried_reports_view
    from story import carriers
    from story.scene import get_scene

    walks = []
    real = carriers._build_carriers

    def counting(*a, **k):
        walks.append(1)
        return real(*a, **k)

    carriers._build_carriers = counting
    if nomemo:
        memoised = carriers._carriers

        def unmemoised(cid, frame_id, scene, chat=None, ctx=None):
            return memoised(cid, frame_id, scene, chat=chat, ctx=None)

        carriers._carriers = unmemoised

    chat = _Chat(id=chat_id, persona_id=row["persona_id"])
    ctx = _Ctx(chat, types.SimpleNamespace(id=0, idx=0, frame_id=None))

    # One walk before the clock starts: the first reader of a story's charter
    # registry pays a 41 MB parse (0.6 s on the town) that every turn after
    # the first does not, and that one number swamps the six sites this is
    # about. `cached_registry` holds it for the rest of the process.
    real(chat_id, None, get_scene(chat_id, chat), chat=chat)

    started = time.perf_counter()
    _carried_reports_view(ctx)                             # interpret payload
    _carried_reports_view(ctx)                             # resolve payload
    scene = get_scene(chat_id, chat)                        # commit's one scene
    carriers._carriers(chat_id, None, scene, chat=chat, ctx=ctx)     # advance
    carriers._cast_index(chat_id, None, scene, chat=chat, ctx=ctx)   # tellings
    carriers._cast_index(chat_id, None, scene, chat=chat, ctx=ctx)   # couriers
    index = carriers._cast_index(chat_id, None, scene, chat=chat, ctx=ctx)
    elapsed = time.perf_counter() - started

    print("%s chat %d: walks=%d wall=%.4fs carriers_by_name=%d"
          % ("no memo" if nomemo else "memo   ", chat_id, len(walks),
             elapsed, len(index)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
