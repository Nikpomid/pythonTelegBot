import os
import datetime
from peewee import SqliteDatabase, Model, CharField, BooleanField, DateField,IntegerField
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.types import ParseMode
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import pandas as pd
import io
import xlsxwriter
import sqlite3
from aiogram.dispatcher.filters import Text
import config
import logging
from aiogram.types.message import ContentType
import aiocron
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import Message
from enum import Enum
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.middlewares import LifetimeControllerMiddleware
import aiosqlite




# Определяем токен бота и chat_id суперпользователя
BOT_TOKEN = '2099288144:AAGXadtWRI9BNf5nt87TA4eLFoVtVz50DyE'
SUPERUSER_CHAT_ID = -1001806118480

# log
logging.basicConfig(level=logging.INFO)


bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализируем бота и диспетчера

# Определяем базу данных
db_path = os.path.join(os.path.dirname(__file__), 'users.db')
db = SqliteDatabase(db_path)


# Определяем модель пользователя
class User(Model):
    telegram_chat_id = CharField(unique=True)
    organization_name = CharField(null=True)
    contact_info = CharField(null=True)
    approved = BooleanField(default=False)
    is_subscribed = BooleanField(default=False)
    subscription_end_date = DateField(null=True)
    subscription_count = IntegerField(default=0)

    class Meta:
        database = db


# Создаем таблицу пользователей в базе данных, если ее нет
with db:
    db.create_tables([User])


# Определяем токен бота и chat_id суперпользователя
BOT_TOKEN = '2099288144:AAGXadtWRI9BNf5nt87TA4eLFoVtVz50DyE'
SUPERUSER_CHAT_ID = -1001806118480

# log
logging.basicConfig(level=logging.INFO)


bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализируем бота и диспетчера

# Определяем базу данных
db_path = os.path.join(os.path.dirname(__file__), 'users.db')
db = SqliteDatabase(db_path)


# Определяем модель пользователя
class User(Model):
    telegram_chat_id = CharField(unique=True)
    organization_name = CharField(null=True)
    contact_info = CharField(null=True)
    approved = BooleanField(default=False)
    is_subscribed = BooleanField(default=False)
    subscription_end_date = DateField(null=True)
    subscription_count = IntegerField(default=0)

    class Meta:
        database = db


# Создаем таблицу пользователей в базе данных, если ее нет
with db:
    db.create_tables([User])


class RegistrationState(StatesGroup):
    waiting_for_organization_name = State()
    waiting_for_contact_info = State()


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    # Получаем пользователя из базы данных
    user = User.get_or_create(telegram_chat_id=str(message.chat.id))[0]

    if user.approved:
        await message.answer("Вы уже зарегистрированы.")
    elif user.contact_info:
        await message.answer("Ваш запрос на регистрацию уже был отправлен и находится на рассмотрении.")
    else:
        # Отправляем приветственное сообщение при команде /start
        await message.answer("Здравствуйте! Чтобы зарегистрироваться, отправьте название организации.")

        # Переходим в состояние ожидания названия организации
        await RegistrationState.waiting_for_organization_name.set()


@dp.message_handler(state=RegistrationState.waiting_for_organization_name)
async def process_organization_name(message: types.Message, state: FSMContext):
    # Получаем пользователя из базы данных
    user = User.get_or_none(telegram_chat_id=str(message.chat.id))
    if message.chat.id == SUPERUSER_CHAT_ID:
        await message.answer("Суперпользователь не может быть зарегистрирован.")
        return

    if user is None:
        # Если запись пользователя не существует,
        # создаем ее
        user = User.create(telegram_chat_id=str(message.chat.id))

    # Сохраняем название организации
    user.organization_name = message.text
    user.save()

    # Отправляем сообщение о том, что запрос на регистрацию отправлен
    await message.reply('Введите контактную информацию.')

    # Переходим в состояние ожидания контактной информации
    await RegistrationState.waiting_for_contact_info.set()


