"""Structural documentation must report the URLs users can actually call.

Read off the two modules that register the routes in question, not off a
whole-tree `generate()` run twice: that cost 8.0 s and 6.8 s of the suite
(the 2026-11-01 baseline's `--durations`), regenerating the map `make check`
had already generated twice more. `check_generated_map` holds the whole map
against the tree; these hold the two route spellings the map must get right.
"""

from tools.generate_code_map import ROOT, module_name, parse_module, source_paths


def _routes(relative):
    local = {module_name(path) for path in source_paths()}
    info = parse_module(ROOT / relative, local)
    return {(method, path, handler) for method, path, handler, _line
            in info["routes"]}


def test_code_map_applies_local_api_router_prefixes():
    routes = _routes("web/auth_routes.py")

    assert ("POST", "/api/auth/login", "auth_login") in routes
    assert ("POST", "/login", "auth_login") not in routes


def test_code_map_includes_explicit_service_route_registration():
    routes = _routes("persist/chat_archive.py")

    assert ("GET", "/api/chats/{cid}/export", "export_chat") in routes
    assert ("POST", "/api/chats/import", "import_chat") in routes
