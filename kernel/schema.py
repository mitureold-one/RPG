"""Validação de subconjunto de JSON Schema sem dependências externas.

Suporta types primitivos, objetos com propriedades e obrigatoriedade,
arrays tipados, enums, limites numéricos e de tamanho.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from kernel.errors import SchemaError

_VALID_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def _match_type(data: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(data, Mapping)
    if expected == "array":
        return isinstance(data, (list, tuple))
    if expected == "string":
        return isinstance(data, str)
    if expected == "integer":
        return isinstance(data, int) and not isinstance(data, bool)
    if expected == "number":
        return (isinstance(data, (int, float)) and not isinstance(data, bool))
    if expected == "boolean":
        return isinstance(data, bool)
    if expected == "null":
        return data is None
    return False


def validate_schema(data: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    """Valida ``data`` contra um subconjunto de JSON Schema.

    Lança :class:`SchemaError` com código ``SCHEMA_INVALID`` e detalhes do caminho em caso de falha.
    """
    if not isinstance(schema, Mapping):
        raise SchemaError(
            f"Schema deve ser um Mapping em '{path}'",
            details={"path": path},
        )

    # 1. Type validation
    if "type" in schema:
        expected = schema["type"]
        if isinstance(expected, str):
            allowed = [expected]
        elif isinstance(expected, (list, tuple)):
            allowed = list(expected)
        else:
            raise SchemaError(
                f"'type' no schema deve ser texto ou lista em '{path}'",
                details={"path": path},
            )

        for item in allowed:
            if item not in _VALID_TYPES:
                raise SchemaError(
                    f"Tipo desconhecido '{item}' no schema em '{path}'",
                    details={"path": path, "type": item},
                )

        if not any(_match_type(data, t) for t in allowed):
            expected_name = allowed[0] if len(allowed) == 1 else str(allowed)
            actual_name = "null" if data is None else type(data).__name__
            raise SchemaError(
                f"Tipo inválido em '{path}': esperado {expected_name}, obtido {actual_name}",
                details={"path": path, "expected": expected, "actual": actual_name},
            )

    # 2. Enum validation
    if "enum" in schema:
        enum_values = schema["enum"]
        if not isinstance(enum_values, (list, tuple)):
            raise SchemaError(
                f"'enum' no schema deve ser lista ou tupla em '{path}'",
                details={"path": path},
            )
        if data not in enum_values:
            raise SchemaError(
                f"Valor em '{path}' não está entre os valores permitidos",
                details={"path": path, "allowed": list(enum_values), "actual": data},
            )

    # 3. Numeric bounds
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema:
            min_val = schema["minimum"]
            if data < min_val:
                raise SchemaError(
                    f"Valor em '{path}' ({data}) é menor que o mínimo ({min_val})",
                    details={"path": path, "minimum": min_val, "actual": data},
                )
        if "maximum" in schema:
            max_val = schema["maximum"]
            if data > max_val:
                raise SchemaError(
                    f"Valor em '{path}' ({data}) é maior que o máximo ({max_val})",
                    details={"path": path, "maximum": max_val, "actual": data},
                )

    # 4. String bounds and pattern
    if isinstance(data, str):
        if "minLength" in schema:
            min_len = schema["minLength"]
            if len(data) < min_len:
                raise SchemaError(
                    f"Tamanho de texto em '{path}' ({len(data)}) é menor que o mínimo ({min_len})",
                    details={"path": path, "minLength": min_len, "actual": len(data)},
                )
        if "maxLength" in schema:
            max_len = schema["maxLength"]
            if len(data) > max_len:
                raise SchemaError(
                    f"Tamanho de texto em '{path}' ({len(data)}) é maior que o máximo ({max_len})",
                    details={"path": path, "maxLength": max_len, "actual": len(data)},
                )
        if "pattern" in schema:
            pat = schema["pattern"]
            if not isinstance(pat, str) or not re.search(pat, data):
                raise SchemaError(
                    f"Texto em '{path}' não corresponde ao padrão regex '{pat}'",
                    details={"path": path, "pattern": pat, "actual": data},
                )

    # 5. Object validation
    if isinstance(data, Mapping):
        # Required properties
        if "required" in schema:
            required_keys = schema["required"]
            if not isinstance(required_keys, (list, tuple)):
                raise SchemaError(
                    f"'required' deve ser lista ou tupla em '{path}'",
                    details={"path": path},
                )
            for req in required_keys:
                if req not in data:
                    prop_path = f"{path}.{req}" if path != "$" else f"$.{req}"
                    raise SchemaError(
                        f"Campo obrigatório ausente: '{req}'",
                        details={"path": prop_path, "missing_property": req},
                    )

        properties = schema.get("properties")
        if properties is not None and not isinstance(properties, Mapping):
            raise SchemaError(
                f"'properties' deve ser um Mapping em '{path}'",
                details={"path": path},
            )
        prop_schemas = properties or {}

        # Additional properties
        additional = schema.get("additionalProperties", True)
        if additional is False:
            for key in data:
                if key not in prop_schemas:
                    prop_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                    raise SchemaError(
                        f"Propriedade não permitida: '{key}'",
                        details={"path": prop_path, "property": key},
                    )
        elif isinstance(additional, Mapping):
            for key, val in data.items():
                if key not in prop_schemas:
                    prop_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                    validate_schema(val, additional, prop_path)

        # Validate defined properties
        for key, prop_schema in prop_schemas.items():
            if key in data:
                prop_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                validate_schema(data[key], prop_schema, prop_path)

    # 6. Array validation
    if isinstance(data, (list, tuple)):
        if "minItems" in schema:
            min_items = schema["minItems"]
            if len(data) < min_items:
                raise SchemaError(
                    f"Array em '{path}' possui menos itens ({len(data)}) que o mínimo ({min_items})",
                    details={"path": path, "minItems": min_items, "actual": len(data)},
                )
        if "maxItems" in schema:
            max_items = schema["maxItems"]
            if len(data) > max_items:
                raise SchemaError(
                    f"Array em '{path}' possui mais itens ({len(data)}) que o máximo ({max_items})",
                    details={"path": path, "maxItems": max_items, "actual": len(data)},
                )
        if "items" in schema:
            item_schema = schema["items"]
            for idx, item in enumerate(data):
                item_path = f"{path}[{idx}]"
                validate_schema(item, item_schema, item_path)


def is_valid_schema(data: Any, schema: Mapping[str, Any]) -> bool:
    """Devolve True se ``data`` cumprir ``schema``, False em caso contrário."""
    try:
        validate_schema(data, schema)
        return True
    except SchemaError:
        return False


__all__ = ["is_valid_schema", "validate_schema"]
