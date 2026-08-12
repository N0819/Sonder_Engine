"""A standing contact is felt on every beat, until it ends.

The perception contract specified the tactile channel only as a SUBSTITUTE for
sight. Every mandatory clause was conditioned on sight being absent -- in the
dark, behind a wall, sealed inside something -- so two bodies in continuous
contact in a lit room had a wide-open tactile channel and nothing requiring a
word of it. A view written under a token budget rendered what was seen and
dropped what was felt.

Measured over 7,508 corpus observations before this: 46.8% classified as
`mixed` because no sensory cue matched them at all, `interoception` accounted
for 2.4%, and in the story that surfaced it the acting view of a character in
three standing contacts was a median 460 characters against 812 for the outcome
view of the same character -- so she chose her conduct with no sensation from
her own body and was told what she had felt after the choice was made.

The missing representation: the engine had `event` (rendered once) and `state`
(mentioned, then inert), and a standing contact is neither. It is a CONTINUOUS
PERCEPT -- true every beat and felt every beat until the ledger drops it.

`spatial.contact_sensation` renders that percept from one party's side and
`agents.perception._deliver_standing_sensations` is the deterministic floor
that puts it in the view when the model left it out. Clinical register
throughout, on purpose: the clause is engine output and has to read the same
in every story.
"""

from __future__ import annotations

from agents.perception import (_deliver_standing_sensations,
                               _observations_from_clean_views,
                               _standing_contacts_for)
from prompts import DEFAULT_PROMPTS
from spatial import (apply_contact_ops, contact_manner_kind, contact_motion,
                     contact_relation, contact_sensation)

# Two bodies, two contacts: one across a surface, one interior. Both stand at
# the top of the beat; neither is news.
SCENE = {
    "positions": {"Reya": "cell", "Bram": "cell"},
    "entities": {},
    "contacts": [
        {"actor": "Reya", "actor_part": "palm", "target": "Bram",
         "target_part": "sternum", "manner": "press"},
        {"actor": "Reya", "actor_part": "blade", "target": "Bram",
         "target_interior": "wound channel", "target_part": "shoulder",
         "manner": "penetrating"},
    ],
}

LIT_VIEW = "Lamplight moves on the wall. Bram is watching you."


def _deliver(view, who, scene=SCENE):
    return _deliver_standing_sensations(
        view, who, scene, _standing_contacts_for(scene, who))


class TestTheMannerReading:

    def test_motion_across_a_surface_reads_as_moving(self):
        for manner in ("rub", "swirling", "grinding", "stroke", "dragging"):
            assert contact_manner_kind(manner) == "moving"

    def test_one_part_within_another_reads_as_interior(self):
        for manner in ("penetrating", "inside", "lodged", "buried", "impaled"):
            assert contact_manner_kind(manner) == "interior"

    def test_an_unknown_manner_falls_through_to_settled(self):
        """The conservative reading. Claiming motion or interiority a record
        does not state would be inventing physical fact, not reporting it."""
        assert contact_manner_kind("throttle") == "settled"
        assert contact_manner_kind("") == "settled"
        assert contact_manner_kind(None) == "settled"

    def test_topology_and_motion_are_independent(self):
        contact = {
            "manner": "thrust", "relation": "interior", "motion": "moving",
        }

        assert contact_relation(contact) == "interior"
        assert contact_motion(contact) == "moving"

    def test_legacy_detail_can_supply_motion_without_erasing_interiority(self):
        contact = {
            "manner": "insert",
            "detail": "withdrawing and thrusting rhythmically",
        }

        assert contact_relation(contact) == "interior"
        assert contact_motion(contact) == "moving"

    def test_resolve_prompt_requires_both_contact_axes(self):
        prompt = DEFAULT_PROMPTS["director_resolve"]

        assert "relation is surface|interior and motion is settled|moving" in prompt
        assert "ALWAYS emit both" in prompt
        assert "target_interior names what currently encloses actor_part" in prompt
        assert "CROSSING AN ENDPOINT IS AN EXPLICIT TRANSITION" in prompt


