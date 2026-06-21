import asyncio
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re
from datetime import datetime

BOT_TOKEN = "8420933081:AAH2mYV5Qvj6F6iFomFvlgdGgf6wKiDUeGI"

user_locations: dict[int, dict[str, float]] = {}
user_sensitivity: dict[int, int] = {}
user_notification_time: dict[int, str] = {}  # Хранит время в формате "ЧЧ:ММ"
user_notifications_enabled: dict[int, bool] = {}  # Включены ли уведомления


# Состояния для FSM
class OutfitState(StatesGroup):
    waiting_for_style = State()
    waiting_for_time = State()


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

# 🌡️ Клавиатура выбора восприимчивости
sensitivity_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Часто мерзну")],
        [KeyboardButton(text="Нормальная восприимчивость")],
        [KeyboardButton(text="Часто жарко")]
    ],
    resize_keyboard=True
)

# ⏰ Клавиатура для настройки уведомлений
notification_time_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔕 не хочу получать уведомления")]
    ],
    resize_keyboard=True
)



def get_outfit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏃 Sport", callback_data="style_sport")
    builder.button(text="👖 Opium", callback_data="style_opium")
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
        "opium": 5,
        "casual": 6,
        "archive": 5
    }

    if category > max_files.get(style, 5):
        category = max_files.get(style, 5)

    file_url = f"https://raw.githubusercontent.com/Fog67/tg/main/{style}{category}.png"

    style_names = {
        "sport": "🏃 Sport",
        "opium": "👖 Opium",
        "casual": "👕 Casual",
        "archive": "📦 Archive"
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
        82: ("🌧", "Очень сильный ливень"),
        85: ("🌨", "Снежная крупа"),
        86: ("🌨", "Сильный град со снегом"),
        95: ("⛈", "Гроза"),
        96: ("⛈", "Гроза с градом"),
        99: ("⛈", "Сильная гроза с градом"),
    }
    emoji, desc = codes.get(code, ("❓", "Неизвестно"))
    return f"{emoji} {desc}"


# Функция для парсинга времени
def parse_time(time_text: str) -> str | None:
    pattern = r'^([01]?\d|2[0-3]):([0-5]\d)$'
    match = re.match(pattern, time_text.strip())
    if match:
        hours, minutes = match.groups()
        return f"{int(hours):02d}:{int(minutes):02d}"
    return None


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
        f"✅ Координаты сохранены:\n🌐 {lat}, {lon}\n\n"
        f"Теперь выбери свою восприимчивость к температуре:",
        reply_markup=sensitivity_keyboard
    )


