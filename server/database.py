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
    # Проверяем и исправляем формат URL для Render
    original_url = DATABASE_URL
    
    # Render может предоставлять postgres:// или postgresql:// вместо postgresql+asyncpg://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        print(f"INFO: Преобразовали DATABASE_URL: postgres:// -> postgresql+asyncpg://")
    elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        print(f"INFO: Преобразовали DATABASE_URL: postgresql:// -> postgresql+asyncpg://")
    elif not DATABASE_URL.startswith("postgresql"):
        print(f"WARNING: Неожиданный формат DATABASE_URL: {DATABASE_URL[:50]}...")
    
    # Проверяем, не используется ли External URL на Render
    # External URL обычно содержит внешний домен типа *.render.com
    # Internal URL обычно содержит внутренний хост типа dpg-xxxxx-a
    from urllib.parse import urlparse
    try:
        parsed = urlparse(DATABASE_URL)
        hostname = parsed.hostname or ""
        
        # Если используется внешний хост (содержит .render.com), предупреждаем
        if ".render.com" in hostname and "dpg-" not in hostname:
            print(f"WARNING: Похоже используется External Database URL. На Render используйте Internal Database URL!")
            print(f"INFO: Хост базы данных: {hostname}")
            print(f"INFO: Internal URL обычно начинается с 'postgresql://' и содержит 'dpg-xxxxx-a' в хосте")
    except Exception as e:
        print(f"WARNING: Не удалось проанализировать DATABASE_URL: {e}")
    
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

