# schemas.py
"""Pydantic schemas for all pipeline and world-state structures."""

import html
import json
import math
import re

from pydantic import BaseModel, Field, ValidationError, validator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NamedTuple, Optional, Union, get_args, get_origin


def _note_drop(message):
    """Say that model output was dropped, on the running step's engine notes.

    This module subtracts in about a dozen places and every one of them was
    silent. Each drop is individually argued and mostly right -- a dropped
    alternative beats a crashed beat -- but the third option was always
    available and only one site ever took it: keep the beat AND say what was
    lost (`_uncross_concealed_speech`, which smuggles its notes back through
    `result["concealment_repairs"]`). As it stood, a list truncated at 64 and
    a well-formed list of 64 were indistinguishable in the stored variant.

    Imported lazily: `llm.schemas` is imported by tools, tests and archive
    readers that have no pipeline and no database, and a diagnostic must
    never be the reason one of them cannot import. Outside a running step the
    sink is unset and this is a no-op, exactly as it is for the repair ladder.
    """
    try:
        from core.pipeline_context import note_step_warning
    except Exception:      # pragma: no cover - diagnostics never fail a call
        return
    note_step_warning(f"llm output pruned: {message}")


def _kept(what, before, after):
    """Return `after`, saying how much of `before` did not survive."""
    try:
        lost = len(before) - len(after)
    except TypeError:
        return after
    if lost > 0:
        _note_drop(
            f"{what}: dropped {lost} of {len(before)} entries the model sent")
    return after


def _coerce_str_list(value):
    """Normalize a value into a list[str], tolerating the shapes smaller /
    cheaper LLMs emit where the schema wants plain strings: a bare string,
    a single object, a list of objects, or nested lists. We preserve the
    text (pulling a sensible field out of objects) instead of hard-rejecting
    the entire step -- a dropped alternative is far cheaper than a crashed
    character turn. See tests/test_tom_normalization.py."""
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        value = [value]

    out = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            picked = next(
                (
                    str(item[key])
                    for key in ("claim", "text", "label", "description", "hypothesis", "value")
                    if item.get(key)
                ),
                None,
            )
            out.append(picked if picked is not None else json.dumps(item, ensure_ascii=False, sort_keys=True))
        elif isinstance(item, (list, tuple)):
            out.append("; ".join(str(part) for part in item))
        else:
            out.append(str(item))
    return out


def _coerce_station_table(value):
    """Normalize a `stations` table into {name: {at?, near?}}, dropping junk.

    Deliberately NOT a typed sub-model, and the reason is a correctness one
    rather than a style one. The merge contract (spatial.merge_scene_with_diff)
    is a PARTIAL update per entity -- a beat touching only `at` must keep the
    standing `near` list, and vice versa. A typed `Station(at=None, near=[])`
    default-fills both halves, so every partial emission would clobber the
    other one. And `_dump` uses exclude_none, which would delete an EXPLICIT
    `{"at": null}` -- the only way to say "stepped away from the fixture".
    `containment: dict[str, Optional[dict]]` already relies on the same
    null-survives-inside-a-dict behaviour for release.

    What the typed model WOULD have bought -- rejecting off-schema shapes
    instead of letting them ride as silently-ignored junk -- is bought here
    instead by canonicalizing them into meaning: a bare string is the anchor,
    a bare list is the `near` roster.
    """
    if not isinstance(value, dict):
        return {}
    out = {}
    for name, station in value.items():
        name = str(name or "").strip()
        if not name:
            continue
        if isinstance(station, str):
            station = {"at": station.strip() or None}
        elif isinstance(station, (list, tuple)):
            station = {"near": list(station)}
        if not isinstance(station, dict):
            continue
        entry = {}
        if "at" in station:
            at = station.get("at")
            entry["at"] = str(at).strip() or None if at is not None else None
        if "near" in station:
            entry["near"] = [n for n in _coerce_str_list(station.get("near"))
                             if str(n).strip()]
        if entry:
            out[name] = entry
    return out


def _coerce_list_valued_map(value):
    """Wrap the single entry where a `dict[str, list]` channel wanted a list.

    `overlays` and `conditions` are name-keyed tables whose values are LISTS
    (a body can carry several marks, several conditions), and a model with
    exactly one to report writes the item directly under the key. Observed
    live (run 20, twice in 14 beats): interpret emitted
    `state_assertions.overlays.village_well: <one value>` and the whole
    otherwise-valid output failed with `value is not a valid list`, costing
    a full temperature-0 repair round-trip (4.9s) for a shape that means
    the same thing as the list of one. Same judgment as the
    mind_model_updates precedent (tests/test_schema_leniency.py): the
    singular and the list of one are unambiguous; wrap, don't reject. An
    explicit null under a key means "nothing here" and becomes the empty
    list; item-level typing (e.g. conditions' entries must be objects) still
    applies after the wrap, so a genuinely off-schema item still fails.
    """
    if isinstance(value, (list, tuple)):
        # The OTHER shape a name-keyed table gets written as: a list of
        # entries that each name their own subject. Observed live at
        # interpret -- `state_assertions.overlays` came back a list, failed
        # with "value is not a valid dict", and cost a 4.2s temperature-0
        # repair for a channel the body specialist then replaced anyway.
        #
        # Keyed only where the entry SAYS whose it is. A list of bare
        # strings is left to fail: nothing here may invent a subject, and
        # attaching an unclaimed mark to the wrong body is worse than
        # rejecting the shape.
        keyed = {}
        for entry in value:
            if not isinstance(entry, dict):
                return value
            subject = next((str(entry[k]).strip() for k in
                            ("subject", "name", "who", "character", "target")
                            if str(entry.get(k) or "").strip()), "")
            if not subject:
                return value
            body = {k: v for k, v in entry.items()
                    if k not in ("subject", "who", "character")}
            # A single-valued entry ({subject, value}) is the item itself.
            payload = body.get("value", body.get("entries", body))
            if isinstance(payload, (list, tuple)):
                keyed.setdefault(subject, []).extend(payload)
            else:
                keyed.setdefault(subject, []).append(payload)
        return keyed or value
    if not isinstance(value, dict):
        return value
    out = {}
    for key, item in value.items():
        if item is None:
            out[key] = []
        elif isinstance(item, (list, tuple)):
            out[key] = list(item)
        else:
            out[key] = [item]
    return out


def _coerce_attire_diff(value):
    """One body's attire diff, canonicalized by attire.coerce_diff_shape.

    Delegated rather than reimplemented because commit.py must run the same
    coercion: rerunning a stage replays diffs stored before this existed, and
    two spellings of the rule would eventually disagree about the same body.
    attire.py imports nothing but `re`, so there is no cycle.
    """
    from story import attire
    return attire.coerce_diff_shape(value)


def _clamp_float(value, lo, hi, default):
    """Coerce to a float within [lo, hi], tolerating the out-of-range numbers
    and non-numeric strings weaker models emit for bounded fields (a
    prompt-compliant 'big betrayal' delta of 0.3, confidence '85', urgency
    'high'). Clamping is obviously correct here and keeps the character step
    from hard-crashing on an advisory number. See tests/test_tom_normalization.py."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return max(lo, min(hi, f))

# ---- Pydantic v1/v2 Compatibility ----

_PYDANTIC_V2 = hasattr(BaseModel, "model_validate")

if _PYDANTIC_V2:
    from pydantic import field_validator

    def _validate(model_cls, data):
        return model_cls.model_validate(data)

    def _dump(model):
        return model.model_dump(exclude_none=True)

    def _fields(model_cls):
        return model_cls.model_fields
else:
    # v1 records a field's container kind as an int enum on the ModelField.
    # There is no v2 equivalent; `_declared` reads the annotation there.
    from pydantic.fields import SHAPE_LIST as _SHAPE_LIST_V1

    def _validate(model_cls, data):
        return model_cls.parse_obj(data)

    def _dump(model):
        return model.dict(exclude_none=True)

    def _fields(model_cls):
        return model_cls.__fields__

# ---- Enums ----

class SpeechVolume(str, Enum):
    whisper = "whisper"
    mutter = "mutter"
    normal = "normal"
    loud = "loud"
    shout = "shout"

class ActionVisibility(str, Enum):
    overt = "overt"
    concealed = "concealed"

class ActionCommitment(str, Enum):
    asserted = "asserted"
    contestable = "contestable"

class ActionStage(str, Enum):
    immediate = "immediate"
    preparation = "preparation"
    approach = "approach"
    contact = "contact"
    sustained = "sustained"

class PlayerAuthorityMode(str, Enum):
    actor_only = "actor_only"
    explicit_outcomes = "explicit_outcomes"
    world_author = "world_author"

class BehaviorController(str, Enum):
    inert = "inert"
    deterministic = "deterministic"
    reactive = "reactive"
    stochastic = "stochastic"
    character_agent = "character_agent"
  
_VOLUME_ALIASES = {
    "": "normal",
    "quiet": "mutter",
    "quietly": "mutter",
    "soft": "mutter",
    "softly": "mutter",
    "conversational": "normal",
    "conversation": "normal",
    "moderate": "normal",
    "medium": "normal",
    "ordinary": "normal",
    "enthusiastic": "loud",
    "excited": "loud",
    "raised": "loud",
    "raised voice": "loud",
    "yell": "shout",
    "yelling": "shout",
    "scream": "shout",
    "screaming": "shout",
}

def normalize_speech_volume(value: Any) -> str:
    volume = str(value or "normal").strip().casefold()
    volume = _VOLUME_ALIASES.get(volume, volume)

    if volume not in {
        "whisper",
        "mutter",
        "normal",
        "loud",
        "shout",
    }:
        return "normal"

    return volume
    

# ---- Fiction Model ----

# ---- One coercion for a whole failure family ----
#
# Five separate crashes in one session were the same shape: a field typed `str`
# receiving a structured object, which discards the ENTIRE stage output and
# costs a whole beat -- observations_used, association_updates, initial_state
# goals, response_candidates.response, changes_asserted.change. Roughly ninety
# more str-typed fields in this file carry the same exposure, and fixing them as
# they crash is a queue rather than a solution.
#
# So the coercion lives once, on a base every schema model inherits. It fires
# only when the declared type is `str` AND the value is a dict or list -- the
# exact mismatch -- and reduces to the prose the value contains. Anything else
# passes through untouched, so it cannot mask a genuine type error on a field
# never meant to hold text.
#
# Rejecting these was never protecting anything: a str field has no invariant a
# nested object violates, and the model plainly meant the words inside it.
_PROSE_KEYS = ("text", "observable", "attempt", "summary", "description",
               "content", "value", "claim", "response", "detail", "reason",
               "name", "id")


def _flatten_to_text(value):
    """The prose inside a structured value, for a field declared `str`."""
    if isinstance(value, dict):
        for key in _PROSE_KEYS:
            got = value.get(key)
            if isinstance(got, str) and got.strip():
                return got.strip()
        parts = [str(v).strip() for v in value.values()
                 if isinstance(v, (str, int, float)) and str(v).strip()]
        return "; ".join(parts)
    if isinstance(value, (list, tuple)):
        parts = [
            _flatten_to_text(v) if isinstance(v, (dict, list, tuple))
            else str(v).strip()
            for v in value
        ]
        return "; ".join(p for p in parts if p)
    return value


# What the coercions below need to know about a field, read the same way on
# either Pydantic major. Pydantic 1 answered all of this from its ModelField
# (`allow_none`, `outer_type_`, `shape == SHAPE_LIST`, `type_`); Pydantic 2 has
# no ModelField at all and the annotation is the only source. Reading it once,
# here, is what keeps the coercion logic itself version-free -- the alternative
# is v1-only internals leaking into rules about model behaviour, which is how
# `pydantic.fields.SHAPE_LIST` came to decide whether a character's beat
# survived.
class _Declared(NamedTuple):
    allows_none: bool     # None is a real value here, not an omission
    default: Any          # the field's own default, or None if it has none
    default_factory: Any
    is_str: bool          # declared plain prose
    is_int: bool          # declared a whole number
    is_bool: bool         # declared a yes/no
    is_list: bool         # declared a list of something
    item_type: Any        # that list's element type, if it has one
    expects_object: bool  # declared a dict or a nested model
    value_type: Any       # a declared dict's value type, if it has one


_NONE_TYPE = type(None)


def _expects_object(annotation):
    """Whether this annotation wants a JSON object -- a dict or a model.

    Both are the same shape on the wire, and Pydantic 1 accepted the same
    wrong spellings for either (`dict([])` and `dict("")` are both `{}`), so
    the coercions treat them as one kind.
    """
    if annotation is dict or get_origin(annotation) is dict:
        return True
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _mapping_value_type(annotation):
    """A declared dict's value type, or None when it declares no value type."""
    if get_origin(annotation) is not dict:
        return None
    args = get_args(annotation)
    return args[1] if len(args) == 2 else None


def _strip_optional(annotation):
    """`Optional[X]` -> `X`, which is what v1's `outer_type_` already gave us.

    A union of two real types is left alone: it is not "X, optionally absent"
    and must not be read as X.
    """
    args = get_args(annotation)
    if _NONE_TYPE in args:
        rest = [a for a in args if a is not _NONE_TYPE]
        if len(rest) == 1:
            return rest[0]
    return annotation


def _field_required(field):
    """Whether the model is obliged to supply this field, either major."""
    is_required = getattr(field, "is_required", None)   # v2 FieldInfo
    if callable(is_required):
        return bool(is_required())
    return bool(getattr(field, "required", False))      # v1 ModelField


def _subject_field_of(model):
    """The field an item model NAMES as its subject, either major.

    A leading-underscore class attribute is a plain string on Pydantic 1 and a
    `ModelPrivateAttr` wrapper on Pydantic 2, where the name lives in
    `.default`. Reading it with a bare `getattr` therefore worked on 1 and
    raised `TypeError: unhashable type: 'ModelPrivateAttr'` on 2 -- the major
    `constraints.txt` pins. The declaration has never once been honoured in a
    default install; it crashed the coercion instead, and only the Pydantic 1
    job was green enough to hide it.

    Returns None for anything that is not a non-empty string, so a typo'd or
    absent declaration falls back to the positional rules rather than raising.
    """
    slot = getattr(model, "_subject_field", None)
    if not isinstance(slot, str):
        # v2 wrapper; `.default` is PydanticUndefined when none was declared,
        # which the isinstance check below rejects along with everything else.
        slot = getattr(slot, "default", None)
    return slot if isinstance(slot, str) and slot else None


def _declared(field):
    """Read one field's declared shape off whichever Pydantic is installed."""
    factory = getattr(field, "default_factory", None)
    required = _field_required(field)
    # A required field has no default to fall back on. Spelling that as None
    # keeps `default` meaning "the value this field falls back to", rather
    # than v2's PydanticUndefined sentinel leaking into the coercion rules.
    default = None if (required or factory is not None) else field.default

    if not _PYDANTIC_V2:
        outer = field.outer_type_
        return _Declared(
            allows_none=bool(field.allow_none),
            default=default,
            default_factory=factory,
            is_str=outer is str,
            is_int=outer is int,
            is_bool=outer is bool,
            is_list=getattr(field, "shape", None) == _SHAPE_LIST_V1,
            item_type=getattr(field, "type_", None),
            expects_object=_expects_object(outer),
            value_type=_mapping_value_type(outer),
        )

    annotation = field.annotation
    inner = _strip_optional(annotation)
    # `Any` accepts None, and v1 read it as allow_none too.
    allows_none = (annotation is None or annotation is Any
                   or _NONE_TYPE in get_args(annotation))
    args = get_args(inner)
    # Only a PARAMETRIZED list counts, matching v1, where a bare `list`
    # annotation is a singleton and not SHAPE_LIST. The wrap-a-single-item rule
    # is about a list of known items; a bare `list` declares no item to be one
    # of, so a dict there stays the disagreement it is instead of becoming a
    # one-element list that validates.
    is_list = get_origin(inner) is list
    return _Declared(
        allows_none=allows_none,
        default=default,
        default_factory=factory,
        is_str=inner is str,
        is_int=inner is int,
        is_bool=inner is bool,
        is_list=is_list,
        item_type=args[0] if (is_list and args) else None,
        expects_object=_expects_object(inner),
        value_type=_mapping_value_type(inner),
    )


def _item_fields(item_type):
    """The element model's own fields, or {} when the element is not a model."""
    if item_type is None or not isinstance(item_type, type):
        return {}
    if not issubclass(item_type, BaseModel):
        return {}
    return _fields(item_type) or {}


def _empty_container(value):
    """An empty `[]`, `()` or `""` -- every spelling of "nothing to report"
    that is not already an object."""
    return isinstance(value, (list, tuple, str)) and not value


def _as_declared_scalar(value, target):
    """One scalar into the type its field declared, as Pydantic 1 did it.

    Pydantic 1 coerced these itself in its lax mode and Pydantic 2 refuses
    them, so without this the same engine is measurably more brittle
    depending on which major happens to be installed -- and the brittleness
    reads later as a bad model rather than as a dependency difference.
    Only the two directions v1 actually performed are reproduced: any scalar
    into prose (`5` -> `"5"`, and a bool is an int, so `True` -> `"True"`),
    and a fractional number into a whole one (`1.5` -> `1`, v1's truncation).
    """
    if target is str and isinstance(value, (int, float)):
        return str(value)
    if target is int and isinstance(value, float):
        # `int(inf)` raises OverflowError, which is neither ValueError nor
        # AssertionError and so is rewrapped by NEITHER major -- it escapes
        # every `except ValidationError` in the engine. `1e999` is ordinary
        # JSON and `json.loads` gives it back as `inf`, so this is reachable
        # from any model that writes a large number. An infinity is not a
        # whole number anyway: leave it to fail as the validation error it
        # is, which is what it did before this coercion existed.
        if math.isinf(value) or value != value:
            return value
        return int(value)
    return value


def _coerce_member(value, declared_type):
    """One element of a declared list, or one value of a declared dict.

    Neither is a field of anything, so no validator ever reaches it -- this
    is the only place their spelling can be tolerated.
    """
    if declared_type is None:
        return value
    # `dict[str, Optional[str]]` (perception's views) declares prose that may
    # be absent, and an absent one stays absent -- `_as_declared_scalar`
    # leaves None alone. What it must not do is read `Optional[str]` as "not
    # prose" and let a number through to fail the step.
    declared_type = _strip_optional(declared_type)
    # A container inside a container -- `dict[str, list[dict]]` is
    # `StateDiff.conditions`, and its inner list's items are as unreachable
    # from a field validator as the list itself was. Recursing costs one
    # line and stops the same rule needing to be rediscovered one level
    # down.
    origin = get_origin(declared_type)
    args = get_args(declared_type)
    if origin is list:
        if isinstance(value, list):
            return [_coerce_member(item, args[0] if args else None)
                    for item in value]
        if isinstance(value, (dict, str)) and not value:
            return []
    if origin is dict and isinstance(value, dict):
        return {key: _coerce_member(item, args[1] if len(args) == 2 else None)
                for key, item in value.items()}
    if _expects_object(declared_type) and _empty_container(value):
        return {}
    # A bare scalar where an OBJECT was declared. The model answered the
    # object's SUBJECT and skipped the wrapper -- asked for
    # `poses:{name:{posture,support,...}}` it sent `{"Hinami": "standing"}`,
    # which is a complete and correct answer to "what is her posture" written
    # in the shorter of the two spellings. Both majors refuse it, and refusing
    # cost the OPENING turn of a story: six bodies, six strings, one dead
    # `director_establish` and no scene at all.
    #
    # This is the mirror of the map-arrives-where-a-list-was-declared rule
    # below, and it asks the same question through the same cascade -- when
    # the model supplied only the subject, where does it go? An item model
    # with no answerable subject slot is left to fail rather than guessed at.
    if _expects_object(declared_type) and isinstance(
            value, (str, int, float, bool)) and not isinstance(value, bool):
        slot = _subject_slot(declared_type)
        if slot:
            return {slot: value}
    return _as_declared_scalar(value, declared_type)


def _subject_slot(model, fields=None):
    """Which field of an item model carries its SUBJECT, or None.

    Extracted so the two places that need it -- a name-keyed map arriving
    where a list was declared, and a bare scalar arriving where the item
    itself was -- cannot answer it differently. Both are asking one question:
    when the model supplied only the subject, where does it go?

    Three rungs, each earned:

    * What the model DECLARES (`_subject_field`). A heuristic cannot see the
      one case where the subject carries a non-empty default:
      `GoalImpact.serves` defaults to "situational", so it is neither required
      nor an empty prose slot, and `{"reach the tower": {"impact": 0.6}}`
      filed the goal in `why` -- recording the goal as its own explanation and
      leaving `serves` generic, which commit.py's goal matching cannot use.
    * The first REQUIRED field. The subject of these shapes is what the model
      is obliged to supply. A guessed list of about_entity/name/entity/id
      looked general and was not -- it missed `belief` on BeliefUpdate and
      `cue` on AssociationUpdate.
    * The first field declared as prose whose default is EMPTY. An empty
      default means "nothing said yet", which is the hole a subject fills; a
      non-empty one is a value the author already chose. Declaration order
      alone would be wrong: it names `category` on AssertedChange (default
      "other") and `op` on LoreOp (default "create").
    """
    if fields is None:
        fields = _item_fields(model)
    if not fields:
        return None
    slot = _subject_field_of(model)
    if slot is not None and slot not in fields:
        slot = None
    if slot is None:
        slot = next((name for name, field in fields.items()
                     if _field_required(field)), None)
    if slot is None:
        slot = _first_empty_prose_field(fields)
    return slot


def _first_empty_prose_field(fields):
    """The slot a name-keyed map's KEY belongs in, when nothing is required.

    The first field declared as plain, non-optional prose whose default is
    empty. Emptiness is the test because an empty default means "nothing
    said yet", which is exactly the hole a key fills, while a non-empty
    default is a value the author already chose. Optional prose is excluded
    for the same reason from the other side: where None is a legitimate
    value, absence already means something, and `BookOp.temp_id` -- a
    scratch handle, declared before the `name` the key actually is -- would
    otherwise swallow every key in a map of books.
    """
    for name, field in fields.items():
        declared = _declared(field)
        if declared.is_str and not declared.allows_none and not declared.default:
            return name
    return None


_BOOLISH = frozenset(
    ("true", "false", "yes", "no", "on", "off", "y", "n", "t", "f", "1", "0"))


def _reads_as_bool(value):
    """Whether both Pydantic majors would read this as a yes/no."""
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return value in (0, 1)
    if isinstance(value, str):
        return value.strip().lower() in _BOOLISH
    return False


#: How many entries an unbounded list of FREE STRINGS may carry.
#:
#: A list of bare strings is the one shape in this schema that invites a model
#: to ENUMERATE, and enumeration is where a stuck sampler locks: each
#: comma-separated item is highly predictable from the last. Live, a character
#: step's `serves` began with real aims, drifted into the payload's own field
#: names, ran off into JSON Schema meta-keywords, and cycled those for
#: thousands of tokens.
#:
#: 64 is measured, not guessed. Across 26,975 stored variants -- the whole of a
#: live install's history -- the longest free-string list ever produced was 13
#: (`state`, and `dialogue_order` in a crowded beat). The largest structure of
#: ANY kind was a 28-key `entities` map. So this sits roughly five times above
#: anything real play has ever generated, which is the point: it must never
#: decide the shape of legitimate output, only stop a runaway.
#:
#: Dicts and lists of MODELS are deliberately NOT capped, though they were
#: measured in the same sweep. Dropping the tail of `serves` costs advisory
#: metadata; dropping the tail of `entities` or `positions` costs world state
#: that commit.py is about to persist. And a model cannot fall into an object
#: list the way it falls into a comma-separated one -- every item needs
#: structure, which breaks the cadence a loop rides on.
FREE_STRING_LIST_LIMIT = 64


