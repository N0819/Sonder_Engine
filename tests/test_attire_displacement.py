"""Displacement: what a still-worn garment no longer covers.

Design note 17. The ledger had two axes — the ladder (progress toward
removal) and the condition (what happened to the fabric) — and the fiction
has three: a jacket pushed off the shoulders is fully worn, undamaged, and
covering less. The corpus showed models writing that third axis into the
one field that accepts a sentence (37% of stored condition notes carried
displacement language; chat 68 t7 wrote a RUNG WORD into a condition), and
writing region-grain coverage that the torso-only validator silently
dropped (`{"sheer silk robe": {"torso": [], "groin": []}}`).

These tests replay the three incident beats and pin the axis rules:
coverage is region-grain, instant and reversible; the ladder is untouched
except that a fully-displaced garment's removal is one rung; decisive
intent dominates the removal/displacement boundary in BOTH directions; and
prose is detected, never executed.
"""

from __future__ import annotations

import time

import attire
import pytest


def _jacket_regions():
    return attire.normalize_regions({"regions": {"torso": {"garments": [
        {"name": "lightweight travel jacket",
         "covers": ["torso", "arms", "waist"]}]}}})


# ---- the third axis, region grain ----

class TestRegionGrainCoverage:
    def test_jacket_off_the_shoulders_arms_still_in_the_sleeves(self):
        """The chat 70 incident, expressed on the right axis: torso and
        waist bare, arms still covered, garment still worn."""
        after, notes = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        assert notes == []
        assert attire.concealing_garments(after) == {
            "arms": ["lightweight travel jacket"]}
        assert set(attire.exposed_regions(after)) == {"torso", "waist"}
        assert attire.flat_wearing(after) == ["lightweight travel jacket"]

    def test_trousers_at_the_ankles_are_worn_and_cover_nothing(self):
        regions = attire.normalize_regions({"regions": {"legs": {"garments": [
            {"name": "travel shorts", "covers": ["legs", "groin"]}]}}})
        after, _ = attire.apply_coverage_changes(
            regions, {"travel shorts": {"legs": [], "groin": []}})
        assert attire.flat_wearing(after) == ["travel shorts"]
        assert attire.concealing_garments(after) == {}
        assert set(attire.exposed_regions(after)) == {"legs", "groin"}

    def test_displacement_reverses_by_writing_the_full_list(self):
        """Instant and reversible: pulled back into place, the override is
        popped and coverage returns — no ladder, no residue."""
        displaced, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        back, _ = attire.apply_coverage_changes(
            displaced, {"travel jacket": {
                "torso": ["chest", "midriff"], "waist": ["waist"]}})
        assert attire.concealing_garments(back) == attire.concealing_garments(
            _jacket_regions())
        for entry in back.values():
            for garment in entry["garments"]:
                assert "covered_zones" not in garment

    def test_displacement_never_moves_the_ladder(self):
        after, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        states = {g["state"] for e in after.values() for g in e["garments"]}
        assert states == {"worn"}

    def test_the_invert_guard_keeps_unreadable_coverage_as_coverage(self):
        """Measured live: `{"head": ["hair"]}`. A non-empty list in which
        nothing validates asserts continued coverage in words the vocabulary
        cannot read — flipping it to "covers nothing" would invert it."""
        after, notes = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": ["hair"]}})
        assert attire.concealing_garments(after) == attire.concealing_garments(
            _jacket_regions())
        assert any("known zone" in n for n in notes)

    def test_a_rung_word_in_the_coverage_channel_is_named_not_applied(self):
        """Measured live: coverage carrying `{"state": "loosened"}`."""
        after, notes = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"state": "loosened"}})
        assert any("not a body region" in n for n in notes)
        states = {g["state"] for e in after.values() for g in e["garments"]}
        assert states == {"worn"}


# ---- composition with the ladder ----

