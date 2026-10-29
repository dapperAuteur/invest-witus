"""`manage.py pull_prices [--since YYYY-MM-DD] [--symbols A,B]`: the nightly pull, by hand.

The same code the cron route runs, for a laptop (against the CSV folder) and for the owner's
shell (against Tiingo, with the key in the environment). Running it twice writes nothing twice.
"""

from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from invest_witus_site.prices.pull import DAYS_BACK, pull, symbol_universe
from invest_witus_site.prices.sources import source_from_settings


def parse_symbols(text: str) -> list[str]:
    """`"index, other"` becomes `["INDEX", "OTHER"]`, each once, in the order given."""
    return list(dict.fromkeys(part.strip().upper() for part in text.split(",") if part.strip()))


class Command(BaseCommand):
    help = (
        "Store end-of-day closes for every held or watched symbol, or for --symbols, since a date."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--since",
            type=date.fromisoformat,
            help=f"First day to ask for, YYYY-MM-DD. Default: {DAYS_BACK} days ago.",
        )
        parser.add_argument(
            "--symbols",
            help="Comma-separated symbols instead of every held symbol, such as INDEX,OTHER.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        today = timezone.localdate()
        since: date = options["since"] or today - timedelta(days=DAYS_BACK)
        if since > today:
            raise CommandError(f"--since {since} is after today ({today})")
        symbols = parse_symbols(options["symbols"]) if options["symbols"] else symbol_universe()
        if not symbols:
            self.stdout.write("Nothing to pull: no account holds or watches a symbol yet.")
            return
        result = pull(source_from_settings(), symbols, since, today)
        self.stdout.write(
            f"Source {result.source}, {result.since} to {result.until}, "
            f"{len(result.symbols)} symbol(s), {result.requests} request(s)."
        )
        self.stdout.write(f"{result.counts}.".capitalize())
        for symbol, problem in result.failed.items():
            self.stderr.write(f"Failed {symbol}: {problem}")
        if result.skipped:
            self.stderr.write(f"Skipped, for the next run: {', '.join(result.skipped)}")
