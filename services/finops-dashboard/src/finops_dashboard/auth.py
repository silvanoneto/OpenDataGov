"""Auth0 JWT Authentication for FinOps Dashboard.

Provides JWT token validation, user extraction, and role-based access control (RBAC).
"""

from __future__ import annotations

import logging
from functools import wraps

import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== Configuration ====================


class Auth0Config(BaseModel):
    """Auth0 configuration."""

    domain: str = Field(..., description="Auth0 domain (e.g., 'opendatagov.us.auth0.com')")
    audience: str = Field(..., description="Auth0 API audience")
    algorithms: list[str] = Field(default=["RS256"], description="JWT algorithms")
    issuer: str = Field(default="", description="JWT issuer (defaults to https://{domain}/)")

    def __init__(self, **data):
        """Initialize Auth0 config."""
        super().__init__(**data)
        if not self.issuer:
            self.issuer = f"https://{self.domain}/"


# Global Auth0 configuration (set via environment variables)
AUTH0_CONFIG: Auth0Config | None = None


def init_auth0(domain: str, audience: str, algorithms: list[str] | None = None):
    """Initialize Auth0 configuration.

    Args:
        domain: Auth0 domain
        audience: Auth0 API audience
        algorithms: JWT algorithms (default: RS256)
    """
    global AUTH0_CONFIG
    AUTH0_CONFIG = Auth0Config(
        domain=domain,
        audience=audience,
        algorithms=algorithms or ["RS256"],
    )
    logger.info(f"Auth0 initialized: domain={domain}, audience={audience}")


# ==================== User Models ====================


class User(BaseModel):
    """Authenticated user."""

    sub: str = Field(..., description="User ID (subject)")
    email: str | None = Field(None, description="User email")
    name: str | None = Field(None, description="User name")
    roles: list[str] = Field(default_factory=list, description="User roles")
    permissions: list[str] = Field(default_factory=list, description="User permissions")

    @property
    def user_id(self) -> str:
        """Get user ID."""
        return self.sub

    def has_role(self, role: str) -> bool:
        """Check if user has role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has permission."""
        return permission in self.permissions

    def has_any_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)

    def has_all_roles(self, *roles: str) -> bool:
        """Check if user has all of the specified roles."""
        return all(role in self.roles for role in roles)


# ==================== JWT Validation ====================

security = HTTPBearer()


def get_jwks_client() -> PyJWKClient:
    """Get JWKS client for Auth0."""
    if not AUTH0_CONFIG:
        raise HTTPException(
            status_code=500,
            detail="Auth0 not configured. Call init_auth0() first.",
        )

    jwks_url = f"https://{AUTH0_CONFIG.domain}/.well-known/jwks.json"
    return PyJWKClient(jwks_url)


def verify_jwt(token: str) -> dict:
    """Verify JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid
    """
    if not AUTH0_CONFIG:
        raise HTTPException(
            status_code=500,
            detail="Auth0 not configured",
        )

    try:
        # Get signing key from JWKS
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and verify token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=AUTH0_CONFIG.algorithms,
            audience=AUTH0_CONFIG.audience,
            issuer=AUTH0_CONFIG.issuer,
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
        ) from None
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {e!s}",
        ) from e
    except Exception as e:
        logger.error(f"Error verifying JWT: {e}")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
        ) from e


def extract_user_from_token(payload: dict) -> User:
    """Extract user information from JWT payload.

    Args:
        payload: Decoded JWT payload

    Returns:
        User object
    """
    # Extract standard claims
    user_id = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name")

    # Extract custom claims (roles and permissions)
    # Auth0 typically stores these under a custom namespace
    namespace = "https://opendatagov.com/"
    roles = payload.get(f"{namespace}roles", [])
    permissions = payload.get("permissions", [])

    # Also check for Auth0 Management API format
    if not roles:
        roles = payload.get("https://schemas.auth0.com/roles", [])

    return User(
        sub=user_id,
        email=email,
        name=name,
        roles=roles,
        permissions=permissions,
    )


