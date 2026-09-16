"""Readable perception preserves the observer's evidence and delivery boundaries."""
from copy import deepcopy

from agents import composer
from agents.character import _character_perception
from agents.character_kernel import compact_character_evidence, expand_character_evidence
from llm.schemas import Observation


def _rendered(*rows):
    spans = []
    for i, (actor, text, phase, kind, channel) in enumerate(rows):
        spans.append((composer.Percept(
            kind=kind, channel=channel, source_label=actor,
            order_key=i if phase == 'event' else None,
            data={'beat': phase == 'change'}, dedupe_key=f'row:{i}'), text))
    return composer.RenderedView(
        text=' '.join(text for _, text in spans), spans=spans,
        standing_keys=set(), described=set())


def test_adjacent_actors_keep_separate_actions_and_citations():
    rendered = _rendered(
        ('Alice', 'Alice opens the door.', 'event', 'act', 'sight'),
        ('Bob', 'Bob takes the cup.', 'event', 'act', 'sight'))
    rows = composer.observations_from_render('7', rendered)
    assert [(r['actor'], r['observed']['text']) for r in rows] == [
        ('Alice', 'Alice opens the door.'), ('Bob', 'Bob takes the cup.')]
    assert len({r['observation_id'] for r in rows}) == 2
    assert [r['order'] for r in rows] == [0, 1]


def test_crowded_scene_keeps_every_quote_and_action_in_order():
    source = []
    for i in range(30):
        actor = ('Alice', 'Bob')[i % 2]
        source.append((actor, f'{actor} says: "Line {i}."',
                       'event', 'speech', 'hearing'))
        source.append((actor, f'{actor} raises finger {i}.',
                       'event', 'act', 'sight'))
    rendered = _rendered(*source)
    rows = composer.observations_from_render('7', rendered)
    packet = composer.perception_packet(rows)
    assert len(packet['events']) == 60
    assert [r['observed']['text'] for r in packet['events']] == [r[1] for r in source]
    assert [r['actor'] for r in packet['events']] == [r[0] for r in source]
    assert all(r['observed']['text'] in rendered.text for r in rows)


def test_noticed_change_has_no_invented_time_and_stays_separate_from_state():
    rendered = _rendered(
        ('Alice', 'Alice is seated.', 'state', 'pose', 'sight'),
        ('Bob', 'Bob says: "Look."', 'event', 'speech', 'hearing'),
        ('Alice', 'Alice has flushed cheeks.', 'change', 'appearance', 'sight'))
    rows = composer.observations_from_render('7', rendered)
    packet = composer.perception_packet(rows)
    assert [r['phase'] for r in packet['events']] == ['event']
    assert [r['phase'] for r in packet['changes_noticed']] == ['change']
    assert [r['phase'] for r in packet['current_state']] == ['state']
    assert 'order' not in packet['changes_noticed'][0]
    assert packet['changes_noticed'][0]['standing'] is False
    assert packet['current_state'][0]['standing'] is True


def test_state_is_grouped_by_owner_without_coalescing_evidence():
    rendered = _rendered(
        ('Alice', 'Alice is seated.', 'state', 'pose', 'sight'),
        ('Bob', 'Bob is standing.', 'state', 'pose', 'sight'),
        ('Alice', 'Alice wears a red coat.', 'state', 'appearance', 'sight'))
    rows = composer.observations_from_render('7', rendered)
    before = deepcopy(rows)
    packet = composer.perception_packet(rows)
    assert [r['actor'] for r in packet['current_state']] == ['Alice', 'Alice', 'Bob']
    assert {r['observation_id'] for r in packet['current_state']} == {
        r['observation_id'] for r in rows}
    assert rows == before


def test_grouped_presence_does_not_claim_one_actor_owns_the_whole_group():
    rendered = _rendered(
        ('Alice', 'Alice is nearby, and Bob is by the door.', 'state', 'presence', 'sight'))
    [row] = composer.observations_from_render('7', rendered)
    assert 'actor' not in row
    assert row['observed']['text'] == rendered.text


