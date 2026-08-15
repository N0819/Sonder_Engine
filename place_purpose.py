# place_purpose.py
"""What a place is FOR: purpose a character can know about rooms.

Built to docs/design/DESIGN_PLACE_PURPOSE.md, on top of machinery the doc predates:
the durable place graph (`chat_chars.state.place_graph`, written only by
`commit.record_spatial_experience` from the character's own standing and
sight), routing over walked doorways (`_destination_from_goals`/`en_route`),
and `survival.py`'s felt vitals. The doc's two problems stay two problems:

* **What the room I am standing in affords is perception** — derived live
  from co-present entities and room anchors (`here_affords`), a structured
  echo of what the view prose already shows, gated on the same full-sight
  light rule `_onward_exits` uses. Nothing is remembered, nothing persists.
* **What a place I am NOT in affords is memory** — an `affords` ledger on
  the character's own place-graph node: `{"food": {"basis": "witnessed",
  "last": 71}}`. Written at commit, read back at need.

Three bases, and where each comes from:

* `witnessed` — learned by living it. Their OWN vitals rose across two
  consecutive commits settled in the same room (interoception,
  unimpeachable: nourishment only ever rises when something was eaten), or
  their body is verifiably lying on a soft support (`comfort.rest_affording`
  — the seam comfort.py left open on purpose; this module is the deliberate
  path by which a remembered warm bed becomes a destination, and comfort
  itself still never pulls). Never derived from the Director's event row,
  which is entitled; that temptation is named in the design doc as a
  firewall breach to reject in review.
* `told` — hearsay. A stated-fact place claim already re-keyed onto the
  place by `theory_of_mind.rekey_place_claims` and merged into mind_models
  is mirrored onto the node with its live credence as `sureness` — and the
  mirror is a READ-MODEL of the belief, so every commit touch re-asks
  `belief_credence` and an entry whose belief has been explained away is
  dropped rather than left steering (the doc's mandatory drift rule).
* `assumed` — cultural prior, and it is NEVER STORED. This is the one
  deliberate departure from the doc's letter (its JSON example shows an
  assumed entry on the node) in service of its spirit: assumed affordances
  are derived at read time from the node's NAME alone, so the doc's breach
  condition — "the lexicon consulted for a name the character has not
  perceived" — is structurally impossible, because a place-graph node name
  exists only if the character walked the room, saw into it, or (future
  basis) was told of it. Deriving also needs no displacement machinery: a
  stored witnessed/told entry shadows the assumption by construction, and a
  lexicon fix reaches every character retroactively instead of leaving
  stale priors persisted.

Where the type-inference line is drawn, explicitly (the sharp edge):

1. Trigger tokens come only from the character's own place-graph node
   names. Never scene rooms, never prose descriptions — names are short
   noun phrases where identifier recognition is honest; descriptions are
   where it lies.
2. The lexicon maps token -> PURPOSE keys only, never structure. "You
   would expect food there" tells a character what an inn is for; it does
   not tell them the layout, the contents, or that this inn in fact has
   any — which is exactly the difference between worldly competence and
   oracle knowledge. No code path resolves an assumed affordance into a
   scene fact.
3. Membership needs genericity: a mapping belongs only if it would hold in
   any generic setting with no knowledge of the story. Story culture ("in
   this city, bathhouses are where deals are made") is lore, which already
   has a gated delivery path; this lexicon must never grow into a parallel
   lore system. Kept under ~30 tokens, exact tokens only — comfort.py left
   "fire" out because identifier recognition cannot tell a hearth from a
   burning building, and that rule holds here too.
4. It renders as an expectation (`basis: "assumed"`), never as knowledge,
   and the prompt says so in words.

From feeling to destination: `felt_needs` reads the character's own
`body_state` at the 0.4 tier ("very hungry" / "tiring badly" — the felt
labels in survival.py; the 0.7 tier fires for most of an ordinary day and
would make the recall a nag), and `place_options` ranks that character's
own matching nodes by basis strength then by rooms over WALKED doorways —
the same taken-edge firewall en_route routes on, so a place they cannot
remember a way to is not offered as one. The engine guarantees only that
the mind REMEMBERS THE OPTION (at most two, absorption-capped, suppressed
entirely when the room they are standing in already affords the need);
whether hunger becomes an intention and the intention movement stays the
character's, same as the URGENT SITUATIONAL FACTS rule: the option must
exist, the refusal may be theirs.

Not built, plainly, and why: witnessed drink/water/warmth (no thirst or
cold vital exists, so there is no deterministic signal and no felt need to
recall them at — only `assumed`/`told` can carry them); the own-memory-row
verb heuristic (doc: it can wait); minting `told`-basis NODES from hearsay
about never-seen places (a node needs a rid, hearsay carries none, and
nothing can route to a room with no rid anyway — the belief still lives in
mind_models); negative entries ("the tavern has no food" — no
deterministic negative signal exists yet).

Persistence: everything here rides `chat_chars.state` (`place_graph` node
`affords` + the two-float `last_vitals` snapshot), the place-graph
precedent — checkpoints, chat_archive and branching carry the blob
verbatim, so no schema, remap, or archive change is needed
(docs/guides/DATABASE.md decision recorded at `record_spatial_experience`).
"""

