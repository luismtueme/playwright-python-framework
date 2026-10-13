"""Generated from the OpenAPI contract. Do not edit by hand.

Regenerate with: uv run python -m utils.generate_api_types
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

Role = Literal["admin", "viewer"]


class LoginRequest(TypedDict):
    username: str
    password: str


class User(TypedDict):
    username: str
    role: Role


class LoginResponse(TypedDict):
    token: str
    user: User


class ItemCreate(TypedDict):
    name: str


class Item(TypedDict):
    id: int
    name: str
    createdAt: str


class ItemList(TypedDict):
    items: list[Item]


class ErrorBody(TypedDict):
    code: Literal[
        "INVALID_CREDENTIALS",
        "INVALID_JSON",
        "UNAUTHORIZED",
        "FORBIDDEN",
        "NOT_FOUND",
        "VALIDATION_ERROR",
        "SERVER_ERROR",
    ]
    message: NotRequired[str]
    field: NotRequired[str]


class Error(TypedDict):
    error: ErrorBody
