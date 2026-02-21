import os
from datetime import datetime, timedelta
from urllib.parse import quote as url_quote
import httpx
from fastapi import FastAPI, Query, Depends, HTTPException, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import time
import asyncio
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
import crud, models, schemas
from database import SessionLocal, async_engine
from typing import List, Optional
from auth import (
    verify_password, create_access_token,
    get_current_user, require_current_user,
    get_db as auth_get_db,
)

load_dotenv()


# Open-Meteo API (бесплатный, без ключа)
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
from translations import WMO_CODES, get_item, get_category_map

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://luggify.vercel.app",
        "https://www.luggify.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Словарь переводов погодных условий


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
            raise HTTPException(status_code=503, detail=f"Ошибка подключения к базе данных: {str(e)}")

class PackingRequest(BaseModel):
    city: str
    start_date: str
    end_date: str
    trip_type: str = "vacation"  # vacation, business, active, beach, winter
    gender: str = "unisex"       # male, female, unisex
    transport: str = "plane"     # plane, train, car, bus
    traveling_with_pet: bool = False
    has_allergies: bool = False
    has_chronic_diseases: bool = False
    language: str = "ru"

class TripSegment(BaseModel):
    city: str
    start_date: str
    end_date: str
    trip_type: str = "vacation"
    transport: str = "plane"

class MultiCityPackingRequest(BaseModel):
    segments: List[TripSegment]
    gender: str = "unisex"
    traveling_with_pet: bool = False
    has_allergies: bool = False
    has_chronic_diseases: bool = False
    language: str = "ru"

class ChecklistResponse(schemas.ChecklistOut):
    daily_forecast: list[schemas.DailyForecast]

class StatsResponse(BaseModel):
    total_trips: int
    total_days: int
    unique_cities: int
    unique_countries: int
    upcoming_trips: int

class ChecklistStateUpdate(BaseModel):
    checked_items: Optional[List[str]] = None
    removed_items: Optional[List[str]] = None
    added_items: Optional[List[str]] = None
    is_public: Optional[bool] = None

class UserPrivacyUpdate(BaseModel):
    is_stats_public: bool

class ChecklistPrivacyUpdate(BaseModel):
    is_public: bool

# ==================== AUTH ENDPOINTS ====================

@app.post("/auth/register", response_model=schemas.Token)
async def register(data: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя"""
    # Проверяем уникальность email
    existing = await crud.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    # Проверяем уникальность username
    existing = await crud.get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    # Создаём пользователя
    user = await crud.create_user(db, data)
    # Генерируем токен
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user),
    }


@app.post("/auth/login", response_model=schemas.Token)
async def login(data: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    """Авторизация пользователя"""
    user = await crud.get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user),
    }


@app.get("/auth/me", response_model=schemas.UserOut)
async def get_me(user=Depends(require_current_user)):
    """Получение профиля текущего пользователя"""
    return user


@app.post("/auth/telegram", response_model=schemas.Token)
async def telegram_auth(data: schemas.TelegramAuth, db: AsyncSession = Depends(get_db)):
    """Авторизация через Telegram — автосоздание пользователя при первом входе"""
    user = await crud.get_user_by_tg_id(db, data.tg_id)
    if not user:
        # Создаём нового пользователя из Telegram-данных
        user = await crud.create_user_from_telegram(
            db,
            tg_id=data.tg_id,
            username=data.username,
            first_name=data.first_name,
        )
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user),
    }


@app.patch("/auth/privacy", response_model=schemas.UserOut)
async def update_privacy(
    privacy: UserPrivacyUpdate,
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Обновление настроек приватности пользователя"""
    user.is_stats_public = privacy.is_stats_public
    await db.commit()
    await db.refresh(user)
    return user


@app.get("/users/{username}", response_model=dict)
async def get_public_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user)  # Optional, to check friend status later
):
    """Публичный профиль пользователя"""
    user = await crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Получаем чеклисты
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    public_checklists = [
        schemas.ChecklistOut.model_validate(c) 
        for c in checklists 
        if c.is_public
    ]

    stats = None
    if user.is_stats_public:
        # Считаем статистику для публичного профиля (только по публичным чеклистам? 
        # Или полную, если user разрешил? Обычно полную, но флаг 'is_stats_public' это и значит)
        
        # Лучше считать полную статистику, раз пользователь разрешил её показывать
        stats = {
            "total_trips": len(checklists),
            "total_days": sum((c.end_date - c.start_date).days + 1 for c in checklists if c.start_date and c.end_date),
            "unique_cities": len({c.city.split(",")[0].strip() for c in checklists if c.city}),
            "unique_countries": len({c.city.split(",")[-1].strip() for c in checklists if c.city and "," in c.city}),
            "upcoming_trips": sum(1 for c in checklists if c.start_date and c.start_date > datetime.now().date())
        }

    return {
        "username": user.username,
        "created_at": user.created_at,
        "is_stats_public": user.is_stats_public,
        "stats": stats,
        "checklists": public_checklists
    }


