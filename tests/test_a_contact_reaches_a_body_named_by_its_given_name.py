"""A declaration that names a body by its given name reaches that body, in a
name written without spaces too.

`_check_player_contact_authority` reads "does a declared act reach this body"
from any PART of the body's name -- t32's "run fingers through Mirelle's
hair" reaches "Mirelle Sulmirath". The parts came from `name.split()` with a
four-character floor, so a Japanese name had one part, itself: a
declaration naming 佐藤ヒナミ as ヒナミ reached nobody, the legitimate contact
was reported as the player acting undeclared, and after a retry the op is
DROPPED (agents_common audit F14). Parts of an unspaced name are its script
runs (`_unspaced_name_parts`), floored by their script (`_display_floor`).
"""

from __future__ import annotations

import json

from language_runtime import language_scope
from story.character_schema import default_character_data

from agents.common import _check_player_contact_authority


def _op(target):
    return {"op": "add", "actor": "ドクター", "actor_part": "hand",
            "target": target, "target_part": "hair"}


def test_a_given_name_reaches_the_body_it_names():
    cast = [{"id": 7, "sheet": json.dumps(default_character_data("佐藤ヒナミ"))}]
    with language_scope("ja"):
        reached = _check_player_contact_authority(
            [_op("佐藤ヒナミ")],
            [{"attempt": "ヒナミの髪に指を通す", "targets": []}],
            "ドクター", cast=cast)
        nobody = _check_player_contact_authority(
            [_op("佐藤ヒナミ")],
            [{"attempt": "ベッドに横たわる", "targets": []}],
            "ドクター", cast=cast)
    assert reached == [], reached
    assert nobody and nobody[0][0] == 0


def test_english_reach_is_unchanged():
    cast = [{"id": 7, "sheet": json.dumps(
        default_character_data("Mirelle Sulmirath"))}]
    op = {"op": "add", "actor": "Hinami", "actor_part": "hand",
          "target": "Mirelle Sulmirath", "target_part": "hair"}
    assert _check_player_contact_authority(
        [op], [{"attempt": "run fingers through Mirelle's hair"}],
        "Hinami", cast=cast) == []
    assert _check_player_contact_authority(
        [op], [{"attempt": "lie back on the bed"}], "Hinami", cast=cast)
