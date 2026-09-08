"""D4 (review 2026-09-07): the roll-call sentence is blocking, so it reads
near to far.

The sentence that enumerates who is present listed bodies in whatever order
the caller handed them -- scene-dict order in production -- so the narrator
was given no arrangement at all and supplied one: a body standing at the
other door was narrated "on my right" (UNBUILT 1.149).

The rule now: ORDER, never withhold. Every body the observer can see is
still named in the same sentence with the same words; only the sequence
changes, and only where the geometry can measure it. The tier decides first
because it is the answer that always exists (`proximity_rel`), the measured
cell distance separates two bodies inside one tier, and a room with no
geometry renders exactly what it rendered before.

The narrator's own half of the same fact is `co_present_positions.depth`,
which rides an entry only where `measured_proximity_rel` MEASURED it -- the
bare "near" default that means nobody wrote stations is not evidence of
separation and never reaches the page as one.
"""

from __future__ import annotations

import json
import time

import pytest

from agents import composer
from agents.composer import Percept, _render_presence_group, presence_percepts
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data


# ---------------------------------------------------------------------------
# Fixtures: one long room, bodies pinned to cells
# ---------------------------------------------------------------------------

def _hall(cells, *, w=20, d=6):
    """A lit hall with every body pinned to its own cell."""
    room = {"name": "the Hall", "desc": "", "light": "lit",
            "exposure": "enclosed", "adjacent": [], "shape": "rectangle",
            "extent": {"w": w, "d": d},
            "anchors": {"door": {"desc": "the door", "dir": "w"}}}
    return {"rooms": {"hall": room},
            "positions": {n: "hall" for n in cells},
            "entities": {}, "attire": {}, "overlays": {},
            "orientation": {}, "contained": {}, "poses": {},
            "stations": {n: {"cell": list(c)} for n, c in cells.items()}}


def _ungeometried(names):
    """The same hall with no extent and no stations: nothing to measure."""
    room = {"name": "the Hall", "desc": "", "light": "lit",
            "exposure": "enclosed", "adjacent": []}
    return {"rooms": {"hall": room},
            "positions": {n: "hall" for n in names},
            "entities": {}, "attire": {}, "overlays": {},
            "orientation": {}, "contained": {}, "poses": {}, "stations": {}}


def _labels(sentence, *names):
    """The order the names appear in one rendered sentence."""
    return sorted(names, key=lambda n: sentence.index(n))


# ---------------------------------------------------------------------------
# The percept carries the distance
# ---------------------------------------------------------------------------

def test_depth_is_stamped_only_where_both_bodies_are_measured():
    scene = _hall({"P": (1, 2), "A": (3, 2), "B": (6, 2)})
    by_label = {p.source_label: p for p in presence_percepts(
        scene, "P", [{"name": "A"}, {"name": "B"}], {"A": "A", "B": "B"})}
    assert by_label["A"].data["depth"] == 4       # two cells, squared
    assert by_label["B"].data["depth"] == 25      # five cells, squared

    bare = presence_percepts(
        _ungeometried(["P", "A", "B"]), "P",
        [{"name": "A"}, {"name": "B"}], {"A": "A", "B": "B"})
    assert all("depth" not in p.data for p in bare), (
        "an unmeasured pair must carry no distance at all")


def test_the_distance_stays_out_of_the_dedupe_key():
    """A body that shuffled one cell has not CHANGED for this observer.
    Hashing the distance would re-announce it every beat -- the tic
    `ACTIVE_STANDING_KINDS` was emptied to stop."""
    near = presence_percepts(_hall({"P": (1, 2), "A": (3, 2)}), "P",
                             [{"name": "A"}], {"A": "A"})[0]
    stepped = presence_percepts(_hall({"P": (1, 2), "A": (4, 2)}), "P",
                                [{"name": "A"}], {"A": "A"})[0]
    assert near.data["depth"] != stepped.data["depth"]
    assert near.dedupe_key == stepped.dedupe_key


# ---------------------------------------------------------------------------
# The sentence is ordered near to far
# ---------------------------------------------------------------------------

def test_the_roll_call_reads_near_to_far_across_tiers():
    """THE ORDER IS MINTED IN THE IR, not in a renderer. `presence_percepts`
    hands the list back near to far, so every pack inherits it; the English
    group renderer only re-states it."""
    scene = _hall({"P": (1, 2), "A": (2, 2), "B": (16, 2)}, w=20)
    percepts = presence_percepts(          # handed far-first on purpose
        scene, "P", [{"name": "B"}, {"name": "A"}], {"A": "A", "B": "B"})
    assert [p.source_label for p in percepts] == ["A", "B"]
    group = _render_presence_group([(p, False, False) for p in percepts])
    assert len(group) == 1
    sentence = group[0][1]
    assert _labels(sentence, "A", "B") == ["A", "B"], sentence
    # Ordering only: nobody was withheld.
    assert "A" in sentence and "B" in sentence


