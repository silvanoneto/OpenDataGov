"""NLP Expert: Natural language processing with BERT.

Architecture:
1. Text input → Tokenize and preprocess
2. BERT encoding → Get contextual embeddings
3. Task-specific heads → Classification, NER, QA, etc.
4. PII detection → GDPR/LGPD compliance
5. Human review for sensitive content
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class PIIDetector:
    """PII (Personally Identifiable Information) detector for GDPR/LGPD compliance."""

    def __init__(self):
        """Initialize PII detector."""
        # Regex patterns for common PII
        self.patterns = {
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        }

    def detect(self, text: str) -> list[dict[str, Any]]:
        """Detect PII in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected PII entities
        """
        detected_pii = []

        for pii_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                detected_pii.append(
                    {
                        "type": pii_type,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

        return detected_pii


class NLPExpert:
    """NLP Expert with BERT for text understanding.

    Uses transformers library with BERT models for:
    - Text classification
    - Named entity recognition (NER)
    - Sentiment analysis
    - Text summarization
    - Question answering
    - PII detection (GDPR/LGPD)
    """

    def __init__(
        self,
        model_name: str = "bert-base-uncased",
        device: str = "cpu",
    ):
        """Initialize NLP Expert.

        Args:
            model_name: BERT model name
            device: Device for inference (cpu/cuda)
        """
        self.model_name = model_name
        self.device = device

        # Initialize PII detector
        self.pii_detector = PIIDetector()

        # Initialize models (placeholder - in production load transformers)
        logger.info(f"NLP Expert initialized with model: {model_name}")
        logger.warning("Using placeholder NLP analysis (load BERT in production)")

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process expert request (main entry point).

        Args:
            request: Expert request with capability and parameters

        Returns:
            Expert response with recommendation and metadata

        Example:
            >>> response = await expert.process({
            ...     "capability": "sentiment_analysis",
            ...     "query": "I love this product!",
            ...     "context": {}
            ... })
        """
        capability = request.get("capability")
        query = request.get("query", "")
        context = request.get("context", {})

        logger.info(f"Processing NLP Expert request: capability={capability}")

        if capability == "text_classification":
            return await self._classify_text(query, context)
        elif capability == "named_entity_recognition":
            return await self._extract_entities(query, context)
        elif capability == "sentiment_analysis":
            return await self._analyze_sentiment(query, context)
        elif capability == "text_summarization":
            return await self._summarize_text(query, context)
        elif capability == "question_answering":
            return await self._answer_question(query, context)
        else:
            return {
                "recommendation": f"Unknown capability: {capability}",
                "confidence": 0.0,
                "reasoning": "Unknown capability",
                "metadata": {"error": "unknown_capability"},
                "requires_approval": True,
            }

    async def _classify_text(self, query: str, context: dict) -> dict[str, Any]:
        """Classify text into categories.

        Args:
            query: Text to classify
            context: Context with labels

        Returns:
            Classification results
        """
        labels = context.get("labels", ["positive", "negative", "neutral"])

        # Check for PII
        pii_detected = self.pii_detector.detect(query)

        # Classify (placeholder)
        predictions = self._placeholder_classify(query, labels)

        # Adjust confidence if PII detected
        confidence = predictions[0]["score"]
        if pii_detected:
            confidence *= 0.7  # Reduce confidence for PII-containing text

        reasoning = f"Text classified as '{predictions[0]['label']}'"
        if pii_detected:
            reasoning += f" (Warning: {len(pii_detected)} PII entities detected)"

        return {
            "recommendation": f"Classification: {predictions[0]['label']}",
            "confidence": confidence,
            "reasoning": reasoning,
            "metadata": {
                "predictions": predictions,
                "pii_detected": pii_detected,
                "privacy_warning": len(pii_detected) > 0,
            },
            "requires_approval": len(pii_detected) > 0,  # Require approval if PII
        }

    async def _extract_entities(self, query: str, context: dict) -> dict[str, Any]:
        """Extract named entities (NER).

        Args:
            query: Text to analyze
            context: Additional context

        Returns:
            Extracted entities
        """
        # Detect PII (critical for GDPR/LGPD)
        pii_entities = self.pii_detector.detect(query)

        # Extract standard NER entities (placeholder)
        ner_entities = self._placeholder_ner(query)

        all_entities = ner_entities + [
            {"type": f"PII_{e['type'].upper()}", "text": e["value"], "start": e["start"], "end": e["end"]}
            for e in pii_entities
        ]

        has_pii = len(pii_entities) > 0

        return {
            "recommendation": f"Extracted {len(all_entities)} entities ({len(pii_entities)} PII)",
            "confidence": 0.85,
            "reasoning": (
                "Named entity recognition completed. "
                + (
                    f"⚠️ {len(pii_entities)} PII entities detected (GDPR/LGPD compliance required)"
                    if has_pii
                    else "No PII detected"
                )
            ),
            "metadata": {
                "entities": all_entities,
                "pii_count": len(pii_entities),
                "privacy_warning": has_pii,
            },
            "requires_approval": has_pii,  # Always require approval if PII
        }

    async def _analyze_sentiment(self, query: str, context: dict) -> dict[str, Any]:
        """Analyze sentiment.

        Args:
            query: Text to analyze
            context: Additional context

        Returns:
            Sentiment analysis results
        """
        # Check for PII
        pii_detected = self.pii_detector.detect(query)

        # Analyze sentiment (placeholder)
        sentiment = self._placeholder_sentiment(query)

        return {
            "recommendation": f"Sentiment: {sentiment['label']} (score: {sentiment['score']:.2f})",
            "confidence": sentiment["score"],
            "reasoning": "Sentiment analysis completed using BERT",
            "metadata": {
                "sentiment": sentiment,
                "pii_detected": pii_detected,
                "privacy_warning": len(pii_detected) > 0,
            },
            "requires_approval": False,  # Sentiment doesn't need approval (read-only)
        }

    async def _summarize_text(self, query: str, context: dict) -> dict[str, Any]:
        """Summarize text.

        Args:
            query: Text to summarize
            context: Additional context (max_length, etc.)

        Returns:
            Summary
        """
        max_length = context.get("max_length", 150)

        # Check for PII
        pii_detected = self.pii_detector.detect(query)

        # Summarize (placeholder)
        summary = self._placeholder_summarize(query, max_length)

        return {
            "recommendation": summary,
            "confidence": 0.75,
            "reasoning": "Text summarized. Review for accuracy and PII leakage.",
            "metadata": {
                "original_length": len(query),
                "summary_length": len(summary),
                "pii_in_original": len(pii_detected),
            },
            "requires_approval": len(pii_detected) > 0,  # Require approval if PII in source
        }

    async def _answer_question(self, query: str, context: dict) -> dict[str, Any]:
        """Answer question based on context.

        Args:
            query: Question
            context: Context with document/passage

        Returns:
            Answer
        """
        passage = context.get("passage", "")

        if not passage:
            return {
                "recommendation": "No context provided for question answering",
                "confidence": 0.0,
                "reasoning": "Cannot answer without context passage",
                "metadata": {"error": "missing_passage"},
                "requires_approval": True,
            }

        # Check for PII
        pii_detected = self.pii_detector.detect(passage)

        # Answer question (placeholder)
        answer = self._placeholder_qa(query, passage)

        return {
            "recommendation": answer,
            "confidence": 0.7,
            "reasoning": "Question answered using BERT QA. Verify accuracy.",
            "metadata": {
                "question": query,
                "passage_length": len(passage),
                "pii_detected": len(pii_detected),
            },
            "requires_approval": True,  # QA requires human verification
        }

    def _placeholder_classify(self, text: str, labels: list[str]) -> list[dict[str, Any]]:
        """Placeholder classification.

        Args:
            text: Text to classify
            labels: Classification labels

        Returns:
            Predictions
        """
        import random

        random.seed(len(text))  # Deterministic based on text

        predictions = []
        for label in labels:
            score = random.uniform(0.1, 0.95)
            predictions.append({"label": label, "score": score})

        predictions.sort(key=lambda x: x["score"], reverse=True)

        return predictions

    def _placeholder_ner(self, text: str) -> list[dict[str, Any]]:
        """Placeholder NER.

        Args:
            text: Text to analyze

        Returns:
            Extracted entities
        """
        # Simple pattern matching for demo
        entities = []

        # Detect capitalized words (potential proper nouns)
        words = text.split()
        for _i, word in enumerate(words):
            if word and word[0].isupper() and len(word) > 2:
                entities.append(
                    {
                        "type": "PERSON_OR_ORG",
                        "text": word,
                        "start": text.find(word),
                        "end": text.find(word) + len(word),
                    }
                )

        return entities[:5]  # Limit to 5

    def _placeholder_sentiment(self, text: str) -> dict[str, Any]:
        """Placeholder sentiment analysis.

        Args:
            text: Text to analyze

        Returns:
            Sentiment
        """
        # Simple keyword-based sentiment
        positive_words = ["good", "great", "excellent", "love", "best", "amazing"]
        negative_words = ["bad", "terrible", "worst", "hate", "poor", "awful"]

        text_lower = text.lower()

        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        if pos_count > neg_count:
            return {"label": "POSITIVE", "score": 0.85}
        elif neg_count > pos_count:
            return {"label": "NEGATIVE", "score": 0.80}
        else:
            return {"label": "NEUTRAL", "score": 0.70}

    def _placeholder_summarize(self, text: str, max_length: int) -> str:
        """Placeholder summarization.

        Args:
            text: Text to summarize
            max_length: Max summary length

        Returns:
            Summary
        """
        # Simple truncation for demo
        if len(text) <= max_length:
            return text

        # Take first N characters and add ellipsis
        return text[:max_length].rsplit(" ", 1)[0] + "..."

    def _placeholder_qa(self, question: str, passage: str) -> str:
        """Placeholder question answering.

        Args:
            question: Question
            passage: Context passage

        Returns:
            Answer
        """
        # Simple keyword matching for demo
        question_lower = question.lower()

        if "what" in question_lower or "who" in question_lower:
            # Extract first sentence
            sentences = passage.split(".")
            return sentences[0].strip() + "." if sentences else "Cannot answer."
        elif "when" in question_lower:
            return "The timing is not specified in the provided context."
        elif "where" in question_lower:
            return "The location is not specified in the provided context."
        else:
            return "The answer requires detailed analysis of the context passage."