def _lenient_coerce(value, declared, name=""):
    """The one coercion, given a value and the shape its field declared.

    `name` is only used to say which field lost something; it never changes
    what the coercion does.
    """
    if value is None and not declared.allows_none:
        if declared.default_factory is not None:
            return declared.default_factory()
        if declared.default is not None:
            return declared.default
        return value
    if isinstance(value, (dict, list, tuple)) and declared.is_str:
        return _flatten_to_text(value)
    # A bare number where prose was declared, or a fractional one where a
    # count was. See `_as_declared_scalar`: Pydantic 1 did both itself, so
    # doing them here keeps the engine's tolerance the same on both majors
    # instead of leaving it to whichever one is installed -- a divergence of
    # exactly the kind that reads later as a bad model.
    if declared.is_str or declared.is_int:
        coerced = _as_declared_scalar(
            value, str if declared.is_str else int)
        if coerced is not value:
            return coerced
    # A yes/no field answering a different question. Observed live:
    # `entities.permit.container` -- "is this a container" -- came back as
    # `"kess_vantar"`, the id of whoever was holding it. Both majors refuse
    # it, and refusing costs the whole step its normalization over one
    # misused field. Falling back to the declared default asserts nothing:
    # the value could not have meant yes-or-no, and the answer it did carry
    # has no slot here to survive in.
    if declared.is_bool and not _reads_as_bool(value):
        if declared.default_factory is not None:
            return declared.default_factory()
        return declared.default
    # An empty list or an empty string where an object was declared. To a
    # model these all read as "nothing to report", and Pydantic 1 agreed
    # with it -- `dict([])` and `dict("")` are both `{}`, so v1 accepted the
    # wrong spelling for every dict- and model-typed field for free. On v2
    # it is a hard error, and the error is not confined to the one field:
    # `validate_llm_output` returns the UNNORMALIZED payload when validation
    # fails, so one `"appraisal": []` costs the whole step every default,
    # every flatten and every wrap the rest of this function would have
    # done. `_coerce_empty_list_to_dict` already does this for six named
    # state_diff/scene_patch keys, which is where it was first seen to crash
    # a live turn; the field's own declaration says which fields need it.
    if declared.expects_object and _empty_container(value):
        return {}
    # And the mirror of it: `{}` or `""` where a list was declared. Same
    # "nothing to report", same field-declares-which-fields-need-it
    # generalization of `_coerce_empty_dict_to_list`, which already does this
    # for three named scene_patch keys. Seen live on
    # `lore_ops[].knowledge_locations: ""`, which cost the mapping commit.
    if declared.is_list and isinstance(value, (dict, str)) and not value:
        return []
    # The same two rules again, one level down. `_lenient_coerce` is a
    # per-FIELD validator, so a nested LenientModel applies it to its own
    # fields -- but nothing applies it to the ELEMENTS of a `list[str]` or
    # the VALUES of a `dict[str, str]`, which are not fields of anything.
    # v1 coerced those element-wise (`[1, 2]` -> `["1", "2"]`) and v2 fails
    # the whole step over `dialogue_order.0: Input should be a valid
    # string`, which is how a model answering with room NUMBERS instead of
    # room names costs a beat.
    if declared.is_list and isinstance(value, list):
        # The runaway ceiling, applied before the per-item coercion so a
        # thousand-element loop is not walked element by element first.
        if declared.item_type is str and len(value) > FREE_STRING_LIST_LIMIT:
            _note_drop(
                f"{name or 'a free-string list'} arrived with {len(value)} "
                f"entries and was cut to {FREE_STRING_LIST_LIMIT} -- this is "
                "the runaway ceiling, so read the tail as a stuck sampler "
                "rather than as content")
            value = value[:FREE_STRING_LIST_LIMIT]
        members = [_coerce_member(item, declared.item_type) for item in value]
        if declared.item_type is dict:
            # A BARE `list[dict]` -- `relevant_lore`, `npc_suggestions`,
            # `sequence`, `staged_lore` -- says "objects, shape unpoliced".
            # There is no item model to consult, so a scalar element carries
            # nothing that could be mapped into one, and every consumer
            # already skips it (`agents/common.lore_for` filters
            # `isinstance(e, dict)`; nothing reads `npc_suggestions` at
            # all). The schema was the only strict layer, and it failed the
            # WHOLE step: observed live, `relevant_lore: [1934, 1938, ...]`
            # -- the model answering with lore ids -- aborted the turn.
            # Dropping the element costs that element; failing costs the
            # beat. A PARAMETRIZED `list[dict[str, Any]]` is left strict on
            # purpose: that is what `chat_archive` declares its rows as, and
            # an archive quietly missing a turn is worse than one refused.
            members = _kept(name or "a list of objects", members,
                            [m for m in members if isinstance(m, dict)])
        return members
    if declared.value_type is not None and isinstance(value, dict):
        return {key: _coerce_member(item, declared.value_type)
                for key, item in value.items()}
    # One item where a list was declared. Asked for "updates" and having
    # exactly one to report, a model will often return the object rather
    # than a list of one -- observed live, a character agent returned a
    # bare object for both `mind_model_updates` and `relationship_updates`
    # and the whole beat was discarded with "value is not a valid list".
    # The mirror of the case above, and no more ambiguous: the singular
    # and the list of one mean the same thing.
    if declared.is_list and isinstance(value, dict) and value:
        # Two different things arrive as a bare dict here and they need
        # opposite treatment. One is a single item -- wrap it. The other
        # is a MAP of items keyed by name, which models reach for when
        # the list is "updates about people": {"Mara": {...}, "Vesk":
        # {...}}. Wrapping that produces a one-element list whose element
        # is the whole map, and it fails as
        # `mind_model_updates.0.about_entity: field required` -- an error
        # that reads like the model omitted a field when in fact we
        # mangled its structure.
        #
        # Told apart by whether the dict's own keys look like the item's
        # fields. Nothing is guessed: a map whose values are not all
        # objects is not a map of items, and is wrapped as before.
        fields = _item_fields(declared.item_type)
        item_fields = set(fields)
        looks_like_item = bool(item_fields & set(value))
        if (not looks_like_item and item_fields
                and all(isinstance(v, dict) for v in value.values())):
            # Carry the key across when the item has an obvious slot for
            # it and the model left that slot empty -- the key IS the
            # subject in this shape.
            # Which slot the key belongs in is the item's own FIRST
            # REQUIRED field, not a list of names guessed in advance. A
            # guessed list of about_entity/name/entity/id looked general
            # and was not: it missed `belief` on BeliefUpdate and `cue`
            # on AssociationUpdate, so a map keyed by belief text lost
            # the text and failed as `belief_updates.0.belief: field
            # required` -- the same error the map handling existed to
            # prevent, one model over. The subject of these shapes is
            # what the model is obliged to supply, which is exactly what
            # "first required field" names.
            # An item model may NAME its own subject, and that wins over
            # both rules below. They are positional heuristics, and a
            # heuristic cannot see the one case where the subject field
            # carries a non-empty default: `GoalImpact.serves` defaults to
            # "situational", so it is neither required nor an empty prose
            # slot, and `{"reach the tower": {"impact": 0.6}}` filed the goal
            # in `why` -- recording the goal as the explanation and leaving
            # `serves` generic, which commit.py's goal matching cannot use.
            # The information survived and landed where nothing reads it.
            # Declaring the slot is how a model says which field is its
            # subject, rather than the shape rules guessing.
            # An item model where nothing is required still has a subject,
            # and dropping the key threw it away entirely: a
            # `knowledge_seeds` map keyed by the seed's own text arrived
            # with `content: ""`, which is the whole seed. See
            # `_subject_slot` for the cascade and why each rung exists.
            slot = _subject_slot(declared.item_type, fields)
            out = []
            for key, item in value.items():
                item = dict(item)
                if slot and not item.get(slot):
                    item[slot] = key
                out.append(item)
            return out
        return [value]
    return value


def coerce_to_declared(model_cls, field_name, value):
    """The value half of the leniency, for models defined outside this file.

    `character_schema.py`'s profiles are plain `BaseModel`s and were relying
    on Pydantic 1 to turn a number into prose for them -- a card with
    `"expression": 3` loaded fine on 1.x and raises on 2.x, from
    `normalize_character_data`, which is the READ path for every character
    accessor. That is a 500 on character save and an unreadable character
    on every later turn.

    Exported rather than duplicated there: which Pydantic is installed, and
    what v1 used to coerce, are two facts this module already owns, and a
    second copy of either is how the majors drift apart again.
    """
    field = _fields(model_cls).get(field_name)
    if field is None:
        return value
    declared = _declared(field)
    if declared.is_str:
        # Structured where prose was declared, same as `LenientModel` --
        # a nested object in `belief` or `expression` is an uncaught
        # ValidationError out of `_normalize_psychology` on both majors,
        # which is a 500 on character save. Flatten it as the rest of the
        # engine does rather than lose the sheet.
        if isinstance(value, (dict, list, tuple)):
            return _flatten_to_text(value)
        return _as_declared_scalar(value, str)
    if declared.is_int:
        return _as_declared_scalar(value, int)
    return value


class LenientModel(BaseModel):
    """BaseModel that accepts a structured value where prose was declared.

    Also treats an explicit `null` on an OPTIONAL field as "the model declined
    to fill this in", which is what it means. `null` is the natural encoding
    of absence, and several models reach for it: observed live, a character
    agent returned `"norm_conflict": null` -- there was no norm conflict --
    and the whole beat was thrown away with
    `norm_conflict: none is not an allowed value`. The field's own default is
    `""`, which means the same thing, so the beat was discarded over spelling.

    A field that ALLOWS None keeps it, because there None is a real value and
    not an omission. A REQUIRED field with no default is left alone to fail:
    inventing a value for something the model was obliged to supply would
    hide the actual error, and that is worth a hard failure.
    """

    if _PYDANTIC_V2:
        # Still a per-FIELD validator on v2, not a whole-model one. What v2
        # removed is the `field` parameter, not the `"*"` target, and
        # `ValidationInfo.field_name` replaces it.
        #
        # The distinction decides correctness, not style. A model-level
        # before-validator runs ahead of every field validator, so this generic
        # coercion would pre-empt the field-specific ones -- and some of those
        # exist precisely to handle a shape this one would handle WORSE.
        # `ResponseCandidate.response` is the case: `_coerce_candidate_response`
        # degrades a prose-less sequence element to "", while the generic
        # flatten scavenges every scalar it can find and returns the `type`
        # discriminator as if it were prose ({"type": "action"} -> "action").
        # As a field validator this runs after the field's own, matching v1,
        # where a specific `pre=True` validator precedes the inherited `"*"`.
        @field_validator("*", mode="before")
        @classmethod
        def _coerce_structured_into_str(cls, value, info):
            field = _fields(cls).get(info.field_name)
            if field is None:
                return value    # extra="allow" keys are not ours to reshape
            return _lenient_coerce(
                value, _declared(field),
                f"{cls.__name__}.{info.field_name}")
    else:
        @validator("*", pre=True, allow_reuse=True)
        def _coerce_structured_into_str(cls, value, field):
            return _lenient_coerce(
                value, _declared(field), f"{cls.__name__}.{field.name}")


class CausalRegime(LenientModel):
    regime_id: str
    scope: str = "default"
    priority: int = 0
    rules: dict[str, Any] = Field(default_factory=dict)

class FictionFrame(LenientModel):
    frame_id: str = ""
    world_id: str = ""
    location_id: Optional[str] = None
    scale: str = "personal"
    temporal_mode: str = "immediate"
    causal_regime_ids: list[str] = Field(default_factory=list)
    active_entity_ids: list[str] = Field(default_factory=list)
    aggregate_entity_ids: list[str] = Field(default_factory=list)
    observer_ids: list[str] = Field(default_factory=list)
    stakes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

# ---- Actions ----

class DurationHint(LenientModel):
    value: Optional[float] = None
    unit: str = "seconds"
    explicit: bool = False

class IntendedEffect(LenientModel):
    target_id: Optional[str] = None
    kind: str
    details: dict[str, Any] = Field(default_factory=dict)

class ActionElement(LenientModel):
    type: str = "action"
    event_id: str = ""
    actor_id: str = ""
    raw_text: str = ""
    attempt: str = ""
    # Intent-free OUTWARD surface of the act -- what a bystander literally
    # sees/hears, with no purpose, magical intent, or private mental content.
    # Delivered to OTHER perceivers in place of `attempt` (which is the actor's
    # own intent-laden framing). "" = the act has no outward manifestation (a
    # purely mental beat) and must not be surfaced to observers at all. See
    # agents/common.observable_action_text and norm_sequence.
    observable: str = ""
    # Authorship mode of a player-authored element. 'pc_action' (default) is
    # the player's character acting. 'npc_offer' is the player authoring another
    # character's interior/behavior -- rerouted to that character's own agent as
    # an offer rather than enacted as truth (the character owns its psychology).
    # 'world_assertion'/'ooc_directive' name the authorial and out-of-character
    # channels. Legacy payloads with no mode default to pc_action.
    mode: str = "pc_action"
    verb: str = ""
    commitment: ActionCommitment = ActionCommitment.contestable
    stage: ActionStage = ActionStage.immediate
    targets: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    intended_effects: list[IntendedEffect] = Field(default_factory=list)
    asserted_effects: list[IntendedEffect] = Field(default_factory=list)
    duration: DurationHint = Field(default_factory=DurationHint)
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)
    conditions: list[dict] = Field(default_factory=list)

class SpeechElement(LenientModel):
    type: str = "speech"
    text: str
    volume: SpeechVolume = SpeechVolume.normal

    _norm_volume = validator("volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )
    tone: str = ""
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)

class DiceSpec(LenientModel):
    # Advisory sub-field of the interpret flow; the Director re-judges
    # difficulty during resolution, so a weak model dropping one key must
    # not hard-crash the whole director_interpret step.
    actor: str = ""
    attempt: str = ""
    ability: str = ""
    difficulty: str = "medium"

class MovementDecl(LenientModel):
    to_room: str
    why: str = ""
    # WHO relocates. "self" (default) = the player's own body. An entity id
    # = the declared move is of a VEHICLE/vessel/mount the player is
    # driving or piloting: the ENTITY's exterior position changes and the
    # player's body stays where it is (typically that entity's interior).
    # Without this field "I drive the van onto the ferry" was structurally
    # identical to "I walk onto the ferry" and moved the player's body.
    mover: str = "self"
    # Does the declaration cover ARRIVING, or only setting off?
    #
    # "I walk to the bridge" arrives. "I wander towards the building" does not:
    # it says which way the walker is going, and the beat ends with them
    # closer, still outside. Live failure, "The Blizzard" turn 2 -- interpret
    # turned "You wander towards it" into
    # `to_room: distant_mountain_building`, the route check passed it (the
    # rooms genuinely were adjacent and open), and the resolve wrote her
    # through the door into the firelight. Nothing was wrong except that
    # nobody had said she was going in.
    #
    # A FIELD rather than something inferred downstream, because it cannot be
    # inferred: measured across 1249 live turns, no test on the declaration's
    # own text separates "I cross the command deck toward the med bay" (an
    # asserted crossing) from "wander towards it" (progress) -- both say
    # "toward", and only the stage that actually read the player's sentence
    # can tell. `stage: "approach"` was already in the schema and read by
    # nothing on the resolve path, which is the same mistake one field over.
    #
    # Defaults TRUE: every declaration that reached this field before it
    # existed meant arrival, and a default of False would strand every one of
    # them.
    arrives: bool = True

# ---- Flow ----

class FlowPlan(LenientModel):
    reactors: list[int] = Field(default_factory=list)
    reactor_refs: list[Any] = Field(default_factory=list)
    addressed_to: list[int] = Field(default_factory=list)
    addressed_to_refs: list[Any] = Field(default_factory=list)
    dialogue_mode: bool = False
    needs_mapping: bool = False
    mapping_request: str = ""
    dice: list[DiceSpec] = Field(default_factory=list)
    tom_triggers: list[int] = Field(default_factory=list)
    tom_trigger_refs: list[Any] = Field(default_factory=list)
    resolution_flags: dict[str, Any] = Field(default_factory=dict)
    generation_requests: list[dict] = Field(default_factory=list)
    authority_claims: list[dict] = Field(default_factory=list)
    fiction_frame: dict[str, Any] = Field(default_factory=dict)
    # Future world beats the player narrated for a LATER turn (P4). Each
    # {summary, due_in_turns}; the engine stores and re-delivers them when due
    # so a player-scheduled event is never silently dropped.
    scheduled_assertions: list[dict] = Field(default_factory=list)

# ---- Director Interpret ----

class OtherPlayerInterpret(LenientModel):
    """Same-beat declaration for an additional human player, interpreted
    with the same rigor as the primary player's top-level fields above --
    this is a second real player, not an NPC. Deliberately a narrower
    mirror of DirectorInterpret's own fields (no separate flow/movement
    plan) rather than a full duplicate: each extra player still shares the
    beat's single flow/reactor plan, since interaction/reaction resolution
    stays scene-wide, not per-player.
    """
    sequence: list[dict] = Field(default_factory=list)
    speech: Optional[str] = None
    speech_volume: SpeechVolume = SpeechVolume.normal
    private_thought: Optional[str] = None
    action: Optional[dict] = None
    follow_op: Optional[dict] = None
    notes: str = ""

    _norm_volume = validator("speech_volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )

class DirectorInterpret(LenientModel):
    kind: str = "mixed"
    sequence: list[dict] = Field(default_factory=list)
    speech: Optional[str] = None
    speech_volume: SpeechVolume = SpeechVolume.normal
    private_thought: Optional[str] = None
    action: Optional[dict] = None
    actions: list[dict] = Field(default_factory=list)
    movement: Optional[MovementDecl] = None
    # A direct, already-present bodily contact the player declares through
    # their own conduct or first-person sensation. These are guarded against
    # the standing scene ledger before pass 1; they are not a license to author
    # a new NPC action. Contact points are open anatomical strings, independent
    # of attire/visibility regions. Each assertion may also carry independent
    # relation (surface|interior) and motion (settled|moving) axes.
    contact_assertions: list[dict] = Field(default_factory=list)
    # WHAT THE PLAYER SAYS HAPPENS, HAPPENS -- that turn, before perception
    # pass 1 fires. A full `StateDiff`, deliberately the SAME structure
    # `director_resolve` emits rather than a curated subset of it: interpret
    # is not a lesser authority than resolve, it is the same authority scoped
    # to the player's input. A declaration that reached the scene only through
    # resolve was invisible for the whole beat in which it was made, because
    # resolve runs after every character has declared. Previewed on a copy for
    # pass 1 and merged into resolve's own diff, so persistence stays exactly
    # where it was: commit, once, through every guard it already runs.
    #
    # Typed as `StateDiff` rather than a bare dict on purpose: it makes the
    # claim checkable. `tools/project_check.py` walks nested models to catch a
    # prompt asking for a field its schema cannot hold, and through an untyped
    # dict it saw nothing -- the exact silent-drop class that cost `entry_ops`,
    # `offscreen_plan_ops` and `project_ops` a measurement each.
    # Forward-referenced: `StateDiff` is declared further down, and resolving
    # it after the fact is cheaper than moving either class.
    state_assertions: Optional["StateDiff"] = None
    # Voluntary durable travel relation for the player. {op:start,target} or
    # {op:stop,reason}; absence means keep the current relation unchanged.
    follow_op: Optional[dict] = None
    location_query: Optional[str] = None
    flow: FlowPlan = Field(default_factory=FlowPlan)
    notes: str = ""

    _norm_volume = validator("speech_volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )
    # Additive multiplayer support: interpretations for any additional
    # human players declaring in this same beat, keyed by persona_id (as a
    # string, since JSON object keys are always strings). Empty for every
    # single-player chat -- nothing here changes behavior unless
    # ctx.extra_players is non-empty.
    other_players: dict[str, OtherPlayerInterpret] = Field(default_factory=dict)
    # ENGINE-AUTHORED (the DirectorResolve.orchestration contract): the
    # orchestrated interpret's own dispatch/scope record. Interpret and
    # resolve are equivalent in capability, so both stages carry the same
    # record shape; empty on every monolithic interpret.
    orchestration: dict[str, Any] = Field(default_factory=dict)

# ---- Scene Entities ----

class SceneEntityDef(LenientModel):
    name: str
    kind: str = "object"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    portable: bool = False
    container: bool = False
    interior_rooms: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    # A voice with no body and no room: a ship's computer, a station AI, a
    # building PA. Positioning one is a category error -- the Enterprise
    # computer is not "in Ten Forward" -- and doing so both pinned it to a
    # single room and made it a promotion candidate. Flagged entities are
    # voiced by the Director, audible wherever the scene is, and never tracked
    # as background presences.
    ubiquitous: bool = False
    # What an interior lets through: opaque | transparent | barred | membrane
    # (spatial._closed_enclosure_barrier / _open_enclosure_barrier). The first
    # three describe the CLOSED state and leave an open one see-through, which
    # is right for a lid or a hatch. `membrane` is the soft or draped opening
    # that is opaque in BOTH states -- passable, never see-through -- so an
    # occupant is concealed by going in rather than exposed by it.
    # Declared for the same reason RoomDef.zone is -- an undeclared field does
    # not survive the validation round-trip, so a Director-authored glass case
    # would silently come back opaque. Absent means opaque, the pre-existing
    # behaviour.
    enclosure: Optional[str] = None
    # What this thing EMITS when lit: dim | lit | bright. A torch, a lantern,
    # a screen. Switched off with state.lit false. Declared here for the same
    # reason enclosure is -- an undeclared field does not survive the
    # validation round-trip, and a lamp that comes back unlit is a character
    # standing in the dark holding it.
    light_source: Optional[str] = None
    # What this thing SMELLS of, as a short noun phrase: bread, lamp oil, a
    # censer, a corpse. The sibling of `light_source` -- what the thing emits
    # on a channel other than sight -- and declared for the same reason. It is
    # a standing property of the object, not this beat's event: matter
    # deposited somewhere is `substance_ops`, and a body's own smell is on its
    # card. Absent means the thing has no smell worth a percept.
    scent: Optional[str] = None

class RoomDef(LenientModel):
    name: str = ""
    desc: str = ""
    adjacent: list[dict] = Field(default_factory=list)
    notes: str = ""
    parent_entity: Optional[str] = None
    # Declared here (not just passed through) because Pydantic's default
    # model_dump() drops any field the model doesn't declare -- without
    # this, a model-authored "zone" would be silently stripped during
    # validate_llm_output's round-trip, before spatial_frames.py's
    # split/merge detector ever got a chance to see it. Only an
    # explicitly authored zone difference between two rooms means
    # "genuinely disconnected locale" (see spatial_frames.py's module
    # docstring); most rooms should leave this unset.
    zone: Optional[str] = None
    # How much light there is to see BY: dark | dim | lit | bright. Declared
    # for the same reason `zone` is -- an undeclared field is dropped by the
    # validation round-trip, and a room going dark must survive it. Absent
    # means lit, so nothing changes for a scene that never mentions light.
    light: Optional[str] = None
    # How much of the sky this room stands under: open | sheltered | enclosed.
    # Declared for the same reason `light` and `zone` are -- the validation
    # round-trip drops what it does not declare, and a courtyard that survives
    # as "enclosed" gets no weather at all. Absent falls back to
    # weather.room_exposure's keyword derivation, never to "it rains here".
    exposure: Optional[str] = None
    # The named features within the room that prose already refers to -- the
    # bar, the hearth, the bed -- as {anchor_id: {desc, dir?}}. Entity
    # `stations` hang off these, and `dir` gives each one a wall so left/right
    # can be derived. Declared for the same reason every field above it is,
    # and the omission was load-bearing: the round-trip stripped anchors from
    # every Director-authored room, so the only anchors any story ever had
    # came in through the mapping stage's UNTYPED scene_patch dicts. The
    # Director could not author, update, or even preserve one.
    #
    # Optional, NOT default_factory=dict, and the difference is load-bearing:
    # `_dump` uses exclude_none, so None disappears and silence stays silence.
    # An always-present `{}` would ride out on every room the Director merely
    # echoes, and `_merge_room`'s catch-all would read it as an erasure --
    # blanking the room's anchors on the next beat and taking every station
    # hanging off them with it. Same shape as `zone`/`light`/`exposure` above,
    # for the same reason.
    anchors: Optional[dict[str, dict]] = None
    # How much floor there is to cross: small | medium | large. The only
    # thing that makes two distinct anchors read as "across" rather than
    # "near" (spatial.proximity_rel), so a great hall stops being as
    # intimate as a wardrobe. Survived until now purely by the same accident
    # `anchors` did.
    size: Optional[str] = None

# The macro-world declarations that lived here and in five other sections are
# gone -- twenty-nine models reachable from no entry in SCHEMA_MAP, no other
# model's annotation, and no module outside this file. WorldDef, LocationDef
# and TransitEdge named the fiction_worlds/fiction_locations/transit_edges
# schema the movement/space phases deprecated, under their own comment saying
# "MARKED FOR REMOVAL ... removed in Phase 3"; StrategicPlacement named the
# decommissioned world_placements; the rest (the fiction/time/authority
# models, the entity ontology, the inventory and lorebook shapes) were an
# early world model the unified scene blob replaced.
#
# A declared-and-unreferenced model is worse than no model, which is why this
# is a deletion rather than a wiring: nothing validates against it, so it
# states a shape the engine does not enforce while reading as the contract.
# That is not hypothetical -- the body specialist's sheet asks for
# `tick_interval_seconds`, and the only place that field exists in code is a
# model no call has ever validated. Same removal as `PerceptionOutput`
# further down, for the same reason.
#
# `PersistentCondition` is kept until the open question about condition
# ticking (build the due-tick sweep, or drop the field, the NULL `next_tick`
# column and its index) is answered; `CausalRegime`, `FictionFrame` and
# `SpeechElement` are kept because tests use them as fixtures.

# ---- Conditions and Scheduling ----

class PersistentCondition(LenientModel):
    condition_id: str
    subject_id: str
    kind: str
    severity: float = 0.0
    started_at_seconds: float = 0.0
    expires_at_seconds: Optional[float] = None
    tick_interval_seconds: Optional[float] = None
    next_tick_seconds: Optional[float] = None
    state: dict[str, Any] = Field(default_factory=dict)
    source_event_id: Optional[str] = None

class DestructionEffect(LenientModel):
    """REVIVED (movement/space Phase 2, item 4) as the Director's
    declaration shape for destruction, carried in StateDiff.destruction.
    The Director owns the causal event -- code never originates a
    destruction; commit.py only realizes a declared one
    deterministically: retire the doomed book(s) + their registered
    rooms, drop the live rooms/entities via the ordinary diff machinery,
    and mint latency-gated `news_arrival` scheduled events (one per
    `news` entry). scale 'vehicle'/'building' dooms the target's ONE
    book; scale 'region' (Phase 3b) dooms the multi-book cascade
    enumerated deterministically from the lorebook tree (parent_id
    descendants + currently_within members physically inside).
    effect_id/source_event_id are optional in the declaration (commit
    derives stable ids itself)."""
    effect_id: str = ""
    source_event_id: str = ""
    target_id: str
    scale: str
    kind: str
    severity: float = 0.0
    affected_components: list[str] = Field(default_factory=list)
    affected_locations: list[str] = Field(default_factory=list)
    immediate_facts: list[str] = Field(default_factory=list)
    persistent_conditions: list[str] = Field(default_factory=list)
    estimated_casualties: Optional[dict] = None
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    # Awareness propagation (info-barrier): destruction is objective the
    # moment it commits; who LEARNS of it is latency-gated. One entry per
    # audience scope: {audience: str, latency_seconds: float, summary: str}
    # -> one news_arrival scheduled event due at clock + latency, delivered
    # with told/heard provenance through the normal director/perception
    # path when it fires. latency_seconds may be omitted: the engine then
    # derives it from the audience's distance to the destroyed root in
    # the lorebook graph (near hears sooner -- Phase 3b,
    # mechanics.news_latency_seconds).
    news: list[dict] = Field(default_factory=list)

class Engagement(LenientModel):
    engagement_id: str
    world_id: str
    location_id: str
    scale: str
    side_ids: list[str] = Field(default_factory=list)
    participant_ids: list[str] = Field(default_factory=list)
    phase: str = "contact"
    objectives: dict[str, list[dict]] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    initiative_state: dict[str, Any] = Field(default_factory=dict)
    command_state: dict[str, Any] = Field(default_factory=dict)
    unresolved_effects: list[dict] = Field(default_factory=list)
    started_at_seconds: float = 0.0
    state: dict[str, Any] = Field(default_factory=dict)

# ---- Reactions and Perception ----

class Observation(LenientModel):
    observation_id: str
    # Defaults, not requirements: the engine's own projection
    # (agents/composer.py, OBSERVATION_DEFAULTS) omits wrapper fields at
    # their resting values -- absent means the default -- so a compacted
    # observation must validate. Old stored observations carry the full
    # shape and validate unchanged.
    perceiver_id: str = ""
    source_atom_id: str = "current"
    channel: str = "mixed"
    fidelity: str = "rendered"
    observed: dict[str, Any] = Field(default_factory=dict)
    # These three ARE composer.OBSERVATION_DEFAULTS, and must stay so. The
    # comment above says absent means the default; it said that while the two
    # sides disagreed on every axis (0.5/0.0/0.5 here against 0.35/0.1/0.15
    # there), so a compacted observation read back through this model came
    # out asserting values the compactor never wrote -- half again the
    # intensity, three times the ambiguity, no suddenness where the resting
    # value is 0.1. Restated rather than imported: `llm` may not import
    # `agents`, so `tests/test_schemas.py` holds the two level instead.
    intensity: float = Field(default=0.35, ge=0.0, le=1.0)
    suddenness: float = Field(default=0.1, ge=0.0, le=1.0)
    ambiguity: float = Field(default=0.15, ge=0.0, le=1.0)
    directed_at_self: bool = False

    # One validator per axis, because each carries its OWN resting value as
    # the fallback. A field validator runs BEFORE the inherited null
    # substitution, so the fallback is what an explicit `null` lands on while
    # omission lands on the declared default -- the two spellings of "not
    # said" have to agree, which they can only do per field.
    _clamp_intensity = validator(
        "intensity", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.35))
    _clamp_suddenness = validator(
        "suddenness", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.1))
    _clamp_ambiguity = validator(
        "ambiguity", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.15))

