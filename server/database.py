import os

from env_utils import load_app_env


load_app_env()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker

class Base(DeclarativeBase):
    pass

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set!")

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
    class_=AsyncSession,
    expire_on_commit=False,
)

from fastapi import HTTPException

async def get_db():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="База данных не настроена. Проверьте переменную окружения DATABASE_URL")
    async with SessionLocal() as session:
        try:
            yield session
        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=503, detail=f"Ошибка БД: {str(e)}")

