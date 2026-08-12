"""Authoring the clothing a character starts in, region by region.

`tests/test_attire_regions.py` covers the model -- where a garment goes, and
that taking it off takes time. This covers the half that lets an author
actually say any of it: the card fields, the seed into a live scene, the switch
governing whether what is under a garment is described at all, and the
generator that fills the whole lot in.
"""

from __future__ import annotations

import json
import time

import attire
import character_schema
import scene


# --- the card can carry it ---------------------------------------------------

def test_a_card_keeps_authored_regions_through_normalization():
    sheet = character_schema.default_character_data("Mira")
    sheet["initial_outfit"] = {
        "wearing": ["a silk sash"],
        "state": [],
        "regions": {"torso": {"garments": [{"name": "flowing robes"}],
                              "beneath": "old scars across the ribs"}},
    }
    out = character_schema.normalize_character_data(sheet)["initial_outfit"]
    # Placed explicitly on the torso and nowhere else, so it spans nothing:
    # the author said where it goes. (The editor's default is "auto", which
    # asks `regions_covered` instead -- see test_auto_coverage_spans.)
    assert out["regions"]["torso"]["garments"] == [
        {"name": "flowing robes", "description": "", "attaches": False,
         "state": "worn", "condition": "", "covers": []}]
    assert out["regions"]["torso"]["beneath"] == "old scars across the ribs"
    # The legacy flat list IS migrated into regions on read, now that it is an
    # input format rather than an authoring surface: `region_of`'s guess has to
    # land somewhere an author can see and move it, and the region editor is
    # the only place that is.
    assert out["regions"]["waist"]["garments"][0]["name"] == "a silk sash"
    # ...and `wearing` comes back DERIVED, so the two cannot disagree about the
    # same body. Robes span torso/waist/groin/legs, and the flat list still
    # names each garment once.
    assert out["wearing"] == ["flowing robes", "a silk sash"]
    assert set(out["regions"]) == {"torso", "waist"}


def test_auto_coverage_spans_from_the_name():
    """The editor's default coverage. Resolved in `character_schema`/`attire`
    rather than in the browser, so the cue table has one implementation."""
    out = character_schema.normalize_character_data({
        "identity": {"name": "Mira"},
        "initial_outfit": {"regions": {"torso": {"garments": [
            {"name": "a silk kimono", "state": "worn", "auto": True}]}}},
    })["initial_outfit"]
    assert set(out["regions"]) == {"torso", "arms", "waist", "groin", "legs"}
    # One garment, not five: it moves and is reported as one thing.
    assert out["wearing"] == ["a silk kimono"]
    assert out["regions"]["legs"]["garments"][0]["covers"] == [
        "torso", "arms", "waist", "groin", "legs"]


def test_a_sash_does_not_cover_the_groin():
    """The failure this region split exists to prevent: `waist` is the belt
    line, and a body wearing nothing but an obi is bare where it counts."""
    out = character_schema.normalize_character_data({
        "identity": {"name": "Mira"},
        "initial_outfit": {"wearing": ["an obi"]},
    })["initial_outfit"]
    assert attire.covered_regions(out["regions"]) == ["waist"]
    assert "groin" not in out["regions"]


def test_a_persona_card_carries_them_too():
    sheet = character_schema.default_persona_data("Nia")
    sheet["initial_outfit"] = {"regions": {
        "feet": {"garments": ["heavy boots"], "beneath": ""}}}
    out = character_schema.normalize_persona_data(sheet)["initial_outfit"]
    assert out["regions"]["feet"]["garments"][0]["name"] == "heavy boots"


def test_an_old_card_gains_the_field_without_gaining_clothes():
    out = character_schema.normalize_character_data(
        {"identity": {"name": "Legacy"}})["initial_outfit"]
    assert out == {"wearing": [], "state": [], "regions": {}}


# --- the merge happens once, where it is not saved ---------------------------

def test_the_flat_list_fills_regions_the_author_left_alone():
    entry = attire.authored_entry(
        wearing=["a silk sash", "flowing robes"],
        regions={"torso": {"garments": [{"name": "flowing robes"}],
                           "beneath": "old scars"}})
    assert entry["regions"]["waist"]["garments"][0]["name"] == "a silk sash"
    assert entry["regions"]["torso"]["beneath"] == "old scars"


def test_a_garment_placed_by_hand_is_not_also_placed_by_guess():
    """The three-outfits bug, in its authoring form. An author who deliberately
    puts a sash on the torso has a card whose flat list still says "silk sash",
    and the cue table says waist -- so the same garment would be worn twice, on
    two body parts."""
    entry = attire.authored_entry(
        wearing=["silk sash"],
        regions={"torso": {"garments": [{"name": "silk sash"}]}})
    assert "waist" not in entry["regions"]
    assert entry["wearing"] == ["silk sash"]


def test_the_flat_list_is_derived_so_the_two_never_disagree():
    entry = attire.authored_entry(
        regions={"feet": {"garments": [{"name": "heavy boots"}]}})
    assert entry["wearing"] == ["heavy boots"]


# --- and reaches a live scene ------------------------------------------------

