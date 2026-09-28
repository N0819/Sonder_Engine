"""The bare character contract: a card about being the character, a reply
that carries only what a character can write, and the decision model for
everything the long reply used to spell out (agents/character_bare.py,
mind/character_jev.py; the owner, 2026-09-26: "I truly want an as bare bones
character prompt as possible. That still basically does the same thing
thanks to jev")."""

from copy import deepcopy

import pytest

from agents import character_bare
from agents.character import _ground_observation_citations
from llm import decisions
from llm.prompts import bare_character_prompt
from llm.schemas import CharacterBareOutput, validate_llm_output
from mind import character_jev as jev
from tests.test_character_continuity import story  # noqa: F401 -- the fixture

BARE_KEYS = ("want", "held_back", "hinge", "unsure", "sequence", "demeanor",
             "tells", "changes", "note", "notebook")


def _dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


# --- the reply and the card --------------------------------------------------------

def test_the_reply_holds_only_what_a_character_writes():
    """The full card's spellings are read as the bare ones they mean, and a
    tell written as an object is its cue, never its JSON."""
    reply = _dump(CharacterBareOutput(**{
        "want": "get the key back",
        "sequence": [{"type": "speech", "text": "Give it here.", "tone": "quietly"},
                     {"type": "action", "attempt": "hold out a hand"},
                     {"type": "ponder", "query": "where I last saw it"}],
        "tells": [{"cue": "jaw tight", "channel": "seen"}],
        "changes": "I do not trust Mara"}))
    steps = reply["sequence"]
    assert (steps[0]["say"], steps[0]["how"]) == ("Give it here.", "quietly")
    assert steps[1]["do"] == "hold out a hand"
    assert steps[2]["ponder"] == "where I last saw it"
    assert reply["tells"] == ["jaw tight"]
    assert reply["changes"] == ["I do not trust Mara"]


@pytest.mark.parametrize("language", ("en", "ja"))
def test_the_bare_card_is_short_and_ends_on_its_reply(language):
    card = bare_character_prompt(language)
    # The full card is 22,853 characters of instructions; this one, with the
    # universal language contract appended and the notebook's paragraph, is a
    # fifth of that. The owner, 2026-09-27, when the notebook came in: "Lets
    # not focus on minimal prompting, what do you think is best but not
    # extremely large?"
    assert len(card) < 4500
    lines = card.split("\n")
    output = next(i for i, line in enumerate(lines) if '"want"' in line and '"sequence"' in line)
    identity = next(i for i, line in enumerate(lines) if "{name}" in line)
    assert identity == output - 1, "who you are sits just before the reply's shape"
    for key in BARE_KEYS:
        assert f'"{key}"' in lines[output], key


def test_the_card_supplies_no_default_temperament():
    """Scope must not quietly author a cautious personality: a turn ends
    where someone else must answer or the world must decide, never at a
    size. Carried from the full card's gating tests (2026-09-27)."""
    card = bare_character_prompt("en")
    assert "nothing here prefers a small move to a large one" in card
    for brake in ("Consider silence, a small response", "It is a brake on unearned action",
                  "must be yielded to"):
        assert brake not in card


def test_a_section_ships_only_when_the_moment_calls_for_it():
    quiet = character_bare.modules_for({"self": {}, "perception": {}})
    assert quiet == []
    loud = character_bare.modules_for(
        {"self": {"project_review": {"id": "p1"}, "still_waiting_for": [{"what": "rope"}],
                  "crisis": True, "recent_tells": ["a swallow"],
                  "tell_grounds": [{"cue": "a swallow", "because": "the key"}],
                  "recent_self_refrain": {"opening": {"word": "listen", "lines": 4, "of": 5}}},
         "decision": {"they_said_nothing": True, "awaiting_your_answer": {"from": "Mara"},
                      "comes_to_you": [{"offer": "x"}],
                      "speech_budget": {"min_lines": 1, "suggested_lines": 2, "hard_max": 4}},
         "perception": {"impossible_knowledge": [{"line_ref": "o1"}], "spatial_frame": {"ahead": [{"room": "Hall"}]}},
         "carried_reports": [{}]},
        disputed=[{"ref": "event:a", "text": "x"}], rupture_open=True, rupture_forced=True)
    assert loud == ["their_silence", "answer_owed", "offers", "speech_budget", "crisis",
                    "tell_variety", "tell_payoff", "repetition", "dispute", "drive_rupture",
                    "drive_rupture_forced", "project_review", "still_waiting", "impossible_knowledge",
                    "carried_reports", "ways_on"]
    # Each restored section is the old card's clause, said when it applies,
    # and names the payload key it explains.
    for module, key in (("their_silence", "decision.they_said_nothing"),
                        ("answer_owed", "decision.awaiting_your_answer"),
                        ("offers", "decision.comes_to_you"), ("speech_budget", "decision.speech_budget"),
                        ("crisis", "self.crisis"), ("tell_variety", "self.recent_tells"),
                        ("tell_payoff", "self.tell_grounds"), ("repetition", "self.recent_self_refrain"),
                        ("ways_on", "perception.spatial_frame")):
        for lang in ("en", "ja"):
            assert f"`{key}`" in character_bare.prompt("Wren", [module], lang), (module, lang)
    card = character_bare.prompt("Wren", ["dispute"], "en")
    assert "may_mean_otherwise" in card and "{name}" not in card
    assert card.index("may_mean_otherwise") < card.index("You are Wren"), (
        "a section joins the core, before the identity-and-reply tail")
    assert "may_mean_otherwise" not in character_bare.prompt("Wren", [], "en")


# --- what the decision model is asked, and of whom ----------------------------------

def _holding(**overrides):
    base = dict(
        name="Wren", language="en", psychology="HOW YOU ARE: careful",
        events=[{"ref": "current:Wren:0", "text": "Mara pockets the brass key.", "actor": "Mara"},
                {"ref": "current:Wren:1", "text": "Tomas says, \"Let it go.\"", "actor": "Tomas"}],
        people=["Mara", "Tomas"], known=["Mara", "Tomas"],
        memories=[{"ref": "event:kind", "text": "Mara once lent me her coat in the rain."},
                  {"ref": "event:key", "text": "I hid the brass key under the loose board."}],
        aims=[{"kind": "drive", "id": "drive", "text": "keep the family safe"},
              {"kind": "intention", "id": "i3", "text": "recover the key"}],
        beliefs=["Mara is honest with me."],
        associations=[{"cue": "a hand in a pocket", "appraisal_bias": "suspicion"}],
        concerns=["the key is missing"],
        contacts=[{"ref": "contact:0", "text": "your hand on Mara's sleeve"}],
        promises=[{"from": "Tomas", "what": "the rope", "turn": 3}],
        strategies=["go quiet and watch"],
        heard=[{"ref": "current:Wren:1", "text": "Tomas says, \"Let it go.\"", "speaker": "Tomas"}],
        drive={"essence": "keep the family safe", "expression": "watchful", "taboo": "betrayal"},
        charge=0.5)
    base.update(overrides)
    return jev.Holding(**base)


