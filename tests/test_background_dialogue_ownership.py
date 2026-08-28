"""The Director mints presences; the background stage speaks for them.

MEASURED, 2026-08-08, across the whole corpus. Background lines authored in
`director_resolve` run a median of **8 words** against the sheeted cast's
**16**, and **27%** of them are four words or fewer against the cast's 13% —
"Dragon Kingdom...", "Kadomon.", "Sorry—sorry—". The author's own diagnosis:
"clunky dialogue from an overworked llm".

And the machinery built to fix that was barely running. Of 2,240 background
lines in the corpus, **2,042 came from the Director** and 200 from
`background_react` — because `pick_background_reactors` is a BACKSTOP that
stands down for anyone already in `dialogue_log`. Both of its paths fired on
**6%** of beats even at `scene_life: full`.

So one model was adjudicating physics, dialogue order, state diffs and time in
a single pass AND writing every extra's dialogue as filler, with no perception
object for the speaker. That is one cause with two symptoms: the flatness here,
and the Kadoman leak `_check_presence_knowledge_channel` was built to catch.

The split: the Director keeps every authority over what EXISTS. It gives up
authoring WORDS for anything person-shaped.
"""

from __future__ import annotations

import pytest

from agents.common import director_may_voice


class TestWhoTheDirectorMayVoice:
    def test_a_beast_keeps_the_directors_voice(self):
        """A snarl gains nothing from a dedicated call with its own memory."""
        sc = {"entities": {"wolf": {"kind": "beast"}}}
        assert director_may_voice("wolf", sc)

    @pytest.mark.parametrize("kind", ["person", "human", "humanoid", "alien",
                                      "npc", "character"])
    def test_anything_person_shaped_is_routed(self, kind):
        """The measured defect: `a8becaa367e148be` (kind `person`) saying
        "Kadomon." as line 14 of a 4,000-token adjudication."""
        sc = {"entities": {"someone": {"kind": kind}}}
        assert not director_may_voice("someone", sc)

    def test_an_unknown_kind_routes_rather_than_keeps(self):
        """Conservative in the direction that costs a model call rather than
        the direction that costs a flat line and a possible leak."""
        assert not director_may_voice("mystery", {"entities": {}})
        assert not director_may_voice("mystery", {"entities": {"mystery": {}}})

    def test_the_kind_can_come_from_the_presence_sketch(self):
        """A presence tracked in `background_presences` but not yet a scene
        entity still has to be classifiable, or every one of them routes."""
        assert director_may_voice(
            "swarm", {"entities": {}}, {"sketch": {"kind": "swarm"}})

    def test_an_empty_speaker_is_never_voiceable(self):
        assert not director_may_voice("", {"entities": {}})
        assert not director_may_voice(None, {"entities": {}})


class TestTheHandOff:
    """Removing the line is only half of it — the presence has to be picked up
    by the stage that replaces it, or this trades clunky dialogue for silence.
    """

    def test_a_routed_presence_is_no_longer_voiced_this_beat(self, temp_db):
        """`pick_background_reactors` skips anyone already in `dialogue_log`.
        The routed name must be subtracted from that set or the hand-off dies
        exactly where it starts."""
        from persist import commit
        import inspect
        # The gate's working body is `pick_voice_demand` since Part C;
        # `pick_background_reactors` is its names-only wrapper.
        body = inspect.getsource(commit.pick_voice_demand)
        assert "routed_to_background" in body
        assert "voiced_this_beat -=" in body, (
            "the routed names must be removed from voiced_this_beat")

    def test_routing_forces_past_the_cap(self, temp_db):
        """A presence the Director chose to speak for is salient by
        construction, so it must force like a flow address rather than compete
        for a slot -- otherwise `max_reactors: 1` silently drops it."""
        import inspect
        from persist import commit
        body = inspect.getsource(commit.pick_voice_demand)
        # Routing forces through the PRECISE address class (§C3): the
        # Director choosing to speak for someone is an address by the
        # Director itself.
        assert "flow_addressed or routed" in body
        assert "if addressed_precise:" in body

    def test_the_field_survives_the_schema_dump(self, temp_db):
        """Unknown keys are dropped by the model dump. Undeclared, the hand-off
        would vanish between the two stages and a re-homed line would simply be
        a deleted one."""
        from llm.schemas import DirectorResolve
        dumped = DirectorResolve(**{"routed_to_background": ["patron2"]}).dict()
        assert dumped["routed_to_background"] == ["patron2"]


def test_the_prompt_names_the_occasion_rather_than_only_forbidding(temp_db):
    """CLAUDE.md: "Bare prohibitions invert. A prompt clause that only forbids
    gets read as a suggestion of the thing it forbids. Name concrete occasions
    instead." So the clause has to say what the Director DOES voice."""
    from llm.prompts import DEFAULT_PROMPTS
    text = DEFAULT_PROMPTS["director_resolve_lean"]
    assert "SIMPLE CREATURES" in text
    assert "write the action and omit the line" in text
    # And it says where the words come from instead, so the omission reads as
    # a hand-off rather than as the extra being silenced.
    assert "own senses and memory" in text


class TestWhatABackgroundPresenceKnowsAboutTheWorld:
    """Neither background path carried a single word of lore.

    That was survivable while the Director wrote most background dialogue from
    the omniscient working state. It stopped being survivable the moment
    dialogue moved here: an innkeeper in Lugunica who cannot be expected to
    know what Lugunica trades in is a different kind of stupid, not a fix.

    This is the firewall APPLIED, not bypassed. The channel rule bars facts
    that reached a mind through no channel; it has never barred what everyone
    in the setting knows, and `_check_presence_knowledge_channel` gates
    single-word matches on the definite article precisely so "trade runs on
    copper and silver" survives while "the strange coins" does not.
    """

    def test_the_place_block_carries_room_scoped_world_knowledge(self):
        import inspect

        from agents import background
        src = inspect.getsource(background._place_block)
        assert "world_knowledge" in src
        assert "_room_notes_from_lore" in src, (
            "must reuse perception's helper, which carries the blocked-slug "
            "scoping for a sealed or nested observer")

    def test_the_per_presence_path_gets_a_place_block_at_all(self):
        """It had none: no room, no time, no setting, no lore — only its own
        role_hint and the beat."""
        import inspect

        from agents import background
        src = inspect.getsource(background._react_one)
        assert '"place": _place_block(' in src

    def test_lore_is_room_scoped_not_the_whole_book(self):
        """A lorebook holds secrets, and a background extra is the last mind
        that should be handed one. Room scope is the boundary."""
        import inspect

        from agents import background
        src = inspect.getsource(background._place_block)
        assert "room_id" in src.split("world_knowledge")[1][:200], (
            "world_knowledge must be resolved from the room, not globally")
