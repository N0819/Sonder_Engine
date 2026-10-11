"""Strict JSON completion, semantic validation, and repair retries."""

import contextvars
import json
import re
import time

from core.pipeline_context import note_step_warning
from llm.providers import (
    answer_ran_away,
    chat_complete,
    escalated_max_tokens,
    generation_notice,
    response_truncated,
    role_candidate_count,
    LLMError,
    Aborted,
    DegenerateOutput,
    RetryConfig,
    ToolsUnsupported,
)
from llm.schemas import (
    output_example,
    validate_llm_output_strict,
)
from llm.prompts import get_prompt

def _without_trailing_commas(text: str) -> str:
    r"""`{"a": 1,}` -> `{"a": 1}`, without touching a comma inside a string.

    The one repair a model's JSON needs that the parser cannot do for itself,
    and the commonest malformation there is: a list or object written with a
    comma after its last member. Two call sites used to carry this as
    `re.sub(r",\s*([}\]])", ...)`, which cannot see quoting and would edit
    the inside of a sentence that happened to end `, }`; it belongs here, once,
    where every reader of model output gets it (2026-09-08, a journey history
    lost at position 8118).
    """
    out = []
    in_str = escape = False
    for index, ch in enumerate(str(text or "")):
        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            continue
        if ch == ",":
            rest = text[index + 1:]
            stripped = rest.lstrip()
            if stripped[:1] in ("}", "]"):
                continue          # the comma has nothing after it but a close
        out.append(ch)
    return "".join(out)


def _extract_balanced_object(text: str):
    """Extract the first balanced {...} object from prose-wrapped output.
    Some models habitually prefix "Here is the JSON:" or append commentary
    after the closing fence, which defeats the fence-strip anchors and burns
    every repair/candidate attempt on a fully-valid object buried in prose."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                span = text[start:i + 1]
                for candidate in (span, _without_trailing_commas(span)):
                    try:
                        value = json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                    return value if isinstance(value, dict) else None
                return None
    return None


def _restarted_object(text: str):
    """The complete object a restarted answer ends with, or None.

    AN AGGREGATOR THAT RESTARTS A GENERATION STREAMS BOTH ATTEMPTS. Measured
    on NanoGPT's z-ai/glm-5.2:thinking (real-turn replay round 2,
    2026-09-23): the narrator's text began `{"{"prose": "<p>The frame fights
    you...` and a character's `{"effect{"effects":[]...` -- a fragment, then
    the whole answer again from its first brace. The fragment's lone quote
    throws every later string off by one, so neither parse nor
    `_extract_balanced_object` can see the answer that follows it, and the
    beat died on a repair that had to reconstruct from the damage.

    The answer is the object that runs to the END of the text. An object
    that parses but stops short of the end is the inside of something
    malformed -- a truncated answer's nested value -- and is never taken."""
    decoder = json.JSONDecoder()
    end_of_text = len(text.rstrip())
    i = text.find("{", 1)
    while i != -1:
        try:
            value, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i = text.find("{", i + 1)
            continue
        if isinstance(value, dict) and end >= end_of_text:
            return value
        i = text.find("{", i + 1)
    return None


def _strip_fences(text: str) -> str:
    """The model's JSON with any Markdown fence taken off.

    One function because two callers need the SAME string: the parser, and the
    check that asks whether the parse failed at the end of the text. A second
    spelling of the fence rule would put the two out of step by exactly the
    length of a fence, and the check is a comparison against that length.
    """
    raw = str(text or "").strip()
    raw = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.I,
    )
    return re.sub(r"\s*```$", "", raw)


def output_ran_out_of_room(raw: str) -> bool:
    """Did this response stop mid-object, rather than say something wrong?

    The two are the same event downstream -- a JSON parse error -- and they
    need opposite responses. A cut-off object is a LENGTH problem: the model
    knew what it was writing and had nowhere to put it, so one more call with
    more room recovers the beat. Malformed JSON is a CONTENT problem, and more
    room changes nothing about it.

    Two witnesses, in order of authority:

    1. The provider's own finish reason (`length` / `max_tokens`). It says so
       outright, and it is also the only witness that survives the case where
       a truncated response happens to parse -- a cut-off outer object whose
       first complete inner object gets recovered by _extract_balanced_object
       parses cleanly and then fails validation on the fields that never
       arrived.
    2. Where the parse died. `Unterminated string` is raised only when the
       scanner runs off the end of the document, so it is EOF by construction.
       Every other message is positional, and the distinction is whether
       anything follows: a truncation fails at the last character (`{"a": 1`
       -> `Expecting ',' delimiter` at the end), while a genuinely malformed
       object fails with its remainder still ahead of it (`{"a": "he said
       "hi""}` -> the same message, a third of the way in). Both real cases
       from the playthrough that prompted this -- position 5042 and position
       10054 -- were end-of-text.
    """
    if response_truncated():
        return True

    text = _strip_fences(raw)
    if not text:
        # Nothing at all is its own diagnosis (a reasoning model that spent
        # the whole budget thinking), but it is not evidence of truncation --
        # a provider returning an empty body looks identical, and the finish
        # reason above is what tells them apart.
        return False

    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        if exc.msg.startswith("Unterminated string"):
            return True
        return exc.pos >= len(text.rstrip())
    except Exception:
        return False
    return False


def json_failure_diagnosis(raw: str, *, max_tokens=None) -> str:
    """One sentence saying WHICH JSON failure this was, and what would help.

    SAY WHICH FAILURE THIS IS, AND OFFER THE REMEDY THAT MATCHES IT. Three
    things arrive at a caller as the same `JSONDecodeError` and only one of
    them is fixed by asking for less:

      * the object was CUT OFF -- `output_ran_out_of_room` above is the
        authority, finish reason first, end-of-text second;
      * the response is the model's own REASONING, with no object in it at
        all -- a retry is the remedy and a smaller request is not;
      * the object is there and MALFORMED -- neither more room nor fewer
        fields changes that.

    Measured (multitude, 2026-09-05, PM20): a location plan came back as
    2,270 characters ending "...plus 2 featured = 14 total residents!", and
    the refusal told the host the plan had outrun its 16,000-token budget and
    to ask for fewer rooms. It had not, and shrinking the request could not
    have helped -- the retry that did work asked for the same thing again.
    A host following that advice narrows a story for no reason.

    `max_tokens` is named in the sentence only for the case where the budget
    is actually the answer, because a number that is not the cause is worse
    than no number.
    """
    text = _strip_fences(raw)
    if output_ran_out_of_room(raw):
        budget = (" -- it outran its %d-token budget; ask for less"
                  % int(max_tokens)) if max_tokens else " -- ask for less"
        return "the response ends mid-structure%s" % budget
    if not text:
        return ("the response is empty -- the call produced no answer at "
                "all, and the remedy is another attempt")
    if _extract_balanced_object(text) is None and "{" not in text:
        return ("the response carries no JSON object at all -- the text is "
                "the model's own prose or reasoning, so the remedy is "
                "another attempt, not a smaller request")
    return ("the object is malformed rather than cut short -- a smaller "
            "request will not change it")


def strict_json_parse(text: str) -> dict:
    raw = _strip_fences(text)

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        value = _extract_balanced_object(raw)
        if value is None:
            value = _restarted_object(raw)
        if value is None:
            raise RuntimeError(
                "LLM returned invalid JSON: "
                f"{exc.msg} at position {exc.pos}"
            ) from exc

    if not isinstance(value, dict):
        raise RuntimeError(
            "LLM output must be one JSON object"
        )

    return value


def _parse_whole(raw: str) -> dict:
    """`strict_json_parse`, refusing what salvage reads out of a CUT-OFF
    answer. Every parse of the repair ladder goes through here.

    Salvage exists for an answer that is whole but wrapped -- in prose, or
    after a restarted fragment -- and reads the object that runs to the end
    of the text. A cut-off answer can END exactly where an inner object
    closes, and salvage then returns that inner object as the answer.
    Measured 2026-09-28 on a designed failure (chat 154's departure, the
    encoder's interpret answer cut at 60%): one sensory event's own fields
    were read as the whole encoder answer, validated with zero events, and
    the beat's encoding was lost without a word -- the check-and-repair pass
    rebuilt it from the prose. So when the text as a whole does not parse
    and the truncation witness says it ran out of room, nothing salvaged
    from it is taken: the re-ask with room is the remedy.
    """
    value = strict_json_parse(raw)
    if output_ran_out_of_room(raw):
        try:
            json.loads(_strip_fences(raw))
        except ValueError:
            raise RuntimeError(
                "LLM returned a cut-off answer; what parsed out of it is a "
                "fragment, not the answer") from None
    return value

# --- The cheap rung: patch the fields that failed, not the whole beat -------

def _error_paths(errors):
    """The dotted field paths named by validator messages ("a.b: msg")."""
    paths = []
    for error in (errors or []):
        text = str(error)
        if ":" not in text:
            continue
        path = text.split(":", 1)[0].strip()
        if path and " " not in path and path not in paths:
            paths.append(path)
    return paths


