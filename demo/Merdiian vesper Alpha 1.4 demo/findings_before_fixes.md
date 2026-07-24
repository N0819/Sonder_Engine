# Findings & pipeline hardening — Meridian run

Bugs, fragilities, and information-boundary anomalies observed while driving the demo.
**8 finding(s).**


### F1. Turn 3 recovered via resume after transient validation failure
- attempt 1 failed (RuntimeError: character failed JSON validation: mind_model_updates.0.alternatives.0: str type expected); resuming
- attempt 2 failed (RuntimeError: character failed JSON validation: mind_model_updates.0.alternatives.0: str type expected); resuming
- attempt 3 failed (RuntimeError: character failed JSON validation: mind_model_updates.0.alternatives.0: str type expected); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F2. Turn 8 recovered via resume after transient validation failure
- attempt 1 failed (RuntimeError: character failed JSON validation: mind_model_updates.0.alternatives.0: str type expected); resuming
- attempt 2 failed (RuntimeError: background_react failed JSON validation: dialogue_log_entry.volume: value is not a valid enumeration member; permitted: ); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F3. Turn 9 recovered via resume after transient validation failure
- attempt 1 failed (RuntimeError: character failed JSON validation: mind_model_updates.0.alternatives.0: str type expected); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F4. Turn 12 recovered via resume after transient validation failure
- attempt 1 failed (RuntimeError: character failed JSON validation: mind_model_updates.0.alternatives.0: str type expected); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F5. Turn 24 recovered via resume after transient validation failure
- attempt 1 failed (RuntimeError: background_react failed JSON validation: dialogue_log_entry.volume: value is not a valid enumeration member; permitted: ); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F6. Turn 26 recovered via resume after transient validation failure
- attempt 1 failed (RuntimeError: background_react failed JSON validation: dialogue_log_entry.volume: value is not a valid enumeration member; permitted: ); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F7. Turn 29 recovered via resume after transient validation failure
- attempt 1 failed (LLMError: ("Connection broken: InvalidChunkLength(got length b'', 0 bytes read)", InvalidChunkLength(got length b'', 0 bytes read)); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F8. Turn 3: concealed action but non-concealed speech (potential info leak)
- `director_interpret` marked the enclosing action `visibility=concealed` with `conceal_from`, but the accompanying speech element stayed `whisper`/unconcealed — so the private words can reach same-room observers, defeating the intended concealment.
- This is the exact failure the Director prompt's 'concealing the action does NOT hide what is said' clause is meant to prevent; the model under-propagates concealment from action to speech.