from __future__ import annotations

import re
from collections import deque

from comfort import _is_body as _body_guard
from comfort import rest_affording
from spatial import effective_light, hiding_holders_of, room_of
from survival import vitals_of
from theory_of_mind import belief_credence

# The closed set of purposes. Each either has a felt-need consumer (food,
# rest), a live perception echo, or a hearsay/assumption carrier; "repair"
# and "social" from the design sketch are deliberately absent because
# nothing consumes them yet and an affordance with no consumer is dead
# weight waiting to become a to-do list (design doc, risk 4).
AFFORDANCES = ("food", "drink", "water", "rest", "warmth", "shelter")

# Vital -> the affordance that answers it, at the tier where the need
# presses ("very hungry", "tiring badly" -- survival._LABELS).
RECALL_AT = 0.4
_NEED_OF_VITAL = (("nourishment", "food"), ("stamina", "rest"))

# A vitals rise smaller than this is rounding, not a meal.
_RISE_EPSILON = 0.005

# Basis strength, for ranking and for what may overwrite what.
_BASIS_RANK = {"witnessed": 0, "told": 1, "assumed": 2}

# --- the lexicons ----------------------------------------------------------
#
# Exact tokens, never prefixes. One lexicon per corpus: place NAMES
# (assumed), structural scene tokens (here_affords), claim text (told
# mirror). Small on purpose, and they must stay so.

_NAME_LEXICON = {
    "tavern": ("food", "drink", "shelter"), "taverns": ("food", "drink", "shelter"),
    "inn": ("food", "drink", "rest", "shelter"), "inns": ("food", "drink", "rest", "shelter"),
    "alehouse": ("drink", "shelter"), "alehouses": ("drink", "shelter"),
    "pub": ("food", "drink"), "pubs": ("food", "drink"),
    "taproom": ("drink",), "taprooms": ("drink",),
    "kitchen": ("food",), "kitchens": ("food",),
    "pantry": ("food",), "pantries": ("food",),
    "larder": ("food",), "larders": ("food",),
    "bedroom": ("rest",), "bedrooms": ("rest",),
    "bedchamber": ("rest",), "bedchambers": ("rest",),
    "dormitory": ("rest",), "dormitories": ("rest",),
    "well": ("water",), "wells": ("water",),
    "fountain": ("water",), "fountains": ("water",),
    "cistern": ("water",), "cisterns": ("water",),
    "hearth": ("warmth",), "hearths": ("warmth",),
    "stable": ("shelter",), "stables": ("shelter",),
    "barn": ("shelter",), "barns": ("shelter",),
}

# Structural tokens for the live echo: entity/anchor ids, kinds, names and
# descriptions. Soft-support and warmth sets are in parity with comfort.py's
# vocabulary (kept separate because comfort's are private and its module
# must stay free to evolve them for pleasure math without moving perception).
_HERE_LEXICON = {
    "rest": frozenset({
        "bed", "beds", "bedroll", "bedrolls", "bunk", "bunks", "cot",
        "cots", "couch", "couches", "sofa", "sofas", "divan", "divans",
        "hammock", "hammocks", "mattress", "mattresses",
    }),
    "warmth": frozenset({
        "hearth", "hearths", "fireplace", "fireplaces", "brazier",
        "braziers", "campfire", "campfires", "stove", "stoves",
    }),
    "food": frozenset({
        "food", "bread", "stew", "meal", "meals", "cheese", "meat",
        "fruit", "rations", "provisions",
    }),
    "drink": frozenset({
        "ale", "beer", "wine", "mead", "keg", "kegs", "cask", "casks",
    }),
    "water": frozenset({
        "well", "wells", "fountain", "fountains", "pump", "pumps",
        "cistern", "cisterns", "trough", "troughs",
    }),
}

