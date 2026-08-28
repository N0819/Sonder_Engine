"""A background person addressed by DESCRIPTION gets a voice.

Measured, chat 95 (a generated market town, 239 charter bodies, 44 of them
standing in the player's room): across turns 3031-3041 the player took a
vendor by the sleeve and asked him a direct question, twice, and no line ever
came back. Two independent kills, both pinned here:

  K1 -- the address could not be AIMED. The player said "the man with the
  braided cords on your table" because in a crowd of strangers nobody has
  told them a name, and no store in the engine records who sells cords (a
  charter body carries name/competence/place/post/rank; a presence row
  name/room/co-presence), so the description was unresolvable by any reader
  in principle. flow.addressed_to came back empty or as id-shaped garbage
  ([0]), refs_seen=[], and the demand gate's addressed class never fired.
  The fix is a BINDING, not retrieval: descriptor_bindings resolves the
  ref to one co-present body deterministically and commit persists the
  phrase into that body's sketch, so the fact exists from that beat on.

  K4 -- even a picked vendor was handed a beat that denied the address.
  `_react_one` derived `addressed_by` only from a dialogue_log
  `intended_target` (measured null on all 189 reads of turn 3041) or a
  `pending_reply` only that same field could write, so on the four calls
  the vendor did get he was shown `addressed_by: null` and correctly
  declined (`reacts: false`, 31 tokens, every time) -- and selection-keyed
  discharge then erased the reply debt his decline should have left
  standing.
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import (
    _flow_addressed_refs,
    presence_display_name,
    _presence_in_addressed_refs,
    descriptor_bindings,
    pick_voice_demand,
    track_background_presences,
)
from story.character_schema import default_character_data

ROOM = "market_square"


def _rec_named(presences, name):
    """The record answering to this display name, however the ledger keyed
    it (tracking mints uid keys)."""
    for key, rec in presences.items():
        if isinstance(rec, dict) and presence_display_name(key, rec) == name:
            return rec
    raise AssertionError(f"{name} not in ledger: {sorted(presences)}")
DESCRIPTOR = "the man with the braided cords"


def _make_ctx(temp_db, presences, cast_names=(), player_input="",
              addressed_refs=(), director_resolve=None, background_react=None,
              turn_idx=7):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    for name in cast_names:
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower().replace(' ', '_')}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
    cast_rows = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    positions = {"The Stranger": ROOM}
    for name in presences:
        positions[name] = ROOM
    for name in cast_names:
        positions[name] = ROOM
    temp_db.wset(chat_id, "scene", {
        "location": "town", "time": "day",
        "rooms": {ROOM: {"name": "Market Square"}},
        "positions": positions, "entities": {}, "attire": {}, "overlays": {},
    })
    temp_db.wset(chat_id, "background_presences",
                 {name: dict(rec) for name, rec in presences.items()})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, player_input, time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=cast_rows, input=player_input,
        director_resolve=director_resolve
        or {"resolved_event": "The square hums.", "dialogue_log": []},
    )
    if addressed_refs:
        ctx["director_interpret"] = {
            "flow": {"addressed_to_refs": list(addressed_refs)}}
    if background_react is not None:
        ctx["background_react"] = background_react
    return ctx


THREE_TRADERS = {
    "Trader Tate": {"first_turn": 1, "last_turn": 4},
    "Trader Mira": {"first_turn": 1, "last_turn": 4},
    "Trader Bell": {"first_turn": 1, "last_turn": 4},
}


def test_a_description_address_binds_one_copresent_body_and_forces_the_pick(temp_db):
    """The measured kill (K1): 'the man with the braided cords' names no
    tracked name, so refs_seen was [] and the gate returned [] with zero
    model calls (turns 3033/3035/3036/3038 all died this way). Bound, the
    described addressee is exactly ONE forced pick -- never zero, and never
    the whole cohort."""
    ctx = _make_ctx(temp_db, THREE_TRADERS, addressed_refs=[DESCRIPTOR],
                    player_input="You. The man with the braided cords. "
                                 "A well, nearer than the east yard?")
    out = pick_voice_demand(ctx, ctx.director_resolve, cap=1)
    assert len(out["picks"]) == 1
    pick = out["picks"][0]
    assert pick in THREE_TRADERS
    assert out["meta"][pick]["addressed"] is True
    assert out["meta"][pick]["player_addressed"] is True


def test_the_same_description_binds_the_same_body_on_every_read(temp_db):
    """The gate reads the refs before commit and the owed-reply writer reads
    them at commit; the two reads must be the same body or the debt lands on
    a stranger. Seeded pick over the sorted cohort, never bare random."""
    ctx = _make_ctx(temp_db, THREE_TRADERS, addressed_refs=[DESCRIPTOR])
    first = _flow_addressed_refs(ctx)
    second = _flow_addressed_refs(ctx)
    assert first == second
    assert first != [DESCRIPTOR]  # actually bound, not passed through
    assert first[0] in THREE_TRADERS


def test_an_ambiguous_partial_binds_one_body_instead_of_forcing_a_chorus(temp_db):
    """Finding 14, the cohort-word inflation: significant-word matching made
    the single shared word 'Trader' name all 44 'Trader *' bodies at once,
    and every flow match is a FORCED pick -- one address widened into a
    chorus. A reference names a person only if it names ONE person, so an
    ambiguous partial resolves by binding, exactly like a description."""
    ctx = _make_ctx(temp_db, THREE_TRADERS, addressed_refs=["the trader"])
    out = pick_voice_demand(ctx, ctx.director_resolve, cap=1)
    assert len(out["picks"]) == 1


def test_a_unique_partial_canonicalizes_to_the_display_name(temp_db):
    """'Tate' singles out Trader Tate; a partial that names exactly one
    person is that person, not a description to bind elsewhere."""
    presences = {"Trader Tate": {"first_turn": 1},
                 "Fisher Bell": {"first_turn": 1}}
    ctx = _make_ctx(temp_db, presences, addressed_refs=["Tate"])
    assert _flow_addressed_refs(ctx) == ["Trader Tate"]


def test_a_cast_name_ref_is_never_bound_to_a_background_body(temp_db):
    """A registered character named as a string ref belongs to loops.py's
    cast resolution; binding it would hand a stranger the companion's
    address."""
    ctx = _make_ctx(temp_db, THREE_TRADERS, cast_names=["Lena Voss"],
                    addressed_refs=["Lena Voss", "Lena"])
    assert descriptor_bindings(ctx) == {}
    out = pick_voice_demand(ctx, ctx.director_resolve, cap=1)
    assert out["picks"] == []


def test_commit_persists_the_binding_and_a_changed_cohort_still_retrieves_it(temp_db):
    """The binding is a world-mint: commit writes the player's phrase into
    the bound body's sketch, so the NEXT use of the description resolves by
    retrieval even after the cohort shifts (a shifted cohort re-seeds the
    hash pick, which without the sketch could name a different body)."""
    ctx = _make_ctx(temp_db, THREE_TRADERS, addressed_refs=[DESCRIPTOR],
                    player_input="You. The man with the braided cords.",
                    background_react={"selected": [], "reactions": []})
    bound = _flow_addressed_refs(ctx)[0]
    track_background_presences(ctx, nonce=0)
    presences = temp_db.wget(ctx.chat.id, "background_presences", {})
    stored = {
        name: (rec.get("sketch") or {}).get("descriptors")
        for name, rec in presences.items() if isinstance(rec, dict)
    }
    assert any(descs for descs in stored.values()), stored
    # A fourth trader walks in; the seeded index over the sorted cohort
    # changes, but the persisted sketch wins.
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["positions"]["Trader Aldous"] = ROOM
    temp_db.wset(ctx.chat.id, "scene", sc)
    presences["Trader Aldous"] = {"first_turn": 6}
    temp_db.wset(ctx.chat.id, "background_presences", presences)
    ctx2 = PipelineContext(
        chat=ctx.chat,
        turn=TurnData(id=ctx.turn.id + 1, chat_id=ctx.chat.id,
                      idx=ctx.turn.idx + 1, player_input="", created=time.time()),
        cast=[], input="",
        director_resolve={"resolved_event": "", "dialogue_log": []},
    )
    ctx2["director_interpret"] = {"flow": {"addressed_to_refs": [DESCRIPTOR]}}
    assert _flow_addressed_refs(ctx2) == [bound]


def test_a_declined_call_leaves_the_reply_debt_standing(temp_db):
    """Selection-keyed discharge erased the debt on the exact beats it was
    needed: the cord-seller was SELECTED on turns 3031/3032/3041, declined
    each call in 31 tokens, and the discharge treated his silence as the
    answer. A debt is paid by a line or a visible act; a declined call
    leaves it standing until expiry."""
    debt = {"from": "Soren Vale", "quote": "A well, is there one?",
            "tone": "", "turn": 6, "expires_turn": 8}
    presences = {"Trader Tate": {"first_turn": 1, "pending_reply": dict(debt)}}
    ctx = _make_ctx(temp_db, presences, turn_idx=7,
                    background_react={"selected": ["Trader Tate"],
                                      "reactions": []})
    track_background_presences(ctx, nonce=0)
    rec = _rec_named(temp_db.wget(ctx.chat.id, "background_presences", {}),
                     "Trader Tate")
    assert rec.get("pending_reply") == debt

    presences2 = {"Trader Tate": {"first_turn": 1, "pending_reply": dict(debt)}}
    ctx2 = _make_ctx(temp_db, presences2, turn_idx=7,
                     background_react={
                         "selected": ["Trader Tate"],
                         "reactions": [{"name": "Trader Tate",
                                        "dialogue_log_entry": {
                                            "speaker": "Trader Tate",
                                            "exact_quote": "East side. Ask for the stone lip."},
                                        "action": ""}]})
    track_background_presences(ctx2, nonce=0)
    rec2 = _rec_named(temp_db.wget(ctx2.chat.id, "background_presences", {}),
                      "Trader Tate")
    assert "pending_reply" not in rec2


def test_an_unanswered_player_address_writes_the_reply_debt(temp_db):
    """The old writer needed a dialogue_log `intended_target`, which no
    prompt instructs and which measured null on every one of 189 reads
    (turn 3041) -- so a player address that went unanswered simply
    evaporated. The player's own precise address now writes the same debt a
    character's aimed line does."""
    ctx = _make_ctx(temp_db, THREE_TRADERS, addressed_refs=[DESCRIPTOR],
                    player_input="You. The man with the braided cords. "
                                 "A well - is there one?",
                    background_react={"selected": [], "reactions": []})
    bound = _flow_addressed_refs(ctx)[0]
    track_background_presences(ctx, nonce=0)
    rec = _rec_named(temp_db.wget(ctx.chat.id, "background_presences", {}),
                     bound)
    pr = rec.get("pending_reply")
    assert pr, "the unanswered address must leave a debt"
    assert pr["from"] == "The Stranger"
    assert "braided cords" in pr["quote"]


