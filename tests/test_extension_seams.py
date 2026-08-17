"""The four seams added after the prototype: commit domains, routing hooks,
extension routes, and hot-loadable UI.

Each one closes a gap the prototype left, and each is pinned here by the
property that makes it worth having rather than by its happy path:

* a commit domain is atomic WITH the turn -- that is the entire reason it is not
  `on_turn_committed`, so the rollback is the test;
* a routing hook may rewrite anything and is ATTRIBUTED for it -- the power is
  not in question, the trace is;
* a route is namespaced under `/x/` so an extension cannot shadow a host route
  whatever it names its path;
* the per-extension script and stylesheet exist so enable is hot rather than
  reload-only, which means the interesting assertion is that a DISABLED
  extension serves nothing.
"""

from __future__ import annotations

import json
import time

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _character, _enable, _turn, _write_extension, ext_root,
    real_ext_root,
)

DEMO = "cohesion-demo"


def _api(ext_id):
    return extension_runtime._apis[ext_id]


def io_read(relative):
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / relative).read_text(
        encoding="utf-8")


@pytest.fixture
def bare(ext_root):
    """One installed, enabled extension with a python entry that does nothing.

    Hooks are then registered against its live api object, so each test states
    the one registration it is about instead of carrying a fixture extension
    whose entry file has to anticipate every test in the file.
    """
    _write_extension(ext_root, "seams", {
        "id": "seams", "version": "1.0.0", "ext_api": 1, "name": "Seams",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("seams")
    return _api("seams")


# ------------------------------------------------------------ commit domains


class TestCommitDomains:
    def test_a_domain_runs_inside_the_turns_transaction(self, temp_db, bare):
        chat_id = _chat(temp_db)
        seen = {}

        def domain(view):
            seen["chat_id"] = view.chat_id
            seen["turn_idx"] = view.turn_idx
            view.state.set({"count": 1})
            return {"ok": True}

        bare.add_commit_domain("counter", domain)
        results = {}
        extension_runtime.run_commit_domains(
            _StubCtx(chat_id=chat_id, turn_id=_turn(temp_db, chat_id), idx=6),
            results)

        assert seen == {"chat_id": chat_id, "turn_idx": 6}
        assert results["ext:seams:counter"] == {"ok": True}
        from db import wget
        assert wget(chat_id, "ext:seams") == {"count": 1}

    def test_state_is_ungated_here_because_the_transaction_is_the_guarantee(
            self, temp_db, bare):
        """The mirror of the `on_turn_committed` gate, and the reason it exists.

        Outside a committed-turn hook `state.set()` refuses, because a
        mid-pipeline write survives the rollback that undid everything it was
        computed from. Inside the transaction that hazard is gone -- the write
        rolls back WITH the turn -- so refusing here would be superstition.
        """
        chat_id = _chat(temp_db)
        captured = {}

        bare.add_commit_domain(
            "writes", lambda view: captured.setdefault(
                "value", view.state.set({"written": True})))
        extension_runtime.run_commit_domains(
            _StubCtx(chat_id=chat_id, turn_id=_turn(temp_db, chat_id)), {})

        assert captured["value"] == {"written": True}
        assert extension_runtime.in_commit_scope() is False

    def test_a_warning_domain_keeps_the_turn(self, temp_db, bare):
        ctx = _StubCtx(chat_id=_chat(temp_db))
        results = {}

        def boom(view):
            raise ValueError("no")

        bare.add_commit_domain("flaky", boom)          # on_error="warn"
        extension_runtime.run_commit_domains(ctx, results)

        assert results["ext:seams:flaky"] == {"error": "no"}
        assert any("flaky" in note for note in ctx.warnings)
        assert extension_runtime.observer_failures()["seams"] == 1

    def test_a_failing_domain_rolls_the_turn_back_when_it_asked_to(
            self, temp_db, bare):
        """`on_error="fail"` must really propagate.

        Swallowing it here would make the option a lie: the whole point of
        choosing "fail" is an extension saying its state being wrong is worse
        than the beat being lost, and it is the only way an extension can
        legitimately cost a turn.
        """
        def boom(view):
            raise ValueError("roll it back")

        bare.add_commit_domain("strict", boom, on_error="fail")
        with pytest.raises(ValueError, match="roll it back"):
            extension_runtime.run_commit_domains(
                _StubCtx(chat_id=_chat(temp_db)), {})

    def test_domains_run_in_a_deterministic_order(self, temp_db, bare):
        order = []
        for name in ("zebra", "alpha", "middle"):
            bare.add_commit_domain(
                name, lambda view, n=name: order.append(n))
        extension_runtime.run_commit_domains(
            _StubCtx(chat_id=_chat(temp_db)), {})
        assert order == ["alpha", "middle", "zebra"]

    def test_a_bad_name_is_refused_at_registration(self, bare):
        for bad in ("", "Has Caps", "with/slash", "..", "9lives"):
            with pytest.raises(ExtensionError):
                bare.add_commit_domain(bad, lambda view: None)
        with pytest.raises(ExtensionError):
            bare.add_commit_domain("fine", lambda view: None, on_error="explode")


# ------------------------------------------------------------ routing hooks


class TestCharacterPayloadRouting:
    def test_a_hook_may_rewrite_the_payload(self, temp_db, bare):
        bare.on_character_payload(
            lambda payload, info: {**payload, "briefing": "the klaxon sounded"})

        out = extension_runtime.dispatch_character_payload(
            _StubCtx(chat_id=_chat(temp_db)), 7, {"self": {"name": "Ash"}})

        assert out["briefing"] == "the klaxon sounded"
        assert out["self"] == {"name": "Ash"}

    def test_every_changed_key_is_attributed_to_its_extension(
            self, temp_db, bare):
        """The exchange the responsibility doctrine makes.

        An extension may put anything in a mind. What it may not do is put it
        there anonymously -- a character who knows what they should not has to
        name their author in one read, or the defect reads as an engine bug and
        gets debugged in the wrong place for a day.
        """
        bare.on_character_payload(
            lambda payload, info: {**payload, "perception": {"view": "rewritten"},
                                   "extra": 1})
        ctx = _StubCtx(chat_id=_chat(temp_db))

        extension_runtime.dispatch_character_payload(
            ctx, 7, {"perception": {"view": "original"}, "self": {}})

        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": 7, "changed": ["extra", "perception"]}]

    def test_a_hook_that_mutates_in_place_is_still_attributed(self, temp_db,
                                                              bare):
        """The audit trail must not be escapable by ordinary Python.

        A hook is handed the real payload, so the natural way to write one
        mutates it and returns it -- and comparing the returned object against
        the passed one then compares an object with ITSELF. The first
        implementation did exactly that and reported no change at all: an
        extension putting a fact into a mind with no record of having done it,
        which is the one guarantee this seam exists to make.
        """
        def hook(payload, info):
            payload["forbidden_fact"] = "the warp core is failing"
            return payload

        bare.on_character_payload(hook)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        out = extension_runtime.dispatch_character_payload(ctx, 7, {"self": {}})

        assert out["forbidden_fact"] == "the warp core is failing"
        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": 7, "changed": ["forbidden_fact"]}]

    def test_mutating_and_returning_none_is_attributed_too(self, temp_db, bare):
        """The same hole by a shorter route: mutate, then say 'unchanged'."""
        def hook(payload, info):
            payload["briefing"] = "smuggled in"
            return None

        bare.on_character_payload(hook)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        out = extension_runtime.dispatch_character_payload(ctx, 7, {"self": {}})

        assert out["briefing"] == "smuggled in"
        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": 7, "changed": ["briefing"]}]

    def test_a_nested_in_place_edit_is_attributed(self, temp_db, bare):
        """A shallow copy would not have caught this one.

        Copying the payload one level deep leaves the nested objects shared, so
        rewriting the view a mind is given -- the single most consequential
        edit an extension can make -- would compare equal to itself.
        """
        def hook(payload, info):
            payload["perception"]["view"] = "a room with the door open"
            return payload

        bare.on_character_payload(hook)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        extension_runtime.dispatch_character_payload(
            ctx, 7, {"perception": {"view": "a room"}, "self": {}})

        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": 7, "changed": ["perception"]}]

    def test_a_removed_key_is_attributed(self, temp_db, bare):
        def hook(payload, info):
            payload.pop("self", None)
            return payload

        bare.on_character_payload(hook)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        extension_runtime.dispatch_character_payload(
            ctx, 7, {"self": {"name": "Ash"}})

        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": 7, "changed": ["self"]}]

    def test_an_unserialisable_value_does_not_silence_the_record(
            self, temp_db, bare):
        """Silence is the failure mode, so an exotic value must read as changed
        rather than as untouched."""
        class Opaque:
            def __repr__(self):
                raise RuntimeError("no repr for you")

        bare.on_character_payload(
            lambda payload, info: {**payload, "odd": Opaque()})
        ctx = _StubCtx(chat_id=_chat(temp_db))

        extension_runtime.dispatch_character_payload(ctx, 7, {"self": {}})

        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "seams", "char_id": 7, "changed": ["odd"]}]

    def test_an_untouched_payload_records_nothing(self, temp_db, bare):
        bare.on_character_payload(lambda payload, info: None)
        ctx = _StubCtx(chat_id=_chat(temp_db))
        payload = {"self": {"name": "Ash"}}

        assert extension_runtime.dispatch_character_payload(
            ctx, 7, payload) == payload
        assert extension_runtime.routing_notes(ctx) == []

    def test_the_hook_learns_whose_mind_it_is(self, temp_db, bare):
        seen = {}

        def hook(payload, info):
            seen.update({"char_id": info.char_id, "name": info.name,
                         "chat_id": info.chat_id, "turn_idx": info.turn_idx})
            return None

        bare.on_character_payload(hook)
        chat_id = _chat(temp_db)
        extension_runtime.dispatch_character_payload(
            _StubCtx(chat_id=chat_id, idx=11), 7, {}, ("Hinami",))

        assert seen == {"char_id": 7, "name": "Hinami", "chat_id": chat_id,
                        "turn_idx": 11}

    def test_a_throwing_hook_leaves_the_payload_exactly_as_assembled(
            self, temp_db, bare):
        def boom(payload, info):
            raise RuntimeError("hook is broken")

        bare.on_character_payload(boom)
        payload = {"self": {"name": "Ash"}, "perception": {"view": "a room"}}

        assert extension_runtime.dispatch_character_payload(
            _StubCtx(chat_id=_chat(temp_db)), 7, payload) == payload
        assert extension_runtime.observer_failures()["seams"] == 1

    def test_a_hook_returning_a_non_dict_is_ignored(self, temp_db, bare):
        bare.on_character_payload(lambda payload, info: "not a payload")
        payload = {"self": {}}
        assert extension_runtime.dispatch_character_payload(
            _StubCtx(chat_id=_chat(temp_db)), 7, payload) == payload

    def test_hooks_compose_and_each_is_attributed_separately(
            self, temp_db, ext_root):
        for name in ("first", "second"):
            _write_extension(ext_root, name, {
                "id": name, "version": "1.0.0", "ext_api": 1, "name": name,
                "capabilities": {"python": "extension.py"},
            }, {"extension.py": "def register(api):\n    pass\n"})
        _enable("first", "second")
        _api("first").on_character_payload(
            lambda payload, info: {**payload, "a": 1})
        _api("second").on_character_payload(
            lambda payload, info: {**payload, "b": 2})
        ctx = _StubCtx(chat_id=_chat(temp_db))

        out = extension_runtime.dispatch_character_payload(ctx, 7, {})

        assert out == {"a": 1, "b": 2}
        assert sorted(note["ext"] for note in extension_runtime.routing_notes(ctx)) \
            == ["first", "second"]

    def test_the_seam_is_wired_into_character_step(self):
        """The hook is worthless if nothing calls it.

        Read as source rather than by running a turn: a stubbed character turn
        proves less than it costs here, but a seam that silently stops being
        invoked is exactly the failure this file exists to prevent.
        """
        import inspect

        from agents import character

        source = inspect.getsource(character.character_step)
        call = source.index("_extension_character_payload(ctx, cid, payload")
        model = source.index("out = _agent_json(")
        assert call < model, "routing must run before the model sees the payload"


