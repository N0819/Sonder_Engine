"""The deterministic composer: firewall properties proven on the IR.

These tests assert the information boundary on `Percept` lists and the
decision-free renderer -- not by regex over prose after the fact, but on the
structured admission decisions themselves (design_notes/03 section 1.1: the
invariant is that no Percept field carries a fact the observer has no
channel to). Fast tier: no database, no model.
"""

from __future__ import annotations

import agents.composer as composer
import agents.perception as perception


def _scene(positions=None, rooms=None, **extra):
    scene = {
        "location": "Test House",
        "time": "day",
        "rooms": rooms or {
            "study": {"name": "The Study", "adjacent": []},
        },
        "positions": positions or {"Alice": "study", "Hinami": "study"},
        "entities": {}, "attire": {}, "overlays": {},
    }
    scene.update(extra)
    return scene


def _stranger(name="Hinami",
              appearance="Hinami, a fox-eared young woman with six tails, "
                         "wearing a red obi"):
    return {"name": name, "room": "study", "appearance": appearance,
            "aliases": [], "disguise_known_to": None}


# ---------------------------------------------------------------------------
# Layer A: admission
# ---------------------------------------------------------------------------

def test_sealed_speakers_words_never_reach_bystander_ir():
    """A voice coming out through a body's mass arrives as a fragment at
    most -- and the fragment percept's data holds ONLY the fragment, never
    the full quote body, so no downstream consumer can outrun the ear."""
    rel = {"same_room": True, "source_enclosed": True}
    entry = {"speaker": "Mara", "text": "The ledger is under the floor",
             "volume": "whisper"}
    assert composer.speech_percept(
        entry, rel, "Alice", display="Mara", can_see=False) is None

    entry["volume"] = "normal"
    percept = composer.speech_percept(
        entry, rel, "Alice", display="Mara", can_see=False)
    assert percept is not None
    assert percept.fidelity == "fragment"
    assert "body" not in percept.data
    assert "ledger" not in str(percept.data.get("fragment", "")).casefold() \
        or "under the floor" not in str(percept.data.get("fragment", ""))


def test_enclosed_listener_hears_nothing_quiet():
    rel = {"same_room": True, "enclosed_from_source": True}
    entry = {"speaker": "Mara", "text": "Quiet words", "volume": "normal",
             "intended_target": "Alice"}
    # Even ADDRESSED speech is not shape-rescued through an enclosure.
    assert composer.speech_percept(
        entry, rel, "Alice", display="Mara", can_see=False) is None


def test_concealed_line_never_admitted():
    rel = {"same_room": True, "barrier": "open"}
    base = {"speaker": "Mara", "text": "the vial goes in the sleeve",
            "volume": "normal", "visibility": "concealed"}
    # Empty conceal_from: hidden from every non-actor.
    assert composer.speech_percept(
        dict(base, conceal_from=[]), rel, "Alice",
        display="Mara", can_see=True) is None
    # Explicitly concealed from this observer.
    assert composer.speech_percept(
        dict(base, conceal_from=["Alice"]), rel, "Alice",
        display="Mara", can_see=True) is None
    # Concealed from somebody ELSE: this observer is a legitimate audience.
    percept = composer.speech_percept(
        dict(base, conceal_from=["Bob"]), rel, "Alice",
        display="Mara", can_see=True)
    assert percept is not None and percept.data["body"]


def test_comm_transmission_reaches_only_its_addressee():
    rel = {"barrier": "unknown"}          # out of all physical earshot
    line = {"speaker": "Mara", "text": "Come to the bridge",
            "volume": "normal", "medium": "comm", "intended_target": "Alice"}
    to_alice = composer.speech_percept(
        line, rel, "Alice", display="a voice", can_see=False)
    assert to_alice is not None and to_alice.data["level"] == "full"
    bystander = composer.speech_percept(
        line, rel, "Bob", display="a voice", can_see=False)
    assert bystander is None


def test_no_sight_no_act_percept():
    """An action is visible or it is nothing -- a touch-only or unseen
    source contributes no event surface at all."""
    scene = _scene()
    event = {"type": "action", "observable": "slides a knife from her belt",
             "visibility": "overt"}
    percept = composer.act_percept(
        scene, event, "Alice", "Mara", {"same_room": True},
        display="the fox-eared woman", can_see=False)
    assert percept is None


def test_mental_beat_is_imperceptible():
    scene = _scene()
    event = {"type": "action", "observable": "", "attempt": "recall the runes",
             "visibility": "overt"}
    assert composer.act_percept(
        scene, event, "Alice", "Hinami", {"same_room": True},
        display="the fox-eared woman", can_see=True) is None


