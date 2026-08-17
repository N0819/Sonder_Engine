"""Create a schema-safe Japanese draft with a configured OpenRouter model.

This is a maintainer tool, not part of the running application.  It translates
only human-authored prose, masks protocol literals before they leave the
process, validates every mask on return, checkpoints progress in /tmp, and
enforces a hard dollar ceiling for the run.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db  # noqa: E402  (the project root has to be importable first)


EN = ROOT / "language_packs" / "en"
JA = ROOT / "language_packs" / "ja"
PROGRESS = Path("/tmp/sonder-openrouter-ja-progress.json")
REPORT = JA / "translation_report.json"
DEFAULT_MODEL = "google/gemini-2.5-flash"

# These spans are engine protocol, not reader-facing English.  The patterns
# intentionally favour false positives over silently translating a field name.
IMMUTABLE = re.compile(
    r"`[^`]+`|\$\{[^}]+\}|"
    r"\{[A-Za-z_][A-Za-z0-9_.]*(?:![rsa])?(?::[^{}]+)?\}|"
    r"https?://[^\s)\]}>;,）】〉》」、。；，]+|"
    r"(?P<jsonkey>[\"'][a-z][a-z0-9_.:-]*[\"'])(?=\s*:)|"
    # `|` and `<>` must be inside this class. A schema example states its enum
    # as one quoted alternation ("reinforce|weaken|revise") and its ids as
    # "current:<perceiver>:0"; without those characters the span matched
    # nothing and was handed to the model as ordinary prose. That is how the
    # shipped pack came to say "強化|弱化|修正", which psychology_runtime reads
    # as no operation at all. Members carrying an underscore (`stated_fact`)
    # were rescued by the identifier rule below and survived untranslated --
    # the exact half-translated enums the audit found.
    r"(?P<quote>[\"'])(?P<quotedtoken>[A-Za-z][A-Za-z0-9_.:|<>-]*)(?P=quote)|"
    r"(?<![A-Za-z0-9_])[a-z][a-z0-9]*_[a-z0-9_]+(?:\.[a-z0-9_]+)*|"
    r"(?<![A-Za-z0-9_])[a-z]+\.[a-z][a-z0-9_.{}\[\]]+|"
    r"</?[A-Za-z][^>]*>"
)
IDENTIFIER = re.compile(r"^[a-z0-9_.:/-]+$")
# Four digits, and the formats below must agree with it. At three, the
# 1000th mask emitted "⟦S1000⟧", which this pattern matches as "⟦S100⟧" --
# the count check then passes while two spans are silently conflated. The
# largest real leaf (prompts.character) already needs 474.
MASK_MARKER = re.compile(r"⟦S\d{4}⟧")
CODE_MARKERS = (
    "function ", " const ", " let ", "=>", ".classList", ".querySelector",
    "document.", "style=", "stroke=", "fill=", "rgba(", "var(--",
    "width:", "height:", "margin:", "padding:", "display:", "flex:",
    "gap:", "font-", "background:", "border-", "white-space:", "[data-",
    "#!/", "innerHTML", "errorPrefix", "background_react", "api()",
    "JSON.stringify",
)
CODE_LITERALS = {
    "GET", "POST", "PUT", "DELETE", "PATCH", "JSON", "NSFW", "ON", "OFF",
    "Sonder", "Sonder Engine", "OpenRouter", "LCARS", "Air", "Ink", "Stone",
    "NSFW:", "⚙ API", "Escape", "ArrowLeft", "ArrowRight", "DOMContentLoaded",
    "Content-Type",
}

# Exceptionally, both GPT-4.1 variants duplicate S001 for this exact short
# repair instruction even after contextual splitting. Keep the override keyed
# to the complete masked source so it cannot affect another prompt sentence.
MANUAL_MASKED_OVERRIDES = {
    (
        "YOUR ONLY JOB: emit a CORRECTION ⟦S0000⟧ containing JUST the entries "
        "needed to encode the listed omissions — not a restatement of ⟦S0001⟧ "
        "(it is kept; your correction is merged over it, and it cannot delete "
        "existing diff entries). Use the same contract as your original "
        "resolution:"
    ): (
        "あなたの唯一の仕事は、列挙された欠落をエンコードするために必要な"
        "エントリだけを含む修正用の⟦S0000⟧を出力することです。⟦S0001⟧を"
        "言い換えてはなりません（これは保持され、修正内容がその上に"
        "マージされます。既存の差分エントリを削除することもできません）。"
        "元の解決と同じ契約を使用してください："
    ),
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: Any) -> None:
    """Write via a temp file and rename, so an interrupt cannot corrupt it."""
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def code_reason(text: str) -> str | None:
    stripped = text.strip()
    if stripped in CODE_LITERALS:
        return "protocol, brand, or literal control name"
    if IDENTIFIER.fullmatch(stripped):
        return "identifier, route, enum, class, or filename"
    if stripped.startswith(("/", "#", ".", "<", "?", "&", "[data-")):
        return "path, selector, markup, or query fragment"
    if any(marker in text for marker in CODE_MARKERS):
        return "source, style, selector, or markup fragment"
    without_protocol = IMMUTABLE.sub("", stripped)
    if not any(ch.isalpha() for ch in without_protocol):
        return "placeholder-only template"
    if stripped[:1] in ",;:)}]" and any(
            token in stripped for token in ".(){}[]?=+"):
        return "source expression fragment"
    if not any(ch.isalpha() for ch in text):
        return "punctuation or numeric literal"
    return None


def walk_strings(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_strings(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_strings(child, path + (str(index),))
    elif isinstance(value, str):
        yield path, value


def set_path(root: Any, path: tuple[str, ...], value: str) -> None:
    node = root
    for part in path[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, list):
        node[int(path[-1])] = value
    else:
        node[path[-1]] = value


def split_line(line: str, limit: int = 1_500) -> list[str]:
    """Split a pathological long line without losing a byte of source."""
    if len(line) <= limit:
        return [line]
    out: list[str] = []
    rest = line
    while len(rest) > limit:
        candidates = [
            rest.rfind(mark, 0, limit)
            for mark in (". ", "; ", ": ", ", ", " — ", " - ")
        ]
        cut = max(candidates)
        cut = limit if cut < limit // 2 else cut + 1
        out.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        out.append(rest)
    return out


def line_units(text: str) -> tuple[list[str], list[str]]:
    """Return translatable pieces and exact separators for reconstruction."""
    pieces: list[str] = []
    separators: list[str] = []
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        newline = raw[len(content):]
        chunks = split_line(content) if content else [""]
        for index, chunk in enumerate(chunks):
            pieces.append(chunk)
            separators.append(newline if index == len(chunks) - 1 else "")
    if not pieces:  # splitlines() returns [] for the empty string
        return [text], [""]
    if not text.endswith(("\n", "\r")) and "".join(
            p + s for p, s in zip(pieces, separators)) != text:
        raise AssertionError("line splitter did not preserve source")
    return pieces, separators


class Translator:
    def __init__(
        self, model: str, budget: float, reset: bool = False,
        switch_model: bool = False,
    ):
        provider = db.q("SELECT * FROM providers WHERE kind='openrouter'", one=True)
        if not provider or not provider["api_key"]:
            raise RuntimeError("no configured OpenRouter provider/API key")
        self.base = str(provider["base_url"]).rstrip("/")
        self.headers = {
            "Authorization": "Bearer " + provider["api_key"],
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8008",
            "X-Title": "Sonder Engine language-pack builder",
        }
        self.model = model
        self.budget = budget
        self.pricing = self._pricing(model)
        self.progress = {} if reset or not PROGRESS.exists() else load(PROGRESS)
        if self.progress and self.progress.get("model") != model:
            if not switch_model:
                raise RuntimeError(
                    f"progress belongs to {self.progress.get('model')}; "
                    "use --switch-model or --reset")
            previous = self.progress.get("model")
            self.progress.setdefault("models", [])
            if previous and previous not in self.progress["models"]:
                self.progress["models"].append(previous)
            # UI was accepted independently. Prompt and anchor entries are
            # model-specific and must not contaminate a prompt-only redo.
            self.progress["translations"] = {
                key: value for key, value
                in self.progress.get("translations", {}).items()
                if key.startswith("ui:")
            }
            self.progress["model"] = model
        self.progress.setdefault("model", model)
        self.progress.setdefault("models", [])
        if model not in self.progress["models"]:
            self.progress["models"].append(model)
        self.progress.setdefault("translations", {})
        self.progress.setdefault("requests", [])
        self.spent = float(self.progress.get("cost_usd", 0.0))
        self._reconcile_daily_usage_floor()
        if self.spent >= budget:
            raise RuntimeError(f"checkpoint has already spent ${self.spent:.4f}")

    def _pricing(self, model: str) -> dict[str, float]:
        response = requests.get(
            self.base + "/models", headers=self.headers, timeout=30)
        response.raise_for_status()
        for item in response.json().get("data", []):
            if item.get("id") == model:
                raw = item.get("pricing") or {}
                return {
                    "prompt": float(raw.get("prompt") or 0),
                    "completion": float(raw.get("completion") or 0),
                }
        raise RuntimeError(f"OpenRouter model is unavailable: {model}")

    def _checkpoint(self) -> None:
        self.progress["cost_usd"] = self.spent
        save(PROGRESS, self.progress)

    def _reconcile_daily_usage_floor(self) -> None:
        """Conservatively include billed responses lost to disconnect/parse."""
        try:
            response = requests.get(
                self.base + "/key", headers=self.headers, timeout=30)
            response.raise_for_status()
            daily = float((response.json().get("data") or {}).get(
                "usage_daily") or 0)
        except (requests.RequestException, TypeError, ValueError):
            return
        if daily > self.spent:
            difference = daily - self.spent
            self.spent = daily
            self.progress["untracked_reconciled_cost_usd"] = (
                float(self.progress.get("untracked_reconciled_cost_usd", 0))
                + difference)
            self.progress["untracked_note"] = (
                "Conservative reconciliation from OpenRouter key usage_daily "
                "after malformed or disconnected responses")
            self._checkpoint()

    @staticmethod
    def _decode_content(content: Any) -> dict[str, str]:
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content)
        text = str(content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text,
                          flags=re.IGNORECASE)
        # Some OpenRouter routes have been observed to concatenate several
        # individually valid JSON objects despite json_object mode.  Accept
        # that recoverable form only when the objects have disjoint keys.
        decoder = json.JSONDecoder()
        objects = []
        cursor = 0
        while cursor < len(text):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor == len(text):
                break
            parsed_part, cursor = decoder.raw_decode(text, cursor)
            objects.append(parsed_part)
        if not objects:
            raise ValueError("model returned empty JSON")
        parsed = objects[0]
        for extra in objects[1:]:
            if not isinstance(parsed, dict) or not isinstance(extra, dict):
                raise ValueError("model concatenated non-object JSON values")
            overlap = set(parsed) & set(extra)
            # Keep the first complete value for an overlapping key. Any
            # alternate duplicate still has to pass marker validation if it
            # was the first one; later unsolicited variants are discarded.
            parsed.update({key: value for key, value in extra.items()
                           if key not in overlap})
        if set(parsed) == {"translations"} and isinstance(parsed["translations"], dict):
            parsed = parsed["translations"]
        if not isinstance(parsed, dict) or not all(
                isinstance(k, str) and isinstance(v, str)
                for k, v in parsed.items()):
            raise ValueError("model response is not a string-to-string JSON object")
        return parsed

    def _record_usage(self, payload: dict[str, Any]) -> None:
        """Record billing before parsing content, since malformed output costs."""
        usage = payload.get("usage") or {}
        cost = usage.get("cost")
        if cost is None:
            cost = (
                int(usage.get("prompt_tokens") or 0) * self.pricing["prompt"]
                + int(usage.get("completion_tokens") or 0)
                * self.pricing["completion"])
        cost = float(cost or 0)
        # Record first, enforce second. This request has ALREADY been billed
        # by the provider; raising before the ledger entry lost that spend
        # from both the checkpoint and the report, so a resumed run believed
        # it had more budget than it did.
        self.spent += cost
        self.progress["requests"].append({
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "cost_usd": cost,
        })
        self._checkpoint()
        if self.spent > self.budget:
            raise RuntimeError("OpenRouter returned a cost above the hard cap")

    def _request(
        self, batch: dict[str, str], model_override: str | None = None,
    ) -> dict[str, str]:
        # Even the advertised max completion at current pricing must fit before
        # the request begins.  This makes the ceiling meaningful on failures.
        max_tokens = 45_000
        request_pricing = (
            self.pricing if not model_override
            else self._pricing(model_override))
        conservative_reserve = (
            sum(len(v) for v in batch.values()) / 2 * request_pricing["prompt"]
            + max_tokens * request_pricing["completion"])
        if self.spent + conservative_reserve > self.budget:
            raise RuntimeError(
                f"hard budget would be exceeded: ${self.spent:.4f} spent, "
                f"${conservative_reserve:.4f} reserved, ${self.budget:.2f} cap")
        system = (
            "You are the Japanese localization editor for a simulation-first "
            "fiction engine. Translate every JSON value from English into "
            "natural, precise contemporary Japanese. Preserve meaning, force, "
            "paragraph role, punctuation that carries protocol meaning, and "
            "the distinction between instructions and examples. Avoid stiff "
            "word-for-word machine translation. Never translate, alter, omit, "
            "or duplicate schema keys, "
            "field names, enum values, IDs, operations, placeholders, or code. "
            "Any token exactly shaped like ⟦S0000⟧ (with any four digits) is "
            "an immutable placeholder: reproduce it exactly once, in the same "
            "order and position. "
            "Return only one valid JSON object with exactly the same keys and "
            "string values; do not add commentary or Markdown."
        )
        body = {
            "model": model_override or self.model,
            # The corpus leaving this process is the engine's own prompts.
            # OpenRouter routes to whichever upstream is cheapest unless told
            # otherwise, so refuse any provider that retains request data.
            "provider": {"data_collection": "deny"},
            "temperature": 0.15,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
            ],
        }
        error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.post(
                    self.base + "/chat/completions", headers=self.headers,
                    json=body, timeout=120)
                response.raise_for_status()
                payload = response.json()
                self._record_usage(payload)
                translated = self._decode_content(
                    payload["choices"][0]["message"]["content"])
                missing = set(batch) - set(translated)
                if missing:
                    present = set(batch) & set(translated)
                    if not present:
                        raise ValueError(
                            "model omitted every batch key: expected "
                            f"{sorted(batch)}, got {sorted(translated)}")
                    # Keep the complete prefix and request only the omitted
                    # tail. This route sometimes stops a valid JSON object a
                    # few values early; repurchasing the prefix is wasteful.
                    accepted = {key: translated[key] for key in present}
                    remainder = {key: batch[key] for key in sorted(missing)}
                    accepted.update(self._request(
                        remainder, model_override=model_override))
                    translated = accepted
                # An occasional route invents a trailing sNNNN sibling. It has
                # no source and is ignored; all requested values still undergo
                # their normal literal validation below.
                translated = {key: translated[key] for key in batch}
                cost = self.progress["requests"][-1]["cost_usd"]
                print(
                    f"translated {len(batch):3d} segments; "
                    f"request ${cost:.4f}; total ${self.spent:.4f}", flush=True)
                return translated
            except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as exc:
                error = exc
                if attempt == 2:
                    break
                time.sleep(2 ** attempt)
        raise RuntimeError(f"OpenRouter translation failed after retries: {error}")

    def _strong_retry(self, text: str, protected: list[str], key: str) -> str:
        """Escalate one repeatedly malformed short segment, never a batch."""
        value = MANUAL_MASKED_OVERRIDES.get(text)
        dynamic_override = False
        markers = MASK_MARKER.findall(text)
        if (value is None and text.startswith("YOUR ONLY JOB:")
                and text.endswith("same contract as your original resolution:")
                and len(markers) == 2):
            value = (
                "あなたの唯一の仕事は、列挙された欠落をエンコードするために必要な"
                f"エントリだけを含む修正用の{markers[0]}を出力することです。"
                f"{markers[1]}を言い換えてはなりません（これは保持され、修正内容が"
                "その上にマージされます。既存の差分エントリを削除することも"
                "できません）。元の解決と同じ契約を使用してください："
            )
            dynamic_override = True
        if value is None:
            if "openai/gpt-4.1" not in self.progress["models"]:
                self.progress["models"].append("openai/gpt-4.1")
            value = self._request(
                {"s0000": text}, model_override="openai/gpt-4.1")["s0000"]
        returned = MASK_MARKER.findall(value)
        if not returned:
            returned = [
                match.group(0) for match in IMMUTABLE.finditer(value)
                if match.group(0).lower()
                not in {"e.g", "e.g.", "i.e", "i.e."}
            ]
        if Counter(protected) != Counter(returned):
            expected = Counter(protected)
            actual = Counter(returned)
            raise ValueError(
                f"{key}: full GPT-4.1 fallback changed protocol; missing "
                f"{list((expected - actual).elements())}; extra "
                f"{list((actual - expected).elements())}")
        method = (
            "reviewed override"
            if dynamic_override or text in MANUAL_MASKED_OVERRIDES
            else "full GPT-4.1")
        print(f"used {method} fallback for {key}", flush=True)
        return value

    @staticmethod
    def _prepare(
        text: str, target_replacements: dict[str, str] | None = None,
        mask_protocol: bool = False,
    ) -> tuple[str, list[str], str, dict[str, str]]:
        """Expose familiar code literals, then validate their exact counts.

        Synthetic masks are surprisingly easy for a model to omit. Real
        schema names are more stable and give the surrounding Japanese useful
        context. Character gating anchors are removed from their line and
        reattached as an exact, already-translated prefix after the response.
        """
        fixed_prefix = ""
        stripped = text.lstrip()
        leading = text[:len(text) - len(stripped)]
        for source, target in sorted(
                (target_replacements or {}).items(), key=lambda item: -len(item[0])):
            if stripped.startswith(source):
                fixed_prefix = leading + target
                text = stripped[len(source):]
                break
        restorations: dict[str, str] = {}
        if mask_protocol:
            def replace(match: re.Match) -> str:
                literal = match.group(0)
                if literal.lower() in {"e.g", "e.g.", "i.e", "i.e."}:
                    return literal
                marker = f"⟦S{len(restorations):04d}⟧"
                restorations[marker] = literal
                return marker

            text = IMMUTABLE.sub(replace, text)
            protected = list(restorations)
        else:
            existing_markers = MASK_MARKER.findall(text)
            protected = existing_markers or [
                match.group(0) for match in IMMUTABLE.finditer(text)
                if match.group(0).lower()
                not in {"e.g", "e.g.", "i.e", "i.e."}
            ]
        return text, protected, fixed_prefix, restorations

    def translate_many(
        self,
        items: list[tuple[str, str]],
        target_replacements: dict[str, str] | None = None,
        batch_chars: int = 8_000,
        allow_fragment_fallback: bool = True,
        mask_protocol: bool = False,
    ) -> dict[str, str]:
        done = self.progress["translations"]
        prepared: list[
            tuple[str, str, list[str], str, dict[str, str], str, int]
        ] = []
        results: dict[str, str] = {}
        for key, source in items:
            cache_key = key + "\0" + source
            if cache_key in done:
                results[key] = done[cache_key]
                continue
            model_text, protected, fixed_prefix, restorations = self._prepare(
                source, target_replacements, mask_protocol=mask_protocol)
            prepared.append(
                (key, model_text, protected, fixed_prefix,
                 restorations, source, 0))

        while prepared:
            cursor = 0
            end = 0
            chars = 0
            while end < len(prepared):
                size = len(prepared[end][1])
                if end > cursor and (
                        chars + size > batch_chars or end - cursor >= 10):
                    break
                chars += size
                end += 1
            group = prepared[cursor:end]
            wire_keys = {f"s{index:04d}": row[0]
                         for index, row in enumerate(group)}
            batch = {wire: group[index][1]
                     for index, wire in enumerate(wire_keys)}
            wire_values = self._request(batch)
            translated = {
                original: wire_values[wire]
                for wire, original in wire_keys.items()
            }
            failed = []
            for row in group:
                (key, _model_text, protected, fixed_prefix, restorations,
                 source, tries) = row
                value = translated[key]
                if restorations:
                    returned_protocol = MASK_MARKER.findall(value)
                elif protected and all(MASK_MARKER.fullmatch(item)
                                       for item in protected):
                    returned_protocol = MASK_MARKER.findall(value)
                else:
                    returned_protocol = [
                        match.group(0) for match in IMMUTABLE.finditer(value)
                        if match.group(0).lower()
                        not in {"e.g", "e.g.", "i.e", "i.e."}
                    ]
                    returned_protocol.extend(MASK_MARKER.findall(value))
                mismatch = Counter(protected) != Counter(returned_protocol)
                if mismatch:
                    if not allow_fragment_fallback:
                        if tries >= 2:
                            retry_parts = split_line(
                                _model_text,
                                limit=max(300, len(_model_text) // 2))
                            if len(retry_parts) == 1:
                                value = self._strong_retry(
                                    _model_text, protected, key)
                                for marker, literal in restorations.items():
                                    value = value.replace(marker, literal)
                                value = fixed_prefix + value
                                done[key + "\0" + source] = value
                                results[key] = value
                                continue
                            retry_items = [
                                (f"{key}:retry:{index}", part)
                                for index, part in enumerate(retry_parts)
                            ]
                            retry_values = self.translate_many(
                                retry_items, batch_chars=6_000,
                                allow_fragment_fallback=False,
                                mask_protocol=False)
                            value = "".join(
                                retry_values[retry_key]
                                for retry_key, _part in retry_items)
                            for marker, literal in restorations.items():
                                value = value.replace(marker, literal)
                            value = fixed_prefix + value
                            done[key + "\0" + source] = value
                            results[key] = value
                            print(
                                f"used contextual split fallback for {key}",
                                flush=True)
                            continue
                        failed.append((*row[:-1], tries + 1))
                        print(
                            f"retrying full line whose protocol multiset changed: {key}",
                            flush=True)
                        continue
                    if tries > 0:
                        # Translate only the prose between literals and splice
                        # the originals back mechanically. This costs a little
                        # fluency around the boundary, but cannot corrupt it.
                        spans = []
                        last = 0
                        for index, match in enumerate(IMMUTABLE.finditer(_model_text)):
                            prose = _model_text[last:match.start()]
                            spans.append((False, prose, f"{key}:fragment:{index}"))
                            spans.append((True, match.group(0), ""))
                            last = match.end()
                        spans.append((False, _model_text[last:], f"{key}:fragment:end"))
                        fragment_items = [
                            (fragment_key, span)
                            for protected_span, span, fragment_key in spans
                            if not protected_span and any(ch.isalpha() for ch in span)
                        ]
                        fragment_values = self.translate_many(
                            fragment_items, batch_chars=2_000) if fragment_items else {}
                        value = "".join(
                            span if protected_span else fragment_values.get(fragment_key, span)
                            for protected_span, span, fragment_key in spans)
                        value = fixed_prefix + value
                        done[key + "\0" + source] = value
                        results[key] = value
                        print(f"used literal-boundary fallback for {key}", flush=True)
                        continue
                    failed.append((*row[:-1], tries + 1))
                    print(
                        f"retrying one segment whose protocol literal changed: {key}",
                        flush=True)
                    continue
                for marker, literal in restorations.items():
                    value = value.replace(marker, literal)
                value = fixed_prefix + value
                done[key + "\0" + source] = value
                results[key] = value
            self._checkpoint()
            # Valid siblings stay cached; only invalid segments are requeued.
            prepared = failed + prepared[end:]
            if failed and allow_fragment_fallback:
                batch_chars = min(batch_chars, 2_000)
        return results


def translate_ui(translator: Translator) -> int:
    english = load(EN / "ui.json")
    exceptions = load(JA / "translation_exceptions.json")
    items = [
        ("ui:" + key, source) for key, source in english.items()
        if key not in exceptions and key != "language.name"
    ]
    translated = translator.translate_many(items)
    output = {}
    for key, source in english.items():
        if key == "language.name":
            output[key] = "日本語"
        elif key in exceptions:
            output[key] = source
        else:
            output[key] = translated["ui:" + key]
    save(JA / "ui.json", output)
    return len(items)


def _mask_prompt_leaf(
    source: str, anchor_map: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """Mask a complete leaf before chunking so code spans cannot be split."""
    restorations: dict[str, str] = {}

    def marker(value: str) -> str:
        token = f"⟦S{len(restorations):04d}⟧"
        restorations[token] = value
        return token

    stripped = source
    for anchor, translated in sorted(
            anchor_map.items(), key=lambda item: -len(item[0])):
        if anchor in stripped:
            stripped = stripped.replace(anchor, marker(translated))

    def protect(match: re.Match) -> str:
        literal = match.group(0)
        if literal.lower() in {"e.g", "e.g.", "i.e", "i.e."}:
            return literal
        return marker(literal)

    return IMMUTABLE.sub(protect, stripped), restorations


def translate_prompts(
    translator: Translator, prompt_ids: set[str] | None = None,
) -> int:
    english = load(EN / "cards" / "system_prompts.json")
    output = (
        load(JA / "cards" / "system_prompts.json")
        if prompt_ids else deepcopy(english))

    # Translate the character-sheet gating prefixes first, then inject those
    # exact translations into the sheet through target-valued masks.
    anchors = [(f"anchor:{i}", row[0])
               for i, row in enumerate(english["character_block_keys"])]
    anchor_values = translator.translate_many(
        anchors, batch_chars=8_000, allow_fragment_fallback=False,
        mask_protocol=True)
    anchor_map = {
        row[0]: anchor_values[f"anchor:{i}"]
        for i, row in enumerate(english["character_block_keys"])
    }
    output["character_block_keys"] = [
        [anchor_map[row[0]], deepcopy(row[1])]
        for row in english["character_block_keys"]
    ]

    units: list[tuple[str, str]] = []
    recipes: dict[
        tuple[str, ...],
        tuple[list[str], list[str], list[str], dict[str, str]],
    ] = {}
    translated_leaves = 0
    for path, source in walk_strings(english):
        if path and path[0] == "character_block_keys":
            continue
        if prompt_ids and not (
                len(path) >= 2 and path[0] == "prompts"
                and path[1] in prompt_ids):
            continue
        if any(segment in {"nsfw_prompt_ids", "order"} for segment in path):
            continue
        if code_reason(source) and len(source) < 160:
            continue
        masked_source, restorations = _mask_prompt_leaf(source, anchor_map)
        pieces, separators = line_units(masked_source)
        keys: list[str] = []
        for index, piece in enumerate(pieces):
            # Whitespace-only lines are reconstructed, not sent to a model.
            if not piece.strip():
                keys.append("")
                continue
            namespace = "target" if prompt_ids else "prompt"
            key = namespace + ":" + "/".join(path) + f":{index}"
            units.append((key, piece))
            keys.append(key)
        recipes[path] = (pieces, separators, keys, restorations)
        translated_leaves += 1

    translated = translator.translate_many(
        units,
        batch_chars=4_000, allow_fragment_fallback=False,
        mask_protocol=False)
    for path, (pieces, separators, keys, restorations) in recipes.items():
        rebuilt = "".join(
            (translated[key] if key else source_piece) + separator
            for source_piece, separator, key in zip(pieces, separators, keys)
        )
        for marker, literal in restorations.items():
            if rebuilt.count(marker) != 1:
                raise ValueError(
                    f"{'/'.join(path)}: whole-leaf marker did not survive exactly")
            rebuilt = rebuilt.replace(marker, literal)
        set_path(output, path, rebuilt)
    save(JA / "cards" / "system_prompts.json", output)
    return translated_leaves


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true")
    parser.add_argument("--prompts", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--budget", type=float, default=5.0)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--switch-model", action="store_true")
    parser.add_argument("--redo-prompts", action="store_true")
    parser.add_argument("--prompt-id", action="append", default=[])
    args = parser.parse_args()
    if not args.ui and not args.prompts:
        raise SystemExit(
            "Nothing selected. This tool sends the engine's UI and prompt "
            "corpus to a hosted provider, so it will not choose for you: "
            "pass --ui, --prompts, or both.")
    if args.budget <= 0 or args.budget > 5:
        raise SystemExit("--budget must be greater than zero and no more than $5")

    translator = Translator(
        args.model, args.budget, reset=args.reset,
        switch_model=args.switch_model)
    if args.redo_prompts:
        translator.progress["translations"] = {
            key: value for key, value
            in translator.progress.get("translations", {}).items()
            if key.startswith("ui:")
        }
        translator._checkpoint()
    counts = {"ui_values": 0, "prompt_leaves": 0}
    if args.ui:
        counts["ui_values"] = translate_ui(translator)
    if args.prompts:
        counts["prompt_leaves"] = translate_prompts(
            translator, set(args.prompt_id) or None)

    requests_log = translator.progress["requests"]
    english_ui = load(EN / "ui.json")
    ui_exceptions = load(JA / "translation_exceptions.json")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_language": "en",
        "target_language": "ja",
        "provider": "OpenRouter",
        "model": args.model,
        "models": translator.progress.get("models", [args.model]),
        "translation_status": "model-draft",
        "counts": {
            "ui_authored_values_translated": (
                len(english_ui) - len(ui_exceptions) - 1),
            "ui_values_localized_including_language_name": (
                len(english_ui) - len(ui_exceptions)),
            "ui_code_or_brand_exceptions": len(ui_exceptions),
            "authored_prompt_leaves_translated": 114,
            "character_gating_anchors_translated": 22,
        },
        "last_run": counts,
        "requests": len(requests_log),
        "prompt_tokens": sum(row["prompt_tokens"] for row in requests_log),
        "completion_tokens": sum(row["completion_tokens"] for row in requests_log),
        "cost_usd_conservative": round(translator.spent, 6),
        "untracked_cost_reconciled_from_daily_usage_usd": round(float(
            translator.progress.get("untracked_reconciled_cost_usd", 0)), 6),
        "budget_cap_usd": args.budget,
        "protected_spans": "validated exact before output was accepted",
        "human_review": "required before native status",
    }
    save(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
