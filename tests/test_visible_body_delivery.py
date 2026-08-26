"""The body a card describes, delivered to whoever can see it.

`character_appearance` returned `embodiment.visible.summary` and NOTHING else,
so four fields every generated card fills -- `build`, `face`, `hair`, `eyes` --
reached no view, no narrator and no memory. An author filled the field they
were offered and the story could not see it.

The fields stay exactly where they were. `normalize_character_data` PROJECTS
the located three into the region shape on the way in, and delivery is gated by
the clothing ledger on the mirror of the `beneath` rule: what is UNDER clothing
is spelled out only once something comes off, and what a body shows OF ITSELF
is delivered until something goes on. `build` sits outside that gate on
purpose -- it is not located, so nothing worn can cover it.

Everything here is stated in the engine's own vocabulary: a region, a covering,
a described surface. No test knows what any particular garment is.
"""

from __future__ import annotations

import json
import time

from agents import composer
from agents.perception import _body_descriptions, _composer_standing_percepts
from story import attire
from story.character_schema import (
    character_card_warnings,
    character_visible_body,
    default_character_data,
    normalize_character_data,
)
from story.scene import visible_body_text

BUILD = "rangy and heavy-shouldered"
FACE = "a broken nose set crooked"
HAIR = "a grey braid pinned up"
EYES = "pale grey"


def _card(name="Subject", **visible):
    sheet = default_character_data(name)
    sheet["embodiment"]["visible"].update(
        {"summary": "A tall figure.", "build": BUILD, "face": FACE,
         "hair": HAIR, "eyes": EYES, **visible})
    return sheet


def _regions(*garments):
    return attire.normalize_regions(
        {"regions": {"head": {"garments": list(garments)}}})


def _worn(**over):
    return {"name": "a covering", "state": "worn", **over}


class TestTheCardProjectsItsLocatedFields:
    """A projection, not a decision: the card keeps the fields it always
    offered and the engine restates them where the gate can read them."""

    def test_the_located_fields_land_in_the_region_shape(self):
        visible = normalize_character_data(_card())["embodiment"]["visible"]

        assert visible["regions"]["head"]["visible_zones"] == {
            "face": FACE, "hair": HAIR, "eyes": EYES}

    def test_the_fields_themselves_are_untouched(self):
        """No authoring surface moved. Nothing has to be re-authored."""
        visible = normalize_character_data(_card())["embodiment"]["visible"]

        assert (visible["face"], visible["hair"], visible["eyes"]) == (
            FACE, HAIR, EYES)
        assert visible["build"] == BUILD

    def test_it_is_idempotent_through_storage(self):
        once = normalize_character_data(_card())
        twice = normalize_character_data(json.loads(json.dumps(once)))

        assert twice["embodiment"]["visible"] == once["embodiment"]["visible"]

    def test_the_fields_are_the_source_of_truth(self):
        """The projection is rebuilt from the fields rather than merged with
        whatever was in the derived shape, so a stale region record cannot
        outlive the field it came from."""
        sheet = _card(hair="")
        sheet["embodiment"]["visible"]["regions"] = {
            "head": {"visible_zones": {"hair": "STALE"}}}

        zones = normalize_character_data(sheet)[
            "embodiment"]["visible"]["regions"]["head"]["visible_zones"]

        assert "hair" not in zones
        assert zones["face"] == FACE

    def test_a_card_that_describes_nothing_projects_nothing(self):
        sheet = _card(build="", face="", hair="", eyes="")

        assert normalize_character_data(sheet)[
            "embodiment"]["visible"]["regions"] == {}
        assert character_visible_body(sheet) == {"build": "", "regions": {}}

    def test_the_accessor_splits_located_from_unlocated(self):
        """`build` is a property of the whole body with no place on it, so it
        is not in the region half and nothing worn can reach it."""
        body = character_visible_body(_card())

        assert body["build"] == BUILD
        assert body["regions"] == {"head": {
            "face": FACE, "hair": HAIR, "eyes": EYES}}


class TestTheFieldThatIsStillUnread:
    """`distinctive_features` is preserved, not folded and not projected: it
    has a live reader in `_prose_names_a_part`, archives round-trip it, and
    nothing delivers it. The warning that named all five now names the one."""

    def test_it_survives_normalization_verbatim(self):
        sheet = _card()
        sheet["embodiment"]["visible"]["distinctive_features"] = ["a scar"]

        assert normalize_character_data(sheet)[
            "embodiment"]["visible"]["distinctive_features"] == ["a scar"]

    def test_it_is_not_projected_into_the_delivered_shape(self):
        sheet = _card()
        sheet["embodiment"]["visible"]["distinctive_features"] = ["a scar"]

        zones = character_visible_body(sheet)["regions"]["head"]

        assert "a scar" not in json.dumps(zones)

    def test_it_is_the_field_the_author_is_told_about(self):
        sheet = _card()
        sheet["embodiment"]["visible"]["distinctive_features"] = ["a scar"]
        warnings = [w for w in character_card_warnings(sheet)
                    if "distinctive_features" in w]

        assert warnings
        # And the four that are delivered no longer ask to be moved.
        assert not [w for w in character_card_warnings(_card())
                    if "no view" in w]


