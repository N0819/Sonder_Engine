"""The character's notebook: what it thinks of people and things, what it
thinks they think, and what it must not forget.

The owner, 2026-09-27: "A hypothesis is basicaly a note that can be updated
or refuted an important piece of a characters mind model of other
characters"; "hypothesis should be about anything in general I suppose but
also about characters"; "I needs stable core where a characters keeps track
of what it thinks about things and other people and how it thinks they
think"; "there should be a general note taking system for things the llm
wishes to keep track of"; and on the context: "making sure the llm still has
acces to what it needs without letting it baloon".

Pinned here: a note keeps a stable id through restatement; strike, revise
and nudge take it by that id (a strike removes it, a revision keeps its
history, a nudge moves confidence and never the words); the kinds for things
have their own ceilings and are not re-read as person language.
"""

from __future__ import annotations

from mind import theory_of_mind as tom


def _form(st, about, claim, kind="goal", confidence=0.5, turn=1):
    return tom.apply_mind_model_updates(
        st, [{"about_entity": about, "kind": kind, "claim": claim, "confidence": confidence}], turn)


def _notes(st, about):
    return st["mind_models"][about]["hypotheses"]


def test_a_note_keeps_its_id_through_a_restatement():
    st = _form({}, "Rell", "means to put my name on the score")
    nid = _notes(st, "Rell")[0]["id"]
    assert nid.startswith("n")
    st = _form(st, "Rell", "means to put my name on the score, whatever I say", confidence=0.6, turn=2)
    assert [h["id"] for h in _notes(st, "Rell")] == [nid]


def test_a_strike_removes_the_note_it_names_and_nothing_else():
    st = _form({}, "Rell", "means to put my name on the score")
    st = _form(st, "Isolde", "is angry with him, not with me", kind="emotion", turn=1)
    nid = _notes(st, "Rell")[0]["id"]
    st = tom.apply_mind_model_updates(st, [{"op": "strike", "id": nid}], 2)
    assert "Rell" not in st["mind_models"] or not _notes(st, "Rell")
    assert _notes(st, "Isolde")


def test_a_revision_keeps_the_notes_id_and_history_in_new_words():
    st = _form({}, "Rell", "means to put my name on the score", turn=3)
    held = _notes(st, "Rell")[0]
    st = tom.apply_mind_model_updates(st, [{
        "op": "revise", "id": held["id"], "about_entity": "Rell", "kind": "goal",
        "claim": "wants the theme itself, not my name", "confidence": 0.6}], 5)
    [note] = _notes(st, "Rell")
    assert note["id"] == held["id"] and note["first_seen_turn"] == 3
    assert note["claim"] == "wants the theme itself, not my name" and note["revised_turn"] == 5


def test_a_nudge_moves_confidence_and_never_the_words():
    st = _form({}, "Rell", "means to put my name on the score", confidence=0.5)
    held = dict(_notes(st, "Rell")[0])
    st = tom.apply_mind_model_updates(st, [{"op": "nudge", "id": held["id"], "confidence": 0.1}], 1)
    [note] = _notes(st, "Rell")
    assert note["claim"] == held["claim"] and note["confidence"] < held["confidence"]
    st = tom.apply_mind_model_updates(st, [{"op": "nudge", "id": held["id"], "confidence": 0.95}], 1)
    [note] = _notes(st, "Rell")
    # up, but never past the kind's ceiling (a goal's is 0.65)
    assert held["confidence"] - 0.2 < note["confidence"] <= 0.65


def test_a_revision_of_a_note_no_longer_held_is_filed_as_new():
    st = tom.apply_mind_model_updates({}, [{
        "op": "revise", "id": "nffffff", "about_entity": "Rell", "kind": "goal",
        "claim": "wants the theme itself", "confidence": 0.6}], 4)
    [note] = _notes(st, "Rell")
    assert note["claim"] == "wants the theme itself" and note["id"] != "nffffff"


def test_a_note_formed_before_ids_is_named_by_what_it_says_and_keeps_that_name():
    st = {"mind_models": {"Rell": {"hypotheses": [
        {"about_entity": "Rell", "kind": "goal", "claim": "means to put my name on the score",
         "confidence": 0.5, "last_updated_turn": 1, "first_seen_turn": 1}]}}}
    derived = tom.note_id("Rell", _notes(st, "Rell")[0])
    st = _form(st, "Rell", "means to put my name on the score, badly", confidence=0.6, turn=2)
    assert [h["id"] for h in _notes(st, "Rell")] == [derived]
    assert tom.find_note(st["mind_models"], derived) == ("Rell", 0)


def test_the_kinds_for_things_have_their_own_ceilings_and_keep_their_kind():
    [forecast] = tom.cap_mind_model_updates([{"about_entity": "the audition", "kind": "what_will_happen",
                                              "claim": "goes to the other soprano", "confidence": 0.95}])
    assert forecast["kind"] == "what_will_happen" and forecast["confidence"] == 0.6
    # "is a ..." is person language for a trait; about a thing it is what the thing is
    [thing] = tom.cap_mind_model_updates([{"about_entity": "the letter", "kind": "what_it_is",
                                           "claim": "is a forgery", "confidence": 0.9}])
    assert thing["kind"] == "what_it_is" and thing["confidence"] == 0.8


