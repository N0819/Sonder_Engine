# Perception presentation check — 2026-09-15

## Result

Perception now supplies separate witnessed events, noticed changes, current
state, and undivided legacy context. The projection is deterministic and adds
no model calls. Characters retain evidence handles and their relevant current
state. Narrators receive ordered event records with explicit source labels,
event types, sensory limits, and exact delivered text.

This fixes information loss and ambiguity introduced by presentation. The
narrator is allowed to add minor details of no consequence. An addition is
not automatically a fidelity defect: assess whether it contradicts established
facts, alters consequential state or causality, changes speaker ownership, or
reveals information this observer was not given.

## Changes exercised

- One rendered span remains one observation, including crowded scenes. The old
  eight-row merging cap no longer combines different actions or speakers.
- Chronology is explicit for witnessed events. A newly noticed blush, garment,
  posture or surrounding condition does not acquire an invented event time.
- A character reads the evidence once, without a second duplicate view
  paragraph. Current state remains available, grouped by the permitted subject
  label without merging evidence.
- The narrator reads `current_events`, `changes_noticed`, `present_scene`, and
  optional `unstructured_context`. Event text is not repeated as standing
  scenery or as `sensory_channels.this_beat`.
- Reconciled player actions remain first in the narrator's event records.
  Exact dialogue substitution retains its existing lookup table.
- Micro-round actions and speech retain individual evidence entries through
  serial turns, blind first waves, and resume. Presentation ordinals cover the
  complete delivered stream; stored round records are unchanged.
- Actor metadata follows identity repair. A grouped presence sentence does not
  claim its first body is the actor of the whole group. Removed archived text
  cannot return through an older observation row. Legacy actor metadata is
  omitted because older text repairs did not always scrub that separate label.
- English and Japanese instructions explain the sections. Quoted requests,
  conditions and promises establish speech, not compliance with that speech.

For example, the narrator now receives an event shaped like:

```json
{
  "order": 4,
  "actor": "Bob",
  "kind": "speech",
  "channel": "hearing",
  "fidelity": "rendered",
  "ambiguity": 0.15,
  "text": "Bob says: \"Only if you hold the door.\""
}
```

That entry cannot authorize an added event in which Alice holds the door.
`Alice has flushed cheeks.` is delivered separately as a noticed change;
its time and cause are not established by the packet.

## Archive replay

Read the main working directory's database in SQLite read-only mode. Converted
120 active stored perception variants, containing 184 nonempty observer views.
The main database is separate from the newer character-kernel worktree database;
this sample is not a replay of the worktree's latest Attempt two scene.

| Measurement | Result |
| --- | ---: |
| Observer views checked | 184 |
| Views with matching word multiplicities before/after | 184 |
| Coverage mismatches | 0 |
| Event rows retained | 528 |
| Standing rows retained | 700 |
| Views needing preserved legacy context | 3 |
| Old view-plus-observations JSON bytes | 783,362 |
| New character perception packet JSON bytes | 488,571 |
| Reduction for this archived sample | 37.63% |

This checks wording coverage, including repeated words, not semantic correctness
or token savings. Historical merges cannot be undone by this projection; the
sample's old rows also cannot recover the new event/change distinction. New
boundary behavior is checked with the synthetic regression fixtures.

## Live reader checks

Used OpenRouter `z-ai/glm-5.2`, temporary databases, synthetic content, and the
normal character/narrator validation paths. The played database was not written.
These are small smoke checks, not a controlled comparison or a reliability rate.

The character read a workshop packet containing a cup handoff, two lines of
conditional dialogue, and a noticed blush. Its output validated, treated Mira
as holding the cup, and stated uncertainty about why Alice was flushed. It
proposed examining the cup. This verifies one successful reading, not every
possible downstream action target or psychological inference.

The final narrator checks used:

1. **Workshop:** Alice opens a door; Bob picks up a cup; Alice says “Pass it to
   Mira.”; Bob says “Only if you hold the door.”; Bob hands Mira the cup.
   Alice's flushed cheeks are a separate noticed change.
2. **Crowded workshop:** twelve alternating actions and spoken deliveries from
   Alice, Bob, Clara and an unidentified voice, including five quotes. Objects
   include a key, cup, folded paper, ledger and red cloth. Requests and
   prohibitions remain quoted speech.

Manual review found all five workshop events and all twelve crowded events
represented in order, with all seven quoted lines retained. The blush reached
the workshop prose. The explicit ownership worked for both workshop quotes;
in the crowded case two later quotes lacked clear ownership on the page.

**Embellishment versus fidelity:** the first review judged incidental additions
too strictly. Cup warmth, minor gestures and connective motion can fall within
the narrator's license when they fit established facts and have no consequence.
Their absence from the packet alone does not make the workshop output a failure.
Likewise, holding a just-opened door is not by itself proof that the narrator
incorrectly resolved a spoken condition.

The useful review questions are narrower: does the added motion contradict a
tracked position, does the cloth change the key's state or conceal it, and does
attribution remain clear? Those consequences were not established by this smoke
test and should not be reported as confirmed defects. The crowded output did
locate an unidentified voice beyond the walls despite the input supplying no
source location; that adds observer knowledge and crosses the separate rule
against assigning a location to an unlocated percept.

The fidelity checker returned no warning for the workshop additions, which is
not itself a failure. It reported one attribution warning on the crowded draft,
but that warning misread “Clara's voice” as the anonymous voice. These checks do
not establish complete event coverage or absence of consequential contradiction.
No output was silently repaired and no additional runtime correction call was
introduced.

## Regression coverage

The new tests live in:

- `tests/test_perception_packet.py`: separate acts and dialogue, 60-event
  stress input, noticed changes, grouped state, actor identity repair,
  citation round trips, legacy text, and accumulated event ordinals.
- `tests/test_micro_observation_structure.py`: delivered speech/action
  structure, degraded hearing, own observable conduct, blind-wave timing,
  evidence uniqueness, exact resume, and legacy fallback.
- `tests/test_narrator_perception_packet.py`: source/type retention,
  conditional speech, unidentified degraded sources, more than eight events,
  player acts, primary/extra-player/opening payloads, archive context and exact
  dialogue substitution.

Existing perception, identity, memory/citation, interaction, narration and
prompt tests were also run. Focused narrator checks passed 205 tests after the
final event-record change. The last archive-identity regression run passed
54 focused tests.

Final full-suite result: **15,512 passed, 29 failed, 3 skipped**. All 29 failing
test names also occur in the earlier baseline (which had 30 failures); there
are no newly failing tests. The remaining failures concern the earlier
Director-contract/prompt migration and associated fixtures, not the new
perception tests. This is not a clean full-suite pass.

Code-map regeneration and project structure checks passed, with the existing
Japanese protocol-parity deferral notice. Python compilation and whitespace
checks passed. The played database was not modified.
