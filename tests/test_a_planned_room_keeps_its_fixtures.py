"""A room's description promises things a body can touch; the plan keeps them.

A room record carries an optional `anchors` map -- the named features a body
can stand at, work at, set something on, take cover behind or lay a hand
against. `spatial_contacts` resolves a contact target against it, a charter
post's `anchor` names an id from it, and `spatial_fov`, `comfort`,
`place_purpose` and the light field all read it. Nothing asked a PLAN for one,
and `structure.plant_structure` normalizes planned rooms through a field
allowlist that dropped them if a plan sent them anyway -- so the only anchors
any story ever had were ones the Director wrote mid-beat.

Measured, two_lives v7 (2026-09-19), turns 5, 7 and 9: `mill_race` was planned
as "The sluice channel and wet timber shroud housing the great undershot
waterwheel" and planted as `{name, desc, adjacent, region}`. Emory Vane, a
millwright, pressed a hand to the apron timber and reached for the wheel
shroud across several beats, and the contact hand refused every row --
"Targets 'shroud' and 'apron timber' do not exist as established world keys or
fixtures/anchors in the mill_race payload". It was right: they did not. The
room's furniture was stored twice, as English in `desc` and as structure
nowhere, so a body could not touch the thing the room was made of.

The same allowlist had already swallowed the plan's MEASUREMENTS once (F47,
five play runs), which is why `planned_geometry` exists beside this.
"""

from __future__ import annotations

from world.structure import planned_anchors

SHROUD = {"desc": "the wet timber shroud over the wheel"}
APRON = {"desc": "the apron timbers along the sluice"}


class TestTheNormalizerKeepsARecordAndRefusesAGuess:
    def test_a_furnished_room_carries_its_anchors(self):
        out = planned_anchors({"name": "Mill Race",
                               "anchors": {"shroud": SHROUD, "apron": APRON}})
        assert out == {"anchors": {"shroud": SHROUD, "apron": APRON}}

    def test_a_room_that_names_none_says_nothing(self):
        """Silence stays silence -- an always-present {} would ride out on
        every room and read as an erasure one layer out
        (`spatial_merge._merge_anchor_fields`)."""
        assert planned_anchors({"name": "Quay"}) == {}
        assert planned_anchors({"anchors": {}}) == {}
        assert planned_anchors({"anchors": "a wheel"}) == {}
        assert planned_anchors(None) == {}

    def test_an_anchor_that_is_not_a_record_is_dropped(self):
        """A bare string is a description with nowhere to put it, and an
        anchor is a record. Dropped rather than guessed into one."""
        out = planned_anchors({"anchors": {"shroud": SHROUD,
                                          "wheel": "the great wheel",
                                          "": SHROUD}})
        assert out == {"anchors": {"shroud": SHROUD}}

    def test_the_plans_own_map_is_not_handed_out_by_reference(self):
        """A planted room must not alias the draft the Room is still editing."""
        plan = {"anchors": {"shroud": SHROUD}}
        out = planned_anchors(plan)
        out["anchors"]["shroud"]["desc"] = "changed"
        assert plan["anchors"]["shroud"]["desc"] == SHROUD["desc"]


class TestTheFixturesReachTheSceneTheOpeningComposes:
    def test_a_planted_room_keeps_them_and_the_skeleton_hands_them_over(
            self, temp_db):
        """Both ends of the rail: `plant_structure` stores them and
        `skeleton_rooms` reads them back in ordinary scene shape, which is
        what the opening turn composes its rooms from."""
        import time

        from world.structure import plant_structure, skeleton_rooms

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("T", "", time.time()))
        plant_structure(cid, {"key": "aldermill", "max_planned": 8},
                        {"mill_race": {"name": "Mill Race & Wheel",
                                       "purpose": "work",
                                       "anchors": {"shroud": SHROUD,
                                                   "apron": APRON}},
                         "mill_house": {"name": "The Mill"}})
        rooms = skeleton_rooms(cid, "aldermill")["rooms"]
        assert set(rooms["mill_race"]["anchors"]) == {"shroud", "apron"}
        assert rooms["mill_race"]["anchors"]["apron"]["desc"] == APRON["desc"]
        # A room that named none does not acquire an empty map.
        assert "anchors" not in rooms["mill_house"]


class TestTheRoomIsToldTheFieldExists:
    def test_the_draft_tool_names_anchors_in_the_room_shape(self):
        """The half that made this unroutable rather than merely unused: the
        charter contract already told the planner a post may carry `anchor`,
        "the id of one of its place's fixtures ... as one of that room's
        anchors" -- referencing a map nothing ever asked it to draft."""
        from story.room_tools import TOOLS

        tool = next(t for t in TOOLS if t["name"] == "draft_location")
        assert "anchors" in tool["description"]
        assert "fixture" in tool["description"].casefold()


