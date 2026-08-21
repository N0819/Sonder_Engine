"""A wardrobe changes only where the beat's words say it does.

Chat 78, nine turns of an interrogation in which nobody touches clothing:
**not one beat's words name a garment**, and the wardrobe was rewritten twice.

* t7 -- `coverage` restating the whole wardrobe as `{region: []}` on a beat
  whose prose is "Hinami winces slightly, then her head lowers". Every garment
  stayed `state: "worn"` and covered nothing, so every region read bare. The
  refusal guard that exists for this shape fired for the other body in the
  scene and not for hers: it asks whether the claim leaves the body covered
  NOWHERE, and her jacket's `waist` survived the block by one region.
* t8 -- `remove` of two garments nobody touched. That set `uncovered` on five
  regions, which is the licence `describe` reads before printing a body's
  `beneath` prose, and the narrator wrote the result onto the page.

Neither is a naming failure: every garment in both blocks is spelled exactly
as the ledger holds it. The gate is therefore not about resolving handles --
`resolve_garment` did that correctly both times -- but about whether the beat
contains the change at all.

The failure direction that matters is the other one. A wardrobe that goes
quiet, or an attire string that loses its garments, is worse than a change
that arrives a beat late, so every test here has its positive control beside
it: the same write, on a beat that names the garment, still lands.
"""

from __future__ import annotations

import time

import pytest

from persist import commit
from story import attire
from core.pipeline_context import ChatData, PipelineContext, TurnData

#: The wardrobe as chat 78 held it before t7, minus the descriptions.
_WORN = ["lightweight travel jacket", "fitted tank top",
         "utility sash with pouches", "travel shorts", "sturdy sandals"]

#: t7's prose, verbatim in shape: a whole beat with no clothing in it.
_QUIET_BEAT = ("Hinami winces slightly, then her head lowers as she stops "
               "supporting herself; her body slumps forward in the restraints, "
               "now held upright solely by the chair's harness.")


def _regions():
    return {
        "torso": {"garments": [
            {"name": "lightweight travel jacket",
             "covers": ["torso", "arms", "waist"]},
            {"name": "fitted tank top"}],
            "beneath": "a scar under the collarbone"},
        "waist": {"garments": [{"name": "utility sash with pouches"}],
                  "beneath": "a paler band of skin"},
        "groin": {"garments": [{"name": "travel shorts",
                                "covers": ["groin", "legs"]}],
                  "beneath": "PRIVATE BODY PROSE"},
        "feet": {"garments": [{"name": "sturdy sandals"}],
                 "beneath": "calloused heels"},
    }


def _ctx(temp_db, player_input="", resolved=""):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Gate", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Gate", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)
    ctx.director_interpret = {}
    ctx.director_resolve = {"resolved_event": resolved}
    return ctx


def _scene():
    return {"positions": {"Hinami": "cell"},
            "attire": {"Hinami": attire.authored_entry(
                list(_WORN), [], _regions())}}


def _apply(temp_db, diff, *, player_input="", resolved="", declared=None):
    sc = _scene()
    ctx = _ctx(temp_db, player_input, resolved)
    if declared:
        # `ctx.character_results` is keyed by character id; `_beat_voices`
        # reads the values, so the ids only have to be distinct.
        ctx.character_results = {i + 1: d for i, d in enumerate(declared)}
    commit.apply_attire_diff(sc, {"attire": {"Hinami": diff}}, ctx,
                             ctx.director_resolve)
    return sc["attire"]["Hinami"], ctx


