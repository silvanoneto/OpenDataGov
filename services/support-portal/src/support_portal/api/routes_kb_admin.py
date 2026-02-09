"""Knowledge Base Admin API - CRUD operations for articles.

Staff-only endpoints for managing KB content.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from support_portal.elasticsearch_client import KnowledgeBaseSearchClient
from support_portal.models import KnowledgeBaseArticleRow, UserRow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/kb", tags=["kb-admin"])


# Pydantic models for request/response
class CreateArticleRequest(BaseModel):
    """Request to create new KB article."""

    title: str
    content: str
    category: str
    tags: list[str] = []
    published: bool = False


class UpdateArticleRequest(BaseModel):
    """Request to update existing article."""

    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    published: bool | None = None


class ArticleResponse(BaseModel):
    """KB article response."""

    article_id: str
    title: str
    slug: str
    content: str
    category: str
    tags: list[str]
    author: str
    view_count: int
    helpful_votes: int
    unhelpful_votes: int
    published: bool
    created_at: datetime
    updated_at: datetime


# Dependencies (same as main.py)
async def get_db() -> AsyncSession:
    """Get database session."""
    from odg_core.db.session import get_async_session

    async with get_async_session() as session:
        yield session


async def get_current_user(db: AsyncSession = Depends(get_db)) -> UserRow:
    """Get authenticated user (placeholder)."""
    # TODO: Real authentication
    user_email = "admin@opendatagov.io"

    result = await db.execute(select(UserRow).where(UserRow.email == user_email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    return user


async def require_staff(current_user: UserRow = Depends(get_current_user)) -> UserRow:
    """Require staff role for admin operations."""
    if current_user.role != "staff":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff access required")

    return current_user


# Elasticsearch client instance
es_client = KnowledgeBaseSearchClient()


@router.post("/articles", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article(
    request: CreateArticleRequest,
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponse:
    """Create new knowledge base article.

    Automatically generates slug from title and indexes in Elasticsearch.
    """
    import re
    import uuid

    # Generate slug from title
    slug = re.sub(r"[^\w\s-]", "", request.title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")

    # Create article
    article = KnowledgeBaseArticleRow(
        article_id=f"kb_{uuid.uuid4().hex[:8]}",
        title=request.title,
        slug=slug,
        content=request.content,
        category=request.category,
        tags=request.tags,
        author=current_user.email,
        published=request.published,
    )

    db.add(article)
    await db.commit()
    await db.refresh(article)

    # Index in Elasticsearch if published
    if article.published:
        await es_client.index_article(
            {
                "article_id": article.article_id,
                "title": article.title,
                "content": article.content,
                "slug": article.slug,
                "category": article.category,
                "tags": article.tags,
                "author": article.author,
                "view_count": article.view_count,
                "helpful_votes": article.helpful_votes,
                "unhelpful_votes": article.unhelpful_votes,
                "published": article.published,
                "created_at": article.created_at,
                "updated_at": article.updated_at,
            }
        )

    logger.info(f"Created KB article: {article.article_id} by {current_user.email}")

    return ArticleResponse.model_validate(article)


@router.get("/articles", response_model=list[ArticleResponse])
async def list_articles(
    category: str | None = Query(None),
    published: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[ArticleResponse]:
    """List all KB articles (including unpublished drafts).

    Staff can see all articles, including drafts.
    """
    query = select(KnowledgeBaseArticleRow)

    if category:
        query = query.where(KnowledgeBaseArticleRow.category == category)

    if published is not None:
        query = query.where(KnowledgeBaseArticleRow.published == published)

    query = query.order_by(KnowledgeBaseArticleRow.updated_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    articles = result.scalars().all()

    return [ArticleResponse.model_validate(a) for a in articles]


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponse:
    """Get article by ID (including unpublished)."""
    result = await db.execute(select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.article_id == article_id))
    article = result.scalars().first()

    if not article:
        raise HTTPException(404, "Article not found")

    return ArticleResponse.model_validate(article)


@router.patch("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: str,
    request: UpdateArticleRequest,
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponse:
    """Update existing article.

    Re-indexes in Elasticsearch if published.
    """
    result = await db.execute(select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.article_id == article_id))
    article = result.scalars().first()

    if not article:
        raise HTTPException(404, "Article not found")

    # Update fields
    updated = False

    if request.title is not None:
        article.title = request.title
        # Regenerate slug
        import re

        slug = re.sub(r"[^\w\s-]", "", request.title.lower())
        slug = re.sub(r"[\s_-]+", "-", slug)
        article.slug = slug.strip("-")
        updated = True

    if request.content is not None:
        article.content = request.content
        updated = True

    if request.category is not None:
        article.category = request.category
        updated = True

    if request.tags is not None:
        article.tags = request.tags
        updated = True

    if request.published is not None:
        # Publish/unpublish
        if request.published and not article.published:
            # Publishing - add to Elasticsearch
            article.published = True
            updated = True
        elif not request.published and article.published:
            # Unpublishing - remove from Elasticsearch
            article.published = False
            await es_client.delete_article(article_id)
            updated = True

    if updated:
        article.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(article)

        # Re-index if published
        if article.published:
            await es_client.index_article(
                {
                    "article_id": article.article_id,
                    "title": article.title,
                    "content": article.content,
                    "slug": article.slug,
                    "category": article.category,
                    "tags": article.tags,
                    "author": article.author,
                    "view_count": article.view_count,
                    "helpful_votes": article.helpful_votes,
                    "unhelpful_votes": article.unhelpful_votes,
                    "published": article.published,
                    "created_at": article.created_at,
                    "updated_at": article.updated_at,
                }
            )

    logger.info(f"Updated KB article: {article_id} by {current_user.email}")

    return ArticleResponse.model_validate(article)


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: str,
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete article (hard delete).

    Also removes from Elasticsearch index.
    """
    result = await db.execute(select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.article_id == article_id))
    article = result.scalars().first()

    if not article:
        raise HTTPException(404, "Article not found")

    # Delete from Elasticsearch if published
    if article.published:
        await es_client.delete_article(article_id)

    # Delete from database
    await db.delete(article)
    await db.commit()

    logger.info(f"Deleted KB article: {article_id} by {current_user.email}")


