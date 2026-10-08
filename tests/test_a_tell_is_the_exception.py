"""A tell is the exception, it shows where it showed, and everything another
person is given of a mind holds only what could be seen or heard.

The outside critique of the Brackwater run (chat 166, 2026-10-07): white
knuckles, held breaths and jaw-sets became "a second dialogue track" saying
the same thing about everyone; gestures arrived glossed with their meaning;
pages ended on a tell. 54 of the 55 body-tension motifs on its pages traced
to records the ENGINE delivered, and a narrator restraint clause A/B-tested
on the captured requests did not remove them -- the model renders what it is
given. So each fix is at the source:

  * the cadence: a reply carries one tell (`jev.MAX_TELLS`), and the card asks
    for one only when the moment presses on what the mind holds back -- 33 of
    34 replies had filled the two-tell quota;
  * the gate: an observer's reach is counted on the scale a tell's subtlety
    is graded on, and an advantage the observer lacks adds nothing
    (`affect.TELL_ADVANTAGE`) -- every subtlety fell 0.397-0.668 against an
    ordinary stranger's 0.70, so the subtlety half blocked none of 67;
  * the order: a cue goes just before the step it showed at
    (`perception._cue_slots`), never after the whole beat -- 16 of 29 pages
    ended on one;
  * the floor: `how`, `do`, `demeanor` and `tells` hold only what a stranger
    could see or hear -- 25 of 39 glosses arrived pre-written in them;
  * the carriage: a demeanor the read-back says did not change keeps the
    words already shown, so the standing ledger can suppress it -- all 34
    demeanors were distinct strings, so one was re-delivered every beat.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from agents import character_bare
from agents.common import STEP_MARK, assign_event_ids, fuse_speech_run, norm_sequence
from agents.perception import _cue_slots, _delivered_manifest, _tell_acuity
from llm.prompts import bare_character_prompt, character_bare_module
from mind import affect
from mind import character_jev as jev
from tests.helpers import forbid_model_calls


def _holding(**overrides):
    base = dict(name="Wren", language="en", people=["Mara"], known=["Mara"])
    base.update(overrides)
    return jev.Holding(**base)


def _reply(**overrides):
    base = {"want": "get the key back", "held_back": "grab her wrist", "hinge": "she lied",
            "sequence": [{"say": "Give it back.", "to": "Mara", "how": "low", "why": "it is mine"},
                         {"do": "holds out a hand to Mara", "why": "the key is mine"}],
            "demeanor": "very still", "tells": ["a tight jaw", "a quick breath"]}
    base.update(overrides)
    return base


def _answers(script):
    """The decision model's answers, each a sure pick."""
    return {key: {"type": "choice", "probabilities": {pick: 1.0}} for key, pick in script.items()}


# --- the cadence: one tell, and only when the moment presses ------------------------

def test_a_reply_gives_at_most_one_tell():
    assert jev.MAX_TELLS == 1
    h, reply = _holding(), _reply()
    asked = {key for key in jev.after_questions(h, reply) if key.startswith("tell:")}
    assert asked == {"tell:0:channel", "tell:0:miss", "tell:0:when"}, "the second is never asked about"
    out, _ = character_bare.compile_bare(reply, {}, h)
    assert [t["cue"] for t in out["manifest"]["tells"]] == ["a tight jaw"]


_TELLS_ONLY_WHEN = {
    "en": ("`tells` is a sign that gives you away against your will",
           "only when this moment presses on what you hold back", "leave it empty"),
    "ja": ("`tells`は本心を意に反して漏らしてしまうしるし",
           "この瞬間があなたの抑えているものに迫るときにだけ表れます", "空にしてください"),
}
_VARIETY_IF_ANY = {"en": "when something gives you away again", "ja": "また何かが本心を漏らすときは"}


