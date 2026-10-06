"""Regression: a character durably remembers their own speech and acts.

d290ca4 (2026-08-10) suppressed the `category: self` row whenever the beat
produced a perception view, reasoning the view was "already the coherent,
resolved first-person episode". That was true only under model-composed
perception, which wrote "You say X" into a mind's own view. 3a82657
(2026-08-11) made perception deterministic, and the composer structurally
excludes a mind's own conduct from its own view (`speaker == name` /
`actor == name` skips in `agents/perception.py` -- the firewall, working as
designed). From that day the suppression branch could never fire, and no
character anywhere formed a memory of anything they said or did.

Measured on the live database: chat 67 (Aug 8) holds 20 self rows over 51
turns; chats 69-80 (Aug 12 on) hold 0 over 240 turns. Chat 80's Dr. Moon
promised a blanket on turn 5, never brought it up again (0 promise rows in
the chat), and restated the same three propositions on five consecutive
beats -- a mind that cannot remember what it already said says it again.

Captured at the embedding-batch boundary so no provider is needed, matching
tests/test_memory_affect.py.
"""

import json
import time

from persist import commit
from mind import memory
from story.character_schema import default_character_data
from persist.commit import _durable_dialogue_category, prepare_memory_commit
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _story(temp_db, name="Sarel"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    sheet = default_character_data(name)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(), sheet["identity"]["uid"]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    return chat_id, char_id, cast


def _capture_batch(monkeypatch):
    captured = {}

    def fake_batch(memories):
        captured["memories"] = memories
        return {"prepared": [], "embedded": None}

    # prepare_memory_commit resolves prepare_memories_batch in ITS
    # module's globals -- commit_memory since the split; patching the
    # commit facade would be inert.
    from persist import commit_memory
    monkeypatch.setattr(commit_memory, "prepare_memories_batch", fake_batch)
    return captured


def _ctx(chat_id, char_id, cast, own_result, *, view=None, idx=5):
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=200 + idx, chat_id=chat_id, idx=idx,
                      player_input="...", created=time.time()),
        cast=cast, input="...",
        director_resolve={"resolved_event": "The beat resolves.",
                          "dialogue_log": []},
    )
    ctx.character_results = {char_id: own_result}
    if view is not None:
        ctx.perception_outcome = {"views": {str(char_id): view}}
    return ctx


def _self_rows(captured):
    return [m for m in captured["memories"] if m.get("category") == "self"]


def _conduct_rows(captured):
    """Rows holding what the mind said and did: since 2026-09-30 the turn's
    one memory ("What I witnessed: ... What I did: ... What happened: ..."), or a self row
    alone when the beat perceived nothing."""
    return [m for m in captured["memories"] if "What I did:" in str(m.get("content") or "")]


def test_a_speaker_remembers_having_spoken_even_with_a_view(
        temp_db, monkeypatch):
    """THE regression. A view is what a mind perceived, and deterministic
    perception withholds the mind's own conduct from it -- so receiving a
    view must not cost the character the only record of what they said."""
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.4,
        "sequence": [{"type": "speech",
                      "text": "You are cold. I will have a blanket brought."}],
        "active_state": {"mood": "steady"},
    }, view="The young woman shivers and pulls the sheet closer.")

    prepare_memory_commit(ctx)

    own = _conduct_rows(captured)
    assert own, ("a character who spoke this beat has no durable memory of "
                 "having spoken -- the d290ca4/3a82657 regression")
    # ONE memory of the turn (the owner, 2026-09-30): what it perceived and
    # what it said, in one row, never a second row beside the episode.
    assert own[0]["content"] == (
        "What I did: I said 'You are cold. I will have a blanket brought.'\n"
        "What happened: The young woman shivers and pulls the sheet closer.")
    assert own[0]["category"] == "episode" and own[0]["provenance"] == "witnessed"
    assert not _self_rows(captured) and len(captured["memories"]) == 1


def test_the_no_view_case_still_mints_the_self_row(temp_db, monkeypatch):
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.9,
        "sequence": [{"type": "speech", "text": "Hold the line."},
                     {"type": "action", "attempt": "brace the door"}],
        "active_state": {"mood": "strained"},
    })

    prepare_memory_commit(ctx)

    # Nothing perceived: what it did is its own row.
    own = _self_rows(captured)
    assert len(own) == 1
    assert own[0]["content"] == "What I did: I said 'Hold the line.' Then I tried to brace the door."