class TestWhatEachPartyFeels:

    def test_both_parties_receive_the_contact_from_their_own_side(self):
        touching = contact_sensation(SCENE["contacts"][0], you="Reya")
        touched = contact_sensation(SCENE["contacts"][0], you="Bram")

        assert touching.startswith("your palm registers Bram's sternum")
        assert touched.startswith("your sternum registers Reya's palm")

    def test_an_interior_contact_is_not_symmetric(self):
        """The enclosing party feels something within them; the entering party
        feels something closed around theirs. Rendering either side with the
        other's phrasing describes a body the perceiver does not have."""
        entering = contact_sensation(SCENE["contacts"][1], you="Reya")
        enclosing = contact_sensation(SCENE["contacts"][1], you="Bram")

        assert "Bram's wound channel enclosing it" in entering
        assert "within your wound channel" in enclosing
        assert "within your shoulder" not in enclosing
        assert "shoulder enclosing" not in entering

    def test_a_moving_interior_contact_carries_both_facts(self):
        contact = {
            "actor": "Reya", "actor_part": "blade", "target": "Bram",
            "target_interior": "wound channel", "target_part": "shoulder",
            "manner": "thrust",
            "relation": "interior", "motion": "moving",
        }

        entering = contact_sensation(contact, you="Reya")
        enclosing = contact_sensation(contact, you="Bram")

        assert "Bram's wound channel enclosing it" in entering
        assert "friction along its length" in entering
        assert "within your wound channel" in enclosing
        assert "fullness, stretch, shifting pressure and movement" in enclosing

    def test_a_bystander_is_a_party_to_nothing(self):
        """Someone watching two other people touch feels nothing, and this
        must never be the thing that tells them otherwise."""
        for contact in SCENE["contacts"]:
            assert contact_sensation(contact, you="Wren") == ""

    def test_a_plural_part_takes_a_plural_verb_and_pronoun(self):
        """The subject is the PART, not the person, and body parts are
        routinely plural -- the same agreement `contact_phrase` already carries
        `_part_is_plural` for. Live output before this read "your legs
        registers ... against it"."""
        plural = {"actor": "Reya", "actor_part": "fingers", "target": "Bram",
                  "target_part": "back", "manner": "digging"}

        assert contact_sensation(plural, you="Reya") == (
            "your fingers register Bram's back against them: shifting "
            "pressure, movement and friction, continuous while the contact "
            "holds")
        assert contact_sensation(plural, you="Bram").startswith(
            "your back registers Reya's fingers against it")

    def test_a_slot_holding_an_act_or_a_sound_renders_nothing(self):
        """The Director periodically fills a part slot with something that is
        not a body -- a live ledger held `physical reaction` against
        `laughter`. Rendering it produced a sensation nobody could have. This
        is a floor, not a validator: the record is wrong where it is written."""
        junk = {"actor": "Reya", "actor_part": "physical reaction",
                "target": "Bram", "target_part": "laughter", "manner": "grip"}

        assert contact_sensation(junk, you="Reya") == ""
        assert contact_sensation(junk, you="Bram") == ""

    def test_a_contact_naming_no_parts_still_names_a_body(self):
        whole = {"actor": "Reya", "target": "Bram", "manner": "lean"}

        assert contact_sensation(whole, you="Bram").startswith(
            "your body registers Reya against it")

    def test_identity_resolves_through_the_scene_not_string_equality(self):
        """One being carries a cast display name and a scene entity id at once.
        A contact recorded under one spelling, against a perceiver named by the
        other, would silently match nobody -- leaving a party to a contact
        feeling nothing from it."""
        scene = {
            "positions": {"Reya": "cell", "bram_guard": "cell"},
            "entities": {"bram_guard": {"name": "Bram"}},
            "contacts": [{"actor": "Reya", "actor_part": "palm",
                          "target": "bram_guard", "target_part": "sternum",
                          "manner": "press"}],
        }
        felt = contact_sensation(scene["contacts"][0], you="Bram", scene=scene)

        assert felt.startswith("your sternum registers")


