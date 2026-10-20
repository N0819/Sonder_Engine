"""A BREATH INTO AN EAR IS THAT EAR'S ALONE (the owner, 2026-10-20:
"Whisper should probably have levels, whispering into someone's ears is
clearly a lot quieter than a normal whisper").

The breath ladder, quietest first, each rung kept for fewer listeners than
the one above it (`spatial_senses.EAR_VOLUME`):

  ear      the lips at one ear: the line's addressee, and nobody else, even
           beside them -- 20-30 dB(A) at a metre-equivalent, heard at all
           only because the lips are at that ear;
  whisper  arm's reach (30-40 dB(A));
  mutter   a few paces (speech under the breath, 35-45).

Measured, chat 73 turn 2480: Hinami whispered to The Doctor with her lips
against his ear; the engine had one word for that and for a whisper across a
table, and both reached whoever stood within arm's reach. The rules, one
test (or more) each:

  1. to its addressee the ear rung is graded exactly as a whisper is --
     whole within reach, lost beyond it and through a door;
  2. to anybody else it is nothing, by any path: beside them, in contact
     with the speaker elsewhere, across an opening, through a live channel,
     named across a barrier, inside the speaker's own body;
  3. a reader that cannot say whether its listener is the addressee gives
     the line to nobody (`hear_level`'s default);
  4. the word is the engine's: the schema keeps it, a pitched line never
     solves to it, a level never rounds to it;
  5. the views say it: the addressee is told it was said into their ear, a
     bystander who sees it sees speech and no words;
  6. every other reader that grades a line for a listener asks whose ear --
     the interaction round's gate, background presences, a charter's
     public evidence, the unanswered address;
  7. the read-back and the encoder offer it, in both packs.

The parlour and the names are a story's shape; the rule is the class.
"""

from __future__ import annotations

import pytest

import agents.composer as composer
from llm.prompts import character_jev_options, unified_specialist_prompt
from llm.schemas import SpeechElement, normalize_speech_volume
from world.spatial import (SPEECH_DB, SPEECH_ONE_PACE_DB, hear_level,
                           hearing_reason, pitched_level_db,
                           spatial_rel_between, word_for_level)

BREATH = ("ear", "whisper", "mutter")
_RANK = {"none": 0, "fragment": 1, "full": 2}


def _parlour(*, tomas=(2, 1), bryn=(3, 2), contact=True, barrier=None):
    """A furnished parlour, five paces by four. Mara at [2, 2]; Tomas, whose
    ear she leans to, a pace north of her; Bryn a pace east, holding her
    hand. `barrier` puts Tomas beyond a doorway in the study instead."""
    parlour = {"name": "The Parlour", "exposure": "enclosed",
               "surface": "furnished", "extent": {"w": 5, "d": 4},
               "light": "lit", "anchors": {}, "adjacent": []}
    rooms = {"parlour": parlour}
    positions = {"Mara": "parlour", "Tomas": "parlour", "Bryn": "parlour"}
    if barrier:
        parlour["adjacent"] = [{"to": "study", "barrier": barrier,
                                "dir": "n", "offset": 0.5,
                                "material": "wood"}]
        rooms["study"] = {"name": "The Study", "exposure": "enclosed",
                          "extent": {"w": 4, "d": 4}, "anchors": {},
                          "adjacent": [{"to": "parlour", "barrier": barrier,
                                        "dir": "s", "offset": 0.5,
                                        "material": "wood"}]}
        positions["Tomas"] = "study"
    sc = {
        "rooms": rooms, "positions": positions,
        "stations": {
            "Mara": {"at": None, "near": [], "cell": [2, 2]},
            "Tomas": {"at": None, "near": [], "cell": list(tomas)},
            "Bryn": {"at": None, "near": [], "cell": list(bryn)}},
        "entities": {}, "poses": {}, "orientation": {}, "contained": {},
        "contacts": [],
    }
    if contact:
        sc["contacts"].append({"actor": "Bryn", "actor_part": "hand",
                               "target": "Mara", "target_part": "hand",
                               "manner": "hold"})
    return sc


def _rel(sc, listener, speaker="Mara"):
    return spatial_rel_between(sc, listener, speaker)


# ---------------------------------------------------------------------------
# 1-3: the rule in `hear_level`
# ---------------------------------------------------------------------------

