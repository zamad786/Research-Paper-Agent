"""
Main Research Paper Agent controller.

Phase 7.2 architecture:

AI Intelligence:
    - Groq

Academic Discovery:
    - OpenAlex
    - Crossref
    - Semantic Scholar

Processing:
    - Intelligent multi-source merging
    - Unpaywall access enrichment
    - Journal-ranking verification
    - Strict Q1 / Q2 / HEC W filtering
    - Final result limiting

Email:
    - Professional email preview
    - Human-in-the-loop approval
    - Explicit sending only after approval


PHASE 7.2 AI BEHAVIOR
---------------------

The user can provide a natural-language request such as:

    "Find 8 recent papers about federated learning
    for IoT security from 2024 to 2026."

Groq extracts:

    keyword
    start_year
    end_year
    paper_count

Groq does NOT determine:

    Q1
    Q2
    HEC W

Journal ranking remains controlled entirely by the
RankingService and local ranking datasets.


FINAL PROJECT REQUIREMENT
-------------------------

Only papers with a VERIFIED ranking of:

    - Q1
    - Q2
    - HEC W

are returned.

Q3, Q4, and Not Verified papers may be identified
internally but are removed before final output.

Access is NOT a rejection condition.

Therefore:

    - Free papers are allowed.
    - Open-access papers are allowed.
    - Publisher/institutional-access papers are allowed.
"""

from dataclasses import dataclass
from datetime import datetime

from config import settings
from models import Paper

from services import (
    CrossrefService,
    EmailService,
    GroqService,
    OpenAlexService,
    PaperService,
    RankingService,
    SemanticScholarService,
    UnpaywallService,
)

from utils import (
    validate_categories,
    validate_email,
    validate_keyword,
    validate_paper_count,
    validate_year_range,
)

from utils.logger import get_logger


logger = get_logger(__name__)


# ==========================================================
# SEARCH REQUEST
# ==========================================================


@dataclass(frozen=True)
class SearchRequest:
    """
    Validated research-paper search request.

    Final accepted journal-ranking categories:

    - Q1
    - Q2
    - W
    """

    keyword: str
    start_year: int
    end_year: int
    paper_count: int
    categories: list[str]


# ==========================================================
# MAIN AGENT
# ==========================================================


