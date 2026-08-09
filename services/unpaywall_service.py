"""
Unpaywall open-access enrichment service.

Phase 6.5 behavior:

Unpaywall is now an OPTIONAL ENRICHMENT SERVICE.

It does NOT decide whether a paper should remain in
the search results.

A paper is always kept when it already has a usable
publisher, DOI, repository, or discovery-source link.

If Unpaywall finds a legal open-access copy:
    - add the free PDF or landing-page URL
    - mark the paper as open access

If Unpaywall does not find a free copy:
    - keep the original publisher/institutional link
    - mark the access appropriately

If a paper has no DOI:
    - keep the paper
    - skip the Unpaywall request

If Unpaywall temporarily fails:
    - keep the paper
    - do not break the complete search pipeline
"""

from urllib.parse import quote

import requests

from config import Settings
from models import Paper
from utils.helpers import clean_doi
from utils.logger import get_logger


logger = get_logger(__name__)


class UnpaywallServiceError(Exception):
    """
    Raised when a direct Unpaywall operation cannot
    be completed.

    Phase 6.5 bulk enrichment normally handles
    individual failures gracefully so papers are
    not lost.
    """


class UnpaywallService:
    """
    Enrich research papers with legal open-access
    information from Unpaywall.
    """

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        """
        Initialize the Unpaywall service.
        """

        self.settings = settings

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": (
                    f"{self.settings.app_name}/1.0 "
                    f"({self.settings.unpaywall_email or 'no-email'})"
                ),
            }
        )

    # ======================================================
    # BULK ENRICHMENT
    # ======================================================

    def verify_papers(
        self,
        papers: list[Paper],
        required_count: int | None = None,
    ) -> list[Paper]:
        """
        Enrich papers using Unpaywall.

        IMPORTANT PHASE 6.5 CHANGE:

        This method returns ALL usable input papers.

        Papers are NOT removed because:
        - they do not have a DOI
        - they are not open access
        - Unpaywall has no record
        - Unpaywall reports the paper as closed
        - an individual Unpaywall request fails

        Args:
            papers:
                Papers discovered by academic search
                services such as OpenAlex.

            required_count:
                Kept for compatibility with the current
                agent pipeline.

                It no longer means that only this many
                open-access papers must be found.

        Returns:
            The original paper collection enriched with
            Unpaywall information whenever possible.
        """

        if not papers:
            return []

        logger.info(
            "Starting optional Unpaywall enrichment "
            "for %s paper(s).",
            len(papers),
        )

        enriched_papers: list[Paper] = []

        checked_count = 0
        open_access_count = 0
        skipped_no_doi_count = 0
        failed_count = 0

        # --------------------------------------------------
        # EMAIL CONFIGURATION
        #
        # If the email is missing, we DO NOT destroy the
        # search. We simply return the original papers.
        # --------------------------------------------------

        if not self.settings.unpaywall_email:

            logger.warning(
                "UNPAYWALL_EMAIL is not configured. "
                "Skipping Unpaywall enrichment."
            )

            return papers

        # --------------------------------------------------
        # PROCESS EVERY PAPER
        # --------------------------------------------------

        for paper in papers:

            doi = clean_doi(
                paper.doi
            )

            # ----------------------------------------------
            # NO DOI
            #
            # Do NOT reject the paper.
            # ----------------------------------------------

            if not doi:

                skipped_no_doi_count += 1

                enriched_papers.append(
                    self._ensure_access_type(
                        paper
                    )
                )

                continue

            # ----------------------------------------------
            # CHECK UNPAYWALL
            # ----------------------------------------------

            try:

                enriched_paper = (
                    self.verify_paper(
                        paper
                    )
                )

                checked_count += 1

                if (
                    enriched_paper.is_open_access
                    or enriched_paper.pdf_url
                ):

                    open_access_count += 1

                enriched_papers.append(
                    enriched_paper
                )

            except Exception as error:

                # ------------------------------------------
                # IMPORTANT:
                #
                # Unpaywall failure must NOT remove the
                # paper from the search results.
                # ------------------------------------------

                failed_count += 1

                logger.warning(
                    "Unpaywall enrichment failed for DOI %s. "
                    "Keeping the original paper. Error: %s",
                    doi,
                    error,
                )

                enriched_papers.append(
                    self._ensure_access_type(
                        paper
                    )
                )

        logger.info(
            "Unpaywall enrichment completed: "
            "total=%s, checked=%s, open_access=%s, "
            "no_doi=%s, failed=%s.",
            len(papers),
            checked_count,
            open_access_count,
            skipped_no_doi_count,
            failed_count,
        )

        return enriched_papers

    # ======================================================
    # VERIFY / ENRICH ONE PAPER
    # ======================================================

    def verify_paper(
        self,
        paper: Paper,
    ) -> Paper:
        """
        Enrich one paper using Unpaywall.

        The paper is ALWAYS returned.

        If Unpaywall finds open access, the paper receives
        the best legal OA URL.

        If Unpaywall reports closed access or cannot find
        the DOI, the original publisher link remains.
        """

        doi = clean_doi(
            paper.doi
        )

        # --------------------------------------------------
        # NO DOI
        # --------------------------------------------------

        if not doi:

            return self._ensure_access_type(
                paper
            )

        # --------------------------------------------------
        # CONFIG CHECK
        # --------------------------------------------------

        if not self.settings.unpaywall_email:

            return self._ensure_access_type(
                paper
            )

        # --------------------------------------------------
        # BUILD REQUEST URL
        # --------------------------------------------------

        encoded_doi = quote(
            doi,
            safe="",
        )

        url = (
            f"{self.settings.unpaywall_base_url}/"
            f"{encoded_doi}"
        )

        params = {
            "email": (
                self.settings.unpaywall_email
            )
        }

        logger.debug(
            "Checking Unpaywall DOI: %s",
            doi,
        )

        # --------------------------------------------------
        # REQUEST
        # --------------------------------------------------

        try:

            response = self.session.get(
                url,
                params=params,
                timeout=(
                    self.settings.request_timeout
                ),
            )

        except requests.Timeout:

            logger.warning(
                "Unpaywall request timed out "
                "for DOI %s.",
                doi,
            )

            return self._ensure_access_type(
                paper
            )

        except requests.ConnectionError:

            logger.warning(
                "Could not connect to Unpaywall "
                "for DOI %s.",
                doi,
            )

            return self._ensure_access_type(
                paper
            )

        except requests.RequestException as error:

            logger.warning(
                "Unpaywall request error for DOI %s: %s",
                doi,
                error,
            )

            return self._ensure_access_type(
                paper
            )

        # --------------------------------------------------
        # DOI NOT FOUND
        #
        # 404 does NOT mean remove the paper.
        # --------------------------------------------------

        if response.status_code == 404:

            logger.debug(
                "DOI not found in Unpaywall: %s",
                doi,
            )

            return self._mark_checked_without_oa(
                paper=paper,
                oa_status=None,
            )

        # --------------------------------------------------
        # INVALID DOI / REQUEST
        # --------------------------------------------------

        if response.status_code == 422:

            logger.debug(
                "Unpaywall could not process DOI: %s",
                doi,
            )

            return self._ensure_access_type(
                paper
            )

        # --------------------------------------------------
        # RATE LIMIT
        # --------------------------------------------------

        if response.status_code == 429:

            logger.warning(
                "Unpaywall rate limit reached. "
                "Keeping paper without additional "
                "Unpaywall enrichment."
            )

            return self._ensure_access_type(
                paper
            )

        # --------------------------------------------------
        # OTHER HTTP ERRORS
        # --------------------------------------------------

        if not response.ok:

            logger.warning(
                "Unpaywall returned HTTP %s for DOI %s. "
                "Keeping the paper.",
                response.status_code,
                doi,
            )

            return self._ensure_access_type(
                paper
            )

        # --------------------------------------------------
        # JSON
        # --------------------------------------------------

        try:

            payload = response.json()

        except ValueError:

            logger.warning(
                "Unpaywall returned invalid JSON "
                "for DOI %s.",
                doi,
            )

            return self._ensure_access_type(
                paper
            )

        # --------------------------------------------------
        # READ OA STATUS
        # --------------------------------------------------

        is_oa = bool(
            payload.get(
                "is_oa"
            )
        )

        oa_status = (
            payload.get(
                "oa_status"
            )
        )

        best_oa_location = (
            payload.get(
                "best_oa_location"
            )
            or {}
        )

        # --------------------------------------------------
        # CLOSED / NOT OPEN ACCESS
        #
        # IMPORTANT:
        # KEEP THE PAPER.
        # --------------------------------------------------

        if not is_oa:

            return self._mark_checked_without_oa(
                paper=paper,
                oa_status=oa_status,
            )

        # --------------------------------------------------
        # OPEN ACCESS FOUND
        # --------------------------------------------------

        pdf_url = (
            self._first_valid_url(
                best_oa_location.get(
                    "url_for_pdf"
                ),
                best_oa_location.get(
                    "url"
                )
                if self._looks_like_pdf(
                    best_oa_location.get(
                        "url"
                    )
                )
                else None,
                paper.pdf_url,
            )
        )

        # --------------------------------------------------
        # OA LANDING PAGE
        # --------------------------------------------------

        oa_landing_url = (
            self._first_valid_url(
                best_oa_location.get(
                    "url_for_landing_page"
                ),
                best_oa_location.get(
                    "url"
                ),
            )
        )

        # --------------------------------------------------
        # KEEP ORIGINAL PUBLISHER LINK WHEN POSSIBLE
        #
        # paper_url represents the normal paper/publisher
        # page. We only use the OA landing page when there
        # is no useful existing paper URL.
        # --------------------------------------------------

        paper_url = (
            str(
                paper.paper_url
            )
            if paper.paper_url
            else oa_landing_url
        )

        # --------------------------------------------------
        # HOST TYPE
        # --------------------------------------------------

        host_type = (
            best_oa_location.get(
                "host_type"
            )
        )

        # --------------------------------------------------
        # ACCESS LABEL
        # --------------------------------------------------

        if pdf_url:

            access_type = (
                "Free PDF"
            )

        else:

            access_type = (
                "Free / Open Access"
            )

        # --------------------------------------------------
        # UPDATE PAPER
        # --------------------------------------------------

        enriched_paper = paper.model_copy(
            update={
                "paper_url": (
                    paper_url
                ),
                "pdf_url": (
                    pdf_url
                ),
                "is_open_access": True,
                "verified_by_unpaywall": True,
                "oa_status": (
                    oa_status
                ),
                "oa_host_type": (
                    host_type
                ),
                "access_type": (
                    access_type
                ),
                "source": (
                    self._merge_source_name(
                        paper.source
                    )
                ),
            }
        )

        logger.debug(
            "Unpaywall found open access "
            "for DOI %s.",
            doi,
        )

        return enriched_paper

    # ======================================================
    # MARK CHECKED BUT NOT OPEN ACCESS
    # ======================================================

    def _mark_checked_without_oa(
        self,
        paper: Paper,
        oa_status: str | None,
    ) -> Paper:
        """
        Mark a paper as checked by Unpaywall when no
        legal open-access copy was identified.

        The original paper URL is preserved.
        """

        access_type = (
            self._get_non_oa_access_type(
                paper
            )
        )

        return paper.model_copy(
            update={
                "verified_by_unpaywall": True,
                "oa_status": (
                    oa_status
                ),
                "access_type": (
                    access_type
                ),
                "source": (
                    self._merge_source_name(
                        paper.source
                    )
                ),
            }
        )

    # ======================================================
    # ENSURE ACCESS TYPE
    # ======================================================

    @staticmethod
    def _ensure_access_type(
        paper: Paper,
    ) -> Paper:
        """
        Ensure every paper has a useful human-readable
        access label.
        """

        # --------------------------------------------------
        # DIRECT FREE PDF
        # --------------------------------------------------

        if paper.pdf_url:

            access_type = (
                "Free PDF"
            )

        # --------------------------------------------------
        # OTHER OPEN ACCESS
        # --------------------------------------------------

        elif paper.is_open_access:

            access_type = (
                "Free / Open Access"
            )

        # --------------------------------------------------
        # PUBLISHER / DOI PAGE EXISTS
        # --------------------------------------------------

        elif (
            paper.paper_url
            or paper.source_url
        ):

            access_type = (
                "Publisher / Institutional Access"
            )

        # --------------------------------------------------
        # UNKNOWN
        # --------------------------------------------------

        else:

            access_type = (
                "Access Unknown"
            )

        if (
            paper.access_type
            == access_type
        ):

            return paper

        return paper.model_copy(
            update={
                "access_type": (
                    access_type
                )
            }
        )

    # ======================================================
    # NON-OA ACCESS TYPE
    # ======================================================

    @staticmethod
    def _get_non_oa_access_type(
        paper: Paper,
    ) -> str:
        """
        Determine the best access label when Unpaywall
        reports no open-access copy.
        """

        if paper.pdf_url:

            # OpenAlex or another source may already
            # have supplied a PDF.
            return "Free PDF"

        if paper.is_open_access:

            return "Free / Open Access"

        if (
            paper.paper_url
            or paper.source_url
        ):

            return (
                "Publisher / Institutional Access"
            )

        return "Access Unknown"

    # ======================================================
    # MERGE SOURCE NAME
    # ======================================================

    @staticmethod
    def _merge_source_name(
        existing_source: str | None,
    ) -> str:
        """
        Record that Unpaywall enriched the paper while
        preserving the original discovery source.
        """

        existing = (
            existing_source
            or "Unknown"
        )

        if (
            "Unpaywall"
            in existing
        ):

            return existing

        if (
            existing
            == "Unknown"
        ):

            return "Unpaywall"

        return (
            f"{existing} + Unpaywall"
        )

    # ======================================================
    # PDF URL CHECK
    # ======================================================

    @staticmethod
    def _looks_like_pdf(
        url: str | None,
    ) -> bool:
        """
        Perform a simple URL-based PDF check.
        """

        if not url:
            return False

        cleaned_url = (
            str(
                url
            )
            .strip()
            .lower()
        )

        return (
            ".pdf" in cleaned_url
        )

    # ======================================================
    # URL HELPER
    # ======================================================

    @staticmethod
    def _first_valid_url(
        *urls: str | None,
    ) -> str | None:
        """
        Return the first available HTTP/HTTPS URL.
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