# --- the view: bounded, and chosen for the moment ------------------------------------

from mind import notebook as nb  # noqa: E402


def _held(*rows, turn=1):
    """A mind-model store from (about, claim, confidence) rows."""
    st = {}
    for about, claim, conf in rows:
        st = tom.apply_mind_model_updates(
            st, [{"about_entity": about, "kind": "trait", "claim": claim, "confidence": conf}], turn)
    return st


def test_the_view_puts_who_and_what_is_in_play_first():
    st = _held(("Rell", "keeps his own counsel", 0.45), ("Harik", "counts the patrols", 0.45),
               ("the letter", "carries the route", 0.45), ("Isolde", "is loyal to the house", 0.2))
    shown = nb.view(st, 20, present=["Isolde"], texts=["Varga folds the letter away"])["people_and_things"]
    # both in play lead, whatever their confidence -- Isolde's note is the weakest held
    assert {e["about"] for e in shown[:2]} == {"Isolde", "the letter"}
    assert all(e["id"].startswith("n") and e["sure"] in ("certain", "likely", "guess", "doubtful") for e in shown)


def test_one_subject_cannot_crowd_out_the_rest():
    habits = ("keeps his own counsel", "drinks alone at night", "counts every coin twice",
              "limps on the left leg", "writes letters he never sends", "hums when anxious")
    st = _held(*[("Rell", habit, 0.45) for habit in habits], ("Isolde", "is loyal to the house", 0.3))
    shown = nb.view(st, 1, present=["Rell"])["people_and_things"]
    assert sum(1 for e in shown if e["about"] == "Rell") == nb.PER_SUBJECT_SHOWN
    assert any(e["about"] == "Isolde" for e in shown)


def test_the_body_having_the_mind_narrows_the_view():
    st = _held(*[(f"Person {i}", "keeps his own counsel", 0.45) for i in range(30)])
    assert len(nb.view(st, 1)["people_and_things"]) == nb.NOTES_SHOWN
    assert len(nb.view(st, 1, absorption=1.0)["people_and_things"]) == nb.NOTES_SHOWN_ABSORBED


def test_a_recall_naming_someone_brings_their_notes_back():
    st = _held(*[(f"Person {i}", "keeps his own counsel", 0.45) for i in range(30)],
               ("Harik", "counts the patrols", 0.1))
    assert "Harik" not in {e["about"] for e in nb.view(st, 1)["people_and_things"]}
    recalled = nb.view(st, 1, texts=["what exactly did Harik ask about the route?"])
    assert recalled["people_and_things"][0]["about"] == "Harik"


def test_reminders_are_added_changed_struck_and_never_reuse_an_id():
    st = nb.apply_notebook_ops({}, [{"op": "add", "about": "the iodine", "note": "nearly out"},
                                    {"op": "add", "note": "ask Isolde over wine"},
                                    {"op": "add", "note": "check the halyard splice"}], 5)
    st = nb.apply_notebook_ops(st, [{"op": "change", "id": "r2", "note": "ask Isolde about the jaw"},
                                    {"op": "strike", "id": "r1"}], 6)
    assert [(r["id"], r["note"]) for r in st["notebook"]] == [("r2", "ask Isolde about the jaw"),
                                                              ("r3", "check the halyard splice")]
    st = nb.apply_notebook_ops(st, [{"op": "add", "note": "find Harik"}], 7)
    assert st["notebook"][-1]["id"] == "r4"


def test_past_the_cap_the_oldest_untouched_reminder_goes(monkeypatch):
    monkeypatch.setattr(nb, "REMINDERS_KEPT", 2)
    st = nb.apply_notebook_ops({}, [{"op": "add", "note": "one"}], 1)
    st = nb.apply_notebook_ops(st, [{"op": "add", "note": "two"}], 2)
    st = nb.apply_notebook_ops(st, [{"op": "change", "id": "r1", "note": "one, again"}], 3)
    st = nb.apply_notebook_ops(st, [{"op": "add", "note": "three"}], 4)
    assert [r["note"] for r in st["notebook"]] == ["one, again", "three"]


def test_a_stale_reminder_leaves_the_view_and_comes_back_when_in_play():
    st = nb.apply_notebook_ops({}, [{"op": "add", "about": "the iodine", "note": "nearly out"}], 0)
    later = 1 + nb.REMINDER_STALE_TURNS
    assert "to_keep" not in nb.view(st, later)
    assert nb.view(st, later, texts=["Anselm reaches for the iodine"])["to_keep"][0]["id"] == "r1"


def test_concerns_and_projects_come_with_their_ids_and_what_would_end_them():
    worry = "whether Kit hangs (settled when: Wat speaks)"
    shown = nb.view({}, 1, concerns=[worry],
                    projects=[{"id": "p1", "project": "clear Kit's name", "satisfied_when": "the magistrate rules",
                               "probation": True}])
    assert shown["on_your_mind"] == [{"id": nb.concern_id(worry), "note": worry}]
    assert shown["what_you_are_about"] == [{"id": "p1", "note": "clear Kit's name",
                                            "until": "the magistrate rules", "on_trial": True}]
    assert set(nb.entries(shown)) == {nb.concern_id(worry), "p1"}
