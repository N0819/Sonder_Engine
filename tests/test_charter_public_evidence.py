"""Player/major-character conduct reaches Charter as observer-owned evidence."""

from __future__ import annotations

import time

from agents.director import _ground_public_evidence, _resolve_beat_view
from world.charter import normalize_charter
from world.charter_mind import hear_claim
from world.charter_observe import apply_public_evidence


def _scene():
    return {
        "rooms": {
            "hall": {"name": "Hall", "adjacent": [
                {"to": "yard", "barrier": "closed_door"}]},
            "yard": {"name": "Yard", "adjacent": [
                {"to": "hall", "barrier": "closed_door"}]},
        },
        "positions": {"Rowan": "hall", "Mara": "hall"},
    }


def _charter():
    return normalize_charter({
        "key": "town",
        "bodies": {
            "reeve": {"name": "Ysra", "title": "Reeve", "place": "hall"},
            "porter": {"name": "Oren", "place": "yard"},
        },
    })


def _speech(**updates):
    row = {
        "source_id": "speech:0", "kind": "speech", "actor": "Rowan",
        "exact_quote": '"Meals and a bed while I work. Which problem first?"',
        "target": "Reeve Ysra", "volume": "normal", "visibility": "overt",
        "conceal_from": [], "salience": 0.8,
        "speech_acts": [
            {"kind": "request", "content": "Meals and a bed"},
            {"kind": "offer", "content": "while I work"},
            {"kind": "question", "content": "Which problem first?"},
        ],
    }
    row.update(updates)
    return row


def test_semantic_roles_are_grounded_to_exact_utterance_spans():
    quote = '"Meals and a bed while I work. Which problem first?"'
    out = {
        "dialogue_log": [{"speaker": "Rowan", "exact_quote": quote,
                          "intended_target": "Reeve Ysra", "volume": "normal"}],
        "public_evidence": [{
            "source_id": "speech:0", "salience": 0.9,
            "speech_acts": [
                {"kind": "request", "content": "Meals and a bed"},
                {"kind": "offer", "content": "while I work"},
                {"kind": "question", "content": "Which problem first?"},
                # The social model cannot smuggle resolve prose into a mind.
                {"kind": "disclosure", "content": "the mayor is secretly ill"},
            ],
        }],
    }
    view = {"public_sources": [{
        "source_id": "speech:0", "kind": "speech", "actor": "Rowan",
        "exact_quote": quote, "target": "Reeve Ysra", "volume": "normal",
        "visibility": "overt", "conceal_from": [],
    }]}

    _ground_public_evidence(out, view)

    evidence = out["public_evidence"][0]
    assert [frame["kind"] for frame in evidence["speech_acts"]] == [
        "request", "offer", "question"]
    assert evidence["target"] == "Reeve Ysra"
    assert "secretly ill" not in str(evidence)


def test_a_failed_semantic_annotation_keeps_the_factual_source():
    out = {"dialogue_log": [], "public_evidence": []}
    view = {"public_sources": [{
        "source_id": "action:Rowan:0", "kind": "action", "actor": "Rowan",
        "surface": "kneels beside the broken axle", "target": "wagon",
        "visibility": "overt", "conceal_from": [], "status": "attempted",
    }]}

    _ground_public_evidence(out, view)

    assert out["public_evidence"] == [{
        **view["public_sources"][0], "speech_acts": [], "salience": 0.5,
    }]


def test_only_player_and_major_character_sources_enter_the_shared_digest():
    out = {"resolved_event": "", "dialogue_log": [
        {"speaker": "Rowan", "exact_quote": '"Come in."'},
        {"speaker": "a porter", "exact_quote": '"Mind the step."'},
    ]}
    interp = {"sequence": [
        {"type": "speech", "text": "Come in."},
        {"type": "action", "attempt": "inspect the hinge",
         "observable": "leans close to inspect the hinge"},
    ]}
    view = _resolve_beat_view(
        out, [{"name": "Mara"}], {"Mara": [{
            "type": "action", "attempt": "holds the lantern higher",
            "observable": "holds the lantern higher",
        }]}, [], "Rowan", interp)

    assert [(s["kind"], s["actor"]) for s in view["public_sources"]] == [
        ("speech", "Rowan"), ("action", "Rowan"), ("action", "Mara")]
    assert all("a porter" not in str(s) for s in view["public_sources"])