def test_the_pair_reads_as_one_beat_not_two_events(temp_db, monkeypatch):
    """A beat's self row and episode row must present as two halves of one
    happening: same beat-age label, same first-hand lane, and the self row
    decision-framed (an attempt beside the perceived outcome) rather than a
    second resolved event. The old ``I chose to attempted '...'`` wording is
    what d290ca4 measured replaying an act as a second event; its decision
    framing is the fix, and the suppression was the over-correction."""
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.9,
        "sequence": [{"type": "action", "attempt": "wrench the lever down"}],
        "active_state": {"mood": "set"},
    }, view="The gate shudders but does not move.", idx=7)

    prepare_memory_commit(ctx)

    # ONE row now (the owner, 2026-09-30), the two halves labelled: the
    # outcome perceived, and the attempt decision-framed beside it -- never
    # the old fragment that read as a second event.
    (row,) = captured["memories"]
    assert row["content"] == ("What I did: I tried to wrench the lever down.\n"
                              "What happened: The gate shudders but does not move.")
    assert "chose to" not in row["content"] and "attempted" not in row["content"]

    # Through the retrieval projection it lands in the first-hand lane with
    # the beat's age label.
    for row in (row,):
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
            "provenance,salience,content,gist,key_phrases,entities,location,"
            "emotional_context,valence,arousal,confidence,access_count,"
            "archived,event_key,embedding_model,encoded_at_seconds) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (chat_id, char_id, 7, row["kind"], row["category"],
             row["provenance"], row["salience"], row["content"],
             row.get("gist") or row["content"], "[]", "[]", "", "",
             0.0, 0.0, 1.0, 0, 0, row["event_key"], "", 120.0))
    buffered = memory.recent_memory_buffer(
        chat_id, char_id, current_turn_idx=8)
    clock = memory.MemoryClock(chat_id, char_id, 8, now_seconds=300.0,
                               viewer_frame_id=None)
    projected = [memory._with_reading(m, clock) for m in buffered]
    assert len(projected) == 1
    assert {p["epistemic_origin"] for p in projected} == {"what_i_experienced"}
    assert {p["when"] for p in projected} == {"about 3 minutes ago"}


def test_the_bound_holds(temp_db, monkeypatch):
    """Storage is bounded by CONDUCT: a mind remembers what it said and what
    it did, and a beat it did nothing in leaves no self row.

    The bound used to be the mind's own `salience` self-report reaching 0.7,
    and that number is not a bound -- it arrives in the character prompt only
    as the literal 0.5 inside the required JSON shape, with nothing saying
    what it means, and the full card's `KERNEL_FILL_QUIETLY` (deleted with
    it 2026-09-27) filled an absent one with the same 0.5 in silence. Measured, two_lives v5 (2026-09-19): across 60 beats
    of two autonomous characters, ONE self row -- the single beat anybody
    spoke -- while a millwright spent twenty of them diagnosing a rotten
    bearing and remembered only the crouch he did it in.

    The fidget that bound was written against is answered by the tier built
    for it (`schedule_memory_consolidation`): a row a consolidator can
    summarise is recoverable, and a beat never written down is not."""
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)

    # A beat with no conduct in it: no self row, whatever it rates itself.
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.9,
        "sequence": [{"type": "action", "attempt": "   "}],
        "active_state": {"mood": "idle"},
    }, view="Dust drifts in the light.", idx=3)
    prepare_memory_commit(ctx)
    assert not _conduct_rows(captured)

    # A silent act, rated low by the mind that took it: durable.
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.0,
        "sequence": [{"type": "action", "attempt": "shift my weight"}],
        "active_state": {"mood": "idle"},
    }, view="Dust drifts in the light.", idx=4)
    prepare_memory_commit(ctx)
    assert len(_conduct_rows(captured)) == 1

    # Speech at any salience: durable.
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.0,
        "sequence": [{"type": "speech", "text": "Mm."}],
        "active_state": {"mood": "idle"},
    }, view="Dust drifts in the light.", idx=5)
    prepare_memory_commit(ctx)
    assert len(_conduct_rows(captured)) == 1


class TestDurableDialogueMarkersBeginAtWords:
    """A spoken marker starts at a word boundary, never inside another word.

    Substring matching filed "compromised" as a promise: of the live
    corpus's 5 promise-category rows, 3 were the word "compromised" (chat
    6's "Section C and D compromised", twice, and chat 58's "TARGETING
    COMPROMISED") against 2 genuine promises."""

    def test_compromised_is_not_a_promise(self):
        assert _durable_dialogue_category(
            "Section C and D compromised -- compromised how?") is None
        assert _durable_dialogue_category(
            "TARGETING COMPROMISED. THROWING OBJECTS WILL NOT SAVE YOU!") is None

    def test_a_genuine_promise_still_is(self):
        assert _durable_dialogue_category(
            "I know why you did it. I promise I'll get you off this station"
        ) == "promise"

    def test_inflection_at_the_marker_end_still_matches(self):
        assert _durable_dialogue_category(
            "I promised you a lantern and you will have one") == "promise"