def test_action_target_body_pronouns_follow_the_named_target():
    """An actor and target may share pronouns without swapping bodies.

    The observable names Alice once, then uses ``her`` for Alice's body.  In
    Alice's own view both references must remain Alice/second-person; the
    omitted predicate subject is still Mara.
    """
    scene = _scene()
    event = {
        "type": "action", "visibility": "overt", "targets": ["Alice"],
        "observable": (
            "guides Alice's hand open between her fingers, "
            "thumb pressing against her palm"),
    }
    percept = composer.act_percept(
        scene, event, "Alice", "Mara", {"same_room": True},
        display="Mara", can_see=True, self_forms=["Alice"],
        self_pronouns={"subject": "she", "object": "her",
                       "possessive": "her"})

    assert percept is not None
    assert percept.data["surface"] == (
        "guides your hand open between your fingers, "
        "thumb pressing against your palm")


def test_action_target_repair_does_not_claim_the_actors_own_body():
    scene = _scene()
    event = {
        "type": "action", "visibility": "overt", "targets": ["Alice"],
        "observable": (
            "takes Alice's hand and draws it toward her own chest"),
    }
    percept = composer.act_percept(
        scene, event, "Alice", "Mara", {"same_room": True},
        display="Mara", can_see=True, self_forms=["Alice"],
        self_pronouns={"subject": "she", "object": "her",
                       "possessive": "her"})

    assert percept is not None
    assert percept.data["surface"] == (
        "takes your hand and draws it toward her own chest")


def test_action_target_body_pronouns_cross_anatomical_modifiers_only():
    scene = _scene()
    event = {
        "type": "action", "visibility": "overt", "targets": ["Alice"],
        "observable": (
            "supports Alice at her injured lower back while checking her bag"),
    }
    percept = composer.act_percept(
        scene, event, "Alice", "Mara", {"same_room": True},
        display="Mara", can_see=True, self_forms=["Alice"],
        self_pronouns={"subject": "she", "object": "her",
                       "possessive": "her"})

    assert percept.data["surface"] == (
        "supports you at your injured lower back while checking her bag")


def test_action_target_body_pronouns_stop_at_another_named_body():
    scene = _scene()
    event = {
        "type": "action", "visibility": "overt",
        "targets": ["Alice", "Beth"],
        "observable": (
            "steadies Alice at her shoulder, then turns to Beth and takes her hand"),
    }
    percept = composer.act_percept(
        scene, event, "Alice", "Mara", {"same_room": True},
        display="Mara", can_see=True, self_forms=["Alice"],
        other_forms=["Beth"],
        self_pronouns={"subject": "she", "object": "her",
                       "possessive": "her"})

    assert percept.data["surface"] == (
        "steadies you at your shoulder, then turns to Beth and takes her hand")


def test_unrecognized_actor_never_named_in_ir():
    scene = _scene()
    body = _stranger()
    display_map = composer.observer_display_map(scene, "Alice", [body], {})
    label = display_map["Hinami"]
    assert "hinami" not in label.casefold()
    percepts = composer.presence_percepts(scene, "Alice", [body], display_map)
    assert percepts, "a lit co-located body must be admitted as presence"
    for p in percepts:
        assert "hinami" not in p.source_label.casefold()
        assert "hinami" not in str(p.data).casefold()
    # The name never rides ANY record field -- not even as bookkeeping. The
    # first-mention ledger uses an opaque body key instead.
    appearance = composer.appearance_percept(
        "Hinami", label, "a fox-eared young woman with six tails")
    whole = appearance.source_label + str(appearance.data)
    assert "hinami" not in whole.casefold()


def test_recognition_uses_known_ledger():
    scene = _scene()
    body = _stranger()
    display_map = composer.observer_display_map(
        scene, "Alice", [body], {"Alice": ["Hinami"]})
    assert display_map["Hinami"] == "Hinami"


def test_no_room_means_no_environment_percept():
    """A mind in unloaded space perceives nothing here -- the old path's
    fabricated "You are in an unspecified area." (812 identical memory rows)
    must be impossible at the IR level."""
    assert composer.environment_percept(None, None) is None
    assert composer.environment_percept("", "") is None
    assert composer.environment_percept("r9", "an unspecified area") is None
    assert composer.environment_percept("study", "The Study") is not None


# ---------------------------------------------------------------------------
# Referring expressions
# ---------------------------------------------------------------------------

