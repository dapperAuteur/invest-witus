# Chapter 00: Set up your machine and your repository

**Starts from:** nothing. **Ends at:** tag `v00` of the reference repo.
**Written against:** uv 0.13.6, Python 3.14.10, pytest 9.2.0, ruff 0.17.3, pyright 1.1.414 (October 27, 2026).
**Goal:** a Python project of your own that runs one passing test, with a linter, a formatter and a type checker
wired in, pushed to your own GitHub repository.
**Time:** 30 to 45 minutes, most of it downloads.

## What you will learn

- **uv is npm, nvm and npx in one tool.** It installs Python itself, creates the project, keeps a lockfile and runs
  commands inside the project's environment (Astral, n.d.-c).
- **`pyproject.toml` is `package.json`.** Dependencies, scripts and every tool's settings live in one file.
- **`uv.lock` is `package-lock.json`.** Commit it. uv writes it; you never edit it by hand (Astral, n.d.-c).
- **pytest is Jest, ruff is ESLint plus Prettier, pyright is `tsc --noEmit`.** pyright is the type checker that
  powers Pylance in VS Code (Microsoft, n.d.).

## How this tutorial works

You build the app in **your own** repository, chapter by chapter. The reference repository has one git tag per
chapter. When you finish chapter NN, your tests should pass the same way the reference's do at tag `vNN`. Every
chapter ends with three links (Browse, Diff, Zip) so you can compare your work with the reference when you get
stuck. The idea, and the link format, come from Miguel Grinberg's Flask Mega-Tutorial (Grinberg, 2023).

This project started from freeCodeCamp's course "Python Algorithmic Trading with SnapTrade, Massive, Alpaca"
(Carnes, 2026), which builds a momentum app in Django. We take a different path: plain Python first, one
investing method at a time, and an app whose job is helping you stay with a method you learned.

## Steps

### 00.1 Install uv

uv's own installation page gives this command for macOS and Linux (Astral, n.d.-a):

Listing 00-1, Terminal:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

It installs `uv` and `uvx` into `~/.local/bin` and adds that folder to your shell's PATH. Open a new terminal
window, then check:

Listing 00-2, Terminal:

```sh
uv --version
```

```text
uv 0.13.6 (329bf9448 2026-10-26 x86_64-apple-darwin)
```

Your build hash and platform may differ. Any 0.13.x is fine.

### 00.2 Install Python 3.14

You don't need a system Python. uv downloads its own (Astral, n.d.-b):

Listing 00-3, Terminal:

```sh
uv python install 3.14
```

```text
Installed Python 3.14.10 in 56.36s
 + cpython-3.14.10-macos-x86_64-none (python3.14)
```

Why 3.14: Django 6.1, which we add later, needs Python 3.12 or newer, and 3.14 is the newest release that still
gets bug fixes and that Vercel's Python runtime offers.

### 00.3 Create the project

Pick a folder name for your copy. This tutorial uses `invest-witus-mine`. The **package name** must be
`invest-witus` so your code and the reference's line up file for file:

Listing 00-4, Terminal:

```sh
uv init --package --name invest-witus --python 3.14 --author-from none invest-witus-mine
cd invest-witus-mine
```

What each flag does:

| Flag | Why |
|---|---|
| `--package` | Makes an installable package in `src/invest_witus/`, with a command you can run. |
| `--name invest-witus` | Same package name as the reference. Python turns the dash into an underscore for the import name: `invest_witus`. |
| `--python 3.14` | Pins the version in `.python-version`. |
| `--author-from none` | Keeps your git email out of `pyproject.toml`. |

uv also ran `git init` for you. Look at what you got:

Listing 00-5, the new files:

```text
.gitignore
.python-version
README.md
pyproject.toml
src/invest_witus/__init__.py
```

Run the command uv generated. The first run creates `.venv` (your `node_modules`) and `uv.lock`:

Listing 00-6, Terminal:

```sh
uv run invest-witus
```

```text
Hello from invest-witus!
```

Where does that come from? Open `pyproject.toml`. The `[project.scripts]` table maps the command name to a
function, the way `"bin"` does in a `package.json`:

```toml
[project.scripts]
invest-witus = "invest_witus:main"
```

`invest_witus:main` means "the function `main` in the package `invest_witus`", which is
`src/invest_witus/__init__.py`.

### 00.4 Add the developer tools

Listing 00-7, Terminal:

```sh
uv add --dev pytest ruff pyright
```

`--dev` puts them in a `dev` dependency group, like `devDependencies`. Open `pyproject.toml` again and you will
see the new `[dependency-groups]` table. uv also updated `uv.lock`.

