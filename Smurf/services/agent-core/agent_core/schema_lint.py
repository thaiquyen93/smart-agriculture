"""Schema "intersection rule" lint — docs/agent-core/03-contracts.md §1.

Any JSON Schema passed to an LLM as `response_format` must be expressible in
BOTH LM Studio's GBNF grammar constraint (llama.cpp) AND Gemini's
`responseSchema` — two different subsets of JSON Schema. This module
enforces that intersection in code, so a schema that only one provider
accepts never silently reaches `structured_output.py`.

Does NOT apply to Kafka event schemas (those are documentation for humans,
see 03-contracts.md §3) — only to schemas fed to an LLM's response_format.
"""
from __future__ import annotations

FORBIDDEN_KEYS = {
    "$ref",
    "$defs",
    "definitions",
    "anyOf",
    "oneOf",
    "allOf",
    "not",
    "patternProperties",
    "additionalItems",
    "if",
    "then",
    "else",
}

ALLOWED_TYPES = {"object", "array", "string", "number", "integer", "boolean"}

# "properties với object phẳng (lồng tối đa 2 tầng)" — 03-contracts.md §1
MAX_OBJECT_NESTING = 2


def lint_schema(schema: dict, *, _depth: int = 1, _path: str = "$") -> list[str]:
    """Return human-readable violations; an empty list means `schema` is
    safe to send to both LM Studio and Gemini as `response_format`."""
    if not isinstance(schema, dict):
        return [f"{_path}: schema node must be an object, got {type(schema).__name__}"]

    violations: list[str] = []

    for key in FORBIDDEN_KEYS:
        if key in schema:
            violations.append(
                f"{_path}: forbidden keyword '{key}' — not in the LM Studio/Gemini schema intersection"
            )

    if "format" in schema:
        violations.append(
            f"{_path}: 'format' is forbidden — express as a plain string with a 'description' instead"
        )

    node_type = schema.get("type")
    if isinstance(node_type, list):
        violations.append(
            f"{_path}: type union {node_type!r} is forbidden — use an enum with a sentinel "
            f"value (e.g. 'NONE'/'UNKNOWN') or a companion boolean field instead"
        )
    elif node_type is not None and node_type not in ALLOWED_TYPES:
        violations.append(f"{_path}: unsupported type '{node_type}'")

    if node_type == "object":
        if _depth > MAX_OBJECT_NESTING:
            violations.append(
                f"{_path}: object nesting exceeds {MAX_OBJECT_NESTING} levels — flatten the schema"
            )

        if schema.get("additionalProperties", None) is not False:
            violations.append(f"{_path}: object must set additionalProperties: false")

        properties = schema.get("properties")
        if not isinstance(properties, dict):
            violations.append(f"{_path}: object must declare 'properties'")
            properties = {}

        required = schema.get("required")
        if not isinstance(required, list):
            violations.append(f"{_path}: object must declare an explicit 'required' list")
        else:
            missing = sorted(set(properties) - set(required))
            if missing:
                violations.append(
                    f"{_path}: fields present in 'properties' but missing from 'required': {missing}"
                )

        for prop_name, prop_schema in properties.items():
            violations.extend(lint_schema(prop_schema, _depth=_depth + 1, _path=f"{_path}.{prop_name}"))

    elif node_type == "array":
        items = schema.get("items")
        if isinstance(items, list):
            violations.append(
                f"{_path}: tuple-typed arrays ('items' as a list) are forbidden — use one 'items' schema"
            )
        elif isinstance(items, dict):
            violations.extend(lint_schema(items, _depth=_depth, _path=f"{_path}[]"))
        else:
            violations.append(f"{_path}: array must declare a single 'items' schema")

    return violations


def assert_schema_ok(schema: dict, *, schema_name: str = "<schema>") -> None:
    """Raise ValueError with every violation listed, or return silently."""
    violations = lint_schema(schema)
    if violations:
        joined = "\n  - ".join(violations)
        raise ValueError(
            f"Schema '{schema_name}' violates the LM Studio/Gemini intersection rule "
            f"(docs/agent-core/03-contracts.md §1):\n  - {joined}"
        )
