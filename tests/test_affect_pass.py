"""The affect pass (mind/affect_pass.py): the character's mood, computed by the
engine and given to it.

The owner, 2026-09-26: "remove all mood related machinery from the character
prompt. and just have it fed to the character in it's packet. And have it
update the moods again post character actions."

Pinned here: the mood is carried between calls and decays toward the card's
temperament, and an earlier round's mood carries within a beat without
decaying; the decision model is asked once per pass, from a state built of
this character's own inputs only; what the call brings moves the mood and
names a surface and an undercurrent; the character's own acts move it again;
a memory recalled beat after beat habituates the owner's way, and one with no
stable key never does; the given affect passes through commit's own
`resolve_affect` with its label intact; the packet's block names the mood in
the pack's words; a pass that cannot ask the decision model fails open,
keeping the carried mood; and the mood the engine keeps survives rollback,
branching and export.
"""

from __future__ import annotations

import pytest

from llm import decisions
from llm.prompts import affect_appraisal_options
from mind import affect, affect_mix as mix
from mind import affect_pass as ap

SHEET = {"psychology": {
    "drive": {"essence": "To keep the harbour safe.", "expression": "Reads the weather first."},
    "values": [{"name": "Duty over comfort", "priority": 0.9}],
    "traits": [{"name": "Steady", "expression": "Does not flinch."}],
    "self_model": {"summary": "A keeper of the harbour."},
    "learning": {"associations": [{"cue": "a boat horn in fog", "appraisal_bias": "someone is in trouble"}]}}}
OBSERVATIONS = [{"observation_id": "o1", "observed": {"text": "says she took the key."}, "actor": "Hinami",
                 "order": 0},
                {"observation_id": "o2", "observed": {"text": "The lamp gutters."}, "order": 1, "standing": True}]
MEMORY = {"recalled_old_memories": [{"event_key": "m1", "details": "The summer at the lake, swimming every day."}]}
ACTIVE = {"active_concerns": ["who opened the lock"]}
PEOPLE = {"Hinami": {"warmth": 0.6, "trust": 0.4, "familiarity": 0.9}}
BASELINE = {"valence": 0.0, "arousal": 0.5}


def _pick(key, criteria):
    """How the fake decision model answers: what Hinami did angers, strongly;
    a pleasant memory stirs nostalgia; a concern weighs; a tense and angry
    mood; and an act against the character's values that stoked it."""
    rules = [("stir_strength", "strong"), ("feel", "anger"), ("strength", "strong"), ("tone", "pleasant"),
             ("kinds", "nostalgia"), ("weight", "clear"), ("dim:tension", "s4"), ("dim:pleasure", "s0"),
             ("mood:anger", "strong"), ("act_against_values", "strong"), ("act_held_back", "strong"),
             ("act_eased_or_stoked", "stoked")]
    for needle, choice in rules:
        if needle in key and choice in criteria:
            return choice
    for neutral in ("neutral", "neither", "none", "s2", "nobody"):
        if neutral in criteria:
            return neutral
    return next(iter(criteria))


@pytest.fixture
def jev(monkeypatch):
    seen = []

    def answer(state, questions):
        seen.append((state, dict(questions)))
        return {k: {"type": "choice", "choice": (c := _pick(k, q["criteria"])), "probabilities": {c: 1.0}}
                for k, q in questions.items()}

    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    return seen


def _before(**kw):
    args = dict(name="Aldo", sheet=SHEET, active=ACTIVE, baseline=BASELINE, units=1.0, observations=OBSERVATIONS,
                memory_context=MEMORY, relationships=PEOPLE, language="en")
    args.update(kw)
    return ap.before_call(**args)


def test_what_the_call_brings_moves_the_mood_and_names_it(jev):
    felt = _before()
    assert felt.asked and felt.mood.get("anger") > 0 and felt.mood.get("tension") > 0
    affect_now = ap.given_affect(felt)
    words = affect_appraisal_options("mood_words", "en")
    assert affect_now["surface"]["label"].startswith(words["anger"])
    assert set(affect_now["surface"]) == {"label", "valence", "arousal"}
    under = affect_now["undercurrent"]
    assert under and set(under) == {"label", "valence", "arousal", "source", "serves"}
    assert under["source"].split(":")[0] in ("memory", "concern")
    block = ap.feelings_block(felt)
    assert set(block) == {"now", "beneath", "mood"} and block["now"][0] == affect_now["surface"]["label"]
    assert block["beneath"][0] == under["label"] and block["mood"]


