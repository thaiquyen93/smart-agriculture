import pytest

from agent_core.schema_lint import assert_schema_ok, lint_schema

VALID_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["playbook", "zone", "urgency"],
    "properties": {
        "playbook": {
            "type": "string",
            "enum": ["PLAN_IRRIGATION", "INSPECT_SESSION", "DEVICE_ISSUE", "REPORT", "ASK_DATA"],
            "description": "Loại yêu cầu đã phân loại",
        },
        "zone": {"type": "string", "enum": ["ZONE_A"], "description": "Khu vực"},
        "urgency": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"], "description": "Mức độ khẩn"},
    },
}


def test_valid_schema_has_no_violations():
    assert lint_schema(VALID_SCHEMA) == []
    assert_schema_ok(VALID_SCHEMA, schema_name="router_output")  # must not raise


def test_ref_is_forbidden():
    schema = {**VALID_SCHEMA, "$ref": "#/$defs/Foo"}
    violations = lint_schema(schema)
    assert any("$ref" in v for v in violations)


def test_any_of_is_forbidden():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value"],
        "properties": {"value": {"anyOf": [{"type": "string"}, {"type": "number"}]}},
    }
    violations = lint_schema(schema)
    assert any("anyOf" in v for v in violations)


def test_type_union_is_forbidden():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value"],
        "properties": {"value": {"type": ["string", "null"]}},
    }
    violations = lint_schema(schema)
    assert any("type union" in v.lower() for v in violations)


def test_missing_additional_properties_false_is_forbidden():
    schema = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "string"}},
    }
    violations = lint_schema(schema)
    assert any("additionalProperties" in v for v in violations)


def test_property_missing_from_required_is_forbidden():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    violations = lint_schema(schema)
    assert any("missing from 'required'" in v for v in violations)


def test_deep_nesting_is_forbidden():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["level1"],
        "properties": {
            "level1": {
                "type": "object",
                "additionalProperties": False,
                "required": ["level2"],
                "properties": {
                    "level2": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["value"],
                        "properties": {"value": {"type": "string"}},
                    }
                },
            }
        },
    }
    violations = lint_schema(schema)
    assert any("nesting exceeds" in v for v in violations)


def test_format_keyword_is_forbidden():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["start_time_iso"],
        "properties": {"start_time_iso": {"type": "string", "format": "date-time"}},
    }
    violations = lint_schema(schema)
    assert any("format" in v for v in violations)


def test_tuple_typed_array_is_forbidden():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["pair"],
        "properties": {"pair": {"type": "array", "items": [{"type": "string"}, {"type": "number"}]}},
    }
    violations = lint_schema(schema)
    assert any("tuple-typed" in v for v in violations)


def test_valid_array_of_strings_has_no_violations():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["evidence_refs"],
        "properties": {
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "description": "Evidence ID"},
                "description": "Danh sách evidence_id",
            }
        },
    }
    assert lint_schema(schema) == []


def test_assert_schema_ok_raises_on_violation():
    schema = {**VALID_SCHEMA, "oneOf": []}
    with pytest.raises(ValueError):
        assert_schema_ok(schema, schema_name="bad_schema")