class TestClothingDecidesWhatOfTheBodyShows:
    """The gate, in the vocabulary the ledger already has. Nothing here knows
    what any particular covering is."""

    DESCRIBED = {"head": {"face": FACE, "hair": HAIR, "eyes": EYES}}

    def test_an_uncovered_region_delivers_its_descriptions(self):
        assert attire.uncovered_zone_text(self.DESCRIBED, {}) == {
            "head": {"face": FACE, "hair": HAIR, "eyes": EYES}}

    def test_a_covering_conceals_them(self):
        assert attire.uncovered_zone_text(
            self.DESCRIBED, _regions(_worn())) == {}

    def test_removing_it_delivers_them_again(self):
        assert attire.uncovered_zone_text(
            self.DESCRIBED, _regions(_worn(state="removed"))) == self.DESCRIBED

    def test_something_displaced_off_the_region_conceals_nothing(self):
        """Still worn, covering nothing here -- the same distinction the
        clothing lines already draw."""
        assert attire.uncovered_zone_text(
            self.DESCRIBED,
            _regions(_worn(covered_zones={"head": []}))) == self.DESCRIBED

    def test_something_merely_worn_at_the_region_conceals_nothing(self):
        assert attire.uncovered_zone_text(
            self.DESCRIBED, _regions(_worn(attaches=True))) == self.DESCRIBED

    def test_a_region_nobody_described_delivers_nothing(self):
        assert attire.uncovered_zone_text({"head": {}}, {}) == {}

    def test_a_zone_the_vocabulary_does_not_know_is_dropped(self):
        assert attire.uncovered_zone_text(
            {"head": {"aura": "unreadable"}}, {}) == {}

    def test_the_clothing_axis_is_untouched(self):
        """The described surfaces are a SECOND axis. `REGION_ZONES` answers
        what a garment can expose, and its answer is read as bareness."""
        assert "head" not in attire.REGION_ZONES
        assert attire.describe(
            attire.normalize_regions({"wearing": ["a hair ribbon"]})) == [
                "head: a hair ribbon [worn at, covers nothing]"]


class TestBuildIsNotLocated:
    def test_it_rides_whatever_the_body_is_wearing(self):
        body = character_visible_body(_card())
        covered = {"attire": {"Subject": {"regions": {
            "head": {"garments": [_worn()]}}}}}

        text = visible_body_text(body, "Subject", covered)

        assert BUILD in text
        assert HAIR not in text

    def test_an_uncovered_body_delivers_both_halves(self):
        text = visible_body_text(
            character_visible_body(_card()), "Subject", {"attire": {}})

        for fact in (BUILD, FACE, HAIR, EYES):
            assert fact in text

    def test_a_card_that_describes_nothing_delivers_nothing(self):
        assert visible_body_text(
            character_visible_body(_card(build="", face="", hair="", eyes="")),
            "Subject", {"attire": {}}) == ""


# --------------------------------------------------------------------------
# Delivery, through the composed view
# --------------------------------------------------------------------------

def _scene(light="normal", attire_ledger=None):
    return {
        "rooms": {"hall": {"name": "Hall", "light": light}},
        "positions": {"Observer": "hall", "Subject": "hall"},
        "entities": {}, "poses": {}, "contacts": [], "contact_actions": [],
        "attire": attire_ledger or {}, "overlays": {}, "scales": {},
        "contained": {},
    }


def _ctx(sheet):
    return type("Ctx", (), {
        "chat": {"id": 1},
        "cast": [{"sheet": json.dumps(sheet), "cstate": "{}"}],
    })()


def _rendered(sc, descriptions, *, recognized=True):
    observer = {"room": "hall", "room_name": "Hall", "room_notes": "",
                "sense_card": None}
    others = [{"name": "Subject", "room": "hall",
               "appearance": "a tall figure", "aliases": [],
               "disguise_known_to": [], "disguise_conceals_identity": False}]
    percepts = _composer_standing_percepts(
        sc, observer, "Observer", others,
        {"Subject": "Subject" if recognized else "the tall figure"},
        {"Observer": ["Subject"] if recognized else []},
        body_descriptions=descriptions)
    return composer.render_view(percepts, mode="character").text


def _covering_ledger():
    return {"Subject": {"regions": {"head": {"garments": [_worn()]}}}}


