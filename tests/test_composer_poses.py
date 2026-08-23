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


# --- a referent is not necessarily a body ---------------------------------
#
# Every one of these is the same defect from a different angle: `relative_to`
# and `support` were resolved through `display_map`, which holds co-present
# BODIES only, and every miss took the person-shaped default "someone". Chat
# 84 had all four poses in one scene doing it at once -- "seated upright on
# desk at someone", "restrained in someone", and, in a room the observer
# could see held exactly two guards, "standing beside someone".

_FURNISHED = {"desk_main": {"name": "Oak Desk", "kind": "furniture",
                            "aliases": ["the desk"]},
              "chair_bolted": {"name": "Bolted Chair", "kind": "fixture"}}


def test_an_object_referent_is_the_object_never_a_person():
    text, _ = _render(_scene(
        {"Kai": {"posture": "seated", "support": "desk_main",
                 "relative_to": "desk_main", "relation": "at"}},
        entities=_FURNISHED))
    assert "someone" not in text
    assert text == "Kai is seated at the Oak Desk."


def test_an_entity_id_never_reaches_the_page_as_an_id():
    """`support` took its raw string onto the page, so a scene keyed by id
    read "sitting on chair_bolted" to the player."""
    text, _ = _render(_scene(
        {"Kai": {"posture": "sitting", "support": "chair_bolted"}},
        entities=_FURNISHED))
    assert "chair_bolted" not in text
    assert text == "Kai is sitting on the Bolted Chair."


def test_one_thing_named_twice_is_rendered_once_under_its_relation():
    """The body specialist fills `support` and `relative_to` with the same
    referent -- three of chat 84's four poses did -- which reads as "on desk
    at desk" the moment the referent stops being a person. The relation is
    the more specific of the two and carries it alone."""
    text, _ = _render(_scene(
        {"Kai": {"posture": "seated", "support": "chair_bolted",
                 "relative_to": "chair_bolted", "relation": "restrained in",
                 "constraint": "secured by restraints"}},
        entities=_FURNISHED))
    assert text == ("Kai is seated restrained in the Bolted Chair, "
                    "secured by restraints.")
    assert text.count("Bolted Chair") == 1


def test_a_referent_matching_no_record_at_all_is_dropped_with_its_relation():
    """`anchor_device` named nothing -- the entity's id was `scranton_anchor`
    -- so it was delivered as a person. An id-shaped token that resolves to
    no record is engine plumbing, not prose, and it subtracts."""
    text, percepts = _render(_scene(
        {"Kai": {"posture": "standing", "relative_to": "anchor_device",
                 "relation": "beside"}},
        entities=_FURNISHED))
    assert text == "Kai is standing."
    assert not percepts[0].data.get("relative_to")


def test_another_bodys_pose_never_names_a_body_you_were_not_shown():
    """Not awkwardness -- disclosure. A body absent from the display map is
    one perception withheld, and it is dropped rather than labelled."""
    scene = _scene({"Kai": {"posture": "leaning", "relative_to": "Mara",
                            "relation": "against"}})
    scene["positions"]["Mara"] = "elsewhere"
    scene["poses"]["Mara"] = {"posture": "standing"}
    text, _ = _render(scene)
    assert "Mara" not in text and "someone" not in text
    assert text == "Kai is leaning."


def test_a_bare_noun_gains_the_packs_article_and_only_when_it_needs_one():
    def support(value):
        text, _ = _render(_scene({"Kai": {"posture": "sitting",
                                          "support": value}}))
        return text
    assert support("desk") == "Kai is sitting on the desk."
    # Already determined, already prepositioned, or a proper name: untouched.
    assert support("the far wall") == "Kai is sitting on the far wall."
    assert support("her shoulder") == "Kai is sitting on her shoulder."
    assert support("on the sill") == "Kai is sitting on the sill."
    assert support("Excalibur") == "Kai is sitting on Excalibur."


# ---- delivery and obligation boundaries in the observation projection ----

