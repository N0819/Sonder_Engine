"""`nsfw_prompt_ids` is the only thing that decides the adult overlay.

Review finding B11: three sites answered one question. The causal hands'
`specialist_prompt` read a per-hand `specialists.<name>.nsfw` flag, its prose
author appended the overlay unconditionally, and `get_prompt_body` read the
roster. All three agreed on the shipped packs -- which is why the disagreement
would have been invisible: the sheet a model is actually sent depended on
which function assembled it.

Since the causal Director went (2026-09-27) the sheets assembled from a card
are the encoder's (overlaid by the owners whose channels ship, named
`director_<owner>` in the roster), the room author's (`director_spatial`) and
a stored prompt body. These tests hand them a card whose roster the test
chooses, and require the roster to win everywhere. Whether the prose
Director's own sheets should take the overlay is an open question
(`docs/UNBUILT_PIPELINE.md` § 1.1): today they do not.
"""

from __future__ import annotations

import pytest

from language_runtime import installed_language_packs
from llm import prompts


@pytest.fixture
def card_with_roster(monkeypatch):
    """Serve every assembly path one card whose roster the test chooses."""
    base = dict(prompts._prompt_card("en"))

    def _serve(roster):
        card = dict(base)
        card["nsfw_prompt_ids"] = list(roster)
        monkeypatch.setattr(prompts, "_prompt_card", lambda language=None: card)
        monkeypatch.setattr(prompts, "nsfw_enabled", lambda: True)
        monkeypatch.setattr(prompts, "active_preset", lambda: "Default")
        return card

    return _serve


def _overlay(card):
    return str(card["nsfw_overlay"])


def test_an_encoder_sheet_takes_the_overlay_only_when_the_roster_names_it(
        card_with_roster):
    """An owner's own name in the roster is the whole condition, for the
    encoder's sheet over that owner's channels. `social` carried
    `nsfw: false` and `body` `nsfw: true` under the old flag, so a roster
    that says the opposite is what separates the two answers."""
    card = card_with_roster(["director_social"])
    names = sorted(card["specialists"])
    assert "social" in names and "body" in names

    for name in names:
        sheet = prompts.unified_specialist_prompt(
            card["specialists"][name]["order"], "en")
        expected = name == "social"
        assert (_overlay(card) in sheet) is expected, (
            f"the encoder over {name!r}'s channels disagrees with the roster")


def test_the_room_author_answers_to_the_spatial_owner(card_with_roster):
    card = card_with_roster(["director_spatial"])
    assert _overlay(card) in prompts.room_author_prompt("en")
    card = card_with_roster(["director_social"])
    assert _overlay(card) not in prompts.room_author_prompt("en")


def test_a_stored_prompt_body_answers_from_the_same_roster(card_with_roster):
    """The third site, unchanged in behaviour and now sharing the reader."""
    card = card_with_roster(["narrator"])
    assert _overlay(card) in prompts.get_prompt_body("narrator")
    assert _overlay(card) not in prompts.get_prompt_body("character_bare")


def test_the_overlay_is_withheld_from_every_sheet_when_nsfw_is_off(
        card_with_roster, monkeypatch):
    """One switch above the roster, and it must reach every path."""
    base = prompts._prompt_card("en")
    card = card_with_roster(list(prompts.DEFAULT_PROMPTS)
                            + [f"director_{name}" for name in base["specialists"]])
    monkeypatch.setattr(prompts, "nsfw_enabled", lambda: False)
    overlay = _overlay(card)
    assert overlay not in prompts.prose_director_prompt("resolve", "en")
    assert overlay not in prompts.get_prompt_body("narrator")
    assert overlay not in prompts.room_author_prompt("en")
    for name, spec in card["specialists"].items():
        assert overlay not in prompts.unified_specialist_prompt(spec["order"], "en")


def test_no_pack_carries_a_second_spelling_of_the_roster():
    """The flag is deleted, not merely unread: a card that still carries one
    would read as authoritative to the next person editing a pack."""
    for pack in installed_language_packs(refresh=True).values():
        card = pack.card("system_prompts")
        for name, spec in card["specialists"].items():
            second = sorted(key for key in spec if "nsfw" in str(key))
            assert not second, (
                f"{pack.id} specialist {name!r} carries {second} beside "
                "nsfw_prompt_ids")


def test_the_shipped_packs_overlay_only_state_writing_hands():
    for pack in installed_language_packs(refresh=True).values():
        roster = set(pack.card("system_prompts")["nsfw_prompt_ids"])
        assert {"director_body", "director_contact", "director_spatial"} <= roster, pack.id
        assert not {"director_social", "director_objects"} & roster, pack.id
