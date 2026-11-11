"""`manage.py refresh_filings SYMBOL [SYMBOL ...]` or `manage.py refresh_filings --watched`:
the SEC refresh by hand (chapter 16), the same code the button and the nightly step run.

Each request waits its turn in the shared throttle and carries the app's User-Agent, which the
command prints, so a refusal can be checked against what was sent.
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from invest_witus import filings as lib
from invest_witus_site.filings import refresh, sec


class Command(BaseCommand):
    help = "Fetch the recent filings and key figures of one or more symbols from SEC EDGAR."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "symbols", nargs="*", help="Symbols such as CORPX (upper or lower case)."
        )
        parser.add_argument(
            "--watched", action="store_true", help="Every watched symbol that is due, as the cron."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.SEC_FILINGS_ENABLED:
            raise CommandError("Filings are off on this copy of the app (SEC_FILINGS=off).")
        self.stdout.write(f"User-Agent: {settings.SEC_USER_AGENT}")
        if options["watched"]:
            run = refresh.refresh_watched()
            self.stdout.write(f"Refreshed: {', '.join(run.refreshed) or 'none'}.")
            if run.funds:
                self.stdout.write(f"Funds, no company filings: {', '.join(run.funds)}.")
            if run.not_listed:
                self.stdout.write(f"Not listed with the SEC: {', '.join(run.not_listed)}.")
            for symbol, problem in run.failed.items():
                self.stderr.write(f"Failed {symbol}: {problem}")
            if run.skipped:
                self.stderr.write(f"Skipped ({run.stopped}): {', '.join(run.skipped)}")
            return
        if not options["symbols"]:
            raise CommandError("Name at least one symbol, or pass --watched.")
        failed = False
        for symbol in options["symbols"]:
            try:
                done = refresh.refresh_symbol(symbol)
            except (sec.SecError, lib.FilingsDataError) as error:
                self.stderr.write(f"Failed {symbol.upper()}: {error}")
                failed = True
                if isinstance(error, sec.SecError) and error.retry_later:
                    break
                continue
            note = f" ({done.note})" if done.note else ""
            self.stdout.write(
                f"{done.symbol}: {done.kind}, {done.filings} filing(s), "
                f"{done.facts} figure(s){note}."
            )
        if failed:
            raise CommandError("Some symbols failed; see above.")
