"""make audit log and status history append only

The database refuses UPDATE and DELETE on these tables (task 1.8).
TRUNCATE is still allowed, so scripts/seed_data.py can rebuild the database.

Revision ID: 4c8768dbe5fc
Revises: 7c0a5724b92a
Create Date: 2026-11-17 19:16:44.098821

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c8768dbe5fc"
down_revision: str | Sequence[str] | None = "7c0a5724b92a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("audit_log", "status_history")


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION reject_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only: % is not allowed',
                TG_TABLE_NAME, TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """)
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION reject_change();"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table};")
    op.execute("DROP FUNCTION IF EXISTS reject_change();")
