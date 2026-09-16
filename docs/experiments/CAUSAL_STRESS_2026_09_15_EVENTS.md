# Recompiled event logs — 2026-09-15

Latest tested outputs. These are event records, not proof that every described physical state was encoded.
See [the audit](CAUSAL_STRESS_2026_09_15.md) for world-state findings.

## Workshop coreference

**Input prose**

The workshop smelled of cedar, and the blue enamel tin was the only container on its crowded bench. Ilya lifted it from the bench and opened its hinged lid. "There is your spare needle," she told Sera. She took the silver needle out of the tin and laid the needle on the folded cloth. Then she shut the tin. Sera held out his empty palm, and Ilya put the closed container into it. "Keep that safe; I still need the needle," she said. Sera set the tin on the stool beside him. Ilya picked up the needle from the cloth and slipped it into her own canvas pouch. She reopened the same blue tin on the stool, looked inside, and closed it once more. "Empty now," she said.

**Recompiled events**

1. Ilya lifts the blue enamel tin from the workbench
2. Ilya opens the hinged lid of the blue enamel tin
3. Ilya: “There is your spare needle,”
4. Ilya removes the silver needle from the blue enamel tin
5. Ilya places the silver needle on the folded cloth
6. Ilya closes the blue enamel tin
7. Sera extends his empty open palm
8. Ilya places the closed blue enamel tin into Sera's outstretched palm
9. Ilya: “Keep that safe; I still need the needle,”
10. Sera places the blue enamel tin on the stool beside him
11. Ilya picks the silver needle up from the folded cloth
12. Ilya slips the silver needle into her canvas pouch
13. Ilya reopens the blue enamel tin sitting on the stool
14. Ilya peers inside the open blue enamel tin
15. Ilya closes the blue enamel tin again
16. Ilya: “Empty now,”

## Door and speech timeline

**Input prose**

Rain freckled the office window; Oren was in the adjoining corridor, beyond the closed connecting door. Mara opened that door without crossing the threshold. "The ledger is under the green lamp," she called to Oren in a normal voice. She shut the door again. She crossed from the office into the archive through its open archway and said, "I am in the archive now." Then she returned through the archway to the office. Mara opened the corridor door a second time and stepped into the corridor. "Bring the ledger here," she told Oren. She went back into the office, closed the connecting door behind her, and sat on the wooden chair. "That is all," she whispered to herself. The green lamp and the ledger had remained where they began.

**Recompiled events**

1. Mara opens the connecting door from the office side, remaining in the office.
2. Mara: “The ledger is under the green lamp,”
3. Mara closes the connecting door.
4. Mara walks through the archway from the office into the archive.
5. Mara: “I am in the archive now.”
6. Mara walks back through the archway from the archive into the office.
7. Mara opens the connecting door again.
8. Mara steps through the open connecting door into the corridor.
9. Mara: “Bring the ledger here,”
10. Mara walks back from the corridor into the office.
11. Mara closes the connecting door from the office side.
12. Mara sits down on the wooden chair in the office.
13. Mara: “That is all,”

## Garment badge and water

**Input prose**

In the ship’s dry maintenance bay, Nia wore the orange work jacket, and the inspection badge was clipped to its chest. She unfastened the badge and handed it to Tomas. "Hold this, not the jacket," she said. Nia took off the jacket and passed it to Rin. Rin draped the garment across the rail. Tomas laid the badge on the nearby tray. Nia lifted a bottle of plain water from the cart and poured a small splash onto the jacket’s left cuff, leaving that cuff wet. She set the bottle back on the cart. "Only the cuff needs rinsing," she told Rin. Rin picked the jacket up from the rail and handed it back to Nia. Nia put it on again. Finally, Tomas lifted the badge from the tray and clipped it to the jacket’s chest. "Ready," he said.

**Recompiled events**

1. Nia detaches the badge from the jacket
2. Nia extends the badge toward Tomas
3. Nia: “Hold this, not the jacket,”
4. Nia removes the jacket from her body
5. Nia extends the jacket toward Rin
6. Rin lays the jacket over the rail
7. Tomas sets the badge down on the tray
8. Nia picks up the bottle from the cart
9. Nia tilts the bottle and water runs onto the jacket's left cuff
10. Nia places the bottle down on the cart
11. Nia: “Only the cuff needs rinsing,”
12. Rin lifts the jacket off the rail
13. Rin extends the jacket toward Nia
14. Nia wears the jacket
15. Tomas picks up the badge from the tray
16. Tomas fastens the badge onto the jacket's chest
17. Tomas: “Ready,”