# ---- Establishment and Resolve ----

class CommsOp(LenientModel):
    """One change to a voice channel: a PA, an intercom, a radio, a phone.

    Endpoints are ROOMS or CARRIERS, which is the difference between a fixed
    installation and a handset that travels in a pocket. `set` is a complete
    replacement snapshot; `open`/`close` flip the switch without restating who
    is on it; `remove` takes the equipment out of the world.
    """

    _subject_field = "id"

    id: str = ""
    op: str = "set"
    name: str = ""
    rooms: list[str] = Field(default_factory=list)
    carriers: list[str] = Field(default_factory=list)
    # "duplex" both ways, "broadcast" one way from `source`.
    mode: str = "duplex"
    source: str = ""
    # True for an earpiece or a handset at an ear -- only the carrier hears it.
    # False for a speaker, which fills the room the carrier is standing in.
    private: bool = False
    live: bool = True


class PoseEntry(LenientModel):
    """One body's complete current pose snapshot.

    Declared as a MODEL rather than as a bare `dict` so the shape the prompts
    have always named is a shape the schema knows. `spatial._POSE_FIELDS` and
    `_clean_pose` have enforced exactly these six since poses existed; the
    schema said `dict` and therefore knew nothing about them, which had two
    costs. It could not tell a model that answered in the short spelling what
    the long one is -- `{"Hinami": "standing"}` was refused outright, killing
    the opening turn of a story rather than reading it as the posture it
    obviously is. And a mistyped field could not be noticed by anything.

    `_subject_field` names `posture` as the subject so that short spelling
    lands where it means: it is the only one of the six that is about the body
    ITSELF, the others being about what supports it or what it is arranged
    against. Extra keys are ignored rather than refused, as everywhere else
    here -- `_clean_pose` keeps these six regardless.
    """

    _subject_field = "posture"

    posture: str = ""
    support: str = ""
    relative_to: str = ""
    relation: str = ""
    constraint: str = ""
    detail: str = ""


class AttireState(LenientModel):
    wearing: list[str] = Field(default_factory=list)
    state: list[str] = Field(default_factory=list)
    # Clothing BY REGION, with each garment's description and what is beneath
    # it. Undeclared until now, so the opening turn's authored regions -- the
    # richest clothing detail any story ever has, straight off the cards --
    # were stripped by the validation round-trip and rebuilt from bare names.
    # Every body in every existing story lost its garment descriptions and its
    # `beneath` text on beat 0. See attire.normalize_regions for the shape.
    regions: dict[str, dict] = Field(default_factory=dict)

class InitialEntityState(LenientModel):
    posture: str = ""
    activity: str = ""
    held_items: list[str] = Field(default_factory=list)
    visible_conditions: list[str] = Field(default_factory=list)

class CrowdOp(LenientModel):
    """Director declaration about a crowd blob.

    A DECLARED field for every op, because a field that is only promised in the
    prompt is a field that silently does nothing: `character.project_ops` is
    asked for by name and dropped by validation, and "has ever held a project:
    0 of 26" is what that costs.

    `crowd_id` is a uid the engine minted and perception showed; it is never a
    display name and never model-invented. Leaving it empty on `set` is how a
    NEW crowd is asked for -- commit mints the id, the model never does.
    """
    op: str = "set"           # set | move | split | disperse | emerge | absorb
    crowd_id: str = ""
    # Who stepped out of it, or who is going back in. Never a cast member: a
    # crowd produces strangers, and someone the story already knows ARRIVES.
    who: str = ""
    room: str = ""
    band: str = ""            # a handful | a dozen or so | a few dozen | a throng
    composition: str = ""
    mood: str = ""
    heading: str = ""         # adjacent room it is flowing toward, or ""

class DirectorEstablish(LenientModel):
    location: str = ""
    time: str = "now"
    # The sky the story opens under. Same shape as StateDiff.weather; absent
    # means the engine's fair-and-still default rather than "no weather", so
    # an opening that never mentions the sky still has one to drift from.
    weather: Optional[dict] = None
    scene_description: str = ""
    rooms: dict[str, RoomDef] = Field(default_factory=dict)
    entities: dict[str, SceneEntityDef] = Field(default_factory=dict)
    positions: dict[str, str] = Field(default_factory=dict)
    # A populous opening. The establish stage AUTHORS the first scene, and
    # "the square is packed" is part of what that scene is -- but establish
    # carries no `state_diff`, so a crowd could not be declared until the
    # second beat. A story that opens in a market had to open in an empty one.
    # Found by playing turns rather than by reading code.
    crowd_ops: list[CrowdOp] = Field(default_factory=list)
    attire: dict[str, AttireState] = Field(default_factory=dict)
    entity_states: dict[str, InitialEntityState] = Field(default_factory=dict)
    # Where in each room the opening puts people: {name: {at, near:[]}}.
    stations: dict[str, dict] = Field(default_factory=dict)
    # Complete current body-pose snapshots: posture/support plus optional
    # relative body arrangement. Separate from room/station and contact.
    poses: dict[str, PoseEntry] = Field(default_factory=dict)
    # Voice channels opened, closed or installed this beat (spatial.comms).
    comms_ops: list[CommsOp] = Field(default_factory=list)
    # Holds the opening passage leaves standing -- same op shape as
    # StateDiff.contact_ops, routed into it by the establish tail so it reaches
    # spatial.apply_contact_ops through the one merge every other beat uses.
    #
    # Declared because an opening that narrates a sequence usually contains the
    # scene's only physical act, and establishment had no way to express one:
    # observed live, a greeting whose whole event was a hand seizing a wrist
    # and hauling a body through a door committed with `contacts: []`, so the
    # grab had never happened and the body it moved had never been anywhere
    # else. Prose is not state; if the hold is still true when play begins it
    # has to arrive as an op.
    contact_ops: list[dict] = Field(default_factory=list)
    # Non-discrete matter the opening leaves located on/within something.
    # Separate from contact (bodies touching) and inventory (discrete objects).
    substance_ops: list[dict] = Field(default_factory=list)
    sensory_events: list[dict] = Field(default_factory=list)
    world_facts: list = Field(default_factory=list)
    opening: str = ""
    fiction_frame: dict[str, Any] = Field(default_factory=dict)
    simulation_clock: dict[str, Any] = Field(default_factory=dict)
    # World-pressure openers (F5): scenario objects/processes established
    # with authored threat/escalation potential register on the ledger from
    # beat 0 -- {op:'open', subject, note}. Applied deterministically by
    # commit.py's commit_world_pressure.
    world_pressure: list[dict] = Field(default_factory=list)

    _coerce_stations = validator("stations", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_station_table(v)
    )

class AttireDiff(LenientModel):
    """One body's clothing change, in whatever shape it arrived.

    `StateDiff.attire` was `dict[str, dict]` -- untyped inside -- and commit's
    loop reads exactly the fields below. Anything else validated cleanly and
    was then silently discarded, which is not the lenient behaviour this
    module's charter asks for: a near-miss shape should be READ, not dropped
    and not fatal. `notes` is where an unrecognised key lands so commit can
    resolve its handle against the wardrobe (attire.coerce_diff_shape).
    """
    wearing: Optional[list[str]] = None
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)
    replace: Optional[list[str]] = None
    state: Optional[list[str]] = None
    conditions: dict[str, str] = Field(default_factory=dict)
    # A still-worn garment may expose part of a coarse region without being
    # removed: {garment_handle: {torso: [chest]}} means it still covers the
    # chest and exposes the midriff. The vocabulary is validated in attire.py
    # so legacy/near-miss model output can degrade fieldwise rather than abort.
    coverage: dict = Field(default_factory=dict)
    # Authored clothing by region -- the opening turn's shape, carrying each
    # garment's description and what is beneath it.
    regions: dict[str, dict] = Field(default_factory=dict)
    # {garment handle or free key: what the beat said about it}
    notes: dict[str, str] = Field(default_factory=dict)

    # A whole-model before-validator, which is the one case LenientModel's
    # docstring argues AGAINST -- and the exception is deliberate. The
    # reshaping here is between KEYS, not within a field's value: it has to see
    # the whole object to know that an unrecognised key is a note rather than a
    # typo. No field validator can be handed that.
    if _PYDANTIC_V2:
        from pydantic import model_validator as _model_validator

        _canonicalize = _model_validator(mode="before")(
            classmethod(lambda cls, value: _coerce_attire_diff(value)))
    else:
        from pydantic import root_validator as _root_validator

        _canonicalize = _root_validator(pre=True, allow_reuse=True)(
            lambda cls, value: _coerce_attire_diff(value))

class DialogueLogEntry(LenientModel):
    speaker: str
    exact_quote: str
    volume: SpeechVolume = SpeechVolume.normal

    _norm_volume = validator("volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )
    intended_target: Optional[str] = None
    tone: str = ""
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)
    # How the sound was FORMED -- the sibling of volume, which is how loud it
    # was made. NOT a model-authored field: the reconciliation seam stamps it
    # deterministically from the contact ledger (and clears it), so a value
    # the model invents never survives. It lives in the schema so that any
    # re-validation of a stamped log cannot silently strip it.
    articulation: str = ""

    _norm_articulation = validator(
        "articulation", pre=True, allow_reuse=True)(
        lambda cls, v: v if v in ("slurred", "stifled") else "")

class BackgroundReactOutput(LenientModel):
    reacts: bool = False
    dialogue_log_entry: Optional[DialogueLogEntry] = None
    action: str = ""

class SceneLifeEntry(LenientModel):
    """One managed presence's conduct for this beat, attributed by name so the
    commit-side append is a ROUTING operation rather than an authoring one
    (docs/design/BACKGROUND_LIFE_DESIGN.md §3.11)."""
    name: str
    speech: Optional[DialogueLogEntry] = None
    action: str = ""
    # Proper nouns / world facts this entry introduces that the beat did not
    # already establish. Self-declared so they can be recorded as CLAIMS rather
    # than silently entering canon (background_claims.py); a deterministic
    # novel-proper-noun scan backstops omissions.
    asserts: list[str] = Field(default_factory=list)

class SceneLifeOutput(LenientModel):
    entries: list[SceneLifeEntry] = Field(default_factory=list)

#: What a tracked presence turns out to BE, answered once and frozen with the
#: blurb. `""` means the pass did not say, which every caller must treat as
#: "undecided" rather than as "person" -- the whole defect this field closes was
#: an unanswered question being read as a yes.
PRESENCE_NATURES = ("person", "thing", "voice")


class BlurbMintEntry(LenientModel):
    """A frozen personality blurb (§3.8). Surface only -- manner, a standing
    concern, a repeatable tic -- never private goals or beliefs about others.

    `nature` is not decoration and not a personality field. The blurb pass is
    the ONE moment the engine already looks at a newly tracked presence with
    its place, the Director's description of it and the story's genre in front
    of a model -- so it is the moment to settle what the thing IS, at no extra
    call. Everything else that asked ("is `device` an animate kind?") was
    trying to derive animacy from a noun the model chose in passing, which is
    an enumeration treadmill: `_INERT_ENTITY_KINDS` reached 50 entries and
    `_ANIMATE_ENTITY_KINDS` 35, and a kind string still cannot separate a
    suppression device from a dalek war machine.
    """
    name: str
    manner: str = ""
    trait: str = ""
    tell: str = ""
    look: str = ""
    nature: str = ""

    _nature = validator("nature", pre=True, allow_reuse=True)(
        lambda cls, value: (
            str(value or "").strip().casefold()
            if str(value or "").strip().casefold() in PRESENCE_NATURES else ""))

class BackdropPromptOutput(LenientModel):
    prompt: str = ""

class BlurbMintOutput(LenientModel):
    blurbs: list[BlurbMintEntry] = Field(default_factory=list)


class OffscreenPlanTrigger(LenientModel):
    """One deterministic condition for an authored off-screen plan stage.

    Exactly one trigger kind survives commit normalization: relative story
    time, or a fired mechanical event kind optionally narrowed to a location.
    Open strings here are intentional input tolerance; `offscreen.py` owns the
    closed write vocabulary and refuses ambiguity before persistence.
    """
    after_seconds: Optional[float] = None
    event_kind: str = ""
    location: str = ""


class OffscreenPlanEffect(LenientModel):
    """A consequence adjudicated now and fired later without invention."""
    what: str = ""
    where: str = ""
    due_seconds: Optional[float] = None
    witnessed: str = ""
    originator: str = ""


class OffscreenPlanStage(LenientModel):
    stage_id: str = ""
    trigger: OffscreenPlanTrigger = Field(default_factory=OffscreenPlanTrigger)
    effect: Optional[OffscreenPlanEffect] = None


class OffscreenPlanOp(LenientModel):
    """Director encoding of a character-owned declaration.

    `basis` must quote/paraphrase that actor's declaration from this beat;
    commit validates the attribution before a plan can exist. The Director
    adjudicates stages/effects but cannot invent an absent mind's objective.
    """
    op: str = "open"
    plan_id: str = ""
    actor: str = ""
    objective: str = ""
    basis: str = ""
    stages: list[OffscreenPlanStage] = Field(default_factory=list)

class TellingOp(LenientModel):
    """One character passing a carried report to another, on-page.

    An explicit COPY. Standing beside someone who knows a thing teaches you
    nothing -- if the engine let proximity transfer knowledge it would have
    rebuilt the omniscience the whole perception layer exists to prevent.
    Commit refuses the op unless the speaker actually holds that report, spoke
    this beat, and shares a room with the listener; the copy then arrives one
    retelling fainter through `degradation`.
    """
    speaker: str = ""
    listener: str = ""
    world_event_id: str = ""
    # Set INSTEAD of world_event_id when the speaker is saying something no
    # event backs: a lie, a boast, an honest mistake. It enters through the
    # same carrier physics as the truth and is indistinguishable downstream --
    # a mind that could tell a lie from a fact by inspecting its own memory is
    # not a mind that can be deceived. The speaker's own row records that they
    # made it up; nothing a listener can reach ever says so.
    claim: str = ""


class CourierOp(LenientModel):
    """Director declaration about a courier -- a message with a body.

    `send` puts a report a registered SENDER actually holds onto a rider who
    departs from the room the sender's body is in, along a passable route the
    engine computes; the model never invents the route and never names the
    courier -- `courier_id` is an engine-minted uid perception showed, exactly
    like a crowd's. `question` and `silence` are the interception seam: both
    are refused unless the named body is in the room the courier is actually
    in, because a route is cut where the rider rides.
    """
    op: str = "send"          # send | question | silence
    courier_id: str = ""      # engine-minted uid; required for question/silence
    sender: str = ""          # registered character whose hands it starts in
    to_room: str = ""         # destination room id (send)
    addressee: str = ""       # optional: deliver only to this character, in person
    world_event_id: str = ""  # a report the sender holds...
    claim: str = ""           # ...or a claim no event backs (a lie rides too)
    method: str = "word"      # word (retold, degrades) | letter (sealed, verbatim)
    # riding | walking. Empty lets the engine choose the kind's own default
    # (a rider rides, a caravan walks); a filled-in schema default here would
    # put every unspecified caravan on horseback.
    pace: str = ""
    description: str = ""     # what an observer sees: "a rider", "a boy with a satchel"
    listener: str = ""        # question: who hears it; silence: who takes what he carried
    by: str = ""              # silence: whose body stops him
    # Non-empty stops make the send a CARAVAN: it dwells at each listed room
    # (charged in simulation time), tells the standing crowd what it carries
    # and picks up what stands there -- talk, public surfaces, posted bills
    # -- degrading at each mouth exactly as a telling does. A caravan may
    # carry nothing at dispatch; then no sender is needed and `from_room`
    # names the known room it forms in (the crowd-minting precedent).
    stops: list[str] = Field(default_factory=list)
    from_room: str = ""       # caravan with no sender and no message: where it forms


class ArtifactOp(LenientModel):
    """Director declaration about a physical notice -- a claim on a wall.

    `post` nails up what a registered POSTER actually holds (or a `claim`
    they are inventing, which lands on their own row exactly as a spoken lie
    does), in the room the poster's body is in. `read` is how a mind
    acquires it -- verbatim, provenance `read`, because a copy is not a
    mouth -- and `remove` tears it down, after which it informs nobody:
    the artifact equivalent of silencing a courier. `artifact_id` is an
    engine-minted uid perception showed, exactly like a courier's.
    """
    op: str = "post"          # post | read | remove
    artifact_id: str = ""     # engine-minted uid; required for read/remove
    poster: str = ""          # post: registered character whose hands nail it up
    room: str = ""            # post: optional; must be the poster's own room
    world_event_id: str = ""  # a report the poster holds...
    claim: str = ""           # ...or a claim no event backs (a false bill posts too)
    description: str = ""     # what an observer sees: "a wanted bill nailed to the post"
    reader: str = ""          # read: whose eyes take it in
    by: str = ""              # remove: whose hands tear it down
    manner: str = ""          # remove: optional -- "torn down", "defaced"


class StateDiff(LenientModel):
    positions: dict[str, str] = Field(default_factory=dict)
    rooms: dict[str, RoomDef] = Field(default_factory=dict)
    entities: dict[str, SceneEntityDef] = Field(default_factory=dict)
    remove_entities: list[str] = Field(default_factory=list)
    remove_rooms: list[str] = Field(default_factory=list)
    remove_adjacent: list[dict] = Field(default_factory=list)
    conditions: dict[str, list[dict]] = Field(default_factory=dict)
    inventory_ops: list[dict] = Field(default_factory=list)
    # Body position tracking. Contact is a RELATION, so it is not stored on
    # either body: these ops maintain the scene-level `contacts` list
    # (spatial.apply_contact_ops), and spatial.normalize_scene_contacts prunes
    # whatever positions no longer permit. {op: add|remove|clear|cross, actor,
    # actor_part, target, target_interior, target_part, crossed_target_part,
    # manner, relation, motion}. `target_interior` is the enclosing structure;
    # `target_part` is the current endpoint. `crossed_target_part` is transient
    # evidence used only by a validated cross transition. Contact
    # topology (`surface|interior`) and kinematics (`settled|moving`) are
    # independent: an interior contact may be moving.
    contact_ops: list[dict] = Field(default_factory=list)
    # Physical matter transferred and left somewhere after the beat.
    # {op:add|release|deposit|remove|clear, source, source_part, substance,
    # target, placement:surface|interior|contained|room, target_interior,
    # target_part, amount, detail, scent, substance_id?}.  A release from the
    # acting part of a unique standing interior contact derives its
    # destination from that topology; the model names the matter, never the
    # code. `scent` is what the matter smells of and is why this ledger, not
    # a parallel one, carries the commonest smell in play.
    substance_ops: list[dict] = Field(default_factory=list)
    # Actor-owned following changes, projected deterministically from the
    # player interpretation and character decisions. The resolve model does
    # not author these. {op:start|stop,follower,target?,reason?,turn?}.
    following_ops: list[dict] = Field(default_factory=list)
    # Within-room position: {name: {at: anchor_id|None, near: [names]}}. The
    # sibling of `positions` at the grain below the room -- at the bed, at the
    # hearth, beside each other. Undeclared until now, and that omission was
    # the whole feature: prompts.py has asked the Director for this since
    # Phase 2, spatial.merge_scene_with_diff has always merged it, and 0 of 45
    # live scenes contain one, because the round-trip dropped the field before
    # anything downstream could see it. Without a station every co-located
    # pair reads `near`, so someone across a great hall and someone in your
    # arms are the same distance.
    #
    # NOT a typed sub-model -- see _coerce_station_table for why the partial
    # merge and the explicit `at: null` both require the plain dict.
    stations: dict[str, dict] = Field(default_factory=dict)
    # Complete replacement snapshots for touched bodies:
    # {name:{posture,support,relative_to,relation,constraint,detail}}.
    # Open strings keep fictional embodiment genre-neutral.
    poses: dict[str, PoseEntry] = Field(default_factory=dict)
    # Voice channels opened, closed or installed this beat (spatial.comms).
    comms_ops: list[CommsOp] = Field(default_factory=list)
    # Scale: {name: factor} relative to that body's own baseline. 1.0 (or
    # omission) is normal size; the engine cancels contacts on a body whose
    # size changed, since a hold is a fact about two bodies at the sizes they
    # were (spatial.contacts_broken_by_scale_change).
    scales: dict[str, float] = Field(default_factory=dict)
    # Containment: {subject: {"in": holder, "mode": ...}}, or a null value to
    # release. A contained body's position is DERIVED from its container's
    # (spatial.derive_contained_positions), so it cannot be somewhere else.
    containment: dict[str, Optional[dict]] = Field(default_factory=dict)
    # Bodily condition {name: {air|stamina|nourishment|injury: 0..1}}. Only
    # ever populated when the survival setting is ON; absent otherwise, which
    # is what keeps the feature free for stories that do not want it.
    vitals: dict[str, Optional[dict]] = Field(default_factory=dict)
    overlays: dict[str, list] = Field(default_factory=dict)
    attire: dict[str, AttireDiff] = Field(default_factory=dict)
    # Who entered or left the story's live cast. {who, status, reason}, with
    # status ∈ active|dormant -- `active` is in the scene, `dormant` is out of
    # it (the roster `offscreen.py` simulates). A free string on an untyped
    # entry, so the commit normalizes the natural words a model reaches for
    # ("departed", "arrived") onto those two and WARNS on anything else rather
    # than dropping it; see `scene.cast_change_status`.
    cast_changes: list[dict] = Field(default_factory=list)
    world_facts: list = Field(default_factory=list)
    introductions: list[dict] = Field(default_factory=list)
    # Names/details a background presence asserted on an earlier beat that this
    # resolution ADOPTS as true (background_claims.py). Ratifying is the
    # Director's alone -- an unratified claim stays hearsay and expires.
    ratified_claims: list[str] = Field(default_factory=list)
    # ...and the ones this resolution REJECTS. Explicit, because contradiction
    # is the one verdict prose cannot carry: "the Widow denies it" and "the
    # Widow says it again" share every distinctive token, so settle_claims can
    # infer adoption from the objective record but never rejection. Without
    # this list a claim the Director threw out was indistinguishable from one
    # it ignored, and went on being offered back to it until the TTL ran out.
    contradicted_claims: list[str] = Field(default_factory=list)
    # Top-level place label, set only when the beat relocates the party to a
    # genuinely different place (DW-1). commit.py's _refresh_relocated_location
    # prefers this over the new room's own name.
    location: str = ""
    time: Optional[dict] = None
    # One sky over the whole scene: {sky, precipitation, intensity, wind,
    # temperature}, normalized to a closed vocabulary by weather.py. Emitted
    # only when a beat actually changes it -- absent means "unchanged", and
    # between Director edits the sky drifts deterministically on the
    # simulation clock (weather.advance_weather). How much of it any given
    # room gets is a property of the ROOM (`RoomDef.exposure`), never of this.
    weather: Optional[dict] = None
    claim_dispositions: list[dict] = Field(default_factory=list)
    # Living world, approach B: consequences this resolution sets in motion
    # OFFSCREEN, minted as fuses at cause time and fired deterministically
    # when the simulation clock reaches them. {what, where, due_seconds,
    # witnessed?, originator?}. NOT this beat's own outcome -- that belongs
    # in the fields above. Commit validates deterministically
    # (living_world.mint_consequences): `where` must resolve to a known
    # room or lore place, dues are clamped to honest bounds, at most 2 land
    # per turn, and the whole lane is inert unless the chat's living-world
    # setting turned it on.
    consequences: list[dict] = Field(default_factory=list)
    # Living world E, reactive floor. These are plans explicitly declared by
    # a character THIS beat and adjudicated into bounded deterministic stages
    # by the Director. Commit requires a grounded `basis`, a registered actor,
    # the antagonist-ladder floor setting, and typed time/event triggers.
    # `open` creates; `cancel` ends an existing plan owned by that actor.
    offscreen_plan_ops: list[OffscreenPlanOp] = Field(default_factory=list)
    # Crowd blobs: one object with many people in it. A populous place cannot
    # be represented by managed presences -- `max_managed` is hard-capped at 8
    # and chat 57 spent three of six slots on ONE Dalek -- so a crowd is a
    # single row that costs the same whatever it holds and NEVER takes a
    # managed slot. Commit validates deterministically (crowds.apply_ops):
    # rooms must exist, a `crowd_id` the engine did not mint is refused rather
    # than created, and the count is a band rather than an integer so two
    # sources can never disagree about whether 37 became 34.
    crowd_ops: list[CrowdOp] = Field(default_factory=list)
    # Who passed a carried report to whom, this beat, on-page. The only way a
    # report reaches a second mind: `carriers.apply_tellings` validates the
    # holding, the speaking and the shared room deterministically, and the
    # copy degrades by subtraction so a rumor can be vaguer but never
    # different -- distortion that cannot invent cannot contradict.
    telling_ops: list[TellingOp] = Field(default_factory=list)
    # Couriers: a carried report put on a body with a position and a route,
    # so distance costs time and the player can intercept, follow, question,
    # outrun or silence the road. Commit validates deterministically
    # (couriers.run_couriers): the sender must hold the report, the route
    # must be walkable, and nobody interferes from a room they are not in.
    # A CourierOp with stops is a caravan -- same body, same road, plus
    # dwelling and two-way news at each stop.
    courier_ops: list[CourierOp] = Field(default_factory=list)
    # Artifacts: a claim made physical -- a notice, a proclamation, a wanted
    # bill standing in a room, acquired by reading and stopped by tearing
    # down. Commit validates deterministically (artifacts.run_artifacts):
    # the poster must hold what the bill asserts, the bill goes up where
    # the poster stands, and reading happens in front of the wall.
    artifact_ops: list[ArtifactOp] = Field(default_factory=list)
    # Destruction declaration (DestructionEffect shape -- see its
    # docstring). Declared here so model_dump() keeps it through
    # validation (the zone-field precedent above); commit.py validates it
    # deterministically: one vehicle/building, or a 'region' whose
    # multi-book cascade commit.py enumerates from the lorebook tree.
    destruction: Optional[dict] = None

    _coerce_stations = validator("stations", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_station_table(v)
    )
    _coerce_list_maps = validator("overlays", "conditions", pre=True,
                                  allow_reuse=True)(
        lambda cls, v: _coerce_list_valued_map(v)
    )


