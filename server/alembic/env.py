import sys
import os
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from alembic import context
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем корень проекта в sys.path, чтобы можно было импортировать server.*
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Alembic Config object
config = context.config

# Настраиваем логирование
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Получаем DATABASE_URL из переменных окружения
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL не установлен в переменных окружения!")

# Преобразуем URL для синхронного движка (psycopg2 вместо asyncpg)
if database_url.startswith("postgresql+asyncpg://"):
    sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgresql://"):
    # Если уже postgresql://, просто добавляем +psycopg2
    sync_database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgres://"):
    sync_database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
else:
    sync_database_url = database_url

# Создаем синхронный движок для Alembic
sync_engine = create_engine(sync_database_url, poolclass=pool.NullPool)

# Импортируем Base и модели
from database import Base
from models import Checklist

target_metadata = Base.metadata

print(f"DEBUG Alembic: DATABASE_URL найден, таблицы в metadata: {list(target_metadata.tables.keys())}")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Используем DATABASE_URL из переменных окружения
    url = sync_database_url
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
