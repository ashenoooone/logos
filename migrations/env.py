"""Окружение Alembic для базы данных SQLite проекта Logos."""

from __future__ import annotations

from pathlib import Path

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from logos_backend.db import database_url

url = database_url()
if url.database:
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)

connectable = create_engine(url, poolclass=NullPool)
try:
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
finally:
    connectable.dispose()