# ------------------------------------------------------------ routes


class TestExtensionRoutes:
    def test_a_registered_route_is_served(self, temp_db, bare):
        bare.add_route("/ping", lambda request: {"pong": request.query.get("q")})

        assert extension_runtime.dispatch_route(
            "seams", "GET", "/ping", query={"q": "hi"}) == {"pong": "hi"}

    def test_chat_id_is_parsed_for_the_route_that_always_wants_it(self, temp_db,
                                                                  bare):
        bare.add_route("/who", lambda request: {"chat": request.chat_id})

        assert extension_runtime.dispatch_route(
            "seams", "GET", "/who", query={"chat_id": "42"}) == {"chat": 42}
        assert extension_runtime.dispatch_route(
            "seams", "GET", "/who", query={"chat_id": "nonsense"}) == {"chat": None}
        assert extension_runtime.dispatch_route(
            "seams", "GET", "/who") == {"chat": None}

    def test_a_method_it_did_not_register_is_not_served(self, temp_db, bare):
        bare.add_route("/only-get", lambda request: {})
        with pytest.raises(ExtensionError, match="POST"):
            extension_runtime.dispatch_route("seams", "POST", "/only-get")

    def test_a_disabled_extension_serves_nothing(self, temp_db, bare):
        bare.add_route("/ping", lambda request: {"pong": True})
        extension_runtime.disable_extension("seams")
        with pytest.raises(ExtensionError, match="not enabled"):
            extension_runtime.dispatch_route("seams", "GET", "/ping")

    def test_a_path_cannot_traverse(self, bare):
        with pytest.raises(ExtensionError):
            bare.add_route("/../../secret", lambda request: {})

    def test_a_route_is_namespaced_under_x(self, bare):
        """`/x/` is why an extension cannot shadow `enable`, `state` or `asset`.

        Without the segment, an extension registering `/disable` would sit at
        the same URL as the host route that turns it off.
        """
        assert bare.add_route("/disable", lambda request: {}) \
            == "/api/extensions/seams/x/disable"

    def test_leading_and_trailing_slashes_do_not_make_two_routes(self, temp_db,
                                                                 bare):
        bare.add_route("history/", lambda request: {"ok": True})
        assert extension_runtime.dispatch_route(
            "seams", "GET", "history") == {"ok": True}
        assert extension_runtime.dispatch_route(
            "seams", "GET", "/history/") == {"ok": True}

    def test_the_demo_serves_its_own_history(self, temp_db, real_ext_root):
        _enable(DEMO)
        chat_id = _chat(temp_db)
        from db import wset
        wset(chat_id, f"ext:{DEMO}",
             {"cohesion": 61.0, "history": [{"turn": 1, "delta": 3}]})

        out = extension_runtime.dispatch_route(
            DEMO, "GET", "/history", query={"chat_id": str(chat_id)})

        assert out["cohesion"] == 61.0
        assert out["history"] == [{"turn": 1, "delta": 3}]


