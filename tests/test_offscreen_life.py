"""How much life the cast is permitted while nobody is watching.

`docs/OFFSCREEN_LIFE_DESIGN.md` specified a ladder and `schemas.BehaviorController`
declared it; nothing consumed either. Meanwhile the mapping stage was asked for
off-screen ticks on every scene change, unconditionally, and commit logged
whatever came back — so the engine had an off-screen simulation with no dial,
no bound, and no reader.

This is step 2 of that document's build order: the ladder becomes real and
settable. It is a CEILING, not an instruction — nothing is obliged to act at
any level, because the architecture's cost claim is that cost scales with
dramatic density rather than story length, and a setting does not get to break
that.
"""

from __future__ import annotations

import time

from commit import normalize_offscreen_events
from scene import (
    OFFSCREEN_LIFE_DESCRIPTIONS, OFFSCREEN_LIFE_LADDER, dialogue_config,
    normalize_offscreen_life, offscreen_life_allows,
)


class TestTheLadder:
    def test_it_is_the_behavior_controller_ladder(self):
        """The rungs are not new vocabulary — `schemas.BehaviorController` has
        declared them since before anything read them, and two spellings of the
        same idea would diverge and then disagree."""
        from schemas import BehaviorController

        declared = {c.value for c in BehaviorController}
        for rung in OFFSCREEN_LIFE_LADDER:
            assert rung in declared, rung

    def test_every_rung_has_a_description(self):
        assert set(OFFSCREEN_LIFE_DESCRIPTIONS) == set(OFFSCREEN_LIFE_LADDER)

    def test_a_level_permits_everything_below_it(self):
        assert offscreen_life_allows("character_agent", "stochastic")
        assert offscreen_life_allows("stochastic", "stochastic")
        assert offscreen_life_allows("stochastic", "deterministic")
        assert not offscreen_life_allows("deterministic", "stochastic")
        assert not offscreen_life_allows("inert", "deterministic")
        assert not offscreen_life_allows("stochastic", "character_agent")

    def test_an_unknown_rung_permits_nothing(self):
        assert not offscreen_life_allows("character_agent", "telepathy")


class TestAnUnreadableValueFallsToTheDefault:
    """Never to the floor. This codebase has met the opposite failure — a term
    an enum could not read falling to the mildest reading and inverting the
    meaning of the setting (see the weather `_SYNONYMS` note in AGENTS.md). A
    typo must not quietly switch a story's off-screen life off."""

    def test_nonsense_becomes_the_default(self):
        assert normalize_offscreen_life("simulate everything") == "stochastic"
        assert normalize_offscreen_life(None) == "stochastic"
        assert normalize_offscreen_life("") == "stochastic"

    def test_case_and_padding_are_tolerated(self):
        assert normalize_offscreen_life("  CHARACTER_AGENT ") == "character_agent"


