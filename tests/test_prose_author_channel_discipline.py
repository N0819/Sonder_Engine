"""No Director sheet may instruct writing a channel it has no field for.

Since 2026-09-27 the Director writes prose and nothing else
(`agents/director_prose.py`); the encoder writes every channel. So neither of
the Director's sheets (`prose_contract/director_interpret`, `.../director_resolve`)
may address a channel as somewhere to write, and neither may address
`state_diff` at all. The history below is the causal Director's, whose prose
author owned half of `state_diff`; the guard it motivated is the same guard.

`prose_author_sheet/12.txt` states the contract: every delegated channel is
owned by a scoped specialist that reads the finished `resolved_event`, none of
them exists in the author's output shape, and anything written into one is
"discarded unread and re-encoded by its specialist". `27.txt` repeats it as
the last sentence of the shape. Two blocks predating the fan-out still gave
the opposite instruction, on beats where their gate opened:

  * `08.txt` (UNGATED -- every beat): "Use state_diff.entities for physical
    entities and state_diff.rooms for navigable spaces", under a heading
    telling the author to maintain a dynamic scene graph.
  * `09_transit.txt`, which was the shared `{{fragment:transit_note}}`:
    "Encode its motion in entities.<id>.state.transit = {...}" and "keep
    positions[<entity>] pointing at the exterior room". Its gate
    (`_prose_gate_facts.transit_capable`) is true whenever the scene has ANY
    containment record, so it shipped on the great majority of beats too. The
    fragment is correct where it is also used -- `director_establish` and
    `mapping_stage` do own `entities`/`rooms` -- which is exactly why a guard
    on the reader rather than on the text is the one that holds.

That is one class, not two instances, and this is its general form: the
delegated set is read from `_DELEGATED_CHANNELS` (mutated in
place as scoping changes, so a channel that moves between hands takes its
answer with it) and the author's own fields from `schemas.StateDiff`, so
neither list is transcribed here and neither can drift out of agreement with
the engine.

Naming a channel is NOT the offence -- `12.txt` names all thirty-one of them
to forbid them, and `04.txt` publishes the manifest categories. The offence is
naming one in a position that only makes sense as a place to WRITE.
"""

from __future__ import annotations

import re

import pytest

from agents.director import _DELEGATED_CHANNELS
from language_runtime import installed_language_packs


LANGUAGES = ("en", "ja")


def _delegated() -> list:
    return sorted(_DELEGATED_CHANNELS)


def _write_position_re() -> re.Pattern:
    """A delegated channel used as somewhere to PUT something.

    Four spellings, each one a form a sheet has actually used: the
    `state_diff.<channel>` address, a subscript, a dotted path into the
    channel, and a `channel:{...}` shape declaration. The boundaries are
    written as explicit ASCII lookarounds rather than `\\b` on purpose --
    `\\b` is Unicode-aware, so `entities\\b` does NOT match in the Japanese
    pack's "state_diff.entitiesを", and the guard would have passed ja/08
    while failing en/08.
    """
    alt = "|".join(re.escape(channel) for channel in _delegated())
    return re.compile(
        r"(?<![A-Za-z0-9_])(?:"
        r"state_diff\.(?:%s)(?![A-Za-z0-9_])"
        r"|(?:%s)(?![A-Za-z0-9_])\s*[\[\{:.](?=[\[\{<a-z'\"])"
        r")" % (alt, alt))


def _blocks(language: str):
    """The prose Director's two sheets."""
    card = installed_language_packs()[language].card("system_prompts")
    for stage in ("director_interpret", "director_resolve"):
        yield stage, str(card["prose_contract"][stage])


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_director_sheet_writes_a_channel(language):
    pattern = _write_position_re()
    offences = []
    for name, text in _blocks(language):
        for match in pattern.finditer(text):
            start = max(0, match.start() - 70)
            offences.append(
                f"{language} {name}: ...{text[start:match.end() + 40]}")
    assert not offences, (
        "a Director sheet instructs writing a channel; the Director writes "
        "prose and nothing else, so its tokens there are discarded unread. "
        "State the judgment in the prose and let the encoder record it:\n"
        + "\n".join(offences))


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_director_is_addressed_at_no_state_diff_field(language):
    """The same rule from the positive side, so a NEW field cannot be invented.

    The causal prose author owned half of `state_diff`, and this checked its
    sheet against the schema; the prose Director owns none of it, so every
    address would be a field it is told to write and cannot.
    """
    addressed = re.compile(r"state_diff\.([A-Za-z_][A-Za-z0-9_]*)")
    strays = [f"{language} {name}: state_diff.{field}"
              for name, text in _blocks(language)
              for field in addressed.findall(text)]
    assert not strays, (
        "the Director is addressed at a state_diff field: " + "; ".join(strays))


class TestTheGuardStillCatchesWhatItWasWrittenFor:
    """A guard is only as good as its proof that it fires.

    These are the two removed sentences verbatim. Without them a later
    loosening of the pattern (an English word boundary, a dropped spelling)
    would leave the test green and the sheet stale again.
    """

    @pytest.mark.parametrize("stale", [
        "Use state_diff.entities for physical entities and state_diff.rooms "
        "for navigable spaces.",
        "物理的実体にはstate_diff.entitiesを、移動可能な空間にはstate_diff.roomsを使う。",
        "Encode its motion in entities.<id>.state.transit = {phase:'docked'"
        "|'sealed'|'in_transit'|'arriving', hatch:'open'|'closed'|'locked', "
        "destination_room, eta_seconds, route_room}",
        "keep positions[<entity>] pointing at the exterior room it is "
        "currently at",
        "an entity with state.link = {rooms:[a,b], phase:'open'|'closed'}",
    ])
    def test_the_removed_instructions_would_fail_the_guard(self, stale):
        assert _write_position_re().search(stale), stale
