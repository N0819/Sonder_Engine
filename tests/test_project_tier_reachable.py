"""The project tier could not be entered from empty.

Projects are the tier between an eternal drive and a completable intention --
what a character is ABOUT right now. They carry the longest single block in the
character prompt, a probation period, a displacement rule, a drift counter, an
appraisal weight equal to the drive itself, and a cap of two. Measured over the
live corpus (`tools/fire_rates.py`):

    has ever held a project      0 of 14 banks

Not "rarely adopted". Never, in either ledger, in any story. And the reason was
a single condition written twice:

    affect.project_boundary      `if not projects: return None`
    agents/character.py          `if isinstance(_preview, dict) and _self.get("projects")`

The prompt names the review beat as the occasion to emit `project_ops` -- "That
beat IS the review this tier owes you ... emit project_ops now" -- and both
gates made the review beat require a project. The one moment a first project
could be adopted was conditional on already having one.

This is §2.1's rule arriving from a new direction. There, a prompt asked models
to prefer a real observation id while the payload made the invented label
easier to reach, and the prompt lost. Here the payload does not merely make the
asked-for thing hard: it withholds the occasion entirely, and no amount of
prompt is going to argue with a key that is never present.

The arrival boundary genuinely needs a project -- it compares the new room
against what a held project names. A task closing and the scene or frame
changing do not, and for a character with nothing standing those are exactly
the moments worth asking: you have just finished something, or you are
somewhere new.
"""

from __future__ import annotations

import inspect

from affect import project_boundary
from agents import character

HELD = [{"id": "p1", "project": "Keep this village alive through the winter",
         "status": "active"}]
MARKER = {"location": "Shrine Clearing", "frame": ""}


def _boundary(projects, **kw):
    args = dict(intentions=[], before_status={}, new_room=None, prev_room=None,
                scene_marker=MARKER, location="Shrine Clearing", frame_id="",
                named_rooms=None)
    args.update(kw)
    return project_boundary(projects, args["intentions"],
                            args["before_status"], args["new_room"],
                            args["prev_room"], args["scene_marker"],
                            args["location"], args["frame_id"],
                            args["named_rooms"])


class TestABoundaryReachesACharacterWithNoProjects:
    def test_the_scene_changing_is_a_boundary(self):
        assert _boundary([], location="Lantern Path")

    def test_the_frame_changing_is_a_boundary(self):
        assert _boundary([], frame_id="frame-2")

    def test_a_task_closing_is_a_boundary(self):
        why = _boundary([], intentions=[{"id": "i3", "status": "satisfied"}],
                        before_status={"i3": "active"})
        assert why and "i3" in why

    def test_none_of_this_changed_for_a_character_who_holds_one(self):
        assert _boundary(HELD, location="Lantern Path")
        assert _boundary(HELD, frame_id="frame-2")

    def test_a_none_project_list_does_not_raise(self):
        assert _boundary(None, location="Lantern Path")


class TestWhatIsStillNotABoundary:
    def test_an_ordinary_beat_in_the_same_place_is_silence(self):
        """The prompt's own line: never because the current room is
        interesting. Opening the gate must not turn every beat into a
        review."""
        assert _boundary([]) is None
        assert _boundary(HELD) is None

    def test_the_first_beat_has_no_marker_and_so_no_boundary(self):
        assert _boundary([], scene_marker=None) is None

    def test_a_task_that_was_already_closed_does_not_re_fire(self):
        assert _boundary([], intentions=[{"id": "i3", "status": "satisfied"}],
                         before_status={"i3": "satisfied"}) is None

    def test_arrival_still_requires_a_project_to_arrive_at(self):
        """It compares the new room against what a held project NAMES, so with
        no projects nothing has been arrived AT. The move itself is still a
        boundary -- via the scene reason -- but it is not the arrival one."""
        why = _boundary([], new_room="lantern_path", prev_room="torii_gate",
                        location="Lantern Path")
        assert why is not None
        assert "points" not in why

    def test_arrival_is_still_named_for_a_character_who_holds_one(self):
        why = _boundary(
            [{"id": "p1", "project": "Keep watch over the Lantern Path",
              "status": "active"}],
            new_room="lantern_path", prev_room="torii_gate",
            location="Lantern Path", named_rooms={"lantern path": "lantern_path"})
        assert why and "p1" in why


class TestThePayloadDeliversIt:
    def test_the_flag_is_no_longer_gated_on_holding_a_project(self):
        src = inspect.getsource(character)
        block = src[src.index('_preview = _interior.get("project_review")'):]
        block = block[:block.index('_self["project_review"]')]
        assert '_self.get("projects")' not in block

    def test_the_flag_is_still_one_beat_only(self):
        """A review that never expires is not a boundary, it is a standing
        instruction -- and the prompt would be telling the character to review
        projects on every beat forever."""
        src = inspect.getsource(character)
        block = src[src.index('_preview = _interior.get("project_review")'):]
        block = block[:block.index('_self["project_review"]')]
        assert "ctx.turn.idx <= int(_preview.get(\"turn\")) + 1" in block


def test_the_engine_still_never_adopts_anything_itself():
    """Detection is a fact; what the review MEANS stays the character's. The
    fix opens an invitation, and an invitation that applied itself would be a
    worse bug than the one it replaced."""
    src = inspect.getsource(project_boundary)
    for verb in ("append(", "projects.append", "adopt"):
        assert "projects.append" not in src
    assert src.count("return") <= 2