def test_stranger_labels_distinguish_by_appearance():
    bodies = [
        ("Hinami", "a fox woman with six tails and amber eyes", []),
        ("Kuzunoha", "a fox woman with a single silver tail", []),
    ]
    labels = composer.assign_stranger_labels(bodies)
    assert labels["Hinami"] != labels["Kuzunoha"]
    assert "(2)" not in labels["Hinami"] and "(2)" not in labels["Kuzunoha"]
    assert "hinami" not in labels["Hinami"].casefold()
    assert "kuzunoha" not in labels["Kuzunoha"].casefold()
    # The distinguishing feature survives into at least one label.
    assert "six" in labels["Hinami"] or "silver" in labels["Kuzunoha"]


def test_identical_appearances_fall_back_to_suffix():
    bodies = [
        ("Guard A", "a masked guard in grey livery", []),
        ("Guard B", "a masked guard in grey livery", []),
    ]
    labels = composer.assign_stranger_labels(bodies)
    assert labels["Guard A"] != labels["Guard B"]


# ---------------------------------------------------------------------------
# Layer B: three render modes over one percept list
# ---------------------------------------------------------------------------

def _sample_percepts():
    env = composer.environment_percept("study", "The Study",
                                       "Dust sheets over the furniture.")
    scene = _scene()
    body = _stranger()
    display_map = composer.observer_display_map(scene, "Alice", [body], {})
    presence = composer.presence_percepts(scene, "Alice", [body], display_map)
    speech = composer.speech_percept(
        {"speaker": "Hinami", "text": "You should not have come",
         "volume": "normal"},
        {"same_room": True, "barrier": "open"}, "Alice",
        display=display_map["Hinami"], can_see=True, order_key=0)
    return [env] + presence + [speech]


def test_character_mode_renders_full_standing_state_every_beat():
    percepts = _sample_percepts()
    first = composer.render_view(percepts, mode="character")
    again = composer.render_view(
        percepts, mode="character", prev_standing=frozenset(first.standing_keys),
        prev_described=frozenset(first.described))
    assert "You are in The Study." in again.text
    assert "You should not have come" in again.text


def test_player_mode_renders_delta_only():
    percepts = _sample_percepts()
    first = composer.render_view(percepts, mode="player")
    assert "You are in The Study." in first.text
    second = composer.render_view(
        percepts, mode="player", prev_standing=frozenset(first.standing_keys),
        prev_described=frozenset(first.described))
    assert "You are in The Study." not in second.text
    assert "You should not have come" in second.text


def test_look_intent_rerenders_everything():
    percepts = _sample_percepts()
    first = composer.render_view(percepts, mode="player")
    look = composer.render_view(
        percepts, mode="player", prev_standing=frozenset(first.standing_keys),
        prev_described=frozenset(first.described), full_render=True)
    assert "You are in The Study." in look.text


def test_changed_standing_state_rerenders_in_delta_mode():
    """The dedupe key hashes the content, so change detection is free: a
    dark room is not the lit room restated."""
    lit = composer.environment_percept("study", "The Study", light="normal")
    dark = composer.environment_percept("study", "The Study", light="dark")
    first = composer.render_view([lit], mode="player")
    second = composer.render_view(
        [dark], mode="player", prev_standing=frozenset(first.standing_keys))
    assert "You are in The Study." in second.text
    assert "dark" in second.text.casefold()


def test_full_appearance_pruning_is_player_only():
    """Page compression must not subtract evidence from an NPC mind."""
    appearance = composer.appearance_percept(
        "Hinami", "the fox woman with six tails",
        "a fox-eared young woman with six tails, wearing a red obi")
    first = composer.render_view([appearance], mode="player")
    assert "six tails" in first.text
    again = composer.render_view(
        [appearance], mode="player",
        prev_described=frozenset(first.described))
    assert again.text == ""

    npc = composer.render_view(
        [appearance], mode="character",
        prev_described=frozenset(first.described))
    assert "six tails" in npc.text
    assert "red obi" in npc.text

    changed = composer.appearance_percept(
        "Hinami", "the fox woman with six tails",
        "a fox-eared young woman, obi torn, fur soaked", force=True)
    third = composer.render_view(
        [changed], mode="player", prev_described=frozenset(first.described))
    assert "soaked" in third.text


def test_render_is_deterministic():
    percepts = _sample_percepts()
    a = composer.render_view(percepts, mode="character")
    b = composer.render_view(percepts, mode="character")
    assert a.text == b.text


