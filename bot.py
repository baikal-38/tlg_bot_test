import os
import logging
import requests
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен и URL для Render
TOKEN = os.environ.get('BOT_TOKEN')
TOKEN = "8569440409:AAGoh6HUFu3jquVunO0XN_Y3Msme24KjS4k"
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')

# Координаты Иркутска
LATITUDE = 52.2978
LONGITUDE = 104.2964

def get_weather_forecast(days=3):
    """Получение прогноза с open-meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": ["temperature_2m_max", "temperature_2m_min"],
        "timezone": "Asia/Irkutsk",
        "forecast_days": days
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        dates = data['daily']['time']
        max_temps = data['daily']['temperature_2m_max']
        min_temps = data['daily']['temperature_2m_min']
        return dates, max_temps, min_temps
    except Exception as e:
        logger.error(f"Ошибка при получении погоды: {e}")
        return None, None, None

def get_chart_image(dates, max_temps, min_temps):
    """Формирует и отправляет POST-запрос на QuickChart, возвращает байты PNG."""
    labels = [d[5:] for d in dates]  # YYYY-MM-DD -> MM-DD

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Днём",
                    "data": max_temps,
                    "borderColor": "rgb(255, 99, 132)",
                    "backgroundColor": "rgba(255, 99, 132, 0.5)",
                    "fill": False,
                    "tension": 0.1
                },
                {
                    "label": "Ночью",
                    "data": min_temps,
                    "borderColor": "rgb(54, 162, 235)",
                    "backgroundColor": "rgba(54, 162, 235, 0.5)",
                    "fill": False,
                    "tension": 0.1
                }
            ]
        },
        "options": {
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Прогноз погоды в Иркутске"
                }
            },
            "scales": {
                "y": {
                    "ticks": {
                        "callback": "function(value) { return value + '°C'; }"
                    }
                }
            }
        }
    }

    response = requests.post(
        "https://quickchart.io/chart",
        json={"chart": chart_config},
        timeout=15
    )
    response.raise_for_status()
    return response.content

def get_main_keyboard():
    """Создаёт инлайн-клавиатуру с основными действиями."""
    keyboard = [
        [InlineKeyboardButton("🌤 Погода (текст)", callback_data='weather')],
        [InlineKeyboardButton("📈 График", callback_data='chart')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_main_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение с главным меню."""
    await context.bot.send_message(
        chat_id=chat_id,
        text="Выберите действие:",
        reply_markup=get_main_keyboard()
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветствие и показывает кнопки."""
    await update.message.reply_text(
        "Привет! Я бот погоды в Иркутске.\n"
        "Используйте кнопки ниже для получения прогноза.",
        reply_markup=get_main_keyboard()
    )

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текстовый прогноз погоды, затем снова показывает меню."""
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    dates, max_temps, min_temps = get_weather_forecast(days=16)

    if dates is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Не удалось получить прогноз. Попробуйте позже."
        )
    else:
        message = "🌤 Прогноз погоды в Иркутске:\n\n"
        for i in range(len(dates)):
            short_date = dates[i][5:]  # ММ-ДД
            message += f"📅 {short_date}: {max_temps[i]}/{min_temps[i]}°C\n"

        await context.bot.send_message(chat_id=chat_id, text=message)

    # Возвращаем меню
    await send_main_menu(chat_id, context)

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Строит и отправляет график температуры, затем снова показывает меню."""
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='upload_photo')
    dates, max_temps, min_temps = get_weather_forecast(days=15)

    if dates is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Не удалось получить данные для графика."
        )
    else:
        try:
            image_bytes = get_chart_image(dates, max_temps, min_temps)
            photo = io.BytesIO(image_bytes)
            photo.name = "weather_chart.png"
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption="Прогноз температуры на ближайшие дни"
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к QuickChart: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Сервис графиков временно недоступен. Попробуйте позже."
            )
        except Exception as e:
            logger.error(f"Ошибка при создании графика: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Не удалось сгенерировать график. Попробуйте позже."
            )

    # Возвращаем меню
    await send_main_menu(chat_id, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на инлайн-кнопки."""
    query = update.callback_query
    await query.answer()  # убираем состояние загрузки на кнопке

    if query.data == 'weather':
        await weather(update, context)
    elif query.data == 'chart':
        await chart(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    if not TOKEN:
        raise ValueError("Токен бота не задан! Укажите BOT_TOKEN в переменных окружения.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    if RENDER_URL:
        port = int(os.environ.get("PORT", 10000))
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        logger.info(f"Запуск вебхука на порту {port}, URL: {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,
            webhook_url=webhook_url
        )
    else:
        logger.info("Запуск polling...")
        app.run_polling()

if __name__ == "__main__":
    main()
