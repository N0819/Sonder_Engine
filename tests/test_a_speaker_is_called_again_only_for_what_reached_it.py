"""While the player or the Director is owed, a speaker is called again only
for what reached it.

Two of the interaction loop's early exits wait on somebody outside it
(`loops.EXITS_THAT_WAIT_OUTSIDE_THE_LOOP`): a line turned to the player and an
act the Director must resolve. Both defer for the beat's summoned cast and
its focus. What may come AFTER those owed turns is the rule here
(`loops._reaction_owed`): the next-speaker draw, narrowed to a speaker that a
micro-round delivered something to since its own last turn -- never anybody
new, and never a speaker the draw names alone.

The rule before this one stopped the beat once the owed turns had run. It
fixed a real repeat -- Brackwater (scratch play db, chat 166 turn idx 26):
the brother asked the player, the pilot was drained in, and the brother was
called again and asked the player again before she had said a word -- and
took the reaction with it: his sister had crossed to the door, and his
"She's at the door. I can hear her coat against the wood." was the line the
rule cut. Replayed through the loop over the 3,934 stored loops of that db
(the stored minds and deliveries; the exits, deferrals, draw and budgets the
loop's own), the stop cut five loops -- three distinct beats, each a
reaction to what had just reached the speaker. This rule calls the stored
sequence on all five, and calls exactly what the loop before the stop called
on every one of the 3,934.

What keeps the answer from being the repeat is what the speaker is told on
the way in: what it left waiting on the player (`loops._note_left_open` ->
`decision.not_answered_yet`, pinned in
tests/test_a_recalled_speaker_knows_what_is_not_answered_yet.py).
"""

from __future__ import annotations

import copy
import json

import pytest

import agents.common as common
import agents.director as director
import agents.loops as loops
from story.character_schema import default_character_data

PLAYER = "Tamsin"
HIS_ASK = "Ask me plain and I'll tell you what I know."


class _Chat:
    id = 1


class _Turn:
    idx = 26
    frame_id = None


class _Ctx:
    def __init__(self, reactors, cast=None):
        self.chat = _Chat()
        self.turn = _Turn()
        self.cast = [
            {"id": cid, "sheet": json.dumps(default_character_data(f"Char{cid}")),
             "cstate": "{}", "active": 1, "stance": "{}"}
            for cid in (cast if cast is not None else reactors)
        ]
        self.director_interpret = {"flow": {
            "reactors": list(reactors), "tom_triggers": []}}
        self.perception_act = {"views": {}}
        self.reaction_results = {}
        self.reaction_loop = {}
        self.character_results = {}
        self.warnings = []
        self._extra = {}

    def get(self, key, default=None):
        return getattr(self, key, default) or default


def _says(cid, text, *, to=None, asks_player=False, closes=False):
    return {"cid": cid,
            "sequence": [{"type": "speech", "text": text,
                          "targets": [to] if to is not None else []}],
            "interaction": {"expects_response": not closes,
                            "conversation_complete_for_me": closes},
            "asks_player": asks_player}


def _words(entry):
    """What the loop holds as left open, as the note reads it: the words of
    each recorded element (`character._not_answered_yet_note`)."""
    if not entry:
        return {}
    read = lambda e: (e.get("text") or e.get("content") or e.get("attempt")
                      if isinstance(e, dict) else e)
    return {key: [read(e) for e in entry.get(key) or []]
            for key in ("said", "tried")}


