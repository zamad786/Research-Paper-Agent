"""
Streamlit interface for the Research Paper Agent.

Phase 7.3

Search modes:

1. AI Search
   - User writes a natural-language research request.
   - Groq extracts:
       * research topic
       * start year
       * end year
       * number of papers
   - The normal research pipeline then runs.

2. Manual Search
   - User manually enters:
       * topic
       * start year
       * end year
       * number of papers

FINAL RANKING REQUIREMENT:

Only papers verified as:

    - Q1
    - Q2
    - HEC W

are returned.

Groq NEVER determines journal ranking.

Ranking verification remains the responsibility of
RankingService and the configured ranking datasets.

Academic discovery sources:

    - OpenAlex
    - Crossref
    - Semantic Scholar

Access enrichment:

    - Unpaywall

Email:

    - Preview first
    - Explicit human approval required
"""

from datetime import datetime
from pathlib import Path

import streamlit as st

from agent import ResearchPaperAgent
from services import (
    EmailServiceError,
    GroqServiceError,
    RankingServiceError,
)
from utils.helpers import format_authors


# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Research Paper Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)
# ==========================================================
# CUSTOM CSS
# ==========================================================

def load_custom_css() -> None:
    """
    Load the professional application theme.
    """

    css_path = (
        Path(__file__).parent
        / "assets"
        / "styles.css"
    )

    if css_path.exists():

        with open(
            css_path,
            "r",
            encoding="utf-8",
        ) as css_file:

            st.markdown(
                f"""
                <style>
                {css_file.read()}
                </style>
                """,
                unsafe_allow_html=True,
            )


load_custom_css()


# ==========================================================
# SESSION STATE
# ==========================================================

DEFAULT_SESSION_STATE = {
    "search_results": [],
    "search_request": None,
    "search_completed": False,
    "paper_links": [],
    "email_preview": None,
    "email_approved": False,
    "email_rejected": False,
    "email_sent": False,

    # Phase 7 AI state
    "search_mode_used": None,
    "ai_original_request": None,
}


for key, default_value in DEFAULT_SESSION_STATE.items():

    if key not in st.session_state:

        st.session_state[key] = default_value


# ==========================================================
# AGENT
# ==========================================================

@st.cache_resource
def get_agent() -> ResearchPaperAgent:
    """
    Create one shared ResearchPaperAgent.
    """

    return ResearchPaperAgent()


agent = get_agent()


# ==========================================================
# RESET EMAIL STATE
# ==========================================================

def reset_email_state() -> None:
    """
    Reset the human-approved email workflow.
    """

    st.session_state.email_preview = None
    st.session_state.email_approved = False
    st.session_state.email_rejected = False
    st.session_state.email_sent = False


# ==========================================================
# RESET SEARCH STATE
# ==========================================================

def reset_search_state() -> None:
    """
    Clear previous search results.
    """

    st.session_state.search_results = []
    st.session_state.search_request = None
    st.session_state.search_completed = False
    st.session_state.paper_links = []
    st.session_state.search_mode_used = None
    st.session_state.ai_original_request = None

    reset_email_state()


# ==========================================================
# RANKING LABEL
# ==========================================================

def get_ranking_label(
    paper,
) -> str:
    """
    Return only verified Q1/Q2/W ranking labels.
    """

    allowed_categories = {
        "Q1",
        "Q2",
        "W",
    }

    categories: list[str] = []

    for category in (
        paper.verified_categories
        or []
    ):

        if (
            category in allowed_categories
            and category not in categories
        ):

            categories.append(
                category
            )

    if (
        paper.ranking_verified
        and paper.category in allowed_categories
        and paper.category not in categories
    ):

        categories.append(
            paper.category
        )

    if categories:

        return ", ".join(
            categories
        )

    return "Unavailable"


# ==========================================================
# ACCESS LABEL
# ==========================================================

def get_access_label(
    paper,
) -> str:
    """
    Return human-readable paper-access status.
    """

    if paper.pdf_url:

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


# ==========================================================
# PAPER LINKS
# ==========================================================

def build_paper_links(
    papers,
) -> list[str]:
    """
    Build unique preferred paper links.
    """

    return agent.build_paper_links(
        papers
    )


