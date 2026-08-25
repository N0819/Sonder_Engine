"""MASTER-036 / docs/UNBUILT.md 1.10: momentary entity state must not outlive
its beat.

`_merge_entity` merges `state` key-wise and the doctrine is silence-is-never-
an-erasure -- right for a held wrench, wrong for a breath: an omitted key
survived forever, and `composer.body_state_percept` reads `activity` back to
the subject's OWN mind (interoception, source "you"), so a body told once it
was running kept perceiving itself running and each later model call received
that as current evidence. Measured stuck verbatim for dozens of beats:
`"breath": "caught"`, `"voice_quality": "held_breath_steadying"`.

The fix is a narrow transient vocabulary that expires on the next merge unless
re-asserted WITH A CHANGED VALUE -- NOT a rejection of undeclared keys (`state`
is deliberately open free text; an earlier skip-the-update attempt was reverted
as durable corruption) and NOT an expiry of durable configuration (posture,
held items, transit all keep today's merge). `activity` is deliberately NOT in
the vocabulary yet: tests/test_body_position.py pins it never-touched as
load-bearing standing state, so expiring it means first deciding that
contract -- the remaining half of docs/UNBUILT.md 1.10.

Narrowed again 2026-08-25 after chat 88 t53-67, where a beat-old momentary key
stood for THIRTEEN beats through the expiry above: the hand owning `entities`
re-emitted the state blob byte for byte nearly every turn, and a re-emission
counted as an assertion. Two rules answer it -- an echo of a value that was
already standing is silence, and the vocabulary is a stated class (exact keys
plus the `_action`/`_motion`/`_sensation` process families) rather than three
names some story happened to write.
"""

from __future__ import annotations

from world.spatial import merge_scene_with_diff


def _scene():
    return {
        "rooms": {"cell": {"name": "Cell", "adjacent": []}},
        "positions": {"mora_uid": "cell"},
        "entities": {"mora_uid": {
            "kind": "person", "name": "Mora",
            "state": {
                "activity": "running for the stair",
                "breath": "caught",
                "voice_quality": "held_breath_steadying",
                "posture": "crouched low",
                "held_items": ["wrench"],
                "transit": {"phase": "boarding"},
            },
        }},
        "attire": {}, "overlays": {},
    }


def _state(merged):
    return merged["entities"]["mora_uid"]["state"]


class TestExpiry:
    def test_momentary_keys_expire_when_the_diff_is_silent(self):
        merged = merge_scene_with_diff(_scene(), {})
        for key in ("breath", "voice_quality"):
            assert key not in _state(merged), key

    def test_they_expire_even_when_the_entity_itself_is_untouched(self):
        """The entity the diff is silent about is exactly the one whose
        caught breath has gone stale -- expiry cannot be scoped to entities
        the diff happens to mention."""
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"someone_else": {"kind": "person", "name": "Tavi"}}})
        assert "breath" not in _state(merged)

    def test_durable_state_keeps_the_silence_doctrine(self):
        merged = merge_scene_with_diff(_scene(), {})
        state = _state(merged)
        assert state["posture"] == "crouched low"
        assert state["held_items"] == ["wrench"]
        assert state["transit"] == {"phase": "boarding"}
        # `activity` deliberately durable for now: pinned load-bearing by
        # tests/test_body_position.py; the remaining half of UNBUILT 1.10.
        assert state["activity"] == "running for the stair"

    def test_reassertion_carries_it_forward(self):
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"mora_uid": {
                "state": {"breath": "steadying now"}}}})
        assert _state(merged)["breath"] == "steadying now"

    def test_assertion_by_display_name_reaches_the_id_keyed_entity(self):
        """A diff may key one body by id, name or alias; expiry must honour
        whichever spelling the assertion used."""
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"Mora": {"state": {"breath": "ragged"}}}})
        entities = merged["entities"]
        held = [e.get("state", {}).get("breath")
                for e in entities.values() if isinstance(e, dict)]
        assert "ragged" in held


