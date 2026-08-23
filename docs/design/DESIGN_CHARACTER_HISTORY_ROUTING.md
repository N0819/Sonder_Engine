# Design: character history is routed, not universally simulated

**Status:** partially built. Greeting launch and multi-character Story Quick
Start now share the conservative router, per-character author choices and
guidance, resident Charter handoff, and an initial cited or explicitly
generated journey compiler. Continuity import, bounded arrival intersections,
richer canon-claim verification, and cast selection in the hand-built story
path remain unbuilt. Current implementation authority remains the source and
maintained guides. Unfinished work is registered in
[`docs/UNBUILT.md`](../UNBUILT.md) §2.20.

Written 2026-08-22 against the current Charter pre-simulation and greeting
handoff implementation. This note extends
[`DESIGN_PRESTORY_MEMORY.md`](DESIGN_PRESTORY_MEMORY.md): that document owns
memory density, retrieval, provenance, inheritance, and the argument for a
summary-heavy, episode-light past. This document answers the earlier question:
**which kind of past should be constructed for this particular character?**

The ruling, stated first:

> **Charter is one character-history backend, not the character-history
> generator. Route the character's continuity first. Use Charter only when
> their life during the simulated period is organized by a bounded location or
> institution.**

---

## 1. The failure this design must prevent

The first production slice places a greeting card character into a generated
location as a featured Charter resident. That is a strong fit for Sarah Moon
at Site-17: the facility, her work, its reporting lines, and the people she
repeatedly encounters are the structure of her recent life. Charter can
simulate that structure rather than merely describe it.

The same operation is wrong for the Doctor. His continuity is not a month of
local shifts. It is a sequence of journeys, arrivals, departures, encounters,
and authored canon. Giving him an available institutional post because one
matches his competence produces a coherent Charter record and a false
character. The system would be wrong more convincingly than a blank history.

This is not a special Doctor rule. The same mismatch affects:

- itinerant adventurers, couriers, explorers, pilgrims, and fugitives;
- diplomats or inspectors visiting a place temporarily;
- returning characters whose important past happened elsewhere;
- canonical figures whose history is author authority rather than simulation
  authority;
- player-created wanderers deliberately defined by having no settled role;
- characters attached to a moving home but not governed by its institution.

The defect would begin one step before memory generation. Once the wrong
backend has declared that the character stood a post for thirty watches, every
later layer can be perfectly grounded and still preserve the original mistake.
The routing decision therefore has to precede generation, pre-simulation, and
memory selection.

## 2. A character class is too blunt

An enum such as `resident | traveler | canonical` looks convenient and fails
as soon as the examples overlap:

- a starship captain travels constantly but is institutionally rooted;
- a merchant caravan is mobile but has stable posts, stock, obligations, and
  reporting relationships;
- a monarch may be fixed in one court, traveling with a court, or visiting
  another polity;
- an eccentric traveler may spend six quiet months teaching at one academy;
- a canonical character may legitimately acquire new simulated experiences
  after their authored history ends.

The router needs three independent axes. Their composition determines the
backend and prevents one label from smuggling in three unrelated assumptions.

### 2.1 Continuity anchor — what organizes daily life?

**Fixed place.** A town, facility, court, hospital, station, monastery, prison,
farm, school, or household. The person stays within a bounded location long
enough that its work, scarcity, relationships, and command structure organize
their recent history.

**Bounded moving place or institution.** A starship, caravan, traveling court,
military unit, touring company, or expedition. It changes world position, but
the person remains inside a stable social and operational system. From their
point of view, the bridge or wagon train is where life keeps happening.

**Itinerary.** Continuity is a route through distinct places. Encounters,
departures, carried obligations, discoveries, and route choices matter more
than watches and upkeep. There may be recurring companions without a chartered
institution.

**Unanchored.** The card intentionally supplies no stable place, group, or
route for the period. The honest result may be authored summaries only, a
recent arrival, or no generated episodes.

### 2.2 Past authority — who is allowed to say what happened?

**Simulated.** The engine may produce new objective pre-story events inside
the author's constraints. Every memory must cite those events.

**Authored.** Card and lore material are the truth. The engine may structure,
select, date loosely, and make it retrievable; it may not replace the canon
with a generated substitute.

**Inherited.** Prior play is imported by an explicit author action. It must be
persona-scrubbed, frame-explicit, and treated as continuity chosen for this
story rather than as a fact that automatically crosses between chats.

