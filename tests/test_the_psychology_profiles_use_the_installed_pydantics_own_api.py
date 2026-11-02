"""The card schema's profile models speak the installed Pydantic's own API.

`story/character_schema.py` declared its psychology profiles with Pydantic
1's `@validator` (thirteen sites) and `class Config`. Pydantic 2 accepts both
as a deprecated shim -- measured: thirteen `PydanticDeprecatedSince20`
warnings at import on 2.11.7, plus an `allow_reuse` warning per site -- and
Pydantic 3 removes them, so the declared range `pydantic>=1.10.13,<3` was the
only thing holding the card schema off a hard failure (story_scene_schema
audit, Pydantic question). It also read the major for itself
(`hasattr(BaseModel, "model_validate")`), a second copy of the read
`llm.schemas` owns.

The validators keep their semantics exactly -- `pre=True` is `mode="before"`
-- and both majors stay supported: the `pydantic1` CI job runs the V1 branch.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pydantic
import pytest

from story import character_schema


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not hasattr(pydantic.BaseModel, "model_validate"),
                    reason="the deprecation is a Pydantic 2 warning")
def test_importing_the_card_schema_raises_no_pydantic_deprecation():
    probe = textwrap.dedent("""
        import warnings
        # The card schema's own dependencies first, so only ITS class bodies
        # are under the catcher below.
        import llm.schemas, story.attire, language_runtime.referring
        from pydantic.warnings import PydanticDeprecatedSince20
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import story.character_schema
        bad = [f"{w.filename}:{w.lineno}: {w.message}" for w in caught
               if issubclass(w.category, PydanticDeprecatedSince20)]
        assert not bad, "\\n".join(bad)
    """)
    result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-4000:]


def test_the_validators_still_run_before_type_validation():
    psych = character_schema._normalize_psychology({
        "traits": {"wary": 0.7, "stubborn": {"strength": "high"}},
        "values": "loyalty",
        "drive": "not a mapping",
        "capacity": " Narrow ",
        "learning": {"associations": [
            {"cue": "bells", "strength": "9", "generalization_tags": "a, b"}]},
        "self_model": {"beliefs": ["the sea provides"]},
        "coping": {"strategies": "freeze"},
        "extension_key": {"kept": True},
    })
    traits = {t["name"]: t for t in psych["traits"]}
    assert traits["wary"]["strength"] == 0.7
    assert traits["stubborn"]["strength"] == 0.5        # "high" -> default
    assert [v["name"] for v in psych["values"]] == ["loyalty"]
    assert psych["drive"] == {}                          # a non-mapping is dropped
    assert psych["capacity"] == "narrow"
    association = psych["learning"]["associations"][0]
    assert association["strength"] == 1.0               # clamped
    assert association["generalization_tags"] == ["a", "b"]
    assert psych["self_model"]["beliefs"][0]["belief"] == "the sea provides"
    assert psych["coping"]["strategies"][0]["name"] == "freeze"
    assert psych["extension_key"] == {"kept": True}      # extra = "allow"


def test_a_number_where_prose_was_declared_still_reads_as_prose():
    psych = character_schema._normalize_psychology(
        {"traits": [{"name": "wary", "expression": 3}]})
    assert psych["traits"][0]["expression"] == "3"