class TestOneEntryIsOneDelivery:
    """`observations_from_render` mints the numbered record the narrator
    writes from, and a numbered entry claims to be ONE delivery.

    Two guarantees, both deterministic, both stated as class rules rather
    than against the beat that exposed them: a spoken line's boundaries are
    part of the fact (never fractured, never welded to another mouth's), and
    obligation is a boundary too (standing state never folded into an event).
    """

    def _render(self, percepts):
        from agents import composer
        rendered = composer.render_view(percepts, mode="character",
                                        full_render=True)
        return composer.observations_from_render("player", rendered), rendered

    def _speech(self, who, body, order):
        from agents import composer
        return composer.speech_percept(
            {"speaker": who, "text": body, "volume": "normal"},
            {"same_room": True}, "Observer",
            display=who, can_see=True, order_key=order,
            observer_id="player")

    def test_two_speakers_never_share_a_numbered_entry(self):
        obs, _ = self._render([
            self._speech("Mara", "We hold the line here.", 0),
            self._speech("Vorne", "Agreed. For now.", 1),
        ])
        for entry in obs:
            text = (entry.get("observed") or {}).get("text") or ""
            assert not ("Mara" in text and "Vorne" in text), text

    def test_one_mouths_consecutive_lines_may_share_an_entry(self):
        """The refusal is about WHOSE delivery, not about tidiness: welding
        one speaker's consecutive lines is an honest description of one
        delivery, and refusing it would uncap the atom count on a monologue."""
        obs, _ = self._render([
            self._speech("Mara", "We hold the line here.", 0),
            self._speech("Mara", "No one crosses.", 1),
        ])
        assert len(obs) <= 2

    def test_every_delivered_quote_survives_whole_in_one_entry(self):
        """The invariant the retired sentence-chunker used to break. A
        multi-sentence utterance is ONE fact; splitting it at a full stop
        makes the record disagree with the view it was projected from."""
        long_line = ("Italian, Hinami. Means 'very good' or 'very well.' "
                     "Old habit from a trip to Florence.")
        obs, rendered = self._render([
            self._speech("The Doctor", long_line, 0),
            self._speech("Mara", "It fits the meal.", 1),
        ])
        texts = [(o.get("observed") or {}).get("text") or "" for o in obs]
        assert any(long_line in t for t in texts), texts
        assert long_line in rendered.text


class TestAChangeOfDressIsAnEvent:
    """A garment gone is an event; re-issuing the wardrobe is a ledger.

    Both halves matter and they pull opposite ways, which is why they are
    tested together: the description must not re-appear when nothing moved,
    and it must NEVER be suppressed when something did. The second is the
    non-negotiable direction -- a change the observer can see and the page
    does not mention is the worse error by far.
    """

    def test_a_state_note_alone_is_not_a_change_of_dress(self):
        """Measured: 233 of 384 stored attire entries (60.7%) carry `state`
        alone, and the notes are mostly posture -- "standing in genkan
        threshold", "nine tails fanned behind her". Seven of every eight
        attire diffs that re-earned a full appearance moved no clothing."""
        from agents.perception import _attire_diff_moves_clothing
        assert not _attire_diff_moves_clothing(
            {"add": [], "remove": [], "replace": None,
             "state": ["standing in genkan threshold", "fox ears visible"]})
        assert not _attire_diff_moves_clothing(
            {"add": [], "remove": [], "replace": None, "state": []})
        assert not _attire_diff_moves_clothing({"add": [""], "remove": []})

    def test_any_real_operation_still_counts(self):
        from agents.perception import _attire_diff_moves_clothing
        assert _attire_diff_moves_clothing({"remove": ["haori"]})
        assert _attire_diff_moves_clothing({"add": ["mask"]})
        assert _attire_diff_moves_clothing({"replace": {"haori": "cloak"}})
        # Unreadable fails toward describing, never toward silence.
        assert _attire_diff_moves_clothing(None)
        assert _attire_diff_moves_clothing("nonsense")

    def test_a_restatement_of_the_same_clothes_is_not_a_change(self):
        from agents.perception import _attire_changed_semantically
        before = {"attire": {"Tamamo": {"wearing": ["kimono", "haori"]}}}
        after = {"attire": {"Tamamo": {"wearing": ["haori", "kimono"]}}}
        assert not _attire_changed_semantically(before, after, "Tamamo")

    def test_an_unknown_ledger_is_treated_as_changed(self):
        from agents.perception import _attire_changed_semantically
        assert _attire_changed_semantically({}, {}, "Tamamo")

    def test_the_change_renders_as_the_change_not_the_inventory(self):
        from agents.perception import _attire_delta_text
        before = {"attire": {"Tamamo": {
            "wearing": ["ceremonial kimono", "haori", "zori", "tabi"]}}}
        after = {"attire": {"Tamamo": {
            "wearing": ["ceremonial kimono", "zori", "tabi"]}}}
        text = _attire_delta_text(before, after, "Tamamo")
        assert "haori" in text
        # The three garments that did NOT move stay out of it -- that whole
        # list reaching the page as an event is the defect this closes.
        assert "kimono" not in text and "zori" not in text

    def test_a_body_whose_clothes_did_not_move_has_no_delta(self):
        from agents.perception import _attire_delta_text
        same = {"attire": {"Tamamo": {"wearing": ["kimono"]}}}
        assert _attire_delta_text(same, same, "Tamamo") == ""

    def test_the_full_description_still_stands_in_when_there_is_no_delta(self):
        """A scale, an overlay or a rewritten description has no readable
        garment delta, and must fall back rather than go unmentioned."""
        from agents import composer
        p = composer.appearance_percept(
            "Tamamo", "Tamamo", "a nine-tailed kitsune", force=True, delta="")
        assert "delta" not in p.data
        rendered = composer.render_view([p], mode="character",
                                        full_render=True)
        assert "nine-tailed kitsune" in rendered.text

    def test_a_forced_change_is_never_filed_as_standing(self):
        """The predicate the whole re-filing rests on: `force` outranks
        `order_key is None`, so a change of dress keeps its number in
        current_events instead of moving to the may-skip reference half."""
        from agents import composer
        p = composer.appearance_percept(
            "Tamamo", "Tamamo", "a nine-tailed kitsune", force=True,
            delta="no longer wearing haori")
        obs = composer.observations_from_render(
            "player", composer.render_view([p], mode="character",
                                           full_render=True))
        assert obs and all(not o.get("standing") for o in obs)
        assert "haori" in (obs[0].get("observed") or {}).get("text", "")