### 00.5 Configure the tools

Add these tables to the end of `pyproject.toml`.

Listing 00-8, Filename: `pyproject.toml` (append):

```toml
[tool.pytest]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
# E/F: errors, I: import order, UP: modern Python syntax, B: likely bugs
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
include = ["src", "tests"]
typeCheckingMode = "strict"
```

`typeCheckingMode = "strict"` is the `"strict": true` of `tsconfig.json`. Python's type hints are optional and
ignored when the code runs; pyright is what reads them. Strict mode means every function you write needs its
types written out, which is the habit TypeScript already gave you.

### 00.6 Write a test that fails, then make it pass

Make a `tests` folder and this file. The assertion is wrong on purpose.

Listing 00-9, Filename: `tests/test_ch00.py` (this code fails):

```python
import sys

import invest_witus


def test_python_is_3_14_or_newer() -> None:
    assert sys.version_info >= (3, 14)


def test_the_package_imports() -> None:
    assert invest_witus.__name__ == "invest-witus"
```

Listing 00-10, Terminal:

```sh
uv run pytest
```

```text
E       AssertionError: assert 'invest_witus' == 'invest-witus'
...
========================= 1 failed, 1 passed in 0.08s ==========================
```

Read the failure. The package's import name uses an underscore. Fix the string to `"invest_witus"` and run
`uv run pytest` again.

Things to notice, coming from TypeScript:

- A test is any function whose name starts with `test_` in a file whose name starts with `test_`. No `describe`,
  no `it`, no imports from pytest.
- `assert` is a Python keyword, not a function. pytest rewrites it so the failure shows both sides.
- `-> None` is the return type. Indentation is the block; there are no braces.
- `sys.version_info >= (3, 14)` compares tuples item by item, left to right.

### 00.7 Run the linter, the formatter and the type checker

Listing 00-11, Terminal:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
All checks passed!
4 files already formatted
0 errors, 0 warnings, 0 informations
```

The first `pyright` run downloads a Node.js runtime for itself, so it is slow once. `ruff check --fix .` fixes
what it can; `ruff format .` rewrites files the way Prettier does.

### 00.8 Commit and push to your own GitHub repository

Listing 00-12, Terminal:

```sh
git add -A
git commit -m "Chapter 00: set up the project"
gh repo create invest-witus-mine --private --source . --push
```

If you don't use the GitHub CLI, create an empty private repository on github.com and follow its "push an existing
repository" instructions. Check that `uv.lock` is in the commit: it must be, so your machine and any other machine
install the same versions.

## Checkpoint

- `uv run pytest` prints `2 passed`.
- `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` all pass.
- `uv run invest-witus` prints `Hello from invest-witus!`.
- Your repository is on GitHub with `uv.lock` committed.

## Exercises

1. Add a third test that checks `sys.version_info.major == 3`. Run it.
2. Run `uv run python` to open the Python prompt (the REPL, like `node` with no arguments). Type
   `0.1 + 0.2` and press Enter. Remember the answer; chapter 01 explains it. Leave with `exit()`.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v00
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v00.zip
- `uv: command not found`: open a new terminal so the PATH change takes effect.
- pytest says `no tests ran`: the file name or the function name doesn't start with `test_`.

The reference repository is private while the project is tested, so these links work only for accounts that
have been given access.

## What we learned

- uv manages Python, the project, the lockfile and the commands you run.
- `pyproject.toml` holds dependencies, scripts and tool settings in one place.
- pytest finds `test_` functions and explains a failed `assert`.
- ruff lints and formats; pyright checks types in strict mode.

## Next

Chapter 01 starts from tag `v00` and writes the first piece of the app: the math of putting the same amount of
money into an index fund every month.

## References

Astral. (n.d.-a). *Installation*. uv documentation. https://docs.astral.sh/uv/getting-started/installation/
(retrieved October 27, 2026)

Astral. (n.d.-b). *Installing Python*. uv documentation. https://docs.astral.sh/uv/guides/install-python/
(retrieved October 27, 2026)

Astral. (n.d.-c). *Working on projects*. uv documentation. https://docs.astral.sh/uv/guides/projects/
(retrieved October 27, 2026)

Carnes, B. (2026, September 29). *Python algorithmic trading with SnapTrade, Massive, Alpaca* [Video course
announcement]. freeCodeCamp.
https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/

Grinberg, M. (2023). *The Flask Mega-Tutorial, Part I: Hello, World!*
https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world (retrieved October 27, 2026)

Microsoft. (n.d.). *Pyright* [README]. GitHub. https://github.com/microsoft/pyright (retrieved October 27, 2026)
