# Chapter 01: Money in Python, and the math of a monthly plan

**Starts from:** tag `v00`. **Ends at:** tag `v01`.
**Written against:** Python 3.14.10, uv 0.13.6 (October 27, 2026).
**Goal:** code that answers "if I put the same amount into an index fund every month, how many shares do I
own, what did they cost on average, and what are they worth now?"
**Time:** 60 to 90 minutes.

## What you will learn

- **Why money is never a float,** and how `Decimal` fixes it (the `0.1 + 0.2` you tried in chapter 00).
- **Modules and imports:** a Python file is a module; a folder with `__init__.py` is a package. `from x import y`
  is `import { y } from "x"`.
- **Dataclasses:** `@dataclass(frozen=True, slots=True)` is a typed, read-only record, close to a TypeScript
  `type` whose fields are all `readonly`.
- **Type hints:** `list[tuple[date, Decimal]]` is `Array<[Date, Decimal]>`.
- **pytest's `parametrize` and `raises`:** one test run against many inputs, and a test that expects an error.

## The method, before the code

The first method the app supports is **index investing with a fixed monthly contribution**. Two ideas, each with
a source you can read in full:

1. **An index fund holds the securities of a market index,** so its return tracks the index instead of trying to
   beat it. The argument for it is mostly about cost. William Sharpe showed with arithmetic alone that before
   costs, the average actively managed dollar must earn the same as the average passively managed dollar, and
   after costs it must earn less (Sharpe, 1991). That is a claim about the *average*; it does not say no active
   manager ever wins. John Bogle, the founder of Vanguard and of its first index fund, made the same case as an
   advocate (Bogle, 1997).
2. **Dollar-cost averaging** usually means splitting a sum you already have into equal pieces invested over time.
   Vanguard's researchers found that investing a lump sum all at once beat common cost-averaging schedules about
   two-thirds of the time in historical and simulated data, while noting cost averaging may suit people very
   averse to losses who would otherwise keep the money in cash (Finlay & Zorn, 2023).

That second point matters for this app. **Putting part of each paycheck into a fund every month is not the
lump-sum question,** because the money arrives over time. There is nothing to "invest all at once." The method
here is the paycheck kind: a fixed amount, on a schedule, into an index fund, without reacting to the news. The
app's job (chapter 03) is helping you keep that schedule.

This tutorial teaches how the method works. It does not recommend a fund or say the method suits you. The code uses
the placeholder symbol `INDEX`, never a real fund.

## Steps

### 01.1 See the float problem for yourself

Listing 01-1, Terminal:

```sh
uv run python
```

```text
>>> 0.1 + 0.2
0.30000000000000004
>>> from decimal import Decimal
>>> Decimal("0.1") + Decimal("0.2")
Decimal('0.3')
>>> exit()
```

Floats are binary fractions; most decimal amounts like 0.1 can't be stored exactly. JavaScript's `number` has the
same problem. `Decimal` stores decimal digits exactly. Always build a `Decimal` from a **string**:
`Decimal(0.1)` copies the float's error into the decimal.

### 01.2 Write the checkpoint test first

Copy this test file into your repo. It fails now, because none of the code it imports exists yet. By the end of
the chapter it passes.

Listing 01-2, Filename: `tests/test_ch01.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from invest_witus.methods.index_dca import buy, plan_purchases, summarize
from invest_witus.money import to_money

D = Decimal


def test_floats_cannot_hold_money_exactly() -> None:
    assert 0.1 + 0.2 != 0.3
    assert D("0.1") + D("0.2") == D("0.3")


def test_to_money_rounds_half_cents_up() -> None:
    assert to_money(D("2.345")) == D("2.35")
    assert to_money(D("2.344")) == D("2.34")


def test_buy_rounds_shares_down() -> None:
    purchase = buy(date(2026, 1, 2), D("100"), D("3"))
    assert purchase.shares == D("33.333333")


@pytest.mark.parametrize(
    "amount, price", [(D("0"), D("10")), (D("100"), D("0")), (D("-5"), D("10"))]
)
def test_buy_rejects_amounts_and_prices_that_are_not_positive(
    amount: Decimal, price: Decimal
) -> None:
    with pytest.raises(ValueError):
        buy(date(2026, 1, 2), amount, price)


def test_a_fixed_amount_buys_more_shares_when_the_price_is_low() -> None:
    high, low = plan_purchases(
        D("100"), [(date(2026, 1, 2), D("100")), (date(2026, 2, 2), D("50"))]
    )
    assert high.shares == D("1")
    assert low.shares == D("2")


def test_summary_of_three_months() -> None:
    prices = [
        (date(2026, 1, 2), D("100")),
        (date(2026, 2, 2), D("50")),
        (date(2026, 3, 2), D("100")),
    ]
    summary = summarize(plan_purchases(D("100"), prices), latest_price=D("100"))
    assert summary.purchases == 3
    assert summary.invested == D("300")
    assert summary.shares == D("4")
    assert summary.average_cost == D("75.00")
    assert summary.value == D("400.00")
    assert summary.gain == D("100.00")


@pytest.mark.parametrize(
    "prices",
    [
        [D("100"), D("50"), D("100")],
        [D("20"), D("25"), D("30"), D("35")],
        [D("80"), D("60"), D("40"), D("60"), D("80")],
    ],
)
def test_average_cost_is_never_above_the_average_price(prices: list[Decimal]) -> None:
    days = [date(2026, month, 2) for month in range(1, len(prices) + 1)]
    summary = summarize(plan_purchases(D("100"), list(zip(days, prices, strict=True))), prices[-1])
    average_price = sum(prices, start=D(0)) / len(prices)
    assert summary.average_cost <= to_money(average_price)


def test_summarize_needs_at_least_one_purchase() -> None:
    with pytest.raises(ValueError, match="no purchases"):
        summarize([], D("100"))
```

