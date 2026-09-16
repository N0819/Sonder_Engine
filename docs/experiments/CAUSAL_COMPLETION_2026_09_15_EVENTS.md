# Causal completion event logs — 2026-09-15

Original captures, intermediate regression failures and latest regressions are separate. Event accounts do not certify resulting world state; see the audit.

## initial

### seed_case_repeated_lid_and_release

Rain ticked against the potting-room panes. Ada picked up the green seed case from the stone worktop and opened its lid. "Still dry," she said to Jun. She closed the lid, handed the case to him, and took the brass scoop from the worktop. Jun opened the same case, looked into its empty interior, and closed it again. "I will leave it here," he said. He set the case on the seed shelf, let go, and walked through the open doorway into the glasshouse. Ada laid the scoop back on the worktop. From beside the shelf she opened the case once more without lifting it, then shut it. "Now it is closed," she called.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Ada | action | applied | picked up the green seed case from the stone worktop |
| 1 | Ada | action | unresolved | opened the green seed case lid |
| 2 | Ada | speech | recorded | Still dry |
| 3 | Ada | action | unresolved | closed the green seed case lid |
| 4 | Ada | action | applied | handed the green seed case to Jun |
| 5 | Ada | action | applied | took the brass scoop from the stone worktop |
| 6 | Jun | action | unresolved | opened the green seed case |
| 7 | Jun | action | recorded | looked into the green seed case interior |
| 8 | Jun | action | unresolved | closed the green seed case |
| 9 | Jun | speech | recorded | I will leave it here |
| 10 | Jun | action | unresolved | set the green seed case on the seed shelf |
| 11 | Jun | action | unresolved | let go of the green seed case |
| 12 | Jun | action | unresolved | walked through the open doorway into the glasshouse |
| 13 | Ada | action | unresolved | laid the brass scoop back on the stone worktop |
| 14 | Ada | action | unresolved | moved beside the seed shelf |
| 15 | Ada | action | unresolved | opened the green seed case once more without lifting it |
| 16 | Ada | action | unresolved | shut the green seed case |
| 17 | Ada | speech | recorded | Now it is closed |

### clipped_tag_follows_then_detaches

The sorting desk was bare except for a grey canvas satchel and a yellow tag with a spring clip. Tess lifted the tag and clipped it firmly to the satchel's outer handle, releasing the clip. "The yellow tag goes with this bag," she said. Ivo picked up the satchel by that handle and carried it through the open doorway into the dispatch hall; the clipped tag travelled with it. He placed the satchel on the dispatch bench and let go. Tess followed him into the hall. "Leave the bag there," she said. She unclipped the tag and held it in her hand, then put the tag on the bench beside the satchel and released it. Ivo took the satchel from the bench and returned to the sorting room with it. The yellow tag remained on the dispatch bench.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Tess | action | unresolved | lifted the tag and clipped it firmly to the satchel's outer handle, releasing the clip |
| 1 | Tess | speech | recorded | The yellow tag goes with this bag |
| 2 | Ivo | action | unresolved | picked up the satchel by its handle |
| 3 | Ivo | action | unresolved | carried the satchel through the open doorway into the dispatch hall; the clipped tag travelled with it |
| 4 | Ivo | action | unresolved | placed the satchel on the dispatch bench and let go |
| 5 | Tess | action | unresolved | followed him into the hall |
| 6 | Tess | speech | recorded | Leave the bag there |
| 7 | Tess | action | unresolved | unclipped the tag from the satchel and held it in her hand |
| 8 | Tess | action | unresolved | put the tag on the bench beside the satchel and released it |
| 9 | Ivo | action | unresolved | took the satchel from the bench |
| 10 | Ivo | action | unresolved | returned to the sorting room with the satchel |

### coat_off_handover_and_rewear

Noa's violet rehearsal coat caught on the chair until she stepped clear of it. "Hold this a moment," she told Kit. She took the coat off, held it in both hands, and passed it to Kit. Kit laid it across the slatted chair and released it. Noa picked up the white cloakroom ticket from the narrow shelf and handed it to Kit. "The ticket, not the coat, is yours," she said. Kit set the ticket back on the shelf, then lifted the coat from the chair and handed the coat back to Noa. Noa put the same violet coat on and let her hands fall free. She walked through the open doorway onto the landing. Kit stayed beside the chair. "It fits again," Noa said from the landing.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Noa | action | unresolved | Noa stepped clear of the slatted chair, freeing her caught violet rehearsal coat |
| 1 | Noa | speech | recorded | Hold this a moment, |
| 2 | Noa | action | unresolved | Noa took the violet rehearsal coat off |
| 3 | Noa | action | unresolved | Noa held the violet rehearsal coat in both hands |
| 4 | Noa | action | unresolved | Noa passed the violet rehearsal coat to Kit |
| 5 | Kit | action | unresolved | Kit laid the violet rehearsal coat across the slatted chair |
| 6 | Kit | action | unresolved | Kit released the violet rehearsal coat |
| 7 | Noa | action | unresolved | Noa picked up the white cloakroom ticket from the narrow shelf |
| 8 | Noa | action | unresolved | Noa handed the white cloakroom ticket to Kit |
| 9 | Noa | speech | recorded | The ticket, not the coat, is yours, |
| 10 | Kit | action | unresolved | Kit set the white cloakroom ticket back on the narrow shelf |
| 11 | Kit | action | unresolved | Kit lifted the violet rehearsal coat from the slatted chair |
| 12 | Kit | action | unresolved | Kit handed the violet rehearsal coat back to Noa |
| 13 | Noa | action | unresolved | Noa put the violet rehearsal coat on |
| 14 | Noa | action | applied | Noa let her hands fall free |
| 15 | Noa | action | unresolved | Noa walked through the open doorway onto the landing |
| 16 | Noa | speech | recorded | It fits again, |

