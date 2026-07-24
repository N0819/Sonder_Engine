# Doctor Who — The Bethnal Green Wound (Reaper paradox) — findings

Live run on `alpha3.3` (+ the V2/V3 fixes at `6f21986`). A test of paradox /
Reaper escalation and its resolution: player = Ellie Marsh (an original
companion), cast = the Tenth Doctor. Ellie means to save her mother from a
2003 hit-and-run — a fixed point — which should open a wound in time.

Turn numbers refer to `run.db` / `run_log.jsonl`.

---

## DW-1 — Frame `location` string not updated on time-travel/relocation  *(open)*

**Symptom.** t3, after the TARDIS travels from Cardiff to 2003 Bethnal Green
Road, the player view narrates the alley "opens onto **Bute Street**" — the
Cardiff street just departed.

**Root cause — NOT a perception leak.** The scene `positions` updated correctly:
after t2, `tardis`, `Ellie Marsh`, `The Doctor` and the auto-created
`karen_marsh` are all in room `Bethnal_Green_Road`. But the frame-level
`scene.location` string still read `"Alley off Bute Street, Cardiff"`. The
narrator payload carries that top-level `location`, so it surfaced the departed
place name even though every entity had moved.

**Fix direction.** On a scene relocation (a movement whose destination is a room
in a different top-level location, or a mapping-authored place change), update
`scene.location` to match where the occupants now are — or derive the narrator's
location label from the player's own room rather than the frame string. The
commit-path scene writer is where the positions moved but the label did not.

**Note.** Distinct from the alpha3.2.1 "stale room description" fix, which was
about a room's own `desc` freezing mid-event; this is the top-level location
label lagging a wholesale relocation.

---

## DW-2 — A fixed-point violation is resolved as an ordinary rescue  *(watching)*

**Symptom.** t6: Ellie breaks the rule and saves Karen from the hit-and-run,
narrating explicitly "Karen Marsh is alive on the twelfth of November 2003, and
she was never supposed to be." `director_resolve` captured the **physical** layer
faithfully — a tracked `cond_winded_karen` condition, the driver emerging,
`world_facts` for the horn and tyres — but registered **nothing about the
temporal violation**: no world_fact, obligation, or established_fact marking that
a fixed-point death was prevented. Karen is simply alive and winded, like any
rescue.

**Matches a known gap** (backburner: director world-event capture). The player
narrated a world-significant event and the Director kept only the ordinary
physical reading. Whether "saving your mother creates a wound in time" is
*objectively* true is a fiction rule that lives in the lorebook and the Doctor's
knowledge, not in the Director's general causal model — so this is arguably
correct scoping (the Director owns physics, not genre metaphysics) rather than a
pure miss.

**Open question the run now tests.** The in-world authority who DOES know is the
Doctor (Reapers are in his private history). If, once he names the wound, the
Director/mapping can pick up the escalation the style guide seeded (stalled
clocks → greying light → Reapers) and then resolve it, the engine handles
paradox through *character knowledge* rather than a hardcoded mechanic — which
is the more interesting result. If the wound only ever exists as flavour in the
Doctor's dialogue while the world stays mechanically normal, that is the real
finding, and it argues for a deterministic "significant-world-event" hook the
Director can raise.

## DW-3 — Dangling-verb heal corrupted a surviving NPC attribution  *(FIXED)*

**Symptom.** t7: "Then he says it., quiet and gentle, 'Ellie.'" (twice). The
Doctor's dialogue attribution was mangled to "says it.," .

**Root cause.** `_strip_player_echo`'s dangling-speech-verb heal
(`_DANGLING_SPEECH_VERB_RE`) runs on the WHOLE prose whenever a player echo is
stripped this beat. Its lookahead accepted a comma that CONTINUES the sentence,
so "he says, quiet and gentle, 'Ellie'" (a normal attribution around a quote
that survived) was treated as a dangling verb and rewritten. Any beat with both
a stripped player line and an NPC "<verb>, ..." attribution hit it.

**Fix.** Lookahead is now sentence-end only (`[.!?]|$`). A genuinely dangling
verb ("you say.", "I whisper," at line end) still heals; an attribution around a
surviving quote is left intact. Healing on a following capital was rejected: it
would eat a proper-noun object ("he tells Karen the truth" -> "he tells it.").
Fixed with `tests/test_echo_colon_heal.py`.

## DW-4 — Auto-created entity duplicated across two rooms via id-vs-name position keys  *(run-state repaired; root fix queued)*

**Symptom.** t8: Karen appears in `scene.positions` twice — `"karen_marsh":
"Bethnal_Green_Road"` (still on the road) AND `"Karen Marsh":
"tardis_console_room"` (in the ship). She is co-present in two rooms, which
corrupts perception's co-present set.

**Root cause.** Positions are canonically keyed by DISPLAY NAME (as everywhere:
`room_of` looks up by name; the player and cast use `"Ellie Marsh"`, `"The
Doctor"`). `director_resolve` consistently writes name keys (`"Karen Marsh"`).
But Karen was **auto-created** from Ellie's backstory as entity id `karen_marsh`,
and that path seeded an **id-keyed** position. The commit scene-merge never
reconciles that an id-key and a name-key denote the same entity, so both persist
and every `director_resolve` move touches only the name-key, orphaning the
id-key in the departed room.

**Same class as `d9e6a3e`** ("scene positions keyed inconsistently duplicated a
character into two rooms"), which fixed the branch-remap path. This is the
live entity-auto-creation path, unfixed.

**Fix direction.** Normalize position keys to the canonical display-name form on
commit (or forbid the auto-creation path from writing an id-keyed position when
a name-keyed one is the convention). A deterministic invariant check — no two
position keys resolving to the same entity — would have caught it. Not fixed
mid-run to avoid a rushed change to the commit scene-writer; the run's scene
state was repaired in place (stray id-key removed) so co-presence is correct
going forward.
