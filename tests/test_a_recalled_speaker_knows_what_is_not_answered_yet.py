"""A speaker called again in the same beat knows what is not answered yet.

The interaction loop may call a speaker a second time in one beat to answer
something that reached it (`loops._reaction_owed`). Its payload then has to
say what its first round left waiting on somebody outside the loop -- words
put to the player, who has no turn until the beat ends, or an act the world
has not answered -- or the wait reads as a silence. Measured, Brackwater
(scratch play db, chat 166 turn idx 26, capture 6911): called again after
his sister crossed to the door, the brother asked the player a second time,
and his own reason is on the record: "I said ask me plain. She hasn't yet."
Every line of his first round was in his payload, marked `this_beat`;
nothing said the player had not had a turn. That fact is
`decision.not_answered_yet` (`character._not_answered_yet_note`), with a
section of the bare card that ships only when it is present.

What it names has to be true. A line waits on the player only when its
addressee, read the way the resolve aims a line, is the player's body: not
a cast member, a presence or a second player, and not a line put to nobody,
which once handed a mind a listener it could not place. A line is handed
back as it was said, cut where an interruption cut it. And the section reads
the player's silence as THEIR SILENCE beside it does: a silence is something
a person did only in a turn they had (review of the 2026-10-08 landing).

The same second call was handed the per-turn debt note unchanged: it reads
committed beats and is cached once per turn, so a mind that had answered in
its first round would still be told someone was waiting on it. Speaking
discharges the debt, whatever was said -- the note's own rule -- and now
counts this beat's earlier rounds too. (0 of the 151 second calls captured
on that db carried a debt: latent, not measured.)
"""

from __future__ import annotations

from copy import deepcopy
import json
import time

import pytest

import agents.character as character
import agents.common as common
import agents.loops as loops
from agents import character_bare
from core.db import qi, wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.prompts import character_bare_module
from story.character_schema import default_character_data

HIS_ASK = "Ask me plain and I'll tell you what I know."
SHOVE = "shoves the door against the bar"


def _persona(name):
    return qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
              (name, json.dumps({"identity": {"name": name}})))


def _chat_row(temp_db, persona_id):
    chat_id = qi("INSERT INTO chats(name,persona_id,created) VALUES('beat',?,0)",
                 (persona_id,))
    return chat_id, dict(temp_db.q("SELECT * FROM chats WHERE id=?",
                                   (chat_id,), one=True))


# --- the note --------------------------------------------------------------------

def test_the_note_says_what_waits_and_on_whom():
    note = character._not_answered_yet_note(
        {"said": [HIS_ASK], "tried": [SHOVE]}, {"persona_id": None},
        {"identity": {"name": "Abel"}}, label=lambda name: "the woman")
    assert note == {"not_answered_yet": {
        "said_to": "the woman", "you_said": [HIS_ASK], "you_tried": [SHOVE]}}


def test_the_note_is_absent_when_nothing_was_left_open():
    for left in (None, {}, {"said": [], "tried": []}, {"said": ["  "]}):
        assert character._not_answered_yet_note(left, {}, {}, label=str) == {}


def test_the_note_is_bounded():
    lines, chars = character.NOT_ANSWERED_YET_LINES, character.NOT_ANSWERED_YET_CHARS
    many = [f"line {i} " + "x" * 400 for i in range(lines + 3)]
    note = character._not_answered_yet_note(
        {"said": many}, {}, {}, label=lambda name: "her")["not_answered_yet"]
    assert len(note["you_said"]) == lines
    assert note["you_said"][-1].startswith(f"line {len(many) - 1} ")
    assert all(len(line) == chars for line in note["you_said"])


