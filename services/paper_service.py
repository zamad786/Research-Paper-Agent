"""
Research-paper processing and multi-source merging service.

Phase 6.5.7

The PaperService now performs intelligent merging of papers
discovered from multiple academic sources:

- OpenAlex
- Crossref
- Semantic Scholar

Instead of simply deleting duplicate records, duplicate
records are COMBINED so useful metadata from every source
can be preserved.

Example:

OpenAlex:
    DOI + ISSN + journal

Crossref:
    DOI + publisher metadata

Semantic Scholar:
    citation count + free PDF

Result:
    ONE enriched Paper object containing the best
    available metadata from all three sources.

Important:
- Paid papers are kept.
- Open-access papers are kept.
- Papers without DOI are kept.
- Papers without ISSN are kept.
- Papers without ranking information are kept.
"""

from models import Paper
from utils.helpers import (
    clean_doi,
    normalize_issn,
    remove_duplicates,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class PaperService:
    """
    Prepare, merge, deduplicate, and limit research papers.
    """

    # ======================================================
    # PREPARE INITIAL CANDIDATES
    # ======================================================

    def prepare_candidates(
        self,
        papers: list[Paper],
        start_year: int,
        end_year: int,
    ) -> list[Paper]:
        """
        Prepare papers discovered by academic sources.

        Papers do NOT need:
        - DOI
        - ISSN
        - open access
        - ranking

        They only need useful metadata and at least
        one usable link.
        """

        if not papers:
            return []

        candidates: list[Paper] = []

        for paper in papers:

            # --------------------------------------------------
            # YEAR
            # --------------------------------------------------

            if not (
                start_year
                <= paper.year
                <= end_year
            ):
                continue

            # --------------------------------------------------
            # TITLE
            # --------------------------------------------------

            if not paper.title.strip():
                continue

            # --------------------------------------------------
            # LINK
            # --------------------------------------------------

            if not paper.preferred_link():
                continue

            # --------------------------------------------------
            # NORMALIZE DOI
            # --------------------------------------------------

            normalized_doi = clean_doi(
                paper.doi
            )

            # --------------------------------------------------
            # NORMALIZE ISSNS
            # --------------------------------------------------

            normalized_issns: list[str] = []

            for issn in paper.issns:

                normalized = normalize_issn(
                    issn
                )

                if (
                    normalized
                    and normalized
                    not in normalized_issns
                ):
                    normalized_issns.append(
                        normalized
                    )

            # --------------------------------------------------
            # UPDATE NORMALIZED METADATA
            # --------------------------------------------------

            paper = paper.model_copy(
                update={
                    "doi": normalized_doi,
                    "issns": normalized_issns,
                }
            )

            candidates.append(
                paper
            )

        # --------------------------------------------------
        # INTELLIGENT MULTI-SOURCE MERGING
        # --------------------------------------------------

        merged_papers = (
            self.merge_duplicate_papers(
                candidates
            )
        )

        logger.info(
            "Candidate preparation completed: "
            "input=%s, usable=%s, merged=%s.",
            len(papers),
            len(candidates),
            len(merged_papers),
        )

        return merged_papers

    # ======================================================
    # PREPARE ENRICHED PAPERS
    # ======================================================

    def prepare_verified_candidates(
        self,
        papers: list[Paper],
    ) -> list[Paper]:
        """
        Compatibility method retained from the old pipeline.

        Despite the method name, papers DO NOT need to be
        verified or open access.

        This stage now:
        - checks basic usability
        - intelligently merges duplicates
        """

        if not papers:
            return []

        candidates: list[Paper] = []

        for paper in papers:

            if not paper.title.strip():
                continue

            if not paper.preferred_link():
                continue

            candidates.append(
                paper
            )

        return self.merge_duplicate_papers(
            candidates
        )

    # ======================================================
    # MULTI-SOURCE PAPER MERGER
    # ======================================================

    def merge_duplicate_papers(
        self,
        papers: list[Paper],
    ) -> list[Paper]:
        """
        Merge duplicate papers rather than simply
        deleting duplicate records.

        Matching priority:

        1. DOI
        2. Normalized title + publication year

        When duplicates are found, useful metadata from
        both records is combined.
        """

        if not papers:
            return []

        merged_papers: list[Paper] = []

        doi_index: dict[str, int] = {}

        title_year_index: dict[str, int] = {}

        for paper in papers:

            doi_key = (
                self._doi_key(
                    paper.doi
                )
            )

            title_year_key = (
                self._title_year_key(
                    paper
                )
            )

            existing_index: int | None = None

            # --------------------------------------------------
            # FIRST TRY DOI
            # --------------------------------------------------

            if (
                doi_key
                and doi_key in doi_index
            ):

                existing_index = (
                    doi_index[
                        doi_key
                    ]
                )

            # --------------------------------------------------
            # FALLBACK TO TITLE + YEAR
            # --------------------------------------------------

            elif (
                title_year_key
                in title_year_index
            ):

                existing_index = (
                    title_year_index[
                        title_year_key
                    ]
                )

            # --------------------------------------------------
            # NEW PAPER
            # --------------------------------------------------

            if existing_index is None:

                merged_papers.append(
                    paper
                )

                new_index = (
                    len(merged_papers)
                    - 1
                )

                if doi_key:

                    doi_index[
                        doi_key
                    ] = new_index

                title_year_index[
                    title_year_key
                ] = new_index

                continue

            # --------------------------------------------------
            # DUPLICATE FOUND → MERGE
            # --------------------------------------------------

            existing_paper = (
                merged_papers[
                    existing_index
                ]
            )

            merged_paper = (
                self._merge_two_papers(
                    existing_paper,
                    paper,
                )
            )

            merged_papers[
                existing_index
            ] = merged_paper

            # --------------------------------------------------
            # REBUILD KEYS AFTER MERGING
            #
            # The merged record may have gained a DOI.
            # --------------------------------------------------

            merged_doi_key = (
                self._doi_key(
                    merged_paper.doi
                )
            )

            merged_title_key = (
                self._title_year_key(
                    merged_paper
                )
            )

            if merged_doi_key:

                doi_index[
                    merged_doi_key
                ] = existing_index

            title_year_index[
                merged_title_key
            ] = existing_index

            # --------------------------------------------------
            # ALSO REMEMBER INCOMING KEYS
            # --------------------------------------------------

            if doi_key:

                doi_index[
                    doi_key
                ] = existing_index

            title_year_index[
                title_year_key
            ] = existing_index

        logger.info(
            "Multi-source merge completed: "
            "input=%s, unique_merged=%s.",
            len(papers),
            len(merged_papers),
        )

        return merged_papers

    # ======================================================
    # MERGE TWO PAPER OBJECTS
    # ======================================================

    def _merge_two_papers(
        self,
        first: Paper,
        second: Paper,
    ) -> Paper:
        """
        Combine useful metadata from two representations
        of the same scholarly work.
        """

        # ==================================================
        # TITLE
        #
        # Prefer the longer non-empty title because it often
        # contains the complete title rather than a shortened
        # metadata variant.
        # ==================================================

        title = self._choose_better_text(
            first.title,
            second.title,
        )

        # ==================================================
        # AUTHORS
        # ==================================================

        authors = remove_duplicates(
            first.authors
            + second.authors
        )

        # ==================================================
        # YEAR
        #
        # Since duplicate matching requires compatible
        # records, keep the first valid publication year.
        # ==================================================

        year = (
            first.year
            or second.year
        )

        # ==================================================
        # JOURNAL / VENUE
        # ==================================================

        journal = (
            first.journal
            or second.journal
        )

        # ==================================================
        # DOI
        # ==================================================

        doi = (
            clean_doi(
                first.doi
            )
            or clean_doi(
                second.doi
            )
        )

        # ==================================================
        # ISSNS
        # ==================================================

        issns: list[str] = []

        for issn in (
            first.issns
            + second.issns
        ):

            normalized = (
                normalize_issn(
                    issn
                )
            )

            if (
                normalized
                and normalized
                not in issns
            ):

                issns.append(
                    normalized
                )

        # ==================================================
        # FREE PDF
        #
        # If ANY discovery source found a free PDF,
        # preserve it.
        # ==================================================

        pdf_url = (
            first.pdf_url
            or second.pdf_url
        )

        # ==================================================
        # MAIN PAPER / PUBLISHER URL
        # ==================================================

        paper_url = (
            self._select_paper_url(
                first,
                second,
            )
        )

        # ==================================================
        # DISCOVERY SOURCE URL
        # ==================================================

        source_url = (
            first.source_url
            or second.source_url
        )

        # ==================================================
        # ACCESS
        # ==================================================

        is_open_access = bool(
            first.is_open_access
            or second.is_open_access
            or pdf_url
        )

        verified_by_unpaywall = bool(
            first.verified_by_unpaywall
            or second.verified_by_unpaywall
        )

        oa_status = (
            first.oa_status
            or second.oa_status
        )

        oa_host_type = (
            first.oa_host_type
            or second.oa_host_type
        )

        if pdf_url:

            access_type = (
                "Free PDF"
            )

        elif is_open_access:

            access_type = (
                "Free / Open Access"
            )

        elif (
            paper_url
            or source_url
        ):

            access_type = (
                "Publisher / Institutional Access"
            )

        else:

            access_type = (
                "Access Unknown"
            )

        # ==================================================
        # CITATION COUNT
        #
        # Different academic indexes may report slightly
        # different citation totals.
        #
        # For discovery display we keep the highest
        # available value.
        # ==================================================

        citation_values = [
            value
            for value in [
                first.citation_count,
                second.citation_count,
            ]
            if isinstance(
                value,
                int,
            )
        ]

        citation_count = (
            max(
                citation_values
            )
            if citation_values
            else None
        )

        # ==================================================
        # DISCOVERY SOURCES
        #
        # Example:
        #
        # OpenAlex + Crossref + Semantic Scholar
        # ==================================================

        source = (
            self._merge_source_names(
                first.source,
                second.source,
            )
        )

        # ==================================================
        # RANKING INFORMATION
        #
        # Normally ranking happens AFTER discovery merging,
        # but these fields are preserved in case this method
        # is called later in the pipeline.
        # ==================================================

        (
            category,
            verified_categories,
            ranking_source,
            ranking_year,
            ranking_verified,
        ) = self._merge_ranking_information(
            first,
            second,
        )

        # ==================================================
        # CREATE MERGED PAPER
        # ==================================================

        return first.model_copy(
            update={
                "title": title,
                "authors": authors,
                "year": year,
                "journal": journal,
                "doi": doi,
                "issns": issns,

                "category": category,

                "verified_categories": (
                    verified_categories
                ),

                "ranking_source": (
                    ranking_source
                ),

                "ranking_year": (
                    ranking_year
                ),

                "ranking_verified": (
                    ranking_verified
                ),

                "paper_url": (
                    paper_url
                ),

                "pdf_url": (
                    pdf_url
                ),

                "source_url": (
                    source_url
                ),

                "is_open_access": (
                    is_open_access
                ),

                "verified_by_unpaywall": (
                    verified_by_unpaywall
                ),

                "oa_status": (
                    oa_status
                ),

                "oa_host_type": (
                    oa_host_type
                ),

                "access_type": (
                    access_type
                ),

                "source": (
                    source
                ),

                "citation_count": (
                    citation_count
                ),
            }
        )

    # ======================================================
    # RANKING MERGER
    # ======================================================

    @staticmethod
    def _merge_ranking_information(
        first: Paper,
        second: Paper,
    ) -> tuple[
        str | None,
        list[str],
        str | None,
        int | None,
        bool,
    ]:
        """
        Preserve the strongest available ranking metadata.
        """

        ranking_verified = bool(
            first.ranking_verified
            or second.ranking_verified
        )

        verified_categories = (
            remove_duplicates(
                first.verified_categories
                + second.verified_categories
            )
        )

        # --------------------------------------------------
        # VERIFIED CATEGORY
        # --------------------------------------------------

        if first.ranking_verified:

            category = (
                first.category
            )

        elif second.ranking_verified:

            category = (
                second.category
            )

        else:

            category = (
                first.category
                or second.category
            )

        # --------------------------------------------------
        # RANKING SOURCE
        # --------------------------------------------------

        ranking_sources: list[str] = []

        for source in [
            first.ranking_source,
            second.ranking_source,
        ]:

            if not source:
                continue

            for part in (
                source.split("+")
            ):

                cleaned = (
                    part.strip()
                )

                if (
                    cleaned
                    and cleaned
                    not in ranking_sources
                ):

                    ranking_sources.append(
                        cleaned
                    )

        ranking_source = (
            " + ".join(
                ranking_sources
            )
            if ranking_sources
            else None
        )

        ranking_year = (
            first.ranking_year
            or second.ranking_year
        )

        return (
            category,
            verified_categories,
            ranking_source,
            ranking_year,
            ranking_verified,
        )

    # ======================================================
    # SELECT PAPER URL
    # ======================================================

    @staticmethod
    def _select_paper_url(
        first: Paper,
        second: Paper,
    ) -> str | None:
        """
        Choose the best normal paper/publisher page.

        We prefer a regular paper URL rather than a
        discovery-source URL.
        """

        candidates = [
            first.paper_url,
            second.paper_url,
        ]

        # --------------------------------------------------
        # PREFER NON-SEMANTIC-SCHOLAR RECORD PAGE
        # --------------------------------------------------

        for candidate in candidates:

            if not candidate:
                continue

            url = str(
                candidate
            )

            if (
                "semanticscholar.org/paper/"
                not in url.lower()
            ):

                return url

        # --------------------------------------------------
        # FALLBACK
        # --------------------------------------------------

        for candidate in candidates:

            if candidate:

                return str(
                    candidate
                )

        return None

    # ======================================================
    # MERGE SOURCE NAMES
    # ======================================================

    @staticmethod
    def _merge_source_names(
        first_source: str | None,
        second_source: str | None,
    ) -> str:
        """
        Merge discovery/enrichment source names without
        producing duplicate labels.

        Example:

        OpenAlex + Unpaywall
        +
        Crossref

        becomes:

        OpenAlex + Unpaywall + Crossref
        """

        sources: list[str] = []

        for source_value in [
            first_source,
            second_source,
        ]:

            if not source_value:
                continue

            for source_part in (
                source_value.split("+")
            ):

                cleaned = (
                    source_part.strip()
                )

                if (
                    cleaned
                    and cleaned not in sources
                ):

                    sources.append(
                        cleaned
                    )

        return (
            " + ".join(
                sources
            )
            if sources
            else "Unknown"
        )

    # ======================================================
    # REMOVE DUPLICATES
    #
    # Kept for compatibility with agent.py.
    #
    # It now performs MERGING rather than throwing
    # useful metadata away.
    # ======================================================

    def remove_duplicate_papers(
        self,
        papers: list[Paper],
    ) -> list[Paper]:
        """
        Compatibility wrapper.

        Old behavior:
            Remove duplicates.

        Phase 6.5.7 behavior:
            Merge duplicates.
        """

        return self.merge_duplicate_papers(
            papers
        )

    # ======================================================
    # LIMIT PAPERS
    # ======================================================

    @staticmethod
    def limit_papers(
        papers: list[Paper],
        paper_count: int,
    ) -> list[Paper]:
        """
        Return the number of results requested by the user.

        This is only a result-count limit.
        """

        if paper_count <= 0:

            return []

        return papers[
            :paper_count
        ]

    # ======================================================
    # DOI KEY
    # ======================================================

    @staticmethod
    def _doi_key(
        doi: str | None,
    ) -> str | None:
        """
        Build normalized DOI matching key.
        """

        cleaned = clean_doi(
            doi
        )

        if not cleaned:

            return None

        return (
            cleaned
            .strip()
            .lower()
        )

    # ======================================================
    # TITLE + YEAR KEY
    # ======================================================

    @classmethod
    def _title_year_key(
        cls,
        paper: Paper,
    ) -> str:
        """
        Build fallback duplicate key.
        """

        title = (
            cls._normalize_title(
                paper.title
            )
        )

        return (
            f"{title}|{paper.year}"
        )

    # ======================================================
    # NORMALIZE TITLE
    # ======================================================

    @staticmethod
    def _normalize_title(
        title: str,
    ) -> str:
        """
        Normalize paper title for duplicate matching.
        """

        normalized = (
            title
            .lower()
            .strip()
        )

        # --------------------------------------------------
        # REMOVE COMMON PUNCTUATION DIFFERENCES
        # --------------------------------------------------

        replacements = {
            ":": " ",
            ";": " ",
            ",": " ",
            ".": " ",
            "-": " ",
            "–": " ",
            "—": " ",
            "(": " ",
            ")": " ",
            "[": " ",
            "]": " ",
            "{": " ",
            "}": " ",
            "/": " ",
        }

        for old, new in (
            replacements.items()
        ):

            normalized = (
                normalized.replace(
                    old,
                    new,
                )
            )

        return " ".join(
            normalized.split()
        )

    # ======================================================
    # BETTER TEXT
    # ======================================================

    @staticmethod
    def _choose_better_text(
        first: str | None,
        second: str | None,
    ) -> str:
        """
        Choose the more complete non-empty text.
        """

        first_clean = (
            str(first).strip()
            if first
            else ""
        )

        second_clean = (
            str(second).strip()
            if second
            else ""
        )

        if not first_clean:

            return second_clean

        if not second_clean:

            return first_clean

        if (
            len(second_clean)
            > len(first_clean)
        ):

            return second_clean

        return first_clean