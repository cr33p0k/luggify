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
    is_admin: bool = False
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
    photos: Optional[List[str]] = None

class TripReviewOut(BaseModel):
    id: int
    rating: int
    text: str
    photo: Optional[str] = None
    photos: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user: UserOut
    checklist_slug: Optional[str] = None
    checklist_city: Optional[str] = None
    checklist_start_date: Optional[date] = None
    checklist_end_date: Optional[date] = None

    class Config:
        from_attributes = True


class AttractionImageUpdate(BaseModel):
    city: str = Field(..., min_length=1, max_length=160)
    lang: str = Field("ru", min_length=2, max_length=12)
    limit: int = Field(10, ge=1, le=30)
    attraction_name: str = Field(..., min_length=1, max_length=220)
    attraction_link: Optional[str] = Field(default=None, max_length=1200)
    image: str = Field(..., min_length=8, max_length=2_000_000)
    image_position: Optional[str] = Field(default="center center", max_length=32)


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
    lat: Optional[float] = None
    lng: Optional[float] = None
    place_source: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    travel_buffer_minutes: Optional[int] = Field(default=None, ge=0, le=480)
    event_type: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class ItineraryEventUpdate(BaseModel):
    event_date: Optional[date] = None
    time: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    place_source: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    travel_buffer_minutes: Optional[int] = Field(default=None, ge=0, le=480)
    event_type: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class ItineraryEventOut(ItineraryEventCreate):
    id: int
    checklist_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TripProfileData(BaseModel):
    trip_type: str = "city_break"
    trip_activities: List[str] = []
    baggage_format: str = "flexible"
    accommodation_type: str = "unspecified"
    accommodation_selected: bool = False
    laundry_access: str = "limited"
    packing_style: str = "balanced"
    adults: int = 2
    children_ages: List[int] = []
    child_profiles: List[Dict[str, Any]] = []
    infants_count: int = 0
    trip_note: Optional[str] = None
    context_enhanced: bool = False
    extracted_tags: List[str] = []

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
    item_categories: Optional[Dict[str, str]] = None
    item_translations: Optional[Dict[str, Dict[str, str]]] = None
    daily_forecast: Optional[List[DailyForecast]] = None
    origin_city: Optional[str] = None
    tg_user_id: Optional[str] = None
    user_id: Optional[int] = None
    is_public: bool = True
    invite_token: Optional[str] = None
    hidden_sections: Optional[List[str]] = []
    transports: Optional[List[str]] = None
    trip_type: Optional[str] = None
    trip_profile: Optional[TripProfileData] = None
    expense_budget_amount: Optional[float] = None
    expense_base_currency: str = "RUB"

    class Config:
        from_attributes = True


class UserBackpackBase(BaseModel):
    name: Optional[str] = "Рюкзак"
    kind: Optional[str] = "backpack"
    child_profile_id: Optional[str] = None
    sort_order: Optional[int] = 0
    is_default: Optional[bool] = False
    editor_user_ids: Optional[List[int]] = []
    items: Optional[List[str]] = []
    checked_items: Optional[List[str]] = []
    added_items: Optional[List[str]] = []
    removed_items: Optional[List[str]] = []
    item_quantities: Optional[Dict[str, int]] = {}
    packed_quantities: Optional[Dict[str, int]] = {}
    item_categories: Optional[Dict[str, str]] = {}
    item_translations: Optional[Dict[str, Dict[str, str]]] = {}

class UserBaggageCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    kind: Optional[str] = "custom"
    user_id: Optional[int] = None
    child_profile_id: Optional[str] = None

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
    expenses: Optional[List["TripExpenseOut"]] = []
    expense_summary: Optional["TripExpenseSummary"] = None


class ChecklistAIAction(BaseModel):
    type: str
    items: List[str]


class ChecklistAICommandRequest(BaseModel):
    command: str = Field(..., min_length=2, max_length=500)
    language: str = "ru"
    command_context: Optional[Dict[str, Any]] = None


class ChecklistAICommandResponse(BaseModel):
    applied: bool
    recognized_action_request: bool = False
    message: str
    actions: List[ChecklistAIAction] = []
    checklist: ChecklistOut
    command_context: Optional[Dict[str, Any]] = None


class AssistantPlanProposal(BaseModel):
    proposal_id: str
    event_date: date
    time: Optional[str] = None
    title: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    place_source: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    travel_buffer_minutes: Optional[int] = Field(default=None, ge=0, le=480)
    event_type: Optional[str] = None
    day_part: Optional[str] = None
    reason: Optional[str] = None
    weather_note: Optional[str] = None
    image: Optional[str] = None
    image_position: Optional[str] = None
    intensity: Optional[str] = Field(default=None, pattern="^(light|balanced|rich)$")
    requires_confirmation: bool = False
    risk_level: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")
    display_time_window: Optional[str] = None


class PackingRecommendation(BaseModel):
    item: str
    priority: str = Field(..., pattern="^(must|nice|optional)$")
    reason: str
    reason_tags: List[str] = []
    suggested_action: str = Field(..., pattern="^(add|remove|move_to_carry_on|keep)$")
    target_section: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=1, le=99)
    requires_confirmation: bool = False
    risk_level: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")


class AssistantDailyBrief(BaseModel):
    title: str = ""
    weather: Optional[str] = None
    plan: List[str] = []
    packing: List[str] = []
    expenses: Optional[str] = None
    warnings: List[str] = []