class TestContactSemanticPersistence:

    @staticmethod
    def _scene(contact):
        return {
            "positions": {"Reya": "cell", "Bram": "cell"},
            "contacts": [contact],
        }

    @staticmethod
    def _contact(**changes):
        contact = {
            "actor": "Reya", "actor_part": "blade", "target": "Bram",
            "target_interior": "wound channel", "target_part": "shoulder",
            "manner": "insert",
            "detail": "fully inserted",
        }
        contact.update(changes)
        return contact

    def test_live_press_rewording_cannot_flatten_interior_motion(self):
        """Chat 68 turn 17 described motion but stored settled `press`."""
        scene = apply_contact_ops(self._scene(self._contact()), [{
            **self._contact(manner="press"),
            "detail": "withdrawing and thrusting rhythmically",
        }])

        contact = scene["contacts"][0]
        assert contact["relation"] == "interior"
        assert contact["motion"] == "moving"

    def test_concise_reassertion_does_not_erase_known_interior(self):
        scene = self._scene(self._contact(target_interior="wound channel"))
        reassertion = self._contact()
        reassertion.pop("target_interior")

        updated = apply_contact_ops(scene, [reassertion])

        assert updated["contacts"][0]["target_interior"] == "wound channel"

    def test_interior_to_surface_requires_an_explicit_end(self):
        scene = self._scene(self._contact())
        flattened = apply_contact_ops(scene, [self._contact(
            manner="press", relation="surface", motion="settled")])
        assert flattened["contacts"][0]["relation"] == "interior"

        moved = apply_contact_ops(flattened, [
            {"op": "remove", **self._contact()},
            {"op": "add", **self._contact(
                manner="press", relation="surface", motion="settled")},
        ])
        assert moved["contacts"][0]["relation"] == "surface"

    def test_crossing_replaces_the_boundary_with_downstream_state(self):
        scene = self._scene(self._contact(
            target_interior="outer channel", target_part="inner seal"))

        advanced = apply_contact_ops(scene, [{
            "op": "cross", "actor": "Reya", "actor_part": "blade",
            "target": "Bram", "crossed_target_part": "inner seal",
            "target_interior": "downstream chamber", "target_part": "far wall",
            "manner": "push",
        }])

        assert len(advanced["contacts"]) == 1
        contact = advanced["contacts"][0]
        assert contact["target_interior"] == "downstream chamber"
        assert contact["target_part"] == "far wall"
        assert contact["relation"] == "interior"
        assert contact["motion"] == "moving"
        assert "crossed_target_part" not in contact

    def test_crossing_the_wrong_boundary_fails_closed(self):
        original = self._contact(
            target_interior="outer channel", target_part="inner seal")
        reports = []

        unchanged = apply_contact_ops(self._scene(original), [{
            "op": "cross", "actor": "Reya", "actor_part": "blade",
            "target": "Bram", "crossed_target_part": "other seal",
            "target_interior": "downstream chamber", "target_part": "far wall",
        }], report=reports)

        assert unchanged["contacts"][0]["target_part"] == "inner seal"
        assert reports and "ignored contact crossing" in reports[0]

    def test_crossing_without_a_new_endpoint_does_not_keep_the_old_one(self):
        original = self._contact(
            target_interior="outer channel", target_part="inner seal")

        advanced = apply_contact_ops(self._scene(original), [{
            "op": "cross", "actor": "Reya", "actor_part": "blade",
            "target": "Bram", "crossed_target_part": "inner seal",
            "target_interior": "downstream chamber",
        }])

        assert advanced["contacts"][0]["target_part"] == ""

    def test_cross_cannot_resurrect_an_endpoint_removed_earlier_in_the_beat(self):
        original = self._contact(
            target_interior="outer channel", target_part="inner seal")

        ended = apply_contact_ops(self._scene(original), [
            {"op": "remove", "actor": "Reya", "actor_part": "blade",
             "target": "Bram", "target_part": "inner seal"},
            {"op": "cross", "actor": "Reya", "actor_part": "blade",
             "target": "Bram", "crossed_target_part": "inner seal",
             "target_interior": "downstream chamber", "target_part": "far wall"},
        ])

        assert ended["contacts"] == []