def _install(monkeypatch, script, *, reaches=lambda actor, observer: True,
             hears=None, **config):
    """The loop's own control flow, the draw and both exit predicates real;
    the minds scripted; a round reaches whoever `reaches` says (or
    `hears(actor, result, observer)`, for a round whose reach depends on how
    it was said). Whom a line was put to resolves by exact name -- the
    label floor is driven for real in
    tests/test_a_recalled_speaker_knows_what_is_not_answered_yet.py.
    Returns the call log and, per call, what the loop says that mouth left
    waiting."""
    settings = {"max_micro_rounds": 4, "max_character_calls": 6,
                "initial_parallel_reactors": 1,
                "stop_on_question_to_player": True,
                "allow_npc_to_npc_dialogue": True,
                "silence_ends_exchange": True}
    settings.update(config)
    monkeypatch.setattr(loops, "dialogue_config", lambda cid: dict(settings))
    monkeypatch.setattr(loops, "get_scene", lambda *a, **kw: {})
    monkeypatch.setattr(loops, "normalize_character_refs",
                        lambda refs, cast: [int(r) for r in refs
                                            if isinstance(r, int) or str(r).isdigit()])
    monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_drop_absent", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_untargeted_order",
                        lambda ctx, ids, nonce: list(ids))
    monkeypatch.setattr(loops, "_merge_character_results",
                        lambda prev, new: new)
    # Whether a line turns to the player is the script's to say; the rest of
    # `_asks_player` has its own suites.
    monkeypatch.setattr(loops, "_asks_player",
                        lambda r, chat, cast: bool(r.get("asks_player")))
    monkeypatch.setattr(loops, "persona_of", lambda chat: {"name": PLAYER})
    monkeypatch.setattr(director, "_bodies_addressed_as",
                        lambda ctx, scene, speaker, forms: [
                            str(f) for f in forms
                            if str(f) == PLAYER or str(f).startswith("Char")])

    def micro(ctx, actor_id, actor_result, scene, **kw):
        reached = {row["id"] for row in ctx.cast
                   if row["id"] != actor_id and (
                       hears(actor_id, actor_result, row["id"]) if hears
                       else reaches(actor_id, row["id"]))}
        return {cid: [f"{actor_id} is seen and heard"] for cid in reached}, reached

    monkeypatch.setattr(loops, "deterministic_micro_perception", micro)
    calls, told = [], []

    def step(ctx, cid, nonce):
        calls.append(cid)
        told.append(json.loads(json.dumps(_words(
            (ctx._extra.get("beat_left_open") or {}).get(cid)))))
        return copy.deepcopy(script(cid, calls.count(cid)))

    monkeypatch.setattr(loops, "character_step", step)
    return calls, told


def _brackwater(cid, n):
    """Chat 166 idx 26 as the minds played it: the brother (83) puts his ask
    to the player; the pilot (81) crosses to the door, speaking to nobody;
    called again, he answers what he saw -- to the player, as he did."""
    if cid == 83 and n == 1:
        return _says(83, HIS_ASK, to=PLAYER, asks_player=True)
    if cid == 83:
        return _says(83, "She's at the door. I can hear her coat against the wood.",
                     to=PLAYER, asks_player=True)
    return {"cid": 81, "sequence": [{
        "type": "action", "attempt": "crosses the landing to the shut door "
        "and sets her ear against the planking", "commitment": "asserted"}],
        "interaction": {"expects_response": False}}


def test_the_asker_answers_what_reached_him_and_is_told_his_ask_still_waits(
        monkeypatch):
    """The measured shape, as it now runs: the pilot's crossing reaches the
    brother, so he is called again -- once -- and on the way in the loop
    holds his ask to the player as still waiting. His answer turns to the
    player, which ends the beat on her."""
    calls, told = _install(monkeypatch, _brackwater)

    out = loops.interaction_loop(_Ctx(reactors=[83, 81]), nonce=0)

    assert calls == [83, 81, 83], calls
    assert told[2] == {"said": [HIS_ASK], "tried": []}, told
    assert out["stop_reason"] == "awaiting player response"


def test_an_asker_nothing_new_reached_is_not_called_again(monkeypatch):
    """The paired control: the pilot's round reaches nobody (she is out of
    his sight and hearing), so the draw has nobody to offer and the beat
    stops on the player once the owed turns have run."""
    calls, _ = _install(monkeypatch, _brackwater,
                        reaches=lambda actor, observer: actor != 81)

    out = loops.interaction_loop(_Ctx(reactors=[83, 81]), nonce=0)

    assert calls == [83, 81]
    assert out["stop_reason"] == "awaiting player response"


def test_nobody_new_is_drawn_while_the_player_is_owed(monkeypatch):
    """A third body in the room hears everything and was never summoned.
    The draw ranks it FIRST (a body that has not spoken gets the draw's
    bonus); it is still never called, and the speaker the round reached is."""
    def script(cid, n):
        return _says(cid, f"{cid} speaks, round {n}", to=PLAYER,
                     asks_player=(cid == 1))

    calls, _ = _install(monkeypatch, script)

    out = loops.interaction_loop(_Ctx(reactors=[1, 2], cast=[1, 2, 3]), nonce=0)

    assert 3 not in calls, calls
    assert calls == [1, 2, 1]
    assert out["stop_reason"] == "awaiting player response"


def _answers_back_and_forth(cid, n):
    """1 puts a question to the player once; after that the two answer each
    other, each reaching the other."""
    if cid == 1 and n == 1:
        return _says(1, "What are you after?", to=PLAYER, asks_player=True)
    return _says(cid, f"{cid} answers the other, round {n}", to=3 - cid)