def build_links_text(
    papers,
) -> str:
    """
    Build numbered paper-link text.
    """

    links = build_paper_links(
        papers
    )

    return "\n".join(
        f"{index}. {link}"
        for index, link
        in enumerate(
            links,
            start=1,
        )
    )


# ==========================================================
# PAPER CARD
# ==========================================================

def display_paper_card(
    paper,
    index: int,
) -> None:
    """
    Display one verified Q1/Q2/W paper.
    """

    with st.container(
        border=True
    ):

        st.markdown(
            f"### {index}. {paper.title}"
        )

        (
            col1,
            col2,
            col3,
            col4,
        ) = st.columns(4)

        col1.metric(
            "Year",
            paper.year,
        )

        col2.metric(
            "Verified Ranking",
            get_ranking_label(
                paper
            ),
        )

        col3.metric(
            "Access",
            get_access_label(
                paper
            ),
        )

        col4.metric(
            "Citations",
            (
                paper.citation_count
                if paper.citation_count is not None
                else "N/A"
            ),
        )

        st.divider()

        info_col, action_col = (
            st.columns(
                [3, 1]
            )
        )

        # ==================================================
        # PAPER INFORMATION
        # ==================================================

        with info_col:

            st.write(
                "**Authors:** "
                + format_authors(
                    paper.authors
                )
            )

            st.write(
                "**Journal / Venue:** "
                + (
                    paper.journal
                    or "Unavailable"
                )
            )

            st.write(
                "**DOI:** "
                + (
                    paper.doi
                    or "Unavailable"
                )
            )

            st.write(
                "**ISSN:** "
                + (
                    ", ".join(
                        paper.issns
                    )
                    if paper.issns
                    else "Unavailable"
                )
            )

            st.write(
                "**Metadata sources:** "
                + (
                    paper.source
                    or "Unknown"
                )
            )

            st.write(
                "**Ranking source:** "
                + (
                    paper.ranking_source
                    or "Unavailable"
                )
            )

            st.write(
                "**Ranking year:** "
                + (
                    str(
                        paper.ranking_year
                    )
                    if paper.ranking_year
                    else "Unavailable"
                )
            )

            if paper.verified_by_unpaywall:

                st.write(
                    "**Access verification:** "
                    "Checked with Unpaywall"
                )

        # ==================================================
        # BADGES + LINK
        # ==================================================

        with action_col:

            ranking = (
                get_ranking_label(
                    paper
                )
            )

            access = (
                get_access_label(
                    paper
                )
            )

            st.success(
                f"🏆 {ranking}"
            )

            if access == "Free PDF":

                st.success(
                    "🔓 Free PDF"
                )

            elif (
                access
                == "Free / Open Access"
            ):

                st.success(
                    "🌐 Open Access"
                )

            elif (
                access
                == (
                    "Publisher / "
                    "Institutional Access"
                )
            ):

                st.warning(
                    "🏫 Institutional Access"
                )

            else:

                st.info(
                    "❓ Access Unknown"
                )

            preferred_link = (
                paper.preferred_link()
            )

            if preferred_link:

                st.link_button(
                    "🔗 Open Paper",
                    preferred_link,
                    use_container_width=True,
                )

        # ==================================================
        # RANKING EXPLANATION
        # ==================================================

        with st.expander(
            "ℹ️ What does this ranking mean?"
        ):

            ranking = (
                get_ranking_label(
                    paper
                )
            )

            if "Q1" in ranking:

                st.write(
                    "🏆 **Q1:** The journal matched "
                    "Q1 in the configured ranking data."
                )

            if "Q2" in ranking:

                st.write(
                    "🏆 **Q2:** The journal matched "
                    "Q2 in the configured ranking data."
                )

            if "W" in ranking:

                st.write(
                    "🇵🇰 **W:** The journal matched "
                    "the configured HEC Pakistan "
                    "W-category data."
                )

            st.write(
                "Only papers that pass the final "
                "Q1/Q2/HEC-W ranking filter are shown."
            )


# ==========================================================
# SIDEBAR
# ==========================================================