@dp.message_handler(state=RegistrationState.waiting_for_contact_info)
async def process_contact_info(message: types.Message, state: FSMContext):
    # Получаем пользователя из базы данных
    user = User.get_or_none(telegram_chat_id=str(message.chat.id))
    if user is None:
        # Если запись пользователя не существует,
        # создаем ее
        user = User.create(telegram_chat_id=str(message.chat.id))

    # Сохраняем контактную информацию
    user.contact_info = message.text
    user.save()

    # Отправляем сообщение о том, что запрос на регистрацию отправлен
    await message.reply('Запрос на регистрацию отправлен на рассмотрение Озерцо-логистик')

    keyboard = InlineKeyboardMarkup(row_width=2)
    approve_button = InlineKeyboardButton('Принять', callback_data=f'approve_{user.telegram_chat_id}')
    reject_button = InlineKeyboardButton('Отклонить', callback_data=f'reject_{user.telegram_chat_id}')
    invalid_button = InlineKeyboardButton('Неверный формат', callback_data=f'invalid_{user.telegram_chat_id}')
    keyboard.add(approve_button, reject_button, invalid_button)

    # Формируем сообщение для администратора
    message_for_admin = f"Пользователь {user.organization_name} ({user.contact_info}) запрашивает регистрацию."
    # Отправляем сообщение администратору
    await bot.send_message(chat_id=SUPERUSER_CHAT_ID, text=message_for_admin, reply_markup=keyboard)

    # Переходим в начальное состояние
    await state.finish()


# Клавиатура для выбора пункта меню
menu_keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
menu_keyboard.add(
    types.KeyboardButton("1 - Краткий номер уведомления"),
    types.KeyboardButton("2 - Транспортное средство, прицеп"),
    types.KeyboardButton("3 - Получатель"),
    types.KeyboardButton("4 - Номер уведомления"),
    types.KeyboardButton("5 - Регистрационный номер уведомления"),
    types.KeyboardButton("6 - Разрешение на временное хранение"),
    types.KeyboardButton("7 - Номер предшествующего свидетельства"),
    types.KeyboardButton("8 - Книжка МДП"),
    types.KeyboardButton("9 - INV"),
    types.KeyboardButton("10 - CMR"),
    types.KeyboardButton("11 - Выход")
)


menu_to_field = {
    "1 - Краткий номер уведомления": "brief_number",
    "2 - Транспортное средство, прицеп": "transport",
    "3 - Получатель": "recipient",
    "4 - Номер уведомления": "notice_number",
    "5 - Регистрационный номер уведомления": "registration_number",
    "6 - Разрешение на временное хранение": "permission",
    "7 - Номер предшествующего свидетельства": "previous_certificate",
    "8 - Книжка МДП": "mdp_book",
    "9 - INV": "inv",
    "10 - CMR": "cmr"
}


class SearchStates(StatesGroup):
    CHOOSING_FIELD = State()
    ENTERING_VALUE = State()


# Определяем хендлер для команды /search, который будет запускать FSM
@dp.message_handler(commands=['search'], state='*')
async def search_handler(message: Message):
    # проверяем, подписан ли пользователь
    user = User.get_or_none(telegram_chat_id=str(message.from_user.id), approved=True, is_subscribed=True)

    if user:
        # Запускаем FSM, переводим пользователя в состояние CHOOSING_FIELD
        await SearchStates.CHOOSING_FIELD.set()
        await message.answer("Вас приветствует Озерцо-Логистик🔥\n\n"
                             "❗️Выберите пункт меню по которому надо найти данные  в ЗТК ❗️", reply_markup=menu_keyboard)
    else:
        await bot.send_message(message.chat.id, "Вы не являетесь подписчиком нашего бота или не прошли модерацию. "
                                                "Для подписки используйте команду /buy")


# Хендлер для обработки выбора поля из меню
@dp.message_handler(lambda message: message.text in menu_to_field.keys(), state=SearchStates.CHOOSING_FIELD)
async def process_field_choice(message: Message, state: FSMContext):
    async with state.proxy() as data:
        # Сохраняем выбранное поле в переменной field
        data['field'] = menu_to_field.get(message.text)

    # Переводим пользователя в состояние ENTERING_VALUE
    await SearchStates.ENTERING_VALUE.set()

    # Отправляем сообщение с запросом на ввод значения для выбранного поля
    await message.answer(f"Введите значение для поля '{message.text}':")