def _reply():
    return {
        "want": "get the key back", "held_back": "grab her wrist", "hinge": "she lied to me",
        "unsure": "whether Tomas knows",
        "sequence": [
            {"say": "Give it back.", "to": "Mara", "how": "under my breath",
             "why": "I hid it myself; Tomas must not hear"},
            {"do": "steel myself", "why": "this is Mara"},
            {"do": "hold out my hand to Mara", "why": "the key is mine"}],
        "demeanor": "very still", "tells": ["a tight jaw", "a quick breath", "a third, dropped"],
        "notebook": [{"about": "Mara", "note": "Mara is covering for someone.", "sure": "likely"}],
        "changes": ["Mara is not honest with me.", "Her kindness in the rain was a way in.",
                    "I stop trying to recover the key.", "I stop waiting on Tomas's rope."],
        "note": "keeping the key from Tomas",
    }


def test_every_question_reads_only_this_minds_own_holding():
    """The firewall by construction: every person, row and item a question
    names is one this mind perceived, was given or already holds."""
    from llm.prompts import character_jev_options
    h = _holding(notebook=_notebook_view())
    questions = {**jev.before_questions(h), **jev.moment_questions(h), **jev.after_questions(h, _reply())}
    assert any(k.startswith("held:") for k in questions), "the note check is covered"
    offered = set()
    for q in questions.values():
        offered.update(q["criteria"].values())
    pack = set()
    for name in ("volume", "yesno", "act_kind", "grade", "miss", "channel", "signed", "fit", "tone", "change_kind",
                 "reading_kind", "aim_moved", "belief_touched", "impact", "certain",
                 "agency", "ability", "choices", "note_kind", "note_touched", "strike_kind", "echo_body",
                 "cue_held", "part_seen"):
        pack.update(character_jev_options(name, "en").values())
    held = ({e["text"] for e in h.events} | {m["text"] for m in h.memories} | set(h.people) | set(h.known)
            | set(h.beliefs) | set(h.strategies) | {jev._aim_label(a, "en") for a in h.aims}
            | {a["text"] for a in h.aims}
            | {f"{p['what']} ({p['from']})" for p in h.promises}
            | {f"You start following {p}." for p in h.people}
            | {f"You {verb} this: {m['text']}" for m in h.memories for verb in ("acted on", "pushed against")})
    assert offered <= pack | held, sorted(offered - pack - held)
    # Every evidence choice carries a way to say "none".
    for key, q in questions.items():
        if key.endswith((":now", ":remembered")):
            assert set(q["criteria"]) & {"nothing_now", "nothing_remembered"}, key
    # The model's reasoning is read after the call and never before it.
    assert "YOUR OWN THINKING" not in jev.state_text(_holding(reasoning="I think she lied."))
    assert "I think she lied." in jev.state_text(_holding(reasoning="I think she lied."), _reply())


def test_release_is_asked_only_once_something_has_built():
    assert "released" in jev.after_questions(_holding(charge=0.5), _reply())
    assert "released" not in jev.after_questions(_holding(charge=0.1), _reply())


def _answer(script):
    """A scripted decision model: the first matching needle picks the option;
    anything unscripted answers its most neutral option."""
    def pick(key, criteria):
        for needle, choice in script:
            if key == needle and choice in criteria:
                return choice
        for neutral in ("no", "none", "nothing", "neither", "same", "normal", "nobody",
                        "nothing_now", "nothing_remembered", "no_memory", "no_belief",
                        "no_aim", "no_promise", "no_target", "no_strategy", "other",
                        "situational", "follow_neither"):
            if neutral in criteria:
                return neutral
        return next(iter(criteria))
    return lambda questions: {k: {"type": "choice", "probabilities": {pick(k, q["criteria"]): 1.0}}
                              for k, q in questions.items()}


SCRIPT = [
    ("say:0:volume", "mutter"), ("say:0:to:0", "yes"), ("say:0:kept:1", "yes"), ("say:0:kept:0", "yes"),
    ("say:0:expects", "yes"),
    ("do:1:seen", "inner"), ("do:2:seen", "outward"), ("do:2:target", "p0"),
    ("want:serves", "a1"), ("want:urgency", "strong"), ("held_back:serves", "a0"),
    ("tell:0:channel", "seen"), ("tell:0:miss", "subtle"), ("tell:1:channel", "heard"),
    ("nb:0:kind", "goal"), ("nb:0:now", "e0"),
    ("change:0:kind", "belief"), ("change:0:belief", "b0"), ("change:0:now", "e0"),
    ("change:0:replaces", "changes"),
    ("belief:0:touched", "overturns"), ("belief:0:now", "e0"),
    ("change:1:kind", "rereading"), ("change:1:memory", "m0"), ("change:1:now", "e0"),
    ("change:1:remembered", "m0"),
    ("change:2:kind", "give_up"), ("change:2:aim", "a0"),
    ("change:3:kind", "stop_waiting"), ("change:3:promise", "w0"),
    ("aim:0:moved", "blocked"), ("aim:0:now", "e0"),
    ("cue:0", "yes"), ("cue:0:now", "e0"), ("cue:0:held", "bore_out"),
    ("rel:0:trust", "much_less"), ("rel:0:break", "yes"), ("rel:0:now", "e0"),
    ("rel:1:warmth", "more"),
    ("concern:0", "yes"), ("keep:0", "yes"), ("mem:shaped", "a1"),
    ("follow", "start0"), ("contact:0", "yes"), ("released", "yes"),
    ("novelty", "strong"), ("control", "slight"), ("coping", "slight"), ("norm", "against"),
    ("pain:0", "none"), ("pleasure:0", "none"), ("pain:1", "clear"),
    ("impact:1", "hurts_badly"), ("impact:1:now", "e0"), ("impact:1:certain", "done"),
    ("impact:1:agency", "other"),
    ("echo", "m1"), ("echo:1:threat", "strong"), ("echo:1:familiar", "clear"),
    ("coping_mode", "s0"), ("done_talking", "no"), ("salience", "strong"),
]