# `DirectorInterpret.state_assertions` is a `StateDiff` -- interpret is not a
# lesser authority than resolve, it is the same authority scoped to the
# player's input -- and it is declared above this class, so the forward
# reference is resolved here.
DirectorInterpret.update_forward_refs()


class OmittedThought(LenientModel):
    """One inner event the resolve deliberately kept OUT of the manifest.

    THIS LEDGER NEVER COMMITS. Nothing here reaches objective state, no
    channel reads it, and no specialist is handed it -- a thought is not a
    change to the world and has no ledger to carry it. Its only job is to
    say so out loud, so the seams that watch for a beat which narrated
    something and encoded nothing can tell "this beat was interior" from
    "this beat lost its changes". Before it existed, those two looked
    identical, and the honest interior beat tripped the same alarm as the
    broken physical one.
    """
    subject: str = ""   # whose interior it was
    thought: str = ""   # one short phrase; never rendered to a player


class AssertedChange(LenientModel):
    """One entry of director_resolve's own changes-asserted manifest: a
    persistent physical change its resolved_event asserts as completed,
    beyond the player's supplied authority_claims. Reconciled against the
    state_diff deterministically (see agents/director.py's seam)."""
    # rooms|adjacency|positions|entities|conditions|attire|contact|substance|inventory|
    # cast_changes|time|transit|other
    category: str = "other"
    # Assigned by the engine in _manifest_items, never by the model: 1..N in
    # the order the resolve narrated the changes, which is the beat's own
    # chronology. Carried into each specialist's manifest slice and echoed
    # back on its resolved_events, so composition is an id lookup rather
    # than a comparison of two spellings of the same change (design note 21).
    event_id: int = 0
    subject: str = ""         # room id / entity id / character name concerned
    change: str = ""          # one short sentence stating the persistent change
    # Contact manifests need the relation's endpoints, not merely one person.
    # Without them, two simultaneous contacts involving the same actor are
    # indistinguishable: a correctly encoded hand-on-hip could falsely prove a
    # separately asserted nozzle-to-valve contact was also encoded. Optional for
    # every non-contact category and for compatibility with saved variants.
    actor: str = ""
    actor_part: str = ""
    target: str = ""
    target_part: str = ""
    substance: str = ""
    placement: str = ""
    target_interior: str = ""

class DirectorResolve(LenientModel):
    resolved_event: str = ""
    summary: str = ""
    dialogue_order: list[str] = Field(default_factory=list)
    dialogue_log: list[DialogueLogEntry] = Field(default_factory=list)
    state_diff: StateDiff = Field(default_factory=StateDiff)
    changes_asserted: list[AssertedChange] = Field(default_factory=list)
    # The manifest's counterpart: what the beat deliberately did NOT list,
    # because it was interior. Never committed, never perceived, never
    # handed to a specialist -- it exists so an honestly interior beat
    # stops reading like a beat that lost its changes (schemas.OmittedThought).
    thoughts_omitted: list[OmittedThought] = Field(default_factory=list)
    # DECLARED BUT NO LONGER REQUESTED. The resolve prompt used to ask the
    # model for both of these and neither answer was ever read: the engine
    # rolls the dice itself from the interpret flow's DiceSpec under a
    # deterministic seed and overwrites this field wholesale
    # (agents/director.py's `out["dice"] = dice`, after validation), and no
    # reader anywhere touches the resolve-side `fiction_frame` -- the payload
    # builder reads the INTERPRET flow's copy. So the model was paying tokens
    # every beat to transcribe one field that is discarded and echo another
    # that nothing consumes.
    #
    # The fields stay DECLARED because LenientModel's round-trip drops
    # undeclared keys: persisted variants, portable archives and pipeline
    # traces all carry historical values, and `dice` is still where the engine
    # writes its own roll. Removing the ASK is free; removing the FIELD would
    # silently discard that history.
    dice: list[dict] = Field(default_factory=list)
    claim_dispositions: list[dict] = Field(default_factory=list)
    fiction_frame: dict[str, Any] = Field(default_factory=dict)
    # Obligation-ledger ops: {op:'open'|'discharge'|'refuse', id, who, what,
    # kind}. Applied deterministically to the world-KV pending_obligations
    # ledger by commit.py's commit_obligations (mirrors standing_intentions).
    obligations: list[dict] = Field(default_factory=list)
    # World-pressure ops (F5 -- THE WORLD ACTS): {op:'open'|'tick'|'hold'|
    # 'resolve', id, subject, note}. Every open pressure on the world-KV
    # world_pressures ledger must be ticked or explicitly held each resolve;
    # commit.py's commit_world_pressure applies the ops deterministically and
    # treats silence as an implicit hold WITH a warning, so an inert world is
    # always a visible choice, never a default (Enterprise: the Array).
    world_pressure: list[dict] = Field(default_factory=list)
    # Player-asserted plot-fact verdicts: {claim_id, claim, subject,
    # verdict:'confirmed'|'contested'|'false', landing}. Audited
    # deterministically in agents/director.py (_audit_fact_adjudications).
    fact_adjudications: list[dict] = Field(default_factory=list)
    # A walk somebody declared once and this beat did not mention CONTINUES
    # (agents/director._travel_continues) -- people talk while they walk, and
    # making travel survive only by being re-declared every beat is the
    # sentence nobody wants to keep writing. So an interruption is the thing
    # that has to be asserted, and this is where the Director asserts it:
    # {subject, reason}. "Did what just happened stop you walking" is
    # objective causality and needs the whole beat to answer, which makes it
    # exactly this stage's call -- and a structured field rather than a prose
    # inference, because prose matching is the boundary this engine exists to
    # stay on the right side of. A deterministic floor (no passable route,
    # carried, already there, restrained) holds a walk regardless of what is
    # said here; this field can only ever STOP a walk, never start one.
    travel_interrupted: list[dict] = Field(default_factory=list)
    # ENGINE-AUTHORED, never written by the model: what the continuation
    # actually did this beat ({advanced, arrived, interrupted, held}).
    # commit.py reads it to retire or keep each standing approach record, so
    # the ledger and the position cannot disagree about who is still under
    # way. Declared for the same reason `following_ops` is -- LenientModel
    # drops undeclared keys on the round trip, and this has to survive into
    # the persisted variant the pipeline drawer and a resume read back.
    travel: dict[str, Any] = Field(default_factory=dict)
    # ENGINE-AUTHORED, never written by the model (same contract as
    # `following_ops` above). Background presences whose Director-written line
    # was removed so the background stage can voice them properly; read by
    # commit.pick_background_reactors as a forced pick. Declared here because
    # the schema dump drops unknown keys, which would have silently discarded
    # the hand-off and turned a re-homed line into a deleted one.
    routed_to_background: list[str] = Field(default_factory=list)
    # ENGINE-AUTHORED (same contract as routed_to_background): the orchestrated
    # Director's dispatch record -- which specialists this beat ran, the scene
    # facts the gate read, and what assembly replaced (design note 19). Empty
    # on every monolithic resolve, so stored pre-orchestration variants are
    # unchanged. Declared so the round-trip keeps the record inspectable.
    orchestration: dict[str, Any] = Field(default_factory=dict)


def _manifest_event_number(value):
    """The integer a specialist MEANT when it echoed a manifest event number.

    `resolved_events[].event_id` is assigned by the engine -- 1..N in the order
    the resolve narrated the beat -- and echoed back by each specialist so
    composition is an id lookup rather than a comparison of two spellings. The
    echo is where it goes wrong: models return the number as "1", "#1", "E1",
    "event 1" or "1.", and only the bare digits validate. That rejection is not
    cheap. It fails the whole call and buys a repair round trip, and across the
    live corpus this ONE field accounts for 8 of 17 validation failures -- 47%
    of every repair call the engine has made.

    Nothing is invented. A value carrying exactly ONE run of digits resolves to
    that run; anything else -- no digits, or two of them ("1,2"), where the
    model's intent is genuinely unclear -- is passed through untouched and
    fails exactly as it did before.
    """
    if isinstance(value, bool) or isinstance(value, int):
        return value
    if not isinstance(value, str):
        return value
    runs = re.findall(r"\d+", value)
    if len(runs) != 1:
        return value
    try:
        return int(runs[0])
    except ValueError:
        return value


class ResolvedEvent(LenientModel):
    """One specialist's verdict on ONE numbered beat event (design note 21).

    The manifest a specialist receives is numbered in the order the resolve
    narrated it, and the specialist echoes each id back with what it did.
    That echo is what makes coverage a LOOKUP instead of a text comparison:
    before it existed, an event was matched to its encoding by comparing
    free-text subject wording, and every measured reconciliation failure was
    that comparison going wrong in a new way -- a manifest naming the
    garment against a diff keyed on the wearer, "prior hand-to-stomach
    contact" against the contact_ops that ended exactly that relation.

    The echo is EVIDENCE, never authority. `encoded` is still checked
    against the merged diff by _evidence_present, because model output is
    provisional until deterministic code validates it. What the echo buys
    is knowing an event was ASKED ABOUT by the mind that owns it, which is
    what makes a second LLM call pointless -- the measured waste was asking
    a specialist to repair a change it had already correctly declined to
    re-encode.
    """
    event_id: int = 0
    _coerce_event_id = validator("event_id", pre=True, allow_reuse=True)(
        _manifest_event_number)
    # encoded      -- I put this in my channels this beat
    # already_true -- standing state carries it; no delta is correct
    # not_mine     -- it needs a channel I was not granted
    status: str = ""
    # WITH `not_mine` ONLY: which hand this belongs to instead. The
    # specialists already knew -- "no posture channel available", "this is a
    # bodily action/pose change" -- and said it in free-text notes nothing
    # read, while the repair tier re-asked the SAME hand that had just
    # declined it, by category. An address turns a complaint into a
    # forwarding note. It is a PROPOSAL: the engine decides whether to act
    # on it, because who gets called is a cross-channel judgment and those
    # stay with the deterministic orchestrator.
    reroute_to: str = ""


class DirectorBodySpecialist(LenientModel):
    """The body specialist's whole output: the four state_diff channels it
    owns under the orchestrated Director (design note 19), in exactly the
    shapes StateDiff declares for them, so assembly can move each channel
    into the resolve diff without a second spelling of any coercion.
    `notes` is the specialist's own flag lane for a bodily change the prose
    asserts that it could not encode -- including one in a channel outside
    this call's granted scope, which is how scope under-grant surfaces."""
    attire: dict[str, AttireDiff] = Field(default_factory=dict)
    conditions: dict[str, list[dict]] = Field(default_factory=dict)
    vitals: dict[str, Optional[dict]] = Field(default_factory=dict)
    overlays: dict[str, list] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    # The numbered manifest slice this call was handed, echoed back
    # with a verdict per event (schemas.ResolvedEvent).
    resolved_events: list[ResolvedEvent] = Field(default_factory=list)

    _coerce_list_maps = validator("overlays", "conditions", pre=True,
                                  allow_reuse=True)(
        lambda cls, v: _coerce_list_valued_map(v)
    )


class DirectorSocialSpecialist(LenientModel):
    """The social-fabric specialist: scene roster and record channels, in
    StateDiff's own shapes (same contract as DirectorBodySpecialist).
    `following_ops` is deliberately NOT here: following is actor-owned and
    engine-projected (`_collect_following_ops`), so no model authors it."""
    cast_changes: list[dict] = Field(default_factory=list)
    introductions: list[dict] = Field(default_factory=list)
    world_facts: list = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # The numbered manifest slice this call was handed, echoed back
    # with a verdict per event (schemas.ResolvedEvent).
    resolved_events: list[ResolvedEvent] = Field(default_factory=list)


class DirectorContactSpecialist(LenientModel):
    """The contact-and-matter specialist: the physical-relation channels,
    in StateDiff's own shapes (same contract as DirectorBodySpecialist)."""
    contact_ops: list[dict] = Field(default_factory=list)
    substance_ops: list[dict] = Field(default_factory=list)
    containment: dict[str, Optional[dict]] = Field(default_factory=dict)
    scales: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    # The numbered manifest slice this call was handed, echoed back
    # with a verdict per event (schemas.ResolvedEvent).
    resolved_events: list[ResolvedEvent] = Field(default_factory=list)


class DirectorObjectsSpecialist(LenientModel):
    """The object-world specialist: the object ledgers, in StateDiff's own
    shapes (same contract as DirectorBodySpecialist)."""
    entities: dict[str, SceneEntityDef] = Field(default_factory=dict)
    remove_entities: list[str] = Field(default_factory=list)
    inventory_ops: list[dict] = Field(default_factory=list)
    artifact_ops: list[ArtifactOp] = Field(default_factory=list)
    destruction: Optional[dict] = None
    notes: list[str] = Field(default_factory=list)
    # The numbered manifest slice this call was handed, echoed back
    # with a verdict per event (schemas.ResolvedEvent).
    resolved_events: list[ResolvedEvent] = Field(default_factory=list)


class DirectorSpatialSpecialist(LenientModel):
    """The spatial specialist: the geography channels, in StateDiff's own
    shapes (same contract as DirectorBodySpecialist). The movement backstop
    stays with the orchestrator and validates the MERGED diff -- this model
    proposes relocations, it never has the last word on them."""
    positions: dict[str, str] = Field(default_factory=dict)
    rooms: dict[str, RoomDef] = Field(default_factory=dict)
    remove_rooms: list[str] = Field(default_factory=list)
    remove_adjacent: list[dict] = Field(default_factory=list)
    stations: dict[str, dict] = Field(default_factory=dict)
    poses: dict[str, PoseEntry] = Field(default_factory=dict)
    # Voice channels opened, closed or installed this beat (spatial.comms).
    comms_ops: list[CommsOp] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # The numbered manifest slice this call was handed, echoed back
    # with a verdict per event (schemas.ResolvedEvent).
    resolved_events: list[ResolvedEvent] = Field(default_factory=list)

    _coerce_stations = validator("stations", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_station_table(v)
    )


class DirectorOffscreenSpecialist(LenientModel):
    """The world-traffic specialist: crowds, couriers, tellings, offscreen
    plans and the hearsay verdict, in StateDiff's own shapes (same contract
    as DirectorBodySpecialist). This is the OPS surface only -- the
    offscreen SIMULATOR (design note 19's out-of-band parallel) remains
    unbuilt, and nothing here schedules or simulates anything."""
    crowd_ops: list[CrowdOp] = Field(default_factory=list)
    courier_ops: list[CourierOp] = Field(default_factory=list)
    telling_ops: list[TellingOp] = Field(default_factory=list)
    offscreen_plan_ops: list[OffscreenPlanOp] = Field(default_factory=list)
    ratified_claims: list[str] = Field(default_factory=list)
    contradicted_claims: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # The numbered manifest slice this call was handed, echoed back
    # with a verdict per event (schemas.ResolvedEvent).
    resolved_events: list[ResolvedEvent] = Field(default_factory=list)

# ---- Resolve reconciliation (agents/director.py's post-resolve seam) ----

class ReconcileOmission(LenientModel):
    """One persistent, physically consequential change asserted as completed
    in resolved_event prose but not encoded anywhere in the state_diff."""
    category: str = "other"   # rooms|adjacency|positions|entities|conditions|attire|contact|inventory|cast_changes|time|other
    subject: str = ""         # room id / entity id / character name concerned
    change: str = ""          # one short sentence stating the persistent change
    evidence: str = ""        # short verbatim quote from resolved_event
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    _clamp_confidence = validator("confidence", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.5)
    )

class ResolveReconcileOutput(LenientModel):
    omissions: list[ReconcileOmission] = Field(default_factory=list)
    notes: str = ""

class ResolveRepairOutput(LenientModel):
    """The Director's own correction delta: a state_diff containing ONLY the
    entries needed to encode the detected omissions (merged additively over
    the original diff by deterministic code -- never applied wholesale)."""
    state_diff: StateDiff = Field(default_factory=StateDiff)
    dispositions: list[dict] = Field(default_factory=list)

class InterpretRepairOutput(LenientModel):
    """The Director's own interpret-side correction delta (the structural
    twin of ResolveRepairOutput, for the seam that runs right after
    director_interpret): ONLY the additional sequence elements / movement /
    generation_requests needed to capture the player declarations the
    original interpretation dropped. Merged ADDITIVELY by deterministic
    code -- existing sequence elements and a declared movement are never
    replaced."""
    sequence: list[dict] = Field(default_factory=list)
    movement: Optional[MovementDecl] = None
    mapping_request: str = ""
    generation_requests: list[dict] = Field(default_factory=list)
    dispositions: list[dict] = Field(default_factory=list)
    notes: str = ""

class NarratorOutput(LenientModel):
    prose: str = ""
    new_specifics: list[str] = Field(default_factory=list)
    text: str = ""
    #: Engine-written, never asked of the model: how many elements arrived in
    #: `paragraphs` before preprocess joined and dropped them. Declared so it
    #: survives validation into the stored variant, where it is the only way
    #: to tell "the model ignored the array" (0) from "the model used the
    #: array and wrote one element" (1). See preprocess_llm_output.
    paragraph_count: int = 0

# ---- Character Output ----


def _evidence_slot(text):
    """Which EvidenceRef field a bare piece of evidence belongs in.

    A token that looks like an id ("current", "turn:12:...") lands on
    `event_id`; anything else is prose and lands on `fact`.
    """
    text = str(text or "").strip()
    if not text:
        return {}
    looks_like_id = bool(re.fullmatch(r"[\w:.\-]+", text)) and " " not in text
    return {"event_id": text} if looks_like_id else {"fact": text}


def _coerce_evidence_refs(value):
    """Accept a bare string where an EvidenceRef was expected.

    Models routinely cite evidence as a list of strings rather than objects
    ("the sound from the east corridor"), and because BOTH EvidenceRef fields
    have defaults, the object form carries no information a string cannot --
    so rejecting it threw away a whole valid character turn over shape alone.
    Observed live: a character step failed validation with three
    `observations_used.N: value is not a valid dict`, which in an unattended
    run aborts the beat entirely.

    A token that looks like an id ("current", "turn:12:...") lands on
    `event_id`; anything else is prose and lands on `fact`.

    A BARE string is the same citation without even the list: observed live
    (run 20, five times in 14 beats) as `remember_lines.0.evidence: "..."`,
    which slipped past this coercion -- the list-of-strings and dict forms
    were handled, the naked string fell through to pydantic and the whole
    character output bought a temperature-0 repair round for it. It gets
    the identical treatment a list of one string always got.
    """
    if isinstance(value, str):
        slot = _evidence_slot(value)
        return [slot] if slot else []
    if isinstance(value, dict):
        # A map keyed by the evidence itself. The generic map expansion
        # would land the key in `event_id` -- the first empty prose slot --
        # which is the opposite of what the same text gets in list form,
        # where a sentence is routed to `fact`. Answer it here, with the
        # one rule, rather than let two paths disagree about the same words.
        if value and all(isinstance(v, dict) for v in value.values()):
            expanded = []
            for key, item in value.items():
                item = dict(item)
                if not item.get("event_id") and not item.get("fact"):
                    item.update(_evidence_slot(key))
                expanded.append(item)
            value = expanded
        else:
            value = [value]
    if not isinstance(value, (list, tuple)):
        return value
    out = []
    for item in value:
        if isinstance(item, str):
            slot = _evidence_slot(item)
            if slot:
                out.append(slot)
        else:
            out.append(item)
    return out


# Legacy spellings of the current-beat event id that models wrote before the
# prompt pointed at real observation_ids. Each is mapped back to the canonical
# sentinel so no existing citation is lost. The real ids ("current:<pid>:<n>")
# are left untouched. Measured across 1,254 stored character variants: 4,939
# of 6,404 citations used one of these invented labels, 1,172 used the old
# magic string "current", and 38 used a real id. (UNBUILT §2.1)
_LEGACY_EVENT_IDS = {
    "current_perception", "perception", "perception_current",
    "perception:view", "perception:current", "event:current_perception",
    "event:current", "current_perception:view", "current:view",
    "current_event", "this_beat", "this_turn", "now",
    "current_perception_event", "perception_event",
}


def _normalize_event_id(value):
    """Map legacy current-beat spellings to the canonical sentinel.

    A real observation id (``current:<perceiver>:<n>``) is left untouched.
    The old magic string ``"current"`` and the ~15 invented labels models used
    before the prompt was updated are all mapped to ``"current"`` so downstream
    code can treat them uniformly.
    """
    text = str(value or "").strip()
    if not text:
        return text
    # A real observation id carries a colon-separated perceiver and index.
    if text.startswith("current:") and text.count(":") >= 2:
        return text
    if text == "current":
        return text
    if text in _LEGACY_EVENT_IDS:
        return "current"
    return text


class EvidenceRef(LenientModel):
    event_id: str = ""
    fact: str = ""

    _normalize_eid = validator("event_id", pre=True, allow_reuse=True)(
        lambda cls, v: _normalize_event_id(v)
    )


class MemoryEvidenceUse(LenientModel):
    """A past item deliberately brought to bear on the present decision."""
    event_id: str = ""
    fact: str = ""
    use: str = "recognition"

    _normalize_eid = validator("event_id", pre=True, allow_reuse=True)(
        lambda cls, v: _normalize_event_id(v)
    )


class RememberLine(LenientModel):
    quote: str = ""
    why: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))


class MemoryDispute(LenientModel):
    memory_ref: str = ""
    gist: str = ""  # legacy locator; grounded to memory_ref before commit
    now_reads: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))


class MemoryEffect(LenientModel):
    memory_ref: str = ""
    use: str = "recognition"
    disposition: str = "integrated"
    changed: str = ""

class MindHypothesis(LenientModel):
    about_entity: str
    kind: str
    claim: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))
    alternatives: list[str] = Field(default_factory=list)

    _coerce_alternatives = validator("alternatives", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_str_list(v)
    )
    _clamp_confidence = validator("confidence", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.5)
    )

class RelationshipUpdate(LenientModel):
    target_entity: str
    trust_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    warmth_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    fear_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    trigger_event_ids: list[str] = Field(default_factory=list)

    _clamp_deltas = validator("trust_delta", "warmth_delta", "fear_delta",
                              pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, -0.2, 0.2, 0.0)
    )

