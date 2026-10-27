> Copied 2026-10-27 from the WitUS ecosystem's local planning notes, `gemini/witus/plans/future/invest-witus-research-2026-10-27/02-tutorial-and-python-dx.md` (researched and written 2026-10-27). Paths to `plans/` files refer to those local notes and are not in this repo.

# Invest.WitUS: follow-along tutorial structure and Python developer experience

Researched: October 27, 2026

Scope: two linked questions from the seed note (`plans/future/python-investing-app-seed-2026-10-27.md`). First, how the best follow-along tutorials and their repositories are built, so that a learner who already knows TypeScript, Next.js, React and Postgres can build a Django investing app chapter by chapter in a repository of his own while the reference implementation (`invest-witus`) lives in a separate repository. Second, what the Python toolchain looks like in October 2026, from each tool's own documentation. Every fact below was read on October 27, 2026 from the page named in the References section. Tags: **V** means fetched and read on that page; **I** means inferred from fetched facts. "Not stated" means the page read did not say.

Conventions: no version, date or feature below is asserted beyond what a fetched page says. Where a page shows a date the row carries it; where the page shows none the row says "not stated" and the References entry uses n.d.

---

## Part A: how the best follow-along tutorials are built

### A1. Django, "Writing your first Django app" (official tutorial, Django 6.1)

- **Edition read:** Django 6.1 documentation. The page states "This tutorial is written for Django 6.1, which supports Python 3.12 and later." (V)
- **What it builds:** a poll application with "A public site that lets people view polls and vote in them" and "An admin site that lets you add, change, and delete polls." (V)
- **Chapter count and sequence (eight parts, V):**
  1. Part 1: creating a project, the development server, creating the polls app, "Write your first view".
  2. Part 2: "We'll set up the database, create your first model, and get a quick introduction to Django's automatically-generated admin site."
  3. Part 3: views and templates (the public interface), `render()`, `get_object_or_404()`, removing hardcoded URLs, namespacing URL names.
  4. Part 4: "form processing and cutting down our code" (minimal form, generic views).
  5. Part 5: automated testing (details below).
  6. Part 6: "add a stylesheet and an image" (static files).
  7. Part 7: customizing the admin site.
  8. Part 8: third-party packages (Django Debug Toolbar), "Getting help from others", "What's next?".
  Then "Advanced tutorial: How to write reusable apps" and "Writing your first contribution for Django". (V)
- **What part 1 does before any app code (V):** `python -m django --version` as a version check; `django-admin startproject mysite djangotutorial` (which creates `manage.py` and `mysite/` with `settings.py`, `urls.py`, `asgi.py`, `wsgi.py`); `python manage.py runserver` with a visible "Congratulations!" page as the checkpoint; `python manage.py startapp polls`. The page warns that the dev server is not for production, tells the reader to ignore the unapplied-migrations warning for now, and warns not to name a project `test`.
- **Chapter layout (V):** each part opens with "This tutorial begins where Tutorial N left off" and a one-sentence goal, then numbered sections of steps with code shown per file, then a short handoff to the next part. A "Where to get help" box points at the FAQ's Getting Help section; part 1 adds a "Page not found?" callout telling the reader to check they went to `/polls/` not `/`.
- **Keeping the learner in sync with a reference:** no reference code repository is mentioned on any part read (V). Sync is by full file listings in the text (V).
- **How exercises are checked (part 5, V):** tests live in `polls/tests.py` ("the testing system will automatically find tests in any file whose name begins with `test`"); run with `python manage.py test polls`. The part is structured as identify a bug, write a test that exposes it, run tests, fix the bug, then test a view with the Django test client. Quoted rules of thumb: "a separate `TestClass` for each model or view", "a separate test method for each set of conditions you want to test", "test method names that describe their function". The page also says "in testing redundancy is a *good* thing" and quotes "Code without tests is broken by design."
- **Takeaway for Invest.WitUS (I):** the official tutorial introduces tests only in part 5 of 8; Invest.WitUS should bring the test runner forward to chapter 1 so every later chapter has a checkpoint test.

### A2. Django Girls Tutorial

- **What it builds:** "a small working web application: your own blog", and it teaches putting it online. (V)
- **Chapter list (24 entries, V):** Introduction; Installation (subsections: Chromebook, macOS/Windows/Linux, Command Line, Python, Code Editor, Virtual Environment, Django, Git, GitHub, PythonAnywhere); How the Internet works; Introduction to command line; Python installation; Code editor; Introduction to Python; What is Django?; Django installation; Your first Django project!; Django models; Django admin; Deploy!; Django URLs; Django views; Introduction to HTML; Django ORM (Querysets); Dynamic data in templates; Django templates; CSS; Template extending; Extend your application; Django Forms; What's next? (Two chapter titles contain a dash in the original and are shortened here.)
- **Before any framework (V):** six chapters come before the first Django chapter: Installation, How the Internet works, Introduction to command line, Python installation, Code editor, Introduction to Python. Deploy! comes early (after Django admin), before URLs and views.
- **Versions pinned (V):** the installation chapter has the learner write `requirements.txt` containing `Django~=5.2.12`; the Debian/Ubuntu notes mention `python3.14`; virtual environment via `python -m venv myvenv` (Windows) or `python3 -m venv myvenv`; `pip install -r requirements.txt`.
- **Checkpoints (V):** the first-project chapter says after `migrate` "you should see something like this" with output ending `sessions.0001_initial... OK`, and after `runserver` "you should see the Django install worked page" with an "Install worked!" image. Troubleshooting is inline: "If you don't see a prefix `(myvenv)` in your console, you need to activate your virtualenv"; a Windows `UnicodeDecodeError` variant `runserver 0:8000`; open a second terminal because the server terminal is busy.
- **Reference repository:** none mentioned (V). **Tests or exercises:** none mentioned (V). The site links a YouTube channel for video walkthroughs and a GitHub issues page for reporting mistakes (V).

### A3. The Flask Mega-Tutorial (Miguel Grinberg, 2024 edition) and the `microblog` repository

- **Edition and size:** "2024 edition", posted 2023-12-03; 23 chapters from "Chapter 1: Hello, World!" to "Chapter 23: Application Programming Interfaces (APIs)". (V)
- **How each chapter links to code (V):** every chapter carries three GitHub links: **Browse** (the repository at the tag for that chapter, `/tree/v0.1`), **Zip** (the whole application up to and including this chapter, `archive/v0.1.zip`), **Diff** (the changes made in this chapter, `compare/v0.0...v0.1`). Chapter 15 shows the same three for v0.15: `tree/v0.15`, `archive/v0.15.zip`, `compare/v0.14...v0.15`.
- **Tag scheme (V, read across three tag pages):** `v0.0` "Initial commit (v0.0)" (Jan 6, 2018), then `v0.1` "Chapter 1: Hello, World! (v0.1)" through `v0.23` "Chapter 23: Application Programming Interfaces (APIs)". Each release title follows "Chapter N: Title (v0.N)", so the tag number equals the chapter number. Tag dates range from 2019 to Apr 6, 2025, which shows tags were re-cut as the edition was revised.
- **Repository layout (V):** folders `app`, `deployment`, `migrations`; files `.flaskenv`, `.gitattributes`, `.gitignore`, `Dockerfile`, `LICENSE`, `Procfile`, `README.md`, `Vagrantfile`, `babel.cfg`, `boot.sh`, `config.py`, `microblog.py`, `requirements.txt`, `tests.py`. The README says the code "corresponds to the 2024 edition" and points older editions at separate repositories (`microblog-2018`, `microblog-2012`).
- **Chapter 1 before any Flask code (V):** install Python; verify by starting the interpreter; create a `microblog` directory; `python3 -m venv venv` and activate (commands given for Linux/macOS, Windows cmd, PowerShell); `pip install flask`; verify with `import flask`.
- **Tests (V):** chapter 15 refactors `tests.py` (Python `unittest`, a `UserModelCase` with `setUp()` and `tearDown()`) to use a `TestConfig` with `TESTING = True` and an in-memory SQLite database, each test calling `create_app(TestConfig)`. The chapter does not give the command to run them (V).
- **If you get stuck (V):** in the comments the author's standing advice is "when in doubt, you can always look at the working code for the chapter you are on." Chapter 1 also handles the macOS port-5000 conflict with `flask run --port 5001`.

### A4. Michael Hartl: Ruby on Rails Tutorial (8th edition) and Learn Enough

