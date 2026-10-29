"""The production-migration workflow: runs on merges that change migrations, reads one secret, fails
closed without it, and never needs the site's real secret key."""

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "migrate-production.yml"


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_runs_on_main_when_migrations_change_and_by_hand() -> None:
    body = text()
    assert "branches: [main]" in body
    assert '"src/**/migrations/**"' in body
    assert "workflow_dispatch:" in body


def test_reads_one_secret_and_fails_closed_without_it() -> None:
    body = text()
    assert body.count("secrets.NEON_DIRECT_URL") == 2
    assert 'if [ -z "$NEON_DIRECT_URL" ]' in body and "exit 1" in body
    assert "DJANGO_SECRET_KEY: secrets." not in body.replace("${{ ", "")


def test_migrates_the_direct_database_and_checks_nothing_is_left() -> None:
    body = text()
    assert "migrate --database direct --noinput" in body
    assert "migrate --database direct --check" in body
    assert "cancel-in-progress: false" in body, "two merges never migrate at once"