# ------------------------------------------------------------ hot-loadable UI


class TestHotLoadableAssets:
    def test_one_extensions_script_is_served_on_its_own(self, temp_db,
                                                        real_ext_root):
        _enable(DEMO)
        script = extension_runtime.extension_script(DEMO)
        assert "registerSidebarTab" in script
        assert f'Sonder._begin("{DEMO}")' in script

    def test_a_disabled_extension_serves_no_script_and_no_style(
            self, temp_db, real_ext_root):
        """The assertion that matters: enable is hot BECAUSE disable is empty.

        If a disabled extension still served its script, the host could not
        tell "not loaded yet" from "loaded and inert", and disable would leave
        a panel on the page.
        """
        _enable()
        assert extension_runtime.extension_script(DEMO) == ""
        assert extension_runtime.extension_styles(DEMO) == ""
        assert extension_runtime.ui_bundle() == ""
        assert extension_runtime.ui_styles() == ""

    def test_styles_are_served_and_fenced_by_owner(self, temp_db,
                                                   real_ext_root):
        _enable(DEMO)
        styles = extension_runtime.ui_styles()
        assert f"/* extension: {DEMO} */" in styles
        assert ".ext-cohesion-demo-card" in styles

    def test_a_declared_stylesheet_is_actually_reachable(self, temp_db,
                                                         real_ext_root):
        """`capabilities.ui.css` was parsed and never served for a whole release.

        A manifest field that is read and ignored is the invisible-failure
        pattern this repo keeps re-learning: nothing errors, nothing warns, and
        the author's stylesheet simply never arrives.
        """
        _enable(DEMO)
        ext = extension_runtime.installed_extensions()[DEMO]
        assert ext.css_entry
        assert extension_runtime.extension_styles(DEMO).strip()

    def test_each_extension_gets_its_own_scope_in_the_bundle(self, temp_db,
                                                             ext_root):
        """Two extensions declaring the same top-level const must both survive.

        Concatenation puts every extension's top level in ONE script, so
        `const EXT` twice is a SyntaxError that kills the whole bundle -- every
        extension after the collision included.
        """
        for name in ("aaa", "bbb"):
            _write_extension(ext_root, name, {
                "id": name, "version": "1.0.0", "ext_api": 1, "name": name,
                "capabilities": {"ui": {"js": "panel.js"}},
            }, {"panel.js": 'const EXT = "%s";\n' % name})
        _enable("aaa", "bbb")

        bundle = extension_runtime.ui_bundle()
        assert bundle.count("(function () {") == 2
        # Both declarations present, neither at the shared top level.
        assert bundle.count("const EXT") == 2

    def test_a_throwing_script_cannot_take_the_next_extension_down(
            self, temp_db, ext_root):
        for name in ("aaa", "bbb"):
            _write_extension(ext_root, name, {
                "id": name, "version": "1.0.0", "ext_api": 1, "name": name,
                "capabilities": {"ui": {"js": "panel.js"}},
            }, {"panel.js": "throw new Error('nope');\n"})
        _enable("aaa", "bbb")

        bundle = extension_runtime.ui_bundle()
        # Each extension's body sits inside its own try, and the finally
        # closes attribution even when the body threw -- otherwise `_owner`
        # stays set and the NEXT extension's registrations are misattributed.
        assert bundle.count("try {") == 2
        assert bundle.count("Sonder._end()") == 2

    def test_safe_mode_serves_nothing_at_all(self, temp_db, real_ext_root,
                                             monkeypatch):
        _enable(DEMO)
        monkeypatch.setenv(extension_runtime.SAFE_MODE_ENV, "1")
        assert extension_runtime.extension_script(DEMO) == ""
        assert extension_runtime.extension_styles(DEMO) == ""
        assert extension_runtime.ui_styles() == ""