class TestTheNameIsGated:
    """`said_to` names the player, so it passes the identity floor -- and by
    default, as `_player_silence_note` does: a caller that forgets the label
    cannot hand over a name the view withholds."""

    def _note(self, temp_db, *, knows):
        persona = _persona("Tamsin")
        chat_id, chat = _chat_row(temp_db, persona)
        wset(chat_id, "known", {"Abel": ["Tamsin"] if knows else []})
        return character._not_answered_yet_note(
            {"said": [HIS_ASK]}, chat, {"identity": {"name": "Abel"}}
        )["not_answered_yet"]

    def test_a_stranger_is_not_named(self, temp_db):
        note = self._note(temp_db, knows=False)
        assert note["you_said"] == [HIS_ASK]
        assert note.get("said_to") != "Tamsin", note

    def test_someone_known_is_named(self, temp_db):
        assert self._note(temp_db, knows=True)["said_to"] == "Tamsin"


def test_the_section_ships_only_with_the_note_and_names_its_fields():
    assert "not_answered_yet" not in character_bare.modules_for(
        {"self": {}, "perception": {}, "decision": {}})
    assert character_bare.modules_for(
        {"self": {}, "perception": {},
         "decision": {"not_answered_yet": {"you_said": [HIS_ASK]}}}
    ) == ["not_answered_yet"]
    for lang in ("en", "ja"):
        section = character_bare_module("not_answered_yet", lang)
        for key in ("`decision.not_answered_yet`", "`said_to`", "`you_said`",
                    "`you_tried`"):
            assert key in section, (lang, key)


# --- the payload a second call is handed ------------------------------------------

@pytest.fixture
def recall(temp_db, monkeypatch):
    """One mind in a room with the player, called through the real
    `character_step` with the model stubbed; returns (payload, card)."""
    now = time.time()
    persona = _persona("Tamsin")
    chat_id = qi("INSERT INTO chats(name,persona_id,scenario,created) "
                 "VALUES(?,?,?,?)", ("Brackwater", persona, "", now))
    sheet = default_character_data("Abel")
    char_id = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                 "VALUES(?,?,?,?,?)",
                 ("Abel", json.dumps(sheet), "{}", now, sheet["identity"]["uid"]))
    qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
       (chat_id, char_id, "active", "{}"))
    wset(chat_id, "scene", {
        "location": "House", "time": "now",
        "rooms": {"house": {"name": "House", "adjacent": []}},
        "positions": {"Abel": "house", "Tamsin": "house"},
        "entities": {}, "attire": {}, "overlays": {}})
    wset(chat_id, "known", {"Abel": ["Tamsin"]})

    def run(extra):
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,))
        turn_id = qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                     "VALUES(?,?,?,?)", (chat_id, 26, "Go on.", now))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Brackwater", persona_id=persona,
                          lorebook_id=None, scenario="", created=now),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=26,
                          player_input="Go on.", created=now),
            cast=cast, input="Go on.")
        ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": []}}
        ctx.perception_act = {"views": {str(char_id): "Tamsin waits at the table."}}
        ctx._extra.update(deepcopy(extra(char_id)))
        captured = {}

        def answer(role, step_key, system, payload, **kwargs):
            captured.setdefault("payload", deepcopy(payload))
            captured.setdefault("card", system)
            return {"sequence": []}

        monkeypatch.setattr(character, "_agent_json", answer)
        character.character_step(ctx, char_id, 0)
        return captured["payload"], captured["card"]

    return run


def _first_round(text=HIS_ASK):
    return {"sequence": [{"type": "speech", "text": text, "targets": ["Tamsin"]}],
            "interaction": {"addresses": ["Tamsin"], "expects_response": True}}


def test_a_speaker_called_again_is_told_what_waits_on_the_player(recall):
    payload, card = recall(lambda cid: {
        "beat_declared": {cid: _first_round()},
        "beat_left_open": {cid: {"said": [HIS_ASK], "tried": []}}})
    note = payload["decision"]["not_answered_yet"]
    assert note["you_said"] == [HIS_ASK]
    assert note["said_to"] == "Tamsin"
    assert "`decision.not_answered_yet`" in card


def test_a_first_call_is_told_nothing(recall):
    payload, card = recall(lambda cid: {})
    assert "not_answered_yet" not in payload["decision"]
    assert "`decision.not_answered_yet`" not in card