def test_seeding_a_scene_places_the_authored_regions():
    sc = {}
    assert scene.seed_initial_attire(sc, "Mira", {
        "wearing": ["a silk sash"],
        "regions": {"torso": {"garments": [{"name": "flowing robes"}],
                              "beneath": "old scars across the ribs"}},
    })
    entry = sc["attire"]["Mira"]
    assert sorted(entry["wearing"]) == ["a silk sash", "flowing robes"]
    assert entry["regions"]["waist"]["garments"][0]["name"] == "a silk sash"
    assert entry["regions"]["torso"]["beneath"] == "old scars across the ribs"


def test_a_card_with_only_regions_still_seeds():
    """Nothing forces an author to fill the flat list as well, so a card that
    used the region editor alone must not read as having no clothes."""
    sc = {}
    assert scene.seed_initial_attire(sc, "Mira", {
        "regions": {"feet": {"garments": [{"name": "heavy boots"}]}}})
    assert sc["attire"]["Mira"]["wearing"] == ["heavy boots"]


def test_an_empty_card_seeds_nothing():
    sc = {}
    assert not scene.seed_initial_attire(sc, "Mira", {})
    assert not scene.seed_initial_attire(sc, "Mira", {"regions": {}})
    assert not sc.get("attire")


def test_seeding_never_overwrites_clothes_the_story_already_changed():
    sc = {"attire": {"Mira": {"wearing": ["a borrowed coat"], "state": []}}}
    assert not scene.seed_initial_attire(
        sc, "Mira", {"regions": {"torso": {"garments": [{"name": "robes"}]}}})
    assert sc["attire"]["Mira"]["wearing"] == ["a borrowed coat"]


# --- what is underneath is off unless asked for ------------------------------

class TestBeneathVisibility:
    """`beneath` is explicit body description that travels in an exported
    card. Authoring it and using it are two separate decisions."""

    def _entry(self):
        return {"wearing": [], "state": [], "regions": {
            "torso": {"garments": [{"name": "a robe", "state": "removed"}],
                      "beneath": "old scars across the ribs"}}}

    def test_off_by_default(self, temp_db):
        from agents.common import attire_view

        view = attire_view(self._entry())
        # The exposure itself is objective and still reported -- it is the
        # description of the body under the clothes that is withheld.
        assert view["regions"] == ["torso: bare"]

    def test_on_when_the_host_switches_it_on(self, temp_db):
        from agents.common import attire_view

        temp_db.set_setting("attire_beneath", "1")
        view = attire_view(self._entry())
        assert "old scars across the ribs" in view["regions"][0]

    def test_a_covered_region_never_says_what_is_under_it(self, temp_db):
        """Even switched on. A robe that is merely open has not uncovered
        anything, and the description belongs to the beat that does."""
        from agents.common import attire_view

        temp_db.set_setting("attire_beneath", "1")
        view = attire_view({"regions": {"torso": {
            "garments": [{"name": "a robe", "state": "open"}],
            "beneath": "old scars across the ribs"}}})
        assert view["regions"] == ["torso: a robe (open)"]

    def test_the_flat_pair_survives_the_view(self, temp_db):
        """The Director writes attire back as whole garments, so the shape it
        reads must keep the list it is going to edit."""
        from agents.common import attire_view

        view = attire_view({"wearing": ["a robe"], "state": ["rain-damp"]})
        assert view["wearing"] == ["a robe"]
        assert view["state"] == ["rain-damp"]


# --- the generator -----------------------------------------------------------

