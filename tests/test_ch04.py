"""Chapter 04 checkpoint: the public site, its header, footer, legal pages and waitlist."""

import re
from html.parser import HTMLParser

import pytest
from django.conf import settings
from django.test import Client

from invest_witus_site.pages.markdown_pages import render_markdown, trim_url
from invest_witus_site.pages.models import WaitlistEntry

PUBLIC_PATHS = [
    "/",
    "/faq/",
    "/privacy/",
    "/terms/",
    "/contact/",
    "/waitlist/",
    "/waitlist/thanks/",
    "/auth/witus/login/",
]
POSITIONING = (
    "Pick a method you learned. Practice it on paper. "
    "The app keeps you to its rules and shows you the lesson behind each one."
)
SIGN_IN = ("/auth/witus/login/", "Sign in")
MARKETING_RULE = (
    "https://www.ecfr.gov/api/versioner/v1/full/2026-10-23/title-17.xml"
    "?part=275&section=275.206(4)-1"
)


class LinkCollector(HTMLParser):
    """Collects (href, text) for every <a>, naming a link the way a screen reader does: by text."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def links_in(html: str) -> list[tuple[str, str]]:
    collector = LinkCollector()
    collector.feed(html)
    return collector.links


def element(html: str, tag: str) -> str:
    """The first <tag>...</tag> block of the page, as text."""
    match = re.search(rf"<{tag}\b.*?</{tag}>", html, re.DOTALL)
    assert match, f"no <{tag}> on the page"
    return match.group(0)


def get(client: Client, path: str) -> str:
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"
    return response.content.decode()


def test_home_shows_the_positioning_line(client: Client) -> None:
    assert POSITIONING in get(client, "/")


def test_home_credits_the_course_and_says_lesson_coming(client: Client) -> None:
    html = get(client, "/")
    assert "freeCodeCamp" in html
    assert "lesson coming" in html
    assert ("/faq/#report-a-bad-actor", "Where to report") in links_in(html)


@pytest.mark.smoke
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_every_public_page_has_the_sign_in_link(client: Client, path: str) -> None:
    """The header link whose accessible name is exactly "Sign in". Never renamed, never removed."""
    assert SIGN_IN in links_in(element(get(client, path), "header"))


def test_sign_in_is_an_honest_stub_until_chapter_07(client: Client) -> None:
    assert "chapter 07" in get(client, "/auth/witus/login/")


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_every_public_page_says_not_advice(client: Client, path: str) -> None:
    assert "Not advice" in get(client, path)


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_no_public_page_shows_a_price_table_or_a_performance_figure(
    client: Client, path: str
) -> None:
    """PRD 7.10, checked narrowly: no <table> at all, and no signed percentage like +8.5% or -12%.

    A dollar amount is not a price: the FAQ's "$25,000" regulatory threshold must pass.
    """
    html = get(client, path)
    assert "<table" not in html.lower()
    assert re.search(r"[+-]\d+(?:\.\d+)?\s?%", html) is None


def test_internal_footer_links_resolve(client: Client) -> None:
    footer_links = links_in(element(get(client, "/"), "footer"))
    internal = {href.split("#")[0] for href, _ in footer_links if href.startswith("/")}
    assert internal, "the footer has no internal links"
    for href in sorted(internal):
        get(client, href)


def test_footer_lists_the_ecosystem_and_keeps_the_disclaimer(client: Client) -> None:
    footer = element(get(client, "/"), "footer")
    assert ("https://learn.witus.online", "Learn.WitUS (opens in new tab)") in links_in(footer)
    assert SIGN_IN in links_in(footer)
    assert "Rise Wellness of Indiana is an independent organization." in footer
    assert "not affiliated with, employed by, or endorsed by Invest.WitUS," in footer
    assert "B4C LLC" in footer


@pytest.mark.parametrize(
    "path, heading",
    [("/privacy/", "Privacy"), ("/terms/", "Terms of use"), ("/faq/", "Invest.WitUS FAQ")],
)
def test_markdown_pages_render_their_headings(client: Client, path: str, heading: str) -> None:
    html = get(client, path)
    assert heading in element(html, "h1")


def test_faq_has_the_report_anchor_and_links_the_marketing_rule(client: Client) -> None:
    html = get(client, "/faq/")
    assert 'id="report-a-bad-actor"' in html
    assert (MARKETING_RULE, MARKETING_RULE) in links_in(html)
    assert ("/faq/#report-a-bad-actor", "Report a bad actor") in links_in(element(html, "footer"))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("https://example.test/a).", "https://example.test/a"),
        ("https://example.test/x(4)-1", "https://example.test/x(4)-1"),
        ("https://example.test/b/.", "https://example.test/b/"),
    ],
)
def test_bare_urls_lose_their_sentence_punctuation(text: str, expected: str) -> None:
    assert trim_url(text) == expected


def test_a_bare_url_in_markdown_becomes_a_link() -> None:
    html = render_markdown("See https://example.test/page?a=1&b=2, then stop.")
    assert ("https://example.test/page?a=1&b=2", "https://example.test/page?a=1&b=2") in links_in(
        html
    )


@pytest.mark.django_db
def test_joining_twice_keeps_one_row_and_shows_the_same_thank_you(client: Client) -> None:
    first = client.post("/waitlist/", {"name": "Ada", "email": "Ada@Example.com "}, follow=True)
    second = client.post("/waitlist/", {"name": "Ada", "email": "ada@example.com"}, follow=True)
    assert first.redirect_chain == [("/waitlist/thanks/", 302)]
    assert first.content == second.content
    assert "You are on the list." in first.content.decode()
    assert WaitlistEntry.objects.count() == 1
    assert WaitlistEntry.objects.get().email == "ada@example.com"


@pytest.mark.django_db
def test_a_bad_email_is_refused_with_a_message(client: Client) -> None:
    response = client.post("/waitlist/", {"name": "Ada", "email": "not-an-email"})
    assert response.status_code == 200
    assert "Enter a valid email address." in response.content.decode()
    assert WaitlistEntry.objects.count() == 0


@pytest.mark.django_db
def test_the_honeypot_keeps_bots_out_quietly(client: Client) -> None:
    data = {"name": "Bot", "email": "bot@example.com", "website": "https://spam.test"}
    response = client.post("/waitlist/", data)
    assert response.status_code == 302 and response["Location"] == "/waitlist/thanks/"
    assert WaitlistEntry.objects.count() == 0


def test_a_post_without_a_csrf_token_is_refused() -> None:
    strict = Client(enforce_csrf_checks=True)
    response = strict.post("/waitlist/", {"name": "Ada", "email": "ada@example.com"})
    assert response.status_code == 403


def test_settings_are_safe_by_default() -> None:
    """Debug off, the database in the folder git ignores, a labeled dev-only key."""
    assert settings.DEBUG is False
    assert settings.DATA_DIR == settings.BASE_DIR / "data" / "private"
    assert settings.SECRET_KEY.startswith("django-insecure-") or len(settings.SECRET_KEY) >= 50