def test_render_takes_no_scene():
    """Layer B's signature takes percepts and mode parameters, nothing else
    -- the renderer structurally cannot reopen the scene bypass."""
    import inspect
    params = inspect.signature(composer.render_view).parameters
    assert "scene" not in params and "sc" not in params and "ctx" not in params


def test_unseen_speaker_renders_as_heard():
    percept = composer.speech_percept(
        {"speaker": "Mara", "text": "Who goes there", "volume": "normal"},
        {"barrier": "open_door", "same_room": False}, "Alice",
        display="a voice", can_see=False, order_key=0)
    assert percept is not None
    rendered = composer.render_view([percept], mode="player")
    assert rendered.text.startswith("You hear")
    assert "says:" not in rendered.text  # bare-infinitive heard form


def test_sudden_event_chain_leads_the_view():
    env = composer.environment_percept("study", "The Study")
    scene = _scene()
    act = composer.act_percept(
        scene, {"type": "action", "observable": "lunges across the table",
                "visibility": "overt", "event_id": "e1"},
        "Alice", "Hinami", {"same_room": True},
        display="the fox woman", can_see=True, order_key=0)
    rendered = composer.render_view([env, act], mode="character")
    assert rendered.text.casefold().startswith("the fox woman lunges")


# ---------------------------------------------------------------------------
# Memory mode: mint from the IR
# ---------------------------------------------------------------------------

def test_all_standing_unchanged_is_a_non_event():
    percepts = _sample_percepts()
    standing_only = [p for p in percepts if p.order_key is None]
    view = composer.render_view(standing_only, mode="character")
    content, gist, entities = composer.render_episode(
        standing_only,
        prev_standing=frozenset(view.standing_keys),
        prev_described=frozenset(view.described))
    assert content == "" and gist == "" and entities == []


def test_episode_leads_with_the_event_not_the_room():
    """Embedding models over-weight the first sentence; an episode must
    never open with invariant scene-setting."""
    percepts = _sample_percepts()
    content, gist, entities = composer.render_episode(percepts)
    assert content
    assert not content.startswith("I was in")
    assert "You should not have come" in content
    # The room change trails, in first person and past tense.
    assert "I was in The Study." in content


def test_room_change_alone_is_still_an_episode():
    env = composer.environment_percept("vault", "the Vault Antechamber")
    content, gist, entities = composer.render_episode([env])
    assert content == "I was in the Vault Antechamber."


def test_episode_never_exceeds_the_view():
    """Rule 03 section 5.2: the episode consumes the same fidelity-degraded
    surfaces the view consumed. Every quote and label token in the episode
    must appear in the full-mode view of the same percepts."""
    percepts = _sample_percepts()
    view = composer.render_view(percepts, mode="character")
    content, gist, entities = composer.render_episode(percepts)
    import re
    view_tokens = set(re.findall(r"[a-z0-9']+", view.text.casefold()))
    for quote in re.findall(r'"([^"]+)"', content):
        for token in re.findall(r"[a-z0-9']+", quote.casefold()):
            assert token in view_tokens, (token, view.text)
    for entity in entities:
        for token in re.findall(r"[a-z0-9']+", entity.casefold()):
            assert token in view_tokens, (entity, view.text)


def test_fragment_episode_carries_only_the_fragment():
    percept = composer.speech_percept(
        {"speaker": "Mara", "text": "Meet me behind the granary at midnight",
         "volume": "normal"},
        {"same_room": True, "source_enclosed": True}, "Alice",
        display="a voice", can_see=False, order_key=0)
    assert percept.fidelity == "fragment"
    content, gist, entities = composer.render_episode([percept])
    assert "muffled" in content
    assert "Meet me behind the granary at midnight" not in content


def test_episode_entities_are_typed_labels_not_scraped_prose():
    scene = _scene()
    body = _stranger()
    display_map = composer.observer_display_map(scene, "Alice", [body], {})
    speech = composer.speech_percept(
        {"speaker": "Hinami", "text": "Stay back", "volume": "normal"},
        {"same_room": True, "barrier": "open"}, "Alice",
        display=display_map["Hinami"], can_see=True, order_key=0)
    content, gist, entities = composer.render_episode([speech])
    assert entities == [display_map["Hinami"]]
    assert all("hinami" not in e.casefold() for e in entities)


# ---------------------------------------------------------------------------
# Observations: projected from the IR
# ---------------------------------------------------------------------------

