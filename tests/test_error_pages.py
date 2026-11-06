"""Error pages keep the app shell (witus docs/shared-ui-ux-dx.md, 2026-11-04).

With DEBUG off, Django renders templates/404.html and templates/500.html. Both extend the base, so
a lost visitor still gets the header with "Sign in" and the footer. The 500 page is rendered the way
Django's server_error view renders it: no request, no context processors.
"""

import pytest
from django.test import Client, RequestFactory, override_settings
from django.views.defaults import server_error

from tests.test_ch04 import SIGN_IN, element, links_in


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_missing_page_is_a_404_with_header_and_footer(client: Client) -> None:
    response = client.get("/this-page-does-not-exist-xyz/")
    assert response.status_code == 404
    html = response.content.decode()
    assert SIGN_IN in links_in(element(html, "header"))
    assert "<footer" in html
    assert html.count("<h1") == 1
    assert ("/", "Back to the home page") in links_in(element(html, "main"))


@override_settings(DEBUG=False)
def test_server_error_page_keeps_header_and_footer() -> None:
    response = server_error(RequestFactory().get("/boom/"))
    assert response.status_code == 500
    html = response.content.decode()
    assert SIGN_IN in links_in(element(html, "header"))
    assert "<footer" in html
    assert html.count("<h1") == 1
    assert "Traceback" not in html
