"""A thing examined tells you what it is like.

Measured on chat 152, turns 4337-4338 (2026-09-21). The Doctor stood at the
TARDIS console with both hands on a panel, "checking what the scar and the
landing cost her", for two beats -- and was told nothing. Read against each
other, the stages showed three gaps, none of them in the stage the symptom
appeared in:

  * the console was a room ANCHOR with a description and no record, so there
    was no `state` to read;
  * both console rows were categorised `contacts, attention`, so the objects
    hand -- whose sheet has required since the detail clause that "a detail a
    body perceives on a thing is a fact the thing must carry" -- never
    received a work item and `entities` wrote `{}` twice;
  * `_visible_things` renders a thing by its description and uses `state`
    only as a placement key, so a written reading would have reached no mind.

Not a defect in something built, but a feature the engine did not have (the
owner, 2026-09-21: "not so much a bug but a missing feature"): nothing had
ever carried a thing's condition or readings from its record to the body
reading it. The owner's 2026-09-19 ruling still sets the bar -- a thing
examined closely tells you what it is like. These tests hold the delivery
half -- who is told, and what -- and pin the prompt clauses that make the
objects hand write the answer, grounded in what the thing is, where it is and
what has happened to it.

Admission is the firewall's ordinary work: the reading crosses to the one
body with a channel to it (hands on it, or standing at its station with light
to see by). A bystander watching someone else read a panel gets the act
through `act_percept`, never the numbers, and nothing here changes that.
"""

from __future__ import annotations

from pathlib import Path

from agents import composer
from agents.perception import _things_read_by

ROOT = Path(__file__).resolve().parents[1]


def _scene(*, light="lit", contacts=(), console_state=None):
    return {
        "rooms": {"bridge": {"name": "Bridge", "light": light,
                             "anchors": {"helm": {"desc": "the helm",
                                                  "cell": [2, 2]}}}},
        "positions": {"Reya": "bridge", "Bram": "bridge",
                      "helm_console": "bridge", "hull_plate": "bridge",
                      "lantern": "hold"},
        "stations": {"Reya": {"at": "helm", "cell": [3, 2]},
                     "Bram": {"at": None, "cell": [0, 0]},
                     "helm_console": {"at": "helm"}},
        "entities": {
            "helm_console": {
                "name": "helm console", "kind": "fixture",
                "aliases": ["the console"],
                "state": console_state if console_state is not None else {
                    "hatch": "open",
                    "power": "reserve cells at a third",
                    "drive": {"phase": "cold", "fault": "coolant line scored"},
                    "alarms": ["hull breach aft"],
                }},
            "hull_plate": {"name": "hull plate", "kind": "object",
                           "state": {"scoring": "a long gouge, bright at the edges"}},
            "lantern": {"name": "lantern", "kind": "object",
                        "state": {"fuel": "half"}},
            "Reya": {"name": "Reya", "kind": "person"},
            "Bram": {"name": "Bram", "kind": "person",
                     "state": {"posture": "crouched"}},
        },
        "contacts": list(contacts),
    }


BODIES = ["Reya", "Bram"]


def _view(sc, who):
    rows = _things_read_by(sc, who, "bridge", bodies=BODIES)
    percepts = composer.thing_reading_percepts([
        (entity.get("name"), composer.thing_reading_text(entity.get("state")),
         eid, channel)
        for eid, entity, channel in rows])
    return composer.render_view(percepts, mode="character").text


