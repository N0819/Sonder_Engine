

class TestBlankRowsFollowDefault:
    """"follow default" on a blank row means `default`, on every row.

    Reported live: "the director fanout seems to only be using the director
    role setting instead of what i set for specialists" -- from a host who
    had deliberately left the six specialists blank so they would all sit on
    one cheap model. They followed `director`, so setting `director` to a
    writing model silently moved six specialists onto it. `f706da7` made the
    panel name the real parent; this makes the parent be the one the label
    always claimed. `utility` (was `mapping`) and `repair` (was `utility`)
    went with them -- eight hidden inheritances, none of them visible at the
    moment a host makes the choice they contradict.
    """

    def test_no_role_has_a_hidden_parent(self):
        from llm.providers import ROLE_FALLBACKS

        assert ROLE_FALLBACKS == {}, (
            "a role with a non-default parent is invisible in the panel "
            "unless the label renders it -- see the bootstrap comment in "
            "app.py, and reasoning_effort_for, which does NOT follow this map"
        )

    def test_every_unset_role_resolves_to_the_default_model(self, monkeypatch):
        """The behavioural claim, not just the map's contents: with only
        `default` configured, every role in the panel lands on it."""
        from llm import providers

        monkeypatch.setattr(
            providers, "provider",
            lambda name: {"name": name, "kind": "openai",
                          "base_url": "http://x", "api_key": ""})
        monkeypatch.setattr(
            providers, "agent_models",
            lambda: {"default": {"provider": "frontier", "model": "big"}})

        for role in providers.ROLES:
            if role == "embeddings":
                # A different KIND of model; never inherited. See the panel
                # note in settings.js.
                continue
            prov, model, _cfg = providers.resolve_role(role)
            assert (prov["name"], model) == ("frontier", "big"), role

    def test_setting_the_director_does_not_move_the_specialists(self, monkeypatch):
        """The reported defect, pinned. A host who configures `director` and
        leaves the specialists blank keeps them on `default`."""
        from llm import providers

        monkeypatch.setattr(
            providers, "provider",
            lambda name: {"name": name, "kind": "openai",
                          "base_url": "http://x", "api_key": ""})
        monkeypatch.setattr(providers, "agent_models", lambda: {
            "default": {"provider": "cheap", "model": "small"},
            "director": {"provider": "frontier", "model": "big"},
        })

        specialists = [r for r in providers.ROLES if r.startswith("director_")]
        assert specialists, "the specialist roles went missing"
        for role in specialists:
            prov, model, _cfg = providers.resolve_role(role)
            assert (prov["name"], model) == ("cheap", "small"), role

        # The Director's own row is untouched by any of this.
        prov, model, _cfg = providers.resolve_role("director")
        assert (prov["name"], model) == ("frontier", "big")

    def test_an_explicit_row_still_wins(self, monkeypatch):
        from llm import providers

        monkeypatch.setattr(
            providers, "provider",
            lambda name: {"name": name, "kind": "openai",
                          "base_url": "http://x", "api_key": ""})
        monkeypatch.setattr(providers, "agent_models", lambda: {
            "default": {"provider": "cheap", "model": "small"},
            "director_body": {"provider": "chosen", "model": "picked"},
        })

        prov, model, _cfg = providers.resolve_role("director_body")
        assert (prov["name"], model) == ("chosen", "picked")

    def test_the_fallback_map_is_exposed_to_the_client(self):
        """Kept published even while empty: the panel renders the label from
        it, so a future non-default parent shows up without the client
        learning a second copy of the rule."""
        src = open("web/app.py", encoding="utf-8").read()
        boot = src[src.index("def bootstrap"):]
        assert '"role_fallbacks":' in boot

    def test_the_panel_reads_the_map_rather_than_hardcoding_default(self):
        js = open("static/js/settings.js", encoding="utf-8").read()
        assert 'role_fallbacks' in js
        # Still built from the map rather than asserted as a bare string:
        # the map being empty is what makes "follow default" true, not a
        # literal in the client that would survive the map changing.
        assert '"follow default"' not in js
