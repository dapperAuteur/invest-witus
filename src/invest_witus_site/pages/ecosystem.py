"""The WitUS ecosystem's product list, for the footer.

Copied as data from `gemini/witus/lib/products.ts`, the canonical registry, on 2026-10-27: every
product whose `surfaces` includes "public-directory", except this app. Nothing here is invented;
when the registry changes, this list changes with it (the authoritative-values rule).
"""

from dataclasses import dataclass
from typing import Literal

Status = Literal["live", "beta", "coming-soon", "infrastructure"]


@dataclass(frozen=True, slots=True)
class Product:
    name: str
    href: str
    status: Status


SIBLINGS: tuple[Product, ...] = (
    Product("WitUS", "https://witus.online", "infrastructure"),
    Product("WitUS Inbox", "https://inbox.witus.online", "infrastructure"),
    Product("WitUS Outbox", "https://outbox.witus.online", "infrastructure"),
    Product("CentenarianOS", "https://centenarianos.com", "live"),
    Product("Work.WitUS", "https://work.witus.online", "live"),
    Product("Tour Manager OS", "https://tour.witus.online", "beta"),
    Product("Wanderlust", "https://wanderlust.witus.online", "beta"),
    Product("Fly.WitUS", "https://fly.witus.online", "beta"),
    Product("FlashLearnAI", "https://flashlearnai.witus.online", "beta"),
    Product("Learn.WitUS", "https://learn.witus.online", "live"),
    Product("AwesomeWebStore", "https://awesomewebstore.com", "live"),
    Product("Triage.Agent.WitUS", "https://triage.agent.witus.online", "beta"),
    Product("Stream.WitUS", "https://stream.witus.online", "beta"),
    Product("Centenarian Coach", "https://centenarian.coach.multiagent.witus.online", "beta"),
    Product("Shop.WitUS", "https://shop.witus.online", "infrastructure"),
    Product("Stay.WitUS", "https://stay.witus.online", "beta"),
    Product("RealEstate.WitUS", "https://realestate.witus.online", "coming-soon"),
    Product("Create.WitUS", "https://create.witus.online", "coming-soon"),
    Product("VO GOAT", "https://vogoat.witus.online", "coming-soon"),
    Product("RideWitUS", "https://ride.witus.online", "beta"),
    Product(
        "Wanderlearn Field Reporter",
        "https://wanderlearn.field.reporter.witus.online",
        "infrastructure",
    ),
)


def products() -> list[Product]:
    """The products people use, in registry order (witus.online's footer splits them this way)."""
    return [p for p in SIBLINGS if p.status != "infrastructure"]


def infrastructure() -> list[Product]:
    """The shared services behind the products."""
    return [p for p in SIBLINGS if p.status == "infrastructure"]
