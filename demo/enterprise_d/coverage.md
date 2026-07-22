# Feature Coverage — Enterprise-D: The Kelvan Array

Auto-detected from captured pipeline steps + committed world state across 30 turns.
`FIRED`=verified in engine output · `MISS`=not detected.

| Feature | Status | Evidence |
|---|---|---|
| Turn-0/establishment world seed | MISS |  |
| mapping_quick (cached recall) | FIRED | turn 1: mapping_quick (cached recall) |
| mapping_stage (full lore routing) | MISS |  |
| Room creation on the fly | FIRED | turn 1: room creation on the fly (bridge, ready_room) |
| Compass bearings / vertical / anchors (spatial) | FIRED | turn 1: within-room anchors (spatial) |
| Within-room station move | MISS |  |
| Movement inference (positions) | FIRED | turn 1: movement / mapping request |
| dialogue_mode | FIRED | turn 2: dialogue_mode |
| addressed_to priority | FIRED | turn 1: addressed_to → [1] |
| Theory of Mind (deep update) | FIRED | turn 1: theory-of-mind (deep update) |
| interaction_loop (NPCs hear each other) | FIRED | turn 1: interaction_loop (NPCs hear each other) |
| reaction_loop (contested physical) | MISS |  |
| Contested action + difficulty | MISS |  |
| Dice roll | MISS |  |
| Concealed speech (conceal_from) | MISS |  |
| Whisper (volume) + proximity gating | FIRED | turn 21: whisper (volume) + proximity gating |
| Raised voice (volume) | MISS |  |
| Private thought (never perceivable) | MISS |  |
| Conditions (wounds/persist) | FIRED | turn 11: conditions (wounds/persist) |
| Attire change | MISS |  |
| Destruction / removal | MISS |  |
| Background presence tracked | FIRED | turn 3: background presence tracked (Data) |
| Promotable background NPC | FIRED | turn 4: promotable background NPC (Data) |
| PROMOTION background → cast | FIRED | turn 1: PROMOTED background → cast (Vorne, Picard) |
| background_react (unregistered NPC) | FIRED | turn 4: background_react (unregistered NPC) |
| Interior depth: blended mood (undercurrent) | FIRED | turn 2: interior depth [Picard:multi-want; Vorne:blended-mood(undercurrent); Vorne:drive-strain=0. |
| Interior depth: multiple wants | FIRED | turn 1: interior depth [Picard:multi-want] |
| Interior depth: suppressed want | MISS |  |
| Interior depth: standing intention | MISS |  |
| Drive strain accrual | FIRED | turn 2: interior depth [Picard:multi-want; Vorne:blended-mood(undercurrent); Vorne:drive-strain=0. |
| DRIVE RUPTURE window | FIRED | turn 15: Vorne: DRIVE RUPTURE window (Vale publicly frames the deaths as a consequence of Vorne's ) |
| DRIVE SHIFT (core changed) | MISS |  |
| Drive scar (former drive) | MISS |  |
| generation request (on-the-fly) | MISS |  |
| narrator_extra (co-player) | MISS |  |

**Totals:** FIRED=18 · MISS=17 (of 35 checks)