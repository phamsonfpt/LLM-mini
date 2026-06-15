"""
Scope Resolution Router â€” Táº§ng Truy xuáº¥t
Analyzes query intent to route to the correct retrieval strategy:
- Query-based â†’ HybridSearch (semantic + keyword)
- Full file/card processing â†’ Scroll All Chunks (Qdrant_Scroll)
"""
import logging
from typing import Optional, Literal
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ScopeType = Literal["query", "scroll"]


@dataclass
class ScopeDecision:
    """Result of scope resolution."""
    scope_type: ScopeType
    query: Optional[str] = None
    filters: Optional[dict] = None
    reason: str = ""


class ScopeRouter:
    """
    PhÃ¢n tÃ­ch Query Ä‘á»ƒ quyáº¿t Ä‘á»‹nh luá»“ng truy xuáº¥t.
    - Náº¿u cÃ³ query text â†’ HybridSearch (luá»“ng tÃ¬m kiáº¿m)
    - Náº¿u xá»­ lÃ½ toÃ n file/tháº» (summarize, quiz, flashcard toÃ n bá»™) â†’ Scroll All Chunks
    """

    def resolve(
        self,
        query: Optional[str] = None,
        document: Optional[str] = None,
        filters: Optional[dict] = None,
        operation: Optional[str] = None,
    ) -> ScopeDecision:
        """
        Determine the retrieval scope.

        Args:
            query: User's search query (if any)
            document: Specific document filename filter
            filters: Additional metadata filters
            operation: Type of operation ('ask', 'summarize', 'quiz', 'flashcard')
        """
        effective_filters = dict(filters or {})
        if document:
            effective_filters["filename"] = document

        # If there's a query â†’ use hybrid search
        if query and query.strip():
            logger.info("Scope: QUERY â†’ HybridSearch for '%s'", query[:60])
            return ScopeDecision(
                scope_type="query",
                query=query,
                filters=effective_filters or None,
                reason=f"Query detected: '{query[:40]}...'",
            )

        # No query â†’ scroll all chunks (for summarize, quiz, flashcard over entire doc/corpus)
        logger.info("Scope: SCROLL â†’ Full document/corpus retrieval")
        return ScopeDecision(
            scope_type="scroll",
            query=None,
            filters=effective_filters or None,
            reason="No query â€” scrolling all chunks for full-document operation.",
        )


# Module-level singleton
_router: Optional[ScopeRouter] = None


def get_router() -> ScopeRouter:
    global _router
    if _router is None:
        _router = ScopeRouter()
    return _router