def test_the_reply_and_the_answers_compile_into_the_engine_shape():
    h, reply = _holding(), _reply()
    answers = _read_back(h, reply, SCRIPT)
    out, warnings = character_bare.compile_bare(reply, answers, h)
    assert warnings == []
    speech, inner, act = out["sequence"]
    # A line is never hidden from the one it is said to.
    assert (speech["volume"], speech["targets"], speech["conceal_from"]) == ("mutter", ["Mara"], ["Tomas"])
    assert speech["visibility"] == "concealed" and speech["tone"] == "under my breath"
    assert out["interaction"]["addresses"] == ["Mara"] and out["interaction"]["expects_response"]
    # An act no one could see is an inner act, and imperceptible.
    assert inner["observable"] == "" and inner["attempt"] == "steel myself"
    assert act["observable"] == act["attempt"] and act["targets"] == ["Mara"]
    wants = out["active_state"]["wants"]
    assert [w["serves"] for w in wants] == ["i3", "drive"]
    assert out["active_state"]["enacted_want"] == 0 and out["active_state"]["suppressed_want"] == 1
    assert out["decision_continuity"] == {"chosen": "get the key back", "suppressed": "grab her wrist",
                                          "why": "she lied to me", "uncertainty": "whether Tomas knows"}
    assert out["note"] == "keeping the key from Tomas"
    # Tells: at most two, whatever the reply wrote.
    assert [t["cue"] for t in out["manifest"]["tells"]] == ["a tight jaw", "a quick breath"]
    assert out["manifest"]["tells"][1]["channel"] == "heard"
    # The belief the beat overturned is revised to the character's own words.
    (belief,) = out["belief_updates"]
    assert (belief["operation"], belief["target_belief"], belief["belief"]) == (
        "revise", "Mara is honest with me.", "Mara is not honest with me.")
    assert belief["evidence"][0]["event_id"] == "current:Wren:0"
    (reading,) = out["mind_model_updates"]
    assert (reading["about_entity"], reading["kind"], reading["claim"]) == (
        "Mara", "goal", "Mara is covering for someone.")
    # A re-reading rests on something other than the memory it re-reads.
    (dispute,) = out["memory_disputes"]
    assert dispute["memory_ref"] == "event:kind"
    assert [e["event_id"] for e in dispute["evidence"]] == ["current:Wren:0"]
    ops = {(op["op"], op.get("id")) for op in out["intent_ops"]}
    assert ("abandon", "i3") in ops and ("block", "i3") in ops
    assert out["waiting_ops"] == [{"op": "abandon", "from": "Tomas", "what": "the rope",
                                   "why": "I stop waiting on Tomas's rope."}]
    (assoc,) = out["association_updates"]
    assert assoc["cue"] == "a hand in a pocket" and assoc["operation"] == "reinforce"
    rel = {r["target_entity"]: r for r in out["relationship_updates"]}
    # A real break moves standing by the break step; an ordinary beat by the
    # full card's +-0.05.
    assert rel["Mara"]["trust_delta"] == -jev.REL_BREAK_STEP
    assert rel["Tomas"]["warmth_delta"] == round(0.5 * jev.REL_STEP, 3)
    assert out["active_state"]["active_concerns"] == []
    assert [r["quote"] for r in out["remember_lines"]] == ['Tomas says, "Let it go."']
    assert out["memory_effects"] == [{"memory_ref": "event:key", "use": "", "disposition": "integrated",
                                      "changed": "she lied to me"}]
    assert out["follow_op"]["target"] == "Mara"
    assert out["contact_ops"] == [{"op": "remove", "contact_ref": "contact:0"}]
    assert out["active_state"]["hedonic"]["released"] is True
    assert out["active_state"]["stress"]["coping_mode"] == "go quiet and watch"
    appraisal = out["appraisal"]
    assert appraisal["novelty"] == 1.0 and appraisal["norm_compatibility"] == -0.5
    assert appraisal["somatic_impact"]["evidence"][0]["event_id"] == "current:Wren:1"
    (impact,) = appraisal["goal_impacts"]
    assert (impact["serves"], impact["impact"], impact["certainty"], impact["agency"]) == (
        "i3", -1.0, 0.9, "other")
    assert appraisal["memory_modulation"]["evidence"][0]["event_id"] == "event:key"
    assert out["salience"] == 1.0


def test_the_compiled_beat_is_a_valid_character_output_and_its_citations_ground():
    h, reply = _holding(), _reply()
    out, _ = character_bare.compile_bare(reply, _answer(SCRIPT)(jev.after_questions(h, reply)), h)
    result, _warnings = validate_llm_output("character", deepcopy(out))
    assert result["note"] == "keeping the key from Tomas"
    assert result["belief_updates"] and result["memory_disputes"] and result["mind_model_updates"]
    observations = [{"observation_id": e["ref"], "observed": {"text": e["text"]}} for e in h.events]
    memory_context = {"recent_episodes": [{"memory_ref": m["ref"], "gist": m["text"]} for m in h.memories]}
    warnings = _ground_observation_citations(result, observations, memory_context)
    assert not [w for w in warnings if "dropped" in w], warnings
    assert result["belief_updates"] and result["memory_disputes"]


def test_a_line_no_row_supports_is_dropped_where_the_models_was():
    """Commit drops a belief, a reading or a re-reading that cites nothing
    this mind was given; asked of the decision model, "none" means the same.
    A notebook note resting on nothing is never filed as what the mind
    thinks of someone -- it is kept as a reminder, in its own words, so the
    thought is not lost (mind/notebook.py)."""
    h, reply = _holding(), _reply()
    script = [("change:0:kind", "belief"), ("nb:0:kind", "goal"), ("change:1:kind", "rereading"),
              ("change:1:memory", "m0")]
    out, _ = character_bare.compile_bare(reply, _answer(script)(jev.after_questions(h, reply)), h)
    assert out["belief_updates"] == [] and out["mind_model_updates"] == []
    assert out["memory_disputes"] == []
    assert out["notebook_ops"] == [{"op": "add", "about": "Mara", "note": "Mara is covering for someone."}]


# --- the step ------------------------------------------------------------------------

def _bare_reply():
    return {"want": "hear the visitor out", "held_back": "send them away",
            "hinge": "they may know something", "unsure": "whether it is true",
            "sequence": [{"say": "Tell me what happened.", "to": "the visitor", "how": "evenly",
                          "why": "I need to know"}],
            "demeanor": "calm", "tells": [], "notebook": [], "changes": [],
            "note": "hearing the visitor out"}


