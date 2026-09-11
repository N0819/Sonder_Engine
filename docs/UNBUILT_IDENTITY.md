# Unbuilt work — Identity, naming, and language

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-17"></a>

### 1.17 A generic name cannot count

**Found 2026-08-01**, investigating chat 57 ("Run! ⎇10"), where scene life was
on, the Dalek was speaking, and the ledger still looked wrong.

`background_presences` is keyed by whatever string the prose used. Chat 57 held
ONE Dalek entity in one room and three presences tracking it — `A Dalek` (from
turn 0, 10 speaking turns), `Dalek` (turn 19) and `The Dalek` (turn 23) — split
by nothing but the article. Each carried its own dialogue history, so the same
creature had three partial memories of itself and none knew what the others had
said; `max_managed: 6` counted all three; and promotion thresholds were measured
against a third of the evidence.

**Fixed as far as it can be**: `_presence_identity` ignores a leading article,
`_resolve_presence_name` files a new spelling under the established one, and
`_fold_duplicate_presences` heals a story already carrying the split on its next
turn. Articles only — a title is often the only thing telling two background
figures apart ("the guard" and "the captain" are not one presence), unlike
roster matching where `strip_name_titles` is right.

**What is NOT fixed, and cannot be at this layer.** `A Dalek` and `The Dalek`
are one creature when the room holds one and two when it holds two, and nothing
in the strings can distinguish those cases. The merge is therefore gated on the
scene showing at most one such body (`_bodies_answering_to`), because an
over-merge silently welds two characters into one and a split is only a naming
problem. That gate is a guard, not an answer: with three Daleks in a room the
engine has three presences it cannot tell apart, and the first one to speak
collects everything.

**The fragmentation half landed 2026-08-19.** Records gained `entity_id` (a
stable scene-entity binding, made only when EXACTLY one body answers to the
identity) and `aka` (former spellings), so a presence that acquires a proper
name mid-story keeps its history across the rename, and promotion cleanup
sweeps the connected spellings.

**The keying half landed 2026-08-26.** The ledger now keys each record on a
minted presence uid (`p_` + 16 hex); the name is an ATTRIBUTE
(`record["name"]`, former spellings in `aka`), so a rename is a field update
rather than a new person, two people who share a name stay two records, and
an id stored where a name belongs cannot be confused with a name. A mint is
needed because an id does not exist for every candidate source — measured
before the re-key, 18 of 38 presences across 19 chats were never scene
entities. `presence_record_for` is the permanent name→record resolver seam
(models speak names forever); `_resolve_or_mint_presence` binds
charter_refs → entity_id → unambiguous name → fresh mint, deterministic in
its seed so pre-commit readers and the commit writer agree on a key; and
`_fold_duplicate_presences` migrates a legacy name-keyed bank on load — no
SQL, the fold's own heal-on-load precedent — in three tiers: charter binding,
provable single-entity binding (which merges two spellings only on ID
AGREEMENT, never string similarity), and a fresh mint that merges nothing.
Attribution refuses to guess: a candidate name two tracked records answer to,
with nothing this beat telling them apart, stays in the objective record
unattributed (a turn warning), and promotion refuses the same ambiguity
rather than seeding one person's sheet from both people's lines.

The collision doctrine above is UNCHANGED and still correct: ambiguity
refuses to merge, because an over-merge welds two characters into one and a
split is the recoverable direction.

**Residuals the re-key does not close, registered here:**
- **Objects tracked as presences are untouched by the key** — an object has
  a perfectly valid entity id, so `_presence_speech_verdict` /
  `_is_inert_presence_candidate` remain the guard; the record's `entity_id`
  binding now makes their scene lookup reliable under a shared display name.
- **The `known` recognition ledger is still keyed by the recognizing mind's
  own NAME** (`agents/background.py`, `_presence_recognizes`) — a presence
  rename orphans its recognition entries.
- **`world/subjects.py` still answers a tracked presence with a refusal**;
  a record bound to a scene entity could resolve positively through its
  binding instead of falling to the bodiless-presence reason.
- **Promotion evidence is still a corpus-wide casefolded speaker scan**
  (`story/importers._promotion_evidence`); drafting now refuses when two
  records share the name, but record-scoped evidence (the presence's own
  `dialogue_turns`/`recent`) would remove the scan's ambiguity entirely.
- ~~An id-shaped display name is refused as an identity but nothing yet
  MINTS a real name for such a record~~ — landed 2026-08-26: the story-law
  name generator (`story/naming.py` + `_mint_missing_presence_names`) now
  names exactly those records, permanently. Its own residuals are §1.89.

<a id="unbuilt-1-19"></a>

### 1.19 An unregistered presence has no name to be called by

**Found 2026-08-02**, fixing the Dalek whose acts never rendered (chat 58,
"Run! ⎇10 ⎇20", t23). Shelved deliberately: the fix is a change to the identity
gate, and widening that on a hunch is worse than the wrong label.

Two defects behind that turn were fixed. `cast_room` could not map a background
presence's NAME to its uid-keyed position, so `spatial_rel(None, room)` called
a machine standing in the player's own alley "remote, no known spatial channel"
and the hearing gate dropped its line for every observer — 47 of 78 background
lines corpus-wide never reached a view. And `_ordered_beat_events` collected
only a reaction's `dialogue_log_entry`, never its `action`, so a presence's act
reached the narrator nowhere. Both are closed; see `Design.md`.