def test_observation_merge_keys_on_the_delivery_verdict():
    """Aggregation must key on the channel/visibility verdict: merging a
    degraded percept into a full one would launder the boundary. Two
    same-channel atoms with different fidelity classes stay separate."""
    full = composer.speech_percept(
        {"speaker": "Mara", "text": "Plainly heard words", "volume": "normal"},
        {"same_room": True, "barrier": "open"}, "Alice",
        display="Mara", can_see=True, order_key=0)
    muffled = composer.speech_percept(
        {"speaker": "Bob", "text": "Sealed away muttering words here",
         "volume": "normal"},
        {"same_room": True, "source_enclosed": True}, "Alice",
        display="a voice", can_see=False, order_key=1)
    rendered = composer.render_view([full, muffled], mode="character")
    atoms = composer.observations_from_render("player", rendered)
    hearing = [a for a in atoms if a["channel"] == "hearing"]
    assert len(hearing) == 2
    # "rendered" is the resting fidelity and is omitted (absent means the
    # default -- see OBSERVATION_DEFAULTS); "ambiguous" is signal and stays.
    fidelities = {a.get("fidelity", "rendered") for a in hearing}
    assert fidelities == {"rendered", "ambiguous"}


def test_observations_text_is_the_rendered_span():
    percepts = _sample_percepts()
    rendered = composer.render_view(percepts, mode="character")
    atoms = composer.observations_from_render("7", rendered)
    assert atoms
    for atom in atoms:
        assert atom["observed"]["text"] in rendered.text
        # The perceiver is named once, by the citation id; a separate
        # perceiver_id repeating it is wrapper the payload no longer carries
        # (measured: it matched the id's perceiver in 100% of 1,692 stored
        # observations).
        assert atom["observation_id"].startswith("current:7:")
        assert "perceiver_id" not in atom
    channels = {a["channel"] for a in atoms}
    assert "hearing" in channels and "sight" in channels


def test_observation_wrapper_omits_only_resting_defaults():
    """The advisory axes are context for the model's appraisal, and nothing
    deterministic consumes them (docs/guides/PIPELINE.md) -- so a resting default
    (intensity 0.35 / suddenness 0.1 / ambiguity 0.15 / fidelity "rendered" /
    source_atom_id "current" / directed_at_self false, near-constant across
    99%/99%/89%/99%/100% of 1,692 stored observations) carries no information
    and is omitted, while every non-default value survives byte-for-byte.
    Ids, text and channel are never trimmed: they are the citation namespace
    and the content."""
    resting = {
        "observation_id": "current:7:0", "perceiver_id": "7",
        "source_atom_id": "current", "channel": "sight",
        "fidelity": "rendered", "observed": {"text": "A door stands open."},
        "intensity": 0.35, "suddenness": 0.1, "ambiguity": 0.15,
        "directed_at_self": False,
    }
    assert composer.compact_observation(resting) == {
        "observation_id": "current:7:0", "channel": "sight",
        "observed": {"text": "A door stands open."},
    }
    varied = dict(resting, intensity=0.75, suddenness=0.35, ambiguity=0.55,
                  fidelity="ambiguous", directed_at_self=True)
    compacted = composer.compact_observation(varied)
    for key in ("intensity", "suddenness", "ambiguity", "fidelity",
                "directed_at_self"):
        assert compacted[key] == varied[key]
    # A perceiver_id that does NOT match the id's perceiver is a fact, not a
    # repetition, and must fail safe by surviving.
    crossed = dict(resting, perceiver_id="99")
    assert composer.compact_observation(crossed)["perceiver_id"] == "99"


def test_residue_is_the_whole_output_for_a_non_awake_mind():
    percepts = composer.residue_percepts(
        "unconscious", targeted=True, loud_event=True, pain=False)
    rendered = composer.render_view(percepts, mode="character")
    assert "Darkness." in rendered.text
    assert "shifts you" in rendered.text or "sound" in rendered.text
    content, gist, entities = composer.render_episode(percepts)
    assert content == rendered.text
    assert entities == []


# ---------------------------------------------------------------------------
# Perception glue
# ---------------------------------------------------------------------------

def test_explicit_look_intent_reads_structured_interpretation():
    assert perception._explicit_look_intent(
        {"location_query": "the far shelf"}) is True
    assert perception._explicit_look_intent({"sequence": [
        {"type": "action", "attempt": "examines the mural closely",
         "observable": "examines the mural closely"}]}) is True
    assert perception._explicit_look_intent({"sequence": [
        {"type": "action", "attempt": "draws his sword",
         "observable": "draws his sword"}]}) is False
    assert perception._explicit_look_intent({}) is False


