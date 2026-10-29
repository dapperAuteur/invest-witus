"""Load a method's rules from the TOML file that ships inside the package."""

import tomllib
from dataclasses import dataclass
from importlib.resources import files

LESSON_COMING = "lesson coming"


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
    """Every method that ships in this package, by id: one per `.toml` file. Chapter 10's start
    form reads this list, so a method added as a file appears there without a code change."""
    package = files("invest_witus.methods")
    ids = sorted(
        resource.name.removesuffix(".toml").replace("_", "-")
        for resource in package.iterdir()
        if resource.name.endswith(".toml")
    )
    return [load_method(method_id) for method_id in ids]


def load_method(method_id: str) -> Method:
    """Read `<method_id with underscores>.toml` from the methods package."""
    resource = files("invest_witus.methods") / f"{method_id.replace('-', '_')}.toml"
    if not resource.is_file():
        raise UnknownMethodError(f"unknown method {method_id!r}")
    data = tomllib.loads(resource.read_text(encoding="utf-8"))
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
