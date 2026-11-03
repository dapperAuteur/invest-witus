"""Which module checks which method: one set of checked rule ids per method id.

Chapter 03 wrote one rule set (`review.CHECKED_RULES`, index investing). Chapter 14 adds the
second (`momentum.CHECKED_RULES`). A test walks every method the package ships and asserts its
TOML file's rule ids equal its set here, so a rules file without checks, or a check without a
rule, fails the suite.

2026-11-03 (decision 173): a method's rules can have versions (`index_dca.v2.toml`), each checked
by its own module. `CHECKED_RULES` stays the first file's set, by method id; `CHECKED_BY_VERSION`
holds every version that ships, and a test walks those too.
"""

from invest_witus.adherence import index_dca_v2, momentum, review

CHECKED_RULES: dict[str, frozenset[str]] = {
    "index-dca": review.CHECKED_RULES,
    "momentum-12-1": momentum.CHECKED_RULES,
}

CHECKED_BY_VERSION: dict[tuple[str, int], frozenset[str]] = {
    ("index-dca", 1): review.CHECKED_RULES,
    ("index-dca", 2): index_dca_v2.CHECKED_RULES,
    ("momentum-12-1", 1): momentum.CHECKED_RULES,
}
