# schemas.py
"""Pydantic schemas for all pipeline and world-state structures."""

import json
import math
import re

from pydantic import BaseModel, Field, ValidationError, validator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NamedTuple, Optional, Union, get_args, get_origin


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


def _coerce_attire_diff(value):
    """One body's attire diff, canonicalized by attire.coerce_diff_shape.

    Delegated rather than reimplemented because commit.py must run the same
    coercion: rerunning a stage replays diffs stored before this existed, and
    two spellings of the rule would eventually disagree about the same body.
    attire.py imports nothing but `re`, so there is no cycle.
    """
    import attire
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

class TemporalMode(str, Enum):
    immediate = "immediate"
    extended = "extended"
    time_skip = "time_skip"

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
    return _as_declared_scalar(value, declared_type)


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


def _lenient_coerce(value, declared):
    """The one coercion, given a value and the shape its field declared."""
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
            members = [m for m in members if isinstance(m, dict)]
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
            slot = _subject_field_of(declared.item_type)
            if slot is not None and slot not in fields:
                slot = None
            if slot is None:
                slot = next((n for n, f in fields.items()
                             if _field_required(f)), None)
            if slot is None:
                # An item model where nothing is required still has a
                # subject, and dropping the key threw it away entirely: a
                # `knowledge_seeds` map keyed by the seed's own text
                # arrived with `content: ""`, which is the whole seed. The
                # slot is the first field declared as prose whose default
                # is EMPTY -- an empty default means "nothing said yet",
                # which is what a key can fill; a non-empty one is a
                # chosen value and not a hole. Declaration order alone
                # would be wrong: it names `category` on AssertedChange
                # (default "other") when the key is the subject, and `op`
                # on LoreOp (default "create") when the key is the entry's
                # own keys.
                slot = _first_empty_prose_field(fields)
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
            return _lenient_coerce(value, _declared(field))
    else:
        @validator("*", pre=True, allow_reuse=True)
        def _coerce_structured_into_str(cls, value, field):
            return _lenient_coerce(value, _declared(field))


class GenreProfile(LenientModel):
    primary: str = "unspecified"
    secondary: list[str] = Field(default_factory=list)
    tone: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)
    threat_density: float = 0.3
    mystery_density: float = 0.3
    humor_density: float = 0.2
    lethality: float = 0.3
    supernatural_prevalence: float = 0.0
    technology_level: str = "unspecified"
    content_boundaries: list[str] = Field(default_factory=list)

class CausalRegime(LenientModel):
    regime_id: str
    scope: str = "default"
    priority: int = 0
    rules: dict[str, Any] = Field(default_factory=dict)

class FictionModel(LenientModel):
    genre: dict[str, Any] = Field(default_factory=dict)
    ontology: dict[str, Any] = Field(default_factory=dict)
    causal_regimes: list[dict] = Field(default_factory=list)
    scale_rules: dict[str, Any] = Field(default_factory=dict)
    abstraction_rules: dict[str, Any] = Field(default_factory=dict)
    narrative_conventions: list[dict] = Field(default_factory=list)
    epistemic_rules: list[dict] = Field(default_factory=list)
    content_rules: list[dict] = Field(default_factory=list)

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

class ScenePressure(LenientModel):
    threat: float = 0.0
    mystery: float = 0.0
    social: float = 0.0
    environmental: float = 0.0
    recent_release: float = 0.0

# ---- Time ----

class SimulationClock(LenientModel):
    elapsed_seconds: float = 0.0
    calendar: Optional[dict[str, Any]] = None
    display: str = "now"
    time_scale: str = "scene"

class TimeDiff(LenientModel):
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    end_seconds: float = 0.0
    mode: str = "action"
    explicit: bool = False
    display_advance: str = ""

class TemporalProperties(LenientModel):
    rate_numerator: float = 1.0
    rate_denominator: float = 1.0
    offset_seconds: float = 0.0
    causal_ordering: str = "global"
    supports_time_travel: bool = False

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

