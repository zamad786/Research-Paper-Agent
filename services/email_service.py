"""
Email service for the Research Paper Agent.

Final Phase 6.5 email system.

Only verified Q1, Q2 and HEC W papers should appear
in the email.

The email can contain:

- Free PDF papers
- Open-access papers
- Publisher/institutional-access papers

Human approval is always required before sending.
"""

import html
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Settings
from models import Paper
from utils.helpers import format_authors
from utils.logger import get_logger


logger = get_logger(__name__)


# ==========================================================
# ERROR
# ==========================================================


class EmailServiceError(Exception):
    """
    Raised when email preview creation or sending fails.
    """


# ==========================================================
# EMAIL SERVICE
# ==========================================================


class EmailService:
    """
    Create and send verified research-paper emails.
    """

    TARGET_CATEGORIES = {
        "Q1",
        "Q2",
        "W",
    }

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        """
        Initialize Gmail SMTP configuration.
        """

        self.settings = settings

        self.smtp_host = (
            "smtp.gmail.com"
        )

        self.smtp_port = 465

    # ======================================================
    # CREATE EMAIL PREVIEW
    # ======================================================

    def create_email_preview(
        self,
        recipient: str,
        papers: list[Paper],
        keyword: str,
        start_year: int | None = None,
        end_year: int | None = None,
        categories: list[str] | None = None,
    ) -> dict[str, str]:
        """
        Create email preview.

        Nothing is sent from this method.
        """

        if not recipient:

            raise EmailServiceError(
                "Recipient email is required."
            )

        # --------------------------------------------------
        # SAFETY FILTER
        #
        # Even though agent.py already filters results,
        # the email service independently ensures that
        # Q3/Q4/unverified papers cannot enter the email.
        # --------------------------------------------------

        verified_papers = [
            paper
            for paper in papers
            if self._is_target_ranked_paper(
                paper
            )
        ]

        if not verified_papers:

            raise EmailServiceError(
                "There are no verified Q1, Q2 "
                "or HEC W papers available "
                "for email."
            )

        cleaned_keyword = (
            keyword.strip()
            if keyword
            else "Research Papers"
        )

        subject = (
            "Verified Q1/Q2/W Research Papers: "
            f"{cleaned_keyword}"
        )

        text_body = (
            self._create_text_body(
                papers=verified_papers,
                keyword=cleaned_keyword,
                start_year=start_year,
                end_year=end_year,
            )
        )

        html_body = (
            self._create_html_body(
                papers=verified_papers,
                keyword=cleaned_keyword,
                start_year=start_year,
                end_year=end_year,
            )
        )

        preview = {
            "recipient": recipient,
            "subject": subject,
            "text_body": text_body,
            "html_body": html_body,
        }

        logger.info(
            "Q1/Q2/W email preview created "
            "for %s with %s paper(s).",
            recipient,
            len(verified_papers),
        )

        return preview

    # ======================================================
    # SEND EMAIL
    # ======================================================

    def send_approved_email(
        self,
        preview: dict[str, str],
        approved: bool,
    ) -> None:
        """
        Send only after human approval.
        """

        if not approved:

            raise EmailServiceError(
                "Email sending was not approved. "
                "No message was sent."
            )

        if not self.settings.sender_email:

            raise EmailServiceError(
                "SENDER_EMAIL is not configured."
            )

        if not self.settings.sender_app_password:

            raise EmailServiceError(
                "SENDER_APP_PASSWORD is not configured."
            )

        recipient = (
            preview.get(
                "recipient",
                "",
            ).strip()
        )

        subject = (
            preview.get(
                "subject",
                "",
            ).strip()
        )

        text_body = (
            preview.get(
                "text_body",
                ""
            )
        )

        html_body = (
            preview.get(
                "html_body",
                ""
            )
        )

        if not recipient:

            raise EmailServiceError(
                "Email preview does not contain "
                "a recipient."
            )

        if not subject:

            raise EmailServiceError(
                "Email preview does not contain "
                "a subject."
            )

        message = (
            MIMEMultipart(
                "alternative"
            )
        )

        message["Subject"] = (
            subject
        )

        message["From"] = (
            self.settings.sender_email
        )

        message["To"] = (
            recipient
        )

        message.attach(
            MIMEText(
                text_body,
                "plain",
                "utf-8",
            )
        )

        message.attach(
            MIMEText(
                html_body,
                "html",
                "utf-8",
            )
        )

        try:

            with smtplib.SMTP_SSL(
                self.smtp_host,
                self.smtp_port,
                timeout=(
                    self.settings.request_timeout
                ),
            ) as server:

                server.login(
                    self.settings.sender_email,
                    self.settings.sender_app_password,
                )

                server.sendmail(
                    self.settings.sender_email,
                    [recipient],
                    message.as_string(),
                )

        except smtplib.SMTPAuthenticationError as error:

            raise EmailServiceError(
                "Gmail authentication failed. "
                "Check your sender email and "
                "Google App Password."
            ) from error

        except smtplib.SMTPRecipientsRefused as error:

            raise EmailServiceError(
                "The recipient email address "
                "was refused."
            ) from error

        except smtplib.SMTPException as error:

            raise EmailServiceError(
                "The mail server returned an error."
            ) from error

        except OSError as error:

            raise EmailServiceError(
                "A network error occurred while "
                "connecting to Gmail."
            ) from error

        logger.info(
            "Approved Q1/Q2/W email sent to %s.",
            recipient,
        )

    # ======================================================
    # TEXT EMAIL
    # ======================================================

    def _create_text_body(
        self,
        papers: list[Paper],
        keyword: str,
        start_year: int | None,
        end_year: int | None,
    ) -> str:
        """
        Build plain-text email.
        """

        lines: list[str] = []

        lines.append(
            "RESEARCH PAPER AGENT"
        )

        lines.append(
            "=" * 60
        )

        lines.append("")

        lines.append(
            f"Research Topic: {keyword}"
        )

        if (
            start_year is not None
            and end_year is not None
        ):

            lines.append(
                "Publication Years: "
                f"{start_year} - {end_year}"
            )

        lines.append(
            "Verified Q1/Q2/W Papers: "
            f"{len(papers)}"
        )

        lines.append("")

        lines.append(
            "Only papers whose journal ranking "
            "was verified as Q1, Q2 or HEC W "
            "are included below."
        )

        lines.append("")

        lines.append(
            "Free and publisher/institutional-access "
            "papers may both be included."
        )

        lines.append("")

        lines.append(
            "=" * 60
        )

        # ==================================================
        # PAPERS
        # ==================================================

        for index, paper in enumerate(
            papers,
            start=1,
        ):

            lines.append("")

            lines.append(
                f"{index}. {paper.title}"
            )

            lines.append(
                "-" * 60
            )

            lines.append(
                "Authors: "
                + format_authors(
                    paper.authors
                )
            )

            lines.append(
                f"Year: {paper.year}"
            )

            lines.append(
                "Journal / Venue: "
                + (
                    paper.journal
                    or "Unavailable"
                )
            )

            lines.append(
                "DOI: "
                + (
                    paper.doi
                    or "Unavailable"
                )
            )

            lines.append(
                "Verified Ranking: "
                + self._ranking_label(
                    paper
                )
            )

            if paper.ranking_source:

                lines.append(
                    "Ranking Source: "
                    + paper.ranking_source
                )

            if paper.ranking_year:

                lines.append(
                    "Ranking Year: "
                    + str(
                        paper.ranking_year
                    )
                )

            lines.append(
                "Access: "
                + self._access_label(
                    paper
                )
            )

            lines.append(
                "Citations: "
                + (
                    str(
                        paper.citation_count
                    )
                    if (
                        paper.citation_count
                        is not None
                    )
                    else "Unavailable"
                )
            )

            lines.append(
                "Discovered Through: "
                + (
                    paper.source
                    or "Unknown"
                )
            )

            link = (
                paper.preferred_link()
            )

            lines.append(
                "Paper Link: "
                + (
                    link
                    or "Unavailable"
                )
            )

        # ==================================================
        # GUIDE
        # ==================================================

        lines.append("")

        lines.append(
            "=" * 60
        )

        lines.append("")

        lines.append(
            "JOURNAL RANKING GUIDE"
        )

        lines.append("")

        lines.append(
            "Q1: Verified first-quartile journal."
        )

        lines.append(
            "Q2: Verified second-quartile journal."
        )

        lines.append(
            "W: Verified HEC Pakistan W-category "
            "journal."
        )

        lines.append("")

        lines.append(
            "Q3, Q4 and unverified journals are "
            "not included in this email."
        )

        lines.append("")

        lines.append(
            "ACCESS GUIDE"
        )

        lines.append("")

        lines.append(
            "Free PDF: A freely accessible PDF "
            "was identified."
        )

        lines.append(
            "Free / Open Access: An open-access "
            "version was identified."
        )

        lines.append(
            "Publisher / Institutional Access: "
            "The paper may require university, "
            "library or subscription access."
        )

        lines.append("")

        lines.append(
            "=" * 60
        )

        lines.append("")

        lines.append(
            "Generated by Research Paper Agent"
        )

        return "\n".join(
            lines
        )

    # ======================================================
    # HTML EMAIL
    # ======================================================

    def _create_html_body(
        self,
        papers: list[Paper],
        keyword: str,
        start_year: int | None,
        end_year: int | None,
    ) -> str:
        """
        Build professional HTML email.
        """

        safe_keyword = (
            html.escape(
                keyword
            )
        )

        if (
            start_year is not None
            and end_year is not None
        ):

            year_text = (
                f"{start_year} - {end_year}"
            )

        else:

            year_text = (
                "Not specified"
            )

        paper_cards: list[str] = []

        for index, paper in enumerate(
            papers,
            start=1,
        ):

            title = html.escape(
                paper.title
            )

            authors = html.escape(
                format_authors(
                    paper.authors
                )
            )

            journal = html.escape(
                paper.journal
                or "Unavailable"
            )

            doi = html.escape(
                paper.doi
                or "Unavailable"
            )

            ranking = html.escape(
                self._ranking_label(
                    paper
                )
            )

            access = html.escape(
                self._access_label(
                    paper
                )
            )

            sources = html.escape(
                paper.source
                or "Unknown"
            )

            ranking_source = (
                html.escape(
                    paper.ranking_source
                )
                if paper.ranking_source
                else "Unavailable"
            )

            ranking_year = (
                str(
                    paper.ranking_year
                )
                if paper.ranking_year
                else "Unavailable"
            )

            citations = (
                str(
                    paper.citation_count
                )
                if (
                    paper.citation_count
                    is not None
                )
                else "Unavailable"
            )

            link = (
                paper.preferred_link()
            )

            safe_link = (
                html.escape(
                    link,
                    quote=True,
                )
                if link
                else None
            )

            if access == "Free PDF":

                access_badge = (
                    "🔓 Free PDF"
                )

            elif (
                access
                == "Free / Open Access"
            ):

                access_badge = (
                    "🌐 Open Access"
                )

            elif (
                access
                == (
                    "Publisher / "
                    "Institutional Access"
                )
            ):

                access_badge = (
                    "🏫 Publisher / "
                    "Institutional Access"
                )

            else:

                access_badge = (
                    "❓ Access Unknown"
                )

            if safe_link:

                link_button = f"""
                <a
                    href="{safe_link}"
                    style="
                        display:inline-block;
                        margin-top:14px;
                        background:#2563eb;
                        color:#ffffff;
                        text-decoration:none;
                        padding:10px 18px;
                        border-radius:7px;
                        font-weight:600;
                    "
                >
                    Open Research Paper
                </a>
                """

            else:

                link_button = """
                <p style="color:#6b7280;">
                    Paper link unavailable.
                </p>
                """

            card = f"""
            <div
                style="
                    border:1px solid #e5e7eb;
                    border-radius:12px;
                    padding:20px;
                    margin-bottom:18px;
                    background:#ffffff;
                "
            >

                <h3
                    style="
                        margin-top:0;
                        color:#111827;
                        line-height:1.4;
                    "
                >
                    {index}. {title}
                </h3>

                <p>
                    <strong>Authors:</strong>
                    {authors}
                </p>

                <p>
                    <strong>Year:</strong>
                    {paper.year}
                </p>

                <p>
                    <strong>Journal / Venue:</strong>
                    {journal}
                </p>

                <p>
                    <strong>DOI:</strong>
                    {doi}
                </p>

                <p>
                    <strong>Verified Ranking:</strong>
                    🏆 {ranking}
                </p>

                <p>
                    <strong>Ranking Source:</strong>
                    {ranking_source}
                </p>

                <p>
                    <strong>Ranking Year:</strong>
                    {ranking_year}
                </p>

                <p>
                    <strong>Access:</strong>
                    {access_badge}
                </p>

                <p>
                    <strong>Citations:</strong>
                    {citations}
                </p>

                <p>
                    <strong>Discovered Through:</strong>
                    {sources}
                </p>

                {link_button}

            </div>
            """

            paper_cards.append(
                card
            )

        paper_cards_html = (
            "\n".join(
                paper_cards
            )
        )

        return f"""
        <!DOCTYPE html>

        <html>

        <head>
            <meta charset="UTF-8">
        </head>

        <body
            style="
                margin:0;
                padding:0;
                background:#f3f4f6;
                font-family:
                    Arial,
                    Helvetica,
                    sans-serif;
                color:#1f2937;
            "
        >

            <div
                style="
                    max-width:760px;
                    margin:0 auto;
                    padding:30px 18px;
                "
            >

                <div
                    style="
                        background:#111827;
                        color:#ffffff;
                        padding:28px;
                        border-radius:14px 14px 0 0;
                    "
                >

                    <h1
                        style="
                            margin:0 0 8px 0;
                        "
                    >
                        📚 Research Paper Agent
                    </h1>

                    <p
                        style="
                            margin:0;
                            color:#d1d5db;
                        "
                    >
                        Verified Q1 • Q2 • HEC W
                        Research Papers
                    </p>

                </div>

                <div
                    style="
                        background:#ffffff;
                        padding:24px;
                        border-left:1px solid #e5e7eb;
                        border-right:1px solid #e5e7eb;
                    "
                >

                    <h2>
                        Search Summary
                    </h2>

                    <p>
                        <strong>Topic:</strong>
                        {safe_keyword}
                    </p>

                    <p>
                        <strong>Publication Years:</strong>
                        {year_text}
                    </p>

                    <p>
                        <strong>
                            Verified Papers:
                        </strong>
                        {len(papers)}
                    </p>

                    <div
                        style="
                            background:#ecfdf5;
                            border-left:4px solid #059669;
                            padding:14px;
                            border-radius:5px;
                            line-height:1.6;
                        "
                    >
                        Only papers whose journal ranking
                        was verified as
                        <strong>Q1, Q2 or HEC W</strong>
                        are included in this email.
                    </div>

                </div>

                <div
                    style="
                        background:#f9fafb;
                        padding:24px;
                        border-left:1px solid #e5e7eb;
                        border-right:1px solid #e5e7eb;
                    "
                >

                    <h2>
                        Research Papers
                    </h2>

                    {paper_cards_html}

                </div>

                <div
                    style="
                        background:#ffffff;
                        padding:24px;
                        border-left:1px solid #e5e7eb;
                        border-right:1px solid #e5e7eb;
                    "
                >

                    <h2>
                        🏆 Journal Ranking
                    </h2>

                    <p>
                        <strong>Q1:</strong>
                        Verified first-quartile journal.
                    </p>

                    <p>
                        <strong>Q2:</strong>
                        Verified second-quartile journal.
                    </p>

                    <p>
                        <strong>W:</strong>
                        Verified HEC Pakistan W-category
                        journal.
                    </p>

                    <p>
                        Q3, Q4 and unverified journals
                        are excluded from these results.
                    </p>

                    <h2>
                        🔓 Paper Access
                    </h2>

                    <p>
                        <strong>Free PDF:</strong>
                        A freely accessible PDF was found.
                    </p>

                    <p>
                        <strong>Open Access:</strong>
                        An open-access version was found.
                    </p>

                    <p>
                        <strong>
                            Publisher / Institutional Access:
                        </strong>
                        The paper may require access through
                        a university, library or subscription.
                    </p>

                </div>

                <div
                    style="
                        background:#111827;
                        color:#d1d5db;
                        padding:20px;
                        border-radius:0 0 14px 14px;
                        text-align:center;
                        font-size:13px;
                        line-height:1.6;
                    "
                >

                    <strong
                        style="color:#ffffff;"
                    >
                        Research Paper Agent
                    </strong>

                    <br>

                    Q1 • Q2 • HEC W Academic Discovery

                    <br><br>

                    Search metadata may come from
                    OpenAlex, Crossref and Semantic Scholar.

                    <br>

                    Access information may be enriched
                    using Unpaywall.

                </div>

            </div>

        </body>

        </html>
        """

    # ======================================================
    # TARGET-RANKING CHECK
    # ======================================================

    def _is_target_ranked_paper(
        self,
        paper: Paper,
    ) -> bool:
        """
        Return True only for verified Q1/Q2/W papers.
        """

        if not paper.ranking_verified:

            return False

        categories = set(
            paper.verified_categories
            or []
        )

        if (
            paper.category
            and paper.category
            != "Not Verified"
        ):

            categories.add(
                paper.category
            )

        return bool(
            categories.intersection(
                self.TARGET_CATEGORIES
            )
        )

    # ======================================================
    # RANKING LABEL
    # ======================================================

    def _ranking_label(
        self,
        paper: Paper,
    ) -> str:
        """
        Return only target ranking labels.
        """

        categories: list[str] = []

        for category in (
            paper.verified_categories
            or []
        ):

            if (
                category
                in self.TARGET_CATEGORIES
                and category
                not in categories
            ):

                categories.append(
                    category
                )

        if (
            paper.ranking_verified
            and paper.category
            in self.TARGET_CATEGORIES
            and paper.category
            not in categories
        ):

            categories.append(
                paper.category
            )

        if categories:

            return ", ".join(
                categories
            )

        return "Unavailable"

    # ======================================================
    # ACCESS LABEL
    # ======================================================

    @staticmethod
    def _access_label(
        paper: Paper,
    ) -> str:
        """
        Return paper-access label.
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

    # ======================================================
    # EXTRACT LINKS
    # ======================================================

    @staticmethod
    def _extract_links(
        papers: list[Paper],
    ) -> list[str]:
        """
        Extract unique preferred paper links.
        """

        links: list[str] = []

        for paper in papers:

            link = (
                paper.preferred_link()
            )

            if not link:

                continue

            if link in links:

                continue

            links.append(
                link
            )

        return links