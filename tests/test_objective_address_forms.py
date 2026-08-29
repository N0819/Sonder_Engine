"""The objective record may not mint a form of address no card carries.

A card's typed identity is exactly {uid, name, aliases, pronouns}. Every other
authored attribute of a person -- what they are addressed as besides their
name, how old they are, what kind of being they are, who they are to someone
else -- lives only as free prose, and prose is not comparable to an assertion.
So an attribute nobody owns cannot be contradicted, and the objective record is
the one representation every observer's wording is derived from: an assertion
does not have to be TRUE to become the shared past, it only has to survive to
commit, after which it re-enters every mind through memory and every payload
through the transcript.

Measured, chat 95 (a 16-turn run, 2026-08-28), turn 1 / turn_id 3030. The
persona's card said one thing in three prose fields -- knowledge.public_history
"Lieutenant assigned to gamma shift in Stellar Cartography...", an
initial_outfit reading "lieutenant rank pips on the collar", an active concern
-- and identity.aliases was []. A character agent who had not recognized her
body ("the compact woman standing behind the command chair", its payload
carrying the authored form ZERO times) declared the speech "Lieutenant
Commander." The VERY NEXT call, the resolve prose author, promoted that
mistaken form of address into the omniscient third person:

    "Lieutenant Commander Sabine Oyelaran folds the five subspace metric
     traces onto a single overlay at the science station."

Its own payload had carried the authored form twice. From the following call
on, the invented form was in every specialist payload -- 51 of the 294 captured
payloads against 82 carrying the authored form, both in the same beat's
dialogue by turn 10 -- and it was durable in three stores (events rows, another
mind's autobiographical memory, checkpoints). The engine raised 133 warnings
across those 16 turns, including a name-channel firewall tripwire on turn 0,
and not one concerned the contradicted attribute. The two attributes the engine
DOES own were both defended in that same run, which is the proof of the rule:
an unearned name tripped the composer's identity floor and a pronoun has
`_check_pronoun_fidelity`.

The character being wrong is fiction working, and nothing here touches it. The
failure is the omniscient account adopting a mind's mistaken form of address as
objective third-person fact.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data

# The exact string from chat 95 turn 1, verbatim.
INVENTED = ("Lieutenant Commander Sabine Oyelaran folds the five subspace "
            "metric traces onto a single overlay at the science station. "
            "She checks the timestamps twice more, then crosses the bridge "
            "to the command chair, halting one pace behind it.")
AUTHORED = ("Lieutenant Sabine Oyelaran folds the five subspace metric "
            "traces onto a single overlay at the science station.")
# The same mistaken form, but SPOKEN by the character who was mistaken -- the
# quoted half of the same beat's resolved_event.
SPOKEN = ('Data turns his head to regard her. "Lieutenant Commander," he '
          'says formally. "Do you have a report for the gamma watch?"')

PUBLIC_HISTORY = ("Lieutenant assigned to gamma shift in Stellar Cartography "
                  "and bridge science station relief.")


def _persona(name, public_history, aliases=()):
    sheet = default_persona_data(name)
    sheet["identity"]["aliases"] = list(aliases)
    sheet["knowledge"]["public_history"] = public_history
    return sheet


def _card(name, public_history="", aliases=()):
    sheet = default_character_data(name)
    sheet["identity"]["aliases"] = list(aliases)
    sheet["knowledge"]["public_history"] = public_history
    return sheet


def _make_ctx(temp_db, persona_sheet, cards):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (persona_sheet["identity"]["name"], json.dumps(persona_sheet), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Test", persona_id, "", time.time()))
    for sheet in cards:
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (sheet["identity"]["name"], json.dumps(sheet), "{}", time.time(),
             sheet["identity"]["uid"]))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "report in", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="report in", created=time.time()),
        cast=cast, input="report in")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx


def _resolve(temp_db, monkeypatch, prose, persona_sheet, cards=()):
    import agents.director as director
    ctx = _make_ctx(temp_db, persona_sheet, list(cards))
    monkeypatch.setattr(director, "_agent_json",
                        lambda *a, **k: {"resolved_event": prose})
    director.director_resolve(ctx, nonce=0)
    return ctx


def _address_warnings(ctx):
    return [w for w in ctx.warnings if "form of address" in w]


def test_the_objective_account_may_not_mint_a_form_of_address_no_card_carries(
        temp_db, monkeypatch):
    """Chat 95 turn 1, the exact resolved_event, warned at the origin stage.

    "Lieutenant Commander Sabine Oyelaran folds the five subspace metric
    traces..." against a card whose only authored form is "Lieutenant". The
    warning has to name the form and the person, because the point of it is
    that the engine can say WHICH assertion it cannot source.
    """
    ctx = _resolve(temp_db, monkeypatch, INVENTED,
                   _persona("Sabine Oyelaran", PUBLIC_HISTORY))
    warnings = _address_warnings(ctx)
    assert warnings, ctx.warnings
    assert any("Lieutenant Commander" in w and "Sabine Oyelaran" in w
               for w in warnings)
    # Same channel as the epithet report: the Director is told, so it can stop
    # producing it, and nothing rewrites the account.
    assert any("Lieutenant Commander" in m for m in ctx.engine_feedback)


def test_a_form_of_address_the_card_authored_in_prose_passes_unremarked(
        temp_db, monkeypatch):
    """The authored form, which 82 of chat 95's 294 payloads carried.

    Free prose is the only place a card can put this today, so prose is a
    channel: what the guard reports is a form with NO channel, not every form
    the typed identity happens to omit.
    """
    ctx = _resolve(temp_db, monkeypatch, AUTHORED,
                   _persona("Sabine Oyelaran", PUBLIC_HISTORY))
    assert not _address_warnings(ctx), ctx.warnings


def test_a_form_of_address_carried_in_aliases_passes_unremarked(
        temp_db, monkeypatch):
    """Chat 95's registered cast carried their forms in `aliases`.

    Aliases are an INCLUSION list for recognition matching and defending an
    attribute is not their job -- but a form written there is still a form the
    author wrote down, so it is a channel like any other.
    """
    ctx = _resolve(
        temp_db, monkeypatch,
        "Doctor Wenna Ashgrove sets the lamp down and unrolls the chart.",
        _persona("Player", ""),
        [_card("Wenna Ashgrove", aliases=["Doctor Ashgrove", "Doctor"])])
    assert not _address_warnings(ctx), ctx.warnings


def test_a_mind_may_still_be_out_loud_wrong_about_who_someone_is(
        temp_db, monkeypatch):
    """The same mistaken form, inside the quotation marks it was spoken in.

    Chat 95 turn 1 again: Data said "Lieutenant Commander." to a body he had
    not recognized, and that is fiction working -- deception, dramatic irony
    and a mind acting on a false belief all need the mistake to be possible.
    Only the omniscient sentence around the quotation is scored.
    """
    ctx = _resolve(temp_db, monkeypatch, SPOKEN,
                   _persona("Sabine Oyelaran", PUBLIC_HISTORY),
                   [_card("Data")])
    assert not _address_warnings(ctx), ctx.warnings


def test_a_name_that_already_carries_its_own_form_of_address_is_left_alone(
        temp_db, monkeypatch):
    """A card storing the form INSIDE identity.name is a different defect.

    docs/UNBUILT.md 1.84d: "A character has nowhere to carry a rank, so the
    rank goes in the name". When it does, the engine cannot tell a second form
    from a spelling of the first, and reporting it means reporting the same
    person on every beat -- measured at 24 hits in one chat of the replay
    corpus, all of them one card named with an abbreviated form written out in
    full in the prose. Declining to score it is the same posture the pronoun
    check takes toward a paradigm it cannot be certain about.
    """
    ctx = _resolve(temp_db, monkeypatch,
                   "Commander Vale crosses to the rail and looks down.",
                   _persona("Player", ""), [_card("Cmdr. Vale")])
    assert not _address_warnings(ctx), ctx.warnings


def test_a_name_two_people_in_the_scene_share_is_not_scored(
        temp_db, monkeypatch):
    """A token that identifies two bodies identifies neither.

    Same rule as `_check_pronoun_fidelity`'s token_owner: the guard reports an
    assertion about a NAMED person, so it needs the name to name one.
    """
    ctx = _resolve(temp_db, monkeypatch,
                   "Sister Ashgrove closes the ledger without a word.",
                   _persona("Player", ""),
                   [_card("Wenna Ashgrove"), _card("Toma Ashgrove")])
    assert not _address_warnings(ctx), ctx.warnings