def test_described_communication_reaches_charter_without_a_fake_quote():
    view = _resolve_beat_view(
        {"resolved_event": "", "dialogue_log": []}, [], {}, [], "Rowan",
        {"sequence": [{
            "type": "communication", "act": "ask",
            "content": "which culvert should be surveyed first",
            "targets": ["Reeve Ysra"], "volume": "normal",
            "visibility": "overt", "conceal_from": [],
        }]})
    out = {"dialogue_log": [], "public_evidence": []}
    _ground_public_evidence(out, view)
    evidence = out["public_evidence"][0]
    assert evidence["kind"] == "communication"
    assert "exact_quote" not in evidence
    assert evidence["speech_acts"] == [{
        "kind": "ask", "content": "which culvert should be surveyed first"}]

    charter, metrics = apply_public_evidence(
        _charter(), [evidence], _scene(), turn_id=11)
    news = next(c for c in charter["minds"]["reeve"].values()
                if c.get("kind") == "news")
    assert metrics["acquired"] == 1
    assert "asks which culvert" in news["claim_text"]


def test_exact_speech_lands_only_in_the_full_hearing_witness():
    charter, metrics = apply_public_evidence(
        _charter(), [_speech()], _scene(), turn_id=7)

    reeve = charter["minds"]["reeve"]
    news = next(c for c in reeve.values() if c.get("kind") == "news")
    assert metrics["acquired"] == 1
    assert news["public_evidence"]["speech_acts"][0] == {
        "kind": "request", "content": "Meals and a bed"}
    assert "Rowan said" in news["claim_text"]
    assert not charter["minds"].get("porter")


def test_concealment_is_checked_against_titles_and_names():
    charter, metrics = apply_public_evidence(
        _charter(), [_speech(conceal_from=["the Reeve"])], _scene(), turn_id=8)

    assert metrics["acquired"] == 0
    assert not charter["minds"].get("reeve")


def test_visible_action_becomes_attempt_evidence_not_an_asserted_outcome():
    action = {
        "source_id": "action:Rowan:0", "kind": "action", "actor": "Rowan",
        "surface": "sets a surveyor's chain beside the cracked culvert",
        "target": "culvert", "visibility": "overt", "conceal_from": [],
        "status": "attempted", "speech_acts": [], "salience": 0.7,
    }
    charter, _ = apply_public_evidence(_charter(), [action], _scene(), turn_id=9)
    news = next(c for c in charter["minds"]["reeve"].values()
                if c.get("kind") == "news")

    assert news["public_evidence"]["status"] == "attempted"
    assert "succeeded" not in news["claim_text"]


def test_retelling_drops_the_pristine_quote_but_keeps_act_direction():
    charter, _ = apply_public_evidence(_charter(), [_speech()], _scene(), turn_id=10)
    claim = next(c for c in charter["minds"]["reeve"].values()
                 if c.get("kind") == "news")
    minds = charter["minds"]

    assert hear_claim(minds, "porter", claim, retention=0.8,
                      heard_from="reeve") is True
    heard = minds["porter"][claim["body"]]
    assert heard["public_evidence"] == {
        "kind": "speech",
        "speech_act_kinds": ["request", "offer", "question"],
        "secondhand": True,
    }
    assert "exact_quote" not in str(heard["public_evidence"])
    assert "was reported saying" in heard["claim_text"]
    assert '"Meals and a bed' not in heard["claim_text"]


