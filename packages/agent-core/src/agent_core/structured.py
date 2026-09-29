"""
Structured-output contract.

Pipeline (fixed order):
  1. Decode whole JSON first; optional fence or explicit best-effort grammar
  2. Parse each; keep those that are objects and schema-valid
  3. Accept only if exactly one schema-valid candidate (uniqueness)
  4. Identity stamping from invocation context (never from model claims)
  5. Parse-path recording
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from agent_core.types import ParsePath

# Reserved identity keys: always stripped from model data before stamping.
RESERVED_IDENTITY_KEYS = frozenset(
    {
        "agent_id",
        "session_id",
        "invocation_id",
        "parent_invocation_id",
        "run_id",
        "project_id",
    }
)


@dataclass(frozen=True)
class ParseDiagnostics:
    """Bounded metadata: no response values, keys, or schema messages."""

    candidate_count: int = 0
    schema_valid_count: int = 0
    validation_failure_count: int = 0
    validation_failures: tuple[str, ...] = ()
    reason: str = "unknown"


class StructuredOutputError(Exception):
    """Typed parser failure with content-safe diagnostic metadata."""

    def __init__(self, message: str, parse_path: ParsePath = ParsePath.FAILED,
                 *, diagnostics: ParseDiagnostics | None = None):
        super().__init__(message)
        self.parse_path = parse_path
        self.diagnostics = diagnostics or ParseDiagnostics()


@dataclass
class ParseResult:
    """Successful structured parse; raw_text remains subject to capture policy."""

    data: Mapping[str, Any]
    parse_path: ParsePath
    raw_text: str
    diagnostics: ParseDiagnostics = field(default_factory=ParseDiagnostics)


# ---------------------------------------------------------------------------
# Schema validation via jsonschema (Draft 2020-12)
# ---------------------------------------------------------------------------

def _reject_non_finite(obj: Any, path: str = "$") -> None:
    """Reject NaN / ±Inf that can appear after non-strict decoding paths."""
    if isinstance(obj, float) and not math.isfinite(obj):
        raise StructuredOutputError(
            f"{path}: non-finite number {obj!r} is not allowed",
            ParsePath.FAILED,
        )
    if isinstance(obj, dict):
        for k, v in obj.items():
            _reject_non_finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _reject_non_finite(v, f"{path}[{i}]")


def _make_validator(schema: Mapping[str, Any]) -> Draft202012Validator:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        raise StructuredOutputError(
            f"invalid schema: {e.message}",
            ParsePath.FAILED,
        ) from e
    return Draft202012Validator(schema)


def _validate(instance: Any, schema: Mapping[str, Any]) -> None:
    _reject_non_finite(instance)
    validator = _make_validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        path = "$"
        if e.absolute_path:
            path = "$." + ".".join(str(p) for p in e.absolute_path)
        raise StructuredOutputError(
            f"{path}: {e.message}",
            ParsePath.FAILED,
        )


# ---------------------------------------------------------------------------
# Candidate extraction (direct + salvage grammar)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)


def _fail(reason: str, *, count: int = 0) -> None:
    raise StructuredOutputError(reason, diagnostics=ParseDiagnostics(
        candidate_count=count, reason=reason))


def _try_json(text: str) -> tuple[bool, Any]:
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("duplicate_key")
            result[key] = value
        return result

    def reject_constant(_):
        _fail("non_finite")

    try:
        return True, json.loads(text, object_pairs_hook=unique_pairs,
                               parse_constant=reject_constant)
    except json.JSONDecodeError:
        return False, None
    except (RecursionError, ValueError):
        _fail("decoder_limit")


def _check_depth(text: str, limit: int) -> None:
    depth = 0
    in_string = escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                _fail("depth_limit")
        elif ch in "]}":
            depth = max(0, depth - 1)


def _extract_all_object_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of every top-level balanced {...} (end exclusive)."""
    results: list[tuple[int, int]] = []
    i = 0
    while i < len(text):
        start = text.find("{", i)
        if start < 0:
            break
        depth = 0
        in_string = False
        escape = False
        end = None
        for j, ch in enumerate(text[start:], start=start):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        if end is not None:
            results.append((start, end))
            i = end
        else:
            break
    return results


@dataclass(frozen=True)
class _Candidate:
    text: str
    path: ParsePath
    data: Any
    span: tuple[int, int]


