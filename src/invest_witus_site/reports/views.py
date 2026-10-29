"""`/report/`: report a problem or ask a question, signed in or not.

The view saves the report, then sends it to WitUS Inbox, then redirects to the thank-you page
whatever Inbox said: a failed send is the row's business (`delivery.py`), never the person's.
Signed out, the form asks for an email; signed in, the WitUS identity supplies it. A honeypot
keeps simple bots out quietly, CSRF comes with every Django form, and a rate limit counts the
reports already in the database, because Vercel's functions share no memory to count in.
"""

import hashlib
import hmac
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from invest_witus_site.accounts.models import WitusIdentity
from invest_witus_site.health import app_version
from invest_witus_site.reports.delivery import deliver
from invest_witus_site.reports.forms import ReportForm, page_path
from invest_witus_site.reports.inbox import configured
from invest_witus_site.reports.models import PAGE_LIMIT, Report

# Five reports an hour from one address, and five from one signed-in person. Enough for anyone
# writing by hand; a script hits it on the sixth.
RATE_LIMIT = 5
RATE_WINDOW = timedelta(hours=1)
LIMITED = (
    "You have sent five reports in the last hour, which is the limit. "
    "Your earlier reports are saved; please try again later."
)


def report(request: HttpRequest) -> HttpResponse:
    signed_in = request.user.is_authenticated
    if request.method != "POST":
        form = ReportForm(initial={"page": referrer_path(request)}, signed_in=signed_in)
        return page(request, form)
    form = ReportForm(request.POST, signed_in=signed_in)
    if not form.is_valid():
        return page(request, form)
    if form.is_bot():
        # The same thank-you a person gets, so a bot learns nothing; nothing is saved.
        return redirect("report-thanks")
    user = request.user if isinstance(request.user, User) else None
    key = client_key(request)
    if over_limit(key, user):
        form.add_error(None, LIMITED)
        return page(request, form, status=429)
    email, name = who(user, str(form.cleaned_data.get("email") or ""))
    row = Report.objects.create(
        kind=form.cleaned_data["kind"],
        message=form.cleaned_data["message"],
        page=form.cleaned_data["page"],
        view=view_letter(request, form.cleaned_data["page"]),
        user=user,
        email=email,
        name=name,
        user_agent=request.headers.get("User-Agent", "")[:PAGE_LIMIT],
        app_version=version(),
        origin=request.build_absolute_uri("/").rstrip("/"),
        client_key=key,
    )
    deliver(row)
    return redirect("report-thanks")


def thanks(request: HttpRequest) -> HttpResponse:
    return render(request, "reports/thanks.html")


def page(request: HttpRequest, form: ReportForm, status: int = 200) -> HttpResponse:
    context = {"form": form, "inbox_on": configured()}
    return render(request, "reports/report.html", context, status=status)


def referrer_path(request: HttpRequest) -> str:
    """The path of the page the person came from, when it is a page of this site and not this
    form; otherwise empty. The query string is dropped: it may hold more than the person meant
    to send."""
    referrer = urlsplit(request.headers.get("Referer", ""))
    if referrer.netloc != request.get_host() or referrer.path == reverse("report"):
        return ""
    return page_path(referrer.path)


def view_letter(request: HttpRequest, path: str) -> str:
    """The method page's view (A, B or C, chapter 10) when the report is about a method page."""
    saved = request.session.get("method_view")
    if "/method/" in path and isinstance(saved, str) and saved in ("a", "b", "c"):
        return saved.upper()
    return ""


def client_key(request: HttpRequest) -> str:
    """A keyed hash of the sender's address, so the limit can count without storing the address.
    On Vercel the address is the first entry of `X-Forwarded-For`, which Vercel overwrites with
    the client's public IP (its request headers page, read October 29, 2026); elsewhere it is the
    connection's own address. A header a client sends to a laptop is never trusted."""
    if settings.ON_VERCEL:
        address = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    else:
        address = str(request.META.get("REMOTE_ADDR") or "")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, (address or "unknown").encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def over_limit(key: str, user: User | None) -> bool:
    since = timezone.now() - RATE_WINDOW
    recent = Report.objects.filter(created_at__gte=since)
    if recent.filter(client_key=key).count() >= RATE_LIMIT:
        return True
    return user is not None and recent.filter(user=user).count() >= RATE_LIMIT


def who(user: User | None, typed_email: str) -> tuple[str, str]:
    """The email and name sent with the report: the WitUS identity's when signed in (or the
    user's own, for the owner before their first WitUS sign-in), the typed email otherwise."""
    if user is None:
        return typed_email.strip().lower(), ""
    identity = WitusIdentity.objects.filter(user=user).first()
    if identity is not None:
        return identity.email or user.email, identity.display_name
    return user.email, user.get_username()


def version() -> str:
    """The app's version, and the deployed commit when Vercel names it (PRD 7.8)."""
    commit = settings.GIT_COMMIT_SHA[:7]
    return f"{app_version()}+{commit}" if commit else app_version()
