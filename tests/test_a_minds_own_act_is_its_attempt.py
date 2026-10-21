"""A MIND'S OWN ACT IS REMEMBERED IN ITS OWN FIRST PERSON, AS ITS ATTEMPT,
WITH GRAMMAR THAT HOLDS.

The bare character contract writes an act "without a subject, as a watcher
would see it" ("lifts the latch and steps inside"). Put after "I tried to" as
written it read "I tried to lifts the latch" (story run 2026-09-30), so the
mind's memory named its doer instead -- third person, and AS DONE. On the
lighthouse probe (2026-10-20, chat 2 row 40) Pell's memory read "What I did:
Pell Hardacre takes the sealed letter from Rhona Carrick's hand and tucks it
into the inside pocket of the oilskin jacket." The world had refused that
take, and two story days later his memory of the skip, and his notebook,
believed he had pocketed the letter. `_own_sequence_memory`'s own contract is
"decision-framed on purpose -- 'I said', 'I tried to' -- an attempt beside the
perceived outcome, never a second resolved event competing with it".

The act is now turned into the mind's own attempt where the turn can be made
exactly (`composer.own_attempt`), and kept as before where it cannot -- never
a word dropped:

  1. verbs: the first word is the act's verb; a later one opens a verb phrase
     of the same doer after a coordinator, a sequencer or a comma, never after
     a relative pronoun; a body noun ("hands and knees") and an absolute
     phrase's head ("hands clasped") are nouns;
  2. the doer's own pronouns turn with it, only where nobody else present
     could be meant by them;
  3. quoted speech stays as said.
"""

from __future__ import annotations

import json
import time

import pytest

from agents.common import self_name_forms
from agents.composer import own_attempt
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import prepare_memory_commit
from persist.commit import _own_pronouns_in_scene, _own_sequence_memory
from story.character_schema import default_character_data

from tests.test_own_conduct_memory import _capture_batch, _conduct_rows

HE = {"subject": "he", "object": "him", "possessive": "his"}
SHE = {"subject": "she", "object": "her", "possessive": "her"}
PELL = self_name_forms("Pell Hardacre", ["Pell"])
TAKE = ("takes the sealed letter from Rhona Carrick's hand and tucks it into "
        "the inside pocket of the oilskin jacket")


def _turn(act, pronouns=HE, mine=True, forms=PELL):
    return own_attempt(act, self_forms=forms, pronouns=pronouns,
                       pronouns_mine=mine)


# --- 1. the probe's own line ----------------------------------------------------

def test_the_probes_take_is_remembered_as_his_attempt():
    content, gist = _own_sequence_memory(
        [{"type": "action", "subjectless": True, "attempt": TAKE},
         {"type": "speech", "text": "Ay, that I will."}],
        "Pell Hardacre", self_forms=PELL, pronouns=HE, pronouns_mine=True)
    assert content == (
        "I tried to take the sealed letter from Rhona Carrick's hand and tuck "
        "it into the inside pocket of the oilskin jacket. Then I said "
        "'Ay, that I will.'")
    assert "Pell Hardacre" not in content
    assert gist == content


# --- 2. the verbs of one doer --------------------------------------------------

