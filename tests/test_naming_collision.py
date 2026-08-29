"""A minted person may not arrive under a registered mind's address.

`_refuse_name_collision` has always stated the rule -- "Names are how this
engine tells minds apart" -- and was wired to the PROMOTION path alone. The
engine mints people on a second path: `world/charter_identity`'s body
allocator, which names a whole institution's population at once from a law
the planner derived from the same lore that supplied the cast. Measured
2026-08-27 over the live corpus (chats 83/84/93/94/95, the five populated
charters): chat 95's 42 generated bodies drew from a family pool holding the
registered crew's own surnames under a formal format of ``{rank} {family}``,
and two landed on them -- one story holding a captain and an ensign whom
everyone addresses by the same word. Chat 83 held the same contamination
latent (its pool carried the single cast member's family element under
``Dr. {family}``).

The rule these tests pin, in engine vocabulary:

- A name ELEMENT is identity only where the story's own law lets it stand for
  the whole person. Under ``{given} {family}`` the pair is the address and two
  people may share a family the way two people do; under ``{rank} {family}``
  the family alone is what everybody is called.
- Both minting paths -- the Charter body allocator and the background-presence
  mint -- ask ONE question, from the two wells `_refuse_name_collision`
  trusts.
- The subtraction happens twice and both times downward: the law PERSISTED on
  a charter stops offering the reserved element to any later reader, and the
  mint refuses a candidate that reaches one anyway.
- Nothing is taken from a body that arrived already named. A featured
  resident is placed into a charter under the registered character's own name
  on purpose.
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import (
    _refuse_name_collision,
    presence_display_name,
    track_background_presences,
)
from story.character_schema import default_character_data
from story.naming import (
    minted_presence_name,
    registered_identity_names,
    story_identity_reservation,
)
from world.charter_generate import close_plan
from world.charter_identity import (
    address_components,
    identity_reservation,
    materialize_body_names,
    normalize_naming_profile,
    strip_reserved_pools,
)
from world.charter_runtime import registry_for, save_registry

# A law whose formal address is one element: everybody is called by the
# family name alone, so two people sharing one share an address.
ELEMENT_LAW = {
    "given": ["Wren", "Talis", "Oren", "Bue", "Kavi", "Serin"],
    "family": ["Halloway", "Ardent", "Cassel", "Dowd"],
    "name_format": "{given} {family}",
    "formal_format": "{rank} {family}",
    "titles": {"ranks": {"senior": "Senior Warden",
                         "junior": "Junior Warden"}},
}

# The same pools under a law that addresses people by the whole pair.
PAIRED_LAW = dict(ELEMENT_LAW, formal_format="{title} {name}")

REGISTERED = "Talis Halloway"
RESERVED_ELEMENT = "Halloway"

# Raw entity ids standing where a name belongs -- the shape the ledger was
# measured holding. Enough of them that a pool of four family elements is
# drawn from more than once.
ID_SHAPED = ["%016x" % (0x7b2e4c9a1d6f3085 + step * 0x1111) for step in range(12)]


def _families(bodies):
    return {str(body.get("family_name") or "").casefold()
            for body in bodies.values()}


def _blank_bodies(count):
    return {"post:%04d" % i: {"place": "hall"} for i in range(count)}


def _chat(db, *, cast=(), persona=None):
    persona_id = None
    if persona is not None:
        persona_id = db.qi(
            "INSERT INTO personas(name,sheet) VALUES(?,?)",
            (persona, json.dumps({"name": persona})))
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Test", "", time.time(), persona_id))
    for index, name in enumerate(cast):
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), "char_%d_%d" % (chat_id, index)))
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    return chat_id


def _plan(law):
    """One institution with enough posts to exhaust a small pool."""
    return {
        "name": "Waypoint",
        "structure": {"key": "waypoint", "max_planned": 8, "grammar": []},
        "rooms": {"hall": {"name": "Hall", "purpose": "work",
                           "adjacent": []}},
        "charters": [{
            "key": "works",
            "naming": law,
            "priority": ["upkeep"],
            "upkeeps": {"upkeep": {
                "place": "hall", "floor": 0.25, "level": 1,
                "fails_untended": "a_week",
                "one_body_restores_in": "a_shift"}},
            "posts": {"warden": {"place": "hall", "serves": ["upkeep"],
                                 "requires": {"tending": 1}}},
            "populations": [{"post": "warden", "count": 9,
                             "competence": {"tending": 1}, "berth": "hall"}],
        }],
    }


# ---------------------------------------------------------------------------
# what makes an element identity
# ---------------------------------------------------------------------------

class TestALawSaysWhichElementIsAnAddress:
    def test_a_paired_format_exposes_neither_half(self):
        """Two people may share a family where the law never calls anyone by
        it alone -- the engine refusing that would be the engine deciding a
        setting cannot have families."""
        assert address_components(PAIRED_LAW) == frozenset()

    def test_a_format_that_calls_people_by_one_element_exposes_it(self):
        assert address_components(ELEMENT_LAW) == frozenset({"family"})
        assert address_components(
            dict(ELEMENT_LAW, formal_format="Elder {given}")
        ) == frozenset({"given"})

    def test_a_format_carrying_the_whole_name_exposes_nothing(self):
        assert address_components(
            dict(ELEMENT_LAW, formal_format="{title} {name}")
        ) == frozenset()

    def test_a_title_does_not_hide_the_identity_underneath_it(self):
        """A registered name written with its rank is still that person's
        address. The title vocabulary comes from the law itself, so no list
        of honorifics has to be maintained anywhere."""
        reservation = identity_reservation(
            ["Senior Warden Talis Halloway"], ELEMENT_LAW)
        pool = strip_reserved_pools(
            normalize_naming_profile(ELEMENT_LAW), reservation)
        assert RESERVED_ELEMENT not in pool["family"]

    def test_a_multi_word_element_is_recognised_whole(self):
        law = dict(ELEMENT_LAW, family=["Van Ryn", "Ardent"])
        reservation = identity_reservation(["Oren Van Ryn"], law)
        pool = strip_reserved_pools(normalize_naming_profile(law), reservation)
        assert pool["family"] == ["Ardent"]

    def test_an_element_buried_mid_name_is_not_an_address(self):
        """Only the head and the tail of a name are what someone is called;
        a word in the middle is not, and subtracting it would shrink a pool
        for no gain."""
        reservation = identity_reservation(
            ["Oren Cassel Ardent"], dict(ELEMENT_LAW, family=["Cassel"]))
        pool = strip_reserved_pools(
            normalize_naming_profile(dict(ELEMENT_LAW, family=["Cassel"])),
            reservation)
        assert pool["family"] == ["Cassel"]


# ---------------------------------------------------------------------------
# the Charter body allocator
# ---------------------------------------------------------------------------

class TestTheCharterMintRefusesARegisteredAddress:
    def test_unreserved_the_mint_takes_the_address(self):
        """The defect, stated as a measurement: with nothing reserved the
        allocator hands a registered mind's address to a generated body."""
        bodies = materialize_body_names(
            "works", _blank_bodies(9), ELEMENT_LAW)
        assert RESERVED_ELEMENT.casefold() in _families(bodies)

    def test_reserved_the_mint_refuses_it(self):
        reservation = identity_reservation([REGISTERED], ELEMENT_LAW)
        bodies = materialize_body_names(
            "works", _blank_bodies(9), ELEMENT_LAW, reservation)
        assert RESERVED_ELEMENT.casefold() not in _families(bodies)
        assert all(str(body.get("name") or "").strip()
                   for body in bodies.values())

    def test_a_paired_law_keeps_the_element_and_refuses_the_whole_name(self):
        """The subtraction is exactly as wide as the law's address: under a
        paired format the family stays available and only the registered
        name itself is out of reach."""
        reservation = identity_reservation([REGISTERED], PAIRED_LAW)
        bodies = materialize_body_names(
            "works", _blank_bodies(9), PAIRED_LAW, reservation)
        assert RESERVED_ELEMENT.casefold() in _families(bodies)
        assert REGISTERED.casefold() not in {
            str(body.get("name") or "").casefold() for body in bodies.values()}

    def test_a_body_that_arrives_named_keeps_its_name(self):
        """A featured resident is placed under the registered character's own
        name deliberately. The refusal governs what the allocator MINTS, and
        an allocator that renamed an authored body would be a different and
        worse defect."""
        raw = _blank_bodies(4)
        raw["post:0000"]["name"] = REGISTERED
        reservation = identity_reservation([REGISTERED], ELEMENT_LAW)
        bodies = materialize_body_names("works", raw, ELEMENT_LAW, reservation)
        assert bodies["post:0000"]["name"] == REGISTERED

    def test_the_refusal_leaves_the_mint_deterministic(self):
        reservation = identity_reservation([REGISTERED], ELEMENT_LAW)
        first = materialize_body_names(
            "works", _blank_bodies(9), ELEMENT_LAW, reservation)
        second = materialize_body_names(
            "works", _blank_bodies(9), ELEMENT_LAW, reservation)
        assert {k: v["name"] for k, v in first.items()} \
            == {k: v["name"] for k, v in second.items()}

    def test_no_registered_name_reserves_nothing(self):
        """A story with no registered cast loses no vocabulary."""
        reservation = identity_reservation([], ELEMENT_LAW)
        assert strip_reserved_pools(
            normalize_naming_profile(ELEMENT_LAW), reservation
        )["family"] == normalize_naming_profile(ELEMENT_LAW)["family"]