class TestLadderComposition:
    def test_removal_from_fully_displaced_lands_even_mid_process(self):
        """Trousers at the ankles have played their middle out on the
        coverage axis: even a beat whose prose is still in progress
        ("begins to step out of them") completes, because from fully
        displaced the removal is one rung."""
        regions = attire.normalize_regions({"regions": {"legs": {"garments": [
            {"name": "travel shorts", "covers": ["legs", "groin"]}]}}})
        displaced, _ = attire.apply_coverage_changes(
            regions, {"travel shorts": {"legs": [], "groin": []}})
        after = attire.apply_flat_change(displaced, [], process=True)
        assert {g["state"] for e in after.values()
                for g in e["garments"]} == {"removed"}

    def test_partial_displacement_earns_no_discount_under_process(self):
        regions = attire.normalize_regions({"regions": {"legs": {"garments": [
            {"name": "travel shorts", "covers": ["legs", "groin"]}]}}})
        half, _ = attire.apply_coverage_changes(
            regions, {"travel shorts": {"groin": []}})
        after = attire.apply_flat_change(half, [], process=True)
        assert {g["state"] for e in after.values()
                for g in e["garments"]} == {"loosened"}

    def test_removed_clears_the_displacement_record(self):
        """A garment off the body covers nothing anywhere; a stale override
        must not resurface half-displaced on a re-wear."""
        displaced, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": []}})
        after = attire.apply_flat_change(displaced, [], decisive=True)
        for entry in after.values():
            for garment in entry["garments"]:
                assert garment["state"] == "removed"
                assert "covered_zones" not in garment

    def test_spanning_copies_agree_about_displacement(self):
        """One garment, one displacement record: every regional copy of a
        spanning garment answers coverage identically after a sync."""
        displaced, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"waist": []}})
        synced = attire._sync_spanning_garments(displaced)
        overrides = [g.get("covered_zones")
                     for e in synced.values() for g in e["garments"]]
        assert all(o == {"waist": []} for o in overrides)


# ---- the decisive boundary, both directions ----

class TestDecisiveBoundary:
    def test_the_chat_68_sentence_is_now_decisive(self):
        """`remove: ["tank top"]` for "she pulls the tank top off" was
        clamped to `loosened` because the fixed-phrase vocabulary cannot see
        a garment noun between the verb and "off" — the commonest English
        removal shape."""
        assert attire.decisive_intent("she pulls the tank top off")
        assert attire.decisive_intent("Elyra pulls Hinami's tank top off")
        assert attire.decisive_intent("he takes his coat off")

    def test_a_shove_off_a_body_place_is_not_a_removal(self):
        assert not attire.decisive_intent("the robe slips off her shoulder")
        assert not attire.decisive_intent(
            "she pushes the jacket off her shoulders")
        assert not attire.decisive_intent("he tugs the sleeve off her wrist")

    def test_yank_off_filed_as_coverage_escalates_to_removal(self):
        """The steal, forward direction: the new axis must not let a removal
        hide as a shove."""
        regions = attire.normalize_regions({"regions": {"torso": {"garments": [
            {"name": "fitted tank top", "covers": ["torso"]}]}}})
        escalated = attire.coverage_removal_escalations(
            ["Elyra pulls Hinami's tank top off in one motion"],
            {"tank top": {"torso": []}}, regions)
        assert escalated == ["tank top"]

    def test_a_hiked_skirt_stays_a_displacement(self):
        """The steal, reverse direction: decisive SPEED without removal
        DIRECTION must not undress anybody."""
        regions = attire.normalize_regions({"regions": {"legs": {"garments": [
            {"name": "linen skirt", "covers": ["legs", "groin"]}]}}})
        escalated = attire.coverage_removal_escalations(
            ["she yanks her skirt up around her waist in one motion"],
            {"skirt": {"groin": [], "legs": []}}, regions)
        assert escalated == []

    def test_partial_displacement_never_escalates(self):
        """Only a claim that empties EVERYTHING the garment covers can be a
        removal in disguise."""
        regions = attire.normalize_regions({"regions": {"torso": {"garments": [
            {"name": "fitted tank top", "covers": ["torso"]}]}}})
        escalated = attire.coverage_removal_escalations(
            ["she tears the tank top off"],
            {"tank top": {"torso": ["chest"]}}, regions)
        assert escalated == []


