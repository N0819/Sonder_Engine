"""Regression tests for greeting-seeded openings (swipe + quick start).

Card greetings (first_mes + alternate_greetings) are captured at import into
sheet.opening.greetings as a swipeable list, and must survive both a
normalize round-trip (the character-edit save path) and greeting-index
selection (what Quick start hands to start_story).
"""

from __future__ import annotations

import pytest

from story import importers
from story.character_schema import normalize_character_data
from story.greetings import _greeting_record
from tests.helpers import patch_provider_seam


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
        "alternate_greetings": [
            "A klaxon blares. {{user}} freezes.",
            "She waves {{user}} over to the sofa.",
            "",  # empty -> must be skipped, not stored as a blank greeting
        ],
    }


class TestGreetingCapture:
    def test_import_captures_first_mes_plus_alternates(self, temp_db):
        _cid, sheet = importers.import_character(_card(), reinterpret=False)
        greetings = sheet["opening"]["greetings"]
        # first_mes + 2 non-empty alternates (the empty one is dropped).
        assert len(greetings) == 3
        assert all(g["prose"].strip() for g in greetings)
        assert all(g["greeting_id"].startswith("greet_") for g in greetings)
        # greeting[0] is first_mes and matches the editor's first_message field.
        assert greetings[0]["prose"] == sheet["opening"]["first_message"]
        # macros are normalized in every greeting, not just first_mes.
        assert all("{{user}}" not in g["prose"] for g in greetings)
        assert all(importers.PLAYER_TOKEN in g["prose"] for g in greetings)

    def test_greeting_ids_are_stable_and_unique(self, temp_db):
        _cid, sheet = importers.import_character(_card(), reinterpret=False)
        ids = [g["greeting_id"] for g in sheet["opening"]["greetings"]]
        assert len(ids) == len(set(ids))


class TestGreetingsSurviveNormalize:
    """The character-edit save path (PUT /api/characters/{id}) normalizes the
    submitted sheet; that must not drop the greetings list."""

    def test_normalize_preserves_greetings(self, temp_db):
        _cid, sheet = importers.import_character(_card(), reinterpret=False)
        before = [g["greeting_id"] for g in sheet["opening"]["greetings"]]
        renorm = normalize_character_data(sheet)
        after = [g["greeting_id"] for g in renorm["opening"]["greetings"]]
        assert after == before

    def test_double_normalize_is_idempotent(self, temp_db):
        _cid, sheet = importers.import_character(_card(), reinterpret=False)
        once = normalize_character_data(sheet)
        twice = normalize_character_data(once)
        assert (twice["opening"]["greetings"]
                == once["opening"]["greetings"])


class TestGreetingSelection:
    """_greeting_record is what Quick start's greeting_index resolves through."""

    def test_index_selects_matching_greeting(self, temp_db):
        _cid, sheet = importers.import_character(_card(), reinterpret=False)
        for i, g in enumerate(sheet["opening"]["greetings"]):
            assert _greeting_record(sheet, i)["prose"] == g["prose"]

    def test_index_is_clamped_in_range(self, temp_db):
        _cid, sheet = importers.import_character(_card(), reinterpret=False)
        last = sheet["opening"]["greetings"][-1]["prose"]
        assert _greeting_record(sheet, 999)["prose"] == last
        first = sheet["opening"]["greetings"][0]["prose"]
        assert _greeting_record(sheet, -5)["prose"] == first

    def test_falls_back_to_first_message_when_no_greetings(self, temp_db):
        sheet = {"opening": {"first_message": "Just a plain opener."}}
        assert _greeting_record(sheet, 0)["prose"] == "Just a plain opener."


class TestReinterpretPathCapturesGreetings:
    """The AI-reinterpret import path returns a fresh sheet with no greetings;
    import_character must still capture them from the original card, or
    alternate greetings are silently lost (the live-DB bug we hit)."""

    def test_reinterpret_import_still_captures_greetings(self, temp_db, monkeypatch):
        # Stub the model to return a native sheet WITHOUT any greetings.
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda *a, **k: '{"name":"Dr. Moon","opening":{"first_message":"AI opener."}}')
        card = {
            "spec": "chara_card_v2", "spec_version": "2.0",
            "data": {
                "name": "Dr. Moon",
                "first_mes": "Hello {{user}}.",
                "alternate_greetings": ["A klaxon blares.", "She waves you over."],
            },
        }
        _cid, sheet = importers.import_character(card, reinterpret=True)
        greetings = sheet["opening"].get("greetings") or []
        assert len(greetings) == 3
        assert all("{{user}}" not in g["prose"] for g in greetings)


