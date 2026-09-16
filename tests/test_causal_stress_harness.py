"""Stress evidence must distinguish an event account from actual world state."""
from copy import deepcopy
import hashlib
import json
import socket
from types import SimpleNamespace

import pytest

from tools import causal_stress as harness


def _result():
    world = {"entities": {"tin": {"name": "Tin", "state": {"hatch": "closed"}}},
             "contained": {"tin": {"in": "Mira", "mode": "held"}},
             "stations": {"tin": {"at": "shelf"}}, "contacts": []}
    return {"case": {"id": "sample", "expectations": {
        "events": [{"id": "e01", "checks": [{"kind": "parent", "entity": "tin", "equals": None}]}],
        "quotes": [{"speaker": "Mira", "text": "Done."}],
        "final": [{"kind": "parent", "entity": "tin", "equals": None}]}},
        "event_log": {"events": [{"actor": "Mira", "kind": "action", "account": "sets down the tin"},
                                 {"actor": "Mira", "kind": "speech", "text": "Done."}]},
        "final_scene": world,
        "causal_worlds": [{"stage": "interpret", "chrono_id": 7, "after": world}]}


def test_complete_event_log_does_not_acquit_missing_release():
    score = harness.score_result(_result(), {"e01": {"stage": "interpret", "chrono_id": 7}})
    assert score["counts"] == {"pass": 1, "fail": 2, "unreviewed": 0, "reviewed": 0}


def test_expected_event_numbers_are_never_assumed_to_be_chronology_ids():
    score = harness.score_result(_result())
    assert score["counts"]["unreviewed"] == 1
    assert score["checks"][0]["status"] == "unreviewed"


def test_quote_scoring_requires_speaker_and_preserves_multiplicity():
    result = _result()
    result["case"]["expectations"]["quotes"] *= 2
    checks = [c for c in harness.score_result(result)["checks"] if "quote" in c]
    assert [c["status"] for c in checks] == ["pass", "fail"]
    result["event_log"]["events"][-1]["actor"] = "Someone else"
    checks = [c for c in harness.score_result(result)["checks"] if "quote" in c]
    assert all(c["status"] == "fail" for c in checks)


def test_quote_scoring_normalizes_typographic_glyphs_inside_a_recollection():
    result = _result()
    result["case"]["expectations"]["quotes"] = [{"speaker": "Mira", "text": "You said, ‘Open it,’ yesterday."}]
    result["event_log"]["events"][-1]["text"] = "You said, 'Open it,' yesterday,"
    assert next(c for c in harness.score_result(result)["checks"] if "quote" in c)["status"] == "pass"


def test_release_check_refuses_a_residual_grip():
    scene = {"attire": {"Mira": {}}, "contacts": [{"actor": "Mira", "target": "tin", "manner": "grip"}]}
    assert harness.check_world(scene, {"kind": "no_grip", "entity": "tin"})["status"] == "fail"


def test_release_check_does_not_mistake_a_mechanical_clip_for_a_persons_grip():
    scene = {"attire": {"Mira": {}}, "contacts": [{"actor": "tag", "target": "bag", "manner": "grip"}]}
    assert harness.check_world(scene, {"kind": "no_grip", "entity": "tag"})["status"] == "pass"


def test_holder_alias_is_resolved_against_actual_world_identity():
    scene = {"entities": {"char_mira": {"name": "Mira", "kind": "person"}},
             "contained": {"tin": {"in": "char_mira", "mode": "held"}}}
    assert harness.check_world(scene, {"kind": "parent", "entity": "tin", "equals": "Mira"})["status"] == "pass"
    assert harness.check_world(scene, {"kind": "parent", "entity": "tin", "equals": "Mara"})["status"] == "fail"


def test_posture_assertions_use_the_engines_typed_aliases():
    check = {"kind": "path", "path": ["poses", "Mira", "posture"], "equals": "sitting"}
    assert harness.check_world({"poses": {"Mira": {"posture": "seated"}}}, check)["status"] == "pass"
    assert harness.check_world({"poses": {"Mira": {"posture": "standing"}}}, check)["status"] == "fail"


def test_replay_never_uses_a_previously_rejected_reply(monkeypatch):
    from llm import schemas
    monkeypatch.setattr(schemas, "validate_llm_output_strict",
                        lambda *args, **kwargs: SimpleNamespace(valid=True, output=args[1]))
    replies = harness.CapturedReplies([
        {"role": "director", "ok": False, "response": '{"wrong":true}'},
        {"role": "director", "ok": True, "response": '{"accepted":true}', "payload": {}, "system": "x"},
    ])
    assert replies("director", "director_interpret", "x", {}) == {"accepted": True}
    assert replies.records[0]["index"] == 1
    assert not replies.unused()
    with pytest.raises(RuntimeError, match="No accepted captured reply"):
        replies("director", "director_resolve", "x", {})


def test_replay_fails_on_changed_contract_instead_of_skipping_a_chronological_reply(monkeypatch):
    from llm import schemas
    monkeypatch.setattr(schemas, "validate_llm_output_strict",
                        lambda *args, **kwargs: SimpleNamespace(valid=False, errors=["invalid"]))
    replies = harness.CapturedReplies([
        {"role": "director_objects", "ok": True, "response": '{}'},
        {"role": "director_objects", "ok": True, "response": '{}'},
    ])
    with pytest.raises(RuntimeError, match="fails current contract"):
        replies("director_objects", "director_objects", "", {})
    assert replies.unused() == [1]


