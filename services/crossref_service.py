"""
Crossref scholarly-search service.

Phase 6.5.5

This service searches Crossref for scholarly works and
converts Crossref metadata into the common Paper model.

Crossref is used as an ADDITIONAL discovery source.

Important behavior:
- Paid papers are kept.
- Open-access papers are kept.
- Papers without ranking information are kept.
- DOI/publisher links are preserved.
- ISSNs are collected for later ranking enrichment.
"""

from typing import Any

import requests

from config import Settings
from models import Paper
from utils.helpers import (
    clean_doi,
    normalize_issn,
    remove_duplicates,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class CrossrefServiceError(Exception):
    """
    Raised when Crossref cannot complete a search.
    """


class CrossrefService:
    """
    Search scholarly works through the Crossref REST API.
    """

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        """
        Initialize Crossref.
        """

        self.settings = settings

        self.base_url = (
            "https://api.crossref.org"
        )

        self.works_url = (
            f"{self.base_url}/works"
        )

        self.session = (
            requests.Session()
        )

        # --------------------------------------------------
        # CROSSREF POLITE POOL
        #
        # Crossref recommends including a contact email.
        # We reuse OPENALEX_EMAIL because it is already
        # configured in this project.
        # --------------------------------------------------

        contact_email = (
            self.settings.openalex_email
            or self.settings.unpaywall_email
            or ""
        )

        self.contact_email = (
            contact_email
        )

        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": (
                    f"{self.settings.app_name}/1.0 "
                    f"({contact_email or 'no-email'})"
                ),
            }
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
        Search Crossref for scholarly works.

        Crossref is not restricted to open-access papers.

        Args:
            keyword:
                User research topic.

            start_year:
                First publication year.

            end_year:
                Last publication year.

            paper_count:
                Number requested by the user.

        Returns:
            List of normalized Paper objects.
        """

        # --------------------------------------------------
        # FETCH MORE THAN FINAL COUNT
        #
        # This gives us enough results for merging and
        # deduplication with OpenAlex.
        # --------------------------------------------------

        fetch_count = min(
            max(
                paper_count * 5,
                20,
            ),
            100,
        )

        # --------------------------------------------------
        # DATE FILTER
        # --------------------------------------------------

        filters = (
            f"from-pub-date:{start_year}-01-01,"
            f"until-pub-date:{end_year}-12-31"
        )

        params = {
            "query.bibliographic": (
                keyword
            ),
            "filter": (
                filters
            ),
            "rows": (
                fetch_count
            ),
            "sort": (
                "relevance"
            ),
            "order": (
                "desc"
            ),
        }

        # --------------------------------------------------
        # CROSSREF POLITE EMAIL
        # --------------------------------------------------

        if self.contact_email:

            params["mailto"] = (
                self.contact_email
            )

        logger.info(
            "Searching Crossref: keyword=%s, "
            "years=%s-%s, requested=%s, fetch=%s",
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
                    self.works_url,
                    params=params,
                    timeout=(
                        self.settings.request_timeout
                    ),
                )
            )

            response.raise_for_status()

        except requests.Timeout as error:

            logger.warning(
                "Crossref request timed out."
            )

            raise CrossrefServiceError(
                "The Crossref request timed out. "
                "Please try again."
            ) from error

        except requests.ConnectionError as error:

            logger.warning(
                "Could not connect to Crossref."
            )

            raise CrossrefServiceError(
                "The application could not connect "
                "to Crossref."
            ) from error

        except requests.HTTPError as error:

            status_code = (
                error.response.status_code
                if error.response is not None
                else "unknown"
            )

            logger.warning(
                "Crossref HTTP error: %s",
                status_code,
            )

            if status_code == 429:

                message = (
                    "Crossref rate limit reached. "
                    "Please wait and try again."
                )

            else:

                message = (
                    "Crossref returned an error. "
                    f"HTTP status: {status_code}."
                )

            raise CrossrefServiceError(
                message
            ) from error

        except requests.RequestException as error:

            logger.warning(
                "Unexpected Crossref request error: %s",
                error,
            )

            raise CrossrefServiceError(
                "An unexpected network error occurred "
                "while searching Crossref."
            ) from error

        # --------------------------------------------------
        # JSON RESPONSE
        # --------------------------------------------------

        try:

            payload = (
                response.json()
            )

        except ValueError as error:

            raise CrossrefServiceError(
                "Crossref returned an unreadable response."
            ) from error

        message = (
            payload.get(
                "message"
            )
            or {}
        )

        raw_items = (
            message.get(
                "items"
            )
            or []
        )

        papers: list[Paper] = []

        # --------------------------------------------------
        # CONVERT RESULTS
        # --------------------------------------------------

        for item in raw_items:

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
            "Crossref returned %s raw records "
            "and %s usable papers.",
            len(raw_items),
            len(papers),
        )

        return papers

    # ======================================================
    # CONVERT CROSSREF RECORD
    # ======================================================

    def _convert_item_to_paper(
        self,
        item: dict[str, Any],
    ) -> Paper | None:
        """
        Convert one Crossref work into Paper.
        """

        # --------------------------------------------------
        # TITLE
        # --------------------------------------------------

        title = (
            self._first_text(
                item.get(
                    "title"
                )
            )
        )

        if not title:

            return None

        # --------------------------------------------------
        # PUBLICATION YEAR
        # --------------------------------------------------

        year = (
            self._extract_year(
                item
            )
        )

        if year is None:

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
        # JOURNAL / VENUE
        # --------------------------------------------------

        journal_name = (
            self._first_text(
                item.get(
                    "container-title"
                )
            )
        )

        # --------------------------------------------------
        # DOI
        # --------------------------------------------------

        doi = (
            clean_doi(
                item.get(
                    "DOI"
                )
            )
        )

        # --------------------------------------------------
        # ISSNS
        # --------------------------------------------------

        issns = (
            self._extract_issns(
                item
            )
        )

        # --------------------------------------------------
        # PUBLISHER / PAPER URL
        # --------------------------------------------------

        doi_url = (
            f"https://doi.org/{doi}"
            if doi
            else None
        )

        paper_url = (
            self._first_valid_url(
                item.get(
                    "URL"
                ),
                doi_url,
            )
        )

        # --------------------------------------------------
        # POSSIBLE FULL-TEXT URL
        #
        # Important:
        # Crossref links do not automatically mean that
        # the content is freely accessible.
        #
        # Therefore we DO NOT mark a Crossref link as
        # open access here.
        # Unpaywall will verify OA later.
        # --------------------------------------------------

        possible_pdf_url = (
            self._extract_pdf_link(
                item
            )
        )

        # --------------------------------------------------
        # SOURCE URL
        # --------------------------------------------------

        source_url = (
            doi_url
            or paper_url
        )

        if (
            not paper_url
            and not source_url
            and not possible_pdf_url
        ):

            return None

        # --------------------------------------------------
        # CITATION COUNT
        # --------------------------------------------------

        citation_count = (
            item.get(
                "is-referenced-by-count"
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
                #
                # Ranking will be added later.
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

                # We intentionally do NOT treat Crossref's
                # full-text metadata link as verified free
                # access.
                pdf_url=None,

                source_url=source_url,

                # ==========================================
                # ACCESS
                # ==========================================

                is_open_access=False,

                verified_by_unpaywall=False,

                oa_status=None,

                oa_host_type=None,

                access_type=(
                    "Publisher / Institutional Access"
                    if (
                        paper_url
                        or source_url
                    )
                    else "Access Unknown"
                ),

                # ==========================================
                # DISCOVERY SOURCE
                # ==========================================

                source="Crossref",

                citation_count=(
                    citation_count
                ),
            )

        except Exception:

            logger.exception(
                "Could not convert Crossref "
                "record to Paper. DOI=%s",
                doi,
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
        Extract Crossref author names.
        """

        authors: list[str] = []

        for author in (
            item.get(
                "author"
            )
            or []
        ):

            given = str(
                author.get(
                    "given"
                )
                or ""
            ).strip()

            family = str(
                author.get(
                    "family"
                )
                or ""
            ).strip()

            name = (
                f"{given} {family}"
            ).strip()

            if (
                name
                and name
                not in authors
            ):

                authors.append(
                    name
                )

        return authors

    # ======================================================
    # YEAR EXTRACTION
    # ======================================================

    @classmethod
    def _extract_year(
        cls,
        item: dict[str, Any],
    ) -> int | None:
        """
        Extract publication year from Crossref metadata.

        Preferred sources:
        1. published
        2. published-print
        3. published-online
        4. issued
        5. created
        """

        for field_name in [
            "published",
            "published-print",
            "published-online",
            "issued",
        ]:

            field = (
                item.get(
                    field_name
                )
                or {}
            )

            year = (
                cls._year_from_date_parts(
                    field
                )
            )

            if year is not None:

                return year

        # --------------------------------------------------
        # FALLBACK: CREATED DATE
        # --------------------------------------------------

        created = (
            item.get(
                "created"
            )
            or {}
        )

        date_parts = (
            created.get(
                "date-parts"
            )
            or []
        )

        if date_parts:

            try:

                return int(
                    date_parts[0][0]
                )

            except (
                IndexError,
                TypeError,
                ValueError,
            ):

                pass

        return None

    # ======================================================
    # DATE PART HELPER
    # ======================================================

    @staticmethod
    def _year_from_date_parts(
        field: dict[str, Any],
    ) -> int | None:
        """
        Extract year from Crossref date-parts.
        """

        date_parts = (
            field.get(
                "date-parts"
            )
            or []
        )

        if not date_parts:

            return None

        try:

            return int(
                date_parts[0][0]
            )

        except (
            IndexError,
            TypeError,
            ValueError,
        ):

            return None

    # ======================================================
    # ISSN EXTRACTION
    # ======================================================

    @staticmethod
    def _extract_issns(
        item: dict[str, Any],
    ) -> list[str]:
        """
        Extract normalized ISSNs from Crossref.
        """

        raw_issns = (
            item.get(
                "ISSN"
            )
            or []
        )

        if isinstance(
            raw_issns,
            str,
        ):

            raw_issns = [
                raw_issns
            ]

        normalized_issns: list[str] = []

        for raw_issn in raw_issns:

            normalized = (
                normalize_issn(
                    raw_issn
                )
            )

            if (
                normalized
                and normalized
                not in normalized_issns
            ):

                normalized_issns.append(
                    normalized
                )

        return normalized_issns

    # ======================================================
    # PDF / FULL-TEXT LINK
    # ======================================================

    @classmethod
    def _extract_pdf_link(
        cls,
        item: dict[str, Any],
    ) -> str | None:
        """
        Extract a possible PDF-like link.

        IMPORTANT:
        This does NOT prove the paper is free.

        We intentionally do not assign this directly to
        Paper.pdf_url. Unpaywall remains responsible for
        verified open-access enrichment.
        """

        links = (
            item.get(
                "link"
            )
            or []
        )

        for link in links:

            url = (
                link.get(
                    "URL"
                )
            )

            content_type = str(
                link.get(
                    "content-type"
                )
                or ""
            ).lower()

            if not url:

                continue

            if (
                "pdf"
                in content_type
                or cls._looks_like_pdf(
                    url
                )
            ):

                valid_url = (
                    cls._first_valid_url(
                        url
                    )
                )

                if valid_url:

                    return valid_url

        return None

    # ======================================================
    # FIRST TEXT
    # ======================================================

    @staticmethod
    def _first_text(
        value: Any,
    ) -> str | None:
        """
        Return the first useful text value.
        """

        if value is None:

            return None

        if isinstance(
            value,
            list,
        ):

            if not value:

                return None

            value = (
                value[0]
            )

        cleaned = str(
            value
        ).strip()

        return (
            cleaned
            or None
        )

    # ======================================================
    # PDF CHECK
    # ======================================================

    @staticmethod
    def _looks_like_pdf(
        url: str | None,
    ) -> bool:
        """
        Simple PDF URL check.
        """

        if not url:

            return False

        return (
            ".pdf"
            in str(
                url
            ).lower()
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

            cleaned_url = str(
                url
            ).strip()

            if cleaned_url.startswith(
                (
                    "https://",
                    "http://",
                )
            ):

                return cleaned_url

        return None