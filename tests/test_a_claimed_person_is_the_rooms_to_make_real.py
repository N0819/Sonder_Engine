"""A person a character invents stays that character's claim, and the
Writers' Room may make them real when it plans -- never code, never
automatically.

The owner's ruling on the Brackwater run's D6 (F99), 2026-10-09: an invented
townsperson stays the character's claim (it may be a lie); the Writers' Room
MAY ratify it when it plans, never automatically.

What the run measured (scratch story 166, idx 19). Hester named "Tam Elver,
tallyman at the bonded store", a man nothing in the world held, and the
engine filed it exactly as designed: a claim no event backs
(`story.carriers._invented_claim`, a `claim:` id), `invented` on her own
row, `told` -- by Hester -- on the player's. Fifteen such rows by the end of
the run, Tam Elver in four of them. And the one author allowed to make him
real never saw any of it: neither payload the Room plans from -- the full
Planner's (`agents.story_planner._payload`) nor the planting sketch's
(`story.room_sketch.sketch_payload`) -- carried a single claim.

* THE PAYLOAD: both carry "unbacked_claims", words said aloud near the
  story with no report the speaker carried behind them -- the words
  ("said"), who said them first ("by"), when ("turn"), and who near the
  story has heard them and from whom ("heard_by"). That is all code knows:
  much of it is what the speaker saw, and some may be a lie.
* REACH: a claim rides when somebody within reach holds it -- the player
  always, a body standing in the frontier's reach -- and one held only far
  off does not.
* ONLY CLAIMS: a report an event backs is not a claim and is never listed.
* THE INVENTED PERSON FIRST: a row whose words say whole a head nobody the
  world holds answers to -- read from the encoder's own record of who
  somebody was revealed to be, never from prose, so it holds in either pack
  -- is shown before any other and says which (review RP-2). Said WHOLE,
  because what the encoder writes down is not always a name, and a clause's
  last word marked claims that named nobody (review RP2-N1).
* BOUNDED: at most `ROOM_CLAIMS_SHOWN`, then newest first, the rest counted.
* THE PLAYER'S OWN CLAIMS FOLLOW THEIR AUTHORITY: one the player made rides
  only when the story's player authority grants the world (review RP-6; the
  owner, 2026-10-09: a player's assertions belong to the authority settings).
* NOTHING WRITES, NOTHING PLANTS: the read leaves every row as it was, and
  the payload builders are its only readers -- code never files a plan from
  a claim.
* A SKETCH HANDS A CLAIMED PERSON ON: one it plants anyway lands nothing and
  goes to the full planner, which can read the plans and write `known_by`
  (review RP-3).
* THE CARDS: both cards, both packs, say what code knows of the section,
  that the full planner may plant the person a claim names deliberately and
  the sketch hands them on, and that a reply never says whether a
  character's words are true unless the player asked (review RP-5) -- the
  full planner's naming what it planted only as spoiler-safe as a sealed
  package allows (review RP5-N1).
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import pytest

from core.db import wset
from llm import providers
from llm.prompts import get_prompt
from story import room_frontier as rf
from story.carriers import ROOM_CLAIMS_SHOWN, unbacked_claims
from story.room_sketch import sketch_payload
from agents import story_planner as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402

PLAYER = "Tamsin Coyle"
TAM = ("Abel claimed he was the only hand aboard the Corvina, but Tam Elver's "
       "coat is on the stake")
TAM_HEARD = ("Abel claimed he was the only hand aboard, but Tam Elver's coat "
             "is on the stake")


def _claim(uid, text, *, turn, provenance="invented", told_by="",
           retellings=0, room="grebe_board"):
    return {"world_event_id": uid, "source_event_id": "", "claim": text,
            "kind": "claim", "occurred_at": 0.0, "acquired_turn": turn,
            "acquired_location": room, "current_location": room,
            "route": [room], "hops": 0, "retellings": retellings,
            "told_by": told_by, "provenance": provenance}


def _event_report(uid, text, *, turn):
    return {"world_event_id": uid, "source_event_id": uid, "claim": text,
            "kind": "event", "occurred_at": 1.0, "acquired_turn": turn,
            "acquired_location": "grebe_board",
            "current_location": "grebe_board", "route": ["grebe_board"],
            "hops": 0, "retellings": 0, "told_by": "",
            "provenance": "witnessed"}


def _cast(db, cid, name, reports):
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps({"identity": {"name": name}}), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,'active',?)",
          (cid, char_id, json.dumps({"carried_reports": reports})))
    return char_id


def _story(db, *, hester=None, colynon=None, player=None, turns=20):
    """A channel walk four hops long: the player and Hester on the boat at
    one end, Colynon in the chapel at the other -- beyond the frontier's
    reach (`room_frontier.FRONTIER_DEPTH_HOPS`)."""
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Brackwater", "A drowned barge.", time.time()))
    pid = db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                (PLAYER, json.dumps({"identity": {"name": PLAYER}})))
    db.qi("UPDATE chats SET persona_id=? WHERE id=?", (pid, cid))
    chain = ["grebe_board", "landing_stage", "low_walk", "chapel_steps",
             "tide_chapel"]
    rooms = {}
    for i, rid in enumerate(chain):
        adjacent = []
        if i:
            adjacent.append({"to": chain[i - 1], "barrier": "open"})
        if i + 1 < len(chain):
            adjacent.append({"to": chain[i + 1], "barrier": "open"})
        rooms[rid] = {"name": rid.replace("_", " ").title(),
                      "desc": "Reed and black water.", "adjacent": adjacent}
    wset(cid, "scene", {"location": "Brackwater", "rooms": rooms,
                        "positions": {PLAYER: "grebe_board",
                                      "Hester Gale": "grebe_board",
                                      "Colynon Saltowford": "tide_chapel"},
                        "entities": {}, "attire": {}})
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    _cast(db, cid, "Hester Gale", hester if hester is not None else [
        _claim("claim:9aabf4bc92fa614e", TAM, turn=19),
        _event_report("event:coat_on_the_stake",
                      "A wool coat caught at the third stake", turn=15)])
    _cast(db, cid, "Colynon Saltowford", colynon if colynon is not None else [
        _claim("claim:00000000000000c0", "Old Murren rang the bell for a "
               "drowned man in the year of the great flood", turn=12,
               room="tide_chapel")])
    wset(cid, "persona_carrier_state", {"carried_reports": player
                                        if player is not None else [
        _claim("claim:9aabf4bc92fa614e", TAM_HEARD, turn=19,
               provenance="told", told_by="Hester Gale", retellings=1)]})
    return cid


TAM_ROW = {"said": TAM, "by": "Hester Gale", "turn": 19,
           "heard_by": [{"who": PLAYER, "from": "Hester Gale"}]}


def _rows(cid):
    report = rf.frontier_report(cid, None)
    rooms = [report["player_room"], *report["reachable"]]
    return unbacked_claims(cid, None, rooms)


class TestTheClaimsWithinReach:
    def test_a_claim_no_event_backs_is_listed_with_its_maker_and_hearers(
            self, temp_db):
        cid = _story(temp_db)
        rows, total = _rows(cid)
        assert rows == [TAM_ROW]
        assert total == 1

    def test_a_claim_held_only_far_off_is_not_listed(self, temp_db):
        """Colynon's claim is real hearsay in the world; nobody within the
        frontier's reach of the player holds it."""
        cid = _story(temp_db)
        rows, _total = _rows(cid)
        assert all("Murren" not in r["said"] for r in rows)

    def test_a_report_an_event_backs_is_not_a_claim(self, temp_db):
        cid = _story(temp_db)
        rows, _total = _rows(cid)
        assert all("third stake" not in r["said"] for r in rows)

    def test_the_player_always_carries_theirs_into_reach(self, temp_db):
        """Told far away, carried here: the player's own claims ride wherever
        the player stands."""
        cid = _story(temp_db, hester=[], player=[
            _claim("claim:00000000000000b1", "The Selwick man came round the "
                   "low walk twice", turn=8, provenance="told",
                   told_by="Colynon Saltowford", retellings=1,
                   room="tide_chapel")])
        rows, _total = _rows(cid)
        assert rows == [{"said": "The Selwick man came round the low walk "
                                 "twice",
                         "by": "Colynon Saltowford", "turn": 8,
                         "heard_by": [{"who": PLAYER,
                                       "from": "Colynon Saltowford"}]}]

    def test_a_maker_no_record_names_is_left_unsaid(self, temp_db):
        """Heard at the second retelling, its maker's own row long gone:
        "by" is said only when the world knows it."""
        cid = _story(temp_db, hester=[], player=[
            _claim("claim:00000000000000b2", "A tallyman drinks at the "
                   "staithe", turn=9, provenance="told",
                   told_by="Hester Gale", retellings=2)])
        rows, _total = _rows(cid)
        assert rows[0]["by"] == ""

    def test_newest_first_and_the_rest_counted(self, temp_db):
        many = [_claim("claim:%016x" % i, "Claim number %d" % i, turn=i)
                for i in range(ROOM_CLAIMS_SHOWN + 3)]
        cid = _story(temp_db, hester=many, player=[])
        rows, total = _rows(cid)
        assert len(rows) == ROOM_CLAIMS_SHOWN
        assert total == ROOM_CLAIMS_SHOWN + 3
        assert [r["turn"] for r in rows] == sorted(
            (r["turn"] for r in rows), reverse=True)
        assert rows[0]["said"] == "Claim number %d" % (ROOM_CLAIMS_SHOWN + 2)

    def test_the_read_writes_nothing(self, temp_db):
        cid = _story(temp_db)
        before = temp_db.q("SELECT key, value FROM world WHERE chat_id=? "
                           "ORDER BY key", (cid,))
        cast_before = temp_db.q("SELECT char_id, state FROM chat_chars "
                                "WHERE chat_id=? ORDER BY char_id", (cid,))
        _rows(cid)
        assert [tuple(r) for r in temp_db.q(
            "SELECT key, value FROM world WHERE chat_id=? ORDER BY key",
            (cid,))] == [tuple(r) for r in before]
        assert [tuple(r) for r in temp_db.q(
            "SELECT char_id, state FROM chat_chars WHERE chat_id=? "
            "ORDER BY char_id", (cid,))] == [tuple(r) for r in cast_before]