def _dig(obj, path):
    """(value, found) at a dotted path, list indices included."""
    node = obj
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and \
                int(part) < len(node):
            node = node[int(part)]
        else:
            return None, False
    return node, True


def _place(obj, path, value):
    """Set a dotted path in place. Only ever called for a path that dug."""
    parts = path.split(".")
    node = obj
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def _targeted_field_patch(parsed, errors, *, validate=None):
    """Fix the named fields with a small call, and splice deterministically.

    The repair rung above this one rebuilds the COMPLETE response on the
    stage's own model: the whole beat re-authored because one field arrived
    in the wrong shape. Measured live: `state_assertions.overlays` came back
    a list instead of a map and cost a 4.2s full round-trip on the Director's
    model -- for a channel a specialist replaced immediately afterwards. A
    decision-review retry on a character cost 36.3s the same way.

    The error already says exactly which path failed and why, so this asks
    only about those fields, on the cheap `repair` model, and splices the
    answer back at the paths that failed and NOWHERE ELSE. Everything
    outside those paths is byte-identical by construction, which is what
    makes a model this small safe to use here: it cannot touch the beat.

    Takes the parsed object and the errors and NOTHING ELSE THE MODEL COULD
    SEE. It used to be handed `step_key` and `payload` as well, and read
    neither -- which is the honest signature for what this is allowed to do.
    The beat's own request is exactly the context that would let a cheap model
    rewrite content nobody complained about, and the guarantee above is that
    it cannot.

    `validate` is the one exception and it is not a widening: a predicate the
    caller supplies, run on THIS FUNCTION'S OWN OUTPUT after the provider has
    already answered, and never sent anywhere. It exists because acceptance is
    the caller's to decide -- a patch that touched fields and still failed
    validation was logged `ok=True` (review 2026-09-07 A84's own diagnostic
    saying the opposite of what it means), and only the caller can say.

    Returns the patched object, or None to fall through to the full repair.
    """
    if not isinstance(parsed, dict) or not parsed:
        return None
    paths = _error_paths(errors)[:4]
    fragments, messages = {}, []
    for path in paths:
        value, found = _dig(parsed, path)
        if not found:
            continue
        fragments[path] = value
        messages += [str(e) for e in (errors or [])
                     if str(e).startswith(path + ":")]
    if not fragments:
        return None
    _system = get_prompt("patch_json_field")
    _payload = {"invalid_fragments": fragments,
                "validation_errors": messages}
    _wall0 = time.time()
    raw = ""
    try:
        raw = chat_complete(
            "repair",
            _system,
            json.dumps(_payload, ensure_ascii=False),
            temperature=0.0,
            max_tokens=1500,
        )
        patch = strict_json_parse(raw)
    except Aborted:
        raise
    except Exception as exc:
        # A PROVIDER CALL WAS MADE AND IS RECORDED (A84). This rung answers
        # with the corrected FIELDS rather than the step's object, so it
        # returned through `_accepted` and the capture never saw it at all --
        # neither its cost nor the cheap model's answer.
        note_provider_exchange(
            role="repair", system=_system, payload=_payload, response=raw,
            ok=False, started=_wall0, error=str(exc))
        return None
    usable = isinstance(patch, dict) and bool(patch)
    out, touched = None, []
    if usable:
        out = json.loads(json.dumps(parsed))
        for path, value in patch.items():
            # ONLY a path that actually failed. A patch naming anything else
            # is rewriting a field nobody complained about, which is the one
            # thing this rung must never do.
            if path in fragments:
                _place(out, path, value)
                touched.append(path)
    stood = bool(touched)
    if stood and validate is not None:
        # A diagnostic must never fail the call it is describing: a predicate
        # that raises leaves the row honest (`ok=False`) and the caller free
        # to raise on its own terms.
        try:
            stood = bool(validate(out))
        except Exception:  # noqa: BLE001
            stood = False
    note_provider_exchange(
        role="repair", system=_system, payload=_payload, response=raw,
        ok=stood, started=_wall0,
        error=("" if stood else
               "the patched object still failed validation" if touched
               else "the patch named no field that failed" if usable
               else "the repair model answered with no usable object"))
    return out if touched else None


#: WHICH ATTEMPT AN ACCEPTED ANSWER CAME FROM, for the caller that keeps a
#: record of the call (`director_prose.encode` files it on the stage's
#: prose-contract record as `encoder.attempt`). Set by `_accepted` on every
#: accepted answer of `complete_validated_json`, read by the caller right
#: after the call returns, on the same thread: one of
#:   first           the request's own answer
#:   mended          that answer with its brackets mended locally, no call
#:   stall_reask     the request asked again after an empty object
#:   room_reask      asked again with more room after a cut answer
#:   runaway_reask   asked again at the same budget after a runaway
#:   field_patch     the failing fields patched by the repair model
#:   rebuild         the temperature-0 rebuild of the broken answer
#:   rebuild_mended  that rebuild with its brackets mended locally
#:   fallback:N      fallback candidate N rebuilding it
#:   first_pruned    the request's own answer with only its failing fields
#:                   taken out, kept because the rung that repaired it
#:                   answered with less (`_unshrunk`) -- the events the beat
#:                   commits are the first answer's, whichever rung ran
#:   fresh           the request asked afresh after a malformed answer
#:   fresh_mended    that fresh answer with its brackets mended locally
#: The trace said none of this before (D5, 2026-10-09): every rung after
#: the first spoke only as an unattributed "llm second call" warning, so a
#: beat's record could not say which attempt its encoding came from.
answered_by: contextvars.ContextVar[str] = contextvars.ContextVar(
    "llm_quality_answered_by", default="")


def _accepted(report, rung="first"):
    """Return an accepted output, saying out loud what it cost to accept it.

    `ValidationReport.warnings` is written on the SUCCESS path. A malformed
    `state_diff` channel, or a whole malformed specialist channel, is DROPPED
    by `validate_llm_output_strict` and the report comes back `valid=True`
    with a warning naming what went -- so the beat commits, correctly, minus
    a piece of world state the model did adjudicate. Every rung of the ladder
    below returned `report.output` and read no further, which made that the
    one repair in the engine that changed a committed beat and announced
    nothing: not in `ctx.warnings`, not in `_engine_notes`, not in the
    pipeline drawer.

    A caller with no pipeline step in scope (importers, generators, jobs)
    still gets its output; `note_step_warning` is a no-op there.

    `rung` is the attempt the answer came from (`answered_by`).
    """
    answered_by.set(str(rung or "first"))
    for warning in (report.warnings or []):
        note_step_warning(f"llm validation: {warning}")
    return report.output


_SCHEMA_CACHE: dict = {}

# JSON Schema annotations help a human reading a generated schema, but they do
# not constrain a provider's sampler.  The character schema in particular is
# prompt-sized: Pydantic's titles/defaults/descriptions made its wire copy
# 26,446 bytes, while the constraint-equivalent copy is 7,477.  Local
# validation still uses the original Pydantic model; only the grammar offered
# to the provider is compacted here.
_SCHEMA_ANNOTATIONS = frozenset({
    "title", "description", "default", "examples", "$comment",
    "deprecated", "readOnly", "writeOnly",
})


def _constraint_only_schema(value):
    """Copy a JSON Schema without non-enforcing annotation keywords."""
    if isinstance(value, dict):
        return {
            key: _constraint_only_schema(item)
            for key, item in value.items()
            if key not in _SCHEMA_ANNOTATIONS
        }
    if isinstance(value, list):
        return [_constraint_only_schema(item) for item in value]
    return value


# FIELDS THE GRAMMAR REQUIRES AND VALIDATION DOES NOT. Every narrator field
# defaults, so its grammar let a constrained model answer `{}` -- and a model
# stalled into exactly that. Measured 2026-09-28 on the two captured narrator
# stall prompts, 30 sends each on the owner's routing (z-ai/glm-5.2): the
# step's own grammar came back `{}` 9 times in 60; with `prose` required and
# non-empty, 0 in 60, the shortest page 714 characters, median time
# unchanged. The WIRE only: validation keeps the default, because a content
# judgment may not buy the narrator a repair (the stall rung in
# `complete_validated_json`), and a provider that samples without the grammar
# still gets that rung's re-ask on an empty object.
_WIRE_REQUIRED = {"narrator": ("prose",)}

# FIELDS THE STEP'S MODEL DECLARES AND THE MODEL IS NEVER ASKED TO WRITE.
# `NarratorOutput.text` is the engine's alias of `prose` (written by
# `agents/narration._generate_narration` after validation, read there as a
# spelling of `prose` when a model files its page under it) and
# `paragraph_count` is engine-written by `schemas.preprocess_llm_output`.
# Both stay declared so they survive validation into the stored variant;
# only the grammar stops offering them. An optional string field in a grammar
# is an invitation: measured on the Brackwater run (chat 166, 2026-10-07),
# 15 of 40 narrator calls wrote the page a second time into `text`, and one
# (capture 6416, turn 4592) went on from `text` into a 5,521-tag
# `<fragment>` loop until the 50,000-token cap -- 238.8 s, finish=length,
# 138,724 characters of answer around a page that had closed whole. A
# provider that samples without the grammar may still send either field,
# and the readers above take it as they always did.
_WIRE_OMITTED = {"narrator": ("text", "paragraph_count")}