# Claim-text tokens for the told mirror: the nouns hearsay actually uses.
_CLAIM_LEXICON = {
    "food": frozenset({
        "food", "meal", "meals", "stew", "bread", "supper", "dinner",
        "breakfast", "fare", "eat", "eats",
    }),
    "drink": frozenset({"ale", "beer", "wine", "mead", "drink", "drinks"}),
    "rest": frozenset({"bed", "beds", "lodging", "lodgings", "sleep"}),
    "water": frozenset({"water", "well", "fountain"}),
    "warmth": frozenset({"hearth", "fireplace", "warmth"}),
    "shelter": frozenset({"shelter", "roof"}),
}


def _tokens(*texts):
    out = []
    for text in texts:
        out.extend(t for t in re.split(r"[^a-z0-9]+",
                                       str(text or "").casefold()) if t)
    return out


def assumed_affords(node_name):
    """{affordance: {"basis": "assumed", "note": ...}} from a place-graph
    node NAME the character owns. Pure; derived, never stored. The caller's
    obligation -- and the firewall -- is that `node_name` comes off the
    character's own graph, where a name exists only because they walked the
    room, saw into it, or were told of it."""
    out = {}
    for token in _tokens(node_name):
        for aff in _NAME_LEXICON.get(token, ()):
            out.setdefault(aff, {"basis": "assumed",
                                 "note": f"the name says '{token}'"})
    return out