def test_a_mind_is_given_what_it_feels_at_once_strongest_first():
    """The owner, 2026-09-26: "allow characters to feel multiple moods". A
    present feeling at least NOW_SHARE of the strongest is given beside it --
    one per kind, at most NOW_FEELINGS -- and a faint one is not."""
    from mind.affect_mix import Emotion, Mood

    felt = ap.Felt(mood=Mood({}), home=Mood({}), habits={}, clock=0.0, language="en",
                   emotions=[Emotion("relief", 0.9, "the scan was clear", "event", "o1"),
                             Emotion("fear", 0.6, "what the doctor did not say", "event", "o2"),
                             Emotion("relief", 0.8, "the waiting is over", "event", "o3"),
                             Emotion("joy", 0.2, "the sun on the car park", "event", "o4"),
                             Emotion("grief", 0.7, "mother's illness began like this", "memory", "m1")])
    block = ap.feelings_block(felt)
    assert [w.split(" (")[0] for w in block["now"]] == ["relief", "fear"]
    assert block["now"][0].endswith("(the scan was clear)")
    assert [w.split(" (")[0] for w in block["beneath"]] == ["grief"]
    many = ap.Felt(mood=Mood({}), home=Mood({}), habits={}, clock=0.0, language="en",
                   emotions=[Emotion(n, 0.9 - i * 0.05, "it", "event", f"o{i}")
                             for i, n in enumerate(("anger", "fear", "distress", "hope", "joy"))])
    assert len(ap.feelings_block(many)["now"]) == ap.NOW_FEELINGS


def test_a_feeling_given_as_now_is_not_given_again_beneath():
    """When the moment stirred nothing, `now` falls back to the strongest
    past or unsettled feeling -- and `beneath`, listing what is felt
    alongside the undercurrent, offered that same feeling a second time
    (the bare-card replay, 2026-09-27: a jealousy about a rival stood in
    both lists). What is named now is not named again beneath."""
    from mind.affect_mix import Emotion, Mood

    felt = ap.Felt(mood=Mood({}), home=Mood({}), habits={}, clock=0.0, language="en",
                   emotions=[Emotion("jealousy", 0.8, "the rival at the director's elbow", "concern", "c0"),
                             Emotion("anticipation", 0.6, "the season's casting", "concern", "c1")])
    block = ap.feelings_block(felt)
    assert [w.split(" (")[0] for w in block["now"]] == ["jealousy"]
    assert [w.split(" (")[0] for w in block["beneath"]] == ["anticipation"]


def test_one_request_per_pass_from_this_characters_own_inputs(jev):
    _before()
    assert len(jev) == 1
    state, questions = jev[0]
    assert "YOU ARE Aldo." in state and "To keep the harbour safe." in state
    assert "Hinami: says she took the key." in state and "summer at the lake" in state
    assert "who opened the lock" in state
    # the standing observation is scenery, not an event to appraise
    assert "The lamp gutters." not in state and not any(":o2:" in k for k in questions)


def test_nothing_new_asks_nothing(jev):
    felt = _before(observations=[], memory_context={}, active={})
    assert jev == [] and not felt.asked and "nothing new" in felt.note


def test_a_pass_that_cannot_ask_fails_open_with_the_carried_mood(monkeypatch):
    def refuse(state, questions):
        raise decisions.DecisionError("jev 402: out of credit")

    monkeypatch.setattr(decisions, "OVERRIDE", refuse)
    stored = {"mood_coords": {"tension": 0.6}, "mood_clock": 3.0, **ACTIVE}
    felt = _before(active=stored, units=0.0)
    assert not felt.asked and "could not be asked" in felt.note
    assert felt.mood.get("tension") == pytest.approx(0.6)


def test_the_carried_mood_decays_toward_temperament_and_round_trips():
    stored = {"mood_coords": {"pleasure": 0.8, "anger": 0.8}, "mood_clock": 2.0, "mood_habits": {"m1": {"h": 0.4, "at": 1.0}}}
    mood, home, habits, clock = ap.carried(stored, BASELINE, mix.SPECTRUM_HALF_LIFE)
    assert mood.get("pleasure") == pytest.approx(0.4)
    assert mood.get("anger") == pytest.approx(0.8 * 0.5 ** (mix.SPECTRUM_HALF_LIFE / mix.STANDALONE_HALF_LIFE))
    assert clock == pytest.approx(2.0 + mix.SPECTRUM_HALF_LIFE) and habits == stored["mood_habits"]
    felt = ap.Felt(mood=mood, home=home, habits=habits, clock=clock)
    again, _home, _habits, _clock = ap.carried(ap.persisted(felt), BASELINE, 0.0)
    assert again.get("pleasure") == pytest.approx(mood.get("pleasure"), abs=1e-4)