def test_the_bare_contract_runs_the_step_and_its_note_reaches_the_next_call(story, monkeypatch):
    import agents.character as character
    char_id, context, commit = story
    asked, calls = [], []

    def jev_answers(state, questions):
        asked.append(sorted(questions)[:3])
        return _answer([])(questions)

    def model(role, step_key, system, payload, **kwargs):
        calls.append((step_key, system))
        return deepcopy(_bare_reply())

    monkeypatch.setattr(decisions, "OVERRIDE", jev_answers)
    monkeypatch.setattr(character, "_agent_json", model)
    result = character.character_step(context(), char_id, 1)
    assert [c[0] for c in calls] == ["character_bare"]
    assert len(calls[0][1]) < 5000, "the bare card, not the full one"
    assert result["sequence"][0]["text"] == "Tell me what happened."
    assert result["decision_continuity"]["why"] == "they may know something"
    state, _ = commit(result, index=2)
    assert state["my_notes"] == [{"turn": 2, "note": "hearing the visitor out"}]
    captured = {}

    def model_again(role, step_key, system, payload, **kwargs):
        captured.update(deepcopy(payload))
        return deepcopy(_bare_reply())

    monkeypatch.setattr(character, "_agent_json", model_again)
    character.character_step(context(state, 3), char_id, 1)
    assert captured["self"]["my_notes"] == [{"turn": 2, "note": "hearing the visitor out"}]


def test_a_kept_note_is_committed_and_shown_in_the_next_calls_notebook(story, monkeypatch):
    """The reminder a character keeps survives commit and comes back to it --
    in the notebook, the one place the next payload carries what it keeps."""
    import agents.character as character
    char_id, context, commit = story
    reply = {**_bare_reply(), "notebook": [{"about": "the visitor", "note": "ask where they came from"}]}
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: _answer([])(questions))
    monkeypatch.setattr(character, "_agent_json", lambda *a, **k: deepcopy(reply))
    result = character.character_step(context(), char_id, 1)
    assert result["notebook_ops"] == [{"op": "add", "about": "the visitor", "note": "ask where they came from"}]
    state, _ = commit(result, index=2)
    assert [(r["id"], r["note"]) for r in state["notebook"]] == [("r1", "ask where they came from")]
    captured = {}

    def model_again(role, step_key, system, payload, **kwargs):
        captured.update(deepcopy(payload))
        return deepcopy(_bare_reply())

    monkeypatch.setattr(character, "_agent_json", model_again)
    character.character_step(context(state, 3), char_id, 1)
    assert captured["self"]["notebook"]["to_keep"] == [
        {"id": "r1", "about": "the visitor", "note": "ask where they came from"}]
    assert "mind_models" not in captured and "active_hypotheses" not in captured


def test_an_unread_reply_stands_on_code_alone_and_buys_no_second_call(story, monkeypatch):
    """No fallback to the call the bare card replaced: when the decision
    model cannot be asked, the beat the character wrote stands, a line goes
    to whoever its `to` names at a voice pitched for them, and nothing is
    filed."""
    import agents.character as character
    char_id, context, _commit = story

    def jev_answers(state, questions):
        if any(k.startswith(("say:", "salience")) for k in questions):
            raise decisions.DecisionError("down")
        return _answer([])(questions)

    calls = []

    def model(role, step_key, system, payload, **kwargs):
        calls.append(step_key)
        return deepcopy(_bare_reply())

    monkeypatch.setattr(decisions, "OVERRIDE", jev_answers)
    monkeypatch.setattr(character, "_agent_json", model)
    ctx = context()
    result = character.character_step(ctx, char_id, 1)
    assert calls == ["character_bare"]
    assert result["sequence"][0]["text"] == "Tell me what happened."
    assert result["belief_updates"] == [] and result["mind_model_updates"] == []
    assert any("was not read back" in w for w in ctx.warnings)


def test_unread_the_addressee_is_the_one_the_line_names_here():
    h, reply = _holding(), _reply()
    out, _ = character_bare.compile_bare(reply, {}, h)
    speech = out["sequence"][0]
    assert (speech["targets"], speech["volume"], speech["conceal_from"]) == (["Mara"], "pitched", [])
    assert out["interaction"]["addresses"] == ["Mara"]
    reply["sequence"][0]["to"] = "the room"
    out, _ = character_bare.compile_bare(reply, {}, h)
    assert (out["sequence"][0]["targets"], out["sequence"][0]["volume"]) == ([], "normal")


# --- the notebook: what the character keeps, and what it wrote in it -----------------
#
# The owner, 2026-09-27: "A hypothesis is basicaly a note that can be updated
# or refuted"; "I needs stable core where a characters keeps track of what it
# thinks about things and other people and how it thinks they think"; "there
# should be a general note taking system for things the llm wishes to keep
# track of"; "There should also be an active concerns section that has a
# method of resolution" (mind/notebook.py).

from mind import notebook  # noqa: E402

_WORRY = "the key is missing"


def _notebook_view():
    return {
        "on_your_mind": [{"id": notebook.concern_id(_WORRY), "note": _WORRY}],
        "what_you_are_about": [{"id": "p1", "note": "keep the family together", "until": "the winter is over"}],
        "people_and_things": [
            {"id": "n1", "about": "Mara", "note": "Mara keeps secrets", "sure": "likely", "kind": "trait"},
            {"id": "n2", "about": "Tomas", "note": "Tomas wants the key for himself", "sure": "guess",
             "kind": "goal"}],
        "to_keep": [{"id": "r1", "note": "check under the loose board"}],
    }


def _notebook_reply():
    reply = _reply()
    reply["notebook"] = [
        {"id": "n1", "note": "Mara keeps secrets for someone she fears"},
        {"id": "r1", "strike": "checked it"},
        {"id": notebook.concern_id(_WORRY), "strike": "Mara has it"},
        {"id": "p1", "strike": "the winter is over"},
        {"note": "whether Tomas tells Father", "until": "Father comes home"},
        {"note": "get the key back before dark", "until": "the key is in my hand"},
        {"note": "learn the knot Mara ties"},
        {"about": "the brass key", "note": "is the only copy", "sure": "certain"},
    ]
    return reply


