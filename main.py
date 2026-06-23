import os
import base64
import json
import asyncio
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

APP_NAME = os.getenv("APP_NAME", "Stockity AI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
PORT = int(os.getenv("PORT", "8000"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ВАЖЛИВО:
# Цей варіант працює з твоєю структурою GitHub, де index.html/app.js/styles.css лежать в корені.
STATIC_DIR = BASE_DIR

app = FastAPI(title=APP_NAME)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


def fallback_analysis(asset: Optional[str] = None):
    return {
        "asset": asset or "Ринок / графік",
        "trend": "Потрібен OPENAI_API_KEY для реального аналізу",
        "signal": "Нейтрально",
        "probability_up": 50,
        "probability_down": 50,
        "confidence": "Низька",
        "support": "Зона не визначена",
        "resistance": "Зона не визначена",
        "market_state": "Не визначено",
        "entry_zone": "Не визначено",
        "timeframe": "За фото",
        "reasoning": "OPENAI_API_KEY не додано в Railway Variables, тому зараз працює демо-відповідь.",
        "risk_note": "Це не фінансова порада. Аналіз має ймовірнісний характер."
    }


@app.get("/")
async def home():
    index_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html не знайдено в корені репозиторію")
    return FileResponse(index_path)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "app": APP_NAME,
        "openai_key": bool(OPENAI_API_KEY),
        "telegram_bot": bool(BOT_TOKEN),
        "webapp_url": WEBAPP_URL or None
    }


@app.post("/api/analyze")
async def analyze_chart(
    file: UploadFile = File(...),
    asset: Optional[str] = Form(default=None)
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Завантаж фото графіка у форматі image/*")

    image_bytes = await file.read()

    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Фото завелике. Максимум 8 MB")

    if not OPENAI_API_KEY:
        return fallback_analysis(asset)

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = file.content_type

    client = OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = """
Ти професійний технічний аналітик фінансових ринків.
Твоє завдання — проаналізувати тільки те, що видно на фото графіка.
Не гарантуй результат. Не обіцяй прибуток. Не пиши "100% сигнал".
Відповідь має бути короткою, структурованою, українською мовою.
Поверни тільки валідний JSON без markdown.
"""

    user_prompt = f"""
Актив: {asset or "невідомий"}.

Проаналізуй фото графіка і поверни JSON з такими полями:
asset, trend, signal, probability_up, probability_down, confidence, support, resistance,
market_state, entry_zone, timeframe, reasoning, risk_note.

Правила:
- signal: тільки "Вгору", "Вниз" або "Нейтрально"
- probability_up і probability_down: числа 0-100
- confidence: тільки "Низька", "Середня" або "Висока"
- support/resistance: якщо ціни не видно, пиши "Зона не визначена"
- market_state: наприклад "Трендовий", "Флет", "Імпульсний", "Невизначений"
- entry_zone: якщо немає чіткої точки, пиши "Краще чекати підтвердження"
- reasoning: 2-4 короткі речення
- risk_note: "Це не фінансова порада. Аналіз має ймовірнісний характер."
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.2,
            max_tokens=800
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        data.setdefault("asset", asset or "Ринок / графік")
        data.setdefault("risk_note", "Це не фінансова порада. Аналіз має ймовірнісний характер.")
        return data

    except Exception as e:
        return {
            **fallback_analysis(asset),
            "trend": "AI помилка",
            "reasoning": f"AI аналіз не спрацював: {str(e)[:220]}"
        }


async def run_bot():
    if not BOT_TOKEN:
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message):
        url = WEBAPP_URL or ""
        if not url:
            await message.answer(
                "WEBAPP_URL не додано в Railway Variables. Додай посилання на Railway-домен."
            )
            return

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📸 Відкрити AI аналіз",
                        web_app=WebAppInfo(url=url)
                    )
                ]
            ]
        )

        await message.answer(
            "📊 Відкрий додаток, сфотографуй графік і отримай AI-аналіз.\n\n"
            "Аналіз має ймовірнісний характер і не є фінансовою порадою.",
            reply_markup=kb
        )

    await dp.start_polling(bot)


async def main():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)

    if BOT_TOKEN:
        await asyncio.gather(server.serve(), run_bot())
    else:
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