class TestTheDeterministicFloor:

    def test_a_lit_view_that_ignored_the_contact_gets_it_anyway(self):
        """The defect in one assertion: sight was open, the model wrote what it
        saw, and nothing required a word of what was felt."""
        view = _deliver(LIT_VIEW, "Bram")

        assert view.startswith(LIT_VIEW)
        assert "Your sternum registers Reya's palm against it" in view
        assert "Your body registers Reya's blade within your wound channel" in view

    def test_it_subtracts_nothing(self):
        assert LIT_VIEW in _deliver(LIT_VIEW, "Bram")

    def test_a_bystander_receives_no_addition(self):
        assert _deliver(LIT_VIEW, "Wren") == LIT_VIEW

    def test_both_ends_must_be_named_together_to_count_as_rendered(self):
        """Scanning the whole view for each part separately matched a hip in
        one clause against a hand in another and called the contact between
        them delivered."""
        scattered = ("Your palm is open at your side. His sternum rises and "
                     "falls with his breathing.")
        view = _deliver(scattered, "Bram")

        assert "sternum registers Reya's palm" in view

    def test_a_part_name_inside_a_longer_word_is_not_a_match(self):
        scene = {"positions": {"Reya": "deck", "Bram": "deck"}, "entities": {},
                 "contacts": [{"actor": "Reya", "actor_part": "hand",
                               "target": "Bram", "target_part": "hip",
                               "manner": "grip"}]}
        view = _deliver_standing_sensations(
            "The ship handles badly in this weather.", "Bram", scene,
            _standing_contacts_for(scene, "Bram"))

        assert "hip registers Reya's hand" in view

    def test_a_view_that_already_rendered_the_contact_is_left_alone(self):
        """Matched on the two body PARTS, because that is what a paraphrase
        preserves -- a model rendering a palm on a sternum says palm and
        sternum whatever else it rewrites -- while the manner is exactly what
        it rewrites."""
        rendered = ("Her palm is flat and warm on your sternum, and the blade "
                    "sits deep in your shoulder, unmoving.")
        assert _deliver(rendered, "Bram") == rendered

    def test_a_partly_rendered_view_gets_only_the_missing_contact(self):
        partial = "Her palm stays flat against your sternum."
        view = _deliver(partial, "Bram")

        assert view.count("registers") == 1
        assert "within your wound channel" in view

    def test_a_contact_with_no_parts_is_never_appended(self):
        """`your body registers X against it` on every beat of an ordinary
        embrace is noise, and an unmatched clause cannot be checked against the
        view, so this one direction stays biased toward silence."""
        scene = {"positions": {"Reya": "cell", "Bram": "cell"}, "entities": {},
                 "contacts": [{"actor": "Reya", "target": "Bram",
                               "manner": "lean"}]}
        assert _deliver_standing_sensations(
            LIT_VIEW, "Bram", scene,
            _standing_contacts_for(scene, "Bram")) == LIT_VIEW

    def test_no_contacts_means_no_change(self):
        empty = {"positions": {}, "entities": {}, "contacts": []}
        assert _deliver_standing_sensations(LIT_VIEW, "Bram", empty, []) \
            == LIT_VIEW


class TestTheChannelItArrivesOn:
    """Observations are re-derived from the scrubbed view, so the channel is
    read back off the delivered prose rather than trusted from anywhere."""

    def _atoms(self, who):
        view = _deliver("The lamp gutters.", who)
        return _observations_from_clean_views({"player": view})["player"]

    def test_a_surface_contact_arrives_as_touch(self):
        surface = [a for a in self._atoms("Bram")
                   if "sternum registers" in a["observed"]["text"]]

        assert surface and surface[0]["channel"] == "touch"

    def test_an_interior_contact_arrives_as_interoception(self):
        """It fired on 2.4% of the corpus because its vocabulary was distress
        -- pain, nausea, wounds. Interior sensation is interoception whatever
        its valence."""
        interior = [a for a in self._atoms("Bram")
                    if "wound channel" in a["observed"]["text"]]

        assert interior and interior[0]["channel"] == "interoception"

    def test_the_perceiver_is_the_subject_of_their_own_sensation(self):
        """`_SELF_DIRECTED` recognised only agent-first constructions, so a
        percept whose subject is the perceiver's own body was filed as somebody
        else's business."""
        felt = [a for a in self._atoms("Bram") if "registers" in
                a["observed"]["text"]]

        assert felt
        assert all(a["directed_at_self"] for a in felt)


