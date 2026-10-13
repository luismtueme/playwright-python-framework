"""Generate contracts/models.py from the OpenAPI document.

    uv run python -m utils.generate_api_types
    uv run python -m utils.generate_api_types --check

CI fails when the generated file is stale. OPENAPI_SPEC selects the document,
same as the runtime contract checks.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from config import ROOT, config

TARGET = ROOT / "contracts" / "models.py"


def render_models(spec: dict[str, Any]) -> str:
    schemas: dict[str, Any] = (spec.get("components") or {}).get("schemas") or {}
    chunks = [
        '"""Generated from the OpenAPI contract. Do not edit by hand.',
        "",
        "Regenerate with: uv run python -m utils.generate_api_types",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Literal, NotRequired, TypedDict",
        "",
    ]
    body: list[str] = []
    for name, schema in schemas.items():
        body.extend(_render_schema(name, schema))
        body.append("")
    return _format_python("\n".join(chunks + body).rstrip() + "\n")


def _format_python(source: str) -> str:
    ruff = shutil.which("ruff")
    if ruff is None:
        return source
    completed = subprocess.run(
        [ruff, "format", "--stdin-filename", "contracts/models.py", "-"],
        input=source,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def _render_schema(name: str, schema: dict[str, Any]) -> list[str]:
    if schema.get("type") == "string" and "enum" in schema:
        return [f"{name} = {_literal(schema['enum'])}"]
    if schema.get("type") != "object":
        raise RuntimeError(f"Unsupported schema {name}: {schema.get('type')}")
    nested, fields = _object_body(name, schema)
    return [*nested, f"class {name}(TypedDict):", *fields]


def _object_body(parent: str, schema: dict[str, Any]) -> tuple[list[str], list[str]]:
    required = set(schema.get("required") or [])
    nested: list[str] = []
    fields: list[str] = []
    properties: dict[str, Any] = schema.get("properties") or {}
    if not properties:
        fields.append("    pass")
        return nested, fields
    for field, definition in properties.items():
        type_name, extra = _type_for(parent, field, definition)
        nested.extend(extra)
        annotation = type_name if field in required else f"NotRequired[{type_name}]"
        fields.append(f"    {field}: {annotation}")
    return nested, fields


def _type_for(parent: str, field: str, definition: dict[str, Any]) -> tuple[str, list[str]]:
    if "$ref" in definition:
        return definition["$ref"].rsplit("/", 1)[-1], []
    kind = definition.get("type")
    if kind == "string" and "enum" in definition:
        return _literal(definition["enum"]), []
    if kind == "string":
        return "str", []
    if kind == "integer":
        return "int", []
    if kind == "number":
        return "float", []
    if kind == "boolean":
        return "bool", []
    if kind == "array":
        item_type, extra = _type_for(parent, field, definition.get("items") or {"type": "object"})
        return f"list[{item_type}]", extra
    if kind == "object":
        nested_name = "ErrorBody" if parent == "Error" and field == "error" else f"{parent}{_pascal(field)}"
        nested, fields = _object_body(nested_name, definition)
        block = [*nested, f"class {nested_name}(TypedDict):", *fields, ""]
        return nested_name, block
    raise RuntimeError(f"Unsupported property {parent}.{field}")


def _literal(values: list[str]) -> str:
    if len(values) <= 3:
        inner = ", ".join(f'"{value}"' for value in values)
        return f"Literal[{inner}]"
    lines = ["Literal["]
    lines.extend(f'    "{value}",' for value in values)
    lines.append("]")
    return "\n".join(lines)


def _pascal(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in value.replace("-", "_").split("_") if part)


def load_document(path: str | None = None) -> dict[str, Any]:
    source = path or config.open_api_spec
    if not source:
        raise RuntimeError("No OpenAPI document. Set OPENAPI_SPEC or use the demo app.")
    file = Path(source)
    loaded = yaml.safe_load(file.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"OpenAPI document must be a mapping: {source}")
    return loaded


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    spec = load_document()
    rendered = render_models(spec)
    check = "--check" in args
    if check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != rendered:
            print(
                f"{TARGET.relative_to(ROOT)} is out of date. Run: uv run python -m utils.generate_api_types",
                file=sys.stderr,
            )
            return 1
        print(f"{TARGET.relative_to(ROOT)} matches the contract")
        return 0
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