class TestAppearanceFill:

    def _card(self, temp_db):
        sheet = {"identity": {"name": "Mira"},
                 "embodiment": {"visible": {"summary": "Tall, weather-worn."}}}
        return temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            ("Mira", json.dumps(sheet), "{}", time.time(), "char_mira"))

    def _proposal(self):
        return {
            "embodiment": {"visible": {
                "summary": "Tall, weather-worn, with a burn across one wrist.",
                "build": "rangy"}},
            "initial_outfit": {
                "wearing": ["flowing robes", "a silk sash"],
                "state": [],
                "regions": {
                    "torso": {"garments": [{"name": "flowing robes",
                                            "state": "worn"}],
                              "beneath": "old scars across the ribs"},
                    "waist": {"garments": [{"name": "a silk sash",
                                            "state": "worn"}],
                              "beneath": ""},
                }},
        }

    def test_it_proposes_a_whole_body_and_outfit(self, temp_db, monkeypatch):
        import importers

        char_id = self._card(temp_db)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: json.dumps(self._proposal()))
        sheet = importers.fill_appearance(
            "character", char_id, "a travelling healer", include_beneath=True)

        assert sheet["embodiment"]["visible"]["build"] == "rangy"
        outfit = sheet["initial_outfit"]
        assert outfit["regions"]["torso"]["beneath"] == "old scars across the ribs"
        assert sorted(outfit["wearing"]) == ["a silk sash", "flowing robes"]

    def test_underneath_is_not_written_unless_it_was_asked_for(
            self, temp_db, monkeypatch):
        """The switch in Settings decides whether `beneath` is USED. This
        decides whether it is ever put on the card -- a model that answered a
        question nobody asked must not leave it there."""
        import importers

        char_id = self._card(temp_db)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: json.dumps(self._proposal()))
        sheet = importers.fill_appearance(
            "character", char_id, "", include_beneath=False)
        assert sheet["initial_outfit"]["regions"]["torso"]["beneath"] == ""

    def test_it_writes_nothing(self, temp_db, monkeypatch):
        """A generation request is "show me one", not "replace my card". The
        author's ordinary Save is still what commits it."""
        import importers

        char_id = self._card(temp_db)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: json.dumps(self._proposal()))
        importers.fill_appearance("character", char_id, "", include_beneath=True)
        stored = json.loads(temp_db.q(
            "SELECT sheet FROM characters WHERE id=?", (char_id,),
            one=True)["sheet"])
        assert stored["embodiment"]["visible"] == {"summary": "Tall, weather-worn."}
        assert "initial_outfit" not in stored

    def test_what_the_author_has_typed_is_what_it_works_from(
            self, temp_db, monkeypatch):
        """Generating from the SAVED copy would ignore the two lines they just
        wrote, which is exactly when anyone presses the button."""
        import importers

        char_id = self._card(temp_db)
        seen = {}
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda role, system, user, **k: (
                seen.update(json.loads(user)), json.dumps(self._proposal()))[1])
        importers.fill_appearance(
            "character", char_id, "brief", draft={
                "appearance": {"summary": "UNSAVED EDIT"},
                "initial_outfit": {"wearing": ["a borrowed coat"]}})
        assert seen["author_draft"]["appearance"]["summary"] == "UNSAVED EDIT"
        assert seen["brief"] == "brief"
        assert seen["include_beneath"] is False

    def test_a_persona_uses_the_same_generator(self, temp_db, monkeypatch):
        import importers

        pid = temp_db.qi(
            "INSERT INTO personas(name,sheet,source,resource_uid) "
            "VALUES(?,?,?,?)",
            ("Nia", json.dumps({"identity": {"name": "Nia"}}), "{}", "p_nia"))
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: json.dumps(self._proposal()))
        sheet = importers.fill_appearance("persona", pid, "", include_beneath=True)
        assert sheet["initial_outfit"]["regions"]["waist"]["garments"][0][
            "name"] == "a silk sash"

    def test_an_empty_response_says_what_actually_went_wrong(
            self, temp_db, monkeypatch):
        """The first thing this feature did in real use was fail with "Raw
        output:" and then nothing, because the raw output WAS nothing. An
        empty response and an unparseable one have different causes."""
        import importers
        import pytest

        char_id = self._card(temp_db)
        monkeypatch.setattr(importers, "chat_complete", lambda *a, **k: "")
        with pytest.raises(RuntimeError, match="budget ran out"):
            importers.fill_appearance("character", char_id, "")

    def test_a_non_json_response_still_shows_what_came_back(
            self, temp_db, monkeypatch):
        import importers
        import pytest

        char_id = self._card(temp_db)
        monkeypatch.setattr(importers, "chat_complete",
                            lambda *a, **k: "I'm sorry, I can't help with that.")
        with pytest.raises(RuntimeError, match="I'm sorry"):
            importers.fill_appearance("character", char_id, "")

    def test_it_asks_for_the_configured_ceiling_not_a_fixed_budget(
            self, temp_db, monkeypatch):
        """A reasoning model bills thinking as output. A hardcoded few thousand
        tokens is spent deliberating and the call returns an empty string --
        which is exactly how this failed. None means "the configured ceiling"
        (providers._clamp_max_tokens)."""
        import importers

        char_id = self._card(temp_db)
        seen = {}

        def capture(*args, **kwargs):
            seen.update(kwargs)
            return json.dumps(self._proposal())

        monkeypatch.setattr(importers, "chat_complete", capture)
        importers.fill_appearance("character", char_id, "")
        assert seen["max_tokens"] is None

    def test_a_cut_off_response_is_reported_not_salvaged(
            self, temp_db, monkeypatch):
        """`_jparse` closes the open braces of a truncated response, which is
        right for a pipeline beat that must not die and wrong here: it hands
        back half an outfit looking exactly like a whole one."""
        import importers
        import pytest

        char_id = self._card(temp_db)
        whole = json.dumps(self._proposal())
        # The first cut the salvage recovers something TRUTHY from. Most cuts
        # yield `{}` and are caught by the no-usable-data branch above; these
        # are the dangerous ones, because a partial dict looks like an answer.
        cut = next(whole[:n] for n in range(40, len(whole))
                   if importers._jparse(whole[:n]))
        salvaged = importers._jparse(cut)
        assert salvaged and "initial_outfit" not in salvaged
        monkeypatch.setattr(importers, "chat_complete", lambda *a, **k: cut)
        with pytest.raises(RuntimeError, match="cut off"):
            importers.fill_appearance("character", char_id, "")

    def test_no_truncation_point_slips_through(self):
        """Ending in `}` is not the test: a cut lands right after a closing
        brace often enough, and then the tail of the object is just missing."""
        import importers

        whole = json.dumps(self._proposal())
        assert not [n for n in range(40, len(whole))
                    if importers._json_arrived_whole(whole[:n])]

    def test_a_complete_answer_is_not_mistaken_for_a_truncated_one(
            self, temp_db, monkeypatch):
        """Fences and chatter around a whole object are a complete answer with
        packaging, not a cut-off one."""
        import importers

        char_id = self._card(temp_db)
        whole = json.dumps(self._proposal())
        for wrapped in ("```json\n%s\n```" % whole,
                        "Sure!\n%s\nHope that helps." % whole,
                        whole):
            monkeypatch.setattr(importers, "chat_complete",
                                lambda *a, _w=wrapped, **k: _w)
            sheet = importers.fill_appearance("character", char_id, "")
            assert sheet["initial_outfit"]["wearing"]

    def test_a_missing_card_is_a_missing_card(self, temp_db):
        import importers
        import pytest

        with pytest.raises(ValueError):
            importers.fill_appearance("character", 999999, "")


