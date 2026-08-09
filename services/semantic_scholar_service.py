"""
Semantic Scholar academic-search service.

Phase 6.5.6

This service searches the Semantic Scholar Academic
Graph API and converts results into the common Paper model.

Semantic Scholar is an ADDITIONAL discovery source.

Important behavior:
- Free and paid papers are kept.
- Papers without DOI are kept.
- Papers without ranking information are kept.
- Semantic Scholar open-access PDFs may be recorded.
- Unpaywall can later perform additional OA enrichment.
"""

from typing import Any

import requests

from config import Settings
from models import Paper
from utils.helpers import (
    clean_doi,
    remove_duplicates,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class SemanticScholarServiceError(Exception):
    """
    Raised when Semantic Scholar cannot complete
    a search request.
    """


class SemanticScholarService:
    """
    Search scholarly works through the Semantic Scholar
    Academic Graph API.
    """

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        """
        Initialize Semantic Scholar.
        """

        self.settings = settings

        self.base_url = (
            "https://api.semanticscholar.org/graph/v1"
        )

        self.search_url = (
            f"{self.base_url}/paper/search"
        )

        self.session = (
            requests.Session()
        )

        headers = {
            "Accept": "application/json",
            "User-Agent": (
                f"{self.settings.app_name}/1.0"
            ),
        }

        # --------------------------------------------------
        # API KEY IS OPTIONAL
        # --------------------------------------------------

        if (
            self.settings.semantic_scholar_api_key
        ):

            headers["x-api-key"] = (
                self.settings.semantic_scholar_api_key
            )

        self.session.headers.update(
            headers
        )

    # ======================================================
    # SEARCH PAPERS
    # ======================================================

    def search_papers(
        self,
        keyword: str,
        start_year: int,
        end_year: int,
        paper_count: int,
    ) -> list[Paper]:
        """
        Search Semantic Scholar for research papers.

        This search is not restricted to open access.

        Args:
            keyword:
                User-entered research topic.

            start_year:
                First publication year.

            end_year:
                Last publication year.

            paper_count:
                Number requested by the user.

        Returns:
            List of normalized Paper objects.
        """

        fetch_count = min(
            max(
                paper_count * 5,
                20,
            ),
            100,
        )

        # --------------------------------------------------
        # FIELDS
        # --------------------------------------------------

        fields = ",".join(
            [
                "paperId",
                "title",
                "url",
                "year",
                "authors",
                "venue",
                "externalIds",
                "openAccessPdf",
                "citationCount",
                "publicationDate",
                "publicationTypes",
            ]
        )

        # --------------------------------------------------
        # YEAR RANGE
        #
        # Semantic Scholar supports ranges such as:
        # 2023-2026
        # --------------------------------------------------

        year_filter = (
            f"{start_year}-{end_year}"
        )

        params = {
            "query": keyword,
            "limit": fetch_count,
            "fields": fields,
            "year": year_filter,
        }

        logger.info(
            "Searching Semantic Scholar: "
            "keyword=%s, years=%s-%s, "
            "requested=%s, fetch=%s",
            keyword,
            start_year,
            end_year,
            paper_count,
            fetch_count,
        )

        # --------------------------------------------------
        # REQUEST
        # --------------------------------------------------

        try:

            response = (
                self.session.get(
                    self.search_url,
                    params=params,
                    timeout=(
                        self.settings.request_timeout
                    ),
                )
            )

            response.raise_for_status()

        except requests.Timeout as error:

            logger.warning(
                "Semantic Scholar request timed out."
            )

            raise SemanticScholarServiceError(
                "The Semantic Scholar request timed out."
            ) from error

        except requests.ConnectionError as error:

            logger.warning(
                "Could not connect to Semantic Scholar."
            )

            raise SemanticScholarServiceError(
                "The application could not connect "
                "to Semantic Scholar."
            ) from error

        except requests.HTTPError as error:

            status_code = (
                error.response.status_code
                if error.response is not None
                else "unknown"
            )

            logger.warning(
                "Semantic Scholar returned HTTP %s.",
                status_code,
            )

            if status_code == 401:

                message = (
                    "Semantic Scholar rejected the API key."
                )

            elif status_code == 403:

                message = (
                    "Semantic Scholar denied the request."
                )

            elif status_code == 429:

                message = (
                    "Semantic Scholar rate limit reached. "
                    "The other academic search sources "
                    "can still continue."
                )

            else:

                message = (
                    "Semantic Scholar returned an error. "
                    f"HTTP status: {status_code}."
                )

            raise SemanticScholarServiceError(
                message
            ) from error

        except requests.RequestException as error:

            logger.warning(
                "Unexpected Semantic Scholar "
                "request error: %s",
                error,
            )

            raise SemanticScholarServiceError(
                "An unexpected network error occurred "
                "while searching Semantic Scholar."
            ) from error

        # --------------------------------------------------
        # JSON
        # --------------------------------------------------

        try:

            payload = (
                response.json()
            )

        except ValueError as error:

            raise SemanticScholarServiceError(
                "Semantic Scholar returned "
                "an unreadable response."
            ) from error

        raw_results = (
            payload.get(
                "data"
            )
            or []
        )

        papers: list[Paper] = []

        # --------------------------------------------------
        # CONVERT RESULTS
        # --------------------------------------------------

        for item in raw_results:

            paper = (
                self._convert_item_to_paper(
                    item
                )
            )

            if paper is not None:

                papers.append(
                    paper
                )

        logger.info(
            "Semantic Scholar returned %s raw "
            "records and %s usable papers.",
            len(raw_results),
            len(papers),
        )

        return papers

    # ======================================================
    # CONVERT RESULT
    # ======================================================

    def _convert_item_to_paper(
        self,
        item: dict[str, Any],
    ) -> Paper | None:
        """
        Convert Semantic Scholar metadata into Paper.
        """

        # --------------------------------------------------
        # TITLE
        # --------------------------------------------------

        title = str(
            item.get(
                "title"
            )
            or ""
        ).strip()

        if not title:

            return None

        # --------------------------------------------------
        # YEAR
        # --------------------------------------------------

        year = (
            item.get(
                "year"
            )
        )

        if not isinstance(
            year,
            int,
        ):

            return None

        # --------------------------------------------------
        # AUTHORS
        # --------------------------------------------------

        authors = (
            self._extract_authors(
                item
            )
        )

        # --------------------------------------------------
        # VENUE
        # --------------------------------------------------

        venue = str(
            item.get(
                "venue"
            )
            or ""
        ).strip()

        journal_name = (
            venue
            or None
        )

        # --------------------------------------------------
        # EXTERNAL IDS
        # --------------------------------------------------

        external_ids = (
            item.get(
                "externalIds"
            )
            or {}
        )

        doi = (
            clean_doi(
                external_ids.get(
                    "DOI"
                )
            )
        )

        # --------------------------------------------------
        # NOTE ABOUT ISSN
        #
        # Semantic Scholar's normal paper search result
        # does not reliably supply journal ISSNs.
        #
        # OpenAlex/Crossref can provide ISSN during
        # multi-source merging.
        # --------------------------------------------------

        issns: list[str] = []

        # --------------------------------------------------
        # SEMANTIC SCHOLAR PAGE
        # --------------------------------------------------

        source_url = (
            self._first_valid_url(
                item.get(
                    "url"
                )
            )
        )

        # --------------------------------------------------
        # DOI / PUBLISHER PAGE
        # --------------------------------------------------

        doi_url = (
            f"https://doi.org/{doi}"
            if doi
            else None
        )

        paper_url = (
            self._first_valid_url(
                doi_url,
                source_url,
            )
        )

        # --------------------------------------------------
        # OPEN ACCESS PDF
        # --------------------------------------------------

        open_access_pdf = (
            item.get(
                "openAccessPdf"
            )
            or {}
        )

        pdf_url = (
            self._first_valid_url(
                open_access_pdf.get(
                    "url"
                )
            )
        )

        # --------------------------------------------------
        # OA STATUS
        #
        # Semantic Scholar's openAccessPdf field indicates
        # that an OA PDF has been supplied.
        # --------------------------------------------------

        is_open_access = bool(
            pdf_url
        )

        # --------------------------------------------------
        # ACCESS TYPE
        # --------------------------------------------------

        if pdf_url:

            access_type = (
                "Free PDF"
            )

        elif paper_url or source_url:

            access_type = (
                "Publisher / Institutional Access"
            )

        else:

            access_type = (
                "Access Unknown"
            )

        # --------------------------------------------------
        # REQUIRE SOME USABLE LINK
        # --------------------------------------------------

        if (
            not pdf_url
            and not paper_url
            and not source_url
        ):

            return None

        # --------------------------------------------------
        # CITATIONS
        # --------------------------------------------------

        citation_count = (
            item.get(
                "citationCount"
            )
        )

        if not isinstance(
            citation_count,
            int,
        ):

            citation_count = None

        # --------------------------------------------------
        # CREATE PAPER
        # --------------------------------------------------

        try:

            return Paper(
                # ==========================================
                # BASIC INFORMATION
                # ==========================================

                title=title,

                authors=authors,

                year=year,

                journal=journal_name,

                # ==========================================
                # IDENTIFIERS
                # ==========================================

                doi=doi,

                issns=issns,

                # ==========================================
                # RANKING
                # ==========================================

                category=None,

                verified_categories=[],

                ranking_source=None,

                ranking_year=None,

                ranking_verified=False,

                # ==========================================
                # LINKS
                # ==========================================

                paper_url=paper_url,

                pdf_url=pdf_url,

                source_url=source_url,

                # ==========================================
                # ACCESS
                # ==========================================

                is_open_access=(
                    is_open_access
                ),

                verified_by_unpaywall=False,

                oa_status=(
                    "open"
                    if is_open_access
                    else None
                ),

                oa_host_type=None,

                access_type=(
                    access_type
                ),

                # ==========================================
                # DISCOVERY SOURCE
                # ==========================================

                source=(
                    "Semantic Scholar"
                ),

                citation_count=(
                    citation_count
                ),
            )

        except Exception:

            logger.exception(
                "Could not convert Semantic Scholar "
                "paper into Paper. paperId=%s",
                item.get(
                    "paperId"
                ),
            )

            return None

    # ======================================================
    # AUTHORS
    # ======================================================

    @staticmethod
    def _extract_authors(
        item: dict[str, Any],
    ) -> list[str]:
        """
        Extract author names.
        """

        authors: list[str] = []

        for author in (
            item.get(
                "authors"
            )
            or []
        ):

            name = str(
                author.get(
                    "name"
                )
                or ""
            ).strip()

            if name:

                authors.append(
                    name
                )

        return remove_duplicates(
            authors
        )

    # ======================================================
    # URL HELPER
    # ======================================================

    @staticmethod
    def _first_valid_url(
        *urls: str | None,
    ) -> str | None:
        """
        Return first usable HTTP/HTTPS URL.
        """

        for url in urls:

            if not url:

                continue

            cleaned_url = (
                str(
                    url
                ).strip()
            )

            if cleaned_url.startswith(
                (
                    "https://",
                    "http://",
                )
            ):

                return cleaned_url

        return None