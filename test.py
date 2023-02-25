import os
from peewee import SqliteDatabase, Model, CharField, BooleanField
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
    # Получаем пользователя из базы данных
    user = User.get_or_create(telegram_chat_id=str(message.chat.id))[0]

    if user.approved:
        await message.answer("Вы уже зарегистрированы.")
    else:
        # Отправляем приветственное сообщение при команде /start
        await message.answer("Здравствуйте! Чтобы зарегистрироваться, отправьте следующую информацию:\n"
                             "Название организации. Контактная информация (адрес, телефон, e-mail)")

# Создаем InlineKeyboard для кнопок
registration_keyboard = InlineKeyboardMarkup(row_width=2)
approve_button = InlineKeyboardButton('Принять', callback_data='approve')
reject_button = InlineKeyboardButton('Отклонить', callback_data='reject')
invalid_button = InlineKeyboardButton('Неверный формат', callback_data='invalid')
registration_keyboard.add(approve_button, reject_button, invalid_button)

# В обработчике сообщения с запросом на регистрацию
@dp.message_handler()
async def process_registration(message: types.Message):
    # Проверяем, есть ли у пользователя запись в базе данных
    user = User.get_or_none(telegram_chat_id=str(message.chat.id))
    if user is None:
        # Если запись пользователя не существует,
        # создаем ее
        user = User.create(telegram_chat_id=str(message.chat.id))

    if not user.organization_name or not user.contact_info:
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


            keyboard = InlineKeyboardMarkup(row_width=2)
            approve_button = InlineKeyboardButton('Принять', callback_data=f'approve_{user.telegram_chat_id}')
            reject_button = InlineKeyboardButton('Отклонить', callback_data=f'reject_{user.telegram_chat_id}')
            wrong_format_button = InlineKeyboardButton('Не верный формат',
                                                       callback_data=f'wrong_format_{user.telegram_chat_id}')
            keyboard.add(approve_button, reject_button, wrong_format_button)

            # Формируем запрос на регистрацию
            registration_request = (
                f"Запрос на регистрацию от {user.organization_name}\n"
                f"Контактная информация: {user.contact_info}\n"
                f"Telegram chat_id: {user.telegram_chat_id}"
            )

            # Отправляем запрос на регистрацию суперпользователю
            if registration_request:
                await bot.send_message(chat_id=SUPERUSER_CHAT_ID, text=registration_request,
                                       parse_mode=ParseMode.HTML, reply_markup=keyboard)

        else:
            await message.reply(
                'Неверный формат. Введите контактную информацию и название организации, разделив их точкой')
    elif not user.approved:
        await message.reply('Запрос на регистрацию уже отправлен на рассмотрение Озерцо-логистик')


# Обработчик InlineKeyboardButton "Принять"
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('approve_'))
async def process_approve(callback_query: types.CallbackQuery):
    # Получаем chat_id пользователя из callback_data
    user_chat_id = callback_query.data.split('_')[1]
    # Получаем пользователя из базы данных по chat_id
    user = User.get_or_none(telegram_chat_id=str(user_chat_id))
    if user:
        # Устанавливаем флаг approved=True и сохраняем пользователя в базе данных
        user.approved = True
        user.save()
        # Удаляем InlineKeyboard
        await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id)
        # Отправляем сообщение пользователю о том, что его запрос на регистрацию одобрен
        await bot.send_message(chat_id=user.telegram_chat_id, text='Ваш запрос на регистрацию одобрен')


# Обработчик InlineKeyboardButton "Отклонить"
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('reject_'))
async def process_reject(callback_query: types.CallbackQuery):
    # Получаем chat_id пользователя из callback_data
    user_chat_id = callback_query.data.split('_')[1]
    # Удаляем InlineKeyboard
    await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id)
    # Отправляем сообщение пользователю о том, что его запрос на регистрацию отклонен
    await bot.send_message(chat_id=user_chat_id, text='Ваш запрос на регистрацию отклонен')


# Обработчик InlineKeyboardButton "Неверный формат"
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('wrong_format_'))
async def process_wrong_format(callback_query: types.CallbackQuery):
    # Получаем chat_id пользователя из callback_data
    user_chat_id = callback_query.data.split('_')[1]
    # Удаляем InlineKeyboard
    await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id)
    # Отправляем сообщение пользователю о том, что в его запросе на регистрацию был неверный формат
    await bot.send_message(chat_id=user_chat_id, text='В вашем запросе на регистрацию был неверный формат')

dp.register_message_handler(cmd_start, commands=['start'])
dp.register_message_handler(process_registration)

# Запускаем бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