class TestMomentaryResidue:
    """A momentary act's standing record delivers its residue, not the act.

    Live (chat 69 "Horny Story. ⎇49"): a head-kiss recorded at turn 42 with
    motion `moving` stood unaged through five quiet beats -- ageing is
    evidence-gated, correctly -- and `contact_sensation` rendered its stored
    motion every beat, so both parties were told "movement and friction" of a
    kiss four beats gone, while its owner held an ordinary conversation. The
    vocabulary's own contract (CONTACT_MOMENTARY_MANNERS) already promised
    residue rendering; only `contact_phrase` honoured it.
    """

    KISS = {"actor": "Reya", "actor_part": "lips", "target": "Bram",
            "target_part": "forehead", "manner": "kiss",
            "relation": "surface", "motion": "moving", "unasserted": 0}

    def test_a_standing_kiss_is_felt_as_lips_at_rest(self):
        felt = contact_sensation(self.KISS, you="Bram")

        assert "steady pressure" in felt
        assert "movement and friction" not in felt

    def test_both_sides_get_the_residue(self):
        felt = contact_sensation(self.KISS, you="Reya")

        assert "steady pressure" in felt
        assert "movement and friction" not in felt

    def test_an_interior_act_keeps_its_standing_kinematics(self):
        """The boundary, drawn on purpose: an interior contact's enclosure
        persists by definition, so `moving` there is standing kinematics (a
        blade still working in a wound), not the echo of a finished act."""
        blade = {"actor": "Reya", "actor_part": "blade", "target": "Bram",
                 "target_interior": "wound channel", "target_part": "shoulder",
                 "manner": "thrust", "relation": "interior", "motion": "moving"}
        felt = contact_sensation(blade, you="Reya")

        assert "friction along its length" in felt

    def test_a_fluid_event_manner_is_momentary(self):
        """A hedonic release recorded `spray` stood as a moving contact into the
        resting beat that followed and was saved with the scene, so the
        aftercare view reported gushing as current. A spray is an event; the
        matter it moved persists in the substance ledger."""
        from spatial import contact_is_momentary
        spray = {"actor": "Reya", "actor_part": "hand", "target": "Bram",
                 "target_part": "shoulder", "manner": "spray",
                 "relation": "surface", "motion": "moving"}

        assert contact_is_momentary(spray)
        assert "steady pressure" in contact_sensation(spray, you="Bram")

    def test_the_head_word_carries_the_manner(self):
        """A live ledger held manner `dripping fluid` -- the act with its
        object narrated into the slot -- and the exact-match read it as a
        durable hold."""
        from spatial import contact_is_momentary

        assert contact_is_momentary({"manner": "dripping fluid"})
        assert not contact_is_momentary({"manner": "press"})


class TestACavityNamedByItsWallIsStillACavity:
    """A vagina cannot be inside a vagina, and a mind must never be told it is.

    Measured live (chat 71). The ledger stood:

        actor "Elyra Voss" / "vaginal walls"  ->  target "Hinami",
        target_part "hand", target_interior "vaginal canal",
        relation interior, manner clench

    Under this module's fixed direction -- the actor is the party whose part
    goes in, the target encloses it -- that asserts Elyra's vaginal walls
    entering Hinami's vaginal canal. It rendered into Elyra's OWN perception
    view as "Your vaginal walls register Hinami's vaginal canal enclosing
    them", a body part that appears nowhere in the record and a containment
    that is anatomically impossible. The truth was the reverse: Hinami's hand
    was inside her.

    The inversion guard was correct and simply did not know the noun.
    `_part_identity` keeps "vaginal walls" as the kind "vaginal wall" -- right
    for a ledger, where two spellings are two rows, and wrong for the only
    question the fold asks: does this part ENCLOSE?
    """

    RAW = {
        "actor": "Elyra Voss", "actor_part": "vaginal walls",
        "target": "Hinami", "target_part": "hand",
        "target_interior": "vaginal canal",
        "manner": "clench", "relation": "interior", "motion": "moving",
    }

    def test_the_roles_are_folded_to_the_true_direction(self):
        import spatial

        out = spatial._clean_contact(dict(self.RAW), scene={})
        assert out["actor"] == "Hinami" and out["actor_part"] == "hand"
        assert out["target"] == "Elyra Voss"
        assert out["relation"] == "interior"

    def test_neither_party_is_told_a_vagina_encloses_a_vagina(self):
        import spatial

        out = spatial._clean_contact(dict(self.RAW), scene={})
        hers = spatial.contact_sensation(out, you="Elyra Voss", scene={})
        theirs = spatial.contact_sensation(out, you="Hinami", scene={})
        # The enclosed party feels the hand inside her, not her own anatomy
        # entering someone else's identical anatomy.
        assert "Hinami's hand within your vaginal canal" in hers
        assert "your vaginal walls register" not in hers.casefold()
        # And the entering party feels the enclosure.
        assert "your hand registers" in theirs
        assert "enclosing it" in theirs

    def test_the_other_wall_and_canal_spellings_fold_too(self):
        import spatial

        for part in ("vaginal canal", "anal canal", "rectal wall",
                     "throat wall"):
            raw = dict(self.RAW, actor_part=part, target_interior="")
            out = spatial._clean_contact(raw, scene={})
            assert out["actor"] == "Hinami", part

    def test_an_entering_part_is_never_folded(self):
        """The guard must not reach a record already stated from the entering
        side -- a tongue or a finger enters far more often than it encloses,
        which is why neither is in the cavity vocabulary."""
        import spatial

        raw = dict(self.RAW, actor="Hinami", actor_part="tongue",
                   target="Elyra Voss", target_part="outer labia",
                   target_interior="")
        out = spatial._clean_contact(raw, scene={})
        assert out["actor"] == "Hinami" and out["actor_part"] == "tongue"


