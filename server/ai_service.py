import json
import os
import re
from datetime import datetime
from typing import Any, Optional

import httpx

from packing_advisor import build_packing_advice
from packing_followup import build_packing_command_context
from trip_context import build_ad_hoc_trip_context
from itinerary_logic import optimize_itinerary_plan_items
from assistant_intents import is_expense_intent

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
GEMINI_COMPLEX_MODEL = os.getenv("GEMINI_COMPLEX_MODEL", GEMINI_MODEL).strip() or GEMINI_MODEL

# By default, use Google's official URL. 
# But let this be overridable if the user buys a key from a third-party proxy service.
DEFAULT_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def _build_model_url(model_name: str) -> str:
    configured_url = os.getenv("GEMINI_BASE_URL", "").strip()
    if configured_url:
        replaced = re.sub(
            r"/models/[^/:?]+:generateContent",
            f"/models/{model_name}:generateContent",
            configured_url,
            count=1,
        )
        if "/models/" in configured_url and ":generateContent" in configured_url:
            return replaced
        return configured_url
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"


def _is_invalid_gemini_key_response(status_code: int, body: str) -> bool:
    if status_code not in {400, 401, 403}:
        return False
    normalized = (body or "").lower()
    return (
        "api key not valid" in normalized
        or "api_key_invalid" in normalized
        or "permission_denied" in normalized
        or "invalid_argument" in normalized
    )


def _gemini_misconfigured_response(language: str) -> dict:
    return {
        "answer": (
            "AI-ассистент не настроен: проверьте GEMINI_API_KEY в .env."
            if language == "ru"
            else "AI assistant is not configured: check GEMINI_API_KEY in .env."
        ),
        "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
        "plan_proposals": [],
        "event_change_proposals": [],
        "expense_proposals": [],
        "packing_recommendations": [],
    }


def _select_model_name(
    planning_intent: bool,
    event_change_intent: bool,
) -> str:
    if planning_intent or event_change_intent:
        return GEMINI_COMPLEX_MODEL
    return GEMINI_CHAT_MODEL


def _build_model_candidates(
    planning_intent: bool,
    event_change_intent: bool,
    food_intent: bool,
) -> list[str]:
    primary = _select_model_name(planning_intent, event_change_intent)
    candidates = [primary]
    if food_intent and primary != GEMINI_COMPLEX_MODEL:
        candidates.append(GEMINI_COMPLEX_MODEL)
    return candidates

SYSTEM_PROMPT = """Ты — умный и интеллигентный AI-помощник для путешественников в приложении Luggify.
Разговаривай по-человечески, вежливо и естественно, как опытный гид. Избегай чрезмерного использования сленга и фамильярности. 
Твоя задача — давать полезную, точную и интересную информацию, сохраняя профессионализм и дружелюбие.

ОЧЕНЬ ВАЖНО: 
1. Не повторяй каждый раз заготовленные вводные фразы ("В Будапеште...", "Этот город славится..."). Начинай сразу с ответа.
2. Используй абзацы и списки (1., 2., 3., 4., 5.) с переносом строки для удобства чтения.
3. Ни в коем случае не используй эмодзи (NO EMOJIS). Твои ответы должны быть строгими и без эмодзи.
4. Отвечай кратко (до 5 предложений), но емко. Пользователь уже знает, в каком он городе.
5. Если пользователь просит план, маршрут или идеи на день, используй события, погоду и известные места из контекста ниже.
6. Не выдумывай точные факты, адреса и часы работы. Если данных не хватает, честно скажи об этом и предложи безопасный вариант.
7. НИКОГДА не говори "дата ещё не наступила", "я не могу предоставить информацию о будущем" или "основываясь на исторических данных". Прогноз погоды и контекст поездки УЖЕ предоставлены ниже — используй их как факт. Составляй план уверенно.
8. При составлении плана на день ОБЯЗАТЕЛЬНО используй прогноз погоды из контекста. Если ожидается дождь — предложи крытые места. Если солнечно — предложи прогулки и парки. Упомяни погоду кратко в начале ответа.

Контекст поездки пользователя:
{trip_context_text}

На каком языке был задан вопрос — на таком и отвечай."""

SUGGESTED_QUESTIONS = {
    "ru": [
        "Что обязательно попробовать из еды?",
        "Какие достопримечательности must-see?",
        "Как лучше перемещаться по городу?",
        "Есть ли опасные районы?",
        "Составь план на день с учетом погоды",
        "Что купить в подарок?",
        "Какие местные обычаи нужно знать?",
    ],
    "en": [
        "What food should I try?",
        "What are the must-see places?",
        "Best way to get around?",
        "Any unsafe areas to avoid?",
        "Plan my day around the weather",
        "What to buy as a souvenir?",
        "Local customs I should know?",
    ]
}

PLAN_KEYWORDS_RE = re.compile(
    r"(план|маршрут|расписан|тайминг|что\s+делать\s+сегодня|что\s+делать\s+завтра|"
    r"куда\s+сходить|что\s+посетить|мест[ао]\s+посетить|достопримечательност|экскурс|"
    r"составь|раскидай\s+по\s+времени|по\s+времени|по\s+часам|"
    r"\bplan\b|\bitinerary\b|\bschedule\b|\broute\b|\bday\s*plan\b|\btimeline\b|"
    r"\bplaces?\s+to\s+visit\b|\bwhat\s+to\s+see\b|\bsights?\b|\battractions?\b|\btours?\b)",
    re.IGNORECASE,
)
ATTRACTION_IDEAS_RE = re.compile(
    r"(куда\s+сходить|что\s+посетить|мест[ао]\s+посетить|достопримечательност|экскурс|"
    r"\bplaces?\s+to\s+visit\b|\bwhat\s+to\s+see\b|\bsights?\b|\battractions?\b|\btours?\b)",
    re.IGNORECASE,
)
FOOD_KEYWORDS_RE = re.compile(
    r"(где\s+поесть|куда\s+сходить\s+покушать|где\s+покушать|где\s+вкусно|"
    r"что\s+попробовать\s+из\s+еды|ресторан|кафе|бар|завтрак|обед|ужин|"
    r"\beat\b|\bfood\b|\brestaurant\b|\bcafe\b|\bbreakfast\b|\blunch\b|\bdinner\b)",
    re.IGNORECASE,
)
EVENT_CHANGE_KEYWORDS_RE = re.compile(
    r"(перенес|сдвин|замен|обнов|измени|исправ|удал|убери|отмен|"
    r"move|shift|resched|replace|update|change|remove|delete|cancel)",
    re.IGNORECASE,
)
EXPENSE_KEYWORDS_RE = re.compile(
    r"(бюджет|трат|расход|потрат|сколько\s+остал|сколько\s+денег|деньг|стоимост|"
    r"\bbudget\b|\bexpense\b|\bexpenses\b|\bspent\b|\bspend\b|\bcost\b|\bmoney\b)",
    re.IGNORECASE,
)
PACKING_KEYWORDS_RE = re.compile(
    r"(вещи|вещь|рюкзак|сумк|чемодан|багаж|положи|возьми|добавь\s+в|убери\s+из|собери|трус|носк|футболк|куртк|плать|"
    r"\bpack\b|\bbaggage\b|\bluggage\b|\bbackpack\b|\bsuitcase\b|\bbag\b|\btake\b|\bput\b|\bremove\b)",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<currency>₽|руб(?:\.|лей|ля|ль)?|rub|евро|eur|€|доллар(?:ов|а)?|бакс(?:ов|а)?|usd|"
    r"фунт(?:ов|а)?|gbp|лари|gel|лир(?:а|ы)?|try|дирхам(?:ов|а)?|aed|тенге|kzt|\$|[a-zA-Z]{3})?",
    re.IGNORECASE,
)


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        repaired = cleaned[start:end + 1]
        repaired = re.sub(r";\s*(?=\"[A-Za-zА-Яа-я_])", ",", repaired)
        repaired = re.sub(r";\s*([}\]])", r"\1", repaired)
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _format_forecast_context(
    daily_forecast: Optional[list[dict[str, Any]]],
    language: str,
) -> str:
    if not daily_forecast:
        return "нет данных" if language == "ru" else "no data"

    rows: list[str] = []
    for entry in daily_forecast[:6]:
        date = str(entry.get("date") or "").strip()
        condition = str(entry.get("condition") or "").strip()
        temp_min = entry.get("temp_min")
        temp_max = entry.get("temp_max")
        humidity = entry.get("humidity")
        uv_index = entry.get("uv_index")
        wind_speed = entry.get("wind_speed")
        source = str(entry.get("source") or "").strip()
        temp_bits = []
        if temp_min is not None:
            temp_bits.append(f"min {temp_min}C")
        if temp_max is not None:
            temp_bits.append(f"max {temp_max}C")
        if humidity is not None:
            temp_bits.append(f"humidity {humidity}%")
        if uv_index is not None:
            temp_bits.append(f"UV {uv_index}")
        if wind_speed is not None:
            temp_bits.append(f"wind {wind_speed} km/h")
        suffix = f" ({', '.join(temp_bits)})" if temp_bits else ""
        source_suffix = f", {source}" if source else ""
        rows.append(f"{date}: {condition}{suffix}{source_suffix}".strip(": "))
    return "; ".join(rows)


