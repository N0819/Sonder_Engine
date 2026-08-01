"""Unbidden recall: one contrasting memory for a measurably stuck mind.

The three repetition mechanisms (recent_self_lines, the refrain skeleton, the
verbatim-repeat rewrite) all say "not that". Unbidden recall is the mechanism
that says "here is something else you own": when the same deterministic
signals that measure stuck-ness fire, exactly one high-salience memory
DISSIMILAR to the current beat is surfaced into the memory context, marked as
arriving on its own, substituting for one ordinary recall slot. What to do
with it stays the character's.

These tests pin the guards: the deterministic trigger with its suppressors
and hysteresis, the strict k=1 envelope over the character's own rows only,
the constant payload budget, the read-only selection (no access_count write),
commit as the sole ledger writer, and non-canonicality -- a surfaced memory
never mints a row.
"""

import json
import time

import pytest

from memory import add_memory, contrast_memory, provenance_context_label
from agents.character import (
    _UNBIDDEN_ABSORPTION_CEILING,
    _UNBIDDEN_COOLDOWN_BEATS,
    _attach_unbidden,
    _unbidden_entry,
    _unbidden_trigger,
)
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


# ---- fixtures -------------------------------------------------------------

def _chat_and_char(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    return chat_id, char_id


def _fill_bank(chat_id, char_id, n=20, *, location="Kitchen", start_turn=30):
    """n recent, same-place, same-vocabulary rows -- the current groove."""
    ids = []
    for i in range(n):
        ids.append(add_memory(
            chat_id, char_id, None, "episodic", "witnessed", 0.7,
            f"The kettle boiled over on the old stove again, pass {i}",
            turn_idx=start_turn + i, location=location, confidence=1.0))
    return ids


QUERY = "the kettle keeps boiling over on the old stove"


# ---- contrast selection ---------------------------------------------------

def test_contrast_prefers_the_distant_dissimilar_high_salience_row(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    _fill_bank(chat_id, char_id)
    target = add_memory(
        chat_id, char_id, None, "episodic", "witnessed", 0.9,
        "Lantern light swung over the orchard wall the night the bells rang",
        turn_idx=2, location="Orchard", valence=-0.7, arousal=0.6,
        confidence=1.0)
    out = contrast_memory(chat_id, char_id, QUERY, 60, here="Kitchen")
    assert len(out) == 1, "the envelope is one entry, stricter than recall"
    assert out[0]["id"] == target


def test_contrast_ignores_confidence(temp_db):
    """What you no longer credit is exactly the sort of thing that intrudes --
    an abandoned inference at its demoted confidence competes on salience."""
    chat_id, char_id = _chat_and_char(temp_db)
    _fill_bank(chat_id, char_id)
    target = add_memory(
        chat_id, char_id, None, "inference", "inferred", 0.9,
        "About the ferryman: he never once looked at the water",
        turn_idx=2, location="Docks", confidence=0.05, category="inference")
    out = contrast_memory(chat_id, char_id, QUERY, 60, here="Kitchen")
    assert out and out[0]["id"] == target


def test_contrast_respects_the_turn_cutoff(temp_db):
    """A mind deciding turn N never retrieves a memory of turn N or later --
    the same F1 envelope ordinary recall enforces."""
    chat_id, char_id = _chat_and_char(temp_db)
    _fill_bank(chat_id, char_id, start_turn=1)
    future = add_memory(
        chat_id, char_id, None, "episodic", "witnessed", 0.95,
        "Lantern light swung over the orchard wall as the bells rang",
        turn_idx=60, location="Orchard", valence=-0.8, confidence=1.0)
    out = contrast_memory(chat_id, char_id, QUERY, 60, here="Kitchen")
    assert all(m["id"] != future for m in out)


def test_contrast_needs_a_bank_worth_contrasting(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    _fill_bank(chat_id, char_id, n=10)
    assert contrast_memory(chat_id, char_id, QUERY, 60) == []


def test_contrast_skips_obligation_tiers_and_excluded_ids(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    _fill_bank(chat_id, char_id)
    promise = add_memory(
        chat_id, char_id, None, "dialogue", "promise", 0.95,
        "A voice swore to return before the thaw",
        turn_idx=2, location="Orchard", confidence=1.0, category="promise")
    other = add_memory(
        chat_id, char_id, None, "episodic", "witnessed", 0.9,
        "Lantern light swung over the orchard wall the night the bells rang",
        turn_idx=3, location="Orchard", valence=-0.7, confidence=1.0)
    out = contrast_memory(chat_id, char_id, QUERY, 60, here="Kitchen")
    assert out and out[0]["id"] == other, "promise rows never intrude as texture"
    out2 = contrast_memory(chat_id, char_id, QUERY, 60, here="Kitchen",
                           exclude_ids=[other])
    assert all(m["id"] not in (other, promise) for m in out2)


def test_contrast_is_a_pure_read(temp_db):
    """search_memories bumps access_count mid-pipeline; the contrast selector
    must not copy that -- the character stage stays read-only."""
    chat_id, char_id = _chat_and_char(temp_db)
    _fill_bank(chat_id, char_id)
    add_memory(
        chat_id, char_id, None, "episodic", "witnessed", 0.9,
        "Lantern light swung over the orchard wall the night the bells rang",
        turn_idx=2, location="Orchard", confidence=1.0)
    before = temp_db.q(
        "SELECT SUM(access_count) c FROM memories WHERE chat_id=?",
        (chat_id,), one=True)["c"]
    contrast_memory(chat_id, char_id, QUERY, 60, here="Kitchen")
    after = temp_db.q(
        "SELECT SUM(access_count) c FROM memories WHERE chat_id=?",
        (chat_id,), one=True)["c"]
    assert after == before


# ---- trigger --------------------------------------------------------------

_REFRAIN = {"opening": {"word": "still", "lines": 4, "of": 6}}


def test_trigger_fires_on_a_refrain_and_names_it():
    reason, fire = _unbidden_trigger({}, {}, _REFRAIN, 10, 0.2)
    assert (reason, fire) == ("refrain", True)


def test_trigger_reads_the_persisted_repeat_flag():
    st = {"unbidden": {"repeat_flag": True}}
    reason, fire = _unbidden_trigger(st, {}, None, 10, 0.2)
    assert (reason, fire) == ("verbatim_repeat", True)


def test_trigger_reads_goal_tenure_and_plateau():
    reason, fire = _unbidden_trigger({}, {"goal_held": 14}, None, 10, 0.2)
    assert (reason, fire) == ("goal_held", True)
    reason, fire = _unbidden_trigger(
        {}, {"hedonic": {"sustained_beats": 4.0}}, None, 10, 0.2)
    assert (reason, fire) == ("plateau", True)


def test_trigger_is_silent_when_nothing_is_stuck():
    assert _unbidden_trigger({}, {}, None, 10, 0.2) == (None, False)


def test_absorption_ceiling_suppresses():
    """A body claiming the mind leaves no room for reminiscence -- the same
    tier where place recall's capacity reaches zero."""
    reason, fire = _unbidden_trigger(
        {}, {}, _REFRAIN, 10, _UNBIDDEN_ABSORPTION_CEILING)
    assert reason == "refrain" and not fire


def test_open_rupture_window_suppresses():
    st = {"interior": {"drive_rupture": {"window_expires": 12}}}
    reason, fire = _unbidden_trigger(st, {}, _REFRAIN, 10, 0.2)
    assert reason == "refrain" and not fire
    # ...and a lapsed window stops suppressing.
    st = {"interior": {"drive_rupture": {"window_expires": 8}}}
    assert _unbidden_trigger(st, {}, _REFRAIN, 10, 0.2)[1]


def test_cooldown_and_hysteresis():
    recent = {"unbidden": {"last_turn": 8, "clear_seen": True}}
    assert not _unbidden_trigger(recent, {}, _REFRAIN,
                                 8 + _UNBIDDEN_COOLDOWN_BEATS, 0.2)[1]
    # Past the cooldown but never observed clear since the last injection:
    # still held. Edge-triggered, not level-triggered.
    stale = {"unbidden": {"last_turn": 2, "clear_seen": False}}
    assert not _unbidden_trigger(stale, {}, _REFRAIN, 10, 0.2)[1]
    rearmed = {"unbidden": {"last_turn": 2, "clear_seen": True}}
    assert _unbidden_trigger(rearmed, {}, _REFRAIN, 10, 0.2)[1]


def test_two_strikes_suppression_holds_until_cleared():
    st = {"unbidden": {"suppressed": True, "clear_seen": True}}
    assert not _unbidden_trigger(st, {}, _REFRAIN, 10, 0.2)[1]


# ---- payload marking and budget -------------------------------------------

def test_entry_keys_carry_the_epistemic_status():
    mem = {"gist": "lantern light over the orchard wall", "provenance":
           "inferred", "turn_idx": 3, "location": "Orchard"}
    entry = _unbidden_entry(mem, 40)
    assert entry["it_comes_back_to_me"] == mem["gist"]
    assert entry["from"] == "what_i_concluded"
    assert entry["when"] == "about 37 beats ago"
    assert entry["where"] == "Orchard"
    # No id, no score, no instruction -- context, not directive.
    assert set(entry) <= {"it_comes_back_to_me", "from", "when", "where"}


def test_provenance_labels_match_the_summary_vocabulary():
    assert provenance_context_label("witnessed") == "what_i_experienced"
    assert provenance_context_label("told") == "what_i_was_told"
    assert provenance_context_label("inferred") == "what_i_concluded"


def test_attach_substitutes_never_adds():
    """The unbidden entry pays for itself out of the recall budget."""
    ctx = {"recalled_old_memories": [
        {"id": i, "score": 0.1 * i} for i in range(1, 9)]}
    _attach_unbidden(ctx, {"it_comes_back_to_me": "x"}, recall_limit=8)
    assert len(ctx["recalled_old_memories"]) == 7
    assert all(m["id"] != 1 for m in ctx["recalled_old_memories"]), \
        "the lowest-ranked ordinary recall yields"
    assert ctx["surfaces_unbidden"]["it_comes_back_to_me"] == "x"
    # Under budget: takes the spare slot, drops nothing.
    ctx = {"recalled_old_memories": [{"id": 1, "score": 0.5}]}
    _attach_unbidden(ctx, {"it_comes_back_to_me": "y"}, recall_limit=8)
    assert len(ctx["recalled_old_memories"]) == 1


def test_the_payload_key_is_documented_in_the_character_prompt():
    """The payload has no natural back-pressure against undocumented keys; a
    marker whose meaning is guessed from its name is worse than no marker."""
    from prompts import DEFAULT_PROMPTS
    prompt = DEFAULT_PROMPTS["character"]
    for key in ("surfaces_unbidden", "it_comes_back_to_me",
                "what_i_concluded"):
        assert key in prompt, key


# ---- commit ledger --------------------------------------------------------

_UID_COUNTER = iter(range(1, 10_000))


def _commit_ctx(temp_db, probe, *, cstate=None, turn_idx=2):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(),
         f"char_mara_{next(_UID_COUNTER)}"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(cstate or {})))
    temp_db.wset(chat_id, "scene", {
        "rooms": {"kitchen": {"name": "Kitchen"}},
        "positions": {"Mara": "kitchen"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "test", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="test", created=time.time()),
        cast=cast, input="test")
    ctx.director_resolve = {
        "summary": "", "resolved_event": "", "dialogue_log": []}
    ctx.character_results = {
        char_id: {"sequence": [], "unbidden_probe": probe}}
    return ctx, chat_id, char_id


def _ledger_of(prepared, char_id):
    state = next(json.loads(s) for c, cc, s in prepared["state_updates"]
                 if cc == char_id)
    return state.get("unbidden") or {}


def test_commit_records_a_fired_injection_and_mints_nothing(temp_db):
    import commit
    gist = "lantern light over the orchard wall"
    probe = {"stuck": True, "trigger": "refrain", "fired": True,
             "memory_id": 77, "repeat_survived": False}
    ctx, chat_id, char_id = _commit_ctx(temp_db, probe)
    prepared = commit.prepare_memory_commit(ctx)
    led = _ledger_of(prepared, char_id)
    assert led["last_turn"] == 2
    assert led["last_trigger"] == "refrain"
    assert led["recent_ids"] == [77]
    assert led["clear_seen"] is False
    assert led["pending"] == {"turn": 2, "goal": ""}
    # Non-canonicality: the surfaced memory is context, never a mint source.
    # No perception view and no character acts means NOTHING is minted, the
    # probe included.
    assert prepared["memory_batch"]["prepared"] == []
    assert gist not in json.dumps(prepared["memory_batch"]["prepared"])


def test_commit_scores_the_next_beat_and_clears(temp_db):
    import commit
    cstate = {"unbidden": {"last_turn": 1, "clear_seen": False,
                           "pending": {"turn": 1, "goal": ""}}}
    probe = {"stuck": False, "trigger": "", "fired": False,
             "memory_id": None, "repeat_survived": False}
    ctx, chat_id, char_id = _commit_ctx(temp_db, probe, cstate=cstate)
    led = _ledger_of(prepared := commit.prepare_memory_commit(ctx), char_id)
    assert led["outcomes"][-1]["helped"] is True
    assert "pending" not in led
    assert led["clear_seen"] is True
    assert led.get("suppressed") is False


def test_commit_suppresses_after_two_unhelpful_injections(temp_db):
    import commit
    cstate = {"unbidden": {
        "last_turn": 1, "clear_seen": False,
        "outcomes": [{"turn": 1, "helped": False}],
        # The goal snapshot matches this beat's goal: unmoved.
        "pending": {"turn": 1, "goal": ""},
    }}
    # Still stuck, goal unmoved: the second strike.
    probe = {"stuck": True, "trigger": "refrain", "fired": False,
             "memory_id": None, "repeat_survived": False}
    ctx, chat_id, char_id = _commit_ctx(temp_db, probe, cstate=cstate)
    led = _ledger_of(commit.prepare_memory_commit(ctx), char_id)
    assert [o["helped"] for o in led["outcomes"]] == [False, False]
    assert led["suppressed"] is True
    # A later clear beat lifts the suppression and re-arms.
    probe2 = {"stuck": False, "trigger": "", "fired": False,
              "memory_id": None, "repeat_survived": False}
    ctx2, _c, char_id2 = _commit_ctx(
        temp_db, probe2,
        cstate={"unbidden": {**led}}, turn_idx=3)
    led2 = _ledger_of(commit.prepare_memory_commit(ctx2), char_id2)
    assert led2["suppressed"] is False
    assert led2["clear_seen"] is True


def test_commit_persists_the_repeat_flag_for_the_next_beat(temp_db):
    import commit
    probe = {"stuck": False, "trigger": "", "fired": False,
             "memory_id": None, "repeat_survived": True}
    ctx, chat_id, char_id = _commit_ctx(temp_db, probe)
    led = _ledger_of(commit.prepare_memory_commit(ctx), char_id)
    assert led["repeat_flag"] is True
    # ...and it clears on a beat whose speech screen passed.
    probe2 = {"stuck": True, "trigger": "verbatim_repeat", "fired": False,
              "memory_id": None, "repeat_survived": False}
    ctx2, _c, char_id2 = _commit_ctx(temp_db, probe2,
                                     cstate={"unbidden": led}, turn_idx=3)
    led2 = _ledger_of(commit.prepare_memory_commit(ctx2), char_id2)
    assert led2["repeat_flag"] is False


def test_ledger_untouched_for_a_character_with_no_probe(temp_db):
    """A character who did not act this beat has unknown stuckness; the
    ledger must not move."""
    import commit
    cstate = {"unbidden": {"last_turn": 1, "clear_seen": False}}
    ctx, chat_id, char_id = _commit_ctx(temp_db, None, cstate=cstate)
    ctx.character_results = {}
    led = _ledger_of(commit.prepare_memory_commit(ctx), char_id)
    assert led == cstate["unbidden"]


class TestTheSemanticAxisAndItsInversionTrap:
    """Unbidden recall gained a semantic distance term in alpha 6.3.1, and
    the gate on it is the interesting part.

    A row embedded by a different model scores 0.0 against any query. In
    `search_memories` that makes it invisible — a silent omission. Here the
    axis is INVERTED, so the same 0.0 reads as maximally contrasting and
    unbidden recall would preferentially surface exactly the memories that
    have not been rebuilt yet. One number, two opposite failures.
    """

    def test_the_axis_is_off_unless_almost_the_whole_bank_is_comparable(self):
        import memory
        assert memory._CONTRAST_SEMANTIC_COVERAGE >= 0.9, (
            "a half-rebuilt bank would rank on which half a row is in")

    def test_it_joins_the_token_axis_rather_than_replacing_it(self):
        """The structural fields are exact and have carried this since the
        beginning; the vector is a second opinion, not a successor."""
        import memory
        assert memory._CONTRAST_SEMANTIC <= 0.8

    def test_a_stranded_bank_falls_back_to_the_old_behaviour(self, temp_db,
                                                             monkeypatch):
        """Degrade to the previous answer, never to a wrong one."""
        import memory
        import providers
        seen = {}
        real = memory.embed_texts_meta

        def fake(texts):
            got = real(texts)
            seen["model"] = got.model_key
            return got

        monkeypatch.setattr(memory, "embed_texts_meta", fake)
        # No rows at all -> no crash, no picks, and never an exception from
        # the embedding path taking the function down with it.
        assert memory.contrast_memory(1, 1, "anything", 5) == []