def test_uncertain_unidentified_delivery_never_gains_a_name_or_full_quote():
    percept = composer.speech_percept(
        {'speaker': 'Secret Person', 'text': 'The vault opens at midnight.'},
        {'same_room': True, 'source_enclosed': True}, '7',
        display='a voice', can_see=False, order_key=1)
    rendered = composer.render_view([percept], mode='character')
    packet = composer.perception_packet(composer.observations_from_render('7', rendered))
    [event] = packet['events']
    assert event['fidelity'] == 'ambiguous'
    assert event['ambiguity'] >= 0.5
    assert 'Secret Person' not in str(packet)
    assert 'The vault opens at midnight.' not in str(packet)
    assert event['observed']['text'] in rendered.text


def test_legacy_observations_keep_their_existing_standing_verdict():
    rows = [
        {'observation_id': 'a', 'standing': True, 'observed': {'text': 'The room is dim.'}},
        {'observation_id': 'b', 'standing': False, 'observed': {'text': 'A bell rings.'}},
        {'observation_id': 'c', 'observed': {'text': 'An older delivered event.'}},
    ]
    packet = composer.perception_packet(rows)
    assert [r['observation_id'] for r in packet['current_state']] == ['a']
    assert [r['observation_id'] for r in packet['events']] == ['b', 'c']


def test_prose_only_archive_stays_context_instead_of_guessed_events():
    text = 'Someone said: "Then go." A door might have closed.'
    packet = composer.perception_packet([], fallback_view=text)
    assert packet['events'] == packet['changes_noticed'] == packet['current_state'] == []
    assert packet['unstructured_context'][0]['observed']['text'] == text


def test_partition_preserves_citation_handles_and_expansion():
    rendered = _rendered(
        ('Alice', 'Alice sits.', 'state', 'pose', 'sight'),
        ('Bob', 'Bob says: "Stay."', 'event', 'speech', 'hearing'))
    rows = composer.observations_from_render('7', rendered)
    payload, handles = compact_character_evidence({
        'perception': composer.perception_packet(rows)})
    event = payload['perception']['events'][0]
    state = payload['perception']['current_state'][0]
    assert event['observation_id'] == 'o1'
    assert state['observation_id'] == 'o2'
    expanded = expand_character_evidence(
        {'observations_used': ['o1', 'o2']}, handles)
    assert expanded['observations_used'] == [rows[1]['observation_id'], rows[0]['observation_id']]


def test_observation_schema_preserves_timing_and_owner_on_round_trip():
    [row] = composer.observations_from_render('7', _rendered(
        ('Alice', 'Alice opens the door.', 'event', 'act', 'sight')))
    model = Observation(**row)
    assert model.phase == 'event' and model.order == 0
    assert model.actor == 'Alice' and model.kind == 'act'


def test_character_selects_observations_matching_the_selected_round():
    base = {'observation_id': 'base', 'observed': {'text': 'The room is dim.'}}
    step = {'observation_id': 'micro', 'phase': 'event', 'observed': {'text': 'Alice speaks.'}}
    ctx = {'perception_act': {'views': {'7': 'The room is dim.'}, 'observations': {'7': [base]}},
           'interaction_views': {7: 'The room is dim. Alice speaks.'},
           'interaction_observations': {7: [base, step]}}
    assert _character_perception(ctx, 7, 'n') == (ctx['interaction_views'][7], [base, step])
    ctx['reaction_views'] = {7: 'The room is dim.'}
    ctx['reaction_observations'] = {7: [base]}
    assert _character_perception(ctx, 7, 'n') == ('The room is dim.', [base])


def test_character_archive_fallback_never_reuses_stale_metadata():
    ctx = {'perception_act': {'views': {'7': 'Old view'}, 'observations': {'7': [{'actor': 'Wrong'}]}},
           'interaction_views': {7: 'New delivery'}}
    view, rows = _character_perception(ctx, 7, 'r2')
    assert view == 'New delivery'
    assert rows[0]['phase'] == 'context'
    assert rows[0]['observation_id'] == 'current:7:micro:r2'
    assert 'Wrong' not in str(rows)