def _format_events_context(
    events: Optional[list[dict[str, Any]]],
    language: str,
) -> str:
    if not events:
        return "нет запланированных событий" if language == "ru" else "no scheduled events"

    normalized = sorted(
        events[:40],
        key=lambda item: (str(item.get("event_date") or ""), str(item.get("time") or "")),
    )
    rows: list[str] = []
    for event in normalized:
        event_date = str(event.get("event_date") or "").strip()
        event_time = str(event.get("time") or "").strip()
        title = str(event.get("title") or "").strip()
        address = str(event.get("address") or "").strip()
        event_id = event.get("event_id")
        prefix = " ".join(part for part in [event_date, event_time] if part).strip()
        row = f"[id={event_id}] {prefix}: {title}" if prefix else f"[id={event_id}] {title}"
        if address:
            row = f"{row} ({address})"
        rows.append(row)
    return "; ".join(row for row in rows if row)


def _format_attractions_context(
    attractions: Optional[list[dict[str, Any]]],
    language: str,
) -> str:
    if not attractions:
        return "нет сохранённых рекомендаций" if language == "ru" else "no saved recommendations"

    rows: list[str] = []
    for attraction in attractions[:6]:
        name = str(attraction.get("name") or "").strip()
        address = str(attraction.get("address") or "").strip()
        if not name:
            continue
        rows.append(f"{name} ({address})" if address else name)
    return "; ".join(rows) or ("нет сохранённых рекомендаций" if language == "ru" else "no saved recommendations")


def _format_trip_profile_context(profile: dict[str, Any], language: str) -> str:
    scenarios = ", ".join(profile.get("trip_activities") or []) or ("не выбраны" if language == "ru" else "not selected")
    accommodation = profile.get("accommodation_type") if profile.get("accommodation_selected") else ("не выбрано" if language == "ru" else "not selected")
    bits = [
        f"type: {(profile.get('trip_type') or 'city_break').replace('_', ' ')}",
        f"activities: {scenarios}",
        f"baggage format: {profile.get('baggage_format') or 'flexible'}",
        f"accommodation: {accommodation}",
        f"laundry: {profile.get('laundry_access') or 'limited'}",
        f"packing style: {profile.get('packing_style') or 'balanced'}",
    ]
    trip_note = str(profile.get("trip_note") or "").strip()
    if trip_note:
        bits.append(f"note: {trip_note}")
    return "; ".join(bits)


def _format_participants_context(participants: Optional[list[dict[str, Any]]], language: str) -> str:
    if not participants:
        return "нет данных" if language == "ru" else "no data"
    rows = []
    for participant in participants[:20]:
        username = participant.get("username") or f"user:{participant.get('user_id')}"
        role = participant.get("role") or "participant"
        baggage_ids = participant.get("baggage_ids") or []
        baggage_suffix = f", baggage_ids={baggage_ids}" if baggage_ids else ""
        rows.append(f"{username} ({role}{baggage_suffix})")
    return "; ".join(rows)


def _format_item_entry(item: dict[str, Any]) -> str:
    name = str(item.get("name") or "").strip()
    quantity = item.get("quantity")
    packed_quantity = item.get("packed_quantity")
    if quantity is None:
        return name
    return f"{name} {packed_quantity or 0}/{quantity}"


def _format_baggage_context(baggage: Optional[dict[str, Any]], language: str) -> str:
    if not baggage:
        return "нет данных" if language == "ru" else "no data"

    rows: list[str] = []
    shared = baggage.get("shared") or {}
    shared_items = [
        _format_item_entry(item)
        for item in (shared.get("items") or [])
        if item.get("name") and not item.get("is_removed")
    ][:30]
    if shared_items:
        rows.append(f"shared: {', '.join(shared_items)}")

    for backpack in (baggage.get("backpacks") or [])[:15]:
        items = [
            _format_item_entry(item)
            for item in (backpack.get("items") or [])
            if item.get("name") and not item.get("is_removed")
        ][:30]
        removed = [
            item.get("name")
            for item in (backpack.get("items") or [])
            if item.get("name") and item.get("is_removed")
        ][:10]
        parts = []
        if items:
            parts.append(f"items: {', '.join(items)}")
        if removed:
            parts.append(f"removed: {', '.join(removed)}")
        rows.append(f"{backpack.get('label') or backpack.get('name') or 'baggage'} ({'; '.join(parts) if parts else 'empty'})")

    if baggage.get("hidden_backpacks_count"):
        rows.append(f"hidden baggage sections: {baggage.get('hidden_backpacks_count')}")
    return "; ".join(rows) or ("багаж пуст" if language == "ru" else "baggage is empty")


def _format_packing_summary_context(summary: Optional[dict[str, Any]], language: str) -> str:
    if not summary:
        return "нет данных" if language == "ru" else "no data"

    def format_summary_items(items: list[dict[str, Any]], limit: int = 12) -> str:
        rows = []
        for item in items[:limit]:
            name = str(item.get("name") or "").strip()
            section = str(item.get("section") or "").strip()
            quantity = item.get("quantity")
            packed_quantity = item.get("packed_quantity")
            if not name:
                continue
            progress = f" {packed_quantity or 0}/{quantity}" if quantity is not None else ""
            rows.append(f"{name}{progress}{f' in {section}' if section else ''}")
        return ", ".join(rows)

    packed = format_summary_items(summary.get("packed_items") or [])
    remaining = format_summary_items(summary.get("remaining_items") or [])
    removed = format_summary_items(summary.get("removed_items") or [], limit=15)
    bits = [
        f"packed_count: {summary.get('packed_count', 0)}",
        f"remaining_count: {summary.get('remaining_count', 0)}",
    ]
    if packed:
        bits.append(f"already packed: {packed}")
    if remaining:
        bits.append(f"remaining: {remaining}")
    if removed:
        bits.append(f"removed: {removed}")
    return "; ".join(bits)


def _format_expenses_context(expenses: Optional[dict[str, Any]], language: str) -> str:
    if not expenses:
        return "нет данных" if language == "ru" else "no data"
    if expenses.get("visible") is False:
        return "раздел трат скрыт" if language == "ru" else "expenses section is hidden"
    base_currency = expenses.get("base_currency") or "RUB"
    bits = [
        f"budget: {expenses.get('budget_amount')} {base_currency}" if expenses.get("budget_amount") is not None else f"budget: not set {base_currency}",
        f"daily limit: {expenses.get('daily_budget_amount')} {base_currency}" if expenses.get("daily_budget_amount") is not None else f"daily limit: not set {base_currency}",
        f"spent: {expenses.get('total_spent', 0)} {base_currency}",
        f"today spent: {expenses.get('today_spent', 0)} {base_currency}",
    ]
    if expenses.get("remaining") is not None:
        bits.append(f"remaining: {expenses.get('remaining')} {base_currency}")
    if expenses.get("today_remaining") is not None:
        bits.append(f"today remaining: {expenses.get('today_remaining')} {base_currency}")
    by_category = expenses.get("by_category") or {}
    if by_category:
        bits.append(
            "categories: "
            + ", ".join(f"{category} {amount} {base_currency}" for category, amount in list(by_category.items())[:8])
        )
    recent = []
    for expense in (expenses.get("items") or [])[:15]:
        title = str(expense.get("title") or "").strip()
        if not title:
            continue
        recent.append(f"{title}: {expense.get('amount')} {expense.get('currency')}")
    if recent:
        bits.append("recent: " + ", ".join(recent))
    return "; ".join(bits)


def _format_trip_context_text(trip_context: dict[str, Any], language: str) -> str:
    trip = trip_context.get("trip") or {}
    profile = trip_context.get("trip_profile") or {}
    lines = [
        f"- Город: {trip.get('city') or 'не указан'}",
        f"- Даты: {trip.get('start_date') or 'не указаны'} — {trip.get('end_date') or 'не указаны'}",
        f"- Длительность: {trip.get('duration_days') or 'неизвестно'} дней",
        f"- Город отправления: {trip.get('origin_city') or 'не указан'}",
        f"- Средняя температура: {trip.get('avg_temp') if trip.get('avg_temp') is not None else 'неизвестна'}°C",
        f"- Транспорт: {', '.join(trip.get('transports') or []) or 'не указан'}",
        f"- Сценарии и настройки: {_format_trip_profile_context(profile, language)}",
        f"- Участники: {_format_participants_context(trip_context.get('participants'), language)}",
        f"- Прогноз по дням: {_format_forecast_context(trip_context.get('daily_forecast'), language)}",
        f"- Запланированные события: {_format_events_context(trip_context.get('events'), language)}",
        f"- Багаж и вещи: {_format_baggage_context(trip_context.get('baggage'), language)}",
        f"- Что уже собрано / осталось: {_format_packing_summary_context(trip_context.get('packing_summary'), language)}",
        f"- Бюджет и траты: {_format_expenses_context(trip_context.get('expenses'), language)}",
        f"- Известные места рядом: {_format_attractions_context(trip_context.get('attractions'), language)}",
    ]
    return "\n".join(lines)