@router.post("/articles/{article_id}/publish", response_model=ArticleResponse)
async def publish_article(
    article_id: str,
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponse:
    """Publish article (make visible to customers).

    Indexes in Elasticsearch.
    """
    result = await db.execute(select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.article_id == article_id))
    article = result.scalars().first()

    if not article:
        raise HTTPException(404, "Article not found")

    if article.published:
        raise HTTPException(400, "Article already published")

    # Publish
    article.published = True
    article.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(article)

    # Index in Elasticsearch
    await es_client.index_article(
        {
            "article_id": article.article_id,
            "title": article.title,
            "content": article.content,
            "slug": article.slug,
            "category": article.category,
            "tags": article.tags,
            "author": article.author,
            "view_count": article.view_count,
            "helpful_votes": article.helpful_votes,
            "unhelpful_votes": article.unhelpful_votes,
            "published": article.published,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        }
    )

    logger.info(f"Published KB article: {article_id} by {current_user.email}")

    return ArticleResponse.model_validate(article)


@router.post("/articles/{article_id}/unpublish", response_model=ArticleResponse)
async def unpublish_article(
    article_id: str,
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponse:
    """Unpublish article (hide from customers).

    Removes from Elasticsearch index.
    """
    result = await db.execute(select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.article_id == article_id))
    article = result.scalars().first()

    if not article:
        raise HTTPException(404, "Article not found")

    if not article.published:
        raise HTTPException(400, "Article not published")

    # Unpublish
    article.published = False
    article.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(article)

    # Remove from Elasticsearch
    await es_client.delete_article(article_id)

    logger.info(f"Unpublished KB article: {article_id} by {current_user.email}")

    return ArticleResponse.model_validate(article)


@router.post("/reindex", response_model=dict[str, Any])
async def reindex_all_articles(
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reindex all published articles in Elasticsearch.

    Useful after schema changes or index corruption.
    """
    # Get all published articles
    result = await db.execute(
        select(KnowledgeBaseArticleRow).where(KnowledgeBaseArticleRow.published == True)  # noqa: E712
    )
    articles = result.scalars().all()

    # Convert to dict format
    articles_data = [
        {
            "article_id": a.article_id,
            "title": a.title,
            "content": a.content,
            "slug": a.slug,
            "category": a.category,
            "tags": a.tags,
            "author": a.author,
            "view_count": a.view_count,
            "helpful_votes": a.helpful_votes,
            "unhelpful_votes": a.unhelpful_votes,
            "published": a.published,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }
        for a in articles
    ]

    # Reindex all
    count = await es_client.reindex_all(articles_data)

    logger.info(f"Reindexed {count} articles by {current_user.email}")

    return {
        "success": True,
        "articles_reindexed": count,
        "total_articles": len(articles),
    }


@router.get("/categories", response_model=list[str])
async def list_categories(
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Get list of all article categories."""
    from sqlalchemy import func

    result = await db.execute(select(func.distinct(KnowledgeBaseArticleRow.category)))
    categories = [row[0] for row in result.all()]

    return sorted(categories)


@router.get("/tags", response_model=list[str])
async def list_tags(
    current_user: UserRow = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Get list of all article tags."""
    from sqlalchemy import func

    result = await db.execute(select(func.unnest(KnowledgeBaseArticleRow.tags).label("tag")))
    tags = list(set(row[0] for row in result.all()))

    return sorted(tags)