class ResearchPaperAgent:
    """
    Main controller for the Research Paper Agent.
    """

    TARGET_CATEGORIES = {
        "Q1",
        "Q2",
        "W",
    }

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def __init__(self) -> None:
        """
        Initialize all application services.
        """

        self.settings = settings

        # ==================================================
        # AI INTELLIGENCE
        # ==================================================

        self.groq_service = (
            GroqService(
                settings=self.settings
            )
        )

        # ==================================================
        # DISCOVERY SERVICES
        # ==================================================

        self.openalex_service = (
            OpenAlexService(
                settings=self.settings
            )
        )

        self.crossref_service = (
            CrossrefService(
                settings=self.settings
            )
        )

        self.semantic_scholar_service = (
            SemanticScholarService(
                settings=self.settings
            )
        )

        # ==================================================
        # ENRICHMENT SERVICES
        # ==================================================

        self.unpaywall_service = (
            UnpaywallService(
                settings=self.settings
            )
        )

        self.ranking_service = (
            RankingService()
        )

        # ==================================================
        # PAPER PROCESSING
        # ==================================================

        self.paper_service = (
            PaperService()
        )

        # ==================================================
        # EMAIL
        # ==================================================

        self.email_service = (
            EmailService(
                settings=self.settings
            )
        )

        logger.info(
            "ResearchPaperAgent initialized "
            "in %s mode.",
            self.settings.app_env,
        )

    # ======================================================
    # STANDARD SEARCH REQUEST
    # ======================================================

    def create_search_request(
        self,
        keyword: str,
        start_year: int,
        end_year: int,
        paper_count: int,
        categories: list[str] | None = None,
    ) -> SearchRequest:
        """
        Validate manually supplied search parameters.

        The final application accepts only:
        Q1, Q2 and HEC W.
        """

        # --------------------------------------------------
        # KEYWORD
        # --------------------------------------------------

        valid_keyword = (
            validate_keyword(
                keyword
            )
        )

        # --------------------------------------------------
        # YEARS
        # --------------------------------------------------

        valid_start_year, valid_end_year = (
            validate_year_range(
                start_year,
                end_year,
            )
        )

        # --------------------------------------------------
        # PAPER COUNT
        # --------------------------------------------------

        valid_paper_count = (
            validate_paper_count(
                paper_count
            )
        )

        # --------------------------------------------------
        # FINAL TARGET RANKINGS
        # --------------------------------------------------

        if categories is None:

            categories = [
                "Q1",
                "Q2",
                "W",
            ]

        valid_categories = (
            validate_categories(
                categories
            )
        )

        final_categories = [
            category
            for category in valid_categories
            if category in self.TARGET_CATEGORIES
        ]

        # --------------------------------------------------
        # FALLBACK
        # --------------------------------------------------

        if not final_categories:

            final_categories = [
                "Q1",
                "Q2",
                "W",
            ]

        request = SearchRequest(
            keyword=valid_keyword,
            start_year=valid_start_year,
            end_year=valid_end_year,
            paper_count=valid_paper_count,
            categories=final_categories,
        )

        logger.info(
            "Search request created: "
            "keyword=%s, years=%s-%s, "
            "paper_count=%s, "
            "target_categories=%s",
            request.keyword,
            request.start_year,
            request.end_year,
            request.paper_count,
            request.categories,
        )

        return request

    # ======================================================
    # AI NATURAL-LANGUAGE REQUEST
    # ======================================================

    def create_ai_search_request(
        self,
        user_request: str,
    ) -> SearchRequest:
        """
        Convert a natural-language research request into
        the normal SearchRequest used by the application.

        Example:

            User:
            "Find 10 recent papers about trust-aware
            federated learning for IoT security
            from 2024 to 2026."

        Groq extracts:

            keyword
            start_year
            end_year
            paper_count

        The application then independently adds:

            Q1
            Q2
            W

        Groq NEVER decides journal ranking.
        """

        logger.info(
            "Processing natural-language "
            "research request with Groq."
        )

        # ==================================================
        # GROQ PARSING
        # ==================================================

        parsed_request = (
            self.groq_service.parse_search_request(
                user_request=user_request
            )
        )

        # ==================================================
        # PASS THROUGH NORMAL VALIDATION
        # ==================================================

        request = (
            self.create_search_request(
                keyword=(
                    parsed_request[
                        "keyword"
                    ]
                ),
                start_year=(
                    parsed_request[
                        "start_year"
                    ]
                ),
                end_year=(
                    parsed_request[
                        "end_year"
                    ]
                ),
                paper_count=(
                    parsed_request[
                        "paper_count"
                    ]
                ),
                categories=[
                    "Q1",
                    "Q2",
                    "W",
                ],
            )
        )

        logger.info(
            "AI search request created: "
            "keyword=%s, years=%s-%s, "
            "count=%s.",
            request.keyword,
            request.start_year,
            request.end_year,
            request.paper_count,
        )

        return request

    # ======================================================
    # COMPLETE AI SEARCH
    # ======================================================

    def search_papers_from_ai(
        self,
        user_request: str,
    ) -> tuple[
        SearchRequest,
        list[Paper],
    ]:
        """
        Execute a complete AI-powered search.

        Pipeline:

        Natural-language request
                ↓
              Groq
                ↓
        Structured SearchRequest
                ↓
        AI Query Expansion
                ↓
        Multiple academic search phrases
                ↓
        OpenAlex + Crossref + Semantic Scholar
                ↓
        Merge duplicates
                ↓
             Unpaywall
                ↓
        Ranking verification
                ↓
        STRICT Q1 / Q2 / W
                ↓
           Final papers
        """

        # ==================================================
        # 1. UNDERSTAND USER REQUEST
        # ==================================================

        search_request = (
            self.create_ai_search_request(
                user_request=user_request
            )
        )

        # ==================================================
        # 2. SEARCH WITH AI QUERY EXPANSION
        # ==================================================

        papers = (
            self.search_papers_with_ai_expansion(
                search_request=search_request
            )
        )

        logger.info(
            "Complete AI research search finished: "
            "keyword=%s, returned=%s.",
            search_request.keyword,
            len(papers),
        )

        return (
            search_request,
            papers,
        )

    # ======================================================
    # AI QUERY EXPANSION
    # ======================================================

    def search_papers_with_ai_expansion(
        self,
        search_request: SearchRequest,
    ) -> list[Paper]:
        """
        Expand the user's academic topic using Groq and
        search all generated query variations.

        Groq generates search phrases only.

        It does NOT:
        - verify journals
        - assign Q1
        - assign Q2
        - assign HEC W

        Ranking remains controlled entirely by
        RankingService.
        """

        original_keyword = (
            search_request.keyword
        )

        # ==================================================
        # 1. ASK GROQ FOR SEARCH VARIATIONS
        # ==================================================

        try:

            search_queries = (
                self.groq_service.expand_search_query(
                    keyword=original_keyword
                )
            )

        except Exception as error:

            logger.warning(
                "AI query expansion failed. "
                "Using original keyword only. "
                "Error: %s",
                error,
            )

            search_queries = [
                original_keyword
            ]

        # ==================================================
        # 2. SAFETY FALLBACK
        # ==================================================

        if not search_queries:

            search_queries = [
                original_keyword
            ]

        # ==================================================
        # 3. REMOVE DUPLICATE QUERY VARIATIONS
        # ==================================================

        unique_queries: list[str] = []

        seen_queries: set[str] = set()

        for query in search_queries:

            cleaned_query = (
                str(query).strip()
            )

            if not cleaned_query:

                continue

            normalized_query = (
                cleaned_query.lower()
            )

            if normalized_query in seen_queries:

                continue

            seen_queries.add(
                normalized_query
            )

            unique_queries.append(
                cleaned_query
            )

            # ----------------------------------------------
            # Maximum 3 academic search phrases
            # ----------------------------------------------

            if len(unique_queries) >= 3:

                break

        # ==================================================
        # 4. GUARANTEE ORIGINAL QUERY
        # ==================================================

        if not unique_queries:

            unique_queries = [
                original_keyword
            ]

        logger.info(
            "AI query expansion prepared %s "
            "search phrase(s): %s",
            len(unique_queries),
            unique_queries,
        )

        # ==================================================
        # 5. RUN NORMAL PIPELINE USING ALL QUERIES
        # ==================================================

        return self.search_papers(
            search_request=search_request,
            search_queries=unique_queries,
            use_ai_relevance=True,
        )
    
    # ======================================================
    # SEARCH PAPERS
    # ======================================================

    def search_papers(
        self,
        search_request: SearchRequest,
        search_queries: list[str] | None = None,
        use_ai_relevance: bool = False,
    ) -> list[Paper]:
        """
        Run the multi-source academic-search pipeline.

        Manual search normally supplies one keyword.

        AI search can supply up to three expanded
        academic search phrases.

        All discovered papers are merged before:

        - Unpaywall enrichment
        - Ranking verification
        - Q1/Q2/W filtering

        This prevents expanded searches from creating
        duplicate final papers.
        """

        # ==================================================
        # 1. PREPARE SEARCH QUERIES
        # ==================================================

        if not search_queries:

            search_queries = [
                search_request.keyword
            ]

        cleaned_queries: list[str] = []

        seen_queries: set[str] = set()

        for query in search_queries:

            cleaned_query = (
                str(query).strip()
            )

            if not cleaned_query:

                continue

            normalized = (
                cleaned_query.lower()
            )

            if normalized in seen_queries:

                continue

            seen_queries.add(
                normalized
            )

            cleaned_queries.append(
                cleaned_query
            )

            # ----------------------------------------------
            # Safety limit
            # ----------------------------------------------

            if len(cleaned_queries) >= 3:

                break

        if not cleaned_queries:

            cleaned_queries = [
                search_request.keyword
            ]

        logger.info(
            "Starting academic discovery using "
            "%s search query variation(s).",
            len(cleaned_queries),
        )

        # ==================================================
        # 2. STORAGE FOR ALL DISCOVERED PAPERS
        # ==================================================

        openalex_papers: list[Paper] = []
        crossref_papers: list[Paper] = []
        semantic_scholar_papers: list[Paper] = []

        # ==================================================
        # 3. SEARCH EVERY QUERY
        # ==================================================

        for query_index, query in enumerate(
            cleaned_queries,
            start=1,
        ):

            logger.info(
                "Searching query %s/%s: %s",
                query_index,
                len(cleaned_queries),
                query,
            )

            # ==================================================
            # OPENALEX
            # ==================================================

            try:

                query_openalex = (
                    self.openalex_service.search_papers(
                        keyword=query,
                        start_year=(
                            search_request.start_year
                        ),
                        end_year=(
                            search_request.end_year
                        ),
                        paper_count=(
                            search_request.paper_count
                        ),
                    )
                )

                openalex_papers.extend(
                    query_openalex
                )

                logger.info(
                    "OpenAlex returned %s paper(s) "
                    "for query: %s",
                    len(query_openalex),
                    query,
                )

            except Exception as error:

                logger.warning(
                    "OpenAlex failed for query "
                    "'%s': %s",
                    query,
                    error,
                )

            # ==================================================
            # CROSSREF
            # ==================================================

            try:

                query_crossref = (
                    self.crossref_service.search_papers(
                        keyword=query,
                        start_year=(
                            search_request.start_year
                        ),
                        end_year=(
                            search_request.end_year
                        ),
                        paper_count=(
                            search_request.paper_count
                        ),
                    )
                )

                crossref_papers.extend(
                    query_crossref
                )

                logger.info(
                    "Crossref returned %s paper(s) "
                    "for query: %s",
                    len(query_crossref),
                    query,
                )

            except Exception as error:

                logger.warning(
                    "Crossref failed for query "
                    "'%s': %s",
                    query,
                    error,
                )

            # ==================================================
            # SEMANTIC SCHOLAR
            # ==================================================

            try:

                query_semantic = (
                    self.semantic_scholar_service.search_papers(
                        keyword=query,
                        start_year=(
                            search_request.start_year
                        ),
                        end_year=(
                            search_request.end_year
                        ),
                        paper_count=(
                            search_request.paper_count
                        ),
                    )
                )

                semantic_scholar_papers.extend(
                    query_semantic
                )

                logger.info(
                    "Semantic Scholar returned "
                    "%s paper(s) for query: %s",
                    len(query_semantic),
                    query,
                )

            except Exception as error:

                logger.warning(
                    "Semantic Scholar failed for query "
                    "'%s': %s",
                    query,
                    error,
                )

        # ==================================================
        # 4. COMBINE ALL DISCOVERY SOURCES
        # ==================================================

        discovered_papers = (
            openalex_papers
            + crossref_papers
            + semantic_scholar_papers
        )

        logger.info(
            "Expanded discovery totals: "
            "queries=%s, OpenAlex=%s, "
            "Crossref=%s, SemanticScholar=%s, "
            "combined=%s.",
            len(cleaned_queries),
            len(openalex_papers),
            len(crossref_papers),
            len(semantic_scholar_papers),
            len(discovered_papers),
        )

        if not discovered_papers:

            logger.info(
                "No academic source returned papers."
            )

            return []

        # ==================================================
        # 5. MERGE DUPLICATE PAPERS
        # ==================================================

        merged_discovery_papers = (
            self.paper_service.merge_duplicate_papers(
                discovered_papers
            )
        )

        logger.info(
            "Multi-query merge completed: "
            "raw=%s, unique=%s.",
            len(discovered_papers),
            len(merged_discovery_papers),
        )

        # ==================================================
        # 6. PREPARE CANDIDATES
        # ==================================================

        candidate_papers = (
            self.paper_service.prepare_candidates(
                papers=(
                    merged_discovery_papers
                ),
                start_year=(
                    search_request.start_year
                ),
                end_year=(
                    search_request.end_year
                ),
            )
        )

        logger.info(
            "Usable candidates after preparation: %s.",
            len(candidate_papers),
        )

        if not candidate_papers:

            return []

        # ==================================================
        # 7. UNPAYWALL ACCESS ENRICHMENT
        #
        # IMPORTANT:
        #
        # Access is informational only.
        #
        # We use required_count=None because query expansion
        # can discover many candidates and we do not want
        # access enrichment to accidentally reduce the
        # candidate pool before ranking verification.
        # ==================================================

        try:

            enriched_papers = (
                self.unpaywall_service.verify_papers(
                    papers=candidate_papers,
                    required_count=None,
                )
            )

        except Exception as error:

            logger.warning(
                "Unpaywall enrichment failed. "
                "Keeping original candidates. "
                "Error: %s",
                error,
            )

            enriched_papers = (
                candidate_papers
            )

        # ==================================================
        # 8. PRE-RANKING CLEANUP
        # ==================================================

        ranking_candidates = (
            self.paper_service.prepare_verified_candidates(
                papers=enriched_papers
            )
        )

        logger.info(
            "Ranking candidates: %s.",
            len(ranking_candidates),
        )

        if not ranking_candidates:

            return []

        # ==================================================
        # 9. RANKING VERIFICATION
        #
        # RankingService may internally identify:
        #
        # Q1
        # Q2
        # Q3
        # Q4
        # W
        # Not Verified
        #
        # It classifies first.
        # The agent filters afterward.
        # ==================================================

        try:

            ranked_papers = (
                self.ranking_service.verify_papers(
                    papers=ranking_candidates,
                    allowed_categories=[
                        "Q1",
                        "Q2",
                        "W",
                    ],
                    paper_count=None,
                )
            )

        except Exception as error:

            logger.warning(
                "Ranking verification failed: %s",
                error,
            )

            # ----------------------------------------------
            # Ranking is mandatory for final output.
            # ----------------------------------------------

            return []

        # ==================================================
        # 10. STRICT Q1 / Q2 / W FILTER
        # ==================================================

        target_ranked_papers = (
            self._filter_target_rankings(
                ranked_papers
            )
        )

        logger.info(
            "Strict ranking filter: "
            "ranked=%s, accepted_Q1_Q2_W=%s.",
            len(ranked_papers),
            len(target_ranked_papers),
        )

        if not target_ranked_papers:

            logger.info(
                "No verified Q1, Q2 or HEC W "
                "papers were found."
            )

            return []

        # ==================================================
        # 11. FINAL DUPLICATE REMOVAL
        # ==================================================

        final_candidates = (
            self.paper_service.remove_duplicate_papers(
                target_ranked_papers
            )
        )

        logger.info(
            "Final verified candidate pool "
            "before relevance ordering: %s.",
            len(final_candidates),
        )

        # ==================================================
        # 12. AI RELEVANCE ORDERING
        #
        # IMPORTANT:
        #
        # This happens ONLY AFTER:
        #
        # - academic discovery
        # - duplicate merging
        # - access enrichment
        # - ranking verification
        # - strict Q1/Q2/W filtering
        #
        # Therefore Groq cannot introduce an
        # unverified journal into final results.
        # ==================================================

        if (
            use_ai_relevance
            and len(final_candidates) > 1
        ):

            logger.info(
                "Applying Groq relevance ordering "
                "to %s verified Q1/Q2/W candidate(s).",
                len(final_candidates),
            )

            try:

                final_candidates = (
                    self.groq_service.rank_papers_by_relevance(
                        keyword=(
                            search_request.keyword
                        ),
                        papers=(
                            final_candidates
                        ),
                    )
                )

            except Exception as error:

                logger.warning(
                    "AI relevance ordering failed. "
                    "Keeping existing paper order. "
                    "Error: %s",
                    error,
                )

        else:

            logger.info(
                "AI relevance ordering not required."
            )

        # ==================================================
        # 13. FINAL PAPER LIMIT
        #
        # IMPORTANT:
        #
        # Relevance ordering happens BEFORE the final
        # requested-count limit.
        #
        # Example:
        #
        # 18 verified candidates
        #       ↓
        # AI relevance ordering
        #       ↓
        # user requested 5
        #       ↓
        # return top 5 relevant verified papers
        # ==================================================

        final_papers = (
            self.paper_service.limit_papers(
                papers=(
                    final_candidates
                ),
                paper_count=(
                    search_request.paper_count
                ),
            )
        )

        logger.info(
            "Final search completed: "
            "queries=%s, AI_relevance=%s, "
            "requested=%s, returned=%s.",
            len(cleaned_queries),
            use_ai_relevance,
            search_request.paper_count,
            len(final_papers),
        )

        return final_papers

    # ======================================================
    # STRICT RANKING FILTER
    # ======================================================

    def _filter_target_rankings(
        self,
        papers: list[Paper],
    ) -> list[Paper]:
        """
        Keep ONLY ranking-verified papers belonging to:

        - Q1
        - Q2
        - W

        Q3, Q4 and Not Verified are excluded.
        """

        filtered: list[Paper] = []

        for paper in papers:

            # ----------------------------------------------
            # Ranking verification is mandatory.
            # ----------------------------------------------

            if not paper.ranking_verified:

                continue

            paper_categories = set(
                paper.verified_categories
                or []
            )

            if (
                paper.category
                and paper.category
                != "Not Verified"
            ):

                paper_categories.add(
                    paper.category
                )

            # ----------------------------------------------
            # At least one verified category must match
            # our final project requirement.
            # ----------------------------------------------

            if paper_categories.intersection(
                self.TARGET_CATEGORIES
            ):

                filtered.append(
                    paper
                )

        return filtered

    # ======================================================
    # EMAIL PREVIEW
    # ======================================================

    def create_email_preview(
        self,
        recipient: str,
        papers: list[Paper],
        keyword: str,
        start_year: int | None = None,
        end_year: int | None = None,
        categories: list[str] | None = None,
    ) -> dict[str, str]:
        """
        Prepare a human-reviewed email preview.

        Only final verified Q1/Q2/W papers should
        reach this stage.
        """

        valid_recipient = (
            validate_email(
                recipient
            )
        )

        if not papers:

            raise ValueError(
                "There are no verified Q1, Q2, "
                "or W research papers available "
                "for email."
            )

        cleaned_keyword = (
            validate_keyword(
                keyword
            )
        )

        preview = (
            self.email_service.create_email_preview(
                recipient=(
                    valid_recipient
                ),
                papers=(
                    papers
                ),
                keyword=(
                    cleaned_keyword
                ),
                start_year=(
                    start_year
                ),
                end_year=(
                    end_year
                ),
                categories=[
                    "Q1",
                    "Q2",
                    "W",
                ],
            )
        )

        logger.info(
            "Email preview prepared for %s.",
            valid_recipient,
        )

        return preview

    # ======================================================
    # SEND EMAIL
    # ======================================================

    def send_email(
        self,
        preview: dict[str, str],
        approved: bool,
    ) -> None:
        """
        Send only after explicit human approval.
        """

        logger.info(
            "Email send requested. Approval=%s.",
            approved,
        )

        self.email_service.send_approved_email(
            preview=(
                preview
            ),
            approved=(
                approved
            ),
        )

    # ======================================================
    # PAPER LINKS
    # ======================================================

    @staticmethod
    def build_paper_links(
        papers: list[Paper],
    ) -> list[str]:
        """
        Build unique preferred paper links.
        """

        links: list[str] = []

        for paper in papers:

            link = (
                paper.preferred_link()
            )

            if not link:

                continue

            if link in links:

                continue

            links.append(
                link
            )

        return links

    # ======================================================
    # HEALTH CHECK
    # ======================================================

    def health_check(
        self,
    ) -> dict[str, str]:
        """
        Return application and service status.
        """

        current_year = (
            datetime.now().year
        )

        status: dict[
            str,
            str,
        ] = {
            # ==============================================
            # APPLICATION
            # ==============================================

            "application": (
                self.settings.app_name
            ),

            "environment": (
                self.settings.app_env
            ),

            "current_year": (
                str(
                    current_year
                )
            ),

            "target_rankings": (
                "Q1, Q2, W"
            ),

            # ==============================================
            # GROQ
            # ==============================================

            "groq_service": (
                "Configured"
                if self.groq_service.is_configured()
                else "Missing API Key"
            ),

            "groq_model": (
                self.settings.groq_model
            ),

            # ==============================================
            # OPENALEX
            # ==============================================

            "openalex_service": (
                "Connected"
            ),

            "openalex_api_key": (
                "Configured"
                if (
                    self.settings.openalex_api_key
                )
                else "Missing"
            ),

            # ==============================================
            # CROSSREF
            # ==============================================

            "crossref_service": (
                "Connected"
            ),

            # ==============================================
            # SEMANTIC SCHOLAR
            # ==============================================

            "semantic_scholar_service": (
                "Connected"
            ),

            "semantic_scholar_api_key": (
                "Configured"
                if (
                    self.settings.semantic_scholar_api_key
                )
                else (
                    "Optional / Not configured"
                )
            ),

            # ==============================================
            # UNPAYWALL
            # ==============================================

            "unpaywall_service": (
                "Connected"
            ),

            "unpaywall_email": (
                "Configured"
                if (
                    self.settings.unpaywall_email
                )
                else "Missing"
            ),

            # ==============================================
            # EMAIL
            # ==============================================

            "email_sender": (
                "Configured"
                if (
                    self.settings.sender_email
                    and
                    self.settings.sender_app_password
                )
                else "Missing"
            ),
        }

        # ==================================================
        # RANKING DATA STATUS
        # ==================================================

        try:

            ranking_status = (
                self.ranking_service.health_status()
            )

            status.update(
                ranking_status
            )

        except Exception as error:

            logger.warning(
                "Ranking health check failed: %s",
                error,
            )

            status[
                "ranking_service"
            ] = (
                "Unavailable"
            )

        return status