**Controlled mixture.** Authored history establishes hard points; simulation
may fill bounded gaps or add later intersections. A generated event that
conflicts with an authored point is refused or shown to the author, never
averaged into plausibility.

### 2.3 Opening relationship — why are they here now?

**Resident.** This location or mobile institution is their current home or
ordinary sphere of activity.

**Returning.** They have genuine prior history here, left, and are now back.
The local simulation may cover the earlier period and the consequences of
their absence, but must not pretend continuous residence.

**Visiting.** They overlap the location for a bounded interval. They may meet
residents, create obligations, acquire reports, or affect stock during that
interval; they do not inherit a local career.

**Just arrived.** Their prior continuity happened elsewhere. Local
pre-simulation may establish the circumstances and witnesses of arrival, but
not weeks of retroactive participation.

These are relationships to the opening location, not permanent traits. The
same character can be a resident in one story and a visitor in another.

## 3. Routing table

The route is derived from the axes, then stored once for the story. `auto` may
recommend a route, but is not itself a backend.

| Anchor and authority | Opening relationship | History backend | What it may produce |
|---|---|---|---|
| Fixed place + simulated/mixed | resident | **Charter resident** | service, local evidence, judgments, commitments, reports, decisions, material incidents |
| Bounded moving institution + simulated/mixed | resident | **Charter within the moving place** | the same institutional history, anchored to ship/caravan/unit rather than each world stop |
| Fixed or moving institution | returning | **Charter interval + absence boundary** | actual earlier service, departure, durable local consequences; no fabricated continuous tenure |
| Any local anchor | visiting | **Bounded Charter intersection** | only events during the visit; no standing post unless explicitly authored |
| Itinerary + simulated/mixed | visiting/arriving | **Journey history** | route legs, encounters, carried information, promises, losses, discoveries, arrivals |
| Any anchor + authored | any | **Authored-history compiler** | one era summary and a few provenance-correct memories selected from card/lore evidence |
| Any anchor + inherited | any | **Continuity import** | scrubbed summaries or explicitly selected episodes from prior play |
| Unanchored + authored or none | arriving | **Summary-only or none** | authored continuity and greeting-established memories; no counterfeit activity |

The table deliberately allows composition. A canonical traveler may use the
authored-history compiler for most of their life, a journey route for a small
author-approved gap, and one arrival intersection with the opening location.
No backend is required to impersonate the others.

## 4. Worked examples

### Sarah Moon at Site-17

- Anchor: fixed place.
- Authority: controlled mixture — Site-17 lore and card history constrain the
  role; simulation supplies recent service and incidents.
- Opening relationship: resident.
- Route: Charter resident.

Only public card material reaches placement. The location is simulated. Her
private history and personality then constrain a licensed recent-life pass
over the real named roster, rooms, duties and simulation anchors. At handoff,
the full character owns separate career and recent-life summaries plus 10–16
detailed, independently identified episodes; Charter no longer speaks or
decides for her.

### The Doctor arriving at Site-17

- Anchor: itinerary.
- Authority: authored or controlled mixture with canon locked.
- Opening relationship: just arrived or visiting.
- Route: authored-history compiler + journey/arrival evidence.

Site-17 can still pre-simulate its residents for a month. The Doctor is absent
from that history unless lore says he was present. A recent tail may establish
the TARDIS arriving, who perceived it, and what information or obligations
crossed during the encounter. It may not assign him `lead_scientist`, infer a
month of employment from his competence, or replace his authored travels with
a locally convenient career.

This is the primary falsifier for the router: **a Doctor-like traveler must
have zero Charter watches, posts, or local-service memories unless the author
explicitly chooses a period of institutional residence.**

### A starship captain

- Anchor: bounded moving institution.
- Authority: simulated or mixed.
- Opening relationship: resident.
- Route: Charter within the ship.

The ship moves, but the captain stays inside the institution whose watches,
stock, maintenance, reports, and command decisions organize their life. World
coordinates changing does not make this an itinerary history.

### A caravan merchant

Two valid routes exist and the distinction is authorial:

- A member of a stable caravan organization uses bounded-moving Charter plus
  the existing physical route, freight, and stop exchange systems.
- A lone merchant moving opportunistically uses journey history. Their past is
  a sequence of deals, debts, route choices, and encounters, not an imaginary
  wagon-company hierarchy.

### A returning monarch