with st.sidebar:

    st.title(
        "📚 Research Paper Agent"
    )

    st.caption(
        "AI-Powered Q1 • Q2 • HEC W Paper Finder"
    )

    st.divider()

    # ======================================================
    # AI
    # ======================================================

    st.subheader(
        "🤖 AI Intelligence"
    )

    try:

        status = (
            agent.health_check()
        )

        if (
            status.get(
                "groq_service"
            )
            == "Configured"
        ):

            st.success(
                "Groq AI: Configured"
            )

            st.caption(
                "Model: "
                + status.get(
                    "groq_model",
                    "Unknown",
                )
            )

        else:

            st.warning(
                "Groq AI: Not configured"
            )

    except Exception:

        st.warning(
            "Groq status unavailable."
        )

    st.caption(
        "Groq understands search instructions. "
        "It does not determine journal ranking."
    )

    st.divider()

    # ======================================================
    # TARGET RANKINGS
    # ======================================================

    st.subheader(
        "🎯 Target Rankings"
    )

    st.success(
        "✅ Q1 Journals"
    )

    st.success(
        "✅ Q2 Journals"
    )

    st.success(
        "✅ HEC W Journals"
    )

    st.caption(
        "Q3, Q4 and unverified journals "
        "are excluded."
    )

    st.divider()

    # ======================================================
    # DISCOVERY
    # ======================================================

    st.subheader(
        "🔎 Discovery Sources"
    )

    st.caption(
        "📘 OpenAlex"
    )

    st.caption(
        "🔗 Crossref"
    )

    st.caption(
        "🧠 Semantic Scholar"
    )

    st.divider()

    # ======================================================
    # ACCESS
    # ======================================================

    st.subheader(
        "🔓 Access Enrichment"
    )

    st.caption(
        "Unpaywall"
    )

    st.write(
        "Both free and institutional-access "
        "papers are accepted."
    )

    st.divider()

    # ======================================================
    # EMAIL
    # ======================================================

    st.subheader(
        "📧 Email"
    )

    st.caption(
        "🔒 Explicit human approval is required "
        "before email delivery."
    )


# ==========================================================
# MAIN HEADER
# ==========================================================

st.title(
    "📚 Research Paper Agent"
)

st.subheader(
    "AI-powered discovery of verified "
    "Q1, Q2 and HEC W research papers"
)

st.write(
    "Search research papers using either a simple "
    "natural-language AI request or the traditional "
    "manual search form."
)

st.info(
    "🤖 Groq AI only understands your search request. "
    "Journal ranking is independently verified by the "
    "ranking system before results are shown."
)


# ==========================================================
# PIPELINE GUIDE
# ==========================================================

with st.expander(
    "🧠 How does the AI Research Agent work?"
):

    st.markdown(
        """
### AI Search

You can write a normal request such as:

> Find 7 recent papers about federated learning for
> IoT security from 2024 to 2026.

Groq extracts:

- Research topic
- Starting year
- Ending year
- Number of papers

Groq **does not determine Q1/Q2/W ranking**.

### Academic discovery

The extracted topic is searched through:

- OpenAlex
- Crossref
- Semantic Scholar

### Processing

The system then:

1. Merges duplicate records
2. Enriches access information using Unpaywall
3. Verifies journal ranking
4. Removes Q3
5. Removes Q4
6. Removes unverified journals
7. Keeps only **Q1, Q2 and HEC W**
8. Shows free or institutional-access links
"""
    )


# ==========================================================
# SEARCH MODE
# ==========================================================

st.divider()

st.header(
    "🔎 Search Research Papers"
)

search_mode = st.radio(
    "Choose how you want to search",
    options=[
        "🤖 AI Search",
        "📝 Manual Search",
    ],
    horizontal=True,
)


# ==========================================================
# AI SEARCH
# ==========================================================