class TestABodysInsideStandsWhereTheBodyStands:
    """Story 166's player and pilot stood on the Grebe's deck from beat 13 --
    the inside of a vessel, which the frontier leaves out of its reach
    because no plan can be filed there. The pilot's claims are near the
    story all the same, and so are those of anyone aboard a boat moored where
    the player stands."""

    BARARON = _claim("claim:7b26bca4554183ae", "It was wool, dark, caught "
                     "fast at the shoulder past the third stake", turn=10,
                     provenance="told", told_by="Bararon Haugenish",
                     retellings=1)

    def _boat(self, db, cid, *, player_on_deck):
        scene = db.wget(cid, "scene", {})
        scene["rooms"]["grebe_board"]["parent_entity"] = "the_grebe"
        scene["entities"]["the_grebe"] = {"name": "the Grebe",
                                          "kind": "vehicle"}
        scene["positions"]["the_grebe"] = "landing_stage"
        if not player_on_deck:
            scene["positions"][PLAYER] = "landing_stage"
        db.wset(cid, "scene", scene)

    def test_a_claim_held_aboard_with_the_player_is_near(self, temp_db):
        cid = _story(temp_db, hester=[self.BARARON], player=[])
        self._boat(temp_db, cid, player_on_deck=True)
        _context, payload = sketch_payload(
            cid, None, rf.frontier_report(cid, None), turn_idx=19)
        assert payload["unbacked_claims"] == [{
            "said": self.BARARON["claim"], "by": "Bararon Haugenish",
            "turn": 10,
            "heard_by": [{"who": "Hester Gale", "from": "Bararon Haugenish"}]}]

    def test_a_claim_held_aboard_a_boat_at_the_players_quay_is_near(
            self, temp_db):
        cid = _story(temp_db, hester=[self.BARARON], player=[])
        self._boat(temp_db, cid, player_on_deck=False)
        rows, _total = _rows(cid)
        assert [r["said"] for r in rows] == [self.BARARON["claim"]]


