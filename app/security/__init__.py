"""
app.security — Enterprise healthcare security layer.

Public API
----------
Auth:
  AuthService                 Full JWT auth lifecycle (login/refresh/logout)
  get_auth_service()          Singleton accessor
  auth_router                 FastAPI router (/auth/*)
  user_router                 FastAPI router (/users/*)
  UserRole                    Role constants: admin / reviewer / provider
  UserPublic                  Safe user representation (no passwords)
  TokenResponse               Login/refresh response with token pair

RBAC:
  Resource                    Enum of protected resources
  Action                      Enum of allowed actions
  is_permitted(role, res, act) Programmatic permission check
  require_permission(res, act) FastAPI dependency factory
  check_permission(...)        Service-layer permission check (raises)
  AdminRequired()              FastAPI dependency: admin only
  ReviewerOrAdmin()            FastAPI dependency: reviewer or admin

Encryption:
  EncryptionService            AES-256-GCM field encryption
  get_encryption_service()     Singleton accessor
  encrypt_field(value)         One-shot encrypt
  decrypt_field(value)         One-shot decrypt
  EncryptedStr                 SQLAlchemy TypeDecorator

PII Masking:
  PIIMasker                    HIPAA PHI masking service
  get_pii_masker()             Singleton accessor
  MaskResult                   Masking operation result with statistics
  HIPAA_MASK_PATTERNS          All 18 HIPAA identifier patterns

Secure Storage:
  SecureDocumentStorage        Encrypted document storage with RBAC
  get_secure_document_storage() Singleton accessor
  DocumentHandle               Document metadata handle (no content)
"""

from app.security.auth import (
    AuthService,
    CreateUserRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    UserInDB,
    UserPublic,
    UserRole,
    auth_router,
    get_auth_service,
    user_router,
)
from app.security.encryption import (
    EncryptedStr,
    EncryptionService,
    decrypt_field,
    encrypt_field,
    get_encryption_service,
)
from app.security.pii import (
    HIPAA_MASK_PATTERNS,
    MaskPattern,
    MaskResult,
    PIIMasker,
    get_pii_masker,
)
from app.security.rbac import (
    Action,
    AdminRequired,
    Resource,
    ReviewerOrAdmin,
    check_permission,
    get_allowed_roles,
    get_permissions_for_role,
    is_permitted,
    require_ownership_or_role,
    require_permission,
)
from app.security.storage import (
    DocumentHandle,
    SecureDocumentStorage,
    get_secure_document_storage,
)

__all__ = [
    # Auth
    "UserRole", "UserInDB", "UserPublic",
    "LoginRequest", "RefreshRequest", "TokenResponse",
    "CreateUserRequest", "MessageResponse",
    "AuthService", "get_auth_service",
    "auth_router", "user_router",
    # RBAC
    "Resource", "Action",
    "is_permitted", "get_allowed_roles", "get_permissions_for_role",
    "require_permission", "require_ownership_or_role", "check_permission",
    "AdminRequired", "ReviewerOrAdmin",
    # Encryption
    "EncryptionService", "get_encryption_service",
    "encrypt_field", "decrypt_field", "EncryptedStr",
    # PII
    "PIIMasker", "get_pii_masker", "MaskResult",
    "HIPAA_MASK_PATTERNS", "MaskPattern",
    # Storage
    "SecureDocumentStorage", "get_secure_document_storage", "DocumentHandle",
]