class TestAShedGarmentIsARealObject:
    """`attire.newly_removed` only reports which garments crossed the line;
    turning one into a thing in the room is the commit path's job."""

    def test_it_lands_in_the_scene_and_in_the_projection(self):
        import commit

        sc = {"positions": {"Mira": "room_a"}}
        diff = {}
        commit._mint_shed_garments(sc, [("Mira", "silk sash")], diff)
        key, = sc["entities"]
        assert sc["entities"][key]["portable"] is True
        assert sc["positions"][key] == "room_a"
        # world_entities is a derived projection of the beat's DIFF, not of the
        # scene blob, so an entity minted only into the scene would be live in
        # the story and missing from the normalized table.
        assert diff["entities"][key] is sc["entities"][key]

    def test_the_same_garment_is_not_minted_twice(self):
        import commit

        sc, diff = {"positions": {"Mira": "room_a"}}, {}
        commit._mint_shed_garments(sc, [("Mira", "silk sash")], diff)
        first = dict(sc["entities"])
        commit._mint_shed_garments(sc, [("Mira", "silk sash")], diff)
        assert list(sc["entities"]) == list(first)

    def test_a_short_remove_handle_uses_the_canonical_garment(
            self, temp_db, monkeypatch):
        """Live chat 68: ``tank top`` must remove ``fitted tank top``.

        The resolver already knew the answer; commit's exact ``in`` check was
        the one bypass that left the garment worn beside its floor object.
        """
        import commit
        from pipeline_context import ChatData, PipelineContext, TurnData

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Attire", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "wait", time.time()))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Attire", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                          player_input="wait", created=time.time()),
            cast=[], input="wait")
        ctx.director_interpret = {}
        ctx.director_resolve = {"resolved_event": "The top comes off."}
        monkeypatch.setattr(attire, "decisive_targets",
                            lambda *a, **k: {"Hinami"})
        sc = {
            "positions": {"Hinami": "room_a"},
            "attire": {"Hinami": attire.authored_entry(
                ["fitted tank top"], [], {"torso": {
                    "garments": [{"name": "fitted tank top"}],
                    "beneath": "a silver scar",
                }})},
        }
        diff = {"attire": {"Hinami": {"remove": ["tank top"]}}}

        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)

        assert "fitted tank top" not in sc["attire"]["Hinami"]["wearing"]
        assert sc["attire"]["Hinami"]["regions"]["torso"][
            "garments"][0]["state"] == "removed"
        shed = [e for e in sc["entities"].values()
                if e.get("name") == "fitted tank top"]
        assert len(shed) == 1

    def test_an_explicit_shed_entity_recovers_removal_and_position(self):
        """The other live split: an entity cannot say shed while the same
        unique garment remains on the named wearer's body."""
        sc = {
            "positions": {"Hinami": "room_a"},
            "entities": {},
            "attire": {"Hinami": {
                "wearing": ["utility sash with pouches"], "state": []}},
        }
        diff = {"entities": {"utility_sash_hinami": {
            "name": "utility sash", "aliases": ["sash"],
            "state": {"clothing": True, "shed": True,
                      "worn_by": "Hinami"},
        }}}

        recovered = attire.recover_shed_entity_changes(sc, diff)

        assert recovered[0]["garment"] == "utility sash with pouches"
        assert diff["attire"]["Hinami"]["remove"] == [
            "utility sash with pouches"]
        assert diff["positions"]["utility_sash_hinami"] == "room_a"

    def test_commit_applies_partial_coverage_through_a_short_handle(
            self, temp_db):
        """Coverage is standing state, separate from a descriptive condition:
        a rucked tank remains worn while only its midriff zone becomes bare."""
        import commit
        from pipeline_context import ChatData, PipelineContext, TurnData

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Coverage", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "wait", time.time()))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Coverage", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                          player_input="wait", created=time.time()),
            cast=[], input="wait")
        ctx.director_interpret = {}
        ctx.director_resolve = {"resolved_event": "The top rides up."}
        sc = {"attire": {"Hinami": attire.authored_entry(
            ["fitted tank top"], [], {"torso": {
                "garments": [{"name": "fitted tank top"}],
                "beneath_zones": {"midriff": "old scrape scars"},
            }})}}
        diff = {"attire": {"Hinami": {
            "conditions": {"tank top": "hem rucked above the stomach"},
            "coverage": {"tank top": {"torso": ["chest"]}},
        }}}

        commit.apply_attire_diff(sc, diff, ctx, ctx.director_resolve)

        hinami = sc["attire"]["Hinami"]
        assert hinami["wearing"] == ["fitted tank top"]
        garment = hinami["regions"]["torso"]["garments"][0]
        assert garment["covered_zones"] == {"torso": ["chest"]}
        assert garment["condition"] == "hem rucked above the stomach"
        assert attire.partially_exposed_regions(hinami["regions"]) == {
            "torso": ["midriff"]}

        restored, notes = attire.apply_coverage_changes(
            hinami["regions"],
            {"tank top": {"torso": ["midriff", "chest"]}},
        )
        assert notes == []
        assert "covered_zones" not in restored["torso"]["garments"][0]
        assert attire.partially_exposed_regions(restored) == {}


