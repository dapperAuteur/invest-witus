"""The monthly review's buys on a paper account: stage them from the plan, place them when the owner
confirms, and copy Alpaca's answers back into the journal.

Three jobs, in the order they happen:

1. `month_buys` stages this month's buys from the active plan: the plan's amount split across its
   symbols to the cent, each with its deterministic `client_order_id`, and the one reason, if any,
   that Confirm is not offered (outside the window, no practice budget, over the budget, a buy
   already logged by hand, more than one symbol).
2. `confirm` places what is staged and not yet placed, one order per symbol, and writes one
   journal entry per order. A second click, a retry after a timeout, or two clicks at once find
   the same row (unique `client_order_id`) and the same Alpaca order, so nothing is bought twice.
3. `sync_orders` reads every open order back from Alpaca and fixes its row and its journal entry:
   the shares filled, the amount, and no entry at all for an order that ended with nothing filled.

Nothing here runs without the owner's click except the sync, which only reads.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import transaction
from django.utils import timezone

from invest_witus.money import CENT, to_money, to_shares
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.paper.alpaca import (
    PAPER_HOST,
    AlpacaError,
    AlpacaNotFound,
    AlpacaPaper,
    AlpacaRateLimited,
    AlpacaRefused,
    MarketClock,
    PaperOrderState,
    paper_client,
)
from invest_witus_site.paper.models import PaperOrder, client_order_id

ZERO = Decimal("0")
NOTE_LIMIT = 200


def today() -> date:
    """The app's today. A function, so a test can fix the day the way chapter 03's `--through`
    fixed the review's."""
    return timezone.localdate()


def month_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def alpaca_allowed(user: AbstractBaseUser | AnonymousUser, account: Account) -> bool:
    """Alpaca is the site owner's: the server holds one pair of paper keys, so only a superuser,
    on an account linked to Alpaca paper, may read it or place orders through it. The caller has
    already fetched the account with `owner=request.user`."""
    return account.is_alpaca_paper and getattr(user, "is_superuser", False) is True


# --- 1. Stage -----------------------------------------------------------------------------------


def split_amount(amount: Decimal, symbols: list[str]) -> list[tuple[str, Decimal]]:
    """The amount in equal parts to the cent, one per symbol, in the plan's order. The cents that
    do not divide go one each to the first symbols, so the parts add up to the amount exactly:
    100.00 over three symbols is 33.34, 33.33 and 33.33."""
    if not symbols:
        raise ValueError("no symbols to split across")
    cents = int(to_money(amount) / CENT)
    each, left_over = divmod(cents, len(symbols))
    return [
        (symbol, (each + (1 if index < left_over else 0)) * CENT)
        for index, symbol in enumerate(symbols)
    ]


def practice_spent(plan: MethodPlan) -> Decimal:
    """What the plan has spent of its practice budget: every buy in the account's journal since
    the plan started, placed through Alpaca or logged by hand. A pending order has its entry
    already, so its money is spent the moment it is placed."""
    buys = JournalEntry.objects.filter(
        account=plan.account, action="buy", date__gte=plan.started_on
    ).values_list("amount", flat=True)
    return sum(buys, ZERO)


@dataclass(frozen=True, slots=True)
class StagedBuy:
    symbol: str
    notional: Decimal
    client_order_id: str
    order: PaperOrder | None

    @property
    def placed(self) -> bool:
        return self.order is not None and self.order.placed


@dataclass(frozen=True, slots=True)
class MonthBuys:
    """This month's buys for one plan, and why Confirm is not offered, in words, when it is not."""

    month: str
    window_closes: date
    buys: list[StagedBuy]
    total: Decimal
    budget: Decimal | None
    spent: Decimal
    refusal: str

    @property
    def left(self) -> Decimal | None:
        return None if self.budget is None else self.budget - self.spent

    @property
    def to_place(self) -> list[StagedBuy]:
        return [buy for buy in self.buys if not buy.placed]

    @property
    def can_confirm(self) -> bool:
        return not self.refusal and bool(self.to_place)


def month_buys(plan: MethodPlan, day: date) -> MonthBuys:
    month = month_of(day)
    parts = split_amount(plan.amount, plan.symbol_list())
    existing = {order.symbol: order for order in PaperOrder.for_month(plan, month)}
    buys = [
        StagedBuy(
            symbol,
            notional,
            client_order_id(plan.account.pk, plan.pk, month, symbol),
            existing.get(symbol),
        )
        for symbol, notional in parts
    ]
    window_closes = date(day.year, day.month, plan.buy_window_days)
    spent = practice_spent(plan)
    unplaced = sum((buy.notional for buy in buys if not buy.placed), ZERO)
    budget = plan.practice_budget
    return MonthBuys(
        month=month,
        window_closes=window_closes,
        buys=buys,
        total=sum((notional for _, notional in parts), ZERO),
        budget=budget,
        spent=spent,
        refusal=refusal_for(plan, day, window_closes, buys, unplaced, budget, spent),
    )


