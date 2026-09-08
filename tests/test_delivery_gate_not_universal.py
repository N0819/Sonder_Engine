"""The delivery gate is one of two families, and the code says which.

Review finding B35 (2026-09-07, `docs/experiments/REVIEW_2026-09-07.md`): the
`_delivery_ok` docstring claimed it was "the one predicate all of them call, so
a rule added here reaches every deterministic delivery site at once". Only
`agents/loops.py` calls it. AGENTS.md had already been corrected to say so and
the drift is registered as `docs/UNBUILT.md` 3.8; a new docstring re-asserted
the closed chokepoint anyway, which is how the same claim goes unmeasured
twice.

The rule this file holds is general: a doc that names a chokepoint is a
representation of the call graph, and the call graph is the authority. So the
caller set is MEASURED here rather than asserted in prose, and the gate's own
docstring has to carry the caveat while the second family exists. If the two
families are ever consolidated -- the change `docs/UNBUILT.md` 3.8 asks for --
the first test below fails, which is the signal to rewrite the docstring,
AGENTS.md's delivery-gate row and 3.8 together, then update this file.
"""

import ast
import pathlib

AGENTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "agents"

# The module that DEFINES the gate; its `def` line is not a call site.
DEFINING_MODULE = "common.py"

# Measured 2026-09-07: `agents/loops.py`'s two micro-round deliveries (the
# speech branch and the action branch) are the only production callers.
EXPECTED_CALLERS = {"loops.py"}


def _call_sites():
    """Modules under agents/ that CALL `_delivery_ok`, by AST, not by grep.

    Four modules mention the name in prose (`composer.py`, `perception.py`,
    `character.py` and this gate's own docstring); a text search cannot tell a
    citation from a call, and the citations are what the finding was about.
    """
    found = {}
    for path in sorted(AGENTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else "")
            if name == "_delivery_ok":
                found.setdefault(path.name, []).append(node.lineno)
    return found


def test_delivery_gate_callers_are_measured_not_claimed():
    sites = _call_sites()
    assert set(sites) == EXPECTED_CALLERS, (
        "The `_delivery_ok` caller set changed: found "
        f"{dict(sorted(sites.items()))}. If a second delivery family was "
        "consolidated onto this gate, that closes docs/UNBUILT.md 3.8 -- "
        "update `_delivery_ok`'s docstring, AGENTS.md's delivery-gate row and "
        "this file in the same commit. If a NEW deterministic delivery site "
        "was added, say which family it belongs to in its own docstring first."
    )
    assert DEFINING_MODULE not in sites
    # Both micro-round branches, not one: the speech branch and the action
    # branch gate separately and a single call would mean one went ungated.
    assert len(sites["loops.py"]) == 2, sites["loops.py"]


def test_delivery_gate_docstring_names_the_other_family():
    """The gate's docstring must scope itself while two families exist."""
    from agents.common import _delivery_ok

    doc = _delivery_ok.__doc__ or ""
    assert "loops.py" in doc, (
        "`_delivery_ok`'s docstring must name its actual callers "
        "(agents/loops.py) rather than claim every deterministic delivery "
        "site calls it -- review finding B35."
    )
    assert "3.8" in doc, (
        "`_delivery_ok`'s docstring must cross-reference docs/UNBUILT.md 3.8, "
        "the registered two-family drift, so a reader adding a rule here "
        "knows it does not reach the composer family."
    )