# ---------------------------------------------------------------------------
# the law that is persisted
# ---------------------------------------------------------------------------

class TestThePersistedLawStopsOfferingTheAddress:
    def test_generation_stores_a_scrubbed_law(self):
        """`state.naming` is read again by every later mint -- the registry
        normalizer and `story/naming.py`'s Charter lane both. Storing the
        contaminated pool would leave the defect alive for readers that never
        saw this generation."""
        reservation = identity_reservation([REGISTERED], ELEMENT_LAW)
        town = close_plan(_plan(ELEMENT_LAW), reservation=reservation)
        charter = town["charters"]["works"]
        assert RESERVED_ELEMENT not in charter["naming"]["family"]
        assert RESERVED_ELEMENT.casefold() not in _families(charter["bodies"])

    def test_generation_without_a_reservation_still_stores_its_law(self):
        town = close_plan(_plan(ELEMENT_LAW))
        assert RESERVED_ELEMENT in town["charters"]["works"]["naming"]["family"]

    def test_a_paired_law_subtracts_the_element_too(self, temp_db):
        """REVERSED 2026-08-28, deliberately, and this docstring is the record.

        It used to read: "Under a paired format nothing is subtracted from the
        pools -- the law calls nobody by one element -- so the mint's own
        refusal is the only thing standing between the allocator and a second
        person under a registered mind's whole name." That was the measured
        defect, not a design: `strip_reserved_pools` gated itself on
        `address_components`, which is EMPTY under `{given} {family}`, so the
        subtraction was a no-op for the commonest law shape in the engine and
        fired only where a law also carried a title format.

        The two questions are different. Two people sharing a family name is
        ordinary, because sharing ARISES. A pool that contains a named
        individual's family name is the engine ISSUING that individual's name
        to strangers. Measured on a generated Star Trek institution: the
        harvest built {given} x {family} pools from a lorebook's canon cast
        and the free cross-product handed twenty strangers names like
        "Jean-Luc Crusher" and "Ro Vulcan", and reconstituted one canon
        character's full name verbatim. In an original setting the same thing
        happens and nobody can see it.
        """
        chat_id = _chat(temp_db, cast=[REGISTERED])
        save_registry(chat_id, {"works": {
            "key": "works", "naming": PAIRED_LAW,
            "posts": {"warden": {"place": "hall"}},
            "bodies": {"post:%04d" % i: {"place": "hall"} for i in range(6)},
        }})
        state = registry_for(chat_id)["items"]["works"]["state"]

        assert RESERVED_ELEMENT not in state["naming"]["family"]
        assert RESERVED_ELEMENT.casefold() not in _families(state["bodies"])
        assert REGISTERED.casefold() not in {
            str(body.get("name") or "").casefold()
            for body in state["bodies"].values()}

    def test_saving_a_registry_scrubs_the_law_it_stores(self, temp_db):
        """The registry's one write chokepoint, so a hand-authored charter or
        an older generation's stored law is answered too."""
        chat_id = _chat(temp_db, cast=[REGISTERED])
        save_registry(chat_id, {"works": {
            "key": "works", "naming": ELEMENT_LAW,
            "posts": {"warden": {"place": "hall"}},
            "bodies": {"post:%04d" % i: {"place": "hall"} for i in range(9)},
        }})
        state = registry_for(chat_id)["items"]["works"]["state"]
        assert RESERVED_ELEMENT not in state["naming"]["family"]
        assert RESERVED_ELEMENT.casefold() not in _families(state["bodies"])


