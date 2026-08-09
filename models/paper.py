"""
Unified research-paper data model.

This model supports papers discovered from multiple
academic sources including:

- OpenAlex
- Crossref
- Semantic Scholar

A paper is NOT rejected merely because:
- it is not open access
- its journal ranking is unavailable
- it is not Q1/Q2/W

Those properties are treated as useful metadata.
"""

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class Paper(BaseModel):
    """
    Standard representation of a research paper.
    """

    # ======================================================
    # BASIC PAPER INFORMATION
    # ======================================================

    title: str = Field(
        min_length=1,
        description="Title of the research paper.",
    )

    authors: list[str] = Field(
        default_factory=list,
        description="List of paper authors.",
    )

    year: int = Field(
        ge=1900,
        le=2100,
        description="Publication year.",
    )

    journal: Optional[str] = Field(
        default=None,
        description="Journal, conference, or publication venue.",
    )

    # ======================================================
    # IDENTIFIERS
    # ======================================================

    doi: Optional[str] = Field(
        default=None,
        description="Digital Object Identifier.",
    )

    issns: list[str] = Field(
        default_factory=list,
        description="Print and electronic ISSNs.",
    )

    # ======================================================
    # JOURNAL RANKING
    # ======================================================

    category: Optional[str] = Field(
        default=None,
        description=(
            "Primary journal category such as "
            "Q1, Q2, Q3, Q4, W, or Not Verified."
        ),
    )

    verified_categories: list[str] = Field(
        default_factory=list,
        description="All verified journal categories.",
    )

    ranking_source: Optional[str] = Field(
        default=None,
        description=(
            "Source used to determine journal ranking."
        ),
    )

    ranking_year: Optional[int] = Field(
        default=None,
        description="Ranking-data year.",
    )

    ranking_verified: bool = Field(
        default=False,
        description=(
            "Whether ranking information was verified."
        ),
    )

    # ======================================================
    # PAPER LINKS
    # ======================================================

    paper_url: Optional[HttpUrl] = Field(
        default=None,
        description=(
            "Main publisher, DOI, repository, "
            "or academic landing-page URL."
        ),
    )

    pdf_url: Optional[HttpUrl] = Field(
        default=None,
        description=(
            "Direct legal open-access PDF URL when available."
        ),
    )

    # ======================================================
    # ACCESS INFORMATION
    # ======================================================

    is_open_access: bool = Field(
        default=False,
        description=(
            "Whether a legal open-access version "
            "has been identified."
        ),
    )

    verified_by_unpaywall: bool = Field(
        default=False,
        description=(
            "Whether Unpaywall checked the paper."
        ),
    )

    oa_status: Optional[str] = Field(
        default=None,
        description="Open-access status.",
    )

    oa_host_type: Optional[str] = Field(
        default=None,
        description=(
            "Location type such as publisher "
            "or repository."
        ),
    )

    access_type: str = Field(
        default="Unknown",
        description=(
            "Human-readable access classification."
        ),
    )

    # ======================================================
    # SEARCH SOURCE INFORMATION
    # ======================================================

    source: str = Field(
        default="Unknown",
        description=(
            "Academic source from which the paper "
            "was discovered."
        ),
    )

    source_url: Optional[HttpUrl] = Field(
        default=None,
        description=(
            "URL of the record on the discovery source."
        ),
    )

    citation_count: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Citation count when supplied by "
            "the discovery source."
        ),
    )

    # ======================================================
    # LINK SELECTION
    # ======================================================

    def preferred_link(self) -> Optional[str]:
        """
        Return the best available paper link.

        Priority:

        1. Free PDF
        2. Main publisher / landing page
        3. Discovery-source page

        IMPORTANT:
        Paid papers are still returned.
        """

        if self.pdf_url:
            return str(
                self.pdf_url
            )

        if self.paper_url:
            return str(
                self.paper_url
            )

        if self.source_url:
            return str(
                self.source_url
            )

        return None

    # ======================================================
    # ACCESS LABEL
    # ======================================================

    def access_label(self) -> str:
        """
        Return beginner-friendly access information.
        """

        if self.pdf_url:
            return "Free PDF"

        if self.is_open_access:
            return "Free / Open Access"

        if self.paper_url:
            return "Publisher / Institutional Access"

        return "Access Unknown"

    # ======================================================
    # RANKING LABEL
    # ======================================================

    def ranking_label(self) -> str:
        """
        Return beginner-friendly ranking information.
        """

        if self.verified_categories:

            return ", ".join(
                self.verified_categories
            )

        if self.category:

            return self.category

        return "Not Verified"