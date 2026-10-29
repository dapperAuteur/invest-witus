"""`manage.py send_outbox`: send every post draft WitUS Outbox has not taken, the nightly job's
step, by hand. With Outbox off it says why and sends nothing."""

from typing import Any

from django.core.management.base import BaseCommand

from invest_witus_site.outbox.delivery import send_unsent


class Command(BaseCommand):
    help = "Send unsent post drafts to WitUS Outbox (the nightly retry, by hand)."

    def handle(self, *args: Any, **options: Any) -> None:
        run = send_unsent()
        self.stdout.write(
            f"Outbox: checked {run.checked}, sent {run.sent}, failed {run.failed}."
            + (f" Stopped: {run.stopped}" if run.stopped else "")
        )
        for error in run.errors:
            self.stderr.write(error)