# ---- the deterministic floor: detect, feed back, never execute ----

class TestProseDetectors:
    def test_the_chat_70_jacket_condition_is_detected(self):
        assert attire.displacement_language(
            "pushed back off shoulders, bunched at forearms over raised arms")

    def test_the_chat_68_rung_word_is_detected(self):
        assert attire.rung_language(
            "hauled upward by Elyra, hem dragged to midriff, fabric bunched "
            "under arms—loosened, still worn") == "loosened"

    def test_plain_fabric_conditions_stay_silent(self):
        for text in ("wine-stained down the front", "torn at the seam",
                     "soaked through", "scorched at the hem"):
            assert not attire.displacement_language(text)
            assert not attire.rung_language(text)

    def test_removals_held_reports_the_process_clamp(self):
        prev = attire.normalize_regions({"regions": {"torso": {"garments": [
            {"name": "fitted tank top", "covers": ["torso"]}]}}})
        after = attire.apply_flat_change(prev, [], process=True)
        assert attire.removals_held(prev, after, []) == [
            ("fitted tank top", "loosened")]

    def test_removals_held_is_silent_when_removal_lands(self):
        prev = attire.normalize_regions({"regions": {"torso": {"garments": [
            {"name": "fitted tank top", "covers": ["torso"]}]}}})
        after = attire.apply_flat_change(prev, [])
        assert attire.removals_held(prev, after, []) == []


# ---- what the readers see ----

class TestRendering:
    def test_describe_marks_the_displaced_region(self):
        after, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        lines = "\n".join(attire.describe(after))
        assert "displaced; not covering this region" in lines
        assert "bare here" in lines

    def test_compact_line_shows_bare_with_the_garment_alongside(self):
        after, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        line = attire.compact_line(after)
        assert "torso:bare[off:lightweight travel jacket]" in line
        assert "arms:lightweight travel jacket" in line

    def test_perception_sees_skin_and_the_hanging_garment(self):
        after, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        surfaces = attire.perceptible_region_surfaces(after)
        # torso is zoned: both zones bare, jacket visible as hanging, never
        # as a covering surface
        assert "chest: bare" in surfaces["torso"]
        assert "midriff: bare" in surfaces["torso"]
        assert "displaced" in surfaces["torso"]
        assert surfaces["waist"].startswith("bare")
        assert "displaced" in surfaces["waist"]
        assert surfaces["arms"].startswith("lightweight travel jacket")

    def test_a_displaced_outer_layer_reveals_the_layer_beneath(self):
        regions = attire.normalize_regions({"regions": {"torso": {"garments": [
            {"name": "wool coat", "covers": ["torso", "arms", "waist"]},
            {"name": "linen shirt"}]}}})
        after, _ = attire.apply_coverage_changes(
            regions, {"wool coat": {"torso": []}})
        surface = attire.perceptible_region_surfaces(after)["torso"]
        assert "chest: linen shirt" in surface
        assert "wool coat" in surface and "displaced" in surface

    def test_flat_state_names_the_displacement_once(self):
        after, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        notes = attire.flat_state(after)
        displaced = [n for n in notes if "displaced off the" in n]
        assert displaced == [
            "lightweight travel jacket displaced off the torso, waist"]
        assert attire.is_derived_state_note(displaced[0])

    def test_rederive_is_idempotent_with_displacement(self):
        """The hand-edit path: attire_put re-derives every entry, and a
        checkpoint restore replays it — the record must not oscillate."""
        after, _ = attire.apply_coverage_changes(
            _jacket_regions(), {"travel jacket": {"torso": [], "waist": []}})
        entry = {"wearing": attire.flat_wearing(after),
                 "state": attire.flat_state(after), "regions": after}
        once = attire.rederive_entry(entry)
        twice = attire.rederive_entry(once)
        assert once == twice
        garment = once["regions"]["torso"]["garments"][0]
        assert garment["covered_zones"] == {"torso": [], "waist": []}