class ResolutionCheck(LenientModel):
    check_id: str = ""
    event_id: str = ""
    actor_id: str = ""
    opposing_actor_id: Optional[str] = None
    ability: str = ""
    opposing_ability: Optional[str] = None
    difficulty: str = "medium"
    modifiers: list[dict] = Field(default_factory=list)
    seed: str = ""
    roll: Optional[int] = None
    opposing_roll: Optional[int] = None
    outcome: str = ""

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

# ---- Authority ----

class AuthorityClaim(LenientModel):
    claim_id: str = ""
    scope: str = "action"
    subject_id: Optional[str] = None
    predicate: str = ""
    value: Any = None
    commitment: str = "asserted"
    source_text: str = ""

class ClaimDisposition(LenientModel):
    claim_id: str = ""
    status: str = "realized"
    realized_event_ids: list[str] = Field(default_factory=list)
    notes: str = ""

class GenerationRequest(LenientModel):
    kind: str
    subject: str = ""
    location_id: Optional[str] = None
    constraints: list[str] = Field(default_factory=list)
    evidence_event_ids: list[str] = Field(default_factory=list)
    urgency: str = "now"

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

class WorldEntity(LenientModel):
    entity_id: str
    kind: str
    subtype: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_turn: Optional[int] = None
    retired_turn: Optional[int] = None

class AggregateEntity(LenientModel):
    entity_id: str
    name: str
    aggregate_kind: str
    member_kind: str = ""
    named_member_ids: list[str] = Field(default_factory=list)
    estimated_count: Optional[int] = None
    strength: float = 1.0
    cohesion: float = 1.0
    morale: float = 1.0
    readiness: float = 1.0
    supply: float = 1.0
    mobility: float = 1.0
    command_quality: float = 0.5
    sensor_quality: float = 0.5
    capabilities: list[dict] = Field(default_factory=list)
    objectives: list[dict] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

class ComponentState(LenientModel):
    component_id: str
    parent_entity_id: str
    kind: str
    name: str
    integrity: float = 1.0
    operational: bool = True
    capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

# ---- World and Location Hierarchy ----
#
# DEPRECATED -- MARKED FOR REMOVAL (movement/space Phase 2, removed in
# Phase 3): WorldDef, LocationDef, and TransitEdge belong to the dead
# fiction_worlds/fiction_locations/transit_edges macro schema that nothing
# in the runtime pipeline ever writes. Their roles are absorbed by the
# unified model: macro geography = upper lorebook-tree books; macro
# transit = portal links (entity.state.link) + scheduled_events latency.
# Kept only so old imports/checkpoint blobs keep tolerating the shapes.

class WorldDef(LenientModel):
    world_id: str
    name: str
    kind: str = "world"
    parent_world_id: Optional[str] = None
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    ontology: dict[str, Any] = Field(default_factory=dict)
    mechanics: list[str] = Field(default_factory=list)
    genre_overrides: dict[str, Any] = Field(default_factory=dict)
    temporal_properties: dict[str, Any] = Field(default_factory=dict)
    spatial_properties: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

# DEPRECATED -- see the WorldDef block comment above.
class LocationDef(LenientModel):
    location_id: str
    world_id: str
    parent_location_id: Optional[str] = None
    kind: str = "location"
    name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    scale: str = "site"
    tags: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    connections: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

class SpatialZone(LenientModel):
    zone_id: str
    location_id: str
    name: str
    zone_kind: str = "area"
    neighbors: list[dict] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)

# DEPRECATED -- see the WorldDef block comment above.
class TransitEdge(LenientModel):
    edge_id: str
    from_world_id: str
    from_location_id: Optional[str] = None
    to_world_id: str
    to_location_id: Optional[str] = None
    kind: str
    bidirectional: bool = False
    traversal_time_seconds: Optional[float] = None
    requirements: list[dict] = Field(default_factory=list)
    costs: list[dict] = Field(default_factory=list)
    hazards: list[dict] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    source_entity_id: Optional[str] = None

class StrategicPlacement(LenientModel):
    subject_id: str
    zone_id: str
    posture: str = ""
    range_band_to: dict[str, str] = Field(default_factory=dict)
    heading: Optional[str] = None
    altitude_band: Optional[str] = None
    depth_band: Optional[str] = None

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

