"""
Phase 7 final smoke test.

This script checks the AI components of the
Research Paper Agent without sending email.

Tests:

1. Configuration
2. Agent initialization
3. Groq availability
4. Natural-language request parsing
5. SearchRequest validation
6. AI query expansion
7. Health information

IMPORTANT:

This script does NOT send email.
It also does not modify ranking data.
"""

import sys

from agent import ResearchPaperAgent
from config import settings


# ==========================================================
# HELPERS
# ==========================================================


def print_header(
    title: str,
) -> None:
    """
    Print a clear test section.
    """

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_pass(
    message: str,
) -> None:
    """
    Print successful test.
    """

    print(
        f"[PASS] {message}"
    )


def print_fail(
    message: str,
) -> None:
    """
    Print failed test.
    """

    print(
        f"[FAIL] {message}"
    )


# ==========================================================
# MAIN TEST
# ==========================================================


def main() -> int:
    """
    Run Phase 7 smoke tests.
    """

    print_header(
        "RESEARCH PAPER AGENT - PHASE 7 FINAL TEST"
    )

    # ======================================================
    # TEST 1 — CONFIGURATION
    # ======================================================

    print_header(
        "TEST 1 - CONFIGURATION"
    )

    if settings.groq_api_key:

        print_pass(
            "GROQ_API_KEY is configured."
        )

    else:

        print_fail(
            "GROQ_API_KEY is missing."
        )

        return 1

    if settings.groq_model:

        print_pass(
            f"Groq model configured: "
            f"{settings.groq_model}"
        )

    else:

        print_fail(
            "Groq model is missing."
        )

        return 1

    # ======================================================
    # TEST 2 — AGENT INITIALIZATION
    # ======================================================

    print_header(
        "TEST 2 - AGENT INITIALIZATION"
    )

    try:

        agent = (
            ResearchPaperAgent()
        )

        print_pass(
            "ResearchPaperAgent initialized."
        )

    except Exception as error:

        print_fail(
            "ResearchPaperAgent initialization failed."
        )

        print(
            f"Error: {error}"
        )

        return 1

    # ======================================================
    # TEST 3 — GROQ SERVICE
    # ======================================================

    print_header(
        "TEST 3 - GROQ SERVICE"
    )

    if agent.groq_service.is_configured():

        print_pass(
            "Groq service reports Configured."
        )

    else:

        print_fail(
            "Groq service reports Not Configured."
        )

        return 1

    # ======================================================
    # TEST 4 — NATURAL-LANGUAGE PARSING
    # ======================================================

    print_header(
        "TEST 4 - NATURAL LANGUAGE PARSING"
    )

    test_request = (
        "Find 5 recent papers about "
        "federated learning for IoT security "
        "from 2024 to 2026."
    )

    print(
        "Input:"
    )

    print(
        test_request
    )

    try:

        ai_request = (
            agent.create_ai_search_request(
                test_request
            )
        )

        print_pass(
            "Groq successfully parsed "
            "the research request."
        )

        print()
        print(
            f"Keyword     : "
            f"{ai_request.keyword}"
        )

        print(
            f"Start Year  : "
            f"{ai_request.start_year}"
        )

        print(
            f"End Year    : "
            f"{ai_request.end_year}"
        )

        print(
            f"Paper Count : "
            f"{ai_request.paper_count}"
        )

        print(
            f"Categories  : "
            f"{ai_request.categories}"
        )

    except Exception as error:

        print_fail(
            "Natural-language parsing failed."
        )

        print(
            f"Error: {error}"
        )

        return 1

    # ======================================================
    # TEST 5 — FINAL RANKING REQUIREMENT
    # ======================================================

    print_header(
        "TEST 5 - RANKING SAFETY"
    )

    expected_categories = {
        "Q1",
        "Q2",
        "W",
    }

    actual_categories = set(
        ai_request.categories
    )

    if (
        actual_categories
        == expected_categories
    ):

        print_pass(
            "SearchRequest contains only "
            "Q1, Q2 and W."
        )

    else:

        print_fail(
            "Unexpected final ranking categories: "
            f"{actual_categories}"
        )

        return 1

    # ======================================================
    # TEST 6 — QUERY EXPANSION
    # ======================================================

    print_header(
        "TEST 6 - AI QUERY EXPANSION"
    )

    try:

        queries = (
            agent.groq_service.expand_search_query(
                ai_request.keyword
            )
        )

        if not queries:

            print_fail(
                "Groq returned no query variations."
            )

            return 1

        print_pass(
            f"Groq generated "
            f"{len(queries)} search phrase(s)."
        )

        print()

        for index, query in enumerate(
            queries,
            start=1,
        ):

            print(
                f"{index}. {query}"
            )

        # --------------------------------------------------
        # SAFETY
        # --------------------------------------------------

        if len(queries) <= 3:

            print_pass(
                "Query-expansion safety limit "
                "is respected."
            )

        else:

            print_fail(
                "More than 3 search queries "
                "were returned."
            )

            return 1

    except Exception as error:

        print_fail(
            "AI query expansion failed."
        )

        print(
            f"Error: {error}"
        )

        return 1

    # ======================================================
    # TEST 7 — MANUAL SEARCH REQUEST
    # ======================================================

    print_header(
        "TEST 7 - MANUAL SEARCH REQUEST"
    )

    try:

        manual_request = (
            agent.create_search_request(
                keyword=(
                    "federated learning "
                    "for IoT security"
                ),
                start_year=2024,
                end_year=2026,
                paper_count=5,
                categories=[
                    "Q1",
                    "Q2",
                    "W",
                ],
            )
        )

        print_pass(
            "Manual SearchRequest created."
        )

        print(
            manual_request
        )

    except Exception as error:

        print_fail(
            "Manual SearchRequest failed."
        )

        print(
            f"Error: {error}"
        )

        return 1

    # ======================================================
    # TEST 8 — HEALTH CHECK
    # ======================================================

    print_header(
        "TEST 8 - APPLICATION HEALTH"
    )

    try:

        health = (
            agent.health_check()
        )

        for key, value in (
            health.items()
        ):

            print(
                f"{key}: {value}"
            )

        print_pass(
            "Health information generated."
        )

    except Exception as error:

        print_fail(
            "Health check failed."
        )

        print(
            f"Error: {error}"
        )

        return 1

    # ======================================================
    # COMPLETE
    # ======================================================

    print_header(
        "PHASE 7 SMOKE TEST COMPLETE"
    )

    print_pass(
        "Core Phase 7 AI components passed."
    )

    print()
    print(
        "Next: perform the full Streamlit "
        "AI/manual/email workflow test."
    )

    return 0


# ==========================================================
# ENTRY POINT
# ==========================================================


if __name__ == "__main__":

    sys.exit(
        main()
    )