def _wire_omitted(step_key, schema):
    """The step's schema without its `_WIRE_OMITTED` fields: declared for
    validation and storage, never offered to the model to write. A field the
    schema does not declare is skipped, so a model change cannot make this
    raise or reshape anything else."""
    props = (schema.get("properties") or {}) if isinstance(schema, dict) else {}
    fields = [f for f in _WIRE_OMITTED.get(step_key, ()) if f in props]
    if not fields:
        return schema
    schema = dict(schema)
    schema["properties"] = {k: v for k, v in props.items() if k not in fields}
    if schema.get("required"):
        schema["required"] = [f for f in schema["required"] if f not in fields]
    return schema


def _wire_required(step_key, schema):
    """The step's schema with its `_WIRE_REQUIRED` strings required and
    non-empty. A field the schema does not declare as a string is left as
    it is, so a model change cannot turn this into a grammar that refuses
    every answer."""
    fields = [f for f in _WIRE_REQUIRED.get(step_key, ())
              if isinstance(schema, dict)
              and ((schema.get("properties") or {}).get(f) or {}).get("type") == "string"]
    if not fields:
        return schema
    schema = dict(schema)
    schema["properties"] = {**schema["properties"],
                            **{f: {**schema["properties"][f], "minLength": 1} for f in fields}}
    schema["required"] = sorted(set(schema.get("required") or []) | set(fields))
    return schema


def _step_json_schema(step_key: str):
    """The JSON Schema for a step, or None if it has no model or will not build.

    Cached because `model_json_schema()` walks the whole Pydantic graph and
    these are the hottest calls in the process. None is a first-class answer:
    every caller treats a missing schema as "send the advisory flag instead".
    """
    if step_key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[step_key]
    schema = None
    try:
        from llm import schemas

        model_cls = (schemas.SCHEMA_MAP or {}).get(step_key)
        if model_cls is not None:
            # Pydantic 2 renamed ``schema`` to ``model_json_schema``. The
            # project supports both majors, so use the public method exposed
            # by the installed version rather than failing closed on 1.x.
            schema_builder = getattr(model_cls, "model_json_schema", None)
            schema = (schema_builder() if schema_builder is not None
                      else model_cls.schema())
            schema = _wire_required(step_key, _wire_omitted(
                step_key, _constraint_only_schema(schema)))
    except Exception:
        schema = None
    _SCHEMA_CACHE[step_key] = schema
    return schema


def note_provider_exchange(*, role, system, payload, response, ok,
                           started, error=""):
    """Record ONE provider call for the debug capture: what was actually sent
    on that call, what came back, and whether it stood.

    ONE ROW PER CALL, NOT ONE PER ACCEPTED ANSWER (review 2026-09-07 A84).
    This used to be a closure over `complete_validated_json`'s OUTER `system`
    and `payload`, hardcoding `ok: True`, reached from the three success
    returns that happened to be in scope. So the ladder was invisible in
    exactly the cases it exists for: a beat that failed validation and was
    rebuilt by the temperature-0 repair recorded the ORIGINAL sheet and
    payload against the repair's answer -- an exchange that never happened --
    while the two rungs that answer with a different object, the targeted
    field patch and the fallback candidates, recorded nothing at all, and no
    failed attempt was recorded ever. The invisible-second-call rate that the
    2026-08-11 audit could not measure is exactly what this makes readable.

    `ok=False` rows are the point: a provider error, a parse failure and a
    validation failure are three different stories and the capture could tell
    none of them apart from a call that never happened.

    A diagnostic must never fail the call it is describing, so everything is
    swallowed. No-op outside a step; the sink is armed on every step, so the
    debug-capture setting gates the WRITE (`llm_capture.record_exchange`) and
    not this funnel.
    """
    try:
        from core.pipeline_context import note_step_exchange
        from llm import providers
        from llm.providers import last_reasoning
        note_step_exchange({
            "role": role,
            # The model of record for this exchange. The `llm_calls` ledger
            # already carries requested/served per call; this is only so an
            # exported turn reads without a join.
            "requested": str((providers.agent_models().get(role) or {})
                             .get("model") or ""),
            "system": system,
            "payload": payload,
            # What CAME BACK, verbatim, on every rung. The accepted rung used
            # to record the validated object instead, which is a different
            # artefact from the one the provider sent and cannot show a
            # truncation or a stray prose preamble.
            "response": response,
            "reasoning": last_reasoning.get() or "",
            "started": started,
            "duration": time.time() - started,
            "ok": bool(ok),
            "error": str(error or "")[:400],
            # HOW the call was shaped and how it stopped: `response_format`
            # type, reasoning effort, `max_tokens` as sent, and the finish
            # reason. Read here, on the thread that made the call, because
            # the provider stashes them per context exactly as it does the
            # reasoning trace above. A call that never reached the wire
            # reads empty, which is the honest answer.
            **providers.request_shape(),
        })
    except Exception:
        pass


def _mended(step_key, raw, payload):
    """`(parsed, report, edits)` for the first local mend of `raw` that
    validates against the step's schema, else the first that merely parses
    (its report invalid, so the rungs below repair real content instead of
    `{}`), else None. See `llm/json_mend.py` for what a mend may touch.

    It mends the text the PARSER reads, fence taken off (`_strip_fences`):
    the live encoder answers inside a ```json fence, and on the first live
    designed-failure run (2026-09-28, chat 154's departure) the fence made
    every candidate unparseable, so two swapped closers went to a 6-7 s
    model rebuild each."""
    from llm.json_mend import mend_candidates

    first = None
    for value, edits in mend_candidates(_strip_fences(raw)):
        report = validate_llm_output_strict(step_key, value, source_payload=payload)
        if report.valid:
            return value, report, edits
        if first is None:
            first = (value, report, edits)
    return first


def _bare_prose_answer(step_key, raw):
    """`{"prose": raw}` when a step whose answer IS its prose sent the prose
    alone, without the JSON around it; else None.

    Measured on the round-7 real-turn replays (2026-09-23, NanoGPT
    z-ai/glm-5.2:thinking): the narrator's first answer on 4 of 13 beats was
    the narration itself, HTML paragraphs and all, cleanly finished -- once
    with json_schema requested -- and the parse failed at position 0. The
    temperature-0 repair then spent 9-52 s re-sending the same prose in an
    envelope, and on one beat, by its own reasoning, rewrote the engine's
    `{{L1}}` line tokens into its own version of the lines on the way.

    Which steps: those whose schema declares `prose`, and validation still
    decides whether prose alone is a whole answer -- the narrator's every
    field is optional, the prose author's places default empty. Refused: a
    reply that opens as JSON or a fence (a broken object is not prose), one
    with no word in it, and one the provider cut off for length."""
    from llm.schemas import SCHEMA_MAP, _fields
    model = SCHEMA_MAP.get(step_key)
    if model is None or "prose" not in _fields(model):
        return None
    text = str(raw or "").strip()
    if not text or text[0] in "{[`" or not re.search(r"\w", text):
        return None
    if output_ran_out_of_room(raw):
        return None
    return {"prose": text}


def _parse_or_bare(step_key, raw):
    """`(parsed, error)`: the answer parsed whole, or -- where it does not
    parse -- the bare-prose page a prose step may answer with
    (`_bare_prose_answer`), read exactly as the first attempt reads it.

    EVERY ASKING OF THE SAME REQUEST READS ITS ANSWER THE SAME WAY. The
    runaway or escalation re-ask, the empty-object stall re-ask and the
    malformed-answer fresh re-ask each parsed whole only, so a narrator page
    the first attempt would have taken as bare prose -- which GLM 5.2
    thinking wrote on 4 of 13 first answers -- failed the beat when it came
    back on a re-ask (review of the 2026-10-08 landing)."""
    try:
        return _parse_whole(raw), None
    except Exception as exc:
        bare = _bare_prose_answer(step_key, raw)
        if bare is not None:
            note_step_warning(
                f"{step_key}: the answer came as bare prose without its JSON "
                "envelope; the prose is the answer")
            return bare, None
        return {}, str(exc)


#: The response format of a rung that rebuilds a broken answer -- the
#: temperature-0 repair and every fallback candidate -- whatever the role
#: or the call chose (see `providers._role_json_mode`). The grammar where
#: the provider supports it; the advisory flag where it does not.
REBUILD_FORMAT = "json_schema"

#: The steps whose same-provider rebuild is sent their OWN sheet ahead of
#: `repair_json`, as every fallback candidate already is: the two calls that
#: write the encoder's transforms. Their payload names the work but not the
#: channel protocols, and a rebuild without them repairs by guessing --
#: an inventory hand once rebuilt a transfer as entity definitions because the
#: generic example showed an entities patch. Measured on the owner's capture
#: (2026-09-28): the sheet-less rebuild was valid 58 of 58 times outside the
#: transform contract, and 52 of 70 inside it, where 12 of the 47 that
#: rebuilt a parseable answer came back with fewer writes.
#:
#: AND THE OPENING'S, whose contract is the whole world the story opens on.
#: Chat 167's rerolled opening (2026-10-10, capture 7016) failed for leaving
#: its bodies and things out; the sheet-less rebuild, reasoning off, then
#: authored the opening afresh from the generic repair sheet -- one entity,
#: two positions -- and that thin world was committed and checkpointed as
#: the story's start. 8 of the play database's 144 establish answers went
#: through the rebuild, and 6 came out with one entity or none.
REBUILD_KEEPS_SHEET = frozenset({"director_specialist", "director_repair",
                                 "director_establish"})