@pytest.mark.parametrize("language", ("en", "ja"))
def test_the_card_asks_for_a_tell_only_when_the_moment_presses(language):
    """The card defined `tells` as signs that give you away and put no
    condition on them, so the model wrote the quota every beat; and the
    variety section said "a new sign shows", presupposing one."""
    card = bare_character_prompt(language)
    moves = next(p for p in card.split("\n\n") if "`want`" in p and "`tells`" in p)
    for phrase in _TELLS_ONLY_WHEN[language]:
        assert phrase in moves, phrase
    assert _VARIETY_IF_ANY[language] in character_bare_module("tell_variety", language)


# --- the floor: what others get of a mind is what could be seen or heard -----------

_FLOOR = {
    "en": ("WHAT OTHERS GET OF YOU", "only what a stranger watching could see or hear",
           "never what it means to you", "say so in `why`", "say so in `how` or `why`"),
    "ja": ("ほかの人に届くもの", "見知らぬ人が見て聞き取れることだけ",
           "何を意味するか", "`why`にそう書いてください", "`how`か`why`にそう書いて"),
}


@pytest.mark.parametrize("language", ("en", "ja"))
def test_everything_another_person_is_given_holds_only_what_could_be_seen_or_heard(language):
    """The observable floor `do` had, stated once for every field another
    mind receives -- a line's `how` (rendered "says in a <how> voice"), the
    `demeanor` ("X seems ...") and the `tells` (the cue) -- with the meaning,
    and whom the mind means not to see or hear, in `why`."""
    head, floor, excluded, concealment, retired = _FLOOR[language]
    card = bare_character_prompt(language)
    paragraph = next(p for p in card.split("\n\n") if p.startswith(head))
    for field in ("`how`", "`do`", "`demeanor`", "`tells`", "`why`"):
        assert field in paragraph, field
    assert floor in paragraph and excluded in paragraph
    assert concealment in paragraph and retired not in card


# --- the gate: the observer's reach on the scale the tell is graded on -------------

_CUE = "a hand that goes still on the rail"


def _delivered(subtlety, *, known=False, focus=None, sheet=None):
    scene = {"rooms": {"hall": {"name": "Hall", "adjacent": [], "light": "lit"}},
             "positions": {"Ada": "hall", "Bo": "hall"}}
    if focus:
        scene["orientation"] = {"Ada": {"focus": {"kind": "entity", "ref": focus}}}
    ctx = SimpleNamespace(character_results={7: {"manifest": {
        "surface_demeanor": "", "tells": [{"channel": "seen", "cue": _CUE, "subtlety": subtlety}]}}})
    out = _delivered_manifest(ctx, scene, "Ada", [{"name": "Bo", "room": "hall"}],
                              {"Ada": ["Bo"]} if known else {}, {"Bo": 7}, sheet)
    return (out.get("Bo") or {}).get("cues", [])


def test_the_observer_is_counted_on_the_scale_the_tell_is_graded_on():
    """An ordinary eye reaches "noticeable", and one advantage reaches one
    grade further -- the scale's own step."""
    assert _tell_acuity(None) == jev.MISS["noticeable"]
    assert affect.TELL_ADVANTAGE == pytest.approx(jev.MISS["subtle"] - jev.MISS["noticeable"])
    assert affect.TELL_ADVANTAGE == pytest.approx(jev.MISS["hidden"] - jev.MISS["subtle"])


def test_a_subtle_tell_misses_a_stranger_glancing_elsewhere():
    subtle = jev.MISS["subtle"]
    assert _delivered(subtle) == [], "an ordinary, unfamiliar, inattentive eye"
    # Each advantage reaches one grade further.
    assert _delivered(subtle, focus="Bo") == [_CUE]
    assert _delivered(subtle, known=True) == [_CUE]
    assert _delivered(subtle, sheet={"senses": [{"channel": "vision", "acuity": "keen"}]}) == [_CUE]
    # What an ordinary eye catches, the stranger still catches -- and so a
    # failing composure (capped at "noticeable", `compile_bare`) shows.
    assert _delivered(jev.MISS["noticeable"]) == [_CUE]


def test_a_hidden_tell_takes_two_advantages():
    hidden = jev.MISS["hidden"]
    assert _delivered(hidden, known=True) == [] and _delivered(hidden, focus="Bo") == []
    assert _delivered(hidden, known=True, focus="Bo") == [_CUE]