def test_dialogue_hear_level_is_the_composer_gate():
    """One implementation of the hearing gate: the model path's entry point
    delegates to composer.line_hear_level, so the two cannot drift."""
    entry = {"volume": "normal", "intended_target": "Alice", "medium": "comm"}
    rel = {"barrier": "unknown"}
    assert perception._dialogue_hear_level(entry, rel, "Alice") \
        == composer.line_hear_level(entry, rel, "Alice") == "full"
    assert perception._dialogue_hear_level(entry, rel, "Bob") == "none"


def test_act_surface_identity_scrub_at_admission():
    """A Director-authored observable can embed a canonical name the
    observer has not earned; the input-side scrub replaces it before the
    percept exists."""
    recognized, unknown = perception._composer_unknown_sources(
        "Reya", {"Reya": []},
        [{"name": "Hinami",
          "appearance": "a fox-eared young woman with six tails",
          "aliases": []}])
    surface = perception._composer_scrub_surface(
        "steps protectively in front of Hinami", "Reya", recognized, unknown)
    assert "Hinami" not in surface
    assert "fox" in surface.casefold()


# ---------------------------------------------------------------------------
# The two rescues that promote an unheard line -- live, and now attributable
# ---------------------------------------------------------------------------

def _speech_decisions(entry, rel, observer, **kw):
    """Every decision `speech_percept` records for one line, plus its result.

    `note_step_decision` is a no-op outside a running step, so a test that
    only calls the function would assert against an engine that recorded
    nothing. This sets the sink the runtime normally sets.
    """
    import contextlib
    from core.pipeline_context import current_decision_sink, current_step_key

    seen = []
    token = current_step_key.set("perception_outcome")
    sink = current_decision_sink.set(
        lambda kind, subject, verdict, reason="": seen.append(
            (kind, subject, verdict, reason)))
    try:
        kw.setdefault("display", observer)
        kw.setdefault("can_see", False)
        out = composer.speech_percept(entry, rel, observer, **kw)
    finally:
        current_decision_sink.reset(sink)
        current_step_key.reset(token)
    return out, [row for row in seen if row[0] == "speech_percept"]


def test_the_addressed_rescue_is_live_and_says_so():
    """NOT DEAD -- a play run that never triggers a branch has measured its
    own story, not the code.

    A line the wall would drop, addressed BY NAME at spoken volume, is
    rescued to a full quotation. That is what carries an ordinary shout
    through a closed door, which is why the rescue exists; the open question
    (docs/UNBUILT.md § 1.121) is whether its premise survives three rooms of
    stone tower, and that question could not be asked because nothing
    recorded which relation had decided. Now the record names it.
    """
    entry = {"volume": "normal", "text": "Get down here.",
             "intended_target": "Alice", "speaker": "Bram"}
    rel = {"barrier": "wall", "same_room": False}
    # The ordinary spatial read drops it...
    assert composer.hear_level(rel, "normal") == "none"
    # ...and the addressed rescue carries it, by name and by name only.
    out, decisions = _speech_decisions(entry, rel, "Alice")
    assert out is not None and out.data["level"] == "full"
    assert any("addressed rescue" in row[3] for row in decisions), decisions
    assert composer.speech_percept(entry, rel, "Carol", display="Carol",
                                   can_see=False) is None


def test_attention_does_not_beat_air_that_is_working():
    """Being addressed is not a second, better path through the same doors.

    Two independent runs, 2026-09-05: a shout three rooms up a stone tower
    delivered verbatim on four beats (lighthouse, PA4), and a line from two
    closed doors and a room away delivered complete in a view whose two
    UNADDRESSED voices were correctly fragments (the Cold Season Ball, PX6).
    Sound reached both places -- that is the point. Where the sound field
    could place the pair it stamps `signal`, and where it could at least say
    what this room's best opening admits it stamps `door_gain`; either way the
    air has an answer and the address does not overrule it.

    The case the shape floor was earned for is the complement, and
    `test_shape_floor_rescues_an_untagged_named_remote_line` pins it: a party
    with no acoustic relationship at all carries neither key, and a line that
    arrives by name there arrives by a device.
    """
    entry = {"volume": "normal", "text": "Get down here.",
             "intended_target": "Alice", "speaker": "Bram"}
    for answered in ({"barrier": "wall", "signal": 0.04, "noise": 18.0},
                     {"barrier": "closed_door", "door_gain": 0.2,
                      "noise": 18.0}):
        assert composer.hear_level(answered, "normal") == "none"
        assert composer.line_hear_level(entry, answered, "Alice") == "none"
    # Nothing placed the pair: the device is the only explanation.
    assert composer.line_hear_level(
        entry, {"barrier": "separated", "distance": "remote"},
        "Alice") == "full"


