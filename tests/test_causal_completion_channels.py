"""An exact hand accidentally put in the channel field still has one owner."""
from agents.director import _completion_requests, _rows_to_forward
from llm.llm_quality import _step_json_schema


def test_captured_hatch_referral_reaches_objects_without_guessing_a_channel():
    jobs = [("contact", {"ledger_items": [
        {"chrono_id": 2, "item_ids": [1], "item_names": ["Blue tin"],
         "categories": ["containment"], "event": "opens the blue tin"}]})]
    results = {"contact": {"results": [{
        "status": "not_mine", "transforms": [], "required_channels": ["objects"]}]}}
    requests = _completion_requests(jobs, results)
    forwarded = _rows_to_forward(jobs, results, {}, requests)
    assert set(forwarded) == {"objects"}
    entry = forwarded["objects"][0]
    assert entry["chrono_id"] == 2 and entry["full_scope"]
    assert entry["channels"] == []

    results["contact"]["results"][0]["required_channels"] = ["objectish"]
    assert _rows_to_forward(jobs, results, {}) == {}


def test_wire_advertises_channels_not_hand_names_for_completion_requests():
    schema = _step_json_schema("director_spatial")
    definitions = schema.get("$defs", schema.get("definitions"))
    names = definitions["LedgerTransformResult"]["properties"]["required_channels"]["items"]["enum"]
    assert "inventory_ops" in names and "contact_ops" in names and "entities" in names
    assert "objects" not in names


def test_worn_known_garment_requests_body_even_without_model_referral():
    scene = {'entities': {'coat': {'name': 'Violet coat', 'state': {'clothing': True}}}}
    row = {'chrono_id': 3, 'item_ids': [1, 2], 'item_names': ['Noa', 'Violet coat']}
    jobs = [('objects', {'ledger_items': [row]})]
    results = {'objects': {'results': [{'status': 'encoded', 'transforms': [
        {'item': 'Violet coat', 'patch': {'inventory_ops': [
            {'object_id': 'coat', 'to_id': 'Noa', 'relation': 'worn'}]}}]}]}}
    requests = _completion_requests(jobs, results, scene=scene)
    assert len(requests) == 1
    assert requests[0]['to'] == 'body'
    assert requests[0]['channels'] == ['attire']
    assert _rows_to_forward(jobs, results, {}, requests)['body'][0]['chrono_id'] == 3
    transform = results['objects']['results'][0]['transforms'][0]
    transform['item'] = 'Some other coat'
    assert _completion_requests(jobs, results, scene=scene) == []
    transform['item'] = 'Violet coat'
    scene['entities']['coat']['state'] = {}
    assert _completion_requests(jobs, results, scene=scene) == []


def test_worn_garment_dependency_dispatches_owner_and_restores_wardrobe(temp_db, monkeypatch):
    from copy import deepcopy
    from agents import director
    from tests.test_director_orchestration import BASE_SCENE, _make_ctx, _fake_agent
    from persist.commit import compose_beat_scene
    initial = deepcopy(BASE_SCENE)
    initial['entities']['coat'] = {'name': 'Violet coat', 'kind': 'object', 'portable': True,
                                  'state': {'clothing': True, 'garment': 'Violet coat', 'shed': True}}
    initial['positions']['coat'] = 'keeper_room'
    initial['contained'] = {'coat': {'in': 'Mara', 'mode': 'held'}}
    initial['attire']['Mara'] = {'wearing': [], 'regions': {}}
    calls = []
    responses = {'director_resolve': {'ledgers': [
        {'chrono_id': 1, 'item_ids': [1, 2], 'item_names': ['Mara', 'Violet coat'],
         'source_entity_id': 'character:mara', 'event': 'Mara puts the coat on.',
         'commitment': 'asserted', 'resolution_notes': 'The coat is worn.',
         'categories': ['inventory_ops']}]},
        'director_objects': {'results': [{'status': 'encoded', 'settled': {}, 'transforms': [
            {'item': 'Violet coat', 'patch': {'inventory_ops': [
                {'op': 'transfer', 'object_id': 'coat', 'from_id': 'Mara', 'to_id': 'Mara', 'relation': 'worn'}]}}]}]},
        'director_body': {'results': [{'status': 'encoded', 'settled': {}, 'transforms': [
            {'item': 'Violet coat', 'patch': {'attire': {'Mara': {'add': ['Violet coat']}}}}]}]}}
    monkeypatch.setattr(director, '_agent_json', _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, scene=initial, interp={'sequence': []})
    out = director.director_resolve(ctx, 0)
    ctx.director_resolve = out
    assert out['orchestration']['forwards'] == {'body': [1]}
    body = next(call['payload'] for call in calls if call['step_key'] == 'director_body')
    assert body['ledgers'][0]['requested_channels'] == ['attire']
    composed = compose_beat_scene(ctx)
    assert 'Violet coat' in composed.scene['attire']['Mara']['wearing']
    assert composed.scene['contained']['coat']['mode'] == 'worn'
    assert composed.causal_worlds[0]['completion']['action_status'] == 'applied'