class Script:
    def __init__(self):
        self.payloads = []

    def __call__(self, role, system, user, **kw):
        self.payloads.append(json.loads(user))
        return json.dumps({"reply": "Nothing to build this pass."})


class TestBothPayloadsCarryThem:
    def test_the_planners_payload(self, temp_db, monkeypatch):
        cid = _story(temp_db)
        script = Script()
        monkeypatch.setattr(providers, "chat_complete", script)

        sp.run_planner(cid, None, text="Who is Tam Elver?")

        assert script.payloads[0]["unbacked_claims"] == [TAM_ROW]
        assert "unbacked_claims_more" not in script.payloads[0]

    def test_the_sketchs_payload(self, temp_db):
        cid = _story(temp_db)
        report = rf.frontier_report(cid, None)

        _context, payload = sketch_payload(cid, None, report, turn_idx=19)

        assert payload["unbacked_claims"] == [TAM_ROW]

    def test_no_claim_no_section(self, temp_db, monkeypatch):
        cid = _story(temp_db, hester=[], colynon=[], player=[])
        script = Script()
        monkeypatch.setattr(providers, "chat_complete", script)

        sp.run_planner(cid, None, text="Anything ahead?")
        _context, payload = sketch_payload(
            cid, None, rf.frontier_report(cid, None), turn_idx=19)

        assert "unbacked_claims" not in script.payloads[0]
        assert "unbacked_claims" not in payload


