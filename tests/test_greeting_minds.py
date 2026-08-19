"""A quick-start greeting seeds whole minds, not one person's list of facts.

The corpus read that shaped this (docs/design/DESIGN_GREETING_MINDS.md):
nearly every live greeting establishes an emotional state at the opening
moment, most establish a stance toward the player, several establish beliefs
-- including deliberately false ones -- and some put additional people in
the room. `GreetingInterpret.minds` records all of it per person;
`start_story` routes each channel to the store the runtime already revises;
what cannot be seeded is refused visibly in the chat's `greeting_minds`
record rather than dropped in silence.
"""

from __future__ import annotations

import json

import pytest

from story import importers


@pytest.fixture(autouse=True)
def _no_ai(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("AI must not be called for heuristic imports")
    monkeypatch.setattr(importers, "chat_complete", fail)
    yield


def _card():
    return {
        "name": "Dr. Moon",
        "first_mes": "The hallway is quiet. {{user}} steps inside.",
    }


def _launch(monkeypatch, extraction, *, already_known=True,
            persona=None):
    from story import greetings
    monkeypatch.setattr(greetings, "extract_greeting",
                        lambda sheet, prose: dict(extraction))
    monkeypatch.setattr(greetings, "_run_pipeline",
                        lambda cid, tid: iter(()))
    cid_char, _ = importers.import_character(_card(), reinterpret=False)
    pid, _ = importers.import_persona(persona or {"name": "Dana"},
                                      reinterpret=False)
    chat_id, tid = greetings.start_story(cid_char, pid, greeting_index=0,
                                         already_known=already_known)
    return chat_id, cid_char


def _char_state(chat_id, char_id):
    from core.db import q
    row = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, char_id), one=True)
    return json.loads(row["state"] or "{}")


def _mind(**over):
    mind = {"who": "Dr. Moon", "knowledge_seeds": [], "beliefs": [],
            "stances": [], "affect": None}
    mind.update(over)
    return mind


def _extraction(*minds):
    return {"time": "now", "knowledge_seeds": [], "minds": list(minds)}


# ---- Schema bounds ----

class TestSchemaBounds:
    def test_belief_confidence_is_capped_below_certainty(self):
        from llm.schemas import GreetingBeliefSeed
        assert GreetingBeliefSeed(belief="x", confidence=1.0).confidence == 0.85
        assert GreetingBeliefSeed(belief="x", confidence=0.5).confidence == 0.5
        assert GreetingBeliefSeed(belief="x", confidence="nope").confidence == 0.5

    def test_stance_axes_are_clamped(self):
        from llm.schemas import GreetingStanceSeed
        s = GreetingStanceSeed(toward="x", trust=5.0, warmth=-5.0, fear="bad")
        assert s.trust == 1.0 and s.warmth == -1.0 and s.fear == 0.0

    def test_affect_axes_are_clamped(self):
        from llm.schemas import GreetingAffectSeed
        a = GreetingAffectSeed(label="fear", valence=-3.0, arousal=3.0)
        assert a.valence == -1.0 and a.arousal == 1.0

    def test_interpret_carries_minds_and_legacy_seeds(self):
        from llm.schemas import GreetingInterpret
        out = GreetingInterpret(
            minds=[{"who": "A", "beliefs": [{"belief": "x"}]}],
            knowledge_seeds=[{"content": "y"}])
        assert out.minds[0].who == "A"
        assert out.knowledge_seeds[0].content == "y"

    def test_extraction_with_no_minds_is_a_semantic_error(self):
        """The silent-empty failure, caught at extraction time: a greeting
        always contains at least its own character's mind."""
        from llm.schemas import semantic_output_errors
        assert semantic_output_errors("greeting_interpret",
                                      {"time": "now", "minds": []})
        assert not semantic_output_errors(
            "greeting_interpret",
            {"time": "now", "minds": [{"who": "A"}]})


# ---- The deterministic guard at extraction ----

class TestExtractionGuard:
    def test_player_naming_seed_is_forced_revealed_in_every_mind(self,
                                                                 monkeypatch):
        """Knowledge about the player's own conduct cannot be asymmetric
        against the player -- the existing top-level guard, now applied to
        per-mind seeds too."""
        from story import greetings
        raw = {
            "time": "now",
            "knowledge_seeds": [],
            "minds": [
                _mind(knowledge_seeds=[
                    {"content": "I watched {{PLAYER}} cross the bridge.",
                     "revealed_in_prose": False},
                    {"content": "I hid the ledger under the floor.",
                     "revealed_in_prose": False},
                ]),
            ],
        }
        monkeypatch.setattr(greetings, "complete_validated_json",
                            lambda **k: json.loads(json.dumps(raw)))
        monkeypatch.setattr(greetings, "get_prompt", lambda pid: "p")
        out = greetings.extract_greeting({"identity": {"name": "A"}}, "prose")
        seeds = out["minds"][0]["knowledge_seeds"]
        assert seeds[0]["revealed_in_prose"] is True
        assert seeds[1]["revealed_in_prose"] is False