Listing 01-3, Terminal:

```sh
uv run pytest tests/test_ch01.py
```

```text
E   ModuleNotFoundError: No module named 'invest_witus.methods'
```

Good: red first. Now make it green.

### 01.3 Money helpers

Two rounding rules, one per kind of number. Money rounds to the cent the usual way. Shares round **down**, so the
app never records more shares than the money bought.

Listing 01-4, Filename: `src/invest_witus/money.py`:

```python
"""Money and share amounts as exact decimals, never floats."""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
# This app records shares to six decimal places. Brokers set their own limits for fractional shares.
SHARE_STEP = Decimal("0.000001")


def to_money(value: Decimal) -> Decimal:
    """Round to whole cents, halves away from zero (the rounding most people expect)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_shares(value: Decimal) -> Decimal:
    """Round down to the share step, so a purchase never records more shares than it paid for."""
    return value.quantize(SHARE_STEP, rounding=ROUND_DOWN)
```

Notes:

- The `"""..."""` string on the first line of a module or function is its **docstring**. Editors show it on
  hover, like a JSDoc comment.
- `CENT` and `SHARE_STEP` are module constants. Upper case is a convention, not a keyword; Python has no `const`.
- `quantize` rounds a `Decimal` to the same number of places as its argument.

### 01.4 The methods package

Listing 01-5, Filename: `src/invest_witus/methods/__init__.py`:

```python
"""The investing methods the app can hold you to, one module per method."""
```

The `__init__.py` file is what makes `methods` a package you can import from. It can hold only a docstring.

### 01.5 The plan math

Listing 01-6, Filename: `src/invest_witus/methods/index_dca.py`:

```python
"""Index investing with a fixed monthly contribution (dollar-cost averaging).

The math only: what a fixed amount buys at each price, and where the plan stands at a later price.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.money import to_money, to_shares


@dataclass(frozen=True, slots=True)
class Purchase:
    day: date
    price: Decimal
    amount: Decimal
    shares: Decimal


@dataclass(frozen=True, slots=True)
class Summary:
    purchases: int
    invested: Decimal
    shares: Decimal
    average_cost: Decimal
    value: Decimal
    gain: Decimal


def buy(day: date, amount: Decimal, price: Decimal) -> Purchase:
    """Spend `amount` at `price` and record the shares it buys."""
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")
    return Purchase(day=day, price=price, amount=amount, shares=to_shares(amount / price))


def plan_purchases(amount: Decimal, prices: list[tuple[date, Decimal]]) -> list[Purchase]:
    """Buy the same amount at every (day, price) in the list."""
    return [buy(day, amount, price) for day, price in prices]


def summarize(purchases: list[Purchase], latest_price: Decimal) -> Summary:
    """Total up the purchases and value the shares at `latest_price`."""
    if not purchases:
        raise ValueError("no purchases to summarize")
    invested = sum((p.amount for p in purchases), start=Decimal(0))
    shares = sum((p.shares for p in purchases), start=Decimal(0))
    value = to_money(shares * latest_price)
    return Summary(
        purchases=len(purchases),
        invested=invested,
        shares=shares,
        average_cost=to_money(invested / shares),
        value=value,
        gain=value - invested,
    )
```

