"""GraphQL API endpoint for governance-engine (ADR-090)."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException, Request
from odg_core.auth.dependencies import get_current_user
from odg_core.auth.models import UserContext
from odg_core.graphql import schema
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter


async def get_graphql_context(request: Request) -> dict[str, Any]:
    """Provide context for GraphQL resolvers (db_session, user, etc.)."""
    session_factory = request.app.state.session_factory

    # Create async generator to manage session lifecycle
    async def _get_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session, session.begin():
            yield session

    # Get session from generator
    session_gen = _get_session()
    session = await session_gen.__anext__()

    # Authenticate user from request
    user: UserContext | None = None
    with contextlib.suppress(HTTPException):
        user = get_current_user(request)

    return {
        "db_session": session,
        "request": request,
        "user": user,
    }


# Create GraphQL router with Strawberry
graphql_router = GraphQLRouter(
    schema,
    path="/api/v1/graphql",
    graphql_ide="graphiql",  # Enable GraphiQL playground
    context_getter=get_graphql_context,  # type: ignore[arg-type]
)
