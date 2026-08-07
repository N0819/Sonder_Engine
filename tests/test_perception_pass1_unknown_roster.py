"""Binds the widened pass-1 identity scrub in agents/perception.py.

perception_act's pass-1 scrub used to enumerate a ONE-ELEMENT roster holding
the player persona alone, so no pattern was ever built for a cast name and a
co-present stranger's canonical name walked straight through the gate. Live,
chat 63 turn 165: two co-present bodies, one scrub pass, the warning reporting
``scrubbed unearned identity ['Hinami']`` while "Tamamo" sat untouched in the
same sentence, delivered to an observer with no ``known`` entry at all.

The widened block builds the roster from every co-present body the observer
does not recognise. Exercising it end-to-end needs a model call, so these two
cases execute the REAL block sliced out of the file on disk by its own source
text: the bytes under test are the bytes that ship, and the live helpers are
imported rather than reproduced. If the block is refactored the anchors stop
matching and this fails loudly rather than passing against a stale copy.

The file's sha is PRINTED, not asserted -- a digest assertion would make this
fail on any unrelated edit to perception.py, which is noise rather than a
finding.
"""

import hashlib
import pathlib
import textwrap

from agents import perception as P

SRC_PATH = pathlib.Path(P.__file__)

# Copied character for character from perception_act. The first line of the
# roster build, and the last line of the warning that reports what leaked.
START = '        recognized = set(known.get(p["name"]) or [])\n'
END = '                    f"from the view of {p[\'name\']}")'

VIEW = (
    "Hinami kneels by the offering box, six golden tails furled behind her. "
    "Tamamo stands at the hearth nearby, one ear pivoting."
)

CO_PRESENT = [
    {
        "name": "Hinami",
        "room": "shrine_hall",
        "appearance": (
            "a beautiful young woman in red and white, "
            "six golden tails furled behind her"
        ),
        "aliases": [],
        "disguise_known_to": [],
    },
    {
        "name": "Tamamo",
        "room": "shrine_hall",
        "appearance": "a striking woman with nine voluminous golden tails",
        "aliases": [],
        "disguise_known_to": [],
    },
]

OBSERVER = "The Doctor"
ACTOR = "Hinami"


class _Ctx:
    """Only the surface the sliced block touches."""

    def __init__(self):
        self.warnings = []


def _pass1_block():
    src = SRC_PATH.read_text(encoding="utf-8")
    print(
        "PERCEPTION_SHA",
        hashlib.sha256(src.encode("utf-8")).hexdigest()[:16],
    )
    assert src.count(START) == 1, (
        "pass-1 roster anchor is not unique in %s -- the block moved, so this "
        "test is no longer binding what it claims to bind" % SRC_PATH
    )
    assert src.count(END) == 1, (
        "pass-1 leak-warning anchor is not unique in %s" % SRC_PATH
    )
    start = src.index(START)
    end = src.index(END, start) + len(END)
    return textwrap.dedent(src[start:end])


def _run(known):
    """Execute the sliced block with the locals perception_act would hold.

    Globals are the real module namespace, so ``_recognizes`` and
    ``_scrub_unknown_identities`` are the live functions. Assignments land in
    the locals dict, so the module is not mutated.
    """
    ns = {
        "p": {"name": OBSERVER},
        "known": known,
        # Derived exactly as perception_act derives it, rather than hardcoded.
        "knows_identity": ACTOR in (known.get(OBSERVER) or []),
        "p_name": ACTOR,
        "p_visible": CO_PRESENT[0]["appearance"],
        "co_present": [dict(b) for b in CO_PRESENT],
        "view": VIEW,
        "leaked": [],
        "ctx": _Ctx(),
    }
    exec(compile(_pass1_block(), str(SRC_PATH), "exec"), vars(P), ns)
    return ns


def test_observer_with_no_known_key_scrubs_both_co_present_bodies():
    """The chat 63 t165 condition: the observer has no `known` entry at all.

    Both bodies are strangers, so both names must leave the prose and both
    must be reported. Under the old one-element roster, 'Tamamo' survived.
    """
    ns = _run({})

    assert ns["leaked"] == ["Hinami", "Tamamo"]
    assert "Hinami" not in ns["view"]
    assert "Tamamo" not in ns["view"]
    assert ns["view"] != VIEW

    assert len(ns["ctx"].warnings) == 1
    warning = ns["ctx"].warnings[0]
    assert "['Hinami', 'Tamamo']" in warning
    assert OBSERVER in warning


def test_observer_recognising_tamamo_keeps_tamamo_and_scrubs_hinami():
    """The negative arm: the widening must not become an over-scrub.

    Recognition is earned per body, so a name the observer has earned stays
    in the prose while the stranger beside her does not.
    """
    ns = _run({OBSERVER: ["Tamamo"]})

    assert ns["leaked"] == ["Hinami"]
    assert "Hinami" not in ns["view"]
    assert "Tamamo" in ns["view"]

    assert len(ns["ctx"].warnings) == 1
    warning = ns["ctx"].warnings[0]
    assert "['Hinami']" in warning
    assert OBSERVER in warning