NOTEBOOK_SCRIPT = [
    ("nb:0:now", "e0"), ("nb:3:strike", "done"),
    ("nb:4:kind", "worry"), ("nb:5:kind", "commitment"), ("nb:6:kind", "commitment"),
    ("nb:7:kind", "what_it_is"), ("nb:7:now", "e0"),
    # The notes in play, checked before the call: n1 (which the reply
    # rewrites itself) and n2.
    ("held:0:touched", "bore_out"), ("held:0:now", "e0"),
    ("held:1:touched", "contradicted"), ("held:1:now", "e1"),
]


def _both_batteries(h, reply):
    """What the engine reads back: the questions asked before the call (the
    dispute check and the note check, `jev.ask_before`) and those asked
    after it (`agents.character` merges the answer sets)."""
    return {**jev.before_questions(h), **jev.moment_questions(h), **jev.after_questions(h, reply)}


def _read_back(h, reply, script):
    """Answers as the engine gets them: both batteries, then the belief pair
    check the first answers call for (`jev.ask_after`)."""
    answers = _answer(script)(_both_batteries(h, reply))
    answers.update(_answer(script)(jev.belief_pair_questions(h, reply, answers)))
    return answers


def test_what_the_character_writes_in_its_notebook_lands_where_it_belongs():
    h = _holding(notebook=_notebook_view(), concerns=[_WORRY])
    reply = _notebook_reply()
    out, warnings = character_bare.compile_bare(reply, _answer(NOTEBOOK_SCRIPT)(_both_batteries(h, reply)), h)
    assert warnings == []
    notes = {(u.get("op"), u.get("id")): u for u in out["mind_model_updates"]}
    # A held note, changed in the character's words: the same note, revised --
    # and not also nudged by the check made before the call.
    revised = notes[("revise", "n1")]
    assert (revised["claim"], revised["kind"], revised["about_entity"]) == (
        "Mara keeps secrets for someone she fears", "trait", "Mara")
    assert ("nudge", "n1") not in notes
    # A new note about a thing, filed under the thing, at the character's own sureness.
    (thing,) = [u for u in out["mind_model_updates"] if not u.get("op")]
    assert (thing["about_entity"], thing["kind"], thing["confidence"]) == ("the brass key", "what_it_is", 0.9)
    # A held note this beat told against is moved down -- never struck.
    nudged = notes[("nudge", "n2")]
    assert nudged["confidence"] == notebook.NUDGE_TOWARD["contradicted"] and nudged["evidence"]
    assert ("strike", "n2") not in notes
    # A reminder struck; a concern struck, and a new one carrying what settles it.
    assert out["notebook_ops"] == [{"op": "strike", "id": "r1"}]
    assert out["active_state"]["active_concerns"] == [
        "whether Tomas tells Father (settled when: Father comes home)"]
    # A project finished; a commitment with an end is taken up as a project,
    # and one with no end to name is an intention.
    assert out["project_ops"] == [
        {"op": "satisfy", "id": "p1", "why": "the winter is over"},
        {"op": "adopt", "project": "get the key back before dark",
         "satisfied_when": "the key is in my hand", "about": ""}]
    assert any(op["op"] == "add" and op["intent"] == "learn the knot Mara ties" for op in out["intent_ops"])


def test_a_struck_note_needs_no_evidence_and_survives_grounding():
    h = _holding(notebook=_notebook_view())
    reply = {**_reply(), "notebook": [{"id": "n2", "strike": "I was wrong about him"}]}
    out, _ = character_bare.compile_bare(reply, _answer(SCRIPT)(jev.after_questions(h, reply)), h)
    result, _ = validate_llm_output("character", deepcopy(out))
    observations = [{"observation_id": e["ref"], "observed": {"text": e["text"]}} for e in h.events]
    _ground_observation_citations(result, observations, {})
    assert [(u["op"], u["id"]) for u in result["mind_model_updates"] if u.get("op")] == [("strike", "n2")]


def test_lines_in_the_field_the_notebook_replaced_are_still_new_notes():
    h = _holding()
    reply = {k: v for k, v in _reply().items() if k != "notebook"}
    reply["people"] = ["Mara is covering for someone."]
    questions = jev.after_questions(h, reply)
    assert "nb:0:kind" in questions and "nb:0:about" in questions
    script = [("nb:0:kind", "goal"), ("nb:0:about", "p0"), ("nb:0:now", "e0")]
    out, _ = character_bare.compile_bare(reply, _answer(script)(questions), h)
    (reading,) = [u for u in out["mind_model_updates"] if not u.get("op")]
    assert (reading["about_entity"], reading["claim"]) == ("Mara", "Mara is covering for someone.")


def test_no_concern_is_lost_for_being_past_the_ones_checked():
    """The holding kept four concerns and the compiled state kept only
    those: a mind with seven lost three on every bare beat."""
    worries = [f"worry number {i}" for i in range(jev.MAX_CONCERNS + 3)]
    h = _holding(concerns=worries)
    questions = jev.after_questions(h, _reply())
    assert f"concern:{jev.MAX_CONCERNS - 1}" in questions and f"concern:{jev.MAX_CONCERNS}" not in questions
    out, _ = character_bare.compile_bare(_reply(), _answer([("concern:0", "yes")])(questions), h)
    assert out["active_state"]["active_concerns"] == worries[1:]


def test_the_payload_carries_one_notebook_not_four_copies():
    payload = {"self": {"projects": [{"id": "p1"}], "active_state": {"active_concerns": ["x"], "mood": "calm"}},
               "mind_models": {"Mara": {}}, "active_hypotheses": [{}], "perception": {}}
    sent = character_bare.with_notebook(payload, _notebook_view())
    assert "mind_models" not in sent and "active_hypotheses" not in sent
    assert "projects" not in sent["self"] and "active_concerns" not in sent["self"]["active_state"]
    shown = sent["self"]["notebook"]["people_and_things"]
    assert shown[0] == {"id": "n1", "about": "Mara", "note": "Mara keeps secrets", "sure": "likely"}
    assert payload["mind_models"], "the payload assembled for the stage is not mutated"


# --- what the old card said, restored (2026-09-27) ----------------------------------