Reading it as a TypeScript developer:

| Python | TypeScript |
|---|---|
| `@dataclass(frozen=True, slots=True) class Purchase:` with typed fields | `type Purchase = Readonly<{ day: Date; ... }>`, plus a generated constructor, `==` and a readable print |
| `raise ValueError(f"... {amount}")` | ``throw new RangeError(`... ${amount}`)`` |
| `[buy(day, amount, price) for day, price in prices]` | `prices.map(([day, price]) => buy(day, amount, price))` |
| `sum((p.amount for p in purchases), start=Decimal(0))` | `purchases.reduce((t, p) => t.plus(p.amount), new Decimal(0))` |
| `summarize(..., latest_price=D("100"))` | a named argument; TypeScript has no direct equivalent |

`frozen=True` makes instances read-only; `slots=True` makes them smaller and stops typos like `p.sahres = 3`
from silently creating a new attribute.

### 01.6 Run the checkpoint

Listing 01-7, Terminal:

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

```text
14 passed
All checks passed!
10 files already formatted
0 errors, 0 warnings, 0 informations
```

If `ruff format --check` complains, run `uv run ruff format .` and look at what it changed.

### 01.7 Try it in the REPL

Listing 01-8, Terminal:

```sh
uv run python
```

```text
>>> from datetime import date
>>> from decimal import Decimal as D
>>> from invest_witus.methods.index_dca import plan_purchases, summarize
>>> prices = [(date(2026, 1, 2), D("100")), (date(2026, 2, 2), D("50")), (date(2026, 3, 2), D("100"))]
>>> summarize(plan_purchases(D("100"), prices), D("100"))
Summary(purchases=3, invested=Decimal('300'), shares=Decimal('4.000000'), average_cost=Decimal('75.00'), value=Decimal('400.00'), gain=Decimal('100.00'))
```

Look at the numbers. The average **price** over the three months was 83.33. The average **cost** of your shares
was 75. A fixed amount buys more shares when the price is low and fewer when it is high, so the average cost of
the shares is never above the average of the prices you paid. The last test in `test_ch01.py` checks exactly
that. It is arithmetic, not a promise of profit: if the price keeps falling, the plan keeps losing money.

## Checkpoint

- `uv run pytest` prints `14 passed` (2 from chapter 00, 12 from this chapter).
- ruff and pyright pass.
- Commit: `git add -A && git commit -m "Chapter 01: money and the monthly plan"` and `git push`.

## Exercises

1. Add a test: $100 a month at prices 10, 20 and 40. Work out the shares and average cost by hand first, then
   let pytest check you.
2. In the REPL, run `summarize` on a falling series (100, 80, 60) valued at 60. What sign does `gain` have?
3. Try `Decimal(0.1)` (a float, no quotes) in the REPL and compare it with `Decimal("0.1")`.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v01
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v00...v01
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v01.zip
- Take the reference's files for this chapter without losing your history:
  `git remote add reference https://github.com/dapperAuteur/invest-witus.git` (once), then
  `git fetch reference --tags && git checkout v01 -- src tests`.
- `ModuleNotFoundError: No module named 'invest_witus.methods'`: the folder is missing its `__init__.py`.
- pyright says a type is "partially unknown": a function is missing a parameter or return type.

## What we learned

- Money goes in `Decimal`, built from strings; shares round down, cents round half up.
- A frozen dataclass is a typed, read-only record.
- List comprehensions and generator expressions replace most `map` and `reduce` calls.
- `pytest.mark.parametrize` runs one test over many inputs; `pytest.raises` expects an error.
- With a fixed amount, average cost is at or below average price. That is arithmetic, not a forecast.

## Next

Chapter 02 starts from tag `v01`. It reads a file of daily prices, picks the first trading day of each month, and
gives the app its first command: `uv run invest-witus plan`.

## References

Bogle, J. C. (1997). *The first index mutual fund* [Introduction, signed June 30, 1997]. Bogle Archive, John C.
Bogle Center for Financial Literacy. https://boglecenter.net/wp-content/uploads/JCB_first_index_mf.pdf

Finlay, M., & Zorn, J. (2023). *Cost averaging: Invest now or temporarily hold your cash?* Vanguard research.
https://corporate.vanguard.com/content/dam/corp/research/pdf/cost_averaging_invest_now_or_temporarily_hold_your_cash.pdf

Sharpe, W. F. (1991). The arithmetic of active management. *Financial Analysts Journal, 47*(1), 7-9.
https://web.stanford.edu/~wfsharpe/art/active/active.htm
