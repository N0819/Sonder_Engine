# Feature Coverage — Meridian demo

Auto-detected from captured pipeline steps, interpret/resolve outputs, and world snapshots.
`FIRED`=verified in engine output · `PARTIAL`=present/reachable, verify manually · `MISS`=not detected.

| Feature | Status | Evidence |
|---|---|---|
| Turn-0 establishment (rooms/cast/attire/clock/fiction_frame) | FIRED | turn 0: establishment plan ran |
| Opening perception split | FIRED | turn 0: perception_establish produced observer views |
| dialogue_mode | FIRED | turn 1: flow.dialogue_mode=true |
| addressed_to priority | FIRED | turn 1: addressed_to=[21] |
| Relationships (trust/warmth/fear) | FIRED | turn 1: aria relationship graph populated |
| Theory of Mind (tom_triggers + deep update) | FIRED | turn 27: tom_triggers=[22, 24] |
| Concealed speech (conceal_from) + verified perception exclusion | FIRED | turn 3: speech visibility=concealed, conceal_from=['char_86ed246a4af24d41924e39e8cae6b1cc', 'char_9631b28ca74f43a9ba1206f293538d2b'] — reached only intended recipient(s); concealed-from parties excluded (verified) |
| Private thought (never perceivable) | FIRED | turn 4: private_thought captured |
| Movement inference | FIRED | turn 5: movement={'to_room': 'central_corridor', 'why': 'heading toward the med bay'} |
| needs_mapping -> full mapping_stage | FIRED | turn 0: mapping_stage ran |
| mapping_quick (cached recall) | FIRED | turn 1: mapping_quick ran |
| Room creation (unmapped room entered) | FIRED | turn 1: archive_vault appears in world state |
| Location lorebook retrieval | FIRED | turn 0: mapping retrieved location lore |
| System lorebook retrieval | FIRED | turn 0: mapping retrieved system/override lore |
| Contested action + dice/difficulty | FIRED | turn 8: contested=False dice=True |
| reaction_loop (contested physical) | MISS |  |
| interaction_loop (NPCs hear each other) | FIRED | turn 1: interaction step ran |
| Parallel blind character steps (autonomy=0) | FIRED | turn 15: 2 parallel character steps under autonomy=0 |
| Background NPC reaction (pick_background_reactor) | FIRED | turn 1: background_react produced output |
| Promotable -> draft -> confirm promotion | FIRED | turn 27: PROMOTED Tomas Reyes -> char_id 24 |
| Dramatic-irony feed | FIRED | turn 1: dramatic-irony feed populated |
| Promise ledger | FIRED | turn 13: promise ledger populated |
| Paradox / fixed-point + hazard consequence | PARTIAL | fixed point declared |
| paradox_policy (mode) | FIRED | turn 0: policy={'mode': 'hazard', 'escalation_rate': 1.0, 'toll_in_radius': True} |
| Attire (clothing change) | FIRED | turn 21: attire diff includes hazard suit |
| Conditions (wounds/radiation persist) | FIRED | turn 10: conditions diff set |
| simulation_clock time_skip | FIRED | turn 17: clock jumped 10800s (time_skip) |
| Extraordinary sense / raw signal (thermal scan) | PARTIAL | turn 18: VESPER thermal-scan beat (inspect prose for raw-signal framing) |
| other_players / multiplayer (narrator_extra) | FIRED | turn 20: narrator_extra rendered for co-player |
| Narration person = first person | FIRED | turn 0: first-person narration |

**Totals:** FIRED=27 · PARTIAL=2 · MISS=1 (of 30 checks)