def test_an_act_turns_the_body_and_can_cut_someone_off():
    """The full card's `look` and `interrupts`, which no bare reply carries,
    read back from the act: toward someone here or all around, and whose
    words it cuts off -- among those who spoke."""
    h = _holding()
    questions = jev.after_questions(h, _reply())
    assert set(questions["do:2:look"]["criteria"]) == {"p0", "p1", "around", "no_target"}
    assert set(questions["do:2:interrupts"]["criteria"]) == {"p0", "no_target"}, "only Tomas spoke"
    assert "finishing" in questions["do:2:interrupts"]["instructions"]
    script = [("do:1:look", "around"), ("do:2:look", "p0"), ("do:2:interrupts", "p0")]
    out, _ = character_bare.compile_bare(_reply(), _answer(script)(questions), h)
    acts = [e for e in out["sequence"] if e["type"] == "action"]
    assert [(a["look"], a["interrupts"]) for a in acts] == [("around", ""), ("Mara", "Tomas")]
    result, _ = validate_llm_output("character", deepcopy(out))
    kept = [e for e in result["sequence"] if e["type"] == "action"]
    assert [(a["look"], a["interrupts"]) for a in kept] == [("around", ""), ("Mara", "Tomas")]


def test_a_remembered_moment_comes_back_in_the_body_with_its_sign():
    """`memory_modulation.somatic_echo` is signed -- a tightening or a
    warmth -- and was written as 0.0 on every bare beat."""
    h = _holding()
    questions = jev.after_questions(h, _reply())
    assert set(questions["echo:1:body"]["criteria"]) == set(jev.BODY_ECHO)
    for answer, expected in (("bad", -0.5), ("hard_good", 1.0), ("none", 0.0)):
        script = [("echo", "m1"), ("echo:1:body", answer)]
        out, _ = character_bare.compile_bare(_reply(), _answer(script)(questions), h)
        assert out["appraisal"]["memory_modulation"]["somatic_echo"] == expected, answer


def test_composure_failing_shows_in_every_tell():
    """The full card asked for a tell no subtler than 0.4 under
    `self.crisis`; the read-back holds it now."""
    script = [("tell:0:miss", "hidden"), ("tell:1:miss", "plain")]
    tells = {}
    for crisis in (False, True):
        h = _holding(crisis=crisis)
        out, _ = character_bare.compile_bare(_reply(), _answer(script)(jev.after_questions(h, _reply())), h)
        tells[crisis] = [t["subtlety"] for t in out["manifest"]["tells"]]
    assert tells == {False: [jev.MISS["hidden"], jev.MISS["plain"]],
                     True: [jev.MISS["noticeable"], jev.MISS["plain"]]}
    shaken = character_bare.holding_from("Wren", {}, {"self": {"crisis": True}}, [], {}, {})
    assert shaken.crisis and not character_bare.holding_from("Wren", {}, {"self": {}}, [], {}, {}).crisis


def test_the_payload_gives_the_mood_once():
    """`self.feelings` is the mood the bare card is given; the coordinates,
    labels and ledgers behind it leave `self.active_state`."""
    payload = {"self": {"feelings": {"surface": "uneasy"}, "active_state": {
        "wants": [{"want": "the key"}], "enacted_want": 0, "affect": {"surface": {}}, "mood": "calm",
        "valence": 0.1, "arousal": 0.2, "mood_coords": {}, "mood_habits": {}, "hedonic": {"charge": 0.4},
        "stress": {"level": 0.3}, "memory_echo": {}, "affect_seconds": 4, "affect_turn": 3, "mood_clock": 1}},
        "perception": {}}
    sent = character_bare.with_notebook(payload, {})
    assert sent["self"]["active_state"] == {"wants": [{"want": "the key"}], "enacted_want": 0}
    assert sent["self"]["feelings"] == {"surface": "uneasy"}
    assert payload["self"]["active_state"]["mood"] == "calm", "the stage's payload is not mutated"


_TWO_PROJECTS = {"what_you_are_about": [
    {"id": "p1", "note": "keep the family together", "until": "the winter is over"},
    {"id": "p2", "note": "learn who took the key", "until": "someone confesses"}]}


def test_a_commitment_adoption_would_refuse_is_kept_as_an_intention():
    """Round 8 (2026-09-27): a commitment refused a project slot was lost.
    What adoption refuses -- a criterion that restates the doing, or both
    slots held -- is kept as an intention, what would finish it in its own
    words; one a held project already says is not taken up twice."""
    h = _holding(notebook=_TWO_PROJECTS)
    reply = {**_reply(), "notebook": [
        {"note": "count the hits", "until": "I have counted the hits"},
        {"note": "find a new place to hide things", "until": "the thaw comes"},
        {"note": "keep the family together", "until": "spring"}]}
    script = [(f"nb:{j}:kind", "commitment") for j in range(3)]
    out, warnings = character_bare.compile_bare(reply, _answer(script)(_both_batteries(h, reply)), h)
    assert out["project_ops"] == []
    assert [op["intent"] for op in out["intent_ops"] if op["op"] == "add"] == [
        "count the hits (until: I have counted the hits)",
        "find a new place to hide things (until: the thaw comes)"]
    assert any("already held" in w for w in warnings)


def test_a_slot_freed_in_the_same_beat_takes_the_new_project():
    """Closures land before adoptions, so a project struck in the reply frees
    its slot for one taken up beside it -- and adoption agrees."""
    from mind import affect
    h = _holding(notebook=_TWO_PROJECTS)
    reply = {**_reply(), "notebook": [
        {"id": "p1", "strike": "the winter is over"},
        {"note": "find a new place to hide things", "until": "the thaw comes"}]}
    script = [("nb:0:strike", "done"), ("nb:1:kind", "commitment")]
    out, _ = character_bare.compile_bare(reply, _answer(script)(_both_batteries(h, reply)), h)
    assert out["project_ops"] == [
        {"op": "satisfy", "id": "p1", "why": "the winter is over"},
        {"op": "adopt", "project": "find a new place to hide things", "satisfied_when": "the thaw comes",
         "about": ""}]
    held = [{"id": "p1", "project": "keep the family together", "satisfied_when": "the winter is over"},
            {"id": "p2", "project": "learn who took the key", "satisfied_when": "someone confesses"}]
    projects, _, project_warnings = affect.apply_project_ops(held, [], out["project_ops"], 10)
    assert project_warnings == [] and [p["project"] for p in projects] == [
        "learn who took the key", "find a new place to hide things"]


def test_a_worry_written_twice_is_one_concern():
    """A worry written in `changes` and again in the notebook arrived twice
    in the round-8 chains."""
    h = _holding(concerns=[])
    reply = {**_reply(), "changes": ["Whether  Tomas tells father"],
             "notebook": [{"note": "whether Tomas tells Father"}]}
    script = [("change:0:kind", "worry"), ("nb:0:kind", "worry")]
    out, _ = character_bare.compile_bare(reply, _answer(script)(_both_batteries(h, reply)), h)
    assert out["active_state"]["active_concerns"] == ["whether Tomas tells Father"]