def test_only_the_rooms_payloads_read_the_claims():
    """A claim's maker is private to its maker (`carriers._invented_claim`):
    the author may read it, no mind may. And no code files a plan from one
    -- the two payload builders are the section's only readers.

    The engine's own source only (`project_check.engine_python_paths`, the
    one tuple of where it lives): a walk of the whole checkout read the
    owner's worktrees under `.claude/` and the browser venv, about 5,750
    files, and failed with nothing wrong the moment a worktree held this
    commit (review RP-4)."""
    readers = set()
    for path in pc.engine_python_paths():
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                    a.name == "unbacked_claims" for a in node.names):
                readers.add(rel)
    assert readers == {"agents/story_planner.py", "story/room_sketch.py"}


# ---------------------------------------------------------------------------
# The slots go to the invented person first (review RP-2)
# ---------------------------------------------------------------------------

TAM_INTRO = "Tam Elver, tallyman at the bonded store for the Marsh Agency"


def _introduced(db, cid, idx, *learned, step="director_resolve", active=1):
    """The encoder's record of a name revealed at beat ``idx``: its
    committed diff's `introductions`, on the Director stage's variant."""
    turn = db.q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (cid, idx),
                one=True)
    sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                (turn["id"], step, step, 5))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,?)",
          (sid, json.dumps({"state_diff": {"introductions": [
              {"who": PLAYER, "learns": learns, "from_event": 1}
              for learns in learned]}}), time.time(), active))


def _many(n, *, first_turn=0):
    return [_claim("claim:%016x" % (first_turn + i),
                   "Claim number %d about the tide" % (first_turn + i),
                   turn=first_turn + i) for i in range(n)]


