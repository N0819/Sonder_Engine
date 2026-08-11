"""Poses reach a mind.

`state_diff.poses` has been in the Director's resolve contract for a long
time, `normalize_scene_poses` cleans it, `merge_scene_with_diff` folds it
into the scene blob, and `pose_facts` projects it observer-safely. Every
link existed except the last one: nothing composed a pose into a view, so
75 turns of authored body arrangement in the corpus reached nobody.

This wires the final hop. Nothing new is declared and nothing new is
stored — the Director already owns the declaration and the scene blob is
already the authority. Perception just reads it now, like it reads
stations and facing.

The interesting rule is the fidelity grade. Posture is the ONE body fact a
silhouette genuinely carries: you can see someone is kneeling across a dim
room without seeing anything else about them. So `shapes` yields posture
alone and `full` yields the lot, and the difference is which fields become
percepts — subtraction, not redaction.
"""

from __future__ import annotations

from agents.composer import pose_percepts, render_episode, render_view


def _scene(poses, light="bright", **kw):
    scene = {
        "rooms": {"h": {"name": "Hall", "light": light}},
        "positions": {"Reya": "h", "Kai": "h"},
        "poses": poses,
    }
    scene.update(kw)
    return scene


def _render(scene, observer="Reya", others=(("Kai", "Kai"),)):
    percepts = pose_percepts(
        scene, observer, [{"name": n} for n, _ in others],
        {n: label for n, label in others})
    return render_view(percepts).text, percepts


# --- the delivery ---------------------------------------------------------

def test_a_full_pose_reads_as_one_sentence():
    text, _ = _render(_scene({"Kai": {
        "posture": "kneeling", "support": "the low bench",
        "relative_to": "Reya", "relation": "facing",
        "constraint": "wrists bound", "detail": "shoulders squared"}}))
    assert text == ("Kai is kneeling on the low bench facing you, "
                    "wrists bound — shoulders squared.")


def test_your_own_pose_is_yours_in_the_second_person():
    text, percepts = _render(_scene({"Reya": {"posture": "sitting"}}),
                             others=())
    assert text == "You are sitting."
    assert percepts[0].channel == "interoception"


def test_a_bare_posture_is_a_short_sentence_not_a_gappy_one():
    text, _ = _render(_scene({"Kai": {"posture": "standing"}}))
    assert text == "Kai is standing."


def test_an_authored_preposition_is_not_doubled():
    """`support` is a free string: "the sill" and "on the sill" are both
    authored, and "sitting on on the sill" is nobody's idea of prose."""
    text, _ = _render(_scene({"Kai": {"posture": "sitting",
                                      "support": "on the sill"}}))
    assert text == "Kai is sitting on the sill."


# --- the grade ------------------------------------------------------------

def test_a_silhouette_gives_posture_and_nothing_else():
    """Posture survives dim light because a shape has one. Support,
    constraint, relation and the authored detail do not — a silhouette
    cannot show a drawn blade."""
    text, percepts = _render(_scene({"Kai": {
        "posture": "standing", "support": "the altar",
        "constraint": "blade drawn", "detail": "SECRET",
        "relative_to": "Reya", "relation": "over"}}, light="dim"),
        others=(("Kai", "an indistinct figure"),))

    assert text == "An indistinct figure is standing."
    assert "SECRET" not in text and "blade" not in text
    assert percepts[0].fidelity == "degraded"


def test_a_body_in_the_dark_has_no_pose_at_all():
    text, percepts = _render(
        _scene({"Kai": {"posture": "kneeling"}}, light="dark"))
    assert not percepts
    assert text == ""


def test_a_body_behind_you_is_not_watched():
    """Matches `presence_percepts`: you do not see how someone behind you
    is sitting."""
    scene = _scene({"Kai": {"posture": "kneeling"}},
                   orientation={"Reya": {"facing": "n"}},
                   stations={"Reya": {"at": "door"}, "Kai": {"at": "hearth"}})
    scene["rooms"]["h"]["anchors"] = {"door": {"dir": "n"},
                                      "hearth": {"dir": "s"}}
    _text, percepts = _render(scene)
    assert not [p for p in percepts if p.source_label != "you"]


def test_a_pose_naming_someone_unrecognised_uses_their_descriptor():
    """`relative_to` is a canonical name in the scene blob. It must not
    reach an observer who has not earned it."""
    text, _ = _render(_scene({"Kai": {
        "posture": "leaning", "relative_to": "Mara", "relation": "against"}}),
        others=(("Kai", "Kai"), ("Mara", "the tall woman")))
    assert "Mara" not in text
    assert "the tall woman" in text


def test_a_pose_for_a_body_that_is_not_here_is_not_delivered():
    scene = _scene({"Elsewhere": {"posture": "kneeling"}})
    _text, percepts = _render(scene)
    assert not percepts


def test_a_pose_never_outruns_the_presence_it_belongs_to():
    """Found by a pose-bearing drive scenario, which the corpus could not
    provide: the Director has declared a pose ONCE in 2,296 turns.

    Kai stood in the yard, Reya knelt in the forge behind a closed door,
    and his view read "Reya is kneeling on the anvil block — breathing
    hard." Presence had already declined to mention her at all —
    `proximity_rel` answers None across rooms — while this gate checked
    only sight and arc. So a body he was not even told was present arrived
    with her posture, her support and her breathing.

    How a body is held is finer-grained than the fact of it, and cannot
    reach further.
    """
    scene = _scene({"Reya": {"posture": "kneeling",
                             "support": "the anvil block"}})
    scene["rooms"] = {
        "h": {"name": "Hall", "adjacent": [
            {"to": "yard", "barrier": "door", "distance": "near"}]},
        "yard": {"name": "Yard", "adjacent": [
            {"to": "h", "barrier": "door", "distance": "near"}]}}
    scene["positions"] = {"Reya": "h", "Kai": "yard"}

    percepts = pose_percepts(scene, "Kai", [{"name": "Reya"}], {"Reya": "Reya"})
    assert not percepts


# --- memory ---------------------------------------------------------------

def test_a_changed_pose_is_remembered_in_the_past_tense():
    """A memory saying "I am kneeling" is a claim about now. The tense is
    chosen when the sentence is built, never patched into finished prose —
    a regex would also reach into the authored `detail`."""
    percepts = pose_percepts(
        _scene({"Reya": {"posture": "kneeling"}}), "Reya", [], {})
    content, _gist, _entities = render_episode(percepts)
    assert content == "I was kneeling."


def test_an_unchanged_pose_mints_nothing():
    """Furniture. The same rule the room already lives under."""
    percepts = pose_percepts(
        _scene({"Reya": {"posture": "kneeling"}}), "Reya", [], {})
    content, _g, _e = render_episode(
        percepts, prev_standing={p.dedupe_key for p in percepts})
    assert content == ""