if search_mode == "🤖 AI Search":

    st.subheader(
        "🤖 Ask the Research Agent"
    )

    st.write(
        "Describe what papers you want in normal language."
    )

    st.caption(
        "You can mention the topic, year range and "
        "number of papers in one sentence."
    )

    with st.form(
        "ai_search_form"
    ):

        ai_request = st.text_area(
            "Research request",
            placeholder=(
                "Example: Find 7 recent papers about "
                "federated learning for IoT security "
                "from 2024 to 2026."
            ),
            height=130,
        )

        st.info(
            "🎯 The final results will automatically "
            "be restricted to verified Q1, Q2 and "
            "HEC W papers."
        )

        ai_search_button = (
            st.form_submit_button(
                "✨ Search with AI",
                type="primary",
                use_container_width=True,
            )
        )

    # ======================================================
    # RUN AI SEARCH
    # ======================================================

    if ai_search_button:

        reset_search_state()

        try:

            if not ai_request.strip():

                raise ValueError(
                    "Please describe the research "
                    "papers you want to find."
                )

            with st.spinner(
                "Groq is understanding your request..."
            ):

                parsed_request = (
                    agent.create_ai_search_request(
                        user_request=(
                            ai_request
                        )
                    )
                )

            # ------------------------------------------------
            # SHOW AI INTERPRETATION
            # ------------------------------------------------

            st.success(
                "✅ Groq understood your research request."
            )

            st.markdown(
                "### 🤖 AI Interpretation"
            )

            (
                ai_col1,
                ai_col2,
                ai_col3,
                ai_col4,
            ) = st.columns(4)

            ai_col1.metric(
                "Topic",
                parsed_request.keyword,
            )

            ai_col2.metric(
                "From",
                parsed_request.start_year,
            )

            ai_col3.metric(
                "To",
                parsed_request.end_year,
            )

            ai_col4.metric(
                "Papers",
                parsed_request.paper_count,
            )

            st.caption(
                "Final ranking requirement: "
                "Q1 • Q2 • HEC W"
            )

            # ------------------------------------------------
            # SEARCH ACADEMIC DATABASES
            # ------------------------------------------------

            with st.spinner(
                "Searching OpenAlex, Crossref and "
                "Semantic Scholar, merging records, "
                "checking access and verifying "
                "Q1/Q2/W rankings..."
            ):

                results = (
                    agent.search_papers_with_ai_expansion(
                        search_request=parsed_request
                    )
                )

            st.session_state.search_request = (
                parsed_request
            )

            st.session_state.search_results = (
                results
            )

            st.session_state.paper_links = (
                build_paper_links(
                    results
                )
            )

            st.session_state.search_completed = (
                True
            )

            st.session_state.search_mode_used = (
                "AI"
            )

            st.session_state.ai_original_request = (
                ai_request.strip()
            )

            if results:

                st.success(
                    f"✅ Found {len(results)} verified "
                    f"Q1/Q2/W research paper(s)."
                )

            else:

                st.warning(
                    "No verified Q1, Q2 or HEC W papers "
                    "were found for this request. "
                    "Try a broader topic or a wider "
                    "publication-year range."
                )

        except GroqServiceError as error:

            st.error(
                f"Groq AI error: {error}"
            )

        except ValueError as error:

            st.error(
                str(error)
            )

        except Exception as error:

            st.error(
                "An unexpected error occurred "
                "during AI search."
            )

            st.exception(
                error
            )


# ==========================================================
# MANUAL SEARCH
# ==========================================================

else:

    st.subheader(
        "📝 Manual Research Search"
    )

    st.write(
        "Enter the search parameters manually."
    )

    current_year = (
        datetime.now().year
    )

    with st.form(
        "manual_search_form"
    ):

        keyword = st.text_input(
            "Research topic or keywords",
            placeholder=(
                "Example: federated learning "
                "for IoT security"
            ),
        )

        (
            year_col1,
            year_col2,
            count_col,
        ) = st.columns(3)

        with year_col1:

            start_year = st.number_input(
                "From year",
                min_value=1900,
                max_value=current_year,
                value=max(
                    1900,
                    current_year - 3,
                ),
                step=1,
            )

        with year_col2:

            end_year = st.number_input(
                "To year",
                min_value=1900,
                max_value=current_year,
                value=current_year,
                step=1,
            )

        with count_col:

            paper_count = (
                st.number_input(
                    "Number of papers",
                    min_value=1,
                    max_value=50,
                    value=5,
                    step=1,
                )
            )

        st.caption(
            "The requested number is the maximum "
            "number of verified Q1/Q2/W papers "
            "to return."
        )

        manual_search_button = (
            st.form_submit_button(
                "🔎 Find Q1 / Q2 / W Papers",
                type="primary",
                use_container_width=True,
            )
        )

    # ======================================================
    # RUN MANUAL SEARCH
    # ======================================================

    if manual_search_button:

        reset_search_state()

        try:

            request = (
                agent.create_search_request(
                    keyword=keyword,
                    start_year=int(
                        start_year
                    ),
                    end_year=int(
                        end_year
                    ),
                    paper_count=int(
                        paper_count
                    ),
                    categories=[
                        "Q1",
                        "Q2",
                        "W",
                    ],
                )
            )

            with st.spinner(
                "Searching academic databases, "
                "merging records, checking access "
                "and verifying Q1/Q2/W rankings..."
            ):

                results = (
                    agent.search_papers(
                        request
                    )
                )

            st.session_state.search_request = (
                request
            )

            st.session_state.search_results = (
                results
            )

            st.session_state.paper_links = (
                build_paper_links(
                    results
                )
            )

            st.session_state.search_completed = (
                True
            )

            st.session_state.search_mode_used = (
                "Manual"
            )

            if results:

                st.success(
                    f"✅ Found {len(results)} verified "
                    f"Q1/Q2/W research paper(s)."
                )

            else:

                st.warning(
                    "No verified Q1, Q2 or HEC W "
                    "papers were found. Try a broader "
                    "keyword or wider year range."
                )

        except ValueError as error:

            st.error(
                str(error)
            )

        except Exception as error:

            st.error(
                "An unexpected error occurred "
                "during the search."
            )

            st.exception(
                error
            )


