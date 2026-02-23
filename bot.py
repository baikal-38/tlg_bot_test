import os
import logging
import requests
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен и URL для Render
TOKEN = os.environ.get('BOT_TOKEN')
TOKEN = "8282281956:AAHAQ0O3JbXg6yFxK0sofZfmvX0lzi8Uaqc"
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
            "plugins": {                              # <-- заголовок теперь в plugins
                "title": {
                    "display": True,
                    "text": "Прогноз погоды в Иркутске"
                }
            },
            "scales": {
                "y": {                                 # <-- вместо yAxes
                    "ticks": {
                        "callback": "function(value) { return value + '°C'; }"
                    }
                }
            }
        }
    }

    logger.error(chart_config)

    response = requests.post(
        "https://quickchart.io/chart",
        json={"chart": chart_config},
        timeout=15
    )
    
    response.raise_for_status()
    return response.content

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот погоды в Иркутске.\n"
        "/weather — текстовый прогноз\n"
        "/chart — график температуры"
    )

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Получаю данные о погоде...")
    dates, max_temps, min_temps = get_weather_forecast(days=16)

    if dates is None:
        await update.message.reply_text("Не удалось получить прогноз. Попробуйте позже.")
        return

    message = "🌤 Прогноз погоды в Иркутске:\n\n"
    for i in range(len(dates)):
        short_date = dates[i][5:]  # ММ-ДД
        message += f"📅 {short_date}: {max_temps[i]}/{min_temps[i]}°C\n"

    await update.message.reply_text(message)

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Строю график...")
    dates, max_temps, min_temps = get_weather_forecast(days=15)

    if dates is None:
        await update.message.reply_text("Не удалось получить данные для графика.")
        return

    try:
        image_bytes = get_chart_image(dates, max_temps, min_temps)
        photo = io.BytesIO(image_bytes)
        photo.name = "weather_chart.png"
        await update.message.reply_photo(photo=photo, caption="Прогноз температуры на ближайшие дни")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к QuickChart: {e}")
        await update.message.reply_text("Сервис графиков временно недоступен. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка при создании графика: {e}")
        await update.message.reply_text("Не удалось сгенерировать график. Попробуйте позже.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    if not TOKEN:
        raise ValueError("Токен бота не задан! Укажите BOT_TOKEN в переменных окружения.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("chart", chart))
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