def _detect_planning_intent(question: str) -> bool:
    return bool(PLAN_KEYWORDS_RE.search((question or "").strip()))


def _detect_event_change_intent(question: str, itinerary_events: Optional[list[dict[str, Any]]]) -> bool:
    if not itinerary_events:
        return False
    normalized = (question or "").strip()
    return bool(EVENT_CHANGE_KEYWORDS_RE.search(normalized))


def _detect_food_intent(question: str) -> bool:
    return bool(FOOD_KEYWORDS_RE.search((question or "").strip()))


def _detect_expense_intent(question: str) -> bool:
    return is_expense_intent(question) or bool(EXPENSE_KEYWORDS_RE.search((question or "").strip()))


def _detect_packing_intent(question: str) -> bool:
    return bool(PACKING_KEYWORDS_RE.search((question or "").strip()))


def _build_question_prefix(question: str, planning_intent: bool, language: str) -> str:
    if not planning_intent:
        return question

    attraction_ideas_intent = bool(ATTRACTION_IDEAS_RE.search(question or ""))
    if language == "ru":
        if attraction_ideas_intent:
            planning_instruction = (
                "Это запрос на идеи мест, достопримечательностей или экскурсий, а не на расписание полного дня. "
                "Верни только JSON без markdown и без пояснений вне JSON. "
                "Формат JSON: "
                "{\"answer\":\"...\","
                "\"plan_proposals\":[{\"event_date\":\"YYYY-MM-DD\",\"time\":\"HH:MM|null\",\"day_part\":\"morning|day|evening|null\","
                "\"title\":\"...\",\"description\":\"...\",\"address\":\"...\",\"lat\":0,\"lng\":0,"
                "\"duration_minutes\":90,\"travel_buffer_minutes\":30,\"event_type\":\"sight|walk|museum|tour|attraction\","
                "\"reason\":\"...\",\"weather_note\":\"...\"}]}. "
                "В answer коротко объясни, что пользователь может отметить места и выбрать дату/время для добавления. "
                "Верни 4-7 plan_proposals только для реальных мест, прогулок, музеев, экскурсий, видовых точек или локальных впечатлений. "
                "Не добавляй завтрак, обед, ужин, рестораны, кафе или бары. "
                "time можно оставить null, если пользователь не просил конкретное время. "
                "event_date ставь в пределах дат поездки; если день не уточнён, используй первый день поездки. "
                "Не повторяй места, которые уже есть в событиях маршрута. "
                "Для каждой реальной точки по возможности укажи address и lat/lng; если не уверен, выбери более известное место в городе."
            )
            return f"{planning_instruction}\n\nВопрос пользователя: {question}"
        planning_instruction = (
            "Это запрос на план поездки. "
            "Верни только JSON без markdown и без пояснений вне JSON. "
            "Формат JSON: "
            "{\"answer\":\"...\","
            "\"plan_proposals\":[{\"event_date\":\"YYYY-MM-DD\",\"time\":\"HH:MM|null\",\"day_part\":\"morning|day|evening|null\","
            "\"title\":\"...\",\"description\":\"...\",\"address\":\"...\",\"lat\":0,\"lng\":0,"
            "\"duration_minutes\":90,\"travel_buffer_minutes\":30,\"event_type\":\"sight|food|walk|rest|snack|shopping|transport\","
            "\"reason\":\"...\",\"weather_note\":\"...\"}]}. "
            "В answer дай короткое вступление и затем логичные блоки дня: утро, день, вечер. "
            "ВСЕ пункты, места и активности из текста answer ОБЯЗАТЕЛЬНО должны быть продублированы в массиве plan_proposals. plan_proposals должен представлять собой полный и пошаговый маршрут дня. "
            "Внутри plan_proposals ОБЯЗАТЕЛЬНО укажи конкретное время `time` (в формате HH:MM) для каждого пункта, включая приемы пищи и достопримечательности. Распределяй время логично, учитывая duration_minutes и travel_buffer_minutes. "
            "Если есть события с временем, используй их как фиксированные якоря дня. "
            "По плотности: для легкого дня дай 7 пунктов, для сбалансированного 8-10, для насыщенного 11-13. Если плотность не указана, делай сбалансированный день. "
            "Для полного дня добавь завтрак, 3-4 разные активности/места, обед, вечернюю активность и ужин. "
            "Не добавляй image или image_position. "
            "Если пользователь просит полный день, насыщенный день, третий/второй/первый день целиком или план на день, обязательно добавь breakfast, lunch и dinner как отдельные food-пункты, даже если пользователь не перечислил приемы пищи явно. "
            "СТРОГОЕ ПРАВИЛО: В плане на день должно быть не более 1 завтрака, 1 обеда и 1 ужина. Чтобы набрать нужное количество пунктов для насыщенного дня, добавляй активности (музеи, прогулки), а не приемы пищи. "
            "Если пользователь просит завтрак, обед или ужин, обязательно добавь отдельный food-пункт для каждого запрошенного приема пищи. "
            "Для food-пунктов не выбирай конкретный ресторан сам: пиши нейтрально вроде \"Завтрак рядом с ...\", потому что конкретное заведение пользователь выберет отдельно. "
            "Не считай generic food-пункт полноценной активностью: кроме еды должны быть содержательные места, прогулки, музеи, рынки, видовые точки или локальные впечатления. "
            "Не добавляй рестораны, кафе, бары или винные бары как обычные активности, если пользователь прямо не попросил именно бары/рестораны; еда должна быть только в food-пунктах завтрака/обеда/ужина. "
            "Можно добавить короткий street-food/snack пункт как локальное впечатление рядом с достопримечательностью: например попробовать глинтвейн, выпечку или уличный десерт у рынка/площади. Это не должен быть заход в ресторан и не должен ломать маршрут. "
            "Не предлагай выезд в другой город или дальний day trip, если пользователь прямо не попросил. Для городского маршрута держи точки внутри города поездки. "
            "Выбирай компактный район дня: не смешивай в одном дне точки с разных концов города, если между ними нет сильной причины. "
            "Для каждой реальной точки маршрута по возможности укажи lat/lng; если координат не знаешь уверенно, лучше выбери более известное место в городе. "
            "Ставь места в логичном географическом порядке: сначала точки рядом друг с другом, без скачков туда-сюда по городу. "
            "Если точки далеко, увеличивай travel_buffer_minutes; если рядом, буфер может быть коротким. "
            "Учитывай погоду при выборе активности и прямо отмечай, что лучше перенести из-за дождя, жары или ветра. "
            "Не повторяй места, которые уже есть в событиях маршрута. Делай день насыщенным, но с буферами на дорогу и отдых. "
            "Для plan_proposals укажи только реально применимые пункты. "
            "event_date ставь в пределах дат поездки; если пользователь не уточнил день, по умолчанию используй первый день поездки."
        )
    else:
        if attraction_ideas_intent:
            planning_instruction = (
                "This is a request for place, sight, or tour ideas, not a full-day schedule. "
                "Return JSON only, with no markdown and no extra text outside JSON. "
                "JSON format: "
                "{\"answer\":\"...\","
                "\"plan_proposals\":[{\"event_date\":\"YYYY-MM-DD\",\"time\":\"HH:MM|null\",\"day_part\":\"morning|day|evening|null\","
                "\"title\":\"...\",\"description\":\"...\",\"address\":\"...\",\"lat\":0,\"lng\":0,"
                "\"duration_minutes\":90,\"travel_buffer_minutes\":30,\"event_type\":\"sight|walk|museum|tour|attraction\","
                "\"reason\":\"...\",\"weather_note\":\"...\"}]}. "
                "In answer, briefly say the user can select places and choose date/time before adding them. "
                "Return 4-7 plan_proposals only for real sights, walks, museums, tours, viewpoints, or local experiences. "
                "Do not add breakfast, lunch, dinner, restaurants, cafes, or bars. "
                "time can be null unless the user asked for a specific time. "
                "Keep event_date within trip dates; if no day is specified, use the first trip day. "
                "Do not repeat places already in the itinerary. "
                "Include address and lat/lng when reasonably confident; if uncertain, choose a better-known place in the city."
            )
            return f"{planning_instruction}\n\nUser question: {question}"
        planning_instruction = (
            "This is a trip-planning request. "
            "Return JSON only, with no markdown and no extra text outside JSON. "
            "JSON format: "
            "{\"answer\":\"...\","
            "\"plan_proposals\":[{\"event_date\":\"YYYY-MM-DD\",\"time\":\"HH:MM|null\",\"day_part\":\"morning|day|evening|null\","
            "\"title\":\"...\",\"description\":\"...\",\"address\":\"...\",\"lat\":0,\"lng\":0,"
            "\"duration_minutes\":90,\"travel_buffer_minutes\":30,\"event_type\":\"sight|food|walk|rest|snack|shopping|transport\","
            "\"reason\":\"...\",\"weather_note\":\"...\"}]}. "
            "In answer, give a short intro followed by logical day blocks: morning, day, evening. "
            "ALL items, places, and activities mentioned in the answer text MUST be included in the plan_proposals array. The plan_proposals array must represent the complete step-by-step daily itinerary. "
            "Inside plan_proposals, you MUST specify an exact `time` (HH:MM format) for every item, including meals and sights. Distribute the times logically based on duration_minutes and travel_buffer_minutes. "
            "Use existing timed events as fixed anchors when available. "
            "For intensity: return 7 items for an easy day, 8-10 for a balanced day, and 11-13 for a rich day. If intensity is not specified, make a balanced day. "
            "For a full day, include breakfast, 3-4 varied activities/places, lunch, an evening activity, and dinner. Do not include image or image_position. "
            "If the user asks for a full day, rich day, first/second/third day, or a day plan, always include breakfast, lunch, and dinner as separate food items, even when meals are not listed explicitly. "
            "STRICT RULE: A daily plan must have no more than 1 breakfast, 1 lunch, and 1 dinner. To reach the required number of items for a rich day, add activities (museums, walks), not meals. "
            "If the user asks for breakfast, lunch, or dinner, always include a separate food item for every requested meal. "
            "For food items, do not pick a specific restaurant yourself: use neutral wording like \"Breakfast near ...\" because the user will choose the exact place separately. "
            "Do not treat generic food as a full activity: add real sights, walks, museums, markets, viewpoints, or local experiences besides meals. "
            "Do not add restaurants, cafes, bars, or wine bars as regular activities unless the user explicitly asks for bars/restaurants; food should appear only as breakfast/lunch/dinner food items. "
            "You may add a short street-food/snack item as a local experience near a sight: for example mulled wine, pastry, or a street dessert near a market/square. It must not be a restaurant stop and must not break the route. "
            "Do not suggest another city or a long day trip unless the user explicitly asks for it. For city routes, keep stops inside the trip city. "
            "Choose a compact area for the day: do not mix stops from opposite sides of the city unless there is a strong reason. "
            "Include lat/lng for every real itinerary stop when reasonably confident; if coordinates are uncertain, choose a better-known place in the city. "
            "Order places geographically: nearby stops should follow each other, without jumping back and forth across the city. "
            "If stops are far apart, increase travel_buffer_minutes; if they are nearby, the buffer can be short. "
            "Account for weather and explicitly mention what should be moved because of rain, heat, or wind. "
            "Do not repeat places that are already in itinerary events. Keep the day rich but realistic with travel/rest buffers. "
            "Only include practical items in plan_proposals. "
            "Keep event_date within the trip dates; if the user does not specify a day, default to the first trip day."
        )

    return f"{planning_instruction}\n\nВопрос пользователя: {question}" if language == "ru" else f"{planning_instruction}\n\nUser question: {question}"


