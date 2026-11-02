"""One list names every door a model -- or any provider -- is reached through.

There were two lists, and they already disagreed: `tests/helpers.py`'s
`MODEL_SEAMS` named three doors and `tests/model_seams.py`'s `MODEL_DOORS`
five, so `forbid_model_calls` left both embedding doors open. Neither named
the decision model's post (`llm/decisions.py`, which arrived after both), the
async completion, the two image calls, the model listing or the research
fetches (tooling_gate F4, 2026-11-01). `tests/test_model_seams.py` opens every
door in the one list; this file holds the list to what the engine has.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_both_sealers_read_the_one_list():
    import model_seams
    from tests import helpers

    assert model_seams.MODEL_DOORS is helpers.MODEL_DOORS
    assert not hasattr(helpers, "MODEL_SEAMS")


@pytest.mark.parametrize("door", [
    ("llm.decisions", "_post"),
    ("llm.providers", "chat_complete_async"),
    ("llm.providers", "embed_texts"),
    ("llm.providers", "embed_texts_meta"),
    ("llm.providers", "generate_image"),
    ("llm.providers", "edit_image"),
    ("llm.providers", "list_models"),
    ("llm.research_providers", "search"),
    ("llm.research_providers", "fetch"),
])
def test_every_way_out_is_a_door(door):
    from tests.helpers import MODEL_DOORS

    assert door in MODEL_DOORS


def test_forbid_model_calls_shuts_the_embedding_doors_too(monkeypatch):
    from llm import providers
    from tests.helpers import forbid_model_calls

    bindings = forbid_model_calls(monkeypatch, reason="no model here")
    assert ("llm.providers", "embed_texts") in bindings
    with pytest.raises(AssertionError, match="embed_texts"):
        providers.embed_texts(["a"])


def test_the_sweep_covers_every_engine_package():
    sys.path.insert(0, str(ROOT / "tools"))
    import project_check
    from tests.helpers import ENGINE_PACKAGES

    assert set(ENGINE_PACKAGES) == set(project_check.ENGINE_PACKAGE_ROOTS)
