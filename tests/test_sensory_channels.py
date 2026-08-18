"""The narrator's per-sense delivery manifest (`sensory_channels`).

THE DEFECT: percepts carry a real channel from every builder through
`composer.observations_from_render` (composer.CHANNELS), and the tag was
discarded one stage before the prose -- `agents/narration.py` handed the
narrator one blob. Measured over 600 stored perception steps: sight 1089
spans, touch 94, and delivered smell ~0 after the opening turn (the cue
classifier's 73 "smell" rows are artefacts of the word "scent" appearing in
prose). The composer's delta dedupe additionally suppresses standing contact
sensations after their first render, so beat two of a sustained contact
delivered no touch at all. The manifest re-delivers standing substrate and
reorganizes this beat's spans per channel; every admission is subtractive
(view containment, recognition floor, cause-blind substance clauses,
exposure-gated weather), so it can never widen what the player knows.
"""

import json

from agents.narration import (
    _sensory_channels_manifest,
    _standing_substance_clauses,
)


PLAYER = "Hero"


def _scene(**over):
    base = {
        "rooms": {"yard": {"name": "Yard", "exposure": "open",
                           "adjacent": []}},
        "positions": {PLAYER: "yard"},
    }
    base.update(over)
    return base


def _manifest(scene, view="", observations=(), recognized=(), cast_info=None,
              room="yard"):
    return _sensory_channels_manifest(
        scene, PLAYER, view, list(observations), set(recognized),
        cast_info or {}, room)


def test_manifest_absent_without_room_or_scene():
    """Absent-when-empty: no scene or no room means no key, so pre-change
    payload shapes are reproducible and replay/reroll of old turns cannot
    grow a field from nothing."""
    assert _manifest(None) == {}
    assert _manifest(_scene(), room=None) == {}


def test_manifest_absent_for_enclosed_player():
    """A player sealed inside an enclosure does not get the room's light,
    weather, or air: the enclosure is between them and every room-level fact
    this manifest carries. Guards subtract -- the whole key is withheld."""
    sc = _scene(contained={PLAYER: {"in": "crate", "mode": "hidden"}})
    assert _manifest(sc) == {}


def test_spans_grouped_by_channel_and_gated_on_view_containment():
    """Observations are projected from the render BEFORE the tripwire scrub
    (`_composer_finish_observer` scrubs `rendered.text` into the view but
    projects observations from `rendered` itself), so a span the scrub
    removed must not ride back in through this second representation. Only
    byte-contained spans are admitted."""
    view = "A bell rings somewhere below. Warm water sheets down your back."
    obs = [
        {"observation_id": "current:player:0", "channel": "hearing",
         "observed": {"text": "A bell rings somewhere below."}},
        {"observation_id": "current:player:1", "channel": "touch",
         "observed": {"text": "Warm water sheets down your back."}},
        {"observation_id": "current:player:2", "channel": "sight",
         "observed": {"text": "A name the scrub removed stands here."}},
    ]
    m = _manifest(_scene(), view=view, observations=obs)
    assert m["hearing"]["this_beat"] == ["A bell rings somewhere below."]
    assert m["touch"]["this_beat"] == ["Warm water sheets down your back."]
    assert "this_beat" not in m["sight"]


def test_all_five_channels_present_with_status():
    m = _manifest(_scene())
    for channel in ("sight", "hearing", "touch", "smell", "interoception"):
        assert m[channel]["status"] in ("live", "degraded", "silent")
    # An empty smell channel is still reported -- its openness is the
    # licensed riffing surface -- and empty touch is reported silent with a
    # reason, which is the fact the blob could never carry.
    assert m["smell"]["status"] == "live"
    assert m["touch"]["status"] == "silent"
    assert m["touch"]["why"]


def test_standing_contact_reaches_touch_with_identity_floor():
    """The composer's dedupe key suppresses a standing contact's sensation
    after its first render (composer.py's `contact:` dedupe), so beat two of
    a held grip delivered no touch. The manifest re-delivers it every beat --
    and the partner passes the same recognition floor the view used: an
    unrecognized cast member's canonical name must not appear anywhere in
    the manifest."""
    sc = _scene(
        positions={PLAYER: "yard", "Elyra Voss": "yard"},
        contacts=[{"actor": "Elyra Voss", "actor_part": "hand",
                   "target": PLAYER, "target_part": "wrist",
                   "manner": "grip"}],
    )
    cast_info = {"Elyra Voss": {
        "appearance": "a tall courier in a grey coat", "aliases": []}}
    m = _manifest(sc, cast_info=cast_info)
    assert m["touch"]["status"] == "live"
    standing = " ".join(m["touch"]["standing"])
    assert "wrist" in standing
    assert "Elyra" not in json.dumps(m)
    # Recognized, the same contact names her.
    m2 = _manifest(sc, recognized={"Elyra Voss"}, cast_info=cast_info)
    assert "Elyra Voss" in " ".join(m2["touch"]["standing"])


def test_unplaceable_contact_partner_falls_to_someone():
    """A partner spelling outside the cast and the recognition ledger falls
    to 'someone' rather than leaking a canonical name -- the same class rule
    perception's `_sensation_label` applies at the composed view."""
    sc = _scene(
        positions={PLAYER: "yard", "Sable": "yard"},
        contacts=[{"actor": "Sable", "actor_part": "hand",
                   "target": PLAYER, "target_part": "shoulder",
                   "manner": "grip"}],
    )
    m = _manifest(sc)
    standing = " ".join(m["touch"]["standing"])
    assert "someone" in standing
    assert "Sable" not in json.dumps(m)


