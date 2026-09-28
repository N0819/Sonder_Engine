"""An exact hand accidentally put in the channel field still has one owner.

The forwarding round (`_rows_to_forward`), a hand's `not_mine` referral and
the hands' wire enum went with the causal hands on 2026-09-27: the encoder
writes every channel itself, so what a completion request names is checked
against its one answer rather than forwarded to another hand.
"""
from agents.director import _completion_requests


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
    transform = results['objects']['results'][0]['transforms'][0]
    transform['item'] = 'Some other coat'
    assert _completion_requests(jobs, results, scene=scene) == []
    transform['item'] = 'Violet coat'
    scene['entities']['coat']['state'] = {}
    assert _completion_requests(jobs, results, scene=scene) == []


def test_worn_garment_dependency_dispatches_owner_and_restores_wardrobe(
        temp_db, monkeypatch, prose_director):
    """One encoder event carries both writes -- the worn transfer and the
    wardrobe entry -- where the causal path needed the objects hand's answer
    forwarded to the body hand."""
    from copy import deepcopy
    from agents import director
    from tests.director_fakes import BASE_SCENE, _make_ctx, _fake_agent, encoder_event
    from persist.commit import compose_beat_scene
    initial = deepcopy(BASE_SCENE)
    initial['entities']['coat'] = {'name': 'Violet coat', 'kind': 'object', 'portable': True,
                                  'state': {'clothing': True, 'garment': 'Violet coat', 'shed': True}}
    initial['positions']['coat'] = 'keeper_room'
    initial['contained'] = {'coat': {'in': 'Mara', 'mode': 'held'}}
    initial['attire']['Mara'] = {'wearing': [], 'regions': {}}
    coat_on = encoder_event(
        'Mara puts the coat on.', source='character:mara', transforms=[
            {'item': 'Violet coat', 'patch': {'inventory_ops': [
                {'op': 'transfer', 'object_id': 'coat', 'from_id': 'Mara',
                 'to_id': 'Mara', 'relation': 'worn'}]}},
            {'item': 'Violet coat', 'patch': {'attire': {'Mara': {'add': ['Violet coat']}}}}])
    responses = {'director_prose': {'prose': 'Mara puts the coat on.'},
                 'director_specialist': {'events': [coat_on], 'missing_tools': [],
                                         'missing_referents': [], 'notes': []}}
    monkeypatch.setattr(director, '_agent_json', _fake_agent([], responses))
    ctx = _make_ctx(temp_db, scene=initial, interp={'sequence': []})
    out = director.director_resolve(ctx, 0)
    ctx.director_resolve = out
    composed = compose_beat_scene(ctx)
    assert 'Violet coat' in composed.scene['attire']['Mara']['wearing']
    assert composed.scene['contained']['coat']['mode'] == 'worn'
    assert composed.causal_worlds[0]['completion']['action_status'] == 'applied'