DEBT = {"awaiting_your_answer": {"from": "Tamsin", "asked": "Whose coat?",
                                 "turns_ago": 1}}


@pytest.mark.parametrize("earlier,owed", [
    (None, True),                                         # a first call
    ({"sequence": [{"type": "action", "attempt": "looks at the coat"}]}, True),
    (_first_round("It was his."), False),                 # answered this beat
])
def test_a_debt_answered_earlier_this_beat_is_not_owed_again(
        recall, monkeypatch, earlier, owed):
    """The debt reads committed beats; this beat's own earlier round is the
    loop's (`beat_declared`). Spoken in, it is discharged; a silent act is
    not speaking, and leaves it owed."""
    monkeypatch.setattr(character, "_unanswered_question_note",
                        lambda *a, **kw: deepcopy(DEBT))
    payload, card = recall(lambda cid: (
        {"beat_declared": {cid: earlier}} if earlier is not None else {}))
    assert ("awaiting_your_answer" in payload["decision"]) is owed, payload["decision"]
    assert ("`decision.awaiting_your_answer`" in card) is owed


# --- whom a line waits on: the resolve's own reading -----------------------------

PLAYER_LOOK = "A tall woman in a salt-stiff oilskin coat."
HAND_LOOK = "A stoop-shouldered wiry dock hand with tarred fingers."


@pytest.fixture
def staithe(temp_db):
    """Abel and Hester Gale in the house with the player, and every reader
    real: the loop's record (`loops._note_left_open`) over the label floor
    the resolve aims lines by (`director._bodies_addressed_as`), on a temp
    db. `build(positions, known, entities)` -> the beat's ctx."""
    now = time.time()
    persona = qi("INSERT INTO personas(name,sheet) VALUES(?,?)", (
        "Tamsin Coyle", json.dumps({
            "identity": {"name": "Tamsin Coyle"},
            "embodiment": {"visible": {"summary": PLAYER_LOOK}}})))
    chat_id = qi("INSERT INTO chats(name,persona_id,scenario,created) "
                 "VALUES(?,?,?,?)", ("Brackwater", persona, "", now))
    ids = {}
    for name in ("Abel Gale", "Hester Gale"):
        sheet = default_character_data(name)
        cid = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                 "VALUES(?,?,?,?,?)",
                 (name, json.dumps(sheet), "{}", now, sheet["identity"]["uid"]))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
           (chat_id, cid, "active", "{}"))
        ids[name] = cid

    def build(positions, known, entities=None):
        wset(chat_id, "scene", {
            "location": "House", "time": "now",
            "rooms": {"house": {"name": "House", "adjacent": []},
                      "cellar": {"name": "Cellar", "adjacent": []}},
            "positions": positions, "entities": entities or {},
            "attire": {}, "overlays": {}})
        wset(chat_id, "known", known)
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,))
        turn_id = qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                     "VALUES(?,?,?,?)", (chat_id, 26, "Go on.", now))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Brackwater", persona_id=persona,
                          lorebook_id=None, scenario="", created=now),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=26,
                          player_input="Go on.", created=now),
            cast=cast, input="Go on.")
        return ctx

    return build, ids


ALL_HOME = {"Abel Gale": "house", "Hester Gale": "house", "Tamsin Coyle": "house"}


def _abel_says(*lines, addresses=None):
    """One round of Abel's: `(text, targets)` pairs, as the bare contract
    writes them -- each target in his own words for the person."""
    return {"sequence": [{"type": "speech", "text": text, "targets": list(targets)}
                         for text, targets in lines],
            "interaction": {"addresses": list(addresses or []),
                            "expects_response": True}}


def _left_open(ctx, cid, result):
    """The words the loop records as waiting on the player, against the
    stored scene (the loop passes the scene its deliveries are judged
    against, which here is the same one)."""
    loops._note_left_open(ctx, cid, result)
    return [element["text"] if isinstance(element, dict) else element
            for element in ((ctx._extra.get("beat_left_open") or {}).get(cid)
                            or {}).get("said") or []]


