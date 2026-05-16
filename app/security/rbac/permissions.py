"""
Resource-level RBAC permission matrix.

Extends the basic role check in app/api/dependencies/common.py with
fine-grained resource + action permissions.

Roles
-----
admin     — Full platform access; can manage users, view all cases, override decisions
reviewer  — Can review and decide on PA cases assigned to them; cannot manage users
provider  — Can submit PA requests and view status of their own cases; read-only on policies

Permission matrix
-----------------
Resource             Action          admin  reviewer  provider
-----------------------------------------------------------
pa_case              create          ✓      ✗         ✓
pa_case              read_own        ✓      ✓         ✓
pa_case              read_any        ✓      ✓         ✗
pa_case              update          ✓      ✓         ✗
pa_case              delete          ✓      ✗         ✗
pa_case              override        ✓      ✗         ✗
document             upload          ✓      ✓         ✓
document             read_own        ✓      ✓         ✓
document             read_any        ✓      ✓         ✗
document             delete          ✓      ✗         ✗
review_action        create          ✓      ✓         ✗
review_action        read            ✓      ✓         ✓
clarification        answer          ✓      ✗         ✓
clarification        read            ✓      ✓         ✓
audit_log            read            ✓      ✗         ✗
user                 create          ✓      ✗         ✗
user                 read            ✓      ✗         ✗
user                 update          ✓      ✗         ✗
user                 delete          ✓      ✗         ✗
policy               read            ✓      ✓         ✓
policy               write           ✓      ✗         ✗
guardrail            manage          ✓      ✗         ✗
metrics              read            ✓      ✓         ✗
"""

from __future__ import annotations

from enum import Enum
from typing import frozenset


class Resource(str, Enum):
    PA_CASE        = "pa_case"
    DOCUMENT       = "document"
    REVIEW_ACTION  = "review_action"
    CLARIFICATION  = "clarification"
    AUDIT_LOG      = "audit_log"
    USER           = "user"
    POLICY         = "policy"
    GUARDRAIL      = "guardrail"
    METRICS        = "metrics"


class Action(str, Enum):
    CREATE      = "create"
    READ_OWN    = "read_own"
    READ_ANY    = "read_any"
    UPDATE      = "update"
    DELETE      = "delete"
    OVERRIDE    = "override"
    UPLOAD      = "upload"
    ANSWER      = "answer"
    WRITE       = "write"
    MANAGE      = "manage"
    READ        = "read"


# Permission matrix: (resource, action) → frozenset of allowed roles
_PERMISSION_MATRIX: dict[tuple[Resource, Action], frozenset[str]] = {

    # PA Cases
    (Resource.PA_CASE, Action.CREATE):    frozenset({"admin", "provider"}),
    (Resource.PA_CASE, Action.READ_OWN):  frozenset({"admin", "reviewer", "provider"}),
    (Resource.PA_CASE, Action.READ_ANY):  frozenset({"admin", "reviewer"}),
    (Resource.PA_CASE, Action.UPDATE):    frozenset({"admin", "reviewer"}),
    (Resource.PA_CASE, Action.DELETE):    frozenset({"admin"}),
    (Resource.PA_CASE, Action.OVERRIDE):  frozenset({"admin"}),

    # Documents
    (Resource.DOCUMENT, Action.UPLOAD):   frozenset({"admin", "reviewer", "provider"}),
    (Resource.DOCUMENT, Action.READ_OWN): frozenset({"admin", "reviewer", "provider"}),
    (Resource.DOCUMENT, Action.READ_ANY): frozenset({"admin", "reviewer"}),
    (Resource.DOCUMENT, Action.DELETE):   frozenset({"admin"}),

    # Review actions
    (Resource.REVIEW_ACTION, Action.CREATE): frozenset({"admin", "reviewer"}),
    (Resource.REVIEW_ACTION, Action.READ):   frozenset({"admin", "reviewer", "provider"}),

    # Clarification
    (Resource.CLARIFICATION, Action.ANSWER): frozenset({"admin", "provider"}),
    (Resource.CLARIFICATION, Action.READ):   frozenset({"admin", "reviewer", "provider"}),

    # Audit log — admin only
    (Resource.AUDIT_LOG, Action.READ): frozenset({"admin"}),

    # User management — admin only
    (Resource.USER, Action.CREATE): frozenset({"admin"}),
    (Resource.USER, Action.READ):   frozenset({"admin"}),
    (Resource.USER, Action.UPDATE): frozenset({"admin"}),
    (Resource.USER, Action.DELETE): frozenset({"admin"}),

    # Policy documents
    (Resource.POLICY, Action.READ):  frozenset({"admin", "reviewer", "provider"}),
    (Resource.POLICY, Action.WRITE): frozenset({"admin"}),

    # Guardrail management — admin only
    (Resource.GUARDRAIL, Action.MANAGE): frozenset({"admin"}),
    (Resource.GUARDRAIL, Action.READ):   frozenset({"admin"}),

    # Metrics / observability
    (Resource.METRICS, Action.READ): frozenset({"admin", "reviewer"}),
}


def is_permitted(
    role: str,
    resource: Resource | str,
    action: Action | str,
    owner_id: str | None = None,
    requester_id: str | None = None,
) -> bool:
    """
    Check whether ``role`` is permitted to perform ``action`` on ``resource``.

    For READ_ANY vs READ_OWN:
        If the caller is the owner (requester_id == owner_id), READ_OWN is
        checked.  Otherwise READ_ANY is checked.

    Args:
        role:          Caller's RBAC role string.
        resource:      Resource being accessed.
        action:        Action being attempted.
        owner_id:      The resource owner's ID (for ownership-based checks).
        requester_id:  The caller's ID.

    Returns:
        True if permitted, False otherwise.
    """
    if isinstance(resource, str):
        try:
            resource = Resource(resource)
        except ValueError:
            return False

    if isinstance(action, str):
        try:
            action = Action(action)
        except ValueError:
            return False

    # Ownership-aware read: if caller owns the resource, READ_OWN applies
    effective_action = action
    if action == Action.READ_ANY and owner_id and requester_id and owner_id == requester_id:
        effective_action = Action.READ_OWN

    allowed_roles = _PERMISSION_MATRIX.get((resource, effective_action), frozenset())
    return role in allowed_roles


def get_allowed_roles(resource: Resource, action: Action) -> frozenset[str]:
    """Return the set of roles allowed for a given resource + action."""
    return _PERMISSION_MATRIX.get((resource, action), frozenset())


def get_permissions_for_role(role: str) -> list[tuple[Resource, Action]]:
    """Return all (resource, action) pairs permitted for a given role."""
    return [
        (res, act)
        for (res, act), roles in _PERMISSION_MATRIX.items()
        if role in roles
    ]