class TestTheQuietBeatChangesNothing:
    """t7 and t8, refused."""

    def test_a_coverage_block_on_a_beat_with_no_clothing_in_it_is_dropped(
            self, temp_db):
        entry, ctx = _apply(temp_db, {"coverage": {
            "lightweight travel jacket": {"torso": [], "arms": []},
            "fitted tank top": {"torso": [], "arms": []},
            "utility sash with pouches": {"waist": []},
            "travel shorts": {"groin": [], "legs": []},
            "sturdy sandals": {"feet": []},
        }}, resolved=_QUIET_BEAT)

        # Every garment still covers what it covered. Not "still worn" --
        # they were still `worn` in the live defect too, and covered nothing.
        assert attire.exposed_regions(entry["regions"]) == []
        assert not [n for n in attire.flat_state(entry["regions"])
                    if "displaced" in n or n.startswith("bare at")]
        assert any("no word of this beat names the garment" in w
                   for w in ctx.warnings)

    def test_a_removal_on_a_beat_with_no_clothing_in_it_is_dropped(
            self, temp_db):
        entry, ctx = _apply(temp_db, {"remove": [
            "lightweight travel jacket", "lightweight travel jacket",
            "travel shorts", "travel shorts"]}, resolved=_QUIET_BEAT)

        assert entry["wearing"] == _WORN
        assert not any(r.get("uncovered")
                       for r in entry["regions"].values())

    def test_the_string_is_not_scrubbed_by_the_gate(self, temp_db):
        """THE FAILURE DIRECTION THIS GATE MUST NOT HAVE.

        Refusing a change must leave the wardrobe exactly as legible as it
        was. A body whose garments stop being rendered is a worse defect than
        the one being fixed -- every mind in the scene reads this string.
        """
        entry, _ = _apply(temp_db, {"coverage": {
            "fitted tank top": {"torso": [], "arms": []}}},
            resolved=_QUIET_BEAT)

        line = attire.compact_line(entry["regions"], beneath_visible=True)
        for garment in ("travel jacket", "tank top", "sash", "sandals"):
            assert garment in line
        assert "PRIVATE BODY PROSE" not in line
        assert "bare" not in attire.describe(
            entry["regions"], beneath_visible=True)[0]


class TestANamedChangeStillLands:
    """The control. Every refusal above, with the beat saying it happened."""

    def test_a_named_removal_lands(self, temp_db):
        entry, ctx = _apply(
            temp_db, {"remove": ["lightweight travel jacket"]},
            resolved="She shrugs the travel jacket off and lets it fall.")

        assert "lightweight travel jacket" not in entry["wearing"]
        assert not any("names the garment" in w for w in ctx.warnings)

    def test_a_removal_named_by_the_player_alone_lands(self, temp_db):
        """The player's own input is licence: they are the same authority the
        Director is, scoped to their own conduct."""
        entry, _ = _apply(
            temp_db, {"remove": ["sturdy sandals"]},
            player_input="I kick the sandals off and stretch my toes.")

        assert "sturdy sandals" not in entry["wearing"]

    def test_a_named_displacement_lands(self, temp_db):
        entry, _ = _apply(
            temp_db, {"coverage": {"travel shorts": {"groin": [], "legs": []}}},
            resolved="She works the travel shorts down around her ankles.")

        assert "travel shorts" in entry["wearing"]
        assert "groin" in attire.exposed_regions(entry["regions"])

    def test_a_short_handle_is_licensed_by_the_ledger_spelling(self, temp_db):
        """The diff writes a handle, the prose uses its own words, and the
        ledger holds a third spelling. All three are the same garment."""
        entry, _ = _apply(
            temp_db, {"remove": ["tank top"]},
            resolved="The top comes free over her head.")

        assert "fitted tank top" not in entry["wearing"]


def _declared_action(attempt, observable=""):
    """One action element in the shape the pipeline actually stores.

    Taken from chat 78's own `interaction_loop` rows. THE POINT OF THIS
    HELPER is the key that is missing: an action element has no `text`. Its
    words are in `attempt` and `observable`, and a fixture that invents a
    `text` key tests a shape the engine never produces -- which is how the
    first version of these tests passed while an NPC undressing anybody in
    `sequence` was in fact refused.
    """
    return {"type": "action", "attempt": attempt, "observable": observable,
            "verb": "", "targets": [], "intended_effects": [],
            "asserted_effects": [], "commitment": "full", "stage": "attempt",
            "interrupts": False, "visibility": "public", "conceal_from": [],
            "event_id": "e1"}


