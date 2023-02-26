import os
from peewee import SqliteDatabase, Model, CharField, BooleanField
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

# Определяем токен бота и chat_id суперпользователя
BOT_TOKEN = '2099288144:AAGXadtWRI9BNf5nt87TA4eLFoVtVz50DyE'
SUPERUSER_CHAT_ID = -1001806118480

# Инициализируем бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Определяем базу данных
db_path = os.path.join(os.path.dirname(__file__), 'users.db')
db = SqliteDatabase(db_path)


# Определяем модель пользователя
class User(Model):
    telegram_chat_id = CharField(unique=True)
    organization_name = CharField(null=True)
    contact_info = CharField(null=True)
    approved = BooleanField(default=False)

    class Meta:
        database = db


# Создаем таблицу пользователей в базе данных, если ее нет
with db:
    db.create_tables([User])


# Определяем функцию-обработчик команды /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("Здравствуйте! Чтобы зарегистрироваться, отправьте следующую информацию:\n"
                         "Название организации Введите контактную информацию (адрес, телефон, e-mail)")


# Определяем функцию-обработчик сообщений
@dp.message_handler()
async def process_registration(message: types.Message):
    # Проверяем, есть ли у пользователя запись в базе данных
    user = User.get_or_none(telegram_chat_id=str(message.chat.id))

    if not user or not user.organization_name or not user.contact_info:
        # Если запись пользователя не существует, или отсутствует информация об организации или контактах,
        # создаем ее или получаем из базы данных
        user = User.get_or_create(telegram_chat_id=str(message.chat.id))[0]

        # Если отсутствует информация об организации или контактах,
        # запрашиваем название организации и контактную информацию
        parts = message.text.split('.')
        if len(parts) >= 2:
            user.organization_name = parts[0].strip()
            user.contact_info = '.'.join(parts[1:]).strip()
            user.save()
            # Отправляем сообщение о том, что запрос на регистрацию отправлен
            await message.reply('Запрос на регистрацию отправлен на рассмотрение Озерцо-логистик')

            # Формируем запрос на регистрацию
            registration_request = (
                f"Запрос на регистрацию от {user.organization_name}\n"
                f"Контактная информация: {user.contact_info}\n"
                f"Telegram chat_id: {user.telegram_chat_id}"
            )

            # Отправляем запрос на регистрацию
            if registration_request:
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
                keyboard.add(KeyboardButton('Принять'))
                keyboard.add(KeyboardButton('Отклонить'))
                keyboard.add(KeyboardButton('Неверный формат'))
                await bot.send_message(chat_id=SUPERUSER_CHAT_ID, text=registration_request,
                                       parse_mode=ParseMode.HTML, reply_markup=keyboard)

        else:
            await message.reply(
                'Неверный формат. Введите контактную информацию и название организации, разделив их точкой')
    elif not user.approved:
        await message.reply('Запрос на регистрацию отправлен на рассмотрение Озерцо-логистик')



@dp.callback_query_handler(lambda callback_query: True)
async def process_callback(callback_query: types.CallbackQuery):
    # Получаем данные из callback_data
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user = User.get(telegram_chat_id=str(chat_id))

    if data == 'approve':
        # Одобряем пользователя
        user.approved = True
        user.save()
        await bot.send_message(chat_id=chat_id, text='Вы были одобрены и зарегистрированы')
    elif data == 'reject':
        # Отклоняем пользователя и удаляем запись из базы данных
        user.delete_instance()
        await bot.send_message(chat_id=chat_id, text='Ваш запрос на регистрацию был отклонен')
    elif data == 'wrong_format':
        # Удаляем пользователя и сообщаем о неверном формате данных
        user.delete_instance()
        await bot.send_message(chat_id=chat_id, text='Неверный формат данных. Пожалуйста, зарегистрируйтесь заново')
        await cmd_start(callback_query.message)


dp.register_message_handler(cmd_start, commands=['start'])
dp.register_message_handler(process_registration)

# Запускаем бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
