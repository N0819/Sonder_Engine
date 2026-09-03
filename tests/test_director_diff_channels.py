"""The guard on the two whole-diff readers in `agents/director_evidence.py`.

Both of them answer a question ABOUT a `StateDiff` -- "did this diff encode
anything at all" (`_diff_is_substantive`) and "does any channel reference this
subject" (`_omission_subject_encoded`) -- and both used to answer it from a
list of channels written out by hand. Against the 37-channel schema the first
walked 16 and the second 13, so `containment`, `stations`, `scales`, `vitals`
and `overlays` were invisible to a check whose whole job is to notice them:
a beat encoded only in those read as encoding NOTHING (tripwire, deep audit)
or as an UNENCODED player claim (repair call). Both drifts spend a model call
on a diff that was already correct.

The fix derives the channel set from the schema, so what these tests hold is
the classification: every StateDiff channel appears in exactly one table, and
a channel the schema grows fails here until someone decides which. That
failure is the only mechanism that has ever kept a list like this current --
the two drifts above happened silently, over the several releases that added
those channels.
"""

import inspect

import pytest
from pydantic import BaseModel

# The two seams are CALLED, so they come through the facade like any caller's.
from agents.director import (
    _diff_is_substantive,
    _normalize_diff_shape,
    _omission_subject_encoded,
)
# The tables are not called, they are READ, and they have to be read off the
# module that defines them: a re-export is a different binding, so a guard on
# a hand-kept table that read a copy could pass while the original drifted --
# the same reason a monkeypatch must name the defining module
# (`docs/experiments/AUDIT_COMMIT.md`).
from agents import director_evidence
from llm import schemas

_CHANNEL_WORD_SUBJECTS = getattr(director_evidence, "_CHANNEL_WORD_SUBJECTS")
_NON_SUBSTANTIVE_CHANNELS = getattr(
    director_evidence, "_NON_SUBSTANTIVE_CHANNELS")
_SUBJECT_KEYED_CHANNELS = getattr(director_evidence, "_SUBJECT_KEYED_CHANNELS")
_SUBJECT_OP_CHANNELS = getattr(director_evidence, "_SUBJECT_OP_CHANNELS")
_SUBJECT_VALUE_CHANNELS = getattr(director_evidence, "_SUBJECT_VALUE_CHANNELS")
_SUBJECTLESS_CHANNELS = getattr(director_evidence, "_SUBJECTLESS_CHANNELS")
_SUBSTANTIVE_CHANNELS = getattr(director_evidence, "_SUBSTANTIVE_CHANNELS")


def _channels():
    """The truth these tables are held against, read from the schema itself
    rather than from the module's own helper -- deriving both sides from one
    reader would prove only that it agrees with itself."""
    return frozenset(schemas._fields(schemas.StateDiff))


# ---------------------------------------------------------------------------
# Coverage: the schema is the enumeration.
# ---------------------------------------------------------------------------

def test_every_state_diff_channel_is_counted_or_named_as_excluded():
    """`_diff_is_substantive` is derived (all channels minus the excluded
    set), so the only way it can be wrong is an exclusion nobody re-read.
    Each one therefore has to carry a stated reason, and no channel may be
    excluded that the schema does not declare -- a stale exclusion would go on
    silencing a channel that had been renamed out from under it."""
    channels = _channels()
    excluded = set(_NON_SUBSTANTIVE_CHANNELS)
    assert not excluded - channels, (
        "exclusions naming channels StateDiff no longer declares: "
        + ", ".join(sorted(excluded - channels)))
    assert _SUBSTANTIVE_CHANNELS | excluded == channels
    assert not _SUBSTANTIVE_CHANNELS & excluded
    for channel, reason in _NON_SUBSTANTIVE_CHANNELS.items():
        assert len(str(reason).strip()) > 20, channel


def test_every_state_diff_channel_is_classified_for_the_subject_check():
    """The subject tables partition the schema: keyed, value-shaped, op-shaped
    or explicitly subjectless. Exactly one home each, because a channel in two
    is a channel whose second reading nobody maintains, and a channel in none
    is the original defect."""
    tables = {
        "keyed": set(_SUBJECT_KEYED_CHANNELS),
        "value": set(_SUBJECT_VALUE_CHANNELS),
        "op": set(_SUBJECT_OP_CHANNELS),
        "subjectless": set(_SUBJECTLESS_CHANNELS),
    }
    classified = set().union(*tables.values())
    channels = _channels()
    assert not channels - classified, (
        "StateDiff channels no subject table classifies: "
        + ", ".join(sorted(channels - classified)))
    assert not classified - channels, (
        "subject tables naming channels StateDiff does not declare: "
        + ", ".join(sorted(classified - channels)))
    counted = sum(len(names) for names in tables.values())
    assert counted == len(classified), "a channel is in two tables"
    for channel, reason in _SUBJECTLESS_CHANNELS.items():
        assert len(str(reason).strip()) > 10, channel
    # The channel-word fallback ("the manifest subject IS 'contacts'") only
    # makes sense for a channel that is walked.
    assert set(_CHANNEL_WORD_SUBJECTS) <= set(_SUBJECT_OP_CHANNELS)