- **Edition:** "Newly updated for Rails 8"; publisher Learn Enough. (V)
- **Chapters (14, V):** 1 From zero to deploy; 2 A toy app; 3 Mostly static pages; 4 Rails-flavored Ruby; 5 Filling in the layout; 6 Modeling users; 7 Sign up; 8 Basic login; 9 Advanced login; 10 Updating, showing, and deleting users; 11 Account activation; 12 Password reset; 13 User microposts; 14 Following users.
- **Chapter 1 before building the app (V, from section headings; the chapter body is behind the course sign-in):** 1.1 Up and running (Development environment, Installing Rails); 1.2 The first application (Bundler, `rails server`, MVC, Hello, world!); 1.3 Version control with Git (Git setup, "What good does Git do you?", GitHub, "Branch, edit, commit, merge"); 1.4 Deploying (Heroku setup and deployment, Heroku commands); 1.5 Conclusion with "What we learned in this chapter"; 1.6 "Conventions used in this book". So a hello-world app is committed, pushed and deployed before any real feature.
- **Chapter structure (V):** numbered sections and subsections (1.1, 1.1.1); every chapter ends with a Conclusion and "What we learned in this chapter". Testing vocabulary is explicit in headings: "Getting started with testing", "Red", "Green", "Refactor", "Successful edits (with TDD)", "minitest reporters", "Automated tests with Guard".
- **Exercises (V):** the book page says the paid course includes "exercises, and community exercise answers". The free Learn Enough Command Line chapter shows the format: each section from 1.2 to 1.7 ends with a numbered "Exercises" subsection ("1.2.1 Exercises" ... "1.7.1 Exercises"), with a community answer widget ("Your Answer", "Add Answer", "View all"). Listing and Box numbering were not visible in the pages served (not stated).
- **Reference application (V):** `learnenough/rails_tutorial_sample_app_8th_ed`. The README gives the checkpoint sequence: clone; match the Ruby version in `.ruby-version` and the Bundler version in `Gemfile.lock`; `bundle _<version>_ install`; `rails db:migrate`; `rails test` ("if the suite passes, you can seed the database and start the server"); `rails db:seed`; `rails server`. **One branch per chapter** for chapters 3 to 14: `static-pages`, `rails-flavored-ruby`, `filling-in-layout`, `modeling-users`, `sign-up`, `basic-login`, `advanced-login`, `updating-users`, `account-activation`, `password-reset`, `user-microposts`, `following-users`. No tags are listed and Releases is empty.

### A5. The Rust Programming Language (the Rust Book)

- **Edition read:** "This version of the text assumes you're using Rust 1.97.0 (released 2026-07-09) or later with `edition = "2024"`". (V)
- **Chapter layout (21 chapters plus appendices A to G, V):** 1 Getting Started (Installation; Hello, World!; Hello, Cargo!); 2 Programming a Guessing Game; 3 Common Programming Concepts; 4 Understanding Ownership; 5 Structs; 6 Enums and Pattern Matching; 7 Packages, Crates, and Modules; 8 Common Collections; 9 Error Handling; 10 Generic Types, Traits, and Lifetimes; 11 Writing Automated Tests; 12 An I/O Project: Building a Command Line Program; 13 Iterators and Closures; 14 More about Cargo and Crates.io; 15 Smart Pointers; 16 Fearless Concurrency; 17 Async; 18 Object Oriented Programming Features; 19 Patterns and Matching; 20 Advanced Features; 21 Final Project: Building a Multithreaded Web Server.
- **Two kinds of chapters (V):** "In concept chapters, you'll learn about an aspect of Rust. In project chapters, we'll build small programs together, applying what you've learned so far. Chapter 2, Chapter 12, and Chapter 21 are project chapters; the rest are concept chapters."
- **Listing numbering (V):** chapter-sequence captions, for example "Listing 2-1: Code that gets a guess from the user and prints it"; terminal output is also numbered (Listing 2-2 is `cargo build` output); source blocks are introduced by "Filename: src/main.rs" or "Filename: Cargo.toml"; the first test listing is "Listing 11-1: The code generated automatically by `cargo new`".
- **Code that is meant to fail (V):** "we'll provide many examples that don't compile along with the error message the compiler will show you in each situation"; three Ferris icons mark "This code does not compile!", "This code panics!", "This code does not produce the desired behavior." Chapter 2 says "Note that this code won't compile just yet, as we will explain" and then shows `error[E0308]: mismatched types` before the fix.
- **If you get stuck (V):** chapter 2 says "If you get warnings, they are safe to ignore. If you get errors, please check that you have `rand = "0.10.1"` in your _Cargo.toml_." Chapter 1 gives `rustc --version` and a PATH check, and points at the community page for help.
- **Chapter 1 before any project (V):** install with `rustup` (`curl ... https://sh.rustup.rs ... | sh`), `rustc --version`, `rustup doc` for offline docs, `cargo new hello_cargo`, `cargo build`, `cargo run`, `cargo check`, `cargo build --release`; Cargo creates `Cargo.toml`, `src/main.rs`, a Git repository and `.gitignore`, and `Cargo.lock` on first build ("keeps track of the exact versions of dependencies in your project").
- **Tests (chapter 11, V):** "a test in Rust is a function that's annotated with the `test` attribute"; `cargo test` "runs all tests in our project"; `cargo new adder --lib`; `assert!`, `assert_eq!`, `assert_ne!`, `should_panic`. Chapter 12's section "Adding Functionality with Test Driven Development" applies this inside a project chapter.
- **Source and quizzes (V):** "The source files from which this book is generated can be found on GitHub." A separate Brown University version adds "quizzes, highlighting, visualizations, and more"; the official book has no quizzes.

### A6. Real Python project-based tutorials (site refused; GitHub materials read)

- **The tutorial page** `realpython.com/django-todo-lists/` returned HTTP 403 (see Not reachable). Not retried.
- **The companion repository** `realpython/materials` (V): "Bonus materials, exercises, and example projects for Real Python's Python tutorials." One folder per tutorial; Django folders visible include `django-diary`, `django-flashcards-app`, `django-todo-list`, `django-user-management`, `build-a-blog-from-scratch-django`, `create-django-project`.
- **Per-step snapshots (V):** `django-todo-list/` contains `source_code_step_1` through `source_code_step_7` plus `source_code_final` and a README: "Source files supporting the "Manage Your To-Do Lists Using Python and Django" step-by-step tutorial on Real Python." The mapping of folder to tutorial step is inferred from the names (I).
- **Lint gate on the materials repo (V):** contributors must pass `ruff format --check` and `ruff check` with the Ruff version pinned in `requirements.txt`; CI runs Ruff in check mode.

### A7. freeCodeCamp, Scientific Computing with Python (site rendered empty; curriculum source read)

- **The learn pages** at `freecodecamp.org/learn/...` returned no readable content (client-rendered application; see Not reachable). The curriculum lives in the `freeCodeCamp/freeCodeCamp` repository under `curriculum/challenges/english/blocks/`, which was readable.
- **Project blocks (V):** `build-an-arithmetic-formatter-project`, `build-a-budget-app-project`, `build-a-polygon-area-calculator-project`, `build-a-probability-calculator-project`, plus lesson blocks such as `core-primitives-in-python`, `control-flow-and-functions-in-python`, `daily-coding-challenges-python`, `data-analysis-with-python-projects` (93 entries were omitted from the listing served, so this is partial).
- **One challenge file (V):** `build-an-arithmetic-formatter-project/5e44412c903586ffb414c94c.md` has frontmatter `id`, `title: Build an Arithmetic Formatter Project`, `challengeType: 23`, `dashedName`; sections `# --description--`, `# --hints--`, `# --seed--` (with `## --seed-contents--`), `# --solutions--`. **Each hint is one sentence of expected behaviour followed by a Python `unittest` assertion** run in the browser via `runPython`, for example the hint `arithmetic_arranger(["3801 - 2", "123 + 49"])` "should return" the arranged string, followed by `TestCase().assertEqual(arithmetic_arranger([...]), '...')`. The seed is a stub `def arithmetic_arranger(problems, show_answers=False)` that returns its input. The page tells the learner to "open the browser console with F12 to see a more verbose output of the tests."
- **How the curriculum tests itself (V, contributor docs):** `pnpm -F=@freecodecamp/curriculum install-puppeteer` once, then `FCC_CHALLENGE_ID=<id> pnpm run test-curriculum-content`; Python seed code uses four-space indentation; tests may use Chai `assert` with "Prefer the specific assertion method."

### A8. Exercism Python track

