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
        scene, event, "Alice", "Hinami", {"same_room": True},
        display="the fox-eared woman", can_see=False)
    assert percept is None


def test_mental_beat_is_imperceptible():
    scene = _scene()
    event = {"type": "action", "observable": "", "attempt": "recall the runes",
             "visibility": "overt"}
    assert composer.act_percept(
        scene, event, "Alice", "Hinami", {"same_room": True},
        display="the fox-eared woman", can_see=True) is None


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


def test_full_appearance_is_first_mention_only_in_every_mode():
    """The 481+249-verbatim-repeat bug: the full appearance description is
    discovery data and must not be re-emitted every beat."""
    appearance = composer.appearance_percept(
        "Hinami", "the fox woman with six tails",
        "a fox-eared young woman with six tails, wearing a red obi")
    first = composer.render_view([appearance], mode="character")
    assert "six tails" in first.text
    again = composer.render_view(
        [appearance], mode="character",
        prev_described=frozenset(first.described))
    assert again.text == ""
    changed = composer.appearance_percept(
        "Hinami", "the fox woman with six tails",
        "a fox-eared young woman, obi torn, fur soaked", force=True)
    third = composer.render_view(
        [changed], mode="character", prev_described=frozenset(first.described))
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