def test_runtime_lands_all_witnesses_with_one_registry_write(temp_db,
                                                              monkeypatch):
    from world import charter_runtime

    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Charter evidence", "", time.time()))
    charter_runtime.save_registry(cid, {"town": _charter()})
    writes = []
    original = charter_runtime.save_registry

    def counted(*args, **kwargs):
        writes.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(charter_runtime, "save_registry", counted)
    result = charter_runtime.ingest_public_evidence(
        cid, [_speech()], _scene(), turn_id=12)

    held = charter_runtime.registry_for(cid)["items"]["town"]["state"][
        "minds"]["reeve"]
    view = charter_runtime.presence_view(cid, "hall", "Reeve Ysra")
    assert result == {"sources": 1, "opportunities": 2, "acquired": 1,
                      "unplaced": []}
    assert sum(1 for claim in held.values() if claim.get("kind") == "news") == 1
    recalled = view[0]["presence"]["can_bring_up"][0]
    assert recalled["public_evidence"]["speech_acts"][0]["kind"] == "request"
    assert len(writes) == 1


def test_a_beat_nobody_receives_costs_no_private_parse_and_no_fetch(
        temp_db, monkeypatch):
    """The no-acquisition beat rides the shared cached registry.

    Measured 2026-08-28 (chat 95, generated market town, 307 bodies,
    41.4MB stored registry): `ingest_public_evidence` paid a ~1.1s private
    `registry_for_update` parse inside the locked commit for a beat that
    landed in nobody's mind, then saved nothing. The appraisal
    (`plan_public_evidence`) now gates on the shared cache: warm, such a
    beat performs zero charters fetches, zero private parses, and zero
    writes -- and the stored row stays byte-identical by construction.
    """
    import core.db as core_db
    from world import charter_runtime

    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Charter evidence", "", time.time()))
    charter_runtime.save_registry(cid, {"town": _charter()})
    charter_runtime.registry_for(cid)   # warm the shared cache

    fetches, private, writes = [], [], []
    real_wget = core_db.wget

    def counting_wget(chat_id, key, d=None):
        if key == charter_runtime.CHARTERS_KEY:
            fetches.append(key)
        return real_wget(chat_id, key, d)

    real_update = charter_runtime.registry_for_update
    monkeypatch.setattr(core_db, "wget", counting_wget)
    monkeypatch.setattr(
        charter_runtime, "registry_for_update",
        lambda *a, **k: private.append(a) or real_update(*a, **k))
    monkeypatch.setattr(
        charter_runtime, "save_registry",
        lambda *a, **k: writes.append(a))

    result = charter_runtime.ingest_public_evidence(
        cid, [_speech(visibility="concealed",
                      conceal_from=["Ysra", "Oren"])],
        _scene(), turn_id=12)

    assert result == {"sources": 1, "opportunities": 2, "acquired": 0,
                      "unplaced": []}
    assert fetches == []
    assert private == []
    assert writes == []


def test_a_beat_that_lands_still_pays_the_private_parse_once(
        temp_db, monkeypatch):
    """The gate must never make the WRITE path read the shared object:
    when a claim lands, the mutation runs on exactly one private parse and
    one save, and the cached registry the appraisal read stays untouched."""
    from world import charter_runtime

    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Charter evidence", "", time.time()))
    charter_runtime.save_registry(cid, {"town": _charter()})
    shared = charter_runtime.registry_for(cid)
    before_minds = dict(shared["items"]["town"]["state"].get("minds") or {})

    private, writes = [], []
    real_update = charter_runtime.registry_for_update
    real_save = charter_runtime.save_registry
    monkeypatch.setattr(
        charter_runtime, "registry_for_update",
        lambda *a, **k: private.append(a) or real_update(*a, **k))
    monkeypatch.setattr(
        charter_runtime, "save_registry",
        lambda *a, **k: writes.append(a) or real_save(*a, **k))

    result = charter_runtime.ingest_public_evidence(
        cid, [_speech()], _scene(), turn_id=12)

    assert result == {"sources": 1, "opportunities": 2, "acquired": 1,
                      "unplaced": []}
    assert len(private) == 1
    assert len(writes) == 1
    # The appraisal read the shared object and mutated nothing in it.
    assert dict(shared["items"]["town"]["state"].get("minds") or {}) \
        == before_minds
    held = charter_runtime.registry_for(cid)["items"]["town"]["state"][
        "minds"]["reeve"]
    assert sum(1 for claim in held.values()
               if claim.get("kind") == "news") == 1