### two_tins_swap_and_split_destination

Bea held the round copper tin; Luca held the square one. "We will swap, but keep both lids shut," Bea said. She set her round tin on the parcel counter and released it. Luca handed the square tin to Bea, then picked up the round tin from the counter. Bea put the square tin on the round stool. Luca put the round tin beside the ribbon on the counter and let go. "You said, ‘Open the square one,’ yesterday," he remarked, without opening either tin. Bea lifted both tins, one in each hand, and carried them through the open doorway into the yard. She set the square tin on the yard ledge and released it, kept the round tin in her hand, and returned to the parcel room. "This one stays with me," she said, raising the round tin. The blue ribbon had not moved.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Bea | action | applied | Bea held the round copper tin |
| 1 | Luca | action | applied | Luca held the square copper tin |
| 2 | Bea | speech | recorded | We will swap, but keep both lids shut, |
| 3 | Bea | action | unresolved | Bea set the round tin on the parcel counter and released it |
| 4 | Luca | action | unresolved | Luca handed the square tin to Bea |
| 5 | Luca | action | unresolved | Luca picked up the round tin from the counter |
| 6 | Bea | action | unresolved | Bea put the square tin on the round stool |
| 7 | Luca | action | unresolved | Luca put the round tin beside the ribbon on the counter and let go |
| 8 | Luca | speech | recorded | You said, 'Open the square one,' yesterday, |
| 9 | Bea | action | unresolved | Bea lifted both tins, one in each hand |
| 10 | Bea | action | unresolved | Bea carried them through the open doorway into the yard |
| 11 | Bea | action | unresolved | Bea set the square tin on the yard ledge and released it |
| 12 | Bea | action | unresolved | Bea returned to the parcel room |
| 13 | Bea | speech | recorded | This one stays with me, |
| 14 | Bea | action | pending | Bea raised the round tin |

### failed_key_quoted_command_and_cup

The red folder lay sealed on the reading table beside a cup and a short iron key. Edda picked up the key. "Sol told me, ‘Break the seal,’ but I refused," she said. She inserted the key into the archive door's lock and tried to turn it; it would not turn, and the door remained locked and closed. She withdrew the key and set it on the reading table, releasing it. Sol did not touch the folder. "Then leave it sealed," he said. Edda picked up the cup, walked through the open side doorway into the alcove, and set the cup on the alcove shelf. She released the cup, returned to the vestibule empty-handed, and sat beside the table. "The key did not fit," she said.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Edda | action | unresolved | picked up the key |
| 1 | Edda | speech | recorded | Sol told me, 'Break the seal,' but I refused, |
| 2 | Edda | action | unresolved | inserted the key into the archive door's lock |
| 3 | Edda | action | unresolved | tried to turn the key; it would not turn, and the door remained locked and closed |
| 4 | Edda | action | unresolved | withdrew the key |
| 5 | Edda | action | unresolved | set it on the reading table, releasing it |
| 6 | Sol | speech | recorded | Then leave it sealed, |
| 7 | Edda | action | unresolved | picked up the cup |
| 8 | Edda | action | unresolved | walked through the open side doorway into the alcove |
| 9 | Edda | action | unresolved | set the cup on the alcove shelf |
| 10 | Edda | action | unresolved | released the cup |
| 11 | Edda | action | applied | returned to the vestibule empty-handed |
| 12 | Edda | action | applied | sat beside the table |
| 13 | Edda | speech | recorded | The key did not fit, |

## regression_intermediate

### coat_off_handover_and_rewear

