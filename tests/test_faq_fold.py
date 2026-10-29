"""The FAQ page opens as a list of questions; each expands to its answer (BAM, 2026-10-28)."""

import pytest
from django.test import Client

from invest_witus_site.pages.markdown_pages import fold_questions, render_markdown

SAMPLE = """# Title

## A. Questions

### Is this an adviser?

No. Two sentences.

### Who holds my money?

A broker.

## B. Bodies

**SEC.** Text.
"""


def test_each_question_becomes_details_with_its_answer() -> None:
    html = fold_questions(render_markdown(SAMPLE))
    assert html.count("<details") == 2 and html.count("</details>") == 2
    assert (
        '<details class="faq-item" id="is-this-an-adviser"><summary>Is this an adviser?</summary>'
        in html
    )
    first = html.split("</details>")[0]
    assert "Two sentences." in first and "A broker." not in first
    assert "<h3" not in html, "the heading moved into the summary"
    assert '<h2 id="b-bodies">' in html, "section headings stay"
    assert "<strong>SEC.</strong>" in html.split("</details>")[-1], "section B text stays outside"


def test_a_page_with_no_h3_is_unchanged() -> None:
    html = render_markdown("# T\n\n## Only sections\n\nText.")
    assert fold_questions(html) == html


@pytest.mark.django_db
def test_the_live_faq_folds_and_keeps_the_report_anchor(client: Client) -> None:
    body = client.get("/faq/").content.decode()
    assert body.count("<details") >= 10
    assert 'id="report-a-bad-actor"' in body
    assert "<h3" not in body