@pytest.mark.parametrize("act,turned", [
    # coordinated verbs, with a particle or an adverb after them
    ("swings down the iron ladder hand over hand to the landing and casts off "
     "the Mary Ann's lines from the ring and bollard",
     "swing down the iron ladder hand over hand to the landing and cast off "
     "the Mary Ann's lines from the ring and bollard"),
    ("steps back from the ladder head to give her room and nods once toward "
     "the iron pegs along the wall",
     "step back from the ladder head to give her room and nod once toward "
     "the iron pegs along the wall"),
    ("lifts the ale pot slowly and drinks deep, eyes settling on the hearth",
     "lift the ale pot slowly and drink deep, eyes settling on the hearth"),
    # a series after commas, and a sequencer
    ("sets the post bag down on the hall table, pulls the Board's letter from "
     "the pocket, and breaks the seal",
     "set the post bag down on the hall table, pull the Board's letter from "
     "the pocket, and break the seal"),
    ("rises to hands and knees, then stands, bracing one hand flat against "
     "the wall",
     "rise to hands and knees, then stand, bracing one hand flat against "
     "the wall"),
    # an act the model wrote in the base form already
    ("make the Mary Ann fast to the ringbolt, kill the engine, and climb the "
     "iron ladder to the tower foot",
     "make the Mary Ann fast to the ringbolt, kill the engine, and climb the "
     "iron ladder to the tower foot"),
    # a capitalised first word, as the older contract wrote them
    ("Shifts slightly on the bench, making room",
     "shift slightly on the bench, making room"),
    # a span after a dash that opens with the doer's own sequencer
    ("lifts the cup \u2014 then sets it down on the boards",
     "lift the cup \u2014 then set it down on the boards"),
    # a body noun with its object straight after it is a verb
    ("turns from the window and eyes the door",
     "turn from the window and eye the door"),
    # only the first sentence is the attempt's; a later one stands as
    # written (the owner's bank, row 22342), and a title's period ends none
    ("lowers to one knee. Takes the foot in both hands and presses a kiss "
     "to it", "lower to one knee. Takes the foot in both hands and presses a "
     "kiss to it"),
    ("hands the letter to Mr. Penrose and turns away",
     "hand the letter to Mr. Penrose and turn away"),
])
def test_each_verb_of_the_doer_turns_and_nothing_else(act, turned):
    assert _turn(act) == turned


@pytest.mark.parametrize("act,kept", [
    # a body noun after a coordinator is a noun
    ("rises to hands and knees, then stands", "hands and knees"),
    # the head of an absolute phrase is a noun
    ("maintains standing position one pace back, hands clasped behind back, "
     "gaze fixed on the door", "hands clasped behind back"),
    ("waits at the rail, boots planted wide on the wet boards",
     "boots planted wide"),
    # a relative pronoun's verb is the relative's
    ("draws out the other chair and sits down, close enough that the table "
     "is all that lies between them", "all that lies between them"),
    # another subject's verb in a subordinate clause
    ("keeps one hand flat on the table while the other holds the pot",
     "while the other holds the pot"),
    # a subordinate clause's own coordinated verbs (the owner's bank, row
    # 28256: "as my own release breaks and soaks through")
    ("braces against the rail as the deck lifts and drops under the swell",
     "as the deck lifts and drops under the swell"),
    # a noun is a subordinate clause's subject (row 25673: "before things
    # get athletic" was filed "before thing get")
    ("loosens the knot before things get worse", "before things get worse"),
    # a list of the body's parts (row 26690: "feet and calves" was filed
    # "feet and calve")
    ("presses her bare feet and calves against the warm stones",
     "feet and calves against the warm stones"),
])
def test_what_is_not_the_doers_verb_is_left_as_written(act, kept):
    out = _turn(act)
    assert out and kept in out


# --- 3. the doer's own pronouns -------------------------------------------------

def test_the_doers_own_pronouns_turn_where_only_it_could_be_meant():
    assert _turn("lifts his hand from the pedestal and turns the brass collar") \
        == "lift my hand from the pedestal and turn the brass collar"
    assert _turn("drops onto the bench beside Tamsin, back to the room, so the "
                 "door is behind her and he is between her and it") == (
        "drop onto the bench beside Tamsin, back to the room, so the door is "
        "behind her and I am between her and it")


def test_a_pronoun_another_body_present_could_own_keeps_the_act_as_it_was():
    """Two women in one room (the owner's chats): the other woman's thighs
    must never be filed as the mind's own."""
    act = "slides both hands from her inner thighs to hook beneath her knees"
    assert _turn(act, pronouns=SHE, mine=False) == ""
    content, _ = _own_sequence_memory(
        [{"type": "action", "subjectless": True, "attempt": act}],
        "Mirelle", self_forms=self_name_forms("Mirelle", []), pronouns=SHE,
        pronouns_mine=False)
    assert content == "Mirelle slides both hands from her inner thighs to " \
                      "hook beneath her knees."


def test_another_bodys_pronouns_are_left_to_it():
    assert _turn("hooks a hand at her elbow and lifts the mug toward Hollis") \
        == "hook a hand at her elbow and lift the mug toward Hollis"


