"""Elasticsearch client for Knowledge Base search.

Provides full-text search with relevance ranking, highlighting, and faceting.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

logger = logging.getLogger(__name__)


class KnowledgeBaseSearchClient:
    """Elasticsearch client for KB article search."""

    INDEX_NAME = "kb_articles"

    # Index mapping for optimal search
    INDEX_MAPPING: ClassVar[dict[str, Any]] = {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "custom_english": {
                        "type": "standard",
                        "stopwords": "_english_",
                    }
                }
            },
        },
        "mappings": {
            "properties": {
                "article_id": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "analyzer": "custom_english",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "ngram": {
                            "type": "text",
                            "analyzer": "standard",
                        },
                    },
                },
                "content": {
                    "type": "text",
                    "analyzer": "custom_english",
                },
                "slug": {"type": "keyword"},
                "category": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "author": {"type": "keyword"},
                "view_count": {"type": "integer"},
                "helpful_votes": {"type": "integer"},
                "unhelpful_votes": {"type": "integer"},
                "published": {"type": "boolean"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        },
    }

    def __init__(self, hosts: list[str] | None = None):
        """Initialize Elasticsearch client.

        Args:
            hosts: List of Elasticsearch hosts (default: localhost:9200)
        """
        if hosts is None:
            hosts = ["http://localhost:9200"]

        self.client = AsyncElasticsearch(hosts=hosts)

    async def create_index(self) -> bool:
        """Create KB articles index with custom mapping.

        Returns:
            True if created successfully
        """
        try:
            if await self.client.indices.exists(index=self.INDEX_NAME):
                logger.info(f"Index {self.INDEX_NAME} already exists")
                return True

            await self.client.indices.create(
                index=self.INDEX_NAME,
                body=self.INDEX_MAPPING,
            )

            logger.info(f"✅ Created Elasticsearch index: {self.INDEX_NAME}")
            return True

        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False

    async def index_article(self, article: dict[str, Any]) -> bool:
        """Index a single KB article.

        Args:
            article: Article data to index

        Returns:
            True if indexed successfully
        """
        try:
            await self.client.index(
                index=self.INDEX_NAME,
                id=article["article_id"],
                document={
                    "article_id": article["article_id"],
                    "title": article["title"],
                    "content": article["content"],
                    "slug": article["slug"],
                    "category": article["category"],
                    "tags": article.get("tags", []),
                    "author": article.get("author", ""),
                    "view_count": article.get("view_count", 0),
                    "helpful_votes": article.get("helpful_votes", 0),
                    "unhelpful_votes": article.get("unhelpful_votes", 0),
                    "published": article.get("published", False),
                    "created_at": article["created_at"].isoformat(),
                    "updated_at": article["updated_at"].isoformat(),
                },
            )

            logger.debug(f"Indexed article: {article['article_id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to index article {article['article_id']}: {e}")
            return False

    async def bulk_index_articles(self, articles: list[dict[str, Any]]) -> int:
        """Bulk index multiple articles.

        Args:
            articles: List of article data

        Returns:
            Number of articles indexed successfully
        """
        actions = [
            {
                "_index": self.INDEX_NAME,
                "_id": article["article_id"],
                "_source": {
                    "article_id": article["article_id"],
                    "title": article["title"],
                    "content": article["content"],
                    "slug": article["slug"],
                    "category": article["category"],
                    "tags": article.get("tags", []),
                    "author": article.get("author", ""),
                    "view_count": article.get("view_count", 0),
                    "helpful_votes": article.get("helpful_votes", 0),
                    "unhelpful_votes": article.get("unhelpful_votes", 0),
                    "published": article.get("published", False),
                    "created_at": article["created_at"].isoformat(),
                    "updated_at": article["updated_at"].isoformat(),
                },
            }
            for article in articles
        ]

        success, failed = await async_bulk(self.client, actions)

        logger.info(f"Bulk indexed {success} articles, {len(failed)} failed")
        return success

    async def search(
        self,
        query: str,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search KB articles with relevance ranking.

        Args:
            query: Search query
            category: Filter by category (optional)
            tags: Filter by tags (optional)
            limit: Number of results to return
            offset: Pagination offset

        Returns:
            Search results with highlights and scores
        """
        # Build Elasticsearch query
        must_clauses = [
            {"term": {"published": True}},  # Only published articles
        ]

        # Multi-match query across title and content
        if query:
            must_clauses.append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "title^3",  # Title 3x more important
                            "content",
                            "tags^2",  # Tags 2x more important
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                }
            )

        # Category filter
        if category:
            must_clauses.append({"term": {"category": category}})

        # Tags filter
        if tags:
            must_clauses.append({"terms": {"tags": tags}})

        search_body = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    # Boost by popularity
                    "should": [
                        {"rank_feature": {"field": "view_count", "boost": 0.1}},
                        {"rank_feature": {"field": "helpful_votes", "boost": 0.2}},
                    ],
                }
            },
            "highlight": {
                "fields": {
                    "title": {"pre_tags": ["<mark>"], "post_tags": ["</mark>"]},
                    "content": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                        "fragment_size": 150,
                        "number_of_fragments": 3,
                    },
                },
            },
            "from": offset,
            "size": limit,
        }

        try:
            response = await self.client.search(
                index=self.INDEX_NAME,
                body=search_body,
            )

            hits = response["hits"]["hits"]
            total = response["hits"]["total"]["value"]

            results = []
            for hit in hits:
                source = hit["_source"]
                result = {
                    "article_id": source["article_id"],
                    "title": source["title"],
                    "slug": source["slug"],
                    "category": source["category"],
                    "tags": source["tags"],
                    "view_count": source["view_count"],
                    "helpful_votes": source["helpful_votes"],
                    "score": hit["_score"],
                }

                # Add highlights if available
                if "highlight" in hit:
                    result["highlights"] = hit["highlight"]

                # Add excerpt from content
                content = source["content"]
                result["excerpt"] = content[:200] + "..." if len(content) > 200 else content

                results.append(result)

            return {
                "total": total,
                "results": results,
                "query": query,
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"total": 0, "results": [], "error": str(e)}

    async def suggest(self, prefix: str, limit: int = 5) -> list[str]:
        """Get search suggestions based on prefix.

        Args:
            prefix: Search prefix (e.g., "how to")
            limit: Number of suggestions

        Returns:
            List of suggested titles
        """
        search_body = {
            "suggest": {
                "title-suggest": {
                    "prefix": prefix,
                    "completion": {
                        "field": "title.ngram",
                        "size": limit,
                        "skip_duplicates": True,
                    },
                }
            }
        }

        try:
            response = await self.client.search(
                index=self.INDEX_NAME,
                body=search_body,
            )

            suggestions = []
            for option in response["suggest"]["title-suggest"][0]["options"]:
                suggestions.append(option["text"])

            return suggestions

        except Exception as e:
            logger.error(f"Suggest failed: {e}")
            return []

    async def get_facets(self) -> dict[str, Any]:
        """Get facets for filtering (categories, popular tags).

        Returns:
            Facets data (categories, tags counts)
        """
        search_body = {
            "size": 0,
            "query": {"term": {"published": True}},
            "aggs": {
                "categories": {"terms": {"field": "category", "size": 20}},
                "tags": {"terms": {"field": "tags", "size": 50}},
            },
        }

        try:
            response = await self.client.search(
                index=self.INDEX_NAME,
                body=search_body,
            )

            return {
                "categories": [
                    {"name": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in response["aggregations"]["categories"]["buckets"]
                ],
                "tags": [
                    {"name": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in response["aggregations"]["tags"]["buckets"]
                ],
            }

        except Exception as e:
            logger.error(f"Facets query failed: {e}")
            return {"categories": [], "tags": []}

    async def delete_article(self, article_id: str) -> bool:
        """Delete article from index.

        Args:
            article_id: Article ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            await self.client.delete(
                index=self.INDEX_NAME,
                id=article_id,
            )

            logger.info(f"Deleted article from index: {article_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete article {article_id}: {e}")
            return False

    async def reindex_all(self, articles: list[dict[str, Any]]) -> int:
        """Reindex all articles (useful for schema changes).

        Args:
            articles: All articles to reindex

        Returns:
            Number of articles reindexed
        """
        # Delete old index
        if await self.client.indices.exists(index=self.INDEX_NAME):
            await self.client.indices.delete(index=self.INDEX_NAME)

        # Create new index
        await self.create_index()

        # Bulk index all articles
        count = await self.bulk_index_articles(articles)

        logger.info(f"Reindexed {count} articles")
        return count

    async def close(self):
        """Close Elasticsearch client."""
        await self.client.close()