def test_an_earlier_round_this_beat_carries_without_decay(jev):
    first = _before()
    second_mood, _home, _habits, clock = ap.carried({}, BASELINE, 5.0, earlier=ap.persisted(first))
    assert second_mood.coords == pytest.approx({k: round(v, 4) for k, v in first.mood.coords.items()
                                                if abs(v) > 1e-4}, abs=1e-4)
    assert clock == pytest.approx(first.clock)


def test_the_characters_own_acts_move_the_mood_again(jev):
    felt = _before()
    before_regard = felt.mood.get("self_regard")
    reply = {"sequence": [{"type": "speech", "text": "I never had the key."}],
             "active_state": {"wants": [{"want": "tell her the truth"}], "suppressed_want": 0}}
    after = ap.after_call(felt, reply)
    assert len(jev) == 2 and "WHAT YOU JUST DID" in jev[1][0] and "You held back from: tell her the truth" in jev[1][0]
    assert {"shame", "frustration"} <= {e.name for e in after.emotions if e.source == "act"}
    assert after.mood.get("self_regard") < before_regard
    # the restraint's cost is felt once, from the want held back -- never
    # once more for every act beside it (15 of 16 traced beats kept
    # frustration when it was)
    frustrated = [e for e in after.emotions if e.name == "frustration"]
    assert [e.ref for e in frustrated] == ["held"]
    held_questions = [k for k in jev[1][1] if k.endswith(":act_held_back")]
    assert held_questions == ["act:held:act_held_back"]
    assert "tell her the truth" in jev[1][1]["act:held:act_held_back"]["instructions"]


def test_a_memory_recalled_beat_after_beat_habituates(jev):
    felt, strengths = None, []
    stored = dict(ACTIVE)
    for _beat in range(8):
        felt = _before(observations=[], active=stored, units=1.0)
        strengths.append(max(e.intensity for e in felt.emotions if e.source == "memory"))
        stored = {**ACTIVE, **ap.persisted(felt)}
    assert strengths[0] == pytest.approx(strengths[1]) and strengths[-1] < strengths[0]


def test_a_minds_own_earlier_lines_are_not_appraised_again_as_events():
    """A later round of a beat hands a mind its own earlier conduct back
    (`loops.self_micro_view`: "You said: ..."). Its feeling was appraised once,
    after it acted; taken again as a perceived event it counted twice, and in
    the lie test story a magistrate's second round was handed "gratification
    (You said: ...)" as how he felt NOW (2026-09-26)."""
    from agents.loops import _micro_observation, self_micro_view

    mine = []
    self_micro_view({"sequence": [{"type": "speech", "text": "Both are recorded."}]},
                    observation_out=mine, observer_id="7", event_prefix="micro:1:7")
    theirs = [_micro_observation("7", 'Kit Sawyer says: "Write it down."', event_prefix="micro:0:3",
                                 event_index=0, kind="speech", channel="hearing", actor="Kit Sawyer")]
    assert mine and theirs
    assert [e["actor"] for e in ap.events_from(theirs + mine)] == ["Kit Sawyer"]


def test_a_memory_without_a_stable_key_never_habituates(jev):
    # 134 of 17,065 rows in the owner's db carry no event_key; their only name
    # is their place in the packet, and a place is not a memory.
    unkeyed = {"recalled_old_memories": [{"details": MEMORY["recalled_old_memories"][0]["details"]}]}
    felt, strengths = None, []
    stored = dict(ACTIVE)
    for _beat in range(8):
        felt = _before(observations=[], active=stored, units=1.0, memory_context=unkeyed)
        strengths.append(max(e.intensity for e in felt.emotions if e.source == "memory"))
        stored = {**ACTIVE, **ap.persisted(felt)}
    assert strengths[-1] == pytest.approx(strengths[0])
    assert ap.persisted(felt)["mood_habits"] == {}


# --- a memory keeps what its moment made the mind feel ----------------------------
#
# The owner, 2026-09-29: a memory's mood "should be a stored value made at
# memory formation not one derived every turn" -- "we use the moods of the
# beat based on character perception and the pass based on how their actions
# make them feel and store those".

MOMENT = {"moment": {"felt": {"tenderness": 0.6}, "strength": 0.6, "at": 0.0, "turn": 3,
                     "key": "3:perceived"}}


