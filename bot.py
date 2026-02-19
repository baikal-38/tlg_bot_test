import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логирования (поможет при отладке)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота берём из переменных окружения
TOKEN = os.environ.get('BOT_TOKEN')
# TOKEN = "8569440409:AAGoh6HUFu3jquVunO0XN_Y3Msme24KjS4k"
# URL вашего сервиса на Render (будет использован для вебхука)
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')  # например https://your-app.onrender.com

# Координаты Иркутска
LATITUDE = 52.2978
LONGITUDE = 104.2964

def get_weather_forecast(days=14):
    """
    Запрашивает прогноз погоды с open-meteo.com
    Возвращает списки дат, максимальных и минимальных температур.
    """
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

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот погоды в Иркутске.\n"
        "Используй команду /weather, чтобы узнать прогноз на ближайшие дни."
    )

# Обработчик команды /weather
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Получаю данные о погоде...")
    dates, max_temps, min_temps = get_weather_forecast(days=16)

    if dates is None:
        await update.message.reply_text("Не удалось получить прогноз. Попробуйте позже.")
        return

    message = "🌤 Прогноз погоды в Иркутске:\n\n"
    for i in range(len(dates)):
        message += f"📅 {dates[i]}    🌡 Днём: {max_temps[i]}°C    🌙 Ночью: {min_temps[i]}°C\n"

    await update.message.reply_text(message)

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """Главная функция запуска бота."""
    if not TOKEN:
        raise ValueError("Токен бота не задан! Укажите BOT_TOKEN в переменных окружения.")

    # Создаём приложение
    app = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather))
    app.add_error_handler(error_handler)

    # Определяем способ запуска
    if RENDER_URL:
        # Запуск через вебхуки (для Render)
        port = int(os.environ.get("PORT", 10000))
        webhook_url = f"{RENDER_URL}/{TOKEN}"  # URL, на который Telegram будет слать обновления
        logger.info(f"Запуск вебхука на порту {port}, URL: {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,           # путь, по которому будут приходить обновления
            webhook_url=webhook_url
        )
    else:
        # Локальный запуск через polling (опрос)
        logger.info("Запуск polling...")
        app.run_polling()

if __name__ == "__main__":
    main()
