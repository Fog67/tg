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

# 📍 Клавиатура погоды с кнопкой "Назад"
weather_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Узнать погоду ☁️")],
        [KeyboardButton(text="◀️ Назад")]
    ],
    resize_keyboard=True
)


#  Функция для создания инлайн-клавиатуры с кнопками стилей и "Назад"
def get_outfit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏃 Sport", callback_data="style_sport")
    builder.button(text=" Nefor", callback_data="style_nefor")
    builder.button(text="👕 Casual", callback_data="style_casual")
    builder.button(text="📦 Archive", callback_data="style_archive")
    builder.button(text="◀️ Назад", callback_data="back_to_weather")
    builder.adjust(2)
    return builder.as_markup()


# 🌡️ Функция для определения категории погоды по ощущаемой температуре и ветру
def get_weather_category(apparent_temp: float, wind_speed: float) -> int:
    if apparent_temp >= 25:
        category = 1
    elif apparent_temp >= 18:
        category = 2
    elif apparent_temp >= 10:
        category = 3
    elif apparent_temp >= 0:
        category = 4
    else:
        category = 5

    if wind_speed > 10 and category < 5:
        category += 1

    if category > 5:
        category = 5

    return category


# ☔ Функция проверки, идёт ли дождь
def is_raining(weather_code: int) -> bool:
    rain_codes = [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]
    return weather_code in rain_codes


#  Функция для отправки картинки с аутфитом
async def send_outfit_image(message: types.Message, style: str, category: int):
    max_files = {
        "sport": 5,
        "nefor": 5,
        "casual": 6,
        "archive": 5
    }

    if category > max_files.get(style, 5):
        category = max_files.get(style, 5)

    file_url = f"https://raw.githubusercontent.com/Fog67/tg/main/{style}{category}.png"

    style_names = {
        "sport": "🏃 Sport",
        "nefor": "👔 Nefor",
        "casual": " Casual",
        "archive": " Archive"
    }

    category_names = {
        1: "очень тепло",
        2: "тепло",
        3: "прохладно",
        4: "по-зимнему прохладно",
        5: "мороз"
    }

    try:
        await message.answer_photo(
            photo=file_url,
            caption=f"👕 {style_names[style]} - {category_names[category]}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки картинки: {e}")


# 🌤 Расшифровка кодов погоды WMO (Open-Meteo)
def decode_weather_code(code: int) -> str:
    codes = {
        0: ("☀️", "Ясно"),
        1: ("🌤", "Преимущественно ясно"),
        2: ("⛅", "Переменная облачность"),
        3: ("️", "Пасмурно"),
        45: ("🌫", "Туман"),
        48: ("🌫️", "Туман с изморозью"),
        51: ("🌦", "Слабая морось"),
        53: ("🌦", "Умеренная морось"),
        55: ("🌧", "Сильная морось"),
        56: ("🌧", "Ледяная морось"),
        57: ("🌧", "Сильная ледяная морось"),
        61: ("🌧", "Слабый дождь"),
        63: ("🌧", "Умеренный дождь"),
        65: ("", "Сильный дождь"),
        66: ("🌨", "Ледяной дождь"),
        67: ("🌨", "Сильный ледяной дождь"),
        71: ("🌨", "Слабый снег"),
        73: ("🌨", "Умеренный снег"),
        75: ("❄️", "Сильный снегопад"),
        77: ("🌨", "Снежные зёрна"),
        80: ("🌦", "Ливневый дождь"),
        81: ("🌧", "Сильный ливень"),
        82: ("", "Очень сильный ливень"),
        85: ("🌨", "Снежная крупа"),
        86: ("️", "Сильный град со снегом"),
        95: ("⛈", "Гроза"),
        96: ("", "Гроза с градом"),
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
    await message.answer(" Отправь геопозицию")


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


# ◀️ Обработчик кнопки "Назад" из клавиатуры погоды → возвращает к старту
async def handle_back_to_start(message: types.Message):
    await message.answer(
        "Привет! Выбери регион, в котором хочешь узнать погоду",
        reply_markup=start_keyboard
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
        f"&current=temperature_2m,apparent_temperature,weather_code,precipitation,wind_speed_10m"
    )

    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        current = data["current"]

        weather_emoji, weather_desc = decode_weather_code(current["weather_code"]).split(" ", 1)

        temp = current["temperature_2m"]
        apparent_temp = current["apparent_temperature"]
        wind_speed = current["wind_speed_10m"]

        category = get_weather_category(apparent_temp, wind_speed)

        weather_code = current["weather_code"]
        umbrella_message = ""
        if is_raining(weather_code):
            umbrella_message = "\n\n☔ **Совет: не забудь взять зонт!**"

        wind_message = ""
        if wind_speed > 10:
            wind_message = f"\n💨 **Сильный ветер! Ощущается как {apparent_temp}°C**"

        await state.update_data(
            temperature=temp,
            apparent_temperature=apparent_temp,
            wind_speed=wind_speed,
            category=category
        )

        text = (
            f"🌤 **Погода сейчас**:\n\n"
            f"🌡 Температура: {temp}°C\n"
            f" Ощущается как: {apparent_temp}°C\n"
            f"{weather_emoji} {weather_desc.strip()}\n"
            f"💧 Осадки: {current['precipitation']} мм/ч\n"
            f"💨 Ветер: {wind_speed} м/с"
            f"{wind_message}"
            f"{umbrella_message}\n\n"
            f" **Выбери стиль образа:**"
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

    data = await state.get_data()
    category = data.get("category", 3)

    await send_outfit_image(callback.message, style, category)
    await callback.answer()


# ◀️ Обработчик кнопки "Назад" из инлайн-клавиатуры стилей → возвращает к клавиатуре погоды
async def handle_back_to_weather(callback: types.CallbackQuery):
    await callback.message.answer(
        "🌤 Нажми кнопку, чтобы узнать погоду",
        reply_markup=weather_menu_keyboard
    )
    await callback.answer()


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(handle_region_button, F.text == "Выбрать регион ")
    dp.message.register(handle_location, F.location)
    dp.message.register(handle_weather, F.text == "Узнать погоду ☁️")

    # Обработчик кнопки "Назад" из клавиатуры погоды
    dp.message.register(handle_back_to_start, F.text == "️ Назад")

    dp.callback_query.register(handle_outfit_choice, F.data.startswith("style_"))
    # Обработчик кнопки "Назад" из инлайн-клавиатуры стилей
    dp.callback_query.register(handle_back_to_weather, F.data == "back_to_weather")

    print("🤖 Бот запущен. Для остановки нажмите Ctrl+C.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())