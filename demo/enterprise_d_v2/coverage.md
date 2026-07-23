# Feature Coverage — Enterprise-D: The Kelvan Array (v2)

Auto-detected from captured pipeline steps + world state across 40 player turns (+ opening). `FIRED`=verified in engine output · `MISS`=not detected.

| Feature | Status | Evidence |
|---|---|---|
| establishment world seed | FIRED | turn 0: director_establish |
| mapping_quick (cached recall) | FIRED | turn 1: cached=True |
| mapping_stage (full lore routing) | FIRED | turn 30: mapping_stage |
| room creation on the fly | FIRED | turn 0: room_bridge,room_turbolift |
| movement inference (positions) | FIRED | turn 14: positions changed |
| dialogue_mode | FIRED | turn 2: flow.dialogue_mode |
| addressed_to priority | FIRED | turn 1: → [1] |
| perception split (act/outcome) | FIRED | turn 1: perception_act |
| interaction_loop (NPCs hear each other) | FIRED | turn 1: rounds=1 |
| reaction_loop (contested physical) | MISS |  |
| contested action + difficulty | FIRED | turn 17: dice=[{'actor': 'Lt. Commander Data', 'attempt': "access the Array's core log to determine why its makers died", 'ability': 'Operations Management', 'difficulty': 'moderate', 'seed': "1:17:0:Lt. Commander Data:access the Array's core log to determine why its makers died", 'roll': 12, 'modifier': 2, 'dc': 12, 'outcome': 'success', 'margin': 2}] |
| dice roll | FIRED | turn 17: [{'actor': 'Lt. Commander Data', 'attempt': "access the Array's core log to determine why its makers died", 'ability': 'Operations Management', 'difficulty': 'moderate', 'seed': "1:17:0:Lt. Commander Data:access the Array's core log to determine why its makers died", 'roll': 12, 'modifier': 2, 'dc': 12, 'outcome': 'success', 'margin': 2}] |
| concealed speech (conceal_from) | FIRED | turn 32: conceal_from present |
| whisper (volume) + proximity gating | FIRED | turn 21: ['whisper'] |
| raised voice (volume) | MISS |  |
| private thought (never perceivable) | FIRED | turn 39: private_thought |
| conditions (wounds/persist) | MISS |  |
| attire change | MISS |  |
| destruction / removal | MISS |  |
| background presence tracked | FIRED | turn 3: 1 |
| PROMOTION background → cast | FIRED | turn 10: Lt. Cmdr. Geordi La Forge |
| background_react (unregistered NPC) | FIRED | turn 4: ['Lt. Commander Data'] |
| theory-of-mind (deep update) | FIRED | turn 1: Captain Picard:2 |
| interior: blended mood (undercurrent) | FIRED | turn 2: Dr. Vorne:controlled intensity/defensiveness |
| interior: multiple wants | FIRED | turn 1: Captain Picard:2 |
| interior: suppressed want | FIRED | turn 2: Dr. Vorne |
| interior: standing intention | MISS |  |
| drive strain accrual | FIRED | turn 9: Dr. Vorne=0.1575 |
| DRIVE RUPTURE window | FIRED | turn 18: Dr. Vorne expires=21 |
| DRIVE SHIFT (core changed) | MISS |  |
| drive scar (former drive) | MISS |  |
| generation request (on-the-fly) | FIRED | turn 30: [{'kind': 'room', 'subject': 'Ready Room', 'location_id': 'room_ready_room', 'constraints': ['adjacent to the main bridge', 'private office/conference space for the captain', 'contains a desk, chairs, possibly a sofa and a replicator'], 'urgency': 'immediate'}] |
| obligation ledger (pending_obligations) | FIRED | turn 11: 1 open |
| time_skip | FIRED | turn 1: Stardate 46357.4, 14:32 hours -> A moment passes. |

**Totals:** FIRED=26 · MISS=8 (of 34 checks)

**Export/import round-trip:** OK — imported 41/41 turns, 6 cast, 349 memories, scene=True.