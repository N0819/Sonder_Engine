"""A supplemental owner must not reason over writes compilation will reject."""

from agents import director


def _prior(name, patches, *, categories, status="encoded", settled=None):
    ledger = {"chrono_id": 1, "event_id": 1, "item_id": 7, "item_ids": [7],
              "item_names": ["Cup"], "categories": categories,
              "source_event_id": "turn:1:raw"}
    return director._earlier_specialist_work(name, 2, {
        name: {"ledger_items": [ledger]},
    }, {name: {"results": [{"status": status,
                           "transforms": [{"item": "Cup", "patch": patch}
                                          for patch in patches],
                           "settled": settled or {}}]}}, {})


def test_prior_work_keeps_owned_transfer_and_drops_unowned_contact():
    prior = _prior("objects", [{
        "inventory_ops": [{"op": "pickup", "object_id": "cup", "to_id": "Mara",
                           "from_event": 991}],
        "contact_ops": [{"op": "add", "actor": "Mara", "target": "cup"}],
    }], categories=["inventory_ops"])
    assert len(prior) == 1
    assert prior[0]["result"]["transforms"] == [{"item": "Cup", "patch": {
        "inventory_ops": [{"op": "pickup", "object_id": "cup", "to_id": "Mara"}],
    }}]
    assert not {"chrono_id", "event_id", "item_id", "item_ids"} & prior[0]["ledger"].keys()


def test_prior_work_omits_encoded_row_when_its_only_write_is_rejected():
    assert _prior("objects", [{"contact_ops": [{"op": "clear", "actor": "Mara"}]}],
                  categories=["inventory_ops"]) == []
    assert _prior("social", [{"world_facts": ["No train arrives before noon"]}],
                  categories=["speech", "world_facts"]) == []


def test_prior_speech_claim_rejection_preserves_its_public_evidence():
    prior = _prior("social", [{
        "world_facts": ["No train arrives before noon"],
        "public_evidence": [{"source_id": "speech:1", "salience": 0.5}],
    }], categories=["speech", "world_facts", "public_evidence"])
    assert prior[0]["result"]["transforms"] == [{"item": "Cup", "patch": {
        "public_evidence": [{"source_id": "speech:1", "salience": 0.5}],
    }}]


def test_prior_independent_fact_remains_but_unverified_completion_does_not():
    prior = _prior("social", [{"world_facts": ["The railway is closed."]}],
                   categories=["world_facts"])
    assert prior[0]["result"]["transforms"][0]["patch"] == {
        "world_facts": ["The railway is closed."]}
    prior = _prior("objects", [], categories=["inventory_ops"], status="already_true",
                   settled={"Cup": "already_true", "Unknown person": "already_true"})
    assert prior == []


def test_prior_entity_mint_can_be_followed_by_partial_patch_in_same_row():
    prior = _prior("objects", [
        {"entities": {"cup": {"name": "Cup", "portable": True}}},
        {"entities": {"cup": {"state": {"cracked": True}}}},
    ], categories=["entities"])
    assert len(prior[0]["result"]["transforms"]) == 2
    assert prior[0]["result"]["transforms"][1]["patch"]["entities"]["cup"][
        "state"]["cracked"] is True


def test_extension_prior_work_uses_its_owned_channel_without_a_core_schema(monkeypatch):
    channel = "ext:sample:annotation"
    monkeypatch.setitem(director.SPECIALISTS, "sample", {
        "step_key": "ext:sample:specialist", "channels": [channel], "ext_id": "sample",
    })
    prior = _prior("sample", [{channel: {"cup": {"label": "inspected"}}}],
                   categories=[channel])
    assert prior[0]["result"]["transforms"][0]["patch"] == {
        channel: {"cup": {"label": "inspected"}}}
