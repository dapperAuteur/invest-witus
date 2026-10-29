"""The header's "Logbook" link (decision 115): the logbook of the signed-in person's first
account, by id, that has a method plan (active or ended) or a journal entry, and nothing for
anyone else.

One link, not a chooser: most owners keep one account, and the logbook page names its account
at the top, so the link never claims to be more than it is. An owner with several accounts
reaches every other logbook from its row on `/accounts/`. A signed-out visitor gets no key and
no query runs; an owner whose accounts have no plan and no entry gets no link, because an
empty logbook is not a place to send someone from every page.
"""

from django.db.models import Exists, OuterRef, Q
from django.http import HttpRequest

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan


def logbook_link(request: HttpRequest) -> dict[str, object]:
    user = request.user
    if not user.is_authenticated:
        return {}
    has_plan = Exists(MethodPlan.objects.filter(account=OuterRef("pk")))
    has_entry = Exists(JournalEntry.objects.filter(account=OuterRef("pk")))
    first = (
        Account.objects.filter(Q(has_plan) | Q(has_entry), owner_id=user.pk)
        .order_by("pk")
        .values_list("pk", flat=True)
        .first()
    )
    return {} if first is None else {"logbook_account_id": first}