# --- the order: a cue shows at the step it went with --------------------------------

def _stream():
    return [
        {"kind": "speech", "declared": "turn:9:player:0:speech",
         "entry": {"speaker": "Tamsin", "exact_quote": "And the coat?"}},
        {"kind": "speech", "declared": "turn:9:character:7:0:speech",
         "entry": {"speaker": "Hester", "exact_quote": "Wool."}},
        {"kind": "action", "actor": "Hester", "declared": "turn:9:character:7:1:action",
         "attempt": "raps on the door"},
        {"kind": "action", "actor": "Tamsin", "declared": "turn:9:player:1:action",
         "attempt": "steps back"},
    ]


def test_a_tell_goes_just_before_the_step_it_showed_at():
    manifest = {"Hester": {"surface_demeanor": "level", "cues": ["knuckles hover before the knock"],
                           "cue_at": ["turn:9:character:7:1:action"]}}
    slots, rest = _cue_slots({}, manifest, "Tamsin", _stream())
    assert slots == {2: [("Hester", "knuckles hover before the knock")]}
    assert rest == {"Hester": {"surface_demeanor": "level"}}, "the demeanor stays standing state"


def test_an_unplaced_tell_goes_inside_its_givers_conduct_never_after_the_beat():
    """No anchor: just before the giver's LAST line or act -- inside its
    conduct, and in the round its tells came from (a mind's manifest is its
    latest round's; its lines and acts are every round's)."""
    slots, _ = _cue_slots({}, {"Hester": {"cues": ["shoulders up at the ears"]}}, "Tamsin", _stream())
    assert slots == {2: [("Hester", "shoulders up at the ears")]}
    # An anchor no entry of the beat carries -- a step it never resolved --
    # is no anchor.
    lost = {"Hester": {"cues": ["jaw sets"], "cue_at": ["turn:9:character:7:5:action"]}}
    assert _cue_slots({}, lost, "Tamsin", _stream())[0] == {2: [("Hester", "jaw sets")]}
    # Two rounds of one mind: the unplaced sign stays in the later one.
    rounds = _stream() + [{"kind": "speech", "declared": "turn:9:character:7:0:speech#r2",
                           "entry": {"speaker": "Hester", "exact_quote": "Go."}}]
    assert _cue_slots({}, {"Hester": {"cues": ["a swallow"]}}, "Tamsin", rounds)[0] == {
        4: [("Hester", "a swallow")]}


def test_a_giver_with_nothing_of_its_own_in_the_beat_keeps_the_old_place():
    manifest = {"Abel": {"surface_demeanor": "braced", "cues": ["eyes on the floor"]}}
    slots, rest = _cue_slots({}, manifest, "Tamsin", _stream())
    assert slots == {} and rest == manifest


def test_the_read_back_asks_where_a_tell_shows_only_between_two_steps_or_more():
    h = _holding()
    question = jev.after_questions(h, _reply())["tell:0:when"]
    assert set(question["criteria"]) == {"s0", "s1", "all_through"}
    assert '"Give it back."' in question["criteria"]["s0"]
    assert "holds out a hand to Mara" in question["criteria"]["s1"]
    one = _reply(sequence=[{"say": "Give it back.", "to": "Mara"}, {"ponder": "where I hid it", "why": "x"}])
    assert "tell:0:when" not in jev.after_questions(h, one), "one step: every answer places it alike"