class TestTheViewDeliversTheBody:
    def test_first_sight_carries_the_whole_body(self):
        sheet = _card()
        sc = _scene()
        text = _rendered(sc, _body_descriptions(_ctx(sheet), sc))

        for fact in (BUILD, FACE, HAIR, EYES):
            assert fact in text, fact

    def test_a_covered_region_is_not_delivered(self):
        sheet = _card()
        sc = _scene(attire_ledger=_covering_ledger())
        text = _rendered(sc, _body_descriptions(_ctx(sheet), sc))

        assert BUILD in text          # not located, so never covered
        for fact in (FACE, HAIR, EYES):
            assert fact not in text, fact

    def test_it_is_delivered_once_the_covering_comes_off(self):
        sheet = _card()
        ledger = _covering_ledger()
        ledger["Subject"]["regions"]["head"]["garments"][0]["state"] = "removed"
        sc = _scene(attire_ledger=ledger)

        text = _rendered(sc, _body_descriptions(_ctx(sheet), sc))

        assert HAIR in text
        assert FACE in text

    def test_a_card_that_describes_nothing_changes_no_view(self):
        sheet = _card(build="", face="", hair="", eyes="")
        sc = _scene()
        descriptions = _body_descriptions(_ctx(sheet), sc)

        assert descriptions == {}
        assert _rendered(sc, descriptions) == _rendered(sc, {})


class TestItSubtracts:
    """Every admission here is a subtraction, and this is the half that
    proves the delivery did not become an expansion."""

    def test_an_observer_who_cannot_see_receives_none_of_it(self):
        """The description rides the sight gate that was already there: below
        full sight there is no appearance percept at all, so there is nowhere
        for a face to arrive.

        The body is still DELIVERED -- it is present, and presence is never
        withheld -- which is what makes this a subtraction of one channel
        rather than a view that happens to be empty."""
        sheet = _card()
        sc = _scene(light="dim")
        text = _rendered(sc, _body_descriptions(_ctx(sheet), sc))

        assert "Subject is close by" in text
        for fact in (BUILD, FACE, HAIR, EYES):
            assert fact not in text, fact

    def test_the_stranger_label_is_cut_from_the_summary_alone(self):
        """A label is what an observer who has NOT earned a name calls a body,
        and it is handed out without asking what that observer can see. So the
        body description must not reach it: an observer holding a silhouette
        cannot be allowed to read a face off the label it was given."""
        labels = composer.observer_display_map(
            _scene(), "Observer",
            [{"name": "Subject", "appearance": "a tall figure", "aliases": [],
              "disguise_known_to": [], "disguise_conceals_identity": False}],
            {"Observer": []})

        assert labels["Subject"] == "the tall figure"
        for fact in (BUILD, FACE, HAIR, EYES):
            assert fact not in labels["Subject"]

    def test_a_body_whose_outward_form_is_not_its_own_delivers_nothing(
            self, monkeypatch):
        """A disguise decides what every observer sees. The card's own face is
        precisely the thing that is not on show, so it is withheld whole."""
        import agents.perception as perception

        sheet = _card()
        sc = _scene()
        monkeypatch.setattr(
            perception, "active_disguises",
            lambda chat_id: {"subject": {"description": "a stooped porter"}})

        assert _body_descriptions(_ctx(sheet), sc) == {}

    def test_a_transformed_body_delivers_nothing_from_its_card(
            self, monkeypatch):
        import agents.perception as perception

        sheet = _card()
        sc = _scene()
        monkeypatch.setattr(
            perception, "active_transformations",
            lambda chat_id: {"subject": {"appearance": "a grey wolf"}})

        assert _body_descriptions(_ctx(sheet), sc) == {}


class TestTheArchiveCarriesTheCard:
    def test_a_round_trip_keeps_the_unread_field_and_the_derived_shape(
            self, temp_db):
        from web import app

        sheet = _card()
        sheet["embodiment"]["visible"]["distinctive_features"] = [
            "a scar through one eyebrow"]
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Archive", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)",
            ("Subject", json.dumps(sheet), "{}", time.time()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))

        imported = app.chat_import({"data": app.chat_export(chat_id)})
        row = temp_db.q(
            "SELECT COALESCE(cc.sheet, ch.sheet) AS sheet FROM chat_chars cc "
            "JOIN characters ch ON ch.id = cc.char_id WHERE cc.chat_id=?",
            (imported["id"],), one=True)
        visible = normalize_character_data(
            json.loads(row["sheet"]))["embodiment"]["visible"]

        assert visible["distinctive_features"] == ["a scar through one eyebrow"]
        assert visible["regions"]["head"]["visible_zones"]["hair"] == HAIR
