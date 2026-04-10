import os
import httpx
from typing import Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"

# By default, use Google's official URL. 
# But let this be overridable if the user buys a key from a third-party proxy service.
DEFAULT_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SYSTEM_PROMPT = """Ты — умный и интеллигентный AI-помощник для путешественников в приложении Luggify.
Разговаривай по-человечески, вежливо и естественно, как опытный гид. Избегай чрезмерного использования сленга и фамильярности. 
Твоя задача — давать полезную, точную и интересную информацию, сохраняя профессионализм и дружелюбие.

ОЧЕНЬ ВАЖНО: 
1. Не повторяй каждый раз заготовленные вводные фразы ("В Будапеште...", "Этот город славится..."). Начинай сразу с ответа.
2. Используй абзацы и списки (1., 2., 3., 4., 5.) с переносом строки для удобства чтения.
3. Добавляй 1-2 эмодзи в текст, но не перебарщивай.
4. Отвечай кратко (до 5 предложений), но емко. Пользователь уже знает, в каком он городе.

Контекст поездки пользователя:
- Город: {city}
- Даты: {start_date} — {end_date}
- Погода: {avg_temp}°C
- Формат: {trip_type}

На каком языке был задан вопрос — на таком и отвечай."""

SUGGESTED_QUESTIONS = {
    "ru": [
        "Что обязательно попробовать из еды?",
        "Какие достопримечательности must-see?",
        "Как лучше перемещаться по городу?",
        "Есть ли опасные районы?",
        "Что купить в подарок?",
        "Какие местные обычаи нужно знать?",
    ],
    "en": [
        "What food should I try?",
        "What are the must-see places?",
        "Best way to get around?",
        "Any unsafe areas to avoid?",
        "What to buy as a souvenir?",
        "Local customs I should know?",
    ]
}


async def ask_travel_ai(
    city: str,
    question: str,
    language: str = "ru",
    start_date: str = "",
    end_date: str = "",
    avg_temp: Optional[float] = None,
    trip_type: str = "vacation",
) -> dict:
    """Ask the AI assistant a question about the trip destination."""
    import asyncio
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "answer": "AI-ассистент не настроен. Добавьте GEMINI_API_KEY в .env" if language == "ru" else "AI assistant not configured. Add GEMINI_API_KEY to .env",
            "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3]
        }

    system = SYSTEM_PROMPT.format(
        city=city,
        start_date=start_date or "не указаны",
        end_date=end_date or "не указаны",
        avg_temp=avg_temp if avg_temp else "неизвестна",
        trip_type=trip_type,
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system}\n\nВопрос пользователя: {question}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 600,
            "topP": 0.95,
        }
    }

    max_retries = 3
    base_delay = 2.0  # start with 2 seconds

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(max_retries):
                # Dynamically load base url to allow proxy services
                gemini_url = os.getenv("GEMINI_BASE_URL", DEFAULT_URL)
                
                resp = await client.post(
                    f"{gemini_url}?key={api_key}",
                    json=payload,
                )
                
                if resp.status_code == 429:
                    if attempt < max_retries - 1:
                        sleep_time = base_delay * (2 ** attempt)
                        print(f"[AI] Gemini rate limit (429). Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        print(f"[AI] Gemini API error: {resp.status_code} {resp.text[:200]}")
                        return {
                            "answer": "Извините, AI-ассистент слишком перегружен запросами. Попробуйте через пару минут." if language == "ru" else "Sorry, AI assistant is overwhelmed. Please try again in a few minutes.",
                            "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3]
                        }
                
                if resp.status_code != 200:
                    print(f"[AI] Gemini API error: {resp.status_code} {resp.text[:200]}")
                    return {
                        "answer": "Извините, AI-ассистент временно недоступен. Попробуйте позже." if language == "ru" else "Sorry, AI assistant is temporarily unavailable.",
                        "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3]
                    }

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return {
                        "answer": "Не удалось получить ответ." if language == "ru" else "Could not get a response.",
                        "suggestions": []
                    }

                answer = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                
                return {
                    "answer": answer.strip(),
                    "suggestions": SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])[:3]
                }

    except Exception as e:
        print(f"[AI] Error: {e}")
        return {
            "answer": "Произошла ошибка при обращении к AI." if language == "ru" else "An error occurred with the AI.",
            "suggestions": []
        }


def get_suggestions(language: str = "ru") -> list:
    """Get suggested questions for the chat."""
    return SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS["ru"])