def _build_food_question_prefix(question: str, language: str) -> str:
    if language == "ru":
        instruction = (
            "Это запрос про еду, рестораны или места, где поесть. "
            "При необходимости используй подключённые инструменты поиска. "
            "Если пользователь просит именно места, сначала постарайся найти реальные заведения и предложи 3-5 конкретных вариантов. "
            "Для каждого варианта коротко объясни, чем он хорош: морепродукты, завтрак, вид, атмосфера, мясо, кофе, романтический ужин и т.д. "
            "Если пользователь не уточнил кухню или бюджет, не задавай встречный вопрос: по умолчанию дай сбалансированную подборку разных форматов. "
            "Если надёжных конкретных мест не нашлось, только тогда предложи районы, форматы заведений или локальные блюда. "
            "Не придумывай факты, адреса и часы работы без опоры на найденные данные."
        )
        return f"{instruction}\n\nВопрос пользователя: {question}"
    instruction = (
        "This is a food or restaurant request. "
        "Use the available search tools when needed. "
        "If the user asks for places, try to find real venues first and recommend 3-5 concrete options. "
        "For each option briefly explain why it fits: seafood, breakfast, view, atmosphere, steak, coffee, date night, and so on. "
        "If the user does not specify cuisine or budget, do not ask a follow-up question by default; instead provide a balanced shortlist. "
        "Only fall back to neighborhoods, venue types, or local dishes when reliable specific places are not available."
    )
    return f"{instruction}\n\nUser question: {question}"


def _build_expense_question_prefix(question: str, language: str) -> str:
    if language == "ru":
        instruction = (
            "Это запрос про бюджет или траты поездки. "
            "Если пользователь просит добавить трату/расход или поставить бюджет, верни только JSON без markdown. "
            "Формат JSON: {\"answer\":\"...\",\"expense_proposals\":[{\"action\":\"create|set_budget|set_daily_budget\","
            "\"title\":\"...|null\",\"category\":\"food|transport|tickets|hotel|entertainment|shopping|other|null\","
            "\"amount\":123,\"currency\":\"ISO-4217 код вроде RUB, EUR, TRY, AED\",\"expense_date\":\"YYYY-MM-DD|null\","
            "\"note\":\"...|null\",\"budget_amount\":123,\"daily_budget_amount\":50,\"base_currency\":\"ISO-4217 код или null\","
            "\"split_count\":3}]}. "
            "ВАЖНО: В текстовом 'answer' не упоминай чемоданы, рюкзаки, багаж или упаковку. Отвечай только про финансы. "
            "Если пользователь спрашивает сводку, экономию или анализ без действия, верни JSON с answer и пустым expense_proposals."
        )
        return f"{instruction}\n\nВопрос пользователя: {question}"
    instruction = (
        "This is a trip budget or expense request. "
        "If the user wants to add an expense or set a budget, return JSON only. "
        "JSON format: {\"answer\":\"...\",\"expense_proposals\":[{\"action\":\"create|set_budget|set_daily_budget\","
        "\"title\":\"...|null\",\"category\":\"food|transport|tickets|hotel|entertainment|shopping|other|null\","
        "\"amount\":123,\"currency\":\"ISO-4217 code like RUB, EUR, TRY, AED\",\"expense_date\":\"YYYY-MM-DD|null\","
        "\"note\":\"...|null\",\"budget_amount\":123,\"daily_budget_amount\":50,\"base_currency\":\"ISO-4217 code or null\","
        "\"split_count\":3}]}. "
        "IMPORTANT: In your 'answer' text, do NOT mention packing, luggage, backpacks, or suitcases. This is purely financial."
        "For summaries or savings advice, return answer and an empty expense_proposals array."
    )
    return f"{instruction}\n\nUser question: {question}"


def _build_tools_payload(food_intent: bool) -> list[dict[str, Any]] | None:
    if not food_intent:
        return None
    return [
        {"googleMaps": {}},
    ]


def _build_event_change_prefix(question: str, language: str) -> str:
    if language == "ru":
        instruction = (
            "Это запрос на изменение уже существующего маршрута. "
            "Верни только JSON без markdown и без пояснений вне JSON. "
            "Формат JSON: "
            "{\"answer\":\"...\","
            "\"event_change_proposals\":[{\"action\":\"update|delete|create\",\"target_event_id\":123,"
            "\"event_date\":\"YYYY-MM-DD|null\",\"time\":\"HH:MM|null\",\"title\":\"...|null\","
            "\"description\":\"...|null\",\"address\":\"...|null\",\"reason\":\"...|null\"}]}. "
            "Для update/delete используй только существующие id событий из контекста. Для create target_event_id=null. "
            "Если нужен перенос или правка, используй action=update. "
            "Если событие лучше убрать, используй action=delete. "
            "Если пользователь явно просит добавить одно событие, используй action=create. "
            "В answer коротко объясни, что предлагаешь поменять и почему."
        )
        return f"{instruction}\n\nВопрос пользователя: {question}"
    instruction = (
        "This is a request to change an existing itinerary. "
        "Return JSON only, with no markdown and no extra text outside JSON. "
        "JSON format: "
        "{\"answer\":\"...\","
        "\"event_change_proposals\":[{\"action\":\"update|delete|create\",\"target_event_id\":123,"
        "\"event_date\":\"YYYY-MM-DD|null\",\"time\":\"HH:MM|null\",\"title\":\"...|null\","
        "\"description\":\"...|null\",\"address\":\"...|null\",\"reason\":\"...|null\"}]}. "
        "Use existing event ids for update/delete. For create use target_event_id=null. "
        "Use action=update for moving or editing, and action=delete for removing an event. "
        "Use action=create when the user explicitly asks to add one event. "
        "In answer, briefly explain what should change and why."
    )
    return f"{instruction}\n\nUser question: {question}"