def here_affords(scene, name):
    """What the room `name` stands in affords, live: ["rest (the bed)",
    "warmth (the hearth)"]. Perception, not memory -- a structured echo of
    what the view prose already shows, from room anchors and co-present
    entities only. Gated on full sight (the `_onward_exits` light rule): a
    dark room's bed is not visible and therefore not echoed. Bodies are
    never furniture (comfort's rule), and a concealed entity is not seen.
    The room's NAME deliberately contributes nothing here: expecting food
    of a tavern is memory's business (`assumed`), not perception's."""
    scene = scene if isinstance(scene, dict) else {}
    rid = room_of(scene, str(name or "").strip())
    if not rid:
        return []
    light = {"lit": "full", "dim": "partial", "dark": "none"}
    if light.get(effective_light(scene, rid), "full") != "full":
        return []
    found = {}

    def consider(tokens, display):
        for aff, vocab in _HERE_LEXICON.items():
            if aff not in found and any(t in vocab for t in tokens):
                found[aff] = str(display or "").strip()

    room = (scene.get("rooms") or {}).get(rid) or {}
    anchors = room.get("anchors") if isinstance(room, dict) else {}
    for aid, anchor in (anchors or {}).items():
        desc = str((anchor if isinstance(anchor, dict) else {}).get("desc")
                   or "").strip()
        consider(_tokens(aid, desc),
                 desc or str(aid).replace("_", " "))
    for eid, ent in (scene.get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        label = str(ent.get("name") or eid)
        if room_of(scene, label) != rid and room_of(scene, str(eid)) != rid:
            continue
        if _body_guard(scene, eid, ent, label):
            continue
        if hiding_holders_of(scene, label) or hiding_holders_of(scene, str(eid)):
            continue
        consider(_tokens(eid, ent.get("kind"), ent.get("name"),
                         ent.get("description")), label)
    return [f"{aff} (the {found[aff]})" if not found[aff].casefold().startswith(("the ", "a ", "an "))
            else f"{aff} ({found[aff]})"
            for aff in AFFORDANCES if aff in found]


def _node_affords(node):
    affords = (node or {}).get("affords")
    return affords if isinstance(affords, dict) else {}


def witness_affords(state, scene, name, turn_idx):
    """Commit-side witnessed-basis writer. Mutates `state`; returns the
    (rid, affordance) pairs written, for tests and warnings.

    Two signals, both the character's own and only their own:

    * vitals rise -- `nourishment`/`stamina` higher than at the previous
      commit, both commits settled in the SAME room, consecutive turns.
      Consecutive on purpose: across a gap the rise happened somewhere,
      and crediting the room they happen to be standing in now would
      witness the wrong place. Nourishment never rises by tick, so any
      rise is something eaten; requires survival on (no vitals, no
      signal).
    * `comfort.rest_affording` -- the body verifiably lying on a soft
      support here, the seam comfort.py documented for exactly this
      writer. Works with survival off, which matters: rest is the one
      affordance whose evidence is postural rather than metabolic.

    Never reads the event row, another body's vitals, or any room but the
    one the character is settled in (whose node `record_spatial_experience`
    has already minted this commit)."""
    if not isinstance(state, dict):
        return []
    graph = state.get("place_graph")
    nodes = (graph or {}).get("nodes") if isinstance(graph, dict) else None
    label = str(name or "").strip()
    here = room_of(scene, label) if label else None
    vit = vitals_of(scene, label)
    written = []

    def _write(aff):
        node = nodes.get(here)
        if not isinstance(node, dict):
            return
        affords = node.setdefault("affords", {})
        if not isinstance(affords, dict):
            affords = node["affords"] = {}
        affords[aff] = {"basis": "witnessed", "last": int(turn_idx)}
        written.append((here, aff))

    if here and isinstance(nodes, dict):
        last = state.get("last_vitals")
        if vit and isinstance(last, dict) \
                and str(last.get("room") or "") == str(here):
            try:
                consecutive = int(last.get("turn")) == int(turn_idx) - 1
            except (TypeError, ValueError):
                consecutive = False
            if consecutive:
                for vital, aff in _NEED_OF_VITAL:
                    try:
                        rise = float(vit.get(vital)) - float(last.get(vital))
                    except (TypeError, ValueError):
                        continue
                    if rise > _RISE_EPSILON:
                        _write(aff)
        if rest_affording(scene, label):
            _write("rest")

    if vit and here:
        state["last_vitals"] = {
            "room": str(here), "turn": int(turn_idx),
            "nourishment": vit.get("nourishment"),
            "stamina": vit.get("stamina"),
        }
    elif not vit:
        state.pop("last_vitals", None)
    return written


def _claim_affords(claim):
    tokens = set(_tokens(claim))
    return [aff for aff in AFFORDANCES
            if tokens & _CLAIM_LEXICON.get(aff, frozenset())]


def mirror_told_affords(state, turn_idx, elapsed_seconds=None):
    """Mirror stated-fact place beliefs onto the character's own nodes as
    `told` entries, and keep every existing `told` entry honest. Mutates
    `state`; returns (rid, affordance) pairs written or refreshed.

    The node entry is a denormalised READ-MODEL of a mind-model belief
    (design doc, risk 3): so on every commit touch, each told entry's
    `sureness` is re-asked from `belief_credence`, and an entry whose
    belief no longer survives is DROPPED -- a stale node entry steering
    navigation toward a place the character no longer believes in is the
    exact drift this rule exists to prevent. `witnessed` is never
    overwritten by hearsay: living it outranks hearing it.

    Only nodes the character already owns can carry hearsay: a place known
    by name alone has no rid, no node, and no walkable route, so its
    belief stays (retrievably) in mind_models until they stand somewhere
    that gives the name ground. Claims arrive already re-keyed onto place
    names by `rekey_place_claims`."""
    if not isinstance(state, dict):
        return []
    graph = state.get("place_graph")
    nodes = (graph or {}).get("nodes") if isinstance(graph, dict) else None
    if not isinstance(nodes, dict):
        return []
    touched = []

    by_name = {}
    for rid, node in nodes.items():
        if isinstance(node, dict) and str(node.get("name") or "").strip():
            by_name.setdefault(
                str(node["name"]).strip().casefold(), str(rid))

    # Refresh (and prune) what is already mirrored.
    for rid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        affords = _node_affords(node)
        for aff in list(affords):
            entry = affords[aff]
            if not isinstance(entry, dict) \
                    or entry.get("basis") != "told":
                continue
            cred = belief_credence(state, entry.get("about"),
                                   entry.get("claim"), turn_idx,
                                   elapsed_seconds)
            if cred is None:
                affords.pop(aff)
            else:
                entry["sureness"] = round(float(cred), 3)
                touched.append((str(rid), aff))

    models = state.get("mind_models")
    for about, model in (models or {}).items() if isinstance(
            models, dict) else []:
        rid = by_name.get(str(about or "").strip().casefold())
        if not rid or not isinstance(model, dict):
            continue
        node = nodes.get(rid)
        if not isinstance(node, dict):
            continue
        for hyp in model.get("hypotheses") or []:
            if not isinstance(hyp, dict) \
                    or str(hyp.get("kind") or "") != "stated_fact":
                continue
            claim = str(hyp.get("claim") or "")
            affs = _claim_affords(claim)
            if not affs:
                continue
            cred = belief_credence(state, about, claim, turn_idx,
                                   elapsed_seconds)
            if cred is None:
                continue
            affords = node.setdefault("affords", {})
            if not isinstance(affords, dict):
                affords = node["affords"] = {}
            for aff in affs:
                existing = affords.get(aff)
                if isinstance(existing, dict) \
                        and existing.get("basis") == "witnessed":
                    continue
                if isinstance(existing, dict) \
                        and existing.get("basis") == "told" \
                        and float(existing.get("sureness") or 0.0) \
                        >= round(float(cred), 3):
                    continue
                affords[aff] = {
                    "basis": "told", "sureness": round(float(cred), 3),
                    "about": str(about), "claim": claim[:160],
                }
                touched.append((str(rid), aff))
    return touched


def felt_needs(body_state):
    """The affordances this body's own state is asking for, worst first.
    [] when nothing presses -- and absence is the common case, so a fed and
    rested character pays nothing for this feature existing."""
    if not isinstance(body_state, dict) or not body_state:
        return []
    pressing = []
    for vital, aff in _NEED_OF_VITAL:
        try:
            value = float(body_state.get(vital))
        except (TypeError, ValueError):
            continue
        if value <= RECALL_AT:
            pressing.append((value, aff))
    return [aff for _v, aff in sorted(pressing)]


def _walked_hops(adjacency, start, goal):
    """Rooms from start to goal over the walked adjacency the caller
    supplies. Parity with agents.character._hops_to -- the caller passes
    the same taken-edge adjacency en_route routes over, so recall and
    routing can never disagree about whether a way is remembered."""
    start, goal = str(start), str(goal)
    if start == goal:
        return 0
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        cur, depth = queue.popleft()
        for nxt in adjacency.get(cur, ()):
            if nxt in seen:
                continue
            if nxt == goal:
                return depth + 1
            seen.add(nxt)
            queue.append((nxt, depth + 1))
    return None


def place_options(graph, here_rid, need, walked_adjacency):
    """This character's own remembered places answering `need`, best first.

    Candidates are their own place-graph nodes carrying a stored
    (witnessed/told) entry or a name-derived assumption for the need,
    excluding where they stand, and only where a route survives over their
    own WALKED doorways -- the en_route firewall: a place with no
    remembered way to it is a memory, not an option, and offering it would
    route through ground their feet never earned. Ranked by basis strength
    (lived beats heard beats guessed), then by distance. Returns
    [{rid, name, basis, hops, sureness?, note?}]; the caller caps, formats
    and decides nothing on the character's behalf."""
    nodes = (graph or {}).get("nodes")
    if not isinstance(nodes, dict) or not here_rid:
        return []
    here = str(here_rid)
    out = []
    for rid, node in nodes.items():
        rid = str(rid)
        if rid == here or not isinstance(node, dict):
            continue
        name = str(node.get("name") or "").strip()
        if not name:
            continue
        entry = _node_affords(node).get(need)
        if not isinstance(entry, dict):
            entry = assumed_affords(name).get(need)
        if not isinstance(entry, dict):
            continue
        hops = _walked_hops(walked_adjacency or {}, here, rid)
        if hops is None or hops < 1:
            continue
        option = {"rid": rid, "name": name,
                  "basis": str(entry.get("basis") or "assumed"),
                  "hops": hops}
        if entry.get("sureness") is not None:
            option["sureness"] = entry.get("sureness")
        if entry.get("note"):
            option["note"] = entry.get("note")
        out.append(option)
    out.sort(key=lambda o: (_BASIS_RANK.get(o["basis"], 3), o["hops"],
                            o["name"]))
    return out


def affords_here(graph, here_rid):
    """Does the character's CURRENT node answer `need`s at all -- the
    stored ledger plus the name-derived assumption for where they stand.
    Used to suppress recall entirely when the answer is the room they are
    in: remembering another tavern while standing in one is noise."""
    node = ((graph or {}).get("nodes") or {}).get(str(here_rid or ""))
    if not isinstance(node, dict):
        return set()
    have = {aff for aff, e in _node_affords(node).items()
            if isinstance(e, dict)}
    have |= set(assumed_affords(str(node.get("name") or "")))
    return have