class GoalImpact(LenientModel):
    # Which field a name-keyed map's KEY belongs in. `serves` is this item's
    # subject, but it carries a non-empty default, so neither positional rule
    # in `_lenient_coerce` can find it -- see the note there.
    _subject_field = "serves"
    serves: str = "situational"
    impact: float = Field(default=0.0, ge=-1.0, le=1.0)
    certainty: float = Field(default=0.5, ge=0.0, le=1.0)
    agency: str = "none"
    intentionality: float = Field(default=0.0, ge=0.0, le=1.0)
    why: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))

    _impact = validator("impact", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0)
    )
    _certainty = validator(
        "certainty", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5))
    # Declares 0.0. See Observation.suddenness above.
    _intentionality = validator(
        "intentionality", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class SomaticImpact(LenientModel):
    pain: float = Field(default=0.0, ge=0.0, le=1.0)
    pleasure: float = Field(default=0.0, ge=0.0, le=1.0)
    why: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))

    _axes = validator("pain", "pleasure", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0)
    )


class MemoryModulation(LenientModel):
    """How remembered past changes appraisal without becoming perception."""
    evidence: list[EvidenceRef] = Field(default_factory=list)
    familiarity: float = Field(default=0.0, ge=0.0, le=1.0)
    expectation: str = ""
    anticipatory_emotion: str = ""
    coping_effect: float = Field(default=0.0, ge=-1.0, le=1.0)
    # A recollection can make the body tense or warm and can prime danger
    # detection. These are NOT current pain/pleasure or proof of a present
    # threat; commit caps them into a separate one-beat memory echo.
    somatic_echo: float = Field(default=0.0, ge=-1.0, le=1.0)
    threat_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    why: str = ""

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))
    _axes = validator("familiarity", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))
    _coping = validator("coping_effect", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0))
    _echo = validator("somatic_echo", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0))
    _threat = validator("threat_bias", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class CharacterAppraisal(LenientModel):
    goal_relevance: str = ""
    expectation: str = ""
    emotion: str = ""
    uncertainty: str = ""
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    controllability: float = Field(default=0.5, ge=0.0, le=1.0)
    coping_potential: float = Field(default=0.5, ge=0.0, le=1.0)
    norm_compatibility: float = Field(default=0.0, ge=-1.0, le=1.0)
    self_congruence: float = Field(default=0.0, ge=-1.0, le=1.0)
    intrinsic_pleasantness: float = Field(default=0.0, ge=-1.0, le=1.0)
    somatic_impact: SomaticImpact = Field(default_factory=SomaticImpact)
    goal_impacts: list[GoalImpact] = Field(default_factory=list)
    present_evidence: list[EvidenceRef] = Field(default_factory=list)
    memory_modulation: MemoryModulation = Field(default_factory=MemoryModulation)

    _coerce_present = validator("present_evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))

    _unit_axes = validator(
        "controllability", "coping_potential",
        pre=True, allow_reuse=True,
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5))
    # Declares 0.0, and `psychology_runtime.stress_delta` reads it with a
    # 0.0 fallback of its own -- the 0.5 was the odd one out of three.
    _novelty = validator(
        "novelty", pre=True, allow_reuse=True,
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))
    _signed_axes = validator(
        "norm_compatibility", "self_congruence", "intrinsic_pleasantness",
        pre=True, allow_reuse=True,
    )(lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0))

    class Config:
        extra = "allow"


class StressState(LenientModel):
    activation: float = Field(default=0.0, ge=0.0, le=1.0)
    # Aversive component of activation, peak-held on its own so a pleasant
    # drive is never re-read as distress next beat (psychology_runtime).
    strain: float = Field(default=0.0, ge=0.0, le=1.0)
    load: float = Field(default=0.0, ge=0.0, le=1.0)
    coping_mode: str = ""
    overloaded: bool = False

    _clamp_stress = validator(
        "activation", "strain", "load", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class HedonicState(LenientModel):
    pain: float = Field(default=0.0, ge=0.0, le=1.0)
    pleasure: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = ""
    # Slow integral of unresolved somatic drive, and the character's own
    # declaration that it discharged this beat (psychology_runtime).
    charge: float = Field(default=0.0, ge=0.0, le=1.0)
    saturated: bool = False
    released: bool = False

    _clamp_hedonics = validator(
        "pain", "pleasure", "charge", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class CharacterActiveState(LenientModel):
    mood: Any = ""
    goal: str = ""
    affect: dict = Field(default_factory=dict)
    wants: list[dict] = Field(default_factory=list)
    enacted_want: Optional[int] = None
    suppressed_want: Optional[int] = None
    active_concerns: list[str] = Field(default_factory=list)
    stress: StressState = Field(default_factory=StressState)
    hedonic: HedonicState = Field(default_factory=HedonicState)

    class Config:
        extra = "allow"


def _coerce_candidate_response(value):
    """Accept a candidate `response` expressed as a sequence ELEMENT.

    `response` is the prose of one option the character weighed, but "the
    candidate response" reads just as naturally as the act itself, and models
    emit it structurally:

        "response": {"type": "action", "attempt": "step through the doorway",
                     "observable": "steps forward through the doorway", ...}

    Rejecting that failed the ENTIRE character turn -- the beat was lost, the
    character did nothing, and the only signal was a type error naming a field
    the author never sees. Reduce it to the prose it contains instead. The
    surface (`observable`) is preferred over the intent (`attempt`) because
    these candidates are weighed, not enacted, and the observable is what the
    other machinery would ever show anyone.
    """
    if isinstance(value, dict):
        for key in ("observable", "attempt", "text", "response", "summary",
                    "content", "description"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
        return ""
    if isinstance(value, (list, tuple)):
        # Recurse rather than `str()` each element: a list of sequence
        # elements is the same shape as the case above, one level out, and
        # stringifying it put a Python dict repr into the character's prose
        # ("{'type': 'action'}; {'type': 'speech'}") -- which then reads as
        # something they considered saying.
        parts = [str(_coerce_candidate_response(v) or "").strip()
                 for v in value]
        return "; ".join(part for part in parts if part)
    return value


def _coerce_candidate_list(value):
    """`response_candidates` however the model spelled the collection.

    A list is the declared shape. A MAP keyed by the option itself --
    `{"step back": {"risk": 0.2}}` -- is the same shape models reach for on
    every other list of named things, and returning `[]` for it discarded
    the character's whole deliberation with no warning. A single candidate
    object is accepted as itself, matching the generic wrap.
    """
    if isinstance(value, str):
        value = [value]
    elif isinstance(value, dict):
        if not value:
            value = []
        elif all(isinstance(v, dict) for v in value.values()):
            expanded = []
            for key, item in value.items():
                item = dict(item)
                if not item.get("response"):
                    item["response"] = key
                expanded.append(item)
            value = expanded
        elif set(value) & set(_fields(ResponseCandidate) or {}):
            value = [value]      # one candidate, written as itself
        else:
            # Neither a candidate nor a map of them. Wrapping it produced a
            # blank `{"response": ""}` -- an option the character never
            # weighed, written into the record the variant viewer shows.
            _note_drop(
                "response_candidates arrived in a shape that is neither a "
                f"candidate nor a map of them ({sorted(value)[:4]}); the "
                "whole deliberation was dropped")
            value = []
    return [
        {"response": item} if isinstance(item, str) else item
        for item in (value if isinstance(value, list) else [])
        if isinstance(item, (str, dict))
    ]


#: How many aims one considered response may name. A DETERMINISTIC ceiling,
#: because the floor must not depend on a model cooperating.
#:
#: `serves` is the only one of the three in this schema that is a LIST -- a
#: want serves one thing, a goal impact serves one thing, a response candidate
#: serves several -- and it was the only one whose vocabulary the prompt never
#: stated. Live, a character step read that as an invitation to enumerate: it
#: began with real aims (`ia1`, `drive`, `situation`), drifted into the payload's
#: own field NAMES (`beliefs`, `values`, `self_model`, `coping`), ran off the end
#: of the payload into JSON Schema meta-keywords (`title`, `properties`, `$ref`),
#: and then locked into a cycle of those. Enumeration is where a sampler locks:
#: each comma-separated item is highly predictable from the last.
#:
#: Six is generous. A response that genuinely serves seven distinct aims is not
#: being reasoned about, it is being listed.
CANDIDATE_SERVES_LIMIT = 6


class ResponseCandidate(LenientModel):
    response: str = ""
    serves: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    inhibition: float = Field(default=0.0, ge=0.0, le=1.0)
    norm_conflict: str = ""
    selected: bool = False

    _lists = validator("serves", pre=True, allow_reuse=True)(
        lambda cls, value: _kept(
            "response_candidates[].serves", _coerce_str_list(value),
            _coerce_str_list(value)[:CANDIDATE_SERVES_LIMIT])
    )
    _coerce_response = validator("response", pre=True, allow_reuse=True)(
        lambda cls, value: _coerce_candidate_response(value)
    )
    _candidate_axes = validator(
        "risk", "inhibition", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class BeliefUpdate(LenientModel):
    belief: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))
    operation: str = "reinforce"
    emotional_charge: float = Field(default=0.0, ge=-1.0, le=1.0)

    _confidence = validator("confidence", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5)
    )
    _charge = validator("emotional_charge", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0)
    )


class AssociationUpdate(LenientModel):
    cue: str
    appraisal_bias: str = ""
    response_tendency: str = ""
    operation: str = "reinforce"
    amount: float = Field(default=0.1, ge=0.0, le=0.25)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))

    _amount = validator("amount", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 0.25, 0.1)
    )


class InteractionControl(LenientModel):
    addresses: list[str] = Field(default_factory=list)
    expects_response: bool = False
    yields_floor: bool = True
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    conversation_complete_for_me: bool = False

    _clamp_urgency = validator("urgency", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.0)
    )

class CharacterOutput(LenientModel):
    observations_used: list[EvidenceRef] = Field(default_factory=list)
    present_evidence_used: list[EvidenceRef] = Field(default_factory=list)
    memory_evidence_used: list[MemoryEvidenceUse] = Field(default_factory=list)

    _coerce_observations = validator(
        "observations_used", "present_evidence_used", "memory_evidence_used",
        pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))
    appraisal: CharacterAppraisal = Field(default_factory=CharacterAppraisal)
    considered_responses: list[str] = Field(default_factory=list)
    response_candidates: list[ResponseCandidate] = Field(default_factory=list)

    _coerce_considered = validator("considered_responses", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_str_list(v)
    )
    _coerce_candidates = validator(
        "response_candidates", pre=True, allow_reuse=True
    )(lambda cls, value: _coerce_candidate_list(value))
    _coerce_active_state = validator("active_state", pre=True, allow_reuse=True)(
        lambda cls, value: (
            {"mood": value, "goal": ""} if isinstance(value, str) else value
        )
    )
    sequence: list[dict] = Field(default_factory=list)
    speech: Optional[str] = None
    action: Optional[dict] = None
    actions: list[dict] = Field(default_factory=list)
    active_state: Optional[CharacterActiveState] = None
    # Interior depth (all optional; the deterministic floors in affect.py apply
    # at commit). Kept as permissive dicts/lists -- affect.py validates/normalizes.
    intent_ops: list[dict] = Field(default_factory=list)
    # Boundary-only updates to this character's one or two held projects:
    # {op:'adopt|displace|satisfy', id, project, about, satisfied_when, why}.
    # Validated by affect.apply_project_ops, which has always been complete.
    #
    # THIS FIELD DID NOT EXIST, and the whole tier died on that. The character
    # prompt asks for `project_ops` by name in three places and prints its
    # shape in the required JSON; commit.py reads
    # `own_result.get("project_ops")`; affect.py implements adopt/displace/
    # satisfy with a cap, a legibility floor and a required reason for giving
    # one up. Pydantic dropped every op in between, silently, because the model
    # had no field to put them in -- so a character could be asked for a
    # project, answer, and be heard saying nothing.
    #
    # Somebody had already gone hunting for the silence and got close: the
    # `project_review` invitation used to be gated on already holding a
    # project, which made the occasion require the thing it would create. That
    # was found and fixed. The measurement it left behind -- "0 of 14 live
    # banks have ever held a project" -- did not move, because the gate was
    # never the only thing shut.
    project_ops: list[dict] = Field(default_factory=list)
    # A voluntary decision by this character to begin or cease following a
    # target. Omit to preserve the current relation.
    follow_op: Optional[dict] = None
    # Completed contact endings this character owns, expressed by opaque refs
    # supplied in self.standing_contacts.  The host resolves each ref back to
    # the exact onset contact; the model never has to recreate anatomical or
    # object-part spelling, and cannot accidentally clear a different contact
    # between the same bodies.  Only op=remove is accepted downstream.
    contact_ops: list[dict] = Field(default_factory=list)
    # Completed, self-owned production/deposit of non-discrete matter.  The
    # character names only matter established by its own embodiment,
    # equipment, ontology, or current state; the host supplies `source` and
    # projects these through the objective substance ledger.
    material_effects: list[dict] = Field(default_factory=list)
    manifest: dict = Field(default_factory=dict)
    # A drive rupture proposal -- only valid inside an engine-opened window;
    # commit (validate_drive_shift) decides whether it counts.
    drive_shift: Optional[dict] = None
    belief_updates: list[BeliefUpdate] = Field(default_factory=list)
    association_updates: list[AssociationUpdate] = Field(default_factory=list)
    # Lines from THIS beat this mind wants to keep. Durable dialogue was gated
    # by a fixed phrase list (`commit._durable_dialogue_category`: promises,
    # "my name is", a handful of confessions), which is why the live corpus
    # holds 15 dialogue rows against 2,028 episodes -- a warning, an
    # instruction, a code, an indirect threat, a newly established fact all
    # fail it. Rather than lengthening the list, the character says. That makes
    # memory formation psychology-dependent, which is the point: one mind keeps
    # an insult another shrugs off. Commit validates the quote was actually
    # said this beat AND actually reached this observer's view, so this can
    # only ever preserve something already heard, never invent one.
    # [{"quote": str, "why": str}]
    remember_lines: list[RememberLine] = Field(default_factory=list)
    # A memory this mind now reads differently. NOT a correction of the record:
    # the event stays true and untouched, and only the character's reading of
    # it is recorded as having changed -- what deception, disguise and
    # misidentification actually do. [{"gist": str, "now_reads": str}]
    memory_disputes: list[MemoryDispute] = Field(default_factory=list)
    # What recalled material actually did to this decision.  Retrieval is not
    # impact; this makes the distinction measurable and gives unbidden recall
    # a consequence signal stronger than "the goal string changed".
    memory_effects: list[MemoryEffect] = Field(default_factory=list)

    _coerce_remember_lines = validator(
        "remember_lines", pre=True, allow_reuse=True)(
        lambda cls, v: _kept("remember_lines", v, [
            item for item in v
            if isinstance(item, dict) and str(item.get("quote") or "").strip()
        ]) if isinstance(v, (list, tuple)) else [])
    _coerce_disputes = validator(
        "memory_disputes", pre=True, allow_reuse=True)(
        lambda cls, v: _kept("memory_disputes", v, [
            item for item in v
            if isinstance(item, dict) and (
                str(item.get("memory_ref") or "").strip() or
                str(item.get("gist") or "").strip())
            and str(item.get("now_reads") or "").strip()
        ]) if isinstance(v, (list, tuple)) else [])

    # `cue` is required and an entry without one names nothing, so it cannot be
    # applied -- but dropping the entry is right where failing the entire
    # character turn is not. Same posture as the dialogue coercion, which drops
    # a line with no quote rather than rejecting the beat.
    _drop_cueless = validator(
        "association_updates", pre=True, allow_reuse=True)(
        lambda cls, v: _kept("association_updates", v, [
            item for item in v
            if not isinstance(item, dict) or str(item.get("cue") or "").strip()
        ]) if isinstance(v, (list, tuple)) else v)
    mind_model_updates: list[MindHypothesis] = Field(default_factory=list)
    relationship_updates: list[RelationshipUpdate] = Field(default_factory=list)
    interaction: InteractionControl = Field(default_factory=InteractionControl)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)

    _clamp_salience = validator("salience", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.5)
    )

# ---- Mapping ----

class ScenePatch(LenientModel):
    rooms: dict[str, dict] = Field(default_factory=dict)
    entities: dict[str, dict] = Field(default_factory=dict)
    positions: dict[str, str] = Field(default_factory=dict)
    # Where in each room the mapping stage places people. Same shape and same
    # reason as StateDiff.stations; the mapping stage is the layout authority,
    # so this is usually the first thing that knows a room HAS a bed to be on.
    stations: dict[str, dict] = Field(default_factory=dict)
    remove_entities: list[str] = Field(default_factory=list)
    remove_rooms: list[str] = Field(default_factory=list)
    remove_adjacent: list[dict] = Field(default_factory=list)

    _coerce_stations = validator("stations", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_station_table(v)
    )

class BookOp(LenientModel):
    """A live, per-turn proposal to create ONE new child lorebook,
    mirroring importers.py's book_ops shape (the existing manual
    reinterpret-lorebook flow) but usable during ordinary play. temp_id
    is this proposal's own scratch handle -- LoreOp.book_id may reference
    it directly so an entry can be filed into a book proposed the SAME
    commit, before it has a real database id yet."""
    op: str = "create"
    temp_id: Optional[str] = None
    name: str = ""
    book_type: str = "general"
    summary: str = ""
    parent_id: Optional[Union[int, str]] = None  # an existing book's int id, or another op's temp_id
    inheritance_mode: str = "inherit"
    scope_world_id: Optional[str] = None
    scope_location_id: Optional[str] = None
    anchor_entity_id: Optional[str] = None

def _one_or_many_locations(value):
    """One named place where a lore entry is known, or several.

    `LenientModel` already reads `""` as "nothing to report" for a declared
    list. It does not reach the mirror case: a NON-empty scalar, where the
    model named a single location instead of a list holding one. Measured
    across the live corpus that is 4 of 17 validation failures -- 24% of every
    repair call -- and the whole mapping commit was thrown away over the
    difference between `"the vault"` and `["the vault"]`.

    Wrapped, never split. A comma inside the string might be two places or one
    place with a comma in its name, and this module's charter is to READ a
    near-miss shape, not to invent structure that was never sent.
    """
    if isinstance(value, str) and value.strip():
        return [value]
    return value


class LoreOp(LenientModel):
    op: str = "create"
    id: Optional[int] = None
    book_id: Optional[Union[int, str]] = None  # an existing book's int id, or a same-turn BookOp's temp_id
    keys: str = ""
    content: str = ""
    category: str = "other"
    title: Optional[str] = None
    knowledge_tag: Optional[str] = None
    knowledge_range: Optional[str] = None
    knowledge_locations: list[str] = Field(default_factory=list)
    _coerce_locations = validator("knowledge_locations", pre=True,
                                  allow_reuse=True)(
        lambda cls, v: _one_or_many_locations(v))
    importance: Optional[float] = None
    aliases: Optional[list[str]] = None
    scope: Optional[dict[str, Any]] = None
    relations: Optional[dict[str, Any]] = None
    source_notes: Optional[str] = None
    reason: str = ""

class ValidatedFact(LenientModel):
    fact: str = ""
    ok: bool = False
    conflict_with: str = ""

class ValidatedIntroduction(LenientModel):
    who: str = ""
    learns: str = ""
    ok: bool = False
    corrected_learns: Optional[str] = None

class MappingCommit(LenientModel):
    validated: list[ValidatedFact] = Field(default_factory=list)
    lore_ops: list[LoreOp] = Field(default_factory=list)
    book_ops: list[BookOp] = Field(default_factory=list)
    shadow_profile: Optional[str] = None
    offscreen_events: list[dict] = Field(default_factory=list)
    standing_intentions: list[dict] = Field(default_factory=list)
    coherence_notes: list[str] = Field(default_factory=list)
    validated_introductions: list[ValidatedIntroduction] = Field(default_factory=list)

# `PerceptionOutput` lived here, keyed as the `perception` step. Removed: it
# was unreachable. Perception makes no model call -- every view is composed
# deterministically in `agents/composer.py` -- so there is no model output to
# validate. The real step keys are `perception_act`, `perception_outcome` and
# `perception_establish`, none of which appear in SCHEMA_MAP, and no
# `perception` step exists in the live corpus (2,317 turns checked) or in
# `STEP_HANDLERS`. The two `step_key == "perception"` branches that read as
# firewall protection went with it: a guard that cannot fire protects nothing,
# and reads as though something is covered when it is not.

class MappingStageOutput(LenientModel):
    relevant_books: list[int] = Field(default_factory=list)
    relevant_lore: list[dict] = Field(default_factory=list)
    staged_lore: list[dict] = Field(default_factory=list)
    scene_patch: ScenePatch = Field(default_factory=ScenePatch)
    npc_suggestions: list[dict] = Field(default_factory=list)
    notes: str = ""

# ---- Greeting interpretation (ingest-time, per docs/design/GREETING_IMPORT_DESIGN.md) ----

class GreetingKnowledgeSeed(LenientModel):
    content: str = ""
    about_entity: str = "self"      # 'self' = the character
    kind: str = "fact"              # fact|goal|relationship|recent_event
    # Capped BELOW the 0.72 consolidation floor (`memory.py`), not at 1.0.
    #
    # Salience used to be the model's unbounded self-report, and the model says
    # 1.00: all four seeds of chat 53's launch came in at 1.00 against the 0.78
    # of the one memory the pipeline actually minted that turn. Nothing above
    # 0.72 is ever archived, so those never age out -- and `contrast_memory`
    # scores `salience + 0.4 * (age / current_turn)`, so their chance of
    # intruding UNBIDDEN grows with story length. Authored scaffolding
    # permanently outranked lived experience and got louder the longer the
    # story ran. A ceiling under the floor lets a seed decay like everything
    # else the character went on to live.
    salience: float = Field(default=0.6, ge=0.0, le=0.7)
    # true = the greeting states it openly on the page (player legitimately
    # sees it); false = implied/secret -> routes to CHARACTER memory only.
    revealed_in_prose: bool = False

    _clamp_salience = validator("salience", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 0.7, 0.6)
    )

class GreetingInterpret(LenientModel):
    """Two fields, because two are read.

    This model used to declare eleven: a whole scene graph (`rooms`,
    `positions`, `entities`, `attire`, `player_room`), plus `location`,
    `scene_description`, `character_state` and `notes`. `story.greetings`
    reads `time` and `knowledge_seeds` and nothing else, and the scene half
    was never a gap waiting to be wired -- `start_story` stores the greeting
    prose itself as the chat's scenario, so `director_establish` builds the
    scene graph from the SAME passage one turn later, with the engine's full
    payload behind it. Asking a second, weaker pass for the same graph and
    discarding the answer cost a large prompt and most of the tokens of every
    card-ingest call.

    Extra keys are ignored rather than refused, as everywhere else here, so a
    stored extraction written by an older extractor still reads.
    """

    #: Seeds the chat's `simulation_clock.display` at launch.
    time: str = "now"
    #: The point of the call: what the greeting implies the CHARACTER knows,
    #: routed to that character's private memory.
    knowledge_seeds: list[GreetingKnowledgeSeed] = Field(default_factory=list)

# ---- Validation ----

SCHEMA_MAP = {
    "greeting_interpret": GreetingInterpret,
    "director_interpret": DirectorInterpret,
    "director_establish": DirectorEstablish,
    "director_resolve": DirectorResolve,
    "director_body": DirectorBodySpecialist,
    "director_social": DirectorSocialSpecialist,
    "director_contact": DirectorContactSpecialist,
    "director_objects": DirectorObjectsSpecialist,
    "director_spatial": DirectorSpatialSpecialist,
    "director_offscreen": DirectorOffscreenSpecialist,
    "resolve_reconcile": ResolveReconcileOutput,
    "resolve_repair": ResolveRepairOutput,
    "interpret_repair": InterpretRepairOutput,
    "narrator": NarratorOutput,
    "character": CharacterOutput,
    "mapping_stage": MappingStageOutput,
    "mapping_commit": MappingCommit,
    "background_react": BackgroundReactOutput,
    "scene_life": SceneLifeOutput,
    "blurb_mint": BlurbMintOutput,
    "backdrop_prompt": BackdropPromptOutput,
}

_WHOLLY_QUOTED = re.compile(r'^\s*["“]([^"”]+)["”]\s*[.!?]*\s*$')


def _sequence_event_from_prose(text):
    """A sequence entry the model wrote as a sentence instead of an object.

    `["Picks up the PADD.", "Says, \\"Nobody leaves this room.\\""]` -- and
    every non-object entry was discarded, so the step then failed as
    "sequence is empty despite nonempty player input" and the turn died.
    Twice in eleven live turns, on both Pydantic majors.

    The entry is kept as an ACTION unless the whole string is a quotation,
    which is the only spelling that says "this is speech" without
    interpretation. A sentence that merely CONTAINS a quote stays an action
    whose attempt text still holds every word, so nothing is lost -- only
    typed conservatively.

    That default is deliberate and it is the safe direction, not the
    convenient one. Typing prose as speech would both author an utterance
    for whoever declared it and transmit it to everyone within earshot;
    typing speech as an action under-informs the room instead. Where the
    engine cannot tell, it must fail toward telling minds LESS than
    happened, never more.
    """
    text = text.strip()
    if not text:
        return None
    quoted = _WHOLLY_QUOTED.match(text)
    if quoted:
        return {"type": "speech", "text": quoted.group(1).strip(),
                "volume": "normal"}
    return {"type": "action", "attempt": text}