def test_identity_keys_name_fields_the_op_schemas_actually_declare():
    """A typo in an identity key fails the way the drift did: silently, as a
    subject the check cannot see. Where the channel's item type is a typed
    model the schema can settle it, so it does."""
    fields = schemas._fields(schemas.StateDiff)
    checked = 0
    for channel, keys in _SUBJECT_OP_CHANNELS.items():
        item = schemas._declared(fields[channel]).item_type
        if not (inspect.isclass(item) and issubclass(item, BaseModel)):
            continue  # list[dict]: untyped by design, nothing to check against
        declared = set(schemas._fields(item))
        assert set(keys) <= declared, (
            f"{channel}: {sorted(set(keys) - declared)} not declared on "
            f"{item.__name__}")
        checked += 1
    assert checked >= 5, "no typed op channel was actually checked"
    # `destruction` is declared `Optional[dict]` on StateDiff (so model_dump
    # keeps it through validation -- see its schema comment), but the shape it
    # carries is DestructionEffect, which can still settle the keys.
    assert set(_SUBJECT_OP_CHANNELS["destruction"]) <= set(
        schemas._fields(schemas.DestructionEffect))


# ---------------------------------------------------------------------------
# Behaviour: the five channels the drift had lost.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("channel, value", [
    ("containment", {"Hinami": {"in": "Tamamo", "mode": "swallowed"}}),
    ("stations", {"Mara": {"at": "hearth", "near": []}}),
    ("scales", {"Mara": 0.1}),
    ("vitals", {"Mara": {"air": 0.4}}),
    ("comms_ops", [{"op": "open", "id": "ward_link", "name": "the ward"}]),
    ("crowd_ops", [{"op": "add", "crowd_id": "quay_crowd", "room": "quay"}]),
    ("destruction", {"effect_id": "e1", "target_id": "the_bridge",
                     "kind": "collapse"}),
])
def test_a_beat_encoded_only_in_one_of_these_is_substantive(channel, value):
    """Each of these was invisible to the tripwire, which reads an empty
    answer as "the resolve encoded nothing" -- a swallowed body, a body at the
    hearth, a body shrunk to a tenth, a body drowning, a voice channel opened,
    a crowd in a room, a bridge destroyed."""
    assert _diff_is_substantive({channel: value}), channel


@pytest.mark.parametrize("channel, value", [
    ("time", {"start_seconds": 0, "duration_seconds": 30}),
    ("weather", {"sky": "overcast"}),
    ("phase_sources", {"positions.Dana": "turn:4:x"}),
    ("following_ops", [{"op": "start", "follower": "Mara", "target": "Dana"}]),
    ("claim_dispositions", [{"claim_id": "c1", "status": "realized"}]),
    ("consequences", [{"what": "the office opens", "where": "quay_road",
                       "due_seconds": 5400}]),
])
def test_bookkeeping_and_future_channels_are_not_an_encoding(channel, value):
    """The complement, and the reason the exclusions are stated rather than
    dropped: a channel present on nearly every diff (or describing some OTHER
    beat) cannot distinguish a diff that encoded this beat from one that did
    not, and counting it would silence the tripwire for good."""
    assert not _diff_is_substantive({channel: value}), channel


def test_an_empty_diff_is_not_substantive():
    assert not _diff_is_substantive({})
    assert not _diff_is_substantive(_normalize_diff_shape({}))


