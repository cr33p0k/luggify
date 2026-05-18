from __future__ import annotations

import re
from typing import Literal

AssistantIntent = Literal[
    "packing",
    "expenses",
    "plan",
    "events",
    "today",
    "weather",
    "help",
    "trip_picker",
    "unknown",
]


INTENT_EXAMPLES = {
    "ru": {
        "plan": "План на завтра сбалансированный",
        "packing": "Что осталось собрать?",
        "expenses": "Сколько осталось сегодня?",
        "events": "Сдвинь весь день на час позже",
        "today": "Сегодня",
        "weather": "Что поменять из-за дождя?",
        "trip_picker": "Выбрать поездку",
    },
    "en": {
        "plan": "Balanced plan for tomorrow",
        "packing": "What is left to pack?",
        "expenses": "How much is left today?",
        "events": "Move the whole day one hour later",
        "today": "Today",
        "weather": "What should change because of rain?",
        "trip_picker": "Choose trip",
    },
}


INTENT_HELP_RU = """**План**
План на завтра лёгкий
Насыщенный план на третий день
Оптимизируй маршрут

**Вещи**
Что осталось собрать?
Что взять в ручную кладь?
Сделай список легче

**Траты**
Добавь 12 EUR кофе
Поставь дневной лимит 50 EUR
Сколько осталось сегодня?

**События**
Перенеси музей на вечер
Сдвинь весь день на час позже
Добавь перерыв после обеда

**Сегодня**
Покажи сегодняшний бриф"""


INTENT_HELP_EN = """**Plan**
Easy plan for tomorrow
Rich plan for the third day
Optimize itinerary

**Packing**
What is left to pack?
What should go in carry-on?
Make the list lighter

**Expenses**
Add 12 EUR coffee
Set daily limit 50 EUR
How much is left today?

**Events**
Move museum to evening
Shift the whole day one hour later
Add a break after lunch

**Today**
Show today's brief"""


EXPENSE_INTENT_RE = re.compile(
    r"(?:"
    r"\b(?:бюджет|траты?|трату|тратам|расход(?:ы|ов|ом)?|потрат(?:ил|ила|или|ить)?|остат(?:ок|ось)?|"
    r"expense|expenses|budget|spent|spend|remaining|left|limit)\b|"
    r"\d+(?:[.,]\d+)?\s*(?:₽|руб\.?|рублей|рубля|евро|eur|€|доллар(?:ов|а)?|бакс(?:ов|а)?|usd|\$|[a-zA-Z]{3})(?=$|\s|[.,;:!?])"
    r")",
    re.IGNORECASE,
)

PACKING_INTENT_RE = re.compile(
    r"добав|отмет|удал|убер|перелож|перемест|рюкзак|чемодан|ручн|вещ|собра|забыл|"
    r"pack|bag|backpack|carry|suitcase|luggage",
    re.IGNORECASE,
)


def is_expense_intent(text: str) -> bool:
    return bool(EXPENSE_INTENT_RE.search(str(text or "").strip().lower().replace("ё", "е")))


def is_packing_intent(text: str) -> bool:
    normalized = str(text or "").strip().lower().replace("ё", "е")
    return bool(PACKING_INTENT_RE.search(normalized)) and not is_expense_intent(normalized)


def detect_assistant_intent(text: str, language: str = "ru") -> AssistantIntent:
    normalized = " ".join(str(text or "").strip().lower().replace("ё", "е").split())
    if not normalized:
        return "unknown"
    if re.fullmatch(r"/?help|помощь", normalized):
        return "help"
    if re.search(r"выбрать поездк|сменить поездк|choose trip|change trip", normalized):
        return "trip_picker"
    if re.search(r"сегодня|today|/today", normalized):
        return "today"
    if re.search(r"план|маршрут|куда сход|что посет|route|itinerary|plan", normalized):
        return "plan"
    if is_expense_intent(normalized):
        return "expenses"
    if is_packing_intent(normalized):
        return "packing"
    if re.search(r"перенеси|сдвин|удали.*событ|добавь.*перерыв|event|move|shift|delete", normalized):
        return "events"
    if re.search(r"погод|дожд|жар|ветер|weather|rain|heat|wind", normalized):
        return "weather"
    return "unknown"


def build_assistant_help_text(language: str = "ru") -> str:
    return INTENT_HELP_EN if language == "en" else INTENT_HELP_RU


def build_unknown_intent_message(language: str = "ru") -> str:
    examples = INTENT_EXAMPLES.get(language, INTENT_EXAMPLES["ru"])
    if language == "en":
        return (
            "I am not sure which action you want. Try one of these:\n"
            f"• {examples['plan']}\n"
            f"• {examples['packing']}\n"
            f"• {examples['expenses']}"
        )
    return (
        "Не до конца понял, какое действие нужно. Попробуйте так:\n"
        f"• {examples['plan']}\n"
        f"• {examples['packing']}\n"
        f"• {examples['expenses']}"
    )
