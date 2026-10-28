from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invest_witus.adherence.journal import Action, Entry, JournalFileError, load_journal
from invest_witus.adherence.plan import Plan, PlanFileError, load_plan
from invest_witus.adherence.review import CHECKED_RULES, months_due, review
from invest_witus.cli import main
from invest_witus.methods.rulebook import LESSON_COMING, UnknownMethodError, load_method

SAMPLES = Path(__file__).parent.parent / "data" / "sample"
D = Decimal

PLAN = Plan(
    method="index-dca",
    start=date(2026, 1, 1),
    amount=D("100.00"),
    symbols=frozenset({"INDEX"}),
    buy_window_days=7,
)


def buy(day: date, amount: str = "100.00", symbol: str = "INDEX") -> Entry:
    return Entry(day=day, action=Action.BUY, symbol=symbol, amount=D(amount))


def rule_ids(entries: list[Entry], through: date) -> list[str]:
    return [f.rule_id for f in review(load_method("index-dca"), PLAN, entries, through)]


def test_the_rules_file_and_the_code_check_the_same_rules() -> None:
    method = load_method("index-dca")
    assert {rule.id for rule in method.rules} == CHECKED_RULES


def test_a_rule_without_a_lesson_says_lesson_coming() -> None:
    assert load_method("index-dca").lesson_for("no-selling") == LESSON_COMING


def test_an_unknown_method_is_an_error() -> None:
    with pytest.raises(UnknownMethodError):
        load_method("get-rich-quick")


def test_the_sample_plan_loads() -> None:
    plan = load_plan(SAMPLES / "plan.toml")
    assert plan.start == date(2025, 10, 1)
    assert plan.amount == D("100.00")
    assert plan.symbols == {"INDEX"}


@pytest.mark.parametrize(
    "toml, problem",
    [
        ('method = "index-dca"\n', "missing setting"),
        (
            'method = "index-dca"\nstart = "2026-01-01"\namount = "100"\n'
            'symbols = ["INDEX"]\nbuy_window_days = 7\n',
            "start must be a date",
        ),
        (
            'method = "index-dca"\nstart = 2026-01-01\namount = "100"\n'
            'symbols = ["INDEX"]\nbuy_window_days = 40\n',
            "between 1 and 28",
        ),
    ],
)
def test_bad_plans_say_what_is_wrong(tmp_path: Path, toml: str, problem: str) -> None:
    path = tmp_path / "plan.toml"
    path.write_text(toml, encoding="utf-8")
    with pytest.raises(PlanFileError, match=problem):
        load_plan(path)


def test_the_journal_reads_actions_and_tidies_symbols(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    path.write_text("date,action,symbol,amount\n2026-01-02,BUY,index,100\n", encoding="utf-8")
    assert load_journal(path) == [buy(date(2026, 1, 2), "100")]


def test_an_unknown_action_names_the_line(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    path.write_text("date,action,symbol,amount\n2026-01-02,hold,INDEX,100\n", encoding="utf-8")
    with pytest.raises(JournalFileError) as info:
        load_journal(path)
    assert info.value.line == 2


def test_the_current_month_is_not_due_until_its_window_closes() -> None:
    assert months_due(PLAN, date(2026, 3, 6)) == [(2026, 1), (2026, 2)]
    assert months_due(PLAN, date(2026, 3, 7)) == [(2026, 1), (2026, 2), (2026, 3)]


def test_months_due_crosses_the_new_year() -> None:
    plan = Plan("index-dca", date(2025, 11, 1), D("100"), frozenset({"INDEX"}), 7)
    assert months_due(plan, date(2026, 1, 31)) == [(2025, 11), (2025, 12), (2026, 1)]


def test_a_plan_followed_exactly_has_no_findings() -> None:
    entries = [buy(date(2026, 1, 2)), buy(date(2026, 2, 2)), buy(date(2026, 3, 2))]
    assert rule_ids(entries, through=date(2026, 3, 31)) == []


@pytest.mark.parametrize(
    "entries, expected",
    [
        ([buy(date(2026, 1, 2))], ["one-buy-each-month"]),  # February is missing
        ([buy(date(2026, 1, 2)), buy(date(2026, 2, 12))], ["buy-in-window"]),
        ([buy(date(2026, 1, 2)), buy(date(2026, 2, 2), "150.00")], ["fixed-amount"]),
        ([buy(date(2026, 1, 2)), buy(date(2026, 2, 2), symbol="OTHER")], ["plan-symbols-only"]),
        (
            [buy(date(2026, 1, 2)), buy(date(2026, 1, 5)), buy(date(2026, 2, 2))],
            ["one-buy-each-month"],
        ),
        (
            [
                buy(date(2026, 1, 2)),
                Entry(date(2026, 1, 20), Action.SELL, "INDEX", D("50")),
                buy(date(2026, 2, 2)),
            ],
            ["no-selling"],
        ),
    ],
)
def test_each_rule_is_flagged(entries: list[Entry], expected: list[str]) -> None:
    assert rule_ids(entries, through=date(2026, 2, 28)) == expected


def test_trades_before_the_plan_started_are_ignored() -> None:
    entries = [Entry(date(2025, 12, 15), Action.SELL, "INDEX", D("50")), buy(date(2026, 1, 2))]
    assert rule_ids(entries, through=date(2026, 1, 31)) == []


def test_review_command_on_the_samples(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "review",
            "--plan",
            str(SAMPLES / "plan.toml"),
            "--journal",
            str(SAMPLES / "journal.csv"),
            "--through",
            "2026-09-30",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "5 thing(s) to look at" in out
    assert "No buy in 2026-03." in out
    assert "Lesson: lesson coming" in out


def test_review_command_reports_a_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["review", "--plan", "nope.toml", "--journal", "nope.csv"]) == 1
    assert "error:" in capsys.readouterr().err
