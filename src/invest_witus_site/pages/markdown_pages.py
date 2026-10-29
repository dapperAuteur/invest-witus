"""Render the site's Markdown pages (`docs/site/*.md`) to HTML."""

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor

# The pages the site serves and the file behind each. A fixed table, not a URL parameter, so a
# request can never name a file outside this folder.
PAGES = {"faq": "faq.md", "privacy": "privacy.md", "terms": "terms.md"}

# A URL written bare in the text. Not preceded by a quote, `=` or `>`, so a URL that is already
# inside an HTML tag is left alone.
BARE_URL = r"(?<![\w\"'=>])https?://[^\s<>\"']+"
TRAILING_PUNCTUATION = ".,;:!?"


@dataclass(frozen=True, slots=True)
class Page:
    title: str
    html: str


def trim_url(url: str) -> str:
    """Drop the sentence punctuation a bare URL picks up, but keep balanced parentheses.

    `https://example.test/a).` becomes `https://example.test/a`;
    `https://example.test/x(4)-1` stays as it is.
    """
    while True:
        before = url
        url = url.rstrip(TRAILING_PUNCTUATION)
        if url.endswith(")") and url.count("(") < url.count(")"):
            url = url[:-1]
        if url == before:
            return url


class BareUrlProcessor(InlineProcessor):
    """Turn a bare `https://...` in the text into a link whose text is the URL."""

    def handleMatch(  # noqa: N802 (Python-Markdown's name)
        self, m: re.Match[str], data: str
    ) -> tuple[ElementTree.Element, int, int]:
        url = trim_url(m.group(0))
        link = ElementTree.Element("a")
        link.set("href", url)
        link.text = url
        return link, m.start(0), m.start(0) + len(url)


class BareUrlExtension(Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:  # noqa: N802
        # Priority 115: after Markdown's own `[text](url)` and `<url>` patterns (160 and 120),
        # before emphasis (60), so an underscore inside a URL is never read as italics.
        md.inlinePatterns.register(BareUrlProcessor(BARE_URL, md), "bare_url", 115)


def render_markdown(text: str) -> str:
    # `toc` gives every heading an id made from its text ("Report a bad actor" becomes
    # `report-a-bad-actor`), which is what the landing page and the footer link to.
    converter = markdown.Markdown(extensions=["toc", BareUrlExtension()])
    return converter.convert(text)


# An `<h3>` on a page: the FAQ writes every question as one. `toc` has already given it an id.
H3 = re.compile(r'<h3 id="(?P<id>[^"]*)">(?P<text>.*?)</h3>\n?', re.S)
# Where a question's answer ends: the next question or the next section heading.
NEXT_HEADING = re.compile(r"(?=<h[23]\b)")


def fold_questions(html: str) -> str:
    """Wrap each `<h3>` question and its answer in `<details>`, so the page opens as a list of
    questions and each one expands to its answer. The heading's id moves to the `<details>`
    element, so `#some-question` links keep working and open nothing but the right block. The
    `<h2>` sections stay as they are."""
    parts = NEXT_HEADING.split(html)
    out: list[str] = []
    for part in parts:
        m = H3.match(part)
        if not m:
            out.append(part)
            continue
        answer = part[m.end() :]
        out.append(
            f'<details class="faq-item" id="{m.group("id")}">'
            f"<summary>{m.group('text')}</summary>\n{answer}</details>\n"
        )
    return "".join(out)


def load_page(pages_dir: Path, slug: str) -> Page:
    """Read one of the pages in PAGES and render it. The title is the file's first `# ` heading."""
    text = (pages_dir / PAGES[slug]).read_text(encoding="utf-8")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), slug)
    html = render_markdown(text)
    if slug == "faq":
        html = fold_questions(html)
    return Page(title=title, html=html)
