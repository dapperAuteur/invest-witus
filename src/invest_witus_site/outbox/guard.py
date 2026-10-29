"""What may never reach a social draft: anything from the owner's accounts.

Invest.WitUS gives information, not advice, and shows no performance, price or holding on a
public page (CLAUDE.md, invariant 1). A social post is the most public page there is, so every
string in an Outbox body is checked here before it is sent, and the owner's draft is checked
when it is saved:

- only the fields this app sends (`ALLOWED_KEYS`); any other key is refused, so a later change
  cannot add `holdings` or `price` to the body without changing this file and its tests;
- no media (an attached chart or screenshot could carry anything) and always a draft;
- no money amount, no percentage, no share count, no cashtag (`$ABC`);
- no symbol the app holds data for: held, on a statement, watched, in a plan, journaled, ordered
  on paper, or priced. Symbols are stored in capitals, so the match is on whole capitalized words.

This is a net, not a proof: a sentence can describe an account without a number or a symbol. The
owner writes every word, and every draft is approved by hand in Outbox before anything is posted.
"""

import re
from collections.abc import Iterable, Mapping
from typing import cast

ALLOWED_KEYS = frozenset(
    {"external_ref", "platform", "caption", "media_urls", "scheduled_at", "as_draft"}
)
MONEY = re.compile(r"[$€£¥]\s?\d|\d\s?(?:usd|dollars?|bucks)\b", re.IGNORECASE)
PERCENT = re.compile(r"\d\s?%|\d\s?(?:per ?cent|pct)\b", re.IGNORECASE)
SHARES = re.compile(r"\d\s?(?:shares?|units?)\b", re.IGNORECASE)
CASHTAG = re.compile(r"\$[A-Za-z][A-Za-z.\-]{0,9}")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*")


def account_symbols() -> frozenset[str]:
    """Every symbol any table in the app records, each once. Read at check time, so a symbol
    added to the watch list a minute ago is already refused."""
    from invest_witus_site.holdings.models import Holding, SnapshotLine
    from invest_witus_site.methods.models import JournalEntry, MethodPlan
    from invest_witus_site.paper.models import PaperOrder
    from invest_witus_site.prices.models import DailyClose
    from invest_witus_site.watchlist.models import WatchItem

    found: set[str] = set()
    for model in (Holding, SnapshotLine, WatchItem, PaperOrder, JournalEntry, DailyClose):
        found.update(model.objects.values_list("symbol", flat=True).distinct())
    for listed in MethodPlan.objects.values_list("symbols", flat=True):
        found.update(listed.replace(",", " ").split())
    return frozenset(symbol.strip().upper() for symbol in found if symbol and symbol.strip())


def text_problems(label: str, text: str, symbols: Iterable[str]) -> list[str]:
    """Why `text` may not be posted, one sentence each; empty when it may."""
    problems: list[str] = []
    if MONEY.search(text):
        problems.append(f"{label} has a money amount.")
    if PERCENT.search(text):
        problems.append(f"{label} has a percentage.")
    if SHARES.search(text):
        problems.append(f"{label} has a share count.")
    if CASHTAG.search(text):
        problems.append(f"{label} has a cashtag ($ and a symbol).")
    words = {word.rstrip(".-") for word in WORD.findall(text)}
    named = sorted(words & set(symbols))
    if named:
        problems.append(
            f"{label} names {', '.join(named)}, a symbol from your accounts or watch list."
        )
    return problems


def body_problems(document: Mapping[str, object], symbols: Iterable[str]) -> list[str]:
    """Why this Outbox body may not be sent; empty when it may."""
    known = frozenset(symbols)
    problems = [
        f"The field {key!r} is not one this app sends."
        for key in document
        if key not in ALLOWED_KEYS
    ]
    if document.get("as_draft") is not True:
        problems.append("Every post from this app must arrive in Outbox as a draft.")
    if document.get("media_urls") not in (None, []):
        problems.append("This app attaches no media to a post.")
    for key, value in document.items():
        for text in strings_in(value):
            problems.extend(text_problems(f"The field {key!r}", text, known))
    return problems


def strings_in(value: object) -> list[str]:
    """A string, or the strings in a list; the other values in a body are not text."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in cast(list[object], value) if isinstance(item, str)]
    return []