# ---- Routing: the card character's mind ----

class TestCharacterMindRouting:
    def test_per_mind_seeds_reach_the_characters_memory(self, temp_db,
                                                        monkeypatch):
        from core.db import q
        chat_id, _cid = _launch(monkeypatch, _extraction(
            _mind(knowledge_seeds=[
                {"content": "I have been waiting three nights for a courier.",
                 "salience": 1.0, "revealed_in_prose": False}])))
        rows = q("SELECT content, salience FROM memories WHERE chat_id=?",
                 (chat_id,))
        assert len(rows) == 1
        # The salience ceiling holds on the per-mind path too: raw stored
        # dicts bypass the schema, so the write is the boundary.
        assert rows[0]["salience"] <= 0.7

    def test_world_beliefs_land_in_the_interior_ledger(self, temp_db,
                                                       monkeypatch):
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(beliefs=[
                {"belief": "The east lock froze shut two days ago.",
                 "about_entity": "world", "confidence": 0.95,
                 "protected": False}])))
        beliefs = _char_state(chat_id, cid)["interior"]["beliefs"]
        assert len(beliefs) == 1
        entry = beliefs[0]
        assert entry["belief"] == "The east lock froze shut two days ago."
        # Capped at the write, not just the schema: 0.95 arrived raw.
        assert entry["confidence"] <= 0.85
        assert entry["source"] == "greeting"
        assert not entry.get("authored"), \
            "a greeting seed must evict before sheet-authored beliefs, " \
            "never claim their re-seed protection"

    def test_protected_beliefs_are_convictions_and_capped_at_two(
            self, temp_db, monkeypatch):
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(beliefs=[
                {"belief": f"conviction {i}", "about_entity": "self",
                 "confidence": 0.6, "protected": True}
                for i in range(4)])))
        beliefs = _char_state(chat_id, cid)["interior"]["beliefs"]
        assert [b["belief"] for b in beliefs if b.get("protected")] == \
            ["conviction 0", "conviction 1"]
        # The overflow is demoted, not dropped: the mind still holds it.
        assert len(beliefs) == 4

    def test_beliefs_about_the_player_route_through_theory_of_mind(
            self, temp_db, monkeypatch):
        """A belief about another mind is a hypothesis, seeded through the
        same gate play would use -- so an identity claim caps at the ToM
        identity ceiling, not at whatever the greeting asserted."""
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(beliefs=[
                {"belief": "{{PLAYER}} is the courier I was promised.",
                 "about_entity": "{{PLAYER}}", "kind": "identity",
                 "confidence": 0.8}])))
        models = _char_state(chat_id, cid)["mind_models"]
        assert "Dana" in models
        hyp = models["Dana"]["hypotheses"][0]
        assert "Dana" in hyp["claim"]
        assert "{{PLAYER}}" not in hyp["claim"]
        assert hyp["confidence"] <= 0.35 + 1e-9

    def test_identity_floor_holds_for_a_stranger_start(self, temp_db,
                                                       monkeypatch):
        """already_known=False: no string entering the mind may carry the
        persona's name -- claims key and read as the perception-built
        description, exactly like memory seeds."""
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(beliefs=[
                {"belief": "{{PLAYER}} slipped in through the east lock.",
                 "about_entity": "{{PLAYER}}", "kind": "goal",
                 "confidence": 0.5}],
                  stances=[{"toward": "{{PLAYER}}", "trust": -0.4,
                            "because": "{{PLAYER}} arrived unannounced"}])),
            already_known=False)
        st = _char_state(chat_id, cid)
        assert "Dana" not in json.dumps(st)
        from core.db import wget
        graph = wget(chat_id, f"relationships:{cid}", {})
        assert graph and "Dana" not in graph

    def test_stances_seed_the_graph_and_leave_a_ledger_row(self, temp_db,
                                                           monkeypatch):
        from core.db import q, wget
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(stances=[
                {"toward": "{{PLAYER}}", "trust": 0.5, "warmth": 0.6,
                 "fear": 0.0,
                 "because": "weeks of growing close to {{PLAYER}}",
                 "revealed_in_prose": False}])))
        graph = wget(chat_id, f"relationships:{cid}", {})
        rel = graph["Dana"]
        assert rel["trust"] == 0.5
        assert rel["emotional_valence"] == 0.6
        rows = q("SELECT axis, delta, provenance, note FROM relationship_events "
                 "WHERE chat_id=? AND char_id=?", (chat_id, cid))
        assert {(r["axis"], r["delta"]) for r in rows} == \
            {("trust", 0.5), ("warmth", 0.6)}
        assert all(r["provenance"] == "greeting" for r in rows)
        assert all("{{PLAYER}}" not in r["note"] for r in rows)

    def test_affect_overlays_the_surface_and_keeps_the_card_baseline(
            self, temp_db, monkeypatch):
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(affect={"label": "terrified", "valence": -0.8,
                          "arousal": 0.9})))
        active = _char_state(chat_id, cid)["active_state"]
        assert active["affect"]["surface"] == {
            "label": "terrified", "valence": -0.8, "arousal": 0.9}
        # Legacy flat projection tracks the surface.
        assert active["mood"] == "terrified"
        assert active["valence"] == -0.8
        # The baseline stays the card's: the greeting is the moment, the
        # card is the temperament the moment decays back toward.
        assert active["affect"]["baseline"] != {"valence": -0.8,
                                                "arousal": 0.9}

    def test_a_contradicted_label_falls_back_to_the_quadrant(self, temp_db,
                                                             monkeypatch):
        """'cheerful' over negative valence is the lexicon contradiction
        label_matches exists to catch; the numbers win, the label yields."""
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(affect={"label": "cheerful", "valence": -0.6,
                          "arousal": 0.5})))
        surface = _char_state(chat_id, cid)["active_state"]["affect"]["surface"]
        assert surface["label"] == "anxious"

    def test_absent_affect_seeds_nothing(self, temp_db, monkeypatch):
        """Absence is not neutrality: no affect in the extraction means the
        card's authored initial_state stands untouched."""
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(beliefs=[{"belief": "x", "about_entity": "world"}])))
        assert "active_state" not in _char_state(chat_id, cid)


