

class TestTheFollowLabelNamesTheRoleActuallyFollowed:
    """Eight roles do not inherit `default`, and the panel said they did.

    Reported live: "the director fanout seems to only be using the director
    role setting instead of what i set for specialists" -- from a host who
    had deliberately left the six specialists blank, reading the label
    "follow default" as meaning they would follow `default`. They follow
    `director`. With both unset the two are the same model and nothing
    shows; the moment `director` is set to a writing model, six specialists
    silently move onto it.
    """

    def test_the_fallback_map_is_exposed_to_the_client(self):
        src = open("app.py", encoding="utf-8").read()
        boot = src[src.index("def bootstrap"):]
        assert '"role_fallbacks":' in boot

    def test_the_panel_reads_the_map_rather_than_hardcoding_default(self):
        js = open("static/js/settings.js", encoding="utf-8").read()
        assert 'role_fallbacks' in js
        # The bare claim must be gone -- it is only true for the roles that
        # have no entry in the map.
        assert '"follow default"' not in js

    def test_every_specialist_follows_the_director_not_the_default(self):
        from providers import ROLE_FALLBACKS, ROLES

        specialists = [r for r in ROLES if r.startswith("director_")]
        assert specialists, "the specialist roles went missing"
        for role in specialists:
            assert ROLE_FALLBACKS.get(role) == "director", role
