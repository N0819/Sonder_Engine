"""The identity family from the Harrowmere playtest (2026-09-02): nothing
bound a ROLE, a POST and a BODY standing in the room, so the Director minted
duplicates of people already there, the background stage picked speakers in
other rooms, and two voices answered one question.

Three rules, one defect, stated as the classes they belong to:

* a minted role a present body already holds IS that body
  (`director_floors._bind_minted_entities_to_present_figures`);
* a demand nobody aimed does not cross a doorway, and a name in a line
  aimed at someone else is a subject, not an addressee
  (`commit_background.demand_reaches`, `pick_voice_demand`);
* a line aimed at one person is answered by one person
  (`background._one_answer_per_line`);

plus the stage contract those rules live under: a voice stage degrades to
silence and only a causal stage aborts (`background._voice_call`).
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mk_ctx(temp_db, presences=None, cast_names=None, player_input="",
            scene=None, turn_idx=5):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Identity", "", time.time()))
    for name in (cast_names or []):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower().replace(' ', '_')}"))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    temp_db.wset(cid, "scene", scene if scene is not None else {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    if presences is not None:
        temp_db.wset(cid, "background_presences", presences)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, player_input, time.time()))
    return PipelineContext(
        chat=ChatData(id=cid, name="Identity", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=cast, input=player_input)


#: The player with no persona row is "The Stranger" (story.scene.persona_of).
PLAYER = "The Stranger"


def _two_rooms(player_room="market_square"):
    """A square and a hall joined by an open door -- the Harrowmere
    geometry: `hear_level` grades that doorway as FULL hearing at normal
    volume, which is exactly the channel the unaimed demand used to ride."""
    return {
        "location": "Harrowmere",
        "rooms": {
            "market_square": {"name": "Market Square", "size": "huge",
                              "adjacent": [{"to": "reeve_hall",
                                            "barrier": "open_door",
                                            "distance": "near"}]},
            "reeve_hall": {"name": "Reeve's Hall", "size": "medium",
                           "adjacent": [{"to": "market_square",
                                         "barrier": "open_door",
                                         "distance": "near"}]},
        },
        "positions": {PLAYER: player_room},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _presence(room, **extra):
    rec = {"first_turn": 1, "last_turn": 4, "dialogue_turns": [],
           "mention_turns": [], "sketch": {"station_room": room}}
    rec.update(extra)
    return rec


_QUIET = {"resolved_event": "The square goes on about its business.",
          "dialogue_log": []}


# ---------------------------------------------------------------------------
# Gap 1 -- a minted role a present body already holds is that body
# ---------------------------------------------------------------------------

def _figures():
    return [
        {"name": "Innkeeper Tam Ashwell", "role": "innkeeper",
         "posts": ["ford_innkeeper"], "room": "ford_inn_common",
         "charter": "ford_inn", "body": "b1"},
        {"name": "Reeve halinham nookfeller", "role": "reeve",
         "posts": ["reeve"], "room": "reeve_hall",
         "charter": "reeves_hall", "body": "r1"},
        {"name": "Osric Fell", "role": "clerk", "posts": ["reeve_clerk"],
         "room": "reeve_hall", "charter": "reeves_hall", "body": "c1"},
        {"name": "Wat Penny", "role": "", "posts": [],
         "room": "reeve_hall", "charter": "reeves_hall", "body": "m1"},
    ]


class TestAMintedRoleAPresentBodyHoldsIsThatBody:
    def _floor(self):
        from agents.director import (
            _bind_minted_entities_to_present_figures)
        return _bind_minted_entities_to_present_figures

    def test_a_role_a_posted_body_holds_binds_the_mint_to_that_body(self):
        """Harrowmere t8: `ford_innkeeper` ("the innkeeper") minted in the
        common room beside three innkeepers."""
        sd = {"entities": {"ford_innkeeper": {
                  "name": "the innkeeper", "kind": "person",
                  "description": "A broad-shouldered man in a leather apron.",
                  "aliases": ["innkeeper", "keeper", "host"]}},
              "positions": {"ford_innkeeper": "ford_inn_common"}}
        dlog = [{"speaker": "the innkeeper", "exact_quote": "Aye?"}]
        order = ["the innkeeper"]
        bound = self._floor()({"entities": {}}, sd, _figures(),
                              dialogue_log=dlog, dialogue_order=order)
        assert [b["bound_to"] for b in bound] == ["Innkeeper Tam Ashwell"]
        assert bound[0]["by"] == "role" and not bound[0]["ambiguous"]
        ent = sd["entities"]["ford_innkeeper"]
        assert ent["name"] == "Innkeeper Tam Ashwell"
        assert "the innkeeper" in ent["aliases"]
        assert ent["charter_ref"] == {"charter": "ford_inn", "body": "b1"}
        # The Director's description of the body survives; the id survives.
        assert ent["description"].startswith("A broad-shouldered")
        assert sd["positions"] == {"ford_innkeeper": "ford_inn_common"}
        # Lines logged under the minted name follow it.
        assert dlog[0]["speaker"] == "Innkeeper Tam Ashwell"
        assert order == ["Innkeeper Tam Ashwell"]

    def test_a_name_a_present_body_answers_to_binds_by_name(self):
        """Harrowmere t18: `reeve_nookfeller` minted as "Reeve Halinham
        Nookfeller" -- the ledgered reeve's own name, differently cased."""
        sd = {"entities": {"reeve_nookfeller": {
                  "name": "Reeve Halinham Nookfeller", "kind": "person",
                  "aliases": ["Nookfeller", "reeve"]}},
              "positions": {}}
        bound = self._floor()({"entities": {}}, sd, _figures(),
                              fallback_room="reeve_hall")
        assert bound and bound[0]["by"] == "name"
        assert sd["entities"]["reeve_nookfeller"]["name"] == (
            "Reeve halinham nookfeller")
        # The minted spelling IS the display name, case aside: no alias is
        # added for it, and the ones the Director wrote survive.
        assert sd["entities"]["reeve_nookfeller"]["aliases"] == [
            "Nookfeller", "reeve"]

    def test_the_head_noun_decides_which_post_a_role_phrase_names(self):
        """Harrowmere t3: "the reeve's clerk" is a CLERK -- it must bind to
        the clerk on watch, never to the reeve the phrase qualifies him by."""
        sd = {"entities": {"reeve_clerk": {
                  "name": "the reeve's clerk", "kind": "person",
                  "aliases": ["clerk", "scribe"]}},
              "positions": {"reeve_clerk": "reeve_hall"}}
        bound = self._floor()({"entities": {}}, sd, _figures())
        assert [b["bound_to"] for b in bound] == ["Osric Fell"]

    def test_a_name_two_bodies_answer_to_is_refused(self):
        figs = _figures() + [{"name": "Innkeeper Tam Ashwell", "role": "cook",
                              "posts": ["cook"], "room": "ford_inn_common",
                              "charter": "ford_inn", "body": "b9"}]
        sd = {"entities": {"x": {"name": "Tam Ashwell", "kind": "person"}},
              "positions": {"x": "ford_inn_common"}}
        assert self._floor()({"entities": {}}, sd, figs) == []
        assert sd["entities"]["x"]["name"] == "Tam Ashwell"

    def test_a_role_two_posted_bodies_hold_binds_to_the_first_and_says_so(self):
        figs = _figures() + [{"name": "Aldo Marr", "role": "clerk",
                              "posts": ["clerk_b"], "room": "reeve_hall",
                              "charter": "reeves_hall", "body": "c2"}]
        sd = {"entities": {"c": {"name": "a clerk", "kind": "person"}},
              "positions": {"c": "reeve_hall"}}
        bound = self._floor()({"entities": {}}, sd, figs)
        assert bound[0]["bound_to"] == "Aldo Marr" and bound[0]["ambiguous"]

    def test_a_member_holding_no_post_never_binds_a_role(self):
        """Wat Penny holds no post this window, so "a clerk" cannot be him
        -- a role is a post held, not a guess about a bystander."""
        figs = [f for f in _figures() if f["name"] == "Wat Penny"]
        sd = {"entities": {"c": {"name": "a clerk", "kind": "person"}},
              "positions": {"c": "reeve_hall"}}
        assert self._floor()({"entities": {}}, sd, figs) == []

    def test_the_mint_binds_only_against_the_room_it_stands_in(self):
        """An innkeeper minted in the HALL is not the innkeeper in the inn."""
        sd = {"entities": {"i": {"name": "the innkeeper", "kind": "person"}},
              "positions": {"i": "reeve_hall"}}
        assert self._floor()({"entities": {}}, sd, _figures()) == []

    @pytest.mark.parametrize("ent", [
        {"name": "the innkeeper", "kind": "object"},
        {"name": "the innkeeper", "kind": "person", "portable": True},
        {"name": "the innkeeper", "kind": "person", "ubiquitous": True},
        {"name": "the innkeeper", "kind": "ship", "interior_rooms": ["hold"]},
    ])
    def test_things_are_never_bound(self, ent):
        sd = {"entities": {"i": dict(ent)},
              "positions": {"i": "ford_inn_common"}}
        assert self._floor()({"entities": {}}, sd, _figures()) == []

    def test_a_redeclared_entity_is_not_a_mint(self):
        sc = {"entities": {"ford_innkeeper": {"name": "the innkeeper"}}}
        sd = {"entities": {"ford_innkeeper": {"name": "the innkeeper",
                                              "kind": "person"}},
              "positions": {"ford_innkeeper": "ford_inn_common"}}
        assert self._floor()(sc, sd, _figures()) == []

    def test_no_figures_means_no_binding_and_no_change(self):
        sd = {"entities": {"i": {"name": "the innkeeper", "kind": "person"}},
              "positions": {"i": "ford_inn_common"}}
        before = json.dumps(sd, sort_keys=True)
        assert self._floor()({"entities": {}}, sd, []) == []
        assert json.dumps(sd, sort_keys=True) == before