def _collect_candidates(raw_text: str, *, allow_salvage: bool,
                        best_effort: bool, max_candidates: int, max_depth: int) -> list[_Candidate]:
    # Successful whole decoding is authoritative, even if schema-invalid.
    # Never extract a nested object from an invalid whole payload.
    def candidate(start, end, path):
        text = raw_text[start:end]
        start += len(text) - len(text.lstrip())
        end -= len(text) - len(text.rstrip())
        # Each source occurrence has its own string state; prose quotes must
        # never mask nesting inside an extracted candidate.
        _check_depth(raw_text[start:end], max_depth)
        ok, data = _try_json(raw_text[start:end])
        return _Candidate(raw_text[start:end], path, data, (start, end)) if ok else None

    whole = candidate(0, len(raw_text), ParsePath.DIRECT)
    if whole is not None:
        return [whole]
    if not allow_salvage:
        return []
    outer = _FENCE_RE.fullmatch(raw_text.strip())
    if outer:
        offset = len(raw_text) - len(raw_text.lstrip())
        fenced = candidate(offset + outer.start(1), offset + outer.end(1),
                           ParsePath.SALVAGE_FENCE)
        if fenced is not None:
            return [fenced]
    if not best_effort:
        return []

    by_span = {}
    # Enumerated spans, including malformed candidates, share one finite bound.
    spans = [(m.start(1), m.end(1), ParsePath.SALVAGE_FENCE)
             for m in _FENCE_RE.finditer(raw_text)]
    spans += [(a, b, ParsePath.SALVAGE_FIRST_OBJECT)
              for a, b in _extract_all_object_spans(raw_text)]
    if len(spans) > max_candidates:
        _fail("candidate_limit")
    for start, end, path in spans:
        item = candidate(start, end, path)
        if item is not None:
            by_span.setdefault(item.span, item)
    return sorted(by_span.values(), key=lambda item: item.span)


def parse_structured(
    raw_text: str,
    schema: Mapping[str, Any],
    *,
    allow_salvage: bool = False,
    best_effort: bool = False,
    max_input_bytes: int = 65536,
    max_depth: int = 64,
    max_candidates: int = 64,
) -> ParseResult:
    """Object-only whole parse; optional outer fence; explicit best-effort scan.

    Duplicate keys, non-finite numbers and resource breaches fail closed.
    Diagnostics count decoded source occurrences (including non-objects).
    Failure codes are bounded metadata; raw response capture is caller-owned.
    """
    if not isinstance(raw_text, str):
        _fail("invalid_input_type")
    for limit in (max_input_bytes, max_depth, max_candidates):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            _fail("invalid_limit")
    if not isinstance(allow_salvage, bool) or not isinstance(best_effort, bool):
        _fail("invalid_mode")
    if best_effort and not allow_salvage:
        _fail("invalid_mode")
    try:
        size = len(raw_text.encode("utf-8"))
    except UnicodeEncodeError:
        _fail("invalid_unicode")
    if size > max_input_bytes:
        _fail("byte_limit")
    _check_depth(raw_text, max_depth)
    try:
        validator = _make_validator(schema)
    except (StructuredOutputError, RecursionError):
        _fail("invalid_schema")
    candidates = _collect_candidates(raw_text, allow_salvage=allow_salvage,
                                     best_effort=best_effort, max_candidates=max_candidates, max_depth=max_depth)
    valid = []
    failures = []
    for cand in candidates:
        if not isinstance(cand.data, dict):
            failures.append("top_level_type")
            continue
        try:
            # _reject_non_finite also catches overflow such as 1e999.
            _reject_non_finite(cand.data)
            error = next(validator.iter_errors(cand.data), None)
        except (StructuredOutputError, RecursionError):
            failures.append("validation_limit_or_non_finite")
            continue
        if error is not None:
            failures.append("schema_invalid")
        else:
            valid.append(cand)
    reason = ("accepted" if len(valid) == 1 else "ambiguous" if len(valid) > 1
              else "schema_invalid" if candidates else "no_json")
    diagnostics = ParseDiagnostics(len(candidates), len(valid), len(failures),
                                   tuple(failures[:16]), reason)
    if len(valid) != 1:
        raise StructuredOutputError(reason, diagnostics=diagnostics)
    chosen = valid[0]
    return ParseResult(chosen.data, chosen.path, raw_text, diagnostics)


def stamp_identity(
    data: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    identity_keys: Sequence[str] = (
        "agent_id",
        "session_id",
        "invocation_id",
        "parent_invocation_id",
        "run_id",
        "project_id",
    ),
) -> dict[str, Any]:
    """
    Stamp identity fields from invocation context onto the parsed object.

    Reserved identity keys are always removed from model data first, then
    trusted context values are written. Model claims never survive.
    """
    out: dict[str, Any] = {
        k: v for k, v in data.items() if k not in RESERVED_IDENTITY_KEYS
    }
    for key in identity_keys:
        if key in context:
            out[key] = context[key]
        elif key in RESERVED_IDENTITY_KEYS:
            # Explicit absence: do not leave a model value; key omitted
            out.pop(key, None)
    return out