class TestGenerationAsksTheStoryBeforeItMints:
    """The generation entry point is where the story is in reach. The pure
    closure below it cannot look a cast up, so a reservation it is never
    handed is a guard that exists and never runs."""

    def _generated(self, temp_db, monkeypatch, chat_id, law):
        from world import charter_generate, charter_runtime

        monkeypatch.setattr(charter_generate, "propose_town",
                            lambda lore, brief, constraints=None: _plan(law))
        chat = temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
        artifact = charter_runtime._plan_lived_location(
            chat_id,
            {"lore": [], "generate_history": False, "horizon_hours": 0.0},
            chat)
        return artifact["town"]["charters"]["works"]

    def test_the_generated_law_and_bodies_avoid_the_registered_address(
            self, temp_db, monkeypatch):
        chat_id = _chat(temp_db, cast=[REGISTERED])
        charter = self._generated(temp_db, monkeypatch, chat_id, ELEMENT_LAW)
        assert RESERVED_ELEMENT not in charter["naming"]["family"]
        assert RESERVED_ELEMENT.casefold() not in _families(charter["bodies"])

    def test_a_story_with_no_cast_keeps_the_whole_pool(
            self, temp_db, monkeypatch):
        chat_id = _chat(temp_db)
        charter = self._generated(temp_db, monkeypatch, chat_id, ELEMENT_LAW)
        assert RESERVED_ELEMENT in charter["naming"]["family"]

    def test_an_authored_law_reaches_the_generated_bodies(
            self, temp_db, monkeypatch):
        chat_id = _chat(temp_db, cast=[REGISTERED])
        temp_db.wset(chat_id, "naming_profile",
                     {"given": ["Isa", "Ruel"], "family": ["Quinn"]})
        charter = self._generated(temp_db, monkeypatch, chat_id, ELEMENT_LAW)
        assert charter["naming"]["family"] == ["Quinn"]
        assert _families(charter["bodies"]) == {"quinn"}


