"""`nsfw_prompt_ids` is the only thing that decides the adult overlay.

Review finding B11: three sites answered one question. `specialist_prompt`
read a per-hand `specialists.<name>.nsfw` flag, `prose_author_prompt` appended
the overlay unconditionally, and `get_prompt_body` read the roster. All three
agreed on the shipped packs -- which is why the disagreement would have been
invisible: a pack that names `director_body` in the roster and clears its flag
gets the overlay from one spelling and not from the other, and the sheet a
model is actually sent depends on which function assembled it.

These tests hand the assembly paths a card whose roster DISAGREES with the old
per-hand flag, and require the roster to win everywhere.
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


def test_a_specialist_sheet_takes_the_overlay_only_when_the_roster_names_it(
        card_with_roster):
    """The hand's own name in the roster is the whole condition. `social`
    carried `nsfw: false` and `body` carried `nsfw: true`, so a roster that
    says the opposite is what separates the two answers."""
    card = card_with_roster(["director_social"])
    names = sorted(card["specialists"])
    assert "social" in names and "body" in names

    for name in names:
        sheet = prompts.specialist_prompt(name, card["specialists"][name]["order"])
        expected = name == "social"
        assert (_overlay(card) in sheet) is expected, (
            f"specialist {name!r} disagrees with the roster it was given")


def test_the_causal_director_never_receives_a_content_style_overlay(
        card_with_roster):
    """It slices causality; it does not author content at either invocation."""
    card = card_with_roster(["director_body"])
    assert _overlay(card) not in prompts.prose_author_prompt(None)

    card = card_with_roster(["director_resolve_lean"])
    assert _overlay(card) not in prompts.prose_author_prompt(None)


def test_a_stored_prompt_body_answers_from_the_same_roster(card_with_roster):
    """The third site, unchanged in behaviour and now sharing the reader."""
    card = card_with_roster(["narrator"])
    assert _overlay(card) in prompts.get_prompt_body("narrator")
    assert _overlay(card) not in prompts.get_prompt_body("character")


def test_the_overlay_is_withheld_from_every_sheet_when_nsfw_is_off(
        card_with_roster, monkeypatch):
    """One switch above the roster, and it must reach all three paths."""
    card = card_with_roster(list(prompts.DEFAULT_PROMPTS))
    monkeypatch.setattr(prompts, "nsfw_enabled", lambda: False)
    overlay = _overlay(card)
    assert overlay not in prompts.prose_author_prompt(None)
    assert overlay not in prompts.get_prompt_body("narrator")
    for name, spec in card["specialists"].items():
        assert overlay not in prompts.specialist_prompt(name, spec["order"])


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
    for name, spec in prompts.SPECIALIST_PROMPT_SPECS.items():
        assert "nsfw" not in spec, name


def test_the_shipped_packs_overlay_only_state_writing_hands():
    for pack in installed_language_packs(refresh=True).values():
        roster = set(pack.card("system_prompts")["nsfw_prompt_ids"])
        assert {"director_body", "director_contact", "director_spatial"} <= roster, pack.id
        assert not {"director_interpret", "director_resolve_lean"} & roster
        assert not {"director_social", "director_objects"} & roster, pack.id
