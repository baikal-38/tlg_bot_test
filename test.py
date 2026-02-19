from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Замените 'YOUR_TOKEN' на полученный токен
TOKEN = '8569440409:AAGoh6HUFu3jquVunO0XN_Y3Msme24KjS4k'

# Обработчик команды /start
async def start(update: Update, context):
    await update.message.reply_text('Привет! Я бот.')

# Обработчик текстовых сообщений
async def echo(update: Update, context):
    await update.message.reply_text(update.message.text)

# Настройка и запуск бота
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    app.run_polling()
