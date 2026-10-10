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

And two found on 2026-10-09, replaying chats 160, 161 and 166 on the pack card:

  * the grade: a tell is placed at the grade the read-back chose, never at
    the expectation between two, which the gate read across a grade -- 42 of
    144 stored tells sat above their nearest grade point -- and each grade's
    option names the observer its point admits, which the options it
    replaced did not ("Someone paying attention would catch it" was the
    grade a stranger looking elsewhere is admitted at);
  * the reading: in `demeanor` and `tells` a sign's meaning is no part of
    it -- the replies kept the meaning by saying it as a watcher would, 8 of
    14 tells -- and `how` stays how the words sound;
  * the scene: a cue goes to every observer the gate admits word for word,
    so one that names something besides its giver -- "as the counting house
    door slides past" -- is not shown, and the card asks for the sign alone,
    its moment being asked on its own. The tell shown is the first the
    floor passes, so a valid sign written beside a withheld one is not lost
    with it; and the floor is one switch (`jev.TELL_SCENE_FLOOR`), kept on
    by the owner until a play run measures its live firing rate.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from agents import character_bare
from agents.common import STEP_MARK, assign_event_ids, fuse_speech_run, norm_sequence
from agents.perception import _cue_slots, _delivered_manifest, _tell_acuity
from llm.prompts import bare_character_prompt, character_bare_module, character_jev_options, character_jev_text
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
    out, _ = character_bare.compile_bare(reply, _answers({"tell:0:outside": "no", "tell:1:outside": "no"}), h)
    assert [t["cue"] for t in out["manifest"]["tells"]] == ["a tight jaw"], "both pass: the first, alone"


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


_NO_READING = {
    "en": ("In `demeanor` and `tells`, a sign's meaning is no part of it",
           "give the sign itself, as it shows or sounds, and stop there",
           "reads it for themselves, and may read it wrong"),
    "ja": ("`demeanor`と`tells`では、しるしの意味はしるしの一部ではありません",
           "見えるまま、聞こえるままのしるしだけを書いて、そこで止めてください",
           "自分で読み取り、読み違えることもあります"),
}


@pytest.mark.parametrize("language", ("en", "ja"))
def test_a_sign_is_given_without_its_reading(language):
    """The floor said "never what it means to you", and the replies kept the
    meaning by saying it from outside: "-- betraying that the distance of
    her abduction registered harder than expected", "-- the only residue of
    the fall she permits", "as if the stillness itself is the comfort she
    chose" (current-card replies on the Sarah Moon story, chats 160/161,
    2026-10-09; 5 of 10 tells written carried one). The narrator renders a
    delivered reading as delivered -- 24 of 33 did on the stored pages -- so
    a watcher was handed what only the giver could know. A sign's meaning is
    the watcher's to read, and to misread.

    SAID OF THE SIGNS, NEVER OF `how`: a line's `how` renders in the voice
    slot for every observer who can see the speaker, ungated
    (`perception._inject_dialogue`), and stated of all four fields the
    sentence moved signs into it -- `how` carrying gaze, posture or a sign
    went from 7 of 12 to 11 of 13 on the same ten replayed beats; scoped to
    the signs, 14 of 29, 9 of 15 leaving out one reply that ran to fourteen
    lines (2026-10-10, one sample a beat, one reader)."""
    head = _FLOOR[language][0]
    card = bare_character_prompt(language)
    paragraph = next(p for p in card.split("\n\n") if p.startswith(head))
    for phrase in _NO_READING[language]:
        assert phrase in paragraph, phrase


# --- the scene: a cue names nothing besides its giver -------------------------------

_SIGN_ALONE = {
    "en": ("Write the sign alone, as it shows on you or sounds in your voice",
           "when it shows is asked of you separately"),
    "ja": ("しるしだけを、あなたの体に表れるまま、声に響くままに書いてください", "それがいつ表れるかは、別にたずねます"),
}


@pytest.mark.parametrize("language", ("en", "ja"))
def test_the_card_asks_for_the_sign_alone_because_its_moment_is_asked_separately(language):
    """A cue tied its sign to the moment it came at, and named the moment by
    what the giver saw: "the left thumb worries the rope callus once as the
    counting-house door comes up on the right" (the 2026-10-09 replay of
    chat 166 turn 4598, on the pack card). When a tell shows is asked of the
    read-back on its own (`tell_when`); with this sentence the same beat
    wrote "the left thumb rubs once, slow, across the rope callus on her
    palm" (2026-10-10)."""
    card = bare_character_prompt(language)
    moves = next(p for p in card.split("\n\n") if "`want`" in p and "`tells`" in p)
    for phrase in _SIGN_ALONE[language]:
        assert phrase in moves, phrase


