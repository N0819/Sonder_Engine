"""The Director's channel ownership, and the scene facts its routing reads.

`SPECIALISTS` is the channel-ownership table: which owner (a "hand") answers
for which `state_diff` channels. The five hands were model calls under the
causal Director; since 2026-09-27 (the causal contract deleted) they are
owners only -- the ONE encoder writes every channel
(`agents/director_prose.py`), and its answer is split by this table so each
owner's binding, validation and fold judge it (`director._run_specialists`).

INVARIANT -- sole writer: this module is the only writer of `SPECIALISTS`
and `_CHANNEL_SPECIALISTS` (`_rebuild_channel_owners` keeps the derived
registries level with the table).

Also here: the per-stage scene facts the decision model's channel choice
reads (`_gate_facts`), and the note-key readers `director_fanout.span_owners`
uses to say which owner a span is for.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

from collections.abc import Mapping

from core.db import q
from world.survival import survival_enabled

from .director_lingua import _ling
from .director_views import (
    _artifacts_view,
    _carried_reports_view,
    _couriers_view,
    _crowds_view,
    _unratified_background_claims,
)


#: The channel owners, one authority for channel ownership on the runtime
#: side; schemas.SPECIALIST_CHANNELS holds the same map by step key, and the
#: pack's `specialists.<hand>.order` the order their chunks join the encoder's
#: sheet. Dict order is the CANONICAL assembly order: owners' shares merge in
#: this order, so a rerun with the same inputs produces the same merged diff.
SPECIALISTS = {
    "body": {
        "step_key": "director_body",
        "channels": ("attire", "conditions", "vitals", "overlays"),
    },
    "social": {
        "step_key": "director_social",
        # ...and, since 2026-09-04, the world's traffic: crowds, couriers,
        # tellings and the hearsay verdict, which the retired offscreen hand
        # carried. A crowd is a charter projection already and a courier is
        # a body walking a route with news, so both are charter's to SIMULATE;
        # the OPS that raise, send, tell and adjudicate are speech and roster
        # work, and this is the hand that owns speech consequences.
        "channels": ("cast_changes", "introductions",
                     "public_evidence", "crowd_ops", "courier_ops",
                     "telling_ops", "ratified_claims", "contradicted_claims",
                     "charter_ops", "claim_dispositions", "consequences", "obligations"),
        # This channel is step metadata rather than StateDiff, so its list
        # shape cannot be derived from StateDiff's annotations below.
        "list_channels": ("public_evidence", "obligations"),
    },
    "contact": {
        "step_key": "director_contact",
        "channels": ("contact_ops", "contact_action_ops", "substance_ops",
                     "containment", "scales"),
    },
    "objects": {
        "step_key": "director_objects",
        "channels": ("entities", "remove_entities", "inventory_ops",
                     "artifact_ops", "destruction", "sensory_events"),
    },
    # The geography. Carved LAST by design: the movement backstop, the
    # following projection, approach semantics and the near-group
    # reconciliation all judge the MERGED diff and stay with the
    # orchestrator -- this specialist proposes relocations and never has
    # the last word on them.
    "spatial": {
        "step_key": "director_spatial",
        # No `time`: a hand receives the rows selected for it, never the
        # beat, so the sum its sheet asked for ("a beat that holds several
        # things in sequence spans all of them") was over terms it could not
        # see. Measured 2026-09-20: in scope on 38 of 60 playerless beats and
        # 50 of 118 live beats since 2026-09-15, written on 0 of either, and
        # the author routed the category 0 times in 3,000 resolve variants,
        # so no time work item ever reached it. The beat's span is now
        # engine arithmetic over the author's per-row `seconds`
        # (`world.mechanics.beat_time_from_spans`).
        "channels": ("positions", "rooms", "remove_rooms",
                     "remove_adjacent", "stations", "poses", "comms_ops",
                     "following_ops", "location", "weather"),
    },
}

#: A hand that no longer exists, and the hand that owns its channels now. A
#: ruling keyed by a retired name is a ruling the Director made and the engine
#: can say for whom -- routing it is bookkeeping, refusing it un-dispatches a
#: correct ruling. The `offscreen` hand was retired 2026-09-04 (its traffic
#: channels are `social`'s), and until 2026-09-07 both stage sheets still
#: taught its name, so every crowd/courier/telling ruling keyed as instructed
#: was reported unrouted and no hand ran. Stored presets and model habit
#: outlive a sheet edit; this map is what makes the retirement safe.
RETIRED_HANDS = {"offscreen": "social"}

#: Channels an ACT OF SPEECH can write. Saying a thing is not a physical
#: action, so for most channels a line of dialogue is material a hand cannot
#: act on and can only restate; for these it is the act itself. An
#: assertion spoken aloud is a claim, never an objective fact.
SPEECH_WRITTEN_CHANNELS = frozenset((
    "obligations",           # explicit requests, promises, answers and refusals
    "introductions",         # a name is given by being said
    "comms_ops",             # a line carried by a device IS the op
    "telling_ops",           # who told whom what
    "ratified_claims",       # a claim is made in speech
    "contradicted_claims",   # and disputed in speech
))


def reads_dialogue(name):
    """Does this specialist own a channel a speech act can write.

    The beat's dialogue used to ride in the COMMON payload, so every hand got
    it whether or not any channel they own could be written by somebody
    talking. Three of the five cannot: `body`, `contact` and `objects` own
    physical ledgers, and for them a transcript is text they can only echo.
    That matters because echoing the payload into the diff is this fan-out's
    measured failure mode, not a hypothetical one -- chat 78 t7's `coverage`
    block is the wardrobe it was shown, transposed -- and because the body
    sheet is already ~6,700 tokens of instruction whose correct answer on an
    ordinary beat is `{}`.

    DERIVED FROM THE CHANNEL TABLE rather than listed per specialist, so a
    channel that moves between hands takes its answer with it and this cannot
    drift out of agreement with `SPECIALISTS`.
    """
    return bool(set(SPECIALISTS[name]["channels"]) & SPEECH_WRITTEN_CHANNELS)

#: Every channel any specialist owns, in canonical assembly order. MUTATED
#: in place by `_rebuild_channel_owners`, never rebound: `director.py` and
#: `director_fanout.py` bind the name at import, so a rebind would leave both
#: readers holding the import-time list forever.
_DELEGATED_CHANNELS = []

#: `changes_asserted` category -> the delegated channel that answers for it.
#: Categories with no delegated channel (time, transit, other, ...) stay
#: the prose author's own and are not the scope backstop's business.
#:
#: KEYED ON THE NORMALIZED CATEGORY NAMES (_normalize_omission_category's
#: output: 'contacts', 'substances', 'poses', ...): every reader of this map
#: looks up items that already went through _manifest_items, which
#: normalizes. The original raw spellings ('contact', 'substance', 'pose')
#: are kept as tolerance for a caller that never normalized, but for two
#: releases they were the ONLY keys -- so a manifest entry asserting a
#: contact, substance or pose change could never reach the scope backstop
#: or be sliced into its specialist's payload, silently.
_CATEGORY_CHANNELS = {
    "attire": "attire",
    "conditions": "conditions",
    "cast_changes": "cast_changes",
    "contact": "contact_ops",
    "contacts": "contact_ops",
    "contact_action": "contact_action_ops",
    "contact_actions": "contact_action_ops",
    "substance": "substance_ops",
    "substances": "substance_ops",
    "inventory": "inventory_ops",
    "entities": "entities",
    "positions": "positions",
    "rooms": "rooms",
    # An adjacency change is either a rooms-edge edit or a severance; the
    # rooms gate and the remove_adjacent gate are the same fact, so either
    # served scope answers for the category.
    "adjacency": "rooms",
    "pose": "poses",
    "poses": "poses",
    "stations": "stations",
    # Equipment that carries a voice, not the doorway it carries it past. A
    # beat that keys a mic, kills an intercom or hands someone a radio is
    # categorized here, so it reaches the specialist that owns the channel
    # rather than being detected as an omission every beat and repaired by a
    # mind that never saw it.
    "comms": "comms_ops",
    "comms_ops": "comms_ops",
    # The remaining delegated families. A category that reaches no channel
    # is a change nobody is handed and nobody can encode, so it is detected
    # as an omission every beat and buys a repair from a mind that never
    # saw it -- measured live at 49.2s for two such events in one beat.
    "vitals": "vitals",
    "containment": "containment",
    "scales": "scales",
    "destruction": "destruction",
    "artifacts": "artifact_ops",
    "introductions": "introductions",
    "obligations": "obligations",
}

#: The delegated channels whose value is a LIST rather than a keyed table.
#: `_normalized_channel_value` coerces everything else to dict-or-`{}`, so a
#: channel missing from here loses its whole value at assembly.
#:
#: DERIVED, not enumerated. For the engine's own channels the shape is already
#: declared once, in `schemas.StateDiff` -- and a hand-copy of it was free to
#: disagree with the model that actually parses the output. An extension's
#: channel is in no schema, so it declares its own shape at registration
#: (`register_specialist(list_channels=...)`) and defaults to a keyed table.
#: Mutated in place for the same reason as `_DELEGATED_CHANNELS`.
_LIST_DELEGATED = set()


def _schema_list_channels():
    """`StateDiff` fields typed as a list. The engine's half of the shape.

    Reads the annotation rather than the default factory: the factory is what
    an omission produces, the annotation is what the field IS.

    Through `llm.schemas`'s own Pydantic-major compatibility layer, and NOT by
    reading a field attribute directly. The first version of this function read
    `field.outer_type_`, which exists only on Pydantic 1 -- so on a Pydantic 2
    install `_LIST_DELEGATED` was the EMPTY SET, `_normalized_channel_value`
    coerced all seventeen op-list channels to `{}`, and every `contact_ops`,
    `introductions`, `crowd_ops` and `remove_rooms` a specialist wrote was
    dispatched, paid for and discarded in silence. It replaced a hand-written
    frozenset that had been correct under both majors, and the suite did not
    catch it because the suite runs on Pydantic 1 while the venv the engine
    serves from runs Pydantic 2 -- a green gate saying nothing about the
    installed engine. Reported by the Directive team against `reorganization`;
    `_fields`/`_declared` is the seam that already answers this for every other
    caller, and a second version check here is how the two drift again.
    """
    from llm.schemas import StateDiff, list_shaped_fields

    return list_shaped_fields(StateDiff)

#: Channels that exist at ONE Director stage and not the other. Distinct from
#: a channel the decision model did not grant, and the distinction decides
#: what happens to content: an ungranted emission is under-grant evidence and
#: is KEPT (fail-open); this table says "this STAGE has nowhere to put it at
#: all", so an emission is dropped. Anything absent here serves both
#: stages.
#:
#: Measured, chat 98 turns 6, 26 and 30: the social specialist emitted
#: `public_evidence` at `director_interpret` on three of forty turns and the
#: notice said "Content was kept (fail-open); the scope gate under-granted and
#: should be widened if this recurs" every time. Both halves were false. It was
#: not kept -- at interpret a specialist's channels merge into
#: `state_assertions`, which is a `StateDiff`, and `public_evidence` is not a
#: StateDiff field, so `validated_player_state_assertions` dropped it a few
#: lines later and all three recorded steps carry `state_assertions: {}`. And
#: widening was the wrong remedy: evidence describes a FINISHED beat, so
#: granting the channel at a stage that has not adjudicated the attempt yet
#: would turn an intention into a witnessed outcome, which is the very thing
#: the gate's `resolved_stage` term exists to refuse. The guard SUBTRACTS and
#: says so instead -- a fail-open that quietly discards is the one shape of
#: guard that reports the opposite of what it did.
CHANNEL_STAGES = {
    "public_evidence": ("resolve",),
}


def channel_serves_stage(channel, stage):
    """Can this stage carry this channel at all, before any beat gate?"""
    return str(stage) in CHANNEL_STAGES.get(str(channel),
                                            ("interpret", "resolve"))



#: channel -> the specialist that owns it. The reconciliation repair router
#: reads this: an omission in a delegated channel is that channel's OWNER's to
#: repair, at specialist cost, never the prose author's at full-core cost.
#: Recomputed rather than frozen at import -- it WAS a module-level
#: comprehension over `SPECIALISTS`, which meant a family registered afterwards
#: was invisible to `_route_repair_omissions` while being perfectly visible to
#: dispatch: a split that routes a repair to nobody.
_CHANNEL_SPECIALISTS = {}

def _rebuild_channel_owners():
    """The three channel registries, rebuilt together from `SPECIALISTS`.

    Together, because they are three views of one fact and were not always
    derived from it: an owner map, the ordered roll the scope backstop walks,
    and the shape table assembly coerces against. Each one that stayed frozen
    at import was a way for a family registered afterwards to be dispatched and
    then dropped -- routed to nobody, reported by nobody, or emptied at merge.
    """
    schema_shapes = _schema_list_channels()
    _CHANNEL_SPECIALISTS.clear()
    _DELEGATED_CHANNELS[:] = []
    _LIST_DELEGATED.clear()
    for name, spec in SPECIALISTS.items():
        for channel in spec["channels"]:
            _CHANNEL_SPECIALISTS[channel] = name
            _DELEGATED_CHANNELS.append(channel)
        # Most engine channels derive their shape from StateDiff.  A small
        # number of orchestrated metadata channels live on the stage output
        # itself and declare their shape beside their owner, just as an
        # extension channel must.
        _LIST_DELEGATED.update(spec.get("list_channels") or ())
        if not spec.get("ext_id"):
            _LIST_DELEGATED.update(
                ch for ch in spec["channels"] if ch in schema_shapes)


#: The engine's own five, populated the same way an extension's sixth will be.
_rebuild_channel_owners()


#: The gate facts, in the order the record carries them.
_GATE_FACT_ORDER = (
    "physical_beat",
    "speech_present",
    "resolved_stage",
    "anyone_wears",
    "active_conditions",
    "overlays_present",
    "vitals_tracked",
    "contacts_standing",
    "containment_active",
    "scales_active",
    "material_effects_declared",
    "notices_in_scene",
    "reports_carried",
    "destructible_entity",
    "crowds_present",
    "couriers_present",
    "unratified_claims_present",
)


class _GateFacts(Mapping):
    """The stage's gate facts, with the world-view-derived five built on read.

    A Mapping rather than a dict for one property: a fact whose source is a
    world VIEW -- crowds, couriers, posted notices, carried reports,
    unratified hearsay -- is built when a gate asks for it and never
    otherwise. Every other fact is standing scene state or one indexed row,
    and stays eager because it costs nothing.

    C8 (review 2026-09-07): on an interpret beat whose ruling reaches no hand
    nothing asks. The gates decide how much sheet an ADDRESSED hand loads, so
    with no hand addressed they decide nothing, and no specialist payload is
    assembled either. Measured on a copy of chat 114 at turn 13, the five
    builds cost 48 ms of a 205 ms deterministic interpret. Where the caller
    already HOLDS the rows -- the resolve stage hands its payload's in --
    nothing here is lazy and this behaves exactly as the dict it replaced.

    `consulted()` is the record's copy: the facts actually read, in the
    canonical order, as a plain JSON-serialisable dict.
    """

    def __init__(self, eager, lazy):
        self._eager = dict(eager)
        self._lazy = dict(lazy)
        self._read = {}

    def __getitem__(self, key):
        if key in self._eager:
            return self._eager[key]
        if key in self._read:
            return self._read[key]
        build = self._lazy[key]          # KeyError names the missing fact
        try:
            value = bool(build())
        except Exception:
            # FAIL OPEN, as the eager read did: a fact whose read fails
            # degrades to True and never gates a channel out on an error.
            value = True
        self._read[key] = value
        return value

    def __iter__(self):
        return iter(_GATE_FACT_ORDER)

    def __len__(self):
        return len(_GATE_FACT_ORDER)

    def pending(self):
        """Whether any fact would still cost a build to read."""
        return any(key not in self._read for key in self._lazy)

    def consulted(self):
        """The facts actually read, in canonical order, as a plain dict."""
        return {key: (self._eager[key] if key in self._eager
                      else self._read[key])
                for key in _GATE_FACT_ORDER
                if key in self._eager or key in self._read}


def _gate_facts(ctx, sc, *, physical, speech, material_effects=False,
                resolved_stage=False, crowds_rows=None, notices_rows=None,
                couriers_rows=None, reports_rows=None, unratified_rows=None):
    """The scene facts every channel gate reads, computed once per stage,
    at that stage's own time. Standing scene state (ledgers, settings) plus
    the two structured beat facts the caller supplies; no prose anywhere.
    A fact whose read fails degrades to True -- fail open, never gate a
    channel out on an error.

    ``crowds_rows`` is the stage's already-computed `_crowds_view` result,
    when the caller built one for its payload: deriving charter crowds walks
    the whole registry, and on a 307-body town the gate's private recompute
    was 2 of the turn's 4 `_crowds_view` calls (3.05s total, measured
    2026-08-28, chat 95) -- two reads for one bool. Both director stages now
    hand their payload's rows in, so the gate and the payload cannot disagree
    about which crowds stand in reach. The fallback recompute passes the
    turn's own idx: the gate's old no-idx read froze the presented-bodies
    lapse (§C3), subtracting long-lapsed bodies from the derived crowds and
    so gating the channel OUT on beats where the payload's aged read had
    crowds to offer.

    Each of the five ``*_rows`` arguments takes THE ROWS OR THE THUNK THAT
    BUILDS THEM (`director_views._lazy_view`). A stage that may read none of
    them -- interpret, whose ruling reaches no hand on most beats -- hands in
    thunks, and a view is built only if a gate asks for its fact (C8); rows
    handed in are facts immediately, exactly as before.
    """
    chat_id = ctx.chat["id"]
    entities = sc.get("entities") or {}
    destructible = any(
        isinstance(e, dict) and (
            str(e.get("kind") or "").strip().casefold() in (
                "vehicle", "building", "structure", "ship", "boat")
            or e.get("interior_rooms"))
        for e in entities.values())
    eager = {
        "physical_beat": bool(physical),
        "speech_present": bool(speech),
        "resolved_stage": bool(resolved_stage),
        "anyone_wears": any(
            bool(entry) for entry in (sc.get("attire") or {}).values()),
        "active_conditions": bool(q(
            "SELECT 1 FROM world_conditions WHERE chat_id=? AND active=1 "
            "LIMIT 1", (chat_id,))),
        "overlays_present": any(
            bool(v) for v in (sc.get("overlays") or {}).values()),
        "vitals_tracked": survival_enabled(chat_id),
        "contacts_standing": bool(sc.get("contacts")),
        "containment_active": bool(sc.get("contained")),
        "scales_active": any(
            isinstance(v, (int, float)) and float(v) != 1.0
            for v in (sc.get("scales") or {}).values()),
        "material_effects_declared": bool(material_effects),
        "destructible_entity": destructible,
    }
    lazy = {}

    # THE PAYLOAD'S OWN ROWS, when the stage built them (the `crowds_rows`
    # rule, extended to the other four views this gate recomputed): two
    # reads for one bool, and the gate and the payload could not disagree.
    # A THUNK where the stage may never read them (C8), and the gate's own
    # recompute where a caller has no payload at all.
    def _fact(key, rows, build):
        if rows is not None and not callable(rows):
            eager[key] = bool(rows)
        else:
            lazy[key] = rows if callable(rows) else build

    _fact("notices_in_scene", notices_rows,
          lambda: _artifacts_view(chat_id, sc))
    _fact("reports_carried", reports_rows,
          lambda: _carried_reports_view(ctx))
    _fact("crowds_present", crowds_rows,
          lambda: _crowds_view(chat_id, sc, ctx.turn["idx"]))
    _fact("couriers_present", couriers_rows,
          lambda: _couriers_view(chat_id, sc))
    _fact("unratified_claims_present", unratified_rows,
          lambda: _unratified_background_claims(chat_id, ctx.turn["idx"]))
    return _GateFacts(eager, lazy)


#: Channels whose existence is a property of the STORY, not of the beat: the
#: gate is false because the ledger is switched off, so no beat can ever put
#: work in them. Read twice: by dispatch, so a hand the ruling addresses by
#: name on a still beat is not handed the chunk for a ledger its story does
#: not keep; and by the scope backstop, where an unserved one is never a
#: mispredict.
_STRUCTURAL_CHANNEL_FACTS = {"vitals": "vitals_tracked"}


def _note_key_forms(key):
    """The spellings one ledger name can arrive under.

    Case and a trailing plural only. NOT a synonym table: the channels are a
    closed set the engine owns, so matching their own names loosely is
    schema-shaped, while guessing that "transit" means `positions` would be
    the engine inventing vocabulary on the Director's behalf and getting it
    wrong quietly.
    """
    k = str(key or "").strip().lower()
    forms = {k}
    if k.endswith("ies"):
        forms.add(k[:-3] + "y")
    if k.endswith("s"):
        forms.add(k[:-1])
    else:
        forms.add(k + "s")
        if k.endswith("y"):
            forms.add(k[:-1] + "ies")
    return forms


def note_key_targets(key):
    """Every hand and channel one `ledger_notes` key addresses.

    Returns ``{("hand", name), ("channel", channel), ...}`` -- empty when the
    key reaches nothing. Its one live reader since the causal hands went
    (2026-09-27, with dispatch by ruling and the unrouted report) is
    `manifest_category_targets`. In order:

    * a hand's own name, or a retired hand's (`RETIRED_HANDS`);
    * a channel's name, under the spellings `_note_key_forms` accepts;
    * the manifest CATEGORY vocabulary -- `_CATEGORY_CHANNELS` through the
      pack's own aliases -- which is the vocabulary the same author is asked
      to file `changes_asserted` under. Measured on the channel's first live
      week: 8 of 11 notes were keyed by channel and the two that were not
      (`inventory`, `entity`) were category words the manifest table owns
      and the note lookup did not consult.
    """
    from llm.schemas import CAUSAL_CATEGORY_REDIRECTS

    forms = _note_key_forms(key)
    retired = {("hand", owner)
               for category, owner in CAUSAL_CATEGORY_REDIRECTS.items()
               if forms & _note_key_forms(category)}
    if retired:
        return retired
    targets = set()
    for name in SPECIALISTS:
        if forms & _note_key_forms(name):
            targets.add(("hand", name))
    for retired, owner in RETIRED_HANDS.items():
        if forms & _note_key_forms(retired) and owner in SPECIALISTS:
            targets.add(("hand", owner))
    for name, spec in SPECIALISTS.items():
        for channel in spec["channels"]:
            if forms & _note_key_forms(channel):
                targets.add(("channel", channel))
    if not targets:
        cat = str(key or "").strip().casefold()
        cat = _ling("_OMISSION_CATEGORY_ALIASES").get(cat, cat)
        if cat in CAUSAL_CATEGORY_REDIRECTS:
            return {("hand", CAUSAL_CATEGORY_REDIRECTS[cat])}
        channel = _CATEGORY_CHANNELS.get(cat)
        if channel:
            targets.add(("channel", channel))
    return targets


def manifest_category_targets(category):
    """Every hand and channel one `changes_asserted` category addresses.

    The manifest's vocabulary is the note key's vocabulary, and this is the
    same resolver saying so. It was not, for the field's whole first life:
    dispatch and the payload slice both read `_CATEGORY_CHANNELS` RAW, so a
    category resolved only if it was a category-table key, spelled exactly,
    in the right case -- while a `ledger_notes` key spelled the same way
    resolved through hand names, channel names, plural tolerance and the
    pack's aliases. One field's vocabulary was four times the other's, and
    nothing said so out loud.

    Measured 2026-09-09 over twelve interpret beats on gemini-3.8-flash,
    which is the reason this exists: the author filed a manifest on 8 of 12
    beats and used FOUR distinct category words -- `body`, `objects`,
    `spatial`, `contact`. Three of the four reached no channel, so
    `tools/dispatch_replay.py --filed-only` scored 8 false negatives, 100%
    of productive calls. Not one of them was a bad ruling. Every `change`
    string was accurate and correctly scoped; the entries simply named the
    HAND rather than the ledger.

    The model was doing what the sheet said. `director_interpret.txt` asked
    for "`category`, one of the ledgers named above", and the only names
    above it are the five specialists -- so the sheet taught one closed
    vocabulary and the router accepted a different one. Given a choice
    between teaching a second twenty-four-word vocabulary to every story and
    letting code accept the one the sheet already teaches, this is the
    cheaper half, and it is the half that matches what the engine is for: a
    hand's name is a legitimate answer to "which ledger", just a coarser one.

    Coarser, and that is the whole cost. A category naming a CHANNEL grants
    that channel; a category naming a HAND grants the hand its story's
    channels, by the rule the causal dispatcher (`_dispatch_specialists`,
    deleted 2026-09-27) followed for a note keyed by hand alone -- "a ruling
    that reached it is better evidence than a prediction that nothing there
    could change". Fail-open, as that gate was.

    Widening only: the union, not the fallback, because `note_key_targets`
    stops at the first kind that matched and `contact` matches BOTH -- the
    hand and, through the category table, `contact_ops`. Resolving it as a
    hand alone would have quietly dropped the one channel the manifest used
    to name correctly.
    """
    targets = set(note_key_targets(category))
    cat = str(category or "").strip().casefold()
    cat = _ling("_OMISSION_CATEGORY_ALIASES").get(cat, cat)
    channel = _CATEGORY_CHANNELS.get(cat)
    if channel:
        targets.add(("channel", channel))
    return targets


