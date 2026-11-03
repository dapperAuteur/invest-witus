"""`manage.py sync_paper_orders`: read every open paper order back from Alpaca and fix the rows
and their journal entries. The nightly cron runs the same function after the price pull. Since
decision 159 each account's orders are read with its own key slot's client."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from invest_witus_site.paper import slots
from invest_witus_site.paper.alpaca import AlpacaError
from invest_witus_site.paper.orders import sync_every_account


class Command(BaseCommand):
    help = "Update open Alpaca paper orders to filled or cancelled, and their journal entries."

    def handle(self, *args: Any, **options: Any) -> None:
        if not slots.any_configured():
            self.stdout.write("Alpaca paper keys are not set; nothing to sync.")
            return
        try:
            result = sync_every_account()
        except AlpacaError as error:
            raise CommandError(error.message) from None
        self.stdout.write(
            f"Checked {result.checked}, changed {result.changed}: {result.filled} filled, "
            f"{result.ended_part_filled} ended part filled, {result.ended_unfilled} ended "
            f"unfilled, {result.still_open} still open."
        )
        for client_order_id, message in result.failed.items():
            self.stderr.write(f"Failed {client_order_id}: {message}")
