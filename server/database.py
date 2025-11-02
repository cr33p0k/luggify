import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker

class Base(DeclarativeBase):
    pass

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Не падаем при импорте, но будет ошибка при использовании
    DATABASE_URL = None
    async_engine = None
    sync_engine = None
    SessionLocal = None
else:
    # Асинхронный движок для приложения
    async_engine = create_async_engine(DATABASE_URL, echo=True)

    # Синхронный движок для Alembic
    if DATABASE_URL.startswith("postgresql+asyncpg"):
        SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    else:
        SYNC_DATABASE_URL = DATABASE_URL

    sync_engine = create_engine(SYNC_DATABASE_URL, echo=True)

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession
    )

