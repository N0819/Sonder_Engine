"""Sustained maximum affect costs sensitivity, so a peak has somewhere to land.

The defect (chat 71, Elyra, char 56 -- and not just her): `resolve_affect`
decays an unreinforced mood toward baseline and clamps proposals at +/-1.
Decay handles FADING; nothing handled SATURATION. A model that sees its own
ceiling-pinned surface in the payload proposes the ceiling again, so a
surface that reaches maximum stays there: her committed surface sat at
0.9943/0.9948 for twelve consecutive beats, and the climax the whole scene
was built toward -- somatic pleasure 0.95, the beat the player asked about
-- committed a surface LOWER than the plateau before it. Zero contrast at
the story's own peak is exactly why she read unfazed. Corpus-wide, 21 of 44
characters with >=8 beats carry a >=6-beat pinned streak at >=0.9; three
stories hold thirty-beat valence streaks.

The fix is the codebase's own precedent (psychology_runtime habituates the
hedonic level's cognitive claim across `sustained_beats`; comfort habituates
on a sustained source) applied to the surface: sensitivity `s` accumulates
per axis while the STIMULUS -- the uncompressed resolution target -- holds
the ceiling-slice of the axis (elevation above _HABITUATION_ELEVATION_FLOOR
of the span from the character's own baseline), recovers on a short
half-life when it comes down, and compresses ONLY that top slice
(_compress_top_slice): everything below the protected range is a character
trait, never a defect, and pays nothing. Habituation covers the plateau,
never the spike: the hedonic RELEASE (the discriminator measured to work
where shock and novelty both fail -- plateau impacts run 0.85-0.95 and
model novelty reads 0.65 mid-plateau, 0.15 at the actual climax) refunds
most of the cost and waives compression on its own beat.

Replayed against the live stored appraisals (tools/affect_replay.py): the
twelve-beat plateau settles to ~0.83 valence, the three release beats land
at 0.915-0.945 -- the highest post-build points of the whole trajectory,
where live they were mathematically indistinguishable from the wallpaper.
The control bands hold: beats below 0.80 valence move by a mean 0.012.

Default OFF (`affect_habituation` setting): the shipped behaviour is
byte-identical, and the state key is neither read nor written.
"""

from __future__ import annotations

import json
import time

import affect


BASE = {"valence": 0.4, "arousal": 0.45}
CEILING = {"surface": {"label": "possessive delight",
                       "valence": 0.99, "arousal": 0.99}}
POSITIVE = {"dV": 0.2, "dA": 0.1, "emotions": ["joy"], "dominant": None}


def _run(beats, habituate, prev=None, released_at=()):
    states = []
    for i in range(beats):
        prev = affect.resolve_affect(
            prev, POSITIVE, BASE, 1, CEILING,
            habituate=habituate, released=(i in released_at))
        states.append(prev)
    return states


class TestTheDefaultIsTheShippedBehaviour:
    def test_off_never_writes_the_state_key(self):
        for state in _run(6, habituate=False):
            assert "habituation" not in state

    def test_off_keeps_the_ceiling_pinned_forever(self):
        """The defect, preserved on purpose when the setting is off: the
        surface reaches the ceiling and stays there with no headroom."""
        states = _run(15, habituate=False)
        assert states[-1]["surface"]["valence"] >= 0.95
        assert states[-1]["surface"]["arousal"] >= 0.95
        # And the release beat cannot out-score the plateau: zero contrast.
        peak = affect.resolve_affect(
            states[-1], POSITIVE, BASE, 1, CEILING,
            habituate=False, released=True)
        assert peak["surface"]["valence"] <= states[-1]["surface"]["valence"] + 0.01

    def test_off_ignores_stale_state_from_a_story_that_had_it_on(self):
        prev = _run(8, habituate=True)[-1]
        assert "habituation" in prev
        after = affect.resolve_affect(prev, POSITIVE, BASE, 1, CEILING,
                                      habituate=False)
        assert "habituation" not in after