class TestTheDirectorIsShownWhoIsHere:
    def test_present_figures_lists_posted_bodies_first_with_their_post(
            self, temp_db):
        from agents.common import present_charter_figures
        ctx = _mk_ctx(temp_db, scene=_two_rooms())
        temp_db.wset(ctx.chat.id, "charters", {"items": {"reeves_hall": {
            "state": {
                "key": "reeves_hall", "upkeeps": {}, "priority": [],
                "posts": {"reeve": {"place": "reeve_hall", "serves": [],
                                    "requires": {}}},
                "bodies": {
                    "r1": {"name": "Halinham Nookfeller", "place": "reeve_hall",
                           "available": True, "competence": {}},
                    "m1": {"name": "Wat Penny", "place": "reeve_hall",
                           "available": True, "competence": {}},
                    "away": {"name": "Ebba Stone", "place": "mill",
                             "available": True, "competence": {}},
                },
                "watch": {"reeve": "r1"},
            }}}})
        rows = present_charter_figures(ctx.chat.id, _two_rooms(),
                                       {"reeve_hall"})
        assert [r["name"] for r in rows] == ["Halinham Nookfeller",
                                             "Wat Penny"]
        assert rows[0]["role"] == "reeve" and rows[0]["posts"] == ["reeve"]
        assert rows[0]["charter"] == "reeves_hall" and rows[0]["body"] == "r1"
        assert rows[0]["room"] == "reeve_hall"
        assert rows[1]["role"] == "" and rows[1]["posts"] == []

    def test_a_story_with_no_charter_lists_nobody(self, temp_db):
        from agents.common import present_charter_figures
        ctx = _mk_ctx(temp_db, scene=_two_rooms())
        assert present_charter_figures(ctx.chat.id, _two_rooms(),
                                       {"reeve_hall"}) == []
        assert present_charter_figures(ctx.chat.id, _two_rooms(), set()) == []

    def test_the_objects_hand_receives_the_figures_and_nobody_else_does(self):
        from agents.director import _specialist_payload
        sc = {"rooms": {}, "entities": {}, "attire": {}}
        view = {"source": "resolved_beat", "player": PLAYER, "cast": [],
                "declared_actions": [], "dice": [], "prose": "x",
                "dialogue": [], "ledger_notes": {}, "manifest": []}
        figs = [{"name": "Innkeeper Tam Ashwell", "role": "innkeeper",
                 "room": "ford_inn_common", "posts": ["ford_innkeeper"],
                 "charter": "ford_inn", "body": "b1"}]
        objects = _specialist_payload("objects", None, sc, view,
                                      {"nonce": 1, "present_figures": figs})
        assert objects["present_figures"] == [
            {"name": "Innkeeper Tam Ashwell", "role": "innkeeper",
             "room": "ford_inn_common"}]
        bare = _specialist_payload("objects", None, sc, view, {"nonce": 1})
        assert "present_figures" not in bare