class ScheduledEvent(LenientModel):
    event_id: str
    due_at_seconds: float
    kind: str
    subject_ids: list[str] = Field(default_factory=list)
    location_id: Optional[str] = None
    trigger: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    source_event_id: Optional[str] = None
    status: str = "pending"

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

# ---- Inventory and Mutations ----

class InventoryOp(LenientModel):
    op: str
    object_id: str
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    relation: str = "held_by"
    details: dict[str, Any] = Field(default_factory=dict)

class ObjectStatePatch(LenientModel):
    object_id: str
    set_fields: dict[str, Any] = Field(default_factory=dict)
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)

# ---- Reactions and Perception ----

class ReactionDeclaration(LenientModel):
    actor_id: str
    trigger_event_ids: list[str] = Field(default_factory=list)
    sequence: list[dict] = Field(default_factory=list)
    urgency: float = 0.0

class EventAtom(LenientModel):
    atom_id: str
    event_id: str
    kind: str
    source_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    location_id: Optional[str] = None
    start_offset_seconds: float = 0.0
    duration_seconds: float = 0.0
    channels: dict[str, dict] = Field(default_factory=dict)
    observable: dict[str, Any] = Field(default_factory=dict)

class Observation(LenientModel):
    observation_id: str
    perceiver_id: str
    source_atom_id: str
    channel: str
    fidelity: str
    observed: dict[str, Any] = Field(default_factory=dict)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    suddenness: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity: float = Field(default=0.5, ge=0.0, le=1.0)
    directed_at_self: bool = False

    _clamp_observation_axes = validator(
        "intensity", "ambiguity", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5))
    # Split out because its declared default is 0.0, not 0.5. A field
    # validator runs BEFORE the inherited null-substitution, so the shared
    # clamp's fallback was the effective value for `null` while an omitted
    # field still got 0.0 -- the same field answering two different ways to
    # two spellings of "not said", and neither matching the other.
    _clamp_suddenness = validator(
        "suddenness", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))

class SensorChannel(LenientModel):
    channel_id: str
    owner_id: str
    kind: str
    range: str
    resolution: str
    latency_seconds: float = 0.0
    coverage: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

class ActorDef(LenientModel):
    entity_id: str
    name: str
    kind: str = "creature"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    abilities: list[dict] = Field(default_factory=list)
    drives: list[str] = Field(default_factory=list)
    behavior_model: str = "reactive"
    cognition_tier: str = "background"
    senses: list[dict] = Field(default_factory=list)
    body: dict[str, Any] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

# ---- Establishment and Resolve ----

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
    attire: dict[str, AttireState] = Field(default_factory=dict)
    entity_states: dict[str, InitialEntityState] = Field(default_factory=dict)
    # Where in each room the opening puts people: {name: {at, near:[]}}.
    stations: dict[str, dict] = Field(default_factory=dict)
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

class BackgroundReactOutput(LenientModel):
    reacts: bool = False
    dialogue_log_entry: Optional[DialogueLogEntry] = None
    action: str = ""

class SceneLifeEntry(LenientModel):
    """One managed presence's conduct for this beat, attributed by name so the
    commit-side append is a ROUTING operation rather than an authoring one
    (docs/BACKGROUND_LIFE_DESIGN.md §3.11)."""
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

class BlurbMintEntry(LenientModel):
    """A frozen personality blurb (§3.8). Surface only -- manner, a standing
    concern, a repeatable tic -- never private goals or beliefs about others."""
    name: str
    manner: str = ""
    trait: str = ""
    tell: str = ""
    look: str = ""

class BackdropPromptOutput(LenientModel):
    prompt: str = ""