def test_a_free_form_self_reported_affect_cannot_kill_the_commit(
        temp_db, monkeypatch):
    """FOUND BY A TEN-BEAT LIVE RUN, and it lost every beat in it.

    `active_state.affect` is the character's own SELF-REPORT.
    `affect.resolve_affect` takes it only as `proposed=`, beside `mood`, and
    computes the authoritative value from the previous affect, this beat's
    appraisal, the baseline and elapsed time. The memory encoder falls back
    to that self-report for a character with no resolved affect yet, and read
    `.get("surface").get("valence")` straight off it.

    One model emitted `affect` in four shapes across one story --
    `{valence,arousal}`, `{surface:"tense"}`, `{}`, `{surface:{...}}` -- and
    the second raised `'str' object has no attribute 'get'` inside
    `prepare_memory_commit`, which `commit.py` re-raises as a failed commit.
    Every beat of the run died there.

    No schema layer was going to catch it: `CharacterActiveState.affect` is
    typed `dict` and never reaches inside, so `{"surface": "tense"}` is a
    perfectly valid value. A self-report has to be read as untrusted at the
    point of use.
    """
    shapes = [
        {"valence": 0.2, "arousal": 0.4},          # flat, no surface
        {"surface": "tense", "undercurrent": "flat"},   # THE crash
        {},
        {"surface": {"valence": -0.3, "arousal": 0.7}},  # the good one
        "tense",                                    # not even a dict
    ]
    for shape in shapes:
        chat_id, char_id, cast = _story(temp_db)
        captured = _capture_batch(monkeypatch)
        ctx = _ctx(chat_id, char_id, cast, {
            "salience": 0.4,
            "sequence": [{"type": "speech", "text": "Three, then."}],
            "active_state": {"mood": "steady", "affect": shape},
        })
        prepare_memory_commit(ctx)
        assert _self_rows(captured), shape

    # ...and the well-formed one is still actually READ, so the guard did not
    # buy safety by throwing the value away.
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.4,
        "sequence": [{"type": "speech", "text": "Three, then."}],
        "active_state": {
            "mood": "steady",
            "affect": {"surface": {"valence": -0.3, "arousal": 0.7}}},
    })
    prepare_memory_commit(ctx)
    row = _self_rows(captured)[0]
    assert float(row.get("valence")) == -0.3, row