# ---------------------------------------------------------------------------
# one authority, one no-fly list
# ---------------------------------------------------------------------------

class TestOneNamingAuthority:
    def test_an_authored_law_outranks_the_charters_own_at_the_mint(self):
        """`story/naming.py` ranks an authored story-level law above a
        Charter's derived one. A body allocator drawing from the derived law
        regardless would be a second naming authority beside the story's."""
        authored = {"given": ["Isa", "Ruel"], "family": ["Quinn"]}
        town = close_plan(_plan(ELEMENT_LAW), naming_law=authored)
        charter = town["charters"]["works"]
        assert charter["naming"]["family"] == ["Quinn"]
        assert _families(charter["bodies"]) == {"quinn"}

    def test_both_paths_read_the_wells_the_promotion_guard_trusts(
            self, temp_db):
        """Every name the Charter mint reserves is a name promotion already
        refuses. One question, asked in two places."""
        chat_id = _chat(temp_db, cast=[REGISTERED, "Bue Dowd"],
                        persona="Serin Ardent")
        names = registered_identity_names(chat_id)
        assert set(names) == {REGISTERED, "Bue Dowd", "Serin Ardent"}
        for name in names:
            with pytest.raises(ValueError):
                _refuse_name_collision(chat_id, name)

    def test_the_reservation_carries_names_no_table_holds(self, temp_db):
        chat_id = _chat(temp_db, cast=[REGISTERED])
        reservation = story_identity_reservation(
            chat_id, ELEMENT_LAW, extra=["Kavi Cassel"])
        pool = strip_reserved_pools(
            normalize_naming_profile(ELEMENT_LAW), reservation)
        assert "Cassel" not in pool["family"]
        assert RESERVED_ELEMENT not in pool["family"]


# ---------------------------------------------------------------------------
# the presence mint, which is the second minting path
# ---------------------------------------------------------------------------

class TestThePresenceMintRefusesTheSameAddress:
    def test_a_stored_law_carrying_the_address_never_mints_it(self, temp_db):
        """A law persisted before this rule existed still holds the element.
        The mint's own refusal is what covers it, so an old story is fixed
        without a migration."""
        chat_id = _chat(temp_db, cast=[REGISTERED])
        temp_db.wset(chat_id, "charters", {"items": {"works": {
            "state": {"key": "works", "naming": ELEMENT_LAW}}}})
        drawn = {minted_presence_name(chat_id, "p_%016x" % i)
                 for i in range(24)}
        assert drawn
        assert all(name for name in drawn)
        assert not any(name.casefold().endswith(RESERVED_ELEMENT.casefold())
                       for name in drawn)

    def test_an_unnamed_speaker_is_named_off_the_reserved_element(
            self, temp_db):
        chat_id = _chat(temp_db, cast=[REGISTERED])
        temp_db.wset(chat_id, "charters", {"items": {"works": {
            "state": {"key": "works", "naming": ELEMENT_LAW}}}})
        temp_db.wset(chat_id, "scene", {
            "location": "x", "rooms": {"hall": {"name": "Hall",
                                                "adjacent": []}},
            "positions": {}, "entities": {}, "attire": {}, "overlays": {}})
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 1, "", time.time()))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Test", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                          player_input="", created=time.time()),
            cast=[], input="",
            director_resolve={
                "resolved_event": "Several people speak.",
                "dialogue_log": [{"speaker": speaker, "line": "A line."}
                                 for speaker in ID_SHAPED],
                "state_diff": {}})
        track_background_presences(ctx, nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        names = [presence_display_name(key, record)
                 for key, record in presences.items()]
        assert len(names) == len(ID_SHAPED)
        assert all(name not in ID_SHAPED for name in names)
        assert not any(
            name.casefold().endswith(RESERVED_ELEMENT.casefold())
            for name in names)
