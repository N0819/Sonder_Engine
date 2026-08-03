# Tests

Run from the repository root:

```bash
make test-fast     # pure/unit contracts; no database-backed slow tests
make test-full     # every Python regression test
make test-browser  # optional real Chromium behavior tests
make check         # compile, regenerate/verify code map, structure, full suite
```

`make test` is an alias for `make test-full`. See `docs/TESTING.md` for
dependency installation, constraints, and CI policy.

The shared `temp_db` fixture creates a fresh SQLite database, calls
`db.configure`, initializes the schema, closes the thread-local connection, and
removes WAL/SHM files afterward. Tests requesting it are marked `slow` during
collection and run in the full tier. Fast-tier tests must not depend on
`engine.db` or on another test having initialized settings; use pure constants
or stub prompt/settings lookup when the database is outside the invariant under
test.

Test files are organized by invariant or subsystem rather than mirroring every source file. Prefer a focused regression test that captures the earliest broken boundary.

Character-psychology coverage is split deliberately: `test_psychology_runtime`
checks bounded state mechanics, `test_character_psychology_fill` checks
non-destructive legacy-card completion, and the perception/self-knowledge tests
attack the new information paths with hidden-intent and other-body markers.
`test_chat_character_cards` covers per-story card isolation, live-state
preservation, identity-key rejection, UI wiring, and portable archive fidelity.
`test_observation_derivation` is the companion to those leak tests on the other
axis: the projection can be perfectly leak-free and still describe the beat
wrongly, and the character agent is told to treat it as structure.
`test_character_self_lines` covers dialogue continuity at both layers: bounded
verbatim history, repeated sentence shapes, one semantic move per turn,
destination substitution, the combined contextual review, and the rule that a
spent intention cannot keep a paraphrased goal steering. Semantic similarity is
a review trigger rather than a blanket ban on intentional continuation.
`test_authorial_channel` and `test_authored_outcome_attribution` cover
attribution — which declarations are the player's to make, and which seams go
blind when an act that lands on a character carries no bound target.
`test_initial_outfit` covers schema/import separation from body appearance,
character/persona editor wiring, one-time seeding into live attire, first
attachment behavior, authoritative establishment, and the private-card
information firewall on that new payload.
`test_pipeline_audit_leak_gaps` covers the pipeline audit information-leak
fixes: rear-arc action injection (B3), `co_present_positions` destination
leak (S3-A4), string-line concealment erosion (X14), reroll memory turn
cutoff (F1), dialogue memory recognition gate (F2/P1), entity-state
concealed-actor gate (S3-A8), omniscient event re-entry (Pattern 4),
surgical concealed redaction (D1/D2), portal-state visibility gating
(S3-A5), and background-presence recognition gate (F3).
`test_reroll_restore_integrity` covers checkpoint restore cast-cache refresh
and cast membership rollback.
