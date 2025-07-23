from typing import Optional, List
from pydantic import BaseModel
from datetime import date

class DailyForecast(BaseModel):
    date: date
    condition: str
    icon: str
    temp_min: float
    temp_max: float

class ChecklistCreate(BaseModel):
    city: str
    start_date: date
    end_date: date
    items: List[str]
    avg_temp: float
    conditions: List[str]
    checked_items: Optional[List[str]] = None
    removed_items: Optional[List[str]] = None
    added_items: Optional[List[str]] = None
    tg_user_id: Optional[str] = None

class ChecklistOut(ChecklistCreate):
    slug: str