_OUTSIDE = {
    "en": ("WHAT GIVES YOU AWAY: {tell}\nDoes it name anything besides you and what you are doing -- "
           "something happening around you, a sight or a sound, or someone else's words or doings?"),
    "ja": ("本心を漏らすもの: {tell}\nあなた自身のほかに、何か・誰かのことが書かれていますか"
           "（周りの出来事、見えるもの、聞こえる音、ほかの人の言葉や動き）？"),
}


@pytest.mark.parametrize("language", ("en", "ja"))
def test_the_floor_question_is_the_wording_the_probes_chose(language):
    """Pinned verbatim: each pack's wording is the one its own probe chose
    (`jev.after_questions`, the comment at `tell:<j>:outside`). The English
    caught 12 of 13 made-up leaks and 32 of 44 stored cues naming something
    besides their giver, dropping 1 of 49 that gave the sign alone; the
    Japanese, asked of the same thirteen leaks translated, 9 (the English
    there 11), dropping none of ten."""
    assert character_jev_text("tell_outside", language).strip() == _OUTSIDE[language]


def test_a_sign_that_names_something_besides_its_giver_is_not_shown():
    """A cue reaches every observer the gate admits word for word
    (`perception._delivered_manifest`), so the scene a giver saw rode along
    with the sign: on the 2026-10-09 replay of chat 166 turn 4598 a tell
    naming the counting-house door was the only mention of one in the
    narrator's input, and the page drew it -- the player acquired the
    giver's view through no channel of her own. The read-back asks of each
    tell whether it names anything besides its giver; the compile shows it
    only on a no, and an unanswered question vouches for nothing."""
    h = _holding()
    leak = "the hand on the guide rope tightens until the knuckles pale as the counting house door slides past"
    reply = _reply(tells=[leak])
    question = jev.after_questions(h, reply)["tell:0:outside"]
    assert leak in question["instructions"] and set(question["criteria"]) == {"yes", "no"}
    named, warnings = character_bare.compile_bare(reply, _answers({"tell:0:outside": "yes"}), h)
    assert named["manifest"]["tells"] == []
    assert any("names something besides its giver" in w for w in warnings), warnings
    kept, warnings = character_bare.compile_bare(reply, _answers({"tell:0:outside": "no"}), h)
    assert [t["cue"] for t in kept["manifest"]["tells"]] == [leak] and warnings == []
    unread, warnings = character_bare.compile_bare(reply, {}, h)
    assert unread["manifest"]["tells"] == [], "fails closed"
    assert any("could not vouch" in w for w in warnings), warnings


def test_the_tell_shown_is_the_first_the_floor_passes_not_the_first_written():
    """With one tell a reply (`MAX_TELLS`), a first tell the floor withheld
    silenced the beat even when the same reply wrote a valid sign beside it.
    On the 68 stored replies of chats 159-166 that keep their call, read
    back in the engine's request shape, the floor withheld the first tell of
    21 and 19 of those had written another, which passed on 16: chat 166
    turn 4603, a beat in a composure crisis -- the one case the card
    requires a tell -- lost "the hum cuts off mid-note as Coyle's eyes
    finish the second pass" and had written "the knuckles on the scull loom
    go white, the loom creaking faintly under the grip" beside it. The
    read-back asks the floor, and what a shown tell needs, of the reply's
    first `TELLS_ASKED`, inside the same request; the compile shows the
    first that passes, still at most `MAX_TELLS` (the owner, 2026-10-10:
    "recover a valid second cue beside a dropped one"). A tell is shown on
    63 of those 68 replies where it was 47. A leak is withheld exactly as
    before."""
    h = _holding()
    leak = "the hum cuts off mid-note as Coyle's eyes finish the second pass"
    sign = "the knuckles on the scull loom go white, the loom creaking faintly under the grip"
    reply = _reply(tells=[leak, sign, "a third, never asked"])
    asked = {key for key in jev.after_questions(h, reply) if key.startswith("tell:")}
    assert jev.TELLS_ASKED == 2
    assert asked == {f"tell:{j}:{part}" for j in range(jev.TELLS_ASKED)
                     for part in ("channel", "miss", "outside", "when")}
    answers = _answers({"tell:0:outside": "yes", "tell:0:channel": "heard", "tell:0:miss": "plain",
                        "tell:1:outside": "no", "tell:1:channel": "seen", "tell:1:miss": "noticeable",
                        "tell:1:when": "s1"})
    out, warnings = character_bare.compile_bare(reply, answers, h)
    (shown,) = out["manifest"]["tells"]
    assert shown["cue"] == sign, "the valid sign beside the withheld one"
    assert (shown["channel"], shown["subtlety"], shown[character_bare._AT_STEP]) == (
        "seen", jev.MISS["noticeable"], 1), "placed by its own answers, never the withheld one's"
    assert any("names something besides its giver" in w and "Coyle" in w for w in warnings), warnings
    # Two withheld: nothing past the number asked stands in.
    neither, _ = character_bare.compile_bare(reply, _answers({"tell:0:outside": "yes", "tell:1:outside": "yes"}),
                                             h)
    assert neither["manifest"]["tells"] == []
    # A first that passes is the one shown, whatever was asked beside it.
    first, warnings = character_bare.compile_bare(
        reply, _answers({"tell:0:outside": "no", "tell:1:outside": "no"}), h)
    assert [t["cue"] for t in first["manifest"]["tells"]] == [leak] and warnings == []