class TestTheRoutes:
    """The wiring, once, through the real app: a stubbed model reaching the
    editor as JSON, and the switch the whole `beneath` feature hangs on."""

    def _client(self):
        import pytest
        from fastapi.testclient import TestClient

        import app as app_module
        import guest_access as guest

        guest.reset_host_account()
        client = TestClient(app_module.app)
        client.__enter__()
        r = client.post("/api/auth/setup",
                        json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        return client

    def test_the_fill_route_returns_a_proposal(self, temp_db, monkeypatch):
        import importers

        monkeypatch.setattr(importers, "chat_complete", lambda *a, **k: json.dumps({
            "embodiment": {"visible": {"summary": "Rangy.", "build": "rangy"}},
            "initial_outfit": {
                "wearing": ["flowing robes"], "state": [],
                "regions": {"torso": {
                    "garments": [{"name": "flowing robes", "state": "worn"}],
                    "beneath": "old scars across the ribs"}}}}))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            ("Mira", json.dumps({"identity": {"name": "Mira"}}), "{}",
             time.time(), "char_route"))
        client = self._client()
        try:
            r = client.post(f"/api/characters/{char_id}/fill_appearance",
                            json={"prompt": "a travelling healer",
                                  "beneath": True,
                                  "draft": {"appearance": {"summary": "UNSAVED"}}})
            assert r.status_code == 200, r.text
            outfit = r.json()["sheet"]["initial_outfit"]
            assert outfit["regions"]["torso"]["beneath"] == "old scars across the ribs"
            assert outfit["wearing"] == ["flowing robes"]
        finally:
            client.__exit__(None, None, None)

    def test_the_switch_round_trips(self, temp_db):
        client = self._client()
        try:
            assert client.get("/api/bootstrap").json()["attire_beneath"] is False
            assert client.put("/api/attire_beneath",
                              json={"enabled": True}).status_code == 200
            assert client.get("/api/bootstrap").json()["attire_beneath"] is True
            client.put("/api/attire_beneath", json={"enabled": False})
            assert client.get("/api/bootstrap").json()["attire_beneath"] is False
        finally:
            client.__exit__(None, None, None)


def test_both_card_editors_offer_regions_and_the_generator():
    """A source-text check, in the spirit of the one beside it in
    `test_initial_outfit.py`: there are two card editors and it is easy to
    build a field into one of them."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    editors = (root / "static/js/editors.js").read_text(encoding="utf-8")
    components = (root / "static/js/components.js").read_text(encoding="utf-8")

    assert editors.count("f.outfit_regions = fAttireGarments(") == 2
    assert editors.count("f.outfit_regions.node") == 2
    # Twice per editor: once into the saved sheet, once into the draft the
    # generator works from.
    assert editors.count("regions: f.outfit_regions.read()") == 4
    assert editors.count("appearanceFillButton(") == 3   # one factory, two uses
    # The regions come from attire.REGIONS; a rename on one side that never
    # reached the other would silently drop a body part from the editor --
    # and `groin` is the one where that would matter most.
    for region in attire.REGIONS:
        assert '"%s"' % region in components
    # Name and description are separate inputs: the name is the matching key.
    assert 'placeholder: "what it looks like (optional)"' in components
    assert "worn at, covers nothing (ribbon, necklace, ring)" in components
    # Prose lists are one-per-line, not comma-split -- a generated feature
    # containing a comma was silently fragmented on save.
    assert "function fLineList(" in components
    assert editors.count("f.distinctive = fLineList(") == 2
    # Coverage is a dropdown of checkboxes -- any combination, with the spans
    # real clothing actually has offered as one-click presets, and "auto"
    # resolved in attire.py rather than duplicated in the browser.
    assert "fCoveragePicker" in components
    assert "ATTIRE_COVERAGE" in components
    assert "kimono, toga, jumpsuit" in components
    assert "auto — work it out from the garment's name" in components
    assert 'const ATTIRE_REGION_ZONES = { torso: ["chest", "midriff"] }' in components
    assert "covered_zones" in components
    assert "beneath_zones" in components
    # The one warning an author most needs where they are authoring.
    assert "a sash alone" in components


def test_the_generator_prompt_states_the_rules_it_has_to_state():
    from prompts import DEFAULT_PROMPTS

    prompt = DEFAULT_PROMPTS["fill_appearance"]
    # Every garment must land somewhere, or the region model has nothing to
    # work with and the flat list is all that survives.
    for region in attire.REGIONS:
        assert region in prompt
    assert "OUTERMOST FIRST" in prompt
    assert "include_beneath" in prompt
    assert "never mention a garment" in prompt
    assert "NAME AND DESCRIPTION ARE TWO FIELDS" in prompt
    assert "WORN AT IS NOT WORN OVER" in prompt
    assert "LAYERS, OUTERMOST FIRST" in prompt
    # The card is most of the answer, not merely something to avoid
    # contradicting -- a body that would fit any stranger means it was not
    # read. Each of these is named as something to derive FROM.
    assert "DERIVE FROM THE CARD" in prompt
    for field in ("competence.abilities", "public_history", "psychology",
                  "initial_state", "embodiment.latent", "identity"):
        assert field in prompt
    # ...and the derivation has to reach the CLOTHES and the UNDERNEATH, not
    # just the body. Either one generated from nothing is the same complaint.
    assert "THE CLOTHES COME FROM THE CARD TOO" in prompt
    assert "DERIVE IT FROM THE SAME CARD" in prompt
    # A thin card must produce less, not invention.
    assert "rather than inventing a history" in prompt


def test_the_generator_sees_the_whole_card_and_the_unsaved_draft(
        temp_db, monkeypatch):
    """The complaint this answers: a generated body unrelated to the character
    it is for. Everything the prompt is told to derive from has to actually be
    in the payload."""
    import importers

    card = character_schema.default_character_data("Mira")
    card["competence"]["abilities"] = [
        {"name": "farrier", "level": "expert", "scope": "horses"}]
    card["knowledge"]["public_history"] = "Twelve years shoeing army horses."
    card["psychology"]["drive"]["essence"] = "Be indispensable to someone"
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mira", json.dumps(card), "{}", time.time(), "char_derive"))

    seen = {}

    def capture(role, system, user, **kwargs):
        seen.update(json.loads(user))
        return json.dumps({"initial_outfit": {"wearing": ["a leather apron"]}})

    monkeypatch.setattr(importers, "chat_complete", capture)
    importers.fill_appearance(
        "character", char_id, "she has just come off a shift",
        draft={"appearance": {"summary": "UNSAVED"}})

    sent = seen["card"]
    assert sent["competence"]["abilities"][0]["name"] == "farrier"
    assert "shoeing army horses" in sent["knowledge"]["public_history"]
    assert sent["psychology"]["drive"]["essence"] == "Be indispensable to someone"
    assert sent["identity"]["name"] == "Mira"
    assert seen["author_draft"]["appearance"]["summary"] == "UNSAVED"


def test_the_director_is_told_damage_lands_on_both_and_heals_differently():
    """A slash across the chest cuts the coat and the chest. The two are not
    the same kind of fact: a cut coat stays cut until mended, a wound heals.
    Neither may be written into the body's stable appearance."""
    from prompts import DEFAULT_PROMPTS

    prompt = DEFAULT_PROMPTS["director_resolve"]
    assert "A BLOW LANDS ON BOTH" in prompt
    assert "conditions" in prompt
    assert "STAYS cut until" in prompt
    assert "heals with time" in prompt
    assert "Never write an injury into a body's stable appearance" in prompt
    assert "If the region was bare, mark only the body" in prompt


