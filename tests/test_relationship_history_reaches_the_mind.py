"""D22 (review 2026-09-07): a mind is handed its own relationship history.

`relationship_events` has recorded one row per axis per movement since the
day it was built and had NO reader anywhere -- the scalar graph a character
reads carries five numbers plus a single `salient_event` string that is
overwritten whenever the character feels anything at all. The reasons were
stored and never read.

The rule these pin: `relationships_for_payload` attaches, per target, the
beat that moved each axis furthest, under `because`. It is bounded by the
axes rather than by a chosen number -- the descent bench (chat 117) holds
322 rows for one pair across 123 beats and five of them reach the payload --
frame-scoped exactly as the graph is, and it never crosses between minds.
"""

import pytest

from core.db import active_frame_id, qi
from mind.memory import (
    RelationshipGraph,
    record_relationship_event,
    relationships_for_payload,
    save_relationships,
)


def _chat(name="relationship history"):
    return qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
              (name, "", 0.0))


def _known(chat_id, char_id, *targets):
    graph = RelationshipGraph()
    for target in targets:
        graph.update(target, familiarity=0.5, last_interaction_turn=1)
    save_relationships(chat_id, char_id, graph)


def test_each_axis_is_explained_by_its_largest_movement(temp_db):
    chat_id = _chat()
    _known(chat_id, 35, "Hinami")
    # Trust moved three times; the payload explains it with the beat that
    # moved it furthest, not the latest and not all three.
    record_relationship_event(chat_id, 35, "Hinami", "trust", 0.05,
                              note="she stayed", turn_idx=4)
    record_relationship_event(chat_id, 35, "Hinami", "trust", -0.18,
                              note="she lied about the door", turn_idx=9)
    record_relationship_event(chat_id, 35, "Hinami", "trust", 0.02,
                              note="she came back", turn_idx=40)
    record_relationship_event(chat_id, 35, "Hinami", "fear", 0.11,
                              note="the knife came out", turn_idx=9)

    because = relationships_for_payload(chat_id, 35)["Hinami"]["because"]

    assert [entry["axis"] for entry in because] == ["trust", "fear"]
    assert because[0]["delta"] == pytest.approx(-0.18)
    assert because[0]["turn"] == 9
    assert because[0]["note"] == "she lied about the door"
    assert because[1]["note"] == "the knife came out"


def test_because_is_bounded_by_the_axes_not_by_the_ledgers_length(temp_db):
    """The shape of chat 117: hundreds of rows for one pair. What the mind is
    handed is the five numbers it already carries, each with its beat."""
    chat_id = _chat()
    _known(chat_id, 78, "character:79")
    for turn in range(120):
        for axis in ("trust", "warmth", "fear", "respect", "suspicion"):
            record_relationship_event(chat_id, 78, "character:79", axis,
                                      0.01, turn_idx=turn)

    because = relationships_for_payload(chat_id, 78)["character:79"]["because"]

    assert len(because) == 5
    assert [entry["axis"] for entry in because] == [
        "trust", "warmth", "fear", "respect", "suspicion"]
    # No note anywhere in the ledger: the key is absent rather than empty.
    assert all("note" not in entry for entry in because)


def test_a_target_the_ledger_never_recorded_carries_no_because(temp_db):
    chat_id = _chat()
    _known(chat_id, 35, "Hinami", "Tamamo")
    record_relationship_event(chat_id, 35, "Hinami", "trust", 0.2,
                              note="she stayed", turn_idx=4)

    out = relationships_for_payload(chat_id, 35)

    assert "because" in out["Hinami"]
    assert "because" not in out["Tamamo"]


def test_another_minds_reasons_never_explain_this_ones_stance(temp_db):
    """The ledger is keyed by the mind that holds the stance. Two characters
    with the same target must not read each other's reasons."""
    chat_id = _chat()
    _known(chat_id, 35, "Hinami")
    _known(chat_id, 36, "Hinami")
    record_relationship_event(chat_id, 35, "Hinami", "trust", -0.2,
                              note="she lied to me", turn_idx=9)
    record_relationship_event(chat_id, 36, "Hinami", "trust", -0.2,
                              note="I watched her draw", turn_idx=9)

    assert relationships_for_payload(chat_id, 35)["Hinami"]["because"][0][
        "note"] == "she lied to me"
    assert relationships_for_payload(chat_id, 36)["Hinami"]["because"][0][
        "note"] == "I watched her draw"


