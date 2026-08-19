"""The `tools/` harnesses, held to the one thing nothing else holds them to.

Nothing imports these drivers, so nothing notices when a module they name by
string moves. They fail into a bare `except`, report a degraded metric, and
exit 0 — which is the failure mode of a measurement instrument that reads zero
because it is unplugged.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def test_perception_quality_resolves_every_engine_symbol():
    """The firewall-measurement harness must actually reach the engine.

    `resolve_engine` asked for `spatial` and `character_schema` — bare
    pre-move names — long after they became `world.spatial` and
    `story.character_schema`. Both raised `ModuleNotFoundError` into the
    tolerant `except`, so `spatial_rel`, `room_of` and `character_name` were
    None, `gate_available` was False on every view, every dialogue line filed
    as `ungated`, and the tool printed a clean report and exited 0.
    """
    from perception_quality import resolve_engine

    _, missing = resolve_engine()
    assert missing == []


def test_perception_quality_names_the_symbols_its_gate_needs():
    from perception_quality import GATE_SYMBOLS, resolve_engine

    symbols, _ = resolve_engine()
    for name in GATE_SYMBOLS:
        assert symbols.get(name) is not None, name


def test_code_map_purposes_all_name_a_real_module():
    """A purpose key that matches nothing renders an empty Purpose column.

    The package move made 33 of 43 keys stale in one commit, and 100 of 110
    rows in `docs/CODE_MAP.md` lost their Purpose with no diff to read:
    `check_generated_map` regenerates the file and compares, so both sides
    lost the purposes together.
    """
    from generate_code_map import MODULE_PURPOSES, module_name, source_paths

    modules = {module_name(path) for path in source_paths()}
    assert sorted(k for k in MODULE_PURPOSES if k not in modules) == []


def test_code_map_generator_refuses_a_stale_purpose_key(monkeypatch):
    import generate_code_map as gcm
    import pytest

    monkeypatch.setitem(gcm.MODULE_PURPOSES, "spatial", "pre-move name")
    with pytest.raises(gcm.StalePurposeKeys) as exc:
        gcm.generate()
    assert "world.spatial" in str(exc.value)


def test_every_benchable_step_resolves_to_a_prompt():
    """A `--step` choice that names no prompt is a KeyError after a paid call.

    The engine does not key its prompts, its schemas and its provider roles the
    same way: `director_resolve` is a real `SCHEMA_MAP` step with no prompt of
    that name, because the monolith is gone and the prose author's prompt is
    `director_resolve_lean`. `contract_bench` carries that mapping;
    `creation_probe` offered the same step without it and raised.
    """
    import contract_bench
    import creation_probe
    from llm import prompts

    for tool in (contract_bench, creation_probe):
        unresolved = sorted(
            step for step in tool.PAYLOADS
            if contract_bench.PROMPT_KEY.get(step, step)
            not in prompts.DEFAULT_PROMPTS)
        assert unresolved == [], (tool.__name__, unresolved)


def test_chat_export_needs_the_wired_service_not_the_class(temp_db):
    """`ChatArchiveService.export_chat(None, cid)` is a delayed crash.

    `export_chat` is an instance method that dereferences `self._remap` inside
    the frames loop, so passing `None` for `self` works exactly until the chat
    has a `frames` row — and a frame split happens on its own, after a paid run
    has finished. Three drivers wrote their `story.json` that way.
    """
    import pytest
    from persist.chat_archive import ChatArchiveService
    from web.app import chat_export

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("archive probe", "", "2026-08-18T00:00:00"))
    temp_db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
        "VALUES(?,?,?,?,?)",
        (cid, "main", 0, "main", "2026-08-18T00:00:00"))

    export = chat_export(cid)
    assert [f["chat_id"] for f in export["frames"]] == [cid]

    with pytest.raises(AttributeError):
        ChatArchiveService.export_chat(None, cid)
