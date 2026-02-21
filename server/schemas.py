from typing import Optional, List
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

    class Config:
        from_attributes = True


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
    tg_user_id: Optional[str] = None
    user_id: Optional[int] = None
    is_public: bool = True

    class Config:
        from_attributes = True


class ChecklistOut(ChecklistCreate):
    slug: str
