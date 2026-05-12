import asyncio
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo  # ✅ Импортируем WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = "8420933081:AAH2mYV5Qvj6F6iFomFvlgdGgf6wKiDUeGI"

user_locations: dict[int, dict[str, float]] = {}

# 🔗 Ссылки на Telegraph-страницы
HELP_URLS = {
    "start": "https://telegra.ph/Help-start-05-12",
    "weather": "https://telegra.ph/help-weather-05-12",
    "outfit": "https://telegra.ph/help-weather-05-12-2",
}

# Клавиатуры
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Выбрать регион 📍"),
         KeyboardButton(text="Отправить геопозицию 📍", request_location=True)],
        [KeyboardButton(text="Помощь: Старт ❓")]  # 📝 Отправит инлайн-кнопку с Web App
    ],
    resize_keyboard=True
)

weather_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Узнать погоду ☁️")],
        [KeyboardButton(text="Помощь: Погода ❓")]  # 📝 Отправит инлайн-кнопку с Web App
    ],
    resize_keyboard=True
)


# 🎨 Инлайн-клавиатура с кнопкой "Подобрать образ"
def get_outfit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Casual", callback_data="outfit_placeholder")
    builder.button(text="Opium", callback_data="outfit_placeholder")
    builder.button(text="Techwear", callback_data="outfit_placeholder")
    builder.button(text="Sport", callback_data="outfit_placeholder")
    # ✅ Кнопка с Web App — открывается внутри Telegram
    builder.button(text="Помощь: Образ ❓", web_app=WebAppInfo(url=HELP_URLS["outfit"]))
    builder.adjust(1)
    return builder.as_markup()


# 🌤 Расшифровка кодов погоды (без изменений)
def decode_weather_code(code: int) -> str:
    codes = {
        0: ("☀️", "Ясно"), 1: ("🌤", "Преимущественно ясно"), 2: ("⛅", "Переменная облачность"),
        3: ("☁️", "Пасмурно"), 45: ("🌫", "Туман"), 48: ("🌫️", "Туман с изморозью"),
        51: ("🌦", "Слабая морось"), 53: ("🌦", "Умеренная морось"), 55: ("🌧", "Сильная морось"),
        56: ("🌧", "Ледяная морось"), 57: ("🌧", "Сильная ледяная морось"),
        61: ("🌧", "Слабый дождь"), 63: ("🌧", "Умеренный дождь"), 65: ("🌧", "Сильный дождь"),
        66: ("🌨", "Ледяной дождь"), 67: ("🌨", "Сильный ледяной дождь"),
        71: ("🌨", "Слабый снег"), 73: ("🌨", "Умеренный снег"), 75: ("❄️", "Сильный снегопад"),
        77: ("🌨", "Снежные зёрна"), 80: ("🌦", "Ливневый дождь"), 81: ("🌧", "Сильный ливень"),
        82: ("⛈", "Очень сильный ливень"), 85: ("🌨", "Снежная крупа"),
        86: ("❄️", "Сильный град со снегом"), 95: ("⛈", "Гроза"),
        96: ("⛈", "Гроза с градом"), 99: ("⛈", "Сильная гроза с градом"),
    }
    emoji, desc = codes.get(code, ("❓", "Неизвестно"))
    return f"{emoji} {desc}"


# 🧩 Вспомогательная функция: создаёт инлайн-клавиатуру с Web App-кнопкой
def get_help_webapp_keyboard(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📖 Открыть справку", web_app=WebAppInfo(url=url))
    builder.adjust(1)
    return builder.as_markup()


# Хендлеры
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Выбери регион, в котором хочешь узнать погоду",
        reply_markup=start_keyboard
    )


async def handle_region_button(message: types.Message):
    await message.answer("📍 Отправь геопозицию")


async def handle_location(message: types.Message):
    if message.location is None:
        return

    user_id = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude

    user_locations[user_id] = {"lat": lat, "lon": lon}

    await message.reply(
        f"✅ Координаты сохранены:\n🌐 {lat}, {lon}",
        reply_markup=weather_menu_keyboard
    )


async def handle_weather(message: types.Message):
    user_id = message.from_user.id

    if user_id not in user_locations:
        await message.answer("❌ Сначала отправь геопозицию через кнопку 📍")
        return

    lat = user_locations[user_id]["lat"]
    lon = user_locations[user_id]["lon"]

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weather_code,precipitation,wind_speed_10m"
    )

    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        current = data["current"]

        weather_emoji, weather_desc = decode_weather_code(current["weather_code"]).split(" ", 1)

        text = (
            f"🌤 **Погода сейчас**:\n\n"
            f"🌡 Температура: {current['temperature_2m']}°C\n"
            f"{weather_emoji} {weather_desc.strip()}\n"
            f"💧 Осадки: {current['precipitation']} мм/ч\n"
            f"💨 Ветер: {current['wind_speed_10m']} м/с\n"
            f"Выбери стиль образа:"
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_outfit_keyboard()
        )

    except requests.exceptions.RequestException:
        await message.answer("❌ Не удалось получить данные о погоде. Попробуй позже.")


# ➕ Обработчики для reply-кнопок "Помощь" — отправляют инлайн-кнопку с Web App
async def handle_help_start(message: types.Message):
    url = HELP_URLS.get("start")
    await message.answer(
        "📖 Справка откроется внизу экрана 👇",
        reply_markup=get_help_webapp_keyboard(url)
    )


async def handle_help_weather(message: types.Message):
    url = HELP_URLS.get("weather")
    await message.answer(
        "📖 Справка откроется внизу экрана 👇",
        reply_markup=get_help_webapp_keyboard(url)
    )


# ➕ Обработчик для инлайн-кнопки "Помощь: Образ" — Web App уже в кнопке
async def handle_help_callback(callback: types.CallbackQuery):
    # Кнопка с web_app не генерирует callback_query при нажатии,
    # но хендлер оставлен на случай изменений в будущем
    await callback.answer("ℹ️ Справка откроется внутри Telegram", show_alert=False)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(handle_region_button, F.text == "Выбрать регион 📍")
    dp.message.register(handle_location, F.location)
    dp.message.register(handle_weather, F.text == "Узнать погоду ☁️")

    # ✅ Хендлеры для reply-кнопок помощи
    dp.message.register(handle_help_start, F.text == "Помощь: Старт ❓")
    dp.message.register(handle_help_weather, F.text == "Помощь: Погода ❓")

    # ✅ Хендлер для инлайн-кнопки (опционально)
    dp.callback_query.register(handle_help_callback, F.data == "help_outfit")

    print("🤖 Бот запущен. Для остановки нажмите Ctrl+C.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())