def _flatten_staged_lore(result):
    """A staged lore entry's `content` is prose, and has to actually be prose.

    `staged_lore` and `relevant_lore` are declared `list[dict]`, so nothing
    checks what is inside an entry -- and a model asked to draft a lore entry
    about a room will sometimes return the entry as an OBJECT
    (`{"name": ..., "desc": ...}`) rather than as the paragraph the prompt
    asks for. Nothing rejects it, and it then reaches code that treats it as
    text: observed live on an opening turn, `_room_notes_from_lore` did
    `content[:600]` on that dict and killed the turn with
    `KeyError: slice(None, 600, None)`. The same value is also what
    `commit.py` writes into `lore_entries.content`.

    Flattened here rather than at either reader, because both of them --
    and the database -- want the same thing, and this is the last point
    where the model's own structure is still visible enough to join in
    traversal order.
    """
    for key in ("staged_lore", "relevant_lore"):
        entries = result.get(key)
        if not isinstance(entries, list):
            continue
        flattened = []
        for entry in entries:
            if isinstance(entry, dict) and not isinstance(
                    entry.get("content"), (str, type(None))):
                entry = dict(entry)
                entry["content"] = _flatten_view_value(entry["content"]) or ""
            flattened.append(entry)
        result[key] = flattened


def _coerce_int_list(value):
    result = []
    for item in value or []:
        if isinstance(item, int):
            result.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            result.append(int(item.strip()))
    return result

def _coerce_considered_responses(value):
    """considered_responses is internal deliberation scratch -- nothing
    downstream reads it (it exists for inspecting a character's reasoning
    in the step/variant viewer). Models commonly emit structured entries
    (e.g. {"response": ..., "score": ...}) instead of the declared
    list[str], which used to hard-fail the entire character turn on a
    field with no behavioral effect. Coerce leniently instead.
    """
    if not isinstance(value, list):
        if value not in (None, "", {}):
            _note_drop(
                "considered_responses was not a list "
                f"({type(value).__name__}); the deliberation scratch was "
                "dropped")
        return []

    result = []

    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("response") or item.get("text")
                or item.get("option") or item.get("action")
                or item.get("description") or item.get("content") or ""
            ).strip()
            score = item.get("score")
            if text and score is not None:
                text = f"{text} (score: {score})"
        else:
            text = str(item).strip()

        if text:
            result.append(text)

    return _kept("considered_responses", value, result)

def _coerce_empty_list_to_dict(value):
    """A field typed as a dict (positions/rooms/entities/conditions/...)
    commonly comes back as `[]` instead of `{}` when a model has nothing
    to report for it -- both read as "empty" to a model, but pydantic
    rejects the type mismatch outright. This crashed a live turn on
    state_diff.conditions being `[]`. director.py already has downstream
    code that defensively re-coerces exactly these fields to `{}` when
    they arrive malformed, but that code is unreachable dead weight if
    strict validation upstream already aborted the call -- so the
    coercion has to happen here, before validation, to actually work.
    Only the unambiguous empty-list case is handled; a genuinely
    non-empty list where a dict was expected is left for validation to
    reject rather than guessed at.
    """
    if value == []:
        return {}
    return value

def _coerce_empty_dict_to_list(value):
    """Inverse of _coerce_empty_list_to_dict, same underlying model behavior:
    a field typed as a list (scene_patch.remove_entities/remove_rooms/
    remove_adjacent) comes back as `{}` instead of `[]` when there's nothing
    to report. Crashed a live turn on exactly this. Only the unambiguous
    empty-dict case is handled; a genuinely non-empty dict where a list was
    expected is left for validation to reject rather than guessed at.
    """
    if value == {}:
        return []
    return value

def _coerce_optional_time(value):
    """`state_diff.time` is Optional[dict]; a scalar becomes None, not a crash.

    Live, GLM-5.2 on a Green Door Inn beat: the model sent a non-dict and the
    whole turn died on `state_diff.time: value is not a valid dict` -- the
    resolved_event, the summary, the dialogue and every other field in a
    correct 4,000-token response thrown away over one optional field.

    Dropping it is the honest repair rather than a lenient one. The field
    carries start/duration/end seconds, and nothing truthful can be built from
    a bare string; the engine drifts its own clock when the field is absent,
    which is exactly the state an omitted `time` already describes. So the
    beat survives saying "this turn asserted no time advance", which is true,
    instead of dying with a number invented to satisfy a validator.

    The cause is fixed separately, in OUTPUT_EXAMPLES: the example showed
    `"time": null` while the prompt described the six-field object in prose
    two thousand lines away, so the model had a scalar to copy -- and the
    repair attempt was handed the same null and could not converge.
    """
    if value is not None and not isinstance(value, dict):
        _note_drop(
            f"state_diff.time arrived as {type(value).__name__} "
            f"({str(value)[:60]!r}) and was dropped; the beat asserts no "
            "time advance and the clock drifts on its own")
    return value if isinstance(value, dict) else None


def _coerce_conditions(value):
    def condition_dict(entry, key=""):
        if isinstance(entry, str) and entry.strip():
            # The condition written as its own description --
            # `{"generator_fuel": ["The generator is running low on fuel..."]}`
            # -- which cost a live turn on `director_resolve`, identically on
            # both Pydantic majors. The key already names the condition and
            # `commit.py` stores the whole entry as its payload, so the prose
            # is kept rather than thrown away with the step around it. Only
            # a string converts: any other scalar carries neither an id nor a
            # description and is dropped by the callers below.
            return {"condition_id": key, "note": entry.strip()}
        if not isinstance(entry, dict):
            return entry
        entry = dict(entry)
        if "state" in entry and not isinstance(entry.get("state"), dict):
            # Condition consumers require structured state. A scalar must not
            # pass list[dict] validation only to crash those readers later.
            entry["state"] = {}
        return entry

    if value == []:
        return {}
    if isinstance(value, list):
        grouped = {}
        for i, cond in enumerate(value):
            if not isinstance(cond, dict):
                _note_drop(
                    f"state_diff.conditions[{i}] is a "
                    f"{type(cond).__name__}, not a condition; dropped")
                continue
            key = str(cond.get("condition_id") or f"condition_{i}")
            grouped.setdefault(key, []).append(condition_dict(cond))
        return grouped
    if isinstance(value, dict):
        # conditions is dict[str, list[dict]] -- a model sometimes writes a
        # single condition object (or the model crashed a live turn on
        # exactly this: a bare dict) for one key instead of wrapping it in
        # the expected one-item list. Same failure shape as the perception
        # views fix: coerce the leaf rather than reject the whole step.
        fixed = {}
        for key, entry in value.items():
            if isinstance(entry, list):
                items = [condition_dict(item, key) for item in entry]
            elif isinstance(entry, dict):
                items = [condition_dict(entry, key)]
            elif entry is not None:
                items = [condition_dict(entry, key)]
            else:
                continue
            fixed[key] = _kept(
                f"state_diff.conditions[{key!r}]", items,
                [item for item in items if isinstance(item, dict)])
        return fixed
    return value

_STATE_DIFF_DICT_FIELDS = (
    "positions", "rooms", "entities", "overlays", "attire", "entity_states",
    "poses",
)

#: The orchestrated Director's specialists (design note 19), step_key ->
#: the state_diff channels that specialist owns. One authority for the
#: preprocess unwrap, the channel-level prune, and (via import) the
#: project-structure check that holds prompts.SPECIALIST_PROMPT_SPECS and
#: agents/director.SPECIALISTS level with this map.
SPECIALIST_CHANNELS = {
    "director_body": ("attire", "conditions", "vitals", "overlays"),
    "director_social": ("cast_changes", "introductions", "world_facts"),
    "director_contact": ("contact_ops", "substance_ops", "containment",
                         "scales"),
    "director_objects": ("entities", "remove_entities", "inventory_ops",
                         "artifact_ops", "destruction"),
    "director_spatial": ("positions", "rooms", "remove_rooms",
                         "remove_adjacent", "stations", "poses", "comms_ops"),
    "director_offscreen": ("crowd_ops", "courier_ops", "telling_ops",
                           "offscreen_plan_ops", "ratified_claims",
                           "contradicted_claims"),
}

def _specialist_channel_shapes():
    """Which empty spelling each specialist channel has to be corrected TO.

    DERIVED, because the two sets used to be written out by hand and had
    drifted: `comms_ops` is declared `list[CommsOp]` and sat in the dict set,
    so an empty `comms_ops: []` -- the ordinary way a model says no voice
    channel changed this beat -- was rewritten to `{}` before validation.
    Inert only because `LenientModel` turned it back, which is one mechanism
    covering for another rather than a reason the first was right. A model
    declares the shape once; nothing else should get to have an opinion.

    Only the unambiguous empty case is ever corrected (see
    `_coerce_empty_list_to_dict`), so a channel appearing here can cost a
    beat nothing: a non-empty value of the wrong shape still reaches
    validation and is still rejected.
    """
    dicts, lists = set(), set()
    for step_key, channels in SPECIALIST_CHANNELS.items():
        fields = _fields(SCHEMA_MAP.get(step_key)) or {}
        for channel in channels:
            field = fields.get(channel)
            if field is None:
                continue
            declared = _declared(field)
            if declared.is_list:
                lists.add(channel)
            elif declared.expects_object:
                dicts.add(channel)
    return frozenset(dicts), frozenset(lists)


_SPECIALIST_DICT_CHANNELS, _SPECIALIST_LIST_CHANNELS = (
    _specialist_channel_shapes())

_STATE_DIFF_SIBLING_FIELDS = (
    "remove_entities", "remove_rooms", "remove_adjacent", "conditions",
    "inventory_ops", "artifact_ops", "destruction", "contact_ops",
    "substance_ops", "stations", "poses", "scales", "containment",
    "vitals", "overlays",
    "attire", "cast_changes",
    "world_facts", "introductions", "time", "claim_dispositions",
)

_SCENE_PATCH_SIBLING_FIELDS = (
    "rooms", "positions", "stations", "remove_entities", "remove_rooms",
    "remove_adjacent",
)


def _non_entity_field_keys():
    """Keys that can never denote an entity: the field names that sit BESIDE
    an entity map in any schema that carries one (StateDiff, ScenePatch, the
    objects specialist), plus the envelope names. An entities mapping is
    keyed by whatever string arrives, so a sibling field written one nesting
    level too deep becomes an "entity" named after a field -- chat 80's scene
    held six entities keyed `remove_entities`, `inventory_ops`,
    `artifact_ops`, `destruction`, `notes` and `resolved_events`, each a
    verbatim copy of the Interview Chair. Computed from the models' own
    declarations so a channel added later is covered without this list being
    remembered."""
    keys = {"entities", "state_diff", "state_assertions"}
    for model_cls in (StateDiff, ScenePatch, DirectorObjectsSpecialist):
        keys |= set(_fields(model_cls) or {})
    return frozenset(keys)


#: See _non_entity_field_keys. Read by spatial.merge_scene_with_diff and
#: scene.get_scene so a live story already carrying such keys stops reading
#: them as entities without a migration.
NON_ENTITY_FIELD_KEYS = _non_entity_field_keys()

def _hoist_misplaced_entity_siblings(container, sibling_fields):
    """Both StateDiff.entities and ScenePatch.entities are dict[str, <entity
    def>] -- keyed by actual in-fiction entity names. Observed live in both
    schemas: a model writes the REST of the parent object's own sibling
    fields (conditions, attire, time, remove_rooms, ...) as if they were
    entries inside `entities`, one nesting level too deep, instead of at
    their correct position as the parent's own top-level keys. A
    flatten-to-string coercion (as used for perception views / narrator
    new_specifics) would be wrong here -- these values need to move up a
    level intact, not collapse into prose. Only hoist keys whose name
    exactly matches a genuine sibling field, and only when the parent
    doesn't already have that field set (never clobber a correctly-placed
    value); an actual entity legitimately named e.g. "time" is not a
    realistic collision risk for either schema's field-name vocabulary.

    A matched key is REMOVED from `entities` even when it cannot be hoisted:
    a field name can never key an entity, so leaving it in place mints one.
    Chat 80 turn 1: the objects specialist's entities map carried its own
    sibling names holding verbatim copies of the Interview Chair's def, and
    six chair clones entered the scene keyed `remove_entities`,
    `inventory_ops`, `artifact_ops`, `destruction`, `notes` and
    `resolved_events`. An entity-def-shaped value under a sibling key is that
    debris exactly -- neither an entity (the key is a field name) nor the
    sibling (the value is an entity def) -- and hoisting it would turn a
    chair copy into, say, a `destruction` declaration, so it is dropped.
    """
    entities = container.get("entities")
    if not isinstance(entities, dict):
        return
    for field in sibling_fields:
        if field not in entities:
            continue
        value = entities.pop(field)
        entity_shaped = isinstance(value, dict) and bool(
            {"kind", "portable", "aliases"} & set(value))
        if field not in container and not entity_shaped:
            container[field] = value

def _flatten_view_value(value):
    """perception's views field is typed as {perceiver_id: string|null} -- one
    continuous piece of sensory prose per perceiver. Some models default to
    decomposing that prose into labeled sub-fields instead (e.g.
    {"sight": "...", "sound": "...", "entity_state": {...}}), which reads as
    valid JSON but fails the string type outright and used to abort the whole
    perception step. Rather than depend on every candidate model reliably
    following the "write one string" instruction, flatten any nested
    structure into prose here -- join leaf values in traversal order. Only
    engages when a value isn't already a plain string or null; the common
    case (a compliant model) never touches this path.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [_flatten_view_value(v) for v in value.values()]
        return " ".join(p for p in parts if p) or None
    if isinstance(value, list):
        parts = [_flatten_view_value(v) for v in value]
        return " ".join(p for p in parts if p) or None
    return str(value)

# Suffixes a model appends to an entity KEY purely to keep the id distinct
# ("guinan_entity", "turbolift_car_entity"); they are not part of the display
# name, as the model's own successful outputs show ("Guinan", "Turbolift Car").
_ENTITY_KEY_SUFFIX = re.compile(r"[_\-](entity|obj|object|item|node)$", re.I)
# Keys a model reaches for instead of `name`, mirroring the dialogue_log
# alias handling below.
_ENTITY_NAME_ALIASES = ("name", "label", "title", "display_name", "displayName")
# A generated handle rather than a word: long, separator-free, and either pure
# hex or all digits. Live scenes key some entities this way
# ("10ae6b6a11324780") alongside semantic ones ("sake_carafe").
_OPAQUE_ID = re.compile(r"(?:[0-9a-f]{12,}|[0-9]{6,})", re.I)


def _entity_name_from_key(key) -> str:
    """A display name derived from the entity's own dict key.

    `entities` is keyed by id, so the key ALREADY names the thing and models
    routinely omit the redundant `name` -- observed live with glm-latest as
    Director: "state_diff.entities.sake_carafe.name: field required;
    state_diff.entities.computer.name: field required", which failed the whole
    turn. Rejecting an output over a field recoverable from its own key is the
    same over-strictness the dialogue_log repair below already addresses.
    """
    slug = _ENTITY_KEY_SUFFIX.sub("", str(key or "").strip())
    # An opaque generated id ("10ae6b6a11324780") names nothing. Live scenes
    # mix semantic keys with hex ids, and title-casing one produces a display
    # name like "10Ae6B6A11324780" that would then be shown to the player and
    # used as a lookup key. Better to derive nothing and let the caller fall
    # back to the schema default than to invent a garbage name.
    if _OPAQUE_ID.fullmatch(slug):
        return ""
    words = [w for w in re.split(r"[_\-\s]+", slug) if w]
    # Preserve deliberate acronyms (LCARS, EPS) rather than title-casing them.
    return " ".join(w if w.isupper() else w.capitalize() for w in words)


def is_derived_entity_name(key, name, kind=None) -> bool:
    """Would `_fill_entity_names` have invented exactly this name for `key`?

    The recovery below is a repair for a MISSING name, but it is indis-
    tinguishable downstream from a name the model actually chose -- and a
    scene merge cannot tell "the Director renamed this" from "the Director
    sent a state-only diff and validation filled the blank". Live
    (Elevator Adventure branch 41): a pose-only update to `the_doctor_10`
    came back named "The Doctor 10" and overwrote "The Doctor", and
    `tardis_001` overwrote "Blue Police Box" with "Tardis 001". Exposed so
    spatial._merge_entity can refuse a placeholder that would replace a
    real name; an explicit rename to some OTHER string still wins.
    """
    text = str(name or "").strip()
    if not text:
        return False
    candidates = {_entity_name_from_key(key),
                  str(kind or "").strip().title(),
                  "Object"}
    return text in {c for c in candidates if c}


def _fill_entity_names(container) -> None:
    """Give every entity def in `container['entities']` a name, in place."""
    if not isinstance(container, dict):
        return
    entities = container.get("entities")
    if not isinstance(entities, dict):
        return
    for key, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        for alias in _ENTITY_NAME_ALIASES:
            value = entity.get(alias)
            if isinstance(value, str) and value.strip():
                entity["name"] = value.strip()
                break
        else:
            # Preference order: a semantic key names the thing; an opaque
            # generated id names nothing, so fall back to the kind rather than
            # either showing the player "10Ae6B6A11324780" or failing the turn
            # over a missing required field.
            derived = (_entity_name_from_key(key)
                       or str(entity.get("kind") or "").strip().title()
                       or "Object")
            entity["name"] = derived


def _unwrap_envelope(step_key, raw):
    """A model that wrapped its whole answer in one key of its own.

    Observed live on an opening turn: `director_establish` returned
    `{"the_director_outputs": {"location": ..., "rooms": ..., "positions":
    ...}}` -- every declared field present and correct, one level too deep.
    Nothing looked inside, so the step failed as "rooms is empty; positions
    is empty", which reads as a model that answered nothing when it had in
    fact answered everything. The repair prompt was handed that same false
    complaint and returned the same envelope, and the turn died.

    Unwrapped only when it is unambiguous: exactly one key, that key is NOT
    itself a field of this step's schema, and the object under it does carry
    fields the schema declares. A single legitimate field (`{"response":
    "..."}`) is left alone, and so is an envelope whose contents this step
    does not recognise -- that is a real disagreement and belongs in the
    error, not in a guess.
    """
    if len(raw) != 1:
        return raw
    key, inner = next(iter(raw.items()))
    if not isinstance(inner, dict) or not inner:
        return raw
    model_cls = SCHEMA_MAP.get(step_key)
    if model_cls is None:
        return raw
    fields = set(_fields(model_cls) or {})
    if key in fields or not (set(inner) & fields):
        return raw
    return inner


# ---------------------------------------------------------------------------
# Inline markup in narration
# ---------------------------------------------------------------------------
# WE OPENED THIS DOOR ON PURPOSE AND THEN WERE SURPRISED BY WHAT CAME THROUGH.
# The paragraph contract asks the narrator for `<p>...</p>` and the comment
# under it says exactly why that marker and not a private token: "the model has
# seen a billion <p> tags", where `[[P]]` returned an empty prose field and
# `[[BREAK]]` silently dropped two speakers' lines. Familiarity is what made it
# work -- and familiarity does not stop at one tag. Told that this channel
# speaks HTML, the narrator reasonably concluded that it speaks HTML, and began
# emitting `<i>` for a thought the prose voices rather than quotes. It is good
# writing and it landed on the page as literal angle brackets.
#
# So the set is CLOSED HERE rather than guessed at downstream. Three outcomes,
# no fourth: a tag is canonical (rewritten to one spelling), or it is
# decoration this engine has no use for (removed, text kept), or it is a
# container whose CONTENT is not prose (removed with its content). Nothing
# reaches storage, the archive, the fidelity checks or the page as a literal
# tag, whatever the model reaches for next.
#
# The rules the `<p>` handler already established, applied here too:
#   * NO TEXT IS EVER DROPPED for a markup reason. A stray tag costs its own
#     characters and nothing else -- never a word, never a sentence.
#   * Unmatched canonical tags are REMOVED, not left in place. An opener with
#     no closer is a typo, and honouring it would italicise the rest of a beat.
#   * Escaped markup stays escaped: tags are stripped BEFORE entities are
#     decoded, so `&lt;i&gt;` renders as the characters the narrator wrote and
#     cannot be promoted into a tag on the way past.
#
# What survives is a short list chosen for FICTION, not for the web: emphasis,
# strength, a struck-through correction, an underline, a highlight, sub/sup,
# and a monospaced readout (a console, a ship's log). Everything else -- links,
# spans, headings, lists, rules, quotes, abbreviations, bidi controls -- is
# decoration around prose that already reads fine without it.
_PROSE_MARK_TAGS = {
    "i": "i", "em": "i", "cite": "i", "dfn": "i", "var": "i", "address": "i",
    "b": "b", "strong": "b",
    "u": "u", "ins": "u",
    "s": "s", "del": "s", "strike": "s",
    "mark": "mark",
    "sup": "sup", "sub": "sub",
    "code": "code", "kbd": "code", "samp": "code", "tt": "code",
    "font": "font",
}
#: COLOUR IS A VOCABULARY, NOT A VALUE. `<font color="#3af">` reads on one
#: ground and vanishes on another -- this engine has five themes including a
#: pure-black console and a parchment tavern -- so the narrator names an
#: INTENT and each theme supplies the ink. Every bucket resolves to a token
#: every theme already defines, so a colour cannot be invisible anywhere.
#: An unrecognised colour is not an error: the tags are dropped and the words
#: stay, exactly like any other decoration.
_PROSE_INK = {
    "red": "red", "crimson": "red", "scarlet": "red", "blood": "red",
    "amber": "amber", "orange": "amber", "gold": "amber", "yellow": "amber",
    "green": "green", "emerald": "green", "lime": "green",
    "blue": "blue", "cyan": "blue", "teal": "blue", "azure": "blue",
    "violet": "violet", "purple": "violet", "magenta": "violet",
    "pink": "violet", "indigo": "violet",
    "grey": "grey", "gray": "grey", "silver": "grey", "faint": "grey",
}
_PROSE_COLOR_ATTR_RE = re.compile(
    r"""\bcolor\s*[:=]\s*["']?\s*([A-Za-z]+)""", re.I)
#: Elements whose CONTENT is not narration. `rt`/`rp` are ruby annotations --
#: keeping them inline welds a pronunciation gloss into the middle of a word
#: ("漢字かんじ"), so the base text survives and the reading is dropped rather
#: than corrupting the sentence. The rest can only arrive by accident.
_PROSE_DROP_CONTENT = frozenset({
    "script", "style", "rt", "rp", "head", "title", "template", "noscript",
})
#: `<br>` is the one tag that IS text: it means a line break, prose renders
#: with `white-space: pre-wrap`, and a newline is what the reader should see.
_PROSE_TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>")


_PROSE_FONT_RE = re.compile(r'<font color="(\w+)">(.*?)</font>', re.S)


def _quoted_regions(text):
    """Spans between paired quote marks, both marks included.

    Tag interiors are masked first, at equal length so every offset still
    means what it meant. Without it `color="red"` reads as a quoted line and
    the colour attribute deletes the colour it declares -- which is exactly
    what it did.
    """
    text = re.sub(r"<[^>]*>", lambda m: "\x02" * len(m.group(0)), text)
    regions, start = [], None
    for index, char in enumerate(text):
        if start is None:
            if char in '"“':
                start = index
        elif char in '"”':
            regions.append((start, index + 1))
            start = None
    return regions


def _drop_ink_in_dialogue(text):
    """Colour is the narration's, never a spoken line's.

    A SPEAKER ALREADY HAS A COLOUR, and it is not the narrator's to choose:
    `chat.js:paintProse` tints each quoted line from the reader's own
    per-speaker palette. A `<font>` reaching inside a quote either fights that
    tint or silently replaces it, and either way the page stops meaning what
    the colour legend says it means.

    Enforced here rather than asked for in the prompt, because a rule the
    model has to remember is a rule that holds most of the time. The tags go
    and every word stays -- the same trade the rest of this function makes.
    """
    if "<font" not in text:
        return text
    quotes = _quoted_regions(text)
    if not quotes:
        return text

    out, cursor = [], 0
    for match in _PROSE_FONT_RE.finditer(text):
        if match.start() < cursor:
            continue
        overlaps = any(match.start() < end and start < match.end()
                       for start, end in quotes)
        if not overlaps:
            continue
        out.append(text[cursor:match.start()])
        out.append(match.group(2))
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out)


