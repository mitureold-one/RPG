"""Testes de contrato e validação para o kernel/schema.py."""

from __future__ import annotations

import unittest

from kernel.errors import SchemaError
from kernel.schema import is_valid_schema, validate_schema


class KernelSchemaTests(unittest.TestCase):
    def test_primitive_types_validation(self) -> None:
        # String
        validate_schema("texto", {"type": "string"})
        with self.assertRaises(SchemaError):
            validate_schema(123, {"type": "string"})

        # Integer vs Boolean (in Python bool subclasses int, must distinguish)
        validate_schema(42, {"type": "integer"})
        with self.assertRaises(SchemaError):
            validate_schema(True, {"type": "integer"})
        with self.assertRaises(SchemaError):
            validate_schema(3.14, {"type": "integer"})

        # Number
        validate_schema(42, {"type": "number"})
        validate_schema(3.14, {"type": "number"})
        with self.assertRaises(SchemaError):
            validate_schema(True, {"type": "number"})
        with self.assertRaises(SchemaError):
            validate_schema("42", {"type": "number"})

        # Boolean
        validate_schema(True, {"type": "boolean"})
        validate_schema(False, {"type": "boolean"})
        with self.assertRaises(SchemaError):
            validate_schema(1, {"type": "boolean"})

        # Null
        validate_schema(None, {"type": "null"})
        with self.assertRaises(SchemaError):
            validate_schema(0, {"type": "null"})

    def test_enum_validation(self) -> None:
        schema = {"enum": ["active", "paused", "completed"]}
        validate_schema("active", schema)
        self.assertTrue(is_valid_schema("completed", schema))
        self.assertFalse(is_valid_schema("unknown", schema))

        with self.assertRaises(SchemaError):
            validate_schema("deleted", schema)

    def test_numeric_bounds(self) -> None:
        schema = {"type": "integer", "minimum": 1, "maximum": 10}
        validate_schema(1, schema)
        validate_schema(10, schema)
        validate_schema(5, schema)

        with self.assertRaises(SchemaError):
            validate_schema(0, schema)
        with self.assertRaises(SchemaError):
            validate_schema(11, schema)

    def test_string_length_and_pattern(self) -> None:
        schema = {
            "type": "string",
            "minLength": 3,
            "maxLength": 10,
            "pattern": r"^[a-z]+$",
        }
        validate_schema("abc", schema)
        validate_schema("abcdef", schema)

        with self.assertRaises(SchemaError):
            validate_schema("ab", schema)  # too short
        with self.assertRaises(SchemaError):
            validate_schema("abcdefghijk", schema)  # too long
        with self.assertRaises(SchemaError):
            validate_schema("abc123", schema)  # regex mismatch

    def test_object_required_and_properties(self) -> None:
        schema = {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        }

        valid_obj = {"id": 1, "name": "Item A", "tags": ["tag1", "tag2"]}
        validate_schema(valid_obj, schema)

        # Missing required
        with self.assertRaises(SchemaError) as ctx:
            validate_schema({"id": 1}, schema)
        self.assertEqual(ctx.exception.code, "SCHEMA_INVALID")
        self.assertIn("missing_property", ctx.exception.details)

        # Wrong property type
        with self.assertRaises(SchemaError):
            validate_schema({"id": "not-an-int", "name": "Item A"}, schema)

        # Disallowed additional property
        with self.assertRaises(SchemaError) as ctx:
            validate_schema({"id": 1, "name": "Item A", "extra": True}, schema)
        self.assertIn("extra", ctx.exception.details.get("property", ""))

    def test_array_items_and_bounds(self) -> None:
        schema = {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {"type": "integer"},
        }
        validate_schema([1, 2], schema)

        with self.assertRaises(SchemaError):
            validate_schema([], schema)  # minItems
        with self.assertRaises(SchemaError):
            validate_schema([1, 2, 3, 4], schema)  # maxItems
        with self.assertRaises(SchemaError):
            validate_schema([1, "bad", 3], schema)  # invalid item type

    def test_invalid_schema_definition(self) -> None:
        with self.assertRaises(SchemaError):
            validate_schema(123, "not-a-mapping")  # type: ignore[arg-type]
        with self.assertRaises(SchemaError):
            validate_schema(123, {"type": "unknown_type"})


if __name__ == "__main__":
    unittest.main()