def test_the_gate_verdict_reaches_the_picked_mind_as_addressed_by(temp_db, monkeypatch):
    """K4: on the four calls the vendor did get, the payload said
    `addressed_by: null` beside a question aimed at a description nothing
    bound to HIM, and the mind correctly declined. The gate's own verdict
    (pick_voice_demand meta.player_addressed) now reaches _react_one, and
    the speaker is the player's appearance label, never a name no one told
    this presence (firewall: recognition-gated, same as _present_others)."""
    import agents.background as bg

    captured = {}

    def fake_agent_json(role, stage, prompt, payload, **kw):
        captured["payload"] = payload
        return {"reacts": True,
                "dialogue_log_entry": {"speaker": "?",
                                       "exact_quote": "Aye. Behind the row, there's a well."},
                "action": ""}

    monkeypatch.setattr(bg, "_agent_json", fake_agent_json)
    ctx = _make_ctx(temp_db, THREE_TRADERS, addressed_refs=[DESCRIPTOR],
                    player_input='You. The man with the braided cords. '
                                 'A well - is there one?')
    ctx["director_interpret"]["sequence"] = [
        {"type": "speech", "visibility": "overt", "volume": "normal",
         "text": "You. The man with the braided cords. A well - is there one?"}]
    out = bg.background_react(ctx, nonce="seed")
    assert out["fired"], out
    payload = captured["payload"]
    addressed_by = payload["beat"]["addressed_by"]
    assert addressed_by is not None
    assert addressed_by["beats_ago"] == 0
    assert "braided cords" in addressed_by["exact_quote"]
    # The presence has never been introduced to the player: the speaker must
    # be an appearance label, not "The Stranger"'s actual name handed over.
    assert addressed_by["speaker"]
    assert "stranger" not in addressed_by["speaker"].casefold()
    # Cost gate: one address, one voice.
    assert len(out["reactions"]) == 1


