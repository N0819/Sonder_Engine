"""Authenticated application entry after replacement cutover."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from web import app as app_module


ROOT = Path(__file__).resolve().parents[1]


def test_root_redirects_anonymous_requests_and_ui_next_is_retired(
    monkeypatch,
):
    monkeypatch.setattr(app_module.guest, "verify_host_session", lambda token: False)
    client = TestClient(app_module.app)
    try:
        root = client.get("/", follow_redirects=False)
        retired = client.get("/ui-next", follow_redirects=False)
    finally:
        client.close()

    assert root.status_code in {302, 303, 307, 308}
    assert root.headers["location"] == "/login"
    assert retired.status_code == 404


def test_root_serves_only_the_static_application_to_a_valid_host(
    monkeypatch,
):
    monkeypatch.setattr(
        app_module.guest,
        "verify_host_session",
        lambda token: token == "valid-host-session",
    )
    client = TestClient(app_module.app)
    try:
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
        response = client.get("/")
    finally:
        client.close()

    assert response.status_code == 200
    assert 'data-ui-next-entry="application"' in response.text
    assert '/static/js/ui-next/main.js?release=alpha98-ui11-0acc47fb0573' in response.text
    assert "/api/" not in response.text
    assert "Baseline Story" not in response.text


def test_ui_next_lab_uses_the_same_host_only_boundary(monkeypatch):
    monkeypatch.setattr(
        app_module.guest,
        "verify_host_session",
        lambda token: token == "valid-host-session",
    )
    client = TestClient(app_module.app)
    try:
        anonymous = client.get("/ui-next/lab", follow_redirects=False)
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
        authenticated = client.get("/ui-next/lab")
    finally:
        client.close()

    assert anonymous.status_code in {302, 303, 307, 308}
    assert anonymous.headers["location"] == "/login"
    assert authenticated.status_code == 200
    assert 'data-ui-next-entry="component-lab"' in authenticated.text


def test_formal_interface_type_scale_is_tokenized():
    css = (ROOT / "static/css/ui/tokens.css").read_text(encoding="utf-8")
    for declaration in (
        "--ui-text-micro: 11px",
        "--ui-leading-micro: 14px",
        "--ui-text-meta: 12px",
        "--ui-leading-meta: 16px",
        "--ui-text-control: 13px",
        "--ui-leading-control: 18px",
        "--ui-text-body: 14px",
        "--ui-leading-body: 20px",
        "--ui-text-section: 16px",
        "--ui-leading-section: 22px",
        "--ui-text-page: 21px",
        "--ui-leading-page: 28px",
        "--ui-text-display: 28px",
        "--ui-leading-display: 36px",
    ):
        assert declaration in css


def test_readable_component_text_uses_semantic_type_tokens():
    offenders: list[str] = []
    raw_size = re.compile(r"font-size\s*:\s*(?!0(?:px|rem|em)?\s*[;}])(?:\d|\.)")
    raw_shorthand = re.compile(r"\bfont\s*:[^;{}]*(?:\d|\.)+(?:px|rem|em)\b")
    for path in (ROOT / "static/css/ui").rglob("*.css"):
        if path.name == "tokens.css" or "themes" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if raw_size.search(line) or raw_shorthand.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def test_free_standing_bordered_surfaces_use_semantic_bevel():
    offenders: list[str] = []
    framed_rule = re.compile(
        r"(?ms)([^{}]+)\{([^{}]*\bborder\s*:\s*(?:1px|2px)\s+solid[^;]*;[^{}]*)\}"
    )
    for path in (ROOT / "static/css/ui").rglob("*.css"):
        if path.name == "tokens.css" or "themes" in path.parts:
            continue
        for match in framed_rule.finditer(path.read_text(encoding="utf-8")):
            declarations = match.group(2)
            if "border-radius:" not in declarations:
                selector = " ".join(match.group(1).split())
                offenders.append(f"{path.relative_to(ROOT)}: {selector}")
    assert offenders == []
