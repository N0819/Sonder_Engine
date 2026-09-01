"""The comms channel, end to end: ledger -> hand -> vocabulary -> auditor.

`comms_ops` is the spatial specialist's channel (`director_scopes.SPECIALISTS`)
and `scene["comms"]` is the ledger it maintains: which rooms and which carried
sets a voice crosses between, whether the channel is live, and whether it plays
out loud. Perception reads that ledger and nothing else (`spatial.comms_link`),
so a channel the engine keeps after the beat that killed it goes on carrying
voices through walls for the rest of the story.

Four surfaces had to agree for a ruling to survive and none of them did:

  * the SPATIAL PAYLOAD carried no `comms`, so every `remove`/`open`/`close`
    was addressed by a guessed id -- and `apply_comms_ops` fails silently in
    three directions on a wrong one (`test_a_guessed_channel_id_...` below);
  * `director_establish` taught the channel and left it out of the output
    shape, on the one stage that can install one at beat zero;
  * the prose author's `changes_asserted` vocabulary omitted 'comms', which
    made `comms_ops` the ONE channel in `_CATEGORY_CHANNELS` no manifest entry
    could route to;
  * the reconcile auditor's category list omitted it too.

The reachability test is the general one: it fails for the NEXT delegated
channel that arrives without a published category, not only for this one.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents import director
from agents.director import (
    _CATEGORY_CHANNELS,
    SPECIALISTS,
    _normalize_omission_category,
)
from language_runtime.card_source import read_card_source
from world import spatial


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "ja")


def _scene():
    return {
        "rooms": {
            "bridge": {"name": "Bridge", "adjacent": []},
            "hold": {"name": "Hold", "adjacent": []},
        },
        "positions": {"Mara": "bridge", "Teo": "hold"},
        "stations": {},
        "poses": {},
        "contained": {},
        "comms": {
            "ship_intercom": {
                "name": "ship's intercom",
                "rooms": ["bridge", "hold"],
                "carriers": [],
                "mode": "duplex",
                "source": "",
                "private": False,
                "live": True,
            },
            "field_set": {
                "name": "handheld radio pair",
                "rooms": ["bridge"],
                "carriers": ["Teo"],
                "mode": "duplex",
                "source": "",
                "private": True,
                "live": True,
            },
        },
    }


def _view():
    return {"source": "resolved_beat", "player": "Mara", "cast": ["Teo"],
            "declared_actions": [], "dice": {}, "prose": "Teo kills the set.",
            "dialogue": [], "manifest": []}


def _payload(name, scene=None, extras=None):
    ctx = SimpleNamespace(chat={"id": 1})
    return director._specialist_payload(
        name, ctx, scene if scene is not None else _scene(), _view(),
        extras or {})


def test_the_spatial_hand_is_given_the_comms_ledger_it_maintains():
    """The hand that owns `comms_ops` sees the channels, keyed by the id its
    ops address. Rows rather than the stored table, because `comms_ops` is a
    list whose entries carry `id` -- the ledger comes back in the shape the
    op is written in, as `substances` and `contact_actions` do."""
    assert "comms_ops" in SPECIALISTS["spatial"]["channels"]

    rows = _payload("spatial")["comms"]

    assert [row["id"] for row in rows] == ["field_set", "ship_intercom"]
    intercom = next(r for r in rows if r["id"] == "ship_intercom")
    # Every field an op has to restate on a `set`, which its own chunk calls
    # "a COMPLETE replacement snapshot": a hand that cannot see `private` or
    # `mode` cannot re-set a channel without inventing them.
    assert intercom["rooms"] == ["bridge", "hold"]
    assert intercom["mode"] == "duplex"
    assert intercom["private"] is False
    assert intercom["live"] is True
    assert next(r for r in rows if r["id"] == "field_set")["carriers"] == ["Teo"]


def test_no_other_hand_is_given_the_comms_ledger():
    """Scoped like every other ledger in this fan-out: the owner sees it and
    nobody else does. Widening what the OWNER can address is not widening
    what any other hand knows."""
    for name in SPECIALISTS:
        if name == "spatial":
            continue
        assert "comms" not in _payload(name), name


def test_the_comms_ledger_is_absent_rather_than_empty_when_there_is_none():
    """A scene with no comms equipment hands the spatial payload an empty
    list, not a missing key -- the same shape every beat, so 'no channels'
    reads as a fact rather than as a payload that failed to build."""
    scene = _scene()
    scene.pop("comms")
    assert _payload("spatial")["comms"] != []
    assert _payload("spatial", scene=scene)["comms"] == []


def test_a_guessed_channel_id_fails_silently_in_three_directions():
    """WHY the payload above is not a convenience. `apply_comms_ops` addresses
    every maintenance op by `id`, and on an id that names nothing it neither
    raises nor reports: `remove` pops nothing, `close` finds no record to flip,
    and a re-`set` installs a SECOND channel beside the one it meant to
    replace. All three leave the original live, and `comms_link` then keeps
    carrying a voice between the rooms the beat just cut apart."""
    scene = _scene()

    spatial.apply_comms_ops(scene, [{"op": "remove", "id": "intercom"}])
    assert "ship_intercom" in scene["comms"]

    spatial.apply_comms_ops(scene, [{"op": "close", "id": "intercom"}])
    assert scene["comms"]["ship_intercom"]["live"] is True

    spatial.apply_comms_ops(scene, [{
        "op": "set", "id": "intercom", "name": "ship's intercom",
        "rooms": ["bridge", "hold"], "live": False}])
    assert set(scene["comms"]) == {"ship_intercom", "field_set", "intercom"}
    assert scene["comms"]["ship_intercom"]["live"] is True

    # The voice still crosses, which is the whole cost of the missing id.
    assert spatial.comms_link(scene, "bridge", "hold", speaker_name="Mara",
                              observer_name="Teo") is not None

    # Addressed by the id the payload now hands over, all three land.
    scene = _scene()
    spatial.apply_comms_ops(scene, [{"op": "remove", "id": "ship_intercom"}])
    assert "ship_intercom" not in scene["comms"]


def _published_manifest_categories(language):
    """The `changes_asserted` category vocabulary, read out of the sheet that
    publishes it (`prose_author_sheet/04.txt`) rather than restated here -- a
    hand-copy of a vocabulary is free to disagree with the prompt that is
    actually sent."""
    card = read_card_source(ROOT / "language_packs" / language,
                            "system_prompts")
    text = card["prose_author_sheet"][4][1]
    match = re.search(r"category:((?:'[a-z_]+'\|)+'[a-z_]+')", text)
    assert match, f"{language}: no category vocabulary found in the sheet"
    return {token.strip("'") for token in match.group(1).split("|")}


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_delegated_channel_is_reachable_from_the_published_vocabulary(
        language):
    """THE GENERAL GUARD. `_CATEGORY_CHANNELS` routes a manifest category to
    the specialist owning the channel that answers for it; the sheet above is
    the only place that vocabulary is published to the author who writes it.
    A channel in the table that no published category folds onto is a route
    nothing can enter -- the change is then detected as an omission every beat
    and repaired by a mind that never saw it (measured at 49.2s for two such
    events in one beat, in the note beside the table).

    Asserted on CHANNELS, not on keys: the table deliberately carries raw and
    normalized spellings of the same category ('contact'/'contacts',
    'pose'/'poses'), and only one of each pair is ever reached.

    `comms_ops` was the only unreachable one when this was written.
    """
    reached = {
        _CATEGORY_CHANNELS[folded]
        for folded in (_normalize_omission_category(cat)
                       for cat in _published_manifest_categories(language))
        if folded in _CATEGORY_CHANNELS
    }
    unreachable = sorted(set(_CATEGORY_CHANNELS.values()) - reached)
    assert not unreachable, (
        f"{language}: delegated channels no published changes_asserted "
        f"category can route to: {unreachable}. Publish a category for each "
        "in prose_author_sheet/04.txt, or the change reaches no hand.")


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_manifest_vocabulary_publishes_comms(language):
    assert "comms" in _published_manifest_categories(language)
    assert _CATEGORY_CHANNELS[
        _normalize_omission_category("comms")] == "comms_ops"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_reconcile_auditor_has_a_word_for_a_comms_change(language):
    """The pass that reports what the diff LEFT OUT is folded by the same
    normalizer, so a category it cannot name is an omission it cannot route.
    This list stays narrower than the manifest's by design and is not tested
    for full channel coverage."""
    card = read_card_source(ROOT / "language_packs" / language,
                            "system_prompts")
    assert "'comms'" in card["prompts"]["resolve_reconcile"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_establish_can_install_a_channel_at_beat_zero(language):
    """`director.py`'s establish merge runs `comms_ops` through the same
    `apply_comms_ops` every later beat uses, so a scene BUILT around an
    intercom can have one before the first beat. A field the OUTPUT SHAPE
    does not name is a field the model has no reason to believe exists --
    measured on the resolve side, where exactly that drew zero emissions."""
    card = read_card_source(ROOT / "language_packs" / language,
                            "system_prompts")
    text = card["prompts"]["director_establish"]
    shape = text.rsplit("\n", 1)[-1]
    assert "comms_ops:[" in shape, (
        f"{language}: director_establish teaches comms_ops and omits it from "
        "the output shape")
    # And the teaching must not be the MID-BEAT chunk pasted verbatim. That
    # chunk's closing sentence is "emit nothing when no equipment CHANGED --
    # an installed channel keeps working without being restated", which is
    # true of every beat except this one: at establishment nothing has changed
    # and nothing is already installed, so it reads as an instruction to emit
    # nothing on the one stage whose job is to state what already stands. EN
    # carried it and JA did not; derived from the chunk so a future paste into
    # either pack is caught rather than a hand-copied English string.
    chunk = card["specialists"]["spatial"]["chunks"]["comms_ops"]
    closing = [line for line in chunk.strip().splitlines() if line.strip()][-1]
    assert closing not in text, (
        f"{language}: director_establish carries the mid-beat chunk's closing "
        "sentence unadapted; at beat zero it points away from emitting")
