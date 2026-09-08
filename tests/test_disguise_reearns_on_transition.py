"""A standing disguise is not a change (review 2026-09-07 finding A37).

`_composer_outcome_views` ended with `if p_disguise: appearance_changed.add(
p_name)` -- true on every beat a disguise was ACTIVE rather than on the beat
it went up or came down. `appearance_changed` is what stamps `force` on an
appearance percept, and `force` means "an objective visible-form channel
moved this beat".

The composed VIEW survived it: `render_view` asks this observer's own render
ledger before it asks `force`, so a byte-identical description suppresses
(the chat 89 measurement beside `appearance_percept`). The memory renderer
has no such ledger to ask -- `_render_episode_english` counts a forced
appearance as changed whatever `prev_described` holds -- so every NPC in the
room minted one identical "you see her" episode per beat for as long as the
mask stayed on.

The transition is the condition ROW, and the beat's own diff is where it is
legible here: `world_conditions` is written by the commit, which runs after
this stage. Both kinds in `scene.SINGULAR_BODY_CONDITIONS` count, and both
directions -- a mask going up and a mask coming down are each something a
watcher sees.
"""

import json
import time

import pytest

from agents.perception import _outward_form_transitions
from tests.test_perception_presence import (
    DOCTOR, PLAYER, TAMAMO, _bystander_ctx,
)


def _disguise_the_player(db, ctx, cid="dz_a37"):
    db.qi(
        "INSERT INTO world_conditions("
        "condition_id,chat_id,subject_id,kind,started_at,payload,active) "
        "VALUES(?,?,?,?,?,?,1)",
        (cid, ctx.chat["id"], PLAYER, "physical_disguise", time.time(),
         json.dumps({
             "subject_id": PLAYER,
             "description": "her fox ears bound flat under a pilgrim's hood",
             "presented_appearance": "a hooded pilgrim in travel-stained grey",
             "concealed_terms": ["fox-eared", "fox"],
             "conceals_identity": True,
             "known_to": [],
         })))


def _forced_bodies(monkeypatch, ctx):
    """Every body the outcome pass judged visibly CHANGED this beat."""
    import agents.perception as perception

    forced = set()
    real = perception.composer.appearance_percept

    def _spy(source_name, label, description, *, force=False, **kw):
        if force:
            forced.add(source_name)
        return real(source_name, label, description, force=force, **kw)

    monkeypatch.setattr(perception.composer, "appearance_percept", _spy)
    perception.perception_outcome(ctx, nonce="n")
    return forced


def _outcome_ctx(temp_db, diff):
    ctx, char_ids = _bystander_ctx(temp_db)
    _disguise_the_player(temp_db, ctx)
    ctx.director_resolve = {
        "resolved_event": "The hall stands quiet.", "state_diff": diff,
        "dialogue_log": [], "dialogue_order": []}
    for name in (DOCTOR, TAMAMO):
        ctx.character_results[char_ids[name]] = {
            "speech": "Hm.", "action": "", "sequence": []}
    return ctx, char_ids


def test_a_mask_that_stayed_on_re_earns_nothing(temp_db, monkeypatch):
    """The defect: the disguise is active, the beat touched no condition,
    and every observer was told her appearance had just changed."""
    ctx, _ = _outcome_ctx(temp_db, {})

    assert PLAYER not in _forced_bodies(monkeypatch, ctx)


def test_a_mask_going_up_re_earns_the_description(temp_db, monkeypatch):
    """The half that must keep working: the beat that WRITES the row is the
    beat a watcher sees the form change on."""
    ctx, _ = _outcome_ctx(temp_db, {"conditions": {"dz_a37": [{
        "condition_id": "dz_a37", "subject_id": PLAYER,
        "kind": "physical_disguise", "active": 1,
        "state": {"presented_appearance": "a hooded pilgrim"}}]}})

    assert PLAYER in _forced_bodies(monkeypatch, ctx)


def test_a_mask_coming_down_re_earns_it_too(temp_db, monkeypatch):
    """A row that arrives INACTIVE is a disguise ending, which is as visible
    as one beginning."""
    ctx, _ = _outcome_ctx(temp_db, {"conditions": {"dz_a37": [{
        "condition_id": "dz_a37", "subject_id": PLAYER,
        "kind": "physical_disguise", "active": 0}]}})

    assert PLAYER in _forced_bodies(monkeypatch, ctx)


def test_the_transition_is_read_for_every_body_not_only_the_player():
    """The rule is about bodies, not about the one body it was wired to. A
    cast member's mask moved nothing at all before this: the player was the
    only subject the branch could name."""
    assert _outward_form_transitions({"conditions": {"c1": [{
        "subject_id": TAMAMO, "kind": "physical_transformation",
        "active": 1}]}}) == {TAMAMO}


@pytest.mark.parametrize("diff", [
    {},
    {"conditions": {}},
    {"conditions": []},                     # a model wrote the wrong shape
    {"conditions": {"c1": [{"subject_id": TAMAMO, "kind": "restraint"}]}},
    {"conditions": {"c1": [{"kind": "physical_disguise"}]}},
    {"conditions": {"c1": "not a row"}},
])
def test_nothing_else_in_the_channel_re_earns_a_description(diff):
    """Only the two conditions that state a body's outward form count, and an
    unreadable row is not a transition."""
    assert _outward_form_transitions(diff) == set()