class TestACharacterMayStillUndress:
    """THE CASE THIS GATE MUST NOT COST: a character taking clothing off.

    Every control above licenses the change from the Director's resolved prose
    or the player's input, and a character undressing -- itself or somebody
    else -- is neither. It reaches the seam through `ctx.character_results`,
    which is the third licence text and the one with no test behind it until
    now. If a declared removal were refused, an NPC could never undress
    anybody, which is a far worse defect than the one this gate closes.

    Every fixture here uses `_declared_action`, so the shape under test is the
    stored one.
    """

    def test_a_character_undressing_itself_is_licensed_by_its_declaration(
            self, temp_db):
        """Declared, and nowhere else. The resolved prose here is the same
        clothing-free beat that t7 refused, so the declaration is carrying the
        licence alone."""
        entry, ctx = _apply(
            temp_db, {"remove": ["lightweight travel jacket"]},
            resolved=_QUIET_BEAT,
            declared=[{"sequence": [_declared_action(
                "Shrug the travel jacket off her shoulders and let it drop "
                "behind the chair.")]}])

        assert "lightweight travel jacket" not in entry["wearing"]
        assert not any("names the garment" in w for w in ctx.warnings)

    def test_one_character_may_undress_another(self, temp_db):
        """The licence is the BEAT's words, not the body's own voice.

        Dr. Moon names the sash; the sash is Hinami's. A gate scoped to the
        undressed body's own declarations would refuse every NPC who ever
        removed somebody else's clothing -- restraints, a medical exam, a
        search, a fight.
        """
        entry, ctx = _apply(
            temp_db, {"remove": ["utility sash with pouches"]},
            resolved=_QUIET_BEAT,
            declared=[{"action": _declared_action(
                "Unclip the utility sash from Hinami's waist and set it on "
                "the tray beside the chair.")}])

        assert "utility sash with pouches" not in entry["wearing"]
        assert not any("names the garment" in w for w in ctx.warnings)

    def test_the_observable_surface_alone_is_licence(self, temp_db):
        """`attempt` is the actor's framing and `observable` is what a
        bystander sees. A garment named in only one of them is still named in
        this beat, so both are read."""
        entry, ctx = _apply(
            temp_db, {"remove": ["sturdy sandals"]},
            resolved=_QUIET_BEAT,
            declared=[{"sequence": [_declared_action(
                "Get her ready for transport.",
                observable="pulls the sturdy sandals off her feet")]}])

        assert "sturdy sandals" not in entry["wearing"]
        assert not any("names the garment" in w for w in ctx.warnings)

    def test_an_act_in_the_actions_list_is_read_too(self, temp_db):
        """`actions` is the other top-level list a merged result carries, and
        it was never read at all."""
        entry, _ = _apply(
            temp_db, {"remove": ["travel shorts"]},
            resolved=_QUIET_BEAT,
            declared=[{"actions": [_declared_action(
                "Draw the travel shorts down and off her legs.")]}])

        assert "travel shorts" not in entry["wearing"]

    def test_a_declared_displacement_lands_too(self, temp_db):
        """Not just `remove` -- the coverage channel takes a declaration as
        licence on the same terms."""
        entry, _ = _apply(
            temp_db, {"coverage": {"travel shorts": {"groin": [], "legs": []}}},
            resolved=_QUIET_BEAT,
            declared=[{"sequence": [
                {"type": "speech", "text": "Hold still."},
                _declared_action(
                    "Work her travel shorts down past her knees.")]}])

        assert "travel shorts" in entry["wearing"]
        assert "groin" in attire.exposed_regions(entry["regions"])

    def test_a_declaration_is_never_reduced_to_a_dict_repr(self, temp_db):
        """The mechanism, pinned directly.

        `str()` of a declaration yields a repr that CONTAINS the words, so a
        reader depending on it looks correct while depending on `repr` for its
        meaning. What must be false is that any voice is a Python literal.
        """
        # Through the facade: this test CALLS the helper rather than patching
        # it, and `persist.commit` re-exports the private names too.
        from persist.commit import _beat_voices

        class _Ctx:
            character_results = {63: {"sequence": [_declared_action(
                "Unclip the utility sash from Hinami's waist.")]}}

        voices = _beat_voices(_Ctx(), {})
        assert voices, "a declared act contributed no text at all"
        for voice in voices:
            assert not voice.lstrip().startswith("{"), voice[:80]
            assert "'type':" not in voice, voice[:80]
        assert any("utility sash" in v for v in voices)


