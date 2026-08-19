#!/usr/bin/env bash
# ---------------------------------------------------------------
#  Sonder Engine launcher for Linux and macOS.
#
#  The counterpart of "Start Sonder.bat", and the same promise: a clean
#  box, a clone, one command. On first run it finds a Python, builds a
#  virtual environment and installs dependencies; on later runs it just
#  starts the server and opens your browser.
#
#      ./"Start Sonder.sh"
#      ./"Start Sonder.sh" --port 8009 --no-browser
#
#  What it deliberately does NOT do:
#
#   * Install a system Python. That needs sudo, and a launcher that
#     sudo-installs packages nobody asked for is a worse failure than a
#     clear message, so it names the one command for this host's package
#     manager and stops.
#   * Delete anything. No environment is removed to "fix" it, and no
#     database is created, reset, or opened by this script at all. When
#     the environment looks broken it prints the command to remove it
#     and leaves the decision with you.
#
#  NOTE: the server starts WITHOUT --reload, exactly as the .bat does,
#  and that is deliberate. This is the launcher for PLAYING, and a code
#  watcher buys a player nothing while costing real battery: uvicorn
#  falls back to re-walking the whole folder and stat-ing every .py file
#  four times a second whenever watchfiles is missing, which measured
#  16% of a CPU core on an idle server. Sonder itself measures 0%
#  sitting idle with a story open. If you are editing the code and want
#  restarts, use "make run" instead.
# ---------------------------------------------------------------
set -euo pipefail
# -E as well, so the ERR trap below is inherited by functions and
# subshells. Without it `set -e` still aborts, but silently, and a bare
# non-zero exit is the opposite of a legible failure.
set -E

# Defaults, so a double-click needs no arguments at all. The environment
# variables are the form that survives a desktop shortcut; the flags
# below are the form a terminal wants. Flags win over environment.
HOST="${SONDER_HOST:-127.0.0.1}"
PORT="${SONDER_PORT:-8008}"
NO_BROWSER="${SONDER_NO_BROWSER:-}"
VENV=".venv"
VENV_PY="${VENV}/bin/python"
STAMP="${VENV}/.deps-installed"
MIN_PY="3.11"

# --- Legible failure -------------------------------------------
# Every exit path says what was being attempted and what to do next.
STEP="starting up"
ADVICE=""

step() { STEP="$1"; ADVICE="${2:-}"; }

pause() {
    # Double-clicked from a file manager, this window can close the
    # instant the script ends, taking the error with it. Only prompt
    # when there is somebody there to press a key.
    if [ -t 0 ]; then
        printf '\nPress Enter to close this window. '
        read -r _ || true
    fi
}

fail() {
    printf '\n[!] %s\n' "$1" >&2
    pause
    exit 1
}

on_error() {
    local code=$?
    printf '\n[!] Failed while %s (exit %d).\n' "$STEP" "$code" >&2
    if [ -n "$ADVICE" ]; then
        printf '\n%s\n' "$ADVICE" >&2
    fi
    pause
    exit "$code"
}
trap on_error ERR

# --- Arguments -------------------------------------------------
usage() {
    printf 'Start Sonder Engine.\n\n'
    printf '  --port N        listen on port N (default %s)\n' "$PORT"
    printf '  --host ADDR     bind to ADDR (default %s)\n' "$HOST"
    printf '  --no-browser    do not open a browser; just print the URL\n'
    printf '  -h, --help      this message\n\n'
    printf 'SONDER_PORT, SONDER_HOST and SONDER_NO_BROWSER set the same\n'
    printf 'three from the environment, for a desktop shortcut that cannot\n'
    printf 'pass arguments. ENGINE_DB, if set, is passed through untouched.\n'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --port)
            # A missing value must not silently become the flag that
            # follows it, or the server binds to a port named "--host".
            [ $# -ge 2 ] || fail "--port needs a number, as in: --port 8009"
            PORT="$2"; shift 2 ;;
        --port=*) PORT="${1#*=}"; shift ;;
        --host)
            [ $# -ge 2 ] || fail "--host needs an address, as in: --host 0.0.0.0"
            HOST="$2"; shift 2 ;;
        --host=*) HOST="${1#*=}"; shift ;;
        --no-browser) NO_BROWSER=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; fail "Unknown option: $1" ;;
    esac
done

case "$PORT" in
    ''|*[!0-9]*) fail "Not a port number: ${PORT}" ;;
esac
URL="http://${HOST}:${PORT}"

