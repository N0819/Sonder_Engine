"""A view LEADS WITH WHAT CHANGED.

Standing state is the BACKGROUND of a percept, not its content. What is
continuously true is context; what is different since THIS OBSERVER last
perceived it is the beat.

Measured over 389 replayed player views in seven stored stories (chats 86-92,
`agents/composer.py` builders run against the checkpointed scenes): 59.3% of
every composed atom -- 48.0% of every composed character -- was standing state
re-rendered because it was still true, and 68 of those beats delivered the
narrator ZERO numbered observations. It was handed the same scene again and
asked to make it feel different, which is the largest warning class the corpus
carries (126 "prose appears to reuse a previous turn's view").

The tier that answers it lives entirely inside the composer's existing seam:
`standing_key` splits a standing dedupe key into subject and content, and
`standing_verdicts` reads it against this observer's OWN previous ledger --
never against the objective scene, which is the shape that leaks.
"""

from __future__ import annotations

import pytest

from agents import composer
from agents.composer import (Percept, appearance_percept, observations_from_render,
                             render_view, standing_verdicts)


def _scene(**over):
    scene = {
        "rooms": {"hall": {"name": "Hall", "light": "normal"},
                  "cellar": {"name": "Cellar", "light": "normal"}},
        "positions": {"Reya": "hall", "Tamamo": "hall"},
        "entities": {}, "poses": {}, "contacts": [], "attire": {},
        "overlays": {}, "scales": {}, "contained": {},
    }
    scene.update(over)
    return scene


def _ledger(rendered):
    """What the next beat receives: this beat's own returned ledger."""
    return frozenset(rendered.standing_keys), frozenset(rendered.described)


def _beat_half(rendered):
    return [sentence for percept, sentence in rendered.spans
            if percept.order_key is not None
            or (percept.data or {}).get("beat")]


def _background_half(rendered):
    return [sentence for percept, sentence in rendered.spans
            if percept.order_key is None
            and not (percept.data or {}).get("beat")]


# ---------------------------------------------------------------------------
# The key shape
# ---------------------------------------------------------------------------

class TestTheKeyCarriesASubjectAndItsContent:
    """One hash could only answer "have I been told this exact thing". Two
    answer "have I been told anything about this thing", which is what
    separates a pose that moved from a body that just walked in."""

    def _every_standing_builder(self):
        scene = _scene(poses={"Tamamo": {"posture": "kneeling"}},
                       attire={"Tamamo": {"wearing": ["a kimono"]}})
        out = []
        out.append(composer.environment_percept("hall", "Hall", "Rain.", "dim"))
        out += composer.presence_percepts(
            scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
            {"Tamamo": "Tamamo"})
        out += composer.pose_percepts(
            scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
            {"Tamamo": "Tamamo"}, None)
        out.append(appearance_percept("Tamamo", "Tamamo", "nine golden tails"))
        out.append(composer.body_state_percept({"posture": "standing"}))
        out += composer.contact_percepts([
            ({"actor": "Tamamo", "actor_part": "hand", "target": "Reya",
              "target_part": "arm", "manner": "resting"}, "your arm registers a hand")])
        out += composer.contact_action_percepts([
            ({"action_id": "a1", "contact_id": "c1", "action": "squeeze",
              "actor": "Tamamo", "intensity": "firm", "rhythm": "steady"},
             "you feel a firm squeeze")])
        out += composer.body_region_percepts([("you", "shoulder", "a long scar")])
        out += composer.body_part_percepts([
            ("Tamamo", {"kind": "tail", "count": 9, "at": "waist",
                        "aspect": "back", "description": "golden"})])
        out += composer.ambient_percepts(
            [{"kind": "sound", "description": "a bell", "source_room": "hall"}],
            "hall")
        out += composer.scent_percepts([
            {"key": "Tamamo", "label": "Tamamo", "scent": "cedar smoke",
             "level": "full", "attributed": True}])
        out += composer.room_content_percepts(
            [{"uid": "crowd-1", "what": "a press of bodies"}])
        out.append(composer.micro_round_percept("A door closes somewhere."))
        out += composer.residue_percepts("under", pain=True)
        return [p for p in out if p is not None]

    def test_every_standing_builder_emits_a_two_colon_key(self):
        built = self._every_standing_builder()
        assert len(built) >= 13, "a builder stopped producing anything"
        for percept in built:
            assert percept.order_key is None
            parts = percept.dedupe_key.split(":")
            assert len(parts) == 3, f"{percept.kind}: {percept.dedupe_key}"
            assert all(parts), percept.dedupe_key
            assert composer._subject_prefix(percept.dedupe_key) == \
                f"{parts[0]}:{parts[1]}"

    def test_no_canonical_name_rides_a_key(self):
        """The IR invariant, checkable by string containment: a subject key
        is a hash, so splitting the key did not put a name in the ledger."""
        for percept in self._every_standing_builder():
            for name in ("Tamamo", "Reya", "tamamo", "reya"):
                assert name not in percept.dedupe_key

    def test_the_same_subject_under_new_content_keeps_its_prefix(self):
        before = appearance_percept("Tamamo", "Tamamo", "nine golden tails")
        after = appearance_percept("Tamamo", "Tamamo", "eight golden tails")
        assert before.dedupe_key != after.dedupe_key
        assert composer._subject_prefix(before.dedupe_key) == \
            composer._subject_prefix(after.dedupe_key)


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------

