"""A card's free description is never what every observer sees.

The heuristic (non-AI) import took the first three sentences of a card's
`description` as `embodiment.visible.summary` -- the stable body appearance
every observer is delivered: the stranger's label, a background presence's
view, the narrator's body facts. A SillyTavern description mixes appearance,
backstory and secrets in any order, so the second sentence of "Aria is a
23-year-old mage. She secretly spies for the thieves guild and has told no
one." reached every mind in the room; and the splitter knew only `.!?`, so a
Japanese description (`。`, no spaces) was one "sentence" and landed WHOLE
(story_attire_import audit F1; the lane brief's F3). The persona path did the
same.

Position in a paragraph is not evidence that a sentence is visible. The
summary is now taken only from a field that SAYS it is appearance; otherwise
it stays the default a blank card has, and the description is kept where the
character's own knowledge of itself belongs -- private history, known to
nobody else -- so nothing the author wrote is lost.
"""

from __future__ import annotations

import json

from story import importers
from story.character_schema import character_private_history


SECRET = "She secretly spies for the thieves guild and has told no one."
DESCRIPTION = ("Aria is a 23-year-old mage. " + SECRET
               + " Silver hair, blue eyes. Lost her family young.")
JA_SECRET = "実は盗賊ギルドの密偵であり、誰にも正体を明かしていない。"
JA_DESCRIPTION = "アリアは二十三歳の魔術師。銀髪で青い瞳。" + JA_SECRET


def _summary(sheet):
    return sheet["embodiment"]["visible"]["summary"]


def test_a_secret_in_the_description_is_not_the_visible_body():
    sheet = importers.heuristic_character_sheet(
        {"name": "Aria", "description": DESCRIPTION})
    assert "spies" not in _summary(sheet)
    assert "thieves" not in json.dumps(sheet["embodiment"])


def test_nor_in_a_script_without_spaces():
    sheet = importers.heuristic_character_sheet(
        {"name": "アリア", "description": JA_DESCRIPTION})
    assert "密偵" not in _summary(sheet)


def test_the_description_is_kept_as_the_characters_own_knowledge():
    sheet = importers.heuristic_character_sheet(
        {"name": "Aria", "description": DESCRIPTION})
    private = character_private_history(sheet)
    assert any(SECRET in e["content"] and not e.get("known_by")
               for e in private)


def test_a_field_that_says_it_is_appearance_is_the_summary():
    sheet = importers.heuristic_character_sheet(
        {"name": "Aria", "description": DESCRIPTION,
         "appearance": "A slight woman with silver hair and blue eyes."})
    assert _summary(sheet) == "A slight woman with silver hair and blue eyes."


def test_a_persona_description_is_not_the_players_visible_body(temp_db):
    _pid, sheet = importers.import_persona(
        {"name": "Dana", "description": "Dana is a courier. She carries a "
         "stolen ledger nobody knows about."}, reinterpret=False)
    assert "ledger" not in _summary(sheet)


def test_example_dialogue_notes_split_in_every_script():
    sheet = importers.heuristic_character_sheet(
        {"name": "アリア", "mes_example": "「はい。」一つ目。二つ目。三つ目。"})
    assert "三つ目" not in sheet["social"]["voice"]["notes"]