class TestTheBindingReachesTheLedger:
    def test_a_bound_mint_is_tracked_under_the_bodys_identity(self, temp_db):
        """`track_background_presences` keys the presence record on the
        charter body a floor-bound mint names, so the derived overlay and
        the durable ledger agree who this is from the first beat."""
        from persist.commit import track_background_presences
        ctx = _mk_ctx(temp_db, presences={}, scene=_two_rooms())
        ctx["director_resolve"] = {
            "resolved_event": "The innkeeper looks up.",
            "dialogue_log": [],
            "state_diff": {
                "entities": {"ford_innkeeper": {
                    "name": "Innkeeper Tam Ashwell", "kind": "person",
                    "description": "A broad-shouldered man.",
                    "aliases": ["the innkeeper"],
                    "charter_ref": {"charter": "ford_inn", "body": "b1"}}},
                "positions": {"ford_innkeeper": "market_square"}}}
        track_background_presences(ctx, "n")
        ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
        recs = [r for r in ledger.values()
                if r.get("name") == "Innkeeper Tam Ashwell"]
        assert len(recs) == 1
        assert recs[0]["charter_refs"] == [{"charter": "ford_inn",
                                            "body": "b1"}]
        assert "_charter_ref" not in (recs[0].get("sketch") or {})


# ---------------------------------------------------------------------------
# Gap 2 -- a demand nobody aimed does not cross a doorway
# ---------------------------------------------------------------------------

