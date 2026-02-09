"""RAG Expert: Retrieval-Augmented Generation for data governance.

Capabilities:
- document_search: Semantic search over governance documents
- qa_generation: Question answering with retrieved context
- summarization: Summarize governance policies and decisions
- compliance_check: Check compliance against regulations

EU AI Act Classification: LIMITED risk (AI system that interacts with humans)
Requires: Model Card + Human oversight ("AI recommends, human decides")
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class RAGExpert:
    """RAG Expert with Qdrant vector store and local LLM.

    Architecture:
    1. User query → Embed with SentenceTransformer
    2. Search Qdrant for relevant documents (top-k)
    3. Build context from retrieved documents
    4. Generate answer with LLM (vLLM or Mistral)
    5. Return answer + sources for transparency
    """

    def __init__(
        self,
        qdrant_url: str = "http://qdrant:6333",
        collection_name: str = "governance_docs",
        embedding_model: str = "all-mpnet-base-v2",
        llm_model: str = "mistralai/Mistral-7B-Instruct-v0.2",
        max_context_docs: int = 5,
    ):
        """Initialize RAG Expert.

        Args:
            qdrant_url: Qdrant server URL
            collection_name: Qdrant collection name
            embedding_model: SentenceTransformer model
            llm_model: LLM model for generation
            max_context_docs: Max documents to retrieve
        """
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.max_context_docs = max_context_docs

        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(url=qdrant_url)

        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedder = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedder.get_sentence_embedding_dimension()

        # Initialize LLM (placeholder - in production use vLLM)
        self.llm_model = llm_model
        logger.info(f"LLM model configured: {llm_model}")

        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensure Qdrant collection exists."""
        collections = self.qdrant_client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process expert request (main entry point).

        Args:
            request: Expert request with capability and parameters

        Returns:
            Expert response with recommendation and metadata

        Example:
            >>> response = await expert.process({
            ...     "capability": "qa_generation",
            ...     "query": "What is the data retention policy for PII?",
            ...     "context": {"domain": "privacy"}
            ... })
        """
        capability = request.get("capability")
        query = request.get("query", "")
        context = request.get("context", {})

        logger.info(f"Processing RAG request: capability={capability}")

        if capability == "document_search":
            return await self._search_documents(query, context)
        elif capability == "qa_generation":
            return await self._generate_qa(query, context)
        elif capability == "summarization":
            return await self._summarize(query, context)
        elif capability == "compliance_check":
            return await self._check_compliance(query, context)
        else:
            return {
                "recommendation": f"Unknown capability: {capability}",
                "confidence": 0.0,
                "requires_approval": True,
                "metadata": {"error": "unknown_capability"},
            }

    async def _search_documents(self, query: str, context: dict) -> dict[str, Any]:
        """Search for relevant documents.

        Args:
            query: Search query
            context: Additional context (filters, etc.)

        Returns:
            Search results with sources
        """
        # Embed query
        query_vector = self.embedder.encode(query).tolist()

        # Search Qdrant
        results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=self.max_context_docs,
        )

        # Format results
        documents = []
        for result in results:
            documents.append(
                {
                    "id": result.id,
                    "score": result.score,
                    "text": result.payload.get("text", ""),
                    "metadata": result.payload.get("metadata", {}),
                }
            )

        return {
            "recommendation": f"Found {len(documents)} relevant documents",
            "confidence": 0.9 if documents else 0.1,
            "reasoning": f"Retrieved top {len(documents)} documents by semantic similarity",
            "metadata": {
                "documents": documents,
                "query": query,
            },
            "requires_approval": False,  # Search doesn't need approval
        }

    async def _generate_qa(self, query: str, context: dict) -> dict[str, Any]:
        """Generate answer to question with retrieved context.

        Args:
            query: Question
            context: Additional context

        Returns:
            Answer with sources
        """
        # 1. Retrieve relevant documents
        search_result = await self._search_documents(query, context)
        documents = search_result["metadata"]["documents"]

        if not documents:
            return {
                "recommendation": "No relevant documents found to answer the question.",
                "confidence": 0.1,
                "reasoning": "Insufficient context in knowledge base",
                "metadata": {"query": query},
                "requires_approval": True,
            }

        # 2. Build context from retrieved docs
        retrieved_context = "\n\n".join([f"Document {i + 1}: {doc['text']}" for i, doc in enumerate(documents)])

        # 3. Generate answer with LLM
        # Note: In production, use vLLM or API call to local LLM
        # For now, return a placeholder that shows retrieved context

        prompt = f"""Context from governance documents:
{retrieved_context}

Question: {query}

Based on the context above, provide a clear answer. If the context doesn't contain enough information, say so.

Answer:"""

        # Placeholder response (in production, call vLLM)
        answer = (
            "Based on the retrieved documents, I found relevant information."
            " However, this requires human review before providing a"
            f" definitive answer. Please review the {len(documents)}"
            " source documents."
        )

        return {
            "recommendation": answer,
            "confidence": 0.75,
            "reasoning": f"Retrieved {len(documents)} relevant documents and generated answer",
            "metadata": {
                "sources": documents,
                "query": query,
                "prompt": prompt,
            },
            "requires_approval": True,  # ADR-011: AI recommends, human decides
        }

    async def _summarize(self, query: str, context: dict) -> dict[str, Any]:
        """Summarize documents or policies.

        Args:
            query: Document/topic to summarize
            context: Additional context

        Returns:
            Summary with sources
        """
        # Similar to QA but optimized for summarization
        search_result = await self._search_documents(query, context)
        documents = search_result["metadata"]["documents"]

        summary = (
            f"Found {len(documents)} documents related to '{query}'."
            " Manual review recommended for comprehensive summary."
        )

        return {
            "recommendation": summary,
            "confidence": 0.7,
            "reasoning": "Document retrieval successful, summary requires review",
            "metadata": {"sources": documents, "topic": query},
            "requires_approval": True,
        }

    async def _check_compliance(self, query: str, context: dict) -> dict[str, Any]:
        """Check compliance against regulations.

        Args:
            query: Compliance question
            context: Context (regulation, policy, etc.)

        Returns:
            Compliance assessment
        """
        regulation = context.get("regulation", "GDPR")

        # Search for relevant compliance documents
        search_query = f"{query} {regulation} compliance"
        search_result = await self._search_documents(search_query, context)
        documents = search_result["metadata"]["documents"]

        assessment = (
            f"Compliance check for {regulation} requires review of"
            f" {len(documents)} relevant documents."
            " Manual legal review required."
        )

        return {
            "recommendation": assessment,
            "confidence": 0.6,
            "reasoning": "Compliance decisions require legal expertise",
            "metadata": {
                "regulation": regulation,
                "sources": documents,
                "query": query,
            },
            "requires_approval": True,  # Always require approval for compliance
        }

    def ingest_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Ingest document into vector store.

        Args:
            doc_id: Document ID
            text: Document text
            metadata: Document metadata
        """
        if metadata is None:
            metadata = {}

        # Embed document
        vector = self.embedder.encode(text).tolist()

        # Store in Qdrant
        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload={"text": text, "metadata": metadata},
                )
            ],
        )

        logger.info(f"Ingested document: {doc_id}")