# --- 4. what cannot be turned exactly is kept, word for word ---------------------

@pytest.mark.parametrize("act", [
    # a dash opens a clause of its own subject: "withdraws" is the tongue's
    # (the owner's bank, row 23519)
    "intensifies the rhythm \u2014 tongue presses deeper, then withdraws to the rim",
    # a body noun with only a phrase after it could be either
    "draws the blanket over the torso and shoulders into the warmth",
    # an act the model wrote as a clause with its own subject (the owner's
    # bank, row 26271)
    "hips lock forward as the wave breaks over the bow",
    # a plural noun ending its own coordination (the owner's bank, row 27836:
    # "from coat and trousers" was filed "from coat and trouser")
    "stands up off the sand, brushing wet grit from coat and trousers",
    "lays both hands on the panel, fingers spreading across gauges and keys, "
    "reading them by touch",
    "keeps one hand flat on the table, still — does not turn, does not shift",
    "breathing settles back to slow and deep; the ear stills",
    "takes Rhona's hand in hers",
    "slowly lifts the latch",
    "扉を開けて中に入る",
])
def test_an_act_that_cannot_be_turned_exactly_is_kept_as_it_was(act):
    assert _turn(act, pronouns=SHE) == ""
    content, _ = _own_sequence_memory(
        [{"type": "action", "subjectless": True, "attempt": act}],
        "Nell Hale", self_forms=self_name_forms("Nell Hale", []),
        pronouns=SHE, pronouns_mine=True)
    assert content == "Nell Hale %s." % (act[0].lower() + act[1:])


def test_quoted_speech_in_an_act_is_what_was_said():
    assert _turn('mouths "she lies, he knows" at Tamsin and steps back',
                 pronouns=SHE) == \
        'mouth "she lies, he knows" at Tamsin and step back'


# --- 5. the contract's other attempts --------------------------------------------

def test_an_attempt_written_in_the_third_person_reads_as_english():
    """The owner's bank, memory row 30622: "I tried to steps forward to the
    control panel and reaches for the SHELTER button"."""
    content, _ = _own_sequence_memory(
        [{"type": "action", "attempt": "steps forward to the control panel "
                                       "and reaches for the SHELTER button"},
         {"type": "action", "attempt": "bar the door"}], "Sarah Moon")
    assert content == ("I tried to step forward to the control panel and "
                       "reach for the SHELTER button. Then I tried to bar "
                       "the door.")


# --- 6. the room decides whose a pronoun can be -----------------------------------

def _scene(**positions):
    entities = ({"hollis": {"name": "Hollis", "kind": "person"}}
                if "Hollis" in positions else {})
    return {"positions": positions, "rooms": {r: {"name": r} for r in
                                              set(positions.values())},
            "entities": entities}


class _Ctx:
    def __init__(self, cast):
        self.cast = cast
        self.chat = ChatData(id=1, name="t", persona_id=None, lorebook_id=None,
                             scenario="", created=0.0)
        self.extra_players = []


def _row(name, pronouns):
    sheet = default_character_data(name)
    sheet["identity"]["pronouns"] = pronouns
    return {"sheet": json.dumps(sheet)}


def test_the_scenes_verdict_on_a_minds_pronouns():
    pell, rhona, elias = (_row("Pell Hardacre", HE), _row("Rhona Carrick", SHE),
                          _row("Elias Thorne", HE))
    sheet = json.loads(pell["sheet"])
    ctx = _Ctx([pell, rhona, elias])
    # with a woman only: his can only be his
    assert _own_pronouns_in_scene(ctx, _scene(**{
        "Pell Hardacre": "steps", "Rhona Carrick": "steps"}),
        sheet, "Pell Hardacre") == (HE, True)
    # another man anywhere in the scene -- "calls up to him at the ladder
    # head" -- and whose "his" is, the act cannot say
    assert _own_pronouns_in_scene(ctx, _scene(**{
        "Pell Hardacre": "steps", "Rhona Carrick": "steps",
        "Elias Thorne": "lamp_room"}), sheet, "Pell Hardacre")[1] is False
    # a body whose pronouns the engine does not hold (a barman)
    assert _own_pronouns_in_scene(ctx, _scene(**{
        "Pell Hardacre": "taproom", "Hollis": "taproom"}),
        sheet, "Pell Hardacre")[1] is False
    # not placed at all: nothing to read the scene from
    assert _own_pronouns_in_scene(ctx, _scene(**{"Rhona Carrick": "steps"}),
                                  sheet, "Pell Hardacre")[1] is False