Authored history establishes reign and exile. A fixed-place Charter interval
may simulate the court before departure; the local world continues during the
absence; the opening relationship is returning. The router must preserve the
gap. Treating the monarch as continuously on the throne would erase the
premise the story is about.

## 5. Auto-routing without private leakage

Automatic routing is useful because most authors should not have to understand
the architecture. It must remain a recommendation with an explanation.

The classifier may consider:

- the character's public history and public abilities;
- the opening brief or selected greeting;
- lore snippets retrieved specifically for character/location relevance;
- explicit author choices such as “lives here,” “visiting,” or “just arrived”;
- a private, character-only routing pass when private history is essential to
  the decision.

The last item needs a two-stage firewall:

1. A routing classifier may inspect the effective story-local character card
   and emit only closed route fields, confidence, and cited reasons.
2. The chosen backend receives the minimum projection it needs. A Charter
   planner still receives only public placement material. Private prose never
   becomes location lore, a post description, or another resident's knowledge.

The classifier must not return a free-prose backstory. Its output is a routing
decision, not history. When confidence is low, the safe default is **no local
residency** and a visible author choice—not “find the nearest matching job.”

The mapping agent's relevance-query pattern is the right precedent: retrieve a
small lore slice for the named decision rather than sending an entire lorebook
or trusting the model to know what matters.

### Proposed route shape

This is a design object, not a committed schema:

```json
{
  "mode": "auto",
  "anchor": "itinerary",
  "authority": "authored",
  "opening_relationship": "just_arrived",
  "backend": ["authored_history", "arrival_intersection"],
  "participation": {
    "starts_hours_before_opening": 2,
    "ends_at_opening": true
  },
  "author_locked": true,
  "confidence": 0.91,
  "reasons": [
    {"source": "card.public_history", "claim": "travels between worlds"},
    {"source": "greeting", "claim": "arrives at the opening"}
  ]
}
```

Protocol names should be chosen only when the schema is implemented. The
important properties are separability, cited reasons, a bounded participation
interval, and an author lock.

## 6. Backend contracts

### 6.1 Charter resident history

The current greeting implementation is the reference:

- stable resident seed;
- public-only placement projection;
- exact body binding after deterministic closure;
- actual pre-simulation evidence;
- memory selection/classification over immutable evidence;
- full-cognition handoff exactly once;
- retirement of the duplicate Charter mind while retaining institutional
  projection, office, service, relationships, and reporting position.

The missing generalization is not “send every wizard character through this.”
It is “invoke this backend for every route that resolved to resident Charter.”

### 6.2 Journey history

Journey history should be sparse and event-ledger based. Its universal
primitives are:

- route leg and arrival;
- encounter with a person, group, place, or obstacle;
- promise, debt, favor, contract, or report acquired/carried;
- material gain, expenditure, damage, scarcity, or loss in qualitative bands;
- decision to continue, divert, wait, return, or abandon;
- companion joining, separating, or becoming unavailable.

It must not simulate every meal, mile, or coin. Like Charter, storage should
grow with branches and consequential intersections, not elapsed time. Unlike
Charter, it has no standing duty-post assumption.

Journey events are still objective facts with witnesses and locations.
Information travels through the existing carrier rules. A traveler does not
know what happened at the destination before reaching it merely because the
route generator planned the stop.

### 6.3 Authored-history compiler

This backend does not invent replacement canon. It turns existing card and
lore material into the retrieval substrate described by
`DESIGN_PRESTORY_MEMORY.md`:

- summary-heavy, episode-light;
- `turn_idx IS NULL`, never negative story turns;
- one compact era summary and no more than six supporting episodes for the
  opening budget unless measurement changes that cap;
- provenance describes the character's in-fiction relationship to the fact
  (`remembered`, `told`, `read`, `inferred`), never the host-facing word
  `authored`;
- citations resolve to immutable card/lore evidence;
- contradiction is surfaced rather than silently repaired by generation.

### 6.4 Continuity import

Import is an explicit host act. It must first repair the known defects recorded
in `UNBUILT.md` §1.74: scrub the prior story's persona, preserve archival
status, and write the intended frame explicitly. Summary-only inheritance is
the safer default; full episodes are a deliberate stronger choice.

### 6.5 Recent arrival or visit intersection

This is not a fifth full simulator. It is a bounded overlap between a character
and a location's actual tail:

