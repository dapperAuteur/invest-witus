"""The header's "Paper account" link: the id of the signed-in owner's account linked to Alpaca
paper, for the pages that may open it, and nothing for anyone else. Since decision 159 an owner
may link several accounts (one Alpaca paper account each); then the header says "Paper accounts"
and links the key slot list, which links each one.

The rule is the paper page's own (`orders.alpaca_allowed`): a superuser who owns an account
linked to Alpaca paper. A signed-out visitor and a signed-in owner without that account get no
key, so the header shows no link and no query runs for a visitor.
"""

from django.http import HttpRequest

from invest_witus_site.holdings.models import Account


def paper_link(request: HttpRequest) -> dict[str, object]:
    user = request.user
    if not user.is_authenticated or not getattr(user, "is_superuser", False):
        return {}
    linked = list(
        Account.objects.filter(owner_id=user.pk, alpaca=Account.Alpaca.PAPER).values_list(
            "pk", flat=True
        )[:2]
    )
    if not linked:
        return {}
    if len(linked) > 1:
        return {"paper_accounts_several": True}
    return {"paper_account_id": linked[0]}