def refusal_for(
    plan: MethodPlan,
    day: date,
    window_closes: date,
    buys: list[StagedBuy],
    unplaced: Decimal,
    budget: Decimal | None,
    spent: Decimal,
) -> str:
    """The first reason Confirm cannot be pressed, or "" when it can. Each is a sentence the page
    prints as it is."""
    if day < plan.started_on:
        return f"The plan starts on {plan.started_on:%Y-%m-%d}; nothing is due before then."
    if day > window_closes:
        return (
            f"This month's window closed on {window_closes:%Y-%m-%d}. The method has no catching "
            "up: the next window opens on the 1st."
        )
    if len(buys) > 1:
        return (
            f"The plan names {len(buys)} symbols. This method's rules count one buy of the plan's "
            "amount each month, so split orders would show as findings; the app places a month's "
            "buys for a plan with one symbol."
        )
    if hand_logged_buys(plan, day):
        return f"A buy for {month_of(day)} is already in the journal, logged by hand."
    if not any(not buy.placed for buy in buys):
        return ""
    if budget is None:
        return "Set a practice budget for this plan first: the app's own number, in the admin."
    if unplaced > budget - spent:
        return (
            f"This month's buys, {unplaced:.2f}, are more than the practice budget left, "
            f"{budget - spent:.2f}."
        )
    return ""


def hand_logged_buys(plan: MethodPlan, day: date) -> bool:
    """A buy this month in the journal that no paper order wrote: the owner already bought."""
    from_orders = PaperOrder.objects.filter(account=plan.account).exclude(journal_entry=None)
    return (
        JournalEntry.objects.filter(
            account=plan.account, action="buy", date__year=day.year, date__month=day.month
        )
        .exclude(pk__in=from_orders.values("journal_entry"))
        .exists()
    )


@dataclass(frozen=True, slots=True)
class PaperSection:
    """What the method page's "This month's buys" box needs: the staged buys, the clock, and the
    one error to show instead when Alpaca did not answer."""

    stage: MonthBuys
    clock: MarketClock | None
    error: str

    @property
    def host(self) -> str:
        return PAPER_HOST

    @property
    def queues_past_window(self) -> bool:
        """Closed now, and the next open is after the window: the fill will land outside it."""
        return (
            self.clock is not None
            and not self.clock.is_open
            and self.clock.next_open.date() > self.stage.window_closes
        )


def paper_section(plan: MethodPlan) -> PaperSection:
    """Built by the method page for a linked account. One request to Alpaca, the clock."""
    stage = month_buys(plan, today())
    try:
        clock = paper_client().clock()
    except AlpacaError as error:
        return PaperSection(stage, None, error.message)
    return PaperSection(stage, clock, "")


# --- 2. Confirm ---------------------------------------------------------------------------------


class ConfirmRefused(Exception):
    """The staged buys may not be placed; the message is `MonthBuys.refusal`."""


@dataclass(slots=True)
class ConfirmResult:
    clock: MarketClock
    placed: list[PaperOrder] = field(default_factory=list[PaperOrder])
    already: list[PaperOrder] = field(default_factory=list[PaperOrder])
    failed: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])


def confirm(plan: MethodPlan, day: date, client: AlpacaPaper) -> ConfirmResult:
    """Place this month's staged buys that are not placed yet. The checks run again here, on the
    server, whatever the page showed: a stale tab cannot buy outside the window or the budget."""
    stage = month_buys(plan, day)
    if stage.refusal:
        raise ConfirmRefused(stage.refusal)
    # Asked first, so a closed market is known before anything is sent; an error here stops the
    # whole confirm with nothing placed.
    result = ConfirmResult(clock=client.clock())
    for buy in stage.buys:
        if buy.placed and buy.order is not None:
            result.already.append(buy.order)
            continue
        try:
            order, new = place_one(plan, buy, day, client)
        except AlpacaError as error:
            result.failed.append((buy.symbol, error.message))
            continue
        (result.placed if new else result.already).append(order)
    return result


def place_one(
    plan: MethodPlan, buy: StagedBuy, day: date, client: AlpacaPaper
) -> tuple[PaperOrder, bool]:
    """One buy, at most once. The row is created or found by its `client_order_id` and locked for
    the length of the call (Postgres; SQLite has one writer anyway), so a second request for the
    same buy waits, then finds the order placed and returns it. A row that already existed
    without an Alpaca id means an earlier try may have reached Alpaca before failing here, so
    Alpaca is asked for that id before anything is sent."""
    failure: AlpacaError | None = None
    with transaction.atomic():
        order, created = PaperOrder.objects.select_for_update().get_or_create(
            client_order_id=buy.client_order_id,
            defaults={
                "account": plan.account,
                "plan": plan,
                "month": month_of(day),
                "symbol": buy.symbol,
                "notional": buy.notional,
            },
        )
        if order.placed:
            return order, False
        try:
            state = submit(client, order, look_first=not created)
        except AlpacaError as error:
            # Kept on the row, so the page can say why, and committed with it: the exception is
            # raised after the block, not inside it, which would roll the message back.
            order.message = error.message[:240]
            order.save(update_fields=["message", "updated_at"])
            failure = error
        else:
            apply_state(order, state)
            order.message = ""
            order.save()
            reconcile_journal(order, day)
            return order, True
    raise failure


