"""A memory's habituation that has rested back to nothing is dropped, and
dropping it changes nothing.

`mood_habits` gained an entry for every memory ever recalled and nothing
removed one: 80 entries / 4.5 KB after 36 turns on the play database (chat
178, char 83), about 2.2 a turn, rewritten every commit and copied into every
checkpoint and archive (review 2026-11-01, mind_affect_psychology E3). An
entry rests back toward zero (`HABITUATION_HALF_LIFE`), and the module stores
`h` to four places (`recall_lands`): one that has decayed below half the last
stored digit lands next exactly as an absent one would -- same multiplier,
same stored level -- so it is dropped when the mood is persisted.
"""

from __future__ import annotations

from mind import affect_mix, affect_pass


def test_a_rested_entry_goes_and_a_fresh_one_stays():
    felt = affect_pass.Felt(mood=affect_mix.Mood({}), home=affect_mix.Mood({}), clock=500.0,
                            habits={"old": {"h": 1.0, "at": 100.0},
                                    "fresh": {"h": 0.4, "at": 499.0}})
    kept = affect_pass.persisted(felt)["mood_habits"]
    assert set(kept) == {"fresh"}
    assert kept["fresh"] == {"h": 0.4, "at": 499.0}


def test_dropping_it_is_lossless():
    """The next landing of a dropped entry is the landing of the kept one."""
    now = 500.0
    kept_state = {"old": {"h": 1.0, "at": 100.0}}
    pruned = affect_mix.rested_away(kept_state, now)
    assert pruned == {}
    for later in (now, now + 1.0, now + 60.0):
        assert affect_mix.recall_lands(kept_state, "old", later) == \
            affect_mix.recall_lands(pruned, "old", later)
