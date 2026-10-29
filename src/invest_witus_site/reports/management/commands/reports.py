"""`manage.py reports`: print the open reports, so a coding session in this repo can read them
(PRD 7.8). `--send` first sends every row WitUS Inbox has not taken, the nightly job's step, by
hand."""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from invest_witus_site.reports.delivery import send_unsent
from invest_witus_site.reports.models import InboxStatus, Report


class Command(BaseCommand):
    help = "List reports not marked done; with --send, send unsent rows to WitUS Inbox first."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--send", action="store_true", help="Send unsent reports and waitlist copies first."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["send"]:
            run = send_unsent()
            self.stdout.write(
                f"Inbox: checked {run.checked}, sent {run.sent}, failed {run.failed}."
                + (f" Stopped: {run.stopped}" if run.stopped else "")
            )
            for error in run.errors:
                self.stderr.write(error)
        open_reports = Report.objects.exclude(triage=Report.Triage.DONE).order_by("created_at")
        if not open_reports:
            self.stdout.write("No open reports.")
            return
        for row in open_reports:
            sent = "sent" if row.sent_at else f"not sent ({InboxStatus(row.inbox_status).label})"
            self.stdout.write(
                f"#{row.pk} {row.created_at:%Y-%m-%d %H:%M} {row.kind} {row.triage}, "
                f"Inbox {sent}, page {row.page or '-'}"
            )
            self.stdout.write(f"    {' '.join(row.message.split())}")
