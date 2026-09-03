"""The five-rung ladder becomes one question: may minds act unwatched.

Owner ruling 2026-09-04. Charter is unconditional, so the ladder no longer
decides whether the world moves; the only thing left for a host to answer is
whether a mind nobody is watching may think and act. The villain ladder
(`antagonist_ladder`) stays as a placeholder, so its floor must keep firing
with cognition off.

The line falls exactly where the code already spends. Measured over
`world/offscreen.py`: `advance_epoch`, `advance_reactive_plans`,
`apply_plan_ops` and `stochastic_ticks` hold no model seam, while
`schedule_profile_ticks` composes through `profile_summary_record` and
`schedule_agent_ticks` through `agent_proposal`. So OFF is the `reactive`
rung -- every deterministic path still runs -- and ON is `character_agent`.
The rung survives underneath as the mechanism the four living-world
approaches are still written against; what goes is the host having to read a
five-word vocabulary to answer one question.
"""
import pytest

from story.scene import (COGNITION_OFF_RUNG, COGNITION_ON_RUNG,
                         OFFSCREEN_COGNITION_DEFAULT, dialogue_config,
                         normalize_offscreen_cognition, offscreen_life_allows)


def _chat(db):
    import time
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Cognition", "", time.time()))


class TestTheToggle:
    def test_it_defaults_on_because_that_is_what_the_ladder_already_did(self):
        assert OFFSCREEN_COGNITION_DEFAULT is True

    @pytest.mark.parametrize("value,expected", [
        (True, True), (False, False), ("on", True), ("off", False),
        ("1", True), ("0", False), ("true", True), ("false", False),
    ])
    def test_it_reads_the_ordinary_spellings(self, value, expected):
        assert normalize_offscreen_cognition(value) is expected

    def test_an_unreadable_value_falls_to_the_default_never_to_off(self):
        assert normalize_offscreen_cognition("sideways") is True
        assert normalize_offscreen_cognition(None) is True


class TestWhatEachSideBuys:
    def test_off_still_permits_every_deterministic_path(self):
        for rung in ("inert", "deterministic", "reactive"):
            assert offscreen_life_allows(COGNITION_OFF_RUNG, rung)

    def test_off_refuses_exactly_the_two_paths_that_spend(self):
        assert not offscreen_life_allows(COGNITION_OFF_RUNG, "stochastic")
        assert not offscreen_life_allows(COGNITION_OFF_RUNG, "character_agent")

    def test_the_villain_ladders_floor_still_fires_with_cognition_off(self):
        from world.living_world import LIVING_WORLD_REQUIRES
        floor = LIVING_WORLD_REQUIRES["antagonist_ladder"]["floor"]
        assert offscreen_life_allows(COGNITION_OFF_RUNG, floor), (
            "the villain ladder is kept as a placeholder, so its floor may "
            "not be collateral of the collapse")

    def test_on_permits_everything(self):
        for rung in ("inert", "deterministic", "reactive", "stochastic",
                     "character_agent"):
            assert offscreen_life_allows(COGNITION_ON_RUNG, rung)


class TestTheStoredConfig:
    def test_a_chat_that_answered_nothing_gets_the_default_both_ways(self,
                                                                    temp_db):
        cid = _chat(temp_db)
        cfg = dialogue_config(cid)
        assert cfg["offscreen_cognition"] is True
        assert cfg["offscreen_life"] == COGNITION_ON_RUNG

    def test_the_toggle_drives_the_rung(self, temp_db):
        cid = _chat(temp_db)
        temp_db.wset(cid, "dialogue_config", {"offscreen_cognition": False})
        cfg = dialogue_config(cid)
        assert cfg["offscreen_life"] == COGNITION_OFF_RUNG
        assert cfg["offscreen_cognition"] is False

    @pytest.mark.parametrize("rung,expected", [
        ("inert", False), ("deterministic", False), ("reactive", False),
        ("stochastic", True), ("character_agent", True),
    ])
    def test_a_story_that_stored_a_rung_keeps_its_answer(self, temp_db, rung,
                                                         expected):
        """Migration by reading, not by rewriting: an existing chat's rung is
        still the rung it stored, and the toggle is derived from it, so no
        running story changes behaviour on the deploy that lands this."""
        cid = _chat(temp_db)
        temp_db.wset(cid, "dialogue_config", {"offscreen_life": rung})
        cfg = dialogue_config(cid)
        assert cfg["offscreen_life"] == rung
        assert cfg["offscreen_cognition"] is expected

    def test_an_explicit_toggle_outranks_a_stale_stored_rung(self, temp_db):
        cid = _chat(temp_db)
        temp_db.wset(cid, "dialogue_config", {
            "offscreen_life": "character_agent", "offscreen_cognition": False})
        assert dialogue_config(cid)["offscreen_life"] == COGNITION_OFF_RUNG


class TestTheRoute:
    def test_the_panel_saves_and_reads_back_the_toggle(self, temp_db):
        from web import app
        cid = _chat(temp_db)

        saved = app.dlg_put(cid, {"autonomy": 50, "offscreen_cognition": False})

        assert saved["offscreen_cognition"] is False
        assert saved["offscreen_life"] == COGNITION_OFF_RUNG
        assert app.dlg_get(cid)["offscreen_cognition"] is False

    def test_an_extension_may_still_set_the_rung_directly(self, temp_db):
        """`api.provision_story(offscreen_life=...)` is a published contract
        and archives carry the rung, so the ladder stays writable."""
        from web import app
        cid = _chat(temp_db)

        saved = app.dlg_put(cid, {"autonomy": 50,
                                  "offscreen_life": "deterministic"})

        # The stored blob is the rung alone, so nothing derived shadows what
        # the caller said; the toggle is read back OUT of it.
        assert saved["offscreen_life"] == "deterministic"
        assert "offscreen_cognition" not in saved
        assert dialogue_config(cid)["offscreen_cognition"] is False
        assert dialogue_config(cid)["offscreen_life"] == "deterministic"
