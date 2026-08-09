"""
Journal-ranking enrichment service.

Phase 6.5 behavior:

Journal ranking is OPTIONAL METADATA.

A paper is NEVER removed simply because:
- it has no ISSN
- its journal is not in the local ranking dataset
- its journal is Q3 or Q4
- its journal ranking cannot be verified
- it is not HEC W category

The ranking service attempts to identify:

- Q1
- Q2
- Q3
- Q4
- HEC W

If no ranking can be verified:

    Ranking = "Not Verified"

The paper still remains in the search results.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from models import Paper
from utils.helpers import normalize_issn
from utils.logger import get_logger


logger = get_logger(__name__)


class RankingServiceError(Exception):
    """
    Raised when ranking datasets cannot be loaded
    or processed.
    """


class RankingService:
    """
    Enrich papers with journal-ranking information.

    Ranking is informational and is NOT used as a
    mandatory rejection condition.
    """

    def __init__(
        self,
        scimago_path: str = "data/scimago_journals.csv",
        hec_path: str = "data/hec_w_journals.csv",
    ) -> None:
        """
        Initialize the ranking service.
        """

        self.scimago_path = Path(
            scimago_path
        )

        self.hec_path = Path(
            hec_path
        )

        self.scimago_df = (
            self._load_scimago_data()
        )

        self.hec_df = (
            self._load_hec_data()
        )

        self.scimago_index = (
            self._build_scimago_index()
        )

        self.hec_index = (
            self._build_hec_index()
        )

        logger.info(
            "Ranking service initialized. "
            "SCImago rows=%s, HEC rows=%s.",
            len(self.scimago_df),
            len(self.hec_df),
        )

    # ======================================================
    # LOAD SCIMAGO DATA
    # ======================================================

    def _load_scimago_data(
        self,
    ) -> pd.DataFrame:
        """
        Load local SCImago journal-ranking data.

        Expected normalized columns:

        journal_name
        issn
        eissn
        quartile
        ranking_year
        """

        if not self.scimago_path.exists():

            logger.warning(
                "SCImago ranking file was not found: %s",
                self.scimago_path,
            )

            return pd.DataFrame(
                columns=[
                    "journal_name",
                    "issn",
                    "eissn",
                    "quartile",
                    "ranking_year",
                ]
            )

        try:

            dataframe = pd.read_csv(
                self.scimago_path
            )

        except Exception as error:

            raise RankingServiceError(
                "The SCImago ranking dataset "
                "could not be loaded."
            ) from error

        required_columns = {
            "journal_name",
            "issn",
            "eissn",
            "quartile",
            "ranking_year",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:

            raise RankingServiceError(
                "The SCImago ranking dataset is "
                "missing required columns: "
                + ", ".join(
                    sorted(
                        missing_columns
                    )
                )
            )

        dataframe = dataframe.copy()

        # --------------------------------------------------
        # NORMALIZE QUARTILES
        # --------------------------------------------------

        dataframe["quartile"] = (
            dataframe["quartile"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # --------------------------------------------------
        # PHASE 6.5:
        # SUPPORT ALL FOUR QUARTILES
        # --------------------------------------------------

        dataframe = dataframe[
            dataframe["quartile"].isin(
                [
                    "Q1",
                    "Q2",
                    "Q3",
                    "Q4",
                ]
            )
        ].copy()

        return dataframe

    # ======================================================
    # LOAD HEC DATA
    # ======================================================

    def _load_hec_data(
        self,
    ) -> pd.DataFrame:
        """
        Load local HEC journal-ranking information.

        Expected columns:

        journal_name
        issn
        eissn
        hec_category
        valid_from
        valid_to
        """

        if not self.hec_path.exists():

            logger.warning(
                "HEC ranking file was not found: %s",
                self.hec_path,
            )

            return pd.DataFrame(
                columns=[
                    "journal_name",
                    "issn",
                    "eissn",
                    "hec_category",
                    "valid_from",
                    "valid_to",
                ]
            )

        try:

            dataframe = pd.read_csv(
                self.hec_path
            )

        except Exception as error:

            raise RankingServiceError(
                "The HEC ranking dataset "
                "could not be loaded."
            ) from error

        required_columns = {
            "journal_name",
            "issn",
            "eissn",
            "hec_category",
            "valid_from",
            "valid_to",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:

            raise RankingServiceError(
                "The HEC ranking dataset is "
                "missing required columns: "
                + ", ".join(
                    sorted(
                        missing_columns
                    )
                )
            )

        dataframe = dataframe.copy()

        dataframe["hec_category"] = (
            dataframe["hec_category"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # --------------------------------------------------
        # CURRENT PROJECT REQUIREMENT:
        # HEC W CATEGORY
        # --------------------------------------------------

        dataframe = dataframe[
            dataframe["hec_category"]
            == "W"
        ].copy()

        # --------------------------------------------------
        # DATES
        # --------------------------------------------------

        dataframe["valid_from"] = (
            pd.to_datetime(
                dataframe["valid_from"],
                errors="coerce",
            )
        )

        dataframe["valid_to"] = (
            pd.to_datetime(
                dataframe["valid_to"],
                errors="coerce",
            )
        )

        return dataframe

    # ======================================================
    # BUILD SCIMAGO INDEX
    # ======================================================

    def _build_scimago_index(
        self,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Build ISSN -> ranking-record lookup.
        """

        index: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        for _, row in (
            self.scimago_df.iterrows()
        ):

            record = {
                "journal_name": (
                    self._safe_string(
                        row.get(
                            "journal_name"
                        )
                    )
                ),
                "quartile": (
                    self._safe_string(
                        row.get(
                            "quartile"
                        )
                    )
                ),
                "ranking_year": (
                    self._safe_int(
                        row.get(
                            "ranking_year"
                        )
                    )
                ),
                "source": "SCImago",
            }

            for raw_issn in [
                row.get(
                    "issn"
                ),
                row.get(
                    "eissn"
                ),
            ]:

                normalized = (
                    normalize_issn(
                        self._safe_string(
                            raw_issn
                        )
                    )
                )

                if not normalized:
                    continue

                index.setdefault(
                    normalized,
                    [],
                ).append(
                    record
                )

        return index

    # ======================================================
    # BUILD HEC INDEX
    # ======================================================

    def _build_hec_index(
        self,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Build ISSN -> HEC-record lookup.
        """

        index: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        for _, row in (
            self.hec_df.iterrows()
        ):

            record = {
                "journal_name": (
                    self._safe_string(
                        row.get(
                            "journal_name"
                        )
                    )
                ),
                "category": (
                    self._safe_string(
                        row.get(
                            "hec_category"
                        )
                    )
                ),
                "valid_from": (
                    row.get(
                        "valid_from"
                    )
                ),
                "valid_to": (
                    row.get(
                        "valid_to"
                    )
                ),
                "source": "HEC",
            }

            for raw_issn in [
                row.get(
                    "issn"
                ),
                row.get(
                    "eissn"
                ),
            ]:

                normalized = (
                    normalize_issn(
                        self._safe_string(
                            raw_issn
                        )
                    )
                )

                if not normalized:
                    continue

                index.setdefault(
                    normalized,
                    [],
                ).append(
                    record
                )

        return index

    # ======================================================
    # ENRICH MULTIPLE PAPERS
    # ======================================================

    def verify_papers(
        self,
        papers: list[Paper],
        allowed_categories: list[str] | None = None,
        paper_count: int | None = None,
    ) -> list[Paper]:
        """
        Enrich all papers with ranking information.

        IMPORTANT PHASE 6.5 CHANGE:

        `allowed_categories` is temporarily retained
        so the current agent.py does not break.

        It does NOT reject papers anymore.

        `paper_count` is also retained for compatibility,
        but ranking itself does not discard papers.

        Every usable input paper is returned.
        """

        if not papers:
            return []

        logger.info(
            "Starting ranking enrichment for %s paper(s).",
            len(papers),
        )

        enriched_papers: list[Paper] = []

        verified_count = 0
        unverified_count = 0

        for paper in papers:

            enriched_paper = (
                self.verify_paper(
                    paper=paper,
                    allowed_categories=(
                        allowed_categories
                    ),
                )
            )

            if (
                enriched_paper.ranking_verified
            ):

                verified_count += 1

            else:

                unverified_count += 1

            enriched_papers.append(
                enriched_paper
            )

        # --------------------------------------------------
        # LIMIT FINAL OUTPUT ONLY BY USER REQUEST COUNT
        #
        # This is NOT a ranking filter.
        # --------------------------------------------------

        if (
            paper_count is not None
            and paper_count > 0
        ):

            enriched_papers = (
                enriched_papers[
                    :paper_count
                ]
            )

        logger.info(
            "Ranking enrichment completed: "
            "returned=%s, verified=%s, "
            "not_verified=%s.",
            len(enriched_papers),
            verified_count,
            unverified_count,
        )

        return enriched_papers

    # ======================================================
    # ENRICH ONE PAPER
    # ======================================================

    def verify_paper(
        self,
        paper: Paper,
        allowed_categories: list[str] | None = None,
    ) -> Paper:
        """
        Attempt to identify ranking information.

        The paper is ALWAYS returned.

        Ranking failures become:

            category = "Not Verified"
            ranking_verified = False
        """

        # --------------------------------------------------
        # NO ISSN
        # --------------------------------------------------

        if not paper.issns:

            return self._mark_not_verified(
                paper
            )

        normalized_issns: list[str] = []

        for issn in paper.issns:

            normalized = (
                normalize_issn(
                    issn
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

        if not normalized_issns:

            return self._mark_not_verified(
                paper
            )

        # --------------------------------------------------
        # COLLECT MATCHES
        # --------------------------------------------------

        scimago_matches: list[
            dict[str, Any]
        ] = []

        hec_matches: list[
            dict[str, Any]
        ] = []

        for issn in normalized_issns:

            scimago_matches.extend(
                self.scimago_index.get(
                    issn,
                    [],
                )
            )

            hec_matches.extend(
                self.hec_index.get(
                    issn,
                    [],
                )
            )

        # --------------------------------------------------
        # SELECT SCIMAGO RECORD
        # --------------------------------------------------

        scimago_record = (
            self._select_scimago_record(
                records=scimago_matches,
                paper_year=paper.year,
            )
        )

        # --------------------------------------------------
        # SELECT VALID HEC RECORD
        # --------------------------------------------------

        hec_record = (
            self._select_hec_record(
                records=hec_matches,
                paper_year=paper.year,
            )
        )

        # --------------------------------------------------
        # BUILD ALL VERIFIED CATEGORIES
        # --------------------------------------------------

        categories: list[str] = []

        ranking_sources: list[str] = []

        ranking_year: int | None = None

        # SCIMAGO
        if scimago_record:

            quartile = (
                scimago_record.get(
                    "quartile"
                )
            )

            if (
                quartile
                and quartile
                not in categories
            ):

                categories.append(
                    quartile
                )

            ranking_sources.append(
                "SCImago"
            )

            ranking_year = (
                scimago_record.get(
                    "ranking_year"
                )
            )

        # HEC
        if hec_record:

            category = (
                hec_record.get(
                    "category"
                )
            )

            if (
                category
                and category
                not in categories
            ):

                categories.append(
                    category
                )

            if (
                "HEC"
                not in ranking_sources
            ):

                ranking_sources.append(
                    "HEC"
                )

        # --------------------------------------------------
        # NO MATCH
        # --------------------------------------------------

        if not categories:

            return self._mark_not_verified(
                paper
            )

        # --------------------------------------------------
        # PRIMARY CATEGORY
        #
        # Prefer quartile for general international
        # understanding. HEC W remains in verified_categories.
        # --------------------------------------------------

        primary_category = (
            self._select_primary_category(
                categories
            )
        )

        ranking_source = (
            " + ".join(
                ranking_sources
            )
            if ranking_sources
            else None
        )

        # --------------------------------------------------
        # IMPORTANT:
        #
        # We intentionally do NOT check:
        #
        # if category not in allowed_categories:
        #     reject
        #
        # That old behavior is gone.
        # --------------------------------------------------

        return paper.model_copy(
            update={
                "category": (
                    primary_category
                ),
                "verified_categories": (
                    categories
                ),
                "ranking_source": (
                    ranking_source
                ),
                "ranking_year": (
                    ranking_year
                ),
                "ranking_verified": True,
            }
        )

    # ======================================================
    # SELECT SCIMAGO RECORD
    # ======================================================

    @staticmethod
    def _select_scimago_record(
        records: list[dict[str, Any]],
        paper_year: int,
    ) -> dict[str, Any] | None:
        """
        Select the most appropriate SCImago ranking.

        Preferred order:

        1. Ranking year exactly equals publication year
        2. Closest earlier ranking year
        3. Closest available ranking year
        """

        if not records:
            return None

        records_with_year = [
            record
            for record in records
            if isinstance(
                record.get(
                    "ranking_year"
                ),
                int,
            )
        ]

        if not records_with_year:

            return records[0]

        # --------------------------------------------------
        # EXACT YEAR
        # --------------------------------------------------

        exact_matches = [
            record
            for record in records_with_year
            if (
                record.get(
                    "ranking_year"
                )
                == paper_year
            )
        ]

        if exact_matches:

            return exact_matches[0]

        # --------------------------------------------------
        # MOST RECENT YEAR BEFORE PAPER
        # --------------------------------------------------

        earlier_matches = [
            record
            for record in records_with_year
            if (
                record.get(
                    "ranking_year",
                    0,
                )
                <= paper_year
            )
        ]

        if earlier_matches:

            return max(
                earlier_matches,
                key=lambda item: (
                    item.get(
                        "ranking_year",
                        0,
                    )
                ),
            )

        # --------------------------------------------------
        # OTHERWISE CLOSEST AVAILABLE YEAR
        # --------------------------------------------------

        return min(
            records_with_year,
            key=lambda item: abs(
                item.get(
                    "ranking_year",
                    paper_year,
                )
                - paper_year
            ),
        )

    # ======================================================
    # SELECT HEC RECORD
    # ======================================================

    @staticmethod
    def _select_hec_record(
        records: list[dict[str, Any]],
        paper_year: int,
    ) -> dict[str, Any] | None:
        """
        Select an HEC W record valid for the publication year.

        The publication year is compared with valid_from
        and valid_to when those values exist.
        """

        if not records:
            return None

        for record in records:

            valid_from = (
                record.get(
                    "valid_from"
                )
            )

            valid_to = (
                record.get(
                    "valid_to"
                )
            )

            # ----------------------------------------------
            # START / END YEAR
            # ----------------------------------------------

            start_year: int | None = None
            end_year: int | None = None

            if (
                valid_from is not None
                and not pd.isna(
                    valid_from
                )
            ):

                start_year = int(
                    valid_from.year
                )

            if (
                valid_to is not None
                and not pd.isna(
                    valid_to
                )
            ):

                end_year = int(
                    valid_to.year
                )

            # ----------------------------------------------
            # NO DATES AVAILABLE
            # ----------------------------------------------

            if (
                start_year is None
                and end_year is None
            ):

                return record

            # ----------------------------------------------
            # CHECK VALIDITY
            # ----------------------------------------------

            start_ok = (
                start_year is None
                or paper_year >= start_year
            )

            end_ok = (
                end_year is None
                or paper_year <= end_year
            )

            if (
                start_ok
                and end_ok
            ):

                return record

        return None

    # ======================================================
    # SELECT PRIMARY CATEGORY
    # ======================================================

    @staticmethod
    def _select_primary_category(
        categories: list[str],
    ) -> str:
        """
        Select a simple primary ranking label.

        Priority here is for display only.
        It is NOT used to filter results.
        """

        priority = [
            "Q1",
            "Q2",
            "Q3",
            "Q4",
            "W",
        ]

        for category in priority:

            if category in categories:

                return category

        return categories[0]

    # ======================================================
    # MARK NOT VERIFIED
    # ======================================================

    @staticmethod
    def _mark_not_verified(
        paper: Paper,
    ) -> Paper:
        """
        Mark ranking information as unavailable.

        IMPORTANT:
        The paper itself remains completely valid.
        """

        return paper.model_copy(
            update={
                "category": (
                    "Not Verified"
                ),
                "verified_categories": [],
                "ranking_source": None,
                "ranking_year": None,
                "ranking_verified": False,
            }
        )

    # ======================================================
    # HEALTH STATUS
    # ======================================================

    def health_status(
        self,
    ) -> dict[str, str]:
        """
        Return ranking dataset status for Streamlit.
        """

        return {
            "scimago_ranking_data": (
                f"{len(self.scimago_df)} rows"
            ),
            "hec_w_ranking_data": (
                f"{len(self.hec_df)} rows"
            ),
        }

    # ======================================================
    # SAFE STRING
    # ======================================================

    @staticmethod
    def _safe_string(
        value: Any,
    ) -> str | None:
        """
        Convert a dataframe value to a safe string.
        """

        if value is None:
            return None

        try:

            if pd.isna(
                value
            ):

                return None

        except (TypeError, ValueError):

            pass

        cleaned = str(
            value
        ).strip()

        if not cleaned:
            return None

        return cleaned

    # ======================================================
    # SAFE INTEGER
    # ======================================================

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int | None:
        """
        Convert a dataframe value to integer safely.
        """

        if value is None:
            return None

        try:

            if pd.isna(
                value
            ):

                return None

            return int(
                float(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            return None