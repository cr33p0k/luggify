import sys
import os
from logging.config import fileConfig

from sqlalchemy import pool
from alembic import context

# Добавляем корень проекта в sys.path, чтобы можно было импортировать server.*
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Alembic Config object
config = context.config

# Настраиваем логирование
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Импортируем Base и синхронный движок для Alembic
from database import Base, sync_engine  
from models import Checklist

target_metadata = Base.metadata

print("DEBUG Alembic: tables in metadata:", target_metadata.tables.keys())

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = sync_engine  # используем синхронный движок

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