class TestSheLeavesAndComesBack:
    """An authored scenario run the way a turn runs it: the ledger threaded
    beat to beat, `mode='player'`.

    Written because the unit tests above each check one rule, and the
    question "does a body who walks out and walks back in read decently"
    is only answerable end to end.
    """

    APPEARANCE = ("a tall woman with fox ears and nine tails, in a "
                  "ceremonial kimono, a haori over it, zori and tabi")

    def _scene(self):
        return {"rooms": {"hall": {"name": "The Hall", "desc": "A dim hall.",
                                   "light": "normal"}},
                "positions": {"You": "hall", "Tamamo": "hall"},
                "entities": [], "poses": {}, "contacts": [], "attire": {},
                "location": "The Hall", "description": "A dim hall."}

    def _beat(self, present, appearance_kwargs, standing, described):
        from agents import composer
        percepts = []
        if present:
            sc = self._scene()
            percepts += composer.presence_percepts(
                sc, "You", [{"name": "Tamamo", "room": "hall"}],
                {"Tamamo": "the unfamiliar person"})
            if appearance_kwargs is not None:
                percepts.append(composer.appearance_percept(
                    "Tamamo", "the unfamiliar person", self.APPEARANCE,
                    **appearance_kwargs))
        r = composer.render_view(percepts, mode="player",
                                 prev_standing=standing,
                                 prev_described=described)
        return r, frozenset(r.standing_keys), frozenset(r.described)

    def test_the_scenario_end_to_end(self):
        st, de = frozenset(), frozenset()

        first, st, de = self._beat(True, {}, st, de)
        assert "fox ears" in first.text, "first sight must describe her"

        gone, st, de = self._beat(False, None, st, de)
        assert not gone.text.strip(), "nothing reaches you while she is out"

        back, st, de = self._beat(True, {}, st, de)
        # SHE IS ANNOUNCED, NOT RE-DESCRIBED. Perception does not repeat a
        # full appearance it has already delivered -- `prev_described` is
        # first-mention tracking and it never forgets, so a body seen once
        # is never re-described however long they were away. The narrator
        # can still reach back for it (`past_narration` carries the earlier
        # description), but the VIEW no longer supplies it.
        #
        # This pins a real decision rather than a guarantee: re-earning the
        # description on re-encounter would need the ledger to record who
        # was DELIVERED AS PRESENT, because the presence dedupe key hashes
        # tier/arc/level and changes when a body merely steps closer.
        assert "close by" in back.text
        assert "fox ears" not in back.text

        off, st, de = self._beat(
            True, {"force": True, "delta": "no longer wearing haori"}, st, de)
        # A change of dress reads as the change, names the body, and does
        # not re-issue the kimono, zori and tabi that did not move.
        assert "no longer wearing haori" in off.text
        assert "the unfamiliar person" in off.text.casefold()
        assert "ceremonial kimono" not in off.text