def test_the_scene_floor_is_one_switch_and_off_the_first_tell_shows_unasked(monkeypatch):
    """The scene floor is a decision-model reading of free prose that
    removes text, and of the 22 deliveries it withholds on the stored tells
    of chats 159-166, 12 named only what their observer said, did, held or
    shared. The owner kept it on (2026-10-10), to be cut or narrowed if the
    next play run shows it withholding valid cues -- so it is one switch
    (`jev.TELL_SCENE_FLOOR`), and that ruling is one line. Off, the read-back
    asks no floor question and only `MAX_TELLS` tells, and the compile shows
    the first, as it did before the floor -- an unanswered read-back at 0.5."""
    assert jev.TELL_SCENE_FLOOR is True, "on, by the owner's ruling of 2026-10-10"
    monkeypatch.setattr(jev, "TELL_SCENE_FLOOR", False)
    h = _holding()
    leak = "the hand on the guide rope tightens until the knuckles pale as the counting house door slides past"
    reply = _reply(tells=[leak, "a quick breath"])
    asked = {key for key in jev.after_questions(h, reply) if key.startswith("tell:")}
    assert asked == {"tell:0:channel", "tell:0:miss", "tell:0:when"}
    out, warnings = character_bare.compile_bare(reply, _answers({"tell:0:outside": "yes"}), h)
    assert [t["cue"] for t in out["manifest"]["tells"]] == [leak] and warnings == []
    unread, warnings = character_bare.compile_bare(reply, {}, h)
    assert [(t["cue"], t["subtlety"]) for t in unread["manifest"]["tells"]] == [(leak, 0.5)] and warnings == []


# --- the gate: the observer's reach on the scale the tell is graded on -------------

_CUE = "a hand that goes still on the rail"


