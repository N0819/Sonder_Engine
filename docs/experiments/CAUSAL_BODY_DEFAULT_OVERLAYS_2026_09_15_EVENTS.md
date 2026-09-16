# Body-default overlay event logs — 2026-09-15

One live capture; the later entry is a zero-call fixed-code replay. The initial onset stage failed despite the final event log showing successful application.

At the washstand, Sela dabbed a small blue dot onto her left cheek. "Can you see the dot?" she asked Bram. Bram took off his grey wool cap and kept it in his left hand. "Yes, on your left cheek," he said. Sela smiled briefly. Then she wiped the blue dot completely away, leaving her cheek clean. "It is gone now," Bram said. His cap remained in his hand; neither the cap nor his skin had acquired a mark.

## initial

### Final event log

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- |
| 0 | Sela | action | applied | At the washstand, Sela dabbed a small blue dot onto her left cheek. |
| 1 | Sela | speech | recorded | Can you see the dot? |
| 2 | Bram | action | applied | Bram took off his grey wool cap and kept it in his left hand. |
| 3 | Bram | speech | recorded | Yes, on your left cheek, |
| 4 | Sela | action | recorded | Sela smiled briefly. |
| 5 | Sela | action | applied | Then she wiped the blue dot completely away, leaving her cheek clean. |
| 6 | Bram | speech | recorded | It is gone now, |

### Onset overlays and receipt

| Chrono | Sela overlays after span | Receipt |
| ---: | --- | --- |
| 1 | [] | unresolved |
| 2 | [] | recorded |
| 3 | [] | applied |
| 4 | [] | recorded |
| 5 | [] | recorded |
| 6 | [] | unchanged |
| 7 | [] | recorded |

### Bram onset view

You are in Washroom. A bright quiet room with an uncovered washstand. Both people stand face to face within easy sight and hearing. Sela is within arm's reach, at Oak washstand. Sela is standing. You are standing. You see a person of unremarkable appearance, wearing Plain linen tunic. You feel the Grey wool cap against your left hand: steady pressure and weight, continuous while the contact holds. Sela says: "Can you see the dot?" Sela smiles briefly. Sela wipes the blue dot away from her cheek.

### Bram outcome view

You are in Washroom. A bright quiet room with an uncovered washstand. Both people stand face to face within easy sight and hearing. Sela is within arm's reach, at Oak washstand. Sela is standing. You are standing. You see a person of unremarkable appearance, wearing Plain linen tunic. You feel the Grey wool cap against your left hand: steady pressure and weight, continuous while the contact holds. Sela dabs a small blue dot onto her left cheek. Sela says: "Can you see the dot?" Sela smiles briefly. Sela wipes the blue dot away from her cheek.

## fixed_code_replay

### Final event log

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- |
| 0 | Sela | action | applied | At the washstand, Sela dabbed a small blue dot onto her left cheek. |
| 1 | Sela | speech | recorded | Can you see the dot? |
| 2 | Bram | action | applied | Bram took off his grey wool cap and kept it in his left hand. |
| 3 | Bram | speech | recorded | Yes, on your left cheek, |
| 4 | Sela | action | recorded | Sela smiled briefly. |
| 5 | Sela | action | applied | Then she wiped the blue dot completely away, leaving her cheek clean. |
| 6 | Bram | speech | recorded | It is gone now, |

### Onset overlays and receipt

| Chrono | Sela overlays after span | Receipt |
| ---: | --- | --- |
| 1 | [{"name": "small blue dot on left cheek", "active": true, "from_event": 1}] | applied |
| 2 | [{"name": "small blue dot on left cheek", "active": true, "from_event": 1}] | recorded |
| 3 | [{"name": "small blue dot on left cheek", "active": true, "from_event": 1}] | applied |
| 4 | [{"name": "small blue dot on left cheek", "active": true, "from_event": 1}] | recorded |
| 5 | [{"name": "small blue dot on left cheek", "active": true, "from_event": 1}] | recorded |
| 6 | [] | applied |
| 7 | [] | recorded |

### Bram onset view

You are in Washroom. A bright quiet room with an uncovered washstand. Both people stand face to face within easy sight and hearing. Sela is within arm's reach, at Oak washstand. Sela is standing. You are standing. You see a person of unremarkable appearance, wearing Plain linen tunic. You feel the Grey wool cap against your left hand: steady pressure and weight, continuous while the contact holds. Sela dabs a small blue dot onto her left cheek. Sela says: "Can you see the dot?" Sela smiles briefly. Sela wipes the blue dot away from her cheek.

### Bram outcome view

You are in Washroom. A bright quiet room with an uncovered washstand. Both people stand face to face within easy sight and hearing. Sela is within arm's reach, at Oak washstand. Sela is standing. You are standing. You see a person of unremarkable appearance, wearing Plain linen tunic. You feel the Grey wool cap against your left hand: steady pressure and weight, continuous while the contact holds. Sela dabs a small blue dot onto her left cheek. Sela says: "Can you see the dot?" Sela smiles briefly. Sela wipes the blue dot away from her cheek.
