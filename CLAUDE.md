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

Python 3.14 via uv · pytest · ruff · pyright. From chapter 04 on: Django 5.2 LTS (decision 33) + django-ninja,
Neon Postgres, Vercel Python runtime with one daily cron (idempotent; Hobby cron has no retries), Alpaca paper
trading, Sign in with WitUS (OIDC), ecosystem footer/legal pages and in-app bug reporting. Framework choice:
`gemini/witus/plans/future/invest-witus-research-2026-10-27/04-python-web-and-api-framework-comparison.md`.

## Commands

`uv sync` · `uv run pytest` · `uv run ruff check --fix . && uv run ruff format .` · `uv run pyright` ·
`uv run invest-witus --help` · `uv run python manage.py migrate` · `uv run --env-file .env python manage.py createsuperuser` (the owner's `/admin/` login) · `uv run --env-file .env python manage.py runserver`
(copy `.env.example` to `.env` first) · `uv run python scripts/render_chapter.py --check docs/chapters/templates/*.md`
(chapter listings are generated from the real files; never edit a rendered chapter by hand). Activate the branch guard
once per clone: `git config core.hooksPath .githooks`.

## Ecosystem rule pointers

Operator tasks go in `./plans/user-tasks/NN-slug.md`; plans in `./plans/NN-description.md` (gitignored);
branch → commit → push, BAM merges, bundle before handoff; APA 7 for curriculum text (the chapters are
curriculum); never assert guessed external values. Full text in the shared-rules block below and in
`gemini/witus/CLAUDE.md`.

---

---

<!-- BEGIN:witus-shared-rules v8 -->
<!-- MANAGED BLOCK — do not edit by hand. Source: gemini/witus/docs/shared-rules.md.
     Update the source, then run `node scripts/sync-claude-rules.mjs` in the witus repo. -->

## ⚠️ Ecosystem identity (shared note — don't confuse repos)

Full ecosystem identity + the canonical product index live in `gemini/witus/CLAUDE.md` and
`gemini/witus/lib/products.ts`. Each repo states *which* product it is in its own hand-owned line
above this managed block; don't infer another app's URLs, routes, IDs, env names, or DB schema —
confirm against that app's own code.

The site **brandanthonymcdonald.com** (BAM's personal portfolio) lives in `claude/bam-landing-page/`
— **NOT** `projects/bam-portfolio/` (the retired legacy static site). Target `bam-landing-page`.

## Operator-task rule — capture user actions in `./plans/user-tasks/`

When Claude proposes work that needs BAM to do something outside the editor (account signup, API
key, DNS change, vendor dashboard, env-var rotation, secret generation, PR review/merge, etc.),
Claude MUST create a `./plans/user-tasks/NN-slug.md` file in this repo. **No exceptions for "small"
steps.** Required sections: **Scope tag** · **What + why** (with explicit *what this blocks* detail
and any hard deadline) · **Steps** · **What Claude will use** · **How to mark done** · **Related**.
Keep `./plans/user-tasks/00-descriptions.md` updated with columns `# | Title | Scope | Blocks |
Status` — the `Blocks` column is the one BAM scans. Ecosystem-wide tasks (Keap, IRL events, retros,
cross-product decisions) live in the canonical witus queue at `gemini/witus/plans/user-tasks/`;
repo-local tasks live here. Read the witus queue at session start before dependent work. Full rule:
`gemini/witus/CLAUDE.md` §"Operator-task rule".

## Branch hygiene — BAM merges, between sessions by default

**Half 1.** Branch → commit → push → stop. Claude does not run `git checkout main && git merge`.
Never `--force` to shared branches. Before every commit run `git branch --show-current`; if it is
`main`/`master`, branch first (`feat/ fix/ chore/ docs/`). After push, hand back the branch name +
summary and stop.

**Half 2.** BAM merges pushed branches via the GitHub UI between sessions. Mid-session, after a
push, BAM may merge in a separate window and the local checkout silently fast-forwards to `main` —
so re-check `git branch --show-current` before **every** commit, not just at branch creation, or you
risk landing follow-up commits directly on `main`.

**Half 3.** Keep branches small (one concern each). When a session produces multiple branches,
consolidate them into one `bundle/<slug>-YYYY-MM-DD` via `git merge --no-ff` (preserves per-concern
history — no squash), resolve conflicts during bundling, run `tsc + lint + build` against the
bundle, push, and file ONE `./plans/user-tasks/NN-merge-bundle-<slug>.md`. BAM does one merge, not N.

**Commit often.** Commit at every working checkpoint — a passing build, a finished sub-step, a green
test — not just at the end. A usage-limit cutoff, a dropped connection, or a crashed session must
never lose more than the last few minutes of work. Small frequent commits on the feature branch keep
the branch un-merged (Half 1 still holds) and give BAM clean per-step history to drill into.

A checked-in `.githooks/pre-commit` guard refuses commits made directly on `main`/`master`. Activate
once per clone: `git config core.hooksPath .githooks`. Full rule: `gemini/witus/CLAUDE.md`
§"Branch-hygiene rule".

## Docs-sync rule — a change isn't done until its docs are current

When a change adds, alters, or removes a user-visible feature/route/scope, update the affected docs
**in the same branch**: README (feature list, env examples, scripts), in-app help/tutorial content,
`ROADMAP.md` **and** any public roadmap page, API/OpenAPI docs, and STYLE_GUIDE/CONTRIBUTING when a
convention changed. State which docs you touched in the handoff. Never leave an aspirational ✅ on a
roadmap — downgrade it with a one-line reason. If a doc update is genuinely out of scope, file it as
a `./plans/` task rather than skipping silently. A Stop hook in `.claude/settings.json` gates on
this: if the session diff changed feature/route files but touched no docs, it blocks once and asks
you to update-or-defer. Schema-only migrations, refactors, perf, and dev-tooling changes don't
trigger it.

## Plans convention

All implementation plans live in `./plans/` as `NN-description-of-plan.md` (two-digit prefix,
kebab-case, next available number, don't skip). Sub-queues: `./plans/user-tasks/NN-slug.md`
(operator tasks), `./plans/bugs/`, `./plans/future/`. (`plans/` is typically gitignored.)

**Finding what BAM mentions: search gitignored files.** Most ideas, plans, decisions, and drafts BAM
refers to live in a `plans/` dir of this repo or another ecosystem repo, and are not tracked by git.
Default `rg`, `git grep`, `git log -S`, and editor search skip gitignored paths, so they miss every
`plans/` dir and report a false "nothing found". Search with `rg -uu` (or `rg --no-ignore`, `grep -r`,
`find`), excluding `node_modules`, `.next`, `.git`, worktrees, and virtualenvs: this repo first, then
the repos in `gemini/witus/docs/ecosystem-repos.json`. A miss from a git-aware search proves nothing;
if the gitignore-aware search also misses, say what you searched and ask BAM where it lives.
Untracked also means unrecoverable: git can't restore an overwritten plan, so read before replacing.
Full rule: `gemini/witus/CLAUDE.md` §"Plans convention".

## New app ideas — vet before building

Before writing code, creating a repo, or onboarding any new product idea, score it with the WitUS
app-idea rubric (`gemini/witus/docs/app-idea-vetting-rubric.md`): search gitignored `plans/` for prior
work, declare the goal with BAM (business / portfolio / community), write the sourced analysis at
`gemini/witus/plans/NN-<slug>-analysis.md`, apply the gates and weighted scores, and file a user task
for any validation BAM does outside the editor. Append lessons and outcomes to the rubric's logs;
gate, weight, and threshold changes need BAM's approval. Full rule: `gemini/witus/CLAUDE.md`
§"New-product vetting rule".

## Citation rule

Anything publishable, teachable, or partner-facing (curriculum, teaching-oriented help articles,
white papers, grant/sponsor/partner writing) uses APA 7 in-line citations with a `## References`
section. Code docs, internal notes, and `plans/user-tasks/*` are out of scope. Full rule:
`gemini/witus/CLAUDE.md` §"Citation rule".

## Spelling rule — American English, always

Everything written in this ecosystem uses **American English spelling**: product copy, course and lesson
text, quiz items, docs, plans, commit messages, and agent output ("fiber" not "fibre", "color", "gray",
"center", "catalog", "organize", "program", "license" as the noun). Never change spelling inside a
quotation or the title of a cited work: a source is quoted as printed. When converting existing text,
skip quotations, blockquotes, bibliography entries and code, and prove the quoted passages are unchanged.
BAM's decision of 2026-10-08.

## Blog ledger rule — every blog post goes in the ledger the session it is written

BAM's blog (brandanthonymcdonald.com/blog, repo `claude/bam-landing-page`) has one ledger of every
post, live and waiting, numbered in publishing order: `gemini/witus/plans/playbook/*-blog-ledger.md`
(gitignored; synced to `witus.online/admin/library`). Read it before writing a post, so a topic is
not written twice. When a session in **any** repo drafts a blog post, add it to the ledger's Part 2
in the same session (slug, title, app, branch, publish task, gate, check result), placed after any
post it links to; then rename the file to today's date, update its row in `00-library-index.md`, and
re-render its PDF (`npm run library:pdf -- <file>` in witus). "Published" means listed in
`https://www.brandanthonymcdonald.com/feed.json`, not merged. Publishing order is BAM's call. Full
rule: `gemini/witus/CLAUDE.md` §"Blog ledger rule".

## Authoritative-values rule — never assert guessed external values

When a value is owned by an external system (DNS/registrar, a host like Vercel, a third-party API,
or another ecosystem app's URLs/routes/IDs/env/schema), read it from the authoritative source; don't
hardcode a guessed default and present it as correct. If you must ship a fallback, label it as a
fallback in both UI copy and a code comment. Verify by behavior (does the flow work?), not by
exact-match against a guess. When unsure, flag or ask — never assert. Full rule:
`gemini/witus/CLAUDE.md` §"Authoritative-values rule".

## Preview-branch cleanup rule — no preview deployment may leave a paid resource behind

Every repo deployed on Vercel with a Neon database through the Vercel-managed integration gets a Neon branch named `preview/<git-branch>` per preview deployment. Neon deletes that branch only when the Vercel **deployment** is deleted, and Vercel keeps preview deployments for six months by default (a project with fewer than about 20 preview deployments may never delete any). Stale branches count toward the plan's branch limit and are billed as extra usage. BAM was charged over $100 in each of two months this way (2026-10-15).

**Required in every Neon repo:**
1. The workflow `.github/workflows/neon-preview-cleanup.yml` (canonical copy in `gemini/witus/.github/templates/`, synced by `node scripts/sync-preview-cleanup-workflow.mjs --write`): on `pull_request` `closed`, run `neondatabase/delete-branch-action@v3` against `preview/${{ github.head_ref }}` with `vars.NEON_PROJECT_ID` and `secrets.NEON_API_KEY`. Do not edit the synced copy; edit the template and re-sync.
2. The GitHub repository variable `NEON_PROJECT_ID` and secret `NEON_API_KEY` set (operator task; the workflow fails loudly without them). **The key is project-scoped and unique to that project** (Neon Console → Organization settings → API keys → Create new → Project-scoped; or `neon api-keys create --name <name> --project-id <id>`), so a leak reaches one database. A project-scoped key still has Editor access to every branch in its project: the `preview/` name filter in code is the real guard, and the key never reaches client-side code. The hub (witus.online) holds the map of all project keys as `NEON_PROJECT_KEYS` for its `/admin/cost-cleanup` page; `scripts/neon-key-plan.ts` prints or mints them.
3. The Vercel project's **Deployment Retention Policy → Pre-Production Deployments** set to the shortest duration (dashboard, per project).
4. A branch created by hand for a preview or an experiment carries `expires_at` (Neon branch expiration, 30 days maximum); never create one without it.

**Supabase repos** (CentenarianOS, Work.WitUS, Tour Manager OS, one shared project): no persistent branches; preview branches only through the GitHub integration, which deletes them when the PR closes. **MongoDB Atlas repos** (FlashLearnAI, bam-landing-page): the integration creates no per-preview resources; cost is the cluster tier, nothing to clean.

**Claude's part:** when a session adds a Neon database to a repo, it adds the workflow in the same change and files the variable/secret step as an operator task. When a session sees preview branches older than the PR that made them (`npx neonctl branches list --project-id <id>`), it lists them for BAM instead of assuming the integration cleaned up. Source for the Neon behavior: https://neon.com/docs/guides/vercel-branch-cleanup (read 2026-10-15).

## Email rule — Mailgun is the ecosystem mailer, never Resend

Every app that sends email uses **Mailgun** (env `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`; witus-inbox is the
reference). Never add Resend as a dependency, and never name it in a PRD, brief, README, CLAUDE.md or cloud
prompt. When a doc in front of you says Resend, fix it in the same change. Two apps still send through Resend
(flashlearn-ai and centenarian-os, 2026-10-23): move them to Mailgun the next time a session touches their email
code. **Why:** Create.WitUS's PRD, CLAUDE.md and README kept specifying Resend after Mailgun was chosen, so the
wrong mailer resurfaced in later sessions (BAM, 2026-10-23: "ensure we don't have this error again").

## Coding conventions

UI/UX/DX conventions (a11y, component patterns, TypeScript, microcopy, git-commit vocabulary, the
default Neon+Drizzle+pnpm+Vitest stack) are consolidated in `gemini/witus/docs/shared-ui-ux-dx.md`.
Read it before writing UI or API code. Two repos are grandfathered on Supabase+Jest and documented
there as exceptions.

<!-- END:witus-shared-rules v8 -->
