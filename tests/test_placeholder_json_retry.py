"""Some models (nemotron:thinking) honour response_format=json_object by
returning a valid SKELETON with every string value set to '...', which parses
and validates fine so '...' reaches the player. _is_placeholder_json detects it
so the provider can retry without json_mode (where the same model writes real
content)."""

from __future__ import annotations

from providers import _is_placeholder_json


def test_all_placeholder_strings_is_a_skeleton():
    assert _is_placeholder_json('{"views":{"player":"...","1":"...","2":"..."}}')
    assert _is_placeholder_json('{"prose":"..."}')
    assert _is_placeholder_json('{"a":"","b":"   "}')  # all empty counts too


def test_any_real_string_is_not_a_skeleton():
    assert not _is_placeholder_json('{"prose":"You step onto the pad."}')
    assert not _is_placeholder_json('{"prose":"real","x":"..."}')


def test_non_string_or_non_json_is_not_a_skeleton():
    assert not _is_placeholder_json('{"n": 5, "ok": true}')
    assert not _is_placeholder_json("not json at all")
    assert not _is_placeholder_json("")
    assert not _is_placeholder_json(None)