class TestRecoverGreetings:
    """recover_greetings_from_source backfills greetings for characters imported
    before capture existed / via the reinterpret path, from the stored card."""

    def _legacy_row(self):
        from core.db import qi
        card = {
            "spec": "chara_card_v2", "spec_version": "2.0",
            "data": {
                "name": "Dr. Moon",
                "first_mes": "Hello {{user}}.",
                "alternate_greetings": ["A klaxon blares.", ""],
            },
        }
        sheet = {"identity": {"name": "Dr. Moon"}, "opening": {"first_message": "Hi."}}
        src = {"format": "imported", "original": card}
        import json
        return qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                  ("Dr. Moon", json.dumps(sheet), json.dumps(src), 0))

    def test_recovers_from_stored_source(self, temp_db):
        rid = self._legacy_row()
        sheet = importers.recover_greetings_from_source(rid)
        g = sheet["opening"]["greetings"]
        assert len(g) == 2  # first_mes + 1 non-empty alternate
        assert all("{{user}}" not in x["prose"] for x in g)

    def test_recover_is_idempotent(self, temp_db):
        rid = self._legacy_row()
        first = importers.recover_greetings_from_source(rid)["opening"]["greetings"]
        again = importers.recover_greetings_from_source(rid)["opening"]["greetings"]
        assert again == first

    def test_recover_returns_none_when_no_card_greetings(self, temp_db):
        from core.db import qi
        import json
        rid = qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                 ("Hand-made", json.dumps({"identity": {"name": "Hand-made"},
                                           "opening": {"first_message": "x"}}),
                  json.dumps({"format": "imported", "original": {"name": "Hand-made"}}), 0))
        assert importers.recover_greetings_from_source(rid) is None