class TestTheSlotsGoToTheInventedPersonFirst:
    def test_a_row_naming_somebody_nobody_holds_is_shown_first_and_says_who(
            self, temp_db):
        """Eight later tellings of ordinary things would have pushed Hester's
        Tam Elver out of a newest-first cap; the name nobody holds keeps
        him in it, and the row says which name that is."""
        many = _many(ROOM_CLAIMS_SHOWN, first_turn=40)
        cid = _story(temp_db, turns=60, hester=[
            _claim("claim:9aabf4bc92fa614e", TAM, turn=19), *many], player=[])
        _introduced(temp_db, cid, 19, TAM_INTRO)

        rows, total = _rows(cid)

        assert total == ROOM_CLAIMS_SHOWN + 1
        assert len(rows) == ROOM_CLAIMS_SHOWN
        assert rows[0]["said"] == TAM
        assert rows[0]["unheld_names"] == ["Tam Elver"]
        assert all("unheld_names" not in r for r in rows[1:])
        assert [r["turn"] for r in rows[1:]] == sorted(
            (r["turn"] for r in rows[1:]), reverse=True)

    def test_without_the_encoders_record_the_rows_are_newest_first(
            self, temp_db):
        """Nothing read, nothing promoted: the old order, unchanged."""
        many = _many(ROOM_CLAIMS_SHOWN, first_turn=40)
        cid = _story(temp_db, turns=60, hester=[
            _claim("claim:9aabf4bc92fa614e", TAM, turn=19), *many], player=[])

        rows, _total = _rows(cid)

        assert all(r["said"] != TAM for r in rows)
        assert all("unheld_names" not in r for r in rows)

    def test_a_name_the_room_has_since_planted_is_held(self, temp_db):
        """Read afresh each time: once a plan answers to the name, nobody is
        left unheld, and the row is an ordinary one again."""
        from world.planned_entities import add_planned_entity
        cid = _story(temp_db)
        _introduced(temp_db, cid, 19, TAM_INTRO)
        assert _rows(cid)[0][0]["unheld_names"] == ["Tam Elver"]

        add_planned_entity(cid, {"kind": "person", "name": "Tam Elver",
                                 "role": "tallyman",
                                 "brief": {"where": "landing_stage"}})

        assert "unheld_names" not in _rows(cid)[0][0]

    def test_a_name_somebody_the_world_holds_answers_to_is_not_unheld(
            self, temp_db):
        """The player introduced by name and work, and a held cast member by
        a title: the engine's own resolution answers to both."""
        cid = _story(temp_db, hester=[_claim(
            "claim:00000000000000d1", "Tamsin Coyle of River Underwriters "
            "came asking after Mrs Gale's brother", turn=12)], player=[])
        _introduced(temp_db, cid, 12, "Tamsin Coyle, River Underwriters",
                    "Mrs Gale")

        assert "unheld_names" not in _rows(cid)[0][0]

    def test_only_the_name_is_read_never_what_is_said_of_its_bearer(
            self, temp_db):
        """Measured on story 166: its `learns` read whole answered to the
        room the description named, and the invented man was held."""
        cid = _story(temp_db)
        scene = temp_db.wget(cid, "scene", {})
        scene["rooms"]["bonded_store"] = {"name": "the bonded store",
                                          "desc": "Grain sacks.", "adjacent": []}
        temp_db.wset(cid, "scene", scene)
        _introduced(temp_db, cid, 19, TAM_INTRO)

        assert _rows(cid)[0][0]["unheld_names"] == ["Tam Elver"]

    def test_the_name_is_read_from_the_encoders_record_in_either_pack(
            self, temp_db):
        """No letter case to read a name from, and none needed: the encoder
        wrote it down as a name, and the engine's name boundary finds it."""
        said = "エイベルは自分ひとりが乗っていたと言ったが、杭にはタム・エルヴァーの上着がある"
        cid = _story(temp_db, hester=[_claim("claim:00000000000000e1", said,
                                             turn=19)], player=[])
        _introduced(temp_db, cid, 19, "タム・エルヴァー、保税倉庫の計量係")

        assert _rows(cid)[0][0]["unheld_names"] == ["タム・エルヴァー"]

    def test_only_the_active_variant_is_the_record(self, temp_db):
        """A rerolled-away Director answer is not what the beat committed."""
        cid = _story(temp_db)
        _introduced(temp_db, cid, 19, TAM_INTRO, active=0)

        assert "unheld_names" not in _rows(cid)[0][0]

    @pytest.mark.parametrize("learns, said", [
        ("something escaped from the bio wing three days ago",
         "The ferry went out three days ago and nobody has seen it"),
        ("Tamamo is Kaa Sama's real name",
         "The receipt in the coat has a name on it that isn't yours"),
        ("health-board inspector",
         "The inspector's boat came in on the morning tide"),
    ])
    def test_a_head_marks_a_claim_only_where_the_claim_says_it_whole(
            self, temp_db, learns, said):
        """What the encoder writes down is "a name, a title, or a short
        descriptor" by its own card, and play.db holds whole clauses too:
        each `learns` here is one a play.db chat left unheld. Read by its
        last word or its last two, it marked a claim that does not name
        anybody -- "days ago", "name", "inspector" -- and put it first
        (review RP2-N1: of the 43 heads play.db's introductions leave
        unheld, 16 are a person's name alone and 13 whole clauses)."""
        cid = _story(temp_db, hester=[_claim("claim:00000000000000a1", said,
                                             turn=19)], player=[])
        _introduced(temp_db, cid, 19, learns)

        assert "unheld_names" not in _rows(cid)[0][0]

    def test_a_part_of_a_name_is_not_the_name_said(self, temp_db):
        """"Elver" alone is the planted-name floor's to read
        (`room_sketch._claimed`, where the name is one a model chose); here
        the head is whatever the encoder wrote, and a part of it is not it.
        Said whole, the same man is marked."""
        cid = _story(temp_db, hester=[
            _claim("claim:00000000000000a2", "Elver's coat is on the stake "
                   "past the third post", turn=19),
            _claim("claim:9aabf4bc92fa614e", TAM, turn=18)], player=[])
        _introduced(temp_db, cid, 19, TAM_INTRO)

        rows, _total = _rows(cid)

        assert [(r["said"], r.get("unheld_names")) for r in rows] == [
            (TAM, ["Tam Elver"]),
            ("Elver's coat is on the stake past the third post", None)]

    def test_a_name_said_without_its_article_is_said_whole(self, temp_db):
        """"The Doctor" is said "Doctor" (`commit_common._address_forms`'s
        article): the name whole, its article aside."""
        cid = _story(temp_db, hester=[_claim(
            "claim:00000000000000a3", "Doctor says the fever will break by "
            "morning", turn=19)], player=[])
        _introduced(temp_db, cid, 19, "The Doctor")

        assert _rows(cid)[0][0]["unheld_names"] == ["The Doctor"]