class TestTheVerdictIsPerObserver:
    def test_the_three_answers(self):
        held = appearance_percept("Tamamo", "Tamamo", "nine golden tails")
        moved = appearance_percept("Tamamo", "Tamamo", "eight golden tails")
        stranger = appearance_percept("Bram", "a tall man", "a tall man")
        prev = frozenset({held.dedupe_key})

        verdicts = standing_verdicts([held, moved, stranger], prev)
        assert verdicts[held.dedupe_key] == "unchanged"
        assert verdicts[moved.dedupe_key] == "changed"
        assert verdicts[stranger.dedupe_key] == "first"

    def test_an_empty_ledger_can_never_read_as_changed(self):
        """No record is not "nothing was there". The opening beat, a mind
        that just woke, and a chat stored before the split key existed all
        arrive here, and none of them may be told the world moved."""
        percepts = [appearance_percept("Tamamo", "Tamamo", "nine tails"),
                    composer.environment_percept("hall", "Hall")]
        verdicts = standing_verdicts(percepts, frozenset())
        assert set(verdicts.values()) == {"first"}

    def test_an_old_single_hash_ledger_reads_as_first_sight(self):
        """Stored chats carry un-split keys. They must degrade toward one
        re-description, never toward a false claim that something moved."""
        percept = composer.environment_percept("hall", "Hall", "", "dim")
        legacy = frozenset({"env:0ff1cd992b", "pose:84ff18d48d"})
        assert standing_verdicts([percept], legacy) == \
            {percept.dedupe_key: "first"}

    def test_an_event_percept_gets_no_verdict(self):
        event = Percept(kind="act", channel="sight", source_label="Tamamo",
                        data={"surface": "crosses the hall"}, order_key=0,
                        dedupe_key="act:x")
        assert standing_verdicts([event], frozenset({"act:x"})) == {}


# ---------------------------------------------------------------------------
# What leads
# ---------------------------------------------------------------------------

class TestThePlayerViewLeadsWithChange:
    def _pose(self, detail):
        scene = _scene(poses={"Tamamo": {"posture": "kneeling",
                                         "detail": detail}})
        return composer.pose_percepts(
            scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
            {"Tamamo": "Tamamo"}, None)

    def _sensation(self, manner):
        return composer.contact_percepts([
            ({"actor": "Tamamo", "actor_part": "hand", "target": "Reya",
              "target_part": "arm", "manner": manner},
             f"your arm registers a hand, {manner}")])

    def test_a_changed_pose_leads_and_an_identical_one_is_suppressed(self):
        first = render_view(self._pose("head bowed"), mode="player")
        standing, described = _ledger(first)

        same = render_view(self._pose("head bowed"), mode="player",
                           prev_standing=standing, prev_described=described)
        assert same.text == "", "an unchanged pose is furniture"

        moved = render_view(self._pose("head lifting"), mode="player",
                            prev_standing=standing, prev_described=described)
        assert "head lifting" in moved.text
        assert _beat_half(moved) == [moved.text]
        assert not _background_half(moved)

    def test_the_beat_half_precedes_the_background_half(self):
        base = self._pose("head bowed") + self._sensation("resting")
        first = render_view(base, mode="player")
        standing, described = _ledger(first)

        rendered = render_view(
            self._pose("head lifting") + self._sensation("resting"),
            mode="player", prev_standing=standing, prev_described=described)
        beat, background = _beat_half(rendered), _background_half(rendered)
        assert beat and background
        assert rendered.text.startswith(beat[0])
        assert rendered.text.endswith(background[-1])
        # The unchanged contact is still being felt, so it still renders --
        # behind what happened rather than in front of it.
        assert "resting" in background[-1]

    def test_events_lead_the_beat_half_and_a_changed_room_closes_it(self):
        first = render_view(
            [composer.environment_percept("hall", "Hall", "Quiet.")],
            mode="player")
        standing, described = _ledger(first)
        event = Percept(kind="act", channel="sight", source_label="Tamamo",
                        data={"surface": "crosses the hall"}, order_key=0,
                        dedupe_key="act:1")
        rendered = render_view(
            [composer.environment_percept("hall", "Hall", "A lamp has died."),
             event] + self._pose("head bowed"),
            mode="player", prev_standing=standing, prev_described=described)
        beat = _beat_half(rendered)
        assert "crosses the hall" in beat[0]
        assert "A lamp has died." in beat[-1]

    def test_a_revealed_body_leads_but_an_opening_beat_does_not(self):
        scene = _scene()
        presence = composer.presence_percepts(
            scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
            {"Tamamo": "Tamamo"})
        opening = render_view(presence, mode="player")
        assert not _beat_half(opening), "the world arriving is not an event"

        # Same percept, against a ledger that holds this observer's room and
        # nothing about this body: she was not there and now she is.
        room = composer.environment_percept("hall", "Hall")
        anchored = render_view([room], mode="player")
        standing, described = _ledger(anchored)
        revealed = render_view(presence + [room], mode="player",
                               prev_standing=standing,
                               prev_described=described)
        assert _beat_half(revealed), "a body that was not there leads"

    def test_a_quiet_beat_composes_to_nothing(self):
        percepts = self._pose("head bowed") + [
            composer.environment_percept("hall", "Hall", "Quiet.")]
        first = render_view(percepts, mode="player")
        standing, described = _ledger(first)
        assert render_view(percepts, mode="player", prev_standing=standing,
                           prev_described=described).text == ""

    def test_an_explicit_look_re_earns_the_whole_background(self):
        percepts = self._pose("head bowed") + [
            composer.environment_percept("hall", "Hall", "Quiet.")]
        first = render_view(percepts, mode="player")
        standing, described = _ledger(first)
        looked = render_view(percepts, mode="player", prev_standing=standing,
                             prev_described=described, full_render=True)
        assert "Quiet." in looked.text
        assert "head bowed" in looked.text
        assert not _beat_half(looked), "asking is not the world moving"


# ---------------------------------------------------------------------------
# The appearance branch: the ledger is asked before `force`
# ---------------------------------------------------------------------------

class TestForceNoLongerReDeliversAnIdenticalCard:
    """Chat 89, turns 3-27: a visible-form channel was written on every beat
    while the composed description stayed byte-identical, and the same
    342-character card went to the narrator twenty-five times running. An
    objective wiggle is not a change FOR THIS OBSERVER."""

    CARD = ("a tall statuesque succubus with warm bronze skin, two small "
            "curved horns and a spade-tipped tail, wearing a plum silk robe")

    def test_an_identical_card_is_suppressed_however_hard_force_fires(self):
        first = render_view([appearance_percept("M", "Mirelle", self.CARD)],
                            mode="player")
        assert self.CARD in first.text
        standing, described = _ledger(first)

        for _ in range(4):
            again = render_view(
                [appearance_percept("M", "Mirelle", self.CARD, force=True)],
                mode="player", prev_standing=standing,
                prev_described=described)
            assert again.text == "", "the card re-earned itself on force alone"
            standing, described = _ledger(again)

    def test_a_description_that_actually_moved_leads(self):
        first = render_view([appearance_percept("M", "Mirelle", self.CARD)],
                            mode="player")
        standing, described = _ledger(first)
        moved = render_view(
            [appearance_percept("M", "Mirelle", self.CARD + ", torn open",
                                force=True)],
            mode="player", prev_standing=standing, prev_described=described)
        assert "torn open" in moved.text
        assert _beat_half(moved) == [moved.text]
        [observation] = observations_from_render("player", moved)
        assert observation["standing"] is False

    def test_a_change_renders_as_the_change_not_as_the_wardrobe(self):
        first = render_view([appearance_percept("M", "Mirelle", self.CARD)],
                            mode="player")
        standing, described = _ledger(first)
        delta = render_view(
            [appearance_percept("M", "Mirelle", self.CARD, force=True,
                                delta="no longer wearing the plum silk robe")],
            mode="player", prev_standing=standing, prev_described=described)
        assert "no longer wearing the plum silk robe" in delta.text
        assert "bronze skin" not in delta.text
        assert _beat_half(delta) == [delta.text]

    def test_a_re_encounter_is_background_not_an_event(self):
        """Meeting someone again is standing state that became sayable
        again, not something that happened."""
        first = render_view([appearance_percept("M", "Mirelle", self.CARD)],
                            mode="player")
        standing, described = _ledger(first)
        away = render_view([], mode="player", prev_standing=standing,
                           prev_described=described)
        back = render_view(
            [appearance_percept("M", "Mirelle", self.CARD, reearn=True)],
            mode="player", prev_standing=frozenset(away.standing_keys),
            prev_described=frozenset(away.described))
        assert self.CARD in back.text
        assert not _beat_half(back)


# ---------------------------------------------------------------------------
# The two representations stay one budget
# ---------------------------------------------------------------------------

class TestTheSecondRepresentationStillCannotExpand:
    def _mixed(self):
        scene = _scene(poses={"Tamamo": {"posture": "kneeling"}})
        return (composer.pose_percepts(
            scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
            {"Tamamo": "Tamamo"}, None)
            + [composer.environment_percept("hall", "Hall", "Quiet."),
               Percept(kind="act", channel="sight", source_label="Tamamo",
                       data={"surface": "crosses the hall"}, order_key=0,
                       dedupe_key="act:1")])

    def test_every_beat_sentence_survives_the_round_trip(self):
        first = render_view(self._mixed(), mode="player")
        standing, described = _ledger(first)
        scene = _scene(poses={"Tamamo": {"posture": "standing"}})
        moved = render_view(
            composer.pose_percepts(
                scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
                {"Tamamo": "Tamamo"}, None)
            + [composer.environment_percept("hall", "Hall", "Quiet.")],
            mode="player", prev_standing=standing, prev_described=described)
        observations = observations_from_render("player", moved)
        assert observations
        for observation in observations:
            text = observation["observed"]["text"]
            assert text in moved.text, "the projection invented text"
        obligations = [o for o in observations if not o["standing"]]
        assert obligations, "a changed pose must reach current_events"
        for sentence in _beat_half(moved):
            assert any(sentence in o["observed"]["text"] for o in obligations)

    def test_an_unchanged_sensation_stays_reference(self):
        sensation = composer.contact_percepts([
            ({"actor": "T", "actor_part": "hand", "target": "R",
              "target_part": "arm", "manner": "resting"},
             "your arm registers a hand")])
        first = render_view(sensation, mode="player")
        standing, described = _ledger(first)
        again = render_view(sensation, mode="player", prev_standing=standing,
                            prev_described=described)
        assert "your arm registers a hand" in again.text.casefold()
        [observation] = observations_from_render("player", again)
        assert observation["standing"] is True


class TestCharacterModeIsUntouched:
    """An NPC agent is a stateless LLM call: what is not in the context is
    not in the mind. The consumer differs, so the mode does."""

    def _percepts(self):
        scene = _scene(poses={"Tamamo": {"posture": "kneeling"}})
        return (composer.presence_percepts(
            scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
            {"Tamamo": "Tamamo"})
            + composer.pose_percepts(
                scene, "Reya", [{"name": "Tamamo", "room": "hall"}],
                {"Tamamo": "Tamamo"}, None)
            + [appearance_percept("Tamamo", "Tamamo", "nine golden tails")])

    EXPECTED = ("Tamamo is close by. Tamamo is kneeling. "
                "You see nine golden tails.")

    def test_the_wording_is_byte_identical_to_before_the_tier(self):
        assert render_view(self._percepts(), mode="character").text \
            == self.EXPECTED

    def test_a_full_ledger_changes_nothing(self):
        percepts = self._percepts()
        first = render_view(percepts, mode="character")
        standing, described = _ledger(first)
        again = render_view(percepts, mode="character",
                            prev_standing=standing, prev_described=described)
        assert again.text == self.EXPECTED
        assert all(not (p.data or {}).get("beat") for p, _ in again.spans)


# ---------------------------------------------------------------------------
# THE FIREWALL
# ---------------------------------------------------------------------------

