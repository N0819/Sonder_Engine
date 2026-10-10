"""A person the Writers' Room planned is promoted on the player's engagement,
and automatic promotion stays the host's setting.

The owner's ruling on the Brackwater run's D7 (F102), 2026-10-09: promote a
Room-planned person the player keeps engaging -- "Yes but automatic should
remain a setting".

What the run measured (scratch story 166). Abel Gale was planned by the Room
before the story began -- Hester's younger brother, the Corvina's only hand,
behind on a loan to Selwick -- and was the story's centre. When the player
came to his door he was a tracked presence like any passer-by, voiced by the
stateless background reactor one line a beat, and nothing would give him a
mind: at the beat a human promoted him by hand (idx 24) his record read two
beats of the story deliberately turning to him and ONE line spoken, under a
passer-by's bars of two lines for the offer and three for the automatic
sweep -- bars that exist to tell an extra who has become somebody from one
who talked twice, a question the Room's plan had already answered. And when
he was promoted, the sheet's author was never shown that plan: the card
lost "bargeman", "younger" and the loan to Selwick, and gave the body the
story had shown with one milky eye a pair of "red-rimmed, dark" ones.

Five claims, one class each:

* THE OFFER: a planned person is offered once the story has deliberately
  turned to them on the chat's planned bar (`promotion_thresholds`'
  "planned", default `PLANNED_PROMOTION_ADDRESSED_THRESHOLD`), and the
  offer reaches the host's panel, the turn's warnings and the Director as a
  passer-by's does. A passer-by with the same record still waits.
* THE SWEEP: automatic promotion of a planned person waits on the same
  engagement rule -- the host's own dial, `promote_after_addressed` -- and
  on nothing a passer-by's voice is measured by; the global `auto_promote`
  switch still governs it, OFF by default, and the dial at 0 still means
  never.
* THE DRAFT: the sheet's author is handed what of the plan the person
  lives and others see -- their work, their home, their look, who has known
  them from before -- and the body the story showed; the seed call, whose
  output becomes first-person witnessed memory, is handed neither.
* THE FLOOR: a plan's truths and purpose -- facts about the world and the
  Room's intent -- never reach the author at all, because the sheet is what
  the promoted mind reads every beat.
* THE CARD: both packs say what "plan" and "seen" are, and name nothing the
  code withholds; each plan field is described in the person's own world's
  words, because a description is what a model writes back into the field
  (review RP1-N1).
"""
from __future__ import annotations

import json
import re
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.prompts import get_prompt
from persist.commit import (
    PLANNED_PROMOTION_ADDRESSED_THRESHOLD,
    _propose_promotions,
    promotable_background_presences,
    promotion_thresholds,
    select_auto_promotion,
)
from story import importers
from world.planned_entities import add_planned_entity

PLAYER = "Tamsin Coyle"
KEY = "p_0e517d30fb54c85a"
SEEN = ("A narrow-faced man, weathered to the colour of old rope, one eye "
        "milky and fixed, the other sharp and dark.")
PLAN = {
    "kind": "person", "name": "Abel Gale", "role": "bargeman",
    "brief": {
        "purpose": "Hester Gale's younger brother, the Corvina's only hand "
                   "the night she sank",
        "truths": "He lives with his sister in the Gale house; his own boat "
                  "is behind on a loan to Selwick at the counting house.",
        "where": "gale_house",
        "station": "sitting at the stove, his boots drying beside it",
    },
    "look": "A big, raw-boned man in his middle twenties.",
    "known_by": ["Hester Gale"],
}