# Хендлер для обработки введенного значения поля
@dp.message_handler(state=SearchStates.ENTERING_VALUE)
async def process_value(message: Message, state: FSMContext):
    async with state.proxy() as data:
        # Сохраняем введенное значение в переменной value
        data['value'] = message.text
        field = data.get('field')

        # Выполняем поиск данных в базе данных
        async with aiosqlite.connect('data.db') as conn:
            async with conn.execute(f"SELECT number, brief_number, date, transport, recipient, notice_number, "
                                     f"registration_number, permission, previous_certificate, mdp_book, inv, cmr "
                                     f"FROM data WHERE {data['field']} = ?", (data['value'],)) as cursor:
                # Получаем найденные данные
                rows = await cursor.fetchall()

        # Если ничего не найдено, сообщаем об этом пользователю
        if not rows:
            await message.answer("Ничего не найдено.")
            # Переводим пользователя в состояние CHOOSING_FIELD
            await SearchStates.CHOOSING_FIELD.set()

            # Отправляем сообщение с меню для нового поиска
            await message.answer("Выберите пункт меню по которому надо найти данные  в ЗТК", reply_markup=menu_keyboard)
            return

        # Выводим найденные данные в сообщении пользователю
        for row in rows:
            data_str = f"📝Данные по запросу '{message.text}':\n" \
                       f"📌Краткий номер уведомления: {row[1]}\n" \
                       f"⏱️Дата: {row[2]}\n" \
                       f"🚗Транспорт: {row[3]}\n" \
                       f"📦👤Получатель: {row[4]}\n" \
                       f"🔢📩Номер уведомления: {row[5]}\n" \
                       f"📝🔢Регистрационный номер уведомления: {row[6]}\n" \
                       f"🕒🏭Разрешение на временное хранение: {row[7]}\n" \
                       f"🔙📜Номер предшествующего свидетельства: {row[8]}\n" \
                       f"📖🚛Книжка МДП: {row[9]}\n" \
                       f"💰📊INV: {row[10]}\n" \
                       f"📜🚛CMR: {row[11]}"
            await message.answer(data_str)

            # Проверяем, что пользователь не подписан на данное значение
            async with aiosqlite.connect('data.db') as conn:
                await conn.execute('CREATE TABLE IF NOT EXISTS sub_value (chat_id INTEGER, field TEXT, value TEXT)')
                await conn.commit()

                cursor = await conn.execute('SELECT 1 FROM sub_value WHERE chat_id = ? AND field = ? AND value = ?',
                                            (message.chat.id, field, data['value']))
                row = await cursor.fetchone()
                if row is not None:
                    # Значение уже существует для данного пользователя и поля, сообщаем об этом и выходим из функции
                    await message.answer(
                        f"Значение '{data['value']}' для поля '{field}' уже существует в базе данных.")
                    return

                await conn.execute("INSERT INTO sub_value (chat_id, field, value) VALUES (?, ?, ?)",
                                   (message.chat.id, field, data['value']))
                await conn.commit()

            # Сообщаем пользователю, что значение успешно сохранено
            await message.answer(f"Значение '{data['value']}' для поля '{field}' успешно сохранено в базе данных.")

        # Сохраняем данные в FSMContext
        await state.finish()

        # Переводим пользователя в состояние CHOOSING_FIELD
        await SearchStates.CHOOSING_FIELD.set()

        # Отправляем сообщение с меню для нового поиска
        await message.answer("Выберите пункт меню по которому надо найти данные  в ЗТК", reply_markup=menu_keyboard)


@dp.message_handler(lambda message: message.text == "11 - Выход",
                    state=[SearchStates.CHOOSING_FIELD, SearchStates.ENTERING_VALUE, 'search'])
async def handle_search_exit(message: types.Message, state: FSMContext):
    # Очищаем FSMContext
    await state.finish()

    # Создаем клавиатуру предыдущего меню
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/time (Оставшейся время подписки)'))
    keyboard.add(KeyboardButton('/search (Поиск по любому элементу в ЗТК)'))

    # Отправляем сообщение о выходе
    await bot.send_message(message.chat.id, "Выход из меню.", reply_markup=keyboard)


@dp.message_handler(Command("time"))
async def show_subscription_time(message: types.Message):
    user = User.get_or_none(telegram_chat_id=str(message.chat.id), approved=True, is_subscribed=True)
    if user:
        remaining_time = user.subscription_end_date - datetime.date.today()
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton('/time (Оставшейся время подписки)'))
        keyboard.add(KeyboardButton('/search (Поиск по любому элементу)'))
        await message.answer(f"Ваша подписка действительна еще {remaining_time.days} дней",
                             reply_markup=keyboard)






dp.register_message_handler(cmd_start, commands=['start'])


# Запускаем бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
