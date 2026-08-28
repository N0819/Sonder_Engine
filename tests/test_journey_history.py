

class TestTheRoadWasShared:
    """A character briefed as the player's travelling companion arrived
    knowing nobody. Measured on a market-town playtest: sixteen generated
    journey events, ZERO naming the player, and one relationship edge to
    "person of unremarkable appearance" at trust 0.06, formed on turn 4 --
    during play. The generator is handed a sheet, some lore and an arrival
    brief, and nothing that says the road was shared, so it wrote one
    person's past correctly and the shared half did not exist.
    See `docs/UNBUILT.md` 1.99f.
    """

    def test_the_flag_rides_every_route_that_produces_a_past(self):
        from story.history_routing import resolve_character_history_route

        sheet = {"identity": {"name": "Elara"},
                 "knowledge": {"public_history": "A wandering herbalist."}}

        for mode in ("generated_journey", "resident", "visitor",
                     "moving_institution", "auto"):
            shared = resolve_character_history_route(
                sheet, requested={"mode": mode, "with_player": True})
            alone = resolve_character_history_route(
                sheet, requested={"mode": mode})
            assert shared["with_player"] is True, mode
            assert alone["with_player"] is False, mode

    def test_the_auto_paths_own_local_did_not_eat_the_flag(self):
        """`resolve_character_history_route`'s auto branch already binds
        `shared` to the words a public history and the opening have in common.
        Naming the new flag `shared` too put a word LIST on the route and the
        first test written for it caught that."""
        from story.history_routing import resolve_character_history_route

        route = resolve_character_history_route(
            {"identity": {"name": "Elara"}}, requested="auto")

        assert route["with_player"] is False
        assert isinstance(route["with_player"], bool)

    def test_the_player_is_addressed_by_uid_not_by_row_id(self, temp_db):
        """1.99g's discipline: everything built around the player keys on the
        persona's `resource_uid`, which survives archive, branch and clone, so
        a player memory bank later is a new writer rather than a retrofit
        through every ledger. A persona row id is local to an install."""
        import json as _json
        import time as _time
        from story.journey_history import companion_of

        pid = temp_db.qi(
            "INSERT INTO personas(name,sheet,source,resource_uid) "
            "VALUES(?,?,?,?)",
            ("Alex Reed", _json.dumps({"name": "Alex Reed"}), "test",
             "persona_stable_uid"))
        cid = temp_db.qi(
            "INSERT INTO chats(name,persona_id,scenario,created) "
            "VALUES(?,?,?,?)", ("market", pid, "", _time.time()))

        found = companion_of(cid, {"with_player": True})

        assert found["resource_uid"] == "persona_stable_uid"
        assert found["name"] == "Alex Reed"
        assert companion_of(cid, {}) is None, "absent flag, absent companion"
