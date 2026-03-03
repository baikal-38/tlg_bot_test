import os
import logging
import requests
import io
import socket
import datetime
import sys
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен и URL для Render
TOKEN = os.environ.get('BOT_TOKEN')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')

if not TOKEN:
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")

# Координаты Иркутска
LATITUDE = 52.2978
LONGITUDE = 104.2964

def get_weather_icon(wmo_code: int) -> str:
    """
    Возвращает эмодзи для кода погоды WMO.
    Коды согласно документации Open-Meteo: https://open-meteo.com/en/docs
    """
    if wmo_code == 0:
        return "☀️"          # ясно
    elif wmo_code == 1:
        return "🌤"          # преимущественно ясно
    elif wmo_code == 2:
        return "⛅"          # переменная облачность
    elif wmo_code == 3:
        return "☁️"          # пасмурно
    elif wmo_code in [45, 48]:
        return "🌫"          # туман
    elif wmo_code in [51, 53, 55, 56, 57]:
        return "🌧"          # морось
    elif wmo_code in [61, 63, 65, 66, 67, 80, 81, 82]:
        return "🌧"          # дождь
    elif wmo_code in [71, 73, 75, 77, 85, 86]:
        return "🌨"          # снег
    elif wmo_code in [95, 96, 99]:
        return "⛈"          # гроза
    else:
        return "🌡"          # неизвестно

def get_weather_forecast(days=3):
    """
    Получение прогноза с open-meteo.
    Возвращает кортеж: (dates, max_temps, min_temps, weathercodes, precip_sum)
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "weathercode",
            "precipitation_sum"
        ],
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
        weathercodes = data['daily']['weathercode']
        precip_sum = data['daily']['precipitation_sum']
        return dates, max_temps, min_temps, weathercodes, precip_sum
    except Exception as e:
        logger.error(f"Ошибка при получении погоды: {e}")
        return None, None, None, None, None

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
    """Создаёт Reply-клавиатуру с основными действиями."""
    keyboard = [
        ["🌤 Погода (текст)"],
        ["📈 График"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def send_main_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение с главным меню (клавиатура уже видна, но можно напомнить)."""
    await context.bot.send_message(
        chat_id=chat_id,
        text="Выберите действие с помощью кнопок ниже:",
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
    """Отправляет текстовый прогноз погоды (температура + осадки), затем снова показывает меню."""
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    dates, max_temps, min_temps, weathercodes, precip_sum = get_weather_forecast(days=16)

    if dates is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Не удалось получить прогноз. Попробуйте позже."
        )
    else:
        message = "🌤 Прогноз погоды в Иркутске:\n\n"
        for i in range(len(dates)):
            short_date = dates[i][5:]  # ММ-ДД
            icon = get_weather_icon(weathercodes[i])
            precip = precip_sum[i]
            if precip and precip > 0:
                precip_str = f"{precip:.1f} мм"
            else:
                precip_str = ""
            message += f"{short_date}: {min_temps[i]}/{max_temps[i]} {icon} {precip_str}\n"

        await context.bot.send_message(chat_id=chat_id, text=message)

    # Возвращаем меню
    await send_main_menu(chat_id, context)

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Строит и отправляет график температуры, затем снова показывает меню."""
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='upload_photo')
    # Нам нужны только даты и температуры, остальное игнорируем
    dates, max_temps, min_temps, _, _ = get_weather_forecast(days=15)

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

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о месте запуска бота."""
    lines = []
    
    if os.getenv('RENDER'):
        lines.append("🚀 Платформа: **Render (облако)**")
        lines.append(f"• RENDER_EXTERNAL_URL: {os.getenv('RENDER_EXTERNAL_URL', 'не задан')}")
        lines.append(f"• RENDER_INSTANCE_ID: {os.getenv('RENDER_INSTANCE_ID', 'не задан')}")
    elif os.getenv('RENDER_EXTERNAL_URL'):
        lines.append("🚀 Платформа: **Render (облако)**")
        lines.append(f"• RENDER_EXTERNAL_URL: {os.getenv('RENDER_EXTERNAL_URL')}")
    else:
        lines.append("💻 Платформа: **Локальная машина**")
    
    if RENDER_URL:
        lines.append(f"🌐 Режим Webhook")
    else:
        lines.append("🔄 Режим polling (webhook не используется)")
    
    hostname = socket.gethostname()
    lines.append(f"🖥️ Имя хоста: {hostname}")
    
    cwd = os.getcwd()
    lines.append(f"📁 Рабочая директория: {cwd}")
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"⏰ Время сервера: {now}")
    
    lines.append(f"🐍 Версия Python: {sys.version.split()[0]}")
    
    await update.message.reply_text("\n".join(lines))

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на Reply-кнопки (текстовые сообщения)."""
    text = update.message.text
    if text == "🌤 Погода (текст)":
        await weather(update, context)
    elif text == "📈 График":
        await chart(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    if not TOKEN:
        raise ValueError("Токен бота не задан! Укажите BOT_TOKEN в переменных окружения.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    # Хендлер для Reply-кнопок – ловим точный текст кнопок
    app.add_handler(MessageHandler(
        filters.Text(["🌤 Погода (текст)", "📈 График"]),
        handle_menu_buttons
    ))

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