def test_a_body_held_inside_its_doer_could_be_meant_too():
    """The owner's chats: a body in an interior room of its doer -- "draw her
    in ... letting her feel" was hers, not the doer's."""
    mirelle, hinami = _row("Mirelle", SHE), _row("Hinami", SHE)
    scene = _scene(**{"Mirelle": "bedroom", "Hinami": "mirelle_throat"})
    assert _own_pronouns_in_scene(_Ctx([mirelle, hinami]), scene,
                                  json.loads(mirelle["sheet"]),
                                  "Mirelle")[1] is False


def test_a_first_person_line_keeps_pronouns_it_cannot_place_and_turns_the_rest():
    """The non-bare contract's line already read "I tried to ..." with its
    pronouns as written; where whose they are cannot be said they stay so,
    and the verb is still put right."""
    content, _ = _own_sequence_memory(
        [{"type": "action", "attempt": "Shifts her posture on the bench, "
                                       "turning slightly toward Hinami"}],
        "Mirelle", self_forms=self_name_forms("Mirelle", []), pronouns=SHE,
        pronouns_mine=False)
    assert content == ("I tried to shift her posture on the bench, turning "
                       "slightly toward Hinami.")


# --- 7. through the commit --------------------------------------------------------

def _pell_story(temp_db, *, elias_at):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Rock", "", time.time()))
    ids = {}
    for name, pronouns in (("Pell Hardacre", HE), ("Rhona Carrick", SHE),
                           ("Elias Thorne", HE)):
        sheet = default_character_data(name)
        sheet["identity"]["pronouns"] = pronouns
        ids[name] = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), sheet["identity"]["uid"]))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (chat_id, ids[name], "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Rock", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=303, chat_id=chat_id, idx=3, player_input="...",
                      created=time.time()),
        cast=cast, input="...",
        director_resolve={"resolved_event": "The beat resolves.",
                          "dialogue_log": []})
    ctx.character_results = {ids["Pell Hardacre"]: {
        "salience": 0.9,
        "sequence": [{"type": "action", "subjectless": True,
                      "attempt": TAKE + " and pats his chest over it"}],
        "active_state": {"mood": "steady"}}}
    positions = {"Pell Hardacre": "steps", "Rhona Carrick": "steps"}
    if elias_at:
        positions["Elias Thorne"] = elias_at
    scene = {"rooms": {"steps": {"name": "The Steps"},
                       "lamp_room": {"name": "The Lamp Room"}},
             "positions": positions, "entities": {}}
    return ctx, scene, ids


def test_the_commit_files_the_take_as_pells_own_attempt(temp_db, monkeypatch):
    ctx, scene, ids = _pell_story(temp_db, elias_at=None)
    captured = _capture_batch(monkeypatch)
    prepare_memory_commit(ctx, scene=scene)
    rows = [m for m in _conduct_rows(captured) if m["char_id"] == ids["Pell Hardacre"]]
    assert rows and rows[0]["content"] == (
        "What I did: I tried to take the sealed letter from Rhona Carrick's "
        "hand and tuck it into the inside pocket of the oilskin jacket and "
        "pat my chest over it.")


def test_with_another_man_on_the_rock_his_chest_could_be_either(temp_db, monkeypatch):
    """Elias up in the lamp room is still a "he" the act could mean."""
    ctx, scene, ids = _pell_story(temp_db, elias_at="lamp_room")
    captured = _capture_batch(monkeypatch)
    prepare_memory_commit(ctx, scene=scene)
    rows = [m for m in _conduct_rows(captured) if m["char_id"] == ids["Pell Hardacre"]]
    assert rows and rows[0]["content"] == (
        "What I did: Pell Hardacre takes the sealed letter from Rhona "
        "Carrick's hand and tucks it into the inside pocket of the oilskin "
        "jacket and pats his chest over it.")