class TestOneMemoryPerTurn:
    """The owner, 2026-09-30: one memory per turn, "What I witnessed / What
    I did", the mood it came in with as words for the mind to read, the mood
    it left with in the arithmetic. A heard line is not a second row of the
    moment it was heard in, unless it is a promise."""

    def _heard(self, temp_db, monkeypatch, quote, *, mood_coords=None):
        chat_id, char_id, cast = _story(temp_db)
        if mood_coords:
            temp_db.q("UPDATE chat_chars SET state=? WHERE char_id=?",
                      (json.dumps({"active_state": {"mood_coords": mood_coords}}), char_id))
            cast = temp_db.q(
                "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
        # Wren and Ostra stand where Sarel can see them: a memory is tagged
        # only with bodies its mind saw in full that beat
        # (`world.spatial.sighted_level`, 2026-10-06) -- a speaker heard and
        # never seen is not a face the mind can tie to a name it learns.
        temp_db.wset(chat_id, "scene", {"rooms": {"well": {"name": "The well"}},
                                        "positions": {"Sarel": "well", "Wren": "well",
                                                      "Ostra": "well"}})
        captured = _capture_batch(monkeypatch)
        ctx = _ctx(chat_id, char_id, cast, {
            "salience": 0.5, "sequence": [{"type": "speech", "text": "Then go."}],
            "active_state": {"mood": "steady"}},
            view=f'Wren says: "{quote}" Wren looks at you.')
        ctx.director_resolve["dialogue_log"] = [
            {"speaker": "Wren", "exact_quote": f'"{quote}"', "intended_target": "Ostra", "volume": "normal"}]
        prepare_memory_commit(ctx)
        return captured["memories"]

    def test_a_kept_line_is_already_in_the_turns_memory(self, temp_db, monkeypatch):
        rows = self._heard(temp_db, monkeypatch, "Remember this: the well is fouled.")
        assert [m["category"] for m in rows] == ["episode"]
        assert "the well is fouled" in rows[0]["content"] and "What I did: I said 'Then go.'" in rows[0]["content"]
        # the speaker and the one spoken to stay on the row, as the dialogue
        # row it replaces kept them -- seen, as they are here (the mind itself
        # never is: `_memory_about`)
        assert {"Wren", "Ostra"} <= set(rows[0]["about"])

    def test_a_promise_keeps_its_own_row(self, temp_db, monkeypatch):
        rows = self._heard(temp_db, monkeypatch, "I promise I will come back for you.")
        assert sorted(m["category"] for m in rows) == ["episode", "promise"]

    def test_the_mood_it_came_in_with_is_words_on_the_row(self, temp_db, monkeypatch):
        rows = self._heard(temp_db, monkeypatch, "Go.", mood_coords={"fear": 0.8, "tension": 0.6})
        last = rows[0]["content"].splitlines()[-1]
        assert last.startswith("How I came into it: ") and last.endswith(".")
        assert len(last) > len("How I came into it: .")

    def test_the_decision_models_option_never_spends_its_chars_on_the_label(self):
        from agents.character_bare import _delivered_memories
        got = _delivered_memories({"recent_memories": [
            {"memory_ref": "r1", "details": "What I witnessed: Wren left by the north gate.\nWhat I did: I said 'Go.'"},
            {"memory_ref": "r2", "details": "What I did: I barred the door."}]})
        assert [m["text"][:20] for m in got] == ["Wren left by the nor", "I barred the door."]


def test_the_bare_contracts_act_keeps_its_doer_and_a_line_is_quoted_once():
    """The bare card writes an act "without a subject", as a watcher sees it,
    and a line sometimes in its own quotation marks. Its memory read "I tried
    to lifts the latch" and "I said '"What file."'" (story run 2026-09-30)."""
    from persist.commit import _own_sequence_memory
    content, _gist = _own_sequence_memory([
        {"type": "speech", "text": '"What file."'},
        {"type": "action", "attempt": "does not close the casebook, stays where she is",
         "subjectless": True},
        {"type": "action", "attempt": "bar the door"}], "Ines Calder")
    assert content == ("I said 'What file.' Then Ines Calder does not close the casebook, "
                       "stays where she is. Then I tried to bar the door.")


def test_the_subjectless_mark_survives_the_sequence_normalizer():
    """`agents.common.norm_sequence` rebuilds every act from named keys; the
    mark was lost there on the first live turn, and the memory read "I tried
    to picks up the card"."""
    from agents.common import norm_sequence
    out = {"sequence": [{"type": "action", "attempt": "picks up the card", "subjectless": True},
                        {"type": "action", "attempt": "bar the door"}]}
    norm_sequence(out)
    assert [e.get("subjectless") for e in out["sequence"]] == [True, None]


def test_the_turns_memory_is_in_the_order_it_was_lived_and_says_nothing_twice(temp_db, monkeypatch):
    """The owner, 2026-09-30: witnessed, then did, then what happened as a
    result, in order and without duplicates. What the act stage showed the
    mind before it acted is the first part; the outcome's episode, with the
    act stage's percepts left out by key, the last."""
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.5,
        "sequence": [{"type": "action", "attempt": "picks up the card", "subjectless": True}],
        "active_state": {"mood": "steady"}},
        view="Klara Hess nods. The door closes behind Klara Hess.")
    ctx.perception_act = {"witnessed": {str(char_id): {
        "episode": "I saw Klara Hess nod.", "gist": "I saw Klara Hess nod.", "entities": ["Klara Hess"],
        "keys": ["act:aaa"]}}}
    ctx.perception_outcome["episodes"] = {str(char_id): "I saw the door close behind Klara Hess."}
    ctx.perception_outcome["episode_meta"] = {str(char_id): {"gist": "The door closed.", "entities": []}}
    prepare_memory_commit(ctx)
    (row,) = captured["memories"]
    assert row["content"] == ("What I witnessed: I saw Klara Hess nod.\n"
                              "What I did: Sarel picks up the card.\n"
                              "What happened: I saw the door close behind Klara Hess.")
    assert row["gist"] == "I saw Klara Hess nod."


def test_one_act_minted_by_both_stages_has_one_signature():
    """The act stage and the outcome mint one act under different event ids,
    so its `dedupe_key` differs between them (live, 2026-09-30: "I saw Klara
    Hess stop at the bottom of the step" said under both "What I witnessed"
    and "What happened"). What it says does not, and that is what the
    outcome's episode leaves out."""
    import agents.composer as composer
    before = composer.Percept(kind="act", channel="sight", source_label="Klara Hess",
                              data={"surface": "nods"}, order_key=1, dedupe_key="act:one")
    again = composer.Percept(kind="act", channel="sight", source_label="Klara Hess",
                             data={"surface": "nods"}, order_key=1, dedupe_key="act:two")
    other = composer.Percept(kind="act", channel="sight", source_label="Klara Hess",
                             data={"surface": "closes the door"}, order_key=2, dedupe_key="act:three")
    assert composer.episode_signature(before) == composer.episode_signature(again) != ""
    assert composer.episode_signature(other) != composer.episode_signature(before)
