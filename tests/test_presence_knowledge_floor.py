"""The Director's mouth on a background presence gets a knowledge floor.

Chat 65 t2148: Kadoman -- an unregistered background presence minted at
turn 9 at the eastern_market labor board -- said "Not from around here, eh?
That explains the strange coins and notes." The coins and notes were shown
once, at turn 4, in fountain_plaza, to a different presence, and pocketed at
turn 5. The line was authored by director_resolve itself (the prompt licenses
the Director to voice unsheeted presences), from the Director's omniscient
working state, with no perception object for the speaker: the yen entities
ride every resolve payload as objective scene state, and nothing sat between
that entitled omniscience and the presence's mouth.

Corpus measurement (59 chats, 2,114 turns): 291 dialogue_log entries are
Director-voiced presence speech -- every unregistered NPC's every line goes
through this channel, with no firewall of any kind before this floor.

The two constraints these tests hold, verbatim from the author: generic world
knowledge must survive untouched (a presence must still say local trade runs
on copper and silver), and a presence with no channel must be able to be
ignorant in front of the player -- that is the demonstration that the
firewall is real, and it is worth more than smooth prose.
"""

from __future__ import annotations

import inspect

from agents.common import _check_presence_knowledge_channel


def lagunica_scene():
    """Chat 65's scene at t2148, reduced: persons placed, belongings not.

    The yen entities are UNPLACED (no position, no containment record) --
    exactly as the live scene stores them -- because they went into the
    satchel and nothing tracks them since. An unplaced entity offers no
    provable channel.
    """
    return {
        "rooms": {
            "fountain_plaza": {"adjacent": [{"to": "commercial_lane",
                                             "barrier": "open"}]},
            "commercial_lane": {"adjacent": [{"to": "eastern_market",
                                              "barrier": "open"}]},
            "eastern_market": {"adjacent": []},
        },
        "entities": {
            "Hinami": {"name": "Hinami", "kind": "person"},
            "Kadoman": {"name": "Kadoman", "kind": "person"},
            "satchel": {"name": "leather satchel", "kind": "object",
                        "aliases": ["satchel"]},
            "yen_notes": {"name": "yen notes", "kind": "object",
                          "aliases": ["paper money", "yen notes",
                                      "foreign notes"]},
            "yen_coins": {"name": "yen coins", "kind": "object",
                          "aliases": ["coins", "yen coins", "foreign coins"]},
            "apple_cart": {"name": "apple cart", "kind": "object"},
        },
        "positions": {"Hinami": "eastern_market", "Kadoman": "eastern_market",
                      "apple_cart": "eastern_market"},
        "contained": {},
    }


KADOMAN_REC = {"first_turn": 9,
               "sketch": {"role_hint": "a labourer scanning the board",
                          "station_room": "eastern_market"}}

THE_LINE = ("Not from around here, eh? That explains the strange coins and "
            "notes. Board here's for day labor - porters, loaders, "
            "stablehands. Pays in copper and silver. Commerce Guild's down "
            "the lane if you need proper leads.")


class TestTheReproduction:
    def test_the_kadoman_line_is_flagged(self):
        """The definite reference to her pocketed money, by a presence that
        was two rooms and five turns away from ever perceiving it. This line
        shipped to the player; on unmodified code nothing anywhere objected."""
        leaks = _check_presence_knowledge_channel(
            "Kadoman", THE_LINE, lagunica_scene(), KADOMAN_REC, heard_text="")
        assert leaks, "the measured leak line raised no warning"
        assert any("coins" in w for w in leaks)

    def test_the_generic_belief_is_not_flagged(self):
        """Garret's turn-0 belief, verbatim. Gagging generic world knowledge
        would make every NPC an amnesiac -- the copper-and-silver rule must
        survive any change to this floor."""
        generic = ("Local trade uses only copper, silver, and gold coins; "
                   "strange paper has no value here.")
        assert _check_presence_knowledge_channel(
            "Kadoman", generic, lagunica_scene(), KADOMAN_REC,
            heard_text="") == []

    def test_the_rest_of_the_kadoman_line_alone_is_clean(self):
        """Day labor, copper and silver, the Commerce Guild: everything else
        Kadoman said was legitimate role knowledge, so the fix must flag the
        sentence's reference, not its speaker."""
        rest = ("Board here's for day labor - porters, loaders, stablehands. "
                "Pays in copper and silver. Commerce Guild's down the lane.")
        assert _check_presence_knowledge_channel(
            "Kadoman", rest, lagunica_scene(), KADOMAN_REC,
            heard_text="") == []