class TestQuickStartLorebook:
    """Quick start can attach an optional lorebook to the new chat, before
    turn 0 runs. The pipeline + greeting extraction are stubbed so the test
    stays deterministic and offline."""

    def _stub_launch(self, monkeypatch):
        from story import greetings
        monkeypatch.setattr(greetings, "extract_greeting",
                            lambda sheet, prose: {"knowledge_seeds": [], "time": "now"})
        monkeypatch.setattr(greetings, "_run_pipeline",
                            lambda cid, tid: iter(()))
        return greetings

    def _fixtures(self):
        from core.db import qi
        cid_char, _ = importers.import_character(_card(), reinterpret=False)
        pid, _ = importers.import_persona({"name": "Dana"}, reinterpret=False)
        lb = qi("INSERT INTO lorebooks(name,book_type,summary) VALUES(?,?,?)",
                ("SCP", "general", ""))
        return cid_char, pid, lb

    def test_attaches_selected_lorebook_as_chat_copy(self, temp_db, monkeypatch):
        from core.db import q
        greetings = self._stub_launch(monkeypatch)
        cid_char, pid, lb = self._fixtures()

        chat_id, _tid = greetings.start_story(
            cid_char, pid, greeting_index=1, lorebook_id=lb)

        rows = q("SELECT cl.lorebook_id, cl.origin_id, lb2.chat_id AS book_chat "
                 "FROM chat_lorebooks cl JOIN lorebooks lb2 ON lb2.id=cl.lorebook_id "
                 "WHERE cl.chat_id=?", (chat_id,))
        assert len(rows) == 1
        # attached as a per-chat duplicate that points back to the template.
        assert rows[0]["origin_id"] == lb
        assert rows[0]["lorebook_id"] != lb
        assert rows[0]["book_chat"] == chat_id

    def test_no_lorebook_attaches_nothing(self, temp_db, monkeypatch):
        from core.db import q
        greetings = self._stub_launch(monkeypatch)
        cid_char, pid, _lb = self._fixtures()

        chat_id, _tid = greetings.start_story(cid_char, pid, greeting_index=0)
        rows = q("SELECT 1 FROM chat_lorebooks WHERE chat_id=?", (chat_id,))
        assert rows == []

    def test_bad_lorebook_id_aborts_before_creating_a_chat(self, temp_db, monkeypatch):
        from core.db import q
        greetings = self._stub_launch(monkeypatch)
        cid_char, pid, _lb = self._fixtures()

        with pytest.raises(ValueError):
            greetings.start_story(cid_char, pid, lorebook_id=999999)
        assert q("SELECT COUNT(*) AS n FROM chats", one=True)["n"] == 0

    def test_lived_location_lands_before_turn_zero_uses_chat_lore_copy(
            self, temp_db, monkeypatch):
        from story import greetings
        from world import charter_runtime
        cid_char, pid, lb = self._fixtures()
        monkeypatch.setattr(
            greetings, "extract_greeting",
            lambda sheet, prose: {"knowledge_seeds": [], "time": "now"})
        order = []

        def generated(chat_id, request, **kwargs):
            order.append("location")
            selected = temp_db.q(
                "SELECT chat_id FROM lorebooks WHERE id=?",
                (request["owning_lorebook_id"],), one=True)
            assert selected["chat_id"] == chat_id
            assert request["lorebook_id"] == lb
            assert request["owning_lorebook_id"] != lb
            return {"ok": True}

        monkeypatch.setattr(charter_runtime, "generate_lived_location", generated)
        monkeypatch.setattr(
            greetings, "_run_pipeline",
            lambda cid, tid: order.append("turn_zero") or iter(()))

        greetings.start_story(
            cid_char, pid, lorebook_id=lb,
            lived_location={"enabled": True, "brief": "the port"})

        assert order == ["location", "turn_zero"]

    def test_lived_location_places_and_hands_off_card_character(
            self, temp_db, monkeypatch):
        from story import greetings
        from world import charter_history, charter_runtime
        cid_char, pid, _lb = self._fixtures()
        monkeypatch.setattr(
            greetings, "extract_greeting",
            lambda sheet, prose: {
                "knowledge_seeds": [{
                    "content": "The original greeting established this memory.",
                    "salience": 0.5, "revealed_in_prose": True}],
                "time": "now"})
        order = []

        def generated(chat_id, request, **kwargs):
            resident = request["featured_residents"][0]
            assert resident["seed_id"] == f"character:{cid_char}"
            assert "private_history" not in resident
            order.append("location")
            return {"ok": True, "featured_residents": {
                resident["seed_id"]: {
                    "seed_id": resident["seed_id"], "charter": "site",
                    "body": "psychologist:featured:x", "name": "Dr. Moon",
                    "place": "office"}}}

        def integrated(chat_id, char_id, binding, sheet, **kwargs):
            assert char_id == cid_char
            assert binding["charter"] == "site"
            greeting_rows = temp_db.q(
                "SELECT content FROM memories WHERE chat_id=? AND char_id=?",
                (chat_id, char_id))
            assert any("original greeting" in row["content"]
                       for row in greeting_rows)
            order.append("resident")
            return {}

        monkeypatch.setattr(charter_runtime, "generate_lived_location", generated)
        monkeypatch.setattr(charter_history, "integrate_featured_resident", integrated)
        monkeypatch.setattr(
            greetings, "_run_pipeline",
            lambda cid, tid: order.append("turn_zero") or iter(()))

        greetings.start_story(
            cid_char, pid,
            lived_location={
                "enabled": True, "brief": "the facility",
                "character_history": {"mode": "resident"}})

        assert order == ["location", "resident", "turn_zero"]

    def test_itinerant_auto_route_never_places_character_in_charter(
            self, temp_db, monkeypatch):
        import json
        from story import greetings, journey_history
        from world import charter_runtime

        cid_char, pid, _lb = self._fixtures()
        row = temp_db.q("SELECT sheet FROM characters WHERE id=?",
                        (cid_char,), one=True)
        sheet = json.loads(row["sheet"])
        sheet.setdefault("knowledge", {})["public_history"] = (
            "An alien traveler who wanders between worlds and arrives at crises.")
        temp_db.qi("UPDATE characters SET sheet=? WHERE id=?",
                   (json.dumps(sheet), cid_char))
        monkeypatch.setattr(
            greetings, "extract_greeting",
            lambda sheet, prose: {"knowledge_seeds": [], "time": "now"})
        order = []

        def generated(chat_id, request, **kwargs):
            assert "featured_residents" not in request
            order.append("location")
            return {"ok": True, "featured_residents": {}}

        def journey(chat_id, char_id, sheet, route, **kwargs):
            assert route["opening_relationship"] == "visiting"
            assert route["backends"] == ["authored_history"]
            order.append("journey")
            return {"events": [{"event_id": "journey:1"}],
                    "memory_event_keys": ["prestory:journey:1"]}

        monkeypatch.setattr(charter_runtime, "generate_lived_location", generated)
        monkeypatch.setattr(journey_history, "compile_journey_history", journey)
        monkeypatch.setattr(
            greetings, "_run_pipeline",
            lambda cid, tid: order.append("turn_zero") or iter(()))

        chat_id, _ = greetings.start_story(
            cid_char, pid,
            lived_location={"enabled": True, "brief": "a distant city",
                            "character_history": {"mode": "auto"}})

        assert order == ["location", "journey", "turn_zero"]
        route = temp_db.wget(chat_id, "character_history_routes", {})[
            str(cid_char)]
        assert route["handoff"]["journey_events"] == 1

    def test_failed_lived_location_leaves_no_half_created_story(
            self, temp_db, monkeypatch):
        from core.db import q
        from llm.providers import ReasoningBudgetExhausted
        from story import greetings
        from world import charter_runtime

        cid_char, pid, lb = self._fixtures()
        monkeypatch.setattr(
            greetings, "extract_greeting",
            lambda sheet, prose: {"knowledge_seeds": [], "time": "now"})

        def fail(*args, **kwargs):
            raise ReasoningBudgetExhausted("answer budget exhausted")

        monkeypatch.setattr(charter_runtime, "generate_lived_location", fail)
        with pytest.raises(ReasoningBudgetExhausted):
            greetings.start_story(
                cid_char, pid, lorebook_id=lb,
                lived_location={"enabled": True, "brief": "the port"})

        assert q("SELECT COUNT(*) AS n FROM chats", one=True)["n"] == 0
        assert q(
            "SELECT COUNT(*) AS n FROM lorebooks WHERE chat_id IS NOT NULL",
            one=True)["n"] == 0

    def test_already_known_default_seeds_mutual_recognition(self, temp_db, monkeypatch):
        from core.db import wget
        greetings = self._stub_launch(monkeypatch)
        cid_char, pid, _lb = self._fixtures()

        chat_id, _tid = greetings.start_story(cid_char, pid, greeting_index=0)
        # Default: greeting written TO the player -> both know each other's name.
        assert wget(chat_id, "known", {}) == {"Dr. Moon": ["Dana"],
                                              "Dana": ["Dr. Moon"]}

    def test_stranger_start_seeds_no_recognition(self, temp_db, monkeypatch):
        from core.db import wget
        greetings = self._stub_launch(monkeypatch)
        cid_char, pid, _lb = self._fixtures()

        # A strangers-meeting greeting: the character must not begin knowing the
        # player's name, or perception leaks it into their view from turn 1.
        chat_id, _tid = greetings.start_story(
            cid_char, pid, greeting_index=0, already_known=False)
        assert wget(chat_id, "known", {}) == {}