def _delivered(subtlety, *, known=False, focus=None, sheet=None):
    scene = {"rooms": {"hall": {"name": "Hall", "adjacent": [], "light": "lit"}},
             "positions": {"Ada": "hall", "Bo": "hall"}}
    if focus:
        scene["orientation"] = {"Ada": {"focus": {"kind": "entity", "ref": focus}}}
    ctx = SimpleNamespace(reaction_results={}, character_results={7: {"manifest": {
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


_MISS_LABELS = {
    "en": {"plain": "Anyone near you would notice it, even with poor eyes or ears.",
           "noticeable": "Anyone who can see or hear you would notice it, even a stranger looking elsewhere.",
           "subtle": "Only someone watching you, or who knows you, would notice it.",
           "hidden": "Only someone who knows you and is watching you would notice it."},
    "ja": {"plain": "目や耳が弱い人でも、近くにいれば誰でも気づく。",
           "noticeable": "あなたが見えるか聞こえる人なら誰でも気づく。よそを見ている見知らぬ人でも。",
           "subtle": "あなたを見ている人か、あなたを知っている人だけが気づく。",
           "hidden": "あなたを知っていて、しかもあなたを見ている人だけが気づく。"},
}


@pytest.mark.parametrize("language", ("en", "ja"))
def test_each_grade_names_the_observer_its_point_admits(language):
    """The read-back's options and the gate are two representations of one
    scale, and they disagreed: "noticeable" read "Someone paying attention
    would catch it" -- the observer one advantage past a stranger -- while
    the gate admits a stranger looking elsewhere at that grade, so with the
    grade chosen in place of the expectation 16 of 102 stored tells would
    have reached such a stranger where the model had named someone paying
    attention (chats 159-166, re-graded 2026-10-10). Each option now names
    the observer the gate admits at its point; on the same tells the
    read-back chose "noticeable" for 2 of 128, and on seventeen made-up
    signs it still put a sob or a shattered cup at "plain" or "noticeable".
    Pinned verbatim: the wording is the one probed in each pack."""
    assert character_jev_options("miss", language) == _MISS_LABELS[language]
    poor = {"senses": [{"channel": "vision", "acuity": "poor"}]}
    assert _delivered(jev.MISS["plain"], sheet=poor) == [_CUE], "plain: even poor eyes"
    assert _delivered(jev.MISS["noticeable"], sheet=poor) == []
    assert _delivered(jev.MISS["noticeable"]) == [_CUE], "noticeable: a stranger looking elsewhere"
    assert _delivered(jev.MISS["subtle"]) == []
    assert _delivered(jev.MISS["subtle"], focus="Bo") == [_CUE], "subtle: someone watching"
    assert _delivered(jev.MISS["subtle"], known=True) == [_CUE], "subtle: someone who knows them"
    assert _delivered(jev.MISS["hidden"], known=True) == []
    assert _delivered(jev.MISS["hidden"], known=True, focus="Bo") == [_CUE], "hidden: both"


def _graded_tell(probabilities):
    """The subtlety a compiled tell carries for the read-back's answer."""
    h, reply = _holding(), _reply(tells=["a hand that goes still on the rail"])
    answers = {"tell:0:miss": {"type": "choice", "probabilities": dict(probabilities)},
               **_answers({"tell:0:outside": "no"})}
    out, _ = character_bare.compile_bare(reply, answers, h)
    return out["manifest"]["tells"][0]["subtlety"]


def test_a_tell_is_placed_at_the_grade_chosen_not_between_two():
    """The gate compares a subtlety with a reach that sits ON the grade
    points, so a subtlety between them decided delivery by the answer's
    tail: on the 2026-10-09 replay of chat 166 turn 4608 both of Hester's
    tells, called "subtle" (0.88, with 0.09 on "hidden"), came out
    0.652-0.665 and missed Tamsin one advantage past a stranger (0.65). In
    the stored run the old gate had delivered both."""
    subtle = _graded_tell({"noticeable": 0.03, "subtle": 0.88, "hidden": 0.09})
    assert subtle == jev.MISS["subtle"]
    assert _delivered(subtle, known=True) == [_CUE] and _delivered(subtle, focus="Bo") == [_CUE]
    assert _delivered(subtle) == [], "and still not a stranger glancing elsewhere"
    # The tail the other way changes nothing either: the grade is the grade.
    assert _graded_tell({"noticeable": 0.2, "subtle": 0.8}) == jev.MISS["subtle"]
    # An ordinary eye catches what the model called "noticeable", whatever
    # it put on "subtle" beside it.
    noticeable = _graded_tell({"noticeable": 0.7, "subtle": 0.3})
    assert noticeable == jev.MISS["noticeable"] and _delivered(noticeable) == [_CUE]
    # Unanswered stays where it was.
    assert _graded_tell({}) == 0.5


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
        out, _ = character_bare.compile_bare(reply, _answers({"tell:0:when": picked, "tell:0:outside": "no",
                                                              "do:2:seen": "outward"}), h)
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
        return _answers({"tell:0:when": "s1", "tell:0:outside": "no", "do:1:seen": "outward",
                         "demeanor:changed": "no"})

    monkeypatch.setattr(jev, "ask_before", lambda holding: {})
    monkeypatch.setattr(jev, "ask_after", read_back)
    out = character_module.character_step(ctx, char_id, nonce=0)
    assert seen["carriage"] == "level and quiet"
    assert out["manifest"]["surface_demeanor"] == "level and quiet"
    (tell,) = out["manifest"]["tells"]
    act = next(e for e in out["sequence"] if e.get("type") == "action")
    assert tell["at_event"] == act["event_id"]
    assert not [e for e in out["sequence"] + list(out.get("actions") or []) if STEP_MARK in e]


def test_a_tell_is_not_placed_where_its_observer_could_not_see_the_giver(temp_db, _no_model):
    """A tell admitted at the end of the beat is placed at its step only if
    the observer could see the giver just before that step. The case the
    review of 9a29099a traced: a line said from behind a shut door, then the
    door opened and the giver walked in, with the tell anchored at the line
    -- she was shown a visual sign at a moment she had no sight of him. It
    goes after the beat instead, where it was admitted."""
    from agents.perception import perception_outcome
    from tests.test_a_line_is_heard_from_where_it_was_spoken import _beat

    ctx = _beat(temp_db)
    shut = [{"to": "study", "barrier": "closed_door"}]
    temp_db.wset(ctx.chat.id, "scene", {
        "rooms": {"hall": {"name": "Hall", "light": "lit", "adjacent": shut},
                  "study": {"name": "Study", "light": "lit",
                            "adjacent": [{"to": "hall", "barrier": "closed_door"}]}},
        "positions": {"Hinami": "hall", "The Doctor": "study"},
        "entities": {}, "stations": {}, "attire": {}})
    said = "I never touched the money."
    sequence = [
        {"type": "speech", "text": said, "volume": "normal", "visibility": "overt",
         "conceal_from": [], "targets": [], "event_id": "walk:0:speech"},
        {"type": "action", "attempt": "opens the door and steps into the hall",
         "observable": "opens the door and steps into the hall",
         "visibility": "overt", "commitment": "asserted",
         "conceal_from": [], "targets": [], "event_id": "walk:1:action"},
    ]
    tell = {"cue": "his hand closes over his coat pocket", "channel": "seen",
            "subtlety": jev.MISS["plain"], "at_event": "walk:0:speech"}
    ctx["interaction_loop"]["rounds"][0]["result"]["sequence"] = sequence
    ctx.character_results[int(ctx.cast[0]["id"])] = {
        "sequence": sequence, "manifest": {"surface_demeanor": "", "tells": [tell]}}
    ctx.director_resolve = {
        "resolved_event": "He answers from the study, then comes in.",
        "dialogue_log": [{"speaker": "The Doctor", "exact_quote": said,
                          "volume": "normal"}],
        # The door's own opening is a causal step with its own moment in a
        # played beat; held fixed here, so only the mover's cut decides
        # whether she could see him when he spoke.
        "state_diff": {"positions": {"The Doctor": "hall"}},
    }
    out = perception_outcome(ctx, "n0")
    events = sorted((o for o in out["observations"]["player"] if o.get("phase") == "event"),
                    key=lambda o: o["order"])
    kinds = [(o["kind"], str((o.get("observed") or {}).get("text") or "")) for o in events]
    cues = [i for i, (kind, _) in enumerate(kinds) if kind == "cue"]
    walk = [i for i, (_, text) in enumerate(kinds) if "steps into the hall" in text]
    assert cues and walk, kinds
    assert cues[0] > walk[0], kinds


def test_a_reaction_phase_tell_reaches_who_saw_it(temp_db, _no_model):
    """A character who declared in the reaction phase gives its tells and
    carriage like any other: its lines and acts were delivered while its
    manifest was read from the interaction map alone (UNBUILT_CHARACTERS
    §6.18)."""
    from agents.perception import perception_outcome
    from tests.test_composer_pipeline import _interp, _make_ctx

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_interpret = _interp(char_id, [
        {"type": "speech", "text": "Hand it over.", "volume": "normal", "tone": "",
         "visibility": "overt", "conceal_from": []}])
    line = {"volume": "normal", "tone": "", "visibility": "overt", "conceal_from": [], "targets": []}
    tell = {"cue": "her grip whitens on the strap", "channel": "seen",
            "subtlety": jev.MISS["plain"]}
    ctx.character_results = {}
    ctx.reaction_results = {char_id: {
        "sequence": [{"type": "speech", "text": "Not a chance.", **line,
                      "event_id": f"turn:{ctx.turn.id}:character:{char_id}:0:speech"}],
        "manifest": {"surface_demeanor": "", "tells": [tell]}}}
    ctx.director_resolve = {"resolved_event": "", "state_diff": {}, "dialogue_log": [
        {"speaker": "Reya", "exact_quote": "Not a chance.", "volume": "normal"}]}
    out = perception_outcome(ctx, "n0")
    cues = [o for o in out["observations"]["player"] if o.get("kind") == "cue"]
    assert cues, out["observations"]["player"]
