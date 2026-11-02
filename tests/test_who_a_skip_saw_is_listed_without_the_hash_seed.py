"""Who a mind saw across a skip is listed in one order on every run.

`_TownRun._seen` sorted the people a row names by (kind, rank, label) over a
`set` of refs, so two residents sharing a stranger label and a rank tied, and
their order -- and which one `SEEN_PER_ROW_CAP` cut -- followed the hash-
salted set order: a rerun process could file a different `seen` list (audit
world_charter_generation_run F16, observed under four PYTHONHASHSEED values).
The ref itself breaks the tie now."""
from world.charter_skip import _seen_order


def test_a_tie_is_broken_by_the_ref_not_by_the_order_it_arrived_in():
    a, b = ("inn", "hand:0001"), ("inn", "hand:0002")
    presence = {a: (0, "present", None), b: (0, "present", None)}

    def label(_ref):
        return "a house hand"

    forward = _seen_order([a, b], presence, {}, label)
    backward = _seen_order([b, a], presence, {}, label)
    assert forward == backward == [a, b]


def test_an_interaction_still_outranks_a_presence():
    a, b = ("inn", "hand:0001"), ("inn", "hand:0002")
    presence = {a: (0, "present", None)}
    interaction = {b: (1, "toward_you", "greet")}
    assert _seen_order([a, b], presence, interaction,
                       lambda ref: "a house hand") == [b, a]
