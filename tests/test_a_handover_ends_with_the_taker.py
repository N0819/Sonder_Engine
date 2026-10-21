"""A thing offered and then taken ends with the taker.

The lighthouse probe (2026-10-21, chat 2 turn idx 3): the player held out a
sealed letter to the boatman, his round agreed to post it, and the resolve's
encoder wrote "Pell takes the sealed letter from Rhona Carrick's hand and
tucks it into his inside pocket" as one event carrying three writes about the
letter -- the transfer to his pocket, a containment record in his pocket, and
`containment: {sister_letter: null}` filed under the giver. The release was
then read as the END of the beat's story about the letter rather than the
departure the same event's arrival completes:

- `compile_transforms` kept the release, listed after the placement, as the
  span's containment (a span's patches are complementary, so the listing
  order is no chronology; left as it is -- with the transfer in the span,
  what the reduction kept no longer decides where the letter goes);
- `derive_inventory_placements` read the release as "this span's explicit
  containment" and refused the transfer: "conflicts with this span's explicit
  containment; the containment was kept";
- the span's receipts then failed both the placement and the transfer, the
  span verified `unresolved`, and perception withheld the take from every
  view ("the beat verified this act as unexecuted"). The narrator wrote "The
  letter stayed out over the drop. He hadn't taken it", the letter lay on the
  ledge, and the boat left without it.

The first play of the same story lost the player's OWN handover the same way
(chat 1 turn idx 2: "puts it in Elias's open hand" -- release plus transfer in
one span, the letter back with her by bearing, her act withheld).

THE RULE: a release (`containment: {thing: null}`) is a departure, never a
destination. It says the carriage standing when its span began has ended --
the containment card's own words, "{subject:null} when it ends". Within one
span it and the span's transfer are one hand-off, so it never refuses the
transfer, and its receipt is met when that carriage is gone, wherever the
same span's arrival put the thing; with no arrival in its span it is met only
when nothing holds the thing. Across spans the program runs in event order,
so a release in a LATER span still lets go of what an earlier span handed
over, and the player's own assertion of what she holds is applied before the
beat's events (the interpret's spans run first).

Refusals that rest on something else still hold: a transfer of a thing the
giver does not hold, a placement in the same span naming another holder, a
transfer with no destination the scene can vouch for.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from agents.common import merge_player_state_assertions
from persist.commit import _refuse_unheld_transfers
from world.causal_program import program_from_history
from world.causal_verification import verify_patch
from world.causality import compile_transforms
from world.spatial import merge_scene_with_diff, room_of, same_subject


RHONA, PELL, ELIAS = "Rhona Carrick", "Pell Hardacre", "Elias Thorne"
LETTER = "sister_letter"

_OPEN_STAIR = {"vertical": "down", "way": "ladder", "barrier": "open"}


def _lighthouse():
    """The ledge and the landing as checkpoint 3 of the probe held them:
    Rhona and Pell on the ledge at the head of the ladder, Elias below on the
    landing, the bodies as the engine mints them (`kind: person`)."""
    return {
        "rooms": {
            "the_stair": {"name": "The Steps", "adjacent": [
                dict(_OPEN_STAIR, to="rock_landing")],
                "anchors": {"ledge": {"desc": "a narrow ledge"}}},
            "rock_landing": {"name": "The Landing", "adjacent": [
                dict(_OPEN_STAIR, to="the_stair", vertical="up")],
                "anchors": {"tie_up": {"desc": "a ring and a bollard"}}},
        },
        "entities": {
            "char_rhona_carrick": {"name": RHONA, "kind": "person", "aliases": []},
            "char_pell_hardacre": {"name": PELL, "kind": "person", "aliases": []},
            "char_elias_thorne": {"name": ELIAS, "kind": "person", "aliases": []},
        },
        "positions": {RHONA: "the_stair", PELL: "the_stair",
                      ELIAS: "rock_landing"},
        "attire": {RHONA: {"regions": {}}, PELL: {"regions": {}},
                   ELIAS: {"regions": {}}},
        "contained": {}, "contacts": [], "stations": {}, "poses": {},
        "scales": {},
    }


_MINT = {"name": "a sealed letter", "kind": "document", "portable": True,
         "container": False, "aliases": ["sealed letter", "the letter", "letter"]}


def _program(stage, rows):
    """Compile `(chrono_id, item_id, object_name, patch)` rows the way
    `director._run_specialists` does -- one ordered history, every channel
    granted -- into a stage diff carrying its executable spans."""
    raw = [{"chrono_id": chrono, "item_id": item, "object_name": name,
            "patch": patch} for chrono, item, name, patch in rows]
    channels = {channel for row in rows for channel in row[3]}
    diff, history, rejected = compile_transforms(raw, allowed_channels=channels)
    assert not rejected, rejected
    diff["causal_steps"] = program_from_history(history, stage=stage)
    return diff


def _offer():
    """The player's declaration, as the interpret's encoder wrote it: she
    brings the letter out (minted, held, a hold in her hand) and holds it out
    to him."""
    return _program("interpret", [
        (1, 1, LETTER, {"entities": {LETTER: dict(_MINT)}}),
        (1, 1, LETTER, {"containment": {LETTER: {"in": RHONA, "mode": "held"}}}),
        (1, 1, LETTER, {"inventory_ops": [{
            "op": "transfer", "object_id": LETTER, "from_id": RHONA,
            "to_id": RHONA, "relation": "held"}]}),
        (1, 2, RHONA, {"contact_ops": [{
            "op": "add", "actor": RHONA, "actor_part": "hand", "target": LETTER,
            "manner": "hold", "relation": "surface", "motion": "settled"}]}),
        (2, 2, RHONA, {"poses": {RHONA: {
            "posture": "standing", "support": "ledge", "relative_to": PELL,
            "relation": "facing",
            "detail": "holding out a sealed letter toward Pell Hardacre"}}}),
    ])


_TAKE = {"op": "transfer", "object_id": LETTER, "from_id": RHONA,
         "to_id": PELL, "relation": "pocket"}


def _take(*, placement=True, release=True):
    """His round, as the resolve's encoder wrote it (span 3): the hold in her
    hand ends, the letter goes to his pocket, the giver's carriage released
    -- the release filed under HER, after the placement, exactly as
    recorded. Then he goes down the ladder to the boat (span 8)."""
    rows = [(3, 4, PELL, {"contact_ops": [
        {"op": "remove", "actor": RHONA, "target": LETTER}]})]
    if placement:
        rows.append((3, 3, LETTER, {"containment": {
            LETTER: {"in": PELL, "mode": "pocket"}}}))
    if release:
        rows.append((3, 5, RHONA, {"containment": {LETTER: None}}))
    rows += [
        (3, 3, LETTER, {"inventory_ops": [dict(_TAKE)]}),
        (3, 3, LETTER, {"entities": {LETTER: {
            "name": "a sealed letter",
            "state": {"examined": "her sister's name on it, sealed with wax"}}}}),
        (8, 4, PELL, {"positions": {PELL: "rock_landing"}}),
    ]
    return _program("resolve", rows)


def _commit_merge(scene, diff):
    """`merge_scene_with_diff` as the commit runs it: the unheld-transfer
    guard on every span, the receipts of every span kept."""
    notes, report, worlds = [], [], []
    ctx = SimpleNamespace(add_warning=notes.append, tell_director=notes.append)
    final = merge_scene_with_diff(
        scene, diff, inventory_report=report, causal_worlds=worlds,
        causal_guard=lambda world, patch: _refuse_unheld_transfers(ctx, world, patch))
    return final, report + notes, worlds


def _holder(scene, thing=LETTER):
    for key, record in (scene.get("contained") or {}).items():
        if same_subject(scene, key, thing) and isinstance(record, dict):
            return record
    return None


def _span(worlds, stage, chrono):
    for world in worlds:
        if world.get("stage") == stage and world.get("chrono_id") == chrono:
            return world
    raise AssertionError("no %s span %s" % (stage, chrono))


class TestTheProbeBeat:
    def test_the_recorded_take_ends_in_his_pocket_and_goes_with_him(self):
        warnings = []
        diff = merge_player_state_assertions(
            _offer(), _take(), RHONA, report=warnings.append)
        # The beat's own notices, as recorded: the resolve restated the
        # letter and the player's flattened channels yielded to it.
        assert any("restated containment for sister_letter" in w for w in warnings)
        final, notes, worlds = _commit_merge(_lighthouse(), diff)

        record = _holder(final)
        assert record is not None, "the letter is held by nobody: %r" % notes
        assert same_subject(final, record["in"], PELL)
        assert record["mode"] == "pocket"
        # ...and it is in the pocket that goes down the ladder to the boat.
        assert room_of(final, LETTER) == "rock_landing"
        assert not any("explicit containment" in n for n in notes), notes

    def test_the_take_is_an_act_every_view_may_see(self):
        """The span that carried it verifies as done, so perception does not
        withhold it as an unexecuted act."""
        diff = merge_player_state_assertions(_offer(), _take(), RHONA)
        _final, _notes, worlds = _commit_merge(_lighthouse(), diff)
        completion = _span(worlds, "resolve", 3)["completion"]
        assert completion["action_status"] != "unresolved", completion
        refused = [e for e in completion["effects"] if e["status"] == "unresolved"]
        assert refused == [], refused

    def test_her_offer_is_applied_before_his_take(self):
        """The interpret's spans run first: after them she holds it out, and
        the take starts from that."""
        diff = merge_player_state_assertions(_offer(), _take(), RHONA)
        _final, _notes, worlds = _commit_merge(_lighthouse(), diff)
        offered = _holder(_span(worlds, "interpret", 1)["after"])
        assert offered is not None and same_subject(
            _lighthouse(), offered["in"], RHONA)
        stages = [w["stage"] for w in worlds]
        assert stages.index("interpret") < stages.index("resolve")


@pytest.mark.parametrize("placement, release", [
    (True, True),    # as recorded: placement, then the giver's release
    (False, True),   # the release and the transfer alone
    (True, False),   # placement and transfer, no release
    (False, False),  # the card's own encoding: the transfer is the whole change
], ids=["recorded", "release_only", "placement_only", "transfer_only"])
def test_an_offer_then_a_take_ends_with_the_taker(placement, release):
    """However the take's span spells the hand-off, the taker has the thing
    at the end of the beat and the act is not withheld."""
    diff = merge_player_state_assertions(
        _offer(), _take(placement=placement, release=release), RHONA)
    final, notes, worlds = _commit_merge(_lighthouse(), diff)
    record = _holder(final)
    assert record is not None and same_subject(final, record["in"], PELL), notes
    assert _span(worlds, "resolve", 3)["completion"]["action_status"] \
        != "unresolved"


class TestThePlayersOwnHandover:
    """The first play's turn idx 2: "Rhona takes the Board's letter from inside
    her coat and puts it in Elias's open hand." One span: the letter resting
    on his palm, the release, the transfer -- and the opening had put it in
    her hand (`held_by`, carried by bearing)."""

    def _scene(self):
        scene = _lighthouse()
        scene["positions"][ELIAS] = "the_stair"
        scene["entities"]["board_instructions"] = {
            "name": "The Board's Instructions", "kind": "object",
            "portable": True, "aliases": ["the instructions"],
            "held_by": RHONA}
        scene["positions"]["board_instructions"] = "the_stair"
        scene["contained"]["board_instructions"] = {
            "in": RHONA, "mode": "carried", "by": "bearing"}
        return scene

    def _diff(self):
        return _program("interpret", [
            (3, 4, ELIAS, {"contact_ops": [{
                "op": "add", "actor": "board_instructions", "target": ELIAS,
                "target_part": "hand", "manner": "rest", "relation": "surface",
                "motion": "settled"}]}),
            (3, 3, "board_instructions", {"containment": {
                "board_instructions": None}}),
            (3, 3, "board_instructions", {"inventory_ops": [{
                "op": "transfer", "object_id": "board_instructions",
                "from_id": RHONA, "to_id": ELIAS, "relation": "held"}]}),
        ])

    def test_the_letter_is_in_his_hand(self):
        final, notes, _worlds = _commit_merge(self._scene(), self._diff())
        record = _holder(final, "board_instructions")
        assert record is not None and same_subject(final, record["in"], ELIAS), \
            (record, notes)
        assert record["mode"] == "held"

    def test_her_act_is_not_withheld(self):
        _final, _notes, worlds = _commit_merge(self._scene(), self._diff())
        completion = _span(worlds, "interpret", 3)["completion"]
        assert completion["action_status"] != "unresolved", completion


class TestRefusalsThatStillHold:
    def test_a_thing_the_giver_does_not_hold_is_not_handed_over(self):
        """The letter is in Elias's pocket down on the landing; a span that
        has Rhona, up on the ledge, hand it to Pell is refused at the guard,
        release or no release, and the act stays unexecuted."""
        scene = _lighthouse()
        scene["entities"][LETTER] = dict(_MINT)
        scene["positions"][LETTER] = "rock_landing"
        scene["contained"][LETTER] = {"in": ELIAS, "mode": "pocket"}
        diff = _program("resolve", [
            (3, 5, RHONA, {"containment": {LETTER: None}}),
            (3, 3, LETTER, {"inventory_ops": [dict(_TAKE)]}),
        ])
        final, notes, worlds = _commit_merge(scene, diff)
        record = _holder(final)
        assert not (record and same_subject(final, record.get("in"), PELL))
        assert any("was not" in n and "to hand over" in n for n in notes), notes
        assert _span(worlds, "resolve", 3)["completion"]["action_status"] \
            == "unresolved"

    def test_a_placement_naming_another_holder_still_outranks_the_transfer(self):
        """A span that puts the letter in Elias's pocket and transfers it to
        Pell says two different things about where it went: the explicit
        record is kept and the conflict is reported, as before."""
        scene = _lighthouse()
        scene["positions"][ELIAS] = "the_stair"
        diff = merge_player_state_assertions(_offer(), _program("resolve", [
            (3, 3, LETTER, {"containment": {LETTER: {"in": ELIAS,
                                                     "mode": "pocket"}}}),
            (3, 3, LETTER, {"inventory_ops": [dict(_TAKE)]}),
        ]), RHONA)
        final, notes, _worlds = _commit_merge(scene, diff)
        record = _holder(final)
        assert record is not None and same_subject(final, record["in"], ELIAS)
        assert any("explicit containment" in n for n in notes), notes

    def test_a_release_in_a_later_span_still_lets_go(self):
        """Taken, then let go: the spans run in event order and the last
        write about the letter stands."""
        diff = merge_player_state_assertions(_offer(), _program("resolve", [
            (3, 3, LETTER, {"inventory_ops": [dict(_TAKE, relation="held")]}),
            (5, 4, PELL, {"containment": {LETTER: None}}),
        ]), RHONA)
        final, notes, _worlds = _commit_merge(_lighthouse(), diff)
        assert _holder(final) is None, notes

    def test_a_release_with_a_destination_nobody_vouches_for_stays_released(self):
        """Set down on something the scene does not hold (the tavern probe's
        "next_table"): the release says it left his hand, and with no place to
        arrive it is not handed back to him."""
        scene = _lighthouse()
        scene["entities"][LETTER] = dict(_MINT)
        scene["positions"][LETTER] = "the_stair"
        scene["contained"][LETTER] = {"in": PELL, "mode": "held"}
        diff = _program("resolve", [
            (3, 4, PELL, {"containment": {LETTER: None}}),
            (3, 3, LETTER, {"inventory_ops": [{
                "op": "transfer", "object_id": LETTER, "from_id": PELL,
                "to_id": "next_table"}]}),
        ])
        final, notes, _worlds = _commit_merge(scene, diff)
        assert _holder(final) is None, notes
        assert room_of(final, LETTER) == "the_stair"
        assert not any("stays with" in n for n in notes), notes


class TestAReleaseReceipt:
    """`verify_patch` on a release, between the two worlds of its span. On its
    own a release is met only when nothing holds the thing; beside the same
    span's arrival (a transfer of the thing) it is the departure, met when the
    carriage that stood when the span began is gone."""

    def _worlds(self, after_record, held=True):
        before = _lighthouse()
        before["entities"][LETTER] = dict(_MINT)
        if held:
            before["contained"][LETTER] = {"in": RHONA, "mode": "held"}
        after = copy.deepcopy(before)
        after["contained"].pop(LETTER, None)
        if after_record:
            after["contained"][LETTER] = after_record
        return before, after

    def _status(self, after_record, *, to=None, relation="held", held=True):
        """The release receipt's status, the span carrying a transfer of the
        letter to `to` when one is named."""
        before, after = self._worlds(after_record, held=held)
        patch = {"containment": {LETTER: None}}
        if to:
            patch["inventory_ops"] = [{
                "op": "transfer", "object_id": LETTER, "from_id": RHONA,
                "to_id": to, "relation": relation}]
        receipts = [r for r in verify_patch(before, after, patch)
                    if r["channel"] == "containment"]
        assert len(receipts) == 1
        return receipts[0]["status"]

    def test_let_go_of_entirely_is_met(self):
        assert self._status(None) == "applied"

    def test_handed_on_within_the_span_is_met(self):
        assert self._status({"in": PELL, "mode": "pocket"},
                            to=PELL, relation="pocket") == "applied"

    def test_moved_from_her_hand_to_her_own_pocket_is_met(self):
        assert self._status({"in": RHONA, "mode": "pocket"},
                            to=RHONA, relation="pocket") == "applied"

    def test_still_in_the_same_hand_is_not(self):
        assert self._status({"in": RHONA, "mode": "held"},
                            to=PELL) == "unresolved"

    def test_still_borne_by_the_evidence_that_stood_is_not(self):
        """A record the merge re-derived for the same holder (`by: bearing`,
        her hand still on it) is the old carriage, not a new one."""
        assert self._status({"in": RHONA, "mode": "carried", "by": "bearing"},
                            to=PELL) == "unresolved"

    def test_a_release_alone_is_not_met_by_a_holder_nothing_in_its_span_named(self):
        """With no arrival in its span, a release that ends with somebody
        holding the thing did not take, whoever that is."""
        assert self._status({"in": PELL, "mode": "pocket"}) == "unresolved"

    def test_nothing_held_to_begin_with_is_already_true(self):
        assert self._status(None, held=False) == "unchanged"

    def test_a_loose_thing_released_and_picked_up_is_not_refused(self):
        """Nothing carried it when the span began, so the release has nothing
        to end, and the span's own transfer says who picked it up."""
        assert self._status({"in": PELL, "mode": "held"}, to=PELL,
                            held=False) != "unresolved"