class TestTheFixtureReachesTheHandThatResolvesATarget:
    """The rest of the rail already existed and was starved at the source.
    `director_fanout._anchor_names` builds the contact hand's whole fixture
    vocabulary from `room["anchors"]` -- its own note says it is "empty when
    nothing places anybody, which is the payload the hand had before" -- and
    `spatial_contacts` resolves a target against it. So a plan that names a
    fixture is what lets a hand encode a body touching it."""

    def test_a_planted_anchor_is_in_the_contact_payload(self, temp_db):
        import time

        from agents.director import _anchor_names
        from world.structure import plant_structure, skeleton_rooms

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("T", "", time.time()))
        plant_structure(cid, {"key": "aldermill", "max_planned": 4},
                        {"mill_race": {"name": "Mill Race & Wheel",
                                       "anchors": {"apron": APRON}}})
        sc = skeleton_rooms(cid, "aldermill")
        sc["positions"] = {"Emory Vane": "mill_race"}
        sc["entities"] = {}
        assert _anchor_names(sc, ["Emory Vane"])["mill_race"]["apron"] \
            == APRON["desc"]


class TestTheEngineTellsTheRoomWhenARoomIsBare:
    """Prose in a tool description did not carry this. The `draft_location`
    contract was taught the field and a fresh design pass came back with
    0 of 19 rooms furnished (design probe, 2026-09-19). The design note's own
    rule is that "the check is the real one" -- the Room believes the engine,
    so the review says it.

    A NOTE, NEVER AN ERROR: some rooms honestly hold nothing a hand would
    find, and which those are is the Room's judgment.
    """

    def _draft(self, chat, rooms):
        from story import location_design

        location_design.open_draft(chat, {"wants_history": False})
        location_design.set_skeleton(chat, name="Aldermill",
                                     structure={"key": "aldermill"},
                                     rooms=rooms)
        location_design.set_charter(chat, {"key": "mill"})
        return location_design.check(chat)

    def test_a_bare_room_is_named_in_the_notes(self, temp_db):
        out = self._draft(temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES('T','',0)", ()),
            {"mill_race": {"name": "Mill Race"},
             "wheel_chamber": {"name": "Wheel Chamber",
                               "anchors": {"shroud": SHROUD}}})
        note = " ".join(out["notes"])
        assert "mill_race" in note
        assert "wheel_chamber" not in note

    def test_a_furnished_plan_draws_no_note(self, temp_db):
        out = self._draft(temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES('T','',0)", ()),
            {"mill_race": {"name": "Mill Race",
                           "anchors": {"apron": APRON}}})
        assert out["notes"] == []

    def test_a_bare_room_still_closes(self, temp_db):
        """It would have launched before and it launches now: the note is
        information, not a gate."""
        out = self._draft(temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES('T','',0)", ()),
            {"mill_race": {"name": "Mill Race"}})
        assert out["notes"] and not [e for e in out["errors"] if "fixture" in e]


class TestTheDraftCallItselfSaysWhichRoomsAreBare:
    """Third attempt at one class, on the one channel the Room cannot skip.

    Measured twice: the `draft_location` contract was taught `anchors` and a
    design came back 0 of 19 furnished (2026-09-19); `review_location` was
    taught to report bare rooms and the next design came back 0 of 12
    (2026-09-20). The review is ADVISORY -- that pass drafted 12 rooms and 4
    charters in 9 calls over 4 steps and may never have asked -- so the report
    belongs in the answer to the call that drafts them, which the Room reads
    every time by construction.
    """

    def test_the_answer_names_the_bare_rooms(self, temp_db):
        from story import location_design

        chat = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                          "VALUES('T','',0)", ())
        location_design.open_draft(chat, {"wants_history": False})
        out = location_design.set_skeleton(
            chat, name="Aldermill", structure={"key": "aldermill"},
            rooms={"mill_race": {"name": "Mill Race"},
                   "wheel_chamber": {"name": "Wheel Chamber",
                                     "anchors": {"shroud": SHROUD}}})
        assert out["rooms_with_no_fixtures"] == ["mill_race"]

    def test_a_furnished_draft_is_not_nagged(self, temp_db):
        from story import location_design

        chat = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                          "VALUES('T','',0)", ())
        location_design.open_draft(chat, {"wants_history": False})
        out = location_design.set_skeleton(
            chat, name="Aldermill", structure={"key": "aldermill"},
            rooms={"mill_race": {"name": "Mill Race",
                                 "anchors": {"apron": APRON}}})
        assert "rooms_with_no_fixtures" not in out

    def test_it_reports_the_whole_plan_not_just_this_call(self, temp_db):
        """Rooms MERGE across calls, so a room left bare two calls ago is
        still bare -- the answer has to say so or the Room never hears about
        it again."""
        from story import location_design

        chat = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                          "VALUES('T','',0)", ())
        location_design.open_draft(chat, {"wants_history": False})
        location_design.set_skeleton(chat, name="Aldermill",
                                     structure={"key": "aldermill"},
                                     rooms={"mill_race": {"name": "Mill Race"}})
        out = location_design.set_skeleton(
            chat, rooms={"forge": {"name": "Forge",
                                   "anchors": {"anvil": {"desc": "an anvil"}}}})
        assert out["rooms_with_no_fixtures"] == ["mill_race"]