# ---------------------------------------------------------------------------
# Behaviour: the subject containment check reaches every channel.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("diff, subject", [
    ({"overlays": {"Mara": [{"kind": "soaked"}]}}, "Mara"),
    ({"stations": {"Mara": {"at": "hearth"}}}, "Mara"),
    ({"scales": {"Mara": 0.1}}, "Mara"),
    ({"vitals": {"Mara": {"air": 0.4}}}, "Mara"),
    # Containment is a two-body fact: the holder is as much its subject as
    # the contained, which is the same reading contact_ops has always had.
    ({"containment": {"Hinami": {"in": "Tamamo"}}}, "Hinami"),
    ({"containment": {"Hinami": {"in": "Tamamo"}}}, "Tamamo"),
    ({"comms_ops": [{"op": "open", "id": "ward_link", "rooms": ["cellar"]}]},
     "cellar"),
    ({"crowd_ops": [{"op": "add", "crowd_id": "quay_crowd", "room": "quay"}]},
     "quay_crowd"),
    ({"telling_ops": [{"speaker": "Mara", "listener": "the harbourmaster"}]},
     "harbourmaster"),
    ({"courier_ops": [{"op": "open", "sender": "Mara", "to_room": "quay"}]},
     "Mara"),
    ({"artifact_ops": [{"op": "post", "poster": "Mara", "room": "quay"}]},
     "quay"),
    ({"consequences": [{"what": "it opens", "where": "quay_road"}]},
     "quay_road"),
    ({"destruction": {"target_id": "the_bridge"}}, "the_bridge"),
    ({"following_ops": [{"op": "start", "follower": "Mara"}]}, "Mara"),
    ({"introductions": [{"who": "Mara", "learns": "Sable"}]}, "Sable"),
    ({"location": "the harbour quay"}, "harbour quay"),
])
def test_the_containment_check_sees_every_channel_that_carries_an_identity(
        diff, subject):
    """"Does ANY diff field reference this subject" is what the docstring
    promises and what the repair decision spends a model call on. A channel it
    cannot see turns a correct encoding into an omission."""
    assert _omission_subject_encoded(_normalize_diff_shape(dict(diff)),
                                     subject), (diff, subject)


def test_a_verdict_or_a_prose_field_is_not_a_reference():
    """The other direction, and the one that costs correctness rather than
    tokens. `claim_dispositions` says the Director judged a claim; if that
    counted as an encoding, the check would acquit precisely the beat where
    the Director marked a claim realized and encoded nothing. Prose is out for
    the same reason: `consequences.what` naming the vault door is a sentence
    about a future beat, not this one's encoding of it."""
    sd = _normalize_diff_shape({
        "claim_dispositions": [{"claim_id": "c1", "subject_id": "vault_door",
                                "status": "realized"}],
        "consequences": [{"what": "the vault door is found open",
                          "where": "quay_road"}],
        "world_facts": ["the vault door has always stuck in winter"],
    })
    assert not _omission_subject_encoded(sd, "vault_door")
    assert not _omission_subject_encoded(sd, "vault door")
    # ...and the channel that DOES carry it is still seen.
    sd["positions"]["vault_door"] = "quay_road"
    assert _omission_subject_encoded(sd, "vault_door")


def test_the_legacy_readings_survive_the_rewrite():
    """Everything the hand-written walk got right it still gets right: room
    ids by substring, an entry's `name`, a condition's subject, a removal
    edge, and a subject that names the CHANNEL rather than a body."""
    sd = _normalize_diff_shape({
        "rooms": {"elevator_interior": {"name": "Service Elevator"}},
        "conditions": {"c1": [{"subject_id": "Mara", "kind": "restrained"}]},
        "remove_adjacent": [{"room": "vault", "to": "hall"}],
        "contact_ops": [{"op": "add", "actor": "Mara", "target": "the rail"}],
        "substance_ops": [{"op": "release", "source": "Mara",
                           "substance": "seawater"}],
    })
    assert _omission_subject_encoded(sd, "elevator")
    assert _omission_subject_encoded(sd, "Service Elevator")
    assert _omission_subject_encoded(sd, "Mara")
    assert _omission_subject_encoded(sd, "vault")
    assert _omission_subject_encoded(sd, "contacts")
    assert _omission_subject_encoded(sd, "substance")
    assert not _omission_subject_encoded(sd, "smoke hallway")
    assert not _omission_subject_encoded(sd, "")
    # The channel word answers for the channel only while it holds something.
    assert not _omission_subject_encoded(
        _normalize_diff_shape({}), "contacts")


def test_a_malformed_channel_cannot_raise():
    """The check runs on a repair delta as well as the normalized diff, so a
    model returning a list where a map belongs (or the reverse) has to read as
    "no reference", never as a 500 in the middle of resolve."""
    sd = {"positions": ["Mara"], "contact_ops": {"actor": "Mara"},
          "rooms": "the quay", "remove_entities": "lantern",
          "conditions": {"c1": "restrained"}, "entities": None}
    assert not _omission_subject_encoded(sd, "Dana")
    # A dict where a list belongs is still read as the one record it is.
    assert _omission_subject_encoded(sd, "Mara")
