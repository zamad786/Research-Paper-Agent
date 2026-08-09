"""
Application configuration.

This module loads environment variables and provides
centralized settings for the Research Paper Agent.

Configured services:

- Groq AI
- OpenAlex
- Crossref
- Semantic Scholar
- Unpaywall
- Gmail SMTP
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


# ==========================================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================================

load_dotenv()


# ==========================================================
# SETTINGS
# ==========================================================

@dataclass(frozen=True)
class Settings:
    """
    Central immutable application settings.
    """

    # ======================================================
    # APPLICATION
    # ======================================================

    app_name: str
    app_env: str

    # ======================================================
    # GROQ AI
    # ======================================================

    groq_api_key: str
    groq_base_url: str
    groq_model: str

    # ======================================================
    # SEMANTIC SCHOLAR
    # ======================================================

    semantic_scholar_api_key: str
    semantic_scholar_base_url: str

    # ======================================================
    # OPENALEX
    # ======================================================

    openalex_api_key: str
    openalex_email: str
    openalex_base_url: str

    # ======================================================
    # CROSSREF
    # ======================================================

    crossref_base_url: str

    # ======================================================
    # UNPAYWALL
    # ======================================================

    unpaywall_email: str
    unpaywall_base_url: str

    # ======================================================
    # EMAIL
    # ======================================================

    sender_email: str
    sender_app_password: str

    # ======================================================
    # REQUEST SETTINGS
    # ======================================================

    request_timeout: int
    maximum_paper_count: int

    openalex_results_per_request: int
    crossref_results_per_request: int
    semantic_scholar_results_per_request: int


# ==========================================================
# LOAD SETTINGS
# ==========================================================

def load_settings() -> Settings:
    """
    Read settings from environment variables.
    """

    return Settings(
        # ==================================================
        # APPLICATION
        # ==================================================

        app_name=os.getenv(
            "APP_NAME",
            "Research Paper Agent",
        ).strip(),

        app_env=os.getenv(
            "APP_ENV",
            "development",
        ).strip(),

        # ==================================================
        # GROQ
        # ==================================================

        groq_api_key=os.getenv(
            "GROQ_API_KEY",
            "",
        ).strip(),

        groq_base_url=(
            "https://api.groq.com/openai/v1"
        ),

        groq_model=os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-20b",
        ).strip(),

        # ==================================================
        # SEMANTIC SCHOLAR
        # ==================================================

        semantic_scholar_api_key=os.getenv(
            "SEMANTIC_SCHOLAR_API_KEY",
            "",
        ).strip(),

        semantic_scholar_base_url=(
            "https://api.semanticscholar.org/graph/v1"
        ),

        # ==================================================
        # OPENALEX
        # ==================================================

        openalex_api_key=os.getenv(
            "OPENALEX_API_KEY",
            "",
        ).strip(),

        openalex_email=os.getenv(
            "OPENALEX_EMAIL",
            "",
        ).strip(),

        openalex_base_url=(
            "https://api.openalex.org"
        ),

        # ==================================================
        # CROSSREF
        # ==================================================

        crossref_base_url=(
            "https://api.crossref.org"
        ),

        # ==================================================
        # UNPAYWALL
        # ==================================================

        unpaywall_email=os.getenv(
            "UNPAYWALL_EMAIL",
            "",
        ).strip(),

        unpaywall_base_url=(
            "https://api.unpaywall.org/v2"
        ),

        # ==================================================
        # EMAIL
        # ==================================================

        sender_email=os.getenv(
            "SENDER_EMAIL",
            "",
        ).strip(),

        sender_app_password=os.getenv(
            "SENDER_APP_PASSWORD",
            "",
        ).replace(
            " ",
            "",
        ),

        # ==================================================
        # REQUEST SETTINGS
        # ==================================================

        request_timeout=int(
            os.getenv(
                "REQUEST_TIMEOUT",
                "30",
            )
        ),

        maximum_paper_count=int(
            os.getenv(
                "MAXIMUM_PAPER_COUNT",
                "50",
            )
        ),

        openalex_results_per_request=int(
            os.getenv(
                "OPENALEX_RESULTS_PER_REQUEST",
                "100",
            )
        ),

        crossref_results_per_request=int(
            os.getenv(
                "CROSSREF_RESULTS_PER_REQUEST",
                "100",
            )
        ),

        semantic_scholar_results_per_request=int(
            os.getenv(
                "SEMANTIC_SCHOLAR_RESULTS_PER_REQUEST",
                "100",
            )
        ),
    )


# ==========================================================
# GLOBAL SETTINGS
# ==========================================================

settings = load_settings()