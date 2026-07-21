"""Strict JSON completion, semantic validation, and repair retries."""

import json
import re

from providers import chat_complete, role_candidate_count, LLMError, Aborted
from schemas import (
    output_example,
    validate_llm_output_strict,
)

_REPAIR_SYSTEM = """
You repair JSON responses produced by another model.

Return exactly one strict JSON object. Do not use Markdown fences.
The object must match the supplied rigid example structurally.

Preserve all valid information from the previous response.
Restore information omitted from the previous response by consulting the
original request. Fix every validation error, not merely the first one.

Do not explain your changes.
""".strip()

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


def strict_json_parse(text: str) -> dict:
    raw = str(text or "").strip()

    raw = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.I,
    )
    raw = re.sub(r"\s*```$", "", raw)

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

def complete_validated_json(
    *,
    role: str,
    step_key: str,
    system: str,
    payload: dict,
    temperature=None,
    max_tokens: int = 16000,
    sampler=None,
    repair_attempts: int = 1,
) -> dict:
    user = json.dumps(payload, ensure_ascii=False)
    provider_errored = False
    last_provider_error = None

    try:
        raw = chat_complete(
            role,
            system,
            user,
            temperature=temperature,
            max_tokens=max_tokens,
            sampler=sampler,
            candidate_offset=0,
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

        try:
            previous_raw = chat_complete(
                role,
                _REPAIR_SYSTEM,
                json.dumps(
                    repair_payload,
                    ensure_ascii=False,
                ),
                temperature=0.0,
                max_tokens=max_tokens,
                candidate_offset=0,
            )
        except Aborted:
            raise
        except LLMError as exc:
            last_provider_error = exc
            break  # provider now failing; move on to fallback candidates

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

        try:
            fallback_raw = chat_complete(
                role,
                system + "\n\n" + _REPAIR_SYSTEM,
                json.dumps(
                    fallback_payload,
                    ensure_ascii=False,
                ),
                temperature=0.0,
                max_tokens=max_tokens,
                sampler=sampler,
                candidate_offset=candidate_offset,
            )
        except Aborted:
            raise
        except LLMError as exc:
            last_provider_error = exc
            continue  # this fallback provider errored; try the next candidate

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

    if last_provider_error is not None:
        raise RuntimeError(
            f"{step_key}: all providers failed "
            f"(last provider error: {last_provider_error}); "
            f"validation: {'; '.join(report.errors[:6])}"
        )
    raise RuntimeError(
        f"{step_key} failed JSON validation: "
        + "; ".join(report.errors[:12])
    )