#: How many times a request is asked AFRESH -- the original request, its own
#: sheet and sampler, no broken draft attached -- when a malformed answer is
#: in its failure (none parsed, or any rung's own answer came back malformed
#: and was not cut for room) before the stage fails; never when the
#: request's own answer was cut, which is the re-ask with room's. One, and
#: the owner ruled it (2026-10-09, D5 of the Brackwater run: "one fresh
#: encoder attempt before a beat with a malformed repair aborts" -- an
#: aborted beat is the worst break in immersion, and the attempt costs one
#: call only on a beat that would otherwise fail). The slip it answers is
#: rare: 2 of 464 captured encoder answers in the scratch play database,
#: both the one lost beat's (turn 4601), and no kept prose-contract beat of
#: either database (338 and 236) reached the ladder at all; the same request
#: asked again parsed, while each re-ask costs a whole first call (an
#: encoder request there ran ~35k input tokens, ~10 s).
MALFORMED_REASKS = 1
#: The fresh ask goes out ONCE: a runaway on it is not re-asked again by the
#: transport (`providers.RetryConfig.degenerate_retries`), which already
#: re-asked the first request's runaway up to its own retries.
_FRESH_ASK_RETRY = RetryConfig(degenerate_retries=0)


def _content_size(step_key, obj):
    """`(events or answers, writes)` a transform-writing step's answer
    carries, or None for any other step."""
    if not isinstance(obj, dict):
        return None
    if step_key == "director_specialist":
        events = [e for e in obj.get("events") or [] if isinstance(e, dict)]
        return len(events), sum(len(e.get("transforms") or []) for e in events)
    if step_key == "director_repair":
        answers = [a for a in obj.get("answers") or [] if isinstance(a, dict)]
        return len(answers), sum(len(a.get("events") or []) + len(a.get("transforms") or [])
                                 for a in answers)
    return None


def _without_paths(obj, paths):
    """A copy of `obj` with the value at each dotted path removed -- a list
    item taken out, a key dropped -- latest index first, so one removal
    cannot shift the next."""
    import copy

    out = copy.deepcopy(obj)

    def order(path):
        return [(0, int(part)) if part.isdigit() else (1, part)
                for part in path.split(".")]

    for path in sorted(paths, key=order, reverse=True):
        parts = path.split(".")
        node = out
        for part in parts[:-1]:
            if isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            elif isinstance(node, dict) and part in node:
                node = node[part]
            else:
                node = None
                break
        last = parts[-1]
        if isinstance(node, list) and last.isdigit() and int(last) < len(node):
            node.pop(int(last))
        elif isinstance(node, dict):
            node.pop(last, None)
    return out


def _unshrunk(step_key, original, original_errors, rebuilt, payload, rung):
    """`(report, kept_first)`: the report to accept for a rebuilt answer --
    `rebuilt`, unless it carries fewer events or writes than the answer it
    was asked to repair -- and whether that report is the FIRST answer kept
    with its failing fields taken out, which the caller files as
    `first_pruned` (`answered_by`): the beat's events are then the first
    answer's, and naming the rung that was refused would say otherwise.

    FIXING BY DELETION is the rebuild's quiet failure: an answer made valid
    by dropping what it could not fix. Measured on the retired hands, the
    encoder's same transform contract: 12 of 47 rebuilds of a parseable
    answer came back with fewer writes -- one kept 1 of 3 contact ops,
    another flipped its status and dropped its write. When the original
    answer, with only the fields its validation named taken out, still
    validates and carries at least as much, that is what the beat keeps.
    Otherwise the rebuild stands, said out loud."""
    before = _content_size(step_key, original)
    after = _content_size(step_key, rebuilt.output)
    if before is None or after is None or all(a >= b for a, b in zip(after, before)):
        return rebuilt, False
    kept = _without_paths(original, _error_paths(original_errors))
    kept_report = validate_llm_output_strict(step_key, kept, source_payload=payload)
    kept_size = _content_size(step_key, kept_report.output) if kept_report.valid else None
    if kept_size is not None and all(k >= a for k, a in zip(kept_size, after)):
        note_step_warning(
            f"{step_key}: the {rung} answered with less than the answer it "
            f"repaired ({before[0]} -> {after[0]} entries, {before[1]} -> "
            f"{after[1]} writes); kept that answer with only its failing "
            "fields taken out")
        return kept_report, True
    note_step_warning(
        f"{step_key}: the {rung} answered with less than the answer it "
        f"repaired ({before[0]} -> {after[0]} entries, {before[1]} -> "
        f"{after[1]} writes); accepted, as nothing else validates")
    return rebuilt, False