def _kept(record=None, disputed_turn=None, key="m1"):
    """A packet whose one recalled row keeps `record`, the way
    `mind/memory_context.py` hands it over: in the host-only registry."""
    return {"recalled_old_memories": [{"event_key": key, "details": "The summer at the lake, swimming every day."}],
            "_internal": {"feelings": {key: {"record": record, "disputed_turn": disputed_turn}}}}


def _memory_questions(questions):
    return {k for k in questions if k.startswith("mem:")}


def test_a_memory_that_keeps_its_feeling_brings_it_back_unasked(jev):
    felt = _before(memory_context=_kept(MOMENT))
    assert _memory_questions(jev[0][1]) == set()
    recalled = [e for e in felt.emotions if e.source == "memory"]
    assert [e.name for e in recalled] == ["tenderness"]
    assert recalled[0].intensity == pytest.approx(0.6 * mix.memory_fade(felt.clock), abs=1e-4)
    assert felt.looks == {}


def test_a_memory_with_nothing_kept_is_read_once_and_the_reading_kept(jev):
    felt = _before()  # MEMORY's row keeps nothing: a row minted before memories kept their feeling
    assert _memory_questions(jev[0][1]) == {"mem:m1:strength", "mem:m1:tone", "mem:m1:kinds"}
    look = felt.looks["m1"]
    assert look["why"] == "unfelt" and look["felt"]["nostalgia"] > 0 and look["at"] == pytest.approx(felt.clock)
    assert "nostalgia" in {e.name for e in felt.emotions if e.source == "memory"}
    # kept on the row as commit keeps it, the reading stands from then on
    jev.clear()
    again = _before(memory_context=_kept({"looks": [{**look, "turn": 4}]}), active={**ACTIVE, **ap.persisted(felt)})
    assert _memory_questions(jev[0][1]) == set() and again.looks == {}
    assert "nostalgia" in {e.name for e in again.emotions if e.source == "memory"}


def test_a_memory_re_read_since_its_feeling_was_kept_is_read_again(jev):
    _before(memory_context=_kept(MOMENT, disputed_turn=2))
    assert _memory_questions(jev[-1][1]) == set()
    felt = _before(memory_context=_kept(MOMENT, disputed_turn=7))
    assert _memory_questions(jev[-1][1]) and felt.looks["m1"]["why"] == "reread"
    # a re-reading recorded on the turn of the latest reading came after it:
    # the row is read before the call, the re-reading kept at its commit
    reread_then = {"looks": [{"felt": {"grief": 0.4}, "strength": 0.4, "at": 1.0, "turn": 7}]}
    felt = _before(memory_context=_kept(reread_then, disputed_turn=7))
    assert felt.looks["m1"]["why"] == "reread"


def test_what_the_beat_made_the_mind_feel_is_formed_by_layer(jev):
    felt = _before()
    reply = {"sequence": [{"type": "speech", "text": "I never had the key."}],
             "active_state": {"wants": [{"want": "tell her the truth"}], "suppressed_want": 0}}
    formed = ap.persisted(ap.after_call(felt, reply))["formed"]
    assert set(formed) == {"perceived", "acted"}
    assert "anger" in formed["perceived"]["felt"] and formed["perceived"]["strength"] > 0
    assert {"shame", "frustration"} <= set(formed["acted"]["felt"])
    # the layer beneath is kept by neither: the recalled memory's nostalgia
    # stored into a new memory would copy itself forward without end
    assert "nostalgia" not in set(formed["perceived"]["felt"]) | set(formed["acted"]["felt"])
    assert formed["perceived"]["at"] == pytest.approx(felt.clock)


def test_a_rows_layer_is_what_it_is_about():
    assert ap.facet_of({"category": "self"}) == "acted"
    assert {ap.facet_of({"category": c}) for c in ("episode", "dialogue", "promise", "inference")} == {"perceived"}


def test_the_rows_of_one_moment_bring_its_feeling_back_once(jev):
    context = {"recalled_old_memories": [{"event_key": "t3:c1:episode", "details": "The harbour at dusk."},
                                          {"event_key": "t3:c1:dialogue", "details": "I heard her say goodbye."}],
               "_internal": {"feelings": {"t3:c1:episode": {"record": MOMENT},
                                          "t3:c1:dialogue": {"record": MOMENT}}}}
    felt = _before(memory_context=context)
    assert [e.name for e in felt.emotions if e.source == "memory"] == ["tenderness"]
    # both rows were recalled, so both land for habituation
    assert set(felt.habits) == {"t3:c1:episode", "t3:c1:dialogue"}


