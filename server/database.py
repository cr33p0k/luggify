from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

Base = declarative_base()
from server import models

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
print("DATABASE_URL =", DATABASE_URL)

# Асинхронный движок (для приложения)
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Синхронный движок (для Alembic)
# Для этого нужно изменить URL, чтобы он был синхронным
SYNC_DATABASE_URL = DATABASE_URL.replace("asyncpg", "psycopg2")
sync_engine = create_engine(SYNC_DATABASE_URL, echo=True)

