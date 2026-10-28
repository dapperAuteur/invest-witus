# Invest.WitUS

A Python app for learning to invest by following one method at a time. You pick a method taught in
Learn.WitUS or ElementaryMBA, run it on paper first, and the app holds you to the method's rules, with a link
from every rule back to the lesson that teaches it.

This repository is two things at once:

1. **The reference app**, built the way the other WitUS ecosystem tools are built.
2. **The finished code for a follow-along tutorial.** Each tutorial chapter ends at a git tag (`v00`, `v01`,
   ...). The chapter text lives in [`docs/chapters/`](docs/chapters/) and the table of chapters in
   [`docs/CHAPTERS.md`](docs/CHAPTERS.md). Learners build their own copy in their own repository and use the
   tags here to check their work.

Information, not advice. Invest.WitUS is a learning tool. It does not recommend securities and is not open to
other users yet.

## Quick start

```sh
uv sync            # install Python 3.14 and the tools from uv.lock
uv run pytest      # run every chapter's checkpoint tests
uv run invest-witus --help

cp .env.example .env                                   # names only; DJANGO_DEBUG=1 for your laptop
uv run python manage.py migrate                        # SQLite under data/private/ (gitignored)
uv run --env-file .env python manage.py createsuperuser  # the owner's admin login (chapter 05)
uv run --env-file .env python manage.py runserver      # the public site at http://127.0.0.1:8000/, the admin at /admin/
```

## Credits

The project began from freeCodeCamp's course "Python Algorithmic Trading with SnapTrade, Massive, Alpaca"
(Carnes, 2026), which builds a momentum app in Django and invites learners to extend it. Invest.WitUS keeps
the idea (a rules-based method, run on a paper account) and builds its own stack and code.

## References

Carnes, B. (2026, September 29). *Python algorithmic trading with SnapTrade, Massive, Alpaca* [Video course
announcement]. freeCodeCamp. https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/