# ==========================================================
# SEARCH INTERPRETATION / DETAILS
# ==========================================================

if (
    st.session_state.search_request
    is not None
):

    request = (
        st.session_state.search_request
    )

    st.divider()

    if (
        st.session_state.search_mode_used
        == "AI"
    ):

        st.header(
            "🤖 AI Search Interpretation"
        )

        if (
            st.session_state.ai_original_request
        ):

            st.write(
                "**Your request:**"
            )

            st.info(
                st.session_state.ai_original_request
            )

        st.write(
            "**Groq interpreted it as:**"
        )

    else:

        st.header(
            "📝 Search Parameters"
        )

    (
        detail1,
        detail2,
        detail3,
        detail4,
    ) = st.columns(4)

    detail1.metric(
        "Research Topic",
        request.keyword,
    )

    detail2.metric(
        "From Year",
        request.start_year,
    )

    detail3.metric(
        "To Year",
        request.end_year,
    )

    detail4.metric(
        "Requested Papers",
        request.paper_count,
    )

    st.caption(
        "Final verified rankings: "
        + ", ".join(
            request.categories
        )
    )


# ==========================================================
# SEARCH SUMMARY
# ==========================================================

if (
    st.session_state.search_request
    is not None
):

    papers = (
        st.session_state.search_results
    )

    request = (
        st.session_state.search_request
    )

    q1_count = sum(
        1
        for paper in papers
        if (
            "Q1"
            in (
                paper.verified_categories
                or []
            )
        )
        or (
            paper.category == "Q1"
            and paper.ranking_verified
        )
    )

    q2_count = sum(
        1
        for paper in papers
        if (
            "Q2"
            in (
                paper.verified_categories
                or []
            )
        )
        or (
            paper.category == "Q2"
            and paper.ranking_verified
        )
    )

    w_count = sum(
        1
        for paper in papers
        if (
            "W"
            in (
                paper.verified_categories
                or []
            )
        )
        or (
            paper.category == "W"
            and paper.ranking_verified
        )
    )

    st.divider()

    st.header(
        "📊 Search Summary"
    )

    (
        summary1,
        summary2,
        summary3,
        summary4,
    ) = st.columns(4)

    summary1.metric(
        "Verified Papers",
        len(
            papers
        ),
    )

    summary2.metric(
        "Q1",
        q1_count,
    )

    summary3.metric(
        "Q2",
        q2_count,
    )

    summary4.metric(
        "HEC W",
        w_count,
    )

    search_method = (
        st.session_state.search_mode_used
        or "Unknown"
    )

    st.caption(
        f"Search mode: {search_method} | "
        f"Topic: {request.keyword} | "
        f"Years: {request.start_year}–"
        f"{request.end_year}"
    )


# ==========================================================
# RESULTS
# ==========================================================