def test_bound_refs_do_not_fan_out_across_name_sharing_cousins(temp_db):
    """The bound ref is a full display name; precise two-way matching keeps
    it from re-matching every body sharing a cohort word (finding 14's
    'Trader' x44)."""
    assert _presence_in_addressed_refs("Trader Tate", ["Trader Tate"])
    assert not _presence_in_addressed_refs("Trader Mira", ["Trader Tate"])
    assert _presence_in_addressed_refs("Trader Tate", ["Tate"])


def test_a_marked_but_unspelled_address_recovers_from_sequence_targets(temp_db):
    """The deterministic floor under the prompt clause. Measured, chat 95
    turn 3042 (grok-4.3), with the ADDRESS BY DESCRIPTION clause already in
    the prompt: flow.addressed_to came back [0] -- no character id 0 exists
    -- while the model's own sequence carried targets=['Trader Tate'] on
    the sleeve-grip and its notes said 'Trader Tate is the only present
    named character being addressed'. The structured reading existed; only
    the channel entry was garbage, and the beat died again."""
    ctx = _make_ctx(temp_db, THREE_TRADERS)
    ctx["director_interpret"] = {
        "flow": {"addressed_to": [0], "addressed_to_refs": [0]},
        "sequence": [
            {"type": "action", "visibility": "overt",
             "targets": ["Trader Tate"],
             "observable": "tightens his grip on the cord-seller's sleeve"},
            {"type": "speech", "visibility": "overt", "volume": "normal",
             "targets": [],
             "text": "You. A well - is there one?"},
        ],
    }
    assert _flow_addressed_refs(ctx) == ["Trader Tate"]
    out = pick_voice_demand(ctx, ctx.director_resolve, cap=1)
    assert out["picks"] == ["Trader Tate"]
    assert out["meta"]["Trader Tate"]["player_addressed"] is True