async def handle_sensitivity(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text

    if "мерзну" in text:
        user_sensitivity[user_id] = 1
        sensitivity_msg = "часто мёрзнешь"
    elif "Нормальная" in text:
        user_sensitivity[user_id] = 0
        sensitivity_msg = "Нормальная восприимчивость"
    elif "жарко" in text:
        user_sensitivity[user_id] = -1
        sensitivity_msg = "часто жарко"
    else:
        return

    await state.set_state(OutfitState.waiting_for_time)
    await message.reply(
        f"✅ Понял! Учту, что тебе {sensitivity_msg}.\n\n"
        f"⏰ В какое время ты хочешь получать рекомендации о погоде?\n"
        f"Введи время в формате ЧЧ:ММ (например: 08:00 или 18:30)",
        reply_markup=notification_time_keyboard
    )


async def handle_notification_time(message: types.Message, state: FSMContext):
    if message.text == "🔕 не хочу получать уведомления":
        user_id = message.from_user.id
        user_notifications_enabled[user_id] = False
        await state.clear()
        await message.reply(
            "✅ Уведомления отключены.\n"
            f"Теперь нажми «Узнать погоду ☁️», чтобы получить текущую погоду.",
            reply_markup=weather_menu_keyboard
        )
        return

    time_parsed = parse_time(message.text)

    if time_parsed is None:
        await message.reply(
            "❌ Некорректный формат времени.\n"
            f"Пожалуйста, введи время в формате ЧЧ:ММ (например: 08:00 или 18:30)",
            reply_markup=notification_time_keyboard
        )
        return

    user_id = message.from_user.id
    user_notification_time[user_id] = time_parsed
    user_notifications_enabled[user_id] = True

    await state.clear()
    await message.reply(
        f"✅ Отлично! Буду отправлять рекомендации в {time_parsed}.\n\n"
        f"Теперь нажми «Узнать погоду ☁️», чтобы получить текущую погоду и подобрать образ!",
        reply_markup=weather_menu_keyboard
    )


async def handle_back_to_start(message: types.Message, state: FSMContext):
    await state.clear()
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

        weather_full = decode_weather_code(current["weather_code"])
        weather_emoji, weather_desc = weather_full.split(" ", 1)

        temp = current["temperature_2m"]
        apparent_temp = current["apparent_temperature"]
        wind_speed = current["wind_speed_10m"]

        category = get_weather_category(apparent_temp, wind_speed)

        sensitivity = user_sensitivity.get(user_id, 0)
        category += sensitivity

        if category < 1:
            category = 1
        elif category > 5:
            category = 5

        weather_code = current["weather_code"]
        umbrella_message = ""
        if is_raining(weather_code):
            umbrella_message = "\n\n☔ **Совет: не забудь взять зонт!**"

        wind_message = ""
        if wind_speed > 10:
            wind_message = f"\n💨 **Сильный ветер! Будь осторожен.**"

        await state.update_data(
            temperature=temp,
            apparent_temperature=apparent_temp,
            wind_speed=wind_speed,
            category=category
        )

        text = (
            f"🌤 **Погода сейчас**:\n\n"
            f"🌡 Температура: {temp}°C\n"
            f"🌡 Ощущается как: {apparent_temp}°C\n"
            f"{weather_emoji} {weather_desc.strip()}\n"
            f"💧 Осадки: {current['precipitation']} мм/ч\n"
            f"💨 Ветер: {wind_speed} м/с"
            f"{wind_message}"
            f"{umbrella_message}\n\n"
            f"👇 **Выбери стиль образа:**"
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


async def handle_back_to_weather(callback: types.CallbackQuery):
    await callback.message.answer(
        "🌤 Нажми кнопку, чтобы узнать погоду",
        reply_markup=weather_menu_keyboard
    )
    await callback.answer()


# Функция для отправки ежедневных уведомлений
async def send_daily_notifications(bot: Bot):
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M")

            for user_id, notif_time in user_notification_time.items():
                if not user_notifications_enabled.get(user_id, False):
                    continue

                if notif_time == current_time:
                    if user_id not in user_locations:
                        continue

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

                        weather_full = decode_weather_code(current["weather_code"])
                        weather_emoji, weather_desc = weather_full.split(" ", 1)

                        temp = current["temperature_2m"]
                        apparent_temp = current["apparent_temperature"]
                        wind_speed = current["wind_speed_10m"]

                        category = get_weather_category(apparent_temp, wind_speed)
                        sensitivity = user_sensitivity.get(user_id, 0)
                        category += sensitivity

                        if category < 1:
                            category = 1
                        elif category > 5:
                            category = 5

                        weather_code = current["weather_code"]
                        umbrella_message = ""
                        if is_raining(weather_code):
                            umbrella_message = "\n\n☔ *Совет: не забудь взять зонт!*"

                        wind_message = ""
                        if wind_speed > 10:
                            wind_message = "\n💨 *Сильный ветер! Будь осторожен.*"

                        text = (
                            f"🌤 *Ежедневная сводка погоды:*\n\n"
                            f"🌡 Температура: {temp}°C\n"
                            f"🌡 Ощущается как: {apparent_temp}°C\n"
                            f"{weather_emoji} {weather_desc.strip()}\n"
                            f"💧 Осадки: {current['precipitation']} мм/ч\n"
                            f"💨 Ветер: {wind_speed} м/с"
                            f"{wind_message}"
                            f"{umbrella_message}\n\n"
                            f"👇 *Подбери образ:*"
                        )

                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            parse_mode="Markdown",
                            reply_markup=get_outfit_keyboard()
                        )

                        await asyncio.sleep(1)

                    except Exception as e:
                        print(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")

            await asyncio.sleep(30)

        except Exception as e:
            print(f"Ошибка в send_daily_notifications: {e}")
            await asyncio.sleep(30)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(handle_region_button, F.text == "Выбрать регион 📍")
    dp.message.register(handle_location, F.location)

    dp.message.register(handle_sensitivity, F.text.in_([
        "Часто мерзну",
        "Нормальная восприимчивость",
        "Часто жарко"
    ]))

    dp.message.register(handle_notification_time, OutfitState.waiting_for_time)

    dp.message.register(handle_weather, F.text == "Узнать погоду ☁️")

    dp.message.register(handle_back_to_start, F.text == "◀️ Назад")

    dp.callback_query.register(handle_outfit_choice, F.data.startswith("style_"))
    dp.callback_query.register(handle_back_to_weather, F.data == "back_to_weather")

    print("🤖 Бот запущен. Для остановки нажмите Ctrl+C.")

    scheduler_task = asyncio.create_task(send_daily_notifications(bot))

    try:
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())