def _build_packing_question_prefix(question: str, language: str) -> str:
    if language == "ru":
        instruction = (
            "Это запрос на управление вещами и багажом (добавление, удаление, распределение). "
            "Верни только JSON без markdown и без пояснений вне JSON. "
            "Формат JSON: "
            "{\"answer\":\"...\","
            "\"packing_recommendations\":[{\"suggested_action\":\"add|remove|move_to_carry_on|keep\",\"item\":\"...\",\"quantity\":1,"
            "\"target_section\":\"...|null\",\"reason\":\"...\"}]}. "
            "action: add (добавить новую вещь), remove (убрать вещь), move_to_carry_on (переложить в ручную кладь), keep. "
            "target_section: название рюкзака/багажа из контекста (например 'Рюкзак Вероники'). Если не указано или не найдено, ставь null. "
            "quantity: количество вещей, если указано (числом). "
            "В answer коротко подтверди, какие изменения с вещами ты предлагаешь."
        )
        return f"{instruction}\n\nВопрос пользователя: {question}"
    instruction = (
        "This is a request to manage packing and baggage (adding, removing, moving items). "
        "Return JSON only, with no markdown and no extra text outside JSON. "
        "JSON format: "
        "{\"answer\":\"...\","
        "\"packing_recommendations\":[{\"suggested_action\":\"add|remove|move_to_carry_on|keep\",\"item\":\"...\",\"quantity\":1,"
        "\"target_section\":\"...|null\",\"reason\":\"...\"}]}. "
        "action: add (add new item), remove (remove item), move_to_carry_on (move to cabin bag), keep. "
        "target_section: exact name of the backpack/baggage from context (e.g. 'Veronika backpack'). If not specified, use null. "
        "quantity: item quantity if specified (as number). "
        "In answer, briefly confirm the proposed packing changes."
    )
    return f"{instruction}\n\nUser question: {question}"


def _normalize_plan_proposals(
    proposals: Any,
    start_date: str,
    end_date: str,
    existing_events: Any = None,
) -> list[dict[str, Any]]:
    if not isinstance(proposals, list):
        return []

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else start_dt
    except ValueError:
        start_dt = None
        end_dt = None

    existing_keys: set[str] = set()
    day_counts: dict[str, int] = {}
    day_minutes: dict[str, int] = {}
    for existing_event in existing_events or []:
        if not isinstance(existing_event, dict):
            continue
        existing_date = str(existing_event.get("event_date") or "").strip()
        if existing_date:
            day_counts[existing_date] = day_counts.get(existing_date, 0) + 1
            duration = _safe_positive_int(existing_event.get("duration_minutes"), fallback=90, maximum=1440) or 0
            buffer_minutes = _safe_positive_int(existing_event.get("travel_buffer_minutes"), fallback=30, maximum=480) or 0
            day_minutes[existing_date] = day_minutes.get(existing_date, 0) + duration + buffer_minutes
        existing_key = _plan_duplicate_key(existing_event.get("title"), existing_event.get("address"))
        if existing_key:
            existing_keys.add(existing_key)

    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(proposals[:15]):
        if not isinstance(raw_item, dict):
            continue
        event_date = str(raw_item.get("event_date") or "").strip() or start_date
        title = str(raw_item.get("title") or "").strip()
        if not title:
            continue
        duplicate_key = _plan_duplicate_key(title, raw_item.get("address"))
        if duplicate_key and duplicate_key in existing_keys:
            continue
        time_value = str(raw_item.get("time") or "").strip() or None
        if time_value and not re.match(r"^\d{2}:\d{2}$", time_value):
            time_value = None
        try:
            parsed_date = datetime.strptime(event_date, "%Y-%m-%d").date()
        except ValueError:
            if start_dt is None:
                continue
            parsed_date = start_dt
        if start_dt and parsed_date < start_dt:
            parsed_date = start_dt
        if end_dt and parsed_date > end_dt:
            parsed_date = end_dt
        day_key = parsed_date.isoformat()
        duration_minutes = _safe_positive_int(raw_item.get("duration_minutes"), fallback=90, maximum=1440)
        travel_buffer_minutes = _safe_positive_int(raw_item.get("travel_buffer_minutes"), fallback=30, maximum=480)
        if day_counts.get(day_key, 0) >= 15:
            continue
        planned_minutes = (duration_minutes or 0) + (travel_buffer_minutes or 0)
        if day_minutes.get(day_key, 0) + planned_minutes > 1080:
            continue
        event_type = str(raw_item.get("event_type") or "").strip() or None
        day_part = _normalize_day_part(raw_item.get("day_part"))
        meal_slot = _detect_meal_slot(
            title,
            raw_item.get("description"),
            raw_item.get("reason"),
            event_type,
            day_part,
        )
        if meal_slot:
            _, day_part, fallback_time = meal_slot
            if not time_value:
                time_value = fallback_time
            event_type = "food"
        if duplicate_key:
            existing_keys.add(duplicate_key)
        day_counts[day_key] = day_counts.get(day_key, 0) + 1
        day_minutes[day_key] = day_minutes.get(day_key, 0) + planned_minutes
        normalized.append(
            {
                "proposal_id": f"plan-{len(normalized) + 1}",
                "event_date": day_key,
                "time": time_value,
                "title": title[:120],
                "description": (str(raw_item.get("description") or "").strip() or None),
                "address": (str(raw_item.get("address") or "").strip() or None),
                "lat": raw_item.get("lat") if isinstance(raw_item.get("lat"), (int, float)) else None,
                "lng": raw_item.get("lng") if isinstance(raw_item.get("lng"), (int, float)) else None,
                "place_source": (str(raw_item.get("place_source") or "").strip() or None),
                "duration_minutes": duration_minutes,
                "travel_buffer_minutes": travel_buffer_minutes,
                "event_type": event_type,
                "day_part": day_part,
                "reason": (str(raw_item.get("reason") or "").strip() or None),
                "weather_note": (str(raw_item.get("weather_note") or "").strip() or None),
                "image": (str(raw_item.get("image") or raw_item.get("image_url") or "").strip() or None),
                "image_position": (str(raw_item.get("image_position") or "").strip() or None),
            }
        )
    return optimize_itinerary_plan_items(normalized)


def _plan_duplicate_key(title: Any, address: Any = None) -> str:
    title_text = re.sub(r"\s+", " ", str(title or "").strip().lower())
    address_text = re.sub(r"\s+", " ", str(address or "").strip().lower())
    if not title_text:
        return ""
    return f"{title_text}|{address_text}" if address_text else title_text


def _safe_positive_int(value: Any, fallback: int | None = None, maximum: int = 1440) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    if parsed < 0:
        return fallback
    return min(parsed, maximum)


def _normalize_day_part(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    aliases = {
        "morning": "morning",
        "утро": "morning",
        "day": "day",
        "afternoon": "day",
        "день": "day",
        "evening": "evening",
        "вечер": "evening",
        "night": "evening",
    }
    return aliases.get(normalized)


def _detect_meal_slot(*values: Any) -> tuple[str, str, str] | None:
    text = " ".join(str(value or "") for value in values).lower()
    if re.search(r"\b(breakfast)\b|завтрак", text):
        return "breakfast", "morning", "09:00"
    if re.search(r"\b(lunch)\b|обед", text):
        return "lunch", "day", "13:00"
    if re.search(r"\b(dinner)\b|ужин", text):
        return "dinner", "evening", "19:00"
    return None


def _normalize_currency_token(value: str | None, fallback: str = "RUB") -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"₽", "РУБ", "РУБ.", "РУБЛЬ", "РУБЛЯ", "РУБЛЕЙ"}:
        return "RUB"
    if normalized in {"$", "US$", "USD", "ДОЛЛАР", "ДОЛЛАРА", "ДОЛЛАРОВ", "БАКС", "БАКСА", "БАКСОВ"}:
        return "USD"
    if normalized in {"€", "EUR", "ЕВРО"}:
        return "EUR"
    if normalized in {"ФУНТ", "ФУНТА", "ФУНТОВ"}:
        return "GBP"
    if normalized == "ЛАРИ":
        return "GEL"
    if normalized in {"ЛИРА", "ЛИРЫ"}:
        return "TRY"
    if normalized in {"ДИРХАМ", "ДИРХАМА", "ДИРХАМОВ"}:
        return "AED"
    if normalized == "ТЕНГЕ":
        return "KZT"
    if re.fullmatch(r"[A-Z]{3}", normalized):
        return normalized
    return fallback