# --- Run from the repository root ------------------------------
# The engine uses absolute package imports rooted here ("from core.db
# import q"), so the working directory is not a convenience.
#
# Resolved without `readlink -f`: that flag is GNU-only and absent from
# the BSD readlink macOS ships, so the symlink walk is done by hand with
# plain `readlink`, which both platforms have.
SCRIPT="$0"
while [ -L "$SCRIPT" ]; do
    TARGET="$(readlink "$SCRIPT")"
    case "$TARGET" in
        /*) SCRIPT="$TARGET" ;;
        *)  SCRIPT="$(dirname "$SCRIPT")/$TARGET" ;;
    esac
done
step "changing to the repository directory"
cd "$(dirname "$SCRIPT")"
ROOT="$PWD"

if [ ! -f "requirements.txt" ] || [ ! -d "web" ]; then
    fail "This does not look like the Sonder Engine folder:
    ${ROOT}

    Keep \"Start Sonder.sh\" in the folder it came in, beside README.md."
fi

# --- How this host installs a Python ---------------------------
# Advice only. Nothing here is ever run.
python_install_hint() {
    if [ "$(uname -s)" = "Darwin" ]; then
        if command -v brew >/dev/null 2>&1; then
            printf '        brew install python@3.13\n'
        else
            printf '        Install Homebrew from https://brew.sh, then:\n'
            printf '        brew install python@3.13\n\n'
            printf '        Or take an installer from https://www.python.org/downloads/\n'
        fi
    elif command -v apt-get >/dev/null 2>&1; then
        printf '        sudo apt-get install python3 python3-venv\n'
    elif command -v dnf >/dev/null 2>&1; then
        printf '        sudo dnf install python3\n'
    elif command -v pacman >/dev/null 2>&1; then
        printf '        sudo pacman -S python\n'
    elif command -v zypper >/dev/null 2>&1; then
        printf '        sudo zypper install python3\n'
    elif command -v apk >/dev/null 2>&1; then
        printf '        sudo apk add python3\n'
    else
        printf '        Install Python %s or newer from https://www.python.org/downloads/\n' "$MIN_PY"
    fi
}

# --- Find a Python new enough to build the environment ---------
# Chosen by VERSION, not by name: "python3" is 3.9 on an untouched macOS
# and 3.13 on a current Fedora, and some distributions still ship no
# bare "python" at all. Saying "too old" HERE is the whole point of the
# check -- an engine started on 3.10 fails much later, with an import
# error that reads like a bug in the app.
#
# Called only when there is no environment yet. Once .venv exists it has
# its own interpreter, and re-deciding which system Python is best is
# both wrong (it is not the one in use) and six process spawns a player
# waits through on every launch.
PY=""
find_python() {
    step "looking for a Python interpreter"
    local candidate version old=""
    for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        version="$("$candidate" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)" || continue
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            PY="$candidate"
            return 0
        fi
        [ -n "$old" ] || old="Python ${version} (${candidate})"
    done

    if [ -n "$old" ]; then
        fail "Sonder Engine needs Python ${MIN_PY} or newer.
    The newest one on this computer is ${old}.

    Install a newer Python with:

$(python_install_hint)
    then run this launcher again."
    fi
    fail "Python was not found on this computer.
    Sonder Engine needs Python ${MIN_PY} or newer.

    Install it with:

$(python_install_hint)
    then run this launcher again."
}

# --- Create the virtual environment on first run ---------------
FIRST_RUN=0
if [ ! -x "$VENV_PY" ]; then
    if [ -e "$VENV" ]; then
        # Something is at .venv but there is no working interpreter in
        # it: a half-finished install, or one built by a Python that has
        # since been upgraded out from under it. Not ours to delete.
        fail "The environment in \"${ROOT}/${VENV}\" is incomplete —
    there is no working interpreter at ${VENV_PY}.

    Remove it yourself and run this launcher again:

        rm -rf \"${ROOT}/${VENV}\""
    fi
    FIRST_RUN=1
    # Before the banner: a box with no usable Python should say so
    # immediately, not after promising a few minutes of work.
    find_python
    printf '\nFirst-time setup: building an environment and downloading\n'
    printf 'dependencies. This can take a few minutes, and happens once.\n'
    printf '\nCreating the virtual environment...\n'
    step "creating the virtual environment" \
"On Debian and Ubuntu the venv module ships separately:

        sudo apt-get install python3-venv"
    "$PY" -m venv "$VENV"
fi

# --- Install / update dependencies -----------------------------
# Reinstall when the stamp is missing, when requirements.txt or
# constraints.txt is NEWER than the stamp -- so pulling an upgrade does
# not need a manual reinstall -- or when the packages are simply not
# importable, since a stamp can outlive the environment it describes.
NEED_DEPS=0
if [ ! -f "$STAMP" ]; then
    NEED_DEPS=1
elif [ "requirements.txt" -nt "$STAMP" ] || [ "constraints.txt" -nt "$STAMP" ]; then
    NEED_DEPS=1
    printf '\nDependencies have changed since the last run; updating them.\n'
elif ! "$VENV_PY" -c 'import importlib.util as u, sys; sys.exit(0 if all(u.find_spec(m) for m in ("fastapi", "uvicorn")) else 1)' >/dev/null 2>&1; then
    NEED_DEPS=1
    printf '\nThe environment is missing packages it should have; reinstalling.\n'
fi

if [ "$NEED_DEPS" = "1" ]; then
    [ "$FIRST_RUN" = "1" ] || printf '\nInstalling dependencies (this may take a few minutes)...\n'
    printf '\n'
    step "installing dependencies" \
"Check the internet connection and run this launcher again.
    Nothing outside \"${ROOT}/${VENV}\" was changed."
    # pip's own output is left on screen rather than hidden. This is the
    # one step that can take minutes, and several silent minutes reads
    # as a hang. Every other run of this script prints five lines.
    "$VENV_PY" -m pip install --upgrade pip
    # -c constraints.txt: requirements.txt declares RANGES, and the range
    # for fastapi resolves to versions CI never runs. One of them moved a
    # Starlette internal this app had reached for, so a fresh install here
    # could fail every api request while CI stayed green -- the people hit
    # by that being exactly the ones running this launcher. Install what
    # was actually tested.
    "$VENV_PY" -m pip install -c constraints.txt -r requirements.txt
    date > "$STAMP"
    printf '\nSetup complete.\n'
fi

# --- Open the browser once the server has had time to boot -----
open_browser() {
    if [ -n "$NO_BROWSER" ]; then
        return 1
    fi
    # The one place the two platforms genuinely differ: macOS has `open`
    # and no `xdg-open`, Linux the other way round. Neither is
    # guaranteed to be installed, so both branches fall through to
    # simply printing the URL.
    if [ "$(uname -s)" = "Darwin" ]; then
        command -v open >/dev/null 2>&1 || return 1
        open "$URL" >/dev/null 2>&1 || return 1
        return 0
    fi
    # No display means this is a headless box or an ssh session, where
    # xdg-open either fails or opens a browser on the wrong machine.
    [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || return 1
    command -v xdg-open >/dev/null 2>&1 || return 1
    xdg-open "$URL" >/dev/null 2>&1 || return 1
    return 0
}

# `trap - ERR` inside the subshell: a browser that will not open is not
# a reason to report the launch as failed.
( trap - ERR; sleep 4; open_browser || printf '\n(Open %s in your browser.)\n' "$URL" ) &
BROWSER_PID=$!

# --- Start the server ------------------------------------------
printf '\n==================================================\n'
printf '  Sonder Engine is starting...\n'
printf '  Opening %s in your browser.\n' "$URL"
printf '  Database: %s\n' "${ENGINE_DB:-engine.db (the default)}"
printf '  Keep this window open while you play.\n'
printf '  Press Ctrl-C to stop the server.\n'
printf '  (No code watcher: idle, this costs near-zero CPU.)\n'
printf '==================================================\n\n'

# ENGINE_DB is passed through untouched when the environment already
# sets it, and left unset otherwise so the engine picks its own default.
# This script never names a database file.

# --timeout-graceful-shutdown: Ctrl-C must actually stop the server.
# Uvicorn otherwise waits forever for a browser that has not finished
# reading a response, and a tab buffering an ambience bed is exactly
# that client.
#
# Run rather than exec'd, and with `set -e` lifted around it, so that a
# server which refuses to start still gets its exit explained below
# instead of the window closing on a traceback.
step "running the server"
set +e
"$VENV_PY" -m uvicorn web.app:app --host "$HOST" --port "$PORT" --timeout-graceful-shutdown 3
STATUS=$?
set -e

kill "$BROWSER_PID" 2>/dev/null || true

# 130 is Ctrl-C, which is how a player is meant to stop this.
if [ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 130 ]; then
    printf '\n[!] The server stopped with exit code %d.\n\n' "$STATUS" >&2
    printf '    If it said "address already in use", Sonder is already\n' >&2
    printf '    running, or something else holds port %s. Use another:\n\n' "$PORT" >&2
    printf '        ./"%s" --port 8009\n' "$(basename "$SCRIPT")" >&2
    pause
    exit "$STATUS"
fi

printf '\nServer stopped.\n'
pause
