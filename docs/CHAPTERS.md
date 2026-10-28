# Chapters

One chapter = one tag = one Learn.WitUS lesson. Each chapter's checkpoint test is `tests/test_chNN.py`.
Tags are fixed points: a fix to a published chapter gets a new tag (`vNN.1`), never a moved tag.

| Chapter | Tag | Text | What the checkpoint tests | Learn.WitUS lesson |
|---|---|---|---|---|
| 00 Set up your machine and your repository | `v00` | [00](chapters/00-set-up-your-machine.md) | Python 3.14+, the package imports | lesson coming |
| 01 Money in Python, and the math of a monthly plan | `v01` | [01](chapters/01-money-and-the-monthly-plan.md) | Decimal money, buying at each price, the plan summary, average cost at or below average price | lesson coming |
| 02 Read a price history and give the app its first command | `v02` | [02](chapters/02-prices-and-the-plan-command.md) | CSV loading and its errors, first trading day of each month, the `plan` command | lesson coming |
| 03 Write the method down, and review yourself against it | `v03` | [03](chapters/03-rules-plan-journal-review.md) | rules file matches the checks, plan and journal loading, months due, each rule flagged, the `review` command | lesson coming |
| 04 The first Django page: the public landing page | `v04` | [04](chapters/04-the-first-django-page.md) | home 200 with the positioning line, the exact "Sign in" link on every page (smoke), waitlist idempotency, honeypot and CSRF, every internal footer link 200, FAQ anchor and bare-URL links, privacy and terms headings, no table or signed percentage on any public page | lesson coming |
| 05 Models and the admin: accounts, statements and the owner's back office | `v05` | [05](chapters/05-models-and-the-admin.md) | the admin sends a stranger to the login page, the waitlist status and approve action, Decimal round trip and rounding, the float guard, symbol normalization and the unique constraints, the change between two statements in the library and through the models, a statement entered through the admin form, the statements page and its chosen pair, models and migrations agree | lesson coming |
