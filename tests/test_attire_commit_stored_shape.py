"""Commit owns the STORED attire shape, and it must not drift.

Every reader of the attire ledger heals it through `attire.rederive_entry` on
the way out, so a corrupted stored entry looks fine from inside the pipeline
-- and wrong everywhere that reads it raw: the attire panel, exports,
checkpoints, archives. Two commit-seam defects produced exactly that split in
chat 76 (turns 57/59/60):

  1. the derived-state prune used a substring test weaker than
     `attire.is_derived_state_note`, so a stale "bare at the ..." note
     survived whenever a garment re-covered a region, and the stored ledger
     accumulated three mutually contradictory notes at once;
  2. the body specialist emitted `remove` ops for garments the body was not
     wearing (one re-removed from the previous beat, one bled in from a
     parent branch's ledger), and commit dropped them SILENTLY, so nothing
     ever told the Director its picture of the wardrobe was wrong.

`tests/test_attire_regions.py::TestDerivedStateDoesNotAccumulate` pins the
read-path rule (chat 52's instance); this file pins the write path.
"""

from __future__ import annotations

from types import SimpleNamespace

from persist import commit


class _Ctx:
    """The slice of PipelineContext `apply_attire_diff` actually reads."""

    def __init__(self, player_input="wait"):
        self.turn = SimpleNamespace(player_input=player_input)
        self.cast = []
        self.told, self.warned = [], []

    def tell_director(self, msg):
        self.told.append(msg)

    def add_warning(self, msg):
        self.warned.append(msg)


def _entry(wearing, state, regions):
    return {"wearing": list(wearing), "state": list(state),
            "regions": regions}


class TestStaleDerivedNotesArePrunedAtCommit:
    """Chat 76's stored ledger held three "bare at the" notes at once:

        "bare at the head, arms"
        "bare at the head, torso, arms, waist, groin, legs"
        "bare at the head, arms, waist, groin, legs"

    The old prune dropped a stale note only when it was a SUBSTRING of the
    new one -- true only while the bare set grows by appending regions in
    order. The moment a garment re-covers a region (torso here), containment
    fails and the stale note is kept as though a human wrote it.
    """

    CHAT_76_NOTES = [
        "bare at the head, arms",
        "bare at the head, torso, arms, waist, groin, legs",
        "bare at the head, arms, waist, groin, legs",
    ]

    def _scene(self):
        # Torso re-covered by the nightgown; head and arms still bare (their
        # garments came off on earlier beats and keep their removed seats
        # until commit's own release pass).
        return {"attire": {"Hinami": _entry(
            ["thin pale nightgown"],
            self.CHAT_76_NOTES + ["her hair is still damp"],
            {"head": {"garments": [
                {"name": "sun hat", "state": "removed"}]},
             "arms": {"garments": [
                 {"name": "lightweight travel jacket", "state": "removed"}]},
             "torso": {"garments": [
                 {"name": "thin pale nightgown", "state": "worn"}]}},
        )}}

    def test_only_the_current_note_survives(self):
        sc = self._scene()
        ctx = _Ctx()
        commit.apply_attire_diff(sc, {"attire": {"Hinami": {}}}, ctx, {})

        state = sc["attire"]["Hinami"]["state"]
        bare = [n for n in state if n.startswith("bare at the")]
        assert bare == ["bare at the head, arms"], state
        # The two stale notes -- neither a substring of the current one, so
        # the old containment test kept both -- are gone.
        assert self.CHAT_76_NOTES[1] not in state
        assert self.CHAT_76_NOTES[2] not in state

    def test_authored_prose_is_kept(self):
        """The whole point of `state` staying a list."""
        sc = self._scene()
        commit.apply_attire_diff(sc, {"attire": {"Hinami": {}}}, _Ctx(), {})
        assert "her hair is still damp" in sc["attire"]["Hinami"]["state"]

    def test_a_body_dressed_again_sheds_its_last_bare_note(self):
        """The prune must run even when NOTHING is currently derived: a fully
        re-dressed body derives no notes, and that is exactly the beat the
        last stale one must leave on. The old code gated the whole rebuild on
        `_notes` being non-empty."""
        sc = {"attire": {"Hinami": _entry(
            ["thin pale nightgown"],
            ["bare at the groin", "her hair is still damp"],
            {"torso": {"garments": [
                {"name": "thin pale nightgown", "state": "worn"}]}},
        )}}
        commit.apply_attire_diff(sc, {"attire": {"Hinami": {}}}, _Ctx(), {})
        assert sc["attire"]["Hinami"]["state"] == ["her hair is still damp"]


class TestANoOpRemovalIsSurfaced:
    """Chat 76 turn 57: `remove` named the sash shed the beat before AND a
    "nightwear garment" this branch never added. Neither could apply -- the
    resolver refuses a handle nothing worn answers to -- but the silence let
    the specialist keep emitting them beat after beat."""

    def _scene(self):
        return {"attire": {"Hinami": _entry(
            ["fitted tank top"], [],
            {"torso": {"garments": [
                {"name": "fitted tank top", "state": "worn"}]}},
        )}}

    def test_a_garment_never_worn_is_dropped_and_reported(self):
        sc = self._scene()
        ctx = _Ctx()
        commit.apply_attire_diff(
            sc, {"attire": {"Hinami": {"remove": ["nightwear garment"]}}},
            ctx, {})

        assert sc["attire"]["Hinami"]["wearing"] == ["fitted tank top"]
        assert any("nightwear garment" in m for m in ctx.told)
        assert any("no-op removal" in m for m in ctx.warned)
        # Nothing came off, so nothing is minted onto the floor.
        assert not sc.get("entities")

    def test_a_re_removal_of_an_already_shed_garment_is_reported(self):
        """Turn 57 re-removed the utility sash turn 56 had already taken off;
        by then it was an object in the room, not a fact about the body."""
        sc = {"attire": {"Hinami": _entry([], [], {})}}
        ctx = _Ctx()
        commit.apply_attire_diff(
            sc,
            {"attire": {"Hinami": {"remove": ["utility sash with pouches"]}}},
            ctx, {})
        assert any("utility sash with pouches" in m for m in ctx.warned)
        assert not sc.get("entities")

    def test_a_legitimate_alias_removal_still_lands_silently(self):
        """`resolve_garment`'s tiers are the gate: "tank top" IS the fitted
        tank top, so the removal applies and no no-op is reported."""
        sc = self._scene()
        ctx = _Ctx()
        commit.apply_attire_diff(
            sc, {"attire": {"Hinami": {"remove": ["tank top"]}}}, ctx, {})

        assert "fitted tank top" not in sc["attire"]["Hinami"]["wearing"]
        assert not any("no-op removal" in m for m in ctx.warned)

    def test_the_preview_path_stays_silent(self):
        """Perception applies the same diff with report=False; the miss must
        be reported once, at commit, not once per preview."""
        sc = self._scene()
        ctx = _Ctx()
        commit.apply_attire_diff(
            sc, {"attire": {"Hinami": {"remove": ["nightwear garment"]}}},
            ctx, {}, report=False)
        assert ctx.warned == [] and ctx.told == []