if (
    st.session_state.search_completed
    and
    st.session_state.search_results
):

    papers = (
        st.session_state.search_results
    )

    st.divider()

    st.header(
        "📄 Verified Q1 / Q2 / W Papers"
    )

    st.success(
        "Every paper below passed the final "
        "Q1/Q2/HEC-W ranking filter."
    )

    # ======================================================
    # OPTIONAL DISPLAY FILTERS
    # ======================================================

    with st.expander(
        "⚙️ Optional Result Filters"
    ):

        ranking_filter = (
            st.multiselect(
                "Show ranking",
                options=[
                    "Q1",
                    "Q2",
                    "W",
                ],
                default=[
                    "Q1",
                    "Q2",
                    "W",
                ],
            )
        )

        access_filter = (
            st.multiselect(
                "Show access",
                options=[
                    "Free PDF",
                    "Free / Open Access",
                    (
                        "Publisher / "
                        "Institutional Access"
                    ),
                    "Access Unknown",
                ],
                default=[
                    "Free PDF",
                    "Free / Open Access",
                    (
                        "Publisher / "
                        "Institutional Access"
                    ),
                    "Access Unknown",
                ],
            )
        )

    filtered_papers = []

    for paper in papers:

        ranking = (
            get_ranking_label(
                paper
            )
        )

        access = (
            get_access_label(
                paper
            )
        )

        ranking_matches = any(
            selected in ranking
            for selected
            in ranking_filter
        )

        access_matches = (
            access
            in access_filter
        )

        if (
            ranking_matches
            and access_matches
        ):

            filtered_papers.append(
                paper
            )

    if filtered_papers:

        st.caption(
            f"Showing {len(filtered_papers)} "
            f"of {len(papers)} verified "
            f"paper(s)."
        )

        for index, paper in enumerate(
            filtered_papers,
            start=1,
        ):

            display_paper_card(
                paper,
                index,
            )

    else:

        st.warning(
            "No papers match the selected "
            "display filters."
        )


# ==========================================================
# PAPER LINKS
# ==========================================================

if (
    st.session_state.search_completed
    and
    st.session_state.search_results
):

    papers = (
        st.session_state.search_results
    )

    st.divider()

    st.header(
        "🔗 Verified Paper Links"
    )

    st.write(
        "These links belong only to verified "
        "Q1/Q2/W papers."
    )

    st.info(
        "🏫 Publisher links may require your "
        "university, institutional or library access."
    )

    links_text = (
        build_links_text(
            papers
        )
    )

    st.text_area(
        "Paper links",
        value=links_text,
        height=220,
        disabled=True,
    )


# ==========================================================
# EMAIL WORKFLOW
# ==========================================================

if (
    st.session_state.search_completed
    and
    st.session_state.search_results
):

    st.divider()

    st.header(
        "📧 Email Verified Papers"
    )

    st.info(
        "Only the verified Q1/Q2/W results will "
        "be included. Nothing is sent without "
        "your explicit approval."
    )

    recipient_email = (
        st.text_input(
            "Recipient email",
            placeholder="example@gmail.com",
            key="recipient_email_input",
        )
    )

    preview_button = (
        st.button(
            "👁 Preview Email",
            use_container_width=True,
        )
    )

    if preview_button:

        try:

            request = (
                st.session_state.search_request
            )

            preview = (
                agent.create_email_preview(
                    recipient=(
                        recipient_email
                    ),
                    papers=(
                        st.session_state.search_results
                    ),
                    keyword=(
                        request.keyword
                    ),
                    start_year=(
                        request.start_year
                    ),
                    end_year=(
                        request.end_year
                    ),
                    categories=[
                        "Q1",
                        "Q2",
                        "W",
                    ],
                )
            )

            st.session_state.email_preview = (
                preview
            )

            st.session_state.email_approved = (
                False
            )

            st.session_state.email_rejected = (
                False
            )

            st.session_state.email_sent = (
                False
            )

            st.success(
                "✅ Email preview created. "
                "Nothing has been sent yet."
            )

        except ValueError as error:

            st.error(
                str(error)
            )

        except EmailServiceError as error:

            st.error(
                str(error)
            )

        except Exception as error:

            st.error(
                "Email preview could not "
                "be created."
            )

            st.exception(
                error
            )


# ==========================================================
# EMAIL PREVIEW
# ==========================================================