# ---------------------------------------------------------------------------
# The player's own claims follow the player's authority (review RP-6)
# ---------------------------------------------------------------------------

class TestThePlayersOwnClaimsFollowTheirAuthority:
    """The owner, 2026-10-09: what the world does with a player's assertion
    belongs to the authority settings. Making real a person the player's
    character only said exists grants that assertion, so the Room is shown
    the player's own claims only where the story grants the player the world
    (`scene.PLAYER_AUTHORITY_GRANTS`) -- the default, `world_author`, does."""

    BLUFF = _claim("claim:00000000000000f1", "My cousin keeps the sluice at "
                   "the mill and saw the barge go by", turn=21)

    def _story(self, db, mode=None):
        from story.scene import set_player_authority
        cid = _story(db, player=[self.BLUFF, _claim(
            "claim:9aabf4bc92fa614e", TAM_HEARD, turn=19, provenance="told",
            told_by="Hester Gale", retellings=1)])
        if mode is not None:
            set_player_authority(cid, mode, turn_idx=19)
        return cid

    def test_under_world_author_the_players_own_claim_rides(self, temp_db):
        cid = self._story(temp_db)
        rows, total = _rows(cid)
        assert {r["said"] for r in rows} == {self.BLUFF["claim"], TAM}
        assert total == 2
        assert next(r for r in rows if r["said"] == self.BLUFF["claim"])[
            "by"] == PLAYER

    @pytest.mark.parametrize("mode", ["actor_only", "explicit_outcomes"])
    def test_a_stricter_mode_leaves_it_out_uncounted(self, temp_db, mode):
        cid = self._story(temp_db, mode)
        rows, total = _rows(cid)
        assert [r["said"] for r in rows] == [TAM]
        assert total == 1

    @pytest.mark.parametrize("mode", ["actor_only", "explicit_outcomes"])
    def test_a_claim_the_player_only_carries_rides_in_every_mode(
            self, temp_db, mode):
        """What Hester made up and told the player is Hester's claim, the
        player carrying it into reach -- not the player's assertion."""
        cid = self._story(temp_db, mode)
        assert [r["by"] for r in _rows(cid)[0]] == ["Hester Gale"]

    def test_a_maker_known_only_by_the_first_telling_is_read_the_same_way(
            self, temp_db):
        """The player's own row gone, Hester's copy says the player told
        her first-hand: still the player's assertion."""
        from story.scene import set_player_authority
        cid = _story(temp_db, player=[], hester=[_claim(
            "claim:00000000000000f2", "My cousin keeps the sluice", turn=21,
            provenance="told", told_by=PLAYER, retellings=1)])
        assert [r["by"] for r in _rows(cid)[0]] == [PLAYER]
        set_player_authority(cid, "actor_only", turn_idx=21)
        assert _rows(cid) == ([], 0)


