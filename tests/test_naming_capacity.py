"""A population larger than its authored name space stays distinct.

The measured defect (chat 95, a 42-body generated institution): the naming
law's family pool held twelve elements, the allocator drew every body's
family uniformly from it, and the same dozen surnames recurred across the
whole population -- four same-surname clusters, each reading as a household
the fiction never authored. A separate body doubled a single pool word into
both halves of its own name.

The rule these tests pin, in engine vocabulary:

- An authored pool is the LAW'S PHONOLOGY, not the population's size limit.
  When the population outgrows the pool, the extension lane
  (`extension_profile`) widens the space with syllable parts -- the
  author's own, or parts derived from the pool's words
  (`derived_name_parts`) -- so every new value is recombined from material
  the law already used. No pool, no derivation: the no-implicit-default
  doctrine stands.
- A component whose sharing ASSERTS something is spread breadth-first
  (`spread_components`): family names, because recurrence inside one
  generated population implies kinship, and any component the law addresses
  people by alone. Reuse is permitted only once the whole reachable space
  is spent -- spreading is preference where `name_is_reserved` is refusal.
- A name never doubles its own component (`components_repeat`).
- The mint stays a WRITE: a stored name never re-enters the allocator, so a
  bank generated under any earlier law keeps every name it has.
"""

from __future__ import annotations

import json

from world.charter import normalize_charter
from world.charter_identity import (
    components_repeat,
    derived_name_parts,
    extension_profile,
    identity_reservation,
    materialize_body_names,
    spread_components,
)
from story.naming import minted_presence_name

# A paired-address law: the family is spread for kinship alone.
LAW = {
    "given": ["Maret", "Ilsa", "Doven", "Karsa",
              "Petrin", "Sole", "Anno", "Reya"],
    "family": ["Halden", "Corvel", "Marsen", "Ostry", "Vintar", "Belamy"],
    "name_format": "{given} {family}",
    "formal_format": "{title} {name}",
}

# The same pools under a law that calls people by the family alone.
ADDRESS_LAW = dict(LAW, formal_format="{rank} {family}")


def _blank_bodies(count):
    return {"post:%04d" % i: {"place": "hall"} for i in range(count)}


def _families(bodies):
    return [str(body.get("family_name") or "") for body in bodies.values()]


def _derived_space(pool):
    parts = derived_name_parts(pool)
    return {(start + end).casefold()
            for start in parts["starts"] for end in parts["ends"]}


# ---------------------------------------------------------------------------
# the extension lane: pool first, derivation after, law obeyed throughout
# ---------------------------------------------------------------------------

class TestAPoolIsAPhonologyNotASizeLimit:
    def test_a_population_beyond_the_pool_shares_no_family(self):
        bodies = materialize_body_names("works", _blank_bodies(24), LAW)
        families = _families(bodies)
        assert len({f.casefold() for f in families}) == 24

    def test_every_authored_family_is_used_before_any_derived_one(self):
        bodies = materialize_body_names("works", _blank_bodies(24), LAW)
        families = {f.casefold() for f in _families(bodies)}
        assert {f.casefold() for f in LAW["family"]} <= families

    def test_a_derived_family_is_built_from_the_pools_own_words(self):
        bodies = materialize_body_names("works", _blank_bodies(24), LAW)
        allowed = ({f.casefold() for f in LAW["family"]}
                   | _derived_space(LAW["family"]))
        assert {f.casefold() for f in _families(bodies)} <= allowed

    def test_authored_parts_outrank_derivation(self):
        """An author who wrote the extension gets exactly the extension
        they wrote; derivation serves only a law with no parts of its
        own."""
        law = dict(LAW, family=["Halden", "Corvel"],
                   family_parts={"starts": ["Zu", "Ka"],
                                 "ends": ["reth", "dim"]})
        bodies = materialize_body_names("works", _blank_bodies(6), law)
        families = {f.casefold() for f in _families(bodies)}
        assert families == {"halden", "corvel", "zureth", "zudim",
                           "kareth", "kadim"}

    def test_exhausting_the_whole_space_permits_reuse_not_failure(self):
        """Spreading is preference, not refusal: past the last reachable
        value every body is still named, and full names stay distinct."""
        law = dict(LAW, family=["Halden"])
        bodies = materialize_body_names("works", _blank_bodies(6), law)
        names = [body["name"] for body in bodies.values()]
        assert all(names)
        assert len(set(names)) == 6

    def test_no_law_derives_nothing_and_the_key_fallback_stands(self):
        bodies = materialize_body_names("works", _blank_bodies(3), {})
        assert all(body["name"] == key for key, body in bodies.items())
        assert extension_profile({}) is None

    def test_a_pool_that_does_not_split_does_not_extend(self):
        """Material whose vowel structure the splitter cannot read derives
        nothing -- the engine follows a law's phonology or stays out."""
        assert derived_name_parts(["Xrth", "Grzk"]) == {
            "starts": [], "middles": [], "ends": []}

    def test_a_single_chunk_word_contributes_no_parts(self):
        """Gluing whole short names together is a collision wearing a
        hyphen's clothes, not a derivation."""
        parts = derived_name_parts(["Halden", "Corvel", "Vosk"])
        assert "vosk" not in {s.casefold() for s in parts["starts"]}
        assert "vosk" not in {e.casefold() for e in parts["ends"]}