def test_the_director_is_told_a_garments_condition_belongs_to_the_garment():
    from prompts import DEFAULT_PROMPTS

    prompt = DEFAULT_PROMPTS["director_resolve"]
    assert "WHAT HAPPENS TO A GARMENT BELONGS TO THE GARMENT" in prompt
    assert "conditions:{garment_name:" in prompt
    assert "Being damaged is not being removed" in prompt


def test_the_director_is_told_undressing_is_a_sequence():
    """The commit path clamps this either way. The prompt is what stops the
    Director WRITING the instant undress -- clamped state under prose that
    already said she was bare is a worse failure than the original."""
    from prompts import DEFAULT_PROMPTS

    prompt = DEFAULT_PROMPTS["director_resolve"]
    assert "UNDRESSING IS A SEQUENCE" in prompt
    assert "worn -> loosened -> open -> removed" in prompt
    assert "STILL BEING WORN" in prompt


class TestOneCharactersAliasIsAnothersName:
    """Found by driving the pipeline by hand. `_heal_attire_identity_keys`
    folds every scene key a character answers to onto their display name --
    which is right, and was collapsing two DIFFERENT people whenever one
    character's alias was another's actual name. That is common in fiction: a
    nickname, a family name, a title.

    Measured: a character named Yuki, and a second whose aliases include
    "Yuki". Yuki's wardrobe was folded onto the other woman -- who was wearing
    nothing and acquired a yukata -- and Yuki's own record ceased to exist.
    """

    def _cast(self):
        return [
            {"id": 1, "name": "Yuki",
             "sheet": json.dumps({"identity": {"name": "Yuki", "aliases": []}})},
            {"id": 2, "name": "Hana",
             "sheet": json.dumps({"identity": {"name": "Hana",
                                               "aliases": ["Yuki"]}})},
        ]

    def test_each_body_keeps_its_own_clothes(self):
        import commit

        scene = {"attire": {
            "Yuki": {"wearing": ["a plain yukata"], "state": []},
            "Hana": {"wearing": ["nothing at all"], "state": []}}}
        canonical = commit._heal_attire_identity_keys(scene, self._cast())
        assert scene["attire"]["Yuki"]["wearing"] == ["a plain yukata"]
        assert scene["attire"]["Hana"]["wearing"] == ["nothing at all"]

    def test_a_registered_name_outranks_somebody_elses_alias_for_it(self):
        import commit

        canonical = commit._heal_attire_identity_keys({}, self._cast())
        assert canonical("Yuki") == "Yuki"
        assert canonical("Hana") == "Hana"

    def test_the_case_the_healer_exists_for_still_heals(self):
        """Live failure it was written against (Elevator Adventure branch 41):
        Dr. Moon held two records, one under her uid with all her clothes and
        one under her name with none, so she rendered as wearing nothing while
        her clothing state still read "lab coat ripped at the hem"."""
        import commit

        cast = [{"id": 1, "name": "Dr. Moon", "sheet": json.dumps(
            {"identity": {"name": "Dr. Moon", "uid": "char_f0ef",
                          "aliases": ["Moon"]}})}]
        scene = {"attire": {
            "char_f0ef": {"wearing": ["a lab coat"], "state": ["ripped hem"]},
            "Dr. Moon": {"wearing": [], "state": []}}}
        commit._heal_attire_identity_keys(scene, cast)
        assert list(scene["attire"]) == ["Dr. Moon"]
        assert scene["attire"]["Dr. Moon"]["wearing"] == ["a lab coat"]