# ---- the commit seam, incident beats end to end ----

def _ctx(temp_db, player_input="wait"):
    from pipeline_context import ChatData, PipelineContext, TurnData
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Displacement", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, player_input, time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Displacement", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)


class TestCommitSeam:
    def test_the_jacket_beat_lands_on_the_coverage_axis(self, temp_db):
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {
            "resolved_event": "She shrugs the jacket back off her shoulders."}
        sc = {"attire": {"Hinami": attire.authored_entry(
            [], [], {"torso": {"garments": [
                {"name": "lightweight travel jacket",
                 "covers": ["torso", "arms", "waist"]}]}})}}
        diff = {"attire": {"Hinami": {
            "conditions": {"travel jacket":
                           "pushed back off shoulders, bunched at forearms"},
            "coverage": {"travel jacket": {"torso": [], "waist": []}},
        }}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        regions = sc["attire"]["Hinami"]["regions"]
        assert attire.concealing_garments(regions) == {
            "arms": ["lightweight travel jacket"]}
        assert "lightweight travel jacket" in sc["attire"]["Hinami"]["wearing"]
        # both channels written: no nag
        assert not any("coverage unchanged" in w for w in ctx.warnings)

    def test_displacement_only_in_prose_is_detected_and_fed_back(
            self, temp_db):
        """The chat 70 defect itself: vivid condition, no coverage change —
        the engine now says so instead of silently holding the body
        covered."""
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {"resolved_event": "The jacket slides back."}
        sc = {"attire": {"Hinami": attire.authored_entry(
            [], [], {"torso": {"garments": [
                {"name": "lightweight travel jacket",
                 "covers": ["torso", "arms", "waist"]}]}})}}
        diff = {"attire": {"Hinami": {"conditions": {
            "travel jacket": "pushed back off shoulders, bunched at "
                             "forearms over raised arms"}}}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        assert any("coverage unchanged" in w for w in ctx.warnings)
        assert any("coverage" in n for n in ctx.engine_feedback)
        # detection, never execution: the ledger still holds the jacket on
        regions = sc["attire"]["Hinami"]["regions"]
        assert "torso" in attire.concealing_garments(regions)

    def test_a_rung_word_in_condition_prose_is_fed_back(self, temp_db):
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {"resolved_event": "The top is hauled up."}
        sc = {"attire": {"Hinami": attire.authored_entry(
            [], [], {"torso": {"garments": [
                {"name": "fitted tank top"}]}})}}
        diff = {"attire": {"Hinami": {"conditions": {
            "tank top": "hauled upward by Elyra, hem dragged to midriff, "
                        "fabric bunched under arms—loosened, still worn"}}}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        assert any("rung word" in w for w in ctx.warnings)

    def test_a_removal_held_mid_process_is_said_out_loud(self, temp_db):
        """The clamp's one remaining removal trigger, and it is no longer
        silent: prose still in progress holds the removal at `loosened` AND
        tells the Director, so the fiction and the ledger reconverge."""
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {
            "resolved_event": "Elyra begins working at Hinami's tank top, "
                              "easing the hem upward."}
        sc = {"attire": {"Hinami": attire.authored_entry(
            [], [], {"torso": {"garments": [
                {"name": "fitted tank top"}]}})}}
        diff = {"attire": {"Hinami": {"remove": ["tank top"]}}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        garment = sc["attire"]["Hinami"]["regions"]["torso"]["garments"][0]
        assert garment["state"] == "loosened"
        assert any("held" in w and "loosened" in w for w in ctx.warnings)
        assert any("still in progress" in n for n in ctx.engine_feedback)

    def test_the_chat_70_reroll_beat_lands_without_vocabulary_help(
            self, temp_db):
        """The second incident: `remove: ["lightweight travel jacket"]`
        with "shrugs the jacket off" — a completion phrasing the decisive
        vocabulary missed. Under the inverted clamp the resolved removal
        lands on the Director's authority alone; no wordlist is on the
        critical path."""
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {
            "resolved_event": "Hinami lets the jacket drop away behind her."}
        sc = {"positions": {"Hinami": "room_a"},
              "attire": {"Hinami": attire.authored_entry(
                  [], [], {"torso": {"garments": [
                      {"name": "lightweight travel jacket",
                       "covers": ["torso", "arms", "waist"]}]}})}}
        diff = {"attire": {"Hinami": {
            "remove": ["lightweight travel jacket"]}}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        states = {g["state"]
                  for e in sc["attire"]["Hinami"]["regions"].values()
                  for g in e["garments"]}
        assert states == {"removed"}
        assert not any("held" in w for w in ctx.warnings)
        shed = [e for e in sc.get("entities", {}).values()
                if e.get("name") == "lightweight travel jacket"]
        assert len(shed) == 1

    def test_process_attribution_is_per_body(self, temp_db):
        """"Corin fumbles with the knots of Mira's sash" is Mira's sash
        staying on — and someone ELSE's clean removal in the same beat still
        lands."""
        targets = attire.process_targets(
            "", ["Corin fumbles with the knots of Mira's sash."],
            {"Mira": ["silk sash"], "Corin": ["jerkin"]},
            player_name="Mira")
        assert targets == {"Mira"}

    def test_the_chat_68_removal_now_lands_in_one_beat(self, temp_db):
        """With the vocabulary gap closed, the same beat reaches `removed`
        at once, undamaged, and the shed garment is minted."""
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {
            "resolved_event": "Elyra pulls Hinami's tank top off in one "
                              "motion."}
        sc = {"positions": {"Hinami": "room_a"},
              "attire": {"Hinami": attire.authored_entry(
                  [], [], {"torso": {"garments": [
                      {"name": "fitted tank top"}]}})}}
        diff = {"attire": {"Hinami": {"remove": ["tank top"]}}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        garment = sc["attire"]["Hinami"]["regions"]["torso"]["garments"][0]
        assert garment["state"] == "removed"
        assert not any("held" in w for w in ctx.warnings)
        shed = [e for e in sc.get("entities", {}).values()
                if e.get("name") == "fitted tank top"]
        assert len(shed) == 1

    def test_a_decisive_removal_filed_as_coverage_is_escalated(
            self, temp_db):
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {
            "resolved_event": "Elyra pulls Hinami's tank top off in one "
                              "motion."}
        sc = {"positions": {"Hinami": "room_a"},
              "attire": {"Hinami": attire.authored_entry(
                  [], [], {"torso": {"garments": [
                      {"name": "fitted tank top"}]}})}}
        diff = {"attire": {"Hinami": {"coverage": {
            "tank top": {"torso": []}}}}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        garment = sc["attire"]["Hinami"]["regions"]["torso"]["garments"][0]
        assert garment["state"] == "removed"
        assert any("decisive removal" in n for n in ctx.engine_feedback)

    def test_a_legacy_blob_without_displacement_is_untouched(self, temp_db):
        """A scene from before the change loads and behaves: no coverage op,
        no override, byte-stable coverage answers."""
        import commit
        ctx = _ctx(temp_db)
        ctx.director_interpret = {}
        ctx.director_resolve = {"resolved_event": "Nothing changes."}
        sc = {"attire": {"Hinami": attire.authored_entry(
            ["fitted tank top"], [], None)}}
        before = attire.concealing_garments(
            attire.normalize_regions(sc["attire"]["Hinami"]))
        diff = {"attire": {"Hinami": {"conditions": {
            "tank top": "wine-stained down the front"}}}}
        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)
        after = attire.concealing_garments(sc["attire"]["Hinami"]["regions"])
        assert after == before
        assert not ctx.warnings
