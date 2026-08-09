"""Small reusable helper functions."""

import re
from typing import Any


def clean_doi(doi: str | None) -> str | None:
    """
    Normalize a DOI.

    Example:
        https://doi.org/10.1000/example
        becomes
        10.1000/example
    """

    if not doi:
        return None

    cleaned_doi = doi.strip()

    cleaned_doi = re.sub(
        r"^https?://(dx\.)?doi\.org/",
        "",
        cleaned_doi,
        flags=re.IGNORECASE,
    )

    return cleaned_doi or None


def normalize_issn(issn: str | None) -> str | None:
    """
    Normalize an ISSN to the form XXXX-XXXX.

    Returns None when the value does not contain eight characters.
    """

    if not issn:
        return None

    cleaned_issn = re.sub(
        r"[^0-9Xx]",
        "",
        issn,
    ).upper()

    if len(cleaned_issn) != 8:
        return None

    return f"{cleaned_issn[:4]}-{cleaned_issn[4:]}"


def remove_duplicates(
    values: list[Any],
) -> list[Any]:
    """Remove duplicate items while preserving their order."""

    return list(dict.fromkeys(values))


def format_authors(
    authors: list[str],
    maximum_authors: int = 3,
) -> str:
    """Format an author list for display."""

    if not authors:
        return "Authors unavailable"

    if len(authors) <= maximum_authors:
        return ", ".join(authors)

    visible_authors = ", ".join(authors[:maximum_authors])

    return f"{visible_authors}, et al."