class TestADebtDoesNotCrossADoorway:
    def test_a_word_of_a_name_called_through_the_doorway_still_picks(
            self, temp_db):
        """Chat 72's night clerk, preserved: "Clerk?" from the lobby is the
        player turning toward whoever the clerk is, one open door away,
        and the hearing channel -- not a radius -- decides it arrives. What
        makes the Harrowmere reeves different is the OTHER addressee, below."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, scene=_two_rooms("market_square"),
                      player_input="Reeve? Anyone in the hall?",
                      presences={"Reeve Fenemere": _presence("reeve_hall")})
        assert pick_background_reactors(ctx, dict(_QUIET), cap=2) == [
            "Reeve Fenemere"]

    def test_the_same_mention_in_the_players_own_room_still_picks(
            self, temp_db):
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, scene=_two_rooms("reeve_hall"),
                      player_input="Morning. Is the reeve about today?",
                      presences={"Reeve Fenemere": _presence("reeve_hall")})
        assert pick_background_reactors(ctx, dict(_QUIET), cap=2) == [
            "Reeve Fenemere"]

    def test_an_exact_name_called_through_the_doorway_is_aimed_and_picks(
            self, temp_db):
        """Calling to someone in the next room on purpose is ordinary; the
        hearing channel decides whether it arrives."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, scene=_two_rooms("market_square"),
                      player_input="Reeve Fenemere! A word, when you can.",
                      presences={"Reeve Fenemere": _presence("reeve_hall")})
        assert pick_background_reactors(ctx, dict(_QUIET), cap=2) == [
            "Reeve Fenemere"]

    def test_an_owed_reply_does_not_discharge_through_the_doorway(
            self, temp_db):
        """Harrowmere t16: the miller, owed a reply from the mill, answered a
        player who was by then knocking on a door in another lane."""
        from persist.commit import pick_background_reactors
        owed = _presence("reeve_hall", pending_reply={
            "from": PLAYER, "quote": "Well?", "turn": 4, "expires_turn": 8})
        ctx = _mk_ctx(temp_db, scene=_two_rooms("market_square"),
                      presences={"Reeve Fenemere": owed})
        assert pick_background_reactors(ctx, dict(_QUIET), cap=1) == []
        ctx2 = _mk_ctx(temp_db, scene=_two_rooms("reeve_hall"),
                       presences={"Reeve Fenemere": owed})
        assert pick_background_reactors(ctx2, dict(_QUIET), cap=1) == [
            "Reeve Fenemere"]

    def test_demand_reaches_states_the_rule_directly(self):
        from persist.commit import demand_reaches
        sc = _two_rooms()
        assert demand_reaches(sc, "reeve_hall", {"market_square"}, aimed=True)
        assert not demand_reaches(sc, "reeve_hall", {"market_square"})
        assert demand_reaches(sc, "reeve_hall", {"reeve_hall"})
        # Fail-open for an UNPLACED presence stays exactly as it was.
        assert demand_reaches(sc, "", {"market_square"})
        assert demand_reaches(sc, "reeve_hall", set())