class AssistantAskResponse(BaseModel):
    answer: str
    suggestions: List[str] = []
    plan_proposals: List[AssistantPlanProposal] = []
    event_change_proposals: List["AssistantEventChangeProposal"] = []
    expense_proposals: List["AssistantExpenseProposal"] = []
    packing_recommendations: List[PackingRecommendation] = []
    daily_brief: Optional[AssistantDailyBrief] = None
    command_context: Optional[Dict[str, Any]] = None


class AssistantPlanApplyRequest(BaseModel):
    proposals: List[AssistantPlanProposal] = Field(default_factory=list, min_length=1, max_length=10)


class AssistantPlanApplyResponse(BaseModel):
    applied_count: int
    created_event_ids: List[int] = []
    checklist: ChecklistOut


class AssistantEventChangeProposal(BaseModel):
    proposal_id: str
    action: str = Field(..., pattern="^(update|delete|create)$")
    target_event_id: Optional[int] = None
    event_date: Optional[date] = None
    time: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    reason: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    requires_confirmation: bool = False
    risk_level: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")


class AssistantEventChangesApplyRequest(BaseModel):
    proposals: List[AssistantEventChangeProposal] = Field(default_factory=list, min_length=1, max_length=10)


class AssistantEventChangesApplyResponse(BaseModel):
    applied_count: int
    created_event_ids: List[int] = []
    updated_event_ids: List[int] = []
    deleted_event_ids: List[int] = []
    checklist: ChecklistOut


class AssistantPackingApplyRequest(BaseModel):
    recommendations: List[PackingRecommendation] = Field(default_factory=list, min_length=1, max_length=20)
    language: str = "ru"


class AssistantPackingApplyResponse(BaseModel):
    applied_count: int
    actions: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    checklist: ChecklistOut


class TripExpenseBase(BaseModel):
    expense_date: Optional[date] = None
    title: str = Field(..., min_length=1, max_length=160)
    category: str = Field(default="other", min_length=1, max_length=64)
    amount: float = Field(..., ge=0)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    note: Optional[str] = Field(default=None, max_length=800)


class TripExpenseCreate(TripExpenseBase):
    pass


class TripExpenseUpdate(BaseModel):
    expense_date: Optional[date] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    category: Optional[str] = Field(default=None, min_length=1, max_length=64)
    amount: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    note: Optional[str] = Field(default=None, max_length=800)


class TripExpenseOut(TripExpenseBase):
    id: int
    checklist_id: int
    created_by_user_id: Optional[int] = None
    amount_base: float
    base_currency: str
    fx_rate: float
    fx_rate_date: Optional[str] = None
    fx_provider: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TripExpenseSettingsUpdate(BaseModel):
    budget_amount: Optional[float] = Field(default=None, ge=0)
    daily_budget_amount: Optional[float] = Field(default=None, ge=0)
    base_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)


class TripExpenseSummary(BaseModel):
    budget_amount: Optional[float] = None
    daily_budget_amount: Optional[float] = None
    base_currency: str = "RUB"
    total_spent: float = 0
    remaining: Optional[float] = None
    today_spent: float = 0
    today_remaining: Optional[float] = None
    by_category: Dict[str, float] = Field(default_factory=dict)
    expense_count: int = 0


class TripExpenseListResponse(BaseModel):
    expenses: List[TripExpenseOut] = []
    summary: TripExpenseSummary
    checklist: Optional[ChecklistOut] = None


class AssistantExpenseProposal(BaseModel):
    proposal_id: str
    action: str = Field(..., pattern="^(create|set_budget|set_daily_budget)$")
    title: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "RUB"
    expense_date: Optional[date] = None
    note: Optional[str] = None
    budget_amount: Optional[float] = None
    daily_budget_amount: Optional[float] = None
    base_currency: Optional[str] = None
    split_count: Optional[int] = Field(default=None, ge=1, le=50)
    requires_confirmation: bool = False
    risk_level: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")


class AssistantExpenseApplyRequest(BaseModel):
    proposals: List[AssistantExpenseProposal] = Field(default_factory=list, min_length=1, max_length=10)


class AssistantExpenseApplyResponse(BaseModel):
    applied_count: int
    created_expense_ids: List[int] = []
    checklist: ChecklistOut


class AssistantRestaurantSearchRequest(BaseModel):
    anchor_event_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    event_date: Optional[date] = None
    time: Optional[str] = None
    day_part: Optional[str] = "day"
    meal_type: Optional[str] = None
    radius_meters: int = Field(default=1200, ge=250, le=3000)
    limit: int = Field(default=5, ge=1, le=8)
    language: str = "ru"


class AssistantRestaurantOption(BaseModel):
    option_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    distance_meters: Optional[int] = None
    lat: float
    lng: float
    source: str = "geoapify"
    map_url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class AssistantRestaurantOptionsResponse(BaseModel):
    options: List[AssistantRestaurantOption] = []
    anchor_event_id: Optional[int] = None
    anchor_title: Optional[str] = None
    event_date: Optional[date] = None
    time: Optional[str] = None
    day_part: Optional[str] = "day"
    provider: str = "geoapify"
    attribution: Optional[str] = None
    configured: bool = True
    message: Optional[str] = None


class AssistantRestaurantApplyRequest(BaseModel):
    option: AssistantRestaurantOption
    event_date: date
    time: Optional[str] = None
    day_part: Optional[str] = "day"
    anchor_event_id: Optional[int] = None


class AssistantRestaurantApplyResponse(BaseModel):
    created_event_id: int
    checklist: ChecklistOut


ChecklistOut.model_rebuild()
AssistantAskResponse.model_rebuild()
TripExpenseListResponse.model_rebuild()
AssistantExpenseApplyResponse.model_rebuild()
AssistantRestaurantOptionsResponse.model_rebuild()
AssistantRestaurantApplyResponse.model_rebuild()

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