# ---- Routing: the player's mind ----

class TestPlayerMindRouting:
    def test_revealed_player_knowledge_reaches_the_persona_store(
            self, temp_db, monkeypatch):
        from core.db import wget
        chat_id, _cid = _launch(monkeypatch, _extraction(
            _mind(),
            _mind(who="{{PLAYER}}", knowledge_seeds=[
                {"content": "I crossed the pass after dark.",
                 "revealed_in_prose": True}])))
        entries = wget(chat_id, "persona_private_history", None)
        assert entries is not None
        assert any(e["content"] == "I crossed the pass after dark."
                   and e["known_by"] == [] for e in entries)

    def test_unrevealed_player_items_are_refused_and_the_refusal_is_visible(
            self, temp_db, monkeypatch):
        """An implied player-mind item is a model's guess about what the
        player-character knows; routing it to a player-readable surface
        would let the extraction widen the page. Dropped -- and recorded,
        because a silent drop is this subsystem's named failure mode."""
        from core.db import wget
        chat_id, _cid = _launch(monkeypatch, _extraction(
            _mind(),
            _mind(who="{{PLAYER}}", knowledge_seeds=[
                {"content": "The tea is safe to drink.",
                 "revealed_in_prose": False}])))
        entries = wget(chat_id, "persona_private_history", None) or []
        assert all(e.get("content") != "The tea is safe to drink."
                   for e in entries)
        record = wget(chat_id, "greeting_minds", {})
        player = next(m for m in record["minds"].values()
                      if m["resolved"] == "player")
        assert any("unrevealed" in r for r in player["refused"])

    def test_player_affect_and_stance_are_refused(self, temp_db, monkeypatch):
        """The player's mind is the human's; the engine seeds no feeling
        into it, and says so."""
        from core.db import wget
        chat_id, _cid = _launch(monkeypatch, _extraction(
            _mind(),
            _mind(who="{{PLAYER}}",
                  affect={"label": "fear", "valence": -0.5, "arousal": 0.8},
                  stances=[{"toward": "Dr. Moon", "trust": 0.5}])))
        record = wget(chat_id, "greeting_minds", {})
        player = next(m for m in record["minds"].values()
                      if m["resolved"] == "player")
        assert any("player" in r for r in player["refused"])

    def test_authored_persona_private_history_survives_the_seed(
            self, temp_db, monkeypatch):
        from core.db import wget
        chat_id, _cid = _launch(monkeypatch, _extraction(
            _mind(),
            _mind(who="{{PLAYER}}", knowledge_seeds=[
                {"content": "I crossed the pass after dark.",
                 "revealed_in_prose": True}])),
            # Native persona shape: the heuristic import path builds a
            # default sheet and would drop the authored history.
            persona={"identity": {"name": "Dana"}, "narration": {},
                     "knowledge": {"private_history": [
                         {"about": "Dana", "content": "I carry a letter.",
                          "known_by": []}]}})
        entries = wget(chat_id, "persona_private_history", None)
        contents = {e["content"] for e in entries}
        assert "I carry a letter." in contents
        assert "I crossed the pass after dark." in contents


