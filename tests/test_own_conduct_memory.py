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

    own = _self_rows(captured)
    assert own, ("a character who spoke this beat has no durable memory of "
                 "having spoken -- the d290ca4/3a82657 regression")
    assert own[0]["content"] == (
        "I said 'You are cold. I will have a blanket brought.'")
    assert own[0]["provenance"] == "remembered"
    # And the episode still minted beside it, untouched.
    episodes = [m for m in captured["memories"]
                if m.get("category") == "episode"]
    assert len(episodes) == 1


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

    own = _self_rows(captured)
    assert len(own) == 1
    assert own[0]["content"] == "I said 'Hold the line.' Then I tried to brace the door."


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

    by_cat = {m["category"]: m for m in captured["memories"]}
    episode, own = by_cat["episode"], by_cat["self"]
    # Decision framing, never the old fragment that read as a second event.
    assert own["content"] == "I tried to wrench the lever down."
    assert "chose to" not in own["content"]
    assert "attempted" not in own["content"]
    # Complementary, not competing: neither row restates the other.
    assert own["content"] not in episode["content"]
    assert episode["content"] not in own["content"]

    # Through the retrieval projection both land in the first-hand lane with
    # the identical beat-age label -- one beat, two aspects, and the reader
    # never has to reconstruct which came from where.
    for row in (episode, own):
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
    assert len(projected) == 2
    assert {p["epistemic_origin"] for p in projected} == {"what_i_experienced"}
    # One beat, one moment: both halves of the pair were formed at the same
    # reading of the story clock and must be stamped with it identically.
    assert {p["when"] for p in projected} == {"about 3 minutes ago"}


def test_the_bound_holds(temp_db, monkeypatch):
    """Storage is bounded by the mind's own appraisal: every spoken beat is
    durable regardless of salience, a silent act only at salience >= 0.7.
    An idle silent motion keeps its 12-turn `_recent_self_moves` window and
    the episode of its consequences, not a durable row per fidget."""
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)

    # Silent act below the floor: no self row.
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.69,
        "sequence": [{"type": "action", "attempt": "shift my weight"}],
        "active_state": {"mood": "idle"},
    }, view="Dust drifts in the light.", idx=3)
    prepare_memory_commit(ctx)
    assert not _self_rows(captured)

    # The same silent act at the floor: durable.
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.7,
        "sequence": [{"type": "action", "attempt": "shift my weight"}],
        "active_state": {"mood": "idle"},
    }, view="Dust drifts in the light.", idx=4)
    prepare_memory_commit(ctx)
    assert len(_self_rows(captured)) == 1

    # Speech at any salience: durable.
    ctx = _ctx(chat_id, char_id, cast, {
        "salience": 0.0,
        "sequence": [{"type": "speech", "text": "Mm."}],
        "active_state": {"mood": "idle"},
    }, view="Dust drifts in the light.", idx=5)
    prepare_memory_commit(ctx)
    assert len(_self_rows(captured)) == 1


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