def test_the_addressed_rescue_is_not_above_the_senses_gate():
    """It ran after `_sense_graded` and returned a bare "full", so one view
    could carry a fragmented sentence into a poor ear at arm's reach beside a
    verbatim shout from two rooms below (rush, PR5)."""
    entry = {"volume": "normal", "text": "Get out.",
             "intended_target": "Alice", "speaker": "Bram"}
    rel = {"barrier": "wall", "distance": "near"}
    # The ordinary read drops it, so this "full" is the rescue's own.
    assert composer.hear_level(rel, "normal") == "none"
    assert composer.line_hear_level(entry, rel, "Alice") == "full"
    dulled = composer.line_hear_level(
        entry, rel, "Alice",
        senses=[{"channel": "hearing", "acuity": "poor"}])
    assert dulled != "full", dulled


def test_the_open_group_continuity_floor_is_live_and_says_so():
    """The other rescue, from the other direction: a compatibility floor for
    a rerolled checkpoint that predates the near-group position repair. It
    fires only when `perception._previous_open_group_continuity` has stamped
    the relation, and it grants hearing alone.
    """
    entry = {"volume": "normal", "text": "Mind the step.", "speaker": "Bram"}
    rel = {"barrier": "wall", "same_room": False}
    assert composer.speech_percept(entry, rel, "Alice", display="Alice",
                                   can_see=False) is None

    out, decisions = _speech_decisions(
        entry, {**rel, "open_group_continuity": True}, "Alice")
    assert out is not None and out.data["level"] == "full"
    assert any("open-group continuity floor" in row[3] for row in decisions), \
        decisions


def test_an_ordinary_refusal_is_recorded_with_its_reason():
    entry = {"volume": "normal", "text": "Nothing.", "speaker": "Bram"}
    out, decisions = _speech_decisions(
        entry, {"barrier": "wall", "same_room": False}, "Alice")
    assert out is None
    assert decisions and decisions[0][2] == "refused"
    assert "via spatial" in decisions[0][3]


# ---------------------------------------------------------------------------
# Campaign 3 (2026-09-05C): an authored description is a NOUN PHRASE
# ---------------------------------------------------------------------------

class TestAuthoredDescriptionsAreSpliced:
    """Run 2026-09-05C `solitude` (PS9) and `masque` (PX20).

    The Director writes anchor descriptions and edge names as capitalised
    sentences, and the composer splices them into the middle of its own
    sentences. Turn 4 shipped "You can see Salt-rimed limestone kerbstones
    dividing the rectangular crystallisation pans. within arm's reach, The
    open stone lip of the middle shelf ... across the room."; turn 5 shipped
    "...at The low cut-limestone arch ... and The massive limestone revetment
    wall at the far northeast end of the dry basin.." with two full stops;
    turn 20 shipped "There is broad salt-crusted stone steps."
    """

    def test_a_sentence_shaped_desc_composes_as_a_phrase(self):
        rows = [{"desc": "The open stone lip of the middle shelf.",
                 "tier": "within_reach"},
                {"desc": "Salt-rimed kerbstones dividing the pans.",
                 "tier": "across"}]
        sentence = composer._render_features(rows)
        assert sentence == (
            "You can see the open stone lip of the middle shelf within "
            "arm's reach and Salt-rimed kerbstones dividing the pans "
            "across the room.")
        # No stop survives inside the list, and a capital that is not an
        # article is left alone -- it may be a name and nothing here knows.
        assert ". " not in sentence[:-1]

    def test_a_bare_noun_takes_the_packs_article(self):
        """F52's last unfixed line: the light's sources are entity NAMES."""
        shape = {"groups": [{"level": "dim", "items": ["low arch."]}],
                 "sources": ["brass hand lamp"], "openings": ["the opening"],
                 "self": None}
        assert composer.render_light_shape(shape) == (
            "The light from the brass hand lamp and the opening thins to "
            "half-light at the low arch.")

    def test_a_way_out_agrees_in_number_with_a_plural_desc(self):
        rows = [{"desc": "broad salt-crusted stone steps", "state": "bare"}]
        assert composer._render_openings(rows) == (
            "There is a way out through the broad salt-crusted stone steps.")

    def test_two_unnamed_boundaries_are_never_the_same_sentence(self):
        """PX20: "The doorway is shut. The doorway is shut." -- one room, two
        unnamed doors, and a boundary sight does not cross may not be
        described by where it goes."""
        rows = [{"desc": "the doorway", "state": "blind"},
                {"desc": "the doorway", "state": "blind"}]
        rendered = composer._render_openings(rows)
        assert rendered == ("Nothing shows through the doorway. "
                            "Nothing shows through the second doorway.")

    def test_the_light_sentence_states_the_light_and_not_a_posture(self):
        """PS20: "You stand in the light." composed on turn 19 while her pose
        was `seated`. Where the light falls is not a claim about the body."""
        shape = {"groups": [], "sources": [], "openings": [], "self": "lit"}
        assert composer.render_light_shape(shape) == "You are in the light."
        assert "stand" not in composer.render_light_shape(
            {"groups": [], "sources": [], "openings": [], "self": "dark"})