def _chat(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Brackwater", "A drowned barge.", time.time()))
    db.wset(cid, "scene", {
        "location": "Brackwater",
        "rooms": {"gale_house": {"name": "The Gale house"},
                  "landing": {"name": "The Gale house landing"}},
        "positions": {PLAYER: "landing", "abel_gale": "gale_house"},
        "entities": {"abel_gale": {
            "name": "Abel Gale", "kind": "person", "description": SEEN,
            "aliases": ["Abel"]}},
    })
    return cid


def _plan(db, cid, **override):
    plan = add_planned_entity(cid, dict(PLAN, **override))
    scene = db.wget(cid, "scene", {})
    scene["entities"]["abel_gale"]["plan_ref"] = {"uid": plan["uid"]}
    db.wset(cid, "scene", scene)
    return plan["uid"]


def _record(plan_uid=None, *, dialogue=(24,), addressed=(23, 24), last=24):
    rec = {"uid": KEY, "entity_id": "abel_gale", "name": "Abel Gale",
           "first_turn": 23, "last_turn": last,
           "dialogue_turns": list(dialogue), "mention_turns": [],
           "addressed_turns": list(addressed),
           "sketch": {"role_hint": SEEN[:60], "station_room": "gale_house"}}
    if plan_uid:
        rec["plan_ref"] = plan_uid
    return rec


def _seed(db, cid, record, **others):
    db.wset(cid, "background_presences", {KEY: record, **others})


def _ctx(cid, idx, text="Mr Gale. Tamsin Coyle, River Underwriters."):
    return PipelineContext(
        chat=ChatData(id=cid, name="Brackwater", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=idx + 1, chat_id=cid, idx=idx, player_input=text,
                      created=time.time()),
        cast=[], input=text)


def _row(cid):
    return next(r for r in promotable_background_presences(cid)
                if r["id"] == KEY)


def _automatic(db, cid, *, after=2, on=True):
    db.set_setting("auto_promote", "1" if on else "0")
    db.wset(cid, "dialogue_config", {"promote_after_addressed": after})


class TestTheOffer:
    def test_a_planned_person_the_story_turned_to_on_two_beats_is_offered(
            self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))

        row = _row(cid)

        assert row["promotable"] is True
        assert row["planned"] is True

    def test_the_bar_is_named_and_is_the_passer_bys_offer_bar(self, temp_db):
        cid = _chat(temp_db)
        assert promotion_thresholds(cid)["planned"] \
            == PLANNED_PROMOTION_ADDRESSED_THRESHOLD == 2

    def test_the_same_record_with_no_plan_is_a_passer_by_and_waits(
            self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(None))

        row = _row(cid)

        assert row["promotable"] is False
        assert row["planned"] is False

    def test_a_plan_for_a_thing_makes_nobody_a_planned_person(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid, kind="thing")))

        assert _row(cid)["promotable"] is False

    def test_turned_to_once_is_not_yet(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid), addressed=(24,)))

        assert _row(cid)["promotable"] is False

    def test_the_chat_may_raise_the_planned_bar(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        temp_db.wset(cid, "promotion_thresholds", {"planned": 3})

        assert _row(cid)["promotable"] is False

    def test_the_offer_reaches_the_director_and_the_turns_warnings(
            self, temp_db):
        """The panel's button reads `promotable`; the MOMENT is surfaced the
        way a passer-by's is, once, so the host sees it on the beat and the
        Director knows `cast_changes` attaches nobody."""
        cid = _chat(temp_db)
        record = _record(_plan(temp_db, cid))
        ctx = _ctx(cid, 24)

        proposed = _propose_promotions(ctx, {KEY: record},
                                       temp_db.wget(cid, "scene", {}))

        assert proposed == ["Abel Gale"]
        assert record["promotion_proposed_turn"] == 24
        assert any("Abel Gale" in m for m in ctx.engine_feedback)
        assert any(w.startswith("promotion proposed") and "Abel Gale" in w
                   for w in ctx.warnings)
        # ...and the reason is legible: the Room planned this person.
        assert any("Writers' Room" in m for m in ctx.engine_feedback)


class TestTheSweep:
    def test_automatic_promotion_waits_on_the_hosts_engagement_rule_alone(
            self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        _automatic(temp_db, cid, after=2)

        assert select_auto_promotion(_ctx(cid, 24)) == (KEY, "Abel Gale")

    def test_automatic_stays_the_hosts_setting(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        _automatic(temp_db, cid, after=2, on=False)

        assert select_auto_promotion(_ctx(cid, 24)) == (None, "")
        # ...and with the switch off he is still offered to the host.
        assert _row(cid)["promotable"] is True

    def test_an_unset_switch_is_off(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        temp_db.wset(cid, "dialogue_config", {"promote_after_addressed": 2})

        assert select_auto_promotion(_ctx(cid, 24)) == (None, "")

    def test_the_dial_at_zero_still_means_never(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        _automatic(temp_db, cid, after=0)

        assert select_auto_promotion(_ctx(cid, 24)) == (None, "")

    def test_below_the_hosts_dial_he_waits(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        _automatic(temp_db, cid, after=3)

        assert select_auto_promotion(_ctx(cid, 24)) == (None, "")

    def test_not_present_this_beat_he_waits(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid), last=24))
        _automatic(temp_db, cid, after=2)

        assert select_auto_promotion(_ctx(cid, 27, "A quiet beat.")) \
            == (None, "")

    def test_a_passer_by_with_his_record_still_needs_the_voice_bar(
            self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(None, dialogue=(23, 24)))
        _automatic(temp_db, cid, after=2)

        assert select_auto_promotion(_ctx(cid, 24)) == (None, "")

    def test_the_planned_person_is_drafted_before_a_chattier_passer_by(
            self, temp_db):
        """One promotion a beat, because each mints a sheet with a model
        call; the one the story is about goes first."""
        cid = _chat(temp_db)
        uid = _plan(temp_db, cid)
        _seed(temp_db, cid, _record(uid), p_00000000000000aa={
            "uid": "p_00000000000000aa", "name": "Colynon Saltowford",
            "first_turn": 6, "last_turn": 24,
            "dialogue_turns": [6, 7, 8, 9, 24], "mention_turns": [],
            "addressed_turns": [7, 9, 24]})
        _automatic(temp_db, cid, after=2)

        assert select_auto_promotion(_ctx(cid, 24)) == (KEY, "Abel Gale")


def _event(db, cid, idx, text, lines=()):
    turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,?,?,?)", (cid, idx, "x", time.time()))
    db.qi("INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
          (cid, turn_id, json.dumps({
              "turn": idx, "summary": "", "event": text,
              "dialogue_log": list(lines)})))


class _Model:
    """The two promotion calls, kept: the sheet call first, the seed call
    second (`importers.draft_promoted_character`)."""

    def __init__(self):
        self.payloads = []

    def __call__(self, role, system, user, **kw):
        self.payloads.append(json.loads(user))
        return json.dumps({
            "sheet": {"identity": {"name": "Abel Gale"},
                      "opening": {"first_message": ""}},
            "memory_seeds": ["I told her there was no other man aboard."]})


class TestTheDraft:
    def test_the_sheet_is_written_from_the_plan_and_the_body_the_story_showed(
            self, temp_db, monkeypatch):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        _event(temp_db, cid, 24, "Abel looks back from the chair.", [{
            "speaker": "Abel Gale", "exact_quote": "There was no other man "
            "aboard.", "tone": "raw and quick"}])
        model = _Model()
        monkeypatch.setattr(importers, "chat_complete", model)

        importers.draft_promoted_character(cid, KEY)

        sheet_pack, seed_pack = model.payloads
        plan = sheet_pack["plan"]
        assert plan == {"role": "bargeman", "home": "The Gale house",
                        "look": PLAN["look"], "known_by": ["Hester Gale"]}
        assert sheet_pack["seen"] == SEEN
        # THE SEEDS STAY SUBTRACTED: what they are made from becomes
        # first-person witnessed memory, and a plan is the author's, never
        # something this man saw.
        assert "plan" not in seed_pack and "seen" not in seed_pack
        assert all("resolved_event" not in e for e in seed_pack["evidence"])

    def test_the_sweeps_own_draft_finds_the_plan_by_his_name(
            self, temp_db, monkeypatch):
        """The out-of-band job drafts under the display name, not the key
        (`commit_background.schedule_auto_promotion`'s `_produce`)."""
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        _event(temp_db, cid, 24, "Abel looks back from the chair.", [{
            "speaker": "Abel Gale", "exact_quote": "There was no other man "
            "aboard.", "tone": "raw and quick"}])
        model = _Model()
        monkeypatch.setattr(importers, "chat_complete", model)

        importers.draft_promoted_character(cid, "Abel Gale")

        assert model.payloads[0]["plan"]["role"] == "bargeman"

    def test_a_passer_by_is_drafted_as_before_with_the_body_it_showed(
            self, temp_db, monkeypatch):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(None))
        _event(temp_db, cid, 24, "Abel looks back from the chair.", [{
            "speaker": "Abel Gale", "exact_quote": "Who's there?",
            "tone": "low"}])
        model = _Model()
        monkeypatch.setattr(importers, "chat_complete", model)

        importers.draft_promoted_character(cid, KEY)

        assert "plan" not in model.payloads[0]
        assert model.payloads[0]["seen"] == SEEN

    def test_a_planned_person_with_no_recorded_turn_is_drafted_from_the_plan(
            self, temp_db, monkeypatch):
        """A plan is a brief: a person turned to twice whose words no event
        recorded still has a life to write the sheet from, where a passer-by
        with no record has nothing and is refused."""
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(_plan(temp_db, cid)))
        model = _Model()
        monkeypatch.setattr(importers, "chat_complete", model)

        draft = importers.draft_promoted_character(cid, KEY)

        assert draft["sheet"]["identity"]["name"] == "Abel Gale"
        assert len(model.payloads) == 1          # nothing to seed a memory from
        assert model.payloads[0]["evidence"] == []

    def test_a_passer_by_with_no_record_is_still_refused(self, temp_db):
        cid = _chat(temp_db)
        _seed(temp_db, cid, _record(None))
        with pytest.raises(ValueError):
            importers.draft_promoted_character(cid, KEY)


class TestAPlanTruthIsNeverPlacedInTheirHead:
    """The firewall floor under the draft (review RP-1, 2026-10-10).

    A plan's `truths` are facts about the WORLD and its `purpose` the Room's
    intent, written under the Room's own card's promise that nothing it
    writes is placed in anybody's head. The sheet is what the promoted mind
    reads every beat (`scene.private_knowledge_for` hands an owner each entry
    of its own private history), so what reaches the sheet's author reaches
    that head -- with nobody reviewing it once the automatic sweep lands the
    draft. Probed in review on the card that asked the model to keep them
    straight: a laundress planned as the late baron's daughter, "never
    told", came back holding it as her own private history. So the author
    is never handed them at all, whatever any card says.

    Regression guards against c3c71ffe, where no plan reached the draft;
    each FAILS on the first build of D7, which handed the author the whole
    brief.
    """

    SECRET = ("She is the late baron's legitimate daughter, left at the "
              "wash-house as an infant; she has never been told, and only "
              "the midwife Orla Penn knows.")
    INTENT = "the foundling the reckoning turns on"

    def _laundress(self, db, *, evidence_says=None):
        cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("Millbrook", "A mill under a claim.", time.time()))
        db.wset(cid, "scene", {
            "location": "Millbrook",
            "rooms": {"wash_house": {"name": "The wash-house"}},
            "positions": {PLAYER: "wash_house", "wenna_rook": "wash_house"},
            "entities": {"wenna_rook": {
                "name": "Wenna Rook", "kind": "person",
                "description": "A broad-armed young woman with red, cracked "
                               "hands and copper hair."}}})
        plan = add_planned_entity(cid, {
            "kind": "person", "name": "Wenna Rook", "role": "laundress",
            "brief": {"purpose": self.INTENT, "truths": self.SECRET,
                      "where": "wash_house",
                      "station": "wringing sheets over the copper"},
            "look": "A broad-armed young woman with a shock of copper hair.",
            "known_by": ["Orla Penn", "player"]})
        scene = db.wget(cid, "scene", {})
        scene["entities"]["wenna_rook"]["plan_ref"] = {"uid": plan["uid"]}
        db.wset(cid, "scene", scene)
        pid = db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                    (PLAYER, json.dumps({"identity": {"name": PLAYER}})))
        db.qi("UPDATE chats SET persona_id=? WHERE id=?", (pid, cid))
        db.wset(cid, "background_presences", {"p_00000000000000ee": {
            "uid": "p_00000000000000ee", "entity_id": "wenna_rook",
            "name": "Wenna Rook", "plan_ref": plan["uid"],
            "first_turn": 4, "last_turn": 5, "dialogue_turns": [5],
            "mention_turns": [], "addressed_turns": [4, 5]}})
        _event(db, cid, 5, evidence_says or (
            "At the wash-house a broad-armed laundress wrings sheets over "
            "the copper and tells the visitor to mind the tub."), [{
                "speaker": "Wenna Rook",
                "exact_quote": "Sheets don't wash themselves. Mind the tub.",
                "tone": "brisk"}])
        return cid

    def test_a_plan_truth_the_evidence_does_not_show_never_reaches_the_sheet(
            self, temp_db, monkeypatch):
        cid = self._laundress(temp_db)
        model = _Model()
        monkeypatch.setattr(importers, "chat_complete", model)

        importers.draft_promoted_character(cid, "p_00000000000000ee")

        sent = json.dumps(model.payloads, ensure_ascii=False)
        for words in ("baron", "legitimate daughter", "never been told",
                      "reckoning", "foundling", "wringing sheets over"):
            assert words not in sent, words

    def test_the_author_is_handed_what_she_lives_and_others_see_and_nothing_else(
            self, temp_db, monkeypatch):
        """`known_by`'s word for the player's own character arrives as the
        player's name: a sheet copies what it is handed."""
        cid = self._laundress(temp_db)
        model = _Model()
        monkeypatch.setattr(importers, "chat_complete", model)

        importers.draft_promoted_character(cid, "p_00000000000000ee")

        plan = model.payloads[0]["plan"]
        assert set(plan) <= set(importers.PLAN_FIELDS_FOR_SHEET)
        assert importers.PLAN_FIELDS_FOR_SHEET == (
            "role", "home", "look", "known_by")
        assert plan == {
            "role": "laundress", "home": "The wash-house",
            "look": "A broad-armed young woman with a shock of copper hair.",
            "known_by": ["Orla Penn", PLAYER]}

    def test_what_the_story_itself_showed_still_reaches_it(
            self, temp_db, monkeypatch):
        """The floor withholds the PLAN's truths, never the record: a truth
        the story put on the page is evidence, and evidence is canon."""
        cid = self._laundress(
            temp_db, evidence_says="Orla Penn tells the laundress, before the "
            "visitor, that she is the late baron's legitimate daughter.")
        model = _Model()
        monkeypatch.setattr(importers, "chat_complete", model)

        importers.draft_promoted_character(cid, "p_00000000000000ee")

        assert "legitimate daughter" in json.dumps(
            model.payloads[0]["evidence"], ensure_ascii=False)
        assert "legitimate daughter" not in json.dumps(
            model.payloads[0]["plan"], ensure_ascii=False)


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_promotion_card_says_what_the_plan_and_the_seen_body_are(language):
    """The card names what code hands the author -- each plan field and the
    body seen -- and nothing code withholds from it."""
    card = get_prompt("promote_character", language)
    for token in ('"plan"', '"seen"', *('"%s"' % field for field in
                                         importers.PLAN_FIELDS_FOR_SHEET)):
        assert token in card, (language, token)
    for withheld in ('"truths"', '"purpose"', '"station"'):
        assert withheld not in card, (language, withheld)
    assert "knowledge.public_history" in card


