"""The player owns what their own body DOES; the world owns what reaches it.

`_check_player_act_authority` holds this boundary in `resolved_event` and
holds it well. `state_diff.contact_ops` stores an ACTOR, so it says the same
thing through a channel nobody was asking.

Measured live (chat 95 t40). The player wrote:

    "H-how about the full thing... maybe it'll smooth over my scars"
    You lie back on the bed. "W-would you like to sit on my face?"

One declared act -- lying back -- and an invitation phrased as a question.
The prose was clean and passed (`player_act_warnings: null`), because it
correctly has MIRELLE lower herself. The ops then wrote
`Hinami.tongue -> Mirelle.vulva, press, moving`, and it committed: an
invitation became the player performing, in the same beat.

Run over the whole 40-turn chat, this flags that turn and no other.
"""
import json

from agents.common import _check_player_contact_authority

CAST = [{"id": 72, "sheet": json.dumps(
    {"identity": {"name": "Mirelle Sulmirath"}})}]


def _check(ops, acts, standing=()):
    return _check_player_contact_authority(
        ops, acts, "Hinami", standing, CAST)


def _op(**kw):
    base = {"op": "add", "actor": "Hinami", "actor_part": "hand",
            "target": "Mirelle Sulmirath", "target_part": "arm",
            "manner": "touch", "motion": "moving"}
    base.update(kw)
    return base


class TestWhatThePlayerDoesIsTheirs:
    def test_an_undeclared_act_on_another_body_is_refused(self):
        [(index, warning)] = _check(
            [_op(actor_part="tongue", target_part="vulva", manner="press")],
            [{"attempt": "lies back on the bed", "verb": "lie"}])
        assert index == 0
        assert "Mirelle Sulmirath" in warning

    def test_an_act_reaching_that_body_licenses_what_it_involves(self):
        """Elaboration stays the Director's job. t23 declared sliding
        Mirelle's chemise and got `hand -> upper arm`; t35 declared clamping
        thighs around her head and got `vulva -> Mirelle`. The test is REACH,
        never a vocabulary of limbs or verbs."""
        assert _check(
            [_op(actor_part="hand", target_part="upper arm")],
            [{"attempt": "slide the shoulder straps of Mirelle's chemise",
              "targets": ["72"]}]) == []

    def test_reach_is_read_from_the_targets_list_by_cast_id(self):
        assert _check([_op()], [{"attempt": "reach out", "targets": ["72"]}]) == []

    def test_reach_is_read_from_a_first_name_in_the_attempt(self):
        """t32: `targets` was empty and the attempt said "Mirelle's hair".
        Requiring the full registered name read that beat as reaching nobody."""
        assert _check(
            [_op(target_part="hair", manner="pet")],
            [{"attempt": "run fingers through Mirelle's hair"}]) == []


class TestWhatReachesThePlayerIsNotTheirs:
    def test_a_body_pressing_against_the_player_is_never_checked(self):
        """The engine owns what presses against them -- including something
        forcing its way in. That is the other body's conduct, and the ledger
        already records which side is acting."""
        assert _check(
            [_op(actor="Mirelle Sulmirath", actor_part="vulva",
                 target="Hinami", target_part="mouth", manner="press")],
            [{"attempt": "lies back on the bed"}]) == []

    def test_furniture_is_posture_not_conduct(self):
        """A bed is not a person. t30's back arching against the bed and
        t40's lying on it are the world resolving posture, and checking them
        fired on the furniture of every reclining beat."""
        assert _check(
            [_op(actor_part="back", target="wide_bed", target_part="")],
            [{"attempt": "arch a little"}]) == []

    def test_a_standing_hold_restated_is_not_a_new_act(self):
        assert _check(
            [_op(contact_id="contact:abc")],
            [{"attempt": "lies back on the bed"}],
            standing=["contact:abc"]) == []

    def test_a_removal_is_not_an_act(self):
        assert _check(
            [_op(op="remove")], [{"attempt": "lies back on the bed"}]) == []