def test_the_japanese_page_reads_near_to_far_too():
    """The ja adapter orders standing percepts by their index in the percept
    list, so a rule that lived in `_render_presence_group` reached one page
    of two: measured before the fix, EN "Aoi is within arm's reach and Ben
    is across the room." against JA far-first, from the same percepts. The
    fix is that both renderers read a list that is already ordered.
    """
    from language_adapters.japanese import JapaneseRenderer

    scene = _hall({"P": (1, 2), "A": (2, 2), "B": (16, 2)}, w=20)
    percepts = presence_percepts(          # handed far-first on purpose
        scene, "P", [{"name": "B"}, {"name": "A"}], {"A": "A", "B": "B"})
    text = JapaneseRenderer().render_view(percepts).text
    assert _labels(text, "A", "B") == ["A", "B"], text
    assert "A" in text and "B" in text


def test_cell_distance_separates_two_bodies_in_one_tier():
    """Both read `near` -- the tier ladder cannot tell them apart and the
    cells can."""
    scene = _hall({"P": (1, 2), "A": (3, 2), "B": (6, 2)})
    percepts = presence_percepts(
        scene, "P", [{"name": "B"}, {"name": "A"}], {"A": "A", "B": "B"})
    assert {p.data["tier"] for p in percepts} == {"near"}
    sentence = _render_presence_group(
        [(p, False, False) for p in percepts])[0][1]
    assert _labels(sentence, "A", "B") == ["A", "B"], sentence


def test_a_room_with_no_geometry_renders_in_the_order_it_was_given():
    """The whole no-change guarantee: nothing measured, nothing moved."""
    percepts = presence_percepts(
        _ungeometried(["P", "A", "B"]), "P",
        [{"name": "B"}, {"name": "A"}], {"A": "A", "B": "B"})
    sentence = _render_presence_group(
        [(p, False, False) for p in percepts])[0][1]
    assert _labels(sentence, "A", "B") == ["B", "A"], sentence


def _presence(label, *, tier, depth=None, fidelity="full"):
    data = {"tier": tier, "known": True}
    if depth is not None:
        data["depth"] = depth
    return Percept(kind="presence", channel="sight", source_label=label,
                   fidelity=fidelity, data=data, salience=0.35,
                   dedupe_key="presence:%s:x" % label)


def test_what_changed_still_leads_however_far_off_it_is():
    """The delta split outranks the ordering: a body spelled in full comes
    before the brief ones whatever the distance, which is the emphasis rule
    `_render_presence_group` already had."""
    far_fresh = _presence("Far", tier="across", depth=100)
    near_brief = _presence("Near", tier="within_reach", depth=1)
    sentence = _render_presence_group(
        [(near_brief, True, False), (far_fresh, False, True)])[0][1]
    assert _labels(sentence, "Far", "Near") == ["Far", "Near"], sentence


def test_fidelity_is_still_never_mixed():
    """Sorting happens inside each fidelity half, so a degraded body cannot
    be folded into a clearly-seen body's sentence by being nearer."""
    seen = _presence("Alma", tier="across", depth=64)
    shape = _presence(composer._dim_figure(), tier="within_reach", depth=1,
                      fidelity="degraded")
    group = _render_presence_group([(seen, False, False), (shape, False, False)])
    assert len(group) == 2
    assert all(("Alma" in s) != (composer._dim_figure() in s.casefold())
               for _p, s in group), group


def test_an_unknown_tier_sorts_last_and_moves_nobody_past_it():
    odd = _presence("Ghost", tier="")
    known = _presence("Alma", tier="across", depth=81)
    sentence = _render_presence_group(
        [(odd, False, False), (known, False, False)])[0][1]
    assert _labels(sentence, "Alma", "Ghost") == ["Alma", "Ghost"], sentence


# ---------------------------------------------------------------------------
# The narrator's half: a depth word, only where it was measured
# ---------------------------------------------------------------------------

def _chat_with(temp_db, names, scene):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()))
    for n in names:
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (n, json.dumps(default_character_data(n)), "{}", time.time(),
             "char_%s" % n))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    temp_db.wset(chat_id, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["outcome_scene"] = json.loads(json.dumps(scene))
    return ctx


def test_co_present_positions_carries_a_measured_depth(temp_db):
    from agents.narration import _position_delta_payload
    scene = _hall({"Alice": (1, 2), "Bob": (16, 2)}, w=20)
    ctx = _chat_with(temp_db, ["Alice", "Bob"], scene)
    payload, _facts, _rooms = _position_delta_payload(
        ctx, ctx.chat, "Alice", "hall", {"Bob"},
        {"Bob": {"appearance": "a tall person", "aliases": []}})
    assert payload["Bob"]["depth"] == "across", payload


def test_an_unmeasured_pair_gets_no_depth_word(temp_db):
    """`measured_proximity_rel` collapses the bare `near` default to None:
    6.7% of live bodies carry an anchored station, so treating the default
    as separation would tell the narrator something the world never said."""
    from agents.narration import _position_delta_payload
    scene = _ungeometried(["Alice", "Bob"])
    ctx = _chat_with(temp_db, ["Alice", "Bob"], scene)
    payload, _facts, _rooms = _position_delta_payload(
        ctx, ctx.chat, "Alice", "hall", {"Bob"},
        {"Bob": {"appearance": "a tall person", "aliases": []}})
    assert "Bob" in payload
    assert "depth" not in payload["Bob"], payload