def test_a_stranger_in_the_cast_named_by_his_word_for_her_is_not_the_player(staithe):
    """Abel has not been told Hester's name, so his line to her names her
    by the view's description; it resolves to her body, who can answer
    inside the loop, and waits on nobody outside it. His line to the player
    does."""
    build, ids = staithe
    ctx = build(ALL_HOME, {"Abel Gale": ["Tamsin Coyle"]})
    hester = common.observer_label_fn(ctx.chat, "Abel Gale", ctx.cast)("Hester Gale")
    assert hester != "Hester Gale"
    result = _abel_says(("Ask me plain.", ["Tamsin Coyle"]),
                        ("And you, wait on the walk.", [hester]),
                        addresses=["Tamsin Coyle", hester])
    assert _left_open(ctx, ids["Abel Gale"], result) == ["Ask me plain."]


def test_the_player_named_by_his_word_for_her_is_the_player(staithe):
    """The other way round: he does not know HER name, and his word for
    her is still her body. (The record follows the player exit's own test,
    `_asks_player`, which reads an address by name: a question fires it.)"""
    build, ids = staithe
    ctx = build(ALL_HOME, {"Abel Gale": ["Hester Gale"]})
    tamsin = common.observer_label_fn(ctx.chat, "Abel Gale", ctx.cast)("Tamsin Coyle")
    assert tamsin != "Tamsin Coyle"
    result = _abel_says(("What did you come for?", [tamsin]), addresses=[tamsin])
    assert common._asks_player(result, ctx.chat, ctx.cast)
    assert _left_open(ctx, ids["Abel Gale"], result) == [
        "What did you come for?"]


def test_a_line_to_a_presence_is_not_the_player_s(staithe):
    """A dock hand in the room, a body the scene records and no card
    describes, named by his look (Brackwater chat 165: "Give me a name and a
    boat." to "the stoop-shouldered wiry figure"). His answer is the
    background's, never the player's."""
    build, ids = staithe
    hand = {"hand": {"name": "Murren", "kind": "person", "appearance": HAND_LOOK}}
    ctx = build({**ALL_HOME, "Murren": "house"},
                {"Abel Gale": ["Tamsin Coyle", "Hester Gale"]}, hand)
    murren = common.observer_label_fn(ctx.chat, "Abel Gale", ctx.cast)("Murren")
    assert murren != "Murren"
    result = _abel_says(("Ask me plain.", ["Tamsin Coyle"]),
                        ("Give me a name and a boat.", [murren]),
                        addresses=["Tamsin Coyle", murren])
    assert _left_open(ctx, ids["Abel Gale"], result) == ["Ask me plain."]


def test_a_line_to_a_second_player_is_not_said_to_the_first(staithe):
    """A second player in the house: a question to him fires the player
    exit through its '?' (he is in no cast), and was then filed as said to
    the first player. It was not."""
    build, ids = staithe
    ctx = build({**ALL_HOME, "Wren Hale": "house"},
                {"Abel Gale": ["Tamsin Coyle", "Wren Hale"]})
    result = _abel_says(("Wren, where were you?", ["Wren Hale"]),
                        addresses=["Wren Hale"])
    assert common._asks_player(result, ctx.chat, ctx.cast)
    assert _left_open(ctx, ids["Abel Gale"], result) == []


def test_a_spoken_line_naming_nobody_is_aimed_by_its_rounds_addresses(staithe):
    """The resolve's own fallback (`director._take_declaration`): a spoken
    line with no target of its own goes to whom its round addressed. So a
    round put to the player carries its untargeted lines to her too."""
    build, ids = staithe
    ctx = build(ALL_HOME, {"Abel Gale": ["Tamsin Coyle"]})
    result = _abel_says(("Ask me plain.", ["Tamsin Coyle"]),
                        ("Whatever you came for.", []),
                        addresses=["Tamsin Coyle"])
    assert _left_open(ctx, ids["Abel Gale"], result) == [
        "Ask me plain.", "Whatever you came for."]


