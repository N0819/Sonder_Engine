"""Structural documentation must report the URLs users can actually call."""

from tools.generate_code_map import generate


def test_code_map_applies_local_api_router_prefixes():
    code_map = generate()

    assert "| POST | `/api/auth/login` | `auth_login()`" in code_map
    assert "| POST | `/login` | `auth_login()`" not in code_map


def test_code_map_includes_explicit_service_route_registration():
    code_map = generate()

    assert "| GET | `/api/chats/{cid}/export` | `export_chat()`" in code_map
    assert "| POST | `/api/chats/import` | `import_chat()`" in code_map
