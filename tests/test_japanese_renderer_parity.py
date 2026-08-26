"""Layer B must deliver the same FACTS in Japanese as in English.

Layer A decides what an observer may receive; Layer B decides only wording. A
renderer that drops a percept kind therefore withholds a fact the observer
legitimately earned, and it does so with no error anywhere -- `_sentence`
returned "" and the sentence was skipped.

The whole adapter was previously exercised with one percept kind (speech), so
`body_part`, `room_notes`, lighting, `body_state`, `body_region`, presence
tier/side and the non-awake floor were all broken without a failing test. Each
case below is written as a PAIR against the English renderer so a future
regression shows up as a divergence rather than as prose somebody has to read.
"""

import dataclasses

import pytest

from agents.composer import Percept, render_episode, render_view
from language_runtime import current_language_id


def _percept(kind, label="Reya", channel="sight", order=None,
             fidelity="full", **data):
    return Percept(kind=kind, channel=channel, source_label=label,
                   fidelity=fidelity, data=data, order_key=order,
                   dedupe_key=f"{kind}:{label}")


@pytest.fixture
def japanese():
    token = current_language_id.set("ja")
    try:
        yield
    finally:
        current_language_id.reset(token)


#: Every kind the composer emits, with the facts each one carries.
KINDS = {
    "environment": _percept("environment", label="",
                            room_name="the atrium", room_notes="Rain on glass",
                            light="dim"),
    "presence": _percept("presence", tier="near", side="left"),
    "appearance": _percept("appearance", description="a tall figure",
                           source_key="reya"),
    "act": _percept("act", surface="crosses to the shelf", order=1),
    "crossing": _percept("crossing", direction="arrived", order=2),
    "pose": _percept("pose", posture="kneeling", support="the floor"),
    "body_part": _percept("body_part", count=2, part="tail", aspect="back",
                          at="waist", description="long and dark"),
    "body_state": _percept("body_state", label="you", posture="standing",
                           activity="catching your breath",
                           held_items=["a lantern"]),
    "body_region": _percept("body_region", place="shoulder",
                            detail="a long scar"),
    "speech": _percept("speech", channel="hearing", order=3,
                       body="the codes are in the safe", can_see=True),
    "sensation": _percept("sensation", clause="your shoulder aches"),
    # An EVENT kind: English renders these only in event position.
    "substance": _percept("substance", clause="smoke fills the room",
                          order=4),
    "ambient": _percept("ambient", label="", desc="a low hum from the vents"),
}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_every_percept_kind_renders_in_japanese(japanese, kind):
    """A dropped kind is a withheld fact, not a wording choice."""
    assert render_view([KINDS[kind]], language="ja").text.strip(), (
        f"{kind} rendered nothing in Japanese")


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_no_percept_kind_is_silently_dropped_relative_to_english(japanese, kind):
    english = render_view([KINDS[kind]], language="en").text.strip()
    japanese_text = render_view([KINDS[kind]], language="ja").text.strip()
    assert bool(english) == bool(japanese_text), (
        f"{kind}: english={english!r} japanese={japanese_text!r}")


def test_environment_carries_notes_and_lighting(japanese):
    """room_notes and the light level were dropped, so a Japanese reader was
    never told a room was dim -- and lighting gates visibility."""
    text = render_view([KINDS["environment"]], language="ja").text
    assert "Rain on glass" in text
    assert "薄暗い" in text


def test_body_state_reads_the_keys_the_percept_actually_carries(japanese):
    """It read `detail`/`state`, which are never set, and rendered a dangling
    `youの状態：` with no content at all."""
    text = render_view([KINDS["body_state"]], language="ja").text
    assert "standing" in text and "catching your breath" in text
    assert "a lantern" in text
    assert "の状態：。" not in text


def test_presence_carries_distance_and_side(japanese):
    text = render_view([KINDS["presence"]], language="ja").text
    assert "すぐ近く" in text, "distance tier dropped"
    assert "左" in text, "side dropped"
    assert "left" not in text, "canonical enum leaked into the view"


def test_speech_distinguishes_heard_from_seen(japanese):
    """Whether the observer could SEE the speaker is perceptual fidelity."""
    heard = _percept("speech", channel="hearing", order=1,
                     body="the codes are in the safe", can_see=False)
    seen = _percept("speech", channel="hearing", order=1,
                    body="the codes are in the safe", can_see=True)
    assert (render_view([heard], language="ja").text
            != render_view([seen], language="ja").text)
    assert "聞こえる" in render_view([heard], language="ja").text


def test_an_appearance_is_not_redescribed_every_beat(japanese):
    """prev_described was accepted and never consulted, so a body's full
    description was re-rendered from scratch on every single beat.

    Page compression is the PLAYER view's rule, in both languages: this
    adapter used to apply it in every mode, which subtracted evidence from
    an NPC mind that English kept giving it. A stateless character call has
    only what is in its context."""
    appearance = KINDS["appearance"]
    assert render_view([appearance], language="ja", mode="player",
                       prev_described={"reya"}).text == ""
    assert render_view([appearance], language="ja", mode="player").text != ""
    assert render_view([appearance], language="ja",
                       prev_described={"reya"}).text != ""


