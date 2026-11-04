"""Decision 174: the rules version a month was closed under.

Additive: one nullable column on `methods_monthlyreview`, then one data step that writes 1 on
every month already closed, or closed once and since reopened (it has a "closed" event), because
every one of those was reviewed under version 1 of its method's rules. The step only touches rows
whose column is still empty, so running it twice changes nothing, and the old code, which does not
know the column, keeps working while the migration runs.
"""

from typing import Any

from django.db import migrations, models
from django.db.models import Q


def pin_reviewed_months_to_version_1(apps: Any, schema_editor: Any) -> None:
    # The database being migrated, not "default": the migrate workflow runs `migrate --database
    # direct` with no DATABASE_URL, so "default" there is an empty SQLite file (2026-11-04 failure).
    alias = schema_editor.connection.alias
    monthly_review = apps.get_model("methods", "MonthlyReview")
    reviewed = Q(closed_at__isnull=False) | Q(events__action="closed")
    ids = (
        monthly_review.objects.using(alias)
        .filter(reviewed, rules_version__isnull=True)
        .values_list("pk", flat=True)
    )
    monthly_review.objects.using(alias).filter(pk__in=list(ids)).update(rules_version=1)


class Migration(migrations.Migration):
    dependencies = [
        ("methods", "0005_view_preference"),
    ]

    operations = [
        migrations.AddField(
            model_name="monthlyreview",
            name="rules_version",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="The rules version the month was first closed under. Empty: the newest.",
                null=True,
            ),
        ),
        migrations.RunPython(pin_reviewed_months_to_version_1, migrations.RunPython.noop),
    ]