class BlurbMintOutput(LenientModel):
    blurbs: list[BlurbMintEntry] = Field(default_factory=list)

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
    # whatever positions no longer permit. {op: add|remove|clear, actor,
    # actor_part, target, target_part, manner}.
    contact_ops: list[dict] = Field(default_factory=list)
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
    cast_changes: list[dict] = Field(default_factory=list)
    world_facts: list = Field(default_factory=list)
    introductions: list[dict] = Field(default_factory=list)
    # Names/details a background presence asserted on an earlier beat that this
    # resolution ADOPTS as true (background_claims.py). Ratifying is the
    # Director's alone -- an unratified claim stays hearsay and expires.
    ratified_claims: list[str] = Field(default_factory=list)
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
    # Destruction declaration (DestructionEffect shape -- see its
    # docstring). Declared here so model_dump() keeps it through
    # validation (the zone-field precedent above); commit.py validates it
    # deterministically: one vehicle/building, or a 'region' whose
    # multi-book cascade commit.py enumerates from the lorebook tree.
    destruction: Optional[dict] = None

    _coerce_stations = validator("stations", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_station_table(v)
    )

class AssertedChange(LenientModel):
    """One entry of director_resolve's own changes-asserted manifest: a
    persistent physical change its resolved_event asserts as completed,
    beyond the player's supplied authority_claims. Reconciled against the
    state_diff deterministically (see agents/director.py's seam)."""
    category: str = "other"   # rooms|adjacency|positions|entities|conditions|attire|inventory|cast_changes|time|transit|other
    subject: str = ""         # room id / entity id / character name concerned
    change: str = ""          # one short sentence stating the persistent change

class DirectorResolve(LenientModel):
    resolved_event: str = ""
    summary: str = ""
    dialogue_order: list[str] = Field(default_factory=list)
    dialogue_log: list[DialogueLogEntry] = Field(default_factory=list)
    state_diff: StateDiff = Field(default_factory=StateDiff)
    changes_asserted: list[AssertedChange] = Field(default_factory=list)
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

# ---- Resolve reconciliation (agents/director.py's post-resolve seam) ----