class TestAGarmentThatChangesHands:
    """Found by driving the pipeline by hand. "She takes off her coat and
    drapes it over his shoulders" is an ordinary beat: the coat leaves one body
    and arrives on another in the same breath. It was being minted as an object
    on the floor as well, so two coats existed -- one on his shoulders, one at
    their feet."""

    def _loop(self, bodies, wanted):
        """The commit path's attire reconciliation, in miniature."""
        shed, gained = [], set()
        after_all = {}
        for name, worn in bodies.items():
            before = attire.normalize_regions({"wearing": worn})
            after = attire.apply_flat_change(before, wanted[name], decisive=True)
            after_all[name] = after
            had = {g["name"].casefold()
                   for entry in before.values()
                   for g in (entry.get("garments") or [])
                   if g.get("state") != "removed"}
            for entry in after.values():
                for g in entry.get("garments") or []:
                    if g.get("state") != "removed" and g["name"].casefold() not in had:
                        gained.add(g["name"].casefold())
            for _region, garment in attire.newly_removed(before, after):
                shed.append((name, garment, ""))
        return [s for s in shed if s[1].casefold() not in gained], after_all

    def test_a_handover_leaves_nothing_on_the_floor(self):
        minted, after = self._loop(
            {"Mira": ["a charcoal coat", "a linen shirt"], "Corin": ["a thin tunic"]},
            {"Mira": ["a linen shirt"], "Corin": ["a thin tunic", "a charcoal coat"]})
        assert minted == []
        assert "a charcoal coat" in attire.flat_wearing(after["Corin"])
        assert "a charcoal coat" not in attire.flat_wearing(after["Mira"])

    def test_a_garment_simply_dropped_still_lands(self):
        minted, _ = self._loop(
            {"Mira": ["a charcoal coat", "a linen shirt"]},
            {"Mira": ["a linen shirt"]})
        assert [m[1] for m in minted] == ["a charcoal coat"]

    def test_two_people_in_the_same_kind_of_cloak_are_not_confused(self):
        """The false negative worth avoiding: an object vanishing is worse
        than one duplicating. Only a garment that ARRIVES on someone this beat
        counts as handed over -- a cloak the other guard was already wearing
        does not."""
        minted, _ = self._loop(
            {"GuardA": ["a wool cloak"], "GuardB": ["a wool cloak"]},
            {"GuardA": [], "GuardB": ["a wool cloak"]})
        assert [m[1] for m in minted] == ["a wool cloak"]
        assert minted[0][0] == "GuardA"


class TestAnOffSchemaDiffIsReadNotDiscarded:
    """`StateDiff.attire` had an untyped inner dict, so a shape the commit loop
    did not recognise validated cleanly and then changed nothing. Two of the
    six attire diffs in the measured story were silent no-ops, and one of them
    was the linen shift the prose had been describing since beat 0.

    Every fixture here is verbatim from that story.
    """

    def _read(self, diff, worn, entry=None):
        from commit import interpret_attire_notes
        return interpret_attire_notes(
            attire.coerce_diff_shape(diff), worn,
            entry if entry is not None else {"wearing": list(worn), "state": []})

    def test_a_note_naming_a_worn_garment_lands_on_that_garment(self):
        out = self._read({"robe": "sheer, parted"},
                         ["sheer obsidian silk robe that parts with every movement"])

        assert out["conditions"] == {
            "sheer obsidian silk robe that parts with every movement":
                "sheer, parted"}

    def test_a_note_naming_an_unworn_garment_dresses_the_body_in_it(self):
        """The reading that keeps the detail. The alternative on record is
        throwing it away, which is what produced a narrator describing a shift
        and a pair of shorts on the same body in the same paragraph."""
        out = self._read(
            {"shift": "linen shift, hem rucked up where her hand slipped beneath"},
            ["lightweight travel jacket", "travel shorts"])

        assert out["add"] == ["linen shift"]
        assert "hem rucked up" in out["conditions"]["linen shift"]

    def test_clothing_undisturbed_changes_nothing(self):
        entry = {"wearing": ["travel shorts"], "state": []}
        out = self._read({"clothing": "undisturbed"}, ["travel shorts"], entry)

        assert not out.get("add") and not out.get("conditions")
        assert entry["state"] == []

    def test_a_note_about_the_whole_outfit_is_kept_as_prose(self):
        entry = {"wearing": ["travel shorts"], "state": []}
        self._read({"outfit": "rain-soaked through"}, ["travel shorts"], entry)

        assert "rain-soaked through" in entry["state"]

    def test_a_garment_keyed_state_dict_is_read_as_a_condition(self):
        out = self._read(
            {"state": {"robe": "parted more open, falling off one shoulder"}},
            ["sheer obsidian silk robe"])

        assert out["conditions"] == {
            "robe": "parted more open, falling off one shoulder"}

    def test_a_shorthand_condition_handle_reaches_the_right_garment(self):
        """Resolution happens where the wardrobe is: `apply_flat_change` is
        what turns "robe" into the one robe on the body."""
        worn = ["sheer obsidian silk robe that parts with every movement"]
        regions = attire.normalize_regions({"wearing": worn})
        out = attire.apply_flat_change(
            regions, worn, conditions={"robe": "falling off one shoulder"})

        assert attire.condition_of(out, worn[0]) == "falling off one shoulder"

    def test_a_recognised_diff_passes_through_untouched(self):
        out = self._read({"remove": ["sash"], "add": ["cloak"]}, ["sash"])

        assert out["remove"] == ["sash"] and out["add"] == ["cloak"]