# ---------------------------------------------------------------------------
# A sketch hands a claimed person on (review RP-3)
# ---------------------------------------------------------------------------

PLANTING = ("identity_fills", "plan_rooms", "plan_entity", "create_people")


class _Sketch:
    def __init__(self, answer):
        self.answer = answer
        self.payloads = []

    def __call__(self, role, system, user, **kw):
        self.payloads.append(json.loads(user))
        return json.dumps(self.answer)


class TestASketchHandsAClaimedPersonOn:
    """The sketch's person is a name, a role, a room and a look: it can tie
    nobody to anybody, and it reads no plan's truths. Measured (story 166,
    checkpoint 24): one of two sketch samples planted Tam Elver as "the
    Corvina's missing hand", a stranger to the two Gales who know him and
    against the Room's own published truth. So a person a claim names is
    the full planner's: the card asks the sketch to hand them on, and when a
    model plants one anyway code lands nothing and hands the question on,
    with the reason, as it does every refusal."""

    def _run(self, db, monkeypatch, people):
        from story import mandates as md
        from story import room_sketch
        cid = _story(db)
        md.grant_mandate(cid, None, text="Plan ahead of me.",
                         capabilities=list(PLANTING))
        model = _Sketch({"people": people, "title": "Along the walk",
                         "reply": "Someone along the walk."})
        monkeypatch.setattr(providers, "chat_complete", model)
        out = room_sketch.run_sketch(
            cid, None, rf.frontier_report(cid, None), role=sp.PLANNER_ROLE,
            actor=sp.PLANNER_ACTOR, turn_idx=19)
        return cid, model, out

    def _published(self, cid):
        from story.plot_packages import list_packages
        return [p for p in list_packages(cid) if p["status"] == "published"]

    def test_a_sketch_that_plants_a_claimed_person_files_nothing_and_escalates(
            self, temp_db, monkeypatch):
        cid, model, out = self._run(temp_db, monkeypatch, [
            {"name": "Tam Elver", "role": "the Corvina's missing hand",
             "where": "landing_stage"},
            {"name": "Worena Sedgecroft", "role": "net-mender",
             "where": "low_walk"}])

        assert model.payloads[0]["unbacked_claims"][0]["said"] == TAM
        assert out["published"] == []
        assert "'Tam Elver' is a person named in what people near the story " \
               "claim" in out["escalate"]
        assert self._published(cid) == []

    def test_the_name_is_read_as_it_is_said(self, temp_db, monkeypatch):
        """"Elver" alone is the man the claim named."""
        _cid, _model, out = self._run(temp_db, monkeypatch, [
            {"name": "Elver", "role": "tallyman", "where": "landing_stage"}])
        assert "'Elver' is a person named in what people near the story " \
               "claim" in out["escalate"]

    def test_a_person_no_claim_names_is_planted_as_before(
            self, temp_db, monkeypatch):
        cid, _model, out = self._run(temp_db, monkeypatch, [
            {"name": "Worena Sedgecroft", "role": "net-mender",
             "where": "low_walk"}])
        assert out["escalate"] == ""
        assert len(out["published"]) == 1
        assert len(self._published(cid)) == 1