def test_partial_legacy_observations_preserve_uncovered_view_without_repeating_rows():
    text = 'A bell rings. The lamps are dim.'
    row = {'observation_id': 'o', 'phase': 'event', 'observed': {'text': 'A bell rings.'}}
    packet = composer.perception_packet([row], fallback_view=text)
    assert packet['events'] == [{**row, 'order': 1}]
    assert packet['unstructured_context'][0]['observed']['text'] == 'The lamps are dim.'
    assert 'A bell rings.' not in str(packet['unstructured_context'])


def test_attribution_audit_reads_the_composers_actual_action_kind():
    from agents.common import _check_action_attribution
    rows = composer.observations_from_render('player', _rendered(
        ('Alice', 'Alice releases the silver necklace.', 'event', 'act', 'sight')))
    warnings = _check_action_attribution(
        'Bob releases the silver necklace.', rows, present_labels=['Alice', 'Bob'])
    assert len(warnings) == 1 and 'Alice' in warnings[0]
    assert _check_action_attribution(
        'Alice releases the silver necklace.', rows, present_labels=['Alice', 'Bob']) == []


def test_location_fragment_does_not_create_double_sentence_stops():
    presence = composer.Percept(kind='presence', channel='sight', source_label='Alice',
                                data={'tier': 'near', 'at': 'the damp sand.'})
    for brief in (False, True):
        rendered = composer._render_presence_group([(presence, brief, False)])
        assert 'sand..' not in rendered[0][1]
        assert 'sand.' in rendered[0][1]


def test_identity_repair_scrubs_owner_metadata_with_the_same_boundary():
    from agents.perception import _repaired_observations
    row = {'observation_id': 'o', 'actor': 'The Doctor', 'kind': 'act',
           'observed': {'text': 'The Doctor opens the door.'}}
    # Obtain the same deterministic anonymous wording as the existing repair.
    from agents.common import _scrub_unknown_identities
    from agents.perception import _composer_unknown_sources
    roster = [{'name': 'Hinami'}, {'name': 'The Doctor'}]
    recognized, unknown = _composer_unknown_sources('Hinami', {}, roster)
    safe, _ = _scrub_unknown_identities(
        row['observed']['text'], allowed_forms=['Hinami', *recognized], unknown_sources=unknown)
    [repaired] = _repaired_observations([row], safe, 'Hinami', {}, roster)
    assert 'The Doctor' not in str(repaired)
    assert repaired['observed']['text'] == safe


def test_archived_observations_cannot_restore_text_removed_from_the_view():
    hidden = {'observation_id': 'old', 'observed': {'text': 'Secret Person opened the vault.'}}
    packet = composer.perception_packet([hidden], fallback_view='A muffled sound reaches you.')
    assert not packet['events']
    assert 'Secret Person' not in str(packet)
    assert packet['unstructured_context'][0]['observed']['text'] == 'A muffled sound reaches you.'


def test_archived_actor_metadata_cannot_identify_an_admitted_anonymous_voice():
    from agents.narration import _narrator_perception_fields

    text = 'You hear a voice say: "Wait."'
    for phase in (None, '', 'legacy'):
        row = {'observation_id': 'old', 'actor': 'Secret Person',
               'kind': 'speech', 'channel': 'hearing',
               'observed': {'text': text}}
        if phase is not None:
            row['phase'] = phase
        original = deepcopy(row)
        packet = composer.perception_packet([row], fallback_view=text)
        narrator = _narrator_perception_fields([row], text)
        assert 'Secret Person' not in str(packet)
        assert 'Secret Person' not in str(narrator)
        assert packet['events'][0]['observed']['text'] == text
        assert narrator['current_events'][0]['text'] == text
        assert row == original


def test_accumulated_micro_rounds_have_one_delivery_order_on_the_wire():
    rows = [
        {'observation_id': f'current:7:micro:{round_}:{slot}',
         'phase': 'event', 'order': slot,
         'observed': {'text': f'Round {round_}, line {slot}.'}}
        for round_ in (0, 1) for slot in (0, 1)
    ]
    packet = composer.perception_packet(rows)
    assert [r['order'] for r in packet['events']] == [1, 2, 3, 4]
    assert [r['order'] for r in rows] == [0, 1, 0, 1]
    assert [r['observation_id'] for r in packet['events']] == [r['observation_id'] for r in rows]