class TestAuthoredRegionsSurviveTheOpeningTurn:
    """`AttireState` declared only `wearing` and `state`, so the validation
    round-trip stripped `regions` -- and the commit loop's whole-outfit branch
    read past it too. Every body in every story lost its garment descriptions
    and its `beneath` text on beat 0."""

    def test_the_schema_keeps_them(self):
        from schemas import AttireState, _dump
        regions = {"torso": {"garments": [{"name": "robe",
                                           "description": "black silk"}],
                             "beneath": "warm skin"}}
        out = _dump(AttireState(**{"wearing": ["robe"], "regions": regions}))

        assert out["regions"]["torso"]["beneath"] == "warm skin"

    def test_the_diff_shape_carries_them_to_commit(self):
        regions = {"torso": {"garments": [{"name": "robe",
                                           "description": "black silk"}]}}
        out = attire.coerce_diff_shape({"wearing": ["robe"], "regions": regions})

        assert out["regions"] == regions


# --- the actor is not the target ---------------------------------------------

class TestDecisiveAttributionDoesNotUndressTheActor:
    """Reported: "an NPC does a motion that would pull off clothes in one
    motion and it only changes the state to loosened."

    Detection was never the problem -- "in one motion" is in `_DECISIVE`, and
    `_beat_voices` reads every character's declared action. ATTRIBUTION was.
    "Corin strips her clothes off in one motion" names no garment the wardrobe
    knows ("clothes" is not a garment), so it fell through to the name rule,
    found exactly one name, and marked CORIN decisive. The body actually losing
    the shift was not flagged, so `advance` clamped it to one rung.

    AGENTS.md states the rule this broke outright: "the ACTOR is not the
    target". A non-reflexive third-person possessive is the tell that the
    sentence acts on somebody else.
    """

    WARDROBE = {"Mira": ["linen shift"], "Corin": ["leather jerkin"]}

    def test_stripping_someone_else_flags_them_not_the_actor(self):
        hits = attire.decisive_targets(
            "", ["Corin strips her clothes off in one motion."],
            self.WARDROBE, player_name="Mira")
        assert hits == {"Mira"}, "the person losing the clothes is decisive"

    def test_an_actor_undressing_themselves_is_still_the_actor(self):
        """The fix must not invert the rule it repairs."""
        hits = attire.decisive_targets(
            "", ["Corin strips off in one motion."],
            self.WARDROBE, player_name="Mira")
        assert hits == {"Corin"}

    def test_reflexive_keeps_the_actor(self):
        hits = attire.decisive_targets(
            "", ["Corin tears herself free of the jerkin in one motion."],
            self.WARDROBE, player_name="Mira")
        assert hits == {"Corin"}

    def test_a_named_garment_still_decides_first(self):
        """Garment attribution outranks everything and must be untouched."""
        hits = attire.decisive_targets(
            "", ["Corin pulls the linen shift off in one motion."],
            self.WARDROBE, player_name="Mira")
        assert hits == {"Mira"}

    def test_ambiguity_undresses_nobody_rather_than_guessing(self):
        """With more than one candidate the answer is no one: undressing the
        WRONG person quickly is a worse error than the right one slowly."""
        hits = attire.decisive_targets(
            "", ["Corin strips her clothes off in one motion."],
            {"Mira": ["shift"], "Corin": ["jerkin"], "Ada": ["robe"]},
            player_name="Mira")
        assert hits == set()

    def test_the_clamp_is_what_this_controls(self):
        """End to end: the flags are only worth anything because `advance`
        reads them. A resolved removal lands by default (the inverted
        clamp); `process` holds it one rung; `decisive` overrides even
        that."""
        previous = {"torso": {"garments": [
            {"name": "linen shift", "state": "worn"}]}}
        proposed = {"torso": {"garments": [
            {"name": "linen shift", "state": "removed"}]}}
        landed = attire.advance(previous, proposed, decisive=False)
        held = attire.advance(previous, proposed, decisive=False,
                              process=True)
        lifted = attire.advance(previous, proposed, decisive=True,
                                process=True)
        assert landed["torso"]["garments"][0]["state"] == "removed"
        assert held["torso"]["garments"][0]["state"] == "loosened"
        assert lifted["torso"]["garments"][0]["state"] == "removed"