class TestRemovalByOmission:
    """`replace` and `wearing` name what STAYS ON, so a garment left out of
    the list comes off -- and the fifth and sixth doors were open.

    `ed8e1e3`'s message claimed `replace` "cannot be a door" because it is
    `list[str]` and so cannot carry a `covered_zones` override. That is true
    and irrelevant: removal by omission needs no override. Measured on the
    branch before this class existed, on the quiet beat below, every case
    here stripped the wardrobe, set `uncovered`, minted floor objects and
    rendered the body's `beneath` prose, with no warning anywhere.
    """

    def test_a_replace_may_not_drop_an_unnamed_garment(self, temp_db):
        entry, ctx = _apply(temp_db, {"replace": ["fitted tank top"]},
                            resolved=_QUIET_BEAT)

        assert entry["wearing"] == _WORN
        assert not any(r.get("uncovered") for r in entry["regions"].values())
        assert "PRIVATE BODY PROSE" not in attire.compact_line(
            entry["regions"], beneath_visible=True)
        assert any("names the garment" in w for w in ctx.warnings)

    def test_a_wearing_restatement_may_not_drop_one_either(self, temp_db):
        entry, ctx = _apply(temp_db, {"wearing": ["fitted tank top"]},
                            resolved=_QUIET_BEAT)

        assert entry["wearing"] == _WORN
        assert any("names the garment" in w for w in ctx.warnings)

    def test_an_empty_replace_does_not_empty_the_wardrobe(self, temp_db):
        """The worst shape: `{"replace": []}` asserted the body wears
        nothing. It also proves the gate examines the channel that will
        actually APPLY -- holding garments back makes an empty `replace`
        truthy, which must not divert a diff the `wearing` branch owns."""
        entry, ctx = _apply(temp_db, {"replace": []}, resolved=_QUIET_BEAT)

        assert entry["wearing"] == _WORN
        assert any("names the garment" in w for w in ctx.warnings)

    def test_a_named_garment_may_still_be_dropped_by_omission(self, temp_db):
        """The control. Omission is a legitimate way to undress somebody when
        the beat says so; only the unnamed half is held."""
        entry, _ = _apply(
            temp_db,
            {"replace": ["lightweight travel jacket", "fitted tank top",
                         "utility sash with pouches", "travel shorts"]},
            resolved="She kicks the sturdy sandals off and leaves them there.")

        assert "sturdy sandals" not in entry["wearing"]
        assert "travel shorts" in entry["wearing"]
        assert entry["regions"]["feet"].get("uncovered") is True

    def test_an_addition_beside_a_restatement_still_lands(self, temp_db):
        """Holding an omission back must not refuse what the same diff ADDS."""
        entry, _ = _apply(
            temp_db, {"replace": ["fitted tank top"], "add": ["wool blanket"]},
            resolved=_QUIET_BEAT)

        assert "wool blanket" in entry["wearing"]
        for garment in _WORN:
            assert garment in entry["wearing"]


