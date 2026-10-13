"""Saved login sessions, one per role.

Browser tests load the session for their role. The files hold live session cookies,
so .auth/ is git-ignored.
"""

from __future__ import annotations

from config import ROOT, Role


def auth_file(role: Role) -> str:
    """Path of the saved session (cookies and local storage) for a role."""
    return str(ROOT / ".auth" / f"{role}.json")
