"""HTTP client for API tests, built on Playwright's API request context.

Responses are plain objects so assertions stay simple: `assert response.status == 201`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import APIRequestContext

from utils.logger import create_logger

log = create_logger("api")
_SENSITIVE = re.compile(r"pass(word)?|secret|token|authorization|api[-_]?key", re.IGNORECASE)

ValidateFn = Callable[[dict[str, Any]], None]
ExchangeFn = Callable[[dict[str, Any]], None]


@dataclass
class ApiResponse:
    status: int
    headers: dict[str, str]
    body: Any


def redact(value: Any) -> Any:
    """Mask sensitive fields so credentials never reach logs or reports."""
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: "***" if _SENSITIVE.search(key) else redact(item) for key, item in value.items()}
    return value


class ApiClient:
    def __init__(
        self,
        context: APIRequestContext,
        *,
        base_url: str | None = None,
        validate: ValidateFn | None = None,
        on_exchange: ExchangeFn | None = None,
        owns_context: bool = False,
    ) -> None:
        self.context = context
        self.base_url = base_url
        self.token: str | None = None
        self._validate = validate
        self._on_exchange = on_exchange
        self._owns_context = owns_context

    @classmethod
    def create(
        cls,
        playwright: Any,
        *,
        base_url: str,
        validate: ValidateFn | None = None,
        on_exchange: ExchangeFn | None = None,
    ) -> ApiClient:
        context = playwright.request.new_context(base_url=base_url)
        return cls(context, base_url=base_url, validate=validate, on_exchange=on_exchange, owns_context=True)

    def login(self, username: str, password: str) -> ApiResponse:
        """Log in via POST /api/login and use the returned token for later requests."""
        response = self.post("/api/login", {"username": username, "password": password})
        if response.status != 200:
            raise RuntimeError(f"Login failed with HTTP {response.status}: {json.dumps(response.body)}")
        token = response.body.get("token") if isinstance(response.body, dict) else None
        if not isinstance(token, str):
            raise RuntimeError("Login response did not include a token")
        self.token = token
        return response

    def get(self, path: str, **options: Any) -> ApiResponse:
        return self.send("GET", path, **options)

    def post(self, path: str, data: Any = None, **options: Any) -> ApiResponse:
        return self.send("POST", path, data=data, **options)

    def put(self, path: str, data: Any = None, **options: Any) -> ApiResponse:
        return self.send("PUT", path, data=data, **options)

    def delete(self, path: str, **options: Any) -> ApiResponse:
        return self.send("DELETE", path, **options)

    def send(
        self,
        method: str,
        path: str,
        *,
        data: Any = None,
        params: dict[str, str | float | bool] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse:
        all_headers = dict(headers or {})
        if self.token:
            all_headers["Authorization"] = f"Bearer {self.token}"
        url = f"{self.base_url}{path}" if self.base_url and path.startswith("/") else path
        response = self.context.fetch(url, method=method, data=data, params=params, headers=all_headers)
        text = response.text()
        body: Any = text
        try:
            body = json.loads(text) if text else None
        except json.JSONDecodeError:
            body = text
        result = ApiResponse(status=response.status, headers=response.headers, body=body)
        log["debug"](f"{method} {path} -> {result.status}")
        if self._validate:
            self._validate({"method": method, "path": path, "status": result.status, "body": result.body})
        if self._on_exchange:
            self._on_exchange(
                redact(
                    {
                        "request": {
                            "method": method,
                            "path": path,
                            "params": params,
                            "headers": all_headers,
                            "body": data,
                        },
                        "response": {"status": result.status, "body": result.body},
                    }
                )
            )
        return result

    def dispose(self) -> None:
        if self._owns_context:
            self.context.dispose()
