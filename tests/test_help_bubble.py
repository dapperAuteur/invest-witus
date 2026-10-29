"""The floating Help bubble (2026-10-30, decision 151, backlog item 4): on every page, signed in
or out, beside the header and footer links. Signed out it is a plain link to `/report/`, so the
public pages still carry no script (chapter 06a). Signed in, `pages/help.js` turns it into a
`<button>` that opens the same report form in a `<dialog>`. The browser behaviour (focus,
Escape, 320 and 1024 pixels) was checked in headless Chromium; these tests pin the markup it
relies on.
"""

import re
from collections import Counter
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client

from invest_witus_site.holdings.models import Account
from invest_witus_site.reports.models import Report
from tests.test_ch04 import PUBLIC_PATHS

STATIC = Path(__file__).resolve().parent.parent / "src" / "invest_witus_site" / "pages" / "static"
LINK = (
    '<a class="help-bubble" href="/report/" data-help-link>Help'
    '<span class="sr-only">: report a problem or ask a question</span></a>'
)
SCRIPT = '<script src="/static/pages/help.js" defer></script>'


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", "owner@example.com", "pw")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(name="Practice", broker="Example", kind="paper", owner=owner)


def html_of(client: Client, path: str) -> str:
    return client.get(path).content.decode()


def duplicate_ids(html: str) -> list[str]:
    counts = Counter(re.findall(r'\sid="([^"]+)"', html))
    return [name for name, count in counts.items() if count > 1]


# --- Signed out: a link, no script --------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_every_public_page_has_the_bubble_as_a_plain_link_and_no_script(
    client: Client, path: str
) -> None:
    html = html_of(client, path)
    assert LINK in html
    assert "<script" not in html and "<dialog" not in html and "data-help-button" not in html


@pytest.mark.django_db
def test_the_report_form_has_no_bubble_of_its_own(client: Client, owner: User) -> None:
    assert "help-bubble" not in html_of(client, "/report/")
    client.force_login(owner)
    assert "help-bubble" not in html_of(client, "/report/")


@pytest.mark.django_db
def test_the_header_and_footer_links_stay(client: Client) -> None:
    html = html_of(client, "/faq/")
    assert html.count('<a href="/report/">Report a problem or ask a question</a>') == 2


# --- Signed in: a button, a dialog, the form -----------------------------------------------------


@pytest.mark.django_db
def test_signed_in_the_bubble_is_a_button_that_opens_the_report_form(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    path = f"/accounts/{account.pk}/"
    html = html_of(client, path)
    assert LINK in html, "the link stays for a browser without JavaScript"
    assert (
        '<button type="button" class="help-bubble" aria-haspopup="dialog" '
        'aria-controls="help-dialog" data-help-button hidden>Help'
    ) in html
    assert (
        '<dialog id="help-dialog" class="help-dialog" aria-labelledby="help-dialog-title">' in html
    )
    assert '<h2 id="help-dialog-title">Report a problem or ask a question</h2>' in html
    assert '<button type="button" class="help-close" data-help-close>Close</button>' in html
    dialog = html[html.index("<dialog") : html.index("</dialog>")]
    assert '<form method="post" action="/report/" class="report-form">' in dialog
    assert 'name="csrfmiddlewaretoken"' in dialog
    assert 'name="kind"' in dialog and 'name="message"' in dialog
    assert f'name="page" value="{path}"' in dialog, "the page is filled in"
    assert 'name="email"' not in dialog, "signed in, the identity says who wrote it"
    assert "Sent as owner, from your WitUS sign-in." in dialog
    assert html.count(SCRIPT) == 1 and html.index("</dialog>") < html.index(SCRIPT)


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/", "/faq/", "/accounts/", "/report/thanks/"])
def test_the_dialogs_ids_never_clash_with_the_pages(client: Client, owner: User, path: str) -> None:
    client.force_login(owner)
    html = html_of(client, path)
    assert "<dialog" in html and duplicate_ids(html) == []
    ids = re.findall(r'\sid="([^"]+)"', html[html.index("<dialog") : html.index("</dialog>")])
    assert all(name.startswith("help") for name in ids), ids


@pytest.mark.django_db
def test_every_described_field_has_its_description(client: Client, owner: User) -> None:
    client.force_login(owner)
    html = html_of(client, "/accounts/")
    dialog = html[html.index("<dialog") : html.index("</dialog>")]
    for target in re.findall(r'aria-describedby="([^"]+)"', dialog):
        assert f'id="{target}"' in dialog, target


@pytest.mark.django_db
def test_the_dialogs_form_files_a_report(client: Client, owner: User, account: Account) -> None:
    client.force_login(owner)
    path = f"/accounts/{account.pk}/"
    response = client.post(
        "/report/", {"kind": "question", "message": "How do I read the chart?", "page": path}
    )
    assert response.status_code == 302 and response.headers["Location"] == "/report/thanks/"
    report = Report.objects.get()
    assert (report.kind, report.page, report.user) == ("question", path, owner)


# --- The script and the styles -------------------------------------------------------------------


def test_the_script_opens_a_modal_moves_focus_and_returns_it() -> None:
    script = (STATIC / "pages" / "help.js").read_text()
    assert "link.hidden = true" in script and "button.hidden = false" in script
    assert 'typeof dialog.showModal !== "function"' in script, "no dialog support: the link stays"
    assert "dialog.showModal()" in script and "first.focus()" in script
    assert 'addEventListener("close"' in script and "button.focus()" in script
    assert "event.target === dialog" in script


def test_the_bubble_is_a_44px_target_in_the_corner_and_hidden_in_print() -> None:
    css = (STATIC / "pages" / "site.css").read_text()
    rule = css[css.index(".help-bubble {") :]
    rule = rule[: rule.index("}")]
    assert "min-height: 2.75rem" in rule and "min-width: 2.75rem" in rule
    wrap = css[css.index(".help-bubble-wrap {") :]
    wrap = wrap[: wrap.index("}")]
    assert "position: fixed" in wrap and "env(safe-area-inset-bottom)" in wrap
    assert ".help-bubble[hidden] { display: none; }" in css
    assert "@media print { .help-bubble-wrap, .help-dialog { display: none; }" in css
