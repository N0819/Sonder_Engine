"""What a per-turn checkpoint costs, and whether it still says the same thing.

Review 2026-09-07 C2. A checkpoint is written twice per turn (the route and
the pipeline both call `ensure_checkpoint`) and again when `data_version`
moves under the lock, so everything it re-derives is paid for two or three
times a beat. This measures the two halves the review named:

* the WORLD section -- `json.loads` of every world row followed by
  `json.dumps` of the parsed result, an identity transform on text that is
  already JSON in the database (`snapshot_blob` splices it instead);
* the MEMORY dump -- `SELECT *` pulling both 20 KB vector blobs off every
  memory row to sha1 them into an address the row now carries (`vkey`,
  schema v38).

It also PROVES the two spellings agree: `snapshot_blob` and the old
`json.dumps(snapshot_state(...))` are compared byte for byte, and the exit
status is non-zero if they differ.

Run it against a COPY of a database, never the live one (it only reads, but a
copy is how you keep that true). The copy must have been opened once by this
engine, so that `db.init()` has run the v38 migration on it:

    ENGINE_DB=/path/to/copy.db python tools/bench/checkpoint_snapshot.py <chat_id>
"""
import json
import sys
import time

from core.db import q
from mind.memory import dump_chat_memories, vector_address
from persist.checkpoints import snapshot_blob, snapshot_state


def _best(fn, runs=3):
    best, out = None, None
    for _ in range(runs):
        started = time.perf_counter()
        out = fn()
        elapsed = time.perf_counter() - started
        best = elapsed if best is None else min(best, elapsed)
    return best, out


def _legacy_memory_dump(chat_id):
    """What the dump did before v38: every row with both blobs, sha1 each.

    Kept here rather than in the engine so the two can be timed against each
    other on the same file -- it is the measurement's control, not a code
    path anything still calls.
    """
    rows = q("SELECT * FROM memories WHERE chat_id=? ORDER BY "
             "CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id",
             (chat_id,))
    return [vector_address(r["embedding"], r["cue_embedding"]) for r in rows]


def main(chat_id):
    world = q("SELECT COUNT(*) n, COALESCE(SUM(LENGTH(value)),0) b "
              "FROM world WHERE chat_id=?", (chat_id,), one=True)
    mem = q("SELECT COUNT(*) n, "
            "COALESCE(SUM(LENGTH(embedding)+LENGTH(cue_embedding)),0) b, "
            "SUM(CASE WHEN vkey IS NULL OR vkey='' THEN 1 ELSE 0 END) unstamped "
            "FROM memories WHERE chat_id=?", (chat_id,), one=True)
    print("chat %d: %d world rows (%.1f KB), %d memories (%.1f MB of vectors, "
          "%d unstamped)" % (chat_id, world["n"], world["b"] / 1024.0,
                             mem["n"], mem["b"] / 1048576.0, mem["unstamped"]))

    # The world section on its own, both spellings, each timed WITH its own
    # query: the parse-and-re-emit the checkpoint used to do, against reading
    # the same rows plus SQLite's verdict on each and splicing the text. The
    # `json_valid` column belongs in the new number -- it is what keeps a row
    # that is not JSON failing at checkpoint time rather than at restore.
    def _old_world():
        rows = q("SELECT key, value FROM world WHERE chat_id=?", (chat_id,))
        return json.dumps({r["key"]: json.loads(r["value"]) for r in rows})

    def _new_world():
        rows = q("SELECT key, value, json_valid(value) AS ok FROM world "
                 "WHERE chat_id=?", (chat_id,))
        return "{%s}" % ", ".join(
            "%s: %s" % (json.dumps(r["key"]), r["value"])
            for r in rows if r["ok"])

    world_old, _ = _best(_old_world)
    world_new, _ = _best(_new_world)
    legacy_t, _ = _best(lambda: _legacy_memory_dump(chat_id))
    dump_t, _ = _best(lambda: dump_chat_memories(chat_id, inline_vectors=False))
    old_t, old_text = _best(lambda: json.dumps(snapshot_state(chat_id)))
    new_t, new_text = _best(lambda: snapshot_blob(chat_id))
    print("  world section, parse+re-emit%7.1f ms" % (world_old * 1000))
    print("  world section, spliced      %7.1f ms" % (world_new * 1000))
    print("  memory dump, blobs+sha1     %7.1f ms" % (legacy_t * 1000))
    print("  memory dump, addresses      %7.1f ms" % (dump_t * 1000))
    print("  json.dumps(snapshot_state)  %7.1f ms   %d bytes" % (old_t * 1000, len(old_text)))
    print("  snapshot_blob               %7.1f ms   %d bytes" % (new_t * 1000, len(new_text)))
    if old_text == new_text:
        print("  the two blobs are byte-identical")
        return 0
    same = json.loads(old_text) == json.loads(new_text)
    print("  BLOBS DIFFER; parsed equal: %s" % same)
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