def test_the_ear_reaches_its_addressee_and_not_the_body_beside_them():
    """Tomas, whose ear it is, follows it; Bryn, a pace off and holding
    Mara's hand, hears nothing -- where a whisper reaches them both."""
    sc = _parlour()
    to_tomas, to_bryn = _rel(sc, "Tomas"), _rel(sc, "Bryn")
    assert to_bryn.get("reach") == "within_reach"     # the contact
    assert hear_level(to_tomas, "ear", addressed=True) == "full"
    assert hear_level(to_bryn, "ear") == "none"
    assert hear_level(to_bryn, "ear", addressed=False) == "none"
    assert hearing_reason(to_bryn, "ear") == "into_another_ear"
    # The rung above it: arm's reach, so both.
    assert hear_level(to_tomas, "whisper") == "full"
    assert hear_level(to_bryn, "whisper") == "full"


@pytest.mark.parametrize("where", [
    {"tomas": (2, 1)},                          # within reach
    {"tomas": (2, 0)},                          # two paces: a whisper's edge
    {"tomas": (0, 0)},                          # beyond a whisper's reach
    {"tomas": (2, 1), "barrier": "open_door"},  # across an opening
    {"tomas": (2, 1), "barrier": "closed_door"},  # through a shut door
])
def test_to_its_own_ear_it_is_graded_exactly_as_a_whisper(where):
    """Lips cannot be at an ear the scene puts out of a whisper's reach, so
    the addressee is given exactly what a whisper would give them -- never
    more, and no further."""
    sc = _parlour(**where)
    rel = _rel(sc, "Tomas")
    for proximity in (None, "within_reach", "near", "across"):
        assert hear_level(rel, "ear", proximity=proximity, addressed=True) \
            == hear_level(rel, "whisper", proximity=proximity), (where,
                                                                  proximity)


def test_the_ladder_is_monotone_for_every_listener():
    """ear <= whisper <= mutter <= a voice, for the addressee and for
    anybody else, at every relation the parlour and its doors give."""
    for kwargs in ({}, {"barrier": "open_door"}, {"barrier": "closed_door"},
                   {"tomas": (0, 0)}, {"contact": False}):
        sc = _parlour(**kwargs)
        for listener in ("Tomas", "Bryn"):
            rel = _rel(sc, listener)
            for addressed in (False, True):
                ranks = [_RANK[hear_level(rel, v, addressed=addressed)]
                         for v in BREATH + ("normal",)]
                assert ranks == sorted(ranks), (kwargs, listener, addressed)


def test_no_path_carries_it_to_anybody_else():
    """A body's mass, an opening, a live channel, a name called across a
    barrier: each carries ordinary speech somewhere it would not otherwise
    go, and none of them carries a breath into another body's ear."""
    # Inside the speaker's own body: conducted, and still not theirs.
    assert hear_level({"inside_source": True, "same_room": True}, "ear") \
        == "none"
    assert hear_level({"inside_source": True, "same_room": True}, "whisper") \
        == "fragment"
    # Across an opening, standing at it.
    sc = _parlour(barrier="open_door")
    assert hear_level(_rel(sc, "Bryn"), "ear") == "none"
    line = {"speaker": "Mara", "text": "Not here.", "volume": "ear",
            "intended_target": "Tomas"}
    # A live channel between the two rooms reproduces any voice -- not this.
    channel = {"barrier": "unknown", "comm_channel": {"id": "intercom"}}
    assert composer.line_hear_level(line, channel, "Bryn") == "none"
    assert composer.line_hear_level(
        {**line, "volume": "whisper"}, channel, "Bryn") == "full"
    # Named across a barrier by a bystander's own name: no rescue either.
    named = {**line, "intended_target": "Bryn", "medium": "comm"}
    assert composer.line_hear_level(named, {"barrier": "wall"}, "Tomas") \
        == "none"


def test_a_reader_that_cannot_tell_gives_it_to_nobody():
    """`hear_level` with no `addressed` -- every reader that never asked --
    answers `none` for the ear rung: a missed delivery costs a line, a leak
    costs the firewall."""
    rel = _rel(_parlour(), "Tomas")
    assert hear_level(rel, "ear") == "none"
    assert hear_level(rel, "ear", addressed=True) == "full"


# ---------------------------------------------------------------------------
# 4: the word is the engine's
# ---------------------------------------------------------------------------

def test_the_schema_keeps_the_word():
    """A word outside the set reads as an ordinary voice -- for a line
    breathed into one ear, the whole room hearing it. So the schema owns it,
    and its plainest spellings."""
    assert normalize_speech_volume("ear") == "ear"
    assert normalize_speech_volume(" Ear ") == "ear"
    assert normalize_speech_volume("into ear") == "ear"
    assert normalize_speech_volume("in_ear") == "ear"
    assert SpeechElement(text="Not here.", volume="ear").volume.value == "ear"


