# Prompt clarity event logs — 2026-09-15

First-pass results and later regression captures are separate. Execution accounts do not certify state or observer delivery; see the audit.

## initial

### flasks_exchange_unchanged_support

The last of the rain whispered against the dispensary window. Mara lifted the striped glass flask from the oak counter. She opened its hinged cap, then snapped the cap shut. "Take the striped one; I will take the dotted one," she told Eren. In one exchange, she handed him the striped flask while taking the dotted flask from his hand. Eren set the striped flask on the counter and let go. "Yesterday you said, 'Open the dotted one,'" he remarked, leaving both caps shut. Mara put the dotted flask on the low stool and released it. Eren lifted the striped flask from the counter, then passed it back to Mara. "Both can wait here," she said. She set the striped flask beside the dotted flask on the stool and let go. The oak counter itself had not moved.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- |
| 0 | Mara | action | pending | The last of the rain whispered against the dispensary window. |
| 1 | Mara | action | applied | Mara lifted the striped glass flask from the oak counter. |
| 2 | Mara | action | applied | She opened its hinged cap. |
| 3 | Mara | action | applied | then snapped the cap shut. |
| 4 | Mara | speech | recorded | Take the striped one; I will take the dotted one, |
| 5 | Mara | action | applied | In one exchange, she handed him the striped flask while taking the dotted flask from his hand. |
| 6 | Eren | action | applied | Eren set the striped flask on the counter and let go. |
| 7 | Eren | speech | recorded | Yesterday you said, 'Open the dotted one,' |
| 8 | Mara | action | applied | Mara put the dotted flask on the low stool and released it. |
| 9 | Eren | action | applied | Eren lifted the striped flask from the counter. |
| 10 | Eren | action | applied | then passed it back to Mara. |
| 11 | Mara | speech | recorded | Both can wait here, |
| 12 | Mara | action | applied | She set the striped flask beside the dotted flask on the stool and let go. |

### partial_key_insertion_failed_turn

Dust shone in the slant of afternoon light above the maple bench. Neri picked up the short silver key, leaving the long silver key where it lay. "Try the short one first," Olan said. Keeping her fingers around its bow, Neri pushed the short key partway into the red cashbox's lock; its tip entered the keyway, but its shoulder stopped outside. She tried to turn the key, but it would not rotate and the cashbox stayed locked and shut. "Wrong key," she said. She pulled the short key completely out of the lock. Then she laid it on the bench and released it. Olan picked up the long silver key and, after a pause, set it back beside the short one and let go. "Neither has opened it," he said.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- |
| 0 | Neri | action | applied | Neri picked up the short silver key, leaving the long silver key where it lay. |
| 1 | Olan | speech | recorded | Try the short one first, |
| 2 | Neri | action | unresolved | Neri pushed the short key partway into the red cashbox's lock; its tip entered the keyway, but its shoulder stopped outside. |
| 3 | Neri | action | unresolved | She tried to turn the key, but it would not rotate and the cashbox stayed locked and shut. |
| 4 | Neri | speech | recorded | Wrong key, |
| 5 | Neri | action | unresolved | She pulled the short key completely out of the lock. |
| 6 | Neri | action | applied | Then she laid it on the bench and released it. |
| 7 | Olan | action | applied | Olan picked up the long silver key |
| 8 | Olan | action | applied | and, after a pause, set it back beside the short one and let go. |
| 9 | Olan | speech | recorded | Neither has opened it, |

### coat_off_handover_and_rewear

Noa's violet rehearsal coat caught on the chair until she stepped clear of it. "Hold this a moment," she told Kit. She took the coat off, held it in both hands, and passed it to Kit. Kit laid it across the slatted chair and released it. Noa picked up the white cloakroom ticket from the narrow shelf and handed it to Kit. "The ticket, not the coat, is yours," she said. Kit set the ticket back on the shelf, then lifted the coat from the chair and handed the coat back to Noa. Noa put the same violet coat on and let her hands fall free. She walked through the open doorway onto the landing. Kit stayed beside the chair. "It fits again," Noa said from the landing.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- |
| 0 | Noa | action | unchanged | Noa's violet rehearsal coat caught on the chair until she stepped clear of it. |
| 1 | Noa | speech | recorded | Hold this a moment, |
| 2 | Noa | action | applied | She took the coat off and held it in both hands. |
| 3 | Noa | action | applied | She passed it to Kit. |
| 4 | Kit | action | applied | Kit laid it across the slatted chair and released it. |
| 5 | Noa | action | applied | Noa picked up the white cloakroom ticket from the narrow shelf. |
| 6 | Noa | action | applied | Noa handed it to Kit. |
| 7 | Noa | speech | recorded | The ticket, not the coat, is yours, |
| 8 | Kit | action | applied | Kit set the ticket back on the shelf. |
| 9 | Kit | action | applied | Kit lifted the coat from the chair. |
| 10 | Kit | action | applied | Kit handed the coat back to Noa. |
| 11 | Noa | action | applied | Noa put the same violet coat on and let her hands fall free. |
| 12 | Noa | action | applied | She walked through the open doorway onto the landing. |
| 13 | Noa | speech | recorded | It fits again, |

## regression

### partial_key_insertion_failed_turn

Dust shone in the slant of afternoon light above the maple bench. Neri picked up the short silver key, leaving the long silver key where it lay. "Try the short one first," Olan said. Keeping her fingers around its bow, Neri pushed the short key partway into the red cashbox's lock; its tip entered the keyway, but its shoulder stopped outside. She tried to turn the key, but it would not rotate and the cashbox stayed locked and shut. "Wrong key," she said. She pulled the short key completely out of the lock. Then she laid it on the bench and released it. Olan picked up the long silver key and, after a pause, set it back beside the short one and let go. "Neither has opened it," he said.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- |
| 0 | Neri | action | applied | Neri picked up the short silver key, leaving the long silver key where it lay. |
| 1 | Olan | speech | recorded | Try the short one first, |
| 2 | Neri | action | applied | Neri pushed the short key partway into the red cashbox's lock; its tip entered the keyway, but its shoulder stopped outside. |
| 3 | Neri | action | recorded | She tried to turn the key, but it would not rotate and the cashbox stayed locked and shut. |
| 4 | Neri | speech | recorded | Wrong key, |
| 5 | Neri | action | applied | She pulled the short key completely out of the lock. |
| 6 | Neri | action | applied | Then she laid it on the bench and released it. |
| 7 | Olan | action | applied | Olan picked up the long silver key |
| 8 | Olan | action | applied | and, after a pause, set it back beside the short one and let go. |
| 9 | Olan | speech | recorded | Neither has opened it, |