def test_the_step_a_tell_shows_at_survives_normalization_as_its_event_id():
    """Found by its mark, never its words: the second line fuses into the
    first (`fuse_speech_run`), so a tell at it goes with the fused line; and
    no mark outlives the anchoring."""
    h = _holding()
    reply = _reply(sequence=[{"say": "Give it back.", "to": "Mara", "how": "low", "why": "x"},
                             {"say": "Now.", "to": "Mara", "how": "low", "why": "x"},
                             {"do": "holds out a hand to Mara", "why": "x"}],
                   tells=["a tight jaw"])
    for picked, element in (("s0", 0), ("s1", 0), ("s2", 1), ("all_through", None)):
        out, _ = character_bare.compile_bare(reply, _answers({"tell:0:when": picked, "do:2:seen": "outward"}), h)
        norm_sequence(out)
        fuse_speech_run(out)
        out["sequence"] = assign_event_ids(out["sequence"], "turn:9:character:7")
        character_bare.anchor_tells(out)
        assert len(out["sequence"]) == 2, "the two lines are one utterance"
        (tell,) = out["manifest"]["tells"]
        if element is None:
            assert "at_event" not in tell
        else:
            assert tell["at_event"] == out["sequence"][element]["event_id"], picked
        assert "_at_step" not in tell
        assert not [e for e in out["sequence"] + list(out.get("actions") or []) if STEP_MARK in e]


@pytest.fixture
def _no_model(monkeypatch):
    forbid_model_calls(monkeypatch, reason="perception attempted a model call")


@pytest.mark.parametrize("anchored", (True, False))
def test_the_page_gets_the_cue_where_it_showed_not_after_the_beat(temp_db, _no_model, anchored):
    """End to end through the outcome stage: a cue anchored at its giver's
    knock lands between her first line and the knock; one with no anchor
    lands before her last line. Neither is the beat's last record."""
    from agents.perception import perception_outcome
    from tests.test_composer_pipeline import _interp, _make_ctx

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_interpret = _interp(char_id, [
        {"type": "speech", "text": "Who rang the bell?", "volume": "normal", "tone": "",
         "visibility": "overt", "conceal_from": []}])
    ids = [f"turn:{ctx.turn.id}:character:{char_id}:{i}:{kind}"
           for i, kind in enumerate(("speech", "action", "speech"))]
    tell = {"cue": "her knuckles hover a breath before they land", "channel": "seen",
            "subtlety": jev.MISS["plain"]}
    if anchored:
        tell["at_event"] = ids[1]
    line = {"volume": "normal", "tone": "", "visibility": "overt", "conceal_from": [], "targets": []}
    ctx.character_results = {char_id: {
        "sequence": [{"type": "speech", "text": "Nobody you know.", **line, "event_id": ids[0]},
                     {"type": "action", "attempt": "raps twice on the door",
                      "observable": "raps twice on the door", "visibility": "overt",
                      "conceal_from": [], "targets": [], "event_id": ids[1]},
                     {"type": "speech", "text": "Open up, it's me.", **line, "event_id": ids[2]}],
        "manifest": {"surface_demeanor": "", "tells": [tell]}}}
    ctx.director_resolve = {"resolved_event": "", "state_diff": {}, "dialogue_log": [
        {"speaker": "Reya", "exact_quote": "Nobody you know.", "volume": "normal"},
        {"speaker": "Reya", "exact_quote": "Open up, it's me.", "volume": "normal"}]}
    out = perception_outcome(ctx, "n0")
    events = sorted((o for o in out["observations"]["player"] if o.get("phase") == "event"),
                    key=lambda o: o["order"])
    kinds = [(o["kind"], o["observed"]["text"]) for o in events]
    position = next(i for i, (kind, _) in enumerate(kinds) if kind == "cue")
    first_line = next(i for i, (_, text) in enumerate(kinds) if "Nobody you know." in text)
    knock = next(i for i, (_, text) in enumerate(kinds) if "raps twice" in text)
    last_line = next(i for i, (_, text) in enumerate(kinds) if "Open up" in text)
    if anchored:
        assert first_line < position < knock, kinds
    else:
        assert knock < position < last_line, kinds
    assert position != len(kinds) - 1, "a tell no longer closes the beat"


# --- the carriage: unchanged, it keeps the words already shown ---------------------