#: The words this request uses for itself -- what the card calls the story,
#: its author, the plan, the scene, the evidence and a turn. Not a list a
#: card matches against: the test's closed set of the request's OWN
#: vocabulary, which a field's description must not hand the sheet. English
#: is read from a word's start ("planned" is the plan's, "return" is not a
#: turn); Japanese, which writes no spaces, anywhere.
_THE_REQUESTS_OWN_WORDS = {
    "en": ("story", "stories", "author", "plan", "scene", "evidence", "turn"),
    "ja": ("物語", "作者", "計画", "シーン", "証拠", "ターン"),
}


def _says_its_own_word(language, text):
    words = _THE_REQUESTS_OWN_WORDS[language]
    if language == "ja":
        return [w for w in words if w in text]
    return [w for w in words if re.search(r"\b" + w, text.casefold())]


@pytest.mark.parametrize("language", ["en", "ja"])
def test_what_the_plan_says_of_them_is_put_in_their_own_worlds_words(language):
    """A field's description is the phrase a model writes back into the
    field: "who has known them since before the story began" came back as
    "Known to Hester from before the story began." in the promoted bargeman's
    own public history, which his mind reads every beat (review RP1-N1:
    one of two replayed drafts of Abel Gale, story 166). So each plan field
    is described as the person's own world would say it, and none in the
    words the request uses for itself."""
    card = get_prompt("promote_character", language)
    paragraph = next(p for p in card.split("\n\n") if '"plan"' in p)
    ends = [paragraph.index('"%s"' % field)
            for field in importers.PLAN_FIELDS_FOR_SHEET]
    begin = max(paragraph.rfind(":", 0, ends[0]),
                paragraph.rfind("：", 0, ends[0]))
    assert begin >= 0, language
    for field, start, end in zip(importers.PLAN_FIELDS_FOR_SHEET,
                                 [begin, *ends[:-1]], ends):
        described = paragraph[start:end]
        assert not _says_its_own_word(language, described), (
            language, field, described)