@pytest.mark.parametrize("known", [["Tamsin Coyle"], []])
def test_an_untargeted_line_carries_no_addressee(staithe, monkeypatch, known):
    """Abel mutters a question to nobody while the player is down in the
    cellar, where he cannot place her. The '?' fires the player exit; the
    line is still put to nobody, so nothing is filed as said to her and his
    second call is handed no listener his view does not hold -- by name
    when he knows her, by description when he does not."""
    build, ids = staithe
    ctx = build({"Abel Gale": "house", "Hester Gale": "house",
                 "Tamsin Coyle": "cellar"}, {"Abel Gale": known})
    cid = ids["Abel Gale"]
    mutter = _abel_says(("Where did I leave the lamp?", []))
    assert common._asks_player(mutter, ctx.chat, ctx.cast)
    assert _left_open(ctx, cid, mutter) == []

    captured = {}

    def answer(role, step_key, system, payload, **kwargs):
        captured.setdefault("payload", deepcopy(payload))
        captured.setdefault("card", system)
        return {"sequence": []}

    monkeypatch.setattr(character, "_agent_json", answer)
    ctx._extra["beat_declared"] = {cid: mutter}
    ctx.director_interpret = {"flow": {"reactors": [cid], "tom_triggers": []}}
    ctx.perception_act = {"views": {str(cid): "The lamp is out."}}
    character.character_step(ctx, cid, 0)
    assert "not_answered_yet" not in captured["payload"]["decision"]
    assert "`decision.not_answered_yet`" not in captured["card"]


def test_the_two_silence_sections_read_one_silence_alike(staithe, monkeypatch):
    """The player is in the room and opened the beat without a word, and
    Abel put his ask to her after: called again, he is handed both notes,
    and the card carries both sections. They are one statement of one
    class -- a silence is something a person did only in a turn they had --
    so THEIR SILENCE is the player's own turn, the one that opened the beat,
    and NOT ANSWERED YET the quiet after his ask, in which she has had none.
    Before, the first called her silence this beat something she did and
    the second called the same silence no answer (review of the 2026-10-08
    landing). Neither says the line was heard: a line put to someone out of
    earshot waits on them all the same."""
    build, ids = staithe
    ctx = build(ALL_HOME, {"Abel Gale": ["Tamsin Coyle"]})
    cid = ids["Abel Gale"]
    ask = _abel_says(("Ask me plain.", ["Tamsin Coyle"]), addresses=["Tamsin Coyle"])
    loops._note_left_open(ctx, cid, ask)
    ctx._extra["beat_declared"] = {cid: ask}
    captured = {}

    def answer(role, step_key, system, payload, **kwargs):
        captured.setdefault("payload", deepcopy(payload))
        captured.setdefault("card", system)
        return {"sequence": []}

    monkeypatch.setattr(character, "_agent_json", answer)
    ctx.director_interpret = {"flow": {"reactors": [cid], "tom_triggers": []}}
    ctx.perception_act = {"views": {str(cid): "Tamsin stands at the table."}}
    character.character_step(ctx, cid, 0)
    decision = captured["payload"]["decision"]
    assert decision.get("they_said_nothing") and decision.get("not_answered_yet")
    assert decision["not_answered_yet"]["you_said"] == ["Ask me plain."]
    card = captured["card"]
    silence = character_bare_module("their_silence", "en")
    waiting = character_bare_module("not_answered_yet", "en")
    assert silence in card and waiting in card
    assert "said nothing in their own turn, the one that opened this beat" in silence
    assert "only in a turn they had" in waiting
    assert "said nothing this beat" not in silence
    assert "unheard" not in waiting
    ja_silence = character_bare_module("their_silence", "ja")
    ja_waiting = character_bare_module("not_answered_yet", "ja")
    assert "この場面を開いた自分の番" in ja_silence
    assert "番があったときだけ" in ja_waiting
    assert "聞かれなかった" not in ja_waiting
