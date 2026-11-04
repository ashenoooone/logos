"""Создаёт таблицы менеджеров, сессий, одноразовых ссылок и попыток входа.

Идентификатор ревизии: 0002
Предыдущая ревизия: 0001
Дата создания: 2026-11-04

Существующая строка administrators не изменяется; singleton-администратор и
его CLI-логин/хеш остаются прежними.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "managers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_normalized", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_managers_name_not_blank"),
        sa.CheckConstraint("length(trim(email)) > 0", name="ck_managers_email_not_blank"),
    )

    op.create_table(
        "login_attempts",
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("scope", "identifier", name="pk_login_attempts"),
        sa.CheckConstraint(
            "scope IN ('administrator', 'manager')",
            name="ck_login_attempts_scope",
        ),
        sa.CheckConstraint("failed_count >= 0", name="ck_login_attempts_count"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "administrator_id",
            sa.Integer(),
            sa.ForeignKey("administrators.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(administrator_id IS NOT NULL AND manager_id IS NULL) "
            "OR (administrator_id IS NULL AND manager_id IS NOT NULL)",
            name="ck_sessions_single_owner",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_sessions_expiry"),
    )

    op.create_table(
        "one_time_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('invitation', 'password_reset')",
            name="ck_one_time_links_purpose",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_one_time_links_expiry"),
    )

    op.create_index(
        "uq_one_time_links_active",
        "one_time_links",
        ["manager_id", "purpose"],
        unique=True,
        sqlite_where=sa.text("consumed_at IS NULL AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_one_time_links_active", table_name="one_time_links")
    op.drop_table("one_time_links")
    op.drop_table("sessions")
    op.drop_table("login_attempts")
    op.drop_table("managers")