def test_its_level_is_a_breath_and_no_level_rounds_to_it():
    """20-30 dB(A) at a metre-equivalent; and since the rung is an act --
    lips put to an ear -- rather than a loudness, a pitched line never
    solves to it and no level is ever read back as it."""
    assert 20.0 <= SPEECH_ONE_PACE_DB["ear"] <= 30.0
    assert SPEECH_ONE_PACE_DB["ear"] < SPEECH_ONE_PACE_DB["whisper"]
    assert word_for_level(SPEECH_DB["ear"]) == "whisper"
    assert word_for_level(0.0) == "whisper"
    sc = _parlour()
    assert word_for_level(pitched_level_db(sc, "Mara", "Tomas")) == "whisper"


# ---------------------------------------------------------------------------
# 5: the views
# ---------------------------------------------------------------------------

def test_the_addressee_is_told_it_was_said_into_their_ear():
    sc = _parlour()
    line = {"speaker": "Mara", "text": "Not here.", "volume": "ear",
            "intended_target": "Tomas"}
    to_tomas = composer.speech_percept(line, _rel(sc, "Tomas"), "Tomas",
                                       display="Mara", can_see=True,
                                       proximity="within_reach")
    assert to_tomas is not None and to_tomas.data["level"] == "full"
    text = composer.render_view([to_tomas], mode="player").text
    assert "into your ear" in text and "Not here." in text


def test_a_bystander_sees_it_said_and_gets_no_word_of_it():
    """Bryn, beside them, sees Mara lean to Tomas and her mouth move: speech
    happened, and nothing of what it was."""
    sc = _parlour()
    line = {"speaker": "Mara", "text": "Not here.", "volume": "ear",
            "intended_target": "Tomas"}
    seen = composer.speech_percept(line, _rel(sc, "Bryn"), "Bryn",
                                   display="Mara", can_see=True,
                                   proximity="within_reach")
    if seen is not None:
        assert seen.data["level"] == "none"
        assert "body" not in seen.data
        text = composer.render_view([seen], mode="player").text
        assert "Not here" not in text
    unseen = composer.speech_percept(line, _rel(sc, "Bryn"), "Bryn",
                                     display="a voice", can_see=False,
                                     proximity="within_reach")
    assert unseen is None
    # The explicit answer of a reader that resolved the target itself wins.
    assert composer.speech_percept(
        {**line, "intended_target": "character:7"}, _rel(sc, "Tomas"),
        "Tomas", display="Mara", can_see=False, observer_id=7) is not None


def test_a_refusal_says_whose_ear_it_was_or_that_it_named_none():
    """The decision note names the clause: a bystander is refused because
    the line went into another ear; a line breathed into an ear that names
    NO ear reaches nobody, its own listener included, and the note says so
    where the line went missing."""
    from core.pipeline_context import current_decision_sink
    notes = []
    token = current_decision_sink.set(
        lambda kind, subject, verdict, reason: notes.append(
            (kind, subject, verdict, reason)))
    try:
        sc = _parlour()
        line = {"speaker": "Mara", "text": "Not here.", "volume": "ear",
                "intended_target": "Tomas"}
        composer.speech_percept(line, _rel(sc, "Bryn"), "Bryn",
                                display="Mara", can_see=False)
        nameless = {**line, "intended_target": None}
        assert composer.speech_percept(nameless, _rel(sc, "Tomas"), "Tomas",
                                       display="Mara", can_see=False) is None
    finally:
        current_decision_sink.reset(token)
    reasons = [reason for kind, _s, _v, reason in notes
               if kind == "speech_percept"]
    assert any(r.endswith("; into_another_ear") for r in reasons), reasons
    assert any(r.endswith("; ear_names_no_one") for r in reasons), reasons


# ---------------------------------------------------------------------------
# 6: the other readers ask whose ear
# ---------------------------------------------------------------------------

def test_the_round_gate_asks_whose_ear():
    """The interaction round's delivery gate (`common._delivery_ok`): the
    addressee is let through and anybody else is not."""
    from agents.common import _delivery_ok
    sc = _parlour()
    assert _delivery_ok(_rel(sc, "Tomas"), sc, "Tomas", "Mara", "hearing",
                        volume="ear", addressed=True)
    assert not _delivery_ok(_rel(sc, "Bryn"), sc, "Bryn", "Mara", "hearing",
                            volume="ear")


class _Ctx:
    cast = [{"id": 7, "sheet": '{"identity": {"name": "Tomas"}}'}]


