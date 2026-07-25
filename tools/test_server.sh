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
if [ "$FRESH" = "1" ] || [ ! -f "$TEST_DB" ]; then
  if [ -f engine.db ]; then
    echo "copying engine.db -> engine.test.db (your real DB is untouched)"
    rm -f "$TEST_DB" "$TEST_DB-wal" "$TEST_DB-shm"
    # sqlite backup rather than cp: safe against an in-flight WAL.
    python3 -c "
import sqlite3, sys
src = sqlite3.connect('engine.db'); dst = sqlite3.connect(sys.argv[1])
src.backup(dst); dst.close(); src.close()" "$TEST_DB"
  else
    echo "no engine.db found; starting with an empty test database"
  fi
fi

export ENGINE_DB="$TEST_DB"
echo
echo "  test server   http://127.0.0.1:$PORT"
echo "  database      $ENGINE_DB  (copy — real engine.db is NOT used)"
echo "  stop          Ctrl-C"
echo
exec python3 -m uvicorn app:app --reload --port "$PORT"