def _guess_expense_category(text: str, language: str) -> str:
    normalized = text.lower()
    if re.search(r"еда|ресторан|кафе|кофе|завтрак|обед|ужин|food|restaurant|cafe|coffee|lunch|dinner", normalized):
        return "food"
    if re.search(r"такси|метро|автобус|поезд|transport|taxi|metro|bus|train", normalized):
        return "transport"
    if re.search(r"музе|билет|экскурс|tickets?|museum|tour", normalized):
        return "tickets"
    if re.search(r"отель|жиль|hotel|apartment|stay", normalized):
        return "hotel"
    if re.search(r"развлеч|бар|клуб|концерт|парк|кино|аттракцион|entertainment|bar|club|concert|cinema|movie|show", normalized):
        return "entertainment"
    if re.search(r"сувенир|покуп|shop|shopping|souvenir", normalized):
        return "shopping"
    return "other"


def _is_likely_split_count_match(text: str, match: re.Match) -> bool:
    currency = str(match.group("currency") or "").strip()
    if currency:
        return False
    try:
        amount = float(match.group("amount").replace(",", "."))
    except (TypeError, ValueError):
        return False
    if amount > 20:
        return False
    before = text[max(0, match.start() - 16):match.start()].lower()
    return bool(re.search(r"(?:на|by|between)\s*$", before))


