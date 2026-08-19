"""TR-2: a line spoken over a comm channel (combadge/radio/intercom) to a party
in another room must reach that party. Perception delivered dialogue purely by
physical hearing (hear_level), so a remote listener across a 'separated far'
barrier got 'none' and never heard the transmission -- the player, on a planet
surface, never heard the ship answer their combadge hail.

The fix, in _dialogue_hear_level: ordinary spatial hearing decides first, and is
overridden in ONE direction only -- a line it would DROP ('none') is rescued to
'full' when the line is a transmission addressed to this observer. A transmission
is recognised either by the director's explicit medium:'comm' tag OR by shape (a
by-name line at a spoken volume to a party who is out of earshot). The shape
floor matters because a weaker director (GLM, observed) does not reliably tag,
and a weaker perception model (nemotron, observed) will not rescue the line on
its own -- so the deterministic floor cannot depend on either cooperating. A line
already audible is never altered."""

from __future__ import annotations

# `_addresses` is the composer's. `perception.py` carried a byte-identical
# twin that no production path called, and this file imported THAT one --
# so the guard below covered a copy nothing ran.
from agents.composer import _addresses
from agents.perception import _dialogue_hear_level
from world.spatial import hear_level


REMOTE = {"same_room": False, "barrier": "separated", "distance": "remote"}
SAME_ROOM = {"same_room": True}


def test_addresses_matches_name_case_insensitively_and_lists():
    assert _addresses("Commander Reyes", "Commander Reyes")
    assert _addresses("commander reyes", "Commander Reyes")
    assert _addresses(["Chief Okonkwo", "Commander Reyes"], "Commander Reyes")
    assert not _addresses("Chief Okonkwo", "Commander Reyes")
    assert not _addresses(None, "Commander Reyes")
    assert not _addresses("Commander Reyes", "")


def test_explicit_comm_tag_reaches_addressed_party_across_a_barrier():
    plain = {"volume": "normal", "intended_target": "Commander Reyes"}
    comm = {**plain, "medium": "comm"}
    assert hear_level(REMOTE, "normal") == "none"        # the bug's baseline
    assert _dialogue_hear_level(comm, REMOTE, "Commander Reyes") == "full"


def test_shape_floor_rescues_an_untagged_named_remote_line():
    """The director (GLM) often omits medium; a by-name line to a party in
    another room is still a transmission and must reach them."""
    untagged = {"volume": "normal", "intended_target": "Commander Reyes"}
    assert _dialogue_hear_level(untagged, REMOTE, "Commander Reyes") == "full"


def test_transmission_does_not_leak_to_a_non_addressed_remote_party():
    """The rescue only carries to whom the line was addressed -- a third party
    in yet another room, not named, still hears nothing."""
    for entry in ({"volume": "normal", "intended_target": "Commander Reyes"},
                  {"volume": "normal", "intended_target": "Commander Reyes",
                   "medium": "comm"}):
        assert _dialogue_hear_level(entry, REMOTE, "Ensign Park") == "none"


def test_untagged_mutter_across_a_barrier_is_not_rescued():
    """A whisper/mutter across rooms with no explicit comm tag stays ambiguous
    and is NOT rescued -- the shape floor requires a spoken volume. An EXPLICIT
    medium:'comm' still carries a muttered line (you can murmur into a combadge)."""
    mutter = {"volume": "mutter", "intended_target": "Commander Reyes"}
    assert _dialogue_hear_level(mutter, REMOTE, "Commander Reyes") == "none"
    assert _dialogue_hear_level({**mutter, "medium": "comm"},
                                REMOTE, "Commander Reyes") == "full"


def test_audible_lines_are_never_altered():
    """The override only ever UPGRADES a dropped ('none') line. A line already
    audible by ordinary hearing is returned exactly as hear_level gives it, for
    every relation/volume -- same-room and open-door hearing are untouched."""
    for rel in (SAME_ROOM, {"barrier": "open"}, {"barrier": "open_door"}):
        for vol in ("normal", "loud", "shout", "mutter"):
            entry = {"volume": vol, "intended_target": "Commander Reyes",
                     "medium": "comm"}
            base = hear_level(rel, vol)
            if base != "none":
                assert _dialogue_hear_level(entry, rel, "Commander Reyes") == base


def test_non_addressed_lines_are_identical_to_bare_spatial_hearing():
    """Regression guard: a line NOT addressed to the observer is delivered
    byte-for-byte as the old hear_level behavior for every relation/volume --
    the rescue is scoped to the addressed party only."""
    for rel in (REMOTE, SAME_ROOM, {"barrier": "closed_door"},
                {"barrier": "open"}, {"barrier": "wall"}):
        for vol in ("normal", "loud", "shout", "mutter"):
            entry = {"volume": vol, "intended_target": "Someone Else",
                     "medium": "comm"}
            assert _dialogue_hear_level(entry, rel, "Commander Reyes") \
                == hear_level(rel, vol)