# ------------------------------------------------------------ specialists


class TestDirectorSpecialists:
    """A seventh Director family, authored outside this tree.

    The reason this needed an API rather than a documented monkeypatch: the
    six registries a specialist lives in are not independent. `SPECIALISTS` is
    read live by `_dispatch_specialists`, which then indexes `_CHANNEL_GATES`
    by channel -- so patching five of six is not a degraded specialist, it is a
    KeyError inside the Director on every beat.
    """

    def test_a_registered_family_joins_the_fan_out(self, temp_db, bare):
        from agents import director

        full = bare.add_director_specialist(
            "morale", channels=["morale_ops"],
            prompt="Judge the crew's morale from the beat.")

        assert full == "ext:seams:morale"
        assert full in director.SPECIALISTS
        assert director.SPECIALISTS[full]["channels"] == ("ext:seams:morale_ops",)

    def test_channels_are_namespaced_so_a_family_cannot_steal_one(
            self, temp_db, bare):
        """Owning `attire` would silently replace the body specialist's work.

        The merge assigns a channel to whichever family was scoped to it, so a
        collision is not an error downstream -- it is a takeover.
        """
        from agents import director

        bare.add_director_specialist(
            "wardrobe", channels=["attire"], prompt="Track clothing.")

        assert director._CHANNEL_SPECIALISTS["attire"] == "body"
        assert director._CHANNEL_SPECIALISTS["ext:seams:attire"] == "ext:seams:wardrobe"

    def test_two_extensions_cannot_claim_the_same_channel(self, temp_db,
                                                          ext_root):
        for name in ("first", "second"):
            _write_extension(ext_root, name, {
                "id": name, "version": "1.0.0", "ext_api": 1, "name": name,
                "capabilities": {"python": "extension.py"},
            }, {"extension.py": "def register(api):\n    pass\n"})
        _enable("first", "second")
        _api("first").add_director_specialist(
            "a", channels=["shared"], prompt="one")
        # Namespacing means they do NOT collide -- each owns its own.
        _api("second").add_director_specialist(
            "b", channels=["shared"], prompt="two")

        from agents import director
        assert director._CHANNEL_SPECIALISTS["ext:first:shared"] == "ext:first:a"
        assert director._CHANNEL_SPECIALISTS["ext:second:shared"] == "ext:second:b"

    def test_the_channel_owner_map_is_rebuilt_not_frozen_at_import(
            self, temp_db, bare):
        """It used to be a module-level comprehension over `SPECIALISTS`.

        A family registered afterwards was then invisible to
        `_route_repair_omissions` while being perfectly visible to dispatch --
        a split that routes a repair to nobody and reports nothing.
        """
        from agents import director

        bare.add_director_specialist(
            "weather", channels=["front"], prompt="Track the weather.")
        assert "ext:seams:front" in director._CHANNEL_SPECIALISTS

    def test_a_family_is_gated_and_defaults_to_failing_open(self, temp_db,
                                                            bare):
        from agents import director

        bare.add_director_specialist(
            "always", channels=["a"], prompt="p")
        bare.add_director_specialist(
            "never", channels=["b"], prompt="p", gate=lambda facts: False)

        facts = {"physical_beat": True}
        assert director._CHANNEL_GATES["ext:seams:a"](facts) is True
        assert director._CHANNEL_GATES["ext:seams:b"](facts) is False
        assert director._CHANNEL_GATES["ext:seams:a"]({"physical_beat": False}) is False

    def test_dispatch_scopes_the_family_like_any_other(self, temp_db, bare):
        from agents import director

        bare.add_director_specialist(
            "morale", channels=["ops"], prompt="p",
            gate=lambda facts: facts["physical_beat"])
        facts = {key: False for key in (
            "physical_beat", "speech_present", "anyone_wears",
            "active_conditions", "vitals_tracked", "overlays_present",
            "contacts_standing", "containment_active", "scales_active",
            "material_effects_declared", "notices_in_scene", "reports_carried",
            "destructible_entity", "crowds_present", "couriers_present",
            "unratified_claims_present", "offscreen_planning_enabled")}

        cold = director._dispatch_specialists(None, None, facts)
        assert cold["ext:seams:morale"]["run"] is False

        hot = director._dispatch_specialists(None, None,
                                             {**facts, "physical_beat": True})
        assert hot["ext:seams:morale"]["run"] is True
        assert hot["ext:seams:morale"]["scope"] == ["ext:seams:ops"]

    def test_disabling_takes_the_family_back_out(self, temp_db, bare):
        """A disabled extension whose specialist stayed would be dispatched --
        and paid for -- on every beat forever."""
        from agents import director

        bare.add_director_specialist("morale", channels=["ops"], prompt="p")
        extension_runtime.disable_extension("seams")

        assert "ext:seams:morale" not in director.SPECIALISTS
        assert "ext:seams:ops" not in director._CHANNEL_GATES
        assert "ext:seams:ops" not in director._CHANNEL_SPECIALISTS

    def test_the_engines_own_six_are_untouched_throughout(self, temp_db, bare):
        from agents import director

        before = {name: spec["channels"]
                  for name, spec in director.SPECIALISTS.items()
                  if not spec.get("ext_id")}
        bare.add_director_specialist("morale", channels=["ops"], prompt="p")
        extension_runtime.disable_extension("seams")
        after = {name: spec["channels"]
                 for name, spec in director.SPECIALISTS.items()
                 if not spec.get("ext_id")}

        assert before == after
        assert set(before) == {"body", "social", "contact", "objects",
                               "spatial", "offscreen"}

    def test_a_family_with_no_channels_or_no_prompt_is_refused(self, temp_db,
                                                               bare):
        for kwargs in ({"channels": [], "prompt": "p"},
                       {"channels": ["ops"], "prompt": "  "},
                       {"channels": [""], "prompt": "p"}):
            with pytest.raises(ValueError):
                bare.add_director_specialist("bad", **kwargs)

    def test_it_runs_loose_because_schema_map_cannot_know_it(self, temp_db,
                                                             bare, monkeypatch):
        """An extension owns the shape of its own channels.

        `_agent_json` validates against `schemas.SCHEMA_MAP`, which only knows
        this engine's steps, so a registered family must take the parse and not
        the schema -- the same split `api.llm_json` makes.
        """
        import schemas
        from agents import director

        full = bare.add_director_specialist(
            "morale", channels=["ops"], prompt="Judge morale.")
        assert full not in schemas.SCHEMA_MAP

        captured = {}

        def fake_complete(role, system, user, **kwargs):
            captured.update({"role": role, "system": system})
            return '{"ext:seams:ops": [{"note": "steady"}]}'

        monkeypatch.setattr("providers.chat_complete", fake_complete)
        out = director._extension_specialist_call(
            director.SPECIALISTS[full], ["ext:seams:ops"], {"beat": "x"})
        # The permissive parse lives in extension_runtime, not in the Director:
        # `test_stage_modules_stay_on_strict_path` forbids `jparse` in a stage
        # module, and that rule is protecting the engine's own stages, whose
        # output DOES reach commit.py.
        assert "jparse(" not in io_read("agents/director.py")

        assert out == {"ext:seams:ops": [{"note": "steady"}]}
        assert "Judge morale." in captured["system"]
        assert "ext:seams:ops" in captured["system"]