class TestTheChannel:
    def test_a_placed_entity_in_the_open_is_referenceable(self):
        """Co-presence is a channel: the apple cart stands in Kadoman's own
        room, so a definite reference to it is earned."""
        assert _check_presence_knowledge_channel(
            "Kadoman", "Mind the apple cart, miss.", lagunica_scene(),
            KADOMAN_REC, heard_text="") == []

    def test_the_same_entity_concealed_loses_the_channel(self):
        """Being in the room with a shut container is not seeing inside it --
        the same entity flips from referenceable to not when a containment
        record hides it (hiding_holders_of, both containment forms)."""
        sc = lagunica_scene()
        sc["contained"] = {"apple_cart": {"in": "satchel"}}
        leaks = _check_presence_knowledge_channel(
            "Kadoman", "Mind the apple cart, miss.", sc, KADOMAN_REC,
            heard_text="")
        assert leaks and "apple cart" in leaks[0]

    def test_a_multi_word_name_needs_no_determiner_to_flag(self):
        """'yen notes' is a definite description all by itself: a presence in
        another room producing the entity's own name has been handed it by
        nothing in the fiction."""
        vendor_rec = {"first_turn": 2,
                      "sketch": {"role_hint": "a fruit seller",
                                 "station_room": "fountain_plaza"}}
        sc = lagunica_scene()
        sc["positions"]["Vendor"] = "fountain_plaza"
        sc["entities"]["Vendor"] = {"name": "Vendor", "kind": "person"}
        leaks = _check_presence_knowledge_channel(
            "Vendor", "Yen notes indeed. Nothing but paper.", sc, vendor_rec,
            heard_text="")
        assert leaks and "yen notes" in leaks[0].casefold()

    def test_a_thing_said_aloud_this_beat_is_earned(self):
        """Hearing is a channel. If the player names her yen notes to the
        presence's face, the presence may answer about THE yen notes -- the
        floor must never make conversation impossible."""
        assert _check_presence_knowledge_channel(
            "Kadoman", "Those yen notes won't spend here, miss.",
            lagunica_scene(), KADOMAN_REC,
            heard_text="do these yen notes have any value here?") == []

    def test_a_presence_may_speak_of_itself(self):
        """Kadoman is a scene entity too; the floor must not read a presence
        naming itself as a reference it never earned."""
        assert _check_presence_knowledge_channel(
            "Kadoman", "The name's Kadoman.", lagunica_scene(), KADOMAN_REC,
            heard_text="") == []


class TestTheFloorIsWiredIn:
    """A guard that exists but is called on no path is the audit's recurring
    discovery. These pin the floor into the seams it must guard."""

    def test_director_resolve_consults_the_floor_on_dialogue_log(self):
        """The dialogue_log backstop loop must call the channel check for a
        speaker that is neither cast nor a player -- the exact mouth the
        voicing license opens."""
        import agents.director as director

        src = inspect.getsource(director.director_resolve)
        assert "_check_presence_knowledge_channel" in src

    def test_the_resolve_payload_carries_the_presence_envelope(self):
        """The prompt-side half: the model can only respect a presence's
        epistemic envelope if the payload states it. Deterministic floor and
        payload envelope land together or the prompt rule keys off nothing."""
        import agents.director as director

        src = inspect.getsource(director.director_resolve)
        assert "background_presence_knowledge" in src

    def test_the_resolve_prompt_states_the_rule(self):
        """Bare prohibitions invert; the rule must name the concrete occasion
        (the pocketed money, the copper-and-silver generality) and the field
        it keys off."""
        from llm.prompts import DEFAULT_PROMPTS

        text = DEFAULT_PROMPTS["director_resolve_lean"]
        assert "background_presence_knowledge" in text
        assert "copper and silver" in text
