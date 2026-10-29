"""Which module checks which method: one set of checked rule ids per method id.

Chapter 03 wrote one rule set (`review.CHECKED_RULES`, index investing). Chapter 14 adds the
second (`momentum.CHECKED_RULES`). A test walks every method the package ships and asserts its
TOML file's rule ids equal its set here, so a rules file without checks, or a check without a
rule, fails the suite.
"""

from invest_witus.adherence import momentum, review

CHECKED_RULES: dict[str, frozenset[str]] = {
    "index-dca": review.CHECKED_RULES,
    "momentum-12-1": momentum.CHECKED_RULES,
}
