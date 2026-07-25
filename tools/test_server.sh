#!/usr/bin/env bash
# Experimental test server.
#
# Runs the engine on a SEPARATE port against a COPY of engine.db, so anything
# you do here -- including a half-finished experimental feature writing to the
# database -- cannot touch your real stories.
#
#   tools/test_server.sh            # copy engine.db once, then reuse it
#   tools/test_server.sh --fresh    # re-copy from engine.db, discarding changes
#   tools/test_server.sh --port 9010
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=8009
FRESH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --fresh) FRESH=1; shift;;
    --port)  PORT="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

TEST_DB="$PWD/engine.test.db"

# Where the real stories live. Resolved explicitly rather than assumed to sit
# beside this script: run from a git worktree, the repo root is NOT the main
# checkout, and a stray empty engine.db there gets copied instead -- which
# silently serves an empty database that looks like data loss.
SOURCE_DB="${ENGINE_SOURCE_DB:-}"
if [ -z "$SOURCE_DB" ]; then
  SOURCE_DB="$PWD/engine.db"
  if git rev-parse --git-common-dir >/dev/null 2>&1; then
    MAIN_ROOT="$(dirname "$(git rev-parse --git-common-dir)")"
    [ -f "$MAIN_ROOT/engine.db" ] && SOURCE_DB="$MAIN_ROOT/engine.db"
  fi
fi

# Source and destination must not be the same file: the copy step deletes the
# destination first, so pointing ENGINE_SOURCE_DB at engine.test.db destroys
# the very database it is about to read.
if [ "$(readlink -f "$SOURCE_DB" 2>/dev/null)" = "$(readlink -f "$TEST_DB" 2>/dev/null)" ]; then
  echo "ENGINE_SOURCE_DB is the test database itself — refusing to copy it over itself."
  echo "To serve engine.test.db directly:  ENGINE_DB=engine.test.db python3 -m uvicorn app:app --port PORT"
  exit 2
fi

if [ "$FRESH" = "1" ] || [ ! -f "$TEST_DB" ]; then
  if [ -f "$SOURCE_DB" ]; then
    echo "copying $SOURCE_DB -> engine.test.db (source is opened read-only)"
    rm -f "$TEST_DB" "$TEST_DB-wal" "$TEST_DB-shm"
    # sqlite backup rather than cp: safe against an in-flight WAL.
    python3 - "$SOURCE_DB" "$TEST_DB" <<'PYCOPY'
import sqlite3, sys
src = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
chats = dst.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
dst.close(); src.close()
print("  copied %d chats" % chats)
if chats == 0:
    print("  WARNING: the copy has no chats -- wrong source database?")
PYCOPY
  else
    echo "no source database at $SOURCE_DB; starting empty"
    echo "(override with ENGINE_SOURCE_DB=/path/to/engine.db)"
  fi
fi

export ENGINE_DB="$TEST_DB"
echo
echo "  test server   http://127.0.0.1:$PORT"
echo "  database      $ENGINE_DB  (copy — real engine.db is NOT used)"
echo "  stop          Ctrl-C"
echo
exec python3 -m uvicorn app:app --reload --port "$PORT"