- the character exists in local simulation only during the declared interval;
- only co-located events can enter their evidence packet;
- local residents learn of them through perception, reporting, and carriers;
- the character acquires no local post, tenure, or obligation without an event
  that creates it;
- the opening can therefore inherit genuine first impressions without a fake
  local career.

## 7. Memory density is shared across every route

Different history backends must not buy different-sized minds. The output
budget belongs to the memory layer, not to Charter or journey generation.

The resident route now uses:

- one career summary and one recent-life summary;
- 10–16 episode-like memories, each a separate row with its own chronology,
  location, named people, affect and consequence;
- a hard ten-row quality floor: ordinary life may be quiet but may not be
  represented by empty acquaintance labels or a watch counter;
- authored standing knowledge remains available through its existing card
  channel until the separate “knowledge versus memory” decision is settled;
- the model may invent bounded personal incidents because the resident route
  is explicit prehistory authoring, but it may use only the supplied roster,
  rooms and duties and may not invent major canon or institutional outcomes.

The caps still keep a month at Site-17 from becoming hundreds of diary rows.
The previous six-row ceiling was rejected after live Diagnosis chat 83 yielded
one watch-count summary, three rows reading only “I know Dr.”, and one generic
private-habit row. That result had neither identity nor retrieval value. Deeper
eras remain a future tier rather than inflating this recent-life batch.

## 8. Story-start ordering

History construction must finish before the opening becomes visible, while
preserving greeting-established cognition.

The built greeting order is the invariant:

1. extract the chosen greeting for routing and mind seeds;
2. attach selected lore;
3. generate and pre-simulate the location;
4. seed the original greeting's memories, beliefs, stances, and affect;
5. compile the selected history backend's grounded memories and hand off any
   temporary background cognition;
6. run establishment/turn zero;
7. replace narrator prose with the selected greeting verbatim.

“Extract first” is preparation, not playback. The reader sees the greeting only
after pre-simulation and handoff finish. If required generation fails, no
opening plays and no half-created story remains.

For multi-character story creation, each character may resolve to a different
route. The location may pre-simulate once; routed participation is then sliced
per character. This is why the route cannot be a single story-wide checkbox.

## 9. Authoring UI

The default UI should be legible without exposing backend names as the choice.
Each selected character gets one summary row:

```text
Sarah Moon   Lives here · recent local history             Change…
The Doctor   Just arrived · authored travels preserved     Change…
Mara Venn    Travels with the caravan                      Change…
```

Opening **Change…** offers reader-facing choices:

- **Auto — use the card and lore** (recommended when confidence is adequate)
- **Lives here**
- **Travels with this place or group**
- **Visits or arrives at the opening**
- **Use authored history only**
- **Continue from another story…**
- **No generated past**

An advanced disclosure may expose the three axes. The immediate preview must
say what will happen in concrete terms:

- whether the character participates in local pre-simulation;
- whether new events may be generated;
- which authored material is locked;
- the maximum resident output (two summaries plus sixteen experiences);
- the estimated extra model calls;
- why auto chose the route.

Mid-story location generation remains conservative. Adding a lorebook-backed
city must never silently relocate the active cast. An author may explicitly
connect a character to the new place, review the route and overlap interval,
and then generate the additive history.

## 10. Observability

Every character-history result needs an author-only explanation surface:

- resolved axes, backend, confidence, and whether the author overrode auto;
- the exact public/private/lore evidence used to route, with private evidence
  never copied into the generated location;
- participation interval and every place touched;
- generated event ids and authored evidence citations;
- compiled summaries and memory event keys;
- dropped unsupported claims;
- contradictions between generated and authored material;
- cognition handoff status and proof that no duplicate background mind remains;
- fallback behavior when a model call fails.

The current Charter diagnostics panel is the first instance of this surface.
The eventual history inspector should normalize the same questions across
Charter, journey, authored, and inherited routes rather than exposing four
unrelated JSON dumps.

## 11. Information and authority boundaries

The router must preserve these invariants:

1. **Truth is not memory.** A generated event enters a mind only through a
   route-specific evidence packet proving the character experienced, heard,
   read, or inferred it.
2. **Competence is not residence.** A matching skill licenses no post, tenure,
   or local relationship.
3. **Authored canon outranks gap generation.** Simulation fills allowed space;
   it does not negotiate with a locked fact.
4. **Private routing evidence stays private.** A classifier may use it to
   choose a closed route; a location planner and other minds may not receive
   its prose.
5. **One cognition owner.** A temporary Charter/background representation is
   retired when a full character takes ownership.
