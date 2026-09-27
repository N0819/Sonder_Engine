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
             "tells", "people", "changes", "note")


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
    # universal language contract appended, is a tenth of that.
    assert len(card) < 3500
    lines = card.split("\n")
    output = next(i for i, line in enumerate(lines) if '"want"' in line and '"sequence"' in line)
    identity = next(i for i, line in enumerate(lines) if "{name}" in line)
    assert identity == output - 1, "who you are sits just before the reply's shape"
    for key in BARE_KEYS:
        assert f'"{key}"' in lines[output], key


def test_a_section_ships_only_when_the_moment_calls_for_it():
    quiet = character_bare.modules_for({"self": {}, "perception": {}})
    assert quiet == []
    loud = character_bare.modules_for(
        {"self": {"project_review": {"id": "p1"}, "still_waiting_for": [{"what": "rope"}]},
         "perception": {"impossible_knowledge": [{"line_ref": "o1"}]}, "carried_reports": [{}]},
        disputed=[{"ref": "event:a", "text": "x"}], rupture_open=True, rupture_forced=True)
    assert loud == ["dispute", "drive_rupture", "drive_rupture_forced", "project_review",
                    "still_waiting", "impossible_knowledge", "carried_reports"]
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
        "people": ["Mara is covering for someone."],
        "changes": ["Mara is not honest with me.", "Her kindness in the rain was a way in.",
                    "I stop trying to recover the key.", "I stop waiting on Tomas's rope."],
        "note": "keeping the key from Tomas",
    }


def test_every_question_reads_only_this_minds_own_holding():
    """The firewall by construction: every person, row and item a question
    names is one this mind perceived, was given or already holds."""
    from llm.prompts import character_jev_options
    h = _holding()
    questions = jev.after_questions(h, _reply())
    offered = set()
    for q in questions.values():
        offered.update(q["criteria"].values())
    pack = set()
    for name in ("volume", "yesno", "act_kind", "grade", "miss", "channel", "signed", "fit", "tone", "change_kind",
                 "reading_kind", "aim_moved", "belief_touched", "memory_shaped", "impact", "certain",
                 "agency", "ability", "choices"):
        pack.update(character_jev_options(name, "en").values())
    held = ({e["text"] for e in h.events} | {m["text"] for m in h.memories} | set(h.people) | set(h.known)
            | set(h.beliefs) | set(h.strategies) | {jev._aim_label(a, "en") for a in h.aims}
            | {a["text"] for a in h.aims}
            | {f"{p['what']} ({p['from']})" for p in h.promises}
            | {f"You start following {p}." for p in h.people})
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
    ("say:0:volume", "mutter"), ("say:0:to", "p0"), ("say:0:kept:1", "yes"), ("say:0:kept:0", "yes"),
    ("say:0:expects", "yes"),
    ("do:1:seen", "inner"), ("do:2:seen", "outward"), ("do:2:target", "p0"),
    ("want:serves", "a1"), ("want:urgency", "strong"), ("held_back:serves", "a0"),
    ("tell:0:channel", "seen"), ("tell:0:miss", "subtle"), ("tell:1:channel", "heard"),
    ("person:0:about", "p0"), ("person:0:kind", "goal"), ("person:0:sure", "clear"),
    ("person:0:now", "e0"),
    ("change:0:kind", "belief"), ("change:0:belief", "b0"), ("change:0:now", "e0"),
    ("belief:0:touched", "overturns"), ("belief:0:now", "e0"),
    ("change:1:kind", "rereading"), ("change:1:memory", "m0"), ("change:1:now", "e0"),
    ("change:1:remembered", "m0"),
    ("change:2:kind", "give_up"), ("change:2:aim", "a0"),
    ("change:3:kind", "stop_waiting"), ("change:3:promise", "w0"),
    ("aim:0:moved", "blocked"), ("aim:0:now", "e0"),
    ("cue:0", "yes"), ("cue:0:now", "e0"),
    ("rel:0:trust", "much_less"), ("rel:0:break", "yes"), ("rel:0:now", "e0"),
    ("rel:1:warmth", "more"),
    ("concern:0", "yes"), ("keep:0", "yes"), ("mem:1:shaped", "integrated"),
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
    answers = _answer(SCRIPT)(jev.after_questions(h, reply))
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
    this mind was given; asked of the decision model, "none" means the same."""
    h, reply = _holding(), _reply()
    script = [("change:0:kind", "belief"), ("person:0:about", "p0"), ("change:1:kind", "rereading"),
              ("change:1:memory", "m0")]
    out, _ = character_bare.compile_bare(reply, _answer(script)(jev.after_questions(h, reply)), h)
    assert out["belief_updates"] == [] and out["mind_model_updates"] == []
    assert out["memory_disputes"] == []


# --- the step ------------------------------------------------------------------------

def _bare_reply():
    return {"want": "hear the visitor out", "held_back": "send them away",
            "hinge": "they may know something", "unsure": "whether it is true",
            "sequence": [{"say": "Tell me what happened.", "to": "the visitor", "how": "evenly",
                          "why": "I need to know"}],
            "demeanor": "calm", "tells": [], "people": [], "changes": [],
            "note": "hearing the visitor out"}


def test_the_bare_contract_runs_the_step_and_its_note_reaches_the_next_call(story, monkeypatch):
    import agents.character as character
    char_id, context, commit = story
    monkeypatch.setattr(character_bare, "enabled", lambda: True)
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


def test_an_unread_reply_stands_on_code_alone_and_buys_no_second_call(story, monkeypatch):
    """No fallback to the call the bare card replaced: when the decision
    model cannot be asked, the beat the character wrote stands, a line goes
    to whoever its `to` names at a voice pitched for them, and nothing is
    filed."""
    import agents.character as character
    char_id, context, _commit = story
    monkeypatch.setattr(character_bare, "enabled", lambda: True)

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
