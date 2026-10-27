## ⚠️ Ecosystem repo identity (don't confuse these)

This repo, **invest-witus**, is **Invest.WitUS**: a Python (Django) app where a user picks an investing method
taught in Learn.WitUS or ElementaryMBA, runs it on paper first, and the app holds them to the method's rules
with a link from every rule to its lesson. It is also the **reference code for a follow-along Python
tutorial**: one git tag per chapter (`v00`, `v01`, ...), chapter text in `docs/chapters/`.

Don't confuse it with:
- `realestate-witus`: property and real-estate tools. Invest.WitUS may teach about real estate as an asset;
  it does not manage properties.
- `witus-learn`: the LMS. The tutorial course and the investing-methods preview are *lessons there*; this repo
  only holds the code and the chapter source text.
- `centenarian-os`: the personal operating system. Invest.WitUS may send it signed events later; it is not a
  finance module of CentOS.
- ElementaryMBA: the full investing course lives there, not here.

The site **brandanthonymcdonald.com** (BAM's personal portfolio) lives in
`/Users/bam/Code_NOiCloud/ai-builds/claude/bam-landing-page/`, **NOT** `bam-portfolio`.
`/Users/bam/Code_NOiCloud/projects/bam-portfolio/` is the retired legacy site: do not edit, revive or delete it.

Full ecosystem identity and product index: `gemini/witus/CLAUDE.md` and `gemini/witus/lib/products.ts`.
Vetting analysis: `gemini/witus/plans/38-invest-witus-analysis.md` (Test cheaply, 2026-10-27). Research:
`gemini/witus/plans/future/invest-witus-research-2026-10-27/` (local, gitignored).

## The one job

**Help a learner choose a taught investing method and stay with it, on paper first.**

## The load-bearing invariants

1. **Information, not advice.** The app never recommends a security, never shows performance claims or
   testimonials on public pages, and never shows market data on public pages. Example symbols in the tutorial
   are placeholders (`INDEX`), not picks.
2. **Paper by default.** Live trading only behind an explicit checklist and separate keys. Never commit keys.
3. **Other users only for education, with the course,** and only after the legal gate in plans/38 (adviser
   registration question, vendor terms: Massive's individual plans and SnapTrade's free plan forbid serving
   other users; Alpaca accounts are self-directed).
4. **Tutorial tags are immutable.** A fix to a published chapter gets a new tag (`v03.1`) and the chapter page
   says which tag it was written against. Later chapters may add files but must not move or rename files from
   earlier chapters, so `compare/vNN-1...vNN` stays readable.
5. **Every chapter ends green:** its checkpoint test file `tests/test_chNN.py` passes, plus `ruff check`,
   `ruff format --check` and `pyright`.
6. **Personal data stays out of git:** real statements, journals and holdings go in `data/private/`
   (gitignored). The *Quantitative Momentum* book PDF is never copied, quoted at length or committed.
7. **Every method rule links to its lesson.** A rule without a published lesson says "lesson coming"; never
   invent a lesson URL (authoritative-values rule).

## Stack

Python 3.14 via uv · pytest · ruff · pyright. From the Django chapters on: Django 6.1 + django-ninja,
Neon Postgres, Vercel Python runtime with one daily cron (idempotent; Hobby cron has no retries), Alpaca paper
trading, Sign in with WitUS (OIDC), ecosystem footer/legal pages and in-app bug reporting. Framework choice:
`gemini/witus/plans/future/invest-witus-research-2026-10-27/04-python-web-and-api-framework-comparison.md`.

## Commands

`uv sync` · `uv run pytest` · `uv run ruff check --fix . && uv run ruff format .` · `uv run pyright` ·
`uv run invest-witus --help`. Activate the branch guard once per clone: `git config core.hooksPath .githooks`.

## Ecosystem rule pointers

Operator tasks go in `./plans/user-tasks/NN-slug.md`; plans in `./plans/NN-description.md` (gitignored);
branch → commit → push, BAM merges, bundle before handoff; APA 7 for curriculum text (the chapters are
curriculum); never assert guessed external values. Full text in the shared-rules block below and in
`gemini/witus/CLAUDE.md`.

---
