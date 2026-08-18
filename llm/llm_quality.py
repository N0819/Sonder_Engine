"""Strict JSON completion, semantic validation, and repair retries."""

import json
import re
import time

from core.pipeline_context import note_step_warning
from llm.providers import (
    chat_complete,
    escalated_max_tokens,
    generation_notice,
    response_truncated,
    role_candidate_count,
    LLMError,
    Aborted,
)
from llm.schemas import (
    output_example,
    validate_llm_output_strict,
)
from llm.prompts import get_prompt

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
                try:
                    value = json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
                return value if isinstance(value, dict) else None
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


def strict_json_parse(text: str) -> dict:
    raw = _strip_fences(text)

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        value = _extract_balanced_object(raw)
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


def _targeted_field_patch(step_key, parsed, errors, payload):
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
    try:
        raw = chat_complete(
            "repair",
            get_prompt("patch_json_field"),
            json.dumps({"invalid_fragments": fragments,
                        "validation_errors": messages}, ensure_ascii=False),
            temperature=0.0,
            max_tokens=1500,
        )
        patch = strict_json_parse(raw)
    except Aborted:
        raise
    except Exception:
        return None
    if not isinstance(patch, dict) or not patch:
        return None
    out = json.loads(json.dumps(parsed))
    touched = []
    for path, value in patch.items():
        # ONLY a path that actually failed. A patch naming anything else is
        # rewriting a field nobody complained about, which is the one thing
        # this rung must never do.
        if path in fragments:
            _place(out, path, value)
            touched.append(path)
    return out if touched else None


