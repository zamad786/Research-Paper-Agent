"""
Groq AI service for the Research Paper Agent.

Phase 7.

Responsibilities:

1. Understand natural-language research requests.
2. Convert user requests into structured search parameters.
3. Expand academic search terminology.
4. Support later relevance-ranking functionality.

IMPORTANT:

Groq AI does NOT determine journal ranking.

Q1 / Q2 / HEC W verification remains the
responsibility of RankingService and verified
ranking datasets.
"""

import json
from datetime import datetime
from typing import Any

import requests

from config import Settings
from models import Paper
from utils.logger import get_logger


logger = get_logger(__name__)


# ==========================================================
# CUSTOM ERROR
# ==========================================================


class GroqServiceError(Exception):
    """
    Raised when Groq AI processing fails.
    """


# ==========================================================
# GROQ SERVICE
# ==========================================================


class GroqService:
    """
    AI intelligence layer for the Research Paper Agent.
    """

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        """
        Initialize Groq API configuration.
        """

        self.settings = settings

        self.base_url = (
            self.settings.groq_base_url.rstrip("/")
        )

        self.model = (
            self.settings.groq_model
        )

        self.chat_url = (
            f"{self.base_url}/chat/completions"
        )

        self.session = (
            requests.Session()
        )

        self.session.headers.update(
            {
                "Authorization": (
                    "Bearer "
                    f"{self.settings.groq_api_key}"
                ),
                "Content-Type": (
                    "application/json"
                ),
                "Accept": (
                    "application/json"
                ),
            }
        )

    # ======================================================
    # AVAILABILITY
    # ======================================================

    def is_configured(
        self,
    ) -> bool:
        """
        Return True when a Groq API key exists.
        """

        return bool(
            self.settings.groq_api_key
        )

    # ======================================================
    # PARSE NATURAL-LANGUAGE SEARCH
    # ======================================================

    def parse_search_request(
        self,
        user_request: str,
    ) -> dict[str, Any]:
        """
        Convert a natural-language research request into
        structured search parameters.

        Example input:

            Find 8 recent papers about federated learning
            for IoT security from 2024 to 2026.

        Example output:

            {
                "keyword":
                    "federated learning for IoT security",

                "start_year":
                    2024,

                "end_year":
                    2026,

                "paper_count":
                    8
            }

        IMPORTANT:

        Journal ranking is deliberately NOT generated
        by Groq.

        The application's fixed ranking requirement
        remains:

            Q1
            Q2
            HEC W
        """

        if not self.is_configured():

            raise GroqServiceError(
                "Groq AI is not configured. "
                "Add GROQ_API_KEY to the .env file."
            )

        cleaned_request = (
            user_request.strip()
        )

        if not cleaned_request:

            raise GroqServiceError(
                "Please enter a research request."
            )

        current_year = (
            datetime.now().year
        )

        # ==================================================
        # STRICT JSON SCHEMA
        # ==================================================

        schema = {
            "type": "object",

            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "Clean academic search topic "
                        "without ranking instructions."
                    ),
                },

                "start_year": {
                    "type": "integer",
                    "minimum": 1900,
                    "maximum": current_year,
                },

                "end_year": {
                    "type": "integer",
                    "minimum": 1900,
                    "maximum": current_year,
                },

                "paper_count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": (
                        self.settings.maximum_paper_count
                    ),
                },
            },

            "required": [
                "keyword",
                "start_year",
                "end_year",
                "paper_count",
            ],

            "additionalProperties": False,
        }

        # ==================================================
        # SYSTEM INSTRUCTIONS
        # ==================================================

        system_prompt = f"""
You are the natural-language search parser for a
research-paper discovery application.

Your ONLY task is to convert the user's request into
structured academic-search parameters.

Current year:
{current_year}

The application itself only returns journal papers
verified as Q1, Q2, or HEC W.

DO NOT attempt to determine journal rankings.

DO NOT put Q1, Q2, W, quartile, ranking, SCImago,
or HEC filtering terms into the keyword unless those
terms are genuinely part of the scientific research
topic itself.

Extract:

1. keyword
   A concise academic search phrase preserving the
   user's actual research topic.

2. start_year
   Beginning publication year.

3. end_year
   Ending publication year.

4. paper_count
   Number of papers requested.

Defaults when the user does not specify values:

- paper_count = 5
- end_year = {current_year}
- start_year = {max(1900, current_year - 3)}

If the user says:
- latest
- recent
- newest

and gives no explicit years, use the default recent
year window above.

start_year must never be later than end_year.

Return only the requested structured data.
""".strip()

        payload = {
            "model": (
                self.model
            ),

            "messages": [
                {
                    "role": "system",
                    "content": (
                        system_prompt
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        cleaned_request
                    ),
                },
            ],

            "temperature": 0,

            "reasoning_effort": (
                "low"
            ),

            "reasoning_format": (
                "hidden"
            ),

            "response_format": {
                "type": (
                    "json_schema"
                ),

                "json_schema": {
                    "name": (
                        "research_search_request"
                    ),

                    "strict": True,

                    "schema": (
                        schema
                    ),
                },
            },
        }

        logger.info(
            "Sending natural-language search "
            "request to Groq."
        )

        response_data = (
            self._send_chat_request(
                payload
            )
        )

        content = (
            self._extract_content(
                response_data
            )
        )

        try:

            parsed = (
                json.loads(
                    content
                )
            )

        except json.JSONDecodeError as error:

            raise GroqServiceError(
                "Groq returned invalid structured "
                "search data."
            ) from error

        # ==================================================
        # FINAL LOCAL VALIDATION
        # ==================================================

        return self._validate_search_intent(
            parsed
        )

    # ======================================================
    # EXPAND SEARCH KEYWORD
    # ======================================================

    def expand_search_query(
        self,
        keyword: str,
    ) -> list[str]:
        """
        Generate academic search-query variations.

        Example:

        Input:
            federated learning for IoT security

        Output:
            [
                "federated learning for IoT security",
                "federated intrusion detection IoT",
                "federated cybersecurity Internet of Things"
            ]

        IMPORTANT:

        These are search phrases only.

        Groq does NOT label papers as Q1/Q2/W.
        """

        if not self.is_configured():

            raise GroqServiceError(
                "Groq AI is not configured."
            )

        cleaned_keyword = (
            keyword.strip()
        )

        if not cleaned_keyword:

            return []

        schema = {
            "type": "object",

            "properties": {
                "queries": {
                    "type": "array",

                    "items": {
                        "type": "string",
                    },

                    "minItems": 3,
                    "maxItems": 3,
                },
            },

            "required": [
                "queries",
            ],

            "additionalProperties": False,
        }

        system_prompt = """
You improve academic database search queries.

Generate exactly 3 concise scholarly search phrases
for the supplied research topic.

Rules:

1. The first query should preserve the original topic.
2. The second may use useful academic synonyms.
3. The third may use closely related technical terms.
4. Preserve the user's research meaning.
5. Do not invent unrelated topics.
6. Do not add Q1, Q2, Q3, Q4, HEC, W, SCImago,
   ranking, quartile, open access, or publisher filters.
7. Journal ranking is handled separately by the
   application.
""".strip()

        payload = {
            "model": (
                self.model
            ),

            "messages": [
                {
                    "role": "system",
                    "content": (
                        system_prompt
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        cleaned_keyword
                    ),
                },
            ],

            "temperature": 0.2,

            "reasoning_effort": (
                "low"
            ),

            "reasoning_format": (
                "hidden"
            ),

            "response_format": {
                "type": (
                    "json_schema"
                ),

                "json_schema": {
                    "name": (
                        "academic_query_expansion"
                    ),

                    "strict": True,

                    "schema": (
                        schema
                    ),
                },
            },
        }

        response_data = (
            self._send_chat_request(
                payload
            )
        )

        content = (
            self._extract_content(
                response_data
            )
        )

        try:

            parsed = (
                json.loads(
                    content
                )
            )

        except json.JSONDecodeError as error:

            raise GroqServiceError(
                "Groq returned invalid query "
                "expansion data."
            ) from error

        raw_queries = (
            parsed.get(
                "queries"
            )
            or []
        )

        queries: list[str] = []

        # --------------------------------------------------
        # ALWAYS KEEP ORIGINAL QUERY
        # --------------------------------------------------

        queries.append(
            cleaned_keyword
        )

        for query in raw_queries:

            cleaned_query = (
                str(
                    query
                ).strip()
            )

            if not cleaned_query:

                continue

            if (
                cleaned_query.lower()
                in {
                    existing.lower()
                    for existing in queries
                }
            ):

                continue

            queries.append(
                cleaned_query
            )

            if len(queries) >= 3:

                break

        logger.info(
            "Groq generated %s academic "
            "search query variation(s).",
            len(queries),
        )

        return queries

    # ======================================================
    # RANK PAPERS BY RELEVANCE
    # ======================================================

    def rank_papers_by_relevance(
        self,
        keyword: str,
        papers: list[Paper],
    ) -> list[Paper]:
        """
        Order already-verified papers according to their
        relevance to the user's research topic.

        IMPORTANT:

        This method does NOT:

        - verify journal rankings
        - assign Q1
        - assign Q2
        - assign HEC W
        - change ranking metadata
        - remove papers because of access type

        It only changes the ORDER of papers that have
        already passed the application's ranking filter.

        If Groq fails, the original paper order is returned.
        """

        # ==================================================
        # BASIC SAFETY
        # ==================================================

        cleaned_keyword = (
            keyword.strip()
        )

        if not cleaned_keyword:

            return papers

        if not papers:

            return []

        if len(papers) == 1:

            return papers

        if not self.is_configured():

            logger.warning(
                "Groq relevance ranking skipped because "
                "Groq is not configured."
            )

            return papers

        # ==================================================
        # BUILD PAPER METADATA
        #
        # We give Groq only real metadata already present
        # in our Paper objects.
        #
        # Groq does not generate new paper information.
        # ==================================================

        paper_records: list[dict[str, Any]] = []

        for index, paper in enumerate(
            papers
        ):

            paper_records.append(
                {
                    "index": index,

                    "title": (
                        paper.title
                    ),

                    "year": (
                        paper.year
                    ),

                    "journal": (
                        paper.journal
                        or ""
                    ),

                    "authors": (
                        paper.authors[:5]
                    ),

                    "verified_ranking": (
                        paper.ranking_label()
                    ),

                    "citation_count": (
                        paper.citation_count
                        if (
                            paper.citation_count
                            is not None
                        )
                        else 0
                    ),
                }
            )

        # ==================================================
        # STRUCTURED OUTPUT SCHEMA
        # ==================================================

        schema = {
            "type": "object",

            "properties": {
                "ranked_indices": {
                    "type": "array",

                    "items": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": (
                            len(papers) - 1
                        ),
                    },

                    "minItems": len(papers),

                    "maxItems": len(papers),

                    "uniqueItems": True,
                },
            },

            "required": [
                "ranked_indices",
            ],

            "additionalProperties": False,
        }

        # ==================================================
        # SYSTEM PROMPT
        # ==================================================

        system_prompt = """
You are the relevance-ranking component of a
research-paper discovery application.

You receive:

1. A research topic.
2. A list of research papers that have ALREADY been
   verified by the application.

Your ONLY task is to order the supplied paper indices
from most relevant to least relevant for the research
topic.

IMPORTANT RULES:

1. Rank using the supplied metadata only.
2. Give highest priority to direct topical relevance.
3. Paper title is the strongest relevance signal.
4. Journal/venue and authors may provide supporting context.
5. Publication year and citation count may be used only
   as secondary tie-breakers.
6. Do not invent information about any paper.
7. Do not remove any paper.
8. Return every supplied index exactly once.
9. Do not determine journal ranking.
10. Do not modify Q1, Q2 or HEC W information.
11. Do not favor a paper simply because it is open access.
12. Do not generate new papers.
13. Return only the required structured output.

The journal-ranking information is supplied only as
existing metadata. It must NOT be reassessed or changed.
""".strip()

        # ==================================================
        # USER CONTENT
        # ==================================================

        user_content = {
            "research_topic": (
                cleaned_keyword
            ),

            "papers": (
                paper_records
            ),
        }

        payload = {
            "model": (
                self.model
            ),

            "messages": [
                {
                    "role": "system",
                    "content": (
                        system_prompt
                    ),
                },

                {
                    "role": "user",
                    "content": json.dumps(
                        user_content,
                        ensure_ascii=False,
                    ),
                },
            ],

            "temperature": 0,

            "reasoning_effort": (
                "low"
            ),

            "reasoning_format": (
                "hidden"
            ),

            "response_format": {
                "type": (
                    "json_schema"
                ),

                "json_schema": {
                    "name": (
                        "paper_relevance_ranking"
                    ),

                    "strict": True,

                    "schema": (
                        schema
                    ),
                },
            },
        }

        logger.info(
            "Sending %s verified paper(s) to Groq "
            "for relevance ordering.",
            len(papers),
        )

        # ==================================================
        # CALL GROQ
        # ==================================================

        try:

            response_data = (
                self._send_chat_request(
                    payload
                )
            )

            content = (
                self._extract_content(
                    response_data
                )
            )

            parsed = (
                json.loads(
                    content
                )
            )

        except Exception as error:

            logger.warning(
                "Groq relevance ranking failed. "
                "Keeping original paper order. "
                "Error: %s",
                error,
            )

            return papers

        # ==================================================
        # EXTRACT INDICES
        # ==================================================

        raw_indices = (
            parsed.get(
                "ranked_indices"
            )
            or []
        )

        # ==================================================
        # LOCAL SAFETY VALIDATION
        #
        # Never trust AI ordering blindly.
        # ==================================================

        valid_indices: list[int] = []

        seen_indices: set[int] = set()

        for raw_index in raw_indices:

            try:

                index = int(
                    raw_index
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            if index < 0:

                continue

            if index >= len(papers):

                continue

            if index in seen_indices:

                continue

            seen_indices.add(
                index
            )

            valid_indices.append(
                index
            )

        # ==================================================
        # GUARANTEE NO PAPER IS LOST
        #
        # If Groq somehow omitted something, append it
        # using the original order.
        # ==================================================

        for index in range(
            len(papers)
        ):

            if index not in seen_indices:

                valid_indices.append(
                    index
                )

        # ==================================================
        # REORDER ORIGINAL PAPER OBJECTS
        # ==================================================

        ranked_papers = [
            papers[index]
            for index in valid_indices
        ]

        logger.info(
            "Groq relevance ordering completed "
            "for %s paper(s).",
            len(ranked_papers),
        )

        return ranked_papers
    
    # ======================================================
    # SEND CHAT REQUEST
    # ======================================================

    def _send_chat_request(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send request to Groq Chat Completions.
        """

        try:

            response = (
                self.session.post(
                    self.chat_url,
                    json=payload,
                    timeout=(
                        self.settings.request_timeout
                    ),
                )
            )

        except requests.Timeout as error:

            raise GroqServiceError(
                "Groq AI request timed out."
            ) from error

        except requests.ConnectionError as error:

            raise GroqServiceError(
                "Could not connect to Groq AI."
            ) from error

        except requests.RequestException as error:

            raise GroqServiceError(
                "A network error occurred while "
                "contacting Groq AI."
            ) from error

        # ==================================================
        # HTTP ERROR HANDLING
        # ==================================================

        if response.status_code == 401:

            raise GroqServiceError(
                "Groq rejected the API key. "
                "Check GROQ_API_KEY in .env."
            )

        if response.status_code == 403:

            raise GroqServiceError(
                "Groq denied access to the "
                "requested model or API."
            )

        if response.status_code == 429:

            raise GroqServiceError(
                "Groq rate limit reached. "
                "Please wait and try again."
            )

        if response.status_code >= 500:

            raise GroqServiceError(
                "Groq is temporarily unavailable."
            )

        if not response.ok:

            error_message = (
                self._extract_api_error(
                    response
                )
            )

            raise GroqServiceError(
                "Groq API error: "
                f"{error_message}"
            )

        try:

            return response.json()

        except ValueError as error:

            raise GroqServiceError(
                "Groq returned an unreadable response."
            ) from error

    # ======================================================
    # EXTRACT CONTENT
    # ======================================================

    @staticmethod
    def _extract_content(
        response_data: dict[str, Any],
    ) -> str:
        """
        Extract assistant response text.
        """

        try:

            content = (
                response_data[
                    "choices"
                ][0][
                    "message"
                ][
                    "content"
                ]
            )

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as error:

            raise GroqServiceError(
                "Groq response did not contain "
                "the expected AI output."
            ) from error

        if not content:

            raise GroqServiceError(
                "Groq returned an empty response."
            )

        return str(
            content
        ).strip()

    # ======================================================
    # VALIDATE SEARCH INTENT
    # ======================================================

    def _validate_search_intent(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Perform application-side validation after AI output.
        """

        current_year = (
            datetime.now().year
        )

        keyword = str(
            data.get(
                "keyword"
            )
            or ""
        ).strip()

        if not keyword:

            raise GroqServiceError(
                "Groq could not identify "
                "a research topic."
            )

        try:

            start_year = int(
                data.get(
                    "start_year"
                )
            )

            end_year = int(
                data.get(
                    "end_year"
                )
            )

            paper_count = int(
                data.get(
                    "paper_count"
                )
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise GroqServiceError(
                "Groq returned invalid "
                "search parameters."
            ) from error

        # --------------------------------------------------
        # YEAR SAFETY
        # --------------------------------------------------

        start_year = max(
            1900,
            min(
                start_year,
                current_year,
            ),
        )

        end_year = max(
            1900,
            min(
                end_year,
                current_year,
            ),
        )

        if start_year > end_year:

            start_year, end_year = (
                end_year,
                start_year,
            )

        # --------------------------------------------------
        # PAPER COUNT SAFETY
        # --------------------------------------------------

        paper_count = max(
            1,
            min(
                paper_count,
                self.settings.maximum_paper_count,
            ),
        )

        result = {
            "keyword": (
                keyword
            ),

            "start_year": (
                start_year
            ),

            "end_year": (
                end_year
            ),

            "paper_count": (
                paper_count
            ),
        }

        logger.info(
            "Groq parsed search intent: "
            "keyword=%s, years=%s-%s, count=%s.",
            keyword,
            start_year,
            end_year,
            paper_count,
        )

        return result

    # ======================================================
    # API ERROR MESSAGE
    # ======================================================

    @staticmethod
    def _extract_api_error(
        response: requests.Response,
    ) -> str:
        """
        Extract useful Groq API error text.
        """

        try:

            payload = (
                response.json()
            )

            error = (
                payload.get(
                    "error"
                )
            )

            if isinstance(
                error,
                dict,
            ):

                message = (
                    error.get(
                        "message"
                    )
                )

                if message:

                    return str(
                        message
                    )

        except ValueError:

            pass

        return (
            f"HTTP {response.status_code}"
        )

    # ======================================================
    # HEALTH STATUS
    # ======================================================

    def health_status(
        self,
    ) -> dict[str, str]:
        """
        Return Groq configuration status.

        No API call is made here.
        """

        return {
            "groq_service": (
                "Configured"
                if self.is_configured()
                else "Missing API Key"
            ),

            "groq_model": (
                self.model
            ),
        }