def submit(client: AlpacaPaper, order: PaperOrder, look_first: bool) -> PaperOrderState:
    """Send the order, unless Alpaca already has one with this id. Alpaca refuses a repeated
    `client_order_id` with 422 "client_order_id must be unique"; that answer means the order
    exists, so it is read back rather than reported as a failure."""
    if look_first:
        try:
            return client.order_by_client_id(order.client_order_id)
        except AlpacaNotFound:
            pass
    try:
        return client.buy_notional(order.symbol, order.notional, order.client_order_id)
    except AlpacaRefused as error:
        if error.status == 422 and "client_order_id" in error.message:
            return client.order_by_client_id(order.client_order_id)
        raise


def apply_state(order: PaperOrder, state: PaperOrderState) -> None:
    order.alpaca_id = state.id
    order.status = state.status
    order.filled_qty = state.filled_qty
    order.filled_avg_price = state.filled_avg_price
    order.submitted_at = state.submitted_at
    order.filled_at = state.filled_at


# --- The journal entry an order writes ----------------------------------------------------------


def journal_amount(order: PaperOrder) -> Decimal:
    """The money that changed hands. A full fill spent the notional; an order that ended part
    filled spent shares times the average price; an order still open is booked at its notional,
    so the practice budget counts it now."""
    partly_done = order.final and order.status != "filled" and order.filled_qty > 0
    if partly_done and order.filled_avg_price is not None:
        return to_money(order.filled_qty * order.filled_avg_price)
    return order.notional


def journal_note(order: PaperOrder) -> str:
    note = f"Alpaca paper order {order.alpaca_id}: {order.status}"
    if order.final and order.filled_qty > 0 and order.filled_avg_price is not None:
        when = f" on {order.filled_at:%Y-%m-%d}" if order.filled_at else ""
        note += f", {to_shares(order.filled_qty)} shares at {order.filled_avg_price}{when}"
    return note[:NOTE_LIMIT]


def reconcile_journal(order: PaperOrder, day: date | None = None) -> None:
    """Make the order's journal entry say what Alpaca says. Shares are recorded once the order is
    final; an order that ended with nothing filled was never a trade, so its entry is removed and
    the row keeps the history. The entry's date is the day the owner confirmed, which is the act
    the method's window rule is about; the fill's date is in the note."""
    entry = order.journal_entry
    if order.final and order.filled_qty == 0:
        if entry is not None:
            order.journal_entry = None
            order.save(update_fields=["journal_entry", "updated_at"])
            entry.delete()
        return
    shares = to_shares(order.filled_qty) if order.final and order.filled_qty > 0 else None
    if entry is None:
        entry = JournalEntry.objects.create(
            account=order.account,
            date=day or today(),
            action="buy",
            symbol=order.symbol,
            amount=journal_amount(order),
            shares=shares,
            note=journal_note(order),
        )
        order.journal_entry = entry
        order.save(update_fields=["journal_entry", "updated_at"])
        return
    entry.amount = journal_amount(order)
    entry.shares = shares
    entry.note = journal_note(order)
    entry.save()


# --- 3. Sync ------------------------------------------------------------------------------------


@dataclass(slots=True)
class SyncResult:
    checked: int = 0
    changed: int = 0
    filled: int = 0
    ended_part_filled: int = 0
    ended_unfilled: int = 0
    still_open: int = 0
    failed: dict[str, str] = field(default_factory=dict[str, str])

    def as_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "changed": self.changed,
            "filled": self.filled,
            "ended_part_filled": self.ended_part_filled,
            "ended_unfilled": self.ended_unfilled,
            "still_open": self.still_open,
            "failed": self.failed,
        }


def sync_orders(client: AlpacaPaper, account: Account | None = None) -> SyncResult:
    """Read every open order back and fix its row and its journal entry. Idempotent: an order that
    did not change writes nothing new, and a final order is never asked about again. One order
    Alpaca refuses is recorded and the rest go on; a 429 stops the run for the next one."""
    result = SyncResult()
    for order in PaperOrder.open_orders(account):
        result.checked += 1
        try:
            state = client.order(order.alpaca_id)
        except AlpacaRateLimited as error:
            result.failed[order.client_order_id] = error.message
            break
        except AlpacaError as error:
            result.failed[order.client_order_id] = error.message
            continue
        before = (order.status, order.filled_qty)
        apply_state(order, state)
        if (order.status, order.filled_qty) != before:
            result.changed += 1
            with transaction.atomic():
                order.save()
                reconcile_journal(order)
        if order.status == "filled":
            result.filled += 1
        elif not order.final:
            result.still_open += 1
        elif order.filled_qty > 0:
            result.ended_part_filled += 1
        else:
            result.ended_unfilled += 1
    return result