def test_a_non_awake_mind_receives_the_residue_and_nothing_else(japanese):
    """The Layer-B floor. A mind below waking does not also receive the room,
    the dialogue and the arrivals -- and this must not depend on call sites
    choosing to assign rather than append."""
    residue = _percept("residue", label="you", level="under", pain=True)
    speech = _percept("speech", channel="hearing", order=1,
                      body="the codes are in the safe", can_see=True)
    text = render_view([residue, speech, KINDS["environment"]],
                       language="ja").text
    assert "the codes are in the safe" not in text
    assert "the atrium" not in text
    assert text.strip()


def test_generic_labels_are_not_minted_as_memory_entities(japanese):
    """"a voice" names nobody. English filters these; indexing them pollutes
    recall with rows that identify no one."""
    voice = _percept("speech", label="声", channel="hearing", order=1,
                     body="誰かがいる", can_see=False)
    _episode, _gist, entities = render_episode([voice], language="ja")
    assert entities == []


def test_a_failing_adapter_costs_wording_not_the_beat(japanese, monkeypatch):
    """A malformed pack must degrade to English prose, never kill the turn."""
    import agents.composer as composer

    class Broken:
        def render_view(self, *a, **k):
            raise RuntimeError("pack is broken")

        def render_episode(self, *a, **k):
            raise RuntimeError("pack is broken")

    monkeypatch.setattr(composer, "_safe_renderer", lambda language: Broken())
    text = render_view([KINDS["act"]], language="ja").text
    assert "crosses to the shelf" in text


def test_both_renderers_reach_the_same_change_verdicts(japanese):
    """WHICH percepts a view may carry is an information decision and has one
    owner; only the wording is the pack's. This adapter carried its own copy
    of the player delta rule and it had already drifted once, so the moment
    the English rule was repaired the two disagreed about what the observer
    receives. Compared on percept identity and beat/background classification
    rather than on prose."""
    from agents.composer import standing_verdicts

    changed = dataclasses.replace(_percept("pose", posture="standing"),
                                  dedupe_key="pose:subj:moved")
    percepts = [KINDS["environment"], KINDS["presence"], changed,
                KINDS["appearance"], KINDS["sensation"], KINDS["act"]]
    # The same subject under different content: the verdict must be
    # `changed` in both renderers, and both must lead with it.
    prev = frozenset({"pose:subj:held", KINDS["presence"].dedupe_key})

    english = render_view(percepts, language="en", mode="player",
                          prev_standing=prev)
    japanese_view = render_view(percepts, language="ja", mode="player",
                                prev_standing=prev)

    def verdict_map(rendered):
        return {p.dedupe_key: bool((p.data or {}).get("beat"))
                for p, _ in rendered.spans if p.order_key is None}

    assert verdict_map(english) == verdict_map(japanese_view)
    assert english.described == japanese_view.described
    # And the shared function is the one both consulted.
    assert standing_verdicts(percepts, prev)["pose:subj:moved"] == "changed"


def test_the_japanese_player_view_leads_with_the_beat(japanese):
    """The beat half has an INTERNAL order, and a pack that partitions for
    itself can get it wrong without dropping a single fact.

    The case this must exercise is a beat half holding both an event and a
    standing percept that CHANGED. A view whose only beat content is the
    event orders correctly no matter what the rule says, which is why the
    earlier version of this test passed while the adapter emitted the changed
    pose first: `pose:Reya` is a two-part key, `_subject_prefix` answers None
    for it, and the verdict was `first` -- so the pose was background and the
    beat half had one member. Every standing key below is written in the
    three-part `<tag>:<subject>:<content>` form the ledger actually stores,
    and the previous ledger holds the same subjects under different content,
    so both renderers must call them `changed` and lead with them.
    """
    changed_pose = dataclasses.replace(KINDS["pose"],
                                       dedupe_key="pose:subj:standing")
    changed_room = dataclasses.replace(KINDS["environment"],
                                       dedupe_key="environment:room:rain")
    percepts = [changed_room, changed_pose, KINDS["sensation"],
                KINDS["act"], KINDS["speech"]]
    prev = frozenset({"pose:subj:kneeling", "environment:room:dry",
                      KINDS["sensation"].dedupe_key})

    def shape(rendered):
        return [(p.kind, bool((p.data or {}).get("beat")))
                for p, _ in rendered.spans]

    japanese_view = render_view(percepts, language="ja", mode="player",
                                prev_standing=prev)
    english = render_view(percepts, language="en", mode="player",
                          prev_standing=prev)
    # Events in declared order, then what changed, a changed room last, then
    # the background -- and the pack must not have its own opinion about it.
    assert shape(japanese_view) == [
        ("act", False), ("speech", False),
        ("pose", True), ("environment", True), ("sensation", False)]
    assert shape(japanese_view) == shape(english)
