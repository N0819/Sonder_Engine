# Shelved: what to take from Directive, in what order

**Status: shelved, nothing decided.** The survey and every licence fact live
in [`../CREDITS.md`](../CREDITS.md) — read that first; this document does not
repeat it. What is here is the part a register cannot hold: an ORDER, a cost,
and a firewall verdict per item, so this can be picked up cold.

Directive is MIT, so implementation is reusable with attribution and not only
ideas. Its central boundary — model proposes, deterministic runtime commits,
narrator continues — is Sonder's `commit.py` boundary reached independently.
Everything below is Directive holding that boundary somewhere Sonder does not.

Nothing here is a defect. Each is a capability Sonder lacks, so none of it
belongs in [`../UNBUILT.md`](../UNBUILT.md) until it is chosen; that register
is for work the engine has committed to, and filing speculation there is how a
roadmap becomes a wish list.

---

## 1. The commit gateway — do this one first

Three separable pieces from `src/runtime/state-delta-gateway.mjs`, ~309 lines.

**Declared domains.** A proposal states which state roots it may mutate; the
gateway diffs before against after and hard-errors on a root nobody declared.
Sonder's `_commit_domain` names domains and never verifies their blast radius.
This is the class of check that catches a domain writing outside itself —
the scene-blob-versus-`world_entities` divergence is exactly that shape.

**Base-revision compare-and-swap** on a monotonic revision, with a conflict
error distinct from a failure, which REFUSES to roll back when in-memory state
has already moved on. `UNBUILT.md` §4.4 Gap 6 asks for this in as many words
and records it verified absent.

**Content-hashed proposal id** in a bounded recent-commit ring, so a replay is
a no-op. Generalises `event_key` from a memory row to the commit itself.

*Cost:* a helper and a field. Not a rearchitecture.
*Firewall:* neutral — it constrains writes, not knowledge.
*Why first:* cheapest, closes a named register entry, and the declared-domain
check pays for itself the first time a commit path grows a second writer.

## 2. Fair Discovery — the one that widens what fiction runs

`docs/architecture/FAIR_DISCOVERY.md`, `src/mission/v1/duty-report-planner.mjs`.

An authored fact that is true but unnarrated stays *discoverable*. It becomes
known only through a delivery route naming **who** may deliver it, **what
capability** makes them credible, **when** delivery is appropriate, and **what
counts** as disclosure — then pending → assigned → visibly delivered →
accepted → materialised, bound to an exact source. Invalidate the source and
the knowledge and everything derived from it rebuild.

Sonder has the transport half, and better: a report is a BODY on a road
(`carriers.py`, `couriers.py`, `artifacts.py`). What it cannot say is *this
fact must reach someone, and here is the legitimate mouth*.

*Answers:* §1.16 residual 5, "the seed asserts a conclusion whose channel does
not exist".
*Firewall:* it SUBTRACTS — this is the channel rule applied to authored canon
instead of to perception, which is the same rule pointed at the other half of
the problem.
*Widens:* mystery, investigation, the briefing, the secret that must land.
*Cost:* real — an authored structure, a deterministic selector, commit-side
materialisation. It decomposes, and the reachability lint (item 4) is worth
having on its own.

## 3. Identity discipline for emergent people

`docs/architecture/PEOPLE_AND_RELATIONSHIPS.md`. Two rules.

**Names are display facts, never identity keys** — a stable id minted at the
encounter, and two records are NEVER guessed to be the same person. That
corroborates the fix §1.17 already prescribes, and indicts what Sonder does
today: `_fold_duplicate_presences` guesses.

**The creation threshold** — a person record exists only from an accepted
direct encounter in which they gave a usable name. A name heard in narration
*about* someone else is insufficient. That is the missing perception filter in
§1.8, where promotion seeds are minted from the objective `resolved_event` and
written `provenance: "witnessed"`.

*Cost:* small for the threshold, moderate for the identity rekey (it is a
migration).
*Firewall:* the threshold IS a firewall rule and is currently missing.

## 4. Authored-content reachability lint

`src/mission/v1/mission-package-linter.mjs`. The static question neither
existing tool asks: `tools/scene_lint.py` finds two live ledgers contradicting
each other, `tools/fire_rates.py` measures whether a mechanism ever fired —
neither asks *can this authored thing ever reach anyone?*

An empty `psychology.drive`, a knowledge tag no cast member holds, and a lore
entry gated out of every range all fail that way, and all fail SILENTLY, which
is the failure mode `CLAUDE.md` singles out as the most expensive in the
engine. Its keyword spoiler list is not worth taking — prose matching, §3.1.

*Cost:* a tool. No runtime change.

## 5. Typed episode boundaries, and 6. the structured-output fingerprint

Lower value, both real. Boundaries: a closed list of hard codes each valid only
from a NAMED engine authority, so a model cannot assert one, beside a soft
model-proposed boundary that must cite criteria — plus an explicit receipt when
a beat is judged ordinary. Answers §2.6 and supplies the contract §2.16 says it
needs. Fingerprint: native JSON-schema mode used only while a fingerprint over
provider/model/mode/policy stays certified, failing before transport rather
than silently downgrading — the same problem `prompt_cache_enabled_for` solves
with a hand-kept allowlist, solved by measurement.

---

## The one that must never be taken

Directive batches ONE model call proposing every person's observations
("Utility is never called per person"). This is the information firewall
inverted. Sonder deleted `_per_observer_model_views` precisely so no shared
call could exist, and per-mind separation is the structural boundary rather
than a policy on top of it.

It is recorded here rather than only in the rejection table because it is the
most TEMPTING thing in that repository: §1.40 wants call multiplicity down,
this reduces it dramatically, and the reasoning that makes it wrong is exactly
the reasoning a future session under time pressure would skip. The full
rejection list is in [`../CREDITS.md`](../CREDITS.md).