def canonicalize_prose_markup(raw):
    """Reduce narrator prose to plain text plus a closed set of inline tags.

    Returns the cleaned string. Idempotent: running it on its own output
    changes nothing, which matters because prose is also editable by hand and
    a saved edit passes through here again on the next validated write.
    """
    text = str(raw or "")
    if "<" not in text and "&" not in text:
        return text

    marks = list(_PROSE_TAG_RE.finditer(text))

    # Pass 1 -- spans whose content is not prose. Nested opens of the same
    # element are counted so an inner one cannot close the outer early.
    dropped = []
    index = 0
    while index < len(marks):
        mark = marks[index]
        name = mark.group(1).lower()
        if name in _PROSE_DROP_CONTENT and not mark.group(0).startswith("</"):
            depth, cursor = 1, index + 1
            while cursor < len(marks) and depth:
                other = marks[cursor]
                if other.group(1).lower() == name:
                    depth += -1 if other.group(0).startswith("</") else 1
                cursor += 1
            end = (marks[cursor - 1].end() if depth == 0 and cursor
                   else len(text))
            dropped.append((mark.start(), end))
            index = cursor
            continue
        index += 1

    def _inside_dropped(position):
        return any(start <= position < end for start, end in dropped)

    live = [m for m in marks if not _inside_dropped(m.start())]

    # Pass 2 -- which canonical tags are a matched pair. Everything else is
    # removed, so an unclosed `<i>` costs four characters rather than the rest
    # of the beat.
    # Keyed by offset rather than by position in the list: the emission loop
    # below walks `marks`, not `live`, so an index into one is not an index
    # into the other and an offset is the only thing that means the same in
    # both.
    stack, paired, inks = [], set(), {}
    for mark in live:
        name = _PROSE_MARK_TAGS.get(mark.group(1).lower())
        if name is None:
            continue
        if not mark.group(0).startswith("</"):
            if name == "font":
                found = _PROSE_COLOR_ATTR_RE.search(mark.group(0))
                ink = _PROSE_INK.get(found.group(1).lower()) if found else None
                if ink is None:
                    continue    # unpaired, so both tags fall away with it
                inks[mark.start()] = ink
            stack.append((mark.start(), name))
            continue
        for depth in range(len(stack) - 1, -1, -1):
            if stack[depth][1] == name:
                paired.add(stack[depth][0])
                paired.add(mark.start())
                del stack[depth:]
                break

    out, cursor = [], 0
    for mark in marks:
        if mark.start() < cursor:
            continue
        out.append(text[cursor:mark.start()])
        cursor = mark.end()
        if _inside_dropped(mark.start()):
            span = next(s for s in dropped if s[0] <= mark.start() < s[1])
            cursor = max(cursor, span[1])
            continue
        name = mark.group(1).lower()
        if name == "br":
            out.append("\n")
        elif name in _PROSE_MARK_TAGS and mark.start() in paired:
            canonical = _PROSE_MARK_TAGS[name]
            if mark.group(0).startswith("</"):
                out.append("</%s>" % canonical)
            elif canonical == "font":
                out.append('<font color="%s">' % inks[mark.start()])
            else:
                out.append("<%s>" % canonical)
    out.append(text[cursor:])

    # Entities LAST, so nothing decoded here can be read as a tag above --
    # EXCEPT the two that would become one. `&lt;i&gt;` is a narrator writing
    # ABOUT a tag, and decoding it here would hand the renderer a real pair to
    # italicise, which is the promotion this ordering exists to prevent. So
    # angle brackets stay encoded through storage and the frontend decodes
    # them inside text nodes only, after it has finished finding tags: the
    # same rule as this function, applied at the other end.
    joined = _drop_ink_in_dialogue("".join(out))
    joined = joined.replace("\x00", "").replace("\x01", "")
    joined = joined.replace("&lt;", "\x00").replace("&gt;", "\x01")
    return (html.unescape(joined)
            .replace("\x00", "&lt;").replace("\x01", "&gt;"))


def _addressee_refs(flow):
    """Every spelling of "the person this beat is addressed to".

    Both lists, because they are the same audience in two encodings:
    `addressed_to` is int-coerced cast ids, `addressed_to_refs` preserves the
    raw entries (a NAME string there is the only way to address an
    unregistered background presence). `conceal_from` is written by the same
    model in whichever of those spellings it reached for, plus the
    `character:<id>` form the perception matchers already accept.
    """
    refs = set()
    for value in (list(flow.get("addressed_to") or [])
                  + list(flow.get("addressed_to_refs") or [])):
        text = str(value).strip().casefold()
        if text:
            refs.add(text)
            refs.add(f"character:{text}")
    return refs


def _uncross_concealed_speech(result, flow):
    """A line cannot be concealed from the person it is addressed to.

    THE FIELD IS AN EXCLUDED AUDIENCE, and the model fills it with whatever
    ids it is holding -- which, for a whisper to the only other person
    present, is the addressee. Live: chat 73 t2480, Hinami whispering to The
    Doctor with `addressed_to: [58]` and `conceal_from: [58]` on the same
    speech event. The Doctor's whole view of the beat was that he could SEE
    her leaning in, and FEEL her lips against his ear -- "steady pressure,
    weight and shared warmth" -- and did not receive the words. The
    felt-but-not-seen path, firing on the one mind the line was for. It ran
    on both whisper beats in that chat, and on 3 of the 24 turns in the
    corpus that use concealment at all.

    NOT REPAIRABLE BY CLEARING THE LIST. An empty `conceal_from` does not
    mean "exclude nobody" -- `composer.concealed_from_observer` and
    `perception._concealed_from_perceiver` both read empty as hidden from
    every non-actor, so emptying it hides the line from the room as well.
    When the addressee was the only entry, the event stops being concealed
    at all and physical audibility decides instead: `hear_level` against a
    `whisper` volume already reaches someone at arm's reach and already
    fails to cross a hall, which is the deterministic floor this field was
    standing in front of.

    SPEECH ONLY, deliberately. Concealing an ACTION from the person you are
    addressing is ordinary and load-bearing -- picking the pocket of someone
    you are talking to is exactly that shape -- so actions are left alone.
    There is no corresponding legitimate reading for a line: "I say this to
    you, and you do not hear it" is not a thing a beat can mean.
    """
    refs = _addressee_refs(flow)
    sequence = result.get("sequence")
    if not refs or not isinstance(sequence, list):
        return []

    notes = []
    for event in sequence:
        if not isinstance(event, dict) or event.get("type") != "speech":
            continue
        if str(event.get("visibility") or "").strip().lower() != "concealed":
            continue
        listed = [value for value in (event.get("conceal_from") or [])
                  if str(value or "").strip()]
        if not listed:
            continue
        kept = [value for value in listed
                if str(value).strip().casefold() not in refs]
        if len(kept) == len(listed):
            continue
        dropped = ", ".join(
            str(value) for value in listed
            if str(value).strip().casefold() in refs
        )
        event["conceal_from"] = kept
        if kept:
            notes.append(
                f"speech concealed from its own addressee ({dropped}); "
                f"dropped from conceal_from, {len(kept)} excluded remain"
            )
        else:
            # Emptied. Leaving it concealed would hide the line from
            # EVERYONE, which is the worse half of the same bug.
            event["visibility"] = "overt"
            notes.append(
                f"speech concealed from its own addressee ({dropped}) and "
                f"from nobody else; concealment dropped, audibility left to "
                f"volume and distance"
            )
    return notes


def preprocess_llm_output(step_key: str, raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}

    result = dict(_unwrap_envelope(step_key, raw))

    if step_key in ("mapping_stage", "mapping_quick"):
        _flatten_staged_lore(result)

    if step_key == "mapping_stage":
        patch = result.get("scene_patch")
        if isinstance(patch, dict):
            _hoist_misplaced_entity_siblings(patch, _SCENE_PATCH_SIBLING_FIELDS)
            for field in ("remove_entities", "remove_rooms", "remove_adjacent"):
                if field in patch:
                    patch[field] = _coerce_empty_dict_to_list(patch[field])
            # ScenePatch.entities is untyped so a missing name does not fail
            # validation here -- but it lands in the scene, where readers key
            # display name -> entity id (commit.track_background_presences,
            # agents/background._name_to_entity_id). A nameless entity is
            # invisible to both.
            _fill_entity_names(patch)

    if step_key == "narrator":
        # PARAGRAPHS ARE MARKED WITH <p>...</p> AND RENDERED HERE.
        #
        # Two earlier contracts failed, both measured. Asking for a blank line
        # -- a literal `\n\n` inside the JSON string -- ran for a week and
        # reached 6 of 600 stored narrations (1%). Asking for a `paragraphs`
        # ARRAY did worse: `paragraph_count` was 0 on every live variant,
        # because the model never emitted the field at all.
        #
        # What both had in common is that they asked the model to change the
        # SHAPE of its reply. A delimiter does not: it is characters inside a
        # string it was already writing, needing no JSON escape and no new
        # key. Benched against the live narrator model on a three-speaker beat
        # (`tools/paragraph_bench.py`): the array contract produced multiple
        # paragraphs 2 times in 5, `<p>` produced them 10 times in 10 with
        # every tag balanced.
        #
        # <p> SPECIFICALLY, not a private token. `[[P]]` came back with the
        # prose field EMPTY and `[[BREAK]]` silently dropped two speakers'
        # lines -- an unfamiliar marker does not get politely ignored, it
        # damages the output. The model has seen a billion <p> tags.
        #
        # Everything downstream still receives exactly one `prose` string with
        # blank lines in it, so the semantic check, the fidelity checks, the
        # correction-notes retry, commit, the archive and the frontend are
        # untouched by this.
        raw_prose = result.get("prose")
        if isinstance(raw_prose, str) and "<p" in raw_prose.lower():
            # EVERY TAG IS A BOUNDARY, AND NO TEXT IS EVER DROPPED. The first
            # version of this extracted <p>...</p> matches and rebuilt the
            # prose from them, which silently deleted anything the model wrote
            # OUTSIDE a pair -- and a model that half-marks its output is
            # exactly the case this has to survive. Splitting on the tags
            # instead keeps every word: a stray or unbalanced tag costs a
            # paragraph break in an odd place, never a sentence.
            marked = re.sub(r"</?p\b[^>]*>", "\x00", raw_prose, flags=re.I)
            blocks = [b.strip() for b in marked.split("\x00")]
            blocks = [b for b in blocks if b]
            if blocks:
                result["prose"] = "\n\n".join(blocks)
                result["paragraph_count"] = len(blocks)

        # AND EVERY OTHER TAG, decided in this one place. `<p>` is consumed
        # above because it means a paragraph and the engine has a paragraph;
        # the rest of what the narrator reaches for is handled here, in the
        # same breath and under the same rule -- no text is ever dropped for a
        # markup reason. See `canonicalize_prose_markup`: the tags that survive
        # are a closed set with one spelling each, and nothing outside it can
        # reach storage, the archive or the page.
        # AFTER the paragraph pass, never before: that one splits on `<p>`
        # boundaries to guarantee no word is lost, and it can only do that
        # while the boundaries are still there.
        if isinstance(result.get("prose"), str):
            result["prose"] = canonicalize_prose_markup(result["prose"])

        # HOW MANY PARAGRAPHS THE MODEL ACTUALLY MARKED, engine-written and
        # never asked for. Without it, "the model ignored the markers" and
        # "the model marked the whole beat as one paragraph" are the same
        # single unbroken string in storage, and the next report of flat prose
        # is unanswerable without another live turn. 0 means no markers came
        # back at all.
        result.setdefault("paragraph_count", 0)

        # new_specifics is list[str] -- proper nouns/hard facts the
        # narrator coined this turn. Same over-structuring failure mode as
        # perception's views: a model occasionally reports one as a nested
        # object instead of a bare string. Flatten rather than reject.
        specifics = result.get("new_specifics")
        if isinstance(specifics, list):
            result["new_specifics"] = [
                flat for flat in (_flatten_view_value(x) for x in specifics)
                if flat
            ]

    if step_key in SPECIALIST_CHANNELS:
        # A specialist's instruction blocks are shared verbatim with the
        # full Director sheet, which says "state_diff.<channel>" -- so a
        # model will sometimes wrap its channels in a state_diff (or, on
        # the interpret side, state_assertions) envelope despite the core
        # saying not to. Deterministic unwrap, then the same coercions the
        # resolve diff gets for the same fields.
        channels = SPECIALIST_CHANNELS[step_key]
        for envelope in ("state_diff", "state_assertions"):
            wrapped = result.get(envelope)
            if isinstance(wrapped, dict) and not any(
                    k in result for k in channels):
                notes = result.get("notes")
                result = dict(wrapped)
                if notes is not None and "notes" not in result:
                    result["notes"] = notes
                break
        if "conditions" in channels and "conditions" in result:
            result["conditions"] = _coerce_conditions(result["conditions"])
        for field in channels:
            if field not in result:
                continue
            if field in _SPECIALIST_DICT_CHANNELS:
                result[field] = _coerce_empty_list_to_dict(result[field])
            elif field in _SPECIALIST_LIST_CHANNELS:
                result[field] = _coerce_empty_dict_to_list(result[field])
        if "entities" in channels:
            # The specialist's own sibling fields, written one nesting level
            # too deep inside `entities`, must come OUT before names are
            # filled -- the resolve diff has had this hoist for ages, but the
            # specialist path did not, which is how chat 80 turn 1 committed
            # six "entities" keyed remove_entities/inventory_ops/artifact_ops/
            # destruction/notes/resolved_events, each a copy of the Interview
            # Chair. The sibling set is the model's own declared fields, so a
            # channel added later is covered automatically.
            model_cls = SCHEMA_MAP.get(step_key)
            siblings = tuple(k for k in (_fields(model_cls) or {})
                             if k != "entities")
            _hoist_misplaced_entity_siblings(result, siblings)
            # SceneEntityDef.name is required but the dict key already
            # carries it; recover rather than fail the call (the same
            # recovery the resolve diff gets).
            _fill_entity_names(result)

    if step_key in ("director_resolve", "director_establish", "resolve_repair"):
        target = result
        if step_key in ("director_resolve", "resolve_repair"):
            state_diff = result.get("state_diff")
            target = state_diff if isinstance(state_diff, dict) else None
            if target is not None:
                _hoist_misplaced_entity_siblings(target, _STATE_DIFF_SIBLING_FIELDS)
            if target is not None and "conditions" in target:
                target["conditions"] = _coerce_conditions(target["conditions"])
            if target is not None and "time" in target:
                target["time"] = _coerce_optional_time(target["time"])
        if isinstance(target, dict):
            for field in _STATE_DIFF_DICT_FIELDS:
                if field in target:
                    target[field] = _coerce_empty_list_to_dict(target[field])
            # SceneEntityDef.name is required but the dict key already carries
            # it; recover rather than fail the turn.
            _fill_entity_names(target)
    
    if "speech_volume" in result:
        result["speech_volume"] = normalize_speech_volume(
            result.get("speech_volume")
        )

    sequence = result.get("sequence")
    if isinstance(sequence, list):
        cleaned_sequence = []

        for event in sequence:
            if isinstance(event, str):
                event = _sequence_event_from_prose(event)
            if not isinstance(event, dict):
                continue

            event = dict(event)

            if event.get("type") == "speech":
                event["volume"] = normalize_speech_volume(
                    event.get("volume")
                )

            cleaned_sequence.append(event)

        result["sequence"] = _kept("sequence", sequence, cleaned_sequence)

    if "considered_responses" in result:
        result["considered_responses"] = _coerce_considered_responses(
            result.get("considered_responses")
        )

    dialogue_log = result.get("dialogue_log")
    if isinstance(dialogue_log, list):
        cleaned_dialogue = []

        for line in dialogue_log:
            # A weak model may emit a bare "Speaker: quote" string instead of
            # an object; dropping it (as we used to) silently erased the beat's
            # dialogue, leaving DIALOGUE FIDELITY nothing to protect.
            if isinstance(line, str):
                text = line.strip()
                if not text:
                    continue
                # X14: preserve concealment markers a weak model may embed
                # in a string line (e.g. "[concealed] Sarah: I know").
                line_visibility = "overt"
                m = re.match(r'^\s*\[(concealed|overt)\]\s*(.*)', text, re.IGNORECASE)
                if m:
                    line_visibility = m.group(1).lower()
                    text = m.group(2)
                if ":" in text and len(text.split(":", 1)[0]) <= 60:
                    spk, quote = text.split(":", 1)
                    line = {"speaker": spk.strip(), "exact_quote": quote.strip().strip('"\'')}
                else:
                    line = {"speaker": "unknown", "exact_quote": text}
                line["visibility"] = line_visibility
            if not isinstance(line, dict):
                continue

            line = dict(line)
            # Alias common key variants a model reaches for onto the schema's
            # required exact_quote / speaker (parallel to the volume path).
            if not line.get("exact_quote"):
                for alias in ("quote", "text", "line", "content", "utterance"):
                    if line.get(alias):
                        line["exact_quote"] = line[alias]
                        break
            if not line.get("speaker"):
                line["speaker"] = line.get("name") or line.get("who") or "unknown"
            line["volume"] = normalize_speech_volume(line.get("volume"))
            # X14: normalize visibility so a concealed line survives the
            # coercion intact. Without this, visibility from the original
            # entry is silently dropped for string lines and unrecognized
            # variants on dict lines, defaulting to "overt" downstream.
            vis = str(line.get("visibility") or "").strip().lower()
            if vis in ("concealed", "hidden", "secret"):
                line["visibility"] = "concealed"
            else:
                line.setdefault("visibility", "overt")
            if not isinstance(line.get("conceal_from"), list):
                line["conceal_from"] = []
            if str(line.get("exact_quote") or "").strip():
                cleaned_dialogue.append(line)

        result["dialogue_log"] = _kept(
            "dialogue_log", dialogue_log, cleaned_dialogue)

    if step_key == "director_interpret":
        flow_raw = result.get("flow")
        flow = flow_raw if isinstance(flow_raw, dict) else {}

        reactors = flow.get("reactors")
        if not isinstance(reactors, list):
            reactors = []

        addressed_to = flow.get("addressed_to")
        if not isinstance(addressed_to, list):
            addressed_to = []

        tom_triggers = flow.get("tom_triggers")
        if not isinstance(tom_triggers, list):
            tom_triggers = []

        resolution_flags = flow.get("resolution_flags")
        if not isinstance(resolution_flags, dict):
            resolution_flags = {}

        dice = flow.get("dice")
        if not isinstance(dice, list):
            dice = []

        generation_requests = flow.get("generation_requests")
        if not isinstance(generation_requests, list):
            generation_requests = []

        authority_claims = flow.get("authority_claims")
        if not isinstance(authority_claims, list):
            authority_claims = []

        fiction_frame = flow.get("fiction_frame")
        if not isinstance(fiction_frame, dict):
            fiction_frame = {}

        flow["reactor_refs"] = list(reactors)
        flow["tom_trigger_refs"] = list(tom_triggers)
        # Raw refs preserved BEFORE int coercion: a name string here is the
        # only way the director can address an UNREGISTERED background
        # presence (commit.pick_background_reactors forces it to answer).
        flow["addressed_to_refs"] = list(addressed_to)
        flow["reactors"] = _coerce_int_list(reactors)
        flow["tom_triggers"] = _coerce_int_list(tom_triggers)
        flow["addressed_to"] = _coerce_int_list(addressed_to)
        flow["resolution_flags"] = resolution_flags
        flow["dice"] = [
            item for item in dice if isinstance(item, dict)
        ]
        flow["generation_requests"] = [
            item for item in generation_requests
            if isinstance(item, dict)
        ]
        flow["authority_claims"] = [
            item for item in authority_claims
            if isinstance(item, dict)
        ]
        flow["fiction_frame"] = fiction_frame

        result["flow"] = flow

        repairs = _uncross_concealed_speech(result, flow)
        if repairs:
            result["concealment_repairs"] = repairs

        # Extra players get the same speech-volume normalization the primary
        # player's sequence already gets (schemas.py above) -- otherwise a
        # co-player's out-of-enum volume either hard-fails or survives raw and
        # is read as inaudible by hear_level. Also tolerate other_players:null.
        others = result.get("other_players")
        if not isinstance(others, dict):
            result["other_players"] = {}
        else:
            for pid, decl in list(others.items()):
                if not isinstance(decl, dict):
                    continue
                if "speech_volume" in decl:
                    decl["speech_volume"] = normalize_speech_volume(decl.get("speech_volume"))
                seq = decl.get("sequence")
                if isinstance(seq, list):
                    # A co-player's beat gets the same reading as the
                    # primary player's, including a sentence where an event
                    # object was declared. Anything else leaves one player's
                    # prose recovered and another's discarded, in the same
                    # payload, for no reason either of them could see.
                    cleaned = []
                    for ev in seq:
                        if isinstance(ev, str):
                            ev = _sequence_event_from_prose(ev)
                        if not isinstance(ev, dict):
                            continue
                        if ev.get("type") == "speech":
                            ev["volume"] = normalize_speech_volume(ev.get("volume"))
                        cleaned.append(ev)
                    decl["sequence"] = cleaned

    return result

def validate_llm_output(step_key: str, raw: dict) -> tuple[dict, list[str]]:
    model_cls = SCHEMA_MAP.get(step_key)
    if not isinstance(raw, dict):
        raw = {}
    prepared = preprocess_llm_output(step_key, raw)
    # A deterministic repair the operator should SEE. It means the guard
    # worked, which is the only reason it is a warning and not a silence.
    repairs = [str(note) for note in (prepared.get("concealment_repairs") or [])]
    if not model_cls:
        return prepared, repairs
    try:
        model = _validate(model_cls, prepared)
        return _dump(model), repairs
    except ValidationError as exc:
        warnings = repairs + [f"Schema validation warning: {len(exc.errors())} errors"]
        for error in exc.errors()[:5]:
            location = ".".join(str(part) for part in error.get("loc", []))
            warnings.append(f"  {location}: {error.get('msg', '')}")
        if step_key == "director_interpret":
            flow = prepared.get("flow")
            if not isinstance(flow, dict):
                flow = {}
            if not isinstance(flow.get("resolution_flags"), dict):
                flow["resolution_flags"] = {}
            for key in ("reactors", "addressed_to", "tom_triggers", "dice",
                        "generation_requests", "authority_claims"):
                if not isinstance(flow.get(key), list):
                    flow[key] = []
            if not isinstance(flow.get("fiction_frame"), dict):
                flow["fiction_frame"] = {}
            prepared["flow"] = flow
        return prepared, warnings
        
@dataclass
class ValidationReport:
    valid: bool
    output: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

