"""Validate API responses against the OpenAPI contract.

A response violates the contract when its operation isn't documented, its status
isn't documented for that operation, or its body doesn't match the documented
schema (including undocumented fields, since the schemas forbid extra properties).

The fixtures run this on every API response, from API clients and from the browser.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml
from jsonschema import Draft202012Validator
from jsonschema.protocols import Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")


@dataclass(frozen=True)
class ContractResponse:
    method: str
    path: str
    status: int
    body: Any
    body_unavailable: bool = False


class ContractViolation(Exception):
    """Raised when a response breaks the contract. The message lists every problem."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("API response does not match the contract:\n  - " + "\n  - ".join(problems))
        self.problems = problems


class Contract:
    def __init__(self, spec_path: str) -> None:
        self.spec = _load_spec(spec_path)
        registry: Registry[Any] = Registry().with_contents(
            [("urn:openapi", self.spec)],
            default_specification=DRAFT202012,
        )
        self._registry = registry
        self._validators: dict[str, Validator] = {}
        paths = self.spec.get("paths") or {}
        self._routes: list[tuple[str, re.Pattern[str]]] = [
            (template, _compile_template(template)) for template in paths
        ]

    def template_for(self, path: str) -> str | None:
        """Documented path template for a concrete path, e.g. /api/items/7 -> /api/items/{id}."""
        pathname = path.split("?", 1)[0]
        for template, pattern in self._routes:
            if pattern.search(pathname):
                return template
        return None

    def check(self, response: ContractResponse) -> list[str]:
        """Problems with a response; empty when it matches the contract."""
        verb = response.method.lower()
        template = self.template_for(response.path)
        path_item = (self.spec.get("paths") or {}).get(template or "", {})
        operation = path_item.get(verb) if isinstance(path_item, dict) else None
        if template is None or not isinstance(operation, dict) or verb not in METHODS:
            return [f"{response.method} {response.path} is not in the contract"]

        label = f"{response.method.upper()} {template} -> {response.status}"
        documented_responses = operation.get("responses") or {}
        status_key = (
            str(response.status) if str(response.status) in documented_responses else f"{str(response.status)[0]}XX"
        )
        documented = documented_responses.get(status_key)
        if documented is None:
            known = ", ".join(documented_responses)
            return [f"{label}: status {response.status} is not documented (documented: {known})"]

        if response.body_unavailable:
            return []
        resolved = self._resolve_response(documented)
        schema = ((resolved.get("content") or {}).get("application/json") or {}).get("schema")
        if schema is None:
            empty = response.body is None or response.body == ""
            if empty:
                return []
            preview = json.dumps(response.body)[:200]
            return [f"{label}: documented without a body, but got {preview}"]

        pointer = _schema_pointer(template, verb, status_key, documented)
        validator = self._validator_for(pointer)
        errors = sorted(validator.iter_errors(response.body), key=lambda error: list(error.path))
        problems: list[str] = []
        for error in errors:
            location = "/" + "/".join(str(part) for part in error.absolute_path)
            extra = ""
            if isinstance(error.validator_value, bool) and error.validator == "additionalProperties":
                # jsonschema's message already names the property when possible
                extra = ""
            problems.append(f"{label}: body{location if location != '/' else ''} {error.message}{extra}")
        return problems

    def _resolve_response(self, response: dict[str, Any]) -> dict[str, Any]:
        ref = response.get("$ref")
        if not isinstance(ref, str):
            return response
        name = ref.removeprefix("#/components/responses/")
        resolved = (self.spec.get("components") or {}).get("responses", {}).get(name)
        if not isinstance(resolved, dict):
            raise RuntimeError(f"Contract references a missing response: {ref}")
        return resolved

    def _validator_for(self, pointer: str) -> Validator:
        cached = self._validators.get(pointer)
        if cached is not None:
            return cached
        validator = Draft202012Validator(
            {"$ref": pointer},
            registry=self._registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        self._validators[pointer] = validator
        return validator


def _compile_template(template: str) -> re.Pattern[str]:
    parts = re.split(r"(\{[^/}]+\})", template)
    pattern = "".join("[^/]+" if part.startswith("{") and part.endswith("}") else re.escape(part) for part in parts)
    return re.compile(f"^{pattern}$")


def _schema_pointer(template: str, verb: str, status: str, documented: dict[str, Any]) -> str:
    ref = documented.get("$ref")
    if isinstance(ref, str):
        return f"urn:openapi{ref}/content/application~1json/schema"
    escaped = template.replace("~", "~0").replace("/", "~1")
    return f"urn:openapi#/paths/{escaped}/{verb}/responses/{status}/content/application~1json/schema"


def _load_spec(spec_path: str) -> dict[str, Any]:
    if spec_path.startswith(("http://", "https://")):
        with urlopen(spec_path, timeout=30) as response:  # spec URL comes from OPENAPI_SPEC
            text = response.read().decode("utf-8")
    else:
        text = Path(spec_path).read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"OpenAPI document must be a mapping: {spec_path}")
    return loaded
