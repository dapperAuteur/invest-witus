"""The public pages. A view takes a request and returns a response; the templates do the HTML."""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe

from invest_witus_site.pages.forms import WaitlistForm
from invest_witus_site.pages.markdown_pages import load_page
from invest_witus_site.pages.models import WaitlistEntry

# The positioning line, word for word from the PRD (section 7.10).
POSITIONING = (
    "Pick a method you learned. Practice it on paper. "
    "The app keeps you to its rules and shows you the lesson behind each one."
)


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/home.html", {"positioning": POSITIONING, "form": WaitlistForm()})


def waitlist(request: HttpRequest) -> HttpResponse:
    """GET shows the form; POST adds the person once and redirects to the thank-you page.

    Redirecting after a POST (Post/Redirect/Get) means a browser refresh repeats a harmless GET,
    not the form submission. The thank-you is the same whether the address was new or already on
    the list, so the page never reveals who signed up.
    """
    if request.method != "POST":
        return render(request, "pages/waitlist.html", {"form": WaitlistForm()})
    form = WaitlistForm(request.POST)
    if not form.is_valid():
        return render(request, "pages/waitlist.html", {"form": form})
    if not form.is_bot():
        WaitlistEntry.join(name=form.cleaned_data["name"], email=form.cleaned_data["email"])
    # TODO(chapter 13): mirror the signup to WitUS Inbox as a `waitlist-signup` (doc 02, section 6).
    return redirect("waitlist-thanks")


def waitlist_thanks(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/waitlist_thanks.html")


def markdown_page(request: HttpRequest, slug: str) -> HttpResponse:
    page = load_page(settings.SITE_PAGES_DIR, slug)
    # Django escapes everything a template prints. This HTML came from our own Markdown file, so
    # it is marked safe here, on purpose, in one place.
    return render(request, "pages/markdown_page.html", {"page": page, "body": mark_safe(page.html)})


def contact(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/contact.html")


def sign_in_stub(request: HttpRequest) -> HttpResponse:
    """Sign in with WitUS arrives in chapter 07. Until then the link leads somewhere honest."""
    return render(request, "pages/sign_in_stub.html")