if (
    st.session_state.email_preview
    is not None
):

    preview = (
        st.session_state.email_preview
    )

    st.divider()

    st.subheader(
        "👁 Email Preview"
    )

    (
        preview_col1,
        preview_col2,
    ) = st.columns(2)

    preview_col1.write(
        f"**To:** "
        f"{preview['recipient']}"
    )

    preview_col2.write(
        f"**Subject:** "
        f"{preview['subject']}"
    )

    st.text_area(
        "Email body",
        value=(
            preview[
                "text_body"
            ]
        ),
        height=350,
        disabled=True,
    )

    st.warning(
        "⚠️ Nothing has been sent yet."
    )

    (
        approve_col,
        reject_col,
    ) = st.columns(2)

    with approve_col:

        approve_button = (
            st.button(
                "✅ Approve and Send",
                type="primary",
                use_container_width=True,
                disabled=(
                    st.session_state.email_sent
                ),
                key="approve_email_button",
            )
        )

    with reject_col:

        reject_button = (
            st.button(
                "❌ Reject Email",
                use_container_width=True,
                disabled=(
                    st.session_state.email_sent
                ),
                key="reject_email_button",
            )
        )

    # ======================================================
    # APPROVE EMAIL
    # ======================================================

    if approve_button:

        try:

            st.session_state.email_approved = (
                True
            )

            st.session_state.email_rejected = (
                False
            )

            with st.spinner(
                "Sending approved email..."
            ):

                agent.send_email(
                    preview=(
                        preview
                    ),
                    approved=True,
                )

            st.session_state.email_sent = (
                True
            )

            st.success(
                "✅ Email sent successfully."
            )

        except EmailServiceError as error:

            st.session_state.email_sent = (
                False
            )

            st.session_state.email_approved = (
                False
            )

            st.error(
                str(error)
            )

        except Exception as error:

            st.session_state.email_sent = (
                False
            )

            st.session_state.email_approved = (
                False
            )

            st.error(
                "Unexpected email sending error."
            )

            st.exception(
                error
            )

    # ======================================================
    # REJECT EMAIL
    # ======================================================

    if reject_button:

        st.session_state.email_approved = (
            False
        )

        st.session_state.email_rejected = (
            True
        )

        st.session_state.email_sent = (
            False
        )

        st.session_state.email_preview = (
            None
        )

        st.warning(
            "❌ Email rejected. "
            "Nothing was sent."
        )


# ==========================================================
# EMAIL STATUS
# ==========================================================

if st.session_state.email_sent:

    st.success(
        "📨 Human-approved email delivery completed."
    )

    st.info(
        "📩 If you don't see the email in your "
        "inbox, check Spam or Junk as well."
    )


if st.session_state.email_rejected:

    st.info(
        "The previous email was rejected "
        "and was not sent."
    )


# ==========================================================
# NO RESULTS
# ==========================================================

if (
    st.session_state.search_completed
    and
    not st.session_state.search_results
):

    st.divider()

    st.warning(
        "No verified Q1/Q2/W research "
        "papers were found."
    )

    st.write(
        "Try broadening the research topic "
        "or increasing the publication-year range."
    )

    st.caption(
        "Q3, Q4 and unverified journal papers "
        "are intentionally excluded."
    )


# ==========================================================
# JOURNAL RANKING GUIDE
# ==========================================================

st.divider()


with st.expander(
    "🏆 Journal Ranking Guide"
):

    st.markdown(
        """
### Q1

Journal matched the configured first-quartile
ranking data.

### Q2

Journal matched the configured second-quartile
ranking data.

### HEC W

Journal matched the configured HEC Pakistan
W-category ranking data.

### Final rule

The application returns only:

- **Q1**
- **Q2**
- **HEC W**

It excludes:

- Q3
- Q4
- Not Verified

Groq AI does not generate or guess these rankings.
"""
    )


# ==========================================================
# DEVELOPMENT STATUS
# ==========================================================

with st.expander(
    "🛠 Development Status"
):

    st.write(
        "✅ OpenAlex discovery"
    )

    st.write(
        "✅ Crossref discovery"
    )

    st.write(
        "✅ Semantic Scholar discovery"
    )

    st.write(
        "✅ Multi-source merging"
    )

    st.write(
        "✅ Unpaywall access enrichment"
    )

    st.write(
        "✅ Ranking verification"
    )

    st.write(
        "✅ Strict Q1/Q2/W filtering"
    )

    st.write(
        "✅ Human-approved email"
    )

    st.write(
        "✅ Groq AI configuration"
    )

    st.write(
        "✅ Natural-language search parsing"
    )

    st.write(
        "✅ AI search interface"
    )

    st.write(
        "⏳ AI query expansion"
    )

    st.write(
        "⏳ AI relevance improvement"
    )

    st.write(
        "⏳ Final production cleanup"
    )