"""The app's URLs. `name` lets templates write `{% url 'faq' %}` instead of a hard-coded path."""

from django.urls import path

from invest_witus_site.pages import views

urlpatterns = [
    path("", views.home, name="home"),
    path("waitlist/", views.waitlist, name="waitlist"),
    path("waitlist/thanks/", views.waitlist_thanks, name="waitlist-thanks"),
    path("faq/", views.markdown_page, {"slug": "faq"}, name="faq"),
    path("privacy/", views.markdown_page, {"slug": "privacy"}, name="privacy"),
    path("terms/", views.markdown_page, {"slug": "terms"}, name="terms"),
    path("contact/", views.contact, name="contact"),
    # The sign-in route (`/auth/witus/login/`, name "sign-in") lives in the accounts app since
    # chapter 07; `sign_in_stub` below is what it renders while the client is off.
]
