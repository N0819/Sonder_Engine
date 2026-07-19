"""Compatibility and ownership checks for the split agent package."""

import agents


def test_agent_roles_live_in_focused_modules():
    assert agents.director_interpret.__module__ == "agents.director"
    assert agents.mapping_stage.__module__ == "agents.mapping"
    assert agents.perception_act.__module__ == "agents.perception"
    assert agents.character_step.__module__ == "agents.character"
    assert agents.interaction_loop.__module__ == "agents.loops"
    assert agents.narrator.__module__ == "agents.narration"
    assert agents.run_pipeline.__module__ == "agents.runtime"


def test_legacy_facade_exports_application_entry_points():
    required = {
        "run_pipeline",
        "request_abort",
        "active_cast",
        "build_plan",
        "establishment_plan",
        "save_step",
        "variant_count",
        "compute_step",
        "active_content",
        "ABORTS",
        "_assert_plan_materialized",
        "is_player_speaker",
    }
    assert required <= set(dir(agents))


def test_runtime_registry_supports_extension_steps():
    key = "test_extension_step"
    agents.register_step(key, lambda ctx, nonce: {"nonce": nonce})
    try:
        assert agents.compute_step(key, object(), 7) == {"nonce": 7}
    finally:
        agents.STEP_HANDLERS.pop(key, None)
