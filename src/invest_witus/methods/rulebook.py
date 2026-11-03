"""Load a method's rules from the TOML file that ships inside the package.

2026-11-03 (decision 173): a method's rules can have versions. `<id>.toml` is the method's first
file (chapter 03's `index_dca.toml` stays version 1, which the command line reads); a later
version ships beside it as `<id>.vN.toml`, its `version` equal to N. `load_method` reads the first
file, as it always has; `load_method_version` reads one version; `latest_method` the newest, which
the web pages and the start form use. A closed month keeps the version it was closed under.
"""

import re
import tomllib
from dataclasses import dataclass
from importlib.resources import files

LESSON_COMING = "lesson coming"
# A later version of a method's rules: `index_dca.v2.toml` is version 2 of `index-dca`.
VERSION_FILE = re.compile(r"(?P<stem>[a-z0-9_]+)\.v(?P<version>[1-9][0-9]*)\.toml")


class UnknownMethodError(LookupError):
    """No rules file ships for this method id."""


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    text: str
    lesson: str


@dataclass(frozen=True, slots=True)
class Method:
    id: str
    name: str
    version: int
    summary: str
    lesson: str
    rules: tuple[Rule, ...]

    def rule(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(f"method {self.id!r} has no rule {rule_id!r}")

    def lesson_for(self, rule_id: str) -> str:
        """The rule's lesson, else the method's lesson, else 'lesson coming'."""
        return self.rule(rule_id).lesson or self.lesson or LESSON_COMING


def available_methods() -> list[Method]:
    """Every method that ships in this package, by id: one per `.toml` file, at its newest
    version (decision 173: a `.vN.toml` file is a version of a method, not another method).
    Chapter 10's start form reads this list, so a method added as a file appears there without a
    code change."""
    package = files("invest_witus.methods")
    ids = sorted(
        resource.name.removesuffix(".toml").replace("_", "-")
        for resource in package.iterdir()
        if resource.name.endswith(".toml") and VERSION_FILE.fullmatch(resource.name) is None
    )
    return [latest_method(method_id) for method_id in ids]


def method_versions(method_id: str) -> list[int]:
    """Every version of the method's rules that ships, oldest first: the first file's version,
    then each `<id>.vN.toml`."""
    stem = method_id.replace("-", "_")
    later = sorted(
        int(match.group("version"))
        for resource in files("invest_witus.methods").iterdir()
        if (match := VERSION_FILE.fullmatch(resource.name)) is not None
        and match.group("stem") == stem
    )
    return [load_method(method_id).version, *later]


def load_method_version(method_id: str, version: int) -> Method:
    """One version of the method's rules: the first file when its `version` is the one asked
    for, else `<id>.vN.toml`. An unknown version is an `UnknownMethodError`, never the nearest."""
    first = load_method(method_id)
    if first.version == version:
        return first
    resource = files("invest_witus.methods") / f"{method_id.replace('-', '_')}.v{version}.toml"
    if not resource.is_file():
        raise UnknownMethodError(f"method {method_id!r} has no version {version}")
    method = read_method(resource.read_text(encoding="utf-8"))
    if (method.id, method.version) != (first.id, version):
        raise UnknownMethodError(f"{resource.name} says {method.id!r} version {method.version}")
    return method


def latest_method(method_id: str) -> Method:
    """The newest version of the method's rules: what a month that is not closed is judged by."""
    return load_method_version(method_id, method_versions(method_id)[-1])


def load_method(method_id: str) -> Method:
    """Read `<method_id with underscores>.toml` from the methods package: the method's first file
    (for index-dca, chapter 03's version 1)."""
    resource = files("invest_witus.methods") / f"{method_id.replace('-', '_')}.toml"
    if not resource.is_file():
        raise UnknownMethodError(f"unknown method {method_id!r}")
    return read_method(resource.read_text(encoding="utf-8"))


def read_method(text: str) -> Method:
    data = tomllib.loads(text)
    return Method(
        id=str(data["id"]),
        name=str(data["name"]),
        version=int(data["version"]),
        summary=str(data["summary"]),
        lesson=str(data.get("lesson", "")),
        rules=tuple(
            Rule(id=str(r["id"]), text=str(r["text"]), lesson=str(r.get("lesson", "")))
            for r in data["rules"]
        ),
    )
