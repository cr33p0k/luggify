from sqlalchemy import Column, Integer, String, Date, Float, DateTime, ForeignKey, func, Boolean, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # nullable для Telegram-пользователей
    tg_id = Column(String, unique=True, index=True, nullable=True)  # Telegram user ID
    is_stats_public = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Связь с чеклистами
    checklists = relationship("Checklist", back_populates="user")


class Checklist(Base):
    __tablename__ = "checklists"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    items = Column(ARRAY(String))  # массив строк
    avg_temp = Column(Float)        # float вместо строки
    conditions = Column(ARRAY(String))
    slug = Column(String, unique=True, index=True)  # токен/slug
    tg_user_id = Column(String, nullable=True, index=True)  # Telegram user id
    checked_items = Column(ARRAY(String), nullable=True)
    removed_items = Column(ARRAY(String), nullable=True)
    removed_items = Column(ARRAY(String), nullable=True)
    added_items = Column(ARRAY(String), nullable=True)
    daily_forecast = Column(JSON, nullable=True) 
    is_public = Column(Boolean, default=True)

    # Привязка к пользователю (nullable — для обратной совместимости)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user = relationship("User", back_populates="checklists")