_SCHEMA_CACHE: dict = {}


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
    except Exception:
        schema = None
    _SCHEMA_CACHE[step_key] = schema
    return schema


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
    provider_errored = False
    last_provider_error = None
    # Raised once, by the length-escalation below, and then inherited by every
    # later attempt in this call -- a repair or a fallback candidate rebuilding
    # the same object needs the same room. None until then, which is the
    # ordinary configured ceiling.
    token_ceiling = None
    ran_out_of_room = False

    # The step's own Pydantic model, offered to the provider as an enforceable
    # grammar. This function already validates against it on the way back; a
    # backend that can constrain sampling with it turns that check from a
    # gate into a formality, and one that cannot is no worse off (providers
    # falls back to json_object, then to nothing). Best-effort by design --
    # a schema this fails to build must never cost the call.
    json_schema = _step_json_schema(step_key)

    try:
        raw = chat_complete(
            role,
            system,
            user,
            temperature=temperature,
            max_tokens=max_tokens,
            sampler=sampler,
            candidate_offset=0,
            json_schema=json_schema,
        )
    except Aborted:
        raise
    except LLMError as exc:
        # The primary provider itself failed (auth/model-not-found/5xx past
        # retries). Don't die here -- fall through to the configured fallback
        # candidates below, which previously only ran on VALIDATION failures.
        raw = ""
        provider_errored = True
        last_provider_error = exc

    parse_error = None

    try:
        parsed = strict_json_parse(raw)
    except Exception as exc:
        parsed = {}
        parse_error = str(exc)

    report = validate_llm_output_strict(
        step_key,
        parsed,
        source_payload=payload,
    )

    if parse_error:
        report.valid = False
        report.errors.insert(0, parse_error)

    if report.valid:
        return report.output

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
    if not provider_errored and output_ran_out_of_room(raw):
        ran_out_of_room = True
        token_ceiling = escalated_max_tokens(max_tokens)

        if token_ceiling:
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
            try:
                raw = chat_complete(
                    role,
                    system,
                    user,
                    temperature=temperature,
                    max_tokens=token_ceiling,
                    sampler=sampler,
                    candidate_offset=0,
                    token_ceiling=token_ceiling,
                )
            except Aborted:
                raise
            except LLMError as exc:
                raw = ""
                provider_errored = True
                last_provider_error = exc
                note_step_warning(
                    "llm second call: truncation re-ask at "
                    f"{token_ceiling} tokens errored after "
                    f"{time.monotonic() - _t0:.1f}s ({exc})")
            else:
                note_step_warning(
                    "llm second call: output truncated at the token "
                    f"ceiling; re-asked once with {token_ceiling} tokens "
                    f"({time.monotonic() - _t0:.1f}s)")
                max_tokens = token_ceiling
                try:
                    parsed = strict_json_parse(raw)
                    parse_error = None
                except Exception as exc:
                    parsed = {}
                    parse_error = str(exc)

                report = validate_llm_output_strict(
                    step_key,
                    parsed,
                    source_payload=payload,
                )

                if parse_error:
                    report.valid = False
                    report.errors.insert(0, parse_error)

                if report.valid:
                    return report.output

                ran_out_of_room = output_ran_out_of_room(raw)
                previous_raw = raw
                previous_parsed = parsed

    # THE CHEAP RUNG FIRST. One malformed field does not need the whole beat
    # re-authored on the stage's own model; the validator already said which
    # path failed and why. Try a small `utility` call that returns only the
    # corrected fields, spliced back at exactly those paths. Falls through
    # untouched to the full rebuild below on any doubt.
    if not provider_errored and repair_attempts > 0:
        _t0 = time.monotonic()
        _patched = _targeted_field_patch(
            step_key, previous_parsed, report.errors, payload)
        if _patched is not None:
            _patched_report = validate_llm_output_strict(
                step_key, _patched, source_payload=payload)
            if _patched_report.valid:
                note_step_warning(
                    "llm second call: validation failed "
                    f"({len(report.errors or [])} errors; first: "
                    f"{str((report.errors or [''])[0])[:120]!r}); repaired by "
                    f"a targeted field patch on the repair model "
                    f"({time.monotonic() - _t0:.1f}s) -- no rebuild")
                return _patched_report.output
            previous_parsed = _patched

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
        try:
            previous_raw = chat_complete(
                role,
                get_prompt("repair_json"),
                json.dumps(
                    repair_payload,
                    ensure_ascii=False,
                ),
                temperature=0.0,
                max_tokens=max_tokens,
                candidate_offset=0,
                token_ceiling=token_ceiling,
            )
        except Aborted:
            raise
        except LLMError as exc:
            last_provider_error = exc
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
            previous_parsed = strict_json_parse(
                previous_raw
            )
            parse_error = None
        except Exception as exc:
            previous_parsed = {}
            parse_error = str(exc)

        report = validate_llm_output_strict(
            step_key,
            previous_parsed,
            source_payload=payload,
        )

        if parse_error:
            report.valid = False
            report.errors.insert(0, parse_error)

        if report.valid:
            return report.output

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
        try:
            fallback_raw = chat_complete(
                role,
                system + "\n\n" + get_prompt("repair_json"),
                json.dumps(
                    fallback_payload,
                    ensure_ascii=False,
                ),
                temperature=0.0,
                max_tokens=max_tokens,
                sampler=sampler,
                candidate_offset=candidate_offset,
                token_ceiling=token_ceiling,
            )
        except Aborted:
            raise
        except LLMError as exc:
            last_provider_error = exc
            note_step_warning(
                f"llm second call: fallback candidate {candidate_offset} "
                f"errored after {time.monotonic() - _t0:.1f}s ({exc})")
            continue  # this fallback provider errored; try the next candidate
        note_step_warning(
            f"llm second call: fallback candidate {candidate_offset} "
            f"({time.monotonic() - _t0:.1f}s)")

        ran_out_of_room = output_ran_out_of_room(fallback_raw)

        try:
            fallback_parsed = strict_json_parse(
                fallback_raw
            )
        except Exception as exc:
            report.errors.append(str(exc))
            continue

        fallback_report = validate_llm_output_strict(
            step_key,
            fallback_parsed,
            source_payload=payload,
        )

        if fallback_report.valid:
            return fallback_report.output

        report = fallback_report

    # What the model ACTUALLY sent, on the exception. A validation error names
    # the field that was wrong and says nothing about the shape that was sent,
    # and those are different questions: "about_entity: field required" reads
    # as an omission whether the model omitted it, nested it, or sent a map we
    # then mangled. Twice now the same failure has been undiagnosable because
    # the raw response died inside this function, so the fix had to be
    # guessed. Trimmed hard, and attached only when everything has already
    # failed -- at which point the beat is lost anyway and the one thing worth
    # salvaging is the evidence.
    _shown = str(previous_raw if previous_raw else raw or "")[:600]
    _sent = f" | model sent: {_shown}" if _shown.strip() else ""
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
        if token_ceiling:
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
    raise RuntimeError(
        f"{step_key} failed JSON validation: "
        + "; ".join(report.errors[:12]) + _sent
    )