class TestThePlateauSettles:
    def test_a_pinned_ceiling_drifts_down_under_continued_stimulus(self):
        states = _run(15, habituate=True)
        assert states[-1]["surface"]["valence"] < 0.9
        assert states[-1]["habituation"]["valence"] > 0.5
        # Monotone-ish settling, not oscillation: the late plateau sits
        # below the early build's peak.
        early_peak = max(s["surface"]["valence"] for s in states[:5])
        assert states[-1]["surface"]["valence"] < early_peak

    def test_the_release_pierces_and_out_scores_the_plateau(self):
        """The measurement that decides the fix (the chat 71 shape): after
        a long plateau, the discharge beat lands ABOVE it."""
        states = _run(15, habituate=True)
        plateau = states[-1]["surface"]["valence"]
        peak = affect.resolve_affect(
            states[-1], POSITIVE, BASE, 1, CEILING,
            habituate=True, released=True)
        assert peak["surface"]["valence"] > plateau + 0.05
        # And the cost was refunded: sensitivity reset toward fresh.
        assert peak["habituation"]["valence"] < \
            states[-1]["habituation"]["valence"] * 0.6

    def test_recovery_restores_full_height_after_quiet_beats(self):
        states = _run(12, habituate=True)
        prev = states[-1]
        for _ in range(8):    # quiet: no proposal, empty appraisal
            prev = affect.resolve_affect(prev, {}, BASE, 1, None,
                                         habituate=True)
        assert prev["habituation"]["valence"] < 0.15
        # A fresh spike after recovery lands essentially uncompressed.
        spike = affect.resolve_affect(prev, POSITIVE, BASE, 1, CEILING,
                                      habituate=True)
        uncompressed = affect.resolve_affect(prev, POSITIVE, BASE, 1, CEILING,
                                             habituate=False)
        assert abs(spike["surface"]["valence"]
                   - uncompressed["surface"]["valence"]) < 0.03


class TestTheProtectedRange:
    def test_sustained_ordinary_warmth_is_a_trait_not_a_defect(self):
        """Below the protected range's edge nothing is ever compressed --
        the control finding (chat 38): a long, warm story's mid-range must
        pass through untouched."""
        warm = {"surface": {"label": "warm", "valence": 0.72, "arousal": 0.5}}
        prev_on = prev_off = None
        for _ in range(20):
            prev_on = affect.resolve_affect(prev_on, {}, BASE, 1, warm,
                                            habituate=True)
            prev_off = affect.resolve_affect(prev_off, {}, BASE, 1, warm,
                                             habituate=False)
        assert abs(prev_on["surface"]["valence"]
                   - prev_off["surface"]["valence"]) < 0.005
        assert abs(prev_on["surface"]["arousal"]
                   - prev_off["surface"]["arousal"]) < 0.005

    def test_compression_is_symmetric_about_the_baseline(self):
        """Pinned misery habituates exactly as pinned delight does."""
        misery = {"surface": {"label": "despair",
                              "valence": -0.99, "arousal": 0.2}}
        grim = {"dV": -0.2, "dA": 0.0, "emotions": ["sadness"],
                "dominant": None}
        prev = None
        for _ in range(15):
            prev = affect.resolve_affect(prev, grim, BASE, 1, misery,
                                         habituate=True)
        assert prev["surface"]["valence"] > -0.9
        assert prev["habituation"]["valence"] > 0.5

    def test_top_slice_math_is_total_on_junk(self):
        assert affect._compress_top_slice("junk", None, "x") == 0.0
        # Inside the protected range: identity.
        assert affect._compress_top_slice(0.7, 0.4, 1.0) == 0.7


def test_the_commit_seam_reads_the_setting(temp_db, monkeypatch):
    """`affect_habituation` (default off) is read at the one call site in
    commit.py -- affect.py deliberately imports no db -- and the release
    flag handed to resolve_affect is the character's own declared hedonic
    discharge, the same one resolve_hedonic receives."""
    import commit
    from character_schema import default_character_data
    from pipeline_context import ChatData, PipelineContext, TurnData

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}",
         time.time(), "char_alice"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "test", time.time()))
    temp_db.wset(chat_id, "scene", {
        "rooms": {"kitchen": {"name": "Kitchen"}},
        "positions": {"Alice": "kitchen"},
        "entities": {}, "attire": {}, "overlays": {}})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="test", created=time.time()),
        cast=cast, input="test")
    ctx.director_resolve = {"summary": "s", "resolved_event": "e",
                            "dialogue_log": []}
    ctx.perception_outcome = {"views": {str(char_id): "Alice sees."}}
    ctx.character_results = {char_id: {
        "sequence": [],
        "active_state": {
            "affect": {"surface": {"label": "calm", "valence": 0.2,
                                   "arousal": 0.2}},
            "hedonic": {"released": True},
            "wants": [],
        },
        "appraisal": {"goal_impacts": []},
    }}

    seen = {}
    real = commit.affect.resolve_affect

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(commit.affect, "resolve_affect", spy)

    temp_db.set_setting("affect_habituation", "on")
    commit.prepare_memory_commit(ctx)
    assert seen.get("habituate") is True
    assert seen.get("released") is True

    seen.clear()
    temp_db.set_setting("affect_habituation", "")
    commit.prepare_memory_commit(ctx)
    assert seen.get("habituate") is False
