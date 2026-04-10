from sqlalchemy import Column, Integer, String, Date, Float, DateTime, ForeignKey, func, Boolean, JSON, Table
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

followers_association = Table(
    "followers",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("following_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("created_at", DateTime, server_default=func.now())
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # nullable для Telegram-пользователей
    tg_id = Column(String, unique=True, index=True, nullable=True)  # Telegram user ID
    is_stats_public = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    avatar = Column(String, nullable=True)  # URL, emoji or base64
    bio = Column(String, nullable=True)     # User biography/description
    social_links = Column(JSON, nullable=True) # JSON store for {"instagram": "...", "telegram": "..."}
    is_email_verified = Column(Boolean, default=False, server_default="false")
    email_verification_code = Column(String, nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    # Связь с чеклистами
    checklists = relationship("Checklist", back_populates="user")

    # Notifications
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    # Подписки (на кого подписан этот юзер)
    following = relationship(
        "User",
        secondary=followers_association,
        primaryjoin=id == followers_association.c.follower_id,
        secondaryjoin=id == followers_association.c.following_id,
        backref="followers"
    )

    trusted_devices = relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")


class UserDevice(Base):
    """Trusted devices for a user to skip email verification on login."""
    __tablename__ = "user_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(String, nullable=False, index=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    last_used_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="trusted_devices")


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
    origin_city = Column(String, nullable=True)  # город отправления
    tg_user_id = Column(String, nullable=True, index=True)  # Telegram user id
    checked_items = Column(ARRAY(String), nullable=True)
    removed_items = Column(ARRAY(String), nullable=True)
    removed_items = Column(ARRAY(String), nullable=True)
    added_items = Column(ARRAY(String), nullable=True)
    daily_forecast = Column(JSON, nullable=True) 
    is_public = Column(Boolean, default=True)
    hidden_sections = Column(ARRAY(String), default=[], server_default="{}")
    transports = Column(ARRAY(String), nullable=True)

    # Привязка к пользователю (nullable — для обратной совместимости)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user = relationship("User", back_populates="checklists")
    
    # Инвайт-ссылка для расшаривания (опционально)
    invite_token = Column(String, unique=True, index=True, nullable=True)

    # Рюкзаки пользователей (личные вещи внутри общего чеклиста)
    backpacks = relationship("UserBackpack", back_populates="checklist", cascade="all, delete-orphan", lazy="selectin")

    # События маршрута
    events = relationship("ItineraryEvent", back_populates="checklist", cascade="all, delete-orphan", lazy="selectin")

class UserBackpack(Base):
    __tablename__ = "user_backpacks"

    id = Column(Integer, primary_key=True, index=True)
    checklist_id = Column(Integer, ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Списки вещей конкретного пользователя
    items = Column(ARRAY(String), default=[])
    checked_items = Column(ARRAY(String), default=[])
    added_items = Column(ARRAY(String), default=[])
    removed_items = Column(ARRAY(String), default=[])
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    checklist = relationship("Checklist", back_populates="backpacks")
    user = relationship("User", lazy="joined")

class ItineraryEvent(Base):
    __tablename__ = "itinerary_events"

    id = Column(Integer, primary_key=True, index=True)
    checklist_id = Column(Integer, ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True)
    event_date = Column(Date, nullable=False)
    time = Column(String, nullable=True) # e.g. "14:30"
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    address = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    checklist = relationship("Checklist", back_populates="events")

class CityAttraction(Base):
    __tablename__ = "city_attractions"

    id = Column(Integer, primary_key=True, index=True)
    city_name = Column(String, unique=True, index=True, nullable=False) # lowercase
    data = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False) # e.g. "checklist_invitation"
    content = Column(String, nullable=False)
    link = Column(String, nullable=True) # e.g. "/checklists/some-slug"
    is_read = Column(Boolean, default=False)
    extra_data = Column(JSON, nullable=True) # For tokens or other metadata
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="notifications")

class FollowRequest(Base):
    __tablename__ = "follow_requests"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    to_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, default="pending", nullable=False)  # pending, accepted, declined
    created_at = Column(DateTime, server_default=func.now())

    from_user = relationship("User", foreign_keys=[from_user_id], lazy="joined")
    to_user = relationship("User", foreign_keys=[to_user_id], lazy="joined")