class TestKnowledgeSeedRouting:
    """What a greeting's seeds become once they are inside the character.

    `tests/test_greetings.py` had 30 tests and none of them touched seed
    routing, which is how chat 53 launched with four authored seeds at
    salience 1.00 sitting permanently above the 0.78 of the one memory the
    pipeline actually minted that turn. See docs/UNBUILT.md 1.16.
    """

    def _launch(self, monkeypatch, seeds):
        from story import greetings
        monkeypatch.setattr(greetings, "extract_greeting",
                            lambda sheet, prose: {"knowledge_seeds": seeds,
                                                  "time": "now"})
        monkeypatch.setattr(greetings, "_run_pipeline", lambda cid, tid: iter(()))
        cid_char, _ = importers.import_character(_card(), reinterpret=False)
        pid, _ = importers.import_persona({"name": "Dana"}, reinterpret=False)
        return greetings.start_story(cid_char, pid, greeting_index=0)

    def test_a_seed_reaches_the_characters_own_memory(self, temp_db, monkeypatch):
        from core.db import q
        chat_id, _tid = self._launch(monkeypatch, [
            {"content": "I have been waiting three nights for a courier.",
             "salience": 0.6, "revealed_in_prose": False}])
        rows = q("SELECT content, salience, event_key FROM memories "
                 "WHERE chat_id=?", (chat_id,))
        assert len(rows) == 1
        assert rows[0]["content"] == "I have been waiting three nights for a courier."

    def test_a_seed_can_never_outrank_the_consolidation_floor(self, temp_db,
                                                              monkeypatch):
        """The defect exactly. Consolidation archives below 0.72, so a seed at
        1.00 never ages out, while `contrast_memory` scores
        `salience + 0.4 * (age / current_turn)` -- making authored scaffolding
        MORE likely to intrude unbidden the longer the story runs.

        Note what this goes through: the stub hands `start_story` a raw dict,
        exactly as a STORED extraction on a character card does. Nothing here
        passes `GreetingKnowledgeSeed`, which is precisely why the ceiling
        cannot live in the schema alone."""
        from core.db import q
        chat_id, _tid = self._launch(monkeypatch, [
            {"content": "The Doctor has a deep-seated fear of Daleks.",
             "salience": 1.0, "revealed_in_prose": False}])
        salience = q("SELECT salience FROM memories WHERE chat_id=?",
                     (chat_id,))[0]["salience"]
        assert salience <= 0.7
        assert salience < 0.72, "a seed that never archives is permanent"

    def test_the_schema_is_where_the_ceiling_lives(self, temp_db):
        """Both routing sites read the validated model, so the cap belongs
        there rather than at one call site that the other can bypass."""
        from llm.schemas import GreetingKnowledgeSeed
        assert GreetingKnowledgeSeed(content="x", salience=1.0).salience == 0.7
        assert GreetingKnowledgeSeed(content="x", salience=0.5).salience == 0.5
        # Still tolerant of nonsense, like every other lenient field.
        assert GreetingKnowledgeSeed(content="x", salience="nope").salience == 0.6

    def test_seeds_carry_a_stable_identity(self, temp_db, monkeypatch):
        """`add_memory` upserts on (chat, character, event_key). Without one,
        routing the same seed twice writes it twice."""
        from core.db import q
        chat_id, _tid = self._launch(monkeypatch, [
            {"content": "I have been waiting three nights for a courier.",
             "salience": 0.6, "revealed_in_prose": False}])
        key = q("SELECT event_key FROM memories WHERE chat_id=?",
                (chat_id,))[0]["event_key"]
        assert key.startswith("greeting_seed:")

    def test_routing_the_same_seed_twice_updates_one_row(self, temp_db,
                                                         monkeypatch):
        from core.db import q
        from mind.memory import add_memory
        chat_id, _tid = self._launch(monkeypatch, [
            {"content": "I have been waiting three nights for a courier.",
             "salience": 0.6, "revealed_in_prose": False}])
        row = q("SELECT char_id, content, event_key FROM memories "
                "WHERE chat_id=?", (chat_id,))[0]
        add_memory(chat_id, row["char_id"], None, "episode", "remembered",
                   0.6, row["content"], turn_idx=0, event_key=row["event_key"])
        assert len(q("SELECT id FROM memories WHERE chat_id=?", (chat_id,))) == 1

    def test_a_bad_seed_does_not_abort_the_launch(self, temp_db, monkeypatch):
        """A launch that half-builds a story is worse than a lost seed."""
        chat_id, _tid = self._launch(monkeypatch, [
            {"content": "", "salience": 0.6},
            {"content": "I know the harbour road floods at spring tide.",
             "salience": 0.6}])
        from core.db import q
        rows = q("SELECT content FROM memories WHERE chat_id=?", (chat_id,))
        assert [r["content"] for r in rows] == [
            "I know the harbour road floods at spring tide."]

    def test_every_seed_is_embedded_in_one_call(self, temp_db, monkeypatch):
        """Six seeds cost ONE round trip to the embedding provider, not six.

        Each seed embeds two documents, and `embed_texts_meta` degrades to the
        crc32 hash on any error -- so one call per seed was six independent
        chances to write a memory that is stamped `cheap:crc32:256` and
        reachable by keyword only. Reported live on 2026-08-11: a story made
        from a greeting offered, on its own first beat, to rebuild the
        memories it had just written. Batching does not make the failure
        impossible; it makes it one failure instead of six, and that one is
        retried inside the provider seam.
        """
        from mind import memory
        calls = []
        real = memory.embed_texts_meta
        patch_provider_seam(monkeypatch, "embed_texts_meta",
                            lambda texts, **kw: (calls.append(list(texts)),
                                                 real(texts, **kw))[1])
        chat_id, _tid = self._launch(monkeypatch, [
            {"content": f"I remember the {word} well.", "salience": 0.5}
            for word in ("harbour", "chandler", "toll", "ferry", "vault",
                         "signal")])
        from core.db import q
        assert len(q("SELECT id FROM memories WHERE chat_id=?", (chat_id,))) == 6
        assert len(calls) == 1
        assert len(calls[0]) == 12  # document + cues per seed

    def test_seeds_still_carry_one_stamp_each(self, temp_db, monkeypatch):
        """The batch must stamp every row, not only the first."""
        chat_id, _tid = self._launch(monkeypatch, [
            {"content": "I know the harbour road floods.", "salience": 0.5},
            {"content": "I know the chandler waters his oil.", "salience": 0.5}])
        from core.db import q
        rows = q("SELECT embedding_model, embedding_dim, embedding FROM "
                 "memories WHERE chat_id=?", (chat_id,))
        assert len(rows) == 2
        assert all(r["embedding_model"] and r["embedding_dim"] and r["embedding"]
                   for r in rows)