def test_another_eras_reasons_never_explain_the_present_stance(temp_db):
    """`relationships:<id>` is a frame-scoped world key, so the history that
    explains a stance has to be scoped the same way -- otherwise a branch the
    story never lived supplies the reason the present reads."""
    chat_id = _chat()
    frame_id = qi("INSERT INTO frames(chat_id,label,kind,created) "
                  "VALUES(?,?,?,?)", (chat_id, "an alternate era", "other",
                                      0.0))
    _known(chat_id, 35, "Hinami")
    record_relationship_event(chat_id, 35, "Hinami", "trust", -0.2,
                              note="what happened here", turn_idx=9)
    record_relationship_event(chat_id, 35, "Hinami", "trust", -0.2,
                              note="what happened in the other era",
                              turn_idx=9, frame_id=frame_id)

    present = relationships_for_payload(chat_id, 35)["Hinami"]["because"]
    assert [entry["note"] for entry in present] == ["what happened here"]

    token = active_frame_id.set(frame_id)
    try:
        _known(chat_id, 35, "Hinami")
        elsewhere = relationships_for_payload(chat_id, 35)["Hinami"]["because"]
    finally:
        active_frame_id.reset(token)
    assert [entry["note"] for entry in elsewhere] == [
        "what happened in the other era"]