def test_bystander_contact_contributes_nothing():
    """A contact between two other bodies delivers no sensation to a watcher
    (contact_sensation returns '' for a non-party); the manifest inherits
    that subtraction rather than re-deciding it."""
    sc = _scene(
        positions={PLAYER: "yard", "Kade": "yard", "Mirren": "yard"},
        contacts=[{"actor": "Kade", "actor_part": "hand",
                   "target": "Mirren", "target_part": "arm",
                   "manner": "grip"}],
    )
    m = _manifest(sc)
    assert m["touch"]["status"] == "silent"


def test_standing_substance_clauses_are_cause_blind_both_ways():
    """Mirrors `substance_event_clause`'s epistemic envelope: the recipient
    never learns the source's identity from a standing record (an internal
    target knows the matter reached them, not who caused it), and the
    releasing side never learns the destination (where it landed is sight's
    problem, delivered separately or not at all). `detail` is model prose
    delivered once at onset and is not re-delivered."""
    sc = _scene(substances=[
        {"source": "Kade", "source_part": "hand", "substance": "blood",
         "target": PLAYER, "placement": "surface", "target_part": "cheek",
         "amount": "a smear", "detail": "already drying"},
        {"source": PLAYER, "source_part": "palm", "substance": "lamp oil",
         "target": "Kade", "placement": "surface", "target_part": "sleeve"},
    ])
    clauses = _standing_substance_clauses(sc, PLAYER)
    joined = " | ".join(clauses)
    assert "a smear of blood on your cheek" in joined
    assert "lamp oil released from your palm" in joined
    assert "Kade" not in joined
    assert "sleeve" not in joined
    assert "already drying" not in joined


def test_interior_substance_clause_names_own_interior_only():
    sc = _scene(substances=[
        {"source": "Kade", "substance": "antidote",
         "target": PLAYER, "placement": "interior",
         "target_interior": "stomach"},
    ])
    clauses = _standing_substance_clauses(sc, PLAYER)
    assert clauses == ["your stomach still holds antidote"]


def test_weather_routes_per_channel():
    """Weather is the one ledger already channel-split by construction
    (`weather_words(scoped, channel)`), and it reached only backdrops.py and
    ambience.py -- never the narrator. Sight words go to sight, sound words
    to hearing, and what lands on the body (falls_on_you / wind_reaches,
    both exposure-gated by weather_for_room itself) to touch."""
    sc = _scene(weather={"sky": "storm", "precipitation": "rain",
                         "intensity": "heavy", "wind": "wind"})
    m = _manifest(sc)
    assert any("storm" in w or "rain" in w for w in m["sight"]["standing"])
    assert any("rain" in w or "thunder" in w
               for w in m["hearing"]["standing"])
    assert any("falling on you" in w for w in m["touch"]["standing"])
    assert m["touch"]["status"] == "live"


def test_enclosed_room_gets_no_weather_words():
    """`weather_for_room` is the exposure gate; the manifest must not
    re-decide it. An enclosed room under a downpour keeps its sight and
    touch dry (sight standing still carries the light line)."""
    sc = _scene(
        rooms={"vault": {"name": "Sealed Vault", "exposure": "enclosed",
                         "adjacent": []}},
        positions={PLAYER: "vault"},
        weather={"sky": "storm", "precipitation": "rain",
                 "intensity": "light", "wind": "calm"},
    )
    m = _manifest(sc, room="vault")
    assert m["sight"]["standing"] == ["light: lit"]
    assert not any("falling on you" in w
                   for w in m["touch"].get("standing", []))


def test_sight_status_follows_effective_light():
    """The one room-level aperture the engine already grades: dark rooms are
    silent on sight (dim ones degraded), unless a span legitimately rode the
    channel this beat -- content wins over aperture, because effective_light
    cannot see a percept that a body-carried source lit."""
    dark = _scene(rooms={"cellar": {"name": "Cellar", "light": "dark",
                                    "adjacent": []}},
                  positions={PLAYER: "cellar"})
    m = _manifest(dark, room="cellar")
    assert m["sight"]["status"] == "silent"
    view = "A blade catches what light there is."
    obs = [{"observation_id": "current:player:0", "channel": "sight",
            "observed": {"text": view}}]
    m2 = _manifest(dark, view=view, observations=obs, room="cellar")
    assert m2["sight"]["status"] == "degraded"

    dim = _scene(rooms={"hall": {"name": "Hall", "light": "dim",
                                 "adjacent": []}},
                 positions={PLAYER: "hall"})
    assert _manifest(dim, room="hall")["sight"]["status"] == "degraded"


def test_narrator_wiring_and_prompt_license():
    """The manifest must actually ride the payload (normal awake turns), and
    the prompt must anchor the riffing license to it -- an unanchored
    license is exactly the unbounded invention the ~15 ABSOLUTE blocks
    exist to forbid, and an unlicensed manifest is dead payload."""
    import inspect

    from agents import narration
    from llm.prompts import DEFAULT_PROMPTS

    src = inspect.getsource(narration.narrator)
    assert "_sensory_channels_manifest" in src
    assert '"sensory_channels"' in src

    prompt = DEFAULT_PROMPTS["narrator"]
    assert "SENSORY CHANNELS" in prompt
    assert "sensory_channels" in prompt
    # The license is bounded: sensation only, consequent on listed material.
    assert "SENSATION ONLY" in prompt
    assert "CONSEQUENT" in prompt
    # SCENE CRAFT's compression now says where the saved words go.
    assert "Cutting REALLOCATES" in prompt