def _clean_expense_title_segment(segment: str) -> str:
    title = str(segment or "").strip(" .,:;—-")
    title = re.sub(r"^(?:и|а|на|за|for|and)\s+", "", title, flags=re.IGNORECASE).strip(" .,:;—-")
    title = re.sub(r"\s+(?:и|and)$", "", title, flags=re.IGNORECASE).strip(" .,:;—-")
    title = re.sub(
        r"^(?:добавь?|добавить|запиши|записать|внеси|внести|трат[уы]?|расход(?:ы)?|add|spent|expense)\s+",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip(" .,:;—-")
    return title


def _extract_expense_title(normalized: str, money_matches: list[re.Match], index: int, language: str) -> str:
    current = money_matches[index]
    next_match = money_matches[index + 1] if index + 1 < len(money_matches) else None
    title_source = normalized[current.end():next_match.start() if next_match else len(normalized)]
    title = _clean_expense_title_segment(title_source)
    if not title:
        previous_match = money_matches[index - 1] if index > 0 else None
        title_source = normalized[previous_match.end() if previous_match else 0:current.start()]
        title = _clean_expense_title_segment(title_source)
    return title[:80] or (f"Трата {index + 1}" if language == "ru" else f"Expense {index + 1}")


def _extract_simple_expense_proposals(question: str, trip_context: dict[str, Any], language: str) -> list[dict[str, Any]]:
    normalized = str(question or "").strip()
    if not normalized:
        return []
    default_currency = ((trip_context.get("expenses") or {}).get("base_currency") or "RUB").upper()
    money_matches = [
        match
        for match in MONEY_RE.finditer(normalized)
        if not _is_likely_split_count_match(normalized, match)
    ]
    if not money_matches:
        return []
    money_match = money_matches[0]
    amount = float(money_match.group("amount").replace(",", "."))
    currency = _normalize_currency_token(money_match.group("currency"), default_currency)
    if re.search(r"дневн|на\s+день|daily|per\s+day", normalized, re.IGNORECASE) and re.search(r"лимит|бюджет|limit|budget", normalized, re.IGNORECASE):
        return [
            {
                "proposal_id": "expense-1",
                "action": "set_daily_budget",
                "title": None,
                "category": None,
                "amount": None,
                "currency": currency,
                "expense_date": None,
                "note": None,
                "budget_amount": None,
                "daily_budget_amount": amount,
                "base_currency": currency,
            }
        ]
    if re.search(r"бюджет|budget", normalized, re.IGNORECASE):
        return [
            {
                "proposal_id": "expense-1",
                "action": "set_budget",
                "title": None,
                "category": None,
                "amount": None,
                "currency": currency,
                "expense_date": None,
                "note": None,
                "budget_amount": amount,
                "daily_budget_amount": None,
                "base_currency": currency,
            }
        ]
    if not re.search(r"добав|запиш|внес|потрат|трат|расход|раздел|подел|add|spent|expense|split", normalized, re.IGNORECASE):
        return []
    split_match = re.search(r"(?:на|между)\s+(\d{1,2}|двоих|троих|четверых)|split\s+(?:by|between)\s+(\d{1,2})", normalized, re.IGNORECASE)
    split_count = None
    if split_match:
        split_token = next((group for group in split_match.groups() if group), "")
        split_count = {"двоих": 2, "троих": 3, "четверых": 4}.get(split_token.lower())
        if split_count is None:
            try:
                split_count = int(split_token)
            except ValueError:
                split_count = None

    proposals: list[dict[str, Any]] = []
    for index, current_match in enumerate(money_matches[:8]):
        raw_amount = float(current_match.group("amount").replace(",", "."))
        current_currency = _normalize_currency_token(current_match.group("currency"), default_currency)
        current_split_count = split_count if len(money_matches) == 1 else None
        personal_amount = round(raw_amount / current_split_count, 2) if current_split_count and current_split_count > 1 else raw_amount
        title = _extract_expense_title(normalized, money_matches, index, language)
        proposals.append(
            {
                "proposal_id": f"expense-{index + 1}",
                "action": "create",
                "title": title,
                "category": _guess_expense_category(title, language),
                "amount": personal_amount,
                "currency": current_currency,
                "expense_date": None,
                "note": (
                    f"Доля 1/{current_split_count} от {raw_amount} {current_currency}"
                    if current_split_count and language == "ru"
                    else None
                ),
                "budget_amount": None,
                "daily_budget_amount": None,
                "base_currency": None,
                "split_count": current_split_count,
            }
        )
    return proposals


def _normalize_expense_proposals(proposals: Any, trip_context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(proposals, list):
        return []
    default_currency = ((trip_context.get("expenses") or {}).get("base_currency") or "RUB").upper()
    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(proposals[:8]):
        if not isinstance(raw_item, dict):
            continue
        action = str(raw_item.get("action") or "").strip().lower()
        if action == "add":
            action = "create"
        if action not in {"create", "set_budget", "set_daily_budget"}:
            continue
        currency = _normalize_currency_token(str(raw_item.get("currency") or ""), default_currency)
        expense_date = str(raw_item.get("expense_date") or "").strip() or None
        if expense_date:
            try:
                datetime.strptime(expense_date, "%Y-%m-%d")
            except ValueError:
                expense_date = None
        item = {
            "proposal_id": f"expense-{index + 1}",
            "action": action,
            "title": (str(raw_item.get("title") or "").strip() or None),
            "category": (str(raw_item.get("category") or "other").strip().lower() or "other"),
            "amount": None,
            "currency": currency,
            "expense_date": expense_date,
            "note": (str(raw_item.get("note") or "").strip() or None),
            "budget_amount": None,
            "daily_budget_amount": None,
            "base_currency": _normalize_currency_token(str(raw_item.get("base_currency") or ""), default_currency),
            "split_count": None,
        }
        try:
            if raw_item.get("amount") is not None:
                item["amount"] = float(raw_item.get("amount"))
            if raw_item.get("budget_amount") is not None:
                item["budget_amount"] = float(raw_item.get("budget_amount"))
            if raw_item.get("daily_budget_amount") is not None:
                item["daily_budget_amount"] = float(raw_item.get("daily_budget_amount"))
            if raw_item.get("split_count") is not None:
                item["split_count"] = int(raw_item.get("split_count"))
        except (TypeError, ValueError):
            pass
        if action == "create" and item["title"] and item["amount"] is not None:
            normalized.append(item)
        if action == "set_budget" and item["budget_amount"] is not None:
            normalized.append(item)
        if action == "set_daily_budget" and item["daily_budget_amount"] is not None:
            normalized.append(item)
    return normalized


def _build_local_expense_answer(question: str, trip_context: dict[str, Any], language: str) -> str | None:
    expenses = trip_context.get("expenses") or {}
    if expenses.get("visible") is False:
        return "Раздел трат скрыт для этой поездки." if language == "ru" else "Expenses are hidden for this trip."
    normalized = str(question or "").lower()
    base = expenses.get("base_currency") or "RUB"
    if re.search(r"сегодня|today|день|daily", normalized) and re.search(r"остат|сколько|left|remaining|limit", normalized):
        if expenses.get("daily_budget_amount") is None:
            return (
                f"Дневной лимит пока не задан. Сегодня уже потрачено {expenses.get('today_spent', 0)} {base}."
                if language == "ru"
                else f"Daily limit is not set. Today spent: {expenses.get('today_spent', 0)} {base}."
            )
        return (
            f"Сегодня потрачено {expenses.get('today_spent', 0)} {base}. Остаток на день: {expenses.get('today_remaining', 0)} {base}."
            if language == "ru"
            else f"Today spent: {expenses.get('today_spent', 0)} {base}. Left today: {expenses.get('today_remaining', 0)} {base}."
        )
    if re.search(r"категор|category", normalized):
        by_category = expenses.get("by_category") or {}
        if not by_category:
            return "Пока нет трат по категориям." if language == "ru" else "No category expenses yet."
        rows = sorted(by_category.items(), key=lambda item: item[1], reverse=True)
        return "\n".join([("Траты по категориям:" if language == "ru" else "Expenses by category:")] + [f"• {key}: {value} {base}" for key, value in rows])
    if re.search(r"хватит|прогноз|до конца|enough|forecast", normalized):
        remaining = expenses.get("remaining")
        if remaining is None:
            return "Общий бюджет пока не задан, поэтому прогноз сделать нельзя." if language == "ru" else "Trip budget is not set yet."
        return (
            f"Остаток бюджета: {remaining} {base}. Если дневной темп сохранится, ориентируйтесь на дневной лимит {expenses.get('daily_budget_amount') or 'не задан'} {base}."
            if language == "ru"
            else f"Budget left: {remaining} {base}. Daily limit: {expenses.get('daily_budget_amount') or 'not set'} {base}."
        )
    if re.search(r"больше всего|most|top", normalized):
        by_category = expenses.get("by_category") or {}
        if not by_category:
            return "Пока нет трат для анализа." if language == "ru" else "No expenses to analyze yet."
        category, amount = max(by_category.items(), key=lambda item: item[1])
        return (
            f"Больше всего ушло на категорию {category}: {amount} {base}."
            if language == "ru"
            else f"Top category is {category}: {amount} {base}."
        )
    if re.search(r"остат|remaining|left", normalized):
        remaining = expenses.get("remaining")
        if remaining is None:
            return f"Бюджет пока не задан. Всего потрачено {expenses.get('total_spent', 0)} {base}." if language == "ru" else f"Budget is not set. Total spent: {expenses.get('total_spent', 0)} {base}."
        return f"Остаток бюджета: {remaining} {base}." if language == "ru" else f"Budget left: {remaining} {base}."
    return None


def _normalize_event_change_proposals(proposals: Any) -> list[dict[str, Any]]:
    if not isinstance(proposals, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(proposals[:8]):
        if not isinstance(raw_item, dict):
            continue
        action = str(raw_item.get("action") or "").strip().lower()
        if action not in {"update", "delete", "create"}:
            continue
        try:
            target_event_id = int(raw_item.get("target_event_id")) if raw_item.get("target_event_id") is not None else None
        except (TypeError, ValueError):
            continue
        if action in {"update", "delete"} and target_event_id is None:
            continue
        event_date = str(raw_item.get("event_date") or "").strip() or None
        if event_date:
            try:
                datetime.strptime(event_date, "%Y-%m-%d")
            except ValueError:
                event_date = None
        time_value = str(raw_item.get("time") or "").strip() or None
        if time_value and not re.match(r"^\d{2}:\d{2}$", time_value):
            time_value = None
        normalized.append(
            {
                "proposal_id": f"event-change-{index + 1}",
                "action": action,
                "target_event_id": target_event_id,
                "event_date": event_date,
                "time": time_value,
                "title": (str(raw_item.get("title") or "").strip() or None),
                "description": (str(raw_item.get("description") or "").strip() or None),
                "address": (str(raw_item.get("address") or "").strip() or None),
                "reason": (str(raw_item.get("reason") or "").strip() or None),
                "old_value": (str(raw_item.get("old_value") or "").strip() or None),
                "new_value": (str(raw_item.get("new_value") or "").strip() or None),
                "requires_confirmation": bool(raw_item.get("requires_confirmation", action in {"delete", "create"})),
                "risk_level": str(raw_item.get("risk_level") or ("medium" if action in {"delete", "create"} else "low")).strip().lower(),
            }
        )
    return normalized


def _normalize_packing_recommendations(proposals: Any) -> list[dict[str, Any]]:
    if not isinstance(proposals, list):
        return []

    normalized: list[dict[str, Any]] = []
    allowed_actions = {"add", "remove", "move_to_carry_on", "keep"}
    for index, raw_item in enumerate(proposals[:12]):
        if not isinstance(raw_item, dict):
            continue
        item = str(raw_item.get("item") or "").strip()
        if not item:
            continue
        suggested_action = str(raw_item.get("suggested_action") or raw_item.get("action") or "keep").strip().lower()
        if suggested_action not in allowed_actions:
            suggested_action = "keep"
        priority = str(raw_item.get("priority") or ("must" if suggested_action == "move_to_carry_on" else "nice")).strip().lower()
        if priority not in {"must", "nice", "optional"}:
            priority = "nice"
        try:
            quantity = int(raw_item.get("quantity")) if raw_item.get("quantity") is not None else None
        except (TypeError, ValueError):
            quantity = None
        normalized.append(
            {
                "recommendation_id": f"packing-{index + 1}",
                "suggested_action": suggested_action,
                "item": item,
                "quantity": quantity if quantity and 1 <= quantity <= 99 else None,
                "target_section": (str(raw_item.get("target_section") or "").strip() or None),
                "reason": (str(raw_item.get("reason") or "").strip() or ("Можно применить к багажу.")),
                "reason_tags": raw_item.get("reason_tags") if isinstance(raw_item.get("reason_tags"), list) else [],
                "priority": priority,
                "requires_confirmation": bool(raw_item.get("requires_confirmation", suggested_action == "remove")),
                "risk_level": str(raw_item.get("risk_level") or ("medium" if suggested_action == "remove" else "low")).strip().lower(),
            }
        )
    return normalized


async def ask_travel_ai(
    city: str,
    question: str,
    language: str = "ru",
    start_date: str = "",
    end_date: str = "",
    avg_temp: Optional[float] = None,
    trip_type: str = "vacation",
    trip_profile: Optional[dict] = None,
    daily_forecast: Optional[list[dict[str, Any]]] = None,
    itinerary_events: Optional[list[dict[str, Any]]] = None,
    attractions: Optional[list[dict[str, Any]]] = None,
    trip_context: Optional[dict[str, Any]] = None,
) -> dict:
    """Ask the AI assistant a question about the trip destination."""
    import asyncio

    if trip_context is None:
        trip_context = build_ad_hoc_trip_context(
            city=city,
            start_date=start_date,
            end_date=end_date,
            avg_temp=avg_temp,
            trip_type=trip_type,
            trip_profile=trip_profile,
            daily_forecast=daily_forecast,
            cached_attractions=attractions,
            language=language,
        )

    trip = trip_context.get("trip") or {}
    profile = trip_context.get("trip_profile") or {}
    city = trip.get("city") or city
    start_date = str(trip.get("start_date") or start_date or "")
    end_date = str(trip.get("end_date") or end_date or "")
    itinerary_events = trip_context.get("events") or itinerary_events or []

    planning_intent = _detect_planning_intent(question)
    event_change_intent = _detect_event_change_intent(question, itinerary_events)
    food_intent = _detect_food_intent(question)
    expense_intent = _detect_expense_intent(question)
    packing_intent = _detect_packing_intent(question)
    
    model_candidates = _build_model_candidates(planning_intent, event_change_intent, food_intent)
    if packing_intent and GEMINI_COMPLEX_MODEL not in model_candidates:
        model_candidates = [GEMINI_COMPLEX_MODEL] + model_candidates

    packing_advice = build_packing_advice(question, trip_context, language)
    if packing_advice and not planning_intent and not event_change_intent:
        return {
            "answer": packing_advice["answer"],
            "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
            "plan_proposals": [],
            "event_change_proposals": [],
            "expense_proposals": [],
            "packing_recommendations": packing_advice["recommendations"],
            "command_context": build_packing_command_context(packing_advice["recommendations"]),
        }

    if expense_intent:
        simple_expense_proposals = _extract_simple_expense_proposals(question, trip_context, language)
        if simple_expense_proposals:
            action = simple_expense_proposals[0]["action"]
            if action == "set_budget":
                answer = (
                    "Нашёл бюджет поездки. Проверь сумму и применяй, если всё верно."
                    if language == "ru"
                    else "I found a trip budget. Review it and apply if it looks right."
                )
            elif action == "set_daily_budget":
                answer = (
                    "Нашёл дневной лимит. Проверь сумму и применяй, если всё верно."
                    if language == "ru"
                    else "I found a daily limit. Review it and apply if it looks right."
                )
            else:
                answer = (
                    "Нашёл трату. Проверь категорию и сумму перед добавлением."
                    if language == "ru"
                    else "I found an expense. Review the category and amount before adding it."
                )
            return {
                "answer": answer,
                "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                "plan_proposals": [],
                "event_change_proposals": [],
                "expense_proposals": simple_expense_proposals,
                "packing_recommendations": [],
            }
        local_expense_answer = _build_local_expense_answer(question, trip_context, language)
        if local_expense_answer:
            return {
                "answer": local_expense_answer,
                "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                "plan_proposals": [],
                "event_change_proposals": [],
                "expense_proposals": [],
                "packing_recommendations": [],
            }

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return _gemini_misconfigured_response(language)

    system = SYSTEM_PROMPT.format(
        trip_context_text=_format_trip_context_text(trip_context, language),
    )

    question_payload = _build_question_prefix(question, planning_intent, language)
    if event_change_intent and not planning_intent:
        question_payload = _build_event_change_prefix(question, language)
    elif expense_intent and not planning_intent:
        question_payload = _build_expense_question_prefix(question, language)
    elif packing_intent and not planning_intent:
        question_payload = _build_packing_question_prefix(question, language)
    elif food_intent and not planning_intent:
        question_payload = _build_food_question_prefix(question, language)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system}\n\n{question_payload}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.4 if event_change_intent else (0.7 if planning_intent else 0.85),
            "maxOutputTokens": 4500 if planning_intent else (1800 if event_change_intent else 800),
            "topP": 0.95,
            "thinkingConfig": {
                "thinkingBudget": 0,
            },
        }
    }
    tools_payload = _build_tools_payload(food_intent and not planning_intent and not event_change_intent and not expense_intent and not packing_intent)
    if (planning_intent or event_change_intent or expense_intent or packing_intent) and not tools_payload:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    if tools_payload:
        payload["tools"] = tools_payload

    max_retries = 3
    base_delay = 2.0  # start with 2 seconds

    try:
        timeout_seconds = 25.0 if food_intent else 15.0
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            last_status: int | None = None
            last_error_preview = ""
            for model_index, selected_model in enumerate(model_candidates):
                for attempt in range(max_retries):
                    gemini_url = _build_model_url(selected_model)
                    resp = await client.post(
                        f"{gemini_url}?key={api_key}",
                        json=payload,
                    )
                    last_status = resp.status_code
                    last_error_preview = resp.text[:200]

                    if resp.status_code == 429:
                        if attempt < max_retries - 1:
                            sleep_time = base_delay * (2 ** attempt)
                            print(
                                f"[AI] Gemini rate limit (429) on {selected_model}. "
                                f"Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})"
                            )
                            await asyncio.sleep(sleep_time)
                            continue
                        print(f"[AI] Gemini API error on {selected_model}: {resp.status_code} {last_error_preview}")
                        break

                    if resp.status_code != 200:
                        print(f"[AI] Gemini API error on {selected_model}: {resp.status_code} {last_error_preview}")
                        if _is_invalid_gemini_key_response(resp.status_code, last_error_preview):
                            return _gemini_misconfigured_response(language)
                        if model_index < len(model_candidates) - 1:
                            break
                        return {
                            "answer": "Извините, AI-ассистент временно недоступен. Попробуйте позже." if language == "ru" else "Sorry, AI assistant is temporarily unavailable.",
                            "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                            "plan_proposals": [],
                            "event_change_proposals": [],
                            "expense_proposals": [],
                            "packing_recommendations": [],
                        }

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return {
                            "answer": "Не удалось получить ответ." if language == "ru" else "Could not get a response.",
                            "suggestions": [],
                            "plan_proposals": [],
                            "event_change_proposals": [],
                            "expense_proposals": [],
                            "packing_recommendations": [],
                        }

                    answer = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if event_change_intent and not planning_intent:
                        payload_json = _extract_json_object(answer)
                        if payload_json:
                            parsed_answer = str(payload_json.get("answer") or "").strip()
                            change_proposals = _normalize_event_change_proposals(payload_json.get("event_change_proposals"))
                            if parsed_answer:
                                return {
                                    "answer": parsed_answer,
                                    "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                                    "plan_proposals": [],
                                    "event_change_proposals": change_proposals,
                                    "expense_proposals": [],
                                    "packing_recommendations": [],
                                }
                    if expense_intent and not planning_intent:
                        payload_json = _extract_json_object(answer)
                        if payload_json:
                            parsed_answer = str(payload_json.get("answer") or "").strip()
                            expense_proposals = _normalize_expense_proposals(payload_json.get("expense_proposals"), trip_context)
                            if parsed_answer:
                                return {
                                    "answer": parsed_answer,
                                    "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                                    "plan_proposals": [],
                                    "event_change_proposals": [],
                                    "expense_proposals": expense_proposals,
                                    "packing_recommendations": [],
                                }
                    if packing_intent and not planning_intent and not event_change_intent and not expense_intent:
                        payload_json = _extract_json_object(answer)
                        if payload_json:
                            parsed_answer = str(payload_json.get("answer") or "").strip()
                            packing_recs = _normalize_packing_recommendations(payload_json.get("packing_recommendations"))
                            if parsed_answer:
                                return {
                                    "answer": parsed_answer,
                                    "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                                    "plan_proposals": [],
                                    "event_change_proposals": [],
                                    "expense_proposals": [],
                                    "packing_recommendations": packing_recs,
                                }
                    fallback_json = _extract_json_object(answer)
                    if fallback_json:
                        parsed_answer = str(fallback_json.get("answer") or "").strip()
                        return {
                            "answer": parsed_answer or ("Готово, разобрал запрос." if language == "ru" else "Done, I parsed the request."),
                            "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                            "plan_proposals": _normalize_plan_proposals(
                                fallback_json.get("plan_proposals"),
                                start_date,
                                end_date,
                                trip_context.get("events") if isinstance(trip_context, dict) else None,
                            ) if fallback_json.get("plan_proposals") else [],
                            "event_change_proposals": _normalize_event_change_proposals(fallback_json.get("event_change_proposals")),
                            "expense_proposals": _normalize_expense_proposals(fallback_json.get("expense_proposals"), trip_context),
                            "packing_recommendations": _normalize_packing_recommendations(fallback_json.get("packing_recommendations")),
                        }
                    if answer.strip().startswith("{"):
                        return {
                            "answer": "Я разобрал запрос, но ответ пришёл в техническом формате. Попробуйте повторить команду чуть проще." if language == "ru" else "I parsed the request, but the answer came back in a technical format. Please try a simpler command.",
                            "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                            "plan_proposals": [],
                            "event_change_proposals": [],
                            "expense_proposals": [],
                            "packing_recommendations": [],
                        }
                    if planning_intent:
                        payload_json = _extract_json_object(answer)
                        if payload_json:
                            parsed_answer = str(payload_json.get("answer") or "").strip()
                            plan_proposals = _normalize_plan_proposals(
                                payload_json.get("plan_proposals"),
                                start_date,
                                end_date,
                                trip_context.get("events") if isinstance(trip_context, dict) else None,
                            )
                            if parsed_answer:
                                return {
                                    "answer": parsed_answer,
                                    "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                                    "plan_proposals": plan_proposals,
                                    "event_change_proposals": [],
                                    "expense_proposals": [],
                                    "packing_recommendations": [],
                                }
                    return {
                        "answer": answer.strip(),
                        "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                        "plan_proposals": [],
                        "event_change_proposals": [],
                        "expense_proposals": [],
                        "packing_recommendations": [],
                    }

            if last_status == 429:
                return {
                    "answer": "Извините, AI-ассистент слишком перегружен запросами. Попробуйте через пару минут." if language == "ru" else "Sorry, AI assistant is overwhelmed. Please try again in a few minutes.",
                    "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                    "plan_proposals": [],
                    "event_change_proposals": [],
                    "expense_proposals": [],
                    "packing_recommendations": [],
                }
            print(f"[AI] Gemini fallback exhausted. Last status={last_status}, error={last_error_preview}")
            return {
                "answer": "Извините, AI-ассистент временно недоступен. Попробуйте позже." if language == "ru" else "Sorry, AI assistant is temporarily unavailable.",
                "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3],
                "plan_proposals": [],
                "event_change_proposals": [],
                "expense_proposals": [],
                "packing_recommendations": [],
            }

    except Exception as e:
        print(f"[AI] Error: {e}")
        return {
            "answer": "Произошла ошибка при обращении к AI." if language == "ru" else "An error occurred with the AI.",
            "suggestions": [],
            "plan_proposals": [],
            "event_change_proposals": [],
            "expense_proposals": [],
            "packing_recommendations": [],
        }


def get_suggestions(language: str = "ru") -> list:
    """Get suggested questions for the chat."""
    return SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])
