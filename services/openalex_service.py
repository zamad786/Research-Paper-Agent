"""
OpenAlex paper-search service.

This service communicates with the OpenAlex Works API and
converts the returned JSON records into Paper objects.

Phase 6.5 behavior:
- Searches broadly across scholarly works.
- Does NOT require a paper to be open access.
- Keeps publisher/institutional-access papers.
- Keeps papers even when ranking information is unavailable.
- Prefers the primary publication source for journal metadata.
- Stores free PDF links when available.
- Stores publisher/DOI/OpenAlex links when a free copy is unavailable.
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


class OpenAlexServiceError(Exception):
    """Raised when the OpenAlex service cannot complete a request."""


class OpenAlexService:
    """Search scholarly works through the OpenAlex API."""

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        """
        Initialize the OpenAlex service.

        Args:
            settings:
                Shared application configuration.
        """

        self.settings = settings

        self.works_url = (
            f"{self.settings.openalex_base_url}/works"
        )

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": (
                    f"{self.settings.app_name}/1.0 "
                    f"({self.settings.openalex_email or 'no-email'})"
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
        Search OpenAlex for scholarly works.

        IMPORTANT:
        Phase 6.5 no longer restricts the search to
        open-access papers or only journal articles.

        Args:
            keyword:
                Research topic entered by the user.

            start_year:
                First allowed publication year.

            end_year:
                Last allowed publication year.

            paper_count:
                Number of papers requested by the user.

        Returns:
            A list of normalized Paper objects.

        Raises:
            OpenAlexServiceError:
                When the API request fails.
        """

        # --------------------------------------------------
        # CHECK API KEY
        # --------------------------------------------------

        if not self.settings.openalex_api_key:

            raise OpenAlexServiceError(
                "OPENALEX_API_KEY is missing. Add your OpenAlex "
                "API key to the .env file and restart Streamlit."
            )

        # --------------------------------------------------
        # FETCH MORE THAN REQUESTED
        #
        # Other services will later enrich and deduplicate
        # these results.
        # --------------------------------------------------

        fetch_count = min(
            max(
                paper_count * 10,
                30,
            ),
            self.settings.openalex_results_per_request,
        )

        # --------------------------------------------------
        # FILTERS
        #
        # IMPORTANT:
        #
        # We intentionally DO NOT use:
        #
        # open_access.is_oa:true
        # type:article
        #
        # because Phase 6.5 performs broad discovery.
        # --------------------------------------------------

        filters = [
            f"publication_year:{start_year}-{end_year}",
            "is_retracted:false",
        ]

        params = {
            "api_key": (
                self.settings.openalex_api_key
            ),
            "search": keyword,
            "filter": ",".join(
                filters
            ),
            "sort": (
                "relevance_score:desc,"
                "publication_year:desc"
            ),
            "per_page": fetch_count,
        }

        logger.info(
            "Searching OpenAlex: keyword=%s, years=%s-%s, "
            "requested_count=%s, fetched_count=%s",
            keyword,
            start_year,
            end_year,
            paper_count,
            fetch_count,
        )

        # --------------------------------------------------
        # REQUEST OPENALEX
        # --------------------------------------------------

        try:

            response = self.session.get(
                self.works_url,
                params=params,
                timeout=(
                    self.settings.request_timeout
                ),
            )

            response.raise_for_status()

        except requests.Timeout as error:

            logger.exception(
                "OpenAlex request timed out."
            )

            raise OpenAlexServiceError(
                "The OpenAlex request timed out. "
                "Please try again."
            ) from error

        except requests.ConnectionError as error:

            logger.exception(
                "Could not connect to OpenAlex."
            )

            raise OpenAlexServiceError(
                "The application could not connect to OpenAlex. "
                "Please check your internet connection."
            ) from error

        except requests.HTTPError as error:

            status_code = (
                error.response.status_code
                if error.response is not None
                else "unknown"
            )

            logger.exception(
                "OpenAlex returned HTTP status %s.",
                status_code,
            )

            if status_code == 401:

                message = (
                    "OpenAlex rejected the API key. Check the "
                    "OPENALEX_API_KEY value in your .env file."
                )

            elif status_code == 403:

                message = (
                    "OpenAlex denied the request. Your API key may "
                    "be invalid or its usage allowance may be exhausted."
                )

            elif status_code == 429:

                message = (
                    "The OpenAlex request limit was reached. "
                    "Please wait and try again."
                )

            else:

                message = (
                    "OpenAlex returned an error while searching "
                    f"for papers. HTTP status: {status_code}."
                )

            raise OpenAlexServiceError(
                message
            ) from error

        except requests.RequestException as error:

            logger.exception(
                "Unexpected OpenAlex request error."
            )

            raise OpenAlexServiceError(
                "An unexpected network error occurred while "
                "searching OpenAlex."
            ) from error

        # --------------------------------------------------
        # READ JSON RESPONSE
        # --------------------------------------------------

        try:

            payload = response.json()

        except ValueError as error:

            logger.exception(
                "OpenAlex returned invalid JSON."
            )

            raise OpenAlexServiceError(
                "OpenAlex returned an unreadable response."
            ) from error

        raw_results = payload.get(
            "results",
            [],
        )

        papers: list[Paper] = []

        # --------------------------------------------------
        # CONVERT RESULTS
        # --------------------------------------------------

        for work in raw_results:

            paper = (
                self._convert_work_to_paper(
                    work
                )
            )

            if paper is not None:

                papers.append(
                    paper
                )

        logger.info(
            "OpenAlex returned %s raw records "
            "and %s usable papers.",
            len(raw_results),
            len(papers),
        )

        return papers

    # ======================================================
    # CONVERT OPENALEX WORK
    # ======================================================

    def _convert_work_to_paper(
        self,
        work: dict[str, Any],
    ) -> Paper | None:
        """
        Convert one OpenAlex work record into a Paper.

        Papers are NOT rejected because they are:
        - paywalled
        - not open access
        - missing journal-ranking information

        Returns None only when minimum useful paper
        information is unavailable.
        """

        # --------------------------------------------------
        # TITLE
        # --------------------------------------------------

        title = str(
            work.get("display_name")
            or work.get("title")
            or ""
        ).strip()

        publication_year = (
            work.get(
                "publication_year"
            )
        )

        if (
            not title
            or not publication_year
        ):

            return None

        # --------------------------------------------------
        # REMOVE RETRACTED WORK
        # --------------------------------------------------

        if (
            work.get("is_retracted")
            is True
        ):

            return None

        # --------------------------------------------------
        # AUTHORS
        # --------------------------------------------------

        authors = (
            self._extract_authors(
                work
            )
        )

        # --------------------------------------------------
        # LOCATIONS
        # --------------------------------------------------

        primary_location = (
            work.get(
                "primary_location"
            )
            or {}
        )

        best_oa_location = (
            work.get(
                "best_oa_location"
            )
            or {}
        )

        open_access = (
            work.get(
                "open_access"
            )
            or {}
        )

        # --------------------------------------------------
        # PUBLICATION SOURCE
        #
        # IMPORTANT:
        # Prefer the primary source because the best OA
        # location could be a repository rather than the
        # actual journal/publisher.
        # --------------------------------------------------

        primary_source = (
            primary_location.get(
                "source"
            )
            or {}
        )

        best_oa_source = (
            best_oa_location.get(
                "source"
            )
            or {}
        )

        source = (
            primary_source
            or best_oa_source
        )

        # --------------------------------------------------
        # JOURNAL / VENUE
        # --------------------------------------------------

        journal_name = (
            source.get(
                "display_name"
            )
        )

        # --------------------------------------------------
        # ISSNS
        # --------------------------------------------------

        issns = (
            self._extract_issns(
                source=source,
                primary_location=(
                    primary_location
                ),
                best_oa_location=(
                    best_oa_location
                ),
            )
        )

        # --------------------------------------------------
        # FREE PDF
        # --------------------------------------------------

        pdf_url = (
            self._first_valid_url(
                best_oa_location.get(
                    "pdf_url"
                ),
                primary_location.get(
                    "pdf_url"
                ),
            )
        )

        # --------------------------------------------------
        # PAPER / PUBLISHER LINK
        #
        # Priority:
        #
        # 1. Primary publication page
        # 2. Best OA page
        # 3. DOI URL
        # 4. OpenAlex page
        # --------------------------------------------------

        paper_url = (
            self._first_valid_url(
                primary_location.get(
                    "landing_page_url"
                ),
                best_oa_location.get(
                    "landing_page_url"
                ),
                work.get(
                    "doi"
                ),
                work.get(
                    "id"
                ),
            )
        )

        # --------------------------------------------------
        # OPENALEX RECORD URL
        # --------------------------------------------------

        source_url = (
            self._first_valid_url(
                work.get(
                    "id"
                ),
            )
        )

        # --------------------------------------------------
        # OPEN-ACCESS STATUS
        # --------------------------------------------------

        is_open_access = bool(
            open_access.get(
                "is_oa"
            )
            or best_oa_location.get(
                "is_oa"
            )
            or primary_location.get(
                "is_oa"
            )
        )

        # --------------------------------------------------
        # IMPORTANT PHASE 6.5 CHANGE
        #
        # DO NOT DO THIS ANYMORE:
        #
        # if not is_open_access:
        #     return None
        #
        # Paid papers are useful because users may have
        # university/institutional access.
        # --------------------------------------------------

        # --------------------------------------------------
        # REQUIRE AT LEAST ONE USABLE LINK
        # --------------------------------------------------

        if (
            not pdf_url
            and not paper_url
            and not source_url
        ):

            return None

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

                year=int(
                    publication_year
                ),

                journal=journal_name,

                # ==========================================
                # IDENTIFIERS
                # ==========================================

                doi=clean_doi(
                    work.get(
                        "doi"
                    )
                ),

                issns=issns,

                # ==========================================
                # RANKING
                #
                # Ranking will be enriched later.
                # Missing ranking does NOT reject paper.
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
                    open_access.get(
                        "oa_status"
                    )
                ),

                oa_host_type=None,

                access_type=(
                    "Free PDF"
                    if pdf_url
                    else (
                        "Free / Open Access"
                        if is_open_access
                        else (
                            "Publisher / "
                            "Institutional Access"
                        )
                    )
                ),

                # ==========================================
                # DISCOVERY SOURCE
                # ==========================================

                source="OpenAlex",

                citation_count=(
                    work.get(
                        "cited_by_count"
                    )
                ),
            )

        except Exception:

            logger.exception(
                "Could not convert OpenAlex work "
                "into Paper: %s",
                work.get(
                    "id"
                ),
            )

            return None

    # ======================================================
    # EXTRACT AUTHORS
    # ======================================================

    @staticmethod
    def _extract_authors(
        work: dict[str, Any],
    ) -> list[str]:
        """
        Extract author names from an OpenAlex work.
        """

        authors: list[str] = []

        for authorship in work.get(
            "authorships",
            [],
        ):

            author = (
                authorship.get(
                    "author"
                )
                or {}
            )

            author_name = (
                author.get(
                    "display_name"
                )
            )

            if author_name:

                authors.append(
                    str(
                        author_name
                    ).strip()
                )

        return remove_duplicates(
            authors
        )

    # ======================================================
    # EXTRACT ISSNS
    # ======================================================

    @staticmethod
    def _extract_issns(
        source: dict[str, Any],
        primary_location: dict[str, Any],
        best_oa_location: dict[str, Any],
    ) -> list[str]:
        """
        Extract and normalize all available ISSNs.
        """

        raw_issns: list[str] = []

        # --------------------------------------------------
        # MAIN SOURCE ISSNS
        # --------------------------------------------------

        source_issns = (
            source.get(
                "issn"
            )
            or []
        )

        if isinstance(
            source_issns,
            list,
        ):

            raw_issns.extend(
                source_issns
            )

        source_issn_l = (
            source.get(
                "issn_l"
            )
        )

        if source_issn_l:

            raw_issns.append(
                source_issn_l
            )

        # --------------------------------------------------
        # LOCATION SOURCE ISSNS
        # --------------------------------------------------

        for location in [
            primary_location,
            best_oa_location,
        ]:

            location_source = (
                location.get(
                    "source"
                )
                or {}
            )

            location_issns = (
                location_source.get(
                    "issn"
                )
                or []
            )

            if isinstance(
                location_issns,
                list,
            ):

                raw_issns.extend(
                    location_issns
                )

            location_issn_l = (
                location_source.get(
                    "issn_l"
                )
            )

            if location_issn_l:

                raw_issns.append(
                    location_issn_l
                )

        # --------------------------------------------------
        # NORMALIZE
        # --------------------------------------------------

        normalized_issns = [
            normalized
            for issn in raw_issns
            if (
                normalized
                := normalize_issn(
                    issn
                )
            )
        ]

        return remove_duplicates(
            normalized_issns
        )

    # ======================================================
    # URL HELPER
    # ======================================================

    @staticmethod
    def _first_valid_url(
        *urls: str | None,
    ) -> str | None:
        """
        Return the first available HTTP or HTTPS URL.
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