# ---------------------------------------------------------------------------
# collisions separated where the component is an address
# ---------------------------------------------------------------------------

class TestSharedComponentsAreSpreadNotRepeated:
    def test_two_bodies_that_would_collide_are_separated(self):
        """Under a single-component law the component IS the address, so
        every generated body must answer to a different word."""
        law = {"given": ["Sorel", "Vanik", "Timo"], "name_format": "{given}"}
        assert "given" in spread_components(law)
        bodies = materialize_body_names("works", _blank_bodies(7), law)
        names = [body["name"] for body in bodies.values()]
        assert len({n.casefold() for n in names}) == 7

    def test_a_name_never_doubles_its_own_component(self):
        """One word sitting in both pools must not become both halves of
        one person."""
        law = {"given": ["Doran", "Mesa", "Kell"],
               "family": ["Doran", "Mesa", "Kell"],
               "name_format": "{given} {family}"}
        bodies = materialize_body_names("works", _blank_bodies(12), law)
        for body in bodies.values():
            assert not components_repeat(
                body.get("given_name"), body.get("family_name")), body

    def test_a_registered_identity_is_refused_even_on_the_extension_lane(
            self):
        """A derived recombination that lands on a registered mind's
        address is refused exactly as a pool value is: the reservation
        binds the whole space, not the authored subset."""
        derived = _derived_space(ADDRESS_LAW["family"])
        target = "Colden"
        assert target.casefold() in derived  # the lane CAN produce it
        reservation = identity_reservation(
            ["Maret " + target], ADDRESS_LAW)
        bodies = materialize_body_names(
            "works", _blank_bodies(30), ADDRESS_LAW, reservation)
        assert target.casefold() not in {
            f.casefold() for f in _families(bodies)}
        assert ("maret " + target.casefold()) not in {
            str(body["name"]).casefold() for body in bodies.values()}


# ---------------------------------------------------------------------------
# permanence: minted once, read thereafter, unchanged by any round trip
# ---------------------------------------------------------------------------

class TestTheMintIsAWrite:
    def test_a_name_minted_on_the_extension_lane_is_read_thereafter(self):
        state = normalize_charter({
            "key": "works", "naming": LAW, "bodies": _blank_bodies(24)})
        first = {k: v["name"] for k, v in state["bodies"].items()}
        again = normalize_charter(state)
        assert {k: v["name"] for k, v in again["bodies"].items()} == first

    def test_the_bank_survives_a_json_round_trip_unchanged(self):
        bodies = materialize_body_names("works", _blank_bodies(24), LAW)
        thawed = json.loads(json.dumps(bodies))
        again = materialize_body_names("works", thawed, LAW)
        assert again == bodies

    def test_allocation_is_deterministic(self):
        first = materialize_body_names("works", _blank_bodies(24), LAW)
        second = materialize_body_names("works", _blank_bodies(24), LAW)
        assert first == second

    def test_an_old_banks_names_stand_and_new_bodies_avoid_its_families(
            self):
        """Migration: a bank named under the pool-only allocator keeps
        every stored name byte-for-byte, and its concentrated surnames are
        counted as spent -- a body added later spreads AWAY from them
        instead of piling on."""
        law = {"given": ["Aldo", "Bila", "Corin", "Dree", "Enna"],
               "family": ["Feren", "Dulan", "Marek"],
               "name_format": "{given} {family}"}
        bank = {
            "w:0001": {"name": "Aldo Feren",
                       "given_name": "Aldo", "family_name": "Feren"},
            "w:0002": {"name": "Bila Feren",
                       "given_name": "Bila", "family_name": "Feren"},
            "w:0003": {"name": "Corin Dulan",
                       "given_name": "Corin", "family_name": "Dulan"},
            "w:0004": {"name": "Dree Dulan",
                       "given_name": "Dree", "family_name": "Dulan"},
            "w:0005": {}, "w:0006": {}, "w:0007": {},
        }
        out = materialize_body_names("works", bank, law)
        for key in ("w:0001", "w:0002", "w:0003", "w:0004"):
            assert out[key]["name"] == bank[key]["name"]
        fresh = [out[k]["family_name"].casefold()
                 for k in ("w:0005", "w:0006", "w:0007")]
        assert "feren" not in fresh and "dulan" not in fresh
        assert len(set(fresh)) == 3


# ---------------------------------------------------------------------------
# the presence mint shares the extension
# ---------------------------------------------------------------------------

class TestThePresenceMintExtendsTheSameWay:
    def test_a_spent_pool_extends_before_conceding(self):
        law = {"given": ["Maret", "Ilsa"], "family": ["Halden", "Corvel"],
               "name_format": "{given} {family}"}
        taken = {"%s %s" % (g, f) for g in law["given"]
                 for f in law["family"]}
        name = minted_presence_name(
            0, "uid-1", used=taken, lanes=[law],
            reservation=identity_reservation([], law))
        assert name
        assert name.casefold() not in {t.casefold() for t in taken}
        given, family = name.split(" ", 1)
        assert given in law["given"]
        assert family.casefold() in _derived_space(law["family"])

    def test_a_law_that_cannot_extend_still_concedes_honestly(self):
        law = {"given": ["Maret"], "family": ["Halden"],
               "name_format": "{given} {family}"}
        name = minted_presence_name(
            0, "uid-1", used={"Maret Halden"}, lanes=[law],
            reservation=identity_reservation([], law))
        assert name == ""
