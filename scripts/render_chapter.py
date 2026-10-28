"""Render a chapter from its template, pasting the real files into the listings.

    uv run python scripts/render_chapter.py docs/chapters/templates/04-the-first-django-page.md
    uv run python scripts/render_chapter.py --check docs/chapters/templates/04-...md

A line holding `{{file:path/from/the/repo/root}}` becomes a fenced code block with that file's
contents, the language picked from the extension (`{{file:path|lang}}` overrides it). The result
is written to `docs/chapters/<same file name>`, so the chapter text and the code cannot drift.
`--check` writes nothing and exits 1 when the rendered chapter is stale.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS = ROOT / "docs" / "chapters"
PLACEHOLDER = re.compile(r"^\{\{file:(?P<path>[^|}]+)(?:\|(?P<lang>[\w-]+))?\}\}$", re.MULTILINE)
LANGUAGES = {
    ".py": "python",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
    ".csv": "text",
    ".txt": "text",
    ".example": "sh",
}


def listing(path: str, lang: str | None) -> str:
    file = ROOT / path
    text = file.read_text(encoding="utf-8").rstrip("\n")
    fence = "````" if "```" in text else "```"
    language = lang or LANGUAGES.get(file.suffix, "text")
    return f"{fence}{language}\n{text}\n{fence}"


def render(template: Path) -> str:
    source = template.read_text(encoding="utf-8")
    return PLACEHOLDER.sub(lambda m: listing(m.group("path"), m.group("lang")), source)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    templates = [Path(a) for a in argv if not a.startswith("--")]
    if not templates:
        print(__doc__, file=sys.stderr)
        return 2
    stale: list[Path] = []
    for template in templates:
        target = CHAPTERS / template.name
        rendered = render(template)
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                stale.append(target)
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"wrote {target.relative_to(ROOT)}")
    for target in stale:
        print(f"stale: {target.relative_to(ROOT)} (re-run without --check)", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
