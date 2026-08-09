"""
External service integrations for the
Research Paper Agent.
"""

from services.crossref_service import (
    CrossrefService,
    CrossrefServiceError,
)

from services.email_service import (
    EmailService,
    EmailServiceError,
)

from services.groq_service import (
    GroqService,
    GroqServiceError,
)

from services.openalex_service import (
    OpenAlexService,
    OpenAlexServiceError,
)

from services.paper_service import (
    PaperService,
)

from services.ranking_service import (
    RankingService,
    RankingServiceError,
)

from services.semantic_scholar_service import (
    SemanticScholarService,
    SemanticScholarServiceError,
)

from services.unpaywall_service import (
    UnpaywallService,
    UnpaywallServiceError,
)


__all__ = [
    "CrossrefService",
    "CrossrefServiceError",
    "EmailService",
    "EmailServiceError",
    "GroqService",
    "GroqServiceError",
    "OpenAlexService",
    "OpenAlexServiceError",
    "PaperService",
    "RankingService",
    "RankingServiceError",
    "SemanticScholarService",
    "SemanticScholarServiceError",
    "UnpaywallService",
    "UnpaywallServiceError",
]