class TestTheGateSpeaksMoreThanOneLanguage:
    """A licence gate that cannot fire is worse than no gate.

    Every other prose reader in this module fails OPEN for a language it
    cannot read -- `_PROCESS` and `_DECISIVE` are English word tables, so a
    Japanese beat simply gets their mildest reading. This one REFUSES, and
    `\\b` does not exist between two Han or kana characters, so before this
    fix every undressing in a Japanese story was refused on every beat and
    "restate next beat" could never recover it. The engine ships language
    packs; this is a supported surface.
    """

    def test_a_japanese_beat_names_its_garment(self):
        assert attire.garments_named_in(
            ["彼女は上着を脱いだ。"], ["上着"], ["上着", "タンクトップ"]) == ["上着"]

    def test_an_unrelated_japanese_beat_still_names_nothing(self):
        """Fails open, not always open."""
        assert attire.garments_named_in(
            ["彼女は椅子に座った。"], ["上着"], ["上着", "タンクトップ"]) == []

    def test_english_word_boundaries_are_unchanged(self):
        """A name inside a longer word is still not a mention -- the anchor
        is dropped per EDGE and only where the script has no boundaries."""
        assert attire.garments_named_in(
            ["She adjusts the jacketing on the pipe."],
            ["lightweight travel jacket"], ["lightweight travel jacket"]) == []


class TestNumberIsNotIdentity:
    """"one sandal" and "her jackets" name their garment exactly as well as
    the ledger's own spelling, and both were refused on the number alone."""

    def test_a_singular_prose_word_names_a_plural_ledger_garment(self):
        assert attire.garments_named_in(
            ["She kicks one sandal off."], ["sturdy sandals"],
            ["sturdy sandals"]) == ["sturdy sandals"]

    def test_a_plural_prose_word_names_a_singular_ledger_garment(self):
        assert attire.garments_named_in(
            ["She peels her jackets off."], ["lightweight travel jacket"],
            ["lightweight travel jacket"]) == ["lightweight travel jacket"]

    def test_an_unrelated_garment_is_still_not_named(self):
        assert attire.garments_named_in(
            ["She kicks one sandal off."], ["fitted tank top"],
            ["fitted tank top", "sturdy sandals"]) == []

    def test_a_removal_named_by_nobody_is_the_only_thing_refused(
            self, temp_db):
        """THE LIMIT, stated rather than discovered later.

        A removal whose every mention is a pronoun -- "he pulls it off her" --
        names no garment and is refused. That is the cost of gating on
        mention, and it is the deliberate trade: design note 17 twice widened
        a verb vocabulary that was still one phrase short, so the gate asks
        the question with a stable answer instead. The Director is told to
        restate it, and a beat that says WHAT came off passes immediately --
        as the three tests above do.
        """
        entry, ctx = _apply(
            temp_db, {"remove": ["lightweight travel jacket"]},
            resolved="He reaches over and pulls it off her, tossing it aside.",
            declared=[{"action": "She lets him take it."}])

        assert "lightweight travel jacket" in entry["wearing"]
        assert any("names the garment" in w for w in ctx.warnings)


class TestUncoveredMeansUncovered:
    def test_shedding_an_outer_layer_does_not_bare_the_region_beneath(
            self, temp_db):
        """The jacket comes off over a tank top that is still on.

        `uncovered` is the flag `describe` reads before printing a body's
        `beneath`, and any departure at all used to set it. Torso keeps the
        tank top, so nothing about that region was uncovered; arms and waist,
        which the jacket alone covered, were.
        """
        entry, _ = _apply(
            temp_db, {"remove": ["lightweight travel jacket"]},
            resolved="She shrugs the travel jacket off her shoulders.")

        regions = entry["regions"]
        # Kept a covering -> not uncovered, and their `beneath` stays sealed.
        assert not regions["torso"].get("uncovered")
        assert not regions["waist"].get("uncovered")
        # The arms had only the jacket, so they genuinely were uncovered.
        assert regions["arms"].get("uncovered") is True
        assert attire.exposed_regions(regions) == ["arms"]
        line = attire.compact_line(regions, beneath_visible=True)
        assert "scar under the collarbone" not in line
        assert "paler band of skin" not in line
        assert "tank top" in line

    def test_shedding_the_last_covering_does_bare_the_region(self, temp_db):
        entry, _ = _apply(
            temp_db, {"remove": ["travel shorts"]},
            resolved="She steps out of the travel shorts.")

        assert entry["regions"]["groin"].get("uncovered") is True
        assert "PRIVATE BODY PROSE" in attire.compact_line(
            entry["regions"], beneath_visible=True)


