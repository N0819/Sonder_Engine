"""THE ROOM AUTHOR'S SHAPE HOLDS EVERY FIELD ITS SHEET ASKS FOR.

The room designer's sheet (`llm.prompts.room_author_prompt`: its core, then
the spatial hand's room chunks) tells it that "the rooms instructions below
are the record's exact shape and vocabulary; follow them for every field".
So a field the same sheet asks for and the shape line leaves out is a field
the sheet both asks for and rules out, and a model that follows the exact
shape writes it nowhere -- or into `desc`, where every mind that walks in
reads it as what is there.

Review F1 of the standing-looks lane (2026-10-09): the core's first design
step asks a place seen from outside for a `far_look`, and the shape line it
embeds (`specialists/spatial/chunks/rooms.txt`) carried none; nor `offset`,
which the core asks of a fixture or doorway the prose fixes along its wall;
nor `sight_from`, which the one_way_window clause asks of a doorway. The ja
line had lagged the en one since 2026-09-15 and also lacked `way`, `surface`,
`level`, `over` and `floor`. When the room author runs, the encoder's own
rooms chunk -- which does carry `far_look` -- is not shipped
(`director_prose`'s `encoder_channels`), so this line is the only rooms shape
the writer of a newly minted place sees.

Stated as the class: every field of the room record that the assembled sheet
names in code is a key of its shape line, in both packs -- and the line
promises nothing the commit's validation drops (`sound` is named by the
vocabulary and kept by no `RoomDef` field, so it stays off the line).
"""

from __future__ import annotations

import re

import pytest

from llm import schemas
from llm.prompts import room_author_prompt
from world.structure import LAYOUT_ANCHOR_FIELDS, LAYOUT_EDGE_FIELDS

#: The fields a doorway carries that the engine reads by name, beside the
#: ones a solved plan lays (`LAYOUT_EDGE_FIELDS`): where it leads, what
#: stands in it, how far and which way it climbs, what it is called, and the
#: two one-way markers (`passage_from`, read by `spatial_barriers`;
#: `sight_from`, by `spatial_routing`).
DOORWAY_FIELDS = ("to", "barrier", "distance", "vertical", "way", "name",
                  "passage_from", "sight_from")


def _record_fields():
    """Every key the room record can carry: what `RoomDef` keeps through the
    commit's validation, and an anchor's and a doorway's own fields."""
    return (set(schemas._fields(schemas.RoomDef)) | set(LAYOUT_ANCHOR_FIELDS)
            | set(LAYOUT_EDGE_FIELDS) | set(DOORWAY_FIELDS))


def _shape_line(sheet):
    lines = [line for line in sheet.splitlines()
             if line.startswith(("Shape: rooms:", "形状：rooms:"))]
    assert len(lines) == 1, "one rooms shape line in the sheet"
    # The record from `rooms:` to the explanation after it, without the
    # line's own label ("Shape:", "形状：").
    line = lines[0]
    return re.split("--|――", line[line.index("rooms:"):])[0]


def _keys(shape):
    return set(re.findall(r"[A-Za-z_]+", shape))


@pytest.mark.parametrize("language", ["en", "ja"])
def test_every_field_the_room_authors_sheet_asks_for_is_in_its_exact_shape(language):
    sheet = room_author_prompt(language)
    keys = _keys(_shape_line(sheet))
    # A backtick span that IS a field, or opens with one (`sight_from:'<id>'`).
    named = set(re.findall(r"`([A-Za-z_]+)(?:[:=][^`]*)?`", sheet)) & _record_fields()
    assert {"far_look", "offset", "sight_from"} <= named, "the sheet asks for them"
    assert named <= keys, sorted(named - keys)


@pytest.mark.parametrize("language", ["en", "ja"])
def test_a_place_seen_from_outside_has_a_far_look_and_a_fixture_its_place_along_the_wall(language):
    """The two cases the review named, where the line carries them: a room's
    `far_look`, and `offset` on a doorway and on a fixture alike."""
    shape = _shape_line(room_author_prompt(language))
    adjacent = re.search(r"adjacent:\[\{([^}]*)\}\]", shape).group(1).split(",")
    anchors = re.search(r"anchors\?:\{anchor_id:\{([^}]*)\}\}", shape).group(1).split(",")
    assert "far_look?" in shape.split(",")
    assert "offset?" in adjacent and "sight_from?" in adjacent
    assert "offset?" in anchors
    # Every anchor written says its height and footprint, as the vocabulary
    # asks (2026-09-15) -- the ja line offered both as optional.
    assert "height" in anchors and "footprint" in anchors


def test_both_packs_hand_the_room_author_the_same_shape():
    """The shape is protocol, so the two packs' lines carry the same keys."""
    en = _keys(_shape_line(room_author_prompt("en")))
    ja = _keys(_shape_line(room_author_prompt("ja")))
    assert en == ja, (sorted(en - ja), sorted(ja - en))


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_shape_promises_no_room_field_the_commit_drops(language):
    """A top-level key of the line is a field `RoomDef` keeps: a key it does
    not declare is dropped by the validation every beat's diff passes
    through, so a shape naming one asks for a write that never lands."""
    shape = _shape_line(room_author_prompt(language))
    inner = shape.split("rooms:{room_id:{", 1)[1]
    depth, top, word = 0, [], ""
    for ch in inner:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if depth == 0 and (ch.isalpha() or ch == "_"):
            word += ch
            continue
        if word:
            top.append(word)
            word = ""
    assert top, "the line's own keys were read"
    assert set(top) <= set(schemas._fields(schemas.RoomDef)), sorted(
        set(top) - set(schemas._fields(schemas.RoomDef)))
    assert "sound" not in top
