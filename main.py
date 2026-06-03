import asyncio
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = "8420933081:AAH2mYV5Qvj6F6iFomFvlgdGgf6wKiDUeGI"

user_locations: dict[int, dict[str, float]] = {}


# Состояния для FSM
class OutfitState(StatesGroup):
    waiting_for_style = State()


# Клавиатуры
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Выбрать регион 📍"),
         KeyboardButton(text="Отправить геопозицию 📍", request_location=True)]
    ],
    resize_keyboard=True
)

weather_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Узнать погоду ☁️")]],
    resize_keyboard=True
)


# 🎨 Функция для создания инлайн-клавиатуры с кнопками стилей
def get_outfit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏃 Sport", callback_data="style_sport")
    builder.button(text="👔 Nefor", callback_data="style_nefor")
    builder.button(text="👕 Casual", callback_data="style_casual")
    builder.button(text="📦 Archive", callback_data="style_archive")
    builder.adjust(2)  # 2 кнопки в ряд
    return builder.as_markup()


# 🌡️ Функция для определения категории погоды по температуре
def get_weather_category(temp: float) -> int:
    if temp >= 25:
        return 1  # очень тепло
    elif temp >= 18:
        return 2  # тепло
    elif temp >= 10:
        return 3  # прохладно
    elif temp >= 0:
        return 4  # по-зимнему прохладно
    else:
        return 5  # мороз


# ☔ Функция проверки, идёт ли дождь
def is_raining(weather_code: int) -> bool:
    rain_codes = [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]
    return weather_code in rain_codes


# 🎨 Функция для отправки картинки с аутфитом
async def send_outfit_image(message: types.Message, style: str, category: int):
    # Определяем максимальный номер для каждого стиля
    max_files = {
        "sport": 5,
        "nefor": 5,
        "casual": 6,
        "archive": 5
    }

    # Проверяем, существует ли файл с таким номером
    if category > max_files.get(style, 5):
        category = max_files.get(style, 5)  # Берем максимальный доступный

    file_path =  f"https://raw.githubusercontent.com/Fog67/tg/main/{style}{category}.png"

    try:
        with open(file_path, 'rb') as photo:
            style_names = {
                "sport": " Sport",
                "nefor": " Nefor",
                "casual": " Casual",
                "archive": " Archive"
            }
            category_names = {
                1: "очень тепло",
                2: "тепло",
                3: "прохладно",
                4: "по-зимнему прохладно",
                5: "мороз",
                6: "очень холодно"
            }

            await message.answer_photo(
                photo=photo,
                caption=f"👕 {style_names[style]} - {category_names[category]}"
            )
    except FileNotFoundError:
        await message.answer(f"❌ Картинка не найдена: {file_path}")


# 🌤 Расшифровка кодов погоды WMO (Open-Meteo)
def decode_weather_code(code: int) -> str:
    codes = {
        0: ("☀️", "Ясно"),
        1: ("🌤", "Преимущественно ясно"),
        2: ("⛅", "Переменная облачность"),
        3: ("☁️", "Пасмурно"),
        45: ("🌫", "Туман"),
        48: ("🌫️", "Туман с изморозью"),
        51: ("🌦", "Слабая морось"),
        53: ("🌦", "Умеренная морось"),
        55: ("🌧", "Сильная морось"),
        56: ("🌧", "Ледяная морось"),
        57: ("🌧", "Сильная ледяная морось"),
        61: ("🌧", "Слабый дождь"),
        63: ("🌧", "Умеренный дождь"),
        65: ("🌧", "Сильный дождь"),
        66: ("🌨", "Ледяной дождь"),
        67: ("🌨", "Сильный ледяной дождь"),
        71: ("🌨", "Слабый снег"),
        73: ("🌨", "Умеренный снег"),
        75: ("❄️", "Сильный снегопад"),
        77: ("🌨", "Снежные зёрна"),
        80: ("🌦", "Ливневый дождь"),
        81: ("🌧", "Сильный ливень"),
        82: ("⛈", "Очень сильный ливень"),
        85: ("🌨", "Снежная крупа"),
        86: ("❄️", "Сильный град со снегом"),
        95: ("⛈", "Гроза"),
        96: ("⛈", "Гроза с градом"),
        99: ("⛈", "Сильная гроза с градом"),
    }
    emoji, desc = codes.get(code, ("❓", "Неизвестно"))
    return f"{emoji} {desc}"


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


async def handle_weather(message: types.Message, state: FSMContext):
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

        # Определяем категорию погоды
        temp = current["temperature_2m"]
        category = get_weather_category(temp)

        # Проверяем, идёт ли дождь
        weather_code = current["weather_code"]
        umbrella_message = ""
        if is_raining(weather_code):
            umbrella_message = "\n\n☔ **Совет: не забудь взять зонт!**"

        # Сохраняем температуру в state
        await state.update_data(temperature=temp, category=category)

        text = (
            f"🌤 **Погода сейчас**:\n\n"
            f"🌡 Температура: {temp}°C\n"
            f"{weather_emoji} {weather_desc.strip()}\n"
            f"💧 Осадки: {current['precipitation']} мм/ч\n"
            f"💨 Ветер: {current['wind_speed_10m']} м/с"
            f"{umbrella_message}\n\n"
            f"👔 **Выбери стиль образа:**"
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_outfit_keyboard()
        )

    except requests.exceptions.RequestException:
        await message.answer("❌ Не удалось получить данные о погоде. Попробуй позже.")


# 🎨 Обработчик выбора стиля аутфита
async def handle_outfit_choice(callback: types.CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_", "")

    # Получаем данные о погоде из state
    data = await state.get_data()
    category = data.get("category", 3)  # По умолчанию прохладно

    # Отправляем соответствующую картинку
    await send_outfit_image(callback.message, style, category)
    await callback.answer()


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(handle_region_button, F.text == "Выбрать регион 📍")
    dp.message.register(handle_location, F.location)
    dp.message.register(handle_weather, F.text == "Узнать погоду ☁️")

    # Регистрируем обработчик callback для кнопок стилей
    dp.callback_query.register(handle_outfit_choice, F.data.startswith("style_"))

    print("🤖 Бот запущен. Для остановки нажмите Ctrl+C.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())