def _regions_zeroing(*names):
    """`_regions()` with those garments asserted to cover nothing.

    The `regions` spelling of the same claim `coverage` makes -- `{region: []}`
    survives `_clean_covered_zones` (an explicitly empty list is the one way to
    say "displaced off it outright") and lands on the garment while it stays
    `state: "worn"`.
    """
    blocks = _regions()
    for entry in blocks.values():
        for item in entry["garments"]:
            if item["name"] in names:
                item["covered_zones"] = {
                    region: [] for region in
                    (item.get("covers") or [])} or {"torso": []}
    # The zones have to name the region the garment is filed under, not just
    # the ones it spans, or the override misses where it is read from.
    for region, entry in blocks.items():
        for item in entry["garments"]:
            if item["name"] in names:
                item["covered_zones"][region] = []
    return blocks


class TestTheRegionsDoor:
    """The fourth writer of `covered_zones`, and the only ungated one.

    `coverage`, `remove` and `placement` are gated at the seam. `regions` gets
    there too -- commit hands the block to `normalize_regions`, which reads a
    per-garment `covered_zones` off each item and replaces the body's whole
    region map -- and the body specialist is offered both spellings on every
    beat. Chat 78's t7 diff carries `"regions": {}` beside the `coverage`
    block that did the damage, so the same restatement one field over was one
    model choice away from landing.
    """

    def test_a_regions_block_may_not_undress_an_unnamed_garment(
            self, temp_db):
        entry, ctx = _apply(
            temp_db,
            {"wearing": list(_WORN),
             "regions": _regions_zeroing("fitted tank top", "travel shorts")},
            resolved=_QUIET_BEAT)

        assert attire.exposed_regions(entry["regions"]) == []
        assert "PRIVATE BODY PROSE" not in attire.compact_line(
            entry["regions"], beneath_visible=True)
        assert any("no word of this beat names the garment" in w
                   for w in ctx.warnings)

    def test_a_named_garment_may_still_be_displaced_by_regions(self, temp_db):
        """The control. The door is gated, not closed.

        The region goes bare and says what displaced it. It does NOT print the
        body's `beneath`: nothing departed, so `uncovered` is unset and the
        garment is still `worn`, which is the pair `describe` reads before
        printing private prose. Displacement bares a region; only a departure
        licenses what is under it. Pinned here because it is the distinction
        the whole gate exists to protect -- t7 shrank coverage and t8 supplied
        the departure, and it took both to put that prose on the page.
        """
        entry, _ = _apply(
            temp_db,
            {"wearing": list(_WORN),
             "regions": _regions_zeroing("travel shorts")},
            resolved="She works the travel shorts down past her hips.")

        assert "groin" in attire.exposed_regions(entry["regions"])
        line = attire.compact_line(entry["regions"], beneath_visible=True)
        assert "groin:bare[off:travel shorts]" in line
        assert "PRIVATE BODY PROSE" not in line

    def test_the_rest_of_an_unnamed_garments_block_still_lands(self, temp_db):
        """Per garment and per field -- not a wholesale refusal.

        A beat that re-arranges a wardrobe must not have its whole block
        refused because one garment in it was quiet; only the half that can
        bare a body is withheld.
        """
        blocks = _regions_zeroing("fitted tank top")
        for item in blocks["torso"]["garments"]:
            if item["name"] == "fitted tank top":
                item["condition"] = "damp at the collar"

        entry, _ = _apply(temp_db,
                          {"wearing": list(_WORN), "regions": blocks},
                          resolved=_QUIET_BEAT)

        garment = next(g for g in entry["regions"]["torso"]["garments"]
                       if g["name"] == "fitted tank top")
        assert garment["condition"] == "damp at the collar"
        assert "covered_zones" not in garment
