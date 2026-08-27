"""A ship's computer is a voice, not a bystander.

Live play put the Enterprise computer in the scene as `computer`, kind=agent,
**positioned in `enterprise_ten_forward`** — so the engine believed the ship's
AI existed in one room. Walk to Deck 14 and it is not "present".

The alternative was not even expressible: `USS Enterprise D` carried
`interior_rooms=[]` and every Enterprise room had `parent_entity=None`, so there
was no containment to scope ubiquity against. Rather than build vessel-scoped
presence, a bodiless voice is simply exempt from position: the Director voices
it, it is audible wherever the scene is, and it is never tracked as a presence.

The trap this guards: `spatial_rel(None, room)` yields barrier='unknown', so
`hear_level` returns 'none'. Without the exemption the Director could voice the
ship's computer and no perceiver would hear a word of it.
"""

from __future__ import annotations

import pytest

from story.scene import (UBIQUITOUS_KINDS, is_ubiquitous_entity,
                   ubiquitous_speaker_names)
from world.spatial import hear_level, spatial_rel


def _scene():
    return {
        "rooms": {"ten_forward": {"adjacent": []}, "deck14": {"adjacent": []}},
        "positions": {"Hinami": "ten_forward"},
        "entities": {
            "computer": {"name": "Computer", "kind": "agent",
                         "ubiquitous": True},
            "guinan_entity": {"name": "Guinan", "kind": "agent"},
        },
    }


def test_explicit_flag_marks_a_bodiless_voice():
    assert is_ubiquitous_entity({"kind": "agent", "ubiquitous": True})


@pytest.mark.parametrize("kind", sorted(UBIQUITOUS_KINDS))
def test_recognized_kinds_need_no_flag(kind):
    """The model forgetting the flag must not silently re-create the bug."""
    assert is_ubiquitous_entity({"kind": kind})


def test_an_ordinary_npc_is_not_ubiquitous():
    assert not is_ubiquitous_entity({"name": "Guinan", "kind": "agent"})
    assert not is_ubiquitous_entity({"name": "Sake Carafe", "kind": "object"})
    assert not is_ubiquitous_entity(None)


def test_names_and_ids_both_resolve():
    names = ubiquitous_speaker_names(_scene())
    assert "computer" in names       # entity id
    assert "computer" in names       # display name, casefolded
    assert "guinan" not in names


def test_the_silence_trap_is_real():
    """Documents WHY the exemption exists: a room-less speaker is inaudible."""
    rel = spatial_rel(_scene(), None, "ten_forward")
    assert hear_level(rel, "normal") == "none"


def test_bodiless_voice_is_never_tracked_as_a_presence(temp_db):
    """Tracking one pinned it to a room and made it promotable."""
    import time
    from persist.commit import track_background_presences
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Trek", "", time.time()))
    temp_db.wset(cid, "scene", _scene())
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Trek", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=tid, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {
        "resolved_event": "The computer answers.",
        "dialogue_log": [
            {"speaker": "Computer", "exact_quote": "Working."},
            {"speaker": "Guinan", "exact_quote": "Long day?"},
        ],
        "state_diff": {"entities": {
            "computer": {"name": "Computer", "kind": "agent",
                         "ubiquitous": True},
            "guinan_entity": {"name": "Guinan", "kind": "agent"},
        }},
    }
    track_background_presences(ctx, nonce=0)
    from persist.commit import presence_name_items
    tracked = temp_db.wget(cid, "background_presences", {}) or {}
    names = {n for n, _ in presence_name_items(tracked)}
    assert "Computer" not in names        # a voice, not a bystander
    assert "Guinan" in names              # an ordinary extra still is one


# ---- the rescue must be asked of the ENTITY, not of the position ---------

def test_a_stale_position_does_not_disable_the_exemption():
    """The guard used to be "this speaker has no room", which a single stale
    `positions` entry falsifies -- and the artifact the exemption exists for
    is exactly such an entry. Measured live: a computer flagged `ubiquitous`
    but still pinned to the room it was first voiced in answered a direct
    question from four decks away, and the answer died at hear_level 'none'.
    """
    scene = _scene()
    scene["positions"]["Computer"] = "ten_forward"   # the category error

    assert "computer" in ubiquitous_speaker_names(scene)
    assert is_ubiquitous_entity(scene["entities"]["computer"])


def test_merge_removes_the_position_a_bodiless_voice_should_never_have():
    from world.spatial import merge_scene_with_diff

    scene = _scene()
    scene["positions"]["Computer"] = "ten_forward"

    merged = merge_scene_with_diff(scene, {})

    assert "Computer" not in merged["positions"]
    assert "computer" in merged["entities"], "the voice itself survives"
    assert merged["positions"]["Hinami"] == "ten_forward", "bodies untouched"


def test_pruning_reports_what_it_dropped_and_is_idempotent():
    from world.spatial import prune_bodiless_positions

    scene = _scene()
    scene["positions"]["Computer"] = "ten_forward"

    assert prune_bodiless_positions(scene) == ["Computer"]
    assert prune_bodiless_positions(scene) == []


def test_pruning_is_total_on_a_scene_without_either_table():
    from world.spatial import prune_bodiless_positions

    assert prune_bodiless_positions({}) == []
    assert prune_bodiless_positions({"positions": "junk"}) == []
    assert prune_bodiless_positions({"positions": {}, "entities": {}}) == []