@app.get("/my-checklists", response_model=List[schemas.ChecklistOut])
async def get_my_checklists(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получение всех чеклистов текущего пользователя"""
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    return checklists


# === Feature: Gamification (Achievements + Levels) ===

ACHIEVEMENTS = [
    {"id": "first_step", "icon": "🎒", "name_ru": "Первый шаг", "name_en": "First Step",
     "desc_ru": "Создайте первый чеклист", "desc_en": "Create your first checklist"},
    {"id": "explorer", "icon": "🧭", "name_ru": "Исследователь", "name_en": "Explorer",
     "desc_ru": "Совершите 3 поездки", "desc_en": "Complete 3 trips"},
    {"id": "globetrotter", "icon": "🌍", "name_ru": "Глобус-троттер", "name_en": "Globetrotter",
     "desc_ru": "Совершите 10 поездок", "desc_en": "Complete 10 trips"},
    {"id": "multi_city", "icon": "🗺", "name_ru": "Мультигород", "name_en": "Multi-City",
     "desc_ru": "Создайте маршрут из нескольких городов", "desc_en": "Create a multi-city route"},
    {"id": "snowbird", "icon": "❄️", "name_ru": "Снежок", "name_en": "Snowbird",
     "desc_ru": "Поездка при температуре ниже 0°C", "desc_en": "Trip with temperature below 0°C"},
    {"id": "beach_lover", "icon": "🏖", "name_ru": "Пляжник", "name_en": "Beach Lover",
     "desc_ru": "Поездка при температуре выше 25°C", "desc_en": "Trip with temperature above 25°C"},
    {"id": "marathoner", "icon": "🏃", "name_ru": "Марафонец", "name_en": "Marathoner",
     "desc_ru": "Суммарно более 30 дней в поездках", "desc_en": "More than 30 days of travel total"},
    {"id": "cosmopolitan", "icon": "🌐", "name_ru": "Космополит", "name_en": "Cosmopolitan",
     "desc_ru": "Побывайте в 5+ странах", "desc_en": "Visit 5+ countries"},
    {"id": "list_keeper", "icon": "📋", "name_ru": "Хранитель списков", "name_en": "List Keeper",
     "desc_ru": "Создайте более 20 чеклистов", "desc_en": "Create more than 20 checklists"},
]

LEVELS = [
    {"name_ru": "Новичок", "name_en": "Novice", "icon": "🌱", "min": 0, "max": 2},
    {"name_ru": "Путешественник", "name_en": "Traveler", "icon": "✈️", "min": 3, "max": 5},
    {"name_ru": "Эксперт", "name_en": "Expert", "icon": "🏅", "min": 6, "max": 7},
    {"name_ru": "Легенда", "name_en": "Legend", "icon": "👑", "min": 8, "max": 9},
]

def compute_achievements(checklists):
    """Вычисляет ачивки на основе чеклистов пользователя"""
    total = len(checklists)
    total_days = 0
    countries = set()
    has_multi_city = False
    has_cold = False
    has_hot = False

    for c in checklists:
        if c.start_date and c.end_date:
            days = (c.end_date - c.start_date).days + 1
            if days > 0:
                total_days += days
        if c.city and "+" in c.city:
            has_multi_city = True
        if c.city and "," in c.city:
            countries.add(c.city.split(",")[-1].strip())
        if c.avg_temp is not None:
            if c.avg_temp < 0:
                has_cold = True
            if c.avg_temp > 25:
                has_hot = True

    unlocked = []
    if total >= 1: unlocked.append("first_step")
    if total >= 3: unlocked.append("explorer")
    if total >= 10: unlocked.append("globetrotter")
    if has_multi_city: unlocked.append("multi_city")
    if has_cold: unlocked.append("snowbird")
    if has_hot: unlocked.append("beach_lover")
    if total_days > 30: unlocked.append("marathoner")
    if len(countries) >= 5: unlocked.append("cosmopolitan")
    if total > 20: unlocked.append("list_keeper")

    # Determine progress for each
    results = []
    for a in ACHIEVEMENTS:
        is_unlocked = a["id"] in unlocked
        progress = 0
        if a["id"] == "first_step":
            progress = min(total, 1)
        elif a["id"] == "explorer":
            progress = min(total / 3, 1)
        elif a["id"] == "globetrotter":
            progress = min(total / 10, 1)
        elif a["id"] == "multi_city":
            progress = 1 if has_multi_city else 0
        elif a["id"] == "snowbird":
            progress = 1 if has_cold else 0
        elif a["id"] == "beach_lover":
            progress = 1 if has_hot else 0
        elif a["id"] == "marathoner":
            progress = min(total_days / 30, 1)
        elif a["id"] == "cosmopolitan":
            progress = min(len(countries) / 5, 1)
        elif a["id"] == "list_keeper":
            progress = min(total / 20, 1)

        results.append({
            **a,
            "unlocked": is_unlocked,
            "progress": round(progress, 2)
        })

    # Level
    unlocked_count = len(unlocked)
    level = LEVELS[0]
    for lv in LEVELS:
        if unlocked_count >= lv["min"]:
            level = lv

    return {"achievements": results, "level": level, "unlocked_count": unlocked_count}


@app.get("/my-achievements")
async def get_my_achievements(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Достижения и уровень пользователя"""
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    return compute_achievements(checklists)


# === Feature: Feedback Stats ===

@app.get("/my-feedback-stats")
async def get_my_feedback_stats(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Статистика предпочтений: что чаще удаляют/добавляют"""
    checklists = await crud.get_checklists_by_user_id(db, user.id)

    removed_counts = {}
    added_counts = {}

    for c in checklists:
        for item in (c.removed_items or []):
            removed_counts[item] = removed_counts.get(item, 0) + 1
        for item in (c.added_items or []):
            added_counts[item] = added_counts.get(item, 0) + 1

    top_removed = sorted(removed_counts.items(), key=lambda x: -x[1])[:10]
    top_added = sorted(added_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "top_removed": [{"item": k, "count": v} for k, v in top_removed],
        "top_added": [{"item": k, "count": v} for k, v in top_added],
    }


@app.get("/my-stats", response_model=StatsResponse)
async def get_my_stats(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Статистика путешествий пользователя"""
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    
    total_trips = len(checklists)
    total_days = 0
    cities = set()
    countries = set()
    upcoming = 0
    today = datetime.now().date()
    
    for c in checklists:
        # Дни
        if c.start_date and c.end_date:
            days = (c.end_date - c.start_date).days + 1
            if days > 0:
                total_days += days
        
        # Города и Страны
        if c.city:
            cities.add(c.city.split(",")[0].strip()) # Только имя города
            if "," in c.city:
                countries.add(c.city.split(",")[-1].strip())
            else:
                # Если страна не указана явно, считаем город уникальным местом
                pass
        
        # Предстоящие
        if c.start_date and c.start_date > today:
            upcoming += 1
            
    return {
        "total_trips": total_trips,
        "total_days": total_days,
        "unique_cities": len(cities),
        "unique_countries": len(countries),
        "upcoming_trips": upcoming
    }


# === Feature: Calendar Export (.ics) ===

@app.get("/checklist/{slug}/calendar")
async def export_checklist_calendar(slug: str, db: AsyncSession = Depends(get_db)):
    """Экспорт чеклиста в .ics формат для добавления в календарь"""
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    
    # Format items for description
    items_text = "\\n".join(f"- {item}" for item in (checklist.items or []))
    city = checklist.city or "Trip"
    start = checklist.start_date.strftime("%Y%m%d")
    end = (checklist.end_date + timedelta(days=1)).strftime("%Y%m%d")  # iCal end is exclusive
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Luggify//Trip Planner//EN
BEGIN:VEVENT
DTSTART;VALUE=DATE:{start}
DTEND;VALUE=DATE:{end}
SUMMARY:🧳 {city}
DESCRIPTION:Чеклист Luggify:\\n{items_text}
DTSTAMP:{now}
UID:{slug}@luggify.app
END:VEVENT
END:VCALENDAR"""
    
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="luggify-{slug}.ics"'}
    )


# === Feature: Attractions (Curated + Wikipedia) ===

ATTRACTIONS_CACHE = {}
ATTRACTIONS_LOCKS = {}


# Топ достопримечательности для популярных городов (en.wikipedia article titles)
_CURATED = {
    "Paris": ["Eiffel Tower","Louvre","Notre-Dame de Paris","Arc de Triomphe","Sacré-Cœur, Paris","Musée d'Orsay","Palace of Versailles","Champs-Élysées","Panthéon, Paris","Sainte-Chapelle","Centre Pompidou","Les Invalides","Place de la Concorde","Palais Garnier","Pont Alexandre III"],
    "London": ["Tower of London","Buckingham Palace","British Museum","London Eye","Big Ben","Tower Bridge","Westminster Abbey","St Paul's Cathedral","Hyde Park, London","Trafalgar Square","Natural History Museum, London","Tate Modern","Palace of Westminster","Kensington Palace","Hampton Court Palace"],
    "Rome": ["Colosseum","Pantheon, Rome","Trevi Fountain","Roman Forum","Vatican Museums","St. Peter's Basilica","Sistine Chapel","Piazza Navona","Spanish Steps","Castel Sant'Angelo","Borghese Gallery","Piazza Venezia","Palatine Hill","Basilica di Santa Maria Maggiore","Aventine Hill"],
    "New York City": ["Statue of Liberty","Central Park","Empire State Building","Times Square","Brooklyn Bridge","Metropolitan Museum of Art","One World Trade Center","Rockefeller Center","Grand Central Terminal","High Line","Museum of Modern Art","Fifth Avenue","Broadway (Manhattan)","Wall Street","Chelsea Market"],
    "Tokyo": ["Sensō-ji","Meiji Shrine","Tokyo Skytree","Tokyo Tower","Shibuya Crossing","Imperial Palace, Tokyo","Shinjuku Gyoen","Ueno Park","Akihabara","Odaiba","Roppongi Hills","Harajuku","Ginza","Asakusa","Tsukiji fish market"],
    "Istanbul": ["Hagia Sophia","Blue Mosque","Topkapi Palace","Grand Bazaar","Basilica Cistern","Galata Tower","Dolmabahçe Palace","Süleymaniye Mosque","Bosphorus","Spice Bazaar","Maiden's Tower","Taksim Square","Istiklal Avenue","Chora Church","Pierre Loti"],
    "Barcelona": ["Sagrada Família","Park Güell","Casa Batlló","La Rambla, Barcelona","Casa Milà","Gothic Quarter, Barcelona","Camp Nou","Palau de la Música Catalana","Barcelona Cathedral","Magic Fountain of Montjuïc","Barceloneta","Montjuïc","Tibidabo","Port Vell","Picasso Museum (Barcelona)"],
    "Berlin": ["Brandenburg Gate","Berlin Wall","Reichstag building","Museum Island","Checkpoint Charlie","East Side Gallery","Berlin Cathedral","Alexanderplatz","Berlin Television Tower","Charlottenburg Palace","Pergamon Museum","Tiergarten","Potsdamer Platz","Victory Column (Berlin)","Holocaust memorial (Berlin)"],
    "Dubai": ["Burj Khalifa","Palm Jumeirah","Dubai Mall","Burj Al Arab","Dubai Marina","Dubai Fountain","Museum of the Future","Gold Souk","Dubai Frame","Jumeirah Mosque","Mall of the Emirates","Al Fahidi Historical Neighbourhood","Dubai Creek","Miracle Garden","Global Village"],
    "Moscow": ["Red Square","Moscow Kremlin","Saint Basil's Cathedral","Bolshoi Theatre","Moscow Metro","Tretyakov Gallery","Cathedral of Christ the Saviour","Arbat Street","GUM (department store)","Gorky Park (Moscow)","Sparrow Hills","Novodevichy Convent","VDNKh","Pushkin Museum","Kolomenskoye"],
    "Saint Petersburg": ["Hermitage Museum","Church of the Savior on Blood","Peter and Paul Fortress","Saint Isaac's Cathedral","Peterhof Palace","Winter Palace","Nevsky Prospect","Mariinsky Theatre","Catherine Palace","Russian Museum","Palace Square","Kazan Cathedral, Saint Petersburg","Summer Garden","Bronze Horseman","Alexander Column"],
    "Prague": ["Charles Bridge","Prague Castle","Old Town Square (Prague)","Prague astronomical clock","St. Vitus Cathedral","Wenceslas Square","Dancing House","Lennon Wall","Petřín","Powder Tower","Josefov","Vyšehrad","National Museum (Prague)","Municipal House (Prague)","Old Jewish Cemetery, Prague"],
    "Amsterdam": ["Rijksmuseum","Anne Frank House","Van Gogh Museum","Royal Palace of Amsterdam","Dam Square","Vondelpark","Jordaan","Heineken Experience","Magere Brug","Westerkerk","NEMO (museum)","Stedelijk Museum Amsterdam","Bloemenmarkt","Museumplein","Begijnhof, Amsterdam"],
    "Vienna": ["Schönbrunn Palace","St. Stephen's Cathedral, Vienna","Hofburg","Belvedere, Vienna","Vienna State Opera","Kunsthistorisches Museum","Prater","Naschmarkt","Austrian Parliament Building","Albertina","MuseumsQuartier","Rathaus, Vienna","Ringstraße","Graben, Vienna","Vienna Secession"],
    "Bangkok": ["Grand Palace (Bangkok)","Wat Arun","Wat Pho","Khao San Road","Temple of the Emerald Buddha","Jim Thompson House","Lumpini Park","Erawan Shrine","Chatuchak Weekend Market","Chinatown, Bangkok","Asiatique The Riverfront","Wat Saket","MBK Center","Siam Paragon","Floating market"],
    "Beijing": ["Forbidden City","Great Wall of China","Temple of Heaven","Summer Palace","Tiananmen Square","Ming tombs","Beihai Park","Lama Temple","798 Art District","Jingshan Park","Hutong","National Museum of China","Dashilan","Olympic Green","Drum Tower of Beijing"],
    "Sydney": ["Sydney Opera House","Sydney Harbour Bridge","Bondi Beach","Darling Harbour","Taronga Zoo","Royal Botanic Garden, Sydney","Circular Quay","The Rocks, Sydney","Manly Beach","Sydney Tower","Art Gallery of New South Wales","Luna Park Sydney","Barangaroo","Museum of Contemporary Art Australia","Paddy's Markets"],
    "Cairo": ["Great Pyramid of Giza","Egyptian Museum","Great Sphinx of Giza","Khan el-Khalili","Cairo Citadel","Al-Azhar Mosque","Mosque of Muhammad Ali","Cairo Tower","Coptic Cairo","Al-Muizz Street","Tahrir Square","Baron Empain Palace","Hanging Church (Cairo)","Giza pyramid complex","Museum of Islamic Art, Cairo"],
    "Singapore": ["Marina Bay Sands","Gardens by the Bay","Merlion","Sentosa","Singapore Zoo","Orchard Road","Singapore Botanic Gardens","Chinatown, Singapore","Clarke Quay","Little India, Singapore","ArtScience Museum","Raffles Hotel","Esplanade – Theatres on the Bay","National Gallery Singapore","Singapore Flyer"],
    "Athens": ["Acropolis of Athens","Parthenon","Ancient Agora of Athens","Erechtheion","Plaka","Monastiraki","Syntagma Square","Panathenaic Stadium","Acropolis Museum","Temple of Hephaestus","Lycabettus","National Archaeological Museum, Athens","Hadrian's Arch (Athens)","Temple of Olympian Zeus, Athens","Odeon of Herodes Atticus"],
    "Lisbon": ["Belém Tower","Jerónimos Monastery","Praça do Comércio","Alfama","Santa Justa Lift","São Jorge Castle","Tram 28 (Lisbon)","Pastéis de Belém","Ponte 25 de Abril","LX Factory","Oceanário de Lisboa","Pantheon of Portugal","Time Out Market","Bairro Alto","Rossio"],
    "Budapest": ["Hungarian Parliament Building","Buda Castle","Széchenyi thermal bath","Fisherman's Bastion","Chain Bridge (Budapest)","St. Stephen's Basilica (Budapest)","Heroes' Square (Budapest)","Matthias Church","Margaret Island","Great Market Hall (Budapest)","Citadella","Gellért thermal bath","Dohány Street Synagogue","Andrássy Avenue","Vajdahunyad Castle"],
    "Warsaw": ["Royal Castle, Warsaw","Old Town Market Place, Warsaw","Wilanów Palace","Palace of Culture and Science","Łazienki Park","Warsaw Uprising Museum","St. John's Archcathedral, Warsaw","Copernicus Science Centre","National Museum, Warsaw","Saxon Garden","Sigismund's Column","Warsaw Barbican","POLIN Museum","Warsaw Old Town","Belweder"],
    "Madrid": ["Royal Palace of Madrid","Prado Museum","Retiro Park","Puerta del Sol","Plaza Mayor, Madrid","Reina Sofía","Thyssen-Bornemisza Museum","Temple of Debod","Gran Vía","Almudena Cathedral","Santiago Bernabéu Stadium","Cibeles Palace","Royal Botanical Garden of Madrid","Plaza de Cibeles","Puerta de Alcalá"],
    "Milan": ["Milan Cathedral","Galleria Vittorio Emanuele II","Santa Maria delle Grazie","Sforza Castle","Pinacoteca di Brera","La Scala","Navigli","San Siro","Basilica of Sant'Ambrogio","Piazza del Duomo, Milan","Quadrilatero della moda","Cimitero Monumentale di Milano","Pinacoteca Ambrosiana","Arco della Pace","Piazza Mercanti"],
    "Munich": ["Marienplatz","Nymphenburg Palace","Englischer Garten","BMW Welt","Frauenkirche, Munich","Deutsches Museum","Viktualienmarkt","Munich Residenz","Allianz Arena","Hofbräuhaus","Alte Pinakothek","Olympiapark, Munich","Asamkirche","St. Peter's Church, Munich","Karlsplatz"],
    "Florence": ["Florence Cathedral","Uffizi","Ponte Vecchio","Palazzo Pitti","Piazzale Michelangelo","Galleria dell'Accademia","Palazzo Vecchio","Piazza della Signoria","Boboli Gardens","Basilica of Santa Croce, Florence","Basilica of San Lorenzo, Florence","Bargello","Baptistery of Saint John (Florence)","Basilica di Santa Maria Novella","Piazza della Repubblica, Florence"],
    "Edinburgh": ["Edinburgh Castle","Royal Mile","Arthur's Seat","Holyrood Palace","Scott Monument","Calton Hill","National Museum of Scotland","St Giles' Cathedral","Princes Street","Edinburgh Old Town","Greyfriars Kirkyard","Royal Botanic Garden Edinburgh","Camera Obscura, Edinburgh","Edinburgh Zoo","Dean Village"],
    "Copenhagen": ["Tivoli Gardens","The Little Mermaid (statue)","Nyhavn","Amalienborg","Christiansborg Palace","Rosenborg Castle","Strøget","Christiania (district)","Round Tower (Copenhagen)","National Museum of Denmark","Church of Our Saviour, Copenhagen","Ny Carlsberg Glyptotek","Frederiksberg Garden","Kastellet, Copenhagen","Copenhagen Opera House"],
    "Oslo": ["Oslo Opera House","Vigeland sculpture park","Viking Ship Museum (Oslo)","Akershus Fortress","Holmenkollbakken","Munch Museum","Oslo City Hall","Royal Palace, Oslo","Aker Brygge","Karl Johans gate","Norsk Folkemuseum","Bygdøy","Oslo Cathedral","National Gallery (Oslo)","Fram Museum"],
    "Stockholm": ["Vasa Museum","Gamla stan","Stockholm Palace","Stockholm City Hall","Skansen","ABBA The Museum","Djurgården","Drottningholm Palace","Storkyrkan","Moderna Museet","Fotografiska","Nobel Prize Museum","Stadshuset","Södermalm","Stortorget, Stockholm"],
    "Helsinki": ["Helsinki Cathedral","Suomenlinna","Temppeliaukio Church","Senate Square, Helsinki","Sibelius Monument","Ateneum","Uspenski Cathedral","Market Square, Helsinki","Esplanadi","Kiasma","Oodi","Helsinki Olympic Stadium","Seurasaari","Hakaniemi Market Hall","Kaivopuisto"],
    "Zurich": ["Grossmünster","Lake Zurich","Bahnhofstrasse","Fraumünster","Old Town, Zurich","Swiss National Museum","Kunsthaus Zürich","Lindenhof hill, Zurich","Zurich Zoo","Uetliberg","FIFA World Football Museum","St. Peter, Zurich","Zürichsee","Pavillon Le Corbusier","Botanical Garden of the University of Zurich"],
    "Porto": ["Livraria Lello","Clérigos Tower","Dom Luís I Bridge","Ribeira, Porto","São Bento railway station","Porto Cathedral","Palácio da Bolsa","Crystal Palace Gardens","Serralves","Igreja do Carmo (Porto)","Foz do Douro","Majestic Café","Church of São Francisco (Porto)","Jardim do Morro","Port wine"],
    "Dubrovnik": ["Walls of Dubrovnik","Stradun (street)","Dubrovnik Cable Car","Rector's Palace, Dubrovnik","Lokrum","Fort Lovrijenac","Sponza Palace","Pile Gate","Dominican Monastery, Dubrovnik","Banje Beach","Franciscan Church and Monastery, Dubrovnik","Dubrovnik Cathedral","Trsteno Arboretum","Buža Bar","Orlando's Column, Dubrovnik"],
    "Krakow": ["Wawel Castle","Main Market Square, Kraków","Cloth Hall, Kraków","St. Mary's Basilica, Kraków","Kazimierz","Auschwitz concentration camp","Wieliczka Salt Mine","Wawel Cathedral","Planty Park","Schindler's Factory","Collegium Maius","Barbican of Kraków","Floriańska Street","National Museum in Kraków","Kościuszko Mound"],
    "Seoul": ["Gyeongbokgung","Bukchon Hanok Village","N Seoul Tower","Myeongdong","Changdeokgung","Dongdaemun Design Plaza","Gwanghwamun","Insadong","Lotte World Tower","War Memorial of Korea","Namdaemun Market","Jogyesa","Cheonggyecheon","Itaewon","COEX Mall"],
    "Hong Kong": ["Victoria Peak","Victoria Harbour","Star Ferry","Tian Tan Buddha","Wong Tai Sin Temple","Avenue of Stars, Hong Kong","Temple Street Night Market","Hong Kong Disneyland","Ngong Ping 360","Man Mo Temple","Repulse Bay","Lan Kwai Fong","Chi Lin Nunnery","Ladies' Market","Ocean Park Hong Kong"],
    "Kuala Lumpur": ["Petronas Towers","Batu Caves","KL Tower","Merdeka Square, Kuala Lumpur","Petaling Street","Islamic Arts Museum Malaysia","Sultan Abdul Samad Building","Thean Hou Temple","Perdana Botanical Garden","National Mosque of Malaysia","Central Market, Kuala Lumpur","Aquaria KLCC","Bukit Bintang","National Museum of Malaysia","Istana Negara, Jalan Istana"],
    "Hanoi": ["Hoan Kiem Lake","Temple of Literature, Hanoi","Ho Chi Minh Mausoleum","Old Quarter (Hanoi)","One Pillar Pagoda","Vietnam Museum of Ethnology","Hoa Lo Prison","Long Biên Bridge","West Lake (Hanoi)","Hanoi Opera House","St. Joseph's Cathedral, Hanoi","Tran Quoc Pagoda","Imperial Citadel of Thăng Long","Ngoc Son Temple","Dong Xuan Market"],
    "Delhi": ["Red Fort","India Gate","Humayun's Tomb","Qutub Minar","Lotus Temple","Jama Masjid, Delhi","Akshardham (Delhi)","Raj Ghat","Chandni Chowk","Rashtrapati Bhavan","Connaught Place","Gurudwara Bangla Sahib","Lodhi Garden","Purana Qila","Jantar Mantar, New Delhi"],
    "Mumbai": ["Gateway of India","Chhatrapati Shivaji Maharaj Terminus","Marine Drive, Mumbai","Elephanta Caves","Haji Ali Dargah","Siddhivinayak Temple","Bandra–Worli Sea Link","Chhatrapati Shivaji Maharaj Vastu Sangrahalaya","Colaba Causeway","Juhu Beach","Dharavi","Banganga Tank","Mani Bhavan","Crawford Market","Flora Fountain"],
    "Los Angeles": ["Hollywood Sign","Griffith Observatory","Getty Center","Hollywood Walk of Fame","Santa Monica Pier","Universal Studios Hollywood","Venice Beach, Los Angeles","The Broad","Los Angeles County Museum of Art","TCL Chinese Theatre","Walt Disney Concert Hall","Rodeo Drive","Sunset Boulevard","Dodger Stadium","Natural History Museum of Los Angeles County"],
    "San Francisco": ["Golden Gate Bridge","Alcatraz Island","Fisherman's Wharf, San Francisco","Lombard Street","Chinatown, San Francisco","Palace of Fine Arts","Pier 39","Cable car (railway)","Golden Gate Park","Painted ladies","Coit Tower","Ghirardelli Square","Twin Peaks (San Francisco)","San Francisco Museum of Modern Art","Exploratorium"],
    "Chicago": ["Millennium Park","Cloud Gate","Art Institute of Chicago","Willis Tower","Navy Pier","Magnificent Mile","Chicago Riverwalk","Field Museum of Natural History","Wrigley Field","Museum of Science and Industry (Chicago)","Grant Park (Chicago)","John Hancock Center","Buckingham Fountain","Lincoln Park Zoo","Water Tower (Chicago)"],
    "Toronto": ["CN Tower","Royal Ontario Museum","Distillery District","Ripley's Aquarium of Canada","Art Gallery of Ontario","St. Lawrence Market","Casa Loma","Toronto Islands","Nathan Phillips Square","Kensington Market, Toronto","High Park","Hockey Hall of Fame","Harbourfront Centre","Dundas Square","Bata Shoe Museum"],
    "Mexico City": ["Zócalo","Palacio de Bellas Artes","National Museum of Anthropology","Chapultepec","Coyoacán","Frida Kahlo Museum","Templo Mayor","Basilica of Our Lady of Guadalupe","Paseo de la Reforma","Xochimilco","National Palace (Mexico)","Palace of Chapultepec","Torre Latinoamericana","Angel of Independence","Ciudad Universitaria"],
    "Rio de Janeiro": ["Christ the Redeemer","Sugarloaf Mountain","Copacabana","Ipanema","Maracanã Stadium","Escadaria Selarón","Santa Teresa, Rio de Janeiro","Tijuca National Park","Lapa, Rio de Janeiro","Jardim Botânico, Rio de Janeiro","Museum of Tomorrow","Arcos da Lapa","Pedra da Gávea","Praia Vermelha","Parque Lage"],
    "Buenos Aires": ["Plaza de Mayo","Casa Rosada","La Boca","Recoleta Cemetery","Teatro Colón","Obelisco de Buenos Aires","San Telmo, Buenos Aires","Puerto Madero","Palermo, Buenos Aires","Caminito","Museo Nacional de Bellas Artes","Avenida 9 de Julio","Floralis Genérica","Palacio Barolo","El Ateneo Grand Splendid"],
    "Cape Town": ["Table Mountain","Robben Island","V&A Waterfront","Cape of Good Hope","Kirstenbosch National Botanical Garden","Boulders Beach","Bo-Kaap","Cape Point","Chapman's Peak","District Six Museum","Castle of Good Hope","Camps Bay","Constantia (Cape Town)","Groot Constantia","Two Oceans Aquarium"],
    "Marrakech": ["Djemaa el-Fna","Bahia Palace","Majorelle Garden","Koutoubia","Saadian Tombs","Ben Youssef Madrasa","Menara gardens","El Badi Palace","Marrakech Museum","Mouassine Mosque","Dar Si Said Museum","Tanneries of Marrakech","Agdal Gardens","Bab Agnaou","Le Jardin Secret"],
    "Melbourne": ["Federation Square","Royal Botanic Gardens, Melbourne","Melbourne Cricket Ground","Flinders Street Station","National Gallery of Victoria","Queen Victoria Market","Hosier Lane","Melbourne Museum","St Paul's Cathedral, Melbourne","Eureka Tower","Brighton Bathing Boxes","Melbourne Zoo","Luna Park, Melbourne","State Library of Victoria","Great Ocean Road"],
    "Kazan": ["Kazan Kremlin","Qolşärif Mosque","Temple of All Religions","Bauman Street","Kazan Cathedral (Kazan)","Kazan Arena","Kazan Family Center","Millennium Bridge (Kazan)","National Museum of the Republic of Tatarstan","Palace of Farmers","Söyembikä Tower","Riviera Aquapark","Kazan Kremlin Annunciation Cathedral","Tatar Academic State Opera and Ballet Theatre","Old Tatar Quarter"],
    "Sochi": ["Sochi Olympic Park","Rosa Khutor","Sochi Park","Krasnaya Polyana","Skypark AJ Hackett Sochi","Fisht Olympic Stadium","Akhun Mountain","Riviera Park (Sochi)","Sochi Art Museum","Dagomys Tea Plantation","Stalin's dacha","Sochi Arboretum","Orekhovsky Waterfall","Sochi Discovery World Aquarium","Agura Waterfalls"],
}


@app.get("/attractions")
async def get_attractions(
    city: str = Query(...),
    lang: str = Query("ru"),
    limit: int = Query(10),
):
    """Достопримечательности: кураторский список + Wikipedia для перевода и фото"""
    cache_key = (city.strip().lower(), lang, limit)

    if cache_key in ATTRACTIONS_CACHE:
        cached_data, cached_at = ATTRACTIONS_CACHE[cache_key]
        if time.time() - cached_at < 86400 * 7:
            return {"attractions": cached_data}

    if cache_key not in ATTRACTIONS_LOCKS:
        ATTRACTIONS_LOCKS[cache_key] = asyncio.Lock()

    async with ATTRACTIONS_LOCKS[cache_key]:
        if cache_key in ATTRACTIONS_CACHE:
            cached_data, cached_at = ATTRACTIONS_CACHE[cache_key]
            if time.time() - cached_at < 86400 * 7:
                return {"attractions": cached_data}

        try:
            wiki_headers = {"User-Agent": "LuggifyBot/1.0 (hello@luggify.app)"}
            target_lang = lang if lang in ("ru", "en", "de", "fr", "es", "it") else "en"
            en_wiki = "https://en.wikipedia.org/w/api.php"

            async with httpx.AsyncClient(timeout=30) as client:
                city_name = city.split(",")[0].strip()

                # ── 1. Определяем английское название города ──
                en_city = city_name
                if target_lang != "en":
                    try:
                        target_wiki = f"https://{target_lang}.wikipedia.org/w/api.php"
                        ll_resp = await client.get(target_wiki, params={
                            "action": "query", "titles": city_name,
                            "prop": "langlinks", "lllang": "en",
                            "lllimit": 1, "format": "json"
                        }, headers=wiki_headers)
                        for pid, page in ll_resp.json().get("query", {}).get("pages", {}).items():
                            lls = page.get("langlinks", [])
                            if lls:
                                en_city = lls[0].get("*", city_name)
                    except Exception:
                        pass

                # ── 2. Берём список достопримечательностей ──
                en_titles = _CURATED.get(en_city, [])[:limit]

                # Фолбэк: поиск через Wikipedia категории
                if not en_titles:
                    try:
                        for cat in [
                            f"Category:Tourist attractions in {en_city}",
                            f"Category:Museums in {en_city}",
                            f"Category:Landmarks in {en_city}",
                        ]:
                            cr = await client.get(en_wiki, params={
                                "action": "query", "list": "categorymembers",
                                "cmtitle": cat, "cmlimit": 30,
                                "cmtype": "page|subcat", "format": "json"
                            }, headers=wiki_headers)
                            for m in cr.json().get("query", {}).get("categorymembers", []):
                                name = m["title"].replace("Category:", "") if m.get("ns") == 14 else m["title"]
                                if not name.lower().startswith("list of"):
                                    en_titles.append(name)
                        en_titles = en_titles[:limit]
                    except Exception:
                        pass

                if not en_titles:
                    return {"attractions": []}

                # ── 3. Батчевый перевод названий ──
                translations = {}  # en_title -> local_title
                if target_lang != "en":
                    for i in range(0, len(en_titles), 50):
                        chunk = en_titles[i:i+50]
                        try:
                            tr = await client.get(en_wiki, params={
                                "action": "query", "titles": "|".join(chunk),
                                "prop": "langlinks", "lllang": target_lang,
                                "lllimit": "max", "redirects": 1, "format": "json"
                            }, headers=wiki_headers)
                            for pid, pd in tr.json().get("query", {}).get("pages", {}).items():
                                if int(pid) > 0:
                                    lls = pd.get("langlinks", [])
                                    if lls:
                                        translations[pd["title"]] = lls[0]["*"]
                        except Exception:
                            pass

                # ── 4. Собираем результат с картинками ──
                results = []
                for en_title in en_titles:
                    local_name = translations.get(en_title, en_title)
                    image_url = None

                    # Картинка из Wikipedia
                    for wiki_title, wlang in [(local_name, target_lang), (en_title, "en")]:
                        if image_url:
                            break
                        try:
                            sr = await client.get(
                                f"https://{wlang}.wikipedia.org/api/rest_v1/page/summary/{url_quote(wiki_title)}",
                                headers=wiki_headers
                            )
                            if sr.status_code == 200:
                                image_url = sr.json().get("thumbnail", {}).get("source")
                        except Exception:
                            pass

                    results.append({
                        "name": local_name,
                        "image": image_url,
                        "link": f"https://www.google.com/search?q={url_quote(local_name)}",
                    })

                if results:
                    ATTRACTIONS_CACHE[cache_key] = (results, time.time())

                return {"attractions": results}
        except Exception as e:
            print(f"Attractions error: {e}")
            return {"attractions": []}


# === Feature: Flight Search (Travelpayouts) ===
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "")

@app.get("/flights/search")
async def search_flights(
    destination: str = Query(..., description="City name"),
    date: str = Query(None, description="YYYY-MM-DD departure"),
    return_date: str = Query(None, description="YYYY-MM-DD return"),
    origin: str = Query(None, description="Origin city name"),
):
    """Поиск дешёвых авиабилетов через Travelpayouts API"""
    if not TRAVELPAYOUTS_TOKEN:
        return {"flights": [], "error": "API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get IATA code for destination
            iata_resp = await client.get(
                "https://autocomplete.travelpayouts.com/places2",
                params={"term": destination.split(",")[0].strip(), "locale": "ru", "types[]": "city"}
            )
            dest_code = ""
            if iata_resp.status_code == 200 and iata_resp.json():
                dest_code = iata_resp.json()[0].get("code", "")

            if not dest_code:
                return {"flights": []}

            # Get IATA code for origin (if provided)
            origin_code = ""
            if origin:
                origin_resp = await client.get(
                    "https://autocomplete.travelpayouts.com/places2",
                    params={"term": origin.split(",")[0].strip(), "locale": "ru", "types[]": "city"}
                )
                if origin_resp.status_code == 200 and origin_resp.json():
                    origin_code = origin_resp.json()[0].get("code", "")

            # Search cheap flights
            params = {
                "destination": dest_code,
                "token": TRAVELPAYOUTS_TOKEN,
                "currency": "rub",
                "limit": 10,
            }
            def format_date_for_url(d_str: str) -> str:
                if not d_str or len(d_str) < 10: return ""
                parts = d_str.split("-")
                return f"{parts[2]}{parts[1]}"

            url_depart = format_date_for_url(date)
            url_return = format_date_for_url(return_date)

            generic_link = f"https://www.aviasales.ru/search/{origin_code}{url_depart}{dest_code}{url_return}1"

            # Helper: выбрать самый дешёвый и самый быстрый рейс
            def pick_best_flights(raw_flights, f_origin_default, f_dest_default, flight_type):
                if not raw_flights:
                    return []
                
                parsed = []
                for f in raw_flights:
                    f_origin = f.get("origin", f_origin_default)
                    f_dest = f.get("destination", f_dest_default)
                    
                    api_link = f.get("link")
                    if api_link:
                        link = f"https://www.aviasales.ru{api_link}"
                    else:
                        link = f"https://www.aviasales.ru/search/{f_origin}{url_depart}{f_dest}{url_return}1"
                    
                    duration = f.get("duration_to") or f.get("duration") or 0
                    
                    parsed.append({
                        "price": f.get("price") or f.get("value") or 999999,
                        "airline": f.get("airline"),
                        "departure_at": f.get("departure_at"),
                        "origin": f_origin,
                        "destination": f_dest,
                        "transfers": f.get("transfers", 0),
                        "duration": duration,
                        "link": link,
                        "type": flight_type,
                    })
                
                if len(parsed) == 1:
                    parsed[0]["tag"] = "Самый дешёвый"
                    return parsed
                
                results = []
                # 1. Самый дешёвый
                cheapest = min(parsed, key=lambda x: x["price"])
                cheapest_copy = dict(cheapest)
                cheapest_copy["tag"] = "Самый дешёвый"
                results.append(cheapest_copy)
                
                # 2. Самый быстрый (другой рейс)
                others = [f for f in parsed if f is not cheapest]
                with_duration = [f for f in others if f["duration"] > 0]
                if with_duration:
                    fastest = min(with_duration, key=lambda x: x["duration"])
                    fastest_copy = dict(fastest)
                    fastest_copy["tag"] = "Самый быстрый"
                    results.append(fastest_copy)
                elif others:
                    alt = min(others, key=lambda x: x["transfers"])
                    alt_copy = dict(alt)
                    alt_copy["tag"] = "Меньше пересадок"
                    results.append(alt_copy)
                
                return results

            # 1. OUTBOUND FLIGHTS
            out_params = {
                "destination": dest_code,
                "token": TRAVELPAYOUTS_TOKEN,
                "currency": "rub",
                "limit": 30,
            }
            if origin_code: out_params["origin"] = origin_code
            if date: out_params["departure_at"] = date
            
            outbound = []
            try:
                out_resp = await client.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates", params=out_params)
                if out_resp.status_code == 200:
                    raw = out_resp.json().get("data") or []
                    outbound = pick_best_flights(raw, origin_code, dest_code, "outbound")
            except Exception: pass

            # 2. INBOUND FLIGHTS
            inbound = []
            if return_date and dest_code:
                # Определяем пункт назначения для обратного рейса
                inbound_dest = origin_code
                if not inbound_dest and outbound:
                    # Используем origin из найденного outbound рейса
                    inbound_dest = outbound[0].get("origin", "")
                
                in_params = {
                    "origin": dest_code,
                    "token": TRAVELPAYOUTS_TOKEN,
                    "currency": "rub",
                    "limit": 30,
                    "departure_at": return_date,
                }
                if inbound_dest:
                    in_params["destination"] = inbound_dest
                
                try:
                    in_resp = await client.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates", params=in_params)
                    if in_resp.status_code == 200:
                        raw = in_resp.json().get("data") or []
                        inbound = pick_best_flights(raw, dest_code, inbound_dest or "", "inbound")
                except Exception: pass

            return {"flights": outbound + inbound, "destination_code": dest_code, "generic_link": generic_link}
    except Exception as e:
        print(f"Flights error: {e}")
        return {"flights": []}


# === Feature: Hotel Search (RapidAPI Booking.com) ===

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

@app.get("/hotels/search")
async def search_hotels(
    city: str = Query(...),
    check_in: str = Query(None, description="YYYY-MM-DD"),
    check_out: str = Query(None, description="YYYY-MM-DD"),
):
    """Поиск отелей через бесплатный RapidAPI Booking.com (или mock пока нет ключа)"""
    city_name = city.split(",")[0].strip()

    # Если ключа нет, возвращаем mock-данные (заглушки) чтобы UI не был пустым
    if not RAPIDAPI_KEY:
        print("No RAPIDAPI_KEY found, returning MOCK hotes data.")
        return {
            "hotels": [
                {
                    "name": f"Grand Hotel {city_name}",
                    "stars": 5,
                    "price_per_night": 12500,
                    "rating": 9.2,
                    "link": f"https://www.booking.com/searchresults.ru.html?ss={city_name}",
                },
                {
                    "name": f"City Center Apartments",
                    "stars": 4,
                    "price_per_night": 4500,
                    "rating": 8.7,
                    "link": f"https://www.booking.com/searchresults.ru.html?ss={city_name}",
                },
                {
                    "name": f"Budget Hostel {city_name}",
                    "stars": 2,
                    "price_per_night": 1200,
                    "rating": 7.5,
                    "link": f"https://www.booking.com/searchresults.ru.html?ss={city_name}",
                }
            ],
            "error": "RAPIDAPI_KEY not configured. Showing mock data."
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
            }
            
            # 1. Сначала нужно получить dest_id города
            loc_resp = await client.get(
                "https://booking-com.p.rapidapi.com/v1/hotels/locations",
                headers=headers,
                params={"name": city_name, "locale": "ru"}
            )
            
            if loc_resp.status_code != 200:
                return {"hotels": []}
                
            locations = loc_resp.json()
            if not locations:
                return {"hotels": []}
                
            dest_id = locations[0].get("dest_id")
            dest_type = locations[0].get("dest_type")

            # 2. Ищем отели
            # Если даты не переданы, ставим завтрашний день
            from datetime import timedelta
            t_check_in = check_in or (datetime.date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
            t_check_out = check_out or (datetime.date.today() + timedelta(days=3)).strftime("%Y-%m-%d")

            search_resp = await client.get(
                "https://booking-com.p.rapidapi.com/v1/hotels/search",
                headers=headers,
                params={
                    "dest_id": dest_id,
                    "dest_type": dest_type,
                    "checkin_date": t_check_in,
                    "checkout_date": t_check_out,
                    "adults_number": "1",
                    "room_number": "1",
                    "units": "metric",
                    "locale": "ru",
                    "currency": "RUB"
                }
            )
            
            if search_resp.status_code != 200:
                return {"hotels": []}

            results = search_resp.json().get("result", [])
            hotels = []
            
            for h in results[:6]:
                hotels.append({
                    "name": h.get("hotel_name", ""),
                    "stars": int(h.get("class", 0)),
                    "price_per_night": h.get("min_total_price"),
                    "rating": h.get("review_score"),
                    "link": h.get("url", f"https://www.booking.com/searchresults.ru.html?ss={city_name}"),
                })

            return {"hotels": hotels}
    except Exception as e:
        print(f"Hotels error: {e}")
        return {"hotels": []}


async def get_weather_forecast_data(city: str, start_date: datetime.date, end_date: datetime.date, language: str = "ru") -> List[schemas.DailyForecast]:
    """Helper to fetch weather forecast for a checklist (used when viewing saved checklists)"""
    async with httpx.AsyncClient() as client:
        # 1. Geocoding
        headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
        try:
            geo_resp = await client.get(NOMINATIM_URL, params={
                "q": city.split(",")[0].strip(),
                "format": "json",
                "accept-language": "ru",
                "limit": 1,
            }, headers=headers)
            if geo_resp.status_code != 200:
                return []
            geo_data = geo_resp.json()
            if not geo_data:
                return []
            
            lat = float(geo_data[0]["lat"])
            lon = float(geo_data[0]["lon"])
        except Exception:
            return []

        # Dates setup
        # start_date/end_date passed as date objects
        today = datetime.now().date()
        forecast_limit = today + timedelta(days=15)
        
        daily_data = {}

        # 2. Forecast (Open-Meteo)
        if start_date <= forecast_limit:
            forecast_end = min(end_date, forecast_limit)
            try:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                    "timezone": "auto",
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": forecast_end.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    for i, t in enumerate(times):
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        daily_data[t] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "forecast"
                        }
            except Exception:
                pass

        # 3. Historical (if needed)
        hist_start = max(start_date, forecast_limit + timedelta(days=1))
        if hist_start <= end_date:
            try:
                # Use last year data
                hist_start_ly = hist_start.replace(year=hist_start.year - 1)
                hist_end_ly = end_date.replace(year=end_date.year - 1)
                
                resp = await client.get(OPEN_METEO_HISTORICAL_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                    "timezone": "auto",
                    "start_date": hist_start_ly.strftime("%Y-%m-%d"),
                    "end_date": hist_end_ly.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    
                    # Compute invalid year diff to map back to requested dates
                    # But simpler: just iterate and map to hist_start + i days
                    current_hist_date = hist_start
                    for i, _ in enumerate(times):
                        if current_hist_date > end_date: break
                        
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        date_str = current_hist_date.strftime("%Y-%m-%d")
                        daily_data[date_str] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "historical"
                        }
                        current_hist_date += timedelta(days=1)
            except Exception:
                pass

        # Convert to list
        result = []
        for date_str in sorted(daily_data.keys()):
            item = daily_data[date_str]
            result.append(schemas.DailyForecast(
                date=date_str,
                temp_min=item["temp_min"],
                temp_max=item["temp_max"],
                condition=item["condition"],
                icon=item["icon"],
                source=item.get("source", "forecast"),
                city=item.get("city"),
                humidity=item.get("humidity"),
                uv_index=item.get("uv_index"),
                wind_speed=item.get("wind_speed")
            ))
        return result


@app.get("/geo/cities-autocomplete")
async def autocomplete_cities(namePrefix: str = Query(..., min_length=2)):
    """
    Гибридный автокомплит: Open-Meteo (быстро, короткие префиксы) + Nominatim (точность, полные названия).
    Объединяет результаты, убирает дубликаты.
    """
    results_open_meteo = []
    results_nominatim = []

    async def fetch_open_meteo():
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": namePrefix, "count": 5, "language": "ru", "format": "json"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if "results" in data:
                        return data["results"]
        except Exception:
            pass
        return []

    async def fetch_nominatim():
        # Используем featuretype=city чтобы отсеять мусор, но это параметр reverse. 
        # Для search используем ограничение по addressdetails, но Nominatim всё равно возвращает разное.
        # Просто запрашиваем и потом фильтруем на клиенте (тут).
        params = {
            "q": namePrefix,
            "format": "json",
            "accept-language": "ru",
            "limit": 5,
            "addressdetails": 1,
        }
        headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return []

    # Запускаем параллельно
    import asyncio
    res_om, res_nom = await asyncio.gather(fetch_open_meteo(), fetch_nominatim())

    final_results = []
    seen = set()

    # 1. Приоритет Open-Meteo (обычно релевантнее для префиксов)
    for item in res_om:
        city = item.get("name")
        country = item.get("country_code", "").upper()
        country_name = item.get("country", "")
        admin1 = item.get("admin1")
        
        # Фикс для "Молотов" -> "Пермь" (если вдруг API возвращает старое название)
        # Но массово это не исправить, надеемся на Nominatim
        
        key = f"{city}:{country}:{admin1}"
        if key in seen: continue
        seen.add(key)

        parts = [city]
        if admin1 and admin1 != city: parts.append(admin1)
        if country_name: parts.append(country_name)
        
        final_results.append({
            "name": city,
            "country": country,
            "country_name": country_name,
            "admin1": admin1,
            "lat": item.get("latitude"),
            "lon": item.get("longitude"),
            "fullName": ", ".join(parts),
            "source": "om"
        })

    # 2. Добавляем Nominatim (если такого города ещё нет)
    for item in res_nom:
        addr = item.get("address", {})
        # Извлекаем город
        city = addr.get("city") or addr.get("town") or addr.get("village") or item.get("name")
        if not city: continue
        
        country = addr.get("country_code", "").upper()
        country_name = addr.get("country", "")
        admin1 = addr.get("state", "")

        # Пропускаем, если название совсем не похоже на запрос (Nominatim иногда ищет по улицам)
        # if namePrefix.lower() not in city.lower(): continue # Слишком строго

        key = f"{city}:{country}:{admin1}"
        
        # Nominatim часто возвращает дубли
        if key in seen: continue
        
        # Если такого ключа нет, но координаты ОЧЕНЬ близко к уже найденному -> тоже дубль
        is_duplicate_coord = False
        lat, lon = float(item["lat"]), float(item["lon"])
        for exist in final_results:
            if abs(exist["lat"] - lat) < 0.1 and abs(exist["lon"] - lon) < 0.1:
                is_duplicate_coord = True
                break
        
        if is_duplicate_coord: continue

        seen.add(key)
        
        parts = [city]
        if admin1 and admin1 != city: parts.append(admin1)
        if country_name: parts.append(country_name)

        final_results.append({
            "name": city,
            "country": country,
            "country_name": country_name,
            "admin1": admin1,
            "lat": lat,
            "lon": lon,
            "fullName": ", ".join(parts),
            "source": "nom"
        })

    return final_results

async def calculate_packing_data(
    city: str,
    start_date_str: str,
    end_date_str: str,
    trip_type: str,
    transport: str,
    gender: str,
    traveling_with_pet: bool,
    has_allergies: bool,
    has_chronic_diseases: bool,
    language: str = "ru"
):
    # 1. Geocoding
    async with httpx.AsyncClient() as client:
        headers = {"User-Agent": "Luggify/1.0"}
        try:
            geo_resp = await client.get(NOMINATIM_URL, params={
                "q": city.split(",")[0].strip(),
                "format": "json",
                "accept-language": language,
                "limit": 1,
                "addressdetails": 1
            }, headers=headers)
            if geo_resp.status_code != 200 or not geo_resp.json():
                raise HTTPException(status_code=404, detail=f"Город {city} не найден")
            geo_data = geo_resp.json()
        except Exception as e:
            print(f"Geocoding error for {city}: {e}")
            raise HTTPException(status_code=404, detail=f"Ошибка БД: 404: Город {city} не найден ({str(e)})")

        lat = float(geo_data[0]["lat"])
        lon = float(geo_data[0]["lon"])
        addr = geo_data[0].get("address", {})
        country = addr.get("country_code", "").upper()

        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        today = datetime.now().date()

        forecast_limit = today + timedelta(days=15)
        daily_data = {}

        # 1) Open-Meteo Forecast
        if start_dt.date() <= forecast_limit:
            forecast_end = min(end_dt.date(), forecast_limit)
            try:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode,relative_humidity_2m_mean,uv_index_max,wind_speed_10m_max",
                    "timezone": "auto",
                    "start_date": start_dt.strftime("%Y-%m-%d"),
                    "end_date": forecast_end.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    hums = d.get("relative_humidity_2m_mean", [])
                    uvs = d.get("uv_index_max", [])
                    winds = d.get("wind_speed_10m_max", [])
                    
                    for i, t in enumerate(times):
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language if language in WMO_CODES else "ru", {}).get(codes[i], (default_desc, "01d"))
                        daily_data[t] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "forecast",
                            "city": city.split(",")[0].strip(),
                            "humidity": hums[i] if i < len(hums) else None,
                            "uv_index": uvs[i] if i < len(uvs) else None,
                            "wind_speed": winds[i] if i < len(winds) else None,
                        }

            except Exception as e:
                print(f"Forecast error: {e}")

        # 2) Historical
        hist_start = max(start_dt.date(), forecast_limit + timedelta(days=1))
        if hist_start <= end_dt.date():
            try:
                hist_start_ly = hist_start.replace(year=hist_start.year - 1)
                hist_end_ly = end_dt.date().replace(year=end_dt.date().year - 1)
                
                resp = await client.get(OPEN_METEO_HISTORICAL_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode,relative_humidity_2m_mean,wind_speed_10m_max",
                    "timezone": "auto",
                    "start_date": hist_start_ly.strftime("%Y-%m-%d"),
                    "end_date": hist_end_ly.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    hums = d.get("relative_humidity_2m_mean", [])
                    winds = d.get("wind_speed_10m_max", [])
                    
                    current_hist_date = hist_start
                    for i, _ in enumerate(times):
                        if current_hist_date > end_dt.date(): break
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        date_str = current_hist_date.strftime("%Y-%m-%d")
                        daily_data[date_str] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "historical",
                            "city": city.split(",")[0].strip(), # Add city
                            "humidity": hums[i] if i < len(hums) else None,
                            "uv_index": None,
                            "wind_speed": winds[i] if i < len(winds) else None,
                        }
                        current_hist_date += timedelta(days=1)
            except Exception as e:
                print(f"Historical error: {e}")

    # Process weather data
    daily_forecast = []
    temps = []
    conditions = set()
    wmo_codes = set()
    humidities = []
    uv_indices = []
    wind_speeds = []

    for date_str in sorted(daily_data.keys()):
        item = daily_data[date_str]
        daily_forecast.append(schemas.DailyForecast(
            date=date_str,
            temp_min=item["temp_min"],
            temp_max=item["temp_max"],
            condition=item["condition"],
            icon=item["icon"],
            source=item.get("source", "forecast"),
            city=item.get("city"),
            humidity=item.get("humidity"),
            uv_index=item.get("uv_index"),
            wind_speed=item.get("wind_speed")
        ))
        temps.append((item["temp_min"] + item["temp_max"]) / 2)
        conditions.add(item["condition"])
        wmo_codes.add(item["weathercode"])
        if item["humidity"]: humidities.append(item["humidity"])
        if item["uv_index"]: uv_indices.append(item["uv_index"])
        if item["wind_speed"]: wind_speeds.append(item["wind_speed"])

    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    
    # Items Generation
    items = set()

    # Weather based items
    if hums := [h for h in humidities if h > 80]:
         items.add(get_item("styling", language))
    if uvs := [u for u in uv_indices if u > 5]:
         items.update([get_item("sunscreen_50", language), get_item("hat", language), get_item("sunglasses", language)])
    if winds := [w for w in wind_speeds if w > 30]:
         items.update([get_item("windbreaker", language), get_item("chapstick", language), get_item("scarf_buff", language)])

    if any("swim" in c.lower() or "купание" in c.lower() for c in conditions) or country in ["TH", "ES", "GR", "IT", "TR", "EG"]:
        items.add(get_item("swimsuit", language))
    if any("mountain" in c.lower() or "гора" in c.lower() for c in conditions):
        items.update([get_item("trekking_shoes", language), get_item("first_aid_kit", language), get_item("thermos", language), get_item("map_compass", language)])

    if has_allergies:
        items.update([get_item("antihistamine", language), get_item("allergies_list", language)])
    if has_chronic_diseases:
        items.update([get_item("meds_personal", language), get_item("meds_regular", language), get_item("med_report", language)])

    if gender == "female":
        items.update([get_item("makeup", language), get_item("hygiene_fem", language), get_item("makeup_remover", language)])
        if avg_temp and avg_temp > 15:
            items.add(get_item("dress", language))
    elif gender == "male":
        items.add(get_item("shaving_kit", language))

    if transport == "plane":
        items.update([get_item("neck_pillow", language), get_item("earplugs", language), get_item("powerbank_hand", language), get_item("liquids_bag", language)])
    elif transport == "train":
        items.update([get_item("slippers_train", language), get_item("mug", language), get_item("powerbank", language), get_item("clothes_train", language), get_item("wipes", language)])
    elif transport == "car":
        items.update([get_item("license", language), get_item("car_charger", language), get_item("snacks_water", language), get_item("playlist", language), get_item("sunglasses_driver", language)])
    elif transport == "bus":
        items.update([get_item("neck_pillow", language), get_item("earplugs", language), get_item("snacks_water", language), get_item("wipes", language)])

    # Basic items based on categories logic (simplified/deduplicated logic from categories map)
    # We will return the raw set of items, and let the caller categorize if needed, or better yet, category logic should be here too?
    # Actually, the caller re-categorizes everything. So we just need to return `items` set, plus weather info.
    
    # ... Wait, the category mapping in `generate_list` had logic for clothes based on temp.
    # We need that logic here.
    
    min_temp = min(daily_data[d]["temp_min"] for d in daily_data) if daily_data else 15
    max_temp = max(daily_data[d]["temp_max"] for d in daily_data) if daily_data else 20
    
    if min_temp < 0:
        items.update([get_item("jacket_warm", language), get_item("hat", language), get_item("scarf", language), get_item("gloves", language), get_item("thermo", language), get_item("boots_winter", language), get_item("socks_warm", language)])
    elif min_temp < 10:
        items.update([get_item("jacket_light", language), get_item("sweater", language), get_item("jeans", language), get_item("sneakers", language)])
    elif max_temp > 20:
        items.update([get_item("tshirt", language), get_item("shorts", language), get_item("cap", language), get_item("shoes_light", language)])
    else:
        items.update([get_item("tshirt", language), get_item("jeans", language), get_item("sneakers", language)])
        
    if any("rain" in c.lower() or "дождь" in c.lower() for c in conditions):
        items.update([get_item("raincoat", language), get_item("shoes_waterproof", language)])
    if max_temp > 22:
        items.update([get_item("sunglasses", language), get_item("cap", language)])
    if max_temp > 20:
        items.add(get_item("water_bottle", language))
        
    if traveling_with_pet:
        items.update([get_item("vet_passport", language), get_item("pet_food", language), get_item("pet_bowl", language), get_item("leash", language), get_item("pet_pads", language), get_item("pet_toy", language)])

    if trip_type == "business":
        items.update([get_item("suit", language), get_item("shirts", language), get_item("shoes_formal", language), get_item("laptop", language), get_item("business_cards", language)])
    elif trip_type == "active":
        items.update([get_item("sportswear", language), get_item("sneakers", language), get_item("backpack_walk", language), get_item("water_bottle", language)])
    elif trip_type == "beach":
        items.update([get_item("swimsuit", language), get_item("pareo", language), get_item("flipflops", language), get_item("beach_towel", language), get_item("after_sun", language), get_item("beach_bag", language), get_item("sunscreen", language)])
    elif trip_type == "winter":
        items.update([get_item("ski_suit", language), get_item("thermo", language), get_item("fleece", language), get_item("mittens", language), get_item("goggles", language), get_item("wind_cream", language)])

    # Visa/Adapter logic
    visa_countries = ["FR", "DE", "IT", "ES", "GB", "US", "CN", "JP", "TR", "EG", "TH", "IN"] # Shortened list for brevity, ideally reuse full list
    if country in visa_countries:
        items.add(get_item("visa", language))
    
    adapter_countries = ["US", "GB", "AU", "JP", "CN", "CH"]
    if country in adapter_countries:
        items.add(get_item("adapter", language))

    return {
        "items": items,
        "avg_temp": avg_temp,
        "conditions": list(conditions),
        "daily_forecast": daily_forecast,
        "country": country,
        "start_date": start_dt.date(),
        "end_date": end_dt.date()
    }

async def create_checklist_from_items(db, items, city, start_date, end_date, avg_temp, conditions, daily_forecast, user_id=None, language="ru"):
    # Categorization logic
    mapping = get_category_map(language)
    categories = {k: [] for k in mapping.keys()}
    
    # Always add essentials
    items.update([get_item("passport", language), get_item("insurance", language), get_item("money", language), get_item("tickets", language), get_item("booking", language)])
    
    for item in items:
        found = False
        for cat, keywords in mapping.items():
            if any(k.lower() in item.lower() for k in keywords):
                categories[cat].append(item)
                found = True
                break
        if not found:
            categories["Прочее"].append(item)

    for k in categories:
        categories[k] = list(sorted(set(categories[k])))
        
    all_items = []
    for k, v in categories.items():
        all_items.extend(v)

    checklist_data = schemas.ChecklistCreate(
        city=city,
        start_date=start_date,
        end_date=end_date,
        items=all_items,
        avg_temp=avg_temp,
        conditions=sorted(list(conditions)),
        daily_forecast=[schemas.DailyForecast(**d) if isinstance(d, dict) else d for d in daily_forecast] if daily_forecast else None,
        user_id=user_id,
    )
    checklist = await crud.create_checklist(db, checklist_data)
    
    # Return ChecklistResponse with daily_forecast
    return ChecklistResponse(
        slug=checklist.slug,
        city=checklist.city,
        start_date=checklist.start_date,
        end_date=checklist.end_date,
        items=all_items,
        avg_temp=checklist.avg_temp,
        conditions=checklist.conditions,
        checked_items=checklist.checked_items,
        removed_items=checklist.removed_items,
        added_items=checklist.added_items,
        tg_user_id=checklist.tg_user_id,
        user_id=checklist.user_id,
        is_public=getattr(checklist, 'is_public', True),
        daily_forecast=daily_forecast
    )

@app.post("/generate-packing-list", response_model=ChecklistResponse)
async def generate_list(req: PackingRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await calculate_packing_data(
        req.city, req.start_date, req.end_date, req.trip_type, req.transport,
        req.gender, req.traveling_with_pet, req.has_allergies, req.has_chronic_diseases, req.language
    )
    return await create_checklist_from_items(
        db, data["items"], req.city, data["start_date"], data["end_date"],
        data["avg_temp"], data["conditions"], data["daily_forecast"],
        current_user.id if current_user else None,
        language=req.language
    )

@app.post("/generate-multi-city", response_model=ChecklistResponse)
async def generate_multi_city(req: MultiCityPackingRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    all_items = set()
    all_forecast = []
    temps = []
    conditions = set()
    cities = []
    
    for seg in req.segments:
        cities.append(seg.city.split(",")[0])
        data = await calculate_packing_data(
            seg.city, seg.start_date, seg.end_date, seg.trip_type, seg.transport,
            req.gender, req.traveling_with_pet, req.has_allergies, req.has_chronic_diseases, req.language
        )
        all_items.update(data["items"])
        all_forecast.extend(data["daily_forecast"])
        if data["avg_temp"]: temps.append(data["avg_temp"])
        conditions.update(data["conditions"])
    
    # Sort forecast by date
    all_forecast.sort(key=lambda x: x.date)
    
    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    display_city = " + ".join(cities)
    
    # Parse dates for main checklist
    min_date = datetime.strptime(req.segments[0].start_date, "%Y-%m-%d").date()
    max_date = datetime.strptime(req.segments[-1].end_date, "%Y-%m-%d").date()
    
    return await create_checklist_from_items(
        db, all_items, display_city, min_date, max_date,
        avg_temp, list(conditions), all_forecast,
        current_user.id if current_user else None,
        language=req.language
    )

@app.post("/save-tg-checklist", response_model=schemas.ChecklistOut)
async def save_tg_checklist(data: schemas.ChecklistCreate = Body(...), db: AsyncSession = Depends(get_db)):
    if not data.tg_user_id:
        raise HTTPException(status_code=400, detail="Не передан tg_user_id")
    checklist = await crud.save_or_update_tg_checklist(db, data)
    return checklist

@app.get("/tg-checklist/{tg_user_id}", response_model=schemas.ChecklistOut)
async def get_tg_checklist(tg_user_id: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_tg_user_id(db, tg_user_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден для пользователя")
    return checklist

@app.get("/tg-checklists/{tg_user_id}", response_model=List[schemas.ChecklistOut])
async def get_tg_checklists(tg_user_id: str, db: AsyncSession = Depends(get_db)):
    checklists = await crud.get_all_checklists_by_tg_user_id(db, tg_user_id)
    return checklists

@app.get("/checklist/{slug}", response_model=ChecklistResponse)
async def get_checklist(slug: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    # If daily_forecast is saved in DB, use it. Otherwise try to fetch fresh one (optional fallback)
    forecast = checklist.daily_forecast
    if not forecast:
        # Fallback to fresh fetch if missing (for legacy checklists)
        try:
            forecast = await get_weather_forecast_data(checklist.city, checklist.start_date, checklist.end_date, language="ru")
        except:
            forecast = []
    
    return ChecklistResponse(
        slug=checklist.slug,
        city=checklist.city,
        start_date=checklist.start_date,
        end_date=checklist.end_date,
        items=checklist.items,
        avg_temp=checklist.avg_temp,
        conditions=checklist.conditions,
        checked_items=checklist.checked_items or [],
        removed_items=checklist.removed_items or [],
        added_items=checklist.added_items or [],
        tg_user_id=checklist.tg_user_id,
        user_id=checklist.user_id,
        is_public=getattr(checklist, 'is_public', True),
        daily_forecast=forecast
    )

    # Категории для чеклиста (для фронта)
    # --- Распределение по категориям (копия логики из generate_list) ---
    mapping = {
        "Важное": ["Паспорт", "Медицинская страховка", "Деньги/карта", "Виза", "Билеты", "Бронь отеля", "Водительское удостоверение/СТС", "Ветпаспорт"],
        "Документы": ["Список аллергенов", "Медзаключение", "Личные рецепты"],
        "Одежда": ["куртка", "пуховик", "Термобельё", "Шапка", "Шарф", "Перчатки", "ботинки", "носки", "Свитер", "толстовка", "Джинсы", "брюки", "Кроссовки", "кофта", "свитшот", "Футболки", "Шорты", "платья", "Панама", "кепка", "очки", "Обувь", "Дождевик", "Зонт", "Купальник", "плавки", "туника", "парео", "Шлёпанцы", "Костюм", "Рубашки", "блузки", "Туфли", "юбка"],
        "Гигиена": ["Зубная", "Паста", "Дезодорант", "Мыло", "Расчёска", "Косметика", "макияж", "Влажные салфетки", "Бритвенный набор", "Антиперспирант"],
        "Техника": ["Телефон", "Зарядка", "Пауэрбанк", "Power bank", "Переходник", "Ноутбук", "Наушники"],
        "Аптечка": ["лекарства", "Пластыри", "Обезболивающее", "Антигистаминные"],
        "Прочее": ["Бутылка", "Термос", "рюкзак", "Сумка", "Крем", "Снеки", "Плейлист", "Подушка", "Беруши", "маска", "Жидкости", "Тапочки", "Кружка", "Миска", "Поводок", "переноска", "Пелёнки", "пакеты", "Игрушка", "Визитки"]
    }

    # Инициализация
    categories = {k: [] for k in mapping.keys()}

    for item in checklist.items:
        found = False
        for cat, keywords in mapping.items():
            if any(k.lower() in item.lower() for k in keywords):
                categories[cat].append(item)
                found = True
                break
        
        if not found:
            categories["Прочее"].append(item)
    # Убираем дубли
    for k in categories:
        categories[k] = list(dict.fromkeys(categories[k]))

    return {
        "slug": checklist.slug,
        "city": checklist.city,
        "start_date": checklist.start_date,
        "end_date": checklist.end_date,
        "items": checklist.items,
        "items_by_category": categories,
        "avg_temp": checklist.avg_temp,
        "conditions": checklist.conditions,
    }

@app.patch("/checklist/{slug}/state", response_model=schemas.ChecklistOut)
async def update_checklist_state(slug: str, state: ChecklistStateUpdate = Body(...), db: AsyncSession = Depends(get_db)):
    checklist = await crud.update_checklist_state(
        db,
        slug,
        checked_items=state.checked_items,
        removed_items=state.removed_items,
        added_items=state.added_items,
        items=state.items,
    )
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    return checklist


@app.patch("/checklist/{slug}/privacy", response_model=schemas.ChecklistOut)
async def update_checklist_privacy(
    slug: str,
    privacy: ChecklistPrivacyUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    """Обновление приватности чеклиста"""
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    
    # Проверка прав (только владелец)
    if checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет прав")

    checklist.is_public = privacy.is_public
    await db.commit()
    await db.refresh(checklist)
    return checklist


@app.delete("/checklist/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(slug: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    await db.delete(checklist)
    await db.commit()
    return

@app.get("/")
async def root():
    return {"message": "Luggify backend is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint - проверяет доступность сервера и подключение к БД"""
    try:
        # Проверяем наличие переменных окружения
        db_url = os.getenv("DATABASE_URL")
        db_status = "configured" if db_url else "missing"

        # Пытаемся подключиться к БД если она настроена
        db_connection = "unknown"
        db_error_details = None
        if db_url and SessionLocal:
            try:
                from sqlalchemy import text
                async with SessionLocal() as session:
                    await session.execute(text("SELECT 1"))
                db_connection = "ok"
            except Exception as e:
                error_msg = str(e)
                db_connection = "error"
                db_error_details = error_msg[:200]
                if "Name or service not known" in error_msg:
                    db_error_details += " | Возможно неправильный хост"
                elif "could not translate host name" in error_msg.lower():
                    db_error_details += " | Проверьте формат DATABASE_URL"
        elif not db_url:
            db_connection = "not_configured"

        result = {
            "status": "ok",
            "database_url": db_status,
            "database_connection": db_connection,
            "message": "Server is running"
        }
        if db_error_details:
            result["database_error"] = db_error_details
        if db_url:
            # Показываем хост из URL (без пароля)
            try:
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                result["database_host"] = parsed.hostname
                result["database_port"] = parsed.port
            except:
                pass
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }