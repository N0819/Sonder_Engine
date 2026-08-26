"""One body gets ONE label per composed view, and a stranger's descriptor is
an appearance fact that degraded sight does not deliver.

Three builders name a co-present body for an observer. Two of them gate on
`visual_level_between` and subtract -- `composer.presence_percepts` renders a
body seen only as shapes as the fixed silhouette label, and perception's
`_co_present_company` did the same for its proximity field. The third,
`composer.observer_display_map`, did not consult sight at all, and it is the
one every OTHER builder reads for what to call a body: poses, acts, speech
attribution, region labels, scent sources.

So in a room dim enough to reduce sight to `shapes` (design note 18: dim
lifts only on a standing contact or a station-measured `within_reach`), one
body arrived in one view under two names at once -- a silhouette in the
presence line, an appearance epithet in every clause after it. An observer
reading both is not confused when it counts an extra person; it is reasoning
correctly from a view that named one body twice.

Two separable defects, asserted separately below:

  * COHERENCE -- every builder must read one source.
  * EXPANSION -- the descriptor is cut from the appearance summary, so it
    carries build and age. A silhouette shows neither, and the subtracting
    renderer is the correct one: the display map is what moves.

Deliberately free of any story noun. The bodies are OBS, NEAR and SUBJ.
"""

from __future__ import annotations

from agents import composer
from agents.perception import _co_present_company
from world.spatial import visual_level_between

#: What full sight would show. Every content word here is an appearance fact
#: and none of them may reach an observer holding a silhouette.
SUBJ_APPEARANCE = "A lean middle-aged man in a wet coat."
NEAR_APPEARANCE = "A stocky woman with cropped grey hair."

APPEARANCE_WORDS = ("lean", "middle", "aged", "wet", "coat")


def _dim_scene():
    """A dim room where the observer is station-measured within reach of NEAR
    and merely close by to SUBJ -- so sight is lifted to `full` for one and
    stays at `shapes` for the other, in one room, for one observer."""
    return {
        "rooms": {"room_a": {"name": "The Room", "light": "dim",
                             "adjacent": []}},
        "positions": {"OBS": "room_a", "SUBJ": "room_a", "NEAR": "room_a"},
        "stations": {
            "OBS": {"at": "station_a", "near": ["NEAR"]},
            "NEAR": {"at": "station_a", "near": ["OBS"]},
            "SUBJ": {"at": "station_b", "near": []},
        },
        "poses": {"SUBJ": {"posture": "sitting"}},
        "contacts": {},
        "contained": {},
    }


def _bodies():
    return [
        {"name": "SUBJ", "appearance": SUBJ_APPEARANCE, "aliases": []},
        {"name": "NEAR", "appearance": NEAR_APPEARANCE, "aliases": []},
    ]


def _leaked_appearance_words(text):
    low = str(text).casefold()
    return [w for w in APPEARANCE_WORDS if w in low]