OUTPUT_EXAMPLES = {
    "director_interpret": {
        "kind": "mixed",
        "sequence": [],
        "speech": None,
        "speech_volume": "normal",
        "private_thought": None,
        "action": None,
        "actions": [],
        "movement": None,
        "location_query": None,
        "flow": {
            "reactors": [],
            "addressed_to": [],
            "dialogue_mode": False,
            "needs_mapping": False,
            "mapping_request": "",
            "dice": [],
            "tom_triggers": [],
            "resolution_flags": {
                "contested": False,
                "possible_reactors": [],
            },
            "authority_claims": [],
            "fiction_frame": {},
            "generation_requests": [],
        },
        "notes": "",
    },
    "director_establish": {
        # The one example that has to be a WORKED scene rather than a bare
        # shape. Establishment's semantic check requires rooms and positions
        # -- an opening in no place, with nobody anywhere, is not an opening
        # -- so an all-empty example is an object this stage's own validator
        # rejects, handed to the model as the thing to imitate on the repair
        # that follows exactly that failure.
        "location": "The Salt Quay",
        "time": "before dawn",
        "scene_description": (
            "Fog off the water, one lamp still burning at the head of the "
            "pier."),
        "rooms": {
            "pier_head": {
                "name": "Pier Head",
                "desc": "Wet boards, a bollard, the lamp on its iron post.",
                "adjacent": [{"room": "quay_road", "barrier": "open"}],
                "exposure": "open",
                "anchors": {"lamp_post": {"desc": "the iron lamp post"}},
            },
            "quay_road": {
                "name": "Quay Road",
                "desc": "A cobbled run of shuttered warehouses.",
                "adjacent": [{"room": "pier_head", "barrier": "open"}],
                "exposure": "open",
            },
        },
        "entities": {},
        "positions": {"{{PLAYER}}": "pier_head", "Maren": "pier_head"},
        "stations": {"Maren": {"at": "lamp_post", "near": []}},
        "poses": {},
        "contact_ops": [],
        "substance_ops": [],
        "attire": {},
        "entity_states": {},
        "sensory_events": [],
        "world_facts": [],
        "fiction_frame": {},
        "simulation_clock": {
            "elapsed_seconds": 0.0,
            "display": "before dawn",
            "time_scale": "scene",
        },
        "opening": (
            "The fog has not lifted. Maren waits under the lamp at the head "
            "of the pier, watching the water rather than the road."),
    },
    # This is the PROSE AUTHOR's example -- `director_resolve` is the step
    # key its call runs under. It owns the beat's prose, its dialogue, the
    # manifest and six `state_diff` channels; the other twenty-nine belong to
    # the six specialists, whose own examples are below. So it shows those six
    # and nothing else: a channel in this example that the author no longer
    # owns is an instruction to spend the beat encoding something a specialist
    # is being asked for in the same fan-out, and whatever it writes there is
    # replaced by the owner anyway.
    "director_resolve": {
        "resolved_event": (
            "Maren turns from the water as you reach the lamp. \"You're "
            "late,\" she says. \"The boat went out an hour ago.\""),
        "summary": "Maren says the boat left an hour ago",
        "dialogue_order": ["Maren"],
        "dialogue_log": [
            {"speaker": "Maren",
             "exact_quote": "You're late. The boat went out an hour ago.",
             "volume": "normal", "intended_target": "{{PLAYER}}",
             "tone": "flat"},
        ],
        "state_diff": {
            "location": "Pier Head",
            # THE SHAPE, NOT A PLACEHOLDER. This was `None`, and the resolve
            # prompt describes the field in prose two thousand lines away
            # ("Emit state_diff.time with start_seconds, duration_seconds,
            # end_seconds, mode ('action'|'time_skip'), explicit (bool), and
            # display_advance"). A model that reads the EXAMPLE sees a scalar
            # and sends one -- live, GLM-5.2 sent a string and the turn died on
            # `state_diff.time: value is not a valid dict`.
            #
            # Worse, this same example is the `required_json_example` handed to
            # the repair attempt, so the repair was shown the identical `null`
            # and had no way to converge. One malformed field killed the whole
            # beat twice over. Same class as the `ratified_claims` defect, one
            # step further: not described-but-never-shown, but described one
            # way and SHOWN AS ANOTHER TYPE.
            "time": {"start_seconds": 0, "duration_seconds": 60,
                     "end_seconds": 60, "mode": "action",
                     "explicit": False, "display_advance": ""},
            # Written OVER the sky already blowing, so a beat reports what it
            # noticed rather than restating the whole sky.
            "weather": {"sky": "fog", "precipitation": "none",
                        "intensity": "none", "wind": "breeze",
                        "temperature": "cold"},
            "claim_dispositions": [],
            # Set in motion OFFSCREEN, fired when the clock reaches it --
            # never this beat's own outcome, which is the prose above.
            "consequences": [
                {"what": "the harbourmaster's office opens for the morning",
                 "where": "quay_road", "due_seconds": 5400,
                 "witnessed": False},
            ],
        },
        # The manifest is where a change lands whose CHANNEL belongs to
        # somebody else: the author narrated her turning, the body specialist
        # owns `poses`, and this is how the two meet.
        "changes_asserted": [
            {"category": "pose", "subject": "Maren",
             "change": "Maren has turned from the water to face you."},
        ],
        "dice": [],
        "fiction_frame": {},
        "obligations": [
            {"op": "open", "who": "Merek", "what": "deliver the survey "
             "report Captain Hale demanded", "kind": "demand"},
        ],
        "fact_adjudications": [
            {"claim_id": "claim:0:event", "claim": "the crew on deck 12 "
             "are dead", "subject": "deck 12 crew", "verdict": "confirmed",
             "landing": "the medic confirms the deaths on-page"},
        ],
    },
    "director_body": {
        "attire": {
            "Mara": {"add": [], "remove": ["wool coat"], "replace": None,
                     "state": None, "conditions": {},
                     "coverage": {}},
        },
        "conditions": {
            "mara_forearm_cut": [
                {"condition_id": "mara_forearm_cut", "subject_id": "Mara",
                 "kind": "wound", "severity": 0.2,
                 "started_at_seconds": 0.0, "tick_interval_seconds": 0,
                 "state": {"detail": "a shallow cut across the forearm"}},
            ],
        },
        "vitals": {},
        "overlays": {},
        "notes": [],
    },
    "director_social": {
        "cast_changes": [
            {"who": "Merek", "status": "dormant",
             "reason": "rode for the garrison"},
        ],
        "introductions": [{"who": "Mara", "learns": "Sable"}],
        "world_facts": [],
        "notes": [],
    },
    "director_contact": {
        "contact_ops": [
            {"op": "add", "actor": "Mara", "actor_part": "hand",
             "target": "Sable", "target_part": "shoulder",
             "manner": "rest", "relation": "surface", "motion": "settled"},
        ],
        # Matter that landed somewhere is the commonest smell in play, and
        # `scent` had to be SHOWN rather than only described: this was `[]`,
        # and an empty list teaches the shape of nothing.
        "substance_ops": [
            {"op": "add", "source": "Mara", "source_part": "forearm",
             "substance": "blood", "target": "lamp_room",
             "placement": "room", "amount": "a few drops",
             "scent": "wet iron"},
        ],
        "containment": {},
        "scales": {},
        "notes": [],
    },
    "director_objects": {
        "entities": {
            "storm_lantern": {"name": "Storm Lantern", "kind": "object",
                              "description": "a brass storm lantern",
                              "aliases": [], "portable": True,
                              "container": False, "interior_rooms": [],
                              "state": {"lit": True},
                              # A lit lamp is the smallest honest scent
                              # example: the thing that emits light emits
                              # something on the other channel too, and a
                              # field shown as absent in the object a repair
                              # is told to imitate reads as "not part of the
                              # answer" -- what `ratified_claims` and
                              # `state_diff.time` each cost a beat for.
                              "scent": "hot brass and lamp oil"},
        },
        "remove_entities": [],
        "inventory_ops": [],
        "artifact_ops": [],
        "destruction": None,
        "notes": [],
    },
    "director_spatial": {
        "positions": {"Mara": "lamp_room"},
        "rooms": {},
        "remove_rooms": [],
        "remove_adjacent": [],
        "stations": {"Mara": {"at": "the_lamp", "near": []}},
        "poses": {},
        # Equipment that carries a VOICE between places, which is a spatial
        # fact about the rooms it joins rather than an object in one of them.
        "comms_ops": [
            {"id": "gallery_intercom", "op": "open",
             "name": "the gallery intercom",
             "rooms": ["lamp_room", "gallery"], "carriers": [],
             "mode": "voice", "source": "", "private": False, "live": True},
        ],
        "notes": [],
    },
    "director_offscreen": {
        "crowd_ops": [
            {"op": "set", "crowd_id": "", "room": "market_square",
             "band": "a few dozen", "composition": "market-goers",
             "mood": "wary"},
        ],
        "courier_ops": [],
        "telling_ops": [],
        "offscreen_plan_ops": [],
        "ratified_claims": [],
        "contradicted_claims": [],
        "notes": [],
    },
    "character": {
        "observations_used": [],
        "present_evidence_used": [],
        "memory_evidence_used": [],
        "appraisal": {},
        "considered_responses": [],
        "response_candidates": [],
        "sequence": [],
        "contact_ops": [],
        "material_effects": [],
        "active_state": {},
        # The psychology tier. The sheet asks for all five and the example
        # named none of them, and an absent key in the object a repair is told
        # to imitate reads as "not part of the answer" -- which is how a whole
        # tier can be asked for on every call and arrive on none of them.
        # Shown at their nothing-this-beat values, like every other key here:
        # what the fields ARE is the sheet's to say, and an example that
        # decided a project or a following change for the character would be
        # the example making the decision.
        "intent_ops": [],
        "project_ops": [],
        "follow_op": None,
        "drive_shift": None,
        "manifest": {"surface_demeanor": "", "tells": []},
        "belief_updates": [],
        "association_updates": [],
        "mind_model_updates": [],
        "relationship_updates": [],
        "remember_lines": [],
        "memory_disputes": [],
        "memory_effects": [],
        "interaction": {
            "addresses": [],
            "expects_response": False,
            "yields_floor": True,
            "urgency": 0.0,
            "conversation_complete_for_me": False,
        },
        "salience": 0.5,
    },
    "mapping_stage": {
        "relevant_books": [],
        "relevant_lore": [],
        "staged_lore": [],
        "scene_patch": {
            "rooms": {},
            "entities": {},
            "positions": {},
            "remove_entities": [],
            "remove_rooms": [],
            "remove_adjacent": [],
        },
        "npc_suggestions": [],
        "notes": "",
    },
    "narrator": {
        # Handed to the model on every repair and fallback call, so it must
        # match the live contract exactly -- an example carrying a stale shape
        # teaches the old one back to the model that has just failed, and the
        # repair then "succeeds" into the wrong format.
        "prose": "<p>One paragraph per pair of markers.</p>",
        "new_specifics": [],
    },
    "mapping_commit": {
        "validated": [],
        "lore_ops": [],
        "book_ops": [],
        "shadow_profile": None,
        "offscreen_events": [],
        "standing_intentions": [],
        "coherence_notes": [],
        "validated_introductions": [],
    },
    # Without an example, output_example() returned {} and the repair prompt
    # steered a compliant model to return {} -- which validates (all defaults),
    # silently swallowing the reaction. This shows the real shape.
    "background_react": {
        "reacts": True,
        "dialogue_log_entry": {
            "speaker": "the barkeep",
            "exact_quote": "Aye, coming right up.",
            "volume": "normal",
            "intended_target": "",
            "tone": "gruff",
        },
        "action": "wipes down the counter",
    },
    "scene_life": {
        "entries": [
            {
                "name": "Hettie Crawe",
                "speech": {
                    # The entry's own `name`, again. A dialogue-log line
                    # carries its speaker, because the log is read by minds
                    # that were never told whose entry it came from.
                    "speaker": "Hettie Crawe",
                    "exact_quote": "Coin first. I've heard the songs.",
                    "volume": "normal",
                    "intended_target": "Bran",
                    "tone": "flat",
                },
                "action": "sets the tankard down harder than needed",
            },
            {
                "name": "Old Sarn",
                "speech": None,
                "action": "turns a little on his stool to watch",
            },
        ],
    },
    "blurb_mint": {
        "blurbs": [
            {
                "name": "Hettie Crawe",
                "manner": "short sentences, never says please, prices everything",
                "trait": "convinced adventurers always leave without paying",
                "tell": "wipes the same clean spot on the bar",
                "look": "forearms like a smith's, grey braid pinned up",
                "nature": "person",
            },
        ],
    },
    "greeting_interpret": {
        "time": "night",
        "knowledge_seeds": [
            {"content": "I have been waiting here for three nights for a courier.",
             "about_entity": "self", "kind": "recent_event", "salience": 0.7,
             "revealed_in_prose": False},
        ],
    },
    "resolve_reconcile": {
        "omissions": [
            {"category": "adjacency",
             "subject": "vault_door",
             "change": "The vault door is now sealed shut.",
             "evidence": "the vault door grinds shut and seals",
             "confidence": 0.9},
        ],
        "notes": "",
    },
    "resolve_repair": {
        "state_diff": {
            "positions": {},
            "rooms": {},
            "entities": {},
            "remove_entities": [],
            "remove_rooms": [],
            "remove_adjacent": [],
            "conditions": {},
            "inventory_ops": [],
            "overlays": {},
            "attire": {},
            "cast_changes": [],
            "world_facts": [],
            "introductions": [],
            # THE SHAPE, NOT A PLACEHOLDER. This was `None`, and the resolve
            # prompt describes the field in prose two thousand lines away
            # ("Emit state_diff.time with start_seconds, duration_seconds,
            # end_seconds, mode ('action'|'time_skip'), explicit (bool), and
            # display_advance"). A model that reads the EXAMPLE sees a scalar
            # and sends one -- live, GLM-5.2 sent a string and the turn died on
            # `state_diff.time: value is not a valid dict`.
            #
            # Worse, this same example is the `required_json_example` handed to
            # the repair attempt, so the repair was shown the identical `null`
            # and had no way to converge. One malformed field killed the whole
            # beat twice over. Same class as the `ratified_claims` defect, one
            # step further: not described-but-never-shown, but described one
            # way and SHOWN AS ANOTHER TYPE.
            "time": {"start_seconds": 0, "duration_seconds": 60,
                     "end_seconds": 60, "mode": "action",
                     "explicit": False, "display_advance": ""},
            "claim_dispositions": [],
        },
        "dispositions": [
            {"subject": "vault_door", "status": "encoded", "reason": ""},
        ],
    },
    "interpret_repair": {
        "sequence": [
            {"type": "action", "raw_text": "duck into the armory",
             "attempt": "duck into the armory", "commitment": "asserted",
             "verb": "enter", "targets": [], "asserted_effects": []},
        ],
        "movement": {"to_room": "armory", "why": "player declared entering",
                     "mover": "self"},
        "mapping_request": "Player enters the armory — generate its layout.",
        "generation_requests": [
            {"kind": "player_declaration", "subject": "a rifle grabbed from "
             "the armory rack", "constraints": [], "urgency": "now"},
        ],
        "dispositions": [
            {"subject": "duck into the armory and grab a rifle",
             "status": "captured", "reason": ""},
        ],
        "notes": "",
    },
}

def output_example(step_key: str) -> dict:
    return OUTPUT_EXAMPLES.get(step_key, {})


# Entity kinds that must occupy a room: things with agency, which can act and
# be acted on. An ALLOW-list, and deliberately the opposite shape to
# commit._INERT_ENTITY_KINDS, which asks the neighbouring question (is this a
# potential background presence) with a deny-list.
#
# The asymmetry is the whole design. Over-including there costs a tracked
# object that never reacts anyway; over-including HERE aborts an opening,
# because a semantic error gets one repair attempt, then the fallback
# candidates, then raises. Measured against all 48 live scenes: 17 of them
# carry an unplaced non-portable entity, 53 such entities in total -- framed
# diplomas, a shoe rack, a captain's chair, bell towers, ward doors, a day-room
# television, `location`-kind stand-ins for a whole starship. Requiring a room
# of all of those would have killed roughly a third of openings to tidy up
# furniture. Reusing the deny-list still failed 3 scenes, 2 of them wrongly (a
# `portal` door spans two rooms by design and belongs to neither; a
# `technology` TV is furniture). This list yields exactly one hit across the
# corpus: the creature that was the entire premise of the opening it went
# missing from.
#
# A kind this list does not know stays unplaced exactly as it does today, so
# missing one costs nothing that is not already the status quo.
_ANIMATE_ENTITY_KINDS = frozenset({
    "person", "people", "npc", "character", "human", "humanoid", "alien",
    "creature", "monster", "beast", "animal", "mount", "swarm",
    "robot", "android", "drone", "automaton", "construct", "golem",
    "spirit", "ghost", "wraith", "demon", "angel", "deity", "god",
    "undead", "zombie", "revenant",
    "agent", "actor", "guard", "soldier", "crew", "crewmember",
})

# A bodiless voice -- a ship's computer, a station AI, a PA -- needs no room,
# and positioning one is the category error scene.is_ubiquitous_entity exists
# to prevent. No separate kind list is needed here: none of the kinds in
# scene.UBIQUITOUS_KINDS ("computer", "ai", "system", "intercom", ...) is an
# animate kind above, so they are already exempt by shape, and the explicit
# `ubiquitous` flag covers one tagged with a kind that is.


def _unplaced_establish_entities(output: dict) -> list[str]:
    """AGENTS the opening declared and then left nowhere.

    An unplaced agent is not merely untidy -- it is excluded from co-presence
    by construction (agents/background.py: "unplaced presence: cannot prove
    co-presence, leave out"), so it can never be perceived and never act.
    Observed live: an opening whose entire premise was a creature closing in
    gave it a full description and a present-tense `entity_states` entry, put
    it in no room at all, and then opened a `world_pressure` thread demanding
    every later beat advance a threat with no location.

    A `portable` thing may be carried and inventory is not `positions`; a
    bodiless voice has no room by definition; a `state.link` portal spans two
    rooms and is in neither. `positions` may be keyed by entity id or by
    display name -- readers accept both, so both satisfy this.
    """
    entities = output.get("entities")
    positions = output.get("positions")
    if not isinstance(entities, dict) or not isinstance(positions, dict):
        return []
    placed = {str(k).strip().casefold() for k in positions if str(k).strip()}
    missing = []
    for eid, ent in entities.items():
        if not isinstance(ent, dict) or ent.get("portable") or ent.get("ubiquitous"):
            continue
        if str(ent.get("kind") or "").strip().casefold() not in _ANIMATE_ENTITY_KINDS:
            continue
        state = ent.get("state")
        if isinstance(state, dict) and state.get("link"):
            continue
        keys = {str(eid).strip().casefold(), str(ent.get("name") or "").strip().casefold()}
        if not (keys - {""}) & placed:
            missing.append(str(eid))
    if not missing:
        return []
    return ["entities %s declared but absent from positions -- an entity in no "
            "room cannot be perceived or acted on; place it in the room it is "
            "in, even one the party has left" % ", ".join(sorted(missing)[:6])]


def semantic_output_errors(
    step_key: str,
    output: dict,
    *,
    source_payload: dict | None = None,
) -> list[str]:
    errors = []
    source_payload = source_payload or {}

    if step_key == "director_interpret":
        raw_input = str(
            source_payload.get("player_raw_input") or ""
        ).strip()

        if raw_input and not output.get("sequence"):
            errors.append(
                "sequence is empty despite nonempty player input"
            )

        if not isinstance(output.get("flow"), dict):
            errors.append("flow must be an object")

    elif step_key == "director_establish":
        if not output.get("rooms"):
            errors.append("rooms is empty")

        if not output.get("positions"):
            errors.append("positions is empty")

        errors.extend(_unplaced_establish_entities(output))

    elif step_key == "director_resolve":
        # Only required when there was something to resolve. Doing nothing is
        # a legitimate thing for a mind to do -- a character may stand still,
        # stay silent, decline -- and an empty sequence is how that arrives.
        # Demanding prose about it unconditionally made a character's silence
        # able to abort the whole turn: observed live, a character agent
        # returned an empty sequence, the director had nothing to write about
        # and returned an empty resolved_event, and the beat was discarded.
        # Non-deterministically, too -- the same model narrated "he stays
        # where he is; no changes occur" on other beats, so the failure came
        # and went and looked like the model being unreliable.
        #
        # Mirrors director_interpret above, which has always required a
        # sequence only "despite nonempty player input".
        def _declared(*keys):
            for key in keys:
                block = source_payload.get(key)
                if isinstance(block, dict) and block.get("sequence"):
                    return True
                if isinstance(block, list):
                    for item in block:
                        if isinstance(item, dict) and item.get("sequence"):
                            return True
                        if isinstance(item, dict) and not {"sequence"} & set(item):
                            # A declaration shape with no sequence key at all
                            # still counts if it carries speech or an action.
                            if item.get("speech") or item.get("action"):
                                return True
            return False

        anything_happened = (
            _declared("player_declaration", "other_players_declarations",
                      "character_declarations")
            or bool(source_payload.get("dice_results_final"))
        )
        if (anything_happened
                and not str(output.get("resolved_event") or "").strip()):
            errors.append("resolved_event is empty")

        if not isinstance(output.get("state_diff"), dict):
            errors.append("state_diff must be an object")

    elif step_key == "character":
        if not isinstance(output.get("sequence"), list):
            errors.append("sequence must be an array")

        if not isinstance(output.get("interaction"), dict):
            errors.append("interaction must be an object")

    elif step_key == "mapping_stage":
        if not isinstance(output.get("scene_patch"), dict):
            errors.append("scene_patch must be an object")

    elif step_key == "narrator":
        if not str(output.get("prose") or "").strip():
            # SAY WHERE IT WENT. "prose is empty" is 3 of 17 validation
            # failures across the live corpus -- 18% of every repair call --
            # and unlike its two larger siblings the message does not carry
            # the shape that failed, so nothing in the record distinguishes a
            # model that returned nothing from one that returned a page of
            # narration under a key this contract does not read. The first is
            # worth a repair call; the second is worth a one-line alias, and
            # for the whole life of the corpus there has been no way to tell
            # which. Name the keys that DID arrive, and the next occurrence
            # answers it.
            present = sorted(str(k) for k in output) if isinstance(
                output, dict) else []
            errors.append(
                "prose is empty" if not present
                else "prose is empty (keys present: %s)" % ", ".join(present[:12]))

    return errors

def _name_what_was_discarded(step_key, raw, error):
    """Say that WE dropped the sequence, when we did.

    `preprocess_llm_output` discards any `sequence` element that is not an
    object, so a model that answers with a list of sentences -- observed
    live twice in eleven turns, e.g. `["Picks up the PADD.", "Says, \\"Nobody
    leaves this room.\\""]` -- reaches the semantic check with nothing left
    and is told `sequence is empty despite nonempty player input`. It is
    then handed that sentence as the thing to repair, and the sentence is
    false: the model sent a sequence, and this code deleted it. Both repair
    and every fallback candidate then failed, and the turn died.

    THAT WORKED CASE NO LONGER OCCURS, and this counts what survives rather
    than what was an object. `_sequence_event_from_prose` now READS a plain
    sentence -- as an action unless the whole string is a quotation -- so a
    list of sentences arrives non-empty and never reaches this at all. What
    still cannot be read is a blank string, or an entry that is neither an
    object nor a string. Counting every non-object entry as discarded would
    now blame the model for the one spelling the engine accepts, and the
    remedy sentence would instruct it away from that spelling; both would be
    false in the same message that exists because a false message cost a turn.

    Naming the real disagreement is not the same as guessing what the
    sentences MEANT -- a bare sentence does not say whether it is speech or
    action, and the engine must not decide that on the player's behalf. The
    model that wrote them does know, so the honest move is to tell it what
    the shape has to be. See docs/UNBUILT.md 1.7.
    """
    if step_key != "director_interpret" or "sequence is empty" not in error:
        return error
    sent = raw.get("sequence") if isinstance(raw, dict) else None
    if not isinstance(sent, list) or not sent:
        return error
    # Exactly what `preprocess_llm_output` keeps, asked the same way.
    readable = [item for item in sent
                if isinstance(item, dict)
                or (isinstance(item, str)
                    and _sequence_event_from_prose(item) is not None)]
    if readable:
        return error
    return (
        f"{error} -- because all {len(sent)} sequence entries you sent were "
        "blank or were neither an object nor a sentence, so none could be "
        "read. An entry must be an object, e.g. "
        '{"type": "action", "attempt": "..."} or '
        '{"type": "speech", "text": "...", "volume": "normal"}; '
        "a plain sentence is read as an action. Resend the same beat in "
        "one of those shapes."
    )


# Steps whose `state_diff` is an ENCODING of an adjudication rather than the
# adjudication itself. The prose, the dialogue and the summary are the beat;
# the diff is how the beat is written into world state, and the engine already
# treats it as separable -- `resolve_reconcile`/`resolve_repair` exist to
# detect changes asserted in prose but missing from the diff and merge a
# correction additively.
_DIFF_PRUNABLE_STEPS = ("director_resolve", "resolve_repair")


def _prunable_diff_fields(errors):
    """The `state_diff` sub-fields every error is rooted under, or None.

    None means at least one error is somewhere else -- in `resolved_event`, in
    `dialogue_log`, in the parse itself -- and nothing may be pruned, because
    those ARE the adjudication and a beat without them is not a beat.
    """
    fields = set()
    for error in errors:
        loc = [str(part) for part in (error.get("loc") or [])]
        if len(loc) < 2 or loc[0] != "state_diff":
            return None
        fields.add(loc[1])
    return fields or None


# A specialist's whole output IS channels, so its analogue of the
# state_diff prune above is one level shallower: when every validation error
# is rooted under one of its channel fields (or `notes`), drop those fields
# and keep the rest. Absent is already "no change asserted" for each of
# them, and the resolve-side reconciliation seam catches anything the drop
# lost -- the same contract the state_diff prune documents. DROPPED, NEVER
# INVENTED.
def _prunable_specialist_fields(step_key, errors):
    allowed = set(SPECIALIST_CHANNELS.get(step_key) or ()) | {"notes"}
    fields = set()
    for error in errors:
        loc = [str(part) for part in (error.get("loc") or [])]
        if not loc or loc[0] not in allowed:
            return None
        fields.add(loc[0])
    return fields or None


def validate_llm_output_strict(
    step_key: str,
    raw: dict,
    *,
    source_payload: dict | None = None,
) -> ValidationReport:
    if not isinstance(raw, dict):
        return ValidationReport(
            valid=False,
            output={},
            errors=["Output is not a JSON object"],
        )

    prepared = preprocess_llm_output(step_key, raw)
    model_cls = SCHEMA_MAP.get(step_key)
    repairs = [str(note) for note in (prepared.get("concealment_repairs") or [])]

    if model_cls is None:
        return ValidationReport(
            valid=True,
            output=prepared,
            warnings=list(repairs),
        )

    try:
        model = _validate(model_cls, prepared)
        output = _dump(model)
    except ValidationError as exc:
        errors = []

        for error in exc.errors():
            location = ".".join(
                str(part)
                for part in error.get("loc", [])
            )
            message = error.get("msg", "invalid value")
            errors.append(f"{location}: {message}")

        # ONE BAD FIELD USED TO COST THE WHOLE BEAT. Live 2026-08-08: a
        # complete, correct 4,000-token resolve -- resolved_event, summary,
        # dialogue all intact -- was discarded because `state_diff.time`
        # arrived as a scalar, and the repair attempt was handed the same
        # broken example that caused it and could not converge.
        #
        # `_coerce_optional_time` fixed that one field. This is the general
        # form, and it is the same shape as the lorebook import's
        # repair-then-degrade: when EVERY error is rooted under a `state_diff`
        # sub-field, drop those sub-fields and re-validate. Absent is already
        # "no change asserted" for every StateDiff field, so the beat commits
        # what it did adjudicate and the drift is the reconcile seam's problem
        # next beat -- which is exactly what that seam exists for.
        #
        # DROPPED, NEVER INVENTED. Nothing truthful can be built from a
        # malformed diff, and a fabricated value is a claim the model never
        # made. And nothing is pruned when any error sits outside `state_diff`:
        # the prose, the dialogue and the summary ARE the adjudication, and a
        # beat without them is not a beat.
        prunable = (_prunable_diff_fields(exc.errors())
                    if step_key in _DIFF_PRUNABLE_STEPS else None)
        if prunable:
            pruned = dict(prepared)
            diff = dict(pruned.get("state_diff") or {})
            for field in prunable:
                diff.pop(field, None)
            pruned["state_diff"] = diff
            try:
                model = _validate(model_cls, pruned)
            except ValidationError:
                pass
            else:
                return ValidationReport(
                    valid=True,
                    output=_dump(model),
                    warnings=repairs + [
                        "Dropped malformed state_diff.%s so the beat could "
                        "commit what it did adjudicate (%s)" % (field, detail)
                        for field, detail in
                        ((f, next((e for e in errors
                                   if e.startswith("state_diff.%s" % f)), ""))
                         for f in sorted(prunable))
                    ],
                )

        spec_prunable = (_prunable_specialist_fields(step_key, exc.errors())
                         if step_key in SPECIALIST_CHANNELS else None)
        if spec_prunable:
            pruned = dict(prepared)
            for field in spec_prunable:
                pruned.pop(field, None)
            try:
                model = _validate(model_cls, pruned)
            except ValidationError:
                pass
            else:
                return ValidationReport(
                    valid=True,
                    output=_dump(model),
                    warnings=repairs + [
                        "Dropped malformed specialist channel %s so the "
                        "beat could keep what it did encode (%s)"
                        % (field, detail)
                        for field, detail in
                        ((f, next((e for e in errors
                                   if e.startswith("%s" % f)), ""))
                         for f in sorted(spec_prunable))
                    ],
                )

        return ValidationReport(
            valid=False,
            output=prepared,
            errors=errors,
        )

    semantic_errors = semantic_output_errors(
        step_key,
        output,
        source_payload=source_payload,
    )
    semantic_errors = [
        _name_what_was_discarded(step_key, raw, error)
        for error in semantic_errors
    ]

    return ValidationReport(
        valid=not semantic_errors,
        output=output,
        errors=semantic_errors,
        warnings=list(repairs),
    )