def test_perception_reads_the_target_as_the_speaker_named_it():
    """A span's target is whatever handle the encoder held -- a cast id, a
    name, an entity id -- and every one of them is the addressee's ear."""
    from agents.perception import _line_is_to
    sc = _parlour()
    for ref in ("Tomas", "tomas", "character:7"):
        line = {"type": "speech", "targets": [ref], "volume": "ear"}
        assert _line_is_to(_Ctx(), sc, "Tomas", line), ref
        assert not _line_is_to(_Ctx(), sc, "Bryn", line), ref
    assert not _line_is_to(_Ctx(), sc, "Tomas", {"targets": []})
    assert _line_is_to(_Ctx(), sc, "Tomas",
                       {"intended_target": "Tomas", "targets": []})


def test_a_background_presence_hears_only_its_own_ear():
    """Two presences at the bar; the one whose ear it is gets the words, the
    other nothing at all."""
    from agents.background import _beat_for_presence
    sc = {"rooms": {"taproom": {"name": "The Taproom",
                                "exposure": "enclosed", "adjacent": []}},
          "positions": {"Mara": "taproom"}, "entities": {}}
    dr = {"resolved_event": "",
          "dialogue_log": [{"speaker": "Mara", "exact_quote": '"Room four."',
                            "volume": "ear", "intended_target": "Old Fen"}]}
    own = _beat_for_presence(dr, sc, "taproom", "Old Fen")
    other = _beat_for_presence(dr, sc, "taproom", "Wick")
    assert "Room four." in own
    assert "Room four." not in other


def test_a_charter_body_receives_only_the_line_breathed_to_it():
    """Two charter bodies standing in the hall with the speaker: the one the
    line resolves to acquires it, the other does not -- whichever sorts
    first (a cache keyed by place would hand one answer to both)."""
    from world.charter_model import normalize_charter
    from world.charter_observe import plan_public_evidence
    scene = {"rooms": {"hall": {"name": "Hall", "adjacent": []}},
             "positions": {"Rowan": "hall"}}
    line = {"source_id": "speech:0", "kind": "speech", "actor": "Rowan",
            "exact_quote": '"Meet me at the mill."', "volume": "ear",
            "visibility": "overt", "conceal_from": [], "salience": 0.8,
            "speech_acts": [{"kind": "request",
                             "content": "Meet me at the mill."}]}
    for endpoint, other in (("aida", "zeno"), ("zeno", "aida")):
        charter = normalize_charter({"key": "town", "bodies": {
            "aida": {"name": "Aida", "place": "hall"},
            "zeno": {"name": "Zeno", "place": "hall"}}})
        plan = plan_public_evidence(
            charter, [{**line, "target": endpoint.title()}], scene,
            turn_id=1)
        assert plan["recipients"].get("speech:0") == {endpoint}, endpoint
        assert other not in plan["recipients"].get("speech:0", set())


# ---------------------------------------------------------------------------
# 7: the cards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_read_back_and_the_encoder_offer_the_ear(language):
    """The character read-back's "how loudly" answers by option KEY, which is
    the volume the line carries; the encoder's sheet names the rung, in the
    one clause that says who each breath reaches."""
    options = character_jev_options("volume", language)
    assert list(options)[:3] == ["ear", "whisper", "mutter"]
    text = unified_specialist_prompt(("entities",), language, parts=())
    assert "ear|whisper|mutter|normal|loud|shout" in text
    # ...and the interaction round tells its listener so, as the view does.
    from language_runtime import compositor_text, compositor_value
    said = compositor_text("loop_speech_ear", language, label="Mara",
                           body="Not here.")
    assert "Not here." in said and said != compositor_text(
        "loop_speech", language, label="Mara", body="Not here.")
    assert "ear" in compositor_value("dialogue_verbs", language)


def test_the_replay_reads_whose_ear_it_was_from_the_note():
    """`tools/speech_replay.py` has only the recorded note, and the note is
    enough: a line breathed into an ear that was not the listener's is filed
    with that refusal, so every other note on it was its addressee's."""
    from tools.speech_replay import addressed_in
    assert addressed_in("full via spatial; volume ear, barrier open, "
                        "tier within_reach")
    assert not addressed_in("none via spatial; volume ear, barrier open, "
                            "tier within_reach; into_another_ear")
    assert not addressed_in("none via spatial; volume ear, barrier open, "
                            "tier unmeasured; ear_names_no_one")
    assert addressed_in("none via spatial; volume whisper, barrier open, "
                        "tier across; breath_beyond_reach")