class TestPresenceEnumeratesEveryone:
    """Run 2026-09-05C `multitude` turn 1 (PM6): six bodies in the hall, and
    the player's outcome view named four of them in a closed conjunctive
    list -- no Tobin Slake, the one person who did nothing that beat. A
    sentence that enumerates who is present must enumerate everyone
    present."""

    @staticmethod
    def _presence(name, tier, at="", key=None):
        return composer.Percept(
            kind="presence", channel="sight", source_label=name,
            data={"tier": tier, **({"at": at} if at else {})},
            dedupe_key=key or f"presence:{name}")

    def test_a_body_that_stood_still_is_still_in_the_room(self):
        moved = self._presence("Maren Vaunt", "within_reach")
        still = self._presence("Tobin Slake", "across", at="the doors")
        rendered = composer.render_view(
            [moved, still], mode="player", language="en",
            prev_standing=frozenset({still.dedupe_key}))
        assert "Tobin Slake" in rendered.text, rendered.text
        assert rendered.text == (
            "Maren Vaunt is within arm's reach and Tobin Slake is still "
            "at the doors.")

    def test_a_beat_where_nobody_moved_is_still_an_empty_view(self):
        """The brief clause is added to a view, never the whole of one --
        `perception`'s outcome floor reads an empty view and asks for the
        background instead (chat 98 turns 13, 15, 16, 20, 21, 36)."""
        still = self._presence("Tobin Slake", "across")
        rendered = composer.render_view(
            [still], mode="player", language="en",
            prev_standing=frozenset({still.dedupe_key}))
        assert rendered.text == ""


def test_an_impaired_ear_is_not_an_unreachable_one():
    """`full` is the top of the hearing ladder, so a -1 acuity took every
    `full` to `fragment` unconditionally: a hard-of-hearing body never made
    out a sentence again, at any volume and any distance, including one
    shouted into it at arm's length -- and no speaker could do anything
    about it, which is what makes it a defect rather than a disability
    (rush, 2026-09-05, PR5).

    The shift yields where the world is already compensating for it, on the
    two terms the world has: a MEASURED intimacy, or a raised voice. Exactly
    the exception design note 18 makes for dim sight.
    """
    poor = [{"channel": "hearing", "acuity": "poor"}]
    same_room = {"same_room": True, "barrier": "open"}
    ordinary = {"volume": "normal", "text": "Here.", "speaker": "Bram"}

    # Across the room at ordinary volume, the card still costs the words.
    assert composer.line_hear_level(
        ordinary, same_room, "Alice", senses=poor) == "fragment"
    # Shouted, or at arm's length, it does not.
    assert composer.line_hear_level(
        {**ordinary, "volume": "shout"}, same_room, "Alice",
        senses=poor) == "full"
    assert composer.line_hear_level(
        ordinary, same_room, "Alice", proximity="within_reach",
        senses=poor) == "full"
    # The exemption is not a repeal: a line the room already muffles stays
    # muffled, because the channel is not at its ceiling.
    muffled = {"barrier": "closed_door", "same_room": False}
    assert composer.hear_level(muffled, "normal") == "fragment"
    assert composer.line_hear_level(
        ordinary, muffled, "Alice", proximity="within_reach",
        senses=poor) != "full"
    # And a deaf card is still deaf -- an absent channel is a cut, not a shift.
    deaf = [{"channel": "hearing", "acuity": "deaf"}]
    assert composer.line_hear_level(
        {**ordinary, "volume": "shout"}, same_room, "Alice",
        proximity="within_reach", senses=deaf) == "none"