class TestEchoIsSilence:
    """A re-emission of a value that was ALREADY standing is not an assertion.

    Provenance: chat 88 turns 53-67. Expiry was already in place and did
    nothing, because the cheapest model behaviour there is -- copying the
    payload's state blob back into the diff unchanged -- read as a fresh
    assertion every beat.
    """

    def test_a_verbatim_echo_of_a_standing_value_still_expires(self):
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"mora_uid": {"state": {"breath": "caught"}}}})
        assert "breath" not in _state(merged)

    def test_an_echo_does_not_drag_the_other_momentary_keys_along(self):
        """One echoed key is silence about that key only -- a second key
        changed in the same diff is still an assertion."""
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"mora_uid": {"state": {
                "breath": "caught",
                "voice_quality": "steadied"}}}})
        state = _state(merged)
        assert "breath" not in state
        assert state["voice_quality"] == "steadied"

    def test_a_momentary_key_first_set_this_beat_survives_its_own_merge(self):
        scene = _scene()
        scene["entities"]["mora_uid"]["state"].pop("breath")
        merged = merge_scene_with_diff(scene, {
            "entities": {"mora_uid": {"state": {"breath": "caught"}}}})
        assert _state(merged)["breath"] == "caught"

    def test_an_echo_keyed_by_display_name_is_still_an_echo(self):
        """The echo comparand folds id, name and alias exactly as the
        assertion side does, or a diff that keys by name defeats the rule."""
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"Mora": {"state": {"breath": "caught"}}}})
        breaths = [e.get("state", {}).get("breath")
                   for e in merged["entities"].values()
                   if isinstance(e, dict)]
        assert not any(breaths)


class TestProcessKeys:
    """The vocabulary is a stated class, not a list of names.

    `state` is open free text, so a fixed allowlist can only name the
    momentary keys some story already wrote. Chat 88's were
    `throat_action`, `tongue_action` and `jaw_motion`; none was reachable.
    """

    def _with(self, key, value="sweeping upward"):
        scene = _scene()
        scene["entities"]["mora_uid"]["state"][key] = value
        return scene

    def test_a_process_suffix_key_lives_the_beat_that_set_it(self):
        merged = merge_scene_with_diff(self._with("arm_motion"), {
            "entities": {"mora_uid": {
                "state": {"arm_motion": "sweeping downward"}}}})
        assert _state(merged)["arm_motion"] == "sweeping downward"

    def test_a_process_suffix_key_dies_on_a_silent_merge(self):
        for key in ("arm_motion", "hand_action", "skin_sensation"):
            merged = merge_scene_with_diff(self._with(key), {})
            assert key not in _state(merged), key

    def test_a_process_suffix_key_dies_on_a_verbatim_echo(self):
        merged = merge_scene_with_diff(self._with("arm_motion"), {
            "entities": {"mora_uid": {
                "state": {"arm_motion": "sweeping upward"}}}})
        assert "arm_motion" not in _state(merged)

    def test_the_two_added_exact_keys_expire_on_silence(self):
        for key in ("expression", "gaze"):
            merged = merge_scene_with_diff(
                self._with(key, "fixed on the door"), {})
            assert key not in _state(merged), key

    def test_a_thing_named_with_a_process_shaped_word_is_not_a_process(self):
        """The suffix families fail OPEN on purpose: `_register` names a
        till or a ledger as often as a reading, and deleting authored
        configuration is the worse failure of the two."""
        merged = merge_scene_with_diff(
            self._with("shift_register", "loaded"), {})
        assert _state(merged)["shift_register"] == "loaded"

    def test_configuration_still_survives_silence_beside_them(self):
        merged = merge_scene_with_diff(self._with("arm_motion"), {})
        state = _state(merged)
        assert state["posture"] == "crouched low"
        assert state["held_items"] == ["wrench"]
        assert state["transit"] == {"phase": "boarding"}
        assert state["activity"] == "running for the stair"


class TestWhatTheOwnMindStillReads:
    def test_the_interoception_percept_survives_the_sweep(self):
        """Entity state feeds `composer.body_state_percept` (the subject's
        own interoception, source "you"); the sweep must take only the
        momentary keys, never the durable body facts the percept renders."""
        from agents.composer import body_state_percept

        merged = merge_scene_with_diff(_scene(), {})
        percept = body_state_percept(_state(merged))
        assert percept is not None
        assert percept.data["posture"] == "crouched low"
        assert percept.data["held_items"] == ["wrench"]