class TestTheResolveStagesAddresseeIsAnAddress:
    def test_the_players_intended_target_binds_to_a_present_body(
            self, temp_db):
        """Harrowmere t2, the other half: interpret marked no address, resolve
        wrote intended_target "market trader", and nobody bound it. The
        description binds to the one person-shaped body in the player's
        room, who is then the forced pick."""
        from persist.commit import pick_voice_demand
        line = "Morning. What are you selling? Is the reeve in the hall?"
        ctx = _mk_ctx(temp_db, scene=_two_rooms("market_square"),
                      player_input=line,
                      presences={"Trader Ansel": _presence("market_square"),
                                 "Reeve Fenemere": _presence("reeve_hall")})
        dr = {"resolved_event": "The trader looks up.",
              "dialogue_log": [{"speaker": PLAYER, "exact_quote": line,
                                "intended_target": "market trader",
                                "volume": "normal"}]}
        demand = pick_voice_demand(ctx, dr, cap=2)
        # The trader is the addressee; the reeve, matched on the word
        # "reeve" from a doorway away, is the SUBJECT of the question and
        # is not voiced -- with the cap at two, the slot stays empty.
        assert demand["picks"] == ["Trader Ansel"]
        assert demand["meta"]["Trader Ansel"]["player_addressed"]

    def test_only_the_players_own_lines_name_the_players_addressee(
            self, temp_db):
        from persist.commit import _player_intended_targets
        ctx = _mk_ctx(temp_db, scene=_two_rooms("market_square"))
        dr = {"dialogue_log": [
            {"speaker": PLAYER, "intended_target": "market trader"},
            {"speaker": "Someone Else", "intended_target": "the reeve"},
            {"speaker": PLAYER, "intended_target": " market  trader "},
            {"speaker": PLAYER, "intended_target": ""}]}
        assert _player_intended_targets(ctx, dr) == ["market trader"]

    def test_the_flow_channel_still_outranks_it(self, temp_db):
        from persist.commit import _addressed_ref_strings
        ctx = _mk_ctx(temp_db, scene=_two_rooms("market_square"))
        ctx["director_interpret"] = {"flow": {
            "addressed_to": ["Trader Ansel"],
            "addressed_to_refs": ["Trader Ansel"]}}
        dr = {"dialogue_log": [{"speaker": PLAYER,
                                "intended_target": "market trader"}]}
        assert _addressed_ref_strings(ctx, dr) == ["Trader Ansel"]


