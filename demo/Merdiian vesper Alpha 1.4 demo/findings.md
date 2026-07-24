# Findings & pipeline hardening — Meridian run

Bugs, fragilities, and information-boundary anomalies observed while driving the demo.
**2 finding(s).**


### F1. Turn 14 recovered via resume after transient validation failure
- attempt 1 failed (LLMError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))); resuming
- **Hardening:** engine's temp-0 internal repair could not fix it; a fresh re-sample (resume) did. Suggests the repair path should re-sample (nonzero temp) on schema-shape errors, not just re-instruct at temp 0.

### F2. Turn 3: `conceal_from` uses character UIDs while `targets`/`addressed_to` use integer ids
- e.g. conceal_from=['char_86ed246a4af24d41924e39e8cae6b1cc', 'char_9631b28ca74f43a9ba1206f293538d2b'] vs targets=['char_9ab579056121426188613d7457267479'] / flow.addressed_to uses ints. Mixed id encodings in one structured output invite downstream mismatch bugs.