class TestTheExtractorVersionIsStampedAndChecked:
    """`EXTRACTOR_VERSION` existed for one purpose -- refusing an extraction
    produced by an older extractor -- and nothing stamped it or read it. Both
    producers of a greeting record wrote `extractor_version: None` outright,
    and `start_story` replayed any stored `extraction` with no version test at
    all, so a card carrying scaffolding from any past extractor was replayed
    as current.

    That matters because the extraction is not cosmetic: it is what routes
    the character's PRIVATE knowledge into memory at turn 0, and its shape
    has already changed once under a cap the schema now enforces on the way
    in. A stored extraction is the one path that reaches the seeding code
    without passing through today's schema."""

    def _fixtures(self, monkeypatch, extraction, version, calls):
        from story import greetings
        from core.db import q, qi
        import json as _json

        def fake_extract(sheet, prose):
            calls.append(prose)
            return {"knowledge_seeds": [], "time": "now"}

        monkeypatch.setattr(greetings, "extract_greeting", fake_extract)
        monkeypatch.setattr(greetings, "_run_pipeline", lambda cid, tid: iter(()))

        cid_char, _ = importers.import_character(_card(), reinterpret=False)
        pid, _ = importers.import_persona({"name": "Dana"}, reinterpret=False)
        row = q("SELECT sheet FROM characters WHERE id=?", (cid_char,), one=True)
        sheet = _json.loads(row["sheet"])
        record = sheet["opening"]["greetings"][0]
        record["extraction"] = extraction
        record["extractor_version"] = version
        qi("UPDATE characters SET sheet=? WHERE id=?",
           (_json.dumps(sheet), cid_char))
        return greetings, cid_char, pid

    def test_a_stored_extraction_of_this_version_is_replayed(
            self, temp_db, monkeypatch):
        from story.greetings import EXTRACTOR_VERSION
        calls = []
        greetings, cid_char, pid = self._fixtures(
            monkeypatch, {"knowledge_seeds": [], "time": "stored"},
            EXTRACTOR_VERSION, calls)

        greetings.start_story(cid_char, pid, greeting_index=0)

        assert calls == []

    def test_an_unstamped_extraction_is_re_extracted(self, temp_db, monkeypatch):
        """Every stored extraction in the wild is unstamped, because nothing
        ever stamped one. Unknown provenance is not this version."""
        calls = []
        greetings, cid_char, pid = self._fixtures(
            monkeypatch, {"knowledge_seeds": [], "time": "stored"}, None, calls)

        greetings.start_story(cid_char, pid, greeting_index=0)

        assert len(calls) == 1

    def test_an_older_extraction_is_re_extracted(self, temp_db, monkeypatch):
        from story.greetings import EXTRACTOR_VERSION
        calls = []
        greetings, cid_char, pid = self._fixtures(
            monkeypatch, {"knowledge_seeds": [], "time": "stored"},
            EXTRACTOR_VERSION - 1, calls)

        greetings.start_story(cid_char, pid, greeting_index=0)

        assert len(calls) == 1

    def test_a_fresh_extraction_carries_its_own_stamp(self, monkeypatch):
        """Stamped where it is MINTED, not where it is filed: the record's
        sibling field and the extraction can be separated by any writer, and
        an extraction that cannot say what made it is unversionable forever
        after."""
        from story import greetings
        from story.greetings import EXTRACTOR_VERSION

        monkeypatch.setattr(greetings, "complete_validated_json",
                            lambda **kw: {"knowledge_seeds": [], "time": "now"})
        out = greetings.extract_greeting({"identity": {"name": "X"}}, "Hello.")

        assert out["extractor_version"] == EXTRACTOR_VERSION

    def test_the_stamp_on_the_extraction_itself_is_enough(
            self, temp_db, monkeypatch):
        from story.greetings import EXTRACTOR_VERSION
        calls = []
        greetings, cid_char, pid = self._fixtures(
            monkeypatch,
            {"knowledge_seeds": [], "time": "stored",
             "extractor_version": EXTRACTOR_VERSION},
            None, calls)

        greetings.start_story(cid_char, pid, greeting_index=0)

        assert calls == []