class TestANameInALineAimedAtSomeoneElseIsASubject:
    def test_a_loose_mention_is_dropped_when_the_beat_has_an_addressee(
            self, temp_db):
        """Harrowmere t4: the player asked the reeve's clerk "which of you is
        the reeve?"; the clerk was the addressee, and the reeve, picked on
        his own title, answered too -- with the opposite answer."""
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, scene=_two_rooms("reeve_hall"),
                      player_input="Which of you is the reeve?",
                      presences={"the reeve's clerk": _presence("reeve_hall"),
                                 "Reeve Fenemere": _presence("reeve_hall")})
        dr = {"resolved_event": "The clerk looks up.",
              "dialogue_log": [{"speaker": PLAYER,
                                "exact_quote": "Which of you is the reeve?",
                                "intended_target": "the reeve's clerk",
                                "volume": "normal"}]}
        assert pick_background_reactors(ctx, dr, cap=2) == ["the reeve's clerk"]

    def test_without_an_addressee_the_mention_still_qualifies(self, temp_db):
        from persist.commit import pick_background_reactors
        ctx = _mk_ctx(temp_db, scene=_two_rooms("reeve_hall"),
                      player_input="Which of you is the reeve?",
                      presences={"Reeve Fenemere": _presence("reeve_hall")})
        assert pick_background_reactors(ctx, dict(_QUIET), cap=2) == [
            "Reeve Fenemere"]

    def test_a_debt_survives_beside_an_addressee(self, temp_db):
        """Only the mention-alone candidate is a subject; an owed reply in
        the same room is still a demand of its own."""
        from persist.commit import pick_background_reactors
        owed = _presence("reeve_hall", pending_reply={
            "from": PLAYER, "quote": "Well?", "turn": 4, "expires_turn": 8})
        ctx = _mk_ctx(temp_db, scene=_two_rooms("reeve_hall"),
                      player_input="Which of you is the reeve?",
                      presences={"the reeve's clerk": _presence("reeve_hall"),
                                 "Reeve Fenemere": owed})
        dr = {"resolved_event": "x",
              "dialogue_log": [{"speaker": PLAYER,
                                "exact_quote": "Which of you is the reeve?",
                                "intended_target": "the reeve's clerk",
                                "volume": "normal"}]}
        picks = pick_background_reactors(ctx, dr, cap=2)
        assert picks[0] == "the reeve's clerk" and "Reeve Fenemere" in picks


# ---------------------------------------------------------------------------
# Gap 3 -- a line aimed at one person is answered by one person
# ---------------------------------------------------------------------------

def _reaction(name, quote, heard, beats_ago=0, action="nods"):
    return {"name": name, "room": "reeve_hall", "action": action,
            "dialogue_log_entry": {"speaker": name, "exact_quote": quote,
                                   "volume": "normal"},
            "heard_address": {"speaker": PLAYER, "exact_quote": heard,
                              "tone": "", "beats_ago": beats_ago}}