def test_replay_guard_blocks_transport_and_dns_then_restores_them():
    original = socket.getaddrinfo
    with harness.no_network():
        with pytest.raises(RuntimeError, match="Network is disabled"):
            socket.getaddrinfo("example.invalid", 443)
        # Call the patched entry points without allocating a socket; some
        # test sandboxes correctly forbid allocation before connect is reached.
        with pytest.raises(RuntimeError, match="Network is disabled"):
            socket.socket.connect(None, ("127.0.0.1", 443))
        with pytest.raises(RuntimeError, match="Network is disabled"):
            socket.socket.connect_ex(None, ("127.0.0.1", 443))
    assert socket.getaddrinfo is original


def test_corpus_has_unique_reviewable_event_sources_and_grounded_bodies():
    cases = harness.load_cases(harness.DEFAULT_CORPUS)
    assert len(cases) == 5
    for case in cases:
        events = case["expectations"]["events"]
        assert len({event["id"] for event in events}) == len(events)
        assert all(event["source"] in case["prose"] for event in events)
        assert all(name in case["scene"]["attire"]
                   for name in [case["primary_name"]] + case["characters"])
        for check in case["expectations"]["final"]:
            harness.check_world(case["scene"], check)


def test_case_paths_and_selections_are_validated_before_any_database_work(tmp_path):
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps([{"id": "../elsewhere"}]))
    with pytest.raises(ValueError, match="safe directory"):
        harness.load_cases(corpus)
    corpus.write_text(json.dumps([{"id": "one"}]))
    with pytest.raises(ValueError, match="Unknown case"):
        harness.load_cases(corpus, ["two"])


def test_existing_database_is_never_reused_or_overwritten(tmp_path):
    existing = tmp_path / "scratch.db"
    existing.write_bytes(b"original")
    with pytest.raises(ValueError, match="already exists"):
        harness.prepare_database(existing)
    assert existing.read_bytes() == b"original"


def test_later_world_snapshot_replaces_the_same_onset_boundary():
    result = _result()
    result["onset_worlds"] = deepcopy(result["causal_worlds"])
    result["causal_worlds"][0]["after"] = {"contained": {}}
    snapshots = harness.world_snapshots(result)
    assert len(snapshots) == 1
    assert snapshots[("interpret", 7)]["after"] == {"contained": {}}


def test_configuration_copy_is_read_only_and_secret_exports_are_refused(tmp_path, temp_db):
    from core import db
    previous = db.DB
    source = tmp_path / "source.db"
    secret = "test-provider-key-do-not-export-239875"
    try:
        db.configure(str(source))
        db.init()
        db.qi("INSERT INTO providers(name,kind,base_url,api_key,enabled) VALUES(?,?,?,?,?)",
              ("fixture", "openrouter", "https://example.invalid/v1", secret, 1))
        db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
              ("Production-like story must stay behind", "", 1))
        db.set_setting("host_username", "source-owner")
        db.close_connection()
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        scratch = harness.prepare_database(tmp_path / "scratch.db", source)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        assert db.q("SELECT count(*) AS n FROM chats", one=True)["n"] == 0
        assert not db.get_setting("host_username")
        assert db.q("SELECT api_key=? AS matches FROM providers", (secret,), one=True)["matches"]
        assert scratch.stat().st_mode & 0o777 == 0o600
        output = tmp_path / "unsafe.json"
        with pytest.raises(RuntimeError, match="configured secret"):
            harness.save_artifact(output, {"accidental": secret}, scratch)
        assert not output.exists()
    finally:
        db.close_connection()
        db.configure(previous)


def test_replay_preparation_has_no_provider_credentials(tmp_path, temp_db):
    from core import db
    previous = db.DB
    try:
        harness.prepare_database(tmp_path / "replay.db", captured_settings={
            "ui_language": "en", "host_username": "not-copied", "research_key": "not-copied"})
        assert not db.q("SELECT 1 FROM providers WHERE enabled=1 OR api_key!=''")
        assert not db.get_setting("host_username")
        assert not db.get_setting("research_key")
    finally:
        db.close_connection()
        db.configure(previous)


def test_evidence_bundle_rehydrates_exact_prompts_without_a_database(tmp_path):
    bundle = {"corpus": {"cases": [{"id": "one", "prose": "Mira opens a tin."}]},
              "prompts": {"digest": "exact captured prompt"},
              "runs": [{"label": "initial", "cases": [{"case_id": "one", "exchanges": [
                  {"role": "director", "system_sha256": "digest", "ok": True, "response": "{}"}]}]}]}
    source = tmp_path / "evidence.json"
    source.write_text(json.dumps(bundle))
    with harness.no_network():
        harness.unpack_evidence(source, tmp_path / "restored", "initial")
    result = json.loads((tmp_path / "restored/one/result.json").read_text())
    assert result["case"] == bundle["corpus"]["cases"][0]
    assert result["exchanges"][0]["system"] == "exact captured prompt"
    assert not list((tmp_path / "restored").glob("**/*.db"))
