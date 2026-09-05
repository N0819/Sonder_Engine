"""A quiet scene applies its pressure through speech, and the ledgers that
carry pressure were both reading zero.

Live case: chat "quiet", 2026-09-05, finding PQ21
(`docs/experiments/PLAY_2026_09_05C_quiet.md`). Tobin was authored at
`stress: {activation: 0.45, load: 0.55}`. At turn 7 -- after his sister had
opened the burial bill he asked her not to open, offered to pay it through a
publican, ordered him to sit, and named the two years -- `inspect_minds`
reported `activation: 0.252, load: 0.0958, drive_strain: 0.0`. Every number
had fallen through a scene built to raise them.

Two mechanisms, each a plain defect rather than a tuning question:

1. `resolve_stress` documents a fallback -- "legacy states carry no strain
   key; their activation is the closest thing to it" -- that has never once
   fired, because `initial_state.stress` is `{activation, load, coping_mode}`
   in every card template the engine ships and
   `character_initial_active_state` fills the absent `strain` in with 0.0.
   An authored acute stress was therefore discarded on beat one, every time.

2. `update_drive_strain` decays on `_STRAIN_HALF_LIFE = 60.0` fed by
   `elapsed_psych_units`, which is one unit per TURN in a story with no
   simulation clock and one unit per MINUTE in one with a clock. The same
   seven beats relaxed a drive by 8% in the first kind of story and by 84%
   in the second, off one constant -- and `drive_strain 0.0` means the
   rupture mechanism can never fire in a story of this shape.
"""

from __future__ import annotations

from mind import affect
from mind.psychology_runtime import resolve_stress


_CALM = {"novelty": 0.0, "controllability": 0.9, "coping_potential": 0.9,
         "norm_compatibility": 0.0}
_PROFILE = {"baseline_reactivity": 0.5, "recovery_rate": 0.5,
            "overload_threshold": 0.8}
_NO_BODY = {"pain": 0.0, "pleasure": 0.0, "charge": 0.0}


def _seeded_card_state(activation, load):
    """Exactly what `character_initial_active_state` hands the first beat:
    a `strain` key, present and zero, beside the authored numbers."""
    return {"activation": activation, "strain": 0.0, "load": load,
            "coping_mode": ""}


class TestAnAuthoredStressReachesTheFirstBeat:
    def test_the_seeded_strain_of_zero_no_longer_erases_the_authored_number(self):
        out = resolve_stress(_seeded_card_state(0.45, 0.55), _CALM, _PROFILE,
                             _NO_BODY, 1.0)
        # Peak-held: the beat itself is calm, so the authored strain is what
        # stands, decayed by the one unit of elapsed time (half-life 5 at the
        # default recovery rate: 0.45 -> 0.392).
        assert out["strain"] > 0.35
        assert out["activation"] > 0.35

    def test_a_block_this_function_produced_is_believed_about_its_own_strain(self):
        """The discriminator is `overloaded`, a key only this function
        writes -- a resolved state whose strain really is zero (all of its
        activation being drive) must not have its activation re-read as
        distress."""
        resolved = resolve_stress({}, _CALM, _PROFILE,
                                  {"pain": 0.0, "pleasure": 0.9, "charge": 0.9},
                                  1.0)
        assert "overloaded" in resolved
        assert resolved["strain"] < 0.05          # only the calm beat's own
        assert resolved["activation"] > 0.4       # and the rest is drive
        again = resolve_stress(resolved, _CALM, _PROFILE, _NO_BODY, 1.0)
        assert again["strain"] < 0.05

    def test_an_unstressed_card_still_starts_unstressed(self):
        out = resolve_stress(_seeded_card_state(0.0, 0.0), _CALM, _PROFILE,
                             _NO_BODY, 1.0)
        assert out["strain"] < 0.05
        assert out["load"] < 0.05


class TestTimeDoesNotPayDownADrive:
    def _decay_only(self, strain, elapsed):
        """No impact, no suppression: decay is the whole of the movement."""
        new, entry = affect.update_drive_strain(strain, [], {}, "", "", elapsed)
        assert entry is None
        return new

    def test_a_clockless_story_decays_exactly_as_before(self):
        """One unit per turn against a 60-unit half-life is 0.988 a beat,
        which is above the floor, so nothing about that path moves."""
        assert self._decay_only(0.8, 1.0) == (
            0.8 * 0.5 ** (1.0 / affect._STRAIN_HALF_LIFE))

    def test_a_two_hour_conversation_no_longer_empties_the_ledger(self):
        """Seven beats of roughly twenty minutes each -- the measured shape
        of the quiet run -- used to leave 16% of a standing strain."""
        strain = 0.8
        for _ in range(7):
            strain = self._decay_only(strain, 20.0)
        assert strain > 0.6
        # And it is still decay, not a freeze: a scene that goes on relaxes.
        assert strain < 0.8

    def test_relief_still_pays_a_drive_down(self):
        """The floor bounds the CLOCK, never the character: living something
        that answers the drive is what relief has always been."""
        relieved, entry = affect.update_drive_strain(
            0.8, [],
            {"drive_impact": {"serves": "drive", "impact": 0.9,
                              "certainty": 0.9,
                              "why": "she said he had done enough"}},
            "drive", None, 1.0)
        assert entry["source"] == "relief"
        assert relieved < 0.6