6. **Names and identities remain stable.** Routing and handoff use permanent
   ids; generated titles, ranks, aliases, and learned names never replace the
   character's canonical identity.
7. **No automatic cross-story continuity.** Inheritance is explicit,
   scrubbed, and target-story scoped.
8. **No model-minted past during play.** Later play may reinterpret or dispute
   a seeded memory; it may not invent an uncited childhood event and backdate
   it into truth.

## 12. Refused designs

### Every selected character becomes a Charter resident

Refused by the Doctor case. It confuses competence with tenure and produces
grounded falsehoods.

### One powerful model writes every character's complete history

Refused as authority, even if the prose is convincing. A single call may be a
good compiler over already-grounded evidence; it is not evidence that the
events occurred. It also encourages thick banks that dominate opening recall.

### Infer the route secretly and never show it

Refused because a plausible classification can still reverse the premise of a
story. The author must see “resident,” “visitor,” or “arrival” before paying for
history generation.

### Let private history flow into the location planner

Refused because routing need does not make private autobiography into public
world lore. Use the two-stage classifier/projection boundary instead.

### Build genre-specific traveler simulators

Refused. Journey history owns universal route, encounter, obligation,
information, and material-change primitives. Lore decides whether the route is
through hyperspace, desert, dream realms, or diplomatic salons.

### Generate first, classify afterward

Refused because classification cannot repair an objective ledger after the
wrong simulator has minted it. Routing is the first decision.

## 13. Falsifiers and regression cases

The design is falsifiable at both routing and fiction layers.

### Required adversarial fixtures

**Sarah Moon / rooted professional**

- resolves to fixed-place resident;
- planner receives no private marker;
- stands lore-appropriate posts;
- receives only event-cited pre-story memories;
- full cognition owns the opening and Charter mind is retired.

**The Doctor / canonical eccentric traveler**

- resolves to itinerary + authored + arrival/visit;
- receives zero local watches, posts, tenure, or service rows;
- authored continuity survives unchanged;
- only actual arrival-tail intersections may become local memories;
- the selected greeting remains verbatim after history processing.

**Starship captain / moving institution**

- resolves to bounded-moving resident, not itinerary;
- duties anchor to ship rooms, not every port visited;
- ship movement does not reset institutional history.

**Returning exile**

- earlier residence and absence are both represented;
- no events are attributed during the absence;
- local judgments may persist and change without granting the exile knowledge
  of those changes.

**Multiple selected characters**

- one location generation may route residents, visitors, and arrivals
  differently;
- no character receives another character's private routing evidence;
- one failed route cannot silently coerce the others to resident.

### Measurements

- route overrides: how often authors reject `auto`, by proposed route;
- false-residency rate in an adversarial card corpus;
- share of pre-story recalls in turns 0–20, by backend;
- unsupported/citation-dropped history claims;
- authored/generated contradictions;
- duplicate-cognition defects after handoff;
- pre-story memories that are later integrated, disputed, or never recalled;
- cost per character and latency added before the opening.

The router is wrong if Doctor-like fixtures acquire local careers, if
institutionally rooted ship crews are treated as disconnected travelers, or if
the thin history arms still read as amnesiac compared with thick generated
histories. Those failures would invalidate the axes, not merely call for prompt
tuning.

## 14. Build order

The safest implementation sequence follows the authority boundary:

1. Add a pure route proposal/validation object and author-visible preview. Do
   not generate any new history yet.
2. Let manual author choices select the already-built Charter resident backend.
   Keep `auto` advisory until the route corpus is measured.
3. Build the authored-history compiler on the pre-story memory substrate and
   its fixed density budget.
4. Repair explicit continuity import before exposing it as a route.
5. Build sparse journey history from universal event and carrier primitives.
6. Add bounded visit/arrival intersections with location pre-simulation.
7. Enable automatic routing only after adversarial fixtures measure false
   residency and false itinerary rates.

This order makes an early mistake visible and reversible. The dangerous order
is to generate histories first and hope a later classifier can explain them.

## Standing conclusion

A convincing past is not one large model call and not one universal simulator.
It is the result of selecting the correct authority and topology before any
event is minted.

Charter remains the strongest backend for a person who stays inside a location
or bounded institution long enough for its routines, shortages, judgments,
obligations, and hierarchy to organize their life. That strength is precisely
why it should not be stretched over characters whose lives have a different
shape.