class ReconcileOmission(LenientModel):
    """One persistent, physically consequential change asserted as completed
    in resolved_event prose but not encoded anywhere in the state_diff."""
    category: str = "other"   # rooms|adjacency|positions|entities|conditions|attire|inventory|cast_changes|time|other
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
    """
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
            value = []
    return [
        {"response": item} if isinstance(item, str) else item
        for item in (value if isinstance(value, list) else [])
        if isinstance(item, (str, dict))
    ]


class ResponseCandidate(LenientModel):
    response: str = ""
    serves: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    inhibition: float = Field(default=0.0, ge=0.0, le=1.0)
    norm_conflict: str = ""
    selected: bool = False

    _lists = validator("serves", pre=True, allow_reuse=True)(
        lambda cls, value: _coerce_str_list(value)
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
    # A voluntary decision by this character to begin or cease following a
    # target. Omit to preserve the current relation.
    follow_op: Optional[dict] = None
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
        lambda cls, v: [
            item for item in (v if isinstance(v, (list, tuple)) else [])
            if isinstance(item, dict) and str(item.get("quote") or "").strip()
        ] if isinstance(v, (list, tuple)) else [])
    _coerce_disputes = validator(
        "memory_disputes", pre=True, allow_reuse=True)(
        lambda cls, v: [
            item for item in (v if isinstance(v, (list, tuple)) else [])
            if isinstance(item, dict) and (
                str(item.get("memory_ref") or "").strip() or
                str(item.get("gist") or "").strip())
            and str(item.get("now_reads") or "").strip()
        ] if isinstance(v, (list, tuple)) else [])

    # `cue` is required and an entry without one names nothing, so it cannot be
    # applied -- but dropping the entry is right where failing the entire
    # character turn is not. Same posture as the dialogue coercion, which drops
    # a line with no quote rather than rejecting the beat.
    _drop_cueless = validator(
        "association_updates", pre=True, allow_reuse=True)(
        lambda cls, v: [
            item for item in (v if isinstance(v, (list, tuple)) else [])
            if not isinstance(item, dict) or str(item.get("cue") or "").strip()
        ] if isinstance(v, (list, tuple)) else v)
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

# ---- Lorebook Tree ----

class LorebookDef(LenientModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    book_type: str = "general"
    summary: str = ""
    scope_world_id: Optional[str] = None
    scope_location_id: Optional[str] = None
    inheritance_mode: str = "inherit"
    sort_order: int = 0

class LoreEntryScope(LenientModel):
    world_ids: list[str] = Field(default_factory=list)
    location_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None

class LoreEntryRelation(LenientModel):
    supersedes_entry_id: Optional[int] = None
    refines_entry_ids: list[int] = Field(default_factory=list)
    contradicts_entry_ids: list[int] = Field(default_factory=list)
    
class PerceptionOutput(LenientModel):
    views: dict[str, Optional[str]] = Field(default_factory=dict)
    # Produced by deterministic post-processing from the final scrubbed view,
    # never trusted from model output. This makes structured perception a
    # projection of the already-audited prose channel, not a second leak path.
    observations: dict[str, list[Observation]] = Field(default_factory=dict)

class MappingStageOutput(LenientModel):
    relevant_books: list[int] = Field(default_factory=list)
    relevant_lore: list[dict] = Field(default_factory=list)
    staged_lore: list[dict] = Field(default_factory=list)
    scene_patch: ScenePatch = Field(default_factory=ScenePatch)
    npc_suggestions: list[dict] = Field(default_factory=list)
    notes: str = ""

# ---- Greeting interpretation (ingest-time, per docs/GREETING_IMPORT_DESIGN.md) ----

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
    location: str = ""
    time: str = "now"
    scene_description: str = ""
    # freeform dicts (kept tolerant, consumed defensively by the launch merge)
    rooms: dict = Field(default_factory=dict)
    positions: dict = Field(default_factory=dict)
    entities: dict = Field(default_factory=dict)
    attire: dict = Field(default_factory=dict)
    character_state: dict = Field(default_factory=dict)
    knowledge_seeds: list[GreetingKnowledgeSeed] = Field(default_factory=list)
    player_room: str = ""           # room id {{PLAYER}} occupies, if present
    notes: str = ""

# ---- Validation ----

SCHEMA_MAP = {
    "greeting_interpret": GreetingInterpret,
    "director_interpret": DirectorInterpret,
    "director_establish": DirectorEstablish,
    "director_resolve": DirectorResolve,
    "resolve_reconcile": ResolveReconcileOutput,
    "resolve_repair": ResolveRepairOutput,
    "interpret_repair": InterpretRepairOutput,
    "narrator": NarratorOutput,
    "character": CharacterOutput,
    "mapping_stage": MappingStageOutput,
    "perception": PerceptionOutput,
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

    return result

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
            fixed[key] = [item for item in items if isinstance(item, dict)]
        return fixed
    return value

_STATE_DIFF_DICT_FIELDS = (
    "positions", "rooms", "entities", "overlays", "attire", "entity_states",
)

_STATE_DIFF_SIBLING_FIELDS = (
    "remove_entities", "remove_rooms", "remove_adjacent", "conditions",
    "inventory_ops", "contact_ops", "stations", "scales", "containment",
    "vitals", "overlays",
    "attire", "cast_changes",
    "world_facts", "introductions", "time", "claim_dispositions",
)

_SCENE_PATCH_SIBLING_FIELDS = (
    "rooms", "positions", "stations", "remove_entities", "remove_rooms",
    "remove_adjacent",
)

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
    """
    entities = container.get("entities")
    if not isinstance(entities, dict):
        return
    for field in sibling_fields:
        if field in entities and field not in container:
            container[field] = entities.pop(field)

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

    if step_key == "perception":
        # Observations are a deterministic projection of the final scrubbed
        # view. Model-authored copies are discarded before validation so a
        # malformed or malicious second channel can neither fail the step nor
        # smuggle information past the prose gates.
        result.pop("observations", None)
        views = result.get("views")
        if isinstance(views, dict):
            result["views"] = {
                k: _flatten_view_value(v) for k, v in views.items()
            }

    if step_key == "narrator":
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

    if step_key in ("director_resolve", "director_establish", "resolve_repair"):
        target = result
        if step_key in ("director_resolve", "resolve_repair"):
            state_diff = result.get("state_diff")
            target = state_diff if isinstance(state_diff, dict) else None
            if target is not None:
                _hoist_misplaced_entity_siblings(target, _STATE_DIFF_SIBLING_FIELDS)
            if target is not None and "conditions" in target:
                target["conditions"] = _coerce_conditions(target["conditions"])
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

        result["sequence"] = cleaned_sequence

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

        result["dialogue_log"] = cleaned_dialogue

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
    if not model_cls:
        return prepared, []
    try:
        model = _validate(model_cls, prepared)
        return _dump(model), []
    except ValidationError as exc:
        warnings = [f"Schema validation warning: {len(exc.errors())} errors"]
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
        "location": "",
        "time": "now",
        "scene_description": "",
        "rooms": {},
        "entities": {},
        "positions": {},
        "stations": {},
        "contact_ops": [],
        "attire": {},
        "entity_states": {},
        "sensory_events": [],
        "world_facts": [],
        "fiction_frame": {},
        "simulation_clock": {
            "elapsed_seconds": 0.0,
            "display": "now",
            "time_scale": "scene",
        },
        "opening": "",
    },
    "director_resolve": {
        "resolved_event": "",
        "summary": "",
        "dialogue_order": [],
        "dialogue_log": [],
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
            "time": None,
            "claim_dispositions": [],
        },
        "changes_asserted": [
            {"category": "adjacency", "subject": "vault_door",
             "change": "The vault door is sealed shut."},
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
    "character": {
        "observations_used": [],
        "present_evidence_used": [],
        "memory_evidence_used": [],
        "appraisal": {},
        "considered_responses": [],
        "response_candidates": [],
        "sequence": [],
        "active_state": {},
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
    "perception": {
        "views": {},
        "observations": {},
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
        "prose": "",
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
            },
        ],
    },
    "greeting_interpret": {
        "location": "a dim tavern",
        "time": "night",
        "scene_description": "A low-ceilinged tavern, rain against the shutters.",
        "rooms": {"tavern": {"name": "The Tavern", "desc": "Low-ceilinged, smoke-hazed.",
                              "adjacent": []}},
        "positions": {"Kara": "tavern", "{{PLAYER}}": "tavern"},
        "entities": {},
        "attire": {"Kara": {"summary": "a travel-worn cloak"}},
        "character_state": {"mood": "wary", "goal": "size up the newcomer"},
        "knowledge_seeds": [
            {"content": "I have been waiting here for three nights for a courier.",
             "about_entity": "self", "kind": "recent_event", "salience": 0.7,
             "revealed_in_prose": False},
        ],
        "player_room": "tavern",
        "notes": "",
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
            "time": None,
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

    elif step_key == "perception":
        perceivers = source_payload.get("perceivers") or []
        views = output.get("views")

        if not isinstance(views, dict):
            errors.append("views must be an object")
        else:
            expected = {
                str(item.get("id"))
                for item in perceivers
                if isinstance(item, dict)
                and item.get("id") is not None
            }

            missing = sorted(
                expected - {str(key) for key in views}
            )

            if missing:
                errors.append(
                    "views is missing perceiver IDs: "
                    + ", ".join(missing)
                )

    elif step_key == "mapping_stage":
        if not isinstance(output.get("scene_patch"), dict):
            errors.append("scene_patch must be an object")

    elif step_key == "narrator":
        if not str(output.get("prose") or "").strip():
            errors.append("prose is empty")

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

    Naming the real disagreement is not the same as guessing what the
    sentences MEANT -- a bare sentence does not say whether it is speech or
    action, and the engine must not decide that on the player's behalf. The
    model that wrote them does know, so the honest move is to tell it what
    the shape has to be. See docs/UNBUILT.md 1.7.
    """
    if step_key != "director_interpret" or "sequence is empty" not in error:
        return error
    sent = raw.get("sequence") if isinstance(raw, dict) else None
    if not isinstance(sent, list):
        return error
    dropped = [item for item in sent if not isinstance(item, dict)]
    if not dropped:
        return error
    return (
        f"{error} -- because {len(dropped)} of the {len(sent)} sequence "
        "entries you sent were not objects and were discarded. Every entry "
        "must be an object, e.g. "
        '{"type": "action", "attempt": "..."} or '
        '{"type": "speech", "text": "...", "volume": "normal"}. '
        "Resend the same beat in that shape."
    )


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

    if model_cls is None:
        return ValidationReport(
            valid=True,
            output=prepared,
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
    )