- **Scale (V):** "146 exercises grouped into 17 Python Concepts", with personal mentoring; Learn (concepts) and Practice modes.
- **How exercises are tested (V):** "We use pytest as our website test runner." The test file "usually ends in `_test.py`", for example `exercise_test.py`. Run from the exercise folder: `python3 -m pytest -o markers=task <exercise_test.py>`; `-o markers=task` registers the custom marker "task: A concept exercise task" so pytest does not warn about unknown markers (a `pytest.ini` can register it instead). Required plugins: pytest-cache and pytest-subtests; `-x` stops after the first failure, `--ff` runs previously failed tests first. "The local test files are the same tests that run on the website when a solution is uploaded."
- **Local workflow (V):** `exercism configure --token=<token>`; `exercism download --exercise=<slug> --track=<slug>`; each download contains README.md, HELP.md ("how to run the tests and get help"), optional HINTS.md, test files and stub files; `exercism submit <implementation_file_paths>` uploads the solution and prints its URL; an incomplete solution can be submitted to see others' approaches or request a mentor.
- **Python version used by the runner:** not stated on the pages read.

### A9. Vercel's Django examples (two repositories exist)

- **`vercel/examples` → `python/django` (V):** README title "Django + Vercel", "This example shows how to use Django on Vercel with Serverless Functions using the Python Runtime." "Vercel detects Django's `manage.py` and uses it to find the WSGI entrypoint and the static file configuration." Local run: `uv sync`, then `uv run python manage.py runserver` at `http://localhost:8000`. Secret via `DJANGO_SECRET_KEY` env var. Files: `config/` (`__init__.py`, `asgi.py`, `settings.py`, `urls.py`, `wsgi.py`), `example/`, `.gitignore`, `README.md`, `manage.py`, `pyproject.toml`, `uv.lock`. No `vercel.json`, no `requirements.txt`. `pyproject.toml` in full: name `django-vercel`, version `0.1.0`, `requires-python = ">=3.12"`, `dependencies = ["django>=6.0"]`, and no `[tool.vercel]` table. `settings.py`: `ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".vercel.app"]`, `DEBUG = os.environ.get("DJANGO_DEBUG") == "1"`, `SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-change-me-in-production")`, SQLite `DATABASES`, `STATIC_ROOT = BASE_DIR / "staticfiles"`, `STATIC_URL = "/static/"`.
- **`vercel/vercel` → `examples/django` (V), the one `vc init django` clones per Vercel's Django doc:** README "Deploy your Django project to Vercel with zero configuration"; install with `pip install .` or `uv sync`; run with `python run.py` or `uv run run.py` on `http://0.0.0.0:5001`; deploy with `vercel --prod`. `pyproject.toml`: project `vercel-django-starter`, `requires-python = ">=3.10"`, `dependencies = ["django>=4.0"]`, no `[tool.vercel]`. Files listed: `app/`, `.gitignore`, `README.md`, `manage.py`, `pyproject.toml` (listing marked incomplete).
- **Note (I):** the two Vercel-owned examples disagree on the Python floor (3.12 versus 3.10) and the Django floor (6.0 versus 4.0). The `vercel/examples` one matches current Django (6.1 requires Python 3.12 or later, V on PyPI) and is the better model.

### Patterns table

| Tutorial | Chapter layout | Learner-to-reference sync | How exercises are checked | What chapter 1 does before the framework | Tag |
|---|---|---|---|---|---|
| Django official (6.1) | 8 parts; each opens "begins where Tutorial N left off", goal sentence, step sections with full-file listings; "Where to get help" box; "Page not found?" callout | No reference repo; sync by full listings in text | `python manage.py test polls`; tests in `polls/tests.py`; introduced in part 5 | Version check, `startproject`, `runserver` checkpoint, `startapp` | V |
| Django Girls | 24 chapters; six pre-Django chapters; "you should see..." checkpoints with screenshots; inline troubleshooting | No reference repo | None | Installation, how the internet works, command line, Python install, editor, Python intro | V |
| Flask Mega-Tutorial | 23 chapters; sections per feature; Browse/Zip/Diff links per chapter | One tag per chapter, `v0.N` = chapter N, from `v0.0` "Initial commit"; GitHub `tree/`, `archive/`, `compare/` URLs | `tests.py` with `unittest` (chapter 15); run command not stated | Install Python, verify interpreter, `python3 -m venv venv`, `pip install flask` | V |
| Hartl Rails Tutorial 8th ed. | 14 chapters; numbered sections; Conclusion plus "What we learned"; "Conventions used in this book"; TDD headings | Reference app repo with one branch per chapter (3 to 14); README checkpoint `rails test` before `rails server` | Minitest via `rails test`; exercises per section ("1.2.1 Exercises") with community answers (Learn Enough) | Dev env, install, Bundler, `rails server`, hello world, Git, GitHub, deploy to Heroku | V |
| Rust Book | 21 chapters plus 7 appendices; concept chapters and project chapters (2, 12, 21); "Listing N-M" captions; "Filename:" labels; Ferris icons for failing code | Book source on GitHub; no per-chapter code tags | `cargo test`, `#[test]`; TDD section inside project chapter 12 | `rustup`, `rustc --version`, `rustup doc`, `cargo new/build/run/check`, `Cargo.lock` | V |
| Real Python (materials repo) | Not readable (403) | `source_code_step_N` and `source_code_final` folders per tutorial | Not readable; repo CI runs `ruff format --check` and `ruff check` | Not readable | V for repo, I for mapping |
| freeCodeCamp (curriculum source) | One markdown per challenge: description, hints, seed, solutions | Browser editor; no learner repo | Each hint is a sentence plus a `unittest` assertion run via `runPython`; verbose output in the browser console | Lesson blocks precede project blocks | V |
| Exercism Python | Exercise = README, HELP, HINTS, test file, stub | `exercism download` / `exercism submit`; local tests identical to website tests | `python3 -m pytest -o markers=task name_test.py`; pytest-subtests | Install the CLI, configure token | V |
| Vercel Django example | Minimal app, no chapters | None | None | `uv sync`, `uv run python manage.py runserver` | V |

---

## Part B: the Python toolchain in October 2026

### Tool table