class TestWhoIsTold:

    def test_hands_on_a_thing_read_its_record(self):
        sc = _scene(contacts=[{"actor": "Bram", "actor_part": "palm",
                               "target": "hull_plate", "manner": "press"}])
        assert _view(sc, "Bram") == (
            "Under your hands, the hull plate: scoring: a long gouge, "
            "bright at the edges.")

    def test_standing_at_its_station_reads_it_by_sight(self):
        assert _view(_scene(), "Reya") == (
            "The helm console shows: power: reserve cells at a third; "
            "drive: phase cold, fault coolant line scored; "
            "alarms: hull breach aft.")

    def test_a_bystander_across_the_room_is_told_nothing(self):
        """Bram is in the room, not at the helm, not touching it."""
        assert _view(_scene(), "Bram") == ""

    def test_watching_someone_else_read_a_panel_is_not_reading_it(self):
        """The contact is Bram's; Reya only sees it. She keeps her own
        station's reading and gets nothing of the plate."""
        sc = _scene(contacts=[{"actor": "Bram", "actor_part": "palm",
                               "target": "hull_plate", "manner": "press"}])
        assert "hull plate" not in _view(sc, "Reya")

    def test_a_contact_target_resolves_by_alias(self):
        sc = _scene(contacts=[{"actor": "Bram", "actor_part": "hands",
                               "target": "the console", "manner": "press"}])
        text = _view(sc, "Bram")
        assert text.startswith("Under your hands, the helm console:")
        assert "reserve cells" in text

    def test_in_the_dark_a_shared_station_reads_nothing(self):
        assert _view(_scene(light="dark"), "Reya") == ""

    def test_a_body_is_never_a_thing_to_be_read(self):
        sc = _scene(contacts=[{"actor": "Reya", "actor_part": "hand",
                               "target": "Bram", "manner": "hold"}])
        assert "crouched" not in _view(sc, "Reya")

    def test_a_thing_in_another_room_is_not_read(self):
        sc = _scene(contacts=[{"actor": "Bram", "actor_part": "hand",
                               "target": "lantern", "manner": "hold"}])
        assert "fuel" not in _view(sc, "Bram")


class TestWhatIsTold:

    def test_keys_another_renderer_owns_are_not_repeated(self):
        """`hatch` renders through the doorway the engine derives from it."""
        assert "hatch" not in _view(_scene(), "Reya")

    def test_a_silent_record_says_nothing(self):
        assert _view(_scene(console_state={}), "Reya") == ""
        assert _view(_scene(console_state={"hatch": "closed"}), "Reya") == ""

    def test_the_reading_is_the_record_not_a_word_list(self):
        """Keys are the hand's: whatever it wrote comes back, humanised."""
        text = composer.thing_reading_text(
            {"cloister_bell": "silent since landing", "artron_reserve": 0.4,
             "scanner": {"last_image": "a scar in the vortex"}, "sealed": True})
        assert text == ("cloister bell: silent since landing; artron reserve: 0.4; "
                        "scanner: last image a scar in the vortex; sealed: yes")

    def test_a_changed_reading_is_a_different_percept(self):
        before = composer.thing_reading_percepts(
            [("panel", "power: full", "p1", "sight")])[0]
        after = composer.thing_reading_percepts(
            [("panel", "power: failing", "p1", "sight")])[0]
        same = composer.thing_reading_percepts(
            [("panel", "power: full", "p1", "sight")])[0]
        assert before.dedupe_key == same.dedupe_key != after.dedupe_key


class TestTheSheetsAskForTheRecord:
    """The two clauses that make the objects hand WRITE the answer the view
    now delivers. Pinned by a distinctive phrase in each pack, so a rewrite
    that drops the case fails here rather than fifty beats into a story."""

    PACKS = ROOT / "language_packs"

    def _leaf(self, pack, rel):
        return (self.PACKS / pack / "cards" / "system_prompts" / rel).read_text(
            encoding="utf-8")

    def test_the_interpret_sheet_routes_a_read_to_entities(self):
        en = self._leaf("en", "causal_director.txt")
        assert "A READ OF IT ANSWERS FROM IT" in en
        ja = self._leaf("ja", "causal_director.txt")
        assert "物を読む行為はその物から答えを得ます" in ja

    def test_the_objects_sheet_writes_harm_and_readings_as_state(self):
        rel = "specialists/objects/chunks/entities.txt"
        en = self._leaf("en", rel)
        assert "WHAT A THING SHOWS OF ITSELF IS ITS state" in en
        assert "AUTHOR IT FROM THREE THINGS AND NOTHING ELSE" in en
        ja = self._leaf("ja", rel)
        assert "受けた損傷もまた state" in ja
        assert "次の三つからのみ行い" in ja

    def test_the_establish_sheet_mints_a_vehicle_with_a_state(self):
        rel = "prompts/director_establish.txt"
        assert "is minted WITH a `state`" in self._leaf("en", rel)
        assert "`state` を伴って鋳造" in self._leaf("ja", rel)