class TestTheDefaultPreservesWhatTheEngineAlreadyDid:
    def test_a_chat_that_never_set_it_gets_the_shipped_behaviour(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        config = dialogue_config(chat_id)
        assert config["offscreen_life"] == "stochastic"
        assert config["max_offscreen_actors"] == 3

    def test_the_default_is_the_rung_that_was_already_running(self):
        """Turning a setting on must not silently change a running story, and
        the ungated behaviour was exactly this rung: seeded ticks for dormant
        actors at meaningful world boundaries."""
        from scene import OFFSCREEN_LIFE_DEFAULT

        assert OFFSCREEN_LIFE_DEFAULT == "stochastic"
        assert offscreen_life_allows(OFFSCREEN_LIFE_DEFAULT, "stochastic")

    def test_a_stored_nonsense_value_does_not_survive_a_read(self, temp_db):
        from db import wset

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        wset(chat_id, "dialogue_config",
             {"offscreen_life": "maximum", "max_offscreen_actors": "lots"})
        config = dialogue_config(chat_id)
        assert config["offscreen_life"] == "stochastic"
        assert config["max_offscreen_actors"] == 3

    def test_the_cap_is_bounded_on_read_as_well_as_on_write(self, temp_db):
        from db import wset

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        wset(chat_id, "dialogue_config", {"max_offscreen_actors": 900})
        assert dialogue_config(chat_id)["max_offscreen_actors"] == 12


class TestOneShapeForATick:
    """`MappingCommitOut.offscreen_events` is typed `list[dict]` with no inner
    model, so the model invented a shape per call. All four below are verbatim
    from the live logs of eight different chats, in the same field."""

    def test_every_live_shape_normalizes(self):
        events = normalize_offscreen_events([
            {"actor": "reyet_solan", "tick": "In sickbay, Reyet Solan rests."},
            {"event": "Tamamo, far away at the shrine, feels a faint tug."},
            {"who": "Tamamo", "event": "Tamamo senses a distant shift."},
            {"description": "Picard reviews mission logs in his ready room."},
        ])
        assert [e["actor"] for e in events] == ["reyet_solan", "", "Tamamo", ""]
        assert all(e["tick"] for e in events)
        assert all(set(e) == {"actor", "tick"} for e in events)

    def test_an_actorless_tick_keeps_an_empty_actor(self):
        """Inventing one would be worse than admitting the tick is about the
        world rather than about a person."""
        events = normalize_offscreen_events([{"event": "The tide goes out."}])
        assert events == [{"actor": "", "tick": "The tide goes out."}]

    def test_junk_is_dropped_rather_than_stored(self):
        assert normalize_offscreen_events([{}, None, 7, {"actor": "X"}]) == []
        assert normalize_offscreen_events("not a list") == []
        assert normalize_offscreen_events(None) == []

    def test_a_tick_is_bounded(self):
        long = normalize_offscreen_events([{"event": "x " * 900}])
        assert len(long[0]["tick"]) <= 600


class TestTheModelIsOutOfTheTickBusiness:
    """Step 4 of docs/PROPOSAL_2026-08-06.md section 1.2: the shipped
    stochastic rung cost a model call (ticks rode the mapping_commit payload
    and its `tick_seed` seeded nothing — no RNG anywhere in commit.py ever
    consumed it). The design specifies a seeded draw against standing
    intentions with NO model call, so low resolution is free for the whole
    cast rather than affordable for six of them."""

    def test_the_dormant_cast_is_never_offered_to_the_model(self):
        """Withheld at every level, not gated: asking a lore validator to
        also author offscreen life was an unadjudicated authoring channel
        wearing a payload field."""
        import inspect

        import commit

        src = inspect.getsource(commit.prepare_mapping_commit)
        assert "dormant_actors" not in src
        assert "tick_seed" not in src

    def test_the_prompt_no_longer_asks_for_ticks(self):
        """A prompt clause that survives its wiring is an instruction the
        model can still obey into a field nobody reads — or worse, one
        somebody still writes."""
        from prompts import get_prompt

        text = get_prompt("mapping_commit")
        assert "OFF-SCREEN LIFE" not in text
        assert "offscreen_events" not in text

    def test_scene_changed_still_reports_the_scene(self):
        """Overloading it to gate off-screen life would have made a payload lie
        about the world to enforce a setting."""
        import inspect

        import commit

        src = inspect.getsource(commit.prepare_mapping_commit)
        assert '"scene_changed": bool(ctx.director_establish),' in src

    def test_a_volunteered_tick_is_refused_on_the_write_path(self):
        """The model can volunteer a field nobody asked for; the write path
        must refuse it at EVERY level, because a model-authored tick is an
        unadjudicated authoring channel whatever the setting says."""
        import inspect

        import commit

        src = inspect.getsource(commit.commit_mapping)
        assert "normalize_offscreen_events" in src
        assert "model-volunteered" in src

    def test_the_seeded_draw_is_gated_on_the_same_rung(self):
        """The ladder still governs; only the mechanism changed. An author
        who set `deterministic` must not start getting stochastic ticks
        because the ticks became cheap."""
        import inspect

        import commit

        import offscreen

        mapping_src = inspect.getsource(commit.commit_mapping)
        epoch_src = inspect.getsource(offscreen.advance_epoch)
        assert "stochastic_ticks" not in mapping_src
        assert 'offscreen_life_allows(cfg.get("offscreen_life"), "stochastic")' in epoch_src
        assert "stochastic_ticks" in epoch_src

    def test_the_tick_does_not_depend_on_mapping_having_work(self):
        """Mapping's skip path is common. Off-screen life is its own commit
        domain so a turn with no new lore still gets a real epoch."""
        import inspect

        import commit

        src = inspect.getsource(commit._commit_all_locked)
        assert '"offscreen_epoch"' in src
        assert "commit_offscreen_epoch" in src
        assert "advance_epoch" in inspect.getsource(commit.commit_offscreen_epoch)


class TestFullIsPermissionNotBehaviour:
    def test_it_is_documented_as_unbuilt_where_a_reader_will_look(self):
        import scene

        source = scene.__doc__ or ""
        import inspect
        source = inspect.getsource(scene)
        marker = source[source.index("What the cast is allowed to do"):
                        source.index("OFFSCREEN_LIFE_LADDER = (")]
        assert "Permission, not behaviour" in marker
        assert "OFFSCREEN_LIFE_DESIGN" in marker

    def test_the_ui_says_so_too(self):
        from pathlib import Path

        js = (Path(__file__).resolve().parents[1]
              / "static/js/settings.js").read_text(encoding="utf-8")
        block = js[js.index('"Off-screen life"'):js.index('"Background life"')]
        assert block.count("Not built yet") == 1  # character_agent only
        assert "behaves as stochastic" in block

    def test_the_ui_renders_the_engines_own_ladder(self):
        """Listing the rungs in the menu would drift the first time one was
        added."""
        from pathlib import Path

        js = (Path(__file__).resolve().parents[1]
              / "static/js/settings.js").read_text(encoding="utf-8")
        assert "c.offscreen_life_levels" in js


def test_the_api_round_trips_the_setting(temp_db):
    import app

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    saved = app.dlg_put(chat_id, {"autonomy": 50, "offscreen_life": "character_agent",
                                  "max_offscreen_actors": 5})
    assert saved["offscreen_life"] == "character_agent"
    assert saved["max_offscreen_actors"] == 5
    assert app.dlg_get(chat_id)["offscreen_life"] == "character_agent"


def test_the_api_normalizes_rather_than_rejecting(temp_db):
    import app

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    saved = app.dlg_put(chat_id, {"autonomy": 50, "offscreen_life": "sideways"})
    assert saved["offscreen_life"] == "stochastic"


def test_a_cap_of_zero_silences_ticks_without_losing_the_level(temp_db):
    """The bound and the permission are separate answers, and a cap of zero is
    a legitimate way to say "not right now"."""
    import app

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    saved = app.dlg_put(chat_id, {"autonomy": 50, "offscreen_life": "character_agent",
                                  "max_offscreen_actors": 0})
    assert saved["offscreen_life"] == "character_agent"
    assert saved["max_offscreen_actors"] == 0