class TestTheSightSplitThatMadeTwoPeopleOfOne:
    def test_the_premise_one_room_two_sight_levels(self):
        """Everything below rests on this: the same observer, in the same
        room, at two different sight levels."""
        scene = _dim_scene()
        assert visual_level_between(scene, "OBS", "SUBJ") == "shapes"
        assert visual_level_between(scene, "OBS", "NEAR") == "full"

    def test_a_silhouette_receives_no_appearance_descriptor(self):
        """THE EXPANSION. Build and age are what full sight shows."""
        scene = _dim_scene()
        display = composer.observer_display_map(
            scene, "OBS", _bodies(), {"OBS": []})
        leaked = _leaked_appearance_words(display["SUBJ"])
        assert not leaked, (
            f"a body seen only as shapes was labelled {display['SUBJ']!r}, "
            f"carrying appearance facts {leaked}")

    def test_every_builder_reads_one_source(self):
        """THE COHERENCE. The display map, the presence percept and the
        proximity field must agree on what this observer calls this body."""
        scene, bodies = _dim_scene(), _bodies()
        known = {"OBS": []}
        display = composer.observer_display_map(scene, "OBS", bodies, known)
        presence = {
            p.data["body"]: p.source_label
            for p in composer.presence_percepts(scene, "OBS", bodies, display)
        }
        prox, _behind = _co_present_company(scene, "OBS", bodies, known)
        for name in ("SUBJ", "NEAR"):
            label = display[name]
            assert presence[composer.body_key(name)] == label
            assert label in prox, (
                f"the proximity field calls {name} something the composed "
                f"view does not: {sorted(prox)} vs {label!r}")

    def test_the_rendered_view_names_the_body_once(self):
        """End to end, which is where it was found: the presence line and the
        pose line are two sentences about one body, and they used to disagree
        about who that body was."""
        scene, bodies = _dim_scene(), _bodies()
        display = composer.observer_display_map(
            scene, "OBS", bodies, {"OBS": []})
        percepts = composer.presence_percepts(scene, "OBS", bodies, display)
        percepts.extend(composer.pose_percepts(scene, "OBS", bodies, display))
        text = composer.render_view(percepts, mode="character").text
        leaked = _leaked_appearance_words(text)
        assert not leaked, (
            f"the composed view delivered appearance facts {leaked} about a "
            f"body seen only as shapes:\n{text}")
        # ...and the body that IS seen in full still is.
        assert "stocky" in text.casefold()

    def test_full_sight_still_earns_the_descriptor(self):
        """The fix subtracts and must not over-subtract: the observer can see
        NEAR plainly, and a plainly seen stranger is still described."""
        scene = _dim_scene()
        display = composer.observer_display_map(
            scene, "OBS", _bodies(), {"OBS": []})
        assert "stocky" in display["NEAR"].casefold()
        assert "near" not in display["NEAR"].casefold()

    def test_degraded_sight_costs_detail_not_acquaintance(self):
        """A body the observer already knows keeps its name in the dark. The
        dim light takes the face, never the name -- the rule
        `presence_percepts` states, now held one layer earlier."""
        scene = _dim_scene()
        display = composer.observer_display_map(
            scene, "OBS", _bodies(), {"OBS": ["SUBJ"]})
        assert display["SUBJ"] == "SUBJ"

    def test_two_silhouettes_stay_indistinguishable(self):
        """An observer who cannot tell two shapes apart must not be handed a
        view that can. They share one label on purpose."""
        scene = _dim_scene()
        scene["stations"]["NEAR"] = {"at": "station_b", "near": []}
        scene["stations"]["OBS"] = {"at": "station_a", "near": []}
        display = composer.observer_display_map(
            scene, "OBS", _bodies(), {"OBS": []})
        assert display["SUBJ"] == display["NEAR"]
        assert not _leaked_appearance_words(" ".join(display.values()))

    def test_an_impaired_eye_takes_the_descriptor_with_it(self):
        """The sense card grades sight after the room does, and the label has
        to be graded with it or the split reopens one card down."""
        scene = _dim_scene()
        dulled = [{"channel": "sight", "acuity": "impaired"}]
        display = composer.observer_display_map(
            scene, "OBS", _bodies(), {"OBS": []}, dulled)
        assert not _leaked_appearance_words(display["NEAR"]), display["NEAR"]
        assert "stocky" not in display["NEAR"].casefold()

    def test_no_visual_channel_delivers_no_figure_either(self):
        """The firewall case with nothing left: an observer with no sight
        line at all. A body reaching them through some other channel is not
        even a silhouette, and certainly not a build and an age."""
        scene = _dim_scene()
        scene["rooms"]["room_b"] = {"name": "The Other Room", "adjacent": []}
        scene["positions"]["SUBJ"] = "room_b"
        assert visual_level_between(scene, "OBS", "SUBJ") == "none"
        display = composer.observer_display_map(
            scene, "OBS", _bodies(), {"OBS": []})
        assert not _leaked_appearance_words(display["SUBJ"]), display["SUBJ"]
        assert "figure" not in display["SUBJ"].casefold()