class TestAChangeReachesNoObserverWhoHadNoChannelToIt:
    """The diff operands are not two scenes. They are this observer's
    admitted percepts and this observer's own last ledger, so a subject with
    no percept produces no verdict and therefore no sentence -- there is
    nothing for a rule to be about."""

    def _sealed_scene(self):
        """The player is in the hall; the cellar door and the body behind it
        are in another room with no adjacency."""
        return {
            "rooms": {"hall": {"name": "Hall", "light": "normal"},
                      "cellar": {"name": "Cellar", "light": "normal"}},
            "positions": {"Reya": "hall", "Tamamo": "cellar"},
            "entities": {}, "poses": {"Tamamo": {"posture": "kneeling"}},
            "contacts": [], "attire": {}, "overlays": {}, "scales": {},
            "contained": {},
        }

    def test_a_body_in_another_room_yields_no_percept_and_no_verdict(self):
        from agents.perception import _composer_standing_percepts

        scene = self._sealed_scene()
        observer = {"room": "hall", "room_name": "Hall", "room_notes": "",
                    "sense_card": None}
        others = [{"name": "Tamamo", "room": "cellar",
                   "appearance": "nine golden tails; wearing a torn kimono",
                   "aliases": [], "disguise_known_to": [],
                   "disguise_conceals_identity": False}]
        percepts = _composer_standing_percepts(
            scene, observer, "Reya", others, {"Tamamo": "Tamamo"},
            {"Reya": ["Tamamo"]},
            appearance_changed={"Tamamo"},
            appearance_deltas={"Tamamo": "no longer wearing the torn kimono"},
            prev_seen={"Tamamo"}, prune_appearance=True)

        # Nothing about that body was admitted, so there is no subject for a
        # verdict to be about and no sentence for the view to carry.
        assert not [p for p in percepts if p.source_label == "Tamamo"]
        rendered = render_view(percepts, mode="player")
        assert "kimono" not in rendered.text
        assert "Tamamo" not in rendered.text
        assert standing_verdicts(percepts, frozenset({"described:x:y"})) \
            .keys() == {p.dedupe_key for p in percepts}

    def test_a_diff_about_an_unperceived_subject_produces_no_sentence(self):
        """Stated at the renderer, which is where a world diff would have to
        be consumed: the view is a function of percepts, so an entry with no
        percept has no way in at all."""
        room = composer.environment_percept("hall", "Hall", "Quiet.")
        first = render_view([room], mode="player")
        standing, described = _ledger(first)
        # The cellar door swung open this beat. The observer's sight never
        # admitted the cellar, so no percept carries it.
        rendered = render_view([room], mode="player", prev_standing=standing,
                               prev_described=described)
        assert rendered.text == ""

    def test_transition_prose_needs_this_observers_own_record_of_the_past(self):
        """"No longer wearing the robe" discloses ROBE-WAS-WORN. Delivered to
        an observer who was asleep, absent or turned away when it came off,
        that is a fact reaching them through no channel. The delta is
        computed from the objective previous scene, so it may only ride a
        percept for an observer whose own seen-record holds that body."""
        from agents.perception import _composer_standing_percepts

        scene = _scene(attire={"Tamamo": {"wearing": ["a shift"]}})
        observer = {"room": "hall", "room_name": "Hall", "room_notes": "",
                    "sense_card": None}
        others = [{"name": "Tamamo", "room": "hall",
                   "appearance": "nine golden tails; wearing a shift",
                   "aliases": [], "disguise_known_to": [],
                   "disguise_conceals_identity": False}]

        def _appearance(prev_seen):
            percepts = _composer_standing_percepts(
                scene, observer, "Reya", others, {"Tamamo": "Tamamo"},
                {"Reya": ["Tamamo"]},
                appearance_changed={"Tamamo"},
                appearance_deltas={"Tamamo": "no longer wearing the haori"},
                prev_seen=prev_seen, prune_appearance=True)
            return next(p for p in percepts if p.kind == "appearance")

        watching = _appearance({"Tamamo"})
        assert composer.appearance_delta(watching) == \
            "no longer wearing the haori"

        # `set()` is a RECORD -- this observer saw nobody last beat.
        absent = _appearance(set())
        assert composer.appearance_delta(absent) == ""
        view = render_view([absent], mode="player")
        assert "haori" not in view.text, \
            "the past state crossed to a mind that had no channel to it"
        assert "nine golden tails" in view.text, "current sight is not withheld"

        # Unknown is not a record either, and must not pass for proof.
        assert composer.appearance_delta(_appearance(None)) == ""

    @pytest.mark.parametrize("prev", [frozenset(), frozenset({"env:a:b"})])
    def test_a_verdict_never_names_a_subject_the_percepts_did_not(self, prev):
        room = composer.environment_percept("hall", "Hall")
        verdicts = standing_verdicts([room], prev)
        assert set(verdicts) == {room.dedupe_key}