class TestEveryWriterThatMovesAStanceSaysWhy:
    """D22 rework. `because` reads `relationship_events`, so a writer that
    moves an axis and records no row hands a mind a number it cannot account
    for -- and the two that recorded nothing were the two a charter story
    produces most: the travelling companion a journey seeds, and plain
    acquaintance, which every charter body has where a judgment is rare.
    The three writers beside them (conduct, inference, charter judgment)
    already recorded, which is what makes this the class and not a feature.
    """

    def test_a_road_walked_together_is_the_reason_they_are_not_strangers(
            self, temp_db, monkeypatch):
        """`story/journey_history` seeded a companion's trust and
        familiarity and wrote no ledger row at all."""
        import json
        import time

        from story.journey_history import compile_journey_history

        pid = temp_db.qi(
            "INSERT INTO personas(name,sheet,source,resource_uid) "
            "VALUES(?,?,?,?)",
            ("Alex Reed", json.dumps({"name": "Alex Reed"}), "test",
             "persona_uid"))
        cid = temp_db.qi(
            "INSERT INTO chats(name,persona_id,scenario,created) "
            "VALUES(?,?,?,?)", ("market", pid, "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)",
            ("Mara", json.dumps({"identity": {"name": "Mara"}}), "{}",
             time.time()))
        monkeypatch.setattr("mind.memory.add_memories_batch",
                            lambda rows: list(range(len(rows))))
        summary = "We crossed three worlds together and I owe her a map."

        compile_journey_history(
            cid, char_id, {"identity": {"name": "Mara"}},
            {"authority": "generated", "with_player": True,
             "event_count": 3},
            model_call=lambda payload: {
                "summary": summary,
                "events": [
                    {"sequence": n, "place": place, "people": ["Alex Reed"],
                     "memory": (
                         f"I walked into the {place} beside Alex Reed with "
                         "the last of our water gone, and we argued the whole "
                         "way about whether the road behind us had been the "
                         "shorter one, and I remember deciding that I would "
                         "not have crossed it alone for anything."),
                     "tone": "absorbing", "lesson": "precision",
                     "valence": 0.2, "arousal": 0.4, "salience": 0.6}
                    for n, place in enumerate(
                        ("Glass Sea", "Nacre", "Orison"), start=1)]})

        rows = temp_db.q(
            "SELECT axis,delta,note,provenance FROM relationship_events "
            "WHERE chat_id=? AND char_id=? ORDER BY axis", (cid, char_id))
        assert [row["axis"] for row in rows] == ["familiarity", "trust"]
        assert all(row["provenance"] == "journey" for row in rows)
        assert all(row["note"] == summary for row in rows)
        assert all(row["delta"] > 0.0 for row in rows)

        because = relationships_for_payload(cid, char_id)["Alex Reed"][
            "because"]
        # The five axes explain a stance; `familiarity` is not one of them,
        # so it is in the ledger and not in `because`.
        assert [entry["axis"] for entry in because] == ["trust"]
        assert because[0]["note"] == summary
        assert because[0]["provenance"] == "journey"

    def test_a_second_journey_records_the_movement_not_nothing(
            self, temp_db, monkeypatch):
        """The delta is the MOVEMENT, and it has to be measured before the
        write: `graph.get` hands back the live Relationship, so a prior read
        after `graph.update` saw the new value and every second seeding wrote
        a zero delta -- which `record_relationship_event` drops, so an edge
        the graph already carried never got its second row at all (D22
        rework, second skeptic). Two compiles, one shared event then three:
        four rows, the second pair carrying the distance travelled."""
        import json
        import time

        from story.journey_history import compile_journey_history

        pid = temp_db.qi(
            "INSERT INTO personas(name,sheet,source,resource_uid) "
            "VALUES(?,?,?,?)",
            ("Alex Reed", json.dumps({"name": "Alex Reed"}), "test",
             "persona_uid_2"))
        cid = temp_db.qi(
            "INSERT INTO chats(name,persona_id,scenario,created) "
            "VALUES(?,?,?,?)", ("market", pid, "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)",
            ("Mara", json.dumps({"identity": {"name": "Mara"}}), "{}",
             time.time()))
        monkeypatch.setattr("mind.memory.add_memories_batch",
                            lambda rows: list(range(len(rows))))

        def events(shared):
            return [
                {"sequence": n, "place": place,
                 "people": ["Alex Reed"] if n <= shared else [],
                 "memory": (
                     f"I walked into the {place} with the last of our water "
                     "gone, and argued the whole way about whether the road "
                     "behind us had been the shorter one, and decided I would "
                     "not have crossed it alone for anything at all."),
                 "tone": "absorbing", "lesson": "precision",
                 "valence": 0.2, "arousal": 0.4, "salience": 0.6}
                for n, place in enumerate(("Glass Sea", "Nacre", "Orison"),
                                          start=1)]

        for shared in (1, 3):
            compile_journey_history(
                cid, char_id, {"identity": {"name": "Mara"}},
                {"authority": "generated", "with_player": True,
                 "event_count": 3},
                model_call=lambda payload, shared=shared: {
                    "summary": f"Shared {shared} of three.",
                    "events": events(shared)})

        rows = temp_db.q(
            "SELECT axis,delta FROM relationship_events WHERE chat_id=? AND "
            "char_id=? ORDER BY id", (cid, char_id))
        assert len(rows) == 4, rows
        second = {row["axis"]: row["delta"] for row in rows[2:]}
        # depth 1/3 -> trust .3667 / familiarity .5; depth 3/3 -> .6 / .8
        assert abs(second["trust"] - 0.2333) < 0.001, second
        assert abs(second["familiarity"] - 0.30) < 0.001, second

    def test_an_acquaintance_carried_across_promotion_says_how_it_was_known(
            self, temp_db, monkeypatch):
        """`persist/commit_background`'s acquaintance block set trust and
        warmth for every charter acquaintance and recorded nothing, ten lines
        below the judgment block that records its rows."""
        import json
        import time

        from persist.commit import promote_background_character
        from world import charter_runtime

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Charter", "", time.time()))
        monkeypatch.setattr(
            charter_runtime, "promotion_bundle",
            lambda *a, **kw: {
                "charter": "gatehouse", "body": "guard",
                "social_names": {"hana": "Hana", "veil": "The Veiled One"},
                "handoff": {"acquaintances": [
                    {"body": "hana", "familiarity": 0.8, "regard": 1.2,
                     "firsthand": True},
                    {"body": "veil", "familiarity": 0.5, "regard": 0.9,
                     "firsthand": False}]}})
        monkeypatch.setattr(charter_runtime, "bind_promoted_character",
                            lambda *a, **kw: True)

        char_id = promote_background_character(
            cid, "Guard", sheet={"identity": {"name": "Guard"}},
            memory_seeds=[])

        rows = temp_db.q(
            "SELECT target,axis,delta,note,provenance FROM relationship_events "
            "WHERE chat_id=? AND char_id=? ORDER BY target,axis",
            (cid, char_id))
        assert [(row["target"], row["axis"]) for row in rows] == [
            ("Hana", "trust"), ("Hana", "warmth"),
            ("The Veiled One", "trust"), ("The Veiled One", "warmth")]
        assert all(row["provenance"] == "charter" for row in rows)
        assert "firsthand" in rows[0]["note"]
        assert "second hand" in rows[2]["note"]

        payload = relationships_for_payload(cid, char_id)
        assert [entry["axis"] for entry in payload["Hana"]["because"]] == [
            "trust", "warmth"]
        assert "second hand" in payload["The Veiled One"]["because"][0]["note"]
