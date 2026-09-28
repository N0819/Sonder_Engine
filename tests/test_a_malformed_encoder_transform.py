"""A malformed encoder transform neither crashes the stage nor vanishes.

Found 2026-09-27 porting the Director's tests to the prose Director, which
has one encoder where there were five hands. A model that copies a whole
diff's structure into one transform's `patch` writes shapes the owners never
read, and each failed a different way:

* a `positions` write as a LIST crashed `declared_moves`, and with it the
  whole resolve;
* a patch wrapped in the diff's own envelope (`patch: {state_diff: {...}}`)
  named no channel an owner holds, so the owner split handed it to nobody
  and the write vanished without a word;
* any other key no owner holds vanished the same way.

The first is read as nothing, the second is unwrapped where the encoder's
answer is first read (`director_prose.patch_as_written`), and the third is
dropped out loud. The chat 80 `entities` shape is
`tests/test_entity_sibling_keys.py`'s.
"""

import agents.director as director
import agents.director_prose as director_prose
from tests.director_fakes import _make_ctx, encoder_event, prose_resolve_agent


def _resolve(temp_db, monkeypatch, prose, *transforms):
    ctx = _make_ctx(temp_db, interp={"sequence": []})
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": prose},
        per_step={"director_specialist": {"events": [encoder_event(
            prose, source="character:mara", transforms=list(transforms))],
            "missing_tools": [], "missing_referents": [], "notes": []}}))
    return ctx, director.director_resolve(ctx, nonce=0)


def test_a_list_valued_positions_write_is_read_as_nothing():
    """`declared_moves` read every `positions` value as a mapping."""
    record = {"events": [{"transforms": [
        {"item": "Mara", "patch": {"positions": ["lamp_room"]}}]}]}
    assert director_prose.declared_moves(record) == {}


def test_a_list_valued_positions_write_does_not_crash_the_stage(
        temp_db, prose_director, monkeypatch):
    _ctx, out = _resolve(temp_db, monkeypatch, "Mara climbs to the lamp.",
                         {"item": "Mara", "patch": {"positions": ["lamp_room"]}})
    assert out["resolved_event"]


def test_a_transform_wrapped_in_a_whole_diff_still_reaches_its_owner(
        temp_db, prose_director, monkeypatch):
    """The move is written, only inside the diff's envelope; it is the
    spatial owner's all the same."""
    _ctx, out = _resolve(
        temp_db, monkeypatch, "Mara climbs to the lamp.",
        {"item": "Mara", "patch": {"state_diff": {"positions": {"Mara": "lamp_room"}}}})
    assert (out["state_diff"].get("positions") or {}).get("Mara") == "lamp_room", \
        out["state_diff"].get("positions")


def test_a_wrapper_never_overrides_a_channel_the_patch_already_carries():
    patch = director_prose.patch_as_written({
        "positions": {"Mara": "keeper_room"},
        "state_diff": {"positions": {"Mara": "lamp_room"},
                       "poses": {"Mara": {"posture": "standing"}}}})
    assert patch == {"positions": {"Mara": "keeper_room"},
                     "poses": {"Mara": {"posture": "standing"}}}


def test_a_channel_no_owner_holds_is_dropped_out_loud(
        temp_db, prose_director, monkeypatch):
    ctx, _out = _resolve(temp_db, monkeypatch, "Mara climbs to the lamp.",
                         {"item": "Mara", "patch": {"positons": {"Mara": "lamp_room"}}})
    assert any("positons" in w and "no channel owner" in w for w in ctx.warnings), \
        ctx.warnings