**What is still wrong.** The act now renders, attributed to **"the unfamiliar
person"**. `wget(58, "known")` is `{"Hinami": ["The Doctor"], "The Doctor":
["Hinami"]}` — the Dalek is not in it, so `_speaker_display` sends it to
`_unknown_actor_label`, which derives a short descriptor from the actor's
appearance summary. An entity has no cast sheet, so there is no appearance, and
it falls through to the generic string. Wrong twice over: a Dalek is not a
person, and it is not unfamiliar — she had been warned about them and had just
thrown a rock at this one.

**The fix, and why it is not in yet.** The recognition gate exists so a
perceiver does not use a PROPER NAME they have not earned. An unregistered
presence's `name` is not that: it is authored as a descriptor — `A Dalek`,
`station engineer`, `Docking Control Operator` — and entities carry no
`identity`/`uid`/`known_to` machinery at all (both entities in chat 58 have
`identity: None`). So an entity should display under its own name, and only a
cast character's name should have to be earned.

Not done because the label is decided in two places and perception's is the
authority: perception wrote "something rolls forward a half-meter" and "The
Doctor steps between her and **the source**" into that same view. Fixing the
narrator's binding alone would leave the page and the view disagreeing about
what the player is looking at. The change wants both ends and an adversarial
identity pass, since every widening of this gate is a candidate identity leak —
the exact failure `_unknown_actor_label` was built to close when a label
derived from an appearance summary leaked the canonical name inside it.

<a id="unbuilt-1-38"></a>

### 1.38 A line addressed by epithet is addressed to nobody

`director_resolve` writes `intended_target` on every dialogue entry, and both
readers of it — `composer._addresses` and `perception._addresses` — match it
against the observer's canonical NAME by casefolded equality. Measured live
(three-model playthrough, 2026-08-12, `mix2.db` turn 1): both of Bryn's lines
carried `"intended_target": "young smith's apprentice"` — the appearance label
perception mints for strangers — where the target was the player, Corin. Every
equality test failed.

Two things ride that answer, and they are not the same kind of thing:

- `directed_at_self` on the speech percept — presentation and salience;
- `line_hear_level`'s **addressed rescue**, which is an ADMISSION decision: a
  quiet line plainly naming you is audible to you when it would otherwise not
  be. So a whisper aimed at the player by epithet is silently not delivered.

The obvious fix — also match `intended_target` against the epithets
`common.self_reference_forms` mints for that observer — is not taken here on
purpose. It LOOSENS an admission gate on a string match, and this engine's
guards subtract; a false positive delivers a line to someone it was not aimed
at. `design_notes/20-observer-epithet-floor.md` closed the prose half of this
defect deterministically and reports the structured half back through
`tell_director` (`director._report_observer_epithets`) so the Director stops
producing it. Before closing the gate, measure how often `intended_target`
fails to match any body at all across the stored corpus — if the Director
stops writing epithets once it is told, the gate never needs touching.

<a id="unbuilt-1-39"></a>

### 1.39 Micro-perception deliveries bypass the composer's identity floor

Pre-existing, and now visible beside §1.38.
`loops.deterministic_micro_perception` composes each delivered sentence with
`_observable_predicate(display, surface)` and applies **no** self-reference
rewrite at all — not the epithet floor added in note 20, and not the older
name-based `_self_second_person` every other delivery site runs. So a
character whose own name or minted epithet appears in another actor's
`observable` surface reads about themselves in the third person in their own
micro-view, and that text flows verbatim into their next character step and
their memory of the beat. (The player is unaffected: `_composer_outcome` skips
the `player` key when merging `micro_by_pid`.)

These additions also arrive at `_composer_outcome` **pre-rendered** and are
appended after the composed view, so they carry none of the percept-level
gates either — the residual already noted in
`design_notes/13-composer-build.md` ("the micro loop should emit percepts").
One fix covers both: emit percepts.

<a id="unbuilt-1-43"></a>

### 1.43 Recognition under a disguise is a boolean where the question is graded

**Found:** the disguise floors (2026-08-15). Design in
[`design/DESIGN_DISGUISE_AND_RECOGNITION.md`](design/DESIGN_DISGUISE_AND_RECOGNITION.md) §5.

`conceals_identity` now separates a disguise that covers what a body is
recognised BY from one that covers something else, which was the collapse
worth fixing first. Three things it still cannot express:

1. **Coverage vs familiarity.** A stranger and a spouse are not equally fooled
   by the same hood. The comparison wants what the disguise covers against
   what *this* observer knows the subject by, and there is currently only one
   answer for everybody.
2. **Circumstantial defeat.** A hood blows back; an illusion falters; someone
   takes hold of the concealed feature. `contact` and `spatial` both hold
   facts bearing on this and neither is consulted.
3. **Witnessing grants knowledge** — watching a disguise go on or come off
   should add the witness to `known_to` with nobody declaring it. **This is
   the highest-value item of the three and is purely deterministic**:
   perception already knows exactly who received the beat.

Deliberately NOT a seventh Director specialist: recognition is a per-observer
question and the Director emits one diff for everybody, so a specialist could
only ever produce the single room-wide verdict `known_to` already is. Every
other per-observer perceptual question here (`hear_level`,
`region_visibility`, `visual_level_between`, scent, containment, darkness) is
a deterministic ladder over typed data, and perception calls no model at all.

<a id="unbuilt-1-48"></a>

### 1.48 Language packs: what is not finished

The pack machinery is built and English is byte-identical to before the
extraction. What is unfinished is the one non-English pack and the surfaces
the language layer does not own.

**Japanese has never been reviewed by a native speaker.** `language_packs/ja`
ships `translation_status: model-draft`, `version: 0.2.0-beta`. It has been
checked for structural integrity — every canonical protocol span survives
translation, every regex compiles, capture-group counts match English, no
mask markers leaked — and none of that is a judgement about whether the
Japanese reads naturally, whether a cue is too broad, or whether the register
is right for fiction. Until it is read by someone who speaks it, treat
`story: true` for `ja` as a claim about coverage, not about quality.

**Story content authored outside the language layer stays English.** Layer B
renders admitted percepts through the pack, but several producers build reader-
facing clauses themselves and hand them over as data:

- contact and substance clauses (`spatial_prose.contact_sensation`,
  `spatial_substance.substance_event_clause`) — these reach the view AND the
  memory episode, so they are written permanently into a non-English
  character's memory bank;
- `scene.appearance_of`'s glue (`"; wearing: "`, `"; clothing state: "`), whose
  separators are also parsed back by `story/attire.py` and `agents/perception.py`,
  so translating them breaks the readers unless all three move together;
- `story/attire.py`'s ledger phrases (`"bare at the %s"`), which are persisted and
  served raw to the attire panel — a later translation does not repair stories
  already written;
- `world/paradox.py`'s `_HAZARD_WOUND_NOTE`, appended to room notes;
- the first-person memory episodes minted in `persist/commit.py` and `world/offscreen.py`
  (`"I said …"`, `"I tried to …"`, the drive-rupture memory).

The fix is not to translate the strings where they sit: each is either
literal-coupled to a parser or persisted, so the real work is moving the
clause construction behind the compositor card and migrating what is stored.
Sized as its own change, not a follow-up patch.

**`LanguagePack.fallback` is a dead contract, and the choice is drop or
keep — not "wire or drop".** The field is parsed
(`language_runtime/__init__.py:154`), published on the pack (`:118`), and
validated to point at an installed pack (`:272`) — and no lookup anywhere
consults it. A pack declaring `"fallback": "en"` gets no fallback behaviour of
any kind. Corrected 2026-08-18: a fallback RESOLVER is unreachable by
construction, so implementing one is not an option on the table.
`installed_language_packs` refuses to load at all if a story pack is missing
any system prompt id or any card leaf path the English pack has, and refuses a
UI pack missing any source message — so the miss a fallback would answer
cannot occur while the pack is installed, and if it could occur the pack is
already rejected. What is left is a decision between deleting the field and
keeping it as a declared lineage marker with the docstring saying so.
Declared-and-ignored is the same invisible-failure shape as
`capabilities.ui.css` was, and that one shipped unnoticed for a release.

**A story does not record which pack version wrote it.** Chats stamp
`story_language` and nothing else — not the pack's `version`, adapter or
translation status. So when a pack's wording or recognition tables change under
an existing story there is nothing to reconstruct the old linguistic behaviour
from: a memory minted under `ja 0.2.0-beta` is indistinguishable from one minted
under a later revision, and a story played across a pack upgrade has beats
produced under different linguistic rules with nothing on disk saying so.
Acceptable while old pack versions are not retained, but a
`story_language_pack_version` stamp beside `story_language` is one key and would
at least make a behaviour change explicable afterwards — and it is only useful
if added BEFORE the packs start moving. *(This was written twice in this entry;
folded 2026-08-19.)*

**Japanese still has open items from its first native review.** The review
(the pack's first) fixed the sentence architecture, but three things were
identified and not done:

- **Co-presence is not grouped.** English merges several present bodies into
  one sentence and counts indistinct figures (`_render_presence_group`); the
  Japanese adapter renders one sentence per body, so four people in a room
  give four clauses of identical shape, each ending 「…にいる。」 The pack's
  `dim_figures`, `count_words` and `join` are authored for this and unused.
  Worse in Japanese than English, because the sentence-final morphology
  repeats too.
- **Two dialogue renderers still coexist and disagree.** `agents/common.py`'s
  `_inject_dialogue` and `language_adapters/japanese.py`'s `_speech` both
  render speech; they now agree on articulation and tone, but they are two
  implementations of one contract and should be one.
- **`_tone_clause` picks its frame by English morphology** (noun-suffix and
  article tests) even for Japanese input. It is harmless today only because
  all three Japanese tone templates are the same string; editing one will
  surprise whoever does it. The durable fix is the prompt contract's new
  requirement that `tone` be a 体言, plus a single frame.

**"句点 inside 「」" is not normalised.** Standard Japanese practice omits the
closing 句点 inside quotation marks; the engine emits whatever the model wrote.

**A rendered view is composed in ONE language, and the suite can now see it
(F59, 2026-09-05).** Five play runs found this one field at a time -- PA14's
`youはbracedleaning。`, PD11's `youはbelowthe crestthe groundの上に
half-crouch`, PE6's `youはthe chairの上にseated。`, and `slurred` printed as a
raw enum key before them -- because nothing could see the CLASS. Three engine
faults were fixed and one check was built:

- `source_label`'s `you` is the composer's own second-person TOKEN, not
  English prose, and nine percept kinds printed it verbatim. It renders
  through the pack's `self_label` now (`JapaneseRenderer._label`).
- The pose sentence had no Japanese frame for a `relation` beside its object
  and joined its clauses with nothing -- correct for kana, and the thing that
  fused two Latin words into one that was never written. `_join_clauses`
  spaces a Latin/Latin boundary and only that; `pose_relation_at` frames the
  relation.
- The renderer borrows deterministic code from `agents/common.py` and
  `agents/composer.py`, and every borrowed helper reads the pack through the
  ambient `current_language_id`, which nothing sets outside a turn. So
  `render_view(language="ja")` composed the non-awake residue -- the WHOLE
  view for an unconscious mind -- in English, and ran the English
  second-to-first-person rules over Japanese memory prose. Both are wrapped
  in `language_scope(self.language)` now.
- `communication` is one of `composer.PERCEPT_KINDS` and the adapter had no
  branch for it at all, so every reported act of speech fell out of every
  Japanese view with no error anywhere.

**Where the line is drawn, because the check depends on it.**
`tests/test_language_packs.py` renders one percept of every kind with every
STORY-AUTHORED slot filled in Japanese, removes those authored values from
the rendered text, and fails on any Latin left. Authored content -- a proper
name, a room's name, a posture the Director wrote, a quoted foreign phrase --
is reproduced in whatever script it was written in, because translating a
name is not the renderer's job and dropping it would lose a fact; everything
else in the view is the engine's, and engine text in Latin script inside a
Japanese view is an untranslated slot every time. `Corin Asheは石床の上に
立っている。` passes; `youは石床の上に立っている。` does not.

**Two engine-owned English slots the new check does NOT yet cover, because
they live outside this agent's files:**

- `agents/common.communication_surface` builds its observable predicate from
  a hardcoded English verb table (`ask -> asks`, `warn -> warns`, sixteen
  entries), so a reported act of speech reaches a Japanese view in English.
  The table belongs in the pack beside `dialogue_verbs`; the moment it does,
  the check above catches any gap in it.
- `agents/composer.communication_percept` writes the literal
  `"speaks indistinctly"` for a partially heard communication. One string,
  same class.

**OWNER DECISION: a stored free-text fact is in the language of the beat that
wrote it (PE5, PD11).** `scene.overlays` and `poses[].detail` are free prose
written by the Director's hands in the language active at the time, stored in
the scene blob, and re-delivered verbatim for the rest of the story. A run
that switches language leaves a permanent tail: PE5 measured
`scene.overlays["Noor Haddad"]` still holding a Japanese string in an English
story on the final scene, and PD11 the reverse. No later switch can
retranslate it, and nothing in the record says which language it is.

The engine currently presents such a slot as if it were composed in the
view's language, which is the part that is wrong however the rest is
decided. Three honest options:

1. Stamp stored free-text scene fields with the language they were written
   in, and let the composer OMIT (never translate) one written in another.
   Costs a key per field and loses a fact on a switch.
2. Stamp it and RENDER it as what it is -- foreign text quoted as foreign --
   so nothing is lost and nothing is misrepresented.
3. Accept the mixture and say so in the docs.

**Recommendation: (1), the stamp, then (2) on top of it.** The stamp is the
cheap half and makes either of the others possible; without it neither is.
Not built here, and DELIBERATELY not built: dropping authored prose from a
view on a guess about its language is a worse failure than showing it. What
IS built is the detection -- a Japanese view carrying Latin-script prose from
an engine-owned slot now fails a test, and the authored-prose case is pinned
as legitimate beside it (`test_a_pose_written_in_another_language_keeps_its_
own_words_unfused`), so whichever way the owner decides, the two cases are
already separated.

**A quoted line is welded once, by the code that owns quoting (F29/F54,
2026-09-05).** Registered here because the fix has a residual worth naming.
The narrator card teaches a placeholder protocol -- the model writes `{{L1}}`
and never types a delivered line -- while DIALOGUE FIDELITY three paragraphs
above tells it to render a line as a quote. So the model wrapped the token,
`"{{L1}}"`, and `_substitute_dialogue_tokens` welded a second pair around it:
`""line""` in English, `「"line"」` in Japanese, on the majority of beats in
five separate runs. Every downstream quote guard reads quote REGIONS, so a
doubled mark shifted every boundary and the guards fired on correct prose --
21 "Delivered line rendered without quotation marks" and 10 "Narrator invented
quoted dialogue" in the flat run alone, all false, and the second of those is
enforceable, so each one bought a rewrite.

The fix is structural and not a normalisation: the substitution matches the
token TOGETHER with any marks around it and writes one pack-correct pair
(`「」` in Japanese), so a doubled mark is never written rather than detected
and repaired. Nothing anywhere normalises repeated quote runs, and nothing
should -- that would be another literal guard over free prose.

NO GUARD WAS DELETED. Both guards that fired falsely were made structural
instead:

- "Delivered line rendered without quotation marks" (`_check_speech_marking`)
  is now satisfied BY CONSTRUCTION for every token-placed line, because the
  engine writes the marks. Its remaining reach is a line the model retyped
  outside its token and outside quotes. **Residual risk:** it still asks its
  question by folding typography and substring-searching the page, so if a
  future path stops welding, it fails in whichever direction its missing
  case points. It is warning-only (not in `_ENFORCEABLE_PREFIXES`), so a
  false positive costs signal and not a rewrite.
- "Narrator invented quoted dialogue absent from the player view" compared a
  quoted span against the spans the VIEW had quoted, and a view quotes a full
  line and leaves a half-heard one unquoted (`A muffled voice: ...deafen...
  glass... midnight...`). A narrator correctly putting that fragment in the
  reader's ear was told it had invented dialogue. It now compares against
  what the view DELIVERED -- a span whose words are in the view verbatim came
  from the view, however the view marked them.

*(Two bullets left this entry on 2026-08-19 — RTL acceptance and the
deliberately broad UI catalog scanner. Both are facts a pack AUTHOR needs before
starting rather than defects in a story, and are now in
[`guides/LANGUAGE_PACKS.md`](guides/LANGUAGE_PACKS.md).)*

<a id="unbuilt-1-51"></a>

### 1.51 Residuals from immutable people identity (Directive hardening §1)

The people projection (`story_view._people`, schema 3) now keys every join
and every anonymous id on immutable identity
(`docs/design/DIRECTIVE_HARDENING_REPORT.md` §1). Two things were
deliberately left. The report's §2 is NOT among them: the executable
full-pipeline correction proof is built
(`tests/test_director_correction_pipeline.py`, commit 4ede534), so both
hardening items are closed.

- **The identity ledger still speaks names, on both sides.** `known` is
  keyed by the VIEWER's name and grants name strings. So two same-named
  viewers share one knowledge row; a granted name that several roster
  members bear admits every bearer (the projection lists all of them because
  it cannot know which one the viewer actually met — correct under "decide
  nothing", but coarser than a ledger of ids would be); and a grant matching
  no roster member's current name resolves to nobody, so a viewer who knows
  only a card-authored alias gets no roster entry. The projection
  deliberately does not join card aliases: knowing a name is not knowing its
  bearer, and an alias→id join here would disclose exactly that link. The
  real fix is the ledger itself granting immutable ids, which is
  perception's change to make, not the facade's.
- **An unregistered background presence has no immutable id to ride.** Its
  ref degrades to its tracked name — honest, because that name IS its
  identity in this engine (`commit._fold_duplicate_presences` keys one
  record per body under its first-seen spelling) — so a deliberate canonical
  rename of an unregistered presence re-keys its viewer-scoped id, where a
  cast member's survives. A presence that matters enough to be renamed
  probably matters enough to promote.

<a id="unbuilt-1-67"></a>

### 1.67 Subject spellings outside the scene blob are not folded

**Landed 2026-08-19**, to
[`DESIGN_SUBJECT_SPELLING_AUTHORITY.md`](design/DESIGN_SUBJECT_SPELLING_AUTHORITY.md):
a registered cast character's canonical spelling is the SHEET's
`identity.name`; every other being keeps the scene entity's own `name`.
Enforced by `common.reconcile_cast_entity_names` at both Director stage bodies
and on both sides of the merge at commit, so the cast-free merge fold reads an
entity record that is already right. `common.cast_spelling_policy` is the one
table both hand-rolled copies now call, the alias fold is reachable for a
name-keyed entity, and `orientation` joined `_SUBJECT_KEYED`. Measured on the
live corpus: 4 entity records renamed (chats 27, 65, 81, 82), 8 scenes healed,
21 ledger keys folded, 62 of 70 scenes byte-identical.

What is NOT folded is every durable store OUTSIDE the scene blob that holds a
subject spelling — `world_conditions` (§1.65, the same gap with its own commit,
restore and branch/clone exposure), `subject_last_seen`, and the
background-presence recognition ledgers. Each is a read-side consumer that
already resolves through identity or must learn to; rewriting them is per-store
work with its own `DATABASE.md` checklist, deliberately out of scope of the
scene fold. Close §1.65 next, citing that note for direction.

Two smaller residuals from the same landing:

- **`canonicalize_positions` still refuses aliases**, and correctly:
  `positions` keys objects and unregistered presences beside people, so a
  generic alias ("The Oncoming Storm") could name a genuinely separate entity
  and folding it would move an object into a person. It is now a stated
  `aliases=False` on the shared policy rather than a second table, but the
  underlying question — how to tell a person's alias from an object's name
  without the scene in scope — is unanswered, and it is why the entity
  reconciliation exists.
- **Two entity records for one character are left alone** by the
  reconciliation, because renaming both would mint the duplicate key
  `_dedup_duplicate_entity_keys` exists to collapse. That is a merge defect
  with its own owner; the pass declines rather than racing it.

<a id="unbuilt-1-89"></a>

### 1.89 A minted name serves only the unnamed

Landed 2026-08-26 with the story-law name generator (`story/naming.py`;
the write is `persist/commit_background._mint_missing_presence_names`,
closing §1.17's last residual): a tracked person with no real name — none,
or an id-shaped string standing where one should — draws ONE permanent name
from the story's own law (authored `naming_profile` world key > Charter
`naming` laws as separate lanes > pools harvested from the cast and the
lorebook's entries about people), deterministic in (chat, presence uid) so a
replayed commit re-lands the same name and a replacement (new uid) draws a
new one. A story yielding no law mints nothing. What the generator does NOT
serve, registered here:

- **A role-descriptor name is kept, never upgraded.** A presence the story
  calls "the barkeep" or "station engineer" has a name in the ledger's eyes,
  so it never enters the mint. Deliberate — renaming it would be the engine
  reaching for the field, the act permanence forbids — but it means the
  J2 brief's "ensign at conn" acquires a personal name only if the story
  (or a future explicit naming surface: promotion, a UI action, the
  Director introducing them) supplies one.
- **Charter bodies still fall back to a body key when the Charter has no
  law of its own.** Closed on 2026-08-27, in part. The AUTHORED story-level
  law now reaches the Charter mint — `_plan_lived_location` passes it as
  `close_plan`'s `naming_law`, so an author's explicit profile outranks a
  Charter's derived one exactly as `story/naming.py` says it should, and the
  two are no longer separate authorities. What is still unbuilt is the third
  lane: a Charter with no law, in a story with no authored law, does not
  fall through to the HARVEST and keeps `materialize_body_names`' body-key
  fallback (which `_plan_lived_location`'s unnamed check then refuses
  loudly). Deliberate for now — the harvest's pools are built from the cast,
  and handing a 42-body population names recombined from the cast's own
  elements is the contamination §1.90's guard exists to prevent, so that
  lane needs its own argument before it is opened. (The "mostly moot while
  every shipped charter is empty" note this entry used to carry was
  withdrawn with §J1: read at `item['state']` rather than the registry
  wrapper, every shipped charter is populated — 40, 37, 42, 8 and 6 bodies.)
- **The authored law has an API and no UI.** GET/PUT
  `/api/chats/{cid}/naming_profile` (web/app.py) is the configurable
  surface; nothing in `static/` renders it yet.
- **Scenario prose is not harvested.** The harvest reads structured
  evidence only (cast rows, lore `character` entries, Charter laws);
  deterministically extracting names from freeform scenario text was
  declined, not forgotten — a capitalization heuristic over prose is the
  kind of guess this repo keeps finding in the fallback-became-the-mechanism
  shape (§1.18).
- **Harvest quality is the lorebook's quality.** An epithet-titled
  `character` entry ("Sacred Rind") contributes epithet tokens; measured on
  the corpus copy, chat 67's three id-named records minted
  harvested-vocabulary names of exactly that flavour. The authored profile
  exists to outrank the harvest wherever an author cares.

<a id="unbuilt-1-90"></a>

### 1.90 A minted person never takes a registered mind's address

Landed 2026-08-27. `_refuse_name_collision` was wired to the promotion path
and the engine mints people on two paths; the Charter body allocator
(`world/charter_identity.materialize_body_names`) took the other one.
`story.naming.registered_identity_names` →
`charter_identity.identity_reservation` → `name_is_reserved` is now the
single answer both consult, subtracting at the persisted law
(`strip_reserved_pools`) and again at the candidate. What it does NOT close,
registered here:

- **A name element is refused only where the law addresses people by it
  alone.** `address_components` reads the story's own `name_format` /
  `formal_format`; under `{given} {family}` two people may share a family,
  which is correct and is also why a story whose prose calls people by
  surname while its LAW writes full names gets no protection from the
  element rule. The whole-name refusal still holds there. The honest fix is
  an authored law that says how people are addressed, not a heuristic over
  prose.
- **Only the head and the tail of a registered name are its address.** A
  token buried mid-name is not matched, so a three-part name whose middle
  element is what everyone actually uses is not protected. No measured case;
  registered because the rule is a choice.
- **Nothing renames what is already named.** A story that already holds a
  generated body under a registered surname keeps it: the mint is a write
  and this is a subtraction at the mint, not a migration. Chat 95's two
  measured bodies stay as they are unless the author changes them.
- **The refusal is silent.** A candidate refused is simply not drawn; a
  generation whose pool is exhausted BY the refusal surfaces as
  `_plan_lived_location`'s unnamed-body error, which names the bodies but
  not the reason. A pool small enough for that to happen is rare (the
  measured laws carried 12 and 27 family elements) and the loud failure is
  correct; a note saying "the reservation took the last one" would be
  better.

<a id="unbuilt-1-90a"></a>

### 1.90a A generic name is never made out of a named person — LANDED

Landed 2026-08-28. The mint's material was a model's, and the guard was a
filter. `refuse_harvested_pools` emptied a generated law's name POOLS and kept
its FRAGMENTS on the premise that "a fragment names nobody however well a
model knows a canon". Measured across three consecutive generations of one
institution: two of the three supplied `family_parts.starts` that were, entry
for entry, the openings of the cast's own surnames — one list 100% so,
including an element belonging to a character registered in that chat — and
the third supplied ordinary fragments touching nobody. Variance in what a
model volunteers, which is why the guard cannot be the model. Reproduced with
that law as a fixture, one body came out wearing a registered person's
surname EXACTLY, assembled from a three-letter opening and a two-letter
ending, past every guard the engine had.

`charter_identity.fragment_is_name_element` runs the same rule at the
fragment (anchored at the head and the tail, `NAME_ELEMENT_FLOOR` = 2), and
`refuse_harvested_material` pairs it with `_fill_empty_material` so a refusal
that empties a field is answered rather than left to surface as a generation
failure. `story.naming.phonology_lanes` is now a real lane, ranked authored >
phonology > charters > harvested. `tests/test_name_material_partition.py`,
`tests/test_phonology_lane.py`. What it does NOT close, registered here:

- **The exact-surname share at the mint is still reachable, by design as
  currently pinned.** Under `{given} {family}` `address_components` is empty,
  so `name_is_reserved` refuses a component only when it is somebody's WHOLE
  untitled name, and `reconstructs_a_reserved_name` deliberately permits an
  exact share ("a registered `Beverly Crusher` does not reserve every
  `Beverly`"). A law whose material legitimately assembles a registered
  surname therefore still can. The measured route to it was the fragments and
  that route is closed; the general case is an owner ruling, because closing
  it reverses `test_a_paired_law_keeps_the_element_and_refuses_the_whole_name`
  and `test_generation_without_a_reservation_still_stores_its_law`, which pin
  the sharing permission on purpose. **`strip_reserved_pools` already made the
  opposite ruling for POOLS** ("a pool that CONTAINS a named individual's
  family name is the engine ISSUING that individual's name to strangers"), so
  the two halves of the engine currently disagree about the same string.
- **The last-resort pool branch still exists.** `refuse_harvested_material`
  falls back to the (subtracted) pools when refusal and both replacements
  leave a law with no assemblable material. It is strictly no worse than the
  behaviour before the refusal existed and both measured generations reach it
  never, but it is a path on which a model-supplied name list still reaches a
  body. Removing it needs a story measured to hit it.
- **`NAME_ELEMENT_FLOOR` = 2 is a new number and wants the owner's eye.** One
  letter is the alphabet and refusing it would take the alphabet away from
  the law; two letters that open or close somebody's name are a piece of that
  name. The cost is real and unmeasured on a large lorebook: every two-letter
  opening of every `character` entry's name becomes unavailable as material,
  and a story with a very large named cast could lose a noticeable share of
  ordinary syllables that way.
- **The vocabulary lane is thin where a setting's places are short words.**
  `vocabulary_name_parts` reads the plan's structure, room names and room
  purposes through `derived_name_parts`, and a single-syllable room name
  ("Hall", "Bay") contributes nothing. A generation whose law is wholly
  refused AND whose rooms are all single-syllable falls through to the pool
  branch above.
- **A refused fragment is silent.** Same shape as §1.90's last residual: the
  law simply carries fewer openings and nothing records that the reservation
  took them. A generation whose material narrows sharply is worth saying so
  about.
- **The measured repetition is the honest cost and is not hidden.** With the
  gen-C law refused, three given openings and three family openings survive,
  so 24 bodies draw from a 12 x 9 space and family names recur. That is the
  capacity allocator's documented reuse-after-exhaustion, not a new defect;
  a law that gives one clean opening in three cannot sound wider than it is.

<a id="unbuilt-1-91"></a>

### 1.91 Nothing tells a character they were addressed

Confirmed by grepping all 77 character payloads across three instrumented runs:
zero hits for any representation of addressee-hood. The `decision` block a
character receives is three keys — `deep_tom_requested`, `dialogue_mode`,
`speech_budget` — and none of them says a question was put to this mind.

The engine KNOWS: `flow.addressed_to` resolves, `agents/loops.py` uses it for
speaker ordering and for the silence guard. It reaches the loop and stops there.
Even on the path that works, a question arrives as a sentence inside
`perception.view`, attributed to an unrecognised body — "An indistinct figure
says in an inquiring voice: ..." — with nothing marking it as directed at the
reader rather than overheard.

AND THE NOTE THAT WOULD SAY SO FIRES ONE BEAT LATE, BY CONSTRUCTION.
`agents/character.py:339 _unanswered_question_note` is bounded
`WHERE t.idx >= ? AND t.idx < current_turn_idx`, so the current beat's own
interpret is out of range. Measured: on the beat a character was asked, no
note; on the NEXT beat it appears as
`{"from": "the player", "asked": "...", "turns_ago": 1}`. On the beat it
matters, it is structurally unable to fire.

RESIDUAL inside it: a line whose vocative names one character was booked as a
debt owed by ANOTHER — the gate trusts the asking character's own
`interaction.addresses` list, and a line addressed by name to somebody else can
still land in it.

<a id="unbuilt-1-92"></a>

### 1.92 A registered character can be voiced by the background path — FIXED

When a cast member is placed into a Charter post (`featured_residents`), they
become a Charter BODY — and `pick_background_reactors` selects Charter bodies.
So a character with a full agent, memory and psychology became eligible for the
stateless background reactor.

Measured: one beat had the captain give two orders as himself, and then a
background presence named `captain <his own name>` say "Acknowledged,
Lieutenant" — rendered to the player as "a voice she couldn't place". Every
subsequent beat carried a cast member as its background presence. Re-measured
in chat 95 (2026-08-28): `background_react` selected
`"lieutenant_commander Data Data"` on turns 2/5/7/11 and
`"captain Jean-Luc Picard"` on turn 15, and `members_of(state,
"main_bridge")` counted both of those bodies as anonymous crowd ground — 10
members where 8 is right.

**Fixed at the derivation, not at the gate.** The eligibility predicate at
`world/charter_runtime.background_presence_records` and its twin at
`world/charter_crowd.members_of` both asked "has a binding been recorded"
(`body_key in state["bindings"]`), and a binding is written only by
`bind_promoted_character`, reached only down the `character_histories` route.
Chat 95 was generated by calling `generate_lived_location` with
`featured_residents=` directly — which the public API accepts, and which
RETURNS bindings for the caller to apply rather than applying them — so
`state["bindings"] == {}` for all four cast and the exclusion was a no-op for
every one of them. Both sites now ask
`world.charter_model.body_of_an_authored_mind`, which reads BOUND **or**
RESERVED (`resident_seed_id`, minted with the body): a seat reserved for an
authored person is that person's seat from the moment it is minted, whether or
not the wiring that names the person has run. The record never reaches
`with_charter_presences`, `_addressable_ledger`, `charter_emergence_pick` or
the gate at all. Pinned by
`tests/test_authored_seat_is_not_anonymous.py`.

RESIDUALS, none of them the identity question:

- **Scope, for the owner.** The predicate excludes every featured seat, not
  only one attached to THIS story. A generated town can carry a featured
  resident who is authored but unattached; that body is now out of the
  background and crowd paths too. Safest, and it removes a body someone may
  have wanted the background path to voice.
- **The gate's roster backstop still cannot match.** `pick_voice_demand`
  excludes registered minds by casefolded display-name equality against
  `_registered_name_roster`, and the charter's `formal_format` guarantees the
  derived display never equals the registered name (`lieutenant_commander
  Data Data` vs `data`). Left as a same-name backstop; deliberately NOT
  hardened by fuzzy matching, which the module already documents as forbidden
  for forcing decisions (`_background_name_named_exactly`, the six-for-one
  failure). The record simply must not reach it.
- **`display_name` formatting** (`world/charter_identity.py`) applies
  `formal_format "{rank} {given} {family}"` with the RAW rank token
  (`lieutenant_commander`) while the humanised form sits in `body["title"]`
  and in `naming.titles.posts`; and `_stored_name_components` on a mononym
  fills both the given and family slot — "Data Data", "Worf Worf". Owned by
  the name-generation pass. Note it does not cover the above: humanising the
  token still leaves "Lieutenant Commander Data Data" ≠ "Data".
- **`generate_lived_location` still returns `featured_residents` bindings
  that nothing applies** unless the caller goes through
  `_complete_cast_histories`. The reservation predicate makes the reservation
  self-sufficient, which is why it was the minimal fix; applying the bindings
  at the API seam is still the tidier answer.
- **Twelve other sites spell `body_key in bindings`** and mean "an authored
  person's body" (`world/charter_run.py:438`, `charter_author.py:186`,
  `charter_observe.py:168`, `charter_model.py:423`,
  `charter_runtime.py:1728/1796/2103/2139/2368/2455/2594`,
  `agents/common.py:1643`). Some of them mean "already promoted", which is a
  genuinely different question from "reserved". Flagged, not swept — each
  needs its own read.

<a id="unbuilt-1-104"></a>

### 1.104 The persona has no per-story copy, so a card edit reaches every story at once

**Found:** 2026-09-03, auditing the per-chat copy design against the code.

Every attached CHARACTER carries a story-local copy: `chat_chars.sheet` holds
the authored card this story reads (`COALESCE(cc.sheet, ch.sheet)` in every
one of the ten readers), `chat_chars.state` holds the runtime mind, and
`chat_char_frames` splits both per frame. A branch copies all three, and a
checkpoint snapshots `state`/`status` while deliberately leaving `sheet`
alone, because a card is configuration and not a turn fact.

The PLAYER has none of it. `chats.persona_id` points straight at the library
row and `persona_of` reads `personas.sheet` verbatim; there is no
`chat_personas.sheet`, no COALESCE, and no writer that would fill one. So
editing your persona in the library rewrites who you were in every story that
persona has ever played, retroactively, with no branch and no checkpoint able
to recover the earlier reading. The engine treats characters and players as
near-equals everywhere else, and this is the largest place it does not.

What DOES vary per story for the player is real but partial, and all of it is
name-keyed scene state rather than a card: `persona_private_history` (a world
key that shadows the sheet's authored copy), the attire ledger, conditions,
positions, and the recognition map. Those branch and checkpoint correctly,
because they live in `world` and the snapshot takes it whole.

The shape of the fix is the one the characters already have: a nullable
`chat_personas.sheet` (plus `chats.persona_id`'s row for the primary player),
one COALESCE at `persona_of` and `story.scene`'s two persona reads, the same
identity-immutability refusal `chat_char_card_put` enforces, archive and
branch carry, and a checkpoint that leaves it alone. Until then, tell hosts
plainly: a persona edit is retroactive across their whole library.

<a id="unbuilt-1-106"></a>

### 1.106 Promotion has four authorities and the owner wants two

**Owner, 2026-09-04**, deliberating rather than deciding: promotion matters
less now that charter gives a townsperson real depth for almost nothing, and it
should become "solely within the player and Story Planner's authority."
Recorded here with what that would actually cost, since three of the four
authorities that exist today are the engine's.

**What holds the power now.**

- **The engine's autonomous sweep** (`auto_promote_background_characters`,
  commit tail). Mints a sheet with a model call and attaches a permanent cast
  member. Already off unless the host sets `auto_promote`, on the argument in
  `_auto_promote_enabled`: a story must not acquire cast the host never asked
  for from a passer-by who happened to talk twice.
- **The engine's deterministic proposal** (`_propose_promotions`). "A mind is
  earned, and the engine says when." At the per-chat thresholds it stamps the
  record, tells the Director through `tell_director`, and raises a turn
  warning. It was built for a measured failure, Harrowmere turns 5, 15 and 17:
  the Director wanted to keep a person, wrote them into `cast_changes` which
  attaches nobody, and the refusal told it nothing about the channel the
  engine already held.
- **The host's review** (`/promotions/draft` and `/promotions/confirm`, the
  presences panel). This is the half the owner wants to keep.
- **The Story Planner: nothing.** The room cannot propose, plan or perform a
  promotion. It has `plan_entity` with `kind: person`, which plans somebody
  who does not exist yet; promotion is the opposite motion, a presence the
  story has already been playing becoming a mind.

**What moving it means, concretely.** Retire the sweep and the setting that
gates it. Keep the draft and confirm routes exactly as they are. Give the room
a promotion proposal that lands in the room thread rather than a turn warning,
so the judgement "this innkeeper has become someone" is made by something that
has read the story rather than by two counters.

**Two things must not be lost with the counters.** The Director still needs to
be told, in the beat, that a presence it wants to keep is proposed and that
`cast_changes` attaches nobody -- that is what `_propose_promotions` was built
for, and the room proposing on its own schedule does not reach the Director on
the beat it matters. And a story with no room seated needs SOME answer, or
promotion silently stops existing for it; the thresholds are the current
answer and would become the fallback rather than the mechanism.

**A live defect either way:** `promotion_thresholds` is absent from
`SETTING_PROVENANCE` and therefore from `PRESERVED_SETTING_KEYS`, while
`background_config` and `dialogue_config` both have entries -- so a threshold
set by hand is rolled back by any restore or reroll.

## 5. Deferred backlog

<a id="unbuilt-5-5"></a>

### 5.5 P7 remainder — promotion-turn identity binding

*Low severity, cosmetic.* On the turn a background presence promotes to cast,
the player's view can render it "the unfamiliar person" for one turn: promotion
runs at commit, after that turn's perception, so the canonical name is not yet
in the observer's `known` set. The alias/variant fallback (`_recognizes`) and a
full mutual roster in `promote_background_character` shipped; what remains is
that the roster registers only the canonical `character_name(sheet)` with no
aliases or variants, and that the **attach** path in `web/app.py` seeds only
player↔character, never cast↔cast. Test: promote a presence the player
addressed by name, assert that turn's view of it is not anonymized.

---