Noa's violet rehearsal coat caught on the chair until she stepped clear of it. "Hold this a moment," she told Kit. She took the coat off, held it in both hands, and passed it to Kit. Kit laid it across the slatted chair and released it. Noa picked up the white cloakroom ticket from the narrow shelf and handed it to Kit. "The ticket, not the coat, is yours," she said. Kit set the ticket back on the shelf, then lifted the coat from the chair and handed the coat back to Noa. Noa put the same violet coat on and let her hands fall free. She walked through the open doorway onto the landing. Kit stayed beside the chair. "It fits again," Noa said from the landing.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Noa | action | unresolved | Noa's violet rehearsal coat caught on the chair until she stepped clear of it |
| 1 | Noa | speech | recorded | Hold this a moment, |
| 2 | Noa | action | applied | Noa took the coat off |
| 3 | Noa | action | applied | Noa held the coat in both hands |
| 4 | Noa | action | applied | Noa passed the coat to Kit |
| 5 | Noa | action | unresolved | Kit laid the coat across the slatted chair and released it |
| 6 | Noa | action | applied | Noa picked up the white cloakroom ticket from the narrow shelf |
| 7 | Noa | action | applied | Noa handed the ticket to Kit |
| 8 | Noa | speech | recorded | The ticket, not the coat, is yours, |
| 9 | Noa | action | unresolved | Kit set the ticket back on the shelf |
| 10 | Noa | action | applied | Kit lifted the coat from the chair |
| 11 | Noa | action | applied | Kit handed the coat back to Noa |
| 12 | Noa | action | applied | Noa put the same violet coat on |
| 13 | Noa | action | applied | Noa let her hands fall free |
| 14 | Noa | action | applied | Noa walked through the open doorway onto the landing |
| 15 | Noa | speech | recorded | It fits again, |

## regression

### clipped_tag_follows_then_detaches

The sorting desk was bare except for a grey canvas satchel and a yellow tag with a spring clip. Tess lifted the tag and clipped it firmly to the satchel's outer handle, releasing the clip. "The yellow tag goes with this bag," she said. Ivo picked up the satchel by that handle and carried it through the open doorway into the dispatch hall; the clipped tag travelled with it. He placed the satchel on the dispatch bench and let go. Tess followed him into the hall. "Leave the bag there," she said. She unclipped the tag and held it in her hand, then put the tag on the bench beside the satchel and released it. Ivo took the satchel from the bench and returned to the sorting room with it. The yellow tag remained on the dispatch bench.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Tess | action | unresolved | Tess lifted the yellow tag from the sorting desk |
| 1 | Tess | action | unresolved | Tess clipped the tag firmly to the satchel's outer handle, releasing the clip |
| 2 | Tess | speech | recorded | The yellow tag goes with this bag, |
| 3 | Ivo | action | applied | Ivo picked up the satchel by its handle |
| 4 | Ivo | action | unresolved | Ivo carried the satchel through the open doorway into the dispatch hall; the clipped tag travelled with it |
| 5 | Ivo | action | unresolved | He placed the satchel on the dispatch bench and let go |
| 6 | Tess | action | unresolved | Tess followed him into the hall |
| 7 | Tess | speech | recorded | Leave the bag there, |
| 8 | Tess | action | unresolved | She unclipped the tag and held it in her hand |
| 9 | Tess | action | unresolved | then put the tag on the bench beside the satchel and released it |
| 10 | Ivo | action | applied | Ivo took the satchel from the bench |
| 11 | Ivo | action | unresolved | and returned to the sorting room with it |

### coat_off_handover_and_rewear

Noa's violet rehearsal coat caught on the chair until she stepped clear of it. "Hold this a moment," she told Kit. She took the coat off, held it in both hands, and passed it to Kit. Kit laid it across the slatted chair and released it. Noa picked up the white cloakroom ticket from the narrow shelf and handed it to Kit. "The ticket, not the coat, is yours," she said. Kit set the ticket back on the shelf, then lifted the coat from the chair and handed the coat back to Noa. Noa put the same violet coat on and let her hands fall free. She walked through the open doorway onto the landing. Kit stayed beside the chair. "It fits again," Noa said from the landing.

| Order | Actor | Kind | Execution | Event |
| ---: | --- | --- | --- | --- | --- |
| 0 | Noa | action | unchanged | Noa's violet rehearsal coat snagged on the slatted chair; she stepped clear of it. |
| 1 | Noa | speech | recorded | Hold this a moment |
| 2 | Noa | action | unresolved | Noa took off the violet rehearsal coat. |
| 3 | Noa | action | unchanged | Noa held the violet rehearsal coat in both hands. |
| 4 | Noa | action | applied | Noa passed the violet rehearsal coat to Kit. |
| 5 | Kit | action | unresolved | Kit laid the violet rehearsal coat across the slatted chair and released it. |
| 6 | Noa | action | unresolved | Noa picked up the white cloakroom ticket from the narrow shelf. |
| 7 | Noa | action | applied | Noa handed the white cloakroom ticket to Kit. |
| 8 | Noa | speech | recorded | The ticket, not the coat, is yours |
| 9 | Kit | action | unresolved | Kit set the white cloakroom ticket back on the narrow shelf. |
| 10 | Kit | action | unresolved | Kit lifted the violet rehearsal coat from the slatted chair. |
| 11 | Kit | action | applied | Kit handed the violet rehearsal coat back to Noa. |
| 12 | Noa | action | applied | Noa put the violet rehearsal coat on. |
| 13 | Noa | action | applied | Noa let her hands fall free. |
| 14 | Noa | action | unresolved | Noa walked through the open doorway onto the landing. |
| 15 | Noa | speech | recorded | It fits again |