def test_a_delivered_memory_is_handed_its_feelings_name_never_its_numbers(jev):
    """The owner, 2026-09-29: "We should keep the spectrum values so we can do
    math with them but only the code derived memory name should be exposed to
    the character"."""
    kept = _kept(MOMENT)
    ap.name_memories(kept, _before(memory_context=kept))
    row = kept["recalled_old_memories"][0]
    assert row["how_it_feels"] == ap._word("tenderness", "en")
    assert not any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in row.values())
    # a row read afresh this call is named by that reading
    legacy = {"recalled_old_memories": [dict(MEMORY["recalled_old_memories"][0])]}
    ap.name_memories(legacy, _before(memory_context=legacy))
    assert legacy["recalled_old_memories"][0]["how_it_feels"] == ap._word("nostalgia", "en")
    # one that keeps nothing and was not read is named nothing
    unread = {"recalled_old_memories": [dict(MEMORY["recalled_old_memories"][0])]}
    ap.name_memories(unread, None)
    assert "how_it_feels" not in unread["recalled_old_memories"][0]


def test_a_memorys_feeling_is_named_in_the_storys_language(jev):
    en, ja = _kept(MOMENT), _kept(MOMENT)
    ap.name_memories(en, _before(memory_context=en))
    ap.name_memories(ja, _before(memory_context=ja, language="ja"))
    assert ja["recalled_old_memories"][0]["how_it_feels"] == ap._word("tenderness", "ja")
    assert ja["recalled_old_memories"][0]["how_it_feels"] != en["recalled_old_memories"][0]["how_it_feels"]


def test_a_later_round_reads_no_memory_twice_and_keeps_the_whole_beat(jev):
    first = _before()
    second = _before(earlier=ap.persisted(first),
                     observations=[{"observation_id": "o3", "observed": {"text": "laughs at the joke."},
                                    "actor": "Hinami", "order": 0}])
    assert _memory_questions(jev[1][1]) == set() and "m1" in second.looks
    assert set(second.formed["perceived"]["felt"]) >= set(first.formed["perceived"]["felt"])


def test_the_given_affect_passes_through_commits_resolver_with_its_label(jev):
    given = ap.given_affect(_before())
    resolved = affect.resolve_affect(None, {}, {"valence": 0.0, "arousal": 0.5}, 1, proposed=given)
    assert resolved["surface"]["label"] == given["surface"]["label"]
    assert (resolved.get("undercurrent") or {}).get("label") == given["undercurrent"]["label"]


@pytest.mark.parametrize("language", ["en", "ja"])
def test_every_word_the_block_can_use_is_in_the_pack(language):
    emotions = affect_appraisal_options("emotion_words", language)
    moods = affect_appraisal_options("mood_words", language)
    assert all(n in emotions or n in moods for n in mix.EMOTION_EFFECTS)
    assert set(mix.STANDALONE) <= set(moods)


def test_the_engines_mood_survives_rollback_branch_and_export(temp_db):
    """`mood_coords`, `mood_habits` and `mood_clock` ride inside
    `chat_chars.state`, keyed by memory `event_key` -- copy-stable by design --
    so no path that moves a character's state may drop or rewrite them."""
    import json
    import time

    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app

    mood = {"mood_coords": {"tension": 0.42, "haunted": 0.31}, "mood_clock": 3.5,
            "mood_habits": {"t7:c2:episode": {"h": 0.25, "at": 2.0}}}
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Mood", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)", ("Aldo", "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,state) VALUES(?,?,?)",
               (cid, char_id, json.dumps({"active_state": dict(mood)})))
    frame_id = temp_db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) VALUES(?,?,?,?,?)",
                          (cid, "Present", 0, "present", time.time()))
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                         (cid, 0, "wait", time.time(), frame_id))

    def carried(chat):
        row = temp_db.q("SELECT state FROM chat_chars WHERE chat_id=?", (chat,), one=True)
        active = json.loads(row["state"] or "{}").get("active_state") or {}
        return {k: active.get(k) for k in mood}

    ensure_checkpoint(cid, 0)
    temp_db.qi("UPDATE chat_chars SET state=? WHERE chat_id=?", (json.dumps({"active_state": {}}), cid))
    restore_checkpoint(cid, 0)
    assert carried(cid) == mood, "rollback lost the engine's mood"

    branch = app.turn_branch(turn_id)["id"]
    assert carried(branch) == mood, "a branch lost the engine's mood"

    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(branch)})
    assert carried(imported["id"] if isinstance(imported, dict) else imported) == mood, (
        "export and import lost the engine's mood")
