from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr
from datetime import date, datetime


# === User схемы ===

class UserCreate(BaseModel):
    email: str
    username: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class TelegramAuth(BaseModel):
    tg_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: Optional[str] = None
    username: str
    tg_id: Optional[str] = None
    is_stats_public: bool = True
    created_at: Optional[datetime] = None
    avatar: Optional[str] = None
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    is_following: Optional[bool] = False

    class Config:
        from_attributes = True


class UserAvatarUpdate(BaseModel):
    avatar: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# === Checklist схемы ===

class DailyForecast(BaseModel):
    date: date
    condition: str
    icon: str
    temp_min: float
    temp_max: float
    city: Optional[str] = None
    humidity: Optional[float] = None
    uv_index: Optional[float] = None
    wind_speed: Optional[float] = None
    source: Optional[str] = "forecast"

class ItineraryEventCreate(BaseModel):
    event_date: date
    time: Optional[str] = None
    title: str
    description: Optional[str] = None
    address: Optional[str] = None

class ItineraryEventUpdate(BaseModel):
    event_date: Optional[date] = None
    time: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None

class ItineraryEventOut(ItineraryEventCreate):
    id: int
    checklist_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ChecklistCreate(BaseModel):
    city: str
    start_date: date
    end_date: date
    items: List[str]
    avg_temp: Optional[float] = None
    conditions: Optional[List[str]] = None
    checked_items: Optional[List[str]] = None
    removed_items: Optional[List[str]] = None
    added_items: Optional[List[str]] = None
    daily_forecast: Optional[List[DailyForecast]] = None
    origin_city: Optional[str] = None
    tg_user_id: Optional[str] = None
    user_id: Optional[int] = None
    is_public: bool = True
    invite_token: Optional[str] = None
    hidden_sections: Optional[List[str]] = []

    class Config:
        from_attributes = True


class UserBackpackBase(BaseModel):
    items: Optional[List[str]] = []
    checked_items: Optional[List[str]] = []
    added_items: Optional[List[str]] = []
    removed_items: Optional[List[str]] = []

class UserBackpackUpdate(UserBackpackBase):
    pass

class UserBackpackOut(UserBackpackBase):
    id: int
    checklist_id: int
    user_id: int
    user: UserOut

    class Config:
        from_attributes = True


class ChecklistOut(ChecklistCreate):
    slug: str
    invite_token: Optional[str] = None
    events: Optional[List[ItineraryEventOut]] = []
    backpacks: Optional[List[UserBackpackOut]] = []

class NotificationOut(BaseModel):
    id: int
    user_id: int
    type: str
    content: str
    link: Optional[str] = None
    is_read: bool
    extra_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