# ==================== FastAPI Dependencies ====================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> User:
    """FastAPI dependency to get current authenticated user.

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.user_id}

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        Authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    payload = verify_jwt(token)
    user = extract_user_from_token(payload)

    logger.debug(f"Authenticated user: {user.user_id}")
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Security(security, auto_error=False),
) -> User | None:
    """FastAPI dependency to get current user (optional).

    Returns None if no credentials provided.

    Args:
        credentials: HTTP Bearer credentials (optional)

    Returns:
        Authenticated user or None
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = verify_jwt(token)
        user = extract_user_from_token(payload)
        return user
    except HTTPException:
        return None


# ==================== Role-Based Access Control ====================


class RoleChecker:
    """Dependency to check user roles.

    Usage:
        @app.get("/admin")
        async def admin_only(user: User = Depends(RoleChecker(["admin"]))):
            return {"message": "Admin access granted"}
    """

    def __init__(self, allowed_roles: list[str]):
        """Initialize role checker.

        Args:
            allowed_roles: List of allowed roles
        """
        self.allowed_roles = allowed_roles

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        """Check if user has required role.

        Args:
            user: Authenticated user

        Returns:
            User if authorized

        Raises:
            HTTPException: If user lacks required role
        """
        if not user.has_any_role(*self.allowed_roles):
            raise HTTPException(
                status_code=403,
                detail=f"User does not have required role. Required: {self.allowed_roles}",
            )

        return user


class PermissionChecker:
    """Dependency to check user permissions.

    Usage:
        @app.post("/budgets")
        async def create_budget(user: User = Depends(PermissionChecker(["create:budgets"]))):
            return {"message": "Budget created"}
    """

    def __init__(self, required_permissions: list[str]):
        """Initialize permission checker.

        Args:
            required_permissions: List of required permissions
        """
        self.required_permissions = required_permissions

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        """Check if user has required permissions.

        Args:
            user: Authenticated user

        Returns:
            User if authorized

        Raises:
            HTTPException: If user lacks required permissions
        """
        missing_permissions = [perm for perm in self.required_permissions if not user.has_permission(perm)]

        if missing_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permissions: {missing_permissions}",
            )

        return user


# ==================== Utility Functions ====================


def require_auth(func):
    """Decorator to require authentication for a function.

    Usage:
        @require_auth
        async def my_function(user: User):
            print(f"User: {user.user_id}")
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Check if 'user' is already in kwargs (injected by FastAPI)
        if "user" not in kwargs:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
            )

        return await func(*args, **kwargs)

    return wrapper


def require_role(*roles: str):
    """Decorator to require specific roles.

    Usage:
        @require_role("admin", "finance_manager")
        async def admin_function(user: User):
            print(f"Admin user: {user.user_id}")
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User, **kwargs):
            if not user.has_any_role(*roles):
                raise HTTPException(
                    status_code=403,
                    detail=f"User does not have required role. Required: {list(roles)}",
                )

            return await func(*args, user=user, **kwargs)

        return wrapper

    return decorator


def require_permission(*permissions: str):
    """Decorator to require specific permissions.

    Usage:
        @require_permission("read:budgets", "write:budgets")
        async def manage_budgets(user: User):
            print(f"User: {user.user_id}")
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User, **kwargs):
            missing = [perm for perm in permissions if not user.has_permission(perm)]

            if missing:
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permissions: {missing}",
                )

            return await func(*args, user=user, **kwargs)

        return wrapper

    return decorator


# ==================== Mock Auth (for Development) ====================


class MockAuth:
    """Mock authentication for development/testing.

    DO NOT USE IN PRODUCTION!
    """

    @staticmethod
    def get_mock_user(
        user_id: str = "dev|123456",
        email: str = "dev@opendatagov.com",
        name: str = "Developer User",
        roles: list[str] | None = None,
    ) -> User:
        """Get mock user for testing.

        Args:
            user_id: User ID
            email: Email
            name: Name
            roles: Roles (default: admin)

        Returns:
            Mock user
        """
        if roles is None:
            roles = ["admin", "finance_manager"]

        return User(
            sub=user_id,
            email=email,
            name=name,
            roles=roles,
            permissions=["read:*", "write:*", "delete:*"],
        )


async def get_current_user_dev() -> User:
    """Development-only dependency that returns mock user.

    DO NOT USE IN PRODUCTION!

    Usage (for development only):
        app = FastAPI()

        # Override get_current_user with mock
        app.dependency_overrides[get_current_user] = get_current_user_dev
    """
    logger.warning("Using mock authentication - DO NOT USE IN PRODUCTION!")
    return MockAuth.get_mock_user()
