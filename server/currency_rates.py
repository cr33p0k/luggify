import time
from typing import Optional

import httpx


EXCHANGE_RATES: dict[str, float] = {}
EXCHANGE_RATES_UPDATED_AT = 0.0
EXCHANGE_RATE_PROVIDER = "open.er-api.com"
EXCHANGE_RATE_TTL_SECONDS = 12 * 60 * 60


def normalize_currency(value: str | None, fallback: str = "RUB") -> str:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return fallback
    if len(normalized) != 3 or not normalized.isalpha():
        return fallback
    return normalized


async def refresh_exchange_rates() -> None:
    global EXCHANGE_RATES_UPDATED_AT

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://open.er-api.com/v6/latest/RUB")
        if resp.status_code != 200:
            raise RuntimeError(f"exchange rates request failed: {resp.status_code}")
        data = resp.json()
        rates = data.get("rates", {})
        EXCHANGE_RATES.clear()
        EXCHANGE_RATES.update(
            {
                str(currency).upper(): 1.0 / float(rate)
                for currency, rate in rates.items()
                if rate and float(rate) > 0
            }
        )
        EXCHANGE_RATES["RUB"] = 1.0
        EXCHANGE_RATES_UPDATED_AT = time.time()


async def get_rub_rate(currency: str) -> float:
    normalized_currency = normalize_currency(currency)
    if normalized_currency == "RUB":
        return 1.0

    now = time.time()
    if (
        normalized_currency not in EXCHANGE_RATES
        or now - EXCHANGE_RATES_UPDATED_AT > EXCHANGE_RATE_TTL_SECONDS
    ):
        try:
            await refresh_exchange_rates()
            print(
                "Exchange rates updated: "
                f"EUR={EXCHANGE_RATES.get('EUR', 0):.1f} RUB, "
                f"USD={EXCHANGE_RATES.get('USD', 0):.1f} RUB"
            )
        except Exception as exc:
            print(f"Exchange rates error: {exc}")

    return EXCHANGE_RATES.get(normalized_currency, 0)


async def convert_currency_amount(
    amount: float,
    from_currency: str,
    to_currency: str = "RUB",
) -> Optional[dict[str, float | str]]:
    source = normalize_currency(from_currency)
    target = normalize_currency(to_currency)
    numeric_amount = float(amount)
    if numeric_amount < 0:
        return None
    if source == target:
        return {
            "amount": round(numeric_amount, 2),
            "rate": 1.0,
            "provider": EXCHANGE_RATE_PROVIDER,
            "rate_date": time.strftime("%Y-%m-%d"),
        }

    source_rub_rate = await get_rub_rate(source)
    target_rub_rate = await get_rub_rate(target)
    if source_rub_rate <= 0 or target_rub_rate <= 0:
        return None

    amount_rub = numeric_amount * source_rub_rate
    converted = amount_rub / target_rub_rate
    return {
        "amount": round(converted, 2),
        "rate": source_rub_rate / target_rub_rate,
        "provider": EXCHANGE_RATE_PROVIDER,
        "rate_date": time.strftime("%Y-%m-%d"),
    }