class TestOneLineHasOneAnswerer:
    def test_a_second_answer_to_the_same_line_becomes_a_claim(self, temp_db):
        """Harrowmere t5: one question to Nookfeller by name, two reeves'
        answers, one narrated speaker."""
        from agents.background import _one_answer_per_line, _result
        ctx = _mk_ctx(temp_db)
        q = "So what's the news in Harrowmere these days?"
        res = _result(["Nookfeller", "Fenemere"], [
            _reaction("Nookfeller", "Thin, but not quiet.", q),
            _reaction("Fenemere", "News travels slow up here.", q)])
        out = _one_answer_per_line(ctx, res)
        assert out["reactions"][0]["dialogue_log_entry"]["exact_quote"] == (
            "Thin, but not quiet.")
        second = out["reactions"][1]
        assert second["dialogue_log_entry"] is None
        assert second["demoted_line"] == "News travels slow up here."
        assert second["action"] == "nods"           # the act still stands
        assert out["claims"] == [{"claimant": "Fenemere",
                                  "text": "News travels slow up here.",
                                  "refs": [], "credence": "ordinary"}]
        assert out["selected"] == ["Nookfeller", "Fenemere"]
        assert any("one line has one answerer" in w for w in ctx.warnings)

    def test_answers_to_different_lines_are_both_delivered(self, temp_db):
        from agents.background import _one_answer_per_line, _result
        ctx = _mk_ctx(temp_db)
        res = _result(["A", "B"], [_reaction("A", "Yes.", "A, well?"),
                                   _reaction("B", "No.", "B, well?")])
        out = _one_answer_per_line(ctx, res)
        assert all(r["dialogue_log_entry"] for r in out["reactions"])
        assert not out.get("claims")

    def test_an_owed_reply_and_an_unaddressed_act_are_untouched(self, temp_db):
        from agents.background import _one_answer_per_line, _result
        ctx = _mk_ctx(temp_db)
        q = "Well?"
        res = _result(["A", "B", "C"], [
            _reaction("A", "Now.", q),
            _reaction("B", "Later.", q, beats_ago=1),
            {"name": "C", "room": "reeve_hall", "action": "sweeps",
             "dialogue_log_entry": {"speaker": "C", "exact_quote": "Hm."},
             "heard_address": None}])
        out = _one_answer_per_line(ctx, res)
        assert [r["dialogue_log_entry"]["exact_quote"]
                for r in out["reactions"]] == ["Now.", "Later.", "Hm."]

    def test_the_legacy_single_entry_keys_follow_the_kept_answer(
            self, temp_db):
        from agents.background import _one_answer_per_line, _result
        ctx = _mk_ctx(temp_db)
        q = "Well?"
        res = _result(["A", "B"], [_reaction("A", "Now.", q),
                                   _reaction("B", "Later.", q)])
        out = _one_answer_per_line(ctx, res)
        assert out["fired"] and out["name"] == "A"
        assert out["dialogue_log_entry"]["exact_quote"] == "Now."


# ---------------------------------------------------------------------------
# A voice stage degrades to silence; only a causal stage aborts
# ---------------------------------------------------------------------------

class TestAVoiceStageDegradesToSilence:
    def test_a_provider_failure_is_a_warning_and_no_line(self, temp_db):
        from agents.background import _voice_call
        ctx = _mk_ctx(temp_db)

        def boom():
            raise RuntimeError("background_react: all providers failed "
                               "(last provider error: HTTP 503)")
        assert _voice_call(ctx, "background_react", "the miller", boom) is None
        assert any("HTTP 503" in w and "stays silent" in w
                   for w in ctx.warnings)

    def test_cancellation_still_propagates(self, temp_db):
        from agents.background import _voice_call
        from llm.providers import Aborted
        ctx = _mk_ctx(temp_db)

        def stop():
            raise Aborted("cancelled")
        with pytest.raises(Aborted):
            _voice_call(ctx, "background_react", "x", stop)

    def test_the_stage_returns_silence_rather_than_raising(
            self, temp_db, monkeypatch):
        """Harrowmere t21: one 503 inside `_react_one` aborted a turn the
        Director had already resolved."""
        import agents.background as background
        from agents.background import background_react

        def fail(*args, **kwargs):
            raise RuntimeError("HTTP 503: service overloaded")
        monkeypatch.setattr(background, "_agent_json", fail)
        ctx = _mk_ctx(temp_db, scene=_two_rooms("reeve_hall"),
                      player_input="Reeve Fenemere, a word.",
                      presences={"Reeve Fenemere": _presence("reeve_hall")})
        ctx["director_resolve"] = dict(_QUIET)
        out = background_react(ctx, "n")
        assert out["fired"] is False
        assert out["selected"] == ["Reeve Fenemere"]
        assert any("stays silent" in w for w in ctx.warnings)