def test_a_carriage_that_did_not_change_keeps_the_words_already_shown():
    h = _holding(carriage="level and quiet, hands busy on the rope")
    reply = _reply(demeanor="Flat calm, hands working the line")
    question = jev.after_questions(h, reply)["demeanor:changed"]
    assert "level and quiet" in question["instructions"] and "Flat calm" in question["instructions"]
    kept, _ = character_bare.compile_bare(reply, _answers({"demeanor:changed": "no"}), h)
    assert kept["manifest"]["surface_demeanor"] == "level and quiet, hands busy on the rope"
    moved, _ = character_bare.compile_bare(reply, _answers({"demeanor:changed": "yes"}), h)
    assert moved["manifest"]["surface_demeanor"] == "Flat calm, hands working the line"
    unread, _ = character_bare.compile_bare(reply, {}, h)
    assert unread["manifest"]["surface_demeanor"] == "Flat calm, hands working the line", (
        "an unanswered question keeps the new words")


def test_the_carriage_is_asked_about_only_when_there_is_one_to_compare():
    assert "demeanor:changed" not in jev.after_questions(_holding(), _reply()), "first sight"
    assert "demeanor:changed" not in jev.after_questions(_holding(carriage="very  still"), _reply()), (
        "the same words")
    assert "demeanor:changed" not in jev.after_questions(_holding(carriage="still"), _reply(demeanor=""))


def test_the_carriage_shown_is_kept_for_the_next_read_back(temp_db):
    from persist.commit import prepare_memory_commit
    from tests.test_rupture_window_and_tells import _commit_ctx, _committed_state, _story

    chat_id, char_id, cast = _story(temp_db, {affect.CARRIAGE_KEY: "even"})
    shown = _commit_ctx(chat_id, char_id, cast, 4, {"manifest": {
        "surface_demeanor": "  level   and quiet ", "tells": []}})
    assert _committed_state(prepare_memory_commit(shown), char_id)[affect.CARRIAGE_KEY] == "level and quiet"
    silent = _commit_ctx(chat_id, char_id, cast, 4, {"manifest": {"surface_demeanor": "", "tells": []}})
    assert _committed_state(prepare_memory_commit(silent), char_id)[affect.CARRIAGE_KEY] == "even", (
        "a beat that showed none keeps the last")


def test_the_step_reads_the_stored_carriage_and_anchors_its_tell(temp_db, monkeypatch):
    """Through `character_step`: the stored carriage reaches the read-back,
    an unchanged one comes back in the manifest, and the tell carries the
    event id of the act it showed at -- with no step mark left anywhere."""
    import agents.character as character_module
    from tests.test_rupture_window_and_tells import _story

    chat_id, char_id, cast = _story(temp_db, {affect.CARRIAGE_KEY: "level and quiet"})
    temp_db.wset(chat_id, "scene", {
        "location": "Hearing Chamber", "time": "day",
        "rooms": {"chamber": {"name": "Chamber", "adjacent": []}},
        "positions": {"Advocate Vorne": "chamber"}, "entities": {}, "attire": {}, "overlays": {}})
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                         (chat_id, 1, "well?", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None, scenario="",
                      created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="well?", created=time.time()),
        cast=cast, input="well?")
    ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": []}}
    reply = {"want": "be done", "sequence": [{"say": "The record stands.", "why": "it does"},
                                             {"do": "closes the ledger", "why": "done"}],
             "demeanor": "Calm and even, hands still", "tells": ["a thumb that works the ledger's edge"]}
    monkeypatch.setattr(character_module, "_agent_json", lambda *a, **k: json.loads(json.dumps(reply)))
    seen = {}

    def read_back(holding, out):
        seen["carriage"] = holding.carriage
        return _answers({"tell:0:when": "s1", "do:1:seen": "outward", "demeanor:changed": "no"})

    monkeypatch.setattr(jev, "ask_before", lambda holding: {})
    monkeypatch.setattr(jev, "ask_after", read_back)
    out = character_module.character_step(ctx, char_id, nonce=0)
    assert seen["carriage"] == "level and quiet"
    assert out["manifest"]["surface_demeanor"] == "level and quiet"
    (tell,) = out["manifest"]["tells"]
    act = next(e for e in out["sequence"] if e.get("type") == "action")
    assert tell["at_event"] == act["event_id"]
    assert not [e for e in out["sequence"] + list(out.get("actions") or []) if STEP_MARK in e]
