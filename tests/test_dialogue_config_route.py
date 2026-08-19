"""What a save to the dialogue panel is allowed to erase.

`PUT /api/chats/{cid}/dialogue_config` is the only production writer of the
`dialogue_config` blob, and it writes a WHOLE-CONFIG REPLACEMENT. That is the
right shape for the fields the panel renders -- an unchecked checkbox has to
be able to turn something off -- and the wrong shape for every knob the panel
does NOT render, because the route's own hardcoded defaults then stand in for
values a host set another way.

Measured (AUDIT_MINDS finding 10): `initial_parallel_reactors` is read by
`agents/loops.py`, defaulted by `story/scene.py`, and named in `Design.md` as
the supported way to restore the simultaneous opening wave -- and a value set
for it survived only until the next time anyone pressed Save on a panel that
has no field for it. Silently: nothing on screen had ever shown the number,
so nothing on screen showed it go.

The rule these tests pin is general, not a rule about one knob: **a PUT that
omits a key preserves it.** Any knob the defaults grow later inherits it.
"""

from __future__ import annotations

import time


def _chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))


def _panel_save(**overrides):
    """Exactly what `settings.js` sends, and nothing else."""
    body = {
        "style": "natural", "min_lines": 0, "max_lines": 4, "variance": 0.6,
        "autonomy": 50,
        "allow_npc_initiative": True, "allow_npc_to_npc_dialogue": True,
        "stop_on_player_address": True, "stop_on_question_to_player": True,
        "silence_ends_exchange": True,
        "promote_after_addressed": 0,
        "offscreen_life": "reactive",
        "max_offscreen_actors": 3,
    }
    body.update(overrides)
    return body


def test_a_knob_the_panel_does_not_render_survives_a_panel_save(temp_db):
    from story.scene import dialogue_config
    from web import app

    cid = _chat(temp_db)
    temp_db.wset(cid, "dialogue_config", {"autonomy": 50,
                                          "initial_parallel_reactors": 3})

    saved = app.dlg_put(cid, _panel_save())

    assert saved["initial_parallel_reactors"] == 3
    assert dialogue_config(cid)["initial_parallel_reactors"] == 3


def test_the_route_can_set_the_wave_size_at_all(temp_db):
    """Unreachable through every supported path is the other half of the
    finding: the doc names the knob, and no route accepted it."""
    from story.scene import dialogue_config
    from web import app

    cid = _chat(temp_db)
    saved = app.dlg_put(cid, _panel_save(initial_parallel_reactors=4,
                                         parallel_isolated_reactors=True))

    assert saved["initial_parallel_reactors"] == 4
    assert saved["parallel_isolated_reactors"] is True
    assert dialogue_config(cid)["initial_parallel_reactors"] == 4


def test_the_wave_size_is_bounded_and_never_zero(temp_db):
    """`agents/loops.py` floors it at 1 when it reads; the write side must not
    be the place a nonsense value is stored and then quietly repaired."""
    from web import app

    cid = _chat(temp_db)
    assert app.dlg_put(cid, _panel_save(initial_parallel_reactors=0))[
        "initial_parallel_reactors"] == 1
    assert app.dlg_put(cid, _panel_save(initial_parallel_reactors=999))[
        "initial_parallel_reactors"] == 12


def test_a_submitted_field_still_wins_over_the_stored_one(temp_db):
    """Preserving on omission must not become preserving on submission --
    turning a checkbox OFF is a submitted `False`, not an absent key."""
    from web import app

    cid = _chat(temp_db)
    app.dlg_put(cid, _panel_save(silence_ends_exchange=True, max_lines=9))
    saved = app.dlg_put(cid, _panel_save(silence_ends_exchange=False, max_lines=2))

    assert saved["silence_ends_exchange"] is False
    assert saved["max_lines"] == 2


def test_the_autonomy_ladder_still_re_derives_on_every_save(temp_db):
    """The derived limits follow autonomy. Preserving stored values must not
    freeze them at whatever the last rung wrote."""
    from web import app

    cid = _chat(temp_db)
    high = app.dlg_put(cid, _panel_save(autonomy=100))
    assert high["max_character_calls"] == 18

    low = app.dlg_put(cid, _panel_save(autonomy=0))
    assert low["max_character_calls"] == 1