# ---- Routing: everyone else ----

class TestRetainedMinds:
    def test_an_unattached_presence_is_retained_not_seeded(self, temp_db,
                                                           monkeypatch):
        from core.db import q, wget
        chat_id, _cid = _launch(monkeypatch, _extraction(
            _mind(),
            _mind(who="The Porter", knowledge_seeds=[
                {"content": "I signed for {{PLAYER}}'s trunk at noon.",
                 "revealed_in_prose": False}])))
        record = wget(chat_id, "greeting_minds", {})
        porter = record["minds"]["porter"]
        assert porter["claimed"] is False
        assert porter["resolved"] is None
        # Persona-neutral: the token is intact so the claim can substitute
        # with whatever handle is legitimate at claim time.
        assert "{{PLAYER}}" in json.dumps(porter["mind"])
        # And nothing of the porter's reached any store.
        assert q("SELECT COUNT(*) AS n FROM memories WHERE chat_id=?",
                 (chat_id,), one=True)["n"] == 0

    def test_promotion_claims_the_retained_mind(self, temp_db, monkeypatch):
        from core.db import q, wget
        from persist.commit import promote_background_character
        chat_id, _cid = _launch(monkeypatch, _extraction(
            _mind(),
            _mind(who="The Porter",
                  knowledge_seeds=[
                      {"content": "I signed for {{PLAYER}}'s trunk at noon.",
                       "salience": 0.6, "revealed_in_prose": False}],
                  beliefs=[
                      {"belief": "The trunk was heavier than a trunk should be.",
                       "about_entity": "world", "confidence": 0.6}],
                  affect={"label": "wary", "valence": -0.3, "arousal": 0.2})))
        new_id = promote_background_character(
            chat_id, "the porter",
            sheet={"identity": {"name": "The Porter"}}, memory_seeds=[])
        rows = q("SELECT content FROM memories WHERE chat_id=? AND char_id=?",
                 (chat_id, new_id))
        assert any("trunk at noon" in r["content"] for r in rows)
        # Promotion seeds mutual recognition, so the persona's name is the
        # legitimate handle at claim time.
        assert any("Dana" in r["content"] for r in rows)
        st = _char_state(chat_id, new_id)
        assert st["interior"]["beliefs"][0]["source"] == "greeting"
        assert st["active_state"]["mood"] == "wary"
        record = wget(chat_id, "greeting_minds", {})
        assert record["minds"]["porter"]["claimed"] is True
        assert record["minds"]["porter"]["resolved"] == f"character:{new_id}"

    def test_promotion_without_a_retained_mind_is_unchanged(self, temp_db,
                                                            monkeypatch):
        from persist.commit import promote_background_character
        chat_id, _cid = _launch(monkeypatch, _extraction(_mind()))
        new_id = promote_background_character(
            chat_id, "a stranger",
            sheet={"identity": {"name": "A Stranger"}}, memory_seeds=[])
        assert "interior" not in _char_state(chat_id, new_id)


# ---- The visible record ----

class TestGreetingMindsRecord:
    def test_the_record_says_what_each_mind_received(self, temp_db,
                                                     monkeypatch):
        from core.db import wget
        chat_id, cid = _launch(monkeypatch, _extraction(
            _mind(knowledge_seeds=[{"content": "I waited.",
                                    "revealed_in_prose": False}],
                  beliefs=[{"belief": "x", "about_entity": "world"}],
                  affect={"label": "wary", "valence": -0.2, "arousal": 0.1})))
        record = wget(chat_id, "greeting_minds", {})
        entry = record["minds"]["dr. moon"]
        assert entry["resolved"] == f"character:{cid}"
        assert entry["claimed"] is True
        assert entry["seeded"]["memories"] == 1
        assert entry["seeded"]["beliefs"] == 1
        assert entry["seeded"]["affect"] == 1

    def test_legacy_top_level_seeds_still_reach_the_card_character(
            self, temp_db, monkeypatch):
        """A hand-stamped stored extraction may still carry v1's top-level
        knowledge_seeds; they fold into the card character's mind."""
        from core.db import q
        chat_id, _cid = _launch(monkeypatch, {
            "time": "now", "minds": [],
            "knowledge_seeds": [{"content": "I kept the old shape.",
                                 "salience": 0.5,
                                 "revealed_in_prose": False}]})
        rows = q("SELECT content FROM memories WHERE chat_id=?", (chat_id,))
        assert [r["content"] for r in rows] == ["I kept the old shape."]