# ------------------------------------------------------------ introspection


class TestRegistrationListings:
    def test_the_host_can_see_what_was_registered(self, temp_db, bare):
        bare.add_route("/one", lambda request: {}, methods=("GET", "POST"))
        bare.add_commit_domain("keep", lambda view: None, on_error="fail")

        assert extension_runtime.registered_routes() == [
            {"ext_id": "seams", "method": "GET", "path": "/one"},
            {"ext_id": "seams", "method": "POST", "path": "/one"},
        ]
        assert extension_runtime.registered_commit_domains() == [
            {"ext_id": "seams", "name": "keep", "on_error": "fail"}]

        bare.add_director_specialist("morale", channels=["ops"], prompt="p")
        assert extension_runtime.registered_specialists() == [
            {"ext_id": "seams", "name": "ext:seams:morale"}]

    def test_disabling_forgets_every_registration(self, temp_db, bare):
        bare.add_route("/one", lambda request: {})
        bare.add_commit_domain("keep", lambda view: None)
        bare.on_character_payload(lambda payload, info: None)
        bare.add_director_specialist("morale", channels=["ops"], prompt="p")

        extension_runtime.disable_extension("seams")

        assert extension_runtime.registered_routes() == []
        assert extension_runtime.registered_commit_domains() == []
        assert extension_runtime.registered_specialists() == []
        assert extension_runtime.dispatch_character_payload(
            _StubCtx(chat_id=_chat(temp_db)), 7, {"a": 1}) == {"a": 1}