def test_a_held_note_is_checked_against_the_moment_alone():
    """Asked after the call, 27 of the 29 nudges in the round-8 chains were
    "bore it out"; asked before it against the whole state, still 21 of 21.
    Against the moment alone -- who is here and what just reached the mind --
    beats that told the mind nothing new were called "bore it out" 9 times of
    34 instead of 28 (56 hand-labelled checks, 2026-09-27)."""
    h = _holding(notebook=_notebook_view(), beliefs=["Mara is honest with me."],
                 reasoning="I think she lied.")
    checks = jev.moment_questions(h)
    assert {k for k in checks if k.startswith("held:")} == {
        "held:0:touched", "held:0:now", "held:1:touched", "held:1:now"}
    # Held beliefs and learned cues are checked against the moment too.
    assert {"belief:0:touched", "belief:0:now", "cue:0", "cue:0:now", "cue:0:held"} <= set(checks)
    for family in ("held:", "belief:", "cue:"):
        assert not any(k.startswith(family) for k in jev.before_questions(h)), family
        assert not any(k.startswith(family) for k in jev.after_questions(h, _reply())), family
    moment = jev.moment_text(h)
    assert "Mara pockets the brass key." in moment and "Mara, Tomas" in moment
    for kept_out in ("Mara keeps secrets", "lent me her coat", "Mara is honest", "recover the key",
                     "I think she lied", "HOW YOU ARE"):
        assert kept_out not in moment, kept_out
    assert jev.moment_questions(_holding(notebook=_notebook_view(), events=[])) == {}


def test_both_checks_before_the_call_are_asked_and_merged(monkeypatch):
    """The engine and the replay tool ask through `ask_before`: the dispute
    check against the whole state, the note check against the moment."""
    h = _holding(notebook=_notebook_view())
    asked = []

    def fake_ask(state, questions):
        asked.append((state, set(questions)))
        return {k: {"type": "choice", "probabilities": {"no": 1.0}} for k in questions}

    monkeypatch.setattr(jev, "ask", fake_ask)
    answers = jev.ask_before(h)
    (dispute_state, dispute_keys), (check_state, check_keys) = asked
    assert dispute_keys == {"dispute:0", "dispute:1"} and dispute_state == jev.state_text(h)
    assert check_keys == set(jev.moment_questions(h)) and check_state == jev.moment_text(h)
    assert set(answers) == dispute_keys | check_keys


def test_striking_an_entry_the_mind_was_not_shown_files_nothing():
    h = _holding(notebook=_notebook_view())
    reply = {**_reply(), "notebook": [{"id": "n99", "strike": "I was wrong"}]}
    questions = _both_batteries(h, reply)
    assert not any(k.startswith("nb:0:") for k in questions)
    out, warnings = character_bare.compile_bare(reply, _answer([])(questions), h)
    assert out["notebook_ops"] == [] and not any(u.get("op") for u in out["mind_model_updates"])
    assert any("'n99'" in w for w in warnings)


def test_a_long_concern_is_struck_and_rewritten_by_its_own_id():
    """Round 8 (2026-09-27): the view gave a concern its id from the whole
    stored text, and the read-back held it cut at `ITEM_CHARS` -- so a
    concern past that length could never be struck or rewritten by its id.
    Each rewrite added a copy, the held one came back truncated, and the
    chains showed the same worry twice, cut at two lengths."""
    long = "Kit has told me: " + "the burns are from the rescue, " * 12 + "and I believe him."
    assert len(long) > jev.ITEM_CHARS
    view = notebook.view({}, 10, concerns=[long])
    (shown,) = view["on_your_mind"]
    h = character_bare.holding_from("Wren", {}, {"self": {}}, [], {}, {"active_concerns": [long]},
                                    notebook_view=view)
    assert h.concerns == [long], "held whole: the id is read off the words the view read"
    reply = {**_reply(), "notebook": [{"id": shown["id"], "note": "Kit pulled Wat out of the fire",
                                       "until": "the inquiry concludes"}]}
    out, _ = character_bare.compile_bare(reply, _answer([])(_both_batteries(h, reply)), h)
    assert out["active_state"]["active_concerns"] == [
        "Kit pulled Wat out of the fire (settled when: the inquiry concludes)"]
    # Left alone, it is written back whole, never cut.
    untouched = {**_reply(), "notebook": []}
    out, _ = character_bare.compile_bare(untouched, _answer([])(_both_batteries(h, untouched)), h)
    assert out["active_state"]["active_concerns"] == [long]
    # A concern kept as a record is read by its text, in the view as in the holding.
    as_record = {"text": long, "since": 3}
    (shown_record,) = notebook.view({}, 10, concerns=[as_record])["on_your_mind"]
    assert shown_record["id"] == shown["id"] and "since" not in shown_record["note"]


def test_a_learned_association_breaks_when_its_reading_proves_untrue():
    """The full card's `extinguish`: a cue that comes and whose reading proves
    untrue weakens the association; one that proves true reinforces it; one
    that merely appears moves nothing. The bare path reinforced every cue
    that appeared, so a learned fear could only ever grow."""
    h = _holding()
    reply = {**_reply(), "notebook": []}
    questions = _both_batteries(h, reply)
    assert set(questions["cue:0:held"]["criteria"]) == {"bore_out", "belied", "neither"}
    assert "suspicion" in questions["cue:0:held"]["instructions"], "the reading is the one it learned"
    for held, operation in (("bore_out", "reinforce"), ("belied", "extinguish"), ("neither", None)):
        script = [("cue:0", "yes"), ("cue:0:now", "e0"), ("cue:0:held", held)]
        out, _ = character_bare.compile_bare(reply, _answer(script)(questions), h)
        assert [u["operation"] for u in out["association_updates"]] == ([operation] if operation else []), held
    # A cue that did not come moves nothing, whatever the reading.
    out, _ = character_bare.compile_bare(reply, _answer([("cue:0", "no"), ("cue:0:held", "belied")])(questions), h)
    assert out["association_updates"] == []