@pytest.mark.parametrize("rounds,calls_budget,expected", [
    (4, 6, [1, 2, 1, 2]),     # the round budget closes it
    (10, 3, [1, 2, 1]),       # the call budget closes it
])
def test_the_budgets_bound_the_reactions(monkeypatch, rounds, calls_budget,
                                         expected):
    """Two speakers answering each other while the player is owed is a
    conversation the budgets bound, as every deferral is -- and the beat
    still ends on the player, not on a budget message."""
    calls, _ = _install(monkeypatch, _answers_back_and_forth,
                        max_micro_rounds=rounds,
                        max_character_calls=calls_budget)

    out = loops.interaction_loop(_Ctx(reactors=[1, 2]), nonce=0)

    assert calls == expected
    assert out["stop_reason"] == "awaiting player response"


def test_the_reaction_helper_is_bounded_and_narrowed():
    """`_reaction_owed` on its own: the draw's order, less anybody new and
    anybody nothing reached, and nothing once either budget is spent."""
    drawn = [3, 2, 1]                       # 3 is new: the draw's bonus
    assert loops._reaction_owed(drawn, {1, 2, 3}, {1, 2}, 2, 6, 2, 4) == [2, 1]
    assert loops._reaction_owed(drawn, {1}, {1, 2}, 2, 6, 2, 4) == [1]
    assert loops._reaction_owed(drawn, set(), {1, 2}, 2, 6, 2, 4) == []
    assert loops._reaction_owed(drawn, {1, 2}, {1, 2}, 6, 6, 2, 4) == []
    assert loops._reaction_owed(drawn, {1, 2}, {1, 2}, 2, 6, 4, 4) == []


def test_a_pending_resolution_lets_a_speaker_answer_what_reached_it(
        monkeypatch):
    """The other outside exit, the same rule: an act the world must answer
    is deferred for the summoned cast, and its actor may answer what one of
    them did -- told the act is still waiting on the world."""
    shove = "shoves the door against the bar"

    def script(cid, n):
        if cid == 1 and n == 1:
            return {"cid": 1, "sequence": [{"type": "action", "attempt": shove,
                                            "commitment": "contestable"}],
                    "interaction": {"expects_response": False}}
        return _says(cid, f"{cid} answers the other, round {n}", to=3 - cid)

    calls, told = _install(monkeypatch, script, max_micro_rounds=3)

    out = loops.interaction_loop(_Ctx(reactors=[1, 2]), nonce=0)

    assert calls == [1, 2, 1]
    assert told[2] == {"said": [], "tried": [shove]}, told
    assert out["stop_reason"] == "physical resolution required"


def test_the_old_stops_still_end_it(monkeypatch):
    """Narrowing the draw changes nothing before it: a drained speaker who
    closes her own exchange still ends the beat, and with NPC-to-NPC
    dialogue switched off a reaction to another cast member is refused --
    both reported as what the beat waits on."""
    def closing(cid, n):
        if cid == 83:
            return _says(83, HIS_ASK, to=PLAYER, asks_player=True)
        return _says(81, "I'll wait on the walk.", to=83, closes=True)

    calls, _ = _install(monkeypatch, closing)
    out = loops.interaction_loop(_Ctx(reactors=[83, 81]), nonce=0)
    assert calls == [83, 81]
    assert out["stop_reason"] == "awaiting player response"

    calls, _ = _install(monkeypatch, _brackwater,
                        allow_npc_to_npc_dialogue=False)
    out = loops.interaction_loop(_Ctx(reactors=[83, 81]), nonce=0)
    assert calls == [83, 81]
    assert out["stop_reason"] == "awaiting player response"


def test_only_a_line_put_to_the_player_waits_on_the_player(monkeypatch):
    """What the loop keeps as waiting on the player is the lines put to
    HER: a line put to another cast member waits on nobody outside, and a
    line naming nobody carries no addressee at all -- it is nobody's to
    answer, the player's least. (Which body a line names is the resolve's
    reading, driven for real -- labels, presences, a second player -- in
    tests/test_a_recalled_speaker_knows_what_is_not_answered_yet.py.)"""
    def script(cid, n):
        if cid == 1 and n == 1:
            return {"cid": 1, "asks_player": True,
                    "interaction": {"expects_response": True},
                    "sequence": [
                        {"type": "speech", "text": "Not here.", "targets": [PLAYER]},
                        {"type": "speech", "text": "Go wait on the walk.",
                         "targets": ["Char2"]},
                        {"type": "speech", "text": "Inside, then.", "targets": []}]}
        return _says(cid, f"{cid} answers the other, round {n}", to=3 - cid)

    calls, told = _install(monkeypatch, script, max_micro_rounds=3)

    loops.interaction_loop(_Ctx(reactors=[1, 2]), nonce=0)

    assert calls == [1, 2, 1]
    assert told[2]["said"] == ["Not here."]