def test_an_empty_addressed_to_never_invents_an_addressee(temp_db):
    """The prompt licenses an empty address for a genuinely ambiguous beat;
    the floor repairs a MARKED address only, or every action's target would
    become somebody forced to speak."""
    ctx = _make_ctx(temp_db, THREE_TRADERS)
    ctx["director_interpret"] = {
        "flow": {"addressed_to": [], "addressed_to_refs": []},
        "sequence": [
            {"type": "action", "visibility": "overt",
             "targets": ["Trader Tate"], "observable": "brushes past"},
            {"type": "speech", "visibility": "overt", "text": "Excuse me."},
        ],
    }
    assert _flow_addressed_refs(ctx) == []


def test_a_resolved_cast_address_disables_the_fallback(temp_db):
    """An int that IS a registered cast id means the address resolved; the
    player punching a vendor while shouting to their companion must not
    mark the vendor addressed."""
    ctx = _make_ctx(temp_db, THREE_TRADERS, cast_names=["Lena Voss"])
    cast_id = ctx.cast[0]["id"]
    ctx["director_interpret"] = {
        "flow": {"addressed_to": [cast_id], "addressed_to_refs": [cast_id]},
        "sequence": [
            {"type": "action", "visibility": "overt",
             "targets": ["Trader Tate"], "observable": "swings at the trader"},
            {"type": "speech", "visibility": "overt", "text": "Lena, run!"},
        ],
    }
    assert _flow_addressed_refs(ctx) == []


def test_the_fallback_needs_words_an_action_alone_aims_no_voice(temp_db):
    """An address is made of words: a silent overt act targeting a presence
    (a pickpocket brushing a trader) marked with garbage ints must not
    force that presence to answer."""
    ctx = _make_ctx(temp_db, THREE_TRADERS)
    ctx["director_interpret"] = {
        "flow": {"addressed_to": [0], "addressed_to_refs": [0]},
        "sequence": [
            {"type": "action", "visibility": "overt",
             "targets": ["Trader Tate"], "observable": "lifts the purse"},
        ],
    }
    assert _flow_addressed_refs(ctx) == []


def test_an_intended_target_addresses_one_body_not_the_cohort(temp_db):
    """`intended_target` is a structured field naming ONE addressee; the
    prose matcher's significant-word fallback read 'Trader Tate' as an
    address of every 'Trader *' body through the shared cohort word.
    Measured, chat 95 turn 3043: one sleeve-grab, intended_target 'Trader
    Tate', 44 forced picks, and the beat answered as an anonymous chorus
    instead of the one man gripped by the sleeve."""
    dr = {"resolved_event": "Soren grips the trader's sleeve.",
          "dialogue_log": [{"speaker": "The Stranger",
                            "intended_target": "Trader Tate",
                            "exact_quote": '"A well - is there one?"',
                            "volume": "normal", "visibility": "overt",
                            "conceal_from": []}]}
    ctx = _make_ctx(temp_db, THREE_TRADERS, director_resolve=dr)
    out = pick_voice_demand(ctx, dr, cap=1)
    assert out["picks"] == ["Trader Tate"]