def test_a_mind_changes_its_own_belief_and_the_moment_only_nudges():
    """Beliefs by the notebook's rule: a `changes` line aimed at a held
    belief revises it in the mind's own words when it rests on something the
    mind was given -- without waiting for the decision model to call the
    belief overturned. The check of the moment moves only the beliefs the
    reply left alone."""
    h = _holding(beliefs=["Mara is honest with me.", "Tomas keeps his word."])
    reply = {**_reply(), "notebook": [], "changes": ["Mara is not honest with me."]}
    script = [("change:0:kind", "belief"), ("change:0:belief", "b0"), ("change:0:now", "e0"),
              ("change:0:replaces", "changes"),
              # The moment says nothing about Mara's honesty, and overturns Tomas's word.
              ("belief:0:touched", "neither"), ("belief:1:touched", "overturns"), ("belief:1:now", "e1")]
    out, warnings = character_bare.compile_bare(reply, _read_back(h, reply, script), h)
    assert warnings == []
    by_target = {(u["operation"], u["target_belief"] or u["belief"]): u for u in out["belief_updates"]}
    revised = by_target[("revise", "Mara is honest with me.")]
    assert revised["belief"] == "Mara is not honest with me."
    weakened = by_target[("weaken", "Tomas keeps his word.")]
    assert weakened["confidence"] == 1.0, "overturned by what happened: the full weakening step"
    assert len(out["belief_updates"]) == 2
    # A line aimed at a held belief that rests on nothing given is not filed.
    bare = [("change:0:kind", "belief"), ("change:0:belief", "b0"), ("change:0:replaces", "changes")]
    out, warnings = character_bare.compile_bare(reply, _read_back(h, reply, bare), h)
    assert out["belief_updates"] == [] and any("rests on nothing" in w for w in warnings)


def test_a_line_about_something_else_never_overwrites_a_belief():
    """The pair check: which held belief a line aims at is the decision
    model's guess, and a revision REPLACES the belief. Round 11 (2026-09-27),
    with no check: "He can save more by staying numb than by feeling" became
    "Luca left the room and I let him go without a word". A pair read as a
    different thought is a belief of its own; so is one never checked."""
    h = _holding(beliefs=["Mara is honest with me."])
    reply = {**_reply(), "notebook": [], "changes": ["Tomas left the room without a word."]}
    base = [("change:0:kind", "belief"), ("change:0:belief", "b0"), ("change:0:now", "e0")]
    pairs = jev.belief_pair_questions(h, reply, _answer(base)(_both_batteries(h, reply)))
    assert set(pairs) == {"change:0:replaces"}
    assert "Mara is honest with me." in pairs["change:0:replaces"]["instructions"]
    for extra in ([("change:0:replaces", "separate")], []):
        answers = _answer(base + extra)(_both_batteries(h, reply))
        if extra:
            answers.update(_answer(base + extra)(pairs))
        out, _ = character_bare.compile_bare(reply, answers, h)
        (update,) = out["belief_updates"]
        assert (update["operation"], update["target_belief"], update["belief"]) == (
            "reinforce", "", "Tomas left the room without a word."), extra



def test_the_pair_check_is_a_second_request_after_the_read_back(monkeypatch):
    """`jev.ask_after`: the read-back, then only the pairs its answers call
    for -- the engine and the replay tool both ask through it."""
    h = _holding(beliefs=["Mara is honest with me."])
    reply = {**_reply(), "notebook": [], "changes": ["Tomas left the room without a word."]}
    asked = []

    def choose(key):
        if key.endswith(":kind"):
            return "belief"
        if key.endswith(":belief"):
            return "b0"
        return "separate"

    def fake_ask(state, questions):
        asked.append(set(questions))
        return {k: {"type": "choice", "probabilities": {choose(k): 1.0}} for k in questions}

    monkeypatch.setattr(jev, "ask", fake_ask)
    answers = jev.ask_after(h, reply)
    assert len(asked) == 2 and asked[1] == {"change:0:replaces"} and "change:0:replaces" in answers


def test_an_act_splits_at_its_own_punctuation_and_never_inside_a_number():
    assert jev.act_parts("circles the junction -- the gap he knows the enemy watches") == [
        "circles the junction", "the gap he knows the enemy watches"]
    assert jev.act_parts("pockets the letter, meaning to burn it tonight; turns away") == [
        "pockets the letter", "meaning to burn it tonight", "turns away"]
    assert jev.act_parts("counts out 1,000 marks at 10:00 — slowly") == [
        "counts out 1,000 marks at 10:00", "slowly"]
    assert jev.act_parts("lifts the latch") == ["lifts the latch"]
    many = jev.act_parts(", ".join(f"step {i}" for i in range(9)))
    assert len(many) == jev.MAX_ACT_PARTS and many[-1] == "step 5, step 6, step 7, step 8"


def test_observers_get_only_what_a_watcher_could_tell():
    """The observable floor: a bare `do` is what observers get, and a plan
    or private knowledge written into it reached them as something seen.
    Only the parts someone watching could tell are given; the Director
    still reads the whole attempt; unread, only the act's first part."""
    h = _holding()
    act = "pockets the letter, meaning to burn it tonight, and turns to Mara"
    reply = {**_reply(), "notebook": [], "sequence": [{"do": act, "why": "no one may read it"}]}
    questions = _both_batteries(h, reply)
    assert {k for k in questions if k.startswith("do:0:part:")} == {"do:0:part:0", "do:0:part:1", "do:0:part:2"}
    assert "watching" in questions["do:0:part:1"]["instructions"]
    script = [("do:0:seen", "outward"), ("do:0:part:0", "outward"), ("do:0:part:1", "inner"),
              ("do:0:part:2", "outward")]
    out, _ = character_bare.compile_bare(reply, _answer(script)(questions), h)
    (element,) = out["sequence"]
    assert element["attempt"] == act
    assert element["observable"] == "pockets the letter, and turns to Mara"
    # Every part only in the mind: nothing is given.
    inner = [("do:0:seen", "outward")] + [(f"do:0:part:{q}", "inner") for q in range(3)]
    out, _ = character_bare.compile_bare(reply, _answer(inner)(questions), h)
    assert out["sequence"][0]["observable"] == ""
    # Unread: the act's first part, not the whole text.
    out, _ = character_bare.compile_bare(reply, {}, h)
    assert out["sequence"][0]["observable"] == "pockets the letter"
    # One part: asked as a whole, given whole.
    single = {**reply, "sequence": [{"do": "lifts the latch", "why": "to go in"}]}
    assert not any(k.startswith("do:0:part:") for k in _both_batteries(h, single))
    out, _ = character_bare.compile_bare(single, _answer([("do:0:seen", "outward")])(_both_batteries(h, single)), h)
    assert out["sequence"][0]["observable"] == "lifts the latch"