## Two object braided transfer

**Input prose**

The inn’s courtyard was bright enough to see the two parcels clearly: a red cloth bundle on the bench and a yellow wooden case beside it. Asha picked up the red bundle and the yellow case together. "Red for you, yellow for me," she told Bram. She handed the bundle to Bram while setting the case on the low table. Bram put the red bundle on the fountain rim. Asha opened the yellow case and removed its brass key. She closed the case, slipped the key into her belt pouch, and lifted the closed case from the table. "Actually, take this one too," she said. She handed the yellow case to Bram. He put it beside the red bundle on the fountain rim. Asha then took the red bundle back and laid it on the original bench. The fountain’s steady splash covered the pause afterward.

**Recompiled events**

1. lifts red cloth bundle and yellow wooden case from bench
2. Asha: “Red for you, yellow for me,”
3. extends red cloth bundle toward Bram
4. places yellow wooden case on low table
5. places red cloth bundle on fountain rim
6. opens yellow wooden case
7. lifts brass key out of open yellow wooden case
8. closes yellow wooden case
9. tucks brass key into belt pouch
10. lifts yellow wooden case from low table
11. Asha: “Actually, take this one too,”
12. extends yellow wooden case toward Bram
13. places yellow wooden case on fountain rim next to red cloth bundle
14. lifts red cloth bundle from fountain rim
15. places red cloth bundle on bench

## Attempt negation and embedded quote

**Input prose**

The cellar door was locked, and Leah’s copper key lay on the table beside an empty mug. Leah picked the key up. "If this works, I will open the cellar and fetch the red book," she said to Pavel. She inserted the key into the lock and tried to turn it, but the key would not turn; the door stayed locked. Leah pulled the key out and laid it back on the table. She did not kick the door. "Yesterday you said, ‘Break the lock,’ but I am not doing that," she told him. Pavel raised both hands. "Then leave it," he said. Leah lifted the empty mug, carried it across the kitchen into the pantry, and set it on the shelf. She returned to the kitchen and sat on the chair. The red book was still out of sight inside the cellar.

**Recompiled events**

1. Leah picks the copper key up from the kitchen table
2. Leah: “If this works, I will open the cellar and fetch the red book,”
3. Leah inserts the copper key into the cellar lock
4. Leah tries to turn the key in the lock; the key does not turn
5. Leah pulls the copper key out of the cellar lock
6. Leah places the copper key back on the kitchen table
7. Leah: “Yesterday you said, 'Break the lock,' but I am not doing that,”
8. Pavel raises both hands
9. Pavel: “Then leave it,”
10. Leah lifts the empty mug from the kitchen table
11. Leah carries the empty mug from the kitchen into the pantry
12. Leah sets the empty mug on the pantry shelf
13. Leah walks from the pantry back to the kitchen
14. Leah sits on the kitchen chair

## Two similar cups ambiguous pronoun

**Input prose**

Two white cups stood on the station kiosk’s counter. The cup with a blue stripe was on Edda’s left; the cup with a black dot was on her right. Edda picked up the striped cup. "This one is yours," she told Kian, and handed it to him. Kian set that cup on the windowsill. Edda lifted the dotted cup and put it on the tray. "The other one stays here," she said. Kian moved the striped cup from the windowsill onto the same tray, beside the dotted cup. Edda turned to face the timetable. "No train until noon," she said. Kian put it on the counter. Edda turned back toward Kian, lifted the dotted cup from wherever it now stood, and placed that clearly marked cup on the windowsill. "At least we can keep them apart," she said.

**Recompiled events**

1. Edda's hand lifts the striped cup from the counter
2. Edda: “This one is yours”
3. Edda extends the striped cup toward Kian
4. Kian places the striped cup on the windowsill
5. Edda's hand lifts the dotted cup from the counter
6. Edda places the dotted cup on the tray
7. Edda: “The other one stays here”
8. Kian lifts the striped cup from the windowsill and places it on the tray next to the dotted cup
9. Edda turns toward the timetable
10. Edda: “No train until noon”
11. Kian places the striped cup on the counter
12. Edda turns to face Kian
13. Edda's hand lifts the dotted cup from the tray
14. Edda places the dotted cup on the windowsill
15. Edda: “At least we can keep them apart”
