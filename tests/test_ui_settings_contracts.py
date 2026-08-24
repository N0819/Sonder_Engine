from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_settings_overview_contract_keeps_ordered_groups_and_existing_targets():
    source = (ROOT / "static/js/ui-next/settings-overview.js").read_text(
        encoding="utf-8"
    )

    ordered_groups = ["Connections", "Appearance", "Story & host", "Advanced"]
    ordered_targets = [
        "#/settings/ai-connections",
        "#/settings/experience?control=themes",
        "#/settings/experience?control=reading",
        "#/settings/experience?control=sound",
        "#/settings/experience?control=accessibility",
        "#/settings/content",
        "#/settings/add-ons",
        "#/settings/maintenance",
        "#/library/stories",
        "#/settings/ai-connections?control=models",
        "#/settings/advanced?tool=prompts",
        "#/play/story-tools?tool=turn-details",
        "#/settings/advanced?tool=story-data",
    ]

    positions = [source.index(f'label: "{label}"') for label in ordered_groups]
    assert positions == sorted(positions)
    positions = [source.index(f'href: "{target}"') for target in ordered_targets]
    assert positions == sorted(positions)


def test_settings_uses_one_navigation_model_and_routes_remain_compatible():
    overview = (ROOT / "static/js/ui-next/settings-overview.js").read_text(
        encoding="utf-8"
    )
    router = (ROOT / "static/js/ui-next/router.js").read_text(encoding="utf-8")
    view = (ROOT / "static/js/ui-next/settings-view.js").read_text(encoding="utf-8")

    for forbidden in ("fetch(", "apiClient", "localStorage", "setRecord(", ".post(", ".put(", ".delete("):
        assert forbidden not in overview
    for segment in (
        "experience",
        "ai-connections",
        "content",
        "add-ons",
        "maintenance",
        "advanced",
    ):
        assert f'"{segment}"' in router
    assert 'route.segments?.[0] || "experience"' in view
    assert 'data-settings-overview' not in view
    assert '"Settings overview"' not in view
    assert ".scrollIntoView(" not in view
    assert ".focus({ preventScroll: true })" in view
