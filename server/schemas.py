from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime


# === User схемы ===

class UserCreate(BaseModel):
    email: str
    username: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str
    device_id: Optional[str] = None
    user_agent: Optional[str] = None


class VerifyDeviceLogin(BaseModel):
    email: str
    password: str
    code: str
    device_id: str
    remember_device: bool = True
    user_agent: Optional[str] = None


class TelegramAuth(BaseModel):
    init_data: Optional[str] = None
    tg_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: Optional[str] = None
    hash: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: Optional[str] = None
    username: str
    tg_id: Optional[str] = None
    is_stats_public: bool = True
    is_email_verified: bool = False
    created_at: Optional[datetime] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    packing_profile: Optional[Dict[str, Any]] = None
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    is_following: Optional[bool] = False

    class Config:
        from_attributes = True

class UserSearchResult(BaseModel):
    id: int
    username: str
    avatar: Optional[str] = None
    bio: Optional[str] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    bio: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    avatar: Optional[str] = None
    is_stats_public: Optional[bool] = None
    packing_profile: Optional[Dict[str, Any]] = None

class UserInfo(BaseModel):
    avatar: Optional[str] = None

class UserAvatarUpdate(BaseModel):
    avatar: str


class TelegramLinkResponse(BaseModel):
    linked: bool
    tg_id: Optional[str] = None
    bot_username: str
    deep_link: str
    link_command: str
    expires_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    message: Optional[str] = None
    email_delivery_failed: bool = False

class TripReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    text: str = Field(..., min_length=10, max_length=2000)
    photo: Optional[str] = None

class TripReviewOut(BaseModel):
    id: int
    rating: int
    text: str
    photo: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user: UserOut
    checklist_slug: Optional[str] = None
    checklist_city: Optional[str] = None
    checklist_start_date: Optional[date] = None
    checklist_end_date: Optional[date] = None

    class Config:
        from_attributes = True


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
    item_quantities: Optional[Dict[str, int]] = None
    packed_quantities: Optional[Dict[str, int]] = None
    daily_forecast: Optional[List[DailyForecast]] = None
    origin_city: Optional[str] = None
    tg_user_id: Optional[str] = None
    user_id: Optional[int] = None
    is_public: bool = True
    invite_token: Optional[str] = None
    hidden_sections: Optional[List[str]] = []
    transports: Optional[List[str]] = None

    class Config:
        from_attributes = True


class UserBackpackBase(BaseModel):
    name: Optional[str] = "Рюкзак"
    kind: Optional[str] = "backpack"
    sort_order: Optional[int] = 0
    is_default: Optional[bool] = False
    editor_user_ids: Optional[List[int]] = []
    items: Optional[List[str]] = []
    checked_items: Optional[List[str]] = []
    added_items: Optional[List[str]] = []
    removed_items: Optional[List[str]] = []
    item_quantities: Optional[Dict[str, int]] = {}
    packed_quantities: Optional[Dict[str, int]] = {}

class UserBaggageCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    kind: Optional[str] = "custom"
    user_id: Optional[int] = None

class UserBaggageUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=60)
    kind: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None
    editor_user_ids: Optional[List[int]] = None

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
    reviews: Optional[List[TripReviewOut]] = []


class ChecklistAIAction(BaseModel):
    type: str
    items: List[str]


class ChecklistAICommandRequest(BaseModel):
    command: str = Field(..., min_length=2, max_length=500)
    language: str = "ru"


class ChecklistAICommandResponse(BaseModel):
    applied: bool
    recognized_action_request: bool = False
    message: str
    actions: List[ChecklistAIAction] = []
    checklist: ChecklistOut

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

class FollowRequestOut(BaseModel):
    id: int
    from_user: UserOut
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