def _three(cid, n):
    """Three at the stair. 1 asks 2 something; 2 turns it to the player;
    3, drained in, puts a question to 1. Then 2 and 3 whisper, each only
    to the other."""
    whisper = n > 1 and cid in (2, 3)
    if cid == 1 and n == 1:
        line = _says(1, "Did you see where she went?", to="Char2")
    elif cid == 2 and n == 1:
        line = _says(2, "Ask her, not me.", to=PLAYER, asks_player=True)
    elif cid == 3 and n == 1:
        line = _says(3, "One, you were on the stair. Say what you saw.", to="Char1")
    elif cid == 2:
        line = _says(2, "Leave him be.", to="Char3")
    elif cid == 3:
        line = _says(3, "I won't.", to="Char2")
    else:
        line = _says(1, "I saw her on the stair.", to="Char3")
    line["whisper"] = whisper
    return line


def _whispers_reach_only_their_listener(actor, result, observer):
    if result.get("whisper"):
        return any(f"Char{observer}" in (e.get("targets") or [])
                   for e in result.get("sequence") or [])
    return True


def test_every_speaker_owed_a_reaction_stays_queued(monkeypatch):
    """The draw after an owed exit keeps EVERY speaker it leaves, in its own
    order, as the open draw keeps its queue. 3's question reaches 1 and 2;
    2 is drawn first and whispers to 3, which 1 never hears -- and 1, still
    owed what 3 put to him, is called next, as he was before the stop.
    Keeping only the first drawn stranded him: 3 was called instead, and
    the line put to 1 went unanswered (review of the 2026-10-08 landing)."""
    calls, _ = _install(monkeypatch, _three, max_micro_rounds=5,
                        hears=_whispers_reach_only_their_listener)
    out = loops.interaction_loop(_Ctx(reactors=[1, 2, 3]), nonce=0)

    monkeypatch.setattr(loops, "EXITS_THAT_WAIT_OUTSIDE_THE_LOOP", frozenset())
    open_calls, _ = _install(monkeypatch, _three, max_micro_rounds=5,
                             hears=_whispers_reach_only_their_listener)
    loops.interaction_loop(_Ctx(reactors=[1, 2, 3]), nonce=0)

    assert open_calls == [1, 2, 3, 2, 1]        # the draw before the stop
    assert calls == open_calls, calls
    assert out["stop_reason"] == "awaiting player response"


LONG_ASK = ("Ask me plain and I will tell you what I know about the ledger "
            "and the man who carried it down the stair.")


def test_an_interrupted_ask_is_handed_back_as_it_was_cut(monkeypatch):
    """What waits on the player is what was SAID: the pilot cut into the
    brother's ask, so the ledger -- the resolve's, the narrator's and his
    own beat record -- holds it cut, and called again he is handed it cut,
    never the whole line beside the cut one (review of the 2026-10-08
    landing: one payload carried both)."""
    def script(cid, n):
        if cid == 83 and n == 1:
            return _says(83, LONG_ASK, to=PLAYER, asks_player=True)
        if cid == 81:
            line = _says(81, "Abel, enough of that.", to="Char83")
            line["sequence"][0]["interrupts"] = "83"
            return line
        return _says(83, "Fine, then.", to="Char81")

    calls, told = _install(monkeypatch, script, max_micro_rounds=3)
    out = loops.interaction_loop(_Ctx(reactors=[83, 81]), nonce=0)

    assert calls == [83, 81, 83], calls
    # The round the resolve and the narrator read (`combined_declarations`).
    record = out["rounds"][0]["result"]["sequence"][0]["text"]
    assert record != LONG_ASK and LONG_ASK.startswith(record.rstrip("—"))
    assert told[2]["said"] == [record], told


def test_the_acts_awaiting_resolution_are_the_exit_s_own():
    """One predicate, two projections: the acts the loop records as waiting
    on the world are exactly the ones that make the exit fire."""
    asserted = {"type": "action", "attempt": "nods once", "commitment": "asserted"}
    contested = {"type": "action", "attempt": "wrenches the bar loose",
                 "commitment": "contestable"}
    concealed = {"type": "action", "attempt": "palms the key",
                 "visibility": "concealed"}
    for sequence in ([], [asserted], [asserted, contested], [concealed],
                     [{"type": "speech", "text": "Grab it."}]):
        result = {"sequence": sequence}
        assert bool(common.acts_awaiting_resolution(result)) == \
            common._requires_director_resolution(result), sequence
    assert common.acts_awaiting_resolution(
        {"sequence": [asserted, contested, concealed]}) == [contested, concealed]