| Tool | Version and date as stated | What it is for | Doc page read |
|---|---|---|---|
| CPython | 3.15 first release 2026-10-09, bugfix, EOL scheduled 2031-10; 3.14 released 2025-10-07, bugfix, EOL 2030-10; 3.13 released 2024-10-07, security, EOL 2029-10; 3.12 released 2023-10-02, security, EOL 2028-10; 3.11 security, EOL 2027-10; 3.10 end-of-life 2026-10-01; 3.9 end-of-life 2025-10-31 (V) | The language runtime | devguide.python.org/versions |
| uv | 0.13.6, released Oct 27, 2026, Requires Python >=3.8 (V, PyPI); docs page dated March 13, 2026 (V) | "An extremely fast Python package and project manager, written in Rust"; replaces pip, pip-tools, pipx, poetry, pyenv, twine, virtualenv; `uv init`, `uv add`, `uv lock`, `uv sync`, `uv run`, `uvx`, `uv tool install`, `uv python install` | docs.astral.sh/uv (index, projects guide, tools guide, install-python guide); PyPI |
| ruff | 0.17.3, released Oct 27, 2026, Requires Python >=3.7 (V, PyPI); pre-commit snippet in the tutorial pins `rev: v0.17.3` (V) | "An extremely fast Python linter and code formatter, written in Rust"; "Over 900 built-in rules"; "Drop-in parity with Flake8, isort, and Black"; `ruff check`, `ruff format` | docs.astral.sh/ruff (index, formatter, tutorial, settings); PyPI |
| pytest | 9.1.1, released 2026-06-19 (V, changelog and PyPI); "Python 3.10+ or PyPy 3" (V); 9.0.0 (2025-11-05) dropped Python 3.9; 9.1.0 (2026-06-13) added official Python 3.15 support (V) | Test runner: "only plain `assert` statements are used"; auto-discovery; fixtures; runs unittest suites | docs.pytest.org (index, changelog); PyPI |
| pytest-django | v4.14.0 (2026-08-10) is the newest changelog entry (V); supported Django and Python versions not stated on the pages read | "a plugin for pytest that provides a set of useful tools for testing Django applications and projects"; `pip install pytest-django[django]`; `DJANGO_SETTINGS_MODULE` under `[tool.pytest]` (pytest 9) or `[tool.pytest.ini_options]` (pytest 7 and 8); run with `pytest` | pytest-django.readthedocs.io (index, helpers) |
| pyright | 1.1.414, released Sep 10, 2026 (V, PyPI wrapper) | "a full-featured, standards-based static type checker for Python", "designed for high performance"; installs via Pylance, `pip install pyright` (community package that installs Node automatically) or `npm install -g pyright`; run `pyright` | github.com/microsoft/pyright (README, docs/installation.md, docs/mypy-comparison.md); PyPI |
| mypy | 2.4.0, released Oct 1, 2026, Requires Python >=3.10 (V, PyPI; docs header "mypy 2.4.0 documentation") | "Mypy is a static type checker for Python", "designed with gradual typing in mind"; `python3 -m pip install mypy`; `mypy program.py`; `--strict` | mypy.readthedocs.io (index, getting started); PyPI |
| pydantic | v2.14.1, changelog dated 2026-10-11 (V); "pure, canonical Python 3.10+" (V); v2.14.0 notes drop Python 3.9 (V) | "the most widely used data validation library for Python"; validation and serialization from type hints; core validation logic written in Rust; strict and lax modes; JSON Schema | pydantic.dev/docs/validation/latest (get-started); PyPI |
| pydantic-settings | 2.16.1, released Oct 20, 2026, Requires Python >=3.11 (V, PyPI) | "loading a settings or config class from environment variables or secrets files"; `BaseSettings`, `SettingsConfigDict(env_prefix=..., env_file='.env')`; env vars "always take priority over values loaded from a dotenv file"; unknown dotenv entries raise `ValidationError` under the default `extra='forbid'` | pydantic.dev/docs/validation/latest/concepts/pydantic_settings; PyPI |
| httpx | 0.28.1, released Dec 6, 2024 (latest release); prereleases up to 1.0.dev6 dated Aug 31, 2026 (V, PyPI); "HTTPX requires Python 3.9+" (V, docs) | "a fully featured HTTP client for Python 3, which provides sync and async APIs, and support for both HTTP/1.1 and HTTP/2"; "A broadly requests-compatible API"; "Strict timeouts everywhere."; "Fully type annotated." | python-httpx.org; PyPI |
| Django | 6.1.2 latest, released Oct 6, 2026, Requires Python >=3.12 (V, PyPI and download page). Supported: 5.2 LTS (5.2.18; extended support to April 2028), 6.0 (6.0.9; mainstream ended August 4, 2026; extended to April 2027), 6.1 (6.1.2; mainstream to April 2027, extended to December 2027). Roadmap: 6.2 LTS April 2027 (extended to April 2030); "Django 2028" January 2028; "Django 2029" January 2029 (V) | The web framework; tutorial written for 6.1 | djangoproject.com/download; docs release process; PyPI |
| django-ninja | 1.7.1, released Sep 19, 2026, Requires Python >=3.7, classifiers list Django 3.1 through 6.1 (V, PyPI); the docs index still says "Python 3.6+" (V) | "a web framework for building APIs with Django and Python 3.6+ type hints"; "Very high performance thanks to Pydantic and async support"; OpenAPI and JSON Schema; `pip install django-ninja`; `api = NinjaAPI()`, `@api.get("/add")` on `def add(request, a: int, b: int)`, mounted with `path("api/", api.urls)` | django-ninja.dev; PyPI |
| Django REST framework | 3.18.3, released Oct 6, 2026, Requires Python >=3.10; requires Django 5.2, 6.0, 6.1 and Python 3.10 to 3.15 (V, docs and PyPI) | "a powerful and flexible toolkit for building Web APIs"; browsable API; serializers, viewsets, routers; `pip install djangorestframework` | django-rest-framework.org; PyPI |
| htmx | Docs and homepage script tag pin `htmx.org@2.0.11`; NEWS banner: "htmx 4.0 has been released!" but 4.0 is not marked `latest` on npm and will be "at some point in 2027"; "~16k min.gz'd" (V) | "high power tools for HTML"; `hx-get`, `hx-post`, `hx-target`, `hx-swap`, `hx-trigger`, `hx-boost`; request headers `HX-Request`, `HX-Target`, `HX-Trigger`, `HX-Boosted`, `HX-Current-URL`; response headers `HX-Redirect`, `HX-Trigger` | htmx.org/docs; htmx.org |
| django-htmx | 1.29.0 (docs header); "Python 3.11 to 3.15 supported", "Django 5.2 to 6.1 supported" (V) | "Extensions for using Django with htmx": `HtmxMiddleware` adds `request.htmx` (`bool(request.htmx)` is true when `HX-Request` equals true; attributes `boosted`, `current_url`, `target`, `trigger`, `trigger_name`, `prompt`); `{% htmx_script %}` tag; CSRF via `hx-headers` with `x-csrftoken` on `<body>` (`hx-headers:inherited` for htmx 4) | django-htmx.readthedocs.io (index, installation, middleware) |
| pre-commit | 4.7.0, released Oct 12, 2026, Requires Python >=3.11 (V, PyPI; the site's `pre-commit --version` example also shows 4.7.0) | "A framework for managing and maintaining multi-language pre-commit hooks"; `.pre-commit-config.yaml` with `repos`, `rev`, `hooks`; `pre-commit install`, `pre-commit run --all-files`, `pre-commit autoupdate` | pre-commit.com; PyPI |
| Vercel Python runtime | Supported Python 3.12 (default), 3.13, 3.14 (V); page last updated 2026-08-12; python-version page 2026-04-10 | Runs WSGI/ASGI apps as one Vercel Function; detects frameworks from `requirements.txt`, `pyproject.toml`, or `Pipfile`; dependencies from `pyproject.toml` "(with or without a `uv.lock`)", `requirements.txt`, or `Pipfile.lock`; 500 MB bundle limit, `excludeFiles` for tests | vercel.com/docs/functions/runtimes/python and /python-version |
| Vercel Django support | Page last updated 2026-07-24 (canonical URL now `/docs/frameworks/full-stack/django`); "Minimum CLI version required: 50.38.0" for `vercel dev` and `vc deploy` (V) | Detection via `manage.py`, `DJANGO_SETTINGS_MODULE`, `WSGI_APPLICATION` or `ASGI_APPLICATION`; `[tool.vercel] entrypoint`; `[tool.vercel.scripts] build`; automatic `collectstatic` when `STATIC_ROOT` is set; `maxDuration` under `functions` keyed by `myproject/wsgi.py`; Celery or Dramatiq for queued work; a continuously running worker needs a different deployment shape | vercel.com/docs/frameworks/backend/django (served from the full-stack path) |
| Vercel Cron Jobs | Cron page last updated 2026-09-16; quickstart 2026-08-11; manage page 2026-08-11; pricing page 2026-07-15 (V) | `vercel.json` `crons: [{ "path": "/api/hello", "schedule": "0 5 * * *" }]`; HTTP GET to the production URL; user agent `vercel-cron/1.0`; header `x-vercel-cron-schedule`; "The timezone is always UTC"; `CRON_SECRET` sent as `Authorization: Bearer`; "Vercel will not retry an invocation if a cron job fails"; delivery is "best effort", design jobs to be idempotent; production deployments only; Hobby: 100 jobs, once per day, per-hour precision (plus or minus 59 min); Pro and Enterprise: 100 jobs, once per minute, per-minute precision | vercel.com/docs/cron-jobs, /quickstart, /manage-cron-jobs, /usage-and-pricing |

### B1. Python version support (devguide, V)

Status key quoted from the devguide: "bugfix: Once a version has been fully released, bug fixes and security fixes are accepted."; "security: After two years (18 months for versions before 3.13), only security fixes are accepted and no more binaries are released."; "end-of-life: Five years after a release, support ends." Dates in italics on the page are scheduled and "can be adjusted".

Consequence for Invest.WitUS (I): Django 6.1 needs Python 3.12 or later; Vercel's runtime offers 3.12, 3.13 and 3.14 and not 3.15; of those, only 3.14 is still in bugfix status today. The pin that satisfies every tool above (pydantic-settings and pre-commit need 3.11 or later; django-htmx and DRF are tested up to 3.15) is 3.14.

### B2. Django's release schedule (V)

- Download page: "The latest official version is 6.1.2." Only 5.2 is marked LTS in the supported table; 6.2 LTS is scheduled for April 2027 with extended support to April 2030.
- Release process doc: "Up to Django 6.2, feature releases happen every eight months or so." LTS releases "receive security and data loss fixes for three years." Under the annual cycle that follows: "One feature release will be made each calendar year", "Mainstream support lasts one year, until the next feature release", "Extended support lasts another two years." The download page adds: "Starting with Django 2028, every feature release receives the same three-year support period."
- Deprecation: a feature deprecated in `A.x` keeps working with warnings through all `A.x` and is removed in `B.0` (or `B.1` when deprecated in the last `A.x`), "to ensure deprecations are done over at least 2 feature releases."
- Mainstream support covers "Security fixes, data loss bugs, crashing bugs, major functionality bugs in newly-introduced features"; extended covers "Security fixes and data loss bugs."

### B3. uv (V)

- `uv init` creates `pyproject.toml`, `.python-version`, `README.md`, `.gitignore` and a source file (`src/hello_world/__init__.py` in the docs' library example); `.venv` and `uv.lock` are created on the first `uv run`, `uv sync` or `uv lock`.
- "`uv.lock` is a cross-platform lockfile that contains exact information about your project's dependencies." "This file should be checked into version control, allowing for consistent and reproducible installations across machines." It "is managed by uv and should not be edited manually."
- `uv run` checks before each run that the lockfile matches `pyproject.toml` and the environment matches the lockfile. `uv lock --upgrade-package requests` upgrades one package.
- Tools: `uvx ruff` is "exactly equivalent to" `uv tool run ruff` and runs in a temporary isolated environment; `uv tool install ruff` for frequent use. "If a tool needs your project installed (the page cites `pytest` and `mypy`), use `uv run` instead of `uvx`."
- Python: `uv python install 3.12` (or several versions at once); uv "automatically installs missing Python versions as needed."
- The ruff tutorial's install line for a project is `uv add --dev ruff`.

### B4. ruff (V)

- Linter and formatter in one binary: `ruff check` (with `--fix`) and `ruff format`; "ruff format --check" exits 1 if any file would change.
- Formatter: "designed as a drop-in replacement for Black"; on Django and Zulip "> 99.9% of lines are formatted identically."
- Ordering rule from the formatter page: to sort imports and format, "call the Ruff linter and then the formatter": `ruff check --select I --fix` then `ruff format`. "the formatter does not sort imports by default"; a unified command is "planned". When configured appropriately, "running the formatter should never introduce new lint errors."
- Defaults from the settings page: `line-length` 88; `target-version` default `"py311"`, but the page recommends setting `project.requires-python` instead, which ruff treats as equivalent (and `target-version` "takes precedence over `requires-python`" when both are set). The tutorial says default rule categories are "F, E, B, UP, and RUF" and configures extra rules with `extend-select`.
- Pre-commit hook ids: `ruff-check` and `ruff-format` from `astral-sh/ruff-pre-commit` at `rev: v0.17.3`.

### B5. pytest and pytest-django (V)

- pytest's index example: `test_sample.py` with `def test_answer(): assert inc(3) == 5`, run with `pytest`, failure shown as `assert 4 == 5`.
- pytest-django quick start: `pip install pytest-django[django]`; configure `DJANGO_SETTINGS_MODULE = "test.settings"` under `[tool.pytest]` for pytest 9.0 and later (or `[tool.pytest.ini_options]` for 7.x and 8.x); run `pytest`.
- Helpers: `pytest.mark.django_db` marks a test as needing database access; each test runs in its own transaction rolled back at the end, matching Django's `TestCase`; `transaction=True` behaves like `TransactionTestCase`. `client` is a `django.test.Client` (use `force_login()` or `login()`); `admin_client` is logged in as an admin and "will cause the test to automatically be marked for database use"; `settings` reverts changes at the end of the test; `live_server` runs a server in a background thread and depends on `transactional_db`.

### B6. pyright versus mypy for a TypeScript-minded learner (the docs' own words)

- **What each is.** pyright: "a full-featured, standards-based static type checker for Python", "designed for high performance", and "designed to be used as the foundation for a Python language server" (Pylance in VS Code). mypy: "a static type checker for Python", "designed with gradual typing in mind". (V)
- **Speed.** pyright's comparison doc: "It is not unusual for pyright to be 3x to 5x faster than mypy when type checking large code bases." (V)
- **Inference.** "mypy never infers return types" versus "pyright infers the return type from `return` and `yield` statements". mypy's getting-started page: "By default, mypy will not type check dynamically typed functions." (V)
- **Unions.** "pyright always uses a union operation," while "Mypy typically (but not always) uses a 'join' operation." (V) For someone used to TypeScript's union types, pyright's behaviour is the one that matches expectations (I).
- **Strictness.** mypy: "If you run mypy with the --strict flag, you will basically never get a type related error at runtime without a corresponding mypy error", though it "will probably be too aggressive" for large existing codebases. pyright's comparison doc has a section "'Unknown' Type and Strict Mode". (V)
- **Runtime.** The PyPI `pyright` package is a "Command line wrapper for pyright"; pyright itself "is written in TypeScript and normally installed through npm, so it needs Node"; the wrapper downloads Node if it is missing, and the `nodejs` extra is recommended. (V) The learner already runs Node for the rest of the ecosystem (seed note), so this is no extra cost (I).
- **Adherence.** pyright "generally adheres to the official Python typing specification" and, for unspecified behaviour, "generally tries to adhere to mypy's behavior unless there is a compelling justification for deviating." (V)
- **Verdict (I):** pyright for Invest.WitUS. It is the checker already running inside the editor, it infers more (closer to `tsc`), it treats unions the way TypeScript does, and the pip wrapper makes `uv run pyright` work. Keep mypy out of the course to avoid teaching two checkers' disagreements.

### B7. django-ninja versus Django REST framework for a JSON API (the docs' own words)

- **django-ninja (V):** "a web framework for building APIs with Django and Python 3.6+ type hints"; "Type hints and automatic docs lets you focus only on business logic"; "Based on the open standards for APIs: OpenAPI (previously known as Swagger) and JSON Schema"; "has good integration with the Django core and ORM"; the whole example is one function with typed parameters. PyPI: 1.7.1 (Sep 19, 2026) with classifiers through Django 6.1. The docs index's "Python 3.6+" line is older than PyPI's `>=3.7` floor; the page gives no Django range (not stated).
- **DRF (V):** "a powerful and flexible toolkit for building Web APIs"; "The Web browsable API is a huge usability win for your developers"; "Serialization that supports both ORM and non-ORM data sources"; requires Django 5.2, 6.0 or 6.1 and Python 3.10 to 3.15; 3.18.3 (Oct 6, 2026); the example needs a serializer class, a viewset class and a router.
- **Verdict (I):** django-ninja for the JSON surface. The seed already wants pydantic at boundaries; ninja's request and response schemas are pydantic models, so one validation idiom covers settings, API bodies and vendor payloads (Alpaca, Massive, SnapTrade). A learner from Next.js reads `def add(request, a: int, b: int)` the way he reads a typed route handler. DRF's serializer, viewset and router trio is a second mental model with no payoff for an app whose UI is server-rendered. Keep the API small (the Learn.WitUS evidence endpoint, the CentenarianOS event sender, the cron route) and use HTMX for the pages.

### B8. HTMX with Django (V)

- htmx 2.0.11 is what the docs and homepage install snippet pin; htmx 4.0 exists but is not `latest` on npm until "at some point in 2027". django-htmx 1.29.0 already documents htmx 4 differences (`hx-headers:inherited`; `trigger` and `trigger_name` are "htmx 2 only"; the `target` format changed).
- Install order from django-htmx: `python -m pip install django-htmx`; add `"django_htmx"` to `INSTALLED_APPS`; add `"django_htmx.middleware.HtmxMiddleware"` to `MIDDLEWARE` (gives `request.htmx`); in the base template `{% load django_htmx %}` and `{% htmx_script %}` in `<head>`; put Django's CSRF token on `<body>` via `hx-headers` with `x-csrftoken` so POST requests work.
- View pattern: `if request.htmx:` return a partial template, otherwise the full page (middleware doc).

### B9. pre-commit (V)

`pip install pre-commit` (the project's own page; a `.pyz` zipapp also exists); `.pre-commit-config.yaml` with `repos:` entries carrying `repo`, `rev`, `hooks`; `pre-commit install` installs the git hook; `pre-commit run --all-files` after adding hooks; `pre-commit autoupdate` moves each `rev` to the latest tag. Requires Python 3.11 or later (PyPI).

### B10. Vercel specifics for a Django app (V)

- **Detection:** "Vercel automatically detects Django projects by locating `manage.py` in your repository. Vercel then executes `manage.py` to discover your `DJANGO_SETTINGS_MODULE` and determines the entrypoint from `WSGI_APPLICATION` or `ASGI_APPLICATION`." The runtime page adds that a `manage.py` "in an immediate subdirectory" is also found. When both are set, ASGI wins.
- **pyproject `[tool.vercel]`:** `entrypoint = "myproject.wsgi:application"` points at a custom module; `[tool.vercel.scripts] build = "python build.py"` defines the Build Command (a `vercel.json` or dashboard Build Command takes precedence). "There is no need to call `collectstatic` in a build script. Vercel runs it automatically" when `STATIC_ROOT` is configured; files are served at `STATIC_URL` from the CDN. `[project.scripts] app = "module:variable"` is still honoured for existing projects; `tool.vercel.entrypoint` is for new ones.
- **Function shape:** "When you deploy a Django app to Vercel, it becomes a single Vercel Function" on Fluid compute; `maxDuration` is set in `vercel.json` under `functions` keyed by the resolved entrypoint file, for example `"myproject/wsgi.py": { "maxDuration": 60 }`. Bundle limit 500 MB; `excludeFiles` glob for `tests/**` and the like.
- **Python version selection:** `requires-python` in `pyproject.toml`, or `.python-version`, or `Pipfile.lock`; missing or unsupported falls back to 3.12.
- **Env and database:** integrations set `DATABASE_URL`; the doc's `settings.py` parses it with `urllib.parse` and falls back to SQLite locally; `vercel pull` writes `.env.local`, loaded in `manage.py` with `dotenv` or `django-environ`; "Never commit `.env.local`".
- **Scheduled work:** cron is `vercel.json` `crons` with `path` and `schedule`; each run is a GET to the production URL; secure with `CRON_SECRET` compared against `Authorization: Bearer ...`; no retries; best-effort delivery, so handlers must be idempotent and reconciliation-based ("Query and process all work since the last successful run"); Hobby plan runs at most once per day and anywhere inside the scheduled hour. Local testing is a plain request to the route; `vercel dev` does not run crons.
- **Background workers:** "Enqueue background work from Django views with Celery or Dramatiq. Their Vercel integrations run tasks in queue-triggered functions"; "For a worker that must run continuously, compare Functions, containers, and Daemons".

---

## Part C: recommendations

### C1. Chapter template (one Learn.WitUS lesson = one chapter = one git tag)

Drawn from: Django's "begins where part N left off" opener and help box (A1); Django Girls' "you should see" checkpoints with the exact expected output (A2); Flask's Browse, Zip and Diff links (A3); Hartl's "What we learned" conclusion and `rails test` gate (A4); the Rust Book's numbered listings, "Filename:" labels and deliberately failing code (A5); freeCodeCamp's hint-plus-assertion pairs (A7); Exercism's one-command test run and HELP file (A8).

```
# Chapter NN: <verb phrase>            (title also used for the git tag message)

Starts from: tag vNN-1 of invest-witus. If your repo does not match, run the sync step in "If you get stuck".
Goal: one sentence, written as the user-visible outcome ("the app lists my paper-trading positions").
What you will learn: 3 to 5 bullets, each tied to a TypeScript or Next.js idea the learner already has
   ("Django's URLconf is the App Router's folder tree, written as a list").
Time: estimate.

## Steps
NN.1 ... NN.k. Each step:
   - "Filename: invest/positions/models.py" label above every code block (Rust Book convention).
   - Listing NN-M caption on every block, including terminal output.
   - Full file for new files; for edits, the full file with the changed lines marked
     (Django style), never a fragment the learner must place by guesswork.
   - Code that is meant to fail is labelled before it is shown, and the error is printed in full.

## Checkpoint
   - The exact command: `uv run pytest tests/test_chNN.py` (or the full suite).
   - The exact expected output lines (Django Girls style): "N passed".
   - A browser check: the URL and what the page should show.

## Exercises (optional, Hartl style)
   - 1 to 3 short tasks. Each has a hidden test in tests/exercises/test_chNN_exN.py so it is
     checked, not just read. Quiz questions in Learn.WitUS come from these.

## If you get stuck
   - Browse: https://github.com/<owner>/invest-witus/tree/vNN
   - Diff for this chapter: https://github.com/<owner>/invest-witus/compare/vNN-1...vNN
   - Zip: https://github.com/<owner>/invest-witus/archive/vNN.zip   (Flask form, verify at the first tag)
   - Sync your repo to the reference (two commands; see C3).
   - Known traps (port in use, venv not active, migrations not applied) with the exact message.

## What we learned (Hartl)
   - 3 to 5 bullets. Becomes the Learn.WitUS lesson summary.

## Next: Chapter NN+1 starts from tag vNN.
```

The checkpoint test is the chapter's acceptance test. It is written by the reference implementation first (TDD in the Rust Book's chapter 12 sense), lives in the reference repo at the chapter's tag, and is copied into the learner's repo as the chapter's first step, so the learner starts every chapter red and ends green.

### C2. Repository layout for the reference app (`invest-witus`)

Mirrors the `vercel/examples` Django layout (A9), the Flask repo's root `tests.py` moved to a `tests/` package, pytest-django's config location (B5), and Vercel's detection rules (B10).

```
invest-witus/
  manage.py                      # Vercel's detection anchor (B10)
  pyproject.toml                 # [project] requires-python = ">=3.12"; deps; [dependency-groups] dev;
                                 # [tool.ruff], [tool.ruff.lint], [tool.pytest] DJANGO_SETTINGS_MODULE,
                                 # [tool.pyright]; [tool.vercel] only if the entrypoint is non-standard
  uv.lock                        # committed (B3)
  .python-version                # 3.14 (B1)
  .pre-commit-config.yaml        # ruff-check, ruff-format at rev v0.17.3 (B4)
  vercel.json                    # crons[], functions{ "config/wsgi.py": { maxDuration } } (B10)
  .env.example                   # names only; pydantic-settings reads .env locally (B tool table)
  config/                        # settings.py, urls.py, wsgi.py, asgi.py (same names as Vercel's example)
  invest/                        # the Django apps, one per chapter cluster:
    core/                        #   settings via pydantic-settings, health route, HTMX base template
    accounts/                    #   Sign in with WitUS (OIDC client), rows keyed by WitUS user id
    methods/                     #   the taught investing methods and their rules, links to lessons
    brokers/                     #   Alpaca paper adapter behind a Protocol; pydantic models at the boundary
    prices/                      #   daily pull, pandas tables
    adherence/                   #   the product: rule checks, nudges, lesson links
    api/                         #   django-ninja NinjaAPI mounted at /api/ (B7)
    jobs/                        #   cron routes guarded by CRON_SECRET (B10)
  templates/                     # Django templates with htmx partials
  static/                        # STATIC_ROOT = BASE_DIR / "staticfiles" at build (B10)
  tests/
    conftest.py                  # pytest-django fixtures
    test_ch01.py ... test_chNN.py  # one checkpoint file per chapter
    exercises/                   # hidden exercise tests
  docs/
    chapters/NN-slug.md          # the chapter text, source for the Learn.WitUS lesson
    CHAPTERS.md                  # table: chapter, tag, lesson URL, what the checkpoint tests
```

Rule: a chapter may add files anywhere, but it may not rename or move files from earlier chapters, so the per-chapter diffs stay readable (I, from the Flask diff links).

### C3. How the learner's repo and the reference relate: tags per chapter

**Recommendation: one annotated tag per chapter in `invest-witus` (`v00` initial commit, `v01` ... `vNN`), with the Flask Mega-Tutorial's three links on every chapter page.** Not branches, not a solutions folder.

Why, from Part A:

1. **Tags give three stable URLs for free.** GitHub serves `tree/<tag>`, `archive/<tag>.zip` and `compare/<a>...<b>` for tags; the Flask tutorial uses exactly these on every chapter (A3, V); the tag dates (v0.0 in 2018, later tags re-dated up to April 2025) suggest the tags were re-cut as the edition was revised while the chapter links kept the same form (I). A Learn.WitUS lesson can link all three and the links never move.
2. **The diff is the lesson.** `compare/v04...v05` shows the learner only what chapter 5 changed, which is what a stuck learner needs; a branch per chapter (Hartl's `static-pages` ... `following-users`, A4) shows a full tree and makes the learner diff two branches himself. Hartl's branches also stop at chapter 14 with no tags, so there is no "zip of chapter 7".
3. **Branches drift.** A branch is mutable; when the reference app gets a fix, a branch per chapter has to be rebased in order, and the learner's checkout of `chapter-05` can silently change. A tag is a fixed point; a fix produces a new tag (`v05.1`) and the chapter page says which tag it was written against, the way the Rust Book states "Rust 1.97.0 (released 2026-07-09)" (A5).
4. **A solutions folder breaks the app.** Real Python's `source_code_step_1 ... source_code_step_7` plus `source_code_final` (A6) works for a seven-step article but means eight copies of the project in one repo; Django's `manage.py` detection on Vercel (B10) and the import paths would have to be duplicated or the folders excluded from the bundle. It also hides the history that `git log v04..v05` gives.
5. **The learner keeps his own history.** BAM's repo is separate by decision 4 in the seed. He never clones the reference; he reads the diff and types. When stuck, two commands bring his tree to the reference state for that chapter without losing his history:

   ```
   git remote add reference https://github.com/<owner>/invest-witus.git   # once
   git fetch reference --tags && git checkout v05 -- .                      # take chapter 5's files
   ```
   (`git checkout <tag> -- .` overlays the tagged files onto the working tree; this is standard git, not a fact from a page fetched today, so treat the exact flags as to be verified when the first chapter is written.)

6. **Tests ride on the tag.** The checkpoint test for chapter NN is in the tag, so "run the tests at tag vNN" is the same gate for the reference and the learner (Hartl's `rails test` before `rails server`, A4; Exercism's "the same tests that run on the website", A8).

Tag naming: `vNN` with two digits (`v01`, not `v1`) so tags sort in chapter order in GitHub's tag list, which sorts descending (A3 showed `v0.23` down to `v0.0`). Release titles follow Flask's "Chapter NN: Title (vNN)" so the tags page doubles as a table of contents.

### C4. DX checklist (one command each)

All commands run from the repo root with uv, so neither the learner nor the reference has to activate a virtual environment (B3: `uv run` syncs the lockfile and environment before each run).

| Need | One command | Source |
|---|---|---|
| Set up | `uv sync` (creates `.venv` and installs from `uv.lock`; uv downloads Python 3.14 if missing) | B3 |
| Run the tests | `uv run pytest` (pytest-django config under `[tool.pytest]` in `pyproject.toml`) | B5 |
| Lint and format | `uv run ruff check --fix . && uv run ruff format .` (linter first, then formatter, the order the ruff docs give) | B4 |
| Type check | `uv run pyright` | B6 |
| Run the app | `uv run python manage.py runserver` (the Vercel example's own README line) | A9 |
| Deploy | `vc deploy` for a preview, `vercel deploy --prod` for production (CLI 50.38.0 or newer) | B10 |
| Pre-commit | `uvx pre-commit install` once; hooks `ruff-check` and `ruff-format` | B4, B9 |

Settings: a single `Settings(BaseSettings)` in `invest/core/settings.py` reading `.env` locally and Vercel env vars in production; env vars win over `.env` (B tool table), and unknown `.env` keys raise at startup, which catches typos in a learner's file early (I). Django's `settings.py` reads from that object.

Chapter 1 (before any Django), in the order the tutorials above all share: install uv; `uv python install 3.14`; `uv init invest-witus-mine`; `uv add django` and `uv add --dev pytest pytest-django ruff pyright pre-commit`; commit `uv.lock`; `uv run pytest` on a one-line `tests/test_ch01.py` (`assert 1 + 1 == 2`, the pytest index example shape) so the learner sees red and green before any framework; `git init`, first push, `vc deploy` of the hello page. That is the Flask chapter 1 (Python, venv, install) plus Hartl's chapter 1 (git, GitHub, deploy) plus the Rust Book's `cargo test` on an empty project, compressed into one lesson (I).

### C5. How each Learn.WitUS lesson points at the chapter

- **Stable URL per tag.** Each lesson carries three links, labelled as Flask labels them: **Browse** `https://github.com/<owner>/invest-witus/tree/vNN`, **Diff** `https://github.com/<owner>/invest-witus/compare/vNN-1...vNN`, **Zip** `https://github.com/<owner>/invest-witus/archive/vNN.zip`. All three forms (`tree/`, `compare/`, `archive/<tag>.zip`) were read on the Flask chapter pages today (V); verify each resolves at the first `invest-witus` tag before publishing a lesson (authoritative-values rule).
- **Lesson text lives in the repo**, at `docs/chapters/NN-slug.md` at the same tag, and the Learn.WitUS lesson body is rendered from it (one source, the way the Rust Book is generated from `src/` on GitHub, A5). The lesson header records "Written against tag vNN, Django 6.1.x, Python 3.14" the way the Rust Book records its Rust version.
- **Quiz questions** come from the chapter's exercises and checkpoint (what command runs the tests; what the diff added; which setting the cron route checks), so a quiz pass means the learner ran the code (I).
- **Lesson URL back-link.** `docs/CHAPTERS.md` in the reference repo maps tag to lesson URL so the reference app's own "method adherence" screens (seed decision 6) can link back to lessons with the same table.
- **Evidence.** In phase 2 (seed note), the checkpoint test's pass output is what the learner submits to the Learn evidence endpoint; Exercism's model is the template: local tests identical to the server's, submit with one command (A8).

---

## Not reachable

| URL | What happened | What was used instead |
|---|---|---|
| https://realpython.com/django-todo-lists/ | HTTP 403 Forbidden. Not retried. | The `realpython/materials` repository on GitHub (A6). |
| https://www.freecodecamp.org/learn/scientific-computing-with-python/ | Page served with no readable content (client-rendered application). | The `freeCodeCamp/freeCodeCamp` curriculum source on GitHub (A7). |
| https://www.freecodecamp.org/learn/scientific-computing-with-python/build-an-arithmetic-formatter-project/build-an-arithmetic-formatter | HTTP 404. | The challenge markdown in the curriculum repository (A7). |
| https://contribute.freecodecamp.org/ (root) | Page served with no readable content. | The direct page `/how-to-work-on-coding-challenges/` loaded and was used (A7). |
| https://github.com/freeCodeCamp/freeCodeCamp/tree/main/curriculum/challenges/english/07-scientific-computing-with-python | HTTP 404 (path no longer exists). | `curriculum/challenges/english/blocks/` (A7). |
| https://www.railstutorial.org/book/beginning and https://www.learnenough.com/ruby-on-rails-8th-edition-tutorial/beginning | Reachable, but only the table of contents and sign-in widgets were served; the chapter body is behind the course account. | Section headings, the book page, the free Learn Enough Command Line chapter, and the reference app's README (A4). |
| https://docs.pydantic.dev/latest/ and .../concepts/pydantic_settings/ | 301 redirect to pydantic.dev/docs/validation/latest/... | The redirect targets were fetched and read (B tool table). |
| https://github.com/miguelgrinberg/microblog (root) | Reachable, but the root page shows no tag list. | The three paginated `/tags` pages (A3). |

No site was circumvented. No paywalled body text was obtained.

---

## References

Astral. (n.d.). *Installing Python*. uv documentation. https://docs.astral.sh/uv/guides/install-python/ (retrieved October 27, 2026)

Astral. (n.d.). *Ruff: An extremely fast Python linter and code formatter, written in Rust*. https://docs.astral.sh/ruff/ (retrieved October 27, 2026)

Astral. (n.d.). *Settings*. Ruff documentation. https://docs.astral.sh/ruff/settings/ (retrieved October 27, 2026)

Astral. (n.d.). *The Ruff formatter*. Ruff documentation. https://docs.astral.sh/ruff/formatter/ (retrieved October 27, 2026)

Astral. (n.d.). *Tutorial*. Ruff documentation. https://docs.astral.sh/ruff/tutorial/ (retrieved October 27, 2026)

Astral. (n.d.). *Using tools*. uv documentation. https://docs.astral.sh/uv/guides/tools/ (retrieved October 27, 2026)

Astral. (2026, March 13). *uv: An extremely fast Python package and project manager, written in Rust*. https://docs.astral.sh/uv/ (retrieved October 27, 2026)

Astral. (n.d.). *Working on projects*. uv documentation. https://docs.astral.sh/uv/guides/projects/ (retrieved October 27, 2026)

htmx.org. (n.d.). *htmx: high power tools for HTML*. https://htmx.org/ (retrieved October 27, 2026)

htmx.org. (n.d.). *htmx documentation*. https://htmx.org/docs/ (retrieved October 27, 2026)

Django REST framework. (n.d.). *Django REST framework*. https://www.django-rest-framework.org/ (retrieved October 27, 2026)

Django Girls. (n.d.). *Django Girls Tutorial*. https://tutorial.djangogirls.org/en/ (retrieved October 27, 2026)

Django Girls. (n.d.). *Django installation*. Django Girls Tutorial. https://tutorial.djangogirls.org/en/django_installation/ (retrieved October 27, 2026)

Django Girls. (n.d.). *Your first Django project!* Django Girls Tutorial. https://tutorial.djangogirls.org/en/django_start_project/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.). *Django's release process*. Django documentation (development version). https://docs.djangoproject.com/en/dev/internals/release-process/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.). *Download Django*. https://www.djangoproject.com/download/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.). *Getting started*. Django 6.1 documentation. https://docs.djangoproject.com/en/6.1/intro/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.). *Writing your first Django app, parts 1 through 8*. Django 6.1 documentation. https://docs.djangoproject.com/en/6.1/intro/tutorial01/ through https://docs.djangoproject.com/en/6.1/intro/tutorial08/ (retrieved October 27, 2026)

PyPI. (2026). *Django 6.1.2*. https://pypi.org/project/Django/ (retrieved October 27, 2026)

HTTPX. (n.d.). *HTTPX*. https://www.python-httpx.org/ (retrieved October 27, 2026)

PyPI. (2024). *httpx 0.28.1*. https://pypi.org/project/httpx/ (retrieved October 27, 2026)

Exercism. (n.d.). *Python track*. https://exercism.org/tracks/python (retrieved October 27, 2026)

Exercism. (n.d.). *Tests*. Python track documentation. https://exercism.org/docs/tracks/python/tests (retrieved October 27, 2026)

Exercism. (n.d.). *Working locally*. https://exercism.org/docs/using/solving-exercises/working-locally (retrieved October 27, 2026)

freeCodeCamp. (n.d.). *Build an Arithmetic Formatter Project* [Curriculum source file 5e44412c903586ffb414c94c.md]. GitHub. https://github.com/freeCodeCamp/freeCodeCamp/tree/main/curriculum/challenges/english/blocks/build-an-arithmetic-formatter-project (retrieved October 27, 2026)

freeCodeCamp. (n.d.). *Curriculum challenge blocks* [Directory listing]. GitHub. https://github.com/freeCodeCamp/freeCodeCamp/tree/main/curriculum/challenges/english/blocks (retrieved October 27, 2026)

freeCodeCamp. (n.d.). *How to work on coding challenges*. Contributing guidelines. https://contribute.freecodecamp.org/how-to-work-on-coding-challenges/ (retrieved October 27, 2026)

Grinberg, M. (2023). *The Flask Mega-Tutorial, Part I: Hello, World!* https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world (retrieved October 27, 2026)

Grinberg, M. (n.d.). *The Flask Mega-Tutorial, Part XV: A Better Application Structure*. https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xv-a-better-application-structure (retrieved October 27, 2026)

Grinberg, M. (n.d.). *microblog* [Repository and tag pages]. GitHub. https://github.com/miguelgrinberg/microblog and https://github.com/miguelgrinberg/microblog/tags (retrieved October 27, 2026)

Hartl, M. (n.d.). *Ruby on Rails Tutorial: Learn Web Development with Rails* (8th ed.). Learn Enough. https://www.railstutorial.org/book (retrieved October 27, 2026)

Hartl, M. (n.d.). *Chapter 1: From zero to deploy*. Ruby on Rails Tutorial (8th ed.). https://www.learnenough.com/ruby-on-rails-8th-edition-tutorial/beginning (retrieved October 27, 2026)

Hartl, M. (n.d.). *Chapter 1: Basics*. Learn Enough Command Line to Be Dangerous. https://www.learnenough.com/command-line-tutorial/basics (retrieved October 27, 2026)

Hartl, M., & Learn Enough. (n.d.). *rails_tutorial_sample_app_8th_ed* [Repository]. GitHub. https://github.com/learnenough/rails_tutorial_sample_app_8th_ed (retrieved October 27, 2026)

django-htmx. (n.d.). *django-htmx 1.29.0 documentation*. https://django-htmx.readthedocs.io/en/latest/ (retrieved October 27, 2026)

django-htmx. (n.d.). *Installation*. django-htmx documentation. https://django-htmx.readthedocs.io/en/latest/installation.html (retrieved October 27, 2026)

django-htmx. (n.d.). *Middleware*. django-htmx documentation. https://django-htmx.readthedocs.io/en/latest/middleware.html (retrieved October 27, 2026)

Klabnik, S., Nichols, C., & Krycho, C. (2026). *The Rust Programming Language*. https://doc.rust-lang.org/book/ (retrieved October 27, 2026)

Klabnik, S., Nichols, C., & Krycho, C. (2026). *Introduction; Getting Started; Installation; Hello, Cargo!; Programming a Guessing Game; How to Write Tests*. The Rust Programming Language. https://doc.rust-lang.org/book/ch00-00-introduction.html, .../ch01-00-getting-started.html, .../ch01-01-installation.html, .../ch01-03-hello-cargo.html, .../ch02-00-guessing-game-tutorial.html, .../ch11-01-writing-tests.html (retrieved October 27, 2026)

Django Ninja. (n.d.). *Django Ninja: Fast Django REST Framework*. https://django-ninja.dev/ (retrieved October 27, 2026)

PyPI. (2026). *django-ninja 1.7.1*. https://pypi.org/project/django-ninja/ (retrieved October 27, 2026)

mypy project. (n.d.). *mypy 2.4.0 documentation* and *Getting started*. https://mypy.readthedocs.io/en/stable/ and https://mypy.readthedocs.io/en/stable/getting_started.html (retrieved October 27, 2026)

Microsoft. (n.d.). *Pyright* [README], *Installation*, and *Mypy comparison*. GitHub. https://github.com/microsoft/pyright (README.md, docs/installation.md, docs/mypy-comparison.md) (retrieved October 27, 2026)

pre-commit. (n.d.). *pre-commit: A framework for managing and maintaining multi-language pre-commit hooks*. https://pre-commit.com/ (retrieved October 27, 2026)

Pydantic. (n.d.). *Pydantic Validation: Get started* (v2.14.1). https://pydantic.dev/docs/validation/latest/get-started/ (retrieved October 27, 2026)

Pydantic. (n.d.). *Settings management*. Pydantic Validation documentation. https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/ (retrieved October 27, 2026)

PyPI. (2026). *mypy 2.4.0; pre-commit 4.7.0; pydantic 2.14.1; pydantic-settings 2.16.1; pyright 1.1.414; pytest 9.1.1; ruff 0.17.3; uv 0.13.6; djangorestframework 3.18.3* [Package pages]. https://pypi.org/project/<name>/ (retrieved October 27, 2026)

pytest-dev. (n.d.). *pytest: helps you write better programs* and *Changelog*. https://docs.pytest.org/en/stable/ and https://docs.pytest.org/en/stable/changelog.html (retrieved October 27, 2026)

pytest-dev. (n.d.). *pytest-django documentation* and *Django helpers*. https://pytest-django.readthedocs.io/en/latest/ and https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 27, 2026)

Python Software Foundation. (n.d.). *Status of Python versions*. Python Developer's Guide. https://devguide.python.org/versions/ (retrieved October 27, 2026)

Real Python. (n.d.). *materials* [Repository and django-todo-list folder]. GitHub. https://github.com/realpython/materials and https://github.com/realpython/materials/tree/master/django-todo-list (retrieved October 27, 2026)

Rust Project. (n.d.). *SUMMARY.md* [Table of contents of The Rust Programming Language]. GitHub. https://raw.githubusercontent.com/rust-lang/book/main/src/SUMMARY.md (retrieved October 27, 2026)

Vercel. (2026, July 24). *Deploy a Django app on Vercel*. Vercel Documentation. https://vercel.com/docs/frameworks/backend/django (retrieved October 27, 2026)

Vercel. (2026, August 12). *Using the Python Runtime with Vercel Functions*. Vercel Documentation. https://vercel.com/docs/functions/runtimes/python (retrieved October 27, 2026)

Vercel. (2026, April 10). *Set the Python version for your Vercel project*. Vercel Documentation. https://vercel.com/docs/functions/runtimes/python/python-version (retrieved October 27, 2026)

Vercel. (2026, September 16). *Cron Jobs*. Vercel Documentation. https://vercel.com/docs/cron-jobs (retrieved October 27, 2026)

Vercel. (2026, August 11). *Getting started with cron jobs*. Vercel Documentation. https://vercel.com/docs/cron-jobs/quickstart (retrieved October 27, 2026)

Vercel. (2026, August 11). *Managing Cron Jobs*. Vercel Documentation. https://vercel.com/docs/cron-jobs/manage-cron-jobs (retrieved October 27, 2026)

Vercel. (2026, July 15). *Usage & Pricing for Cron Jobs*. Vercel Documentation. https://vercel.com/docs/cron-jobs/usage-and-pricing (retrieved October 27, 2026)

Vercel. (n.d.). *Django + Vercel* [Example: python/django, with config/settings.py and pyproject.toml]. GitHub. https://github.com/vercel/examples/tree/main/python/django (retrieved October 27, 2026)

Vercel. (n.d.). *Django Starter* [Example: examples/django, with pyproject.toml]. GitHub. https://github.com/vercel/vercel/tree/main/examples/django (retrieved October 27, 2026)