def test_mutual_penetration_survives_as_two_contacts():
    """Both directions at once, which is an ordinary thing for bodies to do
    and was being lost.

    Measured live (chat 71, turns 20-30). `cock -> Hinami/vaginal canal`
    stood from turn 20. At turn 29 the resolve added the inverted record
    `Elyra "vaginal walls" -> Hinami "hand", interior` -- and at the next
    checkpoint the cock contact was GONE, with no remove op naming it. Two
    interior contacts between the same pair, one displacing the other.

    Read correctly the two are not rivals: Hinami's hand is inside Elyra
    while Elyra's cock is inside Hinami. Once the inverted record folds to
    its true direction the pair no longer collides, and both stand -- which
    is why the fold matters beyond the sentence it was fixing. Before it,
    Elyra spent the beat registering nothing about being inside Hinami,
    because the contact had been deleted.
    """
    import spatial

    scene = {"contacts": [], "positions": {"Elyra Voss": "r", "Hinami": "r"}}
    spatial.apply_contact_ops(scene, [
        {"op": "add", "actor": "Elyra Voss", "actor_part": "cock",
         "target": "Hinami", "target_interior": "vaginal canal",
         "target_part": "", "manner": "rest", "relation": "interior"},
        {"op": "add", "actor": "Elyra Voss", "actor_part": "vaginal walls",
         "target": "Hinami", "target_part": "hand",
         "target_interior": "vaginal canal", "manner": "clench",
         "relation": "interior"},
    ])
    contacts = scene["contacts"]
    assert len(contacts) == 2, contacts
    directions = {(c["actor"], c["actor_part"]) for c in contacts}
    assert ("Elyra Voss", "cock") in directions
    assert ("Hinami", "hand") in directions


def test_a_body_with_both_anatomies_registers_both_at_once():
    """Elyra is futanari: she encloses with one part while being enclosed in
    another, in the same beat, and Hinami is attending to both.

    This is the live case (chat 71) that the inverted record destroyed. The
    bad row claimed Elyra's vaginal walls were ENTERING Hinami; being a
    second interior contact between the same pair, it displaced the standing
    `cock -> Hinami` -- so a body with two sets of anatomy could only ever
    register one of them, and the one it kept was the impossible one.

    Nothing here is exotic to the model: two interior contacts pointing
    opposite ways between two bodies, plus a surface contact. The engine
    just has to keep the directions straight.
    """
    import spatial

    scene = {"contacts": [], "positions": {"Elyra Voss": "r", "Hinami": "r"}}
    spatial.apply_contact_ops(scene, [
        {"op": "add", "actor": "Elyra Voss", "actor_part": "cock",
         "target": "Hinami", "target_interior": "vaginal canal",
         "target_part": "", "manner": "thrust", "relation": "interior"},
        {"op": "add", "actor": "Elyra Voss", "actor_part": "vaginal walls",
         "target": "Hinami", "target_part": "hand",
         "target_interior": "vaginal canal", "manner": "clench",
         "relation": "interior"},
        {"op": "add", "actor": "Hinami", "actor_part": "thumb",
         "target": "Elyra Voss", "target_part": "clit", "manner": "grind",
         "relation": "surface"},
    ])
    assert len(scene["contacts"]) == 3, scene["contacts"]

    felt = {who: [spatial.contact_sensation(c, you=who, scene=scene)
                  for c in scene["contacts"]]
            for who in ("Elyra Voss", "Hinami")}
    hers = " | ".join(s for s in felt["Elyra Voss"] if s)
    theirs = " | ".join(s for s in felt["Hinami"] if s)

    # She feels her cock enclosed AND her own canal filled -- both, not one.
    assert "your cock registers Hinami's vaginal canal enclosing it" in hers
    assert "Hinami's hand within your vaginal canal" in hers
    assert "your clit registers Hinami's thumb" in hers
    # And Hinami feels the mirror of each.
    assert "Elyra Voss's cock within your vaginal canal" in theirs
    assert "your hand registers Elyra Voss's vaginal canal enclosing it" in theirs
    # Nobody is told a cavity entered a cavity.
    assert "vaginal walls register" not in hers.casefold()
