"""
Input validation functions.

These functions validate user input before the agent starts
searching external services.
"""

import re
from datetime import datetime


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def validate_keyword(keyword: str) -> str:
    """
    Validate and clean a paper-search keyword.

    Args:
        keyword: User-provided research topic.

    Returns:
        Cleaned keyword.

    Raises:
        ValueError: When the keyword is missing or too short.
    """

    cleaned_keyword = " ".join(keyword.strip().split())

    if not cleaned_keyword:
        raise ValueError("Please enter a research keyword.")

    if len(cleaned_keyword) < 3:
        raise ValueError(
            "The research keyword must contain at least 3 characters."
        )

    return cleaned_keyword


def validate_year_range(
    start_year: int,
    end_year: int,
) -> tuple[int, int]:
    """
    Validate the selected publication-year range.

    Returns:
        A validated start-year and end-year tuple.
    """

    current_year = datetime.now().year

    if start_year < 1900:
        raise ValueError("The start year cannot be earlier than 1900.")

    if end_year > current_year:
        raise ValueError(
            f"The end year cannot be later than {current_year}."
        )

    if start_year > end_year:
        raise ValueError(
            "The start year cannot be greater than the end year."
        )

    return start_year, end_year


def validate_paper_count(
    paper_count: int,
    maximum: int = 50,
) -> int:
    """Validate the number of requested papers."""

    if paper_count < 1:
        raise ValueError("Please request at least one paper.")

    if paper_count > maximum:
        raise ValueError(
            f"You can request a maximum of {maximum} papers."
        )

    return paper_count


def validate_categories(categories: list[str]) -> list[str]:
    """Validate the selected journal categories."""

    allowed_categories = {"Q1", "Q2", "W"}

    cleaned_categories = [
        category.strip().upper()
        for category in categories
        if category.strip()
    ]

    if not cleaned_categories:
        raise ValueError(
            "Please select at least one category: Q1, Q2, or W."
        )

    invalid_categories = set(cleaned_categories) - allowed_categories

    if invalid_categories:
        invalid_text = ", ".join(sorted(invalid_categories))
        raise ValueError(
            f"Invalid journal categories selected: {invalid_text}."
        )

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(cleaned_categories))


def validate_email(email: str) -> str:
    """Validate and normalize an email address."""

    cleaned_email = email.strip().lower()

    if not cleaned_email:
        raise ValueError("Please enter a recipient email address.")

    if not EMAIL_PATTERN.fullmatch(cleaned_email):
        raise ValueError("Please enter a valid email address.")

    return cleaned_email