class TestEchoIsSilenceIsSticky:
    """An echo must cost the key its life, not make it blink.

    The first form of this rule compared the incoming value only against the
    value STANDING in the scene -- and expiry deletes exactly that value, so
    the next identical echo found nothing standing, re-established the key,
    and the echo after that expired it again. Measured on the first form:
    the same diff merged six times running gave
    {'gaze': 'downcast'} / {} / {'gaze': 'downcast'} / {} / ... forever.
    That is worse than the stale value it replaced, and it lands on exactly
    the input the rule was built for (chat 88 turns 53-67, a hand re-emitting
    its whole state blob verbatim nearly every beat).

    The comparand is therefore what was last ASSERTED, not what is standing:
    a momentary value suppressed as an echo is remembered under
    `expired_entity_state`, so every later echo of it is silence too. The
    memory lives only as long as the echoing does -- a beat that says nothing
    about the key releases it, and the next write of that value is a fresh
    assertion again.
    """

    def _echo(self, times, key="gaze", value="downcast"):
        scene = _scene()
        scene["entities"]["mora_uid"]["state"][key] = value
        seen = []
        for _ in range(times):
            scene = merge_scene_with_diff(scene, {
                "entities": {"mora_uid": {"state": {key: value}}}})
            seen.append(_state(scene).get(key))
        return scene, seen

    def test_a_repeated_identical_echo_never_re_establishes_the_key(self):
        _, seen = self._echo(6)
        assert seen == [None] * 6, seen

    def test_the_same_holds_for_a_process_suffix_key(self):
        _, seen = self._echo(4, "arm_motion", "sweeping upward")
        assert seen == [None] * 4, seen

    def test_an_echo_keyed_by_display_name_stays_silent_too(self):
        """The memory is folded over id, name and alias like the assertion
        side, so switching spelling mid-run cannot revive the key.

        Two beats, not more: `_dedup_duplicate_entity_keys` rekeys the
        record to whichever spelling the diff used, and a body whose id key
        has been replaced by its name no longer answers to the id at all --
        older behaviour than this rule and not what it is pinning.
        """
        scene = _scene()
        for spelling in ("mora_uid", "Mora"):
            scene = merge_scene_with_diff(scene, {
                "entities": {spelling: {"state": {"breath": "caught"}}}})
            assert not any(
                (e.get("state") or {}).get("breath")
                for e in scene["entities"].values() if isinstance(e, dict)
            ), spelling

    def test_a_changed_value_is_still_an_assertion_after_any_echoes(self):
        scene, _ = self._echo(3)
        merged = merge_scene_with_diff(scene, {
            "entities": {"mora_uid": {"state": {"gaze": "levelled"}}}})
        assert _state(merged)["gaze"] == "levelled"

    def test_a_beat_of_silence_releases_the_memory(self):
        """Suppression is not a permanent ban on a word. A beat that does
        not mention the key at all ends the echo run, so writing that value
        again is a body doing the thing again, not a payload copied back."""
        scene, _ = self._echo(3)
        scene = merge_scene_with_diff(scene, {})
        merged = merge_scene_with_diff(scene, {
            "entities": {"mora_uid": {"state": {"gaze": "downcast"}}}})
        assert _state(merged)["gaze"] == "downcast"

    def test_the_memory_is_carried_on_the_scene_and_is_bounded(self):
        """It is scene state because a pure merge has nowhere else to keep
        it, and it holds one value per momentary key per echoing body --
        nothing durable, nothing that grows with the story's length."""
        scene, _ = self._echo(3)
        assert scene["expired_entity_state"]["mora_uid"] == {
            "gaze": "downcast"}
        quiet = merge_scene_with_diff(scene, {})
        assert not quiet.get("expired_entity_state")

    def test_a_body_that_leaves_the_scene_takes_its_memory_with_it(self):
        scene, _ = self._echo(3)
        gone = merge_scene_with_diff(scene, {"remove_entities": ["mora_uid"]})
        gone = merge_scene_with_diff(gone, {})
        assert not gone.get("expired_entity_state")