def complete_validated_json(
    *,
    role: str,
    step_key: str,
    system: str,
    payload: dict,
    temperature=None,
    max_tokens: int | None = None,
    sampler=None,
    repair_attempts: int = 1,
    response_format=None,
    history=None,
    tools=None,
    folded_payload=None,
    first_raw=None,
    first_started=None,
    rung_system=None,
    prefix=None,
) -> dict:
    # None means "the configured ceiling" (providers._clamp_max_tokens). This
    # used to be a hardcoded 16000, which made max_output_tokens a one-way
    # knob: the clamp only ever LOWERS, so raising the setting above 16000
    # changed nothing for the stage that most needs the room. Measured in maze
    # arm A11 -- a reasoning model's thinking is billed as output, so trinity
    # spent 11-13k tokens deliberating before emitting any JSON, hit exactly
    # 16000, and the beat died on `Unterminated string`. The engine's comment
    # invites raising the ceiling for "a model with a genuinely larger usable
    # output window"; that invitation did not work.
    user = json.dumps(payload, ensure_ascii=False)
    _capture_t0 = time.time()

    provider_errored = False
    last_provider_error = None
    # AN ANSWER THAT RAN AWAY IS NO OUTAGE (O27, chat 167 turn 4630). The
    # stream guard kills a runaway as `DegenerateOutput`, an LLMError, and
    # filed as the provider's failure it barred the one fresh ask a
    # malformed answer gets -- so a beat a single re-ask would have kept
    # aborted ("character_bare: all providers failed (last provider error:
    # Degenerate model output: repeating 26-character phrase)"). Kept apart
    # here: a runaway leaves no draft to repair, and earns the fresh ask.
    runaway = None
    # Raised once, by the length-escalation below, and then inherited by every
    # later attempt in this call -- a repair or a fallback candidate rebuilding
    # the same object needs the same room. None until then, which is the
    # ordinary configured ceiling.
    token_ceiling = None
    ran_out_of_room = False
    # Set by the length-escalation below when the stop was a runaway rather
    # than a crowded-out answer (`providers.answer_ran_away`).
    ran_away = False

    # The step's own Pydantic model, offered to the provider as an enforceable
    # grammar. This function already validates against it on the way back; a
    # backend that can constrain sampling with it turns that check from a
    # gate into a formality, and one that cannot is no worse off (providers
    # falls back to json_object, then to nothing). Best-effort by design --
    # a schema this fails to build must never cost the call.
    #
    # Sent on EVERY rung that rebuilds this same object, not only the first.
    # It was first-call-only, which is backwards: the later rungs are the ones
    # answering a request that has already failed validation once. The
    # truncation re-ask gains most -- a constrained model cannot pad, so the
    # object it writes fits in the budget the unconstrained one overflowed.
    # `_targeted_field_patch` deliberately does NOT get it: that rung returns
    # the corrected FIELDS, not the step's object, so the step's grammar would
    # refuse the only shape it is allowed to send.
    #
    # Whether the grammar is SENT is the role's format, or this call's own
    # (`response_format`; `providers._role_json_mode`): the request itself
    # and each re-ask of it -- the empty object, the truncation -- carry it.
    # The two rungs that REBUILD a broken answer carry `REBUILD_FORMAT`
    # instead: the first attempt had its chance at a complete answer, and
    # what the rebuild owes is a valid one.
    json_schema = _step_json_schema(step_key)

    # A CLOSING ROUND after native tool rounds (`agents/character_tools.py`):
    # the first attempt carries the rounds -- the assistant turns with their
    # calls and reasoning, the tools' results -- with the tools offered and
    # none chosen, so the model answers from where its thinking stopped, on
    # the grammar. Every later rung resends `folded_payload` instead: the
    # payload with what the tools returned folded in, so no rung can answer
    # without what this mind looked up.
    #
    # `first_raw` is an answer the model already gave in a tool round that
    # called nothing: it is validated -- and repaired -- as the first
    # attempt's would be, rather than paid for twice. `history` beside it
    # (no `tools`) is only what that round was sent, for the capture.
    #
    # The capture records what the first attempt was SENT -- the packet and
    # the rounds before it (`tool_history`) -- never the folded packet, which
    # only the later rungs send (one row per call, review 2026-09-07 A84).
    #
    # `rung_system` is the card every request after the first is sent -- the
    # one without a section promising lookups, since no later rung offers
    # tools; `first_started` is when the round that gave `first_raw` began,
    # so its capture row carries the round's time and not the validation's.
    _closing = ({"history": history, "tools": tools, "tool_choice": "none"}
                if history and tools else {})
    _sent = {**payload, "tool_history": list(history)} if history else payload
    _sent_system = system
    if first_raw is not None and first_started:
        _capture_t0 = float(first_started)

    # A CACHED PREFIX AND WHAT FOLLOWS IT (`prefix`: `{"system", "user",
    # "after"}`). The request goes as `prefix`'s system and user messages --
    # this call's own `system` and payload where it names none -- with the
    # user message a cache breakpoint where the route honours one
    # (`providers.cache_breakpoint_honoured`), and `after` the messages that
    # follow it. The first attempt and every re-ask of THE SAME REQUEST send
    # it -- the empty object, the truncation, the stall -- because each is
    # that request again. The rungs that REBUILD a broken answer and the
    # fallback candidates send `system` and `payload` on their own, as
    # before: neither continues anything. `payload` is what the answer is
    # validated against either way. The encoder sends its draft this way and
    # its repair continues the draft's own request
    # (`agents/director_repair.call_repair`).
    #
    # The capture records what was SENT (one row per call, A84): the user
    # message's object, and what followed it under `messages_after`.
    if prefix is not None and _closing:
        raise TypeError("a cached prefix does not close a tool round")
    _asked = {"prefixed": prefix is not None}
    if prefix is not None:
        _asked["system"] = prefix.get("system", system)
        _asked["user"] = prefix.get("user", user)
        _asked["after"] = list(prefix.get("after") or ())
        try:
            _shown = json.loads(prefix["user"]) if "user" in prefix else payload
        except ValueError:
            _shown = None
        if not isinstance(_shown, dict):
            _shown = {"user": _asked["user"]}
        _sent_system = _asked["system"]
        _sent = {**_shown, "messages_after": _asked["after"]}

    def _first_call(**closing):
        if _asked["prefixed"]:
            return _same_request()
        return chat_complete(
            role,
            system,
            user,
            temperature=temperature,
            max_tokens=max_tokens,
            sampler=sampler,
            candidate_offset=0,
            json_schema=json_schema,
            response_format=response_format,
            **closing,
        )

    def _same_request(**overrides):
        """The first attempt's request once more, a cached prefix and what
        follows it included -- what every re-ask of it sends."""
        shape = {"temperature": temperature, "max_tokens": max_tokens,
                 "sampler": sampler, "candidate_offset": 0,
                 "json_schema": json_schema, "response_format": response_format,
                 **overrides}
        if _asked["prefixed"]:
            return chat_complete(role, _asked["system"], _asked["user"], **shape,
                                 history=_asked["after"], cache_user=True)
        return chat_complete(role, system, user, **shape)

    def _same_request_record():
        """`(system, payload)` the capture records for a re-ask."""
        return (_sent_system, _sent) if _asked["prefixed"] else (system, payload)

    try:
        if first_raw is not None:
            raw = str(first_raw)
        else:
            try:
                raw = _first_call(**_closing)
            except ToolsUnsupported as exc:
                if not _closing and not _asked["prefixed"]:
                    raise
                note_provider_exchange(
                    role=role, system=_sent_system, payload=_sent, response="",
                    ok=False, started=_capture_t0, error=str(exc))
                if _asked["prefixed"]:
                    # The route took no message after the user's -- the role
                    # resolved to a backend that builds no OpenAI-style body
                    # after the caller shaped the request. Asked as the plain
                    # request: a beat is never lost to a cost saving.
                    note_step_warning(
                        f"{step_key}: the route took no cached prefix "
                        f"({str(exc)[:160]}); asked as the plain request")
                    _asked["prefixed"] = False
                else:
                    # The route served the tool rounds and refused the closing
                    # one (the grammar beside the tools, or the history itself).
                    # Asked again as a plain request, with what the lookups
                    # brought folded into the packet -- a beat a single call
                    # would have survived is not lost to the rounds.
                    note_step_warning(
                        f"{step_key}: the closing round was refused ({str(exc)[:160]}); "
                        "asked again without the rounds, what they found folded in")
                    if folded_payload is not None:
                        payload = folded_payload
                        user = json.dumps(payload, ensure_ascii=False)
                    if rung_system is not None:
                        system = rung_system
                _sent, _sent_system, _capture_t0 = payload, system, time.time()
                raw = _first_call()
    except Aborted:
        raise
    except LLMError as exc:
        # The primary provider itself failed (auth/model-not-found/5xx past
        # retries). Don't die here -- fall through to the configured fallback
        # candidates below, which previously only ran on VALIDATION failures.
        # A runaway is no draft either, but no outage (`runaway`).
        raw = ""
        provider_errored = True
        if isinstance(exc, DegenerateOutput):
            runaway = exc
            note_step_warning(f"{step_key}: the answer ran away ({exc.reason})")
        else:
            last_provider_error = exc
        note_provider_exchange(
            role=role, system=_sent_system, payload=_sent, response="",
            ok=False, started=_capture_t0, error=str(exc))
    if folded_payload is not None:
        payload = folded_payload
        user = json.dumps(payload, ensure_ascii=False)
    if rung_system is not None:
        system = rung_system

    parse_error = None

    try:
        parsed = _parse_whole(raw)
    except Exception as exc:
        parsed = {}
        parse_error = str(exc)
        bare = None if provider_errored else _bare_prose_answer(step_key, raw)
        if bare is not None:
            parsed, parse_error = bare, None
            note_step_warning(
                f"{step_key}: the answer came as bare prose without its JSON "
                "envelope; the prose is the answer")
    # Whether any answer this request got came back MALFORMED -- text that
    # did not parse, and not an outage, a parsed answer that failed
    # validation, or an answer cut off for want of room (that one is the
    # re-ask with room's case, below). It decides the fresh ask at the foot
    # of the ladder (`MALFORMED_REASKS`), and is set again by every rung
    # below whose own answer does not parse. `any_parsed` is its other half:
    # whether any answer, on any rung, parsed at all -- which is what the
    # fresh ask's warning says of the failure, and the last rung alone
    # cannot (a malformed answer, a rebuild that parsed and failed, and a
    # malformed fallback is not "no answer parsed").
    malformed_seen = (parse_error is not None and not provider_errored
                      and not output_ran_out_of_room(raw))
    any_parsed = parse_error is None and not provider_errored

    report = validate_llm_output_strict(
        step_key,
        parsed,
        source_payload=payload,
    )

    if parse_error:
        report.valid = False
        report.errors.insert(0, parse_error)

    if not provider_errored:
        note_provider_exchange(
            role=role, system=_sent_system, payload=_sent, response=raw,
            ok=bool(report.valid), started=_capture_t0,
            error="" if report.valid else "; ".join(report.errors[:3]))

    # A BROKEN ANSWER IS MENDED HERE, BEFORE A MODEL IS ASKED
    # (`llm/json_mend.py`): its brackets and a key's quotes, never a value and
    # never an answer that ran out of room, which is the re-ask's below. The
    # capture row above keeps the answer as it came. Measured 2026-09-28:
    # 8 of the 8 unparseable answers in the owner's capture that today's
    # parser cannot read mend, the encoder's one failure in 470 calls
    # byte-for-byte into what the model rebuild had spent a round trip on.
    if parse_error and not provider_errored and not output_ran_out_of_room(raw):
        mended = _mended(step_key, raw, payload)
        if mended is not None:
            parsed, report, edits = mended
            parse_error = None
            any_parsed = True
            if report.valid:
                note_step_warning(
                    f"{step_key}: the answer's JSON was mended locally "
                    f"({'; '.join(edits)}); no model call")
                return _accepted(report, "mended")
            note_step_warning(
                f"{step_key}: the answer's JSON was mended locally "
                f"({'; '.join(edits)}) and still fails validation; the "
                "repair rungs below work on the mended answer")

    # A BARE `{}` THAT VALIDATES IS STILL NO ANSWER. Every narrator field
    # defaults, so the stall reply `{}` passed validation and COMMITTED an
    # empty page (scratch play 2026-09-14, chat 3 turn 0: the trace ended
    # "Let me render the drawing room" and the content was `{}`). The
    # narrator's standing rule -- a content judgment may not buy a REPAIR,
    # because the repair ladder is what turned an empty answer into a dead
    # turn (chat 95 t18) -- is kept whole: this is one re-ask of the same
    # request, never a repair, and an answer that says something (even
    # `{"prose": ""}`) is taken as it came. Only the literal empty object is
    # a stall.
    if (report.valid and not provider_errored and parsed == {}
            and isinstance(payload, dict) and payload):
        _t0 = time.monotonic()
        _wall0 = time.time()
        try:
            again = _same_request(token_ceiling=token_ceiling)
        except Aborted:
            raise
        except LLMError as exc:
            note_step_warning(
                "llm second call: empty-object reply re-ask errored after "
                f"{time.monotonic() - _t0:.1f}s ({exc}); the empty answer stands")
            return _accepted(report)
        note_step_warning(
            "llm second call: empty-object reply treated as a stall; "
            f"re-asked the original request ({time.monotonic() - _t0:.1f}s)")
        try:
            again_parsed = _parse_whole(again)
        except Exception:
            again_parsed = None
        _asked_system, _asked_payload = _same_request_record()
        if isinstance(again_parsed, dict) and again_parsed:
            again_report = validate_llm_output_strict(
                step_key, again_parsed, source_payload=payload)
            note_provider_exchange(
                role=role, system=_asked_system, payload=_asked_payload,
                response=again, ok=bool(again_report.valid), started=_wall0,
                error="" if again_report.valid
                else "; ".join(again_report.errors[:3]))
            if again_report.valid:
                return _accepted(again_report, "stall_reask")
        else:
            note_provider_exchange(
                role=role, system=_asked_system, payload=_asked_payload,
                response=again, ok=False, started=_wall0,
                error="empty or unparseable re-ask")
        return _accepted(report)

    if report.valid:
        return _accepted(report)

    previous_raw = raw
    previous_parsed = parsed

    # A response that was cut off for want of output budget is the one failure
    # here that the repair ladder below cannot touch, and until this existed it
    # was the ladder that ran anyway: repair re-asks the SAME model for the
    # SAME object on the SAME budget, with the truncated 5k-character attempt
    # added to the prompt. It cannot succeed, and it burns the fallback
    # candidates on its way to losing the beat. Measured live -- two of
    # fourteen beats of one playthrough died exactly this way (mapping_stage
    # mid-`why_relevant`, and a character step at position 10054), each raising
    # a validation error that named a delimiter and read as a model writing
    # nonsense.
    #
    # So: ask again, once, with room. Same request, not a repair prompt -- the
    # model had the right answer and nowhere to put it, and handing back its
    # own truncated output only makes the input larger. Bounded by
    # construction rather than by a counter: `escalated_max_tokens` adds one
    # stage's worth of headroom against the absolute cap and returns 0 when
    # there is none left, and this block is straight-line code that cannot
    # re-enter -- so the worst case is exactly one extra call, at exactly one
    # size above the ceiling, however many times the model truncates.
    #
    # MORE ROOM IS FOR AN ANSWER THINKING CROWDED OUT (`providers.
    # answer_ran_away`). A stop whose budget went to the answer itself -- more
    # of it answer than thinking, and already longer than any stage writes --
    # was not short of room: it ran away, and the same request asked again
    # at the SAME budget is what recovers it, because a runaway is a sampling
    # accident. Still one extra call, never a larger one.
    if not provider_errored and output_ran_out_of_room(raw):
        ran_out_of_room = True
        ran_away = answer_ran_away()
        token_ceiling = None if ran_away else escalated_max_tokens(max_tokens)

        if ran_away or token_ceiling:
            # Visibly, in the live turn view: `generation_reset` is what the
            # browser already understands, and it also clears the truncated
            # half-sentence still sitting in the stream pane. A silent retry
            # would make a model that never fits its budget look like a slow
            # one.
            generation_notice({
                "type": "generation_reset",
                "attempt": 2,
                "candidate": 0,
                "reason": (
                    "output ran away; retrying at the same budget"
                    if ran_away else
                    "output truncated; retrying with "
                    f"{token_ceiling} tokens"
                ),
            })

            # Instrumented, like every other rung of this ladder: a re-ask
            # that SUCCEEDS is otherwise indistinguishable from a first
            # draft in the stored step, which is how the invisible-second-
            # call rate stayed unknowable (audit 2026-08-11: failure floor
            # >=3.5% of character calls, true rate unmeasured).
            _t0 = time.monotonic()
            _wall0 = time.time()
            _budget = max_tokens if ran_away else token_ceiling
            _asked_system, _asked_payload = _same_request_record()
            try:
                raw = _same_request(max_tokens=_budget,
                                    token_ceiling=token_ceiling)
            except Aborted:
                raise
            except LLMError as exc:
                raw = ""
                provider_errored = True
                if isinstance(exc, DegenerateOutput):
                    runaway = exc
                else:
                    last_provider_error = exc
                note_provider_exchange(
                    role=role, system=_asked_system, payload=_asked_payload,
                    response="", ok=False, started=_wall0, error=str(exc))
                note_step_warning(
                    "llm second call: "
                    + ("runaway re-ask at the same budget"
                       if ran_away else
                       f"truncation re-ask at {token_ceiling} tokens")
                    + f" errored after {time.monotonic() - _t0:.1f}s ({exc})")
            else:
                note_step_warning(
                    "llm second call: "
                    + ("the answer ran away to the token ceiling (more of "
                       "the output was answer than thinking, and longer than "
                       "any stage writes); re-asked once at the same budget"
                       if ran_away else
                       "output truncated at the token ceiling; re-asked "
                       f"once with {token_ceiling} tokens")
                    + f" ({time.monotonic() - _t0:.1f}s)")
                max_tokens = _budget
                parsed, parse_error = _parse_or_bare(step_key, raw)
                # The re-ask's own answer is a rung like any other: one that
                # comes back malformed, and not cut again, earns the fresh
                # ask below exactly as the stall re-ask's and the rebuild's
                # do. Unset, an answer cut for want of room, re-asked with
                # room into a malformed one whose rebuild then parsed and
                # failed, lost the beat with no fresh attempt (scripted,
                # 2026-10-09).
                malformed_seen = malformed_seen or (
                    parse_error is not None
                    and not output_ran_out_of_room(raw))
                any_parsed = any_parsed or parse_error is None

                report = validate_llm_output_strict(
                    step_key,
                    parsed,
                    source_payload=payload,
                )

                if parse_error:
                    report.valid = False
                    report.errors.insert(0, parse_error)

                note_provider_exchange(
                    role=role, system=_asked_system, payload=_asked_payload,
                    response=raw, ok=bool(report.valid), started=_wall0,
                    error=("" if report.valid
                           else "; ".join(report.errors[:3])))

                if report.valid:
                    return _accepted(report, "runaway_reask" if ran_away
                                     else "room_reask")

                ran_out_of_room = output_ran_out_of_room(raw)
                ran_away = ran_out_of_room and answer_ran_away()
                previous_raw = raw
                previous_parsed = parsed

    # AN EMPTY OBJECT IS A STALL, NOT A DRAFT TO EDIT. A thinking model
    # sometimes spends its whole reply reasoning correctly -- the trace ends
    # "Let me construct the result." -- and finalizes as `{}`. The same class
    # as the truncation above, in another coat: the model had the answer and
    # delivered none of it, so the repair rung is the wrong tool. It hands
    # the model its own `{}` and asks for a fix, and the model reasons the
    # same way to the same nothing. Re-ask the ORIGINAL request once, with
    # its original sheet and sampler, before any repair rung.
    #
    # THE CLASS IS EVERY VALIDATED STEP, NOT THE CAUSAL DIRECTOR. Measured on
    # the owner's database, 2026-09-14: eight replies that were exactly `{}`
    # since 09-08, across five roles -- director_body, character_major, the
    # room planner twice, and on chat 123 turn 9 the contact and objects
    # hands twice each (the original and the repair that re-stalled) -- and
    # not one on the causal Director this block was first scoped to. That
    # beat lost the door state and the contact ledger to two fruitless repair
    # calls; the same request replayed three times answered three times. It
    # stays narrow in the one way that matters: an object carrying even one
    # field is a substantive attempt and follows ordinary validation, and a
    # `{}` that VALIDATED never reaches here.
    # A reply that PARSED as `{}`, not one that failed to parse: an
    # unparseable reply also leaves `parsed` empty, and that one is the
    # repair rung's own case (a delimiter the model can fix, or a truncation
    # the block above already handled).
    _empty_answer_stall = (
        parse_error is None and previous_parsed == {}
        and isinstance(payload, dict) and bool(payload)
    )
    if not provider_errored and _empty_answer_stall:
        _t0 = time.monotonic()
        _wall0 = time.time()
        _asked_system, _asked_payload = _same_request_record()
        try:
            previous_raw = _same_request(token_ceiling=token_ceiling)
        except Aborted:
            raise
        except LLMError as exc:
            if isinstance(exc, DegenerateOutput):
                runaway = exc
            else:
                last_provider_error = exc
            note_provider_exchange(
                role=role, system=_asked_system, payload=_asked_payload,
                response="", ok=False, started=_wall0, error=str(exc))
            note_step_warning(
                "llm second call: empty-object reply re-ask errored after "
                f"{time.monotonic() - _t0:.1f}s ({exc})")
        else:
            note_step_warning(
                "llm second call: empty-object reply treated as a stall; "
                f"re-asked the original request ({time.monotonic() - _t0:.1f}s)")
            previous_parsed, parse_error = _parse_or_bare(step_key, previous_raw)
            malformed_seen = malformed_seen or (
                parse_error is not None
                and not output_ran_out_of_room(previous_raw))
            any_parsed = any_parsed or parse_error is None
            # The request asked again: whether ITS answer was cut is what the
            # rungs after this one read (`_original_cut`, the final message).
            ran_out_of_room = output_ran_out_of_room(previous_raw)
            report = validate_llm_output_strict(
                step_key, previous_parsed, source_payload=payload)
            if parse_error:
                report.valid = False
                report.errors.insert(0, parse_error)
            note_provider_exchange(
                role=role, system=_asked_system, payload=_asked_payload,
                response=previous_raw, ok=bool(report.valid),
                started=_wall0,
                error="" if report.valid else "; ".join(report.errors[:3]))
            if report.valid:
                return _accepted(report, "stall_reask")

    # THE CHEAP RUNG FIRST. One malformed field does not need the whole beat
    # re-authored on the stage's own model; the validator already said which
    # path failed and why. Try a small `repair`-role call that returns only
    # the corrected fields, spliced back at exactly those paths. Falls through
    # untouched to the full rebuild below on any doubt.
    if not provider_errored and repair_attempts > 0:
        _t0 = time.monotonic()
        # ONE VALIDATION, READ TWICE (A84). The rung's capture row has to say
        # whether the patch STOOD, and only this scope can answer -- the
        # function itself is deliberately handed nothing about the step. The
        # predicate keeps its report so the acceptance test below is the same
        # pass, not a second one.
        _patch_reports = {}

        def _patch_validates(obj):
            _patch_reports["report"] = validate_llm_output_strict(
                step_key, obj, source_payload=payload)
            return bool(_patch_reports["report"].valid)

        _patched = _targeted_field_patch(previous_parsed, report.errors,
                                         validate=_patch_validates)
        if _patched is not None:
            _patched_report = _patch_reports.get("report")
            if _patched_report is None:
                _patched_report = validate_llm_output_strict(
                    step_key, _patched, source_payload=payload)
            if _patched_report.valid:
                note_step_warning(
                    "llm second call: validation failed "
                    f"({len(report.errors or [])} errors; first: "
                    f"{str((report.errors or [''])[0])[:120]!r}); repaired by "
                    f"a targeted field patch on the repair model "
                    f"({time.monotonic() - _t0:.1f}s) -- no rebuild")
                return _accepted(_patched_report, "field_patch")
            previous_parsed = _patched

    # What the rebuild and the fallbacks are repairing, kept for the check
    # that they did not repair it by deleting it (`_unshrunk`).
    _original, _original_errors = previous_parsed, list(report.errors or [])
    # Whether the request's own last answer was cut. The rungs below reassign
    # `ran_out_of_room` from THEIR answers, so the fresh re-ask, which must
    # never repeat a request that ran out of room, reads it from here.
    _original_cut = ran_out_of_room

    # Skip same-provider repair when the primary provider itself errored --
    # repairing against a down provider just wastes attempts; go to fallbacks.
    for _ in range(0 if provider_errored else max(0, repair_attempts)):
        repair_payload = {
            "original_request": payload,
            "previous_raw_output": previous_raw,
            "previous_parsed_output": previous_parsed,
            "validation_errors": report.errors,
            "required_json_example": output_example(step_key),
            "instruction": (
                "Rebuild the complete response. Preserve valid details "
                "and restore omitted information."
            ),
        }

        _first_error = str((report.errors or [""])[0])[:120]
        _t0 = time.monotonic()
        _wall0 = time.time()
        # WHAT THIS RUNG ACTUALLY SENDS, which is not the step's own sheet or
        # its own payload (A84): the repair sheet, and a payload wrapping the
        # failed attempt and the errors it failed on.
        _repair_system = get_prompt("repair_json")
        if step_key in REBUILD_KEEPS_SHEET:
            _repair_system = system + "\n\n" + _repair_system
        try:
            previous_raw = chat_complete(
                role,
                _repair_system,
                json.dumps(
                    repair_payload,
                    ensure_ascii=False,
                ),
                temperature=0.0,
                max_tokens=max_tokens,
                candidate_offset=0,
                token_ceiling=token_ceiling,
                json_schema=json_schema,
                response_format=REBUILD_FORMAT,
            )
        except Aborted:
            raise
        except LLMError as exc:
            if isinstance(exc, DegenerateOutput):
                runaway = exc
            else:
                last_provider_error = exc
            note_provider_exchange(
                role=role, system=_repair_system, payload=repair_payload,
                response="", ok=False, started=_wall0, error=str(exc))
            note_step_warning(
                "llm second call: temperature-0 repair errored after "
                f"{time.monotonic() - _t0:.1f}s ({exc})")
            break  # provider now failing; move on to fallback candidates
        note_step_warning(
            "llm second call: validation failed "
            f"({len(report.errors or [])} errors; first: {_first_error!r}); "
            f"temperature-0 repair ({time.monotonic() - _t0:.1f}s)")

        ran_out_of_room = output_ran_out_of_room(previous_raw)

        try:
            previous_parsed = _parse_whole(
                previous_raw
            )
            parse_error = None
            any_parsed = True
        except Exception as exc:
            previous_parsed = {}
            parse_error = str(exc)
            malformed_seen = malformed_seen or not ran_out_of_room

        report = validate_llm_output_strict(
            step_key,
            previous_parsed,
            source_payload=payload,
        )

        if parse_error:
            report.valid = False
            report.errors.insert(0, parse_error)

        note_provider_exchange(
            role=role, system=_repair_system, payload=repair_payload,
            response=previous_raw, ok=bool(report.valid), started=_wall0,
            error="" if report.valid else "; ".join(report.errors[:3]))

        if report.valid:
            kept, pruned = _unshrunk(step_key, _original, _original_errors,
                                     report, payload, "rebuild")
            return _accepted(kept, "first_pruned" if pruned else "rebuild")

        # The rebuild's own punctuation, mended before another candidate is
        # asked (one retired hand's rebuild in the capture was itself a
        # stray closer).
        if parse_error and not ran_out_of_room:
            mended = _mended(step_key, previous_raw, payload)
            if mended is not None and mended[1].valid:
                note_step_warning(
                    f"{step_key}: the rebuild's JSON was mended locally "
                    f"({'; '.join(mended[2])}); no further call")
                kept, pruned = _unshrunk(step_key, _original, _original_errors,
                                         mended[1], payload, "rebuild")
                return _accepted(kept, "first_pruned" if pruned
                                 else "rebuild_mended")

    candidate_count = role_candidate_count(role)

    for candidate_offset in range(1, candidate_count):
        fallback_payload = {
            "original_request": payload,
            "failed_output": previous_parsed,
            "validation_errors": report.errors,
            "required_json_example": output_example(step_key),
            "instruction": (
                "Produce a complete replacement response as strict JSON."
            ),
        }

        _t0 = time.monotonic()
        _wall0 = time.time()
        _fallback_system = system + "\n\n" + get_prompt("repair_json")
        try:
            fallback_raw = chat_complete(
                role,
                _fallback_system,
                json.dumps(
                    fallback_payload,
                    ensure_ascii=False,
                ),
                temperature=0.0,
                max_tokens=max_tokens,
                sampler=sampler,
                candidate_offset=candidate_offset,
                token_ceiling=token_ceiling,
                json_schema=json_schema,
                response_format=REBUILD_FORMAT,
            )
        except Aborted:
            raise
        except LLMError as exc:
            if isinstance(exc, DegenerateOutput):
                runaway = exc
            else:
                last_provider_error = exc
            note_provider_exchange(
                role=role, system=_fallback_system, payload=fallback_payload,
                response="", ok=False, started=_wall0, error=str(exc))
            note_step_warning(
                f"llm second call: fallback candidate {candidate_offset} "
                f"errored after {time.monotonic() - _t0:.1f}s ({exc})")
            continue  # this fallback provider errored; try the next candidate
        note_step_warning(
            f"llm second call: fallback candidate {candidate_offset} "
            f"({time.monotonic() - _t0:.1f}s)")

        ran_out_of_room = output_ran_out_of_room(fallback_raw)

        try:
            fallback_parsed = _parse_whole(
                fallback_raw
            )
        except Exception as exc:
            report.errors.append(str(exc))
            parse_error = str(exc)
            malformed_seen = malformed_seen or not ran_out_of_room
            note_provider_exchange(
                role=role, system=_fallback_system, payload=fallback_payload,
                response=fallback_raw, ok=False, started=_wall0,
                error=str(exc))
            continue
        parse_error = None
        any_parsed = True

        fallback_report = validate_llm_output_strict(
            step_key,
            fallback_parsed,
            source_payload=payload,
        )

        note_provider_exchange(
            role=role, system=_fallback_system, payload=fallback_payload,
            response=fallback_raw, ok=bool(fallback_report.valid),
            started=_wall0,
            error=("" if fallback_report.valid
                   else "; ".join(fallback_report.errors[:3])))

        if fallback_report.valid:
            kept, pruned = _unshrunk(step_key, _original, _original_errors,
                                     fallback_report, payload,
                                     f"fallback candidate {candidate_offset}")
            return _accepted(kept, "first_pruned" if pruned
                             else f"fallback:{candidate_offset}")

        report = fallback_report

    # AN ANSWER THAT NEVER PARSED IS ASKED FOR AFRESH BEFORE THE STAGE FAILS.
    # Every rung above that rebuilds a broken answer hands the model its own
    # broken text, and a model copying a long input copies its slips with it.
    # Measured, scratch story 166 turn 4601 (the Brackwater run, 2026-10-07):
    # the encoder's resolve answer left one object open at char 2778, the
    # temperature-0 rebuild came back with the same fault at the same
    # character, and the causal stage aborted the beat (the run's only two
    # unparseable encoder answers of 386). So once nothing the ladder holds
    # has parsed, the ORIGINAL request is asked again, as itself: the class
    # is the malformed answer, never a content failure (an answer that
    # parsed and failed validation is the repair rungs' own case, and a
    # truncation is the re-ask with room above, so a cut answer is not asked
    # again here).
    #
    # AND A MALFORMED REPAIR IS ASKED AFRESH TOO (the owner's ruling,
    # 2026-10-09, D5 of the Brackwater run: "one fresh encoder attempt
    # before a beat with a malformed repair aborts"). The rule above fired
    # only when NOTHING had parsed, so an answer that parsed and failed
    # validation, whose rebuild then came back malformed, lost the beat with
    # no fresh attempt -- and so did a malformed answer whose rebuild parsed
    # and still failed, and an answer cut for room whose re-ask with room
    # came back malformed. Each way a malformed answer is in the failure, and
    # a fresh asking is what recovers a slip. A beat whose every answer
    # parsed and none validated is still the repair rungs' own case.
    #
    # WHETHER THE REQUEST WAS CUT IS ITS OWN ANSWER'S, NEVER A REPAIR'S
    # (`_original_cut`). A request whose own answer ran out of room is not
    # asked again here -- it had its re-ask with room, and the same request
    # would only be cut again. A rebuild or a fallback cut off says nothing
    # about it: those are other requests, carrying the broken draft, and the
    # gate that also read the LAST rung's cut lost the beat when an
    # unmendable first answer's rebuild was cut, or a malformed rebuild's
    # last fallback (scripted on the D5 landing's second round).
    if (((malformed_seen and not provider_errored) or runaway is not None)
            and not _original_cut and last_provider_error is None):
        if runaway is not None and not malformed_seen:
            _fresh_why = f"the answer ran away ({runaway.reason})"
        elif not any_parsed:
            _fresh_why = "no answer parsed"
        elif parse_error is not None:
            _fresh_why = "the repair came back malformed"
        else:
            _fresh_why = ("the answer came back malformed and its repair did "
                          "not validate")
        for _attempt in range(MALFORMED_REASKS):
            _t0 = time.monotonic()
            _wall0 = time.time()
            # The request AS IT WAS FIRST ASKED, a cached prefix and what
            # follows it included (`_same_request`), so a continued encoder
            # repair is re-asked as the continuation it was, and recorded as
            # one (`_same_request_record`).
            _asked_system, _asked_payload = _same_request_record()
            try:
                fresh = _same_request(token_ceiling=token_ceiling,
                                      retry_config=_FRESH_ASK_RETRY)
            except Aborted:
                raise
            except LLMError as exc:
                if isinstance(exc, DegenerateOutput):
                    runaway = exc
                else:
                    last_provider_error = exc
                note_provider_exchange(
                    role=role, system=_asked_system, payload=_asked_payload, response="",
                    ok=False, started=_wall0, error=str(exc))
                note_step_warning(
                    f"llm second call: {_fresh_why}; the fresh ask of the "
                    f"original request errored after "
                    f"{time.monotonic() - _t0:.1f}s ({step_key}: {exc})")
                break
            note_step_warning(
                f"llm second call: {_fresh_why}; asked the original request "
                f"afresh ({step_key}, {time.monotonic() - _t0:.1f}s)")
            fresh_parsed, fresh_error = _parse_or_bare(step_key, fresh)
            fresh_report = validate_llm_output_strict(
                step_key, fresh_parsed, source_payload=payload)
            if fresh_error:
                fresh_report.valid = False
                fresh_report.errors.insert(0, fresh_error)
            # A bare `{}` is a stall, not an answer, whatever it validates as
            # (the empty-object rule above): the malformed answer stands as
            # the failure.
            stalled = fresh_error is None and fresh_parsed == {}
            note_provider_exchange(
                role=role, system=_asked_system, payload=_asked_payload, response=fresh,
                ok=bool(fresh_report.valid) and not stalled, started=_wall0,
                error="empty object" if stalled
                else "" if fresh_report.valid
                else "; ".join(fresh_report.errors[:3]))
            if stalled:
                break
            if fresh_report.valid:
                return _accepted(fresh_report, "fresh")
            ran_out_of_room = output_ran_out_of_room(fresh)
            if fresh_error and not ran_out_of_room:
                mended = _mended(step_key, fresh, payload)
                if mended is not None and mended[1].valid:
                    note_step_warning(
                        f"{step_key}: the fresh answer's JSON was mended "
                        f"locally ({'; '.join(mended[2])}); no further call")
                    return _accepted(mended[1], "fresh_mended")
            previous_raw, report = fresh, fresh_report
            if not fresh_error or ran_out_of_room:
                break

    # What the model ACTUALLY sent, on the exception. A validation error names
    # the field that was wrong and says nothing about the shape that was sent,
    # and those are different questions: "about_entity: field required" reads
    # as an omission whether the model omitted it, nested it, or sent a map we
    # then mangled. Twice now the same failure has been undiagnosable because
    # the raw response died inside this function, so the fix had to be
    # guessed. Trimmed hard, and attached only when everything has already
    # failed -- at which point the beat is lost anyway and the one thing worth
    # salvaging is the evidence.
    _full = str(previous_raw if previous_raw else raw or "")
    _shown = _full[:600]
    # SAY WHETHER THIS IS ALL OF IT. The trim above is what a reader sees,
    # and a 600-character window makes a response that STOPPED EARLY and one
    # that merely continues past the window look identical -- both end
    # mid-object. Diagnosed wrongly twice on 2026-09-16 from this very
    # line, once concluding a character kernel had been truncated when it
    # had run to a clean close and simply omitted two sections. The length
    # and whether the object closes are both free to compute here, and they
    # are the difference between "ask for more room" and "the model left
    # fields out", which have opposite remedies.
    _sent = ""
    if _shown.strip():
        _closes = _full.rstrip().endswith(("}", "```"))
        _sent = (" | model sent %d chars, %s: %s"
                 % (len(_full),
                    "closed" if _closes else "ENDING MID-STRUCTURE",
                    _shown))
    # For a thinking model the reasoning is where the intent is visible, and
    # a malformed answer usually has a perfectly clear intent behind it.
    try:
        from llm.providers import last_reasoning as _lr
        _think = str(_lr.get() or "")[:400]
        if _think.strip():
            _sent += f" | reasoning: …{_think[-400:]}"
    except Exception:
        pass
    # Name the cause, not the symptom. A truncation surfaces as a delimiter
    # error at a five-thousandth character, which reads as a model that cannot
    # write JSON -- and sent the last investigation of this looking at the
    # schema instead of at the budget. Say which it was, and say whether the
    # escalation had anywhere left to go.
    if ran_out_of_room:
        if ran_away and token_ceiling:
            # The first stop was thinking crowding the answer out, so it was
            # given more room -- and the retry ran away. Saying "asked again
            # at the same budget" here sent the reader the wrong way.
            _why = (f"; retried at {token_ceiling} tokens and the retry ran "
                    "away -- more of its output was answer than thinking, and "
                    "longer than any stage writes -- so more room would only "
                    "have lengthened it")
        elif ran_away:
            _why = ("; the answer ran away -- more of the output was answer "
                    "than thinking, and longer than any stage writes -- so it "
                    "was asked again at the same budget, not given more room, "
                    "which would only have lengthened it")
        elif token_ceiling:
            _why = (f"; retried at {token_ceiling} tokens and it truncated "
                    "again. Raise 'Max output tokens' in Settings, or point "
                    "this role at a model that spends less of its budget "
                    "thinking")
        elif token_ceiling == 0:
            _why = ("; the budget was already at the absolute cap, so there "
                    "was no larger retry to make")
        else:
            _why = ". Raise 'Max output tokens' in Settings"
        _sent = (
            " | RESPONSE TRUNCATED: the model ran out of output budget"
            + _why + _sent
        )
    if last_provider_error is not None:
        raise RuntimeError(
            f"{step_key}: all providers failed "
            f"(last provider error: {last_provider_error}); "
            f"validation: {'; '.join(report.errors[:6])}{_sent}"
        )
    if runaway is not None:
        raise RuntimeError(
            f"{step_key}: the answer ran away ({runaway.reason}) and its fresh "
            f"ask brought no answer that validated; "
            f"validation: {'; '.join(report.errors[:6])}{_sent}"
        )
    raise RuntimeError(
        f"{step_key} failed JSON validation: "
        + "; ".join(report.errors[:12]) + _sent
    )