# ---------------------------------------------------------------------------
# The cards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_both_cards_say_what_code_knows_and_who_may_plant(language):
    """Both say what each row is, and that "unheld_names" names what nobody
    the world holds answers to; the full planner may plan a claimed person
    with `plan_entity` and tie them with `known_by`; the sketch hands one on
    with "escalate" and no longer plants one "whether or not people are
    short" (review RP-3)."""
    planner = get_prompt("story_planner", language)
    sketch = get_prompt("room_sketch", language)
    for card in (planner, sketch):
        for token in ('"unbacked_claims"', '"said"', '"by"', '"heard_by"',
                      '"unheld_names"'):
            assert token in card, (language, token)
    assert "`plan_entity`" in planner and "`known_by`" in planner
    assert '"escalate"' in sketch
    assert "whether or not people are short" not in sketch
    assert "人物が足りているかどうかは問いません" not in sketch


@pytest.mark.parametrize("language, words", [
    ("en", "never whether something a character said is true or only a claim"),
    ("en", "never says whether something a character said is true or only a "
           "claim unless the player asked"),
    ("ja", "プレイヤーが尋ねない限り決して言いません")])
def test_a_reply_never_says_whether_a_characters_words_are_true(language,
                                                                  words):
    """The room's thread is the player's to read: a fill's reply names what
    was planted, and never whether something a character said is true or
    only a claim unless the player asked (review RP-5: a sketch reply told
    the investigator, unasked, that the man the whole story turns on did not
    exist)."""
    cards = get_prompt("story_planner", language) + get_prompt(
        "room_sketch", language)
    assert words in cards


@pytest.mark.parametrize("language, names_it, yields, stop", [
    ("en", "Your reply names what you planted",
     "spoiler-safe where its package is sealed", "."),
    ("ja", "あなたの返答は何を植えたかを",
     "封印されたパッケージならネタバレを避けて", "。")])
def test_naming_what_was_planted_yields_to_a_sealed_package(
        language, names_it, yields, stop):
    """The full planner's reply names what it planted -- and SPOILERS, the
    paragraph after, holds everything said of a sealed package to "something
    is in motion, never what it is". Said with no condition, the first told
    a fill that plants a claimed person inside a package the player asked to
    have sealed to name them anyway (review RP5-N1). The sketch's packages
    are never sealed, so its card has no such sentence to yield."""
    card = get_prompt("story_planner", language)
    sentence = card[card.index(names_it):]
    sentence = sentence[:sentence.index(stop) + 1]
    assert yields in sentence, (language, sentence)
